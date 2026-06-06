# Test Engineer Deep-Dive — KimCad Stage 0

**Auditor role:** Senior Test Engineer
**Date:** 2026-05-29 (run 2026-05-30)
**Scope:** `C:\Users\scott\dev\kimcad\tests\` vs `src\kimcad\` (+ `scripts\`)
**Verdict altitude:** Suite run live on this machine, OpenSCAD binary present, so the 8 binary-gated tests executed for real (live-assembled, single module path). Coverage tooling (`coverage.py`) is **not installed**, so all coverage statements below are from reading every test and every source line by hand, not from an instrument.

---

## Reality check — does the suite pass as claimed?

```
./.venv/Scripts/python.exe -m pytest -q
119 passed in 6.31s        (re-run: 6.58s)
```

- **119 passed, 0 skipped, 0 xfailed, 0 errors.** Confirmed with `-rs` (no skip reasons printed) and `-v` on the gated module.
- The claim of "8 binary-gated tests that skip when OpenSCAD isn't fetched" is **accurate**. They are the parametrized `test_module_renders_watertight_with_documented_bbox[...]` cases in `tests/test_library_modules.py:79-106`, guarded by `@pytest.mark.skipif(not _binary_present(), ...)`. The binary resolves to `tools/openscad/openscad.exe` (exists), so all 8 ran and passed — verified by running that module with `-v`: each `[wall_hook]…[drawer_divider]` case reports PASSED, and these are genuine shell-outs to the real renderer (`render_scad` → `subprocess.run`), not monkeypatched.
- `ruff check .` → **All checks passed.**
- No `skip`/`xfail`/`.only`/`TODO`/`FIXME`/`assert True`/`sleep` shortcuts anywhere in `tests/` (grepped). The single `skipif` is the legitimate binary gate above.

So the headline numbers are honest. The findings below are about **what those 119 tests do not exercise**, not about a lying scoreboard.

---

## Test-suite shape (one sentence)

Bottom-heavy and disciplined: a thick band of fast unit/contract tests over every pure function, a thin but **real** integration layer (the pipeline run end-to-end against stub renderers, the web HTTP stack over an ephemeral socket, and 8 live OpenSCAD renders), and **no E2E coverage of the two things a user actually touches at the edges — the CLI `design` happy path and the browser 3D preview — nor of the slicer/G-code path.** The mocking that exists is honest (it stubs the binary/socket boundary, not the logic under test).

---

## What's working (credit where due)

This is a well-tested codebase for Stage 0. Specific good practice, named:

- **The renderer's safety layer is tested for real, not asserted-in-prose.** `tests/test_openscad_runner.py` exercises the sanitizer (foreign `use`/`import` stripping `:97`, path-traversal block `:108`, minkowski block `:114`), the library-`use` injection including the substring false-positive guard (`box(` vs `rounded_box(`, `:77`) and the locally-defined-module shadow guard (`:70`), the missing-semicolon repair with comment preservation (`:19-43`), the 3MF→STL fallback (`:153`), the oversize guard (`:190`), timeout (`:231`), and the relative-out_dir resolution regression (`:201`). These are the §12 threat-model behaviors and they are covered at the behavior level.
- **The pipeline's two safety behaviors are tested as behaviors, not implementation.** Render-retry-then-fail-closed (`test_pipeline.py:160`), gate-retry-fixes-then-fails-closed (`:170`, `:183`), `proceed_anyway` skips the retry (`:195`), and slice-only-on-confirmation (`:206`). The `_resizing_renderer` fixture genuinely simulates the model fixing geometry on the second attempt — that's a real integration assertion, not a mock-of-the-thing-under-test.
- **The web HTTP layer is driven over a real socket.** `test_webapp.py:129` stands up `ThreadingHTTPServer` on an ephemeral port and does real `urllib` GET `/`, POST `/api/design`, GET `/api/mesh/{id}`, and a 404 — so the routing, JSON shaping, and mesh-registry handoff are integration-tested, not just the pure `design_response` mapper.
- **The LLM retry path is covered.** `test_llm_provider.py:143` (retry-then-succeed) and `:167` (exhaust-then-raise) drive a flaky fake client raising real `APIConnectionError`, with `retry_wait_s=0` so the wait loop is exercised without wall-clock cost. The structured-output suppression branch (`:190`) is covered too.
- **Regression tests are tied to specific fixed bugs.** `test_codegen_guard.py` is an explicit guard for commit `c15f347` (the `box()`-as-solid `center`-param bug), asserting the corrective prose survives in the manifest and system prompt. `test_openscad_runner.py:201` documents its regression in the docstring. This is exactly the tests-with-fixes culture the framework asks for.
- **The done-gate prompt set is integrity-guarded.** `test_bench_prompts.py` fails loudly on a dropped case, duplicate id, empty prompt, or a bbox that exceeds the build volume — so the `kimcad bench --min-success-rate 0.8` gate can't be silently mis-scored by a bad YAML edit.
- **The Windows cp1252 glyph crash is regression-tested twice** (`test_cli.py:36`, `test_benchmark.py:85`) — a real post-work crash that's now pinned.
- **The IR normalizer's salvage paths are well-covered** (`test_ir.py:92-147`): unknown feature type → `other`, 2-element position dropped, degenerate `[0,0,60]` bbox dropped, and the "does not mutate input" guarantee asserted.

---

## Findings (severity-ranked)

### TEST-001 — Major — Coverage — The slicer / G-code path has no integration test and is unreachable in the running product

**Evidence:**
- `src/kimcad/slicer.py:66` `slice_model()` is unit-tested in isolation (`test_slicer.py`: command-shape `:16`, non-zero → `SliceFailed` `:40`, timeout `:54`), all with `subprocess.run` monkeypatched.
- But `slice_model` / `SliceSettings` are **never called from anywhere in `src/`** (grep: the only `src` hits are inside `slicer.py` itself). Neither `cli.py` nor `webapp.py` constructs a `SliceSettings`, passes `confirm_print=True`, or injects a real slicer into `Pipeline`. `cli.py:102` and `webapp.py:124` both build `Pipeline(config, printer, material, provider)` with **no `slicer=`**.
- The pipeline's slice branch (`pipeline.py:261`) is therefore only ever reached by `test_pipeline.py:206`, which passes a `fake_slicer` returning the string `"sliced-artifact"`. No test maps a config `orca_machine_profile` → on-disk profile JSON paths, and `slicer.py:15-21` flags that mapping as a "KNOWN UNKNOWN" to resolve against the real binary.

**Why this matters:** G-code generation is the spec's terminal deliverable (§6.9) and the one step that turns "a validated mesh" into "a thing you can print." It is exercised end-to-end by **nothing** — not a test, not the CLI, not the web UI. The unit tests prove the command string is well-formed against a *mocked* subprocess; they cannot catch the failure mode the module's own docstring warns about (the real OrcaSlicer CLI rejecting a profile-name-vs-path mismatch, or the shipped binary lacking a P2S profile). The bug class that slips through: **the entire slice path is broken against the real binary and no test would know.**

**Honest framing:** at Stage 0 this is partly **by design** — the web UI's "Prepare print (G-code)" button is deliberately `disabled` (`web/index.html:93`) and labeled "wired in the next slice," and the spec gates G-code behind explicit confirmation that no surface yet offers. So this is not "a shipped critical path with no test"; it's "a unit-tested module not yet wired, with the real-binary integration explicitly deferred." That keeps it at **Major**, not Critical. But it should be logged as the single largest live-assembled gap, and the deferral should be explicit in the release notes, not implicit in the absence of a test.

**Blast radius:**
- Adjacent code: `pipeline.py:261-262` (the only consumer), `config.py:27/103` (`orca_machine_profile`, currently read but never used to build `SliceSettings`).
- Shared state: the config `printers.*.orca_machine_profile` and a future `process`/`filament` profile mapping — none of which has a resolver yet.
- User-facing: when the "Prepare print" button is enabled, this path goes live with zero integration coverage. That's the moment the KNOWN UNKNOWN bites.
- Migration: none yet.
- Tests to update: none break; a new live-binary slice test (gated like the OpenSCAD one) is the fix.
- Related findings: TEST-002 (CLI never wires it either).

**Fix path:** Before the slicer is enabled in any surface, add a binary-gated integration test (mirror `test_library_modules.py:79`'s `skipif`) that resolves a real config profile to disk paths and slices a known-good mesh against the shipped OrcaSlicer, asserting a non-empty `.gcode.3mf` is produced. Until then, document the deferral explicitly.

---

### TEST-002 — Major — Coverage — The CLI `design` and `web` command bodies have no happy-path test; only argument parsing and error exits are covered

**Evidence:**
- `test_cli.py` covers: `_normalize_argv` (`:6`, `:10`), parser wiring (`:16`), `bench` missing-file → exit 2 (`:23`), `design` missing-API-key → exit 2 (`:29`), and the UTF-8 helper (`:36`, `:47`).
- It does **not** cover `_cmd_design` (`cli.py:105`) on a successful run, nor any of its four distinct exit codes for real pipeline outcomes: `3` clarification (`:111`), `4` render_failed (`:114`), `5` gate_failed (`:118`), `0` completed (`:121`). `_cmd_web` (`cli.py:152`) and `_cmd_bench`'s success/summary-persist path (`:137-149`) are likewise untested.
- The pipeline itself is well-tested, but the **CLI's mapping from `PipelineResult.status` → exit code → printed message** is pure glue that nothing exercises. A bug there (wrong exit code, printing `result.report` when `report is None` on a render_failed path, etc.) ships clean.

**Why this matters:** the CLI is the Phase-1 user surface (spec §5). Exit codes are a contract — scripts and the bench gate depend on them. The bug class that slips through: a refactor that swaps two status branches, or a `None`-deref on `result.report.to_text()` for a status that legitimately has no report, would pass all 119 tests. `_cmd_design` calls `result.report.to_text()` unconditionally at `:117` after only ruling out clarification/render_failed — a future status with `report=None` would `AttributeError` here, untested.

**Blast radius:**
- Adjacent code: `cli.py:105-156` (all three command bodies), `_build_pipeline:95`.
- Shared state: the exit-code contract consumed by `kimcad bench --min-success-rate` and any wrapping script.
- User-facing: every CLI invocation; the messages a user reads on clarification/failure are unverified.
- Tests to update: none break.
- Related findings: TEST-001 (the CLI also never wires the slicer).

**Fix path:** Add tests that call `main(["design", ...])` with an injected fake pipeline (or monkeypatch `_build_pipeline`) and assert the exit code + captured stdout for each of the four statuses, plus one `kimcad web --demo`-style smoke that asserts `serve` is invoked with the parsed args (it can be monkeypatched to avoid binding a port).

---

### TEST-003 — Major — Coverage — The browser 3D preview (the web UI's headline feature) is completely untested

**Evidence:**
- `web/index.html` is 251 lines including the three.js STL-preview JavaScript. The only assertion touching it is `test_webapp.py:121` (`(WEB_DIR / "index.html").exists()`) and `:142` (the served HTML contains `<title>KimCad`). The served mesh bytes are asserted non-empty (`:156`) but never parsed or rendered.
- There is no DOM test, no headless-browser test, no assertion that the fetched STL actually loads into the viewer, that the dims table renders, or that an error payload surfaces a message. The JS path from `/api/design` JSON → on-screen result is entirely unverified.

**Why this matters:** this is the classic Static ≠ Runtime / Grep-passing ≠ UI-correct blind spot. "The HTML file exists and contains a title" tests nothing the user sees. The 3D preview is the reason the web UI exists (`webapp.py:4-6`); a broken three.js init, a wrong mesh MIME (`model/stl` at `webapp.py:172` — is that what three.js's loader expects?), or a JS exception on the dims table would render a blank or broken page while every Python test stays green. The bug class: **any client-side regression in the one feature the web UI is for.**

**Blast radius:**
- Adjacent code: `web/index.html` (the JS), `webapp.py:155-172` (the routes feeding it, esp. the `model/stl` content-type).
- User-facing: the entire web experience past the JSON layer.
- Migration: none.
- Tests to update: none break; this is net-new coverage (likely Playwright/headless or at minimum a JS unit test of the render function).
- Related findings: QA role should drive the running web UI and confirm the preview actually paints — this gap is best closed by QA's live run plus a headless smoke.

**Fix path:** Add a headless-browser smoke (Playwright) that POSTs a demo prompt and asserts the canvas paints / the dims table populates, OR — lighter — extract the JS render logic and unit-test it under jsdom. At minimum, QA must verify the preview live before tag (note this as a cross-role item).

---

### TEST-004 — Minor — Coverage — `render_scad`'s real-binary path is exercised only for library modules, not for model-style or adversarial OpenSCAD

**Evidence:**
- The only live (non-monkeypatched) `render_scad` calls are `test_library_modules.py:81`, which render the 8 curated library-module snippets. Every other `render_scad` test (`test_openscad_runner.py:139-237`) monkeypatches `subprocess.run`.
- So the real binary is proven to render **known-good, hand-written library calls**. It is never run against: a deliberately broken SCAD (real parser error → real non-zero exit), a real 3MF-write to confirm the default `output_format="3mf"` actually produces a 3MF on this binary (the fallback logic at `openscad_runner.py:318` keys off real stderr fingerprints that are only tested against synthetic stderr), or a genuinely oversize render.

**Why this matters:** the 3MF→STL fallback (`_NO_3MF_RE`, `openscad_runner.py:44`) matches stderr substrings; whether the *shipped* OpenSCAD actually emits those exact strings when it lacks lib3mf is unverified against the real binary. If the shipped binary writes 3MF fine, the fallback is dead-but-safe; if it can't and emits a string the regex misses, the fallback never fires and renders fail closed in production while tests pass. Low likelihood (the binary is pinned), hence Minor, but it's the kind of binary-reality gap that the live OpenSCAD presence *could* close cheaply.

**Blast radius:**
- Adjacent code: `openscad_runner.py:302-327` (`_render_once` fallback), `:44` (`_NO_3MF_RE`).
- User-facing: a silent render-failure on a binary that can't write 3MF.
- Fix path: add one binary-gated test that renders a trivial `cube(5);` to real 3MF and asserts the file exists + format, and (if feasible) one asserting a real parser-error path raises `RenderFailed`. Cheap given the binary is present.

---

### TEST-005 — Minor — Quality — The mesh-repair path in `validate_mesh` is never tested with an actually-broken mesh

**Evidence:**
- `validation.py:47-58` is the repair branch (`if not mesh.is_watertight: … fix_normals/fix_winding/fill_holes/fix_inversion …`). Every validation test (`test_geometry.py:37-52`) feeds a **watertight** `trimesh.creation.box` (or two of them), so `is_watertight` is True and the entire repair block is skipped.
- The gate's `mesh.repaired`/`not_watertight` findings *are* tested (`test_geometry.py:95`, `:103`) — but via a hand-constructed `MeshReport` with `repaired=True` set by hand, **not** by running a leaky mesh through `validate_mesh`. So the producer of those flags is uncovered.

**Why this matters:** the repair logic (hole-filling, winding/normal/inversion fixes) and the `repairs` provenance strings ("filled holes (was N open boundary loops)") are exactly the code that runs when the model emits imperfect geometry — the common case for a small local model. None of it is exercised. The bug class: a repair step that silently does nothing, mis-counts boundary loops, or produces a wrong `repairs` message would never be caught; the gate would then warn/fail on data the validator mis-generated.

**Blast radius:**
- Adjacent code: `validation.py:47-66`, `_open_boundary_count:81`, and the gate's `_check_integrity` (`printability.py:100`) which consumes `repaired`/`repairs`/`errors`.
- Fix path: add a test that builds a non-watertight mesh (e.g. a box with a face deleted) and runs the **real** `validate_mesh`, asserting `repaired` is True (or `errors` is populated if irreparable) and the bbox/volume are still computed.

---

### TEST-006 — Minor — Coverage — `auto_orient` is tested for the heuristic-success case but not the no-stable-pose fallback

**Evidence:**
- `orientation.py:35-43` `_best_pose` has a `try/except` and a `len(transforms) > 0` branch with a fallback to `np.eye(4), 1.0, "no stable pose found; left as-is"`. `test_geometry.py:117` tests only the success path (a box that reorients to rest on its 40×40 face, `stability > 0`).
- The fallback (degenerate/empty `compute_stable_poses` → identity transform, stability 1.0) is uncovered, as is the `except Exception` guard.

**Why this matters:** orientation feeds the print report and the user-visible "Orientation: … (stability X.XX)" line. A degenerate mesh that yields no stable poses should still produce a valid (identity) orientation and a sane report, not crash. Low exposure (most real meshes have stable poses), hence Minor.

**Fix path:** add a test with a mesh whose `compute_stable_poses` returns empty (or monkeypatch it to raise) and assert `auto_orient` returns the identity-transform fallback with stability 1.0 and the documented description.

---

### TEST-007 — Nit — Quality — Two parallel `FakeProvider`/`_box_renderer` fixtures are duplicated between `test_pipeline.py` and `test_webapp.py`

**Evidence:** `test_pipeline.py:21-55` and `test_webapp.py:22-48` define near-identical `FakeProvider`, `_box_renderer`, `_plan`, `_pipeline` helpers (the pipeline copy additionally tracks call counts; the webapp copy is a trimmed clone). The `BAMBU`/`PLA` constants are re-declared in four test files.

**Why this matters:** fixture drift — the two `_box_renderer`s can diverge silently (they already differ in return shape: one returns `render`, the other `(render, state)`), so a behavior verified in one file isn't guaranteed in the other. Pure hygiene; no bug ships from it today.

**Fix path:** lift the shared fakes and the `BAMBU`/`PLA` constants into a `conftest.py` or a `tests/_fakes.py` and import. Optional.

---

## Things that are NOT unit-test gaps (noted honestly)

- **Prompt quality / model behavior** (does the system prompt actually make a 12B local model emit correct OpenSCAD; does the one-question clarification feel right; does the gate-feedback retry actually converge on a real model) **can only be measured by the live benchmark** (`kimcad bench`, the §4.2 done-gate). The *harness* and *scoring* are unit-tested (`test_benchmark.py`), and the *prompt-set integrity* is guarded (`test_bench_prompts.py`), but the prompts' effect on a real model is not a unit-test concern and should not be counted as a coverage hole. It is, however, the thing the team must run live before believing the product works — flag it for the release gate, not the test suite.
- **The `# pragma: no cover` lines** in `validation.py:64/85/92` and `cli.py:181` are on genuinely defensive/degenerate branches; their exclusion is reasonable.

---

## Summary for the orchestrator

- **Real result:** 119 passed, 0 skipped, 0 xfail, ~6.3s. ruff clean. The 8 binary-gated tests ran live (OpenSCAD present) and are genuine real-binary renders. The pass/skip claim is honest.
- **Suite shape:** bottom-heavy, disciplined unit/contract layer; thin-but-real integration (pipeline end-to-end on stubs, web over a real socket, 8 live renders); no E2E on the CLI happy path, the browser preview, or the slicer.
- **Findings:** 0 Blocker, 0 Critical, 3 Major, 3 Minor, 1 Nit.
- **Top findings:** TEST-001 (slicer/G-code path: unit-tested but unwired and untested against the real binary — by-design-deferred, log it), TEST-002 (CLI command bodies / exit-code contract untested), TEST-003 (browser 3D preview entirely untested).
- **Culture note (for exec report):** this is a genuinely well-tested Stage-0 codebase with real tests-with-fixes regression discipline (`test_codegen_guard.py`, the cp1252 guards, the relative-out_dir regression). The blind spots are all at the *edges* — the surfaces a human or browser touches (CLI glue, the three.js preview) and the not-yet-wired terminal step (slicing). No Blocker or Critical.
- **Cross-role hand-off:** TEST-003 should pair with the QA role's live web-UI run; TEST-001's real-binary slice gap should pair with QA's live-assembled verification before the slicer is ever enabled.
