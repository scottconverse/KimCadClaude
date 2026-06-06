# Re-Audit (Engineering / Security / Test lane) — KimCad Stage 8 CadQuery backend

**Date:** 2026-06-06
**Branch:** `stage-8-cadquery` (uncommitted remediation in the working tree)
**Reviewer:** Claude (independent re-audit, audit-lite framework)
**Scope:** Verify each ENG-/TEST- remediation actually closes its finding, confirm no
regressions, rule explicitly on the OS-confinement deferral. UI/Docs lanes only spot-touched
where they back an eng/security claim (DOC-001/DOC-004).
**Method:** source read of `cadquery_runner.py`, `cadquery_worker.py`, `pipeline.py`,
`scripts/ci.sh`, the Stage-8 tests, and the docs; live execution on this box's Python 3.13.13 +
cadquery 2.7.0 interpreter; in-memory mutation tripwire checks; targeted test run (76 passed,
incl. the live worker/render tests). **No repo file was mutated** — all mutation/probe work ran
in OS temp or as in-process monkeypatches; `git status` verified clean (only the audit dir is
untracked).

---

## TL;DR

**SHIP (eng/security/test lane).** Every ENG-/TEST- finding is genuinely closed and the new
tests are real tripwires (mutation-verified). The two-layer sandbox holds under live adversarial
probing through the production `render_cadquery` entry: all nine known escape classes are blocked,
and the documented layer-2-alone residual (`__globals__` via a facade function) is reachable only
when the sanitizer is bypassed — exactly as the honest docstrings state. The env-scrub drops every
secret and keeps the interpreter launchable. The OS-confinement deferral to Stage 11 is an
**acceptable closure** for this local-first beta (justified below). One NEW Nit (env-scrub
over-strips two non-secret look-alikes — safe direction). No new Major/Critical. No escalation to
audit-team.

## Severity rollup (new findings this re-audit)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 1 (REAUDIT-N1, below)

---

## Per-finding verdicts

### ENG-002 — env/cwd isolation — **CLOSED**
`render_cadquery` now passes `env=_worker_env()` and `cwd=str(out_dir)` to the worker spawn
(`cadquery_runner.py:222-230`); the discovery probe also passes `env=_worker_env()`
(`:319-322`). `_worker_env()` (`:57-61`) drops vars matching
`(API_?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE_?KEY|_KEY$)` case-insensitively.
- **Live verified:** with a realistic 30-var env, every secret form is dropped
  (`OPENROUTER/OPENAI/ANTHROPIC_API_KEY`, `*_TOKEN`, `DB_PASSWORD`, `AWS_SECRET_ACCESS_KEY`,
  `DEEPSEEK_KEY`, `SSH_PRIVATE_KEY`, `GH_TOKEN`, `CREDENTIAL_X`, `PASSWD`) while PATH/SYSTEMROOT/
  TEMP/PYTHONPATH/WINDIR/COMSPEC/APPDATA survive — python starts cleanly (the 153/76 live tests
  prove the worker launches under the scrubbed env).
- **Regex does NOT over-strip the interpreter into non-startable state:** `KEYBOARD`, `KEYRING_X`,
  `MONKEY` are kept (the `_KEY$` anchor needs a trailing `_KEY`; bare `KEY` only matches inside
  `API_KEY`/`PRIVATE_KEY`).
- **Tripwire confirmed:** reverting to `dict(os.environ)` flips `test_worker_env_scrubs_secrets`
  from green to red (the secret survives).

### ENG-001 (+ QA-001 / QA-002) — no OS-level confinement — **CLOSED (actionable parts) / DEFERRAL ACCEPTED**
The three actionable sub-items landed and are verified:
- **env/cwd isolation** = ENG-002 (above).
- **Through-`render_cadquery` escape-class canary**
  (`test_render_cadquery_blocks_escape_class_end_to_end`, `test_cadquery_runner.py:160-171`),
  parametrized over os-import, `exporters.os` pivot, `__globals__` chain, `__subclasses__`,
  subscript-dunder, frame-attr, and `str.format` payloads. **Live verified:** I ran all nine
  classes through the production `render_cadquery` (no interpreter) — every one raises
  `BlockedCodeError` at the real entry point, not just in a unit branch.
