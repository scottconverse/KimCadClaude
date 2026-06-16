# Runtime QA Deep-Dive — KimCad Snapmaker U1 + Multi-Toolhead

**Audit date:** 2026-06-16
**Role:** QA Engineer
**Scope audited:** Snapmaker U1 + generic multi-toolhead feature (commits cc80fed + 3553665); API contract, connector runtime behavior, mock fidelity, cache key correctness, single-head degradation paths.
**Environment:** Windows 11 Pro 10.0.26200, Python 3.13.13, kimcad 0.9.0b4, server on 127.0.0.1:9182 with `--demo` flag, isolated `USERPROFILE=C:\Temp\kimcad-qa-test-9182`, urllib probes (no browser; Playwright cannot drive this app on this box per session notes).
**Auditor posture:** Balanced

---

## TL;DR

The Snapmaker U1 / multi-toolhead feature is fundamentally correct at the API and connector levels. `/api/options` returns `snapmaker_u1` with `toolhead_count: 4`; `SnapmakerConnector.status()` correctly builds `toolhead_temps` tuples and degrades cleanly when fewer extruder objects are present; the cache key correctly differentiates different `filament_slots` tuples; single-head filament slots are correctly ignored. Three test-quality / mock-fidelity findings were uncovered, plus one connector-in-demo-mode observation. No Blockers. No security issues surfaced.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 2 |
| Nit | 1 |

---

## What's working

- **`/api/options` → `snapmaker_u1` with `toolhead_count: 4`** — confirmed live: the entry is present, `toolhead_count` is exactly 4, `sliceable: true`, four Snapmaker-branded filament profiles (no generics).
- **`SnapmakerConnector.status()` toolhead_temps** — confirmed via custom HTTP server: printing state correctly returns `(210.0, 205.0, 200.0, 195.0)`; idle returns `(25.0, 25.0, 25.0, 25.0)`; `nozzle_temp_c` equals `toolhead_temps[0]`.
- **`/api/connector-status/<name>` serializes `toolhead_temps`** — code path at `webapp.py:1813-1814` emits `toolhead_temps` as a list when non-empty; confirmed this path executes for the `mock` (loopback) connector which does not populate it.
- **500 on pause raises `ConnectorError`** — tested with a custom 500-returning server: `SnapmakerConnector.pause()` raises `ConnectorError` with message `"bad-moonraker pause failed (HTTP 500) — MCU error"`. The error-body extraction works.
- **500 on GET `/printer/objects/query`** — `SnapmakerConnector.status()` correctly returns `online=False, state=error` (because `500 < 500` is `False`).
- **Single-head graceful degradation** — when a real Moonraker returns only `extruder` (no `extruder1/2/3`), `capabilities()` returns `toolhead_count=1` and `status()` returns `toolhead_temps=(210.0,)`. The `max(1, sum(...))` floor and the `if block is not None` guard both work correctly.
- **`filament_slots` cache keys are correctly differentiated** — `('pla','petg','pla','pla')` ≠ `('pla','pla','pla','pla')` as dict keys; each hits a separate slice.
- **Single-head printer ignores `filament_slots` from POST body** — `webapp.py:2467` gates on `toolhead_count > 1`; for a 1-head printer `filament_slots` stays `None` and only `material_key` is used.
- **All 14 `test_snapmaker_connector` tests pass** — 14/14 green on Python 3.13.13.
- **HTTP 405 with correct `Allow` header on POST to GET-only routes** — `/api/options`, `/api/connectors`, `/api/connector-status/*` all 405 on POST.

## What couldn't be assessed

- **`/api/connector-status/snapmaker_u1` when a real SnapmakerConnector is configured** — the demo server has no `snapmaker` connector in its `connectors:` block (the entry is intentionally commented out in `default.yaml`; user must add it in `local.yaml`). The status serialization for `toolhead_temps` was verified by code-path inspection and the mock connector-status test.
- **Live Snapmaker U1 hardware** — no device available; all connector tests against controlled HTTP servers.
- **Multi-plate slice rejection for multi-toolhead** — `extract_single_plate_gcode` rejects multi-plate archives; whether the Snapmaker U1's multi-toolhead slices always produce single-plate output was not tested (OrcaSlicer not invoked in demo mode).

---

## Product shape

