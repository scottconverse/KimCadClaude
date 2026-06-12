# Audit Lite - UI-v2 Slice 6 Print Outcome Capture
**Date:** 2026-06-12
**Scope:** Real-send outcome prompt, `/api/print-outcome/<rid>`, local history `print_outcome`, docs, rebuilt SPA bundle.
**Reviewer:** Codex (audit-lite)

## TL;DR
Ship after the full gate. The UI asks for print outcome only after a non-simulated successful send, and non-skip answers are recorded in the existing local Smart Mesh history store without prompt text or geometry.

## Severity Rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Findings

No findings.

## What's Working
- Correctness: `frontend/src/components/SendPanel.tsx` sets the prompt only when `sendDesign` returns `sent:true` and `simulated:false`; simulated sends are covered by regression test.
- Persistence: `src/kimcad/history.py` loads old records with `print_outcome=None` and persists new outcome values.
- Backend: `src/kimcad/webapp.py` validates the outcome vocabulary, treats `skip` as non-recording, and appends a coarse local history row from the live design snapshot.
- API contract: `frontend/src/api.ts` and `docs/api.md` document and exercise `POST /api/print-outcome/<rid>`.
- UX: the four choices are visible as buttons, wrap on narrow panels, and outcome save/error/skipped states are rendered inline.

## Verification
- `.\.venv\Scripts\python.exe -m pytest tests/test_history.py::test_record_and_load_round_trip tests/test_webapp.py::test_print_outcome_endpoint_records_real_world_result -q` - 2 passed.
- `npm.cmd --prefix frontend run test -- api.test.ts SendPanel.test.tsx` - 71 passed.
- `npm.cmd --prefix frontend run test` - 378 passed.
- `.\.venv\Scripts\python.exe -m pytest tests/test_history.py tests/test_webapp.py -q` - 146 passed.
- `npm.cmd --prefix frontend run build` - TypeScript and Vite build passed.

## Watch Items
- The endpoint is advisory and best-effort; the UI enforces the "after a real send" timing. A future authenticated/session-token pass (#31) can add stricter server-side sequencing if needed.

## Escalation Recommendation
No audit-team escalation for this slice. The UI-v2 epic still needs the planned full walkthrough and five-role audit at epic close.
