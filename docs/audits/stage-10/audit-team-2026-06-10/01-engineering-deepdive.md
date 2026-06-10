# Engineering Deep-Dive — Stage 10 (commit `d9495a8`, diff vs `253b08c`)

**Role:** Principal Engineer (audit team, 2026-06-10)
**Scope:** The Stage 10 diff only — 10.1 DesignRegistry alias flattening (`src/kimcad/webapp.py`), 10.2 SendPanel direct-print UI (`frontend/src/components/SendPanel.tsx`, `frontend/src/api.ts`), 10.3 Bambu connector (`src/kimcad/bambu_connector.py`, `connectors.py`, `config.py`, `config/default.yaml`), 10.4 model pulls (`src/kimcad/model_pull.py`, webapp routes, `FirstRunWizard.tsx`, `SettingsPanel.tsx`).
**Method:** Full read of every new/changed module; systematic grep of all `reg.*` state access for lock discipline; introspection of the REAL `bambulabs-api` 2.6.6 (installed in this venv) against every method the connector calls — `mqtt_start`/`mqtt_client_ready`/`get_state`/`upload_file`/`start_print`/`get_percentage` plus the library's MQTT and FTPS internals; verification of 3 of the audit-lite remediation claims in source; full targeted test run.

**Verification actually run (real results):**

| Check | Result |
|---|---|
| `pytest tests/test_bambu_connector.py tests/test_model_pull.py tests/test_webapp.py -q` | **166 passed** (62.6s) |
| `vitest run` (frontend, node 24.14) | **334 passed**, 26 files (32.1s) |
| `ruff check src tests` | **All checks passed** |
| Audit-lite fix spot-checks (10.2 poll generation guard; 10.3 FTP "226" proof; 10.4 `ipaddress`-based loopback + coarse live region) | **All present in source as claimed** |

**Severity rollup: Blocker 0 / Critical 0 / Major 2 / Minor 5 / Nit 2 — 9 findings.**

---

## What's working

This is a strong slice set, and several things deserve explicit credit:

- **The FTP "226" proof (10.3 ENG-001 remediation) is genuinely correct, verified against the real library.** I read `bambulabs_api.ftp_client`'s `connect_and_run` decorator in 2.6.6: it really does swallow a mid-transfer exception (`except Exception: logger.error(...)`) and fall through to return `None`, while connect/login failures escape and get wrapped by `Printer.upload_file`. Requiring `"226"` in the returned `storbinary` response string is exactly the right discriminator — without it a dropped upload would be narrated as "sent, printing". This fix would have been invisible to anyone who didn't read the library source.
- **The 10.1 flattening is complete.** A systematic grep of every `reg.meshes/gcode/step/gate_status/slice_cache/template_state/snapshot/saved_id` access in `webapp.py` found **zero** per-design mutations or reads outside `with reg.lock:`. The multi-field transactions (design registration at `webapp.py:1616-1641`, reopen at `:1768-1781`, re-render at `:2047-2070` including `next_mesh_version()`) all hold the lock across the whole transaction. The `slice_lock`/`progress_lock` server-level locks were correctly left alone.
- **The trust posture of the send surface is right.** `drives_hardware` on the class is the single source of truth for the simulated label; the server re-checks the gate verdict on `/api/send` regardless of UI state (`webapp.py:1379-1391`, fail-closed); `ensure_sendable` requires `confirm is True` (identity, not truthiness) plus a motion-bearing G-code proof before any network I/O; and the SendPanel only ever fires the POST from the confirm dialog.
- **The model-pull security contract holds.** The pull list is fixed server-side (`webapp.py:1180-1188` — never a caller-supplied name), the backend must be loopback (now parsed with `ipaddress`, closing the `127.evil.example` hole), demo mode is refused with a typed status, and the access-code env var value is never logged or echoed anywhere (grep-verified: only the env var *name* appears in messages, which is correct). Ollama error text reaching the wizard renders through React text nodes — no `dangerouslySetInnerHTML` anywhere in `frontend/src`.
- **The `_snapshot_locked` deadlock fix is the right shape** — a documented REQUIRES-lock private method instead of a reentrant lock, with the discipline stated at the definition (`model_pull.py:81-89`).
- **The audit-lite chain is honest.** Every claimed remediation I spot-checked is actually in source, with the finding ID cited at the fix site — a pattern that makes re-audit cheap.

---

## Findings

### ENG-1001 — Major — Correctness — Bambu send's busy gate fails open when the printer state is UNKNOWN (real-hardware session-readiness race)

**Evidence:** `src/kimcad/bambu_connector.py:225-232`:

```python
state_name = self._state_name(p)
if state_name in ("RUNNING", "PREPARE", "PAUSE"):
    raise ConnectorError(... reason="busy" ...)
```

