# Audit Lite — Stage 8.5 Slice 6 MS-4: experimental generator gate + offer
**Date:** 2026-06-04
**Scope:** Gating the pipeline's LLM-OpenSCAD codegen fallback behind an opt-in — `PipelineStatus.needs_experimental` + `run(allow_experimental=...)` (`pipeline.py`), the web `allow_experimental` computation + the `experimental_enabled` setting (`webapp.py`, `settings_store.py`), and the frontend offer + Settings toggle. Safety weighted highest.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after one Minor fix (applied). The two load-bearing safety properties hold: the experimental path **never bypasses the printability gate** (codegen, when it runs, flows through the unchanged `_build_geometry` + gate), and a template miss in the consumer UI **offers** the generator rather than auto-running it. One Minor: the right panel showed a misleading "Size" for the offer state — fixed.

## Severity rollup
**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: the Parameters card shows a "Size" + "generated directly" line for the offer state
**Dimension:** UX
**Evidence:** `RightPanel.tsx` `ParametersCard` — for a `needs_experimental` result there are no `parameters` but the `plan` is present, so it falls into the `plan ?` branch and renders the bbox "Size: 80 × 60 × 40 mm" plus "No live sliders for this part — it was generated directly…". But no part was generated — it's an *offer*. (The Printability + Readiness cards already fall through to their idle placeholders, since the offer carries no `report` and isn't a failure status — only Parameters mis-renders.)
**Why it matters:** Implies a part exists when the viewport is empty and the chat is offering to try. A small honesty/consistency wart on a brand-new state.
**Fix path:** Treat `needs_experimental` as "no part yet" in `ParametersCard` — gate the `plan` branch on `result?.status !== 'needs_experimental'` so it shows the idle placeholder instead.
**Status:** ✅ Fixed — the Parameters plan-branch now excludes `needs_experimental` (idle placeholder shown); a RightPanel test asserts no "Size"/slider content renders for the offer.

## What's working
- **The gate is never bypassed (trust rule 4, load-bearing).** The new branch returns `needs_experimental` *before* `_build_geometry`, so it produces no geometry. When the generator IS allowed, the flow is unchanged — `_build_geometry` → render → printability gate → `_assemble_result`, with the gate verdict intact. A test asserts `openscad_calls == 0` on the offer (codegen genuinely didn't run) and `>= 1` when allowed. There is no path where the experimental codegen skips the gate.
- **`needs_experimental` carries no mesh.** `has_mesh = bool(result.mesh_path and result.mesh_path.exists())` and the offer returns no `mesh_path`, so `has_mesh` is false and no `mesh_url` is set — nothing unvalidated can be shown, sliced, or sent. Confirmed by a test (`not r.get("has_mesh")`).
- **No consumer auto-run (OFF by default, OFFERED).** The SPA's `postDesign` always sends `experimental:false` on a normal design; the handler computes `bool(data.get("experimental", True)) or settings.experimental_enabled`, so `false or (off)` → `needs_experimental` (the offer). The "default True when the flag is absent" only affects flag-less callers (raw API / CLI / older clients) — backward-compatible and analogous to the CLI's existing auto-run — and every SPA caller goes through `postDesign`, which always sends the flag. The full matrix is tested: false→offer, true→run, absent→run, setting-on→run-even-with-false.
- **No dead-end (§4.2).** The offer renders a "Try the experimental generator" button *and* the refine input stays available ("describe it differently") — two concrete next actions. The Try button re-runs the *same* attempt (prompt/history/fromVersionIdx, captured in `lastAttemptRef`) with `experimental:true`, without appending a duplicate user turn. `lastAttemptRef` is set on every `runDesign`, so it always matches the current offer (both produced by the same call) — no stale-attempt hazard.
- **Honest, untrusted-by-default UX.** The offer copy is honest ("may not be perfect", "locked sandbox", "still has to pass the printability check"); `needs_experimental` is not in `FAILURE_STATUSES`, so it gets no error tone. The Settings toggle is badged "Experimental · Untrusted", off by default, with an on/off explainer and the sandbox/never-skips-the-check copy. a11y: `role="switch"` + `aria-checked`, a real `<button>` for the offer.
- **Backward-compatible + non-vacuous tests.** The pipeline default `True` preserves every pipeline + CLI + existing HTTP test (140 backend pass). The new tests pin the gate (no codegen on the offer), the consumer/API/setting matrix, the offer render + Try wiring, and the toggle.

## Watch items
- **API default-on is deliberate (document at stage close).** A raw `/api/design` POST with no `experimental` flag auto-runs codegen (backward-compat for the API/CLI/MCP). The consumer UI is unaffected (the SPA always sends the flag). Worth a one-line note in the API/ARCHITECTURE doc at stage close so a future reviewer doesn't read it as a consumer auto-run.
- **The Try-result paths reuse existing statuses** — a rough experimental part can come back `render_failed` or `gate_failed`, which the chat already handles with their own messages (no dead-end after Try). Verified by inspection; the live wiring-audit should click Try end-to-end.

## Escalation recommendation
No escalation needed. The two safety properties (never bypass the gate, no consumer auto-run) hold and are tested; one Minor (offer-state right panel) fixed. The slice-end audit-team + wiring-audit (after MS-5) remain the gate, and the wiring-audit should exercise the offer → Try flow live.
