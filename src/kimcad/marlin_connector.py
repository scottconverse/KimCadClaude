"""Marlin-serial send-to-printer connector (KC-21, #26).

A concrete :class:`~kimcad.printer_connector.PrinterConnector` for Marlin firmware over its raw
M-code line protocol — the huge installed base of Ender-class and most consumer FDM machines.
Marlin has no host software of its own, so KimCad drives it the way a host would: upload the
G-code to the printer's SD card (``M28``/``M29``), then select + start the print (``M23``/``M24``)
and poll SD progress (``M27``). The printer prints autonomously from SD once started. During SD
write the streamed lines are STORED, not executed, so the upload acks quickly (no heat/home pause).

Integrity: the SD upload is streamed with Marlin's line-number + checksum protocol (``M110``,
``N<n> … *<xor>``) and honors a ``Resend: <n>`` request, so a line corrupted on a noisy USB-serial
link is detected and replayed rather than silently written to the SD file (KC-21 audit ENG-001).

Transport: the protocol is identical over a USB serial port or a TCP socket. KimCad supports both:

- a ``host:port`` target → a TCP socket (stdlib, no dependency). Serves the mock-twin AND real
  serial-over-network bridges (ser2net, ESP3D, an OctoPrint serial relay);
- a serial-port target (``COM3``, ``/dev/ttyUSB0``) → ``pyserial`` (an OPTIONAL dependency; a clear
  "pip install pyserial" message when it's absent).

``send`` runs only after the shared :func:`~kimcad.printer_connector.ensure_sendable` gate. Tested
against :mod:`kimcad.mock_marlin` (a TCP Marlin simulator). No real hardware is driven until metal
validation (#11) — the conformance mock cannot reproduce real serial-line noise, so the checksum/
resend path is exercised by a fault-injecting mock here but proven on metal there.

LIMITATION (job completion): Marlin's done-signal is asynchronous and ``M27`` reports "Not SD
printing" once a print finishes — there is no per-file done query. ``job_status`` therefore LATCHES
done: once it has seen SD progress for a ``job_id`` and then sees "Not SD printing", it reports
``done`` (the print ran and stopped). A connector instance is reused across a poll loop, so the
latch holds for the realistic case; callers should still treat the first terminal state as final.
"""

from __future__ import annotations

import re
import socket
import threading
from pathlib import Path
from typing import Any, Callable

from kimcad.printer_connector import (
    ConnectorError,
    JobState,
    PrinterCapabilities,
    PrinterOffline,
    PrinterState,
    PrinterStatus,
    PrintJob,
    ensure_sendable,
    extract_single_plate_gcode,
)

# M105 temp report:  "ok T:24.83 /0.00 B:23.10 /0.00 @:0 B@:0"
_TEMP_T = re.compile(r"\bT:\s*(-?\d+(?:\.\d+)?)")
_TEMP_B = re.compile(r"\bB:\s*(-?\d+(?:\.\d+)?)")
# M27 SD status:  "SD printing byte 2048/10240"
_SD_BYTES = re.compile(r"SD printing byte\s+(\d+)\s*/\s*(\d+)")
# A resend request:  "Resend: 12"  (or "rs N12")
_RESEND = re.compile(r"(?:Resend|rs):?\s*N?(\d+)", re.IGNORECASE)


def _checksum_line(n: int, line: str) -> str:
    """Marlin line-number + checksum framing: ``N<n> <line>*<xor of the bytes before '*'>``."""
    body = f"N{n} {line}"
    cs = 0
    for b in body.encode("ascii", "replace"):
        cs ^= b
    return f"{body}*{cs}"


