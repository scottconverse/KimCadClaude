# 02 — Senior UI/UX Designer deep-dive

**Audit:** KimCad Stage 8.5 · Slice 6 — in-app Settings screen + experimental-generator inline offer
**Role:** Senior UI/UX Designer (balanced posture; UI/UX = #1 acceptance gate)
**Date:** 2026-06-04
**Altitude:** Software-complete. The model-free demo server (`localhost:8810`) was driven live for rendered evidence. **The JPEG screenshot tool times out in this environment, so all rendered evidence is DOM / computed-style / `getBoundingClientRect` measurement, not pixel captures.** I do not flag "LLM not running" — that's out of altitude.

## What I checked rendered vs. static

**Rendered (live, via `preview_eval` against the running demo):**
- Settings screen loads at `#/settings`; all seven cards present in spec order (Printer & material → Units → AI model → Cloud acceleration → Experimental → Tools → About).
- gemma4:e4b shown as THE model (`<code>gemma4:e4b</code>`, status "Running"), **no dropdown of alternatives** — confirmed via DOM.
- Contrast ratios computed from live computed-styles for `.kc-switch-on`, `.kc-unit-btn-active`, `.kc-set-badge-cloud`, `.kc-set-badge-exp`.
- Touch-target heights measured at 375px for switches, selects, small buttons, inputs, links, topbar nav, brand.
- Masked-key state, Replace→password-entry transition, Reset two-step, `role=switch`/`aria-checked`, `aria-current` nav state, `aria-pressed` unit toggle, tools text labels, switch focus-visible outline.
- Horizontal-overflow check at 375px.

**Static (source only):**
- The **experimental inline offer** (`ChatPanel.tsx` `kc-exp-offer`) — the demo's box matches a template, so `result.status === 'needs_experimental'` does not fire live. Assessed from source + CSS. Limitation noted in UX-104.
- The `@media (pointer: coarse)` vs `(max-width: 640px)` rule split (the root cause of the touch-target findings) — confirmed in `styles.css`.

---

## Severity summary

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

No Blockers, no Criticals. This is a well-built, accessible screen. The two Majors are both touch-target gaps on the primary mobile interaction controls; everything else is polish.

---

## Findings

### UX-101 — Major — Accessibility / Responsive — The on/off switches are 24px tall on mobile (below the 44px touch floor), and unlike the rest of the chrome they get NO size bump on any narrow context

**Evidence (rendered, 375×812):** `.kc-switch` (both the Cloud acceleration toggle `[aria-label="Use a cloud model"]` and the Experimental toggle) measures **42×24px** via `getBoundingClientRect`. The WCAG 2.5.5 / Apple HIG floor is 44×44.

**Root cause (static):** `styles.css` has three separate 44px touch-bump rules — `@media (pointer: coarse)` at line 618 (covers `.kc-btn`, `.kc-icon-btn`, `.kc-chip`, selects, `.kc-design-act`), the `(pointer: coarse), (max-width: 640px)` belt-and-suspenders for `.kc-unit-btn`/`.kc-pval-btn` (line 893) and `.kc-version-pill` (line 1904), and the `(max-width: 640px)` bump for `.kc-set-select` (line 2330). **`.kc-switch` appears in none of them.** So the switch is 24px tall on a real touch phone (coarse pointer) AND on a narrow viewport. The switch is the single most important new interaction on this screen — it's how the user arms Cloud (which sends prompts off-machine) and arms the Experimental untrusted generator. A 24px target for the two highest-consequence toggles in the product is the finding to fix first.

**Why this matters:** A 24px-tall switch is hard to hit cleanly with a thumb; a mis-tap on the Cloud switch toggles a privacy-relevant setting. Small switches also read as "secondary/unfinished" against the otherwise-tactile chrome.

**Blast radius:**
- Adjacent code: `.kc-switch` is defined once (line 2167) and used only on this Settings screen (Cloud + Experimental). Fixing it here fixes both instances. No other surface uses `.kc-switch` today.
- Shared state: none.
- User-facing: the two toggles become reliably tappable on phones; desktop is unchanged (the visual track stays 42×24 — grow the *hit area* with transparent padding so the pill doesn't balloon).
- Migration: none.
- Tests to update: none known (no test asserts switch height).
- Related findings: UX-102 (same root: missing narrow-viewport touch bump), UX-103 (topbar nav, same `coarse`-only gap).

**Fix path:** Add `.kc-switch` to the `(pointer: coarse), (max-width: 640px)` block. Keep the painted pill at 42×24 but expand the tap target to 44px tall via vertical padding + `background-clip: content-box` (the same technique already used for `.kc-range` at line 644), or wrap with a 44px-min-height flex hit area. Example:
```css
@media (pointer: coarse), (max-width: 640px) {
  .kc-switch { min-height: 44px; padding-block: 10px; background-clip: content-box; }
}
```

---

### UX-102 — Major — Accessibility / Responsive — The small action buttons (Save / Replace / Reset…) are 35px tall on mobile; they have no 44px bump on any narrow context

**Evidence (rendered, 375×812):** `.kc-btn-sm` measures **35.3px tall** for all three: "Replace" (72px wide), "Reset…" (full-width 289.8px), and the cloud-key "Save". The key-entry "Save" and the danger "Reset everything" share the class, so all settings-screen action buttons inherit the 35px height.

**Root cause (static):** `.kc-btn-sm` (line 2247, `padding: 8px 13px`, ~35px tall) is in none of the 44px media blocks. Same class-coverage gap as UX-101.

**Why this matters:** Save commits the user's OpenRouter key; Reset everything is destructive. Both deserve a confident, full-size touch target on mobile. 35px is close, but below the floor, and inconsistent with the selects on the same screen (which correctly hit 44px).

**Blast radius:**
- Adjacent code: `.kc-btn-sm` is used on this screen (Save, Replace, Reset…, Reset everything, Cancel) and the accent/danger variants build on it (`.kc-btn-accent-sm`, `.kc-btn-danger-sm`). A single rule fixes all.
- User-facing: action buttons become tappable on phones; desktop unchanged if scoped to the narrow/coarse media block.
- Migration: none. Tests to update: none known.
- Related findings: UX-101, UX-103 (shared root cause — the touch-bump rule list never got the Slice 6 controls added).

**Fix path:** Add `.kc-btn-sm { min-height: 44px; }` inside the `(pointer: coarse), (max-width: 640px)` block. The destructive `.kc-btn-danger-sm` ("Reset everything") and its "Cancel" sit side-by-side in `.kc-reset-confirm`; at 375px verify they don't crowd — consider `flex-wrap` or stacking so a fingertip reaching Cancel can't land on Reset everything (the same destructive-separation pattern already applied to My Designs Delete at line 638).

---

### UX-103 — Minor — Responsive — Topbar nav buttons (My Designs / Settings) are 32px tall when a desktop is resized to 375px; they only reach 44px on a real coarse-pointer device

**Evidence (rendered, 375×812):** `.kc-topbar-actions .kc-btn` — "My Designs" 93.7×32.4, "Settings" 74.1×32.4. The brand home link is 121×32.

**Root cause (static):** `.kc-btn` gets `min-height: 44px` **only** under `@media (pointer: coarse)` (line 618), with no `(max-width: 640px)` arm. On a real phone (coarse pointer) these are 44px and fine; on a desktop narrowed to phone width they're 32px. The author already learned this exact lesson elsewhere — the `.kc-unit-btn`, `.kc-version-pill`, and `.kc-design-act` rules all carry both arms with an inline comment explaining "a desktop resized to 375px never reports `pointer: coarse`." The topbar `.kc-btn` rule predates Slice 6 and never got the second arm.

**Why this matters:** Lower severity than UX-101/102 because on actual touch hardware these controls ARE 44px — the gap only shows on a resized desktop. But it's the same one-line inconsistency, and the topbar is global chrome, so fixing it is cheap and broadly felt.

**Blast radius:**
- Adjacent code: `.kc-btn` is the global button — adding a `(max-width: 640px)` arm affects every `.kc-btn` (topbar nav, "New design", accent/dark variants). That's the intended outcome (consistent 44px on narrow), but regression-check the landing CTA and refine-send so nothing grows awkwardly. The `.kc-refine-send` already has its own coarse bump (line 2373) — leave it.
- User-facing: narrow-desktop and (already-correct) phone nav both reliably 44px.
- Migration: none. Tests to update: none known.
- Related findings: UX-101, UX-102 (same root: the coarse-only touch rule).

**Fix path:** Change line 618 from `@media (pointer: coarse) {` to `@media (pointer: coarse), (max-width: 640px) {`, matching the pattern the rest of the file already standardized on. One-line change, closes UX-101/102/103 if the Slice 6 selectors are also added to that block.

---

### UX-104 — Minor — State / Journey — The experimental inline offer could not be triggered live (template-match demo); offer copy is good but lacks a visible "what if I decline?" affordance beyond the refine box

**Evidence (static, `ChatPanel.tsx` lines 189–202 + `styles.css` `.kc-exp-offer` line 2285):** When `result.status === 'needs_experimental'`, the chat thread renders a warn-toned card: a bold `Experimental · may not be perfect.` line explaining the locked sandbox + mandatory printability check, then a single accent button "Try the experimental generator". The card never auto-runs — the user must opt in or re-describe in the refine input below. The demo server's design request matches a template, so `needs_experimental` does not fire; I could not capture this state rendered. **Limitation stated per task.**

**Assessment from source:** The copy is honest and well-pitched (sets expectations: "may not be perfect," "you'll see exactly what happens"). The warn-amber styling (`color-mix` of `--kc-warn-accent`) correctly signals "proceed with care" without alarming. The offer-not-run philosophy is the right call for an untrusted generator. One soft gap: the card presents one button ("Try…") with the decline path being the implicit refine input beneath it. A first-timer may not realize "or just rephrase your request" is the alternative. Consider a one-line secondary hint inside the card.

**Why this matters:** Minor — the refine input is right there and labelled, so there's no true dead-end. But naming the alternative reduces the chance a user feels cornered into the experimental path.

**Blast radius:**
- Adjacent code: `.kc-exp-offer` is unique to `ChatPanel.tsx`. The matching Settings-card copy (`SettingsPanel.tsx` `.kc-set-callout-warn`) should stay tonally consistent with any reword.
- User-facing: only users who hit a no-template request.
- Related findings: none.

**Fix path:** Add a muted secondary line under the button, e.g. *"Or describe the part differently below and I'll try a template first."* Recommend the dev team also wire a fixture/route so `needs_experimental` can be exercised in the demo — this state is currently invisible to rendered QA, which is itself a coverage gap worth a Test-Engineer note.

---

### UX-105 — Minor — Visual hierarchy / Copy — The default "Optional" status badge on Cloud acceleration is muted grey; against the privacy weight of the section it reads as quieter than the toggle deserves

**Evidence (rendered):** With Cloud off, the badge text is "Optional" in `--kc-muted` (`.kc-set-badge`, no modifier). When toggled on it becomes "On" in accent-deep at 5.85:1. The privacy callout below ("This sends your prompt off your machine") is the louder element, which is correct — but the at-a-glance state indicator for the most consequential toggle is the quietest chip on the card.

**Why this matters:** Minor. The privacy callout carries the real weight, and the toggle's `aria-checked` + visual position convey state. But "Optional" as muted grey slightly under-signals that this is the off/safe default. A user scanning for "is cloud on?" relies on the toggle, not the chip.

**Fix path:** Leave the privacy callout as the hero. Optionally strengthen the off-state chip copy to "Off" (parallel to the on-state "On") rather than "Optional" — "Off"/"On" is a cleaner binary the eye parses instantly, and "Optional" is already conveyed by the section sub-copy. Nit-adjacent; flag once.

---

### UX-106 — Nit — Copy — "Reset…" ellipsis vs. the two-step confirm

**Evidence (rendered):** The button reads "Reset…" (ellipsis = "opens further UI"), and clicking it reveals "Reset everything" + "Cancel" inline. The ellipsis convention is satisfied (it does open a confirm step). No change needed — calling it out only to credit the correct use of the ellipsis affordance.

---

### UX-107 — Nit — Accessibility — Inline text links (Get a free OpenRouter key, Refresh, check again) are ~18px tall

**Evidence (rendered, 375px):** `a.kc-set-link` ("Get a free OpenRouter key →") = 164.9×18.1; `.kc-model-refresh` ("Refresh") = 42.9×18.1. These are inline text links, not primary controls, so the 44px floor is softer (WCAG 2.5.5 exempts inline links in a text block). Noted for completeness; no action required unless the team wants belt-and-suspenders spacing on the standalone "Refresh"/"check again" links, which sit on their own line and are slightly more button-like.

---

## What's working (specific credit)

- **The contrast discipline is exactly right.** Every white-on-accent surface uses `--kc-accent-strong` (#b1542f), not the raw `--kc-accent` (#c8623a). Measured live: `.kc-switch-on` white knob = **5.03:1**, `.kc-unit-btn-active` white label = **5.03:1**, `.kc-set-badge-cloud` accent-deep text = **5.85:1**, `.kc-set-badge-exp` warn text = **5.1:1**. The raw accent would be 3.99:1 (fail); the author knew this and routed around it with inline comments. This is the single most common contrast trap and it was avoided everywhere on the screen.
- **gemma4:e4b is presented as THE model — a health readout, not a menu.** No dropdown of alternatives anywhere in the DOM. Status surfaces honestly ("Running" / "Not running" / "Model not pulled") with a concrete next action and no dead-ends. Exactly the trust posture the product wants.
- **The privacy callout is the right design.** Cloud is off by default, the toggle is honest, and the "This sends your prompt off your machine" callout is bold, plain-English, and placed before the config fields. Local-first is reinforced, not buried.
- **Key handling is exemplary.** Saved key shows masked with only the last 5 chars (`••••••••••••••••ABCDE`), readonly; Replace swaps to a `type="password"`, `autocomplete="off"` entry; the full value never appears. Labelled inputs throughout.
- **a11y fundamentals are clean.** `role="switch"` + `aria-checked` on both toggles; `aria-pressed` on the unit toggle; `aria-current="page"` on the active Settings nav button; `role="status"`/`aria-live` on the save note and model status; tools status uses TEXT labels ("Installed"/"Not found"), never color alone (WCAG 1.4.1); focus-visible outlines render on the switch (measured ~2px solid). The brand wordmark is a real focusable `<button aria-label="KimCad — home">`.
- **No layout breakage at 375px** — `scrollWidth === clientWidth === 375`, no horizontal overflow; the `.kc-set-row` stacks and selects go full-width via the `max-width: 640px` block.
- **Reset is a deliberate two-step** ("Reset…" → "Reset everything" + "Cancel"), and resetAll also clears the unit store and drafts — no half-reset state.

## Cross-cutting note

The two Majors (UX-101, UX-102) and one Minor (UX-103) share a **single root cause**: the Slice 6 controls (`.kc-switch`, `.kc-btn-sm`) and the legacy topbar `.kc-btn` were never added to the file's standardized `(pointer: coarse), (max-width: 640px)` touch-bump pattern. The author had already solved this exact problem for `.kc-unit-btn`, `.kc-range`, `.kc-version-pill`, and `.kc-design-act` — with an inline comment explaining why both media arms are needed. Slice 6's new controls simply didn't get folded into that pattern. **One coordinated CSS change** (add `.kc-switch` and `.kc-btn-sm` to the dual-arm block, and add the `(max-width: 640px)` arm to the line-618 `.kc-btn` block) closes all three. Recommend grouping them as one fix.
