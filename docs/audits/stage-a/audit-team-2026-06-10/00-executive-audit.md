# Executive Audit — Stage A stage gate (first-run hardening)

**Date:** 2026-06-10 · **Scope:** the Stage A diff (414d22a..5aad7f3: Slices A1/A2/A3 + CI retarget + UX-004) · **Posture:** balanced · **Roles:** all five
**Companion:** the live walkthrough (docs/audits/walkthrough-stage-a-2026-06-10/) whose WALK-A-001/002 the roles verified.

## Executive summary
Stage A's core promises hold at runtime — the 4-minute-traceback first-run is now a ~20-second friendly failure on every surface, verified against a genuinely stopped Ollama. But the gate caught real gaps the slices missed: the port-in-use guard is unreachable on Windows for its own headline case (and its test manufactures the very condition the bug avoids — the one Critical); the new fail-fast probe mis-treats cloud backends; `bench`/`bakeoff`/photo-seed/sketch-seed never got the Slice-A1 error mapping; a never-fetched OrcaSlicer still fails with a raw path because profile resolution outruns the binary guard; the new status UI is unreliable for screen-reader users; and the getting-started doc walks a non-developer straight into GitHub's ZIP-nesting trap. Nothing here invalidates the stage's direction — every finding is a missed *edge of the same contract*, and all are mechanically fixable.

## Severity roll-up
| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 14 |
| Minor | 17 |
| Nit | 10 |
| **Total** | **42** |
ENG 0/0/5/4/3 · UX 0/0/2/5/2 · DOC 0/0/3/2/2 · TEST 0/1/1/4/1 · QA 0/0/3/2/2

## Top findings (full detail in the role deep-dives)
1. **TEST-001 (Critical)** + **ENG-001 (Major)** — the QA-006 guard never fires python-vs-python on Windows (SO_REUSEADDR double-bind) and its test passes by manufacturing an `SO_EXCLUSIVEADDRUSE` bind error. Fix: `allow_reuse_address = False` server class + a real double-`serve()` regression test.
2. **ENG-003 (Major)** — `_server_reachable` TCP-probes the **cloud** host for cloud backends: proxy-only networks lose the whole retry budget; CDN-fronted hard failures keep it. Probe only local/loopback hosts.
3. **QA-A-001 (Major)** — `bench`/`bakeoff` swallow model-down per case: raw SDK class names, no guidance, **exit 0** on a 0/N run.
4. **QA-A-002 (Major)** — missing OrcaSlicer surfaces as `no_profile` + a raw filesystem path (profile resolution precedes the binary guard) — QA-003's friendly message is unreachable.
5. **QA-A-003 (Major)** — photo/sketch-seed with model down returns 422 "try a clearer shot" — blames the user's photo for a down server.
6. **UX-A-001/002 (Major×2)** — "Check again" unmounts under the user's finger (focus drops; wizard Tab can escape the trap) and the `role=status` regions mount with content / clear silently — SR users likely never hear any of it. One coordinated persistent-status-container fix.
7. **ENG-004/ENG-005 (Major×2)** — CI: powershell steps only fail on the last command; the no-green-by-skip step prints but never asserts; `pull_request` trigger on a self-hosted dev-box runner is a fork-RCE the day the repo goes public.
8. **ENG-002 (Major)** — SDK `max_retries=2` stacks under our loop (verifies WALK-A-002).
9. **DOC-001 (Major)** — getting-started's ZIP step lands the user in the `kimcadclaude-main\` nesting trap with no troubleshooting entry.
10. **DOC-002/003 (Major×2)** — ARCHITECTURE.md drifted (retry policy, missing errors.py, typed web errors) and CHANGELOG has no Stage A entry at the Stage A gate.

## What's working (consensus across roles)
- The fail-fast contract proven live on real infrastructure: 21.2s CLI / 18.5s web vs 234s before, friendly on every measured surface, zero tracebacks, zero console errors.
- Single-source error copy (CLI/web parity via `_is_model_unreachable` + shared message) held up under adversarial probing.
- Test hermeticity is now complete (probe pinned both directions); stub-binary refactors preserved test intent; leak tests assert both directions.
- The docs' executable claims verified true (ports, commands, pins, the 2.3.2 story, anchors) — the gaps are coverage, not honesty.

## Remediation (this gate — all 42 to zero, per the standing rule)
Grouped: (1) server/provider correctness + CI integrity; (2) error-path completeness (bench/bakeoff, slice-binary order, photo-seed, configurable model name in advice); (3) a11y persistent-status pattern + contrast/underline + dead class; (4) docs (ZIP trap, ARCHITECTURE drift, CHANGELOG, scope-of-delete, web string in troubleshooting, ASCII-safe CLI punctuation per QA-A-004); (5) regression tests for every fix. Then re-walkthrough + re-audit → push → tag `stage-a`.

---

## Remediation addendum (same date) — gate CLOSED at 0/0/0/0/0

All 42 findings remediated and re-verified:
- **TEST-001/ENG-001/WALK-A-001:** `_ExclusiveBindServer` (allow_reuse_address=False on win32) + a real double-bind regression test; **re-verified live** — a second `kimcad web` on an occupied port now exits 2 with the friendly `--port` hint (python-vs-python, the real case).
- **ENG-002/WALK-A-002/TEST-003:** `max_retries=0` on the built client + pinning test; **re-timed live: 10.4 s** model-down CLI failure (was 21.2 s at the walkthrough, 234 s pre-Stage-A).
- **ENG-003:** the probe never judges non-loopback hosts (cloud/LAN keep the full retry budget) + tests.
- **ENG-004/TEST-002:** every CI step strict (`$ErrorActionPreference='Stop'` + per-command exit checks); the no-green-by-skip step now EXECUTES `-m live` and fails on any skip or zero-executed.
- **ENG-005:** `pull_request` trigger removed (self-hosted fork-RCE guard, documented in the workflow header).
- **QA-A-001:** bench/bakeoff re-raise model-down → friendly exit 2 (test added). **QA-A-002:** binary check precedes profile resolution in all three slice paths (webapp + pipeline + CLI intent line; ordering test added). **QA-A-003:** photo/sketch-seed map model-down to typed `model_unavailable` (server + SPA; test added). **QA-A-004:** ASCII-safe CLI phase labels + port message.
- **UX-A-001/002:** persistent live regions everywhere (pill + wizard step-1 + recap); "Check again" stays mounted/focused while checking (aria-disabled no-op) and recovery is announced; focus-retention + announcement tests added. **UX-A-003:** recovery advice names the CONFIGURED model. **UX-A-004/005/007:** pill text on --kc-warn-text (AA), links underlined in warn surfaces, recap warn styled with the amber dot.
- **DOC-001..005 + DOC-009 residue:** ZIP-nesting walkthrough + troubleshooting entry, ARCHITECTURE retry-policy row + errors.py row, CHANGELOG Stage A entry, web pull-message wording, scope-of-delete corrected.
- Minors/Nits across roles: phase-printer dedupe test, NotFoundError branch test, probe-race fix (port 1), vacuous-silence assertions tightened.

Full verification after remediation: ruff clean · **883 pytest passed** (incl. live) · **297 vitest** · typecheck · byte-exact SPA rebuild · live re-walkthrough of both headline fixes.
