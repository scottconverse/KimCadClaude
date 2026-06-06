# Stage 5 — QA Engineer Deep-Dive (audit-team backfill)

**Auditor role:** Senior QA Engineer (independent, runtime-behavior focus)
**Date:** 2026-06-05
**Project:** KimCad — local-first AI→3D-print tool
**Branch:** `stage-0-7-audit-backfill`
**Scope:** Stage 5 — live-slider re-render + deterministic geometry (`POST /api/render/<id>`) and its safety invariants (stale-slice invalidation, gate tracking, send refusal).
**Method:** API-level testing against the running demo at `http://127.0.0.1:8765/` (stdlib `urllib`, deterministic, avoids shared-preview-browser contention) plus targeted source inspection. The task brief designates API/DOM+network as authoritative.
**Evidence:** `qa-evidence/` — `suite.py`/`suite2.py`/`suite3.py`/`suite4.py` + their `*-run.txt`, `nan_probe.py`+`nan-probe-run.txt`, `slice_threshold.py`+`slice-threshold-run.txt`, `probe.py`.

---

## Severity summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 1 |
| Major    | 1 |
| Minor    | 2 |
| Nit      | 1 |
| **Total**| **5** |

---

## What's working (credit where due)

Stage 5's core promise and — more importantly — its *safety* invariants hold up under sustained adversarial testing:

- **Re-render genuinely changes geometry and dimensions track.** A re-render to 120×90×70 produces a different mesh hash than the original, and `report.dims.actual` tracks the new values exactly (T1).
- **Deterministic.** The same parameter values rendered twice produce byte-identical mesh output (`5cc938729c2f0032` == `5cc938729c2f0032`, T15).
- **Clamping is correct and the contract is honest.** Out-of-range values clamp to the spec bounds (9999→250, -50→10, wall 0.1→0.8) and `adjusted_params` reports `{requested, applied}` with `requested` typed as a number, or `null` for non-numeric input (T2/T2b). Unknown keys are ignored; missing keys back-fill defaults (T11/T21).
- **Stale-geometry / re-render-after-slice safety is airtight.** After slicing, a re-render invalidates the cached G-code: `GET /api/gcode/<id>` correctly flips from 200 to **404 "g-code not found"** (T7). A re-shaped part re-slices the *new* shape, not the old one (T12, estimate changes). A part that fails to slice **cannot be sent** — `POST /api/send` returns 404 "Slice the part first" (T16).
- **Render is correctly restricted to template-backed designs.** An LLM-backed / non-template design (`demo:experimental`, `demo:gatefail`) has `template: null` and `/api/render` returns a clean **404** with the right message — distinguishing "unknown id" from "known design, no parameters" (T3, T17).
- **Concurrency is safe.** 7 simultaneous re-renders all return 200; the final settled mesh is a well-formed binary STL with no corruption of the shared per-design output dir (T18). The `render_lock` serialization works as designed.
- **Malformed-body handling is clean** (all 400, never 500): non-JSON body, missing `values`, `values` as a list/string (T5). Bad/non-int id → 404 (T4). Bool/null/nested values coerce safely and clamp (T22).
- **Every re-render returns a fresh cache-busting `mesh_url`** so the viewport always fetches the new geometry (T19).

This is a well-defended endpoint. The two substantive findings below are the exceptions, not the rule.

---

## Findings

### QA-501 (Critical) — `/api/render/<id>` returns HTTP 500 for non-finite JSON numbers (incl. the *valid-JSON* `1e400`)

**Category:** API / Robustness

