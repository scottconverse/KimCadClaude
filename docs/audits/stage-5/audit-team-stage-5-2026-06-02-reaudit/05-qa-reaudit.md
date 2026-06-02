# Runtime QA Re-Audit — KimCad (Stage 5 remediation)

**Date:** 2026-06-02
**Role:** QA Engineer (re-audit)
**Scope:** Verify the 4 prior findings (QA-001..QA-004) are closed at RUNTIME, and screen for any NEW runtime regression introduced by the remediation.
**Env:** Windows 11; Python 3.14.3 (`.venv`); `python -m kimcad.cli web --demo --port 8783` launched with cwd `C:/Users/scott/dev/kimcad` (so bundled OpenSCAD/OrcaSlicer resolve). Remediation **UNCOMMITTED**. Exercised with `curl`. Bundled OrcaSlicer + real slicing used.
**Posture:** Balanced.

---

## TL;DR

All four prior findings are **closed at runtime**. The two Minors (QA-001, QA-002) and two Nits (QA-003, QA-004) are fixed and verified live. The load-bearing safety property (geometry-changing re-render invalidates the cached slice/G-code) still holds, clamping still works, and every previously-green error/method/body-guard path is intact. The remediation introduced **no new runtime regression**. `pytest tests/test_slicer.py tests/test_webapp.py` → **86 passed**, including the new gate-fail safety test.

## Severity roll-up (re-audit): **0 / 0 / 0 / 0 / 0** (Blocker / Critical / Major / Minor / Nit)

---

## Per-finding closure (with curl evidence)

### QA-002 (Minor) — unknown-id vs no-parameters 404 split — **CLOSED**
- `POST /api/render/999999 {"values":{"width":150}}` → **404 `{"error":"Design not found."}`** (was the misleading "no adjustable parameters"). New, distinct message confirmed.
- Known template id still re-renders: `POST /api/render/1 {width:150,...}` → **200**, `mesh_url:"/api/mesh/1?v=1"`, dims/volume recomputed.
- Note: in `--demo` every design is template-backed, so the "no adjustable parameters" (known-id-with-no-template) branch is not reachable live; confirmed the unknown-id message is the new distinct one. The known-but-no-template branch is covered in code (`known = rid in registry`) and by unit test.

### QA-004 (Nit) — generic 404 voice — **CLOSED**
- `GET /api/nonsense` → **404 `{"error":"Not found."}`** (capital N, period).
- `POST /api/render/abc` (non-int id) → **404 `{"error":"Not found."}`**.
- `POST /api/bogus` (unknown POST route) → **404 `{"error":"Not found."}`**. Consistent across all three.

### QA-003 (Nit) — slice-failure note (signed exit + plain-English hint) — **CLOSED**
- 250×250×250 / 8 mm-wall part, `POST /api/slice/1 {bambu_p2s,pla}` → **200** `{"sliced":false,"reason":"failed","note":"orca-slicer exited -50: no slicer output — the part may be too large or too solid for this printer/profile; try a smaller or thinner-walled part."}`.
- Signed exit code **-50** (not `4294967246`), no dangling colon, plain-English hint present. Graceful degrade (HTTP 200, mesh preserved) intact.

### QA-001 (Minor) — build-volume gate-fail unreachable via demo — **CLOSED (no code change, by design)**
- `POST /api/render/1 {width:250,depth:250,height:250,wall:8}` → **gate `pass`**, `volume.fits` "Fits the Bambu Lab P2S build plate." Clamp caps each axis at 250 mm, under the 256³ envelope, so the gate stays green — confirmed live.
- The gate-fail path is now exercised by the new unit test `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (forces a dim.mismatch via a width-120 re-render against an 80-rendering stub; asserts gate=fail → gcode invalidated → slice `reason:"gate_failed"` → send refused). **Passes.**

## Load-bearing safety property — **HOLDS**
- Design 1 → `POST /api/slice/1` → **sliced:true** (88210 lines, gcode_url) → `GET /api/gcode/1` **200** (193356 B) → `POST /api/render/1 {width:200}` (`mesh_url:?v=2`) → `GET /api/gcode/1` → **404 `{"error":"g-code not found"}`**. Stale slice invalidated on geometry change.

## Regression screen (previously-green behavior) — **ALL INTACT, no new findings**
- Clamping: `width:99999`→**250.0**; `width:"abc"`→**80.0**; `width:1e999` (Infinity)→**80.0**. All HTTP 200, no 500.
- Error paths: non-dict `values`→**400** "Provide the parameter values to re-render."; malformed JSON→**400** "invalid request body"; `[1,2,3]`→**400** "invalid request body".
- Body-size guard: 1.5 MiB body→**413** "Request body too large."
- Method discipline: `DELETE /api/options`→**405**, `Allow: GET, HEAD, POST`. `HEAD /api/mesh/1`→**200** header-only.
- Recovery after slice failure: re-render to 100×80×50 → `POST /api/slice/1`→**sliced:true** (92570 lines). Happy path recovers.

## NEW findings: **none.**

## Couldn't run
- LLM-backed "no adjustable parameters" 404 branch — unreachable in `--demo` (every design is template-backed); verified via code + unit test, not live. As designed/expected per directive.

## Final rollup: **0 / 0 / 0 / 0 / 0 — all prior findings closed, no new runtime regression. Stage 5 remediation is runtime-clean.**

Server on 8783 was taskkilled (PID 27640) after the run; port confirmed down.
