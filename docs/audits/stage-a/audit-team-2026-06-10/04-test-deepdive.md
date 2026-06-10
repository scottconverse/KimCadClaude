# Test Suite Deep-Dive — KimCad (Stage A: first-run hardening)

**Audit date:** 2026-06-10
**Role:** Test Engineer
**Scope audited:** Stage A test changes only (a9fd720..5aad7f3): `tests/test_first_run_errors.py` (new), `tests/test_llm_provider.py` (probe pinning), `tests/test_openscad_runner.py` / `tests/test_slicer.py` (stub-binary updates), `tests/test_webapp.py` (typed tool-missing paths + genericized 500s), `frontend/src/components/ModelHealthPill.test.tsx` + `FirstRunWizard.test.tsx`, and the test-related steps of `.github/workflows/ci.yml`. Targeted suites were executed in this audit (20 + 60 + 4 pytest tests, 16 vitest tests — all pass).
**Auditor posture:** Adversarial (stage-gate)

---

## TL;DR

Stage A's new tests are, for the most part, the real thing: real `APIConnectionError` objects, real sockets, a real HTTP server, exact recovery strings pinned on both surfaces, and negative assertions (`b"kaboom" not in body`) that actually bite. The two retry tests were correctly hermetized by pinning the new reachability probe, and the stub-binary refactor preserved every test's original intent — including a deliberate choice to keep the binary absent in the blocked-code test to pin sanitize-before-guard ordering. Two things keep this from a clean bill: the QA-006 port-in-use test certifies green a guard that the same-day walkthrough proved **never fires in real python-vs-python use on Windows** (the only supported OS), and the CI workflow's "no green-by-skip" step asserts collection, not execution — it would stay green if every live test skipped at runtime. The most important class of bug this suite would let through today: *a first-run safety feature that works only in the unit-test harness's manufactured error mode.*

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 1 |
| Minor | 4 |
| Nit | 1 |

## What's working

- **`tests/test_first_run_errors.py` is a genuine contract suite, not theater.** It raises the *real* `openai.APIConnectionError` (built over a real `httpx.Request`), drives `cli.main` end-to-end through the real arg parser, and pins the contract from three directions at once: exit code (`== 2`), the absence of a traceback (`"Traceback" not in err`), and the exact recovery command (`"ollama pull"`, `"fetch_tools.py"`). Call-counting (`client.calls == 1` for never-up fail-fast vs `client.calls == 2` for mid-run retry) pins the *behavioral budget*, not just the outcome — a regression that silently re-entered the 6×30 s loop would fail loudly.
- **Hermeticity of the retry tests is now complete.** Both pre-existing retry tests in `tests/test_llm_provider.py` (lines 197, 225) pin `_server_reachable` to `True` with a comment explaining *why* (the host may or may not have a live Ollama on :11434), and the never-up branch pins it `False` in `test_first_run_errors.py`. Both sides of the new branch are forced deterministically; nothing in these tests now depends on host state. Verified by running the suite (20 passed, 5.8 s) on a box where Ollama exists.
- **The stub-binary updates preserved intent — and improved it.** Every mocked-subprocess test in `test_openscad_runner.py` / `test_slicer.py` still mocks `subprocess.run` exactly as before; the empty on-disk stub satisfies only the new presence guard. Best detail: `test_render_refuses_blocked_code` deliberately does **not** get a stub, with a comment pinning the ordering contract ("sanitization runs before the tool-presence guard"). That is a new, intentional ordering test smuggled into a mechanical refactor. All 60 non-live tests pass.
- **The genericized-500 tests assert both directions.** All four updated/new web 500 tests check the generic line is present **and** that the class name and exception text are absent (`b"RuntimeError" not in body`, `b"kaboom" not in body`). A future "helpful" re-leak cannot pass.
- **Frontend tests pin user-visible strings, not internals.** `ModelHealthPill.test.tsx` and the three new `FirstRunWizard.test.tsx` recap tests assert `role="status"`, the exact `ollama pull gemma4:e4b` command, the demoted "Almost ready" headline, that "Start designing" stays available, and the re-check flow including probe call counts. These would catch exactly the trust-breaking regressions UX-002 targets.
- **Regression culture is real.** Slice-A1's re-audit findings (LITE-A1-001/002) got their pinned tests updated in the same commit as the fix, and the walkthrough was run against a *genuinely stopped* Ollama, not mocks — that is how WALK-A-001 was caught at all.

## What couldn't be assessed

