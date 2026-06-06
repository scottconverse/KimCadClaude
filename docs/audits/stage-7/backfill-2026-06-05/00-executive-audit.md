# Stage 7 (Smart Mesh + PrintProof3D + readiness report) — backfill audit, exec summary
**Date:** 2026-06-06 · **Scope:** the CURRENT `main` code of Stage 7 — `smart_mesh.py` (readiness
synthesis), `printproof3d.py` (the arm's-length engine), `history.py` (learning store), the
readiness attachment in `pipeline.py`/`webapp.py`, and the readiness report card UI
(`RightPanel.tsx`). Audited live + statically.

## Method (real skills, independent agents)
Round 1 — six independent agents (`wiring-audit` on the readiness card + five `audit-team`
deep-dives). Round 2 — an independent re-audit agent (backend + UI + docs), with false-green checks.

## Round-1 severity rollup (deduped)
Blocker 0 · Critical 0 · **Major 2** · Minor ~12 · Nit ~3. The load-bearing INVARIANT held and at
the right layer: the deterministic Printability Gate stays the slice authority; the readiness card
is advisory, never flips a gate verdict, and never claims the engine ran when it didn't (engineering
deep-dive: 0 findings; verified by tests + live).

## The Majors (found → fixed → verified)
- **UX-001 (Major):** the readiness WARN confidence badge/verdict measured ~4.23:1 — below WCAG AA
  4.5:1 — on the warn tint (the most-travelled non-trivial tone). Fixed with a darker
  `--kc-warn-text` token (parallel to the Stage 4 pass-green fix); now ~6.0:1. Also added an
  automated contrast-guard test (UX-006) over pass/warn/fail × verdict+badge so the whole *class*
  of tone-contrast regression fails the build — the old token measures 4.23:1 and FAILS the guard,
  the new one passes (false-green confirmed).
- **TEST-S7-101 (Major):** the "engine configured but returned no report" honesty path (the most
  likely real degrade) was untested. Added a test pinning that readiness is attributed to the gate
  alone — never credits the engine, never reports High confidence — when PrintProof3D returns None.

## Backend correctness (every finding)
- **ENG-702/QA-702:** the score-penalty and risk-tone tables had drifted (`nit` had a penalty but
  no tone → a silent 1-pt dent; an unknown severity silently dented 5 pts with nothing on the card).
  Unified into ONE `_PP_SEVERITY` table so penalty and surfaced-risk can't diverge: a nit is fully
  cosmetic (0/none), and an unknown severity surfaces as a visible warn (no silent dent).
- **ENG-703:** an unexpected gate status now fails SAFE to the lowest base (renders as a visible
  "not ready") instead of a benign mid-70 that could silently absorb an upstream bug.
- **QA-701:** a warn/fail verdict can no longer render with an empty risk list — a neutral "review
  before printing" note is synthesized so the card always says *why*.
- **QA-703:** the history line no longer says "On par" when the majority of past parts strictly beat
  this one — it says so honestly.

## UI a11y + docs
- **UX-002:** the on-model toggle gets a 24px touch target (the InfoTip already had a 25px overlay).
  **UX-003:** the legend swatches now use the card's risk tones (consistent with the risk dots; the
  3D highlight stays bright for the dark viewport — a deliberate cross-surface choice). **UX-004:**
  the gauge's visible number is `aria-hidden` so the score isn't announced twice.
- **DOC-001:** the PrintProof3D confidence trigger reworded ("runs and returns a usable report") + the
  Low state documented. **DOC-002:** README documents the Low/Medium/High confidence. **DOC-003:**
  the stale pre-merge "~2–3 weeks / remaining for the stage gate" tail removed from the (DONE) Stage 7
  ROADMAP section. **DOC-004:** the learning-store data-flow corrected ("PrintProof3D influences the
  score; it does not write the store").

## Accepted / documented (no code change)
- **M-1** (demo probes real Ollama for model-status — already covered in Stage 6 as by-design).
- **TEST-S7-102** (`_fallback_readiness` last-resort branch) and **TEST-S7-103** (located-risk
  camelCase on the Python side) are defensive/edge coverage; the located-risk serialization is
  exercised by the frontend mock + the wiring agent live, and the readiness response shape is now
  pinned by TEST-S7-104. **UX-005** (assessment skeleton) is covered by the Stage-8.5 progress screen
  — the readiness arrives with the completed design, not as a separate async load in the card.
  **M-2/UX-007** (demo scenarios for engine/warn/low-confidence states) are QA-reachability n- to-haves
  noted for Stage 10's direct-print work; the states render correctly when reached (verified by
  injection).

## Round-2 re-audit
CLEAN — all actioned findings verified; false-green checks pass (UX-001 + the PP-table tests fail if
reverted); the readiness/gate authority boundary re-confirmed.

## Final verdict
**STAGE 7 BACKFILL: CLEAN — 0/0/0/0/0 across all five lanes + wiring-audit PASS.**
Gate green: ruff, geometry backends, 778 pytest (not-live), 284 vitest, SPA build reproducible.
