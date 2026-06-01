# UI/UX Deep-Dive — KimCad (Stage 4 gate)

**Audit date:** 2026-06-01
**Role:** Senior UI/UX Designer
**Scope audited:** The built React/Vite SPA (`frontend/src/`) as rendered live in demo mode (`kimcad.cli web --demo`, port 8842): the landing/empty screen, the three-column workspace (conversation · viewport · parameters/printability/export), the printability report, and the export/slice panel. Rendered and driven at 1340×880 (desktop) and 375×812 (mobile). Compared against the Workshop design spec in `docs/design/` (README + `screens/06,09,10` + the React prototype).
**Auditor posture:** Balanced

---

## TL;DR

The Stage-4 UI is a clean, honest, faithful realization of the Workshop design *system* — the tokens are pixel-exact (warm sand `#f0ebe0`, terracotta `#c8623a`, dark viewport `#14171c`, 58px topbar, Bricolage display, the light-chrome-wraps-dark-viewport signature), the three-column layout and responsive stacking work, and the demo flow (landing → design → printability → slice → download) runs end-to-end with zero console errors and a genuinely good accessibility spine (`role="log"` + `aria-live` conversation, label-wrapped selects, focus-visible rings, a focus-trapping hero card). The strongest dimension is **token/layout fidelity and state honesty** (every panel has a real empty state and a real populated state). The weakest dimension is **the 3D viewport**, which departs from the design's signature print-aware preview: it renders a solid-shaded model instead of the blueprint wireframe and — more importantly — ships **none of the on-canvas affordances** (no X/Y/Z dimension pills, no bounding box, no "drag to rotate" hint, no orientation chip), so a first-time user gets an unlabeled rotating box with no cue that it's interactive. The single most important takeaway: **the accent-on-white button text fails WCAG AA contrast (3.99:1)** on the two primary CTAs ("Design it", "Slice & prepare file"), and **no surface respects `prefers-reduced-motion`** while the viewport auto-rotates perpetually — two real accessibility defects that the otherwise-careful a11y work makes surprising.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 6 |
| Nit | 3 |

## What's working

- **Design tokens are pixel-faithful.** Inspected computed styles match the Workshop spec exactly: topbar `57.99px` (spec 58), surface `rgb(250,246,238)` = `#faf6ee`, accent `rgb(200,98,58)` = `#c8623a`, ink `rgb(39,34,25)` = `#272219`, muted `rgb(111,104,87)` = `#6f6857`, hero title Bricolage `47px/700`. No drift. (Landing, desktop 1340.)
- **The light-chrome / dark-viewport contrast — the design's stated signature — is intact.** The viewport card is `#14171c` inside warm-sand chrome; it reads as "friendly app, precise engineering window" exactly as intended. (Workspace, both viewports.)
- **Conversation accessibility is done right.** `.kc-chat-body` has `role="log"`, `aria-live="polite"`, and a live `aria-busy` that flips during the design call — so a screen reader announces the assistant's reply as it arrives. This is the correct, non-obvious choice and it's implemented. (Workspace.)
- **Honest, non-blank empty states everywhere.** Before a design runs, Parameters, Printability, and Export each render a helpful one-line empty state ("The part's adjustable parameters will appear here once it's designed", etc.) rather than a blank card. The viewport shows "Your 3D preview appears here." No blank screens — the hardest UX discipline, and it's held. (Right panel + viewport, pre-design.)
- **Form controls are label-wrapped.** The Printer and Material selects are wrapped in `<label class="kc-field">` with a `<span>` label — proper programmatic association, no orphan selects. (Export panel.)
- **Focus management is considered.** The hero textarea suppresses its own outline and hands the keyboard-focus indicator to the card via `:focus-within` (a 3px accent ring), and chrome buttons/chips/selects all have `:focus-visible` rings. This is deliberate, correct work. (Landing + export panel.)
- **Responsive stacking is correct and clean.** At 375px the three-column grid collapses to a single stacked column (conversation → viewport → panels) with **no horizontal scroll** (`scrollWidth 375 == innerWidth 375`) and the viewport pinned to a sensible 42vh. (Mobile workspace.)
- **Runtime is clean.** Zero console errors or warnings across the full demo flow including the slice round-trip.

