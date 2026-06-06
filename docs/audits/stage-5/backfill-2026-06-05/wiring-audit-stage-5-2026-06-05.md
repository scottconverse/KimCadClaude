# KimCad Stage 5 (Deterministic Template Engine + Live Sliders) — Playwright Interface Wiring Audit

> Audited 2026-06-05 · branch `stage-0-7-audit-backfill` @ `0aeae99` · auditor: Claude (audit-only mode) · LLM-free demo at http://127.0.0.1:8765/

## Executive Summary

**Verdict: the Stage 5 live-slider surface is genuinely wired, end to end, and deterministic — it is not cosmetic.** Dragging a parameter slider fires a real `POST /api/render/<id>`, the deterministic template engine rebuilds the part with **no model call**, the viewport re-fetches a cache-busted mesh (`GET /api/mesh/<id>?v=N`), and the dimension data, printability gate, and readiness card all update from the fresh geometry. I verified this in the live browser (the slider drag fired `POST /api/render/5 → 200`, then `GET /api/mesh/5?v=27 → 200`) and against the raw API.

**Determinism is real:** the same parameter set posted twice produced **byte-identical** STL meshes (sha256 match). The re-render is sub-second and never touches the LLM.

**The re-render-invalidates-slice safety invariant holds end to end** — the single most important Stage 5 correctness property. I sliced a part (G-code served at `/api/gcode/4 → 200`), then re-rendered it; the stale G-code immediately `404`ed and a send was refused with "Slice the part first." A stale-shape print cannot be downloaded or dispatched.

**Input hardening is strong.** Out-of-range values clamp to spec bounds and are honestly reported via `adjusted_params` (e.g. width 9999 → 250, height −50 → 10). Garbage (`"abc"`, `null`) coerces to the family default with `requested: null`. Rapid back-to-back renders serialize cleanly under a render lock; the latest value wins with no corruption. The mm/inch toggle round-trips correctly (80 mm → "3.15in", 60 → "2.362in", 40 → "1.575in", 2 → "0.079in"; all mathematically exact).

**One genuine (low-severity) rough edge:** a hand-crafted request body containing the non-standard JSON literal `Infinity` (or `NaN`) returns a confusing **HTTP 500** ("The server produced an out-of-range number") instead of a clean 400. The geometry path is safe (it clamps the inf to the family default); the 500 comes from the *adjusted-params echo* re-introducing the non-finite value into the response, which trips the server's `allow_nan=False` JSON guard. The SPA sliders can never emit this — it is a raw-API-only edge — and the design state recovers cleanly. See M-1.

No console errors or warnings appeared across a full design + multiple re-render + autosave cycle.

## Methodology

- **Code reviewed (product model):** `src/kimcad/templates.py` (template families, ParamSpec, clamp/coerce/gap logic, `derive_values`/`clamp_values`), `src/kimcad/pipeline.py` (`rerender`, `_build_from_template`, `_assemble_result`, `run_engine=False` hot path), `src/kimcad/webapp.py` (`_handle_render`, `_handle_slice`, `_handle_send`, geometry-version invalidation, `DemoProvider`), and the frontend: `frontend/src/components/RightPanel.tsx` (sliders, numeric entry, unit toggle), `frontend/src/useUnits.ts`, `frontend/src/api.ts` (`postRender`, `designIdFromMeshUrl`), `frontend/src/App.tsx` (`handleRerender`), `frontend/src/components/Viewport.tsx` + `frontend/src/viewport/KCViewport.ts` (mesh load + W/D/H pills).
- **App launch:** an existing LLM-free demo server (`serve(demo=True)`) on `127.0.0.1:8765`, serving the committed build (`/assets/kimcad.js`, `index.html` mtime 2026-06-05 21:38). Health: `{"version":"0.1.0","openscad":true,"orcaslicer":true}`.
- **Live browser:** Claude preview tools (Playwright-backed) drove the real SPA — DOM inspection, slider `preview_fill`, and network capture. Known limit applied: the preview tab's `requestAnimationFrame` is throttled so the canvas overlay loop doesn't tick; I relied on authoritative DOM reads (`aria-label`, computed values) and real network requests, not screenshots (which timed out on the continuous-render WebGL canvas — a tooling artifact, not a finding).
- **Raw API:** `curl` against the live server for the load-bearing invariants (determinism via mesh hash, slice→re-render→404, clamp/garbage/Infinity edges, rapid-render stress).
- **Tests run:** frontend `useUnits.test.ts` + `RightPanel.test.tsx` (50 passed); backend `pytest -k "rerender or template or clamp or stale or render_invalidat"` (92 passed).
- **Evidence dir:** `docs/audits/stage-5/backfill-2026-06-05/wiring-evidence/` (API response JSONs, mesh STLs + hashes).
- **Blocker/contention:** the preview browser is shared with other agents; mid-audit it was reset to the landing route by another session. I re-verified every load-bearing claim with a self-contained DOM or network measurement before that happened, per the skill's contention guidance.

