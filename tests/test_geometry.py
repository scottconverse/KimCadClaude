import tempfile
from pathlib import Path

import numpy as np
import pytest
import trimesh

from kimcad.config import Config, Material, Printer
from kimcad.ir import DesignPlan
from kimcad.orientation import auto_orient
from kimcad.printability import Level, run_gate
from kimcad.validation import MeshReport, load_mesh, validate_mesh

BAMBU = Printer(
    key="bambu_p2s",
    name="Bambu Lab P2S",
    build_volume=(256, 256, 256),
    nozzle_diameter=0.4,
)
PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)


def _report(bbox, *, n_bodies=1, watertight=True):
    return MeshReport(
        watertight=watertight,
        repaired=False,
        repairs=[],
        vertices=8,
        faces=12,
        volume_mm3=float(bbox[0] * bbox[1] * bbox[2]),
        bounding_box_mm=(float(bbox[0]), float(bbox[1]), float(bbox[2])),
        n_bodies=n_bodies,
    )


# --- validation ---------------------------------------------------------------


def test_validate_watertight_box():
    box = trimesh.creation.box(extents=[50, 50, 10])
    _, report = validate_mesh(box)
    assert report.watertight
    assert report.n_bodies == 1
    assert np.allclose(report.bounding_box_mm, (50, 50, 10), atol=1e-6)
    assert abs(report.volume_mm3 - 25000) < 1.0


def test_validate_counts_disconnected_bodies():
    a = trimesh.creation.box(extents=[10, 10, 10])
    b = trimesh.creation.box(extents=[10, 10, 10])
    b.apply_translation([100, 0, 0])
    combined = trimesh.util.concatenate([a, b])
    _, report = validate_mesh(combined)
    assert report.n_bodies == 2


# --- printability gate --------------------------------------------------------


def test_gate_passes_on_match():
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[50, 50, 10])
    res = run_gate(_report((50, 50, 10)), plan, BAMBU, PLA)
    assert res.status is Level.PASS


def test_gate_fails_on_dim_mismatch():
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[200, 70, 52])
    res = run_gate(_report((150, 70, 52)), plan, BAMBU, PLA)
    assert res.failed
    assert any(f.code == "dim.mismatch" for f in res.findings)


def test_gate_fails_when_over_build_volume():
    plan = DesignPlan(object_type="block", summary="s", bounding_box_mm=[300, 300, 300])
    res = run_gate(_report((300, 300, 300)), plan, BAMBU, PLA)
    assert res.failed
    assert any(f.code == "volume.exceeds" for f in res.findings)


def test_gate_fails_on_a_non_finite_bbox():
    # ENG-001: a NaN/inf extent must FAIL the gate, not silently pass. IEEE NaN compares False
    # against every tolerance, so without an explicit finiteness check a degenerate part would
    # read as printable and could be sliced. Fail closed.
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[50, 50, 10])
    res = run_gate(_report((float("nan"), 50, 10)), plan, BAMBU, PLA)
    assert res.failed
    assert any(f.code == "dim.non_finite" for f in res.findings)
    res_inf = run_gate(_report((float("inf"), 50, 10)), plan, BAMBU, PLA)
    assert res_inf.failed and any(f.code == "dim.non_finite" for f in res_inf.findings)


def test_gate_passes_wall_when_adequate():
    # TEST-004: assert the wall.ok PASS branch directly (a declared wall above the min) — it was
    # previously only hit incidentally by other passing tests.
    plan = DesignPlan(object_type="box", summary="s", bounding_box_mm=[50, 50, 10],
                      dimensions={"wall": 2.0})
    res = run_gate(_report((50, 50, 10)), plan, BAMBU, PLA)
    assert any(f.code == "wall.ok" and f.level is Level.PASS for f in res.findings)


def test_gate_dimension_tolerance_boundary():
    # TEST-001: pin the +/-0.5mm dimensional tolerance at its edge — 0.4mm over PASSES, 0.6mm over
    # FAILS — so a future tolerance change is caught (the boundary was untested).
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[50, 50, 10])
    assert run_gate(_report((50.4, 50, 10)), plan, BAMBU, PLA).status is Level.PASS
    fail = run_gate(_report((50.6, 50, 10)), plan, BAMBU, PLA)
    assert fail.failed and any(f.code == "dim.mismatch" for f in fail.findings)


