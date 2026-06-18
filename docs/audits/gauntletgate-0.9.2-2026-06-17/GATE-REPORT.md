# GauntletGate — KimCad 0.9.2 — Gate Report

**Date:** 2026-06-17 · **Build/commit:** e91b148 (version sweep; fixes from 9ddea46) · **Run by:** Claude Sonnet 4.6
**Lanes run:** all (lite + walkthrough + full) · **Lanes NOT run:** none

---

## Verdict (pre-remediation)

> **⛔ DO NOT ADVANCE** — 1 Critical found (TE-001). Remediation in progress immediately after this report.

- **First-run:** NOT VERIFIED (walkthrough env, provisioned) — **first-run coverage: VALID via carry-forward** (0.9.1 attestation VALID, QA role confirmed UNCHANGED for 0.9.2)
- **Severity roll-up (all lanes):** Blocker 0 · Critical 1 · Major 3 · Minor 8 · Nit 7
- **One-line why:** Both 0.9.2 fixes are correct in code; Critical is a test gap (codegen-phase model-down path doesn't assert the new vocabulary); Majors include bespoke secret-filter in _child_env and three stale-doc locations that still say models land in Ollama's global store.

---

## Environment provisioning — attestation

| What | State used | How VERIFIED |
|---|---|---|
| Profile isolation | USERPROFILE → walk9-home (dev mode) | Dev mode: writable_root() → repo root, not LOCALAPPDATA. Isolation NOT effective for data paths. |
| First-run flags | UNKNOWN (localStorage) | Not verified in walkthrough — dev mode with provisioned Ollama |
| External dependency: Ollama | **PRESENT v0.30.8 running** | /api/model-status → running: true; model_present: true |
| Data store | Repo output/ (dev mode) | paths.py:57-62 confirmed dev mode → repo root |
| Network | Online | Standard dev environment |

**Isolation verified?** NO · **First-run coverage:** VALID via carry-forward (QA role verified 0.9.2 diff doesn't touch first-run code; 0.9.1 attestation from directive-007 remains valid)

**Evidence artifacts:** `artifacts/api-health.json`, `artifacts/api-model-status.json`, `artifacts/about-section.txt`

---

## Lane results

### Lite
No Blockers/Criticals. Both Minors confirmed in source + staging. Gate: 1679/405/build-repro green.

### Walkthrough  
Version confirmed: API + UI both show v0.9.2. Design pipeline triggers. Settings all functional. Both Minors verified statically. One Nit found (Settings About nav closes panel). Full details: `WALKTHROUGH.md`.

### Full (5 roles)
QA first-run delta: **UNCHANGED**. Deep-dives: `01-engineering.md` … `05-qa-engineer.md`.

**Per-role roll-up:**

| Role | Blocker | Critical | Major | Minor | Nit |
|------|---------|----------|-------|-------|-----|
| Principal Engineer | 0 | 0 | 1 | 2 | 2 |
| UI/UX Designer | 0 | 0 | 0 | 1 | 2 |
| Technical Writer | 0 | 0 | 2 | 1 | 1 |
| Test Engineer | 0 | 1 | 2 | 2 | 1 |
| QA Engineer | 0 | 0 | 0 | 1 | 1 |
| **TOTAL** | **0** | **1** | **3** | **8** | **7** |

---

## Blocking punch list (must clear to advance)

### TE-001 · Critical · Test gap — codegen-down test missing "engine" guard
`tests/test_webapp.py:3695` — `test_design_with_model_down_during_codegen_is_recoverable` asserts `d["status"] == "model_unavailable"` but NOT `"engine" in d["error"]`. A vocabulary regression on this path would pass silently.
**Fix:** Add `assert "engine" in d["error"]` to line 3695. (1 line) **Size: S**

---

## Next-stage watchlist

### ENG-001 · Major · _child_env() uses bespoke _SECRETISH instead of canonical subprocess_env.is_secret_env()
`ollama_runtime.py:140,145` — misses `AUTH`, `PASSPHRASE`, `PASSWD` patterns. OpenSCAD/CadQuery already use the canonical scrub.
**Fix:** Replace `_SECRETISH` filter with `from kimcad.subprocess_env import is_secret_env`.

### TW-001 · Major · Three docs still say models land in Ollama's global store
`README.md:35`, `docs/install-guide.md:61-63`, `docs/troubleshooting.md:98-99` — contradicts the Minor-2 fix.
**Fix:** Update all three to say `%LOCALAPPDATA%\KimCad\models`.

### TW-002 · Major · USER-MANUAL.md version banner says 0.9.1
`docs/USER-MANUAL.md:15` — version not bumped with the rest.
**Fix:** Change `0.9.1` → `0.9.2`.

### TE-003 · Major · No "Ollama not in error" exclusion guard on MODEL_UNAVAILABLE_MESSAGE tests
`tests/test_webapp.py:1438,3661,3731` — a "Ollama engine isn't running" future edit would pass.
**Fix:** Add `assert "Ollama" not in d["error"]` to all three.

### ENG-003 · Minor · cli.py error handler says "Start Ollama" immediately after MODEL_UNAVAILABLE_MESSAGE
`cli.py:634-637` — the clean message is followed by "Start Ollama, pull the model ... (ollama pull ...)".
**Fix:** Replace with managed-engine vocabulary.

### UIUX-MIN-001 · Minor · ModelHealthPill shows "ollama pull" to all users
`ModelHealthPill.tsx:37,39` — parenthetical "(or run 'ollama pull ...')" on main canvas.
**Fix:** Remove the parentheticals.

### QA-MIN-001 · Minor · FirstRunWizard step 1 says "(Already have Ollama?)"
`FirstRunWizard.tsx:360` — visible on first-run when engine not running.
**Fix:** Reword to hide implementation detail.

### QA-MIN-002 · Minor · model_pull.py engine start-failure error says "install Ollama from ollama.com"
`model_pull.py:286-289` — shown in wizard pull-progress row on engine launch failure.
**Fix:** Replace with product vocabulary.

### ENG-002 · Minor · _free_gb_on_receiving_drive() reads OLLAMA_MODELS from parent env
`model_pull.py:75` — disk pre-check falls back to home-dir on cold-start (OLLAMA_MODELS is set in child env, not parent).
**Fix:** Pass `writable_root() / "models"` as probe_dir from call sites in managed-engine path.

### TE-004 · Minor · No test binds body["error"] to MODEL_UNAVAILABLE_MESSAGE constant directly
**Fix:** Add `from kimcad.pipeline import MODEL_UNAVAILABLE_MESSAGE; assert body["error"] == MODEL_UNAVAILABLE_MESSAGE` to one test.

### TE-005 · Minor · CLI model-down path has no vocabulary test
**Fix:** Add a CLI test asserting MODEL_UNAVAILABLE_MESSAGE text in stderr and "Ollama" absent.

### ENG-005 · Nit · VisionModelMissing error says "ollama pull" in browser
`llm_provider.py:65-66` — shown in UI when vision model not installed.
**Fix:** "Use Settings > AI setup to download it."

### UIUX-NIT-001 · Nit · "engine" vs "local AI" vocabulary drift
`pipeline.py:203` says "engine", Settings says "local AI". Align to "local AI".

### UIUX-NIT-002 · Nit · Settings About nav link closes panel
`SettingsPanel.tsx:244` — hash href triggers SPA router. Use scrollIntoView.

### TW-003 · Minor · CHANGELOG paraphrased quote doesn't match literal message
**Fix:** Use the exact MODEL_UNAVAILABLE_MESSAGE text.

### TW-004 · Nit · ARCHITECTURE.md missing ollama_runtime.py module entry
**Fix:** Add module entry with _child_env()/OLLAMA_MODELS description.

### ENG-004 · Nit · Internal comments in pipeline.py still use "Ollama"
Dev-only, not user-visible. Low priority.

### TE-006 · Nit · designStatus.test.ts fixture uses hardwritten string not real constant
Low priority; acceptable for frontend branching tests.

### QA-NIT-001 · Nit · ModelHealthPill "ollama pull" (same as UIUX-MIN-001)
Covered by UIUX-MIN-001 fix.

---

## What's working (credited, specific)

- **Both 0.9.2 fixes are architecturally correct.** `MODEL_UNAVAILABLE_MESSAGE` is defined once, imported cleanly, flows through the right exception handler in webapp.py, reaches the frontend verbatim. `_child_env()` is the sole managed-Ollama spawn path; `OLLAMA_MODELS` pinning is correct and uninstaller-consistent.
- **First-run is UNCHANGED.** QA confirmed: MODEL_UNAVAILABLE_MESSAGE is only reachable post-first-run (during a design request); _child_env() change in wizard path is purely beneficial. 0.9.1 clean-machine attestation carries forward.
- **Test coverage for the two fixes is real-process.** The 1679/405/build-repro gate uses the real webapp handler, not HTTP mocks. The subprocess test for OLLAMA_MODELS inspects the actual child env dict.
- **Ollama brand elimination is nearly complete.** Every user-visible surface has been audited; only 5 remaining strings mention "ollama" to users (all pre-existing, none introduced by 0.9.2).
- **Version consistency is enforced by test.** All 8 version surfaces verified by test_version_single_source.py.

---

## Sign-off checklist

- [x] Verdict matches lanes actually run (all three lanes ran)
- [x] Environment attestation filled; first-run coverage VALID via carry-forward with documented reason
- [x] QA role confirmed first-run delta: UNCHANGED
- [x] All 5 roles ran; deep-dives written to disk at 01..05
- [x] Every Blocker/Critical has evidence, blast radius, fix path
- [x] What's-working present and specific
- [x] Remediation complete → re-verify → post-remediation verdict update

---

## Post-remediation verdict (2026-06-17)

> **✅ CLEAR TO ADVANCE** — All 19 findings (0 Blocker · 0 Critical · 0 Major · 0 Minor · 0 Nit) driven to zero.

### Remediation summary

| ID | Severity | Fix |
|---|---|---|
| TE-001 | Critical | `test_webapp.py:3695` — added `isn't running` + `Ollama not in` to codegen-drop test |
| TE-003 | Major | Added `Ollama not in d["error"]` guards to all 4 webapp model-down assertions |
| ENG-001 | Major | `ollama_runtime._child_env` — removed bespoke `_SECRETISH`; canonical `is_secret_env()` from `subprocess_env` |
| TW-001 | Major | `README.md:35`, `install-guide.md:62`, `troubleshooting.md:99` — corrected model store path to `%LOCALAPPDATA%\KimCad\models` |
| TE-002 | Major | `test_model_pull.py` — added `test_free_gb_probes_writable_root_in_installed_mode` with monkeypatched `KIMCAD_INSTALL_ROOT` |
| ENG-003 | Minor | `cli.py:633-640` — replaced "Start Ollama, pull the model..." with `MODEL_UNAVAILABLE_MESSAGE` + `kimcad serve` |
| UIUX-MIN-001 | Minor | `ModelHealthPill.tsx` — removed "ollama pull" parentheticals; updated test |
| QA-MIN-001 | Minor | `FirstRunWizard.tsx:360` — "Already have Ollama?" → "Already have a local AI engine?" |
| QA-MIN-002 | Minor | `model_pull.py:286-289` — engine start-failure error no longer mentions "Ollama" |
| ENG-002 | Minor | `model_pull._free_gb_on_receiving_drive` — in installed mode uses `writable_root()/"models"` not `OLLAMA_MODELS` from parent env |
| TW-002 | Minor | `USER-MANUAL.md:15` — version banner updated from `0.9.1` to `0.9.2` |
| TW-003 | Minor | `CHANGELOG.md` — exact `MODEL_UNAVAILABLE_MESSAGE` text (was a paraphrase) |
| ENG-005 | Nit | `llm_provider.py:65-66` `VisionModelMissing` — replaced "ollama pull {model}" with Settings recovery copy |
| UIUX-NIT-001 | Nit | `pipeline.py MODEL_UNAVAILABLE_MESSAGE` — "engine isn't running" → "it isn't running" |
| UIUX-NIT-002 | Nit | `SettingsPanel.tsx` nav links — `onClick` + `scrollIntoView` prevents hash change dismissing Settings |
| ENG-004 | Nit | `pipeline.py:179,209` — removed "Ollama" from dev comments |
| TW-004 | Nit | `ARCHITECTURE.md` — added `ollama_runtime.py` module entry |
| TE-004 | Nit | `test_webapp.py` — added exact `MODEL_UNAVAILABLE_MESSAGE` constant binding |
| TE-005 | Nit | `test_first_run_errors.py:203` — updated CLI model-down test to match new vocabulary |
| TE-006 | Nit | `designStatus.test.ts` — added comment explaining intentionally synthetic fixture |

**Gate verification:** pytest 1680+ passed (0 failed), vitest 405/405 passed, SPA rebuilt clean. Installer rebuild pending push.
