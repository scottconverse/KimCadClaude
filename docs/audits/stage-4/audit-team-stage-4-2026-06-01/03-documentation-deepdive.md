# 03 — Documentation Deep-Dive (Technical Writer)

**Audit:** KimCad Stage-4 gate (React SPA shell + viewport)
**Role:** Senior Technical Writer (audit-only mode)
**Date:** 2026-06-01
**Branch:** `stage-4-react-spa-shell` (head `c65a42d`)
**Scope:** docs touched/affected by Stage 4 — `README.md` ("Web UI" + "Send to a printer"
sections), `ARCHITECTURE.md` ("the web layer" + "module map"), `ROADMAP.md`,
`frontend/README.md`, `CHANGELOG.md`, and the per-slice audit reports under
`docs/audits/stage-4/`. Claims were run down against the actual Stage-4 code: `webapp.py`
routes, `frontend/` source, `package.json` / `vite.config.ts`, and a clean rebuild.

## Method note — claims were executed, not just read

- Ran `npm run build` in `frontend/` on Node v24.14.0 / npm 11.9.0. It succeeded and emitted,
  into `src/kimcad/web/`: `index.html`, `assets/kimcad.js` (147.9 kB), `assets/index.css`
  (12.35 kB), **`assets/Workspace.js` (532.67 kB)**, and three `*.woff2` fonts. The rebuild was
  **byte-identical to the committed output** (`git status` clean after build) — so the
  "commit the rebuilt output" discipline is being honored, and the build is reproducible. Good.
- Cross-checked every documented API route against the actual `do_GET` / `do_POST` dispatch in
  `webapp.py`.
- Read all of `frontend/src/` (App, Workspace, Viewport, KCViewport, RightPanel, ExportPanel,
  ConnectorStatus, api.ts) to verify honesty claims about what the SPA actually does.

---

## Severity rollup

```
Blocker:  0
Critical: 0
Major:    2
Minor:    3
Nit:      2
-----
Total:    7
```

---

## Findings

### DOC-401 — Major — Accuracy / Honesty
**README's "Send to a printer → Web" bullet describes a browser send flow the Stage-4 SPA does not have**

**Evidence:** `README.md` line 169:
> "**Web:** after a slice, pick a connection and confirm to send. A live **ready / not-ready
> badge** shows whether the chosen connection is reachable and idle, and the download stays as
> the fallback."

The Stage-4 SPA does **not** implement sending from the browser. `frontend/src/components/ExportPanel.tsx`
offers printer/material selection, a **Slice & prepare file** action, and **Download G-code / Download
3D model** links — but no send control. `frontend/src/components/ConnectorStatus.tsx` is explicitly
**read-only** ("Read-only readiness of the default printer connection. The full direct-print/send UI is a
later stage"). A grep of `frontend/src` for any `send` call confirms there is **no `/api/send` call and no
send button anywhere in the SPA**; `ExportPanel.tsx` line 15 itself states "The full direct-print/send UI
is Stage 10," and `ROADMAP.md` Stage 10 confirms the direct-print/send UI is deferred there.

The `/api/send/<id>` endpoint *does* exist server-side (`webapp.py` `_handle_send`), and the CLI `--send`
path works — but the README bullet is under the user-facing "Web:" label and tells a browser user they can
"pick a connection and confirm to send" today. They cannot. The "live ready / not-ready badge" half is
accurate (ConnectorStatus renders it); the "confirm to send" half is not.

**Why this matters:** This is the writer's #1 failure mode — implying a capability that doesn't exist. A
user reads "after a slice, pick a connection and confirm to send," slices a part, looks for the send
control, and finds only a download link and a status dot. That's the exact "wait, this doesn't actually do
that" trust-breaker. It also undercuts KimCad's otherwise strong honesty posture (the rest of the docs are
scrupulous about "no real hardware yet," `simulated` labels, etc.), so the contrast is jarring.

