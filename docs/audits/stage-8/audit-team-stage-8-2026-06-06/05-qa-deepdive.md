# Runtime QA Deep-Dive — KimCad (Stage 8, CadQuery parallel backend)

**Audit date:** 2026-06-06
**Role:** QA Engineer
**Scope audited:** Stage 8 CadQuery parallel-geometry backend, end to end at runtime — the in-process runner (`kimcad.cadquery_runner`), the out-of-process worker (`kimcad.cadquery_worker`), the config-driven interpreter discovery (`kimcad.config.Config`), the pipeline backend selection + mutual OpenSCAD↔CadQuery fallback (`kimcad.pipeline`), and the web layer's editable-CAD download (`GET /api/step/<id>`).
**Environment:** Windows 11 Pro (10.0.26200). App/gate venv = Python 3.14.3 (`C:\Users\scott\dev\kimcad\.venv`). CadQuery worker interpreter discovered = Python 3.13.13 (`C:\Users\scott\AppData\Local\Programs\Python\Python313\python.exe`) with `cadquery` installed. Branch `stage-8-cadquery` @ `b945569`, clean tree. Demo server: `python -m kimcad.cli web --demo --port 8770`. HTTP client: curl 8.x.
**Auditor posture:** Balanced. **Method: the product was RUN.** Every finding below has an executed command and observed output — no static-only claims.

---

## TL;DR

The Stage 8 CadQuery backend behaves as designed and documented. I exercised the real ≤3.13+cadquery worker, the 3.14 in-process runner, the config layer, the pipeline fallback, and the running demo web server. A clean script builds STL+STEP; the `result`-assignment contract holds; missing/degenerate `result`, blocked scripts, the timeout guard, and the output-size guard all fail **cleanly** with no traceback leak and no leftover artifacts. The two-layer security model is **honest**: the static sanitizer (layer 1) blocks every dunder/introspection escape source I threw at it, and the production entry point (`render_cadquery`) always runs that sanitizer before the worker ever sees the code. The `/api/step/<id>` endpoint is immune to path traversal because the id is an integer dict key, never a filesystem path component. **No Blockers and no Criticals were found.** The one security nuance worth recording — the worker's *runtime* layer alone does not independently contain a `__globals__`-based escape (I reproduced a marker-file write by invoking the worker directly with the sanitizer bypassed) — is **exactly** what the worker's own docstring states it cannot do, and that path is **not reachable** in production because the sanitizer closes it. I log it as Minor (a defence-in-depth gap that is currently mitigated, not a live hole).

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 1 |

## What's working

- **Clean build produces STL + STEP, correct geometry.** `render_cadquery('result = cq.Workplane("XY").box(40,30,20).faces(">Z").workplane().hole(8)', emit_step=True)` → STL 26,084 B (trimesh extents `[20,30,40]`, watertight), STEP 20,254 B, ~3.2s. `backend="cadquery"`, `output_format="stl"`.
- **The documented contract is enforced.** A script that builds geometry but never assigns `result` → `RenderFailed: the script defined no 'result' object to export`, no STL/STEP written. A degenerate `result = cq.Workplane("XY")` (no solid) → `RenderFailed: result has no measurable solid`. Both leave the temp dir empty.
- **Both guards fire and clean up.** `timeout_s=1` on a real OCCT build → `RenderTimeout`, no leftover STL. `max_output_bytes=10` → `OversizeOutput`, STL deleted (`part.stl` absent after).
- **The static sanitizer blocks every escape source.** `import os`, `cq.exporters.os.system(...)`, the `__globals__["__builtins__"]["__import__"]` chain, the `__subclasses__()` chain, `obj["__globals__"]` string-subscript, frame-introspection attrs, and `str.format` field pivots — all rejected by `sanitize_cadquery`, all before any subprocess spawns.
- **The worker's restricted builtins withhold the obvious primitives.** Invoked directly (sanitizer bypassed): `open()` → `NameError: name 'open' is not defined` (no file created); `eval`/`print` → `NameError`; `__import__('socket')` → `ImportError: import of 'socket' is not allowed`. The geometry-only facade has no `cq.exporters` submodule (the Slice-1 audit Blocker), so the `cq.exporters.os.system` pivot raises `AttributeError` and writes nothing.
- **Result goes to a dedicated file, never stdout.** A clean worker render leaves `stdout` empty and the JSON contract in `result_path`; a script that `print()`s is swallowed. A native fd-1 write cannot corrupt the contract.
- **Worker protocol is robust.** Garbage stdin → `{"ok": false, "kind": "protocol", ...}` (returncode 0, empty stderr); a JSON array → `request must be a JSON object`. A deep OCCT failure (oversized fillet) → clean `{"kind": "exec", "error": "StdFail_NotDone: ..."}` with **no Python traceback** on stderr and **no traceback in the `RenderFailed` message**.
- **Config interpreter resolution is correct + cached.** `null` → auto-discovers Python 3.13 and caches it (2nd call identical); `false` and `""` → `None` with no probe; a bogus explicit path → `None` (authoritative, no silent fall-through); `["py","-3.13"]` → resolves to the real `python.exe`.
- **Pipeline fallback is correct in all four cases.** OpenSCAD-passes → CadQuery never called (0 codegen calls). OpenSCAD gate-fails → CadQuery fallback rescues with the correct size, `backend="cadquery"`, STEP attached. Both gate-fail → `gate_failed`, never sliced (an asserting slicer stub was never invoked). No interpreter → fallback skipped, OpenSCAD-only, no error.
- **Graceful absence end to end.** With `binaries.cadquery_python: false`, a real OpenSCAD template design completes (gate pass, mesh written, `step_path` None), `_cadquery_renderer_or_none()` returns None — the backend is simply off, no error.
- **`/api/step/<id>` is traversal-proof and content-correct.** Unknown int, non-int, empty, negative, huge, `1abc`, `%00`, and every url-encoded `../` variant → clean JSON 404. An OpenSCAD part's id → 404 (no STEP). The positive download path (`application/step`, `ISO-10303-21` body) is proven by the existing socket test, which passes here.

