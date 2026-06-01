# Audit Lite — Stage 4, Slice 4: wired design flow (conversation + plan + printability)
**Date:** 2026-06-01
**Scope:** Wiring `/api/design` into the UI — the conversation (`ChatPanel`), read-only parameters + the printability report (`RightPanel`), the status mappers (`designStatus.ts`), the `App` result state, the reinstated field-contract tests, and a new vitest harness. Branch `stage-4-react-spa-shell`. (Printer/material/slice/download = Slice 5; live sliders = Stage 5.)
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. Describe → design now renders the full result: a user/assistant conversation, the part in the viewport, the read-only parameters, and the printability verdict with a target-vs-actual dimensions table and findings — verified by a rendered desktop + mobile check. Two Minors found (a too-loose contract test and a missing chat `aria-live`) were fixed in this pass. Full CI gate (ruff + pytest incl. live + vitest) is green.

## Severity rollup (round 1)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 2 · Nit: 0

## Severity rollup (round 2 — after fixes)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0 → **0/0/0/0/0, gate cleared**

## Rendered visual check (mandatory for UI slices — done)
Rendered `kimcad web --demo` at desktop + mobile and drove the real flow. Desktop: user+AI bubbles, the real box in the viewport, Parameters (box / 80 × 60 × 40 mm), Printability "Ready to print" + a 3-row dims table + findings; layout DOM-confirmed full-height (workspace 58→860, no scroll). Mobile-375: bubbles align correctly (user right/terracotta, AI left/surface), viewport, Parameters with mono dimensions. The demo provider only emits `completed`/gate-pass, so the other three status branches were exercised by **unit tests** (designStatus.test.ts) rather than visually — an acceptable split (happy path rendered, edge states unit-tested), recorded as a watch item to render once a non-demo path can produce them.

## Findings (both fixed this pass)

### TEST-401 Minor: field-contract test only proved fields were *declared*, not *consumed*
**Dimension:** Tests · **Evidence:** the reinstated `test_frontend_source_consumes_documented_response_fields` grepped ALL of `frontend/src` — including `api.ts` (the `DesignResponse` interface). A field declared in the interface but rendered nowhere would false-pass, defeating the drift-detection intent. **Fix:** the check now greps a "consumer" source that EXCLUDES `api.ts` and the `*.test.ts` files, so a field must actually be used by a component/the logic (verified all 14 fields still resolve in App/ChatPanel/RightPanel/designStatus). **(Fixed.)**

### UX-401 Minor: conversation had no live region for async messages
**Dimension:** UX (a11y) · **Evidence:** `ChatPanel` appends the thinking state and the assistant reply asynchronously, but `.kc-chat-body` had no `aria-live`, so a screen-reader user wasn't told the design had progressed. **Fix:** `role="log" aria-live="polite" aria-busy={busy}` on the chat body. **(Fixed.)**

## What's working
- **The full result renders, honestly:** `assistantMessage` branches on every PipelineStatus — `gate_failed` keeps the mesh + shows a fail report, `render_failed` shows no mesh + the error, `clarification_needed` shows the question, `completed` shows the summary; confirmed by reading the code paths + the vitest cases.
- **Printability report:** gate badge mapped to the green/amber/red scale by **text** (not color-only — "Ready to print" / "Not printable yet"), a `dims` table with `<th scope="col">` and per-axis off-flagging, and severity-colored findings bullets.
- **Security:** every LLM/pipeline string (assistant message, headline, findings, summary) renders as escaped React text — no `dangerouslySetInnerHTML` anywhere, so no XSS surface from model output.
- **Real test coverage added:** the field-contract + every-status checks are reinstated (W2, now consumption-strict), and **vitest** stands up (W6) — `designStatus.test.ts` (all four statuses + fallbacks) and `api.test.ts` (200 / non-2xx / non-JSON) — wired into `scripts/ci.sh` so a vitest failure blocks the push (set -e), while a toolchain-less environment skips with a note (the committed build still ships).
- **Green:** ruff clean; `bash scripts/ci.sh` green (full pytest incl. live + vitest 7 passed); build clean with no `.test.ts` in the bundle and no orphan assets; `npm audit` = 0.

## Watch items
1. **W8 — render the non-completed states once reachable.** `gate_failed`/`clarification_needed`/`render_failed` are unit-tested but not yet visually exercised (the demo provider can't produce them). Capture rendered evidence when a path that yields them exists (e.g. a too-large part for gate_failed), at the latest in the Stage-4 audit-team gate.
2. **W6 (now satisfied) → keep extending vitest.** The harness exists; as Slice 5 adds printer/slice/send logic, add vitest cases there too. Component-render tests still need jsdom (deferred — the pure-logic + the rendered check cover the current surface).

## Escalation recommendation
No escalation needed. A clean flow-wiring slice: the result renders correctly and safely, the rendered check passed, real unit tests were added, and the two Minors are fixed. audit-team remains the right tool for the Stage-4 gate.
