# UI/UX Deep-Dive — Stage 8.5 "Escape-Paths"

**Role:** Senior UI/UX Designer
**Stage under audit:** Escape-paths — a visible, working Cancel/Esc on every blocking action so the user is never trapped.
**Scope (frontend diff):** `git diff 8618027..HEAD -- frontend/src` — `Viewport.tsx` (busy/"Designing…" overlay), `PhotoOnramp.tsx` ('reading' card), `ExportPanel.tsx` (slice), `MyDesigns.tsx` (import), `App.tsx` (Esc + cancel + seq-guard), `ChatPanel.tsx` (experimental copy), `styles.css`.
**Date:** 2026-06-04

---

## What I checked rendered vs. source

**Rendered live** (fresh preview server on :8765, driven via DOM + computed-style, hanging fetches injected to hold each in-flight state open):

- **Design "Designing…" overlay** — verified live: spinner, title, honest sub-copy, live elapsed timer (saw it tick 0:00→0:08), `pointer-events: auto` on both overlay and Cancel, `role="status"`. Cancel returns clean (busy gone, prompt back, no error). **Esc cancels** live — verified. At 375px the Cancel is exactly **44px** tall and the sub-copy stays within the card (no h-scroll). Contrast on the dark overlay computed: title 17.96:1, sub-copy (60% white) 7.03:1, elapsed (46% white) 4.66:1, Cancel text 15.22:1 — all clear WCAG AA.
- **Photo "Reading…" card** — verified live: "Reading your photo…", the honest line "This can take a moment on your computer's AI" present, Cancel = "Cancel", 44px at mobile, `pointer-events: auto`. Cancel returns to the "Describe with a photo" affordance with **no** error card, no seed submitted.
- **Import** — verified live (My Designs): button → "Importing…", a "Cancel" appears immediately after it (order: Importing… / Cancel / New design), `kc-btn kc-btn-ghost`, 44px at mobile. Cancel returns clean to "Import", no error.

