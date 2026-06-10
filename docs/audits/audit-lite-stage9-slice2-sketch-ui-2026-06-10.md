# Audit Lite — Stage 9 Slice 2: sketch on-ramp UI
**Date:** 2026-06-10
**Scope:** `uploadSketch` in api.ts (mirrors uploadPhoto incl. the typed model-down mapping), PhotoOnramp parameterized by `kind` ('photo' | 'sketch') via a copy table (endpoint, affordance, reading line, scale note — a sketch's dimensions are READ AS WRITTEN, a photo's are estimates — and error guidance), PencilGlyph, the Landing renders both on-ramps side by side, App.test mock extended.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. One component serves both on-ramps with zero photo-path behavior change (all 17 prior PhotoOnramp tests pass untouched), the sketch mode is pinned by 3 new tests (endpoint selection — the photo upload must NOT fire; sketch-specific copy; model-down never blames the sketch), and the live demo serves both affordances with `/api/sketch-seed` returning the seeded description end to end.

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**

## Adversarial checks
- **Photo regression surface:** `kind` defaults to `'photo'`; the workspace call site is untouched; every prior photo test passes unmodified — the parameterization is provably behavior-preserving.
- **Endpoint cross-wiring:** the sketch test asserts `uploadSketch` fired AND `uploadPhoto` did not — the exact bug a copy-table refactor invites.
- **Trust copy:** the privacy lines interpolate the noun but keep the same promise (read locally, never leaves, not saved) — the backend's sketch handler carries the same QA-A-003 typed model-down mapping (shipped in the BCD gate), and the SPA surfaces it (tested).
- **Honesty nuance kept:** the photo's "sizes are estimates" did NOT leak into the sketch mode, whose contract is the opposite ("read as written — check they came through").
- **Live wiring:** both affordances render on the served landing; `/api/sketch-seed` 200s with the demo seed.

## Tests
3 new sketch-mode tests; vitest **308**; typecheck; byte-exact build; live demo wiring check.

## Escalation recommendation
No escalation.
