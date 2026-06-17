# GauntletGate — Full lane / Engineering deep-dive

**Project:** KimCad · **Commit under gate:** `09b979c` (0.9.0b4 + cold-start managed-Ollama onboarding + b4+UI audit-watchlist remediation)
**Baseline:** tag `c784a23` (0.9.0b4) · **Date:** 2026-06-17 · **Role:** Principal Engineer (architecture, correctness, security, performance, data provenance, dependencies)
**Method:** read the full delta (`git diff c784a23..HEAD`, 84 files / +4954 −576), read the new managed-runtime modules line-by-line, ran the new + adjacent test suites against the REAL tools on this box, and verified the load-bearing security claims empirically (SHA-256 pin vs the actual GitHub asset; loopback classification against an adversarial host set; `_deny_network` in a fresh subprocess; the live Ollama integration test).

This lane EXTENDS the Walkthrough lane (`02-walkthrough.md`), which proved the cold first-run UI reaches the core feature. I did not re-walk the UI; I scrutinized the code behind it.

---

## Verdict

**Advance with fixes.** The headline security work is genuinely solid — the integrity pin is real and verified, the loopback-classification fix closes the ENG-COLD-002 bug class with no bypass I could find, and `_deny_network` does deny at the Python level in a real subprocess. No Blocker. **One Critical**: the managed `ollama serve` child is never torn down, directly contradicting the module's own "stop it with the app / no orphan process" contract — a leaked background server on every cold-start machine. Plus two Majors (no disk pre-check on the new one-click path; a cosmetic size constant) and minors below.

---

## Severity roll-up

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

---

## Findings

### ENG-GG-001 — Managed `ollama serve` child is never stopped (orphan process; contract violated) — **CRITICAL**

**Evidence.**
- `ollama_runtime.py:12` (module docstring) promises: *"start `ollama serve` as a **managed subprocess**, health-check it, and **stop it with the app**."*
- `start_serve()` (`ollama_runtime.py:131-150`) returns the `subprocess.Popen` handle.
- But `ensure_serving()` calls `start(exe)` at `ollama_runtime.py:194` and **discards the return** — `OllamaStatus` (`ollama_runtime.py:153-160`) carries only `exe`, never the process handle. `ensure_serving_background._run` (`:213-217`) likewise drops it.
- Verified by inspection: `python -c "inspect.getsource(ensure_serving)"` → `start(exe)` with no assignment; `grep` for `CREATE_NEW_PROCESS_GROUP|JobObject|TerminateProcess|.terminate()|.kill()` across `src/kimcad/*.py` → **zero hits**. No Windows job-object, no atexit, no teardown anywhere.
- The two call sites that auto-start it tear down only the HTTP server, not the Ollama child:
  - `shell.py:133-137` `_on_closed` → `httpd.shutdown()` only (shell.py:14 docstring claims *"closing the app leaves no orphan process serving the design pipeline"* — true for the HTTP server, false for the Ollama child it just spawned at `shell.py:121`).
  - `webapp.py:2747-2749` `serve()` → no teardown of the child it spawned.

**Why Critical (not Major).** On Windows, `subprocess.Popen` children are **not** killed when the parent exits unless assigned to a job object — none is. So on exactly the machine this commit targets (cold start: no system Ollama running → KimCad fetches/starts the portable server, OR system Ollama installed-but-stopped → KimCad starts it), **closing KimCad leaves `ollama serve` running**, holding port 11434 and (for the portable build) a multi-GB resident server, indefinitely. The next KimCad launch silently reuses it (`is_up()` true), masking the leak, so it accumulates only across reboots — but it is a real, shipped resource leak and a direct, falsifiable contradiction of two docstrings. On the dev box this is invisible because a system Ollama is already running (`is_up()` short-circuits before any spawn), which is likely why it slipped the walkthrough.

**Blast radius.** Every cold-start / portable-engine user (the population this commit exists to serve). Orphaned headless server process per app close that started one; port 11434 held; on uninstall, the portable `ollama.exe` under `%LOCALAPPDATA%\KimCad\ollama\` may be locked by the running orphan, breaking clean uninstall.

**Fix path.** Capture and own the handle:
1. Have `start_serve` callers store the `Popen` (e.g. a module-level `_managed_proc` guarded by a lock, set only when KimCad *itself* started the server — never when reusing a system one).
2. On Windows, assign the child to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` (via `pywin32`/`ctypes`) so it dies with the parent even on a hard kill; as a floor, register an `atexit`/`weakref.finalize` that calls `proc.terminate()` and wire `shell.py`'s `_on_closed` + `serve()`'s shutdown to stop it.
3. Only tear down a server KimCad started — reusing the user's system Ollama must touch nothing (the existing `source=="already-up"` distinction already tells you which).

