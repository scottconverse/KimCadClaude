# Executive Audit — KimCad Stage 5 (deterministic template engine + live sliders)

**Audit date:** 2026-06-02
**Audit type:** Stage-gate, full five-role, balanced posture
**Branch:** `stage-5-template-engine` @ `91b691c` (diff `main...stage-5-template-engine`, excl. `docs/design` + the completion directive)
**Gate bar:** 0/0/0/0/0 (every finding fixed, Blocker→Nit) before merge + tag.

---

## Executive summary

Stage 5 is a clean, well-architected stage with no Blockers and no Criticals. The "pure-data families" design — one immutable pydantic definition drives codegen, the analytic bounding box, and the slider JSON — is the right call, and it collapses the injection surface to a single numeric formatter that all five load-bearing safety invariants were verified to hold against: the deterministic emit is injection-safe (hostile strings, NaN/inf, lists/dicts all coerce→clamp→format to finite in-range numbers), re-render is structurally model-free (a wired provider *raises* if touched), a gate-FAILED re-render drops the cached slice/G-code at runtime (verified by curl: slice→re-render→`GET /api/gcode` 404), concurrent re-renders serialize on `render_lock`, and the send-gate boundary is documented and unweakened. The marquee UX — drag a slider, sub-second deterministic re-render, quiet viewport swap, server-truth re-sync — works end-to-end and is faithful to the Workshop prototype. The three Majors are all *non-code* gaps: one stale contributor doc (HANDOFF) and two missing regression tests for safety behaviors that are *implemented correctly but tested by nothing*. Everything else is polish (touch-target sizing, error copy, message disambiguation, hygiene comments).

## Severity roll-up (all roles)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 14 |
| Nit | 14 |
| **Total** | **31** |

Per role: Engineering 0/0/0/3/4 · UI/UX 0/0/0/3/4 · Docs 0/0/1/3/2 · Test 0/0/2/3/2 · QA 0/0/0/2/2.

## Top findings (by severity / leverage)

1. **DOC-001 (Major) — HANDOFF.md is stale.** Wrong branch head (`1a0af61` vs `91b691c`), wrong ahead-count (5 vs 8), wrong test counts (404 / 470 vs 484), and "backend done, Slice 4 next" when Slices 4 *and* 5 are committed. The exact "one truth per doc" failure the Stage-4 retro named, recurring across docs.
2. **TEST-001 (Major) — No test that a gate-FAILED re-render makes the part non-sliceable/non-sendable.** The single most important live-slider safety property (drag past printable → old good G-code must not ship) is implemented correctly (`gate_status_by_rid` re-stamped every re-render) but rests on nothing in the suite; every tested re-render lands in a *passing* shape.
3. **TEST-002 (Major) — Frontend `renderSeq` stale-response discard is never exercised.** The guard that stops an out-of-order re-render response from snapping the viewport back to a stale shape is documented and correct, but no test fires two overlapping renders and asserts the newer wins.
4. **ENG-501 (Minor) — `wall_hook` analytic bbox under-reports Z by 2 mm at the plate-height slider minimum** (`plate_h=20`), so that one slider position always fails the gate — a confusing UX dead-zone. Gate holds (fail-closed), so it's not a safety hole.
5. **UX-001 (Minor) — Mobile slider touch target below the 44 px floor** (9 px track / 26 px thumb); `.kc-range` is the one interactive control the codebase's own coarse-pointer 44 px rule skips — on the most-touched control of the feature.
6. **QA-002 / TEST-006 (Minor/Nit) — `/api/render` returns the same 404 "no adjustable parameters" for an unknown id and a real LLM-backed id** — an integrator can't tell a bad id from a no-slider design.
7. **UX-002 (Minor) — The re-render error copy concatenates the raw thrown message** ("…HTTP 500…") into an otherwise warm sentence and doesn't reassure that the last version is intact.
8. **DOC-004 (Minor) — CHANGELOG phrases "<1 s" as the proven bar** while the automated gate certifies ≤5 s; true today, reads as overclaim if a family regresses.
9. **UX-003 (Minor) — The "Updating…" note has no minimum dwell**, so on a fast render it can flicker rather than read as a deliberate signal.
10. **ENG-502/503 (Minor) — Concurrency hygiene:** `version_counter` is read just outside `lock` (safe via `itertools.count` atomicity), and `render_lock` is process-global (a future multi-client ceiling; invisible for the single-user local UI).

