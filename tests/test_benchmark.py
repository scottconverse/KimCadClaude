from dataclasses import dataclass
from pathlib import Path

import pytest

from kimcad.benchmark import (
    BenchCase,
    CaseOutcome,
    grade_correct_dimensions,
    grade_matches_request,
    grade_slices_clean,
    load_cases,
    make_case_runner,
    run_benchmark,
)


def _outcome(id, status, gate="pass", attempts=1, dur=1.0, error=None):
    return CaseOutcome(
        id=id,
        status=status,
        gate_status=gate,
        render_attempts=attempts,
        duration_s=dur,
        error=error,
    )


def test_load_cases(tmp_path):
    p = tmp_path / "prompts.yaml"
    p.write_text(
        "cases:\n"
        "  - id: b01\n"
        '    prompt: "A wall bracket"\n'
        "    expect_object_type: bracket\n"
        "    max_bbox_mm: [120, 80, 40]\n"
        "  - id: b02\n"
        '    prompt: "A knob"\n',
        encoding="utf-8",
    )
    cases = load_cases(p)
    assert len(cases) == 2
    assert cases[0].id == "b01"
    assert cases[0].expect_object_type == "bracket"
    assert cases[0].max_bbox_mm == [120, 80, 40]
    assert cases[1].expect_object_type is None


def test_summary_scoring():
    cases = [BenchCase(id=f"b{i}", prompt="x") for i in range(4)]
    outcomes = {
        "b0": _outcome("b0", "completed"),
        "b1": _outcome("b1", "completed", gate="warn"),
        "b2": _outcome("b2", "gate_failed", gate="fail"),
        "b3": _outcome("b3", "render_failed", gate=None, error="boom"),
    }
    summary = run_benchmark(cases, lambda c: outcomes[c.id])

    assert summary.total == 4
    assert summary.passed == 2  # only completed cases pass
    assert summary.success_rate == 0.5
    assert summary.meets(0.5)
    assert not summary.meets(0.9)
    assert summary.status_counts()["completed"] == 2


def test_run_benchmark_captures_exceptions():
    cases = [BenchCase(id="boom", prompt="x")]

    def explode(case):
        raise RuntimeError("kaboom")

    summary = run_benchmark(cases, explode)
    assert summary.total == 1
    assert summary.passed == 0
    assert summary.outcomes[0].status == "error"
    assert "kaboom" in summary.outcomes[0].error


def test_to_text_includes_verdict():
    summary = run_benchmark(
        [BenchCase(id="b0", prompt="x")],
        lambda c: _outcome("b0", "completed"),
    )
    text = summary.to_text(min_success_rate=0.9)
    assert "Done-gate" in text
    assert "PASS" in text


def test_to_text_is_console_safe():
    # The verdict line must encode on a Windows cp1252 console; the >= glyph
    # (formerly the ≥ character) once crashed `kimcad bench` at print time,
    # after a full batch had run.
    summary = run_benchmark(
        [BenchCase(id="b0", prompt="x")],
        lambda c: _outcome("b0", "completed"),
    )
    text = summary.to_text(min_success_rate=0.8)
    text.encode("cp1252")  # must not raise UnicodeEncodeError
    assert ">=" in text


def test_make_case_runner_times_and_maps(tmp_path):
    @dataclass
    class FakeResult:
        status: object
        render_attempts: int = 1
        error: str | None = None
        gate: object = None

    @dataclass
    class FakeStatus:
        value: str

    class FakePipeline:
        def run(self, prompt, out_dir):
            assert isinstance(out_dir, Path)
            return FakeResult(status=FakeStatus("completed"))

    runner = make_case_runner(FakePipeline(), tmp_path)
    outcome = runner(BenchCase(id="b01", prompt="a block"))
    assert outcome.id == "b01"
    assert outcome.status == "completed"
    assert outcome.passed
    # A minimal result with no plan/gate/report leaves every grading axis unassessed.
    assert outcome.matches_request is None
    assert outcome.correct_dimensions is None
    assert outcome.slices_clean is None
    # completed + no axis assessed-and-failed => the stricter grade still passes.
    assert outcome.graded_passed