KimCad is a local Python web app + API. This audit focused on the API contract layer (GET `/api/options`, GET `/api/connectors`, GET `/api/connector-status/<name>`, POST `/api/slice/<id>`) and the `SnapmakerConnector` runtime behavior — specifically the 4-toolhead Moonraker dialect, its mock, and degradation to single-head scenarios.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| GET `/api/health` | Pass | — |
| GET `/api/options` → `snapmaker_u1` entry | Pass | — |
| GET `/api/connectors` (demo mode) | Pass | QA-004 |
| GET `/api/connector-status/mock` | Pass | — |
| GET `/api/connector-status/snapmaker_u1` (demo, no connector configured) | Returns `unknown` reason | QA-004 |
| `SnapmakerConnector.capabilities()` against 4-head mock | Pass | — |
| `SnapmakerConnector.capabilities()` against single-head custom server | Pass | — |
| `SnapmakerConnector.status()` 4-head printing | Pass | — |
| `SnapmakerConnector.status()` single-head (extruder1/2/3 absent) | Pass | — |
| `SnapmakerConnector.pause()` against 500-returning server | Pass (raises ConnectorError) | — |
| `filament_slots` cache key differentiation | Pass | — |
| Single-head printer ignores filament_slots in POST | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Moonraker GET returns 500 | `online=False`, `state=error`, no traceback | Pass |
| Moonraker pause returns 500 | `ConnectorError` raised, MCU error detail extracted | Pass |
| extruder1/2/3 absent (single-head Klipper) | `toolhead_count=1`, `toolhead_temps=(temp0,)` | Pass |
| `filament_slots=('pla','petg')` then `('pla','pla')` — same rid | Different cache keys → separate slice runs | Pass |
| `filament_slots` sent to single-head printer via POST | Silently ignored, `material_key` used | Pass |
| POST to GET-only `/api/connector-status/*` | 405 + `Allow: GET, HEAD` | Pass |
| GET `/api/connector-status/nonexistent` | 200 + `ready:false, reason:"unknown"` | Pass |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Browser / Mobile / Console / Protocol / Install / Auth

---

### QA-001 — Major — API — `test_capabilities_toolhead_count_at_least_1` doesn't test single-head; always returns 4

**Evidence**

1. Open `tests/test_snapmaker_connector.py:52-57`. Docstring says "Even if only `extruder` is present the count floors at 1."
2. The test uses `serve_mock_moonraker()` with no configuration. `mock_moonraker._status_for()` always includes `extruder1`, `extruder2`, `extruder3` in the response whenever they appear in the query string — which `_EXTRUDER_OBJECTS` always includes.
3. Run `python -c "..."` (script 7 above): `caps.toolhead_count` is `4`, not `1`. The assertion `>= 1` passes for the wrong reason — the tested value is 4.
4. Single-head behavior (only `extruder` present) is only exercisable via a custom HTTP server (verified: scripts 5 and 10 above using `SingleHeadCapabilities` and `SingleHeadMoonraker`).

**Observed:** `caps.toolhead_count == 4` always when using `serve_mock_moonraker()`.
**Expected:** The test named "toolhead_count_at_least_1" should reach the floor guard (`max(1, 0)`) or a 1-extruder response, confirming the scenario it documents.

**Why this matters**

The single-head variant (a Klipper printer with only one extruder, or a Snapmaker with one module installed) is a real deployment scenario. The only test that claims to cover it silently covers 4-head behavior instead. A regression in the `max(1, ...)` floor or the absent-key guard would go undetected.

**Blast radius**

- Adjacent code: `snapmaker_connector.py:71` (`toolhead_count`) and `snapmaker_connector.py:101-106` (absent-key loop in `status()`).
- Tests to update: `test_capabilities_toolhead_count_at_least_1` — replace `serve_mock_moonraker()` with a custom 1-extruder server or add `extruder_count` knob to the mock.
- Related findings: QA-002 (mock cannot simulate the gap at all).

**Fix path**

Either (a) add an `extruder_count: int = 4` parameter to `serve_mock_moonraker` that controls how many extruder objects `_status_for` returns, or (b) add a dedicated test using a custom `BaseHTTPRequestHandler` that returns only `extruder` in its status payload. The single-head scenario is already verified to work at runtime (scripts above); the fix is purely a test-coverage gap.

---

### QA-002 — Minor — API — `mock_moonraker` cannot simulate single-head (extruder1/2/3 absence) without code changes

**Evidence**

1. `mock_moonraker._status_for()` (lines 57-78): the `extruder1/2/3` blocks are emitted unconditionally whenever those keys appear in the query `objects` list.
2. `SnapmakerConnector.capabilities()` always passes all four `_EXTRUDER_OBJECTS` to `_query()`.
3. Result: there is no way to use `serve_mock_moonraker()` to test a single-head Moonraker response — all tests using the mock will always receive all 4 extruders. (Verified: script 6 above.)

**Why this matters**

`mock_moonraker` is presented as the faithful test oracle for Moonraker/Snapmaker connector testing. If it cannot represent a real single-head printer's response, tests using it provide false confidence for that variant.

**Blast radius**

- Adjacent code: every test that uses `serve_mock_moonraker` for Snapmaker/Moonraker connector testing.
- Tests to update: `test_capabilities_toolhead_count_at_least_1`, and any future single-head status tests.
- Related findings: QA-001.

**Fix path**