**Blast radius:**
- Adjacent docs: `ARCHITECTURE.md` "the web layer" (lines 128–136) describes the same browser-send flow
  ("After a successful slice the page can also **send** the job... `POST /api/send/<id>`") in the
  present tense as if the SPA drives it. Same overclaim, second location — fix both together.
- `CHANGELOG.md` lines 108–113 (Stage 2 "Web send-to-printer") also describe the web send as shipped; that
  was true of the *old* vanilla-JS UI but the Stage-4 SPA dropped the send control, so the CHANGELOG now
  describes a UI surface that no longer exists in the React app.
- User-facing: only the README/ARCHITECTURE prose; no code change implied. The honest fix is a doc edit.
- Migration: none.
- Tests to update: none — there is no test asserting a browser send (correctly, since the SPA has none).
- Related findings: DOC-402 (CHANGELOG has no Stage-4 section to record this UI scope change).

**Fix path:** Recommend re-scoping the README "Web:" bullet to what the SPA does today: "**Web:** after a
slice, download the proven G-code (or the model); a live **ready / not-ready badge** shows whether the
default connection is reachable. *Sending to a printer from the browser arrives with the direct-print UI
(Stage 10); for now use the CLI `--send` for the send path.*" Mirror the same correction in
`ARCHITECTURE.md`'s "the web layer" paragraph (keep the endpoint description — `/api/send/<id>` exists —
but state plainly that the SPA does not yet drive it).

---

### DOC-402 — Major — Completeness
**CHANGELOG has no Stage-4 section — the entire React SPA is undocumented in the changelog**

**Evidence:** `CHANGELOG.md` `[Unreleased] → Added` carries an explicit `#### Stage 1`, `#### Stage 2`, and
`#### Stage 3` subsection (lines 57, 78, 120), each cataloguing that stage's work. There is **no
`#### Stage 4` subsection** anywhere in the file. Stage 4 — the React/TS/Vite SPA, the vanilla-Three.js
viewport, the new `/assets/` static-serving path, the design-flow wiring, the slice/download UI — is the
entire body of work on this branch and is **completely absent** from the changelog. The file's own header
(lines 1–4) declares it "follows Keep a Changelog" and "each stage is tagged as it lands," which sets the
expectation that every stage is recorded.

