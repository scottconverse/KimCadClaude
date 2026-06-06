"""Stage 8 Slice 3 — the parallel CadQuery backend + mutual fallback in the pipeline.

OpenSCAD stays the primary geometry backend. When it can't produce a part that renders AND
passes the printability gate, the pipeline falls back to the CadQuery backend (when one is
available) and keeps whichever result is better. These tests inject fake renderers so the
fallback logic is exercised deterministically with no model, no OpenSCAD, and no CadQuery
interpreter — plus one live test that drives the REAL CadQuery worker as the fallback.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from kimcad.cadquery_runner import find_cadquery_interpreter
from kimcad.config import Config
from kimcad.openscad_runner import RenderFailed, RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline, PipelineStatus
from kimcad.templates import TemplateRegistry

from conftest import BAMBU, PLA, FakeProvider, make_plan

_CQ = find_cadquery_interpreter()


def _renderer(extents, *, backend="openscad", raises=False, step=False):
    """A fake renderer that writes a trimesh box of the given extents (or always raises),
    tagging the RenderResult with ``backend``. With ``step=True`` it also writes a STEP file and
    sets ``step_path`` (mimicking the CadQuery backend's editable-CAD export)."""
    state = {"n": 0}

    def render(code, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if raises:
            raise RenderFailed(1, "synthetic render failure", engine=backend)
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
        step_path = None
        if step:
            step_path = out_dir / f"{basename}.step"
            step_path.write_text("ISO-10303-21;\n", encoding="utf-8")
        return RenderResult(
            output_path=path,
            output_format="stl",
            stdout="",
            stderr="",
            duration_s=0.01,
            sanitize=SanitizeResult(code=code, removed=[]),
            backend=backend,
            step_path=step_path,
        )

    return render, state


def _pipeline(provider, renderer, cadquery_renderer=None, **kw) -> Pipeline:
    # Empty registry => force the LLM codegen path (no deterministic template) so the
    # backend-fallback logic is what's under test. retries=0 keeps it to one try per backend.
    return Pipeline(
        Config.load(), BAMBU, PLA, provider,
        renderer=renderer, cadquery_renderer=cadquery_renderer,
        registry=TemplateRegistry(()), max_render_retries=0, **kw,
    )


def test_openscad_success_does_not_reach_cadquery(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, os_state = _renderer((20, 20, 20))  # passes the gate
    cq, cq_state = _renderer((20, 20, 20), backend="cadquery")
    result = _pipeline(provider, osc, cq).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.backend == "openscad"
    assert result.report.backend == "openscad"
    assert provider.cadquery_calls == 0  # fallback never reached
    assert cq_state["n"] == 0


def test_fallback_to_cadquery_when_openscad_fails_to_render(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20), raises=True)  # never renders
    cq, cq_state = _renderer((20, 20, 20), backend="cadquery")  # builds the part
    result = _pipeline(provider, osc, cq).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.backend == "cadquery"
    assert result.report.backend == "cadquery"
    assert provider.openscad_calls == 1
    assert provider.cadquery_calls == 1
    assert cq_state["n"] == 1


def test_fallback_to_cadquery_when_openscad_fails_the_gate(tmp_path):
    # OpenSCAD renders the wrong size (dim.mismatch FAIL); CadQuery renders the right size.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # wrong size -> gate FAIL
    cq, _ = _renderer((20, 20, 20), backend="cadquery")  # correct -> gate PASS
    result = _pipeline(provider, osc, cq).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.backend == "cadquery"
    assert result.gate.status.value != "fail"


def test_no_fallback_when_cadquery_unavailable(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20), raises=True)
    pipe = Pipeline(
        Config.load(), BAMBU, PLA, provider,
        renderer=osc, registry=TemplateRegistry(()), max_render_retries=0,
    )
    # Belt-and-suspenders, INDEPENDENT of the autouse hermeticity fixture: poke the cache directly
    # so this test holds even if that fixture regressed (TEST-007). The other fallback tests rely
    # on the fixture for determinism; this one does not.
    pipe.config._cadquery_interpreter = None
    result = pipe.run("a block", tmp_path)

    assert result.status is PipelineStatus.render_failed
    assert provider.cadquery_calls == 0  # fallback correctly skipped


def test_both_backends_fail_keeps_the_primary_result(tmp_path):
    # Neither backend matches the plan size: both gate-FAIL. The primary (OpenSCAD) result is
    # kept (ties favour the primary), so the user sees the OpenSCAD report, not the CadQuery one.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))
    cq, _ = _renderer((50, 50, 50), backend="cadquery")
    result = _pipeline(provider, osc, cq).run("a block", tmp_path)

    assert result.status is PipelineStatus.gate_failed
    assert result.backend == "openscad"  # tie -> primary
    assert provider.cadquery_calls == 1  # but the fallback WAS attempted


def test_gate_failed_part_is_not_sliced_on_the_multi_backend_path(tmp_path):
    # The core safety property, on the MULTI-backend path: when BOTH backends gate-FAIL and the
    # user confirmed a print, the part is still never sliced (audit FINDING-002 — the single-
    # backend safety test couldn't cover this because the hermeticity fixture forces CadQuery off).
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # gate FAIL
    cq, _ = _renderer((50, 50, 50), backend="cadquery")  # gate FAIL too

    def slicer(mesh_path, out_dir, basename):  # noqa: ANN001
        raise AssertionError("a gate-failed part must never be sliced")

    pipe = Pipeline(
        Config.load(), BAMBU, PLA, provider, renderer=osc, cadquery_renderer=cq,
        registry=TemplateRegistry(()), max_render_retries=0, slicer=slicer,
    )
    result = pipe.run("a block", tmp_path, confirm_print=True)
    assert result.status is PipelineStatus.gate_failed  # slicer never raised -> never called


def test_cadquery_part_carries_a_step_path(tmp_path):
    # Stage 8 Slice 4: a CadQuery-built part exposes its editable STEP via report.step_path.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20), raises=True)  # OpenSCAD fails -> fall back to CadQuery
    cq, _ = _renderer((20, 20, 20), backend="cadquery", step=True)
    result = _pipeline(provider, osc, cq).run("a block", tmp_path)

    assert result.backend == "cadquery"
    assert result.report.step_path is not None
    assert Path(result.report.step_path).exists()


def test_openscad_part_has_no_step_path(tmp_path):
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20))  # OpenSCAD succeeds -> no fallback, no STEP
    result = _pipeline(provider, osc).run("a block", tmp_path)

    assert result.backend == "openscad"
    assert result.report.step_path is None


