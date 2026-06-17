"""Tests for the Marlin-serial connector against the mock Marlin (TCP) server (KC-21, #26).

The connector talks M-code over a transport; these drive the TCP transport (the same protocol as a
serial-over-network bridge), so no real serial hardware is needed. The serial-port path (pyserial)
is covered with an injected fake `serial` module (absent + present + failing); a real serial line's
noise is metal-only (#11).
"""

import sys
import types
import zipfile
from pathlib import Path

import pytest

from kimcad.marlin_connector import MarlinConnector, _checksum_line, _tcp_target
from kimcad.mock_marlin import serve_mock_marlin
from kimcad.printer_connector import (
    ConnectorError,
    JobState,
    NotConfirmed,
    PrinterOffline,
    PrinterState,
)


def _write_gcode_3mf(path: Path, *, gcode: str = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode)
    return path


def _connector(target: str) -> MarlinConnector:
    return MarlinConnector(target, name="mock-marlin", timeout_s=5.0)


# --- helpers ------------------------------------------------------------------

def test_tcp_target_parsing():
    assert _tcp_target("192.168.0.5:8080") == ("192.168.0.5", 8080)
    assert _tcp_target("tcp://host:23") == ("host", 23)
    assert _tcp_target("COM3") is None
    assert _tcp_target("/dev/ttyUSB0") is None
    assert _tcp_target("serial://COM3") is None


def test_checksum_line_is_marlins_xor():
    # "N1 G28" XOR -> a stable, verifiable checksum; framing is "N<n> <line>*<cs>".
    framed = _checksum_line(1, "G28")
    body, _, cs = framed.partition("*")
    assert body == "N1 G28"
    x = 0
    for b in body.encode():
        x ^= b
    assert cs == str(x)


def test_marlin_drives_hardware():
    assert MarlinConnector("x:1").drives_hardware is True


# --- gate (no server needed) --------------------------------------------------

def test_send_requires_confirmation(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(NotConfirmed):
        _connector("127.0.0.1:1").send(g, confirm=False)


def test_send_rejects_non_slice(tmp_path):
    bad = tmp_path / "bad.gcode.3mf"
    bad.write_bytes(b"not a slice")
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        _connector("127.0.0.1:1").send(bad, confirm=True)


# --- against the mock Marlin (TCP) --------------------------------------------

def test_capabilities_handshakes_m115():
    with serve_mock_marlin() as (target, _state):
        caps = _connector(target).capabilities()
    assert caps.name == "mock-marlin"
    assert caps.build_volume_mm is None and caps.nozzle_diameter_mm is None


def test_status_idle_reports_temps():
    with serve_mock_marlin() as (target, _state):
        st = _connector(target).status()
    assert st.online and st.state is PrinterState.operational
    assert st.nozzle_temp_c == 25.0 and st.bed_temp_c == 25.0


def test_send_sd_uploads_the_exact_gcode_and_starts(tmp_path):
    gcode = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n"
    g = _write_gcode_3mf(tmp_path / "part.gcode.3mf", gcode=gcode)
    with serve_mock_marlin(poll_count=2) as (target, state):
        job = _connector(target).send(g, confirm=True, job_name="bracket")
    assert job.state is JobState.printing and job.job_id == "bracket.gco"
    assert state["printing"] is True
    # The bytes that landed on SD reconstruct the source g-code (checksum framing stripped).
    assert state["sd_lines"] == [ln for ln in gcode.split("\n") if ln]


def test_send_then_job_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_marlin(poll_count=2) as (target, _state):
        c = _connector(target)
        job = c.send(g, confirm=True)
        last = c.job_status(job.job_id)
        assert last.state is JobState.printing and 0.0 < last.progress <= 1.0
        for _ in range(6):
            last = c.job_status(job.job_id)
            if last.state is JobState.done:
                break
        assert last.state is JobState.done and last.progress == 1.0


def test_done_is_latched_when_print_finishes_between_polls(tmp_path):
    # The realistic failure: the print completes between two polls, so M27 reads "Not SD printing"
    # without ever showing 100%. The connector LATCHES done from the earlier progress (ENG-004/QA-6).
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_marlin(poll_count=8) as (target, state):
        c = _connector(target)
        job = c.send(g, confirm=True)
        assert c.job_status(job.job_id).state is JobState.printing  # one poll shows progress
        state["printing"] = False  # the print finished between polls -> M27 will say "Not SD printing"
        state["printed"] = 0
        done = c.job_status(job.job_id)
    assert done.state is JobState.done and done.progress == 1.0  # latched, not regressed to queued


def test_job_status_before_any_progress_is_queued(tmp_path):
    # "Not SD printing" with no prior progress for this job_id = not started yet, not done.
    with serve_mock_marlin() as (target, _state):
        job = _connector(target).job_status("never-started.gco")
    assert job.state is JobState.queued


def test_checksum_resend_is_honored_mid_stream(tmp_path):
    # The mock asks to resend the 2nd streamed line once; the connector replays it and the upload
    # still completes with the full content (ENG-001 / TE-03).
    gcode = "G28\nG1 X1 Y1 E1\nG1 X2 Y2 E2\n"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf", gcode=gcode)
    with serve_mock_marlin(resend_at=2) as (target, state):
        job = _connector(target).send(g, confirm=True)
    assert job.state is JobState.printing
    assert state["sd_lines"] == [ln for ln in gcode.split("\n") if ln]  # no corruption, no loss


def test_mid_stream_error_raises_and_closes_the_sd_file(tmp_path):
    # An Error: on the 2nd streamed line aborts the send with a clean ConnectorError; the connector
    # best-effort closes the SD file (M29) so the card isn't left in write mode (TE-04 / QA-3).
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_marlin(error_at=2) as (target, state):
        with pytest.raises(ConnectorError, match="mock mid-stream failure"):
            _connector(target).send(g, confirm=True)
    assert state["printing"] is False  # never started; not left mid-print


def test_status_printing_when_sd_active(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_marlin(poll_count=8) as (target, _state):
        c = _connector(target)
        c.send(g, confirm=True)
        st = c.status()
    assert st.state is PrinterState.printing and st.nozzle_temp_c == 210.0


def test_boot_banner_chatter_is_skipped(tmp_path):
    # A printer that greets with a boot banner must not confuse the first command's reply (ENG-008).
    with serve_mock_marlin(banner=True) as (target, _state):
        caps = _connector(target).capabilities()
    assert caps.name == "mock-marlin"


def test_capabilities_rejects_a_non_marlin_device():
    import socketserver
    import threading

    class Dumb(socketserver.StreamRequestHandler):
        def handle(self):
            while self.rfile.readline():
                self.wfile.write(b"ok\n")
                self.wfile.flush()

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Dumb)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = _connector(f"127.0.0.1:{srv.server_address[1]}")
        with pytest.raises(ConnectorError, match="Marlin"):
            c.capabilities()
        # status() on a non-Marlin peer reports error, not a false "operational" (QA-5).
        assert c.status().state is PrinterState.error
    finally:
        srv.shutdown()
        srv.server_close()


def test_send_handshakes_before_writing_to_a_non_marlin_peer(tmp_path):
    # A wrong-baud / non-Marlin peer must be rejected by the M115 handshake BEFORE any SD write,
    # so no garbage file + no phantom job (QA-2).
    import socketserver
    import threading

    written = []

    class Dumb(socketserver.StreamRequestHandler):
        def handle(self):
            while True:
                ln = self.rfile.readline()
                if not ln:
                    return
                written.append(ln)
                self.wfile.write(b"ok\n")  # never identifies as Marlin
                self.wfile.flush()

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Dumb)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    try:
        with pytest.raises(ConnectorError, match="Marlin"):
            _connector(f"127.0.0.1:{srv.server_address[1]}").send(g, confirm=True)
        # Only the M115 handshake was sent — no M28/SD write.
        assert all(b"M28" not in w for w in written)
    finally:
        srv.shutdown()
        srv.server_close()


