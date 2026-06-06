# Audit Lite — Stage 8.5 Slice 6 MS-2: AI model status
**Date:** 2026-06-04
**Scope:** Surface A of the Settings screen — `probe_ollama` (`model_advisor.py`), the `GET /api/model-status` endpoint (`webapp.py`), and the AI-model section in `SettingsPanel.tsx` (a health readout for gemma4:e4b, no model menu), plus tests.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after two small fixes (applied + re-verified). Trust rule 1 holds: gemma4:e4b is shown as THE model with its health, with no dropdown of alternatives and no Chinese model anywhere in the UI. The probe is bounded (3s) and never raises; the endpoint never 500s; the status is honest and every non-running state gives a concrete next action. One Nit (a slightly-loose tag match) and one Minor (the cloud-branch endpoint test gap), both fixed.

## Severity rollup
**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 1 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: the cloud-backend status branch has no test
**Dimension:** Tests
**Evidence:** `webapp.py` `_handle_model_status` has a cloud branch (`is_local` false → `running:true, model_present:true, backend:"cloud"`, no Ollama probe), but the shipped config's active backend is `local`, so every MS-2 test exercises only the local path. The cloud branch — which MS-3 will lean on — is untested.
**Why it matters:** A regression that probed Ollama for a cloud backend (wrong) or flipped the backend label would pass. The cloud path is about to carry real weight in MS-3.
**Fix path:** Add a webapp test that monkeypatches `Config.llm_backend` to a cloud backend (deepseek/openrouter base_url) and asserts `backend=="cloud"`, `running:true`, the right model, and that no Ollama probe ran.
**Status:** ✅ Fixed — `test_model_status_cloud_backend_reports_cloud` added (monkeypatches the active backend to a deepseek cloud backend) → `backend:"cloud"`, `running:true`, `model:"deepseek-v4-flash"`.

### FOUND-002 Nit: `model_present` match accepts a tag without a separator
**Dimension:** Correctness
**Evidence:** `webapp.py` `_handle_model_status`: `present = any(n == model_name or n.startswith(model_name) for n in names)`. For the active tag `gemma4:e4b`, a real variant `gemma4:e4b-it-q4_K_M` correctly matches (good) — but so would a hypothetical unrelated `gemma4:e4bxyz` with no `-`/`:` separator.
**Why it matters:** No such Ollama tag exists today, so it's theoretical — but anchoring the prefix on a separator is strictly more correct and costs nothing.
**Fix path:** `n == model_name or n.startswith(model_name + "-")` (Ollama variant tags append `-<variant>`). Keeps the quantized-variant match, drops the theoretical false-positive.
**Status:** ✅ Fixed — match tightened; the quantized-variant test still passes.

## What's working
- **Trust rule 1 is honored exactly.** The AI section is a *health readout*, not a picker: gemma4:e4b is rendered as a `<code>` tag with its status (Running / Not running / Model not pulled / Cloud) — there is **no model dropdown**, and a test (`no combobox named /model/i`) locks that in. No Chinese model appears anywhere. The manual `--backend` override stays CLI-only, as designed.
- **Bounded + never-raises probe.** `probe_ollama` wraps `urlopen(timeout=3.0)` in the same exception tuple as the proven `probe_installed_models` (URLError/OSError/ValueError/TimeoutError → `(False, [])`), so a down/slow/garbage Ollama degrades within 3s and never throws. The endpoint catches a config gap (`backend=None` → defaults to gemma4:e4b) and never 500s — a down model server is a *status*, not an error.
- **The reachable-vs-empty distinction is the real win.** `probe_ollama` returns `(reachable, models)` so the UI can say "start Ollama" (not running) vs "get the model" (running, not pulled) — two genuinely different fixes. `probe_installed_models` (which returns `[]` for both) couldn't, and the endpoint maps the two states correctly; all three local states are tested via the mock.
- **Honest, no-dead-end UX.** The status shows a real "Checking…" spinner while the probe runs (never a premature "Running"); each non-running state gives a concrete next action with a re-check, plus a Refresh — matching the §4.2 "every state has a next action" rule. The model status loads *independently* of printer/material, so the ~3s probe doesn't freeze the rest of the screen. a11y: `role="status"` on the live region, a text label beside the color dot (not color-only), real `<button>` controls.
- **Tests are non-vacuous.** The endpoint tests pin the down / up-empty / present distinction and the quantized-variant match; the frontend tests pin the three local states + Refresh + the error readout. 131 vitest + the new backend tests pass.

## Watch items
- **AI section renders inside the settings-loaded body**, so a slow `getSettings` delays the AI card's appearance (the independent load fully decouples only the other direction — a slow Ollama not blocking the already-loaded printer/material rows). Both endpoints are the same local server, so this is acceptable; revisit if Settings ever splits across services.
- **Cloud reachability isn't probed in-band** (it would need the key) — the cloud backend reports `running:true` when merely configured. That's the right call for MS-2; MS-3's cloud opt-in owns the key + the local/cloud labeling.

## Escalation recommendation
No escalation needed. One Minor + one Nit, both fixed; trust rule 1 and the safety posture hold. The slice-end audit-team + wiring-audit (after MS-3–5) remain the gate.
