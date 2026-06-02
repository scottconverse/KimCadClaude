"""Stage 6 — the model bake-off (the Qwen-vs-gemma comparison harness).

Runs the Phase-1 benchmark (``kimcad.benchmark``) once per LLM backend and compares the
results on the spec's 3-axis grade (matches-request / correct-dimensions / slices-clean)
plus completion and speed, then recommends whether to switch the default model.

The comparison (:func:`compare_runs`) is pure and unit-tested with synthetic summaries.
The runner (:func:`run_bakeoff`) is thin: it builds a pipeline per backend (injected, so
tests don't need a live model) and delegates to the benchmark harness. The LIVE run needs
a box with Ollama up and both models pulled — that's the hand-off step; this module is the
machinery. Flipping the configured default model on the result is intentionally NOT done
here: that's a human call (like a merge/tag), so the harness only recommends.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kimcad.benchmark import BenchCase, BenchSummary, make_case_runner, run_benchmark

# Two graded rates within this fraction are treated as a tie on quality, so a trivial
# 1-case difference doesn't flip the default on noise; the tiebreak is then speed.
_GRADED_TIE_EPS = 1e-9


@dataclass
class ModelRun:
    """One backend's benchmark result in the bake-off."""

    backend: str  # the config backend key (e.g. "local", "local_qwen")
    model_name: str  # the model tag that backend runs (e.g. "gemma4:e4b")
    summary: BenchSummary


@dataclass
class BakeoffDecision:
    best: str  # backend key with the best quality (graded rate, then completion, then speed)
    incumbent: str | None  # the current default backend key, if it was in the bake-off
    switch: bool  # whether the bake-off recommends switching the default to `best`
    reason: str


def _rank_key(run: ModelRun) -> tuple[float, float, float]:
    """Sort key (higher is better): 3-axis graded rate, then completion rate, then speed
    (negated mean duration so faster ranks higher)."""
    s = run.summary
    return (s.graded_success_rate, s.success_rate, -s.mean_duration_s)


def compare_runs(runs: list[ModelRun], incumbent: str | None) -> BakeoffDecision:
    """Pick the best backend and decide whether to switch the default to it.

    Best = highest 3-axis graded rate; ties (within an epsilon) break on completion rate,
    then on speed. The default switches only when the best is NOT the incumbent AND it
    genuinely beats it: a strictly higher graded rate, or an equal graded rate but faster.
    Otherwise the recommendation is to keep the incumbent (a challenger must earn the swap).
    """
    if not runs:
        raise ValueError("bake-off needs at least one model run")

    best = max(runs, key=_rank_key)

    if incumbent is None or incumbent == best.backend:
        return BakeoffDecision(
            best=best.backend,
            incumbent=incumbent,
            switch=False,
            reason=(
                f"{best.backend} ({best.model_name}) scored highest"
                if incumbent is None
                else f"the current default {best.backend} ({best.model_name}) is already the best"
            ),
        )

    inc = next((r for r in runs if r.backend == incumbent), None)
    if inc is None:
        # The incumbent wasn't part of this bake-off — report the winner, don't auto-switch.
        return BakeoffDecision(
            best=best.backend,
            incumbent=incumbent,
            switch=False,
            reason=(
                f"{best.backend} ({best.model_name}) scored highest, but the current default "
                f"'{incumbent}' was not in this bake-off, so there's nothing to compare it "
                "against -- run the bake-off with the current default included before switching"
            ),
        )

    b, i = best.summary, inc.summary
    graded_gain = b.graded_success_rate - i.graded_success_rate
    faster = b.mean_duration_s < i.mean_duration_s

    if graded_gain > _GRADED_TIE_EPS:
        return BakeoffDecision(
            best=best.backend,
            incumbent=incumbent,
            switch=True,
            reason=(
                f"{best.backend} ({best.model_name}) beats {incumbent} ({inc.model_name}) on "
                f"the 3-axis graded rate ({b.graded_passed}/{b.total} vs "
                f"{i.graded_passed}/{i.total})"
                + (f" and is faster ({b.mean_duration_s:.0f}s vs {i.mean_duration_s:.0f}s "
                   "mean/prompt)" if faster else "")
            ),
        )
    if abs(graded_gain) <= _GRADED_TIE_EPS and faster:
        return BakeoffDecision(
            best=best.backend,
            incumbent=incumbent,
            switch=True,
            reason=(
                f"{best.backend} ({best.model_name}) matches {incumbent} ({inc.model_name}) on "
                f"the 3-axis graded rate ({b.graded_passed}/{b.total} each) but is faster "
                f"({b.mean_duration_s:.0f}s vs {i.mean_duration_s:.0f}s mean/prompt)"
            ),
        )
    return BakeoffDecision(
        best=best.backend,
        incumbent=incumbent,
        switch=False,
        reason=(
            f"the challenger did not clear the bar -- {incumbent} ({inc.model_name}) is as good "
            f"or better on the 3-axis graded rate ({i.graded_passed}/{i.total} vs "
            f"{b.graded_passed}/{b.total}); keep the current default"
        ),
    )


