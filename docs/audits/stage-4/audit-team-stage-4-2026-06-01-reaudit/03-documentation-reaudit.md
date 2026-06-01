# 03 — Documentation Re-Audit (Technical Writer)

**Audit:** KimCad Stage-4 gate — RE-AUDIT after remediation
**Role:** Senior Technical Writer (audit-only mode — flag, don't rewrite)
**Date:** 2026-06-01
**Branch:** `stage-4-react-spa-shell` (head `fa39fdd`)
**Scope:** verify every original DOC finding (DOC-401 … DOC-407) is resolved **in the current
docs**, cross-checked against the **code** (REMEDIATION.md was not trusted — each claim was
re-derived from the live files); plus a fresh pass for any NEW doc inaccuracy the Stage-4 fixes
introduced.

## Method note — re-derived from source, not from REMEDIATION

- Read the current `README.md`, `ARCHITECTURE.md`, `CHANGELOG.md`, `ROADMAP.md`,
  `frontend/README.md` in full.
- Cross-checked every doc claim that the fixes touched against the actual code: `frontend/src/`
  (`App.tsx`, `components/ExportPanel.tsx`, `components/ConnectorStatus.tsx`, `api.ts`,
  `viewport/KCViewport.ts`), `vite.config.ts`, `src/kimcad/webapp.py` route dispatch, `scripts/ci.sh`,
  and the committed build under `src/kimcad/web/`.
- Confirmed the committed build artifacts on disk and in the index:
  `git ls-files src/kimcad/web/` lists exactly `assets/kimcad.js`, `assets/Workspace.js`,
  `assets/index.css`, three `*-latin-wght-normal.woff2` fonts, `index.html`, and the `vendor/`
  three.js — matching what the docs now describe.
- Confirmed `frontend/src` has **no `send()` call** (`api.ts` exports `postDesign` / `getOptions` /
  `getConnectors` / `getConnectorStatus` / `postSlice` — no send), so the "browser does not send"
  descope is true in code, not just in prose.

---

## Severity rollup (this re-audit)

```
Blocker:  0
Critical: 0
Major:    0
Minor:    0
Nit:      0
-----
Total:    0   (no new findings)
```

All seven original DOC findings are **RESOLVED** (DOC-407 is correctly **deferred to merge**, as the
original finding itself recommended). No new doc inaccuracy was introduced by the Stage-4 fixes.

---

## Per-finding verification

### DOC-401 — Major — RESOLVED
**README + ARCHITECTURE no longer claim the browser sends to a printer.**

- **README** `### Send to a printer` → **Web** bullet (lines 174–176) now reads: "after a slice,
  download the proven G-code or the model, and a live **ready / not-ready badge** shows whether the
  printer connection is reachable. *(Sending to a printer from the browser is a later stage — today
  the web UI is status + slice + download; the CLI and MCP send.)*" The overclaimed "pick a
  connection and confirm to send" is gone; the badge half (accurate) is kept.
- **ARCHITECTURE** "the web layer" (lines 129–134) now states the page shows a "**read-only**
  ready/not-ready connection badge" and "**Sending to a printer from the browser is a later
  stage**; the `POST /api/send/<id>` endpoint exists and is driven today by the CLI (`--send`) and
  the MCP server." Endpoint description retained (the route is real); the SPA-drives-it claim removed.
- **Code cross-check:** `ExportPanel.tsx` offers printer/material selectors, a **Slice & prepare
  file** action, **Download print file (.3mf)** and **Download 3D model (STL)** links, and renders
  `<ConnectorStatus />` (read-only) — **no send control**. `api.ts` has no send function.
  `webapp.py` line 523 confirms `/api/send/<id>` exists server-side (driven by CLI/MCP, per
  `cli.py` `--send` in ARCHITECTURE line 82). The wording is **accurate and not under-claiming** —
  it correctly credits the badge, the slice, and both downloads, and names the real send paths
  (CLI/MCP) rather than implying the feature is wholly absent.

### DOC-402 — Major — RESOLVED
**CHANGELOG has a Stage-4 entry AND the stale vanilla-UI web-send line is superseded.**

- `CHANGELOG.md` now carries `#### Stage 4 — React/TypeScript SPA shell + Three.js viewport + wired
  flow` (lines 145–167) under `[Unreleased] → Added`, cataloguing: the React+TS+Vite SPA committed
  to `src/kimcad/web/` and served by the stdlib server (shell at `/`, bundles at `/assets/<file>`
  behind the `/vendor/`-style guard); Node/Vite build-time only; the Workshop design system + offline
  fonts; the vanilla Three.js `KCViewport` loading the real `*.oriented.stl` from `/api/mesh/<id>`;
  the text→plan→gate→slice→download flow wired through the SPA; and the vitest harness + contract
  tests + build gate.
- The stale web-send claim is explicitly superseded: line 150 states the SPA "**replaces the earlier
  vanilla-HTML/JS page** (and that page's in-browser send controls)," and lines 161–164 state browser
  send is "intentionally deferred… (This supersedes the Stage-2 'Web send-to-printer' item above,
  which belonged to the now-removed vanilla UI.)" — closing the loop on the now-historical
  Stage-2 entry (lines 108–113).
- **Code cross-check:** every Stage-4 entry claim verified — `/api/mesh/<id>` serving
  (`webapp.py` line 673), code-split lazy viewport (`App.tsx` line 8 `lazy(() => import('./components/Workspace'))`,
  `vite.config.ts` `chunkFileNames`), vitest wired into CI (`scripts/ci.sh` lines 28–32) with a
  release gate (line 41). The historical Stage-1 line 47 is correctly left in place (changelogs are
  append-only history; the supersede is recorded in the Stage-4 section, which is the right place).

### DOC-403 — Minor — RESOLVED
**`frontend/README.md` stable-filenames note now includes `Workspace.js`.**

- `frontend/README.md` lines 42–44 now list all stable artifacts: "`assets/kimcad.js`, the
  lazy-loaded three.js chunk `assets/Workspace.js`, `assets/index.css`, and the latin-font
  `.woff2`s." The "How it fits together" diagram (line 13) describes `assets/` as "bundled
  JS/CSS/fonts" (no longer an under-enumerated list).
- **Code cross-check:** `git ls-files src/kimcad/web/assets/` returns exactly `kimcad.js`,
  `Workspace.js`, `index.css`, and the three woff2s — the doc now matches the committed set.
  `vite.config.ts` `chunkFileNames: 'assets/[name].js'` is what produces the stable `Workspace.js`.

### DOC-404 — Minor — RESOLVED
**`frontend/README.md` API list adds `/api/connectors`, drops `/api/send`.**

- `frontend/README.md` lines 19–24 now list the SPA's API as `/api/design`, `/api/slice/<id>`,
  `/api/options`, **`/api/connectors`**, `/api/connector-status/<name>`, `/api/mesh/<id>`,
  `/api/gcode/<id>` — and append: "(`/api/send/<id>` exists server-side but the SPA does not call it
  yet — browser send is a later stage; the CLI and MCP send today.)" So the used route is added and
  the unused route is removed from the SPA list (with an honest note that it still exists server-side).
