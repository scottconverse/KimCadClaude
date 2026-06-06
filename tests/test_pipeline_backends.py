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


def _renderer(extents, *, backend="openscad", raises=False):
    """A fake renderer that writes a trimesh box of the given extents (or always raises),
    tagging the RenderResult with ``backend`` so the pipeline can attribute it."""
    state = {"n": 0}

    def render(code, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if raises:
            raise RenderFailed(1, "synthetic render failure", engine=backend)
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
        return RenderResult(
            output_path=path,
            output_format="stl",
            stdout="",
            stderr="",
            duration_s=0.01,
            sanitize=SanitizeResult(code=code, removed=[]),
            backend=backend,
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
    # Force "no CadQuery interpreter" regardless of what this dev box has installed.
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


def test_all_real_providers_implement_the_full_contract():
    # audit FINDING-003: Provider is a structural Protocol (not runtime-enforced), so a concrete
    # provider can silently miss a method — exactly how generate_cadquery was missing from the
    # web providers (FINDING-001). Assert every provider wired as a REAL Provider answers the
    # whole contract. (_NoModelProvider is a deliberate partial stub for the no-model template
    # path and is intentionally excluded.)
    from kimcad.llm_provider import FallbackProvider, LLMProvider
    from kimcad.webapp import DemoProvider, _SettingsAwareProvider

    contract = ("generate_design_plan", "generate_openscad", "generate_cadquery", "describe_photo")
    for cls in (LLMProvider, FallbackProvider, DemoProvider, _SettingsAwareProvider, FakeProvider):
        for method in contract:
            assert callable(getattr(cls, method, None)), f"{cls.__name__} is missing {method}"


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
