# GauntletGate — Full lane · Test Engineer deep-dive

**Project:** KimCad · **Commit under gate:** `09b979c` (0.9.0b4 + cold-start managed-Ollama onboarding + b4+UI audit-watchlist remediation)
**Baseline:** `c784a23` (0.9.0b4 tag) · **Date:** 2026-06-17 · **Lane:** Full / Test role
**Focus:** test-coverage reality vs claim, blind spots, shortcuts, regression risk in the change delta.
**Division of labor:** I ran the LIGHT suite only (ruff + unit pytest subset + vitest) plus targeted adversarial probes. The QA role owns the one authoritative live OrcaSlicer end-to-end run — I did NOT re-run it.

---

## Verdict

The new code is **well-tested at the unit/orchestration layer** and the headline cold-start fix is real (the Walkthrough lane drove it live; the SHA-256 pin is independently verifiable; the `is_local` regression is pinned adversarially). **No Blocker, no Critical from the test lane.** The advancement-relevant defects are two **Major** items: (1) the in-code claim that "the REAL fetch+serve path is exercised by a `real_tool` integration test" overstates the automated coverage — the auto-run test only proves the *reuse* branch, while the genuinely new/risky fetch→extract→spawn→serve path is manual-only and its one manual verify script self-reported `FAIL`; and (2) the primary cold-start onboarding path (`start_setup`) silently dropped the disk-space pre-check that the legacy `start()` path performs, untested either way.

---

## Light suite — REAL output (all green)

**ruff** (`.venv/Scripts/python.exe -m ruff check src tests`):
```
All checks passed!
```

**unit pytest subset** (`-m 'not real_tool' tests/test_ollama_fetch.py tests/test_ollama_runtime.py tests/test_model_pull.py tests/test_webapp.py`):
```
182 passed, 2 deselected in 80.73s (0:01:20)
```

**vitest** (`frontend`, via the kimcad node22 toolchain `C:\kimcad-ci-tools\node22`):
```
Test Files  33 passed (33)
     Tests  405 passed (405)
  Duration  22.92s
```

**Ollama-gated real test** (`tests/test_ollama_runtime_real.py` — ran, NOT skipped, on the live box):
```
tests\test_ollama_runtime_real.py ..                                     [100%]
2 passed in 0.15s
```

Total collection: **1657 tests** (318 deselected under `not live and not real_tool and not needs_browser`). No `xfail`/`skip` hidden in the new unit test files.

---

## Findings

### TEST-GG-001 — "real_tool integration test" claim overstates automated fetch+serve coverage — **Major**

**Evidence.**
- `src/kimcad/ollama_runtime.py:18` and `src/kimcad/ollama_fetch.py:16` both assert "the REAL fetch+serve path is exercised by a `real_tool` integration test."
- The only auto-run integration test is `tests/test_ollama_runtime_real.py`. On the dev box Ollama is already up — I verified the branch it actually takes:
  ```
  is_server_up(default): True
  resolve_ollama_exe: C:\Users\scott\AppData\Local\Programs\Ollama\ollama.EXE
  ensure_serving -> OllamaStatus(running=True, source='already-up', exe=None)
  ```
  So `test_ensure_serving_reuses_or_starts_the_real_ollama` returns via the **`already-up`** branch (`ollama_runtime.py:186-187`). It NEVER reaches `start_serve` (real `ollama serve` spawn), NEVER reaches the resolve→start→poll-until-healthy branch, and NEVER touches `ollama_fetch.fetch_portable_ollama`. The one branch it covers (detect-and-reuse a running server) is the least likely to break.
- The real fetch path is explicitly NOT auto-run; `tests/test_ollama_runtime_real.py:11-14` defers it to a manual run recorded in `docs/audits/coder-ui-qa-test-coldstart-2026-06-17/`. That run's own log (`VERIFICATION-LOG.md:29`) states the throwaway verify script **printed `RESULT=FAIL`** (rationalized as a cosmetic post-delete `exe.exists()` ordering bug). This is the exact "the tool said FAIL, we decided it was cosmetic" shape the b5 false-green lesson warns against.

