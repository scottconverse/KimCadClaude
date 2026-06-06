# Stage 5 Engine — Principal Engineer Deep-Dive (backfill 2026-06-05)

Auditor role: Principal Engineer (independent, skeptical). Audit-only — no code changed.
Branch: `stage-0-7-audit-backfill`. Scope: the deterministic template engine and the
live-slider re-render path — `src/kimcad/templates.py`, `src/kimcad/pipeline.py::rerender`
and its build/assemble tail, and `src/kimcad/webapp.py`'s `/api/render/<id>` handler with
its lock/version/slice-invalidation invariants. Read for call-site correctness: `ir.py`,
`printability.py`, `openscad_runner.py`, the four library `.scad` modules the families use,
and the Stage-5 tests.

Method: traced every parameter from a live-slider POST through `clamp_values` → `emit_scad`
→ the real OpenSCAD module → the gate, and verified the analytic bounding boxes against the
actual module geometry. Where a claim was checkable against the real binary
(`tools/openscad/openscad.exe` is present), I rendered and gated it rather than reasoning
alone.

---

## Severity counts

- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 3
- Nit: 2
- Total: 6

---

## What's working (specific, earned)

- **The "no model call" invariant is real and proven, not asserted.** `_build_from_template`
  (pipeline.py:813) emits a pure string and renders once; `rerender` (pipeline.py:647) rebuilds
  the match from family + clamped values with no provider call. `test_pipeline_templates.py`
  pins `provider.openscad_calls == 0` on every template path including gate-fail and
  proceed_anyway. This is the load-bearing claim of Stage 5 and it holds.
- **The re-shape safety invariant is genuinely airtight.** The OLD shape being made
  non-sliceable/non-sendable after a re-render is enforced three ways that reinforce each
  other: `/api/render` pops `gcode_registry` + the rid's `slice_cache` entries AND bumps
  `geometry_version` under `lock` (webapp.py:1834-1839); a slice in flight captures
  `sliced_ver` and refuses to register if the version moved (`_respond_slice`, :1685); and
  the cache-write re-checks the version under `lock` (:1758). The same-rid slice/render race
  is closed, and it's tested (`test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale`,
  `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send`).
- **Input hardening on the slider path is thorough.** `_coerce_finite` (templates.py:53)
  drops NaN/inf/non-numeric to the family default *before* clamping, so neither a hostile API
  POST nor an inf that slipped through a plan can reach `emit_scad`. `_finalize` back-fills
  missing keys, drops unknown keys, and clamps — a complete, in-range value set is guaranteed.
  Tested directly (`test_clamp_values_drops_non_finite_to_default`).
- **The `use <library/...>` path resolves correctly and safely.** emit writes a relative
  `use <library/FILE>;`; `openscad_runner` sets `OPENSCADPATH=PROJECT_ROOT` (:229-233) so it
  resolves while cwd stays the isolated temp dir, and `sanitize_scad` only lets
  `library/`-prefixed, traversal-free `use`/`include` survive. No injection surface here.
- **Determinism of matching.** The registry indexes normalized aliases at construction and
  raises on a duplicate (templates.py:266) rather than silently shadowing; `_singular` is
  deliberately conservative and there's a test proving no built-in alias singularizes onto a
  different family (`test_singular_stripping_never_collides_across_families`).
- **The wall_hook `plate_h` min=24 fix is correctly reasoned and verified.** I re-derived the
  module's Z-top (`max(plate_h, arm_z0+arm_rise)` with `arm_z0=max(2,(plate_h-arm_rise)/2)`,
  arm_rise=20): at plate_h=24 the arm top is exactly 24, so the linear `bbox_z=plate_h` stays
  exact across the whole slider range. The comment (templates.py:395-399) is accurate and
  `test_wall_hook_bbox_is_exact_at_the_plate_height_minimum` guards the boundary.
- **Atomic mesh export.** `_assemble_result` writes `*.stl.tmp` then `os.replace` (:496-498),
  so a concurrent viewport/slicer/save reader never sees a half-written STL during a re-render.

---

## Findings

### ENG-501 (Major | Correctness/Determinism): wall slider can collapse `snap_box`/`box` to a silently-solid block that still passes the gate

