"""KC-2 (#8) — trusted CadQuery twins of the template families, for the .STEP export.

Each shipped :class:`~kimcad.templates.TemplateFamily` gets an emitter that produces a
CadQuery script building the SAME geometry as the family's OpenSCAD library module — OUR
code, parameterized only by the family's clamped float values. The pipeline runs these
through the out-of-process worker with ``emit_step=True`` to attach an editable ``.step``
to template-built parts. No LLM ever authors this code, so the export carries zero
code-injection surface (the KC-4 measurement retired the LLM-CadQuery fallback).

Contract per emitter (the worker's script contract, same as ``cadquery_bench``):
- assigns ``result`` (the worker exports it); no imports (the worker provides ``cq``);
- geometry mirrors the library module CORNER-FOR-CORNER where the module is axis-faithful,
  so the per-axis envelope equals ``family.expected_bbox(values)`` — the gate target —
  within the bench tolerance (proven live in ``tests/test_cadquery_templates.py``);
- every value is interpolated through :func:`_f` (``float()`` + fixed-point formatting),
  so a non-numeric "value" raises instead of reaching the script.

Geometry source of truth: ``library/*.scad`` (box, containers, hooks, clips, organizers).
When a library module changes shape, its twin here changes in the same commit.
"""

from __future__ import annotations

from collections.abc import Callable

from kimcad.templates import TemplateFamily

# Mirrors the library modules' overlap epsilon (cuts/unions never z-fight) and the
# fit clearance the modules add to drilled holes.
_EPS = 0.05
_CLEAR = 0.2


def _f(value: object) -> str:
    """A value as CadQuery source: float-coerced (raises on non-numerics — injection-proof)
    and fixed-point formatted (no scientific notation surprises in generated code)."""
    return f"{float(value):.4f}"  # type: ignore[arg-type]


def _merged(family: TemplateFamily, values: dict[str, float]) -> dict[str, float]:
    return {**family.fixed_args, **values}


# Corner-at-origin box — the scad ``cube([x,y,z])`` idiom every library module uses.
_CF = "centered=(False, False, False)"


def _snap_box(v: dict[str, float]) -> str:
    # containers.scad::snap_box — outer solid minus the wall-inset hollow interior.
    w, d, h, t = _f(v["width"]), _f(v["depth"]), _f(v["height"]), _f(v["wall"])
    return (
        f'outer = cq.Workplane("XY").box({w}, {d}, {h}, {_CF})\n'
        f'inner = (cq.Workplane("XY")'
        f".box({w} - 2 * {t}, {d} - 2 * {t}, {h} - 2 * {t}, {_CF})"
        f".translate(({t}, {t}, {t})))\n"
        f"result = outer.cut(inner)\n"
    )


def _open_box(v: dict[str, float]) -> str:
    # box.scad::box (open_top) — cavity starts at the floor and over-cuts the top by 1 mm.
    w, d, h, t = _f(v["width"]), _f(v["depth"]), _f(v["height"]), _f(v["wall"])
    floor = _f(v.get("floor", 2.0))  # the module's default floor thickness
    return (
        f'outer = cq.Workplane("XY").box({w}, {d}, {h}, {_CF})\n'
        f'cavity = (cq.Workplane("XY")'
        f".box({w} - 2 * {t}, {d} - 2 * {t}, {h} - {floor} + 1.0, {_CF})"
        f".translate(({t}, {t}, {floor})))\n"
        f"result = outer.cut(cavity)\n"
    )


def _enclosure(v: dict[str, float]) -> str:
    # containers.scad::enclosure — a snap_box sized OUTER = inner + 2*wall on every axis.
    t = float(v["wall"])
    return _snap_box(
        {
            "width": float(v["inner_w"]) + 2 * t,
            "depth": float(v["inner_d"]) + 2 * t,
            "height": float(v["inner_h"]) + 2 * t,
            "wall": t,
        }
    )


def _tube(v: dict[str, float]) -> str:
    # containers.scad::tube — an annulus extruded to height (the classic cq two-circle idiom).
    od, bore, h = _f(v["od"]), _f(v["id"]), _f(v["height"])
    return (
        f'result = (cq.Workplane("XY")'
        f".circle({od} / 2).circle({bore} / 2).extrude({h}))\n"
    )


def _wall_hook(v: dict[str, float]) -> str:
    # hooks.scad::wall_hook — back plate + L arm (out +Y, lip up +Z), two Y-drilled screw
    # holes. arm_z0 mirrors the module's max(2, (plate_h - arm_rise)/2) seat.
    pw, ph, pt = _f(v["plate_w"]), _f(v["plate_h"]), _f(v["plate_t"])
    sd, ss = _f(v["screw_d"]), _f(v["screw_spacing"])
    proj, rise, arm = _f(v["arm_proj"]), _f(v["arm_rise"]), _f(v.get("arm_size", 6.0))
    return (
        f"eps = {_EPS}\n"
        f"arm_x0 = ({pw} - {arm}) / 2\n"
        f"arm_z0 = max(2.0, ({ph} - {rise}) / 2)\n"
        f'plate = cq.Workplane("XY").box({pw}, {pt}, {ph}, {_CF})\n'
        f'arm = (cq.Workplane("XY").box({arm}, {proj} + eps, {arm}, {_CF})'
        f".translate((arm_x0, {pt} - eps, arm_z0)))\n"
        f'lip = (cq.Workplane("XY").box({arm}, {arm}, {rise}, {_CF})'
        f".translate((arm_x0, {pt} + {proj} - {arm}, arm_z0)))\n"
        f"body = plate.union(arm).union(lip)\n"
        # A +Z cylinder rotated about X by -90 points +Y; translated to start just outside
        # the back face it spans the whole plate (the scad -eps..+eps drill pattern).
        f'drill = (cq.Workplane("XY").circle(({sd} + {_CLEAR}) / 2)'
        f".extrude({pt} + 2 * eps).rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"for z in ({ph} / 2 - {ss} / 2, {ph} / 2 + {ss} / 2):\n"
        f"    body = body.cut(drill.translate(({pw} / 2, -eps, z)))\n"
        f"result = body\n"
    )


def _cable_clip(v: dict[str, float]) -> str:
    # clips.scad::cable_clip — solid block, half-round cable channel along X open at the
    # top, screw hole through the mounting tab along Z. Clearance lives in the cuts only.
    cd, w = _f(v["cable_d"]), _f(v["width"])
    sd, t = _f(v["screw_d"]), _f(v["wall"])
    return (
        f"eps = {_EPS}\n"
        f"chan_r = ({cd} + {_CLEAR}) / 2\n"
        f"body_y = {cd} + 2 * {t}\n"
        f"tab_y = {sd} + 3 * {t}\n"
        f"depth = body_y + tab_y\n"
        f"height = {cd} / 2 + 2 * {t}\n"
        f'block = cq.Workplane("XY").box({w}, depth, height, {_CF})\n'
        # A +Z cylinder rotated about Y by +90 points +X; laid through the top face centre.
        f'chan = (cq.Workplane("XY").circle(chan_r).extrude({w} + 2 * eps)'
        f".rotate((0, 0, 0), (0, 1, 0), 90).translate((-eps, body_y / 2, height)))\n"
        f'screw = (cq.Workplane("XY").circle(({sd} + {_CLEAR}) / 2)'
        f".extrude(height + 2 * eps).translate(({w} / 2, body_y + tab_y / 2, -eps)))\n"
        f"result = block.cut(chan).cut(screw)\n"
    )


