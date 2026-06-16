# Test Suite Deep-Dive — KimCad Snapmaker U1 / Multi-Toolhead Feature

**Audit date:** 2026-06-16
**Role:** Test Engineer
**Scope audited:** commits cc80fed + 3553665 — `snapmaker_connector.py`, `mock_moonraker.py` (pause/resume/cancel additions), `slicer.py` (`resolve_filament_slots` + multi-head `slice_model` branch), `webapp.py` (`_handle_slice` multi-head POST body path)
**Auditor posture:** Balanced

---

## TL;DR

The Snapmaker connector is tested through a faithful in-process mock Moonraker, which is a genuine integration signal — not a pure unit-test mock. The 14 connector tests are well-structured and cover the main happy paths plus key error paths. However, the mock always returns all four extruder objects; partial presence (3-of-4, 1-of-4) is never exercised. The new multi-head slicer branch (`resolve_filament_slots`, `--filament-config` CLI, `filament_slots` key composition) has zero dedicated test coverage in `test_slicer.py`. The webapp's multi-head POST body (`filament_slot_0..N-1`) has no HTTP-layer test at all. The class of bug that slips through: a multi-toolhead slice silently falls back to single-head behavior (or raises an uncaught `OrcaProfileError`) without the test suite catching it.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 2 |
| Major | 3 |
| Minor | 2 |
| Nit | 1 |

## What's working

- **Mock Moonraker is a real HTTP integration, not a pure unit mock.** `serve_mock_moonraker` spins a real `ThreadingHTTPServer` on a loopback port. Tests exercise actual HTTP request/response round-trips, including multipart upload, auth, and now pause/resume/cancel POST paths. This is better than most connector test suites.
- **pause/resume/cancel Moonraker tests are correct and thorough.** The six new tests in `test_moonraker_connector.py` cover the state transitions, auth failure, and offline error path. The mock correctly implements POST to `/printer/print/pause`, `/printer/print/resume`, and `/printer/print/cancel`.
- **Snapmaker inherits the full Moonraker control path.** The three Snapmaker pause/resume/cancel tests validate that the inherited methods work against the same mock — appropriate since no methods are overridden.
- **`test_capabilities_returns_toolhead_count_4` is a real end-to-end count test.** The mock returns all four extruder objects, and the test asserts `toolhead_count == 4`. The counting logic in `snapmaker_connector.py` (`sum(1 for obj in _EXTRUDER_OBJECTS if obj in status)`) is genuinely exercised.

## What couldn't be assessed

- CI history and flakiness record (not accessible).
- Whether `snapmaker_connector.py` would be caught as missing by the import machinery if deleted — this requires running the suite (`pytest --collect-only` or similar), which was not executed.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | Pytest |
| Test pyramid shape | Heavy unit + integration (real HTTP mock); no frontend E2E |
| Coverage tool | Not visible in scope |
| Reported coverage (if any) | N/A |
| Flakiness posture | One intentional time.sleep(0.5) in `test_concurrent_identical_slices` (bounded/documented); otherwise clean |
| CI blocking? | Presumed yes; not verified |

---

## Findings

> **Finding ID prefix:** `TEST-`
> **Categories:** Coverage / Shortcut / Flakiness / Quality / Ergonomics / Mocking / Regression

---

### [TEST-001] — Critical — Coverage — No test for `resolve_filament_slots()` — the multi-head slicer's only new unit

**Evidence**

`src/kimcad/slicer.py` lines 410–429 introduce `resolve_filament_slots()`, the core function that maps per-toolhead material keys to on-disk filament profile JSONs. `tests/test_slicer.py` imports `resolve_slice_settings` but never imports or calls `resolve_filament_slots`. Searching all test files:

```
grep -r "resolve_filament_slots" tests/  → zero matches
```

The function's error path — `OrcaProfileError` when a key has no configured profile — is completely untested. The happy path (valid keys → list of `Path`) is also untested.

**Why this matters**

This is the only new logic in `slicer.py`. A typo in the key lookup (`orca_filament_profiles.get(key)`) or a wrong profile-kind argument (`"filament"` vs `"machine"`) would not be caught. The class of bug: multi-head slicing silently produces single-head G-code or raises an `OrcaProfileError` at runtime that the webapp catches only as a generic 500.

