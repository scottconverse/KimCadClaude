"""Send-to-printer connector abstraction (spec §6.10 / ROADMAP Stage 2).

KimCad never drives a printer directly from the pipeline. Instead a part that has been
sliced to a G-code-bearing 3MF is handed to a **connector** — a thin, swappable adapter
to one printer's control surface (OctoPrint, Moonraker/Klipper, …). This module is the
abstraction every connector implements, plus an in-memory ``LoopbackConnector`` that
exercises the contract with no network and no hardware. (The MCP server in
:mod:`kimcad.mcp_server` is a *consumer* of this abstraction, not a connector itself.)

Two safety properties live here, not in the leaf connectors:

- **Explicit per-send confirmation.** :meth:`PrinterConnector.send` refuses to start a job
  unless the caller passes ``confirm=True``; a missing/false (or merely truthy) confirmation
  raises :class:`NotConfirmed`. The connector cannot be tricked into printing without an
  explicit human-confirmed signal, exactly as G-code generation is gated in Stage 1.
- **The job must be a real, proven slice.** ``send`` validates that the file exists and is a
  G-code-bearing 3MF (via :func:`kimcad.slicer.prove_gcode_3mf`) before it leaves the machine,
  so a connector never uploads an empty or non-printable file.

Real printing waits for Kim's beta (Stage 10). Everything here is tested against mocks /
emulators on the dev box; no connector talks to physical hardware yet.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from kimcad.slicer import MAX_GCODE_MEMBER_BYTES, GcodeProofFailed, prove_gcode_3mf


class ConnectorError(Exception):
    """Base class for send-to-printer failures.

    Carries a machine-readable ``reason`` (so a caller can branch on *why* a send failed
    instead of string-matching the message) and a ``user_message`` (plain, non-developer
    phrasing that is safe to show an end user). ``str(self)`` stays the developer-facing
    detail, which may name an env var, a URL, etc.

    Reason vocabulary (ENG-003 — the single source of truth; keep the web UI's
    ``connectorStatusText`` and any MCP/agent consumers exhaustive against this set, and the
    README "Connector response reasons" table in sync):

    - ``"config"``       — misconfigured connection (missing API key / base_url).
    - ``"unknown"``      — no configured connection by that name (a typo, not a setup task).
    - ``"auth"``         — reachable but the printer rejected the credentials (bad API key).
    - ``"offline"``      — the printer could not be reached.
    - ``"busy"``         — the printer refused the job because it's busy (retry when idle).
    - ``"bad_response"`` — the endpoint answered but not with the expected JSON (wrong device).
    - ``"error"``        — generic / uncategorized failure (the base default).

    ``"not_confirmed"`` (``ensure_sendable`` raises it when a send lacks an explicit
    ``confirm=True``) is an INTERNAL guard — caught before any network call, never returned to a
    client, so the README "Connector response reasons" table omits it (DOC-001). The response
    reasons above appear on ``/api/connector-status`` (``config``/``unknown`` from build;
    ``offline``/``busy``/``error`` from a live status) and on ``/api/send`` soft-failures.
    """

    reason = "error"

    def __init__(
        self, message: str, *, reason: str | None = None, user_message: str | None = None
    ):
        super().__init__(message)
        if reason is not None:
            self.reason = reason
        self.user_message = user_message or message


class NotConfirmed(ConnectorError):
    """A send was attempted without the explicit per-send confirmation."""

    reason = "not_confirmed"


class PrinterOffline(ConnectorError):
    """The printer could not be reached or is not ready to accept a job."""

    reason = "offline"


class AuthError(ConnectorError):
    """The printer was reachable but rejected our credentials (e.g. a bad API key) —
    distinct from :class:`PrinterOffline` (unreachable)."""

    reason = "auth"


class JobState(str, Enum):
    """Lifecycle of a print job, normalized across connectors."""

    queued = "queued"
    uploading = "uploading"
    printing = "printing"
    paused = "paused"
    done = "done"
    error = "error"
    cancelled = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in (JobState.done, JobState.error, JobState.cancelled)


class PrinterState(str, Enum):
    """Printer readiness, normalized across connectors (each connector maps its own
    vendor states onto these)."""

    operational = "operational"
    printing = "printing"
    paused = "paused"
    offline = "offline"
    error = "error"


@dataclass(frozen=True)
class PrinterCapabilities:
    """What a printer reports about itself — used to auto-fill blank profile fields and
    to label honestly what a connector can do. Any field may be ``None`` if unknown.

    ``materials`` is ``None`` when the printer does not report its loaded materials (the
    OctoPrint profile endpoint, for one, doesn't) — distinct from an empty tuple, which
    would mean "reports it supports no materials." Don't treat unknown as none.
    """

    name: str
    build_volume_mm: tuple[float, float, float] | None = None
    nozzle_diameter_mm: float | None = None
    materials: tuple[str, ...] | None = None


@dataclass(frozen=True)
class PrinterStatus:
    """A point-in-time snapshot of printer readiness."""

    online: bool
    state: PrinterState
    detail: str = ""
    nozzle_temp_c: float | None = None
    bed_temp_c: float | None = None


@dataclass(frozen=True)
class PrintJob:
    """A submitted job and its current progress. ``progress`` is 0.0–1.0."""

    job_id: str
    state: JobState
    progress: float = 0.0
    detail: str = ""


@runtime_checkable
class PrinterConnector(Protocol):
    """The contract every printer connector implements.

    NOTE on ``isinstance(x, PrinterConnector)``: ``@runtime_checkable`` only verifies that
    the named attributes *exist*, not that they're callable with the right signature — so it
    is a smoke check, not a guarantee. Behavioral tests carry the real contract.

    THREAD SAFETY: connectors may be called concurrently (the web UI runs on a
    ``ThreadingHTTPServer``), so implementations must guard their mutable state.

    ``drives_hardware`` tells callers whether a send reaches a *real* printer (True) or is a
    simulation/loopback (False), so a UI/CLI can label honestly instead of narrating a mock
    send as a real print.
    """

    name: str
    drives_hardware: bool

    def capabilities(self) -> PrinterCapabilities: ...

    def status(self) -> PrinterStatus: ...

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        """Upload and start a print job. MUST raise :class:`NotConfirmed` unless
        ``confirm is True``, and MUST refuse a file that isn't a proven G-code 3MF."""
        ...

    def job_status(self, job_id: str) -> PrintJob: ...


def ensure_sendable(gcode_path: Path, *, confirm: bool) -> None:
    """Shared precondition for every connector's ``send``: an explicit confirmation and a
    file that proves out as a real, motion-bearing G-code 3MF. Raises :class:`NotConfirmed`
    or :class:`ConnectorError`. Connectors call this before touching the network.

    ``confirm`` must be exactly ``True`` — a merely truthy value is not an explicit confirm.
    """
    if confirm is not True:
        raise NotConfirmed(
            "refusing to send a print job without explicit confirmation (confirm=True)"
        )
    if not gcode_path.exists():
        raise ConnectorError(f"G-code file not found: {gcode_path}")
    try:
        prove_gcode_3mf(gcode_path)
    except GcodeProofFailed as e:
        raise ConnectorError(f"refusing to send a file that isn't a printable slice: {e}") from e


def extract_single_plate_gcode(gcode_3mf: Path) -> bytes:
    """Read the embedded toolpath out of a proven ``*.gcode.3mf`` for upload to a printer.

    Shared by every connector that uploads a flat ``.gcode`` (OctoPrint, Moonraker, …) so the
    guards live in one place. Refuses a multi-plate archive (we'd otherwise upload only the
    first plate while the proof validated all of them) and a member larger than the proof's
    size cap. Only ever *reads* member bytes — never extracts to a path — so a malicious member
    name (``../../etc/...``) is inert here.
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


def read_error_body(e: Any, *, cap: int = 300) -> str:
    """Best-effort, bounded read of an HTTP error response body as whitespace-collapsed text.

    Shared by connectors so each can parse its own JSON error shape from the bytes without
    duplicating the read. Never raises; never includes request headers (the API key is a
    request header, not in the response body), and the result is capped.
    """
    try:
        raw = e.read(cap + 1) or b""
    except Exception:
        return ""
    return " ".join(raw[:cap].decode("utf-8", "replace").split())


def decode_json(raw: bytes | None, *, name: str) -> dict[str, Any]:
    """Parse a printer's JSON response body, or raise a clean :class:`ConnectorError`.

    A device that answers HTTP 200 with a non-JSON body (a captive portal, a proxy, or the
    wrong device on the configured IP) must not surface as a raw ``JSONDecodeError`` — the
    connector contract is "never raise an undecorated exception, never a traceback." Callers in
    ``status()`` / ``job_status()`` catch this and degrade to an error STATUS;
    ``capabilities()`` / ``send`` let it propagate as the typed ConnectorError it already is.
    A non-object JSON body (a list or scalar) is treated as ``{}`` so downstream ``.get`` is safe.
    """
    try:
        data = json.loads(raw or b"{}")
    except ValueError as e:
        raise ConnectorError(
            f"{name} returned a non-JSON response: {e}",
            reason="bad_response",
            user_message=f"The printer '{name}' returned an unexpected response - it may not "
            "be the kind of printer server KimCad expects at that address.",
        ) from e
    return data if isinstance(data, dict) else {}


def auth_error_if_upload_rejected(
    exc: BaseException,
    *,
    request: Callable[..., tuple[int, bytes]],
    api_key: str | None,
    name: str,
    probe_path: str,
) -> AuthError | None:
    """Disambiguate a failed upload: an unreachable printer, or a rejected API key?

    When a server rejects auth on an upload it typically sends 401 and closes the socket
    *before draining the request body*. If the body is larger than the socket send buffer the
    client's write fails first with a connection reset (a :class:`ConnectionError`, a subclass
    of ``OSError`` — not a :class:`urllib.error.HTTPError`), so an upload's
    ``except (URLError, OSError)`` arm would mislabel a bad key as "printer offline" (ENG-001).
    Only a raw mid-write reset (``ConnectionError``, distinct from a connect-time
    ``urllib.error.URLError``) with an API key configured is suspect; re-probe the credential
    with a cheap authenticated GET. A 401/403 there means auth; anything else (including a
    re-probe that is itself unreachable) falls through to "offline". Returns an
    :class:`AuthError` to raise, or ``None`` to fall through.
    """
    if not (api_key and isinstance(exc, ConnectionError)):
        return None
    try:
        request("GET", probe_path)
    except urllib.error.HTTPError as probe:
        if probe.code in (401, 403):
            return AuthError(
                f"{name} rejected the API key (HTTP {probe.code})",
                user_message=f"The printer '{name}' rejected the API key - check that it's "
                "correct.",
            )
    except (urllib.error.URLError, OSError):
        pass  # genuinely unreachable on the re-probe too -> fall through to offline
    return None


def encode_multipart(
    fields: dict[str, str], files: dict[str, tuple[str, bytes]]
) -> tuple[bytes, str]:
    """Encode form fields + files as ``multipart/form-data``. Returns ``(body, content_type)``.

    Shared by the connectors that upload over multipart (OctoPrint, Moonraker) — PrusaLink uses a
    raw PUT body and needs none (ENG-002: one copy, not three).
    """
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


@dataclass
class _LoopJob:
    """Internal state for one mock job (keeps the state machine type-checked)."""

    name: str
    polls: int = 0
    state: JobState = JobState.queued


class LoopbackConnector:
    """An in-memory mock printer that fully implements :class:`PrinterConnector` with no
    network and no hardware. It accepts a (confirmed, proven) job and deterministically
    advances it queued → printing → done over successive ``job_status`` polls, so the
    abstraction, the confirmation gate, and a status-flow can be tested offline.

    Lifecycle: ``send`` returns a ``queued`` job (progress 0.0); the first ``job_status``
    poll moves it to ``printing`` (progress 0.0) and each subsequent poll advances progress
    until the ``polls_to_done``-th poll, which reports ``done`` (progress 1.0).
    ``polls_to_done`` is clamped to ≥ 2 so there is always at least one ``printing`` frame.
    Thread-safe: all job state is guarded by an internal lock.
    """

    drives_hardware = False  # a simulation — no real printer is touched

    def __init__(
        self,
        name: str = "loopback",
        *,
        capabilities: PrinterCapabilities | None = None,
        online: bool = True,
        polls_to_done: int = 3,
    ):
        self.name = name
        self._caps = capabilities or PrinterCapabilities(
            name=name,
            build_volume_mm=(256.0, 256.0, 256.0),
            nozzle_diameter_mm=0.4,
            materials=("pla", "petg", "tpu", "abs"),
        )
        self._online = online
        self._polls_to_done = max(2, polls_to_done)
        self._jobs: dict[str, _LoopJob] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def capabilities(self) -> PrinterCapabilities:
        return self._caps

    def status(self) -> PrinterStatus:
        if not self._online:
            return PrinterStatus(
                online=False, state=PrinterState.offline, detail="mock printer is offline"
            )
        with self._lock:
            busy = any(not j.state.terminal for j in self._jobs.values())
        return PrinterStatus(
            online=True,
            state=PrinterState.printing if busy else PrinterState.operational,
            nozzle_temp_c=210.0 if busy else 25.0,
            bed_temp_c=55.0 if busy else 25.0,
        )

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        if not self._online:
            raise PrinterOffline(f"{self.name} is offline")
        with self._lock:
            self._counter += 1
            job_id = f"{self.name}-{self._counter}"
            self._jobs[job_id] = _LoopJob(name=job_name or gcode_path.name)
        return PrintJob(job_id=job_id, state=JobState.queued, progress=0.0, detail="accepted")

    def job_status(self, job_id: str) -> PrintJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise ConnectorError(f"unknown job: {job_id}")
            if not job.state.terminal:
                job.polls += 1
                job.state = (
                    JobState.done if job.polls >= self._polls_to_done else JobState.printing
                )
            state, polls, name = job.state, job.polls, job.name
        progress = 1.0 if state is JobState.done else (polls - 1) / (self._polls_to_done - 1)
        return PrintJob(job_id=job_id, state=state, progress=round(progress, 4), detail=name)
