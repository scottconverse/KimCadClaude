# UI/UX Re-Audit (Closure) — KimCad Stage 5 remediation

**Re-audit date:** 2026-06-02
**Role:** Senior UI/UX Designer
**Posture:** Balanced
**Scope:** Verify closure of the 7 UX findings from `../audit-team-stage-5-2026-06-02/02-uiux-deepdive.md` (0 Blocker / 0 Critical / 0 Major / 3 Minor / 4 Nit) and review the UX delta for new issues.
**Remediation diff (uncommitted):** `frontend/src/{App,api,components/RightPanel}.tsx`, `frontend/src/styles.css`, `frontend/src/App.test.tsx`, `frontend/src/components/RightPanel.test.tsx`, `src/kimcad/templates.py`, plus the rebuilt `src/kimcad/web/assets/*` (source + build are in sync — the live demo reflects the fix).

---

## TL;DR

All 7 findings are **closed**. The marquee touch-target fix (UX-001) is correct: the slider gets a 44px coarse-pointer hit box via vertical-only `padding-block` + `background-clip: content-box`, and — the key risk the original fix-path flagged — the `--pct` track-fill gradient still aligns, because the padding is purely vertical while the gradient is horizontal. Copy fixes (UX-002/005/006) land warm and honest; the LLM note correctly does **not** promise a chat-refinement path that isn't wired. The min-dwell (UX-003) is correctly seq-guarded and cannot stick the note on or flicker. The per-axis chip (UX-004) renders only for dimensional params and does not wrap or overflow the label row. Nothing new found. **Roll-up: 0 / 0 / 0 / 0 / 0.**

## Severity roll-up (re-audit)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## Per-finding closure

