# UI/UX Deep-Dive — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Role:** Senior UI/UX Designer
**Scope audited:** Full SPA — first-run wizard, landing/on-ramps, describe→design→refine→sliders→quality→export/slice/send journey, My Designs, Settings (all cards), Part Library modal, keyboard-shortcuts help, sketch on-ramp; light + dark themes; mobile (390×844). Source: `frontend/src/` (App.tsx, components/, styles.css). Visual evidence: 35 walkthrough screenshots in `docs/audits/walkthrough-0.9.0b2-2026-06-14/screens/`.
**Auditor posture:** Balanced

---

## TL;DR

This is a genuinely polished, design-system-driven product whose UI quality is well above the bar for a 0.9 beta. The strongest dimension is **accessibility and state coverage**: nearly every component has designed loading / empty / error / partial states, focus is trapped and restored in modals, contrast is guarded by an automated AA test, reduced-motion and 44px touch targets are handled, and the CSS carries a paper-trail of prior-audit remediations (UX-001…UX-1003). The weakest dimension is a **first-run journey gap**: the example chips the landing page itself suggests fail ~⅔ of the time on the default local model after a ~2-minute wait, and the post-failure workspace leaves "Make it bigger"-style refine chips active with no part to act on. There are no Blockers. The single most important takeaway: the product's craft is excellent, but a new tester's *most likely first action* (clicking a featured example) is also its least reliable path — fix the first 2 minutes and this ships clean.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 2 |
| Minor | 4 |
| Nit | 3 |

## What's working

- **Designed empty states everywhere, not blank screens** — My Designs ("Nothing saved yet." + "Design your first part" CTA, `07-my-designs.png`); Parameters before a design ("The part's adjustable parameters will appear here once it's designed.", `08-generating-40s.png`); Quality with no part ("No part to assess — the last attempt didn't produce a model.", `12-quality.png`); viewport idle ("Your 3D preview appears here.", `09-workspace.png`). This is the most-skipped category in real audits and it is thorough here.
- **The long-wait loading experience is honest and non-trapping** — the "Designing your part…" overlay (`08-generating-40s.png`) pairs a phase label ("Planning the shape"), a 4-dot stepper, a live `0:40 elapsed` mono timer, an honest "This runs on your computer's AI — it can take a few minutes… Nothing leaves your machine" line, and a real **Cancel** button. The overlay is deliberately `pointer-events: auto` with a compound selector so a CSS reorder can never re-trap the user (`styles.css:727`). Esc also cancels (`App.tsx:204`).
- **Error copy is human and actionable** — `designStatus.ts:67` branches every pipeline status into plain language; `plan_failed` reads "I couldn't turn that into a workable plan — the model's response wasn't usable. Try describing the part a little differently, or switch to a model better suited to planning." No raw codes; technical `result.error` is deliberately withheld from the parse-failure path.
- **Accessibility is treated as a first-class concern** — visible skip link (`styles.css:169`, seen in `33-dark-settings.png`), `focus-visible` rings on every interactive class, focus-trap + focus-restore in ConfirmDialog (`ConfirmDialog.tsx:26-63`), `role="alertdialog"`/`aria-modal`, `role="log"` + `aria-live="polite"` on the chat with documented SR-noise mitigations (`ChatPanel.tsx:162`, `Viewport.tsx:252`), InfoTip as a proper disclosure (button + `aria-expanded`/`aria-controls`/`role="note"`, Esc + outside-click dismiss, `InfoTip.tsx`), and a dimensions-aware canvas `aria-label` (`Viewport.tsx:163`).
- **An automated WCAG-AA contrast guard** — `tone-contrast.test.ts` re-computes 4.5:1 for every pass/warn/fail verdict + badge in both themes; the token comments (`styles.css:53-71`) explain the fill-vs-text split (`--kc-accent` 3.99:1 → `--kc-accent-strong` for white-on-accent text). This is rare discipline.
- **Confident, restrained visual system** — warm sand/terracotta with a signature dark 3D viewport in both themes; Bricolage display + Hanken body + JetBrains mono are well-paired; the readiness gauge, version rail, and "Saved" indicator give the workspace a finished, trustworthy feel (`20-real-workspace.png`, `23-real-quality.png`). Dark mode is a true token inversion, not a dimmed light theme (`34-dark-landing.png`, `33-dark-settings.png`).
- **Send-to-printer safety** — the confirm dialog ("Send a test job to 'Mock'? No real printer will run — this only exercises the send path.", `26-real-send.png`) plus the "simulated" connector labeling means a non-CAD user can't accidentally start a real print.
- **Responsive reflow is real, not squashed desktop** — mobile landing stacks input above a full-width CTA and full-width chips (`35-mobile-landing.png`); the topbar wraps and drops the build-volume detail under 480px (`styles.css:257`); settings cards stack cleanly (`36-mobile-settings.png`).