Introspecting the real library: `PrinterMQTTClient.ready()` is `bool(self._data)` — it flips true on the **first** MQTT message of any kind. The library's `_on_connect` publishes *three* requests (`pushall`, `get_version`, `get_history`), and `manual_update` merges whichever response lands first into `_data`. If the `info`/`upgrade` response arrives before the `pushall` print report (or the print report is incremental), `get_state()` returns `GcodeState.UNKNOWN` (via the enum's `_missing_` hook — verified: `GcodeState(-1) == UNKNOWN`, no exception). The connector's `_session` wait loop exits on `mqtt_client_ready()`, so on real hardware `send()` can observe `UNKNOWN` while the printer is actually `RUNNING` — and `UNKNOWN` is not in the busy tuple, so the send proceeds to upload and `start_print` over a live job. The module's own `_STATE_MAP` comment states the design intent: "unknown beats wrong … we only read state AFTER the MQTT session reports ready, so a still-unknown state is genuinely abnormal" — `status()` honors that (UNKNOWN → error), but `send()`'s busy gate does the opposite and fails *open*. There is also a smaller TOCTOU inside the same block: the state is checked once, then a potentially-long FTPS upload runs, and `start_print` fires without a re-check.

**Why this matters:** The stated invariant is "Refuse to interrupt a job in progress — busy is a soft, typed outcome." On real P2S/A1 hardware at Kim's Stage 11 beta, the first send to a printer that's mid-print can violate it — `start_print` publishes a `project_file` command whose effect over a running job is firmware-defined (best case the printer refuses; worst case the running print is disturbed). The FakePrinter can never exhibit this because its readiness and state are set together.

**Blast radius:**
- Adjacent code: `_session`'s ready-wait (`bambu_connector.py:136-146`) is the shared root — `status()` has the same race but only mis-*reports* (UNKNOWN → "error" snapshot, an honest-direction lie); `capabilities()` and `job_status()` tolerate it.
- User-facing: a send against a busy-but-not-yet-reported printer; also a transient "printer error / state unknown" status flash right after connect.
- Migration: none — additive enforcement.
- Tests to update: `tests/test_bambu_connector.py` busy-refusal test gains an UNKNOWN case; the FakePrinter needs a "ready before state known" mode to pin it.
- Related findings: ENG-1002 (same `_session` plumbing).

**Fix path:** Two small changes, either alone is a big improvement, both together are right: (1) in `send()`, treat `UNKNOWN`/unrecognized state as a refusal (`ConnectorError`, user message "Couldn't confirm the printer is idle — check its screen, then try again") — fail closed like everything else in this codebase; (2) extend `_session`'s readiness wait (for send only, or globally) to also require `get_state() is not UNKNOWN` within the same deadline, so the normal path never sees the race. Optionally re-read state immediately before `start_print` to close the TOCTOU.

---

### ENG-1002 — Major — Correctness/Performance — MQTT sessions are never disconnected: `mqtt_stop()` only stops the loop thread, and a followed real job opens ~120 fresh TLS sessions

**Evidence:** `src/kimcad/bambu_connector.py:148-152` tears down with `printer.mqtt_stop()`. Verified in the real library: `Printer.mqtt_stop()` → `PrinterMQTTClient.stop()` → `self._client.loop_stop()` — **nothing in bambulabs-api 2.6.6 ever calls paho's `disconnect()`** (`Printer.disconnect()` is also just `loop_stop` + camera stop). So every session ends without an MQTT DISCONNECT packet; the TLS socket closes only when CPython garbage-collects the per-request `Printer`. Meanwhile the webapp builds a fresh connector per request (by design), and SendPanel follows a real job at 5s intervals for up to 10 minutes (`SendPanel.tsx:97` — 120 polls), each poll being a full TLS handshake + MQTT CONNECT + pushall against the printer.

**Why this matters:** Bambu LAN-mode firmware (P1/A1 family) has a small budget of concurrent MQTT connections and is community-documented as unstable under reconnect churn — abrupt socket drops without DISCONNECT leave the broker side to time sessions out. The plausible failure on real hardware is exactly during the highest-trust moment this stage built: the live status-follow after Kim's first real send starts erroring or, worse, destabilizes Bambu Studio's own connection to the printer mid-print. The FakePrinter cannot show any of this (its `mqtt_stop` is a flag). This is "appears to" territory — I could not test against hardware — but the mechanism is verified in the library source, not inferred.

