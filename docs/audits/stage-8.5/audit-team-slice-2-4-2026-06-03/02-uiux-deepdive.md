# UI/UX Deep-Dive — Stage 8.5 Slices 2–4

**Role:** Senior UI/UX Designer
**Scope:** Live design refinement — conversation thread + refine input (Slice 2), version timeline / undo / redo / compare (Slice 2), inline numeric editing (Slice 3), mm/inch units toggle (Slice 4)
**Date:** 2026-06-03
**Posture:** Balanced. UI/UX is the product's #1 acceptance gate.

---

## What I checked rendered vs. static

**Rendered (live, against the model-free demo server at http://localhost:8765, serverId driving a real headless browser via DOM / computed-style / getBoundingClientRect inspection):**

- Landing → submitted `box` via the real UI → drove into the workspace with 4 live sliders (80/60/40/2 mm).
- Conversation thread (4 turns), refine input (placeholder, aria-label, disabled-send state, submit).
- Version rail with 2 versions: pills, active highlight, aria-current, Undo/Redo enable/disable, Compare card injection.
- Inline numeric edit: open editor, type, out-of-range validation (role=alert, aria-invalid, aria-describedby), Escape cancel.
- mm/in toggle cross-card sync — confirmed BOTH the Parameters readout AND the Printability dims table (headers + values) update from one toggle, plus slider `aria-valuetext`.
- **The 375px header-overflow question** — measured at a TRUE 375px CSS viewport (`document.documentElement.clientWidth === 375`) with the transient "Re-rendering…" note PRESENT, sampled across 12 frames during a live re-render.
- Focus-visible rings on all five new control types (computed outline).
- Touch-target sizes at 375px. Contrast ratios computed from live computed colors. Console checked (clean).

**Static only (read, not driven):**

- Shift+Enter-newline vs Enter-submit branch (read in `ChatPanel.handleKeyDown` — correct; the headless env can't cleanly exercise React synthetic keyboard composition, but the code path is unambiguous).
- The dims-table off-axis "⚠" + `kc-dim-off` class (read; confirms not color-only).
- Cross-tab `storage` event sync in `useUnits` (read; single-tab env).

**Environment limitations (NOT gate failures):**

- The JPEG screenshot tool is known-broken in this environment — all visual evidence is DOM / computed-style / bounding-box, not pixels. Stated per instructions.
- The headless preview reports `pointer: fine` and `window.innerWidth` is unreliable (stuck at 427 regardless of resize); I used `document.documentElement.clientWidth` as the source of truth, which tracked the resize correctly. Because the env is `pointer: fine`, the app's `@media (pointer: coarse)` touch-target bumps did NOT apply during measurement — see UX-002 for what that does and does not change.

---

## Headline answer: the 375px header overflow is NOT real

At a verified 375px CSS viewport with the "Re-rendering…" note present (12 sampled frames during a live re-render):

| Measurement | Value |
|---|---|
| `document.documentElement.clientWidth` | **375px** |
| Parameters card inner header width (`hdClientW`) | **315px** |
| Header `scrollWidth` | **315px** → `hdOverflows: false` |
| Title "Parameters" box | x 30 → 116 (w 86) |
| `hd-right` cluster (note + toggle) | x 186 → 345 (w 160) |
| "Re-rendering…" note box | x 186 → 276 (w 90) |
| Card right edge | 361 (hd-right right 345 < 361 → no card overflow) |
| Min gap between title and hd-right | **70px** |
| Title overlaps hd-right? | **false** (all 12 frames) |
| hd-right overflows card? | **false** (all 12 frames) |

The flex header (`justify-content: space-between`, `gap: 8px`, `hd-right` is `flex: none`) fits title + "Re-rendering…" + mm/in toggle inside 315px with ~70px of slack. No clipping, no overflow, no horizontal scroll, no overlap. **This concern is cleared.**

---

## Findings

### UX-001 — Active-fill controls fail WCAG AA contrast (white on `--kc-accent`)
- **Severity:** Major
- **Category:** Accessibility / Color system
- **Evidence (rendered):** The active mm/in toggle button paints `#fff` on `--kc-accent` (`#c8623a`) — computed `color rgb(255,255,255)` on `background rgb(200,98,58)` → **3.99:1**. The label is 11.5px ("mm"/"in") = normal text, which requires 4.5:1. Same `#fff`-on-`#c8623a` pairing is used by the active version pill (`v2`, 12px) and the user chat bubble (`.kc-msg-user`, 13.5px) — all confirmed via computed style, all normal-size, all ~3.99:1. `--kc-on-accent` resolves to `#fff`.
- **Why this matters:** The unit toggle and version pills are the two brand-new interactive surfaces of Slices 2 and 4. Their *active* (selected) state — the one that tells the user "you are here" / "this is the current unit" — is exactly the state that misses AA. Low-vision and bright-sunlight users (a real persona for a maker tool used at a workbench) will struggle to read the selected state.
- **Blast radius:**
  - Adjacent code: token-level. `.kc-unit-btn-active`, `.kc-version-pill-active`, `.kc-msg-user` all rely on `--kc-accent` + white. Anything else solid-filling `--kc-accent` with white text inherits the miss (audit `.kc-btn-accent`, the "Design it" / "Send" buttons — those are larger but worth a sweep).
  - Shared state: the `--kc-accent` / `--kc-on-accent` design tokens in `styles.css`.
  - User-facing: selected-state legibility on toggle, pills, and the user's own chat bubbles.
  - Migration: none — a token-value change.
  - Tests to update: none known (no contrast tests exist — see Test role).
- **Fix path:** Use `--kc-accent-strong` (`#b1542f`, ~4.6:1 on white) as the fill for *small* white-on-accent labels (toggle, pills), or darken `--kc-accent` itself to `#bd5a34`-ish and re-verify the gauge/CTA. Keep `#c8623a` for large text / decorative fills only. Recommend a single token `--kc-accent-text-safe` for "solid fill that carries small white text."

### UX-002 — Touch targets below minimum on the new controls; two new controls have NO coarse-pointer bump
- **Severity:** Major
- **Category:** Accessibility / Responsive
- **Evidence (rendered, 375px):** Measured heights — unit toggle buttons **35×22 and 25×22** ("in" is 25px wide), version pills **34×21**, version steps (Undo/Compare) **54×21 / 62×21**, inline value-edit button (`.kc-pval-btn`) **47×19**, Send **57×33**. The env is `pointer: fine`, so the app's coarse-pointer rules did not apply during measurement. Reading the CSS: `@media (pointer: coarse)` bumps exist for `.kc-version-pill` / `.kc-version-step` (`min-height: 36px`) and `.kc-refine-send` (`min-height: 44px`) — so on a real phone pills/steps reach 36px and Send reaches 44px. **But there is NO coarse-pointer rule for `.kc-unit-btn` or `.kc-pval-btn`** — on a real touch device the mm/in toggle stays ~22px tall and the click-to-edit value target stays ~19px tall.
- **Why this matters:** WCAG 2.5.8 (AA) sets a 24px target floor; 2.5.5 (AAA) and Apple HIG want 44px. The unit toggle at 22px fails even the relaxed 24px AA floor on touch. The inline-edit affordance is the *entire* Slice 3 interaction on mobile — a 19px tall tap target to open the numeric editor is a fat-finger trap. The 36px coarse bump on pills/steps is itself still under 44px, so even the "fixed" controls are borderline against HIG.
- **Blast radius:**
  - Adjacent code: `.kc-unit-btn`, `.kc-pval-btn` in `styles.css` need coarse-pointer minimums added; consider raising the existing 36px pill/step bump toward 44px.
  - User-facing: every mobile/tablet user toggling units or click-editing a value.
  - Migration: none.
  - Tests to update: none known.
- **Fix path:** Add `@media (pointer: coarse)` rules giving `.kc-unit-btn` and `.kc-pval-btn` `min-height: 44px` (and padding to match), and bump the pill/step minimum from 36px to 44px. Verify the header still fits at 375 after the bump (it has 70px of slack today, so a taller toggle is safe).

### UX-003 — Compare card shows the raw enum `pass` while the rest of the app says "Passed"
- **Severity:** Minor
- **Category:** Copy / Consistency
- **Evidence (rendered):** Clicked Compare on v1↔v2. The compare card's gate chips render literal lowercase **`pass`** (`textContent "pass"`, `text-transform: none`). The Printability card, for the same gate, renders **"Gate: Passed"** via the `gateLabel()` helper. `ChatPanel.CompareCard` uses `a.result.report?.gate_status` directly instead of `gateLabel()`.
- **Why this matters:** Two surfaces describing the same verdict with different words ("pass" vs "Passed") reads as unpolished and, for a `warn`/`fail` part, "fail" vs "Needs work" could under-communicate severity in the very card meant to help the user choose between versions.
- **Blast radius:**
  - Adjacent code: `CompareCard` in `ChatPanel.tsx`; reuse the existing `gateLabel()` / `gateTone()` from `designStatus.ts` already imported by `RightPanel`.
  - User-facing: the version-compare card only.
  - Migration: none.
- **Fix path:** Import and apply `gateLabel(gate)` for the chip text and `gateTone(gate)` for the class, matching the Printability badge. One-line-per-column change.

### UX-004 — Inch mode resolution is too coarse to edit thin features; displayed precision ≠ step precision
- **Severity:** Minor (borderline Major for a printability tool where wall thickness is nozzle-multiple-sensitive)
- **Category:** Interaction / Journey
- **Evidence (rendered):** Toggled to inches, opened the Wall-thickness editor. Display reads **"0.08 in"** (2 dp). The number input has `min 0.0314…`, `max 0.3149…`, `step 0.00787…` — i.e. min/max/step carry 4–5 dp while the *display* is rounded to 2 dp. 2 mm shows as 0.08 in; 0.08 in commits back to 2.032 mm (the no-op guard in `commitEdit` is what stops re-commit drift — good defense, confirmed in code). But the user-facing consequence stands: in inch mode a 2 dp readout for a 2 mm wall can't distinguish 0.078 in (1.98 mm) from 0.082 in (2.08 mm); one displayed increment (0.01 in) is ~0.25 mm and the rounding makes fine wall edits feel "stuck."
- **Why this matters:** Wall thickness is the dimension most tied to print success (nozzle multiples, e.g. 0.4/0.8/1.2 mm). A US maker who prefers inches gets a control that can't express those targets cleanly. The slider still works in mm under the hood, so it's a degraded-precision experience, not data loss.
- **Blast radius:**
  - Adjacent code: `formatDisplay` / `formatMm` 2-dp inch rounding in `RightPanel.tsx` and `useUnits.ts`.
  - User-facing: any sub-~5 mm dimension edited in inch mode.
  - Migration: none.
- **Fix path:** Either (a) show 3 dp for inch values under ~0.5 in (so 2 mm reads 0.079 in and a 0.4 mm step is visible), or (b) for sub-mm-critical params keep an mm readout in parentheses in inch mode (e.g. `0.08 in (2.0 mm)`). Recommend (b) for wall/clearance params — it keeps the print-critical truth visible without forcing the user to do mental math.

### UX-005 — Numeric-input aria-label reads "value in in" in inch mode
- **Severity:** Minor
- **Category:** Accessibility / Copy
- **Evidence (rendered):** In inch mode the inline editor's `aria-label` computes to **"Wall thickness value in in"** (the unit "in" concatenated after the preposition "in"). The template is `` `${spec.label} value${displayUnit ? ` in ${displayUnit}` : ''}` `` → "in in" when `displayUnit === 'in'`. In mm it reads fine ("value in mm").
- **Why this matters:** A screen-reader user editing a value in inches hears "wall thickness value in in" — momentarily confusing. Same doubling affects the slider `aria-valuetext`? No (that one is `"0.08 in"`, fine), and the unit tag `<i>in</i>` is visual-only. So the defect is isolated to the input's `aria-label`.
- **Blast radius:**
  - Adjacent code: the `aria-label` template in `SliderRow` (`RightPanel.tsx`).
  - User-facing: screen-reader users in inch mode only.
- **Fix path:** Spell out the unit for the inch case in the aria-label: `... value in inches` (and `... value in millimeters` for symmetry), decoupling the spoken label from the abbreviated visual tag.

### UX-006 — Compare card states two versions but surfaces no diff
- **Severity:** Minor (data-shaped; verify with a real model)
- **Category:** Journey
- **Evidence (rendered):** Compare v1↔v2 rendered two columns: both "Demo part for: …", both gate `pass`, both "Readiness 92/100." Nothing is highlighted as *changed*. This is partly the demo's identical data, but structurally the card shows two summaries side by side with no delta emphasis (no "+2 mm taller," no changed-dimension call-out, no winner indication).
- **Why this matters:** "Compare" implies "tell me what's different." Two near-identical cards make the user do the diffing. For the core "which version do I keep?" decision this is a soft dead-end — the user clicks Compare, learns little, and falls back to eyeballing the viewport.
- **Blast radius:**
  - Adjacent code: `CompareCard` in `ChatPanel.tsx`; would consume `plan.target_bbox_mm` / `report.dims` deltas.
  - User-facing: the version-decision journey.
  - Migration: none.
- **Fix path:** Compute and emphasize the delta — e.g. a middle column or inline badges ("Z 40 → 52 mm", "Readiness +0", color the improved/regressed metric). Even a one-line "What changed: height 40 → 52 mm" pulled from the bbox diff would convert Compare from a restatement into a decision aid. Confirm against a real model run before sizing.

### UX-007 — Error microcopy in inline edit is a bare range, not a sentence (alert with no verb)
- **Severity:** Nit
- **Category:** Copy / Accessibility
- **Evidence (rendered):** Typing 300 into a 10–250 field shows `role="alert"` text **"10–250 mm"**. With `aria-invalid` and `aria-describedby` correctly wired (verified), a screen reader announces "10 to 250 mm" with no statement of what's wrong.
- **Why this matters:** It works for sighted users via proximity (red border + range under the field), but the alert announces a bare range with no "out of range" framing. Minor, since the visual context carries it.
- **Fix path:** "Enter 10–250 mm" or "Must be 10–250 mm" — adds the missing verb so the alert is self-describing. Keep it short to preserve the no-overflow layout (the tooltip currently fits inside the panel, right edge 1236 < 1280 at desktop — verified).

---

## What's working (specific credit)

- **The shared-store units architecture is the standout.** Toggling mm↔in fires ONE state change and instantly, correctly updates the Parameters readouts, the slider `aria-valuetext`, the inline-editor min/max/step/seed, the dims-table *headers* (`Target (in)` / `Actual (in)`) AND the dims-table *values* — verified live (80 mm → 3.15 in in both cards from a single click). `useUnits` backing this with `useSyncExternalStore` instead of per-component `useState` is the right call and visibly pays off in cross-card consistency. No drift observed.
- **Version rail state logic is correct and accessible.** `role="navigation"`, `aria-current="true"` on the active pill, descriptive `aria-label`s ("Version 2: make it taller"), Undo correctly disabled at v1 (opacity 0.35), Redo correctly hidden at the latest version and shown after stepping back, Compare labeled with the actual version numbers. Rail correctly absent with a single version. All verified live.
- **Inline-edit validation a11y is genuinely good.** Out-of-range input gets `aria-invalid="true"`, `aria-describedby` pointing at a `role="alert"` message, a red border, and the error tooltip stays inside the panel — a complete, accessible error state on a brand-new control.
- **Focus-visible is handled everywhere new.** All five new control types (unit btn, pill, step, refine textarea, value button) render a ~2px accent `:focus-visible` outline — verified via computed style.
- **Refine input details are considered:** disabled Send when empty, clear aria-label, a genuinely helpful placeholder with examples ("make it 10mm taller", "add mounting holes"), and a context-aware placeholder for the clarification case (read in code). Enter-submits / Shift+Enter-newline is implemented correctly.
- **Color is never the sole signal where it counts:** off-axis dims carry a "⚠" glyph plus the `kc-dim-off` class, and risk tiers carry an `.kc-sr-only` severity word ("Critical risk" / "Warning") — both verified in code, the right instinct for colorblind safety.
- **The 375px header — the thing we worried about — is clean** with 70px of slack even with the "Re-rendering…" note present.
- **Console is silent** through the entire flow (design, refine, version switch, compare, toggle, edit, validation). No runtime noise.

---

## Severity rollup (this role)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 4 |
| Nit | 1 |
| **Total** | **7** |

**Blockers:** none.

**Cross-cutting:** UX-001 (accent contrast) and UX-002 (touch targets) are both *token/system* issues, not one-off — they touch the unit toggle, version pills, chat bubbles, and the inline-edit affordance together. Fixing them at the token / shared-media-query level resolves several surfaces at once and is the highest-leverage UI work in these slices. UX-003/005/006/007 are localized copy/precision polish.
