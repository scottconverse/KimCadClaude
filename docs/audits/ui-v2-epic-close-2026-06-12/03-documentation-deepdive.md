# 03 - Documentation Deep-Dive

## Scope

`README.md`, `ARCHITECTURE.md`, `docs/api.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `scripts/ci.sh`, `.github/COST_HYGIENE.md`, and the UI-v2 burndown/handoff trail.

## What's Working

- The docs accurately describe KimCad as local-first, loopback by default, no runtime Node, and explicit about cloud opt-in.
- The changelog and burndown have strong traceability for UI-v2 slices 1-6.
- The API reference covers the relevant public HTTP surfaces and error-shape conventions.

## Findings

### DOC-001 - Major - API Accuracy - Send endpoint heading named the wrong path variable

**Evidence:** `docs/api.md` documented `POST /api/send/<connector>`, while the shipped server and SPA call `POST /api/send/<rid>` with connector in the JSON body.

**Why this matters:** An API reader would build the wrong request path for one of the most safety-sensitive flows.

**Blast radius:**
- Adjacent docs: README and architecture already use `<id>`/`<rid>` correctly.
- User-facing: integrators and future tests using the API reference.
- Migration: none; documentation-only correction.
- Tests to update: none; existing API tests already exercise the true path.

**Fix path:** Fixed in `docs/api.md`, and the print-outcome guard behavior is now documented with its `409` response.

## Could Not Assess

Support-channel frequency was not reviewed; this pass used repo-local docs and issue handoff context only.
