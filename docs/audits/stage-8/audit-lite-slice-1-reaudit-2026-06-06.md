# Audit Lite (RE-AUDIT) — Stage 8 Slice 1: CadQuery sandbox fix verification

**Date:** 2026-06-06
**Scope:** Verification re-audit of the fixes applied to the six findings from `audit-lite-slice-1-2026-06-06.md`, on branch `stage-8-cadquery` (working tree). Files re-read in full: `src/kimcad/cadquery_worker.py`, `src/kimcad/cadquery_runner.py`, the `RenderResult` change in `src/kimcad/openscad_runner.py`, and `tests/test_cadquery_runner.py`. Goal: confirm each fix closes its finding, hunt for any remaining sandbox escape, and check the fixes introduced nothing new.
**Reviewer:** Claude (audit-lite), genuinely independent and adversarial — ran the real worker subprocess against the system `py -3.13` + cadquery 2.7.0, both through the full `render_cadquery` pipeline and bypassing the sanitizer to test the worker layer in isolation.

## TL;DR
**Ship — with one documentation/test-claim correction strongly recommended first (not a release blocker).** The original Blocker (FINDING-001) is closed *as shipped*: the module-pivot escape (`cq.exporters.os.system(...)`) is dead — the geometry-only facade has no `exporters` to pivot from, and the static sanitizer independently blocks the attribute name. FINDING-002 through -006 are all genuinely closed and verified by reproduction. The full suite is green (796 passed, 0 fail; all 21 Slice-1 tests incl. live ones pass; ruff clean). **However**, the re-audit found that the worker's *second layer* is not as independent as the code's own docstrings and two of its tests assert: bypassing the static sanitizer, a script can still reach the real `os` through a cadquery function's `__globals__` (`cq.version.__globals__["__builtins__"]["__import__"]("os")`). This is **not reachable in the shipped product** because the static sanitizer blocks every `__dunder__`, so the only effective barrier in front of it holds — but the "defence in depth / worker holds even if the sanitizer is bypassed" claim is overstated, and three small sanitizer gaps (string-literal dunder subscripts, non-dunder frame attributes, `str.format` attribute pivots) mean the single effective barrier is more load-bearing than the design intends. That is a Major (security-claim integrity + fragility), not a Blocker, because no end-to-end escape exists in the shipped composition.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1  (new — worker layer is not independently sound; sanitizer is the sole effective barrier and has scannable gaps)
- Minor: 0
- Nit: 1  (new — CadQuery failures surface with the wrong engine name "openscad exited …")

Prior findings: **6/6 CLOSED.**

---

## Per-finding verdict (the six prior findings)

### FINDING-001 (BLOCKER → CLOSED, as shipped)
**Module-pivot escape via `cq.exporters.os` — verified dead at both layers.**

Evidence (ran live against `py -3.13` + cadquery 2.7.0, worker invoked directly, sanitizer bypassed):
- `cq.exporters.os.system("cmd /c echo x > MARKER")` → `{"ok": false, "kind": "exec", "error": "AttributeError: 'types.SimpleNamespace' object has no attribute 'exporters'"}`, **no marker written.**
- `cq.exporters.assembly.os.system(...)` → same AttributeError, no marker.
- `cq.exporters.tempfile.mkdtemp()` → same AttributeError, no marker.
- Facade contents confirmed (`_build_facade`, `cadquery_worker.py:52-64`): exposes exactly the 29 geometry classes/functions (`Workplane`, `Sketch`, `Assembly`, `Solid`, `Vector`, `version`, `sortWiresByBuildOrder`, …) and **zero `types.ModuleType` values** — `exporters`/`importers`/`occ_impl`/`selectors` are all gone. A BFS of the facade's non-dunder attribute graph to **depth 5** reached exactly one module — `math` (intentionally injected) — and **zero** path to `os`/`subprocess`/`builtins`/`io`/`sys`/etc.
- Static sanitizer (`sanitize_cadquery`, `cadquery_runner.py:112-116`) now flags `ast.Attribute` whose `.attr` is in `_BANNED_NAMES`/`_BANNED_ATTRS` or contains `__`, so `cq.exporters.os.system(...)` is blocked at layer 1 with `attribute access '.os'` / `.system` before it ever reaches the worker. Verified: end-to-end through `render_cadquery`, the payload raises `BlockedCodeError`.

