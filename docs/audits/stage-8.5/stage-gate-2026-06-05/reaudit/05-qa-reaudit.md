# QA Engineer RE-AUDIT — KimCad Stage 8.5 (Usability) Stage Gate

**Date:** 2026-06-05
**Branch / head:** `stage-8.5-usability` @ `6c98674` ("Stage 8.5 gate remediation (Test + QA): close all 8 remaining findings")
**Reviewer:** QA Engineer (audit-team, 5-role) — independent re-audit
**Scope:** Verify the three prior QA findings (QA-001/002/003) are fixed **at runtime**, and that the
remediation did not break the runtime safety invariants it touched.
**Builds on:** `../05-qa-deepdive.md` (the original QA pass at `95b25e0`: 0 Blocker / 0 Critical /
0 Major / 2 Minor / 1 Nit) and `../wiring-audit-stage-8.5-2026-06-05.md`.

## Method (what I actually did)
Started the demo server live via the CLI — `.venv\Scripts\python.exe -m kimcad.cli web --demo
--port 8771` (8765/8770 left untouched; 8771 confirmed free first) — and drove ~30 HTTP requests
against it covering every claim below, then stopped the server and removed all temp files. I also
re-ran the QA-relevant non-live pytest subset and ruff. Evidence below is from the live socket, not
from reading the diff.

## Severity rollup (QA re-audit lane)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 1  (QA-N1 — new: the QA-002 demo-keyword branch is runtime-correct but has no automated test)
- **Total: 1** (one new Nit). All three prior findings **RESOLVED**. No regression. Gate not threatened.

---

## Per-finding verdicts

### QA-001 — `adjusted_params` on `/api/render` when values are clamped/coerced → **RESOLVED**
Verified live on a template-backed design (id 5; sliders width/depth/height/wall, ranges
10–250 / 0.8–8.0):
- **In-range** (`width:100`) → `200`, `adjusted_params` **ABSENT**, applied width `100.0`. Correct —
  the hint only appears when the input was actually changed.
- **Out-of-range** (`width:1e9, height:-50`) → `200` with
  `adjusted_params: [{name:width, requested:1e9, applied:250.0}, {name:height, requested:-50, applied:10.0}]`
  — both clamped to the family min/max and reported.
- **Non-numeric** (`width:"abc"`) → `200`, `adjusted_params: [{name:width, requested:"abc", applied:80.0}]`
  (coerced to the family default and reported).
- **`"Infinity"` string** → `200`, `adjusted_params: [{name:width, requested:"Infinity", applied:80.0}]`.

The chokepoint behaves exactly as the original fix-path recommended: present when (and only when) a
value was adjusted, absent on an honored request. The `1e-6` float-compare avoids false positives on
clean values. Confirmed the contract holds for a programmatic (raw-JSON) client, which was the gap.

### QA-002 — gate-failed / experimental-offer states reachable in the LIVE demo → **RESOLVED**
The prompt-keyword scenarios are live-reachable AND the safety refusal still holds:
- `POST /api/design {prompt:"demo:gatefail"}` (consumer default, `experimental:false`) → `200`,
  `status: needs_experimental`, `has_mesh:false` — routes to a NON-template object and OFFERS the
  experimental generator instead of dead-ending. Correct.
- `POST /api/design {prompt:"demo:experimental", experimental:false}` → `200`,
  `status: needs_experimental` — reaches the experimental offer. Correct.
- `POST /api/design {prompt:"demo:gatefail", experimental:true}` → `200`, `status: gate_failed`,
  `has_mesh:true`, `report.gate_status:"fail"`, design id 3. The oversized `cube([300,300,300])`
  exceeds the default printer's 256³ build volume (config `bambu_p2s`), so the gate fails for real —
  this is now demoable end to end, not only unit-tested.
- **And it is still correctly refused:** `POST /api/slice/3` →
  `200 {sliced:false, reason:"gate_failed", note:"...download the model to inspect, but it can't be
  sliced or sent to a printer."}`; `GET /api/gcode/3` → `404` (no G-code ever produced);
  `POST /api/send/3` → `404 "Slice the part first, then send it to a printer."` The gate-failed part
  cannot be sliced or sent — the load-bearing invariant survives the new live path.
- `POST /api/design {prompt:"demo:experimental", experimental:true}` → `200`, `status: completed`,
  `report.gate_status:"pass"` (codegen falls through to the snap_box module, builds a clean part) —
  so opting into the generator from the offer lands on a working, gate-passing result, no dead end.

### QA-003 — bad-id wording unified ("That design couldn't be found.") → **RESOLVED**
- `POST /api/render/999999` (unknown numeric id) → `404 "That design couldn't be found."`
- `GET /api/designs/999999/reopen` (the reference wording) → `404 "That design couldn't be found."`
  — exact match, confirmed live.
