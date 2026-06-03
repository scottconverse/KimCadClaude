# Stage 7 — QA Engineer Deep-Dive

**Role:** QA Engineer (runtime behavior across CLI, web API, readiness payload contract)
**Posture:** Balanced
**Repo:** `C:\Users\scott\dev\kimcad` @ branch `stage-7-smart-mesh`, head `a89841c`
**Date:** 2026-06-02 (work continued 2026-06-03)
**Env:** Windows 11, Python venv `.venv/Scripts/python.exe`, bundled OpenSCAD at `tools/openscad/openscad.exe`. PrintProof3D engine **intentionally absent** on disk (degrade path under test). Model-free demo server on `127.0.0.1:8790`.

---

## Summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 1 |
| Nit      | 1 |

**Verdict from the QA chair: no runtime blocker to merge+tag.** The readiness path is clean end-to-end. The `/api/design` and `/api/render` payloads carry a `report.readiness` whose shape matches the frontend `ReadinessPayload` type field-for-field, and which the `RightPanel.tsx` card actually consumes. Every error/adversarial input returns the correct typed 4xx with no 5xx and no traceback leak. The gate-FAIL slice/send refusal holds at the HTTP layer (verified via source + passing webapp tests). The "engine configured-but-missing → degrade, never break the build" default is real at runtime. Console-safety holds in the real CLI because `main()` forces UTF-8 on stdout/stderr before any report prints.

Two non-blocking findings below: one Minor (a latent cp437-console encode hazard guarded only by a best-effort reconfigure), one Nit (the demo's slider clamps mean a gate-FAIL card can't be exercised live in the demo — by design, but worth a note for future manual QA).

---

## What I ran (live, observed)

### 1. Server start (model-free demo)
```
.venv/Scripts/python.exe -m kimcad.cli web --demo --port 8790
```
Came up first poll; `netstat` showed `127.0.0.1:8790 LISTENING` (PID 14196). `GET /api/options` → 200.

### 2. POST /api/design — the readiness PASS card (observed JSON)
```
curl -s -X POST http://127.0.0.1:8790/api/design -H "Content-Type: application/json" -d '{"prompt":"a snap-fit box"}'   → HTTP 200
```
```json
{
  "status": "completed",
  "plan": { "object_type": "box", "summary": "Demo part for: a snap-fit box",
            "target_bbox_mm": [80.0, 60.0, 40.0] },
  "report": {
    "gate_status": "pass",
    "headline": "Dimensions match: 80.0 × 60.0 × 40.0 mm.",
    "dims": [ {"axis":"X","target":80.0,"actual":80.0,"ok":true},
              {"axis":"Y","target":60.0,"actual":60.0,"ok":true},
              {"axis":"Z","target":40.0,"actual":40.0,"ok":true} ],
    "findings": [ {"level":"pass","code":"mesh.solid","message":"Closed, watertight solid."},
                  {"level":"pass","code":"dim.match","message":"Dimensions match: 80.0 × 60.0 × 40.0 mm."},
                  {"level":"pass","code":"volume.fits","message":"Fits the Bambu Lab P2S build plate."},
                  {"level":"pass","code":"wall.ok","message":"Wall 2.0 mm is adequate."} ],
    "watertight": true, "volume_mm3": 38784.0, "orientation": "rests on most stable facet",
    "readiness": {
      "score": 92,
      "verdict": "Ready to print",
      "tone": "pass",
      "confidence": "Medium",
      "risks": [],
      "recommendations": ["Slice for PLA on the selected printer's profile."],
      "comparison": null,
      "attribution": "KimCad printability gate"
    }
  },
  "template": "snap_box",
  "parameters": [ width 80 (10–250), depth 60 (10–250), height 40 (10–250), wall 2.0 (0.8–8.0) ],
  "has_mesh": true, "prompt": "a snap-fit box", "mesh_url": "/api/mesh/2"
}
```
**Matches the expected PASS card exactly:** score 92, verdict "Ready to print", confidence "Medium", attribution "KimCad printability gate", comparison null, empty risks. All 8 `ReadinessPayload` fields present (`score, verdict, tone, confidence, risks[], recommendations[], comparison, attribution`).