**Why it's not worse than Major.** The orchestration IS genuinely unit-tested with injected effects (`test_ollama_runtime.py` 14 tests; `test_model_pull.py` start_setup suite covers cold-fetch-then-pull, fetch failure, serve-never-healthy). The SHA-256 pin is independently correct (see What's working). Crucially, the **Walkthrough lane drove the real `/api/model-pull` live against real GitHub** and observed `total:1,461,613,335` with `completed` climbing 52→134 MB and a partial zip landing in the managed dir (`02-walkthrough.md:44`) — so the real fetch DID execute live this gate, just not inside pytest. The defect is the **misleading in-code claim** + **no CI guard** on the spawn/poll branches, not a total coverage void.

**Blast radius.** If a future change breaks `start_serve` arg construction, the `resolve→start→poll` loop bound, or the fetch extract/exe-resolution, **no automated test fails** — it surfaces only on a real cold machine (the highest-stakes first-run path). The reuse-branch green light gives false confidence.

**Fix path.** (a) Correct the docstrings to state honestly that the auto-run real test covers only the reuse branch; the spawn+fetch are covered by injected-effect unit tests + a recorded manual run. (b) Add a `real_tool`/Ollama-gated test that forces the spawn branch — e.g. point `ensure_serving` at a dead loopback port with `resolve` returning the real exe so it actually runs `ollama serve` on an alternate `OLLAMA_HOST` and polls to healthy, then tears it down (the manual run already did exactly this on `:11456`). (c) Fix or delete the manual verify script so it never prints `FAIL` on success — a script that cries FAIL trains the team to ignore FAIL.

**Suggested test.** `test_ensure_serving_spawns_real_serve_on_alt_port` (Ollama-gated): resolve the real exe, `start_serve(exe, host="127.0.0.1:<free>")`, assert `is_server_up` flips True within `wait_s`, then terminate the child.

---

### TEST-GG-002 — `start_setup` (the primary cold onboarding path) dropped the disk-space pre-check — **Major**

**Evidence.**
- The legacy `ModelPullJob.start()` performs a deliberate disk pre-check that fails friendly BEFORE gigabytes move (`model_pull.py:121-140`; tested by `test_the_disk_precheck_fails_friendly_before_any_download`, `test_disk_precheck_measures_the_ollama_models_drive`). The module docstring sells this: "the disk is pre-checked against rough model sizes so the common case fails BEFORE gigabytes are downloaded" (`model_pull.py:13-15`).
- The new one-click `start_setup` → `_run_setup` Phase 2 calls `_pull_one` directly (`model_pull.py:268-272`) with **no disk pre-check**, and the Phase-1 engine fetch (`fetch(managed_dir, …)`, `model_pull.py:224`) also has none. So the *primary* cold-start flow ("Set up KimCad's AI") begins the ~1.4 GB engine + ~7.7 GB model downloads and only fails mid-stream via `_friendly_error`'s "disk filled up" mapping — the slow, late failure the pre-check existed to avoid.
- No test asserts disk behavior for `start_setup` either way (grep of `tests/test_model_pull.py`: the disk-precheck tests only call `start()`).

**Blast radius.** The most common real failure (a user on a small/full SSD clicking the headline onboarding button) now downloads gigabytes before failing, instead of failing fast — a UX regression on the exact flow this commit exists to make good. Not data loss, not a security issue; bounded to a degraded failure experience on constrained disks.

**Fix path.** Factor the disk pre-check into a helper and call it at the top of `start_setup` (sum engine ≈1.4 GB + missing-model sizes against the OLLAMA_MODELS/managed drive) before kicking the thread. **Suggested test:** `test_setup_disk_precheck_fails_before_fetch_or_pull` — monkeypatch `shutil.disk_usage` low, assert the engine row goes `error` with "Not enough disk space" and neither `fetch` nor the opener was ever called.

---

### TEST-GG-003 — `_deny_network` is never exercised through the real worker `_run` path — **Minor**

