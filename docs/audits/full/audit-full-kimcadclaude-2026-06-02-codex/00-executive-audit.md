# Executive Audit - KimCadClaude full project

**Audit date:** 2026-06-02  
**Audit target:** `C:\Users\scott\dev\kimcad`, `main` at `f26feb9`, tag `stage-6`  
**Audit scope:** Full project: product/spec docs, roadmap/handoff, Python core, React SPA, local web/API runtime, CLI, test suite, CI gate, prior stage audit artifacts.  
**Posture:** Balanced  
**Execution note:** Run sequentially by Codex under `audit-full`; no delegated subagents were used.

## Executive summary

KimCadClaude is in strong engineering shape for the implemented Stage 6 artifact: the full Python suite passed, frontend tests/build passed, the local web UI worked in demo mode, re-render and slice APIs worked, and the CLI model advisor behaved cleanly. The acute risk is not code; it is **control-plane truth drift**. The v3.0 controlling spec points to missing companion files and still carries obsolete model/stage instructions, `HANDOFF.md` still tells a resumed agent to redo the completed Stage 6 gate, and hosted CI is materially weaker than the docs claim. This is shippable as the current Stage 6 code artifact, but not clean enough as a project control surface for the next autonomous stage.

## Readiness at a glance

| Dimension | Status | Summary |
|---|---|---|
| Architecture & code | Solid | Implemented Stage 6 seams are narrow, tested, and runtime-verified. |
| UI / UX | Solid for current shipped slice | Demo flow renders and produces preview/export/slice; v3.0 target surfaces remain future staged work. |
| Documentation | Serious concerns | The controlling spec and handoff contradict current reality in load-bearing places. |
| Test suite | Concerns | Local test signal is strong, but hosted CI does not match the documented gate. |
| Runtime QA | Solid | Web/API/CLI checks passed on the actual KimCad server at port 9876. |

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 1 |
| Major | 2 |
| Minor | 0 |
| Nit | 0 |
| **Total** | **3** |

## Top findings

| # | ID | Severity | Role | Title | Blast |
|---|---|---|---|---|---|
| 1 | DOC-001 | Critical | Documentation | The controlling v3.0 spec points to missing files and obsolete model/stage truth | Next-stage builders can follow a non-existent or wrong control plane |
| 2 | DOC-002 | Major | Documentation | `HANDOFF.md` first banner still says to resume at the completed Stage 6 gate | Resumed sessions may redo completed work instead of starting Stage 7 |
| 3 | TEST-001 | Major | Test | Hosted CI does not run the same gate the docs say it does | A future GitHub-hosted green check could miss frontend/build/live-gate failures |

## Cross-role findings

### Control-plane truth drift

- **Surfaced in:** DOC-001, DOC-002, TEST-001
- **What it is:** The implementation is healthier than the project instructions around it. The v3.0 spec, handoff, README, hosted CI file, and local CI script no longer agree about the source of truth, next stage, model default, companion docs, or gate coverage.
- **Why this is the most important issue:** Scott explicitly relies on specs/handoffs to resume work across sessions. If those documents point to missing artifacts or stale stages, future agents can waste a stage before touching code.
- **Blast radius of the fix:** Mostly docs and CI. Do not change runtime code while rebaselining the control plane.
- **Recommended approach:** Treat the next task as a docs/control-plane cleanup: reconcile v3.0 spec, handoff, roadmap, README CI text, and hosted CI before Stage 7 code begins.

## What's working

- **Engineering:** The deterministic pipeline, fallback model layer, bake-off isolation, and plan-failure boundary are narrow and tested.
- **UI/UX:** The current SPA renders the core prompt-to-preview-to-printability-to-export flow cleanly in desktop demo mode.
- **Documentation:** README/ROADMAP/HANDOFF mostly tell the implemented Stage 6 story correctly; the stale lines are identifiable and local.
- **Tests:** 609 pytest, 37 vitest, ruff, frontend build, npm audit, direct API re-render, and live slice all passed in this session or the immediately preceding audit run.
- **Runtime quality:** `kimcad models`, web demo, `/api/render`, and `/api/slice` all behaved cleanly.

## This-sprint punch list summary

Must-fix:

- DOC-001 - Rebaseline the controlling v3.0 spec to match the repo's actual current truth, or move the missing companion-doc claims out of the controlling path.

Should-fix:

- DOC-002 - Remove the stale Stage 6 resume instruction from `HANDOFF.md`.
- TEST-001 - Either make hosted CI match the documented gate or correct the docs to say the real gate is local Windows/pre-push only until hosted CI is re-enabled.

See `sprint-punchlist.md`.

## Next-sprint watchlist summary

- Add a real UI rendered regression pass for desktop + mobile slider drag in the next UI-bearing stage.
- Decide whether v3.0 spec stage numbering or repo tag stage numbering is authoritative before Stage 7 starts.
- Keep cloud fallback disclosure visible if `alt_backend` becomes normal user setup rather than a power-user override.

See `next-sprint-watchlist.md`.

## What we couldn't assess

- Real hardware printers are not in scope until Kim/community hardware validation.
- Mobile layout was not rendered in this pass.
- The Browser screenshot API timed out in the prior pass, so this report uses DOM/console/API evidence rather than screenshots.

## Recommended next actions

1. Fix DOC-001 and DOC-002 as a docs/control-plane pass.
2. Run `audit-lite` on that docs/control-plane fix.
3. Fix TEST-001 before relying on GitHub-hosted checks as an authoritative gate.
4. Proceed to Stage 7 only after the source-of-truth docs have one current state.

## Reference - role deep-dives

- `01-engineering-deepdive.md`
- `02-uiux-deepdive.md`
- `03-documentation-deepdive.md`
- `04-test-deepdive.md`
- `05-qa-deepdive.md`