**Suggested test.** Unit: inject a fake `spawn` returning a recording handle; assert the teardown path calls `terminate()` exactly when `source in {"started"}` and never when `"already-up"`. Real-tool: on a box where Ollama is installed but stopped, `ensure_serving()` then teardown → assert `is_server_up()` is False afterward (today it stays True).

---

### ENG-GG-002 — One-click cold setup skips the disk pre-check (the "fail before gigabytes move" guarantee is lost on the new path) — **MAJOR**

**Evidence.**
- The disk pre-check (`shutil.disk_usage(...).free` vs `need_gb`, ~15 GB for chat+vision) lives ONLY in the legacy `ModelPullJob.start()` at `model_pull.py:124-140`.
- The new cold-start entry point `start_setup()` (`model_pull.py:153-203`) and its worker `_run_setup` (`:205-278`) go straight to `fetch_portable_ollama` (~1.46 GB) then `_pull_one` per missing model (~7.7 GB) with **no disk pre-check**.
- The module docstring (`model_pull.py:13-15`) advertises: *"the disk is pre-checked against rough model sizes so the common case fails BEFORE gigabytes are downloaded."* That promise is now false on the path most likely to hit it — a fresh machine, possibly space-constrained, running one-click setup.

**Impact.** A user with, say, 5 GB free clicks "Set up KimCad's AI", waits through a 1.46 GB engine download and a multi-GB model pull, and only then gets the friendly "no space" message from `_friendly_error` (`model_pull.py:64-67`) — after the time and bandwidth are spent and the disk is now even fuller. Not data loss, but a poor, slow failure on the flagship new flow; degrades the cold-start UX this commit was written to fix.

**Fix path.** Hoist the pre-check into `_run_setup` before Phase 1's fetch: estimate engine (~1.5 GB) + missing-model GB against the drive that will receive them (managed dir for the engine, `OLLAMA_MODELS`/`~` for models), and write a friendly engine-row error if short — reusing the existing `_EST_GB` and message.

**Suggested test.** Inject a `disk_usage` stub returning < needed; assert `start_setup` ends with an error row and `fetch`/`serve` were never called.

---

### ENG-GG-003 — `PORTABLE_SIZE_BYTES` fallback is ~0.9 MB short of the real asset — **MAJOR (cosmetic-progress; low severity but a correctness nit on a pinned constant)**

**Evidence.** `ollama_fetch.py:40` sets `PORTABLE_SIZE_BYTES = 1393 * 1024 * 1024 = 1,460,666,368`. The real `v0.30.9` asset is **1,461,613,335** bytes (verified: `gh api repos/ollama/ollama/releases/tags/v0.30.9`). The walkthrough's observed `total:1,461,613,335` came from the server's `Content-Length`, not this constant.

**Impact.** Purely the progress-bar denominator when the server omits `Content-Length` — GitHub always sends it, so in practice this never shows. If it ever did, progress would exceed 100% by ~0.06%. Integrity is the SHA-256, never the size (correctly stated in the comment). I rate this Major only because it sits in the same pinned-constants block as the security-critical SHA and should be kept exact; otherwise it's effectively a nit.

**Fix.** Set `PORTABLE_SIZE_BYTES = 1_461_613_335` (the actual asset size) and add a one-line provenance comment next to the SHA.

---

### ENG-GG-004 — `_deny_network` leaves real residual egress vectors (honestly documented, but worth naming precisely) — **MINOR**

**Evidence.** `cadquery_worker._deny_network` (`cadquery_worker.py:123-145`) replaces `socket`, `create_connection`, `create_server`, `socketpair` on both `socket` and `_socket`. It does NOT touch `socket.fromfd`, `socket.fromshare`, `socket.dup`, or `socket.getaddrinfo`, and cannot reach a reference captured before it ran. It runs at `cadquery_worker.py:177`, before `exec`, which is correct ordering.

