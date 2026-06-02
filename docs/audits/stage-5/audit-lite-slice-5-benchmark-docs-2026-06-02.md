# Audit Lite — Stage 5 Slice 5: deterministic-template benchmark + Stage 5 docs
**Date:** 2026-06-02
**Scope:** `src/kimcad/template_bench.py` (the deterministic-family benchmark/proof), `tests/test_template_bench.py`, the committed proof `docs/benchmarks/stage-5-template-families.md`, and the Stage 5 doc edits to `ARCHITECTURE.md` / `CHANGELOG.md` / `ROADMAP.md` / `README.md`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one small fix. The benchmark measures the *real* deterministic re-render path (`Pipeline.rerender`, the same one `POST /api/render` runs), enforces "no model" at runtime (a `_NoModelProvider` that raises if touched), and its automated gate is honestly conservative (a 5 s ceiling, with the true sub-second numbers reported + documented). The docs are accurate and — importantly — do *not* repeat the Stage-4 "done" banner mistake: Stage 5 is marked "implemented on the branch, pending the gate." One Minor (a tautological determinism check that gives false confidence) and one Nit (a missing markdown-rendering test).

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 1

## Findings

### BENCH-001 Minor: the per-family "determinism" check is tautological
**Dimension:** Tests / Correctness
**Evidence:** `template_bench.py:189` `deterministic = emit_scad(family, defaults) == emit_scad(family, defaults)`. A pure function compared to itself is always equal, so this can never fail and proves nothing — and it's computed from `defaults` while the row's measured render uses `perturbed`, so it isn't even tied to the geometry the benchmark actually renders. The column "No model"/determinism is meant to be load-bearing evidence in a proof artifact; a check that can't fail is false confidence.
**Why it matters:** The whole point of this file is rigor. A hollow assertion in the proof undermines the claim it's supposedly backing, and would not catch a real regression (e.g. emit later interpolating something order-dependent).
**Fix path:** Tie it to the rendered path: capture the re-render result and assert its emitted SCAD equals a fresh pure emit of the perturbed (clamped) values — `deterministic = (result.scad == emit_scad(family, clamp_values(family, perturbed)))`. That proves the pipeline rendered *exactly* the deterministic template emit (no model contamination) and connects the check to the geometry measured. Add an offline test that a divergence flips `deterministic_emit`/`ok` to False.

### BENCH-002 Nit: no test covers the "Under 1s" markdown cell for an over-target family
**Dimension:** Tests
**Evidence:** `test_template_bench.py` `test_report_markdown_*` only exercise families with `rerender_s` of 0.3/0.4 (both render "yes"). `FamilyBench.meets_target`'s logic is unit-tested (`test_family_ok_and_target_logic`, the 1.5 s case), but the *markdown rendering* of a "no" cell isn't asserted.
**Why it matters:** Very low — the boolean logic is covered; only the table cell isn't. Cheap to close.
**Fix path:** Add a family with `rerender_s` above `RERENDER_TARGET_S` (but under the ceiling) to a `to_markdown` test and assert the row shows `no` in the Under-1s column.

## What's working
- **It measures the real path, and "no model" is enforced, not assumed.** `benchmark_families` builds a `Pipeline` with `_NoModelProvider` (raises on `generate_design_plan`/`generate_openscad`) and times `Pipeline.rerender` — which I traced end-to-end: `match_family → _build_from_template → renderer → _assemble_result`, none of which touch `self.provider`. So the happy path genuinely never calls the model, and a violation would surface as a per-family `error` → `ok=False` (rendered as an `ERROR:` cell). The `test_no_model_provider_raises` test pins the guard.
- **The performance claim is honest.** The hard automated gate is `RERENDER_CEILING_S = 5.0` (so the suite can't flake on a loaded box), while the `<1 s` interactive target is *reported* per family (`meets_target`) and *documented* with the environment in `docs/benchmarks/stage-5-template-families.md` (measured 0.13–0.44 s, 8–38× margin under the ceiling, 0.0000 mm envelope error). I agree with this split: hard-asserting `<1 s` in CI would buy false failures under load with no correctness gain, and the committed measurement + the "Under 1s" column already prove the headline. Not misleading.
- **Console safety holds where it counts.** `to_markdown` is ASCII-only and I verified its output `.encode("cp1252")` succeeds — the exact trap `kimcad.benchmark` hit. (The em-dashes that remain in `template_bench.py` are in docstrings/comments only, never printed, and match the rest of the codebase's style — so not flagged.)
- **The envelope + watertight proof is real** and now spans all seven families through the actual pipeline, complementing the pre-existing `test_family_renders_watertight_with_its_declared_bbox` (which renders at defaults) with a *re-render at changed values* — closer to the live-slider reality.
- **Docs are accurate and consistent.** Cross-checked against the code: the seven families, emit-by-substitution, the `/api/render` versioned `mesh_url` + slice invalidation, and the tiered fallback all match. Crucially, `ROADMAP.md` marks Stage 5 "**implemented on `stage-5-template-engine` … pending the stage gate**" — not done/merged/tagged — so the Stage-4 self-contradiction isn't repeated. `CHANGELOG` puts Stage 5 under `[Unreleased]` (untagged), and `ARCHITECTURE`/`README` describe the engine + sliders correctly.

## Watch items
- The benchmark counts a `gate_failed` re-render as "rendered" (a built, watertight mesh at the right envelope is a successful render regardless of the gate verdict). `_perturb` is gentle enough that no family trips the gate today, so it's moot — but if a family's perturbation ever exceeded the build volume, the row would still pass on geometry while `gate_status` recorded `fail`. That's intended, just worth remembering when reading the proof.
- The committed proof carries machine-specific timings (AMD64 / Win11 / Py3.14). That's correct for a benchmark artifact (environment is recorded), but the numbers will differ on Kim's box — re-run `python -m kimcad.template_bench --write …` on the target when it matters.

## Escalation recommendation
No escalation needed. Small, well-scoped proof + docs slice; one Minor and one Nit, both one-spot fixes. The stage-end `audit-team` will cover the whole Stage 5 branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **BENCH-001 (Minor) — FIXED.** `_bench_one` now computes `deterministic = result.scad == emit_scad(family, clamp_values(family, perturbed))` — the SCAD the pipeline *actually rendered* must equal a fresh pure emit of the (clamped) perturbed values. This both makes the determinism check able to fail (it's tied to the rendered geometry) and adds positive "no-model" evidence (a model-written or order-drifted emit would diverge). The live gate already asserts `f.deterministic_emit` per family, so the strengthened check is exercised; a new offline assertion (`_fb("a", deterministic_emit=False).ok is False`) pins the logic. Verified live: all 7 families still report deterministic + PASS (the rendered SCAD matches the pure emit exactly).
- **BENCH-002 (Nit) — FIXED.** New `test_markdown_marks_an_over_target_family_as_not_under_1s` builds a report with a 0.3 s and a 2.0 s family and asserts the "Under 1s" column renders `yes`/`no` respectively (and that `report.ok` holds while `all_meet_target` is False).

Verified after the fixes: `test_template_bench.py` **14 passed** (was 13); ruff clean; `python -m kimcad.template_bench` re-run PASS (all 7 families deterministic, watertight, 0.0000 mm, under 1 s) and the committed proof doc regenerated. **Roll-up: 0/0/0/0/0.**
