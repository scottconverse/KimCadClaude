# Stage 5 Remediation Re-Audit — Principal Engineer

Date: 2026-06-02
Scope: uncommitted remediation on branch `stage-5-template-engine` (`git diff -- src tests`).
Posture: balanced. Gate bar: 0 Blocker / 0 Critical / 0 Major / 0 Minor / 0 Nit.
Method: read the changed code (not just the notes), proved behavior preservation, ran ruff + targeted pytest.

## Closure verification (first-pass findings)

### ENG-501 — wall_hook bbox drift at plate_h min — CLOSED
`templates.py:400` raised `plate_h` min 20→24. Verified against `library/hooks.scad:23,29-30`:
lip top Z = `max(2,(plate_h-arm_rise)/2)+arm_rise`, arm_rise=20. For plate_h in [20,22) the floor
`max(2,…)` pins arm_z0=2 → lip top 22 > plate_h → analytic `bbox_z=plate_h` under-reports (gate
fails-closed). At plate_h>=24 the floor is no longer binding (`(24-20)/2=2`), lip top 22 < 24 = plate
top, so `bbox_z=plate_h` is exact across the whole [24,200] range. Math is correct; the in-code
comment matches the SCAD. New test `test_wall_hook_bbox_is_exact_at_the_plate_height_minimum`
clamps to the actual min, asserts the slider is at min, renders via the real OpenSCAD binary, and
checks the rendered envelope == declared. Ran it: PASSED (not skipped — binary present).

### ENG-502 — version_counter read outside lock — CLOSED
`webapp.py:841` `next(version_counter)` now sits inside the `with lock:` block (826-841). Confirmed.

### ENG-503 — render_lock global, undocumented — CLOSED
`webapp.py:305-308` comment documents the single-user/loopback decision and the "key by rid if a
multi-client mode lands" upgrade path. Accurate; no behavior change (the lock object is unchanged).

### ENG-504 — _singular fragility — CLOSED
`test_singular_stripping_never_collides_across_families` builds `_normalize(alias)->family` over the
REAL `default_registry()`, then asserts no alias singularizes onto a different family's alias. It
exercises cross-family collisions over the live registry as claimed.

### ENG-505 — derive/clamp duplication → `_finalize` — CLOSED, BEHAVIOR-PRESERVING
Highest-risk change. `_finalize(family, raw)` = per-param `_clamp(_coerce_finite(raw.get(name,
default), default), min, max)` + `_apply_gaps`, shared by both entry points. Proved equivalence:
- `clamp_values` body is now literally the old loop verbatim → identical.
- `derive_values` now skips `raw[name]` when `value is None`; `_finalize`'s `raw.get(name, default)`
  reproduces the old explicit `p.default`, and defaults are always finite → identical for both the
  None and not-None branches.
Ran a direct equivalence harness: dim_keys still beats bbox_axis (width=55 over bboxX=10), bbox_axis
fallback intact, default fallback intact, unknown keys dropped, NaN→default, gap honored (id<=od-1),
all outputs finite, and `clamp(derive(x))==derive(x)` (finalize-stable). Injection-safety invariant
(only finite clamped numbers reach `emit_scad`) holds in every path.

### ENG-506 — DemoProvider.generate_openscad dead path — CLOSED
`webapp.py:158-162` comment explains it is shadowed by the template tier in demo mode and kept as the
LLM-codegen contract shape (exercised via FakeProvider). Documentation-only; accurate.

### ENG-507 — _perturb first-param assumption — CLOSED
`template_bench.py` `_perturb` docstring now states the "params[0] is a geometry-affecting linear
dim" assumption, why it holds for all seven built-ins, and the remedy if a cosmetic first param ever
lands. Documentation-only; accurate.

## Delta review for NEW issues

- `_finalize` refactor: no edge behavior changed (proved above). No new issue.
- 404-split (`known = rid in registry`, webapp.py:798): read under the same `with lock:` snapshot as
  `state`; only selects between two 404 *messages* (both 404). Worst case under eviction is a slightly
  mismatched-but-still-404 message — no correctness/security consequence. No race of consequence.
- Slicer signed-exit conversion (`slicer.py`): small code (2) → unchanged; unsigned 4294967246 → -50;
  `None` short-circuits via `returncode is not None` so the `> 2**31` compare never TypeErrors and the
  message reads "exited None". `GcodeProofFailed` sets returncode=None but calls `SliceError.__init__`
  directly, bypassing this branch — so the None guard is defensive only. Empty stderr → plain-English
  hint, no dangling colon. Correct.
- `axis` added to `TemplateMatch.parameters()` (templates.py:187-188): purely additive optional key;
  consumed at webapp.py:114 and JSON-serialized; non-dimensional params (wall) carry no axis. No
  consumer breaks; new test pins the shape.

## Load-bearing safety invariants — re-confirmed after the diff

1. Injection-safe emit — HOLDS (only finite clamped numbers reach `emit_scad`; proved across paths).
2. No-model re-render — HOLDS (`emit_scad` is pure string substitution; demo path now template-shadowed).
3. Gate-fail re-render drops the slice — HOLDS (webapp.py:833-835 pop gcode + slice_cache;
   `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` proves slice+send both refuse).
4. Render serialization — HOLDS (`render_lock`; `test_concurrent_rerenders_are_serialized` now also
   asserts a jitter-free `max inside == 1` invariant).
5. Send-gate — HOLDS (same test confirms a gate-failed re-render is non-sendable).

## Verification run

- `ruff check` on all 8 changed files: All checks passed.
- `pytest` on the 4 changed test files: 153 passed.
- 4 key new tests run verbosely: all PASSED, none skipped (wall_hook render is real).

## Rollup

0 Blocker / 0 Critical / 0 Major / 0 Minor / 0 Nit. Every first-pass finding is genuinely closed; the
remediation introduced no new issue and all five safety invariants still hold. Gate met: **0/0/0/0/0.**

Not independently re-verified: the full 489-suite (taken as given per the brief; the targeted 153 +
binary-gated render were run here).
