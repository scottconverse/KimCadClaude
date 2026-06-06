# Audit Lite — Escape-paths MS-1: design cancel + honest long-run feedback
**Date:** 2026-06-04
**Scope:** The "Designing your part…" screen now has an escape — a Cancel that aborts the in-flight design + honest "runs on your computer's AI, can take a few minutes" copy + a live elapsed timer (api.ts, App.tsx, Workspace.tsx, Viewport.tsx, ChatPanel.tsx, styles.css + tests). First instance of the load-bearing rule "every action must have an escape."
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-one-fix. The escape genuinely works (live-verified: Cancel is clickable, aborts the request, returns to the prompt; timer ticks; honest copy), and there's no timer leak and no same-run stale-apply (abort rejects the promise, so the success path is skipped). The one real gap is *cross-run*: escaping via "New Design" (or starting another design) while one is in flight doesn't abort the prior request and there's no design seq-guard, so a late resolve can inject a stale result into the fresh session — a zombie-request edge that's squarely in the escape rule's spirit. Plus two Nits (an order-dependent CSS override on the load-bearing Cancel, and an invisible cancel message on a first-design cancel).

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 2

## Findings

### ESC-MS1-001 Minor: "New Design" / a new submit during an in-flight design doesn't abort the prior request → a late resolve injects a stale result
**Dimension:** Correctness
**Evidence:** `App.tsx:189-190` — `runDesign` creates a new `AbortController` and overwrites `designAbortRef.current` **without aborting the previous one**. The success path (`App.tsx:198-219` `setMessages`/`setVersions`/`applyResult`) has **no design seq-guard**. `handleNewDesign` (`App.tsx:298-311`) resets the thread + `setBusy(false)` but **never aborts** the in-flight controller. So: start design A (slow local model) → click **New Design** (escape) → start design B → when A finally resolves, A's `runDesign` success path runs against the *new* session, appending a stale assistant message and a stale version/result. `runDesign` cancels-by-reject for the *same* run (the awaited promise throws on abort, skipping the success path), but nothing supersedes a *prior* run's late resolve.
**Why it matters:** The escape (New Design) leaves a zombie request that can corrupt the fresh session — a confusing "a part I didn't ask for just appeared" bug. With the local model being slow (the exact situation that motivated the escape), the timing window is wide, not theoretical. No data loss (designs persist separately), so Minor — but it undercuts the very "clean escape" this change is about.
**Fix path:** Add a `designSeqRef` stamped at the top of `runDesign` (`const seq = ++designSeqRef.current`) and guard the success + catch + finally bodies with `if (seq !== designSeqRef.current) return`. Abort the prior controller at the start of `runDesign` (`designAbortRef.current?.abort()` before creating the new one) and in `handleNewDesign` (abort + bump `designSeqRef`). Mirror of the existing `renderSeq` guard on `handleRerender` (`App.tsx:271`, 277, 316, 320) — same pattern, applied to the design path.

### ESC-MS1-002 Nit: the load-bearing `pointer-events:auto` on the busy overlay wins only by source order
**Dimension:** UX (CSS robustness)
**Evidence:** `styles.css` — `.kc-viewport-overlay { pointer-events: none }` and `.kc-viewport-busy { pointer-events: auto }` are equal specificity (one class each); the override wins purely because `.kc-viewport-busy` is defined later. The element carries both classes. It works today (live-verified `pointerEvents: auto`, Cancel clickable), but a future CSS reorder/merge could silently flip Cancel back to unclickable — re-trapping the user, the exact failure this rule forbids.
**Fix path:** Make it order-independent: scope the busy rule to `.kc-viewport-overlay.kc-viewport-busy` (specificity 0,0,2,0 — always beats the base regardless of order).

### ESC-MS1-003 Nit: a first-design cancel pushes a "Cancelled — back to you." message that's never seen
**Dimension:** UX
**Evidence:** `App.tsx:221-223` — on abort, `runDesign` always appends a "Cancelled — back to you." assistant message. On a *first*-design cancel `result` is null, so `onWorkspace` becomes false and the app returns to the **landing** — where the thread (and that message) isn't rendered. It's a harmless dangling state entry (reset by the next submit), but the message is wasted there. On a *refine* cancel it's correct and visible.
**Fix path:** Only push the cancel message when the user stays in the workspace: `if (resultRef.current) setMessages(...)`. Refine-cancel still shows the confirmation; first-design-cancel returns silently to the landing.

## What's working
- **The escape genuinely works (live-verified).** On the running app with a delayed `/api/design`: the busy overlay shows the title, the honest "runs on your computer's AI — a few minutes… Nothing leaves your machine" line, a ticking `0:14 → 0:15` elapsed timer, and a Cancel that is clickable (`pointer-events: auto`), aborts the request (`AbortError`), and drops the user back to the landing prompt. This is the rule satisfied for this action.
- **No same-run stale-apply.** Because `postDesign` rejects on abort, the awaited success path is skipped — a cancelled run can't apply its own result. (The gap is only *across* runs, ESC-MS1-001.)
- **No timer leak.** The elapsed `useEffect` (`App.tsx`) starts the interval only while `busy`, clears it on `!busy` and on unmount, and resets to 0 — it can't double-run or leak across designs.
- **Honest, well-placed copy.** The overlay sets the right expectation without over- or under-stating, and the experimental offer (`ChatPanel.tsx`) now warns about the time + the cancel option *before* the user commits. Nothing claims the server-side model work is truly killed (it isn't — only the UI wait is released), which is the honest framing.
- **Tests are non-vacuous.** The cancel test makes the mocked `postDesign` reject on `signal.abort` and asserts the UI escaped to the landing (busy gone) — it would fail if Cancel didn't abort. The signal-forwarding test asserts `fetch` received the exact `AbortSignal`; `isAbortError` is checked true/false/null. Build clean; 165 frontend tests pass.

## Watch items
- **Esc-key + the broader sweep.** This overlay has a Cancel button but no `Esc`-to-cancel, and other actions (photo "Reading…", slicing, settings model-pull, modals) still need their escapes — all explicitly the **next stage** (the systematic escape sweep), not a gap in this change.
- **Server-side cancel.** Client-abort releases the UI; the local model finishes its current pass in the background (killing the web server doesn't abort an in-flight Ollama generation — only killing the runner does). A true server-side cancel is a later improvement, honestly scoped.

## Escalation recommendation
No escalation needed. One Minor (a cross-run zombie-request guard, fixable with the existing `renderSeq` pattern) + two Nits, on a small change whose core escape behavior is live-verified working. The systematic multi-action escape sweep is the next stage and will get its own gate.
