# Next-Sprint Watchlist - KimCadClaude full project

**Audit date:** 2026-06-02

## Structural / architectural

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | WATCH-001 | Engineering | Decide whether repo tag stage numbering or v3.0 spec stage numbering is authoritative going forward. | Before Stage 7 begins. |

## Design debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | WATCH-002 | UI/UX | Include a real desktop + mobile rendered slider-drag proof in the next UI-bearing audit. |

## Documentation debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | DOC-001 | Docs | Keep the v3.0 spec, design handoff, ROADMAP, HANDOFF, and README aligned as one control plane. |

## Test-culture debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | TEST-001 | Test | Treat hosted CI as partial until it proves frontend/build/live-slicer gates. |

## Performance and scaling

None surfaced in this pass.

## Dependency and supply chain

Consider adding Python dependency CVE scanning (`pip-audit` or equivalent) before the installer/beta gate.

## Decisions needing product/leadership input

- Whether the missing `docs/spec` companion-doc package should be restored, created, or explicitly retired.
- Whether hosted CI should become authoritative before GitHub Actions minutes are reliable.