def test_gate_warns_on_thin_wall():
    plan = DesignPlan(
        object_type="box",
        summary="s",
        bounding_box_mm=[50, 50, 50],
        dimensions={"wall": 0.5},
    )
    res = run_gate(_report((50, 50, 50)), plan, BAMBU, PLA)
    assert any(f.code == "wall.thin" and f.level is Level.WARN for f in res.findings)


def test_gate_warns_on_multiple_shells():
    plan = DesignPlan(object_type="x", summary="s", bounding_box_mm=[20, 20, 20])
    res = run_gate(_report((20, 20, 20), n_bodies=3), plan, BAMBU, PLA)
    assert any(f.code == "shells.multiple" for f in res.findings)


def test_gate_fails_when_not_watertight():
    # A non-manifold / leaky mesh is unprintable, even if its dimensions match.
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[50, 50, 10])
    res = run_gate(_report((50, 50, 10), watertight=False), plan, BAMBU, PLA)
    assert res.failed
    assert any(f.code == "mesh.not_watertight" for f in res.findings)


def test_gate_warns_when_mesh_was_repaired():
    # Watertight only after repair: allowed, but surfaced — it had a real defect.
    plan = DesignPlan(object_type="plate", summary="s", bounding_box_mm=[50, 50, 10])
    rep = _report((50, 50, 10))
    rep.repaired = True
    rep.repairs = ["filled holes (was 2 open boundary loops)"]
    res = run_gate(rep, plan, BAMBU, PLA)
    assert res.status is Level.WARN
    assert any(f.code == "mesh.repaired" for f in res.findings)


# --- orientation --------------------------------------------------------------


def test_auto_orient_lays_flat_on_bed():
    box = trimesh.creation.box(extents=[40, 40, 8])
    # stand it on end so it needs reorienting
    box.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    oriented, info = auto_orient(box)
    # lowest point sits on the bed
    assert abs(oriented.bounds[0][2]) < 1e-6
    # most stable pose rests on a 40x40 face → height is the 8 mm dimension
    assert abs(oriented.extents[2] - 8) < 0.5
    assert info.stability > 0


# --- QA-001: nested cavity vs. stray body, on REAL geometry -------------------
#
# The gate must NOT flag a plain hollow container (one watertight solid whose inner
# cavity skin trimesh counts as a second "body") as a stray-shell mistake, but MUST
# flag genuinely loose geometry sitting apart from the main body. These tests drive
# real geometry through validate_mesh + run_gate.
#
# trimesh's boolean backend (manifold3d / blender) is not installed in this venv, so a
# true hollow watertight container is produced by rendering the demo `snap_box` library
# module through the pinned OpenSCAD binary — the exact QA-001 scenario.

_SNAP_BOX_SCAD = "use <library/containers.scad>;\nsnap_box(width=80, depth=60, height=40, wall=2);"


def _binary_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:  # pragma: no cover - config/binary absent
        return False


def _render_hollow_box() -> trimesh.Trimesh:
    """Render the demo snap_box to a watertight hollow solid via the real binary."""
    cfg = Config.load()
    from kimcad.openscad_runner import render_scad

    with tempfile.TemporaryDirectory() as td:
        result = render_scad(
            _SNAP_BOX_SCAD,
            binary=cfg.binary_path("openscad"),
            out_dir=Path(td),
            basename="hollow",
            output_format=cfg.default_output_format(),
            timeout_s=cfg.limit("openscad_timeout_simple_s"),
            max_output_bytes=cfg.limit("max_output_bytes"),
        )
        return load_mesh(result.output_path)


def test_qa001_single_solid_box_no_stray_no_warning():
    """A single solid box: stray_bodies == 0 and no shells.multiple warning."""
    box = trimesh.creation.box(extents=[20, 20, 20])
    _, report = validate_mesh(box)
    assert report.stray_bodies == 0
    plan = DesignPlan(object_type="block", summary="s", bounding_box_mm=[20, 20, 20])
    res = run_gate(report, plan, BAMBU, PLA)
    assert not any(f.code == "shells.multiple" for f in res.findings)


