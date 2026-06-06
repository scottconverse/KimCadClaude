# Stage 8 audit-team — remediation (2026-06-06)

The 5-role audit-team rolled up **0 Blocker / 0 Critical / 7 Major / 16 Minor / 11 Nit** on the
`stage-8-cadquery` branch. The security model was confirmed holding by every role (each tried to
break it; the production path is closed). Every finding below is FIXED or ACCEPTED-with-rationale.
Re-audit closure is recorded in `REAUDIT-eng.md` (engineering/security/test) and
`REAUDIT-uxdocs.md` (UI/UX + docs) — both returned SHIP with all findings CLOSED.

> ⚠ Process note: during the parallel run, a role agent's mutation-test left an `if False and …`
> edit in the real working tree (`cadquery_runner.py`, the string-subscript dunder check); the
> Principal Engineer caught and reverted it, and the tree was verified clean (`git diff` empty)
> before remediation. Future stage gates should isolate mutation-testing agents in worktrees.

## Major (7)

- **ENG-002 — FIXED.** The worker subprocess now runs in the isolated `out_dir` with a
  **secret-scrubbed environment** (`_worker_env()` drops API-key/token/secret vars), mirroring the
  OpenSCAD runner. The discovery probe scrubs its env too. (`cadquery_runner.py`)
- **ENG-001 — FIXED (the actionable parts) + ACCEPTED (full OS sandbox, deferred to Stage 11).**
  The Major's concrete concerns are addressed: (a) blast radius cut by ENG-002 (no secrets in env,
  isolated cwd); (b) a **through-`render_cadquery` escape-class regression canary**
  (`test_render_cadquery_blocks_escape_class_end_to_end`, parametrized over the os-pivot,
  `__globals__` chain, dunder-subscript, frame-attr, and `str.format` payloads) so a single-branch
  sanitizer regression fails loudly at the real entry point, not only in a unit branch; (c) a
  **release-gate backstop** (TEST-001). Full OS-level process confinement (network-off, job
  object/restricted token) is genuinely heavier + platform-specific and disproportionate for a
  local-first beta whose trust model is "you run generated code on your own machine" (same as
  OpenSCAD); it is now an explicit **Stage 11** backlog item (docs updated), with the env-scrub +
  isolated-cwd as the in-tree mitigation until then.
- **UX-001 — FIXED.** The Printability card now shows a neutral **"Engine: CadQuery / OpenSCAD"**
  provenance chip (`RightPanel.tsx` + `.kc-engine-badge`), so the part's geometry engine is stated,
  not inferred from the STEP link. Rendered-verified ("Engine: OpenSCAD" on the demo part).
- **UX-002 — FIXED.** The no-STEP formats note no longer dead-ends: it states KimCad **picks the
  engine to fit each part** (shown on the printability check), names the precision CAD engine, and
  explains STEP is available for CadQuery parts — no phantom control implied.
- **DOC-001 — FIXED.** The worker `__import__` is now described accurately everywhere
  (`docs/cadquery-backend.md`, `cadquery_worker.py` docstring, CHANGELOG, ARCHITECTURE): it returns
  the facade for `cadquery`, real `math`, and **raises `ImportError` for any other import**.
- **TEST-001 — FIXED.** `scripts/ci.sh` gained a CadQuery release-gate backstop mirroring the
  OrcaSlicer one: a warning always, and a **hard fail under `KIMCAD_RELEASE=1`** when no CadQuery
  interpreter is discoverable (so the worker-sandbox RCE live tests can't silently skip on a
  release run).
- **TEST-002 — FIXED.** Added worker failure-direction tests: `RenderTimeout`
  (stubbed `subprocess.run`), `_read_worker_result` crash-synthesis on a missing result file, and
  live `test_worker_withholds_dangerous_builtins_beyond_open` (eval/exec/getattr).

## Minor (16)

- **ENG-003 — FIXED.** The string-subscript dunder check now also catches **bytes** constant keys,
  with an in-code note on the worker↔sanitizer coupling (the worker withholds the string-building
  primitives that would make a computed key usable). Regression test added.
- **ENG-005 — FIXED.** The interpreter probe prints a **sentinel-delimited** path and parses
  between the sentinels, so a noisy interpreter (startup banner) is no longer silently skipped.
  Non-live tests added (OSError swallowed, bogus path skipped, banner-noise parsed).
- **ENG-006 — FIXED.** The output-size guard now covers the **STEP** too, not just the STL.
- **UX-003 — FIXED.** `.kc-download-step` now has a distinct, slightly-elevated treatment (a
  leading edit glyph + bordered pill) so the editable-CAD export reads as different from the STL.
