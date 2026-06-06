# 01 — Principal Engineer Deep-Dive

**Audit:** KimCad Stage 8.5 Slice 7 — "describe with a photo" on-ramp (Surface D)
**Role:** Principal Engineer (backend correctness / security / architecture / data-provenance)
**Date:** 2026-06-04
**Scope:** the Slice 7 diff only — `git -C C:/Users/scott/dev/kimcad diff 76c6f89..HEAD`
**Commits in scope:**
- `c6778d1` Slice 7 MS-1: backend photo→vision seed (local-only)
- `39b9b09` Slice 7 MS-2: the "describe with a photo" on-ramp UI (Surface D)

**Backend focus files reviewed (in full):**
- `src/kimcad/llm_provider.py` — `LLMProvider.describe_photo` (lines 238–285)
- `src/kimcad/webapp.py` — `DemoProvider.describe_photo` (278–285), `_SettingsAwareProvider.describe_photo` (369–376), `_handle_photo_seed` (1147–1168), `_read_raw_body` (1424–1439), wiring (296–304)
- `src/kimcad/prompts/system_photo_seed.md`
- `tests/conftest.py` — `FakeProvider.describe_photo` (71–75)
- `tests/test_webapp.py` — photo tests (2178–2328)

---

## Verification performed (run, not just read)

| Check | Result |
|---|---|
| `pytest tests -k "photo or describe_photo" -q` | **6 passed**, 733 deselected |
| `ruff check src/kimcad/llm_provider.py src/kimcad/webapp.py` | **All checks passed** |
| Live demo server (`:8767`) — small image body | **200** + canned seed JSON |
| Live demo server — oversized Content-Length (`MAX_PHOTO_BYTES+1`) | **413** `{"error":"File too large."}`, body never read |
| Live demo server — Content-Length `0` | **400** `{"error":"Empty upload."}` |
| Resolved `local` backend (`Config.load().llm_backend("local")`) | `base_url=http://localhost:11434/v1`, `model=gemma4:e4b`, `timeout_s=1200.0` |
| Grep of the diff for `log/print/write/open/save/persist` of photo bytes | none — photo never logged or written to disk |

All four load-bearing invariants verified as **HELD**. Details below.

---

## Invariant verification (the four load-bearing rules)

### Invariant 1 — the photo NEVER auto-sends off the machine. **HELD.**

Traced every path the photo bytes / base64 can take:

1. HTTP body → `_handle_photo_seed` (`webapp.py:1152`) reads raw bytes into a local `image` var.
2. `image` is passed to `pipeline.provider.describe_photo(...)` (`webapp.py:1160`).
3. In the real server, `pipeline.provider` is `_SettingsAwareProvider` (`webapp.py:296,300`). Its `describe_photo` (`webapp.py:369–376`) **builds a fresh `LLMProvider(self._config.llm_backend("local"))` and does NOT call `_active()`** — so even with cloud TEXT fully enabled, the photo uses the local backend.
4. `LLMProvider.describe_photo` derives the chat URL from `self.backend.base_url` of the **local** backend (`http://localhost:11434/...`), base64-encodes the image, and POSTs to that local host only.
5. The bytes are never written to disk, never logged, never persisted, and `_handle_photo_seed` returns only the resulting text `seed`.

The dedicated regression `test_photo_never_routes_to_cloud_even_when_cloud_enabled` (`test_webapp.py:2280–2328`) sets `cloud_enabled=True` + a real OpenRouter key + cloud model, then asserts the built backend is `llm_backend("local").key` and that `_active()` is never consulted (it monkeypatches `_active` to raise). This is exactly the right test and it passes. **Strong implementation.**

### Invariant 2 — best-effort / never-500. **HELD.**

- Oversized → `_read_raw_body` checks `Content-Length` *before* reading (`webapp.py:1432–1435`), sends **413**, sets `close_connection=True`, returns `None`; the body is never read so memory is bounded by the header check. Verified live.
- Empty (`Content-Length <= 0`) → **400** (`webapp.py:1436–1438`). Verified live.
- Vision exception → caught by the broad `except Exception` (`webapp.py:1161`) → clean **422**. Regression `test_photo_seed_unreadable_is_422_not_500` passes.
- Empty/blank seed → `(seed or "").strip()` then `if not seed` → **422** (`webapp.py:1164–1167`). Regression `test_photo_seed_empty_seed_is_422` passes.
- `cfg.printer(None)` / `cfg.material(None)` are evaluated **inside** the try (they are arguments on `webapp.py:1160`), so a config error there is also a 422, not a 500. (One narrow residual is ENG-003 below.)