Worse, the changelog *still* describes the superseded UI: line 47 ("Phase-2 web UI first slice... a
dependency-free local browser app") and lines 108–113 (Stage 2 web send-to-printer) describe the old
single-file vanilla-JS page that Stage 4 replaced — with no entry noting the replacement.

**Why this matters:** The new-team-member persona and any release-notes consumer reads the CHANGELOG to
learn what changed. For a project that meticulously logged Stages 0–3, the gap reads as "Stage 4 wasn't
finished" or "the changelog is no longer maintained" — both corrosive to trust. It also means the
SPA-replaces-vanilla-JS architectural shift (a real breaking change to the front end, and to how the UI is
built) is unrecorded.

**Blast radius:**
- Adjacent docs: ties to DOC-401 (the dropped browser-send control is one of the scope changes a Stage-4
  changelog entry would record) and DOC-405 (the build-process change — Node-at-build-time — belongs here
  too).
- User-facing: changelog only.
- Migration: none.
- Tests to update: none.
- Related findings: DOC-401, DOC-405.

**Fix path:** Recommend adding a `#### Stage 4 — React SPA shell + viewport` subsection under
`[Unreleased] → Added` covering: the React+TS+Vite SPA built (build-time only) into `src/kimcad/web`;
the Python server now serving `/assets/<file>` (same traversal guard as `/vendor/`); the vanilla
Three.js viewport loading the real exported STL; the design → plan → gate → slice → download flow wired
through the new UI; vitest added for the TS logic. A one-line `### Changed` note that Stage 4 *replaced*
the vanilla-JS first-slice page with the SPA closes the loop on the now-stale lines 47 / 108–113.

---

### DOC-403 — Minor — Accuracy
**`frontend/README.md` "stable filenames" note omits the `Workspace.js` chunk the build actually emits**

**Evidence:** `frontend/README.md` lines 40–41:
> "Output filenames are **stable** (un-hashed: `assets/kimcad.js`, `assets/index.css`) so each rebuild
> overwrites cleanly and the committed output stays tidy."

The actual build (verified by running `npm run build`) emits a **third** stable, un-hashed JS file:
`assets/Workspace.js` (532.67 kB — the code-split, lazy-loaded Three.js viewport chunk). It is the
*largest* artifact in the build and is committed at `src/kimcad/web/assets/Workspace.js`. The "How it fits
together" diagram (lines 10–15) and this note both list only `kimcad.js` + `index.css` under `assets/`,
plus the fonts — `Workspace.js` is invisible in the doc despite being the dominant bundle. `vite.config.ts`
sets `chunkFileNames: 'assets/[name].js'`, which is exactly what produces this stable-named chunk, and the
config comment (lines 22–25) even explains the chunk exists and is intentionally code-split — so the doc
is internally inconsistent with the config it ships beside.

**Why this matters:** The new-team-member persona who edits the viewport, rebuilds, and reviews
`git status` sees `Workspace.js` change. The README told them to expect only `kimcad.js` + `index.css`, so
they may wonder whether the build is misbehaving or whether to commit the extra file. The "stays tidy"
claim is also weaker than stated: the build is tidy, but the doc undersells *what* is in the tidy set.

**Blast radius:**
- Adjacent docs: the "How it fits together" diagram in the same file (`assets/` line) — update both.
- User-facing: doc only.
- Migration: none.
- Tests to update: `tests/test_frontend.py` asserts referenced assets exist by reading the shell's
  `/assets/` references; it does not enumerate chunks, so it is unaffected.

**Fix path:** Recommend listing all three committed `assets/` JS/CSS artifacts: "`assets/kimcad.js`
(entry), `assets/Workspace.js` (the code-split Three.js viewport chunk), `assets/index.css`." A one-clause
mention that the viewport is lazy-loaded as its own chunk also explains *why* there are two JS files.

---

### DOC-404 — Minor — Accuracy / Completeness
**`frontend/README.md` API list omits `/api/connectors` and the index implies an exhaustive list**

**Evidence:** `frontend/README.md` lines 19–22:
> "The JSON API the SPA talks to (`/api/design`, `/api/slice/<id>`, `/api/options`,
> `/api/connector-status/<name>`, `/api/mesh/<id>`, `/api/gcode/<id>`, `/api/send/<id>`) is unchanged
> from the pre-SPA UI..."

`webapp.py` also serves **`GET /api/connectors`** (lines 343–357 — lists the configured connections with
their `simulated` flag), which `ConnectorStatus.tsx` calls via `getConnectors()` (`api.ts` line 126) to
find the default connection before checking its status. So the SPA *does* talk to `/api/connectors`, but it
is missing from this list. Conversely, `/api/send/<id>` *is* listed but the SPA does **not** call it (see
DOC-401), so the list is both missing a used route and listing an unused one.

**Why this matters:** Low impact (the list is a developer convenience, not an install path), but a
contributor wiring a new panel will take this list as the API surface and miss `/api/connectors`. The
"unchanged from the pre-SPA UI" claim is also slightly off given the SPA dropped the send call.

**Blast radius:**
- Adjacent docs: `ARCHITECTURE.md` "the web layer" lists the same endpoints in prose (it *does* mention
  `/api/connectors` at line 133, so ARCHITECTURE is the more complete of the two — align frontend/README
  to it).
- User-facing: doc only.
- Migration: none.
- Tests to update: none.

**Fix path:** Recommend adding `/api/connectors` to the list and, for precision, noting `/api/send/<id>`
exists but is exercised by the CLI today, not the SPA (ties to DOC-401).

---

### DOC-405 — Minor — Onboarding / Completeness
**No top-level Requirements/Setup mention that Node is needed to rebuild the UI; the "no Node to run" story is only in two deep sections**

