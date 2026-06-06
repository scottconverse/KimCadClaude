# Audit Lite (RE-AUDIT) — Stage 8 Slice 3 (CadQuery parallel backend + mutual fallback)
**Date:** 2026-06-06
**Scope:** Independent verification that the 6 findings from `audit-lite-slice-3-2026-06-06.md` (1 Critical, 1 Major, 3 Minor, 1 Nit) are genuinely closed and that the fixes introduced nothing new. Working-tree changes on branch `stage-8-cadquery` (uncommitted): `src/kimcad/pipeline.py`, `src/kimcad/llm_provider.py`, `src/kimcad/template_bench.py`, `src/kimcad/webapp.py`, `tests/conftest.py`, plus new `src/kimcad/prompts/system_cadquery.md` and `tests/test_pipeline_backends.py`.
**Reviewer:** Claude (audit-lite), independent re-audit

## TL;DR
All six prior findings are CLOSED, each verified against its root cause rather than the maintainer's say-so. The two safety-relevant fixes (the production-provider gap and the multi-backend slice-refusal test) were mutation-tested: I defeated the underlying invariant in a scratch copy and confirmed the new tests fail, then restored. The CadQuery prompt example was run on the real 3.13 interpreter and produces the claimed 40×20×40 single connected solid. Ruff clean; targeted non-live suite (`test_pipeline_backends.py` + `test_webapp.py`) 116 passed / 2 deselected. No new findings. **Ship.**

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Per-finding verdicts

