"""Tests for the Snapmaker U1 connector (4-toolhead Klipper/Moonraker, Stage 10+)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.mock_moonraker import serve_mock_moonraker
from kimcad.printer_connector import AuthError, PrinterOffline, PrinterState
from kimcad.snapmaker_connector import SnapmakerConnector


def _connector(base_url: str, *, key: str | None = None) -> SnapmakerConnector:
    return SnapmakerConnector(base_url, key, name="mock-snapmaker")


def _write_gcode_3mf(path: Path, *, gcode: str = "G28\nG1 X10 Y10 E1\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode)
    return path


# --- class-level contract -------------------------------------------------------


def test_snapmaker_drives_hardware():
    assert SnapmakerConnector.drives_hardware is True


def test_snapmaker_inherits_moonraker():
    from kimcad.moonraker_connector import MoonrakerConnector

    assert issubclass(SnapmakerConnector, MoonrakerConnector)


# --- capabilities (4-toolhead) --------------------------------------------------


def test_capabilities_returns_toolhead_count_4():
    """All four extruder objects present → toolhead_count = 4."""
    with serve_mock_moonraker(
        axis_maximum=[270.5, 271.0, 270.05, 0.0]
    ) as (base, _state):
        c = _connector(base)
        caps = c.capabilities()
        # The mock returns extruder, extruder1, extruder2, extruder3 when queried.
        assert caps.toolhead_count == 4


def test_capabilities_toolhead_count_at_least_1():
    """Even if only `extruder` is present the count floors at 1."""
    with serve_mock_moonraker() as (base, _state):
        c = _connector(base)
        caps = c.capabilities()
        assert caps.toolhead_count >= 1


def test_capabilities_build_volume_from_axis():
    with serve_mock_moonraker(
        axis_minimum=[0.5, 1.0, 0.0, 0.0],
        axis_maximum=[271.0, 272.0, 270.05, 0.0],
    ) as (base, _state):
        caps = _connector(base).capabilities()
        assert caps.build_volume_mm is not None
        assert abs(caps.build_volume_mm[0] - 270.5) < 0.01
        assert abs(caps.build_volume_mm[1] - 271.0) < 0.01


def test_capabilities_offline_raises():
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").capabilities()


def test_capabilities_wrong_key_raises_auth():
    with serve_mock_moonraker(api_key="real") as (base, _state):
        with pytest.raises(AuthError):
            _connector(base, key="wrong").capabilities()


# --- status (multi-extruder temps) -----------------------------------------------


def test_status_returns_toolhead_temps_tuple():
    with serve_mock_moonraker() as (base, state):
        state["printing"] = True
        state["klip_state"] = "printing"
        c = _connector(base)
        st = c.status()
        # During a print the mock sets extruder=210, extruder1=205, extruder2=200, extruder3=195.
        assert st.toolhead_temps is not None
        assert len(st.toolhead_temps) == 4
        assert st.toolhead_temps[0] == pytest.approx(210.0)
        assert st.toolhead_temps[1] == pytest.approx(205.0)
        assert st.toolhead_temps[2] == pytest.approx(200.0)
        assert st.toolhead_temps[3] == pytest.approx(195.0)


def test_status_nozzle_temp_c_is_t0():
    with serve_mock_moonraker() as (base, state):
        state["printing"] = True
        state["klip_state"] = "printing"
        st = _connector(base).status()
        assert st.nozzle_temp_c == pytest.approx(210.0)


def test_status_idle_temps_are_cold():
    with serve_mock_moonraker() as (base, _state):
        st = _connector(base).status()
        assert st.toolhead_temps is not None
        for t in st.toolhead_temps:
            assert t <= 30.0


def test_status_offline_is_offline():
    st = _connector("http://127.0.0.1:1").status()
    assert st.online is False
    assert st.state is PrinterState.offline


# --- control (pause / resume / cancel) -------------------------------------------


def _start_print(state: dict) -> None:
    state["printing"] = True
    state["klip_state"] = "printing"
    state["progress"] = 0.1
    state["filename"] = "job.gcode"


def test_pause_via_snapmaker():
    with serve_mock_moonraker() as (base, state):
        _start_print(state)
        _connector(base).pause()
        assert state["paused"] is True
        assert state["klip_state"] == "paused"


def test_resume_via_snapmaker():
    with serve_mock_moonraker() as (base, state):
        _start_print(state)
        c = _connector(base)
        c.pause()
        c.resume()
        assert state["printing"] is True
        assert state["klip_state"] == "printing"


def test_cancel_via_snapmaker():
    with serve_mock_moonraker() as (base, state):
        _start_print(state)
        _connector(base).cancel()
        assert state["klip_state"] == "cancelled"
        assert state["printing"] is False
