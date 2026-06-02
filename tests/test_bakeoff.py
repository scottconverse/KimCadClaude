"""Stage 6 Slice 4 -- the model bake-off harness (Qwen-vs-gemma comparison).

The comparison (compare_runs) is pure and exercised with synthetic BenchSummary objects.
run_bakeoff is covered with a fake pipeline (no live model). The LIVE bake-off -- real
Ollama with both models pulled -- is the hand-off step, not tested here.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from kimcad.bakeoff import Bakeoff, ModelRun, compare_runs, run_bakeoff
from kimcad.benchmark import BenchCase, BenchSummary, CaseOutcome


# --- synthetic summaries -------------------------------------------------------

def _graded_outcome(dur: float) -> CaseOutcome:
    return CaseOutcome("x", "completed", "pass", 1, dur,
                       matches_request=True, correct_dimensions=True, slices_clean=True)


def _completed_not_graded(dur: float) -> CaseOutcome:
    # Completed, but fails one assessed axis -> counts for `passed`, not `graded_passed`.
    return CaseOutcome("x", "completed", "pass", 1, dur,
                       matches_request=True, correct_dimensions=False, slices_clean=True)


def _summary(graded: int, total: int, dur: float = 10.0) -> BenchSummary:
    outs = [_graded_outcome(dur) for _ in range(graded)]
    outs += [_completed_not_graded(dur) for _ in range(total - graded)]
    return BenchSummary(outcomes=outs)


def _run(backend: str, model: str, graded: int, total: int, dur: float = 10.0) -> ModelRun:
    return ModelRun(backend=backend, model_name=model, summary=_summary(graded, total, dur))


# --- compare_runs --------------------------------------------------------------

def test_switch_when_challenger_has_higher_graded_rate():
    runs = [_run("local", "gemma", 8, 10, 140), _run("local_qwen", "qwen", 9, 10, 60)]
    rec = compare_runs(runs, incumbent="local")
    assert rec.switch is True
    assert rec.best == "local_qwen"
    assert "graded rate" in rec.reason


def test_keep_when_challenger_loses_on_graded_rate():
    # Incumbent is the best -> "already the best", no switch.
    runs = [_run("local", "gemma", 9, 10, 60), _run("local_qwen", "qwen", 7, 10, 60)]
    rec = compare_runs(runs, incumbent="local")
    assert rec.switch is False
    assert rec.best == "local"


def test_keep_when_challenger_ties_graded_but_is_slower():
    runs = [_run("local", "gemma", 8, 10, 60), _run("local_qwen", "qwen", 8, 10, 140)]
    rec = compare_runs(runs, incumbent="local")
    # local ranks higher (same graded + completion, faster) -> it's the best -> keep.
    assert rec.best == "local"
    assert rec.switch is False


def test_switch_on_a_graded_tie_when_challenger_is_faster():
    runs = [_run("local", "gemma", 8, 10, 140), _run("local_qwen", "qwen", 8, 10, 60)]
    rec = compare_runs(runs, incumbent="local")
    assert rec.best == "local_qwen"
    assert rec.switch is True
    assert "faster" in rec.reason


def test_switch_on_graded_win_even_if_slower_and_reason_omits_faster():
    runs = [_run("local", "gemma", 8, 10, 60), _run("local_qwen", "qwen", 9, 10, 200)]
    rec = compare_runs(runs, incumbent="local")
    assert rec.best == "local_qwen"
    assert rec.switch is True
    assert "faster" not in rec.reason  # it won on quality, not speed


def test_no_switch_when_incumbent_absent_from_the_bakeoff():
    runs = [_run("a", "m_a", 9, 10), _run("b", "m_b", 8, 10)]
    rec = compare_runs(runs, incumbent="zzz")
    assert rec.switch is False
    assert "not in this bake-off" in rec.reason
    # This reason path surfaces to the console -> must be ASCII / cp1252-safe.
    assert rec.reason.isascii()
    rec.reason.encode("cp1252")


def test_did_not_clear_reason_is_console_safe():
    # Challenger ranks best (graded tie, higher completion) but is slower -> it does NOT
    # clear the bar, so keep the incumbent. This reason path also prints to the console.
    chal = BenchSummary(outcomes=[
        _graded_outcome(200), _graded_outcome(200), _completed_not_graded(200),
    ])  # graded 2/3, completed 3/3, slow
    inc = BenchSummary(outcomes=[
        _graded_outcome(10), _graded_outcome(10),
        CaseOutcome("x", "gate_failed", "fail", 1, 10),
    ])  # graded 2/3, completed 2/3, fast
    runs = [ModelRun("local_qwen", "qwen", chal), ModelRun("local", "gemma", inc)]
    rec = compare_runs(runs, incumbent="local")
    assert rec.switch is False
    assert "did not clear the bar" in rec.reason
    assert rec.reason.isascii()
    rec.reason.encode("cp1252")


def test_no_incumbent_reports_best_without_switching():
    runs = [_run("a", "m_a", 9, 10), _run("b", "m_b", 8, 10)]
    rec = compare_runs(runs, incumbent=None)
    assert rec.best == "a"
    assert rec.switch is False
    assert "scored highest" in rec.reason


def test_ranking_breaks_graded_tie_on_completion_then_speed():
    # Same graded rate; a higher completion rate should rank higher than just being fast.
    more_completed = BenchSummary(outcomes=[
        _graded_outcome(200), _graded_outcome(200), _completed_not_graded(200),
    ])  # graded 2/3, completed 3/3
    fewer_completed = BenchSummary(outcomes=[
        _graded_outcome(10), _graded_outcome(10),
        CaseOutcome("x", "gate_failed", "fail", 1, 10),
    ])  # graded 2/3, completed 2/3, but faster
    runs = [
        ModelRun("slow_complete", "m1", more_completed),
        ModelRun("fast_incomplete", "m2", fewer_completed),
    ]
    rec = compare_runs(runs, incumbent=None)
    assert rec.best == "slow_complete"  # completion beats speed in the tiebreak order


def test_empty_runs_raises():
    with pytest.raises(ValueError):
        compare_runs([], incumbent="local")


# --- Bakeoff.to_text -----------------------------------------------------------

def test_to_text_table_and_recommendation_are_console_safe():
    bo = Bakeoff(
        runs=[_run("local", "gemma4:e4b", 8, 10, 140),
              _run("local_qwen", "qwen2.5-coder:1.5b", 9, 10, 60)],
        incumbent="local",
    )
    text = bo.to_text()
    text.encode("cp1252")  # must stay cp1252-safe
    assert text.isascii()  # the module keeps printed strings ASCII (no em-dashes)
    assert "backend" in text and "graded" in text and "mean_s" in text
    assert "gemma4:e4b" in text and "qwen2.5-coder:1.5b" in text
    assert "Recommendation:" in text
    assert "SWITCH default to local_qwen" in text
    assert "(default)" in text  # the incumbent is tagged


def test_to_text_keep_recommendation():
    bo = Bakeoff(
        runs=[_run("local", "gemma", 9, 10, 60), _run("local_qwen", "qwen", 7, 10, 60)],
        incumbent="local",
    )
    text = bo.to_text()
    assert "KEEP default local" in text


# --- run_bakeoff wiring --------------------------------------------------------

def test_run_bakeoff_runs_each_backend_and_requests_slice(tmp_path):
    @dataclass
    class FakeStatus:
        value: str

    @dataclass
    class FakeFinding:
        code: str

    @dataclass
    class FakeGate:
        findings: list
        status: str = "pass"

    @dataclass
    class FakeFamily:
        name: str

    @dataclass
    class FakeMatch:
        family: object

    @dataclass
    class FakeReport:
        actual_bbox_mm: tuple
        sliced: bool

    @dataclass
    class FakePlan:
        object_type: str
        bounding_box_mm: list

    @dataclass
    class FakeResult:
        status: object
        plan: object
        gate: object
        report: object
        template: object
        render_attempts: int = 1
        error: str | None = None
        slice_error: str | None = None

    seen_confirm = []

    class FakePipeline:
        def __init__(self, backend):
            self.backend = backend

        def run(self, prompt, out_dir, **kwargs):
            seen_confirm.append(kwargs.get("confirm_print"))
            return FakeResult(
                status=FakeStatus("completed"),
                plan=FakePlan(object_type="wall hook", bounding_box_mm=[40, 25, 65]),
                gate=FakeGate([FakeFinding("dim.match")]),
                report=FakeReport(actual_bbox_mm=(39.8, 25.0, 64.5), sliced=True),
                template=FakeMatch(family=FakeFamily("wall_hook")),
            )

    cases = [BenchCase(id="b01", prompt="a wall hook",
                       expect_object_type="hook", max_bbox_mm=[40, 25, 65])]
    models = {"local_qwen": "qwen2.5-coder:1.5b", "local": "gemma4:e4b"}

    bakeoff = run_bakeoff(
        ["local_qwen", "local"],
        make_pipeline=lambda key: FakePipeline(key),
        model_name_for=lambda key: models[key],
        cases=cases,
        out_root=tmp_path,
        slice_for_grade=True,
        incumbent="local",
    )

    assert [r.backend for r in bakeoff.runs] == ["local_qwen", "local"]  # order preserved
    assert bakeoff.runs[0].model_name == "qwen2.5-coder:1.5b"
    assert all(r.summary.total == 1 for r in bakeoff.runs)
    assert all(r.summary.graded_passed == 1 for r in bakeoff.runs)  # the fake fully passes
    assert seen_confirm == [True, True]  # slicing requested for both backends
    assert bakeoff.incumbent == "local"


def test_run_bakeoff_without_slice_does_not_request_confirm(tmp_path):
    @dataclass
    class FakeStatus:
        value: str

    @dataclass
    class FakeResult:
        status: object
        render_attempts: int = 1
        error: str | None = None
        gate: object = None

    seen_confirm = []

    class FakePipeline:
        def run(self, prompt, out_dir, **kwargs):
            seen_confirm.append(kwargs.get("confirm_print"))
            return FakeResult(status=FakeStatus("completed"))

    cases = [BenchCase(id="b01", prompt="x")]
    bakeoff = run_bakeoff(
        ["a", "b"],
        make_pipeline=lambda key: FakePipeline(),
        model_name_for=lambda key: key,
        cases=cases,
        out_root=tmp_path,
        slice_for_grade=False,
        incumbent="a",
    )
    assert seen_confirm == [None, None]  # no confirm_print kwarg when not slicing
    assert len(bakeoff.runs) == 2
