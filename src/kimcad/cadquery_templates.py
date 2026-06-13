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
