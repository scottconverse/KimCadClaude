# Audit Lite — Stage 10 Slice 10.3 (Bambu-native connector)
**Date:** 2026-06-10
**Scope:** Uncommitted working tree on top of 75a9794 — `src/kimcad/bambu_connector.py` + `tests/test_bambu_connector.py` (new), `connectors.py`, `config.py`, `config/default.yaml`, `pyproject.toml`, README/ARCHITECTURE rows.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship with caveats. The connector's contract discipline, session lifecycle, secret hygiene, and config gating are all sound, and the real-API binding was verified line-by-line against the installed bambulabs-api 2.6.6 (method names/signatures, GcodeState member names, and the `plate_1` → `Metadata/plate_1.gcode` start path all match). One Major: the library's FTP layer **swallows mid-transfer upload failures** (returns `None`, no exception), and the connector ignores `upload_file`'s return value — on real hardware a failed transfer can be reported as a successful send. Hardware-only (mock-tested stage), one-line fix; the rest is small.

## Verification run (this audit, not the dev's claims)
- `.venv\Scripts\python.exe -m pytest tests/test_bambu_connector.py -q` → **23 passed**
- `.venv\Scripts\python.exe -m ruff check src tests` → **All checks passed**
- Targeted `test_connectors/test_printer_connector/test_config/test_mcp_server` → **82 passed**
- Full suite `pytest -q` → **952 passed** (274 s)
- bambulabs-api 2.6.6 introspection: `Printer.__init__(ip_address, access_code, serial)`, `mqtt_start/mqtt_stop/mqtt_client_ready/get_state/get_percentage/get_nozzle_temperature/get_bed_temperature/nozzle_diameter` all present; `upload_file(file: BinaryIO, filename: str)` and `start_print(filename, plate_number, use_ams=True, ...)` signatures compatible; `GcodeState` members exactly `IDLE/PREPARE/RUNNING/PAUSE/FINISH/FAILED/UNKNOWN` (= `_STATE_MAP` keys), with `_missing_` → `UNKNOWN` so `get_state` never raises on an odd payload; `start_print(…, 1, …)` builds `Metadata/plate_1.gcode` — exactly where KimCad's proven G-code lives.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 4
- Nit: 0

## Findings

### ENG-001 Major: A silently-failed FTPS upload can be reported as a successful send
**Dimension:** Correctness
**Evidence:** `src/kimcad/bambu_connector.py:215` calls `p.upload_file(...)` and discards the return value. In bambulabs-api 2.6.6, `PrinterFTPClient.upload_file` is wrapped by a decorator whose body is `except Exception: logger.error(...)` — a mid-transfer failure (`STOR` aborted by a Wi-Fi blip, printer storage full) is **swallowed and returns `None`**; only connect/login failures (which happen before the wrapped call) raise. `Printer.start_print` returns the result of an MQTT *publish*, which succeeds regardless of whether the file landed — so the connector returns `PrintJob(state=printing, detail="started")` for a file that never arrived. Worse, the printer then sits at `IDLE`, which `job_status` maps to `queued` (bambu_connector.py:56), so the UI's poll chain never reaches a terminal state.
**Why it matters:** A realistic failure (multi-MB FTPS transfer over LAN Wi-Fi) produces a false "sent — printing" instead of a typed soft failure. Mock-only today, but this is precisely the path Stage 11's first hardware run exercises.
**Fix path:** Check `upload_file`'s return: the library returns ftplib's `storbinary` result (`"226 Transfer complete"`) on success, `None`/non-226 on a swallowed failure — treat anything that isn't a `str` starting with `"226"` as an upload failure and raise the existing upload `ConnectorError` (the FakePrinter already returns `f"226 {filename}"`, so a `FakePrinter` variant returning `None` tests it directly).
**Blast radius:** Local to `BambuConnector.send`; no other connector uses this library. Tests to update: add one upload-returns-None case to `tests/test_bambu_connector.py`. No migration, no API change.

### ENG-002 Minor: Raw library exceptions inside a session propagate undecorated from send()/capabilities()
**Dimension:** Correctness
**Evidence:** `src/kimcad/bambu_connector.py:135-146` — `mqtt_start()` / `mqtt_client_ready()` calls are not wrapped; only the factory call (line 125-133) and the ready-timeout are converted to typed errors. The library's `mqtt_start` → paho `connect_async` is non-blocking (so the common unreachable-printer case correctly lands on the timeout → `PrinterOffline` path — verified in source), but a library/paho exception here (bad port value, paho internal error) would leave `send()` raising a raw exception, against the module's "never an undecorated exception" connector posture (`printer_connector.py:257`). The webapp degrades safely (catch-alls at `webapp.py:1279`/`1348` — no traceback to the browser, but the send path turns it into a generic 500 instead of a soft typed outcome); the CLI `--send` path (`cli.py:235`) catches only `ConnectorError` and would print a traceback.
**Why it matters:** Low likelihood, but the failure mode is a 500/traceback instead of the soft "not sent" contract every other connector keeps.
**Fix path:** Wrap the `printer.mqtt_start()` call (and the ready-poll) in `except ConnectorError: raise / except Exception as e: raise PrinterOffline(...) from e`, mirroring the factory arm directly above.

