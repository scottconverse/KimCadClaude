"""Deterministic template engine (Stage 5, spec §6.3 — the critical-path module).

The Stage-1..4 engine writes OpenSCAD with the LLM: every render is a model call, so
"drag a slider and watch it change" is impossible (each nudge would round-trip the
model). This module is the deterministic alternative — a registry of *parametric
template families* built on the proven `library/*.scad` modules. The planner picks a
family by ``object_type``; the family maps the plan's named dimensions onto typed,
range-bounded parameters; and emitting OpenSCAD is a pure string substitution (no model
in the loop). That makes a re-render a sub-second, fully-local pass and is what lets
named live sliders re-render instantly.

The LLM-writes-OpenSCAD path stays as the tiered *fallback* for prompts no template
covers — it is never the live-slider path.

Design notes:
- Families are pure DATA (pydantic models), so the same definition drives codegen,
  bbox prediction, and the JSON the web UI needs to render sliders — no per-family code.
- A family's :class:`ParamSpec` ``name`` is exactly the underlying module's parameter
  name, so :func:`emit_scad` is generic: ``module(name=value, ...)``.
- Each family declares its bounding box analytically (:class:`BBoxTerm`), so the gate
  can be targeted at what the template *intends* to build and a render that drifts from
  it fails loudly (mirrors ``tests/test_library_modules.py``).

All linear dimensions are millimeters.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kimcad.ir import DesignPlan


def _fmt(value: float, *, integer: bool = False) -> str:
    """Render a number as a clean OpenSCAD literal: ``80`` not ``80.0``, ``2.5`` kept,
    integer-typed params always whole. Trims float noise to 3 decimals."""
    if integer:
        return str(int(round(value)))
    rounded = round(value, 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _coerce_finite(raw: object, default: float) -> float:
    """Best-effort float, but a non-numeric or non-finite (NaN/inf) input falls back to
    ``default`` — so neither garbage from a live-slider POST nor an inf that slipped
    through a plan can ever reach :func:`emit_scad` (TPL-003)."""
    try:
        num = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return num if math.isfinite(num) else default


def _normalize(text: str) -> str:
    """Lower-case, trim, collapse internal whitespace/underscores/hyphens to single
    spaces — so ``"Wall  Hook"``, ``"wall-hook"`` and ``"wall_hook"`` all match the same
    family alias."""
    return re.sub(r"[\s_\-]+", " ", text.strip().lower())


def _singular(text: str) -> str:
    """A deliberately tiny plural-stripper: drop a trailing ``s`` on words longer than
    three letters (``bins``→``bin``, ``tubes``→``tube``). It handles only simple ``-s``
    plurals; ``-es`` plurals (``boxes``→``box``) can't be stripped without breaking words
    like ``cases``, so those are covered by explicit alias entries instead. Intentionally
    conservative — alias lists carry the real coverage."""
    return text[:-1] if len(text) > 3 and text.endswith("s") else text


class ParamSpec(BaseModel):
    """One typed, range-bounded parameter — a single live slider.

    ``name`` MUST equal the underlying library module's parameter name (so emit is a
    generic ``name=value``). ``dim_keys`` are the :class:`~kimcad.ir.DesignPlan`
    ``dimensions`` keys this parameter is derived from, tried in order; ``bbox_axis`` is
    the fallback onto the plan's ``bounding_box_mm`` when no named dimension matches.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    default: float
    min: float
    max: float
    step: float = 1.0
    unit: str = "mm"
    integer: bool = False
    dim_keys: tuple[str, ...] = ()
    bbox_axis: int | None = None


class BBoxTerm(BaseModel):
    """One term in a family's analytic bounding box: ``coef * value(ref)``. ``ref`` is a
    parameter or fixed-arg name; an empty ``ref`` makes the term the constant ``coef``."""

    model_config = ConfigDict(frozen=True)

    coef: float = 1.0
    ref: str = ""


class TemplateFamily(BaseModel):
    """A parametric family: a library module + its slider parameters + the analytic
    bounding box the module produces. Pure data — no per-family code."""

    model_config = ConfigDict(frozen=True)

    name: str
    summary: str
    object_types: tuple[str, ...]
    library_file: str
    module: str
    params: tuple[ParamSpec, ...]
    # Module args passed on every emit but NOT exposed as sliders (sensible constants).
    fixed_args: dict[str, float] = Field(default_factory=dict)
    # Bounding box per axis as a sum of terms over params + fixed_args.
    bbox_x: tuple[BBoxTerm, ...] = ()
    bbox_y: tuple[BBoxTerm, ...] = ()
    bbox_z: tuple[BBoxTerm, ...] = ()
    # Ordering constraints (small, large, gap, coef): enforce values[small] <= coef*values[large]
    # - gap after clamping, so independent slider ranges can't produce degenerate geometry — a tube
    # whose bore is wider than its wall (coef 1.0), OR a box whose wall is so thick the cavity
    # vanishes into a solid block (coef 0.5: wall <= half the dimension - gap). See _apply_gaps.
    gaps: tuple[tuple[str, str, float, float], ...] = ()
    # Honesty tier surfaced in the library picker (#19). "benchmarked" = what-you-set-is-
    # what-you-get, no hidden fitness caveat. "baseline" = real, gate-verified geometry but a
    # real-world fitness caveat the user must check before trusting it (e.g. thread RELIEF not
    # certified threads, Gridfinity-compatible geometry, a VESA hole pattern, a heat-set pocket
    # sized to a generic insert). The tier is INERT to the Printability Gate — every family,
    # whatever its label, is render-verified against its analytic bbox identically.
    tier: Literal["benchmarked", "baseline"] = "benchmarked"

    def _resolve(self, ref: str, values: dict[str, float]) -> float:
        if ref in values:
            return values[ref]
        if ref in self.fixed_args:
            return self.fixed_args[ref]
        raise KeyError(f"bbox term references unknown name '{ref}' in family '{self.name}'")

    def _axis(self, terms: tuple[BBoxTerm, ...], values: dict[str, float]) -> float:
        return sum(t.coef * (self._resolve(t.ref, values) if t.ref else 1.0) for t in terms)

    def expected_bbox(self, values: dict[str, float]) -> tuple[float, float, float]:
        """The [x, y, z] envelope this family produces for ``values`` — the gate target
        and the truth a real render must match (to float noise)."""
        return (
            self._axis(self.bbox_x, values),
            self._axis(self.bbox_y, values),
            self._axis(self.bbox_z, values),
        )


@dataclass(frozen=True)
class TemplateMatch:
    """A family matched to a plan, with the parameter values derived from it. Carries
    everything the deterministic path needs: the emit, the gate target, and the typed
    parameter snapshot the live-slider UI renders."""

    family: TemplateFamily
    values: dict[str, float]

    def scad(self) -> str:
        return emit_scad(self.family, self.values)

    def expected_bbox(self) -> tuple[float, float, float]:
        return self.family.expected_bbox(self.values)

    def parameters(self) -> list[dict]:
        """The slider snapshot: each parameter's spec plus its current value, as plain
        JSON-able dicts (the shape the web UI consumes). A dimensional parameter also carries
        its ``axis`` (X/Y/Z), so the UI can tag the slider to the viewport's W/D/H pills."""
        out = []
        for p in self.family.params:
            entry = {
                "name": p.name,
                "label": p.label,
                "value": self.values[p.name],
                "min": p.min,
                "max": p.max,
                "step": p.step,
                "unit": p.unit,
                "integer": p.integer,
            }
            if p.bbox_axis is not None:
                entry["axis"] = ("X", "Y", "Z")[p.bbox_axis]
            out.append(entry)
        return out


def emit_scad(family: TemplateFamily, values: dict[str, float]) -> str:
    """Deterministically emit the OpenSCAD that builds ``family`` at ``values`` — a pure
    string substitution, no model call. ``use``s the library file and calls the module
    with every slider parameter (named) plus the family's fixed args."""
    args = [f"{p.name}={_fmt(values[p.name], integer=p.integer)}" for p in family.params]
    args += [f"{k}={_fmt(v)}" for k, v in family.fixed_args.items()]
    return f"use <library/{family.library_file}>;\n{family.module}({', '.join(args)});\n"


def _apply_gaps(family: TemplateFamily, values: dict[str, float]) -> dict[str, float]:
    """Enforce each ``(small, large, gap, coef)`` ordering so ``small <= coef*large - gap``, by
    lowering ``small`` (clamped back into its own range). Mutates and returns ``values``.
    Best-effort: if a too-small ``large`` would push ``small`` below its minimum, ``small``
    stays at its minimum (still the closest legal value). ``coef`` 1.0 is a plain ordering
    (bore < bore); ``coef`` 0.5 keeps a wall under half a dimension so the cavity never collapses
    (ENG-501). Constraints are applied in order, each against the running value, so several
    constraints on one param (a box wall vs width AND depth AND height) converge on the tightest."""
    spec = {p.name: p for p in family.params}
    for small, large, gap, coef in family.gaps:
        if small in values and large in values:
            ceiling = coef * values[large] - gap
            if values[small] > ceiling:
                p = spec[small]
                new_val = _clamp(ceiling, p.min, p.max)
                # An integer-count param (e.g. compartments) must stay whole, so floor the ceiling
                # — half a compartment would round back up and re-introduce the overlap (ENG-505).
                if p.integer:
                    new_val = float(int(new_val))
                values[small] = new_val
    return values


def _finalize(family: TemplateFamily, raw: dict[str, float]) -> dict[str, float]:
    """The shared value tail for both entry points: per parameter, coerce the raw value to a
    finite number (non-numeric/NaN/inf → the family default), clamp it into the parameter's
    range, back-fill any missing key with its default, drop unknown keys, then honor the
    ordering constraints. The single guarantee that only finite, in-range, geometrically-valid
    numbers reach :func:`emit_scad`."""
    out: dict[str, float] = {}
    for p in family.params:
        out[p.name] = _clamp(_coerce_finite(raw.get(p.name, p.default), p.default), p.min, p.max)
    return _apply_gaps(family, out)


def derive_values(family: TemplateFamily, plan: DesignPlan) -> dict[str, float]:
    """Map a plan onto the family's parameters: prefer a named ``dimensions`` key, fall
    back to the matching ``bounding_box_mm`` axis, then the family default — and clamp
    every result into the parameter's range (and honor ordering constraints) so a wild or
    non-finite model number can't escape the slider bounds."""
    raw: dict[str, float] = {}
    for p in family.params:
        value: float | None = None
        for key in p.dim_keys:
            if key in plan.dimensions:
                value = plan.dimensions[key]
                break
        if value is None and p.bbox_axis is not None and plan.bounding_box_mm is not None:
            value = plan.bounding_box_mm[p.bbox_axis]
        if value is not None:  # else _finalize back-fills the family default
            raw[p.name] = value
    return _finalize(family, raw)


def clamp_values(family: TemplateFamily, values: dict[str, float]) -> dict[str, float]:
    """Clamp an externally-supplied set of parameter values (e.g. a live-slider POST)
    into range, ignoring unknown keys, back-filling any missing parameter with its
    default, dropping non-finite input, and honoring ordering constraints. Guarantees a
    complete, in-range, geometrically-valid value set for :func:`emit_scad`."""
    return _finalize(family, values)


class TemplateRegistry:
    """The set of known families, indexed by normalized ``object_type`` alias."""

    def __init__(self, families: tuple[TemplateFamily, ...]):
        self._families = families
        # ENG-504: a family with an empty bbox axis would silently report that axis as 0 mm
        # (an empty sum), so the gate's target under-declares a forgotten dimension. Fail at
        # construction instead of mis-gating at runtime.
        for fam in families:
            for axis, terms in (("x", fam.bbox_x), ("y", fam.bbox_y), ("z", fam.bbox_z)):
                if not terms:
                    raise ValueError(
                        f"family '{fam.name}' has an empty bbox_{axis}; every axis needs at "
                        "least one term or its size silently reads as 0 mm"
                    )
        index: dict[str, TemplateFamily] = {}
        for fam in families:
            for alias in fam.object_types:
                norm = _normalize(alias)
                if norm in index:
                    # Fail loudly rather than silently shadow an earlier family — a
                    # duplicate alias means one family would never match (TPL-002).
                    raise ValueError(
                        f"duplicate template alias '{norm}' claimed by both "
                        f"'{index[norm].name}' and '{fam.name}'"
                    )
                index[norm] = fam
        self._index = index

    def families(self) -> tuple[TemplateFamily, ...]:
        return self._families

    def family(self, name: str) -> TemplateFamily | None:
        return next((f for f in self._families if f.name == name), None)

    def match(self, plan: DesignPlan) -> TemplateMatch | None:
        """Pick a family for the plan's ``object_type`` (exact normalized alias, then a
        conservative singular form), and derive its parameter values. Returns ``None``
        when nothing matches — the caller then falls back to the LLM codegen path."""
        norm = _normalize(plan.object_type)
        fam = self._index.get(norm) or self._index.get(_singular(norm))
        if fam is None:
            return None
        return TemplateMatch(family=fam, values=derive_values(fam, plan))

    def match_family(self, name: str, values: dict[str, float]) -> TemplateMatch | None:
        """Build a match for a named family from an explicit (live-slider) value set."""
        fam = self.family(name)
        if fam is None:
            return None
        return TemplateMatch(family=fam, values=clamp_values(fam, values))


# --- The built-in families ---------------------------------------------------------
# Defaults and bounding boxes are pinned to the values verified by real renders in
# tests/test_library_modules.py, so a family's expected_bbox is the module's measured
# envelope, not a guess.

# A printable linear dimension. QA-502: the X/Y FOOTPRINT is capped at the reference P2S/A1's
# *sliceable* envelope, not the 256 mm physical bed — OrcaSlicer's auto-arrange reserves edge
# clearance (the P2S profile's extruder_clearance_radius is 72 mm), so a ~200 mm footprint fails to
# arrange while ~170 mm reliably slices. Capping the param max here clamps BOTH the slider and an
# LLM-derived value (via _finalize), so a part can't pass the gate then fail in OrcaSlicer. Height
# (Z) is free to the bed height. (The big Elegoo Neptune 4 Max's larger plate is a Stage-10
# per-printer-envelope refinement; 170 is the safe default for the reference machines.)
# QA-502: EVERY outer dimension is capped at the reference P2S/A1's sliceable footprint side
# (~170 mm), not the 256 mm bed. Two reasons compound: (1) OrcaSlicer's auto-arrange reserves edge
# clearance, so the usable plate is well under the physical bed (a 200 mm side fails to arrange);
# and (2) the printability auto-orient ROTATES the part for the best print orientation, so ANY axis
# can become a footprint dimension — height included. Capping all three at 170 guarantees the
# oriented footprint is <= 170x170, which slices (a 170x170x170 cube is verified to slice end to
# end through orient). A per-printer 3-D envelope (the big Elegoo Max plate) is a Stage-10
# refinement; 170 is the safe, conservative default for the reference machines. _FOOTPRINT and
# _HEIGHT are the same cap today — kept as two names for where the axis role is meaningful.
_FOOTPRINT = dict(min=10.0, max=170.0, step=1.0)
_HEIGHT = dict(min=10.0, max=170.0, step=1.0)

