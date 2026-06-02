# Executive Audit — KimCad Stage 6 (model layer)

**Date:** 2026-06-02
**Branch:** `stage-6-model-swap` (head `96033c2` at audit time), diffed against `main`
**Scope:** the full Stage 6 surface — hardware-aware model advisor (`kimcad models`), tiered LLM fallback (`FallbackProvider`), 3-axis benchmark grading, the model bake-off (`kimcad bakeoff`), and plan-failure robustness (`PlanParseError` / `plan_failed`), plus the Stage 6 docs.
**Posture:** balanced. **Mode:** full (all 5 roles). **Writer mode:** audit-only.

## Executive summary

Stage 6 is **engineering-sound and runtime-clean** — the Principal Engineer and QA roles found zero Blockers/Criticals/Majors, and every load-bearing safety property holds under both code-read and live runruntime checks: advisory-only (no config mutation), no fallback contamination in the bake-off, connection errors never masked as plan failures, unique exit codes, and an honest tri-state grade. The weakness is **documentation honesty**: the Stage 6 bake-off doc — the one artifact whose whole subject is the model decision — still frames the swap as open and shows a worked example in which Qwen *wins*, the exact inverse of the settled verdict (Qwen rejected 0/10; gemma stays). That is the lone Critical. The UI/UX role flagged two real Majors on the failure-and-degenerate-result surfaces (a web plan-failure that reads like an idle state; a bake-off table that shows misleading `0/0` for a model that completed nothing). The remaining findings are doc staleness, test-coverage seams on defensive paths, and hygiene. No finding blocks the gate on its own, but per the project's fix-everything standard all are remediated to 0/0/0/0/0 before merge + tag.

## Severity roll-up (all roles)

| Severity | Eng | UI/UX | Docs | Test | QA | **Total** |
|---|---|---|---|---|---|---|
| Blocker | 0 | 0 | 0 | 0 | 0 | **0** |
| Critical | 0 | 0 | 1 | 0 | 0 | **1** |
| Major | 0 | 2 | 4 | 0 | 0 | **6** |
| Minor | 2 | 4 | 3 | 4 | 0 | **13** |
| Nit | 3 | 3 | 2 | 3 | 0 | **11** |
| **Total** | **5** | **9** | **10** | **7** | **0** | **31** |

## Top 10 findings (by severity)

1. **DOC-001 (Critical)** — `docs/benchmarks/stage-6-model-bakeoff.md` still presents the swap as open and shows a worked example where Qwen wins ("SWITCH default to local_qwen"); the real verdict (Qwen 0/10, rejected; gemma stays, KEEP) appears nowhere in the doc named for the decision.
2. **UX-001 (Major)** — A web `plan_failed` renders like an idle/neutral state: the failure copy sits in a neutral bubble (no error tone) and both right-panel cards show their never-tried-yet placeholders, so a skimming user can't tell the attempt failed.
3. **UX-002 (Major)** — The bake-off table shows misleading `0/0` axis cells (and `0.0` mean_s) for a model that completed zero cases — the canonical "reject the challenger" run is the most ambiguous row.
4. **DOC-002 (Major)** — HANDOFF title says "Stage 6 IN PROGRESS — Slices 1 & 2 done" while its own body says "ALL 5 SLICES DONE."
5. **DOC-003 (Major)** — HANDOFF pins branch head `1928e13`; the actual head is `96033c2` (the Slice-5 commit, not the final docs commit).
6. **DOC-004 (Major)** — README documents 3 of the 5 shipped CLI verbs — no `kimcad models`, no `kimcad bakeoff`, no model decision.
7. **DOC-005 (Major)** — `config/default.yaml` `local_qwen` comment still says it "Becomes the default only if it clears the bar," implying the swap is pending.
8. **ENG-601 (Minor)** — `_ollama_tags_url` string-splits on `/v1` and drops any path tail (advisory robustness; correct for every real local URL).
9. **UX-003 (Minor)** — `kimcad models` suggests pulling Qwen 7B "for a step up in quality" from a static `tier` int — the repo's own bake-off rejected the qwen family; two un-reconciled notions of "better."
10. **TEST-001 (Minor)** — No negative test that `FallbackProvider` lets an arbitrary (non-transport) exception propagate without touching alt — the one in-scope narrowing whose exclusivity isn't pinned.

## What's working well (specific)

- **The central safety boundary is airtight.** The network call sits *outside* the try; only the parse is wrapped; `pipeline.run` catches *only* `PlanParseError`; and openai's transport errors are provably disjoint from the wrapped set (verified against `openai==2.38.0`). A transport outage can never be misreported as a "model too small" plan failure.
- **Advisory-only is enforced by construction** — `model_advisor` and `bakeoff` have no config-write path at all; `recommend()` and `compare_runs()` are pure (idempotent, inputs unmutated).
- **No fallback contamination** — `_pipeline_for_backend` builds a bare `LLMProvider` so each bake-off model is measured in isolation.
- **The 3-axis grade is honest** — a None/unassessed axis is excluded from the denominator and never blocks a pass; the dimensional ceiling can only *fail* the axis, never assert it (the undersized-fits-ceiling regression is a named test).
- **Tests don't game CI** — zero skips/xfail/.only/placeholder-asserts across the in-scope files; every safety property has a mutation-killing test; a real two-thread concurrency test pins thread-local stickiness.
- **QA: every runtime gate green** — `kimcad models`, the `bakeoff` fail-fast validation, the `plan_failed` exit-6 clean path, 588 pytest (incl. live OrcaSlicer) + 36 vitest + a reproducible frontend build, and `git status` stayed clean after every command.
- **The model decision reads accurately in the load-bearing docs** (CHANGELOG/ROADMAP/HANDOFF body) and matches the committed `output/bakeoff/bakeoff.txt`; no doc overclaims Stage 6 as done/merged/tagged.

## This-sprint punch list

See `sprint-punchlist.md` — every finding (Critical→Nit) is remediated this sprint per the fix-everything standard before the stage is merged + tagged.

## Next-sprint watchlist

See `next-sprint-watchlist.md` — forward-looking items (the advisor-vs-bake-off "two notions of better" seam, the future `alt_backend` user-doc note on stickiness, the `Recommendation` name collision if the model layer grows).

## Blast-radius notes (fixes that ripple)

- **UX-001 fix touches all status-based failures** (`plan_failed`/`render_failed`/`gate_failed`), not just plan_failed — drive the assistant-row tone + card "failed" branches once for all three; rebuild the SPA (the pre-push reproducibility gate checks committed assets == fresh build).
- **The stale "swap qwen if it clears the bar" framing has one root and three instances** (DOC-001 bake-off doc, DOC-005 config comment, DOC-006 HANDOFF block) — fix as one coordinated pass so a single truth ("evaluated, rejected, gemma stays") lands everywhere.
- **ENG-602 rename** (`bakeoff.Recommendation`) ripples to `bakeoff.py` internals + `test_bakeoff.py` imports — pure rename, no behavior.

## Gate decision

Bar = 0/0/0/0/0. The audit found 0 Blocker / 1 Critical / 6 Major / 13 Minor / 11 Nit. I (Claude) remediate every finding, re-verify (full Windows gate), then merge + tag `stage-6`. The model decision (gemma stays; qwen rejected) is settled and was not re-litigated by any role.
