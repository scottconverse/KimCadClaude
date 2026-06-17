import functools
from pathlib import Path

import pytest
import trimesh

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.openscad_runner import RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline, PipelineStatus

# TEST-007: FakeProvider, the box renderer, and BAMBU/PLA are hoisted into conftest.py
# and shared with test_webapp.py. The local aliases keep every test body below unchanged.
from conftest import BAMBU, PLA, FakeProvider, make_plan
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


class _RaisingPlanProvider:
    """A provider whose design-plan call raises — to exercise the plan_failed path.
    ``exc`` is raised on generate_design_plan; codegen counts stay observable."""

    def __init__(self, exc: Exception):
        self._exc = exc
        self.design_calls = 0
        self.openscad_calls = 0

    def generate_design_plan(self, prompt, printer, material, history=None):  # noqa: ANN001
        self.design_calls += 1
        raise self._exc

    def generate_openscad(self, plan, printer, material, history=None):  # noqa: ANN001
        self.openscad_calls += 1
        return "use <library/box.scad>;\nbox(20,20,20);"


def _validation_error() -> Exception:
    # The real error the parse path raises when a model returns schema-shaped / wrong JSON
    # (e.g. a too-small model echoing the schema back).
    try:
        DesignPlan.model_validate({"not": "a plan"})
    except Exception as e:  # pydantic.ValidationError
        return e
    raise AssertionError("model_validate unexpectedly accepted junk")


def test_invalid_plan_fails_clean_instead_of_a_traceback(tmp_path):
    # A model returning something that isn't a valid plan must produce a clean plan_failed
    # result with an actionable message -- never a raw pydantic traceback to the user. The
    # provider raises PlanParseError (what a real LLMProvider raises at the parse boundary).
    from kimcad.llm_provider import PlanParseError

    provider = _RaisingPlanProvider(PlanParseError("bad", original=_validation_error()))
    renderer, state = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a box", tmp_path)

    assert result.status is PipelineStatus.plan_failed
    assert provider.openscad_calls == 0  # never reached codegen
    assert state["n"] == 0  # never rendered
    assert "design plan" in (result.error or "").lower()
    assert "different model" in (result.error or "").lower()  # actionable
    assert "ValidationError" in (result.error or "")  # underlying type surfaced as the detail


# --- QA-002: the experimental generator must fail fast on non-code, before the render subprocess --
@pytest.mark.parametrize("garbage", ["coaster", "  ", "// just the object name\n", "/* nothing */", "\n\n"])
def test_reject_non_code_raises_on_garbage(garbage):
    from kimcad.openscad_runner import RenderError
    from kimcad.pipeline import _reject_non_code

    with pytest.raises(RenderError):
        _reject_non_code(garbage)


@pytest.mark.parametrize(
    "good",
    [
        "cube([10,10,2]);",
        "use <library/box.scad>;\nbox(20,20,20);",  # a library module call — valid, no primitive
        "translate([0,0,1]) cylinder(r=5,h=2);",
        "/* pad */\nlinear_extrude(2) circle(20);",
        "difference(){ cube(10); sphere(4); }",
    ],
)
def test_reject_non_code_accepts_real_openscad(good):
    from kimcad.pipeline import _reject_non_code

    _reject_non_code(good)  # must not raise


def test_non_code_generation_fails_fast_without_rendering(tmp_path):
    # QA-002: when the experimental generator echoes the object name ("coaster") instead of emitting
    # OpenSCAD, the pipeline rejects it BEFORE spending a render, feeds back + retries, then fails
    # with a clear message — never a burned subprocess, never a cryptic render traceback.
    plan = DesignPlan(
        object_type="articulated dragon",  # matches no template family → the experimental codegen path
        summary="x", dimensions={}, bounding_box_mm=[20, 20, 20],
        printer="bambu_p2s", material="pla",
    )
    provider = FakeProvider(plan, scad="coaster")  # the QA-002 failure mode: the model echoed the name
    renderer, state = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a coaster", tmp_path, allow_experimental=True)

    assert state["n"] == 0  # the render subprocess was never spawned on the garbage
    assert provider.openscad_calls >= 1  # codegen was attempted (and re-attempted with feedback)
    assert result.status is PipelineStatus.render_failed
    assert "not buildable code" in (result.error or "").lower()


