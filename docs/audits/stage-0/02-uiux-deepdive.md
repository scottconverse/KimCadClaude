# UI/UX Deep-Dive — KimCad (Phase-2 web UI, first slice)

**Audit date:** 2026-05-29
**Role:** Senior UI/UX Designer
**Scope audited:** The single-page local web app — `src/kimcad/web/index.html` (markup, CSS, client JS) and its server `src/kimcad/webapp.py` (response shaping, state values, error/404 paths). One route (`/`), one core flow (describe a part → design plan + printability verdict + dims + 3D preview).
**Auditor posture:** Balanced
**Method note:** This is a **static review**. I read the rendered markup and CSS and traced the client JS state machine and the server payload shape by hand, and computed WCAG contrast ratios numerically from the declared hex values. I did **not** run a live browser, drive a real pipeline run, or capture screenshots — no live-assembled run was performed here. Findings about runtime behavior (spinner duration, WebGL render, focus ring appearance) are inferred from code and flagged as such.

---

## TL;DR

This is a genuinely well-built first slice for a developer tool: one clear input, an honest verdict, a dimensions table, and a 3D preview that degrades gracefully. The code is XSS-safe and the "no fake G-code" honesty is exactly right. The weakest dimension is **state coverage and the long-wait experience**: the model call takes *minutes* and the only feedback is a single static line plus a 16px spinner, with no progress, no elapsed time, no cancel, and no timeout — a user cannot tell a slow run from a hung one, which is the single most important UX gap to close. Accessibility is mostly thoughtful (real labels, semantic table, `escapeHtml`) but has three concrete misses: the primary CTA fails AA contrast (3.22:1 white-on-blue), the clarification answer field has no label, and dynamic state changes (result appears, error appears, spinner toggles) are silent to screen readers with no live region or focus move. The offline 3D-preview gap (three.js from CDN) and the disabled G-code stub are both correctly handled in code but each needs one line of clearer copy.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 4 |
| Minor | 6 |
| Nit | 3 |
| **Total** | **14** |

*(One prior-audit item — the missing clarification-answer label — was re-checked and found already fixed in this revision; it is recorded under UX-004 as resolved and is **not** counted above.)*

## What's working

- **Honest verdict surface, not a marketing screen.** The result card leads with the part title, a pass/warn/fail badge, a headline, and a target-vs-actual dimensions table with per-axis ✓/✗. This is the right shape for an engineering tool — it tells the truth about whether the part is printable rather than just declaring success. (`#result` card, `renderDims`, `#gateBadge`.)
- **Graceful 3D degradation is designed, not accidental.** `showModel` checks for `THREE`/`STLLoader` before touching WebGL, wraps the whole render in try/catch, and routes every failure path (loader missing, load error, exception) to `viewerFallback` with a human message. The preview literally cannot take down the report. (`index.html:184–229`.)
- **The G-code stub tells the truth.** The disabled "Prepare print (G-code)" button is paired with copy explaining *why* it's disabled and that the validated model is ready now. Disabling a control without explanation is a common UX sin; this avoids it. (`index.html:92–95`.) See UX-009 for one copy tightening.
- **XSS-safe by construction.** Plan/summary/headline/clarification all go through `textContent`; findings messages go through an `escapeHtml` helper; only trusted server-shaped numeric/string fields reach `innerHTML`. A user pasting `<script>` into the prompt cannot break the page.
- **Restrained, coherent dark theme.** A single CSS custom-property palette, semantic colors (`--ok`/`--warn`/`--fail`), `tabular-nums` on the dimensions table so numbers align, and `system-ui` font stack. Body and panel text contrast is excellent (14–16:1). This is a tasteful, consistent system — the contrast problems are isolated to two specific spots, not the palette as a whole.
- **The empty/initial state is welcoming.** The prompt textarea ships with a concrete, well-chosen placeholder example (a wall hook with real dimensions) that doubles as documentation of what a good prompt looks like. (`index.html:59`.)

## What couldn't be assessed

