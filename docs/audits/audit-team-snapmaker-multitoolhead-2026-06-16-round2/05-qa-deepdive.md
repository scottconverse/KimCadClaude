# Runtime QA Deep-Dive (Round 2 — Post-Remediation) — KimCad Snapmaker U1 + Multi-Toolhead

**Audit date:** 2026-06-16 (round 2)
**Role:** QA Engineer
**Scope re-audited:** The four round-1 QA findings (QA-001 Major, QA-002 Minor, QA-003 Minor, QA-004 Nit) plus a fresh hunt for regressions introduced by the fixes — specifically whether wiring a `snapmaker_u1` connector into `config/default.yaml` perturbs the `/api/connectors` default selection or the existing connector list.
**Environment:** Windows 11 Pro 10.0.26200, Python 3.13.13, kimcad 0.9.0b4, demo server on `127.0.0.1:9184`, isolated `USERPROFILE=C:\Temp\kimcad-qa-r2-9184`, `curl.exe` + venv-python probes. Server started via the venv interpreter (`.venv\Scripts\python.exe -m kimcad.cli web --demo --port 9184` — see "Probe note" below), polled `/api/health`, killed cleanly by PID after probing.
**Auditor posture:** Balanced.

---

## TL;DR

All four round-1 QA findings are **RESOLVED** and verified — three by code+test inspection and one (QA-004) by live API probe. The QA-004 fix is the headline re-check: a `snapmaker_u1` connector now appears in the live `/api/connectors` response with `configured:false`, and `/api/connector-status/snapmaker_u1` returns a sane not-configured `200` (`reason:"config"`) rather than the round-1 `reason:"unknown"` — and crucially **without disturbing the `default` connector (still `mock`) or breaking any other connector's status**. No new findings. No Blockers, Criticals, Majors, Minors, or Nits introduced.

**QA round-2 result: 0/0/0/0/0.**

## Severity roll-up (QA, round 2 — OPEN only)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

---

## Per-finding resolution table

| ID | R1 Severity | R1 Title | R2 Status | Verified by |
|---|---|---|---|---|
| QA-001 | Major | `test_capabilities_toolhead_count_at_least_1` didn't exercise single-head; always returned 4 | **RESOLVED** | Code + test + live test run |
| QA-002 | Minor | `mock_moonraker` couldn't simulate single-head (extruder1/2/3 absence) | **RESOLVED** | Code inspection + test run |
| QA-003 | Minor | No webapp test for `filament_slots` cache-key diff / single-head ignore | **RESOLVED** | Test inspection + test run |
| QA-004 | Nit | No `snapmaker` connector wired in demo mode; `/api/connector-status/snapmaker_u1` returned `reason:"unknown"` | **RESOLVED** | Live API probe |

---

## Evidence per finding

### QA-001 — RESOLVED (was Major)

The mock now carries an `extruder_count` knob, and the test named for the single-head floor actually drives a single-head printer:

- `src/kimcad/mock_moonraker.py:75` — `_status_for` now emits only the first `extruder_count` extruder objects: `for i, obj in enumerate(_EXTRUDER_OBJECTS[: state["extruder_count"]])`. Default is 4 (all existing tests preserved).
- `tests/test_snapmaker_connector.py:52-57` — `test_capabilities_toolhead_count_at_least_1` now uses `serve_mock_moonraker(extruder_count=1)` and asserts `caps.toolhead_count == 1` (the real single-head value, not an accidental `>= 1` pass on a 4-head response).
- A **new** companion test `test_capabilities_toolhead_count_2` (lines 60-64) drives `extruder_count=2` → asserts `== 2`, and `test_status_partial_toolhead_temps` (lines 123-130) asserts a dual-head reports exactly 2 toolhead temps.
- Live run: `pytest tests/test_snapmaker_connector.py -q` → **17 passed** (was 14 in round 1; the 3 new tests close the single-/dual-head coverage gap).

The "single-head floors at 1" scenario is now genuinely exercised through the public mock, not just via a hand-rolled custom server.

### QA-002 — RESOLVED (was Minor)

The mock can now represent a single- or dual-head Moonraker without code changes:

- `serve_mock_moonraker(..., extruder_count: int = 4)` (lines 209-216) and `_initial_state(..., extruder_count: int = 4)` (lines 187-205) thread the count through to `_status_for`. Docstring (lines 222-225) documents `extruder_count` and that the default of 4 preserves every existing test.
- This is the exact fix path recommended in round 1 (add `extruder_count` defaulting to 4). Confirmed it backs both QA-001 and the new dual-head tests.

### QA-003 — RESOLVED (was Minor)

`tests/test_webapp.py` now covers the multi-toolhead POST → cache-key path at the web layer (lines 1498-1609):

- `test_slice_multihead_forwards_filament_slots` (1532) — explicit `filament_slot_0..3` forward as an ordered tuple `("pla","petg","pla","abs")`.
- `test_slice_multihead_with_no_slots_fills_full_tuple` (1552) — a multi-head POST with no slot fields fills the full 4-tuple `("pla","pla","pla","pla")` rather than collapsing to the single-head key (this is the ENG-001/QA-003 edge).
- **`test_slice_multihead_distinct_slots_are_distinct_slices_same_are_cached` (1568)** — the direct cache-key-diff test: POST tuple A, then tuple B (different → second slice), then A again (same → cache hit). Asserts exactly 2 slicer calls with the expected tuples. This is the cache-key differentiation that had no coverage in round 1.
- **`test_slice_single_head_ignores_filament_slots` (1593)** — POSTs `filament_slot_*` to `bambu_p2s` (toolhead_count 1) and asserts the slicer is called with `filament_slots is None` (single-head ignore).
- Live run: the 14 webapp tests matching `filament_slot/toolhead/multihead/single_head/connector` → **14 passed**.

### QA-004 — RESOLVED (was Nit) — the key live re-check

`config/default.yaml` now ships a `snapmaker_u1` connector template in the `connectors:` block (lines 515-518): `type: snapmaker`, empty `base_url` (visible-but-unconfigured, matching the moonraker/marlin/bambu templates), `api_key_env: SNAPMAKER_API_KEY`.

**Live `GET /api/connectors` (port 9184, demo, isolated home):**
```json
{"connectors": [
  {"name": "mock",         "simulated": true,  "configured": true},
  {"name": "octoprint",    "simulated": false, "configured": false},
  {"name": "moonraker",    "simulated": false, "configured": false},
  {"name": "snapmaker_u1", "simulated": false, "configured": false},
  {"name": "prusalink",    "simulated": false, "configured": false},
  {"name": "duet",         "simulated": false, "configured": false},
  {"name": "marlin",       "simulated": false, "configured": false},
  {"name": "bambu_p2s",    "simulated": false, "configured": false},
  {"name": "bambu_a1",     "simulated": false, "configured": false}
], "default": "mock"}
```
`snapmaker_u1` now appears with `configured:false` and `simulated:false` — exactly the round-1 fix request (pre-listed like octoprint/moonraker/marlin so the UI can prompt the user to configure it). It did **not** crash the list.

**Live `GET /api/connector-status/snapmaker_u1`:**
```json
{"name":"snapmaker_u1","ready":false,"reason":"config","simulated":false,
 "note":"The 'snapmaker_u1' connection has no address configured."}
```
Round 1 returned `reason:"unknown"` with note "There's no printer connection named 'snapmaker_u1'." Round 2 returns `reason:"config"` with a precise "no address configured" note — the connector is now *recognized* and reports an honest not-yet-configured state. HTTP 200, not a 500.

---

## NEW findings (regressions introduced by the fixes)

**None.** The fixes are additive and clean. I specifically hunted the two highest-risk regression vectors the QA-004 fix could introduce and confirmed both are clean:

### Regression check 1 — does adding `snapmaker_u1` change the `/api/connectors` `default`?

**No.** The handler (`webapp.py:1015-1017`) computes `default = next((c["name"] for c in conns if c["configured"]), None) or names[0]`. The new `snapmaker_u1` ships with an empty `base_url`, so `connector_is_configured` (`connectors.py:51-64`) calls `build_connector`, which raises `ConnectorError` ("snapmaker has no base_url configured", `connectors.py:200-203`) → `configured:false`. `mock` (loopback, first in config order, always configured) remains the first configured entry. **Live observed `"default":"mock"`** — unchanged from round 1. A new unconfigured connector cannot hijack the default.

