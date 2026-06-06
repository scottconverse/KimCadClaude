# Test Engineer Deep-Dive — KimCad Backend Foundation (Stages 0–3)

Backfill audit on the current code. Branch `stage-0-7-audit-backfill`, repo `C:\Users\scott\dev\kimcad`.
Role reference: `audit-team/references/test-engineer.md`. Severity per `severity-framework.md`.
AUDIT-ONLY — no files modified.

## Test run (read-only)

```
.venv/Scripts/python.exe -m pytest -m "not live" -q
778 passed, 4 deselected in 127.94s
```

The 4 deselected are the `@pytest.mark.live` real-OrcaSlicer slices in `test_slicer.py` (correctly gated off the default run). No failures, no errors, no warnings surfaced.

## Test-suite shape

Bottom-and-middle heavy: a large unit layer over the deterministic pipeline (sanitize, gate, IR, hardening, slicer parse), a genuinely strong **integration** layer for the seams that matter (real `trimesh` geometry through `validate_mesh`/`run_gate`/`auto_orient`; real in-process mock HTTP servers — `mock_octoprint`, `mock_moonraker`, `mock_prusalink` — for every connector), and a thin but real **live** layer behind the `live` marker for the actual OrcaSlicer binary. This is a healthy pyramid: the slicer/connector seams are exercised against real protocol behavior, not just mocked stubs, and the one place mocks are unavoidable (the LLM, the real printer) is isolated behind an injected `provider`/`runner`/`connector`.

## What's working (credited specifically)

- **The gate is the core safety property and it is directly, not just incidentally, tested.** `test_geometry.py` and `test_capability.py` drive `run_gate` through every check and every level: `dim.mismatch` FAIL, `volume.exceeds` FAIL, `mesh.not_watertight` FAIL, `wall.thin` WARN, `mesh.repaired` WARN, `shells.multiple` WARN, plus the blank-field guards (`volume.unchecked`, nozzle-unknown skip) that prove a missing build volume warns-not-crashes and re-enables the fit check once filled (`test_capability.py:101-113`).
- **The failure-direction safety invariant is pinned.** `test_pipeline.py:360 test_gate_fail_with_confirm_does_not_slice` proves a gate-FAILED part is NOT sliced even when `confirm_print=True`, and its companion (`:381`) proves `proceed_anyway` is the only override. This is the single most important property of "gated export" and it is tested in both directions.
- **The confirm gate is exact-True, not truthy.** `test_printer_connector.py:43` rejects `confirm="yes"` — a real shortcut someone would otherwise take.
- **`prove_gcode_3mf` is adversarially tested:** motionless G-code rejected, G10/G28/G92 not mistaken for motion (the `\b` boundary case, `:420`), arc-only (G2/G3) accepted, non-zip rejected, missing member rejected, oversize/too-many-members rejected. The non-motion 3MF the scope asked about IS rejected.
- **Profile resolution refuses cross-vendor fallback honestly** (`test_slicer.py:233, 265, 527`): an unmapped material raises "not available," and the same name under two vendors raises "ambiguous" rather than silently slicing the wrong machine's profile — the exact Elegoo-class bug family, locked down.
- **Connectors have real-server integration + secret hygiene:** every connector redacts the API key from errors (`test_*_connector.py::test_api_key_never_appears_in_error`), distinguishes auth-rejected from offline, handles garbage-200/5xx, percent-encodes filenames, rejects multi-plate archives, and the LoopbackConnector's documented lock is proven under a 12-thread barrier race (`test_printer_connector.py:167`).
- **Regression discipline is visible:** findings carry IDs in test docstrings (QA-001, ENG-001/002/008, TEST-001..011, FIND-001..006, BENCH-001) — fixes arrived with regression tests, which is the culture you want.
- **No shortcuts:** zero `xfail`, zero unjustified `skip`, zero `assert True`/`.only`/commented-out assertions, zero TODO/FIXME in tests. Every `skipif` is a legitimate environment guard (binary/profiles/manifold3d absent) or the `live` marker.

---

## Findings

### TEST-001 (Major | Coverage | stage 0) — The dimensional tolerance BOUNDARY (`DIM_TOL_MM = 0.5`) is never tested at its edge

**Evidence:** `printability.py:33` sets the gate's headline bar at a flat 0.5 mm with a documented "accuracy over leniency" decision. `dim_tolerance()` (`printability.py:37`) has **no direct test**. The gate's dim tests use gross gaps only: `test_geometry.py:68` is 150 vs 200 (50 mm), `test_geometry.py:62` is an exact match. No test exercises a delta just under 0.5 mm (must PASS) or just over (must FAIL). `grep` for the tolerance edge across `tests/` finds only the benchmark grader (49.8/50.2), which is a different code path (`grade_correct_dimensions`), not `run_gate`.

**Why this matters:** the 0.5 mm line is the literal definition of "did we build the right size." A regression that flips `>` to `>=`, swaps the flat floor for a percentage, or widens the constant would let a wrong-sized part pass the gate, and the suite would stay green — the boundary is exactly where this safety property lives and exactly what is untested. Off-by-tolerance is the most likely future mutation of this function.

