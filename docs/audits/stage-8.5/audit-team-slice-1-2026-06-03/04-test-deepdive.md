# Test Suite Deep-Dive — KimCad Stage 8.5 Slice 1 (export/import + search/sort + "My Designs")

**Audit date:** 2026-06-03
**Role:** Test Engineer
**Scope audited:** `tests/test_design_store.py`, `tests/test_webapp.py` (Stage 8.5 design endpoints), `frontend/src/components/MyDesigns.test.tsx`, `frontend/src/App.test.tsx`, `frontend/src/useHashRoute.test.ts` — covering `src/kimcad/design_store.py`, the saved-design endpoints in `src/kimcad/webapp.py`, `MyDesigns.tsx`, `App.tsx`, `useHashRoute.ts`. Frameworks: pytest + vitest/RTL.
**Auditor posture:** Balanced
**HEAD audited:** 657bc3b (branch `stage-8.5-usability`)

---

## TL;DR

This is a thoughtful, security-aware test surface — well above typical for a Slice-1 increment. The two load-bearing backend invariants that matter most (the decompression-bomb cap and the export→import round-trip with coexistence) have **real, non-vacuous** tests, which I verified by independent execution. Path-safety is well covered at the store layer and through the live HTTP thumb endpoint. The one genuine soft spot is the **frontend auto-save lifecycle**: the create-race guard (`creatingRef`), the debounced re-save, and update-in-place-on-`saved_id` are entirely untested on the client — the App test's `Workspace` stub never invokes `onModelReady`, so `persist()`/`saveDesign()` is dark in every test. The class of bug that would slip through is a **duplicate-library-entry race** from the SPA (two creates firing before the first save returns). The named zip-slip assertion is technically vacuous (checks a path nothing ever writes), though the surrounding assertions still exercise the safe path. Concurrency on the store's `_WRITE_LOCK` is untested, acceptable-but-worth-noting given the server is threaded.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 4 |
| Nit | 2 |

## What's working

- **The decompression-bomb cap is genuinely exercised, not vacuously asserted.** `test_import_rejects_an_oversized_member` (test_design_store.py:185) monkeypatches `_MAX_IMPORT_MEMBER` to 8 and proves the same archive that imports under the real cap is rejected and nothing is written. I confirmed independently: the identical zip imports `True` under the 64 MiB cap and `False` under cap=8, with `get("big1") is None`. The bounded read `f.read(_MAX_IMPORT_MEMBER + 1)` (design_store.py:306) is the real mechanism and the test pins it.
- **Export→import round-trip with coexistence is tested at both layers.** Store-level (`test_export_then_import_round_trips`, line 145) and through the real HTTP stack (`test_designs_export_import_round_trip`, test_webapp.py:1576) both assert the imported design gets a *fresh* id, *coexists* with the original (`len == 2`), and *reopens with sliders restored* (`reopened.get("parameters")`). The webapp test runs against a real `DesignStore` on a tmp dir via `_serve_with_designs`, not a mock — a true integration test.
- **Path-safety is covered at the store API and the live endpoint.** `_safe_id` is directly unit-tested (line 58) and every id-taking method has a traversal-rejection assertion. I probed `_safe_id` adversarially (backslash, `C:abc`, null byte, bare/multiple dots, pure-separator strings) — all correctly rejected. The thumb endpoint has a *live* traversal test that plants a real `thumb.png` at the traversal target and asserts the secret bytes are not served (`test_designs_thumb_endpoint_rejects_traversal`, test_webapp.py:1513).
- **The never-raises / clean-error contract is well exercised.** Corrupt meta degrades (`test_list_degrades_on_a_corrupt_meta`), unwritable root returns `False` not an exception (`test_save_is_best_effort_on_an_unwritable_root`), garbage import → 400 not 500 (`test_designs_import_rejects_garbage`, store-level `test_import_rejects_a_non_design_or_zip_slip_archive`), export of a missing/unsafe id → `None`/404.
- **The stale-snapshot save bug has a sharp regression test.** `test_save_after_rerender_persists_the_rerendered_parameters` (test_webapp.py:1526) re-renders `wall` 2.0→3.0 then asserts the reopened design persisted 3.0, with an inline comment naming the bug it guards. This is exactly the tests-with-fixes culture the rubric credits.
- **Frontend debounce tests are deterministic.** `RightPanel.test.tsx` uses `vi.useFakeTimers()` + `advanceTimersByTime`, not wall-clock waits — no flakiness. The out-of-order re-render guard (`App.test.tsx` TEST-002) uses manually-resolved promises, also deterministic.

