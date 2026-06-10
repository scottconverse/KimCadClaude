# UI/UX Deep-Dive — KimCad, Stage 9 (image & sketch on-ramp)

**Audit date:** 2026-06-10
**Role:** Senior UI/UX Designer
**Scope audited:** Stage 9 UI surfaces at commit `e8339d9`: the dual on-ramps on the Landing (`PhotoOnramp` `kind=photo|sketch`, the `KIND_COPY` table, `PencilGlyph`, the `.kc-onramps` CSS), the wizard model-card copy (vision-model mention), and Stage-9-adjacent copy (wizard welcome, error strings, workspace on-ramp). Verified in source and in the running demo app (`--demo`, isolated temp `USERPROFILE`) at 375×812 and 1280×800. The Stage-9 walkthrough (`docs/audits/walkthrough-stage-9-2026-06-10/WALKTHROUGH-REPORT.md`) already proved the real-model journeys; this audit did not re-run them.
**Auditor posture:** Adversarial (stage gate)

---

## TL;DR

Stage 9's copy discipline is genuinely strong — the `KIND_COPY` parametrization means the sketch mode inherits **zero** photo-only wording anywhere I could find (affordance, reading state, privacy lines, scale notes, error strings, size-cap messages, backend 422s, aria-labels — all kind-correct). The two real problems are structural, not verbal: **the "side by side" dual on-ramp layout never actually renders side by side** (a Stage-8.5 `width:100%` rule defeats the new flex row at every viewport, and the idle block resolves to a quirky 350px shrink-to-fit column), and **the wizard now advertises the vision model but never checks it**, so a fresh install can sail through setup "Ready" and only discover the missing second model when their first photo/sketch read fails. Both are fixable in an afternoon. No Blockers, no Criticals.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 5 |
| Nit | 2 |

## What's working

- **`KIND_COPY` as a single source of per-kind truth** (`frontend/src/components/PhotoOnramp.tsx:35–52`) — every user-visible string that should differ between photo and sketch does, and every string that should stay shared stays shared. The scale note is the standout: photo honestly says sizes are estimates; sketch says "Labeled dimensions are read as written — check they came through." That is exactly the right epistemic framing for each input, and it survived into the live demo verbatim.
- **No photo-wording leaks into sketch mode — verified end-to-end.** Frontend (`PhotoOnramp.tsx`, `api.ts:388–414`), backend handlers (`src/kimcad/webapp.py:1410–1444`), aria-labels (`aria-label="Edit the description read from your sketch"`, group labels per `copy.noun`), the 12 MB cap message ("That sketch is too large…"), and the generic 413/400 ("File too large." / "Empty upload." — kind-neutral by design). The dedicated sketch-mode tests (`PhotoOnramp.test.tsx:175–207`) pin this.
- **Confirm-state focus management** — on a successful read, focus moves into the editable seed textarea (`MS2-002`, verified live: `focusedNow: "Edit the description read from your sketch"`), which both announces the result to AT and invites the edit.
- **Touch targets at 375px** — affordance chips, all three card action buttons, and Cancel all measured exactly 44px tall in the running app (`@media (pointer: coarse), (max-width: 640px)` at `styles.css:3308`).
- **The other on-ramp stays available while one card is open** — opening the sketch card leaves the photo chip visible and clickable above it (verified live at 1280px); no modal lock-in.
- **Reduced motion is handled globally** (`styles.css:849`) — the card's fade-up and the reading spinner are neutralized for opted-out users.
- **Error taxonomy honors the trust contract** — bad image (422 "try a clearer image with written dimensions"), Ollama down ("Make sure Ollama is running"), and vision model missing (exact `ollama pull` command) are three distinct messages; the user's sketch is never blamed for a setup problem (`webapp.py:1425–1438`).

## What couldn't be assessed

- Real-model latency feel and the real confirm card content — covered by the walkthrough's live runs; not re-run here.
- The `VisionModelMissing` message **as rendered** in the error card — verified via source + unit tests and the API contract; the demo provider can't simulate a missing model.
- Native OS file-picker and real drag-and-drop (files were injected synthetically into the inputs).
- Actual screen-reader behavior (NVDA/VoiceOver) — assessed from the accessibility tree and ARIA semantics only; UX-906's announcement concern is inferred, not observed.

---

## First impressions

