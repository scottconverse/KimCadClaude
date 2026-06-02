# Runtime QA Deep-Dive — KimCad (Stage 5: live-slider re-render API)

**Audit date:** 2026-06-02
**Role:** QA Engineer
**Scope audited:** The running model-free demo web server (`kimcad web --demo`) — the Stage 5 `/api/render/<id>` re-render endpoint and its interaction with `/api/design`, `/api/slice/<id>`, `/api/gcode/<id>`, `/api/mesh/<id>`, `/api/options`, plus HTTP-contract surfaces (methods, error bodies, body-size guard). Light CLI surface sanity check.
**Environment:** Windows 11; Python 3.14.3 (`.venv`); server started from repo root `C:/Users/scott/dev/kimcad` on `127.0.0.1:8781`; bundled OpenSCAD (`tools/openscad/openscad.exe`) and bundled OrcaSlicer resolved relative to the repo cwd; demo mode (no LLM — `DemoProvider` + `snap_box` template). Exercised with `curl`.
**Auditor posture:** Balanced.

---

## TL;DR

The Stage 5 re-render path behaves exactly as claimed under real HTTP requests. `/api/design` → `/api/render/<id>` rebuilds a template-backed part deterministically with **no model call**, echoes clamped values, recomputes the report dims, and returns a versioned `mesh_url`. The load-bearing safety property — **a geometry-changing re-render invalidates the cached slice/G-code** — holds at runtime: after a re-render, `GET /api/gcode/<id>` returns 404. Input handling is solid: out-of-range numbers clamp, non-numeric/NaN/Infinity fall back to defaults, oversized and malformed bodies get clean 4xx, and no request I threw produced a 500 traceback. No Blockers, Criticals, or Majors. Two Minors and two Nits, all on cosmetics/messaging of already-graceful failure paths. One scenario in the directive — "a re-render that exceeds the build volume flips the gate to fail" — is **not reachable through the demo `snap_box` template**, by design (clamps cap every linear axis at 250 mm, under the smallest 256 mm printer envelope); the gate-fail→slice-refused wiring itself is present and test-covered.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 2 |

## What's working