class _Transport:
    """A line-oriented M-code transport: write a command line, read response lines until the
    Marlin ``ok`` ack (tolerating ``echo:busy:`` heartbeats and boot chatter), surfacing an
    ``Error:`` as a clean error and a ``Resend:`` request to the caller."""

    def __init__(self, send_bytes: Callable[[bytes], Any], recv_bytes: Callable[[int], bytes],
                 close: Callable[[], None]):
        self._send = send_bytes
        self._recv = recv_bytes
        self._close = close
        self._buf = b""

    def _read_line(self) -> str:
        while b"\n" not in self._buf:
            chunk = self._recv(256)
            if not chunk:
                raise ConnectorError("printer closed the connection mid-line", reason="bad_response")
            self._buf += chunk
        line, _, self._buf = self._buf.partition(b"\n")
        return line.decode("utf-8", "replace").strip()

    def send_raw(self, cmd: str) -> None:
        self._send((cmd + "\n").encode("ascii", "replace"))

    def command(self, cmd: str) -> tuple[list[str], int | None]:
        """Send ``cmd``; read up to the ``ok`` ack. Returns ``(reply_lines, resend_n)`` — ``resend_n``
        is the line number Marlin asked to resend (then no ``ok`` is awaited), else None."""
        self.send_raw(cmd)
        lines: list[str] = []
        for _ in range(4000):  # generous: busy heartbeats + boot chatter can precede the ok
            line = self._read_line()
            if not line:
                continue
            rs = _RESEND.search(line)
            if rs is not None:
                return lines, int(rs.group(1))
            lines.append(line)
            head = line.split(maxsplit=1)[0] if line else ""
            if head == "ok":
                return lines, None
            if line.startswith("Error:") or head == "Error":
                raise ConnectorError(
                    f"printer reported an error: {line[:200]}",
                    reason="bad_response",
                    user_message="The printer reported an error. Check its screen and try again.",
                )
            # Any other line (echo:busy:, T:/B: autoreport, a banner) is collected and skipped —
            # the loop keeps reading until the ok, so a heartbeat never ends the command early.
        raise ConnectorError("no `ok` from the printer", reason="bad_response")

    def close(self) -> None:
        try:
            self._close()
        except OSError:
            pass


def _tcp_target(target: str) -> tuple[str, int] | None:
    """Parse ``host:port`` (optionally ``tcp://host:port``) → ``(host, port)``; None for a serial
    port path (``COM3``, ``/dev/ttyUSB0``)."""
    t = target.strip()
    if t.lower().startswith("tcp://"):
        t = t[len("tcp://"):]
    if t.lower().startswith("serial://"):
        return None
    host, sep, port = t.rpartition(":")
    if sep and host and port.isdigit():
        return host, int(port)
    return None


