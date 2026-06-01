"""PrusaLink (Prusa) send-to-printer connector (ROADMAP Stage 3).

A third concrete :class:`~kimcad.printer_connector.PrinterConnector`, talking to a Prusa
printer through its local PrusaLink REST API (``/api/v1``, stdlib HTTP only — no new
dependency). Covers Prusa MK4/MK3.9/MINI/XL running PrusaLink.

Auth: PrusaLink accepts an API key (found in the printer's PrusaLink settings) sent as an
``X-Api-Key`` header — the same scheme real clients (e.g. PrusaLinkPy) use. ``send`` extracts
the printable G-code from KimCad's ``*.gcode.3mf`` and uploads it with ``PUT
/api/v1/files/<storage>/<name>`` plus the ``Print-After-Upload: ?1`` header (upload-and-start),
after the shared :func:`~kimcad.printer_connector.ensure_sendable` gate.

Tested against :mod:`kimcad.mock_prusalink`; no real hardware is driven until Kim's beta
(Stage 10).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from kimcad.printer_connector import (
    AuthError,
    ConnectorError,
    JobState,
    PrinterCapabilities,
    PrinterOffline,
    PrinterState,
    PrinterStatus,
    PrintJob,
    auth_error_if_upload_rejected,
    decode_json,
    ensure_sendable,
    extract_single_plate_gcode,
    read_error_body,
)

_ERR_BODY_CAP = 300

# PrusaLink printer.state -> our normalized PrinterState
_PRINT_STATE = {
    "idle": PrinterState.operational,
    "ready": PrinterState.operational,
    "finished": PrinterState.operational,
    "stopped": PrinterState.operational,
    "printing": PrinterState.printing,
    "busy": PrinterState.printing,
    "paused": PrinterState.paused,
    "attention": PrinterState.error,
    "error": PrinterState.error,
}


def _prusalink_error_detail(e: urllib.error.HTTPError) -> str:
    """Bounded extraction of PrusaLink's error reason. PrusaLink returns
    ``{"title": "...", "message": "..."}`` on errors; fall back to the raw bounded text."""
    text = read_error_body(e, cap=_ERR_BODY_CAP)
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            msg = parsed.get("message") or parsed.get("title")
            if msg:
                text = str(msg)
    except ValueError:
        pass
    text = " ".join(text.split())
    return f" — {text[:_ERR_BODY_CAP]}" if text else ""


class PrusaLinkConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for Prusa printers via PrusaLink.

    Holds no per-request state (only the base URL + API key + storage), so one instance is
    safe to share across the threaded web server's request handlers.
    """

    drives_hardware = True  # a real send reaches a real printer

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        name: str = "prusalink",
        storage: str = "usb",
        timeout_s: float = 15.0,
    ):
        self.name = name
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._storage = storage
        self._timeout = timeout_s

    # --- HTTP plumbing ------------------------------------------------------
    def _request(
        self,
        method: str,
        path: str,
        *,
        data: bytes | None = None,
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(self._base + path, data=data, method=method)
        req.add_header("X-Api-Key", self._key)
        if content_type:
            req.add_header("Content-Type", content_type)
        for k, v in (extra_headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return resp.status, resp.read()

    def _get_json(self, path: str) -> dict[str, Any]:
        _status, raw = self._request("GET", path)
        return decode_json(raw, name=self.name)

    # --- connector contract -------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        try:
            info = self._get_json("/api/v1/info")
        except urllib.error.HTTPError as e:
            detail = _prusalink_error_detail(e)
            if e.code in (401, 403):
                raise AuthError(
                    f"{self.name} rejected the API key (HTTP {e.code}){detail}",
                    user_message=f"The printer '{self.name}' rejected the API key — "
                    "check that it's correct.",
                ) from e
            raise ConnectorError(
                f"{self.name} capabilities query failed (HTTP {e.code}){detail}"
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        nozzle = info.get("nozzle_diameter")
        # PrusaLink's /api/v1/info does not report a build volume; leave it unknown so
        # capability reconciliation keeps the configured value authoritative.
        return PrinterCapabilities(
            name=str(info.get("name") or info.get("hostname") or self.name),
            build_volume_mm=None,
            nozzle_diameter_mm=float(nozzle) if nozzle is not None else None,
        )

    def _printer_block(self) -> dict[str, Any]:
        return (self._get_json("/api/v1/status") or {}).get("printer") or {}

    def status(self) -> PrinterStatus:
        try:
            printer = self._printer_block()
        except urllib.error.HTTPError as e:
            label = "authentication failed" if e.code in (401, 403) else "request rejected"
            # A 5xx means the server itself is faulted, not "reachable but rejected" — keep
            # `online` honest by reporting it as not-online.
            return PrinterStatus(
                online=e.code < 500, state=PrinterState.error, detail=f"{label} (HTTP {e.code})"
            )
        except (urllib.error.URLError, OSError) as e:
            return PrinterStatus(online=False, state=PrinterState.offline, detail=str(e))
        except ConnectorError:
            return PrinterStatus(
                online=True, state=PrinterState.error, detail="unexpected response from printer"
            )
        raw = str(printer.get("state") or "").lower()
        # Unknown beats wrong: an UNRECOGNIZED non-empty state (e.g. a future firmware state)
        # reports as `error` (needs attention), never silently as "ready". An empty/missing
        # state is treated as idle/operational.
        state = _PRINT_STATE.get(raw, PrinterState.error if raw else PrinterState.operational)
        return PrinterStatus(
            online=True,
            state=state,
            detail=str(printer.get("state") or ""),
            nozzle_temp_c=printer.get("temp_nozzle"),
            bed_temp_c=printer.get("temp_bed"),
        )

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        gcode = extract_single_plate_gcode(gcode_path)
        base = job_name or gcode_path.name.removesuffix(".gcode.3mf")
        upload_name = base + ".gcode"
        # Percent-encode each path segment so a job name with a space / # / ? / % produces a
        # well-formed request target that round-trips through the server's unquote (ENG-002).
        path = (
            f"/api/v1/files/{urllib.parse.quote(self._storage, safe='')}"
            f"/{urllib.parse.quote(upload_name, safe='')}"
        )
        try:
            status, _raw = self._request(
                "PUT",
                path,
                data=gcode,
                content_type="application/octet-stream",
                # RFC 8941 booleans (?1 = true). Print-After-Upload starts the print in the
                # same call; Overwrite lets a re-send of the same job name replace the prior
                # upload rather than 409-conflict on the existing file.
                extra_headers={"Print-After-Upload": "?1", "Overwrite": "?1"},
            )
        except urllib.error.HTTPError as e:
            detail = _prusalink_error_detail(e)
            if e.code in (401, 403):
                raise AuthError(
                    f"{self.name} rejected the API key (HTTP {e.code}){detail}",
                    user_message=f"The printer '{self.name}' rejected the API key — "
                    "check that it's correct.",
                ) from e
            if e.code == 409:
                # PrusaLink returns 409 Conflict when it's busy / can't accept the job now.
                # A typed `busy` reason lets a UI offer a "retry when idle" affordance (QA-005).
                raise ConnectorError(
                    f"{self.name} is busy and refused the upload (HTTP 409){detail}",
                    reason="busy",
                    user_message=f"The printer '{self.name}' is busy. Try again when it's idle.",
                ) from e
            raise ConnectorError(
                f"{self.name} rejected the upload (HTTP {e.code}){detail}",
                user_message=f"The printer '{self.name}' refused the job — it may be busy or "
                "the file type unsupported. Try again when it's idle.",
            ) from e
        except (urllib.error.URLError, OSError) as e:
            # A bad API key on a large upload can surface as a mid-write connection reset (the
            # server 401s and closes before draining the body) rather than the HTTPError above;
            # re-probe the credential so it's reported as auth, not "offline" (ENG-001).
            auth_err = auth_error_if_upload_rejected(
                e,
                request=self._request,
                api_key=self._key,
                name=self.name,
                probe_path="/api/v1/info",
            )
            if auth_err is not None:
                raise auth_err from e
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        if status not in (200, 201, 204):
            body_txt = _raw[:_ERR_BODY_CAP].decode("utf-8", "replace") if _raw else ""
            suffix = f" — {' '.join(body_txt.split())}" if body_txt else ""
            raise ConnectorError(f"{self.name} upload returned HTTP {status}{suffix}")
        return PrintJob(job_id=upload_name, state=JobState.printing, progress=0.0, detail="started")

    def job_status(self, job_id: str) -> PrintJob:
        try:
            data = self._get_json("/api/v1/status")
        except urllib.error.HTTPError as e:
            return PrintJob(job_id=job_id, state=JobState.error, detail=f"HTTP {e.code}")
        except (urllib.error.URLError, OSError) as e:
            return PrintJob(job_id=job_id, state=JobState.error, detail=f"unreachable: {e}")
        except ConnectorError:
            return PrintJob(job_id=job_id, state=JobState.error, detail="unexpected response")
        printer = data.get("printer") or {}
        prusa_state = str(printer.get("state") or "").lower()
        job = data.get("job") or {}
        progress = job.get("progress")
        # PrusaLink reports job.progress as a percentage 0-100.
        progress = max(0.0, min(1.0, float(progress) / 100.0)) if progress is not None else 0.0
        if prusa_state == "finished":
            return PrintJob(job_id=job_id, state=JobState.done, progress=1.0)
        if prusa_state == "stopped":
            return PrintJob(job_id=job_id, state=JobState.cancelled, progress=round(progress, 4))
        if prusa_state in ("error", "attention"):
            return PrintJob(job_id=job_id, state=JobState.error, progress=round(progress, 4))
        if prusa_state == "paused":
            return PrintJob(job_id=job_id, state=JobState.paused, progress=round(progress, 4))
        if prusa_state in ("printing", "busy"):
            return PrintJob(job_id=job_id, state=JobState.printing, progress=round(progress, 4))
        return PrintJob(job_id=job_id, state=JobState.queued, progress=round(progress, 4))
