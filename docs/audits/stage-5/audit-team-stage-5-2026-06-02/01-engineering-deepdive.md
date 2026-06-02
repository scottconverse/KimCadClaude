# Engineering Deep-Dive — KimCad Stage 5 (Deterministic Template Engine)

**Audit date:** 2026-06-02
**Role:** Principal Engineer
**Scope audited:** The complete Stage 5 branch diff `main...stage-5-template-engine` (HEAD `91b691c`), excluding `docs/design` and the completion directive. Source focus: `src/kimcad/templates.py`, `src/kimcad/pipeline.py` (tiering, `rerender`, `_build_from_template`, `_assemble_result`), `src/kimcad/webapp.py` (`/api/render`, `template_state`, `render_lock`, `version_counter`, eviction), `src/kimcad/template_bench.py`, `src/kimcad/mcp_server.py` (send-gate boundary). Minified `web/assets/*` bundles ignored per scope.
**Auditor posture:** Balanced

---

## TL;DR

Stage 5 is a clean, well-reasoned addition. The deterministic template engine is exactly the right architecture for "drag a slider, watch it change" — pure-data families drive codegen, bbox prediction, and the slider UI from one definition, and the injection trust boundary (coerce → clamp → format, all numeric) is correctly placed and airtight: I could not find any path that lands a non-numeric, unclamped, or attacker-influenced value in the emitted OpenSCAD. The five load-bearing invariants all hold — re-render is structurally model-free, a gate-FAILED re-render drops the cached slice/G-code, concurrent re-renders serialize on `render_lock`, and the send-gate boundary is documented and unweakened. The one real defect I found is a benign analytic-bbox drift in the `wall_hook` family at the very bottom of its plate-height slider; it is caught fail-closed by the gate, so it is a UX dead-zone, not a safety hole. Architectural debt is low; test coverage on the new surface is strong (484 suite green; the 73 Stage-5-specific tests pass). Security posture: solid.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 4 |

## What's working

- **Injection trust boundary is correct and verified end-to-end.** Every path into `emit_scad` (`derive_values`, `clamp_values`, `match`, `match_family`, `rerender`) routes values through `_coerce_finite` (non-numeric/NaN/inf → default) then `_clamp` (into the typed range) then `_fmt`. I exercised `_coerce_finite` with a SCAD-injection string (`'80; cube(999)'`), `nan`, `inf`, `None`, lists, dicts, and `'1e9'`: all hostile inputs fall back to the numeric default or clamp into range, and `_fmt` never emits scientific notation, `inf`, or `nan` within the clamp bounds (`templates.py:38-61, 191-242`). `fixed_args` are family-defined float constants. The emitted SCAD is provably `module(name=<finite number>, ...)`.
- **Re-render is structurally model-free.** `Pipeline.rerender` → `_build_from_template` never references `self.provider`; the only provider touch in the file is in `_build_geometry`'s LLM branch, which `_build_from_template` does not enter (`pipeline.py:426-488, 581-617`). `template_bench._NoModelProvider` makes "no model" a *runtime* assertion too — any accidental call raises. Verified.
- **The deterministic path fails closed, no retry.** `_build_from_template` has no feedback loop: a render/blocked error is surfaced directly (no LLM fallback — "a proven library module shouldn't fail to render"), and a gate FAIL is returned as-is. I confirmed against a real render that `wall_hook` at `plate_h=20` returns `gate=fail` and is not retried (`pipeline.py:606-617`).
- **Gate-FAILED re-render drops the stale slice/G-code.** `_handle_render` pops `gcode_registry[rid]` and every `slice_cache` entry for the id under `lock` whenever the geometry changes, and re-stamps `gate_status_by_rid` from the fresh report (`webapp.py:817-822`). The integration test `test_rerender_invalidates_a_cached_slice` proves a re-shape forces a re-slice. A stale passing slice cannot survive a re-shape.
- **Analytic bbox formulas match the library modules.** I cross-checked each family's `bbox_*` terms against the documented + actual module geometry: `wall_hook = [plate_w, plate_t+arm_proj, plate_h]`, `cable_clip = [width, cable_d+5*wall+screw_d, cable_d/2+2*wall]`, `enclosure = [inner+2*wall]³`, `tube = [od, od, height]`, `drawer_divider = [length, depth, height]`. All correct against `library/*.scad`. Module parameter names exactly match `ParamSpec.name`/`fixed_args` keys, so `emit_scad` produces valid calls.
- **The tube ordering constraint is robustly bounded.** `id` min (1.0) + gap (1.0) = 2.0 ≤ `od` min (4.0), so `_apply_gaps` can always lower `id` to satisfy `id ≤ od - 1`; the docstring's "floor" edge case cannot actually trigger. I verified at the extremes (`od=4,id=200` → `id=3`).
- **Duplicate-alias guard fails loudly at construction.** `TemplateRegistry.__init__` raises on a duplicate normalized alias rather than silently shadowing (`templates.py:251-261`), so a family that would never match is caught at import, not in production.
- **Concurrency discipline mirrors the proven slice path.** `render_lock` serializes the geometry write to the fixed per-design output dir; registry/cache mutations run under `lock`; LRU `move_to_end`/`popitem` and eviction all run under `lock`. The `test_concurrent_rerenders_are_serialized` test asserts non-overlap with a deliberately slow renderer.
- **Send-gate boundary is documented and unweakened.** `mcp_server.send_print` still gates on `confirm is True` (identity, no `bool()` coercion) + a proven motion-bearing slice, and the new comment honestly documents that it does *not* re-check the printability gate (the design flows do). Stage 5 did not touch the web/CLI gate-fail refusals.