# --- 3-axis grading: matches-request -------------------------------------------

@pytest.mark.parametrize("produced,expected,result", [
    ("wall hook", "hook", True),          # token contained
    ("pegboard hook", "hook", True),
    ("l-bracket", "bracket", True),       # hyphen normalized
    ("cable clip", "clip", True),
    ("drawer divider", "divider", True),
    ("cylindrical spacer", "spacer", True),
    ("two-part enclosure", "enclosure", True),
    ("Hooks", "hook", True),              # case + plural
    ("box", "hook", False),               # wrong kind
    ("wall mount", "holder", False),      # no shared token
    ("anything", None, None),             # no expectation -> not assessed
    (None, "hook", False),                # planner produced nothing
])
def test_grade_matches_request(produced, expected, result):
    assert grade_matches_request(produced, expected) is result


def test_grade_matches_request_uses_template_name_fallback():
    # Planner's object_type misses, but the matched family name carries the token.
    assert grade_matches_request("widget", "hook", template_name="wall_hook") is True


# --- 3-axis grading: correct-dimensions ----------------------------------------

def test_grade_correct_dimensions_mismatch_fails():
    assert grade_correct_dimensions({"dim.mismatch"}, (50, 50, 10), [50, 50, 10]) is False


def test_grade_correct_dimensions_match_passes():
    assert grade_correct_dimensions({"dim.match"}, (50, 50, 10), None) is True


def test_grade_correct_dimensions_exceeds_ceiling_fails():
    # Built bigger than the prompt's stated envelope on Z (10 -> 12, past 0.5 mm tol).
    assert grade_correct_dimensions(set(), (50, 50, 12), [50, 50, 10]) is False


def test_grade_correct_dimensions_match_within_ceiling_passes():
    # The gate confirmed the size AND it fits the ceiling -> a real pass.
    assert grade_correct_dimensions({"dim.match"}, (49.8, 50.0, 10.2), [50, 50, 10]) is True


def test_grade_correct_dimensions_ceiling_only_is_unassessed():
    # No gate target, the part is within the ceiling: not too big, but the size was
    # never confirmed -> None (the ceiling is an upper bound, not positive evidence).
    assert grade_correct_dimensions(set(), (49.8, 50.0, 10.2), [50, 50, 10]) is None


def test_grade_correct_dimensions_undersized_fits_ceiling_is_not_a_pass():
    # BENCH-001 regression: a grossly undersized part (5x5x1 vs requested 50x50x10)
    # fits under the ceiling but must NOT grade as a dimensional pass.
    assert grade_correct_dimensions(set(), (5, 5, 1), [50, 50, 10]) is None


def test_grade_correct_dimensions_no_signal_is_unassessed():
    # No gate dim finding and no stated max -> nothing to check.
    assert grade_correct_dimensions({"dim.no_target"}, (50, 50, 10), None) is None


def test_grade_correct_dimensions_mismatch_beats_ceiling():
    # A gate mismatch is decisive even if it happens to fit the ceiling.
    assert grade_correct_dimensions({"dim.mismatch"}, (10, 10, 10), [50, 50, 50]) is False


# --- 3-axis grading: slices-clean ----------------------------------------------

def test_grade_slices_clean_not_attempted_is_none():
    assert grade_slices_clean(False, None, attempted=False) is None
    assert grade_slices_clean(True, None, attempted=False) is None


def test_grade_slices_clean_sliced_passes():
    assert grade_slices_clean(True, None, attempted=True) is True


def test_grade_slices_clean_gate_failed_no_slice_fails():
    # Attempted (confirm_print) but the gate failed so nothing sliced.
    assert grade_slices_clean(False, None, attempted=True) is False


def test_grade_slices_clean_slice_error_fails():
    assert grade_slices_clean(False, "no process profile", attempted=True) is False


# --- CaseOutcome.graded_passed -------------------------------------------------

def test_graded_passed_completed_all_axes_pass():
    o = CaseOutcome("b", "completed", "pass", 1, 1.0,
                    matches_request=True, correct_dimensions=True, slices_clean=True)
    assert o.graded_passed


