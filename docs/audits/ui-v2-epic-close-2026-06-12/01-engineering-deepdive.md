# 01 - Engineering Deep-Dive

## Scope

UI-v2 epic (#23) final audit after slices 5-6, including the browser server, SPA build artifacts, direct-print outcome flow, and API docs contract.

## What's Working

- The core local-first architecture remains coherent: stdlib HTTP server, compiled React SPA, loopback default, and no runtime Node dependency.
- Send and slice safety are already strong: gate-failed/stale parts cannot be sliced or sent, and the send endpoint treats the POST as explicit confirmation.
- The final CI gate includes real HTTP tests, live slicer coverage, CadQuery worker checks, Vitest component tests, and build reproducibility.

## Findings

### ENG-001 - Major - Correctness/Security - Print outcome recording trusted client timing

**Evidence:** First-pass review of `src/kimcad/webapp.py` showed `/api/print-outcome/<rid>` accepted any existing design id with a non-skip outcome, even though the product contract says outcome capture happens after a real hardware send.

**Why this matters:** A non-browser caller could feed "real print" outcomes into Smart Mesh history without ever sending a print. That corrupts the local learning signal.

**Blast radius:**
- Adjacent code: `/api/send/<rid>`, `SendPanel`, `HistoryStore`.
- Shared state: in-memory design registry and local Smart Mesh history file.
- User-facing: Smart Mesh comparison quality over time.
- Migration: none; this is a stricter runtime guard.
- Tests to update: webapp outcome test.

**Fix path:** Fixed. The server now tracks non-simulated successful sends in-process and returns `409` for non-skip outcomes before a real send.

### ENG-002 - Minor - Hygiene - Browser default favicon request produced console noise

**Evidence:** First Playwright pass saw a Chromium console error for missing `/favicon.ico`.

**Why this matters:** Console noise weakens runtime QA signal and can hide real frontend errors.

**Fix path:** Fixed. `/favicon.ico` returns `204` and is pinned by `test_serves_spa_index_and_assets_and_rejects_traversal`.

## Could Not Assess

No real hardware printer was available, so the final browser pass verified the real-send outcome guard with a stubbed non-simulated connector in tests, not by driving physical hardware.
