# Test Engineer Deep-Dive — Stage 8.5 Slice 7 ("describe with a photo" on-ramp)

**Auditor:** Test Engineer (audit-team, balanced posture)
**Date:** 2026-06-04
**Scope:** the Slice 7 test diff only — `git -C C:/Users/scott/dev/kimcad diff 76c6f89..HEAD`
**Commits in scope:** `c6778d1` (MS-1 backend photo→vision seed), `39b9b09` (MS-2 on-ramp UI)

---

## Observed run results (I ran the suites — not just read them)

| Suite | Command | Result |
|---|---|---|
| Backend (full) | `.venv/Scripts/python.exe -m pytest tests -q` | **739 passed** in 116.40s |
| Backend (photo subset) | `… -k "photo or describe_photo"` | **6 passed**, 733 deselected |
| Frontend (full) | `npm run test` (vitest) | **158 passed** (14 files) |

Both match the expected counts in the brief (739 / 158). No skips, no `xfail`, no `.only`, no flaky retries observed in the Slice 7 surface.

**Test-suite shape for Slice 7:** bottom-heavy and honest — fast unit/contract tests with a small number of real-HTTP integration tests (`http.client` against an actually-served handler). The two load-bearing trust properties (never-route-to-cloud, native-endpoint wiring) each have a dedicated, **non-vacuous** test. The blind spots are concentrated in error/empty boundary paths and two frontend branches (`onDrop`, "Use a different photo").

---

## Non-vacuity verification (I mutated the product, not the tests)

A passing suite is evidence the tests passed — nothing more. I confirmed the four highest-value guards actually bite by mutating the **product** code and re-running. Every mutation was reverted; the tree is clean.

