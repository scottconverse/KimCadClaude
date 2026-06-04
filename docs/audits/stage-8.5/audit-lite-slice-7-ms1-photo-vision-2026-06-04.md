# Audit Lite — Stage 8.5 Slice 7 MS-1 (backend photo → vision seed)
**Date:** 2026-06-04
**Scope:** The photo on-ramp's engine — `LLMProvider.describe_photo` (native Ollama `/api/chat`, `think:false`), `_SettingsAwareProvider`/`DemoProvider`/`FakeProvider` `describe_photo`, the `system_photo_seed.md` prompt, `POST /api/photo-seed` + `_handle_photo_seed` + `MAX_PHOTO_BYTES`/`_read_raw_body`, and the `frontend/src/api.ts` `uploadPhoto` client (+ both test files). MS-2 (the photo UI / seed-confirm flow) is out of scope.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-one-fix. The load-bearing safety/privacy properties all **hold in code**: vision is structurally pinned to the LOCAL provider (the photo never routes to cloud even when cloud TEXT is enabled), the photo is never persisted and never logged, and every failure path returns a clean 422/413 — never a 500. The native-`/api/chat` + `think:false` + image-attached wiring matches the proven live probe and is tested. The one real gap is a **test** gap, not a behavior gap: the never-auto-send invariant and the actual `_SettingsAwareProvider.describe_photo` routing method are exercised by zero tests (the happy-path test injects `FakeProvider` directly, bypassing the routing layer). Add that regression test and this is clean.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 0
- Nit: 1

## Findings

### PHOTO-001 Major: The never-auto-send privacy invariant (and the real routing method) have no test
**Dimension:** Tests
**Evidence:**
- The load-bearing trust rule is enforced in `src/kimcad/webapp.py:369-376` — `_SettingsAwareProvider.describe_photo` ignores `_active()` (which can return a cloud provider) and builds a dedicated local provider: `local = LLMProvider(self._config.llm_backend("local"))`. Correct, but untested.
- The happy-path test `tests/test_webapp.py:2198-2207` wires `FakeProvider` in as `pipeline.provider` directly (`_pipeline(provider, ...)`), so it never constructs or runs `_SettingsAwareProvider` — the routing method at webapp.py:369-376 is covered by **no** test.
- `test_llm_describe_photo_uses_native_chat_with_think_false` (test_webapp.py:2246) tests `LLMProvider.describe_photo` in isolation; it does not assert that, with `cloud_enabled=True` + a saved key + a saved `cloud_model`, the photo still goes local.
**Why it matters:** "The photo never leaves the machine, even when the user has turned on cloud TEXT" is the single most load-bearing trust property of this slice. It holds today, but a future refactor of `_SettingsAwareProvider` (e.g. someone routes `describe_photo` through `_active()` for "consistency") would silently send a user's photo to OpenRouter and **no test would fail**. A privacy guarantee with no regression test is one refactor away from breaking quietly.
**Fix path:** Add a backend test that constructs `_SettingsAwareProvider(spy_local, config)` against a settings file with `cloud_enabled=True`, a non-empty `openrouter_api_key`, and a `cloud_model` set; call `describe_photo(b"img", printer, material)`; assert (a) the spy local provider received the call, and (b) no cloud provider was built / `_active()` was not consulted for the photo (e.g. spy the cloud branch and assert it stays untouched). One small test closes the load-bearing gap.
**Blast radius:**
- *Adjacent code:* none — the fix is test-only; the production code is already correct.
- *Shared state:* the settings file (`~/.kimcad/settings.json`); the autouse `_isolate_kimcad_home` fixture (conftest.py:24) already isolates it per test, so the new test can write cloud settings without touching the dev's real file.
- *Tests to update:* none; this is a net-new test.

### PHOTO-002 Nit: `DemoProvider.describe_photo` comment claims it uses the byte length, but it ignores the image
**Dimension:** Docs (inline comment)
**Evidence:** `src/kimcad/webapp.py:280` — the comment reads "The byte length stands in for 'I saw a photo'.", but the method body (webapp.py:281-284) returns a constant string and never reads `image_bytes` (or its length).
**Why it matters:** Trivial, but the comment describes behavior the code doesn't have; a future reader may look for a length check that isn't there.
**Fix path:** Drop the second sentence of the comment (or change it to "the image is ignored; the canned seed stands in for a real vision read").

## What's working
- **Vision is structurally local-only** (`webapp.py:369-376`): a dedicated `LLMProvider(config.llm_backend("local"))` is built for every photo, so the cloud-routing in `_active()` is unreachable from the photo path. The photo can't auto-send even with cloud TEXT enabled — exactly the trust rule.
- **Never persisted, never logged:** `_handle_photo_seed` (webapp.py:1147-1168) reads the bytes, passes them to `describe_photo`, returns the seed, and discards the bytes — no disk write, no design store. `log_message` is a no-op (webapp.py:629-630), and even the stdlib default would log only the request line, never the body. No `print` of the image anywhere.
- **Never-500:** `_read_raw_body` (webapp.py:1424-1439) checks the declared Content-Length *before* reading (413 + `close_connection` on oversize, 400 on empty), so memory is bounded at 12 MiB and an oversized upload is rejected without reading. The `describe_photo` call is wrapped `try/except Exception → 422` (webapp.py:1159-1163), and an empty/blank seed is a 422 (webapp.py:1164-1167) — every failure is a clean, friendly status, verified by the 413/422/422 tests.
- **Correct native wiring:** the `/api/chat` URL derivation (`urlsplit` → replace path with `/api/chat`, llm_provider.py:255-260) correctly drops `/v1` and targets Ollama's native endpoint at root; `think:false` and the base64 image are set (llm_provider.py:274-277); the wiring test (test_webapp.py:2246-2279) pins all three. Matches the proven live probe.
- **Honesty by construction:** the seed is plain text that re-enters the existing text→DesignPlan path — the same trust boundary as a typed prompt; it never becomes geometry directly, and `_strip_fences` (llm_provider.py:284) keeps stray markdown out of it. The prompt (`system_photo_seed.md`) is well-aimed: one part, rough/estimated mm only ("a photo carries NO scale"), 1–3 plain sentences, and an explicit "say so if you can't make out a part."
- **Client guard mirrors the server:** `uploadPhoto` (api.ts:293-310) rejects an oversized file up front with a precise message (no doomed request), wraps `fetch` for a friendly network-failure message, and surfaces the backend error on a non-2xx. Both client paths are tested (api.test.ts:82-99).
- **Verified this pass:** `pytest -k "photo or describe_photo"` → 5 passed; `ruff check` on the four changed backend files → All checks passed.

## Watch items
- *Truncated upload:* `_read_raw_body` returns `self.rfile.read(declared)` without checking the actual length matches the declared Content-Length (shared with the proven import path). A truncated photo just yields partial bytes → vision fails → 422, so it degrades safely — but worth a glance if MS-2 ever surfaces upload-progress states.
- *Request-thread hold (MS-2 concern):* `describe_photo` blocks the request thread for up to the local backend's `timeout_s` while the CPU-bound vision model runs (the live probe took ~18s). MS-2's UI needs a clear "Reading your photo…" state and should tolerate a long, single in-flight call — already on the MS-2 plan; noting it so it isn't lost.

## Escalation recommendation
No escalation needed. One Major (a test gap, not a behavior defect) + one Nit, on a small, well-contained diff whose load-bearing properties hold in code. audit-lite is the right altitude; the full `audit-team` runs at the Slice 7 slice-end as planned.