## What couldn't be assessed

- **CI history / flake history** — not available in this environment; flakiness judged by reading test mechanics, not run history.
- **The live OrcaSlicer path** — out of scope by instruction (already passed via the pre-push hook on HEAD); `test_live_web_design_then_slice_then_download` is correctly `@pytest.mark.live` and skipped under `-m "not live"`.
- **Real concurrent save/prune behavior** — there is no concurrency test for the store, so the `_WRITE_LOCK`/atomic-write race is judged by inspection only (see TEST-004).

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (backend), vitest + React Testing Library (frontend) |
| Test pyramid shape | Strong unit layer (store, `_safe_id`, parseHash) + real-socket HTTP integration for every endpoint; component tests at the network boundary. No browser E2E (acceptable at this altitude). |
| Coverage tool | None configured/observed; no coverage number reported — judged on actual covered paths. |
| Reported coverage (if any) | n/a |
| Flakiness posture | Clean. One self-documented bounded `time.sleep(0.5)` in `test_concurrent_identical_slices_run_once` (slice path, out of Slice-1 scope) that is "under-cover, never flaky-FAIL" by construction. Frontend uses fake timers. |
| CI blocking? | Pre-push hook runs the full suite incl. live slicing (per project memory); not independently re-verified here. |

**Observed counts (run by me, HEAD 657bc3b):** `test_design_store.py` **16 passed**, `test_webapp.py` **59 passed** → **75 passed** combined (28s). Frontend vitest **56 passed across 8 files** (2.3s); in-scope Slice-1 cases: MyDesigns 10, App 3, useHashRoute 2.

---

## Findings

> **Finding ID prefix:** `TEST-`
> **Categories:** Coverage / Shortcut / Flakiness / Quality / Ergonomics / Mocking / Regression / CI

### [TEST-001] — Major — Coverage / Mocking — Frontend auto-save lifecycle (create-race guard, debounce, update-in-place) is entirely untested

**Evidence**
`App.tsx` implements the whole client-side persistence loop: `persist()` (lines 59–96) auto-creates a library entry on first frame, guards a concurrent create with `creatingRef` (lines 48, 69–70, 85), debounces re-saves (`RESAVE_DEBOUNCE_MS`, line 92), and carries `saved_id` forward on re-render (line 139) so a saved part updates in place. The trigger is `handleModelReady` → `persist()`, wired via `onModelReady={handleModelReady}` (App.tsx:223).

In `App.test.tsx` the `Workspace` mock (lines 19–37) accepts only `{rerendering, onRerender, result}` — it does **not** accept or call `onModelReady`. So `handleModelReady` never fires, `persist()` is never called, and `saveDesign` (mocked at line 12) is never asserted. I grepped all frontend tests: the only `saveDesign` reference is the unasserted mock; no test references `creatingRef`, `onModelReady`, `persist`, the debounce, or `toHaveBeenCalledTimes` on a save. The `creatingRef` guard — a real concurrency invariant that prevents a duplicate library entry when a re-render races the initial create — has zero client coverage.

