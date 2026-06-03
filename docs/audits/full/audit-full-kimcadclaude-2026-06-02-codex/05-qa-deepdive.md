# Runtime QA Deep-Dive - KimCadClaude full project

**Audit date:** 2026-06-02  
**Role:** QA Engineer  
**Scope audited:** CLI, web UI, API, slice path, local test/build gate.  
**Environment:** Windows, Python venv, local KimCad server on `127.0.0.1:9876`, Browser viewport 1280 x 720.  
**Auditor posture:** Balanced

## TL;DR

Runtime QA passed for the currently implemented product. The CLI help and model advisor work, the actual KimCad web server rendered the demo flow, the browser console stayed clean, the re-render API updated geometry and cache-busted the mesh URL, and the slice API produced a proven G-code 3MF for Bambu P2S / PLA. No runtime QA findings were found.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **CLI discoverability** - `kimcad --help` lists the five commands: design, web, bench, models, bakeoff.
- **Model advisor runtime** - `kimcad models` detected installed models and recommended Gemma E4B.
- **Web flow** - Landing page -> prompt -> workspace rendered successfully.
- **API re-render** - `POST /api/render/1` with width 90 returned a 90 x 60 x 40 mm pass report and `/api/mesh/1?v=1`.
- **API slice** - `POST /api/slice/1` for P2S/PLA produced `sliced: true`, 80,860 G-code lines, estimate, profiles, and `/api/gcode/1`.
- **Console health** - Browser console warnings/errors were empty after the demo flow.

## What couldn't be assessed

- Real printers and real hardware sends were not available.
- Mobile layout was not tested.
- Screenshot capture was not available due Browser runtime timeout in the prior pass.

## Product shape

KimCad is a local-first CLI plus local web app that runs CAD/slicer/model workflows on a user's machine. QA focused on current implemented flows rather than future v3.0 target features.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| CLI help | Pass | None |
| CLI model advisor | Pass | None |
| Web demo prompt to workspace | Pass | None |
| Direct API re-render | Pass | None |
| Direct API slice | Pass | None |
| Full pytest | Pass: 609 | None |
| Frontend tests/build | Pass: 37 tests + build | None |
| npm audit | Pass: 0 vulnerabilities | None |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Port collision on 8767 | Existing unrelated uvicorn process owned port; switched to 9876 before judging KimCad | None |
| Invalid hosted/API shape on wrong process | Identified as not the KimCad server | None |
| API re-render after web design | Returned correct updated payload | None |
| Slice after web design | Returned successful slice payload | None |

## Findings

No QA findings.

## Performance snapshot

| Metric | Observed | Verdict |
|---|---:|---|
| Full pytest | 609 passed in 1:44 | Pass |
| Focused Stage 6/backend pytest | 184 passed in 29.08 s | Pass |
| Frontend tests | 37 passed in 4.94 s | Pass |
| Frontend build | Completed in 335 ms | Pass |
| Direct demo slice | Completed in ~3.4 s via API | Pass |

## Security / privacy snapshot

- Server binds localhost by default.
- No console warnings/errors in the tested web flow.
- Cloud fallback remains opt-in config.
- No real printer send was attempted.

## Appendix: environments and artifacts

- `http://127.0.0.1:9876/`
- `/api/options`
- `/api/render/1`
- `/api/slice/1`
- `kimcad --help`
- `kimcad models`

