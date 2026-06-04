# Senior UI/UX Designer — Deep Dive

**Audit:** Stage 8.5 · Slice 7 — "Describe with a photo" on-ramp (Surface D)
**Scope:** Slice 7 frontend only — `git -C kimcad diff 76c6f89..HEAD` (PhotoOnramp.tsx, Landing.tsx, ChatPanel.tsx, Workspace.tsx, App.tsx, styles.css `kc-photo-*`)
**Approved design:** `docs/design/stage-8.5-slice-5-onramps.md` §"Surface D" + the 5 trust rules
**Posture:** Balanced. Hold a high bar on honest framing, states, copy, and accessibility; do not invent defects.
**Date:** 2026-06-04

---

## What I checked — rendered vs. from source

**Rendered (live, in the model-free demo on port 8765 via the preview tools — `/api/photo-seed` returns 200 there, no stale-port problem):**
- Idle affordance at desktop (685px-wide preview window) and at 375×812 — bounding boxes, computed styles, placement relative to the input card and examples, horizontal-overflow check.
- Full happy path: injected a file via `DataTransfer` → `change`, polled to the confirm card. Measured the 56px thumbnail, the editable/focused/labelled seed textarea, the scale note, the privacy line, the three action buttons (dimensions, accessible names, type), card `role`/`aria-label`, and post-confirm focus target.
- Error path: pushed a 13 MB file to trip the client-side 12 MB cap → measured the error message text, its `aria-live`, the fallback actions, and the error-tinted card.
- Workspace variant: entered the workspace via an example chip, drove the photo flow in the refine footer, confirmed the restart cue note and focus-to-seed.
- Touch targets at 375px (a `pointer: fine` desktop resized — the harder case): all three `.kc-btn` actions + Cancel measured at 44px.
- WCAG AA contrast computed for the affordance text, muted copy, seed ink, the accent button, and the error message.
- Console: zero warnings/errors across the whole flow.
- Cancel reset → returns to idle (affordance back, card gone).

**From source only (could not exercise rendered, and why):**
- The **reading-state `aria-live`** (PhotoOnramp.tsx:139). The model-free demo resolves the read in well under 100 ms, so the reading region is gone before a DOM sample lands. The `aria-live="polite"` is present in source on the reading row; I rate it real on that basis. (The long real-vision reading time is a Slice 9 polish item per the brief — noted as a watch item, not a finding.)
- **No-auto-submit** (verified by reading the component): `onSeed` is called in exactly one place — `useSeed()` (PhotoOnramp.tsx:104-109) — which is wired only to the "Use this as a starting point" button's `onClick` (line 183). The two `useEffect`s (lines 41, 48) only revoke blob URLs and move focus; neither advances the flow. There is no effect or timer that submits.

I rate Slice 7 **clean — no Blocker / Critical / Major findings.** The build matches the approved Surface D design and honors all five trust rules. Findings below are two Minors and one Nit.

---

## Trust-rule verification (the load-bearing gate)

| Rule | Requirement | Verdict | Evidence |
|------|-------------|---------|----------|
| 5 — honest framing | Never "photo → finished part"; rough, editable seed; scale disclaimer; privacy line | **PASS** | Confirm card title "A rough starting point"; editable `<textarea>` (not disabled); note "A photo can't tell us scale, so any sizes are estimates"; privacy "Read locally — your photo never left your machine." The seed text the API returns *also* carries the disclaimer inline. |
| 5 — never auto-sends | Photo read locally; no auto-advance | **PASS** | Privacy copy in reading + confirm; `onSeed` only fires on explicit click (source). |
| 2 — no dead-ends | Every state offers a next action; failures offer a fallback | **PASS** | Reading→confirm→3 actions; error→"Try another photo" + Cancel; Cancel always returns to the text box. |
| Accessibility | Real buttons, labelled seed, focus-visible, aria-live, focus-to-seed, 44px touch | **PASS** | All real `<button type="button">` with text labels; seed `aria-label="Edit the description read from your photo"`; focus moves to seed on confirm (rendered `activeIsSeed: true`); error `aria-live="polite"` (rendered); 44px at 375px (rendered). |
| Visual | Workshop tokens, terracotta accent, hairlines, radii, secondary placement | **PASS** | Affordance: dashed `--kc-hair-strong` border, `--kc-muted` text, transparent bg, 13px — reads clearly secondary against the solid terracotta primary. Card uses `--kc-surface` / `--kc-r-card` / `--kc-shadow-card`. No overflow at desktop or 375px. |