def test_bad_json_plan_fails_clean(tmp_path):
    import json

    from kimcad.llm_provider import PlanParseError

    bad_json = _RaisingPlanProvider(
        PlanParseError("bad json", original=json.JSONDecodeError("Expecting value", "x", 0))
    )
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(bad_json, renderer).run("a box", tmp_path)
    assert result.status is PipelineStatus.plan_failed
    assert "JSONDecodeError" in (result.error or "")


def test_connection_error_is_not_swallowed_as_plan_failed(tmp_path):
    # A genuine connection failure is NOT a bad-plan; it must propagate (the FallbackProvider
    # or the CLI's error handler owns it), not be masked as plan_failed.
    import httpx
    import pytest
    from openai import APIConnectionError

    down = _RaisingPlanProvider(
        APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))
    )
    renderer, _ = _box_renderer((20, 20, 20))
    with pytest.raises(APIConnectionError):
        _pipeline(down, renderer).run("a box", tmp_path)


def test_a_non_parse_error_is_not_masked_as_plan_failed(tmp_path):
    # PLAN-002: pipeline.run catches ONLY PlanParseError. A plain ValueError (a real bug,
    # not unparseable model output) must propagate so the defect surfaces -- never be hidden
    # behind the user-facing "try a different model" message.
    import pytest

    provider = _RaisingPlanProvider(ValueError("a real bug, not bad model output"))
    renderer, _ = _box_renderer((20, 20, 20))
    with pytest.raises(ValueError):
        _pipeline(provider, renderer).run("a box", tmp_path)


def test_open_questions_dont_block_a_sized_plan(tmp_path):
    # A sized plan proceeds even when the model attached an open question.
    provider = FakeProvider(_plan([20, 20, 20], open_questions=["What screw size?"]))
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a block", tmp_path)

    assert result.status is PipelineStatus.completed
    assert provider.openscad_calls >= 1


def test_experimental_gate_offers_when_disallowed(tmp_path):
    # Slice 6 MS-4: a non-template request with allow_experimental=False returns the offer
    # (needs_experimental) and never calls the codegen model — no dead-end, no auto-run.
    provider = FakeProvider(_plan([20, 20, 20]))  # object_type "block" -> non-template
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a topo coaster", tmp_path, allow_experimental=False)

    assert result.status is PipelineStatus.needs_experimental
    assert provider.openscad_calls == 0  # codegen never ran
    assert result.plan is not None  # the plan is kept (so the offer can name what was asked)


def test_experimental_allowed_runs_codegen(tmp_path):
    # The same request WITH experimental allowed (the default) runs codegen and completes.
    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    result = _pipeline(provider, renderer).run("a topo coaster", tmp_path, allow_experimental=True)

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


def test_run_hardens_mesh_before_export(tmp_path):
    # Slice 4: the oriented mesh is hardened (Manifold3D) before export/slice, and the
    # report says so. manifold3d is a declared dependency, so this runs in CI/target.
    import pytest

    try:
        import manifold3d  # noqa: F401
    except ImportError:  # pragma: no cover
        pytest.skip("manifold3d not installed")

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer).run("a block", tmp_path)
    assert r.status is PipelineStatus.completed
    assert r.report.hardened is True
    assert "manifold3d" in r.report.harden_summary
    assert r.mesh_path.exists()  # the hardened mesh was exported


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


