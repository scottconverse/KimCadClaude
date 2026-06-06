# Test Suite Deep-Dive — KimCad Stage 8 (CadQuery parallel backend)

**Audit date:** 2026-06-06
**Role:** Test Engineer
**Scope audited:** the Stage 8 test coverage for the CadQuery parallel geometry backend —
`tests/test_cadquery_runner.py`, `tests/test_config.py` (CadQuery sections),
`tests/test_pipeline_backends.py`, `tests/test_webapp.py` (STEP sections),
`tests/test_cadquery_bench.py`, and the autouse hermeticity fixture in `tests/conftest.py`.
Cross-read the production code under test (`cadquery_runner.py`, `cadquery_worker.py`,
`pipeline.py`, `config.py`, `openscad_runner.py`, `webapp.py`, `llm_provider.py`).
Framework: pytest. Coverage tool: none configured (no coverage number is claimed).
**Auditor posture:** Balanced

---

## TL;DR

The Stage 8 security tests are genuinely strong where it counts: the static sanitizer's
escape-class tests are real tripwires (hand-mutation confirmed they FAIL when the dunder,
banned-attr, and subscript-key guards are weakened), and the worker-layer defence-in-depth
test catches *real* RCE — when I removed the facade's submodule-stripping, the
`cq.exporters.os.system(...)` pivot actually wrote a file to disk and the worker test went
red. The fallback state machine (no-fallback-on-success, fallback-on-render-fail,
fallback-on-gate-fail, both-fail-keeps-primary, gate-failed-never-sliced on the multi-backend
path) is well-covered with deterministic fakes. The hermeticity fixture is correct and does
NOT mask the gate-failed-not-sliced safety property — the multi-backend twin is present and real.

The one structural risk that rises above hygiene: **the security-critical second layer
(worker restricted-builtins + geometry-only facade) is exercised ONLY by `live` tests, and
there is no release-gate backstop that fails the build when the CadQuery interpreter is
absent** — unlike the OrcaSlicer live tests, which have a `KIMCAD_RELEASE=1` hard gate. On any
gate machine without a `<=3.13 + cadquery` interpreter (hosted CI is exactly this), those RCE
tests skip silently to green. The class of bug that slips through: a regression that re-opens
the worker sandbox would not turn any *mandatory* gate red.

Secondary gaps are the usual error-direction thinness: no test for the worker timeout path, the
worker-crash/missing-result synthesis, `proceed_anyway` on the multi-backend path, or the
`FallbackProvider.generate_cadquery` delegation behavior.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 4 |
| Nit | 2 |

## What's working

- **The sanitizer escape tests are tripwires, not tautologies (mutation-verified).** I made a
  SCRATCH copy and weakened each guard in turn:
  - Disabling the `Attribute` dunder check (`cadquery_runner.py:127`) → `test_dunder_escape_is_blocked`
    (`test_cadquery_runner.py:66`) FAILS. Real catch.
  - Disabling the `Subscript` dunder-key check (`cadquery_runner.py:135`, the NEW-007 escape) →
    `test_dunder_string_subscript_is_blocked` (`:96`) FAILS. Real catch.
  - Emptying the banned-attr branch (`cadquery_runner.py:129`) → three tests FAIL at once:
    `test_attribute_pivot_to_os_is_blocked` (`:73`, the Slice-1 Blocker class),
    `test_banned_method_attr_is_blocked` (`:82`), `test_str_format_field_pivot_is_blocked` (`:110`).
  All guards restored; `git diff` against HEAD is clean.
- **The worker-layer test catches real RCE.** Weakening `_build_facade` so it no longer strips
  submodules (`cadquery_worker.py:75`) made `test_worker_facade_has_no_module_pivot_to_os`
  (`test_cadquery_runner.py:231`) FAIL — and I confirmed independently that under the weakened
  facade the worker actually *executed* `os.system` and wrote a marker file to disk (verified by
  hand, then restored). This is genuine defence-in-depth coverage, honestly bypassing the static
  sanitizer (`_run_worker_directly`, `:196`) to test the worker's own teeth.
- **The fallback state machine is deterministic and complete on the happy/failure axes.**
  `test_pipeline_backends.py` covers: OpenSCAD success → no fallback + `cadquery_calls == 0`
  (`:68`); render-fail → fallback (`:81`); gate-fail → fallback (`:95`); unavailable → no
  fallback (`:107`); both-fail → keep primary on the tie (`:122`); STEP path present/absent
  (`:154`,`:166`). Each fake renderer tags its `RenderResult.backend`, so the assertions verify
  the *winning backend*, not just "something rendered."
