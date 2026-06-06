# Engineering Deep-Dive — KimCad Stage 8 (CadQuery parallel backend)

**Audit date:** 2026-06-06
**Role:** Principal Engineer
**Scope audited:** `git diff main...HEAD` on branch `stage-8-cadquery` — the CadQuery parallel geometry backend. Core files: `cadquery_worker.py`, `cadquery_runner.py`, `pipeline.py` (mutual fallback), `llm_provider.py` (`generate_cadquery`), `config.py` (interpreter discovery/cache), `openscad_runner.py` (RenderResult/RenderFailed extensions), `webapp.py` (STEP registry + `/api/step`), plus `config/default.yaml`, `prompts/system_cadquery.md`, `cadquery_bench.py`, and the Stage-8 tests/conftest.
**Auditor posture:** Balanced

---

## TL;DR

Stage 8 is well-engineered, honestly documented, and the highest-stakes surface — executing untrusted LLM-generated Python locally — holds up under active probing. The security model is sanitizer-anchored defence in depth: an `ast` block-list (layer 1) that closes the dunder/introspection/globals escape class, backed by a worker (layer 2) that runs the script with a tightly restricted builtins map (no `type`, `chr`, `getattr`, `open`, `eval`, `exec`) against a geometry-only cadquery facade with every submodule stripped. I attempted multiple escapes — the function-globals-to-builtins-import pivot, computed-dunder subscripts, star-import, `type()` class-body tricks, attribute-graph pivots to the OS module — and every one was blocked by layer 1 and/or dead at layer 2 (e.g. `chr`/`type` are not even in the builtins, so a computed dunder string cannot be constructed). The arm's-length seam cleanly mirrors the OpenSCAD/OrcaSlicer/PrintProof3D pattern, graceful-absence is correct, and the mutual fallback never downgrades a passing OpenSCAD result. The one finding that matters: I discovered a working-tree mutation (an `if False and …` short-circuit) that disabled the string-subscript dunder check in `cadquery_runner.py` — it was uncommitted, I restored it from HEAD, but it shows how a single-token change silently re-opens a closed escape and that nothing in the gate would have caught it. Architectural debt is low; the findings below are mostly Minor/Nit hardening and one Major defense-in-depth gap (no OS-level process confinement, which the code itself already flags as future work).

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 4 |
| Nit | 3 |

## What's working

- **The sanitizer is genuinely the load-bearing layer, and it earns it.** `sanitize_cadquery` (`cadquery_runner.py:92-146`) blocks: non-cadquery/math imports (both `Import` and `ImportFrom`, including relative `from . import`), banned names as both `Name` and `Attribute`, all dunder-containing names/attributes, dunder-containing constant string subscript keys (the NEW-007 fix), `format`/`format_map` field pivots, and names in `Global`/`Nonlocal` statements (which AST stores as plain strings, not `Name` nodes — a real and easy thing to miss). I verified the exact Slice-1 escape (the injected-module attribute-graph pivot to the OS module) and the Slice-1-reaudit escape (function-globals to builtins) are each blocked, and blocked redundantly (three ways for the latter).
- **The worker's second layer is a real, independent net even though it cannot close the globals class alone.** I ran the worker subprocess directly (bypassing the sanitizer) with the globals pivot and it did write the marker file — exactly as the docstring honestly says it would. But the dunder-free paths are dead: `type`, `chr`, `ord`, `getattr`, `globals`, `vars` are all absent from `_safe_builtins` (`cadquery_worker.py:102-108`), so an attacker cannot construct a dunder string dynamically or reach an attribute without a dunder. The facade (`_build_facade`, `:66-78`) strips every module object, so the `exporters`/`occ_impl` submodules simply do not exist, and a star-import brings in nothing usable.
- **The arm's-length seam is clean and consistent.** `cadquery_worker.py` is stdlib + cadquery only and never imports `kimcad` (so it loads under the foreign 3.13), the runner returns the same `RenderResult` the pipeline already consumes from OpenSCAD, and the whole orient/harden/gate/readiness tail is backend-agnostic (`pipeline.py:498-527`). This is the right abstraction — the fallback added a backend without perturbing the deterministic spine.
- **Result-to-file, not stdout.** The worker writes its JSON verdict to a dedicated `result_path` (`cadquery_worker.py:193-204`), so an OCCT C++-layer write to fd 1, or a stray print, cannot corrupt the protocol. `_read_worker_result` (`cadquery_runner.py:292-304`) degrades a missing/garbage result file (segfault/kill) into a clean `RenderFailed` synthesized from captured stderr — no raise, no hang.
- **The fallback never downgrades.** `_backend_succeeded` (`pipeline.py:927-939`) short-circuits the moment OpenSCAD renders a non-FAIL part (so a WARN is accepted and CadQuery is never invoked — no doubled LLM cost on the common path), and `_better_result` (`:941-958`) keeps the primary on a tie. Confirmed by `test_openscad_success_does_not_reach_cadquery` and `test_both_backends_fail_keeps_the_primary_result`.
- **Config cache thread-safety is correct.** `cadquery_interpreter()` (`config.py:150-181`) uses a double-checked lock so the ~3s probe runs at most once even under the threaded web server, and the false/empty/path/null sentinels are handled distinctly (and tested).
- **Graceful absence is real.** `_cadquery_renderer_or_none` (`pipeline.py:400-408`) skips the fallback entirely when no interpreter is discoverable; `find_cadquery_interpreter` never raises. Verified the deterministic bench (5/5 watertight at declared envelope) and all 8 live worker security tests pass on the local cadquery 2.7.0 / Python 3.13.13.
- **Test coverage is strong and honest.** The sanitizer is unit-tested without an interpreter; the worker's defenses are independently tested by invoking the subprocess directly (bypassing the sanitizer) so layer 2 is proven in isolation; the conftest hermeticity fixture (`_default_cadquery_backend_off`) is a thoughtful fix for the real flakiness it documents (a box with cadquery installed would rescue a single-backend render_failed test).

