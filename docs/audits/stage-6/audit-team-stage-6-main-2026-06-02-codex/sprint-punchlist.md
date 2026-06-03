# Sprint Punch List - KimCad Stage 6 current main

**Audit date:** 2026-06-02

## Must-fix (Blockers + Criticals)

None. This fresh audit found no Blockers or Criticals.

## Should-fix (high-leverage Majors)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | DOC-001 | Major | Documentation | Remove the stale `RESUME HERE = Stage 6 gate` instruction and stale counts from the top `HANDOFF.md` Stage 6 banner; make it point only to Stage 7. | S |

## Suggested sequencing

Fix DOC-001 first because it is cheap, isolated, and sits in the first-read handoff surface. Then run `audit-lite` on the doc-only fix to confirm the handoff no longer has a split-brain Stage 6 state.

## Items deferred to next sprint

- Slider rendered pointer/mobile proof belongs in the next UI-bearing stage audit, not as a Stage 6 code fix, because the backend/API path and component tests are already green and Browser automation was inconclusive rather than product-failing.

## Sign-off gate

- [ ] DOC-001 fixed.
- [ ] `audit-lite` run on the doc-only fix.
- [ ] Working tree remains clean after any verification/build commands.