- **Release-gate backstop** = TEST-001 (below).
- **Mutation-verified tripwire:** deleting the sanitizer's `Subscript` branch (the exact
  `if False and …` regression the prior round's agent left) makes the subscript-dunder payload
  reach the subprocess — the parametrized canary would go **red**. This is precisely the backstop
  the Major asked for.

**Explicit ruling on the OS-confinement deferral → ACCEPTABLE; no Major remains open.**
Reasoning:
1. **Trust model parity.** KimCad already executes generated OpenSCAD locally with the same
   ambient authority; CadQuery does not raise the *category* of trust, only the surface area. The
   product's stated model is "you run generated code on your own machine." OS-level confinement is
   a depth improvement, not a correctness gap for a local-first beta.
2. **The live escape class is closed by layer 1.** Under live probing, the only path that reaches
   a facade function's real `__globals__` requires a dunder/introspection attribute — every one of
   which the static sanitizer blocks (verified nine ways, end-to-end). Layer-2-alone reachability
   exists (I confirmed it direct-to-worker, sanitizer bypassed), but production never bypasses the
   sanitizer.
3. **The residual is now backstopped, not bare.** The original Major's core complaint was "one
   token from RCE with no second gate to catch a regression." That is materially addressed: a
   single-branch sanitizer regression now fails the through-entry canary loudly, and a release run
   without the worker-sandbox live tests hard-fails (`KIMCAD_RELEASE=1`). Plus env-scrub bounds the
   blast radius (no API keys in the worker env) and isolated-cwd bounds the write surface.
4. **Cost/benefit + precedent.** A Job Object / restricted token (Windows) or namespaces (Linux)
   is heavy, platform-specific, and naturally co-lands with the installer/bundling work — which is
   exactly where the docs now schedule it (Stage 11). Deferring a disproportionate hardening with a
   written rationale, a backlog item, and cheap in-tree mitigations in place is the right call;
   shipping a half-built confinement layer now would be worse.
The deferral is honestly documented in `docs/cadquery-backend.md:91-100`, the worker docstring
(`cadquery_worker.py:44-50`), CHANGELOG, and ARCHITECTURE. Verdict: **closed as
fixed-where-cheap + accepted-with-rationale.** No open Major.

### ENG-003 — bytes-key dunder subscript — **CLOSED**
`cadquery_runner.py:148-160`: the `Subscript` branch now flags a constant key of type **str OR
bytes** containing `__`, decoding bytes via `latin-1`. An in-code NOTE documents the
worker↔sanitizer coupling (`:151-155`).
- **Tripwire confirmed:** reverting to str-only lets `x[b"__globals__"]` pass →
  `test_bytes_dunder_subscript_is_blocked` goes red; the str path still blocks under both (the fix
  is additive).
- **Computed-key residual is inert — live verified.** A computed key (`chr(95)*2+"globals"…`) and
  a concat-literal key (`"__glo"+"bals__"`) DO pass the static sanitizer (as the NOTE admits), but
  the worker **withholds every string-building primitive**: `chr`, `ord`, `bytes`, `type`,
  `getattr`, `globals`, `vars`, `eval`, `exec`, `compile`, `open`, and the real `__import__` each
  raise NameError/ImportError at the worker. So a dunder string cannot be *built or used* at
  runtime — the two layers are correctly coupled, and I confirmed both legs live.

### ENG-005 — sentinel-delimited interpreter probe — **CLOSED**
`_PROBE` now wraps the path in `__KIMCAD_CQ__` sentinels (`:279-283`) and discovery parses
`stdout.split(sentinel)` requiring `len >= 3` then `parts[1]` (`:329-333`).
- **Live verified:** the real 3.13 interpreter emits `__KIMCAD_CQ__<path>__KIMCAD_CQ__`; a banner
  before/after does not corrupt `parts[1]`.