**Blast radius:**
- Adjacent code: `_check_dimensions` (`printability.py:128`), `dim_tolerance` (`:37`), and the retry-feedback path that shares `DIM_TOL_MM`.
- Tests to update: none break; this is additive.
- Related findings: none — this is the highest-value single missing test in the stage.

**Fix path:** add a focused boundary test in `test_geometry.py`: expected `[50,50,50]`, render `(50.4,50,50)` → PASS (within 0.5), render `(50.6,50,50)` → `dim.mismatch` FAIL; plus a direct `dim_tolerance(200.0) == 0.5` assertion to pin the "no relative term" decision.

### TEST-002 (Major | Coverage | stage 2) — `ensure_sendable` (the send-side proof+confirm gate) lacks a "gate-failed part" send test at the connector seam

**Evidence:** the pipeline-level safety (gate-failed → not sliced) is tested (`test_pipeline.py:360`). At the connector seam, `ensure_sendable`/`send` are tested for: no-confirm, truthy-confirm, missing file, non-zip, no-gcode-member, motionless. That is the *file-shape* gate. There is no test that the send path refuses a file that came from a **gate-FAILED** run — because `ensure_sendable` only re-proves the G-code, it has no knowledge of the upstream gate verdict. So the only thing standing between a gate-failed part and the printer is the pipeline not handing it a gcode file.

**Why this matters:** "gated export" promises a failed part never reaches hardware. That invariant is currently enforced only at the pipeline layer; the connector trusts its caller. If any future caller (web upload of a pre-existing `.gcode.3mf`, a CLI "send this file" path) routes around the pipeline, a motion-bearing but dimensionally-wrong slice would send. No test documents whether that is in-scope or accepted risk.

**Blast radius:**
- Adjacent code: `ensure_sendable` (`printer_connector.py`), every connector `send`, the web/CLI send entry points.
- User-facing: a wrong part could print if a non-pipeline send path exists.
- Related findings: TEST-001 (same gate), pipeline `test_gate_fail_with_confirm_does_not_slice`.

**Fix path:** confirm (in code review) whether any send path bypasses the pipeline; if so, add a test that the send entry point refuses a part whose run did not pass the gate, or document explicitly that `ensure_sendable` is a shape gate only and the pipeline owns the verdict gate.

### TEST-003 (Minor | Coverage | stage 3) — `test_config.py` is thin on printer/material coverage breadth

**Evidence:** `test_config.py` (66 lines) tests the default printer, `min_wall`, four densities, LLM-backend defaults, and binary path. It does NOT iterate every shipped printer/material to assert each loads with a sane build volume / nozzle / required fields. The cross-product breadth that catches a malformed config entry only exists behind the `skipif(profiles)` slicer test (`test_slicer.py:283`), which is skipped when profiles aren't fetched.

**Why this matters:** a typo in `config/*.toml` for a non-default printer (e.g. Elegoo build volume, A1 nozzle) would not be caught by any always-run test. Stage 3's claim is "printer/material/profile coverage," and the always-on config tests only assert the default.

**Fix path:** add a parametrized `test_config.py` test iterating `cfg.printers()` and `cfg.materials()` asserting each loads with build_volume/nozzle/density present and positive — fast, no binary needed.

### TEST-004 (Minor | Coverage | stage 1) — `_check_wall_thickness` PASS branch and the gate-failed-never-sliced *unit* of the slicer are covered, but the "gate failed → slicer never invoked" assertion lives only in the pipeline

**Evidence:** `test_geometry.py:82` covers `wall.thin` WARN; the `wall.ok` PASS branch (`printability.py:213`) is only hit incidentally. Minor — the PASS branch is low-risk. Noting for completeness; not worth blocking.

**Fix path:** one assertion that a comfortably-thick wall yields `wall.ok` PASS.

---

## Culture / pattern observations (for the exec report)

- This suite does the hard thing well: it spins up **real mock HTTP servers** per connector and drives the actual `urllib` request path, rather than mocking `_request` everywhere. Where `_request` is monkeypatched, it's deliberately for the garbage-body/5xx branches that a live mock can't easily produce — a defensible split, not over-mocking.
- The gate, the proof, and the confirm gate — the three safety seams of Stages 0–2 — are each tested in both pass and fail directions, with the failure direction (the dangerous one) explicitly pinned. That is the right instinct.
- The only systemic gap is **boundary coverage of numeric thresholds** (TEST-001 is the load-bearing instance; the tolerance constant and the wall-minimum are asserted by gross examples, never at the edge). Everything else is breadth-of-config (TEST-003), not depth-of-safety.
- The scope brief named per-module test files (`test_printability.py`, `test_validation.py`, `test_orientation.py`) that do not exist; that coverage is **consolidated** into `test_geometry.py` + `test_capability.py`. Coverage is present — the file names in the brief are stale, not the tests.

## Severity counts

Blocker 0 · Critical 0 · Major 2 · Minor 2 · Nit 0 — Total 4.
