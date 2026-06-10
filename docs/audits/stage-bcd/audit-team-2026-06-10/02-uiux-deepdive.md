# UI/UX Deep-Dive — KimCad (Stage C/D UI surfaces)

**Audit date:** 2026-06-10
**Role:** Senior UI/UX Designer
**Scope audited:** Stage C/D copy + decision surfaces at commit `5a07381`: Settings key-storage disclosure (`SettingsPanel.tsx`) and its wizard variant (`FirstRunWizard.tsx`); landing draft preservation + "Picked up where you left off" (`Landing.tsx` / `App.tsx`); the new-design `window.confirm`; warn→proceed bridge (`RightPanel.tsx`) + slice caution (`ExportPanel.tsx`); de-jargoned Printability badge + connective line; Enter hint, friendly model name, universal chips (`ChatPanel.tsx`); photo-discard line (`PhotoOnramp.tsx`).
**Auditor posture:** Balanced
**Verification:** Static review of all listed components + `styles.css` + `designStatus.ts` / `glossary.ts`, plus a live demo run (`kimcad.cli web --demo`, port 8701 via preview harness, ~397px viewport): walked landing → design → workspace → New design, captured the live confirm string firing on unsaved-in-flight work, confirmed the connective line / badge ("Passed") / engine chip / Enter hint / universal chips render, and confirmed no confirm fires on saved work.

---

## TL;DR

The Stage C/D copy work is genuinely good: honest, concrete, consistently in the Workshop voice ("Anyone who can read your files could read it" is exactly the right register for a trust disclosure). The decision surfaces — warn→proceed bridge, slice caution, unsaved-only confirm — correctly close the loops the prior audit flagged. The two real weaknesses are **pattern, not copy**: the new-design confirm uses a native `window.confirm` in an app that already owns two better confirm patterns, and the accumulated reassurance notes are starting to stack — the photo confirm card now carries four lines of 12px small print that say "private" twice. Nothing here blocks the stage gate.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 6 |
| Nit | 2 |

## What's working

- **The key-storage disclosure (SettingsPanel.tsx:357–364)** — branches honestly on the live `key_storage` value, names the real mechanism ("Windows Credential Manager"), and the file-fallback variant states the actual risk in plain words. This is best-in-class trust copy; verified the demo backend reports `keyring` so the strong variant is what users on this class of machine see.
- **The warn→proceed bridge (RightPanel.tsx:411–415) + slice caution (ExportPanel.tsx:177–181)** — the amber verdict now explicitly grants permission ("you can still slice it") and the enabled Slice button carries a matching caution. The two ends of the decision reference each other ("review the risks in the Readiness card first") — a closed loop, not two orphan notes. Both use `--kc-warn-text` at 600 weight, correctly louder than the muted notes around them.
- **De-jargoned gate badge (designStatus.ts gateLabel + RightPanel.tsx:558–563)** — "Passed / Needs review / Failed" with the card title supplying the subject; the same vocabulary is reused by the Compare card, so the gate speaks one language everywhere. Verified live: badge renders "Passed".
- **The connective line ("The detail behind the readiness score above.", RightPanel.tsx:556)** — at 12.5px with negative top margin it reads as a subtitle under the Printability title, exactly the right hierarchy for a relationship statement. Verified live at ~400px: the stacked card order keeps "above" truthful on narrow viewports too.
- **Unsaved-only confirm logic (App.tsx:502–509)** — saved work never nags; verified live that New design from a saved design navigates silently, and that the confirm fires for an in-flight first design. The *policy* is right (the finding below is about the *vehicle*).
- **Enter hint (ChatPanel.tsx:301)** — "Enter to send · Shift+Enter for a new line" states the keyboard contract exactly where the risk of accidental send lives. Quiet (11.5px muted), correct.
- **Universal chips (ChatPanel.tsx:260–273)** — "Make it wider / taller / smaller / Thicker walls" apply to every part family; correctly hidden during a clarification turn so the user answers the question instead of firing a generic edit. Verified live.
- **Friendly model name in the wizard (FirstRunWizard.tsx:223–226)** — "KimCad local AI" leads, the slug demoted to a mono detail. Right ordering for a non-developer audience.

## What couldn't be assessed

- **Warn-gate rendering live** — the demo design produced a pass gate; the warn bridge/caution were verified in code + CSS only.
- **The `key_storage === 'file'` fallback live** — this machine has a working keyring; the file-variant strings were verified in code only.
- **Real screen-reader behavior** of the native confirm and the photo card's note sequence (no NVDA/VoiceOver session in this harness — consistent with the dev's own deferral note at ChatPanel.tsx:187–191).
- **`window.confirm` behavior inside the planned WebView2 shell** (Stage 11 is not built yet) — flagged below as forward risk, not verified.

---

## First impressions

