# KimCad — Finish-the-product run ledger (started 2026-06-05)

**Mandate (Scott, 2026-06-05):** do the per-stage audits that were owed AND finish the build to a
releasable beta. Don't stop except on a catastrophic break. Every audit is the REAL skill via
independent agents, every finding fixed (Blocker→Nit), evidence committed to VC. This ledger is the
resume anchor — keep it current so the run survives compaction.

**Branch:** `stage-8.5-usability` (forward build continues here per stage; merges to `main` at each
stage gate). **Resume rule:** read this file + `HANDOFF.md`, find the first row not ✅, continue there.

## Program (execution order)

| # | Phase | wiring-audit | audit-team 0/0/0/0/0 | merge+tag | status |
|---|---|---|---|---|---|
| 1 | Stage 8.5 Slice 11 (responsive/a11y/copy/polish) — build + audit-lite | n/a (slice) | ✅ audit-lite 0/0/0/0/0 (`95b25e0`) | n/a | ✅ DONE |
| 2 | Stage 8.5 STAGE GATE (whole stage) | ✅ wiring-audit PASS 0/0/0/0 | ⏳ audit-team ran (0B/0C/11Maj/22Min/11Nit=44); REMEDIATING to 0/0/0/0/0 | ☐ tag `stage-8.5` | ⏳ IN PROGRESS |
| 3 | Backfill Stage 4 (SPA) audits | ☐ | ☐ (refresh) | n/a (already on main) | ☐ |
| 4 | Backfill Stage 5 (templates/sliders) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 5 | Backfill Stage 6 (model layer) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 6 | Backfill Stage 7 (Smart Mesh) audits | ☐ | ☐ (refresh) | n/a | ☐ |
| 7 | Backfill Stage 0–3 audit-team into VC | n/a (backend) | ☐ | n/a | ☐ |
| 8 | Stage 8 (CadQuery backend) — build + gate | ☐ | ☐ | ☐ tag `stage-8` | ☐ |
| 9 | Stage 9 (image on-ramp) — build + gate | ☐ | ☐ | ☐ tag `stage-9` | ☐ |
| 10 | Stage 10 (direct-print + layer preview) — build + gate | ☐ | ☐ | ☐ tag `stage-10` | ☐ |
| 11 | Stage 11 (installer + beta) — build + gate | ☐ | ☐ | ☐ tag `stage-11` | ☐ |

## Audit gap baseline (verified 2026-06-05, why this run exists)
- **wiring-audit** had run on only 2 Stage-8.5 slices (1, 2–4). NEVER on shipped stages 0–7.
- **audit-team** committed in-repo for stages 4,5,6,7 only; 0–3 audited outside VC (unproven) or not committed.
- Stage 8.5 per-slice gate was incomplete: slices 8 & 9 had no committed audit artifact; 8,9,10 had no audit-team/wiring-audit.

## Stage 8.5 stage-gate remediation tracker (fix all 44 → re-audit → 0/0/0/0/0 → merge → tag)
- ✅ **Docs (9)** — DOC-001..006 + DOC-N1/N2/N3 — commit `d2764ad`.
- ✅ **Engineering (7)** — ENG-001..007 (incl. geometry-version stamp + reopen re-gate + tests) — commit `c1261f2`.
- ✅ **UI/UX (20)** — DONE. A (`bf1006c`): UX-001/009/005/007/012/013/015/017. B1 (`3fa1655`): UX-002/003/010/008/011. B2: UX-004 (shorter mobile viewport + sticky "Check & download" CTA), UX-006 (Topbar printer-status chip incl. build_volume on /api/options). Nits: UX-014 (apostrophe style — convention noted, no mass rewrite), UX-016 (photo alt="" confirmed intentional — decorative; the editable seed is the content), UX-018 (InfoTip italic-i kept — hit-area meets WCAG 2.5.8; documented). All UX findings closed.
- ✅ **Tests (5)** — TEST-001 (hosted frontend CI job, `be1e138`); TEST-002 (useHashRoute hook tests); TEST-003 (cloud key never in logs — capsys); TEST-004 (My Designs active-route behavior assertion); TEST-005 (api-mock seam accepted — strong socket-level backend coverage; documented).
- ✅ **QA (3)** — QA-001 (/api/render `adjusted_params` clamp hint); QA-002 (prompt-keyword demo scenarios `demo:gatefail` / `demo:experimental` so error/offer states are live-reachable); QA-003 (bad-id wording unified).
- ✅ **Re-audit round 1** (reaudit/): Engineering CLEAR 0/0/0/0/0; QA PASS; UI/Docs/Test all-prior-resolved + a second tier surfaced (remediation-introduced gaps). **Second-tier remediated** (UI focus-ring/dup-rule; docs reconciled; +6 tests).
- ✅ **Re-audit round 2** (reaudit/round2-*): **UI 0/0/0/0/0, Docs 0/0/0/0/0, Test 0/0/0/0/0** (Test lane confirmed coverage with a false-green mutation sweep). 763 pytest non-live + 262 vitest.
- 🟢 **STAGE 8.5 GATE = CLEAN: 0/0/0/0/0 across all 5 lanes (engineering/UI/docs/test/QA) + wiring-audit PASS.** All 44 original + second-tier findings closed, independently re-verified.
- ▶ **MERGE + TAG `stage-8.5` — Scott authorized "do it all / finish the whole run" (2026-06-05).** Phase A: exec-doc 44→42 corrected; Stage-8.5 CHANGELOG block added; docs marked DONE; merge `stage-8.5-usability` → `main` (--no-ff) + tag `stage-8.5` IN PROGRESS.

## Phase B — backfill owed audits on shipped stages 0–7 (wiring-audit first, then audit-team)
| Stage | wiring-audit | audit-team | status |
|---|---|---|---|
| 0 (pipeline + web stub) | n/a (backend) | ☐ (commit into VC) | ☐ |
| 1 (deterministic pipeline) | n/a | ☐ (commit into VC) | ☐ |
| 2 (connectors) | n/a | ☐ (move pkg into VC) | ☐ |
| 3 (printer coverage) | n/a | ☐ (move pkg into VC) | ☐ |
| 4 (React SPA + viewport) | ☐ | ☐ | ☐ |
| 5 (templates + sliders) | ☐ | ☐ | ☐ |
| 6 (model layer) | ☐ | ☐ | ☐ |
| 7 (Smart Mesh + readiness) | ☐ | ☐ | ☐ |

## Phase C — build Stages 8 → 9 → 10 → 11 to the beta (per-slice audit-lite → stage gate → 0/0/0/0/0 → merge → tag)
| Stage | build | gate | tag | status |
|---|---|---|---|---|
| 8 (CadQuery backend) | ☐ | ☐ | ☐ `stage-8` | ☐ |
| 9 (image/sketch on-ramp) | ☐ | ☐ | ☐ `stage-9` | ☐ |
| 10 (direct-print + layer preview) | ☐ | ☐ | ☐ `stage-10` | ☐ |
| 11 (installer + beta gate, FINAL) | ☐ | ☐ | ☐ `stage-11` | ☐ |

## Log
- 2026-06-05: Run started. Slices 1–10 of Stage 8.5 built + pushed (Slice 10 = `7fc5415`). Slice 11 built + gated + pushed (`95b25e0`). Stage-8.5 stage gate ran: wiring-audit PASS; audit-team 44 findings. Remediation: docs (`d2764ad`) + engineering (`c1261f2`) done; UX/test/QA next.
