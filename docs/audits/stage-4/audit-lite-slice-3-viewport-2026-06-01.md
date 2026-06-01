# Audit Lite — Stage 4, Slice 3: workspace + Three.js viewport + real mesh loading
**Date:** 2026-06-01
**Scope:** The 3-column workspace, the vanilla Three.js viewport (`KCViewport.ts`) loading the real `*.oriented.stl` from `/api/mesh/<id>`, the minimal design flow (describe → /api/design → mesh), and the wired topbar/landing. Branch `stage-4-react-spa-shell`. (Rich conversation/plan/printability rendering = Slice 4; printer/slice/download = Slice 5.)
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. The real rendered part loads and displays in a framework-free Three.js viewport, the 3-column desktop and stacked mobile layouts were verified by a RENDERED browser check (not static comparison), and that check caught two layout bugs that are now fixed. Reviewing the viewport internals surfaced two more real issues — an STL load race and incomplete GPU disposal — both fixed in this pass. Build, ruff, full suite, and npm audit are green.

## Severity rollup (round 1)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 4 · Nit: 0
  (2 from the rendered visual check: workspace vertical collapse, disabled-button styling; 2 from internals: STL load race, incomplete dispose.)

## Severity rollup (round 2 — after fixes)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0 → **0/0/0/0/0, gate cleared**

## Rendered visual check (mandatory for UI slices — done)
Ran `kimcad web --demo` and rendered the SPA in a non-interactive Preview, driving the real flow (example chip → POST /api/design → STL → viewport). Captured and reviewed: desktop landing, desktop workspace (3-col, real box rendered on the grid plate), mobile-375 landing (responsive, hero wraps), mobile workspace (stacked: conversation → viewport → panels, real mesh). Layout confirmed via computed styles + getBoundingClientRect, not just pixels (desktop grid row resolved 774px with no empty space / no scroll; mobile single 375px column, rows 130/341/283).

## Findings (all fixed this pass)

### UX-301 Minor: desktop workspace collapsed vertically *(caught by the rendered check)*
**Dimension:** UX · **Evidence:** at ≥1000px the `.kc-workspace` grid had only `grid-template-columns` set; with auto rows the single row sized to content (the viewport card has no intrinsic height), leaving the workspace ~265px tall over empty page. **Fix:** added `grid-template-rows: 1fr` (mobile overrides it). Re-verified: workspace spans 58→832, body == viewport, no scroll. **(Fixed.)**

### UX-302 Minor: disabled "Design it" button looked fully enabled *(caught by the rendered check)*
**Dimension:** UX · **Evidence:** the empty-state CTA is `disabled`, but with no `:disabled` style it rendered at full terracotta — a dead-looking button. **Fix:** `.kc-btn:disabled { opacity: .5; cursor: not-allowed }`. Re-verified faded on the mobile landing. **(Fixed.)**

### ENG-301 Minor: STL load race could show a stale part
**Dimension:** Correctness · **Evidence:** `KCViewport.loadMesh` awaited `STLLoader.loadAsync` then mutated the scene; the React wrapper's `cancelled` flag only guarded `setState`, not the viewport mutation. Two overlapping loads (fast re-design) could resolve out of order and leave the older mesh displayed. **Fix:** a monotonic `loadToken` — `loadMesh` captures it, discards (and disposes the geometry) if a newer load or a `clearModel()` superseded it; `clearModel()` also bumps the token to cancel an in-flight load. **(Fixed.)**

### ENG-302 Minor: dispose() leaked grid/plate/drag resources
**Dimension:** Correctness · **Evidence:** `dispose()` disposed only the model group; the grid + plate-border geometries/materials were never released (a GPU leak each mount cycle — notably under React StrictMode's dev double-mount), and a dispose during an active drag left `pointermove`/`pointerup` listeners on `window`. **Fix:** `dispose()` now traverses the whole scene disposing every geometry/material, and an active drag registers a `dragCleanup` that dispose() invokes. **(Fixed.)**

## What's working
- **The real 3D pipeline renders end-to-end:** describe → `/api/design` → the pipeline's `*.oriented.stl` (pipeline.py:296) → `STLLoader` → a shaded terracotta part on the dark Workshop grid plate. Confirmed visually at desktop + mobile.
- **Honest viewport states:** designing / rendering / empty / error overlays (role="status"), and a typed `postDesign` that degrades a non-JSON or non-200 response to a readable message rather than a crash.
- **Architecture:** the viewport is framework-free vanilla three (portable, matches the prototype's approach) behind a thin React wrapper; three.js is code-split + lazy-loaded so the entry bundle stays ~147 kB and the ~525 kB engine chunk loads on first design (acceptable: localhost-served, committed, `test_viewport_chunk_is_code_split_from_the_entry` guards the split).
- **Responsive:** verified 3-col ≥1000px and stacked ≤1000px (with the viewport given a real `minmax(240px,42vh)` row on mobile).
- **Green:** ruff clean; full `pytest tests` = 399 passed incl. live; build emits {kimcad.js, Workspace.js, index.css, 3 latin woff2} with no orphans and no chunk-size warning; `npm audit` = 0.

## Watch items
1. **W7 — viewport keyboard accessibility.** Orbit/zoom are pointer-only; the canvas has an `aria-label` and the data lives in the (forthcoming) panels, so this is supplementary, but a keyboard affordance (or a "reset view" control) is worth adding when the viewport toolbar lands.
2. **W6 (carried) — vitest.** `KCViewport` needs WebGL so it can't run in jsdom, but `api.ts` and the `App` state machine are unit-testable. Stand up vitest in Slice 4 (alongside reinstating the field-contract tests, W2) and gate it in `scripts/ci.sh`.

## Escalation recommendation
No escalation needed. A substantial but well-scoped slice; the rendered check did its job (two layout bugs caught), the viewport internals are now race- and leak-safe, and everything verifies green. audit-team is not warranted for this change (it is warranted as the Stage-4 gate later).