- **The gate-failed-never-sliced safety property has a real multi-backend twin.**
  `test_gate_failed_part_is_not_sliced_on_the_multi_backend_path` (`:135`) injects a slicer that
  raises `AssertionError` if called, with BOTH backends gate-failing and `confirm_print=True`.
  This is the test the hermeticity fixture's docstring promises (FINDING-002) and it is real.
- **The hermeticity fixture is correct and effective.** I verified that patching
  `cadquery_runner.find_cadquery_interpreter` propagates through `config.cadquery_interpreter()`
  (config re-imports the symbol lazily at call time, `config.py:166`), so the autouse fixture
  (`conftest.py:84`) genuinely forces the backend off for non-live tests via the production
  config path — it does not merely stub a value the pipeline ignores.
- **Config discovery semantics are pinned precisely.** `test_config.py:100-164` distinguishes
  `false`/`""` (force off, no probe — asserts the probe is NOT called), explicit path
  (authoritative, `include_defaults=False`), `null` (auto-probe, `include_defaults=True`), and
  the probe-once cache (`:153`). These assert the *arguments passed to the probe*, not just the
  return — strong.
- **Clean shortcut census.** Every `skipif` is legitimate live-gating with a clear reason; no
  `.only`, no `xfail`, no `TODO: add test`, no `assert True` placeholders.

## What couldn't be assessed

- **CI history / flakiness over time.** No access to Actions run history; flakiness assessed by
  reading (no wall-clock/network/shared-state dependence found in the Stage 8 tests).
- **The live-model "union lifts the pass rate" claim.** By design the deterministic bench
  (`test_cadquery_bench.py`) proves only the *engine*; the higher-level union claim needs a live
  model bench (documented as out of scope in `cadquery_bench.py:9`). Not a gap — correctly scoped.
- **Cross-platform interpreter discovery.** `find_cadquery_interpreter`'s `py -3.13` launcher
  branch (`cadquery_runner.py:271`) is Windows-only and only exercised live; the `python3.x`
  PATH branch has no unit test with a fake PATH.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (+ trimesh for real geometry in fakes) |
| Test pyramid shape | Heavy unit (pure sanitizer + config), solid integration (pipeline fallback with fakes, webapp over a real socket), thin live e2e (worker/bench, gated by interpreter presence) |
| Coverage tool | none configured; no coverage % claimed (honest) |
| Reported coverage | n/a |
| Flakiness posture | Clean — no retries config, no sleeps, deterministic fakes; live tests bounded by timeouts |
| CI blocking? | Hosted CI runs `pytest -m "not live"` only (no cadquery) — the security live tests SKIP there. The authoritative local Windows pre-push gate runs the FULL suite, but has no release-gate backstop for an absent CadQuery interpreter (see TEST-001). |

Non-live targeted run: **153 passed, 12 deselected (62s)**. Live Stage 8 subset on this machine
(a Python-3.13 cadquery interpreter IS present): **11 passed, 42 deselected (68s)**.

---

## Findings

> **Finding ID prefix:** `TEST-`
> **Categories:** Coverage / Shortcut / Flakiness / Quality / Ergonomics / Mocking / Regression / CI

### [TEST-001] — Major — CI — The worker-sandbox RCE tests are live-only with no release-gate backstop; they skip to green where it matters

**Evidence**
The only tests that exercise the SECOND security layer (the worker's restricted builtins +
geometry-only facade) are marked `live` and `skipif(_CQ is None)`:
`test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed` (`test_cadquery_runner.py:220`),
`test_worker_facade_has_no_module_pivot_to_os` (`:231`),
`test_worker_writes_result_to_file_not_stdout` (`:244`).
Hosted CI runs `pytest -q -m "not live"` on Python 3.12 with no cadquery installed
(`.github/workflows/ci.yml:34`) — so all three SKIP there. The authoritative local gate runs the
full suite (`scripts/ci.sh:32`, `pytest -q -ra`), but its release-gate hard-fails
(`KIMCAD_RELEASE=1`) exist ONLY for the OrcaSlicer binary (`ci.sh:66`) and the frontend toolchain
(`ci.sh:49`) — there is **no** equivalent guard that fails the gate when the CadQuery interpreter
is absent. On a gate machine without `<=3.13 + cadquery`, these RCE tests skip and the push goes
green.

