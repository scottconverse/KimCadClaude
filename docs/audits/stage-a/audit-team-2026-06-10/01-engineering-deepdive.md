# Engineering Deep-Dive — KimCad (Stage A: first-run hardening)

**Audit date:** 2026-06-10
**Role:** Principal Engineer
**Scope audited:** Stage A diff `414d22a..5aad7f3` (10 commits) plus the files it touches: `src/kimcad/errors.py` (new), `openscad_runner.py`, `slicer.py`, `llm_provider.py`, `cli.py`, `webapp.py` (serve + design/slice/send/rerender handlers), frontend `FirstRunWizard.tsx` / `ModelHealthPill.tsx` / `Landing.tsx` / `App.tsx` / `styles.css`, `.github/workflows/ci.yml`, `scripts/ci.sh`, `docs/getting-started-windows.md`, `docs/troubleshooting.md`, `tests/test_first_run_errors.py`. Stage gate — adversarial on the NEW code's correctness/security, not a re-audit of the whole repo.
**Auditor posture:** Balanced

---

## TL;DR

Stage A is a disciplined, well-tested first-run hardening slice: typed `ToolMissingError`, fail-fast model probe, connect/read timeout split, friendly CLI/web error mapping, and an honest wizard recap. The error-mapping architecture (one message source, two surfaces, re-raise on unrecognized) is the right shape and the new test file pins the contract. The top concerns are all at the *boundaries of the new guards*: the port-in-use guard is decorative on the target platform (verified WALK-A-001), the fail-fast probe is undermined by the SDK's internal retries (verified WALK-A-002) and misclassifies cloud/proxied backends, and the new self-hosted CI gate has two integrity gaps (intermediate-command exit codes swallowed; the "no green-by-skip" step doesn't actually assert) plus a latent `pull_request`-on-self-hosted exposure that is one repo-visibility toggle away from RCE on the dev box. No Blockers; nothing in the diff leaks secrets.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 5 |
| Minor | 4 |
| Nit | 3 |

## What's working

- **Single-source error contract** — `src/kimcad/errors.py` carries the user-facing message once; CLI (`cli.main`) and web (`webapp._handle_design`/slice) both surface `str(e)` so the surfaces cannot drift. The docstrings explain *why*, not just what.
- **Re-raise on unrecognized** — `cli.main`'s broad `except Exception` maps only the two known first-run failures and re-raises everything else (`cli.py:520`). Real bugs still crash loudly. The duck-typed class-name match deliberately avoids importing the OpenAI SDK in the CLI. `except Exception` correctly does not swallow `KeyboardInterrupt`/`SystemExit`.
- **Probe is thread-safe** — `_server_reachable` (`llm_provider.py:243`) holds no shared mutable state; under `ThreadingHTTPServer` concurrent design requests each open and close their own socket. `FallbackProvider`'s thread-local stickiness resets per connection thread, which is the documented intent. I hunted for a race here and found none.
- **Sanitize-before-guard ordering preserved** — `render_scad` still sanitizes and writes the `.scad` *before* the `ToolMissingError` check (`openscad_runner.py:290-294`), so blocked code is blocked regardless of tool presence. The docstring calls this out explicitly.
- **QA-008 leak closure is real** — all four web 500 paths (design, slice, send, rerender) now log class+detail server-side via `log_error` and return a generic line to the browser. `ToolMissingError` is correctly carved out as a 200 setup-state, ordered *after* the model-unreachable check.
- **Secret handling clean** — the TCP probe sends no bytes (no API key on the wire); the explicit-key-over-env precedence is unchanged; nothing new logs or echoes a key; the wizard recap renders `keyDraft` only as a boolean.
- **Tests pin the new contract** — `tests/test_first_run_errors.py` covers the typed error message, both runner guards, fail-fast vs mid-run-retry (with call counts), the probe against a real listener, both CLI exit paths (asserting "no Traceback"), and the bind guard. This is exactly the test shape a hardening slice needs.
- **Skip link is complete** — `id="kimcad-main"` exists on all four `<main>` views (Landing, Workspace, MyDesigns, SettingsPanel), not just the one in the diff's headline; `App.test.tsx` asserts it.
- **Docs match the code** — `getting-started-windows.md` / `troubleshooting.md` quote the real Slice-A1 error strings (spot-checked "Your local AI isn't running yet — start Ollama" against `ModelHealthPill.tsx:25`).
- **fetch_tools pin tightened** — the Windows OpenSCAD pin gains a sha256 (`scripts/fetch_tools.py:60`).