def test_qa001_disjoint_solids_are_stray_and_warn():
    """Two solids with non-overlapping bounding boxes: stray and warned on."""
    a = trimesh.creation.box(extents=[10, 10, 10])
    b = trimesh.creation.box(extents=[10, 10, 10])
    b.apply_translation([100, 0, 0])
    combined = trimesh.util.concatenate([a, b])
    _, report = validate_mesh(combined)

    # Neither disjoint box is nested inside the other, so both are stray.
    assert report.stray_bodies >= 1
    plan = DesignPlan(object_type="x", summary="s", bounding_box_mm=list(report.bounding_box_mm))
    res = run_gate(report, plan, BAMBU, PLA)
    assert any(f.code == "shells.multiple" for f in res.findings)


@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
def test_qa001_hollow_box_is_watertight_single_solid():
    """The rendered demo snap_box is one closed watertight solid with two surface
    shells (outer skin + nested inner cavity skin)."""
    mesh = _render_hollow_box()
    _, report = validate_mesh(mesh)
    assert report.watertight is True
    assert report.n_bodies == 2  # outer skin + inner cavity skin


@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
def test_qa001_hollow_box_does_not_warn_on_shells():
    """The exact QA-001 scenario: a plain hollow container must report stray_bodies == 0
    and the gate must NOT emit shells.multiple.

    The stray-body logic treats the largest-bbox component as the main solid (the outer
    shell of a hollow box), so its nested inner-cavity shell is not counted as stray.
    Regression anchor for the QA-001 fix.
    """
    mesh = _render_hollow_box()
    _, report = validate_mesh(mesh)
    assert report.stray_bodies == 0
    plan = DesignPlan(
        object_type="box", summary="s", bounding_box_mm=[80, 60, 40], dimensions={"wall": 2.0}
    )
    res = run_gate(report, plan, BAMBU, PLA)
    assert not any(f.code == "shells.multiple" for f in res.findings)


# --- TEST-005: non-watertight input is repaired-or-flagged correctly ----------


def test_validate_records_repair_on_non_watertight_input():
    """A box with a face removed is not watertight on input. validate_mesh attempts a
    conservative repair and records the outcome truthfully: in this trimesh build the
    single missing face is filled, so the result is watertight AND flagged repaired
    (the part had a real defect even though repair succeeded)."""
    box = trimesh.creation.box(extents=[20, 20, 20])
    open_mesh = trimesh.Trimesh(
        vertices=box.vertices.copy(), faces=box.faces[1:].copy(), process=False
    )
    assert open_mesh.is_watertight is False  # precondition: input really is open

    _, report = validate_mesh(open_mesh)

    if report.watertight:
        # trimesh repaired it: the repair must be recorded, and no leftover error.
        assert report.repaired is True
        assert report.repairs  # e.g. "filled holes (was 3 open boundary loops)"
        assert "not watertight after repair" not in "; ".join(report.errors)
    else:
        # repair could not close it: flagged not-watertight with an error recorded.
        assert report.repaired is True  # a repair was still attempted
        assert any("not watertight" in e for e in report.errors)


# --- TEST-006: auto_orient survives degenerate input --------------------------


def test_auto_orient_handles_flat_near_degenerate_mesh():
    """A near-zero-thickness sheet has no real volume; auto_orient must still return a
    mesh and orientation info without raising, and drop it onto the bed."""
    flat = trimesh.creation.box(extents=[40, 40, 1e-4])
    oriented, info = auto_orient(flat)
    assert isinstance(oriented, trimesh.Trimesh)
    assert info.description  # some non-empty description
    assert 0.0 <= info.stability <= 1.0
    assert abs(oriented.bounds[0][2]) < 1e-6  # sits on the bed


def test_auto_orient_handles_single_triangle():
    """A single triangle (no stable pose computable) must fall back gracefully rather
    than raise, returning a mesh and the 'left as-is' heuristic orientation."""
    tri = trimesh.Trimesh(
        vertices=np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], float),
        faces=np.array([[0, 1, 2]]),
        process=False,
    )
    oriented, info = auto_orient(tri)
    assert isinstance(oriented, trimesh.Trimesh)
    # ENG-004: the no-stable-pose fallback reports 0.0 stability (least certain), not a misleading
    # max-confidence 1.0 — the part is left as-is, but that isn't a confident orientation.
    assert info.stability == 0.0
    assert "left as-is" in info.description