## What couldn't be assessed

- **Failure-path visuals** (gate_failed / clarification_needed / render_failed). The demo backend only emits a gate-PASS box, so the amber/red printability states, the clarify-question conversation styling, and the error bubble were not visually reachable. The code paths exist (`assistantMessage`, `gate_failed` branch in `ExportPanel`, `.kc-msg-error`, `.kc-tone-fail`) and per the audit charter these are unit-tested — I did not flag them as missing. I did verify the *tone classes* render (the pass badge is correctly `kc-tone-pass`, green `#1d7a4e`).
- **Out-of-scope, by charter:** live parameter sliders (Stage 5), the direct-print/send dialog + Smart Mesh readiness card + printer monitoring (Stage 10), the first-run wizard, model picker, photo on-ramp, and the version-history rail. Their absence in the build is expected and is not flagged below.

---

## First impressions

Landing at the front door (desktop, no context): the eye lands cleanly on the hero "What do you want to make today?" and immediately on the terracotta "Design it" button — the visual hierarchy is correct, and within ~3 seconds I know this turns a description into a printable part. The "Try" example pills are an excellent zero-friction on-ramp; clicking one designs a part with no typing. The page feels friendly and uncrowded.

Two first-impression gaps against the design: (1) the badge reads **"Local-first · runs entirely on your machine"** with no leading status dot, where the design's badge is **"Ready to print in ~15 minutes · no CAD skills"** with a green dot — the shipped copy sells the *architecture* (a developer concern) instead of the *outcome and speed* (the user's concern); and (2) the topbar is bare (brand + gear) where the design has a printer chip showing the connected printer + build volume. The printer identity matters — it's the thing that makes "will this fit my printer?" answerable at a glance — and it's referenced later in the report ("Fits the Bambu Lab P2S build plate") but never shown in the chrome.

Entering the workspace, the model appears as a solid terracotta box that slowly auto-rotates on a faint grid. It's attractive, but there is **no on-canvas cue that it's draggable**, no dimension labels, and no orientation chip — so the "print-aware preview" that's central to the product promise reads, on first contact, as a decorative spinning box.

## Journey walkthroughs

### Journey: Describe → preview → check → download (the core Stage-4 loop)