def test_graded_passed_one_failed_axis_blocks():
    o = CaseOutcome("b", "completed", "pass", 1, 1.0,
                    matches_request=True, correct_dimensions=False, slices_clean=None)
    assert not o.graded_passed


def test_graded_passed_requires_completion():
    o = CaseOutcome("b", "gate_failed", "fail", 1, 1.0,
                    matches_request=True, correct_dimensions=True)
    assert not o.graded_passed


def test_graded_passed_unassessed_axes_do_not_block():
    o = CaseOutcome("b", "completed", "pass", 1, 1.0)  # all axes None
    assert o.graded_passed


# --- BenchSummary axis tallies + graded rate -----------------------------------

def test_axis_tally_and_graded_rate():
    cases = [BenchCase(id=f"b{i}", prompt="x") for i in range(3)]
    outcomes = {
        "b0": CaseOutcome("b0", "completed", "pass", 1, 1.0,
                          matches_request=True, correct_dimensions=True, slices_clean=True),
        "b1": CaseOutcome("b1", "completed", "pass", 1, 1.0,
                          matches_request=True, correct_dimensions=False, slices_clean=None),
        "b2": CaseOutcome("b2", "completed", "pass", 1, 1.0,
                          matches_request=False, correct_dimensions=True, slices_clean=None),
    }
    summary = run_benchmark(cases, lambda c: outcomes[c.id])

    assert summary.passed == 3                 # all completed
    assert summary.graded_passed == 1          # only b0 clears all assessed axes
    assert summary.axis_tally("matches_request") == (2, 3)
    assert summary.axis_tally("correct_dimensions") == (2, 3)
    assert summary.axis_tally("slices_clean") == (1, 1)  # only b0 assessed
    assert summary.meets_graded(0.33)
    assert not summary.meets_graded(0.5)


def test_to_text_shows_three_axis_block_and_is_console_safe():
    cases = [BenchCase(id="b0", prompt="x")]
    summary = run_benchmark(
        cases,
        lambda c: CaseOutcome("b0", "completed", "pass", 1, 1.0,
                              matches_request=True, correct_dimensions=False, slices_clean=None),
    )
    text = summary.to_text(min_success_rate=0.8)
    text.encode("cp1252")  # the axis marks (ok/XX/--) must stay cp1252-safe
    assert "Graded (3-axis)" in text
    assert "matches-request" in text
    assert "req=ok" in text and "dim=XX" in text and "slice=--" in text


def test_runner_grades_a_rich_result_and_requests_slice(tmp_path):
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
    class FakeResult:
        status: object
        plan: object
        gate: object
        report: object
        template: object
        render_attempts: int = 1
        error: str | None = None
        slice_error: str | None = None

    @dataclass
    class FakePlan:
        object_type: str
        bounding_box_mm: list

    seen = {}

    class FakePipeline:
        def run(self, prompt, out_dir, **kwargs):
            seen.update(kwargs)
            return FakeResult(
                status=FakeStatus("completed"),
                plan=FakePlan(object_type="wall hook", bounding_box_mm=[40, 25, 65]),
                gate=FakeGate([FakeFinding("dim.match")]),
                report=FakeReport(actual_bbox_mm=(39.8, 25.0, 64.5), sliced=True),
                template=FakeMatch(family=FakeFamily("wall_hook")),
            )

    runner = make_case_runner(FakePipeline(), tmp_path, slice_for_grade=True)
    case = BenchCase(id="b01", prompt="a wall hook",
                     expect_object_type="hook", max_bbox_mm=[40, 25, 65])
    outcome = runner(case)

    assert seen.get("confirm_print") is True   # slicing was requested
    assert outcome.matches_request is True
    assert outcome.correct_dimensions is True  # dim.match + within ceiling
    assert outcome.slices_clean is True
    assert outcome.object_type == "wall hook"
    assert outcome.actual_bbox_mm == (39.8, 25.0, 64.5)
    assert outcome.graded_passed
