# Audit Lite — Stage 8 Slice 2: CadQuery interpreter discovery + config plumbing
**Date:** 2026-06-06
**Scope:** The working-tree changes (branch `stage-8-cadquery`) that add `Config.cadquery_interpreter()` / `Config.cadquery_timeout_s()` to `src/kimcad/config.py`, the `include_defaults` keyword to `find_cadquery_interpreter()` in `src/kimcad/cadquery_runner.py`, the `binaries.cadquery_python` + `limits.cadquery_timeout_s` keys in `config/default.yaml`, and the new tests in `tests/test_config.py`. (Rest of `cadquery_runner.py` reviewed under Slice 1 — out of scope.)
**Reviewer:** Claude (audit-lite), genuinely independent

## TL;DR
Ships. This is a tight, well-modeled config slice — the null/false/explicit contract is correct, the lazy import is the right call and actually resolves the real config↔runner↔openscad_runner cycle (verified at runtime), and the cache memoizes `None` correctly via the `_UNSET` sentinel. One Minor (the cache is non-atomic mutable state on a `Config` shared across `ThreadingHTTPServer` threads — benign today, worth a comment), and two Nits (falsy-but-not-`False` values silently auto-discover; no schema validates `default.yaml`). No correctness defect, no security exposure, no test gap. Not-yet-wired into production paths, which correctly bounds the blast radius for a Slice-2 plumbing change.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 2

## Findings

