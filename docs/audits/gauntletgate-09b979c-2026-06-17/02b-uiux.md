# GauntletGate — Full lane · Senior UI/UX Designer deep-dive

**Project:** KimCad · **Commit:** `09b979c` (0.9.0b4 + cold-start managed-Ollama onboarding fix + b4+UI audit-watchlist remediation)
**Date:** 2026-06-17 · **Lane:** Full / UI-UX role (extends the Walkthrough lane's verified cold first-run)
**Method:** read the change delta (`c784a23..HEAD`) and the touched components; drove the **REAL app** (`kimcad web`, the live preview harness on port 8714, warm state — live Ollama `qwen2.5:7b` + `qwen2.5vl:3b`, OrcaSlicer + OpenSCAD bundled) to observe **rendered** states for the warm/returning, Settings, error/partial, and accessibility surfaces. State branches that don't occur naturally on the dev box were forced by intercepting `/api/model-status` in-page and reading the actual rendered DOM (not asserted from CSS). WCAG contrast computed numerically from the token values.

> **Scope note:** the cold/first-run wizard was verified by the Walkthrough lane (`02-walkthrough.md`) and is NOT re-walked here. This role extends to the warm landing, Settings, the wizard's non-cold branches, error/empty/partial states, the photo/sketch on-ramps, and accessibility across the app.

---

## Verdict

The product's UI quality is high and most of the b4 watchlist is genuinely closed (see "What's working"). **But the headline new code — the cold-start "managed Ollama" narrative — was applied to only two of the surfaces that talk about the local AI's health.** The Settings AI-model screen, the in-thread `model_unavailable` wall, and the photo on-ramp error still instruct a returning user to "Start Ollama" / "get Ollama" — the exact self-install dead-end the release set out to eliminate. In a realistic returning state (the managed engine isn't running) the **landing** gives the new, correct guidance while **Settings** gives the old, contradictory one — on the same machine, in the same session. That inconsistency is the one thing in this delta that undercuts the release's own thesis.

**No Blockers. No Criticals.** The contradiction is a Major (systemic copy inconsistency across surfaces, recoverable, no data/security exposure).

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 2 |
| Nit | 1 |

---

## Findings

### [UX-FULL-001] — Major — Copy / Journey consistency — The "managed Ollama" cold-start narrative was not propagated to Settings, the chat model-down wall, or the on-ramp error; a returning user is still sent to "Start / get Ollama"

**This is the new-code finding.** Commit `fc03873` rewrote the *wizard* (`FirstRunWizard.tsx:360`) and `ModelHealthPill.tsx:33-35` to the new promise — *"KimCad sets up its AI for you — no separate install … (Already have Ollama? KimCad uses it automatically.)"* — and the Walkthrough lane verified that path. Three other surfaces that speak to the same local-AI health were **not** updated and still carry the pre-fix self-install language:

- `frontend/src/components/SettingsPanel.tsx:451-463` — the AI-model action line for `backend==='local' && !model.running` renders:
  *"Ollama isn't running. Start it (or **get Ollama**), then check again."* with the **get Ollama** link → `https://ollama.com/download` (`openExternal`, line 457).
- `frontend/src/components/SettingsPanel.tsx:450` — the error branch: *"Couldn't reach Ollama."*
- `frontend/src/designStatus.ts:79-80` — the `model_unavailable` design-thread copy: *"Your local AI isn't running. **Start Ollama**, then try again — you can check its status in Settings."* (surfaced by `ChatPanel.tsx`'s model-down wall, whose decline line at `ChatPanel.tsx:224` reads *"Start Ollama first — see the AI's status in Settings."*).
- `frontend/src/api.ts:490-492` — the photo/sketch on-ramp surfaces *"Your local AI isn't running yet."* (less egregious — generic — but part of the same family).

**Verified live (rendered, not asserted).** Driving the real app and intercepting `/api/model-status` to return `running:false` (a returning user whose managed engine stopped — exactly the state the wizard says KimCad auto-manages), the same `running:false` state produced two contradictory messages in one session:

- **Landing** `.kc-model-pill` (rendered text): *"Your local AI isn't ready yet — finish setup (the wizard's "Set up KimCad's AI") to design."* ✅ new narrative
- **Settings** `.kc-model-action-line` (rendered text): *"Ollama isn't running. Start it (or get Ollama), then check again."* with rendered buttons `["get Ollama", "Check again"]` ❌ old dead-end

**Blast radius.** Every returning user whose local engine is down lands in this contradiction. The ModelHealthPill even points them *to Settings* ("see the AI's status in Settings") — so the natural next click takes them from the correct message to the wrong one. The release's central claim ("no separate install; KimCad manages its own engine") is silently reversed for a user who reads Settings: they're told to download and run a tool the product just promised they'd never have to touch. This is a trust regression precisely on the dimension this commit exists to fix.

**Fix path.** Make Settings' `!running` branch and the `model_unavailable` copy mirror the wizard/pill narrative: drop "get Ollama" / "Start Ollama" as the primary instruction; lead with the in-app setup ("KimCad will set this up — open setup" / route to the wizard's "Set up KimCad's AI"). The `running && !model_present` branch already does the right thing (`SettingsPanel.tsx:464-471` → CTA "Open setup" → `kimcad-rerun-setup` event); extend that same re-entry to the `!running` branch so Settings has a path *into* the managed setup, not *out* to ollama.com. Keep a single small "advanced: already running your own Ollama?" affordance if desired, but it must not be the headline instruction.

**Suggested test.** A rendered-state test (RTL) asserting that with `getModelStatus → {backend:'local', running:false}` the SettingsPanel action line does **not** contain "get Ollama"/"Start it" and **does** offer an in-app setup re-entry; symmetrically that `designStatus` `model_unavailable` copy names the in-app setup, not "Start Ollama." (Note: existing tests `SettingsPanel.test.tsx:133-143` and `ChatPanel.test.tsx:153-159` currently *assert the old copy*, so they will need to flip with the fix — they're codifying the stale language today.)

---

### [UX-FULL-002] — Minor — Journey — Settings `!running` AI branch has no route into the in-app setup (asymmetry with `!model_present`)

`SettingsPanel.tsx`'s precedence action line gives the `running && !model_present` case a CTA that re-enters the managed setup wizard (cta "Open setup", clears `kc-first-run-done`, fires `kimcad-rerun-setup` — lines 464-471). The `!running` case (lines 451-463) gets only an external "get Ollama" link + "Check again" — no path into the very setup flow that the wizard advertises as the fix. So the surface that's *most* likely to be visited by a confused returning user (engine not running) is the one with *no* in-product recovery. This compounds UX-FULL-001 and should be fixed together: give `!running` the same "Open setup" re-entry.

**Fix path.** Reuse the `onCta` from the `!model_present` branch for the `!running` branch. **Test:** assert the `!running` action line's button dispatches `kimcad-rerun-setup`.

---

### [UX-FULL-003] — Minor — Information scent — Cloud "On" badge with no key reads as "active" when the effective backend is still local

Observed live (this dev profile): `/api/settings` = `cloud_enabled:true, has_cloud_key:false, cloud_model:''`. The Cloud-acceleration card shows a prominent **"On"** badge (`SettingsPanel.tsx:495-497`) and the toggle is on, while the AI-model card correctly shows **"Local / Running"** (the backend honestly falls back). The two are internally consistent (the badge tracks the toggle; the AI card tracks the *effective* backend), and the fallback note explains it — but a glance at "Cloud acceleration · On" can read as "my prompts are going to the cloud now" when nothing is, because there's no key/model. Consider a third badge state ("On — needs a key") or demoting the badge to "Off" until a usable key+model exist, so the toggle's headline matches what's actually happening.

**Fix path.** Branch the badge: `cloud_enabled && has_cloud_key && cloud_model ? 'On' : cloud_enabled ? 'On — needs setup' : 'Off'`. **Test:** RTL assertion on the badge text across the three combinations.

---

### [UX-FULL-004] — Nit — Visual hierarchy — Realistic human-face avatar as the brand mark (carried from b4 UX-009)

`.kc-logo` / `.kc-ava` now render the new 64×64 `kim-avatar.png` (a photoreal-style face) as the top-left brand mark and the assistant-row avatar. This is the b4 watchlist item UX-009 (a deliberate design choice, not a defect). The file-size half of b4's concern (UX-004) is **resolved** (see What's working). Flagging only for continuity; no action required this gate.

---

## What's working (honest signal)

- **The whole b4 UX watchlist is genuinely closed — verified, not assumed:**
  - **UX-002 (Inspector tablist keyboard model)** — `RightPanel.tsx:679-689` now implements ArrowLeft/Right (wrapping), Home/End, and a roving tabindex (`tabIndex={tab===t.key?0:-1}`, line 725). The WAI-ARIA Tabs contract the b4 audit called out as the one broken custom widget is now honored.
  - **UX-003 (Settings section-nav `aria-current`)** — confirmed LIVE: with the nav rendered, exactly one link carried `aria-current="true"` ("Printer & material"), and each link points at its own card id; the IntersectionObserver marks a single in-view card (`SettingsPanel.tsx:112-134`). The dual-highlight + dead-anchor bug is gone.
  - **UX-004 (1.27 MB avatar)** — **resolved**: `kim-avatar.png` is now **64×64, 7,701 bytes** (was 1254×1254 / 1.27 MB), committed once in `frontend/src/assets/` and once in the served `src/kimcad/web/assets/` (both 7,701 B). Served correctly as `image/png` via `_serve_asset` (`webapp.py:1263-1278`, MIME map line 86) with a traversal guard.
  - **UX-006 (mobile nav loses group headings)** — confirmed LIVE at 375px: the four group headings ("Design defaults" / "AI" / "Output & tools" / "System") stay `display:block` full-width dividers in the wrapped pill row (`styles.css` `@media (max-width:860px)`); nav collapses to a single static column. Information scent preserved.
  - **UX-011 (Saved chip 44px touch target)** — `styles.css` adds `@media (pointer:coarse),(max-width:640px){ .kc-savestate-saved{min-height:44px} }`.
- **Warm/returning landing is clean and correctly silent.** Live snapshot: no first-run wizard (returning flag set), ModelHealthPill renders nothing when the model is healthy (the live region stays mounted for recovery announcements), all three on-ramps present (words + photo + sketch), examples/library link, 3-step strip, and a "What KimCad does" region. Console clean (no warns/errors).
- **Warm Settings is professional and honest.** AI model "Running / Local", action line "Running on your machine · Refresh" (ok tone), vision row "downloaded", CAD + Tools "Installed", live key-storage note correctly reads "secure credential store (Windows Credential Manager)" (keyring backend). Per-item section nav with status dots on AI model / Editable CAD / Tools.
- **Accessibility — color contrast passes WCAG AA in both themes (computed):** muted-on-surface 5.14:1 (light) / 7.02:1 (dark); `--kc-warn-text` 7.2:1; `--kc-warn` 5.1:1 (and ≥4.55:1 on its own tinted backgrounds); `--kc-fail` 5.59:1; pass-green 4.94–6.76:1; on-accent on the light primary button 5.03:1. The token comments' "non-text fills only" discipline is actually honored — `--kc-warn-accent` (2.47:1) is used only for dots/borders/fills, never as text.
- **Dialog & focus a11y is solid.** The keyboard-shortcuts dialog: `role=dialog`, `aria-modal=true`, labelled by its title, focus moved inside on open (verified live). The FirstRunWizard implements a real Tab focus-trap + Escape-to-skip + focus-on-mount (`FirstRunWizard.tsx:166-195`), and the cloud `<details>` summary has a `:focus-visible` ring.
- **Error / empty / partial states are designed throughout.** MyDesigns empty state ("Nothing saved yet" + CTA), filtered-empty ("No designs match"), per-card error + thumbnail-404 fallback tile + two-step delete; SendPanel's unconfigured-connector note, simulated-connection labeling, typed failed-send recovery with the download fallback; ConnectionsCard's failed-load retry; PhotoOnramp's reading/confirm/error phases with focus moves and abort-on-unmount; RightPanel's per-card "no part yet" / "last attempt didn't produce a model" states.
- **Honest copy under uncertainty** remains a strength: "Ready — words only" when vision is absent, the recap demotes to "Almost ready" with a re-check when the model is down, the experimental generator is framed as untrusted, and cloud is consistently disclosed as off-by-default with a privacy callout.

---

## Could not assess

- **Real screen-reader pass (NVDA/VoiceOver).** I verified ARIA roles/labels/live-region structure and focus management in source and via the live a11y tree, but did not run an actual AT session. The code's own comments (`ChatPanel.tsx:181-185`) note that fuller live-region scoping is deferred until a real AT session can measure it — that remains true and is the right next investment.
- **The `!running` Settings copy after a fix.** I forced the `!running` branch by intercepting the probe and confirmed the *current* (stale) rendered copy; I did not implement the fix, so the corrected re-entry is a recommendation, not a verified state.
- **Long-download wizard UX over a real multi-GB pull.** The Walkthrough lane verified the cold one-click setup *starts* and progresses (~14%); I did not sit through a full multi-GB managed-engine + model download to observe the late-stage and completion transitions in the wizard recap.
- **Direct-print SendPanel against real hardware.** No physical printer; the simulated/test-connection path and the disabled-unconfigured states were assessed, but a real `sent && !simulated` live-status follow was not exercised (that's the QA/Test role's REAL-tool re-exercise).
- **Touch interaction on a real device.** Responsive breakpoints and the 44px target rules were verified by computed layout at mobile width; no real touch device was used.
