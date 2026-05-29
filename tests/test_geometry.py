import numpy as np
import trimesh

from kimcad.config import Material, Printer
from kimcad.ir import DesignPlan
from kimcad.orientation import auto_orient
from kimcad.printability import Level, run_gate
from kimcad.validation import MeshReport, validate_mesh

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
