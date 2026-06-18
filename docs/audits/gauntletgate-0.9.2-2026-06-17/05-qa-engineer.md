# GauntletGate Full — QA Engineer — KimCad 0.9.2

**Role:** QA Engineer
**Date:** 2026-06-17
**Build/commit:** e91b148 (version sweep) + 9ddea46 (the two fixes)
**First-run delta verdict:** UNCHANGED — the 0.9.2 change surface does not touch the first-run/onboarding path
**Severity roll-up:** Blocker 0 · Critical 0 · Major 0 · Minor 1 · Nit 1

---

## First-run delta analysis

### What changed in 0.9.2

Two changes, both in the backend:

1. **`MODEL_UNAVAILABLE_MESSAGE`** (`pipeline.py:202-205`) — the string shown when the local AI server can't be reached mid-pipeline.
2. **`_child_env()` OLLAMA_MODELS** (`ollama_runtime.py:150`) — pins the Ollama models directory to `writable_root() / "models"` when KimCad starts its own managed server.

### Does Fix 1 affect first-run?

**No.** `MODEL_UNAVAILABLE_MESSAGE` is emitted at three call sites in `webapp.py` (lines 2000-2001, 2042-2043, 2120-2121) — all inside the `_handle_design()`, `_handle_photo_seed()`, and `_handle_sketch_seed()` handlers. These handlers process user design requests; none of them are called during first-run setup. The wizard (`frontend/src/components/FirstRunWizard.tsx`) calls only `/api/settings`, `/api/model-status`, `/api/model-pull`, and `/api/model-pull/progress`. The error message string is unreachable from the first-run path.

The trigger for `MODEL_UNAVAILABLE_MESSAGE` is a `ConnectionRefusedError`, `APIConnectionError`, `URLError`, or timeout raised **during a design pipeline run** — a mid-session event that requires the user to have already finished setup, entered a prompt, and submitted a design request. First-run users never reach this path.

### Does Fix 2 affect first-run?

**Only in the desired direction.** `_child_env()` is called by `start_serve()` in `ollama_runtime.py:168`, which is called from `model_pull._run_setup()` (via the injected `serve` callback, `model_pull.py:215 → serve(exe)`). `_run_setup()` IS called during first-run when the user clicks "Set up KimCad's AI" in wizard step 1 — but the change is a **fix**, not a regression.

Before 0.9.2: `OLLAMA_MODELS` was not explicitly set, so models landed in `~/.ollama` (7+ GB orphaned after uninstall). After 0.9.2: models land in `writable_root() / "models"` = `%LOCALAPPDATA%\KimCad\models` in installed mode. This is the correct path, already covered by the uninstaller scope.

**`writable_root()` on first launch:** `writable_root()` returns `_per_user_data_root()` = `%LOCALAPPDATA%\KimCad` in installed mode. The directory need not exist before `_child_env()` is called — `OLLAMA_MODELS` is only an env var passed to `ollama serve`. Ollama creates the models directory itself when it first downloads a model. There is no mkdir call in `_child_env()`; the path resolution is just string construction. This is safe on a clean first launch.

**Reuse-path (system Ollama present):** `_child_env()` is only called via `start_serve()`. The `ensure_serving()` / `_run_setup()` reuse branch returns `OllamaStatus(True, "already-up")` immediately if a server is already up, skipping `start_serve()` entirely. A user with system Ollama already running never hits `_child_env()` — the fix has no effect on their path.

### First-run verdict: UNCHANGED

The 0.9.2 diff touches two backend constants/functions. Neither touches `FirstRunWizard.tsx`, the `/api/model-pull` pipeline, the wizard API surface (`/api/settings`, `/api/model-status`), or any first-run rendering logic. The `_child_env()` change is exercised during the wizard's "Set up KimCad's AI" flow but only improves it (models land under uninstall scope). The 0.9.1 first-run attestation — VALID on a clean machine with Ollama ABSENT, confirmed by directive-007 tester — carries forward unchanged. No re-verification of the first-run path is required for 0.9.2 advancement.

---

## Findings

### QA-MIN-001 · Minor: User-visible "Ollama" mention in wizard step 1 action copy

**File:** `frontend/src/components/FirstRunWizard.tsx:360`
**Text shown to user (when engine is not running):**
```
'KimCad sets up its AI for you — no separate install. It downloads the AI engine, then the model, right here. (Already have Ollama? KimCad uses it automatically.)'
```
**Context:** This string is rendered inside the wizard's "Set up your AI" step (step 1) when `model.running` is false — i.e., the first thing a cold-start user sees when they click through to the AI setup step.

**Why it matters:** The parenthetical `(Already have Ollama? KimCad uses it automatically.)` exposes the "Ollama" brand name to a first-run user. The bug this 0.9.2 gate exists to fix (Minor-1) was precisely that `MODEL_UNAVAILABLE_MESSAGE` said "Ollama" — the product decision is to hide the Ollama dependency from users who know it only as "KimCad's AI." This string contradicts that decision in the exact first-run path.

