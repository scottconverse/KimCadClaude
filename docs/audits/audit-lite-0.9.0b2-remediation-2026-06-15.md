# Audit Lite — 0.9.0b2 second-pass remediation (commit `959761b`)
**Date:** 2026-06-15
**Scope:** Verify the remediation of the 0.9.0b2 second-pass audit (`docs/audits/audit-team-0.9.0b2-2026-06-14/`) is genuinely closed in the committed code (`4ea7282..959761b`), and that the fixes introduced no regression.
**Reviewer:** Claude (audit-lite)

## TL;DR
**Ships.** Every Blocker, Critical, and Major from the second-pass audit is closed in the committed tree, each with a test that fails without the fix, and the full authoritative gate is green on `959761b` (1597 pytest incl. live OpenSCAD/OrcaSlicer/CadQuery + the real-`qwen2.5:7b` landing canary; 393 vitest; SPA build-repro). This verification pass found **no new defects and no regressions**. The remaining items are the consciously-deferred watchlist the audit itself flagged forward — acknowledged below, none a shipping blocker.

## Severity rollup (new findings from this verification pass)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Closure verification (prior findings → state in `959761b`)

| ID | Sev | Closed? | Evidence in the committed tree |
|----|-----|---------|--------------------------------|
| DOC-001 | Blocker | ✅ | `docs/install-guide.md` checksum cmd names `KimCad-Setup-0.9.0b2.exe`; README badge/CTA/filename, USER-MANUAL banner, DoD all on `0.9.0b2`. Locked by `test_version_single_source` README-badge tripwire. |
| UX-001/TEST-001/QA-001/ENG-002 | Critical | ✅ | Landing chips recurated to dimensioned, family-mapped prompts (`Landing.tsx:14-18`); matcher containment fallback (`templates.py:335 _contains_alias`, exact/singular preserved); **real-model canary** `tests/test_landing_examples.py` ran live in the gate (3 `qwen2.5:7b` plans at 69/33/30 s, all mapped) + a deterministic CI check. |
| QA-002 | Critical | ✅ | `pipeline.py:107 _reject_non_code` (structural `name(...)`/`{}` necessary-condition) called before the render subprocess in `_run_one_backend`; `test_pipeline.py` proves fast-fail with renderer never invoked + the valid-codegen fixtures still pass. |
| DOC-002/ENG-003 | Critical | ✅ | `ARCHITECTURE.md` "Four jobs" / OpenSCAD-only codegen; removed-fallback framing gone (Remediation B). |
| DOC-003 | Critical | ✅ | `ARCHITECTURE.md` adds Duet/Marlin + mocks, the session-token guard, macOS/Linux paths. |
| UX-002 | Major | ✅ | `ChatPanel.tsx` gates geometric refine chips on `hasPart`; 2 vitest cases (failed design → chips hidden, input stays; real part → shown). |
| TEST-002 | Major | ✅ | `test_version_single_source.py` now scans the README badge against pyproject. |
| ENG-001 | Major | ✅ | `requirements.lock` bundles **both** `bambulabs-api` and `pyserial`; `test_build_installer.py::test_lock_bundles_both_connector_extras_symmetrically`; CONTRIBUTING regen procedure; ARCHITECTURE packaging policy. |
| ENG-004 | Major | ✅ | `webapp.py:719 design_slots = BoundedSemaphore(_MAX_INFLIGHT_DESIGNS)`, non-blocking acquire in the `/api/design` dispatcher, `429 + Retry-After` via `_busy`, `finally` release; `test_webapp.py` admission-cap test (cap pinned to 1, 2nd POST 429s, first completes). |
| UX-003 | Major | ✅ | `KCViewport.handleKey` (arrow orbit, ±  zoom, same clamps); focusable `<canvas>` + `onKeyDown` + focus ring (`styles.css`); aria-label advertises keys; 2 Viewport vitest cases. |
| DOC-004 | Major | ✅ | USER-MANUAL covers b2 + a `## Glossary` (DOC-007); model framing is qwen-as-default, gemma-as-fallback. |
| DOC-005 | Major | ✅ | `docs/index.html` honest landing page (correct `scottconverse/KimCadClaude` casing, qwen2.5:7b/qwen2.5vl:3b, 86 families, Duet/Marlin, version-agnostic CTAs); GitHub Pages enabled from `/docs` (live at https://scottconverse.github.io/KimCadClaude/). |
| DOC-006 | Major | ✅ | FAQ "about 90" → "86"; matches the test-backed `EXPECTED_FAMILY_NAMES` count. |
| ENG-005 | Minor | ✅ | `connectors.py:114 validate_printer_base_url` (http/https, host required, no userinfo) wraps the 4 HTTP connectors; Marlin/Bambu exempt; 3 `test_connectors.py` cases incl. the Marlin-exempt guard. |
| ENG-006 | Minor | ✅ | `webapp.py:1217` index shell served `no-store, no-cache, must-revalidate`, ETag/304 dropped for the token-bearing body; static assets keep their ETag. |
| ENG-007 | Minor | ✅ | CONTRIBUTING "Regenerating `requirements.lock`" section + the symmetry tripwire. |
| ENG-012 | Nit | ✅ | `ExportPanel.tsx` → `#/settings`; test updated. |
| DOC-009/010/011/013, DOC-012 | Minor/Nit | ✅ | README CTA version-neutralized (+ TEST-002 lock); CHANGELOG `[Unreleased]` reframed + remediation entries; ROADMAP `0.9.0b2` entry; DoD plan-gate wording softened (Rule-11 removal); ARCHITECTURE module-map table/paragraph bleed fixed; stage-6 bake-off superseded banner. |
| secondary model docs | Minor | ✅ | getting-started, troubleshooting, guide-settings pull-commands → `qwen2.5:7b`. |

Adversarial re-checks that came back clean: the matcher fallback is whole-word, multi-word-only, longest-wins (single-word aliases stay exact-only — `test_containment_does_not_hijack_single_word_aliases`), so it can't hijack `box`/`ring`; `_reject_non_code` accepts library-module-call output (`box(20,20,20);`) so it doesn't false-reject valid codegen; the admission gate releases in `finally` (no slot leak, no deadlock — non-blocking acquire); `validate_printer_base_url` leaves Marlin's serial/`host:port` target untouched. The full 249-case `test_templates`, 39-case `test_pipeline`, and 78-case `test_connectors` modules pass — no routing/codegen/connector regression.

## What's working
- **The verification is test-anchored, not asserted.** Every closed finding has a regression test that would fail without the fix, and all of them ran in the green gate (`959761b`) — including a *live-model* canary, which is the honest way to prove the default-model Critical (no demo-only blind spot).
- **The two security Minors are real hardening, scoped tightly** — the connector scheme allowlist closes the `file://`/`ftp://` class at the type-aware chokepoint without touching Marlin; `no-store` stops the per-boot token landing in a disk cache while leaving asset caching intact.
- **Honest deferral.** The watchlist below was not silently skipped — each item has a stated reason and (for ENG-009) is partially addressed by the matcher work.

## Watch items
1. **ENG-004 cap is conservative (`_MAX_INFLIGHT_DESIGNS = 2`).** Right for single-user loopback; revisit if a legitimate multi-tab/`--allow-remote` workflow ever needs more headroom (the 429 copy already guides a retry).
2. **ENG-009 is reduced, not eliminated.** The matcher broadening means fewer prompts dead-end at the experimental offer, but a genuinely-unmatched object_type still pays the plan latency first. The forward fix (surface a fuzzy near-match suggestion) remains a nice-to-have.

## Consciously deferred (acknowledged, not new findings)
Carried forward with reasons — none gates the beta:
- **ENG-008** (Minor) — CadQuery worker OS-level confinement. Structural watchlist; the experimental path is off by default and the static AST sanitizer is the documented layer-1 boundary. No code change needed to ship b2 (the audit said the same).
- **ENG-010** (Minor) — `real_print_sends` not cleared on registry eviction. Negligible bounded leak (≤ real sends per session); the fix needs a registry eviction callback out of proportion to the impact; audit rated it "do when next touching the registry."
- **ENG-011 / ENG-013** (Nit) — `experimental` absent-flag default; Marlin SD 8.3 truncation. Both documented, deliberate behaviors.
- **TEST-003** (Major→watchlist) — live-Ollama error-path tests. Needs a CI Ollama lane; the new landing canary is the first Ollama-gated test and runs on the dev box / any future lane.
- **TEST-004/005/006/007/008, QA-003/004, UX-004/005/006/007/008/009/010, DOC-008** — cosmetic/structural Nits and Minors (prior-audit-covered connector-mock parity, e2e xdist serialization, demo adversarial breadth, a 3.5k-line test file split, `toBeTruthy` style, demo-only non-image bytes, WebGL `readPixels` perf warnings, the 320px breakpoint, hue-only Settings cue, disabled-CTA copy, overlay contrast, part/design noun, the "TRY" eyebrow, the PDF manual — explicitly format-flexible per the owner). Each is logged in the original deep-dives; none is a regression or a shipping risk.

## Escalation recommendation
**No escalation needed.** This is a verification of a remediation whose code is already proven by the full gate; it surfaced zero new defects. The deferred set is forward-looking watchlist material, not this-sprint work — so a full `audit-team` re-run would not change the disposition.
