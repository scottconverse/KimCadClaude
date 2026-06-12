# 04 - Test Deep-Dive

## Scope

Python tests, Vitest frontend tests, CI script, first-pass focused tests, final `scripts/ci.sh` gate.

## What's Working

- The suite has real HTTP integration coverage and does not stop at mocked component tests.
- UI-v2 slices added focused regression tests for the changed contracts.
- `npm audit --audit-level=high` reported 0 vulnerabilities.

## Findings

### TEST-001 - Minor - Regression Coverage - Outcome endpoint lacked a negative pre-send case

**Evidence:** The slice-6 test initially proved outcome recording but did not prove that non-skip outcomes are refused before a real hardware send.

**Why this matters:** The exact bug class was an API client bypassing the SPA's correct timing.

**Fix path:** Fixed. `test_print_outcome_endpoint_records_real_world_result_after_hardware_send` now asserts `409` before a non-simulated send, then proves a stubbed hardware send unlocks recording.

## Could Not Assess

No Playwright suite is committed in CI yet; this audit ran Playwright manually as required by the epic gate. The handoff already tracks CI Playwright as later issue #25.
