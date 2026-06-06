# 01 — Principal Engineer Deep-Dive

**Audit:** KimCad Stage 8.5 Slice 6 — in-app Settings screen
**Repo / branch / HEAD:** `C:/Users/scott/dev/kimcad` · `stage-8.5-usability` · `44c248c`
**Diff under review:** `16f9290..HEAD` (excluding `docs/audits`, `src/kimcad/web/assets` — built bundle)
**Posture:** balanced; SECURITY + SAFETY weighted highest
**Date:** 2026-06-04
**Reviewer focus:** architecture, correctness, security, performance, data provenance

---

## Verdict

**0 Blocker / 0 Critical / 0 Major / 1 Minor / 2 Nit.**

The four load-bearing invariants all hold, verified against source (not the bundle) and confirmed by green tests:

1. **The OpenRouter key is never echoed in full or logged** — VERIFIED. Every read path masks or consumes-without-returning; the request logger is a no-op; the store only persists `_ALLOWED_KEYS`.
2. **The experimental gate never bypasses the printability check, and never auto-runs for the consumer** — VERIFIED. `needs_experimental` returns before any codegen/mesh; when codegen is allowed it flows through the same gate; the consumer SPA always sends `experimental:false`.
3. **Local always works (cloud degrade-safe)** — VERIFIED. `_SettingsAwareProvider` falls back to local on every gap and reads settings per call; the `api_key` override doesn't break the env path (41 provider tests pass).
4. **Model trust (rule 1)** — VERIFIED. No Chinese model and no menu of alternatives is surfaced; gemma4:e4b is THE local model; the cloud model is the user's own free-text choice with no hardwired vendor.

Test evidence: `tests/test_webapp.py + test_settings_store.py + test_pipeline.py` → **113 passed**; `tests -k "llm or provider"` → **41 passed**.

---

## Findings

### ENG-S6-001 (Minor · Security/Hygiene) — `_mask_key` reveals the last 5 chars of a key shorter than ~5 chars

**Evidence:** `src/kimcad/webapp.py:359-364`

```python
def _mask_key(key: Any) -> str | None:
    if not isinstance(key, str) or not key:
        return None
    return "•" * 16 + key[-5:]
```

For a key shorter than 5 characters the whole key is shown (`key[-5:]` returns the entire string), and the fixed 16-dot prefix doesn't reveal length, so this is bounded. A real OpenRouter key is ~40+ chars, so in practice only the last 5 of a long secret are ever shown — the intended, approved behavior. The edge only matters for a user who pastes a near-empty placeholder, where echoing it back is harmless (it's already on their own screen, on their own machine).

**Why this matters:** No real exposure — the last 5 of a long key is not a reconstruction risk, and the only "leak" is of a string the user just typed locally. Flagged purely so the team is aware the dot count is cosmetic (always 16) and not length-proportional; a reviewer skimming the UI shouldn't infer key length from the mask.

**Fix path (optional):** if absolute strictness is wanted, guard `key[-5:]` to only reveal the tail when `len(key) > 5` (e.g. `key[-5:] if len(key) > 5 else ""`). Not required for ship.

---

### ENG-S6-002 (Nit · Architecture) — `_cloud_cache` in `_SettingsAwareProvider` is unbounded and keyed on `(key, model)`

**Evidence:** `src/kimcad/webapp.py:319, 337-347`

The cloud-provider cache is keyed by `(api_key, model)` and never evicted. In the single-user, loopback consumer app this is correct and negligible (a user changes their key/model a handful of times in a lifetime, each entry is a thin `LLMProvider`). It is a Nit, not a leak: the cache lives in process memory only, is never serialized, and holds the same key the user already saved to disk by design.

**Why this matters:** Only relevant if a future multi-tenant/server mode lands (already anticipated by the `ENG-503` per-id-lock note at `webapp.py:520-522`). At that point an unbounded per-(key,model) cache would retain every distinct user key in RAM for the process lifetime.

**Fix path:** none needed now. If a multi-client mode lands, cap the cache (small LRU) alongside the `render_lock`/`slice_lock` per-id work already flagged for that mode.

---

### ENG-S6-003 (Nit · Correctness) — `model-status` cloud branch reports `running:true`/`model_present:true` without probing

**Evidence:** `src/kimcad/webapp.py:910-911, 937-942`

When cloud is enabled+configured, the status returns `{"model": cm, "backend": "cloud", "running": True, "model_present": True}` without contacting OpenRouter. This is the documented, deliberate choice (line 938-939: "reachability isn't probed in-band — it would need the key"), and it is the right altitude: probing would require spending the user's key on a health check and would couple the Settings screen to a live network call. The UI surfaces the key state separately (`has_cloud_key`), so the user isn't misled about whether a key is present.

**Why this matters:** A user with a cloud key that is invalid/expired sees "ready" in Settings; the actual failure surfaces only when a design call runs (and then degrades to local per invariant 3). Acceptable — the alternative (a live probe) is worse for a consumer app, and the local fallback means an invalid cloud key never breaks a design.

