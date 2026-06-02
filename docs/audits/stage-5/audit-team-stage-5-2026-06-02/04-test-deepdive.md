# Test Suite Deep-Dive — KimCad Stage 5 (deterministic template engine + live sliders)

**Audit date:** 2026-06-02
**Role:** Test Engineer
**Scope audited:** Python `tests/test_templates.py`, `tests/test_pipeline_templates.py`, `tests/test_template_bench.py`, the Stage 5 additions in `tests/test_webapp.py`; frontend `frontend/src/api.test.ts`, `frontend/src/App.test.tsx`, `frontend/src/components/RightPanel.test.tsx`. Cross-checked against `src/kimcad/{templates,pipeline,webapp,template_bench}.py` and `frontend/src/{api.ts,App.tsx,components/RightPanel.tsx,components/Viewport.tsx,viewport/KCViewport.ts}`.
**Auditor posture:** Balanced
**Test framework(s):** pytest 9.0.3 (Python 3.14.3), Vitest 4.1.8 + @testing-library/react (jsdom).

---

## TL;DR

This is an unusually honest Stage 5 test surface. The load-bearing "no model call on the deterministic path" claim is asserted three independent ways — a structural `provider.openscad_calls == 0` on every template pipeline test, a runtime `_NoModelProvider` that *raises* if the model is ever touched, and a determinism check that compares the pipeline's actually-rendered SCAD against an independent pure emit. Injection/clamping (NaN, inf, non-numeric, out-of-range, tube `id<od`) is covered at the unit layer and a binary-gated live gate renders all 7 families watertight at their declared envelope. Both binaries are present in this environment, so **nothing in the Stage 5 surface skipped** — the live proofs all ran. The blind spots are two specific safety properties that are *implemented correctly but tested by nothing*: (1) a part that was re-rendered into a **gate-FAILED** shape becomes non-sliceable/non-sendable, and (2) the frontend **`renderSeq` stale-response discard** (an out-of-order re-render response must be dropped). Both are the kind of regression a future refactor silently breaks with the suite still green. Per the house rule (a safety behavior without a regression test is at least Major), those are the two Majors.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **"No model call" is proven three ways, not asserted once.** Every template-path test in `test_pipeline_templates.py` asserts `provider.openscad_calls == 0` (lines 48, 76 inverse, 103, 146, 157, 180); the benchmark wires a `_NoModelProvider` whose `generate_design_plan`/`generate_openscad` *raise* (`src/kimcad/template_bench.py:53-61`), and `test_no_model_provider_raises_on_any_model_call` (`test_template_bench.py:65`) verifies the guard itself bites. This is a structural guarantee plus a runtime guarantee plus a guard-of-the-guard — exactly right for the headline claim.
- **The determinism check is non-tautological.** `template_bench.py:216` compares `result.scad` (the SCAD that flowed all the way through `rerender` → `_build_from_template` → the renderer) against a *fresh independent* `emit_scad(family, clamp_values(...))`. The two derive the string by different paths; if a model had written geometry, or emit had drifted to something order-dependent, they would diverge. Credit: this is the right way to make "deterministic" falsifiable.
- **Clamping/injection safety is covered at the boundary.** `test_templates.py` covers out-of-range clamp (139), non-numeric→default (155), NaN/inf→default (161, the explicit TPL-003 case), back-fill missing + drop unknown keys (147), and the tube `id<od` ordering gap from both entry points — `clamp_values` (168) and `derive_values` (176). Combined with the live gate, `emit_scad` only ever sees clamped, finite numbers.
- **The concurrency test is real, not a fake.** `test_concurrent_rerenders_are_serialized` (`test_webapp.py:1281`) installs a renderer that sleeps 0.3 s and records its `[enter, exit]` interval, fires two real HTTP `/api/render` calls on two threads, then asserts the intervals do not overlap (`a1 <= b0 + 0.001`, line 1326). That actually exercises `render_lock` over a socket — it would fail if the lock were removed. Likewise `test_concurrent_identical_slices_run_once` (1086) for `slice_lock`.
- **The live family gate is a true proof and it ran.** `test_every_family_re_renders_deterministically_under_budget` (`test_template_bench.py:145`) renders + re-renders all 7 families through the real pipeline and asserts watertight + bbox ≤ 0.05 mm + deterministic + under ceiling; `test_family_renders_watertight_with_its_declared_bbox` (`test_templates.py:254`) renders each family and checks the real envelope to 0.01 mm. Both executed (binaries present) — confirmed PASSED, not skipped.
- **Cache invalidation on re-render is tested end-to-end with the real renderer.** `test_rerender_invalidates_a_cached_slice` (`test_webapp.py:1251`) slices, re-renders, re-slices, and asserts the slicer ran *twice* (`calls["n"] == 2`) — proving a re-shaped part drops its cached slice. Strong.
- **Frontend debounce/coalesce/resync are well covered.** `RightPanel.test.tsx` proves the debounce fires one `onRerender` after 150 ms (122), coalesces a rapid drag to a single call with the latest value (141), and re-syncs sliders to the server's clamped echo (158). Fake-timer use is sound — `vi.advanceTimersByTime` is wrapped in `act()` and `vi.useRealTimers()` is restored in `afterEach`.

