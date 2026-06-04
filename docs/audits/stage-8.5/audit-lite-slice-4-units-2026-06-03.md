# Audit Lite — Stage 8.5 Slice 4: mm/inch units toggle
**Date:** 2026-06-03
**Scope:** A units-preference feature (mm | inch) — a shared `useUnits` hook (`frontend/src/useUnits.ts`), the mm/in toggle + display conversion in `RightPanel.tsx` (Parameters card + Printability dims table), and tests (`useUnits.test.ts` + the `RightPanel units (Slice 4)` block). Backend is untouched and stays mm-only.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after one Minor fix (applied + re-tested). The backend mm boundary is intact (every `onChange`/`onRerender` payload is converted to mm before clamping; the native slider still operates in mm). The shared external store correctly syncs both `useUnits()` instances so the toggle updates the Parameters card and the Printability dims table together — proven by a non-vacuous test. One Minor: in inch mode, opening the inline numeric editor and committing without a real change nudged the value by up to ~0.13mm (a 2-dp round-trip artifact) and fired a wasted re-render. Fixed with a no-op guard + a regression test.

## Severity rollup

**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: inch-mode numeric edit drifts the value on a no-op commit
**Dimension:** Correctness / UX
**Evidence:** `RightPanel.tsx`, `SliderRow.startEdit` seeds the draft with the 2-dp inch display (`parseFloat(toDisplay(value).toFixed(2)).toString()`), and `commitEdit` runs on **blur** as well as Enter:
```
const mm = fromDisplay(rawDisplay)
onChange(spec.name, clampToSpec(mm, spec))
```
A 2.0 mm value displays as `0.08 in`. Opening the editor and clicking away (blur) — with no intended change — commits `0.08 in → 2.032 mm`, because the seeded display value is rounded to 2 dp and converted back. That fires a debounced re-render and silently changes the part from 2.0 to 2.032 mm.
**Why it matters:** KimCad's whole value proposition is dimensional precision. A focus+blur that silently moves a dimension (and burns a server re-render) erodes trust, even though the drift is bounded (≤ half a display ULP ≈ 0.127 mm) and converges rather than compounding. mm mode is unaffected (its label is exact, so `parseFloat` round-trips perfectly).
**Fix path:** In `commitEdit`, compare the committed value's display string to the current value's display string; if they're equal, the user didn't actually change anything — skip `onChange` (no drift, no spurious re-render). Add a regression test asserting that opening + committing the unchanged seed in inch mode does **not** call `onRerender`, while a real inch edit still does.
**Status:** ✅ Fixed — `formatDisplay()` helper added; `commitEdit` now no-ops when the display string is unchanged; two tests added (no-op guard + real-change still commits). 96 vitest pass.

## What's working

- **The backend mm boundary holds.** Every value that reaches `onChange`/`onRerender` is mm: the numeric-commit path applies `fromDisplay()` *before* `clampToSpec()`, and the native `<input type="range">` keeps `min`/`max`/`step`/`value` in spec mm — only `aria-valuetext` and the value label are display-converted. There is no path that sends inches to the deterministic mm engine. This is the load-bearing safety property and it's correct.
- **Shared state is correctly designed.** `useUnits` is backed by a module-level external store via `useSyncExternalStore`, not per-component `useState`. `getSnapshot` reads localStorage live and returns a stable primitive (`'mm'`/`'in'`), so there's no render loop and no stale module cache. `setUnitPref` notifies every subscriber, so toggling in the Parameters header instantly re-renders the Printability dims table (a *separate* `useUnits()` instance). The `RightPanel units` test that flips to inches and asserts the dims table header + cells convert is a genuine proof of cross-instance sync — exactly the bug the design avoids.
- **No subscriber leak.** `subscribe` removes both the in-memory listener and the `storage` event listener on cleanup. localStorage access is wrapped in try/catch on every path (read, write), so private-mode / disabled-storage degrades to mm rather than throwing.
- **Accessibility is solid.** The toggle is a real `role="group"` with `aria-label="Display units"` and two `<button type="button">` controls with `aria-pressed` reflecting state and a `focus-visible` ring. The slider announces its converted value via `aria-valuetext` (`"3.15 in"`), and the numeric input's `aria-label` correctly names the unit (`"Width value in in"`). The dims table headers convey the active unit (`"Target (in)"`).
- **Discoverable placement.** The toggle sits in the Parameters card header next to the values it governs — not buried in a settings page — matching the product's "units near the dimensions" intent.
- **Tests are non-vacuous and the default is protected.** 94→96 vitest pass. The inch-commit test asserts `101.6 mm` (not `4`); the clamp test asserts `200 mm` from a 40-in entry; the cross-card test proves sync. Adding `localStorage.clear()` to the global `afterEach` stops a unit choice from leaking into the mm-assuming tests, and those (`80 × 60 × 40 mm`, `aria-valuetext '2 mm'`) still pass — the mm default is unchanged for existing users.

## Watch items

- **Mobile header in the combined re-rendering+toggle state.** `.kc-card-hd-right` is `flex: none` with no internal wrap, so when the transient `Re-rendering…` note and the toggle show together on a 375-px card, the header right cluster could squeeze the `Parameters` title. The toggle-alone (persistent) state is fine. The slice-end **wiring-audit** should confirm the combined state at 375 doesn't overflow; if it does, shorten the re-render indicator to a dot/spinner.
- **Cross-tab + SSR snapshot paths are untested.** The `storage`-event branch (cross-tab unit change) and `getServerSnapshot` (`'mm'`, dead in this SPA) have no test. Both are trivial and correct by inspection; not worth a finding, but candidates if coverage is tightened.
- **CHANGELOG / user-facing docs.** The mm/in toggle is new observable behavior with no CHANGELOG/manual entry yet. This matches the established Slice 1–3 cadence (docs batched at stage close, not per micro-slice), so it's deferred to the Stage 8.5 close, not a drift finding now.

## Escalation recommendation
No escalation needed. One Minor, fixed inline; the architecture (shared store, mm boundary) is sound. 96 vitest pass, tsc + vite build clean. Ship the slice; the slice-end audit-team + wiring-audit remain the gate before Stage 8.5 close.
