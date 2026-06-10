# Audit Lite — Stage B: quality-gate depth (TEST-004/005/006/008/009)
**Date:** 2026-06-10
**Scope:** New `tests/test_printability.py` (5 real-geometry seam tests + 1 real-OpenSCAD pipeline contract test), conftest import-probe extension, TEST-009 named-constant cleanup.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. The validate_mesh→run_gate seam is now tested with real trimesh geometry in both directions (a genuine 2-solid stray warns; a sealed hollow container's nested cavity does NOT — the exact false-positive class the stray/nested split exists for), and the full Pipeline.run orchestration now drives the REAL OpenSCAD binary in an always-on (binary-gated) test. A partial install now fails pytest with one actionable line instead of a ModuleNotFoundError cascade.

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**

## Adversarial checks performed
- **Did the "real OpenSCAD" test actually run the binary?** 0.16 s looked suspicious; verified by construction — no fake renderer is wired, the mesh file exists on disk, is watertight, and the gate measured it at 20 mm (a cube via OpenSCAD 2021.01 genuinely renders that fast). TEST-004's contract-drift net is real.
- **Hollow-cavity representation:** `outer + inverted inner` concatenation produces the intended 2-bodies/0-strays report (asserted), so the no-warn path is tested against real nested geometry, not an assumption.
- **conftest probe scope:** probes only import-time hard deps (pydantic/openai/trimesh/yaml) that previously crashed conftest import before the existing geometry probe could speak; geometry deps stay with the existing deeper probe. UsageError carries the exact pip command.
- **skipif vs live:** the new real-binary test uses the repo's established `_openscad_present()` skipif pattern (same as test_geometry/test_templates) — in CI the binary is provisioned, so it executes there; the no-green-by-skip CI step doesn't cover non-live skips, but the suite count regression (889) would catch a silent skip class growing.
- TEST-008 reviewed: the codegen-guard prose-survival pattern needs no new instances (no prompt fixes landed since); noted for future prompt changes.

## Tests
6 new (5 seam + 1 real-tool contract); ruff clean; printability/templates/pipeline suites 92 passed.

## Escalation recommendation
No escalation.
