# Stage 6 — Settings Model Section: UI/UX Deep-Dive

**Role:** Senior UI/UX Designer (independent, skeptical)
**Date:** 2026-06-05
**Branch:** `stage-0-7-audit-backfill`
**App under test:** running demo at http://127.0.0.1:8765/ (`#/settings`), `kimcad web --demo`
**Scope:** Stage 6 model layer as it appears in Settings — the AI-model status readout, the cloud opt-in flow (toggle / model field / API-key field), and the experimental shape-generator toggle. AUDIT-ONLY.

**Method:** Drove the running app via preview tools at desktop (1280) and mobile (390). DOM + computed-style are authoritative; load-bearing claims re-verified by DOM measurement and cross-checked against source (`src/kimcad/web/assets/kimcad.js`, `webapp.py`). WCAG contrast computed numerically, not eyeballed. Demo settings were mutated during testing and **reset to defaults afterward** (verified `cloud_enabled:false, has_cloud_key:false`).

**Out of scope per directive (NOT raised):** the deliberate single-model design (gemma4 + health line, no local model picker) is correct and is not flagged.

---

## Severity summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 1 |
| Major    | 0 |
| Minor    | 2 |
| Nit      | 2 |
| **Total** | **5** |

---

## What's working (specific credit)

This section is genuinely well-built. Real strengths, named:

- **Masked-key handling is exemplary.** The backend (`webapp.py:442 _mask_key`) returns dots + last-5 only (`••••••••••••••••WXY99`); the full key is *never* returned by `/api/settings` (verified against the live response body — only `cloud_key_masked` / `has_cloud_key` are present). On the client the saved key renders as a **`readonly`** input with `aria-label="Saved OpenRouter key (masked)"` and the action button flips from **"Save"** to **"Replace"**. The entry field is `type="password"` and `autocomplete="off"`. This is the correct, accessible, honest pattern.
- **Privacy framing on the cloud toggle is strong and honest.** The callout — *"This sends your prompt off your machine. Off by default — KimCad stays on your computer until you choose this."* — is exactly the right disclosure for a local-first product, and it measures **7.34:1** contrast (rgb(93,71,8) on rgb(243,233,211)), well above AA.
- **Cloud fallback honesty.** *"If a model isn't reachable, KimCad falls back to your local model — a design never fails just because a cloud slug is wrong."* Sets correct expectations and removes fear of a broken slug.
- **Model status states are fully designed.** Source confirms `checking` (spinner + "Checking…"), `error` ("Couldn't check"), `Running`, `Model not pulled`, and `Not running`, plus two actionable down-state guidances: *"Ollama isn't running. Start it, then [check again]."* and *"The model isn't pulled yet. Pull `<model>` in Ollama, then [check again]."* No blank states.
- **Accessibility baseline is solid.** Both toggles are `button[role="switch"]` with `aria-checked` + descriptive `aria-label`s ("Use a cloud model", "Enable the experimental shape generator"). Global `:focus-visible` (2px accent outline) plus dedicated focus styles for `.kc-switch` and `.kc-set-input`. `prefers-reduced-motion` is respected. The "Saving…" / "Saved" header note uses `role="status" aria-live="polite"`.
- **Honest backend status gating.** `/api/model-status` (`webapp.py:1100`) only reports `backend:"cloud"` when cloud is enabled AND a key AND a model are all present — so the "Cloud" *badge* itself never lies.
- **Mobile (390) is clean.** No horizontal scroll (scrollWidth == clientWidth == 390). Callouts, badges, and fields wrap gracefully.

---

## Findings

### UX-001 — Critical — Copy / Honesty — Cloud model is described as "local AI … nothing leaves your computer"

**Category:** Copy / Honesty
**Screen/element:** `#/settings` → "AI model" card body (`p.kc-set-sub`), cloud-enabled state
**Viewport:** verified desktop 1280 (live screenshot) and confirmed in source

**Evidence (live, with cloud enabled + key + model saved):** the AI-model card renders badge **"Cloud"**, green status **"Cloud"**, and the body sentence:

> **`some/model-v1` — KimCad's local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer.**

The model name is the *cloud* OpenRouter slug, yet the very same sentence asserts it is the local AI, needs no internet, and that nothing leaves the computer. This is flatly false and self-contradictory (the badge two lines up says "Cloud").

**Root cause (source, `src/kimcad/web/assets/kimcad.js`, AI-model card):** only the model *name* is interpolated; the descriptive sentence is hardcoded for the local case:

```jsx
<code className="kc-mono">{c?.model ?? `gemma4:e4b`}</code>
` — KimCad’s local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer.`
```

When `c.model` becomes the cloud slug (`/api/model-status` returns `backend:"cloud"`), the static sentence does not switch with it.

**Why this matters:** For a privacy-first, local-first tool whose entire value proposition is "your data stays on your machine," telling the user a *cloud* model "runs on your machine … nothing leaves your computer" is the single most damaging possible copy error. It is the opposite of the truth at exactly the moment the user has opted into sending data off-box. It also directly contradicts the (correct) cloud callout 100px below it, which says "This sends your prompt off your machine." A privacy-conscious user who reads the model card will be actively misled; a careful one will lose trust the moment they spot the contradiction. This is a release-quality-beta honesty defect.

**Fix path:** Branch the description on `c.backend`. Suggested copy:

- Local: *"`gemma4:e4b` — KimCad's local AI. Runs on your machine, on your CPU. No internet required; nothing leaves your computer."* (unchanged)
- Cloud: *"`<model>` — a cloud model via OpenRouter. KimCad sends your prompt to this model when you make a hard request; local always remains the fallback."*

Pull the sentence from the same source of truth as the badge (`c.backend === 'cloud'`) so the copy can never drift from the badge again.