# --- offline (nothing listening) ----------------------------------------------

def test_capabilities_offline_raises_printer_offline():
    with pytest.raises(PrinterOffline):
        _connector("127.0.0.1:1").capabilities()


def test_offline_status_reports_offline():
    st = _connector("127.0.0.1:1").status()
    assert st.online is False and st.state is PrinterState.offline


def test_offline_send_raises_printer_offline(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(PrinterOffline):
        _connector("127.0.0.1:1").send(g, confirm=True)


def test_offline_job_status_returns_error():
    job = _connector("127.0.0.1:1").job_status("x")
    assert job.state is JobState.error


def test_offline_job_status_detail_is_clean_not_raw_exception():
    # ENG-009: job_status() must mirror status()'s QA-003 clean detail — never the raw
    # urllib/WinError/serial exception string (which surfaces in the UI/API).
    job = _connector("127.0.0.1:1").job_status("x")
    assert job.detail == "could not reach the printer"
    # the raw OSError text (a port number, "Connection refused", a WinError code) is gone
    assert "Errno" not in (job.detail or "") and "127.0.0.1" not in (job.detail or "")


# --- serial-port path (pyserial absent / present / failing) -------------------

def test_serial_target_without_pyserial_is_a_clear_error(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def _no_serial(name, *a, **k):
        if name == "serial":
            raise ImportError("no pyserial")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_serial)
    with pytest.raises(ConnectorError, match="pyserial"):
        _connector("COM3").capabilities()


def _fake_serial_module(responses: list[bytes]):
    """A fake `serial` module whose Serial replays `responses` on read()."""
    mod = types.ModuleType("serial")

    class _Fake:
        def __init__(self, *a, **k):
            self._buf = b"".join(responses)

        def write(self, data):
            return len(data)

        def read(self, n=1):
            chunk, self._buf = self._buf[:n], self._buf[n:]
            return chunk

        def close(self):
            pass

    class _SerialException(Exception):
        pass

    mod.Serial = _Fake
    mod.SerialException = _SerialException
    return mod


def test_serial_port_happy_path_with_injected_pyserial(monkeypatch):
    # The real-serial transport path runs end to end against a fake pyserial (the protocol is the
    # same as TCP; only the open differs). Real serial-line noise is metal-only (#11).
    fake = _fake_serial_module([b"FIRMWARE_NAME:Marlin 2.1 (fake)\nok\n"])
    monkeypatch.setitem(sys.modules, "serial", fake)
    caps = _connector("COM7").capabilities()
    assert caps.name == "mock-marlin"


def test_serial_open_failure_is_printer_offline(monkeypatch):
    fake = _fake_serial_module([])

    def _boom(*a, **k):
        raise fake.SerialException("port busy")

    fake.Serial = _boom
    monkeypatch.setitem(sys.modules, "serial", fake)
    with pytest.raises(PrinterOffline, match="serial port"):
        _connector("/dev/ttyUSB0").capabilities()