### [UX-001] Slider mobile touch target — CLOSED
`styles.css:586-603` adds `.kc-range` to the `@media (pointer: coarse)` block: `box-sizing: border-box; height: auto; min-height: 44px; padding-block: 18px; background-clip: content-box;` plus a 28px `::-webkit-slider-thumb` / `::-moz-range-thumb`.
**Gradient-alignment risk (the original fix-path's explicit verify item): resolved — NOT risky.** The track-fill gradient is `linear-gradient(to right, accent var(--pct), hair var(--pct))` (`styles.css:854-867`) — a purely **horizontal** stop driven by `--pct`. The remediation adds **`padding-block`** (top/bottom only; computed `padding-left/right: 0`) — so it changes vertical geometry only and leaves the horizontal gradient stops untouched. `background-clip: content-box` clips the painted track **vertically** into the content box, keeping it thin (measured ~26px content band inside a ~62px box on a forced-coarse clone; the painted rail is the base 5px rule, fattened by clip, never the full 44px). `--pct` is computed as linear `(value-min)/(max-min)*100` (`RightPanel.tsx:31-32`) — independent of thumb width — so the fill tracks the value exactly as before. Verified live: gradient stop held at `29.1667%` at both desktop and mobile widths; horizontal padding is 0.
*Minor cosmetic note (not a finding):* fattening the thumb 17px→28px slightly widens the pre-existing fill-vs-thumb-center divergence at the track extremes — but that divergence exists in the base design, is coarse-pointer-only, and is not introduced by the padding/clip change. Not a regression.

### [UX-002] Re-render error copy — CLOSED
`RightPanel.tsx:135-137`: now leads "That change didn't render — your last version is still here. Nudge a slider to try again." with the raw detail demoted to a muted `.kc-error-detail` span (`styles.css:901-905`, `color: var(--kc-muted); font-size: 11px`). Warm voice ✓, reassurance that the last version is intact ✓ (which is true — the viewport keeps the last mesh), raw detail demoted out of the primary sentence ✓. Test updated to assert all three (`RightPanel.test.tsx`).

### [UX-003] "Re-rendering…" min-dwell — CLOSED
`App.tsx:62, 73-84`: `RERENDER_MIN_DWELL_MS = 350`; on the latest re-render the flag is cleared either immediately (≥350ms elapsed) or via a `setTimeout`, **re-guarded** by `seq === renderSeq.current` inside the callback.
- **Can't stick on:** a stale (superseded) re-render's `finally` fails the seq guard and is a no-op — it neither schedules nor clears. Only the latest owner clears the flag, and `handleSubmit`/`handleNewDesign` force-reset it (`App.tsx:44, 94`). No path leaves it permanently true.
- **Can't flicker:** the 350ms floor is the anti-flicker mechanism. A new test (`App.test.tsx`, out-of-order discard) confirms the seq guard drops a stale late response.

### [UX-004] Per-axis chip restored — CLOSED
Full chain present: `templates.py parameters()` emits `axis` only when `p.bbox_axis is not None` → `("X","Y","Z")[p.bbox_axis]` (`templates.py:187-188`); `api.ts ParamSpec` adds `axis?: string`; `RightPanel.tsx:38` renders `<i className="kc-axis">`; `styles.css:826-835` defines `.kc-axis`, and `.kc-plabel > span:first-child` becomes `display:flex; align-items:center; gap:6px`.
**Renders only for dimensional params — verified live** on the demo `snap_box` (4 sliders): Width→X, Depth→Y, Height→Z each carry a chip; **Wall thickness has no chip** (it has no `bbox_axis`). Confirmed in the DOM at mobile 375.

### [UX-005] LLM read-only copy — CLOSED
`RightPanel.tsx:158-160`: "This part was generated directly rather than from a parametric template, so it has no preset sliders — but you can still slice and download it, or describe a change to start a new version."
**Honest:** it does **not** promise an inline chat-refinement of the LLM part (the original fix-path made that conditional on the path being wired — it isn't, so the remediation correctly omitted it). "Describe a change to start a new version" points to the existing re-describe / new-design flow, not a nonexistent slider/chat-edit of the current part.

### [UX-006] "Updating…" → "Re-rendering…" — CLOSED
`RightPanel.tsx:114` now reads "Re-rendering…", matching the subtitle's vocabulary. Verified absent in the built `Updating` string; tests updated.

### [UX-007] focus-visible on pointer-drag — CLOSED (verification-only, correct call)
No code change was the right call: the slider ring uses `:focus-visible` (`styles.css`), the correct keyboard-only selector — a mouse-drag does not persist the ring by construction. The original finding was explicitly verification-only ("code is correct by construction"); no remediation was warranted.

## New-issue review (UX delta)

- **Min-dwell × rapid drags:** safe. Each debounced re-render bumps `renderSeq`; superseded calls no-op, the latest owns the flag, the dwell `setTimeout` re-checks the seq. The dwell timer isn't explicitly cleared, but App is the SPA root (never unmounts) and the seq guard makes a late fire a no-op — no leak, no stuck note. No finding.
- **44px padding — layout shift / overlap:** none. The coarse block applies only on `pointer: coarse`; desktop (1280) measured the unchanged 5px track (no padding). The 44px box is vertical growth on the slider row only; the row already stacks the label/value line above the input, so the taller hit box pushes nothing into overlap. No finding.
- **Axis chip wrap/overflow:** none. Live at mobile 375: label row height stayed 19px, chip is 15×17px inline (gap 6px), `labelWiderThanRow: false` on every row — no wrap, no overflow of the label/value row. No finding.

## What was / wasn't render-checked

- **Render-checked (live, `--demo` server on :8784):** SPA loaded, designed a box → 4 sliders; **UX-004** axis chips X/Y/Z on dims, none on Wall (DOM-verified); **UX-001** geometry — desktop 5px thin track / no padding, gradient stop `29.1667%`; mobile forced-coarse clone confirmed `padding-block:18px`, `padding-left/right:0`, `background-clip:content-box`, painted band stays thin, gradient stop unchanged; **UX-006** built copy; label-row layout (no wrap/overflow). All 36 frontend tests pass; 112 templates-related Python tests pass.
- **Not directly render-checked:** the preview harness emulates viewport size but **not** `pointer: coarse`, so the coarse `@media` block doesn't auto-apply at mobile width — UX-001 was verified via a forced-coarse clone of the exact rule values + CSS reasoning (stated plainly, per protocol). The re-render **error** state (UX-002) and the **LLM read-only** state (UX-005) aren't reachable from the deterministic demo box, so they were verified from source + the committed build JS. JPEG screenshot tool remains broken (known) — all rendered findings are DOM / computed-style / bbox.

## Final rollup

**0 Blocker / 0 Critical / 0 Major / 0 Minor / 0 Nit.** All 7 findings closed; no new UX issues. Gate bar met from the UI/UX lens.