def _drawer_divider(v: dict[str, float]) -> str:
    # organizers.scad::drawer_divider — four-wall frame (open top AND bottom) plus
    # (compartments - 1) equal cross walls across the depth.
    length, d, h = _f(v["length"]), _f(v["depth"]), _f(v["height"])
    t = _f(v.get("panel_t", 2.0))
    n = int(round(float(v["compartments"])))
    return (
        f"eps = {_EPS}\n"
        f'frame = cq.Workplane("XY").box({length}, {d}, {h}, {_CF}).cut(\n'
        f'    cq.Workplane("XY")'
        f".box({length} - 2 * {t}, {d} - 2 * {t}, {h} + 2 * eps, {_CF})"
        f".translate(({t}, {t}, -eps)))\n"
        f"result = frame\n"
        f"for i in range(1, {n}):\n"
        f"    x = i * {length} / {n} - {t} / 2\n"
        f'    wall = (cq.Workplane("XY")'
        f".box({t}, {d} - 2 * {t} + 2 * eps, {h}, {_CF})"
        f".translate((x, {t} - eps, 0)))\n"
        f"    result = result.union(wall)\n"
    )


def _pegboard_hook(v: dict[str, float]) -> str:
    # hooks.scad::pegboard_hook — back plate + two rearward (-Y) pegs + an L arm out +Y and up.
    pw, hs, al = _f(v["plate_w"]), _f(v["hole_spacing"]), _f(v["arm_length"])
    pt, peg, rise, arm = _f(v["plate_t"]), _f(v["peg_len"]), _f(v["arm_rise"]), _f(v["arm_size"])
    hd = _f(v["hole_d"])
    return (
        f"eps = {_EPS}\n"
        f"clear = {_CLEAR}\n"
        f"plate_h = {hs} + 2 * {arm} + 16\n"
        f"peg_d = max(2.0, {hd} - clear)\n"
        f"z_lo = (plate_h - {hs}) / 2\n"
        f"z_hi = z_lo + {hs}\n"
        f"arm_x0 = ({pw} - {arm}) / 2\n"
        f"arm_z0 = max(2.0, z_lo - {arm})\n"
        f'body = cq.Workplane("XY").box({pw}, {pt}, plate_h, {_CF})\n'
        # rearward pegs: a +Z cylinder rotated +90 about X points -Y (the scad rotate([90,0,0])).
        f'peg = (cq.Workplane("XY").circle(peg_d / 2).extrude({peg} + eps)'
        f".rotate((0, 0, 0), (1, 0, 0), 90))\n"
        f"for z in (z_lo, z_hi):\n"
        f"    body = body.union(peg.translate(({pw} / 2, eps, z)))\n"
        f'arm = (cq.Workplane("XY").box({arm}, {al} + eps, {arm}, {_CF})'
        f".translate((arm_x0, {pt} - eps, arm_z0)))\n"
        f'lip = (cq.Workplane("XY").box({arm}, {arm}, {rise}, {_CF})'
        f".translate((arm_x0, {pt} + {al} - {arm}, arm_z0)))\n"
        f"result = body.union(arm).union(lip)\n"
    )


def _spool_holder(v: dict[str, float]) -> str:
    # holders.scad::spool_holder — back plate + horizontal axle arm (+Y) + end-stop flange,
    # minus two wall screw holes drilled along Y.
    pw, sw, ph = _f(v["plate_w"]), _f(v["spool_width"]), _f(v["plate_h"])
    pt, sd, ad = _f(v["plate_t"]), _f(v["screw_d"]), _f(v["arm_d"])
    return (
        f"eps = {_EPS}\n"
        f"clear = {_CLEAR}\n"
        f"arm_len = {sw} + 15\n"
        f"arm_z = {ph} - {ad} / 2 - 8\n"
        f"stop_d = {ad} + 12\n"
        f'plate = cq.Workplane("XY").box({pw}, {pt}, {ph}, {_CF})\n'
        # +Z cylinder rotated -90 about X points +Y (the scad rotate([-90,0,0])).
        f'arm = (cq.Workplane("XY").circle({ad} / 2).extrude(arm_len)'
        f".rotate((0, 0, 0), (1, 0, 0), -90).translate(({pw} / 2, {pt} - eps, arm_z)))\n"
        f'stop = (cq.Workplane("XY").circle(stop_d / 2).extrude(3.0)'
        f".rotate((0, 0, 0), (1, 0, 0), -90).translate(({pw} / 2, {pt} + arm_len - 3.0, arm_z)))\n"
        f"body = plate.union(arm).union(stop)\n"
        f'drill = (cq.Workplane("XY").circle(({sd} + clear) / 2).extrude({pt} + 2 * eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"for z in ({ph} * 0.25, {ph} * 0.75):\n"
        f"    body = body.cut(drill.translate(({pw} / 2, -eps, z)))\n"
        f"result = body\n"
    )


def _l_bracket(v: dict[str, float]) -> str:
    # bracket.scad::l_bracket — base arm (XY) + upright arm (rising Z), two clearance holes
    # through each arm. screw clearance mirrors fasteners.scad::screw_clearance_dia.
    arm, width, thick = _f(v["arm"]), _f(v["width"]), _f(v["thick"])
    inset = _f(v.get("inset", 8.0))
    screw = float(v.get("screw", 4.0))
    clear_d = _f(
        {2.0: 2.4, 2.5: 2.9, 3.0: 3.4, 4.0: 4.5, 5.0: 5.5, 6.0: 6.6, 8.0: 9.0}.get(
            screw, screw * 1.12
        )
    )
    return (
        f"eps = {_EPS}\n"
        f'base = cq.Workplane("XY").box({arm}, {width}, {thick}, {_CF})\n'
        f'upright = cq.Workplane("XY").box({thick}, {width}, {arm}, {_CF})\n'
        f"body = base.union(upright)\n"
        # base holes through Z
        f'zhole = (cq.Workplane("XY").circle({clear_d} / 2).extrude({thick} + 2 * eps)'
        f".translate((0, 0, -eps)))\n"
        f"for y in ({inset}, {width} - {inset}):\n"
        f"    body = body.cut(zhole.translate(({arm} - {inset}, y, 0)))\n"
        # upright holes through X: a +Z cylinder rotated +90 about Y points +X (scad rotate([0,90,0])).
        f'xhole = (cq.Workplane("XY").circle({clear_d} / 2).extrude({thick} + 2 * eps)'
        f".rotate((0, 0, 0), (0, 1, 0), 90).translate((-eps, 0, 0)))\n"
        f"for y in ({inset}, {width} - {inset}):\n"
        f"    body = body.cut(xhole.translate((0, y, {arm} - {inset})))\n"
        f"result = body\n"
    )


def _picture_frame(v: dict[str, float]) -> str:
    # frames.scad::picture_frame — outer face minus a through window minus a back rabbet.
    ow_in, oh_in = _f(v["opening_w"]), _f(v["opening_h"])
    b, rab, d, lip = _f(v["border"]), _f(v["rabbet"]), _f(v["depth"]), _f(v.get("lip", 3.0))
    return (
        f"eps = {_EPS}\n"
        f"ow = {ow_in} + 2 * {b}\n"
        f"oh = {oh_in} + 2 * {b}\n"
        f'outer = cq.Workplane("XY").box(ow, oh, {d}, {_CF})\n'
        f'win = (cq.Workplane("XY").box({ow_in}, {oh_in}, {d} + 2 * eps, {_CF})'
        f".translate(({b}, {b}, -eps)))\n"
        f'rab = (cq.Workplane("XY").box({ow_in} + 2 * {lip}, {oh_in} + 2 * {lip}, {rab} + eps, {_CF})'
        f".translate(({b} - {lip}, {b} - {lip}, -eps)))\n"
        f"result = outer.cut(win).cut(rab)\n"
    )