- **Code cross-check:** `ConnectorStatus.tsx` calls `getConnectors()` → `/api/connectors`
  (`api.ts` line 126; served at `webapp.py` line 362). `api.ts` has no send call, matching the note.

### DOC-405 — Minor — RESOLVED
**README Requirements states no Node is needed to run.**

- `README.md` "Requirements" now ends (lines 44–47) with: "**No Node.js is needed to *run*
  KimCad.** The browser UI is a React single-page app whose compiled output is committed and served
  by the Python server, so `kimcad web` works with the steps above alone. Node (+ `npm`) is needed
  only to *rebuild* that UI… `npm --prefix frontend ci && npm --prefix frontend run build` (see
  `frontend/README.md`)." The contributor's Node requirement is now discoverable from Requirements,
  not only from the deep "Web UI" subsection.
- **Code cross-check:** `npm --prefix frontend ci && npm --prefix frontend run build` matches
  `package.json` scripts and `vite.config.ts` (build → `../src/kimcad/web`). The "served verbatim,
  no toolchain" story matches `webapp.py` serving the committed files.

### DOC-406 — Nit — RESOLVED
**`App.tsx` comment refreshed.**

- `frontend/src/App.tsx` lines 11–15 now read: "landing → describe → the part renders in the
  Three.js viewport (Slice 3); the conversation, plan, and printability report fill in from
  /api/design (Slice 4); and the printer/material → slice → download + connector status panel is
  wired (Slice 5). Live parameter sliders are Stage 5…; browser send is Stage 10." The stale
  "Slice 5 comes next" / send-is-Slice-5 wording is gone; Slice 5 is now described as done, and send
  is correctly attributed to Stage 10.