**Why this matters**
The class of bug that slips through: a **duplicate "My Designs" entry** created when the viewport frames a part and a near-simultaneous re-render both reach `persist()` before the first `saveDesign` resolves. The `creatingRef` guard is the only thing preventing it; if a refactor drops or inverts it, no test fails. The backend update-in-place is covered (`test_save_update_in_place_keeps_one_entry`), but that only protects the path *after* the client correctly reuses `saved_id` — it can't catch the client firing two creates. Auto-save is the headline Stage-8.5 promise ("your work is kept automatically"); its correctness is currently asserted nowhere on the client.

**Blast radius**
- Test files affected: `frontend/src/App.test.tsx` — the `Workspace` mock needs an `onModelReady` prop and a button to invoke it; a new test should assert `saveDesign` is called exactly once across an overlapping create + re-render.
- Adjacent code: `handleModelReady` (App.tsx:100), `persist` (App.tsx:59), `captureRef` (App.tsx:43, 65), `Viewport.onModelReady` (Viewport.tsx:68). The same stub gap means `captureThumbnail` wiring is also untested end to end.
- Shared state: `creatingRef`, `resaveTimer`, `resultRef.saved_id` — all client refs; no server/migration impact.
- User-facing: a duplicated library card, or a stuck "not saved" state, would reach users silently.
- Migration: none.
- Related findings: TEST-002 (no api-layer test for `saveDesign`/`importDesign`), TEST-004 (store concurrency untested — the server side of the same race class).

**Fix path**
Extend the `App.test.tsx` `Workspace` mock to accept `onModelReady` and expose a "frame-model" button that calls it (returning a stub `captureThumbnail`). Add a test: design a part, trigger `onModelReady`, fire a re-render before the first `saveDesign` resolves (manual promise), and assert `saveDesign` was called exactly once (create), then again with the returned `saved_id` (update) — never twice as a create. This directly pins the `creatingRef` invariant.

### [TEST-002] — Minor — Coverage — New Stage-8.5 api.ts functions have no unit tests (notably `importDesign`'s distinct fetch/error path)

**Evidence**
`frontend/src/api.test.ts` covers `postDesign`, `postRender`, `designIdFromMeshUrl`, `getOptions`, `postSlice`. None of the eight Slice-1 functions are tested: `getDesigns`, `saveDesign`, `reopenDesign`, `renameDesign`, `deleteDesign`, `duplicateDesign`, `exportDesignUrl`, `importDesign` (api.ts:227–281). Seven are thin `getJson`/`postJson` wrappers (low risk), but `importDesign` (api.ts:272) is different: it uses a raw `fetch` with a binary body, its own `Content-Type: application/zip`, and its own `readJson`/`throwIfNotOk` error handling rather than the shared helper.

**Why this matters**
`importDesign`'s bespoke error path (a non-2xx from `/api/designs/import` → thrown readable error) is only exercised indirectly via the mocked component test (`MyDesigns.test.tsx:118`, which mocks `importDesign` itself, so the real fetch/error code never runs). A regression in its error handling — e.g. swallowing a 400 and returning `{id: undefined}` — would pass every current test. `exportDesignUrl`'s `encodeURIComponent` is also untested (a missing encode would break ids with special chars, though server ids are hex).

