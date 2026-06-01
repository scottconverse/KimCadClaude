# Audit Lite — Stage 5 Slice 1: deterministic template engine
**Date:** 2026-06-01
**Scope:** The two new files `src/kimcad/templates.py` (template engine: param schema, registry, derive/clamp/emit, analytic bbox, 7 built-in families) and `tests/test_templates.py`. Engine core only — not yet wired into the pipeline or web UI; no behavior change to existing flows.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after fixes. The engine is sound, genuinely deterministic, and its central honesty invariant — that each family's *declared* bbox equals what it really renders — is proven by a binary-gated test against the real OpenSCAD binary (7/7 watertight, exact bbox). No injection vector (only clamped numbers reach emit; `object_type` is never emitted). Findings are all Minor/Nit and concentrated on value-range edge cases that only bite once the live-slider POST path lands (Slices 3–4): an uncoupled tube inner/outer diameter, a silently-shadowing registry, fragile NaN handling, and one inaccurate docstring.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 2
- Nit: 2

## Findings

### TPL-001 Minor: tube `id`/`od` are independent ranges — a live-slider POST can yield `id ≥ od` → degenerate, non-watertight geometry
**Dimension:** Correctness
**Evidence:** `templates.py` tube family: `od` range [4,200], `id` range [1,190], no coupling. `clamp_values(tube, {"od":4,"id":190})` → `{od:4, id:190}` (verified) → emits `tube(od=4, id=190, height=12)`. `library/containers.scad` `tube()` does `difference(cylinder(od), cylinder(id))`; with `id ≥ od` the bore swallows the wall → empty/inverted, non-manifold mesh. `derive_values` defaults are safe (16/8); the exposure is the future live-slider POST that `clamp_values` exists to guard.
**Why it matters:** A user dragging the tube sliders into `id ≥ od` gets a broken render. It fails *closed* (the gate's `mesh.not_watertight` is a FAIL code, so it can't be sliced/sent), so it's not a safety hole — but it's a confusing dead-end on the very interaction Stage 5 is built for.
**Fix path:** Add a declarative per-family ordering constraint (e.g. `gaps: tuple[(small, large, gap)]`) applied after independent clamping in both `derive_values` and `clamp_values`; tube declares `("id","od",1.0)` so `id ≤ od − 1`. Add a test that `clamp_values(tube, {od:4,id:190})` yields `id < od` and renders watertight.

### TPL-002 Minor: `TemplateRegistry` builds its alias index with last-write-wins — a duplicate alias across families is silently shadowed
**Dimension:** Correctness
**Evidence:** `templates.py` `TemplateRegistry.__init__` does `index[_normalize(alias)] = fam` with no duplicate check. Today there are 35 aliases and zero collisions (verified), so nothing is broken now — but the benchmark slice will add families, and a reused alias (e.g. another family claiming "container") would silently override an earlier family with no error.
**Why it matters:** A silent shadow is a latent correctness bug that surfaces as "the wrong template matched" with no signal — exactly the kind of thing that's invisible in a diff and bites weeks later when families grow.
**Fix path:** Raise `ValueError` on a duplicate normalized alias in the constructor; add a test asserting the built-in registry has no collisions (and that a hand-built colliding registry raises).

### TPL-003 Nit: `clamp_values` coerces NaN/inf to a bound via fragile CPython `min`/`max` semantics
**Dimension:** Correctness
**Evidence:** `clamp_values` does `float(raw)` then `_clamp`. `float("inf")`→250 and `float("nan")`→250 (verified) — the NaN case "works" only because `min`/`max` with NaN returns the non-NaN operand by argument order, which is unspecified/fragile. A future refactor of `_clamp` could let a NaN slip into `emit_scad`.
**Why it matters:** Low exposure (values come from a validated plan or a clamped POST), but a NaN reaching `_fmt` would emit `nan` into OpenSCAD. Cheap to make explicit.
**Fix path:** In the coercion, reject non-finite input explicitly: `if not math.isfinite(num): num = default` (in `clamp_values`, and guard `derive_values` likewise).