## What couldn't be assessed

- **A real CadQuery STEP download over HTTP from the demo server.** By design the `--demo` provider only emits CadQuery for the `demo:gatefail` scenario, and that part stays oversized so it is gate-failed and therefore never registered for a STEP download. Producing a real, downloadable CadQuery STEP over HTTP needs the live LLM model (out of scope here). The positive `/api/step` wiring is covered instead by `tests/test_webapp.py::test_cadquery_part_exposes_a_step_download` (fake CadQuery pipeline over a real socket) — I ran it; it passes. I verified the negative/security side of `/api/step` directly against the running server.
- **OS-level process confinement (network off, restricted CWD).** The worker docstring explicitly defers this as future hardening; it is not implemented, so there was nothing to runtime-test. See QA-002.
- **Concurrency on the live web `cadquery_interpreter()` probe-once lock.** I confirmed the cache returns an identical handle on repeated calls in-process; I did not stress two cold HTTP requests racing the ~3s probe (would require the live model path). The lock is present in code (`Config._cadquery_lock`).

---

## Product shape

KimCad is a local-first AI→3D-print desktop tool: a prompt becomes a design plan, geometry is generated (OpenSCAD primary, CadQuery parallel fallback), rendered to a mesh, gated for printability, oriented/hardened, and — only on explicit confirmation — sliced. Stage 8 adds the CadQuery backend, which runs **out-of-process on a separate ≤3.13 interpreter** (CadQuery's OCCT has no 3.14 wheels) and uniquely exports editable STEP/BREP. The geometry it executes is **untrusted LLM output**, so QA focused on three runtime dimensions: (1) correctness of the build + the documented `result` contract, (2) the security boundary against a sanitizer-bypassing malicious script, and (3) the web-layer download surface (traversal, content-type, status correctness). I matched method to shape — this is a CLI/library + a thin stdlib HTTP layer, not a SaaS app, so I drove the Python entry points and the HTTP endpoint, not a browser.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Clean script → STL + STEP via `render_cadquery` | Pass | — |
| `result`-assignment contract (missing `result`) | Pass (clean `RenderFailed`) | — |
| Degenerate `result` (no solid / zero extent) | Pass (clean `RenderFailed`) | — |
| Blocked script (`import os`) via runner | Pass (`BlockedCodeError`, nothing written, no subprocess) | — |
| Attribute pivot `cq.exporters.os.system` via runner | Pass (`BlockedCodeError`) | — |
| Timeout guard (`timeout_s=1`) | Pass (`RenderTimeout`, no leftovers) | — |
| Output-size guard (`max_output_bytes=10`) | Pass (`OversizeOutput`, STL deleted) | — |
| Config resolution: null / false / "" / bogus path / argv | Pass (all correct, cached) | — |
| Pipeline: OpenSCAD passes → no CadQuery | Pass | — |
| Pipeline: OpenSCAD gate-fails → CadQuery rescues (+STEP) | Pass | — |
| Pipeline: both gate-fail → gate_failed, never sliced | Pass | — |
| Pipeline: no interpreter → OpenSCAD-only, no error | Pass | — |
| Graceful absence (`cadquery_python: false`) end to end | Pass | — |
| `GET /api/step/<id>` — unknown / non-int / OpenSCAD part | Pass (clean 404) | — |
| `GET /api/step/<id>` — url-encoded path traversal | Pass (clean 404, no FS access) | — |
| Positive `/api/step` download (socket test) | Pass | — |
| Demo `demo:gatefail` over HTTP + server-side slice refusal | Pass (gate_failed, slice refused) | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| `open(path,'w')` direct to worker (sanitizer bypassed) | `NameError`, no file written | — (credit) |
| `().__class__.__bases__[0].__subclasses__()` chain to worker | ran, did **not** reach a usable escape; no marker written | — |
| `cq.exporters.os.system(...)` direct to worker | `AttributeError` (facade has no submodule), no marker | — (credit) |
| `Workplane.__init__.__globals__["__builtins__"]["__import__"]("os").system(...)` direct to worker | **marker file WAS written** — worker-layer-only escape | QA-001 (Minor) |
| Same `__globals__` source through `sanitize_cadquery` | **blocked** (5 dunder/subscript/attr violations) — production path is closed | QA-001 mitigation |
| `__subclasses__`-walk to find a class with `__builtins__` (direct to worker) | no class matched in this run; no marker written | QA-001 |
| Garbage / non-object JSON on worker stdin | clean `protocol` error, returncode 0, empty stderr | — (credit) |
| Deep OCCT failure (`fillet(99999)`) | clean `exec` error, no traceback leak anywhere | — (credit) |
| `/api/step/` with `..%2f..%2f`, `%2e%2e%2f`, raw `../../config/default.yaml` | clean 404, no file disclosed | — (credit) |
| `/api/step/` with `-1`, huge int, `1abc`, `1%00` | clean 404 | — (credit) |
| `POST /api/slice/<gate-failed id>` (non-browser client) | refused server-side: `reason: gate_failed` | — (credit) |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Console / Install

### [QA-001] — Minor — Security — The worker's runtime layer alone does not contain a `__globals__`-based escape (mitigated by the sanitizer; documented)

**Evidence**
Invoking the worker subprocess **directly**, bypassing the static sanitizer (the production runner never does this — it always sanitizes first):

1. Script (written to a scratch file, sent to `cadquery_worker.py` on stdin):
   ```python
   f = cq.Workplane
   g = f.__init__.__globals__
   osmod = g["__builtins__"]["__import__"]("os")
   osmod.system(r"echo x > <scratch>\pwned_globals.txt")
   result = cq.Workplane().box(1,1,1)
   ```
2. Observed: `{"ok": true, "bbox_mm": [1.0,1.0,1.0], ...}` AND **the marker file `pwned_globals.txt` was created** (`MARKER written: True`). The restricted builtins are bypassed because a facade function still carries its real, unrestricted `__builtins__` inside `__globals__`.
3. The **same source** through `sanitize_cadquery(...)` is **blocked**: `safe == False`, violations include `dunder access '__globals__'`, `dunder access '__init__'`, `subscript with a dunder key '__import__'`, `attribute access '.system'`, `subscript with a dunder key '__builtins__'`.
4. The `__subclasses__()`-walk variant run directly against the worker did **not** find a usable class in this run (no marker written), but is also blocked by the sanitizer (`dunder access '__subclasses__'` etc.).

Environment: Python 3.13.13 worker, Python 3.14.3 runner, branch `stage-8-cadquery`.

**Why this matters**
This is the escape class the worker's own docstring (point 3, `cadquery_worker.py` lines 42–48) explicitly states it **cannot** independently close, and that the runner docstring assigns to layer 1. The production entry point `render_cadquery` **always** calls `sanitize_cadquery` first (`cadquery_runner.py` line 169, before any subprocess), so in the shipping product this path is **not reachable**: the malicious source is rejected with `BlockedCodeError` and no worker is spawned. The finding is therefore **defence-in-depth, not a live hole** — the single sanitizer layer is currently the *only* thing standing between untrusted LLM code and a real `os` module. If a future dunder-evasion technique slips past the AST sanitizer (or a caller is ever added that reaches the worker without sanitizing), there is no second wall. Severity is Minor because (a) the reachable production path is closed today and verified closed, (b) KimCad's trust model is local execution of generated code on the user's own machine (the same posture as executing generated OpenSCAD), and (c) the residual is honestly documented in-code.

**Blast radius**
- Adjacent code: `kimcad/cadquery_worker.py` (`_safe_builtins`, `_safe_import`, `_build_facade`) and `kimcad/cadquery_runner.py::sanitize_cadquery` (the sole reachable gate). Any new caller of the worker must sanitize first — there is exactly one today (`render_cadquery`).
- Shared state: none. The worker is a stateless subprocess.
- User-facing: none today. Legitimate geometry is unaffected; the sanitizer blocks no valid CadQuery (verified: a banned word inside a `.text("import os")` string literal is NOT a false positive).
- Migration: none. The durable fix is OS-level process confinement (see QA-002), additive.
- Tests to update: none break. Consider adding a live test that asserts the worker-direct `__globals__` escape is the *only* thing the sanitizer-bypass demonstrates, so the honest two-layer claim stays pinned.
- Related findings: QA-002 (the durable hardening that would turn this Minor into "closed at both layers").

**Fix path**
Keep the sanitizer as the authoritative layer (it is correct and comprehensive today). To remove the residual, land the deferred OS-level confinement: run the worker with the network disabled and a restricted working directory (e.g. a job object / restricted token on Windows, or a sandbox subprocess), so even a hypothetical sanitizer bypass cannot reach the filesystem or network. This is already tracked as future hardening in the worker docstring — recommend promoting it to a Stage-8.x backlog item rather than leaving it implicit.

---

### [QA-002] — Minor — Security — OS-level worker confinement (network-off, restricted CWD) is not implemented

**Evidence**
The worker docstring (`cadquery_worker.py` lines 46–48) states: *"The durable, defence-in-depth answer (OS-level process confinement: no network, restricted working dir) is tracked as a later hardening; it is NOT yet implemented."* Confirmed at runtime: the worker is spawned as a plain `subprocess.run([interpreter, WORKER_PATH], ...)` (`cadquery_runner.py` lines 196–202) with the inherited environment and no sandboxing. The QA-001 marker-write reproduction confirms that, absent the sanitizer, the worker process has full filesystem reach.

**Why this matters**
Today the entire security guarantee rests on a single in-process AST sanitizer. A second, OS-enforced wall (no outbound network, a scratch-only working directory) would make the boundary robust against any future logic-layer bypass and would also defend against a CadQuery/OCCT native-code bug that a Python sanitizer fundamentally cannot see. Minor (not higher) because the reachable path is gated and the trust model is local-machine execution.

**Blast radius**
- Adjacent code: `cadquery_runner.py::render_cadquery` (subprocess spawn) — would gain platform-specific confinement (Windows job object/restricted token; POSIX equivalents for `python3.x` discovery). Mirror the same treatment for OpenSCAD/OrcaSlicer subprocesses for consistency.
- Shared state: the worker request/result protocol is unchanged — confinement is wrapping, not contract change.
- User-facing: none for legitimate parts; a confined worker that can't write outside its scratch dir is invisible to a well-behaved script.
- Migration: none.
- Tests to update: none break; add a confinement test (e.g. a sanitizer-bypassed script attempting a network connect / out-of-CWD write fails under confinement).
- Related findings: QA-001 (this is its durable fix).

**Fix path**
Add a platform-aware confinement wrapper around the worker subprocess: on Windows, a job object with `JOB_OBJECT_LIMIT` + a restricted token and a per-render scratch CWD; block network at the process level where feasible. Stage-8.x backlog.

---

### [QA-003] — Nit — Console — OCCT native stderr noise can reach the captured diagnostic stream

**Evidence**
Python-level `stdout`/`stderr` from the script are swallowed (`contextlib.redirect_stdout/redirect_stderr`, `cadquery_worker.py` line 149), and the authoritative result is on `result_path`, so the contract is never corrupted (verified: clean render → empty `proc.stdout`). However, OCCT is a C++ library that can write to the OS-level fd 2 below Python's redirection. In my deep-failure test (`fillet(99999)`) the captured `RenderFailed` message was clean (`StdFail_NotDone: BRep_API: command not done`, no traceback), but OCCT C++ warnings on a more complex model could surface in `proc.stderr`, which the runner does pass through into `RenderResult.stderr`.

**Why this matters**
Cosmetic only — it never corrupts the JSON result (that's on a dedicated file by design) and never breaks a render. Worth a one-line note so a future reader doesn't mistake OCCT chatter in `stderr` for a defect.

**Fix path**
No action required. If desired, document that `RenderResult.stderr` for a CadQuery part may carry OCCT native diagnostics, or filter known-benign OCCT lines before surfacing.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| CadQuery cold render (box + hole, STL+STEP) | ~3.2 s | OCCT cold-import dominated; acceptable for a local CPU tool | pass |
| Interpreter discovery probe (`import cadquery`) | within the 20 s bound; cached after first call | <20 s guard | pass |
| `/api/step/<id>` 404 (unknown/traversal) | sub-millisecond (int parse + dict miss) | trivial | pass |
| `/api/mesh/1` (OpenSCAD demo part) | 200, 1,284 B, immediate | trivial | pass |

The ~3 s render is OCCT cold-import + tessellation, not KimCad overhead; the config caches the discovered interpreter so the probe cost is paid once per process. The CadQuery path is the slower, parallel backend by design (it runs only when OpenSCAD can't satisfy the gate), so this latency sits off the common path.

## Security / privacy snapshot

- **Path traversal on `/api/step/<id>`: not reachable.** The id is parsed with `int(raw_id)` and used only as a dict key into `step_registry`; no filesystem path is ever constructed from caller input. Every url-encoded `../`, `%2e`, `%00`, and raw-dots attempt returned a clean JSON 404. The download filename is server-minted (`kimcad-part-<int>.step`), so there is no Content-Disposition header injection.
- **Untrusted-code execution: gated by the sanitizer (reachable path closed), with a documented runtime-layer residual** — see QA-001/QA-002.
- **Gate-failed parts cannot be sliced/sent**, even by a non-browser API client: `POST /api/slice/<gate-failed id>` returned `{"sliced": false, "reason": "gate_failed"}`. The Stage-8 fallback does not weaken this boundary.
- **No secret/credential exposure observed** on the CadQuery/STEP surfaces.

## Console and log observations

Server log (`--demo --port 8770`) was clean across the session — the handler suppresses access logging (`log_message` no-op) and no unhandled exceptions surfaced. Worker subprocesses returned exit code 0 on every error path (errors are data on `result_path`, not crashes). No Python traceback leaked to a user-facing message or to stdout in any tested failure.

## Patterns and systemic observations

- **"Block, don't strip" is applied consistently** across both the OpenSCAD and CadQuery sanitizers — dangerous input is rejected so the orchestrator re-prompts, and valid geometry is never silently mutated. This is the right call and held under every adversarial input.
- **Errors are data, not exceptions, at the process boundary** — the worker always exits 0 and reports via a dedicated result file; the runner synthesizes a clean failure when that file is missing (worker crash/kill). This made every failure path I tested degrade gracefully.
- **The two-layer security story is documented honestly**, with the in-code docstrings stating precisely what each layer can and cannot guarantee. That honesty is itself a quality signal; QA-001/QA-002 simply track the residual the docs already name.
- **Graceful absence is a first-class, tested posture** (`false`/`""`/missing interpreter all leave the backend cleanly off), mirroring the optional PrintProof3D engine.

## Appendix: environments and artifacts

- **Runner / app venv:** Python 3.14.3 (`.venv/Scripts/python.exe`).
- **CadQuery worker interpreter:** Python 3.13.13 (`...\Python313\python.exe`), `cadquery` importable.
- **Branch / commit:** `stage-8-cadquery` @ `b945569` (clean working tree).
- **Demo server:** `python -m kimcad.cli web --demo --port 8770` (terminated and port freed after the audit).
- **Tools:** curl (HTTP), custom Python harnesses driving `kimcad.cadquery_runner` / `kimcad.cadquery_worker` / `kimcad.config.Config` / `kimcad.pipeline`, and `pytest` for the three focused web socket tests (`test_cadquery_part_exposes_a_step_download`, `test_openscad_part_has_no_step_url_and_unknown_step_is_404`, `test_serves_spa_index_and_assets_and_rejects_traversal` — all passed, 3/3 in 1.76 s). The full live pytest suite was deliberately NOT run (a push gate was running concurrently).
- **Scratch:** all harness scripts and temp render dirs were created under `_qa_scratch/` and OS temp, and cleaned up after the audit.
