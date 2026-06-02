# Audit Lite — Stage 5 Slice 3: live-slider re-render backend
**Date:** 2026-06-01
**Scope:** `src/kimcad/pipeline.py` (`_assemble_result` extraction + `rerender`), `src/kimcad/webapp.py` (`_result_to_payload` template/parameters, `design_response` returns the result, `/api/render/<id>`, per-id `template_state`, slice/G-code invalidation, versioned mesh_url, `/api/mesh` query-strip), and the new `tests/test_webapp.py` cases.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after fixes. The re-render path is deterministic (no model call — proven over a real socket), the slice-invalidation safety property is airtight (a re-shaped part drops its cached slice + G-code, and a gate-FAILED re-render becomes non-sliceable), and the error/contract handling is clean. But two real issues bite the live-slider path itself: a **stale wall-thickness gate** (dragging the wall slider thin produces no warning — verified) and an **unserialized per-design output dir** that concurrent slider re-renders can corrupt. One Nit on LRU freshness.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 1
- Nit: 1

## Findings

### RENDER-001 Major: concurrent re-renders of the same design race on its output dir — no serialization
**Dimension:** Correctness
**Evidence:** `webapp.py` `_handle_render` calls `pipeline.rerender(..., web_root / str(rid))` with no lock; `rerender` → `_build_from_template` writes `web_root/<rid>/part.scad`, renders to `part.<fmt>`, then `_assemble_result` exports `part.oriented.stl` — all fixed paths. `ThreadingHTTPServer` runs each request on its own thread (`test_webapp.py` proves it). Two `/api/render/<same id>` in flight (a fast slider drag, or any client) interleave: thread A writes `part.scad` (width=100), thread B overwrites it (width=120), A renders B's SCAD, and `registry[rid]` ends pointing at a mesh that may not match either response's reported dims — or a reader serves a half-written `part.oriented.stl`.
**Why it matters:** Live sliders are *the* feature of this slice and they generate exactly this access pattern (rapid same-id re-renders). Unserialized, the user can get a mesh that doesn't match the numbers, or a corrupt download. The slice path already serializes with `slice_lock` for the same reason; re-render needs the same discipline.
**Fix path:** Add a module-level `render_lock = threading.Lock()` in `make_handler` and hold it around the `pipeline.rerender(...)` call (the geometry write). Re-renders are sub-second, so serializing them is acceptable for a local single-user tool; the latest drag wins. (Per-id locking is an option but global is simpler and sufficient here.) Optionally `registry.move_to_end(rid)` too (see RENDER-003).
**Blast radius:**
- Adjacent code: mirrors the existing `slice_lock` pattern in `_handle_slice`; no other call site writes `web_root/<rid>/`.
- User-facing: the live-slider drag becomes reliable under rapid input.
- Tests to update: add a concurrency test (two near-simultaneous re-renders → consistent final mesh), or at minimum assert serialization holds.

### RENDER-002 Minor: the re-render wall-thickness gate checks the ORIGINAL declared wall, not the slider value
**Dimension:** Correctness
**Evidence:** `printability._check_wall_thickness` reads `plan.dimensions[<wall key>]`. `rerender` builds `plan = base_plan.model_copy(update={"bounding_box_mm": ...})` but leaves `dimensions` as the original design's. Verified: a design at `wall=2.0` re-rendered with `wall=0.8` still emits `wall.ok "Wall 2.0 mm is adequate."` and `result.plan.dimensions["wall"] == 2.0` — the thin-wall WARN never fires though the rendered part now has a 0.8 mm wall.
**Why it matters:** It's an honesty gap on the wall slider specifically: a user can thin a wall below the printable minimum and the report still says it's fine. It's WARN-level (a thin wall doesn't FAIL/block slicing), so not a safety hole — but the gate is silently checking stale geometry, which undercuts the report's trustworthiness on the exact interaction Stage 5 adds.
**Fix path:** In both `run()` (template branch) and `rerender()`, fold the template's current parameter values into the gate plan's dimensions, e.g. `dimensions={**plan.dimensions, **match.values}`, so dimension-keyed gate checks reflect the geometry actually built. Add a test: a thin-wall re-render produces `wall.thin`.

