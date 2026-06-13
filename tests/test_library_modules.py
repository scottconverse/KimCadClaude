"""Coverage for the Phase-1 library expansion (option A).

Two layers:
- offline contract tests (no binary): the manifest, the runner's module map, and the
  prompt advertisement stay in sync, so a call to a real module always gets its `use`.
- a binary-gated integration test that actually renders each module and asserts it is
  watertight with the bounding box its manifest comment promises. Skipped when the
  pinned OpenSCAD binary isn't present, so the suite stays green offline.
"""

import tempfile
from pathlib import Path

import pytest

from kimcad.config import Config
from kimcad.llm_provider import build_library_manifest
from kimcad.openscad_runner import _library_module_map, inject_library_uses

# module name -> (its file, a representative call, expected bbox or None)
NEW_MODULES = {
    "wall_hook": (
        "hooks.scad",
        "wall_hook(plate_w=25, plate_h=60, plate_t=4, screw_d=4, "
        "screw_spacing=30, arm_proj=35, arm_rise=20);",
        [25, 39, 60],
    ),
    "pegboard_hook": (
        "hooks.scad",
        "pegboard_hook(hole_d=6, hole_spacing=25.4, arm_length=45);",
        [30, 62, 53.4],
    ),
    "l_bracket": ("bracket.scad", "l_bracket(arm=40, width=30, thick=4);", [40, 30, 40]),
    "cable_clip": ("clips.scad", "cable_clip(cable_d=6, width=20, screw_d=4);", [20, 25, 9.0]),
    "snap_box": ("containers.scad", "snap_box(width=80, depth=60, height=40, wall=2);", [80, 60, 40]),
    "enclosure": (
        "containers.scad",
        "enclosure(inner_w=80, inner_d=50, inner_h=30, wall=2.5);",
        [85, 55, 35],
    ),
    "tube": ("containers.scad", "tube(id=8, od=16, height=12);", [16, 16, 12]),
    "spool_holder": (
        "holders.scad",
        "spool_holder(spool_od=200, spool_width=70, screw_d=4);",
        [60, 93, 120],
    ),
    "drawer_divider": (
        "organizers.scad",
        "drawer_divider(length=150, depth=80, height=50, panel_t=2, compartments=3);",
        [150, 80, 50],
    ),
    # #19 slice 3: frames
    "picture_frame": (
        "frames.scad",
        "picture_frame(opening_w=90, opening_h=130, border=12, rabbet=4, depth=10, lip=3);",
        [114, 154, 10],
    ),
    "mat_board": (
        "frames.scad",
        "mat_board(mat_w=130, mat_h=160, window_w=90, window_h=120, mat_t=2);",
        [130, 160, 2],
    ),
    "floating_frame": (
        "frames.scad",
        "floating_frame(opening_w=90, opening_h=90, lip_w=10, gap=5, depth=20, back_t=3);",
        [120, 120, 20],
    ),
    "shadow_box_frame": (
        "frames.scad",
        "shadow_box_frame(opening_w=80, opening_h=80, border=12, cavity_depth=25, rabbet=4, "
        "back_t=3, lip=3);",
        [104, 104, 32],
    ),
    "lithophane_frame": (
        "frames.scad",
        "lithophane_frame(outer_w=100, outer_h=120, face_rim=8, light_gap=12, panel_t=3, "
        "face_rim_t=2);",
        [100, 120, 17],
    ),
    # #19 slice 4: hangers
    "sawtooth_hanger": (
        "hangers.scad",
        "sawtooth_hanger(plate_w=40, plate_h=15, plate_t=3, tooth_count=5, tooth_depth=4);",
        [40, 3, 19],
    ),
    "keyhole_hanger_plate": (
        "hangers.scad",
        "keyhole_hanger_plate(plate_w=30, plate_h=50, plate_t=4, hole_d=10, slot_w=5);",
        [30, 4, 50],
    ),
    "hidden_rod_shelf_bracket": (
        "hangers.scad",
        "hidden_rod_shelf_bracket(plate_w=80, plate_h=40, plate_t=6, rod_length=40, rod_d=8);",
        [80, 46, 40],
    ),
}


def test_manifest_maps_every_new_module_to_its_file():
    mapping = _library_module_map()
    for name, (file, _call, _bbox) in NEW_MODULES.items():
        assert mapping.get(name) == file, f"{name} should resolve to {file}"


def test_injection_adds_use_for_each_new_module():
    for name, (file, call, _bbox) in NEW_MODULES.items():
        _out, added = inject_library_uses(call)
        assert added == [f"use <library/{file}>;"], f"{name} -> {file}"


def test_prompt_manifest_advertises_new_modules():
    manifest = build_library_manifest()
    for name in NEW_MODULES:
        assert name in manifest, f"codegen prompt manifest should list {name}"


def _binary_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:
        return False


@pytest.mark.real_tool
@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
@pytest.mark.parametrize("name", list(NEW_MODULES))
def test_module_renders_watertight_with_documented_bbox(name):
    from kimcad.openscad_runner import render_scad
    from kimcad.validation import load_mesh, validate_mesh

    file, call, expected = NEW_MODULES[name]
    cfg = Config.load()
    scad = f"use <library/{file}>;\n{call}"
    with tempfile.TemporaryDirectory() as td:
        r = render_scad(
            scad,
            binary=cfg.binary_path("openscad"),
            out_dir=Path(td),
            basename="t",
            output_format=cfg.default_output_format(),
            timeout_s=cfg.limit("openscad_timeout_simple_s"),
            max_output_bytes=cfg.limit("max_output_bytes"),
        )
        _mesh, report = validate_mesh(load_mesh(r.output_path))
    assert report.watertight, f"{name} should render watertight"
    got = report.bounding_box_mm
    # Library geometry is deterministic: the rendered envelope must equal the module's
    # documented formula to mesh-format float noise, NOT the gate's fit tolerance. This
    # bound (10 microns) is ~10x the observed 3MF read-back noise and far below any real
    # geometric error, so a drift like the 0.1 mm cable-clip leak fails loudly here.
    for axis, g, e in zip("XYZ", got, expected):
        assert abs(g - e) <= 0.01, f"{name} {axis}: got {g:.4f}, expected {e:.4f}"