| Guard | Mutation applied to product | Result |
|---|---|---|
| **Never-route-to-cloud** (`test_photo_never_routes_to_cloud_even_when_cloud_enabled`) | `_SettingsAwareProvider.describe_photo` rewritten to `return self._active().describe_photo(...)` | **FAILED** with the exact guard message: `describe_photo must not route a photo through the cloud-capable _active()`. The patched `_active()` genuinely raises — the test cannot pass trivially. |
| **Native-endpoint wiring** (`test_llm_describe_photo_uses_native_chat_with_think_false`) | endpoint changed `/api/chat` → `/v1/chat/completions`; `think: False` → `True` | **FAILED**: `'http://localhost:11434/v1/chat/completions'.endswith('/api/chat')` is False. The endpoint assertion bites; the `think`/`images` assertions follow on the same captured body. |
| **Empty-seed → 422** (`test_photo_seed_empty_seed_is_422`) | removed the `if not seed: 422` guard, returned 200 with blank seed | **FAILED**: `assert 200 == 422`. The other two photo tests still passed (correctly — they don't exercise the empty path). |

**Conclusion: the load-bearing guards are real, not decorative.** This is the single most important question the brief posed, and the answer is favorable. Credit is due (see "What's working").

---

## Findings

### TEST-701 — Major — Coverage — The 400 "Empty upload" branch of `/api/photo-seed` is untested

**Evidence:**
- Product: `src/kimcad/webapp.py:1424` `_read_raw_body` returns 400 `{"error":"Empty upload."}` when `declared <= 0` (line 1436–1438), and 413 when oversized (1432–1434). `_handle_photo_seed` (1144) relies on this guard and comments `# _read_raw_body already sent a 413/400` (line 1154).
- Tests: `tests/test_webapp.py` covers **only** the 413 path — `test_photo_seed_oversized_is_413` (line ~2219) posts `content_length=MAX_PHOTO_BYTES + 1`. There is **no** test that posts a zero/empty Content-Length to `/api/photo-seed` and asserts 400. The frontend never sends an empty body (it guards on `file.size`), so the 400 is a server-only contract with no test on either side.

**Why this matters:** the brief explicitly calls this out. The 400-vs-413 split is a real branch in the request guard; a refactor of `_read_raw_body` (shared with `/api/import`, `MAX_IMPORT_BYTES`) could silently turn the empty-photo case into a 500 (e.g. `rfile.read(0)` → empty bytes → `describe_photo(b"")` → provider behavior undefined) and no Slice 7 test would catch it. A 0-byte POST is a realistic shape (a broken upload, a curl typo, a proxy that strips the body).

**Blast radius:**
- Adjacent code: `_read_raw_body` is shared by `/api/import` (line 1415). The import path *does* exercise the empty/oversized guard via its own tests, so the helper itself isn't wholly untested — but the photo endpoint's reliance on it is unverified for the 400 case.
- User-facing: an empty upload should yield a clean "Empty upload." 400, not a traceback. Currently unverified for this route.
- Migration: none.
- Tests to update: add one — see fix path. No existing test asserts the wrong behavior, so nothing breaks.

**Fix path:** add `test_photo_seed_empty_upload_is_400` mirroring the 413 test but with `content_length=0` (or omit the body), asserting `st == 400`. ~6 lines, reuses `_post_photo`.

---

### TEST-702 — Major — Coverage — `uploadPhoto`'s server-error mapping path is untested

**Evidence:**
- Product: `frontend/src/api.ts` `uploadPhoto` (diff ~line 290) calls `readJson(res)` then `throwIfNotOk(res, data)` (api.ts:153) so a non-2xx server response surfaces the server's `{error: …}` string to the UI (the 413/422 friendly messages from `_handle_photo_seed`).
- Tests: `frontend/src/api.test.ts` `describe('uploadPhoto')` has exactly two cases — the **200 happy path** (posts to `/api/photo-seed`, returns the seed) and the **client-side oversized reject** (`rejects.toThrow(/too large/i)` with **no** request). There is **no** test where the mocked `fetch` returns `{ok:false, status:422, json:()=>({error:'…'})}` and asserts `uploadPhoto` rejects with that server message. The `ok:false` cases at api.test.ts:38/47/152 belong to *other* endpoints (postDesign / getHealth), not `uploadPhoto`.
- The component test (`PhotoOnramp.test.tsx`) mocks `uploadPhoto` **itself** (`vi.mock('../api', … uploadPhoto: vi.fn())`), so it exercises the component's reaction to a thrown error — but **never** the api.ts code that turns a 422/413 HTTP response into that thrown error. So the server→error-message wiring is mocked on both sides of the seam and tested on neither.

**Why this matters:** this is finding-class #4 from the role brief ("a test that mocks the thing it's supposed to exercise is a test of the mock"). The friendly server messages ("Couldn't read that photo…", "File too large.") are the user's only feedback on a vision failure or an oversized upload that slips past the client guard (e.g. a body the browser doesn't size-check, or a server-side 413 on a body just under the client cap but over the server cap — the caps are equal here at 12 MiB, but a boundary-off-by-one or future divergence would expose this). If `throwIfNotOk` or `readJson` regressed (e.g. swallowed the server `error` and threw a generic "Request failed"), no Slice 7 test would notice; the user would lose the actionable message.

**Blast radius:**
- Adjacent code: `throwIfNotOk` / `readJson` are shared by every `api.ts` call, so they're covered *in general* — but the photo route's reliance on them for its specific friendly strings is unverified.
- User-facing: the photo error-recovery UX (the whole point of the 422 path) rests on this seam.
- Migration: none.
- Tests to update: add one api.test.ts case — see fix.

**Fix path:** add an `uploadPhoto` case: `mockFetch(async () => ({ ok:false, status:422, json: async () => ({error:'Couldn't read that photo…'}) }))` then `await expect(uploadPhoto(file)).rejects.toThrow(/couldn.t read/i)`. ~8 lines. This closes the mock-both-sides gap end-to-end with the component test.

---

### TEST-703 — Minor — Coverage — The `onDrop` (drag-and-drop) path is entirely untested

**Evidence:**
- Product: `PhotoOnramp.tsx:94` `onDrop(e)` calls `e.preventDefault()`, guards on `disabled`, and routes `e.dataTransfer.files?.[0]` into the **same** `handleFile` the file-picker uses (line 97). Wired on the idle affordance button (`onDrop={onDrop}`, line 129).
- Tests: `PhotoOnramp.test.tsx` — **0** references to `onDrop`, `drop`, or `dataTransfer` (grep confirmed). Every test drives input via `pickFile` → `fireEvent.change` on the file input. The drag path is never fired.

**Why this matters:** drag-drop and file-pick are advertised as equal on-ramps ("pick (or drop) a photo" — component header comment line 5). They converge on `handleFile`, so the **downstream** behavior (reading → confirm/error) is covered. The *only* untested logic unique to `onDrop` is the `preventDefault()` (so the browser doesn't navigate to the dropped image) and the `disabled` short-circuit. That's a thin, low-risk surface — hence Minor, not Major: a regression here can't corrupt data or leak the photo; worst case the drop does nothing or the browser navigates away. Still, "drop a photo" is a promised affordance with zero verification.

**Blast radius:**
- Adjacent code: shares `handleFile` with the tested pick path — low risk of silent divergence.
- User-facing: drag-drop affordance only.
- Tests to update: add one — see fix.

**Fix path:** add a test that `fireEvent.drop` on the affordance with a `dataTransfer: { files: [file] }`, then assert the reading/confirm flow runs (and that `preventDefault` fired, via a spy). ~10 lines.

---

### TEST-704 — Minor — Coverage — The "Use a different photo" re-pick branch is untested

**Evidence:**
- Product: `PhotoOnramp.tsx:188` — in the confirm card, a `kc-btn-ghost` button "Use a different photo" calls `openPicker` (re-opens the file dialog **without** resetting state), distinct from "Cancel" (`reset`, line 191) and "Use this as a starting point" (`useSeed`, line 183). The `error` phase has its own re-pick via "Try another photo" (line 202) — which **is** indirectly covered (the error tests assert that button renders).
- Tests: `PhotoOnramp.test.tsx` covers `Use this as a starting point` (the edited-seed test), `Cancel` (returns to affordance + revokes URL), and the error-state buttons render. It does **not** click "Use a different photo" from the confirm card, so the re-pick-while-in-confirm transition (pick a 2nd file → new `handleFile` → preview swap + `clearPreview` of the prior blob URL) is unverified.

**Why this matters:** re-picking mid-confirm is a real flow (the rough seed looks wrong, user wants a clearer shot without discarding the on-ramp). The `clearPreview()` inside `handleFile` (line 67) revokes the *previous* object URL on a re-pick — an object-URL leak guard exactly parallel to the one TEST'd for Cancel (the MS2-001 assertion). That leak-guard is tested for the Cancel/reset path but **not** for the in-confirm re-pick path, which exercises the same `URL.revokeObjectURL` line via a different trigger.

**Blast radius:**
- Adjacent code: `handleFile`/`clearPreview` — shared with the tested first-pick, low divergence risk.
- User-facing: re-pick flow + object-URL hygiene on repeated reads.
- Tests to update: add one — see fix.

**Fix path:** in a confirm-state test, click "Use a different photo", `pickFile` a second file, assert `URL.createObjectURL` called twice and `revokeObjectURL` called for the first blob, and the reading→confirm flow re-runs. ~10 lines. Closes the object-URL leak-on-re-pick blind spot.

---

### TEST-705 — Nit — Mocking — The 200-seed test injects a `FakeProvider`; the never-route test exercises the real `_SettingsAwareProvider.describe_photo`

This is **not** a defect — it's worth a one-line note for the reader. Two distinct providers are exercised, and the split is correct:
- `test_photo_seed_returns_a_rough_seed` injects `conftest.FakeProvider` (whose `describe_photo` returns a canned seed and bumps `photo_calls`) — it verifies the **endpoint→provider→200 JSON** wiring and that vision ran once (`photo_calls == 1`). Good: the `photo_calls == 1` assertion would catch a double-call or a no-call.
- `test_photo_never_routes_to_cloud_even_when_cloud_enabled` exercises the **real** `_SettingsAwareProvider.describe_photo` (the routing decision under cloud-enabled settings), spying on which backend key is built (`built == [local.key]`, `"custom_openrouter" not in built`).

So the trust property is tested on the **real router**, and the 200 contract on a **fake provider** — the right division. No action needed. (Flagged only because the brief asked me to distinguish the two; padding this to Minor would be inflating the count.)

---

## Blind spots I considered and DID NOT flag (with reasons)

- **"No test runs the real vision model."** Out of altitude per the brief — the wiring test pins the native `/api/chat` + `think:false` + image body, the committed live probe covers the real path, and `DemoProvider`/`FakeProvider` make the on-ramp exercisable. Correctly out of scope.
- **413 oversized path** — IS tested (`test_photo_seed_oversized_is_413`), and the client-side oversized reject IS tested (`uploadPhoto` rejects `/too large/i` with no request). Good.
- **vision-raises → 422 (not 500)** — IS tested (`test_photo_seed_unreadable_is_422_not_500`, `_BadVision` raises `RuntimeError`, asserts 422 + "photo" in error). Non-vacuous: the bare `except Exception` in `_handle_photo_seed` (line 1161) is the thing under test, and a 500 would fail the assertion.
- **Content-Type not validated server-side** — `_handle_photo_seed` ignores the declared Content-Type and feeds raw bytes to vision. This is intentional (the local vision model tolerates/downsizes; a non-image just yields a blank seed → the tested 422 empty path). Not a Slice 7 test gap — it's a deliberate design choice with the empty-seed 422 as the backstop, which IS tested. No finding.
- **`onSeed` prop plumbing through `ChatPanel`** — `ChatPanel.test.tsx` adds `onPhotoSeed: vi.fn()` to the default props (line 29 of the diff), so the prop is wired into the render harness. Thin (it only proves the prop is accepted, not invoked) but the invocation is covered by `PhotoOnramp`'s own `onSeed` tests. Acceptable; no finding.

---

## What's working (credit where due)

1. **The two load-bearing trust guards are genuinely non-vacuous.** I proved it by mutating the product (not the tests): re-routing the photo through `_active()` fails the never-route test with its exact assertion message, and switching to `/v1` fails the wiring test. The patched `_active()` really throws; the wiring test really pins the native endpoint, `think:false`, and the attached image — not just a 200. This is exactly the discipline the brief demanded, and it holds.
2. **Honest error/empty modeling on the backend.** Three of the six backend tests are negative-path: oversized→413, vision-raises→422-not-500, empty-seed→422-not-silent-200. That's an unusually high error-path ratio for a new feature — the opposite of the "happy-path-only" smell. The empty-seed→422 guard is non-vacuous (mutation-confirmed).
3. **Real-HTTP integration, not mock-the-server.** The backend photo tests serve the actual handler over `http.client` (`_post_photo` builds a raw request to assert the 413 path without sending a body). These are integration tests that actually integrate at the HTTP layer.
4. **The frontend tests assert behavior the user sees**, not implementation: the reading state + the "never leaves your machine" privacy promise, the editable seed value, **focus moves to the seed field** (MS2-002 AT announcement), **onSeed is NOT called from merely reading** (the explicit-confirm trust rule), the **edited** seed (not the raw seed) reaches `onSeed`, blank-seed → friendly failure not silent success, and the **object-URL revoke on Cancel** (MS2-001 leak guard). These are real regressions-in-waiting, well chosen.
5. **No shortcuts.** No `.skip`/`.only`/`xfail`/`TODO: test`/`assert True` in the Slice 7 diff. No retry config. The `FakeProvider.describe_photo` fixture is freshly added for this slice (not a six-times-edited drifted fixture).

---

## Summary for the orchestrator

- **Findings:** Blocker 0 · Critical 0 · Major 2 · Minor 2 · Nit 1 (total 5)
- **Top findings:**
  - TEST-702 (Major) — `uploadPhoto`'s server-error mapping is mocked on both sides of the seam and tested on neither; a regression in the 413/422 friendly-message path would ship unnoticed.
  - TEST-701 (Major) — the 400 "Empty upload" branch of `/api/photo-seed` has no test (only 413 is covered).
  - TEST-704 (Minor) — "Use a different photo" re-pick branch + its object-URL leak guard untested.
  - TEST-703 (Minor) — drag-and-drop (`onDrop`) path entirely untested.
  - TEST-705 (Nit) — provider split (FakeProvider vs real router) is correct; noted, not a defect.
- **Blockers:** none.
- **Culture/pattern note (for the exec report):** the two trust-critical guards were verified non-vacuous by product-mutation — they bite. Error-path coverage is strong on the backend (3 of 6 tests are negative paths). The blind spots are not in the core property (cloud-isolation is well guarded) but in **secondary boundary branches**: one untested server contract (400 empty), one mock-both-sides seam (uploadPhoto error mapping), and two thin frontend branches (onDrop, re-pick). All four are additive ~6–10-line tests; none requires touching product code or asserting current-wrong behavior, so zero existing tests break.