The fix is structurally correct: removing the module objects from the namespace removes the capability, which is the right defense (vs. the original Name-only block-list that couldn't see attribute pivots). **Closed.**

> Caveat that drives NEW-FINDING-007 below: "closed as shipped" depends on the static sanitizer remaining in front. The worker layer *alone* does not block all module pivots — see NEW-FINDING-007. This does not reopen 001 (the shipped composition blocks it), but it qualifies the "two independent layers" framing.

### FINDING-002 (CRITICAL → CLOSED)
**Native fd-1 writes can no longer corrupt the result — result is on a dedicated file.**

Evidence:
- The worker writes the JSON to `result_path` via `_emit` (`cadquery_worker.py:179-190`), never stdout (stdout fallback only if no `result_path` was supplied — a malformed request). The runner reads it via `_read_worker_result` (`cadquery_runner.py:264-276`), which parses *only* the result file.
- Reproduced: a successful box render leaves **`stdout == ''`** and a valid `{"ok": true}` in the result file (matches the shipped test `test_worker_writes_result_to_file_not_stdout`, `tests/test_cadquery_runner.py:218-241`). A garbage write to Python stdout in the script no longer reaches the contract channel.
- Crash fallback verified directly: `_read_worker_result(<missing file>, fake_proc)` with `stderr="boom segfault"` returns `{"ok": False, "kind": "exec", "error": "cadquery worker crashed: boom segfault"}` — no exception raised. The decoupling is complete and the missing-file path is handled. **Closed.**

### FINDING-003 (MAJOR → CLOSED)
**Test coverage now exercises the escape class, not just `open`.**

Evidence (`tests/test_cadquery_runner.py`):
- Static negatives for the escape class: `test_attribute_pivot_to_os_is_blocked` (`:73`), `test_banned_method_attr_is_blocked` (`:82`), `test_global_statement_names_are_scanned` (`:88`), plus the prior import/name/dunder/syntax/dedupe tests.
- Live worker-runtime negatives: `test_worker_facade_has_no_module_pivot_to_os` (`:205`) runs the `cq.exporters.os.system` payload directly against the worker and asserts `ok is False` AND no marker file — i.e. it encodes the *attribute-graph-to-module* escape class, which the original suite never did. `test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed` (`:194`) and `test_worker_writes_result_to_file_not_stdout` (`:218`) round it out.
- All 21 tests pass; the 6+ live tests executed against real 3.13 + cadquery (not skipped). **Closed.**

> The coverage closes the *known* vector. It does NOT cover the `__globals__` worker-layer pivot in NEW-FINDING-007 (and that test, if added, would currently FAIL at the worker layer) — see below.

### FINDING-004 (MINOR → CLOSED)
**Partial outputs are cleaned up on every failure branch.**

Evidence: `render_cadquery` defines `_cleanup_outputs()` (`cadquery_runner.py:161-164`, unlinks STL + STEP with `missing_ok=True`) and calls it on the timeout branch (`:184`), the `!ok` branch (`:190`), and the oversize branch (`:203`). Reproduced:
- Oversize (`max_output_bytes=10`, `emit_step=True`) → `OversizeOutput` raised, **`b.stl` and `b.step` both absent** afterward.
- Degenerate result (`emit_step=True`) → `RenderFailed` raised, **no STL or STEP left behind.**
The original gap (STL orphaned on a non-ok result) is closed. **Closed.**

### FINDING-005 (MINOR → CLOSED)
**`global`/`nonlocal` names are scanned.**

Evidence: `sanitize_cadquery` handles `ast.Global`/`ast.Nonlocal` (`cadquery_runner.py:117-121`), checking each name against `_BANNED_NAMES` and the `__` rule. Verified live: `def f():\n  global os\n  os=1` → blocked (`use of 'os' is not allowed`). Test `test_global_statement_names_are_scanned` (`:88`) covers it. **Closed.**

### FINDING-006 (NIT → CLOSED)
**Probe timeout reduced to 20s/candidate.**

Evidence: `find_cadquery_interpreter` uses `timeout=20` (`cadquery_runner.py:251-253`), down from 60, with an inline comment noting the Config layer caches the discovered result. Worst-case serial wall-clock on a hung candidate is now bounded at 20s/candidate instead of 60s. **Closed.**

---

## NEW findings introduced or surfaced by the fixes

### NEW-FINDING-007 — Major (Correctness & Security): the worker's "second layer" is not independently sound; the static sanitizer is the *sole* effective barrier, and it has three scannable gaps
**Dimension:** Correctness & Security
**Evidence:** Ran adversarial payloads **directly against the worker subprocess, bypassing `sanitize_cadquery`** (exactly the threat model the worker docstring and two tests claim to defend — `cadquery_worker.py:23-38` "restricted builtins are the second layer … even if the static sanitizer were bypassed"; `tests/test_cadquery_runner.py:194,205`).

1. **Worker-layer escape via `__globals__` (reproduced, marker written):**
   ```python
   osmod = cq.version.__globals__["__builtins__"]["__import__"]("os")
   osmod.system(r"cmd /c echo x > MARKER")
   result = cq.Workplane().box(1,1,1)
   ```
   Direct-to-worker result: `{"ok": true, ...}` and **the marker file was written** — i.e. arbitrary command execution at the worker layer. Root cause: every cadquery function/method on the facade (`cq.version`, `cq.sortWiresByBuildOrder`, and 993 non-dunder class methods like `Plane.named`, `Workplane.box`) carries its original `__globals__`, whose `__builtins__` is the **real, unrestricted** builtins dict (confirmed: it has the real `__import__`, `open`, `eval`). The worker's `_safe_builtins` only governs the *script's* namespace and frames created *inside* the sandboxed `exec`; it does nothing to the home globals of injected library functions. So the geometry-only facade removes the *module-attribute* pivot (FINDING-001) but not the *function-globals* pivot.

2. **Why this is NOT a shipped escape (and so not a Blocker):** every payload that reaches it uses a `__dunder__` attribute (`__globals__`, `__builtins__`/`__class__`/`__subclasses__`), and the static sanitizer blocks **all** `__`-containing names and attributes (`cadquery_runner.py:108-109,113-114`). Verified end-to-end: through `render_cadquery`, the `__globals__` payload raises `BlockedCodeError: dunder access '__globals__' is not allowed`. The shipped composition (sanitizer → worker) blocks it. The problem is that the worker — advertised and unit-tested as an independent second layer — is **not** one for this class; the whole defense rests on the sanitizer's dunder rule.

3. **Three sanitizer gaps that make the sole barrier fragile (each PASSES the sanitizer today):**
   - **String-literal dunder subscript:** `obj.f_builtins["__import__"]` — the AST walk only inspects `ast.Name`/`ast.Attribute`/`ast.Global`/`ast.Nonlocal`; it never scans `ast.Constant` string values, so a dunder hidden as a dict key string is invisible.
   - **Non-dunder frame attributes:** `gen.gi_frame.f_builtins` / `.f_globals` / `.f_back` — `gi_frame`, `f_builtins`, `f_globals`, `f_back`, `gi_code`, `cr_frame` are all *non-dunder* attribute names that reach a frame and its builtins. The sanitizer passes them.
   - **`str.format` attribute pivot:** `"{0.gi_frame}".format(obj)` — `str.format` performs attribute/getitem access at *runtime* from inside a benign-looking string; the AST sees only a string constant and a `.format` call.

   I confirmed each of the three passes `sanitize_cadquery` (returns `safe=True`).

**Why it isn't already exploitable through these gaps (I tried hard):** to weaponize the frame/format gaps you must reach a frame or function whose builtins are the *real* ones. Frames created inside the sandboxed `exec` (e.g. a genexpr defined in the script) inherit the **restricted** builtins — verified: `gen.gi_frame.f_builtins["__import__"]("os")` from a sandbox-created generator returns the restricted importer and is refused (`ImportError: import of 'os' is not allowed`), and `f_builtins["open"]` raises `KeyError`. The only objects carrying real builtins are cadquery's own functions/methods, and the sole non-dunder way to reach *their* globals/frame is via `__globals__`/`__class__` — both dunders, both sanitizer-blocked. A depth-4 BFS of the facade's non-dunder attribute graph found **zero** reachable frame/generator/code objects. So today the gaps are not chainable into an escape. But that safety is incidental: it depends on no facade object ever exposing a real-builtins-bearing frame/function through a non-dunder attribute, across all of cadquery + OCP — a property nobody is testing and that a cadquery version bump could silently break.

**Why it matters:** (1) Security-claim integrity: the worker docstring (`cadquery_worker.py:23-38`) and tests `test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed` / `test_worker_facade_has_no_module_pivot_to_os` assert an independent worker layer that, for the `__globals__` class, does not exist — those tests pass only because they happen to use `open`/`exporters` rather than `__globals__`. A reader trusts "defence in depth" that is actually single-layer for this class. (2) Fragility: the entire CadQuery sandbox now hinges on one rule (sanitizer blocks `__`), and that rule has three documented blind spots; any future relaxation, or a cadquery object that surfaces a real-builtins frame via a non-dunder attribute, turns a blind spot into an escape.

**Fix path:**
1. Make the second layer real (cheap, high-value): in the worker, after `exec`, the script's frames already get restricted builtins — extend that to the *injected facade* by not handing the script live cadquery functions whose `__globals__` are hot. Practical option: run the `exec` with the restricted builtins (already done) **and** drop the worker's own access by additionally validating, or accept that the worker is best hardened by an OS-level sandbox (the original FINDING-001 fix #2 — restricted working dir + no-network + Job-object/AppContainer/seccomp). The durable boundary against a library as large as OCCT is OS-level confinement, not namespace surgery.
2. Close the three sanitizer gaps so the front barrier is tight: (a) scan `ast.Constant` string values for `__`-dunders and banned tokens used as subscripts/format fields; (b) add the frame-introspection attribute names (`gi_frame`, `f_builtins`, `f_globals`, `f_back`, `f_locals`, `gi_code`, `cr_frame`, `cr_await`, `ag_frame`) to `_BANNED_ATTRS`; (c) treat `.format`/`.format_map` on a literal containing `{...!...}`/attribute access as suspect, or simpler — block `format`/`format_map` as attrs (they're never needed in geometry code) and rely on f-strings, which the AST does see.
3. Fix the two tests' claims: rename/rescope `test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed` to state honestly that the worker blocks *builtin-name* escapes (no `open` in the restricted map) — and add a worker-layer test for the `__globals__` pivot that asserts the *current* behavior, marked `xfail` with a comment, OR (preferred) only after fix #1 lands, asserts it's blocked. Do not leave a green test implying the worker independently blocks what it doesn't.
4. Add a sanitizer regression test for each of the three gap payloads.

**Blast radius:**
- *Adjacent code:* `sanitize_cadquery` (the one barrier) and `cadquery_worker.py`'s namespace/exec construction. The OpenSCAD path is unaffected.
- *Shared state:* On escape, the worker runs at the full privilege of the discovered system interpreter — full user-level FS/network/process access. Same exposure as the original Blocker, just reached through a dunder the sanitizer currently catches.
- *User-facing change:* None if fixes are sanitizer-side (valid geometry never uses dunders or `format`-pivots). If OS-sandboxing the worker, verify legitimate renders still write STL/STEP under the restricted working dir.
- *Migration concern:* None for the sanitizer tightening. OS-level sandbox is a larger, platform-specific effort — track separately.
- *Tests to update:* the two worker tests named above; add the three gap regressions and a worker `__globals__` test.

### NEW-FINDING-008 — Nit (UX / Correctness): CadQuery worker failures surface to the user/logs as "openscad exited …"
**Dimension:** Correctness & UX
**Evidence:** `render_cadquery` raises `RenderFailed(proc.returncode, error)` (`cadquery_runner.py:197`), and `RenderFailed.__str__` hardcodes the OpenSCAD engine name (`openscad_runner.py:70`: `f"openscad exited {returncode}: …"`). Reproduced: a degenerate CadQuery result surfaces as `RenderFailed: openscad exited 0: result has no measurable solid: 'Vector' …` — wrong engine, and `exited 0` is misleading (the worker exited 0; the failure is logical, carried in the result file). This is a pre-existing exception reused by the new backend, surfaced by the CadQuery path.
**Why it matters:** Operator/log confusion when triaging CadQuery failures and re-prompts; the message attributes a CadQuery modelling error to OpenSCAD. Cosmetic — no functional impact.
**Fix path:** Give `RenderFailed` a backend/engine label (default "openscad" for back-compat) and pass `"cadquery"` from `render_cadquery`, or raise a small `RenderFailed` subclass; drop the misleading `exited {returncode}` when the code is 0 and the error is logical. One-line message change.

---

## What's working (verified this pass)
- **The Blocker fix is structurally right.** Removing module objects from the namespace removes the capability — the correct defense, replacing the original un-winnable Name-only block-list. Facade contents and the depth-5 BFS both confirm no module reachable but `math`.
- **Result-to-file decoupling (FINDING-002) is clean and complete** — stdout is empty on success, the contract lives in `result_path`, and the missing-file crash path synthesizes a clean failure without raising. This is the most important robustness fix and it's well done.
- **Failure atomicity (FINDING-004)** — `_cleanup_outputs()` on all three failure branches, verified by reproduction (oversize + degenerate both leave nothing behind).
- **Sanitizer breadth genuinely improved** — attribute-name blocking, `_BANNED_ATTRS` for OS/exec method names, and `global`/`nonlocal` scanning all verified live; the dunder rule (the actual load-bearing barrier) correctly catches `__class__`/`__globals__`/`__subclasses__`/`__builtins__` end-to-end.
- **No regressions.** Full non-live suite: **796 passed, 12 deselected** (131s). Slice-1 suite: **21 passed** incl. live tests against real 3.13 + cadquery 2.7.0. **ruff clean** on both new files.
- **`RenderResult` change remains backward-compatible** — `backend`/`step_path` are defaulted trailing fields (`openscad_runner.py:97-103`); the broad suite passing confirms no constructor breakage.

## Watch items
- The whole CadQuery sandbox now rests on a single effective barrier (the sanitizer's dunder rule) with three known blind spots; an OS-level worker sandbox is the durable fix and should be tracked even though no escape is reachable today.
- A cadquery version bump could change the facade's object graph; the depth-5 "no reachable real-builtins frame" property is not pinned by any test and could silently regress.

## Escalation recommendation
**No escalation to audit-team required for shipping this slice.** The Blocker and the four lesser findings are genuinely closed, no end-to-end escape exists in the shipped composition, and the suite is green. NEW-FINDING-007 is a Major about *defense-in-depth integrity and fragility*, not a live exploit — it should be fixed (sanitizer-gap closures are cheap; the OS-sandbox is a tracked follow-up), and the two over-claiming worker tests should be corrected so the suite stops asserting an independence the worker doesn't have. If the team wants the durable OS-level worker confinement designed and the full OCP/OCCT object graph enumerated for non-dunder real-builtins reachability, that specific hardening is worth a focused security pass — but it's a Stage-8 hardening task, not a gate on this slice.

## Ship / no-ship
**SHIP** the Slice-1 fixes (FINDING-001…006 are closed; no regressions). **Before merge, strongly recommend** the two cheap, in-scope corrections from NEW-FINDING-007: (a) close the three sanitizer string/frame/format gaps, and (b) fix the two worker tests + docstring so they don't claim an independent second layer the worker doesn't provide for the `__globals__` class. Those keep the sole effective barrier tight and the security claims honest. NEW-FINDING-008 (wrong engine name in errors) is a one-line nit, fix at leisure. Track OS-level worker sandboxing as the durable Stage-8 security follow-up.
