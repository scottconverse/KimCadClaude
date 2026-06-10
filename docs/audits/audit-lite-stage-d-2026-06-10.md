# Audit Lite — Stage D: UX polish + version-story normalization
**Date:** 2026-06-10
**Scope:** UX-001 (landing draft preserved through first-design cancel/failure, with the "picked up where you left off" note), UX-005 (confirm only for genuinely-unsaved in-flight work), UX-003 (warn→proceed bridge on the Readiness card + a caution echo beside the enabled Slice button), UX-008 ("Gate:" jargon removed from the trust moment), UX-009 (the Printability card states its relationship to the score), UX-006 (Enter/Shift+Enter hint), UX-007 (thinking-row taken out of the polite live region; fuller scoping documented as measure-first), UX-010 (photo-discard line closes the privacy loop), UX-011 (friendly model name leads the slug), UX-013 (chips made universal). DOC-006/QA-010: Python **3.13** as THE supported line (`requires-python = ">=3.13"`, README Requirements + platform table, config comment, CadQuery worker/runner docstrings and doc rewritten — the process boundary is now correctly framed as security isolation, not a version workaround). DOC-007/008 stale paths fixed; ARCHITECTURE "Four jobs"→five drift fixed.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. The cross-cutting "am I OK to proceed?" theme from the original audit is closed at all three seams (cancel, all-set, warn-but-sliceable), and the project now tells one consistent Python story: 3.13, with the CadQuery process boundary justified by the real reason (sandbox isolation) rather than the obsolete one (wheel availability).

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**

## Adversarial checks performed
- **UX-005 false-nag risk:** the confirm predicate requires *unsaved + in-flight/no-version* — a completed design (which always has a version) never nags, pinned by the no-nag test; the existing supersede test was updated to accept the new confirm (it tests supersede mechanics, not the dialog).
- **UX-001 draft lifecycle:** the draft clears only on a successful design (not on cancel/failure), so a hard failure that bounces to the landing also re-seeds; a SECOND visit to the landing after success shows a clean box (cleared) — no stale "picked up" note.
- **UX-007 scope discipline:** only the thinking-row left the live region (it re-announced on every busy render); the log's polite semantics are otherwise untouched, and the deferral of deeper changes to a real SR session is documented in-code — blind live-region surgery risks regressions the audit itself warned about.
- **requires-python tightening:** the venv (3.13.13), CI (`py -3.13`), and lockfile all already satisfy `>=3.13`; the editable re-install in the pre-push gate re-validates it. Historical docs (CHANGELOG stage-8 entry, ROADMAP/HANDOFF completed-stage records, dated audit reports) keep their as-of-then "3.14" statements — records aren't rewritten; every *current-facing* surface now says 3.13.
- **UX-008 regression surface:** the compare-card already used the bare verdict vocabulary; the one test pinning `Gate: Passed` was updated to pin the *absence* of the jargon.
- **UX-012/014 closure note:** UX-014 was verified-no-issue by the original audit; UX-012's stated fix path is "acceptable as-is" (glyphs are aria-hidden with SR words) — both close by verified acceptance, recorded here.

## Tests
3 new (cancel-preserves-prompt, confirm-respects-no, no-nag-when-saved) + 2 updated; vitest **300**, pytest **907**, ruff clean, typecheck, byte-exact SPA rebuild.

## Escalation recommendation
No escalation. Stage B/C/D are now feature-complete → proceed to the stage gate (walkthrough + audit-team).