# ENG-501: keep a box wall under half of EACH outer dimension (minus a 1 mm minimum cavity) so a
# thick wall on a small box can't collapse the part into a silently-solid block that still gates
# PASS. Applied to both closed (snap_box) and open (box) families.
_BOX_WALL_GAPS = (
    ("wall", "width", 1.0, 0.5),
    ("wall", "depth", 1.0, 0.5),
    ("wall", "height", 1.0, 0.5),
)


def _build_default_families() -> tuple[TemplateFamily, ...]:
    box_like_params = (
        ParamSpec(name="width", label="Width", default=80.0, dim_keys=("width",), bbox_axis=0, **_FOOTPRINT),
        ParamSpec(name="depth", label="Depth", default=60.0, dim_keys=("depth",), bbox_axis=1, **_FOOTPRINT),
        ParamSpec(name="height", label="Height", default=40.0, dim_keys=("height",), bbox_axis=2, **_HEIGHT),
        ParamSpec(
            name="wall", label="Wall thickness", default=2.0, min=0.8, max=8.0, step=0.2,
            dim_keys=("wall", "thickness"),
        ),
    )
    xyz_bbox = (
        (BBoxTerm(ref="width"),),
        (BBoxTerm(ref="depth"),),
        (BBoxTerm(ref="height"),),
    )

    snap_box = TemplateFamily(
        name="snap_box",
        summary="A closed, watertight box sized to its outer envelope.",
        object_types=("box", "boxes", "case", "project box", "closed box", "snap box", "enclosure box"),
        library_file="containers.scad",
        module="snap_box",
        params=box_like_params,
        bbox_x=xyz_bbox[0], bbox_y=xyz_bbox[1], bbox_z=xyz_bbox[2],
        gaps=_BOX_WALL_GAPS,
    )
    open_box = TemplateFamily(
        name="box",
        summary="An open-top walled container (tray / bin).",
        object_types=("open box", "tray", "bin", "open container", "open top box", "container"),
        library_file="box.scad",
        module="box",
        params=(
            ParamSpec(name="width", label="Width", default=60.0, dim_keys=("width",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="depth", label="Depth", default=40.0, dim_keys=("depth",), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="height", label="Height", default=30.0, dim_keys=("height",), bbox_axis=2, **_HEIGHT),
            ParamSpec(
                name="wall", label="Wall thickness", default=2.0, min=0.8, max=8.0, step=0.2,
                dim_keys=("wall", "thickness"),
            ),
        ),
        bbox_x=xyz_bbox[0], bbox_y=xyz_bbox[1], bbox_z=xyz_bbox[2],
        gaps=_BOX_WALL_GAPS,
    )
    enclosure = TemplateFamily(
        name="enclosure",
        summary="A two-part enclosure sized from its internal volume; walls add on every side.",
        object_types=("enclosure", "electronics enclosure", "project enclosure"),
        library_file="containers.scad",
        module="enclosure",
        params=(
            # Inner dims capped at 150 so the OUTER (inner + 2*wall, wall<=8) stays inside the ~170 mm
            # sliceable side on EVERY axis (QA-502) — the auto-orient can rotate any axis onto the bed.
            ParamSpec(name="inner_w", label="Inner width", default=80.0, min=10.0, max=150.0, step=1.0, dim_keys=("inner_w", "width"), bbox_axis=0),
            ParamSpec(name="inner_d", label="Inner depth", default=50.0, min=10.0, max=150.0, step=1.0, dim_keys=("inner_d", "depth"), bbox_axis=1),
            ParamSpec(name="inner_h", label="Inner height", default=30.0, min=10.0, max=150.0, step=1.0, dim_keys=("inner_h", "height"), bbox_axis=2),
            ParamSpec(
                name="wall", label="Wall thickness", default=2.5, min=0.8, max=8.0, step=0.2,
                dim_keys=("wall", "thickness"),
            ),
        ),
        bbox_x=(BBoxTerm(ref="inner_w"), BBoxTerm(coef=2.0, ref="wall")),
        bbox_y=(BBoxTerm(ref="inner_d"), BBoxTerm(coef=2.0, ref="wall")),
        bbox_z=(BBoxTerm(ref="inner_h"), BBoxTerm(coef=2.0, ref="wall")),
    )
    tube = TemplateFamily(
        name="tube",
        summary="A ring / cylindrical spacer or standoff.",
        object_types=("tube", "ring", "spacer", "standoff", "sleeve", "bushing"),
        library_file="containers.scad",
        module="tube",
        params=(
            # od is the footprint (diameter), capped at the sliceable envelope (QA-502).
            ParamSpec(name="od", label="Outer diameter", default=16.0, min=4.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter"), bbox_axis=0),
            ParamSpec(name="id", label="Inner diameter", default=8.0, min=1.0, max=160.0, step=1.0,
                      dim_keys=("id", "inner_diameter", "bore")),
            ParamSpec(name="height", label="Height", default=12.0, min=2.0, max=170.0, step=1.0,
                      dim_keys=("height", "length"), bbox_axis=2),
        ),
        bbox_x=(BBoxTerm(ref="od"),), bbox_y=(BBoxTerm(ref="od"),), bbox_z=(BBoxTerm(ref="height"),),
        # The bore must stay at least 1 mm inside the outer wall or difference() degenerates.
        gaps=(("id", "od", 1.0, 1.0),),
    )
    wall_hook = TemplateFamily(
        name="wall_hook",
        summary="A wall-mounted hook: a screwed-on back plate with an arm projecting out.",
        object_types=("hook", "wall hook", "coat hook", "key hook", "wall mounted hook"),
        library_file="hooks.scad",
        module="wall_hook",
        params=(
            ParamSpec(name="plate_w", label="Plate width", default=25.0, min=12.0, max=120.0, step=1.0,
                      dim_keys=("width", "plate_w"), bbox_axis=0),
            # min=24 (not 20): below 24 the module's arm floor max(2,(plate_h-arm_rise)/2)+arm_rise
            # lifts the true Z top above plate_h, so the analytic (linear) bbox_z would under-report
            # and the gate would fail-closed on an otherwise-fine part (ENG-501). 24 keeps the
            # linear bbox exact across the whole slider range (a 20 mm plate with a 20 mm arm rise
            # is a degenerate hook anyway).
            ParamSpec(name="plate_h", label="Plate height", default=60.0, min=24.0, max=170.0, step=1.0,
                      dim_keys=("height", "plate_h"), bbox_axis=2),
            ParamSpec(name="arm_proj", label="Arm reach", default=35.0, min=10.0, max=120.0, step=1.0,
                      dim_keys=("arm_proj", "projection", "reach", "depth")),
        ),
        fixed_args={"plate_t": 4.0, "screw_d": 4.0, "screw_spacing": 30.0, "arm_rise": 20.0},
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="plate_t"), BBoxTerm(ref="arm_proj")),
        bbox_z=(BBoxTerm(ref="plate_h"),),
    )
    cable_clip = TemplateFamily(
        name="cable_clip",
        summary="A screw-down cable / cord saddle clip.",
        object_types=("cable clip", "cord clip", "wire clip", "cable saddle", "cable holder"),
        library_file="clips.scad",
        module="cable_clip",
        params=(
            ParamSpec(name="cable_d", label="Cable diameter", default=6.0, min=2.0, max=40.0, step=0.5,
                      dim_keys=("cable_d", "cable_diameter", "diameter")),
            ParamSpec(name="width", label="Clip width", default=20.0, min=8.0, max=80.0, step=1.0,
                      dim_keys=("width", "length"), bbox_axis=0),
        ),
        fixed_args={"screw_d": 4.0, "wall": 3.0},
        bbox_x=(BBoxTerm(ref="width"),),
        bbox_y=(BBoxTerm(ref="cable_d"), BBoxTerm(coef=5.0, ref="wall"), BBoxTerm(ref="screw_d")),
        bbox_z=(BBoxTerm(coef=0.5, ref="cable_d"), BBoxTerm(coef=2.0, ref="wall")),
    )
    drawer_divider = TemplateFamily(
        name="drawer_divider",
        summary="A drawer divider — a frame split into equal compartments by cross walls.",
        object_types=("drawer divider", "divider", "drawer organizer", "compartment tray"),
        library_file="organizers.scad",
        module="drawer_divider",
        params=(
            ParamSpec(name="length", label="Length", default=150.0, dim_keys=("length", "width"), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="depth", label="Depth", default=80.0, dim_keys=("depth",), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="height", label="Height", default=50.0, dim_keys=("height",), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="compartments", label="Compartments", default=3.0, min=1.0, max=12.0, step=1.0,
                      unit="", integer=True, dim_keys=("compartments", "sections", "bays")),
        ),
        fixed_args={"panel_t": 2.0},
        bbox_x=(BBoxTerm(ref="length"),), bbox_y=(BBoxTerm(ref="depth"),), bbox_z=(BBoxTerm(ref="height"),),
        # ENG-505: cap the compartment count to the length so the (compartments-1) cross-walls can't
        # consume the frame and overlap into a solid block — keep compartments <= length/4 (with
        # panel_t=2 mm that leaves each bay comfortably wider than a wall).
        gaps=(("compartments", "length", 0.0, 0.25),),
    )

    # --- #19 slice 2: three printable library modules that already shipped UNUSED ---------
    # Their .scad geometry + analytic bbox are pinned by tests/test_library_modules.py; here we
    # expose them as selectable families with trusted CadQuery twins (cadquery_templates.py).

    pegboard_hook = TemplateFamily(
        name="pegboard_hook",
        summary="A hook with two rear pegs that seat into a standard pegboard.",
        object_types=("pegboard hook", "peg hook", "peg board hook", "pegboard"),
        library_file="hooks.scad",
        module="pegboard_hook",
        params=(
            ParamSpec(name="plate_w", label="Plate width", default=30.0, min=16.0, max=120.0,
                      step=1.0, dim_keys=("plate_w", "width"), bbox_axis=0),
            ParamSpec(name="arm_length", label="Hook reach", default=45.0, min=15.0, max=120.0,
                      step=1.0, dim_keys=("arm_length", "reach", "projection", "depth")),
            ParamSpec(name="hole_spacing", label="Peg spacing", default=25.4, min=20.0, max=80.0,
                      step=0.1, dim_keys=("hole_spacing", "spacing")),
            ParamSpec(name="hole_d", label="Peg diameter", default=6.0, min=3.0, max=10.0,
                      step=0.5, dim_keys=("hole_d", "peg_diameter")),
        ),
        # arm_size is fixed, so arm_z0 = max(2, (arm_size+8) - arm_size) = 8 is constant and the
        # bbox stays linear; plate_t and peg_len ride as fixed Y-span terms.
        fixed_args={"plate_t": 5.0, "peg_len": 12.0, "arm_rise": 15.0, "arm_size": 6.0},
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="peg_len"), BBoxTerm(ref="plate_t"), BBoxTerm(ref="arm_length")),
        bbox_z=(BBoxTerm(ref="hole_spacing"), BBoxTerm(ref="arm_size", coef=2.0), BBoxTerm(coef=16.0)),
    )

    spool_holder = TemplateFamily(
        name="spool_holder",
        summary="A wall bracket a filament spool slides onto, with an end stop.",
        object_types=("spool holder", "filament spool holder", "filament holder", "spool bracket"),
        library_file="holders.scad",
        module="spool_holder",
        params=(
            # plate_w min 34 keeps the end-stop flange (arm_d+12 = 32 wide) inside the plate so
            # bbox_x stays exactly plate_w; plate_h min 40 keeps the arm seat above the bed.
            ParamSpec(name="plate_w", label="Plate width", default=60.0, min=34.0, max=120.0,
                      step=1.0, dim_keys=("plate_w", "width"), bbox_axis=0),
            ParamSpec(name="spool_width", label="Spool width", default=70.0, min=20.0, max=120.0,
                      step=1.0, dim_keys=("spool_width",)),
            ParamSpec(name="plate_h", label="Plate height", default=120.0, min=40.0, max=170.0,
                      step=1.0, dim_keys=("plate_h", "height"), bbox_axis=2),
        ),
        fixed_args={"spool_od": 200.0, "screw_d": 4.0, "plate_t": 8.0, "arm_d": 20.0},
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="plate_t"), BBoxTerm(ref="spool_width"), BBoxTerm(coef=15.0)),
        bbox_z=(BBoxTerm(ref="plate_h"),),
    )

    l_bracket = TemplateFamily(
        name="l_bracket",
        summary="An L-shaped mounting bracket with screw holes through both arms.",
        object_types=(
            "l bracket", "bracket", "corner bracket", "angle bracket", "shelf bracket",
            "right angle bracket",
        ),
        library_file="bracket.scad",
        module="l_bracket",
        params=(
            # arm is both the X and Z envelope (like the tube's od on X and Y); thick stays well
            # under arm across the ranges so bbox_x = max(arm, thick) = arm holds.
            ParamSpec(name="arm", label="Arm length", default=40.0, min=20.0, max=120.0,
                      step=1.0, dim_keys=("arm", "length"), bbox_axis=0),
            ParamSpec(name="width", label="Width", default=30.0, min=20.0, max=120.0,
                      step=1.0, dim_keys=("width",), bbox_axis=1),
            ParamSpec(name="thick", label="Thickness", default=4.0, min=3.0, max=10.0,
                      step=0.5, dim_keys=("thick", "thickness", "wall")),
        ),
        fixed_args={"screw": 4.0, "inset": 8.0},
        bbox_x=(BBoxTerm(ref="arm"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="arm"),),
    )

    # --- #19 slice 3: frames (Kim's design world) — frames.scad ------------------------
    # Rectangular frames carry the envelope as opening + 2*border (like the enclosure's
    # inner + 2*wall), so opening/border maxes are chosen to keep the outer envelope <=170.

    picture_frame = TemplateFamily(
        name="picture_frame",
        summary="A picture frame with a back rabbet that seats glass, art, and backing.",
        tier="baseline",
        object_types=("picture frame", "photo frame", "art frame", "rabbet frame", "wall frame"),
        library_file="frames.scad",
        module="picture_frame",
        params=(
            ParamSpec(name="opening_w", label="Opening width", default=90.0, min=20.0, max=140.0,
                      step=1.0, dim_keys=("opening_w", "width")),
            ParamSpec(name="opening_h", label="Opening height", default=130.0, min=20.0, max=140.0,
                      step=1.0, dim_keys=("opening_h", "height")),
            ParamSpec(name="border", label="Border width", default=12.0, min=6.0, max=15.0,
                      step=1.0, dim_keys=("border", "frame_width")),
            ParamSpec(name="rabbet", label="Rabbet depth", default=4.0, min=2.0, max=10.0, step=0.5),
            ParamSpec(name="depth", label="Frame depth", default=10.0, min=5.0, max=30.0,
                      step=1.0, dim_keys=("depth", "thickness")),
        ),
        fixed_args={"lip": 3.0},
        bbox_x=(BBoxTerm(ref="opening_w"), BBoxTerm(ref="border", coef=2.0)),
        bbox_y=(BBoxTerm(ref="opening_h"), BBoxTerm(ref="border", coef=2.0)),
        bbox_z=(BBoxTerm(ref="depth"),),
        # the rabbet must leave a front face (rabbet <= depth - 2)
        gaps=(("rabbet", "depth", 2.0, 1.0),),
    )

    # Same geometry as picture_frame, document-proportioned defaults + its own aliases.
    certificate_frame = TemplateFamily(
        name="certificate_frame",
        summary="A document/diploma frame (wider border, portrait default).",
        tier="baseline",
        object_types=("certificate frame", "diploma frame", "document frame", "award frame",
                      "degree frame"),
        library_file="frames.scad",
        module="picture_frame",
        params=(
            ParamSpec(name="opening_w", label="Opening width", default=120.0, min=20.0, max=140.0,
                      step=1.0, dim_keys=("opening_w", "width")),
            ParamSpec(name="opening_h", label="Opening height", default=140.0, min=20.0, max=140.0,
                      step=1.0, dim_keys=("opening_h", "height")),
            ParamSpec(name="border", label="Border width", default=12.0, min=6.0, max=15.0,
                      step=1.0, dim_keys=("border", "frame_width")),
            ParamSpec(name="rabbet", label="Rabbet depth", default=5.0, min=2.0, max=10.0, step=0.5),
            ParamSpec(name="depth", label="Frame depth", default=12.0, min=5.0, max=30.0,
                      step=1.0, dim_keys=("depth", "thickness")),
        ),
        fixed_args={"lip": 3.0},
        bbox_x=(BBoxTerm(ref="opening_w"), BBoxTerm(ref="border", coef=2.0)),
        bbox_y=(BBoxTerm(ref="opening_h"), BBoxTerm(ref="border", coef=2.0)),
        bbox_z=(BBoxTerm(ref="depth"),),
        gaps=(("rabbet", "depth", 2.0, 1.0),),
    )

    mat_board = TemplateFamily(
        name="mat_board",
        summary="A flat framing mat with a centered window opening.",
        object_types=("mat board", "frame mat", "photo mat", "matte board", "window mat",
                      "passe partout"),
        library_file="frames.scad",
        module="mat_board",
        params=(
            ParamSpec(name="mat_w", label="Mat width", default=130.0, min=40.0, max=170.0,
                      step=1.0, dim_keys=("mat_w", "width"), bbox_axis=0),
            ParamSpec(name="mat_h", label="Mat height", default=160.0, min=40.0, max=170.0,
                      step=1.0, dim_keys=("mat_h", "height"), bbox_axis=1),
            ParamSpec(name="window_w", label="Window width", default=90.0, min=20.0, max=160.0,
                      step=1.0, dim_keys=("window_w",)),
            ParamSpec(name="window_h", label="Window height", default=120.0, min=20.0, max=160.0,
                      step=1.0, dim_keys=("window_h",)),
            ParamSpec(name="mat_t", label="Thickness", default=2.0, min=1.0, max=6.0, step=0.5,
                      bbox_axis=2),
        ),
        bbox_x=(BBoxTerm(ref="mat_w"),),
        bbox_y=(BBoxTerm(ref="mat_h"),),
        bbox_z=(BBoxTerm(ref="mat_t"),),
        # the window must leave a >=5 mm mat border each side
        gaps=(("window_w", "mat_w", 10.0, 1.0), ("window_h", "mat_h", 10.0, 1.0)),
    )

    floating_frame = TemplateFamily(
        name="floating_frame",
        summary="A floating frame: the art sits on a recessed shelf with a shadow gap.",
        tier="baseline",
        object_types=("floating frame", "float frame", "floater frame", "canvas floater",
                      "shadow gap frame"),
        library_file="frames.scad",
        module="floating_frame",
        params=(
            ParamSpec(name="opening_w", label="Art width", default=90.0, min=20.0, max=110.0,
                      step=1.0, dim_keys=("opening_w", "width")),
            ParamSpec(name="opening_h", label="Art height", default=90.0, min=20.0, max=110.0,
                      step=1.0, dim_keys=("opening_h", "height")),
            ParamSpec(name="lip_w", label="Lip width", default=10.0, min=5.0, max=15.0, step=1.0),
            ParamSpec(name="gap", label="Shadow gap", default=5.0, min=2.0, max=8.0, step=0.5),
            ParamSpec(name="depth", label="Frame depth", default=20.0, min=10.0, max=40.0,
                      step=1.0, dim_keys=("depth", "thickness"), bbox_axis=2),
        ),
        fixed_args={"back_t": 3.0},
        bbox_x=(BBoxTerm(ref="opening_w"), BBoxTerm(ref="gap", coef=2.0), BBoxTerm(ref="lip_w", coef=2.0)),
        bbox_y=(BBoxTerm(ref="opening_h"), BBoxTerm(ref="gap", coef=2.0), BBoxTerm(ref="lip_w", coef=2.0)),
        bbox_z=(BBoxTerm(ref="depth"),),
    )

    shadow_box_frame = TemplateFamily(
        name="shadow_box_frame",
        summary="A deep shadow box: solid back, display cavity, and a front glass rabbet.",
        tier="baseline",
        object_types=("shadow box", "shadow box frame", "memory box frame", "display box frame",
                      "deep display frame"),
        library_file="frames.scad",
        module="shadow_box_frame",
        params=(
            ParamSpec(name="opening_w", label="Opening width", default=80.0, min=20.0, max=130.0,
                      step=1.0, dim_keys=("opening_w", "width")),
            ParamSpec(name="opening_h", label="Opening height", default=80.0, min=20.0, max=130.0,
                      step=1.0, dim_keys=("opening_h", "height")),
            ParamSpec(name="border", label="Border width", default=12.0, min=6.0, max=20.0, step=1.0),
            ParamSpec(name="cavity_depth", label="Cavity depth", default=25.0, min=8.0, max=60.0,
                      step=1.0, dim_keys=("cavity_depth", "depth")),
            ParamSpec(name="rabbet", label="Rabbet depth", default=4.0, min=2.0, max=8.0, step=0.5),
        ),
        fixed_args={"back_t": 3.0, "lip": 3.0},
        bbox_x=(BBoxTerm(ref="opening_w"), BBoxTerm(ref="border", coef=2.0)),
        bbox_y=(BBoxTerm(ref="opening_h"), BBoxTerm(ref="border", coef=2.0)),
        bbox_z=(BBoxTerm(ref="cavity_depth"), BBoxTerm(ref="rabbet"), BBoxTerm(ref="back_t")),
    )

    lithophane_frame = TemplateFamily(
        name="lithophane_frame",
        summary="A backlit lithophane frame with a panel rebate and an LED light gap.",
        tier="baseline",
        object_types=("lithophane frame", "litho frame", "backlit frame", "light gap frame",
                      "lit picture frame"),
        library_file="frames.scad",
        module="lithophane_frame",
        params=(
            ParamSpec(name="outer_w", label="Width", default=100.0, min=40.0, max=170.0,
                      step=1.0, dim_keys=("outer_w", "width"), bbox_axis=0),
            ParamSpec(name="outer_h", label="Height", default=120.0, min=40.0, max=170.0,
                      step=1.0, dim_keys=("outer_h", "height"), bbox_axis=1),
            ParamSpec(name="face_rim", label="Face rim", default=8.0, min=4.0, max=20.0, step=1.0),
            ParamSpec(name="light_gap", label="Light gap", default=12.0, min=6.0, max=30.0, step=1.0),
            ParamSpec(name="panel_t", label="Panel thickness", default=3.0, min=1.0, max=6.0, step=0.5),
        ),
        fixed_args={"face_rim_t": 2.0},
        bbox_x=(BBoxTerm(ref="outer_w"),),
        bbox_y=(BBoxTerm(ref="outer_h"),),
        bbox_z=(BBoxTerm(ref="face_rim_t"), BBoxTerm(ref="panel_t"), BBoxTerm(ref="light_gap")),
        # the face rim must leave a window (face_rim <= outer/2 - 2)
        gaps=(("face_rim", "outer_w", 2.0, 0.5), ("face_rim", "outer_h", 2.0, 0.5)),
    )

    # --- #19 slice 4: hangers (Kim's design world) — hangers.scad ----------------------

    sawtooth_hanger = TemplateFamily(
        name="sawtooth_hanger",
        summary="A sawtooth picture hanger — a nail catches any tooth to level the frame.",
        tier="baseline",
        object_types=("sawtooth hanger", "sawtooth picture hanger", "saw tooth hanger",
                      "frame hanger", "toothed hanger"),
        library_file="hangers.scad",
        module="sawtooth_hanger",
        params=(
            ParamSpec(name="plate_w", label="Plate width", default=40.0, min=25.0, max=120.0,
                      step=1.0, dim_keys=("plate_w", "width"), bbox_axis=0),
            ParamSpec(name="plate_t", label="Thickness", default=3.0, min=2.0, max=6.0, step=0.5,
                      bbox_axis=1),
            ParamSpec(name="plate_h", label="Plate height", default=15.0, min=10.0, max=60.0,
                      step=1.0, dim_keys=("plate_h", "height")),
            ParamSpec(name="tooth_count", label="Teeth", default=5.0, min=3.0, max=12.0, step=1.0,
                      unit="", integer=True, dim_keys=("tooth_count", "teeth")),
            ParamSpec(name="tooth_depth", label="Tooth depth", default=4.0, min=2.0, max=8.0,
                      step=0.5),
        ),
        fixed_args={"screw_d": 3.0},
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="plate_t"),),
        bbox_z=(BBoxTerm(ref="plate_h"), BBoxTerm(ref="tooth_depth")),
    )

    keyhole_hanger_plate = TemplateFamily(
        name="keyhole_hanger_plate",
        summary="A flush keyhole plate: drop over a screw head and slide down to lock.",
        tier="baseline",
        object_types=("keyhole hanger", "keyhole plate", "keyhole slot plate", "keyhole mount",
                      "keyhole bracket plate"),
        library_file="hangers.scad",
        module="keyhole_hanger_plate",
        params=(
            ParamSpec(name="plate_w", label="Width", default=30.0, min=20.0, max=100.0, step=1.0,
                      dim_keys=("plate_w", "width"), bbox_axis=0),
            ParamSpec(name="plate_t", label="Thickness", default=4.0, min=3.0, max=8.0, step=0.5,
                      bbox_axis=1),
            ParamSpec(name="plate_h", label="Height", default=50.0, min=35.0, max=150.0, step=1.0,
                      dim_keys=("plate_h", "height"), bbox_axis=2),
            ParamSpec(name="hole_d", label="Screw-head hole", default=10.0, min=6.0, max=16.0,
                      step=0.5, dim_keys=("hole_d",)),
            ParamSpec(name="slot_w", label="Slot width", default=5.0, min=3.0, max=10.0, step=0.5),
        ),
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="plate_t"),),
        bbox_z=(BBoxTerm(ref="plate_h"),),
        # the entry hole + back counterbore (hole_d + 6) must fit the plate width; the slot is
        # narrower than the entry hole.
        gaps=(("hole_d", "plate_w", 1.0, 6.0), ("slot_w", "hole_d", 1.0, 1.0)),
    )

    hidden_rod_shelf_bracket = TemplateFamily(
        name="hidden_rod_shelf_bracket",
        summary="A concealed floating-shelf support: a wall plate with rods into the shelf.",
        tier="baseline",
        object_types=("floating shelf bracket", "hidden shelf bracket", "blind shelf bracket",
                      "concealed shelf support", "rod shelf bracket"),
        library_file="hangers.scad",
        module="hidden_rod_shelf_bracket",
        params=(
            ParamSpec(name="plate_w", label="Plate width", default=80.0, min=40.0, max=160.0,
                      step=1.0, dim_keys=("plate_w", "width"), bbox_axis=0),
            ParamSpec(name="plate_h", label="Plate height", default=40.0, min=25.0, max=120.0,
                      step=1.0, dim_keys=("plate_h", "height"), bbox_axis=2),
            ParamSpec(name="plate_t", label="Plate thickness", default=6.0, min=4.0, max=10.0,
                      step=0.5),
            ParamSpec(name="rod_length", label="Rod length", default=40.0, min=20.0, max=90.0,
                      step=1.0, dim_keys=("rod_length", "reach")),
            ParamSpec(name="rod_d", label="Rod diameter", default=8.0, min=5.0, max=12.0, step=0.5),
        ),
        fixed_args={"screw_d": 4.0},
        bbox_x=(BBoxTerm(ref="plate_w"),),
        bbox_y=(BBoxTerm(ref="plate_t"), BBoxTerm(ref="rod_length")),
        bbox_z=(BBoxTerm(ref="plate_h"),),
    )

    # --- #19 slice 5: zen trays / dishes / incense holders — dishes.scad ----------------
    # Authored + render-verified via the verified-authoring workflow (each module proven
    # watertight at its analytic bbox before integration); twins gate-checked at 0.5mm.

    ring_dish = TemplateFamily(
        name="ring_dish",
        summary="A round trinket / ring dish: a shallow well in a solid puck, with an optional center spike.",
        object_types=("ring dish", "trinket dish", "jewelry dish", "ring holder", "trinket bowl"),
        library_file="dishes.scad",
        module="ring_dish",
        params=(
            ParamSpec(name="od", label="Outer diameter", default=70.0, min=24.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=18.0, min=8.0, max=120.0, step=1.0,
                      dim_keys=("h", "height")),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=1.5, max=10.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="well_depth", label="Well depth", default=12.0, min=3.0, max=110.0, step=1.0,
                      dim_keys=("well_depth", "depth")),
            ParamSpec(name="spike_h", label="Center spike height", default=0.0, min=0.0, max=80.0, step=1.0,
                      dim_keys=("spike_h", "spike")),
        ),
        fixed_args={"spike_d": 6.0},
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"), BBoxTerm(ref="spike_h")),
        gaps=(("wall", "od", 4.0, 0.5), ("well_depth", "h", 2.0, 1.0)),
    )

    incense_cone_holder = TemplateFamily(
        name="incense_cone_holder",
        summary="A round incense-cone burner dish with an ash moat around a dimpled pedestal.",
        object_types=("incense cone holder", "incense cone dish", "cone incense holder",
                      "cone burner", "incense cone burner"),
        library_file="dishes.scad",
        module="incense_cone_holder",
        params=(
            ParamSpec(name="dish_d", label="Dish diameter", default=70.0, min=40.0, max=160.0,
                      step=1.0, dim_keys=("dish_d", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Dish height", default=18.0, min=10.0, max=60.0, step=1.0,
                      dim_keys=("h", "height"), bbox_axis=2),
            ParamSpec(name="ped_d", label="Pedestal diameter", default=28.0, min=12.0, max=148.0,
                      step=1.0, dim_keys=("ped_d", "pedestal_diameter")),
            ParamSpec(name="moat_depth", label="Moat depth", default=8.0, min=3.0, max=58.0,
                      step=0.5, dim_keys=("moat_depth", "moat")),
            ParamSpec(name="dimple_d", label="Cone dimple diameter", default=12.0, min=4.0,
                      max=144.0, step=0.5, dim_keys=("dimple_d", "dimple")),
        ),
        fixed_args={"rim": 4.0},
        bbox_x=(BBoxTerm(ref="dish_d"),),
        bbox_y=(BBoxTerm(ref="dish_d"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(
            ("ped_d", "dish_d", 12.0, 1.0),
            ("dimple_d", "ped_d", 4.0, 1.0),
            ("moat_depth", "h", 2.0, 1.0),
        ),
    )

    incense_stick_holder = TemplateFamily(
        name="incense_stick_holder",
        summary="A low ash boat for stick incense: a trough along its length with a row of stick bores.",
        tier="baseline",
        object_types=(
            "incense stick holder", "incense holder", "incense burner", "stick incense holder",
            "incense ash boat", "incense ash catcher", "joss stick holder",
        ),
        library_file="dishes.scad",
        module="incense_stick_holder",
        params=(
            ParamSpec(name="length", label="Length", default=120.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=40.0, dim_keys=("width", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="h", label="Height", default=12.0, dim_keys=("h", "height"), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="hole_d", label="Stick-bore diameter", default=4.0, min=2.0, max=8.0, step=0.5,
                      dim_keys=("hole_d", "stick_diameter", "diameter")),
            ParamSpec(name="trough_depth", label="Trough depth", default=6.0, min=2.0, max=20.0, step=0.5,
                      dim_keys=("trough_depth",)),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(("hole_d", "width", 1.0, 0.5), ("trough_depth", "h", 2.0, 1.0)),
    )

    catchall_tray = TemplateFamily(
        name="catchall_tray",
        summary="A rounded-rect catch-all valet tray: a walled pocket with a solid floor.",
        object_types=("catchall tray", "catchall", "valet tray", "edc tray", "key tray"),
        library_file="dishes.scad",
        module="catchall_tray",
        params=(
            ParamSpec(name="length", label="Length", default=120.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=90.0, dim_keys=("width", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="h", label="Height", default=25.0, dim_keys=("h", "height"), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=1.5, max=8.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="corner_r", label="Corner radius", default=8.0, min=2.0, max=40.0, step=0.5,
                      dim_keys=("corner_r", "radius", "fillet")),
        ),
        fixed_args={"floor": 2.0},
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(
            ("corner_r", "length", 1.0, 0.5),
            ("corner_r", "width", 1.0, 0.5),
            ("wall", "corner_r", 1.0, 1.0),
        ),
    )

    soap_dish = TemplateFamily(
        name="soap_dish",
        summary="A rectangular draining soap dish: a pocketed tray with floor drain ribs and holes.",
        object_types=("soap dish", "soap holder", "soap saver", "draining soap dish",
                      "soap rest", "bar soap dish"),
        library_file="dishes.scad",
        module="soap_dish",
        params=(
            ParamSpec(name="length", label="Length", default=110.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=80.0, dim_keys=("width", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="h", label="Height", default=22.0, dim_keys=("h", "height"), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=0.8, max=8.0, step=0.2,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="rib_count", label="Drainage ribs", default=4.0, min=1.0, max=12.0, step=1.0,
                      unit="", integer=True, dim_keys=("rib_count", "ribs")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(("wall", "length", 1.0, 0.5), ("wall", "width", 1.0, 0.5), ("wall", "h", 1.0, 0.5)),
    )

    handled_tray = TemplateFamily(
        name="handled_tray",
        summary="A shallow serving tray with two integral grip cut-outs in the end walls.",
        object_types=("handled tray", "serving tray", "carry tray", "tray with handles",
                      "two handled tray"),
        library_file="dishes.scad",
        module="handled_tray",
        params=(
            ParamSpec(name="length", label="Length", default=160.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=120.0, dim_keys=("width", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="h", label="Height", default=40.0, dim_keys=("h", "height"), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=0.8, max=8.0, step=0.2,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="handle_w", label="Handle width", default=70.0, min=10.0, max=140.0,
                      step=1.0, dim_keys=("handle_w", "handle")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(
            ("wall", "length", 1.0, 0.5),
            ("wall", "width", 1.0, 0.5),
            ("wall", "h", 1.0, 0.5),
            ("handle_w", "width", 2.0, 1.0),
        ),
    )

    zen_garden_tray = TemplateFamily(
        name="zen_garden_tray",
        summary="A shallow zen sand garden tray: a rounded-rect tray on four short corner feet.",
        object_types=("zen garden", "sand garden", "zen tray", "sand tray", "meditation tray",
                      "rock garden", "zen garden tray"),
        library_file="dishes.scad",
        module="zen_garden_tray",
        params=(
            ParamSpec(name="length", label="Length", default=120.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("length", "width"), bbox_axis=0),
            ParamSpec(name="width", label="Width", default=90.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("width", "depth"), bbox_axis=1),
            ParamSpec(name="wall_h", label="Rim height", default=18.0, min=6.0, max=60.0, step=1.0,
                      dim_keys=("wall_h", "rim_height", "height")),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=1.5, max=5.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="foot_h", label="Foot height", default=6.0, min=2.0, max=20.0, step=1.0,
                      dim_keys=("foot_h", "foot_height")),
        ),
        fixed_args={"corner_r": 6.0, "foot_d": 10.0},
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="wall_h"), BBoxTerm(ref="foot_h")),
        gaps=(
            ("wall", "wall_h", 1.0, 1.0),
            ("wall", "length", 1.0, 0.5),
            ("wall", "width", 1.0, 0.5),
        ),
    )

    # --- #19 slice 6: holders / cups + planters — dishes.scad --------------------------
    # Authored + render-verified via the verified-authoring workflow (each module proven
    # watertight at its analytic bbox; twins gate-checked at 0.5mm). All in dishes.scad.

    tealight_holder = TemplateFamily(
        name="tealight_holder",
        summary="A tealight / votive holder: a round body with a top pocket that seats a standard ~38-40 mm metal tealight cup.",
        tier="baseline",
        object_types=(
            "tealight holder", "tea light holder", "votive holder", "tealight cup holder",
            "candle tealight holder", "tea candle holder",
        ),
        library_file="dishes.scad",
        module="tealight_holder",
        params=(
            ParamSpec(name="od", label="Outer diameter", default=50.0, min=20.0, max=120.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=20.0, min=10.0, max=80.0, step=1.0,
                      dim_keys=("h", "height")),
            ParamSpec(name="pocket_d", label="Tealight pocket diameter", default=39.5, min=20.0, max=110.0,
                      step=0.5, dim_keys=("pocket_d", "pocket_diameter", "cup_d")),
            ParamSpec(name="pocket_h", label="Tealight pocket depth", default=12.0, min=4.0, max=70.0,
                      step=0.5, dim_keys=("pocket_h", "pocket_depth", "cup_h")),
            ParamSpec(name="wall", label="Rim wall", default=3.0, min=1.5, max=8.0, step=0.5,
                      dim_keys=("wall", "thickness")),
        ),
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # the pocket must leave a rim all round (pocket_d <= od - 2*wall, min wall 1.5 -> gap 3) and a
        # floor under it (pocket_h <= h - 2); both keep the difference() from blowing through the body.
        gaps=(("pocket_d", "od", 3.0, 1.0), ("pocket_h", "h", 2.0, 1.0)),
    )

    # taper_candle_holder: reconstructed (its family_code came back "duplicate_ignored", a race
    # artifact). Mirrors the tealight_holder style — bbox = [base_d, base_d, h], a solid base with a
    # centered top socket; gaps keep a rim around the bore and a floor under it.
    taper_candle_holder = TemplateFamily(
        name="taper_candle_holder",
        summary="A weighted taper candle holder: a solid round base with a centered top socket that grips a standard ~22 mm taper candle.",
        tier="baseline",
        object_types=(
            "taper candle holder", "candle holder", "taper holder", "candlestick",
            "candlestick holder", "dinner candle holder", "candle stick holder",
        ),
        library_file="dishes.scad",
        module="taper_candle_holder",
        params=(
            ParamSpec(name="base_d", label="Base diameter", default=70.0, min=30.0, max=160.0, step=1.0,
                      dim_keys=("base_d", "base_diameter", "diameter", "od", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=40.0, min=15.0, max=120.0, step=1.0,
                      dim_keys=("h", "height")),
            ParamSpec(name="bore_d", label="Candle socket diameter", default=22.0, min=8.0, max=60.0,
                      step=0.5, dim_keys=("bore_d", "bore_diameter", "socket_d", "candle_d")),
            ParamSpec(name="bore_depth", label="Candle socket depth", default=25.0, min=8.0, max=110.0,
                      step=0.5, dim_keys=("bore_depth", "socket_depth", "depth")),
        ),
        bbox_x=(BBoxTerm(ref="base_d"),),
        bbox_y=(BBoxTerm(ref="base_d"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # the socket must leave a rim all round (bore_d <= base_d - 8) and a floor under it
        # (bore_depth <= h - 2), so the difference() never blows through the weighted base.
        gaps=(("bore_d", "base_d", 8.0, 1.0), ("bore_depth", "h", 2.0, 1.0)),
    )

    luminary_base = TemplateFamily(
        name="luminary_base",
        summary="A weighted candle/LED luminary base: an outer cylinder with a center puck cavity and a wider top rim ledge.",
        tier="baseline",
        object_types=("luminary base", "luminary", "candle luminary", "led luminary base",
                      "luminary candle base", "luminary holder", "tealight luminary"),
        library_file="dishes.scad",
        module="luminary_base",
        params=(
            ParamSpec(name="outer_d", label="Outer diameter", default=80.0, min=30.0, max=170.0,
                      step=1.0, dim_keys=("outer_d", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="height", label="Height", default=40.0, min=15.0, max=170.0,
                      step=1.0, dim_keys=("height", "h"), bbox_axis=2),
            ParamSpec(name="cavity_d", label="Cavity diameter", default=52.0, min=20.0, max=150.0,
                      step=1.0, dim_keys=("cavity_d", "cavity_diameter", "puck_d")),
            ParamSpec(name="cavity_h", label="Cavity depth", default=26.0, min=8.0, max=150.0,
                      step=1.0, dim_keys=("cavity_h", "cavity_depth", "puck_h")),
            ParamSpec(name="rim_ledge", label="Rim ledge", default=5.0, min=2.0, max=20.0,
                      step=0.5, dim_keys=("rim_ledge", "ledge")),
        ),
        fixed_args={"ledge_t": 3.0},
        bbox_x=(BBoxTerm(ref="outer_d"),),
        bbox_y=(BBoxTerm(ref="outer_d"),),
        bbox_z=(BBoxTerm(ref="height"),),
        # cavity_d stays inside the outer wall (gap 8 leaves >=4 mm wall each side); the wider
        # rim ledge is additionally clamped inside the body IN the module (ledge_d = min(...,
        # outer_d - 2)), so the top ledge slab can never shave the documented height; cavity_h
        # stays under the height so a >=2 mm floor remains under the puck cavity.
        gaps=(
            ("rim_ledge", "outer_d", 4.0, 0.5),
            ("cavity_d", "outer_d", 8.0, 1.0),
            ("cavity_h", "height", 2.0, 1.0),
        ),
    )

    bud_vase_sleeve = TemplateFamily(
        name="bud_vase_sleeve",
        summary="A printed sleeve that seats a glass test tube as the watertight vessel "
                "(bud vase / reed-diffuser / dry-stem sleeve): an outer cylinder with a vertical bore.",
        tier="baseline",
        object_types=("bud vase sleeve", "bud vase", "test tube vase", "reed diffuser sleeve",
                      "stem vase sleeve", "test tube holder"),
        library_file="dishes.scad",
        module="bud_vase_sleeve",
        params=(
            # od is the footprint (diameter), capped at the sliceable envelope (QA-502).
            ParamSpec(name="od", label="Outer diameter", default=60.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=120.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("h", "height", "length")),
            ParamSpec(name="bore_d", label="Bore diameter", default=26.0, min=8.0, max=160.0, step=1.0,
                      dim_keys=("bore_d", "bore_diameter", "tube_diameter", "bore")),
            ParamSpec(name="bore_depth", label="Bore depth", default=110.0, min=10.0, max=168.0, step=1.0,
                      dim_keys=("bore_depth", "depth", "insert_depth")),
            ParamSpec(name="wall", label="Wall thickness", default=4.0, min=1.5, max=10.0, step=0.5,
                      dim_keys=("wall", "thickness")),
        ),
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # The bore must stay >= 2 mm inside the outer wall (so the wall never breaks) and the
        # bore floor must leave >= 2 mm of solid material under the seated tube.
        gaps=(("bore_d", "od", 2.0, 1.0), ("bore_depth", "h", 2.0, 1.0)),
    )

    pencil_cup = TemplateFamily(
        name="pencil_cup",
        summary="A straight-walled round pen / pencil / brush cup: an outer cylinder hollowed to a deep pocket over a thick floor.",
        object_types=(
            "pencil cup", "pen cup", "pen holder", "pencil holder", "brush cup",
            "pencil cup holder", "desk cup", "pen pot", "pencil pot",
        ),
        library_file="dishes.scad",
        module="pencil_cup",
        params=(
            ParamSpec(name="od", label="Outer diameter", default=70.0, min=24.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=100.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("h", "height", "length")),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=1.5, max=10.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="floor_t", label="Floor thickness", default=4.0, min=1.5, max=20.0, step=0.5,
                      dim_keys=("floor_t", "floor", "base")),
        ),
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # Keep the wall under half the OD (minus a 2 mm minimum bore) so a thick wall on a slim
        # cup can't collapse the pocket into a solid puck; keep the floor under the height (minus
        # a 2 mm minimum pocket) so the cup always has a usable cavity.
        gaps=(("wall", "od", 2.0, 0.5), ("floor_t", "h", 2.0, 1.0)),
    )

    # propagation_station: reconstructed (its family_code came back as the bare name string, a
    # race artifact). From its scad signature + new_modules_call/bbox + notes: a horizontal bar
    # on two end legs with a FIXED 5-bore row; bbox = [length, depth, h + leg_h] (the bar rises
    # from z = leg_h to leg_h + h). tube_d is the only count-relevant slider; bores/leg_w fixed.
    propagation_station = TemplateFamily(
        name="propagation_station",
        summary="A test-tube propagation station: a horizontal bar on two end legs, with a fixed row of vertical tube bores for plant cuttings.",
        tier="baseline",
        object_types=(
            "propagation station", "propagation bar", "cutting propagation station",
            "plant propagation station", "test tube propagation station", "propagation stand",
            "cutting station", "plant cutting holder",
        ),
        library_file="dishes.scad",
        module="propagation_station",
        params=(
            ParamSpec(name="length", label="Length", default=160.0, min=60.0, max=170.0, step=1.0,
                      dim_keys=("length", "width"), bbox_axis=0),
            ParamSpec(name="depth", label="Depth", default=40.0, min=24.0, max=80.0, step=1.0,
                      dim_keys=("depth",), bbox_axis=1),
            ParamSpec(name="h", label="Bar height", default=20.0, min=12.0, max=60.0, step=1.0,
                      dim_keys=("h", "bar_height")),
            ParamSpec(name="tube_d", label="Tube bore diameter", default=24.0, min=8.0, max=40.0,
                      step=0.5, dim_keys=("tube_d", "tube_diameter", "bore_d", "diameter")),
            ParamSpec(name="leg_h", label="Leg height", default=70.0, min=20.0, max=110.0, step=1.0,
                      dim_keys=("leg_h", "leg_height", "height")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="depth"),),
        bbox_z=(BBoxTerm(ref="h"), BBoxTerm(ref="leg_h")),
        # tube_d <= depth - 4 (>=2 mm wall each side across depth) and tube_d <= length/6 (narrower
        # than the inter-bore pitch so the 5 fixed bores cannot overlap).
        gaps=(("tube_d", "depth", 4.0, 1.0), ("tube_d", "length", 0.0, 1.0 / 6.0)),
    )

    planter_pot = TemplateFamily(
        name="planter_pot",
        summary="A tapered plant pot: a frustum wall (wider at the rim) over a flat floor, with a center drain hole.",
        tier="benchmarked",  # what-you-set-is-what-you-get; no hidden fitness caveat (it holds soil/water)
        object_types=(
            "planter pot", "plant pot", "flower pot", "flowerpot", "planter", "nursery pot",
            "tapered pot", "seedling pot",
        ),
        library_file="dishes.scad",
        module="planter_pot",
        params=(
            # top_d is the footprint (the rim is the widest point), so it carries bbox_x/y; it is
            # pinned >= bottom_d by the gap below so the envelope stays linear at [top_d, top_d, h].
            ParamSpec(name="top_d", label="Rim diameter", default=90.0, min=30.0, max=170.0, step=1.0,
                      dim_keys=("top_d", "rim_diameter", "diameter", "od", "width"), bbox_axis=0),
            ParamSpec(name="bottom_d", label="Base diameter", default=70.0, min=30.0, max=160.0, step=1.0,
                      dim_keys=("bottom_d", "base_diameter", "base_d")),
            ParamSpec(name="h", label="Height", default=90.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("h", "height")),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=2.0, max=6.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="drain_d", label="Drain hole diameter", default=12.0, min=4.0, max=20.0, step=0.5,
                      dim_keys=("drain_d", "drain", "drain_diameter", "hole_d")),
        ),
        bbox_x=(BBoxTerm(ref="top_d"),),
        bbox_y=(BBoxTerm(ref="top_d"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(
            # the rim is the widest point: keep bottom_d <= top_d so top_d sets the linear bbox.
            ("bottom_d", "top_d", 0.0, 1.0),
            # keep the wall under half the BASE diameter (the narrow end) so the inner taper never
            # collapses: wall <= bottom_d/2 - 1 -> inner base diameter (bottom_d - 2*wall) >= 2.
            ("wall", "bottom_d", 1.0, 0.5),
            # keep the drain at least 14 mm inside the base diameter so it stays well within the
            # inner floor ring (drain_d <= bottom_d - 14) and never breaks the floor edge.
            ("drain_d", "bottom_d", 14.0, 1.0),
        ),
    )

    planter_saucer = TemplateFamily(
        name="planter_saucer",
        summary="A shallow round drip tray under a plant pot: a catch pocket inside a full-height outer rim, with a raised inner ring the pot rests on above collected water.",
        object_types=("planter saucer", "plant saucer", "pot saucer", "drip tray", "saucer",
                      "plant drip tray", "flower pot saucer"),
        library_file="dishes.scad",
        module="planter_saucer",
        params=(
            ParamSpec(name="od", label="Outer diameter", default=140.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=22.0, min=10.0, max=80.0, step=1.0,
                      dim_keys=("h", "height"), bbox_axis=2),
            ParamSpec(name="wall", label="Wall thickness", default=4.0, min=1.5, max=8.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="floor_t", label="Floor thickness", default=3.0, min=1.5, max=10.0, step=0.5,
                      dim_keys=("floor_t", "floor", "base")),
            ParamSpec(name="rim_h", label="Pot-rest rim height", default=6.0, min=2.0, max=40.0, step=0.5,
                      dim_keys=("rim_h", "rim_height", "rim")),
        ),
        fixed_args={"rim_w": 4.0},
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(
            ("wall", "od", 4.0, 0.5),
            ("floor_t", "h", 2.0, 1.0),
            ("rim_h", "h", 4.0, 1.0),
        ),
    )

    bonsai_pot = TemplateFamily(
        name="bonsai_pot",
        summary="A shallow rectangular bonsai tray-pot: a walled soil pocket over a fixed grid of base drain holes.",
        tier="benchmarked",
        object_types=("bonsai pot", "bonsai tray", "bonsai planter", "bonsai dish",
                      "plant tray", "penjing pot"),
        library_file="dishes.scad",
        module="bonsai_pot",
        params=(
            ParamSpec(name="length", label="Length", default=140.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=100.0, dim_keys=("width", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="h", label="Height", default=35.0, dim_keys=("h", "height"), bbox_axis=2, **_HEIGHT),
            ParamSpec(name="wall", label="Wall thickness", default=4.0, min=1.5, max=8.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            ParamSpec(name="drain_d", label="Drain hole diameter", default=8.0, min=2.0, max=20.0, step=0.5,
                      dim_keys=("drain_d", "drain", "hole_d")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="h"),),
        gaps=(("wall", "length", 1.0, 0.5), ("wall", "width", 1.0, 0.5), ("wall", "h", 1.0, 0.5)),
    )

    succulent_pot = TemplateFamily(
        name="succulent_pot",
        summary="A small faceted (n-gon) succulent pot: a straight-walled prism hollowed to a soil pocket with a center drain hole.",
        # benchmarked: what-you-set-is-what-you-get geometry — no real-world fitness caveat. od is
        # the across-corners diameter and the envelope; facets only re-shapes the prism inside it.
        object_types=(
            "succulent pot", "succulent planter", "cactus pot", "faceted planter",
            "geometric planter", "mini planter", "small planter pot",
        ),
        library_file="dishes.scad",
        module="succulent_pot",
        params=(
            # od is the across-corners (vertex-to-vertex) diameter AND the X/Y footprint, capped at
            # the sliceable envelope (QA-502). The default octagon (facets % 4 == 0) fills the bbox
            # to exactly [od, od, h]; other facet counts inscribe within the od circle, never past it.
            ParamSpec(name="od", label="Outer diameter", default=80.0, min=24.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=75.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("h", "height")),
            ParamSpec(name="wall", label="Wall thickness", default=3.0, min=1.5, max=8.0, step=0.5,
                      dim_keys=("wall", "thickness")),
            # facets is an INTERNAL integer count (number of sides) — it re-shapes the prism inside
            # the od circle but does NOT change the [od, od, h] envelope (drawer_divider precedent),
            # so it carries no bbox_axis and is excluded from the gate target.
            ParamSpec(name="facets", label="Sides", default=8.0, min=3.0, max=12.0, step=1.0,
                      unit="", integer=True, dim_keys=("facets", "sides", "faces")),
            ParamSpec(name="drain_d", label="Drain diameter", default=12.0, min=3.0, max=40.0, step=0.5,
                      dim_keys=("drain_d", "drain", "hole_d")),
        ),
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # Keep the wall under half the diameter so the soil pocket never collapses (wall <= od/2 - 4),
        # and keep the drain comfortably inside the pocket floor (drain_d <= od/2 - 8) so the bore
        # never breaks through the side wall.
        gaps=(("wall", "od", 4.0, 0.5), ("drain_d", "od", 8.0, 0.5)),
    )

    # --- #19 slice 7: flat decor + ornaments — dishes.scad -----------------------------
    # Authored + render-verified via the verified-authoring workflow (each module proven
    # watertight at its analytic bbox; twins gate-checked at 0.5mm). All in dishes.scad.

    coaster_with_rim = TemplateFamily(
        name="coaster_with_rim",
        summary="A round drink coaster with a shallow raised rim to contain condensation: a solid round body with a recessed top pocket inside a rim wall.",
        object_types=(
            "coaster with rim", "drink coaster", "round coaster", "rimmed coaster",
            "condensation coaster", "cup coaster", "beverage coaster", "raised rim coaster",
        ),
        library_file="dishes.scad",
        module="coaster_with_rim",
        params=(
            ParamSpec(name="od", label="Outer diameter", default=90.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="h", label="Height", default=6.0, min=4.0, max=40.0, step=0.5,
                      dim_keys=("h", "height"), bbox_axis=2),
            ParamSpec(name="rim_w", label="Rim width", default=4.0, min=2.0, max=20.0, step=0.5,
                      dim_keys=("rim_w", "rim_width", "wall", "thickness")),
            ParamSpec(name="rim_h", label="Rim height", default=3.0, min=1.0, max=30.0, step=0.5,
                      dim_keys=("rim_h", "rim_height", "rim", "well_depth", "depth")),
            ParamSpec(name="floor_t", label="Floor thickness", default=2.0, min=1.0, max=20.0, step=0.5,
                      dim_keys=("floor_t", "floor", "base")),
        ),
        bbox_x=(BBoxTerm(ref="od"),),
        bbox_y=(BBoxTerm(ref="od"),),
        bbox_z=(BBoxTerm(ref="h"),),
        # Keep the rim wall under half the OD (minus a 2 mm minimum pocket) so a wide rim on a
        # small coaster can't collapse the recess into a solid puck; keep the rim height under the
        # body height (minus a 2 mm minimum floor) so a >=2 mm solid, watertight floor always
        # remains under the condensation pocket (the pocket floor sits at z = h - rim_h).
        gaps=(("rim_w", "od", 2.0, 0.5), ("rim_h", "h", 2.0, 1.0)),
    )

    trivet = TemplateFamily(
        name="trivet",
        summary="A flat square hot-pad: a square slab with a fixed grid of square through-slots, raised on four short corner feet.",
        object_types=("trivet", "hot pad trivet", "hotplate trivet", "pot trivet", "kitchen trivet", "hot pad", "pan rest"),
        library_file="dishes.scad",
        module="hotplate_trivet",
        params=(
            ParamSpec(
                name="size", label="Size (square)", default=140, min=80, max=170, step=1,
                dim_keys=("size", "length", "width", "side"), bbox_axis=0,
            ),
            ParamSpec(
                name="plate_t", label="Plate thickness", default=6, min=2, max=12, step=0.5,
                dim_keys=("plate_t", "thickness", "slab_t"),
            ),
            ParamSpec(
                name="slot_w", label="Slot width", default=10, min=2, max=20, step=0.5,
                dim_keys=("slot_w", "slot", "vent"),
            ),
            ParamSpec(
                name="foot_h", label="Foot height", default=8, min=2, max=16, step=0.5,
                dim_keys=("foot_h", "foot", "standoff", "clearance"),
            ),
        ),
        fixed_args={"fn": 32},
        bbox_x=(BBoxTerm(coef=1.0, ref="size"),),
        bbox_y=(BBoxTerm(coef=1.0, ref="size"),),
        bbox_z=(BBoxTerm(coef=1.0, ref="plate_t"), BBoxTerm(coef=1.0, ref="foot_h")),
        # slot_w must stay under the fixed grid pitch (size/5 = 0.2*size) with a 2 mm web, so the
        # grid x grid through-slots never overlap or reach an outer edge (keeps the slab watertight).
        gaps=(("slot_w", "size", 2.0, 0.2),),
        tier="baseline",
    )

    bookend = TemplateFamily(
        name="bookend",
        summary="An L-shaped bookend: a vertical upright slab joined to a horizontal base foot.",
        tier="baseline",
        object_types=("bookend", "book end", "book stop", "book support"),
        library_file="dishes.scad",
        module="l_bookend",
        params=(
            ParamSpec(name="height", label="Height", default=150.0, min=60.0, max=170.0, step=1.0,
                      dim_keys=("height",), bbox_axis=2),
            ParamSpec(name="width", label="Width", default=120.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("width", "depth"), bbox_axis=1),
            ParamSpec(name="base_len", label="Base length", default=110.0, min=40.0, max=170.0, step=1.0,
                      dim_keys=("base_len", "length", "base"), bbox_axis=0),
            ParamSpec(name="upright_t", label="Upright thickness", default=6.0, min=3.0, max=20.0, step=0.5,
                      dim_keys=("upright_t", "upright", "thickness", "wall")),
            ParamSpec(name="base_t", label="Base thickness", default=5.0, min=3.0, max=20.0, step=0.5,
                      dim_keys=("base_t", "base_thickness", "foot_t")),
        ),
        bbox_x=(BBoxTerm(ref="base_len"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="height"),),
        # The upright thickness stays strictly inside the base length (X axis) and the base
        # thickness strictly inside the height (Z axis), so neither slab thickness can reach the
        # envelope it sits on — bbox stays exactly [base_len, width, height].
        gaps=(("upright_t", "base_len", 2.0, 1.0), ("base_t", "height", 2.0, 1.0)),
    )

    geometric_wall_tile = TemplateFamily(
        name="geometric_wall_tile",
        summary="A square modular wall-art tile: a flat backer with a raised perimeter border so tiles register edge-to-edge.",
        object_types=(
            "geometric wall tile", "wall tile", "modular wall tile", "wall art tile",
            "accent wall tile", "decorative wall tile", "bordered wall tile",
        ),
        library_file="dishes.scad",
        module="geometric_wall_tile",
        params=(
            ParamSpec(name="side", label="Tile side", default=100.0, min=20.0, max=170.0, step=1.0,
                      dim_keys=("side", "width", "length", "size"), bbox_axis=0),
            ParamSpec(name="base_t", label="Backer thickness", default=3.0, min=1.5, max=20.0, step=0.5,
                      dim_keys=("base_t", "base", "backer", "thickness")),
            ParamSpec(name="border_w", label="Border width", default=6.0, min=2.0, max=30.0, step=0.5,
                      dim_keys=("border_w", "border", "frame_width")),
            ParamSpec(name="border_h", label="Border height", default=4.0, min=1.0, max=30.0, step=0.5,
                      dim_keys=("border_h", "border_height", "rim_height", "height")),
        ),
        bbox_x=(BBoxTerm(ref="side"),),
        bbox_y=(BBoxTerm(ref="side"),),
        bbox_z=(BBoxTerm(ref="base_t"), BBoxTerm(ref="border_h")),
        # The border frame must leave an inner window (border_w on each of two opposite edges),
        # so keep border_w under half the side (minus a 2 mm minimum opening) — otherwise the
        # inner square vanishes and the difference() leaves a solid block.
        gaps=(("border_w", "side", 2.0, 0.5),),
    )

    tile_connector_clip = TemplateFamily(
        name="tile_connector_clip",
        summary="A flat dogbone connector clip whose two end tongues slot into grooves on two adjoining tiles.",
        tier="baseline",
        object_types=(
            "tile connector clip", "tile clip", "tile connector", "dogbone clip", "tile joiner clip",
            "panel connector clip", "tile bridge clip", "tile link clip",
        ),
        library_file="dishes.scad",
        module="tile_connector_clip",
        params=(
            ParamSpec(name="length", label="Length", default=60.0, dim_keys=("length",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="width", label="Width", default=24.0, min=10.0, max=80.0, step=1.0,
                      dim_keys=("width", "depth"), bbox_axis=1),
            ParamSpec(name="neck_w", label="Neck width", default=12.0, min=4.0, max=78.0, step=1.0,
                      dim_keys=("neck_w", "neck")),
            ParamSpec(name="thick", label="Thickness", default=4.0, min=2.0, max=12.0, step=0.5,
                      dim_keys=("thick", "thickness"), bbox_axis=2),
            ParamSpec(name="tongue_l", label="Tongue length", default=14.0, min=4.0, max=80.0, step=1.0,
                      dim_keys=("tongue_l", "tongue")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="width"),),
        bbox_z=(BBoxTerm(ref="thick"),),
        # neck stays narrower than the width (>=2 mm shoulder each side, so neck_w < width and the
        # tongues remain the Y envelope); the two tongues must leave a positive neck span.
        gaps=(
            ("neck_w", "width", 2.0, 1.0),
            ("tongue_l", "length", 2.0, 0.5),
        ),
    )

    ornament_blank = TemplateFamily(
        name="ornament_blank",
        summary="A flat round medallion / ornament disc with a top hanging hole, ready for a relief or engraving.",
        object_types=(
            "ornament blank", "ornament disc", "medallion blank", "medallion disc",
            "round ornament", "hanging ornament", "christmas ornament blank",
            "pendant blank", "engraving blank", "relief blank", "name medallion",
        ),
        library_file="dishes.scad",
        module="medallion_blank",
        params=(
            ParamSpec(name="diameter", label="Diameter", default=60.0, min=10.0, max=170.0, step=1.0,
                      dim_keys=("diameter", "od", "outer_diameter", "width"), bbox_axis=0),
            ParamSpec(name="thick", label="Thickness", default=4.0, min=2.0, max=20.0, step=0.5,
                      dim_keys=("thick", "thickness", "height", "h")),
            ParamSpec(name="hole_d", label="Hanging hole diameter", default=4.0, min=1.5, max=20.0,
                      step=0.5, dim_keys=("hole_d", "hole_diameter", "hole")),
            ParamSpec(name="rim_margin", label="Hole rim margin", default=5.0, min=2.0, max=40.0,
                      step=0.5, dim_keys=("rim_margin", "margin", "edge_margin")),
        ),
        fixed_args={},
        bbox_x=(BBoxTerm(ref="diameter"),),
        bbox_y=(BBoxTerm(ref="diameter"),),
        bbox_z=(BBoxTerm(ref="thick"),),
        # Keep the hanging hole wholly inside the disc near the top edge: its top point reaches
        # y = diameter/2 - rim_margin, so the bore + its rim margin must fit within the radius.
        # hole_d <= diameter - 4 (coef 1.0, gap 4) guarantees a slim hole on a small blank can't
        # span the disc; rim_margin <= diameter/2 - 2 (coef 0.5, gap 2) keeps the hole center on
        # the +Y side of the disc center so it stays a top-edge hanging hole, never the middle.
        gaps=(("hole_d", "diameter", 4.0, 1.0), ("rim_margin", "diameter", 2.0, 0.5)),
        tier="benchmarked",
    )

    ornament_cap = TemplateFamily(
        name="ornament_cap",
        summary="A press-fit cap that plugs a sphere ornament, topped by a vertical hang loop.",
        tier="baseline",
        object_types=(
            "ornament cap", "ornament topper", "bauble cap", "sphere ornament cap",
            "ornament hanger cap", "christmas ornament cap",
        ),
        library_file="dishes.scad",
        module="ornament_cap",
        params=(
            ParamSpec(name="cap_d", label="Cap diameter", default=22.0, min=12.0, max=120.0, step=1.0,
                      dim_keys=("cap_d", "cap_diameter", "diameter", "width"), bbox_axis=0),
            ParamSpec(name="cap_h", label="Cap height", default=12.0, min=6.0, max=60.0, step=1.0,
                      dim_keys=("cap_h", "cap_height", "height")),
            ParamSpec(name="neck_d", label="Ornament-neck bore", default=14.0, min=4.0, max=110.0, step=0.5,
                      dim_keys=("neck_d", "neck_diameter", "bore")),
            ParamSpec(name="loop_od", label="Hang-loop diameter", default=14.0, min=6.0, max=120.0, step=1.0,
                      dim_keys=("loop_od", "loop_diameter", "loop")),
            ParamSpec(name="loop_t", label="Hang-loop thickness", default=4.0, min=1.5, max=20.0, step=0.5,
                      dim_keys=("loop_t", "loop_thickness")),
        ),
        bbox_x=(BBoxTerm(ref="cap_d"),),
        bbox_y=(BBoxTerm(ref="cap_d"),),
        bbox_z=(BBoxTerm(ref="cap_h"), BBoxTerm(ref="loop_od")),
        gaps=(
            ("neck_d", "cap_d", 2.0, 1.0),   # the neck bore stays inside the cap wall (neck_d <= cap_d - 2)
            ("loop_od", "cap_d", 0.0, 1.0),  # PIN the loop OD <= cap_d so the X/Y footprint stays exactly cap_d
            ("loop_t", "loop_od", 1.0, 0.5), # keep the ring bore positive: loop_t <= loop_od/2 - 1 (>=2 mm bore)
        ),
    )

    gift_box_lid = TemplateFamily(
        name="gift_box_lid",
        summary="A telescoping two-part gift box printed side by side: a tray base and an overlapping shoulder lid.",
        tier="baseline",
        object_types=("gift box lid", "gift box", "telescoping box", "two part box",
                      "shoulder lid box", "lidded gift box", "keepsake box lid"),
        library_file="dishes.scad",
        module="gift_box_lid",
        params=(
            # width is the per-PART footprint side; the two parts sit side by side along X, so the
            # X envelope is 2*width + gap. Capped at 160 so each printed part stays inside the
            # ~170 mm sliceable side (QA-502) — the composite X is two separate prints OrcaSlicer
            # arranges, not one solid.
            ParamSpec(name="width", label="Width", default=90.0, min=20.0, max=160.0, step=1.0,
                      dim_keys=("width",), bbox_axis=0),
            ParamSpec(name="depth", label="Depth", default=70.0, dim_keys=("depth",), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="base_h", label="Base height", default=35.0, min=10.0, max=160.0, step=1.0,
                      dim_keys=("base_h", "base_height")),
            ParamSpec(name="lid_h", label="Lid height", default=40.0, min=10.0, max=170.0, step=1.0,
                      dim_keys=("lid_h", "lid_height", "height"), bbox_axis=2),
            ParamSpec(name="wall", label="Wall thickness", default=2.0, min=0.8, max=8.0, step=0.2,
                      dim_keys=("wall", "thickness")),
        ),
        fixed_args={"gap": 8.0},
        bbox_x=(BBoxTerm(coef=2.0, ref="width"), BBoxTerm(ref="gap")),
        bbox_y=(BBoxTerm(ref="depth"),),
        bbox_z=(BBoxTerm(ref="lid_h"),),
        # lid_h is PINNED >= base_h so the LID is the taller box and sets the linear Z envelope;
        # the wall stays under half of EVERY box dimension (incl. both heights) so no cavity
        # collapses into a silently-solid block.
        gaps=(
            ("base_h", "lid_h", 0.0, 1.0),
            ("wall", "width", 1.0, 0.5),
            ("wall", "depth", 1.0, 0.5),
            ("wall", "base_h", 1.0, 0.5),
            ("wall", "lid_h", 1.0, 0.5),
        ),
    )

    jar_lid = TemplateFamily(
        name="jar_lid",
        summary="A round press/recess jar lid: a top disc with a down-skirt ring that caps a jar rim.",
        tier="baseline",
        object_types=(
            "jar lid", "mason jar lid", "press lid", "recess lid", "jar cap",
            "canister lid", "bottle cap lid", "vessel lid",
        ),
        library_file="dishes.scad",
        module="jar_lid",
        params=(
            ParamSpec(name="outer_d", label="Lid diameter", default=70.0, min=20.0, max=170.0,
                      step=1.0, dim_keys=("outer_d", "diameter", "lid_diameter", "width"), bbox_axis=0),
            ParamSpec(name="top_t", label="Top thickness", default=4.0, min=1.5, max=12.0, step=0.5,
                      dim_keys=("top_t", "top_thickness", "lid_thickness")),
            ParamSpec(name="skirt_d", label="Skirt diameter", default=64.0, min=18.0, max=170.0,
                      step=1.0, dim_keys=("skirt_d", "rim_diameter", "mouth_diameter")),
            ParamSpec(name="skirt_h", label="Skirt height", default=12.0, min=3.0, max=60.0, step=1.0,
                      dim_keys=("skirt_h", "skirt_height", "rim_height", "height")),
            ParamSpec(name="skirt_wall", label="Skirt wall", default=3.0, min=1.0, max=8.0, step=0.5,
                      dim_keys=("skirt_wall", "wall", "thickness")),
        ),
        bbox_x=(BBoxTerm(ref="outer_d"),),
        bbox_y=(BBoxTerm(ref="outer_d"),),
        bbox_z=(BBoxTerm(ref="top_t"), BBoxTerm(ref="skirt_h")),
        # The disc is the widest part: pin the skirt OD <= the lid OD so the envelope stays
        # [outer_d, outer_d, ...]. Keep the skirt wall under half the skirt radius (skirt_wall <=
        # skirt_d/4 - 1) so the annular bore can never collapse into a solid puck.
        gaps=(("skirt_d", "outer_d", 0.0, 1.0), ("skirt_wall", "skirt_d", 1.0, 0.25)),
    )

    # #19 slice 8: stands / easels + ledges / rails
    wedge_easel_stand = TemplateFamily(
        name="wedge_easel_stand",
        summary="A fixed-angle tabletop easel: a triangular wedge with a front lip to prop a framed photo, tile, or sign.",
        tier="benchmarked",
        object_types=(
            "wedge easel", "tabletop easel", "fixed angle easel", "photo easel stand",
            "tile easel", "sign easel", "desktop easel wedge",
        ),
        library_file="dishes.scad",
        module="wedge_easel_stand",
        params=(
            ParamSpec(name="width", label="Width", default=80.0, dim_keys=("width",), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="back_height", label="Back height", default=70.0, min=10.0, max=150.0, step=1.0,
                dim_keys=("back_height", "height")),
            ParamSpec(name="base_depth", label="Base depth", default=60.0, dim_keys=("base_depth", "depth"), bbox_axis=1, **_FOOTPRINT),
            ParamSpec(name="lip_height", label="Lip height", default=14.0, min=4.0, max=30.0, step=1.0,
                dim_keys=("lip_height", "lip")),
            ParamSpec(name="lip_depth", label="Lip depth", default=10.0, min=4.0, max=40.0, step=1.0,
                dim_keys=("lip_depth",)),
        ),
        bbox_x=(BBoxTerm(ref="width"),),
        bbox_y=(BBoxTerm(ref="base_depth"),),
        bbox_z=(BBoxTerm(ref="back_height"), BBoxTerm(ref="lip_height")),
        # the lip must stay inside the base footprint so it never extends the Y envelope
        gaps=(("lip_depth", "base_depth", 2.0, 1.0),),
    )

    display_riser = TemplateFamily(
        name="display_riser",
        summary="A tiered stepped pedestal that elevates a displayed piece: stacked centered slabs, bottom widest, each stepped in.",
        object_types=(
            "display riser", "tiered riser", "stepped riser", "stepped pedestal",
            "tiered pedestal", "display pedestal", "stepped display riser",
        ),
        library_file="dishes.scad",
        module="display_riser",
        params=(
            ParamSpec(name="base_w", label="Base width", default=90.0, min=30.0, max=170.0, step=1.0,
                dim_keys=("base_w", "width"), bbox_axis=0),
            ParamSpec(name="base_d", label="Base depth", default=70.0, min=30.0, max=170.0, step=1.0,
                dim_keys=("base_d", "depth"), bbox_axis=1),
            ParamSpec(name="tiers", label="Tiers", default=4.0, min=2.0, max=5.0, step=1.0,
                unit="", integer=True, dim_keys=("tiers", "steps", "levels")),
            ParamSpec(name="step_in", label="Step inset", default=8.0, min=2.0, max=25.0, step=0.5,
                dim_keys=("step_in", "inset", "step")),
        ),
        # tier_t FIXED at 8 mm so bbox_z = coef(=tier_t) * tiers stays LINEAR in the integer tiers
        # (tiers * tier_t is otherwise bilinear).
        fixed_args={"tier_t": 8.0},
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_d"),),
        bbox_z=(BBoxTerm(ref="tiers", coef=8.0),),
        # step_in gap-clamped against BOTH base dims so the top tier (base - 2*(tiers-1)*step_in)
        # stays comfortably positive across the whole slider envelope (worst case ~14 mm). The
        # coef/gap are sized for the largest tier count (drawer_divider count-vs-length precedent).
        gaps=(("step_in", "base_w", 2.0, 0.1), ("step_in", "base_d", 2.0, 0.1)),
    )

    slanted_sign_holder = TemplateFamily(
        name="slanted_sign_holder",
        summary="A weighted base block with an interior angled slot that holds a menu / price card at a readable backward tilt.",
        tier="baseline",
        object_types=(
            "slanted sign holder", "card easel", "tabletop sign holder", "menu card holder",
            "price card holder", "table card display", "sloped card holder", "angled sign base",
        ),
        library_file="dishes.scad",
        module="slanted_card_easel",
        params=(
            ParamSpec(name="base_w", label="Base width", default=90.0, min=40.0, max=170.0, step=1.0,
                dim_keys=("base_w", "width"), bbox_axis=0),
            ParamSpec(name="base_depth", label="Base depth", default=40.0, min=20.0, max=120.0, step=1.0,
                dim_keys=("base_depth", "depth")),
            ParamSpec(name="base_height", label="Base height", default=45.0, min=20.0, max=120.0, step=1.0,
                dim_keys=("base_height", "height"), bbox_axis=2),
            ParamSpec(name="slot_w", label="Card slot width", default=4.0, min=2.0, max=10.0, step=0.5,
                dim_keys=("slot_w", "slot", "card_thickness")),
            ParamSpec(name="back_margin", label="Back margin", default=12.0, min=6.0, max=40.0, step=1.0,
                dim_keys=("back_margin", "margin")),
        ),
        fixed_args={"lean_deg": 15.0},
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_depth"), BBoxTerm(ref="back_margin")),
        bbox_z=(BBoxTerm(ref="base_height"),),
        gaps=(("slot_w", "base_depth", 2.0, 1.0), ("back_margin", "base_depth", 0.0, 1.0)),
    )

    desk_nameplate_holder = TemplateFamily(
        name="desk_nameplate_holder",
        summary="A low desk base with a rear leaning wedge: an engraved name strip drops into a near-vertical slot.",
        tier="baseline",
        object_types=(
            "desk nameplate holder", "name plate holder", "name strip stand",
            "desk name plate", "engraved nameplate holder", "name strip display",
        ),
        library_file="dishes.scad",
        module="desk_nameplate_strip_stand",
        params=(
            ParamSpec(name="base_w", label="Base width", default=120.0, min=40.0, max=170.0, step=1.0,
                dim_keys=("base_w", "width", "length"), bbox_axis=0),
            ParamSpec(name="base_depth", label="Base depth", default=45.0, min=20.0, max=90.0, step=1.0,
                dim_keys=("base_depth", "depth"), bbox_axis=1),
            ParamSpec(name="base_height", label="Base height", default=14.0, min=8.0, max=40.0, step=1.0,
                dim_keys=("base_height", "height")),
            ParamSpec(name="slot_w", label="Slot width", default=4.0, min=2.0, max=12.0, step=0.5,
                dim_keys=("slot_w", "strip_thickness", "slot")),
            ParamSpec(name="slot_back_offset", label="Slot back rise", default=30.0, min=10.0, max=130.0,
                step=1.0, dim_keys=("slot_back_offset", "back_offset", "rise")),
        ),
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_depth"),),
        bbox_z=(BBoxTerm(ref="base_height"), BBoxTerm(ref="slot_back_offset")),
    )

    place_card_holder = TemplateFamily(
        name="place_card_holder",
        summary="A small base that stands a folded place card upright in a thin vertical slot.",
        tier="benchmarked",
        object_types=("place card holder", "place card stand", "name card holder",
            "table card holder", "escort card holder", "place card slot"),
        library_file="dishes.scad",
        module="place_card_holder",
        params=(
            ParamSpec(name="base_w", label="Base width", default=60.0, min=20.0, max=170.0, step=1.0,
                dim_keys=("base_w", "width", "length"), bbox_axis=0),
            ParamSpec(name="base_depth", label="Base depth", default=25.0, min=16.0, max=120.0, step=1.0,
                dim_keys=("base_depth", "depth"), bbox_axis=1),
            ParamSpec(name="base_height", label="Base height", default=18.0, min=10.0, max=80.0, step=1.0,
                dim_keys=("base_height", "height"), bbox_axis=2),
            ParamSpec(name="slit_w", label="Slot width", default=2.5, min=1.0, max=6.0, step=0.5,
                dim_keys=("slit_w", "slot_width", "card_thickness")),
            ParamSpec(name="slit_depth", label="Slot depth", default=12.0, min=4.0, max=70.0, step=1.0,
                dim_keys=("slit_depth", "slot_depth")),
        ),
        # end_margin is fixed (Y-end inset that keeps the slot interior along the depth); it never
        # enters the envelope, and pinning it keeps slot_l = base_depth - 2*end_margin linear.
        fixed_args={"end_margin": 6.0},
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_depth"),),
        bbox_z=(BBoxTerm(ref="base_height"),),
        # the slot must leave a wall each side (slit_w <= base_w - 6) and a solid floor
        # (slit_depth <= base_height - 2), so the cut stays strictly interior.
        gaps=(("slit_w", "base_w", 6.0, 1.0), ("slit_depth", "base_height", 2.0, 1.0)),
    )

    picture_ledge_shelf = TemplateFamily(
        name="picture_ledge_shelf",
        summary="A long narrow wall ledge with a raised front lip that holds framed art leaning against the wall.",
        tier="baseline",
        object_types=(
            "picture ledge", "art ledge", "photo ledge", "picture rail shelf",
            "frame ledge shelf", "leaning art ledge", "display ledge shelf",
        ),
        library_file="dishes.scad",
        module="picture_ledge_shelf",
        params=(
            ParamSpec(name="length", label="Length", default=160.0, dim_keys=("length", "width"), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="depth", label="Depth", default=70.0, min=20.0, max=170.0, step=1.0,
                dim_keys=("depth",), bbox_axis=1),
            ParamSpec(name="back_height", label="Back-wall height", default=40.0, min=15.0, max=170.0,
                step=1.0, dim_keys=("back_height", "height"), bbox_axis=2),
            ParamSpec(name="lip_height", label="Front lip height", default=15.0, min=10.0, max=170.0,
                step=1.0, dim_keys=("lip_height", "lip")),
            ParamSpec(name="thk", label="Thickness", default=4.0, min=2.0, max=8.0, step=0.5,
                dim_keys=("thk", "thickness", "wall")),
        ),
        fixed_args={"screw_d": 4.0},
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="depth"),),
        bbox_z=(BBoxTerm(ref="back_height"),),
        # The front lip must not rise above the back wall, so the Z envelope is always
        # back_height (the lip_height term stays OUT of bbox_z, like a pinned secondary feature).
        gaps=(("lip_height", "back_height", 0.0, 1.0),),
    )

    peg_hook_rail = TemplateFamily(
        name="peg_hook_rail",
        summary="A wall back-bar with a fixed row of evenly spaced projecting pegs for coats, towels, or keys.",
        tier="benchmarked",
        object_types=(
            "peg hook rail", "peg rail", "coat peg rail", "towel peg rail",
            "wall peg rail", "shaker peg rail", "key peg rail",
        ),
        library_file="dishes.scad",
        module="peg_hook_rail",
        params=(
            ParamSpec(name="length", label="Bar length", default=160.0, min=40.0, max=170.0,
                step=1.0, dim_keys=("length", "width"), bbox_axis=0),
            ParamSpec(name="bar_h", label="Bar height", default=40.0, min=20.0, max=170.0,
                step=1.0, dim_keys=("bar_h", "height"), bbox_axis=2),
            ParamSpec(name="bar_t", label="Bar thickness", default=12.0, min=6.0, max=30.0,
                step=1.0, dim_keys=("bar_t", "thickness")),
            ParamSpec(name="peg_length", label="Peg length", default=35.0, min=15.0, max=120.0,
                step=1.0, dim_keys=("peg_length", "projection", "reach", "depth")),
            ParamSpec(name="peg_d", label="Peg diameter", default=12.0, min=6.0, max=25.0,
                step=0.5, dim_keys=("peg_d", "peg_diameter", "diameter")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="bar_t"), BBoxTerm(ref="peg_length")),
        bbox_z=(BBoxTerm(ref="bar_h"),),
        # peg_d must fit within the bar height (a centered peg stays inside the Z envelope) AND
        # within the bar length (the inset end pegs at x = length/6 must not overhang the X face,
        # i.e. peg_d <= length/3) so the analytic bbox stays exactly linear across the slider range.
        gaps=(("peg_d", "bar_h", 0.0, 1.0), ("peg_d", "length", 0.0, 0.333)),
    )

    j_decor_hook = TemplateFamily(
        name="j_decor_hook",
        summary="A decorative J-profile robe/towel hook: an extruded J ribbon (back tab, forward bend, an up catch) with a back screw tab.",
        tier="benchmarked",
        object_types=("j hook", "robe hook", "towel hook", "j profile hook", "decorative wall hook", "bathrobe hook"),
        library_file="dishes.scad",
        module="j_decor_hook",
        params=(
            ParamSpec(name="width", label="Hook width", default=60.0, min=10.0, max=120.0, step=1.0,
                dim_keys=("width",), bbox_axis=0),
            ParamSpec(name="back_height", label="Back tab height", default=70.0, min=20.0, max=150.0, step=1.0,
                dim_keys=("back_height", "height"), bbox_axis=2),
            ParamSpec(name="reach", label="Hook reach", default=22.0, min=10.0, max=120.0, step=1.0,
                dim_keys=("reach", "projection", "depth")),
            ParamSpec(name="catch_rise", label="Catch rise", default=18.0, min=5.0, max=80.0, step=1.0,
                dim_keys=("catch_rise", "catch")),
            ParamSpec(name="thk", label="Profile thickness", default=5.0, min=3.0, max=12.0, step=0.5,
                dim_keys=("thk", "thickness", "wall")),
        ),
        fixed_args={"screw_d": 4.0},
        bbox_x=(BBoxTerm(ref="width"),),
        bbox_y=(BBoxTerm(ref="thk"), BBoxTerm(ref="reach")),
        bbox_z=(BBoxTerm(ref="back_height"), BBoxTerm(ref="catch_rise")),
        # back_height pinned >= catch_rise so the front-catch tip (back_height + catch_rise) is always
        # the tallest point and bbox_z stays the linear sum (the wall_hook pin-a-min precedent).
        gaps=(("catch_rise", "back_height", 0.0, 1.0),),
    )

    plate_display_stand = TemplateFamily(
        name="plate_display_stand",
        summary="An upright display stand that grips a decorative plate or tile on edge: a flat "
        "base with a fixed-lean back panel carrying a plate groove.",
        tier="baseline",
        object_types=(
            "plate display stand", "plate stand", "plate easel", "display plate stand",
            "decorative plate stand", "plate holder stand", "tile display stand",
        ),
        library_file="dishes.scad",
        module="plate_display_stand",
        params=(
            ParamSpec(name="base_w", label="Base width", default=90.0, min=40.0, max=170.0, step=1.0,
                dim_keys=("base_w", "width"), bbox_axis=0),
            ParamSpec(name="base_depth", label="Base depth", default=70.0, min=30.0, max=120.0, step=1.0,
                dim_keys=("base_depth", "depth")),
            ParamSpec(name="back_height", label="Back height", default=90.0, min=40.0, max=140.0, step=1.0,
                dim_keys=("back_height", "height")),
            ParamSpec(name="groove_w", label="Plate groove width", default=8.0, min=4.0, max=20.0, step=0.5,
                dim_keys=("groove_w", "plate_thickness", "groove")),
        ),
        # base_h and lean_off are FIXED so the lean angle is fixed and the bbox stays LINEAR
        # (the rear-most/top-most point lands at base_depth + lean_off; the top at base_h +
        # back_height). The back panel thickness (12) and groove depth (6) live inside the module.
        fixed_args={"base_h": 10.0, "lean_off": 24.0},
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_depth"), BBoxTerm(ref="lean_off")),
        bbox_z=(BBoxTerm(ref="base_h"), BBoxTerm(ref="back_height")),
        # The groove must stay narrower than the base width so the back panel keeps a wall each
        # side of the slot (groove_w <= base_w/2 - 2).
        gaps=(("groove_w", "base_w", 2.0, 0.5),),
    )

    # #19 slice 9: frame joinery + profile hangers
    canvas_stretcher_corner = TemplateFamily(
        name="canvas_stretcher_corner",
        summary="An L-shaped mitered corner key that squares and joins two canvas stretcher bars at 90 degrees, with underside tongues that slot into the bar ends.",
        tier="baseline",
        object_types=(
            "canvas stretcher corner", "stretcher corner key", "stretcher bar corner",
            "canvas frame corner key", "stretcher bar joiner", "canvas corner brace",
        ),
        library_file="dishes.scad",
        module="canvas_stretcher_corner",
        params=(
            ParamSpec(name="arm", label="Arm length", default=80.0, min=30.0, max=170.0,
                      step=1.0, dim_keys=("arm", "length"), bbox_axis=0),
            ParamSpec(name="leg_w", label="Leg width", default=18.0, min=10.0, max=40.0,
                      step=1.0, dim_keys=("leg_w", "width")),
            ParamSpec(name="bar_t", label="Bar thickness", default=10.0, min=4.0, max=30.0,
                      step=0.5, dim_keys=("bar_t", "thickness")),
            ParamSpec(name="tongue_l", label="Tongue length", default=40.0, min=10.0, max=80.0,
                      step=1.0, dim_keys=("tongue_l",)),
            ParamSpec(name="tongue_h", label="Tongue height", default=8.0, min=3.0, max=20.0,
                      step=0.5, dim_keys=("tongue_h",)),
        ),
        bbox_x=(BBoxTerm(ref="arm"),),
        bbox_y=(BBoxTerm(ref="arm"),),
        bbox_z=(BBoxTerm(ref="bar_t"), BBoxTerm(ref="tongue_h")),
        # the tongue must stay inside an arm (tongue_l <= arm) so it never overruns the L body
        gaps=(("tongue_l", "arm", 1.0, 1.0),),
    )

    frame_corner_clamp = TemplateFamily(
        name="frame_corner_clamp",
        summary="A right-angle frame glue-up jig: a corner block with two perpendicular jaws holding two mitered pieces square.",
        tier="baseline",
        object_types=(
            "frame corner clamp", "miter corner jig", "frame corner jig",
            "right angle glue jig", "frame assembly jig", "miter glue clamp",
            "corner gluing jig",
        ),
        library_file="dishes.scad",
        module="frame_corner_clamp",
        params=(
            ParamSpec(name="jaw_l", label="Jaw length", default=50.0, min=20.0, max=120.0,
                      step=1.0, dim_keys=("jaw_l", "length"), bbox_axis=0),
            ParamSpec(name="jaw_t", label="Jaw thickness", default=12.0, min=6.0, max=30.0,
                      step=1.0, dim_keys=("jaw_t", "thickness")),
            ParamSpec(name="jaw_h", label="Jaw height", default=20.0, min=10.0, max=60.0,
                      step=1.0, dim_keys=("jaw_h", "height"), bbox_axis=2),
            ParamSpec(name="screw_d", label="Thumbscrew diameter", default=5.0, min=3.0, max=8.0,
                      step=0.5, dim_keys=("screw_d", "screw_diameter")),
            ParamSpec(name="corner", label="Corner block size", default=20.0, min=12.0, max=40.0,
                      step=1.0, dim_keys=("corner", "corner_size")),
        ),
        fixed_args={},
        bbox_x=(BBoxTerm(ref="jaw_l"), BBoxTerm(ref="corner")),
        bbox_y=(BBoxTerm(ref="jaw_l"), BBoxTerm(ref="corner")),
        bbox_z=(BBoxTerm(ref="jaw_h"),),
        # the thumbscrew bore must fit inside the jaw thickness (screw_d <= jaw_t - 2), and the
        # corner block must fully back the jaw (jaw_t <= corner) so the L stays clean.
        gaps=(("screw_d", "jaw_t", 2.0, 1.0), ("jaw_t", "corner", 0.0, 1.0)),
    )

    frame_corner_joiner = TemplateFamily(
        name="frame_corner_joiner",
        summary="A flat under-side spline plate that screws across a 45-degree frame miter to lock two moulding lengths.",
        tier="baseline",
        object_types=(
            "frame corner joiner", "miter joiner plate", "frame miter spline", "corner spline plate",
            "frame joining plate", "miter lock plate",
        ),
        library_file="dishes.scad",
        module="frame_corner_joiner",
        params=(
            ParamSpec(name="plate", label="Plate size", default=50.0, min=24.0, max=170.0, step=1.0,
                      dim_keys=("plate", "size", "width"), bbox_axis=0),
            ParamSpec(name="plate_t", label="Plate thickness", default=4.0, min=2.0, max=12.0, step=0.5,
                      dim_keys=("plate_t", "thickness")),
            ParamSpec(name="screw_d", label="Screw diameter", default=4.0, min=2.0, max=8.0, step=0.5,
                      dim_keys=("screw_d", "screw")),
            ParamSpec(name="screw_inset", label="Screw inset", default=10.0, min=6.0, max=40.0, step=1.0,
                      dim_keys=("screw_inset", "inset")),
            ParamSpec(name="rib_h", label="Registration rib height", default=2.0, min=1.0, max=10.0, step=0.5,
                      dim_keys=("rib_h", "rib")),
        ),
        fixed_args={"rib_w": 4.0},
        bbox_x=(BBoxTerm(ref="plate"),),
        bbox_y=(BBoxTerm(ref="plate"),),
        bbox_z=(BBoxTerm(ref="plate_t"), BBoxTerm(ref="rib_h")),
        # the two diagonal screw bosses must clear each other inside the plate (screw_inset <= plate/2 - 4);
        # the counterbore (screw_d + 4) must fit the plate around each boss (screw_d <= plate/4 - 1).
        gaps=(("screw_inset", "plate", 4.0, 0.5), ("screw_d", "plate", 1.0, 0.25)),
    )

    frame_turn_button = TemplateFamily(
        name="frame_turn_button",
        summary="A rotating frame turn-button: a rounded bar with a center pivot bore and a raised boss that screws to a frame back and pivots to retain the backing board.",
        tier="baseline",
        object_types=(
            "frame turn button", "turn button retainer", "backing board retainer",
            "frame backing button", "art backing turnbutton", "frame back swivel retainer",
        ),
        library_file="dishes.scad",
        module="frame_turn_button",
        params=(
            ParamSpec(name="button_l", label="Button length", default=40.0, min=30.0, max=170.0,
                      step=1.0, dim_keys=("button_l", "length", "width"), bbox_axis=0),
            ParamSpec(name="button_w", label="Button width", default=16.0, min=12.0, max=40.0,
                      step=1.0, dim_keys=("button_w", "width", "depth"), bbox_axis=1),
            ParamSpec(name="button_t", label="Bar thickness", default=4.0, min=2.0, max=10.0,
                      step=0.5, dim_keys=("button_t", "thickness")),
            ParamSpec(name="bore_d", label="Pivot bore diameter", default=4.0, min=2.0, max=8.0,
                      step=0.5, dim_keys=("bore_d", "bore", "screw_d")),
            ParamSpec(name="boss_h", label="Boss height", default=3.0, min=1.0, max=12.0,
                      step=0.5, dim_keys=("boss_h", "boss")),
        ),
        # boss_d is a fixed pivot-boss diameter clamped inside button_w by the module's
        # min(boss_d, button_w - 2), so it never widens the Y envelope; corner_r is a fixed
        # rounding radius <= half the min in-range dimension, so the X/Y extents stay exact.
        fixed_args={"boss_d": 12.0, "corner_r": 4.0},
        bbox_x=(BBoxTerm(ref="button_l"),),
        bbox_y=(BBoxTerm(ref="button_w"),),
        bbox_z=(BBoxTerm(ref="button_t"), BBoxTerm(ref="boss_h")),
    )

    frame_backing_clip = TemplateFamily(
        name="frame_backing_clip",
        summary="A flat stepped offset clip that wedges between a frame rabbet and the backing board to retain it without screws.",
        tier="baseline",
        object_types=(
            "frame backing clip", "backing retainer clip", "rabbet backing clip",
            "offset backing clip", "frame backing retainer", "spring backing clip",
        ),
        library_file="dishes.scad",
        module="frame_backing_clip",
        params=(
            ParamSpec(name="clip_l", label="Clip length", default=30.0, min=15.0, max=80.0,
                      step=1.0, dim_keys=("clip_l", "length"), bbox_axis=0),
            ParamSpec(name="clip_w", label="Clip width", default=16.0, min=8.0, max=80.0,
                      step=1.0, dim_keys=("clip_w", "width"), bbox_axis=1),
            ParamSpec(name="clip_t", label="Material thickness", default=3.0, min=1.5, max=6.0,
                      step=0.5, dim_keys=("clip_t", "thickness", "wall")),
            ParamSpec(name="step", label="Offset step", default=6.0, min=2.0, max=40.0,
                      step=0.5, dim_keys=("step", "offset")),
            ParamSpec(name="tab", label="Retaining tab", default=10.0, min=5.0, max=40.0,
                      step=1.0, dim_keys=("tab",)),
        ),
        bbox_x=(BBoxTerm(ref="clip_l"),),
        bbox_y=(BBoxTerm(ref="clip_w"),),
        bbox_z=(BBoxTerm(ref="clip_t"), BBoxTerm(ref="step")),
        # Keep the stepped profile valid across the whole slider range: the riser starts at
        # x = clip_l - tab - clip_t, which must stay > 0. Cap the tab to half the length and the
        # material thickness to a quarter of the length so clip_l - tab - clip_t >= clip_l/4 + 3.
        gaps=(("tab", "clip_l", 2.0, 0.5), ("clip_t", "clip_l", 1.0, 0.25)),
    )

    wire_loop_hanger = TemplateFamily(
        name="wire_loop_hanger",
        summary="A screw-on plate with an upstanding triangular wire bail for hanging framed art.",
        tier="baseline",
        object_types=(
            "wire loop hanger", "picture wire hanger", "wire bail hanger", "framing wire loop",
            "art wire hanger", "triangle bail hanger",
        ),
        library_file="dishes.scad",
        module="wire_loop_hanger",
        params=(
            ParamSpec(name="base_w", label="Plate width", default=30.0, min=12.0, max=170.0,
                      step=1.0, dim_keys=("base_w", "width"), bbox_axis=0),
            ParamSpec(name="base_t", label="Plate thickness", default=4.0, min=2.0, max=12.0,
                      step=0.5, dim_keys=("base_t", "thickness"), bbox_axis=1),
            ParamSpec(name="base_h", label="Plate height", default=18.0, min=12.0, max=170.0,
                      step=1.0, dim_keys=("base_h", "height")),
            ParamSpec(name="loop_height", label="Loop height", default=22.0, min=10.0, max=120.0,
                      step=1.0, dim_keys=("loop_height", "loop")),
            ParamSpec(name="loop_thk", label="Loop thickness", default=4.0, min=1.5, max=12.0,
                      step=0.5),
        ),
        fixed_args={"screw_d": 4.0},
        bbox_x=(BBoxTerm(ref="base_w"),),
        bbox_y=(BBoxTerm(ref="base_t"),),
        bbox_z=(BBoxTerm(ref="base_h"), BBoxTerm(ref="loop_height")),
        # loop_thk <= base_t keeps the bail inside the plate thickness so the Y envelope stays
        # exactly base_t; loop_thk <= 0.5*loop_height - 0.5 keeps the inner wire-hole triangle
        # valid (the loop bar half-base = loop_height/2 stays wider than the bar wall).
        gaps=(("loop_thk", "base_t", 0.0, 1.0), ("loop_thk", "loop_height", 0.5, 0.5)),
    )

    z_clip_panel_hanger = TemplateFamily(
        name="z_clip_panel_hanger",
        summary="The wall half of a Z-profile interlocking panel clip; the mating half hangs a flat sign/mirror flush.",
        tier="baseline",
        object_types=(
            "z clip", "z clip hanger", "z clip panel hanger", "z bar hanger",
            "interlocking panel clip", "french cleat z clip", "flush mount z clip",
        ),
        library_file="dishes.scad",
        module="z_clip_panel_hanger",
        params=(
            ParamSpec(name="length", label="Length", default=120.0, dim_keys=("length", "width"), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="flange_w", label="Flange width", default=20.0, min=12.0, max=80.0,
                      step=1.0, dim_keys=("flange_w", "flange", "depth")),
            ParamSpec(name="web_h", label="Web height", default=15.0, min=8.0, max=150.0,
                      step=1.0, dim_keys=("web_h", "web", "standoff", "height")),
            ParamSpec(name="thk", label="Material thickness", default=4.0, min=2.0, max=10.0,
                      step=0.5, dim_keys=("thk", "thickness", "wall")),
            ParamSpec(name="screw_d", label="Screw diameter", default=4.0, min=2.0, max=8.0,
                      step=0.5, dim_keys=("screw_d", "screw", "screw_diameter")),
        ),
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="flange_w"), BBoxTerm(ref="thk")),
        bbox_z=(BBoxTerm(ref="web_h"), BBoxTerm(coef=2.0, ref="thk")),
        # Keep the counterbore (screw_d*2) inside the mounting flange so the screw holes never
        # breach a Y face: screw_d <= flange_w/2 - 1 (the wall_hook param-pin precedent — the
        # hole must stay strictly within the flange or the envelope would no longer be linear).
        gaps=(("screw_d", "flange_w", 1.0, 0.5),),
    )

    art_french_cleat_pair = TemplateFamily(
        name="art_french_cleat_pair",
        summary="A matched pair of interlocking 45-degree wall cleats (wall half + art half), printed side by side, to hang and self-level a piece.",
        tier="baseline",
        object_types=(
            "french cleat pair", "art french cleat", "interlocking wall cleat",
            "picture french cleat", "45 degree wall cleat", "art hanging cleat pair",
            "beveled wall cleat",
        ),
        library_file="dishes.scad",
        module="art_french_cleat_pair",
        params=(
            ParamSpec(name="length", label="Length", default=120.0, dim_keys=("length", "width"), bbox_axis=0, **_FOOTPRINT),
            ParamSpec(name="depth", label="Cleat depth", default=22.0, min=12.0, max=80.0, step=1.0,
                      dim_keys=("depth", "cleat_depth")),
            ParamSpec(name="rise", label="Rise", default=18.0, min=12.0, max=170.0, step=1.0,
                      dim_keys=("rise", "height")),
            ParamSpec(name="thick", label="Back thickness", default=6.0, min=3.0, max=10.0, step=0.5,
                      dim_keys=("thick", "thickness", "wall")),
        ),
        fixed_args={"gap": 10.0},
        bbox_x=(BBoxTerm(ref="length"),),
        bbox_y=(BBoxTerm(ref="depth", coef=2.0), BBoxTerm(ref="gap")),
        bbox_z=(BBoxTerm(ref="rise"),),
    )

    picture_rail_hook = TemplateFamily(
        name="picture_rail_hook",
        summary="An over-the-molding picture-rail hook: an inverted-J that hooks over the rail without nails, with a cord eye.",
        tier="baseline",
        object_types=(
            "picture rail hook", "rail hook", "molding hook", "moulding hook",
            "over the rail hook", "picture moulding hook",
        ),
        library_file="dishes.scad",
        module="picture_rail_hook",
        params=(
            ParamSpec(name="width", label="Width", default=50.0, min=30.0, max=170.0, step=1.0,
                      dim_keys=("width",), bbox_axis=0),
            ParamSpec(name="throat_depth", label="Throat depth", default=18.0, min=8.0, max=60.0,
                      step=1.0, dim_keys=("throat_depth", "rail_depth", "depth")),
            ParamSpec(name="throat_gap", label="Throat height", default=22.0, min=10.0, max=80.0,
                      step=1.0, dim_keys=("throat_gap", "rail_height", "gap")),
            ParamSpec(name="body_height", label="Body drop", default=60.0, min=20.0, max=150.0,
                      step=1.0, dim_keys=("body_height", "height", "drop")),
            ParamSpec(name="thk", label="Thickness", default=5.0, min=3.0, max=8.0, step=0.5,
                      dim_keys=("thk", "thickness", "wall")),
        ),
        fixed_args={"eye_d": 8.0},
        bbox_x=(BBoxTerm(ref="width"),),
        bbox_y=(BBoxTerm(ref="throat_depth"), BBoxTerm(ref="thk")),
        bbox_z=(BBoxTerm(ref="body_height"), BBoxTerm(ref="throat_gap")),
        # Keep the wall thickness under each throat dimension (minus a 2 mm minimum cavity) so the
        # inverted-J ribbon can never self-intersect into a degenerate / non-manifold profile.
        gaps=(("thk", "throat_depth", 2.0, 1.0), ("thk", "throat_gap", 2.0, 1.0)),
    )

    d_ring_strap_hanger = TemplateFamily(
        name="d_ring_strap_hanger",
        summary="A screw-down strap plate with a fixed printed D-ring loop for hanging heavier framed art.",
        tier="baseline",
        object_types=("d ring strap hanger", "strap d ring hanger",
                      "d ring picture hanger", "strap mount d ring"),
        library_file="dishes.scad",
        module="d_ring_strap_hanger",
        params=(
            ParamSpec(name="strap_w", label="Strap width", default=40.0, min=20.0, max=120.0,
                      step=1.0, dim_keys=("strap_w", "width"), bbox_axis=0),
            ParamSpec(name="strap_t", label="Strap thickness", default=5.0, min=3.0, max=12.0,
                      step=0.5, dim_keys=("strap_t", "thickness")),
            ParamSpec(name="strap_h", label="Strap height", default=50.0, min=30.0, max=110.0,
                      step=1.0, dim_keys=("strap_h", "height")),
            ParamSpec(name="ring_od", label="Ring outer diameter", default=28.0, min=16.0, max=60.0,
                      step=1.0, dim_keys=("ring_od", "ring_diameter", "diameter")),
            ParamSpec(name="ring_thk", label="Ring thickness", default=6.0, min=4.0, max=15.0,
                      step=0.5, dim_keys=("ring_thk",)),
        ),
        fixed_args={"screw_d": 4.0},
        bbox_x=(BBoxTerm(ref="strap_w"),),
        bbox_y=(BBoxTerm(ref="strap_t"), BBoxTerm(ref="ring_thk")),
        bbox_z=(BBoxTerm(ref="strap_h"), BBoxTerm(ref="ring_od")),
        # The vertical-annulus loop (OD ring_od, centered across the plate width) and its fuse
        # boss must stay inside the plate width, so pin ring_od <= strap_w — that keeps the X
        # envelope exactly strap_w (proven: ring_od == strap_w renders at bbox_x = strap_w).
        gaps=(("ring_od", "strap_w", 0.0, 1.0),),
    )

    return (
        snap_box, open_box, enclosure, tube, wall_hook, cable_clip, drawer_divider,
        pegboard_hook, spool_holder, l_bracket,
        picture_frame, certificate_frame, mat_board, floating_frame, shadow_box_frame,
        lithophane_frame,
        sawtooth_hanger, keyhole_hanger_plate, hidden_rod_shelf_bracket,
        ring_dish, incense_cone_holder, incense_stick_holder, catchall_tray, soap_dish,
        handled_tray, zen_garden_tray,
        # #19 slice 6: holders/cups + planters
        tealight_holder, taper_candle_holder, luminary_base, bud_vase_sleeve, pencil_cup,
        propagation_station, planter_pot, planter_saucer, bonsai_pot, succulent_pot,
        # #19 slice 7: flat decor + ornaments
        coaster_with_rim, trivet, bookend, geometric_wall_tile, tile_connector_clip,
        ornament_blank, ornament_cap, gift_box_lid, jar_lid,
        # #19 slice 8: stands / easels + ledges / rails
        wedge_easel_stand, display_riser, slanted_sign_holder, desk_nameplate_holder,
        place_card_holder, picture_ledge_shelf, peg_hook_rail, j_decor_hook,
        plate_display_stand,
        # #19 slice 9: frame joinery + profile hangers
        canvas_stretcher_corner, frame_corner_clamp, frame_corner_joiner, frame_turn_button,
        frame_backing_clip, wire_loop_hanger, z_clip_panel_hanger, art_french_cleat_pair,
        picture_rail_hook, d_ring_strap_hanger,
    )


# Built eagerly at import: construction is cheap and deterministic, and the families are
# immutable, so there's no init race when the threaded webapp builds pipelines concurrently.
_DEFAULT_REGISTRY = TemplateRegistry(_build_default_families())


def default_registry() -> TemplateRegistry:
    """The process-wide built-in registry (constructed once at import)."""
    return _DEFAULT_REGISTRY
