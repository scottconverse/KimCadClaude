# Stage 4 — UI/UX Deep-Dive (audit-team backfill, 2026-06-05)

**Role:** Senior UI/UX Designer (independent, skeptical)
**Scope:** Stage 4 = React SPA shell + 3D viewport + primary flow (land → generate(demo) → viewport → adjust → slice → export), plus the screens that share the shell (My Designs, Settings, First-run wizard, Shortcuts help).
**Method:** Drove a live demo build (`kimcad-demo`, `--demo`, served from the committed Vite build) at desktop (1280px) and mobile (390px). Findings use rendered DOM + computed-style inspection as the authoritative source (per harness note: `preview_eval` is an isolated world and screenshots can return stale frames); screenshots are corroborating. Contrast ratios were computed from rendered `color`/`background-color` with proper alpha-blending.

**Tooling note (not a product finding):** the preview harness intermittently (a) reverted the requested viewport width to a 685px default for a frame, and (b) returned stale composited screenshots that didn't match the live DOM. Every layout/contrast claim below was re-verified with `getBoundingClientRect` / `getComputedStyle` and, for the overflow finding, a live `window.scrollTo` reachability test. The demo also auto-seeds a sample design, so the route oscillates between `#/` (landing) and the workspace as the seed resolves — this is demo behavior, not a routing bug.

---

## Severity counts

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 2 |
| Minor    | 4 |
| Nit      | 2 |
| **Total**| **8** |

No Blockers. No Critical findings. The shell is genuinely strong; the two Majors are an accessibility-contrast miss on the product's single most important readout, and a real (if subtle) dead-scroll layout bug on the core workspace.

---

## What's working (specific credit)

- **State coverage is unusually complete.** Every data view has an idle / loading / empty / error branch with human copy (RightPanel cards, ExportPanel, MyDesigns, Settings). The "Designing…" overlay is honest and never a trap: live phase stepper + elapsed timer + a real Cancel, with `pointer-events:auto` forced via a compound selector so a CSS reorder can't re-trap the user (`styles.css:569`). This is the kind of thing most teams skip.
- **Accessibility fundamentals are real, not cosmetic.** Logical tab order on the landing (brand → nav → textarea → Design it → photo → examples; no positive tabindex, no traps — verified live). The first-run wizard implements a genuine focus trap (`FirstRunWizard.tsx:79-108`) with Tab cycling and Escape-to-skip. `InfoTip` is a proper disclosure button with `aria-expanded`/`aria-controls`/`role=note` and Escape + outside-click dismiss. SR-only severity words back every color-coded status (`RISK_TONE_WORD`, the `kc-check` "OK:"/"Needs review:" prefixes) so meaning isn't carried by color alone (WCAG 1.4.1).
- **Reduced-motion is respected globally** (`styles.css:783`) and the viewport's auto-rotate is disabled to match.
- **Touch targets** get a 44px floor under both `pointer:coarse` AND `max-width:640px` (belt-and-suspenders, since a desktop resized narrow never reports coarse) for the sliders, unit toggle, value editor, and card actions.
- **Copy is plain-English and trustworthy throughout** — "Runs entirely on your machine", the privacy callout on cloud opt-in, "KimCad never auto-starts a print", the honest "results can be rough" on the experimental generator. The model is shown as `gemma4:e4b` (a health readout, never a menu of alternatives), consistent with product intent.
- **Destructive actions are guarded** with two-step confirms (Delete → Delete?/Cancel; Reset → Reset everything/Cancel) that auto-disarm.
- **Mobile reflow is deliberate**, not a squashed desktop: single-column grid, a shorter viewport row, and a sticky "↓ Check & download" CTA that jumps to the export card (the print actions otherwise fall below a tall viewport).

---

## Findings

### UX-001 — Major — Accessibility / Color — Readiness verdict + confidence badge fail WCAG AA contrast