## What couldn't be assessed

- **CI history / flake rate over time.** Not a git-CI repo with retained run logs in this environment; flakiness is assessed by construction (reading the tests), not from historical retry data. The concurrency tests use real threads + a 0.001 s overlap margin and a real socket — they are timing-sensitive *by construction* (see TEST-005), but I observed them pass on this box.
- **Behavior when only one of the two binaries is present.** Both OpenSCAD and OrcaSlicer resolve and exist here, so the "binary absent → honest skip" branch of the binary-gated tests could not be exercised; I read the `skipif` predicates and confirmed they gate on real `.exists()` checks rather than no-op'ing inside the test body (the skip is honest — see Blind spots).

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (Python), Vitest + Testing Library (frontend) |
| Test pyramid shape | Heavy, honest unit/contract layer; a thin but real integration layer (socket-level webapp tests, binary-gated live renders); no browser E2E (Viewport/three.js untested by design — see TEST-007) |
| Coverage tool | None configured (no coverage.py / nyc / vitest --coverage in scope) |
| Reported coverage | None — assessed by reading, per methodology |
| Flakiness posture | Clean; no `--retry`/`retries` config. Two concurrency tests are timing-sensitive by construction but use real overlap detection, not sleeps-as-proof |
| CI blocking? | Tests run locally via pytest/vitest; binary-gated tests run only where binaries exist (honest skip otherwise) |
| Observed counts | Stage 5 Python surface: **122 passed, 0 skipped** (test_templates 73-with-others; full Stage 5 set 122 in 30 s). Frontend: **33 passed** (6 files). Both binaries present → every binary-gated test executed. |

---

## Findings

> **Finding ID prefix:** `TEST-`
> **Categories:** Coverage / Shortcut / Flakiness / Quality / Ergonomics / Mocking / Regression / CI

### [TEST-001] — Major — Coverage/Regression — No test that a gate-FAILED re-render makes the part non-sliceable / non-sendable

**Evidence**
The re-render safety contract is stated in the handler docstring: a re-render "replaces the design's mesh and INVALIDATES any cached slice/G-code for it, so a stale slice of the previous shape can never be served, sliced, or sent" (`src/kimcad/webapp.py:781-782`). The mechanism is `_handle_render` updating the gate verdict on every re-render: `gate_status_by_rid[rid] = rep.get("gate_status") or "fail"` (`webapp.py:817`), which the slice guard (`webapp.py:736,742`) and send guard (`webapp.py:619,625`) read to refuse a failed part.

The tested cases all re-render into a *passing* shape:
- `test_rerender_invalidates_a_cached_slice` (`test_webapp.py:1251`) re-renders to a valid size and asserts the slice cache was dropped (re-slice runs).
- `test_render_endpoint_reshapes_a_template_part_without_the_model` (`test_webapp.py:1227`) re-renders bigger but still valid.

No test drives the safety-critical transition: **design PASSES → slice OK → re-render into an INVALID shape (gate FAIL) → slice and send must now be refused.** I confirmed empirically that the code does the right thing — a re-render to a gate-failing size returns a `mesh_path` that exists with `report.gate_status == "fail"` and `openscad_calls == 0`, so line 817 *would* flip the part to non-sliceable — but that correctness rests on nothing in the suite. A refactor that, say, only writes `gate_status_by_rid` inside an `if gate passes` branch, or that updates the registry mesh but forgets the gate map, would leave a **printable-from-the-server stale-but-now-invalid part** and every test would stay green.

**Why this matters**
This is the live-slider feature's single most important safety property: a user drags the wall to 0.4 mm (or the part past the build volume), the gate now FAILs, and the previously-good G-code/mesh must not be sliceable or dispatchable. The bug class that slips through is "old geometry shipped after the part was re-shaped into something unprintable" — the exact thing the docstring promises and the gate exists to prevent.

