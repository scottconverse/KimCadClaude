"""KC-2 (#8) — trusted template→STEP CadQuery emitters.

Every shipped template family gets a CadQuery twin emitter: OUR code, parameterized only by
the family's clamped float values — never LLM-authored — so the editable .STEP export carries
zero code-injection / RCE surface. The contract under test:

- every family in the default registry has an emitter (full STEP coverage, no silent gaps);
- emitted scripts satisfy the worker contract (assign ``result``, no imports) and pass the
  same sanitizer the worker enforces;
- values are coerced through ``float()`` (a non-numeric "value" raises — injection-proof);
- (live) each family's script renders through the REAL worker watertight at the family's
  analytic ``expected_bbox`` per axis, and the .step file is written and non-trivial.
"""

from __future__ import annotations

import pytest

from kimcad.cadquery_runner import find_cadquery_interpreter, sanitize_cadquery
from kimcad.cadquery_templates import emit_cadquery, step_supported
from kimcad.templates import default_registry

_FAMILIES = default_registry().families()


def _defaults(family) -> dict[str, float]:
    return {p.name: p.default for p in family.params}


def test_every_shipped_family_has_a_step_emitter():
    """Full coverage: a family without an emitter would silently lack STEP — fail loud."""
    missing = [f.name for f in _FAMILIES if not step_supported(f.name)]
    assert missing == [], f"families with no CadQuery emitter: {missing}"
    assert not step_supported("no_such_family")


def test_emitters_satisfy_the_worker_contract_and_sanitizer():
    """Scripts must assign ``result``, carry no imports (the worker provides ``cq``), and
    pass the same sanitizer the worker enforces on every script it runs."""
    for family in _FAMILIES:
        code = emit_cadquery(family, _defaults(family))
        assert code is not None, family.name
        assert "result" in code and "=" in code, family.name
        assert "import" not in code, f"{family.name}: emitters must not import"
        check = sanitize_cadquery(code)
        assert check.safe, f"{family.name}: sanitizer blocked {check.blocked}"


def test_unknown_family_returns_none():
    fam = _FAMILIES[0]
    assert emit_cadquery(fam.model_copy(update={"name": "no_such_family"}), _defaults(fam)) is None


def test_values_are_float_coerced_so_strings_cannot_inject():
    """The emitters interpolate VALUES into code — they must go through float(), so a
    crafted string raises instead of landing in the script."""
    tube = next(f for f in _FAMILIES if f.name == "tube")
    values = _defaults(tube)
    values["od"] = "16); __import__('os')  # "  # type: ignore[assignment]
    with pytest.raises((TypeError, ValueError)):
        emit_cadquery(tube, values)


def test_parameter_values_appear_in_the_script():
    tube = next(f for f in _FAMILIES if f.name == "tube")
    code = emit_cadquery(tube, {"od": 22.0, "id": 9.0, "height": 33.0})
    assert code is not None
    for token in ("22", "9", "33"):
        assert token in code, f"missing {token} in:\n{code}"


_CQ = find_cadquery_interpreter()


@pytest.mark.live
@pytest.mark.needs_cadquery
@pytest.mark.skipif(_CQ is None, reason="no cadquery interpreter")
@pytest.mark.parametrize("family", _FAMILIES, ids=lambda f: f.name)
def test_family_emitter_renders_watertight_at_the_analytic_bbox(family, tmp_path):
    """The real-worker proof: each family's CadQuery twin builds a watertight solid whose
    PER-AXIS envelope matches the family's analytic expected_bbox (the gate target) within
    the bench tolerance, and the .step export lands non-trivially on disk."""
    import trimesh

    from kimcad.cadquery_bench import BBOX_TOLERANCE_MM
    from kimcad.cadquery_runner import render_cadquery

    values = _defaults(family)
    code = emit_cadquery(family, values)
    assert code is not None
    render = render_cadquery(
        code, interpreter=_CQ, out_dir=tmp_path, basename=family.name, emit_step=True
    )
    mesh = trimesh.load(render.output_path)
    assert mesh.is_watertight, family.name
    actual = tuple(float(v) for v in mesh.extents)
    expected = family.expected_bbox(values)
    for axis, (a, e) in enumerate(zip(actual, expected)):
        assert abs(a - e) <= BBOX_TOLERANCE_MM, (
            f"{family.name} axis {'XYZ'[axis]}: rendered {a:.2f} != analytic {e:.2f}"
        )
    step = tmp_path / f"{family.name}.step"
    assert step.exists() and step.stat().st_size > 1024, f"{family.name}: STEP missing/trivial"