**Category:** Accessibility (contrast)
**Evidence:** Workspace right panel, Readiness card, desktop. Computed from rendered colors:
- Verdict "Ready to print" — `color: rgb(29,122,78)` (`--kc-pass #1d7a4e`) on the readiness card's warm tint (`color-mix(--kc-accent 7%, --kc-surface)`), 17px/700 → **3.92:1**.
- "Medium confidence" badge — same green on a `--tone 14%` tint, 11.5px/700 → **3.92:1**.

WCAG 2.1 AA requires 4.5:1 for normal text; "large" (≥18.66px bold) would only need 3:1, but the verdict is 17px bold and the badge is 11.5px — both are *normal* text, so 4.5:1 applies. Both fail. The warn tone (`#876312`) clears AA; the fail tone (`#a8431f`) is borderline (~4.4:1) and should be checked in the same fix.

**Why it matters:** This is the product's single most important sentence — the "should I print this?" answer an ex-Apple owner will judge the whole app on. A user with low vision or a dim laptop panel reads the verdict worse than any other text in the product, and the color *is* the meaning here.

**Fix path:** Darken the pass tone used for text-on-tint to ≥4.5:1 — e.g. introduce `--kc-pass-deep: #166b43` (or darker) and use it for `.kc-readiness-verdict` and `.kc-conf-badge` text (and the fail-tone equivalent), mirroring the existing `--kc-accent` → `--kc-accent-strong/-deep` split the team already uses for white-on-accent. Keep the bright `--kc-pass` for the gauge stroke/dots (non-text).

