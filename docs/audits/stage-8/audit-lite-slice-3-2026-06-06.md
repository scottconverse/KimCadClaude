# Audit Lite — Stage 8 Slice 3 (CadQuery parallel backend + mutual fallback wiring)
**Date:** 2026-06-06
**Scope:** Working-tree changes wiring the CadQuery parallel geometry backend into the pipeline with OpenSCAD↔CadQuery mutual fallback — `src/kimcad/pipeline.py`, `src/kimcad/llm_provider.py`, `src/kimcad/prompts/system_cadquery.md`, `tests/conftest.py`, `tests/test_pipeline_backends.py`. Branch `stage-8-cadquery`, uncommitted.
**Reviewer:** Claude (audit-lite)

## TL;DR
The core wiring is well done: `_run_llm_backend` is a faithful extraction of the prior single-backend loop (no retry-budget or behavior drift), the fallback scoring logic is sound with no downgrade path, basenames don't collide, and the untrusted-Python path is always routed through the sanitizing `render_cadquery`. **Do not ship as-is:** the Protocol gained `generate_cadquery`, but two real provider classes — including the production web wrapper `_SettingsAwareProvider` — never implement it, so the fallback raises `AttributeError` in production exactly when it's supposed to rescue a failed part. One Critical, one Major (a safety property now exercised only with the fallback disabled), plus minors. Fix the provider gap and add a multi-backend slice-refusal test, then it ships.

## Severity rollup
- Blocker: 0
- Critical: 1
- Major: 1
- Minor: 3
- Nit: 1

## Findings

### FINDING-001 Critical: Production providers don't implement `generate_cadquery`; fallback crashes with AttributeError
**Dimension:** Correctness
**Evidence:**
- `src/kimcad/webapp.py:372` `_SettingsAwareProvider` — the wrapper used for every real (non-demo) web design (`webapp.py:356`) — delegates `generate_design_plan` (`:426`), `generate_openscad` (`:429`), `describe_photo` (`:432`) by explicit per-method methods, with **no `generate_cadquery` and no `__getattr__`** fallthrough.
- `src/kimcad/webapp.py:291` `DemoProvider` — same gap; reachable via the `demo:gatefail` / `oversized_block` scenario (`webapp.py:309,328` returns an oversized cube → gate FAILs on build volume).
- `src/kimcad/pipeline.py:857` the fallback calls `self.provider.generate_cadquery` unconditionally once `_cadquery_renderer_or_none()` is non-None.
- Production builders (`webapp.py:360`, `cli.py:178`) inject NO `cadquery_renderer`, so `_cadquery_renderer_or_none()` (`pipeline.py:392`) auto-discovers a real interpreter — on any box with a `≤3.13` cadquery, the fallback fires.
- Concrete repro (run this session): `_SettingsAwareProvider` and `DemoProvider` both report `generate_cadquery=False  __getattr__=False`; `sap.generate_cadquery` → `AttributeError: '_SettingsAwareProvider' object has no attribute 'generate_cadquery'`.
**Why it matters:** The fallback fires precisely when OpenSCAD render-failed or exhausted its gate retries — the user is already on a failing path. Instead of being rescued by CadQuery (the whole point of Slice 3), the web request dies with an unhandled `AttributeError` (raw 500/traceback), a strictly worse outcome than the pre-Slice-3 `render_failed`/`gate_failed` response. The `llm_provider.py:92-94` docstring claims the contract is "total — every provider answers it," which is false. This is invisible in the suite because the autouse hermeticity fixture forces CadQuery OFF for every non-live test (see FINDING-002), and the live test uses `FakeProvider` (which DOES implement it) — so no test drives a real production provider into the fallback.
**Fix path:** Add `generate_cadquery` to `_SettingsAwareProvider` (delegate via `self._active().generate_cadquery(...)`, mirroring `generate_openscad` at `webapp.py:429`) and to `DemoProvider` (return a fixed valid CadQuery script, e.g. `'result = cq.Workplane("XY").box(...)'`, mirroring the `FakeProvider` default). Then add a test that runs a REAL production-style provider (no `generate_cadquery`-bearing fake) through the fallback to prove the contract holds. `_NoModelProvider` (`template_bench.py:53`) also lacks it but is genuinely unreachable (template-only path, never `match is None`) — adding a raising stub there keeps the totality claim honest without behavior change.
**Blast radius:**
- Adjacent code: every class structurally typed as `Provider` — `_SettingsAwareProvider`, `DemoProvider`, `_NoModelProvider`, `FakeProvider` (ok), `LLMProvider`/`FallbackProvider` (ok).
- Shared state: none (stateless delegation).
- User-facing change: after the fix, a gate-failed/render-failed real web design that previously 500'd will instead attempt the CadQuery rescue — the intended Slice-3 behavior.
- Migration concern: none.
- Tests to update: add a multi-backend test using a provider that lacks `generate_cadquery` only if you want a regression guard for the contract; primarily ADD the production-provider-through-fallback test described above.