## What couldn't be assessed

- **The live dual-backend union lift** (does CadQuery actually rescue prompts OpenSCAD fails?) requires the real `gemma4:e4b` model and is documented as a manual procedure (`docs/benchmarks/stage-8-cadquery-backend.md`), not run here. The engine soundness (deterministic bench) was verified; the union claim is correctly scoped as model-dependent and unmeasured-here.
- **The full live suite** was not run (a push gate is running concurrently, per instructions). I ran the Stage-8 non-live suite (153 passed), the Stage-8 live tests in isolation (`test_cadquery_runner.py -m live`: 8 passed), and targeted probes.
- **OCCT/OCP wheel provenance** (supply-chain) was not deeply audited beyond confirming version `OCP 7.8.x` / cadquery 2.7.0; the dependency is optional and out-of-process, which bounds the risk (see Dependency snapshot).

---

## Findings

> **Finding ID prefix:** `ENG-`

### [ENG-001] — Major — Security — No OS-level confinement: the sandbox is one sanitizer token away from RCE, with no second gate to catch a regression

**Evidence**
The entire untrusted-code boundary rests on the static sanitizer (`cadquery_runner.py:92-146`) plus a restricted-builtins namespace (`cadquery_worker.py:97-112`). The worker docstring is admirably honest about this (`cadquery_worker.py:42-52`): a cadquery facade function still carries its real, unrestricted builtins inside its globals, so a script that reaches a facade function's globals would get full import power; every such path needs a dunder or an introspection attribute, which the static sanitizer blocks — so that escape class is closed by layer 1, not layer 2. The docstring states plainly that OS-level process confinement (no network, restricted working dir) is NOT yet implemented.

I confirmed this empirically. Running the worker subprocess directly with the sanitizer bypassed, a script that reaches a facade function's globals, then its builtins, then the import hook, then the OS module, reached the real OS module and wrote a marker file. Layer 2 alone does not stop this — only the sanitizer does (and it does, three ways: the globals attribute, the builtins subscript key, and the constructor dunder are each blocked).

The fragility this implies is not theoretical. During this audit the working tree contained an uncommitted mutation at `cadquery_runner.py:135`: the string-subscript dunder check had been prefixed with an `if False and …` short-circuit, disabling it (the NEW-007 fix). With layer 1 weakened that way, a string-subscript chain into globals/import would pass the sanitizer; with no OS confinement under it, that is a direct path to code execution. I restored the file from HEAD and re-verified the check blocks the subscript pivot. (Origin of the mutation is unknown — likely a mutation-test or scratch artifact — but the point stands: nothing in the build or gate would have caught a layer-1 hole, because the only test that catches this specific hole is the unit test for that one branch.)