def _mat_board(v: dict[str, float]) -> str:
    # frames.scad::mat_board — a flat sheet minus a centered window.
    mw, mh, ww, wh, mt = _f(v["mat_w"]), _f(v["mat_h"]), _f(v["window_w"]), _f(v["window_h"]), _f(v["mat_t"])
    return (
        f"eps = {_EPS}\n"
        f'sheet = cq.Workplane("XY").box({mw}, {mh}, {mt}, {_CF})\n'
        f'win = (cq.Workplane("XY").box({ww}, {wh}, {mt} + 2 * eps, {_CF})'
        f".translate((({mw} - {ww}) / 2, ({mh} - {wh}) / 2, -eps)))\n"
        f"result = sheet.cut(win)\n"
    )


def _floating_frame(v: dict[str, float]) -> str:
    # frames.scad::floating_frame — outer block minus the front-open art cavity above the back shelf.
    ow_in, oh_in = _f(v["opening_w"]), _f(v["opening_h"])
    lw, gap, d, bt = _f(v["lip_w"]), _f(v["gap"]), _f(v["depth"]), _f(v.get("back_t", 3.0))
    return (
        f"eps = {_EPS}\n"
        f"ow = {ow_in} + 2 * {gap} + 2 * {lw}\n"
        f"oh = {oh_in} + 2 * {gap} + 2 * {lw}\n"
        f'outer = cq.Workplane("XY").box(ow, oh, {d}, {_CF})\n'
        f'cav = (cq.Workplane("XY").box({ow_in} + 2 * {gap}, {oh_in} + 2 * {gap}, {d} - {bt} + eps, {_CF})'
        f".translate(({lw}, {lw}, {bt})))\n"
        f"result = outer.cut(cav)\n"
    )


def _shadow_box_frame(v: dict[str, float]) -> str:
    # frames.scad::shadow_box_frame — solid back, blind cavity, front glass rabbet.
    ow_in, oh_in, b = _f(v["opening_w"]), _f(v["opening_h"]), _f(v["border"])
    cd, rab = _f(v["cavity_depth"]), _f(v["rabbet"])
    bt, lip = _f(v.get("back_t", 3.0)), _f(v.get("lip", 3.0))
    return (
        f"eps = {_EPS}\n"
        f"ow = {ow_in} + 2 * {b}\n"
        f"oh = {oh_in} + 2 * {b}\n"
        f"depth = {cd} + {rab} + {bt}\n"
        f'outer = cq.Workplane("XY").box(ow, oh, depth, {_CF})\n'
        f'cav = (cq.Workplane("XY").box({ow_in}, {oh_in}, {cd} + eps, {_CF})'
        f".translate(({b}, {b}, {bt})))\n"
        f'rab = (cq.Workplane("XY").box({ow_in} + 2 * {lip}, {oh_in} + 2 * {lip}, {rab} + eps, {_CF})'
        f".translate(({b} - {lip}, {b} - {lip}, {bt} + {cd})))\n"
        f"result = outer.cut(cav).cut(rab)\n"
    )


def _lithophane_frame(v: dict[str, float]) -> str:
    # frames.scad::lithophane_frame — face rim with a window, panel rebate, open-back light cavity.
    ow, oh, fr = _f(v["outer_w"]), _f(v["outer_h"]), _f(v["face_rim"])
    lg, pt, frt = _f(v["light_gap"]), _f(v["panel_t"]), _f(v.get("face_rim_t", 2.0))
    return (
        f"eps = {_EPS}\n"
        f"depth = {frt} + {pt} + {lg}\n"
        f'outer = cq.Workplane("XY").box({ow}, {oh}, depth, {_CF})\n'
        f'win = (cq.Workplane("XY").box({ow} - 2 * {fr}, {oh} - 2 * {fr}, {frt} + eps, {_CF})'
        f".translate(({fr}, {fr}, -eps)))\n"
        f'cav = (cq.Workplane("XY").box({ow} - {fr}, {oh} - {fr}, {pt} + {lg} + eps, {_CF})'
        f".translate(({fr} / 2, {fr} / 2, {frt})))\n"
        f"result = outer.cut(win).cut(cav)\n"
    )


def _sawtooth_hanger(v: dict[str, float]) -> str:
    # hangers.scad::sawtooth_hanger — plate + a row of triangular teeth + two screw holes.
    pw, ph, pt = _f(v["plate_w"]), _f(v["plate_h"]), _f(v["plate_t"])
    n = int(round(float(v["tooth_count"])))
    td, sd = _f(v["tooth_depth"]), _f(v.get("screw_d", 3.0))
    return (
        f"eps = {_EPS}\n"
        f"clear = {_CLEAR}\n"
        f"run = {pw} / {n}\n"
        f'body = cq.Workplane("XY").box({pw}, {pt}, {ph}, {_CF})\n'
        f"for i in range({n}):\n"
        f'    tooth = (cq.Workplane("XY").polyline([(0, 0), (run, 0), (0, {td} + eps)]).close()'
        f".extrude({pt}).rotate((0, 0, 0), (1, 0, 0), 90).translate((i * run, {pt}, {ph} - eps)))\n"
        f"    body = body.union(tooth)\n"
        f'drill = (cq.Workplane("XY").circle(({sd} + clear) / 2).extrude({pt} + 2 * eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"for x in ({pw} * 0.25, {pw} * 0.75):\n"
        f"    body = body.cut(drill.translate((x, -eps, {ph} * 0.45)))\n"
        f"result = body\n"
    )


def _keyhole_hanger_plate(v: dict[str, float]) -> str:
    # hangers.scad::keyhole_hanger_plate — plate minus entry hole + slot + slot-bottom + back counterbore.
    pw, ph, pt = _f(v["plate_w"]), _f(v["plate_h"]), _f(v["plate_t"])
    hd, sw = _f(v["hole_d"]), _f(v["slot_w"])
    return (
        f"eps = {_EPS}\n"
        f"head_z = {ph} * 0.72\n"
        f"slot_bot = {ph} * 0.30\n"
        f"cb_d = {hd} + 6\n"
        f"cb_depth = {pt} * 0.5\n"
        f'body = cq.Workplane("XY").box({pw}, {pt}, {ph}, {_CF})\n'
        f'hole = (cq.Workplane("XY").circle({hd} / 2).extrude({pt} + 2 * eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"body = body.cut(hole.translate(({pw} / 2, -eps, head_z)))\n"
        f'slot = (cq.Workplane("XY").box({sw}, {pt} + 2 * eps, head_z - slot_bot, {_CF})'
        f".translate(({pw} / 2 - {sw} / 2, -eps, slot_bot)))\n"
        f"body = body.cut(slot)\n"
        f'sb = (cq.Workplane("XY").circle({sw} / 2).extrude({pt} + 2 * eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"body = body.cut(sb.translate(({pw} / 2, -eps, slot_bot)))\n"
        f'cb = (cq.Workplane("XY").circle(cb_d / 2).extrude(cb_depth + eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"body = body.cut(cb.translate(({pw} / 2, -eps, head_z)))\n"
        f"result = body\n"
    )