Arriving cold at the landing (~400px): the hero question, one obvious primary action, the honest "Runs entirely on your machine" promise, and a photo on-ramp clearly subordinate to the text path. The voice is consistent from landing through Settings — first-person-adjacent, concrete, never marketing-speak. The Stage D additions blend in; nothing reads bolted-on. The one tonal break a user will eventually hit is the OS-chrome `window.confirm` ("127.0.0.1:8714 says…") — the only moment the app stops sounding like KimCad.

## Journey walkthroughs

### Journey: first design → cancel → return → New design

Landing → example chip → workspace (instant in demo). "Saved · My Designs" appears in the topbar; New design navigates back with no nag — correct. Submitting a fresh prompt and clicking New design ~60ms in (still busy, nothing saved) fires `Start over? Your current description isn't saved yet.` — the right gate at the right moment, in the wrong dialog (UX-101) and with a follow-through wrinkle (UX-103). A cancel-while-busy lands back on the Landing with the prompt re-seeded and "Picked up where you left off." — the draft-preservation loop works as designed (verified in code; the demo design completes too fast to cancel interactively).

### Journey: warn-gate part → decision → slice

(Code-verified.) Amber verdict → "This should print, but check the risks below first — you can still slice it." → risks list → Slice button enabled → "Slicing with cautions — review the risks in the Readiness card first." The user is told they may proceed, what to check, and where — no dead end, no implicit decision. This is the strongest journey fix in Stage D.

---

## Findings

### [UX-101] — Major — Pattern — The new-design confirm is a native `window.confirm` in an app that owns two better confirm patterns

**Evidence**
`App.tsx:509`: `window.confirm('Start over? Your current description isn't saved yet.')`. Captured live: the browser-chrome dialog fires (origin-prefixed — "127.0.0.1:8714 says" in Chrome) when New design / the logo / the `n` shortcut is invoked over unsaved in-flight work. Meanwhile the app already ships an inline two-button confirm (Settings → "Reset everything / Cancel", SettingsPanel.tsx:454–467) and styled modal overlays (wizard, shortcuts help).

**Why this matters**
Three compounding costs. (1) **Tone**: this is the only moment the Workshop voice is replaced by OS chrome with an IP-address prefix and OK/Cancel buttons — "OK" is precisely the vague non-verb label the rest of the app avoids, and it's the *destructive* choice. (2) **Behavior**: `confirm()` blocks the main thread, so during a busy run the elapsed counter and phase poll freeze behind the dialog (cosmetic but visible). (3) **Forward fragility**: Stage 11 plans a WebView2 shell; embedded hosts that suppress script dialogs make `confirm()` return `false` silently — New design would become a dead button exactly when the user has unsaved work. To be fair: the native dialog is keyboard- and SR-accessible out of the box, and the *unsaved-only* policy is right — this finding is about the vehicle, not the gate.

