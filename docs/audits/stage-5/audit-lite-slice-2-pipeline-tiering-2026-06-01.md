# Audit Lite — Stage 5 Slice 2: pipeline tiering (template-first, LLM fallback)
**Date:** 2026-06-01
**Scope:** `src/kimcad/pipeline.py` (registry wiring: `PipelineResult.template`, `Pipeline.__init__(registry=...)`, `run()` match + bbox alignment, `_build_geometry(match=...)` branch, new `_build_from_template`) and the new `tests/test_pipeline_templates.py`. `templates.py` was audited in Slice 1.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two Nit fixes. The tiering is correct and — most importantly — safe: a template-covered part builds with zero model calls, single-shot (no retry, no LLM fallback on failure), and an oversized template part still **fails the gate closed and is not sliced** (verified live: 120×100×80 on a 50 mm printer → `gate_failed`, `volume.exceeds`, `sliced=False` even with `confirm_print=True`). The bbox-alignment is sound — it only drives the dimensional check (a tautology for a deterministic template), while build-volume fit and wall thickness still run against the real mesh/printer/material. The two findings are both Nits: a benign registry-init race and one missing safety-interaction test.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 2

## Findings

### TPL2-001 Nit: `default_registry()` lazy global has an unguarded init race under the threaded webapp
**Dimension:** Correctness
**Evidence:** `templates.py` `default_registry()` does `if _DEFAULT_REGISTRY is None: _DEFAULT_REGISTRY = TemplateRegistry(...)`. The webapp serves on `ThreadingHTTPServer` (Slice 3), and each `Pipeline.__init__` calls `default_registry()`. Two threads racing the first call can both build it.
**Why it matters:** The race is **benign** — families are immutable, both builds are identical, and the global ends pointing at one valid instance (worst case: the 7 pydantic models are constructed twice at startup). But an unguarded lazy global is a smell that invites a non-idempotent change later.
**Fix path:** Build the registry eagerly at module import (`_DEFAULT_REGISTRY = TemplateRegistry(_build_default_families())`) and have `default_registry()` just return it — the construction is cheap and deterministic, so import-time is fine and the race disappears.

### TPL2-002 Nit: no explicit test that `proceed_anyway` slices a gate-FAILED *template* part
**Dimension:** Tests
**Evidence:** `test_pipeline_templates.py` covers the fail-closed direction (`test_template_gate_failure_is_single_shot_no_retry_no_llm`) but not the override direction. The override lives in shared `run()` code (`gate.status is FAIL and not proceed_anyway`) and *is* tested for the LLM path (`test_pipeline.py::test_proceed_anyway_with_confirm_slices_a_gate_failed_part`), so the behavior is covered — but not pinned for the template path specifically.
**Why it matters:** Low — the override is shared logic already under test. Adding the template-path case documents that the safety override behaves identically regardless of engine, which matters as the two paths diverge.
**Fix path:** Add a test: a template part whose stub render is the wrong size (gate FAIL) + `proceed_anyway=True` + `confirm_print=True` → `completed` and the slicer is invoked once.

## What's working
- **The deterministic invariant bites and is well-tested.** `provider.openscad_calls == 0` on the template path (proving no model round-trip — the whole point of live sliders), `state["n"] == 1` (single render, no retry loop), and `openscad_calls == 0` *after a gate/render failure* (proving the template path never silently falls back to the model) are all asserted with real counters, not mocks-of-mocks.
- **Safety preserved under the bbox override.** `run_gate` runs `_check_build_volume(report, printer)` and `_check_wall_thickness(plan, printer, material)` — the fit check uses the **actual rendered mesh**, not the plan, so aligning `plan.bounding_box_mm` to `expected_bbox` cannot hide an oversize part. Verified live: an oversized template part fails `volume.exceeds` and is not sliced even with `confirm_print=True`. The override makes `dim.match` a tautology for templates (correct — they're deterministic and Slice-1 already proves emit==declared bbox), nothing more.
- **No-LLM-fallback-on-failure is the right call.** A matched template that fails to render is a real defect (the library modules are proven), so surfacing it beats masking it with a model call; the only fallback is the no-match path. Both directions are tested.
- **Existing LLM path is untouched.** `object_type "block"` matches no family, so all 18 `test_pipeline.py` cases pass unchanged — the tiering is purely additive.

## Watch items
- **Clarification vs. template defaults.** A bare template request with no size still hits `first_clarification` and asks for dimensions rather than showing the family's default part immediately. That's safe, but the live-slider philosophy ("show something, adjust it") may favor pre-filling defaults — revisit in Slice 4 when the slider UI exists.
- **Slider ranges aren't printer-aware.** Param maxes are a fixed 250 mm, not derived from the active printer's build volume; a too-big part fails the gate closed (good), but the sliders could instead cap at what fits. A Stage-5-polish refinement, not a defect.

## Escalation recommendation
No escalation needed. Additive, well-scoped wiring; safety verified live; two Nits with trivial fixes. audit-team is not warranted for this slice.

---

## Re-audit (resolution) — 0/0/0/0/0

- **TPL2-001 (Nit) — FIXED.** `templates.py` now builds `_DEFAULT_REGISTRY` eagerly at module import; `default_registry()` just returns it — no lazy global, no init race. Slice-1 template tests still green (the registry is identical), so no regression.
- **TPL2-002 (Nit) — FIXED.** Added `test_proceed_anyway_slices_a_gate_failed_template_part`: a gate-FAILED template part + `proceed_anyway=True` + `confirm_print=True` → `completed`, slicer invoked once, `openscad_calls==0`. The override now pinned on the template path too.

Verified: `ruff` clean; `pytest tests/test_pipeline_templates.py tests/test_templates.py` = **58 passed** (incl. live renders); existing `tests/test_pipeline.py` = 18 passed (LLM path unchanged). **Roll-up: 0/0/0/0/0.**