**Blast radius:**
- Adjacent code: `_session` is the single seam — one fix covers `capabilities`/`status`/`send`/`job_status`. `_handle_send` additionally opens a *second* session right after a successful send for the status decoration (`webapp.py:1428-1433`).
- User-facing: live status line under a real job; possibly the printer's own connectivity.
- Migration: none.
- Tests to update: a FakePrinter assertion that teardown calls disconnect (extend the existing `test_mqtt_stops_even_when_the_upload_raises`).
- Related findings: ENG-1001 (shared `_session`); the per-request-connector design is otherwise sound — don't abandon it, just make teardown clean.

**Fix path:** In `_session`'s `finally`, before `mqtt_stop()`, defensively send a real disconnect: `getattr(getattr(printer, "mqtt_client", None), "_client", None)` and call `.disconnect()` inside the existing broad-except (the fake without that attribute path is already tolerated by `try/except`). That single line sends the DISCONNECT and closes the socket deterministically instead of at GC time. For Stage 11, consider letting one connector instance serve the whole poll chain (or lengthening the poll period for `bambu`-type connectors) to cut the handshake churn — flagging now so it's a known knob if the beta shows instability.

---

### ENG-1003 — Minor — Correctness — One failed status poll permanently kills SendPanel's live-follow chain

**Evidence:** `frontend/src/components/SendPanel.tsx:77-79` — `pollStatus`'s `.catch()` comments "a missed poll is not an error state — the last known status stands", but it never reschedules; the chain only continues from the `.then` branch. One transient fetch failure (server briefly busy slicing, laptop Wi-Fi blip) and the live line freezes on the last snapshot — for the rest of a multi-hour print the UI shows a stale "printing" with no further updates and no indication it stopped watching.

**Fix path:** In the catch, reschedule `pollStatus(name, remaining - 1, gen)` after the same 5s delay (still generation-guarded, still bounded by `remaining`). One line, plus a vitest case alongside the existing poll-lifecycle regression test.

---

### ENG-1004 — Minor — Correctness — The Bambu plate guard's error copy is wrong for the zero-plate case, and its member matching is stricter than the proof's

**Evidence:** `src/kimcad/bambu_connector.py:213-220` — `len(plates) != 1` raises with user message "This print file has more than one plate…" even when `found 0`. The plate scan requires `n.startswith("Metadata/plate_") and n.endswith(".gcode")` (case-sensitive), while the upstream proof (`slicer.py:prove_gcode_3mf`) accepts any member whose name `.lower().endswith(".gcode")` anywhere in the archive — so a 3MF that passes `ensure_sendable` can still reach this guard with 0 matches and get told it has "more than one plate".

**Fix path:** Branch the message (0 → "doesn't contain a recognizable plate — re-slice and try again"; >1 → the current text), and align matching with the proof (case-insensitive suffix). Low-likelihood edge (KimCad's own OrcaSlicer output always matches), but the wrong-direction copy is a user-facing lie when it does fire.

---

### ENG-1005 — Minor — UX/Correctness — A wrong Bambu access code surfaces as reason `"error"`/`"offline"`, never `"auth"`, so the UI's auth-specific hint can't trigger for the connector whose secret is most fiddly

**Evidence:** A bad access code fails in one of two ways on real hardware: MQTT auth rejection → `ready()` never flips → `PrinterOffline` (reason `"offline"`, `bambu_connector.py:140-145`), or FTPS `530 Login incorrect` → wrapped by the generic upload `ConnectorError` (default reason `"error"`, `bambu_connector.py:235-240`). The reason vocabulary has `"auth"` exactly for this, and `SendPanel.tsx:107` carries a reason-specific hint ("Check the connection's key or access code in Settings") that can never fire for Bambu. Mitigated: both `user_message` strings do mention the access code, so the user isn't stranded — this is vocabulary drift, not a dead end.

**Fix path:** In the upload except, detect `ftplib.error_perm` whose message starts with `530` and raise `AuthError` instead. The MQTT side genuinely can't distinguish auth-reject from unreachable with this library (paho reports it only via the connect reason code, which the library logs but doesn't expose) — keep `offline` there and let the user message carry the "check the access code" hint as it already does.

---

### ENG-1006 — Minor — Correctness — A cleanly-closed pull stream is marked "done" without Ollama's terminal success line

**Evidence:** `src/kimcad/model_pull.py:189-192` — `_pull_one` returns success whenever the stream ends without an `error` line; the comment acknowledges Ollama's documented final `{"status":"success"}` line but doesn't require it. If Ollama is stopped mid-pull and the socket closes cleanly (FIN, no error line), the wizard row shows "✓ done" while the post-pull `checkModel()` re-probe shows the model still missing — a contradictory UI (row says done, recap says "not downloaded yet"). The re-probe means no *false* "Ready" claim is ever made — the harm is confusion, not a lie about readiness.

