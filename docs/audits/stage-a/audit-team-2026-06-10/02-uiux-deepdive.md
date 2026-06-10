# UI/UX Deep-Dive — KimCad, Stage A surfaces

**Audit date:** 2026-06-10
**Role:** Senior UI/UX Designer
**Scope audited:** Stage A first-run hardening at commit `5aad7f3`, UI surfaces only: ModelHealthPill (Landing), FirstRunWizard step-4 honest recap ("Almost ready" path), the skip link, and the user-facing copy of the new error paths (`errors.py`, `cli.py` exception mapping, `webapp.py` typed responses, `designStatus.ts` rendering).
**Auditor posture:** Balanced
**Prior evidence relied on:** `docs/audits/walkthrough-stage-a-2026-06-10/WALKTHROUGH-REPORT.md` live-verified both pill states, both recap states, the skip link target, and the CLI/web model-down copy against a genuinely stopped Ollama. Those runtime facts are not re-litigated here; this pass goes deeper on copy quality, state transitions, and assistive-technology behavior, by close code reading.

---

## TL;DR

Stage A's UX instincts are right and unusually disciplined: the pill is silent when healthy, the recap refuses to say "you're all set" over a dead model, error copy is one friendly actionable sentence sourced from a single shared constant so CLI and web can't drift. The weakest dimension is the assistive-technology experience of the *recovery* affordance: in all three places it appears, "Check again" unmounts itself the moment it's pressed, destroying keyboard focus (inside the wizard, focus can escape behind the modal), and the `role="status"` regions are mounted with their content already in them, so screen readers are likely to announce neither the problem nor the recovery. The single most important takeaway: make the re-check round-trip a persistent, announced, focus-stable element — one fix pattern, three call sites.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 5 |
| Nit | 2 |

## What's working

- **The honest recap is the right pattern, executed honestly.** Step 4 re-probes on open (`FirstRunWizard.tsx:78-80`), demotes the headline to "Almost ready", drops the ✓ badge, puts the fix *on the Model row itself*, and still leaves "Start designing" available. The lede — "One thing still needs attention before KimCad can design — everything else is saved." — is exactly the right sentence: it scopes the problem, reassures about saved work, and doesn't block. Walkthrough confirmed both directions live.
- **Silence means healthy.** The pill renders nothing on the happy path and nothing when the probe itself fails ("stay silent rather than cry wolf", `ModelHealthPill.tsx:16`). No badge noise on a healthy landing is a mature choice most products get wrong.
- **One source of truth for the model-down sentence.** `MODEL_UNAVAILABLE_MESSAGE` (`pipeline.py:180`) is reused verbatim by the CLI mapping and the web typed response, and `designStatus.ts:75-81` prefers the backend's message with a sane fallback. The walkthrough measured the same friendly copy on both surfaces. This is how you prevent copy drift structurally, not by review.
- **Error copy reads like a person wrote it.** "KimCad couldn't reach your local AI. Make sure Ollama is running, then try again. You can check the AI's status in Settings." — what happened, what to do, where to verify. The CLI adds the exact `ollama pull` command and points at `kimcad models`. `ToolMissingError` carries its own recovery command and a config override path. The web 500 deliberately hides internals (QA-008) while telling you where the detail lives.
- **The recap demotion never flashes pessimistic.** `modelOk` derives from last-known status while a re-probe is in flight (`FirstRunWizard.tsx:150-155`), so the headline doesn't flicker to "Almost ready" mid-check on a healthy setup. The comment documents the intent.
- **Skip link is done properly.** First element in the shell (`App.tsx:572`), fixed-position, ink-on-bg (high contrast), revealed on `:focus-visible` with a visible outline (`styles.css:128-148`), and the walkthrough confirmed it's first-focusable and resolves to the active `<main>`.
- **The model-down wall has a one-click way back.** ChatPanel offers "Try again" on `model_unavailable` so recovery isn't a retype — the recovery journey was designed end-to-end, not just the error screen.