## Project Gestalt

KimCad is a local-first AI → OpenSCAD → 3D-print web tool. Stage 5 is the **deterministic template engine** that makes "drag a slider and watch it change" possible: instead of the LLM writing OpenSCAD on every nudge (Stages 1–4, one model call per render), a registry of seven parametric **template families** (snap_box, open box, enclosure, tube, wall_hook, cable_clip, drawer_divider) maps a plan's `object_type` to typed, range-bounded parameters and emits OpenSCAD by pure string substitution. A re-render is a sub-second local pass — no model in the loop — which is exactly what live sliders need.

Each family declares its parameters as data (`ParamSpec`: name/label/default/min/max/step/unit/integer/axis) and an analytic bounding box, so the same definition drives codegen, the printability gate target, and the JSON the slider UI consumes. The web layer exposes this at `POST /api/render/<id>` (the live-slider endpoint), which rebuilds the part via `Pipeline.rerender(...)`, replaces the design's mesh, bumps a per-design `geometry_version`, and drops any cached slice/G-code so a stale shape can never be printed.

The UI (`RightPanel.tsx` → `ParametersCard` → `SliderRow`) renders one slider per backend parameter, debounces a drag ~150 ms, posts the values, and re-syncs the sliders to the server's clamped truth. A clickable value label opens an inline numeric input; a mm/inch toggle (`.kc-unit-toggle`, backed by a localStorage-persisted `useUnits` store) converts the display while keeping all state and the wire format in mm. The viewport (`KCViewport`) loads the real `*.oriented.stl` and projects W/D/H dimension pills.

**Demo-mode note (intentional, not flagged):** `DemoProvider` is LLM-free and always returns `object_type: "box"` (→ snap_box family) for any normal prompt, with keyword scenarios (`demo:gatefail`, `demo:experimental`) for the error/offer states. This is the documented demo behavior.

## Findings By Severity

### Critical
None found.

### High
None found.

### Medium

#### M-1 `Infinity`/`NaN` in a re-render body returns a confusing 500 instead of a clean 400
- **Severity:** Medium (Low real-world reach; raw-API-only — promoted to Medium only because it returns a 5xx where a 4xx is the contract).
- **Location / route:** `POST /api/render/<id>`
- **Element or workflow:** raw parameter-values body containing a non-standard JSON literal.
- **What the user sees (raw API client):** `HTTP 500 {"error": "The server produced an out-of-range number."}` — a server-error shape, implying KimCad crashed, for what is actually bad client input.
- **What actually happens:** Python's `json.loads` accepts the non-standard `Infinity`/`NaN`/`-Infinity` literals, so `values={"width": inf}` reaches the handler. The **geometry path is safe** — `_coerce_finite` (templates.py:53) maps the inf to the family default (80), and the mesh renders correctly. But the *adjusted-params echo* in `_handle_render` does `float(req)` on the raw requested value (`webapp.py:1816`), stores `req_num = inf` in `adjusted_params` (`webapp.py:1822`), and then `_json`'s `allow_nan=False` (`webapp.py:805`) refuses to serialize it → `ValueError` → the generic 500. The design state survives; the very next valid render returns 200.
- **What should happen:** a non-finite requested value should be reported as `requested: null` (the existing contract for a "non-numeric value was rejected"), and the response should be a normal 200 with the clamped geometry — or a 400 if the body is judged invalid. It should never be a 500.
- **Evidence:** `wiring-evidence/e_inf.json` (`{"error":"The server produced an out-of-range number."}`, HTTP 500); recovery confirmed in `e_recover.json` (next render HTTP 200, width back to a valid value). Mechanism: `src/kimcad/webapp.py:1815-1822` (the unguarded `float(req)` echo) + `:805` (`allow_nan=False`). Contrast: a non-numeric string `"abc"` is handled perfectly (`e_garbage.json`: `requested: null`, HTTP 200) — only the *finite-float-that-isn't-finite* case slips the guard.
- **Likely cause:** the `float(req)` guard at webapp.py:1816 catches `TypeError`/`ValueError` (non-numeric) but not the finite-but-not-finite case (`inf`/`nan` parse to valid floats).
- **Suggested fix:** in the `try` block, after `req_num = float(req)`, add `if not math.isfinite(req_num): req_num = None; same = False` (mirroring the non-numeric branch). One line; keeps the contract uniform and the response a clean 200.
- **Suggested test coverage:** an API test posting `{"values": {"width": Infinity}}` (and `NaN`) asserting HTTP 200 with `adjusted_params[*].requested == null` and a finite, clamped applied value — the test that would have caught this.