**Evidence.** `tests/test_cadquery_worker.py` (2 tests) calls `cadquery_worker._deny_network()` in **isolation** in a subprocess and proves socket creation is blocked + idempotent. No test asserts `_deny_network()` is actually *invoked inside* `_run()` (the call site is `cadquery_worker.py:177`) during a real script execution. `tests/test_trust_boundary.py:128` only statically greps the worker source for keyring/settings imports. If a refactor deleted the line-177 call, every existing test stays green.

**Why Minor.** This is a documented *secondary* defence-in-depth layer; the *primary* layer (the static sanitizer) genuinely closes the `__globals__`/socket escape class and IS well-tested (`tests/test_cadquery_runner.py` covers `subprocess` import block, dunder-escape, `cq.exporters.os.system`, and the `x["__globals__"]["__import__"]` string-literal hide). So losing the deny-network hook silently would not reopen a reachable exploit, only erode depth.

**Fix path.** Add an assertion that the call site fires — e.g. a worker-level test that runs a sanitizer-bypassing script (constructed namespace) attempting `socket.socket()` *through `_run`* and confirms it's blocked; or a cheaper static guard asserting `_deny_network()` appears before `exec(` in source. **Suggested test:** `test_run_invokes_deny_network_before_exec`.

---

### TEST-GG-004 — zip-slip test covers only `../`, not Windows-absolute or embedded traversal — **Minor**

**Evidence.** `test_fetch_rejects_zip_slip` (`tests/test_ollama_fetch.py:92`) only exercises a single `../evil.txt` member. The implementation is broader and correct — I proved it adversarially:
```
BLOCKED: 'C:/Windows/Temp/evil.txt' -> refusing to extract unsafe path…
BLOCKED: '../../evil2.txt'           -> refusing to extract unsafe path…
BLOCKED: 'foo/../../evil3.txt'       -> refusing to extract unsafe path…
BLOCKED: 'lib/../../../evil4.txt'    -> refusing to extract unsafe path…
```
So `_safe_extract`'s `resolve()` + `relative_to(dest)` correctly defeats drive-absolute paths and embedded `..` on Windows. The behavior is right; the *test* under-samples the threat class, so a regression to a naive `name.startswith("..")` prefix check would pass the suite while reopening the drive-absolute path.

**Fix path.** Parametrize `test_fetch_rejects_zip_slip` over `["../evil", "C:/Windows/evil", "lib/../../evil", "..\\..\\evil"]`. (Symlink members are not a concern: `_safe_extract` writes member *content* via `open(target,"wb")`, never creates a symlink.)

---

### TEST-GG-005 — `start_setup` idempotent-while-running guard is unverified — **Minor**

**Evidence.** `start_setup` guards against a second concurrent run (`model_pull.py:191-192`, returns the running snapshot), but `test_start_is_idempotent_while_running` and `test_concurrent_starts_never_fork_a_second_pull` only exercise `start()`, not `start_setup()`. A wizard re-mount mid-setup relies on this guard; it's load-bearing for the cold path and untested on that method.

**Fix path.** Add `test_setup_is_idempotent_while_running` mirroring the existing `start()` idempotency test against `start_setup` (block the fetch/serve, fire two `start_setup` calls, assert one worker).

---

### TEST-GG-006 — `PORTABLE_SIZE_BYTES` is ~1 MB off the real asset size — **Nit**

**Evidence.** Real asset `size` = `1461613335` bytes (GitHub API, below); `PORTABLE_SIZE_BYTES = 1393 * 1024 * 1024 = 1,460,617,216` — off by ~996 KB. It's only the progress-bar fallback when `Content-Length` is absent; integrity is by SHA-256 and the live server sends Content-Length (the walkthrough saw the exact `1,461,613,335`), so the constant is never used in practice. Cosmetic.

---

## What's working (honest signal — credit where due)

- **The SHA-256 pin is real and independently correct.** I verified `PORTABLE_SHA256` (`ollama_fetch.py:37`) against the live GitHub release asset digest:
  ```
  gh api repos/ollama/ollama/releases/tags/v0.30.9 …
  {"digest":"sha256:6d83cbe1db06ec659e7f47c0897318d2093128bcbb7c5d140c142e71d65f991f",
   "name":"ollama-windows-amd64.zip","size":1461613335}
  ```
  Exact match. The "verify-before-extract, reject on mismatch" logic is unit-tested (`test_fetch_rejects_hash_mismatch_without_extracting` asserts nothing extracts AND the temp is cleaned). This is the opposite of a command-string assertion — it's a genuine, checkable integrity pin.
