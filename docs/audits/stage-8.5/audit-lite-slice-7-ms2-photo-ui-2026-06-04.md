# Audit Lite — Stage 8.5 Slice 7 MS-2 (photo on-ramp UI)
**Date:** 2026-06-04
**Scope:** The "describe with a photo" UI — `PhotoOnramp.tsx` (the idle→reading→confirm→error state machine) and its wiring into Landing + the workspace (ChatPanel/Workspace/App) + the Slice 7 styles + tests. MS-1 (the backend + `uploadPhoto`) is out of scope (already gated).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-three-small-fixes. The load-bearing parts are right: the UI frames the photo as a **rough, editable starting point** (scale disclaimer + "never left your machine" privacy line), it **never auto-submits** (a design starts only on an explicit "Use this as a starting point"), and every state offers a concrete next action. The full flow was verified live end-to-end on the running demo (affordance → reading → editable confirm card → real demo design in the workspace) with 44px touch targets at 375px and no overflow. Three Minor polish items: an object-URL leak on unmount, the confirm card's arrival not being announced / focus not moved for AT, and the workspace on-ramp silently replacing the current session.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 3
- Nit: 0

## Findings

### MS2-001 Minor: Preview object URL isn't revoked on unmount
**Dimension:** Correctness / Runtime
**Evidence:** `PhotoOnramp.tsx` creates a preview blob URL in `handleFile` (`setPreviewUrl(URL.createObjectURL(file))`) and revokes it only via `clearPreview()` on replace / `reset()` / `useSeed()`. There is no `useEffect` cleanup (the component imports `useRef, useState` only — no `useEffect`). If the component unmounts while a `previewUrl` is live — e.g. the user is on the **error** or **confirm** card and clicks New Design / My Designs / Settings (or, on Landing, submits via an example chip) without first clicking Cancel/Use — the blob URL is never revoked.
**Why it matters:** A small per-photo memory leak (the browser holds the blob until the document is discarded). No user-visible impact, but it accumulates across repeated photo attempts in a long session.
**Fix path:** Add `useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])` (revokes the prior URL on change and on unmount), and assert `URL.revokeObjectURL` is called on reset in the test.

### MS2-002 Minor: The confirm card's arrival isn't announced to assistive tech, and focus isn't moved to the editable seed
**Dimension:** UX (accessibility)
**Evidence:** The reading state carries `aria-live="polite"` on `.kc-photo-row`, but when the seed lands the whole reading region is **replaced** by the confirm card (a different subtree with no live region), so a screen-reader user is not told "the rough description is ready and editable." Focus also stays on the (now-removed) trigger; nothing moves focus to the `.kc-photo-seed` textarea.
**Why it matters:** An AT user who triggered the read gets silence at the moment the result appears, and has to hunt for the new editable field. It also costs sighted users a click — the seed is meant to be edited immediately.
**Fix path:** When entering `confirm`, focus the seed textarea (a `ref` + `useEffect` on phase), which both announces the field to AT and lets a sighted user edit right away. Optionally keep a stable `role="status"` line so the transition is spoken.

### MS2-003 Minor: In the workspace, "Use this as a starting point" silently replaces the current design
**Dimension:** UX
**Evidence:** `App.tsx` wires `onPhotoSeed={handleSubmit}`; `handleSubmit` (App.tsx) resets the thread, versions, and result and starts a brand-new design. In the workspace the affordance therefore **discards the in-progress conversation/part** when the seed is used, with no cue that it starts over. (Prior work is auto-saved to My Designs, so nothing is lost — but the label doesn't signal a restart.)
**Why it matters:** A user mid-refine who reaches for a photo "to add context" may be surprised when their current part is swapped for a new one. The action is deliberate (open card → pick → edit → confirm) and recoverable (auto-saved), so it's not data loss — but the surprise is real and avoidable.
**Fix path:** In the `variant="workspace"` card, add a subtle cue (e.g. a one-line "This starts a new part from the photo." under the actions, or relabel to "Start a new part from this"). Cheap, removes the surprise, and stays faithful to the approved "photo = a starting point" design.

## What's working
- **Honest framing (trust rule 5) is solid.** The confirm card titles the result "A rough starting point," shows "Read locally — your photo never left your machine," and carries the explicit scale disclaimer: *"A photo can't tell us scale, so any sizes are estimates. Adjust anything, then continue."* The seed is a normal editable `<textarea>` — no "photo → finished part" promise anywhere, and the delivered geometry stays KimCad's deterministic output. This is the most important property of the slice and it's clean. (Verified live: note text + editable seed present.)
- **Never auto-submits.** `onSeed` fires only inside `useSeed()` (the "Use this as a starting point" click), which trims first and resets after. Reading a photo never starts a design — there's a dedicated test (`never auto-submits — onSeed is NOT called from merely reading a photo`) and it's non-vacuous. Verified live: the demo design started only on the explicit click, with the seed becoming the user turn verbatim.
- **No dead-ends.** idle → a clear affordance; reading → honest "Reading your photo…" + privacy line (aria-live); confirm → Use / Use a different photo / Cancel; error → the friendly message + "Try another photo" / Cancel. A blank seed is treated as a failure, not a silent success (own branch + backend 422 both covered).
- **Touch + responsive (live-verified).** At 375px the affordance and all three action buttons and Cancel are exactly 44px; the card sits within the viewport with 0 horizontal overflow. At desktop the affordance is correctly secondary — dashed border, muted ink — 14px below the input card and 18px above the examples, no overlap.
- **Correctness details done right.** The file input resets `e.target.value` so re-picking the same file re-fires; `disabled` (busy) gates `openPicker`, `onDrop`, `handleFile`, the textarea, and `useSeed`; drag-drop and click share one `handleFile`; the workspace refine row was made `flex-wrap` so the affordance lands on its own line (verified — workspace affordance renders and the flow works).
- **Tests are non-vacuous and cover the states**: affordance shown, reading→confirm with the seed + scale note, never-auto-submit, edited-seed→onSeed, blank-seed→error, upload-error message, Cancel→idle, disabled. 157 frontend tests pass; build (tsc+vite) clean.

## Watch items
- **Long reading state:** real local vision on CPU can take ~15–20s; today it's a spinner + text (honest, but static). The design explicitly defers the no-frozen-spinner treatment to Slice 9 — fine for now, but worth the Slice 9 polish so a 20s read doesn't read as a hang.
- **Drag-drop path is untested:** `onDrop` shares `handleFile` with the (tested) file-input path, so risk is low, but a direct drop test would close the gap.
- **Demo thumbnail uses `alt=""`** (decorative, since the seed text conveys content) — defensible; revisit if a future a11y pass wants a described preview.

## Escalation recommendation
No escalation needed. Three Minor, UX-polish findings on a small, well-contained UI diff whose load-bearing honesty + never-auto-submit properties are correct and live-verified. The full 5-role `audit-team` runs at the Slice 7 slice-end as planned (with the runtime wiring-audit) — that's the right place for the deeper pass, not a mid-slice escalation.
