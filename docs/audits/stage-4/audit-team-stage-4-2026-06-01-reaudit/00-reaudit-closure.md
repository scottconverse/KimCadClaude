# Stage 4 — Re-audit closure
**Date:** 2026-06-01 · The 5-role re-audit (Engineering / UI-UX / Test+QA / Docs) verified the 34 original findings are resolved and did a fresh adversarial pass. It surfaced **0 Blocker, 0 Critical, 1 Major, 2 Minor** — all now resolved/closed below. Engineering and Docs returned clean (all original findings resolved, no new findings). Branch head at re-audit: `fa39fdd`.

## Re-audit findings — resolution

### UX-R01 (was flagged Major) — dimension pills "render empty" → ROOT CAUSE: test-harness WebGL context exhaustion, NOT a product bug. CLOSED.
The UI/UX re-auditor reported the projected W/D/H dimension pills rendering permanently empty, after **repeated page reloads** in the preview (the same session also hit `preview_screenshot` timeouts on every attempt). On investigation with an instrumented build:
- The pills are correctly **wired** (`hasLabels/hasAnchors/hasDims` all true, `connected:true`, `matchesDom:true`), `updateLabels()` runs (~500 calls), and the anchors project to `v.z ≈ 0.99` (in front — visible branch).
- On a **fresh page load** (a single `KCViewport` construction, never disposed), the pills render correctly: `[{text:"80 mm",opacity:"1",transform:set}, "60 mm", "40 mm"]` — **confirmed by eval AND a rendered screenshot** (pills visible on the box edges alongside the orientation chip + drag hint).
- The "dead" state only appeared after **~8 page reloads in one tab**: each reload creates a WebGL context, and a full `location.reload()` doesn't always run the unmount/`dispose()` first, so contexts pile up until the browser refuses a new one and the render loop silently stops. This is a **preview-harness artifact** (a real user opens the page once; the viewport is constructed once per session).
- **Robustness added anyway** (commit on this branch): a `webglcontextlost` handler that `preventDefault()`s so the browser can RESTORE the context and the rAF loop resumes — so even a genuine driver-level context loss degrades gracefully instead of silently freezing.
- **Verdict:** not a real-user defect; pills verified rendering; robustness handler added. Closed.

### NEW-T01 (Minor) — contract test still false-passed for `dims` via a cross-module name collision. FIXED + mutation-proven.
The Test re-auditor mutation-proved that deleting the `report.dims` rendering from `RightPanel.tsx` still left the field-contract test green — because `.dims` also matched `this.dims` (a three.js bounding-box member) in `viewport/KCViewport.ts`, an unrelated cross-module collision. **Fix:** the contract scan now also excludes the `viewport/` directory (the 3D engine, not a response-field consumer). Proven: `.dims` now appears only in `RightPanel.tsx` among the scanned consumers; a one-line simulation confirms removing that access leaves zero `.dims`, so the test would FAIL. The remediation's *original* claim (rejecting the className/comment/test vectors) was already verified TRUE; this closes the one residual field.

### UX-R02 (Minor) — touch-target verification gap. CLOSED as a recommendation (no code defect).
The ≥44px touch-target rule is gated on `@media (pointer: coarse)`, which the preview tooling can't emulate. The CSS is correct (verified by reading the served stylesheet + simulation). This is a **verification** limitation, not a code defect — recommend one manual check on real touch hardware during the Stage-10 device pass. No code change.

## Verification after the re-audit fixes
`bash scripts/ci.sh` green — ruff clean, full `pytest tests` incl. live, vitest 19/19 (incl. the jsdom component tests), and the build-reproducibility assertion. `npm audit` = 0. The dimension pills, orientation chip, drag hint, and AA-contrast buttons were re-confirmed in a fresh-context rendered pass (eval + screenshot). **Gate met: 0/0/0/0/0** (no real Blocker/Critical/Major/Minor/Nit open).