**Blast radius**
- Test files affected: add to `tests/test_webapp.py` (Stage 5 section).
- Adjacent code: the same `gate_status_by_rid` map gates both `_handle_slice` (736/742) and `_handle_send` (619/625); one test covers the slice refusal, a second assertion can cover send refusal in the same flow.
- Related findings: TEST-002 (the other untested re-render safety guard), and the gate-safety findings the Engineering/QA roles raise on `webapp.py` (ENG-001 lineage).
- Migration: none — additive test only.

**Fix path**
Add `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (binary-gated, real renderer): design a `snap_box` that passes → `POST /api/slice` → assert `gcode_url`; then `POST /api/render` with values that overflow the build volume (e.g. `width=250, depth=250, height=250` on the 256³ P2S, or wall below the printable floor) → assert the render payload's `report.gate_status == "fail"`; then `POST /api/slice` again → assert `sliced is False and reason == "gate_failed"`, and `POST /api/send` → assert `sent is False and reason == "gate_failed"`. A unit-level companion (no binary, stub renderer returning a wrong size) can assert `pipe.rerender(...).status is PipelineStatus.gate_failed` with `report.gate_status == "fail"` and `mesh_path.exists()` so the guard's precondition is pinned even where binaries are absent.

---

### [TEST-002] — Major — Coverage — Frontend `renderSeq` stale-response discard is never exercised

**Evidence**
`App.tsx` guards against an out-of-order re-render response clobbering newer geometry with a monotonic token: `const seq = ++renderSeq.current` (line 57), then on resolution `if (seq === renderSeq.current) setResult(next)` (line 62), with the same guard on the error and finally branches (64, 68). The class comment calls this out explicitly: "an out-of-order re-render response (a slow render that resolves after a newer one) can't clobber the latest geometry — only the most recent request applies" (lines 27-29).

`App.test.tsx` has exactly one test (`clears the re-render flag when a new design abandons an in-flight re-render`, line 61). It covers the *new-design* reset path (SLIDE-001) by making `postRender` a promise that never resolves and checking the flag clears. It does **not** test the renderSeq *discard*: that when render A (slow) and render B (fast) both fire, B's result wins and A's late resolution is dropped. The positive behavior of the stale guard — superseding an in-flight result — is asserted by nothing.

**Why this matters**
On a live slider, overlapping `/api/render` calls are the normal case the moment a render takes longer than the debounce window (the server serializes them via `render_lock`, so responses can absolutely arrive out of order under load). If the `seq === renderSeq.current` guard were dropped or inverted in a refactor, the viewport could snap back to a *stale, smaller* shape after the user already dragged it bigger — a visible correctness bug the suite would not catch. This is the frontend twin of TEST-001: a documented anti-stale guarantee with no regression test.

**Blast radius**
- Test files affected: `frontend/src/App.test.tsx`.
- Adjacent code: the same `renderSeq` ref also guards `handleNewDesign` (line 79) and `handleSubmit` (line 41); a test that resolves two overlapping renders out of order also indirectly protects those increments.
- Related findings: TEST-001 (server-side stale-slice safety), TEST-004 (the debounce that feeds these overlapping calls).
- Migration: none — additive test.

**Fix path**
Add to `App.test.tsx`: mock `postRender` to return two deferred promises (capture their `resolve` fns). Trigger re-render A, then re-render B (via the stub Workspace button, parameterized to send different widths). Resolve **A last** with an old payload and **B first** with the new payload; assert the rendered `result`/`mesh_url` reflects B, not A. Using manually-resolved promises (not fake timers) keeps the ordering deterministic and non-racy.

---

### [TEST-003] — Minor — Coverage — The "<1 s interactive" headline is never asserted on a real render

**Evidence**
The spec headline is "drag a slider, re-render in under a second, no round-trip." The automated gate deliberately asserts only the 5 s `RERENDER_CEILING_S` (`test_template_bench.py:160`, comment at 145-150: "so the suite can't flake"). The `<1 s` `RERENDER_TARGET_S` is checked only against synthetic `FamilyBench` objects in `test_family_ok_and_target_logic` (`test_template_bench.py:76-88`) — i.e. the *logic* of `meets_target`, never a real timing. The real sub-second numbers live in the static `docs/benchmarks/stage-5-template-families.md` (all 7 families 0.13–0.45 s), which is a committed artifact regenerated by hand, not a CI assertion.

**Why this matters**
Anti-flake is the right call for a hard gate, and the committed doc carries genuine measured evidence, so this is not a lie — but the product's *defining* performance promise is verified by a static markdown file, not by any executable check. A regression that pushed a family to, say, 3 s (a pathological `$fn`, an accidental double-render) would stay under the 5 s gate and pass silently; only a human re-running the bench and eyeballing the doc would catch it.

**Fix path**
Keep the 5 s hard gate as-is. Add a soft, non-gating signal: either a `@pytest.mark.perf` (deselected by default) variant that asserts `report.all_meet_target` on the real run, or a CI step that runs `python -m kimcad.template_bench` and fails if any `Under 1s` column flips to `no`. Documenting the median-vs-ceiling rationale in the test docstring (already partly there) would also make the intentional gap explicit to future readers.

---

### [TEST-004] — Minor — Coverage — Debounce timer cleanup-on-unmount is implemented but untested

**Evidence**
`RightPanel.tsx:90-92` clears a pending debounce on unmount ("so it can't fire after the card is gone"), and `handleSlide` clears any prior timer before scheduling (98). `RightPanel.test.tsx` covers the fire (122), coalesce (141), and resync (158) paths, but no test unmounts the panel with a debounce pending and asserts `onRerender` does **not** fire afterward.

**Why this matters**
A debounce that fires after unmount is a classic "setState on an unmounted component" / stale-post bug. It is low-exposure (the panel unmounts on New Design, which also bumps `renderSeq` server-side discard), so Minor — but it is an explicit guard with no regression test.

**Fix path**
Add a test: render the panel with fake timers, `fireEvent.change` a slider, `cleanup()`/unmount before `advanceTimersByTime`, then advance past 150 ms and assert `onRerender` was not called.

---

### [TEST-005] — Minor — Flakiness — Two concurrency tests are timing-sensitive by construction

**Evidence**
`test_concurrent_rerenders_are_serialized` (`test_webapp.py:1281`) proves serialization by sleeping 0.3 s in the renderer and asserting `a1 <= b0 + 0.001` on recorded intervals (line 1326). `test_concurrent_identical_slices_run_once` (1086) uses `threading.Event` handshakes plus a real socket. These are *good* tests (they catch a removed lock), but they depend on a 0.3 s body comfortably exceeding scheduling jitter and on a 1 ms overlap margin. On a heavily loaded or very slow CI box, GIL/thread-scheduling jitter could in principle make the margin tight.

**Why this matters**
The 0.3 s body is generous and these passed cleanly here, so the risk is theoretical, not observed — hence Minor, not Major. Flagging it so that if either ever flakes in CI, the fix is to widen the body/margin, **not** to add a retry (which would institutionalize flakiness — exactly the anti-pattern the methodology warns about).

**Fix path**
No change needed now. If flake appears: increase the slow-render body to ~0.5 s and/or assert non-overlap via a shared "currently inside render" counter (assert it never exceeds 1) rather than a wall-clock interval margin — a logically exact, jitter-free invariant.

---

### [TEST-006] — Nit — Quality — `test_render_endpoint_rejects_non_template_design` conflates two distinct 404 reasons

**Evidence**
`test_webapp.py:1197` posts `/api/render/<llm-id>` and asserts 404 + "no adjustable parameters". The handler returns that same 404 for *both* an unknown id and an LLM-backed id (`webapp.py:790-793`), because neither is in `template_state`. The test only exercises the LLM-backed branch; an unknown/never-designed id returning the same message is asserted nowhere.

**Why this matters**
Tiny — the behavior is identical and correct. But the message ("This design has no adjustable parameters") is slightly misleading for a genuinely-unknown id, and no test pins the unknown-id case.

**Fix path**
Add a one-line assertion (or parametrize): `POST /api/render/999999` (never designed) → 404. Optional: distinguish the two messages in the handler.

---

### [TEST-007] — Nit — Coverage — KCViewport mesh-reload on `?v=` cache-bust is asserted only indirectly

**Evidence**
The re-render cache-bust depends on `Viewport.tsx:73` keying its load effect on `meshUrl` and the backend appending `?v=<n>` (`webapp.py:826`). `KCViewport.ts` (`loadMesh`) and `Viewport.tsx` have no unit tests (three.js/WebGL is intentionally not run in jsdom — a reasonable scope choice). The api-layer test `designIdFromMeshUrl` does verify the `?v=` query is stripped for id extraction (`api.test.ts:114`), and the backend emits the versioned URL, but that the *viewport actually re-fetches* when only the `?v=` changes is verified by nothing executable.

**Why this matters**
Low — the version suffix changing the `meshUrl` string guarantees React re-runs the effect (it is the sole dep), so the wiring is sound by inspection. Flagged only so the team knows the viewport-reload link in the live-slider chain rests on code inspection, not a test (consistent with the no-browser-E2E posture).

**Fix path**
Optional, when a viewport test harness exists: mount `Viewport`, change `meshUrl` from `/api/mesh/1` to `/api/mesh/1?v=2`, and assert `KCViewport.loadMesh` (spied) is called twice with the distinct URLs.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@pytest.mark.skip` (unconditional) | 0 |
| `@pytest.mark.skipif` (binary-gated, honest) | 4 in scope (`test_templates.py:252`, `test_pipeline_templates.py:168`, `test_template_bench.py:144`, `test_webapp.py:1226/1250`) — all gate on a real `binary_path(...).exists()`, all *ran* here |
| `.only` (left in) | 0 |
| `xfail` | 0 |
| `TODO: add test` / similar | 0 in the Stage 5 surface |
| Empty assertion / `assert True` placeholder | 0 |
| `--retry` / retries normalized | No — no retry config anywhere |