**Assessment — this is defence-in-depth, and the code is honest about it.** The docstring (`:50-53`, and the module header `:46-57`) correctly states the PRIMARY layer is the static sanitizer (which blocks the `__globals__`/dunder/introspection escape class that is the *only* way a script reaches a smuggled socket reference in the first place), and that a pure-native Winsock bypass needs OS-level firewalling. I verified the block works in a real subprocess (`tests/test_cadquery_worker.py` passed: `socket.socket()` and `create_connection` both raise `PermissionError`). Given the sanitizer gates reachability, the un-blocked constructors are not independently exploitable through the documented threat model. Naming them keeps the "could not assess" honest rather than implying total closure.

**Fix path (optional hardening).** Also neutralize `fromfd`/`fromshare`/`dup`, or — cleaner — drop a single deny-all default into `socket.setdefaulttimeout`-style choke point is not enough; the durable fix is the tracked OS-level FS/network confinement (job object + restricted token / Windows firewall rule per worker). Keep on the watchlist; do not block on it.

---

### ENG-GG-005 — Duplicated loopback-classification logic across two modules — **MINOR**

**Evidence.** `config.Config._is_local_base_url` (`config.py:390-404`) and `model_pull.is_loopback_url` (`model_pull.py:50-59`) implement the same loopback/`localhost` IP parse independently. `_handle_model_pull` calls BOTH (`webapp.py:1634` and `:1636`) as an AND. I tested 11 adversarial hosts (`127.evil.example`, `127.0.0.1.attacker.com`, decimal `2130706433`, hex `0x7f000001`, `127.1`, `0.0.0.0`, link-local `169.254.169.254`, `[::1]`, empty) — **the two agree on every case** and both correctly reject the spoofs. So this is not a bypass risk today; it's a maintenance hazard (a future fix to one and not the other could desync the AND).

**Fix.** Have one delegate to the other (e.g. `model_pull.is_loopback_url` calls `Config._is_local_base_url`, or factor both into a shared `kimcad.netutil`).

---

### ENG-GG-006 — `start_serve` inherits the full parent environment into the child — **MINOR**

**Evidence.** `start_serve` (`ollama_runtime.py:144`) does `run_env = dict(os.environ ...)` then `setdefault("OLLAMA_HOST", host)`. The managed Ollama child therefore inherits every env var of the KimCad process, including any cloud `*_API_KEY` the user set for the LLM backend. Ollama doesn't read those, so there's no active exfiltration — but a headless server child carrying the user's cloud key in its environment is a needless secret-surface expansion for a local geometry/LLM runtime.

**Fix.** Pass a minimal env (PATH, SystemRoot, OLLAMA_HOST, and any genuinely needed Ollama vars) rather than the whole environment, mirroring the least-privilege posture the rest of the codebase takes.

---

### ENG-GG-007 — `_present` model-match could false-positive on a longer model name — **NIT**

**Evidence.** `_run_setup._present` (`model_pull.py:261-262`): `any(n == tag or n.startswith(tag + "-") for n in names)`. For `qwen2.5:7b` this matches `qwen2.5:7b` and `qwen2.5:7b-instruct` (intended). It would NOT mis-match `qwen2.5:70b` (different tag) because the separator is `-`, not a digit — so the guard is actually fine. Flagging only because the same pattern is duplicated from the webapp's old `_present` and is easy to get subtly wrong; no defect observed.

---

### ENG-GG-008 — `creationflags` only suppresses the console on the managed serve, not group isolation — **NIT**

`start_serve` sets `CREATE_NO_WINDOW` (`ollama_runtime.py:149`) but not `CREATE_NEW_PROCESS_GROUP`. Once ENG-GG-001's job-object teardown lands, this is moot; noting it so the teardown fix picks the right flag combo.

---

## What's working (verified, honest signal)

