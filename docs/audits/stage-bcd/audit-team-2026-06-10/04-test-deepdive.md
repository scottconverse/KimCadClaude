# Test Suite Deep-Dive — KimCad (Stage B/C/D stage gate)

**Audit date:** 2026-06-10
**Role:** Test Engineer
**Scope audited:** ONLY the Stage B/C/D test changes landing at commit `5a07381` (Stage B `60a4181`, Stage C `3feaff5`, Stage D `5a07381`): `tests/test_printability.py` (new), `tests/conftest.py` (import probe + `_fake_keyring`), `tests/test_settings_store.py` keyring additions, `tests/test_trust_boundary.py`, the updated `tests/test_webapp.py` cloud-key tests, `frontend/src/App.test.tsx` additions, `frontend/src/components/ModelHealthPill.test.tsx` rewrite, and the walkthrough-flagged Settings key-storage disclosure gap.
**Auditor posture:** Adversarial (stage gate)

---

## TL;DR

The Stage B/C/D test work is mostly the real thing: the new printability tests drive genuine trimesh geometry through `validate_mesh → run_gate` (I verified the "0.16s real OpenSCAD" test actually executes `tools\openscad\openscad.exe` — a direct timed render of the same SCAD took 0.13s and produced a real 1720-byte 3MF), the webapp cloud-key tests were correctly upgraded to assert the sentinel-on-disk contract over a real threaded HTTP server, and the `_fake_keyring` hermeticity holds for every in-process test. Two Majors: the headline "always-on" real-OpenSCAD contract test is `skipif`-gated **outside** the CI no-green-by-skip assertion (which only watches `-m live`), joining a wider pattern of ~10 binary-gated non-live tests; and the ENG-001 `key_storage` disclosure chain (API field → SettingsPanel/FirstRunWizard note) has zero tests above the store method — exactly what the walkthrough flagged. The Stage C `test_trust_boundary.py` photo-routing test is near-tautological — but the routing invariant is genuinely pinned by a much stronger pre-existing test in `test_webapp.py`, so that downgrades to a Minor quality issue, not a coverage hole.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 5 |
| Nit | 2 |

## What's working