### TPL-004 Nit: `_singular` docstring claims "boxes→boxe is handled by the box alias list" — it isn't; `"boxes"` matches nothing
**Dimension:** Docs
**Evidence:** `templates.py` `_singular` docstring asserts `boxes` is covered; `match(plan("boxes"))` returns `None` (verified) because `_singular("boxes")="boxe"` and `"boxe"` isn't an alias. The `-s` stripper genuinely can't do `-es` plurals without breaking `cases→cas`.
**Why it matters:** Trivial — an inaccurate comment, plus a tiny alias-coverage gap on an uncommon plural (the planner emits singular `object_type` ~always).
**Fix path:** Correct the docstring to state honestly that only simple `-s` plurals are stripped and `-es` plurals rely on explicit alias entries; optionally add `"boxes"` to the snap_box alias list if worth it.

## What's working
- **Determinism is real and the honesty invariant is enforced, not asserted.** `emit_scad` is pure string substitution; the binary-gated `test_family_renders_watertight_with_its_declared_bbox` renders all 7 families against the real OpenSCAD binary and checks the measured envelope equals `expected_bbox` to 0.01 mm — so a drift between a family's declared bbox and its module fails loudly (the same bar `tests/test_library_modules.py` set).
- **No injection surface.** Only clamped floats reach `emit_scad`, formatted by `_fmt` into bare numeric literals; `object_type` is used only for matching and is never emitted; `library_file`/`module` are trusted family constants. A hostile prompt can't shape the SCAD beyond a number in range.
- **Built on proven geometry.** Defaults and bbox formulas are pinned to the values already verified by real renders in `test_library_modules.py` (`snap_box [80,60,40]`, `wall_hook [25,39,60]`, `cable_clip [20,25,9]`, `enclosure [85,55,35]`, `tube [16,16,12]`), so the engine inherits that ground truth.
- **Tests bite.** `test_emit_is_deterministic` pins the exact string; clamp/derive tests assert real clamping (250/10/8) not just "a number"; the match tests cover aliases, normalization, plurals, and the None path. No tautologies spotted.

## Watch items
- Inter-parameter constraints will recur as families grow (e.g. wall < min(width,depth)/2 for boxes). The `gaps` mechanism added for TPL-001 should be the general home for these rather than per-family special cases.

## Escalation recommendation
No escalation needed. Single new module, scoped change, all findings Minor/Nit with concrete fixes. audit-team is not warranted for this slice.

---

## Re-audit (resolution) — 0/0/0/0/0

All four findings fixed in `templates.py`/`test_templates.py` and re-verified empirically:

- **TPL-001 (Minor) — FIXED.** Added a declarative `gaps: (small, large, gap)` ordering constraint applied after clamping in both `derive_values` and `clamp_values`; tube declares `("id","od",1.0)`. Verified: `clamp_values(tube, {od:4, id:190})` → `id=3 < od=4`. Tests `test_tube_gap_keeps_bore_inside_the_outer_wall`, `test_derive_honors_gap_constraint`.
- **TPL-002 (Minor) — FIXED.** `TemplateRegistry.__init__` now raises `ValueError` on a duplicate normalized alias. Verified raises; the 7 built-ins construct clean (36 aliases, 0 collisions). Tests `test_registry_rejects_duplicate_alias`, `test_builtin_registry_constructs_without_alias_collision`.
- **TPL-003 (Nit) — FIXED.** New `_coerce_finite()` drops NaN/inf (and non-numeric) to the parameter default; used by both `derive_values` and `clamp_values`. Verified: `inf`/`nan` → 80 (default), not a bound. Test `test_clamp_values_drops_non_finite_to_default`.
- **TPL-004 (Nit) — FIXED.** `_singular` docstring corrected to state only `-s` plurals are stripped (`-es` rely on aliases); `"boxes"` added to the snap_box alias list. Verified `match("boxes")` → `snap_box`. Test `test_match_handles_es_plural_via_explicit_alias`.

No regressions: emit still produces only clamped numeric literals (`snap_box(width=50, depth=60, height=40, wall=2)`), the 7 binary-gated renders still pass. `ruff` clean; `pytest tests/test_templates.py` = **50 passed** (incl. 7 live renders). **Roll-up: 0/0/0/0/0.**