**Fix path:** Track `saw_success` while iterating; on stream end without it, raise `RuntimeError("the download ended early")` so the existing per-model error path (with retry button) takes over. One flag + one test against the existing `_FakeStream`.

---

### ENG-1007 — Minor — Architecture — `JOB` is a process-wide mutable singleton shared by every webapp instance

**Evidence:** `src/kimcad/model_pull.py:194` (`JOB = ModelPullJob()`), consumed via module import in two routes (`webapp.py:836-839`, `:1188`). `make_handler` deliberately closes over per-server state (`reg`, locks), but the pull job is global: two handler instances in one process (the test suite does this; a future second server would) share snapshots, so one instance's leftover error rows are reported by another's `/api/model-pull/progress`. The docstring does say "app-wide" — the singleton is intentional — but it's the only piece of mutable per-server-ish state that escaped the Stage 9/10 closure-and-registry discipline.

**Blast radius:** Test isolation (a pull test leaving state behind can bleed into a later webapp test's progress route — not currently bitten, the suite passes); any future multi-instance embedding. **Fix path:** either instantiate `ModelPullJob()` inside `make_handler` (one download at a time *per server* — still satisfies the wizard's idempotency contract since one server serves one UI), or keep the singleton and add a `reset()` used by test fixtures + a line in the webapp comment owning the choice.

---

### ENG-1008 — Nit — Hygiene — `/api/connectors` comment claims `default` is "the first configured connector"; the code returns `names[0]` unconditionally

`webapp.py:860-862`. SendPanel independently computes "configured default, else first configured" (`SendPanel.tsx:46-48`), so behavior is fine — but the comment documents the client's policy, not the server's. Fix the comment (or make the server actually skip unconfigured names and simplify the client).

### ENG-1009 — Nit — Hygiene — `_handle_model_pull` hardcodes fallback model names duplicated from the config layer

`webapp.py:1183-1184` (`"gemma4:e4b"`, `"qwen2.5vl:3b"`) duplicate defaults that exist where `backend.model_name`/`vision_model` are resolved (and again in `FirstRunWizard.tsx:328`). If the default model ever changes, the pull surface drifts silently. Hoist to a shared constant.

---

## Cross-cutting observations (no finding ID)

- **`_handle_send` reads `gcode_path` under the lock but uses it after release** (`webapp.py:1379-1403`): an eviction or re-render mid-send can delete the file while the connector reads it. This predates Stage 10 (every connector has it) and lands in the generic logged-500 — acceptable for a single-user desktop app, noted for completeness, not charged to this diff.
- **`start_print` proves only an MQTT publish**, not firmware acceptance — the code comments this honestly and the 226 check covers the dangerous half (the upload). The residual gap (publish OK, firmware silently ignores) is only closable by post-start state polling; reasonable to defer to Stage 11 hardware learnings.
- **The library hardcodes print options** (`bed_leveling: True`, `bed_type: "textured_plate"`, `vibration_cali: True` in `start_print_3mf`) — worth knowing at the beta if a print behaves unexpectedly on a different plate type; not actionable in KimCad today.
- **`_pull_one` stream parsing is bytes-correct**: `urlopen` responses iterate as `bytes` lines and `json.loads` accepts bytes; the test fakes stream bytes too (`test_model_pull.py:24`), so the fake and the real path match.
- **Timeout semantics are right**: `timeout=300` on `urlopen` is a per-socket-op timeout, so it bounds a silent stall without capping total download time — exactly what the comment claims.

## What I couldn't check

- **Real hardware.** Every Bambu finding above is source-verified against the real library but not executed against a printer — by design (Stage 11 is the hardware beta). ENG-1001/1002 are precisely the items to retest first on hardware.
- The live walkthrough was not re-run (its report at `docs/audits/walkthrough-stage-10-2026-06-10/WALKTHROUGH-REPORT.md` is taken as read; backend + frontend suites were re-run independently instead).
- No dependency CVE scan was run this pass (`bambulabs-api` 2.6.6 / MIT is the only new dependency, optional, and absent-graceful).

## Punch list (this sprint)

1. ENG-1001 — fail closed on UNKNOWN state in `send()` (+ ready-wait extension).
2. ENG-1002 — one defensive `disconnect()` line in `_session` teardown.
3. ENG-1003 — reschedule the poll chain on a failed fetch.
4. ENG-1004/1005/1006 — small typed-error and copy fixes, each with a one-test pin.

## Watchlist (next sprint / Stage 11)

- Hardware-validate the busy gate, session churn under the 10-minute follow, and FTP 530 mapping on the real P2S/A1.
- Decide the `JOB` singleton's ownership (ENG-1007) before any second-server scenario appears.
