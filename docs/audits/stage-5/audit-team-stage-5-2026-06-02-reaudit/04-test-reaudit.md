# Stage 5 Re-Audit — Test Engineer (lens 04)

Date: 2026-06-02 · Posture: balanced · Bar: 0/0/0/0/0
Scope: uncommitted remediation diff (`git diff -- tests frontend` + guarded `src/`).
Method: read each new test, traced it to the guarded code, confirmed it would FAIL on regression
(not merely pass), then ran the suites.

## Per-finding closure

- **TEST-001 (Major — gate-fail re-render non-sliceable/sendable): CLOSED.**
  `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (tests/test_webapp.py). The stub
  renderer is fixed 80x60x40; a `width=120` re-render makes the template's expected X=120 vs the
  rendered 80 → `dim.mismatch` → gate FAIL. Drives a real good→fail transition: pre-render slice
  succeeds, post-render gcode 404s, slice returns `sliced:False reason==gate_failed`, send is not
  `sent:True`. Would catch removal of the re-stamp at webapp.py:830 (old "pass" would persist and
  let the slice through) and the gcode eviction at webapp.py:833. Non-tautological.

- **TEST-002 (Major — renderSeq stale discard): CLOSED.**
  `discards a stale (out-of-order) re-render response` (App.test.tsx). Two manually-held resolvers;
  newer (B) resolved first, stale (A) last, each in its own `act()` — fully deterministic, no
  timers. Asserts mesh-url == `?v=new`. Without the seq guard at App.tsx:67 A's late resolve would
  overwrite to `?v=stale` and the assertion fails. Genuine.

- **TEST-003 (<1 s never asserted): CLOSED-WITH-NEW-ISSUE.**
  The gate now asserts `report.all_meet_target` on measured render times (test_template_bench.py:166),
  which is a real assertion (`meets_target` = `rerender_s <= 1.0` on a live OpenSCAD render). The gap
  is closed — but the chosen assertion is timing-sensitive and flaked in this re-audit. See NEW-001.

- **TEST-004 (debounce unmount): CLOSED.**
  `does not fire the debounced re-render after the panel unmounts` (RightPanel.test.tsx). Uses fake
  timers, calls `unmount()` BEFORE `advanceTimersByTime(150)`, asserts `onRerender` not called.
  Guards the cleanup effect at RightPanel.tsx:93-95; remove it and the pending setTimeout fires
  post-unmount. Correct.

- **TEST-005 (concurrency timing-sensitive): CLOSED.**
  `test_concurrent_rerenders_are_serialized` now asserts `state["max"] == 1` via an inside-counter
  bracketed in try/finally around the 0.3 s sleep. This is logically exact (the count of renders
  simultaneously inside the body), not a widened margin — it catches a regression even if the wall
  clock happens not to overlap. The wall-clock check is kept belt-and-suspenders. Good model for
  how a concurrency invariant should be asserted.

- **TEST-006 (404 conflation): CLOSED.**
  `test_render_endpoint_unknown_id_is_design_not_found`. Asserts 404 + "not found" AND that
  "no adjustable parameters" is absent — pinning the unknown-id branch (webapp.py:804) distinctly
  from the LLM-backed branch (webapp.py:806). Correct.

- **TEST-007 (viewport reload cache-bust): ACCEPTED.**
  Correct call. jsdom has no WebGL, so a real viewport-reload E2E isn't runnable here; the `?v=`
  cache-buster is produced server-side (webapp.py) and the api-layer `designIdFromMeshUrl` strip is
  exercised by the existing api tests. No fabricated browser test was added — the honest boundary.

- **QA-003 regression: CLOSED.**
  `test_slice_failed_message_is_user_legible` (test_slicer.py) pins the signed exit code
  (4294967246 → -50) and the empty-stderr plain-English hint ("too large or too solid"), and
  confirms a real stderr is preserved. Matches slicer.py:78-85 exactly.

## Copy-change verification (all EXACT against shipped strings)
- "Re-rendering…" ✓ (RightPanel.tsx:114) · error "didn't render / last version is still here /
  Nudge a slider to try again" ✓ (137-138) · "generated directly" ✓ (158). Tests match.

## NEW findings

- **NEW-001 (Minor) — test_template_bench.py:166: the `all_meet_target` assertion is
  flaky-by-construction.** TEST-003's new gate asserts a hard 1.0 s wall-clock budget on a real
  OpenSCAD render. In this re-audit it FAILED when the bench ran in a loaded batch:
  `wall_hook` measured **rerender_s = 1.037 s** (> RERENDER_TARGET_S = 1.0). It passes standalone
  (~0.93 s idle) but `wall_hook`, `tube`, and `cable_clip` all sit at 0.74–1.04 s — `wall_hook`
  straddles the exact threshold, so the result depends on machine load. The remediation's own
  comment ("~0.13–0.45 s, 2–7x under 1 s") is measured on `snap_box`/`box` only and does not hold
  for the slowest families. This is the very anti-pattern TEST-005 was careful to avoid (it used an
  exact in-body invariant, not a margin). The hard automated gate is already `RERENDER_CEILING_S`
  (5 s); the <1 s headline is the right thing to *measure and report*, not to assert as a CI gate.
  **Exact fix:** replace the hard assertion with a recorded/reported check that doesn't fail CI on
  the boundary, e.g.

  ```python
  # Record the <1 s interactive headline; don't gate CI on a load-sensitive wall clock
  # (the hard gate is RERENDER_CEILING_S above). Surface slow families as a warning.
  slow = [(f.name, round(f.rerender_s, 3)) for f in report.families if not f.meets_target]
  if slow:
      warnings.warn(f"families over the <1 s interactive target (non-gating): {slow}")
  ```

  Alternatively keep the assertion but bump `RERENDER_TARGET_S` to a load-robust value (e.g. 1.5 s)
  with a comment that <1 s is the *reported* idle figure — but a warning is cleaner because the spec
  headline is genuinely sub-second on idle hardware and you don't want to weaken the documented
  target. Either way the assertion as written will intermittently red the suite on loaded CI.

No other new issues: no other new test is flaky, tautological, or over-loose; stub-based assertions
(TEST-001/006) are wired to catch the specific regression they name.

## Observed counts
- pytest full suite: **490 passed** (112 s). Affected files (webapp+slicer+bench): 100 passed.
- The bench target test passes standalone (3/3) but failed 1× in a loaded batch — see NEW-001.
- vitest: **36 passed** (6 files), all six remediation tests present and green.

## Rollup
NOT 0/0/0/0/0. **0 Critical / 0 Major / 0 Minor… +1 Minor (NEW-001)** → **0/0/1/0/0.**
7 of 8 gaps are genuinely and durably closed; TEST-003 closes the *gap* but introduces a
flaky-by-construction CI gate. Fix NEW-001 (warn instead of assert, or raise the target margin)
and the bar is clean.
