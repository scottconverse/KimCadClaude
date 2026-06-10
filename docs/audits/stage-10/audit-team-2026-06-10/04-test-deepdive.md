# Test Engineer Deep-Dive — Stage 10 (commit d9495a8)

**Role:** Senior Test Engineer, audit-team 2026-06-10
**Scope:** Stage 10 test reality (`git diff 253b08c..d9495a8 -- tests frontend/src/**/*.test.*`): `tests/test_bambu_connector.py` (27), `tests/test_model_pull.py` (14), SendPanel tests (9) + 3 `sendDesign` transport tests, FirstRunWizard pull tests (+3), SettingsPanel vision tests (+3), `api.test.ts` additions, the kept TEST-003 pins in `test_webapp.py` post-flattening. Per-slice audit-lites read first; fixed findings are not re-reported.

---

## Verification runs (mine, this audit — not the dev's claims)

| Suite | Command | Result |
|---|---|---|
| Backend, full | `.venv\Scripts\python.exe -m pytest -q -ra` | **970 passed, 0 skipped, 0 xfailed in 312.06s (5:12)** |
| Frontend, full | `node node_modules/vitest/vitest.mjs run` (node22, frontend/) | **334 passed (26 files) in 14.4s** |
| New files alone | `pytest tests/test_bambu_connector.py` / `tests/test_model_pull.py` | 27 passed / 14 passed |
| Mock-contract introspection | `bambulabs_api` 2.6.6 in `.venv` (inspect.getsource on `Printer`, `PrinterFTPClient`, `PrinterMQTTClient`, `GcodeState`) | see TEST-1004/TEST-1005 |
| Fake-timer semantics | scratch vitest run (deleted) | **proved** a real timer scheduled before `vi.useFakeTimers()` is NOT fired by `advanceTimersByTimeAsync` — see TEST-1001 |

Skip census: zero skips on this provisioned box. The skip inventory in the tree is principled — every `skipif` is tool/profile/interpreter-gated with a reason, and the CI strict gate (`KIMCAD_CI_STRICT=1` in `ci.yml` + the grep in `scripts/ci.sh`) turns ANY skip on the provisioned runner into a red build, with a separate `-m live` zero-skip assertion. No `.only`, `.skip`, `xit`, `todo`, or empty-body tests anywhere in `frontend/src` or `tests/`. That gate is real, verified in source, and is better discipline than most production teams have.

**Test-suite shape:** backend is genuinely two-layered — behavior-level units plus true socket integration (route tests run a real `ThreadingHTTPServer` and speak HTTP, monkeypatching only at the connector/slicer seam). Frontend is component-level with the `api` module mocked; no browser E2E (the walkthrough skill covers that manually). Hardware is faked wholesale — accepted for Stage 11 beta; this report judges whether the fake's contract is the *right* contract.

---

## What's working (credit where due)