At 375px the landing reads cleanly top-to-bottom: badge → hero → input card → "Enter to send" hint → two dashed chips ("Describe with a photo", "Start from a sketch") → example chips → three steps. The dashed-border chip treatment correctly signals the on-ramps as secondary to the text path; text remains the visually dominant action. The pencil glyph is instantly legible next to the camera. At 1280px the impression is slightly off: the two chips stack vertically as a narrow left-aligned island inside an otherwise centered composition — it reads as an accident rather than a column (it is one — see UX-901).

## Journey walkthroughs

### Journey: Landing → sketch on-ramp → confirm card → seed (demo, 375px and 1280px)

Chip → (file chosen) → card replaces the chip: spinner + "Reading your sketch…" + the privacy line + Cancel → confirm card with thumbnail, "Read locally — your sketch never left your machine and isn't saved", editable seed (focused), the read-as-written note, and three actions. Every string is sketch-correct. Friction points: the card's visible title is "A rough starting point" with no source noun (UX-903), and on desktop the idle chips aren't where the comment says they should be (UX-901).

### Journey: both on-ramps opened (photo card, then sketch card)

Both cards open and stack vertically, photo above sketch, each full-width (`.kc-onramps .kc-photo-card { flex-basis: 100% }` works as intended). The layout does not break — but the two cards are visually near-identical: same heading "A rough starting point", same button row, same shape. Only the one-line privacy sentence ("your photo…" vs "your sketch…") and the thumbnails distinguish them. The second read to complete also steals focus from the first card's textarea. Confusing at the margin, not broken (UX-903).

### Journey: fresh install → wizard → first sketch

Wizard step 0 promises "Describe a part in plain words — or photograph one" (no sketch — UX-905). Step 1's model card checks gemma4:e4b, shows "Ready", and mentions the vision model only as a parenthetical ("qwen2.5vl:3b — pulled the same way"). Nothing checks whether it actually is pulled — the user learns at first use (UX-902), albeit with an exact recovery command (whose backticks render literally — UX-904).

---

## Findings

> **Finding ID prefix:** `UX-` (9xx series — Stage 9 gate)
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern

### [UX-901] — Major — Visual hierarchy / Responsive — The "side by side" dual on-ramps never render side by side; the idle block resolves to a fragile 350px shrink-to-fit column

**Evidence**
`frontend/src/styles.css:2775` states the intent: *"Stage 9: the two on-ramps (photo + sketch) sit side by side under the prompt box"*, and `.kc-onramps` (2777–2782) is `display:flex; flex-wrap:wrap; gap:10px`. But each child carries the Stage-8.5 rule `.kc-photo-landing { width: 100% }` (`styles.css:3161–3164`), which sets each flex item's basis to the full row — so the chips stack vertically at **every** viewport. Verified in the running demo: at 1280×800 the two chips render at the same x (465) on separate rows (y 496 / 553); the `min-width: 0` override at 2783 doesn't help. Worse, in the idle state the `.kc-onramps` container shrink-resolves to exactly 350px (the sum of the two chip widths + gap — a circular intrinsic-sizing artifact), producing a narrow, **left-aligned** chip island centered as a block inside the otherwise center-aligned landing column; the moment a card opens, the container snaps to the full 640px. At 375px the stack is fine (it's what wrap would do anyway).

**Why this matters**
On any laptop screen the Stage 9 headline feature presents as a misaligned afterthought: two left-ragged dashed chips floating in a centered composition, with a container width that visibly jumps when a card opens. Users won't articulate "the flex basis is wrong," but they will register the landing as slightly broken. The layout also only *works at all* by accident of intrinsic-size resolution — a third on-ramp (Stage 10's wizard upgrade territory) or a longer label translation would reshuffle it unpredictably.

**Blast radius**
- Adjacent code: `.kc-photo-landing` (`styles.css:3161`) is shared with the single-on-ramp era; `.kc-photo-workspace` (3166) is unaffected (workspace has one on-ramp, `ChatPanel.tsx:305`). The built bundle `src/kimcad/web/assets/index.css` carries the same rules and needs a rebuild.
- User-facing: landing only — chips become one centered row on desktop, wrapping to a stack ≤~400px; open cards stay full-width.
- Tests to update: none known (no layout assertions on `.kc-onramps`); a screenshot baseline if one is added later.
- Related findings: UX-903 (the both-cards-open stack this row produces).

**Fix path**
Scope the width out of the flex context and center the row, e.g.:
```css
.kc-onramps { justify-content: center; }
.kc-onramps .kc-photo-onramp.kc-photo-landing { width: auto; flex: 0 1 auto; }
.kc-onramps .kc-photo-card { flex-basis: 100%; }  /* keep */
```
…and keep `.kc-onramps { width: 100% }` (add it) so the open card still spans the 640px inner column. Verify at 320/375/768/1280 that the chips sit on one row until they genuinely don't fit, then wrap.

