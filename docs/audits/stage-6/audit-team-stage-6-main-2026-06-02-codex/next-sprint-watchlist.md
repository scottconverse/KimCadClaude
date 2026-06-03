# Next-Sprint Watchlist - KimCad Stage 6 current main

**Audit date:** 2026-06-02

## Structural / architectural

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | WATCH-001 | Engineering | If `alt_backend` becomes a recommended setup path rather than a power-user config, surface fallback/stickiness state in user-facing output, not only stderr/server logs. | Before documenting cloud fallback as a normal user path. |

## Design debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | WATCH-002 | UI/UX | Include a real rendered desktop + mobile slider-drag proof in the next UI-bearing audit. |

## Documentation debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | DOC-001 | Docs | Keep `HANDOFF.md` single-source: the first banner should never contain both "done" and "resume the old gate" language. |

## Test-culture debt

None surfaced.

## Performance and scaling

None surfaced.

## Dependency and supply chain

None surfaced; npm audit reported 0 vulnerabilities.

## Decisions needing product/leadership input

None for this pass.