- **The FakePrinter contract is substantially the real library's contract.** I introspected `bambulabs_api` 2.6.6 and checked every surface the fake models: `PrinterFTPClient.upload_file` really returns ftplib's `storbinary` response (`"226 Transfer complete."`) on success; the FTP decorator really swallows mid-transfer exceptions and returns `None` (so the ENG-001 pin `upload_file → None ⇒ not sent` tests the library's actual failure mode, not an invented one); `GcodeState`'s members are exactly the seven names the parametrized state-map test covers (`IDLE/PREPARE/RUNNING/PAUSE/FINISH/FAILED/UNKNOWN` — no eighth state untested); `get_percentage` is typed `int | str | None` and the `"Unknown"` string case is pinned; `mqtt_start` uses paho `connect_async` (non-blocking), so the fake's "never ready → timeout → PrinterOffline" model matches how an unreachable printer actually presents. This is the most honest mock I've audited in a while.
- **Regression culture is real.** Every audit-lite finding fixed in Stage 10 carries a named test or code comment tracing back to it (ENG-001/002/003, UX-002, QA-/TEST- ids in test docstrings). The TEST-003 eviction pin was deliberately *kept* through the alias flattening and still exercises the lockstep protocol end-to-end through the routes.
- **The model-pull route tests exercise the real dispatch path.** `_handle_model_pull` does call-time local imports (`from kimcad.model_advisor import probe_ollama`), so the monkeypatches at `ma.probe_ollama` and `mp.ModelPullJob.start` take effect on the genuine handler path — demo-mode refusal, loopback refusal, native-root derivation, and the config-derived missing list are all computed by production code under test, over a real socket.
- **Client side of the no-model-menu rule is pinned:** `api.test.ts` "POSTs with no body — the pull list is fixed server-side" asserts the request body is undefined.
- **Conftest is a model of suite ergonomics:** one-clear-line degraded-env probes, hermetic `~/.kimcad` isolation, fake keyring (no test touches the OS credential store), and the CadQuery-backend-off default that kills machine-dependent green/red.

---

## Findings

### TEST-1001 — Major — Quality / Regression — Stage 10's poll-lifecycle fixes are effectively unpinned: the SendPanel unmount test is vacuous, and the other two guards have no test at all

**Evidence (verified, not inferred):**

1. **The vacuous pin.** `frontend/src/components/SendPanel.test.tsx:119-135` ("unmount stops the live-status poll chain") renders, sends, waits for poll #1, unmounts, **then** calls `vi.useFakeTimers()` and `advanceTimersByTimeAsync(30000)`, asserting no new `getConnectorStatus` calls. But the chain's next tick was scheduled with **real** `setTimeout(…, 5000)` (`SendPanel.tsx:74`) *before* fake timers were installed. Fake timers only control timers created while installed — I proved this empirically with a scratch vitest run against the project's own vitest 4.1.8: a real timer scheduled pre-install does **not** fire under a 30 s fake advance (and is still alive afterward, firing on real time). The test therefore passes **even if the unmount cleanup (`useEffect(() => stopPoll, …)`, `SendPanel.tsx:65`) and the `pollGen` guard are deleted outright** — the leaked 5 s timer simply never fires inside the test's ~50 ms lifetime. The assertion `mockStatus.mock.calls.length === callsAtUnmount` is true for leaking and non-leaking implementations alike.
2. **The supersede guard is untested.** Slice 10.2's FINDING-001 (Major) had two halves: unmount leak AND a superseding send painting the *old connector's* status under the *new* job's banner. The shipped fix (`pollGen`, `SendPanel.tsx:34/61/70`) covers both; the test suite covers neither (the only lifecycle test is the vacuous one above). The commit message's claim "generation-guarded so unmount/re-slice/supersede kills the chain" is implemented but not proven.
3. **FirstRunWizard's `disposedRef` fix (slice-10.4 ENG-001) has no test.** `FirstRunWizard.tsx:84-100` closes the unmount-between-click-and-resolve window for the 1 Hz pull poll; `FirstRunWizard.test.tsx` contains no unmount test and no fake-timer use at all (grep: zero matches for `unmount|useFakeTimers`). Deleting `disposedRef` keeps all 334 vitest green.

**Why this matters:** these are the regression pins for two *fixed audit Majors*. The class of bug let through: any future refactor of SendPanel/FirstRunWizard polling (e.g. moving to a `usePoll` hook, or React 19 effect-timing changes) can silently reintroduce background polling against a real printer connection and wrong-printer status display during a real print — and the suite stays green. A test that exists but cannot fail is worse than a gap: it reads as coverage in every future audit.

**Blast radius:**
- Adjacent code: `SendPanel.test.tsx:119-135` (rewrite), `FirstRunWizard.test.tsx` (add), `SendPanel.tsx` / `FirstRunWizard.tsx` untouched.
- User-facing: none from the fix itself; the protected behaviors are live-print status honesty and background network traffic.
- Tests to update: the rewritten test must install fake timers **before** `render()` (vitest 4: `vi.useFakeTimers()` then drive the flow with `advanceTimersByTimeAsync`), first prove the detector works (advance 5 s while mounted → poll #2 fires), then unmount, advance 30 s, assert no further calls. Add: a supersede case (second send while first chain's status promise is pending; resolve the old promise; assert `setLive` output reflects the new connector only) and a wizard unmount-mid-`startModelPull` case.
- Related findings: none open (the underlying behaviors were fixed in 10.2/10.4; this is purely the net).

### TEST-1002 — Major — Coverage / Regression — No adversarial-body test pins the server-side-fixed pull list; the invariant is structural today and one refactor away from silently dissolving

**Evidence:** `_handle_model_pull` (`webapp.py:1132-1187`) never reads the request body — the pull list comes from `cfg.llm_backend()` only. That is the right design. But the only test asserting the invariant, `test_pull_starts_only_the_missing_models_fixed_server_side` (`test_model_pull.py:279-301`, docstring: "the list came from CONFIG, not from any request body"), POSTs with **no body at all**. Nothing in the suite sends `{"model": "attacker/anything:670b"}` (or `?model=` in the path) and asserts it is ignored.

**Why this matters:** the no-model-menu rule is a repeatedly documented trust boundary (module docstring, handler docstring, README). The bug class let through: a future convenience change (`data = self._read_json() or {}; chat = data.get("model", chat)`) — the most natural way someone "adds flexibility" — passes all 970 tests. The client-side pin (`api.test.ts` "POSTs with no body") proves KimCad's own SPA doesn't send a name; it proves nothing about what the server would do with one, and the server is reachable by anything on loopback.

**Blast radius:**
- Adjacent code: `tests/test_model_pull.py` route section only — one new test using the existing `_serve`/`fake_start` plumbing, POSTing a hostile JSON body and asserting `started["missing"]` is unchanged and the response is the normal snapshot.
- Shared state: none. User-facing: none. Migration: none.
- Related findings: the same adversarial-input habit would also cover the (currently unread) body on `/api/model-pull` interacting with `_read_json`'s QA-001 non-object guard — the new test gets that for free.

### TEST-1003 — Minor — Mocking / Regression — The FakePrinter never models the library's missing-data defaults; first hardware contact can emit a false nozzle-mismatch warning no test would catch

**Evidence:** in the real library, `Printer.nozzle_diameter()` is `float(self.__get_print("nozzle_diameter", 0))` — when MQTT hasn't reported the field yet (early session, older firmware), it returns **0.0**, not `None` and not an exception. `BambuConnector.capabilities()` (`bambu_connector.py:160-170`) filters only `None` and exceptions, so 0.0 flows through as a claimed nozzle size; `capability.py:101-124` then reconciles it against config and produces "Configured nozzle 0.40 mm disagrees with the printer's reported 0.00 mm — verify against the real machine." The FakePrinter models exactly two behaviors: `0.4` and (via test monkeypatching) raising — never the library's documented `0` default. Similarly, `get_percentage()` returning `None` (its typed third case) is handled in code (`bambu_connector.py:275`) but only the `"Unknown"` string is tested.

**Why this matters:** this is the precise question the audit asked — which real-API behaviors does the fake's contract miss? This is the one concrete case where a test asserts a contract (`caps.nozzle_diameter_mm == 0.4`, never-guess semantics) that the real lib will violate in a realistic state, producing a user-visible false warning on Stage 11's first hardware run. Everything else I introspected (FTP 226 return, None-on-swallowed-failure, GcodeState member set, busy-state names, `start_print` bool, connect_async non-raising) matches the fake — credited above.

**Blast radius:**
- Adjacent code: `bambu_connector.py:163-167` (map `raw in (None, 0)` → `None`; 0 mm is not a nozzle), one new FakePrinter case in `test_bambu_connector.py`.
- User-facing: removes a future false capability-mismatch note. Migration: none.
- Related findings: TEST-1004 (the drift-prevention side of the same mock).

### TEST-1004 — Minor — Mocking — Nothing prevents FakePrinter/real-library drift: the real package is absent from the lockfile, so no environment ever cross-checks the contract

**Evidence:** `bambulabs-api` is not in `requirements.lock` (verified) — the provisioned CI runner installs from the lock, so CI runs with the package **absent**; every "without the package" test simulates absence by monkeypatching `bambulabs_api_available`, and no test ever imports the real package. My fidelity verification above was only possible because this dev box happens to have 2.6.6 in `.venv` — that check exists nowhere in the repo. The optional extra is `bambulabs-api>=2.6` with no upper bound: a future 3.x changing `upload_file`'s return shape or `GcodeState`'s members would pass the entire suite and surface only on Kim's printer.

**Why this matters:** the mock is excellent *today* (TEST-1003 aside) because someone clearly read the library source. The suite cannot keep it excellent. Note the structural tension: the zero-skip CI strict gate means a `skipif(package absent)` contract test would fail the gate — so the only clean paths are (a) pin `bambulabs-api` in `requirements.lock` for the provisioned runner and add a small introspective contract test (assert `GcodeState` member set, `upload_file` return annotation/source contains `storbinary`, `get_percentage` typing), or (b) accept pure-fake until Stage 11 and write that acceptance down.

**Blast radius:**
- Adjacent code: `requirements.lock`, one new `tests/test_bambu_contract.py` (or a section in the existing file), CI provisioning unchanged (lock-driven).
- Migration: pip-audit then also scans the package — a plus. Upper-bound the extra (`>=2.6,<3`) while at it.
- Related findings: TEST-1003.

### TEST-1005 — Minor — Coverage / Quality — A handler mutating registry state outside `reg.lock` is undetectable by the suite; the `_locked` methods don't assert the lock they require

**Evidence:** post-flattening, the lock discipline is "every `reg.<field>` access inside `with reg.lock:`" — enforced by convention and review only. The kept TEST-003 pin (`test_webapp.py:1198-1217`) genuinely catches *stale-copy* regressions (a handler holding pre-eviction state) through the routes, but it cannot catch *lock omission*: an unlocked `reg.gcode[rid] = …` races only under concurrent load and passes all 970 tests deterministically. `DesignRegistry`'s eight `_locked` methods document "REQUIRES `self.lock` held" (`design_registry.py:15-16, 85-156`) but never check it, although `threading.Lock.locked()` makes the check one line.

**Why this matters:** the webapp is a `ThreadingHTTPServer` — status polls, progress polls, and design POSTs genuinely run concurrently. The bug class let through: a future handler (Stage 11 will add send/job-status surfaces) touching `reg` state without the lock ships green and fails as a once-a-week corrupted-registry mystery. I found **no current violation** — this is a guard for the seam the flattening just widened (every handler now touches `reg.<field>` directly instead of going through aliases).

**Blast radius:**
- Adjacent code: `design_registry.py` — add `assert self.lock.locked(), "must hold reg.lock"` (or raise) at the top of each `_locked` method. Because every existing call site is already under the lock, all 970 tests immediately become detectors: any future unlocked call to a `_locked` method fails deterministically. Direct field mutations remain reviewable-only — a known residual.
- Tests to update: none (existing suite is the net once the asserts exist). Migration: none.
- Related findings: none.

### TEST-1006 — Minor — Ergonomics / Regression — The fixed model-pull deadlock "regression test" manifests as an infinite suite hang, not a failure; and two concurrency cases are untested

**Evidence:** `_snapshot_locked`'s docstring (`model_pull.py:82-84`) says "deadlock, caught by test". True in substance: reverting the idempotent/no-op/disk-precheck paths in `start()` to call `self.snapshot()` under the held non-reentrant lock would block forever inside `test_start_is_idempotent_while_running` / `test_a_new_start_replaces_the_previous_runs_states`. But "caught" means: the local suite hangs silently with no failing test name (the `_wait_done` 5 s timeout never runs — the hang is inside `job.start()` itself), and CI dies at the 45-minute job timeout. There is no `pytest-timeout` in the dev deps. Additionally untested: (a) two **simultaneous** `start()` calls from different threads (the lock makes it safe by design; nothing proves it stays safe), and (b) the opener raising at open time (URLError/timeout) rather than yielding an error line — the `except Exception` in `_run` covers it, but only stream-level errors are exercised.

**Why this matters:** a deadlock regression should name itself in red, in seconds. A hang is the most expensive possible failure mode for a 5-minute suite, and on a dev box (non-CI) it looks like "pytest is slow today".

**Blast radius:**
- Adjacent code: `pyproject.toml` dev extras (+`pytest-timeout`, a generous `--timeout=120` default in `ini_options`), or a single dedicated test running `job.start` in a worker thread with `join(timeout=5)` + a liveness assert. The pytest-timeout route also bounds every *future* hang class for free.
- Tests to update: none break. Migration: none.

---

## Severity rollup (this role)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 (TEST-1001, TEST-1002) |
| Minor | 4 (TEST-1003, TEST-1004, TEST-1005, TEST-1006) |
| Nit | 0 |

## Top 3

1. **TEST-1001** — the poll-lifecycle pins don't pin: SendPanel's unmount test is empirically vacuous (fake timers installed after the real timer was scheduled), and the supersede guard + wizard `disposedRef` have no tests. Two fixed audit Majors are unprotected.
2. **TEST-1002** — no adversarial-body test for `/api/model-pull`'s server-fixed pull list; the no-model-menu trust boundary survives only as long as nobody adds a body read.
3. **TEST-1004** (with TEST-1003) — the FakePrinter is faithful today but uncheckably so: the real package is absent from the lockfile, nothing pins the contract against drift, and the one fidelity gap found (nozzle `0` default) yields a false hardware warning at Stage 11.

## Culture / pattern observations (for the exec report)

- The zero-skip strict gate, the live-marker execution assertion, and the audit-id-traceable regression tests are genuinely strong culture — the suite's claims are mostly honest claims.
- The recurring weak spot is **frontend async-lifecycle testing**: every gap found (vacuous fake-timer use, missing unmount/supersede pins) is in the same class. A short pattern note in the frontend README (fake timers before render; prove-the-detector-then-prove-the-fix) would prevent the next instance.
- Verified numbers for the record: backend 970/970 in 5:12, frontend 334/334 in 14.4 s, both zero-skip on the provisioned box.