**Evidence (reproduced, `nan-probe-run.txt`):**
```
POST /api/render/13  {"values": {"width": NaN}}        -> 500 {"error":"The server produced an out-of-range number."}
POST /api/render/13  {"values": {"depth": Infinity}}   -> 500  (same)
POST /api/render/13  {"values": {"height": -Infinity}} -> 500  (same)
POST /api/render/13  {"values": {"width": 1e400}}      -> 500  (same)
```
- Observed: HTTP **500** with a generic server-error body.
- Expected: HTTP **200** with the value clamped to a finite default and reported in `adjusted_params` with `requested: null` (the contract the code's own comment at webapp.py:1812–1814 already promises).

**Root cause (pinpointed):** The *geometry* layer handles these correctly — `templates._coerce_finite` maps NaN/inf → the family default, verified directly: `clamp_values(tube, {od: nan, id: inf, height: 30}) -> {od: 16.0, id: 8.0, height: 30.0}`. The bug is isolated to the **`adjusted_params` echo** in `_handle_render` (`src/kimcad/webapp.py:1815–1822`): `float(req)` *succeeds* for `nan`/`inf` (and `1e400`, which Python's `json.loads` — and any RFC-8259 parser — parses to `inf`), so the non-finite value is appended to `adjusted_params.requested`. The response then fails `json.dumps(obj, allow_nan=False)` at `webapp.py:805`, which the `_json` fallback converts to the 500. The `try/except (TypeError, ValueError)` at line 1818 catches *non-numeric* input but not a *successfully-parsed non-finite float*.

**Why this matters:** `1e400` is **strictly valid JSON** (RFC 8259 places no range bound on number literals; confirmed `json.loads("1e400") -> inf`). A standards-compliant API client — or a fuzzer, or a serializer that emitted a large exponent — sending `{"values":{"width":1e400}}` gets a 5xx from an endpoint that should never 500 on client input. The QA severity framework lists "An API endpoint returns 500 for normal input" as a Blocker example; this is gated down to **Critical** because (a) the geometry/safety layer is unaffected (no corruption, nothing sliceable results), and (b) the SPA's range-bounded sliders never emit these values, so only raw/third-party API consumers are exposed. It remains Critical because Stage 5 explicitly exposes `/api/render` as a contract and the brief calls out "type: requested should be number-or-null" as an acceptance point — this is the one input class that violates it by 500-ing instead.

**Fix path:** In `_handle_render`, after `req_num = float(req)`, coerce non-finite to the null branch — e.g. `if not math.isfinite(req_num): req_num, same = None, False`. (`import math` is needed in `webapp.py`.) This makes the handler honor the number-or-null contract it already documents and mirrors `_coerce_finite`'s own discipline. One-line guard; no contract change.

**Blast radius:**
- Adjacent code: `_handle_render` is the only consumer of this diff logic, but the same `allow_nan=False` serialize at `webapp.py:805` guards *every* JSON response — any other handler that echoes a client-supplied float into its payload without a finite-check shares the latent risk. Quick grep for raw-float echoes recommended (none found in Stage 5 scope; the design/slice paths route floats through the report/coerce layers).
- Shared state: none. No geometry, registry, slice cache, or stored data is touched — the re-render up to the payload-shaping step already completed correctly.
- User-facing: no change for SPA users (sliders can't reach these). Raw-API consumers go from 500 → a correct 200.
- Migration: none. Additive robustness.
- Tests to update: add a unit/integration case for NaN/Infinity/`1e400` on `/api/render` asserting 200 + `requested: null`. No existing test asserts the current (buggy) 500 behavior, so nothing breaks. (Hand to Test Engineer — this is a coverage gap as well: TEST role should note no test exercises non-finite re-render input.)
- Related findings: TEST gap (non-finite render input untested).

---

### QA-502 (Major) — Gate passes parts (≥~200 mm) that then fail to slice, with a generic error

**Category:** Flow / Gate-vs-slicer consistency

**Evidence (reproduced, `slice-threshold-run.txt`):**
```
100^3 wall=3 -> gate=pass | slice sliced=True
150^3 wall=3 -> gate=pass | slice sliced=True
180^3 wall=3 -> gate=pass | slice sliced=True
200^3 wall=3 -> gate=pass | slice sliced=False reason=failed
220^3 wall=3 -> gate=pass | slice sliced=False reason=failed
250^3 wall=3 -> gate=pass | slice sliced=False reason=failed
```
Slice note (T13): `orca-slicer exited -50: no slicer output — the part may be too large or too solid for this printer.`

**Observed:** The live slider's max for each linear dimension is 250 mm. The P2S build volume is `[256, 256, 256]` (config/default.yaml:94), so the printability gate's `volume.fits` check passes the whole 0–250 slider range (250 < 256). But the actual slice (OrcaSlicer) fails with exit `-50` for parts ≥ ~200 mm/axis on this CPU-only target. The failure message ("the part may be too large") is **misleading** — the part demonstrably *fits* the plate; the slicer is hitting a resource/processing limit, not a build-volume limit.

**Expected:** A part the UI shows as gate-`pass` ("ready") should slice. Either the slider range / gate should account for the practical sliceable envelope, or the failure message should be honest about what actually happened.

**Why this matters:** A user drags the live slider into the 200–250 mm range, sees the printability card stay green (gate = pass, "Fits the … build plate"), confirms the print — and slicing fails with a generic message that contradicts the green gate they were just shown. It's a trust/UX-honesty gap. **Importantly, the safety boundary holds**: the failed slice produces no G-code, `sliced: False` is surfaced honestly (HTTP 200, not a 500), and `send` is refused (T16) — so nothing bad ships. That's why this is Major, not Critical: no corrupt/stale output, no false success; the damage is a confusing dead-end and an inaccurate error.

**Caveat / what I couldn't fully isolate:** Exit `-50` is OrcaSlicer's own code on this environment (Windows, 32 GB, 780M CPU-only). The exact threshold (~200 mm) may shift with host resources, slicer version, or the solid volume of the specific part. The *gate/slider-range vs. practical-slice-capacity mismatch* is the durable finding; the precise cutoff is environment-influenced.

**Fix path (options, for Eng + UI/UX):**
1. Categorize the slicer `-50`/no-output failure into a clearer, non-contradictory message that doesn't claim "too large" when the part fits the plate (e.g. "the slicer ran out of resources on this large part — try a smaller size"). Cheapest, addresses the trust gap directly. **Recommended.**
2. Tighten the slider `max` (or add a soft gate warning above a practical threshold) so the UI doesn't let the user reach a green-but-unsliceable state. More correct but needs a defensible threshold and risks under-restricting capable hosts.
- Recommend (1) as the immediate fix and (2) as a Stage-follow-up watchlist item, because (1) closes the contradiction with one message change and no behavioral risk, while (2) requires a host-aware threshold that's hard to pin precisely (see caveat).

**Blast radius:**
- Adjacent code: `kimcad/slicer.py` `SliceFailed.__init__` (the "-50 / no slicer output" message, slicer.py:79–92); the gate's `_check_build_volume` (printability.py:166–188); slider `max` constants (`_LINEAR`, templates.py:304) shared by snap_box / open_box / enclosure / drawer_divider — any fix to the range applies to all linear-dimension families.
- Shared state: the same `volume.fits` gate verdict feeds the slice/send refusal logic (`gate_status_by_rid`); a message change is safe, a range change touches every template family's sliders.
- User-facing: the slice-confirmation flow for large parts; the message shown on slice failure.
- Migration: none.
- Tests to update: none assert the current message. Add a test that a near-plate-max part either slices or fails with a non-contradictory message.
- Related findings: a UI/UX finding (green gate contradicts slice failure) and a Test gap (no test covers the gate-pass/slice-fail boundary). Cross-role root: the gate's fit check and the slicer's practical capacity are two different truths the product treats as one.

---

### QA-503 (Minor) — Zero-padded id aliases a real design

**Category:** API / Input handling

**Evidence (T14, `suite2-run.txt`):** `POST /api/render/00<rid>` → **200**, re-renders design `<rid>` (because `int("006") == 6`). `POST /api/render/<rid>%20` (trailing space) → 404 (rejected).

**Why this matters:** Low. `int()` accepts leading zeros, so `/api/render/006` and `/api/render/6` hit the same design. No security or data impact (ids are integers, no path traversal, the value still resolves to a legitimate in-registry id). It's a minor contract laxity — two distinct URLs map to one resource.

**Fix path:** If strict id canonicalization is desired, reject non-canonical integer strings (e.g. compare `str(int(raw)) == raw`). Optional; many APIs tolerate this. Logged for completeness, not worth blocking.

---

### QA-504 (Minor) — Slice failure message claims "too large or too solid" for a part that fits the plate

**Category:** Console/UX honesty (sub-aspect of QA-502, logged separately for the message itself)

**Evidence:** `orca-slicer exited -50: no slicer output — the part may be too large or too solid for this printer.` shown for a 200³ mm part that passes `volume.fits` on a 256³ plate.

**Why this matters:** Stand-alone from QA-502's range issue: even if the range is left as-is, the *wording* directly contradicts the just-shown green "Fits the build plate" gate. A user reads two opposite statements about the same part. Minor because it's a copy/categorization issue, fully covered by QA-502 fix option (1) — tracked separately so it isn't lost if QA-502 is deferred to the range discussion.

**Fix path:** Same as QA-502 option (1). `kimcad/slicer.py:89` message.

---

### QA-505 (Nit) — `width: true` (JSON bool) is accepted and coerced to `1.0` then clamped

**Category:** Input handling

**Evidence (T22):** `{"values":{"width": true}}` → `requested: 1.0, applied: 10.0` (Python `float(True) == 1.0`, clamped to min 10). No crash, value is safely bounded.

**Why this matters:** Essentially nothing — a JSON boolean is not a realistic slider input, and the result is safely clamped and reported. Flagged once for completeness: if strictness is ever desired, `isinstance(req, bool)` could be rejected to `null` like other non-numeric types. Not worth action.

---

## What I could not test

- **Live UI / browser slider pass.** The registered preview server (`kimcad-demo`, serverId `764490cd-…`) is bound to the `C:\dev\Claude` workspace, not this kimcad worktree's cwd, so `preview_screenshot`/`preview_network` returned "Server not found. No running servers for this workspace." I verified the slider→re-render wiring by source inspection instead (`RightPanel.tsx`: 150 ms debounce → `onRerender`, sliders always emit **mm**, native `min/max/step` in mm at lines 183–185; `useUnits.ts`: clean mm↔inch at 25.4, backend always mm, typed-input path clamps `fromDisplay`→mm→`clampToSpec`). The API layer — which the brief designates authoritative — was exercised end to end. The UI wiring is sound on inspection but was **not** confirmed against rendered pixels; recommend a quick browser confirmation when the preview is bound to this worktree.
- **Units round-trip at runtime via the UI** (mm/inch). Logic verified statically (clean); not exercised through a real toggle because the UI pass was unavailable. The backend is unit-agnostic (mm only), so there is no server-side unit risk.
- **Gap-constraint families (tube od/id) end to end via the API.** The demo provider always emits `object_type="box"` regardless of prompt, so the running demo can only ever produce a snap_box — the tube/wall_hook/cable_clip families are unreachable through the demo's `/api/design`. I verified the gap logic against the *shipped* template code directly: `clamp_values(tube, {od:20, id:100, height:30}) -> {od:20, id:19, height:30}` (the bore is correctly pulled to od−1). The runtime *handler* path for gapped families is therefore exercised at the geometry layer but not via a live `/api/render` round-trip on a gapped design (no demo route reaches it). Worth a Test-Engineer note: no live/demo path covers a non-box template family.

---

## Verdict

**Stage 5's safety-critical invariants are solid** — deterministic re-render, stale-slice invalidation, gate-tracking restriction to template-backed parts, send-refusal after a failed/absent slice, and concurrency integrity all hold under adversarial testing. Two substantive findings stand between this and a clean bill: **QA-501 (Critical)** — a valid-JSON non-finite number 500s the endpoint via the `adjusted_params` echo (one-line finite-guard fix, geometry unaffected) — and **QA-502 (Major)** — the gate passes large parts the slicer then can't process, with a contradictory error message (no safety impact; honesty/UX gap). The rest are Minor/Nit. Given the project bar is **zero findings**, Stage 5 is **NOT yet at the bar**; it is close, and both substantive items have concrete, low-risk fixes.

**Report path:** `C:\Users\scott\dev\kimcad\docs\audits\stage-5\backfill-2026-06-05\05-qa-deepdive.md`
