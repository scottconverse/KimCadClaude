# 00 — Executive Audit — KimCad Stage 8.5 Slice 7 ("describe with a photo" on-ramp)

**Date:** 2026-06-04 · **Branch:** `stage-8.5-usability` · **Diff under audit:** `76c6f89..HEAD`
**Posture:** balanced · **Mode:** full (all 5 roles) · **Writer mode:** audit-only
**Gate bar:** 0/0/0/0/0 (every finding fixed, Blocker→Nit) before Scott's walkthrough. **NEVER merge/tag — Scott's authorization only.**

## Executive summary

Slice 7 is a small, well-built, trust-sensitive slice and it holds up. All five load-bearing trust
invariants — the photo **never auto-sends off the machine** (vision is pinned to the local provider
even with cloud TEXT enabled), the UI **never promises "photo → finished part"** (a rough, editable,
estimates-only seed), it **never auto-submits** (a human confirms), it is **best-effort / never-500**
(413/400/422, never a traceback), and **gemma4:e4b is THE model** (native `/api/chat` + `think:false`,
no alternative offered) — were verified HELD by the engineering, UI/UX, and test roles, and the QA role
found **zero** runtime findings (200/400/413 only, no 500s, nothing persisted to disk). The test role
proved the two trust-critical guards **non-vacuous by mutating the product** (re-routing the photo
through the cloud router, or switching to `/v1`, fails the guards with their exact assertions). The
findings were all in the **Major-and-below** band and concentrated in secondary boundary tests and in
**project-prose-doc staleness** (CHANGELOG/README/HANDOFF lagging several slices behind the branch) —
not in the slice's core behavior.

**Every finding has been remediated to 0/0/0/0/0** (see `REMEDIATION.md`). Re-verified: ruff clean,
**740** backend tests pass, **162** frontend tests pass, build (tsc+vite) clean.

## Severity roll-up (as found → after remediation)

| Severity | Found | After remediation |
|---|---|---|
| Blocker | 0 | 0 |
| Critical | 0 | 0 |
| Major | 4 | **0** |
| Minor | 10 | **0** |
| Nit | 4 | **0** |
| **Total** | **18** | **0** |

Per-role as found: Engineering 0/0/0/3/1 · UI/UX 0/0/0/2/1 · Docs 0/0/2/3/1 · Test 0/0/2/2/1 · QA 0/0/0/0/0.

## Top findings (all remediated)

1. **DOC-001 (Major, Docs)** — CHANGELOG `[Unreleased]` was frozen at Slice 1; Slices 2–7 missing. → Added Slice 2–4, 6, 7 entries + corrected the preamble.
2. **DOC-002 (Major, Docs)** — README banner + "Saving your work" described only Slice 1; the camera on-ramp was undocumented. → Banner updated to the real branch state; the on-ramp mentioned honestly; the Slice-1 tag de-pinned.
3. **TEST-701 (Major, Tests)** — the 400 "Empty upload" branch of `/api/photo-seed` was untested. → Added `test_photo_seed_empty_upload_is_400` (asserts 400 + vision never invoked).
4. **TEST-702 (Major, Tests)** — `uploadPhoto`'s server-error mapping was mocked on both sides of the seam, tested on neither. → Added api.test.ts cases: a 422 surfaces the backend message; a non-JSON body → a readable error.
5. **UX-001 (Minor, UX)** — the error card promised "describe it in words" but offered only "Try another photo". → Copy tightened to "…or **cancel** and describe the part in words" (truthful: Cancel → the text box), backend + component in sync.
6. **UX-002 (Minor, UX)** — the confirm card's group label duplicated the affordance label. → Phase-specific `aria-label` (reading / "A rough starting point from your photo" / "Photo couldn't be read").
7. **ENG-002 (Minor, Eng)** — an empty vision response on a stale Ollama looks like a bad photo. → A one-line stderr breadcrumb on an empty seed (matches the existing `FallbackProvider` logging style); user still gets the graceful 422.
8. **ENG-003 (Minor, Eng)** — `cfg = get_config()` sat just outside the never-500 try. → Moved inside the try (closes the last theoretical 500 path).
9. **TEST-703 / TEST-704 (Minor, Tests)** — the drag-drop `onDrop` path and the "Use a different photo" re-pick (+ its object-URL revoke) were untested. → Added both tests.
10. **DOC-003/004/005/006 (Minor/Nit, Docs)** — HANDOFF resume block, the usability-plan Slice 6/7 status markers, the ARCHITECTURE "Two jobs"/web-layer inventory, and the prompt's "millimetres" spelling were stale/inconsistent. → All corrected.

(Remaining: **ENG-001** imports moved to module top; **ENG-004** curly-punctuation Nit — confirmed *consistent house style* across the whole UI, no defect, no change; **UX-003** "different/another" wording unified to "Use a different photo"; **TEST-705** the FakeProvider-vs-real-router split — confirmed correct, no change. Full per-finding disposition in `REMEDIATION.md`.)

## What's working well (specific credit)

- **The trust rule is enforced at the right layer and tested adversarially.** `_SettingsAwareProvider.describe_photo` forces local vision at one chokepoint; the regression test fails loudly (with its exact message) if anyone routes a photo through the cloud router. (Engineering + Test.)
- **Honesty is reinforced three ways and is impossible to bypass** — the standalone scale note, the privacy line, and the disclaimer baked into the seed text itself; the seed is a real editable textarea that **takes focus on confirm** (AT announce + invite-to-edit). (UI/UX.)
- **Runtime is clean** — 200/400/413 only, never a 500; an oversized upload is rejected in ~0.001s without sinking the body; a marker-payload photo POST left **no** bytes on disk. (QA.)
- **Error-path coverage is strong on the backend** — 3 of the (now 7) photo tests are negative paths; the load-bearing guards are non-vacuous by product mutation. (Test.)
- **Code-level docs/copy are a model of honest writing** — no over-promise anywhere; the inline docstrings capture the local-only / never-500 / never-persisted guarantees right where they're enforced. (Docs.)

## This-sprint punch list

See `sprint-punchlist.md`. **Status: all 18 items closed (0/0/0/0/0).** Re-verified green.

## Next-sprint watchlist

See `next-sprint-watchlist.md` — forward-looking items that are explicitly NOT Slice-7 blockers (the real-vision reading-state polish slated for Slice 9; the affordance contrast margin; the older-Ollama empty-vision support path now breadcrumbed; the optional-engine one-click-enable deferred with Stage 8).

## Blast-radius notes

- The doc fixes (DOC-001..005) bring CHANGELOG/README/HANDOFF/usability-plan/ARCHITECTURE current through Slice 7; they also cleared **pre-existing** Slice 2–6 doc-debt the per-slice builds had left. No code blast radius (doc-only).
- The copy change (UX-001) touches the backend `cant_read` message and the component's empty-seed message in lockstep, so the client error path and the server 422 stay consistent.
- No fix touched the load-bearing routing or the gate; the trust invariants are unchanged by remediation (re-verified by the full suite).

## Sign-off

All in-scope roles ran and produced deep-dives (`01`–`05`). Every finding has evidence + a fix path and is now **closed** (`REMEDIATION.md`). The slice meets the Surface-D design and all five trust rules. **Gate: 0/0/0/0/0.** A runtime `wiring-audit` follows; then this goes to Scott for his walkthrough + approval. **Not merged, not tagged.**
