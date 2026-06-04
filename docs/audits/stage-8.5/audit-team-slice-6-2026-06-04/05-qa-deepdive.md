# QA Engineer — Deep-Dive: Stage 8.5 Slice 6 (Settings + cloud routing + experimental gate)

**Role:** Senior QA Engineer (runtime behavior — exercise the running product)
**Posture:** Balanced
**Date:** 2026-06-04
**Target:** KimCad Stage 8.5 Slice 6 — the in-app Settings screen, OpenRouter cloud routing, and the experimental-generator gate.

## Environment & method

- **Live demo server:** model-free demo at `http://localhost:8810` (registered preview server `kimcad-slice6-demo`, port 8810). Running before this audit; driven, not restarted.
- **HTTP layer:** `curl` against the Slice 6 endpoints (`/api/settings` GET+POST, `/api/model-status`, `/api/health`).
- **Browser/DOM:** Claude_Preview tools (eval / network / console) against the registered server. The Settings SPA route is `#/settings`.
- **Source read in full:** `src/kimcad/webapp.py` (handlers + `_mask_key` + `_SettingsAwareProvider` + `settings_response`), `src/kimcad/settings_store.py`, `frontend/src/components/SettingsPanel.tsx`, and the experimental gate in `src/kimcad/pipeline.py`.
- **JPEG/screenshot tool:** per the brief, not relied on — all visual verification is via DOM (`preview_eval` reading `document`), network bodies, and console logs.

