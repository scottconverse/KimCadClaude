# KimCad Stage 4 — Audit-Team Executive Report (Stage Gate)
**Date:** 2026-06-01 · **Branch:** `stage-4-react-spa-shell` @ `c65a42d` · **Bar to pass:** 0/0/0/0/0

## Executive summary
Stage 4 (React/TS/Vite SPA shell + vanilla Three.js viewport + the wired design→gate→slice→download flow) is **architecturally sound and safe — no Blockers, no Criticals**. All five roles independently confirmed the load-bearing invariants hold: a gate-FAILED part can't be sliced/sent (enforced in three layers — UI + `/api/slice` + `/api/send` — and tested server-side), the `/assets/` route's traversal guard is empirically equivalent to `/vendor/` (10 encodings rejected), there is no XSS sink (no `dangerouslySetInnerHTML`), no credential leak in the connector path, the build is byte-reproducible from source, and the runtime flow works end-to-end (real OrcaSlicer slice → valid 3MF → mock send honestly flagged `simulated`). The gate does **not** pass yet only because of lower-severity findings: **6 Major, 19 Minor, 9 Nit** — all to be fixed to reach 0/0/0/0/0 before merge + tag. The standout is a **test that lies** (TEST-001): the headline field-contract test is a substring spell-checker that does not actually detect dropped rendering.

## Severity roll-up
| Blocker | Critical | Major | Minor | Nit | Total |
|---|---|---|---|---|---|
| 0 | 0 | 6 | 19 | 9 | 34 |

**Gate verdict: NOT PASSED — fix all 34 → re-audit → 0/0/0/0/0 → merge + tag `stage-4`.**

