# Escape-paths audit-team — Remediation to 0/0/0/0/0

**Date:** 2026-06-04 · Re-verified: build clean; 175 frontend tests pass (Viewport now has its own test).

## Engineering (01)
| ID | Sev | Resolution |
|---|---|---|
| ENG-001 | Major | **Fixed.** A reopen (`#/design/<id>`) showed the "Designing…" overlay with a garbage timer + dead Cancel (busy set without stamping busyStartRef). Added a `restoring` state threaded App→Workspace→Viewport; a reopen now renders a plain "Reopening your design…" overlay (no timer, no Cancel); a real design run keeps the cancelable, elapsed-timed overlay. |
| ENG-002 | Minor | **Fixed** by the same change — the reopen overlay no longer shows a dead Cancel/Esc (it's a fast load; the user escapes via the Topbar). |
| ENG-003 | Minor | **Fixed.** `handleSlice`/`handleImportFile` now abort any prior in-flight request before overwriting the ref (mirrors runDesign/handleFile). |
| ENG-004 | Nit | **No change (intentional).** The PhotoOnramp `clearPreview` + the unmount effect can both revoke the same object URL — a no-op double-revoke; defense-in-depth (immediate-on-replace + unmount safety). Harmless. |

## UI/UX (02)
| ID | Sev | Resolution |
|---|---|---|
| UX-801 | Minor | **Fixed.** `aria-hidden` on the ~2 Hz `.kc-busy-elapsed` timer so a screen reader doesn't chant it. |
| UX-802 | Minor | **Fixed.** Busy-overlay backdrop bumped 80% → 94% (near-solid) so the dark copy + Cancel keep contrast even with a part framed underneath during a refine. |
| UX-803 | Nit | **No change.** The three "your computer's AI" phrasings are context-appropriate (reading vs designing vs the experimental offer) — correct as-is. |

## Docs (03)
| ID | Sev | Resolution |
|---|---|---|
| DOC-ESC-001 | Major | **Fixed.** CHANGELOG `[Unreleased]` now has an "escape paths on every action" entry. |
| DOC-ESC-002 | Minor | **Fixed.** HANDOFF resume block notes the escape stage was inserted ahead of Slice 8, built + gated, pending Scott. |
| DOC-ESC-003 | Minor | **Fixed.** `docs/stage-8.5-usability-plan.md` now has an "Escape paths everywhere (inserted ahead of Slice 8)" section noting the Slice 9 "progress on long runs" scope pulled forward + the deferred items. |

## Tests (04)
| ID | Sev | Resolution |
|---|---|---|
| TEST-801 | Major | **Fixed.** Added "no error surfaced" assertions to the ExportPanel + MyDesigns cancel tests (no `.kc-export-error`, no leaked "aborted") and a new App refine-cancel test that asserts the `error` testid stays empty. |
| TEST-802 | Minor | **Fixed.** `isAbortError` now tested against a real `DOMException('…','AbortError')` (the browser path) + a non-abort DOMException. |
| TEST-803 | Minor | **Fixed.** New App test exercises the refine-cancel branch (a part present → cancel → stays in the workspace, prior part intact, no error). |
| TEST-804 | Minor | **Fixed.** New `Viewport.test.tsx` (mocks the three.js KCViewport) renders the REAL busy overlay: a design run shows the elapsed timer + Cancel (→ onCancelDesign), a reopen shows "Reopening…" with no timer/Cancel. |
| TEST-805 | Nit | **Fixed.** Added the `postSlice` api-layer signal-forwarding assertion (its siblings had it). |

## QA (05)
Lone Nit (a theoretical post-unmount `act` warning) is a React-18 no-op — no action. All endpoints 200; all four cancels verified live; no regressions.