**Source + tests + committed evidence** (slice flow could not be driven through the demo — the model-free demo's `/api/design` returns to landing without a sliceable mesh for these prompts, so the ExportPanel slice button never mounts in the demo UI):

- **Slice "Slicing…"** — verified by source (`ExportPanel.tsx` lines 151–165: `{slicing && <button className="kc-btn kc-btn-ghost">Cancel</button>}` in the new `.kc-slice-actions` flex row beside the Slice button), CSS, the committed live evidence (verified this session: Cancel appears, aborts, returns to the button, no error), and the passing ExportPanel cancel test.
- **All four cancel paths + the seq-guard** — verified by running the touched test files: **71/71 pass** (`App.test.tsx`, `api.test.ts`, `ExportPanel.test.tsx`, `MyDesigns.test.tsx`, `PhotoOnramp.test.tsx`), including the cancel-aborts-and-returns test for each surface, the Esc-cancels-design test, and the "superseded design's late result is dropped" seq-guard test.

Net: 3 of 4 cancels independently re-verified rendered this session; the 4th (slice) verified via source + CSS + committed live evidence + passing test. Per the brief, I did **not** fail the stage for the absent JPEG.

---

## Verdict

**The stage meets the bar.** Every blocking state now has a clearly-labelled, reachable, working Cancel; the design overlay additionally honors Esc and shows a live timer + honest local-AI copy; a cancel is treated as a cancel (quiet return to the prior control), never as an error. The four affordances are consistent in label and weight. No new dead-ends, no layout regression, touch targets hold at 44px, contrast holds on the dark overlay. Findings below are **Minor/Nit polish** — none blocks the stage.

---

## Findings

### UX-801 (Minor) · Accessibility — Live elapsed timer sits inside an `aria-live` region and may re-announce every tick

**Category:** Accessibility
**Evidence:** Rendered, `:8765`, design "Designing…" overlay. The busy overlay is `<div role="status">` (which implies `aria-live="polite"`). Inside it, `.kc-busy-elapsed` ("0:08 elapsed") updates ~2 Hz and carries no `aria-hidden`. Confirmed live: `overlayRole: "status"`, `elapsedAriaHidden: null`, `elapsedInsideStatus: true`.
**Why this matters:** A polite live region re-announces changed content. A timer that mutates twice a second can make a screen reader chant "1 elapsed… 2 elapsed… 3 elapsed…" over the user's other navigation — turning a reassuring detail into noise. The *intent* of `role="status"` here is to announce "Designing your part…" once, not to narrate the clock. (Visually the timer is excellent — this is screen-reader-only.)
**Fix path:** Add `aria-hidden="true"` to the `.kc-busy-elapsed` node so it stays visual-only, and let the title/sub-copy carry the single spoken announcement. If you want the elapsed time spoken at all, do it coarsely (e.g. a separate visually-hidden node that updates once a minute), not on the 2 Hz visual tick.
**Blast radius:**
- Adjacent code: only `Viewport.tsx` busy block. The other three in-flight states ("Reading…", "Slicing…", "Importing…") have no ticking counter inside a live region, so they're unaffected — this is isolated to the design overlay.
- User-facing: screen-reader users on the design flow only; no visual change.
- Migration: none. Tests to update: none known.

### UX-802 (Minor) · State / Visual hierarchy — Busy overlay sits at 80% opacity over the model during a *refine*, so contrast on the dark copy is guaranteed only on a first design

**Category:** State / Visual hierarchy
**Evidence:** Source + computed style. `.kc-viewport-overlay.kc-viewport-busy { background: color-mix(in srgb, var(--kc-viewport-bg) 80%, transparent) }` (`--kc-viewport-bg` = `#14171c`). On a **first** design there's no model behind it, so the effective background is ~`#14171c` and contrast is excellent (measured 4.66–18:1). On a **refine** (the model is already framed and the overlay re-appears over it), the dark copy is composited over whatever the rendered part shows through the 20% transparency — typically mid-tone gray on dark, so it usually still passes, but a light or pale-rendered model could erode the elapsed-timer line (the lowest-contrast text at 46% white) below AA.
**Why this matters:** The escape affordance must read in *every* state it appears in, including the refine re-run. This is the one place the "contrast holds on the dark overlay" guarantee is conditional on what's behind it.
**Fix path:** Bump the overlay's opacity for the busy variant (e.g. 88–92% of `--kc-viewport-bg` instead of 80%), or add a subtle solid scrim behind just the text column. Cheap and makes the guarantee unconditional. Alternatively, raise the elapsed-timer alpha from 0.46 to ~0.6 (which already measures 7:1 on pure dark) for headroom.
**Blast radius:**
- Adjacent code: `styles.css` `.kc-viewport-overlay.kc-viewport-busy` only.
- User-facing: design refine flow (model already on screen) — a real, common path.
- Migration: none. Tests to update: none.

### UX-803 (Nit) · Copy — Two honest-time phrasings differ slightly across surfaces

**Category:** Copy
**Evidence:** Design overlay: "This runs on your computer's AI — it can take a few minutes…". Photo card: "This can take a moment on your computer's AI." Experimental offer (`ChatPanel.tsx`): "It writes the design on your computer's AI, so it can take a few minutes; you can cancel anytime."
**Why this matters:** All three are honest and accurate — this is genuinely good copy, and the time estimates are appropriately scaled (a vision read is "a moment," a full design is "a few minutes"). The only nit: "your computer's AI" appears three times with slightly different framings. That's fine and arguably correct (the durations *are* different), but if you ever want a single canonical phrase for the local-AI promise, this is where it'd live.
**Fix path:** No change required. If standardizing later, keep the duration differentiated (read = "a moment"; design/experimental = "a few minutes") — the variation is correct, only the lead-in could be unified.

---

## What's working (specific credit)

- **The design overlay is the model citizen of the stage.** Spinner + honest "runs on your computer's AI… nothing leaves your machine" + a **live elapsed timer** + Cancel + Esc — that's exactly the right answer to "a local model can run for minutes and a frozen spinner reads as a hang." The timer is the detail that turns "is it stuck?" into "it's working, and I can leave." Excellent.
- **A cancel is treated as a cancel, not a failure.** Every catch distinguishes `isAbortError` and returns *quietly* to the prior control — no scary "Slicing failed / import failed / couldn't read that photo" card after a deliberate Cancel. Verified live on three surfaces. This is the single most important UX property of an escape and it's done right everywhere.
- **Consistency is real.** All four cancels use the exact label "Cancel", all carry `.kc-btn` (so all inherit the 44px coarse-pointer floor), and placement is sensible per context (beside the action for slice/import; below the message for the full-cover overlay). The design overlay's white-outlined `.kc-busy-cancel` vs. the panels' `.kc-btn-ghost` is a *correct* context adaptation (dark overlay vs. light panel), not an inconsistency.
- **The seq-guard is a quiet win.** `designSeqRef` + the AbortController drop a superseded design's late resolve (cancel, New Design, or re-submit while in flight) so a stale result can't repopulate a fresh session — verified by the "late result dropped, version count stays 1" test. This is the kind of escape bug that bites *after* shipping; catching it now is the right altitude.
- **The pointer-events override is defended on purpose.** The compound selector `.kc-viewport-overlay.kc-viewport-busy` (with an explicit comment) beats the base `pointer-events: none` regardless of source order — a thoughtful guard against a future CSS reorder silently re-trapping the user. Verified live: `overlayPointerEvents: auto`, `cancelPointerEvents: auto`.
- **Reduced-motion is covered without losing the progress signal.** Global `prefers-reduced-motion: reduce` zeroes the spinner animation, but the elapsed timer still ticks — so motion-sensitive users still get a live "it's working" signal. Nice.
- **Unmount aborts.** ExportPanel, MyDesigns, and PhotoOnramp each abort their in-flight request on unmount, so navigating away mid-flight doesn't leave a request finishing in the background and yanking the user somewhere unexpected.

---

## Keyboard (per brief)

- **Esc cancels the design** — verified live. Good, and the highest-value place for it (the full-cover overlay is the most "trapping" state).
- **Other actions that would benefit from Esc** (noted, **not** a stage failure — the broader Esc-everywhere is a tracked follow-up): the photo read, slice, and import in-flight states are each escapable by an on-screen Cancel but **not** by Esc. Consistency would suggest Esc should cancel whichever single action is in flight, anywhere. Recommend folding "Esc cancels the active in-flight action" into the noted Esc-everywhere follow-up rather than this stage.

---

## Not flagged (documented decisions, verified sound)

- **Save has no Cancel** — correct; it's a non-blocking background commit, nothing to escape.
- **Model-pull has no in-app action** — out of this stage's surface; no in-flight UI to trap the user.
- **Global timeout deferred** — acknowledged; the per-action Cancel + Esc already prevent the trap this stage targets.

---

## Severity rollup

```
Blocker:  0
Critical: 0
Major:    0
Minor:    2   (UX-801 live-region timer chatter, UX-802 refine-overlay contrast headroom)
Nit:      1   (UX-803 copy phrasing variation — no change required)
-----
Total:    3
```

No Blockers. No cross-cutting journey gap. The stage delivers a clear, consistent, working escape on every blocking action, with the design overlay setting a notably high bar. The two Minors are polish that a screen-reader user (UX-801) and a refine-flow edge (UX-802) would feel; neither blocks the gate.