**Blast radius**
- Adjacent code: `slice_model()` has a new branch (`if settings.filaments and len(settings.filaments) > 1: ... --filament-config`) that is also untested — covered by TEST-002.
- User-facing: every Snapmaker U1 multi-material print attempt.
- Related findings: TEST-002, TEST-003.

**Fix path**

Add unit tests in `test_slicer.py`:
1. `test_resolve_filament_slots_happy_path` — stub `_find_profile_json` and assert correct paths returned for 2-key and 4-key lists.
2. `test_resolve_filament_slots_missing_profile_key_raises_orca_error` — pass a material key absent from `printer.orca_filament_profiles`, assert `OrcaProfileError`.

---

### [TEST-002] — Critical — Coverage — `--filament-config` multi-head CLI branch in `slice_model` has no test

**Evidence**

`slicer.py` lines 218–222:
```python
if settings.filaments and len(settings.filaments) > 1:
    for fp in settings.filaments:
        cmd += ["--filament-config", str(fp)]
else:
    cmd += ["--load-filaments", str(settings.filament)]
```

`test_slicer.py::test_slice_builds_expected_command` passes `SETTINGS` which has `filaments=None`. The `--filament-config` branch is never exercised. A grep across all tests for `filament-config` returns zero matches.

**Why this matters**

If the branch has a bug — wrong flag name, wrong order, missing the `else` — single-head slices remain green while every multi-head slice fails at the slicer subprocess call. Since the slicer is not run in CI (live tests gated by binary presence), this failure would only surface at a real printer.

**Blast radius**
- Adjacent code: `slice_model` is the single subprocess call; a wrong CLI flag poisons every multi-head print.
- User-facing: all Snapmaker U1 multi-material prints.
- Related findings: TEST-001, TEST-003.

**Fix path**

Extend `test_slice_builds_expected_command` (or add a companion test) with a `SliceSettings(filaments=(Path("f0.json"), Path("f1.json"), Path("f2.json"), Path("f3.json")), ...)` and assert:
- `"--filament-config"` appears in `cmd` four times.
- `"--load-filaments"` does NOT appear.
- `"--allow-newer-file"` still appears (regression guard).

---

### [TEST-003] — Major — Coverage — Webapp `_handle_slice` multi-head POST body has no HTTP-layer test

**Evidence**

`webapp.py` lines 2462–2476 extract `filament_slot_0..N-1` keys from the POST body, compose a `filament_slots` tuple, and build the slice cache key as a tuple (rather than a string). The existing `test_webapp.py` slice tests (`test_web_refuses_to_slice_a_gate_failed_part`, `test_slice_is_idempotent_one_real_slice_per_key`, `test_http_slice_before_design_is_404`, etc.) never POST `filament_slot_0` or any `filament_slot_N` key. The walkthrough report also flagged this gap explicitly.

Searching `test_webapp.py`:
```
grep "filament_slot" tests/test_webapp.py → zero matches
```

**Why this matters**

Three distinct bugs could exist here without any test catching them:
1. The tuple vs. string cache key collision (a multi-head re-confirm with the same printer/material could collide with a cached single-head result if the key composition is wrong).
2. The `_slot_kw` empty-tuple edge case: `filament_slots=()` (all `filament_slot_N` keys absent from body) should produce `_slot_kw = {}` (single-head path), but the condition `if any(slots)` needs to be correct — untested.
3. Silently falling through to single-head when the POST body omits `filament_slot_N` keys.

**Blast radius**
- Adjacent code: `slice_registered_mesh` with `filament_slots` kwarg.
- Shared state: the slice cache key (`(rid, printer_key, tuple | str)`) — a collision produces stale cached G-code for the wrong material combination.
- User-facing: every multi-head slice confirmation from the web UI.
- Related findings: TEST-001, TEST-002.

**Fix path**