## What couldn't be assessed

- The self-hosted runner's actual machine configuration (service account, PATH, what else runs as `scott`) — assessed from the workflow file and its comments only.
- A live run of the new CI workflow (no access to Actions logs from this audit seat).
- `pip-audit` results on `requirements.lock` (the CI step exists; I did not execute it).
- Everything else in scope was readable and was read.

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

### [ENG-001] — Major — Correctness — Port-in-use guard (QA-006) is defeated by SO_REUSEADDR on the target platform (verifies WALK-A-001)

**Evidence**
`webapp.py:2015-2023` wraps the `ThreadingHTTPServer` bind in `except OSError` to produce the friendly "Port {port} is already in use" line. But `http.server.HTTPServer` sets `allow_reuse_address = 1` (SO_REUSEADDR), and on Windows SO_REUSEADDR permits binding a port that another SO_REUSEADDR socket already holds — the second bind *succeeds*, no `OSError` is raised, and two `kimcad web` instances silently share the port with nondeterministic connection delivery. The new test (`tests/test_first_run_errors.py:221-236`) only proves the guard against a blocker socket that sets `SO_EXCLUSIVEADDRUSE` — i.e., it pins the guard against a scenario the guard's own docstring ("a second `kimcad web`") does not match. Verified by code inspection: no `allow_reuse_address` override exists anywhere in `webapp.py`.

**Why this matters**
The guard's headline case — a user double-launching `kimcad web`, the most likely first-run port collision — is exactly the case where it never fires on the only platform the product targets. The user sees two "KimCad web UI on http://127.0.0.1:8765" banners and a browser that talks to whichever server wins each connection: stale designs, vanishing progress polls, baffling behavior with no error anywhere.

**Blast radius**
- Adjacent code: `serve()` is the only bind site; the fix is local. The friendly-message wrapper itself is fine and stays.
- Shared state: two processes writing `output/web/<rid>` with independent counters can collide on rids.
- User-facing: the double-launch flow; also anything else that binds 8765 with SO_REUSEADDR.
- Tests to update: `test_serve_port_in_use_raises_friendly_runtime_error` must gain a second case — blocker socket created the way a real second KimCad would (or spawn `serve` twice) — and assert the second bind raises.
- Related findings: none.

**Fix path**
Subclass: `class _Server(ThreadingHTTPServer): allow_reuse_address = False` on Windows (or set `SO_EXCLUSIVEADDRUSE` in an overridden `server_bind`). Keep `allow_reuse_address` on POSIX where it only relaxes TIME_WAIT. Then the existing `except OSError` → friendly message works as designed.

---

### [ENG-002] — Major — Correctness — OpenAI SDK default `max_retries=2` stacks under the project's retry loop and dilutes the QA-002 fail-fast (verifies WALK-A-002)

**Evidence**
`llm_provider.py:210` builds `OpenAI(base_url=..., api_key=key, timeout=timeout)` without `max_retries`. The SDK defaults to `max_retries=2` and internally retries `APIConnectionError`/`APITimeoutError` with exponential backoff before the exception ever reaches `_complete`'s loop (`llm_provider.py:225-241`).

**Why this matters**
Two contracts in this very diff are quietly weakened: (1) the QA-002 fail-fast — "attempt 1" against a dead server is really 3 SDK connection attempts at the new 5 s connect timeout plus backoff, so "fails an attempt in seconds" is in practice ~15–20 s before the probe even runs; (2) the worst-case budget — 6 outer attempts × 3 inner tries means up to 18 connects and a wait noticeably longer than the documented ~6×30 s. With `FallbackProvider` (primary `max_attempts=1`) the dead-primary handoff still eats the inner-retry tax on every fresh request thread.