**Fix path:** none. Documented and correct for this posture.

---

## Invariant verification (the four load-bearing checks)

### Invariant 1 — the OpenRouter key is never echoed in full or logged ✓

Traced every reference to `openrouter_api_key` / `api_key` / `_mask_key` / `log_message` in `webapp.py`:

| Path | Location | Behavior |
|---|---|---|
| `_SettingsAwareProvider._active()` | `webapp.py:333, 346` | Reads the key to build the cloud `LLMProvider`; **never returns or logs it**. |
| `settings_response()` | `webapp.py:371-375` | Emits only `has_cloud_key` (bool) + `cloud_key_masked` (`_mask_key`, last 5). The raw key is **never placed in the payload**. |
| `_handle_settings_get` (GET) | `webapp.py:873-877` | Calls `settings_response` → masked only. |
| `_handle_settings_post` (POST) | `webapp.py:978-997` | Stores the key, then returns `settings_response` → masked only. **No echo of the input.** |
| `_handle_model_status` cloud branch | `webapp.py:910-911` | Reads the key only to choose the cloud branch; returns `{"model": cm, ...}` — **model name only, never the key**. |
| `log_message` | `webapp.py:606-607` | `pass` — **no request/body logging anywhere** in the handler. |

The `_SettingsAwareProvider` reads the key from the store (`webapp.py:325`) and hands it to `LLMProvider(backend, api_key=key)` (`webapp.py:346`); the provider passes it to the OpenAI client only (`llm_provider.py:170`) — never to `print`, never to a return value. No `print`/`logging` call anywhere in `webapp.py`/`settings_store.py`/`llm_provider.py` takes the key. (`FallbackProvider` prints only the *alt backend key name*, `llm_provider.py:290-294` — a backend identifier like `cloud_deepseek`, not a secret.)

**Store can't be stuffed with arbitrary data:** `settings_store.py:35-47, 94` — `update()` skips any key not in `_ALLOWED_KEYS`. Tested at `tests/test_settings_store.py:28-32` (`unknown_field`, `nested` dropped). A crafted client cannot write arbitrary keys to `~/.kimcad/settings.json`.

**Test:** `tests/test_webapp.py:1988-2021` asserts `SECRET not in json.dumps(resp)` on **both** the POST response and a fresh GET, asserts the key *did* land on disk (the approved local plaintext posture), and asserts model-status returns only the model name. Decisive.

**Is the key ever echoed/logged?** No. Not in any GET, POST, model-status, or log path.

### Invariant 2 — experimental gate never bypasses the printability check; no consumer auto-run ✓

- **Returns before codegen/mesh:** `pipeline.py:372-381` — when `match is None and not allow_experimental`, `run()` returns `PipelineStatus.needs_experimental` *before* `_build_geometry` (called at line 393). No `generate_openscad` call, no render, no mesh. `_result_to_payload` therefore reports `has_mesh: False` (`webapp.py:151`, since `result.mesh_path` is None). Nothing unvalidated is rendered, sliced, or sent.
- **Same gate when allowed:** when `allow_experimental` is True (or a template matches), control flows into `_build_geometry` → `run_gate` (`pipeline.py:756, 805`) — the identical printability gate as every other part. Experimental does not add a bypass.
- **Consumer never auto-runs:** the web computes `allow_experimental = bool(data.get("experimental", True)) or saved_settings().get("experimental_enabled")` (`webapp.py:1135-1137`). The SPA's normal design call sends `experimental: false` (`frontend/src/api.ts:217, 219`; `App.tsx:166` default `experimental = false` → `handleSubmit` → `runDesign(submitted)` at `App.tsx:220`). Only the explicit "try the experimental generator" button sends `true` (`App.tsx:239-245`, `handleTryExperimental`). The absent-flag-default-`True` only benefits a raw API/CLI client that omits the field — a power-user/non-consumer path. The Settings toggle is a deliberate force-enable.

**Tests:** `tests/test_pipeline.py:166-175` asserts `status is needs_experimental` AND `provider.openscad_calls == 0` (codegen never ran). `tests/test_webapp.py:1923-1985` covers the consumer-false-offers, true-runs, and setting-on-auto-runs cases.

**Can the experimental path bypass the gate or auto-run for the consumer?** No. The offer returns before any geometry; codegen (when allowed) runs through the same gate; the consumer SPA always opts out.

### Invariant 3 — local always works (cloud degrade-safe) ✓

`_SettingsAwareProvider._active()` (`webapp.py:329-350`) returns the local provider when: cloud not enabled (line 331-332), key/model missing or wrong type (line 333-336), or the cloud `LLMProvider` build throws (line 348-349, broad `except` → local). Settings are read per call (`webapp.py:321-327`, wrapped — a read failure returns `{}` → local). A cloud misconfig therefore cannot break a local design.

The `api_key` override doesn't break the env path: `llm_provider.py:159-170` — an explicit key wins; when `None`, it falls back to `os.environ[backend.api_key_env]` exactly as before; the `"not-needed"` sentinel still covers a keyless local backend. The 41 `llm`/`provider` tests pass, including the env-path cases.