def _hidden_rod_shelf_bracket(v: dict[str, float]) -> str:
    # hangers.scad::hidden_rod_shelf_bracket — wall plate + two screw holes + two +Y shelf rods.
    pw, ph, pt = _f(v["plate_w"]), _f(v["plate_h"]), _f(v["plate_t"])
    rl, rd, sd = _f(v["rod_length"]), _f(v["rod_d"]), _f(v.get("screw_d", 4.0))
    return (
        f"eps = {_EPS}\n"
        f"clear = {_CLEAR}\n"
        f'body = cq.Workplane("XY").box({pw}, {pt}, {ph}, {_CF})\n'
        f'drill = (cq.Workplane("XY").circle(({sd} + clear) / 2).extrude({pt} + 2 * eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"for z in ({ph} * 0.25, {ph} * 0.75):\n"
        f"    body = body.cut(drill.translate(({pw} / 2, -eps, z)))\n"
        f'rod = (cq.Workplane("XY").circle({rd} / 2).extrude({rl} + eps)'
        f".rotate((0, 0, 0), (1, 0, 0), -90))\n"
        f"for x in ({pw} * 0.25, {pw} * 0.75):\n"
        f"    body = body.union(rod.translate((x, {pt} - eps, {ph} / 2)))\n"
        f"result = body\n"
    )


def _ring_dish(v: dict[str, float]) -> str:
    # dishes.scad::ring_dish — outer puck minus a top well, plus an optional center spike.
    od, h, wall = _f(v["od"]), _f(v["h"]), _f(v["wall"])
    wd, sh, sd = _f(v["well_depth"]), _f(v["spike_h"]), _f(v.get("spike_d", 6.0))
    return (
        f"eps = {_EPS}\n"
        f"well_floor = {h} - {wd}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'well = (cq.Workplane("XY").circle(({od} - 2 * {wall}) / 2)'
        f".extrude({wd} + eps).translate((0, 0, well_floor)))\n"
        f'spike = (cq.Workplane("XY").circle({sd} / 2)'
        f".extrude({wd} + {sh} + eps).translate((0, 0, well_floor - eps)))\n"
        f"result = body.cut(well).union(spike)\n"
    )


def _incense_cone_holder(v: dict[str, float]) -> str:
    # dishes.scad::incense_cone_holder — dish minus an annular ash moat minus a downward cone dimple.
    dish_d, h = _f(v["dish_d"]), _f(v["h"])
    ped_d, md, dd = _f(v["ped_d"]), _f(v["moat_depth"]), _f(v["dimple_d"])
    rim = _f(v.get("rim", 4.0))
    return (
        f"eps = {_EPS}\n"
        f"moat_od = {dish_d} - 2 * {rim}\n"
        f'dish = cq.Workplane("XY").circle({dish_d} / 2).extrude({h})\n'
        f'moat = (cq.Workplane("XY").circle(moat_od / 2).circle({ped_d} / 2)'
        f".extrude({md} + eps).translate((0, 0, {h} - {md})))\n"
        f'dimple = (cq.Workplane("XY").circle({dd} / 2)'
        f".extrude({md} + eps).translate((0, 0, {h} - {md})))\n"
        f"result = dish.cut(moat).cut(dimple)\n"
    )


def _incense_stick_holder(v: dict[str, float]) -> str:
    # dishes.scad::incense_stick_holder — boat minus an ash trough minus a fixed row of stick bores.
    length, width, h = _f(v["length"]), _f(v["width"]), _f(v["h"])
    hd, td = _f(v["hole_d"]), _f(v["trough_depth"])
    bores = 5
    return (
        f"eps = {_EPS}\n"
        f"end_inset = 0.1 * {length}\n"
        f"side_inset = 0.2 * {width}\n"
        f"trough_l = {length} - 2 * end_inset\n"
        f"trough_w = {width} - 2 * side_inset\n"
        f"bore_y = {width} - side_inset - {hd} / 2 - 1\n"
        f"bore_depth = {h} - 2\n"
        f'body = cq.Workplane("XY").box({length}, {width}, {h}, {_CF})\n'
        f'trough = (cq.Workplane("XY").box(trough_l, trough_w, {td} + eps, {_CF})'
        f".translate((end_inset, side_inset, {h} - {td})))\n"
        f"result = body.cut(trough)\n"
        f"for i in range({bores}):\n"
        f"    x = {length} / 2 + (i - ({bores} - 1) / 2) * ({length} / ({bores} + 1))\n"
        f'    bore = (cq.Workplane("XY").circle({hd} / 2).extrude(bore_depth + eps)'
        f".translate((x, bore_y, {h} - bore_depth)))\n"
        f"    result = result.cut(bore)\n"
    )


def _catchall_tray(v: dict[str, float]) -> str:
    # dishes.scad::catchall_tray — rounded-rect prism (|Z edges filleted) minus an inset rounded pocket.
    length, width, h = _f(v["length"]), _f(v["width"]), _f(v["h"])
    t, cr, floor = _f(v["wall"]), _f(v["corner_r"]), _f(v.get("floor", 2.0))
    return (
        f"eps = {_EPS}\n"
        f"inner_r = {cr} - {t}\n"
        f'outer = (cq.Workplane("XY").box({length}, {width}, {h}, {_CF})'
        f'.edges("|Z").fillet({cr}))\n'
        f'pocket = (cq.Workplane("XY").box({length} - 2 * {t}, {width} - 2 * {t}, {h} - {floor} + eps, {_CF})'
        f'.edges("|Z").fillet(inner_r).translate(({t}, {t}, {floor})))\n'
        f"result = outer.cut(pocket)\n"
    )


def _soap_dish(v: dict[str, float]) -> str:
    # dishes.scad::soap_dish — open-top tray + rib_count drainage ribs minus a row of drain holes.
    length, w, h = _f(v["length"]), _f(v["width"]), _f(v["h"])
    t = _f(v["wall"])
    n = int(round(float(v["rib_count"])))
    return (
        f"eps = {_EPS}\n"
        f"pocket_l = {length} - 2 * {t}\n"
        f"pocket_w = {w} - 2 * {t}\n"
        f"pocket_depth = {h} - {t}\n"
        f"pitch = pocket_l / ({n} + 1)\n"
        f"rib_t = min(1.6, pitch / 4)\n"
        f"rib_h = min(2.0, pocket_depth / 2)\n"
        f"drain_d = min(min(3.0, pitch / 4), pocket_w / 2)\n"
        f'outer = cq.Workplane("XY").box({length}, {w}, {h}, {_CF})\n'
        f'pocket = (cq.Workplane("XY")'
        f".box(pocket_l, pocket_w, pocket_depth + eps, {_CF})"
        f".translate(({t}, {t}, {t})))\n"
        f"result = outer.cut(pocket)\n"
        f"for i in range(1, {n} + 1):\n"
        f"    x = {t} + i * pitch - rib_t / 2\n"
        f'    rib = (cq.Workplane("XY")'
        f".box(rib_t, pocket_w, rib_h + eps, {_CF})"
        f".translate((x, {t}, {t} - eps)))\n"
        f"    result = result.union(rib)\n"
        f'drill = cq.Workplane("XY").circle(drain_d / 2).extrude({t} + 2 * eps)\n'
        f"for i in range({n} + 1):\n"
        f"    x = {t} + i * pitch + pitch / 2\n"
        f"    result = result.cut(drill.translate((x, {w} / 2, -eps)))\n"
    )


