# Audit Lite - Beta Readiness Bootstrap
**Date:** 2026-06-10
**Scope:** Reviewed the first audit-remediation bootstrap slice: license/security hygiene, ignored audit leftovers, Python 3.13 lockfile, OpenSCAD checksum pinning, and CadQuery worker discovery.
**Reviewer:** Codex (audit-lite)

## TL;DR
Ship this slice. It is scoped, additive, and verified on the target Windows checkout with Python 3.13.13, real OpenSCAD/OrcaSlicer tools, the CadQuery worker venv, and the frontend Node 22 toolchain. No findings.

## Severity Rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Findings

None.

## What's Working
- DOC-002 now has an actual root license grant plus a regression check: `LICENSE` exists and `tests/test_project_hygiene.py:10` verifies it matches the `Apache-2.0` declaration.
- Audit-run leftovers are now ignored in `.gitignore`, and `tests/test_project_hygiene.py:21` pins both `/output_test/` and `.pytest_run_full.txt`.
- The 3.13 lockfile captures the critical compiled pins (`numpy==2.2.6`, `scipy==1.17.1`) and the README tells beta reproducers to install it first (`README.md:97`).
- DOC-003 is closed for the Windows OpenSCAD fetch: `scripts/fetch_tools.py:60` now records the observed SHA-256 for `OpenSCAD-2021.01-x86-64.zip`.
- CadQuery live tests no longer depend on a global `py` launcher: discovery now checks the documented repo-local `.venv-cq313` worker first (`src/kimcad/cadquery_runner.py:322`).

## Runtime Verification

- `.venv\Scripts\python.exe -m ruff check .` -> passed.
- `.venv\Scripts\python.exe scripts\check_geometry_backends.py` -> passed.
- `.venv\Scripts\python.exe -m pytest` -> 857 passed in 196.88s.
- `.venv\Scripts\python.exe -m pytest -m live` -> 18 passed, 0 skipped after CadQuery provisioning.
- `npm --prefix frontend ci` using portable Node 22.13.1 -> passed, 0 vulnerabilities.
- `npm --prefix frontend run typecheck` -> passed.
- `npm --prefix frontend run test` -> 287 passed.
- `npm --prefix frontend run build` -> passed; no committed SPA diff.
- `ollama list` -> `gemma4:e4b` installed.
- `kimcad models` -> reports `gemma4:e4b` installed and recommended.

## Watch Items

- `cadquery` currently resolves `cadquery-ocp 7.8.1.1.post1` on Python 3.13 because the available `cadquery` package requires `cadquery-ocp<7.9`; this differs from the handoff's expected 7.9.x line and should be tracked in the Python 3.13 migration notes.
- The native `scripts/ci.sh` was not invoked directly because the available `bash` is the Windows WSL launcher; the component commands were run natively in PowerShell instead.
- Hosted CI enablement and `pip-audit` are still pending because they require the separate GitHub/Actions decision path.

## Escalation Recommendation

No escalation needed for this small slice. Continue with the first-run hardening and Python-version-doc reconciliation slices under the normal audit cadence.
