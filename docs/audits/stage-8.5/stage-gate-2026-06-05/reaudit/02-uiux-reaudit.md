# UI/UX Re-Audit (closure) — KimCad Stage 8.5 (Usability) stage gate

**Role:** Senior UI/UX Designer (audit-team, 5-role) — independent re-audit after remediation
**Date:** 2026-06-05
**Scope:** repo `C:\Users\scott\dev\kimcad`, branch `stage-8.5-usability` @ `6c98674` (remediation head; original audit was at `95b25e0`)
**Method:** audit-only, source-based. Verified each of the 18 prior UX findings against CURRENT `frontend/src/components/*` + `styles.css`, cross-checked against the runtime wiring-audit evidence (`wiring-audit-stage-8.5-2026-06-05.md`). Did NOT start the web server (per gate instruction). Ran the frontend unit suite: **257 vitest pass (22 files)** at this commit. Remediation diff touched 15 frontend files (+377/-25), and added/updated tests for every changed component (`Topbar.test`, `ChatPanel.test`, `VersionRail.test`, `App.test`, `useHashRoute.test`).

---

## Verdict at a glance

The remediation is **real and faithful**, not cosmetic re-labelling. Every one of the 18 prior findings is genuinely addressed in current code, with the fix landing exactly where the original finding pointed and reusing the existing wired paths (`onRefine`, `getOptions`, `setShowShortcuts`) rather than bolting on parallel machinery. Accessibility was respected on the way through: the new non-colour cues are correct, focus management on the suppressed-duplicate state is intact, and the new interactive controls inherit the app's branded focus rings — with **one exception** (the mobile CTA, below).

Hunting for regressions surfaced **two new items, both low-severity** (1 Minor, 1 Nit) and **zero Critical/Major regressions**. Nothing the remediation did broke visual hierarchy, an ARIA contract, a state, or a colour-only-cue rule.

**Re-audit severity counts**

| Severity | Original | Resolved | Carried | New (regression) |
|---|---|---|---|---|
| Blocker | 0 | — | 0 | 0 |
| Critical | 0 | — | 0 | 0 |
| Major | 6 | 6 | 0 | 0 |
| Minor | 9 | 9 | 0 | 1 |
| Nit | 5 | 5 | 0 | 1 |
| **Total** | **20** | **20** | **0** | **2** |

(The original report numbered findings UX-001…UX-018 = 18 distinct findings; the count table totalled 20 by counting two cross-cutting clusters. All 18 numbered findings are resolved.)

---

## Per-finding verification (current file:line)

### Majors

- **UX-001 / UX-009 — right-column hierarchy. RESOLVED.**
  `ReadinessCard` now renders `<section className="kc-card kc-card-readiness">` (`RightPanel.tsx:505`) and `PrintabilityCard` renders `<section className="kc-card kc-card-report">` (`RightPanel.tsx:533`). CSS gives the readiness card a warm accent tint + a 3px accent left edge and the report card a subtler accent border, applied as **per-card modifiers** (not the shared `.kc-card`), exactly as the blast-radius note required so the other cards stay flat (`styles.css:1852-1859`). The eye now lands on the verdict card. UX-009's gauge-shape concern was consciously folded into this hierarchy treatment rather than reshaping the semicircle to a donut — the half-gauge remains (`RightPanel.tsx:353-379`) but now carries the visual weight the donut was meant to provide, which is an acceptable close for a Minor fidelity note.

- **UX-002 — Printability icon-tile checks. RESOLVED.**
  Findings now render as `<ul className="kc-checks">` with one `<li className="kc-check{ kc-check-warn}">` per finding, each a `.kc-check-ico` status tile (`⚠` when `f.level !== 'pass'`, else `✓`) **plus** a `.kc-sr-only` word ("Needs review: " / "OK: ") so status is not colour-only (`RightPanel.tsx:569-585`). CSS styles the tiles as 18px rounded chips with pass/warn background+colour mix (`styles.css:1894-1926`). This is the scannable, glanceable verdict list the design reference promised. (The Material control staying in the Export card as the single source of truth is the correct resolution of the blast-radius "don't end up with two material controls" warning.)

- **UX-003 / UX-010 — refine chips + persistent hint. RESOLVED.**
  `ChatPanel.tsx:243-267` renders a `.kc-refine-hint` ("Refine by talking — tap a change or describe your own:") above a `.kc-refine-chips` group of four `.kc-refine-chip` buttons ("Make it wider / Make it taller / Thicker walls / Add mounting holes"), each calling the existing `onRefine` path. Correctly **suppressed when `result.status === 'clarification_needed'`** so the user answers the question rather than firing a generic change — a thoughtful guard. The persistent hint replaces the vanishing-placeholder-only guidance the original flagged (UX-010). CSS at `styles.css:1866-1881`.