The binary-gated skips are **honest**: each predicate is a real `.exists()` probe and the test body does real work (renders, asserts watertight + envelope) — there is no silent no-op that "passes" when the binary is missing. In this environment both binaries exist, so the skip branch was not taken and the live proofs executed.

## Blind spots by class

- **Re-render-into-invalid safety (server):** a re-render that turns a good part bad → must become non-sliceable/non-sendable. Implemented, untested (TEST-001).
- **Out-of-order async (client):** the `renderSeq` stale-response discard. Implemented, untested (TEST-002).
- **Real-world performance regression:** the `<1 s` promise is doc-evidenced, not gated (TEST-003).
- **Lifecycle teardown (client):** debounce fire-after-unmount (TEST-004).
- **Viewport reload on cache-bust:** wired-by-inspection, no executable check (TEST-007) — part of the deliberate no-browser-E2E boundary.

No blind spots found in: injection/clamping (thorough), no-model enforcement (triple-proven), alias matching incl. plurals and es-plurals and duplicate-alias rejection, analytic bbox vs real render (live gate), slice-cache idempotency/serialization, console-safety of the report markdown.

## Patterns and systemic observations

- **Strong, non-tautological proof culture.** The recurring pattern across this surface is to prove a property by an *independent* derivation rather than by re-asserting the implementation: the determinism check re-emits SCAD by a second path; the no-model guard *raises* rather than counts; the concurrency test detects overlap by wall-clock intervals rather than trusting the lock exists. This is the opposite of the "test the mock" anti-pattern.
- **The two Majors share one root cause:** both safety guarantees that are *transitions into a worse state* (good→gate-fail server-side, new→stale client-side) are untested, while every *happy* transition (good→good, clamp→echo) is covered. The team tested the path the demo walks and under-tested the path an adversarial user (or a slow network) walks. A single focused pass adds both regression tests.
- **Mocking is disciplined.** The webapp tests run a real `ThreadingHTTPServer` over a real socket with a real (or stubbed-renderer) pipeline; the slicer is stubbed only to dodge the multi-minute real slice while the *real* renderer still drives the geometry change (`test_rerender_invalidates_a_cached_slice`). Integration tests actually integrate.