class MarlinConnector:
    """A :class:`~kimcad.printer_connector.PrinterConnector` for Marlin over serial or TCP.

    Opens a fresh transport per operation; the connection is closed before the call returns. A
    small per-instance latch makes ``job_status`` report ``done`` reliably (see the module docs)."""

    drives_hardware = True  # a real send reaches a real printer

    def __init__(
        self,
        target: str,
        *,
        baud: int = 115200,
        name: str = "marlin",
        timeout_s: float = 20.0,
    ):
        self.name = name
        self._target = target
        self._baud = baud
        self._timeout = timeout_s
        self._lock = threading.Lock()
        self._progressed: set[str] = set()  # job_ids that have shown SD progress (for the done latch)

    # --- transport ----------------------------------------------------------
    def _open(self) -> _Transport:
        tcp = _tcp_target(self._target)
        if tcp is not None:
            host, port = tcp
            sock = socket.create_connection((host, port), timeout=self._timeout)
            sock.settimeout(self._timeout)
            return _Transport(sock.sendall, sock.recv, sock.close)
        return self._open_serial()

    def _open_serial(self) -> _Transport:
        try:
            import serial  # pyserial — optional
        except ImportError as e:
            raise ConnectorError(
                f"sending to {self.name!r} over the serial port {self._target!r} needs the "
                "pyserial package, which isn't installed",
                reason="config",
                user_message=f"To print to '{self.name}' over USB, install pyserial "
                "(`pip install pyserial`), or use a network address instead.",
            ) from e
        port = self._target
        if port.lower().startswith("serial://"):
            port = port[len("serial://"):]
        try:
            ser = serial.Serial(port, self._baud, timeout=self._timeout)
        except Exception as e:  # noqa: BLE001 - pyserial raises SerialException on a bad/busy port
            raise PrinterOffline(
                f"{self.name} serial port {port!r} unavailable: {e}",
                user_message=f"Couldn't open the printer '{self.name}' on {port}. Is it plugged in "
                "and not in use by another program?",
            ) from e
        return _Transport(ser.write, ser.read, ser.close)

    def _converse(self, run: Callable[[_Transport], Any]) -> Any:
        try:
            t = self._open()
        except (ConnectorError, PrinterOffline):
            raise
        except OSError as e:
            raise PrinterOffline(
                f"{self.name} unreachable: {e}",
                user_message=f"Couldn't reach the printer '{self.name}'. Is it powered on "
                "and connected?",
            ) from e
        try:
            return run(t)
        except (OSError, socket.timeout) as e:
            raise PrinterOffline(
                f"{self.name} connection failed: {e}",
                user_message=f"Lost the connection to the printer '{self.name}'.",
            ) from e
        finally:
            t.close()

    @staticmethod
    def _is_marlin_reply(text: str) -> bool:
        return "FIRMWARE_NAME" in text or "Marlin" in text

    # --- connector contract -------------------------------------------------
    def capabilities(self) -> PrinterCapabilities:
        def run(t: _Transport) -> PrinterCapabilities:
            lines, _ = t.command("M115")  # firmware info handshake — confirms it's a Marlin device
            if not self._is_marlin_reply(" ".join(lines)):
                raise ConnectorError(
                    f"{self.name} did not answer M115 like a Marlin printer",
                    reason="bad_response",
                    user_message=f"The device at '{self.name}' didn't respond like a Marlin "
                    "printer.",
                )
            # Marlin's M-code surface reports neither build volume nor nozzle diameter reliably,
            # so those stay None (honest — filled from the chosen profile instead).
            return PrinterCapabilities(name=self.name, build_volume_mm=None, nozzle_diameter_mm=None)

        return self._converse(run)

    def status(self) -> PrinterStatus:
        try:
            def run(t: _Transport) -> PrinterStatus:
                temp_line = " ".join(t.command("M105")[0])
                sd_line = " ".join(t.command("M27")[0])
                nozzle = _TEMP_T.search(temp_line)
                bed = _TEMP_B.search(temp_line)
                printing = bool(_SD_BYTES.search(sd_line))
                # Identity guard (QA-5): a peer that shows neither a temp report nor an SD line is
                # not answering like Marlin — report error, not a false "operational idle".
                if not (nozzle or bed or printing or "Not SD printing" in sd_line):
                    return PrinterStatus(
                        online=True, state=PrinterState.error, detail="unexpected response from printer"
                    )
                return PrinterStatus(
                    online=True,
                    state=PrinterState.printing if printing else PrinterState.operational,
                    detail="SD printing" if printing else "idle",
                    nozzle_temp_c=float(nozzle.group(1)) if nozzle else None,
                    bed_temp_c=float(bed.group(1)) if bed else None,
                )

            return self._converse(run)
        except PrinterOffline:
            return PrinterStatus(online=False, state=PrinterState.offline, detail="could not connect")
        except ConnectorError:
            return PrinterStatus(
                online=True, state=PrinterState.error, detail="unexpected response from printer"
            )

    @staticmethod
    def _sd_name(base: str) -> str:
        """A conservative SD filename (8.3-ish): up to 8 alphanumerics + ``.gco`` so it works on
        firmware without long-filename support. NOTE: designs sharing the first 8 alphanumeric
        characters reuse the same SD file (a deliberate compatibility tradeoff — see the docs)."""
        stem = "".join(ch for ch in base if ch.isalnum())[:8] or "kimcad"
        return f"{stem}.gco"

    def send(self, gcode_path: Path, *, confirm: bool, job_name: str | None = None) -> PrintJob:
        ensure_sendable(gcode_path, confirm=confirm)
        gcode = extract_single_plate_gcode(gcode_path)
        base = job_name or gcode_path.name.removesuffix(".gcode.3mf")
        sd_name = self._sd_name(base)
        data_lines = [raw.decode("ascii", "replace").strip() for raw in gcode.split(b"\n")]
        data_lines = [ln for ln in data_lines if ln]

        def run(t: _Transport) -> PrintJob:
            # Identity handshake BEFORE writing anything to SD (QA-2): a wrong-baud / non-Marlin
            # peer is rejected up front, never left with a half-written file + a phantom job.
            id_lines, _ = t.command("M115")
            if not self._is_marlin_reply(" ".join(id_lines)):
                raise ConnectorError(
                    f"{self.name} did not answer M115 like a Marlin printer",
                    reason="bad_response",
                    user_message=f"The device at '{self.name}' didn't respond like a Marlin "
                    "printer; refusing to upload.",
                )
            t.command("M110 N0")  # reset the line-number counter for the checksummed stream
            t.command(f"M28 {sd_name}")  # open the SD file for writing
            try:
                self._stream_checksummed(t, data_lines)
                t.command("M29")  # close the SD file
            except ConnectorError:
                # A mid-stream failure leaves the SD file open — best-effort close it so the card
                # isn't left in write mode (TE-04 / QA-3).
                try:
                    t.command("M29")
                except (ConnectorError, OSError):
                    pass
                raise
            t.command(f"M23 {sd_name}")  # select the file
            t.command("M24")  # start the SD print
            return PrintJob(job_id=sd_name, state=JobState.printing, progress=0.0, detail="started")

        return self._converse(run)

    @staticmethod
    def _stream_checksummed(t: _Transport, lines: list[str]) -> None:
        """Stream the G-code lines with line numbers + checksums, honoring ``Resend: <n>``. Line n
        (1-based, after ``M110 N0``) is ``lines[n-1]``."""
        i = 0
        n = 1
        resend_budget = 4 * max(1, len(lines)) + 20  # bound replays so a stuck line can't loop forever
        while i < len(lines):
            _reply, resend = t.command(_checksum_line(n, lines[i]))
            if resend is not None:
                resend_budget -= 1
                if resend_budget <= 0:
                    raise ConnectorError(
                        "printer kept requesting resends — the serial link looks unreliable",
                        reason="bad_response",
                        user_message="The connection to the printer is dropping data. Check the "
                        "USB cable, then try again.",
                    )
                if 1 <= resend <= len(lines):
                    i, n = resend - 1, resend  # rewind to the requested line and replay
                continue
            i += 1
            n += 1

    def job_status(self, job_id: str) -> PrintJob:
        try:
            def run(t: _Transport) -> PrintJob:
                sd_line = " ".join(t.command("M27")[0])
                m = _SD_BYTES.search(sd_line)
                if not m:
                    # "Not SD printing": if we've seen this job print, it has finished (LATCH done);
                    # otherwise it hasn't started yet. M27 is global SD state with no per-file id, so
                    # this is a best-effort signal — see the module docstring (ENG-004 / QA-6).
                    with self._lock:
                        done = job_id in self._progressed
                    return (
                        PrintJob(job_id=job_id, state=JobState.done, progress=1.0)
                        if done
                        else PrintJob(job_id=job_id, state=JobState.queued, detail="not SD printing")
                    )
                done, total = int(m.group(1)), int(m.group(2))
                progress = max(0.0, min(1.0, done / total)) if total else 0.0
                if done > 0 or total > 0:
                    with self._lock:
                        self._progressed.add(job_id)
                if total > 0 and done >= total:
                    return PrintJob(job_id=job_id, state=JobState.done, progress=1.0)
                return PrintJob(job_id=job_id, state=JobState.printing, progress=round(progress, 4))

            return self._converse(run)
        except (PrinterOffline, ConnectorError):
            # ENG-009: mirror the QA-003 status() treatment — a clean fixed detail, not the raw
            # exception text (a noisy urllib/WinError/serial string), which the UI/API surfaces.
            return PrintJob(job_id=job_id, state=JobState.error, detail="could not reach the printer")