### Regression check 2 — does the new entry break the existing connectors list or any other connector's status?

**No.** Probed every connector's status live; all return clean `200`s with sane not-configured notes, none 500:

| Connector | HTTP | ready | reason / note |
|---|---|---|---|
| mock | 200 | true | operational, nozzle 25.0, simulated |
| octoprint | 200 | false | config — needs API key |
| moonraker | 200 | false | config — no address |
| snapmaker_u1 | 200 | false | config — no address |
| marlin | 200 | false | config — no address or serial |
| bambu_p2s | 200 | false | config — no printer IP |

The `snapmaker_u1` entry slots in between `moonraker` and `prusalink` without disturbing the others.

---

## Other live confirmations (sanity)

- `GET /api/health` → `{"version":"0.9.0b4","openscad":true,"orcaslicer":true,"cadquery":true}` (ready in ~1s after startup).
- `GET /api/options` → `snapmaker_u1` entry present with `toolhead_count:4`, `sliceable:true`, materials `[pla,petg,tpu,abs]`, no generics. `bambu_p2s` carries `toolhead_count:1`. `default_printer:bambu_p2s`.
- `GET /api/connector-status/does_not_exist` → `200`, `reason:"unknown"`, "no printer connection named" — correctly distinguishes an *unknown* name (`unknown`) from a *known-but-unconfigured* one (`config`). The snapmaker fix sharpened this distinction in the user's favor.

## Probe note (method deviation, disclosed)

The task specified starting the server with `python -m kimcad`. That form **does not work** for this package — `kimcad` has no `__main__` module (`No module named kimcad.__main__; 'kimcad' is a package and cannot be directly executed`). The package exposes its CLI via the `[project.scripts]` entry point `kimcad = "kimcad.cli:main"` (`pyproject.toml:67-68`). I therefore launched with the **same venv interpreter** via `python -m kimcad.cli web --demo --port 9184`, which is the exact code path the `kimcad.exe` console script runs. This is an environmental note, **not a product finding** — the documented/installed launch path (`kimcad web`) is unaffected; only the bare `-m kimcad` invocation (which nothing ships or documents) fails.

## Adversarial / method-discipline observation (not a finding)

A bare `curl -X POST` to GET-only `/api/connectors` and `/api/connector-status/*` returns **HTTP 403** (the app's cross-site/state-change guard fires before method routing), not the `405 + Allow` the round-1 report recorded under a different request setup. This is the app's pre-existing CSRF posture and is **unchanged by the Snapmaker work** (which adds no new POST routes), so it is not a regression and not in scope for this feature. Flagging only for transparency about why the status code differs between the two rounds.

---

## What I could not test (unchanged from round 1, honestly restated)

- **Live Snapmaker U1 hardware** — none available. All connector behavior verified against the mock and code paths.
- **A fully-configured `SnapmakerConnector` `/api/connector-status`** — the demo ships the template unconfigured (empty `base_url`), by design; a real IP would be needed to exercise the online path. The `toolhead_temps` serialization remains covered by the connector unit tests (17/17 green) and round-1's custom-server probes.
- **Browser UI** — no browser exercised (Playwright cannot drive this app on this box per session notes); API-layer only.

---

## Roll-up

- **Round-1 QA findings:** 4 total — **4 RESOLVED, 0 OPEN.**
- **New findings this round:** 0.
- **Final OPEN roll-up (QA): Blocker 0 / Critical 0 / Major 0 / Minor 0 / Nit 0 → 0/0/0/0/0.**

## Appendix: environment + artifacts

- OS: Windows 11 Pro 10.0.26200 · Python 3.13.13 · kimcad 0.9.0b4
- Server: `.venv\Scripts\python.exe -m kimcad.cli web --demo --port 9184`, `USERPROFILE=C:\Temp\kimcad-qa-r2-9184`, killed by PID after probing (post-kill `/api/health` → connection refused, confirmed down).
- Probes: `curl.exe` (Windows built-in) + venv-python `json` parsing.
- Tests run green: `tests/test_snapmaker_connector.py` (17 passed), `tests/test_webapp.py -k "filament_slot or toolhead or multihead or single_head or connector"` (14 passed).