## Appendix: test artifacts reviewed

- Python tests: `tests/test_templates.py`, `tests/test_pipeline_templates.py`, `tests/test_template_bench.py`, `tests/test_webapp.py` (Stage 5 section, lines 1144-1327; plus the gate-safety tests at 51-82), `tests/conftest.py` (shared `FakeProvider` / `box_renderer`).
- Source under test: `src/kimcad/templates.py`, `src/kimcad/template_bench.py`, `src/kimcad/pipeline.py` (`rerender`, `_build_from_template`, `_assemble_result`), `src/kimcad/webapp.py` (`_handle_render`, `_handle_slice`, `_handle_send`, `_handle_design`, `_result_to_payload`, `_evict`).
- Frontend tests: `frontend/src/api.test.ts`, `frontend/src/App.test.tsx`, `frontend/src/components/RightPanel.test.tsx`.
- Frontend source: `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/{RightPanel,Viewport,Workspace}.tsx`, `frontend/src/viewport/KCViewport.ts`.
- Runs observed: Stage 5 Python set **122 passed, 0 skipped** (~30 s); `test_webapp.py` 49 passed (~23 s); frontend Vitest **33 passed** (6 files, ~1.8 s); binary presence confirmed (`tools/openscad/openscad.exe`, `tools/orcaslicer/orca-slicer.exe` both exist); binary-gated live tests confirmed PASSED (not skipped) via `-v`.
- Committed evidence: `docs/benchmarks/stage-5-template-families.md` (real sub-second per-family timings, verdict PASS).
