"""RepRapFirmware / Duet send-to-printer connector (KC-21, #26).

A concrete :class:`~kimcad.printer_connector.PrinterConnector` for Duet boards (Duet 2/3) and
other RepRapFirmware controllers, over RRF's classic HTTP interface (stdlib HTTP only — no new
dependency):

- ``GET  /rr_connect?password=…`` — optional session auth (RRF runs open on many LANs);
- ``GET  /rr_status?type=N``      — status (1 basic, 2 adds axis limits, 3 adds print progress);
- ``POST /rr_upload?name=/gcodes/…`` — upload the G-code (raw body, NOT multipart);
- ``GET  /rr_gcode?gcode=M32 "0:/gcodes/…"`` — select + start the SD print;
- ``GET  /rr_disconnect`` — release the session (RRF's session table is small and bounded).

``send`` extracts the printable G-code from KimCad's ``*.gcode.3mf``, uploads it (rejecting a
non-``err 0`` reply), then issues ``M32`` and CONFIRMS the start was accepted before returning a
printing job — all only after the shared :func:`~kimcad.printer_connector.ensure_sendable` gate.
A password-protected board that rejects the password surfaces as
:class:`~kimcad.printer_connector.AuthError`, distinct from offline. When a password is configured
the connector opens a session per operation and ALWAYS ``/rr_disconnect``s it in a finally, so
repeated status polling can't exhaust the board's session slots and spuriously report "busy".

The job name is reduced to a safe filename before it reaches the ``M32 "0:…"`` command, so a quote
or newline can't unbalance the command or inject a second ``rr_gcode`` (security).

Tested against :mod:`kimcad.mock_duet` (a mock RRF HTTP server); no real hardware until metal
validation (#11). The status/temperature JSON shape this connector reads is the subset the mock
emits; real-board field variance across RRF versions is a metal concern.

LIMITATION (job completion): over the classic ``/rr_status`` a finished print returns to idle and
RRF resets ``fractionPrinted`` to 0 — there is no per-file done query. ``job_status`` therefore
LATCHES done: once it has seen progress for a ``job_id`` and then sees idle, it reports ``done``.
It reflects the printer's CURRENT SD job (no per-file identity over this surface), so a different
job started elsewhere may be misattributed; callers should treat the first terminal state as final.
"""

from __future__ import annotations

import json
import threading
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
    ensure_sendable,
    extract_single_plate_gcode,
    read_error_body,
)

_ERR_BODY_CAP = 300

# RRF status character -> our normalized PrinterState. Unrecognized (non-empty) beats wrong.
_RRF_STATE = {
    "I": PrinterState.operational, "O": PrinterState.operational, "B": PrinterState.operational,
    "C": PrinterState.operational, "T": PrinterState.operational,
    "P": PrinterState.printing, "R": PrinterState.printing, "M": PrinterState.printing,
    "D": PrinterState.printing,
    "S": PrinterState.paused, "A": PrinterState.paused,
    "H": PrinterState.error, "F": PrinterState.error,
}


class DuetConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for RepRapFirmware / Duet."""

    drives_hardware = True  # a real send reaches a real printer

    def __init__(
        self,
        base_url: str,
        password: str | None = None,
        *,
        name: str = "duet",
        timeout_s: float = 15.0,
    ):
        self.name = name
        self._base = base_url.rstrip("/")
        self._password = password or None
        self._timeout = timeout_s
        self._lock = threading.Lock()
        self._progressed: set[str] = set()  # job_ids that have shown print progress (done latch)

    # --- HTTP plumbing ------------------------------------------------------
    def _request(self, method: str, path: str, *, data: bytes | None = None) -> tuple[int, bytes]:
        req = urllib.request.Request(self._base + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/octet-stream")
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return resp.status, resp.read()

    def _get_json(self, path: str) -> dict[str, Any]:
        _status, raw = self._request("GET", path)
        try:
            parsed = json.loads(raw.decode("utf-8", "replace") or "{}")
        except ValueError as e:
            raise ConnectorError(
                f"{self.name} returned a non-JSON RRF response",
                reason="bad_response",
                user_message=f"The printer '{self.name}' returned an unexpected response — it may "
                "not be a RepRapFirmware/Duet endpoint.",
            ) from e
        if not isinstance(parsed, dict):
            raise ConnectorError(
                f"{self.name} returned a non-object RRF response",
                reason="bad_response",
                user_message=f"The printer '{self.name}' returned an unexpected response — it may "
                "not be a RepRapFirmware/Duet endpoint.",
            )
        return parsed

    def _connect(self) -> None:
        """Open an RRF session when a password is configured. ``err`` 1 = wrong password,
        2 = no free sessions; 0 = ok. A board with no password ignores the call."""
        if not self._password:
            return
        data = self._get_json("/rr_connect?password=" + urllib.parse.quote(self._password))
        err = data.get("err")
        if err == 1:
            raise AuthError(
                f"{self.name} rejected the password (rr_connect err 1)",
                user_message=f"The printer '{self.name}' rejected the password — check that it's "
                "correct.",
            )
        if err == 2:
            raise ConnectorError(
                f"{self.name} has no free sessions (rr_connect err 2)",
                reason="busy",
                user_message=f"The printer '{self.name}' has no free connection slots right now. "
                "Close another session and try again.",
            )

    def _disconnect(self) -> None:
        """Release the RRF session (only meaningful when a password opened one). Best-effort — a
        failed disconnect must never mask the operation's real result."""
        if not self._password:
            return
        try:
            self._request("GET", "/rr_disconnect")
        except (urllib.error.URLError, OSError):
            pass

    def _status_json(self, status_type: int) -> dict[str, Any]:
        return self._get_json(f"/rr_status?type={status_type}")

    @staticmethod
    def _rrf_error_detail(e: urllib.error.HTTPError) -> str:
        text = " ".join(read_error_body(e, cap=_ERR_BODY_CAP).split())
        return f" — {text[:_ERR_BODY_CAP]}" if text else ""

    @staticmethod
    def _auth_from_http(name: str, e: urllib.error.HTTPError) -> AuthError | None:
        if e.code in (401, 403):
            return AuthError(
                f"{name} rejected the request (HTTP {e.code})",
                user_message=f"The printer '{name}' rejected the connection — it may need a password.",
            )
        return None

    # --- connector contract -------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        try:
            self._connect()
            status = self._status_json(2)
        except (AuthError, ConnectorError):
            self._disconnect()
            raise
        except urllib.error.HTTPError as e:
            self._disconnect()
            auth = self._auth_from_http(self.name, e)
            if auth is not None:
                raise auth from e
            raise ConnectorError(
                f"{self.name} status query failed (HTTP {e.code}){self._rrf_error_detail(e)}"
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        self._disconnect()
        mins, maxes = status.get("axisMins"), status.get("axisMaxes")
        build_volume = None
        if (isinstance(mins, (list, tuple)) and isinstance(maxes, (list, tuple))
                and len(maxes) >= 3 and len(mins) >= 3):
            build_volume = tuple(float(maxes[i]) - float(mins[i]) for i in range(3))
        return PrinterCapabilities(
            name=self.name, build_volume_mm=build_volume, nozzle_diameter_mm=None
        )

    @staticmethod
    def _temps(status: dict[str, Any]) -> tuple[float | None, float | None]:
        """(nozzle_temp, bed_temp) from the RRF temps block, tolerating the shape variance across
        RRF versions: ``temps.bed`` may be a dict, a number, or a list; ``temps.current`` is
        ``[bed, tool0, …]``."""
        temps = status.get("temps") or {}
        bed: Any = None
        bed_obj = temps.get("bed")
        if isinstance(bed_obj, dict):
            bed = bed_obj.get("current")
        elif isinstance(bed_obj, (int, float)):
            bed = bed_obj
        elif isinstance(bed_obj, (list, tuple)) and bed_obj:
            first = bed_obj[0]
            bed = first.get("current") if isinstance(first, dict) else first
        current = temps.get("current")
        nozzle: Any = None
        if isinstance(current, (list, tuple)) and current:
            if len(current) >= 2:
                nozzle = current[1]  # first tool
            if bed is None:
                bed = current[0]
        return (
            float(nozzle) if isinstance(nozzle, (int, float)) else None,
            float(bed) if isinstance(bed, (int, float)) else None,
        )

    def status(self) -> PrinterStatus:
        # ENG-003: _disconnect() runs on EVERY exit path (try/finally), so a transient mid-poll
        # URLError/OSError after a successful _connect() can't leak an RRF session. urllib.error.URLError
        # is caught before its OSError sibling-overlap is irrelevant; HTTPError (a URLError subclass) and
        # AuthError/ConnectorError are matched first so the offline arm only sees true transport failures.
        try:
            try:
                self._connect()
                status = self._status_json(3)
            except AuthError:
                return PrinterStatus(online=True, state=PrinterState.error, detail="authentication failed")
            except urllib.error.HTTPError as e:
                return PrinterStatus(
                    online=e.code < 500, state=PrinterState.error,
                    detail=f"request rejected (HTTP {e.code})",
                )
            except (urllib.error.URLError, OSError):
                return PrinterStatus(online=False, state=PrinterState.offline, detail="could not connect")
            except ConnectorError:
                return PrinterStatus(
                    online=True, state=PrinterState.error, detail="unexpected response from printer"
                )
        finally:
            self._disconnect()
        raw = str(status.get("status") or "")
        state = _RRF_STATE.get(raw, PrinterState.error if raw else PrinterState.operational)
        nozzle, bed = self._temps(status)
        return PrinterStatus(online=True, state=state, detail=raw, nozzle_temp_c=nozzle, bed_temp_c=bed)

    @staticmethod
    def _safe_upload_name(base: str) -> str:
        """A filename safe to embed in the ``M32 "0:…"`` G-code and the rr_gcode/rr_upload query:
        keep only alphanumerics + ``-_``, so a quote, newline, or slash in a user-supplied job
        name can't break the M32 quoting or inject a second rr_gcode command (security)."""
        cleaned = "".join(ch for ch in base if ch.isalnum() or ch in "-_")[:60].strip("-_")
        return (cleaned or "kimcad") + ".gcode"

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        gcode = extract_single_plate_gcode(gcode_path)
        base = job_name or gcode_path.name.removesuffix(".gcode.3mf")
        upload_name = self._safe_upload_name(base)
        remote_path = "/gcodes/" + upload_name
        try:
            self._connect()
            up = self._post_upload(remote_path, gcode)
            # Require an explicit err == 0; a missing/garbage reply is a FAILED upload, not silent
            # success (ENG-007) — never start a print on a file that may not have landed.
            if up.get("err") != 0:
                raise ConnectorError(
                    f"{self.name} rejected the upload (rr_upload err {up.get('err')!r})",
                    user_message=f"The printer '{self.name}' refused the file — it may be busy or "
                    "out of SD space. Try again when it's idle.",
                )
            gcode_cmd = f'M32 "0:{remote_path}"'
            started = self._get_json("/rr_gcode?gcode=" + urllib.parse.quote(gcode_cmd))
            # rr_gcode replies {"err": N} or {"buff": N}; a non-zero err means the start was refused
            # (QA-1) — don't report a printing job for a job that never started.
            if started.get("err"):
                raise ConnectorError(
                    f"{self.name} refused the print start (M32 err {started.get('err')!r})",
                    reason="busy",
                    user_message=f"The printer '{self.name}' wouldn't start the print — it may be "
                    "busy. Try again when it's idle.",
                )
        except (AuthError, ConnectorError):
            self._disconnect()
            raise
        except urllib.error.HTTPError as e:
            self._disconnect()
            auth = self._auth_from_http(self.name, e)
            if auth is not None:
                raise auth from e
            raise ConnectorError(
                f"{self.name} rejected the job (HTTP {e.code}){self._rrf_error_detail(e)}",
                user_message=f"The printer '{self.name}' refused the job — it may be busy. "
                "Try again when it's idle.",
            ) from e
        except (urllib.error.URLError, OSError) as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        self._disconnect()
        return PrintJob(job_id=upload_name, state=JobState.printing, progress=0.0, detail="started")

    def _post_upload(self, remote_path: str, gcode: bytes) -> dict[str, Any]:
        _status, raw = self._request(
            "POST", "/rr_upload?name=" + urllib.parse.quote(remote_path), data=gcode
        )
        try:
            parsed = json.loads(raw.decode("utf-8", "replace") or "{}")
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def job_status(self, job_id: str) -> PrintJob:
        # ENG-003: _disconnect() in a finally so the URLError/OSError arm can't leak an RRF
        # session after a successful _connect() (a transient mid-poll blip).
        # ENG-009: the offline detail is a clean fixed string, not raw urllib/WinError text.
        try:
            try:
                self._connect()
                status = self._status_json(3)
            except AuthError:
                return PrintJob(job_id=job_id, state=JobState.error, detail="authentication failed")
            except urllib.error.HTTPError as e:
                return PrintJob(job_id=job_id, state=JobState.error, detail=f"HTTP {e.code}")
            except (urllib.error.URLError, OSError):
                return PrintJob(job_id=job_id, state=JobState.error, detail="could not reach the printer")
            except ConnectorError:
                return PrintJob(job_id=job_id, state=JobState.error, detail="unexpected response")
        finally:
            self._disconnect()
        raw = str(status.get("status") or "")
        frac = status.get("fractionPrinted")
        progress = max(0.0, min(1.0, float(frac) / 100.0)) if frac is not None else 0.0
        if raw in ("P", "R", "M", "D"):
            if progress > 0:
                with self._lock:
                    self._progressed.add(job_id)
            return PrintJob(job_id=job_id, state=JobState.printing, progress=round(progress, 4))
        if raw in ("S", "A"):
            return PrintJob(job_id=job_id, state=JobState.paused, progress=round(progress, 4))
        if raw in ("H", "F"):
            return PrintJob(job_id=job_id, state=JobState.error, progress=round(progress, 4))
        # Idle: a print that ran and returned to idle is DONE (latched); RRF clears fractionPrinted
        # on completion, so this latch — not the (reset) progress — is what detects done.
        with self._lock:
            done = job_id in self._progressed
        if done:
            return PrintJob(job_id=job_id, state=JobState.done, progress=1.0)
        return PrintJob(job_id=job_id, state=JobState.queued, progress=round(progress, 4))
