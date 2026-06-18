# GauntletGate Walkthrough — KimCad 0.9.2

**Date:** 2026-06-17 · **Build/commit:** e91b148 (version sweep; fixes from 9ddea46) · **Run by:** Claude Sonnet 4.6
**Lanes run:** lite, walkthrough · **Lanes NOT run:** full (in progress — dispatched immediately after this report)
**How run / environment:** dev server at port 8714 via `.claude/launch.json` `kimcad-web-real` config; USERPROFILE redirected to `C:\Users\scott\AppData\Local\Temp\kimcad-walk9-home`

---

## Verdict (this lane)

> **⚠️ PARTIAL CHECK** — lanes run: `lite, walkthrough`. This is NOT an advancement gate. Full lane dispatched concurrently; combined verdict will follow.

- **First-run:** NOT VERIFIED — first-run coverage: **INVALID** (see attestation below)
- **Severity roll-up (walkthrough):** Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 1
- **One-line why:** Both 0.9.2 Minor fixes confirmed statically + test-backed; live engine-down and OLLAMA_MODELS paths cannot be exercised on this provisioned box (system Ollama running, dev mode). First-run attestation invalid due to environment limitations, not product defect.

---

## Environment provisioning — attestation

| What | State used | How VERIFIED — not assumed |
|---|---|---|
| Profile / USERPROFILE isolation | `C:\Users\scott\AppData\Local\Temp\kimcad-walk9-home` | `launch.json` sets env var — **but app runs in dev mode (no `KIMCAD_INSTALL_ROOT`), so `writable_root()` returns repo root, NOT LOCALAPPDATA. USERPROFILE redirect does not affect dev-mode data paths.** |
| First-run flags (`kc-first-run-done`) | UNKNOWN | Stored in browser localStorage (per-origin); no localStorage check performed |
| External dependency: Ollama | **PRESENT — v0.30.8 running** on port 11434 | `ollama list` visible in system; `/api/model-status` returned `running: true` |
| Data store (design output) | Repo `output/` dir in dev mode | Dev mode `writable_root()` → repo root (confirmed `paths.py:57-62`) |
| Network | Online | Standard dev environment |

**Isolation verified?** NO — LOCALAPPDATA not redirected; dev-mode data paths unaffected by USERPROFILE override.
**First-run coverage: INVALID.**

**Why this doesn't block the combined verdict:** The 0.9.2 change surface is strictly `pipeline.py` (error message wording) and `ollama_runtime.py` (`_child_env()` OLLAMA_MODELS pin). Neither touches the first-run/onboarding/wizard code path. The 0.9.1 gate (CLEAR TO ADVANCE, 2026-06-17 earlier session) produced a VALID first-run attestation with Ollama ABSENT, confirmed by directive-007 tester on a clean machine. The Full lane's QA role will assess first-run coverage delta.

**Evidence artifacts:** `artifacts/api-health.json`, `artifacts/api-model-status.json`, `artifacts/about-section.txt`

---

## Lane results

### Lite lane

**Scope:** source-level review of the two 0.9.2 Minor fixes (9ddea46).

**Minor-1 — `MODEL_UNAVAILABLE_MESSAGE` (pipeline.py:202-205):**
```
"KimCad couldn't reach your local AI — the engine isn't running. You can restart it from Settings, then try again."
```
- "Ollama" not present ✓
- "engine isn't running" is the key phrase ✓
- Confirmed in dist/staging/site-packages/kimcad/pipeline.py (installer staging) ✓
- Data flow: `webapp.py:1999-2001` → `{"status": "model_unavailable", "error": MODEL_UNAVAILABLE_MESSAGE}` ✓
- Frontend renders `body.error` string directly in the chat UI ✓
- Test coverage: test_webapp.py:1438,3661,3731 all assert `"engine" in body["error"]`; gate PASSED ✓

**Minor-2 — `_child_env()` OLLAMA_MODELS (ollama_runtime.py:150):**
```python
run_env["OLLAMA_MODELS"] = str(writable_root() / "models")
```
- Confirmed in dist/staging/site-packages/kimcad/ollama_runtime.py ✓
- Resolves to `%LOCALAPPDATA%\KimCad\models` (installed mode) ✓
- Test coverage: test_ollama_runtime.py:96-99 asserts `OLLAMA_MODELS == str(writable_root() / "models")`; gate PASSED ✓

**Lite verdict:** No Blockers/Criticals. Both Minors confirmed fixed in the 0.9.2 installer staging. Full gate: 1679/405/build-repro green. No escalation.

---

### Walkthrough lane

