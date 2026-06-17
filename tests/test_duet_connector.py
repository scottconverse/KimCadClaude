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


def test_malicious_job_name_is_sanitized_before_the_m32_command(tmp_path):
    # A job name with a quote/newline/slash must NOT break the M32 "0:…" quoting or inject a
    # second rr_gcode command — the upload name is reduced to safe chars.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet(step=40.0) as (base, state):
        job = _connector(base).send(g, confirm=True, job_name='evil"\nM112 /../boom')
        assert job.job_id == "evilM112boom.gcode"  # quotes/newlines/slashes/dots stripped
        assert state["files"] == ["/gcodes/evilM112boom.gcode"]


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


# --- KC-21 audit remediation (#26) --------------------------------------------

def test_send_uploads_the_exact_gcode_bytes(tmp_path):
    gcode = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n"
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf", gcode=gcode)
    with serve_mock_duet() as (base, state):
        _connector(base).send(g, confirm=True)
    assert state["uploaded_body"] == gcode.encode()  # TE-06: the real bytes, not just "an upload"


def test_session_is_released_so_repeated_polls_never_exhaust(tmp_path):
    # ENG-003/QA-4: with a password the connector opens AND closes a session per op, so a finite
    # session table (cap 2) is never exhausted across many polls — no false "busy".
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet(password="pw", session_cap=2) as (base, state):
        c = DuetConnector(base, "pw", name="mock-duet")
        c.send(g, confirm=True)
        for _ in range(10):
            assert c.status().online is True
            c.job_status("x")
    assert state["sessions"] == 0          # every session was released
    assert state["max_sessions_seen"] <= 1  # never more than one open at a time


def test_upload_without_err0_is_a_failure_not_a_silent_start(monkeypatch, tmp_path):
    # ENG-007: a 200 with no `err` key (or err!=0) must be treated as a FAILED upload — never start.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet() as (base, _state):
        c = _connector(base)
        monkeypatch.setattr(c, "_post_upload", lambda *a, **k: {})  # no err key
        with pytest.raises(ConnectorError, match="rejected the upload"):
            c.send(g, confirm=True)


def test_m32_failure_is_not_reported_as_a_printing_job(monkeypatch, tmp_path):
    # QA-1: if rr_gcode/M32 returns a non-zero err, the start was refused — don't report printing.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet() as (base, _state):
        c = _connector(base)
        orig = c._get_json
        monkeypatch.setattr(
            c, "_get_json", lambda path: {"err": 1} if "rr_gcode" in path else orig(path)
        )
        with pytest.raises(ConnectorError, match="refused the print start"):
            c.send(g, confirm=True)


def test_temps_parsing_tolerates_rrf_shape_variance():
    # ENG-006: bed may be a dict, a number, or a list; current is [bed, tool0, ...].
    assert DuetConnector._temps({"temps": {"bed": {"current": 55.0}, "current": [55.0, 205.0]}}) == (205.0, 55.0)
    assert DuetConnector._temps({"temps": {"bed": 50.0, "current": [50.0, 200.0]}}) == (200.0, 50.0)
    assert DuetConnector._temps({"temps": {"current": [48.0, 198.0]}}) == (198.0, 48.0)
    assert DuetConnector._temps({"temps": {}}) == (None, None)


@pytest.mark.parametrize("char,expected", [("S", JobState.paused), ("A", JobState.paused),
                                           ("H", JobState.error), ("F", JobState.error)])
def test_job_status_maps_paused_and_halted_states(char, expected):
    with serve_mock_duet() as (base, state):
        state["status"] = char
        job = _connector(base).job_status("x")
    assert job.state is expected


@pytest.mark.parametrize("method", ["status", "job_status"])
def test_disconnect_runs_when_status_blips_offline_after_connect(method):
    # ENG-003: a transient URLError AFTER a successful _connect() must still release the RRF
    # session (try/finally), or repeated polling through flaky Wi-Fi exhausts the board's
    # small session table and locks the user out of their own printer.
    import urllib.error

    c = _connector("http://x", password="pw")  # a password => a session is opened
    connects: list[int] = []
    disconnects: list[int] = []

    def fake_get_json(path: str):
        if "rr_connect" in path:
            connects.append(1)
            return {"err": 0}  # _connect() succeeds and opens a session
        raise urllib.error.URLError("mid-poll blip")  # _status_json then fails transiently

    # _connect/_disconnect run their real logic; only the transport raises. _disconnect() calls
    # self._request directly (not _get_json), so stub that to record the session release.
    def fake_request(meth, path, *, data=None):
        if "rr_disconnect" in path:
            disconnects.append(1)
            return 200, b"{}"
        raise AssertionError("only rr_disconnect should reach _request in this test")

    c._get_json = lambda path: fake_get_json(path)  # type: ignore[method-assign]
    c._request = fake_request  # type: ignore[method-assign]

    result = getattr(c, method)("job") if method == "job_status" else getattr(c, method)()

    assert connects == [1]                 # the session WAS opened
    assert disconnects == [1]              # ...and released on the offline path (the leak fix)
    if method == "status":
        assert result.online is False and result.state is PrinterState.offline
    else:
        assert result.state is JobState.error
        # ENG-009: a clean fixed detail, not the raw URLError text.
        assert result.detail == "could not reach the printer"
        assert "URLError" not in result.detail and "blip" not in result.detail


def test_done_is_latched_after_progress_then_idle(tmp_path):
    # ENG-004/TE-01/TE-02: RRF clears fractionPrinted on completion, so done is detected by the
    # LATCH (progress seen -> later idle == done), and a poll past done never regresses to queued.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with serve_mock_duet(step=40.0) as (base, _state):
        c = _connector(base)
        job = c.send(g, confirm=True)
        last = None
        for _ in range(6):
            last = c.job_status(job.job_id)
            if last.state is JobState.done:
                break
        assert last.state is JobState.done and last.progress == 1.0
        assert c.job_status(job.job_id).state is JobState.done  # poll past done stays done
