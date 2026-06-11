"""Stage 5 Slice 2 — the tiered engine wired into the pipeline.

A template-covered object_type builds deterministically (no model call, single-shot, gate
against the template's declared envelope); everything else falls back to LLM codegen. The
load-bearing assertion throughout is ``provider.openscad_calls == 0`` on the template path:
that is what proves a slider re-render will never round-trip the model.
"""

from __future__ import annotations

import pytest

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.pipeline import Pipeline, PipelineStatus
from kimcad.templates import TemplateRegistry, default_registry

from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer as _box_renderer


def _plan(object_type: str, *, dimensions=None, bbox=None) -> DesignPlan:
    return DesignPlan(
        object_type=object_type,
        summary="t",
        dimensions=dimensions or {},
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
    )


def _pipeline(provider, renderer, **kw) -> Pipeline:
    return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **kw)


def test_template_object_type_builds_without_calling_the_model(tmp_path):
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2})
    match = default_registry().match(plan)
    assert match is not None and match.family.name == "snap_box"

    # Stub renderer returns the template's declared envelope so the gate passes.
    renderer, _ = _box_renderer(match.expected_bbox())
    provider = FakeProvider(plan)
    result = _pipeline(provider, renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls == 0, "the deterministic path must NOT call the model"
    assert result.render_attempts == 1
    assert result.template is not None and result.template.family.name == "snap_box"
    # The emitted SCAD is the deterministic template emit, not model output.
    assert result.scad == match.scad()
    assert "use <library/containers.scad>;" in result.scad


def test_template_aligns_gate_target_to_declared_envelope(tmp_path):
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40})
    match = default_registry().match(plan)
    renderer, _ = _box_renderer(match.expected_bbox())
    result = _pipeline(FakeProvider(plan), renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.report.gate_status == "pass"
    # The plan's target bbox is the template's analytic envelope (not the model's guess).
    assert result.plan.bounding_box_mm == list(match.expected_bbox())
    assert result.report.target_bbox_mm == list(match.expected_bbox())


def test_non_template_object_type_falls_back_to_llm(tmp_path):
    plan = _plan("articulated dragon", bbox=[20, 20, 20])
    provider = FakeProvider(plan)  # default SCAD renders a 20mm box via the stub
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a dragon", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls >= 1, "no template -> the model writes the OpenSCAD"
    assert result.template is None


def test_empty_registry_disables_the_engine(tmp_path):
    # An empty registry forces the LLM path even for a normally-template-covered type.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40}, bbox=[80, 60, 40])
    provider = FakeProvider(plan)
    renderer, _ = _box_renderer((80, 60, 40))
    result = _pipeline(provider, renderer, registry=TemplateRegistry(())).run("a box", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls >= 1
    assert result.template is None


def test_template_gate_failure_is_single_shot_no_retry_no_llm(tmp_path):
    # The template renders the WRONG size (stub) -> dim mismatch FAIL. The deterministic
    # path must not retry and must not fall back to the model: a too-wrong part fails
    # closed, to be fixed by adjusting a parameter, not by regenerating geometry.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40})
    provider = FakeProvider(plan)
    renderer, state = _box_renderer((20, 20, 20))  # not the declared (80,60,40) envelope
    result = _pipeline(provider, renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.gate_failed
    assert state["n"] == 1, "rendered exactly once — no retry loop on a deterministic part"
    assert provider.openscad_calls == 0, "must not fall back to the model on a gate failure"
    assert result.template is not None
    assert result.report is not None  # report still produced for the user


def test_rerender_gate_reflects_current_parameter_values(tmp_path):
    # RENDER-002: the re-render gate must check the CURRENT slider values, not the original
    # design's. The stub renderer is fine here — the wall gate reads plan.dimensions, so this
    # proves the plan carries the new wall (0.8), not the stale 2.0.
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2.0})
    pipe = _pipeline(FakeProvider(plan), _box_renderer((80, 60, 40))[0])
    design = pipe.run("a box", tmp_path)
    wall0 = [f for f in design.gate.findings if f.code.startswith("wall.")]
    assert wall0 and "2.0" in wall0[0].message  # original wall reported

    r = pipe.rerender(design.plan, "snap_box",
                      {"width": 80, "depth": 60, "height": 40, "wall": 0.8}, tmp_path)
    assert r.plan.dimensions["wall"] == 0.8
    wall1 = [f for f in r.gate.findings if f.code.startswith("wall.")]
    assert wall1, "the re-render gate should still produce a wall finding"
    assert "0.8" in wall1[0].message, "gate must reflect the current wall, not the stale 2.0"
    assert "2.0" not in wall1[0].message


def test_proceed_anyway_slices_a_gate_failed_template_part(tmp_path):
    # The explicit override behaves identically on the template path: a gate-FAILED template
    # part DOES slice with proceed_anyway, confirming proceed_anyway is the one override
    # regardless of which engine built the geometry (companion to the fail-closed test).
    sliced = {"n": 0}

    def counting_slicer(mesh_path, out_dir, basename):
        sliced["n"] += 1
        return "sliced"

    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40})
    provider = FakeProvider(plan)
    renderer, _ = _box_renderer((20, 20, 20))  # wrong size -> gate FAIL
    result = _pipeline(provider, renderer, slicer=counting_slicer).run(
        "a box", tmp_path, proceed_anyway=True, confirm_print=True
    )

    assert result.status is PipelineStatus.completed  # override accepted
    assert sliced["n"] == 1
    assert provider.openscad_calls == 0  # still the deterministic path


def test_template_render_failure_surfaces_without_llm_fallback(tmp_path):
    plan = _plan("box", dimensions={"width": 80, "depth": 60, "height": 40})
    provider = FakeProvider(plan)
    renderer, state = _box_renderer((80, 60, 40), fail_times=99)  # always fails
    result = _pipeline(provider, renderer, max_render_retries=2).run("a box", tmp_path)

    assert result.status is PipelineStatus.render_failed
    assert state["n"] == 1, "deterministic path renders once, no retry budget burned"
    assert provider.openscad_calls == 0, "a template render failure is a defect, not an LLM fallback"
    assert result.error is not None


def _binary_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:
        return False


@pytest.mark.real_tool
@pytest.mark.skipif(not _binary_present(), reason="OpenSCAD binary not fetched")
def test_template_path_end_to_end_with_real_openscad(tmp_path):
    """The full deterministic path against the real OpenSCAD binary: a 'box' request builds
    via the template (no model call) into a real watertight mesh at the declared envelope,
    passes the gate, and exports — proving the engine produces a sliceable part on its own."""
    plan = _plan("box", dimensions={"width": 90, "depth": 70, "height": 45, "wall": 2})
    match = default_registry().match(plan)
    provider = FakeProvider(plan)
    # Default renderer = real OpenSCAD (no renderer override).
    result = Pipeline(Config.load(), BAMBU, PLA, provider).run("a 90mm box", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls == 0
    assert result.report.gate_status == "pass"
    assert result.scad == match.scad()
    assert result.mesh_path is not None and result.mesh_path.exists()
    # Real rendered envelope matches the template's declaration to mesh-float noise.
    expected = match.expected_bbox()
    for axis, got, exp in zip("XYZ", result.report.actual_bbox_mm, expected):
        assert abs(got - exp) <= 0.05, f"{axis}: got {got:.3f}, expected {exp:.3f}"