- **Live long-wait behavior.** I could not time a real CPU model run, so claims about the spinner experience over minutes are inferred from the code (a static label + CSS spinner, no timer, no progress events). The *absence* of progress/cancel/timeout in the code is verified; the felt experience is inferred.
- **Live 3D render.** The WebGL path was read statically. I did not confirm a real STL renders, that OrbitControls feels right, or that the camera framing is correct on varied geometry.
- **Real responsive rendering.** No browser at 320/768/1440px. Responsive findings below are read from the CSS (fixed `max-width: 1040px`, `.row` is `display:flex` with no wrap, fixed-height viewer) and are flagged as inferred.
- **Focus-ring appearance.** Whether the browser default focus outline is visible against this dark theme was not screenshotted; the code neither adds nor removes `:focus-visible` styling, so it relies on UA defaults (see UX-006).

---

## First impressions

A first-time user lands on a calm, dark, single-column page: a title bar reading **KimCad — describe a part → printable model**, then one card with a labeled textarea and a blue **Design it** button. Within five seconds you know exactly what to do, and the placeholder shows you *how* to describe a part. This is a strong, low-friction entry — no nav to parse, no chrome, one obvious action. The friendly tone of the tagline matches the input label. Nothing feels adversarial.

The first worry surfaces only when you imagine clicking **Design it**: the status line will say "Designing… this can take a few minutes on CPU" next to a small spinner, and then — for minutes — nothing else changes. That gap between "I clicked" and "something happened" is where this otherwise-tidy UI is thinnest.

## Journey walkthroughs

### Journey: Describe a part → printable verdict (the one core flow)

1. **Arrive / idle** — Prompt card visible, button enabled, status empty. Clean. (Good.)
2. **Submit** — `#go` click trims the prompt; if non-empty, `design()` runs. If the textarea is empty, **nothing happens at all** — no inline hint, no shake, no focus. The button looks live but silently no-ops. (UX-003.)
3. **Loading** — Button disables, status shows spinner + "Designing… this can take a few minutes on CPU." For a real backend this state persists for *minutes* with zero further feedback, no elapsed timer, no cancel, no timeout. (UX-001, the Critical.)
4. **Branch A — clarification** — Server returns `clarification_needed`; the clarify card appears with the question and an answer textarea. The answer field has no label (UX-004), and the card's appearance is silent to assistive tech (UX-002). On continue, the original prompt + answer is re-sent — and the loading status reappears, but the previously-shown clarify card is hidden, so a screen-reader user gets no announcement that the page advanced.
5. **Branch B — result (completed or gate_failed)** — Result card appears: title, badge, headline, dims table, findings list, 3D viewer. This is the payoff and it's well-composed. But it appears below the fold-ish content with no scroll-to and no focus move, so on a tall result a user may not realize new content rendered above where they were looking (UX-002).
6. **Branch C — render_failed / error** — Error card shows "Couldn't build that" + a message. Good human heading. The message itself can be a raw exception string on a 500 (`TypeError: ...`), which is fine for this dev tool but unfriendly if ever shown to a non-developer (UX-008).
7. **Return / retry** — There is no "start over" affordance; the user edits the same textarea and clicks again. Acceptable for a single-shot tool, but the clarify card and prior result/error are hidden on the next run, which is the right reset.

**Journey-level gap:** the flow has no concept of *time* or *cancellation*. For a tool whose headline cost is a multi-minute CPU call, that's the defining UX risk, not a pixel issue. Everything else is polish on top of a sound skeleton.

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion

### [UX-001] — Critical — State / Journey — The multi-minute wait has no progress, elapsed time, cancel, or timeout

**Evidence**
`index.html:111–127` (`design`) and `:232–235` (`setStatus`). On submit the only feedback is `<span class="spinner"></span> Designing… this can take a few minutes on CPU.` The `fetch` has **no timeout** (no `AbortController`), no cancel control, no progress, and no elapsed-time counter. The server (`webapp.py do_POST`) runs `design_response` → `pipeline.run` synchronously and only responds when the whole CPU-bound model + render + gate completes. The status string itself admits the wait is "a few minutes."

**Why this matters**
This is the product's signature interaction and its longest. A static label plus a 16px spinner for *minutes* is indistinguishable from a hung page. Users will reasonably conclude it froze, click again (no double-submit guard beyond the button disable, which they may not notice), reload (losing the in-flight run), or quit. There is no way to abandon a run that's taking too long, and if the model genuinely hangs there's no client-side timeout to surface "this is taking unusually long — the model may be stuck." For a local CPU tool where minutes is *normal*, the UI must make a long-but-healthy wait feel different from a dead one.