- Non-live tests cover OSError-swallow, bogus-path-skip, and banner-noise-parse
  (`test_cadquery_runner.py:212-236`); all pass.

### ENG-006 — STEP covered by output-size guard — **CLOSED**
`cadquery_runner.py:256-259` adds a STEP-size check mirroring the STL one.
- **Live verified, independent of the STL:** with `max_output_bytes` set above the STL (684 B) but
  below the STEP (15 504 B), `render_cadquery(..., emit_step=True)` raises
  `OversizeOutput: cadquery STEP is 15504 bytes (> 8094 guard)`. Pre-fix (STL-only) this render
  would have succeeded. ENG-009 (docstring drift) is consequently accurate too.

### ENG-007 — worker os/sys imports marked harness-only — **CLOSED**
`cadquery_worker.py:59-61` carries the comment that `os`/`sys`/etc. are harness-only and never
reach the executed script (which gets `_safe_builtins`, not module globals). Confirmed accurate:
the exec namespace (`:141-146`) is an explicit fresh dict with no `os`/`sys`.

### TEST-001 — CadQuery release-gate backstop in ci.sh — **CLOSED**
`scripts/ci.sh:71-84`: a python one-liner exits 0 if `find_cadquery_interpreter()` returns a path,
1 otherwise; on 0 → "OK (worker-sandbox live tests ran)", on 1 → WARNING and, under
`KIMCAD_RELEASE=1`, `exit 1`. Mirrors the OrcaSlicer gate.
- **Logic verified both directions:** present → exit 0 → OK branch; forced-None → exit 1 →
  WARN/release-gate branch. The `2>/dev/null` swallow routes even an import error to the
  fail-closed (else) branch — the safe direction.

### TEST-002 — worker timeout / crash-synthesis / withholding tests — **REAL**
- `test_render_cadquery_timeout_is_raised` (`:187-195`) stubs `subprocess.run` to raise
  `TimeoutExpired` → asserts `RenderTimeout` (non-live; runs on hosted CI).
- `test_read_worker_result_synthesizes_failure_on_a_missing_result_file` (`:198-205`) feeds a
  `CompletedProcess(rc=139, stderr="segfault!")` with no result file → asserts a synthesized
  `{ok:False, kind:exec}` carrying the stderr (non-live).
- `test_worker_withholds_dangerous_builtins_beyond_open` (`:321-331`, live) sends
  `eval`/`exec`/`getattr` straight to the worker → each fails. I independently confirmed live that
  all 12 dangerous primitives are withheld.

### TEST-003 / 004 / 005 / 006 / 007 — **REAL (tripwires where applicable)**
- **TEST-003** `generate_cadquery` delegation: `test_primary_success_cadquery_alt_never_called` +
  `test_fallback_on_cadquery_delegates_to_alt` (`test_fallback_provider.py:94-109`) — behavioral
  success-skips-alt and fallback-on-error. Pass.
- **TEST-004** `proceed_anyway` + WARN: `test_proceed_anyway_accepts_a_gate_failed_primary_without_fallback`
  (`test_pipeline_backends.py:204-214`, asserts `cadquery_calls == 0`, `backend == openscad`) and
  `test_backend_succeeded_accepts_a_warn_primary_without_fallback` (`:217-226`, binds the rendered
  tuple to `_backend_succeeded`). Pass; matches `pipeline.py` `_backend_succeeded`/`_better_result`.
- **TEST-005** contract is now behavioral: `test_all_real_providers_implement_the_full_contract`
  (`:177-201`) `inspect.signature(...).bind(...)` against the real arg shape for each provider —
  catches a wrong-arity stub, not just presence.
- **TEST-006** discovery internals: OSError-swallow / bogus-path-skip / banner-parse — three
  non-live tests, all pass; reverting the sentinel parse would break them (verified by the ENG-005
  reasoning + the bogus-path test which requires `p.exists()`).
