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
| 5 | Backfill Stage 6 (model layer) audits | ✅ wiring PASS | ✅ 0/0/0/0/0 (re-audited) | n/a | ✅ DONE |
| 6 | Backfill Stage 7 (Smart Mesh) audits | ✅ wiring PASS | ✅ 0/0/0/0/0 (re-audited) | n/a | ✅ DONE |
| 7 | Backfill Stage 0–3 audit-team into VC | n/a (backend) | ✅ 0/0/0/0/0 (re-audited; ENG-001 safety + QA-301) | ✅ committed | ✅ DONE |
| 8 | Stage 8 (CadQuery backend) — build + gate | n/a (UI delta driven live by QA+UX roles) | ✅ audit-team 7M/16m/11n ALL fixed → 2 re-audit lanes 0/0/0/0/0 | ✅ merged + tagged `stage-8` | ✅ DONE |
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
| 0 (pipeline + web stub) | n/a (backend) | ✅ DONE (`docs/audits/stage-0-3-backend/backfill-2026-06-06/`; old root pkg migrated to `docs/audits/stage-0/`) | ✅ DONE |
| 1 (deterministic pipeline / gated export) | n/a | ✅ DONE (combined backend audit; ENG-001 NaN-gate safety fix) | ✅ DONE |
| 2 (connectors) | n/a | ✅ DONE (combined backend audit) | ✅ DONE |
| 3 (printer coverage) | n/a | ✅ DONE (combined backend audit; QA-301 friendly errors) | ✅ DONE |
| 4 (React SPA + viewport) | ✅ PASS | ✅ 0/0/0/0/0 (round-2 re-audit verified) | ✅ DONE — `docs/audits/stage-4/backfill-2026-06-05/` |
| 5 (templates + sliders) | ✅ PASS | ✅ 0/0/0/0/0 (re-audited; 3 real bugs fixed) | ✅ DONE — `docs/audits/stage-5/backfill-2026-06-05/` |
| 6 (model layer) | ✅ PASS | ✅ 0/0/0/0/0 (re-audited; Critical privacy-copy bug fixed) | ✅ DONE — `docs/audits/stage-6/backfill-2026-06-05/` |
| 7 (Smart Mesh + readiness) | ✅ PASS | ✅ 0/0/0/0/0 (re-audited; warn-badge AA + score-table consistency fixed) | ✅ DONE — `docs/audits/stage-7/backfill-2026-06-05/` |

## Phase C — build Stages 8 → 9 → 10 → 11 to the beta (per-slice audit-lite → stage gate → 0/0/0/0/0 → merge → tag)
| Stage | build | gate | tag | status |
|---|---|---|---|---|
| 8 (CadQuery backend) | ✅ 5 slices audit-lite | ✅ audit-team + 2 re-audit lanes 0/0/0/0/0 | ✅ `stage-8` | ✅ DONE |
| 9 (image/sketch on-ramp) | ✅ 3 slices audit-lite | ✅ walkthrough + audit-team 0/0/0/0/0 | ✅ `stage-9` | ✅ DONE |
| 10 (direct-print + Bambu-native + wizard downloads; layer preview resolved deferred-not-dropped at the tag) | ✅ 4 slices audit-lite | ✅ walkthrough + audit-team 0/0/0/0/0 | ✅ `stage-10` | ✅ DONE |
| 11 (installer + beta gate, FINAL) | ✅ 7 slices (audit-lites 11.1-11.5; 11.6/11.7 covered at the gate) | ✅ two-lane audit-team on the diff + the INSTALLED artifact, 0/0/0/0/0 (a REAL Blocker caught: no SPA in the wheel) | ✅ `stage-11` + `beta` | ✅ DONE - THE BETA IS BUILT |