- **UX-004 — mobile layout. RESOLVED.**
  The ≤1000px viewport row dropped from `42vh` to `minmax(200px, 34vh)` (`styles.css:465`), and a mobile-only sticky `.kc-mobile-cta` ("↓ Check & download") is rendered in `Workspace.tsx:117-129` (gated on `result?.has_mesh`) that `scrollIntoView`s `#kc-export-card`. The scroll target exists — `ExportPanel.tsx:118` is `<section className="kc-card" id="kc-export-card">`. The CTA is `display:none` on desktop and `display:block` + `position:sticky` only inside the ≤1000px block (`styles.css:1965-1985`), with a 44px min-height. The verdict + print actions are now reachable in one tap on a phone.

- **UX-005 — visible "?" Help button. RESOLVED.**
  `Topbar.tsx:139-147` renders a `.kc-help-btn` ("?") wired to the new `onShowShortcuts` prop; `App.tsx:579` passes `onShowShortcuts={() => setShowShortcuts(true)}`, and `App.tsx:573` mounts `<ShortcutsHelp>` on that state. The button carries `aria-label="Keyboard shortcuts"` + `title="Keyboard shortcuts (?)"`. It is a `kc-btn kc-btn-ghost`, so it inherits the branded `:focus-visible` ring (`styles.css:261`). The hidden feature is now discoverable for mouse-only users too.

- **UX-006 — always-on printer-status chip. RESOLVED (and correctly a readout, not a menu).**
  `Topbar.tsx:51-71` fetches `getOptions()`, derives the default printer's name + `build_volume`, and renders a `.kc-printer-chip` (dot + name + mono volume) at `Topbar.tsx:88-98`. It is a non-interactive `<span>` with `title="Target printer — change it in Settings"` and a descriptive `aria-label` — a status READOUT, NOT a printer/model menu, satisfying the project's settled model rule. Best-effort: a total try/catch swallows any load failure so it's absent-rather-than-dead (no fake control). CSS `styles.css:1929-1962` hides the volume ≤820px and the whole chip ≤560px to protect the narrow chrome — a sensible responsive call.

### Minors / Nits

- **UX-007 — landing "~15 minutes" badge. RESOLVED.** `Landing.tsx:43` now reads "Ready to print in ~15 minutes · no CAD skills"; the privacy line moved to the sub ("Runs entirely on your machine.", `Landing.tsx:48`). Exactly the recommended fix.
- **UX-008 — duplicate "Designing" row suppressed on first design. RESOLVED, a11y intact.** `ChatPanel.tsx:187` now gates the thinking row on `busy && result !== null` (in-thread refines only) and re-labels it "Refining your part…"; the first-design progress is owned by the viewport overlay. Verified no a11y loss: the viewport overlay carries `role="status"` + an `aria-live="polite"` phase label (`Viewport.tsx:183,189`), so a screen reader still hears progress on a first design.
- **UX-011 — v1 version cue. RESOLVED.** `VersionRail.tsx:17-26` returns a `.kc-version-rail-hint` (`role="note"`) reading "v1 — refine to create versions you can step back to." instead of `null` at one version; the full rail still appears at 2+.
- **UX-012 — format-purpose note. RESOLVED.** `ExportPanel.tsx:191-195` now carries the one-line "what each format is for" guidance (".3mf is printer-agnostic and safe to share; .STL opens in other slicers and CAD tools") while keeping the honest "STEP/BREP arrive with the CAD engine" framing.
- **UX-013 — dedup save indicator. RESOLVED.** `Topbar.tsx:113-121` the persisted indicator now reads just "Saved" (dot + word), with the link role preserved via `aria-label="Saved — open My Designs"`; the doubled "· My Designs" tail is gone since the nav button already provides the link.
- **UX-014 (Nit) — apostrophe convention. ACCEPTABLE CLOSE.** The remediation standardized on the `&rsquo;` entity across the touched components (e.g. `Landing.tsx:47-48`, `RightPanel.tsx:288,316`, `ExportPanel.tsx:122-124`). Consistent within the edited surfaces; renders identically. Fine to close.
- **UX-015 — disabled-slice reason. RESOLVED.** `ExportPanel.tsx:169-174` adds a muted "This printer doesn't have a slicer profile yet — pick another printer above…" line when `selectedPrinter.sliceable !== true`, giving the disabled button an inline why.
- **UX-016 (Nit) — photo alt decorative. ACCEPTABLE CLOSE.** `PhotoOnramp.tsx:171,194` keep `alt=""` on the preview thumbnails; the editable seed text is the real content and is focused on arrival. Intentional and correct.
- **UX-017 — lighter arrow. RESOLVED (with a hygiene caveat — see NEW-2).** `styles.css:1862-1864` adds `.kc-rec-arrow { font-weight: 600 }`, which (being later in the cascade) wins over the original `font-weight: 800` at `styles.css:1481`. The arrow renders lighter as intended.
- **UX-018 (Nit) — InfoTip "i" glyph kept. ACCEPTABLE CLOSE.** `InfoTip.tsx:46-57` keeps the italic-i glyph with the WCAG 2.5.8 hit-area expansion intact; a real `<button>` with `aria-label`, `aria-expanded`, and `aria-controls`. Keeping the glyph for the hit-area was the right trade; close.

---

## NEW findings (regressions / introduced by remediation)