## What couldn't be assessed

- **Actual screen-reader output (NVDA/JAWS/VoiceOver).** Findings UX-A-001/002 are from close reading of the React mount/unmount behavior and ARIA live-region semantics, not a live SR session. Severity assumes typical NVDA/Chromium behavior; a live SR pass would confirm.
- **The pill's "model not pulled" variant and its 320px wrap.** The walkthrough exercised the *not-running* pill live; the *not-pulled* branch (`run "ollama pull …" first`) and the pill's wrapping behavior at 320px were not visually verified — demo mode can't force those states. By inspection the inline-flex pill should wrap acceptably, but this is unconfirmed.

---

## First impressions

Arriving at the landing with Ollama down: badge → headline → sub → **a warm amber pill in the natural read order, before the input** — "Your local AI isn't running yet — start Ollama to design. Check again". The eye finds it without it shouting; the input stays usable. This is the correct hierarchy for a warning that should inform but not gate. The pill's lozenge shape and 13.5px/600 weight sit comfortably between the hero sub and the input card; it reads as part of the page's voice, not a system toast bolted on. Visual fit: good.

## Journey walkthroughs

### Journey: first run with Ollama stopped → recovery

Wizard step 1 says "Ollama isn't running" with "Start Ollama, then check again. You can finish setup either way." — honest, non-blocking. Step 4 re-probes and demotes to "Almost ready" with the fix inline. Close the wizard: the landing pill repeats the same truth in the same words ("start Ollama"). Start Ollama, click "Check again": the pill clears. Sighted-mouse-user experience: coherent and truthful end-to-end.

The same journey on keyboard + screen reader is where it breaks down: pressing "Check again" removes the button you're focused on (UX-A-001), and the status regions likely never speak (UX-A-002). The user who most needs the re-check confirmation — one who can't visually watch the pill vanish — gets nothing.

---

## Findings

### [UX-A-001] — Major — Accessibility / State — "Check again" unmounts itself when activated, destroying keyboard focus (three call sites; in the wizard, focus can escape the modal)

**Evidence**
Code-verified, deterministic:
- `ModelHealthPill.tsx:22` — `if (checking || …) return null`. Clicking "Check again" sets `checking=true`, so the entire pill (including the focused button) unmounts for the duration of the probe, then remounts if still down.
- `FirstRunWizard.tsx:411` — the recap warn span renders only when `!modelOk && modelState !== 'checking'`; clicking its "check again" flips `modelState` to `'checking'` and unmounts the focused button.
- `FirstRunWizard.tsx:244-265` — step 1's action paragraphs have the same `modelState === 'ready'` condition; same unmount on activation.

**Why this matters**
When the focused element is removed, focus drops to `document.body`. On the landing, a keyboard user's next Tab restarts from the top of the page. Inside the wizard it's worse: the focus trap (`FirstRunWizard.tsx:85-114`) only intercepts Tab when the active element is the dialog's first/last focusable or the dialog root — with focus on `body`, the next Tab follows document order, and the first focusable in the document is the skip link *behind* the modal (`App.tsx:572`). A keyboard or switch user who uses the recovery affordance is silently ejected from the dialog. If Ollama is still down, the button remounts as a *new* element with no focus, so repeated re-checks mean re-Tabbing to the button every time.

**Blast radius**
- Adjacent code: `ModelHealthPill.tsx` (1 site), `FirstRunWizard.tsx` (3 sites: step-1 not-running, step-1 not-pulled, recap warn). One fix pattern applies to all four.
- User-facing: the model-down recovery loop — the exact flow Stage A exists to harden — for keyboard/AT users.
- Tests to update: `ModelHealthPill.test.tsx` ("Check again re-probes…") and `FirstRunWizard.test.tsx` (recap re-check tests) assert text presence, not focus; add focus-retention assertions (`document.activeElement` after click resolves).
- Related findings: UX-A-002 (same round-trip is also unannounced), UX-A-006 (same unmount causes the visual flicker).