**Blast radius:**
- Adjacent code: only the one `p.kc-set-sub` in the AI-model card. The badge (`Ue(c)`) and class (`He(c)`) helpers already branch on `c.backend` correctly — reuse that branch for the copy.
- Shared state: driven by `/api/model-status` `backend`/`model` (`webapp.py:1089`); no backend change needed — backend already reports cloud correctly.
- User-facing: every user who enables cloud + saves a key/model sees this card; it's on the primary Settings surface.
- Migration: none.
- Tests to update: any frontend snapshot/text assertion on the AI-model card body; add a cloud-state assertion (currently no test catches the contradiction — coordinate with the Test role).
- Related findings: UX-002 (same card, related staleness), and the QA/Test lanes (no test exercises the cloud-enabled card copy).

---

### UX-002 — Minor — State — "Refresh" / "check again" is the only way to re-sync the model card after a cloud change; card model name can momentarily mismatch settings

**Category:** State
**Screen/element:** "AI model" card status line
**Viewport:** desktop 1280

**Evidence:** The card's model name and backend come solely from `/api/model-status`, which is re-fetched (`w()`) after a settings save. On the happy path this works. But the card body's *description* (UX-001) and the *model name* are sourced from a status fetch that is independent of the in-flight settings form, so during the brief save→refetch window the card can show a stale name. Low exposure (sub-second), but it compounds UX-001's contradiction.

**Why this matters:** Minor on its own — the window is short and self-corrects. Logged because the root (copy/state derived from two sources that can momentarily disagree) is the same root as UX-001; fixing UX-001 by binding copy to `c.backend` also tightens this.

**Fix path:** Fold into the UX-001 fix — bind the entire card body (badge, name, sentence) to the single `c` status object so they always move together.

**Blast radius:**
- Adjacent code: AI-model card in `kimcad.js` only.
- User-facing: transient; no data effect.
- Migration: none.
- Related findings: UX-001.

---

### UX-003 — Minor — Responsive — Cloud key field and model field have mismatched right edges on mobile

**Category:** Responsive / Visual hierarchy
**Screen/element:** Cloud acceleration → API-key row vs. Model field
**Viewport:** mobile 390

**Evidence (DOM measurement, 390px):** the API-key input shares its row with the "Replace"/"Save" button and measures `width 225, right 268`; the Model field below it is full-width at `width 305, right 348`. The two stacked fields therefore terminate at different x-positions (268 vs 348), breaking the vertical edge alignment a user expects from a stacked form.

**Why this matters:** Minor visual-rhythm issue, not a break — there is no overflow and the layout is legible (verified by screenshot). But on a narrow viewport the ragged right edge reads as slightly unfinished on a screen the owner holds to an Apple-grade bar.

**Fix path:** On mobile, either (a) drop the Save/Replace button to its own full-width row below the key input so the key field spans full width and aligns with the Model field, or (b) keep the inline button but constrain the Model field to the same right edge as the key+button group. Option (a) is the cleaner mobile pattern.

**Blast radius:**
- Adjacent code: cloud-section layout CSS in `index.css` (the key-row flex container).
- User-facing: mobile Settings only.
- Migration: none.

---

### UX-004 — Nit — Accessibility — Disabled "Save" button keeps `pointer-events: auto`

**Category:** Accessibility / Interaction state
**Screen/element:** Cloud "Save" button (empty-key state)

**Evidence (computed style):** when the key field is empty the Save button is correctly `disabled` with `opacity:0.45` and `cursor:default` — good — but `pointer-events:auto`. Native `disabled` already blocks activation, so this is harmless, but `pointer-events:auto` on a visually-disabled control is a small inconsistency.

**Why this matters:** Negligible — the button can't fire while `disabled`. Flagged once as hygiene.

**Fix path:** Add `pointer-events:none` to the disabled button rule (or rely solely on the native `disabled` attribute, which is already present).

---

### UX-005 — Nit — Visual — "Untrusted" experimental badge sits right at the AA contrast floor

**Category:** Color / Accessibility
**Screen/element:** Experimental shape-generator card → "Experimental · Untrusted" badge

**Evidence (computed + composited):** badge text rgb(135,99,18) on the composited gold-tint background (≈ rgb(243,233,211)) computes to **4.55:1** at 11px. It *passes* AA for normal text (4.5:1), but with no margin, and the badge text is small.

**Why this matters:** Passes, so not a defect — but it's the thinnest contrast margin in the section and the badge carries a safety-relevant word ("Untrusted"). A hair more depth would make the warning unmissable.

**Fix path:** Darken the badge text one step (e.g. toward rgb(110,80,12)) to land comfortably above 5:1, or raise the tint opacity slightly. Cosmetic, not blocking.

---

## Cross-cutting / journey note

The model section's journey is otherwise coherent: a user lands, sees the local model is "Running," understands cloud is off and what turning it on means, can paste and save a key (masked), set a model, and is told local is always the fallback. The **one** thing that breaks the trust spine is UX-001 — and it breaks it precisely on the privacy promise that is the product's reason to exist. Everything else in this section is at or near release quality. Fix UX-001 and bind the card copy to `c.backend` (which also resolves UX-002), and this section clears the bar.

## Verdict

**NOT a pass — 1 Critical (UX-001) must be fixed.** The cloud-model card asserts a cloud model is local and that "nothing leaves your computer," directly contradicting the product's privacy guarantee and the correct callout a few lines below. It is an isolated, low-risk frontend copy fix (branch one sentence on `c.backend`). The remaining items are 2 Minor + 2 Nit. The masked-key handling, privacy framing, status states, and accessibility baseline are genuinely strong and deserve credit.