- **The real-geometry seam tests assert what they claim** — `tests/test_printability.py:29-79` builds real trimesh boxes and asserts the *computed* report (watertight, `n_bodies`, `stray_bodies`, bbox to `pytest.approx`, volume 8000mm³) before asserting the gate verdict, so a `validate_mesh` computation regression can no longer hide behind hand-built `MeshReport` fixtures. The stray-vs-nested case (`:50-70`) tests **both directions** — two separated solids must warn, a sealed hollow (outer shell + inverted cavity skin) must not — which is the exact false-positive class the split exists for and only exercises with real geometry.
- **The 0.16s "real OpenSCAD" test really drives the binary** — verified empirically: `render_scad` with `tools\openscad\openscad.exe` on the same `use <library/box.scad>; box(20,20,20);` source completed in 0.133s wall (OpenSCAD's manifold backend on a trivial part) and wrote a 1,720-byte `part.3mf`. The test's speed is legitimate, not evidence of a stub. The default `Pipeline` renderer is the real `render_scad` (`src/kimcad/pipeline.py:359,375-384`), and the autouse `_default_cadquery_backend_off` fixture ensures no CadQuery rescue can mask an OpenSCAD failure.
- **The webapp cloud-key tests were upgraded honestly** — `tests/test_webapp.py:2615-2657` now asserts the file holds the literal `@keyring` sentinel AND that the secret string is absent from the raw file text AND absent from stdout/stderr, all through real HTTP requests against the threaded server. That's runtime-path verification, not grep-passing.
- **The LOAD-BEARING photo/sketch routing tests are exemplary** — `tests/test_webapp.py:2890` and `:2939` spy on which backend key `LLMProvider` is constructed with (`built == [cfg.llm_backend("local").key]`) and rig `_active()` to raise `AssertionError` if the cloud-capable router is even consulted. These catch precisely the realistic regression (routing vision through `_active()`).
- **`_fake_keyring` hermeticity holds for everything in-process** — every pytest gets an in-memory keyring (`tests/conftest.py:168-177`); I verified `src/kimcad/cadquery_worker.py` imports neither `keyring` nor `settings_store` (the only Python child process tests spawn), and the only other real child is `openscad.exe`. `keyring` is imported in exactly one production module (`settings_store.py`). No current test can reach the real Windows Credential Manager.
- **Fixture ordering is a non-issue (verified, not assumed)** — `_isolate_kimcad_home` (conftest.py:126) is defined before `_fake_keyring` (conftest.py:169) and pytest runs same-scope autouse fixtures in definition order, but neither fixture's *setup* constructs a `SettingsStore` or reads settings — both only install independent monkeypatches. The `SettingsStore.__init__` migration (the only path that touches the keyring at construction time) runs inside test bodies, after both patches are live; teardown reverses safely. Reordering them would change nothing today.
- **The conftest import probe fails honestly** — `tests/conftest.py:26-38` turns a broken install into one `pytest.UsageError` line, and the geometry-backend gate (`:96-101`) deliberately goes RED on CI (`UsageError`) while skipping locally — the team explicitly reasoned about green-by-skip and rejected `xfail` for the right reason.
- **The App draft/confirm tests assert behavior, not implementation** — `App.test.tsx:486-540` proves the cancelled first design re-seeds the landing with the user's exact prompt plus the "picked up where you left off" note, and that `confirm()` returning false keeps the run alive. The supersede tests resolve promises out of order and assert the seq-guard drops stale results — real race coverage.
- **The ModelHealthPill rewrite tests live-region semantics properly** — `ModelHealthPill.test.tsx` asserts the `role=status` region is persistently mounted and *empty* when healthy, that "Check again" keeps the button mounted/focused (`aria-disabled`, `document.activeElement`) during the in-flight re-check, and that recovery is announced. That's a11y behavior testing, not snapshotting.
- **Shortcut hygiene is clean** — 0 `.skip`/`.only`/`.todo` in 25 vitest files, 0 `TODO/FIXME` in pytest files, no retry config anywhere. All 25 `skipif`s have honest reasons.
- **Everything runs** — scoped suites: 32 pytest pass in 0.90s (including the real-OpenSCAD test, executed not skipped on this machine); full frontend suite: 300/300 pass in 25 files (8.7s).

## What couldn't be assessed

- **CI history / flake rate** — no access to past runs from this audit; flakiness posture judged from config only (no retries configured anywhere — good).
- **Coverage numbers** — no coverage tool is wired into the default invocation; nothing claimed, so no claimed-vs-actual gap to report.
- **A real NVDA/VoiceOver pass** for the UX-007 `aria-hidden` thinking-row change — the code comment itself defers fuller live-region scoping to a real screen-reader session; jsdom can't assess it either.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (907 collected) + Vitest 4 / Testing Library (300 tests, 25 files, jsdom) |
| Test pyramid shape | Heavy unit + genuine integration (real threaded HTTP server, real OpenSCAD/OrcaSlicer/CadQuery behind `live`/`skipif` gates); no browser E2E in-repo (Playwright walkthrough run separately) |
| Coverage tool | none wired (no number claimed) |
| Flakiness posture | clean — no retries, races tested with explicit promise resolvers |
| CI blocking? | yes — `scripts/ci.sh` full suite + a dedicated "no green-by-skip" execution assertion, but that assertion only covers `-m live` (see TEST-001) |

---

## Findings

> **Finding ID prefix:** `TEST-`

### [TEST-001] — Major — CI — The "always-on" real-OpenSCAD contract test can silently skip on CI, and it joins a pattern of ~10 binary-gated tests outside the no-green-by-skip guard

**Evidence**
`tests/test_printability.py:91` — `@pytest.mark.skipif(not _openscad_present(), ...)` with **no `live` marker**. The CI step that enforces "assert EXECUTION, not collection" (`.github/workflows/ci.yml:97-111`, the stage-A TEST-002 remediation) runs `pytest -m live` and fails on any skip — so this test is invisible to it. Stage B's commit message (`60a4181`) calls it "an always-on real-OpenSCAD Pipeline.run contract test"; the always-on claim is not enforced anywhere. The same shape exists at `tests/test_webapp.py:1582,1606`, `tests/test_geometry.py:227,237`, `tests/test_library_modules.py:79`, `tests/test_template_bench.py:145`, `tests/test_pipeline_templates.py:168`, `tests/test_templates.py:341` — all binary-gated, none `live`-marked, all able to skip-to-green.

**Why this matters**
`_openscad_present()` resolves through `Config.load().binary_path("openscad")` — a `local.yaml` redirect, a tools-cache key change, or a path drift makes every one of these tests skip while CI stays green. That is the exact failure mode the project's own stage-A TEST-002 finding was remediated to prevent; the CI comment even names "a local.yaml redirect" as a skip source — but only for the `live` subset. The bug class that slips through: a real-renderer contract drift (RenderResult shape, 3MF fallback, gate inputs) shipping unverified while everyone believes the contract test is "always-on." Mitigation today: the CI provision step does `Test-Path tools\openscad\openscad.exe` and throws on fetch failure, so the binary is normally present — the exposure is config/path drift, not the common case, which is why this is Major rather than Critical.

**Blast radius**
- Adjacent code: all 8+ binary-gated, non-`live` tests listed above share the gap; fix once (policy), apply everywhere.
- Shared state: the `live` marker semantics — note `_default_cadquery_backend_off` (conftest.py:104) skips its stub for `live`-marked tests, which is harmless for the OpenSCAD test (OpenSCAD succeeds before any CadQuery fallback) but should be stated when re-marking.
- User-facing: none directly; this is CI-signal integrity.
- Tests to update: `tests/test_printability.py:91` plus the listed files if the pattern fix is adopted.
- Related findings: stage-A TEST-002 (same root cause, partially remediated).

**Fix path**
Either mark the binary-gated contract tests `live` (the existing CI assertion then enforces execution), or extend the CI assertion to a second pass: run the binary-gated subset with `-ra` and fail on any skip, mirroring lines 104-110. The one-line version: add `@pytest.mark.live` to `test_real_openscad_render_through_pipeline_matches_fake_contract` and the `test_webapp.py`/`test_geometry.py` siblings.

---

### [TEST-002] — Major — Coverage — The ENG-001 key-storage disclosure chain is untested above the store method: no pytest asserts the API field, no vitest renders the note

**Evidence**
`store.key_storage()` is tested in both directions (`tests/test_settings_store.py:94,124`) — but that is the *source variable*, not the runtime path. Nothing above it is tested:
- No test in `tests/test_webapp.py` asserts that `GET /api/settings` returns the `key_storage` field (`src/kimcad/webapp.py:500-501,1156,1240,1289`) — grep for `key_storage` across `tests/` hits only the two store-level lines.
- No vitest renders the disclosure note in either state: `frontend/src/components/SettingsPanel.tsx:357-364` ("kept in this computer's secure credential store" vs "Anyone who can read your files could read it") and `frontend/src/components/FirstRunWizard.tsx:318` are both unasserted; `SettingsPanel.test.tsx` and `FirstRunWizard.test.tsx` contain no `key_storage` fixture variation. (Flagged by the Stage B/C/D walkthrough; confirmed.)

**Why this matters**
This is the honesty feature of Stage C: when the credential store is unusable, the UI must *disclose* that the key sits in a plain file. Today the payload field could be dropped, renamed, or the ternary inverted (claiming "secure credential store" while the key is in a readable file — a false security claim to the user) and 1,207 tests stay green. Note also that when `key_storage` is `undefined` (field missing), both components render the *keyring* (reassuring) branch — so the failure mode of a dropped field is the over-promising text, the worst direction.

**Blast radius**
- Adjacent code: `SettingsPanel.tsx` and `FirstRunWizard.tsx` duplicate the note logic — a fix/regression in one can miss the other; same for their `modelLabel` duplication.
- Shared state: the `SettingsResponse.key_storage?` optional typing (`frontend/src/api.ts:316`) is what makes the silent-drop possible.
- User-facing: the Settings cloud section and wizard recap — the two trust moments of cloud setup.
- Tests to update: add to `tests/test_webapp.py` (settings GET/POST round-trip asserting `key_storage`), `SettingsPanel.test.tsx`, `FirstRunWizard.test.tsx` (render both values, assert the file-fallback warning text appears for `"file"` and not for `"keyring"`).
- Related findings: TEST-003 (same trust-boundary theme), walkthrough observation 2026-06-10.

**Fix path**
Three small tests: (1) webapp test — save a key, assert `GET /api/settings` includes `key_storage: "keyring"` with the fake keyring and `"file"` with a `FakeKeyring(fail=True)`; (2)+(3) one vitest per component rendering both `key_storage` values and asserting the warning copy. ~30 lines total.

---

### [TEST-003] — Minor — Mocking — The Stage C photo-routing test in `test_trust_boundary.py` is near-tautological; the real pin lives elsewhere

**Evidence**
`tests/test_trust_boundary.py:85-112` (`test_describe_photo_routes_local_even_with_cloud_enabled`) monkeypatches `LLMProvider.describe_photo` **at class level** and asserts it was called. But the cloud provider built by `_SettingsAwareProvider._active()` is *also* an `LLMProvider` instance (`src/kimcad/webapp.py:436`), so the realistic regression — `describe_photo` refactored to route through `_active()`, sending the photo to OpenRouter — would still hit the patched class method and the test would **pass**. It also doesn't prove `build_web_pipeline` applies the `_SettingsAwareProvider` wrapper: a bare `LLMProvider`/`FallbackProvider` would satisfy it equally. The module docstring overclaims: "the photo on-ramp's local-only promise is pinned by a test, not by wiring convention."

**Why this matters**
By itself this would be Critical — a privacy promise guarded by a test of the mock. It is Minor only because the invariant **is** properly pinned by the pre-existing `tests/test_webapp.py:2890` (`test_photo_never_routes_to_cloud_even_when_cloud_enabled`, added in `c6778d1`), which spies on the constructed backend key and rigs `_active()` to raise. The residual risk is human: a future cleanup that trusts the `test_trust_boundary.py` docstring and deletes the "duplicate" strong test would leave only the tautology guarding the promise.

**Fix path**
Rewrite the trust-boundary test in the style of its `test_webapp.py` twin (assert the constructed backend is `llm_backend("local")` and trip on `_active()`), or reduce it to a `build_web_pipeline`-wiring smoke test with a comment pointing at `test_webapp.py:2890` as the load-bearing pin. Recommend also correcting the module docstring.

---

### [TEST-004] — Minor — Coverage — `settings_store` concurrency and failure-path code is entirely untested (the case the prompt's threading design exists for)

**Evidence**
`src/kimcad/settings_store.py:27` (`_WRITE_LOCK`), `:71-86` (`_atomic_write_json` with an 8-attempt Windows `PermissionError` retry/backoff loop), and the read-modify-write in `update()` exist specifically for "a concurrent reader on the threaded web server" (module docstring). No test exercises any of it: no two-thread concurrent `update()` test, no test injecting `PermissionError` into `os.replace` to verify the retry loop and the final tmp-file cleanup, no cross-instance lost-update test.

**Why this matters**
Bug class that slips through: someone removes or per-instances the lock (regression invisible — all current tests are single-threaded), or breaks the retry loop's cleanup path (`tmp.unlink` on final failure), and settings saves start intermittently failing or leaving `.tmp` litter on exactly the platform (Windows) and deployment (threaded server) the code targets. Stakes are limited to user settings (recoverable), hence Minor not Major.

**Fix path**
Add (1) a thread-pool test firing N concurrent `update()`s with distinct keys and asserting all land; (2) a monkeypatched `os.replace` that raises `PermissionError` twice then succeeds (assert success + no `.tmp` left), and always-raises (assert `update()` returns False and the prior file is intact).

---

### [TEST-005] — Minor — Coverage — Sentinel collision is unhandled and untested: a key value literally `"@keyring"` in file-fallback mode corrupts the disclosure

**Evidence**
`src/kimcad/settings_store.py:184-193`: in file-fallback mode (`stored=False`) the raw value is written verbatim — `current[_SECRET_KEY] = v`. If `v == "@keyring"`, the file now holds the sentinel with no credential-store entry, so `key_storage()` (`:125-126`) reports `"keyring"` (false — the UI then shows the reassuring "secure credential store" note) and `all()` (`:137-148`) drops the key entirely (it silently vanishes). No test covers a key value equal to the sentinel in either storage mode.

**Why this matters**
Pathological input (no real OpenRouter key is `@keyring`), but it is reachable from the Settings text box and the failure is the *dishonest* direction: the UI claims keyring storage that doesn't exist. This is as much a code finding as a test finding — flagging here per the gate's scope.

**Fix path**
Reject (or prefix-escape) a submitted key equal to `_KEYRING_SENTINEL` in `update()`; add two tests (keyring mode: round-trips fine — it already does; file mode: rejected or escaped, `key_storage()` stays honest).

---

### [TEST-006] — Minor — Coverage — Stage D's conditional UX changes shipped without tests; only 3 of ~9 UX fixes in `5a07381` gained assertions

**Evidence**
Covered: UX-001 and UX-005 (`App.test.tsx:486-540`), UX-008 (`RightPanel.test.tsx:114-122`). Not covered: UX-003's conditional slice-caution — `frontend/src/components/ExportPanel.tsx:175-181` renders "Slicing with cautions…" only when `gate_status === 'warn'`, and `ExportPanel.test.tsx` was not touched; UX-007's `aria-hidden` thinking row (`ChatPanel.tsx:187-196`) has no assertion; UX-013's chip swap, UX-006's Enter hint, and UX-010's photo-discard line are copy-only and also unasserted (`ChatPanel.test.tsx` matches neither the old "Add mounting holes" nor the new "Make it smaller" — no stale test, but no pin either).

**Why this matters**
The two conditional ones are real logic: the warn-gate caution could invert (showing the caution on a clean pass, or a clean bill on a warn part — the exact trust problem UX-003 fixed) and the suite stays green. The project's culture is tests-with-fixes (UX-001/005/008 all got them in the same commit); these are the exceptions, worth closing while the context is fresh. Copy-only items are lower value — flag once, don't belabor.

**Fix path**
One `ExportPanel.test.tsx` case per gate status (warn shows the caution, pass does not); one `ChatPanel.test.tsx` assertion that the busy thinking row carries `aria-hidden="true"`.

---

### [TEST-007] — Minor — Quality — Suite hermeticity vs the real vault and real `~/.kimcad` is in-process only; subprocess tests bypass it by convention, not enforcement

**Evidence**
`_fake_keyring` and `_isolate_kimcad_home` are monkeypatches — they do not survive into child processes. Tests that spawn real Python children exist: `tests/test_cadquery_runner.py:296-313,368` runs `src/kimcad/cadquery_worker.py` directly via `subprocess.run`. Today this is safe — verified: the worker imports neither `keyring` nor `settings_store`, and `keyring` is imported in exactly one module (`settings_store.py:63`); the other real child is `openscad.exe` (not Python). But nothing *enforces* that a future worker change (e.g. reading a setting) won't silently re-open the real Credential Manager / real `~/.kimcad` from inside a test.

**Why this matters**
The Stage C commit claims "suite hermetic vs the real vault" — true now, by a one-import-site invariant nobody is watching. The bug class: a worker/CLI change adds a settings read, and tests start mutating the developer's real credential store with fake values (or worse, deleting the real `KimCad/openrouter_api_key` entry via a `clear()` path).

**Fix path**
Cheap guard: a test asserting `"keyring" not in` / `"settings_store" not in` the worker's imports (e.g. scan `cadquery_worker.py`'s module-level imports, or run the worker child with a poisoned `KIMCAD_HOME`/`PYTHONPATH` shim that fails loudly on keyring import). Alternatively document the invariant next to `_fake_keyring`.