**Test:** `tests/test_webapp.py:2039-2065` walks no-settings→local, enabled-but-unconfigured→local, fully-configured→cloud `LLMProvider` carrying the user's model.

### Invariant 4 — model trust (rule 1) ✓

- **No menu / no Chinese model in the UI:** `frontend/src/components/SettingsPanel.tsx:222-268` renders gemma4:e4b as THE model (a health readout + concrete next-actions: start Ollama / pull the model / refresh), with explicit comments citing trust rule 1 (lines 24-25, 222-223). The only `<select>` elements (lines 167, 182) are the printer/material default pickers, not a model menu.
- **Cloud model is the user's choice, no hardwired vendor:** `SettingsPanel.tsx:270-272` (spec §7.3 cited); the config backend `custom_openrouter` has `model_name: ""` (`config/default.yaml:70-77`) and a fixed `base_url: https://openrouter.ai/api/v1`. The user supplies the model as free text; KimCad pins only the router, not a vendor.
- **Match logic is sound:** the cloud model-tag is reported verbatim (`webapp.py:911`). The gemma4:e4b presence match (`webapp.py:934`) accepts the exact tag or a `model_name + "-"` variant suffix — the `-` separator anchors the prefix so an unrelated tag can't false-match (mirrors `_installed_match` in `model_advisor.py:283-296`, which requires specific tags to match exactly). `_ollama_tags_url` (`model_advisor.py:218-228`) discards the base_url path so a proxied sub-path can't leak into the tags URL.

The `model_advisor.py` diff is a clean refactor: it extracts `_parse_tags` and adds `probe_ollama` (returns `reachable` so the UI distinguishes "Ollama down" from "model not pulled"). No catalog change; no new model surfaced as a default.

---

## What's working (credit where due)

- **The key-handling discipline is exemplary.** A single `_mask_key` chokepoint, a `settings_response` that is the *only* shaper of the Settings payload, a no-op request logger, and an `_ALLOWED_KEYS` allowlist in the store together make the "never echo/log the raw key" invariant a structural property, not a per-call promise. The trust-critical test (`test_webapp.py:1988`) asserts the negative (`SECRET not in json.dumps(...)`) on every response shape — exactly the right way to test a non-leak.
- **The experimental gate is designed to fail safe.** Returning `needs_experimental` *before* `_build_geometry` — rather than running codegen and then refusing to show it — means no unvalidated geometry is ever produced on the consumer path. The offer-don't-auto-run pattern is enforced at both the pipeline (`pipeline.py:372-381`) and the SPA (`api.ts:217`), and the absent-flag default is correctly scoped to non-consumer API/CLI callers. `provider.openscad_calls == 0` is the right assertion.
- **Cloud degrades to local at every gap.** `_SettingsAwareProvider` is a thin, correct decorator: per-call settings read (so a toggle takes effect without a restart), and a broad fallback-to-local on *any* misconfig or build failure. Local genuinely always works, which is the whole point of KimCad's local-first posture.
- **The store is atomic and best-effort.** Temp-file + `os.replace` with a Windows `PermissionError` retry/backoff (`settings_store.py:50-65`), a write lock, and a never-raises contract on both read and write — consistent with the existing history/design stores. Corrupt/non-object JSON reads as `{}` (tested), so a bad file degrades to config defaults rather than breaking the app.
- **`effective_defaults` handles stale keys gracefully** (`webapp.py:380-393`): a saved printer/material that was removed from config between sessions falls back to the shipped default rather than dangling — a real data-provenance nicety.
- **Settings POST validates at the boundary** (`webapp.py:952-987`): unknown printer/material → 400 (never silently saved); wrong-typed model/key → 400; blank clears. Input is checked against config keys, not trusted implicitly.

---

## What I could not check (altitude / honest gaps)

- The **live OpenRouter network call** and the **live gemma4:e4b model** are not exercised — out of scope (software-complete, no real model/hardware). The routing is unit-tested by *which provider is selected* (`test_webapp.py:2039`), which is the correct altitude: the decision logic is verified without spending a real key or standing up Ollama.
- **No real-hardware print** — out of scope by design.
- The **POSIX file mode** of `~/.kimcad/settings.json` is not set to `0600`. Per the engagement's stated posture this is at most a watch item, not a finding: the plaintext-key-in-home-dir is the approved consumer posture (Scott settled it — a normal local Settings field, never in repo/logs), and on the Windows target the default user-profile ACL already scopes the file to the user. Noted, not flagged.

---

## Blast radius

No Blocker/Critical/Major findings, so no blast-radius enumeration is required. The two Nits (`_cloud_cache`, `model-status` no-probe) are explicitly scoped to a hypothetical future multi-client mode and are already anticipated in-code (`webapp.py:520-522`, `ENG-503`); they carry no migration, API-contract, or test-update concern today. The one Minor (`_mask_key` short-key edge) is a self-contained one-line guard with no downstream callers beyond `settings_response`.