### Low

#### L-1 Demo mode confines the live-slider walkthrough to the snap_box family (coverage note)
- **Severity:** Low (intentional demo behavior; flagged only as an audit-coverage limitation).
- **Location / route:** `POST /api/design` (demo provider) → `RightPanel` sliders.
- **What the user sees:** every normal prompt in the live demo produces a `box` (snap_box) with width/depth/height/wall sliders.
- **What actually happens:** `DemoProvider.generate_design_plan` (`src/kimcad/webapp.py:298-321`) hardcodes `object_type="box"` for any non-keyword prompt, so the tube/wall_hook/cable_clip/enclosure/drawer_divider families — and the tube's `gaps=(("id","od",1.0),)` ordering constraint (`templates.py:384`) — are **not reachable through the running demo UI**. They are reachable only via the real LLM provider or by posting a non-box plan directly.
- **What should happen:** nothing to change — this is the documented LLM-free demo design. Noting it so the reader knows the gap-ordering invariant was verified via the unit suite (92 backend tests, incl. clamp/gap cases), not the live demo.
- **Evidence:** `wiring-evidence/tube_design.json` (prompt "a tube" → `template: snap_box`, `object_type: box`); `DemoProvider` at `src/kimcad/webapp.py:307-313`.
- **Likely cause:** by design (demo determinism).
- **Suggested fix:** optional — a `demo:tube`-style keyword scenario (mirroring `demo:gatefail`) would let a hands-on walkthrough exercise the gap-ordering clamp on the tube family. Not required for ship.
- **Suggested test coverage:** already covered — the tube gap constraint is exercised in the backend template tests.

## Missing Or Partial Features

None. Every Stage 5 promise — live sliders, numeric entry, mm/inch toggle, deterministic re-render, viewport + dimension + gate update on drag, and re-render invalidates a prior slice — is implemented and wired. The W/D/H dimension pills are data-bound (the canvas `aria-label` read "3D preview — 80 by 60 by 40 millimetres" off the same `getDimensions()` source); their *visual* fill is driven by `KCViewport`'s rAF loop, which I could not observe ticking in the throttled preview tab (a tooling limit, see Confidence and Gaps), but the data binding is proven.

## Backend Or System Capabilities Not Surfaced

- The `adjusted_params` signal (server clamped/coerced your input) is returned by `/api/render` and consumed defensively by the SPA, but because the range-bounded sliders never send out-of-range values, a normal user never sees it. This is correct (it exists for raw API clients) — noted, not a finding.
- `Pipeline.rerender` supports `proceed_anyway` and `confirm_print`, but the web `_handle_render` path never slices on a re-render (by design — slicing is a separate confirmed step). Correct separation; no gap.

## Confusing Or Misleading UI