**Fix path**
Keep the container mounted during the probe. In the pill: render the pill in a "Checking…" state (button disabled, spinner) instead of `return null` while `checking && model already known-bad`; only return null when healthy/unknown. In the wizard, drop the `modelState !== 'checking'` guard and swap the inner text to "Checking…" while keeping the button (disabled) in the tree. If the result is healthy and the element must go away, move focus deliberately first (e.g. to the textarea on the landing; to the "Start designing" button in the recap) — that's also a nicer success handoff.

---

### [UX-A-002] — Major — Accessibility — `role="status"` regions are mounted with their content, and the success path is removal — screen readers likely announce neither the problem nor the recovery

**Evidence**
- `ModelHealthPill.tsx:30` — the `<p role="status">` enters the DOM *already containing* the warning text. ARIA live regions announce *changes to* an existing region; content present at insertion time is inconsistently announced (commonly not, in Chromium + NVDA).
- The healthy outcome is the region's removal (`return null`) — removals are not announced. An SR user who activates "Check again" hears nothing whether it succeeded or failed.
- Same pattern in the wizard: step-1 swaps three *separate* `role="status"` spans (checking / error / labeled, `FirstRunWizard.tsx:224-238`), each newly mounted; the recap warn span (`:412`) mounts with its content.

**Why this matters**
The pill's entire job (UX-002) is "a down model must be visible BEFORE the user invests a prompt." For a screen-reader user, it likely isn't visible at all — they submit a prompt, wait, and hit the model-down wall the pill was built to prevent. And after pressing "Check again", silence in both directions makes the control feel broken.

**Blast radius**
- Adjacent code: `ModelHealthPill.tsx`; `FirstRunWizard.tsx` step-1 status spans and recap warn; same fix shape as UX-A-001 (a persistent region whose *text* changes solves both).
- User-facing: SR users on the landing and in the wizard — the not-ready discovery and the recovery confirmation.
- Tests to update: jsdom can't prove announcements; assert structure instead (one persistent `role="status"` node whose textContent transitions warning → "Checking…" → "" / "Local AI is ready").
- Related findings: UX-A-001 (one coordinated fix), UX-A-008.

**Fix path**
Render one *always-mounted* `role="status"` container per surface (visually empty when healthy) and change its text content: problem sentence when down → "Checking…" on re-probe → a brief "Your local AI is ready." on recovery (then optionally clear after a few seconds). This makes mount-time announcement moot, gives the success confirmation for free, and pairs naturally with the UX-A-001 fix.

---

### [UX-A-003] — Minor — Copy — CLI recovery copy hardcodes `gemma4:e4b` while the model is configurable

**Evidence**
`cli.py:507` and `cli.py:515` both say `` `ollama pull gemma4:e4b` `` literally. The configured model lives in `config/default.yaml` (`model_name:`) and is user-overridable; the pill and wizard correctly interpolate the live `model.model`.

**Why this matters**
A user who configured a different local model gets a recovery command that pulls the wrong model — confidently wrong advice in the one place (first failure) where trust is most fragile. It also contradicts `errors.py`'s own design note that surfaces "can never drift apart."

**Fix path**
Interpolate the configured model name (the `config` object is in scope for `design`/`bench` paths): `f"…pull the model if you haven't (\`ollama pull {config.llm.model_name}\`)…"`. Fall back to the default string only where config isn't loaded.

---

### [UX-A-004] — Minor — Color / Accessibility — Pill text contrast is marginally below WCAG AA

**Evidence**
Pill text `--kc-warn` `#876312` over the pill's effective background — `rgba(196,138,26,0.08)` composited on `--kc-bg` `#f0ebe0` ≈ `#ECE3D0` — computes to ≈ **4.3:1**. AA for 13.5px/600 (not "large text") is 4.5:1. Calculated, not eyeballed.

**Why this matters**
The warning sentence is the pill's payload; low-vision users on marginal displays are exactly the audience for a slightly darker ink. It's a near miss, but on the surface's key text.