- **TEST-007** belt-and-suspenders comment present at `test_pipeline_backends.py:114-117`,
  documenting the explicit `_cadquery_interpreter = None` poke is independent of the fixture.

### DOC-001 / DOC-004 (eng-backing docs) — **CLOSED**
- **Live verified DOC-001:** the worker `__import__` raises `ImportError` for os/sys/subprocess/
  socket and `from os import system`; returns the facade for `import cadquery` and real `math`.
  Wording is accurate in `docs/cadquery-backend.md`, `cadquery_worker.py:33-42`, CHANGELOG,
  ARCHITECTURE.
- **DOC-004:** "every **top-level** cadquery submodule" scoping is present
  (`docs/cadquery-backend.md:82`, CHANGELOG:47).

---

## Independent end-to-end break attempt (production entry, env-scrub in place)

Through `render_cadquery` (the production path) I attempted: os/sys/subprocess/socket import;
`cq.exporters.os.system`; `__globals__["__builtins__"]["__import__"]("os")`; `().__class__…
__subclasses__()`; str- and bytes-subscript dunder keys; `gi_frame.f_builtins`; `str.format`
field pivot; `global os`; and computed-/concat-key dunder subscripts. **Every payload was either
blocked by the sanitizer (BlockedCodeError) or rendered inert at the worker** (the string-building
primitives needed to weaponize a computed key are all withheld). **No payload reached os,
subprocess, the network, the filesystem, or an API key** — no marker file was ever written. The
only reachable layer-2-alone weakness (a facade function's `__globals__`) requires bypassing the
sanitizer, which production never does. **No escape = no new finding.**

## NEW findings

### REAUDIT-N1 — Nit — Security/Hygiene: env-scrub over-strips two non-secret look-alikes
**Dimension:** Correctness/Security
**Evidence:** `_SECRET_ENV_RE` (`cadquery_runner.py:52-54`) is a substring match, so `TOKENIZER`
(contains `TOKEN`) and `PASSWORDLESS` (contains `PASSWORD`) are dropped from the worker env even
though they are not secrets (confirmed live).
**Why it matters:** Purely cosmetic — the geometry-only worker needs none of these, and dropping a
non-secret is the *safe* over-approximation. It is not a correctness or security defect.
**Fix path:** Optional. If a real `TOKENIZER_*`/`PASSWORDLESS_*` var ever needs to reach the
worker, anchor the secret tokens (e.g. `\b(...)\b` or require `_`/start boundaries). Not worth
doing now.

## What's working (credit)
- The two-layer model is honest and the docstrings state what each layer *cannot* do — rare and
  valuable. Live probing matched the docs exactly.
- The new escape-class canary runs at the **production entry with no interpreter**, so it gates on
  hosted CI (not just the live tier) — the highest-leverage part of the ENG-001 remediation.
- The sanitizer↔worker coupling (computed dunder keys inert because no string-building builtin
  exists) is now documented in-code AND empirically true for all 12 primitives.
- The release-gate backstop closes the "green because skipped" hole for the security-critical
  second layer, matching the existing OrcaSlicer/frontend gates.

## git cleanliness confirmation
`git -C C:\Users\scott\dev\kimcad status --porcelain` shows the remediation's tracked-modified
files (`ARCHITECTURE.md`, `CHANGELOG.md`, the two docs, the four frontend files, `scripts/ci.sh`,
the three `src/kimcad` py files, the three `tests` files, the two `web/assets` build outputs) plus
exactly one untracked entry: `docs/audits/stage-8/audit-team-stage-8-2026-06-06/`. **No tracked
file was altered by this re-audit and no stray untracked file was created** — all mutation/probe
work ran in OS temp or as in-process monkeypatches.

## Escalation recommendation
**No escalation needed.** Zero new Blocker/Critical/Major. The lane is clean.

## Overall verdict (eng/security/test lane): **SHIP.**
