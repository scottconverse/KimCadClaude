# UI/UX Deep-Dive — KimCad Stage 8.5 (Usability) stage gate

**Role:** Senior UI/UX Designer (audit-team, 5-role)
**Date:** 2026-06-05
**Scope:** repo `C:\Users\scott\dev\kimcad`, branch `stage-8.5-usability` @ `95b25e0`
**Surfaces:** Landing · Workspace (Chat | Viewport | RightPanel: Parameters/Readiness/Printability/Export) · My Designs · Settings · FirstRunWizard · PhotoOnramp · VersionRail · InfoTip glossary · Slice-10 print summary · Slice-11 shortcuts modal
**Method:** audit-only (no source modified). Based on (a) the completed runtime wiring-audit evidence (`wiring-audit-stage-8.5-2026-06-05.md` — a11y tree, computed styles, network proofs), (b) a close read of `frontend/src/components/*` + `styles.css`, and (c) the Workshop design reference in `docs/design/` (README, screen PNGs, `prototype/jsx/*`).
**Design system:** Workshop (warm sand `#f0ebe0` / terracotta `#c8623a` / dark `#14171c` viewport). UX is the project's #1 priority (owner is ex-Apple).

---

## Verdict at a glance

This is a genuinely well-made consumer UI. The Workshop tokens are recreated faithfully, accessibility has been treated as a first-class concern (not bolted on), state coverage is unusually complete (loading / empty / error / disabled / partial all exist and are designed), and the copy is plain-English with real craft. The team clearly internalized "no dead ends." Against an Apple-level bar it is **close but not yet there**: a handful of visual-hierarchy and IA gaps keep the workspace feeling like three stacked panels rather than one composed product, and several high-fidelity affordances from the design reference (the icon-tile Printability checks, the in-viewport refine chips, the orientation "change" action) were flattened or dropped. None of those is a Blocker; the core journey works end to end.

**Severity counts**

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 6 |
| Minor | 9 |
| Nit | 5 |
| **Total** | **20** |

No Blockers. No Criticals. The Majors are quality/coherence/fidelity issues, not "users can't complete the task."

---

## What's working (specific credit)

- **Accessibility is real, not theater.** Both modals (`FirstRunWizard`, `ShortcutsHelp`) implement a genuine Tab focus-trap *and* focus restore on close (`ShortcutsHelp.tsx:21,52` saves/returns `previouslyFocused`). `:focus-visible` accent rings are applied consistently across virtually every interactive class in `styles.css`. Color is never the sole cue: risk rows carry an SR-only severity word (`RightPanel.tsx:347` `RISK_TONE_WORD`), and the off-dimension table row adds a `⚠` glyph next to the red (`RightPanel.tsx:561`). `prefers-reduced-motion` is honored globally (`styles.css:781`) and in the 3D auto-rotate. `aria-live` regions are used with restraint and correctly — the per-second elapsed tick is deliberately `aria-hidden` so it doesn't chant in a screen reader (`Viewport.tsx:205`, UX-801), while the infrequent phase label is `aria-live="polite"`. This is thoughtful, senior-level a11y.
- **State coverage is close to complete.** Every right-panel card has a designed idle/empty placeholder, a failure message distinct from idle, and the populated state (`RightPanel.tsx` Parameters/Readiness/Printability; `ExportPanel.tsx`). The viewport has Rendering / empty / hard-error / busy-with-cancel / reopening / stale-preview states (`Viewport.tsx:145,177`). My Designs has loading / empty-welcoming / no-search-match / error (`MyDesigns.tsx:311-329`). This is exactly the discipline the audit methodology asks for.
- **The "Designing…" screen is honest and never a trap.** It is interactive (Cancel stays clickable via a compound `pointer-events:auto` selector that beats source-order, `styles.css:567`), shows a live phase stepper + plain-language labels ("Planning the shape" → "Checking it for printing", `designPhase.ts:10`), an elapsed timer, and an honest "runs on your computer's AI — can take a few minutes" line. Escape also cancels. For a multi-minute local-model run this is the right design.
- **Copy is plain-English and jargon-aware.** The InfoTip glossary (`glossary.ts`) defines manifold-adjacent terms (gate, readiness, printability, risks, confidence) in concrete, jargon-free language, surfaced as in-context "(i)" disclosures next to the term. `humanizeObjectType` strips slugs to words (`objectType.ts`). Error copy is actionable, e.g. the re-render failure: "That change didn't render — your last version is still here. Nudge a slider to try again." (`RightPanel.tsx:289`).
- **Destructive-action care.** Delete is two-step (arm → confirm, auto-disarms after 3.5s, `MyDesigns.tsx:42`), and on touch the Delete action is pushed to the row end so a fingertip reaching for Export can't hit it (`styles.css:729`). Slicing G-code/sending is gated. This matches the spec's safety posture.
- **Auto-save is reassurance, not celebration.** The Topbar "Saving… / Saved · My Designs / Couldn't save — retrying" indicator (`Topbar.tsx:57`) is quiet, self-healing, and links to the user's work. The right tone for a background concern.
- **Touch targets are handled with belt-and-suspenders rigor.** The team correctly noticed that a desktop browser resized to 375px reports `pointer: fine`, so every 44px floor is duplicated under `(pointer: coarse), (max-width: 640px)` and the slim switch/slider grow only their *hit area* via content-box clipping (`styles.css:735,2681`). Genuinely sophisticated.