def test_all_real_providers_implement_the_full_contract():
    # audit FINDING-003 + TEST-005: Provider is a structural Protocol (not runtime-enforced), so a
    # concrete provider can silently miss a method (how generate_cadquery was missing from the web
    # providers) OR carry an incompatible signature. Assert every provider wired as a REAL Provider
    # both DEFINES each method AND its signature accepts the contract argument shape — a presence
    # check alone wouldn't catch a wrong-arity stub. (_NoModelProvider is a deliberate partial stub
    # for the no-model template path and is intentionally excluded.)
    import inspect

    from kimcad.llm_provider import FallbackProvider, LLMProvider
    from kimcad.webapp import DemoProvider, _SettingsAwareProvider

    codegen = ("generate_design_plan", "generate_openscad", "generate_cadquery")
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


def test_proceed_anyway_accepts_a_gate_failed_primary_without_fallback(tmp_path):
    # TEST-004: proceed_anyway ("inspect this failed part") must short-circuit the fallback — an
    # OpenSCAD render that gate-FAILs is accepted as-is, CadQuery is never invoked.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((40, 40, 40))  # gate FAIL
    cq, cq_state = _renderer((20, 20, 20), backend="cadquery")
    result = _pipeline(provider, osc, cq).run("a block", tmp_path, proceed_anyway=True)

    assert result.backend == "openscad"
    assert provider.cadquery_calls == 0  # no fallback spent
    assert cq_state["n"] == 0


def test_backend_succeeded_accepts_a_warn_primary_without_fallback():
    # TEST-004: a WARN (not FAIL) gate is acceptable — _backend_succeeded returns True, so a WARN
    # primary short-circuits the fallback (a WARN primary never reaches _better_result).
    from kimcad.printability import Finding, GateResult, Level

    warn_gate = GateResult(findings=[Finding(Level.WARN, "wall.thin", "a wall is thin")])
    rendered = (object(), "scad", object(), object(), warn_gate, 1, None)
    assert Pipeline._backend_succeeded(rendered, gate_retry=True) is True
    not_rendered = (None, None, None, None, None, 1, "err")
    assert Pipeline._backend_succeeded(not_rendered, gate_retry=True) is False


@pytest.mark.live
@pytest.mark.skipif(_CQ is None, reason="no cadquery interpreter")
def test_live_cadquery_fallback_builds_a_real_part(tmp_path):
    # OpenSCAD "fails"; the REAL CadQuery worker builds the box from the FakeProvider's script.
    provider = FakeProvider(make_plan((20, 20, 20)))
    osc, _ = _renderer((20, 20, 20), raises=True)
    pipe = Pipeline(
        Config.load(), BAMBU, PLA, provider,
        renderer=osc, registry=TemplateRegistry(()), max_render_retries=0,
    )  # no injected cadquery_renderer -> uses the real interpreter
    result = pipe.run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.backend == "cadquery"
    assert result.mesh_path is not None and result.mesh_path.exists()