**Blast radius**
- Adjacent code: every `_complete` caller (plan, OpenSCAD codegen, CadQuery codegen); `FallbackProvider._call`'s handoff latency; the CLI and web model-down paths inherit the delay.
- User-facing: time-to-friendly-error on the dominant first-run failure (Ollama not started).
- Tests to update: `test_never_up_server_fails_fast_no_retry_loop` uses a fake client, so it cannot catch this; consider one test constructing the real client and asserting `client.max_retries == 0`.
- Related findings: ENG-003 (same `_complete` retry machinery).

**Fix path**
Pass `max_retries=0` in `_build_client` — the project owns its retry policy (`max_attempts`/`retry_wait_s`); two uncoordinated retry layers is one too many. If a vestige of SDK-level retry is wanted for cloud 5xx, set it per-backend, deliberately.

---

### [ENG-003] — Major — Correctness — `_server_reachable` mis-grounds the fail-fast decision for cloud and proxied backends (TCP-only probe, proxy-blind)

**Evidence**
`llm_provider.py:243-256`: on a *first-attempt* connection/timeout error, `_complete` dials `socket.create_connection((host, port))` derived from `backend.base_url` — including when the backend is a **cloud** one (`https://openrouter.ai/api/v1` → raw TCP to `openrouter.ai:443`). The OpenAI client's httpx transport honors `HTTPS_PROXY`/`HTTP_PROXY` (trust_env default); the raw socket does not.

**Why this matters**
Two misclassification directions, both on the supported cloud/OpenRouter path (and the `FallbackProvider` alt path):
1. **Proxy-only egress** (corporate network): the real request goes via the proxy; the probe's *direct* TCP dial is firewalled and fails → every first-attempt cloud connection error — including a genuinely transient one the 6×30 s budget exists to bridge — is classified "never up" and raised immediately. The retry contract is silently repealed for exactly these users.
2. **CDN-fronted hosts**: TCP to :443 on an anycast edge succeeds even when the service/TLS/origin is hard-down → a permanently failing cloud backend keeps the full multi-minute retry budget, the opposite of fail-fast.
Secondarily, the probe is an un-proxied egress side-channel: it dials external hosts directly, bypassing configured proxy policy (a low-grade compliance smell, and a 2 s stall per misfire). It sends no data, so there is no secret exposure.

