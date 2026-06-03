# Stage 7 Stage-Gate Audit — Executive Report
**Project:** KimCad — Stage 7 (Smart Mesh + PrintProof3D + readiness report + learning store)
**Branch:** `stage-7-smart-mesh` (9 commits, 33 files, +2630/−60 vs `main`)
**Date:** 2026-06-02
**Posture:** balanced · **Mode:** full (all 5 roles) · **Writer:** audit-only

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** Every finding below was fixed and re-verified;
> see `REMEDIATION.md` and the per-role deep-dives. The as-found rollup is recorded beneath for the
> record — it is NOT the current state.

## Executive summary
Stage 7 is a clean, honestly-built stage. All five roles independently returned **zero Blockers and
zero Criticals**; the single Major was a real but contained data-loss race in the history store's
write path, now fixed with a process-wide lock + atomic replace (regression-tested: 40 concurrent
writers now keep all 40 records, vs the reproduced ~1). The load-bearing invariants all hold: the
deterministic slice gate is untouched and remains the slice authority (readiness is advisory),
PrintProof3D is genuinely arm's-length (subprocess, never linked, config-only binary path) and
never raises, the worst-of-two tone keeps the card from ever out-promising either signal, the
history store is local-first/coarse with no data egress, and no test touches the real user history.
The docs clear the Stage-4 honesty bar — nothing claims Stage 7 is done/merged/tagged. The
remaining 11 Minors + 9 Nits were polish: a write-race hardening, a few never-raises/΄honesty
refinements, UX copy (US spelling, a "Gate:" badge prefix, an arrow instead of a green check), and
three integration-path test gaps. All fixed → 0/0/0/0/0.

## Severity rollup

| Severity | As-found | Final |
|---|---|---|
| Blocker | 0 | 0 |
| Critical | 0 | 0 |
| Major | 1 | 0 |
| Minor | 11 | 0 |
| Nit | 9 | 0 |
| **Total** | **21** | **0** |

Per role (as-found): Engineering 1Maj/3Min/3Nit · UI/UX 2Min/2Nit · Docs 2Min/2Nit · Test 3Min/1Nit · QA 1Min/1Nit.

## Top findings (as-found, all now fixed)
1. **ENG-701 (Major) — history write race → lost records.** `HistoryStore.record` was a non-atomic read-modify-write with no lock; under the threaded web server, concurrent designs reliably lost records (40 writers → ~1). **Fix:** process-wide `_WRITE_LOCK` + temp-file `os.replace` (atomic); regression test added.
2. **UX-001 (Minor) — duplicate "Ready to print" headline.** The readiness verdict and the Printability gate badge could both read "Ready to print." **Fix:** the gate badge is now "Gate: passed / needs review / failed."
3. **DOC-001 (Minor) — "prints" vs "parts" in source comments.** User-facing strings/docs correctly say "parts," but a few code comments still said "prints." **Fix:** comments aligned to "parts."
4. **TEST-S7-001 (Minor) — gate-failed-recorded-to-history untested.** A documented behavior with no test pinning it on the integration path. **Fix:** test added (gate-failed run records with `gate_status == "fail"`).
5. **TEST-S7-002 (Minor) — confidence precedence untested.** `mesh_unanalysable` must force Low even when the engine ran; only the gate-only Low path was tested. **Fix:** precedence test added.
6. **ENG-702/703 (Minor) — never-raises hardening.** `record` caught only `OSError` (vs its "never raises" docstring); profile/record JSON could emit `NaN`/`Infinity`. **Fix:** broadened catch + `allow_nan=False`.
7. **UX-003 (Minor) — British spelling.** "analysed/analysable" in the Low-confidence copy + attribution. **Fix:** US "analyzed/analyzable."
8. **QA-001 (Minor) — em-dash console-safety.** The new readiness/comparison strings used U+2014 (not in cp437). **Fix:** ASCII `-` in the Stage-7 console strings (defense-in-depth atop the CLI's forced UTF-8).
9. **ENG-704 (Minor) — history pool semantics undocumented.** **Fix:** documented the comparison as intentionally all-time; `created_at` retained for future recency.
10. **TEST-S7-003 + the Nits (ENG-705/706/707, UX-004/005, DOC-002/003/004, TEST-S7-004, QA-002).** Boundary test, fully-guarded readiness fallback, runner-stderr note, inert-engine-path config comment, the recommendation arrow, gauge spacing, the HANDOFF count clarifier, the card design-screen reference. All fixed or acknowledged.

## What's working well (specific, credited)
- **Never-breaks-the-build is real and tested**, not just asserted — `validate_model`'s degrade matrix (no binary / no report / runner raises / unparseable / non-dict / bad status / non-list issues) is exhaustively exercised, and the bed-positioning test actually loads the STL and checks `min≈origin` rather than trusting a flag.
- **The slice gate is untouched** — `gate.status is FAIL and not proceed_anyway → return` is intact; readiness rides alongside as advisory, verified at runtime (a gate-failed part returns `sliced:false`, no G-code, un-sendable).
- **Honesty by construction** — worst-of-two tone (engine-worse and gate-worse both tested), gate-only vs engine attribution/confidence never overstate, and the comparison is factual ("on par" for a tie, never "below"; no history → no line).
- **Privacy/local-first intact** — coarse local JSON in the per-user home, no egress; PrintProof3D runs locally with a config-only binary path (injection-safe).
- **UX-first card** — `pathLength=100` honest gauge, scoped `--tone` mechanism (no background flood), full non-color-only a11y (role=img gauge, screen-reader severity word), all tone colors clear WCAG AA on the warm surfaces, and the stale-comparison-on-drag concern is clean (the body is a pure prop function).
- **Disciplined test + CI** — 664 pytest (incl. live OrcaSlicer) + 43 vitest, no skips/flake; the pre-push gate is a superset of hosted CI (ruff + full pytest + vitest + SPA build-reproducibility + a `KIMCAD_RELEASE=1` hard-gate).
- **Doc honesty is exemplary** — every surface marks Stage 7 implemented-on-branch/pending-gate; zero done/tagged overclaim; every spot-checked claim matches the code.

## This-sprint punch list
See `sprint-punchlist.md`. All 21 items were fixed in this remediation pass (the stage-gate requires 0/0/0/0/0 before tag).

## Next-sprint watchlist
See `next-sprint-watchlist.md` — the forward-looking items (fold a PrintProof3D `fail` into the slice gate once the engine ships enabled; a cross-process history lock if multi-instance ever matters; a recency window for the comparison; live engine-on slider latency).

## Blast-radius notes
- The UX-003 spelling fix touched a user-facing string that an existing test asserted (`test_unanalysable_mesh_drops_confidence_to_low`) — that assertion was updated in lockstep.
- The UX-001 "Gate:" badge prefix changed the rendered text an existing RightPanel test asserted — updated to match.
- The ENG-701 lock is process-wide; it serializes all history writes, which is harmless (writes are tiny/rare) and does not touch the read path.
- Re-running `npm run build` regenerated the committed `src/kimcad/web/assets/*`; the pre-push hook's build-reproducibility check gates it.
