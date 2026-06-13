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
    # #19 slice 5: zen trays / dishes / incense holders
    "ring_dish": ("dishes.scad", "ring_dish(od=70, h=18, wall=3, well_depth=12, spike_h=0);", [70, 70, 18]),
    "incense_cone_holder": (
        "dishes.scad",
        "incense_cone_holder(dish_d=70, h=18, ped_d=28, moat_depth=8, dimple_d=12);",
        [70, 70, 18],
    ),
    "incense_stick_holder": (
        "dishes.scad",
        "incense_stick_holder(length=120, width=40, h=12, hole_d=4, trough_depth=6);",
        [120, 40, 12],
    ),
    "catchall_tray": (
        "dishes.scad",
        "catchall_tray(length=120, width=90, h=25, wall=3, corner_r=8, floor=2);",
        [120, 90, 25],
    ),
    "soap_dish": ("dishes.scad", "soap_dish(length=110, width=80, h=22, wall=3, rib_count=4);", [110, 80, 22]),
    "handled_tray": (
        "dishes.scad",
        "handled_tray(length=160, width=120, h=40, wall=3, handle_w=70);",
        [160, 120, 40],
    ),
    "zen_garden_tray": (
        "dishes.scad",
        "zen_garden_tray(length=120, width=90, wall_h=18, wall=3, foot_h=6, corner_r=6, foot_d=10);",
        [120, 90, 24],
    ),
    # #19 slice 6: holders / cups + planters
    "tealight_holder": (
        "dishes.scad",
        "tealight_holder(od=50, h=20, pocket_d=39.5, pocket_h=12, wall=3);",
        [50, 50, 20],
    ),
    "taper_candle_holder": (
        "dishes.scad",
        "taper_candle_holder(base_d=70, h=40, bore_d=22, bore_depth=25);",
        [70, 70, 40],
    ),
    "luminary_base": (
        "dishes.scad",
        "luminary_base(outer_d=80, height=40, cavity_d=52, cavity_h=26, rim_ledge=5, ledge_t=3);",
        [80, 80, 40],
    ),
    "bud_vase_sleeve": (
        "dishes.scad",
        "bud_vase_sleeve(od=60, h=120, bore_d=26, bore_depth=110, wall=4);",
        [60, 60, 120],
    ),
    "pencil_cup": (
        "dishes.scad",
        "pencil_cup(od=70, h=100, wall=3, floor_t=4);",
        [70, 70, 100],
    ),
    "propagation_station": (
        "dishes.scad",
        "propagation_station(length=160, depth=40, h=20, tube_d=24, leg_h=70);",
        [160, 40, 90],
    ),
    "planter_pot": (
        "dishes.scad",
        "planter_pot(bottom_d=70, top_d=90, h=90, wall=3, drain_d=12);",
        [90, 90, 90],
    ),
    "planter_saucer": (
        "dishes.scad",
        "planter_saucer(od=140, h=22, wall=4, floor_t=3, rim_h=6, rim_w=4);",
        [140, 140, 22],
    ),
    "bonsai_pot": (
        "dishes.scad",
        "bonsai_pot(length=140, width=100, h=35, wall=4, drain_d=8);",
        [140, 100, 35],
    ),
    "succulent_pot": (
        "dishes.scad",
        "succulent_pot(od=80, h=75, wall=3, facets=8, drain_d=12);",
        [80, 80, 75],
    ),
    # #19 slice 7: flat decor + ornaments (keys are MODULE names — the render test calls the module)
    "coaster_with_rim": (
        "dishes.scad",
        "coaster_with_rim(od=90, h=6, rim_w=4, rim_h=3, floor_t=2);",
        [90, 90, 6],
    ),
    "hotplate_trivet": (
        "dishes.scad",
        "hotplate_trivet(size=140, plate_t=6, slot_w=10, foot_h=8);",
        [140, 140, 14],
    ),
    "l_bookend": (
        "dishes.scad",
        "l_bookend(height=150, width=120, base_len=110, upright_t=6, base_t=5);",
        [110, 120, 150],
    ),
    "geometric_wall_tile": (
        "dishes.scad",
        "geometric_wall_tile(side=100, base_t=3, border_w=6, border_h=4);",
        [100, 100, 7],
    ),
    "tile_connector_clip": (
        "dishes.scad",
        "tile_connector_clip(length=60, width=24, neck_w=12, thick=4, tongue_l=14);",
        [60, 24, 4],
    ),
    "medallion_blank": (
        "dishes.scad",
        "medallion_blank(diameter=60, thick=4, hole_d=4, rim_margin=5);",
        [60, 60, 4],
    ),
    "ornament_cap": (
        "dishes.scad",
        "ornament_cap(cap_d=22, cap_h=12, neck_d=14, loop_od=14, loop_t=4);",
        [22, 22, 26],
    ),
    "gift_box_lid": (
        "dishes.scad",
        "gift_box_lid(width=90, depth=70, base_h=35, lid_h=40, wall=2, gap=8);",
        [188, 70, 40],
    ),
    "jar_lid": (
        "dishes.scad",
        "jar_lid(outer_d=70, top_t=4, skirt_d=64, skirt_h=12, skirt_wall=3);",
        [70, 70, 16],
    ),
    # #19 slice 8: stands / easels + ledges / rails (keys are MODULE names — the render test
    # calls the module; slanted_sign_holder's module is slanted_card_easel)
    "wedge_easel_stand": (
        "dishes.scad",
        "wedge_easel_stand(width=80, back_height=70, base_depth=60, lip_height=14, lip_depth=10);",
        [80, 60, 84],
    ),
    "display_riser": (
        "dishes.scad",
        "display_riser(base_w=90, base_d=70, tiers=4, step_in=8, tier_t=8);",
        [90, 70, 32],
    ),
    "slanted_card_easel": (
        "dishes.scad",
        "slanted_card_easel(base_w=90, base_depth=40, base_height=45, slot_w=4, "
        "back_margin=12, lean_deg=15);",
        [90, 52, 45],
    ),
    "desk_nameplate_strip_stand": (
        "dishes.scad",
        "desk_nameplate_strip_stand(base_w=120, base_depth=45, base_height=14, slot_w=4, "
        "slot_back_offset=30);",
        [120, 45, 44],
    ),
    "place_card_holder": (
        "dishes.scad",
        "place_card_holder(base_w=60, base_depth=25, base_height=18, slit_w=2.5, "
        "slit_depth=12, end_margin=6);",
        [60, 25, 18],
    ),
    "picture_ledge_shelf": (
        "dishes.scad",
        "picture_ledge_shelf(length=160, depth=70, back_height=40, lip_height=15, thk=4, screw_d=4);",
        [160, 70, 40],
    ),
    "peg_hook_rail": (
        "dishes.scad",
        "peg_hook_rail(length=160, bar_h=40, bar_t=12, peg_length=35, peg_d=12, peg_count=5);",
        [160, 47, 40],
    ),
    "j_decor_hook": (
        "dishes.scad",
        "j_decor_hook(width=60, back_height=70, reach=22, catch_rise=18, thk=5);",
        [60, 27, 88],
    ),
    "plate_display_stand": (
        "dishes.scad",
        "plate_display_stand(base_w=90, base_depth=70, back_height=90, groove_w=8, "
        "base_h=10, lean_off=24);",
        [90, 94, 100],
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
