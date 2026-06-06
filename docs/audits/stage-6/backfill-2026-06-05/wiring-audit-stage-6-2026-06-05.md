# KimCad Stage 6 (Model Layer) — Playwright Interface Wiring Audit

> Audited 2026-06-05 · branch `stage-0-7-audit-backfill` · commit `6b60126` · auditor: Claude (audit-only mode)
> Scope: the model layer as surfaced in the UI — the Settings screen's **AI model** + **Cloud acceleration** sections, `GET /api/model-status`, `GET`/`POST /api/settings`.

## Executive Summary

**The Stage 6 model surface is genuinely wired, not cosmetic — with one real misleading-UI defect.** The Settings "AI model" status (badge, dot, label, model name) reflects the live `/api/model-status` response, which honestly probes real Ollama; the cloud opt-in persists server-side and survives a full reload; the OpenRouter key is stored and only ever returned masked (last 5); and the effective backend (`local` vs `cloud`) flips correctly when cloud is enabled with a key + model. I exercised every one of these end to end against the running demo on `127.0.0.1:8765` and confirmed each with a fired network request and a re-queried API response.

The one substantive finding (**H-1**): when the effective backend is **cloud**, the AI-model section's description still reads "**KimCad's local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer.**" — interpolated with the *cloud* model's name. The badge/dot correctly say "Cloud," but the body copy makes a false privacy assurance about a model that runs off-machine. That subtitle is a hardcoded string (`SettingsPanel.tsx:239-242`) that never switches on `model.backend`.

Two secondary observations: (M-1) `--demo` mode ("no LLM") does **not** apply to the model-status surface — it always probes real Ollama, so on a demo box without Ollama the Settings AI section tells the user to "start Ollama" even though demo design generation is LLM-free; and (M-2) the entire `model_advisor.recommend()` decision engine (hardware probe, catalog, tiers, non-China escape, upgrade hints, `friendly_label`) is built + unit-tested but has **no UI path** — only `probe_ollama` is imported by the webapp. M-2 is largely **by design** (the trust rule: the AI section is a gemma4 health readout, never a menu of alternatives) but the advisor's primary output is UI-dead and reachable only via the `kimcad doctor` CLI.

Verdict up front: **the model layer is honestly wired; fix the cloud privacy-copy bug (H-1) before ship.**

## Methodology

- **Reviewed:** `src/kimcad/model_advisor.py`, `src/kimcad/webapp.py` (`_handle_model_status` 1089-1132, `settings_response`/`_mask_key` 442-463, `_handle_settings_get/post` 1063-1196, `_active`/cloud routing 399-439, `serve`/`build_web_pipeline` 343-359/1868-1892, GET dispatch 823-840), `frontend/src/components/SettingsPanel.tsx`, `frontend/src/api.ts`, `useHashRoute.ts`, `App.tsx` (route → SettingsPanel), and the test suites (`tests/test_webapp.py`, `frontend/.../SettingsPanel.test.tsx`, `tests/test_model_advisor.py`).
- **App launch:** demo already running — `…\.venv\Scripts\python.exe -m kimcad.cli web --demo --port 8765` (PID 16116). Driven via Claude preview tools against preview serverId `72b81e3e-…` on port 8765. Real Ollama confirmed up at `:11434` with `gemma4:e4b` genuinely pulled (9.6 GB, Q4_K_M) plus `gemma4:e4b-it-q4_K_M`, `qwen2.5-coder:1.5b`, etc.
- **Tests run:** `pytest -k 'model_advisor or model_status or settings or advisor'` → **60 passed**. Frontend SettingsPanel suite reviewed statically.
- **Coverage:** Settings route (`#/settings`) fully exercised — AI model section (local Running state, Refresh button), Cloud acceleration (toggle on/off, key masked redisplay, model field, persistence across reload, backend flip to cloud). Adversarial: cloud-on-without-key (stays local), reload-persistence, backend-flip verification.
- **Artifacts:** evidence dir `docs/audits/stage-6/backfill-2026-06-05/wiring-evidence/` (network/eval transcripts inline below; screenshots captured during the run). **State restored to clean defaults** (cloud off, key/model cleared) at end.
- **Known limit honored:** preview_eval is isolated-world, so all decisive checks were re-verified via DOM reads + authoritative `fetch()` to the real API and via `preview_network`.

## Project Gestalt