## Log
- 2026-06-10 (Phase C / Stage 11 — the installer + beta gate, FINAL): built in 7 slices (the
  WebView2 shell with a stable-origin port; the Settings Printer-connections card closing the
  Stage-10 root UX finding; 0.9.0b1 single-sourced; the dev/installed paths seam; the build
  pipeline + Inno installer — built, silent-installed, verified, uninstalled on this box;
  Ollama detect-and-guide; dispositions + user docs incl. PrintProof3D v0.5.0 BUNDLED on its
  stable release). Slice audit-lites caught real ones (ephemeral-origin localStorage wipe; two
  seam-bypassed PROJECT_ROOT copies; a cosmetic release strip). THE GATE CAUGHT A GENUINE
  BLOCKER: the wheel shipped no SPA and no prompts (editable installs had masked missing
  package-data for the project's entire history; every install proof had exercised the API,
  never '/') — packaging fixed, verify_install now fetches the SPA shell + an asset, the
  installer-staging smoke added to CI, and the full install/verify cycle re-proven incl.
  spaced paths and the installed window showing the real app. ALL gate findings remediated to
  0/0/0/0/0. Tagged stage-11 + beta; KimCad-Setup-0.9.0b1.exe + SHA-256 attached to the
  GitHub release. **Phase C complete. The beta is built — next: Kim's printers.**
- 2026-06-10 (Phase C / Stage 10 — direct-print UI + Bambu-native + wizard downloads): built in 4
  slices (registry-alias flattening; SendPanel direct print; Bambu-native connector mock-tested;
  in-app model downloads + Settings vision row), each through an independent audit-lite to
  0/0/0/0/0 — the slice audits caught a REAL lock-reentrancy deadlock (model_pull) and a REAL
  vacuous fake-timers test (SendPanel unmount). Live walkthrough clean (zero findings). The 5-role
  audit-team gate rolled up 0B/0C/10Maj/21Min/5Nit — headline finds: the Bambu busy gate failing
  OPEN on UNKNOWN-at-send (fail-closed now, TOCTOU re-check added), the library never sending MQTT
  DISCONNECT (defensive disconnect added), server log_error silenced (restored to stderr), the
  send-flow copy pointing at a Settings section that doesn't exist (venue-honest sweep + the
  per-piece /api/connector-status diagnosis surfaced in the picker). ALL 36 remediated to
  0/0/0/0/0. Tagged `stage-10`. Package: docs/audits/stage-10/audit-team-2026-06-10/.
  **Next: Stage 11 (installer + beta gate, FINAL).**
- 2026-06-10 (Phase C / Stage 9 — image & sketch on-ramps): built in 3 slices (sketch backend,
  sketch UI, vision-model fix + benchmark), each audit-lite 0/0/0/0/0. The stage MEASURED the
  inherited photo on-ramp against the real pinned model and found gemma4:e4b's vision BROKEN on
  this stack (deterministic hallucination; the model itself says no image was provided) — every
  Stage-8.5 photo impression had come from demo mode. Fixed with a dedicated local vision model
  (qwen2.5vl:3b, 5/5 end-to-end), photo→3D reconstruction honestly descoped per the ROADMAP exit
  branch, DesignRegistry extracted with its three locking protocols as methods. Live walkthrough
  clean; audit-team 0B/0C/10Maj/18Min/5Nit → ALL 33 remediated to 0/0/0/0/0. Tagged `stage-9`.
  Package: docs/audits/stage-9/audit-team-2026-06-10/.
