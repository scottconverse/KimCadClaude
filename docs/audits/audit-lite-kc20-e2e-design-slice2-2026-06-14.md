# Audit Lite — #25 (KC-20) Playwright e2e — Slice 2 (design journeys)
**Date:** 2026-06-14
**Scope:** The core design journeys + their fixtures: `tests/e2e/test_design_refine.py` (new, 5 journeys) and the `landing` / `design` fixtures (+ the first-run-seed constant) added to `tests/e2e/conftest.py`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. Five journeys on the Slice-1 harness drive the real `kimcad web --demo` SPA through the core loop: a typed prompt renders a parametric part, the Inspector's Quality tab surfaces the Readiness score, a parameter slider re-renders the preview locally, a quick-refine chip is recorded in the conversation, and New design returns to a fresh landing. All five pass; the selectors and assertions were grounded by driving the real app, not guessed. No findings.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

## Findings
None. The journeys were authored against the live DOM (a throwaway exploration mapped the post-design tree, then removed), and two initial mis-assertions were corrected before commit: (a) the Readiness band is on the Quality tab — hidden under the default Parameters tab — so its journey switches tabs first; (b) a refine (chip/typed) round-trips to the **stubbed** demo model, which echoes a fixed demo part rather than re-cutting geometry, so the chip journey asserts the **conversation log**, not the preview dimensions. The slider journey, by contrast, is a real client-side param→geometry change, so it correctly asserts the preview's dimension label updates.

## What's working
- **Honest demo-mode modelling.** The journeys assert what the demo server genuinely does — slider = live local re-render (real geometry), refine = conversation echo (the model is stubbed) — rather than pretending the demo refine resizes the part. The docstring records the split so a future author isn't surprised.
- **Console-clean across the loop.** Every journey carries the `console_errors` watcher (attached before navigation via the `landing` fixture's dependency on it) and ends green — the design + slider + tab-switch + refine paths wire up with no errors / uncaught exceptions (only the filtered GL-driver perf warnings).
- **First-run handled correctly.** The `landing` fixture seeds `kc-first-run-done='1'` *before* navigation (a Playwright init script), suppressing the wizard modal that a fresh browser context shows — so the design journeys reach the workspace deterministically. The onboarding/wizard journey (a later slice) will omit the seed to test the wizard itself.
- **Resilient selectors.** Role/label-based throughout (`get_by_role("tab", …)`, `get_by_label("Width", exact=True)` to disambiguate the slider from its click-to-edit label), with Playwright's auto-waiting `expect` — no arbitrary sleeps.

## Watch items
- **Demo-copy coupling.** The chip journey asserts the demo echo string (`Demo part for: Make it bigger`). It's deterministic, but a change to the demo-mode copy would require updating the assertion — acceptable, and the right place to notice such a change.
- **Refine geometry is not exercised** (the model is stubbed in demo) — by design. The model's actual transform logic is covered by the unit suite; the e2e proves the refine *wiring* end-to-end.

## Escalation recommendation
No escalation. Test-only slice on the established harness; all 7 e2e tests (Slice 1 + 2) pass together, ruff clean. Slice 3 (photo/sketch on-ramps) is next.
