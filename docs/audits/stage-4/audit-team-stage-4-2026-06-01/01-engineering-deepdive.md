# Stage-4 Gate Audit — Engineering Deep-Dive (Principal Engineer)

- Audit date: 2026-06-01
- Repo: kimcad working tree
- Scope: branch diff main vs stage-4-react-spa-shell (head c65a42d) — the new React/TS/Vite frontend SPA, the committed build in src/kimcad/web, the webapp.py /assets/ route (the _serve_asset method plus the _ASSET_CONTENT_TYPES table), scripts/ci.sh, and the Vite/TS/package config.
- Focus: architecture, correctness, security, performance, dependencies, build hygiene.
- Out of scope (later stages, not flagged): live parameter sliders (Stage 5), direct-print/send UI plus printer monitoring (Stage 10), first-run wizard / model-picker / photo on-ramp, real-hardware testing.

## Verdict at a glance

This is a clean, well-reasoned slice. The architecture (build-time Node, runtime-free Python serving committed static output) is the right call for a local-first tool, the security-critical invariants (no-traversal asset serving, gate-FAILED-can't-slice) are correctly implemented and tested server-side, and the committed build is reproducible byte-for-byte from source. I found zero Blockers and zero Criticals. The findings below are a handful of Majors-and-below that pay their rent but none of which should hold the gate.

Severity counts: Blocker 0, Critical 0, Major 1, Minor 4, Nit 3.

## Checks I ran (and their results)

- Dependency CVEs (production-dep audit via the package manager): 0 vulnerabilities.
- TypeScript (strict, noEmit): clean.
- Frontend unit tests (vitest): 12 passed across 3 files.
- Python lint (ruff over src and tests): all checks passed.
- Reproducible build: rebuilt from source, then inspected version-control status of src/kimcad/web — no drift; the committed output is byte-identical to what the source produces.
- XSS sink search over frontend/src (dangerouslySetInnerHTML, innerHTML, eval, new Function, document.write): no matches.
- Path-traversal guard: empirical probe of the _serve_asset name guard plus the pathlib join on Windows, against percent-encoded dot/slash/backslash, percent-null, drive-relative C:foo, and absolute paths — no bypass found.
- Leftover debug (console statements, debugger, TODO, FIXME) over frontend/src: no matches.
- Live pytest suite: not run, per scope — it is verified green and running five parallel live OrcaSlicer suites would contend.

## Findings

### ENG-401 (Major) — Build hygiene: the prebuild clean is narrower than emptyOutDir, so a renamed or removed entry chunk can orphan in the committed output

- Category: Build hygiene / Architecture.
- Evidence: frontend/package.json:9 — the prebuild step targets only ../src/kimcad/web/assets. frontend/vite.config.ts:20-21 sets emptyOutDir to false. The deliberate design is: commit the build output, keep stable un-hashed filenames, and not blank out web/ (so the hand-vendored web/vendor/ three.js survives). To compensate, prebuild targets only web/assets/ before each build.
- Why this matters: the safety of "no orphan assets" rests entirely on the prebuild step running and on assets/ being the only place build output lands. Two realistic ways it breaks: (1) the Vite build invoked directly rather than through the npm build script skips the prebuild hook, so a renamed chunk leaves a stale sibling that the server will still serve at /assets/<old-name>; (2) if a future change emits anything into web/ outside assets/ (a second HTML entry, a webmanifest, a favicon at root), the prebuild step won't touch it. Today the output is exactly index.html plus assets/* and the rebuild produced no drift, so there is no orphan now — this is a latent hazard, not a present defect, which is why it is Major and not Critical.
- Blast radius:
  - Adjacent code: vite.config.ts rollupOptions.output (entry assets/kimcad.js, chunks assets/[name].js); the _serve_asset route serves whatever sits in web/assets/ with no allow-list.
  - Shared state: the committed src/kimcad/web/ tree is the runtime artifact — an orphan there ships.
  - User-facing: none unless an orphan is referenced; the risk is silent disk/repo cruft and a confusing "why is this old bundle still served" later.
  - Migration: none.
  - Tests to update: test_built_spa_references_only_existing_assets (tests/test_frontend.py) checks the inverse (every referenced asset exists) but not the converse (every asset is referenced). Add a test asserting no web/assets/* file is unreferenced by index.html except the known lazy chunk(s).
- Fix path: keep emptyOutDir false but broaden the guarantee — add a CI/test assertion that the version-control status of src/kimcad/web is clean after a build (this promotes the reproducible-build property I verified by hand into a gate), and/or add an orphan-sweep check that every file in web/assets/ is reachable from index.html or is a known code-split chunk name. Alternatively, document in frontend/README.md that builds must go through the npm build script. The status-clean assertion is stronger — it catches the orphan regardless of how the build was invoked.

### ENG-402 (Minor) — _handle_slice and _handle_send read registry and gate_status_by_rid outside the lock

- Category: Correctness (concurrency).
- Evidence: webapp.py:642 reads registry.get(rid) and :648 reads gate_status_by_rid.get(rid) in _handle_slice; :538 reads gate_status_by_rid.get(rid) in _handle_send — all without holding the lock, whereas _handle_design writes both under the lock (:607-616) and _evict mutates them under the lock.
- Why this matters: in practice this is benign on CPython: dict get is atomic under the GIL; rids are monotonic from itertools.count() issued under the lock, so a slice or send for a given rid can only arrive after the design POST that created it has already returned mesh_url to that client; and a concurrent _evict of the same rid can only happen once the registry exceeds 50 entries, after which the subsequent exists() re-check (:643, :533) catches a removed path. So there is no exploitable race today. It is logged as Minor because the locking discipline is asymmetric (writes locked, reads not) and a future maintainer adding a non-atomic compound read here would not be protected.
- Fix path: wrap the registry.get and gate_status_by_rid.get reads in the lock for symmetry, or add a one-line comment at each read site stating the atomicity plus monotonic-rid argument that makes the lock-free read safe. The comment is cheaper and sufficient; the lock is more defensible long-term.

### ENG-403 (Minor) — KCViewport dispose() does not forceContextLoss; relies on browser GC of the WebGL context

- Category: Performance / Resource lifecycle.
- Evidence: frontend/src/viewport/KCViewport.ts:123-140 — dispose() cancels the RAF, clears the resume timer, runs dragCleanup, disconnects the ResizeObserver, runs all registered cleanups, traverses the scene disposing every geometry and material, then calls renderer.dispose(). It does not call renderer.forceContextLoss().
- Why this matters: this is mostly a credit — the dispose path is unusually thorough (see What's working). The one gap: renderer.dispose() releases the renderer's own GL resources but does not eagerly release the underlying WebGL context; that is reclaimed on GC. Under React 18 StrictMode (main.tsx:12), the Viewport mount effect runs mount, unmount, mount in dev, so a KCViewport is created, disposed, and re-created on the same canvas. Re-acquiring a context on a canvas after renderer.dispose() (without forceContextLoss) works in practice and is the standard pattern, so there is no dev breakage. The theoretical risk is only if many viewport instances were created and destroyed rapidly enough to approach the browser's roughly 16-live-context limit — not reachable with a single persistent viewport. StrictMode is dev-only and does not affect the shipped (committed, production-mode) build.
- Fix path: optional — call renderer.forceContextLoss() immediately before renderer.dispose() in dispose() to release the GL context deterministically rather than on GC. Low urgency given the single-instance lifecycle; worth it as cheap insurance if the viewport ever becomes mountable in multiple places.

### ENG-404 (Minor) — Grid/plate geometry rebuilt per construction; not a leak but a small avoidable allocation on every viewport remount

- Category: Performance.
- Evidence: KCViewport.ts:155-176 — buildPlate(256) constructs a GridHelper and a BufferGeometry plus Line border on every constructor call. Under StrictMode dev double-mount this runs twice; each is correctly disposed by the scene traverse in dispose() (:132-138), so there is no leak — confirmed the traverse covers grid and border (lines carry geometry and material).
- Why this matters: negligible runtime cost (a 16x16 grid plus a five-point line). Flagged only because the plate is static — it could be built once and shared — but sharing across instances would complicate the clean per-instance dispose story, so the current choice is reasonable. This is essentially a "no action needed" note documenting that I checked the plate and grid for the leak the brief asked about, and it is clean.
- Fix path: none recommended. Keep as-is; the per-instance build keeps dispose simple and correct.

### ENG-405 (Minor) — _ASSET_CONTENT_TYPES falls back to octet-stream for unknown suffixes

- Category: Correctness / Hygiene.
- Evidence: webapp.py:404-416 (_serve_asset) and :48-60 (_ASSET_CONTENT_TYPES). The map covers js, mjs, css, map, json, woff2, woff, ttf, svg, png, ico. Unknown suffix maps to application/octet-stream.
- Why this matters: today the only emitted asset types are js, css, woff2 (verified: web/assets/ contains exactly those plus index.html at root), all mapped. The fallback is the safe default (a wrong-typed JS would not execute; an octet-stream just downloads). The note: if a future build emits a webmanifest, an avif, or a wasm, it would be served as octet-stream and silently mis-handled by the browser. Low exposure because the build output is fixed and committed.
- Fix path: no change needed now. When the asset surface grows, extend the map; vite.config.ts is the single place that determines what gets emitted, so the two stay in sync by inspection.

### ENG-406 (Nit) — Asset content-type asymmetry vs _serve_mesh/_serve_gcode octet-stream defaults is fine but undocumented

- Category: Hygiene.
- Evidence: _serve_asset (:415), _serve_mesh (:427), _serve_gcode (:387) each use a different content-type map with the same octet-stream fallback. Intentional and correct.
- Fix path: none. Noted for completeness.

### ENG-407 (Nit) — chunkSizeWarningLimit 700 is a magic number tied to the current three.js size

- Category: Hygiene.
- Evidence: vite.config.ts:25. The comment explains it well (the viewport chunk is three.js-sized, code-split, lazy, and localhost-served, so the generic 500 kB heuristic does not apply). The current Workspace.js is 533 kB, comfortably under 700.
- Why this matters: if three.js grows past 700 kB in a future bump, the warning returns and someone bumps the number again — a slow ratchet. Purely cosmetic.
- Fix path: none needed; the comment already justifies it. Optionally raise to 1000 for headroom, but that weakens the signal — the current value is fine.

### ENG-408 (Nit) — scripts/ci.sh frontend gate skips silently when frontend/node_modules is absent

- Category: Build hygiene.
- Evidence: scripts/ci.sh:27-32 — vitest runs only when frontend/node_modules exists and the package manager is on PATH, else it prints a SKIP note. This mirrors the existing, well-reasoned pattern for the OrcaSlicer live tests: the committed build is what ships, so a toolchain-less box should not fail the gate. The note is printed, so it is honest.
- Why this matters: consistent with the project's stated philosophy and the live-slicer gate just below it. The only asymmetry: the OrcaSlicer skip has a release-flag hard-gate escalation (:45-48); the frontend skip does not. For a release that changes frontend source, you would want vitest to have actually run.
- Fix path: optional symmetry — under the release-gate env flag, fail (not skip) if frontend/node_modules is absent, so a release tag cannot be cut without the SPA tests having run. Low priority — the committed build is also verified reproducible, which is a stronger guarantee.

## Security assessment (dedicated pass)

I treated the two security-critical invariants the brief called out as primary, and ran dedicated passes.

### 1. The /assets/ path-traversal guard is equivalent to _serve_vendor; no bypass found

_serve_asset (webapp.py:404-416) applies the identical guard to _serve_vendor (:390-402): reject when the name is empty or contains a forward slash, a backslash, or a double-dot, then join WEB_DIR with "assets" and the name and require is_file(). I verified the routing and the guard empirically against every bypass named in the brief:

- The GET router strips the query with urlsplit(self.path).path (:369) and does not percent-decode the name (unlike _handle_connector_status, which uses unquote — that asymmetry is correct, since asset names are literal filenames). So percent-encoded dot and slash sequences arrive literally: they either contain a real double-dot (rejected) or the literal text of the percent escape (no separator semantics) and then fail is_file().
- A percent-null sequence arrives as literal text (no decode, no null-byte truncation), passes the name guard, but fails is_file() and returns 404.
- Drive-relative C:foo passes the name guard, but joining it under the assets path collapses to assets/foo on Windows (the drive anchor is absorbed because the base is already C:-anchored) — it stays inside assets/. Verified by probe.
- Absolute paths contain a forward slash and are rejected.

Server-side test test_serves_spa_index_and_assets_and_rejects_traversal (tests/test_webapp.py) covers /assets/nope.js, /assets/, /assets/sub/x.js, and a percent-encoded traversal — all 404. No reachable read outside web/assets/.

### 2. The gate-FAILED-can't-slice invariant is enforced in depth and tested

Three independent layers, all present:
- UI: ExportPanel.tsx:68 derives gateFailed from report.gate_status being "fail", so canSlice is false (:69-74) and the slice controls are replaced by an inspect-only message (:106-110); the model stays downloadable.
- Server (slice): webapp.py:648-652 refuses with sliced false and reason gate_failed, and produces no G-code, so nothing can later be sent.
- Server (send): webapp.py:538-542 is a belt-and-suspenders refusal even if a gcode entry somehow existed.
- The default is fail-closed: the stored gate status defaults to "fail" when a report is absent (:612).
- Tested: test_web_refuses_to_slice_a_gate_failed_part asserts sliced is False, reason is gate_failed, and no gcode_url is present. A direct API client (not just the browser UI, which hides the controls) cannot dispatch a gate-rejected part. Solid.

### 3. XSS: none

No dangerouslySetInnerHTML, innerHTML, eval, new Function, or document.write anywhere in frontend/src. All dynamic content (prompt echo, plan summary, findings, connector notes) renders through React's auto-escaping JSX text nodes.

### 4. Credential leak in the connector-status path: none

getConnectorStatus (api.ts:130-132) consumes a typed snapshot; the server's _handle_connector_status (webapp.py:474-518) returns only name, ready, online, state, detail, reason, simulated, and note — no API key, no URL with credentials. Build and config failures (for example a missing API key) are caught and reported as a non-error status with a generic note, never a stack or the secret. connectorLabel and connectorTone (connectorStatus.ts) only map those typed fields to copy.

### 5. Dependencies

The production-dependency audit reports 0 vulnerabilities. The committed binaries are the intended architecture: three woff2 fonts (latin-only subsets, self-hosted for offline use — main.tsx:3-4), kimcad.js (148 kB entry: React 18.3.1 plus the app), Workspace.js (533 kB lazy chunk: three.js 0.184). No source maps committed. react and react-dom 18.3.1, three 0.184, vite 8, typescript 5.6 — all current, no abandoned packages.

## What's working (credit where due)

- The architecture is the right call, not just the convenient one. Build-time-only Node, runtime-free Python serving committed static output, keeps the local-first / no-toolchain-at-runtime guarantee intact while still getting a modern React/TS/Vite developer experience. vite.config.ts documents why (stable un-hashed names so rebuilds overwrite cleanly; emptyOutDir false to preserve web/vendor/). A thoughtful, well-commented config.
- The build is reproducible. I rebuilt from source and the version-control status of src/kimcad/web showed no drift — the committed artifact is byte-identical to what the current source produces. That eliminates the single biggest hazard of a committed-build repo (stale output) and is worth a lot.
- KCViewport's dispose() is genuinely thorough — the exact thing the brief asked me to scrutinize hardest. It cancels the RAF (:125), clears the auto-rotate resume timer (:126), tears down an in-flight drag's window listeners via dragCleanup (:127), disconnects the ResizeObserver (:128), runs every registered cleanup (window resize, pointerdown, wheel — :129), and traverses the entire scene disposing every geometry and material including the grid and the plate border, with array-material handling (:132-138). I verified the traverse reaches the grid (GridHelper) and the border (Line) — no orphaned GPU resources. The only gap (no forceContextLoss) is a Minor.
- The loadToken STL-race guard is correct. loadMesh captures the incremented loadToken before the async load, and discards the result if disposed or the token is stale (:73-79), disposing the now-orphaned geometry rather than leaking it. clearModel() bumps the token (:104) so a pending load discards. The React Viewport.tsx wrapper adds a cancelled flag per effect (:32, 45-47) so a superseded meshUrl does not flip loading or error state. Two layers, both correct — a stale slow-loading STL cannot clobber a newer one.
- Security invariants are enforced in depth and tested, not just hidden in the UI. The gate-failed and traversal guards both have explicit server-side tests, and the fail-closed default on an absent report is exactly right.
- Honest UX wiring is carried into the typed client. simulated is threaded through every connector branch (server and client) so a loopback send is never narrated as a real print; sliceable and generic_materials let the UI offer only valid combinations and flag generic profiles. The derived selectedMaterial (ExportPanel.tsx:53-59) avoids a controlled-select stale-value React warning — a real correctness detail handled well.
- Test coverage is proportionate and meaningful. 12 vitest cases on the pure mappers and the API client (including error paths and the designIdFromMeshUrl parse), plus Python tests that assert the served shell references only existing assets, loads both JS and CSS with correct content types, rejects traversal, and that the viewport chunk is actually code-split (Workspace.js larger than kimcad.js). The frontend-to-backend field contract is pinned by test_frontend_source_consumes_documented_response_fields. Strict TS plus noUnusedLocals, noUnusedParameters, and noFallthroughCasesInSwitch are on.
- No dead code, no debug leftovers, no TODO or FIXME in the new frontend source. ruff clean, tsc clean.

## What I could not check (disclosed)

- I did not run the full live pytest suite (per the brief — it is verified green, and running five parallel live OrcaSlicer suites would contend). I ran ruff, the frontend vitest suite, the typecheck, and the production-dependency audit, and read the relevant Python tests to confirm the gate and traversal invariants are covered.
- I did not exercise the SPA in a live browser (no runtime UI session). The StrictMode double-mount analysis is by code reasoning plus the known three.js renderer-dispose / re-acquire behavior, not an observed dev session. A browser smoke test is the QA role's lane.
- I did not load-test the threaded server's slice serialization under real concurrency; the existing test_concurrent_identical_slices_run_once covers the contract I would want to see.

## Bottom line for the gate

Nothing here blocks Stage 4. The one finding worth doing this sprint is ENG-401 (turn the reproducible-build property into a CI/test assertion so a bare Vite build orphan cannot slip in). Everything else is Minor or Nit polish. The security-critical work — no-traversal asset serving and gate-FAILED-can't-slice — is correct, defense-in-depth, and tested.