**Blast radius**
- Adjacent code: `_complete` (the `attempt == 1` branch); `FallbackProvider` (a fast-raised primary error *helps* handoff, but the alt backend's own probe has the same flaw); the CLI/web model-down mapping treats the raised `APIConnectionError` as "Ollama down" and prints **Ollama** advice even when the failing backend was cloud (see ENG-006 for the message side).
- User-facing: cloud-backend users behind proxies (fail-fast where retry was promised); cloud users during provider incidents (4-minute hang where fail-fast was promised).
- Tests to update: add cases for an `https` base_url; assert the probe is skipped (or its result ignored) for non-local backends.
- Related findings: ENG-002 (same loop), ENG-006 (Ollama-specific advice on a generic connection error).

**Fix path**
Scope the fail-fast to what it was designed for — the *local* server case. Cheapest honest rule: run the probe only when the host is loopback/private (`localhost`, `127.0.0.1`, `::1`); for any other host, keep the pre-existing full-retry behavior. (Alternative: probe via httpx with trust_env so proxies are honored — but that re-adds HTTP semantics the comment explicitly avoids; the loopback scope is simpler and matches QA-002's stated intent: "Ollama not started".)

---

### [ENG-004] — Major — Correctness — CI gate integrity: intermediate PowerShell command failures don't fail steps, and the "no green-by-skip" step doesn't assert what it claims

**Evidence**
`.github/workflows/ci.yml`:
1. With `shell: powershell`, GitHub Actions fails a step only on the **last** command's exit code; native-command failures mid-script pass silently. In "Provision Python venv" (lines ~46-53), if `pip install -r requirements.lock` fails, the following `pip install --no-deps -e .` can still succeed and the step goes green on an unpinned/broken env. Same pattern risk in the other provision steps. The gate step is the only one that explicitly checks `$LASTEXITCODE`.
2. "Assert the live tool contracts actually ran" (lines ~77-84) captures `pytest -m live --collect-only -q` into `$out`, prints it, and never inspects it — no assertion on collected count, and `$LASTEXITCODE` from the pytest collect is ignored (pytest exits 5 on zero collected). The real assertions in the step are only file-existence (`orca-slicer.exe`) and interpreter discovery. The step *name* overclaims.

**Why this matters**
This workflow's whole reason to exist (per its own header) is to be the authoritative, can't-go-green-by-skip gate. Both gaps are silent-pass gaps: a provisioning failure that leaves a stale cached venv, or a marker/collection regression that quietly empties the live suite, produces a green run that proved less than it claims. On a self-hosted runner with persistent `_work` caches, stale-env drift is the *likely* failure mode, not a theoretical one.

**Blast radius**
- Adjacent code: every `shell: powershell` step in `ci.yml`; the trust statements in the workflow header comment and in `scripts/ci.sh`'s header (ENG-007).
- Shared state: the persistent self-hosted workspace caches (`.venv`, `.venv-cq313`, `tools/`, `node_modules`) — exactly what un-failed provisioning can leave half-built.
- User-facing: none directly; this is release-confidence infrastructure.
- Tests to update: none in pytest; the fix is in the workflow.
- Related findings: ENG-005 (same file), ENG-007/ENG-008 (same file, hygiene).

**Fix path**
Add `$ErrorActionPreference = 'Stop'` plus an explicit `if ($LASTEXITCODE -ne 0) { throw }` after each native command (or a tiny `Invoke-Checked` helper / `Set-StrictMode` + per-command checks — the explicit check is what actually covers native exes). In the assert step, parse the collect output (e.g. match `(\d+) tests collected`, throw if 0 or if `$LASTEXITCODE -ne 0`).

---

### [ENG-005] — Major — Security — `pull_request` trigger on a self-hosted runner is latent RCE on the dev box (currently contained by repo privacy)

**Evidence**
`.github/workflows/ci.yml` lines ~22-25: `on: push / pull_request / workflow_dispatch`, `runs-on: [self-hosted, kimcad-windows]`. The runner lives in the developer's logon session on the dev box (per the workflow's own caveat), which is also the deployment target and holds an authenticated `gh` keyring. Verified the repo is currently **private** (`gh repo view` → `"isPrivate": true`), so no outside fork can open a PR today.

**Why this matters**
The classic self-hosted-runner attack — a fork PR whose workflow/test code executes arbitrary commands on the runner — is fully assembled here and disarmed by exactly one setting (repo visibility) that the roadmap's open-source posture (LICENSE/SECURITY.md landed in this very diff) suggests may flip. If the repo goes public, any GitHub account gets code execution as `scott` on this machine by opening a PR. No `${{ }}` expression-injection issues were found in the workflow itself (the only expansion, `github.ref`, is in `concurrency`, not a script), and no secrets are referenced.

**Blast radius**
- Adjacent code: the workflow trigger block only.
- Shared state: the entire dev box — credentials in keyring, the deployment target itself.
- User-facing: none today; catastrophic if visibility flips without this fixed.
- Migration: none — trigger-block edit.
- Related findings: ENG-004 (same file).

**Fix path**
Now, while private: drop `pull_request` (push already covers every branch) or guard the job with `if: github.event.pull_request.head.repo.full_name == github.repository`. Also confirm the repo/org setting "require approval for fork PR workflows" stays at its restrictive default. Add a line to SECURITY.md's release checklist: re-audit CI triggers before any visibility change.

---

### [ENG-006] — Minor — Correctness — CLI recovery advice hardcodes `gemma4:e4b` and points at the wrong surface

**Evidence**
`cli.py:507` and `cli.py:514` both bake in `` `ollama pull gemma4:e4b` `` regardless of the configured `model_name`; the model-unreachable path also prints `MODEL_UNAVAILABLE_MESSAGE` (`pipeline.py:180-183`), which ends "You can check the AI's status in Settings" — a web-UI affordance, shown here on the CLI. And per ENG-003, a *cloud* backend's connection error currently receives "Start Ollama" advice.

**Why this matters**
A user who configured a different model (the `kimcad models` recommender exists precisely to encourage that) gets a recovery command that pulls the wrong ~8 GB model. Wrong-but-confident advice is worse than generic advice in a first-run flow built on trust.

**Fix path**
Thread the active backend's `model_name` (and locality) into the message — `config` is already in scope in `main`'s handler. Suggest "check `kimcad models`" instead of "Settings" on the CLI surface.

---

### [ENG-007] — Minor — Hygiene — `scripts/ci.sh` header now misdescribes hosted CI

**Evidence**
`scripts/ci.sh:2-7` still says hosted CI "is an intentionally PARTIAL smoke check (Python lint + pytest only, Linux) and is not equivalent" — but this diff rewrote `ci.yml` to a self-hosted Windows runner that executes `scripts/ci.sh` itself as the authoritative gate.

**Why this matters**
The two files now make contradictory trust claims about which gate is authoritative. The next person debugging a CI discrepancy will be misled by the stale header.

**Fix path**
Rewrite the ci.sh header to match the new reality (one script, two invokers: pre-push hook and the self-hosted workflow).

---

### [ENG-008] — Minor — Hygiene — Machine-specific absolute paths baked into the workflow

**Evidence**
`ci.yml` env: `KIMCAD_PY_LAUNCHER: C:\Users\scott\AppData\Local\Programs\Python\Launcher\py.exe`, `KIMCAD_CI_NODE: C:\kimcad-ci-tools\node22`, plus `C:\Program Files\Git\bin\bash.exe` in the gate step. Documented as deliberate for the one-box setup.

**Why this matters**
Acceptable for the stated single-runner trust model, but the workflow silently breaks on any runner replacement/reinstall (e.g., a system-wide Python install moves the launcher). Low cost to make the failure loud.

**Fix path**
Keep the pins but add a first step that asserts each pinned path exists and throws a one-line "runner not provisioned per docs" error; or read them from runner-machine environment/runner labels.

---

### [ENG-009] — Minor — Correctness — Ctrl+C during a multi-minute CLI run prints a raw traceback

**Evidence**
`cli.main` (`cli.py:476-521`) correctly leaves `BaseException` alone — `KeyboardInterrupt` is not swallowed (good) — but nothing above it catches it either, so the canonical first-run action "this is taking forever, Ctrl+C" ends in a `KeyboardInterrupt` stack trace, in a slice whose stated goal is "never a traceback" for first-run flows.

**Why this matters**
Cosmetic but squarely inside Stage A's own success criterion; generations take minutes on the CPU target, so Ctrl+C is a common, normal exit.

**Fix path**
In the `__main__` guard / console entry, wrap: `except KeyboardInterrupt: print("\nCancelled.", file=sys.stderr); return 130`. Do not catch it inside `main`'s mapping block.

---

### [ENG-010] — Nit — Correctness — ToolMissingError guard has a TOCTOU window (assessed: acceptable)

**Evidence**
`openscad_runner.py:293-294` and `slicer.py:205-206` check `Path(binary).is_file()` then spawn. A binary deleted (or an antivirus quarantine landing) between check and spawn yields the old raw `FileNotFoundError`, now mapped to the generic 500/log path rather than the friendly message. Hunted per the gate brief; the window is microseconds and the guard is a UX affordance, not a security control — sanitization runs first regardless. Also verified the guard cannot false-positive on PATH-style bare names: `Config.binary_path` always resolves to an absolute path (`config.py:127-131`), so bare-command configs were never supported.

**Fix path** (optional)
Additionally catch `FileNotFoundError` around the spawn and re-raise as `ToolMissingError` — belt and suspenders; not required for the gate.

---

### [ENG-011] — Nit — Correctness — Probe/wizard micro-edges

**Evidence**
(a) `_server_reachable` on a scheme-less/odd `base_url` falls back to `localhost:80` (`llm_provider.py:250-251`) — a misprobe rather than a crash; config validation likely prevents this upstream. (b) `FirstRunWizard.checkModel` (`FirstRunWizard.tsx:48-56`) has no cancellation, so a "check again" click racing the step-5 auto re-probe can resolve out of order and briefly show the staler result. (c) `modelOk` derivation is duplicated between the wizard and `ModelHealthPill` — drift risk if the readiness rule changes.

**Fix path** (optional)
Share a `isModelReady(m)` helper in `api.ts`; sequence-stamp the probe responses if it ever matters.

---

### [ENG-012] — Nit — Hygiene — `push` + `pull_request` double-runs every PR commit

**Evidence**
`ci.yml` triggers on both; the `concurrency` group keys on `github.ref`, which differs between the branch push (`refs/heads/...`) and the PR merge ref (`refs/pull/N/merge`), so both run, serialized only by the single runner.

**Fix path** (optional)
Scope `push` to the default branch, or drop `pull_request` (which ENG-005 recommends anyway — fixing ENG-005 fixes this).

---

## Patterns and systemic observations

1. **Guards verified against a stand-in, not the real adversary.** The port guard is tested against an `SO_EXCLUSIVEADDRUSE` blocker (not a second KimCad); the fail-fast is tested with a fake client (so the SDK's internal retries are invisible); the CI "assert" step prints instead of asserting. ENG-001/002/004 share this root: the test proves *a* failure mode, the code claims *the* failure mode. When a guard's docstring names a scenario, the test should construct that scenario.
2. **The local-first assumption leaks into generic paths.** The probe (ENG-003) and the recovery copy (ENG-006) both assume "connection error ⇒ Ollama," but the same code path serves cloud backends. A single `backend.is_local`-style predicate, consulted by both the probe and the message chooser, would fix the family.
3. **The CI rewrite is honest about its trust model but not yet defensive about it.** The header comment is admirably candid (one box, one user, runner in the logon session). ENG-004/005/008 are all "make the honest assumption loud or enforced" items — cheap now, expensive after a visibility flip or a runner rebuild.

## Dependency snapshot

Stage A adds no new dependencies. `httpx` (used for the `Timeout` split) ships with the `openai` SDK already in the tree; `pip-audit` is installed transiently in CI. `requirements.lock` (new, 34 lines) pins the runtime set and CI now scans it with `pip-audit --strict` — a posture improvement. No CVE scan was executed in this audit seat (see "What couldn't be assessed").

| Dependency | Version | Concern |
|---|---|---|
| openai (SDK) | per requirements.lock | Default `max_retries=2` interacts with the project retry loop (ENG-002) — config issue, not a CVE |
| httpx | transitive via openai | none |

## Appendix: artifacts reviewed

- `git diff 414d22a..5aad7f3` (full), `git log` of the 10-commit range
- `src/kimcad/errors.py`, `cli.py` (full main + design path), `llm_provider.py` (full), `openscad_runner.py` (render_scad), `slicer.py` (slice_model), `webapp.py` (serve, `_handle_design`, slice/send/rerender handlers, lock/progress plumbing), `cadquery_runner.py` (interpreter discovery), `config.py` (binary_path)
- `pipeline.py` (`MODEL_UNAVAILABLE_MESSAGE`, `_is_model_unreachable`)
- `frontend/src/App.tsx`, `components/FirstRunWizard.tsx`, `ModelHealthPill.tsx`, `Landing.tsx`, `styles.css`; `App.test.tsx` / `Workspace.test.tsx` (skip-link assertions)
- `.github/workflows/ci.yml`, `scripts/ci.sh`, `scripts/fetch_tools.py` (pin)
- `tests/test_first_run_errors.py` (full)
- `docs/getting-started-windows.md`, `docs/troubleshooting.md` (spot-checked against code strings)
- `gh repo view` (visibility check for ENG-005)
