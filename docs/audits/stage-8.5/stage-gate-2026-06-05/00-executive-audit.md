# KimCad — Stage 8.5 (Usability) Stage-Gate Audit — Executive Report

**Date:** 2026-06-05 · **Branch:** `stage-8.5-usability` @ `95b25e0` (pre-merge to `main`, pre-tag `stage-8.5`)
**Lanes run:** runtime `wiring-audit` (PASS 0/0/0/0) + full 5-role `audit-team` (this package) · Posture: balanced · Writer: audit-only

## Executive summary
Stage 8.5 turned KimCad's core loop into a tool people keep, and it is fundamentally sound: every
load-bearing safety invariant holds (verified in code AND at runtime), persistence and the
deterministic re-render are genuinely wired, the test culture is mature and honest, and accessibility
is strong. There are **no Blockers and no Criticals.** The work to close before this stage is shown
as "done" is concentrated in two places: (1) **UI fidelity + discoverability** — several high-value
designed surfaces (the accent-tinted readiness/report cards, the icon-tile printability checks,
in-viewport refine chips, the printer-status chip) were flattened or dropped versus the reference
prototype, and the new keyboard/refine features are wired but hard to find; and (2) **two real
correctness/safety gaps on the gate path** (a slice/re-render lock race, and reopen/import trusting a
stored gate verdict without re-gating). Plus doc-lag in two files and a CI-coverage process gap.

## Severity roll-up (all roles)
| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 11 |
| Minor | 22 |
| Nit | 11 |
| **Total** | **44** |

Per role: Engineering 0/0/2/4/1 · UI-UX 0/0/6/9/5 · Docs 0/0/2/4/3 · Test 0/0/1/3/1 · QA 0/0/0/2/1.

## Top findings (by severity, across roles)
1. **UX-001 (Major):** Workspace right column is four identical flat sand cards — the reference's accent-tinted readiness/report hierarchy is gone, so the verdict carries no visual weight. (`RightPanel.tsx`, `styles.css:803`)
2. **UX-002 (Major):** Printability card flattened from designed icon-tile checks (✓/⚠ + label/detail) to a bare bullet list; in-card Material control dropped. (`RightPanel.tsx:528`)
3. **UX-003 (Major):** In-viewport refine chips ("Make it wider"…) + orientation "change" action from the reference are missing — refine-by-talking is a bare box with a vanishing placeholder. (`ChatPanel.tsx:240`, `Viewport.tsx:167`)
4. **UX-004 (Major):** Stacked mobile workspace buries the readiness verdict + Slice/Download below a ~42vh viewport; no in-page nav/sticky CTA. (`styles.css:460`)
5. **UX-005 (Major):** Keyboard shortcuts built + polished but undiscoverable — no visible "?" entry point. (`App.tsx`, `Topbar.tsx`)
6. **UX-006 (Major):** Topbar dropped the always-on printer-status chip (build-volume cue) the reference centered on. (`Topbar.tsx`)
7. **ENG-001 (Major):** Slice and re-render of the same `rid` use different locks (`slice_lock` vs `render_lock`); a slice can register pre-reshape G-code after a re-render invalidated the cache → a stale-geometry slice could be served/sent. Low exposure (single-user SPA) but it's the one real hole in the re-render-invalidates-slice invariant. (`webapp.py:1564-1565` vs `1671-1687`)
8. **ENG-002 (Major):** Reopen/import trusts the stored `gate_status` and never re-gates the mesh — a crafted `.kimcad` import could mark an unprintable mesh gate-passed + sliceable. (`webapp.py:1464`, `design_store.py:269-297`)
9. **DOC-001 (Major):** `HANDOFF.md` "Backend API contract" still calls itself "the unchanged seam" and lists only Stage-4 routes — omits the ~14 endpoints Stage 5–8.5 shipped. (`HANDOFF.md:306-317`) (ARCHITECTURE.md is correct.)
10. **DOC-002 (Major):** `docs/design/README.md` still tags Qwen "RECOMMENDED" (:147), defaults the photo on-ramp to cloud OpenRouter vision (:157), and encodes `model: qwen|gemma|cloud` (:204) — contradicts the settled gemma4:e4b-only / local-vision posture (a load-bearing rule). The build-to-this fidelity target points future work at the wrong posture.
11. **TEST-001 (Major):** Hosted CI is a disabled Linux-pytest-only smoke check; the 249-test frontend layer + SPA build-reproducibility are gated ONLY by a per-clone local Windows pre-push hook — a UI/build-drift regression ships green on any machine without the hook armed. (`.github/workflows/ci.yml`)

## What's working well (credited, specific)
- **All safety invariants hold** — local-first/cloud-off/key-masked; gemma4:e4b the only UI default; gate-failed never sliced/sent (server-enforced, proven live); `confirm is True` identity; deterministic re-render; sandboxed experimental codegen; honest "estimated"/"simulated" labels. (Engineering + QA + Test concur.)
- **Genuinely wired, not cosmetic** — the wiring-audit drove design→render(no-model)→slice→download→save and proved persistence round-trips the slider-modified state.
- **Mature, honest test suite** — 757 Python (incl. real-renderer cache-invalidation) + 249 vitest = 1006 passing; adversarial persistence coverage (traversal/zip-slip/oversized/threaded); tests pin bug-IDs; no sleep-based flake.
- **Strong accessibility foundation** — real focus traps + focus restore in both modals, SR-only severity words, reduced-motion honored, disciplined aria-live, 44px touch targets.
- **Best-in-class CHANGELOG + ARCHITECTURE**, current to Stage 8.5; the new My-Designs guide + glossary are genuinely plain-English.

## This-sprint punch list
See `sprint-punchlist.md`. Per the project mandate, **every finding (Major→Nit) is fixed this gate**, re-audited to 0/0/0/0/0, before merge + tag.

## Next-sprint watchlist
See `next-sprint-watchlist.md` (forward-looking structural items that are not gate-blockers).

## Blast-radius notes (fixes that ripple)
- **ENG-001 (shared per-rid lock / geometry version stamp):** touches the slice/render/send paths and the cache eviction — regression-test the idempotent-slice + re-render-invalidates-slice + concurrent-slice tests after the change.
- **ENG-002 (re-gate on reopen/import):** changes the reopen/import responses to carry a freshly-computed gate_status; regression-test reopen of a known-good design (still passes) and import of a tampered file (now refused/flagged). Coordinate with the designs-store schema.
- **UX-001/002/009 (restore right-column hierarchy):** CSS + component structure on the shared `.kc-card` family — verify no regression to the InfoTip anchors, the gauge, the dims table, and the print-summary that live in those cards; re-run the rendered desktop+mobile checks.
