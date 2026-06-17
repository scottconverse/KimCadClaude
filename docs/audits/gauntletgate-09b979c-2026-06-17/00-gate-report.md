# GauntletGate report — KimCad — pre-installer release gate

**Date:** 2026-06-17 · **Build/commit:** `09b979c` (0.9.0b4 + cold-start managed-Ollama fix + audit-watchlist remediation) · **Run by:** Claude (gauntletgate `all`)
**Lanes run:** lite · walkthrough · full (5 roles) · **Lanes NOT run:** none
**How run / environment:** Lite inline; Walkthrough drove the real `kimcad web` on a constructed + **verified** first-run-clean state (Ollama ABSENT); Full = 5-role fan-out (`wf_dd439e07-fe6`), QA ran the authoritative real-tool end-to-end against the LIVE Ollama + real OrcaSlicer.

---

## Verdict (read first)

> **CLEAR TO ADVANCE** (post-remediation) — at commit `ad5aca7`. The gate's findings (1 Critical + 5 Major + minors, recorded below) were all driven to **0/0/0/0/0** and re-verified.

- **First-run:** reaches core feature ✅ — **coverage VALID** (isolation proven; the cold-start dead-end is fixed and verified live).
- **Severity roll-up — AS FOUND (on `09b979c`):** Blocker **0** · Critical **1** · Major **5** · Minor **~12** · Nit **~5**.
- **Severity roll-up — AFTER REMEDIATION (`ad5aca7`):** **0 / 0 / 0 / 0 / 0** actionable (the only "remaining" items are explicit no-action: a test-isolation note, the deliberate avatar/version-pin choices, and the genuine #11/admin-firewall dependencies on the watchlist).
- **Re-verification (committed `ad5aca7`):** ruff clean · **pytest 1679 passed** (live OrcaSlicer + the new real-ollama spawn/teardown + CadQuery sandbox) · **vitest 405 passed** · **SPA build-repro PASS**. One authoritative full-gate run **confirmed green end-to-end (`RERUN_GATE_EXIT=0`)** on this commit; the pre-push hook re-runs it at push as the backstop.
- **Why the gate earned its keep:** it caught a leaked background `ollama serve` on every cold-start machine — invisible on a dev box (system Ollama already running) — plus a missing disk-precheck on the headline flow, an incomplete narrative propagation, and a stated-dimension drop. None of these would have surfaced in a warm-box check; all are now fixed + tested.

Full remediation detail: [REMEDIATION-PLAN.md](REMEDIATION-PLAN.md) (Resolution section). The findings AS FOUND are preserved below for the record.

---

## Environment provisioning — verified (attestation)

| What | State used | How VERIFIED — not assumed |
|---|---|---|
| Profile / `USERPROFILE` / app-data isolation | fresh temp `…\kimcad-gate-coldhome` | App wrote `…\AppData\Local\KimCad\{config,output,ollama}` into the isolated path; `/api/settings` returned **defaults** (`cloud_enabled:false`, no connectors) — the real `~/.kimcad` (`cloud_enabled:true` + Bambu/OctoPrint) did **not** leak; real profile confirmed untouched after. |
| First-run flags | unset | Wizard auto-opened ("Welcome to KimCad"). |
| External dependency: **Ollama** | **ABSENT** (cold lane) / present v0.30.8 (warm lane) | Cold: `find_system_ollama()` returned None (PATH + `LOCALAPPDATA` both isolated) + dead-port `base_url` overlay → `/api/model-status` running:false. Warm (QA): live `:11434`, model-status running:true+model_present:true. |
| Data store | empty (cold) / real (warm) | `/api/settings` defaults cold; real profile warm. |
| Network | online | Real GitHub engine fetch streamed bytes (cold); real model generation (warm). |

**Isolation verified?** YES. **→ First-run coverage: VALID.**

---

## Lane results

### Lite — feeder
Ship-within-gate; 0/0/0/0/0. ruff clean + 101 targeted tests green (incl. `real_tool` fetch+serve). [01-lite.md](01-lite.md)

### Walkthrough — first-run authority
First-run **reaches core feature ✅ (VALID)**. Cold-start dead-end **fixed** (one-click "Set up KimCad's AI" fires the real fetch path live; engine row "setting up… 14%"). ENG-COLD-002/UX-COLD-003/005 verified fixed. Console clean. 0 Blocker / 0 Critical. [02-walkthrough.md](02-walkthrough.md)

### Full — 5-role adversarial deep audit
| Role | B | C | Maj | Min | Nit | Deep-dive |
|---|---|---|---|---|---|---|
| Principal Engineer | 0 | 1 | 2 | 3 | 2 | [01-engineering.md](01-engineering.md) |
| Senior UI/UX | 0 | 0 | 1 | 2 | 1 | [02b-uiux.md](02b-uiux.md) |
| Technical Writer | 0 | 0 | 1 | 2 | 1 | [03-writer.md](03-writer.md) |
| Test Engineer | 0 | 0 | 2 | 3 | 1 | [04-test.md](04-test.md) |
| QA Engineer (real-tool) | 0 | 1* | 1 | 2 | 1 | [05-qa.md](05-qa.md) |

\* QA-GG-001 corroborates ENG-GG-001 (same root cause — counted once in the dedup'd total).

**QA proved the core promise end-to-end on REAL tools:** live qwen2.5:7b plan → real OpenSCAD render → printability gate PASS → real OrcaSlicer `.3mf` (80 KB) with **10,445 G1 motion moves**, unzipped + inspected losslessly. Session-token guard, gate-failure slice refusal, 405/Allow + 413 hygiene all verified live.

---

## Blocking punch list (must clear to advance)

**Critical**
- **ENG-GG-001 / QA-GG-001** — Managed `ollama serve` child never torn down (orphan process; contradicts two docstrings). Capture the `Popen` only when KimCad started it (`source=="started"`); Windows Job Object `KILL_ON_JOB_CLOSE` + `atexit` terminate; wire `shell._on_closed` + `serve()` `finally`; never touch a reused system Ollama.

**Major**
- **DISK-PRECHECK (ENG-GG-002 = TEST-GG-002 = DOC-101)** — `start_setup` skips the disk pre-check; docs (12 GB) contradict the runtime threshold (15 GB) and the "8 GB" string. Hoist the pre-check into `_run_setup`; reconcile the three numbers to one honest story; add a doc-vs-code consistency test.
- **ENG-GG-003 = TEST-GG-006** — `PORTABLE_SIZE_BYTES` ~0.9 MB short → set exact `1_461_613_335`.
- **UX-FULL-001** — managed-Ollama narrative not propagated to Settings / design-status / chat wall (still "Start it / get Ollama"). Update `SettingsPanel.tsx`, `designStatus.ts`, `ChatPanel.tsx` + flip the stale-copy tests.
- **TEST-GG-001** — "real_tool integration test" claim overstates coverage (auto-test only hits the reuse branch). Correct the docstrings; add an Ollama-gated spawn-branch test; fix the verify script that printed `RESULT=FAIL`.
- **QA-GG-002** — stated dimensions silently dropped ("8 mm cable" → 6 mm clip). Strengthen plan→template dimension binding and/or surface a "defaulted" note when a stated dimension isn't bound.

## Next-stage watchlist (carried; genuine dependencies, not gate blockers)
- **#11** real-metal print send (no printer on the box). 
- Native-Winsock-bypass / OS-level FS confinement half of ENG-004/ENG-GG-004 (needs admin-level firewall / AppContainer).
- QA-GG-003 (first-design-after-boot mesh 404; observed once, not reproduced) — defensive look at the startup `rmtree` vs first-render timing.

## What's working (credited, specific)
- Core promise proven end-to-end on real tools (real `.3mf` with real motion).
- SHA-256 integrity pin verified against the live GitHub asset; hash-before-extract; zip-slip guarded.
- ENG-COLD-002 loopback-host classification: no bypass across 11 adversarial host forms.
- Per-boot session-token guard, server-side gate-failure refusal, 405/413 hygiene — all live-verified.
- Entire b4 UX watchlist closed; WCAG AA contrast passes in both themes; 1657 tests collected, no hidden skips/xfail.

---

## Sign-off checklist
- [x] Verdict matches lanes actually run (full `all`; honest DO NOT ADVANCE on the open Critical).
- [x] Environment attestation filled with verified facts; first-run reachability stated + verified.
- [x] All 5 role deep-dives on disk; cross-role findings deduped (orphan Critical, disk-precheck triple, size-constant pair).
- [x] Every Blocker/Critical has evidence, blast radius, fix path.
- [x] What's-working populated.
- [x] **Remediation to 0/0/0/0/0 + verdict re-emitted → CLEAR TO ADVANCE** at `ad5aca7` (ruff + pytest 1679 + vitest 405 + build-repro green; authoritative single full-gate run re-confirmed green, `RERUN_GATE_EXIT=0`).