### Altitude / what is NOT exercised live
- Software-complete; **no real hardware**.
- **gemma4 / OpenRouter are NOT exercised live.** The cloud path is verified through the settings/routing contract (the key is saved, masked, and `model-status` flips to `backend: cloud`), not by issuing a real OpenRouter call. A FAKE key (`FAKEAUDITKEY0000000000ABCDE`) was used throughout.
- The `experimental:false` → `needs_experimental` runtime behavior on a NON-template prompt is **not reproducible in the demo** (the demo's "box" matches the `snap_box` template, which short-circuits before the gate). It is confirmed by source + the design POST observations below.

### Note on the live model probe
This box actually has Ollama running with `gemma4:e4b-it-q4_K_M` pulled, so the *local* `model-status` reads `running:true, model_present:true` from a REAL probe (not a stub). The variant-suffix match (`gemma4:e4b-it-q4_K_M` matches `gemma4:e4b-`) works correctly.

---

## Findings

**Severity counts: Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 1**

No defects of Minor severity or above were found. One Nit is logged below. This slice is in strong shape at the runtime layer.

### QA-001 (Nit) — Reset persists `cloud_enabled:false` / `experimental_enabled:false` as explicit keys rather than removing them
- **Category:** API / State
- **Evidence:** After a full DOM Reset, `~/.kimcad/settings.json` reads:
  ```json
  { "cloud_enabled": false, "experimental_enabled": false }
  ```
  The printer/material/key/model keys are correctly *removed* (the store pops `None`-valued keys), but the two booleans are written as explicit `false` because `resetAll()` sends `false`, not `null`.
- **Why this matters:** Purely cosmetic. The effective state is identical to a pristine install (both default to `false`), and the GET payload is byte-identical to a never-configured app. No user impact, no key residue.
- **Fix path (optional):** If a truly empty file after reset is desired, send `null` for the two booleans in `resetAll()` so the store pops them. Not worth a change on its own.

---

## What's working (credited)

Every load-bearing claim the brief asked me to prove or break held up under live exercise:

### 1. The OpenRouter key is NEVER returned raw — only masked
- **POST response** (set `cloud_enabled:true` + key `FAKEAUDITKEY0000000000ABCDE` + model): body returned `"cloud_key_masked": "••••••••••••••••ABCDE"`, `"has_cloud_key": true`. The raw key did **not** appear.
- **GET `/api/settings` over the wire** (captured via `preview_network`, the actual payload that fed the DOM):
  ```json
  "default_printer": "bambu_a1", "default_material": "petg",
  "cloud_enabled": true, "cloud_model": "anthropic/claude-3.5-sonnet",
  "has_cloud_key": true, "cloud_key_masked": "••••••••••••••••ABCDE",
  "experimental_enabled": true
  ```
  No `openrouter_api_key`, no raw value anywhere in the response.
- **DOM after reload:** `#cloud-key` input value = `••••••••••••••••ABCDE` (16 dots + last 5), `readOnly: true`, with a "Replace" button. A scan of the entire `document.body.innerHTML` for the raw string returned **`false`** — the raw key appears nowhere in the rendered DOM.
- The raw key **is** stored on disk at `~/.kimcad/settings.json` (line: `"openrouter_api_key": "FAKEAUDITKEY..."`). This is correct and by design — local-first, the user's own secret on their own machine, never the repo, never the API.

### 2. Unknown printer/material → 400, never 500; malformed input handled
- `POST {"default_printer":"nonexistent_printer"}` → **400** `{"error":"Unknown printer."}`
- `POST {"default_material":"unobtanium"}` → **400** `{"error":"Unknown material."}`
- `POST [1,2,3]` (non-object body) → **400** `{"error":"Request body must be a JSON object."}`
- `POST {not valid json` → **400** `{"error":"Request body isn't valid JSON."}`
- `PUT` / `DELETE` on `/api/settings` → **405** (correct, not 501/500).
- Valid `POST {"default_printer":"bambu_a1","default_material":"petg"}` → **200** with `"saved": true`.

### 3. A down model server / config gap is a STATUS, never a 500
- `/api/health` → **200** `{"version":"0.1.0","openscad":true,"orcaslicer":true}`. Health is best-effort with a per-binary `try/except` that returns `present:false` rather than raising — verified in source (`_handle_health`).
- `/api/model-status` (local) → **200** `{"model":"gemma4:e4b","backend":"local","running":true,"model_present":true}`.
- `/api/model-status` (cloud configured) → **200** `{"model":"anthropic/claude-3.5-sonnet","backend":"cloud","running":true,"model_present":true}` — correctly reflects the EFFECTIVE backend, not the local default.
- All endpoints stayed 200 after the reset.

### 4. Settings persist across reload
- After setting printer/material, enabling cloud + key + model, and toggling experimental, a **full browser reload** re-fetched the settings and the DOM showed: printer `bambu_a1`, material `petg`, cloud switch `aria-checked:true`, model `anthropic/claude-3.5-sonnet`, masked key present, experimental `aria-checked:true`. Everything survived.
- **Units** persist independently in the client store: toggling to `in` wrote `localStorage['kc-units']='in'` and the `in` button stayed active across a reload. (Units are intentionally client-only, not in `settings.json` — documented design.)

### 5. Reset clears everything (two-step, confirmed)
- Two-step confirm: clicking **"Reset…"** reveals a danger-styled **"Reset everything"** + **"Cancel"** (verified the confirm UI appears before the destructive action).
- After **"Reset everything"**:
  - **DOM:** cloud `aria-checked:false` (config section hidden, no `#cloud-key`), experimental `aria-checked:false`, printer `bambu_p2s`, material `pla`, units `mm`.
  - **Server GET:** `default_printer:"bambu_p2s"`, `default_material:"pla"`, `cloud_enabled:false`, `cloud_model:""`, `has_cloud_key:false`, `cloud_key_masked:null`, `experimental_enabled:false`.
  - **On disk:** `openrouter_api_key` is **gone** from `settings.json` — the key was truly erased, not just hidden. (See QA-001 for the cosmetic residue of two `false` booleans.)

### 6. Experimental gate (confirmed via source + design POST)
- `pipeline.py` line 373: `if match is None and not allow_experimental:` → returns `PipelineStatus.needs_experimental` (offers the generator rather than dead-ending or auto-running).
- `webapp.py` `_handle_design`: `allow_experimental = bool(data.get("experimental", True)) or saved_settings().get("experimental_enabled")` — an absent flag defaults True (back-compat), the consumer SPA sends `experimental:false`, and the Settings toggle force-enables it.
- **Live design POST on the demo:** both `{"experimental":false}` and `{"experimental":true}` on prompt "a small box" returned `status:completed, template:snap_box, gate:pass` — because the box matches a template, the experimental flag is never reached. This is the expected demo limitation (a non-template prompt would be needed to drive `needs_experimental`, which the model-free demo can't produce). Covered by unit tests per the slice's audit-lite.

### 7. Console & network discipline
- **Zero console logs** (error or warn) across the entire Settings flow — load, toggle cloud, save key, save model, toggle experimental, reset.
- **Zero failed requests** (no 4xx/5xx) in the browser session; all asset, settings, model-status, and health requests were 200.
- **No spurious write-on-mount:** a fetch spy across a fresh Settings re-mount recorded `[]` POSTs — the SPA does not write settings on load, only on user interaction.

---

## What I couldn't test (explicit)
- A real OpenRouter cloud completion (no live key / out of altitude). The routing *contract* is verified; the actual cloud LLM call is not.
- `needs_experimental` runtime on a real non-template prompt (the demo provider only emits a template-matching "box"). Verified by source + unit-test coverage instead.
- Real-hardware send/slice paths (out of scope for this slice and altitude).
- The screenshot/JPEG tool was deliberately not used (times out per the brief) — all evidence is DOM/network/console.

---

## Blast radius (slice-level)
The Slice 6 surface is well-isolated. The key-masking is centralized in `_mask_key` + `settings_response` (single source), the persistence is the small best-effort `SettingsStore` with an allow-list of keys (a crafted client can't stuff arbitrary data), and the cloud routing degrades to local on every gap. No finding rises to a level that touches adjacent flows, so no per-finding blast radius is enumerated (QA-001 is a Nit).