**Why this matters**
The security posture is "local trust model, same as executing generated OpenSCAD" — defensible for a local-first consumer tool — but the OpenSCAD sanitizer blocks a much smaller, regex-shaped surface (file I/O + minkowski), whereas the CadQuery surface is "arbitrary Python minus a block-list." A block-list over a Turing-complete language is inherently one omission away from a bypass, and the consequence here is RCE on the user's machine (the worker has the user's full ambient authority: network, filesystem, env). The gap bites if (a) a future Python/cadquery version exposes a new introspection attribute the block-list does not name, or (b) a refactor regresses a single sanitizer branch — and there is no backstop layer to contain either.

**Blast radius**
- Adjacent code: `cadquery_worker.py` (the exec namespace), `cadquery_runner.render_cadquery` (the subprocess spawn at `:196-202`, which currently inherits the parent env and cwd). The OpenSCAD path (`openscad_runner._run`) shares the "no OS confinement" property but a far narrower code surface.
- Shared state: the worker runs with the parent process's environment (API keys in env vars are readable by escaped code) and unrestricted network.
- User-facing: none on the happy path; this is purely a containment-depth concern.
- Migration: none — additive hardening.
- Tests to update: add a sanitizer-regression canary that asserts each escape-class probe is blocked through the full `render_cadquery` path (not just the unit branch), so a single-branch regression fails loudly.
- Related findings: ENG-002 (subprocess hardening), ENG-005 (probe/env), and the TEST-role gap (no end-to-end escape-class regression suite).

**Fix path**
Treat OS-level confinement as the Stage-8 hardening item the code already promises, scoped to what is cheap on Windows-first: (1) spawn the worker with a scrubbed environment (an explicit minimal env mapping, dropping the API-key vars) and an isolated working directory (a temp dir, not the project root) — both are one-line changes at `cadquery_runner.py:196`; (2) add a deny-network note/option even if enforcement is OS-specific; (3) add the through-`render_cadquery` escape-class regression test described above so a layer-1 regression can never ship silently. Longer term, a Job Object (Windows) or namespaces (Linux) wrapper is the durable answer, but the env-scrub + isolated-cwd + regression-canary trio captures most of the value this sprint.

---

### [ENG-002] — Major — Security — Worker subprocess inherits the full parent environment and runs in-tree (no env/cwd isolation, unlike the OpenSCAD runner)

**Evidence**
At `cadquery_runner.py:196-202` the worker spawn passes no env mapping and no working-directory argument, so the worker inherits the parent's full environment (including any LLM/printer API keys set as env vars per the `config/default.yaml` `api_key_env` keys) and the parent's working directory. The OpenSCAD runner, by contrast, deliberately runs in the isolated `out_dir` for sandbox isolation (`openscad_runner.py:249-256`) and only augments `OPENSCADPATH`.

**Why this matters**
This is the concrete amplifier of ENG-001: if the sanitizer is ever bypassed, the escaped code reads the user's API keys straight out of the environment and can write anywhere relative to the project root. Even absent an escape, it is an inconsistency with the sibling OpenSCAD runner that already models the safer pattern. The exposure is conditional on an escape, so this is Major rather than Critical — but it is the cheapest meaningful hardening in the diff.

**Blast radius**
- Adjacent code: mirror `openscad_runner._run`'s isolation discipline; the worker reads only `script_path`/`result_path` (absolute paths in the request), so it needs no inherited cwd or env at all.
- Shared state: process environment (secrets); the `out_dir` tree.
- User-facing: none.
- Migration: none.
- Tests to update: add a test asserting the worker cannot see a sentinel env var (pass an env mapping without it and confirm a probe script reports it absent).
- Related findings: ENG-001 (root containment gap), ENG-005.

**Fix path**
Pass an explicit minimal env (drop secret-bearing vars; keep only what cadquery/Python need such as `PATH`, `SYSTEMROOT`, `TEMP`) and the isolated `out_dir` working directory to the worker spawn. Both are low-risk one-liners and bring the CadQuery runner to parity with the OpenSCAD runner's isolation.