def _handled_tray(v: dict[str, float]) -> str:
    # dishes.scad::handled_tray — box-tray hollowed to a pocket, with two rounded grips through
    # the short end walls (slot2D = the convex hull of two circles, the scad hull() equivalent).
    length, width, h = _f(v["length"]), _f(v["width"]), _f(v["h"])
    t, hw = _f(v["wall"]), _f(v["handle_w"])
    return (
        f"eps = {_EPS}\n"
        f"slot_h = {h} * 0.25\n"
        f"slot_zc = {h} * 0.90 - {t} - slot_h / 2\n"
        f'outer = cq.Workplane("XY").box({length}, {width}, {h}, {_CF})\n'
        f'pocket = (cq.Workplane("XY")'
        f".box({length} - 2 * {t}, {width} - 2 * {t}, {h} - {t} + eps, {_CF})"
        f".translate(({t}, {t}, {t})))\n"
        f"body = outer.cut(pocket)\n"
        f'grip = (cq.Workplane("XY").slot2D({hw}, slot_h, 90).extrude({t} + 2 * eps)'
        f".rotate((0, 0, 0), (0, 1, 0), 90))\n"
        f"body = body.cut(grip.translate((-eps, {width} / 2, slot_zc)))\n"
        f"body = body.cut(grip.translate(({length} - {t} - eps, {width} / 2, slot_zc)))\n"
        f"result = body\n"
    )


def _zen_garden_tray(v: dict[str, float]) -> str:
    # dishes.scad::zen_garden_tray — four XY-centered corner feet under a rounded-rect tray body
    # with a top-open sand cavity. The rounded rect is a corner-at-origin box with its vertical
    # (|Z) edges filleted at corner_r — the same robust idiom as _catchall_tray (mirrors the
    # OpenSCAD offset(square) rounded rect to the same envelope + corner radius).
    length, width, wall_h = _f(v["length"]), _f(v["width"]), _f(v["wall_h"])
    wall, foot_h = _f(v["wall"]), _f(v["foot_h"])
    cr, fd = _f(v.get("corner_r", 6.0)), _f(v.get("foot_d", 10.0))
    return (
        f"eps = {_EPS}\n"
        f"foot_r = {fd} / 2\n"
        f"inset = {cr} + foot_r\n"
        f'body = (cq.Workplane("XY").box({length}, {width}, {wall_h}, {_CF})'
        f'.edges("|Z").fillet({cr}).translate((0, 0, {foot_h})))\n'
        f'cav = (cq.Workplane("XY").box({length} - 2 * {wall}, {width} - 2 * {wall}, '
        f"{wall_h} - {wall} + eps, {_CF})"
        f'.edges("|Z").fillet({cr} - {wall}).translate(({wall}, {wall}, {foot_h} + {wall})))\n'
        f"result = body.cut(cav)\n"
        f'foot = cq.Workplane("XY").circle(foot_r).extrude({foot_h} + eps)\n'
        f"for fx in (inset, {length} - inset):\n"
        f"    for fy in (inset, {width} - inset):\n"
        f"        result = result.union(foot.translate((fx, fy, 0)))\n"
    )


# --- #19 slice 6: holders / cups + planters (dishes.scad) ----------------------------


def _tealight_holder(v: dict[str, float]) -> str:
    # dishes.scad::tealight_holder — solid outer cylinder minus a centered top pocket that
    # seats a standard ~38-40 mm tealight cup. Both cylinders are XY-centered; the pocket
    # over-cuts +eps up into open air, so the envelope stays exactly [od, od, h].
    od, h = _f(v["od"]), _f(v["h"])
    pd, ph = _f(v["pocket_d"]), _f(v["pocket_h"])
    return (
        f"eps = {_EPS}\n"
        f"pocket_floor = {h} - {ph}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'pocket = (cq.Workplane("XY").circle({pd} / 2)'
        f".extrude({ph} + eps).translate((0, 0, pocket_floor)))\n"
        f"result = body.cut(pocket)\n"
    )


def _taper_candle_holder(v: dict[str, float]) -> str:
    # dishes.scad::taper_candle_holder — a solid XY-centered base cylinder (base_d x h) minus a
    # centered top bore (bore_d x bore_depth) that grips a ~22 mm taper. The bore over-cuts UP by
    # eps into the open air above the rim (never past the base height); bbox = [base_d, base_d, h].
    base_d, h = _f(v["base_d"]), _f(v["h"])
    bore_d, bd = _f(v["bore_d"]), _f(v["bore_depth"])
    return (
        f"eps = {_EPS}\n"
        f"bore_floor = {h} - {bd}\n"
        f'body = cq.Workplane("XY").circle({base_d} / 2).extrude({h})\n'
        f'bore = (cq.Workplane("XY").circle({bore_d} / 2)'
        f".extrude({bd} + eps).translate((0, 0, bore_floor)))\n"
        f"result = body.cut(bore)\n"
    )


def _luminary_base(v: dict[str, float]) -> str:
    # dishes.scad::luminary_base — outer puck minus a center puck cavity minus a wider top
    # rim-ledge counterbore. Cylinders are XY-centered (matches OpenSCAD's cylinder()); the
    # ledge diameter is min()-clamped strictly inside the outer wall, mirroring the module,
    # so the top ledge cut can never shave the documented height.
    od, h = _f(v["outer_d"]), _f(v["height"])
    cd, ch, rl = _f(v["cavity_d"]), _f(v["cavity_h"]), _f(v["rim_ledge"])
    lt = _f(v.get("ledge_t", 3.0))
    return (
        f"eps = {_EPS}\n"
        f"cavity_floor = {h} - {ch}\n"
        f"ledge_d = min({cd} + 2 * {rl}, {od} - 2)\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'cavity = (cq.Workplane("XY").circle({cd} / 2)'
        f".extrude({ch} + eps).translate((0, 0, cavity_floor)))\n"
        f'ledge = (cq.Workplane("XY").circle(ledge_d / 2)'
        f".extrude({lt} + eps).translate((0, 0, {h} - {lt})))\n"
        f"result = body.cut(cavity).cut(ledge)\n"
    )


def _bud_vase_sleeve(v: dict[str, float]) -> str:
    # dishes.scad::bud_vase_sleeve — XY-centered outer cylinder minus a top bore. safe_bore
    # mirrors the module's min(bore_d, od - 2*wall) wall guard, resolved at emit time from the
    # clamped float values (so the script stays a pure cylinder cut, no runtime min()).
    od, h = _f(v["od"]), _f(v["h"])
    bore_depth = _f(v["bore_depth"])
    safe_bore = _f(min(float(v["bore_d"]), float(v["od"]) - 2 * float(v["wall"])))
    return (
        f"eps = {_EPS}\n"
        f"bore_floor = {h} - {bore_depth}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'bore = (cq.Workplane("XY").circle({safe_bore} / 2)'
        f".extrude({bore_depth} + eps).translate((0, 0, bore_floor)))\n"
        f"result = body.cut(bore)\n"
    )


def _pencil_cup(v: dict[str, float]) -> str:
    # dishes.scad::pencil_cup — solid outer cylinder hollowed to a top-open pocket with a
    # thick floor. Bore = od - 2*wall, pocket floor at z = floor_t, over-cut up by eps into
    # the open air above the rim. XY-centered cylinders; bbox = [od, od, h].
    od, h, wall, floor_t = _f(v["od"]), _f(v["h"]), _f(v["wall"]), _f(v["floor_t"])
    return (
        f"eps = {_EPS}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'pocket = (cq.Workplane("XY").circle(({od} - 2 * {wall}) / 2)'
        f".extrude({h} - {floor_t} + eps).translate((0, 0, {floor_t})))\n"
        f"result = body.cut(pocket)\n"
    )


