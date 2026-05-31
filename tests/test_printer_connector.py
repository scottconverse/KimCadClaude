"""Tests for the send-to-printer connector abstraction (Stage 2, Slice 1)."""

import zipfile
from pathlib import Path

import pytest

from kimcad.printer_connector import (
    ConnectorError,
    JobState,
    LoopbackConnector,
    NotConfirmed,
    PrinterCapabilities,
    PrinterConnector,
    PrinterOffline,
    PrinterState,
    ensure_sendable,
)


def _write_gcode_3mf(
    path: Path, *, gcode: str | None = "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n"
) -> Path:
    """A minimal but structurally-real G-code-bearing 3MF (zip with an embedded plate).
    ``gcode=None`` writes a 3MF with NO .gcode member (a valid zip that isn't a slice)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("3D/3dmodel.model", "<model/>")
        if gcode is not None:
            zf.writestr("Metadata/plate_1.gcode", gcode)
    return path


# --- the confirmation + proof gate (ensure_sendable) --------------------------


def test_send_without_confirmation_is_refused(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(NotConfirmed):
        ensure_sendable(g, confirm=False)


def test_send_with_truthy_but_non_true_confirm_is_refused(tmp_path):
    # confirm must be exactly True — a truthy value (e.g. "yes") is not an explicit confirm.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(NotConfirmed):
        ensure_sendable(g, confirm="yes")  # type: ignore[arg-type]


def test_send_rejects_missing_file(tmp_path):
    with pytest.raises(ConnectorError, match="not found"):
        ensure_sendable(tmp_path / "nope.gcode.3mf", confirm=True)


def test_send_rejects_non_printable_file(tmp_path):
    bad = tmp_path / "bad.gcode.3mf"
    bad.write_bytes(b"not a zip, not a slice")
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        ensure_sendable(bad, confirm=True)


def test_send_rejects_valid_zip_with_no_gcode_member(tmp_path):
    # A realistic bad input: a valid 3MF (zip) that carries no toolpath member.
    no_member = _write_gcode_3mf(tmp_path / "nomember.gcode.3mf", gcode=None)
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        ensure_sendable(no_member, confirm=True)


def test_send_rejects_valid_gcode_with_no_motion(tmp_path):
    # A valid 3MF with a .gcode member but only setup/homing — nothing would print.
    motionless = _write_gcode_3mf(
        tmp_path / "motionless.gcode.3mf", gcode="; header\nM104 S210\nG28\nG92 E0\n"
    )
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        ensure_sendable(motionless, confirm=True)


def test_ensure_sendable_passes_a_real_slice(tmp_path):
    g = _write_gcode_3mf(tmp_path / "ok.gcode.3mf")
    ensure_sendable(g, confirm=True)  # does not raise


# --- LoopbackConnector implements the contract --------------------------------


def test_loopback_satisfies_the_protocol():
    c = LoopbackConnector()
    assert isinstance(c, PrinterConnector)
    # runtime_checkable only checks attribute presence, so also verify the four contract
    # methods are actually callable (the behavioral tests below carry the real contract).
    for m in ("capabilities", "status", "send", "job_status"):
        assert callable(getattr(c, m)), m


def test_loopback_capabilities_and_status():
    c = LoopbackConnector(name="mock")
    caps = c.capabilities()
    assert isinstance(caps, PrinterCapabilities)
    assert caps.name == "mock" and caps.nozzle_diameter_mm == 0.4
    st = c.status()
    assert st.online and st.state == "operational"


def test_loopback_send_requires_confirmation(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    with pytest.raises(NotConfirmed):
        LoopbackConnector().send(g, confirm=False)


def test_loopback_send_rejects_non_slice(tmp_path):
    # The proof gate fires through send(), not only ensure_sendable() directly.
    bad = tmp_path / "bad.gcode.3mf"
    bad.write_bytes(b"not a slice")
    with pytest.raises(ConnectorError, match="isn't a printable slice"):
        LoopbackConnector().send(bad, confirm=True)


def test_loopback_send_then_status_flows_to_done(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    c = LoopbackConnector(polls_to_done=3)
    job = c.send(g, confirm=True, job_name="my-part")
    assert job.state is JobState.queued and job.progress == 0.0
    assert job.job_id

    # a queued (non-terminal) job means the printer reports busy
    assert c.status().state is PrinterState.printing

    p1 = c.job_status(job.job_id)  # queued -> printing, first frame progress 0.0
    assert p1.state is JobState.printing and p1.progress == 0.0
    p2 = c.job_status(job.job_id)  # printing, progress climbs but isn't done yet
    assert p2.state is JobState.printing and 0.0 < p2.progress < 1.0
    p3 = c.job_status(job.job_id)  # done
    assert p3.state is JobState.done and p3.progress == 1.0
    assert JobState.done.terminal

    # idempotent at terminal, and the printer is operational again afterward
    assert c.job_status(job.job_id).state is JobState.done
    assert c.status().state is PrinterState.operational


def test_loopback_polls_to_done_is_clamped_to_have_a_printing_frame(tmp_path):
    # polls_to_done=1 is clamped to 2 so there is always at least one printing frame
    # before done (no instant queued->done that skips printing).
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    c = LoopbackConnector(polls_to_done=1)
    job = c.send(g, confirm=True)
    assert c.job_status(job.job_id).state is JobState.printing
    assert c.job_status(job.job_id).state is JobState.done


def test_loopback_offline_send_raises(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    c = LoopbackConnector(online=False)
    assert c.status().online is False
    with pytest.raises(PrinterOffline):
        c.send(g, confirm=True)


def test_loopback_unknown_job_raises():
    with pytest.raises(ConnectorError, match="unknown job"):
        LoopbackConnector().job_status("does-not-exist")


# --- TEST-004: the lock the docstring promises actually holds under concurrency -----------


def test_loopback_concurrent_sends_get_distinct_jobs(tmp_path):
    import threading

    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    c = LoopbackConnector()
    ids: list[str] = []
    ids_lock = threading.Lock()
    barrier = threading.Barrier(12)

    def one() -> None:
        barrier.wait()  # maximize the chance of a real race on _counter/_jobs
        job = c.send(g, confirm=True)
        with ids_lock:
            ids.append(job.job_id)

    threads = [threading.Thread(target=one) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(ids) == 12
    assert len(set(ids)) == 12  # no two sends collided on a job id
    assert len(c._jobs) == 12  # and none was lost to a lost update


# --- UX-001: connectors self-describe whether they drive real hardware --------------------


def test_loopback_is_marked_simulated():
    assert LoopbackConnector().drives_hardware is False
