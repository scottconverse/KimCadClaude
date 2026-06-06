# Audit Lite — Stage 8 Slice 1: CadQuery parallel-geometry backend (out-of-process execution core)

**Date:** 2026-06-06
**Scope:** Working-tree (uncommitted) review of the CadQuery backend's arm's-length execution core on branch `stage-8-cadquery`: `src/kimcad/cadquery_worker.py` (NEW), `src/kimcad/cadquery_runner.py` (NEW), the `RenderResult` change in `src/kimcad/openscad_runner.py` (MODIFIED), and `tests/test_cadquery_runner.py` (NEW).
**Reviewer:** Claude (audit-lite), genuinely independent — ran the real worker on the system 3.13 + cadquery 2.7.0 interpreter.

## TL;DR
**Do not ship.** The two-layer sandbox has a confirmed, reproduced, full escape: an untrusted LLM-generated script can read/write arbitrary files and execute arbitrary shell commands by pivoting through cadquery's own `exporters` submodule (`cq.exporters.os.system(...)`), which the worker hands the script as the injected `cq` object. The payload passes the static sanitizer with zero blocks AND runs in the live worker with `{"ok": true}`. The static block-list checks banned names only as bare `Name` nodes, never as attribute access, and the injected `cq` object is a live graph reaching the full stdlib. The restricted `__builtins__` is bypassed entirely (the escape never touches builtins). Everything else in the slice is solid — the subprocess contract, crash handling, and the `RenderResult` change are well done — but the central security promise of the slice is broken.

## Severity rollup
- Blocker: 1
- Critical: 1
- Major: 1
- Minor: 2
- Nit: 1

## Findings

### FINDING-001 — Blocker (Correctness & Security): Untrusted script escapes the sandbox via cadquery's `exporters.os` — arbitrary file write + arbitrary command execution
**Dimension:** Correctness & Security
**Evidence:** Reproduced end-to-end against the real worker (`py -3.13`, cadquery 2.7.0). Payload:
```python
_p = cq.exporters.os.path.join(cq.exporters.tempfile.gettempdir(), 'kimcad_PWNED_marker.txt')
with cq.exporters.os.fdopen(cq.exporters.os.open(_p, cq.exporters.os.O_WRONLY | cq.exporters.os.O_CREAT, 0o644), 'w') as _f:
    _f.write('escaped via cq.exporters.os')
cq.exporters.os.system('echo SANDBOX_ESCAPE_VIA_OS_SYSTEM')
result = cq.Workplane('XY').box(1,1,1)
```
- `sanitize_cadquery(payload)` → `safe=True, blocked=[]` (no Name node `os`; only attribute access `.os`, which the AST walk does not check — `cadquery_runner.py:95-101` only flags `ast.Name` against `_BANNED_NAMES` and `ast.Attribute` only for `__` dunders).
- Live worker stdout: `SANDBOX_ESCAPE_VIA_OS_SYSTEM` then `{"ok": true, "bbox_mm": [1.0, 1.0, 1.0], "stl_bytes": 684, "step_bytes": null}` — a *successful render*.
- The file `C:\Users\scott\AppData\Local\Temp\kimcad_PWNED_marker.txt` was written with the marker contents. Confirmed on disk, then cleaned up.
- Root: `py -3.13` enumeration showed three live module pivots reachable from the injected `cq` by pure attribute access (no dunder, no banned Name): `cq.exporters.os` → `os`, `cq.exporters.assembly.os` → `os`, `cq.exporters.tempfile` → `tempfile`. From `os` the script reaches `os.system`, `os.open`, `os.environ`, `os.remove`, `os.popen`, etc. — none of which are banned names or dunders.
- The worker's `_safe_builtins` (`cadquery_worker.py:65-80`) and locked `__import__` (`:51-62`) are irrelevant here: the escape never calls a builtin or `import`; it walks the attribute graph of an object the worker itself injected (`cadquery_worker.py:103-108`).

**Why it matters:** This is the single most important thing the slice exists to get right (per the worker docstring `cadquery_worker.py:24-34` and runner docstring `cadquery_runner.py:13-16`). Both defense layers fail open against a one-line payload an LLM can emit by accident or an attacker can inject via a crafted prompt. "ok: true" means the orchestrator treats the malicious render as a *valid result* and proceeds — the escape is silent. While the honest trust model is "the user runs this locally," the slice spends two whole layers specifically to contain untrusted generated code, and advertises that containment; a trivial bypass that yields RCE/file-write is a Blocker against the slice's own stated contract.

