# Stage 5 — Test Engineer Deep-Dive (backfill 2026-06-05)

**Role:** Senior Test Engineer (independent, skeptical)
**Scope:** Deterministic template engine + live-slider re-render. Backend pytest
(`test_templates.py`, `test_pipeline_templates.py`, `/api/render` block of `test_webapp.py`)
and frontend vitest (`RightPanel` sliders/units/numeric-entry, `api.ts` `postRender`, `App`
re-render lifecycle, `useUnits`).
**Branch:** `stage-0-7-audit-backfill` @ `0aeae99`.

---

## Test-suite shape (one line)

Bottom-heavy and honest: a thick layer of offline contract/unit tests over the template
engine and the HTTP layer, plus a **real-OpenSCAD-backed** band of integration tests for the
re-render safety properties — and, critically, those binary-gated tests are **actually
running** in the supported environment (the OpenSCAD binary is present at
`tools/openscad/openscad.exe`), not silently skipped. The frontend mirrors the contract at the
component level with real fake-timer debounce tests.

## What I ran (read-only)

- `.venv/Scripts/python.exe -m pytest -m "not live" -q -k "template or render or slider or unit or clamp"`
  → **115 passed, 653 deselected, 0 failed, 0 skipped.**
- `pytest tests/test_webapp.py tests/test_pipeline_templates.py tests/test_templates.py -m "not live" -rs`
  → **170 passed, 1 deselected** (the single `@pytest.mark.live` OrcaSlicer web test). No skips.
- `pytest tests/test_webapp.py -k "reshapes or invalidates or stale or concurrent_rerenders" -v`
  → **4 passed** — the real-renderer re-render safety tests are exercised, not skipped.
- `frontend && npx vitest run` → **23 files, 276 tests, all passed.**

Confirmed binary present: `Config.load().binary_path("openscad").exists()` → `True`.

---

## What's working (credit where due)

This is one of the better-tested slices in the repo. Specifically:

