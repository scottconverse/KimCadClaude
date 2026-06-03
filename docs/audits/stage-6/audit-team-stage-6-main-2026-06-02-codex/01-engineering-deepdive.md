# Engineering Deep-Dive - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Role:** Principal Engineer  
**Scope audited:** Stage 6 model layer, pipeline integration, fallback wiring, bake-off isolation, plan-failure handling, web render endpoint, config.  
**Auditor posture:** Balanced

## TL;DR

Engineering is solid for the current Stage 6 artifact. The model-selection machinery remains advisory-only, fallback is opt-in and narrow, the bake-off isolates each backend from fallback contamination, and plan failures are caught only at the parse boundary. No engineering findings were found in this fresh pass.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Narrow fallback boundary** - `FallbackProvider` catches `APIConnectionError`, `APITimeoutError`, and `NotFoundError` only; tests pin that arbitrary exceptions propagate.
- **Provider protocol is clean** - `Pipeline` depends on the `Provider` protocol rather than concrete provider classes.
- **Bake-off isolation holds** - `_pipeline_for_backend` is tested to build a bare `LLMProvider` even when `alt_backend` is configured.
- **Re-render API invalidates stale slices** - `webapp.py` updates `gate_status_by_rid`, removes cached G-code, drops slice cache entries, and returns a versioned mesh URL.

## What couldn't be assessed

All engineering source paths needed for this audit were accessible.

## Findings

No engineering findings.

## Dependency snapshot

| Area | Result |
|---|---|
| Python lint | `ruff check src/kimcad tests` passed |
| Python tests | `python -m pytest tests` passed: 609 tests |
| Frontend tests | `npm --prefix frontend test -- --run` passed: 37 tests |
| Frontend audit | `npm --prefix frontend audit --audit-level=moderate` found 0 vulnerabilities |

## Appendix: artifacts reviewed

- `src/kimcad/llm_provider.py`
- `src/kimcad/model_advisor.py`
- `src/kimcad/benchmark.py`
- `src/kimcad/bakeoff.py`
- `src/kimcad/pipeline.py`
- `src/kimcad/cli.py`
- `src/kimcad/webapp.py`
- `config/default.yaml`
- Stage 6 remediation package under `docs/audits/stage-6/audit-team-stage-6-2026-06-02/`