**Blast radius**
- Adjacent code: `setStatus` (single status surface, reused for both the initial and the clarify-answer submit), `design()` fetch. A fix is localized to these.
- Shared state: none; this is presentation only. No payload-shape change required for a basic elapsed timer + cancel.
- User-facing: every real (non-`--demo`) run passes through this state. Demo mode returns in <1s and won't exhibit the pain, which means the gap is easy to miss in demos — note for QA.
- Migration: none. A streaming/progress version would later want server-sent events or polling, but the first fix (elapsed timer + `AbortController` cancel + soft timeout message) needs no server change.
- Tests to update: none exist for client behavior; this is also a test gap (cross-ref the test-engineering role).

**Fix path**
Three additive changes, no backend work:
1. **Elapsed timer.** Start a `setInterval` on submit and update the status to e.g. `Designing… 0:42 elapsed. CPU runs take a few minutes — this is normal.` so the user sees the page is alive.
2. **Cancel.** Wire an `AbortController` into the fetch and add a "Cancel" secondary button next to the spinner; on abort, restore idle and show "Cancelled — edit your prompt and try again."
3. **Soft timeout.** After a threshold (say 5 min), change the copy to `Still working — this is longer than usual. The model may be heavily loaded; you can keep waiting or cancel.` rather than silently spinning forever.
Suggested copy for the steady state: replace "Designing… this can take a few minutes on CPU." with **"Designing your part… {m:ss} elapsed. This runs locally on CPU and usually takes a few minutes."**

---

### [UX-002] — Major — Accessibility — Dynamic state changes are silent and steal no focus (no live region, no focus move)

**Evidence**
`render()` / `show()` / `hide()` (`index.html:129–156, 236–238`) toggle a `.hidden` class on `#clarify`, `#result`, `#error`. `showError` (`:238`) sets text and reveals `#error`. `setStatus` (`:232–235`) swaps the status line. **None** of these surfaces is an ARIA live region (`aria-live`/`role="status"`/`role="alert"`), and focus is never moved to the newly revealed card. The spinner/status `#status` is a plain `<span class="muted">`.

**Why this matters**
A screen-reader user submits, hears nothing while "Designing…" appears, hears nothing when (minutes later) the result, clarification, or error card appears, and is left at the submit button with no indication the page changed. The most important moments in the flow — "your part is ready," "I need one more detail," "that failed" — are inaudible. Sighted keyboard users have a milder version: the result can render below their viewport with no scroll or focus cue. This turns a usable-looking page into one that excludes assistive-tech users from the core flow.

**Blast radius**
- Adjacent code: `#status` (loading announcements), `#error` (failure announcements), `#clarify`/`#result` reveals, `#clarifyQ` text. One shared pattern, four surfaces — fix once, apply across.
- User-facing: every assistive-tech user on every run; also benefits sighted users via a scroll-into-view on result.
- Tests to update: none exist; add to the a11y checklist.
- Related findings: UX-004 (label), UX-006 (focus visibility) — same accessibility root.

**Fix path**
- Make `#status` a polite live region: `role="status" aria-live="polite"` (it already updates in place — this alone announces "Designing…" and clears).
- Make `#error` an assertive region: `role="alert"` so failures interrupt.
- On `show("result")` and `show("clarify")`, move focus to the card heading (`tabindex="-1"` + `.focus()`) and `scrollIntoView({block:"start"})`. For clarify, focus the `#answer` field directly so the user can type immediately.

---

### [UX-003] — Major — State / Copy — Submitting an empty prompt silently does nothing

**Evidence**
`index.html:241–244`: `$("go")` handler reads `.value.trim()`; if falsy it simply doesn't call `design()`. No message, no focus, no visual change. Same for `#goAnswer` (`:245–248`) on an empty answer. The server *does* return a friendly 400 ("Please describe the part you want.") — but the client never lets an empty prompt reach the server, so that good message is dead code from the UI's perspective.

**Why this matters**
A live-looking primary button that does nothing on click is a trust break — the user can't tell if the app is broken, if their text didn't register, or if they did something wrong. Empty-submit is an extremely common real path (clicked too early, cleared the field, hit the button by habit). Silent no-op is the worst of the options.

