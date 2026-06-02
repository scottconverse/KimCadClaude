# Audit Lite — Stage 6 Slice 5: plan-failure robustness
**Date:** 2026-06-02
**Scope:** The `plan_failed` path — `src/kimcad/pipeline.py` (new status + `PLAN_FAILED_MESSAGE` + `_PLAN_PARSE_ERRORS` + the wrapped `generate_design_plan` call), `src/kimcad/cli.py` `_cmd_design` handler, `frontend/src/designStatus.ts` (+ rebuilt SPA assets), and the tests in `tests/test_pipeline.py` + `frontend/src/designStatus.test.ts`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one real fix. The core change is correct and well-built: a model that returns un-parseable output now fails with a clean, actionable message instead of a raw pydantic traceback, and the load-bearing safety property holds — genuine connection/timeout/model-not-found errors are NOT masked as `plan_failed` (verified: none of openai's network exceptions subclass the caught set). But I introduced an **exit-code collision**: `plan_failed` returns `5`, which the documented CLI contract already assigns to `gate_failed`. That's a Major. One Minor: the catch set is broad enough to mask a non-model bug as `plan_failed`.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 1
- Nit: 0

## Findings

### PLAN-001 Major: `plan_failed` exit code collides with `gate_failed` (both return 5)
**Dimension:** Correctness
**Evidence:** `cli.py:261` returns `5` for `plan_failed`; `cli.py:269` returns `5` for `gate_failed`. The CLI exit-code contract is explicit (`tests/test_cli.py:80-81`): "completed -> 0, clarification_needed -> 3, render_failed -> 4, gate_failed -> 5", and `test_design_gate_failed_exit_5_prints_report` pins `gate_failed == 5`. So two distinct outcomes now share exit code 5 — a script that branches on the exit code can't tell a plan failure (the model produced junk) from a gate failure (a real part that failed printability). No existing test caught it because there's no `plan_failed` exit-code test yet.
**Why it matters:** The exit-code contract exists precisely so automation can distinguish outcomes; collapsing two onto 5 silently breaks that. A CI/script treating "5 = gate failed, slice with --proceed-anyway" would now mis-handle a plan failure (where there's nothing to proceed with).
**Fix path:** Give `plan_failed` the next free code — `6` (used: 0 completed, 2 validation/argparse, 3 clarification, 4 render_failed, 5 gate_failed). Update the contract comment at `test_cli.py:80-81` to include `plan_failed -> 6`, and add `test_design_plan_failed_exit_6` mirroring the other exit-code tests (monkeypatch a provider that raises a parse error, assert exit 6 + the clean message printed).
**Blast radius:**
- **Adjacent code:** any CI/script consuming `kimcad design` exit codes; the `test_cli.py` exit-code contract block.
- **User-facing change:** a plan failure returns a distinct code (6) instead of colliding with 5.
- **Migration concern:** none — `plan_failed` is new this slice, so no external consumer depends on the (briefly) colliding value.
- **Tests to update:** `test_cli.py` contract comment + one new exit-code test.

### PLAN-002 Minor: the catch set is broad enough to mask a non-model bug as `plan_failed`
**Dimension:** Correctness
**Evidence:** `pipeline.py:302` wraps the whole `generate_design_plan` call in `except _PLAN_PARSE_ERRORS` where `_PLAN_PARSE_ERRORS = (ValueError, TypeError, KeyError, AttributeError, ValidationError)` (`pipeline.py:133`). The intent is to catch parse failures of untrusted model output (good), but `generate_design_plan` also assembles the system prompt and constraints before the model call; a future bug there that raises one of those builtin types would be silently reported as "the model returned a bad plan" rather than surfacing the real defect. Practical risk is low today — the prompt-assembly code is simple/stable, file errors are `OSError` and network errors are openai types (neither caught) — but the net is wider than the thing it's protecting.
**Why it matters:** A broad builtin catch around a multi-step call can hide a genuine bug behind a user-facing "try a different model" message, which is the hardest kind of bug to find (it looks like a model problem). With independent auditors reviewing the code, a tightly-scoped catch reads better and is safer.
**Fix path:** Raise the failure at the exact parse boundary instead of catching broadly downstream: in `llm_provider.generate_design_plan`, wrap only `parse_design_plan(normalize_plan_dict(json.loads(_strip_fences(raw))))` and re-raise as a dedicated `PlanParseError`; have `pipeline.run` catch only `PlanParseError`. Then a bug in prompt assembly (or anywhere else) propagates as itself, and only true parse failures become `plan_failed`. Update the three new pipeline tests to drive `PlanParseError` (or keep one that asserts a raw `ValidationError` from a provider still surfaces as a bug, per the chosen contract).

## What's working
- **The load-bearing safety property holds.** Verified live: `APIConnectionError`, `APITimeoutError`, and `NotFoundError` all return `False` for `issubclass(exc, (ValueError, TypeError, KeyError, AttributeError, ValidationError))` — they derive from `OpenAIError`/`APIError`, so a genuine connection/timeout/model-not-found error propagates (to the `FallbackProvider` or the CLI's `RuntimeError` handler) and is never masked as `plan_failed`. `JSONDecodeError` *is* a `ValueError` subclass, so bad JSON is correctly caught. A dedicated pipeline test (`test_connection_error_is_not_swallowed_as_plan_failed`) pins this.
- **The catch is scoped to only the design-plan call**, not the rest of `run()` — the render/gate/slice stages keep their own error handling untouched, so the blast radius of the wrap is contained to the one call.
- **No traceback leak.** Verified live: `kimcad design "..." --backend local_qwen` (qwen echoes the schema back) now exits cleanly with the actionable message — no raw pydantic dump. Pre-slice this exact invocation produced a multi-frame traceback.
- **UX split is sensible.** The web message (`designStatus.ts` `plan_failed` case) is clean and deliberately does NOT echo `result.error` (which carries the technical `(details: <Type>)`); the CLI shows the message plus a short type hint. Web stays friendly, CLI stays debuggable. The frontend test asserts the message is shown AND that `ValidationError` does not leak into it.
- **The detail was trimmed.** `error` carries only `(details: <ExceptionTypeName>)`, not the full multi-line pydantic dump — a good catch during dev (the first cut leaked the whole validation error to the CLI).
- **Benchmark/bake-off honesty improves for free.** A plan failure is now a first-class `plan_failed` outcome (status != completed → not passed/graded) with a real measured duration, instead of the swallowed 0.0s "error" the bake-off recorded for qwen. No benchmark code change needed.
- **Console-safe + backward-compatible.** `PLAN_FAILED_MESSAGE` is ASCII (verified `.isascii()`), uses `--` not an em-dash; the four prior statuses and their handling are unchanged; `webapp.py` needed no change (its generic `result.error` pass-through carries the clean message); the frontend `status` field is typed `string`, so the new value needs no type change.

## Watch items
- **Doc consistency check came back clean:** the only "four PipelineStatus values" references live in `docs/audits/stage-4/...` — historical audit records (correctly frozen at their point in time), not live docs, so no drift to fix there. The live enumerations (the `designStatus.ts` doc comment) were updated to five.
- **Should a parse failure trigger the fallback chain?** Today `FallbackProvider` falls back only on connection/timeout/404, not on a `plan_failed` from a primary that returns junk. That's defensible (and out of scope here), but if an alt is ever configured, a primary that reliably produces unparseable plans won't be escaped by the alt. Worth a deliberate decision later, not now.

## Escalation recommendation
No escalation needed. One Major (a self-inflicted exit-code collision, fixed by moving `plan_failed` to 6 + a test) and one Minor (tighten the catch to a dedicated parse error). The core behavior — fail clean, don't mask real connection errors — is correct and verified live. Fix both and re-audit to 0/0/0/0/0; the Stage-6 stage-end `audit-team` covers the whole branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **PLAN-001 (Major) — FIXED.** `_cmd_design` now returns **6** for `plan_failed` (was 5), distinct from `gate_failed`'s 5. The contract comment (`test_cli.py`) is updated to "completed -> 0, clarification_needed -> 3, render_failed -> 4, gate_failed -> 5, plan_failed -> 6" and a new `test_design_plan_failed_exit_6_clean_no_traceback` pins exit 6 + the clean message + "no Traceback". Verified live: `kimcad design --backend local_qwen` now exits **6**.
- **PLAN-002 (Minor) — FIXED via a dedicated parse error.** A new `PlanParseError` (with the underlying exception as `.original`) is raised at the exact parse boundary in `llm_provider.generate_design_plan` — only `parse_design_plan(normalize_plan_dict(json.loads(...)))` is wrapped, so the network call and prompt assembly are outside it. `pipeline.run` now catches **only `PlanParseError`**; the broad `(ValueError, TypeError, KeyError, AttributeError, ValidationError)` tuple and the `pydantic` import are gone from `pipeline.py`. A bug elsewhere that raises a plain `ValueError` now propagates instead of being masked — pinned by `test_a_non_parse_error_is_not_masked_as_plan_failed`. New `test_llm_provider.py` cases prove the real provider raises `PlanParseError` (carrying the `ValidationError` / `JSONDecodeError` original) on a schema echo and on bad JSON. The CLI detail is now the underlying type (`(details: ValidationError)`), confirmed live.

Verified after the fixes: `tests/test_pipeline.py` + `test_llm_provider.py` + `test_cli.py` **57 passed**; ruff clean; live qwen design exits 6 with the clean message and no traceback; the connection-error-propagates and non-parse-error-propagates properties both hold. **Roll-up: 0/0/0/0/0.**
