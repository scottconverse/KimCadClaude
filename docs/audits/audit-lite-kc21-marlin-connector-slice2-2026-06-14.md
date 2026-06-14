# Audit Lite — #26 (KC-21) Slice 2: the Marlin-serial connector
**Date:** 2026-06-14
**Scope:** The Marlin send-to-printer connector + its mock-twin: `src/kimcad/marlin_connector.py` (new), `src/kimcad/mock_marlin.py` (new), `tests/test_marlin_connector.py` (new, 14 tests), the `connectors.py` registry + build branch, `tests/test_connectors.py` (4 new), the `config/default.yaml` example, and the optional `pyserial` dependency.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. A new `PrinterConnector` for Marlin firmware over its raw M-code line protocol (the huge Ender-class installed base). Marlin has no host software, so KimCad drives it like a host: SD upload (M28/M29) → select + start (M23/M24) → poll SD progress (M27). The transport is TCP (mock + serial-over-network, stdlib) or a USB serial port (optional pyserial, with a clear install hint). 14 connector tests + 4 registry tests pass against a faithful TCP Marlin mock; surfaces in the send picker automatically. No findings.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

## Findings
None. The connector reuses the audited `printer_connector` contract + `ensure_sendable` gate, opens a fresh transport per operation (thread-safe), and maps connection failures to `PrinterOffline` / a non-Marlin device to a clear `ConnectorError`. The line-protocol reader (`_Transport.command`) reads up to the `ok` ack with a generous cap and surfaces a Marlin `Error:` reply as a clean `ConnectorError`, never a hang or a traceback.

## What's working
- **Right model for a host-less firmware.** Marlin doesn't track "jobs"; the connector uploads to SD and starts an autonomous SD print, then polls `M27` — the correct way a host drives bare Marlin, not a fiction.
- **One protocol, two transports.** The M-code is identical over USB serial and TCP; the connector parses `host:port` → TCP (no dependency; covers the mock *and* real ser2net/ESP3D/OctoPrint-relay bridges) and a port path → pyserial. `_tcp_target` parsing is unit-tested (TCP, `tcp://`, `serial://`, COM, /dev/tty).
- **Graceful optional dependency.** A serial-port target without pyserial reports an actionable "pip install pyserial" config error (tested by forcing the import to fail) — the same graceful-absence posture as the CadQuery/Bambu paths; pyserial stays out of the lockfile.
- **Faithful conformance mock.** `mock_marlin` is a TCP server speaking the exact ack/report subset (M115 firmware string, M105 temps, M28/M29 SD write with real byte counting, M23/M24, M27 progress) and advancing the print per poll — so the tests prove the protocol, including the non-Marlin-device rejection.
- **Honest capabilities.** Marlin's serial surface reports neither build volume nor nozzle diameter reliably, so both are `None` (filled from the chosen profile instead) rather than guessed.

## Watch items
- **Job-completion is inferred, and not sticky.** Marlin's done-signal is asynchronous ("Done printing file") and `M27` reports "Not SD printing" once the print clears — so the connector reports `done` on the poll where progress reaches 100%, but a *later* poll (after the byte count clears) reads as idle/queued. Callers should stop polling at the first terminal state. Metal validation (#11) should confirm and may track the expected total or watch the async done message. This is the documented "API-validated, not metal-validated" posture every connector carries.
- **SD filename is truncated to 8.3** (`bracket.gco`) for firmware without long-filename support — a deliberate conservative choice; a name collision on the SD card would overwrite. Acceptable for the single-job send flow.

## Escalation recommendation
No escalation. A self-contained connector + mock + tests on the established pattern; 71 connector tests pass, ruff clean. Both #26 connectors (Duet + Marlin) are now built; the docs (supported-printers + CHANGELOG) land with this slice, then the #26 stage close.