- 2026-06-06 (Phase C / Stage 8 — CadQuery parallel backend): built in 5 slices (worker+runner,
  interpreter discovery+config, pipeline mutual OpenSCAD↔CadQuery fallback, STEP export end-to-end,
  docs+bench), each through an independent `audit-lite` to 0/0/0/0/0 — the Slice-1 audit caught a
  REAL reproduced sandbox escape (`cq.exporters.os.system` pivot via the injected cadquery module),
  closed by a geometry-only facade + `ast` block-list. The 5-role `audit-team` stage gate rolled up
  0B/0C/7Maj/16Min/11Nit (the security model held under every role's probing; the small UI delta's
  wiring was driven live by the QA + UX roles). ALL findings remediated — worker env/cwd isolation +
  a through-`render_cadquery` escape-class canary + a `KIMCAD_RELEASE=1` backstop (so the
  worker-sandbox RCE live tests can't silently skip), an "Engine: …" provenance chip, doc precision,
  and the worker failure-direction tests — then TWO independent re-audit lanes (eng/security/test,
  UX/docs) closed at 0/0/0/0/0 (2 new found+fixed: a STEP-pill contrast regression, an env-scrub
  over-strip). Full OS-level worker confinement accepted-with-rationale as a Stage-11 item.
  Merged to `main` (merge `f2fc2b8`) + tagged `stage-8`; gate green (ruff, 835 non-live + live
  OrcaSlicer + live CadQuery worker, 287 vitest, build reproducible). Package:
  `docs/audits/stage-8/audit-team-stage-8-2026-06-06/`. **Next: Stage 9 (image/sketch on-ramp).**
- 2026-06-06 (Phase B / backend stages 0-3): combined backend audit-team (eng/test/QA/docs; UI/UX
  n/a) across the coupled backend (pipeline, gate, slicer, connectors, printer coverage), findings
  tagged per stage → 0B/0C/~5Maj/~9Min/~6Nit. STANDOUT safety bug: ENG-001 — a NaN/inf bbox extent
  SILENTLY PASSED the dim + build-volume gates (IEEE NaN compares False); now fails closed via a
  finiteness check that runs first. Plus QA-301 (friendly UnknownConfigKey instead of a raw KeyError
  traceback; web 400 not 500), ENG-002/004/005 (zip-entry cap, honest orient stability, timeout
  align), QA-303 (no rec for an unavailable material), DOC-001/002/004/006 (baseline/help/Bambu/
  envelope honesty), TEST-001/003/004 + ENG-001/QA-301 regression tests. Accepted-with-rationale:
  QA-302/304/305, ENG-003, DOC nits. **ENG-006 surfaced to Scott** (physical build-volume VERIFY
  needs the real P2S/A1; mitigated by the Stage-5 sliceable-footprint cap). Re-audit CLEAN
  (false-green confirmed). Old root `audit-stage0-2026-05-29/` migrated into `docs/audits/stage-0/`.
  Gate green (ruff, geometry, 783 pytest, 284 vitest, build reproducible).
  **PHASE B COMPLETE — all owed audits (stages 0-7) backfilled. Next: Phase C (build Stages 8-11).**
- 2026-06-06 (Phase B / Stage 7): backfill audit of Smart Mesh readiness + PrintProof3D + learning
  store + the readiness card. 6 independent agents → 0B/0C/2Maj/~12Min/~3Nit (engineering-invariant
  pass itself 0 findings: gate stays slice authority, readiness advisory). Majors: UX-001 (warn
  confidence badge 4.23:1 < AA → darker --kc-warn-text + an automated contrast-guard test that fails
  the build on any tone-token AA regression), TEST-S7-101 (engine-returned-None honesty path test).
  Backend: ENG-702/703 (one PP severity table — no silent score dents; unknown gate status fails
  safe), QA-701 (no empty warn verdict), QA-703 (no flattering "On par"). a11y: UX-002/003/004.
  Docs: DOC-001..004. Re-audit CLEAN (false-green confirmed). Gate green (ruff, geometry, 778
  pytest, 284 vitest, build reproducible). Package: `docs/audits/stage-7/backfill-2026-06-05/`.
  **Phase B UI stages (4-7) all DONE; remaining: backend stages 0-3 (audit-team).**
- 2026-06-05 (Phase B / Stage 6): backfill audit of the model layer (advisor + fallback + bake-off
  + Settings model/cloud surface). 6 independent agents → 0B/1C/2Maj/6Min/3Nit (advisor-logic
  engineering pass itself 0/0/0/0/0). Real bug: a CRITICAL privacy-copy contradiction — the Settings
  AI-model card claimed "nothing leaves your computer" even when CLOUD was active; fixed by branching
  the copy on the live backend. Plus DOC-001 (README omitted OpenRouter), TEST-101 (cloud-key-leak
  guard test), QA-001 (short-key masking), QA-002 (405 for GET-only), DOC-003 (Qwen 3B/7B
  "deprioritized not bench-tested"), UX-003/004/005 minors. gemma4-top/Qwen-deprioritized design +
  one-model UI treated as correct-by-design (Scott's hard rule), not flagged. Re-audit CLEAN
  (Critical verified both ways live). Gate green (ruff, geometry, 773 pytest, 278 vitest, build
  reproducible). Package: `docs/audits/stage-6/backfill-2026-06-05/`.
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
