"""Tests for the PrusaLink (Prusa) connector against the mock PrusaLink server (Stage 3)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.mock_prusalink import DEFAULT_API_KEY, serve_mock_prusalink
from kimcad.printer_connector import (
    AuthError,
    ConnectorError,
    JobState,
    NotConfirmed,
    PrinterOffline,
    PrinterState,
)
from kimcad.prusalink_connector import PrusaLinkConnector


def _write_gcode_3mf(path: Path, *, gcode: str = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", gcode)
    return path


def _connector(base_url: str, *, key: str = DEFAULT_API_KEY) -> PrusaLinkConnector:
    return PrusaLinkConnector(base_url, key, name="mock-prusa")


def test_prusalink_drives_hardware():
    assert PrusaLinkConnector("http://x", "k").drives_hardware is True


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


# --- against the mock PrusaLink server ----------------------------------------


def test_capabilities_from_info():
    with serve_mock_prusalink() as (base, _state):
        caps = _connector(base).capabilities()
    assert caps.nozzle_diameter_mm == 0.4
    assert caps.build_volume_mm is None  # PrusaLink /api/v1/info doesn't report build volume
    assert caps.materials is None


def test_status_operational_when_idle():
    with serve_mock_prusalink() as (base, _state):
        st = _connector(base).status()
    assert st.online and st.state is PrinterState.operational
    assert st.nozzle_temp_c == 25.0


def test_send_uploads_and_starts_then_job_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "part.gcode.3mf")
    with serve_mock_prusalink(step=40.0) as (base, state):
        c = _connector(base)
        job = c.send(g, confirm=True, job_name="bracket")
        assert job.state is JobState.printing
        assert state["files"] == ["bracket.gcode"]  # uploaded via PUT as a flat .gcode
        assert state["printing"] is True
        last = c.job_status(job.job_id)
        assert last.state is JobState.printing and 0.0 < last.progress <= 1.0
        for _ in range(6):
            last = c.job_status(job.job_id)
            if last.state is JobState.done:
                break
        assert last.state is JobState.done and last.progress == 1.0


def test_send_while_printing_is_busy_conflict(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink(step=5.0) as (base, _state):
        c = _connector(base)
        c.send(g, confirm=True)  # now printing
        with pytest.raises(ConnectorError, match="busy") as exc:
            c.send(g, confirm=True)  # PrusaLink returns 409 while printing
        assert exc.value.reason == "busy"  # QA-005: typed reason enables a "retry when idle" UI


def test_wrong_api_key_is_auth_error_not_offline(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink(api_key="the-real-key") as (base, _state):
        c = _connector(base, key="wrong-key")
        with pytest.raises(AuthError, match="HTTP 401"):
            c.send(g, confirm=True)
        st = c.status()
        assert st.online is True and st.state is PrinterState.error


def test_capabilities_wrong_api_key_is_auth_error():
    with serve_mock_prusalink(api_key="the-real-key") as (base, _state):
        with pytest.raises(AuthError, match="HTTP 401"):
            _connector(base, key="nope").capabilities()


def test_capabilities_offline_raises_printer_offline():
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").capabilities()


def test_job_status_http_error_is_error_not_unreachable():
    with serve_mock_prusalink(api_key="the-real-key") as (base, _state):
        job = _connector(base, key="wrong").job_status("x")
    assert job.state is JobState.error
    assert "HTTP 401" in job.detail and "unreachable" not in job.detail


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
    secret = "prusa-secret-leak-me-4d1a"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink(api_key="the-real-key") as (base, _state):
        c = _connector(base, key=secret)
        with pytest.raises(AuthError) as exc:
            c.send(g, confirm=True)
        assert secret not in str(exc.value)


# --- state mapping (every PrusaLink state -> our normalized enum) --------------


@pytest.mark.parametrize(
    "prusa_state,expected",
    [
        ("IDLE", PrinterState.operational),
        ("READY", PrinterState.operational),
        ("FINISHED", PrinterState.operational),
        ("PRINTING", PrinterState.printing),
        ("BUSY", PrinterState.printing),
        ("PAUSED", PrinterState.paused),
        ("ATTENTION", PrinterState.error),  # needs-attention is NOT "ready"
        ("ERROR", PrinterState.error),
        ("WAT-FUTURE-STATE", PrinterState.error),  # unknown beats wrong: error, not "ready"
    ],
)
def test_status_state_mapping(prusa_state, expected):
    with serve_mock_prusalink() as (base, state):
        state["printing"] = False  # don't let the poll advance/override the state
        state["printer_state"] = prusa_state
        st = _connector(base).status()
    assert st.state is expected


@pytest.mark.parametrize(
    "prusa_state,expected",
    [
        ("FINISHED", JobState.done),
        ("STOPPED", JobState.cancelled),
        ("PAUSED", JobState.paused),
        ("ATTENTION", JobState.error),
        ("ERROR", JobState.error),
        ("PRINTING", JobState.printing),
        ("IDLE", JobState.queued),
    ],
)
def test_job_status_state_mapping(prusa_state, expected):
    with serve_mock_prusalink() as (base, state):
        state["printing"] = False
        state["printer_state"] = prusa_state
        state["filename"] = "x.gcode"
        job = _connector(base).job_status("x")
    assert job.state is expected


def test_status_temps_while_printing(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink() as (base, _state):
        c = _connector(base)
        c.send(g, confirm=True)  # now printing
        st = c.status()
    assert st.state is PrinterState.printing
    assert st.nozzle_temp_c == 215.0 and st.bed_temp_c == 60.0


# --- ENG-002: a job name with a space / # is percent-encoded and round-trips --------------


def test_upload_filename_is_percent_encoded(tmp_path):
    # The PrusaLink upload puts the filename in the URL path; a space/#/? must be percent-encoded
    # so the request target is well-formed and the server's unquote recovers the real name.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink() as (base, state):
        _connector(base).send(g, confirm=True, job_name="a b#c")
    assert state["files"] == ["a b#c.gcode"]


def test_upload_filename_encodes_non_ascii(tmp_path):
    # TEST-R2-003: a non-ASCII job name is percent-encoded (UTF-8) and round-trips through the
    # server's unquote — a unicode name must not corrupt the request target.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_prusalink() as (base, state):
        _connector(base).send(g, confirm=True, job_name="café-Ω-part")
    assert state["files"] == ["café-Ω-part.gcode"]


# --- QA-001: a garbage HTTP-200 body degrades to an error STATUS, never a raw traceback ----


def test_status_garbage_200_is_error_not_raise(monkeypatch):
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"<html>not json</html>"))
    st = c.status()
    assert st.state is PrinterState.error and st.online is True


def test_job_status_garbage_200_is_error(monkeypatch):
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"<html>not json</html>"))
    assert c.job_status("x").state is JobState.error


def test_capabilities_garbage_200_raises_clean_error(monkeypatch):
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"not json"))
    with pytest.raises(ConnectorError) as exc:
        c.capabilities()
    assert exc.value.reason == "bad_response"


# --- ENG-005: a 5xx means the server is faulted, reported as NOT online --------------------


def test_status_5xx_reports_not_online(monkeypatch):
    import urllib.error

    c = _connector("http://x")

    def _boom(*a, **k):
        raise urllib.error.HTTPError("http://x/status", 502, "no upstream", {}, None)

    monkeypatch.setattr(c, "_request", _boom)
    st = c.status()
    assert st.online is False and st.state is PrinterState.error


# --- ENG-007: the mock 409s a duplicate filename unless Overwrite is set -------------------


def test_mock_409s_duplicate_filename_without_overwrite():
    import urllib.error
    import urllib.request

    def _put(base, name, *, overwrite):
        headers = {"Content-Type": "application/octet-stream"}
        if overwrite:
            headers["Overwrite"] = "?1"
        req = urllib.request.Request(
            f"{base}/api/v1/files/usb/{name}", data=b"G1 X1\n", method="PUT", headers=headers
        )
        return urllib.request.urlopen(req, timeout=10).status

    with serve_mock_prusalink(api_key=None) as (base, _state):
        assert _put(base, "dup.gcode", overwrite=False) == 201  # first upload
        with pytest.raises(urllib.error.HTTPError) as exc:
            _put(base, "dup.gcode", overwrite=False)  # duplicate, no Overwrite -> 409
        assert exc.value.code == 409
        assert _put(base, "dup.gcode", overwrite=True) == 201  # Overwrite replaces it
        # The connector always sends Overwrite: ?1, so a real re-send round-trips (asserted via
        # the connector path elsewhere); this exercises the mock's conformance to the API.


def test_status_no_printer_block_is_error(monkeypatch):
    # ENG-003: a reachable device answering 200 with no `printer` block (wrong device) reports
    # an error status, not a false "ready."
    c = _connector("http://x")
    monkeypatch.setattr(c, "_request", lambda *a, **k: (200, b"{}"))
    assert c.status().state is PrinterState.error


def test_large_upload_with_wrong_key_is_auth_not_offline(tmp_path):
    # TEST-001 / ENG-001: a bad key on a LARGE upload surfaces as a mid-write reset (not an
    # HTTPError) — the connector must still report AuthError. The deterministic probe-logic proof
    # is in test_connectors.py; this is the PrusaLink end-to-end analogue of the Moonraker one.
    big = "G28\n" + "G1 X1 Y1 E1\n" * 320_000  # ~4 MB of motion-bearing G-code
    g = _write_gcode_3mf(tmp_path / "big.gcode.3mf", gcode=big)
    with serve_mock_prusalink(api_key="the-real-key") as (base, _state):
        c = _connector(base, key="wrong-key")
        with pytest.raises(AuthError):
            c.send(g, confirm=True)
