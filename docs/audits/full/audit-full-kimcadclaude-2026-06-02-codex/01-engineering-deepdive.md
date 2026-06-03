# Engineering Deep-Dive - KimCadClaude full project

**Audit date:** 2026-06-02  
**Role:** Principal Engineer  
**Scope audited:** Python core, provider/model layer, pipeline, webapp, connector safety seams, frontend build/runtime seam, config, CI scripts.  
**Auditor posture:** Balanced

## TL;DR

The implemented engineering surface is sound. Stage 6 added a model layer without widening the unsafe parts of the system: advisory-only model selection, opt-in fallback, isolated bake-off measurement, and narrow plan-parse failure handling. No engineering code findings were found in this full pass; the serious findings are docs/control-plane and CI-gate accuracy.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Safety seams are explicit** - print confirmation, send-gate behavior, model fallback, and plan-failure boundaries are all named in code and tests.
- **Provider abstraction is clean** - `Provider` protocol keeps `Pipeline` from coupling to concrete provider implementations.
- **Template re-render path is deterministic** - `/api/render/<id>` rebuilds from template values without a model call, refreshes mesh URL, and invalidates stale G-code.
- **No obvious secret leak pattern** - connector credentials are env-var sourced and tests assert API keys do not appear in representative connector errors.

## What couldn't be assessed

- No production telemetry or real printer hardware was available.
- Dependency CVE audit for Python packages was not run with `pip-audit`; npm audit was run and clean.

## Findings

No engineering code findings.

## Dependency snapshot

| Dependency area | Observation |
|---|---|
| Python deps | Reasonable and domain-appropriate: OpenAI SDK, Pydantic, Trimesh, NumPy, Manifold3D. |
| Frontend deps | React 18, Vite 8, Three.js; `npm audit` found 0 vulnerabilities. |
| External binaries | OpenSCAD + OrcaSlicer are pinned/fetched under `tools/`; live slice verified through API. |

## Appendix: artifacts reviewed

- `src/kimcad/pipeline.py`
- `src/kimcad/webapp.py`
- `src/kimcad/llm_provider.py`
- `src/kimcad/model_advisor.py`
- `src/kimcad/bakeoff.py`
- `src/kimcad/benchmark.py`
- `src/kimcad/connectors.py`
- `frontend/src/App.tsx`
- `frontend/src/components/*`
- `frontend/src/api.ts`
- `config/default.yaml`
- `scripts/ci.sh`
- `.github/workflows/ci.yml`