---

### [TEST-008] — Nit — Quality — The open-mesh repair test's OR-chained assertions can pass while saying little

**Evidence**
`tests/test_printability.py:122-125`: `assert report.repaired or report.errors` followed by a conditional `assert _codes(...).get("mesh.repaired") is Level.WARN or result.status is not Level.FAIL`. If the repair fails *and* an error is recorded, the test passes without asserting anything about the gate outcome; the final OR can be satisfied by the right-hand side alone.

**Fix path**
Split into two parametrized expectations (repair-succeeded → WARN `mesh.repaired`; repair-failed → an error recorded AND a non-PASS gate), or at least assert the specific code in the success branch without the `or`.

---

### [TEST-009] — Nit — Quality — `App.test.tsx` "does not nag when the work is already saved" never saves; it passes via the completed-design branch

**Evidence**
`frontend/src/App.test.tsx:529-539` completes a design (`designFrom`) but never clicks `frame-model`, so `saveDesign` is never called and `result.saved_id` is absent. It passes because `handleNewDesign`'s condition (`App.tsx:506-508`) only nags when `busy` or when `versions.length === 0` — a completed design has a version, so no confirm regardless of saved state. The test name asserts a property its setup never establishes; dropping the `saved_id` checks from the condition would not fail it.

**Fix path**
Either rename ("does not nag once a design has completed") or click `frame-model` and await the save before the New Design click so the name is earned.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@skip` (unconditional) | 0 |
| `skipif` (conditional, reasoned) | 25 — binary/interpreter gates; the non-`live` subset is TEST-001 |
| `importorskip` | 2 (`test_printability.py:11-12` — trimesh/numpy, redundant with the conftest probe but harmless) |
| `.only` / `.todo` (left in) | 0 |
| `TODO: add test` / `FIXME` in tests | 0 |
| `xfail` | 0 (one comment explaining why xfail was *rejected* — good) |
| `--retry` / retries normalized | no |

## Blind spots by class

- **CI green-by-skip on binary-gated, non-`live` tests** (TEST-001) — the only path by which the real-tool contracts go unverified while CI passes.
- **Runtime path of the key-storage disclosure** (TEST-002) — store-level truth, untested API/UI presentation.
- **Concurrency / Windows file-contention** in `settings_store` (TEST-004).
- **Adversarial settings input** — sentinel collision (TEST-005); other `_ALLOWED_KEYS` junk is covered.
- **Cross-process hermeticity** — by convention only (TEST-007).
- **Screen-reader reality** of the UX-007 live-region change — explicitly deferred, correctly, to a real AT session.

## Patterns and systemic observations

- **Test-with-fix culture is real here** — UX-001/005/008, ENG-002/003, TEST-004/005/006 all landed with behavior-level tests in the same commits; the Stage D copy-level changes are the partial exception (TEST-006).
- **The team already thinks about green-by-skip** (conftest CI `UsageError`, the `-m live` execution assertion) — TEST-001 is an incomplete rollout of their own principle, not a missing principle.
- **Mock discipline is generally strong** (spy-on-constructed-backend, `_active()` tripwires, AbortSignal-honoring fetch mocks) — which is why the one tautological monkeypatch (TEST-003) stands out; it's drift from their own bar, with the better pattern sitting in the same repo.
- **Duplicated UI logic without a shared test** — `modelLabel`/disclosure-note logic duplicated across `SettingsPanel.tsx` and `FirstRunWizard.tsx`; per-component tests (TEST-002) are the cheap mitigation, extraction the durable one.

## Appendix: test artifacts reviewed

- Read in full: `tests/test_printability.py`, `tests/conftest.py`, `tests/test_settings_store.py`, `tests/test_trust_boundary.py`, `frontend/src/App.test.tsx`, `frontend/src/components/ModelHealthPill.test.tsx`; `src/kimcad/settings_store.py`, relevant parts of `src/kimcad/webapp.py`, `src/kimcad/pipeline.py`, `frontend/src/components/SettingsPanel.tsx`, `.github/workflows/ci.yml`; diffs of `5a07381`, `3feaff5`, `60a4181`.
- Executed: `pytest tests/test_printability.py tests/test_settings_store.py tests/test_trust_boundary.py -q --durations=10` → 32 passed, 0.90s (real-OpenSCAD test ran, 0.16s); full vitest → 300/300; direct timed `render_scad` probe against `tools\openscad\openscad.exe` (0.133s, 1,720-byte 3MF); `pytest --collect-only` → 907 collected.
