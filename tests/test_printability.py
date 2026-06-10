"""TEST-005 (2026-06-09 audit): close the upstream seam — the gate's behavioral tests in
test_geometry.py feed it HAND-BUILT MeshReports, so a regression in how validate_mesh
COMPUTES a report (bbox, body counts, watertightness) would pass those tests while the
gate faithfully processed wrong numbers. These cases run real trimesh geometry through
``validate_mesh`` → ``run_gate`` end to end, so the seam itself is under test."""

from __future__ import annotations

import pytest

trimesh = pytest.importorskip("trimesh")
np = pytest.importorskip("numpy")

from conftest import BAMBU, PLA, make_plan  # noqa: E402

from kimcad.printability import Level, run_gate  # noqa: E402
from kimcad.validation import validate_mesh  # noqa: E402


def _gate(mesh, plan):
    repaired, report = validate_mesh(mesh)
    return report, run_gate(report, plan, BAMBU, PLA)


def _codes(result):
    return {f.code: f.level for f in result.findings}


def test_clean_box_computes_real_report_and_passes():
    mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    report, result = _gate(mesh, make_plan([20, 20, 20]))
    # The report's numbers come from real geometry, not a fixture.
    assert report.watertight is True
    assert report.n_bodies == 1 and report.stray_bodies == 0
    assert report.bounding_box_mm == pytest.approx((20.0, 20.0, 20.0))
    assert report.volume_mm3 == pytest.approx(8000.0, rel=1e-6)
    assert result.status is Level.PASS


def test_real_oversized_mesh_fails_build_volume():
    # Bambu P2S build volume is 256^3; a 300mm-long real mesh must FAIL, with the
    # failure driven by the COMPUTED bbox (the plan agrees, so dimensions pass).
    mesh = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    report, result = _gate(mesh, make_plan([300, 20, 20]))
    assert report.bounding_box_mm[0] == pytest.approx(300.0)
    assert result.status is Level.FAIL
    assert _codes(result).get("volume.exceeds") is Level.FAIL


def test_real_stray_bodies_warn_but_hollow_cavity_does_not():
    # Two solids sitting APART: the computed stray count drives the multi-shell warn.
    a = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.creation.box(extents=(10, 10, 10))
    b.apply_translation((30, 0, 0))
    stray_mesh = trimesh.util.concatenate([a, b])
    report, result = _gate(stray_mesh, make_plan([40, 10, 10]))
    assert report.n_bodies == 2 and report.stray_bodies == 1
    assert _codes(result).get("shells.multiple") is Level.WARN

    # A sealed hollow container (outer shell + nested cavity skin): 2 bodies, 0 strays —
    # the gate must NOT warn. This is exactly the false-positive class the stray-vs-nested
    # split exists for, and it only exercises with REAL geometry.
    outer = trimesh.creation.box(extents=(20, 20, 20))
    inner = trimesh.creation.box(extents=(16, 16, 16))
    inner.invert()  # cavity skin faces inward
    hollow = trimesh.util.concatenate([outer, inner])
    report2, result2 = _gate(hollow, make_plan([20, 20, 20]))
    assert report2.n_bodies == 2
    assert report2.stray_bodies == 0
    assert "shells.multiple" not in _codes(result2)  # no multi-shell warn


def test_real_dimension_mismatch_fails_from_computed_bbox():
    # The mesh is genuinely 30mm where the plan promised 20mm — the failure must come
    # from the computed bounding box, not a fixture value.
    mesh = trimesh.creation.box(extents=(30.0, 20.0, 20.0))
    _report, result = _gate(mesh, make_plan([20, 20, 20]))
    assert result.status is Level.FAIL
    assert _codes(result).get("dim.mismatch") is Level.FAIL


def _openscad_present() -> bool:
    from kimcad.config import Config

    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:  # pragma: no cover - config/binary absent
        return False


@pytest.mark.skipif(not _openscad_present(), reason="OpenSCAD binary not fetched")
def test_real_openscad_render_through_pipeline_matches_fake_contract(tmp_path):
    """TEST-004 (2026-06-09 audit): the pipeline's integration tests run on a fake renderer
    that can never drift from 'correct'. This case drives the REAL OpenSCAD binary through
    the full Pipeline.run orchestration (FakeProvider supplies deterministic OpenSCAD), so
    a real-tool contract drift — RenderResult shape, output format fallback, gate inputs —
    fails here instead of only in production."""
    from conftest import BAMBU, PLA, FakeProvider, make_plan

    from kimcad.config import Config
    from kimcad.pipeline import Pipeline, PipelineStatus

    provider = FakeProvider(make_plan([20, 20, 20]))
    pipeline = Pipeline(Config.load(), BAMBU, PLA, provider)  # default = real render_scad
    result = pipeline.run("a 20mm cube", tmp_path)
    assert result.status is PipelineStatus.completed
    assert result.mesh_path is not None and result.mesh_path.exists()
    # The real renderer's mesh fed the real validate→gate chain and passed it.
    assert result.report is not None
    assert result.report.gate_status == "pass"
    assert result.mesh_report is not None and result.mesh_report.watertight


def test_open_mesh_is_repaired_and_reported():
    # TEST-008 (stage-BCD gate): concrete assertions on the OBSERVED repair behavior —
    # a missing face on a real box fills deterministically (probed: repaired=True,
    # watertight=True, "filled holes" recorded), so pin exactly that, not an OR-chain.
    mesh = trimesh.creation.box(extents=(20, 20, 20))
    mesh.faces = mesh.faces[:-1]
    mesh.process(validate=False)
    assert not mesh.is_watertight
    report, result = _gate(mesh, make_plan([20, 20, 20]))
    assert report.repaired is True
    assert report.watertight is True  # the fill succeeded
    assert any("filled holes" in r for r in report.repairs)
    # A successful repair still surfaces as a WARN in the gate — never a silent pass.
    assert _codes(result).get("mesh.repaired") is Level.WARN
    assert result.status is not Level.FAIL
