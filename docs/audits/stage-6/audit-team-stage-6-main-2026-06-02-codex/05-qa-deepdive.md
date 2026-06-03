# Runtime QA Deep-Dive - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Role:** QA Engineer  
**Scope audited:** CLI, backend API, local demo web UI, frontend console health, build/test/runtime commands.  
**Environment:** Windows, Python 3.14.3 test environment, in-app Browser at 1280 x 720, local demo server on `127.0.0.1:8766`.  
**Auditor posture:** Balanced

## TL;DR

Runtime QA is clean for the Stage 6 code surface. The CLI advisor runs and recommends Gemma on this box, bake-off invalid input fails cleanly, the web demo renders a complete workspace with no console warnings/errors, and direct render API verification returns a new 90 mm result plus a versioned mesh URL. The only runtime limitation is that Browser automation could not conclusively perform a real range-slider drag or screenshot capture.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **CLI model advisor** - `kimcad models` detected Windows 11, 31 GB RAM, installed Ollama models, and recommended Gemma E4B.
- **CLI error handling** - invalid bake-off prompts path returned a clean message instead of a traceback.
- **Web demo flow** - prompt-to-workspace rendered successfully with no console warnings/errors.
- **Re-render API** - posting width 90 to `/api/render/<id>` returned a 90 x 60 x 40 mm pass report and `/api/mesh/<id>?v=1`.
- **Build/test gate** - ruff, full pytest, frontend tests, frontend build, and npm audit passed.

## What couldn't be assessed

- Real hardware printers are not in scope until the later hardware phase.
- Browser screenshot capture timed out.
- Browser range-control drag/keyboard automation did not generate a conclusive re-render event; direct API verification and unit tests cover the path, but this is not a rendered pointer/touch proof.
- Mobile viewport was not tested in this pass.

## Product shape

KimCad is a local-first CLI plus local web app for AI-assisted 3D-print part generation. QA focused on Stage 6 model-layer behavior, the web demo path, re-render API health, and the documented local gate.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Full Python test suite | Pass: 609 tests | None |
| Frontend Vitest suite | Pass: 37 tests | None |
| Frontend production build | Pass | None |
| npm audit | Pass: 0 vulnerabilities | None |
| CLI model advisor | Pass | None |
| CLI bake-off invalid prompts path | Pass: clean error | None |
| Web demo prompt to workspace | Pass | None |
| Direct render API width change | Pass | None |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Invalid bake-off prompts file | Clean error, non-zero exit | None |
| Direct `/api/render/<id>` with changed width | Clean completed payload, pass report, versioned mesh URL | None |
| Browser console after demo flow | No warnings/errors | None |

## Findings

No QA findings.

## Performance snapshot

| Metric | Observed | Verdict |
|---|---:|---|
| Full pytest suite | 609 passed in 1:44 | Pass |
| Focused Stage 6/backend pytest | 184 passed in 29.08 s | Pass |
| Frontend tests | 37 passed in 4.94 s | Pass |
| Frontend build | Vite build completed in 335 ms | Pass |

## Security / privacy snapshot

- Cloud fallback remains opt-in via `llm.alt_backend`.
- Credentials are still env-var based in reviewed config/docs.
- No browser console errors or mixed-content warnings surfaced in the local demo flow.

## Console and log observations

Browser console warnings/errors after landing and workspace render: none.

## Appendix: environments and artifacts

- Browser viewport: 1280 x 720, DPR 1.68.
- Local server started in demo mode on port 8766.
- Direct API checked with local HTTP requests.