def test_slice_refusal_is_reported_not_raised(tmp_path):
    """A slicer that refuses (e.g. a printer configured with no process profile) must not
    blow up the run: the part still completes with an exported mesh and a slice_note
    explaining why no G-code was produced."""
    from kimcad.slicer import OrcaProfileError

    def refusing_slicer(mesh_path, out_dir, basename):
        raise OrcaProfileError("printer 'x' has no OrcaSlicer process profile")

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    pipe = _pipeline(provider, renderer, slicer=refusing_slicer)
    r = pipe.run("a block", tmp_path, confirm_print=True)

    assert r.status is PipelineStatus.completed
    assert r.slice_result is None
    assert r.slice_error and "process profile" in r.slice_error
    assert r.report.sliced is False
    # ENG-008: a profile gap reads as "not sliceable as configured", distinct from a real
    # failure, and the wrapped message still names the specific cause (here, the process profile).
    assert r.report.slice_note and "not sliceable as configured" in r.report.slice_note
    assert "process profile" in r.report.slice_note
    assert r.mesh_path is not None and r.mesh_path.exists()  # mesh still exported


def test_operational_slice_failure_is_distinguished_from_capability_gap(tmp_path):
    """ENG-008: a SliceFailed on a sliceable printer is reported as a failure ('slicing
    failed'), not framed like the capability gap of a printer with no process profile."""
    from kimcad.slicer import SliceFailed

    def failing_slicer(mesh_path, out_dir, basename):
        raise SliceFailed(2, "bad profile")

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer, slicer=failing_slicer).run(
        "a block", tmp_path, confirm_print=True
    )
    assert r.status is PipelineStatus.completed
    assert r.slice_error and "slicing failed" in r.slice_error
    assert "not yet sliceable" not in (r.report.slice_note or "")


def test_gate_fail_with_confirm_does_not_slice(tmp_path):
    """TEST-001 (the stage's core safety property, failure direction): a part that FAILS
    the gate must NOT be sliced even when the caller also asked to print."""
    sliced = {"n": 0}

    def counting_slicer(mesh_path, out_dir, basename):
        sliced["n"] += 1
        return "should-not-happen"

    # plan says 50mm, render is 20mm -> dim mismatch -> gate FAIL
    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer, slicer=counting_slicer).run(
        "a block", tmp_path, confirm_print=True
    )
    assert r.status is PipelineStatus.gate_failed
    assert sliced["n"] == 0  # the slicer was never invoked
    assert r.slice_result is None
    assert r.report.sliced is False


def test_proceed_anyway_with_confirm_slices_a_gate_failed_part(tmp_path):
    """Companion to TEST-001: proceed_anyway is the explicit override, so a confirmed
    print of a gate-failed part DOES slice — pins that intended interaction."""
    sliced = {"n": 0}

    def counting_slicer(mesh_path, out_dir, basename):
        sliced["n"] += 1
        return "sliced"

    provider = FakeProvider(_plan([50, 50, 50]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer, slicer=counting_slicer).run(
        "a block", tmp_path, proceed_anyway=True, confirm_print=True
    )
    assert r.status is PipelineStatus.completed  # override accepted
    assert sliced["n"] == 1


def test_record_slice_handles_proofless_result(tmp_path):
    """TEST-009: a SliceResult with no proof/settings folds in without crashing —
    sliced True, but no line count / profiles."""
    from kimcad.slicer import SliceResult

    def bare_slicer(mesh_path, out_dir, basename):
        gp = out_dir / f"{basename}.gcode.3mf"
        gp.write_bytes(b"PK")
        return SliceResult(gcode_path=gp, stdout="", stderr="", duration_s=0.0)

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer, slicer=bare_slicer).run(
        "a block", tmp_path, confirm_print=True
    )
    assert r.report.sliced is True
    assert r.report.gcode_lines is None
    assert r.report.slice_profiles is None
    assert r.report.to_text()  # does not raise