I confirmed these are the tests that actually catch a sandbox regression: weakening
`_build_facade` (`cadquery_worker.py:75`) so submodules survive let `cq.exporters.os.system(...)`
write a real file to disk, and `test_worker_facade_has_no_module_pivot_to_os` was the test that
went red. With it skipped, that regression ships green.

**Why this matters**
The worker layer is the documented defence-in-depth boundary for untrusted LLM-generated code
(`cadquery_worker.py:23-52`). A future refactor that re-introduces a module object onto the facade,
loosens the restricted builtins, or restores `open` would re-open an RCE path — and on any
interpreter-less gate, *no mandatory test* would turn red. This is the "CI is green because the
tests are skipped" pattern the severity framework calls out, scoped to the security layer.

**Blast radius**
- Test files affected: `test_cadquery_runner.py` (the 3 worker tests), `scripts/ci.sh`,
  `.github/workflows/ci.yml`.
- Shared assumption: the project already encodes "a live tool's absence must hard-fail a release"
  for OrcaSlicer and the frontend — this is the same pattern, missing for CadQuery.
- User-facing: none directly; the risk is a silently-regressed sandbox shipping.
- Migration: none.
- Related findings: TEST-002 (the sanitizer's own coverage is non-live, which mitigates — layer 1
  is the primary guard and IS tested everywhere; this finding is about layer 2's enforcement).

**Fix path**
Add a release-gate backstop mirroring the OrcaSlicer one: in `scripts/ci.sh`, when
`KIMCAD_RELEASE=1` and `find_cadquery_interpreter()` returns None, FAIL with a clear message
("CadQuery worker-sandbox contract unproven this run"). Optionally add cadquery to a dedicated
hosted-CI job (a `<=3.13` matrix entry that `pip install cadquery`) so the worker tests run on at
least one mandatory gate. At minimum, make the absence loud in `ci.sh` like the OrcaSlicer warning.

---

### [TEST-002] — Major — Coverage — The security feature's FAILURE direction is tested for the sanitizer but thin for the worker; the worker's restricted-builtins map and timeout/crash paths have no test

**Evidence**
The sanitizer's failure direction is excellent (see "What's working"). The worker's is partial:
- `_safe_builtins` (`cadquery_worker.py:97`) withholds `eval`/`exec`/`compile`/`getattr`/
  `setattr`/`vars`/`globals`, but only `open` is tested as blocked-at-the-worker
  (`test_cadquery_runner.py:220`). There is no worker-level test that `eval`/`exec`/`getattr`
  is absent — so a regression that accidentally re-added `getattr` to the `allowed` tuple
  (`cadquery_worker.py:102`) would not be caught (the static sanitizer bans the *name* `getattr`,
  but the whole point of the worker layer is to hold even if the sanitizer is bypassed, which is
  exactly the scenario `_run_worker_directly` exists to test).
- `render_cadquery`'s `RenderTimeout` path (`cadquery_runner.py:203-205`) has NO test —
  `grep` for `RenderTimeout`/`TimeoutExpired` across `tests/` finds it only in
  `test_openscad_runner.py` and `test_slicer.py`, never for CadQuery.
- `_read_worker_result`'s crash-synthesis (`cadquery_runner.py:292-304`, the "worker segfaulted /
  missing result file" path) has no test. This is the path that converts a killed/segfaulted OCCT
  worker into a clean `RenderFailed` instead of an unparseable-JSON crash — a realistic failure for
  a C++ geometry kernel on a pathological model, and entirely untested.

**Why this matters**
The worker layer's reason to exist is "hold even if layer 1 is bypassed." Testing only `open` at
that layer means a loosening of the builtins map, or a broken timeout/crash handler, slips through.
The crash path in particular is the difference between a graceful re-prompt and a 500/traceback
when OCCT dies on a hostile model.

**Blast radius**
- Test files affected: `test_cadquery_runner.py`.
- Shared assumption: the worker's restricted-builtins allowlist is load-bearing; only one entry is
  pinned by a test.
- User-facing: a worker timeout or crash currently has no proof it surfaces as a clean error.
- Migration: none.
- Related findings: TEST-001 (same live-only enforcement caveat applies to any new worker test —
  add them and the release-gate backstop together).

**Fix path**
Add live worker tests for: a banned builtin other than `open` (e.g. assert a script using
`eval("1")` fails at the worker); a `RenderTimeout` (monkeypatch `subprocess.run` to raise
`TimeoutExpired`, no interpreter needed — this one can be non-live); and the crash-synthesis path
(delete/corrupt the result file before `_read_worker_result`, non-live with a stubbed
`CompletedProcess`). The timeout + crash tests are pure-Python and belong in the non-live tier so
they run on hosted CI.

---

### [TEST-003] — Minor — Coverage — `FallbackProvider.generate_cadquery` delegation has no behavioral test

**Evidence**
`test_fallback_provider.py` thoroughly tests delegation for `generate_design_plan` and
`generate_openscad` — success-skips-alt (`:74`,`:83`), fallback-on-connection/timeout/404
(`:96`,`:104`,`:112`), sticky-alt (`:140`), thread-local stickiness (`:159`). `generate_cadquery`
(`llm_provider.py:418`, which uses the identical `self._call(...)` machinery) appears in NONE of
them. Its only coverage is the structural presence check
`test_all_real_providers_implement_the_full_contract` (`test_pipeline_backends.py:175`), which
asserts `callable(getattr(cls, "generate_cadquery"))` — that the method *exists*, not that it
delegates or falls back.

**Why this matters**
`generate_cadquery` is the only codegen-path Provider method without a behavioral delegation test,
and it feeds the security-sensitive CadQuery sandbox. Low risk *because* it shares `_call`, but the
contract test is a presence assertion (see TEST-005) — if someone overrode `generate_cadquery` on
a subclass to bypass `_call`, no test would notice the broken fallback.

**Blast radius**
- Test files affected: `test_fallback_provider.py`.
- User-facing: a dead-primary on a CadQuery-fallback codegen would be the unproven path.
- Related findings: TEST-005 (the contract test is structural, not behavioral).

**Fix path**
Add a one-line parametrization of the existing fallback tests to include `generate_cadquery`, or a
single `test_fallback_on_cadquery_delegates_to_alt`.

---

### [TEST-004] — Minor — Coverage — `proceed_anyway` and the WARN gate are untested on the multi-backend path

**Evidence**
`proceed_anyway` is tested in `test_pipeline.py` (`:393`) but only single-backend. On the
multi-backend path, `_build_geometry` passes `gate_retry=not proceed_anyway` (`pipeline.py:499`),
and `_backend_succeeded` returns True for a *rendered* primary when `gate_retry` is False
(`pipeline.py:937-938`) — i.e. with `proceed_anyway=True`, an OpenSCAD render that gate-FAILs is
ACCEPTED and CadQuery is never tried. No test pins this branch. Separately, `_better_result`'s
scoring comment claims "a WARN primary never actually reaches here" (`pipeline.py:953`) — there is
no test asserting a WARN-gate primary is accepted by `_backend_succeeded` (skipping fallback), nor
a case where the fallback produces a WARN.

**Why this matters**
`proceed_anyway` is the "inspect a failed part" escape hatch; whether it correctly short-circuits
the fallback (rather than silently spending a CadQuery codegen call) is a real behavioral contract.
The WARN path is the common "printable with notes" outcome and is asserted only implicitly.

**Blast radius**
- Test files affected: `test_pipeline_backends.py`.
- User-facing: the "proceed anyway" flow could spend an unexpected model call, or change which
  backend's report the user sees, without any test catching the drift.
- Related findings: none.

**Fix path**
Add `test_proceed_anyway_accepts_a_gate_failed_primary_without_fallback` (assert
`provider.cadquery_calls == 0` and `result.backend == "openscad"`), and a WARN-on-primary case
asserting no fallback.

---

### [TEST-005] — Minor — Quality — The "all providers implement the contract" test is structural (presence), not behavioral (signature/return)

**Evidence**
`test_all_real_providers_implement_the_full_contract` (`test_pipeline_backends.py:175`) asserts
`callable(getattr(cls, method, None))`. This catches a *missing* method (the FINDING-001 bug it was
written for) but NOT a method with an incompatible signature, a stub that returns the wrong type, or
one that raises `NotImplementedError`. It also tests the class object, so it can't detect an
instance-level override. `_NoModelProvider` (`template_bench.py:53`) is deliberately excluded.

**Why this matters**
A provider could satisfy this test while having a `generate_cadquery(self)` that ignores its
arguments or returns `None` — the pipeline would then fail at call time, not at the test. The test's
own docstring frames it as guarding a Protocol that is "not runtime-enforced," but a presence check
is a weak enforcement.

**Blast radius**
- Test files affected: `test_pipeline_backends.py`.
- Related findings: TEST-003 (the behavioral gap for one of these methods).

**Fix path**
Strengthen to call each method on an instance with the real argument shape (a `make_plan` plan +
`BAMBU`/`PLA`) and assert the return is a `str`, for the providers that can be constructed cheaply.
At minimum, assert the method's signature accepts `(plan, printer, material, history=...)` via
`inspect.signature`.

---

### [TEST-006] — Minor — Coverage — The interpreter-discovery PATH branch and the `find_cadquery_interpreter` probe-failure handling are only exercised live

**Evidence**
`find_cadquery_interpreter` (`cadquery_runner.py:247`) has rich logic: candidate argv prefixes, the
Windows `py -3.x` launcher, `python3.x` on PATH, probe-success requiring `returncode == 0 AND
out AND path.exists()`, and swallowing `OSError`/`SubprocessError`. The only unit tests
(`test_config.py`) monkeypatch the function wholesale; the function's own internals are covered only
by the single live `test_real_cadquery_interpreter_is_discovered` (`:172`), which on an
interpreter-less machine skips. There's no test that a candidate which prints a *non-existent* path
is rejected, or that a probe raising `OSError` is skipped rather than propagated.

**Why this matters**
The "graceful absence" posture (never raise, just return None) is the contract that keeps the
backend optional. A regression that let a probe exception escape would break every pipeline run on a
machine with a misconfigured `py` launcher — and no non-live test guards it.

**Blast radius**
- Test files affected: `test_config.py` or a new `test_cadquery_runner` non-live section.
- User-facing: a discovery exception would crash a design run instead of disabling the backend.
- Related findings: none.

**Fix path**
Add non-live tests that monkeypatch `subprocess.run` to (a) raise `OSError` → returns None,
(b) return rc=0 with a bogus path → that candidate is skipped, (c) return the first good candidate
→ that path wins. No interpreter needed.

---

### [TEST-007] — Nit — Quality — `test_no_fallback_when_cadquery_unavailable` belt-and-suspenders masks whether the fixture alone suffices

**Evidence**
`test_no_fallback_when_cadquery_unavailable` (`test_pipeline_backends.py:107`) sets
`pipe.config._cadquery_interpreter = None` directly (`:116`) in addition to relying on the autouse
hermeticity fixture. The direct cache-poke short-circuits `cadquery_interpreter()`, so this test
would pass even if the fixture were broken. It's redundant (harmless), but it slightly obscures that
the fixture is what makes the *other* fallback tests deterministic.

**Why this matters (lightly)**
If the fixture regressed, this test wouldn't be the one to catch it — the test reads as if it
proves the fixture works, but it bypasses it.

**Fix path**
Drop the explicit `_cadquery_interpreter = None` line and rely on the fixture (I verified the
fixture alone yields `cadquery_interpreter() == None` through the real config path), OR keep it but
add a comment that it's independent of the fixture.

---

### [TEST-008] — Nit — Quality — The deterministic bench's bbox tolerance (0.5 mm, sorted) is appropriately loose but could let a small wrong-axis-size regression through

**Evidence**
`cadquery_bench.py:32` uses `BBOX_TOLERANCE_MM = 0.5` and `_bbox_matches` (`:86`) compares
**sorted** dims, so an axis permutation passes. This is the right call for curved/filleted
envelopes (tessellation moves a curve a fraction of a mm) and orientation-invariance. But combined,
a part that built 40×30×20 when 40×20×30 was intended would pass (sorted dims identical). The live
`test_render_cadquery_builds_a_box` (`test_cadquery_runner.py:151`) DOES assert exact sorted
`[20,30,40]` with `round()`, so the *runner* has a tight check; the bench is the looser one.

**Why this matters (lightly)**
The bench proves "watertight at roughly the right overall size," not "the right axis assignment."
That's an acceptable scope for an engine-soundness floor, but worth stating so no one reads a green
bench as proving dimensional fidelity.

**Fix path**
None required (the looseness is justified and documented in-code). If axis fidelity is ever a bench
goal, add one case with three distinct axis sizes asserted *unsorted*.

---

## Shortcut census

| Shortcut pattern | Count (Stage 8 files) |
|---|---|
| `.skip` / `xit` / `@skip` (unjustified) | 0 |
| `skipif` (justified live-gating) | 4 (`test_cadquery_runner.py:28`, `test_config.py:173`, `test_cadquery_bench.py:23`, `test_pipeline_backends.py:191`) |
| `.only` (left in) | 0 |
| `TODO: add test` / similar | 0 |
| Empty assertion / placeholder (`assert True`) | 0 |
| `--retry` / retries normalized | no |

Clean. The only skips are interpreter-gated live tests with explicit reasons, plus the
geometry-backends collection gate in `conftest.py:62` (which is honest: `UsageError` → RED on CI,
skip-with-actionable-message locally).

## Blind spots by class

- **Sandbox second-layer regression on an interpreter-less gate** (TEST-001) — the worker RCE tests
  skip to green where the CadQuery interpreter is absent; no mandatory gate proves the worker holds.
- **Worker error directions** (TEST-002) — timeout, crash/segfault-synthesis, and all-but-`open`
  restricted builtins are untested.
- **Backend-selection edge branches** (TEST-004) — `proceed_anyway` multi-backend, WARN-gate
  primary/fallback.
- **Provider contract behavior vs presence** (TEST-003, TEST-005) — `generate_cadquery` delegation,
  and signature/return shape of the whole contract.
- **Discovery internals** (TEST-006) — probe-failure swallowing and the PATH/launcher branches.

## Patterns and systemic observations

- **Honest, well-labeled mocking.** The fakes (`conftest.FakeProvider`, the `_renderer`/
  `box_renderer` factories) write *real* trimesh geometry rather than returning mock meshes, so the
  orient/harden/gate tail runs for real — these are integration tests that actually integrate, not
  unit tests in disguise. The one place mocking is bypassed on purpose (`_run_worker_directly`,
  `test_cadquery_runner.py:196`) is exactly where it should be: to test the worker's own defenses.
- **The two-layer security model is documented AND the division of labor is reflected in the
  tests** — sanitizer tests live in the non-live tier (run everywhere), worker tests in the live
  tier. The gap is purely that the live tier has no enforcement backstop (TEST-001), not that the
  tests are weak.
- **Regression discipline is visible.** Tests are tagged to the findings that motivated them
  (FINDING-001/002/003, NEW-007, SLICE2-002, QA-301, ENG-007), and the worker tests explicitly
  re-prove the Slice-1 audit Blocker is closed. This is good tests-with-fixes culture.
- **No flakiness vectors** in the Stage 8 tests: deterministic fakes, bounded timeouts, no sleeps,
  the autouse `_isolate_kimcad_home` + `_default_cadquery_backend_off` fixtures remove
  machine-dependence. The fixture-driven hermeticity is the right fix for the "rescued by a real
  worker" non-determinism it documents.

## Appendix: test artifacts reviewed

- `tests/test_cadquery_runner.py`, `tests/test_config.py`, `tests/test_pipeline_backends.py`,
  `tests/test_webapp.py` (STEP sections, lines 322-391), `tests/test_cadquery_bench.py`,
  `tests/conftest.py`, `tests/test_fallback_provider.py`, `tests/test_pipeline.py` (slice-safety).
- Source under test: `src/kimcad/cadquery_runner.py`, `cadquery_worker.py`, `pipeline.py`,
  `config.py`, `openscad_runner.py`, `webapp.py` (`_serve_step` + step_url wiring), `llm_provider.py`,
  `cadquery_bench.py`.
- Gate config: `.github/workflows/ci.yml`, `.githooks/pre-push`, `scripts/ci.sh`.
- Mutation runs (all in a scratch copy, restored; `git diff` against HEAD verified clean):
  Attribute-dunder, Subscript-key, banned-attr branches in `cadquery_runner.py`; facade
  submodule-strip in `cadquery_worker.py` (confirmed real RCE under the weakened facade).
- Test execution: non-live targeted set 153 passed / 12 deselected; live Stage 8 subset 11 passed
  / 42 deselected (this machine has a Python-3.13 cadquery interpreter).
