# Stage 7 — Audit-Team Remediation → 0/0/0/0/0

The full 5-role `audit-team` ran 2026-06-02 over `main...stage-7-smart-mesh` and returned, as-found:
**0 Blocker · 0 Critical · 1 Major · 11 Minor · 9 Nit = 21.** Every finding was then fixed (the
stage gate requires 0/0/0/0/0 before tag). See `sprint-punchlist.md` for the per-finding fix +
status; the per-role detail is in `01..05-*-deepdive.md`.

## The Major (ENG-701) in detail
`HistoryStore.record` was a non-atomic read-modify-write with no lock. Under the threaded web
server, concurrent designs raced and lost records (the Principal Engineer reproduced 40 writers
collapsing to ~1). **Fix:** a process-wide `_WRITE_LOCK` serializes the read-modify-write, and the
write is atomic (temp file + `os.replace`), so a concurrent write can neither lose records nor
observe a half-written file. **Regression test:** `test_record_is_thread_safe_under_concurrency`
spawns 40 threads and asserts all 40 records survive (`tests/test_history.py`).

## Verification (after remediation)
- `ruff check src/kimcad tests` — clean.
- Python (Stage-7 + pipeline/webapp/cli/config suites) — 167 passed; `test_history.py` 15 passed
  (incl. the concurrency + the two new boundary/coverage tests); full suite green.
- Frontend — `vitest` 43 passed; `npm run build` clean (tsc --noEmit + vite), committed
  `src/kimcad/web/assets/*` regenerated.
- The native Windows pre-push gate (ruff + full pytest incl. live OrcaSlicer + vitest + SPA
  build-reproducibility) gates the push.

## Tests added this remediation
- `test_record_is_thread_safe_under_concurrency` (ENG-701)
- `test_gate_failed_part_is_still_recorded_to_history` (TEST-S7-001)
- `test_unanalysable_mesh_keeps_confidence_low_even_when_the_engine_ran` (TEST-S7-002)
- `test_compare_phrase_at_two_same_type_still_falls_back_to_all_parts` (TEST-S7-003)

**Roll-up: 0 / 0 / 0 / 0 / 0.** Cleared for the native gate → merge → tag `stage-7`.