## Top findings (the 6 Majors)
1. **TEST-001 (Test) — the field-contract test is a spell-checker, not a contract test.** Proven by mutation: deleting the *entire* printability panel's rendering left the test green except for `headline`; `gate_status`/`dims`/`findings` survived on a comment + classNames. 8/14 fields pass with zero property access. Fix: after stripping comments, require a `.field` access or a quoted-literal shape, not a bare substring. Same flaw in the every-status and connector-status checks.
2. **UX-003 (UI/UX, a11y) — primary-button text fails WCAG AA contrast.** White on terracotta `#c8623a` = 3.99:1 ("Design it", "Slice & prepare file"); accent text/link on surface = 3.70:1. Fix: darken the button/link fill (e.g. a dedicated `--kc-accent-strong`/darker) so white clears 4.5:1; keep `--kc-accent` for non-text accents.
3. **UX-001 (UI/UX) — the viewport ships none of the design's print-aware affordances.** No X/Y/Z dimension pills, no bounding box, no "drag to rotate" hint, no orientation chip — the centerpiece reads as a decorative spinning box vs. the design's instrumented preview. Fix: add the dimension labels (project bbox corners to screen space) + a faint bbox + a drag hint.
4. **DOC-401 (Docs, honesty) — README + ARCHITECTURE overclaim browser "send to printer".** They say the browser can "pick a connection and confirm to send", but the SPA has **no send control** (ExportPanel slices + downloads only; send is Stage 10). Fix by **descoping the doc claim** (do NOT build send UI — that's Stage 10).
5. **DOC-402 (Docs) — CHANGELOG has no Stage-4 section** and still carries stale vanilla-JS-UI lines (incl. its web-send). Fix: add a Stage-4 entry; supersede the stale lines.
6. **ENG-401 (Eng) — build-hygiene latent trap.** The `prebuild` rimraf only cleans `assets/`; a renamed/removed chunk built via bare `vite build` (bypassing `prebuild`) or output outside `assets/` could orphan in the committed tree. Not currently present (rebuild = no drift). Fix: in `ci.sh`, assert the working tree is VC-clean after a rebuild (committed output == fresh build).

## What's working (verified, specific)
- **Safety invariants all hold** (Eng + QA): gate-fail-can't-slice fail-closed in 3 layers + tested; traversal guard equivalent to `/vendor/` (drive-relative `C:foo` collapses inside `assets/`); no XSS; no credential leak; no 5xx/stack-trace leak on bad input.
- **Design system is pixel-faithful** (UI/UX, verified by computed-style inspection): palette, type ramps, 58px topbar, logo cube + Kim**Cad** wordmark, 3-col→stacked responsive — all match the Workshop spec. Strong empty/loading/error state discipline; aria-live conversation, label-wrapped selects, focus-visible rings; zero console errors.
- **Runtime green end-to-end** (QA): real OrcaSlicer slice (78k-line G-code, valid estimate/profiles) → valid 3MF → honest simulated send.
- **Engineering**: `loadToken` STL-race guard + `dispose()` lifecycle correct; `npm audit` 0; `tsc` strict clean; build byte-reproducible; the real-socket `/assets/` serve+traversal test is the strongest test in the surface.
- **Viewport loads the REAL exported STL** (not a demo box) — the "demo box only" worry is false (Tech Writer confirmed).

## This-sprint punch list (fix ALL to reach 0/0/0/0/0)
**Major (6):** TEST-001 (tighten the field-contract grep — require `.field`/quoted shapes, strip comments); UX-003 (button/link contrast → AA); UX-001 (viewport dimension pills + bbox + drag hint); DOC-401 (descope the browser-send claim in README + ARCHITECTURE); DOC-402 (CHANGELOG Stage-4 entry + supersede stale UI lines); ENG-401 (CI: assert committed build == fresh build).

**Minor (19):** ENG-402 (lock the `registry`/`gate_status_by_rid` reads in `_handle_slice`/`_handle_send`); ENG-403 (`dispose()` add `renderer.forceContextLoss()`); ENG-404 (grid/plate alloc — *no action needed, verified no leak*); ENG-405 (document the `_ASSET_CONTENT_TYPES` octet-stream fallback intent); UX-002 (viewport blueprint-wireframe default per design); UX-004 (mobile touch targets ≥44px — button/gear/chips); UX-005 (hero input card stacks on mobile); UX-006 (Settings gear: hide it or make it clearly inert until the wizard exists); UX-007 (`prefers-reduced-motion`: stop the auto-rotate / animations); UX-008 (landing badge: outcome-first copy per design); UX-009 (dynamic canvas `aria-label` with the part's dimensions); DOC-403 (frontend/README stable-filenames note: add `Workspace.js`); DOC-404 (frontend/README API list: add `/api/connectors`, drop `/api/send`); DOC-405 (README setup: mention Node-to-rebuild up front); TEST-002 (component-render tests — stand up jsdom + a couple of ExportPanel/RightPanel tests, or record an explicit, justified deferral); TEST-003 (vitest: cover `assistantMessage` default, `connectorTone` paused, the 4 missing `connectorLabel` outcomes); TEST-004 (code-split test: also assert no three.js fingerprint in the entry bundle); TEST-005 (note the CSS-token test is build-completeness, not visual — keep, don't over-read); QA-001 (implement header-only `do_HEAD` → 200, not 405).

**Nit (9):** ENG-406 (document the content-type-map asymmetry across serve methods); ENG-407 (the `chunkSizeWarningLimit` magic number — already well-commented; leave or name it); ENG-408 (`ci.sh` frontend gate: add a `KIMCAD_RELEASE=1` hard-fail when `node_modules` is absent, mirroring the OrcaSlicer gate); UX-010 (hero sub-copy: warmer first-person voice); UX-011 (AI messages: add the 28px cube avatar); UX-012 (export card 3MF-first framing — *largely Stage-10; minimal here*); TEST-006 (a couple of exact-string label assertions couple to copy — acceptable, note); QA-002 (add `Cache-Control`/`ETag` on `/assets` + `/vendor`); QA-003 (`output/web/<id>` orphan dirs across restarts — opportunistic cleanup on startup); QA-004 (413 + keep-alive `ConnectionAbortedError` — drain or signal close).

## Next-sprint watchlist
- Component-render coverage (jsdom) grows in importance at Stage 5 (sliders) — TEST-002 should not be deferred twice.
- The viewport's print-aware instrumentation (UX-001/002/009) is the bridge to the Stage-5 slider UX — design it to extend.
- Asset caching (QA-002) matters more once the Windows/WebView2 shell (Stage 11) ships.

## Blast-radius notes for the fixer
- **UX-003 contrast**: changing `--kc-accent` would recolor every accent surface; instead introduce a darker token used only for text-bearing fills/links — low blast radius.
- **TEST-001**: tightening the grep may newly FAIL if a field truly isn't rendered — that's the point; verify all 14 + the statuses + the 5 connector fields still pass after tightening (they should, the rendering exists).
- **DOC-401/402**: doc-only — descope the claim, do NOT add send UI (Stage 10).
- **ENG-401 CI assert**: ensure the assertion runs *after* a build in CI and that the committed output is regenerated+committed in the same change, or it will trip on the first run.

Per-role detail: `01-engineering-deepdive.md` · `02-uiux-deepdive.md` · `03-documentation-deepdive.md` · `04-test-deepdive.md` · `05-qa-deepdive.md`.
