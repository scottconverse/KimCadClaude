# Stage 4 audit-team — remediation closure
**Date:** 2026-06-01 · Every finding from the five deep-dives is resolved (fixed, or a documented no-action / addressed-differently). Fixes landed in five batches on `stage-4-react-spa-shell`; each was built, tested, and pushed under the CI gate (ruff + full pytest incl. live + vitest + build-reproducibility).

## Majors (6) — all FIXED
| ID | Resolution | Commit |
|----|-----------|--------|
| TEST-001 | Contract test tightened: strips comments, requires `.field` access / quoted literal — mutation-proven to reject the className/comment false-pass vectors. | batch 1 (`2603566`) |
| DOC-401 | Descoped the browser-"send" overclaim in README + ARCHITECTURE (send is CLI/MCP + Stage 10). | batch 1 |
| DOC-402 | Added the Stage-4 CHANGELOG entry; superseded the stale vanilla-UI web-send line. | batch 1 |
| ENG-401 | `scripts/ci.sh` rebuilds the SPA and asserts committed `src/kimcad/web` == fresh build. | batch 2 (`d39a9ee`) |
| UX-003 | Text-bearing fills/links use `--kc-accent-strong/-deep` → white-on-accent ~5.0:1, accent-on-surface ~4.7:1 (both clear WCAG-AA). | batch 3 (`af3a5cf`) |
| UX-001 | Viewport instrumented: projected W/D/H dimension pills + bounding box + orientation chip + drag hint. | batch 3 |

## Minors — FIXED unless noted
ENG-402 lock the registry/gate reads (batch 4 `c224c1e`) · ENG-403 `dispose()` `forceContextLoss()` (batch 3) · ENG-405 documented the octet-stream fallback (batch 4) · UX-004 touch targets ≥44px (batch 3) · UX-005 hero input stacks on mobile (batch 3) · UX-006 removed the inert Settings gear (batch 3) · UX-007 `prefers-reduced-motion` (batch 3) · UX-008 outcome-first badge (batch 3) · UX-009 dimensions-aware canvas aria-label (batch 3) · DOC-403 frontend/README filenames (batch 1) · DOC-404 frontend/README API list (batch 1) · DOC-405 README "no Node to run" up front (batch 5) · TEST-002 stood up jsdom + Testing Library; component tests for the printability render + gate-aware ExportPanel (batch 5) · TEST-003 vitest branch cases (batch 2) · TEST-004 code-split three.js fingerprint (batch 2) · QA-001 HEAD → header-only 200 (batch 4).
- **UX-002 — addressed differently (documented):** kept solid-shaded rendering rather than the prototype's blueprint-wireframe default — solid is the better, more honest default for a *real loaded STL* (the prototype's blueprint suited its fake parametric geometry); the print-aware affordances (UX-001) deliver the design's "instrumented preview" intent.
- **ENG-404 — NO-ACTION:** the audit verified the grid/plate alloc is disposed (no leak); only a tiny avoidable allocation, no fix recommended.
- **TEST-005 — NO-ACTION:** the CSS-token test is intentionally a build-completeness check (its docstring says so); kept, not over-read as visual proof — the rendered visual check covers visual correctness.

## Nits — FIXED unless noted
ENG-406 documented the content-type map (batch 4) · ENG-408 CI frontend release gate (batch 2) · UX-010 warmer first-person sub-copy (batch 3) · UX-011 assistant cube avatar (batch 3) · UX-012 print-file (.3mf) framing (batch 3) · DOC-406 refreshed the App comment (batch 1) · QA-002 static-asset ETag revalidation (batch 4) · QA-003 orphan per-design dir cleanup on startup (batch 4) · QA-004 413 sets `close_connection` (batch 4).
- **ENG-407 — NO-ACTION:** the `chunkSizeWarningLimit` is already commented with its rationale.
- **TEST-006 — NO-ACTION:** the few exact-string label assertions are an accepted copy-coupling trade-off (audit recommended no action).
- **DOC-407 — at merge:** ROADMAP Stage 4 flips from "⬅ NEXT" to "DONE — tagged" when the branch merges (same as Stage 3).

## Verification
After all batches: `bash scripts/ci.sh` green — ruff clean, full `pytest tests` (incl. live OrcaSlicer), vitest 19/19 (5 files, incl. jsdom component tests), and the build-reproducibility assertion (committed build == fresh). `npm audit` = 0. A rendered desktop + mobile pass confirmed the UX fixes (dimension pills, AA contrast, chip/hint/avatar, stacked hero). Re-audit follows; merge + tag only at 0/0/0/0/0.