**Blast radius**
- Adjacent code: `readJson`, `throwIfNotOk` helpers in api.ts; the `MyDesigns` import flow that consumes the result.
- User-facing: a broken import error message ("That file couldn't be imported." vs. a silent no-op).
- Migration: none.
- Related findings: TEST-001 (same module's `saveDesign` untested at unit level).

**Fix path**
Add api.test.ts cases for `importDesign` (200 returns `{id}`; non-2xx throws the backend message; non-JSON body throws a readable error) using the existing `fetch` mock pattern. One assertion that `exportDesignUrl('a/b')` encodes the slash is cheap insurance.

### [TEST-003] — Minor — Quality — The named zip-slip assertion is vacuous (checks a path nothing ever writes)

**Evidence**
`test_import_rejects_a_non_design_or_zip_slip_archive` (test_design_store.py:164) plants a `../evil.txt` member and asserts `not (tmp_path / "evil.txt").exists()` (line 182). I verified two things independently: (1) `import_bytes` reads only the three known names by exact match and writes them into the new design dir, so `evil.txt` is never written *anywhere* (confirmed: only `mesh.stl` + `meta.json` land under the root). (2) Even a *naive* `extractall` on Python 3.14 sanitizes `../evil.txt` to `designs/<id>/evil.txt` (inside the dest), and the design dir is `tmp_path/designs/<id>/`, so a naive bug would land it at `tmp_path/designs/<id>/evil.txt` or `tmp_path/designs/evil.txt` — **never** `tmp_path/evil.txt`. The asserted path can't be written by either the safe code or the plausible buggy code, so the assertion cannot fail.

**Why this matters**
The test's *name* promises zip-slip protection, but the specific anti-traversal line pins nothing — a reviewer reading the suite would over-trust it. The good news: the *surrounding* assertions in the same test (the valid design still imports `True`, i.e. the malicious member doesn't abort the import) and the exact-name-only design itself are the real, sound defense. This is a labeling/precision issue, not a security hole — the code is genuinely zip-slip safe.

**Blast radius**
- Test files affected: `tests/test_design_store.py:164`.
- User-facing: none (code is safe).
- Related findings: none.

**Fix path**
Make the assertion bite: after the import, assert the design dir contains *exactly* `{meta.json, mesh.stl}` (no `evil.txt`), and/or assert `evil.txt` is absent from `tmp_path/designs/<x3-dir>/` and its parent. Optionally add a member named `mesh.stl` plus a sibling absolute-path member to prove only the known names are read.

### [TEST-004] — Minor — Coverage — The store's `_WRITE_LOCK` / atomic-write under concurrency is untested; the server is threaded

**Evidence**
`tests/test_design_store.py` has no thread/concurrency test (grep for `thread|race|concurrent` finds only `test_atomic_meta_is_valid_json_after_save`, which is single-threaded — it confirms `os.replace` left valid JSON, not that a concurrent reader never sees a half-write). The store's `_WRITE_LOCK` (design_store.py:36) and `_atomic_write_json` (line 293) serialize save/rename/delete/duplicate/import/prune, and the web server is `ThreadingHTTPServer`, so concurrent writes are genuinely reachable (two tabs; auto-save racing a manual save/rename; a save racing a `_prune`).

**Why this matters**
A regression that drops the lock or makes a write non-atomic (e.g. writing `meta.json` directly instead of via temp+replace) would let a concurrent `list()`/`get()` read a torn meta and skip/corrupt a design — and no test would fail. At this altitude (local, single-user) the *probability* is low, which is why this is Minor not Major, but the guard is load-bearing and the threaded server makes the race real, not theoretical.

**Blast radius**
- Test files affected: `tests/test_design_store.py` (add one threaded test).
- Adjacent code: every `with _WRITE_LOCK:` block; `_prune` (design_store.py:280) which calls `list()` then `rmtree`.
- User-facing: a transiently-missing or corrupt design card under concurrent edits.
- Migration: none.
- Related findings: TEST-001 (client-side create-race, the same race class one layer up).

**Fix path**
Add a test that spawns N threads each doing `save(...)` with distinct ids while one thread loops `list()`, asserting `list()` never raises and the final count is correct; and a save-vs-prune test (cap shrunk) asserting no exception and the cap is honored. Keep it bounded (join with timeout) to avoid CI flake.

### [TEST-005] — Nit — Coverage — Sort-order branches (`oldest`, `name`) are not asserted

**Evidence**
`MyDesigns.tsx` `shown` (lines 178–186) sorts by `newest`/`oldest`/`name`. `MyDesigns.test.tsx` covers search filtering and the no-matches state but never changes the sort `<select>` to assert `oldest` or `name (A–Z)` reorders the grid. Slice 1's title explicitly includes "search/sort."

**Why this matters**
A broken comparator (e.g. `localeCompare` reversed, or `oldest` using the wrong field) ships silently. Low impact — cosmetic ordering — hence Nit.

