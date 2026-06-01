# Audit Lite — HANDOFF.md stale audit-path fix
**Date:** 2026-06-01
**Scope:** A one-finding corrective doc fix: HANDOFF.md §8 named the stale Codex-audit dir at an in-repo path (`...\kimcad\_STALE-codex-audit-2026-06-01-SUPERSEDED\`) that no longer exists; it was corrected to the actual sibling location (`...\kimcad-STALE-codex-audit-2026-06-01-SUPERSEDED`, outside the working tree). Branch `stage-4-react-spa-shell`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. The doc now matches the filesystem (verified by `ls` of both paths), and a repo-wide `git grep` confirms no remaining tracked doc asserts the dead in-repo path as a current location. Docs-only; nothing executable touched.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0 → **0/0/0/0/0**

## Dimensions checked
- **Docs:** the corrected §8 path vs. the real filesystem, plus a repo-wide sweep for other stale references.
- **Correctness/Security/UX/Runtime:** N/A — no source, test, config, or UI changed.
- **Tests:** N/A to add — a path string in a handoff doc has no unit under test; the build/serve tests are unaffected.

## Findings
None. The single underlying issue (a false asserted path — the exact class of trust-killer this cleanup addresses) is resolved, and the sweep found no others.

## What's working
- **Doc now matches reality, verified:** `ls` confirms `C:/Users/scott/dev/kimcad-STALE-codex-audit-2026-06-01-SUPERSEDED` EXISTS and the old `C:/Users/scott/dev/kimcad/_STALE-codex-audit-2026-06-01-SUPERSEDED` does NOT; HANDOFF.md §8 now points at the former and explicitly notes the latter no longer exists.
- **No remaining false path, repo-wide:** `git grep -E "STALE-codex|_STALE"` over all tracked files returns only (a) the corrected sibling path in HANDOFF.md and (b) the prior `docs/audits/stage-4-prep/...` report, which accurately records that the dir "was moved out of the repo … to a sibling" — a true point-in-time statement, deliberately left as history rather than rewritten.
- **Clean + green:** `git status` shows only HANDOFF.md modified; `ruff check src tests` passes. The change is docs-only, so the full `pytest` suite (398 passed incl. live this session) is unaffected and is re-gated by the pre-push hook on push.

## Escalation recommendation
No escalation needed. A correct, complete, single-line factual fix with a repo-wide verification sweep.
