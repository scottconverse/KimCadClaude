# Audit Lite — Stage 8.5 Slice 1: frontend "My Designs" (library + routing + auto-save)
**Date:** 2026-06-03
**Scope:** `useHashRoute.ts`, `MyDesigns.tsx`, the `App.tsx` rewrite (routing + auto-save + restore), `KCViewport.captureThumbnail`/`Viewport.onModelReady`/`Workspace`, `Topbar` (My Designs link), `api.saveDesign(savedId)`, the gallery CSS, and the one backend `save`-update-in-place addition. UX weighted highest.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after three Minors. The deal-killer is genuinely fixed and rendered-verified: a design auto-saves with a captured thumbnail, gets a durable `#/design/<id>` URL, and a **hard refresh restores the full part** (viewport + readiness + the 4 template sliders) instead of dropping to the landing — plus a working library (open / inline-rename / duplicate / delete) that's responsive on mobile. The three Minors are a destructive Delete with no confirmation, a narrow auto-save race that can spawn a duplicate library entry, and a tractable-but-missing unit test for the restore-on-load path.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)".

**As found:** 0 Blocker · 0 Critical · 0 Major · 3 Minor · 0 Nit.

## Findings

### S1F-001 Minor: Delete removes a saved design with no confirmation (accidental data loss)
**Dimension:** UX
**Evidence:** `MyDesigns.tsx` — the Delete button calls `act(() => deleteDesign(design.id))` immediately on click; there's no confirm step and no undo. A saved design (the user's work) is permanently removed on a single click.
**Why it matters:** This slice exists *because* losing work is a deal-killer; a one-click, no-confirm delete of a saved part is the same failure mode by a different door. An accidental click (or a misfire on a dense card grid) silently destroys work.
**Fix path:** Add a lightweight two-step confirm on the card — click Delete → the button becomes "Delete?" with a cancel, deletes only on the second click (auto-reverts after a few seconds). Cheaper than a modal, better than `window.confirm`.

### S1F-002 Minor: auto-save create has no in-flight guard → a re-render during the initial save can create a duplicate entry
**Dimension:** Correctness
**Evidence:** `App.tsx:76-77` — `persist()` runs an immediate create whenever `!r.saved_id`. `handleModelReady` (`:88-92`) calls `persist()` on every framed model. If the user drags a slider *during* the initial create's round-trip (before `saved_id` is applied at `:68`), the re-render's `onModelReady → persist()` still sees `saved_id == null` and starts a **second** create → two library entries for one design. Narrow (the drag must land in the ~ms save window on loopback), but reachable.
**Why it matters:** A duplicated library entry is confusing and undermines the "one entry per design" model the update-in-place backend was built for.
**Fix path:** Add a `creatingRef` guard: when a create is in flight, skip starting another (the in-flight create sets `saved_id`; subsequent re-renders then re-save the single entry). Clear it in `finally`.

### S1F-003 Minor: the restore-on-load path has no unit test (it's tractable)
**Dimension:** Tests
**Evidence:** `App.tsx`'s restore `useEffect` (route `#/design/<id>` + not-already-loaded → `reopenDesign`) is only covered by the live rendered check. Unlike the auto-save path (which needs WebGL/canvas capture and is fairly untestable in jsdom), the restore path *is* tractable: render `App` with `window.location.hash = '#/design/x'`, mock `reopenDesign`, assert it's called and the workspace renders. No vitest pins it.
**Why it matters:** Refresh-restore is the headline behavior of this slice; a regression that broke the restore effect (e.g. a deps change) would pass the suite. The rendered check caught it once, but it isn't pinned.
**Fix path:** Add an `App.test.tsx` case: set the hash to `#/design/abc`, mock `reopenDesign` → resolved DesignResponse, render `<App/>`, assert `reopenDesign` called with `abc` and the workspace (not the landing) shows.

## What's working
- **The deal-killer is fixed and rendered-verified.** Live on :8765: design → `#/design/<uuid>` + auto-save (library count 1) + a real captured thumbnail (PNG, 10.5 KB) + readiness "Ready to print"; reopen restores the viewport, readiness, and the 4 template sliders; **a hard reload on the design URL restores the part, not the landing.** That's the whole point of the slice, working end to end.
- **No reopen/auto-save loop.** The restore effect bails when `resultRef.current?.saved_id === route.id` (`App.tsx`), so the auto-save's `navigate('design/<id>', replace)` doesn't re-trigger a reopen; `replaceState` updates the route directly without a spurious `hashchange`. The `resultRef.current.mesh_url === r.mesh_url` guard (`:66`) stops a stale `persist` from clobbering a newer design's state.
- **The re-save debounce coalesces correctly** (`:78-81`): a rapid drag clears the prior timer and captures the latest thumb + params, so a drag persists once; `handleSubmit`/`handleNewDesign` both clear the timer so a pending re-save can't fire against an abandoned design. The backend update-in-place (one entry, created_at + name preserved) is tested.
- **Thumbnail capture is safe.** `preserveDrawingBuffer:true` (negligible cost for one local preview) + a bounded offscreen downscale (maxDim 320) + a `try/catch → null`, so a capture miss yields a thumb-less-but-still-saved design (the gallery shows the typed placeholder) rather than a crash.
- **Gallery UX is solid.** Empty / loading / error (`role="alert"`) states; inline rename (Enter commits, Escape reverts, blur commits); the open affordance is a button with `aria-label`; decorative thumb `alt=""` with the name as the accessible label; responsive grid (verified mobile 375 — no overflow). Hash routing keeps the stdlib server fallback-free.
- **Tests are real.** `parseHash` + the gallery (render / empty / error / open / delete-and-reload / inline-rename) are pinned (7 new vitest, 50 total); `tsc` clean; build clean.

## Watch items
- **A pending re-save timer isn't cleared when navigating to a *different* design via the gallery** (only `handleSubmit`/`handleNewDesign` clear it). The stale timer firing is harmless — it re-saves to its own `saved_id` with the `mesh_url` guard, or 404s best-effort — but clearing it in the restore effect would be tidier.
- **The demo server auto-saves to `~/.kimcad/designs`.** That's the real (correct) behavior, not a bug; noting because UI checks against the demo write real library entries (cleaned up after this check).

## Escalation recommendation
No escalation needed. Three Minors (a missing delete-confirm, a narrow create-race, a tractable test gap) on a slice whose headline behavior is verified working end-to-end on desktop and mobile. Fix the three, re-audit to 0/0/0/0/0, push.

---

## Re-audit (resolution) — 0/0/0/0/0

- **S1F-001 (Minor) — FIXED.** Delete is now two-step: the first click arms a "Delete?" + "Cancel" pair (auto-disarms after 3.5s); the design is removed only on the confirm. New tests pin both the confirm path and the cancel path.
- **S1F-002 (Minor) — FIXED.** `persist()` now uses a `creatingRef` in-flight guard, so a re-render during the initial create can't start a second create → no duplicate library entry. The in-flight create sets `saved_id`; subsequent re-renders re-save the single entry.
- **S1F-003 (Minor) — FIXED.** New `App.test.tsx` case: loading on `#/design/abc` (mocked `reopenDesign`) restores the workspace (the stub mesh shows; the landing's prompt is absent) — pinning the refresh-restore behavior.

Verified: `tsc` clean; `npm run test` **52 passed** (8 files); `npm run build` clean; `test_webapp.py` 57 passed. **Roll-up: 0/0/0/0/0.**
