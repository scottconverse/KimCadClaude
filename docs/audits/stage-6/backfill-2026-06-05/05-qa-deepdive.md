# 05 — QA Engineer Deep-Dive — KimCad Stage 6 Model Layer (backfill 2026-06-05)

**Role:** Senior QA Engineer (independent, skeptical). QA = runtime behavior, run it.
**Branch:** `stage-0-7-audit-backfill` (HEAD `6b60126`)
**Scope:** Runtime behavior of the model layer — `/api/model-status`, `/api/settings` GET/POST
(cloud opt-in, API-key masking, experimental toggle), model-down behavior, advisor surface,
malformed-input handling, and API-key leakage.
**Environment:** Windows 11; demo server `python -m kimcad.cli web --demo --port 8765 --host 127.0.0.1`
(PID 12792); Ollama up at `localhost:11434` with `gemma4:e4b` pulled (Q4_K_M, 9.6 GB);
OpenSCAD + OrcaSlicer binaries present. Probes via curl + stdlib `urllib` against the live server
and direct function-level calls into `kimcad.model_advisor` / `kimcad.pipeline`.

> NOTE on test mode: the live server runs in **`--demo`** mode. In demo mode the *pipeline provider*
> is the bare `DemoProvider` (no `_SettingsAwareProvider` wrap), but the HTTP handler's `get_config()`
> / `saved_settings()` still use the **real** config and the real `~/.kimcad/settings.json` store —
> so model-status, settings GET/POST, masking, and malformed-body handling are all exercised against
> production code paths. The one path demo mode does NOT exercise live is the cloud-provider *build*
> (it only runs on a real design call through `_SettingsAwareProvider`); that path was reviewed
> statically and confirmed leak-free (see QA-W4). I captured the real settings file and restored it
> afterward; no probe scripts were left behind.

---

## Severity counts

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 2 |
| Nit      | 1 |
| **Total**| **3** |

No Blockers, Criticals, or Majors. The model layer's runtime contract is honest and resilient:
the API key is never echoed in full on any surface, model-status reports truthfully, Ollama-down is
a typed status (never a 500/traceback), and malformed input yields clean 4xx everywhere I pushed it.

---

## What's working (credit where due)

- **`GET /api/model-status` is honest.** Live: `{"model":"gemma4:e4b","backend":"local","running":true,"model_present":true}`.
  Cross-checked against `GET http://localhost:11434/api/tags` — `gemma4:e4b` is genuinely pulled and
  Ollama genuinely answers, so every field is true-to-reality. The handler matches the model tag
  exactly or as a `<tag>-<variant>` quant suffix, so a quantized pull (`gemma4:e4b-it-q4_K_M`) would
  also read `model_present:true` without false-matching an unrelated tag.