**Evidence.** `snap_box(width, depth, height, wall)` (library/containers.scad:16) builds its
cavity as `cube([width-2*wall, depth-2*wall, height-2*wall])`. The `box_like_params`
(templates.py:308-316) and the `box` family (:338-345) give width/depth/height `min=10` and
`wall` `min=0.8, max=8.0` with **no ordering constraint** linking wall to the linear
dimensions. Only `tube` declares a `gaps` constraint (:384); the `gaps` mechanism exists
precisely for this ("independent slider ranges can't produce degenerate geometry",
comment :131-134) but is not applied to snap_box or box.

I reproduced it against the real binary. `clamp_values(snap_box, {width:14, depth:14,
height:14, wall:8})` yields a -2 mm interior and emits `snap_box(width=14, ..., wall=8)`.
Rendered result: **watertight, bbox 14×14×14, volume 2744 mm³ = 14³ = a solid cube** (the
negative-interior `cube()` is treated as empty, so the `difference()` subtracts nothing).
The gate returns **PASS on every check**, including `wall.ok "Wall 8.0 mm is adequate."`

**Why this matters.** A "tray"/"bin"/"box" is, by definition, hollow. A user who designs one
and drags the wall thick (entirely within the slider's own range — width 10-40 with wall 8 is
common for a small part) silently gets a solid block: wrong part, far more filament and print
time, and the readiness card says "Ready to print." The gate can't catch it because the bbox
is unchanged and "wall adequate" reads the declared number, not the realized geometry. This is
a reachable, normal-operation correctness + determinism failure on the headline Stage-5 path.
It is Major, not Critical, because there is no data/security impact and the workaround (don't
push wall past dimension/2) is obvious *once you know* — but nothing tells the user.

**Blast radius.**
- Adjacent code: the same vulnerability exists for any family whose module subtracts `2*wall`
  from a slider dimension without a guard — `snap_box` and `box`. `enclosure` is **safe** by
  construction (its inner snap_box interior is `inner_w >= 10`), and `drawer_divider` is safe
  (panel_t fixed at 2, length min 10 → interior 6); I verified both, so the fix is scoped to two
  families.
- Shared state: the `gaps` engine (`_apply_gaps`, templates.py:202) already implements exactly
  the needed enforcement — this is a missing *declaration*, not missing machinery.
- User-facing: tray/bin/box live-slider drags near the wall max; the report flips from a wrong
  "pass" to either a correct hollow part or an honest clamp signal.
- Migration: none. Adding a gap only lowers an out-of-range slider value at clamp time; in-range
  designs are unaffected.