- **Design contract is exact.** `POST /api/design {"prompt":"a box"}` → `status: "completed"`, `has_mesh: true`, `template: "snap_box"`, `mesh_url: "/api/mesh/1"`, and `parameters` = `[width, depth, height, wall]`, each a fully typed `{name,label,value,min,max,step,unit,integer}`. Report gate `pass`, dims 80×60×40 all `ok`. Evidence: response body verbatim in Appendix A1.
- **Re-render is deterministic and model-free.** `POST /api/render/1 {"values":{"width":150,...}}` → `width` echoed `150.0`, report dims X target/actual both `150.0`, `volume_mm3` recomputed 38784 → 65664, and a **versioned** `mesh_url: "/api/mesh/1?v=1"`. The version suffix increments on each re-render (`?v=1` … `?v=8`). No LLM is wired in `--demo` (`DemoProvider`), confirmed by sub-second responses and the fixed template. Evidence: A2.
- **Slice invalidation holds (the load-bearing safety property).** Sequence: design 1 → `POST /api/slice/1` (real OrcaSlicer, 88210 G-code lines, 193349-byte 3mf served at `/api/gcode/1`) → `POST /api/render/1` changing `width` to 200 → `GET /api/gcode/1` now returns **404 `{"error":"g-code not found"}`**. The stale slice of the prior shape can no longer be downloaded, sliced, or sent. Evidence: A3.
- **Boundary clamping is correct.** `width:99999` → `250.0` (max), `wall:-5` → `0.8` (min), echoed clamped, gate recomputed against the clamped values, HTTP 200, no raw value injected. Evidence: A4.
- **Garbage input degrades safely.** `width:"abc"` → falls back to default `80.0`; `width:1e999` (parses to JSON Infinity / non-finite) → falls back to `80.0`. No 500. Evidence: A5. (Backed by `_coerce_finite` in `templates.py`.)
- **Error paths are clean, typed, and traceback-free.** Unknown id → 404 "This design has no adjustable parameters."; non-dict `values` → 400 "Provide the parameter values to re-render."; malformed JSON → 400 "invalid request body"; JSON array/scalar body → 400 "invalid request body"; non-integer id → 404 "not found"; oversized 1.5 MiB body → 413 "Request body too large." (no body drained); unknown printer on slice → 400 "Unknown printer or material: 'nonexistent'". Evidence: A6.
- **Mesh cache-buster query is stripped.** `GET /api/mesh/1?v=2` → 200, fresh STL served (`Content-Type: model/stl`), the `?v=` discarded before id parse. Evidence: A7.
- **Slice is idempotent + cached.** A second identical `(rid, printer, material)` slice returned in **2.5 ms** with identical output — OrcaSlicer was not re-run (the first slice took several seconds). Evidence: A8.
- **Slice failure degrades gracefully (no 500).** A pathological 250×250×250 mm, 8 mm-wall solid (2.8 M mm³) made OrcaSlicer exit non-zero; the server returned **HTTP 200** `{"sliced":false,"reason":"failed", ...}` and the validated mesh stayed downloadable. The happy path recovered immediately afterward (A1/PETG slice succeeded, 105626 lines). Evidence: A9, A10.
- **HTTP method + verb discipline.** `DELETE` → 405 with `Allow: GET, HEAD, POST`; `HEAD /api/mesh/2` → 200 header-only (Content-Length 1284, no body); unknown route → 404. Evidence: A11.
- **Design input validation.** Empty prompt and non-string prompt both → 400 "Please describe the part you want."; empty `values:{}` on re-render → 200 with all four params back-filled to defaults. Evidence: A12.
- **CLI surface is coherent.** `kimcad --help` lists `design / web / bench`; `kimcad design --help` documents `--printer/--material/--backend/--out/--proceed-anyway/--slice/--send` with accurate descriptions (`--proceed-anyway`: "Continue past a failing Printability Gate (advanced)"). Evidence: A13.

## What couldn't be assessed

- **A live build-volume gate FAILURE via the demo re-render** — not reachable, by design. The only gate-`FAIL` conditions are non-watertight mesh, dimension mismatch, and build-volume-exceeded (`printability.py:_check_build_volume`). The deterministic `snap_box` always renders exactly to spec (so never a dim mismatch) and is always watertight, and every linear parameter clamps at ≤ 250 mm — under the smallest configured printer envelope (256³ for the P2S/A1). So no value set sent to `/api/render` on the default printer can trip `volume.exceeds`. I confirmed the **opposite** at runtime: a max 250³ cube renders, the gate still `pass`es, and it "Fits the Bambu Lab P2S build plate." The gate-fail→slice/send-refused wiring is present in code (`gate_status_by_rid` → `_handle_slice`/`_handle_send` refuse on `"fail"`) and is covered by `tests/test_webapp.py::test_web_refuses_to_slice_a_gate_failed_part` (which forces a fail with a mocked dim mismatch). I did not find a runtime path to flip it through the demo template — see QA-001 (Minor) for the nuance.
- **The real LLM CLI `design` flow** — the CLI `design` subcommand has no `demo` backend (`--demo` is web-only); it runs the on-device model (`gemma4:e4b` via the configured backend). Per directive scope ("don't belabor the CLI; the API re-render is the Stage 5 focus") and to avoid a slow CPU-bound model run, I did not execute a real-LLM design. The CLI help/flags are correct and the re-render path is fully template-driven and independent of the LLM.
- **Browser-rendered UI / screenshots** — out of remit (the JPEG screenshot tool is broken in this env, per directive); curl-level runtime was the assignment.
- **Real-hardware print / non-loopback connector** — intentionally post-release; the `mock` (simulated) connector + bundled OrcaSlicer are the correct altitude. Not flagged.

---

## Product shape

