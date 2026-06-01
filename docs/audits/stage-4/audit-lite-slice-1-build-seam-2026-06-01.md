# Audit Lite — Stage 4, Slice 1: Vite/React/TS build→serve seam
**Date:** 2026-06-01
**Scope:** The build→serve seam only — a new `frontend/` React+TS+Vite app that compiles to committed static files under `src/kimcad/web/`, served by the existing stdlib Python server via a new `/assets/` route. Branch `stage-4-react-spa-shell`. (Design system, panels, viewport, and flow wiring are explicitly later slices and out of scope.)
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. The seam is correct and safe: the `/assets/` route's path-traversal guard is character-identical to the already-audited `/vendor/` guard, the build is reproducible and documented, the committed output is internally consistent, docs match the code, and the full suite + ruff + `npm audit` are green. No defects found at any severity. Three forward-looking watch items (all scheduled for later slices) are recorded so they don't get lost — none blocks this slice.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

→ **0/0/0/0/0 — gate cleared.**

## Dimensions checked
- **Correctness & Security:** the `/assets/` route + traversal guard — checked in depth (below).
- **Tests:** the test rewrite + net count — checked; the server-level serve test is a real runtime smoke (live socket).
- **Docs:** ARCHITECTURE.md / README.md / frontend/README.md vs. actual code — checked.
- **Runtime:** verified via `test_serves_spa_index_and_assets_and_rejects_traversal` (real `ThreadingHTTPServer`, real GET `/` + `/assets/*` + traversal probes) and the full suite.
- **UX:** N/A — this slice renders a deliberately minimal shell; the design system and interactions are Slices 2–5.

## Security review — the `/assets/` route (the one new attack surface)
The guard at `webapp.py:408` is **character-identical** to the audited `/vendor/` guard at `:394`:
`if not name or "/" in name or "\\" in name or ".." in name:`. I probed the bypass classes:
- **Encoded separators / dots** (`..%2fx`, `%2e%2e%2f…`): the route reads `urlsplit(self.path).path`, which does **not** percent-decode, so `%2f`/`%2e` reach the filesystem as literal filename characters → no such file → 404. (`..%2fx` is additionally caught by the `..` check.) The new `test_serves_spa_index_and_assets_and_rejects_traversal` asserts exactly this set.
- **No separator ⇒ no escape:** with `/`, `\`, and `..` all rejected, a passing `name` is a single path segment, so the lookup can only resolve to a file directly inside `web/assets/`. Directory traversal is structurally impossible.
- **Content types** come from an allow-list (`_ASSET_CONTENT_TYPES`) with `application/octet-stream` as a safe default — no reflected/guessed types.
This is the right bar: it reuses the exact guard that passed the Stage 3 `audit-team` at 0/0/0/0/0. (See watch item W1 for an optional future hardening that would also benefit `/vendor/`.)

## What's working
- **Guard parity, verified:** `_serve_asset` (`webapp.py:408`) and `_serve_vendor` (`:394`) are byte-identical guards; the new route inherits an already-audited safety property rather than inventing one.
- **Build hygiene is deliberate and sound for this slice:** stable, un-hashed filenames (`assets/kimcad.js`, `assets/index.css`) mean each rebuild overwrites cleanly; `emptyOutDir:false` provably preserves `web/vendor/` — and `test_serves_vendored_threejs_and_rejects_traversal` still passes, confirming vendor survived.
- **Reproducible + documented build:** `frontend/package-lock.json` is present and committed; `node_modules` is correctly git-ignored (`git check-ignore` confirms); `frontend/README.md` spells out `npm ci && npm run build`, why the output is committed, and that Node is build-time only. README.md/ARCHITECTURE.md now state end-users need no Node.
- **The committed build is internally consistent:** `index.html` references `/assets/kimcad.js` + `/assets/index.css`, and `test_built_spa_references_only_existing_assets` asserts every referenced bundle exists on disk — a stale/missing build trips the suite.
- **Supply chain clean:** the initial dev-server-only esbuild advisory was resolved by moving to Vite 8; `npm audit` re-run = 0 vulnerabilities.
- **Verified green (re-run this pass):** `ruff check src tests` clean; full `pytest tests` = 396 passed incl. live; web tests = 43 passed.

## Watch items (forward-looking — not findings; scheduled, tracked here so they don't vanish)
1. **W1 — optional static-route hardening.** The filename guard is string-based. It provably prevents traversal (no separator ⇒ single segment), but a `.resolve().is_relative_to(WEB_DIR/'assets')` containment check would be belt-and-suspenders and could be shared by `/assets/` **and** `/vendor/` via one helper. Genuinely theoretical exposure (localhost-only, no separator ⇒ no arbitrary read), so not a defect — fold into a future security/dedup pass if desired.
2. **W2 — reinstate the frontend↔backend field-contract tests.** The old vanilla-UI tests for field consumption (`gate_status`/`clarification`/the four `PipelineStatus` values/the connector-status vocabulary) were removed because their page no longer exists and the shell consumes none of those fields yet. They MUST return — asserted against the TypeScript source — in **Slice 4** (design flow) and **Slice 5** (printer/slice/send), or the contract goes unguarded. This accounts for the 400→396 test delta (~8 removed for removed behavior, ~4 SPA/asset tests added); acceptable for this slice, but the reinstatement is a hard requirement of the later slices, not optional.
3. **W3 — orphan-asset guard when code-splitting lands.** With `emptyOutDir:false` + stable names, the single entry+CSS overwrite cleanly today (no orphans). When Slice 3 adds three.js (likely a split chunk), a later-removed/renamed chunk could orphan a stale file in the committed `web/assets/`. Add a build-clean of `web/assets/` (preserving `vendor/`) or an assertion that the committed asset set equals the fresh build output, when chunking is introduced.

## Escalation recommendation
No escalation needed. A small, well-scoped infrastructure slice that reuses an audited safety pattern, with green tests/lint/audit and accurate docs. audit-team is not warranted.