def _propagation_station(v: dict[str, float]) -> str:
    # dishes.scad::propagation_station — a horizontal bar on top of two end legs, with a FIXED
    # row of vertical tube bores drilled down into the bar. The bar carries the full [length,
    # depth] footprint and rises from z = leg_h to z = leg_h + h; the legs sit inside that
    # footprint (so the envelope is exactly [length, depth, h + leg_h]). bores is FIXED — it
    # does not enter the bbox (the drawer_divider / incense_stick_holder precedent).
    length, depth, h = _f(v["length"]), _f(v["depth"]), _f(v["h"])
    tube_d, leg_h = _f(v["tube_d"]), _f(v["leg_h"])
    bores = 5
    leg_w = _f(10.0)
    return (
        f"eps = {_EPS}\n"
        f"bore_depth = {h} - 2\n"
        f'bar = (cq.Workplane("XY").box({length}, {depth}, {h}, {_CF})'
        f".translate((0, 0, {leg_h})))\n"
        f"result = bar\n"
        f"for i in range({bores}):\n"
        f"    x = {length} / 2 + (i - ({bores} - 1) / 2) * ({length} / ({bores} + 1))\n"
        f'    bore = (cq.Workplane("XY").circle({tube_d} / 2).extrude(bore_depth + eps)'
        f".translate((x, {depth} / 2, {leg_h} + {h} - bore_depth)))\n"
        f"    result = result.cut(bore)\n"
        f"for x in (0.0, {length} - {leg_w}):\n"
        f'    leg = (cq.Workplane("XY").box({leg_w}, {depth}, {leg_h} + eps, {_CF})'
        f".translate((x, 0, 0)))\n"
        f"    result = result.union(leg)\n"
    )


def _planter_pot(v: dict[str, float]) -> str:
    # dishes.scad::planter_pot — outer tapered frustum minus an inner tapered cavity minus a
    # center drain hole. Each frustum is a LOFT between two XY-centered circles at different Z
    # (the proven taper idiom — NOT makeCone); the drain is an XY-centered cylinder. floor = wall.
    bd, td, h = _f(v["bottom_d"]), _f(v["top_d"]), _f(v["h"])
    wall, dd = _f(v["wall"]), _f(v["drain_d"])
    return (
        f"eps = {_EPS}\n"
        f"floor = {wall}\n"
        f"in_bot = {bd} - 2 * {wall}\n"
        f"in_top = {td} - 2 * {wall}\n"
        f'outer = (cq.Workplane("XY").circle({bd} / 2)'
        f".workplane(offset={h}).circle({td} / 2).loft())\n"
        f'cavity = (cq.Workplane("XY").circle(in_bot / 2)'
        f".workplane(offset={h} - floor + eps).circle(in_top / 2).loft()"
        f".translate((0, 0, floor)))\n"
        f'drain = (cq.Workplane("XY").circle({dd} / 2)'
        f".extrude(floor + 2 * eps).translate((0, 0, -eps)))\n"
        f"result = outer.cut(cavity).cut(drain)\n"
    )


def _planter_saucer(v: dict[str, float]) -> str:
    # dishes.scad::planter_saucer — outer body minus a catch pocket, plus a raised inner
    # pot-rest rim ring (the two-circle annulus idiom). Cylinders are XY-centered.
    od, h, wall = _f(v["od"]), _f(v["h"]), _f(v["wall"])
    floor_t, rim_h, rim_w = _f(v["floor_t"]), _f(v["rim_h"]), _f(v.get("rim_w", 4.0))
    return (
        f"eps = {_EPS}\n"
        f"pocket_d = {od} - 2 * {wall}\n"
        f"rim_id = pocket_d - 2 * {rim_w}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'pocket = (cq.Workplane("XY").circle(pocket_d / 2)'
        f".extrude({h} - {floor_t} + eps).translate((0, 0, {floor_t})))\n"
        f'rim = (cq.Workplane("XY").circle(pocket_d / 2).circle(rim_id / 2)'
        f".extrude({rim_h} + eps).translate((0, 0, {floor_t} - eps)))\n"
        f"result = body.cut(pocket).union(rim)\n"
    )


def _bonsai_pot(v: dict[str, float]) -> str:
    # dishes.scad::bonsai_pot - box-tray hollowed to a soil pocket (floor = wall thick), minus a
    # FIXED 2x2 grid of base drain holes. Each XY-centered drain bore spans -eps (open air below)
    # up into the open pocket cavity, so it never touches the outer envelope.
    length, width, h = _f(v["length"]), _f(v["width"]), _f(v["h"])
    t, dd = _f(v["wall"]), _f(v["drain_d"])
    return (
        f"eps = {_EPS}\n"
        f"pocket_l = {length} - 2 * {t}\n"
        f"pocket_w = {width} - 2 * {t}\n"
        f"pocket_depth = {h} - {t}\n"
        f'outer = cq.Workplane("XY").box({length}, {width}, {h}, {_CF})\n'
        f'pocket = (cq.Workplane("XY")'
        f".box(pocket_l, pocket_w, pocket_depth + eps, {_CF})"
        f".translate(({t}, {t}, {t})))\n"
        f"result = outer.cut(pocket)\n"
        f'drill = cq.Workplane("XY").circle({dd} / 2).extrude({t} + 2 * eps)\n'
        f"for dx in ({length} * 0.3, {length} * 0.7):\n"
        f"    for dy in ({width} * 0.3, {width} * 0.7):\n"
        f"        result = result.cut(drill.translate((dx, dy, -eps)))\n"
    )


def _succulent_pot(v: dict[str, float]) -> str:
    # dishes.scad::succulent_pot — an n-gon (facets-sided) prism hollowed to a top-open soil
    # pocket above a wall-thick floor, minus one center round drain through that floor. The
    # outer prism is .polygon(facets, od) [XY-centered, vertices on the across-corners od circle],
    # so od is the across-corners diameter; the default octagon (facets % 4 == 0) fills the bbox
    # to exactly [od, od, h] and other facet counts inscribe WITHIN that od circle (never past it),
    # so facets is inert to the envelope (drawer_divider precedent). The pocket bore is the same
    # facets-gon at od - 2*wall, floor at z = wall, over-cut UP by eps into the open air above the
    # rim. The drain over-cuts -eps below the base and +eps into the pocket so both faces are clean.
    od, h, wall = _f(v["od"]), _f(v["h"]), _f(v["wall"])
    n = int(round(float(v["facets"])))
    dd = _f(v["drain_d"])
    return (
        f"eps = {_EPS}\n"
        f'body = cq.Workplane("XY").polygon({n}, {od}).extrude({h})\n'
        f'pocket = (cq.Workplane("XY").polygon({n}, {od} - 2 * {wall})'
        f".extrude({h} - {wall} + eps).translate((0, 0, {wall})))\n"
        f'drain = (cq.Workplane("XY").circle({dd} / 2)'
        f".extrude({wall} + 2 * eps).translate((0, 0, -eps)))\n"
        f"result = body.cut(pocket).cut(drain)\n"
    )


# --- #19 slice 7: flat decor + ornaments (dishes.scad) -------------------------------


def _coaster_with_rim(v: dict[str, float]) -> str:
    # dishes.scad::coaster_with_rim — solid outer cylinder minus a shallow top pocket that
    # leaves a rim_w-wide rim wall and a floor. The pocket floor sits at z = h - rim_h; the
    # cut over-cuts UP by eps into the open air above the rim (never past h), so the envelope
    # stays exactly [od, od, h] and the floor stays solid. Cylinders are XY-centered.
    od, h = _f(v["od"]), _f(v["h"])
    rim_w, rim_h = _f(v["rim_w"]), _f(v["rim_h"])
    return (
        f"eps = {_EPS}\n"
        f"pocket_floor = {h} - {rim_h}\n"
        f'body = cq.Workplane("XY").circle({od} / 2).extrude({h})\n'
        f'pocket = (cq.Workplane("XY").circle(({od} - 2 * {rim_w}) / 2)'
        f".extrude({rim_h} + eps).translate((0, 0, pocket_floor)))\n"
        f"result = body.cut(pocket)\n"
    )