- Tests to update: add a clamp test (wall can't exceed dimension/2 − margin) and a binary-gated
  render test asserting the cavity volume is < the solid-cube volume. No existing assertion
  breaks.
- Related findings: ENG-502 (the gate has no "is this actually hollow" check) is the same root
  seen from the gate side.

**Fix path.** Two complementary options; recommend doing both.
1. Declare gaps so the smallest linear dimension stays above `2*wall + ε`. The current `gaps`
   tuple is `(small, large, gap)` enforcing `small <= large - gap` by lowering `small`. To cap
   `wall` against width/depth/height you'd add `("wall", "width", w), ("wall","depth",w),
   ("wall","height",w)` with `gap ≈ width_min` — but note `_apply_gaps` lowers the *first*
   element, which is `wall` here, so the semantics line up (wall is lowered to fit). Verify the
   ceiling math handles three constraints on one param (it iterates, so the tightest wins).
2. Add a cheap geometry sanity check to the gate or to `_build_from_template`: if the realized
   mesh volume equals the solid-bbox volume for a family declared hollow, FAIL with a clear
   "walls too thick — the part came out solid" finding. This catches the class even if a future
   family forgets the gap.

---

### ENG-502 (Minor | Correctness): gate trusts the declared `wall` number, never the realized wall

**Evidence.** `_check_wall_thickness` (printability.py:191) reads `plan.dimensions[wall]` and
compares it to the material minimum. On the template path the plan's `dimensions` are
overwritten with `match.values` (pipeline.py:425, rerender :679), so the gate checks the
*requested* wall, not what the module actually produced. In the ENG-501 repro the wall is
reported "adequate (8.0 mm)" for a part that has no walls at all.

**Why this matters.** The wall check is advisory and reads correctly in the normal case, so on
its own this is Minor — but it's the gate-side blind spot that lets ENG-501 pass. Worth a note
so the fix for ENG-501 doesn't stop at the emit side and leave the gate still lying.

**Fix path.** Covered by ENG-501 option 2 (volume/realized-geometry check). No separate change
needed if ENG-501 is fixed with a geometry check; otherwise document that the wall finding is
intent-only.

---

### ENG-503 (Minor | Performance/Architecture): a single global `render_lock` serializes re-renders across *all* designs

**Evidence.** `render_lock` (webapp.py:669) is one process-wide lock; every `/api/render`
holds it for the full `pipeline.rerender` (:1798), which renders via the OpenSCAD subprocess.
The code comments this as intentional for the single-user/loopback case and tags the multi-client
upgrade as ENG-503.

**Why this matters.** Correct and safe for the shipped single-user app, so Minor. But two
different designs being dragged at once (two browser tabs) would serialize their sub-second
renders into a visible stutter. The comment already names the fix (key the lock by rid), so this
is a logged watch-item, not a defect.

**Blast radius.** Adjacent: `slice_lock` has the same global-vs-per-rid shape and the same
note. If a multi-client mode lands, fix both together. Migration: none. Tests:
`test_concurrent_rerenders_are_serialized` asserts the *current* serialize-everything behavior
and would need to become per-rid.

---

### ENG-504 (Minor | Correctness): `_axis` bbox sum returns `0.0` for an empty term tuple, silently mis-declaring a forgotten axis

**Evidence.** `_axis` (templates.py:143) is `sum(...)` over the terms; a family that omits
`bbox_y` (default `()`) gets `expected_bbox()[1] == 0.0` rather than an error. Every built-in
declares all three axes, so this is latent — but a future family that forgets one axis would
declare a 0-mm envelope, and the dim gate would then FAIL every render of it with a confusing
"Y is N mm but spec asked for 0.0 mm" instead of flagging the authoring mistake.

**Why this matters.** No current part is affected (Minor), but it's a sharp edge for the next
person adding a family — the failure surfaces far from the cause.

**Fix path.** In `TemplateFamily` validation (or a registry self-check at construction, next to
the duplicate-alias guard), assert each of `bbox_x/y/z` is non-empty. Cheap, runs once at
import, and turns a silent 0 into a loud authoring error — mirroring the existing
fail-loud-at-construction philosophy.

---

### ENG-505 (Nit | Hygiene): `drawer_divider` cross-walls can overlap when `compartments` is high and `length` is low

**Evidence.** library/organizers.scad:20 spaces cross walls at `i*length/compartments`. With
length=10 (min) and compartments=12 (max), spacing is 0.83 mm < panel_t (2 mm), so walls merge.
The result stays watertight and the bbox is unchanged, so the gate is fine and the part is
printable — just not 12 distinct compartments.

**Why this matters.** Cosmetic/intent drift at an extreme slider corner; no incorrect "pass"
because the envelope is right and it's still a valid solid. Nit.

**Fix path.** Optionally add a `compartments`-vs-`length` gap, or clamp `compartments` to
`floor(length / (panel_t + min_cell))`. Low priority.

---

### ENG-506 (Nit | Hygiene): `_fmt` integer path can emit `-0` and uses `int(round())` (banker's rounding) inconsistently with the float path

**Evidence.** `_fmt` (templates.py:38) integer branch is `str(int(round(value)))`; the float
branch rounds to 3 then formats with `:g`. The two rounding modes differ at .5 boundaries
(`round` is banker's, the float path's `:g` is not the issue but the pre-round is). All current
integer params (`compartments`) are derived from already-integer inputs and clamped to a
positive range, so neither `-0` nor a .5 tie is reachable today. Pure consistency nit.

**Fix path.** None required. If touched, use `int(round())` consistently or document the intent.

---

## What I could not check

- **No live, full-suite run in this pass.** I rendered targeted cases against the real binary
  (the ENG-501 repro and the bbox claims) but did not run the entire pytest suite or the
  binary-gated `test_family_renders_watertight_with_its_declared_bbox` across all families. The
  ENG-501 finding is confirmed by direct render; the rest of the bbox formulas I verified by
  re-deriving them against the module source and the offline `test_expected_bbox_matches_module_formulas`
  assertions, not by rendering all seven.
- **PrintProof3D / readiness on the rerender path** was read for call-site correctness
  (`run_engine=False` is correctly threaded so a drag stays gate-only) but not exercised, as it
  is out of the Stage-5 engine scope and gated on an external engine binary.
