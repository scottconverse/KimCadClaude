"""Deterministic template engine (Stage 5, Slice 1).

Two layers, mirroring tests/test_library_modules.py:
- offline contract tests (no binary): registry match, parameter derivation + clamping,
  deterministic emit, and the analytic bounding box;
- a binary-gated integration test that actually renders each family at its defaults and
  asserts the real mesh is watertight with the bbox the family *declares* — so a template
  whose emit or bbox formula drifts from its module fails loudly. Skipped offline.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.templates import (
    BBoxTerm,
    ParamSpec,
    TemplateFamily,
    TemplateRegistry,
    _fmt,
    _normalize,
    _singular,
    clamp_values,
    default_registry,
    derive_values,
    emit_scad,
)


def _family(name: str, *aliases: str) -> TemplateFamily:
    return TemplateFamily(
        name=name, summary="", object_types=aliases or ("widget",),
        library_file="containers.scad", module="snap_box",
        params=(ParamSpec(name="width", label="W", default=10, min=1, max=20),),
        # All three axes are non-empty: the registry now rejects a family with an empty bbox
        # axis (ENG-504), so a minimal test family must declare each one.
        bbox_x=(BBoxTerm(ref="width"),), bbox_y=(BBoxTerm(ref="width"),), bbox_z=(BBoxTerm(ref="width"),),
    )


def _plan(object_type: str, *, dimensions=None, bbox=None) -> DesignPlan:
    return DesignPlan(
        object_type=object_type,
        summary="t",
        dimensions=dimensions or {},
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
    )


# --- registry / matching -----------------------------------------------------------

# The declared family set — the SINGLE place to acknowledge a new family (#19). The registry
# is asserted against this below, so adding a family without listing it here (or vice versa)
# fails loud: a deliberate "declare your new family" tripwire, but DRY (one literal, not the
# old scattered `== 7`s).
EXPECTED_FAMILY_NAMES = frozenset(
    {
        "snap_box", "box", "enclosure", "tube", "wall_hook", "cable_clip", "drawer_divider",
        # #19 slice 2: library modules that shipped unused, now selectable families
        "pegboard_hook", "spool_holder", "l_bracket",
        # #19 slice 3: frames (Kim's design world)
        "picture_frame", "certificate_frame", "mat_board", "floating_frame",
        "shadow_box_frame", "lithophane_frame",
        # #19 slice 4: hangers
        "sawtooth_hanger", "keyhole_hanger_plate", "hidden_rod_shelf_bracket",
        # #19 slice 5: zen trays / dishes / incense holders
        "ring_dish", "incense_cone_holder", "incense_stick_holder", "catchall_tray",
        "soap_dish", "handled_tray", "zen_garden_tray",
    }
)


def test_registry_exposes_the_builtin_families():
    names = {f.name for f in default_registry().families()}
    assert names == EXPECTED_FAMILY_NAMES


def test_every_family_declares_a_valid_tier():
    # #19: every family carries an honesty tier. The original geometry-honest built-ins are
    # all "benchmarked"; "baseline" is reserved for families with a real fitness caveat
    # (a frame seats glass+art; a tealight cup seats a metal cup; threads are relief-only).
    fams = default_registry().families()
    assert all(f.tier in ("benchmarked", "baseline") for f in fams)
    originals = {"snap_box", "box", "enclosure", "tube", "wall_hook", "cable_clip", "drawer_divider"}
    by_name = {f.name: f for f in fams}
    assert all(by_name[n].tier == "benchmarked" for n in originals)
    # The expansion introduced baseline families — prove the tier is actually exercised.
    assert any(f.tier == "baseline" for f in fams)


@pytest.mark.parametrize(
    "object_type,expected",
    [
        ("box", "snap_box"),
        ("case", "snap_box"),
        ("tray", "box"),
        ("bin", "box"),
        ("enclosure", "enclosure"),
        ("tube", "tube"),
        ("spacer", "tube"),
        ("hook", "wall_hook"),
        ("coat hook", "wall_hook"),
        ("cable clip", "cable_clip"),
        ("drawer divider", "drawer_divider"),
    ],
)
def test_match_resolves_object_type_aliases(object_type, expected):
    match = default_registry().match(_plan(object_type))
    assert match is not None and match.family.name == expected


@pytest.mark.parametrize("written", ["Wall Hook", "wall-hook", "wall_hook", "WALL  HOOK"])
def test_match_normalizes_separators_and_case(written):
    match = default_registry().match(_plan(written))
    assert match is not None and match.family.name == "wall_hook"


@pytest.mark.parametrize("plural,expected", [("hooks", "wall_hook"), ("bins", "box"), ("tubes", "tube")])
def test_match_handles_simple_plurals(plural, expected):
    match = default_registry().match(_plan(plural))
    assert match is not None and match.family.name == expected


def test_match_returns_none_for_unknown_object_type():
    assert default_registry().match(_plan("articulated dragon")) is None


def test_match_handles_es_plural_via_explicit_alias():
    # "boxes" can't be -s stripped to "box"; it's covered by an explicit alias (TPL-004).
    match = default_registry().match(_plan("boxes"))
    assert match is not None and match.family.name == "snap_box"


def test_registry_rejects_duplicate_alias():
    # Two families claiming the same normalized alias must fail loudly, not silently
    # shadow each other (TPL-002).
    with pytest.raises(ValueError, match="duplicate template alias"):
        TemplateRegistry((_family("a", "widget"), _family("b", "widget")))


def test_builtin_registry_constructs_without_alias_collision():
    # default_registry() construction itself raises on any collision; reaching here with the
    # full declared family set proves the built-ins have no overlapping aliases.
    assert len(default_registry().families()) == len(EXPECTED_FAMILY_NAMES)


# --- parameter derivation ----------------------------------------------------------

def test_derive_prefers_named_dimensions():
    fam = default_registry().family("snap_box")
    vals = derive_values(fam, _plan("box", dimensions={"width": 50, "depth": 40, "height": 30, "wall": 3}))
    assert vals == {"width": 50, "depth": 40, "height": 30, "wall": 3}


def test_derive_falls_back_to_bounding_box_axes():
    fam = default_registry().family("snap_box")
    vals = derive_values(fam, _plan("box", bbox=[55, 45, 35]))
    assert (vals["width"], vals["depth"], vals["height"]) == (55, 45, 35)
    assert vals["wall"] == 2.0  # no dim, no bbox axis -> family default


def test_derive_falls_back_to_defaults_when_unspecified():
    fam = default_registry().family("snap_box")
    vals = derive_values(fam, _plan("box"))
    assert vals == {"width": 80.0, "depth": 60.0, "height": 40.0, "wall": 2.0}


def test_derive_clamps_out_of_range_dimensions():
    fam = default_registry().family("snap_box")
    vals = derive_values(fam, _plan("box", dimensions={"width": 9999, "depth": 1, "wall": 99}))
    assert vals["width"] == 170.0  # clamped to the sliceable footprint max (QA-502)
    assert vals["depth"] == 10.0   # clamped to min
    # wall clamps to its own max (8.0), then the ENG-501 cavity rule holds it under half the
    # smallest dimension so the box can't become a solid block: depth=10 -> wall <= 0.5*10 - 1 = 4.
    assert vals["wall"] == 4.0


def test_box_wall_cannot_collapse_to_a_solid_block():
    # ENG-501: a thick wall on a small box must NOT collapse the cavity into a silently-solid block
    # (which still gates PASS on its outer bbox). The cavity rule holds wall under half of EVERY
    # outer dimension minus a 1 mm minimum cavity, for both the closed and open box families.
    for name in ("snap_box", "box"):
        fam = default_registry().family(name)
        for dim in (10, 20, 40):
            v = clamp_values(fam, {"width": dim, "depth": dim, "height": dim, "wall": 8})
            assert v["wall"] <= 0.5 * dim - 1.0 + 1e-9, (name, dim, v["wall"])
            assert dim - 2 * v["wall"] >= 2.0 - 1e-9  # a real >=2 mm cavity remains on each axis


def test_footprint_capped_to_sliceable_envelope():
    # QA-502: the X/Y footprint can't exceed the reference printers' sliceable plate (OrcaSlicer's
    # auto-arrange clearance makes it smaller than the 256 mm bed), so a slider/LLM value can't pass
    # the gate then fail to slice. Height stays free to the bed height.
    fam = default_registry().family("snap_box")
    v = clamp_values(fam, {"width": 250, "depth": 250, "height": 250, "wall": 2})
    # EVERY outer dimension caps at the sliceable footprint side — the auto-orient can rotate any
    # axis onto the bed, so a 170x170x170 cube is the worst corner and it slices.
    assert v["width"] == 170.0 and v["depth"] == 170.0 and v["height"] == 170.0


def test_emit_scad_reflects_changed_values_without_a_renderer():
    # TEST-501: a binary-free proof that a re-render at new values actually changes the geometry
    # SOURCE (emit_scad embeds the new dimension), so the offline suite isn't blind to a slider that
    # silently renders the same shape when the OpenSCAD binary is absent (the offline stub renderer).
    fam = default_registry().family("snap_box")
    s80 = emit_scad(fam, clamp_values(fam, {"width": 80, "depth": 60, "height": 40, "wall": 2}))
    s120 = emit_scad(fam, clamp_values(fam, {"width": 120, "depth": 60, "height": 40, "wall": 2}))
    assert "width=80" in s80 and "width=120" in s120 and s80 != s120


def test_drawer_divider_compartments_capped_to_length():
    # ENG-505: too many compartments for a short frame would overlap the (compartments-1) cross-walls
    # into a solid block; the count is capped to <= length/4 and stays a whole number.
    # TEST-009: named expectations, not inline arithmetic — the cap rule is length/4.
    frame_length_mm = 12
    max_compartments_for_frame = frame_length_mm // 4  # == 3 bays
    fam = default_registry().family("drawer_divider")
    v = clamp_values(fam, {"length": frame_length_mm, "depth": 80, "height": 50, "compartments": 12})
    assert v["compartments"] == int(v["compartments"])  # a whole count, never half a compartment
    assert 1 <= v["compartments"] <= max_compartments_for_frame


def test_registry_rejects_a_family_with_an_empty_bbox_axis():
    # ENG-504: a forgotten bbox axis silently reports 0 mm; the registry rejects it at construction.
    bad = TemplateFamily(
        name="b", summary="", object_types=("b",), library_file="containers.scad", module="snap_box",
        params=(ParamSpec(name="width", label="W", default=10, min=1, max=20),),
        bbox_x=(BBoxTerm(ref="width"),), bbox_y=(BBoxTerm(ref="width"),),  # bbox_z left empty
    )
    with pytest.raises(ValueError, match="empty bbox_z"):
        TemplateRegistry((bad,))


def test_clamp_values_backfills_missing_and_ignores_unknown():
    fam = default_registry().family("snap_box")
    vals = clamp_values(fam, {"width": 100, "bogus": 5})
    assert vals["width"] == 100
    assert vals["depth"] == 60.0  # back-filled default
    assert "bogus" not in vals


def test_clamp_values_coerces_non_numeric_to_default():
    fam = default_registry().family("snap_box")
    vals = clamp_values(fam, {"width": "not-a-number"})
    assert vals["width"] == 80.0


def test_clamp_values_drops_non_finite_to_default():
    # NaN/inf must not survive into emit (TPL-003); they fall back to the default, not a bound.
    fam = default_registry().family("snap_box")
    assert clamp_values(fam, {"width": float("inf")})["width"] == 80.0
    assert clamp_values(fam, {"width": float("nan")})["width"] == 80.0


def test_tube_gap_keeps_bore_inside_the_outer_wall():
    # Independent od/id sliders could otherwise yield id >= od -> degenerate geometry (TPL-001).
    fam = default_registry().family("tube")
    vals = clamp_values(fam, {"od": 4, "id": 190, "height": 12})
    assert vals["id"] < vals["od"]
    assert vals["id"] == 3.0  # od(4) - gap(1)


def test_derive_honors_gap_constraint():
    fam = default_registry().family("tube")
    vals = derive_values(fam, _plan("tube", dimensions={"od": 10, "id": 50}))
    assert vals["id"] < vals["od"]


# --- emit --------------------------------------------------------------------------

def test_emit_is_deterministic_and_uses_the_library_module():
    fam = default_registry().family("snap_box")
    scad = emit_scad(fam, {"width": 80, "depth": 60, "height": 40, "wall": 2})
    assert scad == "use <library/containers.scad>;\nsnap_box(width=80, depth=60, height=40, wall=2);\n"


def test_emit_includes_fixed_args_and_formats_integers():
    fam = default_registry().family("drawer_divider")
    scad = emit_scad(fam, {"length": 150, "depth": 80, "height": 50, "compartments": 3})
    assert "use <library/organizers.scad>;" in scad
    assert "compartments=3" in scad and "compartments=3.0" not in scad
    assert "panel_t=2" in scad  # fixed arg present


def test_emit_passes_wall_hook_fixed_geometry():
    fam = default_registry().family("wall_hook")
    scad = emit_scad(fam, {"plate_w": 25, "plate_h": 60, "arm_proj": 35})
    for token in ("plate_w=25", "plate_h=60", "arm_proj=35", "plate_t=4", "arm_rise=20"):
        assert token in scad


@pytest.mark.parametrize("value,integer,expected", [
    (80.0, False, "80"), (2.5, False, "2.5"), (25.4, False, "25.4"), (3.0, True, "3"), (3.4, True, "3"),
])
def test_fmt_renders_clean_openscad_literals(value, integer, expected):
    assert _fmt(value, integer=integer) == expected


# --- analytic bounding box ---------------------------------------------------------

def test_expected_bbox_matches_module_formulas():
    reg = default_registry()
    assert reg.family("snap_box").expected_bbox({"width": 80, "depth": 60, "height": 40, "wall": 2}) == (80, 60, 40)
    assert reg.family("enclosure").expected_bbox(
        {"inner_w": 80, "inner_d": 50, "inner_h": 30, "wall": 2.5}
    ) == (85, 55, 35)
    assert reg.family("wall_hook").expected_bbox({"plate_w": 25, "plate_h": 60, "arm_proj": 35}) == (25, 39, 60)
    assert reg.family("cable_clip").expected_bbox({"cable_d": 6, "width": 20}) == (20, 25, 9)
    assert reg.family("tube").expected_bbox({"od": 16, "id": 8, "height": 12}) == (16, 16, 12)


def test_match_parameters_snapshot_is_in_range_and_typed():
    match = default_registry().match(_plan("box", dimensions={"width": 100}))
    params = {p["name"]: p for p in match.parameters()}
    assert params["width"]["value"] == 100
    assert params["width"]["min"] <= params["width"]["value"] <= params["width"]["max"]
    assert params["wall"]["unit"] == "mm" and params["wall"]["step"] == 0.2


def test_parameters_snapshot_exposes_axis_for_dimensional_params():
    # UX-004: a dimensional parameter carries its X/Y/Z axis so the slider can tag to the
    # viewport's W/D/H pills; a non-dimensional one (wall thickness) carries no axis.
    params = {p["name"]: p for p in default_registry().match(_plan("box")).parameters()}
    assert params["width"]["axis"] == "X"
    assert params["depth"]["axis"] == "Y"
    assert params["height"]["axis"] == "Z"
    assert "axis" not in params["wall"]


def test_singular_stripping_never_collides_across_families():
    # ENG-504: the conservative -s plural stripper must not let one family's alias singularize
    # onto a DIFFERENT family's alias (which would silently mis-match). Holds for all built-ins.
    reg = default_registry()
    alias_owner: dict[str, str] = {}
    for fam in reg.families():
        for alias in fam.object_types:
            alias_owner[_normalize(alias)] = fam.name
    for norm, owner in alias_owner.items():
        singular = _singular(norm)
        if singular != norm and singular in alias_owner:
            assert alias_owner[singular] == owner, (
                f"'{norm}' ({owner}) singularizes to '{singular}' owned by "
                f"'{alias_owner[singular]}' — a cross-family collision"
            )


def test_unknown_bbox_ref_raises():
    fam = TemplateFamily(
        name="x", summary="", object_types=("x",), library_file="containers.scad", module="snap_box",
        params=(ParamSpec(name="width", label="W", default=10, min=1, max=20),),
        bbox_x=(BBoxTerm(ref="nope"),),
    )
    with pytest.raises(KeyError):
        fam.expected_bbox({"width": 10})


# --- binary-gated: the template actually builds what it declares -------------------

def _binary_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:
        return False


@pytest.mark.real_tool
@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
@pytest.mark.parametrize("name", [f.name for f in default_registry().families()])
def test_family_renders_watertight_with_its_declared_bbox(name):
    """Each family, emitted at its defaults, must render to a watertight mesh whose real
    envelope equals the family's analytic expected_bbox to mesh-float noise — proving the
    deterministic emit and the bbox formula stay honest against the underlying module."""
    from kimcad.openscad_runner import render_scad
    from kimcad.validation import load_mesh, validate_mesh

    fam = default_registry().family(name)
    values = clamp_values(fam, {})  # all defaults, in range
    scad = emit_scad(fam, values)
    expected = fam.expected_bbox(values)
    cfg = Config.load()
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
    for axis, got, exp in zip("XYZ", report.bounding_box_mm, expected):
        assert abs(got - exp) <= 0.01, f"{name} {axis}: got {got:.4f}, declared {exp:.4f}"


@pytest.mark.real_tool
@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
def test_wall_hook_bbox_is_exact_at_the_plate_height_minimum():
    """ENG-501: at the plate_h slider minimum the module's arm floor used to lift the true Z top
    2 mm above the analytic plate_h, failing the gate at that one slider end. With the min raised
    to 24 the linear bbox_z equals the rendered envelope across the whole range — verify at the
    minimum (the formerly-drifting boundary)."""
    from kimcad.openscad_runner import render_scad
    from kimcad.validation import load_mesh, validate_mesh

    fam = default_registry().family("wall_hook")
    plate_h_min = next(p.min for p in fam.params if p.name == "plate_h")
    values = clamp_values(fam, {"plate_h": plate_h_min})
    assert values["plate_h"] == plate_h_min  # the slider is actually at its minimum
    scad = emit_scad(fam, values)
    expected = fam.expected_bbox(values)
    cfg = Config.load()
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
    for axis, got, exp in zip("XYZ", report.bounding_box_mm, expected):
        assert abs(got - exp) <= 0.05, (
            f"wall_hook@plate_h_min {axis}: got {got:.4f}, declared {exp:.4f} (ENG-501 regression)"
        )