---

## Findings

### UX-001 (Major) — Visual hierarchy: the workspace reads as three flat lists, not one composed product
**Category:** Visual hierarchy / Pattern fidelity
**Evidence:** `RightPanel.tsx` (Parameters/Readiness/Printability/Export are four identical `.kc-card` blocks, `styles.css:803`); design reference `screens/09-workspace.png` + `screens/10-smartmesh-report.png`; wiring-audit computed-styles section.
**What the user sees:** Four visually identical cards stacked in the right column with equal weight — Parameters, Readiness, Printability, Export each get the same surface, the same 16px radius, the same 15px title. In the design reference, the Smart Mesh readiness card has an **accent-tinted gradient background** and the Print report card an **accent-tinted border** (README §7), giving the column a clear read order: *tune → here's the verdict (emphasized) → the details → act*. Shipped, every card is the same flat sand surface, so the most important thing on the screen (the print-readiness verdict + score) carries no more visual weight than the parameter sliders above it.
**Why this matters:** Visual hierarchy is the single biggest "does this feel designed" signal, and it's the owner's stated #1 axis. A first-time maker's eye should land on the readiness gauge ("can I print this?"); instead it lands nowhere in particular. The gauge is well-built (`ScoreGauge`, `RightPanel.tsx:353`) but it's buried in a uniform stack.
**Blast radius:**
- Adjacent code: the `.kc-card` class is shared by all four right-panel cards plus `ExportPanel`'s empty card. A tint/border treatment must be applied per-card (a `.kc-card-readiness` / `.kc-card-report` modifier), not globally, or it'll wash the whole column.
- User-facing: every workspace view; directly affects the "is this designed?" first impression.
- Migration: none (CSS only). Tests: none assert card background; safe. Related: UX-002, UX-005.

