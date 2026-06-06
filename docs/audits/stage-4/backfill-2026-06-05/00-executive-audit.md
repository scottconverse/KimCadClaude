# Stage 4 (React SPA shell + viewport) — backfill audit, executive summary
**Date:** 2026-06-05 · **Scope:** the CURRENT `main` code of the Stage 4 surface (the React/TS SPA
in `frontend/src/**`, the committed build `src/kimcad/web/**`, and the stdlib backend serving +
core render/slice wiring in `src/kimcad/webapp.py`), audited live + statically.
**Why:** Stage 4 never got the owed `wiring-audit`, and its `audit-team` package predated the
Stage 8.5 overhaul. This is the Phase-B backfill: re-audit the current code, fix EVERY finding, re-
verify to 0/0/0/0/0, commit the evidence.

## Method (real skills, independent agents)
Round 1 — six independent agents in parallel: a `wiring-audit` driving the live demo app + the five
`audit-team` role deep-dives (engineering / UI-UX / docs / tests / QA). Deep-dives:
`wiring-audit-stage-4-2026-06-05.md`, `01-engineering-deepdive.md` … `05-qa-deepdive.md`.
Round 2 — two independent re-audit agents (live UI/UX measurement + docs/backend cross-check) after
the fixes, plus a focused empirical re-verify of the one fix that round 2 rejected.

## Round-1 severity rollup (deduped across lanes)
Blocker 0 · Critical 0 · **Major 8** · Minor 17 · Nit 9.
The "Majors" were: 2 UI/UX (readiness-verdict AA contrast; a 248px phantom dead-scroll), 3 docs
(stage-status drift across README/ROADMAP/CHANGELOG from the 8.5 merge), 1 engineering (a stale,
HTTP-exposed vendored three.js, unreferenced by the SPA), 1 engineering (build-vs-source drift
guard — found ALREADY MITIGATED by `scripts/ci.sh`), 1 test (the reopen→re-gate→slice-refusal chain
had no end-to-end test). No safety invariant was broken: gate-failed-never-sliced, the mid-slice
stale-geometry guard, path-traversal defense, and `confirm is True` send identity all verified intact.

## What was fixed (every finding; Blocker→Nit)
**Backend (`webapp.py`, `connectors.py`):** removed the dead `web/vendor/` tree + `_serve_vendor`
route (ENG-401/407); locked the registry reads in `_serve_mesh`/`_serve_gcode` (ENG-403); gave
`_serve_static` an mtime+size cache so the content-hash ETag isn't recomputed per request, preserving
the never-stale guarantee (ENG-404); serve `index.html` fresh (ENG-405); a distinct `MAX_SLICE_CACHE`
(ENG-406); `/api/render` `adjusted_params.requested` is now number-or-null (QA-001); `/api/connectors`
carries a `configured` flag derived from `build_connector` so an unset OctoPrint template reads as
not-ready, not just "not a mock" (QA-002); a reopened design's report now reflects the RE-GATED
verdict, never showing "Ready" over a silently-blocked part (TEST-402); saved designs are auto-named
by the refine lineage's ORIGINAL prompt, not the latest tweak (QA-004). ENG-402 (build-drift guard)
and ENG-408 (single-user lock) were verified already-handled/documented.
**Frontend (`styles.css`, components):** AA-safe deep-green text token for the readiness verdict +
confidence badge (UX-001, now 6.1:1 / 5.6:1); the sr-only dead-scroll fixed by pinning the absolute
box to the origin (UX-002, dead-scroll 248px → 0px); mobile topbar no longer overflows (M-1/UX-005);
"Backup (.kimcad)" relabel + no anchor underline (L-2/UX-003); resting destructive cue on Delete
(UX-004); content-width Settings toggle/Reset on mobile (UX-007/008); honest STEP/BREP "planned" copy
(L-1); viewport canvas `max-width` safety net (QA-003). UX-006 (modal scrim) verified already-correct
(both overlays are `position:fixed; inset:0` over the topbar).
**Docs:** reconciled the Stage-8.5 status drift across README, ROADMAP, CHANGELOG, HANDOFF, the
My-Designs guide, ARCHITECTURE, and frontend/README (DOC-401…408); added a "what the 3D preview
shows" section (DOC-406); purged every now-dead `/vendor/` reference; re-pointed the route list to
ARCHITECTURE; banner on the historical Stage-8.5 plan doc.
**Tests:** end-to-end reopen→re-gate-fail→slice-refused HTTP test (TEST-401/402, a real guard, not a
tautology — verified); QA-001 null-on-non-numeric assertion; QA-002 `configured` assertion; QA-004
original-intent naming test; frontend `api.ts` wrapper tests for the saved-designs + settings/status
seam (TEST-403).

## Round-2 re-audit — caught and fixed
Round 2 rejected the first UX-002 attempt (`clip-path` clips paint, not layout — the 248px persisted)
and found 4 residual live `/vendor/` contradictions my own deletion created (frontend/README build
note, a HANDOFF API-contract line, a CHANGELOG phrasing, my own stale ledger row). All fixed; UX-002
re-verified empirically at **0px** dead-scroll with the sr-only spans retained (a11y intact).

## Final verdict
**STAGE 4 BACKFILL: CLEAN — 0/0/0/0/0 across all five lanes + wiring-audit PASS.**
Gate green: ruff, geometry backends, 764 pytest (not-live), 276 vitest, SPA build reproducible.
Live OrcaSlicer slice runs on push (pre-push hook).
