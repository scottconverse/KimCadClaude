"""Regression guard for the codegen library-misuse fix (commit c15f347).

The bug: the model treated the walled-container ``box()`` library module as a
solid primitive and invented a ``center`` argument, producing wrong geometry
(a 5.2x5.2x40 mm sliver instead of a 20 mm cube) that still rendered. The fix
is pure prose that feeds the model at runtime — the box warning in the manifest
and rules 11/12 in the codegen system prompt. Nothing else asserts that prose
survives, so a future prompt cleanup could silently reintroduce the bug.
"""

from kimcad.llm_provider import PROMPT_DIR, build_library_manifest


def test_manifest_warns_box_is_not_a_solid():
    manifest = build_library_manifest()
    assert "HOLLOW" in manifest
    assert "NOT a solid cube" in manifest
    # The exact invented parameter that caused the bug.
    assert "'center' parameter" in manifest


def test_system_prompt_keeps_builtin_primitive_rules():
    prompt = (PROMPT_DIR / "system_openscad.md").read_text(encoding="utf-8")
    # Rule 11 — reach for built-ins, not a library module, for plain solids.
    assert "Use OpenSCAD built-in primitives for simple solids" in prompt
    # Rule 12 — never pass an undeclared parameter (the `center` mistake).
    assert "Never pass a parameter a module or primitive does not declare" in prompt
    # Worked example demonstrates the correct cube-with-hole pattern.
    assert "difference()" in prompt
