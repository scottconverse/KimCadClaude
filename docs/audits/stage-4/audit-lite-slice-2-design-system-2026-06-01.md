# Audit Lite — Stage 4, Slice 2: Workshop design system + topbar + landing
**Date:** 2026-06-01
**Scope:** The static design layer — the Workshop token set + self-hosted latin-only fonts + base reset (`styles.css`), the topbar chrome (`Topbar.tsx`), and the landing screen (`Landing.tsx`), composed by `App.tsx`. Build hygiene (`prebuild` clean) and two build-output tests. Branch `stage-4-react-spa-shell`. (No flow wiring, no 3D viewport — Slices 3–5.)
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. Token and typography fidelity against `docs/design/prototype/jsx` is strong (Workshop palette exact, 58px topbar, 32px/r9 logo cube, wordmark and hero-title type ramps match), fonts are correctly self-hosted latin-only (3 woff2, no orphans), the build-hygiene trap from Slice 1 (W3) is resolved, and accessibility (focus-visible + focus-within, aria-hidden glyphs, single h1) is sound. One fidelity Nit (button/chip metrics drifting from the prototype's exact values) was found and fixed in this pass. Full suite + ruff + npm audit green.

## Severity rollup (round 1)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 1

## Severity rollup (round 2 — after fix)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0 → **0/0/0/0/0, gate cleared**

## Dimensions checked
- **UX / visual fidelity:** styles.css vs the Workshop tokens in `data.jsx`/`styles.jsx` (static comparison — see the screenshot judgement call below).
- **Correctness:** @font-face (families, weight ranges, unicode-range, format), build hygiene.
- **Tests:** the two new build-output assertions; ran the full suite.
- **Docs:** no behavior/API change — README/ARCHITECTURE from Slice 1 still accurate. N/A this slice.
- **Runtime:** the served shell + bundled assets are exercised by test_webapp's live-socket serve test; the CSS/fonts are verified present in the committed build.

## Findings

### UX-201 Nit: button/chip metrics drifted from the prototype's exact values
**Dimension:** UX
**Evidence:** `styles.jsx` defines `.kc-newbtn` as `font-size:12.5px; padding:8px 15px` and `.kc-chip` with `border:1px solid var(--hair-strong); font-size:13px` and a hover of `color:var(--accent)` (no background change). The Slice-2 `.kc-btn` shipped 13px / `padding:9px 15px`, and `.kc-chip` shipped a `--hair` border / 12.5px / a background-change hover.
**Why it matters:** Scott's stated target for Stage 4 is a pixel-faithful recreation; sub-pixel button/chip drift compounds across the many controls still to come, so the base needs to match now.
**Fix path:** Align `.kc-btn` to 12.5px / `8px 15px`; `.kc-chip` to a `--hair-strong` border, 13px, and an accent-text hover. **(Fixed in this pass; rebuilt + 45 web tests green.)**

## What's working
- **Workshop palette is exact:** every token in `styles.css :root` (`#f0ebe0 / #faf6ee / #f4eee2 / #272219 / #6f6857 / hair(-strong) / #14171c / #c8623a`) matches `data.jsx` `KC_DIRECTIONS.workshop` character-for-character; `test_built_css_carries_workshop_tokens` proves the accent + viewport survive minification.
- **Chrome type/metrics match:** 58px topbar, 32×32 r9 accent logo cube, wordmark (display 21px / `Kim` 600 ink + `Cad` 800 accent / `-0.015em`), hero title `clamp(30px,4.4vw,47px)` 700 — all match `styles.jsx`. The landing's input card uses the design's hero-input shadow (`0 18px 50px -22px rgba(0,0,0,.4)`).
- **Fonts done right for offline + size:** hand-written latin-only @font-face reference the @fontsource `files/*.woff2`, so the build bundles exactly 3 woff2 (verified) instead of 11; correct family names, weight ranges (Bricolage 200–800 / Hanken 100–900 / JetBrains 100–800), `font-display:swap`, and a latin unicode-range that covers every glyph the UI uses (English + `·` + em-dash + curly apostrophe; the send arrow is an inline SVG, not a glyph). No tofu risk, no CDN.
- **Build hygiene W3 resolved:** the `prebuild` `rimraf ../src/kimcad/web/assets` clears stale assets each build while `emptyOutDir:false` preserves `web/vendor/` and `web/index.html` — verified a rebuild leaves exactly {3 woff2, index.css, kimcad.js} with no orphans, and vendor + index.html survive.
- **Accessibility:** the textarea's suppressed outline is replaced by an accent `:focus-within` ring on its card; `:focus-visible` rings on buttons/chips; all decorative SVGs `aria-hidden`; the icon-only Settings button has `aria-label`; one `h1`. Muted `#6f6857` on the sand surfaces clears WCAG AA (~4.6:1).
- **Green:** ruff clean; full `pytest tests` = 398 passed incl. live; web tests 45 passed; `npm audit` = 0.

## Watch items
1. **W4 — pixel-level visual review at the audit-team gate (the one real gap).** No browser screenshot was taken: 4 Chrome instances are connected and driving one needs an interactive pick that would interrupt the autonomous build and touch real sessions. Static token/layout fidelity was verified here, but a true pixel-match against `docs/design/screens/06-landing.png` + the prototype belongs to the Stage-4 `audit-team` UI/UX role. Acceptable to defer — **but it must actually happen before Stage 4 merges** (UX is the #1 priority). Recorded so it isn't lost.
2. **W5 — inert-but-enabled chrome must be wired before merge.** "Design it", the example chips, "New design", and Settings render enabled but have no handlers yet (chosen over disabled for visual fidelity). Acceptable for an intermediate slice; the design→flow wiring in Slices 4–5 makes them live, and none of this may reach a user-facing build inert.
3. **W6 — component-level JS tests (vitest).** Python build-output assertions can't execute React. When interactive logic lands in Slice 4, add a vitest + jsdom setup (and wire it into `scripts/ci.sh`) so component/flow behavior is gated, not just the build output.

## Escalation recommendation
No escalation needed. A clean, well-scoped design-system slice with exact token fidelity, correct offline fonts, and sound a11y; the single Nit is fixed. The deferred pixel-level visual review (W4) is the natural job of the Stage-4 audit-team gate, not a reason to escalate now.
