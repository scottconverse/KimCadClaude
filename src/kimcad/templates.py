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
    # Ordering constraints (small, large, gap): enforce values[small] <= values[large] -
    # gap after clamping, so independent slider ranges can't produce degenerate geometry
    # (e.g. a tube whose bore is wider than its outer wall). See _apply_gaps / TPL-001.
    gaps: tuple[tuple[str, str, float], ...] = ()

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
        JSON-able dicts (the shape the web UI consumes)."""
        out = []
        for p in self.family.params:
            out.append(
                {
                    "name": p.name,
                    "label": p.label,
                    "value": self.values[p.name],
                    "min": p.min,
                    "max": p.max,
                    "step": p.step,
                    "unit": p.unit,
                    "integer": p.integer,
                }
            )
        return out


def emit_scad(family: TemplateFamily, values: dict[str, float]) -> str:
    """Deterministically emit the OpenSCAD that builds ``family`` at ``values`` — a pure
    string substitution, no model call. ``use``s the library file and calls the module
    with every slider parameter (named) plus the family's fixed args."""
    args = [f"{p.name}={_fmt(values[p.name], integer=p.integer)}" for p in family.params]
    args += [f"{k}={_fmt(v)}" for k, v in family.fixed_args.items()]
    return f"use <library/{family.library_file}>;\n{family.module}({', '.join(args)});\n"


def _apply_gaps(family: TemplateFamily, values: dict[str, float]) -> dict[str, float]:
    """Enforce each ``(small, large, gap)`` ordering so ``small <= large - gap``, by
    lowering ``small`` (clamped back into its own range). Mutates and returns ``values``.
    Best-effort: if a too-small ``large`` would push ``small`` below its minimum, ``small``
    stays at its minimum (still the closest legal value)."""
    spec = {p.name: p for p in family.params}
    for small, large, gap in family.gaps:
        if small in values and large in values:
            ceiling = values[large] - gap
            if values[small] > ceiling:
                p = spec[small]
                values[small] = _clamp(ceiling, p.min, p.max)
    return values


def derive_values(family: TemplateFamily, plan: DesignPlan) -> dict[str, float]:
    """Map a plan onto the family's parameters: prefer a named ``dimensions`` key, fall
    back to the matching ``bounding_box_mm`` axis, then the family default — and clamp
    every result into the parameter's range (and honor ordering constraints) so a wild or
    non-finite model number can't escape the slider bounds."""
    out: dict[str, float] = {}
    for p in family.params:
        value: float | None = None
        for key in p.dim_keys:
            if key in plan.dimensions:
                value = plan.dimensions[key]
                break
        if value is None and p.bbox_axis is not None and plan.bounding_box_mm is not None:
            value = plan.bounding_box_mm[p.bbox_axis]
        coerced = p.default if value is None else _coerce_finite(value, p.default)
        out[p.name] = _clamp(coerced, p.min, p.max)
    return _apply_gaps(family, out)


def clamp_values(family: TemplateFamily, values: dict[str, float]) -> dict[str, float]:
    """Clamp an externally-supplied set of parameter values (e.g. a live-slider POST)
    into range, ignoring unknown keys, back-filling any missing parameter with its
    default, dropping non-finite input, and honoring ordering constraints. Guarantees a
    complete, in-range, geometrically-valid value set for :func:`emit_scad`."""
    out: dict[str, float] = {}
    for p in family.params:
        out[p.name] = _clamp(_coerce_finite(values.get(p.name, p.default), p.default), p.min, p.max)
    return _apply_gaps(family, out)


class TemplateRegistry:
    """The set of known families, indexed by normalized ``object_type`` alias."""

    def __init__(self, families: tuple[TemplateFamily, ...]):
        self._families = families
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

_LINEAR = dict(min=10.0, max=250.0, step=1.0)  # a printable linear dimension (vol 256)