### FINDING-002 Major: The core slice-refusal safety property is no longer exercised on the multi-backend path
**Dimension:** Tests
**Evidence:**
- `tests/conftest.py:84` autouse `_default_cadquery_backend_off` monkeypatches `Config.cadquery_interpreter` → `None` for every non-`live` test.
- The stage's stated "core safety property" test `test_gate_fail_with_confirm_does_not_slice` (`tests/test_pipeline.py:360`) uses `_pipeline` (`test_pipeline.py:53`), which injects no `cadquery_renderer` — so under the fixture it runs single-backend only.
- `tests/test_pipeline_backends.py:116` `test_both_backends_fail_keeps_the_primary_result` exercises the multi-backend gate-FAIL path but does **not** pass `confirm_print=True`, so it never asserts the slicer is refused on a gate-failed multi-backend result.
**Why it matters:** The fixture is legitimate and necessary for hermeticity (it correctly fixes the 4 tests that the real worker was silently rescuing). But it has a side effect: the safety-critical "a gate-failed part is never sliced" invariant is now verified ONLY with the fallback disabled — i.e. not on the configuration production actually runs (CadQuery discoverable). After both backends gate-FAIL, the result still carries `status=gate_failed` and `proceed_anyway` still gates the slicer, so the property almost certainly holds — but "almost certainly" is not the bar for the stage's load-bearing safety check. The fixture masks the question rather than answering it.
**Fix path:** Add one multi-backend test (inject a fake `cadquery_renderer`, or mark `live`) that drives both backends to gate-FAIL with `confirm_print=True` and asserts the slicer is never called and `report.sliced is False` — the multi-backend twin of `test_gate_fail_with_confirm_does_not_slice`. This closes the masking concern from #4 of the brief.

### FINDING-003 Minor: `llm_provider.py` Protocol/docstring claims a "total" contract that isn't enforced
**Dimension:** Docs
**Evidence:** `src/kimcad/llm_provider.py:92-94` — "Declared on the Protocol so the contract is total — every provider answers it." Three non-`LLMProvider`/`FallbackProvider` implementations (`DemoProvider`, `_SettingsAwareProvider`, `_NoModelProvider`) do not. Protocols are structural and not runtime-checked, so nothing enforces totality.
**Why it matters:** The comment gives false confidence that exactly produced FINDING-001. Doc drift on a safety-relevant contract.
**Fix path:** After fixing FINDING-001 the statement becomes true; otherwise soften the comment. Consider a `pytest` that asserts every concrete `Provider` impl in `src/` defines all Protocol methods (a cheap structural guard against the next provider forgetting one).

### FINDING-004 Minor: `_better_result` collapses PASS and WARN to the same score
**Dimension:** Correctness
**Evidence:** `src/kimcad/pipeline.py:940-944` — `score` returns `2` for any `gate.status is not Level.FAIL` (PASS=0 and WARN=1 both map to 2; FAIL=2→1; no render→0).
**Why it matters:** Not a defect today — the fallback only runs when the primary already failed `_backend_succeeded` (which accepts a primary WARN, so a WARN primary never reaches `_better_result`). So the only `_better_result` cases are primary∈{FAIL, none}. But the collapse means that IF the logic is ever reused where both candidates rendered cleanly, a fallback PASS would not beat a primary WARN. Worth a one-line comment that the PASS/WARN tie is intentional given the current call site, so a future refactor doesn't silently prefer a noisier part.
**Fix path:** Add a comment at `pipeline.py:944` noting PASS and WARN are deliberately equivalent here (WARN = "printable with notes" is acceptable, and a WARN primary never reaches this function anyway), or split the score (PASS=3, WARN=2) defensively — behavior is unchanged either way at the current call site.

