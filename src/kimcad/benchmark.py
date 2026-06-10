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

import re
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
    # --- Stage 6 Slice 3: the spec's 3-axis grading (§4.2). Each is a tri-state:
    # True (assessed, passed), False (assessed, failed), None (NOT assessed — e.g.
    # slices_clean when the batch ran without --slice, or matches_request when a case
    # carries no expect_object_type). A None axis never counts against a case, so the
    # grade stays honest about what was actually measured. ---
    object_type: str | None = None  # the planner's object_type (what it built)
    target_bbox_mm: list[float] | None = None  # the plan's declared envelope
    actual_bbox_mm: tuple[float, float, float] | None = None  # what was rendered
    matches_request: bool | None = None  # object_type aligns with the expected family
    correct_dimensions: bool | None = None  # built size matches the plan / fits the ask
    slices_clean: bool | None = None  # produced a real motion-bearing slice

    @property
    def passed(self) -> bool:
        # A case passes if the pipeline ran to completion (the Gate did not fail,
        # or the user proceeded). Clarification / render-failure / gate-failure
        # are all non-passes for the unattended benchmark.
        return self.status == "completed"

    @property
    def graded_passed(self) -> bool:
        """The stricter, 3-axis verdict: completed AND no *assessed* axis failed.

        Axes left None (not measured) don't block — this is what keeps the grade
        honest when slicing wasn't run or a case has no expected type. It's the
        signal the model bake-off (Slice 4) compares between models, distinct from
        the coarse completion ``passed`` the done-gate threshold uses."""
        if self.status != "completed":
            return False
        return all(
            axis is not False
            for axis in (self.matches_request, self.correct_dimensions, self.slices_clean)
        )


# --- 3-axis grading helpers (pure; unit-tested without an LLM or the binaries) -------

def _grade_tokens(text: str) -> set[str]:
    """Normalize an object-type string into a set of singularized word tokens, so
    ``"Wall-Hooks"``, ``"wall hook"`` and ``"hook"`` all share the token ``hook``.
    Mirrors the template registry's normalization (lower/trim/collapse separators)
    plus the same tiny ``-s`` plural strip, kept local so benchmark grading doesn't
    depend on the template module's internals."""
    normalized = re.sub(r"[\s_\-]+", " ", (text or "").strip().lower())
    tokens: set[str] = set()
    for word in normalized.split():
        word = re.sub(r"[^a-z0-9]", "", word)
        if not word:
            continue
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        tokens.add(word)
    return tokens


def grade_matches_request(
    produced_object_type: str | None,
    expected_object_type: str | None,
    *,
    template_name: str | None = None,
) -> bool | None:
    """Did the planner produce the *kind of thing* the prompt asked for?

    Token-tolerant: the expected type (e.g. ``"hook"``) matches the produced type
    (``"pegboard hook"``) or the matched template family name when they share a
    normalized, singularized token. Returns None when the case states no expectation
    (nothing to grade against)."""
    if not expected_object_type:
        return None
    expected = _grade_tokens(expected_object_type)
    if not expected:
        return None
    produced = _grade_tokens(produced_object_type or "")
    if template_name:
        produced |= _grade_tokens(template_name)
    return bool(expected & produced)


def grade_correct_dimensions(
    gate_codes: set[str],
    actual_bbox_mm: tuple[float, float, float] | None,
    max_bbox_mm: list[float] | None,
) -> bool | None:
    """Is the built part dimensionally right?

    Two independent ways to fail, either of which is decisive:
    - the gate raised ``dim.mismatch`` — the geometry doesn't match its own plan's
      target envelope on some axis (the gate's flat 0.5 mm per-axis tolerance);
    - the rendered part exceeds the prompt's stated envelope (``max_bbox_mm``) on any
      axis beyond that tolerance — it's bigger than what was asked for.

    Passes only when the gate confirmed the dimensions (``dim.match``). The ceiling is
    an *upper bound*: fitting under it rules out "too big" but is NOT positive evidence
    of the right size (a grossly undersized part also fits) — so it can only turn the
    verdict to False, never assert True on its own. Returns None when there's no gate
    target and the part is within (or has no) ceiling: not too big, but size unconfirmed."""
    from kimcad.printability import dim_tolerance

    if "dim.mismatch" in gate_codes:
        return False
    verdict: bool | None = True if "dim.match" in gate_codes else None
    if max_bbox_mm and actual_bbox_mm:
        for got, ceiling in zip(actual_bbox_mm, max_bbox_mm):
            if got > ceiling + dim_tolerance(ceiling):
                return False  # exceeds the requested envelope — decisive
    return verdict


