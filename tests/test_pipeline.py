from pathlib import Path

import trimesh

from kimcad.config import Config, Material, Printer
from kimcad.ir import DesignPlan
from kimcad.openscad_runner import RenderFailed, RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline, PipelineStatus

BAMBU = Printer(
    key="bambu_p2s",
    name="Bambu Lab P2S",
    build_volume=(256, 256, 256),
    nozzle_diameter=0.4,
)
PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)


class FakeProvider:
    def __init__(self, plan: DesignPlan, scad: str = "use <library/box.scad>;\nbox(20,20,20);"):
        self._plan = plan
        self._scad = scad
        self.design_calls = 0
        self.openscad_calls = 0

    def generate_design_plan(self, prompt, printer, material, history=None):
        self.design_calls += 1
        return self._plan

    def generate_openscad(self, plan, printer, material, history=None):
        self.openscad_calls += 1
        return self._scad


def _box_renderer(extents, *, fail_times=0):
    state = {"n": 0}

    def render(scad, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if state["n"] <= fail_times:
            raise RenderFailed(1, "synthetic render failure")
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
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


def test_clarification_short_circuits(tmp_path):
    provider = FakeProvider(_plan([20, 20, 20], open_questions=["What screw size?"]))
    renderer, state = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.clarification_needed
    assert result.clarification == "What screw size?"
    assert provider.openscad_calls == 0  # never reached codegen
    assert state["n"] == 0


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