**Fix path:** The Name-only block-list cannot contain an attribute-graph pivot — defense must move to the worker's runtime, where the object graph is real:
1. Primary: stop injecting the full `cadquery` module. The script needs `cq.Workplane`, `cq.Workplane(...).box(...)`, etc. — a constructive geometry API, not `cq.exporters`. Either (a) inject a thin facade exposing only the geometry-builder surface (Workplane, Solid, Sketch, Assembly-construction, selectors, etc.) and NOT `exporters`/`os`/`tempfile`, or (b) keep the worker doing the export (it already does) and never expose `exporters` to the script namespace at all. Even a facade must be audited for transitive module attributes (e.g. does `Workplane` reach a module via `.__module__`? — that's a dunder, blocked at sanitizer, but verify the runtime facade too).
2. Secondary (defense in depth, since cadquery objects may still transitively reference modules): run the worker under an OS-level sandbox where file/network/process syscalls are denied (e.g. a restricted working dir + no-network + seccomp/Job-object/AppContainer per platform), so even a runtime pivot cannot do harm. This is the only durable boundary against a library as large as OCCT.
3. Extend the sanitizer to also reject *attribute* access whose `.attr` is in a module-name block-list (`os`, `sys`, `subprocess`, `tempfile`, `system`, `popen`, `environ`, …) — cheap, helps re-prompt quality, but treat it as belt-and-suspenders only; it is NOT sufficient alone (an attacker can reach `os` as `getattr`-free chains or via differently-named attributes).
4. Add the regression test in FINDING-004 so this exact payload is proven blocked.

**Blast radius:**
- *Adjacent code:* Any future caller of `render_cadquery` inherits the hole. The OpenSCAD path is unaffected (different sandbox model). The escape is specific to the Python-exec backend.
- *Shared state:* The worker runs with the full privileges of whatever interpreter `find_cadquery_interpreter` returns (here the user's system Python) — full user-level filesystem/network/process access on escape.
- *User-facing change:* None visible — that's the danger; the malicious render returns `ok: true`.
- *Migration concern:* If the namespace-facade approach is taken, confirm real generated geometry still renders (box/hole/sphere/extrude/loft/selectors) — narrowing the namespace could break legitimate scripts that use `cq.exporters` deliberately (they shouldn't — the worker exports — but verify the codegen prompt never instructs the model to call `cq.exporters`).
- *Tests to update:* `tests/test_cadquery_runner.py` — the lone defense-in-depth test (`:151`) covers only `open`; add the `cq.exporters.os` vector and assert both `sanitize_cadquery` blocks it AND the worker refuses it / writes nothing.

### FINDING-002 — Critical (Correctness): `os.system`/native-library writes to fd 1 corrupt the JSON result contract; `redirect_stdout` does not contain them
**Dimension:** Correctness & Runtime
**Evidence:** `cadquery_worker.py:114` uses `contextlib.redirect_stdout(io.StringIO())`, which rebinds the *Python-level* `sys.stdout` only. A subprocess or C-extension that writes to OS file descriptor 1 bypasses it. Reproduced: a script doing `cq.exporters.os.system('echo CORRUPTION_BEFORE_JSON')` produced worker stdout `'CORRUPTION_BEFORE_JSON\n{"ok": true, ...}'`; `_parse_worker_output` (`cadquery_runner.py:235-246`) then did `json.loads` on the whole blob, failed, and returned `{"ok": False, "kind": "exec", "error": "cadquery worker crashed: ..."}` — a valid render reported as a crash.
**Why it matters:** Two ways this bites in normal operation, independent of the security escape: (1) OCCT/OCP is a large C++ library that can and does print warnings/progress to native stderr/stdout under some conditions — those would land on fd 1/2 and either corrupt the JSON (fd1) or are at least not contained by the Python-level redirect; a legitimate render then surfaces as a spurious "worker crashed." (2) It also means the worker's stdout framing assumes nothing else ever writes fd1, which the escape (FINDING-001) trivially violates. The contract is "one JSON object on stdout" (`cadquery_worker.py:20`) and it is not robust to that.
**Fix path:** Make the JSON channel robust to noise. Cheapest correct fix: write the result JSON to a *dedicated* channel the script can't pollute — e.g. the worker writes the JSON to a result file path passed in the request, or to fd 3, rather than stdout. If stdout must stay the channel, redirect at the fd level (`os.dup2` a devnull/pipe over fd 1 around `exec`, restoring fd 1 only to emit the final JSON) so native writes are swallowed too. Either way, `_parse_worker_output` should parse only the designated channel, not "whatever ended up on stdout."
**Blast radius:**
- *Adjacent code:* `_parse_worker_output` and the worker's `main()` emit path. The discovery probe (`_PROBE`) writes `sys.executable` to stdout and parses it the same way — fine for the probe (no untrusted code runs there), but the same fd-1 assumption.
- *User-facing change:* Fewer false "worker crashed" failures on chatty native renders; the orchestrator stops re-prompting on what was actually a good model.
- *Tests to update:* Add a worker test that a benign `print()` in the script does not corrupt the result (the redirect handles Python prints today; the gap is fd-level / native writes) — and ideally a test that a script which forces an fd-1 write still yields parseable JSON after the fix.

### FINDING-003 — Major (Tests): Security tests cover the happy-path-of-failure for one vector only; the real escape class is untested
**Dimension:** Tests
**Evidence:** `tests/test_cadquery_runner.py` has good *sanitizer* negatives (`os` import `:48`, `subprocess` from-import `:54`, `open` name `:60`, dunder `:66`, syntax error `:79`, dedupe `:85`) and exactly one *worker-runtime* negative: `test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed` (`:151-173`), which only proves `open` is absent from `_safe_builtins`. There is no test for the attribute-graph pivot (`cq.exporters.os`), no test that an attribute named after a banned module (`x.os`, `x.system`) is handled, and no test that the worker refuses a script that reaches a module through the injected `cq`. A security feature whose only runtime negative is the easiest-to-block vector gives false confidence — the suite is green (16/16, confirmed) while the sandbox is wide open.
**Why it matters:** Per the standing rule, a security feature with only happy-path coverage is at least a Major. Here the gap directly hid FINDING-001: the existing tests would never have caught the `cq.exporters.os` escape, and indeed don't.
**Fix path:** Add, at minimum: (1) a sanitizer test asserting the `cq.exporters.os.system(...)` payload is blocked once the fix lands; (2) a live worker test (gated like the others) that runs the pivot payload and asserts `ok is False` AND no file was written AND no command ran (e.g. assert a sentinel file the payload would create does not exist — mirror the `pwned.txt` pattern at `:173`); (3) a worker test for the fd-1 corruption case (FINDING-002). Tests should encode the *escape class* (attribute-graph reach to a module), not just one banned builtin.

### FINDING-004 — Minor (Correctness): Partial STL left on disk when STEP export fails after STL succeeds
**Dimension:** Correctness
**Evidence:** In the worker (`cadquery_worker.py:138-148`), STL is exported first, then STEP; if STEP raises, the worker returns `{"ok": False, "kind": "export"}` but the STL file already exists. In `render_cadquery` (`cadquery_runner.py:160-168`), a non-ok result raises `RenderFailed` *without* unlinking the STL (the unlink only happens on the oversize branch, `:173-177` — confirmed: `!ok` branch has no `unlink`). So a partial STL remains in `out_dir`.
**Why it matters:** Low impact because each render targets an isolated, caller-owned `out_dir`, so the stale STL doesn't corrupt a retry (fresh dir / overwrite). But a caller that inspects `out_dir` after a failure could mistake the orphaned STL for a success, and it's inconsistent with the oversize path which does clean up.
**Fix path:** On a non-ok worker result in `render_cadquery`, unlink `stl_path` and `step_path` (both `missing_ok=True`) before raising, mirroring the oversize branch. Cheap and makes failure atomic.

### FINDING-005 — Minor (Correctness): `global`/`nonlocal` statement names are not scanned by the sanitizer
**Dimension:** Correctness & Security
**Evidence:** `ast.Global`/`ast.Nonlocal` store identifiers as raw strings (`node.names`), not `ast.Name` nodes, so `def f():\n global os` is not flagged (confirmed: `sanitize_cadquery` returns no block for it).
**Why it matters:** Benign *today* — there is no `os` in the worker namespace to bind to, so `global os` does nothing exploitable on its own. But it's a coverage hole in a block-list the slice presents as comprehensive, and it compounds with any future change that puts a module in scope. Worth closing while the sanitizer is being revised for FINDING-001.
**Fix path:** In the AST walk, also check `ast.Global`/`ast.Nonlocal` names against `_BANNED_NAMES` and the `__`-dunder rule.

### FINDING-006 — Nit (Runtime): Discovery probe worst case is up to ~7 × 60s of wall-clock if a candidate interpreter hangs on `import cadquery`
**Dimension:** Runtime
**Evidence:** `find_cadquery_interpreter` (`cadquery_runner.py:198-232`) runs up to ~7 probes (candidates + `py -3.13/3.12/3.11` + `python3.13/3.12/3.11/python3`), each with `timeout=60`. Measured cost when cadquery is present: ~4s (a full interpreter startup per failed import). The 60s ceiling only bites if a real interpreter *hangs* importing cadquery (e.g. a broken OCCT DLL load) — uncommon but possible, and it would be 60s per such candidate, serially.
**Why it matters:** Minor latency/UX risk on a misconfigured box; the function correctly never raises and degrades to "backend unavailable," which is the right posture. Calling it out as a watch item, not a defect — but the per-candidate 60s is generous for a probe that's just `import cadquery; print(sys.executable)`.
**Fix path:** Drop the probe timeout to ~10-15s (an import that hasn't finished by then is hung), and consider caching the discovered interpreter so the ~4s cost isn't paid per render. Optional.

## What's working
- **Out-of-process architecture is the right call and cleanly executed.** Running cadquery on a foreign ≤3.13 interpreter, stdlib+cadquery only, never importing `kimcad` (`cadquery_worker.py:7-8,37-48`) — verified it imports and runs standalone under `py -3.13`. This mirrors the established OpenSCAD/OrcaSlicer arm's-length pattern faithfully.
- **Worker-crash handling is genuinely robust.** `_parse_worker_output` (`cadquery_runner.py:235-246`) cleanly synthesizes a failure dict for: empty stdout, junk/non-JSON stdout, a segfault (non-zero exit, no JSON), and a valid-JSON-but-wrong-type (`[1,2]`) result. Tested all four — all return a clean `ok: False` instead of throwing. Good.
- **Degenerate/empty-result detection** (`cadquery_worker.py:127-136`): measuring the bbox before export and rejecting `min(bbox) <= 0` turns a silent broken-mesh into a clear re-promptable error. Covered by a live test (`:134`).
- **Sanitizer Name-node coverage is thorough across expression contexts** — walrus, lambda default, comprehension, f-string interpolation, decorator, and annotation all correctly catch a banned Name (verified live). The token/AST approach correctly avoids false positives on banned words inside string literals (`:73`, verified).
- **The `RenderResult` change is genuinely backward-compatible.** `backend: str = "openscad"` and `step_path: Path | None = None` (`openscad_runner.py:98-103`) are defaulted trailing fields; all existing constructors use kwargs (`openscad_runner.py:297`, `conftest.py:150`, `test_pipeline.py:29`, `test_webapp.py:1600`). Grep confirmed the `.backend` references in `bakeoff.py`/`llm_provider.py` are a *different* `backend` attribute (LLM run/provider objects), so no collision. Blast radius of this change is clean.
- **Test suite runs and passes** (16/16 in the 3.14 venv; the 6 live tests actually executed against system 3.13 + cadquery 2.7.0 — discovery works cross-interpreter from inside the 3.14 venv via `py -3.13`).
- **Timeout and oversize-guard paths are correct** (`cadquery_runner.py:156-157,170-177`); oversize cleans up both STL and STEP. The oversize live test passes.

## Watch items
- The codegen prompt (out of scope here) must never instruct the model to call `cq.exporters.*` — the worker owns all export. Verify when the prompt slice lands, and once FINDING-001's namespace facade is in, confirm legitimate geometry still renders.
- OCCT is a very large native dependency; even after closing the `cq.exporters` pivot, treat the worker as potentially-compromisable and pursue the OS-level sandbox (FINDING-001 fix #2) as the durable boundary.

## Escalation recommendation
**Recommend running `audit-team`** — and specifically a security-focused pass on the CadQuery backend before this slice merges. Trigger met two ways: (1) a Blocker was found, and (2) the root cause is not local — it's a design choice (inject the whole `cadquery` module into an exec namespace and rely on a Name-based block-list) whose only durable fix is architectural (namespace facade + OS-level sandbox). The fix touches the worker's namespace construction, the sanitizer, and the test strategy together; a full review will catch transitive-pivot variants this single pass may not have exhausted (I confirmed `os`/`tempfile` via `exporters`; a deeper enumeration of the OCP/OCCT object graph for other module references is warranted before declaring the namespace clean).