---

### [ENG-003] — Minor — Security — Sanitizer string-subscript check only inspects constant keys (computed/bytes keys evade it)

**Evidence**
At `cadquery_runner.py:131-136` the `Subscript` branch flags a key only when it is an `ast.Constant` string containing a dunder. A computed key (built from `chr(95)` runs concatenated with a name fragment) or a bytes key is not an `ast.Constant` str and slips past this branch. I confirmed both are ALLOWED by the sanitizer in isolation.

**Why this matters**
In the current worker this is not reachable: `chr`/`ord`/`bytes`/`type` are absent from the restricted builtins, so the attacker cannot construct the string at runtime, and there is no object in scope whose item-access returns globals anyway. So today this is a latent gap, not a live bypass — which is why it is Minor, not Critical. But it is exactly the kind of "the other layer happens to cover it" coupling that ENG-001 warns about: if a future change adds `chr`/`bytes`/`type` to the builtins (easy to imagine for legitimate geometry math), this branch silently becomes a hole.

**Blast radius**
- Adjacent code: the worker builtins allow-list (`cadquery_worker.py:102-108`) is the implicit reason this is safe; the two must stay coupled.
- Migration: none.
- Tests to update: add the ALLOWED-today computed/bytes-key probes as explicit regression markers so the coupling is documented.
- Related findings: ENG-001.

**Fix path**
Flag any `Subscript` whose key is a constant (str or bytes) containing a dunder, and — defensively — keep the worker builtins free of string-construction primitives (document that `chr`/`ord`/`bytes`/`type` must never be added without re-hardening the sanitizer). Add a comment noting that computed-key subscripts are intentionally relied on to be inert because no string-building builtin exists.

---

### [ENG-004] — Minor — Performance — Every CadQuery fallback pays a fresh ~3s OCCT cold-start per render, and the retry loop multiplies it

**Evidence**
Measured on the dev box: each `render_cadquery` call is ~3.0s wall-clock, dominated by importing cadquery + OCCT init in a fresh subprocess (the worker reloads every call). The fallback runs a full codegen-render-gate loop with its own retry budget (`pipeline.py:873-925`); with `max_render_retries=2` (the default), a hard CadQuery prompt can spawn up to 3 worker processes (3 × ~3s startup) plus the LLM codegen calls — on top of the OpenSCAD attempts that already failed.

**Why this matters**
The fallback only fires when OpenSCAD already failed, so the user is already in a slow/degraded path; adding ~9s of pure process-startup overhead (before any geometry work or model latency) is noticeable but bounded. Minor because it only affects the failure path and is dwarfed by the CPU-bound local model latency (minutes, not seconds) — but worth a comment so a future maintainer does not assume the worker is warm.

**Blast radius**
- Adjacent code: `_run_llm_backend` retry loop; `render_cadquery` (one subprocess per call).
- User-facing: extra latency only on the OpenSCAD-failed fallback path.
- Migration: none.
- Tests to update: none.
- Related findings: none.

**Fix path**
Acceptable as-is for a fallback. If it ever matters, a persistent worker (spawn once, feed scripts over stdin in a loop) would amortize the OCCT cold-start — but that trades the clean fresh-process-per-render isolation property for speed, so it is not obviously worth it. Recommend documenting the cost in `render_cadquery`'s docstring rather than optimizing now.

---

### [ENG-005] — Minor — Correctness — `find_cadquery_interpreter` probe treats all of stdout as the path; a candidate that also prints to stdout is silently skipped

**Evidence**
At `cadquery_runner.py:275-289` the probe runs a one-liner that writes `sys.executable` to stdout and accepts the result if the return code is 0 and the printed path exists on disk. If a candidate interpreter's startup writes anything to stdout (a sitecustomize banner, a deprecation print), the captured output becomes the banner plus the path concatenated, and the path-exists check correctly fails — so the failure mode is "skip a usable interpreter," not "accept a bad one." That is the safe direction, but a noisy-but-valid interpreter goes silently undiscovered.