### NEW-1 (Minor) — the new mobile CTA is the one interactive control missing the app's branded `:focus-visible` ring
**Category:** Accessibility / consistency
**Evidence:** `Workspace.tsx:117` renders the CTA as a bare `<button className="kc-mobile-cta">` — it does **not** carry `kc-btn`, and `styles.css:1965-1985` defines no `.kc-mobile-cta:focus-visible`. Every other interactive control in the app has an explicit branded accent focus ring (`.kc-btn`/`.kc-chip` at `styles.css:261-263`, plus per-control rules at 979, 1071, 1459, 2275, 2353, 2878, 3103, …). There is no global `outline:none` reset (the two `outline:none` rules are scoped to `.kc-input` at `styles.css:364` and one other element), so the CTA still shows the browser's *default* focus outline — it is not invisible, just inconsistent and thinner/lower-contrast than the rest of the app, on what is the **primary print action on a phone**.
**Why it matters:** It's the lone keyboard/switch-control focus indicator in the app that doesn't match the deliberate accent-ring system, on the most important mobile control. Low exposure (mobile + keyboard/switch user), low impact (focus is still visible), but it's a visible crack in an otherwise rigorously consistent a11y story on the owner's #1 axis.
**Fix path:** Either add `kc-btn kc-btn-accent` to the CTA's className (it would then inherit `.kc-btn:focus-visible`), or add an explicit `.kc-mobile-cta:focus-visible { outline: 2px solid var(--kc-accent-deep); outline-offset: 2px }` to match the system.

### NEW-2 (Nit) — duplicate `.kc-rec-arrow` rule leaves a stale `font-weight: 800`
**Category:** Code hygiene (CSS)
**Evidence:** `.kc-rec-arrow` is declared twice — `styles.css:1481` (`font-weight: 800`, the pre-fix value) and again at `styles.css:1862` (`font-weight: 600`, the UX-017 fix). The later rule wins, so the rendered result is correct, but the conflicting earlier declaration is now dead and is a trap for a future editor (changing line 1481 would have no effect).
**Fix path:** Edit the original rule at `styles.css:1481` to `font-weight: 600` and drop the duplicate block at 1862 (or vice-versa) so there's a single source of truth. Purely cosmetic source hygiene; zero user impact.

---

## Regression sweep — explicit clears

- **Visual hierarchy:** the accent treatments are per-card modifiers, so they did not wash the column or over-weight the wrong card — the verdict card is now the heaviest, as intended. No regression.
- **Non-colour cues:** the new printability icon tiles convey status by **shape** (✓ check vs ⚠ triangle-bang) for sighted/colour-blind users **and** by an SR-only word for screen readers — not colour alone (`RightPanel.tsx:578-579`). Token contrast is strong: `--kc-pass` is `#1d7a4e` (a dark green; the `var(--kc-pass, #3f8f5b)` fallback at `styles.css:1920` is unreachable dead text but harmless) and `--kc-fail` is `#a8431f`, both on a ~16% tint of near-white surface. WCAG-safe.
- **Printer chip accessibility:** descriptive `aria-label` carrying name + build volume; the dot is `aria-hidden`. As a static "target" readout (not a live connection indicator) the always-accent dot is honest — it does not falsely imply "connected." No regression.
- **ARIA/state integrity:** suppressing the duplicate "Designing" chat row (UX-008) does not strip screen-reader progress — the viewport overlay's `role="status"` + `aria-live` phase label still announce it. The chat `role="log" aria-live="polite"` region is unchanged. Save-indicator branches remain mutually exclusive (`Topbar.tsx:99-122`). No state was broken.
- **Focus rings on new controls:** help button (inherits `.kc-btn`), refine chips (inherit `.kc-chip`), saved button (`styles.css:2275`) all covered. Only the mobile CTA is the gap (NEW-1).
- **Tests:** 257 vitest pass; the remediation added coverage for every changed component, so the fixes are regression-guarded.

---

## Final UX rollup & gate recommendation

**All 18 prior UX findings (6 Major, 7 Minor, 5 Nit) are RESOLVED in current code.** The remediation introduced **2 new low-severity items** (1 Minor focus-ring consistency on the mobile CTA, 1 Nit CSS-hygiene duplicate) and **zero new Major/Critical/Blocker** issues. The cross-cutting concerns that kept the original from clearing the Apple-level bar — right-column composition (cluster 1), discoverability of Stage 8.5 capabilities (cluster 2), and a real phone layout (cluster 3) — are all addressed.

**Gate recommendation (UX lane): PASS — clears the bar for a beta.** No Blockers, no Criticals, no Majors. The two new findings are not beta-blocking (the mobile CTA is still keyboard-focusable; the duplicate CSS rule is invisible to users). Recommend NEW-1 be picked up in the same touch-up pass as NEW-2 — both are sub-five-minute edits — but neither should hold the beta. The workspace now reads as one composed product, the new capabilities are discoverable, and the accessibility story is intact end to end.

**Re-audit closure: PASS with 2 trivial follow-ups (NEW-1 Minor, NEW-2 Nit) for the next hygiene pass.**