**Severity rationale:** Minor, not Blocker. The copy is informational, not blocking; the "Already have Ollama" clause is targeted at power users who would already know the name. It doesn't block setup or create a dead-end. But it is inconsistent with the 0.9.2 fix's stated goal and with the `UX-COLD-001` note immediately above it in the source.

**Fix path:** Reword the parenthetical to hide the implementation detail, e.g.:
```
'KimCad sets up its AI for you — no separate install. It downloads the AI engine, then the model, right here. (If you've already set up a local AI engine, KimCad uses it automatically.)'
```

**Pre-existing or new?** Pre-existing — not introduced by 0.9.2. However, 0.9.2's stated fix rationale ("Never mentions 'Ollama'") makes this inconsistency newly salient. The walkthrough did not flag it because walkthrough ran on a provisioned box where `model.running` was true and the action copy was never rendered.

---

### QA-MIN-002 · Minor (pre-existing, flagged for completeness): "Ollama" in engine start-failure error

**File:** `src/kimcad/model_pull.py:286-289`
**Text shown to user (engine start failure during setup):**
```
"Couldn't start the local AI engine — try again, or install Ollama from ollama.com."
```
**Context:** This error appears in the wizard's pull progress row when `start_serve(exe)` raises an exception during the one-click setup flow.

**Why it matters:** Same rationale as QA-MIN-001 — "Ollama" is visible to a first-run user in an error path. The recovery instruction ("install Ollama from ollama.com") is also logically inconsistent: KimCad is supposed to manage the runtime itself, so sending a first-run user to ollama.com after the managed setup fails contradicts the UX-COLD-001 architecture.

**Severity rationale:** Minor. Only reachable on an error path (the managed `ollama serve` launch raises), which requires the portable binary to have been fetched and extracted but then failed to spawn — an uncommon failure mode on first run. Not blocking; the error is friendlier than a raw traceback.

**Fix path:** Reword to stay within KimCad's product vocabulary:
```
"Couldn't start the local AI engine — check that no other application is blocking port 11434, then try again."
```

**Pre-existing or new?** Pre-existing — not in the 0.9.2 diff. Flagged because the 0.9.2 `MODEL_UNAVAILABLE_MESSAGE` fix set a clear product standard ("never says Ollama"), and this string violates that standard in the same first-run path.

---

### QA-NIT-001 · Nit: `ModelHealthPill.tsx` model-not-downloaded copy contains "ollama pull"

