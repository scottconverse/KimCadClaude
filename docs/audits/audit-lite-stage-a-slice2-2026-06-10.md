# Audit Lite — Stage A Slice 2: honest wizard recap + landing model pill (UX-002)
**Date:** 2026-06-10
**Scope:** `FirstRunWizard.tsx` (step-4 recap reflects live model state, re-probes on entry, "Almost ready" + cause + in-place re-check when not ready; finishing never blocked), new `ModelHealthPill.tsx` on the Landing (warn-only pill: start-Ollama / pull-command lines + Check again; silent when healthy, on cloud, or when the probe itself fails), pill CSS.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. The recap can no longer claim "You're all set" with a dead model, and a down model is now visible on the Landing before the user invests a prompt. One real defect was found during the audit pass and fixed before commit (the headline flashed pessimistic during the step-entry re-probe); everything else checked clean.

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0** (one defect found mid-audit, fixed pre-commit, regression-covered by the existing last-known-state tests).

## Adversarial checks performed
- **Pessimistic flash on re-probe (FOUND + FIXED):** entering step 4 re-probes; `modelOk` originally required `modelState === 'ready'`, so the headline flashed "Almost ready" for the probe duration even when the model was fine. Fixed: `modelOk` derives from the last-known status (kept during re-probe); the quiet re-probe updates the headline only if the truth changed.
- **Stale pill on a long-lived Landing:** the pill probes on mount only — a user who starts Ollama later sees a stale warn until "Check again". Accepted: the re-check affordance is right there, and background polling on the landing would be noise; the design run itself now fails fast with the same guidance (Slice A1).
- **Probe-failure behavior:** an unreachable `/api/model-status` keeps the pill silent (don't cry wolf when the page itself is being served); tested.
- **Cloud backend:** pill silent, wizard recap treats cloud as self-managed; tested.
- **Finish never blocked:** "Start designing" remains available in the not-ready recap — the wizard informs, it doesn't trap; tested.
- **Live verification:** served demo app probed — healthy model ⇒ pill correctly absent; both new code paths present in the rebuilt committed bundle; byte-exact rebuild.

## Tests
8 new (3 wizard recap states incl. the pull-command copy; 5 pill states incl. re-check clearing). Vitest 297 passed, typecheck clean, SPA rebuilt + committed.

## Escalation recommendation
No escalation — scoped UI slice at zero findings.
