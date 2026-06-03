# Test Suite Deep-Dive - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Role:** Test Engineer  
**Scope audited:** Python and frontend test suite, with emphasis on Stage 6 model layer and prior remediation tests.  
**Auditor posture:** Balanced

## TL;DR

The test suite is in strong shape for Stage 6. The full Python suite passed at 609 tests, the frontend suite passed at 37 tests, and the focused Stage 6 tests cover the important safety boundaries. No test-suite findings were found.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Fallback narrowing is pinned** - Tests assert arbitrary primary errors do not trigger alt fallback.
- **Bake-off isolation is pinned** - Tests assert a bake-off backend pipeline is bare even when `alt_backend` exists.
- **Plan parse boundaries are pinned** - Tests distinguish `PlanParseError` from connection errors and ordinary bugs.
- **Frontend state fixes are pinned** - 37 Vitest tests pass, including UI state behavior around Stage 5/6 surfaces.

## What couldn't be assessed

Coverage percentage tooling was not run in this pass.

## Test landscape

| Dimension | Observation |
|---|---|
| Frameworks | Pytest, Vitest |
| Test pyramid shape | Broad unit/integration suite with live OrcaSlicer tests included in the full run |
| Coverage tool | Not assessed |
| Reported coverage | Not assessed |
| Flakiness posture | No flakes observed in this pass |
| CI blocking | Local native gate is documented as pre-push; this pass ran the core commands directly |

## Findings

No test findings.

## Shortcut census

| Shortcut pattern | Count / observation |
|---|---|
| `.skip` / `xit` / `@skip` | Only conditional dependency skips found (`manifold3d` missing path); dependency present here, full suite passed |
| `.only` | None found |
| TODO add test | None found in reviewed test paths |
| Placeholder assertion | None found |
| Retries normalized | None found |

## Appendix: test artifacts reviewed

- `tests/test_fallback_provider.py`
- `tests/test_model_advisor.py`
- `tests/test_benchmark.py`
- `tests/test_bakeoff.py`
- `tests/test_pipeline.py`
- `tests/test_webapp.py`
- `frontend/src/*.test.ts`
- `frontend/src/components/*.test.tsx`

