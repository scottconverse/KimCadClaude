# UI/UX Re-Audit — ROUND 2 (closure) — KimCad Stage 8.5 (Usability) stage gate

**Role:** Senior UI/UX Designer (audit-team, 5-role) — independent round-2 re-verify after second-tier UI fixes
**Date:** 2026-06-05
**Scope:** repo `C:\Users\scott\dev\kimcad`, branch `stage-8.5-usability` @ `a6dff43` (second-tier remediation head; round-1 re-audit was at `6c98674`)
**Method:** audit-only, source-based. Verified the two round-1 NEW findings (NEW-1, NEW-2) against CURRENT `frontend/src/styles.css` + components, spot-checked the original 18 UX fixes still hold, and swept for regressions in a11y/hierarchy. Ran the frontend unit suite: **262 vitest pass (23 files)**.

---

## Verdict at a glance

Both round-1 NEW findings are **RESOLVED** in current code, fixed exactly where they were flagged, using the app's existing token system rather than parallel machinery. No residual on either. The original 18 UX fixes all still hold. The regression sweep is clean — no new a11y, hierarchy, state, or colour-only-cue issue introduced by the touch-up pass.

**Final UI rollup: 0 / 0 / 0 / 0 / 0** (Blocker / Critical / Major / Minor / Nit).

---

## NEW-1 — mobile CTA branded focus-visible ring — RESOLVED

**Round-1 finding (Minor):** `.kc-mobile-cta` had no `:focus-visible` rule, so the primary mobile print action fell back to the browser's default focus outline — the lone interactive control not matching the app's accent-ring system.

**Round-2 verification:**
- `styles.css:1982-1985` now defines, inside the `≤1000px` media block:
  ```css
  .kc-mobile-cta:focus-visible {
    outline: 2px solid var(--kc-accent);
    outline-offset: 2px;
  }
  ```
- The comment at `styles.css:1980-1981` explicitly tags it `UX-NEW-1` and notes it "matches `.kc-btn`."
- `var(--kc-accent)` is the real brand terracotta token (`#c8623a`, defined `styles.css:56`) — the same token the app-wide focus ring uses (`styles.css:148`: `outline: 2px solid var(--kc-accent)`). So this is a genuinely branded ring at the system's `2px / offset 2px` spec, not an undefined-var typo and not a thinner ad-hoc treatment.
- The CTA JSX (`Workspace.tsx:118-128`) is a real `<button type="button">`, keyboard-focusable, gated on `result?.has_mesh`, scrolling to `#kc-export-card`. Unchanged and correct.

**Residual: none.** The fix is on the right element, in the right (mobile-only) cascade scope, at the right contrast. The mobile primary action now carries the same focus indicator as every other control.

## NEW-2 — duplicate `.kc-rec-arrow` rule (dead `font-weight: 800`) — RESOLVED

**Round-1 finding (Nit):** `.kc-rec-arrow` was declared twice — `styles.css:1481` (`font-weight: 800`, pre-fix) and again at `styles.css:1862` (`font-weight: 600`, the UX-017 fix). The later rule won, but the stale earlier declaration was a trap for a future editor.

**Round-2 verification:**
- There is now **exactly ONE** `.kc-rec-arrow` rule, at `styles.css:1481-1486`, with `font-weight: 600` and an inline comment `/* UX-017: lighter (was 800) */`.
- The old duplicate at line 1862 is gone — that line is now `.kc-refine-hint` (an unrelated UX-003/010 rule). A repo-wide grep for `.kc-rec-arrow` returns only the single styles.css declaration (plus the one consuming `RightPanel.tsx:474`).
- The four remaining `font-weight: 800` occurrences in styles.css (lines 172, 1295, 2050, 2498) belong to unrelated selectors — none is the rec-arrow.

**Residual: none.** Single source of truth restored; the arrow renders at the intended lighter weight.

---

## Original 18 UX fixes — spot-check still holds

Confirmed the key remediated surfaces are present and wired in current code at `a6dff43`:

- **Right-column hierarchy** — `RightPanel.tsx:505` `kc-card kc-card-readiness`, `:533` `kc-card kc-card-report`; per-card accent modifiers at `styles.css:1852-1859` (verdict card carries the weight). Intact.
- **Printability icon-tile checks** — `RightPanel.tsx:573-583` renders `<ul className="kc-checks">` with `kc-check-ico` shape tile (`⚠`/`✓`) PLUS `kc-sr-only` status word ("Needs review:" / "OK:"). Non-colour cue + SR text intact.
- **Refine chips** — `ChatPanel.tsx:252-258` `kc-refine-chips` group (`role="group"`, `aria-label="Quick refinements"`) of `kc-chip kc-refine-chip` buttons. Intact.
- **Printer chip** — `Topbar.tsx:88-97` non-interactive `<span className="kc-printer-chip">` with descriptive `aria-label` (name + build volume) and `aria-hidden` dot — a readout, not a menu. Intact.
- **Mobile CTA** — `Workspace.tsx:117-129` sticky CTA gated on `has_mesh`, scrolling to the real `#kc-export-card`. Intact (and now with NEW-1 focus ring).
- **"?" Help button** — `Topbar.tsx:139-147` `kc-btn kc-btn-ghost kc-help-btn` with `aria-label="Keyboard shortcuts"` + `title`, wired to `onShowShortcuts`. Inherits the branded `.kc-btn:focus-visible` ring. Intact.

## Regression sweep — explicit clears

- **A11y contracts preserved:** printer-chip `aria-label`, help-button `aria-label`, check-tile `kc-sr-only` words, decorative `aria-hidden` on dot/ico/arrow all present and unchanged.
- **Hierarchy:** accent treatments remain per-card modifiers — no column wash, verdict card still heaviest.
- **Focus rings:** every interactive control (buttons, chips, help, saved, AND now the mobile CTA) carries a branded accent `:focus-visible` ring. No control left on the browser default.
- **Tests:** 262 vitest pass (23 files), up from 257 at round-1 — the second-tier pass added coverage and broke nothing.
- **Working tree:** clean at `a6dff43` (no uncommitted drift).

No Blocker / Critical / Major / Minor / Nit introduced or carried.

---

## Final UI rollup & gate recommendation

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |
| **Total** | **0** |

**NEW-1: RESOLVED. NEW-2: RESOLVED. Residual: none.**

**Round-2 UI/UX closure: PASS — 0/0/0/0/0.** All 18 original UX findings plus both round-1 NEW findings are now fully resolved in current code; the UI lane clears the bar with no open items.
