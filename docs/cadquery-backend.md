# CadQuery — KimCad's editable-CAD (.STEP) export engine

KimCad's geometry backend is OpenSCAD: the template engine emits it deterministically, and
the (opt-in) experimental generator targets it. **CadQuery is the optional export engine on
top**: with it installed, every **template-built part** also offers an editable **`.STEP`**
download — precision BREP CAD geometry (CadQuery's OCCT kernel) that OpenSCAD cannot
produce. Open it in Fusion 360, FreeCAD, SolidWorks and the like to keep modeling.

CadQuery is **optional and gracefully absent**: with no suitable interpreter found, the
export simply isn't offered and everything else works exactly as before — the same posture
as the optional PrintProof3D engine.

## How the STEP is built — trusted twins, never AI code

Every shipped template family has a **CadQuery twin** in `src/kimcad/cadquery_templates.py`:
KimCad's own code building the *same geometry* as the family's OpenSCAD library module,
parameterized only by the family's clamped float values (each value passes through
`float()` — values are data, never code). The contract is pinned by tests: each twin renders
**watertight** at the family's analytic `expected_bbox` (the printability-gate target) per
axis, live through the real worker.

The export is **lazy**: nothing CadQuery-related runs during design or slider re-renders.
The `.STEP` builds on the *first download* (a few seconds), is cached, and is invalidated by
any re-shape — a download always matches the live geometry.

> **History (Stage 8 → KC-4).** CadQuery originally also ran as an LLM *fallback generator*:
> when the OpenSCAD codegen path failed, the model re-generated the part as CadQuery Python.
> Its realized lift was later **measured at 0** on the shipping model
> ([the benchmark](benchmarks/stage-8-cadquery-backend.md)), so that path was removed — and
> with it the only place AI-written Python was ever executed. Today **no LLM writes CadQuery
> code**; only the trusted twins run.

## Why it still runs out of process

Defense in depth, and the same arm's-length posture as OpenSCAD/OrcaSlicer (spec §6.4/§12).
The worker pipeline — static sanitizer, then `exec` in a restricted namespace in a separate
interpreter — predates the fallback's removal and stays, so even KimCad's own generated
scripts run with no more privilege than they need:

```
main app (3.13)                              worker (own 3.13 env + cadquery)
─────────────────                            ─────────────────────────────────
cadquery_runner.render_cadquery(code)
  ├─ sanitize_cadquery(code)   ── static block-list (layer 1)
  ├─ write script to the design dir
  └─ subprocess: <python> cadquery_worker.py ──►  exec(script) in a restricted
        (request JSON on stdin)                    namespace (layer 2); export
        ◄── result JSON in a result file           STL + STEP; measure bbox
```

## Enabling it

**In the app:** *Settings → Editable CAD export* shows whether the engine is installed and
walks through the one-time setup:

1. Install Python 3.13 (python.org) if you don't have it.
2. `py -3.13 -m pip install cadquery` (a few minutes — it's a full CAD kernel).
3. Click *check again* in Settings (or restart KimCad) — discovery is automatic.

**From source:** the repo convention is a dedicated worker venv next to the app's:

```
py -3.13 -m venv .venv-cq313
.venv-cq313\Scripts\pip install cadquery
```

**Discovery order:** the repo-local `.venv-cq313` first, then the Windows launcher
(`py -3.13/-3.12/-3.11`), then `python3.x` on `PATH`. Pin or disable with
`binaries.cadquery_python` in `config/local.yaml`: `null` = auto-discover, `false` = force
off, or an explicit interpreter path (authoritative — no fall-through).

The installed beta does **not** bundle CadQuery; the Settings card is the supported install
path. (Bundling a minimal OCCT engine for one-click STEP remains an open option — tracked on
the issue board.)

## Proving it

- **Deterministic engine bench** (no model, runs under the `needs_cadquery` marker):
  `pytest tests/test_cadquery_bench.py` renders a fixed script spread through the real
  worker — watertight at declared envelopes.
- **Template-twin contract**: `pytest tests/test_cadquery_templates.py` proves every shipped
  family's twin live — watertight, per-axis bbox == the analytic gate target, non-trivial
  `.step` on disk.
- **Web wiring**: `tests/test_webapp.py` pins the lazy build, caching, re-render
  invalidation, and the honest no-engine Settings pointer.

Worker limits: wall-clock `limits.cadquery_timeout_s` (default 120 s) and the standard
`max_output_bytes` cap; a failed export is reported (the `.STL` is always there) and never
breaks a build.