Add `extruder_count: int = 4` to `serve_mock_moonraker` and `_initial_state`; thread it into `_status_for` to conditionally emit only `extruder` when `extruder_count == 1`. Defaults to 4 to preserve all existing tests.

---

### QA-003 — Minor — API — No webapp-level test for `filament_slots` cache-key differentiation or single-head ignore behavior

**Evidence**

1. `grep -r filament_slot tests/` — no matches. No test exercises the `POST /api/slice/<id>` path with `filament_slot_0`, `filament_slot_1` etc. in the body.
2. The cache-key logic in `webapp.py:2464-2476` is only reachable through the full HTTP request path; it has no unit-test coverage at the `_handle_slice` level.
3. The "single-head ignores filament_slots" behavior (the `if printer_cfg.toolhead_count > 1` guard at line 2467) has no test.

**Why this matters**

Cache-key logic bugs in multi-toolhead slicing could silently serve a cached single-material slice when the user switches slot assignments, or vice versa. These bugs are invisible until a user prints the wrong material.

**Blast radius**

- Adjacent code: `webapp.py:2464-2476`, `webapp.py:2490`, `slice_registered_mesh`.
- Tests to update: `test_frontend.py` — add cases that call `/api/slice/<id>` with multi-toolhead body params and verify cache separation.

**Fix path**

Add two `test_frontend.py` cases: (a) two successive POST `/api/slice/<id>` calls with different `filament_slot_*` values confirm they produce different cache entries; (b) a POST with `filament_slot_0/1` to a single-head printer confirms only `material` is used in the key.

---

### QA-004 — Nit — API — No `snapmaker` connector is wired in demo mode; `/api/connector-status/snapmaker_u1` returns `reason: "unknown"` even though the printer profile is present

**Evidence**

```
GET /api/connector-status/snapmaker_u1
→ {"name":"snapmaker_u1","ready":false,"reason":"unknown","simulated":false,
   "note":"There's no printer connection named 'snapmaker_u1'."}
```

The `connectors:` block in `default.yaml` has `snapmaker_u1` commented out (user must provide `base_url` in `local.yaml`). This is intentional — the connector requires a real IP. However, `/api/connectors` does not surface a `snapmaker_u1` template entry, which means the UI cannot prompt a user to configure it.

**Why this matters**

Minor UX gap, not a bug. A user who has a Snapmaker U1 may not discover they need to add a connector template to `local.yaml`. The printer appears in the slicing dropdown with `toolhead_count: 4` but has no corresponding connector entry.

**Fix path**

Either add a commented-but-listed `snapmaker` connector to the `/api/connectors` response (similar to how `octoprint`, `moonraker`, `marlin` are pre-listed as `configured: false`), or document the setup step prominently in the UI when `snapmaker_u1` is selected as the slice target.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| `/api/health` cold response | ~5s server startup, <10ms after | — | Pass |
| `/api/options` | <5ms | <50ms API benchmark | Pass |
| `/api/connectors` | <5ms | <50ms | Pass |
| `/api/connector-status/mock` (loopback) | <5ms | <50ms | Pass |

Browser metrics not applicable (no browser UI exercised; Playwright cannot drive this app on this box).

## Security / privacy snapshot

- No auth on any `GET /api/*` endpoint — by design (local LAN app, no user accounts). No IDOR risk (no user data).
- POST `/api/slice/<id>` body `filament_slot_*` values are safely passed through `str(...)` and validated against printer config before slicing; no injection risk observed.
- No credentials stored or echoed in any response.

## Console and log observations

Server stderr was empty during the audit (no warnings, no uncaught exceptions). The `--demo` flag suppresses model calls; only the HTTP request log is suppressed (handler sets `log_message` to no-op). No unexpected 5xx observed.

## Patterns and systemic observations

- **Mock fidelity vs. connector completeness:** the `mock_moonraker` is a capable oracle for the 4-head happy path but lacks parameterization for partial configurations. As the Snapmaker feature targets real hardware variants (2-head, 1-head with a single module), the mock should be extended to represent those.
- **Missing webapp integration tests for multi-toolhead slicing:** the connector-layer tests are thorough (14 tests, all green); the web layer has no coverage of the multi-toolhead POST body → cache-key path. These are logically separate concerns and both need coverage.

## Appendix: environments and artifacts

- OS: Windows 11 Pro 10.0.26200
- Python: 3.13.13
- KimCad: 0.9.0b4 (commit 3553665)
- Server: `kimcad web --demo --port 9182` (via `.venv\Scripts\kimcad.exe`)
- Probing tools: `curl.exe` (Windows built-in), `urllib.request` (Python stdlib), custom `ThreadingHTTPServer` stubs
- `USERPROFILE` isolated to `C:\Temp\kimcad-qa-test-9182`
- All 14 `test_snapmaker_connector` tests run and passed: `pytest tests/test_snapmaker_connector.py -v`
- Server started and killed cleanly within the audit session