**Blast radius**
- Adjacent code: `App.tsx handleNewDesign` — reached from the Topbar New design button, the logo (`onHome`), and the `n` shortcut (`shortcutsRef`). One call site, three entry points.
- User-facing: the confirm moment in the core "start over" flow; no other surface uses `window.confirm` (verified by grep).
- Migration: none — swap to the existing inline-confirm or a small styled dialog. The Settings reset pattern (state flag + two labeled buttons) is the cheapest consistent fix; a focused modal matching the wizard overlay is the richer one. Use action-verb labels: **"Start over" / "Keep working"**.
- Tests to update: no existing test exercises the confirm (grep over `*.test.tsx` finds no "Start over" — see related finding); the replacement should land with one.
- Related findings: UX-103 (the dialog's premise vs. what actually happens), TEST-side gap (no coverage of UX-001/UX-005 Stage D behaviors).

### [UX-102] — Major — Visual hierarchy / Copy — Reassurance-note stacking: the photo confirm card carries four lines of small print and says "private" twice

**Evidence**
`PhotoOnramp.tsx:191–239` (workspace variant): header privacy line "Read locally — your photo never left your machine." (12px muted) + seed textarea + note 1 "A photo can't tell us scale…" + note 2 "The photo isn't saved anywhere — only this description continues." + note 3 "This starts a new part from the photo — your current part is saved in My Designs." All four are 12px `--kc-muted` with identical styling (`styles.css:3199–3229`). The same drift shows elsewhere: the Printability card stacks two near-identical muted lines (connective line 12.5px + headline 13px, RightPanel.tsx:556/575), and the Export panel can stack the no-profile note, the slice caution, and the formats note.

**Why this matters**
Each note individually passed review; together they've become a wall of undifferentiated fine print. Uniform small muted text means the user's eye ranks nothing — the scale warning (which materially affects their next action: fix the sizes) has the same visual weight as the workspace-variant footnote. And privacy is asserted twice in one card ("never left your machine" / "isn't saved anywhere"), which paradoxically reads less confident than saying it once, completely. This is a systemic pattern (Major per framework: a systemic pattern is Major even when each instance is Minor) and it will worsen — Stage 9/10 will want notes on these same cards.

**Blast radius**
- Adjacent code: `PhotoOnramp.tsx` (both variants), `RightPanel.tsx` PrintabilityCard, `ExportPanel.tsx` notes block — all consumers of the `kc-muted-note` / `kc-photo-note` single-tier note style in `styles.css`.
- User-facing: photo on-ramp confirm (landing + workspace), Printability card, Export & print card.
- Migration: none — copy merge + one CSS tier.
- Tests to update: `PhotoOnramp.test.tsx` asserts on note strings; expect 2–4 assertions to change.
- Related findings: UX-101 (same root: each fix added a surface instead of composing with existing ones).

**Fix path**
Merge the two privacy lines into the header: *"Read locally — your photo never left your machine and isn't kept; only this description continues."* Keep the scale note as the single emphasized note (it's the actionable one — consider the `kc-slice-caution` weight treatment), and let the workspace-variant line stay as the one truly-muted footnote. Net: 4 lines → 2 (+1 in workspace), and the actionable note gains rank. On Printability, fold the connective line and headline tiering: connective line is fine as-is; ensure `report.headline` reads as the card's lede (13.5px) rather than a second muted whisper.

### [UX-103] — Minor — Journey / Copy — After confirming "Start over," the landing re-seeds the prompt the user just chose to abandon

**Evidence**
`App.tsx`: `handleNewDesign` (502–529) never clears `landingDraft` (set at handleSubmit:401, cleared only on design success:365). Cancel-while-busy → confirm "Your current description isn't saved yet." → OK → Landing renders with the abandoned prompt re-seeded and "Picked up where you left off."

**Why this matters**
The dialog warns the description will be lost; accepting it then presents the description, un-lost, under a note implying deliberate preservation. Benign (generous, even) but self-contradictory — the user just said "start over" and the app didn't. It mildly undermines the credibility of the new confirm.

**Fix path**
`setLandingDraft('')` inside the confirmed branch of `handleNewDesign`. Keep preservation for *cancel/failure* paths (UX-001's actual intent). Add the missing test alongside.

### [UX-104] — Minor — Pattern — Enter submits in the refine box (with a hint) but not in the landing box (without one)

**Evidence**
`ChatPanel.tsx:147–152` Enter sends, hint at :301. `Landing.tsx:62–79`: textarea inside a form, no key handler — Enter inserts a newline; only the button submits.

**Why this matters**
The two prompt boxes are the same mental object ("tell KimCad what you want") with different keyboard contracts, and the contract is only documented on the second one the user meets. A user who learns Enter-sends in the workspace will press Enter on the landing and get a silent newline.

**Fix path**
Adopt the refine box's contract on the landing textarea (Enter submits, Shift+Enter newline) and reuse the same `kc-key-hint` line under it.

### [UX-105] — Minor — Copy — Settings AI-model description still leads with the raw slug, undoing UX-011's ordering

**Evidence**
`SettingsPanel.tsx:250–253`: "`gemma4:e4b` — KimCad's local AI. …" vs the wizard's "KimCad local AI `gemma4:e4b`" (FirstRunWizard.tsx:223–226).

**Why this matters**
The friendly-name-first decision was made and shipped in the wizard but not propagated to the surface users revisit. Suggested rewrite: *"KimCad's local AI (`gemma4:e4b`). Runs on your machine, on your CPU. No internet required; nothing leaves your computer."*

### [UX-106] — Minor — Copy — The wizard's file-fallback key note omits the risk sentence the Settings note carries

**Evidence**
`FirstRunWizard.tsx:318–320`: file case says only "The key is kept in a settings file on this computer." Settings (SettingsPanel.tsx:359–361) adds "Anyone who can read your files could read it."

**Why this matters**
The wizard is where the key is *first pasted* — the disclosure should be at least as complete at entry as on review. Exposure is limited (keyring-unavailable machines only), hence Minor. Fix: append the same risk sentence, or a compact "(readable by anyone with access to your files)".

### [UX-107] — Minor — Accessibility — The engine chip's explanation lives only in a hover `title`

**Evidence**
`RightPanel.tsx:566–573`: `kc-engine-badge` carries its meaning in `title=` only; neighboring terms (gate, readiness, confidence) get the focusable `InfoTip` treatment.

**Why this matters**
Touch users, keyboard users, and screen readers never receive the explanation of what "Engine: OpenSCAD/CadQuery" means or why it matters (STEP availability). Inconsistent with the card's own InfoTip pattern. Fix: add a glossary `engine` entry and render `<InfoTip term="engine" />` beside the chip; keep or drop the `title`.

### [UX-108] — Minor — State — "Picked up where you left off." persists after the user clears the box

**Evidence**
`Landing.tsx:58–60`: the note keys off the static `initialValue` prop; `value` is live state. Select-all-delete leaves the note above an empty textarea.

**Why this matters**
A claim ("picked up") that's no longer true once the user discards the draft. One-line fix: gate on `value !== ''` too (`{initialValue && value && …}`), or fade the note on first edit.

### [UX-109] — Nit — Copy — The gate InfoTip reintroduces the word the badge removed

**Evidence**
`glossary.ts:26–29`: the tip header renders "Gate" next to a badge that was deliberately de-jargoned (UX-008). The definition itself is fine. Consider retitling the entry "This check" or "Pass/fail check" — flag once, team's call.

### [UX-110] — Nit — Copy — Chip set offers grow on two axes but shrink on only one

**Evidence**
`ChatPanel.tsx:261`: "Make it wider / Make it taller / Make it smaller / Thicker walls" — no "shorter"/"narrower" counterpart. Defensible (four chips is the right count); noted for symmetry only.

---

## States audit matrix

| Component / surface | Default | Loading | Empty | Error | Notes |
|---|---|---|---|---|---|
| Landing + draft note | ✓ | ✓ (busy-disable) | ✓ | n/a | UX-108 stale-note edge |
| New-design confirm | ✓ | ✓ (fires while busy) | ✓ (no nag when saved — verified) | — | UX-101 vehicle, UX-103 follow-through |
| Settings key-storage note | ✓ (both branches) | ✓ | — | ✓ (save-failure note) | UX-106 wizard variant thinner |
| Printability card | ✓ | — | ✓ (idle copy) | ✓ (failed-attempt copy) | UX-102 note tiering |
| Readiness warn bridge | ✓ (code) | — | ✓ | ✓ | warn case not reproducible in demo |
| Slice caution | ✓ (code) | ✓ (Slicing…+Cancel) | — | ✓ | mutually consistent with bridge |
| Photo confirm card | ✓ | ✓ (cancelable read) | — | ✓ | UX-102 stacking |

## Accessibility snapshot

- Keyboard navigation: strong — `n`/`d`/`,`/`?` shortcuts correctly suppressed while typing and while the wizard owns the keyboard (App.tsx:192–232); native confirm is itself keyboard-operable.
- Focus visibility: not re-audited this pass (Stage A covered it); no new focus traps introduced by the Stage D surfaces.
- Color contrast: new notes use `--kc-muted` (Stage A brought tones to AA, pinned by `tone-contrast.test.ts`); warn notes use `--kc-warn-text` at 600 weight. No new raw colors introduced.
- Screen reader labeling: the thinking-row `aria-hidden` move (ChatPanel.tsx:187–199) is the right interim call, honestly documented as awaiting a real SR session. UX-107 is the one new labeling gap.
- Reduced motion: no new animation added by these surfaces.
- Touch targets: chips and note links unchanged from audited baselines; the engine chip is non-interactive (its tooltip is the issue, not its size).

## Patterns and systemic observations

1. **The copy system is winning; the note system is losing.** Stage D's strings are individually excellent, but the delivery mechanism is always "append another muted `<p>`." The product needs a two-tier note vocabulary (actionable caution vs. background reassurance) before Stage 9/10 add more surfaces — UX-102 is the start of that.
2. **One confirm, three patterns.** Native `confirm` (new design), inline two-button (Settings reset), styled overlay (wizard/help). Converge on the inline pattern for destructive-lite confirms before Stage 10's direct-print flow needs one (sending a job to a printer is exactly the next confirm moment).
3. **Decisions now have closing copy.** The warn→proceed bridge + slice caution pair is a repeatable pattern worth naming in the design notes: *state the permission at the verdict, echo the caution at the action.* Apply it to Stage 10's "send to printer."
4. **Stage D shipped UI behavior with no frontend test trace** for the confirm gate, draft preservation, or the draft note (grep over `*.test.tsx`: zero hits for "Start over" / "Picked up"). Cross-role: the Test Engineer should pick this up.

## Appendix: surfaces reviewed

- Live (demo, port 8701, ~397×912 viewport): `#/` landing, design run via example chip, workspace (Conversation, Versions, viewport, Printability card, refine chips/hint), New design from saved and from unsaved-in-flight (confirm string captured), `/api/settings` + `/api/health` payloads.
- Code: `frontend/src/App.tsx`, `components/Landing.tsx`, `components/SettingsPanel.tsx`, `components/FirstRunWizard.tsx`, `components/RightPanel.tsx`, `components/ExportPanel.tsx`, `components/ChatPanel.tsx`, `components/PhotoOnramp.tsx`, `designStatus.ts`, `glossary.ts`, `styles.css` (note/badge tiers).