None observed in the Stage 5 surface. The Parameters card sub-copy is honest ("the part re-renders locally, no AI round-trip"), the LLM-backed empty state correctly explains there are no sliders and points to the conversation panel, and the re-render error copy is reassuring and actionable ("your last version is still here. Nudge a slider to try again."). The only confusing *output* is the M-1 500 message, and only for a raw API client.

## Broken Or Suspicious Wiring Map

| UI element or workflow | Expected system connection | Actual connection | Status | Evidence |
| --- | --- | --- | --- | --- |
| Parameter slider drag | debounce → `POST /api/render/<id>` (no model) | Fires `POST /api/render/5 → 200`, deterministic template rebuild | Working | live network capture; `r1.json`; `RightPanel.tsx:228-237` |
| Viewport after drag | re-fetch fresh mesh | `GET /api/mesh/5?v=27 → 200` (cache-busted) | Working | live network; `webapp.py:1854` |
| Re-render determinism | same input → same geometry | byte-identical STL (sha256 match) | Working | `mesh_after_r1.stl` == `mesh_after_r2.stl` |
| Dimension pills / report dims | bound to re-rendered bbox | dims X/Y/Z update to 120/60/90 then 150; aria-label exact | Working | `r1.json`; req `22276.30` body; canvas aria-label |
| Re-render invalidates slice | bump geometry_version, drop G-code | `/api/gcode/4` 200 → after re-render → 404; send refused | Working | slice/gcode/send curl sequence; `webapp.py:1831-1839` |
| Out-of-range clamp + signal | clamp to spec, report adjusted | 9999→250, −50→10, `adjusted_params` populated | Working | `e_oob.json` |
| Garbage numeric input | coerce to default, `requested: null` | "abc"/null → default 80/2.0, requested null | Working | `e_garbage.json` |
| `Infinity`/`NaN` body | clean 400 or 200 with requested:null | **HTTP 500** (geometry safe, echo trips JSON guard) | **Broken (Low reach)** | M-1; `e_inf.json`; `webapp.py:1816,805` |
| mm/inch toggle | convert display, keep wire mm | 80mm→"3.15in" etc.; sliders stay mm internally | Working | live DOM read; `useUnits.ts`; 50 passing tests |
| Rapid successive drags | serialize, latest wins, no corruption | 5 back-to-back 200s; final = last value (220) | Working | `rr_*.json`; `render_lock` `webapp.py:669` |
| Unknown / non-template rid | 404 with clear message | `/api/render/99999` → 404 "couldn't be found" | Working | curl; `webapp.py:1777-1786` |
| Numeric-entry revert (empty/garbage) | no re-render, revert | covered, no `onRerender` fired | Working | `RightPanel.test.tsx:700-711` |

## Test Assessment

Coverage for Stage 5 is genuinely behavioral, not rendering-only, and it is strong.

- **Frontend (50 passing, `RightPanel.test.tsx` + `useUnits.test.ts`):** debounce coalescing of a rapid drag into one re-render with the latest value; re-sync to server-clamped values; inch↔mm round-trip on both the readout and the dims table; out-of-range inch entry clamps to mm bounds; empty/non-numeric entry reverts with no re-render; sub-0.1mm mm edit not swallowed by the no-op guard; integer-spec rounding; debounce cancels on unmount; per-axis chip rendering. These assert *behavior and emitted values*, not just that a component mounted.
- **Backend (92 passing, `-k "rerender or template or clamp or stale or render_invalidat"`):** template emit, clamp/coerce (incl. non-finite), gap-ordering, the rerender path, and slice-invalidation/stale-geometry races.

**Highest-value test gaps (each tied to a finding):**
1. **API test for non-finite re-render input (catches M-1):** post `{"values":{"width": Infinity}}` and `NaN`; assert HTTP 200, `adjusted_params[*].requested == null`, finite clamped `applied`. Layer: API/integration. This is the one real defect with no guarding test today.
2. **(Optional, ties to L-1)** if a `demo:tube` scenario is added, an E2E that drags `id` past `od` and asserts the gap clamp surfaces in the live demo — currently only unit-covered.

## Recommended Repair Plan