- **API-key masking holds on every surface.** POSTing a 42-char fake key returned
  `cloud_key_masked: "••••••••••••••••WXY99"` (16 dots + last 5) and `has_cloud_key:true`; the full
  key appeared in **neither** the POST response, a subsequent GET, nor `/api/model-status`. The full
  key is stored only in `~/.kimcad/settings.json` (the user's own machine, never the repo) — I grepped
  the entire repo tree, `output/`, and any `.log` files for the sentinel: zero hits outside the home
  settings file. `log_message` is a no-op so the stdlib request log can't leak it either.
- **Reset fully purges the key.** `POST /api/settings {"reset":true}` cleared everything; the on-disk
  file became `{}` and the API reported `has_cloud_key:false`, `cloud_key_masked:null`. A user can
  genuinely remove their stored secret.
- **Cloud-readiness is reported truthfully, not optimistically.** model-status flips to
  `backend:"cloud"` only when cloud is enabled AND a key AND a model are all set. With cloud enabled +
  key set but model **blank**, model-status honestly fell back to `backend:"local"`/gemma4:e4b — it
  does not claim a cloud model it can't actually route to. This matches `_SettingsAwareProvider._active()`'s
  identical guard, so the status and the routing agree.
- **Model-down is a typed status, never a 500.** `probe_ollama` against a dead port returns
  `(False, [])` in ~2 s and against six garbage base_urls (`""`, `"not a url"`, `"http://["`, …)
  returns `(False, [])` with no exception — so a down Ollama makes model-status report
  `running:false, model_present:false`. On the design path, an Ollama-down `APIConnectionError`/
  `APITimeoutError` is recognized by `_is_model_unreachable` and mapped to a `200 model_unavailable`
  with a recoverable, plain-English message — never a raw traceback.
- **Malformed-input handling is uniformly clean (no 500s).** Garbage non-JSON → 400 "isn't valid
  JSON"; a JSON list / scalar / null → 400 "must be a JSON object"; wrong-typed `default_printer`
  (int), `cloud_model` (int), `openrouter_api_key` (int) → 400 with field-specific messages; an
  unknown printer/material → 400; an unknown extra key alongside a valid field → 200 (ignored, not
  persisted, since `SettingsStore` filters to `_ALLOWED_KEYS`). An oversized body (>1 MiB) → 413.
- **HTTP method discipline (settings).** `PUT/DELETE/PATCH/OPTIONS /api/settings` → 405 with an
  `Allow: GET, HEAD, POST` header and the app's JSON error shape; `HEAD /api/model-status` → 200
  header-only.
- **Demo design path is LLM-free and complete.** `POST /api/design {"prompt":"a small box"}` →
  `status:completed, has_mesh:true, gate:pass` without touching the model.

## Advisor surface

The hardware/availability advisor (`kimcad.model_advisor.recommend` / `probe_hardware`) is **not
exposed over HTTP** — no `/api/advisor`, `/api/recommend`, or `/api/model-*` route beyond
`model-status`. Only `probe_ollama` feeds the HTTP layer. The advisor is a CLI-side surface, out of
the running-product scope here; I confirmed (static read) the catalog hard-deprioritizes Qwen below
`gemma4:e4b` (tier 7 vs tier 1, with REJECTED notes) and surfaces gemma4 as the non-China escape, so
the advisor cannot recommend a Chinese model over gemma4. No runtime finding. *(Not raising a
gemma4-vs-other finding per scope; noted only as confirmation the standing rule holds in code.)*

---

## Findings

### QA-001 (Minor) — A short cloud key (9–~12 chars) is masked but still reveals most of itself

**Category:** Security / API
**Endpoint:** `POST /api/settings` → `cloud_key_masked` (and the same on `GET /api/settings`)

**Evidence (reproduced):**
1. `POST /api/settings {"openrouter_api_key":"123456789"}` (9 chars).
2. Observed: `cloud_key_masked = "••••••••••••••••56789"` — the last **5 of 9** characters (≈55%)
   are revealed.
3. By contrast, `"abc123"` (6 chars, ≤ 8) → `cloud_key_masked = "••••••••••••••••"` (nothing
   revealed), and `has_cloud_key:true`.

The `_mask_key` guard (`tail = key[-5:] if len(key) > 8 else ""`) reveals nothing at ≤ 8 chars but
flips to a flat last-5 reveal at 9 chars — so a 9–13-char value exposes 38–55% of itself in one
step. The dot run is a fixed 16, so the mask length also does not track the real key length (no
length-inference leak, which is good, but the reveal fraction is the issue).

**Why it matters:** A real OpenRouter key is 40+ chars (the docstring assumes this), where last-5 is
a fine fingerprint. The exposure only bites if a user pastes an unusually short/truncated key or a
non-OpenRouter token. Real-world likelihood is low, hence Minor — but the cliff at 9 chars is a
sharp, surprising boundary for a security-relevant redaction.

**Blast radius:**
- Adjacent code: `_mask_key` in `src/kimcad/webapp.py` (the sole masker; used by `settings_response`,
  which feeds both GET and POST `/api/settings`). One fix point.
- User-facing: only the redisplayed mask changes; no stored-data or routing change.
- Migration: none.
- Tests to update: any test asserting the exact `cloud_key_masked` for a short key (search
  `tests/test_webapp.py` for `cloud_key_masked` / `_mask_key`).
- Related findings: none.

**Fix path:** Reveal the last-5 tail only when the key is long enough that 5 chars is a small
fraction — e.g. require `len(key) >= 12` (or `len(key) > 16`) before revealing any tail, otherwise
return the all-dots form. Optionally reveal `min(5, len//4)` so the fraction stays bounded for
short values.

---

### QA-002 (Minor) — `POST /api/model-status` returns 404, not 405

**Category:** API (contract consistency)
**Endpoint:** `POST /api/model-status` (and by the same mechanism: POST to any GET-only API resource,
e.g. `/api/health`, `/api/options`, `/api/connectors`)

**Evidence (reproduced):**
1. `POST /api/model-status` → **404** `{"error":"Not found."}`.
2. `PUT /api/settings` → **405** `{"error":"Method not allowed."}` with `Allow: GET, HEAD, POST`.

So the wrong-verb contract is inconsistent: `/api/settings` (which has both GET and POST handlers)
correctly answers 405 for *other* verbs, but a GET-only resource answers POST with 404 — because
`do_POST` is a separate dispatch table that has no entry for `/api/model-status` and falls through to
its generic 404. A REST integrator probing the API would read "this resource doesn't exist" rather
than "this resource exists but doesn't accept POST." The QA-005 design comment in the source ("the
resources exist for GET/HEAD/POST, so an unsupported verb is 405, not 501") is only realized for the
verbs routed through `_method_not_allowed` (PUT/DELETE/PATCH/OPTIONS), not for POST-to-a-GET-resource.

**Why it matters:** Minor — it's an honest-error/contract nicety, not a functional break; the SPA
never issues these. It only misleads a direct API client or a contract test. No security impact (the
resource isn't mutated).

**Blast radius:**
- Adjacent code: `do_POST` / `do_GET` dispatch in `src/kimcad/webapp.py`; affects every GET-only API
  path uniformly.
- User-facing: none (SPA uses correct verbs).
- Migration: none.
- Tests to update: none known (no test asserts POST-to-GET-resource status today — itself a small
  gap to hand the Test Engineer).
- Related findings: none.

**Fix path:** Have `do_POST` (and `do_GET`) distinguish "known resource, wrong method" from "unknown
resource": keep a small set of known GET-only and POST-only API paths and return 405 with an `Allow`
header naming the accepted verb(s) when the path matches a known resource but not this verb. Low
priority.

---

### QA-003 (Nit) — Settings booleans coerce truthy strings silently rather than rejecting them

**Category:** API (input hygiene)
**Endpoint:** `POST /api/settings` — `experimental_enabled`, `cloud_enabled`

**Evidence (reproduced):**
1. `POST {"experimental_enabled":"notabool"}` → response `experimental_enabled:true`.
2. `POST {"cloud_enabled":"yes"}` → response `cloud_enabled:true`.

The handler applies `bool(data.get(...))` to these flags, so any truthy non-bool (a non-empty
string, a non-zero number) becomes `true` and is persisted. Contrast with the string fields
(`cloud_model`, `openrouter_api_key`), which **do** reject a wrong type with a 400. The booleans are
the looser end of an otherwise strict validation surface.

**Why it matters:** Nit. It's lenient, not unsafe — the value still lands as a clean bool and the
toggle behaves; a malicious client gains nothing (it could just send `true`). It's only an
inconsistency in how strictly the endpoint validates types across fields, and could surprise a
contract test. No blast radius enumerated per the framework (Nit).

**Fix path (optional):** For symmetry with the string fields, reject a non-bool, non-null value for
`cloud_enabled` / `experimental_enabled` with a 400 ("Invalid value."), or document that these
fields are coerced. Lowest priority — leave as-is is defensible.

---

## What I could not test (named, not silently skipped)

- **Live cloud routing to OpenRouter.** No real OpenRouter key on hand and the spec is local-first;
  I used a fake key to exercise *masking and persistence*, not an actual cloud design call. The
  cloud-provider *build* path (`_SettingsAwareProvider._active` → `LLMProvider(backend, api_key=key)`)
  was read statically: it passes the key to the provider constructor only, caches providers in a
  bounded LRU (max 4) that evicts old key material, and never logs/returns the key. No runtime
  exercise of an actual cloud request/response, so I can't certify the *wire* behavior — only that
  the local-side handling is leak-free.
- **A genuinely down Ollama at the live HTTP layer.** I did not stop the operator's Ollama. I instead
  drove `probe_ollama` against a dead/garbage base_url (returns the typed `(False, [])`) and confirmed
  the design path's `_is_model_unreachable` mapping at the function level — together these cover the
  handler's branch, but the end-to-end "Ollama stopped, hit `/api/model-status`" sequence on the live
  server was inferred, not executed.
- **Concurrency/race on the settings file.** During testing I observed `~/.kimcad/settings.json`
  being written by *another* process/session (it appeared mid-audit and `cloud_enabled` flipped under
  me between a POST and a read). This is environmental (a parallel session), not a server defect — the
  store's writes are atomic (`os.replace` + retry) and serialized by a lock, so it's safe — but it
  meant I could not treat the file as a stable single-writer fixture. Worth the operator knowing only
  if multiple KimCad sessions are expected to run against the same home dir.

---

## Method notes

- All findings reproduced at least twice. Sentinel keys were distinctive 42-char non-credential
  strings so I could grep every surface for leakage.
- The real `~/.kimcad/settings.json` was backed up before mutation and restored to its found state
  (`{"cloud_enabled": true}`) afterward; all temporary probe scripts were removed. A pre-existing
  local Agent-Pipeline hook flagged a `sk-or-v1-…`-shaped sentinel and some inline-Python patterns
  as credential/destructive — I switched to non-credential-shaped sentinels and a saved probe script;
  no product behavior was affected by the hook.