def _trivet(v: dict[str, float]) -> str:
    # dishes.scad::hotplate_trivet — a square slab raised on four corner feet, with a FIXED
    # grid x grid lattice of square through-slots. grid/foot_d/inset are fixed internals (the
    # count is inert to the envelope, the drawer_divider precedent), so the bbox is exactly
    # [size, size, plate_t + foot_h]. The plate sits on the feet (z = foot_h .. foot_h+plate_t);
    # each slot over-cuts eps below AND above the plate into the open air on both open ends.
    size, pt = _f(v["size"]), _f(v["plate_t"])
    sw, fh = _f(v["slot_w"]), _f(v["foot_h"])
    grid = 4
    foot_d = 12.0
    return (
        f"eps = {_EPS}\n"
        f"foot_r = {foot_d} / 2\n"
        f"inset = foot_r + 4\n"
        f"pitch = {size} / ({grid} + 1)\n"
        f'result = (cq.Workplane("XY").box({size}, {size}, {pt}, {_CF})'
        f".translate((0, 0, {fh})))\n"
        f"for fx in (inset, {size} - inset):\n"
        f"    for fy in (inset, {size} - inset):\n"
        f'        foot = (cq.Workplane("XY").circle(foot_r).extrude({fh} + eps)'
        f".translate((fx, fy, 0)))\n"
        f"        result = result.union(foot)\n"
        f"for i in range(1, {grid} + 1):\n"
        f"    for j in range(1, {grid} + 1):\n"
        f'        slot = (cq.Workplane("XY").box({sw}, {sw}, {pt} + 2 * eps, {_CF})'
        f".translate((i * pitch - {sw} / 2, j * pitch - {sw} / 2, {fh} - eps)))\n"
        f"        result = result.cut(slot)\n"
    )


def _bookend(v: dict[str, float]) -> str:
    # dishes.scad::l_bookend — vertical upright slab + horizontal base foot, box union,
    # corner-at-origin. The base over-spans the upright in X (overlap interior to the union),
    # so the two slabs fuse with no z-fight gap and the envelope stays [base_len, width, height].
    h, w = _f(v["height"]), _f(v["width"])
    bl, ut, bt = _f(v["base_len"]), _f(v["upright_t"]), _f(v["base_t"])
    return (
        f'upright = cq.Workplane("XY").box({ut}, {w}, {h}, {_CF})\n'
        f'base = cq.Workplane("XY").box({bl}, {w}, {bt}, {_CF})\n'
        f"result = upright.union(base)\n"
    )


def _geometric_wall_tile(v: dict[str, float]) -> str:
    # dishes.scad::geometric_wall_tile — flat backer (side x side x base_t) + a raised square
    # border frame (border_w wide, border_h tall) rising from the backer top. The frame is the
    # outer block minus an inner window; the inner cut over-cuts DOWN -eps into the backer (clean
    # fuse) and UP +eps into the open air above the rim (never past a documented face), so the
    # envelope is exactly [side, side, base_t + border_h].
    side, base_t = _f(v["side"]), _f(v["base_t"])
    bw, bh = _f(v["border_w"]), _f(v["border_h"])
    return (
        f"eps = {_EPS}\n"
        f'backer = cq.Workplane("XY").box({side}, {side}, {base_t}, {_CF})\n'
        f'frame = (cq.Workplane("XY").box({side}, {side}, {bh}, {_CF}).cut(\n'
        f'    cq.Workplane("XY")'
        f".box({side} - 2 * {bw}, {side} - 2 * {bw}, {bh} + 2 * eps, {_CF})"
        f".translate(({bw}, {bw}, -eps)))"
        f".translate((0, 0, {base_t})))\n"
        f"result = backer.union(frame)\n"
    )


def _tile_connector_clip(v: dict[str, float]) -> str:
    # dishes.scad::tile_connector_clip — a flat dogbone connector bar minus two side notches
    # that narrow the central neck. Mirrors the library module corner-for-corner: the two end
    # tongues keep the full width (so the Y envelope = width), and the notches over-cut OUTWARD
    # past the side faces (never past the X/Z faces). bbox = [length, width, thick].
    length, width = _f(v["length"]), _f(v["width"])
    neck_w, thick, tongue_l = _f(v["neck_w"]), _f(v["thick"]), _f(v["tongue_l"])
    return (
        f"eps = {_EPS}\n"
        f"side = ({width} - {neck_w}) / 2\n"
        f"neck_l = {length} - 2 * {tongue_l}\n"
        f'bar = cq.Workplane("XY").box({length}, {width}, {thick}, {_CF})\n'
        # -Y side notch across the central span, over-cut down past the -Y face by eps
        f'notch_lo = (cq.Workplane("XY").box(neck_l, side + eps, {thick} + 2 * eps, {_CF})'
        f".translate(({tongue_l}, -eps, -eps)))\n"
        # +Y side notch across the central span, over-cut up past the +Y face by eps
        f'notch_hi = (cq.Workplane("XY").box(neck_l, side + eps, {thick} + 2 * eps, {_CF})'
        f".translate(({tongue_l}, {width} - side, -eps)))\n"
        f"result = bar.cut(notch_lo).cut(notch_hi)\n"
    )


def _ornament_blank(v: dict[str, float]) -> str:
    # dishes.scad::medallion_blank — a solid disc (diameter x thick), XY-centered, with one
    # vertical hanging hole bored through near the top edge. The hole center sits off +Y at
    # y = diameter/2 - rim_margin - hole_d/2, so its top reaches only y = diameter/2 - rim_margin
    # (inside the edge) and the footprint stays [diameter, diameter]. The disc extrudes z=0..thick;
    # the bore over-cuts -eps below and +eps above into open air, so both faces are clean.
    dia, t = _f(v["diameter"]), _f(v["thick"])
    hd, rim = _f(v["hole_d"]), _f(v["rim_margin"])
    return (
        f"eps = {_EPS}\n"
        f"hole_y = {dia} / 2 - {rim} - {hd} / 2\n"
        f'disc = cq.Workplane("XY").circle({dia} / 2).extrude({t})\n'
        f'hole = (cq.Workplane("XY").circle({hd} / 2).extrude({t} + 2 * eps)'
        f".translate((0, hole_y, -eps)))\n"
        f"result = disc.cut(hole)\n"
    )


