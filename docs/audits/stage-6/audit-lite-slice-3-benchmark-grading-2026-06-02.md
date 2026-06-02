# Audit Lite — Stage 6 Slice 3: expanded 3-axis benchmark grading
**Date:** 2026-06-02
**Scope:** `src/kimcad/benchmark.py` (the tri-state axis fields on `CaseOutcome`, `graded_passed`, the three pure grade functions, `BenchSummary` tallies + `to_text`, `_grade_result`/`_bbox_from_result`/`make_case_runner`), the `kimcad bench --slice` flag in `src/kimcad/cli.py`, the `bench/prompts.yaml` header comment, and the +30 tests in `tests/test_benchmark.py`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one honesty fix. The 3-axis grading is well-built: it's pure and decoupled from execution, backward-compatible (the completion done-gate is untouched), and the tri-state (True/False/None) is honest about what was measured — a None axis never blocks and is excluded from the per-axis denominator. One real over-claim: `grade_correct_dimensions` reports `True` for a part that's grossly *undersized* but happens to fit under the prompt's `max_bbox_mm` ceiling — fitting an upper bound is necessary, not sufficient, evidence of correct size. Confirmed live: a 5×5×1 part against a requested 50×50×10 grades `correct-dimensions = pass`. Cheap fix; one Minor + two Nits.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 2

## Findings

### BENCH-001 Minor: `grade_correct_dimensions` over-claims `True` from a ceiling-only fit (an undersized part passes)
**Dimension:** Correctness / Honesty
**Evidence:** `benchmark.py:142-148`. When the gate produced no `dim.match`/`dim.mismatch` code (verdict starts `None`), the ceiling loop runs and — if every axis fits under `max_bbox_mm` — sets `verdict = True` (line 147). But `max_bbox_mm` is an *upper bound* (the build-volume / requested envelope ceiling), so "fits under it" only rules out *too big*; it says nothing about *too small*. Confirmed live: `grade_correct_dimensions(set(), (5, 5, 1), [50, 50, 10])` returns **`True`** — a part a tenth the requested size on every axis is graded dimensionally correct. The existing test `test_grade_correct_dimensions_within_ceiling_passes` (`tests/test_benchmark.py`) actually pins this optimistic behavior.
**Why it matters:** `correct-dimensions` is one of the three axes the Slice-4 model bake-off uses to choose the default model. An optimistic axis inflates a model's quality score in exactly the direction that matters for the decision. The trigger frequency is low in the current 10-case gate (template parts and LLM parts both normally carry a dimensional target, yielding `dim.match`/`dim.mismatch`), so this bites only the no-target path — but when it bites, it silently scores a wrong-size part as correct.
**Fix path:** Make the ceiling an upper-bound *failure* check only — it can turn a verdict to `False` (too big) but must never assert `True` on its own. Delete the `verdict = True` after the loop so the no-gate-target + fits-ceiling case stays `None` (honest: "not too big, but the size was never confirmed"). Then update `test_grade_correct_dimensions_within_ceiling_passes` to expect `None`, and add a regression case asserting the undersized-fits-ceiling part is `None` (or `False`), not `True`. (Keep the `dim.match` + within-ceiling → `True` path and the too-big → `False` path; both are already covered.)

## What's working
- **Tri-state honesty is genuinely honest.** `None` means "not assessed" and is handled correctly everywhere: `graded_passed` only blocks on an axis that is *assessed and False* (`benchmark.py:71-74`), and `axis_tally` excludes `None` from both numerator and denominator (`benchmark.py:199-204`), so "7/8 matches-request" never silently counts an unmeasured case. This is the crux of the slice and it's right.
- **Backward compatibility is intact.** `passed`, `success_rate`, and `meets` keep their completion semantics (`benchmark.py:54-59, 180-185, 218-219`); the `--min-success-rate` done-gate still gates on completion. `make_case_runner`'s new `slice_for_grade` is keyword-only with a default, so `make_case_runner(pipeline, out_dir)` callers are unaffected. The existing tests (`test_summary_scoring`, `test_make_case_runner_times_and_maps`, the verdict + cp1252 tests) still pass unchanged — verified in the 41-test run.
- **`slice_for_grade` is correctly conditional.** `confirm_print=True` is only passed when slicing for the grade (`benchmark.py:412-415`), so a duck-typed pipeline whose `run()` lacks the kwarg (the test fakes) still works by default — and a gate-FAILED part returns before the slicer, so `report.sliced=False` → `slices_clean=False` (a correct non-pass), not a misleading `None`. The runner test pins that `confirm_print` is actually requested.
- **`grade_matches_request` token logic is sound and tolerant in the right direction.** Expected (usually one noun) ∩ produced-phrase tokens, both normalized + singularized, with the matched template family name folded into the produced side as a fallback (`benchmark.py:116-119`). Verified across the real expected types (hook/bracket/box/clip/spacer/enclosure/holder/plate/divider) it matches phrasings like "pegboard hook", "l-bracket", "two-part enclosure" and rejects unrelated types — no plausible false-positive given these nouns, and the family-name fallback catches the case where the planner's free-text `object_type` misses but a family matched.
- **`dim.mismatch` is decisive over the ceiling** (`benchmark.py:140-141`, returns `False` before the ceiling check), and the ceiling comparison reuses the gate's own `dim_tolerance` (flat 0.5 mm) so it can't false-fail on fillet/mesh-export float noise. Both verified live.
- **Defensive extraction.** `_grade_result` and `_bbox_from_result` use `getattr(..., default)` for every field, so a minimal/Fake result (no plan/gate/report/template) yields all-`None` axes and never raises — confirmed by the unchanged `test_make_case_runner_times_and_maps` plus the new minimal-result assertions.
- **Console safety.** The new `to_text` rollup + per-case `{req=,dim=,slice=}` marks use only ASCII (`ok`/`XX`/`--`); the new `test_to_text_shows_three_axis_block_and_is_console_safe` encodes to cp1252. (The pre-existing em-dash on the error line, `benchmark.py:253`, predates this slice and is itself cp1252-representable.)

