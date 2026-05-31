from pathlib import Path

import trimesh

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.openscad_runner import RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline, PipelineStatus

# TEST-007: FakeProvider, the box renderer, and BAMBU/PLA are hoisted into conftest.py
# and shared with test_webapp.py. The local aliases keep every test body below unchanged.
from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer as _box_renderer


def _resizing_renderer(extents_sequence):
    """Render a different box size per call, clamping to the last once exhausted.

    Lets a test simulate the model fixing geometry on retry: e.g. wrong size first,
    correct size second.
    """
    state = {"n": 0}

    def render(scad, out_dir: Path, basename: str) -> RenderResult:
        ext = extents_sequence[min(state["n"], len(extents_sequence) - 1)]
        state["n"] += 1
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=ext).export(str(path))
        return RenderResult(
            output_path=path,
            output_format="stl",
            stdout="",
            stderr="",
            duration_s=0.01,
            sanitize=SanitizeResult(code=scad, removed=[]),
        )

    return render, state


def _plan(bbox, *, open_questions=None, dimensions=None) -> DesignPlan:
    return DesignPlan(
        object_type="block",
        summary="a test block",
        dimensions=dimensions or {},
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
        open_questions=open_questions or [],
    )


def _pipeline(provider, renderer, **kw) -> Pipeline:
    return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **kw)


def test_clarification_short_circuits_when_unsized(tmp_path):
    # No envelope and no dimensions -> ask before building, never reach codegen.
    provider = FakeProvider(_plan(None, open_questions=["What overall size?"]))
    renderer, state = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.clarification_needed
    assert result.clarification == "What overall size?"
    assert provider.openscad_calls == 0  # never reached codegen
    assert state["n"] == 0


def test_open_questions_dont_block_a_sized_plan(tmp_path):
    # A sized plan proceeds even when the model attached an open question.
    provider = FakeProvider(_plan([20, 20, 20], open_questions=["What screw size?"]))
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls >= 1


def test_completed_happy_path(tmp_path):
    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a 20mm block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.report is not None
    assert result.report.gate_status == "pass"
    assert result.mesh_path is not None and result.mesh_path.exists()
    assert result.render_attempts == 1
    assert "20" in result.report.to_text()


def test_gate_fail_blocks_unless_proceed_anyway(tmp_path):
    # plan claims 50mm but the render is 20mm -> dimensional mismatch FAIL
    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a block", tmp_path)
    assert result.status is PipelineStatus.gate_failed
    assert result.gate.failed
    assert result.report is not None  # report still produced for the user

    provider2 = FakeProvider(_plan([50, 50, 50]))
    renderer2, _ = _box_renderer((20, 20, 20))
    result2 = _pipeline(provider2, renderer2).run("a block", tmp_path, proceed_anyway=True)
    assert result2.status is PipelineStatus.completed


def test_render_retry_feeds_error_back(tmp_path):
    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, state = _box_renderer((20, 20, 20), fail_times=1)
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.render_attempts == 2
    assert provider.openscad_calls == 2  # regenerated after the failure
    assert state["n"] == 2


def test_render_fails_closed_after_retries(tmp_path):
    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, state = _box_renderer((20, 20, 20), fail_times=99)
    result = _pipeline(provider, renderer, max_render_retries=2).run("a block", tmp_path)

    assert result.status is PipelineStatus.render_failed
    assert state["n"] == 3  # initial + 2 retries
    assert result.error is not None


def test_gate_retry_fixes_dimensional_failure(tmp_path):
    # Plan wants 50mm; first render is 20mm (dim FAIL), second render is 50mm (pass).
    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, state = _resizing_renderer([(20, 20, 20), (50, 50, 50)])
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert result.report is not None and result.report.gate_status == "pass"
    assert state["n"] == 2  # rendered twice: failed, then fixed
    assert provider.openscad_calls == 2  # regenerated after the gate failure
    assert result.render_attempts == 2


def test_gate_retry_fails_closed_after_budget(tmp_path):
    # Render stays the wrong size; the gate retry exhausts and fails closed.
    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, state = _resizing_renderer([(20, 20, 20)])
    result = _pipeline(provider, renderer, max_render_retries=2).run("a block", tmp_path)

    assert result.status is PipelineStatus.gate_failed
    assert state["n"] == 3  # initial + 2 retries
    assert provider.openscad_calls == 3
    assert result.report is not None


def test_proceed_anyway_skips_gate_retry(tmp_path):
    # proceed_anyway means the caller accepted the gate result; don't burn retries.
    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, state = _resizing_renderer([(20, 20, 20)])
    result = _pipeline(provider, renderer).run("a block", tmp_path, proceed_anyway=True)

    assert result.status is PipelineStatus.completed
    assert state["n"] == 1  # rendered once, no retry
    assert provider.openscad_calls == 1


def test_slice_only_with_confirmation(tmp_path):
    sliced = {"called": 0}

    def fake_slicer(mesh_path, out_dir, basename):
        sliced["called"] += 1
        return "sliced-artifact"

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    pipe = _pipeline(provider, renderer, slicer=fake_slicer)

    # no confirmation -> no slice
    r1 = pipe.run("a block", tmp_path)
    assert sliced["called"] == 0
    assert r1.slice_result is None

    # with confirmation -> slices
    provider2 = FakeProvider(_plan([20, 20, 20]))
    renderer2, _ = _box_renderer((20, 20, 20))
    pipe2 = _pipeline(provider2, renderer2, slicer=fake_slicer)
    r2 = pipe2.run("a block", tmp_path, confirm_print=True)
    assert sliced["called"] == 1
    assert r2.slice_result == "sliced-artifact"