### FINDING-005 Minor: Prompt allows `from math import …` but the example uses bare names; sanitizer/worker contract is otherwise aligned
**Dimension:** Correctness
**Evidence:** `prompts/system_cadquery.md:10-12` permits `math` (and shows `from math import pi`); `cadquery_runner.py:52` `_ALLOWED_IMPORT_ROOTS = {"cadquery", "math"}` matches. The prompt forbids imports of `cadquery` itself ("not even `import cadquery`") while the sanitizer *would* allow it — a stricter prompt than the sanitizer, which is safe (model is told to do less than what's permitted). The "no dunder / no string-subscript / no `os`/`sys`/…" rules in the prompt (`:18-19`) line up with `_BANNED_NAMES`/`_BANNED_ATTRS` and the dunder/subscript AST checks.
**Why it matters:** No functional mismatch that would make the model reliably emit rejected code. The only friction: the prompt's worked examples (`:49-74`) never exercise the `math` import, and the L-bracket example uses `.transformed(offset=...)` / `combine=True` chains that are more fragile than the "prefer simple robust chains" guidance two lines above — a model copying the example may produce the disconnected-shell failure the prompt itself warns about (`:22-25`).
**Fix path:** Optional: simplify the L-bracket example to a single `.union()` of two boxes so the example embodies the "one connected solid / simple chains" rule it preaches. No blocker.

### FINDING-006 Nit: `_run_llm_backend` recomputes `rbase` by string-compare on `backend.name`
**Dimension:** Correctness
**Evidence:** `src/kimcad/pipeline.py:878` — `rbase = basename if backend.name == "openscad" else f"{basename}-{backend.name}"`.
**Why it matters:** Works correctly (primary keeps the bare basename so existing OpenSCAD output naming is untouched; CadQuery gets `part-cadquery`, no collision with `part.3mf`/`part.scad`/`part.oriented.stl` — verified). It's a slightly implicit coupling between the special-case string and the `_GeomBackend("openscad", …)` literal at `:848`. A future third backend would Just Work, but a rename of "openscad" would silently change the primary's output path.
**Fix path:** Optional: make "is primary" an explicit field on `_GeomBackend` (e.g. `bare_basename: bool`) rather than inferring from the name string.

## What's working
- **`_run_llm_backend` is a faithful extraction.** Diffed against the prior committed `_build_geometry` loop (`git show HEAD:…`): identical retry budget (`range(1, max_render_retries + 2)`), identical render-fail mapping (`attempt > max_render_retries` → return `None` tuple), identical gate-feedback gate (`attempt <= max_render_retries`), identical 7-tuple shape and `attempts` values, identical `_feed_back` threading. The only changes are parameterizing generate/render/label/fix via `_GeomBackend` and the per-backend `rbase`. No off-by-one, no behavior drift on the proven OpenSCAD path. (`pipeline.py:864-916`)
- **Template path correctly bypasses all of it.** `_build_geometry` returns from `_build_from_template` before constructing any backend (`pipeline.py:840-841`); templates never fall back, exactly as specified.
- **Fallback scoring has no downgrade path.** `_better_result` is monotonic (PASS/WARN=2 > FAIL=1 > none=0) with ties→primary; a primary WARN never reaches it (`_backend_succeeded` accepts WARN), and a primary FAIL/none can only be replaced by a strictly-better fallback. Verified across both-fail / both-pass / primary-fail-secondary-pass / render=None. (`pipeline.py:918-946`)
- **`proceed_anyway` coherence confirmed.** With `gate_retry=False`, `_backend_succeeded` returns True for any rendered primary (`pipeline.py:928-929`), so no fallback fires — the user's "slice THIS failed part for inspection" intent is honored, not silently swapped for a CadQuery part.
- **Security wiring is sound.** The fallback's only execution route is `_default_cadquery_renderer` → `render_cadquery` (`pipeline.py:383`), which sanitizes (`cadquery_runner.py:169-171`) before the worker runs; limits are passed correctly (`timeout_s=config.cadquery_timeout_s()`, `max_output_bytes=config.limit("max_output_bytes")`). No config/injection path bypasses the sanitizer — a config can only point at a different *interpreter*, never skip `render_cadquery`. `emit_step` is left default-False (no STEP this slice, per scope).
- **No basename clobbering.** OpenSCAD writes `part.{scad,3mf|stl}`; CadQuery writes `part-cadquery.{cq.py,stl,cq-result.json}`; `_assemble_result` exports the winner's mesh once to `part.oriented.stl`. Distinct namespaces in one `out_dir`. (`pipeline.py:878`, `openscad_runner.py:286-297`, `cadquery_runner.py:175-179`)
- **`_assemble_result` is backend-correct.** It operates on the in-memory `mesh` (the winner's validated trimesh) and threads `render.backend` into both `PrintReport.backend` and `PipelineResult.backend` (`pipeline.py:600,633,1015`); the report describes whichever backend actually won.
- **Hermeticity fixture is the right call** for determinism (correctly fixes the 4 tests the real worker was rescuing) — see FINDING-002 for its one side effect.
- **`FallbackProvider.generate_cadquery`** delegates through the same sticky primary→alt `_call` as the other methods (`llm_provider.py:418-425`); stickiness/correctness are consistent with the existing pattern.
- Targeted suite green: `pytest tests/test_pipeline_backends.py -m "not live"` → 5 passed; `tests/test_pipeline.py -m "not live"` → 28 passed (under the hermeticity fixture).

## Watch items
- The live test (`test_pipeline_backends.py:131`) proves the real worker rescues a part, but uses `FakeProvider` — it does NOT exercise a production provider through the fallback (the FINDING-001 blind spot). When you add the production-provider test, consider a `live` variant so the real worker + real provider shape are covered together.
- `FallbackProvider.__init__` mutates `primary.max_attempts = 1` in place (`llm_provider.py:368`); if a future Slice constructs CadQuery codegen against a shared primary, re-check that note. Out of scope here, no action.

## Escalation recommendation
**No escalation needed.** This is a scoped slice and a single-pass lite audit is the right tool. One Critical with a concrete, local fix (add two delegating methods) plus one Major test gap — both fixable this sitting; the situation has not outgrown audit-lite. Re-run the targeted backend tests after the provider fix and add the multi-backend slice-refusal test, then it ships.

---

## Remediation (maintainer, 2026-06-06) — converging to 0/0/0/0/0

- **FINDING-001 (Critical) — FIXED.** `generate_cadquery` added to `_SettingsAwareProvider`
  and `DemoProvider` (webapp.py), and to `_NoModelProvider` (template_bench.py, raises like its
  siblings). `_SettingsAwareProvider` delegates through the same active local/cloud provider as
  the OpenSCAD codegen; `DemoProvider` mirrors the oversized-part logic so the demo:gatefail
  scenario still gate-fails on both backends. The fallback no longer AttributeErrors in
  production.
- **FINDING-002 (Major) — FIXED.** New `test_gate_failed_part_is_not_sliced_on_the_multi_backend_path`
  drives BOTH backends to gate-FAIL with `confirm_print=True` and asserts the slicer is never
  invoked — the safety property now covered on the multi-backend path the production config uses.
- **FINDING-003 (Minor) — FIXED.** New `test_all_real_providers_implement_the_full_contract`
  asserts every provider wired as a real Provider answers the whole Protocol — it would have
  caught FINDING-001.
- **FINDING-004 (Minor) — FIXED.** `_better_result` scoring now carries a comment explaining the
  PASS/WARN collapse and why a WARN primary never reaches it.
- **FINDING-005 (Minor) — FIXED.** The L-bracket prompt example is now a robust `.union()` of two
  boxes (verified to build on 3.13), avoiding the fragile `.transformed()`/`combine=True` chain.
- **FINDING-006 (Nit) — FIXED.** `_GeomBackend` gained an explicit `primary` field; the basename
  decision uses it instead of the `name == "openscad"` string coupling.

Re-verified: ruff clean (src + tests); `tests/test_pipeline_backends.py` 8 passed (incl. the live
real-worker fallback, the multi-backend slice-refusal, and the contract-completeness test).
