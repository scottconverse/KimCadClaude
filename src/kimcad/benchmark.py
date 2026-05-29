"""Phase-1 benchmark harness — the done-gate (spec §4, Appendix B).

Runs a fixed set of plain-English prompts end to end through the pipeline and scores
the batch against the §4.2 thresholds. This is the gate that says "the architecture
works" before Phases 2–4 are built.

The harness is data-driven: the prompt set (Appendix B) and the pass thresholds
(§4.2) are loaded from ``bench/*.yaml`` rather than hard-coded, so the same code
grades any prompt set. The scoring logic is decoupled from execution (a ``run_one``
callable) so it is unit-testable without an LLM or the binaries.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BenchCase:
    id: str
    prompt: str
    # Optional acceptance hints from Appendix B, used for richer grading once the
    # spec content is available. Absent hints just aren't checked.
    expect_object_type: str | None = None
    max_bbox_mm: list[float] | None = None
    notes: str | None = None


@dataclass
class CaseOutcome:
    id: str
    status: str  # PipelineStatus value
    gate_status: str | None
    render_attempts: int
    duration_s: float
    error: str | None = None

    @property
    def passed(self) -> bool:
        # A case passes if the pipeline ran to completion (the Gate did not fail,
        # or the user proceeded). Clarification / render-failure / gate-failure
        # are all non-passes for the unattended benchmark.
        return self.status == "completed"


@dataclass
class BenchSummary:
    outcomes: list[CaseOutcome] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def success_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    @property
    def mean_duration_s(self) -> float:
        if not self.outcomes:
            return 0.0
        return sum(o.duration_s for o in self.outcomes) / len(self.outcomes)

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for o in self.outcomes:
            counts[o.status] = counts.get(o.status, 0) + 1
        return counts

    def meets(self, min_success_rate: float) -> bool:
        return self.success_rate >= min_success_rate

    def to_text(self, min_success_rate: float | None = None) -> str:
        lines = [
            f"Benchmark: {self.passed}/{self.total} passed ({self.success_rate * 100:.0f}%)",
            f"Mean wall-clock per prompt: {self.mean_duration_s:.1f}s",
            f"Status breakdown: {self.status_counts()}",
        ]
        if min_success_rate is not None:
            verdict = "PASS" if self.meets(min_success_rate) else "FAIL"
            lines.append(f"Done-gate (>= {min_success_rate * 100:.0f}%): {verdict}")
        for o in self.outcomes:
            mark = "ok " if o.passed else "XX "
            extra = f" — {o.error}" if o.error else ""
            lines.append(
                f"  {mark}{o.id}: {o.status}"
                f" [gate={o.gate_status}, attempts={o.render_attempts},"
                f" {o.duration_s:.1f}s]{extra}"
            )
        return "\n".join(lines)


def load_cases(path: str | Path) -> list[BenchCase]:
    """Load benchmark cases from a YAML file.

    Expected shape:

        cases:
          - id: b01
            prompt: "A wall bracket for a 20mm pipe..."
            expect_object_type: bracket   # optional
            max_bbox_mm: [120, 80, 40]    # optional
    """
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cases = []
    for raw in data.get("cases", []):
        cases.append(
            BenchCase(
                id=str(raw["id"]),
                prompt=str(raw["prompt"]),
                expect_object_type=raw.get("expect_object_type"),
                max_bbox_mm=raw.get("max_bbox_mm"),
                notes=raw.get("notes"),
            )
        )
    return cases


def run_benchmark(
    cases: list[BenchCase],
    run_one: Callable[[BenchCase], CaseOutcome],
) -> BenchSummary:
    """Execute every case via ``run_one`` and collect a summary.

    ``run_one`` owns the actual pipeline invocation (and timing); the harness only
    aggregates. A raised exception is captured as a failed outcome so one bad case
    can't abort the batch.
    """
    summary = BenchSummary()
    for case in cases:
        try:
            summary.outcomes.append(run_one(case))
        except Exception as e:  # defensive: never let one case kill the run
            summary.outcomes.append(
                CaseOutcome(
                    id=case.id,
                    status="error",
                    gate_status=None,
                    render_attempts=0,
                    duration_s=0.0,
                    error=f"{type(e).__name__}: {e}",
                )
            )
    return summary


def make_case_runner(pipeline: Any, out_root: Path) -> Callable[[BenchCase], CaseOutcome]:
    """Bind a Pipeline into a ``run_one`` that times a single case.

    Each case renders into its own ``out_root/<id>/`` directory. ``pipeline`` is
    duck-typed (anything with ``.run(prompt, out_dir) -> PipelineResult``) so this
    stays importable without forcing a live provider at module load.
    """
    import time

    def run_one(case: BenchCase) -> CaseOutcome:
        out_dir = out_root / case.id
        started = time.monotonic()
        result = pipeline.run(case.prompt, out_dir)
        duration = time.monotonic() - started
        gate_status = str(result.gate.status) if getattr(result, "gate", None) else None
        return CaseOutcome(
            id=case.id,
            status=result.status.value,
            gate_status=gate_status,
            render_attempts=result.render_attempts,
            duration_s=duration,
            error=result.error,
        )

    return run_one
