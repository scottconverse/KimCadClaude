# Audit Lite — Stage 8.5 Slice 2 MS-1b: conversation thread + refine input
**Date:** 2026-06-03
**Scope:** `App.tsx` (messages thread + handleRefine + runDesign), `ChatPanel.tsx` (full rewrite to render thread + refine textarea), `Workspace.tsx` (new props), `api.ts` (ChatTurn/Message types), `styles.css` (refine styles), `App.test.tsx` (updated mock + Slice 2 tests).
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/1** — ship. One Nit (comment parity). The conversation thread is correctly implemented: history is snapshotted before the new user turn is appended, the error path surfaces in the thread rather than orphaning a dangling user message, clarification_needed correctly routes through the refine input, and the tests are non-vacuous. 70 vitest pass.

> **FINAL (after remediation): 0/0/0/0/1.** As-found below.

## Severity rollup

**As found:** 0 Blocker · 0 Critical · 0 Major · 0 Minor · 1 Nit.

## Findings

### NIT-001 — Nit: `App.tsx` removed explanatory comments from Slice 1 code without replacing them
**Dimension:** Docs
**Evidence:** The rewrite stripped the inline comments explaining `creatingRef`, `restoredRef`, `RESAVE_DEBOUNCE_MS`, and the persist error-retry rationale — context that was load-bearing for the next engineer reading `persist()`.
**Why it matters:** Minor doc drift — the logic is unchanged but now undocumented inline.
**Fix path:** Re-add the one-liner comments to the refs and constants on the next pass; no correctness impact.

## What's working

- **History snapshot is correct.** `handleRefine()` calls `buildHistory()` *before* `setMessages((prev) => [...prev, { role: 'user', content: followUp }])` — so the backend receives `[prior turns]`, not `[prior turns + the in-progress turn]`. This is the critical ordering invariant and it holds. (`App.tsx:178-183`)
- **Error path surfaces in the thread, no orphaned user message.** `runDesign()` always appends an assistant message in both the success and catch paths — a network failure shows as an error-toned assistant bubble rather than leaving the user turn without a reply. (`App.tsx:148-153`)
- **Clarification inline works.** `result?.status === 'clarification_needed'` switches the refine placeholder to "Answer the question above…" and `canRefine = hasResult && !busy` is true on clarification_needed (the result is non-null), so the user types their answer and `handleRefine()` fires with the full thread as history — the exact path the backend needs to continue in context. (`ChatPanel.tsx:44-50`)
- **State resets correctly.** `handleSubmit` resets `messages` to `[{ role: 'user', content: submitted }]`; `handleNewDesign` resets to `[]`; restore seeds `[user, assistant]` from the reopened design. All three are correct.
- **Tests are non-vacuous.** The `threads prior history` test asserts the actual shape of `postDesign`'s second argument — `expect.arrayContaining([expect.objectContaining({ role: 'user', content: 'a box' }), ...])` — not just that it was called. The `msg-count` assertion correctly counts 4 messages after a refine (user→assistant→user→assistant). The `resets on new design` test confirms the workspace is gone after `handleNewDesign`.
- **Accessibility.** The refine textarea has `aria-label="Refine your part"`, a `focus-visible` ring via `.kc-refine-input:focus-visible`, and the Send button has `aria-label="Send refinement"`. Keyboard: Enter submits (Shift+Enter for newline). `canRefine` correctly hides the input while busy so the user can't submit during an in-flight request.
- **Auto-scroll.** The `useEffect` on `[messages, busy]` scrolls `bodyRef` to the bottom on every new turn — the user always sees the latest reply.

## Watch items
- The `buildHistory()` filter `m.role === 'user' || m.role === 'assistant'` is a no-op guard since `Message.role` is typed as `'user' | 'assistant'` — but it's harmless defensive code and costs nothing to keep.
- On a very long conversation the refine input grows the context sent to the model indefinitely (subject only to the backend's `MAX_HISTORY_TURNS=20` cap). The cap is adequate for current use; watch if conversations routinely hit 20+ turns.

## Escalation recommendation
No escalation needed. One Nit, no correctness/UX/security issues, 70 tests pass. Ship.