def test_report_describes_hardened_mesh_when_geometry_changed(tmp_path, monkeypatch):
    """ENG-001: when hardening actually alters the mesh, the report's integrity facts are
    re-derived from the hardened (exported/sliced) mesh, not the pre-harden input."""
    import trimesh

    from kimcad import pipeline as pipeline_mod
    from kimcad.hardening import HardenReport

    # A hardener that returns a *different* solid (a 10mm cube) and flags a real change.
    small = trimesh.creation.box(extents=[10, 10, 10])

    def fake_harden(mesh):
        return small, HardenReport(
            engine="manifold3d", ok=True, status="Error.NoError", genus=0,
            changed=True, before=(8, 12), after=(8, 12),
        )

    monkeypatch.setattr(pipeline_mod, "harden_mesh", fake_harden)
    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    r = _pipeline(provider, renderer).run("a block", tmp_path)
    # The report's volume now reflects the 10mm cube that was exported, not the 20mm input.
    assert abs(r.report.volume_mm3 - 1000.0) < 1.0
    assert r.report.watertight is True


def test_successful_slice_recorded_in_report(tmp_path):
    """A SliceResult carrying a G-code proof and resolved profiles is folded into the
    print report, including the exact machine/process/filament names used."""
    from kimcad.slicer import GcodeProof, SliceResult, SliceSettings

    def good_slicer(mesh_path, out_dir, basename):
        gpath = out_dir / f"{basename}.gcode.3mf"
        gpath.write_bytes(b"PK\x03\x04")  # bytes irrelevant; the proof is supplied here
        return SliceResult(
            gcode_path=gpath,
            stdout="",
            stderr="",
            duration_s=1.0,
            gcode_proof=GcodeProof(
                entries=("Metadata/plate_1.gcode",), line_count=42, has_motion=True,
                estimated_time="14m 45s", layer_count=100, filament_cm3=6.21,
            ),
            settings=SliceSettings(
                machine=Path("Bambu Lab P2S 0.4 nozzle.json"),
                process=Path("0.20mm Standard @BBL P2S.json"),
                filament=Path("Bambu PLA Basic @BBL P2S.json"),
            ),
        )

    provider = FakeProvider(_plan([20, 20, 20]))
    renderer, _ = _box_renderer((20, 20, 20))
    pipe = _pipeline(provider, renderer, slicer=good_slicer)
    r = pipe.run("a block", tmp_path, confirm_print=True)

    assert r.status is PipelineStatus.completed
    assert r.report.sliced is True
    assert r.report.gcode_lines == 42
    assert r.report.gcode_estimate and "14m 45s" in r.report.gcode_estimate
    assert r.report.gcode_path.endswith(".gcode.3mf")
    assert r.report.slice_profiles == (
        "Bambu Lab P2S 0.4 nozzle",
        "0.20mm Standard @BBL P2S",
        "Bambu PLA Basic @BBL P2S",
    )
    text = r.report.to_text()
    assert "G-code produced" in text
    assert "0.20mm Standard @BBL P2S" in text  # resolved profile shown to the user
    assert "Estimate:" in text and "14m 45s" in text  # print estimate surfaced


def test_is_model_unreachable_detects_connection_and_timeout_by_name():
    # The web layer's duck-typed detector: matches the OpenAI client's connection/timeout errors
    # by class name (so the pipeline needn't import openai), and nothing else.
    from kimcad.pipeline import _is_model_unreachable

    assert _is_model_unreachable(type("APIConnectionError", (Exception,), {})())
    assert _is_model_unreachable(type("APITimeoutError", (Exception,), {})())
    assert not _is_model_unreachable(ValueError("a real bug"))
    assert not _is_model_unreachable(RuntimeError("something else"))


# MS-3 — the design run reports its coarse phase so a multi-minute local run can show progress.
def test_run_reports_progress_phases_in_order(tmp_path):
    # object_type "block" matches no template, so this walks the full LLM path.
    render, _ = _box_renderer((20, 20, 20))
    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(make_plan([20, 20, 20])), renderer=render)
    phases: list[str] = []
    pipe.run("a 20mm block", tmp_path, progress=phases.append)
    assert phases == ["planning", "generating", "rendering", "validating"]


def test_run_progress_emits_extra_generate_render_on_a_retry(tmp_path):
    # A first render failure feeds back to the model and retries — the progress stream reflects the
    # extra generate+render pass, so the UI doesn't look stuck during a retry.
    render, _ = _box_renderer((20, 20, 20), fail_times=1)
    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(make_plan([20, 20, 20])), renderer=render)
    phases: list[str] = []
    pipe.run("a block", tmp_path, progress=phases.append)
    assert phases == [
        "planning", "generating", "rendering", "generating", "rendering", "validating",
    ]


