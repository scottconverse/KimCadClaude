# Stage 5 — UI/UX Deep-Dive (Senior UI/UX Designer)

**Audit type:** audit-team role audit, live-app driven
**Scope:** Stage 5 live parameter sliders + numeric entry + mm/inch units toggle, the W/D/H viewport dimension pills, param labels/units, slider/numeric accessibility, and the empty/disabled/error states of the Parameters card.
**App under test:** running demo at `http://127.0.0.1:8765/` (template-backed demo → real sliders), launched via `.claude/launch.json` (`kimcad.cli web --demo --port 8765`).
**Date:** 2026-06-05 · **Branch:** `stage-0-7-audit-backfill`
**Method:** Live DOM + computed-style measurement at 1280px (desktop) and 390px (mobile). Per the known harness limit, `preview_screenshot` timed out (shared/contended preview browser) and synthetic events in the isolated eval world were used for state transitions; every load-bearing claim below is re-verified by DOM/computed-style measurement, which is authoritative. Source cross-referenced: `frontend/src/components/RightPanel.tsx`, `frontend/src/useUnits.ts`, `frontend/src/components/Viewport.tsx`, `frontend/src/styles.css`.

---

## What's working (specific credit)

These are real, verified strengths — not generic praise.

- **AA contrast was deliberately engineered and it holds.** The active unit button uses `--kc-accent-strong` (#b1542f) precisely because raw `--kc-accent` is only 3.99:1 for white text; measured, the active "mm"/"in" chip is **5.03:1** (AA pass). Muted text on card **5.36:1**, ink **15.31:1**, error red **5.83:1**, the "Re-rendering…" indicator **4.66:1**, axis tag **4.79:1**. Every Stage 5 text/background pair I sampled clears WCAG 2.1 AA. The inline source comments (UX-001) show this was a conscious fix, not luck.
- **The quiet model swap is the right call.** Driving a slider to 120mm, the "Re-rendering…" note appears and clears, the value commits, and **no full-cover overlay** flashes over the viewport — the previous part stays framed while the new mesh loads atomically (`Viewport.tsx` `loadMesh` awaits-then-swaps, `RightPanel` debounces 150ms). This avoids the jarring flash-to-spinner that a naive implementation would have. Verified live: `viewportBusyOverlayDuringRerender: false`.
- **Numeric entry is genuinely well-built.** Click-to-type opens a `type=number` input with a correct `aria-label` ("Width value in inches"), live range validation with `role="alert"`, `aria-invalid="true"`, and `aria-describedby` wiring to the error node. The error is self-describing ("Enter 0.394–9.843 in"), not a bare range. Enter/blur commits, Escape cancels (verified — edit closed cleanly).
- **Units are one shared source of truth.** `useUnits` is backed by `useSyncExternalStore` over localStorage, so toggling to "in" instantly converts the sliders, the value labels, the Printability dims-table header ("Target (in)"/"Actual (in)") AND its cell values, and the bbox size line — all at once, with no drift. Verified live: dims header and first row both flipped to inches in the same toggle. The preference also persisted across a re-render and survives reload.
- **Accessibility fundamentals are present on the slider.** Native `input[type=range]` (free keyboard nudge), per-slider `aria-label`, a live `aria-valuetext` that reads the value in the current display unit ("3.15 in"), a visible `:focus-visible` outline (2px accent, 4px offset), and a logical tab order (unit toggle → value-button/slider pairs in DOM order). `prefers-reduced-motion: reduce` is honored globally.
- **Axis tags tie sliders to the viewport.** Width/Depth/Height sliders carry X/Y/Z chips that map to the viewport's W/D/H dimension pills — a thoughtful spatial link.
- **The no-slider empty state copy is humane** (source, `kc-param-hint`): it explains *why* there are no sliders ("built straight from your description rather than a ready-made shape with options") and routes the user to the conversation panel with concrete examples ("make it 10mm taller"). This is the opposite of a blank screen.

---

## Findings

### UX-501 — Minor — Inch readouts have ragged decimal precision within one slider group
**Category:** Copy / Visual consistency
**Evidence:** Live, 1280px, Parameters card in inch mode. Width = **"3.15in"** (2 dp), Depth = **"2.362in"** (3 dp), Height = **"1.575in"** (3 dp), Wall = **"0.079in"** (3 dp). Same column, same group, different decimal counts.
**Root cause:** `formatDisplay`/`formatMm` do `parseFloat(value.toFixed(3)).toString()`, which trims trailing zeros — 80mm → 3.150 → "3.15", while 60mm → "2.362". The 3-dp choice (UX-004) is correct for editing nozzle-multiple walls; the trailing-zero trim is what makes the column uneven.
**Why it matters:** A column of numbers that should align visually instead reads ragged (3.15 / 2.362 / 1.575). For an ex-Apple bar on a precision tool, mixed decimal places in one numeric column reads as unpolished and very slightly harder to scan. It does not affect correctness.
**Blast radius:**
- Adjacent code: `useUnits.formatMm` (used by Printability dims table + bbox size line — same ragged effect appears there) and `SliderRow.formatDisplay` in `RightPanel.tsx`. Fix once in a shared formatter, apply both places.
- User-facing: every inch-mode readout — sliders, value labels, dims table, size line.
- Migration: none. Tests to update: `useUnits.test.ts` likely asserts the trimmed form; a fixed-dp change would need those expectations updated.
**Fix path:** For inch display, pad to a fixed precision instead of trimming — `toFixed(2)` for the slider/label column (matches the title hint "0.39–9.84 in"), reserving 3 dp only for sub-mm/wall-class values; or simply present all inch readouts at a consistent dp. Recommend a single shared `formatInch(mm, {dp})` so the slider label, the edit error, the title hint, and the dims table never disagree on precision.

### UX-502 — Minor — Title hint and edit-error disagree on inch precision (2 dp vs 3 dp)
**Category:** Copy
**Evidence:** Live, inch mode. The value button's `title` reads "Click to type an exact value (**0.39–9.84** in)" (2 dp) while the inline validation error reads "Enter **0.394–9.843** in" (3 dp) for the same bound. The mm-mode title also shows a 2-dp variant.
**Why it matters:** Two different printed bounds for the same limit is a small trust ding on a precision control — a user comparing the hover hint to the error sees "9.84" vs "9.843" and wonders which is real.
**Blast radius:**
- Adjacent code: `SliderRow` — the `title` string uses `toFixed(2)`, `handleDraftChange` error uses `toFixed(3)`. Same component, two formatters. Related to UX-501 (same root: no single precision authority).
- Migration: none.
**Fix path:** Route both the title hint and the error through the same `formatInch` helper at one precision. Recommend 2 dp for both the hint and the error in inch mode (the bound itself is coarse; the 3-dp precision is only needed for the *value*, not the printed limit).

### UX-503 — Minor — Slider touch hit-area is 44px only under `pointer: coarse`, not at narrow width
**Category:** Accessibility / Responsive
**Evidence:** Live, viewport 390px wide (emulated, fine pointer). The slider track renders 9px tall with **no** added hit padding (`min-height: auto`, `padding-block: 0`), measured 9px. The 44px hit area (`min-height:44px; padding-block:18px`) lives only inside `@media (pointer: coarse)`. By contrast, the unit toggle and value button correctly use `@media (pointer: coarse), (max-width: 640px)` and measure a full 44px tall at this width.
**Why it matters:** On a real phone (coarse pointer) the slider is fine — 44px. The gap is the narrow-window / desktop-touch / hybrid-device case where width is small but the pointer reports fine: there the most-touched control of the whole feature is a 9px target while its siblings already grew. It's an internal inconsistency the codebase otherwise avoids by design (the inline UX-002 comment explicitly calls out that "a desktop resized to 375px never reports coarse, so both queries are needed" — the slider rule simply didn't get the second query).
**Blast radius:**
- Adjacent code: `.kc-range` `@media (pointer: coarse)` block in `styles.css` (~line 769) vs the `.kc-unit-btn, .kc-pval-btn` block (~line 1021) which already does both queries. One-line fix: add `(max-width: 640px)` to the slider's coarse rule (or merge).
- User-facing: touch/hybrid users on a narrow window; phone users already covered.
- Migration: none. Tests: none known (no responsive hit-area test exists).
**Fix path:** Change the slider's `@media (pointer: coarse)` to `@media (pointer: coarse), (max-width: 640px)`, matching the belt-and-suspenders pattern the unit/value buttons already use, so the 44px hit area applies whenever the layout is phone-sized regardless of reported pointer type.