### 3. POST /api/render/<id> — live re-render (observed JSON)
```
curl -s -X POST http://127.0.0.1:8790/api/render/2 -H "Content-Type: application/json" \
  -d '{"values":{"width":120,"depth":90,"height":50,"wall":2.0}}'   → HTTP 200
```
```json
{ "mesh_url": "/api/mesh/2?v=1", "template": "snap_box",
  "report": { "dims": [X 120 ok, Y 90 ok, Z 50 ok],
    "readiness": { "score": 92, "verdict": "Ready to print", "tone": "pass",
      "confidence": "Medium", "risks": [],
      "recommendations": ["Slice for PLA on the selected printer's profile."],
      "comparison": null, "attribution": "KimCad printability gate" } } }
```
- Re-render **carries a fresh `report.readiness`** (gate-only) — confirmed.
- **Gate-consistent** (new 120×90×50 dims all `ok`, gate pass, card pass) — confirmed.
- **No engine attribution added** — attribution stays `"KimCad printability gate"`, exactly as `rerender(... run_engine=False)` dictates. Confirmed.
- `comparison: null` on the re-render (the drag doesn't record/compare history) — confirmed, consistent with the design intent.
- `mesh_url` is cache-busted (`?v=1`) so the viewport refetches.

### 4. CLI / `PrintReport.to_text()` — readiness line + console-safety
Direct pipeline harness with `conftest.FakeProvider` + `box_renderer`, registry forced empty (LLM path) to drive real geometry through the gate:

**PASS case** (20mm box) `to_text()`:
```
Gate: PASS
Readiness: 92/100 — Ready to print (confidence Medium; via KimCad printability gate)
  Suggest: Slice for PLA on the selected printer's profile.
```
**FAIL case** (400mm box, exceeds 256 build volume):
```
status: gate_failed | gate: fail
Readiness: 38/100 — Not print-ready (confidence Medium; via KimCad printability gate)
  Risk: Too big for the printer — Part exceeds the Bambu Lab P2S build volume
        (X 400.0 > 256, Y 400.0 > 256, Z 400.0 > 256 mm). Scale it down or split it before slicing.
```
The `Readiness:`, `Risk:`, `Suggest:`, `History:` lines all render. No `UnicodeEncodeError` in the real CLI: `main()` calls `_force_utf8_output(sys.stdout)` / `(sys.stderr)` (cli.py:443-444) before any subcommand prints. See QA-001 for the residual cp437 edge.

### 5. Adversarial / error paths (all observed)
| Input | Result |
|-------|--------|
| `POST /api/design` body `[1,2,3]` (non-object) | 400 `{"error":"invalid request body"}` |
| `POST /api/design` `{"prompt":"   "}` (empty) | 400 `{"error":"Please describe the part you want."}` |
| `POST /api/design` `{"prompt":42}` (wrong type) | 400 `{"error":"Please describe the part you want."}` |
| `POST /api/design` `{bad json` | 400 `{"error":"invalid request body"}` |
| `POST /api/render/9999` (unknown id) | 404 `{"error":"Design not found."}` |
| `POST /api/render/abc` (non-numeric id) | 404 `{"error":"Not found."}` |
| `POST /api/render/2` `{}` (no values) | 400 `{"error":"Provide the parameter values to re-render."}` |
| `POST /api/render/2` `{"values":5}` (non-dict) | 400 `{"error":"Provide the parameter values to re-render."}` |
| `PUT /api/design` (unsupported verb) | 405 |
| `GET /api/mesh/2` | 200, `model/stl`, 1284 bytes (binary STL) |
| `HEAD /api/mesh/2` | 200, header-only |
| `GET /api/mesh/9999` | 404 |

**No 5xx anywhere in the readiness path. No traceback leak. Every error is the correct typed status.**

### 6. Engine-missing degrade (never breaks the build)
- `config/default.yaml` sets `binaries.printproof3d: tools/printproof3d/printproof3d.exe`.
- `ls tools/printproof3d/printproof3d.exe` → **does not exist.**
- `Config.printproof3d_binary()` (config.py:116-126) returns `None` when the configured path is absent (`return p if p.exists() else None`), so `Pipeline._compute_readiness` never spawns the engine and `assess_readiness` runs gate-only. Observed in every payload above: `attribution: "KimCad printability gate"`, `confidence: "Medium"` — the documented degrade signature. The build completes; nothing 5xx's. Confirmed at runtime.

### 7. Test corroboration (run on this checkout)
- `pytest -k "readiness or smart_mesh or webapp or render or printproof"` → **126 passed**.
- `pytest tests/test_webapp.py -k "gate_failed or rerender_into_a_gate or readiness or refuses_to_slice"` → **2 passed** (the slice-gate authority + the rerender-into-fail safety).
- `pytest tests/test_frontend.py` → **9 passed**.

---

## Slice-gate authority at runtime (judged)

**Holds.** I could not force a gate-FAIL through the *demo* `/api/render` path (see QA-002 / Nit — the snap_box sliders clamp to 250mm < 256 build volume and wall ≥ 0.8mm, all inside the safe envelope, so the demo card can't be driven red live). I therefore verified the authority from source + the passing webapp tests:

- `test_web_refuses_to_slice_a_gate_failed_part` (test_webapp.py:63) — a gate-FAILED design returns `status: gate_failed`; `POST /api/slice/<rid>` returns `{"sliced": false, "reason": "gate_failed"}` with **no `gcode_url`**. No G-code produced.
- `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (test_webapp.py:1230) — the highest-value state-hazard test: a part that PASSED and was sliced, then re-rendered into a gate-FAILING shape, becomes **both un-sliceable and un-sendable** — `_handle_render` drops the cached slice + G-code under `lock` (webapp.py:858-862) and re-stamps `gate_status_by_rid[rid]`, so a stale slice of the old shape can never be served/sent.
- Server-side enforcement lives in `_handle_slice` / `_handle_send` (webapp.py:777, 660), keyed off `gate_status_by_rid` — a direct API client (not just the browser, which hides the controls) is refused. The card's `verdict: "Not print-ready"` (FAIL tone) and the slice refusal share the same `gate_status` source of truth, so they cannot disagree.

The "drag → comparison:null" concern is **not a hazard**: the re-render intentionally omits history comparison (and engine attribution) because a drag is not a new design. The card stays internally consistent (gate-only readiness, honestly attributed) across the drag, and the bounded score (92) never claims more confidence than the gate gives.

---

## Findings

### QA-001 (Minor) — Console / cp437: report em dash (U+2014) is not in cp437; CLI safety depends on a best-effort `reconfigure`
**Category:** Console
**Evidence:**
```
PrintReport.to_text() emits U+00B3 (³), U+00D7 (×), U+2014 (—).
"…".encode("cp1252") → OK
"…".encode("cp437")  → UnicodeEncodeError: '—' (em dash) maps to <undefined>
"…".encode("utf-8")  → OK
```
The real CLI is safe because `main()` forces stdout/stderr to UTF-8 (cli.py:443-444) before printing the report, and the readiness line uses the em dash (`Readiness: 92/100 — Ready to print`). **But** `_force_utf8_output` is best-effort: `if reconfigure is None: return` and it swallows `ValueError/OSError`. On any text stream that lacks `reconfigure` (or where the reconfigure is refused) under a `chcp 437` console or a redirected pipe, the readiness line would raise `UnicodeEncodeError` *after the work is done* — the exact failure mode the docstring at cli.py:36 says it exists to prevent. The web API is unaffected (JSON is UTF-8 over the wire; the observed `×` escape is correct JSON).
**Why this matters:** A user on a legacy OEM console, or piping `kimcad design ... | tee`, could see a crash at the moment the readiness verdict prints. Low exposure (UTF-8 reconfigure succeeds on modern Windows terminals), but it's the readiness feature's own glyph, so Stage 7 slightly widened the surface.
**Blast radius:**
- Adjacent code: every `print(...to_text())` / `print(text)` in cli.py (design, bench summary, bakeoff). The em dash is new to the readiness line; `×`/`³` were already there and *are* in cp1252 (so prior reports were cp1252-safe; cp437 was always a latent gap).
- Migration: none.
- Tests to update: none break. Consider adding one asserting `to_text()` encodes under cp437, or swap U+2014 → " - " (ASCII hyphen) in the readiness line for a zero-dependency fix.
**Fix path (recommend):** Use an ASCII separator (`-`) instead of the em dash in the `Readiness:`/`Risk:` lines of `PrintReport.to_text()` (pipeline.py:187-192). That removes the only non-cp437 glyph and makes the report encode-safe on every Windows code page regardless of whether `reconfigure` landed — defense in depth behind the existing UTF-8 force. Alternatively, harden `_force_utf8_output` to also set `errors="backslashreplace"`.

### QA-002 (Nit) — Demo's snap_box slider clamps prevent exercising a gate-FAIL card live
**Category:** Flow (test-coverage observation, not a product defect)
**Evidence:** `POST /api/render/2` with `{"width":300,"depth":300,"height":300,"wall":2.0}` returned 250×250×250 (clamped to the slider max), gate `pass`, card 92/"Ready to print". `{"wall":0.8}` returned wall 0.8 (the min) with `wall.ok`. The snap_box parameter ranges (10–250mm, wall 0.8–8.0) sit entirely inside the P2S 256mm build volume and the minimum-wall threshold, so the live demo can never produce a gate-FAIL or even a WARN card.
**Why this matters:** Purely a manual-QA ergonomics note — a reviewer eyeballing the demo will only ever see the green card and can't visually confirm the amber/red treatment. The FAIL/WARN paths are correct (verified via the harness in §4 and the passing webapp tests), so there is no product bug. The clamping is the intended UX guard (you can't drive a slider into an un-printable part).
**Fix path:** None required. For future manual-QA convenience, an optional demo template with a wider range (or a `--demo-fail` seed) would let a human see the red card without a code harness. Logged for the watchlist, not this sprint.

---

## What's working (credit)

- **Readiness payload contract is exact, end-to-end.** Python `_readiness_payload` (webapp.py:72) emits `{score, verdict, tone, confidence, risks[{title,detail,tone}], recommendations[], comparison, attribution}`; the TS `ReadinessPayload` (api.ts:28) declares the same fields; `RightPanel.tsx` `ReadinessBody` (line 224) reads every one of them and nothing more. No drift, no missing field, no extra field the card silently ignores. The `CONFIDENCE_BLURB[...] ?? ''` lookup degrades gracefully on an unknown confidence string.
- **Re-render readiness is correct by construction:** fresh gate-only verdict, no engine attribution, comparison null, gate-consistent, cache-busted mesh URL. The drag stays snappy (engine skipped) without lying about its basis.
- **Slice/send gate authority is enforced server-side**, not just hidden in the UI, and the re-render-into-fail state hazard is explicitly closed (slice cache + G-code dropped under lock, gate status re-stamped).
- **Engine configured-but-missing degrades cleanly** — `printproof3d_binary()` returns None on an absent path and the readiness falls back to the gate; the build never breaks. Verified at runtime with the real (absent) default config.
- **Error handling is uniformly typed:** 400 for bad/empty/wrong-typed bodies and missing/non-dict render values, 404 for unknown/non-numeric ids, 405 for unsupported verbs, 413 guard for oversized bodies (source). No 5xx in the readiness path; no traceback ever leaves the server.
- **Console-safety is handled** at the CLI entry (UTF-8 force before any print); the residual cp437 gap (QA-001) is minor and guarded.
- **126 readiness/webapp/render/printproof tests + 9 frontend tests pass** on this checkout.

## What I could not test
- A **live gate-FAIL card in the demo** (slider clamps prevent it — QA-002). Covered instead via a direct pipeline harness (real FAIL: 38/100, "Not print-ready", fail-tone risk) and the passing webapp gate-fail tests.
- **PrintProof3D engine-PRESENT path** (High confidence / engine attribution / score penalties) — the binary isn't on disk by design. The engine-absent degrade is the shipping default and is fully exercised; the engine-present path is covered by `test_smart_mesh.py` unit tests (PrintProofReport injected), not a live subprocess here.
- **JPEG/PNG screenshot of the rendered card** — the screenshot tool times out in this environment (known env limitation). Substituted with API/DOM-level contract checks against `RightPanel.tsx` (the component that renders the card), which is the load-bearing verification.