### UX-002 (Major) — Pattern fidelity: the Printability card was flattened from designed icon-tile checks to a bare bullet list
**Category:** Pattern fidelity / Visual hierarchy
**Evidence:** `RightPanel.tsx:528-591` (`PrintabilityCard`) renders `report.findings` as a flat `<ul className="kc-findings">` of text with a small colored dot (`styles.css:1544`). Design reference `prototype/jsx/panels.jsx:162-200` + `screens/09`: each check is a **19px status-icon tile** (✓ / ⚠) + a bold label + a muted detail line ("Dimensions match plan / 70 × 49 × 150 mm", "Fits the build plate / Bambu Lab P1S · 256×256×256 mm", "Wall thickness OK / 4.0 mm · 10.0× nozzle").
**What the user sees:** Instead of the scannable, icon-led checklist the reference promises — where pass/warn reads at a glance from the icon and each row has a label/detail pair — the shipped card shows a one-line bullet per finding with a tiny dot. The dims table (`RightPanel.tsx:545`) covers target-vs-actual well, but the *check rows* themselves lost their structure. The Material segmented control that lived inside this card in the reference (PLA/PETG/TPU/ABS, `panels.jsx:173`) is gone from here entirely (material now lives only in the Export card's `<select>`).
**Why this matters:** The printability check is the product's core trust moment — "is this actually printable?" The reference made it a confident, glanceable verdict list; the shipped version reads like log output. This is a fidelity regression against an explicitly high-fidelity design source on the most important card in the app.
**Blast radius:**
- Adjacent code: `kc-findings`/`kc-finding-*` (`styles.css:1535`), `report.findings` shape from the backend. Adding label/detail tiles needs the backend finding to carry a label + detail (it may only carry `message` today — check the `/api/design` payload before committing the UI).
- Shared assumption: Material selection — moving/duplicating it back into the gate card means deciding the single source of truth (today it's `ExportPanel` local state). Don't end up with two material controls.
- User-facing: every sliced/checked part. Tests: `RightPanel.test.tsx` asserts on findings text; will need updating. Related: UX-001.

### UX-003 (Major) — Journey/IA: the in-viewport refine chips and orientation "change" action from the design reference are missing
**Category:** Journey / Discoverability / Pattern fidelity
**Evidence:** Design reference `screens/09`, `prototype/jsx/panels.jsx:96-101` (the composer refine-chip row: "Make it wider", "Thicker walls", "Make it taller", "Add a hook") and `screens/09` the viewport "Auto-oriented · plate-down · **change**" chip. Shipped: `ChatPanel.tsx:240-268` is a bare textarea + Send (no quick-refine chips); `Viewport.tsx:167` renders "Auto-oriented · plate-down" as a **non-interactive** chip (`pointer-events:none`, `styles.css:680`) with no "change" affordance.
**What the user sees:** The reference taught the user how to refine by offering one-tap chips ("Make it wider") right where they type — the single most important discoverability cue for the refine-by-talking feature, which is otherwise an empty text box the user has to *guess* how to use. Shipped, the refine input's only guidance is its placeholder ("make it 10mm taller", "add mounting holes"). And the orientation chip *says* "Auto-oriented · plate-down" but offers no way to change it, even though the reference made "change" a link.
**Why this matters:** Refine-by-conversation is a headline Stage 8.5 capability (Slice 2). Without the chip scaffolding, a non-technical user faces a blank box and may not realize they can just talk to it. The chips are a 30-minute add that materially raises feature discoverability. The dead "change" word on the orientation chip is a small honesty problem — it implies an action that doesn't exist.
**Blast radius:**
- Adjacent code: `ChatPanel.tsx` refine composer; chips would call the existing `onRefine`. The orientation "change" needs a real re-orient flow or the word should be dropped (don't ship a label that promises an unbuilt action).
- User-facing: every workspace refine. Migration: none. Tests: `ChatPanel.test.tsx` would gain chip coverage. Related: UX-010 (placeholder is the only guidance).

### UX-004 (Major) — Responsive: the stacked mobile workspace buries the right-panel verdict below a tall viewport, with no in-page nav
**Category:** Responsive / Journey
**Evidence:** `styles.css:460-474` — at ≤1000px the 3-column grid stacks to `auto / minmax(240px,42vh) / auto` (chat, then viewport, then right panel) and the whole workspace becomes one vertical scroll. The viewport reserves up to 42vh; the right panel (Parameters → Readiness → Printability → Export, four cards) sits entirely below it.
**What the user sees:** On a phone, after designing a part the user sees: the conversation, then a ~42vh-tall dark viewport, and must scroll *past all of it* to reach the readiness verdict and the Slice/Download actions. There's no tab bar, no jump-to-section, no sticky "Slice" CTA. The primary outcome (get my file) is the furthest thing from the top.
**Why this matters:** On mobile the linear stack inverts the priority — the action the user came for (check + download) is at the bottom of a long scroll, behind a large viewport that's the *least* actionable element. The reference is desktop-first (README acknowledges "the prototype is mouse-first; build a11y/responsive in"), so this is net-new design work that landed as "make the columns stack" rather than "rethink the phone layout." Consider a segmented Chat / 3D / Details switcher or a sticky bottom action bar carrying the slice/download CTA.
**Blast radius:**
- Adjacent code: `.kc-workspace` grid + the ≤1000px media block (`styles.css:460`); a mobile nav/sticky-CTA is new structure in `Workspace.tsx`.
- User-facing: all touch/narrow users on the core flow. Migration: none. Tests: none cover mobile layout (a gap — flag to Test Engineer). Related: UX-001 (hierarchy), QA mobile pass.

### UX-005 (Major) — Discoverability: keyboard shortcuts exist but are effectively undiscoverable; no visible "?" entry point
**Category:** Discoverability / Accessibility
**Evidence:** `App.tsx:188-228` binds n / d / , / ? globally; `ShortcutsHelp.tsx` is a polished modal — but the *only* way to learn any of this is to already know to press "?". There is no "?" button in the Topbar, no hint anywhere in the chrome, and (per the wiring-audit) the shortcuts can't even be triggered from the preview harness's isolated world.
**What the user sees:** A genuinely nice shortcuts system (with a focus-trapped, focus-restoring help modal) that a normal user will never find. Power-user shortcuts are a credit; *hidden* power-user shortcuts deliver almost none of their value.
**Why this matters:** Apple-bar products surface their shortcuts (a "?" affordance, a Help menu, or a hint on hover). The cost-to-build was paid; the cost-to-discover wasn't. A single quiet "?" icon-button in the Topbar (mirroring the gear) that opens the same modal would convert a hidden feature into a real one. As a bonus it gives mouse-only users a path to the same help.
**Blast radius:**
- Adjacent code: `Topbar.tsx` (add a `?`/Help icon-button → calls `setShowShortcuts(true)` lifted from `App.tsx`); `App.tsx` already owns the state. User-facing: all users. Migration: none. Tests: `Topbar.test.tsx` + `App.test.tsx`. Related: the wiring-audit's harness note (a real-browser e2e for the keyboard flow is still owed).

### UX-006 (Major) — IA/Fidelity: the Topbar dropped the printer-status chip and model picker the design centered the chrome on
**Category:** Information architecture / Pattern fidelity
**Evidence:** `Topbar.tsx` renders brand + save indicator + My Designs + Settings + New design. Design reference README "Global Layout & Chrome" and `screens/06/09/10`: the top bar's right cluster is **printer chip (green dot + name + build volume in mono) → model picker → settings gear → New design**. The shipped Topbar comment even acknowledges this ("the live printer-status chip [is a] later Stage 8.5 slice — absent until built rather than [a] dead control", `Topbar.tsx:5`).
**What the user sees:** The persistent "which printer am I targeting, and is it connected?" context that anchored the reference's chrome is gone from the top bar. The printer is now only visible/selectable deep inside the Export card's `<select>` and in Settings. The model identity (gemma4:e4b) only appears in Settings + wizard.
**Why this matters:** The printer chip was an always-on orientation cue — it told the user, on every screen, what their parts are being checked against (build volume), which is core to the "is this printable" mental model. Burying it in a select inside one card weakens that. (This is correctly *not* a dead control — the team chose absence over fakery, which is the right call — but as a stage *gate* the chrome is materially less informative than the design it's being measured against.) Note: the model picker should remain a status readout, not a menu of alternatives, per the project's settled model rule — a "Bambu P2S · 256³" chip is the ask, not a Qwen-vs-Gemma toggle.
**Blast radius:**
- Adjacent code: `Topbar.tsx`; data already exists (`/api/settings` default_printer + volume, `/api/model-status`). User-facing: every screen's chrome. Migration: none. Tests: `Topbar.test.tsx`. Related: UX-002 (where material/printer live), Settings.

### UX-007 (Minor) — Landing badge + sub copy drift from the design reference's promise
**Category:** Copy
**Evidence:** Shipped `Landing.tsx:43` badge reads "No CAD skills needed · runs entirely on your machine"; sub "Describe a functional part in plain words — I'll design it…". Reference `screens/06` badge: "Ready to print in ~15 minutes · no CAD skills"; the 3-step footer + "Start from a photo" link are present in both.
**What the user sees:** The shipped badge dropped the reference's strongest value prop — the **time-to-print expectation** ("~15 minutes"), which is the single most reassuring number for a nervous first-timer and appears in the wizard's time-budget note. The shipped copy is fine, just less compelling than the design intent.
**Why this matters:** The above-the-fold promise sets expectations. "Ready to print in ~15 minutes" is concrete and disarming; "runs entirely on your machine" is a privacy point better placed second. Minor because both are honest and clear.
**Fix path:** Badge → `Ready to print in ~15 minutes · no CAD skills`; keep the privacy line in the sub or as a secondary chip.

### UX-008 (Minor) — "Designing your part…" message appears twice simultaneously (chat + viewport)
**Category:** State / Visual hierarchy
**Evidence:** `ChatPanel.tsx:189` renders a thinking row "Designing your part…" while busy; `Viewport.tsx:185` simultaneously renders the full-cover busy overlay with the same "Designing your part…" title. Both are on screen at once during a first design.
**What the user sees:** The identical sentence in two places at the same time — the chat spinner row and the viewport overlay. It reads as a small redundancy/duplication rather than one confident progress state.
**Why this matters:** Two copies of the same status dilute it and look unconsidered. The viewport overlay is the richer one (phase stepper + timer + Cancel); the chat row is redundant during a *first* design (there's no thread to anchor it to yet). Minor — not confusing, just not crisp.
**Fix path:** During a first design, suppress the chat "Designing…" row (or reduce it to a quiet "…") and let the viewport overlay own the progress; keep the chat thinking-row for in-thread refines where the viewport already shows the prior part.

### UX-009 (Minor) — Readiness gauge is a semicircle in code but the reference uses a full-circle score ring
**Category:** Pattern fidelity / Visual hierarchy
**Evidence:** `RightPanel.tsx:353-379` (`ScoreGauge`) draws a 120×70 **semicircular** arc; `styles.css:1259` `.kc-gauge-wrap` is 168px wide. Reference README §7 + `screens/10`: a **68px full-circle SVG donut** score ring with the number centered.
**What the user sees:** A wide half-gauge instead of the compact circular score ring the design specifies. It's well-executed and animated, but it's a different shape than the design system's signature readiness element, and at 168px wide it's larger/heavier than the reference's tidy 68px donut.
**Why this matters:** The score ring is a recognizable design-system component; swapping a donut for a half-gauge is a visible fidelity drift on the verdict card. Minor — it communicates the score fine.
**Fix path:** Match the reference donut (full circle, ~68px, number centered) or consciously document the half-gauge as an intentional improvement.

### UX-010 (Minor) — The refine input is the only path to change an LLM-backed (slider-less) part, and its guidance is just a placeholder
**Category:** Journey / Discoverability
**Evidence:** `RightPanel.tsx:313` — a slider-less part shows "To change it, use the conversation on the left: type an exact change like 'make it 10mm taller'…". The conversation's refine input (`ChatPanel.tsx:248`) carries the same hint only as placeholder text, which vanishes on focus.
**What the user sees:** For parts with no sliders (LLM-backed), the *entire* edit surface is a text box whose only instruction disappears the moment they click into it. The right-panel hint is good but it's across the screen from where the user must act.
**Why this matters:** The cross-panel instruction ("use the conversation on the left") asks the user to look one place and act another. Pairing this with the refine chips from UX-003 would close the loop. Minor because the hint copy itself is excellent.
**Fix path:** Surface the refine chips (UX-003) for slider-less parts especially; consider a persistent micro-hint above the refine input, not only a vanishing placeholder.

### UX-011 (Minor) — VersionRail hides entirely until there are 2+ versions, so v1 gives no "history exists" cue
**Category:** Discoverability
**Evidence:** `VersionRail.tsx:16` `if (versions.length < 2) return null`.
**What the user sees:** After the first design there's no version affordance at all; it appears only after the first refine. The user has no cue that refining will create a navigable history.
**Why this matters:** Hiding the rail at v1 is defensible (no clutter), but it means the version/undo capability is invisible until discovered by accident. A subtle "v1 — refine to create versions" hint at v1 would advertise the feature. Minor.
**Fix path:** Optionally show a single quiet pill at v1, or fold the cue into the refine chips.

### UX-012 (Minor) — Export card lists "Download 3D model (.STL)" but the design reference promised 3MF / STEP / G-code with format guidance
**Category:** Copy / Journey
**Evidence:** `ExportPanel.tsx:181` model download is `.STL` with note "STEP and BREP precision formats arrive with the CAD engine"; the sliced print file is `.3mf` (`ExportPanel.tsx:271`). Reference `screens/10`: "Download .3MF" primary + "STEP" + "G-code" ghosts with the note "3MF is printer-agnostic & safe to share · STEP for CAD editing · G-code locks to <printer>."
**What the user sees:** Honest, forward-referenced state (STEP "arrives with the CAD engine") — which is the *right* call versus faking buttons — but the format guidance ("3MF is safe to share / STEP for CAD") that helped users choose is reduced. The sliced 3MF is correctly the real deliverable.
**Why this matters:** Format choice confuses non-experts; the reference's one-line "what each format is for" was genuinely helpful and is mostly gone. Minor — the actual files work and the deferral is honest.
**Fix path:** Add the one-line format-purpose note to the print-file row; keep the honest "STEP arrives later" framing.

### UX-013 (Minor) — Save indicator can show "Saved · My Designs" and the "My Designs" nav button side by side (redundant pair)
**Category:** Visual hierarchy / IA
**Evidence:** `Topbar.tsx:67` "Saved · My Designs" link + `Topbar.tsx:77` "My Designs" ghost button render together when persisted.
**What the user sees:** Two adjacent controls that both say "My Designs" and both navigate there. The team flagged the route-active dedup (UX-005 in their own notes) but the save-link + nav-button pair still reads as a doubled label.
**Why this matters:** Mild redundancy in the chrome. Minor.
**Fix path:** Make the save indicator read "Saved" (dot + word) without the "· My Designs" tail when the nav button is already present, or merge them.

### UX-014 (Nit) — Mixed apostrophe styles in source copy (`'` entity vs `'`)
**Category:** Copy
**Evidence:** `RightPanel.tsx` uses `&rsquo;` in some strings and curly `'` (e.g. "KimCad's") in others; `MyDesigns.tsx` uses curly `'`. Renders fine; just inconsistent in source.
**Fix path:** Pick one (the curly char or the entity) for consistency. Nit.

### UX-015 (Nit) — "Slice & prepare file" disabled state gives no inline reason when no slicer profile exists
**Category:** State / Copy
**Evidence:** `ExportPanel.tsx:154` the Slice button is disabled when `selectedPrinter.sliceable !== true`; the printer `<option>` is labeled "(no slicer profile)" but the disabled button itself has no adjacent "why."
**Why this matters:** The methodology asks disabled states to say *why* and what to do. The option label carries it, so it's a Nit, but a one-line "This printer has no slicer profile yet — pick another" under the disabled button would be clearer.
**Fix path:** Add a muted reason line when the selected printer isn't sliceable.

### UX-016 (Nit) — Photo on-ramp thumbnails use `alt=""` (decorative) — fine, but the confirm card's edited seed is the real content
**Category:** Accessibility
**Evidence:** `PhotoOnramp.tsx:171,194` thumbnails are `alt=""`. Reasonable (the editable seed text is the content and is focused on arrival, `PhotoOnramp.tsx:52`). Flagging only to confirm it's intentional. Nit.

### UX-017 (Nit) — Readiness recommendations use a "→" arrow glyph as a list marker
**Category:** Visual hierarchy
**Evidence:** `RightPanel.tsx:474` each rec is prefixed with an accent "→". Deliberate (the comment notes a check would read as "already done"). Good reasoning; the arrow is slightly heavy at `font-weight:800` (`styles.css:1479`). Nit — consider a lighter weight.

### UX-018 (Nit) — InfoTip "(i)" visual chip is 15px; hit area is expanded to ~25px via `::before` (good), but the glyph is italic lowercase "i" which can read as a typo to some users
**Category:** Pattern
**Evidence:** `styles.css:2932` `font: italic 700 10px` "i". The hit-area expansion (`styles.css:2939`) correctly meets WCAG 2.5.8. The italic-i convention is common but a circled-i or "?" is more universally recognized as "info." Nit.

---

## Cross-cutting themes (for the executive rollup)

1. **Fidelity-flattening on the high-value cards (UX-001, UX-002, UX-006, UX-009, UX-012).** The pattern across the right column and chrome is that richly-designed elements (tinted readiness/report cards, icon-tile checks, the printer chip, the score-ring donut, format guidance) were simplified to a uniform sand-card list. Individually Minor-to-Major; *together* they're the reason the workspace reads as "competent panels" instead of "one designed product." This is the highest-leverage cluster — a single coordinated "restore the right-column hierarchy" pass addresses UX-001/002/009 at once, and is the most felt change against the owner's UX-first bar.
2. **Discoverability of the new Stage 8.5 capabilities (UX-003, UX-005, UX-010, UX-011).** Refine-by-talking, keyboard shortcuts, version history — all *built* and *wired* (the wiring-audit confirms), but their entry points are thin (blank text box, a hidden "?", a rail that hides at v1). The features exist; users won't find them. Cheap to fix (chips + a "?" button + a v1 cue).
3. **Mobile is "stacked," not "designed" (UX-004).** The responsive work is technically careful (touch targets especially) but the phone *layout* inverts task priority. This is the one Major that's genuine new-design work, not a restore-from-reference.

---

## Apple-level-bar read

**Not yet, but within one focused sprint.** The foundations an Apple-bar product needs are present and, in places, excellent: accessibility, honest state coverage, plain-English copy, restraint, and a faithful token system. What's missing is the *composition* layer — the visual hierarchy that makes a screen feel authored (UX-001/002), the discoverability that makes built features feel present (UX-003/005), and a real phone layout (UX-004). None of these is hard; all are the difference between "a good engineer's faithful build" and "a designed product." Fix the cross-cutting cluster #1 and the discoverability cluster #2, and this clears the bar for a beta. Mobile (cluster #3) can trail by a sprint if desktop is the launch surface.

**Gate recommendation (UX lane):** PASS with conditions — no Blockers or Criticals, core journey works, accessibility is strong. The six Majors should be on the this-sprint punch list (especially UX-001/002 and UX-003/005) before this is shown to the owner as "done," given the explicit UX-first bar. Recommend gating the *next* stage's UI work behind the right-column hierarchy restore.