- **CI run history / flake rate** — the self-hosted runner's past run logs were not inspected; flakiness posture is judged from test code only.
- **The live (`-m live`) tool-contract tests were not executed in this audit** (multi-minute real OrcaSlicer slices); their skip *conditions* were reviewed instead.
- **No mutation testing** is configured, so "meaningful coverage" is judged by reading assertions, not by mutation score.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (backend; real-HTTP integration + `-m live` real-tool contracts), Vitest + Testing Library (frontend, jsdom) |
| Test pyramid shape | Strong unit + real-socket integration; live tool contracts gated on binary presence; no automated browser E2E (covered manually by the walkthrough skill) |
| Coverage tool | none configured (no coverage.py/istanbul in the gate) |
| Reported coverage | n/a |
| Flakiness posture | Clean — no retries configured anywhere; one narrow theoretical race found (TEST-005) |
| CI blocking? | Yes for the main gate (`scripts/ci.sh` via the self-hosted runner); the live-test "no green-by-skip" assertion is partially decorative (TEST-002) |

---

## Findings

> **Finding ID prefix:** `TEST-`

### [TEST-001] — Critical — Regression — The QA-006 port-in-use test certifies a guard that never fires in real use on Windows; no regression test for the known double-bind (WALK-A-001)

**Evidence**
`tests/test_first_run_errors.py:221-237` (`test_serve_port_in_use_raises_friendly_runtime_error`): the blocker socket sets `SO_EXCLUSIVEADDRUSE` before binding, which *manufactures* the `OSError` the guard in `webapp.serve` (src/kimcad/webapp.py:2015-2023) handles. The same-day walkthrough (docs/audits/walkthrough-stage-a-2026-06-10/WALKTHROUGH-REPORT.md, WALK-A-001, Major) proved at runtime that a second `kimcad web` binds **silently** — `ThreadingHTTPServer` sets `allow_reuse_address`, which on Windows maps to `SO_REUSEADDR` and permits the double bind. No test in the suite starts a real `serve()` and then a second one on the same port. The suite is green; the feature is unreachable for every real user on the only supported OS.

**Why this matters**
This is the textbook false-confidence failure: the test exercises the *message wiring* of the guard, while the *trigger condition* it exists for never occurs in reality. The class of bug let through is severe for the non-developer target user: two KimCad servers silently fighting over one port, with intermittent wrong-instance responses and no error anywhere. Any future fix to WALK-A-001 that regresses would also pass this test.

**Blast radius**
- Adjacent code: `webapp.serve` / the `ThreadingHTTPServer` construction (the WALK-A-001 fix point: a subclass with `allow_reuse_address = False` on win32).
- Tests to update: keep the existing test (it pins the message + `--port` hint) **and** add the real-condition regression test: start `serve()` on a thread on an ephemeral port, attempt a second `serve()` on the same port, assert the friendly `RuntimeError`. The new test will *fail until WALK-A-001 is fixed* — which is the point; land them together.
- User-facing: second-instance launches go from silent corruption to one actionable line.
- Related findings: WALK-A-001 (walkthrough); TEST-005 (same file, socket-lifecycle care).

**Fix path**
Land the WALK-A-001 fix with a python-vs-python double-bind regression test in `test_first_run_errors.py` (real `serve()` thread + second `serve()` on the same port; tear down via `httpd.shutdown`). Recommend tagging it with the WALK-A-001 ID in the docstring, matching the suite's existing QA-tag convention.

---

### [TEST-002] — Major — CI — The "no green-by-skip" CI step does not actually fail when live tests skip

**Evidence**
`.github/workflows/ci.yml:78-85`:
```powershell
$out = .\.venv\Scripts\python.exe -m pytest -m live --collect-only -q 2>$null | Select-Object -Last 2
$out
```
Three independent gaps: (1) `--collect-only` proves the live tests *exist*, not that they *ran* or didn't skip — `skipif` is evaluated at run time and is invisible to collection counts; (2) `$out` is printed but never asserted on; (3) `$LASTEXITCODE` is not checked after the pytest call, so even a collection error (exit 2/3/4/5) passes the step. The only real teeth in the step are the `Test-Path tools\orcaslicer\orca-slicer.exe` and the CadQuery-interpreter check. But the live tests' actual skip conditions are wider than those proxies: `tests/test_slicer.py:550-561` and `tests/test_webapp.py:525-534` skip when the **profiles** root is absent or when `config/local.yaml` redirects `binary_path("orcaslicer")` somewhere other than the path CI checks. And `scripts/ci.sh` deliberately only *warns* on skipped live tests unless `KIMCAD_RELEASE=1` — so on a normal push, nothing red happens when the live contracts skip.

**Why this matters**
The step's name promises exactly the Blocker condition in the severity framework ("CI passes because tests are skipped") is impossible; it isn't. A profiles-folder deletion, a fetch_tools format change that stops producing profiles, or a stray `local.yaml` on the runner would silently downgrade CI from "live tool contracts proven" to "live tool contracts collected," with a green check either way. The class of bug let through: a real OrcaSlicer CLI/profile regression shipping behind a green gate.