### UX-504 — Minor — Unit-toggle buttons meet the 44px height floor but are far under it in width (25–35px)
**Category:** Accessibility (touch target)
**Evidence:** Live, 390px. Active "in" chip measures **25×44**, inactive "mm" **35×44**. Height is on-spec; width is well below the WCAG 2.5.5 / Apple HIG 44×44 recommendation.
**Why it matters:** A 25px-wide tap target between two adjacent toggles invites mis-taps (hitting "mm" when reaching for "in") on a phone. Less acute than a too-short target because the two buttons are siblings in one pill (a near-miss usually still lands on a unit button), which is why this is Minor not Major.
**Blast radius:**
- Adjacent code: `.kc-unit-btn` padding (`2px 8px`) in `styles.css`. Adding horizontal min-width affects only this two-button group.
- User-facing: mobile users toggling units.
- Migration: none.
**Fix path:** On the coarse/narrow query, give `.kc-unit-btn` a `min-width` of ~44px (or increase horizontal padding) so each chip is a comfortable square-ish target. The pill already clips overflow, so widening the children is visually clean.

### UX-505 — Nit — "Re-rendering…" is the only non-viewport feedback, and it sits in the card header away from the slider
**Category:** Interaction state
**Evidence:** Live. During a drag-commit the only Parameters-card feedback is the small mono "Re-rendering…" text in the card header (verified it appears then clears). The slider thumb/track show no in-flight state; the real "something happened" feedback is the viewport model swapping.
**Why it matters:** Mostly fine — the viewport IS the primary feedback and the swap is visible. But the user's gaze during a drag is on the thumb or the viewport, not the card header, so the textual indicator is easy to miss. Because the re-render is fast and deterministic in this build, this rarely bites; on a slower machine a tiny bit of at-the-thumb feedback (e.g. a subtle pulse on the value, or a momentary thumb tint) would reassure better. Flagging as a Nit, not a defect — current behavior is acceptable.
**Fix path (optional):** Consider a very light in-flight cue co-located with the active control (value label dims/pulses while the debounce-and-render is pending). Keep it `prefers-reduced-motion`-safe.