Add an offline HTTP-layer test in `test_webapp.py` (monkeypatching `slice_registered_mesh`):
1. POST `{"printer": "snapmaker", "material": "pla", "filament_slot_0": "pla", "filament_slot_1": "petg", "filament_slot_2": "pla", "filament_slot_3": "abs"}` and assert `slice_registered_mesh` received `filament_slots=("pla", "petg", "pla", "abs")`.
2. POST with no `filament_slot_N` keys and assert the single-head path is taken (no `filament_slots` kwarg).
3. POST with `filament_slot_0` only (partial presence) and verify the tuple is formed correctly.

---

### [TEST-004] — Major — Mocking — Mock always returns all 4 extruders; partial toolhead presence never tested

**Evidence**

`mock_moonraker.py` `_status_for()` responds to any requested extruder object by returning it unconditionally (lines 67–73). The Snapmaker `capabilities()` queries all four. This means `test_capabilities_toolhead_count_at_least_1` (which asserts `>= 1`) cannot distinguish between "only extruder is present" and "all four are present" — the mock returns all four regardless of what the real printer would have.

The connector's partial-presence logic (`max(1, sum(1 for obj in _EXTRUDER_OBJECTS if obj in status))`) for 2-of-4 or 3-of-4 scenarios is never exercised. Similarly, `status()` builds `toolhead_temps` iteratively — if `extruder2` is absent on a 2-head machine, the test suite does not verify only 2 temperatures are returned.

**Why this matters**

A Snapmaker user with a 2-head configuration (extruder + extruder1 only) could get an incorrect `toolhead_count=4` if the connector fails to count correctly from a partial response — the test suite would not catch this.

**Blast radius**
- Adjacent code: `mock_moonraker._status_for()` would need a parametric override (e.g., `serve_mock_moonraker(extruder_count=2)`).
- User-facing: `toolhead_count` returned from `capabilities()` is used by webapp to populate `filament_slot_0..N-1` UI controls.
- Related findings: TEST-003 (the UI field count depends on this value).

**Fix path**

Add a `extruder_count` parameter to `serve_mock_moonraker` / `_status_for` that limits which extruder objects are returned. Add tests:
- `test_capabilities_toolhead_count_2` — assert `caps.toolhead_count == 2` with only extruder + extruder1.
- `test_status_partial_toolhead_temps` — assert `len(st.toolhead_temps) == 2` for a 2-head mock.

---

### [TEST-005] — Major — Coverage — `toolhead_count` field in `/api/options` response has no test

**Evidence**

`webapp.py` `web_options()` includes `"toolhead_count": p.toolhead_count` in each printer entry (line 555). `test_web_options_lists_printers_with_sliceable_flag` and `test_web_options_lists_per_printer_available_materials` test various printer fields but neither asserts on `toolhead_count`. Searching:

```
grep "toolhead_count" tests/test_webapp.py → zero matches
```

**Why this matters**

The frontend uses this value to render the per-slot material selectors. If `toolhead_count` is missing or wrong in the API response, the ExportPanel renders the wrong number of selectors — silently, because neither the backend test nor any frontend test catches it. Since there are no frontend `.test.ts` files at all (`frontend/src/**/*.test.*` → zero matches), this path is tested nowhere.

**Blast radius**
- Adjacent code: the frontend `ExportPanel` materialSlots reset `useEffect` depends on `toolhead_count` from `/api/options`. No test covers this frontend reset behavior.
- User-facing: all Snapmaker U1 users see wrong slot count in the export panel.
- Related findings: no frontend test exists (TEST-006).

**Fix path**

Extend `test_web_options_lists_printers_with_sliceable_flag` to assert `by_key["bambu_p2s"]["toolhead_count"] == 1` and (if a snapmaker entry is in the config) `by_key["snapmaker_u1"]["toolhead_count"] == 4`.

---

### [TEST-006] — Minor — Coverage — Zero frontend test coverage for ExportPanel / api.ts

**Evidence**

`frontend/src/**/*.test.*` → zero matches. The ExportPanel's `materialSlots` reset `useEffect` (triggered when `toolhead_count` changes) has no test. The `api.ts` multi-head POST body construction is also untested.

**Why this matters**

UI-level regressions in the material slot selector (wrong reset on printer change, wrong slot count sent to `/api/slice`) would not be caught by any automated test. Manual QA is the only gate.

**Fix path**

