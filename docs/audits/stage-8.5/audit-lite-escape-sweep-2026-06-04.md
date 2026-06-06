# Audit Lite — Escape-paths sweep (photo / slice / import cancels + design Esc)
**Date:** 2026-06-04
**Scope:** Adding a working Cancel/escape to the remaining blocking actions — the photo "Reading…" vision read, slicing, importing — plus Esc-to-cancel the design, so no action traps the user (api.ts, PhotoOnramp, ExportPanel, MyDesigns, App + tests). The design overlay's Cancel shipped earlier (5118918).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-two-small-fixes. Every targeted escape works and leaves clean state: photo/slice/import each abort the request and return the user to the prior control with no error (a cancel isn't a failure), refs are nulled in `finally`, and the abort makes the promise reject so no stale result applies. The deliberate non-targets (save = non-blocking commit; model-pull = no in-app action; global timeout = noted follow-up) are sound. Two minor gaps: MyDesigns import lacks the unmount-abort its siblings have, and the new `.kc-slice-actions` wrapper has no CSS so the Slicing/Cancel buttons abut.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 1

## Findings

### ESC-SWEEP-001 Minor: MyDesigns import has no unmount-abort (its siblings do)
**Dimension:** Correctness
**Evidence:** `PhotoOnramp.tsx` and `ExportPanel.tsx` each abort their in-flight request on unmount (`useEffect(() => () => <ref>.current?.abort(), [])`). `MyDesigns.tsx` `handleImportFile` adds `importAbortRef` and a Cancel button but **no unmount-abort effect**. So if the user starts an import and navigates away from My Designs before it finishes, the import keeps running; on success it still calls `onOpen(r.id)` — yanking the user to the imported design even though they'd left the gallery.
**Why it matters:** A mild surprise (a background import pulls you into a design after you navigated away) and an inconsistency with the other two cancelable uploads. Not a trap (the user already left), so Minor.
**Fix path:** Add `useEffect(() => () => importAbortRef.current?.abort(), [])` to MyDesigns (mirrors ExportPanel/PhotoOnramp).

### ESC-SWEEP-002 Nit: the `.kc-slice-actions` wrapper has no CSS — the Slicing/Cancel buttons abut
**Dimension:** UX (visual)
**Evidence:** `ExportPanel.tsx` now wraps the slice button + the (while-slicing) Cancel in `<div className="kc-slice-actions">`, but `styles.css` has no `.kc-slice-actions` rule. Both buttons are `kc-btn` (inline-flex), so they sit on one line with no gap between "Slicing…" and "Cancel".
**Why it matters:** Cosmetic — the two buttons touch with no spacing while slicing. Only visible during an active slice.
**Fix path:** Add `.kc-slice-actions { display: flex; gap: 8px; align-items: center; }` (and drop the now-redundant `margin-top` quirk if it misaligns).

## What's working
- **Every targeted escape works and is clean.** Photo: `handleFile` aborts a prior read, passes the signal, and on `isAbortError` calls `reset()` → back to the affordance with no error; a Cancel button is in the 'reading' card. Slice: `handleSlice` passes the signal, surfaces no error on cancel, and shows a Cancel beside the disabled "Slicing…". Import: same shape with a Cancel beside "Importing…". Each nulls its abort ref in `finally` (guarded `=== controller`), and clears its busy flag. (Verified by reading each handler + the tests.)
- **No stale-apply.** Because the aborted fetch rejects (uploadPhoto/importDesign re-throw the AbortError rather than masking it as a read/import failure; postJson lets it propagate), the awaited success path is skipped — a cancelled action can't apply its result.
- **The cancel-vs-failure distinction is honest.** `uploadPhoto`/`importDesign` re-throw `AbortError` so the component treats a cancel as a cancel (quiet return), and only a real failure shows the "couldn't read/import" message. The photo 'reading' copy now sets the right expectation ("this can take a moment on your computer's AI").
- **Keyboard escape.** The App Escape listener is bound only while `busy` and removed on cleanup (no leak, no double-bind); it aborts the in-flight design — a keyboard way out of the "Designing…" screen.
- **Sound non-targets.** Save (postSettings) correctly gets no Cancel — it's a non-blocking commit and the Settings screen stays interactive; model-pull is an external "pull in Ollama then re-check" with no in-app action; the global request timeout is honestly deferred to its own slice (the per-action Cancels already remove every trap). These are the right calls, not gaps.
- **Tests are non-vacuous + no regressions.** Each cancel test makes the mocked request reject on `signal.abort` and asserts the UI returned to its pre-action control with no error; the import test asserts `importDesign` received an `AbortSignal`; the Esc test fires a bubbling keydown and asserts the design cancelled. The `postJson` signal addition didn't break existing callers (postSettings passes none → undefined). Build clean; 171 frontend tests pass.

## Watch items
- **Global "nothing hangs forever" timeout** — deferred to its own slice (combining a timeout signal with the user signal without breaking the forwarding contract). The per-action Cancels cover the traps; this is the backstop. Tracked.
- **Unmount-abort sets state on an unmounting component** for PhotoOnramp/ExportPanel (the abort's catch runs `reset()`/`setSlicing(false)`). Harmless no-op under React 18 (no warning), so not a finding — noted for awareness.

## Escalation recommendation
No escalation needed. One Minor (a missing unmount-abort) + one Nit (a wrapper's CSS), on a focused, well-tested change whose escapes are verified working. The escape-stage slice-end `audit-team` + a live `wiring-audit` (confirming every action has a working escape in the running app) follow — that's the right place for the deeper pass.
