# Audit Lite — Stage 5 Slice 4: frontend live parameter sliders
**Date:** 2026-06-02
**Scope:** The Slice 4 frontend diff — `api.ts` (ParamSpec + `postRender` + versioned-URL id parse), `App.tsx` (re-render state + stale-response guard), `RightPanel.tsx` (the sliders), `Workspace.tsx` (prop forwarding), `Viewport.tsx` (overlay suppression while a model is framed), `styles.css` (slider styling), and the new `api.test.ts` / `RightPanel.test.tsx` cases. The committed `src/kimcad/web/assets/*` are build output of these sources (not audited as bundles).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two small fixes. The live-slider path is correct where it counts: the frontend never computes geometry (it edits values and asks the deterministic backend to render), the re-render uses `/api/render` with no model call, the server's clamped values replace local slider state (not the reverse), and a stale/out-of-order response can't clobber newer geometry (monotonic `renderSeq`). Two real issues — a `rerendering` flag that can stick `true` when a re-render is abandoned by a new design (Minor, cosmetic-but-visible), and a slider whose spoken value omits its unit (Nit, a11y). No Blocker/Critical/Major.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 1

## Findings

### SLIDE-001 Minor: the "Updating…" flag can stick on after a re-render is abandoned by a new design
**Dimension:** Correctness / UX
**Evidence:** `App.tsx:53-69` `handleRerender` sets `setRerendering(true)` up front and only clears it in `finally` *guarded by* `if (seq === renderSeq.current)`. `handleSubmit` (`:40`) and `handleNewDesign` (`:77`) bump `renderSeq.current++` to abandon an in-flight re-render but neither calls `setRerendering(false)`. So if a re-render POST is in flight (the ~150 ms-debounced drag has fired) when the user submits a new prompt or clicks "New design", the abandoned re-render's `finally` is skipped (`seq !== renderSeq.current`) and `rerendering` stays `true`. The next template-backed design then renders its Parameters card with a stuck "Updating…" note until the user happens to drag a slider.
**Why it matters:** It's a small but visible honesty/UX glitch on the marquee feature of the stage — the card claims it's busy when it isn't. UX is priority #1.
**Fix path:** Reset `setRerendering(false)` in both `handleSubmit` and `handleNewDesign` (alongside the existing `setRerenderError(null)` / `renderSeq.current++`). One line each.

### SLIDE-002 Nit: the slider's accessible value announcement drops the unit
**Dimension:** UX / accessibility
**Evidence:** `RightPanel.tsx` `SliderRow` gives the input `aria-label={spec.label}` (e.g. "Width") and renders the unit only in the visible `.kc-pval` (`<i>{spec.unit}</i>`). A screen reader announces the native `aria-valuenow` ("Width, 150") with no unit; for `wall` it reads "2" rather than "2 mm". Sighted users see "mm"; AT users don't.
**Why it matters:** Minor a11y polish, but cheap, and the unit is meaningful (mm vs unitless). Worth doing for the design bar this project holds itself to.
**Fix path:** Add `aria-valuetext={`${formatValue(value, spec)}${spec.unit ? ` ${spec.unit}` : ''}`}` to the range input so the unit is spoken.

