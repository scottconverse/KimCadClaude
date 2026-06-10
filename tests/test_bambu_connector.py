"""Stage 10 Slice 10.3 — the Bambu-native connector, proven wholly against an injected fake
transport (no hardware, no real bambulabs-api needed: the package is OPTIONAL and these tests
must run identically with or without it installed — the strict CI gate allows no skips)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

import kimcad.connectors as connectors
from kimcad.bambu_connector import BambuConnector
from kimcad.config import Config
from kimcad.connectors import build_connector, connector_is_configured, connector_is_simulated
from kimcad.printer_connector import (
    ConnectorError,
    JobState,
    NotConfirmed,
    PrinterState,
)


def _write_gcode_3mf(path: Path, *, gcode: str = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode)
    return path


class FakeState:
    def __init__(self, name: str):
        self.name = name


class FakePrinter:
    """A stand-in for bambulabs_api.Printer with the exact surface the connector uses."""

    def __init__(self, *, state: str = "IDLE", ready_after: int = 0, start_ok: bool = True):
        self.state_name = state
        self._ready_countdown = ready_after  # mqtt_client_ready() False this many times first
        self.start_ok = start_ok
        self.mqtt_started = False
        self.mqtt_stopped = False
        self.uploaded: tuple[str, bytes] | None = None
        self.started_with: tuple | None = None
        self.percentage: int | None = 42

    def mqtt_start(self):
        self.mqtt_started = True

    def mqtt_stop(self):
        self.mqtt_stopped = True

    def mqtt_client_ready(self) -> bool:
        if self._ready_countdown > 0:
            self._ready_countdown -= 1
            return False
        return True

    def get_state(self):
        return FakeState(self.state_name)

    def get_percentage(self):
        return self.percentage

    def get_nozzle_temperature(self):
        return 219.5

    def get_bed_temperature(self):
        return 55.0

    def nozzle_diameter(self):
        return 0.4

    def upload_file(self, file, filename):
        self.uploaded = (filename, file.read())
        return f"226 {filename}"

    def start_print(self, filename, plate_number, use_ams=True, **_kw):
        self.started_with = (filename, plate_number, use_ams)
        return self.start_ok


def _connector(fake: FakePrinter, **kw) -> BambuConnector:
    return BambuConnector(
        "192.168.0.60", "12345678", "01S00C123", name="bambu_p2s",
        timeout_s=1.0, printer_factory=lambda *_a: fake, **kw,
    )


# --- the confirm gate (no transport touched) -----------------------------------------


def test_send_requires_explicit_confirm(tmp_path):
    fake = FakePrinter()
    f = _write_gcode_3mf(tmp_path / "part.gcode.3mf")
    with pytest.raises(NotConfirmed):
        _connector(fake).send(f, confirm=1)  # truthy is NOT an explicit confirm
    assert fake.mqtt_started is False  # the gate fired before any network/transport work


def test_send_refuses_a_motionless_file(tmp_path):
    fake = FakePrinter()
    f = _write_gcode_3mf(tmp_path / "hollow.gcode.3mf", gcode="M104 S200\n")
    with pytest.raises(ConnectorError):
        _connector(fake).send(f, confirm=True)
    assert fake.uploaded is None


# --- send ------------------------------------------------------------------------------


def test_send_uploads_the_whole_3mf_and_starts_plate_1(tmp_path):
    """Bambu-native: the sliced .gcode.3mf is the printer's own format — uploaded AS-IS
    (byte-identical, no G-code extraction) and started by filename + plate."""
    fake = FakePrinter(state="IDLE")
    f = _write_gcode_3mf(tmp_path / "bracket.gcode.3mf")
    job = _connector(fake).send(f, confirm=True)
    name, payload = fake.uploaded
    assert name == "bracket.gcode.3mf"
    assert payload == f.read_bytes()  # the whole 3MF, untouched
    assert fake.started_with == ("bracket.gcode.3mf", 1, True)
    assert job.state is JobState.printing
    assert job.job_id == "bracket.gcode.3mf"
    assert fake.mqtt_stopped is True  # the session never leaks


def test_send_honors_the_external_spool_setting(tmp_path):
    fake = FakePrinter()
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    _connector(fake, use_ams=False).send(f, confirm=True)
    assert fake.started_with[2] is False


def test_send_refuses_while_a_job_is_running(tmp_path):
    """Busy is a soft, typed outcome — and nothing is uploaded over the live job."""
    fake = FakePrinter(state="RUNNING")
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(ConnectorError) as ei:
        _connector(fake).send(f, confirm=True)
    assert ei.value.reason == "busy"
    assert fake.uploaded is None
    assert fake.mqtt_stopped is True


def test_send_treats_a_swallowed_upload_failure_as_not_sent(tmp_path):
    """ENG-001 (slice-10.3 audit): the library's FTP layer can swallow a mid-transfer failure
    and return None — without the 226 transfer-complete proof, the job must NOT be started or
    narrated as sent."""
    fake = FakePrinter()
    fake.upload_file = lambda file, filename: None  # the decorator ate the exception
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(ConnectorError) as ei:
        _connector(fake).send(f, confirm=True)
    assert "didn't finish uploading" in ei.value.user_message
    assert fake.started_with is None  # start_print never fired on an unproven upload
    assert fake.mqtt_stopped is True


def test_mqtt_stops_even_when_the_upload_raises(tmp_path):
    def _boom(file, filename):
        raise OSError("connection reset")

    fake = FakePrinter()
    fake.upload_file = _boom
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(ConnectorError):
        _connector(fake).send(f, confirm=True)
    assert fake.mqtt_stopped is True  # the session never leaks, even on the failure path


def test_send_refuses_a_multi_plate_file(tmp_path):
    """ENG-003: starting is by plate and KimCad starts plate 1 — a multi-plate file must be
    refused, never silently printed wrong."""
    p = tmp_path / "multi.gcode.3mf"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X10 Y10 E1\n")
        zf.writestr("Metadata/plate_2.gcode", "G28\nG1 X5 Y5 E1\n")
    fake = FakePrinter()
    with pytest.raises(ConnectorError) as ei:
        _connector(fake).send(p, confirm=True)
    assert "more than one plate" in ei.value.user_message
    assert fake.uploaded is None


def test_job_status_survives_a_non_numeric_percentage():
    fake = FakePrinter(state="RUNNING")
    fake.percentage = "Unknown"  # the library types get_percentage as int | str | None
    job = _connector(fake).job_status("p.gcode.3mf")
    assert job.state is JobState.printing
    assert job.progress == 0.0  # unparseable progress reads as 0, never a crash


def test_send_surfaces_a_refused_start_with_a_next_step(tmp_path):
    fake = FakePrinter(start_ok=False)
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(ConnectorError) as ei:
        _connector(fake).send(f, confirm=True)
    assert "printer's screen" in ei.value.user_message


def test_send_reports_an_unreachable_printer_as_offline_not_a_crash(tmp_path):
    from kimcad.printer_connector import PrinterOffline

    fake = FakePrinter(ready_after=999)  # never answers within the 1s test timeout
    f = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(PrinterOffline) as ei:
        _connector(fake).send(f, confirm=True)
    assert "access code" in ei.value.user_message  # the LAN checklist, not a stack trace
    assert fake.mqtt_stopped is True


# --- status / job_status ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("bambu_state", "expected"),
    [
        ("IDLE", PrinterState.operational),
        ("FINISH", PrinterState.operational),
        ("PREPARE", PrinterState.printing),
        ("RUNNING", PrinterState.printing),
        ("PAUSE", PrinterState.paused),
        ("FAILED", PrinterState.error),
        ("UNKNOWN", PrinterState.error),  # unknown beats wrong — never shown as ready
    ],
)
def test_status_maps_every_gcode_state(bambu_state, expected):
    st = _connector(FakePrinter(state=bambu_state)).status()
    assert st.online is True
    assert st.state is expected


def test_status_carries_temperatures():
    st = _connector(FakePrinter()).status()
    assert st.nozzle_temp_c == 219.5
    assert st.bed_temp_c == 55.0


def test_status_reports_offline_as_a_snapshot_not_an_exception():
    st = _connector(FakePrinter(ready_after=999)).status()
    assert st.online is False
    assert st.state is PrinterState.offline


def test_job_status_progress_and_done():
    fake = FakePrinter(state="RUNNING")
    job = _connector(fake).job_status("p.gcode.3mf")
    assert job.state is JobState.printing
    assert job.progress == 0.42
    fake.state_name = "FINISH"
    job = _connector(fake).job_status("p.gcode.3mf")
    assert job.state is JobState.done
    assert job.progress == 1.0


def test_capabilities_reports_nozzle_and_never_guesses_build_volume():
    caps = _connector(FakePrinter()).capabilities()
    assert caps.nozzle_diameter_mm == 0.4
    assert caps.build_volume_mm is None  # not reported over MQTT — config stays authoritative


# --- the factory + graceful absence ------------------------------------------------------


def _cfg(connector: dict) -> Config:
    return Config({"connectors": {"bambu_p2s": connector}})


_FULL = {
    "type": "bambu",
    "base_url": "http://192.168.0.60",
    "serial": "01S00C123",
    "api_key_env": "KIMCAD_TEST_BAMBU_CODE",
}


def test_build_connector_without_the_package_is_an_actionable_config_gap(monkeypatch):
    monkeypatch.setattr(connectors, "bambulabs_api_available", lambda: False)
    monkeypatch.setenv("KIMCAD_TEST_BAMBU_CODE", "12345678")
    cfg = _cfg(_FULL)
    with pytest.raises(ConnectorError) as ei:
        build_connector(cfg, "bambu_p2s")
    assert ei.value.reason == "config"
    assert "pip install bambulabs-api" in ei.value.user_message
    assert connector_is_configured(cfg, "bambu_p2s") is False  # the UI label follows


def test_build_connector_reports_each_missing_piece_distinctly(monkeypatch):
    monkeypatch.setattr(connectors, "bambulabs_api_available", lambda: True)
    monkeypatch.setenv("KIMCAD_TEST_BAMBU_CODE", "12345678")
    with pytest.raises(ConnectorError, match="base_url"):
        build_connector(_cfg({**_FULL, "base_url": None}), "bambu_p2s")
    with pytest.raises(ConnectorError, match="serial"):
        build_connector(_cfg({**_FULL, "serial": None}), "bambu_p2s")
    monkeypatch.delenv("KIMCAD_TEST_BAMBU_CODE")
    with pytest.raises(ConnectorError) as ei:
        build_connector(_cfg(_FULL), "bambu_p2s")
    assert "access code" in ei.value.user_message.lower()


def test_build_connector_parses_a_host_from_url_forms(monkeypatch):
    monkeypatch.setattr(connectors, "bambulabs_api_available", lambda: True)
    monkeypatch.setenv("KIMCAD_TEST_BAMBU_CODE", "12345678")
    for base in ("http://192.168.0.60", "192.168.0.60", "http://192.168.0.60:8883/x"):
        conn = build_connector(_cfg({**_FULL, "base_url": base}), "bambu_p2s")
        assert isinstance(conn, BambuConnector)
        assert conn._host == "192.168.0.60"
    assert conn.drives_hardware is True


def test_bambu_is_never_labeled_simulated():
    cfg = _cfg(_FULL)
    assert connector_is_simulated(cfg.connector_config("bambu_p2s")) is False


def test_default_yaml_ships_bambu_visible_but_unconfigured():
    """The shipped templates appear in the picker disabled-with-reason, and can never be
    'configured' by accident (no IP/serial filled in)."""
    cfg = Config.load()
    assert "bambu_p2s" in cfg.connectors()
    assert "bambu_a1" in cfg.connectors()
    assert connector_is_configured(cfg, "bambu_p2s") is False
    assert connector_is_configured(cfg, "bambu_a1") is False
    # And the default connector (config order) is still the loopback mock, not a Bambu.
    assert next(iter(cfg.connectors())) == "mock"
