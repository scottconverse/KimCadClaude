# Audit Team — #26 (KC-21) Duet + Marlin connectors stage close
**Date:** 2026-06-14
**Scope:** The two new send-to-printer connectors — `duet_connector` (RRF `/rr_*` HTTP) + `marlin_connector` (M-code serial/TCP), their mocks, tests, registry, config, and docs. A 4-role review (Principal Engineer, Test Engineer, QA Engineer, Technical Writer) run via Workflow, hunting for what the per-slice audit-lites missed.

## Executive summary

The connectors were structurally sound (correct reuse of the `ensure_sendable` gate + the audited error taxonomy, genuine statelessness/thread-safety, secret hygiene), but the holistic review found **27 cross-cutting protocol-correctness issues (13 Major / 12 Minor / 2 Nit)** the per-slice passes couldn't see — issues that could **mis-drive real hardware while the tests stay green** because the conformance mocks were too convenient. **All 27 are remediated; the connectors are at 0/0/0/0/0.** The central theme: the mocks were strengthened from convenient oracles into adversarial ones (fault injection, faithful completion reset, session pools), and the connectors hardened to match.

## Severity roll-up

| | Found | Remediated |
|---|---|---|
| Blocker / Critical | 0 | — |
| Major | 13 | 13 |
| Minor | 12 | 12 |
| Nit | 2 | 2 |
| **Total** | **27** | **27** |

## Findings → remediation (all landed this pass)

**Marlin — protocol integrity**
- **ENG-001 / TE-03** SD upload streamed with no line numbers/checksums → a corrupted serial line was silently written. **Fixed:** `M110 N0` + `N<n> … *<xor>` framing per line + honor `Resend: <n>` (rewind + replay, bounded). Mock injects a `Resend:` to prove it.
- **QA-2** `send` wrote to SD with no firmware handshake → a wrong-baud/non-Marlin peer got a garbage file + a phantom job. **Fixed:** `M115` identity check before any SD write (test: a dumb peer is rejected, no `M28` sent).
- **TE-04 / QA-3** a mid-stream `Error:`/drop left the SD file open, untested. **Fixed:** best-effort `M29` on failure; mock injects an `Error:` mid-stream. (SD-write *stores* lines, doesn't execute them — so the feared heat-pause-mid-stream can't occur; documented.)
- **ENG-005 / ENG-008** busy heartbeats / boot banner could confuse the reader. **Fixed:** the read-until-`ok` loop skips `echo:busy:`/banner lines; a `banner` mock mode + bounded resend budget cover it.
- **QA-5** `status` reported a non-Marlin peer as operational. **Fixed:** identity guard → error.

**Duet — RRF correctness**
- **ENG-002** job name flowed unsanitized into the `M32 "0:…"` command (quote/newline injection). **Fixed:** `_safe_upload_name` (alnum + `-_`), used for both the upload name and the M32 string; injection test.
- **ENG-003 / QA-4** connect-per-op never `/rr_disconnect`'d → a polling UI could exhaust RRF's small session table and report a false "busy". **Fixed:** `/rr_disconnect` in a `finally` per op; mock models a finite session pool (test proves ≤1 open + never exhausted).
- **QA-1** a failed `M32` was reported as `printing`. **Fixed:** the `rr_gcode` reply is checked; a non-zero `err` raises.
- **ENG-007** a 200 with no `err` was treated as a successful upload. **Fixed:** require `err == 0` before `M32`.
- **ENG-006** temps parsing assumed one RRF shape. **Fixed:** `_temps` tolerates `bed` as dict/number/list + the `current` array; unit test over the variants.

**Both — job completion (ENG-004 / TE-01 / TE-02 / QA-6)**
Done detection passed only because the mocks were sticky at 100%. **Fixed:** the mocks now faithfully reset (`fractionPrinted`→0 on RRF idle; "Not SD printing" after a Marlin print), and each connector **latches** done (progress-seen → later idle == done, never regressing to queued). A poll-past-done test pins it. The remaining identity limitation (no per-file query over the classic surface) is documented in the connector docstrings + the user docs.

**Tests (TE-05/06/07/08)** Parametrized the RRF status chars + Marlin M27 outcomes; assert the **exact uploaded bytes** reconstruct the source (Duet `uploaded_body`, Marlin `sd_lines`); added the pyserial-PRESENT real-serial path via an injected fake `serial` module (happy + open-failure). *(TE-07 — the Marlin mock advancing on `M27` — is kept as a deliberate determinism choice: the connector only ever reads, so the read-only-`M27` purity gap can't change its behavior; documented.)*

**Docs (TW-01..05)** README "Send to a printer" gains `duet`/`marlin` rows + the two new mock servers; `pyserial` documented in README + troubleshooting (the `serial` extra); the job-completion + 8.3-filename limitations disclosed in README + supported-printers + troubleshooting; the CHANGELOG carries the "API-validated against the mock; metal at #11" hedge.

## Verification
- Connector suite: **92 passed** (Duet 30, Marlin 24, registry + others); the broader connector-surface set: **279 passed**.
- ruff clean across `src` + `tests`; both mocks import + run.
- The mocks now FAIL the connector if the integrity/handshake/latch fixes regress (fault-injection + faithful-reset modes), so the green is earned, not convenient.

**Verdict: 0/0/0/0/0. Metal validation (a real Duet board + a real Marlin serial line) remains #11. #26 closes on the gate's green.**