- **The SHA-256 integrity pin is REAL and exact.** `PORTABLE_SHA256` (`ollama_fetch.py:37`) = `6d83cbe1db06ec659e7f47c0897318d2093128bcbb7c5d140c142e71d65f991f` matches the live GitHub release digest for `v0.30.9` `ollama-windows-amd64.zip` byte-for-byte (`gh api repos/ollama/ollama/releases/tags/v0.30.9`). The hash is checked **before** any extraction (`ollama_fetch.py:108-114`), streamed to a temp file (never whole in RAM), and the temp is removed in a `finally` (`:123-124`). This is the b5 false-green lesson done right — verified against the real artifact, not asserted.
- **Zip-slip guard is correct.** `_safe_extract` (`ollama_fetch.py:47-65`) resolves each member against the resolved dest and `relative_to`-rejects any traversal; directory entries skipped; exact-member writes only. Matches the documented design_store discipline.
- **ENG-COLD-002 loopback fix is sound with no bypass found.** Both classifiers reject all 11 adversarial host forms I threw at them (above). The old `"11434" in base_url` substring bug is genuinely gone (`webapp.py:1634`, `:1681`).
- **`_deny_network` denies at the Python level, proven in a fresh subprocess** (`tests/test_cadquery_worker.py` — `socket.socket()` and `create_connection` both raise `PermissionError`; idempotent). Runs before `exec`. The two-layer sandbox docstring is unusually honest about what each layer does and does not guarantee.
- **Model-pull surface is correctly local-only AND behind the session-token guard.** `/api/model-pull` is in `_POST_ONLY_PATHS` → passes through the `hmac.compare_digest` session-token check (`webapp.py:1395-1405`) before reaching `_handle_model_pull`, which then re-gates on `is_local AND is_loopback_url` (`webapp.py:1633-1641`) and refuses demo mode (`:1616`). A drive-by cross-origin POST can't start a multi-GB download.
- **Single-source route table (ENG-005/008) is a clean refactor.** `_GET_ONLY_PATHS`/`_POST_ONLY_PATHS`/`_is_get_only` (`webapp.py:684-696`) genuinely de-duplicates the 405/Allow logic that was triplicated; the wrong-verb 405 now precedes the token guard for read-only paths only (`webapp.py:1392-1394`), which is correct (no state-changing route is exposed pre-token).
- **Disk-streaming refactor (ENG-006)** `_stream_file` (`webapp.py:903-925`) replaces `read_bytes()` for g-code/STEP/mesh downloads — `Content-Length` from `stat()`, 64 KiB `copyfileobj` chunks, HEAD-aware. Real RSS win on large artifacts; no correctness regression spotted.
- **Auto-start is genuinely off the launch path** (`ensure_serving_background` → daemon thread, swallow-all, `webapp.py:2749` / `shell.py:121`) and does not auto-fetch in the cold state (only `ensure_serving` → `needs-fetch` no-op), matching the walkthrough's "no surprise background download" observation.
- **Tests pass against real tools.** New suites: `test_ollama_fetch` + `test_ollama_runtime` + `test_model_pull` = 42 passed; `test_ollama_runtime_real` (drove the LIVE Ollama on this box) + `test_cadquery_worker` = 4 passed; `test_webapp` + `test_config` + `test_shell` = 176 passed. No flakes observed.
- **Frontend wiring is solid.** `FirstRunWizard.tsx` polls `/api/model-pull/progress` with a disposed-flag guard (`:89-133`), coarse a11y live region (`:136-155`), cleanup on unmount; re-probes so "Ready" is measured, not assumed.

## Could not assess

- **The real ~1.46 GB portable FETCH + extract + serve end-to-end** — not exercised this lane (the integration test deliberately skips it as wasteful per gate; it's recorded as manually proven in `docs/audits/coder-ui-qa-test-coldstart-2026-06-17/`). I verified the SHA pin matches the real asset, the zip-slip guard logic, and the live-Ollama serve path, but did not myself download the 1.46 GB blob to confirm extraction yields a working `ollama.exe`. Cross-checked against the Walkthrough lane, which observed real bytes streaming (`completed` 52→134 MB) and a partial zip landing in the managed dir.
- **Behavior when KimCad starts a system Ollama that is installed-but-stopped, then closes** — I confirmed by code-read that no teardown exists (ENG-GG-001) but did not stop my running system Ollama to observe the orphan live (would disrupt the box). The code path is unambiguous: the handle is discarded.
- **Native Winsock bypass of `_deny_network`** — out of scope for a Python-level review; tracked by the team as needing OS-level confinement. Not independently reachable through the documented sanitizer-gated threat model.
- **Concurrent cold-start races** (two browser tabs both POSTing `/api/model-pull` during a fetch) — `start_setup` is idempotent-while-running via the job lock (`model_pull.py:191-192`), which I read but did not stress under real concurrency.

---

*Deep-dive written to `docs/audits/gauntletgate-09b979c-2026-06-17/01-engineering.md`.*
