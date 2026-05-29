from dataclasses import dataclass
from pathlib import Path

from kimcad.benchmark import (
    BenchCase,
    CaseOutcome,
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