Add Vitest unit tests for `ExportPanel`: assert that switching to a 4-head printer creates 4 `filament_slot_N` fields in the POST body, and that switching back to a 1-head printer resets to a single material selector.

---

### [TEST-007] — Minor — Regression — Import-level test for `snapmaker_connector.py` existence but no import-failure sentinel

**Evidence**

`test_snapmaker_connector.py` line 10: `from kimcad.snapmaker_connector import SnapmakerConnector`. If `snapmaker_connector.py` were accidentally omitted from a commit (the prior bug reported in the walkthrough), this import would fail and the test file would be an error (not a failure). This IS a collection-time error in pytest — the suite would not be green — so the prior bug WOULD have been caught by this test file existing.

However, the walkthrough noted this as a concern, so confirming: yes, a missing module causes `ImportError` at collect time, which pytest reports as an ERROR (not a pass). The regression posture for module-level omission is adequate.

**Why this matters**

This is a positive finding rather than a gap. Noted here for completeness — no action required.

**Fix path**

No fix needed. The import is a sufficient sentinel for module-level omission.

---

### [TEST-008] — Nit — Quality — `test_capabilities_toolhead_count_at_least_1` assertion is too weak

**Evidence**

`test_snapmaker_connector.py` line 57: `assert caps.toolhead_count >= 1`. Given the mock always returns all 4 extruder objects, the actual value is 4, but the assertion accepts any value ≥ 1. This means a broken `capabilities()` returning `toolhead_count=999` would pass.

**Fix path**

Either tighten to `== 1` after adjusting the mock to return only `extruder`, or rename the test to `test_capabilities_fallback_to_single_head` and document the intent. Either way, combine with TEST-004 fix.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@skip` | 0 |
| `.only` (left in) | 0 |
| `TODO: add test` / similar | 0 |
| Empty assertion / placeholder | 1 (TEST-008: `>= 1` in wrong mock context) |
| `--retry` / retries normalized | No |

## Blind spots by class

1. **Multi-head slicer path end-to-end** — `resolve_filament_slots` → `slice_model --filament-config` branch. An entire new code path with zero test coverage.
2. **Partial toolhead presence** — 1-of-4 or 2-of-4 extruder objects in Moonraker status response.
3. **Multi-head webapp HTTP body** — `filament_slot_0..N-1` fields in POST to `/api/slice/<id>`.
4. **Cache key collision** — multi-head tuple key vs. single-head string key for the same `(rid, printer)`.
5. **Frontend material slot UI** — zero automated frontend tests.
6. **`/api/options` `toolhead_count` field** — asserted nowhere.
7. **`resolve_filament_slots` error path** — `OrcaProfileError` on missing profile key.

## Patterns and systemic observations

The test suite has a strong integration-testing culture for the Python backend (real HTTP, real zip files, real subprocess stubs) and a complete absence of frontend testing. This asymmetry is a pre-existing gap that predates this feature, but the multi-toolhead feature widens it: the new feature is end-to-end only in the browser for the slot-count display and slot-reset behavior. The connector layer is the strongest; the slicer and webapp layers for multi-head are the weakest.

The mock Moonraker is a high-quality testing asset — it correctly implements the HTTP protocol and stateful print lifecycle. Its single gap is the always-return-all-4-extruders behavior, which can be fixed without disturbing existing tests by adding a parameter.

## Appendix: test artifacts reviewed

- `tests/test_snapmaker_connector.py` (14 tests, all read)
- `tests/test_moonraker_connector.py` (full, pause/resume/cancel section lines 254–312)
- `tests/test_webapp.py` (3670 lines, scanned fully for `filament_slot`, `toolhead_count`, `snapmaker`)
- `tests/test_slicer.py` (full, confirmed no `resolve_filament_slots` or multi-head coverage)
- `src/kimcad/mock_moonraker.py` (full)
- `src/kimcad/snapmaker_connector.py` (full)
- `src/kimcad/slicer.py` (`resolve_filament_slots`, `slice_model` multi-head branch)
- `src/kimcad/webapp.py` (`_handle_slice`, `web_options`, `slice_registered_mesh`)
- `frontend/src/**/*.test.*` → zero files found