KimCad is a local-first AI→3D-print web tool. The "model layer" the UI surfaces is a **health readout**, not a model chooser: `gemma4:e4b` is THE model (settled, non-negotiable). The Settings **AI model** card shows backend (Local/Cloud), a status dot, a label (Running / Not running / Model not pulled / Cloud / Checking… / Couldn't check), and the active model name, plus a concrete next action and a Refresh. **Cloud acceleration** is an opt-in OpenRouter fallback (off by default; user picks the model; key saved locally, shown masked). `GET /api/model-status` is the source of truth: cloud-enabled+key+model → reports `cloud`; otherwise probes Ollama and reports `running`/`model_present` for the local model. Demo mode is LLM-free for *design generation* only.

## Findings By Severity

### H-1 Cloud backend is described as "local… nothing leaves your computer"
- **Severity:** High
- **Location / route:** `#/settings` → "AI model" card
- **Element or workflow:** the card's description paragraph (`.kc-set-sub`)
- **What the user sees:** With cloud enabled + a saved key + model, the card shows badge **Cloud**, dot **Cloud**, model `some/model-v1`, and the description "**`some/model-v1` — KimCad's local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer.**"
- **What actually happens:** The effective backend is cloud (`/api/model-status` → `backend:"cloud"`); prompts are sent to OpenRouter, off-machine. The subtitle is a static string and never switches on backend.
- **What should happen:** When `model.backend === 'cloud'`, the copy must describe the cloud model honestly (runs in the cloud via OpenRouter, prompt leaves the machine) — not assert local/private operation. The "local AI / nothing leaves your computer" copy belongs to the local branch only.
- **Evidence:** `preview_eval` → `{backend:"cloud", model:"some/model-v1", badge:"Cloud", subtitle:"some/model-v1 — KimCad's local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer."}`; screenshot in evidence dir; source `frontend/src/components/SettingsPanel.tsx:239-242` (hardcoded subtitle, no backend branch).
- **Likely cause:** The subtitle was written for the local-only case and not revisited when MS-3 added the cloud effective-backend reporting to the same card.
- **Suggested fix:** Branch the subtitle on `model?.backend`: cloud → "Routed to `<model>` in the cloud via OpenRouter — your prompt leaves your machine for this request"; local → the existing text.
- **Suggested test coverage:** A SettingsPanel test that mounts with `getModelStatus → {backend:'cloud', model:'x/y'}` and asserts the description does NOT contain "nothing leaves your computer" / "local AI" and DOES name the cloud routing.

### M-1 `--demo` ("no LLM") does not apply to the model-status surface
- **Severity:** Medium
- **Location / route:** `#/settings` → "AI model"; `GET /api/model-status`
- **Element or workflow:** model-status under demo mode
- **What the user sees:** On this box (Ollama up, gemma4 pulled) the demo correctly shows "Running" — honest. But on a demo box *without* Ollama, the same demo would show "Ollama isn't running. Start it…" while design generation works LLM-free via `DemoProvider`.
- **What actually happens:** `serve()` threads `demo` only into `build_web_pipeline` (the design provider). `make_handler` never receives `demo`; `_handle_model_status` always calls `cfg.llm_backend()` + `probe_ollama` (webapp.py:1880, 1116-1118). So the AI status is live regardless of demo.
- **What should happen:** Either honestly indicate in demo mode that the AI section reflects the real machine (not the demo), or surface a "demo (no LLM)" state so the readout doesn't tell a demo user to start a server the demo doesn't need.
- **Evidence:** `serve` passes `demo` only to `build_web_pipeline` (webapp.py:1880); handler dispatch has no demo branch for `/api/model-status` (823-840, 1089-1132); demo banner copy "(demo mode — no LLM)" (webapp.py:1883). Live `--demo` server returned real `running:true,model_present:true`.
- **Likely cause:** Demo was scoped to the design pipeline; the Settings health readout was added later and intentionally always-live.
- **Suggested fix:** Low-effort — accept as documented behavior, or add a demo-aware note in the AI card. Not a blocker on a box with Ollama.
- **Suggested test coverage:** A webapp test asserting model-status behavior is independent of the `demo` flag (documents the intent), or, if changed, a demo-mode status assertion.

### M-2 `model_advisor.recommend()` engine has no UI path (CLI-only)
- **Severity:** Medium
- **Location / route:** Settings AI section / `model_advisor.py`
- **Element or workflow:** the hardware-aware recommendation engine
- **What the user sees:** The AI card shows only the fixed gemma4:e4b health readout (correct per trust rule — never a menu of alternatives).
- **What actually happens:** webapp.py imports **only** `probe_ollama` from `model_advisor` (webapp.py:1116). `recommend`, `probe_hardware`, `HardwareProfile`, `friendly_label`, `MODEL_CATALOG`, `Recommendation`, the tier/origin/non-China-escape/upgrade logic are reachable only via `kimcad doctor` (cli.py:384-419) — no web/UI surface.
- **What should happen:** This is **largely by design** (gemma4 is THE model; the UI must not offer alternatives). Flag for awareness: the module's primary output is UI-dead; if any of the advisor's *advisory value* (e.g. an "your machine could run a bigger local model" hint, or `friendly_label` for a non-default pulled tag) is ever intended for the app, it is currently unsurfaced.
- **Evidence:** Grep — webapp imports only `probe_ollama`; `recommend`/`probe_hardware`/`friendly_label` referenced only in `cli.py`. `model_advisor.py:99-124` (catalog/tiers/Qwen-deprioritization) all CLI-path only.
- **Likely cause:** Intentional separation of the doctor CLI (advisory) from the app (fixed model). Correct by design; recorded as a capability-not-surfaced note, not a defect.
- **Suggested fix:** None required for ship. Optionally document that `recommend()` is the `kimcad doctor` engine, not a UI feature.
- **Suggested test coverage:** None needed; `test_model_advisor.py` (60 tests) covers the engine.

### L-1 No frontend test asserts the AI-model description copy
- **Severity:** Low
- **Location / route:** `frontend/src/components/SettingsPanel.test.tsx`
- **Element or workflow:** AI model card body copy
- **What the user sees / actually happens:** The SettingsPanel suite asserts the status *labels* (Running / Not running / Model not pulled / Couldn't check) and cloud *controls*, but never the description paragraph — so H-1 (the cloud privacy-claim bug) shipped with zero guarding test.
- **What should happen:** A copy assertion tied to backend.
- **Evidence:** No match for "local AI"/"nothing leaves"/subtitle in `SettingsPanel.test.tsx` (grep); tests at lines 94-132 cover labels + controls only.
- **Likely cause:** Tests focused on state machine, not body copy.
- **Suggested fix / test:** see H-1's suggested test.

## Missing Or Partial Features

- **Cloud-backend description copy** — implemented but **broken** (H-1): the cloud effective-backend is reported, but the card's prose is the local copy.
- **Hardware-aware model recommendation / upgrade hint / `friendly_label`** — present in code, **missing from the UI** (M-2), by design (CLI-only via `kimcad doctor`).
- All other promised model-layer surfaces (status states, cloud opt-in, masked key, persistence, refresh) — **implemented and working**.

## Backend Or System Capabilities Not Surfaced

- `model_advisor.recommend()` + `probe_hardware()` + `MODEL_CATALOG` (tiers, origin, non-China escape, upgrade suggestion) + `friendly_label()` — full engine, **no UI path** (M-2). Reachable only via `kimcad doctor`.
- `/api/model-status` distinguishes "not running" vs "running but model absent" (the `probe_ollama` two-tuple); both states are wired into the UI's action copy (SettingsPanel.tsx:244-256) — **surfaced correctly** (noted as a positive).

## Confusing Or Misleading UI

- **H-1** is the headline: a cloud model described as local + private. Actively misleading on a privacy claim.
- Minor: the AI card's "Local"/"Cloud" badge and the right-side status both read "Cloud" when cloud is active (badge + dot label duplicate the word) — harmless but slightly redundant.

## Broken Or Suspicious Wiring Map

| UI element or workflow | Expected system connection | Actual connection | Status | Evidence |
| --- | --- | --- | --- | --- |
| AI model status (badge/dot/label/name) | `GET /api/model-status` → real Ollama probe | Reflects live response exactly (Local/Running/gemma4:e4b) | Working | snapshot; `preview_network 19664.49/.71`; `_handle_model_status` 1089-1132 |
| AI model description copy | switch text on `backend` (local vs cloud) | Hardcoded local copy regardless of backend | **Broken** | H-1; `SettingsPanel.tsx:239-242` |
| Refresh / "check again" button | re-fire `GET /api/model-status` | Fires it (`checkModel`) | Working | `preview_network 19664.99` after Refresh click |
| Cloud opt-in toggle | `POST /api/settings {cloud_enabled}` → persist | POSTs, persists, survives reload | Working | `19664.51` POST; reload showed switch still on; `_handle_settings_post` 1168-1169 |
| Cloud change re-checks model | POST settings → then GET model-status | Both fire in sequence | Working | `19664.51`→`.52`, `.57`→`.58`; `SettingsPanel.tsx:98-99` |
| Cloud effective-backend flip | enabled+key+model → backend:"cloud" | Flips to cloud, names the model | Working | `preview_eval` → `{backend:"cloud", model:"some/model-v1"}`; webapp 1100-1102 |
| OpenRouter key storage | save full, redisplay masked, never echo | Masked `••••…WXY99`; full never returned | Working | `/api/settings` resp `cloud_key_masked`; `_mask_key` 442-450; test_webapp 2238 |
| Cloud enabled but no key/model | must stay LOCAL | backend stays `local` | Working (correct) | `preview_eval` (cloud_enabled:true, no key) → `backend:"local"`; webapp 1100 |
| model-status under `--demo` | (LLM-free demo) | Always probes real Ollama; demo flag not applied | Suspicious-by-design | M-1; `serve` 1880; banner 1883 |
| `recommend()` engine | (no UI promise) | No UI import; CLI-only | Missing (by design) | M-2; grep webapp imports only `probe_ollama` |

## Test Assessment

**Backend coverage is strong.** `tests/test_webapp.py` covers all five model-status states + guards: local-running-with-model (2097), quantized-variant match (2112), ollama-down→not-running (2125), running-but-absent (2137), cloud-backend→cloud + must-not-probe-Ollama (2151), cloud-never-returns-the-key (2238), and the end-to-end cloud flip after a settings POST (2416-2418). `test_model_advisor.py` covers the pure `recommend()` engine (60 tests passing). Frontend `SettingsPanel.test.tsx` covers status labels (Running/Not running/Model not pulled/Couldn't check), Refresh, and the cloud controls (toggle, masked key + Replace, model-on-blur).

**The gap that let H-1 through:** no test — frontend or backend — asserts the AI card's **description copy** against the backend. The state machine is tested; the prose is not.

**Highest-value tests (ranked):**
1. (catches **H-1**, High) SettingsPanel test: `getModelStatus → {backend:'cloud', model:'x/y'}` ⇒ description does NOT contain "nothing leaves your computer"/"local AI" and DOES name cloud/OpenRouter routing. **Frontend/component.**
2. (catches **M-1**, Medium) webapp test asserting `/api/model-status` is unaffected by `demo=True` (pins the intent), or a demo-aware status if changed. **API.**
3. (L-1) generalize #1 to assert the local-branch copy is shown when `backend:'local'`. **Component.**

## Recommended Repair Plan

1. **Immediate blockers:** none (app is usable; H-1 is misleading, not breaking).
2. **Core wiring fixes:** **H-1** — branch the AI-card subtitle on `model.backend`; never show "local / nothing leaves your computer" for a cloud backend.
3. **Feature completion:** **M-1** — decide demo-mode behavior for the AI status (document as-is, or add a demo-aware note).
4. **UI/UX cleanup:** optional — de-duplicate the "Cloud" badge + status label.
5. **Test coverage:** add tests #1-#3 above (lock H-1 first).

## Confidence And Gaps

- **Fully audited (end to end, with evidence):** Settings AI model status (local Running state, model name, Refresh re-fire); cloud opt-in toggle + POST persistence across full reload; OpenRouter key masked redisplay; effective-backend flip to cloud and back; cloud-enabled-without-key stays local. All confirmed via fired network requests + authoritative API re-queries + DOM reads.
- **Partially audited:** the "Not running" and "Model not pulled" *action* branches were verified by code path + backend tests, but not driven live (real Ollama is up on this box; I did not stop it). The branch conditions are honestly reachable.
- **Unreachable:** a live "not running"/"model not pulled" UI state (would require stopping Ollama or removing gemma4 — out of audit scope, not safe to do to the user's machine).
- **Unverified:** OpenRouter cloud *reachability* end-to-end (the status reports cloud as "ready" when configured without probing; this is documented behavior, webapp.py:1128-1131, and a real key was not used).

## Appendix

- **Commands:** `git -C C:\Users\scott\dev\kimcad rev-parse HEAD` → `6b60126`; `pytest -k 'model_advisor or model_status or settings or advisor'` → 60 passed; demo already running via `…\.venv\Scripts\python.exe -m kimcad.cli web --demo --port 8765`.
- **Real Ollama state:** `gemma4:e4b` (9.6 GB Q4_K_M), `gemma4:e4b-it-q4_K_M`, `qwen2.5-coder:1.5b`, `nomic-embed-text`, a deepseek-coder — confirmed via `GET :11434/api/tags`.
- **Key network evidence:** `19664.49/.71/.99` GET /api/model-status; `19664.51/.57` POST /api/settings; `.52/.58` follow-up model-status (cloud-change re-check).
- **Key eval evidence:** cloud-on+key+model → `{backend:"cloud", model:"some/model-v1", running:true, model_present:true}`; H-1 → subtitle "…local AI… nothing leaves your computer" while `backend:"cloud"`.
- **State restored** to clean defaults at audit end (cloud off, key/model cleared, experimental off, backend local/gemma4:e4b).
- **Note on repo location:** the live kimcad repo is `C:\Users\scott\dev\kimcad` (user-profile dev), not `C:\dev\…`.