### ENG-003 Minor: Bambu send silently prints plate 1 of a hypothetical multi-plate 3MF, diverging from the documented connector invariant
**Dimension:** Correctness
**Evidence:** `src/kimcad/slicer.py:114-116` documents the alignment: a >1-plate archive "would prove OK yet be refused at send" via `extract_single_plate_gcode` — "keep the two layers aligned." The Bambu path doesn't extract (`bambu_connector.py:201-203` uploads the whole file) and hardcodes plate 1 (`:222`), so a multi-plate file would upload fully and silently print only plate 1. Unreachable today (KimCad emits single-plate only — README's "started by plate" claim is honest for current output), but the invariant the comment asks to preserve is now connector-dependent.
**Why it matters:** If multi-plate slicing ever ships, every other connector refuses loudly while Bambu silently prints a third of the job.
**Fix path:** Count `Metadata/plate_*.gcode` members before upload and refuse >1 with the same message `extract_single_plate_gcode` uses (or update the slicer.py comment to name `BambuConnector` as the third place to teach).

### TEST-001 Minor: Two real test gaps — session teardown on upload failure, and the lib's documented `"Unknown"` percentage string
**Dimension:** Tests
**Evidence:** `tests/test_bambu_connector.py` (23 tests) covers the gate, busy, offline-timeout, byte-identity, state map, and config arms well — but (a) no test that `mqtt_stop` runs when `upload_file` raises mid-session (the `finally` at `bambu_connector.py:147-151` handles it by construction, but it's the exact regression a future refactor breaks), and (b) no test for `get_percentage()` returning a non-numeric string — the library types it `int | str | None` and its docstring says it returns `"Unknown"`; `float("Unknown")` → `ValueError` is caught at `bambu_connector.py:240`, but untested.
**Why it matters:** Both are by-construction-correct today and one `try` reshuffle away from not being; the fake transport makes each a 5-line test.
**Fix path:** Add a `FakePrinter` whose `upload_file` raises (assert `mqtt_stopped is True` and the typed upload error) and one with `percentage = "Unknown"` (assert `progress == 0.0`, no crash).

### DOC-001 Minor: Stale connector enumerations in the CLI help and README send section
**Dimension:** Docs
**Evidence:** (a) `src/kimcad/cli.py:81-83` `--send` help: "ships 'mock' (loopback) and 'octoprint' active; 'moonraker'/'prusalink' are supported but commented out" — no mention of the bambu templates, which ship *visible-but-unconfigured* (a third category the sentence's model doesn't have). (b) `README.md:282-286` CLI bullet enumerates `--send octoprint/moonraker/prusalink` only ("entries for them are commented examples"), omitting bambu. (c) `README.md:316` reasons-table `busy` row: "send (PrusaLink 409 only — OctoPrint/Moonraker report a busy upload as `error`)" — the Bambu connector now raises a pre-upload `busy` on send too (`bambu_connector.py:207-213`), so "PrusaLink 409 only" is no longer true. The new connector-table row and Bambu setup note themselves are accurate; ARCHITECTURE.md's new module row matches the implementation.
**Why it matters:** The change altered observable behavior (a new send path, a new `busy` source) and three surfaces still describe the old world.
**Fix path:** Add bambu to the `--send` help and the README CLI bullet (noting the visible-but-unconfigured template posture), and amend the `busy` row to "PrusaLink 409 and Bambu pre-upload check."

## What's working
- **Real-API binding is correct** — every method name/signature the connector touches exists in bambulabs-api 2.6.6 as called; `GcodeState` member names match `_STATE_MAP` exactly (and the enum's `_missing_` → UNKNOWN means an unrecognized payload degrades to the connector's error state, never a raise); plate-1 start resolves to `Metadata/plate_1.gcode`, KimCad's actual G-code location.
- **Session lifecycle** (`bambu_connector.py:120-151`): `ensure_sendable` fires before any session (proven by `test_send_requires_explicit_confirm` asserting `mqtt_started is False`); a factory failure never enters the `finally`; `mqtt_stop` is exception-proofed; no mutable instance state, so the per-request webapp pattern is thread-safe; the ready-poll checks the deadline before sleeping (no pathological spin or over-wait).
- **Secret hygiene**: every f-string in `bambu_connector.py` / the bambu arm of `connectors.py` was checked — the access code never appears; config errors name the env *var*, the library's FTPS errors don't echo the password.
- **Offline semantics fit the library**: `connect_async` is non-blocking, so the unreachable-printer case correctly lands on the ready-timeout → `PrinterOffline` (with the LAN checklist), and `status()` returns a snapshot instead of raising. All raised reasons (`offline`/`busy`/`config`/`error`/internal `not_confirmed`) stay inside the documented vocabulary; a wrong access code surfaces as offline (MQTT, with "access code" named in the checklist) or a typed upload error naming the access code — sensible, even without a distinct `auth` reason (MQTT auth failure is indistinguishable from unreachable at this layer).
- **Config/template safety**: empty `base_url:`/`serial:` parse to `None` → distinct actionable config errors; `test_default_yaml_ships_bambu_visible_but_unconfigured` pins both templates unconfigured and `mock` still first; full suite (952) confirms no consumer assumes a fixed connectors count.

## Watch items
- `start_print` returning True only proves the MQTT *publish* succeeded, not that the printer accepted the job — first hardware session (Stage 11) should confirm a refused job actually returns False rather than True-then-IDLE.
- `job_status` maps `IDLE` → `queued` (never terminal), so a job that vanishes printer-side polls until the webapp's 10-minute cap; consider whether a long-`IDLE` job should age out to `error`.

## Escalation recommendation
No escalation needed — one Major with a one-line fix plus small minors, all local to the new connector and its docs; nothing architectural, nothing security-relevant.
