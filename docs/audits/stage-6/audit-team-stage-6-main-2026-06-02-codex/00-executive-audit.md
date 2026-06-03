# Executive Audit - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Audit target:** `main` at `f26feb9` (`stage-6`, `origin/main`)  
**Audit scope:** Full five-role audit-team pass over the current Stage 6 artifact: model advisor, fallback provider, benchmark grading, bake-off, plan-failure handling, web runtime, docs, tests, and prior Stage 6 audit/remediation package.  
**Posture:** Balanced  
**Execution note:** Run sequentially by Codex. No subagents were spawned because the available delegated-agent tool requires explicit delegation permission.

## Executive summary

The current `main` artifact is broadly shippable for the Stage 6 scope: code, tests, CLI behavior, API behavior, and the demo web flow all hold up under this pass. The full backend suite passed at 609 tests, frontend tests passed at 37 tests, ruff is clean, npm audit found 0 vulnerabilities, and the demo web UI rendered with no console warnings or errors. The one real defect is documentation drift in the first-screen handoff banner: the same paragraph says Stage 6 is done and then tells the next agent to resume at the already-completed Stage 6 gate with stale test counts. That is not a code safety issue, but it is load-bearing process documentation and should be fixed before the next handoff.

## Readiness at a glance

| Dimension | Status | Summary |
|---|---|---|
| Architecture & code | Solid | Stage 6 seams remain narrow: advisory-only model selection, opt-in fallback, isolated bake-off, narrow plan-parse failure handling. |
| UI / UX | Solid with one unverified interaction | Demo desktop flow rendered cleanly; Browser automation could not conclusively exercise physical slider drag/keyboard changes. |
| Documentation | Concerns | One stale `HANDOFF.md` resume instruction contradicts the completed/merged/tagged Stage 6 state. |
| Test suite | Solid | 609 pytest, 37 vitest, focused Stage 6 coverage and prior remediation tests are present. |
| Runtime QA | Solid | CLI model advisor, invalid bake-off handling, web demo design, API re-render, and console/log checks passed. |

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 0 |
| Nit | 0 |
| **Total** | **1** |

## Top findings

| # | ID | Severity | Role | Title | Blast |
|---|---|---|---|---|---|
| 1 | DOC-001 | Major | Documentation | `HANDOFF.md` first-screen Stage 6 banner still says to resume at the completed gate | Misleads a resumed agent into re-running/completing work that is already merged and tagged |

## Cross-role findings

### Stale handoff instruction

- **Surfaced in:** DOC-001, QA observation
- **What it is:** The top `READ FIRST` Stage 6 paragraph says Stage 6 is done, remediated, merged, tagged, and next is Stage 7, but lines 18-19 still say `RESUME HERE = the Stage 6 stage-end audit-team gate` and cite stale 588/36 counts.
- **Why this matters:** `HANDOFF.md` is explicitly the first document a resumed agent is supposed to trust. A contradiction there creates process churn even when code is healthy.
- **Blast radius of the fix:** Documentation only. Update the top banner and any stale count in that sentence; do not change code.
- **Recommended approach:** Replace the stale resume clause with "Resume at Stage 7" language and either remove per-run counts from the top banner or use the already-current 609 pytest / 37 vitest statement from the Stage 6 section.

## What's working

- **Engineering:** `FallbackProvider` catches only transport/not-found errors; arbitrary primary exceptions are tested to propagate without alt fallback.
- **UI/UX:** Demo mode reached the workspace with conversation, 3D preview, parameter panel, printability report, connector badge, printer/material selectors, and export link visible.
- **Documentation:** The Stage 6 benchmark doc and roadmap now lead with the settled verdict: qwen rejected, gemma stays.
- **Tests:** The full Python suite passed at 609 tests; the frontend suite passed at 37 tests; the prior Stage 6 remediation tests remain committed.
- **Runtime quality:** `kimcad models` ran on this box and returned the expected Gemma recommendation; invalid bake-off input failed cleanly instead of crashing.

## This-sprint punch list summary

Must-fix: none.  
Should-fix: DOC-001.

See `sprint-punchlist.md`.

## Next-sprint watchlist summary

- Keep real pointer/touch slider verification in the Stage 7 UI audit checklist.
- Keep cloud fallback disclosure visible in user-facing docs if `alt_backend` becomes recommended rather than power-user config.

See `next-sprint-watchlist.md`.

## Blast-radius callouts

- **DOC-001** - Documentation-only fix, but it is in the handoff first viewport. Do not create another "done up top / pending below" split while editing it.

## What we couldn't assess

- **UI/UX and QA:** The in-app Browser screenshot call timed out, and pointer/keyboard manipulation of range sliders did not produce a conclusive interaction signal. The `/api/render/<id>` re-render path was verified directly and component/unit tests cover the debounce path, but a real visual desktop+mobile slider drag was not conclusively reproduced in this audit pass.

## Recommended next actions

1. Fix DOC-001 in `HANDOFF.md`.
2. Run `audit-lite` on that doc-only fix.
3. Keep Stage 7 as the next implementation stage; do not reopen the Stage 6 model decision.

## Reference - role deep-dives

- `01-engineering-deepdive.md`
- `02-uiux-deepdive.md`
- `03-documentation-deepdive.md`
- `04-test-deepdive.md`
- `05-qa-deepdive.md`

