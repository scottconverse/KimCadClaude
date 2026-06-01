# Audit Lite — pre-Stage-4 documentation cleanup
**Date:** 2026-06-01
**Scope:** The three doc/working-tree fixes that resolve the prior Codex current-state audit (0/0/1/2/0) before branching Stage 4 — ROADMAP.md full rewrite, HANDOFF.md Stage-4 branch-name alignment, and removal of the stale audit directory from the working tree. Repo: `C:\Users\scott\dev\kimcad` on `main` @ `7683f12`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. The cleanup correctly resolves all three prior findings (DOC-001 ROADMAP, DOC-002 branch name, ENG-001 dirty tree), and the rewritten ROADMAP is consistent with HANDOFF §4 and the verified repo state (tags `stage-0..3`, HEAD `7683f12`, `ruff` clean, tree clean except the two intentional edits). Round 1 surfaced one genuine Nit: a terminology collision between "Kim is the beta tester" and labeling her phase "post-beta." Fixed; round 2 is clean.

## Severity rollup (round 1)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 1

## Severity rollup (round 2 — after fix)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0  → **0/0/0/0/0, gate cleared**

## Findings

### DOC-003 Nit: "beta tester" vs "post-beta" terminology collide
**Dimension:** Docs
**Evidence:** `ROADMAP.md` target section ("**Kim is the beta tester.** So *all* real-hardware validation … happens **only post-beta at Kim's**, after the Stage 11 beta gate") and the closing "## Post-beta — Real hardware at Kim's … **Kim is the beta tester**." Calling the phase "post-beta" while also calling Kim "the beta tester" is internally inconsistent — a beta tester tests *the beta*, not *after* it.
**Why it matters:** The next reader can't tell whether Kim's real-hardware phase *is* the beta or comes after it. The whole point of this cleanup is to remove handoff-ambiguity, so a self-contradictory label undercuts it. (Source HANDOFF §4 says "real-hardware = post-beta," meaning after the Stage 11 beta-readiness gate ships the installable build — so the precise model is: Stage 11 ships the v3.0 Windows beta; Kim then runs that beta on real hardware.)
**Fix path:** Make the model explicit — Stage 11's gate ships the installable v3.0 Windows beta; the Kim phase is that beta running on real hardware (post-Stage-11). Reword so "beta" usage is coherent and stays consistent with HANDOFF §4. **(Fixed in this pass — all five usages normalized: "beta tester" removed entirely, every literal "post-beta" replaced with "after Stage 11" / "post-Stage-11"; verified `grep` returns 0 "beta tester" and 0 literal "post-beta".)**

## What's working
- **ROADMAP ↔ HANDOFF consistency verified:** ROADMAP Stages 4–11 match HANDOFF §4 verbatim in scope (4 React SPA + viewport, 5 template engine + live sliders, 6 Qwen swap + tiered fallback, 7 Smart Mesh + PrintProof3D + report, 8 CadQuery, 9 image on-ramp opt-in, 10 direct-print + Bambu + first-run wizard, 11 installer + beta gate).
- **Repo facts verified, not assumed:** `git tag` → `stage-0..3`; `git log -1` → `7683f12`; `git status --short --branch` → clean except `M HANDOFF.md` / `M ROADMAP.md`; `ruff check src tests` → "All checks passed!". ROADMAP's "tagged `stage-3` @ `96aba02`" and "`ruff` clean" claims hold.
- **DOC-002 fully closed:** `git grep` for `stage-4-react-spa` not followed by `-shell` returns zero matches; the only occurrence is the corrected `stage-4-react-spa-shell` in HANDOFF.md:81.
- **ENG-001 fully closed:** the stale `_STALE-codex-audit-2026-06-01-SUPERSEDED/` directory was moved out of the repo (non-destructively, to a sibling) — accepted remedy per the prior audit; the working tree no longer carries the untracked artifact.
- **Stage 4 scope is honestly narrow** in the rewrite (read-only flow, vanilla Three.js, Workshop baseline, no Stage 5 template work) — matches Scott's directive.

## Watch items
- The "400 tests passing" claim in ROADMAP is consistent with the last recorded gate run at HEAD (`7683f12`) and no test files changed in this docs-only cleanup; it is re-confirmed by the mandatory full `ruff` + `pytest` run that gates this same cleanup push.
- `gemma4:e4b` / `Qwen2.5-Coder 1.5B` "per spec §7.5" citation is carried from HANDOFF §9 (canonical), not independently re-opened here — fine for a roadmap, but worth a glance when Stage 6 starts.

## Escalation recommendation
No escalation needed. Docs-only cleanup; one Nit, fixed; verified clean against the repo. audit-team is not warranted for this change.
