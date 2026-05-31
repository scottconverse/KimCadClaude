"""Tests for the OctoPrint connector against the mock OctoPrint server (Stage 2, Slice 2)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.mock_printer import DEFAULT_API_KEY, serve_mock_octoprint
from kimcad.octoprint_connector import OctoPrintConnector
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


def _connector(base_url: str, *, key: str = DEFAULT_API_KEY) -> OctoPrintConnector:
    return OctoPrintConnector(base_url, key, name="mock-octo")


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


# --- against the mock OctoPrint server ----------------------------------------


def test_capabilities_from_printer_profile():
    with serve_mock_octoprint() as (base, _state):
        caps = _connector(base).capabilities()
    assert caps.build_volume_mm == (250.0, 210.0, 210.0)
    assert caps.nozzle_diameter_mm == 0.4
    assert caps.name == "Mock Printer"


def test_status_operational_when_idle():
    with serve_mock_octoprint() as (base, _state):
        st = _connector(base).status()
    assert st.online and st.state is PrinterState.operational
    assert st.nozzle_temp_c == 25.0


def test_send_uploads_and_starts_then_status_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "part.gcode.3mf")
    with serve_mock_octoprint(step=40.0) as (base, state):
        c = _connector(base)
        job = c.send(g, confirm=True, job_name="bracket")
        assert job.state is JobState.printing
        # the mock recorded the uploaded .gcode and started a job
        assert state["files"] == ["bracket.gcode"]
        assert state["job"]["name"] == "bracket.gcode"
        # printer reports printing while the job is active
        assert c.status().state is PrinterState.printing
        # progress climbs to done over polls (mock advances 40% per /api/job poll)
        p1 = c.job_status(job.job_id)
        assert p1.state is JobState.printing and 0.0 < p1.progress < 1.0
        c.job_status(job.job_id)
        p3 = c.job_status(job.job_id)
        assert p3.state is JobState.done and p3.progress == 1.0
        # printer is operational again once the job completed
        assert c.status().state is PrinterState.operational


def test_wrong_api_key_is_auth_error_not_offline(tmp_path):
    # A bad key is reachable-but-rejected: AuthError on send, and status() reports an
    # error state (online), NOT offline (which means unreachable).
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_octoprint(api_key="the-real-key") as (base, _state):
        c = _connector(base, key="wrong-key")
        with pytest.raises(AuthError, match="HTTP 403"):
            c.send(g, confirm=True)
        st = c.status()
        assert st.online is True and st.state is PrinterState.error


def test_send_rejects_multi_plate_archive(tmp_path):
    p = tmp_path / "multi.gcode.3mf"
    p.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X1 Y1 E1\n")
        zf.writestr("Metadata/plate_2.gcode", "G28\nG1 X2 Y2 E1\n")
    with pytest.raises(ConnectorError, match="plates"):
        _connector("http://127.0.0.1:1").send(p, confirm=True)


def test_job_status_queued_when_no_job():
    with serve_mock_octoprint() as (base, _state):
        # no send yet -> OctoPrint reports completion None
        job = _connector(base).job_status("nothing")
    assert job.state is JobState.queued


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


def test_job_status_http_error_is_error_not_unreachable():
    # A 401/403 on job_status is reachable-but-rejected — reported as the HTTP code, NOT
    # mislabeled "unreachable" (HTTPError must be caught before its URLError superclass).
    with serve_mock_octoprint(api_key="the-real-key") as (base, _state):
        job = _connector(base, key="wrong-key").job_status("x")
    assert job.state is JobState.error
    assert "HTTP 403" in job.detail and "unreachable" not in job.detail


# --- the mock server's own negative paths -------------------------------------


def test_mock_rejects_upload_with_no_file():
    import urllib.error
    import urllib.request

    with serve_mock_octoprint() as (base, _state):
        req = urllib.request.Request(
            base + "/api/files/local",
            data=b"no multipart here",
            method="POST",
            headers={"X-Api-Key": DEFAULT_API_KEY, "Content-Type": "text/plain"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=10)
        assert exc.value.code == 400


def test_mock_cancel_clears_the_job(tmp_path):
    import json
    import urllib.request

    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_octoprint() as (base, state):
        _connector(base).send(g, confirm=True)
        assert state["job"] is not None
        req = urllib.request.Request(
            base + "/api/job",
            data=json.dumps({"command": "cancel"}).encode(),
            method="POST",
            headers={"X-Api-Key": DEFAULT_API_KEY, "Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        assert resp.status == 204
    assert state["job"] is None


# --- TEST-002: capabilities() auth + offline branches (were tested on send/status only) ---


def test_capabilities_wrong_api_key_is_auth_error():
    with serve_mock_octoprint(api_key="the-real-key") as (base, _state):
        with pytest.raises(AuthError, match="HTTP 403"):
            _connector(base, key="wrong-key").capabilities()


def test_capabilities_offline_raises_printer_offline():
    with pytest.raises(PrinterOffline):
        _connector("http://127.0.0.1:1").capabilities()


# --- ENG-203: an OctoPrint that doesn't report materials yields None (unknown), not () ---


def test_capabilities_materials_unknown_is_none():
    with serve_mock_octoprint() as (base, _state):
        caps = _connector(base).capabilities()
    assert caps.materials is None  # OctoPrint's profile endpoint doesn't report loaded materials


# --- ENG-206: no _default + several profiles -> decline (unknown beats guessing) ----------


def test_capabilities_multiple_profiles_no_default_is_unknown(monkeypatch):
    c = _connector("http://127.0.0.1:1")
    monkeypatch.setattr(
        c,
        "_get_json",
        lambda path: {
            "profiles": {
                "a": {"name": "A", "volume": {"width": 100, "depth": 100, "height": 100}},
                "b": {"name": "B", "volume": {"width": 300, "depth": 300, "height": 300}},
            }
        },
    )
    caps = c.capabilities()
    assert caps.build_volume_mm is None and caps.nozzle_diameter_mm is None


def test_capabilities_single_profile_no_default_is_used(monkeypatch):
    c = _connector("http://127.0.0.1:1")
    monkeypatch.setattr(
        c,
        "_get_json",
        lambda path: {
            "profiles": {"only": {"name": "Only", "volume": {"width": 220, "depth": 220, "height": 250}}}
        },
    )
    caps = c.capabilities()
    assert caps.build_volume_mm == (220.0, 220.0, 250.0)


# --- TEST-003: the upload-side size cap is a DIFFERENT guard from the proof gate's --------


def test_extract_gcode_refuses_oversize_member(tmp_path, monkeypatch):
    # Shrink ONLY the shared extractor's cap (not the proof gate's, which lives on slicer.*),
    # so the file proves out as a real slice but the upload-side guard fires.
    # extract_single_plate_gcode runs after ensure_sendable and before any network.
    g = _write_gcode_3mf(tmp_path / "big.gcode.3mf", gcode="G28\n" + "G1 X1 Y1 E1\n" * 50)
    monkeypatch.setattr("kimcad.printer_connector.MAX_GCODE_MEMBER_BYTES", 10)
    with pytest.raises(ConnectorError, match="too large"):
        _connector("http://127.0.0.1:1").send(g, confirm=True)


# --- ENG-202: a rejection surfaces OctoPrint's own reason, not just the HTTP code ---------


def test_http_error_detail_surfaces_octoprint_reason():
    import io
    import urllib.error

    from kimcad.octoprint_connector import _http_error_detail

    e = urllib.error.HTTPError(
        "http://x/api/files/local", 409, "Conflict", {}, io.BytesIO(b'{"error": "Printer is busy"}')
    )
    assert _http_error_detail(e) == " — Printer is busy"


# --- TEST-005: the API key is never echoed in an error message --------------------------


def test_api_key_never_appears_in_error(tmp_path):
    secret = "super-secret-leak-me-9f3a"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_octoprint(api_key="the-real-key") as (base, _state):
        c = _connector(base, key=secret)
        with pytest.raises(AuthError) as exc:
            c.send(g, confirm=True)
        assert secret not in str(exc.value)
        with pytest.raises(AuthError) as exc2:
            c.capabilities()
        assert secret not in str(exc2.value)


# --- UX-003: a typed user_message / reason rides on the connector errors -----------------


def test_auth_error_carries_reason_and_user_message():
    with serve_mock_octoprint(api_key="the-real-key") as (base, _state):
        try:
            _connector(base, key="nope").capabilities()
            raise AssertionError("expected AuthError")
        except AuthError as e:
            assert e.reason == "auth"
            assert "API key" in e.user_message
