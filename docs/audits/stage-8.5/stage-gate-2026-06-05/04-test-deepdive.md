# Stage 8.5 (Usability) — Test Engineer Deep-Dive

**Repo:** `C:\Users\scott\dev\kimcad`  **Branch:** `stage-8.5-usability` @ `95b25e0`
**Date:** 2026-06-05  **Role:** Test Engineer (audit-only; no source modified)

---

## Test runs I actually executed

| Suite | Command | Result |
|-------|---------|--------|
| Python (fast) | `.venv\Scripts\python.exe -m pytest -m "not live" -q` | **757 passed, 4 deselected** in 127.77s |
| Python (collect) | `pytest --collect-only -q` | **761 tests collected** |
| Frontend | `npm --prefix frontend run test -- --run` (vitest) | **249 passed across 22 files** in ~11s |

- **0 skipped** in the fast Python run. The 4 deselected are the `live` marker. Crucially, my machine HAS the OpenSCAD binary and OrcaSlicer profiles present, so every `skipif(not _binary_present())` / `skipif(not _profiles_present())` test **actually ran** (verified via `--collect-only` and `-rs`: no skips reported, only the named `live` deselections). The real-renderer cache-invalidation and reshape tests executed for real, not as skips.
- **The 2 `live` tests I did NOT run** (`test_slicer.py:526`, `test_webapp.py:477`): they invoke the real OrcaSlicer CLI. They `skipif` when the binary is absent and are deselected by `-m "not live"`. I did not run the `live` lane; I read both and they are substantive (full design->slice->download->send over a socket, with the Slice-10 estimate breakout + estimated-weight assertion).

---

## What's working (credit where due)

The Stage 8.5 test suite is **genuinely good** — well above the bar I usually see at a "usability polish" stage. Shape: **bottom-heavy Python unit + a strong layer of HTTP-over-real-socket integration** (`test_webapp.py`, 2109 lines, ~90 tests, each spinning a real `http.server` on a port and driving it with `urllib`/`http.client`), plus a **behavior-focused vitest layer** that drives components through React Testing Library; the `api.ts` module itself is unit-tested separately at the fetch seam. The only thing missing from the pyramid is a true browser E2E — and the team has a documented compensating control (the local pre-push gate runs the live OrcaSlicer proof + SPA build-reproducibility).

Specific strengths:

- **Safety invariants are tested, at the HTTP layer, not just in a helper:**
  - *Gate-failed never sliced/sent:* `test_web_refuses_to_slice_a_gate_failed_part` (`test_webapp.py:64`) — asserts `sliced is False`, `reason == "gate_failed"`, and **no `gcode_url`** in the response.
  - *Re-render invalidates the slice cache:* `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (`:1335`) is the standout — slice a passing part, re-render into a gate-FAILING shape, then assert the stale G-code 404s, re-slice refuses, AND send refuses. The binary-free version covers the invariant; `test_rerender_invalidates_a_cached_slice` (`:1407`, real renderer) proves the slicer is called twice (cache busted).
  - *Key never returned:* `test_cloud_key_saved_locally_but_never_returned_in_full` (`:2202`) and `test_model_status_cloud_never_returns_the_key` (`:2055`) assert the secret is **not anywhere in `json.dumps(response)`**, only masked (last-5), while confirming it DID land on disk (correct for a consumer local-storage model).
  - *Photo stays local:* `test_photo_never_routes_to_cloud_even_when_cloud_enabled` (`:2398`) installs a hard guard (`_active` raises) so the test fails if a photo ever touches the cloud router — even with cloud TEXT fully configured. This is the load-bearing privacy rule, tested adversarially.
- **Persistence/designs store is exhaustively unit-tested** (`test_design_store.py`, 24 tests): save/get/list/rename/delete/duplicate, **traversal-unsafe ids rejected**, **zip-slip ignored** (and pinned to exactly the 3 known files, `:185`), **oversized-member bounded read** (`:190`), corrupt-meta degrade, unwritable-root best-effort (never raises), cap-drops-oldest, orphan-dir prune, atomic JSON, export/import round-trip, ASCII-only id guard, fresh `created_at` on duplicate, and a real **threaded concurrency test** (6 writers + 4 readers, asserts no torn meta, `:243`).
- **The full designs round-trip is tested end-to-end over a socket** (`test_designs_full_round_trip`, `:1556`): design -> save -> list -> thumb bytes -> **reopen yields a fully-functional design (sliders restored, re-render works)** -> rename -> duplicate -> delete. This is the integration coverage the api-mocked component tests can't give.
- **Numeric entry + clamping is excellent** (`RightPanel.test.tsx`, 41 tests): clamp-to-max in mm AND in inches, integer rounding, sub-0.1mm change commits (guards against an over-eager no-op guard), empty/non-numeric revert, Escape-cancels-without-commit, debounce coalescing, **no re-render after unmount**, and the dual-`useUnits()`-instance lockstep test (`:673`) that a plain-`useState` refactor would regress.
- **Units round-trip** (`useUnits.test.ts:58`): mm->display->mm within 0.01mm; every `onRerender` still emits mm even when entered in inches (`RightPanel.test.tsx:590`).
- **Escape/cancel on blocking actions is tested everywhere it should be:** in-flight design cancel + keyboard-Escape (`App.test.tsx:437`), refine cancel returns to prior part with NO leaked "aborted" error (`:413`), import cancel (`MyDesigns.test.tsx:160`), photo-read cancel (`PhotoOnramp.test.tsx:129`). The AbortError-misclassification bug class is explicitly hunted.
- **A11y invariants are tested, not assumed:** focus trap AND focus-restore-to-trigger (`ShortcutsHelp.test.tsx:62`), modal focus trap (`FirstRunWizard.test.tsx:84`), `aria-current`, `aria-valuetext` with units, `aria-modal`, shortcut typing-guard + modifier-passthrough (`App.test.tsx:536,557`).
- **Honesty guards on the estimate** (`test_webapp.py:1114-1151`): weight-from-volume when slicer emits none (flagged `estimated`), prefer slicer grams when present, and the **zero-volume guard** that refuses to fabricate "0.0 g (estimated)" — stays honestly `None`.
- **Determinism done right:** the live-phase progress test (`:2528`) uses a blocking provider gated by `threading.Event`s rather than sleeps; the concurrency tests assert an invariant (max-inside-body <= 1) alongside the wall-clock interval. No `time.sleep`-based races, no `retries` config anywhere (vitest uses defaults; no retry in vite.config.ts).
- **No shortcut smells.** Grep for `.skip` / `.only` / `xit` / `xfail` / `assert True` / `TODO: test` found **zero** unjustified skips. Every `skipif` is an honest environment gate (binary/profiles/manifold3d absent) with a clear reason string. The shared `conftest.py` `autouse` fixture isolates `~/.kimcad` per test so no test reads the developer's real settings/designs (and a comment documents the exact machine-dependent flake this prevented).
- **The CI honesty is itself a strength.** `.github/workflows/ci.yml` is explicitly labelled a PARTIAL smoke check; `scripts/ci.sh` (the pre-push gate) is the authoritative SUPERSET — ruff + full pytest incl. live + vitest + SPA build-reproducibility — with a `KIMCAD_RELEASE=1` hard-fail if the frontend toolchain OR the OrcaSlicer binary is absent, and `-ra` so a green-from-skips run can't masquerade as a proven one. This team has thought hard about the "N/N passing != proven" trap.

---

## Findings

### TEST-001 (Major / Coverage) — The authoritative test gate does not run in hosted CI; "green check" on GitHub proves only a Linux pytest subset

**Evidence:** `.github/workflows/ci.yml:1-28` runs `ruff` + `pytest -q` on `ubuntu-latest` only. Its own header (`:3-9`) states it "deliberately does NOT run the frontend Vitest suite, the SPA build / build-reproducibility check, ... or the live OrcaSlicer slice proof" and that "a green check here is not equivalent to the local gate." It is also "Currently disabled to save Actions minutes." On a Linux runner the 2 `live` tests `skipif` away (no OrcaSlicer), so hosted CI proves **none** of: the 249 frontend tests, the committed-SPA-matches-source check, or the real slicer contract.

**Why this matters:** The entire frontend test layer — which is where the Stage 8.5 *usability* behavior lives (sliders, clamping, units, escape/cancel, a11y, the wizard) — has **no enforced automated gate except a developer's local Windows pre-push hook**. If a contributor pushes without `core.hooksPath .githooks` set, or CI is re-enabled and mistaken for the gate, a vitest regression or a stale committed SPA build (source changed, `src/kimcad/web` not rebuilt) ships green. The bug class: **UI behavior regressions and source/build drift land undetected** on any machine that isn't the one dev box with the hook armed.

**Blast radius:**
- Adjacent code: every `frontend/src/**/*.test.tsx` (249 tests) and the `src/kimcad/web` committed build output.
- Shared assumption: "the pre-push hook is always armed on every machine that pushes." That's a per-clone `git config`, not enforced by the repo.
- User-facing: a regressed slider/clamp/units/escape behavior, or a UI change that was coded but never rebuilt into the served bundle, reaches users.
- Migration: none — additive. Recommend a hosted job (Linux can run vitest headless + the SPA build-reproducibility diff; only the live OrcaSlicer slice is Windows/binary-bound) that runs vitest + `npm run build` + `git diff --quiet src/kimcad/web`. Keep the live slice as the local/release-only gate.
- Tests to update: none.
- Related findings: none (this is a process gap, not a code gap).

*Severity rationale:* Major, not Critical — the local pre-push gate IS a real superset and the team documents it honestly, so on the primary dev box the coverage is enforced. But "the gate is one un-versioned `git config` away from off" is a meaningful systemic exposure for a 249-test layer.

---

### TEST-002 (Minor / Coverage) — The `useHashRoute` hook's listener + `navigate` effect is untested directly; only the pure `parseHash` is

**Evidence:** `useHashRoute.test.ts` imports and tests only `parseHash` (the pure function). The hook itself (`useHashRoute.ts:27-41`) wires a `hashchange` listener and a `navigate()` that calls `replaceState` and then updates route state directly (because `replaceState` doesn't fire `hashchange`, `:41`). That direct-update branch and the listener teardown have no dedicated test. They are exercised *indirectly* by `App.test.tsx` (`restore-on-load` reads `window.location.hash`; the `"d" navigates to My Designs` case drives `navigate`), but never in isolation.

**Why this matters:** A regression in the `replaceState`-then-`setRoute` branch (e.g. dropping the direct update on the theory that `hashchange` will fire) would not be caught by a unit test — only by the App-level cases that happen to traverse it, which assert higher-level outcomes and could mask a subtle route-state desync (browser back/forward, deep-link to `#/settings`). Routing is a Stage 8.5 feature called out in scope.