KimCad is a local-first "plain English → printable 3D part" pipeline. Stage 5 adds a **live-slider re-render**: once a prompt resolves to a parametric template family, the browser can drag sliders and POST new values to `/api/render/<id>`, which rebuilds the OpenSCAD geometry deterministically (no model call), re-runs the printability gate, and replaces the design's mesh — while **invalidating any cached slice/G-code** so a stale shape can never be printed. The runtime under test is the stdlib `ThreadingHTTPServer` in `webapp.py`. QA focused on the API contract, the invalidation safety property, input robustness/clamping, and HTTP error discipline — the dimensions that matter for a re-render endpoint that gates a physical print.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Design → typed parameters → mesh_url | Pass | — |
| Re-render (in-range) → versioned mesh, clamped echo, report update | Pass | — |
| Design → slice → re-render (geometry change) → G-code invalidated (404) | Pass | — |
| Re-render boundary clamp (over-max, under-min) | Pass | — |
| Re-render garbage input (string, Infinity) → default fallback | Pass | — |
| Slice → identical re-slice (idempotent cache hit) | Pass | — |
| Slice an oversized part → graceful `sliced:false` (no 500) | Pass | QA-003 (Nit) |
| Slice recovery after a failure → happy path | Pass | — |
| Mesh fetch with `?v=` cache-buster | Pass | — |
| Design input validation (empty / non-string prompt) | Pass | — |
| CLI help + flag surface | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| `width:99999`, `wall:-5` (out of range) | Clamped to 250 / 0.8, 200 | — |
| `width:"abc"` (wrong type) | Default 80, 200 | — |
| `width:1e999` (JSON Infinity / non-finite) | Default 80, 200 | — |
| `values:"notadict"` | 400 "Provide the parameter values" | — |
| Body `this is not json` | 400 "invalid request body" | — |
| Body `[1,2,3]` (valid JSON, non-object) | 400 "invalid request body" | — |
| 1.5 MiB body (> 1 MiB cap) | 413 "Request body too large." | — |
| `render/99999` (unknown id) | 404 "no adjustable parameters" | QA-002 (Minor) |
| `render/abc` (non-int id) | 404 "not found" | — |
| `slice` unknown printer | 400 "Unknown printer or material" | — |
| 250³ solid 8 mm-wall part → slice | Slicer exits non-zero → 200 `sliced:false` | QA-003 (Nit) |
| `DELETE /api/options` | 405 + `Allow` header | — |
| Empty / non-string prompt | 400 | — |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Console / Protocol / Install

### [QA-001] — Minor — Flow — The "re-render exceeds build volume → gate fails → can't slice" path is unreachable through the demo `snap_box` template

**Evidence**
1. Every linear `ParamSpec` in `templates.py` clamps to `max ≤ 250` (`_LINEAR = dict(min=10.0, max=250.0, ...)`); `wall` to `[0.8, 8.0]`.
2. The smallest configured printer envelope is 256³ mm (`config/default.yaml`: Bambu P2S and A1 `build_volume: [256, 256, 256]`).
3. `printability.py:_check_build_volume` only FAILs when an **axis** exceeds the envelope; `_check_dimensions` only FAILs on a target-vs-actual mismatch (impossible for the deterministic `snap_box`); `_check_integrity` only FAILs on a non-watertight mesh (the template is always watertight).
4. Runtime confirmation of the opposite: `POST /api/render/2 {"values":{"width":250,"depth":250,"height":250,"wall":8}}` → gate `pass`, finding `volume.fits` "Fits the Bambu Lab P2S build plate." (Appendix A9 shows the immediate slice attempt; the render verdict was `pass`.)