1. **The core safety property is tested against real geometry, not a mock.**
   `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (test_webapp.py:1330) proves a
   part that passed → was sliced → re-rendered into a gate-failing shape becomes
   **non-sliceable AND non-sendable**, and the stale G-code 404s. The cache-invalidation
   (`test_rerender_invalidates_a_cached_slice`:1402) and the mid-slice race
   (`test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale`:1432) both run on the
   **real OpenSCAD renderer**, so the geometry-version guard
   (webapp.py:650–656, 1682–1687, 1717–1719, 1831–1839) is verified end to end, not asserted
   against a stub.

2. **"No model call on the deterministic path" is a real, repeatedly-pinned invariant.**
   `provider.openscad_calls == 0` is asserted on every template path
   (test_pipeline_templates.py:48, 103, 157; test_webapp.py:1398) — including the binary-gated
   end-to-end `test_render_endpoint_reshapes_a_template_part_without_the_model`. A regression
   that routed a slider drag back through the LLM would fail loudly.

3. **Clamping is tested at three layers and they agree.** Engine
   (`clamp_values`/`derive_values`, test_templates.py:141–182), the `/api/render` `adjusted_params`
   contract (test_webapp.py:1495–1513), and the frontend `clampToSpec` (RightPanel.test.tsx:507,
   609, 736). NaN/inf rejection (test_templates.py:163) and the od/id degenerate-geometry guard
   (test_templates.py:170) are real edge-case coverage, not happy-path.

4. **The re-render gate reflects CURRENT values, not stale ones** — the exact bug class that
   would silently approve a wall dragged too thin — is pinned by
   `test_rerender_gate_reflects_current_parameter_values` (test_pipeline_templates.py:108) against
   the `rerender` plan-rebuild (pipeline.py:674–681).

5. **Single-shot fail-closed behavior** (no retry, no LLM fallback on a deterministic gate fail
   or render fail) is covered: test_pipeline_templates.py:92 and :149 with explicit render-count
   assertions (`state["n"] == 1`).

6. **Units round-trip is verified to emit mm** even when entered in inches
   (RightPanel.test.tsx:590–668), including the no-op-drift guard (FOUND-001) and a sub-step mm
   edit not being swallowed (ENG-002). `useUnits` has its own conversion/persistence tests.

7. **Concurrency is genuinely tested**, not hand-waved: `test_concurrent_rerenders_are_serialized`
   (test_webapp.py:1547) uses a slow instrumented renderer with a jitter-free "max inside body"
   invariant AND a wall-clock interval check on `render_lock`.

8. **App-level out-of-order race** (a stale re-render response losing to a newer one via the
   `renderSeq` guard) is covered (App.test.tsx:149–168), and the debounce-after-unmount leak is
   pinned (RightPanel.test.tsx:463).

---

## Findings

### TEST-501 — Major — Offline `/api/render` tests use a fixed-size stub renderer that ignores the SCAD; the geometry-change semantics are proven ONLY by the binary-gated band

- **Category:** Mocking / Coverage
- **Evidence:** `box_renderer` (conftest.py:137–159) returns a trimesh box of a **fixed
  `extents`** regardless of the `scad` it's handed. So every *offline* re-render test
  (test_webapp.py:1330 gate-fail-blocks-slice, :1495 adjusted_params, :1547 serialization)
  exercises the locking/version/cache/clamp plumbing but **not** "the new parameter values
  actually changed the mesh." The only tests that prove a slider drag reshapes the geometry are
  the three `_openscad_present()`-gated ones (test_webapp.py:1377, :1401, :1432) plus the
  pipeline-level `test_template_path_end_to_end_with_real_openscad` (test_pipeline_templates.py:168).
- **Why this matters:** On a machine or CI lane **without** the OpenSCAD binary, those gated
  tests skip and the green suite would no longer contain a single assertion that re-rendering at
  new values yields different geometry — a `rerender` that emitted the *old* SCAD (or ignored
  `values`) would still pass every non-gated test. The suite's truthfulness about the feature's
  central promise is contingent on the binary being present. It IS present here (verified), so
  today the coverage is real; the risk is that the *non-gated* layer alone gives a false sense of
  coverage if the binary lane ever drops.
- **Blast radius:**
  - Adjacent: every `box_renderer`-driven test across test_webapp.py and test_pipeline.py shares
    this stub; the same fixed-extent assumption underlies the `_box_renderer((80,60,40))` calls.
  - User-facing: none directly — this is a test-confidence gap, not a product bug.
  - Tests to update: add ONE offline test that asserts the emitted SCAD differs between two
    re-renders (`result.scad` contains `width=120` after a width=120 render vs `width=80`
    initially) — `emit_scad` is deterministic and needs no binary, so this closes the gap without
    OpenSCAD. Mirrors the existing `result.scad == match.scad()` assertion (test_pipeline_templates.py:52).
  - Related: none.
- **Fix path:** Add an offline assertion that the re-render *emit* reflects the new values (SCAD
  string contains the new dimension), so "values flow into geometry" is pinned even when the
  binary lane is unavailable. Optionally mark the binary-gated re-shape tests as a required CI
  lane so they can never silently skip on the release runner.

### TEST-502 — Minor — `/api/render` units contract is tested only in mm; the inch→mm seam is verified frontend-only

- **Category:** Coverage
- **Evidence:** Every `/api/render` backend test posts raw mm `values`
  (test_webapp.py:1355, 1391, 1425, 1447, 1502). The inch→mm conversion lives entirely in the
  frontend (`fromDisplay`, RightPanel.tsx:103–116) and is tested there
  (RightPanel.test.tsx:590, 609). There is no test that an inch-mode edit's *converted* mm value
  survives the backend clamp/gate as a coherent whole — the two halves are each tested in
  isolation but never as one path.
- **Why this matters:** A drift in either the conversion constant or the backend's expectation of
  units would slip through — each side's test would still pass. Low exposure (the contract is
  simple and the frontend always sends mm), hence Minor.
- **Fix path:** Optional — a thin App-level test that an inch numeric edit results in a
  `postRender` call whose mm payload then round-trips through a stub backend. The existing
  `emitted.width` assertions already cover the conversion math; this would only add the seam.

### TEST-503 — Minor — `rerender` "unknown family → render_failed" branch has no direct test

- **Category:** Coverage
- **Evidence:** pipeline.py:666–673 returns `render_failed` when `match_family` returns None for a
  bad `family_name`. No test passes an unknown family to `rerender` / `/api/render`. The HTTP
  layer always supplies the family from `template_state` (webapp.py:1794), so it's not reachable
  from the SPA — but `rerender` is a public method and the branch is a defensive guard.
- **Why this matters:** A defensive error path with no test is the kind that rots into a wrong
  status code or a leaked traceback under refactor. Low exposure (unreachable from the UI), hence
  Minor.
- **Fix path:** One test: `pipeline.rerender(plan, "no_such_family", {...}, tmp)` →
  `status is PipelineStatus.render_failed` and a sane `error`. No binary needed.

### TEST-504 — Nit — `_handle_render` 500-on-unexpected-exception branch is untested

- **Category:** Coverage
- **Evidence:** webapp.py:1800–1802 catches any exception from `pipeline.rerender` and returns a
  500 without leaking a traceback — mirroring the well-tested `/api/design` 500 path
  (test_webapp.py:886, which asserts no `Traceback` leaks). The render endpoint has no equivalent
  "boom → clean 500, no traceback" test.
- **Fix path:** Mirror `test_unexpected_pipeline_error_is_clean_500_no_traceback` for
  `/api/render` (monkeypatch `pipeline.rerender` to raise). Nit because the code is a copy of an
  already-proven pattern.

---

## Shortcut census

Clean. No `.skip` / `.only` / `xit` / `@pytest.mark.skip` / `assert True` placeholders / TODO-test
comments in any Stage 5 test file. The only `skipif` markers are legitimate binary-presence gates
(`_binary_present`, `_openscad_present`, `_trimesh_can_export_3mf`) with honest reasons, and the
single `@pytest.mark.live` marker is the OrcaSlicer web test (correctly excluded by
`-m "not live"`). The conftest geometry-backend probe even **fails the build red on CI** rather
than skipping to a false green (conftest.py:77–78) — good test culture.

## Regression posture

Strong. Findings carry named regression tests with their finding IDs in the docstrings
(ENG-001 stale-slice, RENDER-001 serialization, RENDER-002 current-values gate, QA-001
adjusted_params type, ENG-002 sub-step edit, FOUND-001 inch no-op). This is a tests-with-fixes
culture, not retrofitted coverage.

---

## Summary for the orchestrator

- **Severity counts:** Blocker 0 · Critical 0 · Major 1 · Minor 2 · Nit 1 (total 4).
- **Blockers:** none.
- **Top findings:** TEST-501 (offline tests can't prove geometry actually changes without the
  binary — add an offline emit-diff assertion), TEST-503 (unknown-family branch untested),
  TEST-502 (units seam tested per-side, not end to end).
- **Pattern/culture:** Genuinely good. The load-bearing re-render safety properties (no-model,
  stale-slice invalidation, fail-closed gate, serialization) are each pinned with an explicit
  regression test, and the most important ones run against real OpenSCAD geometry in the
  supported env. The one real gap is a *confidence* gap, not a bug: strip the binary and the
  green suite stops proving that a slider drag reshapes the part — closeable with a single
  binary-free emit-diff test.