**Evidence:** `README.md` "Requirements" (lines 31–43) and "Setup" (lines 44–81) never mention Node or the
front-end build at all. The "you don't need Node to run KimCad / Node only to rebuild" story appears only
in the "Web UI" subsection (lines 127–131) and in `frontend/README.md`. The README's `npm --prefix frontend
ci && npm --prefix frontend run build` command (line 130) is accurate and matches `package.json` (`ci`
installs from the committed `package-lock.json`; `build` = `tsc --noEmit && vite build`) — verified by
running it — but a contributor scanning Requirements/Setup to set up a dev environment won't learn that
editing the UI needs Node 18+ until they reach the Web UI section near the end.

**Why this matters:** The new-team-member persona reads Requirements + Setup to provision a machine. The
*runtime* requirements are complete (and the "no Node at runtime" claim is true and well-verified). But the
*contributor* who will touch the UI needs Node, and that requirement is buried. This is a completeness gap
for the contributor path, not a runtime-install blocker (so Minor, not Major).

**Blast radius:**
- Adjacent docs: there is no `CONTRIBUTING.md` / `DEVELOPING.md`, so the README is the only home for this;
  `frontend/README.md` has the detail but a contributor has to know to look there.
- User-facing: doc only.
- Migration: none.
- Tests to update: none.

**Fix path:** Recommend one line under Requirements: "*Node 18+ — only to rebuild the browser UI; not
needed to run KimCad (the built UI ships committed). See `frontend/README.md`.*" That keeps the strong "no
Node at runtime" message while making the contributor requirement discoverable.

---

### DOC-406 — Nit — Accuracy
**Stale code comments in `App.tsx` and `ConnectorStatus.tsx` describe slices/stages as "next" that are now done**

**Evidence:** `frontend/src/App.tsx` lines 13–14: "Live sliders (Stage 5) and the **printer/slice/send
controls (Slice 5) come next**." Slice 5 (the printer/slice/download controls) is **done** on this branch —
`ExportPanel.tsx` exists and the slice-5 audit report (`audit-lite-slice-5-export-2026-06-01.md`) records it
cleared its gate. The comment reads as if Slice 5 is still ahead. (The "Live sliders (Stage 5)" half is
correct.) Minor wording: it also conflates "Slice 5" controls with "send," but send is Stage 10, not Slice 5.

These are source-code comments, not user docs, so this is a Nit — but they live in the audited files and a
reader uses them to understand state, so worth a one-line correction.

**Why this matters:** Low — internal comments only. But stale "comes next" comments make a reader doubt
whether the code matches the plan.

**Fix path:** Recommend updating the `App.tsx` comment to reflect that the design flow + slice/download are
wired and only live sliders (Stage 5) and the direct-print/send UI (Stage 10) remain.

---

### DOC-407 — Nit — Accuracy / Tone
**ROADMAP Stage 4 still flagged "⬅ NEXT" while it is in fact the stage being gated**

**Evidence:** `ROADMAP.md` line 102: "## Stage 4 — React SPA shell + viewport  ⬅ NEXT", and line 37 "Next
= Stage 4." This is *defensible* — Stage 4 is not yet merged or tagged (work is on branch
`stage-4-react-spa-shell`, and ROADMAP's convention is to mark a stage DONE only once merged+tagged, as it
does for Stage 3 "✅ DONE — tagged `stage-3` @ `96aba02`"). So "NEXT" is not wrong against the branch state.
But the stage is complete-and-under-audit, not un-started, so "NEXT" slightly understates reality at this
moment. The rest of ROADMAP is accurate: Stage 3 correctly DONE+tagged, the 9-stage v3.0 numbering
(stages 3–11) matches the spec reference, later-stage scopes (template engine/sliders → Stage 5, model swap
→ Stage 6, Smart Mesh → 7, CadQuery → 8, image → 9, direct-print/Bambu-native → 10, installer → 11) are
internally consistent and match the cross-references in the other docs.

**Why this matters:** Trivial; resolves itself the moment Stage 4 merges (the marker flips to ✅ DONE).
Flagging once so it isn't forgotten at merge.

**Fix path:** No change required pre-merge; recommend flipping Stage 4 to "✅ DONE — tagged `stage-4`" (and
updating the "Current baseline" header) as part of the merge commit, exactly as Stage 3 was handled.

---

## What's working (credit where due)

The Stage-4 documentation is, on the whole, **accurate, honest, and unusually well cross-referenced** — the
findings above are edge-trims on a solid body, not a teardown.

- **The "no Node at runtime" story is true and well-told.** `README.md` lines 127–131, `ARCHITECTURE.md`
  lines 138–144, `frontend/README.md`, `vite.config.ts`, and `package.json` all agree: Node/Vite are
  build-time only, the build output is committed, and `kimcad web` serves it with no toolchain. I verified
  this end-to-end — the rebuild was byte-identical to the committed files, so the "commit the rebuilt
  output" instruction (`frontend/README.md` lines 43–44) is being followed in practice, not just preached.
- **The viewport docs are honest — there is no "demo box" overclaim.** The KCViewport docstring
  (`frontend/src/viewport/KCViewport.ts` lines 4–11) is explicit that, *unlike* the design prototype's
  slider-driven fake geometry, this loads the **real** exported STL from `/api/mesh/<id>`. `Viewport.tsx`
  and `Workspace.tsx` confirm the real `meshUrl` flows through. The viewport genuinely renders the
  pipeline's rendered part; no doc claims more than that. (The audit prompt's hypothesis that "the viewport
  only shows a demo box" does **not** hold — the only "demo" is `--demo` mode, which still renders a real
  `snap_box` mesh via the pipeline, not a placeholder cube.)
- **ARCHITECTURE's API list matches `webapp.py`.** Every route in the "the web layer" section
  (`/api/design`, `/api/slice/<id>`, `/api/gcode/<id>`, `/api/options`, `/api/connectors`, `/api/send/<id>`)
  is a real route in `do_GET`/`do_POST`. ARCHITECTURE is actually *more* complete than `frontend/README.md`
  here (it includes `/api/connectors`; see DOC-404).
- **The `/assets/` serving description is precise.** ARCHITECTURE (lines 142–144) and `frontend/README.md`
  (lines 17–18) correctly state the SPA shell is served at `/` and bundles at `/assets/<file>` "behind the
  same traversal guard as `/vendor/`" — which matches `webapp.py` `_serve_asset` (lines 404–416) mirroring
  `_serve_vendor` exactly. The `emptyOutDir: false` rationale (vendor survival) is documented and matches
  the config.
- **The build command in the docs is correct.** `npm --prefix frontend ci && npm --prefix frontend run
  build` (README line 130) maps exactly to `package.json` scripts; `ci` uses the committed lockfile and
  `build` typechecks then builds. Ran it; it works.
- **The Verify section is accurate.** `frontend/README.md` "Verify" correctly names `npm test` (vitest) for
  the TS logic and points at `tests/test_frontend.py` + `tests/test_webapp.py` for the Python-side build
  contract — and those tests exist (`test_frontend.py` reads the built shell/assets; `test_webapp.py` covers
  serving + traversal rejection).
- **The per-slice audit reports are honest and well-scoped.** The five `audit-lite-slice-*` reports record
  rounds, fixes, and watch items truthfully (e.g. slice-5 logs the UX-501 stale-`<select>` Nit and its fix,
  and correctly notes send/sliders are out of scope for Stage 4). They don't overclaim a clean gate they
  didn't earn.

## Cross-role hand-offs

- **DOC-401 / DOC-402** pair with the UX/QA review: the "browser send" the README promises is genuinely
  absent from the SPA, so if UX or QA file a "no send affordance in the export panel" observation, the
  correct resolution is a **doc fix** (descope the claim), not a feature add — send UI is legitimately
  Stage 10 per ROADMAP. Flagging so the team doesn't accidentally build send UI to match a doc that should
  instead be corrected.
- **DOC-403** (the undocumented `Workspace.js` chunk) is worth a glance from the Principal Engineer only to
  confirm the lazy-split is intended (it is — `vite.config.ts` documents it); no code action, doc-only.
