"""Tests for the Moonraker (Klipper) connector against the mock Moonraker server (Stage 3)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.mock_moonraker import serve_mock_moonraker
from kimcad.moonraker_connector import MoonrakerConnector
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


def _connector(base_url: str, *, key: str | None = None) -> MoonrakerConnector:
    return MoonrakerConnector(base_url, key, name="mock-klipper")


# --- the connector self-describes as real hardware ----------------------------


def test_moonraker_drives_hardware():
    assert MoonrakerConnector("http://x").drives_hardware is True


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


def test_send_rejects_multi_plate_archive(tmp_path):
    p = tmp_path / "multi.gcode.3mf"
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X1 Y1 E1\n")
        zf.writestr("Metadata/plate_2.gcode", "G28\nG1 X2 Y2 E1\n")
    with pytest.raises(ConnectorError, match="plates"):
        _connector("http://127.0.0.1:1").send(p, confirm=True)


# --- against the mock Moonraker server (unauthenticated, the common LAN case) --


def test_capabilities_from_toolhead_and_config():
    with serve_mock_moonraker() as (base, _state):
        caps = _connector(base).capabilities()
    # axis_maximum [250,250,240] - axis_minimum [0,0,0] = build volume
    assert caps.build_volume_mm == (250.0, 250.0, 240.0)
    assert caps.nozzle_diameter_mm == 0.4
    assert caps.materials is None  # Moonraker doesn't report loaded materials


def test_status_operational_when_idle():
    with serve_mock_moonraker() as (base, _state):
        st = _connector(base).status()
    assert st.online and st.state is PrinterState.operational
    assert st.nozzle_temp_c == 25.0


def test_send_uploads_and_starts_then_job_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "part.gcode.3mf")
    with serve_mock_moonraker(step=0.4) as (base, state):
        c = _connector(base)
        job = c.send(g, confirm=True, job_name="bracket")
        assert job.state is JobState.printing
        assert state["files"] == ["bracket.gcode"]  # uploaded as flat .gcode
        assert state["printing"] is True
        p1 = c.job_status(job.job_id)
        assert p1.state is JobState.printing and 0.0 < p1.progress <= 1.0
        last = p1
        for _ in range(6):
            last = c.job_status(job.job_id)
            if last.state is JobState.done:
                break
        assert last.state is JobState.done and last.progress == 1.0


def test_wrong_api_key_is_auth_error_not_offline(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_moonraker(api_key="the-real-key") as (base, _state):
        c = _connector(base, key="wrong-key")
        with pytest.raises(AuthError, match="HTTP 401"):
            c.send(g, confirm=True)
        st = c.status()
        assert st.online is True and st.state is PrinterState.error


def test_missing_key_against_authed_server_is_auth_error():
    # No key configured, but the server requires one -> reachable-but-rejected = AuthError.
    with serve_mock_moonraker(api_key="the-real-key") as (base, _state):
        with pytest.raises(AuthError):
            _connector(base).capabilities()


def test_capabilities_offline_raises_printer_offline():
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").capabilities()


def test_capabilities_honors_non_zero_build_origin():
    # A printer reporting a negative axis_minimum (some delta/CoreXY beds): the build volume is
    # the travel SPAN (max - min), not just max. (FIND-003)
    with serve_mock_moonraker(
        axis_minimum=[-5.0, -5.0, 0.0, 0.0], axis_maximum=[250.0, 250.0, 240.0, 0.0]
    ) as (base, _state):
        caps = _connector(base).capabilities()
    assert caps.build_volume_mm == (255.0, 255.0, 240.0)


def test_job_status_http_error_is_error_not_unreachable():
    # FIND-001/002: a 401 on job_status is reachable-but-rejected, reported as HTTP error,
    # NOT mislabeled "unreachable" (the HTTPError except must precede the URLError one).
    with serve_mock_moonraker(api_key="the-real-key") as (base, _state):
        job = _connector(base, key="wrong").job_status("x")
    assert job.state is JobState.error
    assert "HTTP 401" in job.detail and "unreachable" not in job.detail


def test_job_status_reports_paused():
    # FIND-006: a paused Klipper print is reported as JobState.paused, not "printing".
    with serve_mock_moonraker() as (base, state):
        state["klip_state"] = "paused"  # printer is paused mid-job
        job = _connector(base).job_status("x")
    assert job.state is JobState.paused


# --- offline behavior (nothing listening) -------------------------------------


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


def test_api_key_never_appears_in_error(tmp_path):
    secret = "moonraker-secret-leak-me-7c2b"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_moonraker(api_key="the-real-key") as (base, _state):
        c = _connector(base, key=secret)
        with pytest.raises(AuthError) as exc:
            c.send(g, confirm=True)
        assert secret not in str(exc.value)