## What couldn't be assessed

All items in scope were accessible and exercised. I ran `ruff check src tests` (clean), `pytest` on `test_templates.py`/`test_pipeline_templates.py`/`test_template_bench.py` (73 passed), and live OpenSCAD renders of the `wall_hook` family to confirm the bbox-drift finding empirically. Real-hardware printing and the live LLM are deliberately out of altitude per the audit charter and were not assessed. I did not re-run the full 484 suite (already green per the directive); I spot-ran the Stage-5 surface.

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

### [ENG-501] — Minor — Correctness — `wall_hook` analytic bbox under-reports Z by 2 mm at the plate-height slider minimum

**Evidence**
`templates.py:375-393` declares `wall_hook` `bbox_z = (BBoxTerm(ref="plate_h"),)`, i.e. the analytic Z envelope is exactly `plate_h`. But the module `library/hooks.scad:17-37` seats the arm at `arm_z0 = max(2, (plate_h - arm_rise) / 2)` and the up-turned lip rises `arm_rise` from there, so the true Z top is `max(2, (plate_h-20)/2) + 20`. With `arm_rise` fixed at 20 and `plate_h` min = 20, at `plate_h=20` the floor clamps `arm_z0` to 2 and the lip top reaches 22 mm. I rendered it:

```
plate_h=20: expected_bbox_z=20.0  actual_z=22.0  (Δ +2.0, tol 0.5)  gate=FAIL
plate_h=22: expected_bbox_z=22.0  actual_z=22.0  gate=pass
plate_h>=22: exact
```

The drift exists only at the exact slider minimum (`plate_h=20`); for `plate_h ≥ 22` the analytic and actual envelopes agree.

**Why this matters**
A user who drags the plate-height slider to its minimum gets a part that *always* fails the printability gate (`dim.mismatch`) and therefore can't be sliced or sent — a confusing dead-zone at one end of one slider, with a "your part is the wrong size" message that doesn't correspond to anything the user did wrong. It is **not** a safety bug: the gate is the backstop and it holds — a wrong-sized part never silently passes, never gets sliced, never gets sent. The blast is purely UX/correctness-of-prediction.

**Blast radius**
- Adjacent code: only `wall_hook`. I swept the other six families' extremes; none showed analytic-vs-actual drift (the box-like families are exact, `tube` bbox ignores `id`, `cable_clip`/`enclosure`/`drawer_divider` are linear in their params). This is specific to the `max(2, …)` floor in `hooks.scad`, not a systemic pattern.
- Shared state: none. `expected_bbox` is consumed by the gate target alignment in `run`/`rerender` and by the report/viewport; all three would show the corrected envelope after a fix.
- User-facing: the wall-hook slider's bottom 1–2 mm of plate-height range becomes usable again.
- Migration: none.
- Tests to update: add a `wall_hook` `plate_h=min` case to `test_templates.py`/`test_pipeline_templates.py` asserting analytic == actual (currently the families are tested at defaults, which sit in the exact region).
- Related findings: none.

**Fix path**
Two clean options. (a) Raise `plate_h` min to 24 in the `ParamSpec` so the floored region is never reachable (cheapest, no geometry change). (b) Make the analytic term honest: `bbox_z = max(plate_h, max(2,(plate_h-arm_rise)/2)+arm_rise)`. Since `BBoxTerm` is a linear sum and can't express the `max`/floor, (b) needs either a small per-family override hook or pinning `arm_rise` into the bbox. Recommend (a) — it matches how the family is intended to be used (a 20 mm-tall wall hook with a 20 mm rise is degenerate anyway) and keeps `expected_bbox` purely linear.