### FINDING-001 (Critical) — CLOSED
Production providers now implement `generate_cadquery`.
- `_SettingsAwareProvider.generate_cadquery` (webapp.py:440-444) routes through `self._active().generate_cadquery(...)` — the same local/cloud selection (`_active()`, webapp.py:407-432) as `generate_openscad` (webapp.py:437-438). Correct: cloud opt-in / local-default / degrade-to-local all carry over unchanged.
- `DemoProvider.generate_cadquery` (webapp.py:334-340) mirrors the OpenSCAD oversized-block logic: `object_type == "oversized_block"` → `box(300,300,300)` (gate-fails on build volume), else `box(80,60,40)`. So `demo:gatefail` still gate-FAILs on the CadQuery branch — the demo keeps demoing a gate failure rather than being silently rescued by the fallback.
- `_NoModelProvider.generate_cadquery` (template_bench.py:63-64) raises `AssertionError`, matching its `generate_openscad` sibling; keeps the "total contract" claim honest without behavior change on the template-only path (it's never the `match is None` LLM path).
- **No other concrete provider is missing it.** Every `src/` class defining `generate_design_plan` — `LLMProvider`, `FallbackProvider` (llm_provider.py), `DemoProvider`, `_SettingsAwareProvider` (webapp.py), `_NoModelProvider` (template_bench.py) — now defines `generate_cadquery` (verified by grepping both method names across `src/`). The Protocol itself (llm_provider.py:95) and `FallbackProvider` (llm_provider.py:418, delegates via `_call`) are correct.
- Test-side providers lacking the method (test_cli.py:156, test_pipeline.py:70, several in test_webapp.py) are NOT at risk: they either fail before codegen (plan_failed) or run under the autouse `_default_cadquery_backend_off` fixture with no injected `cadquery_renderer`, so the fallback is skipped. Only `test_pipeline_backends.py` injects a renderer / marks `live`, and it uses `FakeProvider`, which implements the method.

### FINDING-002 (Major) — CLOSED
`test_gate_failed_part_is_not_sliced_on_the_multi_backend_path` (test_pipeline_backends.py:129-145) injects a real `cadquery_renderer`, drives BOTH backends to gate-FAIL (40³ and 50³ vs a 20³ plan), passes `confirm_print=True`, and asserts via a raise-on-call slicer that slicing never happens.
- **Mutation-tested:** I changed the slice-gate guard `if gate.status is Level.FAIL and not proceed_anyway:` (pipeline.py:587) to `if False and …` in a scratch copy. The test then FAILED at pipeline.py:608 with `AssertionError: a gate-failed part must never be sliced` — proving the test genuinely exercises and guards the property, not a tautology. Restored to byte-identical.
- This covers the configuration production actually runs (CadQuery discoverable), which the single-backend `test_gate_fail_with_confirm_does_not_slice` could not, because the hermeticity fixture forces CadQuery off.

### FINDING-003 (Minor) — CLOSED
`test_all_real_providers_implement_the_full_contract` (test_pipeline_backends.py:148-160) asserts `LLMProvider, FallbackProvider, DemoProvider, _SettingsAwareProvider, FakeProvider` each define the full 4-method contract; correctly excludes the partial `_NoModelProvider`.
- **Mutation-tested:** removing `_SettingsAwareProvider.generate_cadquery` in a scratch copy made the test FAIL with `_SettingsAwareProvider is missing generate_cadquery` — i.e. it would have caught FINDING-001. Restored.

### FINDING-004 (Minor) — CLOSED
The comment at pipeline.py:946-948 explains the PASS/WARN collapse and states a WARN primary never reaches `_better_result`.
- **Accuracy verified:** `_backend_succeeded` (pipeline.py:932) returns True for any non-FAIL gate (PASS or WARN), so the primary short-circuits at pipeline.py:853 and the fallback never runs for a WARN primary. Therefore the only inputs `_better_result` ever sees are a primary that FAILED or didn't render — exactly what the comment says. The score (render=None→0, FAIL→1, non-FAIL→2) is monotonic and ties favour the primary (`>=`), so no downgrade path. Comment is correct.

### FINDING-005 (Minor) — CLOSED
The L-bracket example in system_cadquery.md:62-72 is now a `.union()` of two boxes.
- **Run on the real interpreter** (`Python313\python.exe`, cadquery 2.7.0 — the one `find_cadquery_interpreter()` discovers on this box): the example builds, bbox = **40.000 × 20.000 × 40.000** (matches the maintainer's claim), and `solid count: 1` — a single connected, watertight solid, embodying the "one connected solid / simple chains" rule the prompt preaches. The cube+through-hole example also builds (20×20×20). No fragile `.transformed()`/`combine=True` chain remains.

### FINDING-006 (Nit) — CLOSED
`_GeomBackend` gained an explicit `primary: bool = True` field (pipeline.py:98); the basename decision is now `rbase = basename if backend.primary else f"{basename}-{backend.name}"` (pipeline.py:880), no longer coupled to the `name == "openscad"` string.
- No collision/regression: primary keeps the bare `part` basename (OpenSCAD output naming untouched); the fallback writes `part-cadquery.*`. The two `_GeomBackend(...)` constructions set `primary=True`/`primary=False` explicitly (pipeline.py:848-851, 858-861). A rename of "openscad" no longer silently moves the primary's output path.

## What's working (independently re-confirmed)
- **`_run_llm_backend` is a faithful extraction.** Diffed against `git show HEAD:src/kimcad/pipeline.py`: identical retry budget (`range(1, max_render_retries + 2)`), identical render-fail mapping (`attempt > max_render_retries` → `None`-tuple), identical gate-feedback gate (`attempt <= max_render_retries`), identical 7-tuple shape. Only deltas are `_GeomBackend` parameterization and per-backend `rbase`. No off-by-one or behavior drift on the proven OpenSCAD path.
- **Security wiring intact.** The fallback's only execution route is `_default_cadquery_renderer` → `render_cadquery` (pipeline.py:380-390), which sanitizes before the out-of-process worker runs; config can only point at a different *interpreter*, never skip the sanitizer. Limits passed correctly.
- **Hermeticity fixture is correct.** `_default_cadquery_backend_off` (conftest.py:84-99) forces CadQuery off for non-live tests, with documented opt-ins (inject `cadquery_renderer`, or mark `live`). This is why the per-finding mutation tests behaved deterministically.
- **Targeted suite green:** `test_pipeline_backends.py` + `test_webapp.py`, `-m "not live"` → 116 passed, 2 deselected (51s). Ruff clean on `src` + `tests`. Working tree byte-identical after all scratch mutations (diffstat unchanged: 5 files, +243/-21).

## Watch items (not findings)
- `test_all_real_providers_implement_the_full_contract` hardcodes its class list rather than discovering every `Provider` impl in `src/`. It covers all current real providers, but a future 5th provider class wouldn't be auto-included. Cheap future hardening: enumerate provider classes via the module rather than a literal tuple. Not a defect today.
- The live test (`test_live_cadquery_fallback_builds_a_real_part`) still uses `FakeProvider`, not a production provider, so the real-worker + production-provider shapes aren't covered together in one live run. The new contract test plus the AttributeError-root-cause fix close the practical risk; a live production-provider variant remains a nice-to-have.

## Escalation recommendation
**No escalation needed.** Every finding is closed with evidence (two mutation-tested, one run on the real interpreter), nothing new introduced, suite green, lint clean. Rollup 0/0/0/0/0. **Ship.**