**Blast radius**
- Adjacent code: both submit handlers (`#go`, `#goAnswer`) share this shape.
- User-facing: anyone who clicks before typing — early in every first session.
- Tests to update: none; add an empty-submit assertion when client tests exist.
- Related findings: UX-002 (the hint should also be announced to AT).

**Fix path**
On empty submit, focus the field and show an inline hint rather than no-op. Reuse the status line: `setStatus(false, "")` then set `#status` to **"Add a short description first — e.g. a 60 mm wall hook with two screw holes."** and `$("prompt").focus()`. Keep it inline (don't disable the button preemptively — that hides the problem).

---

### [UX-004] — Resolved (not counted) — Accessibility — Clarification answer field label: verified present

**Evidence**
The prior audit-lite (FINDING-003) flagged a missing label on the clarification answer field. Re-checked in this revision: `index.html:69` has `<label for="answer" class="muted">Your answer:</label>` immediately before `<textarea id="answer">` (`:70`), and `#prompt` (`:58`) likewise has a matching label. Both inputs are properly associated.

**Status**
Resolved — retained in the audit trail so the prior finding shows as checked and closed. Excluded from the open roll-up. The remaining accessibility gaps are UX-002 (no live regions / focus move), UX-005 (button contrast), and UX-006 (no focus ring) — not a missing label.

---

### [UX-005] — Major — Accessibility — Primary CTA fails WCAG AA contrast (white on `--accent`)

**Evidence**
CSS `:27–30`: buttons are `color:#fff` on `background: var(--accent)` = `#4f8cff`. Computed contrast ratio: **3.22:1**. WCAG 2.1 AA for normal-weight text (the button text is `font-weight:600`, ~15px — below the 18.66px/14pt-bold large-text threshold) requires **4.5:1**. This affects the **primary** "Design it" CTA and the "Continue" button, the two most important controls on the page.

**Why this matters**
The single most-clicked, highest-importance control on the page doesn't meet the minimum legibility bar. Low-vision users and anyone on a glary screen will strain to read the label. It's also the kind of finding that fails an automated a11y gate (axe/Lighthouse) outright, which matters for a Stage-0 sign-off.

**Blast radius**
- Adjacent code: the base `button` rule — fixing the token or the text color updates **all** primary buttons at once (Design it, Continue, and any future ones). The `.secondary` button (`#2a2f3a` bg, white text) computes ~9:1 and is fine.
- Shared state: `--accent` (`#4f8cff`) is also used for spinner border-top, the mesh material color, and the dims/findings accents — do **not** darken the token globally or you shift the whole accent identity. Fix at the button rule, not the token.
- User-facing: every user reads these buttons; low-vision users most affected.
- Migration: none — pure CSS.
- Tests to update: none; would be caught by an added automated contrast check.

**Fix path**
Two clean options:
1. Darken the *button* background only (keep the `--accent` token for accents): a blue around `#2f6fe0`/`#2563eb` with white text reaches ≥4.5:1 while staying on-brand. Recommend this.
2. Keep `#4f8cff` and use a dark text color (`#0f1115`) — computes ~6.5:1 and reads well, but dark-on-bright-blue reads less like a primary CTA in a dark UI. Option 1 is the better fit.

---

### [UX-006] — Major — Accessibility — No explicit focus-visible styling on the dark theme; relies on UA default

**Evidence**
The stylesheet defines `button:disabled` and `button.secondary` but **no** `:focus`/`:focus-visible` rule for buttons, the textareas, or any interactive element. Focus indication is left entirely to the browser default outline, which on a `#0f1115`/`#181b22` dark background is often a thin dark or low-contrast ring (and on some `WebGLRenderer` canvas / `OrbitControls` interactions, focus can land on the canvas with no visible cue).

**Why this matters**
Keyboard users need to see where focus is. A custom dark theme that doesn't define its own focus ring is gambling on the UA default being visible against its specific dark panels — frequently it isn't, especially the textarea's. Invisible focus on the primary controls is a real keyboard-navigation barrier (and, like UX-005, an automated-gate failure).

**Blast radius**
- Adjacent code: all interactive elements — `button`, `textarea#prompt`, `textarea#answer`, and the canvas. One shared `:focus-visible` rule covers them.
- User-facing: all keyboard users.
- Migration: none — pure CSS.
- Related findings: UX-002, UX-005 (same a11y root; can ship together).

**Fix path**
Add a high-contrast focus ring using an existing token, e.g.
`:where(button, textarea, [tabindex]):focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }`
and verify it's visible on both `--bg` and `--panel`. Pair with the focus-move from UX-002 so the moved focus is also *seen*.

---

### [UX-007] — Minor — State / Copy — Offline 3D-preview gap is handled but the fallback copy hides the real cause

**Evidence**
`index.html:104–106` loads three.js, STLLoader, and OrbitControls from `cdn.jsdelivr.net`. Offline (or CDN blocked), `THREE` is undefined and `showModel` (`:186–189`) shows: **"3D preview unavailable (viewer failed to load). The model is still saved."** This cuts against the project's local-first posture (the rest of the stack — pipeline, render, gate — runs entirely offline; only the preview needs the network). The prior audit-lite already logged the CDN dependency as a watch item; this finding is the *UX copy* angle, not the architecture.

**Why this matters**
A user running this local-first tool offline gets a vague "viewer failed to load" with no hint that *the internet* is the missing ingredient or that everything else worked. They may think the whole run failed. The honest, actionable message is that the 3D *preview* specifically needs a network for now.

**Blast radius**
- Adjacent code: `viewerFallback` messages (`:188`, `:214`, `:217`); the CDN `<script>` tags. Vendoring three.js locally (the real fix) is an architecture task tracked elsewhere — this finding is only the interim copy.
- User-facing: offline users, which for a local-first tool may be common.
- Migration: vendoring would remove the network dependency entirely; until then, copy.

**Fix path**
Until three.js is vendored locally, make the fallback name the cause: **"3D preview needs an internet connection the first time (the viewer loads from a CDN). Your validated model was created and saved — only the live preview is unavailable."** Recommend vendoring three.js into `web/` in a later slice (architecture role owns that); this is the stopgap.

---

### [UX-008] — Minor — Copy — Error card can surface a raw exception string

**Evidence**
`webapp.py:192–193` returns `{"error": f"{type(e).__name__}: {e}"}` on an unexpected 500; the client (`render`/`showError`) drops that straight into `#errorMsg` under the "Couldn't build that" heading. So a user can see e.g. `KeyError: 'bounding_box_mm'`. The prior audit-lite (FINDING-005) judged this acceptable *for a dev tool* — I agree for the developer audience, hence Minor not Major.

**Why this matters**
For the current single-developer, localhost audience, a raw exception is arguably *more* useful than a sanitized message (there's no server log — `log_message` is silenced). But the heading "Couldn't build that" sets a friendly register that a bare `TypeError:` then breaks, and if this UI ever faces a non-developer the technical string is noise.

**Blast radius**
- Adjacent code: the 500 path in `do_POST`; `showError`.
- User-facing: only on unexpected server errors (rare path).

**Fix path**
Keep the raw detail (it's useful here) but frame it: heading stays "Couldn't build that," then a plain lead line **"Something went wrong while building your part. The details below can help debug it:"** followed by the exception in a `.muted` monospace block. Gives the developer the trace and the friendlier register at once. (No change needed if the audience stays strictly you.)

---

### [UX-009] — Minor — Copy — G-code stub copy is slightly buried / passive

**Evidence**
`index.html:92–95`: a disabled "Prepare print (G-code)" button (`title="Coming in the next slice"`) beside the note "G-code is generated only on explicit confirmation — wired in the next slice. The validated 3D model is ready now." The honesty here is excellent (credited above); the nit is that the most reassuring part ("your model is ready now") comes last and the sentence leads with internal-roadmap framing ("wired in the next slice").

**Why this matters**
The user's question at this point is "did it work and what do I have?" Lead with the reassurance, then the limitation. "Next slice" is developer language leaking into user copy.

**Fix path**
Reorder and de-jargon: **"Your validated 3D model is ready. Generating G-code is a separate, confirmed step — coming soon."** Keep the button disabled with `title="Coming soon"`.

---

### [UX-010] — Minor — Responsive — Layout reads from CSS as desktop-only; `.row` doesn't wrap, viewer height is fixed (inferred)

**Evidence**
`main { max-width:1040px }` centers content but there is no mobile-specific rule, no `@media` query anywhere. `.row { display:flex; gap:12px }` with **no** `flex-wrap` (`:26`): the result card's bottom row is the disabled button + a sentence of note text, which at ~320px will either overflow or squeeze. `#viewer { height:340px }` is fixed regardless of width. The dims `table` is full-width but has four numeric columns that will get tight on a phone. *(Inferred from CSS; not rendered at narrow widths.)*

**Why this matters**
A local dev tool is likely opened on a laptop, so this is Minor — but "describe a part on your phone" is a plausible casual use, and an overflowing button row / horizontally-scrolling table is a visibly broken state.

**Blast radius**
- Adjacent code: `.row` (used in three places: prompt submit, clarify submit, result footer), `#viewer`, `table`.
- User-facing: narrow-viewport users only.

**Fix path**
Add `flex-wrap: wrap` to `.row`; give `#viewer` a responsive height (e.g. `min(340px, 56vw)` floor ~220px); allow the dims table to scroll within a wrapper (`overflow-x:auto`) rather than the page. One small `@media (max-width: 640px)` block covers it. Verify at 320/768px.

---

### [UX-011] — Minor — State — Dims table and findings list have no explicit empty sub-states within a result

**Evidence**
`renderDims` (`:158–169`) hides the table when `dims` is empty — good. But `renderFindings` (`:171–179`) on an empty `findings` array renders an **empty `<ul>`** with no "no issues found" affirmation. A clean pass (gate ok, no findings) shows the badge but a blank space where findings would be.

**Why this matters**
A clean result is the *best* outcome and currently looks like missing content. An explicit "No printability issues found" is a small confidence win and avoids "did the findings fail to load?"

**Fix path**
In `renderFindings`, when `findings.length === 0` and the gate passed, render a single muted line: **"No printability issues found."** (Suppress it only if the gate failed, where a dims-mismatch is the implied finding.)

---

### [UX-012] — Minor — Accessibility / Motion — Spinner animation ignores `prefers-reduced-motion`

**Evidence**
`:49–50` the `.spinner` uses an infinite `spin .8s linear` animation; there is no `@media (prefers-reduced-motion: reduce)` rule anywhere. The OrbitControls auto-`update` loop also runs continuously (`animate`, `:220–224`).

**Why this matters**
Users who set reduced-motion (vestibular sensitivity) still get a perpetually spinning indicator for *minutes* during the core flow. Low harm (a small spinner) but it's the easy, expected accommodation and the wait is unusually long here.

**Fix path**
Add `@media (prefers-reduced-motion: reduce) { .spinner { animation: none; } }` and instead show static text (the elapsed timer from UX-001 already serves as motion-free progress). Leave the 3D controls as-is (user-driven, not auto-playing).

---

### [UX-013] — Nit — Copy — Title bar uses a HTML entity arrow; fine, but verb tense drifts

**Evidence**
Header tagline (`:55`) "describe a part → printable model" (lowercase, imperative-ish) vs input label (`:58`) "Describe the part you want to print:" (sentence case). Minor voice drift between the two adjacent strings.

**Fix path**
Harmonize to sentence case in both, or keep the lowercase tagline as a deliberate stylistic flourish. Nit-level; flag once.

---

### [UX-014] — Nit — Visual hierarchy — Badge "—" placeholder for unknown gate status reads as a typo

**Evidence**
`render` (`:146–149`): when `gate_status` is empty/unknown the badge text becomes `"—"` with class `badge warn`. An em-dash in a status pill can read as a rendering glitch rather than "unknown."

**Fix path**
Use a word: `"unknown"` or `"n/a"` in the badge for the indeterminate case. Nit.

---

### [UX-015] — Nit — Pattern — Status line is the only output channel for both progress and validation hints

**Evidence**
`#status` carries the loading spinner text and (per UX-003's fix) would also carry the empty-submit hint. Overloading one span for "busy" and "you made an input error" is a mild pattern smell.

**Fix path**
Acceptable for a one-card tool; if input validation grows, give errors their own inline slot near the field rather than the shared status line. Nit / future.

---

## States audit matrix

| Component / page | Default | Loading | Empty (no data) | Success populated | Error | Partial | Notes |
|---|---|---|---|---|---|---|---|
| Prompt card | ✓ | ✓ (spinner) | ✓ (placeholder) | — | — | — | Empty-submit no-ops (UX-003); spinner has no progress/cancel/timeout (UX-001) |
| Clarification card | ✓ | ✓ (shared) | n/a | ✓ | — | — | Appears silently to AT (UX-002); label present (UX-004 resolved) |
| Result card | n/a | n/a | partial | ✓ | — | ✓ | Findings empty-state blank (UX-011); no focus/scroll on reveal (UX-002) |
| Dims table | n/a | n/a | ✓ (hidden when empty) | ✓ | — | ✓ | Clean handling |
| 3D viewer | ✓ (placeholder box) | — | ✓ (fallback msg) | ✓ (inferred) | ✓ (fallback) | — | Graceful degradation is a strength; offline copy vague (UX-007) |
| Error card | n/a | n/a | n/a | n/a | ✓ | — | Good heading; raw exception possible (UX-008); no `role=alert` (UX-002) |

State coverage is strong overall — the gaps are *quality* of a few states (empty findings, offline copy, the loading state's lack of progress), not missing states. No blank screens.

*(UX-004 in the matrix above refers to the clarification-answer label, which is present/resolved — not an open finding.)*

## Accessibility snapshot

- **Keyboard navigation:** Reachable — native `<button>` and `<textarea>` are all keyboard-operable; tab order follows DOM order and is logical. No keyboard traps. The 3D canvas is mouse-oriented (OrbitControls) with no keyboard equivalent, acceptable for a preview.
- **Focus visibility:** **At risk** — no custom `:focus-visible`; relies on UA default against a dark theme (UX-006).
- **Color contrast:** Body/panel text excellent (14–16:1); `--muted` is fine (6.7–7.35:1, passes AA). **Primary button fails: 3.22:1** white-on-`#4f8cff` (UX-005). Semantic ok/warn/fail text all pass on panel (≥5:1).
- **Screen reader labeling:** Inputs are properly labeled (`#prompt`, `#answer`). **But** state transitions, loading, and errors are not announced — no live regions, no focus move (UX-002). This is the main a11y gap.
- **Reduced motion:** Not respected — spinner animates regardless (UX-012).
- **Touch target size:** Buttons ~36–40px tall (`padding:10px 18px`), close to but possibly under the 44px guideline on touch; minor given the desktop-first audience.

## Patterns and systemic observations

- **One root, three a11y findings.** UX-002 (no live regions / focus move), UX-005 (button contrast), and UX-006 (no focus ring) all stem from a theme/JS that was built visually-first without an accessibility pass. They should be fixed as one coordinated a11y sweep — together they're the difference between "looks accessible" and "is accessible," and together they'd clear an automated gate.
- **The wait is the product's defining UX surface.** UX-001 is the highest-leverage single fix: the multi-minute synchronous run with a static spinner is the one place a sound-looking tool can feel broken. An elapsed timer + cancel + soft-timeout copy transforms the felt experience with no backend change.
- **Honesty is a through-line strength.** The G-code stub, the gate verdict, and the 3D fallback all tell the truth rather than faking success. That's a real cultural asset in the UI; the copy findings (UX-007/008/009) just tighten *how* it tells the truth.

## Appendix: surfaces reviewed

- Route: `GET /` (the single page), `POST /api/design`, `GET /api/mesh/<id>` — read statically.
- Files: `src/kimcad/web/index.html` (full: markup, CSS `:7–52`, client JS `:107–249`); `src/kimcad/webapp.py` (full: response shaping, state values, handler, error/404 paths); cross-checked `src/kimcad/cli.py:24,63–70,152–173` for the `web`/`--demo`/`--host` surface.
- Viewports: none rendered (static review); responsive findings inferred from CSS.
- Contrast: ratios computed numerically from declared hex values (WCAG 2.1 relative-luminance formula).
- Not run: live browser, real pipeline run, WebGL render, screenshots, automated a11y scan.

Open findings: **1 Critical, 4 Major, 6 Minor, 3 Nit = 14**, plus one prior item (UX-004) re-verified as already resolved.
