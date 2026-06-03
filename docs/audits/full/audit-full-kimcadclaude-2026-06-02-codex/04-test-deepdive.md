# Test Suite Deep-Dive - KimCadClaude full project

**Audit date:** 2026-06-02  
**Role:** Test Engineer  
**Scope audited:** Pytest suite, Vitest suite, local pre-push gate, hosted CI workflow, test shortcut patterns.  
**Auditor posture:** Balanced

## TL;DR

The local test suite is strong and broad: the full Python suite passed at 609 tests, frontend tests passed at 37 tests, and the live slice path is exercised on this machine. The problem is gate provenance: the repo says hosted CI has the same checks, but the GitHub Actions workflow is Python-only and omits the frontend/build/audit/live-gate logic from the actual local gate.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Large meaningful suite** - 609 pytest passed, including live OrcaSlicer paths on this machine.
- **Frontend suite exists and passes** - 37 Vitest tests passed.
- **Regression tests are culture, not decoration** - Stage audit remediation tests are specific and behavior-oriented.
- **Local gate is honest** - `scripts/ci.sh` warns when frontend tooling or live slicer proof is missing and hard-fails those cases under release mode.

## What couldn't be assessed

- GitHub Actions was not run remotely.
- Coverage percentage was not generated.

## Test landscape

| Dimension | Observation |
|---|---|
| Frameworks | Pytest, Vitest |
| Test pyramid shape | Broad unit/integration with selected real external-tool tests |
| Coverage tool | `pytest-cov` is installed, coverage not run in this pass |
| Flakiness posture | No flaky behavior observed |
| CI blocking | Local pre-push is strong; hosted CI is incomplete |

## Findings

### TEST-001 - Major - CI / Regression - Hosted CI does not run the same gate the docs say it does

**Evidence**

- `README.md:253-255` says every push runs `scripts/ci.sh` and "The same checks are defined for hosted CI in `.github/workflows/ci.yml`."
- `scripts/ci.sh:20-52` runs ruff, pytest, frontend Vitest, frontend build reproducibility, and live-slicer/release checks.
- `.github/workflows/ci.yml:18-23` installs Python deps, runs ruff, then runs `pytest -q`. It does not install Node, run Vitest, build the SPA, check committed build reproducibility, run npm audit, fetch/verify external tools, or enforce release-mode live-slicer proof.

**Why this matters**

If GitHub Actions is re-enabled and treated as authoritative, a green hosted check can miss exactly the frontend/build/live-gate regressions the local process says are load-bearing.

**Blast radius**

- Adjacent docs: `README.md`, `HANDOFF.md`, `ROADMAP.md`, `.github/workflows/ci.yml`, `scripts/ci.sh`.
- User-facing: indirect; bad builds or stale committed SPA assets can ship if hosted CI becomes trusted.
- Tests to update: hosted CI workflow.
- Related findings: DOC-001.

**Fix path**

Either update hosted CI to invoke the same gate semantics as `scripts/ci.sh` where possible, including frontend tests/build and explicit live-tool proof behavior, or correct README/HANDOFF to state hosted CI is intentionally partial and not authoritative.

## Shortcut census

| Shortcut pattern | Observation |
|---|---|
| `.only` | None found in reviewed tests |
| `xfail` | None found |
| `skip` | Conditional dependency skips only; full suite passed here |
| Placeholder assertions | None found |
| TODO test debt | No actionable test TODO pattern found |

## Appendix: test artifacts reviewed

- `tests/`
- `frontend/src/*.test.ts`
- `frontend/src/components/*.test.tsx`
- `pyproject.toml`
- `frontend/package.json`
- `scripts/ci.sh`
- `.github/workflows/ci.yml`