def _build_default_families() -> tuple[TemplateFamily, ...]:
    box_like_params = (
        ParamSpec(name="width", label="Width", default=80.0, dim_keys=("width",), bbox_axis=0, **_LINEAR),
        ParamSpec(name="depth", label="Depth", default=60.0, dim_keys=("depth",), bbox_axis=1, **_LINEAR),
        ParamSpec(name="height", label="Height", default=40.0, dim_keys=("height",), bbox_axis=2, **_LINEAR),
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
    )
    open_box = TemplateFamily(
        name="box",
        summary="An open-top walled container (tray / bin).",
        object_types=("open box", "tray", "bin", "open container", "open top box", "container"),
        library_file="box.scad",
        module="box",
        params=(
            ParamSpec(name="width", label="Width", default=60.0, dim_keys=("width",), bbox_axis=0, **_LINEAR),
            ParamSpec(name="depth", label="Depth", default=40.0, dim_keys=("depth",), bbox_axis=1, **_LINEAR),
            ParamSpec(name="height", label="Height", default=30.0, dim_keys=("height",), bbox_axis=2, **_LINEAR),
            ParamSpec(
                name="wall", label="Wall thickness", default=2.0, min=0.8, max=8.0, step=0.2,
                dim_keys=("wall", "thickness"),
            ),
        ),
        bbox_x=xyz_bbox[0], bbox_y=xyz_bbox[1], bbox_z=xyz_bbox[2],
    )
    enclosure = TemplateFamily(
        name="enclosure",
        summary="A two-part enclosure sized from its internal volume; walls add on every side.",
        object_types=("enclosure", "electronics enclosure", "project enclosure"),
        library_file="containers.scad",
        module="enclosure",
        params=(
            ParamSpec(name="inner_w", label="Inner width", default=80.0, dim_keys=("inner_w", "width"), bbox_axis=0, **_LINEAR),
            ParamSpec(name="inner_d", label="Inner depth", default=50.0, dim_keys=("inner_d", "depth"), bbox_axis=1, **_LINEAR),
            ParamSpec(name="inner_h", label="Inner height", default=30.0, dim_keys=("inner_h", "height"), bbox_axis=2, **_LINEAR),
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
            ParamSpec(name="od", label="Outer diameter", default=16.0, min=4.0, max=200.0, step=1.0,
                      dim_keys=("od", "outer_diameter", "diameter"), bbox_axis=0),
            ParamSpec(name="id", label="Inner diameter", default=8.0, min=1.0, max=190.0, step=1.0,
                      dim_keys=("id", "inner_diameter", "bore")),
            ParamSpec(name="height", label="Height", default=12.0, min=2.0, max=250.0, step=1.0,
                      dim_keys=("height", "length"), bbox_axis=2),
        ),
        bbox_x=(BBoxTerm(ref="od"),), bbox_y=(BBoxTerm(ref="od"),), bbox_z=(BBoxTerm(ref="height"),),
        # The bore must stay at least 1 mm inside the outer wall or difference() degenerates.
        gaps=(("id", "od", 1.0),),
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
            ParamSpec(name="plate_h", label="Plate height", default=60.0, min=20.0, max=200.0, step=1.0,
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
            ParamSpec(name="length", label="Length", default=150.0, dim_keys=("length", "width"), bbox_axis=0, **_LINEAR),
            ParamSpec(name="depth", label="Depth", default=80.0, dim_keys=("depth",), bbox_axis=1, **_LINEAR),
            ParamSpec(name="height", label="Height", default=50.0, dim_keys=("height",), bbox_axis=2, **_LINEAR),
            ParamSpec(name="compartments", label="Compartments", default=3.0, min=1.0, max=12.0, step=1.0,
                      unit="", integer=True, dim_keys=("compartments", "sections", "bays")),
        ),
        fixed_args={"panel_t": 2.0},
        bbox_x=(BBoxTerm(ref="length"),), bbox_y=(BBoxTerm(ref="depth"),), bbox_z=(BBoxTerm(ref="height"),),
    )

    return (snap_box, open_box, enclosure, tube, wall_hook, cable_clip, drawer_divider)


_DEFAULT_REGISTRY: TemplateRegistry | None = None


def default_registry() -> TemplateRegistry:
    """The process-wide built-in registry (built once)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = TemplateRegistry(_build_default_families())
    return _DEFAULT_REGISTRY