**File:** `frontend/src/components/ModelHealthPill.tsx:37,39`
**Text:**
```
`The model isn't downloaded yet — the setup wizard's Download button fetches it (or run "ollama pull ${model.model}").`
`Photos and sketches need one more download — the setup wizard's Download button fetches it (or run "ollama pull ${model.vision_model}"). Designing in words works now.`
```
**Context:** Shown as a persistent warning pill above the prompt input when the model isn't pulled. A first-run user who dismissed the wizard and went straight to the chat would see this.

**Severity rationale:** Nit. The primary action path ("the setup wizard's Download button fetches it") is correct and doesn't mention Ollama. The parenthetical CLI command is a secondary fallback for power users and is technically accurate. Not a dead-end. However, `SettingsPanel.tsx:425` has an identical `ollama pull` reference in a settings context (not first-run), so this is a systemic pattern.

**Pre-existing or new?** Pre-existing.

---

## API contract verification

**`model_unavailable` status routing — verified correct at every layer:**

1. **Pipeline propagation:** `_run_pipeline()` does not catch connection errors — they propagate to the caller. The `webapp.py` exception handler at line 2108-2122 catches them and maps to `{"status": "model_unavailable", "error": MODEL_UNAVAILABLE_MESSAGE}`. This is the correct separation: pipeline stays pure, web layer owns the HTTP mapping.

2. **Photo/sketch handlers:** Both `_handle_photo_seed()` (line 1999-2002) and `_handle_sketch_seed()` (analogous pattern ~line 2030-2043) also catch `_is_model_unreachable()` and return the same typed status. `VisionModelMissing` and `VisionReadError` also map to `model_unavailable` with their own messages — typed, not `MODEL_UNAVAILABLE_MESSAGE`. This is correct: those errors carry specific actionable messages.

3. **Frontend `designStatus.ts:75`:** `model_unavailable` maps to `assistantMessage()` which uses `body.error` (the server's message string) when present, else a generic `/local AI/i` fallback. Verified in `designStatus.test.ts:70-74`. Correct.

4. **Frontend `ChatPanel.tsx:217`:** Renders a "Try again" button specifically for `model_unavailable` status — a one-click recovery without navigating to Settings. Tested in `ChatPanel.test.tsx:150`.

5. **`api.ts:492,519`:** Two fetch helpers map `model_unavailable` status to a typed error. Tests at `api.test.ts:270-274` assert the new message text flows through. Correct.

**No gaps found in the API contract chain.**

---

## Edge case analysis

### `writable_root()` returns non-existent path on first launch

`_child_env()` calls `writable_root() / "models"` and converts it to a string for the `OLLAMA_MODELS` env var. It does NOT `mkdir` the path — that's correct. Ollama itself creates the models directory on first pull. No crash risk on first launch.

### `OLLAMA_MODELS` set to a read-only or inaccessible path

`writable_root()` in installed mode returns `%LOCALAPPDATA%\KimCad`. On a standard Windows install, `%LOCALAPPDATA%` is always the current user's writable dir. An edge case where `LOCALAPPDATA` points somewhere read-only (e.g., a kiosk/managed device) would cause Ollama to fail model pulls with a write error — but this would surface as a `model_pull` error row, not a silent failure. The error would be Ollama's own message, not KimCad's. This is the same risk as before 0.9.2 (previously models went to `~/.ollama`, which could also be read-only on a kiosk). **Not a regression; pre-existing edge case.**

### `_child_env()` called with `env=None` (the default real path)

`base = os.environ` — inherits the full process environment. The `_SECRETISH` deny-list strips `API_KEY`, `SECRET`, `TOKEN`, `PASSWORD`, `_KEY`, `CREDENTIAL` patterns. `KIMCAD_INSTALL_ROOT` is not secret-shaped, so it passes through. `LOCALAPPDATA` passes through (needed for `writable_root()` calls inside Ollama if any). `PATH` passes through (Ollama needs it). No regression from the `OLLAMA_MODELS` addition.

### What if `_child_env()` is called before `writable_root()` creates its directory?

`writable_root()` in `paths.py:57-62` is pure path computation — it never creates the directory. `_child_env()` uses it only to compute a string. No filesystem operations happen in `_child_env()`. Safe on first launch regardless of directory state.

---

## What's working (specific and credited)

- **Fix 1 scope is exactly right.** `MODEL_UNAVAILABLE_MESSAGE` is only shown mid-session (post-design-request), never during first-run. The fix eliminates the "Ollama" leak at the exact place it mattered for an established user who loses the engine mid-session.

- **Fix 2 scoping is precise.** `_child_env()` is only called when KimCad starts its OWN managed server (`start_serve()`). The reuse branch (`already-up`) never calls it. This means users with system Ollama are completely unaffected by the models-path change — their models stay where Ollama put them, no migration needed.

- **`_child_env()` deny-list is safe.** The `_SECRETISH` filter is a deny-list (never accidentally starves Ollama of needed vars), and the comment in the source correctly explains the rationale. The `OLLAMA_MODELS` addition sits after the deny-list filter — it's always set, which is the right behavior.

- **`writable_root() / "models"` is uninstaller-consistent.** The uninstaller already removes all of `writable_root()` (`%LOCALAPPDATA%\KimCad`). Pinning `OLLAMA_MODELS` there means models are removed on uninstall without a separate cleanup step.

- **Test coverage matches the fixes.** `test_ollama_runtime.py:96-99` asserts `OLLAMA_MODELS == str(writable_root() / "models")`; `test_webapp.py:1438,3661,3731` assert `"engine" in body["error"]`. Both green at gate (1679/405 confirmed by walkthrough lane).

- **First-run wizard (pre-existing, credited):** `FirstRunWizard.tsx` correctly uses `model.running` (not a string comparison to "Ollama") to drive its state machine. The `modelLabel()` function returns "Not set up yet" (not "Ollama isn't running") — the UX-COLD-001 intent holds throughout the wizard component.

---

## Coverage gaps

1. **First-run with engine start failure (`model_pull.py:286-289`):** The error path where `start_serve(exe)` raises (the managed engine binary fails to launch) has never been exercised live. The error message in that path says "install Ollama from ollama.com" — a guidance gap that would send a first-run user off-product. Coverage: unit tests mock the serve call to raise, confirming the row gets `status: error`; but no test asserts the message text in this path.

2. **`OLLAMA_MODELS` live first-run (installed mode):** Cannot be verified on this dev box (dev mode → `writable_root()` → repo root, not `%LOCALAPPDATA%\KimCad`). Static + unit-test evidence is sufficient for gate purposes, consistent with the walkthrough lane attestation.

3. **`model_unavailable` live trigger (provisioned box):** Cannot exercise live on a box with system Ollama running. Static + test coverage (three test files, multiple assertions) is the verification record.

4. **`ModelHealthPill` "Not set up yet" first-run path:** The pill is mounted above the chat input on the landing page. If a user dismisses the wizard without downloading the model, the pill shows an "ollama pull" CLI hint (QA-NIT-001). This path was not exercised in any lane because the walkthrough had models already present.
