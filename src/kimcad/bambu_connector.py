"""Bambu Lab native send-to-printer connector (ROADMAP Stage 10 — the gap left from Stage 3).

Drives a Bambu printer (P2S / A1 family) in LAN mode over the printer's own protocols —
MQTT-over-TLS:8883 for state/control and FTPS for the file upload — via the **optional**
``bambulabs-api`` package (MIT). The package has the same graceful-absence posture as
CadQuery/PrintProof3D: when it isn't installed, :func:`kimcad.connectors.build_connector`
reports the connection unconfigured with the exact ``pip install`` to fix it — never a crash.

LAN-mode prerequisites (the UI copy and config template explain them): the printer's
**access code** (Settings → WLAN on the printer; supplied via an env var, never stored in
config) and its **serial number**, with the printer and this machine on the same network.
KimCad's sliced output is a ``*.gcode.3mf`` — Bambu's own project format — so the file is
uploaded AS-IS (no G-code extraction) and started by filename + plate.

The job starts ONLY through the shared :func:`~kimcad.printer_connector.ensure_sendable`
gate (explicit ``confirm=True`` + a proven motion-bearing slice), like every connector.

Tested wholly against an injected fake transport (``printer_factory``); no real hardware is
driven until Kim's beta (Stage 11) — the same posture the other connectors shipped with.
"""

from __future__ import annotations

import io
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from kimcad.printer_connector import (
    ConnectorError,
    JobState,
    PrinterCapabilities,
    PrinterOffline,
    PrinterState,
    PrinterStatus,
    PrintJob,
    ensure_sendable,
)

# How the library's GcodeState names map onto KimCad's normalized PrinterState. UNKNOWN maps
# to error (with a saying-so detail): we only read state AFTER the MQTT session reports
# ready, so a still-unknown state is genuinely abnormal — and unknown-shown-as-ready is the
# direction that lies to the user (the Elegoo lesson: unknown beats wrong).
_STATE_MAP: dict[str, PrinterState] = {
    "IDLE": PrinterState.operational,
    "FINISH": PrinterState.operational,
    "PREPARE": PrinterState.printing,
    "RUNNING": PrinterState.printing,
    "PAUSE": PrinterState.paused,
    "FAILED": PrinterState.error,
    "UNKNOWN": PrinterState.error,
}

_JOB_MAP: dict[str, JobState] = {
    "IDLE": JobState.queued,  # accepted but not yet rolling
    "PREPARE": JobState.printing,
    "RUNNING": JobState.printing,
    "PAUSE": JobState.paused,
    "FINISH": JobState.done,
    "FAILED": JobState.error,
    "UNKNOWN": JobState.error,
}

BAMBU_INSTALL_HINT = (
    "Bambu connections need the optional bambulabs-api package — in a terminal, run: "
    "pip install bambulabs-api — then try again."
)


def bambulabs_api_available() -> bool:
    """Whether the optional ``bambulabs-api`` package is importable (cheap, cached by
    Python's own module cache after the first call)."""
    try:
        import bambulabs_api  # noqa: F401

        return True
    except ImportError:
        return False


def _default_factory(host: str, access_code: str, serial: str) -> Any:
    import bambulabs_api as bl

    return bl.Printer(host, access_code, serial)


class BambuConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for Bambu LAN mode.

    Each call opens a short MQTT session and closes it again (``mqtt_start`` →
    wait-until-ready → work → ``mqtt_stop``): the webapp builds a fresh connector per
    request, so holding a live MQTT client on the instance would leak threads. The
    camera client is never started. ``printer_factory`` is injectable for tests — every
    behavior is provable against a fake without hardware or the real package.
    """

    drives_hardware = True  # a real send starts a real Bambu printer

    def __init__(
        self,
        host: str,
        access_code: str,
        serial: str,
        *,
        name: str = "bambu",
        use_ams: bool = True,
        timeout_s: float = 15.0,
        printer_factory: Callable[[str, str, str], Any] = _default_factory,
    ):
        self.name = name
        self._host = host
        self._code = access_code
        self._serial = serial
        self._use_ams = use_ams
        self._timeout = timeout_s
        self._factory = printer_factory

    # --- session plumbing -----------------------------------------------------------
    @contextmanager
    def _session(self) -> Iterator[Any]:
        """A bounded MQTT session. Raises :class:`PrinterOffline` if the printer never
        answers within the timeout; always stops the client on the way out."""
        try:
            printer = self._factory(self._host, self._code, self._serial)
        except ConnectorError:
            raise
        except Exception as e:  # the factory touched the network/library and failed
            raise PrinterOffline(
                f"{self.name} client could not be created: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and on your network?",
            ) from e
        try:
            printer.mqtt_start()
            deadline = time.monotonic() + self._timeout
            while not printer.mqtt_client_ready():
                if time.monotonic() >= deadline:
                    raise PrinterOffline(
                        f"{self.name} did not answer over MQTT within {self._timeout:.0f}s",
                        user_message=f"Couldn't reach the printer '{self.name}'. Check it's "
                        "powered on, on your network, in LAN mode, and the access code and "
                        "serial are right.",
                    )
                time.sleep(0.2)
            yield printer
        finally:
            try:
                printer.mqtt_stop()
            except Exception:  # noqa: BLE001 — teardown must never mask the real outcome
                pass

    @staticmethod
    def _state_name(printer: Any) -> str:
        state = printer.get_state()
        return getattr(state, "name", str(state)).upper()

    # --- connector contract -----------------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        with self._session() as p:
            nozzle: float | None
            try:
                raw = p.nozzle_diameter()
                nozzle = float(raw) if raw is not None else None
            except Exception:  # noqa: BLE001 — capability fields are best-effort by contract
                nozzle = None
            # Build volume isn't reported over MQTT — the configured printer profile stays
            # authoritative (None = unknown, never a guess).
            return PrinterCapabilities(name=self.name, nozzle_diameter_mm=nozzle)

    def status(self) -> PrinterStatus:
        try:
            return self._status_inner()
        except PrinterOffline:
            # status() reports rather than raises (the webapp's status route expects a
            # snapshot) — same shape as the other connectors' offline answer.
            return PrinterStatus(online=False, state=PrinterState.offline, detail="could not connect")
        except Exception:  # noqa: BLE001 — ENG-002: a raw library error is a snapshot, never a 500
            return PrinterStatus(
                online=True, state=PrinterState.error, detail="unexpected response from printer"
            )

    def _status_inner(self) -> PrinterStatus:
        with self._session() as p:
            name = self._state_name(p)
            state = _STATE_MAP.get(name, PrinterState.error)
            detail = name.lower() if name in _STATE_MAP else f"unrecognized state {name!r}"
            if name == "UNKNOWN":
                detail = "printer state unknown"

            def _temp(fn: Any) -> float | None:
                try:
                    v = fn()
                    return float(v) if v is not None else None
                except Exception:  # noqa: BLE001 — temps are decoration, never an error
                    return None

            return PrinterStatus(
                online=True,
                state=state,
                detail=detail,
                nozzle_temp_c=_temp(p.get_nozzle_temperature),
                bed_temp_c=_temp(p.get_bed_temperature),
            )

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        # KimCad's sliced 3MF IS Bambu's native project format — upload whole, no extraction.
        # ENG-003 (slice-10.3 audit): starting is by PLATE and we start plate 1 — uphold the
        # single-plate invariant the other connectors enforce (slicer.py), so a future
        # multi-plate file can never silently print the wrong plate.
        with zipfile.ZipFile(gcode_path) as zf:
            plates = [n for n in zf.namelist() if n.startswith("Metadata/plate_") and n.endswith(".gcode")]
        if len(plates) != 1:
            raise ConnectorError(
                f"{self.name}: expected exactly one plate in {gcode_path.name!r}, found {len(plates)}",
                user_message="This print file has more than one plate, which direct send "
                "doesn't support — print it from Bambu Studio instead.",
            )
        payload = gcode_path.read_bytes()
        upload_name = (job_name or gcode_path.name.removesuffix(".gcode.3mf")) + ".gcode.3mf"
        with self._session() as p:
            # Refuse to interrupt a job in progress — busy is a soft, typed outcome.
            state_name = self._state_name(p)
            if state_name in ("RUNNING", "PREPARE", "PAUSE"):
                raise ConnectorError(
                    f"{self.name} is busy (state {state_name})",
                    reason="busy",
                    user_message=f"The printer '{self.name}' is already running a job — "
                    "try again when it's free.",
                )
            try:
                ftp_result = p.upload_file(io.BytesIO(payload), upload_name)
            except Exception as e:
                raise ConnectorError(
                    f"{self.name} upload failed: {e}",
                    user_message=f"The file couldn't be uploaded to '{self.name}'. Check the "
                    "access code and that the printer is in LAN mode, then try again.",
                ) from e
            # ENG-001 (slice-10.3 audit): the library's FTP layer can swallow a mid-transfer
            # failure and return None — and start_print only proves an MQTT publish, so a
            # dropped upload would otherwise be narrated as "sent, printing". FTP's own
            # transfer-complete code ("226 ...") is the proof of a finished upload.
            if not (isinstance(ftp_result, str) and "226" in ftp_result):
                raise ConnectorError(
                    f"{self.name} upload did not complete (FTP said {ftp_result!r})",
                    user_message=f"The file didn't finish uploading to '{self.name}' — check "
                    "the network connection to the printer and try again.",
                )
            try:
                started = p.start_print(upload_name, 1, use_ams=self._use_ams)
            except Exception as e:  # ENG-002: a raw library error must surface typed, not as a 500
                raise ConnectorError(
                    f"{self.name} start_print raised: {e}",
                    user_message=f"The printer '{self.name}' didn't accept the start command — "
                    "check its screen, then try again.",
                ) from e
            if not started:
                raise ConnectorError(
                    f"{self.name} refused to start {upload_name!r}",
                    user_message=f"The printer '{self.name}' accepted the file but refused to "
                    "start the job — check the printer's screen for a prompt or error.",
                )
        return PrintJob(job_id=upload_name, state=JobState.printing, progress=0.0, detail="started")

    def job_status(self, job_id: str) -> PrintJob:
        try:
            with self._session() as p:
                name = self._state_name(p)
                state = _JOB_MAP.get(name, JobState.error)
                progress = 0.0
                try:
                    pct = p.get_percentage()
                    progress = max(0.0, min(1.0, float(pct) / 100.0)) if pct is not None else 0.0
                except (TypeError, ValueError):
                    progress = 0.0
                if state is JobState.done:
                    progress = 1.0
                return PrintJob(job_id=job_id, state=state, progress=round(progress, 4))
        except PrinterOffline as e:
            return PrintJob(job_id=job_id, state=JobState.error, detail=str(e))
        except Exception:  # noqa: BLE001 — ENG-002: report, never crash a status poll
            return PrintJob(job_id=job_id, state=JobState.error, detail="unexpected response")