**Fix path:** Add a `renderHook(useHashRoute)` test: assert initial route from `window.location.hash`, that dispatching a `hashchange` event updates `route`, that `navigate('#/settings')` updates `route` synchronously (the replaceState branch), and that the listener is removed on unmount. ~20 lines.

---

### TEST-003 (Minor / Coverage) — No backend test that the cloud key is kept out of LOGS (only out of HTTP responses)

**Evidence:** `test_cloud_key_saved_locally_but_never_returned_in_full` (`:2202`) and `test_model_status_cloud_never_returns_the_key` (`:2055`) prove the secret never appears in any HTTP response body. There is no test asserting the key is never written to a log line / stderr / the request log. The scope brief lists "key never logged" as a safety invariant to check.

**Why this matters:** The two trust-critical leak vectors for a local-stored secret are (a) the wire — well covered — and (b) the logs. A future `logging.info(f"settings update: {body}")` or an exception that stringifies the settings dict would leak the raw key into a log the user might paste into a bug report. No current test would catch that regression. I did not find evidence the key currently flows to a log (this is a missing-test finding, not a confirmed leak), which is why it's Minor rather than Major.

**Fix path:** Add a test that POSTs a settings update carrying `openrouter_api_key`, captures `caplog` (and/or the server's request-log output), and asserts the raw secret substring appears in **neither**. Pair it with a stderr capture around an induced settings-handler exception to prove a traceback doesn't stringify the key.

*Note for the orchestrator:* if Engineering confirms the key can reach any log/exception path, this escalates to **Major** (a safety invariant with no test, per the brief's rule).

---

### TEST-004 (Minor / Quality) — A few component tests assert rendering/labels where a behavior assertion would bite harder

**Evidence:** This is a small, scattered pattern, not systemic. Examples: `Topbar.test.tsx` (4 tests) asserts the nav buttons exist and call their `on*` props, but Topbar's *active-route highlighting logic* is only checked for `settings` (`:34`), not for `designs`/`landing`. `RightPanel`'s help-tip tests (`:290`) assert the (i) buttons render for each jargon term — good — but only one test (`:330`) actually opens a tip and reads the definition. The InfoTip glossary content (the actual plain-language text per term) is largely asserted by presence, not by correctness of the definition shown.

**Why this matters:** Low. These are mostly cosmetic/label surfaces. The risk is a wrong-definition or wrong-active-state slipping through because the test checks "a thing rendered" rather than "the right thing rendered." Given the otherwise-high behavioral bar, calling it out so it doesn't drift.

**Fix path:** Parameterize the active-route assertion across all routes; add one assertion per glossary term that the revealed definition matches the term (table-driven). Optional.

---

### TEST-005 (Nit / Mocking) — App-level tests mock the entire `api` module; the api<->component contract is verified only by shared TypeScript types

The vitest component tests (`App`, `MyDesigns`, `SettingsPanel`, `FirstRunWizard`, `PhotoOnramp`) mock `./api` wholesale. `api.ts` is separately and well unit-tested at the fetch seam. The seam between them — that a component calls the api function with the args the api function expects and consumes the shape it returns — is held together by TS types, not a test. This is the standard, reasonable RTL pattern and the backend `test_webapp.py` round-trips cover the real server contract, so the residual risk is small. Flagging once: a contract test (e.g. MSW driving the real `api.ts` through one component) would close the last seam, but it is not warranted at this stage given the strong socket-level integration coverage already present. No action recommended unless a future type-erased refactor lands.

---

## Adversarial-case census (sampled)

| Case class | Covered? | Where |
|---|---|---|
| Empty / null / non-numeric numeric entry | Yes | `RightPanel.test.tsx:700` |
| Out-of-range clamp (mm + inch + integer) | Yes | `RightPanel.test.tsx:507,609,736` |
| Traversal / zip-slip / oversized import | Yes | `test_design_store.py:51,164,190` |
| Corrupt/missing persistence file | Yes | `test_design_store.py:72`, `test_settings_store.py:42` |
| Concurrency (parallel save/list, parallel render, dup-create race) | Yes | `test_design_store.py:243`, `test_webapp.py:1437,1715`, `App.test.tsx:195` |
| Out-of-order / superseded async responses | Yes | `App.test.tsx:142,388` |
| Model/network down (plan AND codegen) | Yes | `test_webapp.py:2447,2480` |
| Abort/cancel every blocking action | Yes | `App`, `PhotoOnramp`, `MyDesigns` |
| Secret never on the wire | Yes | `test_webapp.py:2055,2202` |
| Secret never in logs | **No** | TEST-003 |
| Empty states (no designs, no result, search-no-match) | Yes | `MyDesigns.test.tsx:35,135`, `RightPanel.test.tsx:123` |
| Permission/unwritable persistence | Yes | `test_design_store.py:110` |
| Hash-route listener/navigate effect | **Indirect only** | TEST-002 |

---

## Summary for the orchestrator

**Finding counts:** Blocker 0 / Critical 0 / Major 1 / Minor 3 / Nit 1 (total 5)

**Blockers:** none. The test suite runs clean (757 + 249 = **1006 passing**, 0 unjustified skips), and every Stage 8.5 safety invariant in scope is tested *except* "key-never-logged."

**Top findings:**
1. **TEST-001 (Major):** hosted CI is a documented partial smoke check and is currently disabled; the 249-test frontend layer + SPA-build-reproducibility are gated **only** by a per-clone local pre-push hook. UI regressions / source-vs-build drift can ship green on any machine without the hook armed. (`.github/workflows/ci.yml:1-28`, `scripts/ci.sh`)
2. **TEST-003 (Minor, watch for escalation):** the cloud key is proven absent from HTTP responses but **not from logs** — the second classic leak vector for a local secret has no test. Escalates to Major if Engineering finds any log/exception path stringifies settings.
3. **TEST-002 (Minor):** `useHashRoute` is tested only via the pure `parseHash`; the hook's `hashchange` listener and `replaceState`-direct-update branch (routing) have no direct test.
4. **TEST-004 (Minor):** a few render-presence assertions (Topbar active state for non-settings routes; glossary definition correctness) where a behavior assertion would catch more.
5. **TEST-005 (Nit):** component tests mock `api` wholesale; the api<->component seam rests on TS types — acceptable given the strong socket-level backend coverage.

**Culture/pattern observations (for the exec report):** This is a mature, honest test culture — adversarial unit tests with named finding-ID provenance in the comments (each test cites the bug it pins, e.g. `TEST-003`, `ENG-002`, `FOUND-001`), real-socket integration over the actual HTTP handlers, deterministic concurrency via events not sleeps, no retry/flake institutionalization, and a gate that explicitly refuses to mistake green-from-skips for proven (the `-ra` flag and the `KIMCAD_RELEASE=1` hard-fails). The single most valuable fix is process, not code: **make the frontend + build-reproducibility gate run somewhere other than one developer's local hook.**