- **ENG-COLD-002 regression is pinned adversarially, not tautologically.** `test_model_status_local_on_nondefault_port_is_local` (`test_webapp.py:2877`) uses `provider="openai_compatible"` (so the `provider=="ollama"` shortcut can't mask the bug) on `:11500`, asserts `backend=="local"`, asserts the dead port was actually PROBED (`running:false`), and pins the probed URL. It genuinely fails if anyone reverts to `"11434" in base_url`. The companion `test_model_status_cloud_backend_reports_cloud` proves a cloud backend is NOT probed. Strong pair.
- **The b4+UI watchlist remediation is tested.** ENG-001 cloud-host validation (4 tests in `test_llm_provider.py:398-438` covering refuse-unlisted-host, allow-shipped, escape-hatch, keyless-not-gated) and ENG-007 wedged-but-listening fail-fast (`test_native_plan_path_fails_fast_on_wedged_but_listening_server`, asserts the short budget bounds the call) both have real coverage.
- **The model-pull adversarial/trust tests are excellent.** `is_loopback_url` pins `127.evil.example` as NOT loopback (`test_native_root_and_loopback_helpers`); the pull list is fixed server-side and an attacker `{"model":"evil/backdoored"}` body changes nothing (`test_pull_ignores_an_attacker_named_model_in_the_body`); demo mode and non-loopback backends are refused (`test_pull_refuses_demo_mode`, `test_pull_refuses_a_non_loopback_backend`); a 2 MiB body deterministically gets a typed 413 (the loop hardens the 2026-06-13 latent-RST flake); `_friendly_error` clips untrusted upstream text to [:300] (proven at both the stream and unit boundary).
- **The cold one-click setup orchestration is genuinely unit-tested with injected effects** (`test_setup_cold_fetches_runtime_then_pulls` proves fetch bytes ride the engine row, serve flips `is_up`, both models pull; `test_setup_fetch_failure_marks_engine_error`; `test_setup_serve_never_healthy_errors`; `test_setup_server_already_up_pulls_missing_only`). The b5-lesson discipline (inject the effect, don't mock it away) is followed — the gap is only the *real-binary* edge (TEST-GG-001), not the logic.
- **Frontend cold-path coverage is real.** `FirstRunWizard.test.tsx` proves: cold (Ollama down) offers one-click "Set up KimCad's AI" with NO "Get Ollama" dead-end (line 260), recap routes to in-app setup with no `ollama pull` homework (line 176), and the shared `disposedRef` poll-cleanup-on-unmount (line 236) — which covers BOTH the download and setup flows since they share the timer code. 405 vitest tests green.
- **The worker network-deny + sanitizer split is honestly framed.** The sanitizer (primary layer, well-tested escape-class) actually closes the `__globals__` class; `_deny_network` is correctly labeled defence-in-depth and proven in a fresh subprocess (not patching the pytest process's own socket).

---

## Could not assess

- **The real OrcaSlicer end-to-end slice/print path** — out of scope by design; the QA role owns the single authoritative live run. I did not run the `live`/`real_tool` (OrcaSlicer/OpenSCAD) suites.
- **The real portable-Ollama fetch→extract→spawn→serve on a truly cold machine** — not auto-run anywhere; I confirmed (TEST-GG-001) the auto test only covers reuse. The Walkthrough lane corroborated the *fetch* live this gate; the *spawn/poll-to-healthy* of a freshly-fetched portable binary remains covered only by injected fakes + a prior manual run.
- **Browser e2e (`needs_browser`)** — not run this lane (Playwright suite); the Walkthrough lane drove the live UI separately.
- **CI wiring of the new tests** — `.github/workflows/ci.yml` changed (+23) but I did not execute the workflow; whether the gated `real_tool`/Ollama tests run in CI on a box with Ollama vs skip there was not verified end-to-end (the local run proves they execute when Ollama is present).
