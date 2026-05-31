"""Moonraker (Klipper) send-to-printer connector (ROADMAP Stage 3).

A second concrete :class:`~kimcad.printer_connector.PrinterConnector`, talking to a Klipper
printer through its Moonraker REST API (stdlib HTTP only — no new dependency). Moonraker is
the control surface for a large swath of printers: Creality with Klipper, Voron, RatRig, and
anything running Klipper/Mainsail/Fluidd.

``send`` extracts the printable G-code from KimCad's ``*.gcode.3mf`` and uploads it to
Moonraker's ``gcodes`` root with ``print=true`` (upload-and-start), but only after the shared
:func:`~kimcad.printer_connector.ensure_sendable` gate (explicit confirmation + a proven,
motion-bearing slice).

Auth: Moonraker often runs unauthenticated on a trusted LAN; an optional API key is sent as
``X-Api-Key`` when configured. A reachable-but-rejected printer (401/403) surfaces as
:class:`~kimcad.printer_connector.AuthError`, distinct from offline.

Tested against :mod:`kimcad.mock_moonraker` (a mock Moonraker server); no real hardware is
driven until Kim's beta (Stage 10).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
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
    ensure_sendable,
    extract_single_plate_gcode,
    read_error_body,
)

_ERR_BODY_CAP = 300

# Klipper print_stats.state -> our normalized PrinterState
_PRINT_STATE = {
    "standby": PrinterState.operational,
    "printing": PrinterState.printing,
    "paused": PrinterState.paused,
    "complete": PrinterState.operational,
    "cancelled": PrinterState.operational,
    "error": PrinterState.error,
}


def _moonraker_error_detail(e: urllib.error.HTTPError) -> str:
    """Bounded extraction of Moonraker's error reason. Moonraker returns
    ``{"error": {"code": .., "message": ".."}}``; fall back to the raw bounded text."""
    text = read_error_body(e, cap=_ERR_BODY_CAP)
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict) and err.get("message"):
                text = str(err["message"])
            elif isinstance(err, str) and err:
                text = err
    except ValueError:
        pass
    text = " ".join(text.split())  # collapse internal whitespace in the extracted reason too
    return f" — {text[:_ERR_BODY_CAP]}" if text else ""


def _encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes]]
) -> tuple[bytes, str]:
    """Encode form fields + files as ``multipart/form-data``. Returns ``(body, content_type)``."""
    boundary = "----KimCad" + uuid.uuid4().hex
    out: list[bytes] = []
    for name, value in fields.items():
        out += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"'.encode(),
            b"",
            str(value).encode(),
        ]
    for name, (filename, content) in files.items():
        out += [
            f"--{boundary}".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode(),
            b"Content-Type: application/octet-stream",
            b"",
            content,
        ]
    out += [f"--{boundary}--".encode(), b""]
    return b"\r\n".join(out), f"multipart/form-data; boundary={boundary}"


class MoonrakerConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for Klipper via Moonraker.

    Holds no per-request state (only the base URL + optional API key), so one instance is safe
    to share across the threaded web server's request handlers.
    """

    drives_hardware = True  # a real send reaches a real printer

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        *,
        name: str = "moonraker",
        timeout_s: float = 15.0,
    ):
        self.name = name
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout_s

    # --- HTTP plumbing ------------------------------------------------------
    def _request(
        self, method: str, path: str, *, data: bytes | None = None, content_type: str | None = None
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(self._base + path, data=data, method=method)
        if self._key:
            req.add_header("X-Api-Key", self._key)
        if content_type:
            req.add_header("Content-Type", content_type)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return resp.status, resp.read()

    def _query(self, *objects: str) -> dict[str, Any]:
        """`GET /printer/objects/query?obj1&obj2` -> the ``result.status`` dict."""
        qs = "&".join(urllib.parse.quote(o) for o in objects)
        _status, raw = self._request("GET", f"/printer/objects/query?{qs}")
        data = json.loads(raw or b"{}")
        return (data.get("result") or {}).get("status") or {}

    # --- connector contract -------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        try:
            status = self._query("toolhead", "configfile")
        except urllib.error.HTTPError as e:
            detail = _moonraker_error_detail(e)
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
        toolhead = status.get("toolhead") or {}
        axis_max = toolhead.get("axis_maximum")  # [x, y, z, e]
        axis_min = toolhead.get("axis_minimum") or [0.0, 0.0, 0.0, 0.0]
        build_volume = None
        if isinstance(axis_max, (list, tuple)) and len(axis_max) >= 3:
            # build volume = travel span per axis (max - min), so a non-zero origin is honored
            build_volume = tuple(
                float(axis_max[i]) - float(axis_min[i] if len(axis_min) > i else 0.0)
                for i in range(3)
            )
        settings = (status.get("configfile") or {}).get("settings") or {}
        nozzle = (settings.get("extruder") or {}).get("nozzle_diameter")
        return PrinterCapabilities(
            name=self.name,
            build_volume_mm=build_volume,
            nozzle_diameter_mm=float(nozzle) if nozzle is not None else None,
        )

    def status(self) -> PrinterStatus:
        try:
            status = self._query("print_stats", "extruder", "heater_bed")
        except urllib.error.HTTPError as e:
            label = "authentication failed" if e.code in (401, 403) else "request rejected"
            return PrinterStatus(
                online=True, state=PrinterState.error, detail=f"{label} (HTTP {e.code})"
            )
        except (urllib.error.URLError, OSError) as e:
            return PrinterStatus(online=False, state=PrinterState.offline, detail=str(e))
        print_stats = status.get("print_stats") or {}
        state = _PRINT_STATE.get(str(print_stats.get("state") or "").lower(), PrinterState.operational)
        return PrinterStatus(
            online=True,
            state=state,
            detail=str(print_stats.get("state") or ""),
            nozzle_temp_c=(status.get("extruder") or {}).get("temperature"),
            bed_temp_c=(status.get("heater_bed") or {}).get("temperature"),
        )

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        gcode = extract_single_plate_gcode(gcode_path)
        base = job_name or gcode_path.name.removesuffix(".gcode.3mf")
        upload_name = base + ".gcode"
        body, content_type = _encode_multipart(
            {"root": "gcodes", "print": "true"}, {"file": (upload_name, gcode)}
        )
        try:
            status, _raw = self._request(
                "POST", "/server/files/upload", data=body, content_type=content_type
            )
        except urllib.error.HTTPError as e:
            detail = _moonraker_error_detail(e)
            if e.code in (401, 403):
                raise AuthError(
                    f"{self.name} rejected the API key (HTTP {e.code}){detail}",
                    user_message=f"The printer '{self.name}' rejected the API key — "
                    "check that it's correct.",
                ) from e
            # The bounded server reason stays in the developer message; the user-facing one
            # avoids echoing a raw upstream string.
            raise ConnectorError(
                f"{self.name} rejected the upload (HTTP {e.code}){detail}",
                user_message=f"The printer '{self.name}' refused the job — it may be busy or "
                "the file type unsupported. Try again when it's idle.",
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        if status not in (200, 201):
            # Defensive: urllib raises HTTPError for >=400, so this only fires on an odd 2xx
            # that isn't 200/201 — a belt-and-suspenders guard, not a normal path.
            body_txt = _raw[:_ERR_BODY_CAP].decode("utf-8", "replace") if _raw else ""
            suffix = f" — {' '.join(body_txt.split())}" if body_txt else ""
            raise ConnectorError(f"{self.name} upload returned HTTP {status}{suffix}")
        return PrintJob(job_id=upload_name, state=JobState.printing, progress=0.0, detail="started")

    def job_status(self, job_id: str) -> PrintJob:
        try:
            status = self._query("print_stats", "virtual_sdcard")
        except urllib.error.HTTPError as e:
            # HTTPError is a subclass of URLError, so it MUST be caught first — a 401/403 is a
            # reachable-but-rejected printer, not "unreachable" (FIND-001).
            return PrintJob(job_id=job_id, state=JobState.error, detail=f"HTTP {e.code}")
        except (urllib.error.URLError, OSError) as e:
            return PrintJob(job_id=job_id, state=JobState.error, detail=f"unreachable: {e}")
        print_stats = status.get("print_stats") or {}
        klip_state = str(print_stats.get("state") or "").lower()
        progress = (status.get("virtual_sdcard") or {}).get("progress")
        progress = max(0.0, min(1.0, float(progress))) if progress is not None else 0.0
        if klip_state == "complete":
            return PrintJob(job_id=job_id, state=JobState.done, progress=1.0)
        if klip_state == "error":
            return PrintJob(job_id=job_id, state=JobState.error, progress=round(progress, 4))
        if klip_state == "cancelled":
            return PrintJob(job_id=job_id, state=JobState.cancelled, progress=round(progress, 4))
        if klip_state == "paused":
            return PrintJob(job_id=job_id, state=JobState.paused, progress=round(progress, 4))
        if klip_state == "printing":
            return PrintJob(job_id=job_id, state=JobState.printing, progress=round(progress, 4))
        return PrintJob(job_id=job_id, state=JobState.queued, progress=round(progress, 4))