1. **Immediate blockers:** none — Stage 5 is shippable as-is.
2. **Core wiring fixes:** none — all promised flows are wired end to end.
3. **Feature completion:** **M-1** — guard the `adjusted_params` echo against non-finite requested values (`webapp.py:1816`) so `/api/render` returns a clean 200/400, never a 500. One line + one API test.
4. **UI/UX cleanup:** none required. (Optional L-1: add a `demo:tube` keyword scenario for richer demo coverage.)
5. **Test coverage:** add the non-finite re-render API test (gap #1) to lock M-1's fix.

## Confidence And Gaps

- **Fully audited (live + raw API + code, with evidence):** slider drag → `POST /api/render` → fresh mesh fetch; re-render determinism (byte-identical mesh); re-render-invalidates-slice (gcode 404 + send refusal); out-of-range clamp + `adjusted_params`; garbage coercion; rapid-render serialization; unknown/non-template rid handling; mm/inch conversion math; the `Infinity`/`NaN` 500 (M-1) and its recovery; gate + readiness update on drag (status `completed`, gate-only attribution per the `run_engine=False` hot path).
- **Partially audited:** the **visual** W/D/H dimension pills — the *data binding* is proven (canvas aria-label is exact, sourced from `getDimensions()`), but the pills' on-screen fill is driven by `KCViewport`'s `requestAnimationFrame` loop, which is throttled in the headless/backgrounded preview tab, so I could not observe the pills painting text/position live (computed opacity stayed 0). This is a preview-tool limitation, not a wiring defect; the pill-fill logic is plain and reviewed (`KCViewport.ts:436-454`).
- **Unreachable in the live demo:** the tube/wall_hook/cable_clip/enclosure/drawer_divider families and the tube gap-ordering clamp — `DemoProvider` always builds a box (L-1). Verified instead via the backend test suite.
- **Unverified:** a real-LLM re-render lineage (out of scope for the LLM-free demo and for Stage 5, which is by definition the no-model path); cross-browser viewport rendering (single Chromium preview); screenshot evidence (the WebGL canvas hung the screenshot path — confirmed a tooling artifact, all claims re-verified via DOM/network).

## Appendix

- **Commands run (setup/probe):** `curl http://127.0.0.1:8765/api/health` → `{"version":"0.1.0","openscad":true,"orcaslicer":true}`; `preview_list` → server `kimcad-demo` port 8765 running.
- **Live browser actions:** `preview_eval` DOM reads (slider rows, unit toggle, dim pills, localStorage); `preview_fill input[name=width]=150`; `preview_network` (captured `POST /api/render/5 → 200`, `GET /api/mesh/5?v=27 → 200`, `POST /api/designs/save → 200`); `preview_console_logs` (no warnings/errors).
- **Raw API sequences:** design → render → determinism hash; slice → re-render → gcode 404 → send refused; out-of-range / garbage / Infinity / non-dict bodies; rapid 5× render; wall-to-min.
- **Tests:** `cd frontend && npx vitest run src/useUnits.test.ts src/components/RightPanel.test.tsx` → 50 passed; `python -m pytest tests/ -k "rerender or template or clamp or stale or render_invalidat" -q` → 92 passed.
- **Evidence files (`docs/audits/stage-5/backfill-2026-06-05/wiring-evidence/`):** `d1_design.json`, `r1.json`/`r2.json`, `mesh_after_r1.stl`/`mesh_after_r2.stl` (sha match), `s1.json`, `e_oob.json`, `e_garbage.json`, `e_inf.json`, `e_recover.json`, `tube_design.json`, `exp.json`, `rr_100..220.json`, `thin.json`, `final.stl`.
- **Notable code refs:** `src/kimcad/webapp.py:1764-1855` (`_handle_render`), `:1816`+`:805` (M-1), `:298-321` (`DemoProvider`, L-1); `src/kimcad/pipeline.py:647-714` (`rerender`); `src/kimcad/templates.py:53-61` (`_coerce_finite`), `:202-253` (clamp/gaps); `frontend/src/components/RightPanel.tsx:36-237`; `frontend/src/useUnits.ts`; `frontend/src/viewport/KCViewport.ts:436-464`.
</content>
</invoke>