- **UX-004 — FIXED.** Format download links are now ≥40px touch targets (padding + min-height) with
  an 8px inter-link gap. Rendered-verified (STL link height 40px).
- **UX-005 — FIXED.** The STEP-present note leads with what's downloadable now (STL/STEP) and gates
  the `.3mf` behind "once you slice."
- **DOC-002/DOC-003 — FIXED.** The "Enabling it" section now restates the no-3.14-wheels reason and
  notes a 3.11–3.13 KimCad install can host CadQuery **in place** (no second interpreter needed).
- **DOC-004 — FIXED.** "every cadquery submodule is stripped" scoped to "every **top-level**
  submodule" across the docs.
- **TEST-003 — FIXED.** `FallbackProvider.generate_cadquery` now has behavioral delegation tests
  (success-skips-alt + fallback-on-error).
- **TEST-004 — FIXED.** Multi-backend `proceed_anyway` (accepts the gate-failed primary, no
  fallback) and the WARN-primary path (`_backend_succeeded` accepts WARN) are now tested.
- **TEST-005 — FIXED.** The provider-contract test is now behavioral: it binds each method's
  signature to the contract argument shape (catches a wrong-arity stub), not just presence.
- **TEST-006 — FIXED.** `find_cadquery_interpreter` internals have non-live tests (OSError
  swallowed → None; bogus path skipped; banner-noise parsed via the sentinel).
- **QA-001 / QA-002 — ADDRESSED (= ENG-001 cluster).** The worker-layer-alone `__globals__`
  residual is closed in production by the sanitizer (verified by every role); the cheap in-tree
  hardenings (env-scrub, isolated cwd, regression canary, release gate) landed; the durable
  OS-level confinement is the same Stage-11 backlog item as ENG-001.
- **ENG-004 — ACCEPTED (documented).** The ~3s CadQuery cold-start is off the common path (fallback
  only); documented in `_default_cadquery_renderer` rather than trading away fresh-process isolation
  for a warm worker.

## Nit (11)

- **ENG-007 — FIXED.** A comment marks the worker's `os`/`sys` imports as harness-only (never
  exposed to the executed script).
- **ENG-008 — ACCEPTED.** `backend`/`step_path` across RenderResult/PrintReport/PipelineResult is a
  deliberate DTO-flattening pattern (consistent with the rest of the report).
- **ENG-009 — FIXED (by ENG-006).** The "output size guard" now genuinely covers STL + STEP, so the
  docstring is accurate.
- **UX-006 — FIXED.** "the CadQuery engine" → "the precision CAD engine (CadQuery)".
- **UX-007 / DOC-006 — ACCEPTED (house style).** Format names are upper-cased (`.STL`/`.STEP`) in
  the UI for consistency; the on-disk file + download name use lowercase `.step`. Distinction is
  intentional and documented.
- **DOC-005 — FIXED.** The bench's measured numbers are marked as-measured (not a version
  requirement) and the sorted-dims tolerance scope is stated.
- **DOC-007 — VERIFIED.** The cited test files (`test_pipeline_backends.py`,
  `test_cadquery_bench.py`) exist and cover the described behavior (Test lane confirmed).
- **TEST-007 — FIXED.** The redundant cache-poke in `test_no_fallback_when_cadquery_unavailable`
  is now commented as belt-and-suspenders independent of the fixture.
- **TEST-008 — ACCEPTED (documented).** The bench's 0.5mm sorted-dims tolerance is justified
  (tessellation + orientation-invariance) and now documented; the runner test is the tight per-axis
  check.
- **QA-003 — ACCEPTED (documented).** OCCT native stderr may carry diagnostics in
  `RenderResult.stderr`; it never corrupts the result (that's on a dedicated file).

## Re-audit follow-ups (2 new, both FIXED)

- **UX-N1 (Minor, contrast) — FIXED.** The UX-003 STEP pill's tinted fill dropped the terracotta
  link text to 4.35:1 (just under AA). Removed the fill — the border + ✎ glyph still distinguish
  the STEP link, and the text sits on the card surface at 4.66:1 (AA pass).
- **REAUDIT-N1 (Nit) — FIXED.** The env-scrub now matches secret-bearing NAME *segments*
  (underscore-delimited) instead of substrings, so a look-alike like `TOKENIZER_PATH` /
  `PASSWORDLESS_MODE` is kept while `OPENROUTER_API_KEY` / `SOME_TOKEN` / `AWS_SECRET_ACCESS_KEY`
  are stripped. Regression test extended.

Both re-audit lanes returned SHIP with all original findings CLOSED; these two are the only new
items and are now resolved.
