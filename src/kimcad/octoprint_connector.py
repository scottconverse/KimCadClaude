"""OctoPrint send-to-printer connector (ROADMAP Stage 2).

The first concrete :class:`~kimcad.printer_connector.PrinterConnector`: it talks to an
OctoPrint instance over its REST API (stdlib HTTP only — no new dependency), authenticating
with an API key. ``send`` extracts the printable G-code embedded in KimCad's ``*.gcode.3mf``
and uploads it to OctoPrint as a ``.gcode`` file, selecting + starting the print — but only
after the shared :func:`~kimcad.printer_connector.ensure_sendable` gate (explicit
confirmation + a proven motion-bearing slice).

Tested against :mod:`kimcad.mock_printer` (a mock OctoPrint server); no real hardware is
driven until Kim's beta (Stage 10).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
import zipfile
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
)
from kimcad.slicer import MAX_GCODE_MEMBER_BYTES


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


def _extract_gcode(gcode_3mf: Path) -> bytes:
    """Read the embedded toolpath out of a ``*.gcode.3mf`` (already proven by the gate).

    Refuses a multi-plate archive (we'd otherwise upload only the first plate while the
    proof validated all of them) and a member larger than the proof's size cap.
    """
    with zipfile.ZipFile(gcode_3mf) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".gcode")]
        if not members:
            raise ConnectorError(f"{gcode_3mf.name} has no embedded .gcode to send")
        if len(members) > 1:
            raise ConnectorError(
                f"{gcode_3mf.name} has {len(members)} plates; single-plate send only for now"
            )
        info = zf.getinfo(members[0])
        if info.file_size > MAX_GCODE_MEMBER_BYTES:
            raise ConnectorError(
                f"{gcode_3mf.name} G-code is too large to send ({info.file_size} bytes)"
            )
        return zf.read(members[0])


class OctoPrintConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for OctoPrint.

    The client object holds no per-request state (only the base URL + API key), so a single
    instance can be shared across the threaded server's request handlers.
    """

    def __init__(
        self, base_url: str, api_key: str, *, name: str = "octoprint", timeout_s: float = 15.0
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
        req.add_header("X-Api-Key", self._key)
        if content_type:
            req.add_header("Content-Type", content_type)
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return resp.status, resp.read()

    def _get_json(self, path: str) -> dict[str, Any]:
        _status, raw = self._request("GET", path)
        return json.loads(raw or b"{}")

    # --- connector contract -------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        try:
            data = self._get_json("/api/printerprofiles")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError(f"{self.name} rejected the API key (HTTP {e.code})") from e
            raise ConnectorError(f"{self.name} capabilities query failed (HTTP {e.code})") from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(f"{self.name} unreachable: {e}") from e
        profiles = data.get("profiles") or {}
        prof = profiles.get("_default") or next(iter(profiles.values()), {})
        vol = prof.get("volume") or {}
        build_volume = None
        if all(k in vol for k in ("width", "depth", "height")):
            build_volume = (float(vol["width"]), float(vol["depth"]), float(vol["height"]))
        nozzle = (prof.get("extruder") or {}).get("nozzleDiameter")
        return PrinterCapabilities(
            name=prof.get("name") or self.name,
            build_volume_mm=build_volume,
            nozzle_diameter_mm=float(nozzle) if nozzle is not None else None,
        )

    def status(self) -> PrinterStatus:
        try:
            data = self._get_json("/api/printer")
        except urllib.error.HTTPError as e:
            # reachable but not usable as configured — distinct from offline
            label = "authentication failed" if e.code in (401, 403) else "request rejected"
            return PrinterStatus(
                online=True, state=PrinterState.error, detail=f"{label} (HTTP {e.code})"
            )
        except (urllib.error.URLError, OSError) as e:
            return PrinterStatus(online=False, state=PrinterState.offline, detail=str(e))
        flags = (data.get("state") or {}).get("flags") or {}
        if flags.get("printing"):
            state = PrinterState.printing
        elif flags.get("paused"):
            state = PrinterState.paused
        elif flags.get("error") or flags.get("closedOrError"):
            state = PrinterState.error
        else:
            state = PrinterState.operational
        temps = data.get("temperature") or {}
        return PrinterStatus(
            online=True,
            state=state,
            detail=str((data.get("state") or {}).get("text") or ""),
            nozzle_temp_c=(temps.get("tool0") or {}).get("actual"),
            bed_temp_c=(temps.get("bed") or {}).get("actual"),
        )

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        gcode = _extract_gcode(gcode_path)
        base = job_name or gcode_path.name.removesuffix(".gcode.3mf")
        upload_name = base + ".gcode"
        body, content_type = _encode_multipart(
            {"select": "true", "print": "true"}, {"file": (upload_name, gcode)}
        )
        try:
            status, _raw = self._request(
                "POST", "/api/files/local", data=body, content_type=content_type
            )
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AuthError(f"{self.name} rejected the API key (HTTP {e.code})") from e
            raise ConnectorError(f"{self.name} rejected the upload (HTTP {e.code})") from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(f"{self.name} unreachable: {e}") from e
        if status not in (200, 201):
            raise ConnectorError(f"{self.name} upload returned HTTP {status}")
        # OctoPrint runs one job at a time; the uploaded filename identifies it.
        return PrintJob(job_id=upload_name, state=JobState.printing, progress=0.0, detail="started")

    def job_status(self, job_id: str) -> PrintJob:
        try:
            data = self._get_json("/api/job")
        except (urllib.error.URLError, OSError) as e:
            return PrintJob(job_id=job_id, state=JobState.error, detail=f"unreachable: {e}")
        completion = (data.get("progress") or {}).get("completion")
        if completion is None:
            return PrintJob(job_id=job_id, state=JobState.queued, progress=0.0)
        progress = max(0.0, min(1.0, float(completion) / 100.0))
        state = JobState.done if progress >= 1.0 else JobState.printing
        return PrintJob(job_id=job_id, state=state, progress=round(progress, 4))