---

### [UX-902] — Major — Journey / State — The wizard advertises the vision model but never checks it; "Ready" can be a half-truth on a fresh install

**Evidence**
Wizard step 1 (`FirstRunWizard.tsx:220–249`, verified live): the model card pings `/api/model`, shows status "Ready" for `gemma4:e4b`, and the description adds *"a separate small local vision model reads photos and sketches (qwen2.5vl:3b — pulled the same way)."* No status check, action line, or "check again" exists for the vision model — the per-model action copy (lines 253–285) covers only the text model. `kimcad models` (CLI, `cli.py:515`) does report the vision model's installed state, so the data exists server-side; the wizard just doesn't surface it.

**Why this matters**
Stage 9 made the vision model a *second required pull* (the getting-started doc's two-pull instruction). The wizard is the product's one purpose-built moment to verify setup, and it now names the second model while validating only the first. Kim finishes setup on a green "Ready", later tries the sketch chip during a design session, and hits a mid-task setup error. The recovery message is excellent (exact pull command — credit), but the wizard converted a setup-time fix into a task-time interruption. Exposure: every fresh install whose user doesn't independently follow the docs' two-pull step.

**Blast radius**
- Adjacent code: `ModelHealthPill.tsx` (landing health pill) has the same single-model blind spot — a user can see a healthy pill and still lack the vision model. `SettingsPanel`'s model status likewise if it mirrors `/api/model`. Backend: the model-info endpoint would need to carry the vision model's presence (the `kimcad models` CLI path shows the lookup already exists).
- User-facing: wizard step 1 gains a second, smaller status row; no flow changes.
- Tests to update: `FirstRunWizard.test.tsx` (the test at line 52 currently pins "one model card / no alternative" — a second *status line* inside the same card preserves its intent but the test's selectors may need adjusting).
- Related findings: UX-904, UX-908 (same card's copy).

**Fix path**
Extend the model-info payload with the vision model's presence and render one quiet line under the existing status: "Vision model (photos & sketches): qwen2.5vl:3b — ✓ installed" / "not installed yet — KimCad will show you the install command when you first use a photo or sketch." Keep it informational (don't block Continue); the goal is no surprises, not a second gate.

---

### [UX-903] — Minor — Copy / State — Both confirm cards open simultaneously are visually near-identical; the visible title omits the source the aria-label already names

**Evidence**
Verified live at 375px with both on-ramps driven to `confirm`: two stacked cards, both titled **"A rough starting point"** (`PhotoOnramp.tsx:230`), both with the same three buttons. The `role="group"` aria-label *does* differentiate ("A rough starting point from your photo/sketch", lines 194–200) — sighted users get less information than screen-reader users. Only the one-line privacy sentence and the thumbnails distinguish the cards. Additionally, whichever read completes last steals focus into its textarea (the `phase === 'confirm'` effect, line 85–87), even if the user is editing the other card's seed.

**Why this matters**
Opening both is a plausible novice move ("try the photo, also try the sketch, compare"). Two same-titled cards with identical CTAs invite using the wrong "Use this as a starting point." The focus steal compounds it: mid-edit, the caret silently jumps to the other card.

**Fix path**
Make the visible title match the accessible one: `A rough starting point from your {copy.noun}` (then simplify the aria-label to avoid double-speak). For the focus steal, only auto-focus if the seed textarea's card was the most recently interacted-with on-ramp — or simply if `document.activeElement` isn't already inside another `.kc-photo-card`.

---

### [UX-904] — Minor — Copy — The vision-model-missing error renders literal backticks and "pulled" jargon in the on-ramp error card

**Evidence**
`src/kimcad/llm_provider.py:60`: `"KimCad's vision model isn't pulled yet. Run \`ollama pull qwen2.5vl:3b\`, then try again."` This string is surfaced verbatim as the error card's text (`webapp.py:1431–1433` → `api.ts:409–411` → `kc-photo-error-msg`). The card renders plain text, so Kim sees actual backtick characters. The sibling `MODEL_UNAVAILABLE_MESSAGE` (`pipeline.py:180–183`) is correctly markdown-free, so this is a one-off drift.

**Why this matters**
Backticks are developer-culture punctuation; in Kim's error card they read as typos. "Pulled" is Ollama jargon she has never had to learn (the wizard's own action copy at least anchors it to "in Ollama").

**Fix path**
Rewrite (keeps the exact command, drops the markdown):
> "KimCad's vision model isn't installed yet. In a terminal, run: ollama pull qwen2.5vl:3b — then try again."
Tests pinning the string (the trust tests + troubleshooting doc quote the exact error, per the walkthrough) must be updated in the same change — the troubleshooting entry's verbatim quote is the load-bearing one.

---

### [UX-905] — Minor — Copy — The wizard welcome still pitches "or photograph one"; the sketch path Stage 9 just shipped is missing from the product's own elevator pitch

**Evidence**
`FirstRunWizard.tsx:198–202` (verified live): *"Describe a part in plain words — or photograph one — and get a print-ready file in minutes."* The same screen's step-1 description does mention sketches, so the omission is inconsistency, not policy.

**Why this matters**
The welcome screen is where a new user forms their mental model of what KimCad accepts. A dimensioned sketch is arguably the *stronger* Stage 9 story (it carries real dimensions; a photo only estimates) and it's invisible at the front door.

**Fix path**
> "Describe a part in plain words — or start from a photo or a dimensioned sketch — and get a print-ready file in minutes."

---

### [UX-906] — Minor — Accessibility / State — On a failed read, focus is dropped and the error may not be announced

**Evidence**
`PhotoOnramp.tsx`: clicking the affordance unmounts it once `phase` leaves `idle` (line 176), so keyboard focus falls to `<body>` during the read. On `phase === 'error'` the message `<p className="kc-photo-error-msg" aria-live="polite">` (line 275) is mounted *with* its text in a single render — newly inserted live regions whose initial content arrives at insertion are unreliably announced across SR/browser pairs. The success path was deliberately fixed (MS2-002 moves focus to the textarea); the error path got no equivalent.

**Why this matters**
A screen-reader user who picks an unreadable sketch may hear nothing: no focus, no announcement — a silent dead end on the exact path where guidance ("try a clearer image with written dimensions") matters most. Inferred from semantics, not observed with a live SR — hence Minor rather than Major.

**Fix path**
Mirror MS2-002: on `phase === 'error'`, move focus to the "Use a different {noun}" button (the natural next action); keep the live region as a belt. One effect, both kinds, both variants. Add a test beside the existing MS2-002 one.

---

### [UX-907] — Minor — Journey — The workspace has a photo on-ramp but no sketch counterpart

**Evidence**
`ChatPanel.tsx:303–306` renders a single `<PhotoOnramp variant="workspace" />` (default `kind="photo"`) at the foot of the refine row. The landing has both kinds; the workspace silently has one.

**Why this matters**
A user mid-design who wants to start their next part from a sketch — the exact behavior the landing taught them — finds the option missing and has no breadcrumb back ("My Designs → new design" is the actual path). If this was a deliberate Stage 9 descope (keeping the refine row light), it's defensible; it just shouldn't be accidental.

**Fix path**
Either add the sketch chip beside the photo chip in the workspace (the component is fully parametrized — `kind="sketch"` is one line, plus the row's wrap already accommodates it), or record the descope decision so Stage 10 doesn't rediscover it.

---

### [UX-908] — Minor — Copy — The model-card's vision sentence leans on Ollama jargon and a second raw slug for an audience the card elsewhere protects

**Evidence**
`FirstRunWizard.tsx:244–249` (verified live): *"It's the tested default for designing parts; a separate small local vision model reads photos and sketches (qwen2.5vl:3b — pulled the same way)."* The card's own design history (UX-011) deliberately demoted the raw slug to a secondary detail for the *primary* model; this sentence reintroduces a second slug plus "pulled the same way" — which assumes the user both knows what "pulling" is and remembers that the first model was pulled (on a healthy install they never saw a pull at all; the card just said "Ready").

**Why this matters**
Length is fine (two sentences, ~59px); clarity is the issue. For Kim, "pulled the same way" is a dangling reference. The slug itself is acceptable *if* it's doing work — and per UX-902 it currently isn't, since nothing on the screen checks or acts on it.

**Fix path**
Pair with UX-902. If the vision-model status line lands, the description can shrink to: *"KimCad's local AI — runs on your CPU, no internet required. It's the tested default for designing parts."* — and the slug moves into the status line where it's actionable. If UX-902 is deferred, minimally: *"…a second small model reads photos and sketches (qwen2.5vl:3b — installed the same way as the model above)."*

---

### [UX-909] — Nit — Accessibility / Copy — The error card's group label always blames the image, even when the body text correctly blames setup

**Evidence**
`PhotoOnramp.tsx:194–196`: in `phase === 'error'` the group's aria-label is "Your {noun} couldn't be read" — including when the rendered message is "Ollama isn't running" or "vision model isn't pulled," which the backend went out of its way *not* to frame as the user's fault (QA-A-003).

**Fix path**
Neutral label for the error group: "Couldn't get a starting point from your {noun}" — true in all three error flavors.

---

### [UX-910] — Nit — Pattern — The affordance chips accept drag-and-drop but nothing hints at it

**Evidence**
`PhotoOnramp.tsx:182–183`: `onDragOver`/`onDrop` on the idle chip; no copy, hover state, or drag-enter highlight advertises droppability.

**Fix path**
A drag-enter style on the chip (accent border, like the hover state) would reward the users who try it; not worth copy real estate.

---

## States audit matrix

| Component / state | Default | Loading | Success | Error | Empty/edge | Notes |
|---|---|---|---|---|---|---|
| Photo on-ramp (landing) | ✓ chip | ✓ spinner + privacy + Cancel | ✓ confirm card, focus moves | ✓ 3-flavor taxonomy | ✓ empty seed → kind-specific cantRead | UX-906 (error focus), UX-909 (error label) |
| Sketch on-ramp (landing) | ✓ chip | ✓ (sketch wording) | ✓ (sketch wording) | ✓ (sketch wording) | ✓ | no copy leaks found |
| Both cards open | ✓ stacks, no overflow (375 & 1280) | — | ⚠ identical titles, focus steal | — | — | UX-903 |
| Wizard model card | ✓ | ✓ "Checking…" | ✓ "Ready" | ✓ "Couldn't check" + action lines | ⚠ vision model unchecked | UX-902, UX-908 |

## Accessibility snapshot

- Keyboard navigation: logical and verified — prompt textarea → "Design it" → photo chip → sketch chip → example chips. Hidden file input is `hidden` (out of the tab order, opened via the labeled button) — correct pattern.
- Focus visibility: `:focus-visible` outlines on chips, cancel, and seed textarea (`styles.css:3195, 3265, 3302`).
- Focus management: confirm ✓ (moves to textarea); error ✗ (UX-906).
- Labeling: file flow labeled by the visible button text; textarea has a kind-correct aria-label; card groups labeled per kind (visible titles lag the labels — UX-903).
- Color/contrast: no new colors in Stage 9 surfaces; chips use `--kc-muted` on transparent at 13px/600 — inherited palette, not re-measured this gate.
- Reduced motion: ✓ global kill switch (`styles.css:849`).
- Touch targets: ✓ all Stage 9 interactive elements measured 44px at 375px.

## Patterns and systemic observations

- **One parametrized component beats two near-twins** — `KIND_COPY` is the reason this stage has zero copy-leak findings. When Stage 10 adds surfaces, extend the table rather than forking the component.
- **The wizard's coverage lags the product's requirements** (UX-902, UX-905, UX-908 share this root): Stage 9 grew the install footprint and the input modalities, and the wizard's welcome, check, and description all still describe the Stage-8.5 product. One coordinated wizard pass fixes all three.
- **Stage-8.5 CSS assumptions vs Stage-9 layout** (UX-901): `.kc-photo-landing` was written for a single full-width on-ramp; Stage 9 wrapped two of them in a flex row without revisiting it. Worth a quick grep for other width-100% children inside the new container next time a flex parent is introduced around existing components.

## Appendix: surfaces reviewed

- `frontend/src/components/PhotoOnramp.tsx` (+ `.test.tsx`), `Landing.tsx`, `ChatPanel.tsx:290–306`, `FirstRunWizard.tsx:185–290` (+ `.test.tsx:52`), `api.ts:351–414`, `styles.css:2775–2788, 3154–3313, 849`
- `src/kimcad/webapp.py:1372–1444, 1784–1799`, `src/kimcad/llm_provider.py:51–62, 361–436`, `src/kimcad/pipeline.py:178–183`, `src/kimcad/cli.py:507–515`; built bundle spot-checked (`src/kimcad/web/assets/index.css`, `kimcad.js`)
- Running demo app (isolated temp `USERPROFILE`), viewports 375×812 and 1280×800: landing idle, both on-ramps reading/confirm (single and simultaneous), wizard steps 0–1, tab order, touch-target and layout measurements via DOM inspection. Demo server and temp home removed after the session.