## What couldn't be assessed

- **Live screen-reader output (NVDA/VoiceOver).** Assessed ARIA from source only; the team itself flags this (`ChatPanel.tsx:188` defers fuller live-region scoping to a real SR session). The aria structure is sound on inspection, but the actual announced experience is unverified.
- **Real keyboard-only traversal of the 3-column workspace** (tab order across conversation → viewport → inspector). Inferred from DOM order and per-control `focus-visible`; not walked key-by-key in a live browser.
- **Computed contrast of overlay text on the dark viewport** (e.g. `rgba(255,255,255,0.5)` hint, `0.46` elapsed timer). These are decorative/secondary, but the lowest-opacity ones likely sit below AA — see UX-007.
- **The 320px breakpoint.** Screenshots are at 390px; 320px (small phone) was not captured. CSS targets 420/480/640px so it most likely holds, but it's unverified.
- **Photo on-ramp live** (verified statically; shares the sketch code path).

---

## First impressions

Arriving cold on the landing page (`03-landing.png`), the product passes the 5-second test cleanly. The hero "What do you want to make today?" + sub-copy "Describe a functional part in plain words — I'll design it, check that it's actually printable, and get it ready for your printer. Runs entirely on your machine." tells me exactly what this is, who it's for, and its privacy posture, all without jargon. The eye lands first on the hero, then on the single prominent input card with its terracotta "Design it" button — the one action the product wants. The status badge ("Ready to print in ~15 minutes · no CAD skills") sets honest expectations. The three on-ramps (text primary, photo + sketch secondary) and the "TRY" example chips make the next step obvious. The below-the-fold capability strip reinforces the arc without crowding. It feels friendly, not adversarial: no signup wall, no cookie banner, no upsell.

The one first-impression risk is invisible until you act: the example chips look like the safest possible first click, and on the default model two of the three fail after ~100-140s (UX-001). So the *visual* first impression is excellent; the *behavioral* first impression is the product's weakest point.

A minor note: the disabled "Design it" button (empty input) renders as a washed-out terracotta (`03-landing.png`, `35-mobile-landing.png`) via `opacity: 0.5`. It reads as a primary button that's oddly faded rather than clearly "type something first," which can momentarily confuse a first-timer (UX-006).

## Journey walkthroughs

### Journey: New user → first value (describe → design → check → download)