**Fix path**
Darken `--kc-warn` to ~`#7a590f` (≈4.9:1 on the composited bg) or raise the pill's background alpha so the composite lightens. Verify the other `--kc-warn` consumers (`.kc-model-stat-warn`) on their backgrounds at the same time.

---

### [UX-A-005] — Minor — Visual hierarchy / Accessibility — "Check again" is distinguishable from surrounding text by color alone, and barely by color

**Evidence**
`.kc-link-btn` (`styles.css:2773`) renders `#9a4828` with no underline, same `font-weight: 600` as the pill text. Link-vs-surrounding-text contrast: ≈ **1.15:1** against the pill's `#876312`, ≈ **2.4:1** against the recap warn's ink — both far below the 3:1 WCAG 1.4.1 expects when color is the only cue, and there is no non-color cue.

**Why this matters**
"Check again" is the only recovery affordance, and to colorblind or low-vision users it reads as plain text. The phrasing invites a click, which softens this — but the affordance shouldn't depend on the user guessing.

**Blast radius (pattern):** `.kc-link-btn` is shared — pill, wizard step 1 (×2), recap, and `.kc-model-refresh` in Settings. One CSS rule fixes all sites.

**Fix path**
Add `text-decoration: underline` (or `border-bottom: 1px solid currentColor`) to `.kc-link-btn`. Underlined inline actions are the established convention; nothing else needs to change.

---

### [UX-A-006] — Minor — State / Motion — The pill pops in late (layout shift) and blinks out during re-check

**Evidence**
`ModelHealthPill.tsx:22` returns null while `checking`. On load, the landing renders complete, then the pill appears after the probe resolves, pushing the input card down ~45px — potentially as the user is clicking into the textarea. On "Check again" with Ollama still down, the pill vanishes for the probe duration and reappears: a blink that reads as "something happened" when nothing changed.

**Why this matters**
The shift can steal a click; the blink undermines confidence in the re-check. Both are the visual face of the UX-A-001 unmount.

