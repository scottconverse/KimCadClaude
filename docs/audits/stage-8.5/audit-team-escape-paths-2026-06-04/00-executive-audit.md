# 00 — Executive Audit — KimCad Stage 8.5 "escape-paths" stage

**Date:** 2026-06-04 · **Branch:** `stage-8.5-usability` · **Diff:** `8618027..HEAD` (design-cancel MS-1 `5118918` + the sweep `7fb2642`)
**Posture:** balanced · **Mode:** full (5 roles) · **Writer:** audit-only
**Gate bar:** 0/0/0/0/0 before Scott's walkthrough. **NEVER merge/tag — Scott's authorization only.**

## Executive summary

The escape-paths stage makes every blocking action cancelable so the user is never trapped (the
load-bearing rule Scott set after hitting an unkillable "Designing…" screen). The audit confirmed the
core property holds: all four in-flight actions (design, photo read, slice, import) have a working
Cancel that aborts the request and returns the user to the prior control with no error; the design
overlay adds an honest local-AI message, a live elapsed timer, and Esc; requests are abortable end to
end; the design seq-guard + abort-prior prevent stale/superseded results. QA found the app fully
working (no regressions) and all four cancels verified live; the test guards are non-vacuous
(mutation-proven). The audit's value-add: it caught **a real regression the timer change introduced** —
reopening a saved design showed the "Designing…" overlay with a garbage elapsed value and a dead
Cancel — plus a test gap (cancel tests didn't assert "no error shown") and missing docs.

**Every finding has been remediated to 0/0/0/0/0** (see `REMEDIATION.md`). Re-verified: build clean,
**175** frontend tests pass (Viewport now has its own test).

## Severity roll-up (as found → after remediation)

| Severity | Found | After |
|---|---|---|
| Blocker | 0 | 0 |
| Critical | 0 | 0 |
| Major | 3 | **0** |
| Minor | 10 | **0** |
| Nit | 3 | **0** |
| **Total** | **16** | **0** |

Per-role as found: Engineering 0/0/1/2/1 · UI/UX 0/0/0/2/1 · Docs 0/0/1/2/0 · Test 0/0/1/4/1 · QA 0/0/0/0/1.

## Top findings (all remediated)

1. **ENG-001 (Major)** — Reopening a saved design (`#/design/<id>` cold load) showed the "Designing…" overlay with a garbage elapsed (~28M min) + a dead Cancel: the restore set `busy` without stamping `busyStartRef` and reused the design overlay. → Added a `restoring` state; a reopen now shows a plain "Reopening your design…" overlay (no timer, no Cancel); a design run keeps the cancelable timed overlay. (Closes ENG-002 too.)
2. **TEST-801 (Major)** — 3 of 4 cancel tests asserted "un-stuck" but not "no error shown," so an isAbortError-miss (leaking the raw "aborted") would slip. → Added "no error surfaced" assertions to the ExportPanel, MyDesigns, and a new App refine-cancel test.
3. **DOC-ESC-001 (Major)** — the escape hardening was undocumented in CHANGELOG. → Added an `[Unreleased]` entry.
4. **UX-801 (Minor)** — the ~2 Hz elapsed timer inside `role="status"` would chant in a screen reader. → `aria-hidden` the timer node.
5. **UX-802 (Minor)** — the busy overlay's 80% wash let a framed part weaken the dark-copy contrast during a refine. → Bumped the backdrop to 94% (near-solid).
6. **ENG-003 (Minor)** — slice/import didn't abort a prior in-flight request before overwriting the ref (latent). → Added abort-prior (mirrors runDesign/handleFile).
7. **TEST-802/803/804/805** — added: the `isAbortError` DOMException branch; an App refine-cancel test; a new **Viewport.test** rendering the real busy overlay (design Cancel→handler, restore overlay, elapsed) via a mocked three.js viewport; a `postSlice` signal-forwarding assertion.
8. **DOC-ESC-002/003 (Minor)** — HANDOFF resume block + the usability plan now note the escape stage was inserted ahead of Slice 8 (and pulled some Slice 9 "progress on long runs" scope forward).

(ENG-004 — a no-op double-revoke in PhotoOnramp — is intentional defense-in-depth, harmless, no change. UX-803 — three slightly-different "your computer's AI" phrasings — correct in context, no change. QA's lone Nit — a post-unmount `act` warning — is a React-18 no-op.)

## What's working well (credit)

- **The escape property holds across all four actions** — Cancel aborts + returns clean, no error; the cancel-vs-failure classification (re-throw AbortError) is correct end to end. (Engineering + QA + the live wiring-audit.)
- **The trust guards are non-vacuous** — mutation testing proved the design-cancel, Esc, and seq-guard tests each bite; the seq-guard (race a hanging design against a completing one, resolve the loser late, assert the winner's state untouched) is the strongest piece. (Test.)
- **Runtime is clean** — all demo endpoints 200, a real demo design + slice succeed, no regressions; all four cancels verified in the rendered preview. (QA + the session wiring-audit.)
- **Honest copy + sound non-targets** — the local-AI/elapsed/Esc framing is accurate; save (non-blocking commit), model-pull (external), and the global timeout (deferred) are correctly out of scope. (UI/UX + Docs.)

## This-sprint punch list / Next-sprint watchlist
See `sprint-punchlist.md` (all 16 closed) and `next-sprint-watchlist.md` (the deferred global timeout; broader Esc-everywhere + modal Esc; a true server-side cancel of OrcaSlicer/Ollama).

## Blast-radius notes
The ENG-001 fix threads a new `restoring` prop App→Workspace→Viewport and splits the busy overlay; no behavior change to a real design run (re-verified by the full suite + the new Viewport test). Doc fixes are doc-only.

## Sign-off
All five roles ran (`01`–`05`); every finding is closed (`REMEDIATION.md`). **Gate: 0/0/0/0/0.** The four escapes were also verified live (wiring-audit) this session. Pending Scott's walkthrough + approval. **Not merged, not tagged.**