### RENDER-003 Nit: a re-render doesn't refresh the design's LRU position
**Dimension:** Correctness
**Evidence:** `_handle_render` does `registry[rid] = result.mesh_path`; assigning to an existing `OrderedDict` key does not move it to the end. Eviction (`registry.popitem(last=False)` in `_handle_design`) drops the oldest-inserted, so an actively re-rendered design can be evicted ahead of idle ones once a session exceeds `MAX_REGISTRY` (50) designs.
**Why it matters:** Very low — needs >50 designs in one session, and the effect is a 404 on the next interaction with an old-but-active design. Cosmetic for a local single-user tool.
**Fix path:** `registry.move_to_end(rid)` when a re-render updates the entry (and likewise the design path already inserts fresh). One line under the existing lock.

## What's working
- **Deterministic re-render, proven.** The binary-gated socket test drives `/api/design` then `/api/render` with the real OpenSCAD binary, asserts the X dimension actually changes 80→120, and checks `provider.openscad_calls == 0` in-process — real proof there's no model in the slider loop.
- **The slice-invalidation safety property is airtight.** On a geometry-changing re-render, `_handle_render` drops `gcode_registry[rid]` and every `slice_cache[(rid, …)]` under the lock and updates `gate_status_by_rid[rid]`, so the previous shape's slice can't be downloaded, re-sliced from cache, or sent. A gate-FAILED re-render replaces the mesh and marks the id `fail` → the slice endpoint refuses it. `test_rerender_invalidates_a_cached_slice` proves the re-slice (calls==2). A *failed* re-render (no new mesh) correctly leaves the prior good mesh + slice intact.
- **Clean contract + error handling.** `/api/render` is behind `_read_json_body` (size guard, non-dict-body 400), 404s an unknown or LLM-backed id ("no adjustable parameters"), 400s a missing `values`, and wraps the pipeline in the same no-traceback `except` as `_handle_design`. The shared `_result_to_payload` keeps `/api/design` and `/api/render` on one contract.
- **The versioned mesh_url is sound.** `/api/render` returns `/api/mesh/<id>?v=<n>` and the `/api/mesh` route now strips the query via `urlsplit` before parsing the id — verified the cache-busted URL fetches the fresh mesh in the socket test.
- **The `_assemble_result` extraction is a net safety win.** Harden-before-export and never-slice-a-gate-failed-part now live in exactly one place shared by `run` and `rerender`; all 18 existing pipeline tests still pass, so the refactor preserved behavior.

## Watch items
- Slider ranges remain fixed (not printer-aware) — carried from Slice 2; a too-big re-render still fails the gate closed.

## Escalation recommendation
No escalation needed. Well-scoped backend slice; one Major with a known one-pattern fix (mirror `slice_lock`), one Minor honesty fix, one Nit. audit-team is not warranted for this slice.

---

## Re-audit (resolution) — 0/0/0/0/0

- **RENDER-001 (Major) — FIXED.** Added `render_lock` in `make_handler`; `_handle_render` holds it around `pipeline.rerender(...)`, serializing the per-design geometry write (mirrors `slice_lock`). New `test_concurrent_rerenders_are_serialized` proves it deterministically: a 0.3 s slow renderer records its [enter,exit] interval and the two concurrent re-render intervals must not overlap — they don't.
- **RENDER-002 (Minor) — FIXED.** `run()` (template branch) and `rerender()` now fold the template's current values into the gate plan via `dimensions={**…, **match.values}`, so dimension-keyed gate checks reflect the built geometry. Verified: a re-render at `wall=0.8` now reports "Wall 0.8 mm…" (not the stale "2.0"), and `plan.dimensions["wall"] == 0.8`. (Note: the wall *slider's* min, 0.8 mm, coincides with the PLA/0.4 mm gate minimum, so a sub-minimum-wall WARN isn't reachable via the slider — but the gate was reporting the wrong wall *value*; the fix makes the reported thickness honest.) Test `test_rerender_gate_reflects_current_parameter_values`.
- **RENDER-003 (Nit) — FIXED.** `_handle_render` now calls `registry.move_to_end(rid)` when it updates the entry, so an actively re-rendered design stays LRU-fresh.

Verified: `ruff` clean; the re-render/concurrency/invalidation/reshape tests pass (incl. 2 live OpenSCAD + the serialization test); existing pipeline + webapp suites unchanged. **Roll-up: 0/0/0/0/0.**