**Version confirmation:**
- `/api/health` → `{"version": "0.9.2", "cadquery": true, "openscad": true, "orcaslicer": true}` ✓
- In-app About section → `v0.9.2 · open-source (Apache-2.0)` ✓ (verified by scrollIntoView + DOM extraction)

**Design pipeline trigger:**
- Prompt entered: "a simple cable clip for a 6 mm cable"
- Pipeline started: "Designing your part..." + "Planning the shape" stage active ✓
- Spinner and step progress dots rendered correctly ✓
- "This runs on your computer's AI — it can take a few minutes. Nothing leaves your machine." copy present ✓
- Cancel button functional ✓
- Workspace layout correct: CONVERSATION left / design preview center / Parameters-Quality-Export tabs right ✓

**Settings panel:**
- Printer & material: Bambu Lab P2S default, PLA material ✓
- Display: mm/in toggle, Light/Dark/System appearance ✓
- AI model: "Local · Running" — qwen2.5:7b + qwen2.5vl:3b downloaded ✓
- Cloud acceleration: Off (correct default) ✓
- Experimental: Off (correct default) ✓
- Printer connections: Octoprint not configured, Bambu A1 fields visible ✓
- Editable CAD (.STEP): Installed ✓
- Tools — OpenSCAD: Installed ✓; OrcaSlicer: Installed ✓

**Minor-1 live verification:**
- CANNOT exercise (system Ollama running; engine-unreachable path not triggered)
- Static + test-backed evidence sufficient (see Lite lane above)

**Minor-2 live verification:**
- CANNOT exercise (system Ollama reused; `_child_env()` not called; dev mode → `writable_root()` → repo root, not LOCALAPPDATA)
- Static + test-backed evidence sufficient (see Lite lane above)

---

## Findings

### WLK-NIT-001 · Nit: Settings "About & reset" nav link closes the panel

**Route/screen:** Settings panel, left nav
**Element:** `<a href="#set-about">About & reset</a>`
**Expected:** Clicking "About & reset" in the Settings sidebar scrolls Settings content to the About section
**Actual:** Clicking the link changes the URL hash to `#set-about`, which triggers the SPA router and dismisses the Settings panel entirely
**Evidence:** `aboutLink.href` = `http://localhost:8714/#set-about`; clicking it navigated back to the landing page
**Cause:** The hash-based anchor conflicts with SPA hash routing — a `hashchange` listener in the router interprets `#set-about` as a route transition
**Fix:** Either use `href="#"` + `e.preventDefault()` + `scrollIntoView()` in an onClick handler, or change the Settings nav to use smooth-scroll anchors instead of hash hrefs
**Severity:** Nit — the About section is reachable by scrolling; there's no dead-end; one-time click-path workaround is trivial

---

## Readiness-by-area table

| Area | Status | Notes |
|---|---|---|
| App launch / version | ✅ | 0.9.2 confirmed API + UI |
| Design pipeline trigger | ✅ | Pipeline starts, planning stage active |
| AI model status | ✅ | Local · Running, both models present |
| Settings sections | ✅ | All sections present and functional |
| Tools (OpenSCAD, OrcaSlicer) | ✅ | Both Installed |
| Minor-1 fix (engine-down message) | ✅ static+tests | Cannot exercise live on this box |
| Minor-2 fix (OLLAMA_MODELS pin) | ✅ static+tests | Cannot exercise live on this box |
| First-run (Ollama ABSENT) | NOT VERIFIED | Provisioned box; VALID on 0.9.1 (unchanged in 0.9.2) |
| Settings About nav link | ⚠️ Nit | Hash-href closes panel instead of scrolling |

---

## What's working (credited, specific)

- Version consistency: API, in-app About, CHANGELOG, pyproject.toml, package.json, docs, README all show 0.9.2 ✓
- The Minor-1 fix is exactly right: "engine isn't running" is product-vocabulary (not "Ollama"); the recovery CTA points to Settings
- The Minor-2 fix correctly uses `writable_root() / "models"` — it will track the app's own data dir regardless of install-time LOCALAPPDATA value, and is covered by the existing uninstaller scope
- Gate hygiene: 1679/405/build-repro all green; version-single-source test enforces the one-location rule
- The workspace UI is clean: no console errors during session

---

## Sign-off checklist

- [x] Verdict matches lanes actually run (PARTIAL CHECK — full lane in progress)
- [x] Environment attestation filled; INVALID clearly stated with reason
- [x] First-run not-verified rationale given; delta from 0.9.1 documented
- [x] Every finding has evidence, dimension, and fix path
- [x] What's-working present and specific
- [ ] Full lane results — in progress