The remaining Minors/Nits (ENG-504..507, UX-004..007, DOC-002/003/005/006, TEST-003/004/005/007, QA-001/003/004) are in the deep-dives and the punch list.

## Cross-role findings

- **The re-render "transition into a worse state" safety net is implemented but under-tested (TEST-001 + TEST-002 + QA-001).** The Test role found both the server-side (good→gate-fail) and client-side (new→stale) guards untested; QA confirmed the server-side guard *works at runtime* but couldn't trip the build-volume variant through the demo `snap_box` (clamps cap under the printer envelope — safe by design). Resolution: add the forced-overflow regression test (TEST-001) which also gives QA-001 a reachable gate-fail path, plus the overlapping-response test (TEST-002).
- **`/api/render` unknown-id messaging (QA-002 + TEST-006).** QA found the runtime conflation; Test found the matching coverage gap. One fix (split the message + add the unknown-id assertion) closes both.
- **The `<1 s` performance promise (DOC-004 + TEST-003).** Docs phrase it as the bar; Test notes it's never asserted on a real render (only the 5 s ceiling is gated). One fix — assert `all_meet_target` on the live bench + soften the CHANGELOG wording — closes both honestly.

## What's working (credited, specific)

- **Injection trust boundary is exemplary** — coerce→clamp→format at the family entry, verified against hostile inputs; combined with the existing `sanitize_scad` defense-in-depth, SCAD generation is robust by construction (Engineering).
- **"No model call" is proven three independent ways** — structural `openscad_calls == 0`, a `_NoModelProvider` that raises, and a determinism check that re-emits SCAD by a second path (Test).
- **Slice-invalidation holds at runtime** — slice → re-render → `GET /api/gcode` 404, verified by curl (QA).
- **The deterministic sub-second re-render is real and felt** — a rapid drag coalesces to exactly one `POST /api/render`, the viewport swaps without blanking, sliders + dims re-sync to server truth (UI/UX, rendered at desktop + mobile).
- **The user-facing docs (ARCHITECTURE/CHANGELOG/ROADMAP/README) are accurate, consistent, and correctly keep Stage 5 "pending the gate"** — the Stage-4 self-contradiction lesson applied (Docs).
- **Degrade-don't-crash discipline** — every adversarial request returned a typed 4xx/200, never a 5xx traceback; the idempotent slice cache returns in 2.5 ms (QA).

## This-sprint punch list

See `sprint-punchlist.md` — all 3 Majors + all 14 Minors + all 14 Nits (this is a 0/0/0/0/0 gate; everything is in-sprint).

## Next-sprint watchlist

See `next-sprint-watchlist.md` — forward-looking structural items (per-id re-render lock for any future multi-client mode; the `BBoxTerm` linear model vs non-linear module geometry seam; a viewport test harness for the no-browser-E2E boundary).

## Blast-radius notes (fixes that ripple)

- **ENG-501 (`wall_hook` `plate_h` min):** raising the `ParamSpec` min changes the slider's reachable range and the family's default-region; add a `plate_h=min` analytic==actual test. No migration.
- **QA-002 message split:** touches `_handle_render`'s `state is None` branch; any test asserting the exact unknown-id string must update (TEST-006 adds the case).
- **UX-001 touch hit-area:** padding the range input must not shift the track-fill gradient — verify `--pct` alignment after the change.
- **HANDOFF rewrite (DOC-001):** single-source the test count so it can't drift in two places again.

## Gate decision

**No Blockers, no Criticals — the stage is structurally sound.** It does NOT yet meet the 0/0/0/0/0 bar (3 Major + 14 Minor + 14 Nit open). Remediate all 31, re-audit to 0/0/0/0/0, run the native Windows gate, then merge + tag `stage-5`.