1. **Landing.** Click the "a wall-mounted holder…" example pill. Clean transition into the workspace; the conversation immediately shows the user's prompt as a right-aligned terracotta bubble.
2. **Designing.** The viewport shows "Designing your part…" and the conversation shows a spinner row with "Designing your part…". Honest loading state, correctly announced via `aria-live`. (Note: the demo returns a generic `box`, not a wall-mounted holder — that's canned demo data, not a UI defect.)
3. **Built.** The AI reply arrives ("Here you go — Demo part for: …"); the right panel fills with Parameters (Type `box`, Size `80 × 60 × 40 mm` in mono), a green **"Ready to print"** badge, an Axis/Target/Actual dims table, and four green findings ("Closed, watertight solid", "Dimensions match…", "Fits the Bambu Lab P2S build plate", "Wall 2.0 mm is adequate"). This is a strong, legible report.
4. **Slice.** "Slice & prepare file" produces a real estimate ("~50m 20s, 200 layers, 33.63 cm3 filament"), a "Download G-code" button, and a "Download 3D model (STL)" link, with a connector status line ("mockReady · simulated"). The flow completes with a downloadable artifact — the journey reaches "task complete."

The loop is coherent and has no dead ends *within the happy path*. The friction is concentrated in the viewport (no interaction cues / dimension labels — UX-001) and the gear button, which looks interactive but does nothing (UX-006).

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion / IA

### [UX-001] — Major — Pattern / Journey — The 3D viewport ships none of the design's print-aware affordances (dimension labels, interaction hint, orientation chip)

**Evidence**
Workspace viewport, both 1340 and 375. Inspected via `preview_eval`: the `.kc-viewport-card` contains a single `<canvas>` and `.kc-viewport-stage` and *nothing else* — `hasOrbitHint: false`, no "Auto-oriented · plate-down" text, no dimension-label elements. The KCViewport (`frontend/src/viewport/KCViewport.ts`) builds a `MeshStandardMaterial` solid + `EdgesGeometry` lines + a `GridHelper` plate, but no bounding box and no projected dimension pills. The Workshop design (`screens/09`) anchors mono glass pills `H 150 mm` / `W 70 mm` / `D 49 mm` to the model's bounding box, a top-right "drag to rotate · scroll to zoom" hint, and a top-left "Auto-oriented · plate-down · change" chip. In the render, the model auto-rotates with no on-canvas cue that the user can grab it.

**Why this matters**
The "print-aware preview" is the heart of the product promise — it's how a non-CAD user *sees* that the part is the right size and correctly oriented for the plate. Without the X/Y/Z labels, the dimensions live only in a side-panel table, so the user can't connect "this face is 80 mm" to the geometry. Without the "drag to rotate" hint, a first-timer doesn't know the canvas is interactive (the perpetual auto-rotation actually *reduces* the perceived need to touch it). The orientation chip is what tells the user "I already laid this flat for printing" — its absence removes a key trust signal. Each individual screen is "fine," but the journey loses the single most differentiating moment.

**Blast radius**
- Adjacent code: `frontend/src/viewport/KCViewport.ts` (add bbox + projected-label rendering, a render-mode toggle, and the overlay DOM); `frontend/src/components/Viewport.tsx` (overlay markup + the "drag to rotate" hint + orientation chip). The prototype `docs/design/prototype/jsx/preview.jsx` already implements projected labels and can be mined directly.
- User-facing: every designed part in the workspace; this is on the primary flow for 100% of users.
- Tests to update: none known (no current viewport-overlay tests).
- Related findings: UX-002 (render mode), UX-009 (canvas aria-label could carry the dimensions an SR user can't see on-canvas).

**Fix path**
Prioritize, in order: (1) add the top-right **"drag to rotate · scroll to zoom"** hint — cheapest, highest-value cue; (2) add the **projected X/Y/Z dimension pills** anchored to the bounding box (port from `preview.jsx`); (3) add the **"Auto-oriented · plate-down"** chip. These are the three affordances that make the preview "print-aware" rather than decorative. Even if the version rail and click-to-point stay deferred, these three are what a Stage-4 "preview & refine" surface needs.

---

### [UX-002] — Minor — Pattern — Viewport renders a solid-shaded model, not the design's blueprint wireframe default

**Evidence**
Workspace viewport (both sizes; clearest in the 375 screenshot). The model is a solid terracotta `MeshStandardMaterial` fill with edge lines (`KCViewport.ts:89,92`). The Workshop design specifies the **default render mode is the accent wireframe / "Blueprint"** style (README §"Workspace — Viewport": "rendered as an accent **wireframe** (blueprint style; also Solid and Hologram render modes)"; recommended baseline = "Blueprint render").

**Why this matters**
The blueprint wireframe is part of the brand's "precise engineering window" identity and visually communicates "this is a technical preview, not a finished render." The solid fill is attractive and not *wrong*, but it shifts the read from "blueprint" to "product shot," diluting the intended character. It's a Minor because the model is still clearly legible and the build plate/grid is present.

**Blast radius**
- Adjacent code: `KCViewport.ts` material setup; if the three render modes (Blueprint/Solid/Hologram) ship later, this becomes a default-selection decision, not a rebuild.
- User-facing: every workspace render.
- Related findings: UX-001.

**Fix path**
Make Blueprint (accent wireframe, edges-forward with a faint translucent fill) the default render, matching the recommended baseline. Keep the current solid as the "Solid" mode option for when render modes ship.

---

### [UX-003] — Major — Accessibility — Primary-button text fails WCAG AA contrast (white on terracotta = 3.99:1)

**Evidence**
Computed at runtime: accent `#c8623a` (rgb 200,98,58) with white text yields a contrast ratio of **3.99:1**. This is the fill of the two primary CTAs — **"Design it"** (landing, 12.5px/600) and **"Slice & prepare file"** (export, 12.5px/600) — both *normal-size* text (well under the 18.66px / 14pt-bold large-text threshold). WCAG 2.1 AA requires **4.5:1** for normal text. The "Download G-code" dark button passes (it's ink-on-bg). The accent "Download 3D model (STL)" link (12.5px/600, accent-on-surface = **3.70:1**) and the accent "Cad" wordmark text on surface (3.70:1) are also below 4.5 — the wordmark is large (21px/800) so it passes AA-large (3:1), but the STL link is normal text and fails.

**Why this matters**
These are the product's two most important buttons; their labels are measurably below the AA floor the spec's accessibility requirement (§4.2, "WCAG 2.1 AA contrast") commits to. Users with low vision, and anyone on a sunlit screen, will find the white label on terracotta harder to read than it should be. It also undercuts the otherwise-careful a11y work (which makes this the more surprising to find).

**Blast radius**
- Adjacent code: `--kc-accent` / `--kc-on-accent` and `.kc-btn-accent` in `styles.css`; `.kc-download-model`. Every accent button + accent link inherits the fix.
- Shared state: the `--kc-accent` token is the brand color — changing it has theme-wide reach, so prefer the targeted approach below.
- User-facing: every primary CTA and accent link, every screen.
- Tests to update: none known.
- Related findings: UX-009.

**Fix path**
Don't change the brand accent (it's correct for fills, chips, focus rings, and the wireframe). Instead darken **only the button-fill / link variant** to meet 4.5:1 with white text — `--kc-accent-strong` (`#b1542f`) is already defined and lands at ~4.5:1; use it as the button background (and the active fill becomes a still-darker step), or introduce a `--kc-accent-text` token for accent-colored text/links that clears 4.5:1 on surface. Verify the chosen value with a contrast checker, not by eye.

---

### [UX-004] — Minor — Accessibility / Responsive — Touch targets below the 44×44 minimum on mobile

**Evidence**
At 375×812 (touch viewport), measured bounding boxes: "Design it" button **104×39px** (height 39 < 44), gear icon-button **38×38px**, "Try" example chips **32px tall**. The spec's accessibility floor (§4.2) and the role brief both require hit targets ≥44×44 / 44px min on touch.

**Why this matters**
On a phone these are the primary actions (design a part, open settings, pick an example). Sub-44px targets raise mis-tap rate, especially the 32px chips and the 38px gear. This is the kind of thing that's invisible on desktop and bites every mobile user.

**Blast radius**
- Adjacent code: `.kc-btn`, `.kc-icon-btn`, `.kc-chip` padding/min-height in `styles.css` — a single media query at the mobile breakpoint raises all of them.
- User-facing: all touch users on landing + workspace chrome.
- Related findings: UX-005.

**Fix path**
At ≤1000px (the existing stacking breakpoint), set `min-height: 44px` on `.kc-btn`, `.kc-icon-btn` (→ 44×44), and `.kc-chip`, and bump vertical padding accordingly. Desktop sizing can stay as-is.

---

### [UX-005] — Minor — Responsive — Hero input card never stacks on mobile; textarea is squeezed beside the button

**Evidence**
At 375px the `.kc-input-card` keeps `flex-direction: row` with `align-items: flex-end`, so the textarea (right edge ~222px) sits beside the 104px "Design it" button, leaving the textarea ~184px wide. The placeholder "e.g. a wall-mounted holder for a 1 kg filament spool" wraps to two lines and reads as crowded against the button (visible in the mobile landing screenshot). No literal overlap (10px gap), but the field is cramped, and a real typed prompt gets a very narrow input.

**Why this matters**
The input is *the* primary action on the most important screen. On a phone, a narrow two-line field beside a big button feels awkward and makes a longer description hard to read back. The design's hero input is roomy.

**Blast radius**
- Adjacent code: `.kc-input-card` in `styles.css` (add a mobile rule).
- User-facing: every mobile/landing visitor.
- Related findings: UX-004.

**Fix path**
At the mobile breakpoint, switch `.kc-input-card` to `flex-direction: column; align-items: stretch;` so the textarea takes the full card width and the "Design it" button drops below it full-width (which also gives it a comfortable ≥44px height for UX-004).

---

### [UX-006] — Minor — Journey — Settings gear is a visible affordance that does nothing

**Evidence**
Topbar gear (`aria-label="Settings"`, `.kc-icon-btn`) has hover styling (color → accent) so it reads as interactive, but clicking it changes nothing (`changedAfterClick: false`). Source confirms it's intentional placeholder chrome ("the gear is persistent chrome without an action yet"). It's present on *both* landing and workspace, on desktop and mobile.

**Why this matters**
A control that looks clickable and hover-responds but is inert is a small trust/dead-end paper-cut — the user clicks expecting settings (and the design intends it to reopen the first-run wizard) and gets silence, with no explanation. It's Minor because it's peripheral, not on the core path.

**Blast radius**
- Adjacent code: `frontend/src/components/Topbar.tsx`.
- User-facing: anyone who clicks the gear (likely common — it's the universal "settings" glyph).
- Related findings: none.

**Fix path**
Until the wizard ships, either (a) hide the gear, or (b) keep it but give it a minimal action — a small popover/toast "Settings arrive with the first-run setup wizard" — so the click is acknowledged. Option (b) preserves the chrome the design wants while removing the dead-click. Recommend (b).

---

### [UX-007] — Minor — Accessibility / Motion — No `prefers-reduced-motion` handling; the viewport auto-rotates perpetually

**Evidence**
No `prefers-reduced-motion` media query anywhere in `frontend/src` (CSS or TS). The viewport auto-rotates continuously (`KCViewport.ts:201`, `this.theta += 0.0026` every frame, pausing only during drag). The CSS entrance (`kc-fadeup`) and the spinner (`kc-spin`) also run unconditionally. The Workshop design's §Motion explicitly says to respect reduced-motion.

**Why this matters**
Continuous, unattended rotation is exactly the kind of motion that triggers vestibular discomfort, and there is no way to opt out. Users who set "reduce motion" at the OS level reasonably expect the app to honor it; KimCad currently ignores it across every animated surface. The auto-rotate is the most impactful because it never stops.

**Blast radius**
- Adjacent code: `KCViewport.ts` (gate the auto-rotate on the media query); `styles.css` (wrap `kc-fadeup` / spinner, or add a global `@media (prefers-reduced-motion: reduce)` block).
- User-facing: every workspace visitor with reduced-motion set; the auto-rotate affects all workspace users.
- Related findings: none.

**Fix path**
Add `@media (prefers-reduced-motion: reduce)` to disable `kc-fadeup` and slow/stop decorative motion, and in `KCViewport` read `window.matchMedia('(prefers-reduced-motion: reduce)')` to default `autoRotate = false` (keep manual drag-orbit — that's user-initiated and fine). Consider stopping auto-rotate by default regardless, since it competes with UX-001's "drag to rotate" cue.

---

### [UX-008] — Minor — Copy — Landing badge sells the architecture, not the outcome

**Evidence**
Badge reads **"Local-first · runs entirely on your machine"** (muted text, no status dot). The Workshop design badge is **"Ready to print in ~15 minutes · no CAD skills"** with a green status dot. (Landing, both sizes.)

**Why this matters**
"Local-first / runs on your machine" is a *developer/privacy* value proposition; the first thing a maker wants to know is "how fast can I get a print, and do I need CAD skills?" The design's copy answers the user's actual question and sets a concrete expectation. The green dot also adds a reassuring "system ready" cue. This is a copy + small-visual miss on the highest-traffic line of the product.

**Blast radius**
- Adjacent code: `frontend/src/components/Landing.tsx` (`.kc-badge` string + an optional dot span); `.kc-badge` CSS if adding the dot.
- User-facing: every first-time visitor.
- Related findings: UX-010 (hero sub copy).

**Fix path**
Restore the design copy: **"Ready to print in ~15 minutes · no CAD skills"** with a leading green status dot (reuse `.kc-status-dot.kc-tone-pass`). If "~15 minutes" can't be substantiated at this stage, a safe alternative that keeps the outcome framing: **"From plain words to a print-ready file · no CAD skills."**

---

### [UX-009] — Minor — Accessibility — Canvas aria-label is static ("3D preview") and conveys none of the part's information

**Evidence**
`.kc-viewport-canvas` has `aria-label="3D preview"` — constant regardless of what's rendered. Because the design's on-canvas dimension labels aren't present (UX-001), a screen-reader or low-vision user gets *no* dimensional information from the viewport at all; the only place dimensions exist is the side-panel table.

**Why this matters**
The viewport is the centerpiece, and for an SR user it's an opaque "3D preview" with no content. A descriptive label that names the object and its size turns a black box into usable information and partially compensates for the missing on-canvas labels.

**Blast radius**
- Adjacent code: `frontend/src/components/Viewport.tsx` (thread the plan's object_type + bbox into a computed aria-label).
- User-facing: assistive-tech users in the workspace.
- Related findings: UX-001, UX-003.

**Fix path**
Make the label dynamic from the design result, e.g. `aria-label="3D preview: box, 80 × 60 × 40 mm"`. When designing/empty, reflect that state ("3D preview, designing your part" / "3D preview, no part yet"). Cheap, and meaningfully improves the SR experience.

---

### [UX-010] — Nit — Copy — Hero sub-copy is solid but diverges from the design's voice

**Evidence**
Shipped sub: "Describe a functional part in plain words. KimCad designs it, checks that it's actually printable, and gets it ready for your printer." Design sub (screen 06): "Describe it in plain words — I'll turn it into a print-ready model. No CAD needed." The design uses a warmer first-person ("I'll") voice consistent with the conversational product.

**Why this matters**
Both are good; the design's is slightly warmer and shorter, and the first-person voice matches the chat persona the rest of the app uses ("Here you go —"). Purely a voice-consistency preference, hence Nit.

**Fix path**
Optional: adopt the first-person voice for consistency with the conversation, e.g. "Describe it in plain words — I'll turn it into a print-ready file, checked and ready for your printer."

---

### [UX-011] — Nit — Visual hierarchy — AI conversation messages lack the 28px cube avatar from the design

**Evidence**
`.kc-msg-ai` renders as a plain bubble with no avatar (`aiHasAvatar: false`). The Workshop design (screen 09) precedes each AI bubble with a 28px terracotta cube-glyph avatar; user messages are avatar-less and right-aligned (which the build does correctly).

**Why this matters**
The avatar visually distinguishes "KimCad speaking" from "you speaking" beyond just alignment/color, and reinforces the brand cube. Minor polish — the bubbles are already distinguishable by alignment and color, so it's a Nit.

**Fix path**
Optional: add the 28px accent cube avatar before AI bubbles (the `CubeGlyph` already exists in `Topbar.tsx` and can be lifted into a shared icon).

---

### [UX-012] — Nit — IA / Copy — Export card omits the printer/format guidance and 3MF-first framing from the design

**Evidence**
The built "Export & print" card offers "Download G-code" + "Download 3D model (STL)". The Workshop print-report (screen 10) leads with **"Download .3MF"** as primary (printer-agnostic, safe to share), STEP + G-code as ghosts, plus the note "3MF is printer-agnostic & safe to share · STEP for CAD editing · G-code locks to <printer>." The build's primary downloadable is STL/G-code with no format guidance.

**Why this matters**
The design's framing teaches the user *which* file to take and why (3MF to share, G-code locks to one printer) — useful guardrails for a non-expert. STL also loses the print metadata 3MF carries. This is a Nit at Stage 4 because the slice/download path works and the richer report (3MF/STEP/Send-to-printer) is largely Stage-10 scope; flagging the framing for when that card is built out.

**Fix path**
When the print-report card is expanded (Stage 10), lead with 3MF and add the one-line format guidance. For Stage 4, optionally relabel "Download 3D model (STL)" with a tooltip noting STL carries no print settings.

---

## States audit matrix

| Component / page | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| Landing input | ✓ | ✓ (button/field disable while busy) | ✓ (placeholder) | — | — | Mobile field cramped (UX-005) |
| Conversation | ✓ | ✓ (spinner row, aria-busy) | ✓ ("conversation will appear here") | ✓ (`.kc-msg-error`, not reachable in demo) | — | No avatar (UX-011) |
| Viewport | ✓ | ✓ ("Designing…/Rendering…") | ✓ ("preview appears here") | ✓ ("Could not load the 3D preview") | — | Missing on-canvas affordances (UX-001/002/009) |
| Parameters card | ✓ | — | ✓ | — | — | Read-only by design (Stage 4) |
| Printability card | ✓ (pass verified) | — | ✓ | ✓ tone classes present (warn/fail not reachable in demo) | — | Pass badge correctly green |
| Export & print | ✓ | ✓ ("Slicing…") | ✓ | ✓ (slice-fail + gate-fail copy) | — | 3MF framing deferred (UX-012) |

All visually reachable states are designed and non-blank — a genuinely strong result. The unreachable states (warn/fail/clarify/render-fail) have their code paths and tone classes in place and are unit-tested per the charter.

## Accessibility snapshot

- **Keyboard navigation:** Good. Buttons/chips/selects are native and reachable; the hero textarea is reachable and its card carries the focus indicator.
- **Focus visibility:** Good. `:focus-visible` accent rings on `.kc-btn`, `.kc-icon-btn`, `.kc-chip`, and selects; `:focus-within` ring on the hero card. This is deliberate and correct.
- **Color contrast:** Mixed. Body/ink (14.66:1) and muted `#6f6857` (5.14 / 4.79 / 4.66 across surfaces) **pass AA for normal text**. Status text passes (pass 4.94, fail 5.59, warn 4.75). **But white-on-accent button text is 3.99:1 and accent-on-surface link/text is 3.70:1 — both fail AA for normal text** (UX-003).
- **Screen reader labeling:** Mostly good — `role="log"` + `aria-live` conversation, label-wrapped selects, `aria-label="Settings"` on the gear, decorative SVGs `aria-hidden`. Weak spot: the canvas label is static and content-free (UX-009).
- **Reduced motion:** **Not handled at all** (UX-007) — auto-rotate, fade-up, and spinner all ignore the preference.
- **Touch target size:** Below the 44px floor on mobile (UX-004).

## Patterns and systemic observations

- **Token system is the project's strongest asset** — exact, centralized in `:root`, and used consistently. Fixes to contrast (UX-003) and touch targets (UX-004) are single-source edits because of this discipline.
- **State-honesty discipline is excellent and systemic** — every component has a real empty + loading + error branch. This is the hardest UX habit to instill and it's already in the codebase's DNA.
- **The viewport is the one surface where the build trails the design** — it's where three of the Major/Minor findings cluster (UX-001/002/009). It's not broken, but it's under-built relative to the print-aware-preview promise. Treat the viewport as the focused investment for the next slice.
- **Two accessibility gaps (contrast, reduced-motion) are surprising given how careful the rest of the a11y work is** — they read as oversights, not philosophy, and are cheap to close.

## Does the rendered UI match the Workshop design?

**Yes on the system, partially on the surfaces.** The palette, type, spacing, radii, topbar, layout, and responsive behavior are faithful to the Workshop direction — measured, not eyeballed. The gaps are: the viewport's missing print-aware affordances + solid-vs-blueprint render (UX-001/002), the bare topbar (no printer chip), the landing badge copy/dot (UX-008), the missing AI avatar (UX-011), and the export card's plainer framing (UX-012). Several of those (printer chip, model picker, Smart Mesh, version rail, refine composer) are deferred-by-charter and correctly absent. The in-scope misses are concentrated and fixable.

## Appendix: surfaces reviewed

- **Server:** `kimcad-web` launch config — `kimcad.cli web --demo --port 8842`, served the built SPA.
- **Routes/views:** landing (`view=landing`), workspace (`view=workspace`) post-design, post-slice export state.
- **Viewports:** 1340×880 (desktop), 375×812 (mobile preset).
- **Components inspected (computed styles / bounding boxes):** `.kc-topbar`, `.kc-badge`, `.kc-hero-title`, `.kc-design-btn`, `.kc-status-badge` (+ class), `.kc-muted-note`, `.kc-input-card`, `.kc-input`, `.kc-icon-btn`, `.kc-chip`, `.kc-viewport-card`/`-canvas`, `.kc-workspace` (grid), `.kc-field`, `.kc-slice-btn`, `.kc-slice-result`, `.kc-connector`.
- **Source cross-referenced:** `frontend/src/styles.css`, `App.tsx`, `components/{Topbar,Landing,Workspace,ChatPanel,RightPanel,ExportPanel,Viewport,ConnectorStatus}.tsx`, `viewport/KCViewport.ts`, `designStatus.ts`.
- **Design reference:** `docs/design/README.md`, `docs/design/screens/06-landing.png`, `09-workspace.png`, `10-smartmesh-report.png`.
- **Contrast:** computed via WCAG relative-luminance in-page; AA thresholds 4.5:1 normal / 3:1 large.
- **Console:** clean (0 errors/warnings) across the full flow.