- `POST /api/render/abc` (non-numeric id) → `404 "Not found."` — this is the early `int()`-parse
  guard (a syntactically invalid id, not a missing design), unchanged and out of scope for QA-003 as
  written (the finding was specifically the unknown-id message matching reopen). Noted, not a defect.

---

## Safety invariants the remediation touched — re-verified at RUNTIME

- **Gate-failed part can't be sliced or sent** — proven above on the now-live `demo:gatefail` path
  (slice refused with `reason:gate_failed`, no `gcode_url`; send 404).
- **Re-render invalidates a prior slice; the new geometry-version guard didn't break the normal
  slice/serve path.** On design id 7: sliced (`gcode_url:/api/gcode/7`, fetched = `200`, 142,840
  bytes), then `POST /api/render/7 {width:130}` → `200`; the SAME `/api/gcode/7` immediately returned
  `404 "g-code not found"` (stale slice killed). Re-slicing the new geometry returned `200` with a
  fresh G-code that fetched `200` (179,862 bytes) — so the version bump invalidates the stale slice
  **and** the normal slice→serve path is intact for the new shape. The guard works without breaking
  the happy path.
- **No raw traceback leaks.** Forced a bad slice (`printer:"NOPE"`) → `400 {"error":"Unknown printer
  or material: 'NOPE'"}` — class/message only, no stack. The server console (stdout+stderr) stayed
  completely empty across all ~30 adversarial requests (0 lines containing traceback/exception/error).
- **Masked-key contract holds.** `GET /api/settings` returns `cloud_enabled, cloud_key_masked,
  cloud_model, default_material, default_printer, experimental_enabled, has_cloud_key, materials,
  printers` — **no** `openrouter_api_key` / `cloud_key` / `api_key` field. `has_cloud_key:false`,
  `cloud_key_masked:null` (no key configured on this machine). No full key in the payload.

---

## NEW finding

### QA-N1 (Nit / Tests): the QA-002 demo-keyword routing is runtime-correct but has no automated test
**Category:** Tests (regression-protection)
**Evidence:** The remediation added a new branch to `DemoProvider.generate_design_plan` /
`generate_openscad` (`demo:gatefail` → `oversized_block` → `cube([300,300,300])`; `demo:experimental`
→ `demo_widget`). The only DemoProvider test, `tests/test_webapp.py::test_demo_provider_returns_plan_
and_module_call`, still uses prompt `"anything"` and asserts only the default box/snap_box path. No
test pins the two new keyword branches, so a future edit to the demo provider could silently break the
hands-on gate-failed / experimental-offer demo (the very states QA-002 added to make reachable)
without a red test. The behavior itself is correct — I verified all four keyword combinations live.
**Why it matters:** Negligible product risk (demo fixture only; the underlying refusal/offer logic is
covered by the existing `test_web_refuses_to_slice_a_gate_failed_part` and the experimental-offer
tests). It's a coverage gap on the new fixture branch, not a defect — exactly the kind of thing the
original QA-002 itself was (a demo-fixture observation), so it lands as a Nit.
**Fix path:** Consider a 2-line assert in the existing demo test: `demo:gatefail` →
`object_type=="oversized_block"` and its SCAD is the oversized cube; `demo:experimental` →
`object_type=="demo_widget"`. Optional, low priority.

---

## Test / lint re-check (supporting, not a substitute for the runtime checks)
- `pytest tests/test_webapp.py -m "not live" -k "render or gate_failed or rerender or adjusted or
  demo or settings or cloud_key or not_found or unknown_id or refuse or invalidat"` → **24 passed**,
  including `test_render_endpoint_unknown_id_is_design_not_found` (the QA-003 wording assertion) and
  `test_cloud_key_never_appears_in_logs` (the TEST-003 log-leak guard).
- `ruff check src/kimcad/webapp.py` → clean.

## What I did not test (honest scope)
- A real cloud round-trip and a real printer send — no key / no hardware on this machine (same scope
  caveat as the original pass; simulated `mock` send and masked-key redaction were verified).
- I exercised the gate-failed slice/send refusal via the **HTTP API** directly rather than clicking
  the SPA, because that is the safety seam (the contract). The browser-level rendering of the
  refusal/offer UI is the wiring-audit's lane; this pass confirms the backend states the demo now
  reaches and that they are correctly refused.

## Verdict
**QA re-audit: PASS.** All three prior QA findings (QA-001 `adjusted_params`, QA-002 live
gate-failed/experimental demo scenarios, QA-003 unified bad-id wording) are **RESOLVED and verified at
runtime**, and none of the remediation regressed the safety invariants it touched — the gate-failed
slice/send refusal, the re-render slice-invalidation (now with a working geometry-version guard that
leaves the normal slice/serve path intact), no-traceback-leak, and the masked-key contract all hold
over a live server. One new Nit (QA-N1: the new demo-keyword branch lacks an automated test) — does
not block the gate. Recommend proceeding.