@dataclass
class Bakeoff:
    runs: list[ModelRun]
    incumbent: str | None = None

    def recommendation(self) -> BakeoffDecision:
        return compare_runs(self.runs, self.incumbent)

    def to_text(self) -> str:
        """A side-by-side ASCII table (cp1252-safe) + the recommendation line."""
        n_cases = self.runs[0].summary.total if self.runs else 0
        lines = [f"Bake-off: {len(self.runs)} model(s), {n_cases} case(s) each"]
        # Backend column width: fit the widest tag (a key + " (default)") so the data columns
        # always line up under the header, whatever the configured default backend is named.
        tags = [
            f"{r.backend}{' (default)' if r.backend == self.incumbent else ''}" for r in self.runs
        ]
        bw = max(14, *(len(t) for t in tags)) if tags else 14
        header = (
            f"  {'backend':<{bw}} {'model':<22} {'completed':>9} {'graded':>7} "
            f"{'match':>6} {'dims':>6} {'slice':>6} {'mean_s':>8}"
        )
        lines.append(header)
        zero_completion: list[str] = []
        for r, tag in zip(self.runs, tags):
            s = r.summary
            mr_p, mr_n = s.axis_tally("matches_request")
            cd_p, cd_n = s.axis_tally("correct_dimensions")
            sc_p, sc_n = s.axis_tally("slices_clean")
            # Format each cell as a whole token first, then pad it to the header's width +
            # alignment, so the data columns line up under their headers.
            completed = f"{s.passed}/{s.total}"
            graded = f"{s.graded_passed}/{s.total}"
            # An axis with nothing assessed reads "n/a", not a misleading "0/0" (which scans
            # as a 0 score). mean_s is "n/a" for a model that completed nothing -- it never
            # timed any real work, so a "0.0" would falsely read as "instant/fast".
            match = f"{mr_p}/{mr_n}" if mr_n else "n/a"
            dims = f"{cd_p}/{cd_n}" if cd_n else "n/a"
            slc = f"{sc_p}/{sc_n}" if sc_n else "n/a"
            mean_s = f"{s.mean_duration_s:.1f}" if s.passed else "n/a"
            lines.append(
                f"  {tag:<{bw}} {r.model_name:<22} {completed:>9} {graded:>7} "
                f"{match:>6} {dims:>6} {slc:>6} {mean_s:>8}"
            )
            if s.passed == 0:
                zero_completion.append(
                    f"  note: {r.backend} completed 0/{s.total} cases -- no axes could be graded"
                )
        lines.extend(zero_completion)
        rec = self.recommendation()
        verb = f"SWITCH default to {rec.best}" if rec.switch else f"KEEP default {rec.incumbent or rec.best}"
        lines.append(f"Recommendation: {verb} -- {rec.reason}.")
        lines.append("(Flipping the configured default model is Scott's call, not the harness's.)")
        return "\n".join(lines)


def run_bakeoff(
    backends: list[str],
    make_pipeline: Callable[[str], Any],
    model_name_for: Callable[[str], str],
    cases: list[BenchCase],
    out_root: Path,
    *,
    slice_for_grade: bool = True,
    incumbent: str | None = None,
) -> Bakeoff:
    """Run the benchmark once per backend and collect a :class:`Bakeoff`.

    ``make_pipeline(backend_key)`` builds the pipeline for a backend (injected so tests
    don't need a live model); ``model_name_for(backend_key)`` resolves the display model
    tag. Each backend renders into ``out_root/<backend>/<case-id>/``. ``slice_for_grade``
    defaults True here (a bake-off wants the slices-clean axis), unlike the plain benchmark.
    """
    runs: list[ModelRun] = []
    for backend in backends:
        pipeline = make_pipeline(backend)
        runner = make_case_runner(
            pipeline, out_root / backend, slice_for_grade=slice_for_grade
        )
        summary = run_benchmark(cases, runner)
        runs.append(ModelRun(backend=backend, model_name=model_name_for(backend), summary=summary))
    return Bakeoff(runs=runs, incumbent=incumbent)