---

## States coverage (Step-3 checklist)

| State | Status | Evidence |
|---|---|---|
| Default / idle | ✅ | 4 sliders render with labels, axis tags, values, unit toggle (live). |
| Loading (re-render) | ✅ | "Re-rendering…" `role=status` note; viewport quiet-swaps, no overlay flash (live). |
| Success populated | ✅ | Slider drag → value commits → re-syncs to server truth (live, 80→120mm). |
| Success empty (no part yet) | ✅ | `kc-muted-note` "The part's adjustable parameters will appear here once it's designed." (source). |
| No-slider (LLM-backed) | ⚠️ Not reachable live in this demo build | `demo:experimental` routes to the experimental *offer* path and returned to landing rather than rendering a no-slider populated part, so the `kc-param-hint` populated state could not be exercised live. The copy itself (source `RightPanel.tsx` 313–318) is clear and helpful. Recommend a demo scenario that lands a non-template part so this state is walkable, paralleling the QA-002 `demo:gatefail` scenario. |
| Error (re-render failed) | ✅ (source-verified) | `kc-param-error` "That change didn't render — your last version is still here. Nudge a slider to try again." with demoted technical detail. Not triggered live (demo re-renders succeed). |
| Numeric input error | ✅ | Out-of-range "999" → inline `role=alert` "Enter 0.394–9.843 in", `aria-invalid`, `aria-describedby` (live). |
| Disabled | ✅ by design | Sliders intentionally remain enabled during re-render (debounce coalesces) — verified `anyRangeDisabledDuringIdle: false`. |

---

## Accessibility summary

- **Keyboard:** Slider focusable and arrow-nudgeable (native range), value button reachable, edit input commits on Enter / cancels on Esc, visible focus rings throughout. Tab order logical.
- **Screen reader:** Per-slider `aria-label`; `aria-valuetext` reads value + spelled-out unit context; unit toggle is a labeled `role=group` ("Display units") with `aria-pressed` on each button; numeric error wired via `role=alert` + `aria-describedby`; the busy/updating notes use `role=status`. Unit word is spelled out ("inches") for the input aria-label (UX-005) so SR doesn't read "value in in".
- **Contrast:** All Stage 5 pairs measured ≥ AA (see Working credit).
- **Motion:** `prefers-reduced-motion` honored globally.
- **Touch:** Unit/value buttons hit 44px height at mobile width; **two gaps** — slider hit-area (UX-503) and unit-button width (UX-504).

---

## Severity rollup (this role)

```
Blocker:  0
Critical: 0
Major:    0
Minor:    4   (UX-501, UX-502, UX-503, UX-504)
Nit:      1   (UX-505)
-----
Total:    5
```

## Verdict

**Stage 5's slider/numeric/units UX is release-quality in substance.** No Blocker, Critical, or Major. The hard parts — AA contrast on the accent, the no-flash model swap, a shared single-source units store that converts every surface at once, and a properly-wired accessible numeric editor — are all done correctly and verified on the running app. The five findings are all polish: ragged inch precision (UX-501/502), two touch-target gaps that only bite hybrid/narrow-fine-pointer cases (UX-503/504), and an optional feedback nicety (UX-505). Against a "zero findings" beta bar these five Minors/Nit should be cleared, but none change the shape of the feature and none block. Recommend fixing UX-501–504 (all small, mostly one-liners) and adding a reachable demo scenario for the no-slider state so it can be walked, not just read.