- `ConnectorStatus.tsx` comment (lines 5–6) is also accurate ("Read-only readiness… The full
  direct-print/send UI is a later stage").

### DOC-407 — Nit — RESOLVED (correctly deferred to merge)
**ROADMAP Stage 4 "⬅ NEXT" → DONE flip is the only ROADMAP staleness and is appropriately deferred.**

- `ROADMAP.md` line 102 still reads "## Stage 4 — React SPA shell + viewport  ⬅ NEXT" and line 37
  "**Next = Stage 4**". Per the original finding and `REMEDIATION.md` ("DOC-407 — at merge"), this is
  **intentionally deferred**: ROADMAP's convention marks a stage DONE only once merged + tagged
  (Stage 3 = "✅ DONE — tagged `stage-3` @ `96aba02`"), and Stage 4 is still on branch, unmerged,
  untagged. Marking it DONE now would be the *less* accurate state.
- **Confirmed this is the only Stage-4 staleness in ROADMAP:** the rest is accurate — Stage 3
  correctly DONE+tagged; the Stage-4 scope bullets (lines 103–118) match what shipped (React/TS/Vite
  SPA served by the Python server, Workshop design system, vanilla Three.js `KCViewport`, wired
  flow, read-only sliders only); later-stage scopes and cross-references are internally consistent
  with the spec and the other docs; "vanilla Three.js" (line 110) is the correct architecture
  descriptor (vs react-three-fiber), not a stale vanilla-UI reference. The recommended action is the
  same one-line flip at merge that Stage 3 received.

---

## Fresh pass — did the fixes introduce any NEW inaccuracy?

Checked specifically for contradictions the descope/CHANGELOG/Requirements edits could have created.
**No new findings.** Details:

- **No descope contradiction.** Every place that previously claimed browser-send was found and
  corrected in lockstep: README "Web" bullet, ARCHITECTURE "the web layer", and the CHANGELOG
  supersede note all now agree that browser send is deferred and CLI/MCP are the send paths. The
  README's broader `### Send to a printer` section and the `reason`/`note` tables describe the
  CLI/MCP/HTTP-API send surface (which genuinely exists) and do **not** imply a browser send — no
  residual overclaim. ARCHITECTURE's `printer_connector.py` / `mcp_server.py` / `cli.py` module rows
  describe the real send abstraction and CLI/MCP send, all code-accurate.
- **CHANGELOG Stage-4 entry matches what shipped.** Every claim re-derived from code (SPA committed +
  served, build-time-only Node, `/assets/` serving + traversal guard, real STL via `/api/mesh/<id>`,
  code-split lazy viewport, wired flow, read-only badge, browser-send deferred, vitest + contract +
  build gates). No claim overstates the branch.
- **REMEDIATION.md is accurate** on the DOC items: DOC-401/402/403/404/406 fixes are present as
  described; DOC-405 is present (its "batch 5" attribution is plausible and the content is in
  Requirements); DOC-407 is correctly listed as "at merge." No DOC line in REMEDIATION overstates
  what landed.
- **frontend/README "Verify" still true.** It names `npm test` (vitest) for the pure logic and
  `tests/test_frontend.py` + `tests/test_webapp.py` as the Python-side build gate. Those modules
  exist; `test_frontend.py` asserts `kimcad.js` + `Workspace.js` exist (lines 174–176), the shell
  mounts `#root`, references existing `/assets/`, and carries the Workshop fonts — matching the prose.
  The vitest file set is now five (`api`, `connectorStatus`, `designStatus`, `ExportPanel`,
  `RightPanel`), consistent with REMEDIATION's "19/19 (5 files)".
- **One sub-finding-threshold imprecision (logged, not a finding):** the README "Web" bullet says the
  badge "shows whether **the** printer connection is reachable," where `ConnectorStatus.tsx` shows the
  **default** connection specifically (it reads `getConnectors().default`). This is a prose
  simplification, not an inaccuracy — there is one badge and it tracks the default connection; the
  original finding's own recommended text used the same loose phrasing. Below Nit; no action.

---

## What's working (credit where due)

- **The honesty posture is now fully consistent.** The single jarring overclaim (browser send) that
  contrasted with KimCad's otherwise-scrupulous "no real hardware / simulated label / build-time-only
  Node" story has been removed at all three sites *and* in the changelog, restoring a uniformly honest
  doc set. The fixes corrected the docs to match the code rather than building send UI to match the
  docs — the right call, exactly as the original cross-role hand-off recommended.
- **The CHANGELOG now records the architectural shift.** The SPA-replaces-vanilla-JS change (a real
  front-end breaking change) is captured, with an explicit supersede of the now-historical Stage-2
  web-send item — the new-team-member / release-notes persona can now trace what changed in Stage 4.
- **The doc↔code↔build triangle holds.** Committed build artifacts, `vite.config.ts`, the API route
  dispatch in `webapp.py`, and the prose in README/ARCHITECTURE/frontend-README all agree after the
  fixes; the contract tests gate the agreement from the Python side.

## Bottom line

All seven original DOC findings are resolved (DOC-407 correctly deferred to the merge commit). The
Stage-4 doc fixes introduced **no** new inaccuracy. From the Technical Writer lens, the docs are
clean to merge; the only remaining doc action is the routine ROADMAP Stage-4 "⬅ NEXT → ✅ DONE —
tagged `stage-4`" flip (plus the "Current baseline" header bump) as part of the merge commit, exactly
as Stage 3 was handled.