def test_run_without_progress_callback_is_unaffected(tmp_path):
    # The callback is optional — omitting it must not change the result (backward compatible).
    render, _ = _box_renderer((20, 20, 20))
    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(make_plan([20, 20, 20])), renderer=render)
    result = pipe.run("a 20mm block", tmp_path)
    assert result.status is PipelineStatus.completed


def test_is_model_unreachable_covers_native_ollama_path():
    """Regression: the grammar-format (Ollama-native) path raises urllib/OSError exceptions,
    not the OpenAI client's APIConnectionError — _is_model_unreachable must catch both.

    Before the fix, URLError / TimeoutError / ConnectionRefusedError fell through to the
    generic 500 handler; after the fix, /api/design returns 200 model_unavailable instead.
    """
    import urllib.error
    from kimcad.pipeline import _is_model_unreachable

    # OpenAI client path (existing)
    class _FakeAPIConnectionError(Exception):
        pass
    _FakeAPIConnectionError.__name__ = "APIConnectionError"
    assert _is_model_unreachable(_FakeAPIConnectionError())

    class _FakeAPITimeoutError(Exception):
        pass
    _FakeAPITimeoutError.__name__ = "APITimeoutError"
    assert _is_model_unreachable(_FakeAPITimeoutError())

    # Ollama-native path (NEW): urllib + stdlib connection errors
    assert _is_model_unreachable(urllib.error.URLError("Connection refused"))
    assert _is_model_unreachable(TimeoutError())
    assert _is_model_unreachable(ConnectionRefusedError())
    assert _is_model_unreachable(ConnectionResetError())

    # Must NOT match unrelated exceptions
    assert not _is_model_unreachable(ValueError("bad input"))
    assert not _is_model_unreachable(RuntimeError("parse failure"))
    assert not _is_model_unreachable(KeyError("missing key"))


# --- TEST-101: the REAL model output through the full render+slice chain, end to end ----------
#
# Every test above runs FakeProvider — a canned plan + canned SCAD — so the model's OWN output is
# never rendered or sliced by the gate. This is the b5 failure shape: a real path (model → SCAD →
# render → watertight mesh → real OrcaSlicer → motion-bearing G-code) left unproven while proxy
# assertions (plan→family in test_landing_examples; FakeProvider's box in the pipeline tests) stay
# green. This test closes that gap: the REAL LLMProvider (default backend, qwen2.5:7b) plans 1-2
# prompts, the pipeline builds + renders + hardens the geometry, asserts the exported mesh is
# watertight, then slices it through the bundled OrcaSlicer and proves the .gcode.3mf carries a
# real motion-bearing toolpath (line_count > 100) — re-proven from disk via prove_gcode_3mf.
#
# Marked `live` so the gate's explicit `pytest -m live ... 0 skipped` step guards it (TEST-102),
# not only ci.sh's STRICT skip-grep. Kept to 2 prompts to bound wall-clock (real local inference
# + 2 real slices, ~minutes). Model output is non-deterministic, so this asserts the chain PARSES,
# is sized, renders watertight, and slices — NOT exact dimensions.


@functools.lru_cache(maxsize=1)
def _default_model_pulled() -> tuple[bool, str, str]:
    """(is the configured default chat model pulled, its name, the probe base_url). Cached so the
    Ollama probe runs at most once per session. Mirrors test_landing_examples._default_model."""
    from kimcad.model_advisor import probe_installed_models

    backend = Config.load().llm_backend(None)
    try:
        names = {m.name for m in probe_installed_models(backend.base_url)}
    except Exception:  # noqa: BLE001 - Ollama not running -> treat as not pulled (skip below)
        names = set()
    ok = any(backend.model_name == n or backend.model_name in n for n in names)
    return ok, backend.model_name, backend.base_url