### [ENG-502] — Minor — Hygiene — `version_counter` is read outside `lock` (relies on `itertools.count` atomicity)

**Evidence**
`webapp.py:826`: `payload["mesh_url"] = f"/api/mesh/{rid}?v={next(version_counter)}"` runs *after* the `with lock:` block closes at line 824. Every other shared-counter read in this file (`next(counter)` at line 687) is taken under `lock`.

**Why this matters**
`itertools.count.__next__` is a single atomic bytecode under CPython's GIL, so in practice there is no race and no duplicate/skipped version. But the inconsistency with the `counter` pattern invites a future maintainer to "fix" one and not the other, or to swap the counter for a non-atomic source. The cache-buster only needs uniqueness, which atomicity already gives — so this is hygiene, not a live bug.

**Fix path**
Move the `next(version_counter)` inside the `with lock:` block (it's already the right scope), or add a one-line comment at the call site noting the deliberate reliance on `itertools.count` atomicity. Recommend the comment — moving it under the lock is harmless but unnecessary.

### [ENG-503] — Minor — Architecture — `render_lock` is process-global, serializing re-renders across *all* designs

**Evidence**
`webapp.py:302` defines a single `render_lock = threading.Lock()`; `_handle_render` holds it around `pipeline.rerender` for any id (`webapp.py:806-807`). Two users (or two browser tabs) dragging sliders on *different* designs serialize against each other even though they write to different per-design output dirs.

**Why this matters**
The local web UI is single-user by design (127.0.0.1, one operator), so under the real workload this is invisible — re-renders are sub-second and contention is nil. It becomes a throughput ceiling only if KimCad ever grows a multi-client or shared-server mode. Flagging it now because the slice path made the same choice (`slice_lock`) where the cost is much higher (multi-minute slices), and there the global lock is load-bearing for protecting the box; for re-render the global scope is broader than the invariant requires (which is per-design-dir mutual exclusion).

**Blast radius**
- Adjacent code: `slice_lock` shares the pattern; a per-key refactor would naturally cover both.
- User-facing: none today (single user). Future multi-client mode only.
- Migration: none.
- Tests to update: `test_concurrent_rerenders_are_serialized` asserts serialization *for the same id*, which a per-id lock still satisfies.

**Fix path**
If/when multi-client matters, key the lock by `rid` (a `defaultdict(threading.Lock)` guarded by `lock`, or a small per-rid lock registry evicted alongside `_evict`). Not worth doing for the single-user tool today — recommend leaving a `# single global lock: fine for the single-user local UI` note and revisiting with any networked-server work.

### [ENG-504] — Nit — Hygiene — `_singular` plural-stripping is documented as conservative but silently misfires on a few aliases

**Evidence**
`templates.py:71-77` strips a trailing `s` on words > 3 chars. `match` tries the exact alias then `_singular(norm)`. For an `object_type` the registry doesn't list explicitly, e.g. `"rings"` → `"ring"` (matches `tube`, good), but `"cases"` → `"case"` (matches `snap_box`, good) only because `case` is an explicit alias. The docstring already calls this out and says `-es` plurals are covered by explicit aliases. No incorrect match is reachable with the current alias lists — I checked each family's aliases against the stripper.

**Why this matters**
It's correct today but fragile: adding a family whose alias ends in `s` (e.g. `"truss"` → stripped to `"trus"`) could create a silent miss. Pure forward-looking hygiene.

**Fix path**
Leave as-is (the docstring is honest and the alias lists carry the real coverage), or add a tiny test that asserts `_singular` over the full alias set produces no cross-family collision. Recommend the test as cheap insurance.

### [ENG-505] — Nit — Hygiene — `derive_values` and `clamp_values` duplicate the coerce/clamp/gaps tail

**Evidence**
`templates.py:215-242`: `derive_values` and `clamp_values` differ only in how the *raw* value is sourced (plan dimension/bbox vs. external dict), then both do `_clamp(_coerce_finite(...))` per param and `return _apply_gaps(...)`. The shared tail is small but identical.

**Why this matters**
Minor duplication; if the clamp policy ever changes (e.g. a new "snap to step" rule) it must be edited in two places. Not worth a refactor on its own.

**Fix path**
Optional: extract a `_finalize(family, raw: dict) -> dict` that does coerce+clamp+gaps and have both call it. Low priority.

### [ENG-506] — Nit — Hygiene — `DemoProvider.generate_openscad` hardcodes a `snap_box` call that the template tier now bypasses

**Evidence**
`webapp.py:157-158`: `DemoProvider.generate_openscad` returns a fixed `snap_box(...)` string. But `DemoProvider.generate_design_plan` returns `object_type="box"`, which the registry now matches to the `snap_box` family, so the deterministic tier builds the geometry and `generate_openscad` is never reached in demo mode.

**Why this matters**
It's dead in the demo path now (the template tier shadows it). Harmless, but a reader debugging demo mode may waste time on a method that no longer runs. It still serves as documentation of the LLM contract shape.

**Fix path**
Leave it (it documents the provider interface and is exercised by the LLM-path tests via `FakeProvider`), or add a one-line comment that the template tier shadows it in demo mode. Recommend the comment.

### [ENG-507] — Nit — Hygiene — `template_bench` `_perturb` assumes `family.params[0]` is a good perturbation target

**Evidence**
`template_bench.py:178-184`: `_perturb` nudges `family.params[0]` by one `step`. For every current family `params[0]` is a linear dimension that changes geometry, so the benchmark's "not a no-op" guarantee holds. But it's an implicit assumption — a future family whose first param doesn't affect geometry (e.g. a cosmetic toggle) would make the bench measure a no-op re-render and over-report determinism.

**Why this matters**
Forward-looking only; no current family violates it.

**Fix path**
Pick the first param with a non-empty `bbox` contribution, or document the assumption in the `_perturb` docstring. Low priority.

---

## Patterns and systemic observations

- **The "pure data families" choice is the high-leverage decision of this stage.** One immutable pydantic definition drives codegen, analytic bbox, and the slider JSON — there is no per-family imperative code, which is why the injection surface collapses to a single numeric formatter and why the bbox is auditable against the module source. This is the right pattern, not just the convenient one. The only crack in it (ENG-501) is precisely where the *data* model (a linear `BBoxTerm` sum) can't express a *non-linear* module behavior (`max(2, …)`); that's the seam to watch as families grow.
- **Trust-boundary placement is exemplary.** Untrusted input (live-slider POST, model plan numbers) is coerced and clamped at the *entry* to the family (`derive_values`/`clamp_values`), not deep inside emit. Combined with the existing `sanitize_scad` defense-in-depth (which would block any `use`/`import`/`minkowski` even if a string did leak), the SCAD generation path is robust against injection by construction.
- **Fail-closed is consistent across the deterministic tier.** Render error → surfaced (no LLM mask); gate fail → returned, never retried, never sliced/sent; unknown family → `render_failed` with a clean message, never a 500. The web layer wraps `rerender` in a `try/except` that returns `{"error": type+message}` as a 500 only for truly unexpected errors and never leaks a traceback (`webapp.py:808-810`). Error handling is uniform and matches the prior stages' contract.

## Dependency snapshot

Stage 5 adds **no new runtime dependencies**. It builds entirely on already-vendored pieces: `pydantic` (families), stdlib `http.server`/`threading`/`collections.OrderedDict` (webapp), `trimesh` (already present, used in tests), and the existing OpenSCAD binary. `template_bench` uses only stdlib (`argparse`, `platform`, `time`, `tempfile`). Dependency surface is clean — no notable concerns.

## Appendix: artifacts reviewed

- `src/kimcad/templates.py` (full)
- `src/kimcad/pipeline.py` (full; focus on tiering, `rerender`, `_build_from_template`, `_assemble_result`, `_build_geometry`)
- `src/kimcad/webapp.py` (full; focus on `_handle_render`, `template_state`, `render_lock`, `version_counter`, `_evict`, LRU)
- `src/kimcad/template_bench.py` (full)
- `src/kimcad/mcp_server.py` (Stage 5 diff — send-gate boundary comment)
- `src/kimcad/ir.py`, `src/kimcad/openscad_runner.py` (supporting: DesignPlan typing; sanitizer/BlockedCodeError; SanitizeResult)
- `src/kimcad/printability.py` (gate codes: `dim.mismatch`, `volume.exceeds`, `mesh.not_watertight`)
- `library/hooks.scad`, `library/clips.scad`, `library/organizers.scad`, `library/containers.scad`, `library/box.scad` (bbox cross-check)
- `tests/test_webapp.py`, `tests/test_templates.py`, `tests/test_pipeline_templates.py`, `tests/test_template_bench.py` (Stage 5 diffs)
- `frontend/src/api.ts` (re-render contract; `designIdFromMeshUrl` query-string handling)
- Live runs: `ruff check src tests` (clean); `pytest` of the 4 Stage-5 suites (73 passed); 7 live OpenSCAD renders of `wall_hook` across `plate_h` 20–60 to empirically confirm ENG-501.