1. **First-run wizard** (`01-firstrun-or-landing.png`, `02-wizard-step2.png`) — 5 clear steps (Welcome / Set up your AI / Pick your printer / Direct printing / Ready) with Skip/Back/Continue, a progress dot row, and honest model copy ("runs on your CPU, no internet required… the tested default"). Good: skippable, re-openable from Settings, sets `kc-first-run-done`. The wizard renders *over* the landing — a strong, oriented entry.
2. **Landing → describe** — clear primary path (above). Friction only at the chip reliability (UX-001).
3. **Designing** (`08-generating-40s.png`) — best-in-class long-wait handling (see What's working).
4. **Failure path** (`09-workspace.png`, `12-quality.png`) — the failure itself is handled gracefully (error-tone bubble, "No part to assess" cards). But the user is dropped into the *workspace* with refine chips ("Make it bigger / smaller / taller / Thicker walls") and a refine composer active even though no part exists (UX-002). Clicking "Make it bigger" sends that literal string as a fresh design prompt with the failed history — almost certainly another ~2-minute failure. This is a dead-end-shaped trap dressed as a recovery path.
5. **Success** (`20-real-workspace.png`) — excellent. Version rail ("v1 — refine to create versions you can step back to"), "Saved" indicator, readiness badge ("Passed · Readiness 92"), dimensioned 3D preview with orientation chip + Measure tool, refine chips, and a parameter panel with mm/in toggle and click-to-type values that re-render locally ("Drag or click a value to type — the part re-renders locally, no AI round-trip").
6. **Quality** (`23-real-quality.png`) — a readiness gauge (92, "Ready to print"), confidence badge, and a Printability checklist as scannable ✓ tiles. The product's trust moment reads at a glance.
7. **Export → slice → send** (`24-real-export.png`, `25-real-sliced.png`, `26-real-send.png`) — a "your design → sliced → print file ready" flow strip, broken-out stats (time/layers/filament/weight) with an honest density caveat, Download .3mf + Copy link, and the no-accidental-print confirm. Clean close to the journey.

### Journey: Return visit (persistence → reopen → refine)

My Designs persists across a fresh browser session; reopen restores the part with sliders and seeds v1 so the user can refine into v2 (`30`–`32`, `App.tsx:578`). The reopen uses a distinct "Reopening your design…" overlay (no timer/Cancel) vs. the design overlay — a thoughtful distinction (`Viewport.tsx:225`). No dead ends on return.

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion / IA

### [UX-001] — Critical — Journey — Featured example chips fail ~2 of 3 on the default model after a 100–140 s wait

**Evidence**
Landing → click a "TRY" example chip (`03-landing.png`) → `Landing.tsx:9-13` (`EXAMPLES`) submits the chip text verbatim via `onSubmit`. On the default `gemma4:e4b`, "a 40 mm desk cable clip" and "a wall-mounted holder for a 1 kg filament spool" return `plan_failed` after ~140 s / ~100 s respectively (`09-workspace.png` — the graceful failure UI); the control "a round coaster 90 mm across and 4 mm thick" succeeds in ~40 s (`20-real-workspace.png`). Corroborated by the walkthrough (W-F-001) and reproduced here from the chip definitions.

**Why this matters**
A new beta tester's most natural first action is clicking a suggested example — the product is *recommending* these. On the default config that means a ~2-minute wait followed by a failure roughly two-thirds of the time. The loading and failure states are individually excellent, which makes this worse, not better: the user sees a beautifully honest "couldn't turn that into a workable plan" after investing two minutes on the app's own suggestion, and concludes the product doesn't work — when in fact it works well on dimensioned prompts. This shapes the first impression of every new tester and is the single highest-leverage UX fix in the build.

**Blast radius**
- Adjacent code / pages using the same pattern: `EXAMPLES` in `Landing.tsx:9`; the Part Library seeds (`LibraryModal.tsx`) and any wizard sample prompts share the "suggested prompt → default model" assumption and should be spot-checked the same way. The placeholder text ("e.g. a wall-mounted holder for a 1 kg filament spool", `Landing.tsx:128`) is one of the failing prompts — even users who type rather than click are nudged toward it.
- User-facing: directly affects first-run activation; every new tester is exposed.
- Tests to update: no test runs the *real default model* against the *shipped chips* (the e2e suite runs `--demo` with a canned part, so it can't catch this). Add a real-model CI canary that plans each shipped chip and asserts a usable result, or a curation guard.
- Related findings: UX-002 (the failure drops you into a workspace with meaningless refine affordances), and the walkthrough's W-F-001 / test-gap note.

**Fix path**
Cheapest, highest-impact: **curate the example chips (and the placeholder) to prompts the default model reliably fulfills** — dimensioned, template-mapped, coaster-style. Concretely, replace the current three with vetted ones, e.g.:
- "a round coaster 90 mm across and 4 mm thick" (known-good)
- "a 60 × 40 × 25 mm open-top box, 2 mm walls"
- "a 20 mm cable clip with a 6 mm screw hole"

Then add a CI guard that fails the build if any shipped chip can't be planned by the default model. Secondary, non-exclusive options for the dev/product call: ship/recommend a stronger default planning model; add a plan-parse retry/repair pass; bias the planner toward the template catalog for short prompts. Curation alone closes the first-impression wound this sprint.

---

### [UX-002] — Major — State / Journey — After a failed design, refine chips and composer act on a non-existent part

**Evidence**
Workspace after a `plan_failed` result (`09-workspace.png`): no mesh is framed ("Your 3D preview appears here.", Parameters reads "No part was produced…"), yet the left column shows "Refine by talking" with chips **Make it bigger / Make it smaller / Make it taller / Thicker walls** and an active refine composer. Root cause: `ChatPanel.tsx:137` — `hasResult = result !== null || (messages.length > 0 && !busy)`, and `canRefine = hasResult && !busy`. After a failure there's no `result` mesh but there *are* messages, so the refine UI renders. Clicking "Make it bigger" routes through `handleRefine` → `runDesign("Make it bigger", history, undefined)` (`App.tsx:448`), submitting the chip text as a fresh design prompt with the failed conversation as history.

**Why this matters**
The chips are universal *edits* to an existing part ("bigger", "taller", "thicker walls"). With no part on screen they are semantically meaningless, and firing one sends the user into another ~2-minute model run that is very likely to fail again — a recovery path that is actually a loop. The genuinely useful recovery (re-describe the part more specifically, or try the experimental generator) is available via the composer, but the chips visually dominate it and mislead. This converts a graceful single failure (UX-001) into a frustrating multi-failure session.

**Blast radius**
- Adjacent code: `ChatPanel.tsx:248-311` (the `canRefine` block and the chip array at `:262`); the `model_unavailable` and `needs_experimental` branches already render *targeted* recovery affordances (`ChatPanel.tsx:204-233`) — `plan_failed`/`render_failed` should do the same instead of the generic chips.
- User-facing: every user who hits a design failure (frequent on the default model — UX-001) sees this.
- Tests to update: `ChatPanel.test.tsx` — add a case asserting the geometric refine chips are hidden when the latest result has no mesh; assert a re-describe/clarify affordance shows instead.
- Related findings: UX-001 (failures are common, amplifying this), and the existing `clarification_needed` branch which already correctly hides the chips (`ChatPanel.tsx:254`) — extend that gating to failure statuses.

**Fix path**
Gate the geometric refine chips on "a part is actually framed," not merely "messages exist." Recommend: hide the four edit chips when `result?.has_mesh` is false (mirroring the existing `clarification_needed` suppression), and when the last result is a `plan_failed`/`render_failed`, replace them with the recovery-oriented affordance the product already has elsewhere — a one-line prompt + a "Describe it differently" hint, and (where applicable) the "Try the experimental generator" button. Keep the composer, but change its placeholder for the failure case to "Describe the part again, with sizes — e.g. '90 mm coaster, 4 mm thick'".

---

### [UX-003] — Major — Accessibility / Pattern — Viewport interaction is mouse/touch-only; no keyboard path to rotate, zoom, or measure

**Evidence**
The 3D viewport (`Viewport.tsx`, `KCViewport.ts`) exposes "Drag to rotate · scroll to zoom" and a click-to-measure tool (`20-real-workspace.png`). The canvas has a descriptive `aria-label` (good) but no keyboard handlers and no documented keyboard alternative for orbit/zoom/measure. The Measure toggle is a real focusable button, but the act of measuring requires clicking two points on the canvas with a pointer.

**Why this matters**
For a product explicitly aimed at *non-CAD users*, inspecting the part in 3D is part of the core "is this what I wanted?" trust moment. A keyboard-only or switch-access user can reach the workspace, read dimensions (via the aria-label and the right-panel data), slice, and download — so the *task* is completable, which keeps this out of Blocker territory. But they cannot orbit, zoom, or measure, so a meaningful slice of the value (visual verification) is closed to them. Per WCAG 2.1, 2.1.1 (Keyboard) applies to functionality; orbit/zoom currently has no keyboard equivalent.

**Blast radius**
- Adjacent code: `Viewport.tsx` (add keydown handlers on the canvas wrapper), `viewport/KCViewport.ts` (expose `rotateBy`/`zoomBy`/programmatic measure), the viewport hint string (`Viewport.tsx:216`) to advertise the keys.
- User-facing: keyboard-only and assistive-tech users on the workspace; also benefits power users (arrow-key nudge orbit).
- Tests to update: `Viewport.test.tsx` / `KCViewport.test.ts` — add keyboard-orbit assertions.
- Related findings: none direct; complements the otherwise-strong a11y posture, so closing it raises the whole product to a consistent bar.

**Fix path**
Make the canvas (or its stage wrapper) focusable (`tabIndex=0`) with a visible focus ring, and bind arrow keys to orbit, +/− (or PageUp/Down) to zoom, and Home to reset framing. Update the viewport hint to mention "or use arrow keys" when focused. Measure can stay pointer-first for now (document it as a known limitation), but orbit/zoom keyboard support is the meaningful win. Confirm the auto-rotate already respects `prefers-reduced-motion` (the CSS suggests it does — `styles.css:1004`).

---

### [UX-004] — Minor — Responsive — 320px small-phone breakpoint unverified; densest surfaces are the risk

**Evidence**
Mobile evidence is at 390×844 (`35-mobile-landing.png`, `36-mobile-settings.png`). CSS breakpoints target 420/480/560/640/720/820/1000/1140/1320px (`styles.css` passim) but not 320px. The densest surfaces — the Settings connections cards (env-var help text, monospace addresses) and the slider rows with inline value editors — are where a 320px viewport is most likely to wrap awkwardly or push a control off-edge.

**Why this matters**
320px is the iPhone SE / small-Android floor and a standard responsive checkpoint. The layout very likely holds (chips and inputs are full-width and stack), but the dense Settings forms and the parameter value-edit popover (`kc-pval-err` absolutely positioned, `styles.css:1409`) are unverified at the narrowest width, where horizontal overflow or a clipped error tooltip would be most likely.

**Blast radius**
- Adjacent code: `SettingsPanel` / `ConnectionsCard` cards; the slider value-edit inline error (`styles.css:1409`).
- User-facing: small-phone users (a minority for a desktop-first CAD tool, hence Minor).

**Fix path**
Spot-check the landing, workspace, Settings connections, and the slider value-edit popover at 320px; add a 320px row to any visual-regression matrix. No code change expected if it already holds — but verify rather than assume.

---

### [UX-005] — Minor — Accessibility — Settings AI-model card uses warn-amber as the *only* signal for "needs attention"

**Evidence**
`SettingsPanel.tsx:31-40` maps model state to a tone (`ok`/`warn`) and a dot + label. In the healthy case the dot is green and the label "Running"/"Ready"; in the unhealthy case amber + "Not running"/"Model not pulled". The label text *does* differ (good — not color-only). The residual concern is the status *dot* and tint carrying the at-a-glance meaning, and amber-on-warm-tint for the dot relying on hue discrimination. The verdict/badge *text* is AA-guarded (`tone-contrast.test.ts`), but the small status dots are not part of that guard.

**Why this matters**
Color-blind safety: a deuteranope scanning the Settings AI card for "is my model OK?" leans on the dot color. The accompanying text label saves it from being a hard failure, but the primary scannable cue (dot) is hue-only. This is a Minor because the text equivalent exists adjacent.

**Blast radius**
- Adjacent code: status-dot classes `.kc-status-dot.kc-tone-*` (`styles.css:1906`), the connector dots (`ConnectorStatus.tsx`), the printer chip dot.
- User-facing: color-blind users reading any dot-based status.

**Fix path**
Pair each status dot with a tiny shape/glyph differentiator (e.g. ✓ vs ! inside the dot, as the Printability checks already do with ✓/⚠ tiles, `styles.css:2372`) so status is shape+color, not color alone — and extend the contrast guard to cover the dot tones.

---

### [UX-006] — Minor — Visual hierarchy / Copy — Disabled primary CTA reads as a faded button rather than "type something first"

**Evidence**
Landing "Design it" button when the input is empty (`03-landing.png`, `35-mobile-landing.png`): `disabled={busy || value.trim() === ''}` (`Landing.tsx:141`) + `.kc-btn:disabled { opacity: 0.5 }` (`styles.css:297`). The result is a washed-out terracotta primary button with no explanation of why it's inert.

**Why this matters**
A first-timer who hasn't yet typed sees the product's single primary action looking broken/faded. There's no microcopy tying the disabled state to "describe a part first." Low severity because the adjacent placeholder ("e.g. a wall-mounted holder…") implies the input, and typing immediately enables it — but the moment is a small avoidable friction at the exact spot the product most wants momentum.

**Blast radius**
- Adjacent code: the same disabled-primary pattern recurs on the refine **Send** (`ChatPanel.tsx:295`) and the slice/export actions — consistent, so any fix should be a shared treatment.
- User-facing: every first-time landing view before typing.

**Fix path**
Either (a) keep the button visually "ready" (full color) and let the no-op-on-empty submit show an inline hint ("Describe a part to design it"), or (b) keep it disabled but add a one-line helper under the card on the empty state. Lowest-effort: a brief tooltip/aria-describedby on the disabled button ("Describe a part above to enable"). Ensure the disabled state still meets non-text-contrast expectations or is clearly communicated by text, since disabled controls are exempt from contrast but shouldn't *look* like the primary action merely dimmed.

---

### [UX-007] — Minor — Accessibility / Contrast — Lowest-opacity viewport overlay text likely sits below AA

**Evidence**
Viewport overlay/hint text uses white at low alpha on the dark viewport (`#14171c`): the drag hint `rgba(255,255,255,0.5)` (`styles.css:888`), the elapsed timer `rgba(255,255,255,0.46)` (`styles.css:784`), the busy sub-copy `0.6` (`styles.css:779`). At 0.46–0.5 alpha over a near-black background the effective contrast is roughly ~5–6:1 — but the *lowest* ones and any text over a *framed light part* (during refine) are the risk. The contrast guard (`tone-contrast.test.ts`) covers status tones on surfaces, not these overlay strings.

**Why this matters**
The drag hint and elapsed timer are secondary/decorative, so this is Minor. But "it can take a few minutes" busy sub-copy and the dimension pills are informational; if any dips below 4.5:1 (normal text) it's a real legibility miss for low-vision users during the longest wait in the app.

**Blast radius**
- Adjacent code: `.kc-viewport-hint`, `.kc-busy-elapsed`, `.kc-busy-sub`, `.kc-dim-pill`, `.kc-viewport-overlay` (`styles.css:704-892`).
- User-facing: anyone reading the viewport during a design/refine.

**Fix path**
Sample each overlay string against `#14171c` with a checker; raise any below 4.5:1 (informational) / 3:1 (large) to compliant alpha, and add a couple of these combinations to the existing contrast test so they're guarded going forward. The busy sub-copy and dimension pills should clear 4.5:1; the pure-decorative drag hint can stay lighter.

---

### [UX-008] — Nit — Copy — "Designing your part…" vs "Reopening your design…" mixes part/design nouns

**Evidence**
The busy overlay says "Designing your part…" (`Viewport.tsx:233`) and the reopen overlay "Reopening your design…" (`Viewport.tsx:228`); the thread thinking-row says "Refining your part…" (`ChatPanel.tsx:197`). "Part" and "design" are used somewhat interchangeably across surfaces.

**Why this matters**
Trivial, but a consistent noun ("part" for the physical object, "design" for the saved record) would read marginally cleaner. Both are clear in context; this is a preference-level polish item.

**Fix path**
Pick one mental model — "part" = the thing being made, "design" = the saved/reopenable artifact — and apply consistently. Current usage is already close to that; only "Reopening your design…" vs "Designing your part…" sits side by side.

---

### [UX-009] — Nit — Visual hierarchy — "TRY" eyebrow label is easy to miss beside the chips

**Evidence**
Landing example chips (`03-landing.png`): the "TRY" label (`kc-examples-label`, uppercase 11px muted, `styles.css:493`) sits inline-left of the chip row and is visually quiet next to the pill chips.

**Why this matters**
Minor scannability: the chips read as standalone tags rather than clearly "examples to try." Not a real defect; the chips are obviously clickable. (Note: if UX-001's curation lands, this label points at *reliable* examples and matters slightly more.)

**Fix path**
Optional — bump the label weight/contrast a touch, or move it above the row as a quiet "Try one of these". Pure preference.

---

### [UX-010] — Nit — Motion — WebGL `readPixels` console warnings add noise

**Evidence**
Repeated `GL Driver Message (… GPU stall due to ReadPixels)` performance warnings on any viewport screen (per the walkthrough W-F-003; self-limiting). Not user-visible.

**Why this matters**
Console-only; harmless to users but can mask real warnings for developers. Out of strict UI/UX scope but noted for completeness since it touches the viewport (likely the thumbnail capture / measure pick readback).

**Fix path**
Throttle/cache the readback or render-to-target off the present path. Engineering-side; no UI change.

---

## States audit matrix

| Component / page | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| Landing | ✓ | ✓ (busy disables input) | ✓ (idle hero) | ✓ (ModelHealthPill warns pre-submit) | — | Strong; UX-006 disabled-CTA nit |
| Viewport | ✓ | ✓ (rich busy overlay + reopen variant) | ✓ ("preview appears here") | ✓ ("Could not load") + stale-note partial | ✓ (stale preview kept) | Best-in-class loading; UX-003 keyboard gap |
| Parameters | ✓ | ✓ ("Updating…") | ✓ (pre-design + post-fail copy) | ✓ (inline value error) | ✓ | Click-to-type + units; solid |
| Quality (Readiness/Printability) | ✓ | ✓ | ✓ ("No part to assess…") | ✓ | ✓ | Gauge + ✓/⚠ tiles; excellent |
| Export/Slice/Send | ✓ | ✓ | ✓ (pre-slice) | ✓ (`kc-export-error`) | ✓ (stats) | Confirm dialog; honest caveats |
| ChatPanel (conversation) | ✓ | ✓ (think row) | ✓ ("conversation will appear here") | ✓ (error-tone bubble) | ✓ | UX-002: refine chips show with no part |
| My Designs | ✓ | ✓ (list) | ✓ ("Nothing saved yet" + CTA) | ✓ | — | Model empty state |
| Settings | ✓ | ✓ (model/health probes) | n/a | ✓ ("Couldn't load your settings") | ✓ (independent card loads) | Dense; UX-005 dot color |
| Part Library modal | ✓ | ✓ | ✓ (search no-results assumed) | — | — | Searchable, tier badges; verify empty-search |
| First-run wizard | ✓ | — | n/a | — | — | Skip/Back/Continue, re-openable |

## Accessibility snapshot

- **Keyboard navigation:** Strong for chrome and modals — global shortcuts (?, N, D, ,, Esc) that correctly *don't* fire while typing (`App.tsx:213`), focus-trapped + focus-restoring dialogs (`ConfirmDialog.tsx`, ShortcutsHelp, FirstRunWizard), `focus-visible` rings on every interactive class. **Gap:** the 3D viewport has no keyboard orbit/zoom (UX-003). Full key-by-key workspace traversal not live-verified.
- **Focus visibility:** Consistent 2px accent outline with offset across buttons, chips, icon-buttons, sliders (offset 4px), selects, value-edit, skip link. Strong.
- **Color contrast:** Body ink `#272219` on surfaces ≈ 13:1+. Status verdict/badge text AA-guarded by `tone-contrast.test.ts` in both themes; token comments document the accent fill-vs-text split. **Watch:** low-alpha viewport overlay text (UX-007); status dots are hue-only (UX-005).
- **Screen reader labeling:** Icon buttons and glyphs `aria-hidden`; canvas has a dimensions-aware label; chat is a polite log with documented anti-spam scoping; InfoTip is a proper disclosure. Inferred-sound; **not live-tested** (the team flags this too).
- **Reduced motion:** Honored globally (`styles.css:1006`) — animations/transitions reduced; viewport auto-rotate disabled. Good.
- **Touch target size:** 44px floors applied broadly under `pointer: coarse` OR `max-width: 640px` (slider, unit toggle, value-edit, My Designs actions, help button), with the destructive Delete pushed to row-end to avoid mis-taps. Notably thorough.

## Patterns and systemic observations

- **The CSS is an audit ledger.** Nearly every rule cites a prior finding ID (UX-001…UX-1003, ENG, QA, MS, KC) and explains the reasoning. This is a sign of a team that audits and remediates rigorously — the residual findings here are genuinely the edges that remain, not systemic neglect.
- **"Suggested action vs. default-model capability" is the one cross-cutting gap.** UX-001 (chips), the placeholder text, and library seeds all share the assumption that *recommended prompts work on the shipped default*. That assumption is unguarded by tests and is the root of the weakest first-run moment. A single curation + CI-guard fix addresses the class.
- **Failure-recovery affordances are inconsistent by status.** `model_unavailable` and `needs_experimental` get *targeted* recovery buttons; `plan_failed`/`render_failed` fall back to generic geometric chips that don't fit (UX-002). Unifying recovery on a "no mesh → re-describe/experimental, never geometric-edit" rule closes the gap.
- **Two-theme discipline is real.** Dark mode is token inversion with preserved AA splits, not a dimmed copy — and the contrast guard runs against *both* themes.

## Appendix: surfaces reviewed

- Routes/screens: `#/` landing, `#/design/<id>` workspace (design/refine/sliders/quality/export/slice/send), `#/designs` My Designs, `#/settings`, first-run wizard, Part Library modal, keyboard-shortcuts help, photo/sketch on-ramps.
- Components: App.tsx, Landing, ChatPanel, Viewport (+ KCViewport), Workspace, RightPanel, ExportPanel, SendPanel, SettingsPanel, ConnectionsCard, ConnectorStatus, MyDesigns, LibraryModal, FirstRunWizard, ShortcutsHelp, ConfirmDialog, InfoTip, ModelHealthPill, Topbar, VersionRail; styles.css (4368 lines); designStatus.ts; tone-contrast.test.ts.
- Viewports: 390×844 (mobile, captured), ~1280×850 (desktop, captured), dark + light themes. **Not captured:** 320px, 768px tablet, 1440px+.
- Screenshots: `docs/audits/walkthrough-0.9.0b2-2026-06-14/screens/` 01–41 (35 PNGs).