**Fix path**
Covered by the UX-A-001 fix (stay mounted, swap text to "Checking…"). For initial load, accept the pop-in (reserving space for a usually-absent warning isn't worth it) but the in-place re-check removes the worst occurrence.

---

### [UX-A-007] — Minor — Visual hierarchy — The recap's warn state has no visual warn cue, inconsistent with step 1 and the pill

**Evidence**
`FirstRunWizard.tsx:412` applies `kc-wiz-model-warn` (which is just `color: var(--kc-ink)` — plain text) plus `kc-wiz-recap-warn`, **which has no rule anywhere in `styles.css`** — a dead class. Step 1 and the pill both pair their warnings with the amber `kc-statdot`; the recap row's warning is weight-600 ink, visually identical to the healthy "File download" value on the row below.

**Why this matters**
The recap is the *summary* screen — the one place a skimming user decides "am I done?". The headline demotes, but the row that names the one broken thing doesn't pull the eye. Wording-only signaling is colorblind-safe, which is good — but a small amber dot (the established vocabulary) would make the broken row scannable without relying on color alone.

**Fix path**
Either define `.kc-wiz-recap-warn` (amber statdot before the text, matching step 1) or remove the dead class. Recommend the dot: `…<span className="kc-statdot kc-statdot-warn" aria-hidden="true"/> not reachable yet — start Ollama, then check again`.

---

### [UX-A-008] — Nit — Copy — Backticks render literally in browser-facing strings

`webapp.py:1513` ("The terminal running \`kimcad web\` has the detail.") and `ToolMissingError`'s message (shown in the SPA via `render_failed`) carry Markdown backticks the SPA renders as literal characters. Fine in a terminal; slightly off in the chat bubble. Consider plain quotes for web-bound strings, or strip backticks client-side.

### [UX-A-009] — Nit — Copy — `ToolMissingError` speaks developer in a non-developer product

"Run \`python scripts/fetch_tools.py\`… or point binaries.openscad in config/local.yaml at your own copy" assumes a repo checkout and YAML literacy. Accurate for today's distribution; revisit the sentence when the Stage-11 installer makes "non-developer" literal. Flagging once, per the docs' non-dev voice goal (DOC-001).

---

## States audit matrix

| Component / state | Default | Loading | Success | Error/down | Notes |
|---|---|---|---|---|---|
| ModelHealthPill | ✓ (silent) | ✗ renders null — pop-in + blink (UX-A-001/006) | ✓ (silent; unannounced — UX-A-002) | ✓ both variants, good copy | probe-failure → silent, deliberate and documented |
| Wizard recap (step 4) | ✓ | △ warn span hidden mid-check, nothing in its place (UX-A-001) | ✓ "You're all set" + badge | ✓ "Almost ready" + inline fix | headline holds last-known — no pessimistic flash |
| Wizard step-1 model card | ✓ | ✓ spinner + "Checking…" | ✓ "Ready" | ✓ "Couldn't check" / "Ollama isn't running" / "Model not pulled yet" | most complete state set of the three |
| CLI model-down | ✓ exit 2, two lines | ✓ live phase line (walkthrough) | — | ✓ no traceback | UX-A-003 hardcoded model name |
| Web model-down | ✓ typed 200 `model_unavailable` | ✓ | — | ✓ + one-click "Try again" | shared message; verified live |

## Accessibility snapshot

- Keyboard navigation: skip link first-focusable and working; wizard traps Tab and honors Escape — **but** "Check again" activation drops focus (UX-A-001), and inside the wizard the drop can escape the trap.
- Focus visibility: `:focus-visible` outlines defined for the skip link and `.kc-link-btn` — good.
- Color contrast (computed): pill warn text ≈ 4.3:1 (UX-A-004, just under AA); "Check again" `#9a4828` on the pill bg ≈ 4.9:1 (passes); skip link ink-on-bg far above AA.
- Screen reader: `role="status"` placement is well-intentioned but the mount-with-content pattern likely yields silence (UX-A-002); decorative dots correctly `aria-hidden`; wizard dialog properly labeled via `aria-labelledby` per step.
- Color as sole indicator: pill pairs color with text (good); link affordance is color-only (UX-A-005); recap warn is wording-only (UX-A-007 — safe, but inconsistent).
- Reduced motion: the small spinners don't gate anything; no vestibular-risk motion in scope.

## Patterns and systemic observations

One root cause underlies both Majors and two Minors: **conditional rendering treats "checking" as "render nothing," which is hostile to focus, live regions, and layout.** The fix is a single pattern — a persistently mounted status container with text-content transitions — applied to four call sites. Fixing UX-A-001/002/006 and most of 007 together is one small, coordinated change.

Conversely, credit the systemic *strength*: error copy as shared constants with surface-specific mapping (`MODEL_UNAVAILABLE_MESSAGE`, `ToolMissingError`) is the right architecture for copy quality, and it shows — the Stage A strings are the best-written error messages in the product.

## Appendix: surfaces reviewed

- `frontend/src/components/ModelHealthPill.tsx` (+ `.test.tsx`), `frontend/src/components/Landing.tsx`
- `frontend/src/components/FirstRunWizard.tsx` (steps 1 and 4; + `.test.tsx`)
- `frontend/src/App.tsx:570-595` (skip link), `frontend/src/styles.css` (skip link, pill, link-btn, statdot, wizard recap rules)
- `src/kimcad/errors.py`, `src/kimcad/cli.py:476-521`, `src/kimcad/webapp.py:1487-1515`, `src/kimcad/pipeline.py:160-190`
- `frontend/src/designStatus.ts` (typed-status → user copy), `frontend/src/components/ChatPanel.tsx:215-225` ("Try again")
- Runtime evidence inherited from `docs/audits/walkthrough-stage-a-2026-06-10/WALKTHROUGH-REPORT.md` (live pill/recap/skip-link/CLI/web verification at 8701/8703, incl. 375px mobile screenshot)