**Blast radius**
- Adjacent code: `.github/workflows/ci.yml` step "Assert the live tool contracts actually ran"; `scripts/ci.sh`'s warn-only blocks share the same intent (and stay warn-only by design for dev pushes — that's fine *if* the CI step compensates).
- Shared state: the runner's persistent `_work` workspace (cached `tools/`, possible stale `config/local.yaml`) is exactly where the proxies and reality drift apart.
- Tests to update: none — this is workflow logic.
- Related findings: none in this scope; complements ci.sh's TEST-002 (Stage 8.5 lineage) intent.

**Fix path**
Replace the collect-only probe with an execution assertion: run `pytest -m live -q -ra --junitxml=live-results.xml` (or re-use the gate run's `-ra` output) and fail the step if `skipped > 0` or `passed == 0` for the live selection; check `$LASTEXITCODE` after every native call in the step. A 6-line PowerShell parse of the junit XML is enough.

---

### [TEST-003] — Minor — Regression — WALK-A-002 (SDK-internal retries stacking) has no pinning test

**Evidence**
`src/kimcad/llm_provider.py:_build_client` (lines 200-210) constructs `OpenAI(...)` without `max_retries=0`; the walkthrough measured the consequence (21.2 s CLI / 18.5 s web fail-fast instead of ~7 s, up to 18 connect cycles on a listening-but-failing server). No test asserts the built client's retry configuration, and no test pins an upper bound on the fail-fast budget.

**Why this matters**
The QA-002 fail-fast contract is "seconds, not minutes." Without a test on `max_retries`, the SDK default (2) can silently re-stack under KimCad's own loop — or triple after an SDK upgrade — and the suite stays green. (The fix itself is also still unapplied.)

**Fix path**
When applying the WALK-A-002 fix, add to `test_llm_provider.py`: build a provider without an injected client and assert `provider.client.max_retries == 0` (the openai client exposes it). One line of arrange, one assert.

---

### [TEST-004] — Minor — Coverage — New `cli.main` error-mapping branches are untested: the openai `NotFoundError` branch, the bench/bakeoff routes, and the deliberate re-raise

**Evidence**
`src/kimcad/cli.py:496-521`. Tested: the `_is_model_unreachable` branch and the `RuntimeError`/`ToolMissingError` branch, via the two CLI tests in `test_first_run_errors.py` — but only through `args.command == "design"`. Untested: (a) the model-not-pulled branch (`type(e).__name__ == "NotFoundError" and module startswith "openai"`, lines 512-519) — `tests/test_fallback_provider.py` builds a real `openai.NotFoundError` but never drives it through `cli.main`; (b) the same mapping reached via `bench` / `bakeoff` (lines 484-487 sit inside the same `try`, so the path is shared, but nothing proves a bench run against a dead server exits 2 with the friendly line rather than tracebacking from some inner handler first); (c) the final `raise` (line 520) — the contract that an *unrecognized* exception still crashes loudly is itself unpinned.

**Why this matters**
The name-and-module duck-typing in (a) is precisely the kind of string-matched branch that silently dies when the SDK renames or re-modules the class — and only a test would notice. (b) and (c) are cheap to pin and protect the "never hide a real bug behind a friendly message" half of the QA-001 contract.

**Fix path**
Three small tests in `test_first_run_errors.py`: reuse `_patch_pipeline_with` with a provider that raises a real `openai.NotFoundError` (borrow the constructor from `test_fallback_provider.py:63-69`) and assert exit 2 + "ollama pull"; one bench-route model-down test; one `pytest.raises(SomeWeirdError)` through `cli.main` proving the re-raise.

---

### [TEST-005] — Minor — Flakiness — `test_server_reachable_probe_true_and_false` has a narrow port-reuse race

**Evidence**
`tests/test_first_run_errors.py:130-145`: the test binds an ephemeral port, probes True, closes the listener, then asserts the *same* port now refuses. Between `srv.close()` and the second `create_connection`, the OS may hand that ephemeral port to any other process — and this box is also the self-hosted CI runner host running Ollama, node tooling, and parallel jobs. If anything binds it in that window, the probe returns True and the test fails spuriously. (A second, smaller hazard in the same file: `test_serve_port_in_use_raises_friendly_runtime_error` reuses the blocker's port only while the blocker is still bound, so it is safe.)

**Why this matters**
The window is microseconds and pytest runs serially, so this is theoretical-but-real on a busy runner. The first flaky failure of a first-run-contract test is how "just re-run it" culture starts.

**Fix path**
Make the false-case self-healing: if the post-close probe unexpectedly returns True, re-derive a fresh closed port (bind/close a new socket) and probe once more before failing; or assert against a port held bound-but-not-listening by a UDP socket. Two lines either way.

---

### [TEST-006] — Minor — Coverage — QA-005's CLI progress phases (`_phase_printer`) shipped with no test

**Evidence**
`src/kimcad/cli.py:242-263`: new user-visible behavior — phase labels to **stderr** (stdout reserved for the report), with consecutive-repeat dedupe for codegen retries. The Stage A diff adds no test touching it; nothing asserts phases land on stderr rather than stdout, that labels come from `_PHASE_LABELS`, or that a retried `generating` phase doesn't stutter.

**Why this matters**
The stdout/stderr split is a real contract (scripts piping the report would break if phases leaked to stdout), and the dedupe is exactly the kind of small stateful logic that regresses invisibly. The walkthrough saw it work once, live; the suite would not notice it breaking.

**Fix path**
A direct unit test of `_phase_printer()` (call with `planning, generating, generating, rendering`; capture stderr; assert 3 lines, labels mapped, stdout untouched) — no pipeline needed.

---

### [TEST-007] — Nit — Quality — The ModelHealthPill "stays silent" tests settle on a signal that is satisfied before the probe resolves

**Evidence**
`frontend/src/components/ModelHealthPill.test.tsx:26-31, 46-61`: the silent-path tests await `waitFor(() => expect(fn).toHaveBeenCalled())` — but `getModelStatus` is called synchronously in the mount effect, so the condition holds at t=0. The subsequent `queryByRole('status')` assertions currently pass *after* state settles only because the mock's microtasks happen to flush ahead of `waitFor`'s resolution. If `check()` ever gains an extra `await` before the call (or the component moves to a deferred probe), these assertions would run against the still-`checking` render — where the pill is null regardless — and would keep passing against a broken component.

**Fix path**
Settle on something that proves resolution, e.g. `await waitFor(() => expect(fn).toHaveBeenCalled()); await act(() => Promise.resolve())` or assert a post-settle marker (the cloud case could render a `data-settled` test hook, or simply `await screen.findByText` on a sibling that exists post-resolution). Flag once; the warn-path tests in the same file already use `findBy*` correctly.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `it.skip` (frontend) | 0 |
| `.only` (left in) | 0 |
| `@pytest.mark.xfail` | 0 |
| `TODO: add test` / similar | 0 |
| Empty assertion / placeholder | 0 |
| `--retry` / retries normalized | no |
| `@pytest.mark.skipif` (environment guards, backend-wide) | ~25, all with concrete reasons (binary/profiles/interpreter/manifold presence) — legitimate, but they are exactly the population TEST-002's CI step fails to police |

## Blind spots by class

- **"Manufactured trigger" tests** — TEST-001 is the live instance: the suite proves the handler, not the condition. Worth a one-time sweep of other OS-conditioned guards.
- **Skip-driven green** — environment-conditional skips are well-reasoned individually but unenforced collectively (TEST-002).
- **CLI surfaces other than `design`** — bench/bakeoff error UX is unpinned (TEST-004).
- **Timing/budget contracts** — "fails fast in seconds" has no numeric pin anywhere (TEST-003 is the cheap proxy).
- No automated browser E2E — accepted Stage A posture (the walkthrough skill fills this manually, and demonstrably caught what the unit suite missed).

## Patterns and systemic observations

- The dominant pattern is **good**: every Stage A fix landed with tests that name their QA finding ID in docstrings, assert exact user-facing strings, and include negative assertions. That convention is worth protecting.
- The two real problems share one root: **trusting a proxy for the real condition** (a manufactured socket option for the real double-bind; collection counts and binary paths for "live tests ran"). Both fixes are about asserting the real thing.

## Appendix: test artifacts reviewed

- `tests/test_first_run_errors.py` (full read; executed)
- `tests/test_llm_provider.py`, `tests/test_openscad_runner.py`, `tests/test_slicer.py`, `tests/test_webapp.py` (Stage A diffs + skip guards; executed where non-live)
- `frontend/src/components/ModelHealthPill.test.tsx`, `FirstRunWizard.test.tsx` (full read; executed — 16/16 pass)
- `.github/workflows/ci.yml`, `scripts/ci.sh`, `tests/conftest.py` (geometry-gate skip logic)
- `src/kimcad/cli.py`, `errors.py`, `llm_provider.py`, `webapp.py`, `openscad_runner.py`, `slicer.py` (code under test)
- `docs/audits/walkthrough-stage-a-2026-06-10/WALKTHROUGH-REPORT.md` (WALK-A-001/002)
