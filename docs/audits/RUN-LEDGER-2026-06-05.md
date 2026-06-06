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
| 2 | Stage 8.5 STAGE GATE (whole stage) | ✅ wiring-audit PASS | ✅ audit-team 44 findings ALL fixed → re-audit 0/0/0/0/0 across 5 lanes | ✅ merged `fb65e6f` + tagged `stage-8.5` | ✅ DONE |
| 3 | Backfill Stage 4 (SPA) audits | ✅ wiring PASS | ✅ 0/0/0/0/0 (re-audited) | n/a (fixes on backfill branch) | ✅ DONE |
| 4 | Backfill Stage 5 (templates/sliders) audits | ✅ wiring PASS | ✅ 0/0/0/0/0 (re-audited) | n/a | ✅ DONE |
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
- ✅ **MERGE + TAG `stage-8.5` — DONE (2026-06-05, Scott authorized "do it all / finish the whole run").** Merged `stage-8.5-usability` → `main` (--no-ff, merge `fb65e6f`), tag `stage-8.5` on the merge commit; pushed gate-green (`c20c0d8..fb65e6f main`; `* [new tag] stage-8.5`). Stages 0–8.5 all tagged on origin. **RESUME = Phase B below.**

## Phase B — backfill owed audits on shipped stages 0–7 (wiring-audit first, then audit-team)
| Stage | wiring-audit | audit-team | status |
|---|---|---|---|
| 0 (pipeline + web stub) | n/a (backend) | ☐ (commit into VC) | ☐ |
| 1 (deterministic pipeline) | n/a | ☐ (commit into VC) | ☐ |
| 2 (connectors) | n/a | ☐ (move pkg into VC) | ☐ |
| 3 (printer coverage) | n/a | ☐ (move pkg into VC) | ☐ |
| 4 (React SPA + viewport) | ✅ PASS | ✅ 0/0/0/0/0 (round-2 re-audit verified) | ✅ DONE — `docs/audits/stage-4/backfill-2026-06-05/` |
| 5 (templates + sliders) | ✅ PASS | ✅ 0/0/0/0/0 (re-audited; 3 real bugs fixed) | ✅ DONE — `docs/audits/stage-5/backfill-2026-06-05/` |
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
- 2026-06-05 (Phase B / Stage 5): backfill audit of the template engine + live-slider surface.
  6 independent agents → 0B/1C/4Maj/7Min/4Nit. THREE real bugs (this is where they showed up):
  QA-501 (non-finite JSON 500'd /api/render), ENG-501 (thick wall collapsed a box to a solid block
  that still gated PASS), QA-502 (gate said "fits" but parts failed to slice — root-caused live to
  OrcaSlicer arrange-clearance + auto-orient rotating the footprint; fixed by capping every template
  dim at the verified-sliceable ~170mm + an honest slicer message). ALL findings fixed + regression
  tests; round-2 re-audit CLEAN (false-green verified; worst corner 170³ slices to real G-code).
  Gate green (ruff, geometry, 771 pytest, 276 vitest, build reproducible). Package:
  `docs/audits/stage-5/backfill-2026-06-05/`.
- 2026-06-05 (Phase B / Stage 4): backfill audit of the current SPA + viewport + web-serving code.
  6 independent agents (wiring-audit + 5-role audit-team) → 0B/0C/8Maj/17Min/9Nit. ALL fixed
  (backend ENG-401/403/404/405/406 + QA-001/002/004 + TEST-402; frontend UX-001..008 + M-1 + L-1/2 +
  QA-003; docs DOC-401..408; tests TEST-401/402/403 + QA regressions). Round-2 re-audit caught
  UX-002 (clip-path was paint-only → re-fixed by pinning sr-only top:0; re-verified 248px→0px) and
  4 residual `/vendor/` doc contradictions (all fixed). Final: 0/0/0/0/0 all lanes + wiring PASS;
  gate green (ruff, geometry, 764 pytest, 276 vitest, build reproducible). Package committed at
  `docs/audits/stage-4/backfill-2026-06-05/`. Removed dead `src/kimcad/web/vendor/`.
- 2026-06-05: Run started. Slices 1–10 of Stage 8.5 built + pushed (Slice 10 = `7fc5415`). Slice 11 built + gated + pushed (`95b25e0`). Stage-8.5 stage gate ran: wiring-audit PASS; audit-team 44 findings. Remediation: docs (`d2764ad`) + engineering (`c1261f2`) done; UX/test/QA next.