def grade_slices_clean(
    sliced: bool,
    slice_error: str | None,
    *,
    attempted: bool,
) -> bool | None:
    """Did the part slice to a real, motion-bearing toolpath?

    Only assessed when slicing was actually attempted (the batch ran with --slice and
    the pipeline got ``confirm_print=True``); otherwise None. A part that gate-failed
    never reaches the slicer, so ``sliced`` is False there — correctly a non-pass on
    this axis. A slice refusal (no profile) or operational failure sets ``slice_error``
    and grades False."""
    if not attempted:
        return None
    if slice_error:
        return False
    return bool(sliced)


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
    def graded_passed(self) -> int:
        """Cases passing the stricter 3-axis grade (completed + no assessed axis failed)."""
        return sum(1 for o in self.outcomes if o.graded_passed)

    @property
    def graded_success_rate(self) -> float:
        return self.graded_passed / self.total if self.total else 0.0

    def meets_graded(self, min_success_rate: float) -> bool:
        return self.graded_success_rate >= min_success_rate

    def axis_tally(self, axis: str) -> tuple[int, int]:
        """``(passed, assessed)`` for one grading axis across the batch. ``assessed``
        excludes cases where the axis is None (not measured), so the ratio is honest."""
        values = [getattr(o, axis) for o in self.outcomes]
        assessed = [v for v in values if v is not None]
        return sum(1 for v in assessed if v), len(assessed)

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

    @staticmethod
    def _axis_mark(value: bool | None) -> str:
        """ASCII tri-state mark (cp1252-safe): ok / XX / -- (not assessed)."""
        return "ok" if value is True else ("XX" if value is False else "--")

    def to_text(self, min_success_rate: float | None = None) -> str:
        lines = [
            f"Benchmark: {self.passed}/{self.total} completed "
            f"({self.success_rate * 100:.0f}%)",
            f"Mean wall-clock per prompt: {self.mean_duration_s:.1f}s",
            f"Status breakdown: {self.status_counts()}",
        ]
        if min_success_rate is not None:
            verdict = "PASS" if self.meets(min_success_rate) else "FAIL"
            lines.append(f"Done-gate (>= {min_success_rate * 100:.0f}%): {verdict}")

        # 3-axis grading rollup (spec 4.2): completion is the coarse gate; these three
        # axes are how the model bake-off judges quality beyond "did it finish".
        mr_p, mr_n = self.axis_tally("matches_request")
        cd_p, cd_n = self.axis_tally("correct_dimensions")
        sc_p, sc_n = self.axis_tally("slices_clean")
        lines.append(
            f"Graded (3-axis): {self.graded_passed}/{self.total} "
            f"({self.graded_success_rate * 100:.0f}%)"
        )
        lines.append(
            "  matches-request "
            f"{mr_p}/{mr_n} | correct-dimensions {cd_p}/{cd_n} | slices-clean {sc_p}/{sc_n}"
            "  (passed/assessed)"
        )

        for o in self.outcomes:
            mark = "ok " if o.passed else "XX "
            extra = f" -- {o.error}" if o.error else ""
            axes = (
                f" {{req={self._axis_mark(o.matches_request)},"
                f" dim={self._axis_mark(o.correct_dimensions)},"
                f" slice={self._axis_mark(o.slices_clean)}}}"
            )
            lines.append(
                f"  {mark}{o.id}: {o.status}"
                f" [gate={o.gate_status}, attempts={o.render_attempts},"
                f" {o.duration_s:.1f}s]{axes}{extra}"
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
            # QA-A-001 (stage-A gate): a DOWN MODEL SERVER is not a per-case outcome — it
            # fails every remaining case identically and deserves the friendly model-down
            # exit, not N "APIConnectionError" rows and a green exit code. Re-raise so the
            # CLI's central mapping (exit 2 + guidance) owns it; genuine per-case errors
            # (a bad render, one weird prompt) still degrade case-by-case.
            from kimcad.pipeline import _is_model_unreachable

            if _is_model_unreachable(e):
                raise
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


def _persist_case_artifacts(out_dir: Path, result: Any) -> None:
    """Best-effort dump of the plan, report, and outcome for offline diagnosis.

    The pipeline already writes the SCAD and mesh; without the plan envelope and the
    gate findings a failing case can't be debugged without re-running the model (which
    is minutes of CPU per prompt). Diagnosis aid only — never fail a run over a write.
    """
    try:
        plan = getattr(result, "plan", None)
        if plan is not None:
            (out_dir / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        report = getattr(result, "report", None)
        if report is not None:
            (out_dir / "report.txt").write_text(report.to_text(), encoding="utf-8")
        lines = [f"status: {result.status.value}"]
        if getattr(result, "clarification", None):
            lines.append(f"clarification: {result.clarification}")
        if getattr(result, "error", None):
            lines.append(f"error: {result.error}")
        (out_dir / "outcome.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _bbox_from_result(result: Any) -> tuple[float, float, float] | None:
    """The part's rendered bounding box: the report's actual bbox if present, else the
    mesh report's. None when nothing rendered (clarification / render failure)."""
    report = getattr(result, "report", None)
    if report is not None and getattr(report, "actual_bbox_mm", None) is not None:
        return tuple(report.actual_bbox_mm)  # type: ignore[return-value]
    mesh_report = getattr(result, "mesh_report", None)
    if mesh_report is not None and getattr(mesh_report, "bounding_box_mm", None) is not None:
        return tuple(mesh_report.bounding_box_mm)  # type: ignore[return-value]
    return None


def _grade_result(case: BenchCase, result: Any, *, sliced_requested: bool) -> dict[str, Any]:
    """Derive the 3-axis grades + the supporting bbox/object-type facts from a pipeline
    result. Pure extraction over the (duck-typed) result — every lookup is defensive so a
    minimal/Fake result (no plan/gate/report) simply yields None axes rather than raising."""
    plan = getattr(result, "plan", None)
    object_type = getattr(plan, "object_type", None) if plan is not None else None
    target_bbox = getattr(plan, "bounding_box_mm", None) if plan is not None else None

    match = getattr(result, "template", None)
    template_name = None
    if match is not None and getattr(match, "family", None) is not None:
        template_name = getattr(match.family, "name", None)

    gate = getattr(result, "gate", None)
    gate_codes = {f.code for f in gate.findings} if gate is not None else set()
    actual_bbox = _bbox_from_result(result)

    report = getattr(result, "report", None)
    sliced = bool(getattr(report, "sliced", False)) if report is not None else False
    slice_error = getattr(result, "slice_error", None)

    return {
        "object_type": object_type,
        "target_bbox_mm": list(target_bbox) if target_bbox is not None else None,
        "actual_bbox_mm": actual_bbox,
        "matches_request": grade_matches_request(
            object_type, case.expect_object_type, template_name=template_name
        ),
        "correct_dimensions": grade_correct_dimensions(
            gate_codes, actual_bbox, case.max_bbox_mm
        ),
        "slices_clean": grade_slices_clean(sliced, slice_error, attempted=sliced_requested),
    }


def make_case_runner(
    pipeline: Any, out_root: Path, *, slice_for_grade: bool = False
) -> Callable[[BenchCase], CaseOutcome]:
    """Bind a Pipeline into a ``run_one`` that times and grades a single case.

    Each case renders into its own ``out_root/<id>/`` directory. ``pipeline`` is
    duck-typed (anything with ``.run(prompt, out_dir) -> PipelineResult``) so this
    stays importable without forcing a live provider at module load.

    ``slice_for_grade`` asks the pipeline to also slice each part (``confirm_print=True``)
    so the ``slices-clean`` axis can be graded — slower (real OrcaSlicer per case), off by
    default so the completion done-gate and CI stay fast. The matches-request and
    correct-dimensions axes are graded either way (free — no extra render or slice)."""
    import time

    def run_one(case: BenchCase) -> CaseOutcome:
        out_dir = out_root / case.id
        started = time.monotonic()
        # Only pass confirm_print when slicing for the grade, so a duck-typed pipeline
        # whose run() doesn't accept the kwarg (e.g. test fakes) still works by default.
        if slice_for_grade:
            result = pipeline.run(case.prompt, out_dir, confirm_print=True)
        else:
            result = pipeline.run(case.prompt, out_dir)
        duration = time.monotonic() - started
        _persist_case_artifacts(out_dir, result)
        gate_status = str(result.gate.status) if getattr(result, "gate", None) else None
        grades = _grade_result(case, result, sliced_requested=slice_for_grade)
        return CaseOutcome(
            id=case.id,
            status=result.status.value,
            gate_status=gate_status,
            render_attempts=result.render_attempts,
            duration_s=duration,
            error=result.error,
            **grades,
        )

    return run_one