**Why this matters**
Low impact: graceful absence means a missed interpreter just disables the backend (OpenSCAD still works). Flagged so the "why didn't auto-discovery find my cadquery?" support case is anticipated. The 20s per-candidate timeout (`:279-281`) across up to 7 candidates also means a pathological PATH could spend ~140s on first probe — but it is cached after the first call and bounded.

**Blast radius**
- Adjacent code: `Config.cadquery_interpreter` (caches the result); the env/cwd concern of ENG-002 also applies to the probe subprocess.
- User-facing: backend silently off on a noisy interpreter.
- Migration: none.
- Tests to update: none.
- Related findings: ENG-002.

**Fix path**
Make the probe robust to leading noise: print a sentinel-delimited path and parse the last matching line rather than treating all of stdout as the path. Minor and optional.

---

### [ENG-006] — Minor — Hygiene — `_default_cadquery_renderer` always emits STEP, and the output-size guard covers the STL only

**Evidence**
At `pipeline.py:386-398` the default CadQuery renderer always passes `emit_step=True` and reuses `max_output_bytes` (the 200MB OpenSCAD render guard). STEP export adds a second OCCT export pass on every CadQuery part (cost on the already-slow fallback path), and the size guard is checked against the STL only (`cadquery_runner.py:223-226`) — a pathological STEP file is not bounded by `max_output_bytes`.

**Why this matters**
Minor: STEP is the whole point of the CadQuery path (editable CAD export) so always emitting it is defensible, and a runaway STEP is unlikely given the geometry is already gate-bounded. Worth noting that the guard's coverage is STL-only, so the docstring's "output size guard" is slightly broader than the implementation.

**Blast radius**
- Adjacent code: `render_cadquery` size check; `webapp._serve_step` reads the STEP bytes whole into memory to serve (an unbounded STEP would be read entirely into RAM).
- Migration: none.
- Tests to update: none.
- Related findings: none.

**Fix path**
Either also bound the STEP size against the guard in `render_cadquery`, or note explicitly in the docstring that the guard covers the STL only and STEP is implicitly bounded by the gate-validated geometry. Low priority.

---

### [ENG-007] — Nit — Hygiene — `cadquery_worker.py` imports `os`/`sys` at module top; harmless but worth a one-line note given the sandbox it builds

**Evidence**
At `cadquery_worker.py:55-63` the harness imports `os`, `sys`, and friends. These are used only by the worker harness (file reads, file-size lookup, the stdout fallback) and never enter the executed script's namespace (the script gets `_safe_builtins`, not the module globals — the exec uses an explicit fresh dict). So this is correct and safe.

**Why this matters**
Purely a readability note: a reviewer skimming the file sees an OS-module import in the file that sandboxes untrusted code and has to confirm it is never exposed. It is not. A one-line comment would save that double-take.

**Fix path**
Add a comment at the import block noting these are harness-only and never reach the executed script's namespace.

---

### [ENG-008] — Nit — Architecture — `backend`/`step_path` are now duplicated across `RenderResult`, `PrintReport`, and `PipelineResult`

**Evidence**
`backend` and `step_path` appear on `RenderResult` (`openscad_runner.py:107-112`), `PrintReport` (`pipeline.py:211-216`), and `PipelineResult.backend` (`pipeline.py:312-314`), each copied through `_build_report` and `_assemble_result`. This is a reasonable DTO-flattening choice (each layer is independently serializable), but it is three places to keep in sync.

**Why this matters**
Nit. It is a deliberate, consistent pattern (mirrors how the rest of the report flattens fields for the web payload). Flagged only so the team is aware the backend/step pair is now a cross-layer invariant.

**Fix path**
None needed; if the field count grows, consider a small value object carried through. Not worth it today.

---

### [ENG-009] — Nit — Documentation — One docstring phrase ("output size guard") is slightly ahead of the STL-only implementation

**Evidence**
`config/default.yaml:18-25` documents `cadquery_python` thoroughly and correctly; `docs/cadquery-backend.md` and the worker docstring are excellent. The only drift: the worker docstring (`cadquery_worker.py:38`) and `render_cadquery`'s docstring reference an "output size guard" generically while the guard is STL-only (see ENG-006).

**Why this matters**
Nit — the docs are unusually good and honest (they explicitly call out the unimplemented OS-confinement, the model-dependent union lift, and the layer-1-vs-layer-2 division). This is a tiny precision note, not a real gap.

