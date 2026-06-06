# Stage 5 (deterministic template engine + live sliders) — backfill audit, executive summary
**Date:** 2026-06-05 · **Scope:** the CURRENT `main` code of the Stage 5 surface — `templates.py`
(families, clamping, the `gaps` ordering), the `/api/render` live-slider re-render + `pipeline.rerender`,
the slicer capacity/message path, and the slider/numeric/units UI (`RightPanel.tsx`, `useUnits`,
`styles.css`). Audited live (real OrcaSlicer) + statically.
**Why:** Stage 5 never got the owed `wiring-audit`, and its `audit-team` predated later changes.

## Method (real skills, independent agents)
Round 1 — six independent agents: a `wiring-audit` driving the live demo + the five `audit-team`
deep-dives. Round 2 — two independent re-audit agents (backend/engine/docs + UI/UX live), plus the
orchestrator's own live-slicer reproduction to root-cause the capacity bug.

## Round-1 severity rollup (deduped)
Blocker 0 · **Critical 1** · **Major 4** · Minor 7 · Nit 4. This stage is where the real bugs were
(as predicted) — three genuine defects, all confirmed by live runs, not inference.

## The real bugs (found → fixed → verified)
- **QA-501 / wiring M-1 (Critical):** `POST /api/render` 500'd on a non-finite JSON number
  (`Infinity`/`NaN`/`1e400` — `json.loads` accepts them). The geometry clamped them, but echoing
  inf/nan into the response tripped `allow_nan=False`. Fixed with a `math.isfinite` guard that
  coerces non-finite (and bool) to `null`, matching the typed `adjusted_params` contract. Live: now
  a clean 200 with `requested: null`.
- **ENG-501/502 (Major):** a thick wall on a small box collapsed it into a silently-**solid block**
  that still gated PASS (confirmed: a 14³ solid cube reported "Ready to print"). Fixed by
  generalizing the `gaps` ordering with a coefficient and adding a wall-vs-dimension constraint
  (`wall ≤ 0.5·dim − 1` on every axis) so a real cavity always remains. The constraint clamps both
  slider and LLM-derived values. A generic "realized-volume" gate check was considered and rejected
  (solid parts are legitimately printable; the fix belongs in per-family geometry constraints).
- **QA-502/504 (Major):** the gate said "fits the build plate" for parts that then **failed to
  slice** — even a 200 mm box on a 256 mm bed. Root-caused live to two compounding effects:
  OrcaSlicer's auto-arrange reserves edge clearance (usable plate ≈ 170 mm, not 256), AND the
  printability **auto-orient rotates the part**, so any axis can become a footprint dimension.
  Fixed by capping **every** outer template dimension at the verified-sliceable ~170 mm side (a
  170³ cube is verified to slice end-to-end through orient), so a slider/LLM part can no longer pass
  the gate then fail to slice; plus an honest slicer message that parses the OrcaSlicer arrange
  signature and names the footprint instead of the generic "too large or too solid." (The big
  Elegoo Max's larger plate + the experimental-codegen path are noted as a Stage-10 per-printer
  envelope refinement.)

## Other fixes (every finding, Blocker→Nit)
- **ENG-504:** the registry now rejects a family with an empty bbox axis (a forgotten axis silently
  reported 0 mm). **ENG-505:** `_apply_gaps` floors integer params and the drawer divider caps its
  compartment count to the length so cross-walls can't overlap into a solid. **ENG-503** (single
  global render lock) and **ENG-506** (unreachable `_fmt` branch) confirmed documented/no-op.
- **UX-501/502:** inch readouts use one consistent 3-dp precision authority (no ragged
  "3.15 / 2.362"); the title hint and the edit-error bounds now agree. **UX-503/504:** the slider
  and the mm/in toggle reach a 44 px touch target at narrow widths, not just `pointer:coarse`.
- **DOC-101:** a new user guide `docs/guide-sliders-and-units.md` (linked from README + the docs
  index) — the marquee slider/units features had no how-to. **DOC-102:** the Stage-5 benchmark file
  now documents the `python -m kimcad.template_bench --write …` re-run command.
- **TEST-501:** a binary-free assertion that a re-render's emitted SCAD reflects new values (the
  offline stub renderer otherwise hid a do-nothing slider). **TEST-503:** the rerender
  unknown-family branch. Plus regression tests for every fix above (QA-501 non-finite, ENG-501
  cavity, QA-502 cap, ENG-504/505, the honest slicer message).

## Round-2 re-audit
Both lanes CLEAN. False-green check: every new test FAILS if its fix is reverted (verified). The
worst slider corner (170³) slices to 275 KB of real toolpath G-code. One coverage gap the re-audit
named (no isolated test for the arrange message) was then closed.

## Final verdict
**STAGE 5 BACKFILL: CLEAN — 0/0/0/0/0 across all five lanes + wiring-audit PASS.**
Gate green: ruff, geometry backends, 771 pytest (not-live), 276 vitest, SPA build reproducible.
Live OrcaSlicer slice runs on push.
