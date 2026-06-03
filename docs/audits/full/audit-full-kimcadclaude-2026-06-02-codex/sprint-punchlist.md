# Sprint Punch List - KimCadClaude full project

**Audit date:** 2026-06-02

## Must-fix (Blockers + Criticals)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | DOC-001 | Critical | Documentation | Rebaseline the controlling v3.0 spec so it does not point to missing companion docs, does not reopen the rejected qwen default, and does not contradict the repo stage plan. | M |

## Should-fix (high-leverage Majors)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | DOC-002 | Major | Documentation | Remove the stale Stage 6 `RESUME HERE` gate instruction and stale counts from `HANDOFF.md`. | S |
| 2 | TEST-001 | Major | Test | Make hosted CI match the documented local gate or correct docs to say hosted CI is partial/non-authoritative. | M |

## Suggested sequencing

Fix DOC-001 first because it decides the truth source for all later work. Then fix DOC-002 as the resume-specific cleanup. TEST-001 can follow, but should land before any future claim that hosted GitHub checks are an authoritative release gate.

## Items deferred to next sprint

- Rendered desktop/mobile slider-drag proof should be part of the next UI-bearing stage audit.
- Cloud fallback disclosure belongs with any future user-facing model/settings work.

## Sign-off gate

- [ ] DOC-001 fixed and `audit-lite` re-run.
- [ ] DOC-002 fixed and verified against `HANDOFF.md` first viewport.
- [ ] TEST-001 either fixed in CI or corrected in docs.