---

## What's working (specific credit)

- **The honesty is genuinely well done, not box-ticked.** The disclaimer lives in *three* places that reinforce each other: the standalone note, the privacy line, and the seed body text itself ("…these sizes are rough guesses from the photo (a photo has no scale), so adjust them"). A user cannot reach "Use this as a starting point" without having read that the sizes are estimates. This is exactly the trust-rule-5 spirit.
- **The seed is a real editable textarea that receives focus on confirm.** Rendered-confirmed: `document.activeElement` is the seed the instant the confirm card appears. That single design choice does three good things at once — it announces the result to assistive tech (the reading `aria-live` is gone by then), it invites the sighted user to edit, and it makes "this is yours to change" the literal first interaction. Nicely judged.
- **No dead-ends, including the failure path.** The error card keeps the user moving ("Try another photo") and Cancel is always one click from the text box that's still sitting right above. The reading state is honest ("Reading your photo…") rather than a bare spinner.
- **The workspace variant earns its extra sentence.** Starting a new part from a photo in the workspace could silently feel like it clobbers the current part; the cue "This starts a new part from the photo — your current part is saved in My Designs" pre-empts exactly that anxiety. The landing variant correctly omits it (nothing to lose there). Good context-sensitivity.
- **Secondary really reads as secondary.** Dashed/muted/transparent affordance next to a solid terracotta primary, placed *after* the primary input in reading order both on the landing and in the refine footer. It's discoverable without competing — the design doc's "headline capability worth seeing, off the primary path" intent, delivered.
- **Blob-URL hygiene.** `clearPreview()` + the unmount effect (PhotoOnramp.tsx:41-44, 52-55) revoke the object URL on change and on teardown, so an abandoned read doesn't leak. Small, correct, easy to have missed.

---

## Findings

### UX-001 (Minor · Copy/State) — The size-cap error offers only "Try another photo," not the "describe in words" fallback the generic read-error promises

**Evidence:** PhotoOnramp.tsx:198-209 (error card). The generic read failure sets the message *"Couldn't read that photo — try a clearer shot, or describe the part in words."* (line 76) — naming two fallbacks. But the error card's only concrete action is **"Try another photo"** (+ Cancel). The oversize path (`api.ts:289`, *"That photo is too large to read (max 12 MB)."*, rendered-confirmed) likewise offers only "Try another photo." A user whose only photo is too large (or unreadable) is told in copy they could "describe it in words," but the card gives them no button toward words — they have to know to hit Cancel and find the text box themselves.

**Why this matters:** It's a soft mismatch between what the error copy promises ("describe it in words instead") and what the error card affords (only another photo). For most users Cancel-then-type is obvious because the text box is right there, so this is not a dead-end — hence Minor, not Major. But on the *landing*, after Cancel the user lands back at the hero input, which is the right place; in the *workspace refine footer*, Cancel returns them to the refine input, also fine. The gap is purely that the promised "in words" route isn't a one-click action from the error state.

**Blast radius:**
- Adjacent code: only the error branch of PhotoOnramp.tsx (one component, two variants). No shared pattern elsewhere.
- User-facing: the photo-failure flow only; the happy path is unaffected.
- Migration: none. Tests to update: PhotoOnramp.test.tsx error-state assertions if a third button is added.

**Fix path (lowest-cost):** Leave the buttons as-is and tighten the copy so it doesn't over-promise a route the card doesn't provide. Change the generic failure message to *"Couldn't read that photo — try a clearer shot, or cancel and describe the part in words."* (it already says "cancel" → text box truthfully). Alternatively (richer) add a third ghost action **"Describe in words"** that calls `reset()` and focuses the nearest text input. Recommend the copy tweak — it closes the mismatch with one string and no new wiring.

---

### UX-002 (Minor · Accessibility) — The confirm card's group label duplicates the affordance label; a slightly more specific name would orient screen-reader users better

**Evidence:** PhotoOnramp.tsx:137 — the confirm/error card is `role="group" aria-label="Describe with a photo"`. That's the same string as the idle affordance button (line 132). A screen-reader user who activated "Describe with a photo" then enters a group also called "Describe with a photo," which restates rather than advances their mental model. The card's *content* (the editable seed, the scale note) is well-labelled, so this is mild.

