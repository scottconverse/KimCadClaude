# Audit Lite — #26 (KC-21) Slice 1: the Duet / RepRapFirmware connector
**Date:** 2026-06-14
**Scope:** The RRF/Duet send-to-printer connector + its mock-twin: `src/kimcad/duet_connector.py` (new), `src/kimcad/mock_duet.py` (new), `tests/test_duet_connector.py` (new, 19 tests), the `connectors.py` registry + build branch, `tests/test_connectors.py` (5 new), and the `config/default.yaml` example.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. A new `PrinterConnector` for RepRapFirmware/Duet over the classic `/rr_*` HTTP interface, built on the proven Moonraker pattern (stdlib HTTP, no new dependency) and tested against a faithful mock RRF server. 19 connector tests + 5 registry tests pass; the connector surfaces in the SPA's send picker automatically (the frontend is data-driven from `config.connectors()`), so no frontend change is needed. No findings.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

## Findings
None. The connector mirrors the audited Moonraker connector's structure (per-request statelessness, the same HTTPError→AuthError/ConnectorError/PrinterOffline taxonomy, the `ensure_sendable` gate, garbage-200→error degradation) and the mock mirrors `mock_moonraker` (bounded 413 drain, the live-print progress model). The auth path is enforced both ways: a wrong password fails at `/rr_connect` (err 1), and an open connector against a password-protected board is rejected (403→AuthError) — both tested.

## What's working
- **Proven-pattern reuse.** The connector reuses `printer_connector`'s shared helpers + error types, so it inherits the same honest failure semantics the other connectors were audited into (auth vs offline vs faulted; a 5xx reports `online=False`; a non-JSON 200 degrades to an error status, never a traceback).
- **Faithful conformance mock.** `mock_duet` implements exactly the `/rr_connect`, `/rr_status?type=N`, `/rr_upload`, `/rr_gcode` subset the connector reads, emits the JSON shape the connector parses, advances `fractionPrinted` per poll, and enforces the password session — so the tests prove the real protocol contract, not a stub.
- **Honest auth modelling.** RRF runs open on many LANs, so a missing password is not an error (it just sends no `rr_connect`); a configured password is used per-operation. The password never appears in an error message (tested).
- **No frontend work.** The send picker + connections card are data-driven (`getConnector` / `config.connectors()`); only "bambu" is special-cased (for its unique access-code/serial fields). Duet's standard `base_url` + optional password flow through the generic path like octoprint/moonraker/prusalink — so adding the `default.yaml` entry surfaces it.

## Watch items
- **Job-completion detection is approximate.** Over the classic `/rr_status`, a finished print returns to idle (`I`) and the board resets `fractionPrinted` — so the connector infers "done" from idle + progress ≥ 99.9% (the mock holds 100% at completion). A real board that resets the fraction before the next poll would read the tail as idle/queued. This is the documented "API-validated, not metal-validated" posture; metal validation (#11) should confirm, and may switch to RRF3's Object Model (`/rr_model?key=job`) which exposes `state` + `lastFileName` more reliably.
- **Nozzle diameter is not reported** by `rr_status` (so `capabilities` returns `None` for it) — consistent with the connector contract (other connectors also leave it `None` when unavailable).

## Escalation recommendation
No escalation. A self-contained connector + mock + tests on the established pattern; 53 connector tests pass, ruff clean. Slice 2 (Marlin-serial — the harder protocol, needs a serial/TCP transport) is next, then Slice 3 (any UI polish + docs), then the #26 stage close.