## What's working
- **The deterministic invariant is honored end-to-end.** `RightPanel.tsx` only ever sends a `{name: number}` map to `onRerender`; all geometry comes back from `/api/render`. Verified live: a Width drag fired exactly one debounced `POST /api/render/<id>` with the merged values `{width:150,depth:60,height:40,wall:2}` and the Printability dims + slider re-synced to the server's re-rendered truth (X actual 150). No `openscad`/model call in the slider loop (carried from the Slice 2/3 backend proof).
- **Server truth wins.** `ParametersCard` re-syncs local slider values to `result.parameters` via `useEffect([parameters])`, so a clamped value the backend returns replaces the local one — proven by `RightPanel.test.tsx` "re-syncs the sliders to the server-returned (clamped) values".
- **Stale-response safety.** `App.tsx` `renderSeq` (a monotonic ref) means only the latest re-render's response calls `setResult`; a slow render that resolves after a newer one is dropped. Correct and minimal.
- **Debounce coalescing.** A rapid multi-step drag collapses to a single POST with the latest value (`RightPanel.test.tsx` "coalesces a rapid drag…", and the live drag confirmed one call, not many).
- **The gate guard wasn't weakened.** `ExportPanel.tsx` is untouched; it still keys browser slicing off `result.report.gate_status !== 'fail'` and clears the cached slice on `result.mesh_url` change (which a re-render versions), so a re-render that flips a part to gate-FAIL automatically disables browser slicing while keeping the model download. No browser send UI was added. `ExportPanel.test.tsx` still covers the fail/pass paths.
- **The viewport swap is genuinely quiet.** `KCViewport.loadMesh` awaits the new geometry and *then* removes the old mesh, so the previous part stays on screen during a re-render; `Viewport.tsx`'s new `hasModel` gate suppresses the full "Rendering…" overlay while a model is framed, leaving only the card's "Updating…". Matches the spec's "keep the last mesh, don't blank the viewport" requirement.
- **Layout is clean at both breakpoints** (live DOM/computed-style/bounding-box check): desktop (1280) and mobile (375) both show 4 sliders with no label/value overlap, no clipping, a terracotta track fill whose `--pct` matches the value (29.17 % at width 80/[10,250], 58.33 % at 150), and a mobile `@media` that fattens the track to 9 px for touch.
- **Tests + types + lint green:** vitest 30 passed (11 new), `tsc --noEmit` clean, `vite build` reproducible, ruff clean, full pytest 470 passed incl. live OrcaSlicer (the rebuilt SPA didn't break the served-asset tests).

## Watch items
- **A re-render *mesh-load* failure is silent.** If a re-render POST succeeds but the returned STL fails to fetch/parse, `Viewport.tsx` keeps the last mesh (good — safe degradation) but surfaces nothing, and `rerenderError` only covers POST failures. This is a near-impossible edge (the server just wrote the file locally) and the fallback is safe, so it isn't a formal finding — but if a future stage adds remote/large meshes, thread a viewport-load error up to the card.
- **Slider ranges are within the build volume** for `snap_box`, so a snap_box can't be dragged to a gate-FAIL — a nice implicit safety property, but other families' ranges aren't audited here; the structural gate-awareness (above) covers them regardless.

## Methodology note (rendered check)
The mandatory rendered desktop+mobile check was performed against the live `--demo` server in a real headless browser, but via **live-DOM / computed-style / bounding-box inspection plus the real `/api/render` network round-trip**, not a JPEG: the Claude_Preview screenshot tool timed out (30 s, twice, including on the WebGL-free landing page; console clean), an environment limitation of the capture subsystem. For verifying layout, overlap, clipping, colors, and the re-render behavior this evidence is at least as strong as a screenshot (the tool's own guidance prefers `inspect` over screenshots for style/layout); the limitation is recorded here rather than papered over.

## Escalation recommendation
No escalation needed. Well-scoped single-feature frontend slice; one Minor + one Nit, both with one-line fixes. audit-team is not warranted for this slice (the stage-end audit-full will cover the whole branch).

---

## Re-audit (resolution) — 0/0/0/0/0

- **SLIDE-001 (Minor) — FIXED.** `App.tsx` now calls `setRerendering(false)` in both `handleSubmit` and `handleNewDesign` (alongside the `setRerenderError(null)` / `renderSeq.current++` resets), so a re-render abandoned by a new design can no longer leave the "Updating…" note stuck on. New `App.test.tsx` "clears the re-render flag when a new design abandons an in-flight re-render" reproduces the exact path (re-render in flight via a never-resolving `postRender`, then New design → fresh design) and asserts the flag is `false` — it fails against the pre-fix code, so it's a real regression guard.
- **SLIDE-002 (Nit) — FIXED.** `SliderRow` now sets `aria-valuetext={`${formatValue(value, spec)}${spec.unit ? ` ${spec.unit}` : ''}`}`. Verified live in the demo browser: the four sliders report `aria-valuetext` "80 mm", "60 mm", "40 mm", "2 mm". Covered by `RightPanel.test.tsx` "announces the value with its unit via aria-valuetext".

Verified after the fixes: vitest **33 passed** (3 new — the App lifecycle guard, the aria-valuetext assertion, and the prop-driven note-hidden case); `tsc --noEmit` clean; `vite build` reproducible; the `aria-valuetext` + slider render re-confirmed live in a real browser. **Roll-up: 0/0/0/0/0.**