**Blast radius:**
- Adjacent code: `.kc-readiness-verdict`, `.kc-conf-badge`, `.kc-tone-pass` text, `.kc-finding-*` dots, and `--tone` consumers in `styles.css` (~1245-1500). The same green is reused for the topbar "Saved" dot, `.kc-status-badge.kc-tone-pass`, and Settings "Installed"/"Running" — audit those text usages in the same pass.
- Shared state: the `--kc-pass`/`--kc-warn`/`--kc-fail` tokens (`:root`, `styles.css:62-65`). A text-vs-fill token split fixes every instance at once.
- User-facing: verdict/badge get slightly darker; no layout change.
- Migration: none.
- Tests to update: none known (no contrast assertions exist — see the Test role's coverage gap).

---

### UX-002 — Major — Responsive / Layout — ~248px of dead scroll on the desktop workspace (absolutely-positioned `.kc-sr-only` inflates document height)

**Category:** Responsive / Layout
**Evidence:** Workspace, desktop 1280×832. `document.documentElement.scrollHeight = 1080` vs `innerHeight = 832`. A live `window.scrollTo(0,400)` left the page at `scrollY ≈ 248` — the page genuinely scrolls into empty space below the app. No *visible* element extends past 832 (deepest unclipped visible element bottoms at exactly 832), so the user gets a scrollbar and ~248px of nothing.
Root cause isolated: the offending elements are the `.kc-sr-only` spans inside `.kc-check` items in the Printability card (the "OK:"/"Needs review:" SR prefixes). They are `position:absolute` (`styles.css:1229`), their `.kc-check`/`.kc-col-right` ancestors are `position:static`, so they escape the right column's `overflow:auto` clip and position against the document — landing at docBottom 1005/1030/1055/**1080**, exactly the inflated scrollHeight.

**Why it matters:** On the core working screen, the scrollbar implies there's more below and there isn't — a small but real "is this broken?" moment. For a UI-first, zero-findings bar it's the kind of polish defect that erodes trust. It only appears once a part is on screen (Printability card rendered), i.e. the main use case.

**Fix path:** Either (a) modernize `.kc-sr-only` to the clip-path visually-hidden pattern that doesn't affect layout: add `clip-path: inset(50%); white-space: nowrap;` and `inset: auto` so it can't extend any scroll container; or (b) give the SR-only host a positioned, zero-size containing block. Option (a) is the standard fix and corrects every SR-only instance app-wide.

**Blast radius:**
- Adjacent code: every `.kc-sr-only` usage — `.kc-check` prefixes, `.kc-risk` tone words, the MyDesigns "Sort by" label, the copy-link live-region, the file `<input>` in MyDesigns. All inherit the fix.
- Shared state: the single `.kc-sr-only` rule (`styles.css:1229-1239`).
- User-facing: dead scroll on the workspace (and any scroll container holding an sr-only) disappears.
- Migration: none.
- Tests to update: none known.
- Related: this is precisely the class of subtle layout bug that has no rendered-screenshot test (Test/QA role gap).

---

### UX-003 — Minor — Visual hierarchy / Affordance — My Designs card actions mix link and button styling; "Export" is underlined, the others aren't

**Category:** Visual hierarchy / Pattern
**Evidence:** My Designs, each card's action row. Verified live: Rename/Duplicate/Delete are `<button>` with `text-decoration:none`; "Export (.kimcad)" is an `<a download>` with `text-decoration:underline`. Visually, one of four sibling actions is underlined for no user-meaningful reason (it's an implementation detail that it's an anchor).

**Why it matters:** A row of peer actions should read as peers. The lone underline makes "Export" look like a different *kind* of thing (a navigation link) when it's a sibling action, and draws the eye to a secondary action over Rename.

**Fix path:** Normalize the row — apply the existing `.kc-design-act` styling so the anchor renders identically (`text-decoration:none`, same color/weight/hover), keeping it an `<a download>` for the native download behavior. The action set should look like one control group.

**Blast radius:**
- Adjacent code: `.kc-design-act`, `.kc-design-act` anchor in `MyDesigns.tsx:147`.
- User-facing: Export stops looking like an outlier; no behavior change.
- Migration / tests: none.

---

### UX-004 — Minor — Visual hierarchy / Safety — "Delete" has no resting destructive cue on desktop

**Category:** Visual hierarchy
**Evidence:** My Designs card actions. `.kc-design-act-danger` base color is `rgb(111,104,87)` — identical to the non-destructive actions; the red (`--kc-fail`) only applies on `:hover` (`styles.css:2181`), and the "push Delete to the row end" (`margin-left:auto`) only applies under `pointer:coarse`/`max-width:640px`. So on desktop with a mouse at rest, Delete sits inline immediately after Export, same color, no separation.

**Why it matters:** A destructive action reads as just another link until you hover it. The two-step "Delete → Delete?" confirm is good and meaningfully lowers the risk, so this stays Minor — but at rest the destructive action deserves a visual tell (and the touch-only separation should also help mouse users).

**Fix path:** Give `.kc-design-act-danger` a subtle resting cue (e.g. `color: color-mix(--kc-fail 70%, --kc-muted)`) and apply the end-of-row placement on desktop too, not only coarse pointers. Keep the confirm step.

**Blast radius:**
- Adjacent code: `.kc-design-act-danger` rules (`styles.css:731, 776, 2181`), `MyDesigns.tsx:155-179`.
- User-facing: Delete becomes distinguishable at a glance; lower mis-click risk.
- Related: shares the "destructive-action affordance" concern with the Settings "Reset everything" button.

---

### UX-005 — Minor — Responsive — Topbar wraps awkwardly at mobile width (multi-line buttons)

**Category:** Responsive
**Evidence:** Topbar at 390px. The action buttons wrap to two lines each ("Bambu Lab / P2S", "My / Designs", "New / design"), and with the printer chip + Saved indicator the cluster is cramped. Functional and tappable, but visually busy and inconsistent button heights.

**Why it matters:** The top chrome is the first thing on every screen; two-line buttons read as a layout that wasn't tuned for phones. The content reflow elsewhere is clearly intentional, which makes the topbar stand out as the one un-tuned strip.

**Fix path:** At mobile width, condense the topbar: collapse "My Designs"/"Settings"/"?" into icons (or an overflow menu), shorten "New design" to an icon+label or a single "+", and let the printer chip drop its build-volume on the smallest widths (it's already a status readout). `white-space:nowrap` on the remaining labels prevents the two-line wrap.

**Blast radius:**
- Adjacent code: `.kc-topbar`, `.kc-topbar-actions`, `.kc-btn` at the `max-width:640px` breakpoint; `Topbar.tsx`.
- User-facing: cleaner mobile chrome; ensure tap targets stay ≥44px after condensing.
- Migration / tests: none.

---

### UX-006 — Minor — Visual consistency — Modal scrim leaves the topbar visually un-dimmed

**Category:** Visual hierarchy / Pattern
**Evidence:** First-run wizard (and Shortcuts help share the pattern). The overlay (`z-index:200`, `inset:0`, 55% ink scrim) functionally covers the topbar — `elementFromPoint` over the topbar buttons returns `.kc-wiz-overlay`, so the topbar is correctly NOT clickable through the modal (focus integrity is intact). But in the rendered screenshot the topbar buttons read at near-full brightness above the scrim, so the chrome *looks* interactive while the modal is open.

**Why it matters:** The visual cue contradicts the (correct) behavior: it invites a click that does nothing. Minor, because the trap works and Escape/Skip are obvious.

**Fix path:** Confirm the scrim actually paints over the topbar at full strength (a static topbar under a `z-index:200` fixed overlay should be dimmed — verify no stacking context on the shell is lifting the topbar). If the dimming is too light, deepen the scrim or add a slight blur so "behind the modal" reads unambiguously.

**Blast radius:**
- Adjacent code: `.kc-wiz-overlay`, `.kc-modal-backdrop` (Shortcuts help reuses the pattern, `styles.css:1777`), `.kc-topbar` stacking.
- User-facing: modal background reads as inert.
- Migration / tests: none.

---

### UX-007 — Nit — Visual — Settings unit toggle stretches full-width on mobile

**Category:** Visual hierarchy
**Evidence:** Settings → Units at 390px. The mm/in segmented toggle expands across the row (the active "mm" is a small filled box, "in" fills the remaining width), looking unbalanced versus the same compact toggle in the Parameters card header.

**Fix path:** Constrain the Settings unit toggle to content width (`align-self:flex-start` / `width:max-content`) so it matches the workspace toggle.

---

### UX-008 — Nit — Visual — Settings "Reset…" / "Design your first part" CTAs render full-width and centered

**Category:** Visual hierarchy
**Evidence:** Settings → About "Reset…" button and (by code) the empty-state primary CTA render as wide, centered buttons. A full-width secondary "Reset…" reads slightly heavier than a destructive-adjacent secondary action warrants.

**Fix path:** Size the "Reset…" trigger to content width; keep the empty-state primary CTA prominent (it's a genuine primary). Subjective — flagged once.

---

## Cross-cutting / journey notes

- **No journey dead-ends found.** Every failure surface offers a way forward: model-down → "Try again" + "Start Ollama" pointer; no-template → explicit experimental opt-in or re-describe; gate-fail → model still downloadable to inspect; reopen failure → "That design couldn't be opened." with the library still reachable. This is the strongest part of the UX.
- **The two Majors share a root with the Test/QA roles:** there is no rendered-browser/contrast assertion in the suite, which is exactly why a 3.92:1 verdict and a 248px phantom scroll could ship. A single visual-regression + contrast gate would have caught both. Recommend the dev team pair the UX-001/UX-002 fixes with a minimal rendered-state test (desktop + mobile screenshot of the populated workspace, plus an automated contrast check on the readiness verdict).
- **Verdict:** Stage 4's shell and viewport are release-quality on structure, states, copy, and keyboard accessibility; the only thing standing between this and the zero-findings bar is the AA contrast miss on the headline verdict (UX-001) and the dead-scroll layout bug on the core workspace (UX-002) — both small, both worth fixing before sign-off.

---

## Evidence

Live-driven against the running demo build. Screenshots were captured at desktop (1280) and mobile (390) for: landing, first-run wizard (step 1), populated workspace, My Designs (desktop + mobile), Settings (mobile, top + scrolled). Per the harness limitation, the load-bearing claims (contrast ratios, the scroll-overflow reachability, tab order, modal hit-testing, action-row tag/decoration) are backed by `getComputedStyle`/`getBoundingClientRect`/`elementFromPoint`/`window.scrollTo` measurements quoted inline above, which are authoritative where screenshots can be stale.