## Watch items
- **`slices-clean` conflates model fault with environment.** A slice refusal (no OrcaSlicer profile for the printer/material) sets `slice_error` → `slices_clean=False`, which would penalize the *model* for an *environment* gap. Harmless for the bake-off because both models run on the same configured printer (P2S has profiles), so it's a constant, not a differentiator — but if the bake-off ever runs on a printer with a missing profile, the axis would read as a model regression. Worth a one-line note when the Slice-4 bake-off runner is written.
- **`import re` / `dim_tolerance` are imported inside their functions** (`benchmark.py:85, 138`). The `dim_tolerance` lazy import is defensible (avoids pulling `printability` at module load); the `re` one is pure stdlib with no cycle risk — see BENCH-002.

## Findings (Nits)

### BENCH-002 Nit: `import re` lives inside `_grade_tokens`
**Dimension:** Correctness (style)
**Evidence:** `benchmark.py:85` imports `re` inside `_grade_tokens`, called once per case. No cycle risk (stdlib); negligible perf on a 10-case batch.
**Fix path:** Move `import re` to the module top. (Leave the `dim_tolerance` local import — that one avoids importing `printability` at module load and is a deliberate guard.)

### BENCH-003 Nit: the `to_text` headline `"X/total passed"` can read as quality, not completion
**Dimension:** UX (operator-facing output)
**Evidence:** `benchmark.py:228` prints `"Benchmark: 10/10 passed (100%)"` (completion) directly above `"Graded (3-axis): 7/10 (70%)"`. A skimmer could read the first line as "100% good." The two lines together are accurate, so this is genuinely minor.
**Fix path:** Optional — relabel the headline to `"Benchmark: 10/10 completed"` (no test asserts the literal word "passed" there) so completion vs. graded quality is unambiguous at a glance. Or leave it; the graded line directly below disambiguates.

## Escalation recommendation
No escalation needed. One Minor honesty fix (delete one line + adjust one test) and two Nits. The grading machinery is sound, pure, well-tested, and backward-compatible; the Stage-6 stage-end `audit-team` will cover the whole branch. Fix BENCH-001 (+ optionally the Nits) and re-audit to 0/0/0/0/0.

---

## Re-audit (resolution) — 0/0/0/0/0

- **BENCH-001 (Minor) — FIXED.** The `verdict = True` after the ceiling loop is removed (`benchmark.py grade_correct_dimensions`); the ceiling now only returns `False` (too big) and can never assert correctness. A no-gate-target part that merely fits the ceiling — including a grossly undersized one — now stays `None` (size unconfirmed), not `True`. Verified live: `grade_correct_dimensions(set(), (5,5,1), [50,50,10])` → **None** (was True); `grade_correct_dimensions({'dim.match'}, (49.8,50,10), [50,50,10])` → **True** (the real-pass path intact). Tests updated: the old `..._within_ceiling_passes` is replaced by `..._ceiling_only_is_unassessed` (asserts None) + a new `..._undersized_fits_ceiling_is_not_a_pass` regression + `..._match_within_ceiling_passes` (pins the dim.match + ceiling → True path). The docstring now states the ceiling is an upper bound, not positive evidence.
- **BENCH-002 (Nit) — FIXED.** `import re` moved to the module top; `_grade_tokens` no longer imports per-call. The `dim_tolerance` local import is kept (deliberate — avoids importing `printability` at module load).
- **BENCH-003 (Nit) — FIXED.** The `to_text` headline now reads `"Benchmark: X/total completed"` (was `"... passed"`), so completion is unambiguous against the `"Graded (3-axis): Y/total"` line directly below. No test asserted the old word; the cp1252 + 3-axis-block tests still pass.

Verified after the fixes: `tests/test_benchmark.py` **38 passed**; ruff clean; the undersized-fits-ceiling part now grades `None`, the dim.match path still grades `True`. **Roll-up: 0/0/0/0/0.**