Observed: through the demo template, no `/api/render` value set flips the gate to `fail`. Expected (per the directive's scenario): a re-render large enough to exceed the build volume should flip the gate to `fail` and block slicing.

**Why this matters**
The gate-fail→slice/send-refused safety wiring is genuinely present (`gate_status_by_rid` set on every design/re-render; `_handle_slice` and `_handle_send` refuse on `"fail"`) and is unit-tested via a mocked dim mismatch. But a *runtime* QA pass cannot demonstrate the build-volume-exceeded variant of that safety net through the demo path, because the clamp bounds are deliberately set under the smallest printer envelope. This is a **design property (safe by construction), not a defect** — it's surfaced as a Minor so the team knows the live demo cannot exercise this particular gate-fail branch, and any manual test plan that asserts "drag the slider past the plate" against the demo will never see it fire.

**Blast radius**
- Adjacent code: `templates.py` clamp bounds; `printability.py:_check_build_volume`; `webapp.py:_handle_render`/`_handle_slice` gate gating.
- User-facing: none — the protection is conservative (parts always fit). A template family whose clamp `max` ever exceeds a configured printer's smallest axis would change this; none currently do.
- Tests to update: none required. (Optionally add a `tests` case that re-renders a hypothetical large family against a small-envelope printer to exercise the build-volume FAIL through the live `/api/render` path, complementing the existing mocked dim-mismatch test.)
- Related findings: none.

**Fix path**
No code change needed for Stage 5. If the team wants the build-volume gate-fail reachable via the live re-render (for a future template whose envelope can exceed a printer, or for demo/QA completeness), add a small-envelope test printer or a family whose `max` exceeds 256, and assert `/api/render` → gate `fail` → `/api/slice` returns `sliced:false, reason:"gate_failed"`.

### [QA-002] — Minor — API — `/api/render` conflates "unknown id" and "LLM-backed id with no parameters" into one 404 message

**Evidence**
1. `POST /api/render/99999 {"values":{"width":150}}` (an id that was never designed) → `404 {"error":"This design has no adjustable parameters."}`.
2. The same branch (`webapp.py:_handle_render`, `state is None`) serves both a genuinely-unknown id and a real LLM-backed design that has no template. The message asserts "no adjustable parameters," which is misleading for an id that simply doesn't exist.

Observed: a not-found id is reported as "This design has no adjustable parameters." Expected: a not-found id reads more like "design not found," while a known-but-LLM-backed id reads "no adjustable parameters."

**Why this matters**
A direct API consumer (agent / MCP / future SPA) cannot distinguish "I used a bad/expired id" from "this design genuinely has no sliders." Both are 404, which is the right status, but the single message can send an integrator debugging the wrong thing. Low exposure (the browser always uses a freshly-returned id), hence Minor.

**Blast radius**
- Adjacent code: `webapp.py:_handle_render` (`state is None` branch).
- User-facing: error copy only; no behavior change.
- Migration: none. (If split into two messages, no status-code change — both remain 404.)
- Tests to update: any test asserting the exact string for the unknown-id case (grep `no adjustable parameters` in `tests/test_webapp.py`).
- Related findings: none.

**Fix path**
In `_handle_render`, before the `template_state` lookup, check `registry`/`gate_status_by_rid` membership: if the id is entirely unknown, return 404 "Design not found." Reserve "no adjustable parameters" for a known id with no `template_state` entry.

### [QA-003] — Nit — API — Slice-failure `note` leaks a raw, truncated process error

**Evidence**
1. `POST /api/slice/2` on a 250³ mm, 8 mm-wall solid → `200 {"sliced":false,"reason":"failed","note":"orca-slicer exited 4294967246: "}`.
2. The `note` is the raw exit code (`4294967246` is `-50` as unsigned 32-bit) with an empty stderr tail after the colon.

Observed: the user-facing `note` is "orca-slicer exited 4294967246: " — an opaque number and a dangling colon. Expected: a plain-English note (e.g. "Slicing failed — the part may be too large or solid for this printer/profile; try a smaller part or different settings.").

**Why this matters**
The server already degrades correctly (HTTP 200, `sliced:false`, mesh still downloadable) — this is purely message quality on a rare path. The dangling colon + huge unsigned number reads like a bug to an end user. Nit, not Minor, because it only appears on an already-handled failure and doesn't affect behavior or safety.

**Blast radius** (optional for Nit — included for the one concrete hand-off)
- Adjacent code: `webapp.py:slice_registered_mesh` `SliceError` branch; `slicer.py` where the `SliceError` message is composed.
- User-facing: error copy only.
- Related findings: none.

**Fix path**
In `slicer.py` (where the non-zero-exit `SliceError` is raised), normalize the exit code to a signed value and, when stderr is empty, append a plain-English hint instead of a bare colon. Optionally map the common "too large/solid" failure to a friendlier `reason`.

### [QA-004] — Nit — API — `404` body for unknown routes / ids is terse and inconsistent in tone

**Evidence**
1. Unknown route `GET /api/nonsense` → `{"error":"not found"}`.
2. Non-integer id `POST /api/render/abc` → `{"error":"not found"}`.
3. Other 404s in the same surface use friendlier copy ("This design has no adjustable parameters.", "g-code not found", "mesh not found", "Design the part first, then send it to a printer.").

Observed: a mix of bare "not found" and full-sentence messages across 404s. Expected: a consistent voice (the friendly full-sentence style already used elsewhere).

**Why this matters**
Cosmetic consistency only; all statuses are correct. Flagged once, not belabored.

**Fix path**
Optional: standardize the generic 404 bodies to the same sentence style used by the resource-specific 404s.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| `POST /api/design` (demo, full render+gate) | sub-second | < 2 s for a local template build | pass |
| `POST /api/render` (re-render, demo) | sub-second | < 1 s (no model call) | pass |
| `POST /api/slice` (cold, real OrcaSlicer) | several seconds | category-normal for a real slice | pass |
| `POST /api/slice` (idempotent cache hit) | **2.5 ms** | near-instant | pass |
| `GET /api/mesh` / `GET /api/gcode` | instant | static-file serve | pass |

The idempotency cache (returning a prior slice in 2.5 ms vs a multi-second cold slice) is the standout — it means a UI re-confirm never re-pays OrcaSlicer cost.

## Security / privacy snapshot

- **No traceback leakage** on any path I exercised — malformed JSON, oversized body, wrong types, unknown ids, unknown printers, and a real slicer crash all returned typed 4xx/200 messages, never a 5xx stack. The handlers wrap `design_response`, `slice_registered_mesh`, and `rerender` in `except Exception` → `{type(e).__name__}: {e}` (class + message only, never the stack). I did not trigger that last-resort 500 with any input.
- **Body-size guard** (`MAX_BODY_BYTES = 1 MiB`) rejects oversized uploads with 413 **before** reading them, and sets `close_connection` so a still-streaming client gets a clean close rather than a connection abort.
- **Non-object JSON guard** rejects lists/scalars/null with 400 before any `.get()` runs (prevents an `AttributeError` drop).
- **Path-traversal guards** on `/vendor/` and `/assets/` reject any `/`, `\`, or `..` before touching the filesystem (read, not exercised live this pass — static analysis only; noted as adjacent, not a new finding).
- No auth surface in scope (local loopback demo). Nothing exposed that shouldn't be.

## Console and log observations

Server log discipline is clean: `log_message` is overridden to no-op, so the console stays quiet. No stderr noise observed during the entire session beyond the intentional slicer-failure case (which surfaced as a structured JSON `note`, not a console dump). The expected startup banner ("KimCad web UI on http://…") is buffered/not flushed to the captured log file, but the server was confirmed up via a 200 on `/api/options` — not a finding.

## Patterns and systemic observations

- **Consistent "degrade, don't crash" discipline** across every handler: slice refusals, gate failures, garbage input, and a real slicer crash all resolve to a structured 200/4xx with a typed `reason`/`error`, never a 5xx. This is the right posture for an endpoint that gates a physical print, and it held under every adversarial request.
- **Clamp-at-the-edge is the single robustness backbone.** `_clamp` + `_coerce_finite` + `_apply_gaps` in `templates.py` mean every value reaching `emit_scad` is finite, in-range, and ordering-valid regardless of what the client POSTs. The runtime evidence (99999→250, -5→0.8, "abc"→default, Infinity→default) all traces to these three functions. Because the same clamp bounds also keep parts under the printer envelope, they double as the build-volume safety margin (see QA-001).
- **Invalidation is correctly coupled to the geometry write.** `_handle_render` drops `gcode_registry[rid]` and every `slice_cache` entry for the id under the same lock as the mesh swap, so there's no window where the old G-code is served against the new mesh. Verified end-to-end (slice→re-render→404).

## Appendix: environments and artifacts

**Environment:** Windows 11; `C:/Users/scott/dev/kimcad/.venv/Scripts/python.exe` (Python 3.14.3); server `python -m kimcad.cli web --demo --port 8781` launched with cwd `C:/Users/scott/dev/kimcad` (so bundled OpenSCAD/OrcaSlicer resolve); client `curl`. Demo mode = `DemoProvider` (no LLM) + `snap_box` template.

**Key curl evidence (verbatim observed results):**

- **A1 — design:** `POST /api/design {"prompt":"a box"}` → `{"status":"completed", ..., "template":"snap_box", "parameters":[{width,...},{depth,...},{height,...},{wall...}], "has_mesh":true, "mesh_url":"/api/mesh/1"}`; gate `pass`, dims 80/60/40 all ok.
- **A2 — re-render:** `POST /api/render/1 {"values":{"width":150,"depth":60,"height":40,"wall":2}}` → `width` value `150.0`, report X target/actual `150.0`, `volume_mm3` `65664.0`, `mesh_url":"/api/mesh/1?v=1"`.
- **A3 — invalidation:** `POST /api/slice/1 {"printer":"bambu_p2s","material":"pla"}` → `sliced:true, gcode_lines:88210, gcode_url:/api/gcode/1`; `GET /api/gcode/1` → 200 (model/3mf, 193349 bytes). Then `POST /api/render/1 {width:200,...}` → `mesh_url:/api/mesh/1?v=2`, X actual `200.0`. Then `GET /api/gcode/1` → **404 `{"error":"g-code not found"}`**.
- **A4 — clamp:** `POST /api/render/1 {width:99999, wall:-5,...}` → width `250.0`, wall `0.8`, gate `pass`, HTTP 200.
- **A5 — garbage:** `{width:"abc",...}` → width `80.0` (default); `{width:1e999,...}` → width `80.0`; both HTTP 200.
- **A6 — errors:** unknown id 99999 → 404 "This design has no adjustable parameters."; `values:"notadict"` → 400 "Provide the parameter values to re-render."; `this is not json` → 400 "invalid request body"; `[1,2,3]` → 400 "invalid request body"; id `abc` → 404 "not found"; 1.5 MiB body → 413 "Request body too large."; slice unknown printer → 400 "Unknown printer or material: 'nonexistent'".
- **A7 — mesh ?v strip:** `GET /api/mesh/1?v=2` → 200, `Content-Type: model/stl`, 1284 bytes.
- **A8 — idempotent slice:** 2nd identical `POST /api/slice/2 {bambu_a1,petg}` → identical body in `time_total` 0.002521 s (cache hit, slicer not re-run).
- **A9/A10 — graceful slice failure + recovery:** `POST /api/slice/2` on 250³/8 mm part → HTTP 200 `{"sliced":false,"reason":"failed","note":"orca-slicer exited 4294967246: "}`; after re-render to 100×80×50, `POST /api/slice/2 {bambu_a1,petg}` → `sliced:true, gcode_lines:105626`, served as `model/3mf` 187768 bytes.
- **A11 — verbs:** `DELETE /api/options` → 405 + `Allow: GET, HEAD, POST`; `HEAD /api/mesh/2` → 200, Content-Length 1284, no body; `GET /api/nonsense` → 404.
- **A12 — design validation:** empty prompt → 400 "Please describe the part you want."; `prompt:12345` → 400 same; `render/2 {values:{}}` → 200, params back-filled to 80/60/40/2.
- **A13 — CLI:** `kimcad --help` → `{design,web,bench}`; `kimcad design --help` → `--printer/--material/--backend/--out/--proceed-anyway/--slice/--send` documented.

**Tools used:** curl, Python (file-creation helper for the oversized-body fixture), static read of `webapp.py` / `templates.py` / `printability.py` / `pipeline.py` / `config/default.yaml` to confirm the contracts the runtime evidence exercised.
