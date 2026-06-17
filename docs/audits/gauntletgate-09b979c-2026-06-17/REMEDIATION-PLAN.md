# GauntletGate 09b979c — Remediation plan (drive every finding to 0/0/0/0/0)

Consolidated + cross-role-dedup'd punch list from the Full lane (Writer, Engineering, UI/UX, Test) + Lite + Walkthrough. QA findings appended when its lane lands. Scott's standing bar: **fix every severity to zero before the installer build** (not just Blocker/Critical).

## CRITICAL (gate-blocking — verdict is DO NOT ADVANCE until fixed)

- **ENG-GG-001 — Managed `ollama serve` child is never torn down (orphan process).**
  Fix in `ollama_runtime.py`: track the `Popen` only when KimCad *started* the server (`source=="started"`, never `"already-up"`) in a lock-guarded module handle; add `stop_managed()`; on Windows assign the child to a Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, via ctypes) with `CREATE_NEW_PROCESS_GROUP` (folds in ENG-GG-008) + an `atexit`/`finalize` `terminate()` floor. Wire `shell.py:_on_closed` (after `httpd.shutdown()`) and `webapp.serve()`'s `finally` to call `stop_managed()`. Never touch a reused system Ollama.
  Tests: inject a recording `spawn`; assert teardown fires for `source=="started"` and never for `"already-up"`; Ollama-gated real test — start a stopped engine then teardown, assert `is_server_up()` False after.

## MAJOR

- **DISK-PRECHECK (ENG-GG-002 = TEST-GG-002, doc side = DOC-101) — cross-role triple.**
  (a) Hoist the disk pre-check into `start_setup`/`_run_setup` *before* the Phase-1 engine fetch: estimate engine (~1.5 GB) + missing-model GB against the receiving drive; write a friendly engine-row error if short, never starting the download. (b) Reconcile the THREE disk numbers to one honest story: documented free-disk (docs say ~12 GB) vs the runtime pre-check (`_EST_GB` 11+4=15 GB) vs the disk-full string ("8 GB"). Decision: lower `_EST_GB` so the models pre-check + engine clears the documented ~12 GB with margin, and fix `model_pull.py:67` "8 GB" → the canonical "~7.7 GB". (c) Add a doc-vs-code consistency test (`sum(_EST_GB) + engine ≤ DOCUMENTED_FREE_DISK_GB`) and update the stale `tests/test_model_pull.py:203` `"8 GB"` assertion.
- **ENG-GG-003 = TEST-GG-006 — `PORTABLE_SIZE_BYTES` ~0.9 MB short.** Set `ollama_fetch.py:40` = `1_461_613_335` (verified real `v0.30.9` asset size) + provenance comment by the SHA.
- **UX-FULL-001 — managed-Ollama narrative not propagated to Settings / design-status / chat wall.** Update `SettingsPanel.tsx:451-463` (drop the primary "Start it (or get Ollama)" + `ollama.com/download` link; lead with in-app setup, route via the existing `kimcad-rerun-setup` event), `designStatus.ts:80` ("Start Ollama…" → finish setup in-app), `ChatPanel.tsx:224` ("Start Ollama first…" → in-app setup). Flip the tests that pin the stale copy: `SettingsPanel.test.tsx:133-143`, `ChatPanel.test.tsx:153`.
- **TEST-GG-001 — "real_tool integration test" claim overstates coverage.** Correct the docstrings (`ollama_runtime.py:18`, `ollama_fetch.py:16`) to state the auto-run real test covers only the reuse branch; add an Ollama-gated test forcing the spawn branch (`start_serve` on an alt `OLLAMA_HOST`/dead default → poll healthy → teardown); fix/remove the manual verify script that printed `RESULT=FAIL` on success.

## MINOR

