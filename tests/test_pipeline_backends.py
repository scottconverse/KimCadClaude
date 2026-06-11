"""The LLM codegen path — OpenSCAD as the ONLY generative backend (KC-2/KC-4, #8/#6).

Stage 8 shipped a parallel LLM-CadQuery fallback here; KC-4 measured its realized lift at 0
on the shipping model, so it was removed — with its entire LLM-written-Python execution
surface (#9). These tests pin the single-backend behavior: a primary failure is REPORTED
(render_failed / gate_failed), never silently rescued, and the safety properties hold on the
one remaining path. CadQuery geometry now comes only from the trusted template twins
(``kimcad.cadquery_templates`` — tested in test_cadquery_templates.py / test_webapp.py).
"""

from __future__ import annotations

from pathlib import Path

import trimesh

from kimcad.config import Config
from kimcad.openscad_runner import RenderFailed, RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline, PipelineStatus
from kimcad.templates import TemplateRegistry

from conftest import BAMBU, PLA, FakeProvider, make_plan


def _renderer(extents, *, raises=False):
    """A fake renderer that writes a trimesh box of the given extents (or always raises)."""
    state = {"n": 0}

    def render(code, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if raises:
            raise RenderFailed(1, "synthetic render failure", engine="openscad")
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
        return RenderResult(
            output_path=path,
            output_format="stl",
            stdout="",
            stderr="",
            duration_s=0.01,
            sanitize=SanitizeResult(code=code, removed=[]),
            backend="openscad",
        )

    return render, state


def _pipeline(provider, renderer, **kw) -> Pipeline:
    # Empty registry => force the LLM codegen path (no deterministic template).
    # retries=0 keeps it to one try.
    return Pipeline(
        Config.load(), BAMBU, PLA, provider,
        renderer=renderer, registry=TemplateRegistry(()), max_render_retries=0, **kw,
    )


def test_openscad_success_completes(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, state = _renderer((20, 20, 20))  # passes the gate
    result = _pipeline(provider, osc).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.backend == "openscad"
    assert result.report.backend == "openscad"
    assert state["n"] == 1


def test_render_failure_is_reported_not_rescued(tmp_path):
    # KC-4: no fallback exists — a primary that can't render is an honest render_failed.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20), raises=True)
    result = _pipeline(provider, osc).run("a block", tmp_path)

    assert result.status is PipelineStatus.render_failed
    assert provider.openscad_calls == 1


def test_gate_failure_is_reported_not_rescued(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # wrong size -> dim.mismatch gate FAIL
    result = _pipeline(provider, osc).run("a block", tmp_path)

    assert result.status is PipelineStatus.gate_failed
    assert result.backend == "openscad"


def test_gate_failed_part_is_never_sliced(tmp_path):
    # The core safety property on the codegen path: a gate-FAILed part is never sliced,
    # even with the print confirmed.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # gate FAIL

    def slicer(mesh_path, out_dir, basename):  # noqa: ANN001
        raise AssertionError("a gate-failed part must never be sliced")

    pipe = Pipeline(
        Config.load(), BAMBU, PLA, provider, renderer=osc,
        registry=TemplateRegistry(()), max_render_retries=0, slicer=slicer,
    )
    result = pipe.run("a block", tmp_path, confirm_print=True)
    assert result.status is PipelineStatus.gate_failed  # slicer never raised -> never called


def test_codegen_part_has_no_step_path(tmp_path):
    # The editable-CAD export belongs to TEMPLATE parts (their trusted CadQuery twins, built
    # lazily by the web layer) — an LLM-OpenSCAD part has none.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20))
    result = _pipeline(provider, osc).run("a block", tmp_path)

    assert result.backend == "openscad"
    assert result.report.step_path is None


def test_proceed_anyway_accepts_a_gate_failed_part(tmp_path):
    # TEST-004: proceed_anyway ("inspect this failed part") accepts the gate-FAILed render
    # as-is — the user asked to see it, not to have it silently replaced.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # gate FAIL
    result = _pipeline(provider, osc).run("a block", tmp_path, proceed_anyway=True)

    assert result.backend == "openscad"
    assert result.status is PipelineStatus.completed


def test_llm_cadquery_codegen_is_fully_retired():
    # KC-4 (#6) / KC-3 (#9): no provider may write CadQuery anymore — the method is gone
    # from the Provider contract and every concrete provider. A reintroduction (and with it
    # the LLM-written-Python execution surface) fails this test.
    from kimcad.llm_provider import FallbackProvider, LLMProvider
    from kimcad.webapp import DemoProvider, _SettingsAwareProvider

    for cls in (LLMProvider, FallbackProvider, DemoProvider, _SettingsAwareProvider):
        assert not hasattr(cls, "generate_cadquery"), f"{cls.__name__} regrew generate_cadquery"


def test_all_real_providers_implement_the_full_contract():
    # audit FINDING-003 + TEST-005: Provider is a structural Protocol (not runtime-enforced), so
    # a concrete provider can silently miss a method OR carry an incompatible signature. Assert
    # every provider wired as a REAL Provider both DEFINES each method AND its signature accepts
    # the contract argument shape — a presence check alone wouldn't catch a wrong-arity stub.
    import inspect

    from kimcad.llm_provider import FallbackProvider, LLMProvider
    from kimcad.webapp import DemoProvider, _SettingsAwareProvider

    codegen = ("generate_design_plan", "generate_openscad")
    image = ("describe_photo", "describe_sketch")
    for cls in (LLMProvider, FallbackProvider, DemoProvider, _SettingsAwareProvider, FakeProvider):
        for method in (*codegen, *image):
            fn = getattr(cls, method, None)
            assert callable(fn), f"{cls.__name__} is missing {method}"
            sig = inspect.signature(fn)  # includes `self`; None stands in for the instance
            try:
                if method in image:
                    sig.bind(None, b"img", object(), object())
                else:
                    sig.bind(None, object(), object(), object(), history=None)
            except TypeError as e:
                raise AssertionError(f"{cls.__name__}.{method} can't accept the contract args: {e}")