**Fix path**
One test: render two designs, switch the sort select to "Oldest first" and "Name (A–Z)", assert DOM order via `getAllByRole`/`closest('.kc-design-card')` sequence.

### [TEST-006] — Nit — Quality — `_safe_id` accepts unicode letters and Windows reserved device names

**Evidence**
I probed `_safe_id`: `"é"`, `"con"`, `"NUL"` all return `True` because `str.isalnum()` accepts unicode letters and the guard doesn't blocklist reserved device names. No test documents this. Server-minted ids are uuid4 hex, so these never arise in practice, and crucially none of them *escape the root* — `root/NUL/...` stays inside the store; there is no traversal. On Windows `NUL` as a directory name is reserved and could misbehave, but it cannot read another design or leave the store.

**Why this matters**
Purely defensive precision. The escape invariant (the one that matters) holds; this is a "could be tighter" note, not a defect.

**Fix path**
Optional: tighten `_safe_id` to ASCII-only (`re.fullmatch(r"[A-Za-z0-9_-]+")`) and add a one-line test pinning that `"é"` and reserved names are rejected. Not required for ship.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@skip` | 0 in-scope (1 conditional `@pytest.mark.skipif` for the 3MF backend, justified; 1 `@pytest.mark.live`, justified) |
| `.only` (left in) | 0 |
| `TODO: add test` / similar | 0 in scope |
| Empty assertion / placeholder | 0 |
| `--retry` / retries normalized | No |

No left-in shortcuts. The two conditional skips are principled (a missing 3MF backend, and the live-slicer marker), each with an explaining docstring.

## Blind spots by class

- **Client-side write concurrency** (duplicate-create race) — `creatingRef` untested (TEST-001).
- **Store write concurrency** (torn meta under threaded writes) — `_WRITE_LOCK` untested (TEST-004).
- **api.ts binary import error path** — `importDesign`'s bespoke fetch/error code never runs unmocked (TEST-002).
- **Sort comparators** — `oldest`/`name` ordering unasserted (TEST-005).
- **`_safe_id` unicode/reserved-name edge** — accepted but harmless (TEST-006).

## Patterns and systemic observations

The backend suite is the strong half: it tests behavior (degrade paths, caps, the bomb, coexistence) rather than implementation, runs the real HTTP layer over real sockets against a real on-disk store, and includes tight regression tests tied to named bugs (the stale-snapshot save, the in-place update). The recurring weak pattern is **client-side mocking that mocks away the thing under test**: the App `Workspace` stub omits the `onModelReady` hook that drives the entire auto-save feature, leaving the headline Stage-8.5 promise (persistence "just happens") unverified on the client. One coordinated fix — a richer `Workspace` mock plus a couple of `saveDesign` call-count assertions — closes the highest-leverage gap (TEST-001) and naturally enables a fix for TEST-002.

## Appendix: test artifacts reviewed

- `tests/test_design_store.py` (16 tests, read in full + executed)
- `tests/test_webapp.py` (Stage-8.5 design endpoints, lines ~1393–1595, read in full; full file 59 tests executed)
- `frontend/src/components/MyDesigns.test.tsx` (10 tests, read in full)
- `frontend/src/App.test.tsx` (3 tests, read in full)
- `frontend/src/useHashRoute.test.ts` (2 tests, read in full)
- Code under test: `src/kimcad/design_store.py`, `src/kimcad/webapp.py` (design endpoints + store factory), `frontend/src/App.tsx`, `frontend/src/components/MyDesigns.tsx`, `frontend/src/api.ts`, `frontend/src/components/Viewport.tsx`/`Workspace.tsx` (onModelReady wiring)
- Independent verification scripts run: decompression-bomb cap (non-vacuous), zip-slip extraction path on Python 3.14, `_safe_id` adversarial probe, naive-`extractall` sanitization behavior
- Suites executed at HEAD 657bc3b: pytest (75 passed), vitest (56 passed)