- **ENG-GG-004** — `_deny_network` also neutralize `socket.fromfd`/`fromshare`/`dup` (cheap depth; OS-level confinement stays on the watchlist).
- **ENG-GG-005** — dedup loopback logic: `model_pull.is_loopback_url` delegate to `Config._is_local_base_url` (or shared `netutil`).
- **ENG-GG-006** — `start_serve` pass a minimal env (PATH, SystemRoot, OLLAMA_HOST) to the Ollama child, not the full parent env (keeps cloud `*_API_KEY` out of the child).
- **DOC-102** — `installer/kimcad.iss:34` comment "ANOTHER ~13 GB" → ~7.7 GB (+ ~1.4 GB engine).
- **DOC-103** — add the managed-engine location bullet to the "what goes where" inventories (`README.md:28-35`, `install-guide.md:48-59`); confirm exact path (`%LOCALAPPDATA%\KimCad\ollama`) against `ollama_runtime.py`.
- **UX-FULL-002** — Settings `!running` branch: add the in-app setup re-entry (reuse the `!model_present` branch's `onCta`).
- **UX-FULL-003** — cloud "On" badge only when `cloud_enabled && has_cloud_key && cloud_model`; else "On — needs setup"/"Off".
- **TEST-GG-003** — assert `_deny_network()` actually fires inside the worker `_run` before `exec` (test or static guard).
- **TEST-GG-004** — parametrize the zip-slip test over drive-absolute + embedded-`..` members.
- **TEST-GG-005** — test `start_setup` idempotent-while-running guard.

## NIT

- **DOC-104** — add the engine dir to `troubleshooting.md:94-98` "Where is my stuff?" (roll into DOC-103).
- **ENG-GG-007** — `_present` match: no defect; add a clarifying comment if touched.
- **ENG-GG-008** — `CREATE_NEW_PROCESS_GROUP` on the managed serve — folds into the ENG-GG-001 job-object fix.
- **UX-FULL-004** — photoreal avatar brand mark: **no action** (Scott's deliberate choice; b4 UX-009 KEEP).

## Re-verify after fixes
ruff + the full self-hosted gate (pytest incl. live OrcaSlicer + CadQuery sandbox + the new tests; vitest; build-repro), then re-emit the gate verdict. Only then is the gate clear for the installer build.

---

## Resolution — 2026-06-17 (every finding driven to zero or explicitly no-action)

**Critical**
- ENG-GG-001 / QA-GG-001 — **FIXED** (inline): `ollama_runtime` now tracks the `Popen` only when KimCad started it (`source=="started"`), assigns a Windows Job Object (`KILL_ON_JOB_CLOSE`) + `atexit` terminate, and `stop_managed()` is wired into `shell._on_closed` and `serve()`'s `finally`. Reused system Ollama untouched. **Proven against the REAL binary**: a new `real_tool` test spawns `ollama serve` on an alt port, polls healthy, tears it down, asserts it's gone (`test_ollama_runtime_real.py`, 3 passed); system Ollama on :11434 verified untouched.

**Major**
- ENG-GG-002 / TEST-GG-002 / DOC-101 — **FIXED** (agent B): disk pre-check hoisted into `_run_setup` (engine + missing models) before any fetch; `_EST_GB={chat:6,vision:4}` + `_ENGINE_EST_GB=1.5` (11.5 ≤ documented 12 GB, pinned by a new doc-vs-code test); disk-full string "8 GB"→"7.7 GB" + its assertion updated. 36 passed.
- ENG-GG-003 / TEST-GG-006 — **FIXED** (agent B): `PORTABLE_SIZE_BYTES = 1_461_613_335` (exact) + provenance comment + pin test.
- UX-FULL-001 — **FIXED** (agent C): Settings down-state, `designStatus.ts`, `ChatPanel.tsx` now route to the in-app "Set up KimCad's AI" (no "Start Ollama / get Ollama"); ollama.com link removed; tests flipped + positively assert no stale copy. vitest 405 passed.
- TEST-GG-001 — **FIXED** (inline `ollama_runtime` docstring + new spawn-branch `real_tool` test; agent B fixed the `ollama_fetch` docstring) — the overstated "real_tool covers fetch+serve" claim is now honest, and the spawn branch has real coverage.
- QA-GG-002 — **FIXED** (inline): `bind_prompt_dimensions` honors an explicit, uniquely-anchored, in-range `<N> mm` the planner left unbound (adjacency + uniqueness, can't mis-bind box/dish). **Proven with the REAL planner**: "a desk cable clip for an 8 mm cable" → `cable_d=8.0` (was 6 mm default). 6 new unit tests.

**Minor** — ENG-GG-004 (FIXED, agent E: `fromfd`/`fromshare`/`dup` neutralized + guards), ENG-GG-005 (FIXED, B: `is_loopback_url` delegates to `Config._is_local_base_url`), ENG-GG-006 (FIXED, inline: managed-serve child env scrubbed of `*_API_KEY`/secrets), DOC-102/103 (FIXED, D: stale "13 GB" comment + engine location added to README/install-guide), UX-FULL-002 (FIXED, C: Settings down-state re-entry), UX-FULL-003 (FIXED, C: cloud "On" badge only when key+model present), TEST-GG-003 (FIXED, E: `_deny_network`-before-exec guard test), TEST-GG-004 (FIXED, B: zip-slip parametrized), TEST-GG-005 (FIXED, B: `start_setup` idempotency test), **QA-GG-003** (FIXED, inline: startup cleanup spares dirs touched within a grace window so a concurrent instance's live mesh isn't clobbered + 2 tests), QA-GG-004 (**NO CODE DEFECT** — a warm-lane test-isolation note; product behavior is correct).

**Nit** — ENG-GG-008 (FIXED, folded into ENG-GG-001: `CREATE_NEW_PROCESS_GROUP`), DOC-104 (FIXED, D), ENG-GG-007 (**NO DEFECT** — QA's own analysis confirmed the `_present` match is correct), UX-FULL-004 (**NO ACTION** — Scott's deliberate avatar choice; b4 UX-009 KEEP), QA-GG-005 (**NO ACTION** — the v0.30.9 pin is the deliberate newest-verified release; a cold fetch uses it, a warm box reuses its own Ollama regardless).

**Authoritative re-verification:** `scripts/ci.sh` (the self-hosted gate) running — ruff + full pytest incl. live OrcaSlicer + the new real-ollama spawn/teardown + CadQuery sandbox + vitest 405 + SPA build-repro. Verdict re-emitted in 00-gate-report.md on green.
