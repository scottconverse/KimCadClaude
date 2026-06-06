# 01 — Engineering Deep-Dive (Principal Engineer)

**Project:** KimCad — plain-English → OpenSCAD → STL/3MF, with a Printability Gate and OrcaSlicer integration.
**Audit point:** Stage 0, pre-merge / pre-tag.
**Reviewer lens:** Principal Engineer — architecture, correctness, security, error handling, concurrency, dependency hygiene, data provenance.
**Date:** 2026-05-29.

Scope reviewed (read in full): `src/kimcad/` (openscad_runner, webapp, pipeline, llm_provider, config, ir, validation, printability, orientation, slicer, cli, benchmark), `src/kimcad/web/index.html`, `src/kimcad/prompts/*.md`, `library/*.scad` + `library/manifest.yaml`, `config/default.yaml`, `scripts/fetch_tools.py`, `scripts/ollama_watchdog.py`, `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`, `README.md`, `HANDOFF.md`, and the test suite (`tests/test_openscad_runner.py`, `tests/test_webapp.py`, `tests/test_codegen_guard.py`, plus the file list of all 15 test modules).

**What I could not check:** I did not run OpenSCAD or OrcaSlicer against live LLM output (no model server running in this session), and I did not run the full 119-test suite — I read the tests rather than executing them. The sanitizer bypasses below were reproduced directly against the real `sanitize_scad` function (Python, `PYTHONPATH=src`); those are verified, not inferred. Severity for the slicer is partial: `slice_model` was read but is not yet wired into a live profile path (acknowledged in the module docstring), so its runtime behavior is unverified.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 2 |
| Major | 5 |
| Minor | 5 |
| Nit | 3 |
| **Total** | **15** |

No Blocker. The two Criticals are both in the security sandbox (`openscad_runner.py`) and both have a concrete fix path that does not require an architecture change.

---

## What's working

Credit where it's due — this is a well-structured codebase for an early-phase project, and several decisions are better than typical:

- **The injectable-seam architecture is genuinely good.** The LLM provider, renderer, and slicer are all injected into `Pipeline` (`pipeline.py:171-189`), so the whole orchestration — including the render-retry loop and the Gate escape hatch — is unit-testable offline against real Trimesh geometry with no binary, no socket, no model. `webapp.py` reuses the *same* wiring (`build_web_pipeline`) rather than duplicating it. `design_response` is a pure function over a `PipelineResult`, so the entire web response shape is tested without an HTTP server. This is the single biggest reason the test count (112 functions / "119 tests") is meaningful rather than theater.
- **Defense-in-depth intent is real.** The threat model is taken seriously: generated OpenSCAD is treated as untrusted, `minkowski()` is a hard block (DoS prevention), file-I/O is stripped, `OPENSCADPATH` is scoped to the project root while the binary runs in an isolated temp dir, a render timeout and a 200 MB output guard both exist (`openscad_runner.py:252, 287`), and G-code is gated behind explicit `confirm_print` (`pipeline.py:261`). The *intent* is correct; two implementation gaps (ENG-001/002) are what drop it to Critical rather than Blocker.
- **Fail-closed retry loop.** `_build_geometry` (`pipeline.py:279-342`) feeds render errors and fixable gate failures back to the model within a bounded attempt budget, then fails closed rather than looping forever. The retry feedback is high-quality: `_axis_breakdown` spells out all three axes at once so a two-wrong-axis part converges in one shot instead of burning the budget one axis at a time.
- **The deterministic-spine philosophy is the right call.** Generating parametric CSG (closed manifold geometry by construction) instead of neural meshes means output is dimensionally meaningful and the Gate can make hard assertions. The Design-Plan IR (`ir.py`) as a validated intermediate before any geometry is the correct abstraction.
- **Input validation at the LLM boundary is thoughtful.** `normalize_plan_dict` (`ir.py:101`) salvages almost-valid model JSON (out-of-enum feature types, degenerate bounding boxes) before strict pydantic validation, without mutating the input — a clean "be liberal in what you accept" boundary that doesn't crash the whole part on a recoverable slip.
- **The web layer is correctly XSS-safe.** Findings rendered into the DOM go through `escapeHtml` / `textContent` (`index.html:176, 239`); the one place `innerHTML` is built from data (`renderDims`, `index.html:165`) uses numeric `toFixed` values, not strings. The server never reflects the prompt into HTML. Tracebacks are caught and never leaked to the browser (`webapp.py:192`).
- **Secret hygiene is clean.** No hardcoded keys; API keys come from env vars named in config; `config/local.yaml`, `.env`, and `*.key` are gitignored; `tools/` and `output/` are gitignored and confirmed not tracked.
- **Checksum-pinned binary fetch.** `fetch_tools.py` pins the OrcaSlicer download by SHA-256 and aborts on mismatch (`fetch_tools.py:125-141`), with a documented, well-reasoned pin to 2.4.0-alpha (upstream CLI crash on GPU-less boxes). This is more supply-chain discipline than most projects ship with.