### Invariant 3 — injection / provenance. **HELD.**

The seed is plain untrusted **text**. `_handle_photo_seed` returns it to the client as `{"seed": ...}`; it does NOT feed it onward into design generation in this handler. The user reviews/edits it and submits it through the existing `/api/design` text path, which runs the same `DesignPlan` validation as a typed prompt — so the seed cannot become geometry directly or smuggle anything past `DesignPlan`. The native-chat request body (`llm_provider.py:248–260`) is built entirely from server-controlled literals plus `self.backend.model_name`, the loaded system prompt, and the base64 image — there is no interpolation of attacker-controlled strings into the JSON (it's built via `json.dumps`, not string concatenation). The system prompt is a static repo asset. No injection surface introduced.

### Invariant 4 — correctness of the native-chat call. **HELD.**

- URL derivation (`llm_provider.py:243–247`): `urlsplit` on `http://localhost:11434/v1` → `urlunsplit((scheme, netloc, "/api/chat", "", ""))` = `http://localhost:11434/api/chat`. The path is **replaced**, so `/v1` is dropped and the call targets root `/api/chat`. Fallback branch handles a base_url with no scheme/netloc via `.removesuffix("/v1") + "/api/chat"`. Verified the live `local` base_url really carries `/v1`, so this derivation is both correct and necessary.
- `think: False` is set (`llm_provider.py:258`); `stream: False`; `options.temperature=0`, `num_predict=400`. Image base64'd and attached under `messages[1].images` (`llm_provider.py:255`).
- Response extraction: `seed = ((data.get("message") or {}).get("content") or "").strip()` (`llm_provider.py:283`) — an empty model response yields `""` → 422 upstream, not a blank 200.
- `urllib.request.urlopen(req, timeout=self.backend.timeout_s)` (`llm_provider.py:281`) uses the backend timeout (1200s for local). Verified.
- Regression `test_llm_describe_photo_uses_native_chat_with_think_false` asserts `.endswith("/api/chat")`, `think is False`, and image attached. Passes.

---

## What's working

- **The trust rule is implemented at the architecturally correct layer.** Forcing local vision in `_SettingsAwareProvider.describe_photo` rather than per-call-site means there is exactly one chokepoint, and it's covered by a test that fails loudly if anyone later routes a photo through `_active()`. This is the single most important property of the slice and it's done well.
- **Memory safety is correct by construction.** The `Content-Length`-before-read guard (reused from the import path, `MAX_PHOTO_BYTES=12 MiB`) means a hostile declared-huge upload is rejected without ever allocating the body. Live-verified.
- **The error taxonomy is clean and honest.** 413 / 400 / 422 each map to a real, distinct condition; the broad `except` is justified and commented (`# never leak a traceback; vision is best-effort`). No 500 path is reachable through the documented failure modes.
- **The "thinking-mode eats the budget" fix is real and well-documented.** The docstring on `describe_photo` (`llm_provider.py:241–249`) records *why* the native `/api/chat` + `think:false` path exists (the `/v1` path returns empty for gemma4 vision). That context will save a future maintainer hours.
- **Test coverage is proportionate and adversarial.** Six tests cover: happy path + local-provider-ran assertion, oversized, vision-exception, empty-seed, native-endpoint wiring, and the cloud-never-routes guard. The wiring test monkeypatches `urlopen` (no real model needed) — exactly the right altitude for CI.
- **Provenance is conservative.** The system prompt explicitly tells the model a photo has no scale and to mark sizes as estimates; the seed is returned for human confirmation, never auto-committed to geometry. Good product instinct encoded in the prompt.

---

## Findings

### ENG-001 (Minor) — Hygiene/Architecture: imports for `describe_photo` are function-local
**Category:** Hygiene
**Evidence:** `src/kimcad/llm_provider.py:238–240` — `import base64`, `import urllib.request`, `from urllib.parse import urlsplit, urlunsplit` are inside the method body. Similarly `_SettingsAwareProvider.describe_photo` does `from kimcad.llm_provider import LLMProvider` at call time (`webapp.py:374`).
**Why this matters:** Function-local imports add a small per-call cost and slightly obscure the module's dependency surface. The `webapp.py` late import is *deliberate and load-bearing* — the test `test_photo_never_routes_to_cloud_even_when_cloud_enabled` relies on patching `lp.LLMProvider` at call time, and module-top stdlib imports for `base64`/`urllib` are conventional. This is a near-Nit; flagged only for consistency with the rest of the module, which imports stdlib at the top.
**Fix path:** Move `import base64` / `import urllib.request` / `from urllib.parse import ...` to module top in `llm_provider.py`. **Leave the `webapp.py` late import as-is** — it is required for the monkeypatch-based trust test; if moved to module top, document why it must stay patchable. Optional; no behavior change.

### ENG-002 (Minor) — Correctness/Compatibility: `think:false` silently does nothing on older Ollama, and an empty response is indistinguishable from a refusal
**Category:** Correctness
**Evidence:** `src/kimcad/llm_provider.py:258` sends `"think": False`. Older Ollama builds (pre-`/api/chat` `think` support) ignore unknown top-level fields rather than erroring. If a user runs such a build, gemma4's thinking mode can again consume the token budget and `message.content` comes back empty → `seed == ""` → a 422 "Couldn't read that photo." The user sees a generic photo-failure message even though the real cause is a stale Ollama, not a bad photo.
**Why this matters:** It's a confusing support path: a correct photo + correct model + outdated Ollama presents identically to an unreadable photo. Low exposure (most users on current Ollama; the live probe that motivated this fix presumably ran a current build), so Minor.
**Blast radius:**
- Adjacent code: only `describe_photo`; the text path uses the OpenAI-compatible `_complete` and is unaffected.
- User-facing: a stale-Ollama user gets a "bad photo" message; no data risk.
- Migration: none.
- Tests to update: none; would add one asserting behavior is graceful (it already is — just opaque).
**Fix path:** Out of strict scope to fix now (no minimum-Ollama-version contract exists in this slice). Recommend a follow-up: when the seed is empty, log at debug a hint that an outdated Ollama can cause empty vision output, or surface a one-line "if this keeps happening, update Ollama" in the 422 copy. Not a blocker for the slice.

### ENG-003 (Minor) — Correctness: `cfg = get_config()` is the one statement outside the never-500 try
**Category:** Correctness
**Evidence:** `src/kimcad/webapp.py:1158` — `cfg = get_config()` is evaluated before the `try:` on line 1159. `get_config()` lazily calls `Config.load()` (`webapp.py:567–572`).
**Why this matters:** If `Config.load()` raised here, the handler would emit a 500 rather than the intended best-effort 422. In practice this is near-unreachable: `Config.load()` already ran at server boot (`webapp.py:293`) and on every other request via `get_config()`, and the result is memoized in `config_box`, so by the time a photo POST arrives the config is loaded and cached. The window is effectively nil, hence Minor.
**Why not higher:** `printer(None)`/`material(None)` — the more plausible failure points — are already *inside* the try (arguments on line 1160). Only the cached config fetch sits outside.
**Fix path:** Optionally move `cfg = get_config()` inside the `try` (it's cheap and removes the last theoretical 500 path). One-line change; no test churn.

### ENG-004 (Nit) — Hygiene: non-ASCII characters in user-facing error/copy strings
**Category:** Hygiene
**Evidence:** `src/kimcad/webapp.py:1156` uses a curly apostrophe and an em dash ("Couldn’t read that photo — ..."). The seed prompt and DemoProvider seed also use em dashes.
**Why this matters:** Purely cosmetic/consistency — these are valid UTF-8 and serialized correctly (verified live: the seed came back as `—`-escaped JSON and parses fine). No defect. Flagged once only because some teams keep source strings ASCII for grep/diff ergonomics; this team evidently does not, which is a fine choice.
**Fix path:** None required. Leave as-is unless the team has an ASCII-source convention.

---

## What I could not check (stated honestly)

- **Live vision accuracy** — out of altitude by directive, and correctly so; the real model output quality is a product concern, not an engineering-correctness one. The DemoProvider + the committed wiring test + the live probe cover the wiring.
- **Real-hardware print** — out of scope (post-release per project plan).
- **Behavior against a genuinely old Ollama build** — not exercised; see ENG-002. The `think:false` contract is asserted on the request side only (the test mocks `urlopen`), which is the correct CI altitude, but no integration test runs a real Ollama of either vintage.

---

## Summary

No Blockers, Criticals, or Majors. All four load-bearing invariants (local-only vision, never-500, injection/provenance, native-chat correctness) are implemented correctly and backed by proportionate, adversarial tests; the suite (6) passes and ruff is clean. The slice is, from a backend-engineering standpoint, **ready** — the four findings are Minor/Nit polish, none blocking.

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 1 |
| **Total** | **4** |