def _orca_and_profiles_present() -> bool:
    try:
        cfg = Config.load()
        return cfg.binary_path("orcaslicer").exists() and cfg.orca_profiles_root().exists()
    except Exception:  # pragma: no cover - config/binary absent
        return False


# Prompts phrased around real template families (project box, trinket dish) so the geometry path
# is deterministic and bounded once the REAL model has planned them — exercising the full
# model→plan→family→render→harden→slice chain without gambling on a multi-minute free-form codegen
# run. (The model still does the real planning work; only the geometry is the deterministic twin.)
_LIVE_PIPELINE_PROMPTS = [
    "an 80 x 60 x 40 mm project box with a lid",
    "a round trinket dish, 90 mm across",
]


@pytest.mark.live  # TEST-101: invokes the REAL model AND the real OrcaSlicer; `-m "not live"` skips
@pytest.mark.skipif(
    not _orca_and_profiles_present(), reason="OrcaSlicer binary/profiles not present"
)
@pytest.mark.parametrize("prompt", _LIVE_PIPELINE_PROMPTS)
def test_live_real_model_output_renders_and_slices_end_to_end(tmp_path, prompt):
    """TEST-101: the WHOLE chain, live, on REAL model output — plan with qwen2.5:7b, generate the
    geometry, render, prove the exported mesh is watertight, slice with the real OrcaSlicer, and
    prove the result carries a real motion-bearing toolpath (line_count > 100), re-proven from disk
    with prove_gcode_3mf. No FakeProvider, no demo mode — the model's own output flows through the
    real renderer and slicer. Asserts PARSES + sized + watertight + slices, never exact dimensions
    (model output is non-deterministic)."""
    ok, model, base = _default_model_pulled()
    if not ok:
        pytest.skip(f"default chat model {model!r} not pulled at {base} (no Ollama lane — TEST-003)")

    from kimcad.llm_provider import LLMProvider
    from kimcad.slicer import prove_gcode_3mf

    config = Config.load()
    printer = config.printer("bambu_p2s")
    material = config.material("pla")
    provider = LLMProvider(config.llm_backend(None))

    # Real provider + the default real renderer (OpenSCAD) + the default real slicer (OrcaSlicer).
    pipe = Pipeline(config, printer, material, provider)
    result = pipe.run(prompt, tmp_path, confirm_print=True)

    # The model planned a buildable part that rendered and passed the gate.
    assert result.status is PipelineStatus.completed, (
        f"{prompt!r} did not complete: status={result.status} error={result.error!r}"
    )
    assert result.plan is not None and result.plan.object_type  # a real, parsed plan
    assert result.mesh_path is not None and result.mesh_path.exists()

    # The exported (hardened) mesh is watertight — a sliceable solid, not a shell.
    mesh = trimesh.load(str(result.mesh_path), file_type="stl")
    assert mesh.is_watertight, f"{prompt!r}: exported mesh is not watertight"
    assert result.report is not None and result.report.watertight is True

    # The real OrcaSlicer produced a motion-bearing toolpath.
    from kimcad.slicer import SliceResult

    assert isinstance(result.slice_result, SliceResult), (
        f"{prompt!r}: no slice (slice_error={result.slice_error!r})"
    )
    proof = result.slice_result.gcode_proof
    assert proof is not None and proof.has_motion
    assert proof.line_count > 100, f"{prompt!r}: near-empty toolpath ({proof.line_count} lines)"

    # Independently re-prove from disk: open the actual .gcode.3mf zip, require motion-bearing
    # G-code — not a string assertion on a constructed command.
    reproved = prove_gcode_3mf(result.slice_result.gcode_path)
    assert reproved.has_motion and reproved.line_count > 100
    print(
        f"\n[TEST-101 PROOF] prompt={prompt!r} object_type={result.plan.object_type!r}\n"
        f"  gcode={result.slice_result.gcode_path.name} has_motion={reproved.has_motion} "
        f"line_count={reproved.line_count} layers={reproved.layer_count} "
        f"time={reproved.estimated_time} filament_mm={reproved.filament_mm}"
    )