---

## Findings

### ENG-001 (Critical) — Security: SCAD sanitizer is line-oriented and misses multi-line `import()` / `minkowski()`

**Category:** Security

**Evidence:** `openscad_runner.py:39-40, 204-223`. The sanitizer iterates `code.splitlines()` and matches each line independently against `_IMPORT_RE = re.compile(r"\b(?:import|surface)\s*\(")` and `_MINKOWSKI_RE = re.compile(r"\bminkowski\s*\(")`. Both regexes require the `(` to sit on the **same physical line** as the keyword. OpenSCAD's lexer treats any whitespace — including newlines — as a token separator, so `import` and its `(` may legally be on different lines.

Reproduced against the real function (`PYTHONPATH=src`):

```python
sanitize_scad('import\n(\n"/etc/passwd"\n);')
#   safe? True   removed: []        -> "/etc/passwd" survives in the rendered code
sanitize_scad('minkowski\n()\n{cube(1);sphere(1);}')
#   blocked? False                  -> minkowski() is NOT blocked
```

Both pass straight through the sanitizer untouched and would be handed to the binary.

**Why this matters:** The sanitizer is the *primary* trust boundary for untrusted, LLM-generated OpenSCAD — the module docstring (`openscad_runner.py:1-20`) states file-I/O is stripped and `minkowski()` is a hard block, and the rest of the system relies on that guarantee. The `import()` gap means a model (or, more importantly, a prompt-injected request — the prompt is fully attacker-controlled in the web UI) can get the renderer to read an arbitrary local file. `surface()` reads a file too. The `minkowski()` gap defeats the documented DoS guard: `minkowski()` at high `$fn` can pin a CPU for hours (the stated reason it's banned), and the 30 s render timeout (`config/default.yaml:76`) caps a single render but the threat model treats minkowski as un-renderable-by-policy, not merely slow. Exposure is realistic: the model emits multi-line, formatter-friendly code, and the codegen prompt does not forbid newlines before parentheses. A model that wraps a long `import(...)` call across lines — or an attacker who crafts a prompt to induce it — bypasses the gate today.

**Practical impact ceiling:** information disclosure (read a local file into a mesh the user downloads) and CPU DoS. Not RCE — OpenSCAD has no shell-out — which is why this is Critical, not Blocker. But it is a reachable bypass of the system's named security control, so it must be fixed before Stage 0.

**Fix path:** Normalize whitespace before matching, or match across the whole source rather than per line. Concretely: run the import/surface/minkowski detection against the comment-stripped *full* source with `re.DOTALL`-tolerant patterns (e.g. `re.compile(r"\b(?:import|surface|minkowski)\b\s*\(", re.DOTALL)` applied to the joined source after stripping `//` and `/* */`), and reject (block) rather than line-delete when a match spans lines so you don't silently corrupt geometry (see ENG-002). Better still, treat any *un-approved* `use`/`include`/`import`/`surface`/`minkowski` token as a *block* (re-prompt) rather than a silent strip — the current "strip and continue" posture is what makes partial matching dangerous. Add regression tests for newline-separated tokens and for token-with-trailing-comment forms.

**Blast radius:**
- Adjacent code: `inject_library_uses` and `ensure_terminated` (`openscad_runner.py:134, 168`) also parse SCAD with single-line-oriented regex and run *before* `sanitize_scad` (`render_scad` ordering, lines 260-262). Confirm they don't re-introduce a stripped construct or move text across the boundary. `_USE_INCLUDE_RE` (line 41) is single-line too and has the same class of gap for `use`/`include`.
- Shared state: the sanitizer's output is the exact bytes written to disk and rendered (`openscad_runner.py:272`). Any change to what "safe" means changes what reaches the binary for every code path (CLI, web, bench).
- User-facing: legitimate renders are unaffected; the change closes a bypass with no visible change to valid parts. `SanitizeResult.removed` is surfaced in the print report (`pipeline.py:375`), so a shift from "strip" to "block" changes the report copy for the rare malicious case only.
- Migration: none — additive enforcement.
- Tests to update: `tests/test_openscad_runner.py` asserts the current single-line behavior (e.g. `test_sanitize_strips_foreign_use_and_import`, line 97; `test_sanitize_blocks_minkowski`, line 114). Add multi-line cases; expect 3-5 new/changed assertions. The existing tests give a false sense of coverage here precisely because they only feed single-line inputs — call that out in the Test deep-dive.
- Related findings: ENG-002 (collateral line deletion), ENG-006 (no test exercises multi-line/adversarial SCAD).

---

### ENG-002 (Critical) — Correctness/Security: sanitizer deletes an entire source line when stripping inline file-I/O, silently destroying valid geometry

**Category:** Correctness (with a security dimension)

**Evidence:** `openscad_runner.py:212-219`. When a line matches the foreign-`use`/`import`/`surface` patterns, the whole line is replaced with a single comment (`out_lines.append(f"// [kimcad] removed file I/O: {line.strip()}")`). It does not excise only the offending call.

Reproduced:

```python
sanitize_scad('a = 1; import("/etc/passwd"); cube(5);  // inline')
#   removed: ['line 1: import/surface file I/O']
#   but a=1, cube(5), AND the comment are ALL gone — the whole line became a comment
```

**Why this matters:** Two distinct harms from one root cause. (1) **Correctness/data loss in normal operation:** OpenSCAD output from a small model is frequently dense — multiple statements per line are common. If any of those statements happens to trip the file-I/O regex (including false positives — e.g. a user variable literally named `import_offset` would be caught by `\bimport\s*\(`? no — but a module *call* on a shared line absolutely is), every *other* statement on that line is silently deleted. The result is a part that renders to wrong geometry with no error, which then fails the dimensional gate for a reason that has nothing to do with the model's actual mistake — burning retry budget and confusing the feedback loop. This is the exact "renders but is silently wrong" failure class the codegen prompt (rule 12, `system_openscad.md:34`) was written to prevent, reintroduced by the sanitizer itself. (2) **Security-adjacent:** combined with ENG-001, the "strip the line" posture is the wrong model — a single-line `import(...); <real code>` strips both, but a multi-line `import(...)` strips neither.

**Fix path:** Stop doing line-granular deletion. Two clean options: (a) when an unapproved file-I/O construct is found, **block** (raise `BlockedCodeError` / add to `blocked`) and re-prompt — consistent with how `minkowski()` is already handled, and it removes the "partial line surgery" problem entirely; or (b) if stripping must stay, parse and remove only the matched call expression, not the line. Option (a) is simpler and safer and matches the existing minkowski precedent — recommend it. It also aligns with the orchestrator, which already knows how to re-prompt on `BlockedCodeError` (`pipeline.py:318`).

**Blast radius:**
- Adjacent code: shares root with ENG-001; fix them together. `render_scad` (line 264) already raises `BlockedCodeError` when `sanitized.blocked` is non-empty, so promoting strips to blocks is a one-line change in `sanitize_scad` plus the existing raise path — no new plumbing.
- Shared state: changes `SanitizeResult.removed` vs `.blocked` semantics; `pipeline.py:375` reads `.removed` for the report and `pipeline.py:318` reacts to `BlockedCodeError`. Both already exist.
- User-facing: legitimate parts that today silently lose geometry will instead get a clean re-prompt; strictly an improvement.
- Migration: none.
- Tests to update: `test_sanitize_strips_foreign_use_and_import` (line 97) asserts strip-and-keep-safe; it would flip to block. 2-3 assertions.
- Related findings: ENG-001 (same module, same trust boundary), ENG-006 (test gap).

---

### ENG-003 (Major) — Data provenance: README install step pulls the wrong model (`gemma3:12b`), which config explicitly calls "too big/slow for the target"

**Category:** Data / Documentation-as-code

**Evidence:** `README.md:66` instructs `ollama pull gemma3:12b`. The active backend in `config/default.yaml:29` is `model_name: gemma4:e4b`, and the inline comment at `config/default.yaml:31` says "gemma3:12b is too big/slow for the target." `HANDOFF.md` (resume step 1) also references `gemma3:12b`. So the documented setup path pulls a model the config does not use and explicitly warns against, while never pulling the model the tool actually calls (`gemma4:e4b`).

**Why this matters:** This is a data-provenance bug in the most literal sense from the methodology: the value the *user* ends up running against is not the value the *code* reads. A new user follows the README, pulls `gemma3:12b` (a multi-GB download), then runs `kimcad`, which calls `gemma4:e4b` via the config — Ollama returns a model-not-found error, or (if the user also has gemma3 aliased) runs the slow/large model the team measured as unfit for the 32 GB / 780M-iGPU target. Either way the documented first-run experience is broken or degraded. Given the done-gate result (8/10) was measured on `gemma4:e4b`, a user on `gemma3:12b` will not reproduce it. This is the install-doc-doesn't-work pattern that the severity framework calls Critical for a *core* flow; I'm rating it Major because there's an obvious workaround (read the config) and the binary fetch path is correct — but it's a strong Major and should be fixed in the same pass as ENG-001/002.

**Fix path:** Change `README.md:66` to `ollama pull gemma4:e4b` and update `HANDOFF.md` step 1 likewise. Consider adding a startup preflight in `LLMProvider` (or `cli.main`) that calls Ollama's `/api/tags` and emits a plain-English "model `gemma4:e4b` not found — run `ollama pull gemma4:e4b`" instead of surfacing a raw API error; this closes the provenance gap permanently rather than relying on doc/config staying in sync.

**Blast radius:**
- Adjacent code: none in `src/` — this is config↔doc drift. A preflight check would touch `llm_provider.py` `_build_client` / `_complete`.
- Shared state: `config/default.yaml` `llm.backends.local.model_name` is the single source of truth; docs must mirror it. Same drift risk exists for the OrcaSlicer/OpenSCAD version pins (README narrates 2.4.0-alpha — that one is currently consistent).
- User-facing: directly affects every first-run user and reproducibility of the 8/10 done-gate number.
- Migration: none.
- Tests to update: none exist for doc/config consistency — a cheap test that asserts the README's `ollama pull` line matches `config` `model_name` would prevent regression (flag to Test deep-dive).
- Related findings: none structural; standalone provenance fix.

---

### ENG-004 (Major) — Concurrency/Resource: web mesh registry grows unbounded and serves whole files from memory; no eviction, no body-size cap on `/api/design`

**Category:** Performance / Concurrency

**Evidence:** `webapp.py:136, 188-199, 164-172`. `registry: dict[int, Path]` is populated on every successful design (`registry[rid] = mesh_path`) and **never** evicted or capped. Each entry's mesh stays on disk under `output/web/<rid>/` indefinitely. `_serve_mesh` does `self._send(200, mesh_path.read_bytes(), ...)` — the entire mesh is read into memory per request. The POST handler reads `length = int(self.headers.get("Content-Length") or 0)` and then `self.rfile.read(length)` (`webapp.py:178-180`) with **no upper bound** on `length`.

**Why this matters:** This is a long-running local server (`serve_forever`). On the target 32 GB box this is not acute, but three issues compound: (1) the registry and the on-disk `output/web/` tree grow without limit for the life of the process — a session that designs many parts accumulates both dict entries and mesh files forever; (2) `read_bytes()` of a mesh up to the 200 MB render guard, multiplied by `ThreadingHTTPServer` concurrency, is a memory-amplification path; (3) an unbounded `Content-Length` read lets any client (the server runs the pipeline for anyone who can reach it, per README:104) send a huge body and force a large allocation before the prompt is even validated. The README explicitly warns not to expose the server publicly, which correctly scopes the exposure to "localhost / trusted LAN" — that's why this is Major, not Critical. But "it's local" is a deployment assumption, not a code guarantee, and `--host` can bind it anywhere (`cli.py:64`).

**Fix path:** (a) Cap the request body: reject `Content-Length` above a sane limit (e.g. 64 KB — a prompt is text) with a 413 before reading. (b) Bound the registry with an LRU/`OrderedDict` of fixed size (e.g. last 50), and `unlink` or let old run dirs be cleaned; or stream the mesh with a file handle / `shutil.copyfileobj` to `self.wfile` instead of `read_bytes()` so a large mesh isn't fully buffered. (c) Optionally add a per-process cap on concurrent renders (a `Semaphore`) since each render is CPU-bound and `ThreadingHTTPServer` will happily spawn unbounded worker threads.

**Blast radius:**
- Adjacent code: `make_handler` closure state (`registry`, `counter`, `lock`); the lock already exists and is used correctly for `counter` and `registry` writes, so adding an LRU is low-risk. The CLI design path writes to a fixed `output/` dir (`cli.py:56`) with a fixed `part` basename — same unbounded-accumulation concern on disk, different surface (single-user, less acute).
- Shared state: `output/web/` directory tree; `registry` dict; thread pool implied by `ThreadingHTTPServer`.
- User-facing: no change to a normal short session; long sessions stop leaking. A body cap returns a clean 413 instead of OOM risk.
- Migration: none.
- Tests to update: `test_webapp.py` exercises the happy HTTP path (line 129) but not body-size limits, registry growth, or concurrency. Add a 413 test and a registry-bound test.
- Related findings: ENG-006 (no adversarial HTTP tests).

---

### ENG-005 (Major) — Correctness: `validate_mesh` mutates the caller's mesh in place during "repair," and the mesh is reused for orientation/export

**Category:** Correctness

**Evidence:** `validation.py:40-78`. `validate_mesh(mesh)` calls `mesh.process(...)`, `trimesh.repair.fix_normals(mesh)`, `fix_winding`, `mesh.fill_holes()`, `fix_inversion(mesh)` — all in place on the passed object — then returns the *same* object. In `pipeline.py:328-330` the flow is `mesh = load_mesh(...)`, `mesh, mesh_report = validate_mesh(mesh)`, then later `auto_orient(mesh)` (`pipeline.py:239`) and `oriented.export(...)`. So the exported/oriented geometry is the repaired-in-place mesh, and `mesh_report.bounding_box_mm` (which drives the **dimensional gate**, `printability.py:128`) is measured from `mesh.extents` *after* `fill_holes` may have altered it.

**Why this matters:** Two concerns. (1) **Provenance of the gated dimension:** the headline gate assertion (rendered bbox vs plan envelope) is the product's core promise. If `fill_holes`/`process` changes the mesh's extents (e.g. by merging or dropping degenerate faces), the gate is asserting on post-repair geometry, not on what OpenSCAD actually produced. That may be correct (you want to gate the thing you'll print), but it's undocumented and the function's contract ("conservatively repair") doesn't make clear the bbox is measured post-repair. A reviewer tracing "where does the dimension the user sees come from" lands on a mutated object. (2) **In-place mutation as a latent bug:** `validate_mesh` returns the same object it received, so any caller that still holds the pre-validation reference (today none do, but the seam invites it) sees it change under them. The contract should be explicit: copy-and-return, or document "mutates and returns the same mesh; the input is consumed."

**Why Major not Critical:** I did not observe a concrete wrong-dimension case caused by this — on watertight parts the repair branch is skipped entirely (`validation.py:47`), so the common path is unaffected. The risk is on the repair path, which by definition involves a defective mesh. It's a defensible-in-code-review correctness/clarity issue, not a confirmed data-loss bug.

**Fix path:** Make the mutation explicit and intentional: either operate on `mesh.copy()` inside `validate_mesh` and return the repaired copy (clearer contract, slightly more memory), or keep in-place but rename/document the function to state it consumes its input and that the reported bbox is the post-repair envelope. Recommend the latter is at minimum documented and the bbox-is-post-repair semantics are stated in `MeshReport` and surfaced in the report copy, since printing the repaired geometry is the correct behavior — the gap is clarity, not logic.

**Blast radius:**
- Adjacent code: `pipeline._build_geometry` (line 328), `auto_orient` (`orientation.py:24`, which already `.copy()`s — good), `_build_report` (`pipeline.py:349`) reads `mesh_report.bounding_box_mm`.
- Shared state: `MeshReport.bounding_box_mm` feeds both `_check_dimensions` and `_check_build_volume` (`printability.py:128, 166`) and the per-axis UI table (`webapp.py:42-65`). A change in when the bbox is measured shifts all of those consistently.
- User-facing: the dims table and gate verdict are derived from this; behavior wouldn't change if you keep measuring post-repair (recommended), only the documented contract.
- Migration: none.
- Tests to update: `test_validation` / geometry tests (present per file list) likely assert on watertight inputs; add a repair-path test that asserts the returned mesh is the intended one and the bbox semantics.
- Related findings: ENG-007 (silent `except Exception` in the same module).

---

### ENG-006 (Major) — Test gap: the security sanitizer has no adversarial / multi-line coverage, so ENG-001/002 ship green

**Category:** Hygiene / Testability (engineering view of a test gap)

**Evidence:** `tests/test_openscad_runner.py` exercises the sanitizer only with single-line inputs: `test_sanitize_strips_foreign_use_and_import` (line 97), `test_sanitize_blocks_path_traversal_use` (line 108), `test_sanitize_blocks_minkowski` (line 114). There is no test for `import`/`minkowski` split across lines, no test for inline file-I/O sharing a line with valid geometry, and no test for `use < library/x >` with internal whitespace. The suite therefore reports full green while the primary trust boundary has the ENG-001/002 holes.

**Why this matters:** The test suite is the project's main quality signal (no hosted CI yet; pre-push hook runs the same checks). A security control that is only tested on the inputs it already handles gives false confidence — the audit found the gaps by feeding the function adversarial input directly, which the suite never does. For a system whose explicit design premise is "the generated code is untrusted," the sanitizer deserves a dedicated adversarial test class.

**Fix path:** Add a `TestSanitizerAdversarial` class with: newline-separated `import (`/`minkowski (`; mixed-statement lines; whitespace inside `use < ... >`; comment-obfuscated tokens (`/* */`); and a property-style check that no `removed`/`blocked` path ever leaves an `import(`/`surface(`/`minkowski(` token live in the output. Pair this with the ENG-001/002 fix so the tests drive the fix.

**Blast radius:**
- Adjacent code: none — additive tests.
- User-facing: none.
- Migration: none.
- Tests to update: additive; will (correctly) fail until ENG-001/002 are fixed.
- Related findings: ENG-001, ENG-002 (root cause), ENG-004 (no adversarial HTTP tests either — same testing-altitude gap).

---

### ENG-007 (Minor) — Hygiene: broad `except Exception` swallows real errors in mesh stats

**Category:** Hygiene / Correctness

**Evidence:** `validation.py:63-66, 84-86, 90-93` (`volume`, `_open_boundary_count`, `_body_count`) and `orientation.py:36-39` (`_best_pose`) all catch bare `Exception` and substitute a default (0.0 volume, 1 body, identity pose). `benchmark.py:176` and `webapp.py` artifact-dump also swallow broadly (those are defensible "never fail the run on a diagnostic write"). The mesh-stat catches are riskier: a `volume could not be computed` is appended to `errors` but a body-count or pose failure is silent.

**Why this matters:** A degenerate mesh that throws inside `body_count` is reported as `n_bodies=1` (a clean single solid) when it may be many shells — masking exactly the `shells.multiple` WARN the gate exists to raise (`printability.py:207`). The volume case is handled (it records an error); the body/pose cases are not. These are `# pragma: no cover` so they're untested by design.

**Fix path:** Narrow the catches to the specific Trimesh/numpy exceptions expected, and when a stat genuinely can't be computed, append to `MeshReport.errors` (as the volume path already does) so the gate can downgrade confidence rather than silently passing. Pose-failure already degrades gracefully to identity, which is fine, but log it.

**Blast radius:** Adjacent: `printability._check_shells` consumes `n_bodies`. Low risk; behavior only changes on degenerate meshes. Tests: add a degenerate-mesh fixture.

---

### ENG-008 (Minor) — Dependency hygiene: `scipy` and `networkx` are declared direct deps but never imported in `src/`

**Category:** Dependencies

**Evidence:** `pyproject.toml:13-22` lists `scipy>=1.13` and `networkx>=3.3` as direct dependencies. A search of `src/` (`grep -rln "import scipy|import networkx|from scipy|from networkx"`) finds **no** direct import. They are transitive requirements of `trimesh` (used by `compute_stable_poses` / graph ops under the hood).

**Why this matters:** Declaring transitive deps as direct ones is misleading (it says "we use these directly") and pins versions the project doesn't actually control the usage of, increasing the surface for version conflicts and CVE noise without giving the project any real say. It's not a correctness bug — they're installed either way via trimesh — so Minor.

**Fix path:** Either remove `scipy`/`networkx` from `[project.dependencies]` and let them come in transitively via `trimesh` (cleanest — trimesh declares the versions it needs), or, if you want to pin them for reproducibility, move them to a comment-annotated "trimesh-extras we pin" block or use `trimesh[easy]`/the relevant extra so intent is explicit. Verify trimesh actually pulls them at the versions you need first.

**Blast radius:** Build/CI only; no runtime change if removed (trimesh still installs them). Confirm by `pip install -e .` in a clean venv and running the geometry tests. Tests: the existing geometry/orientation tests cover the trimesh paths that need these.

---

### ENG-009 (Minor) — Correctness/Hygiene: `import os` inside `_run`, re-imported per render call

**Category:** Hygiene

**Evidence:** `openscad_runner.py:226-233`. `_run` does `import os` inside the function body on every invocation. It works (import is cached) but is unidiomatic and hides a module-level dependency.

**Why this matters:** Pure hygiene — module-level `import os` is clearer and the repeated in-function import is the kind of thing a linter config could catch. No functional impact.

**Fix path:** Move `import os` to the top of `openscad_runner.py` with the other stdlib imports.

**Blast radius:** None.

---

### ENG-010 (Minor) — Web: `/api/mesh/<id>` returns `Content-Type: model/stl` even when the served file is a `.3mf`

**Category:** Correctness

**Evidence:** `webapp.py:172` always sends `"model/stl"`. The pipeline's default output format is `3mf` (`config/default.yaml:50`), and `mesh_path` is whatever the renderer produced (`.3mf` or fallback `.stl`). The frontend's three.js loader is an `STLLoader` (`index.html:105, 202`), and `pipeline.py:240-241` always exports an `oriented.stl` for the preview — so today the served mesh path is the oriented STL and the content-type happens to be correct. But `design_response` returns `result.mesh_path` (`webapp.py:86`), and `PipelineResult.mesh_path` is set to the `.oriented.stl` (`pipeline.py:240`), so it's consistent *for now* by coincidence of that wiring.

**Why this matters:** Low impact today (the served file is in fact an STL), but it's a latent provenance mismatch: the content-type is hardcoded rather than derived from the file, so the day someone serves the `.3mf` directly (a reasonable future change, since 3MF is the canonical output) the header will be wrong and the loader will silently fail. Worth fixing while it's cheap.

**Fix path:** Derive the content-type from `mesh_path.suffix` (`.stl` → `model/stl`, `.3mf` → `model/3mf` / `application/vnd.ms-package.3dmanufacturing-3dmodelfile+xml`). One line.

**Blast radius:** `index.html` loader expects STL; if you ever serve 3MF you also need a 3MF loader. Note in the UI deep-dive.

---

### ENG-011 (Nit) — `default.yaml` `server.port: 8080` is dead config; the web server defaults to 8765

**Category:** Hygiene

**Evidence:** `config/default.yaml:80-83` defines `server: {host: 127.0.0.1, port: 8080}`. The actual web server defaults come from CLI args (`cli.py:64-65`, host `127.0.0.1`, port `8765`) and `webapp.serve` (`webapp.py:204-211`, port `8765`). The config `server` block is never read by any code I found.

**Fix path:** Either wire `serve`/CLI to read `config.raw["server"]` as the default, or delete the dead `server` block. The port mismatch (8080 vs 8765) is a tell that it drifted. Recommend wiring it (single source of truth) over deleting, so the documented localhost-only binding lives in config.

**Blast radius:** Config only.

---

### ENG-012 (Nit) — `library/bracket.scad` / `mounts.scad` use relative `use <fasteners.scad>;`, relying on `OPENSCADPATH` resolution semantics

**Category:** Hygiene / Robustness

**Evidence:** `library/bracket.scad:11` and `library/mounts.scad:9` contain `use <fasteners.scad>;` (bare filename, no `library/` prefix). This resolves only because the binary runs with `OPENSCADPATH` pointing at the project root and OpenSCAD also searches the including file's own directory. The sanitizer's `_approved_library_path` would *reject* `use <fasteners.scad>` if a model emitted it (it requires the `library/` prefix), but these are trusted library files, not model output, so they bypass the sanitizer — fine, but inconsistent with the `library/`-prefixed convention the prompt and sanitizer enforce everywhere else.

**Fix path:** Make library cross-references explicit and consistent — `use <library/fasteners.scad>;` — so the resolution doesn't depend on CWD/OPENSCADPATH subtleties and matches the one convention the rest of the system enforces. Verify the render still resolves after the change.

**Blast radius:** Library rendering only; covered by `test_library_modules.py`. Re-run that after the change.

---

### ENG-013 (Nit) — `validate_mesh` repair path is hard to follow; `_open_boundary_count` formula is a heuristic

**Category:** Hygiene

**Evidence:** `validation.py:81-86`. `_open_boundary_count` returns `len(mesh.edges_unique) - len(mesh.face_adjacency_edges)` as an "open boundary loop" count, which is an edge-count proxy, not a loop count, despite the repair message saying "open boundary loops" (`validation.py:53`). It's a cosmetic mismatch between the number's meaning and its label.

**Fix path:** Either compute actual boundary loops (trimesh exposes outline/boundary helpers) or relabel the message as "open boundary edges" to match what's measured.

**Blast radius:** Report copy only.

---

## Cross-cutting themes for the executive summary

1. **The sanitizer is the project's keystone security control and it has two reachable gaps (ENG-001, ENG-002) plus no adversarial tests (ENG-006).** These three share a root cause — line-oriented parsing of a whitespace-insensitive grammar with a "strip the line" posture. One coordinated fix (match the comment-stripped full source; *block* rather than strip; add adversarial tests) closes all three. This is the highest-leverage fix in the engineering scope and the one thing I'd insist on before tagging Stage 0.
2. **Doc/config provenance drift (ENG-003) undermines reproducibility of the headline done-gate number.** The 8/10 was measured on `gemma4:e4b`; the README pulls `gemma3:12b`. Cheap to fix, high embarrassment cost if a reviewer or new user hits it first. A consistency test would prevent recurrence.
3. **The injectable-seam architecture is a real asset — lean into it.** The same property that makes the pipeline testable offline (ENG "what's working") is what lets the sanitizer and HTTP body-cap fixes land with tight, fast unit tests rather than integration runs. The fixes above are all small because the architecture is sound.

No Blocker. Two Criticals, both in one file, both with a shared, concrete fix. The project is close — this is a tightening pass, not a rebuild.