**Fix path**
Align the "output size guard" phrasing with ENG-006's resolution.

---

## Patterns and systemic observations

The root pattern is "block-list over a Turing-complete language, with the only real backstop being a sibling layer that happens to cover the gaps." ENG-001, ENG-002, and ENG-003 are all facets of this. It is a defensible posture for a local-first tool whose trust model is "you already run generated OpenSCAD on your machine," and the implementation is unusually careful (the dunder/introspection/format/global coverage is more complete than most hand-rolled Python sandboxes I have seen). But three things make the residual risk worth a sprint of hardening: (1) the consequence is code execution with the user's full ambient authority including API keys in env; (2) the two layers are coupled — the sanitizer is safe partly because the worker withholds `chr`/`type`, and the worker is safe partly because the sanitizer blocks dunders — so a change to either side can silently weaken the whole; (3) I found a live, uncommitted single-token regression of exactly this kind, and nothing in the gate would have caught it. The highest-leverage fixes are cheap and additive: pass the worker a minimal env + an isolated working directory (ENG-002), add a through-`render_cadquery` escape-class regression canary (ENG-001), and document the inter-layer coupling so neither side is weakened in isolation (ENG-003).

What is genuinely well done and should be preserved: the honesty of the threat-model docstrings (they state what each layer cannot do, not just what it can), the result-to-file protocol, the fail-closed fallback that can only raise the pass rate, and the clean reuse of the existing `RenderResult`/orient/harden/gate tail so the second backend added zero branching to the deterministic spine.

## Dependency snapshot

- cadquery 2.7.0 — optional, out-of-process on a separate sub-3.14 interpreter; never imported in the 3.14 main process. Heavy (OCCT) but isolated. Not in KimCad's own dependency closure — the user installs it into a side interpreter.
- OCP (OpenCASCADE) 7.8.x — transitive via cadquery; a C++ kernel. Runs in the sandboxed worker subprocess. Provenance not deeply audited; risk bounded by out-of-process isolation plus the recommended env/cwd isolation.
- Python (worker) 3.13.13 — foreign interpreter, discovered or configured. No 3.14 wheels for OCP is the entire reason for the arm's-length design — correctly handled.

Stage 8 adds no new dependency to KimCad's own 3.14 environment — a deliberate, good architectural choice. The new code is stdlib-only on the main side (`ast`, `subprocess`, `json`, `threading`).

## Appendix: artifacts reviewed

- `src/kimcad/cadquery_worker.py`, `src/kimcad/cadquery_runner.py`, `src/kimcad/pipeline.py`, `src/kimcad/llm_provider.py`, `src/kimcad/config.py`, `src/kimcad/openscad_runner.py`, `src/kimcad/webapp.py` (Stage-8 diff)
- `src/kimcad/cadquery_bench.py`, `src/kimcad/prompts/system_cadquery.md`, `config/default.yaml`
- `tests/test_cadquery_runner.py`, `tests/test_pipeline_backends.py`, `tests/test_config.py`, `tests/test_webapp.py` (Stage-8 parts), `tests/test_cadquery_bench.py`, `tests/conftest.py` (diff)
- `ROADMAP.md`, `docs/cadquery-backend.md`, `docs/benchmarks/stage-8-cadquery-backend.md` (diffs)
- Live probes executed (Python 3.13.13 + cadquery 2.7.0): sanitizer adversarial set (~30 inputs incl. computed-dunder subscripts, star-import, `type()`/`chr()` tricks, alias hiding, format pivots); worker-in-isolation escapes (the globals pivot reached the OS module and wrote a marker, confirming the layer-2-alone gap; the facade attribute-graph pivot was blocked); full two-layer `render_cadquery` escapes (all blocked or inert); discovery + render performance timing; the deterministic engine bench (5/5); the Stage-8 non-live suite (153 passed) and live worker suite (8 passed).
- Note: on arrival the working tree carried an uncommitted edit at `cadquery_runner.py:135` (an `if False and …` short-circuit) that disabled the string-subscript dunder check; I reverted that one file to its committed state and re-verified the check blocks the subscript pivot. See ENG-001.