**Why this matters:** The group label is the first thing a screen reader announces on entering the region. "A rough starting point from your photo" (matching the visible heading) would tell the user *where they now are* rather than echo the button they just pressed. Minor — the experience is usable as-is; this is a polish that improves orientation.

**Blast radius:**
- Adjacent code: PhotoOnramp.tsx:137 only.
- User-facing: assistive-tech users entering the confirm/error card. Migration: none. Tests: none known.

**Fix path:** Set the group label to track the phase, e.g. `aria-label={phase === 'error' ? 'Photo couldn’t be read' : 'A rough starting point from your photo'}`. One line.

---

### UX-003 (Nit · Copy) — "Use a different photo" and "Try another photo" are two phrasings for the same action across states

**Evidence:** Confirm card uses **"Use a different photo"** (line 188); error card uses **"Try another photo"** (line 202). Both re-open the picker.

**Why this is a Nit, not a defect:** The two phrasings are arguably *intentional* — "different" reads naturally after a successful-but-wrong read; "try another" reads naturally after a failure. A reasonable designer could keep them. Flagging once for consistency-review only; do not belabor. If the team wants one label, "Try another photo" works in both states.

---

## Watch items (not findings — noted per the brief)

- **Reading-state duration on real vision.** On real gemma4:e4b CPU vision the "Reading your photo…" state will last meaningfully longer than the demo's sub-100 ms. The brief acknowledges this is Slice 9 polish (the standardized no-frozen-spinner treatment). The honest copy and `aria-live` are already in place; just confirm in Slice 9 that a multi-second read still feels alive (e.g. progress cue), and that the `aria-live` region isn't so chatty it spams a screen reader.
- **Affordance text contrast margin.** The muted affordance label on the page background measures **4.66:1** — over the 4.5:1 AA floor for normal text, but slim. It's belt-and-suspenders safe because the affordance is also bounded by a dashed border (shape, not color alone), and on the card surface it measures 5.14:1. No action needed; just don't darken the page bg or lighten `--kc-muted` without re-checking.

---

## Rendered measurements (reference)

| Check | Result |
|-------|--------|
| Affordance (desktop) | dashed `rgba(39,34,25,0.16)` border, `#6f6857` text, transparent bg, 13px/600; 14px below input card, 18px above examples; 0 horizontal overflow |
| Primary "Design it" | solid `#b1542f` (accent-strong) fill, white text — clear primary vs. secondary |
| Confirm thumbnail | 56 × 56 px, `alt=""` (decorative; seed text conveys content) |
| Seed field | `<textarea>`, not disabled, **focused on confirm**, `aria-label` present, scale disclaimer in value |
| Confirm actions | "Use this as a starting point" (accent, disabled when seed empty), "Use a different photo" (ghost), "Cancel" — all `type="button"`, named |
| Touch @ 375px (fine pointer) | accent 44px, ghost 44px, cancel 44px (via global `.kc-btn` `(pointer: coarse), (width<=640px)` rule + Slice 7 `.kc-photo-cancel` rule) |
| Error state | "That photo is too large to read (max 12 MB)." · `aria-live="polite"` · "Try another photo" + Cancel both 44px · error-tinted card |
| Workspace variant | shows BOTH the scale note AND the restart cue; focus to seed; affordance secondary in refine footer |
| Landing variant | scale note only (no restart cue) — correct |
| Cancel | resets to idle (affordance returns, card removed) |
| Contrast (AA) | affordance/bg 4.66 · muted/surface 5.14 · seed ink 13.67 · white/accent-btn 5.03 · error ink 13.73 — all pass |
| Console | 0 warnings, 0 errors across the full flow |

---

## Summary

- **Blocker:** 0
- **Critical:** 0
- **Major:** 0
- **Minor:** 2 (UX-001 error-state copy/affordance mismatch; UX-002 generic group label)
- **Nit:** 1 (UX-003 "different"/"another" wording)

Slice 7 meets the Surface D design and all five trust rules. Honest framing is the standout — the "rough, editable, estimates-only, read-locally" message is reinforced three ways and is impossible to bypass. States are complete with no dead-ends, accessibility is solid (labelled seed, focus-to-seed, aria-live on reading/error, 44px touch at 375px, AA contrast), and the secondary affordance reads as secondary in both variants. The two Minors and one Nit are copy-level polish, none blocking. From a UI/UX standpoint this slice is ready.
