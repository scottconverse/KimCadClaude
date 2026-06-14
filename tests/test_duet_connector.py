"""Tests for the RepRapFirmware/Duet connector against the mock RRF server (KC-21, #26)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.duet_connector import DuetConnector
from kimcad.mock_duet import serve_mock_duet
from kimcad.printer_connector import (
    AuthError,
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


def _connector(base_url: str, *, password: str | None = None) -> DuetConnector:
    return DuetConnector(base_url, password, name="mock-duet")


# --- self-describes as real hardware ------------------------------------------

def test_duet_drives_hardware():
    assert DuetConnector("http://x").drives_hardware is True


# --- gate (no server needed: ensure_sendable fires first) ---------------------

def test_send_requires_confirmation(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(NotConfirmed):
        _connector("http://127.0.0.1:1").send(g, confirm=False)


def test_send_rejects_non_slice(tmp_path):
    bad = tmp_path / "bad.gcode.3mf"
    bad.write_bytes(b"not a slice")
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        _connector("http://127.0.0.1:1").send(bad, confirm=True)


# --- against the mock RRF server (open board, the common LAN case) ------------

def test_capabilities_from_axis_limits():
    with serve_mock_duet() as (base, _state):
        caps = _connector(base).capabilities()
    # axisMaxes [230,210,200] - axisMins [0,0,0] = build volume; RRF reports no nozzle diameter.
    assert caps.build_volume_mm == (230.0, 210.0, 200.0)
    assert caps.nozzle_diameter_mm is None


def test_capabilities_honors_non_zero_build_origin():
    with serve_mock_duet(axis_mins=[-5.0, -5.0, 0.0], axis_maxes=[230.0, 210.0, 200.0]) as (base, _s):
        caps = _connector(base).capabilities()
    assert caps.build_volume_mm == (235.0, 215.0, 200.0)


def test_status_operational_when_idle():
    with serve_mock_duet() as (base, _state):
        st = _connector(base).status()
    assert st.online and st.state is PrinterState.operational
    assert st.nozzle_temp_c == 25.0 and st.bed_temp_c == 25.0


def test_send_uploads_to_gcodes_and_starts_then_job_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "part.gcode.3mf")
    with serve_mock_duet(step=40.0) as (base, state):
        c = _connector(base)
        job = c.send(g, confirm=True, job_name="bracket")
        assert job.state is JobState.printing
        assert state["files"] == ["/gcodes/bracket.gcode"]  # uploaded to the SD gcodes folder
        assert state["printing"] is True  # M32 started it
        last = c.job_status(job.job_id)
        assert last.state is JobState.printing and 0.0 < last.progress <= 1.0
        for _ in range(6):
            last = c.job_status(job.job_id)
            if last.state is JobState.done:
                break
        assert last.state is JobState.done and last.progress == 1.0


def test_job_status_reports_paused():
    with serve_mock_duet() as (base, state):
        state["status"] = "S"  # stopped/paused
        job = _connector(base).job_status("x")
    assert job.state is JobState.paused


def test_status_unknown_char_is_error():
    with serve_mock_duet() as (base, state):
        state["status"] = "Z"  # not a real RRF status char
        st = _connector(base).status()
    assert st.state is PrinterState.error


# --- auth (password-protected board) ------------------------------------------

def test_wrong_password_is_auth_error_not_offline(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet(password="the-real-pw") as (base, _state):
        c = _connector(base, password="wrong-pw")
        with pytest.raises(AuthError):
            c.send(g, confirm=True)
        st = c.status()
        assert st.online is True and st.state is PrinterState.error


def test_missing_password_against_protected_board_is_auth_error():
    # No password configured, but the board requires one -> reachable-but-rejected = AuthError.
    with serve_mock_duet(password="the-real-pw") as (base, _state):
        with pytest.raises(AuthError):
            _connector(base).capabilities()


def test_password_never_appears_in_error(tmp_path):
    secret = "duet-secret-leak-me-7c2b"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet(password="the-real-pw") as (base, _state):
        c = _connector(base, password=secret)
        with pytest.raises(AuthError) as exc:
            c.send(g, confirm=True)
        assert secret not in str(exc.value)


# --- offline (nothing listening) ----------------------------------------------

def test_capabilities_offline_raises_printer_offline():
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").capabilities()


def test_offline_status_reports_offline():
    st = _connector("http://127.0.0.1:1").status()
    assert st.online is False and st.state is PrinterState.offline


def test_offline_send_raises_printer_offline(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").send(g, confirm=True)


def test_offline_job_status_returns_error():
    job = _connector("http://127.0.0.1:1").job_status("x")
    assert job.state is JobState.error


# --- a garbage HTTP-200 body degrades to an error STATUS, never a raw traceback ----

def test_status_garbage_200_is_error_not_raise(monkeypatch):
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"<html>not json</html>"))
    st = c.status()
    assert st.state is PrinterState.error and st.online is True


def test_capabilities_garbage_200_raises_clean_error(monkeypatch):
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"not json"))
    with pytest.raises(ConnectorError) as exc:
        c.capabilities()
    assert exc.value.reason == "bad_response"


# --- a 5xx means the board is faulted, reported as NOT online -----------------

def test_status_5xx_reports_not_online(monkeypatch):
    import urllib.error

    c = _connector("http://x")

    def _boom(*a, **k):
        raise urllib.error.HTTPError("http://x/rr_status", 503, "rrf down", {}, None)

    monkeypatch.setattr(c, "_request", _boom)
    st = c.status()
    assert st.online is False and st.state is PrinterState.error