### SLICE2-001 Minor: Interpreter cache is non-atomic mutable state on a Config shared across server threads
**Dimension:** Correctness
**Evidence:** `src/kimcad/config.py:107` (`self._cadquery_interpreter = _UNSET` in `__init__`), `:156-171` (check-then-probe-then-assign, no lock). `src/kimcad/webapp.py:36` imports `ThreadingHTTPServer`; `:1892-1895` constructs one `Config` and hands it to `make_handler(..., config=config)`; `:701` stores that single instance in `config_box["config"]` and `:703-708` returns the same object to every request thread. So the cache is read/written by concurrent worker threads with no synchronization.
**Why it matters:** Two requests that both miss the cache can each spawn the discovery subprocess and both write `self._cadquery_interpreter`. The result is idempotent (every probe returns the same interpreter, and a plain attribute assignment is atomic under CPython's GIL, so no torn/corrupt read), so the only cost is a duplicated ~3-4s `import cadquery` probe under a cold concurrent burst — exactly the cost the cache exists to avoid, partially defeated in the one window it matters. No incorrectness, no crash. Today nothing in production even calls this method (see "What's working"), so the window isn't reachable yet — but it will be once Slice 3 wires CadQuery into the threaded pipeline.
**Fix path:** Either (a) prime the cache once at startup (call `config.cadquery_interpreter()` right after `Config.load()` in `serve()` / before the server starts accepting connections, so all threads hit a warm cache), or (b) guard the probe with a `threading.Lock` on the Config. Option (a) is simpler and matches the "discover once" intent. A one-line comment noting the deliberate no-lock-because-idempotent decision would also suffice if you choose to leave it.

### SLICE2-002 Nit: Falsy-but-not-`False` values (`""`, `0`, `[]`) silently auto-discover instead of erroring or disabling
**Dimension:** Correctness
**Evidence:** `src/kimcad/config.py:163-169` — `if raw is False:` (off) `elif raw:` (authoritative) `else:` (auto-discover). I confirmed at runtime that `cadquery_python: ""` and `cadquery_python: 0` both fall into the `else` (auto-discover) branch with `candidates=[]`, `include_defaults=True`.
**Why it matters:** A user who writes `cadquery_python: ""` (or an empty argv list) probably meant "explicitly none / disable," but gets full auto-discovery instead — a quiet surprise, not a failure. The documented contract (`null` / `false` / a path) doesn't cover these, so it's out-of-contract input, and the graceful-absence posture means the worst case is "backend turns on when I didn't expect," which a misconfigured machine would notice immediately. Low stakes.
**Fix path:** Optional. If you want to be strict, treat an empty string as `false` (off) or raise an `UnknownConfigKey`-style hint. Otherwise leave as-is and rely on the doc comment in `default.yaml:21-24`, which is clear about the three intended values.

### SLICE2-003 Nit: Nothing validates `default.yaml` shape; new keys rely on accessor-level `.get(...)` defaults
**Dimension:** Tests / Correctness
**Evidence:** No `jsonschema`/validator covers config — the only `jsonschema` usages in `src/` are `ir.py` and `webapp.py` (LLM-output schemas, unrelated). `cadquery_timeout_s()` (`config.py:175`) and `cadquery_interpreter()` (`:163`) both use `self._d.get(..., {})` with literal defaults, so a typo'd key (`cadquery_timout_s`) silently yields the default 120 rather than erroring.
**Why it matters:** Consistent with the existing pattern in this file (every accessor self-defaults; there's no global schema), so this isn't a regression — just noting the slice inherits the project's no-schema posture. A mistyped limit key would be invisible. Acceptable for a local-first tool where the default is a safe value.
**Fix path:** None required for this slice. If config typos become a recurring support issue, a lightweight schema check at `Config.load()` would catch all of them at once — a separate, larger task, not this slice.

## What's working
- **The null/false/explicit contract is correct and matches the docs.** `config.py:163-171` cleanly maps `false`→off-without-probe, truthy path/argv→authoritative (`include_defaults=False`), null/absent→auto-discover. I verified all three branches at runtime, including that `false` does NOT spawn a probe (`called == []`) and that an explicit path passes `include_defaults=False`. The `default.yaml:18-25` comment block documents exactly these three values.
- **The lazy import is the right call and actually resolves a real cycle.** There genuinely is a cycle: `config` → (lazy) `cadquery_runner` → `openscad_runner` → `from kimcad.config import PROJECT_ROOT` (`openscad_runner.py:33`). Importing `find_cadquery_interpreter` at module top in `config.py` would risk a partially-initialized-module import during startup since `config` is imported very widely. Deferring it into the method body sidesteps that. I confirmed `import kimcad.config` + a `cadquery_interpreter()` call works at runtime with no ImportError.
- **The cache memoizes `None` correctly.** The `_UNSET` sentinel (`config.py:99`, `:107`, `:156`) is the correct idiom — a plain `if self._x is None` check would re-probe forever when the interpreter is genuinely absent (the common case on a machine without a ≤3.13 + cadquery). The `false` branch correctly stores `None` and is cached. `test_cadquery_interpreter_is_cached` pins exactly one probe per Config.
- **`include_defaults=False` truly prevents fall-through.** `cadquery_runner.py:264-273`: when `include_defaults=False`, the `py -3.x` / `python3.x` defaults are never appended to `cmds`, so only the explicit candidate is probed — an explicit override that lacks cadquery yields `None`, not a silent fall-through to some other interpreter. This is the authoritative-override guarantee, and it holds.
- **Argv-list overrides work.** `config.py:167` wraps the raw value as `[raw]`; I confirmed `cadquery_python: ["py","-3.13"]` arrives at the runner as a single argv-prefix candidate `[["py","-3.13"]]` with `include_defaults=False` — the loop at `cadquery_runner.py:265-269` correctly distinguishes a `str`/`Path` candidate from an argv sequence.
- **Monkeypatch tests pin the real contract, not just smoke.** The Slice-2 tests assert the exact `candidates` list AND the `include_defaults` flag passed through (`test_config.py:122-123`, `:137-138`) and that the `false` path makes zero calls (`:108`) — they pin behavior, not just the return value. The live test is correctly gated with both `@pytest.mark.live` and `skipif(find_cadquery_interpreter() is None)`, so it self-skips on a machine without cadquery instead of failing. `tests/test_config.py` = 16 passed in 6.4s on my run (the live discovery test ran — this machine has an interpreter).
- **`find_cadquery_interpreter` never raises** (`cadquery_runner.py:282-283` swallows `OSError`/`SubprocessError`), so a hostile/broken candidate degrades to "unavailable" rather than crashing config loading — the same graceful-absence posture as `printproof3d_binary()`.
- **Blast radius is correctly bounded for Slice 2.** Neither new method is called by any production code yet (only tests reference them) — adding two methods and two `__init__`-cached fields to `Config` touches nothing else; every existing `Config` consumer is unaffected. Adding `self._cadquery_interpreter` to `__init__` is safe because `Config` is constructed in exactly two ways (`Config.load()` and the direct `Config(dict)` used in tests), both of which run `__init__`.

## Watch items
- When Slice 3+ wires `cadquery_interpreter()` into the threaded pipeline, revisit SLICE2-001 — priming the cache at server startup is the cheap fix and the natural place to do it is right after `Config.load()` in `webapp.serve()`.
- `cadquery_timeout_s()` returns `int` and feeds `render_cadquery(timeout_s=...)`; the default (120) matches `render_cadquery`'s own default (`cadquery_runner.py:157`) and `default.yaml:197`. Keep those three in sync if the limit changes.

## Escalation recommendation
No escalation needed. This is a small, correct config slice with zero Blocker/Critical/Major findings — exactly the scope audit-lite is for. The single Minor is a latent (not-yet-reachable) concurrency nicety, and the two Nits are out-of-contract-input and an inherited project-wide no-schema posture, neither specific to this slice. A full `audit-team` run would be overkill.

---

## Remediation (maintainer, 2026-06-06) — 0/0/0/0/0

- **SLICE2-001 (Minor) — FIXED.** `Config.cadquery_interpreter()` now probes under a
  `threading.Lock` with a double-checked guard (`config.py`), so the probe-once guarantee
  holds on the shared, threaded web server even before Slice 3 wires CadQuery in. No
  double-probe window remains.
- **SLICE2-002 (Nit) — FIXED.** An explicitly-cleared empty string (`cadquery_python: ""`)
  is now treated like `false` (force OFF, no probe), matching the doc comment in
  `default.yaml`. Regression test `test_cadquery_python_empty_string_disables_without_probing`.
- **SLICE2-003 (Nit) — ACCEPTED (rationale).** No schema validates `default.yaml`; every
  accessor self-defaults via `.get(..., default)`. This is a pre-existing, project-wide
  pattern (not introduced by this slice) and a `Config.load()` schema validator is a
  separate, larger task. Safe defaults make a typo'd key benign and immediately visible.
  Tracked as a future hardening, not fixed in this slice.

Re-verified: ruff clean; `tests/test_config.py` 17 passed (incl. the new empty-string + the
live discovery test).
