# Executive Audit — Stage B/C/D stage gate (gate depth · trust boundary · UX polish)

**Date:** 2026-06-10 · **Scope:** the B/C/D diff (3bb1226..5a07381) · **Posture:** balanced · **Roles:** all five
**Companions:** the live walkthrough (docs/audits/walkthrough-stage-bcd-2026-06-10/ — the keyring chain verified end-to-end against the real Windows vault) and the three per-stage audit-lites.

## Executive summary
The three stages' substance held up under five-role scrutiny and live adversity — the QA role hammered the keyring chain with sentinel-collision keys, kilobyte keys, unicode keys, and 50 parallel writes on a live isolated server and the at-rest contract never cracked. What the gate caught was the *edges*: a real lost-update race in the migration path (read outside the lock, amplified by per-request store construction), an importable-but-broken-vault disclosure gap, a BOM'd settings file silently blocking the migration, a native `window.confirm` in an app that owns better patterns, a doc promising a key-deletion gesture the UI didn't have, and the one current-facing surface the 3.13 sweep missed. **0 Blocker / 0 Critical / 7 Major / 20 Minor / 10 Nit — all 37 remediated this gate.**

## Severity roll-up (as found)
| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 7 |
| Minor | 20 |
| Nit | 10 |
| **Total** | **37** |
ENG 0/0/1/4/4 · UX 0/0/2/6/2 · DOC 0/0/2/3/1 · TEST 0/0/2/5/2 · QA 0/0/0/2/1

## The Majors (and their fixes — all landed this gate)
1. **ENG-101** migration race → the whole read-migrate-write now runs under `_WRITE_LOCK`, once per path per process; concurrency + BOM + rollback tests added.
2. **UX-101** native `window.confirm` → the app's own `ConfirmDialog` (focus-trapped `alertdialog`, Escape cancels, safe-action default), survives the WebView2 future; tests drive both buttons.
3. **UX-102** note-stacking → the photo card's two privacy lines merged into one complete promise (read locally + not saved).
4. **DOC-D-001** phantom key-deletion gesture → a real **Remove** button shipped (posts `openrouter_api_key: null`, wipes the vault), guide updated to match, vitest added.
5. **DOC-D-002** ARCHITECTURE's two "runs on 3.14" rows → rewritten to the 3.13 + security-isolation story (and HANDOFF's resume box, DOC-D-005).
6. **TEST-001** binary-gated tests invisible to the no-green-by-skip guard → `KIMCAD_CI_STRICT=1` in CI makes ANY skip in the full provisioned-runner suite fail the gate (`ci.sh`).
7. **TEST-002** untested disclosure chain → pytest pins `/api/settings` carries `key_storage`; vitest renders the Settings note for both values + the Remove flow.

## Minors/Nits — all 30 closed
Highlights: vault rollback on failed saves (ENG-102) + test; lockfile regenerated BOM-free/sorted (ENG-103); `AUTH`/`PASSPHRASE` scrub segments (ENG-104); explicit start-over clears the draft (ENG-105/UX-103) + the "picked up" note hides on edit (UX-108); landing Enter-submit + hint (UX-104); friendly-name-first in Settings (UX-105); wizard fallback note carries the risk sentence (UX-106); engine chip explanation became a keyboard-reachable InfoTip (UX-107); the redundant Gate tip removed and its consequence folded into the Printability tip (UX-109, with the InfoTip/RightPanel tests migrated); grow/shrink chips symmetric (UX-110); broken-vault health probe drives honest pre-save disclosure (QA-D-001/ENG-109) + test; `utf-8-sig` reads (QA-D-002) + test; reserved-sentinel keys refused at store AND API with 400 (ENG-106/QA-D-003) + tests; troubleshooting gained the file-fallback entry (DOC-D-003); the five-jobs row labels Stage 9 Slice 1 correctly with consistent dashes (DOC-D-004/006); the stale wheel comment dropped (ENG-107); photo-routing test strengthened to the transport layer (TEST-003); settings concurrency/failure paths tested (TEST-004); worker hermeticity pinned statically (TEST-007); open-mesh assertions made concrete (TEST-008); the no-nag test reframed honestly (TEST-009); Stage-D UX changes gained tests (TEST-006 — confirm both paths, draft clearing, Enter contract).

## What's working (consensus)
- The at-rest contract survived genuine adversity: sentinel-collision/1000-char/unicode keys round-tripped byte-exact, 50 parallel POSTs left a coherent sentinel'd file, reset wiped the real (isolated) vault — live.
- `--allow-remote`'s refusal AND accept paths verified live; no bypass found beyond the documented programmatic import.
- The scrubbed OpenSCAD env provably strips planted secrets while rendering keeps working (live demo design + re-render with a planted key).
- Doc claim-accuracy: every guide claim traced to code in the same commits; the walkthrough's vault evidence was independently re-verified by the roles.

## Verification after remediation
ruff clean · **915 pytest** (24 new this remediation) · **305 vitest** (8 new) · typecheck · byte-exact SPA rebuild · settings/trust/webapp suites re-run green.

## Watchlist (forward)
- The `KIMCAD_CI_STRICT` gate's first CI run will prove the zero-skip claim on the provisioned runner — watch it.
- UX-102's deeper two-tier note vocabulary (the systemic fix) is design-system work for the Stage 11 polish pass; the acute duplication is resolved.
- Real-WinVault behavior for >2.5 KB keys remains statically reasoned (the fallback handles it); revisit only if OpenRouter ever issues giant keys.