def _ornament_cap(v: dict[str, float]) -> str:
    # dishes.scad::ornament_cap — solid cap cylinder minus a bottom ornament-neck bore, plus a
    # vertical hang-loop annulus standing on the cap top. Cylinders are XY-centered. The loop is
    # the two-circle annulus idiom extruded along its thickness loop_t then stood vertical by
    # rotating -90 about X (a +Z extrusion points +Y, ring plane -> XZ). It is centered in Y over
    # the cap and embedded a hair (embed) into the crown so OCCT fuses cleanly; the ring TOP lands
    # at ~cap_h + loop_od (within the 0.5 mm bench tol of the analytic [cap_d, cap_d, cap_h+loop_od]).
    cap_d, cap_h, neck_d = _f(v["cap_d"]), _f(v["cap_h"]), _f(v["neck_d"])
    loop_od, loop_t = _f(v["loop_od"]), _f(v["loop_t"])
    return (
        f"eps = {_EPS}\n"
        f"loop_id = {loop_od} - 2 * {loop_t}\n"
        f'body = cq.Workplane("XY").circle({cap_d} / 2).extrude({cap_h})\n'
        # neck bore: open at the BOTTOM, over-cut DOWN by eps into open air below the base,
        # leaving a >=2 mm solid crown (never reaches the cap top).
        f'bore = (cq.Workplane("XY").circle({neck_d} / 2)'
        f".extrude({cap_h} - 2 + eps).translate((0, 0, -eps)))\n"
        f"cap = body.cut(bore)\n"
        f"embed = 0.2\n"
        f'loop = (cq.Workplane("XY").circle({loop_od} / 2).circle(loop_id / 2)'
        f".extrude({loop_t})"
        f".rotate((0, 0, 0), (1, 0, 0), -90)"
        f".translate((0, {loop_t} / 2, {cap_h} + {loop_od} / 2 - embed)))\n"
        f"result = cap.union(loop)\n"
    )


def _gift_box_lid(v: dict[str, float]) -> str:
    # dishes.scad::gift_box_lid — a tray BASE + a taller shoulder LID, two open-top walled boxes
    # side by side along X (gap apart). bbox = [2*width + gap, depth, lid_h]. Each is a corner-at-
    # origin box (via _CF) cut by its cavity; the lid bore = base outer footprint + a slip-fit
    # clearance, centered and STRICTLY inside the lid wall, then the lid is translated +X by
    # width + gap. result is the union of the two disjoint shells (the propagation_station idiom).
    w, d = _f(v["width"]), _f(v["depth"])
    bh, lh = _f(v["base_h"]), _f(v["lid_h"])
    t, gap = _f(v["wall"]), _f(v.get("gap", 8.0))
    fit = _f(0.4)  # diametral slip-fit clearance, matches the module
    return (
        f"eps = {_EPS}\n"
        f"fit = {fit}\n"
        f'base = cq.Workplane("XY").box({w}, {d}, {bh}, {_CF})\n'
        f'base_cav = (cq.Workplane("XY")'
        f".box({w} - 2 * {t}, {d} - 2 * {t}, {bh} - {t} + eps, {_CF})"
        f".translate(({t}, {t}, {t})))\n"
        f"base = base.cut(base_cav)\n"
        f"bore_w = {w} - 2 * {t} + fit\n"
        f"bore_d = {d} - 2 * {t} + fit\n"
        f'lid = cq.Workplane("XY").box({w}, {d}, {lh}, {_CF})\n'
        f'lid_cav = (cq.Workplane("XY")'
        f".box(bore_w, bore_d, {lh} - {t} + eps, {_CF})"
        f".translate((({w} - bore_w) / 2, ({d} - bore_d) / 2, {t})))\n"
        f"lid = lid.cut(lid_cav).translate(({w} + {gap}, 0, 0))\n"
        f"result = base.union(lid)\n"
    )


def _jar_lid(v: dict[str, float]) -> str:
    # dishes.scad::jar_lid — a top disc (outer_d x top_t) on top, with a concentric down-skirt
    # annular ring (skirt_d OD, skirt_wall thick, skirt_h tall) hanging below it to cap a jar
    # rim. Both the disc and the skirt are XY-centered (matches OpenSCAD's cylinder()); the skirt
    # is the two-circle annulus idiom (OD skirt_d, bore skirt_d - 2*skirt_wall). The skirt over-
    # cuts +eps UP into the disc solid so the two fuse without a z-fight gap. skirt_d is pinned
    # <= outer_d (the disc is the widest part), so the envelope is exactly
    # [outer_d, outer_d, top_t + skirt_h].
    od, tt = _f(v["outer_d"]), _f(v["top_t"])
    sd, sh, sw = _f(v["skirt_d"]), _f(v["skirt_h"]), _f(v["skirt_wall"])
    return (
        f"eps = {_EPS}\n"
        f"skirt_id = {sd} - 2 * {sw}\n"
        f'disc = (cq.Workplane("XY").circle({od} / 2)'
        f".extrude({tt}).translate((0, 0, {sh})))\n"
        f'skirt = (cq.Workplane("XY").circle({sd} / 2).circle(skirt_id / 2)'
        f".extrude({sh} + eps))\n"
        f"result = disc.union(skirt)\n"
    )


# Keyed by TemplateFamily.name. A family absent here simply has no STEP twin yet —
# test_every_shipped_family_has_a_step_emitter fails loud if a shipped family is missing.
_EMITTERS: dict[str, Callable[[dict[str, float]], str]] = {
    "snap_box": _snap_box,
    "box": _open_box,
    "enclosure": _enclosure,
    "tube": _tube,
    "wall_hook": _wall_hook,
    "cable_clip": _cable_clip,
    "drawer_divider": _drawer_divider,
    "pegboard_hook": _pegboard_hook,
    "spool_holder": _spool_holder,
    "l_bracket": _l_bracket,
    "picture_frame": _picture_frame,
    "certificate_frame": _picture_frame,  # same geometry, document-proportioned defaults
    "mat_board": _mat_board,
    "floating_frame": _floating_frame,
    "shadow_box_frame": _shadow_box_frame,
    "lithophane_frame": _lithophane_frame,
    "sawtooth_hanger": _sawtooth_hanger,
    "keyhole_hanger_plate": _keyhole_hanger_plate,
    "hidden_rod_shelf_bracket": _hidden_rod_shelf_bracket,
    "ring_dish": _ring_dish,
    "incense_cone_holder": _incense_cone_holder,
    "incense_stick_holder": _incense_stick_holder,
    "catchall_tray": _catchall_tray,
    "soap_dish": _soap_dish,
    "handled_tray": _handled_tray,
    "zen_garden_tray": _zen_garden_tray,
    # #19 slice 6: holders/cups + planters
    "tealight_holder": _tealight_holder,
    "taper_candle_holder": _taper_candle_holder,
    "luminary_base": _luminary_base,
    "bud_vase_sleeve": _bud_vase_sleeve,
    "pencil_cup": _pencil_cup,
    "propagation_station": _propagation_station,
    "planter_pot": _planter_pot,
    "planter_saucer": _planter_saucer,
    "bonsai_pot": _bonsai_pot,
    "succulent_pot": _succulent_pot,
    # #19 slice 7: flat decor + ornaments (keyed by family name; trivet's module is hotplate_trivet,
    # bookend's is l_bookend, ornament_blank's is medallion_blank)
    "coaster_with_rim": _coaster_with_rim,
    "trivet": _trivet,
    "bookend": _bookend,
    "geometric_wall_tile": _geometric_wall_tile,
    "tile_connector_clip": _tile_connector_clip,
    "ornament_blank": _ornament_blank,
    "ornament_cap": _ornament_cap,
    "gift_box_lid": _gift_box_lid,
    "jar_lid": _jar_lid,
}


def step_supported(family_name: str) -> bool:
    """Whether a family has a trusted CadQuery twin (and so can export .STEP)."""
    return family_name in _EMITTERS


def emit_cadquery(family: TemplateFamily, values: dict[str, float]) -> str | None:
    """The trusted CadQuery script for ``family`` at ``values`` (clamped floats from the
    template engine), or None when the family has no twin. Raises ``TypeError``/
    ``ValueError`` if a value is not numeric — values are data, never code."""
    emitter = _EMITTERS.get(family.name)
    if emitter is None:
        return None
    return emitter(_merged(family, values))
