# Stage-4 Gate RE-AUDIT — Engineering Deep-Dive (Principal Engineer)

- Re-audit date: 2026-06-01
- Repo: `C:\Users\scott\dev\kimcad` working tree
- Branch: `stage-4-react-spa-shell`, head `fa39fdd` (verified `git rev-parse HEAD` = `fa39fddd98d7a6d52f6196018ea38797e70fcf0d`)
- Predecessor: the original Stage-4 engineering deep-dive (head `c65a42d`), which logged ENG-401..408 (Major 1, Minor 4, Nit 3).
- Method: I read the **current** code for every original finding (not the REMEDIATION claims), ran a fresh adversarial pass over the new fix code (the QA-001 HEAD path, the QA-002 ETag/304 path, the QA-003 startup rmtree, the QA-004 413 close, and the KCViewport changes), and re-verified the load-bearing invariants. Diff base: `c65a42d..fa39fdd`.

## Verdict at a glance

Every original ENG finding (ENG-401 through ENG-408) is genuinely resolved in the current code — verified against the actual source, not the remediation note. The fixes are tight and well-scoped; the adversarial pass on the new code turned up **no regressions** and **no new Blocker/Critical**. The load-bearing invariants (gate-FAILED-can't-slice, /assets and /vendor traversal guard, no XSS, no leaked sensitive data, build reproducibility) all still hold and are still tested.

**Re-audit severity counts: Blocker 0, Critical 0, Major 0, Minor 0, Nit 0.**

Stage 4 clears the engineering bar for merge.

## Checks I ran (and their results)

- `ruff check src tests` — **all checks passed**.
- `pytest -m "not live" -q` — **400 passed, 4 deselected** (the 4 are the `@pytest.mark.live` OrcaSlicer cases, intentionally skipped to avoid contending parallel slicer runs; they are covered by the live gate in `ci.sh`).
- `npm --prefix frontend run build` — clean: `tsc --noEmit` passes, Vite build succeeds (31 modules; `kimcad.js` 147 kB, `Workspace.js` 536 kB lazy chunk, `index.css` 13.8 kB, 3 woff2 fonts).
- Build reproducibility: `git diff --quiet -- src/kimcad/web` after a fresh build — **no drift** (committed build == fresh build). This is now also a hard gate in `scripts/ci.sh`.
- `npm --prefix frontend run test` (vitest) — **19 passed across 5 files** (includes the new jsdom component tests).
- `npm --prefix frontend audit` — **0 vulnerabilities**.
- XSS sink sweep over `frontend/src` (`innerHTML`, `dangerouslySetInnerHTML`, `eval`, `new Function`, `document.write`, `outerHTML`, `insertAdjacentHTML`) — **no matches**.

## Part 1 — Verification of original findings (ENG-401..408)

### ENG-401 (Major) — orphan-asset / build-reproducibility gate → **RESOLVED**

The fix is the stronger of the two options the original finding offered (promote the reproducible-build property into a gate, rather than just documenting that builds must go through npm).

Evidence — `scripts/ci.sh` (the frontend block): when `frontend/node_modules` and `npm` are present it runs vitest, then runs a fresh `npm --prefix frontend run build`, then asserts `git diff --quiet -- src/kimcad/web` and **exits non-zero on any drift** (printing a `--stat`). This asserts the committed `src/kimcad/web` is byte-identical to a fresh build, and fails the push on any drift — catching an orphan regardless of how the build was invoked (the exact gap the original finding named: a bare `vite build` that skips the prebuild hook would now produce drift and be caught). The `prebuild` step (`rimraf ../src/kimcad/web/assets`, confirmed in the build output) still runs before each npm build. I verified the property holds right now: a fresh build produced zero drift. On a toolchain-less box the check skips with a printed note, but `KIMCAD_RELEASE=1` hard-fails so a release tag can never be cut without this gate having run. Resolved, and resolved the right way.

### ENG-402 (Minor) — registry/gate reads outside the lock → **RESOLVED**

Both call sites now take a consistent snapshot under `lock`.

Evidence — `webapp.py` `_handle_send` (~line 586): a `with lock:` block reads `gcode_registry.get(rid)` and `gate_status_by_rid.get(rid) == "fail"` together into `gcode_path` and `gate_failed`.

Evidence — `webapp.py` `_handle_slice` (~line 699): a `with lock:` block reads `registry.get(rid)` and `gate_status_by_rid.get(rid) == "fail"` together into `mesh_path` and `gate_failed`.

The asymmetry the original finding flagged (writes locked, reads not) is gone — reads of the shared registries are now under the same `lock` the writers (`_handle_design`, `_evict`) use, and the gate verdict + path are captured as one snapshot so a maintainer adding a compound read here is protected. The downstream `gate_failed` boolean replaces the prior inline `gate_status_by_rid.get(rid) == "fail"` at the use site. Resolved.

### ENG-403 (Minor) — `dispose()` does not `forceContextLoss()` → **RESOLVED**

Evidence — `frontend/src/viewport/KCViewport.ts` (~line 165-168): `this.renderer.dispose()` is immediately followed by `this.renderer.forceContextLoss()`, with a comment that it proactively releases the WebGL context rather than waiting for GC (matters under StrictMode's dev double-mount and repeated New-design cycles). Ordering is correct (dispose the renderer's own resources, then force-lose the context). Resolved.

### ENG-404 (Minor) — grid/plate rebuilt per construction → **NO-ACTION confirmed reasonable**

The original finding itself recommended no action ("Keep as-is; the per-instance build keeps dispose simple and correct"). I re-verified the underlying claim in the current code: `buildPlate(256)` (`KCViewport.ts` ~184-205) adds the `GridHelper` and the border `Line` to `this.scene`, and `dispose()`'s `scene.traverse` (~158-164) disposes every geometry and material it reaches, including the grid and the border line. No leak; the allocation is a static 16×16 grid plus a 5-point line — negligible. NO-ACTION is the correct call.

### ENG-405 (Minor) — octet-stream fallback for unknown asset suffixes → **RESOLVED (documented)**

Evidence — `webapp.py` `_serve_asset` doc comment (~454-457) now states the ENG-405/406 rationale: an unknown suffix falls back to `application/octet-stream` (a safe default — the SPA build only emits the mapped types), and names `_ASSET_CONTENT_TYPES` as the single source for asset content types. The behaviour is unchanged (it was already the safe default); the fix is the documentation the finding asked for, so the map and the Vite emit list stay in sync by inspection. Resolved.

### ENG-406 (Nit) — content-type-map asymmetry undocumented → **RESOLVED (documented)**

Same comment block (`webapp.py` ~454-457) plus the `_ASSET_CONTENT_TYPES` table comment (~46-48) now document the intentional per-route content-type maps and the single-source map. Nit closed.

### ENG-407 (Nit) — `chunkSizeWarningLimit 700` magic number → **NO-ACTION confirmed reasonable**

The original finding said "none needed; the comment already justifies it." That remains true — `vite.config.ts` carries the rationale comment, and the current `Workspace.js` (536 kB) is under 700. NO-ACTION is correct; raising it would only weaken the signal.

### ENG-408 (Nit) — CI frontend gate skips silently → **RESOLVED**

Evidence — `scripts/ci.sh` (the frontend skip branch): when the toolchain is absent it prints a SKIP note, and under `KIMCAD_RELEASE=1` it now `exit 1`s with a "RELEASE GATE: refusing — frontend toolchain absent, the SPA gate is unproven" message. This is the same release-flag hard-gate escalation the live-slicer gate already has: a normal dev push on a toolchain-less box still skips, but a release tag can't be cut without the SPA tests + build-reproducibility check having actually run. This is the exact symmetry the original finding suggested. Resolved.

## Part 2 — Fresh adversarial pass on the fix code (regression hunt)

I scrutinized every new code path introduced by the remediation. No regressions found. Detail per area:

### QA-001 — `do_HEAD` → `do_GET` with `_head_only` body suppression: **safe, no body leak, no unsafe side effect**

`do_HEAD` (`webapp.py` ~325-333) sets `self._head_only = True`, calls `do_GET()`, and clears the flag in a `finally`. The body is suppressed in the three — and only three — body-writing helpers. I grepped `wfile.write` across the file: exactly 3 sites (`_send`, `_send_download`, `_serve_static`), and **all three** guard the write with `if not getattr(self, "_head_only", False)`. There is no GET path that writes a body outside these helpers:
- `_send` ← `_json`, the index/HTML path, `_serve_mesh`. Guarded.
- `_send_download` ← `_serve_gcode`. Guarded.
- `_serve_static` ← `_serve_asset`, `_serve_vendor`. Guarded (200 path) and the 304 path returns early with no body anyway.

The `finally` guarantees the flag is reset even if `do_GET` raises, so a HEAD that hits an error path can't leave `_head_only` stuck True on a (recycled) handler instance. HEAD-triggered side effects: the only routed handler with an external effect is `/api/connector-status/<name>`, which builds a connector and calls `connector.status()` — a read-only status poll, idempotent and safe to run on HEAD. No state mutation, no slice, no send is reachable via GET/HEAD (those are POST-only). Tested: `test_head_returns_headers_without_body` asserts a header-only 200 with `Content-Length > 0` and an empty body. **No finding.**

### QA-002 — `_serve_static` ETag / 304: **correct**

`_serve_static` (`webapp.py` ~409-430): the ETag is a quoted strong validator derived from a sha256 of the actual served bytes (first 16 hex chars), so it changes with content (never stale after a rebuild). The `If-None-Match` compare is an exact string match against that same quoted form, which is correct for a single strong ETag. On a match it sends 304 with the ETag, `Cache-Control: no-cache`, `Content-Length: 0`, and **no body**. On a miss it sends 200 with Content-Type, Content-Length, ETag, `Cache-Control: no-cache`, and the body (suppressed under HEAD). `no-cache` (revalidate-every-time) with a content ETag is the right caching policy for stable un-hashed filenames. Both `_serve_vendor` and `_serve_asset` route through it, so the traversal guard (checked before the call) is preserved. Tested: `test_static_assets_carry_an_etag_and_revalidate_304` confirms the ETag round-trips to a body-less 304. **No finding.**

### QA-003 — startup `shutil.rmtree` of numeric dirs: **cannot delete anything it shouldn't**

`make_handler` (`webapp.py` ~261-267) does `web_root.mkdir(parents=True, exist_ok=True)` then, for each child of `web_root`, `shutil.rmtree(child, ignore_errors=True)` only when `child.is_dir() and child.name.isdigit()`.

The blast radius is bounded to **direct children of `web_root` whose name is all-digits**. Critically, `web_root` is the *runtime* output dir (`output/web`, set at `serve()`), which is a **different path** from `WEB_DIR` (`src/kimcad/web`, the committed SPA artifact). So this loop never touches the committed `assets/`, `vendor/`, or `index.html` — those live under `WEB_DIR`, not `web_root`. It only removes per-design dirs named `str(rid)` (rid from `itertools.count(1)`, always ASCII digits) that a previous session created and the fresh session's reset registry no longer references. A stray non-numeric dir under `output/web` is left alone; a non-existent `web_root` is created first by `mkdir`. The one theoretical curiosity — `str.isdigit()` is True for some non-ASCII digit characters — is not reachable: KimCad only ever creates ASCII-digit dirs here, and there's no attacker-controlled path into this loop (it runs once at handler construction). Tested: `test_evicted_design_dir_is_removed_from_disk` covers the eviction sibling (`_evict` removing `web_root/str(rid)`). **No finding.**

### QA-004 — `close_connection` on 413: **correct**

`_read_json_body` (`webapp.py` ~491-496): when the declared `Content-Length` exceeds `MAX_BODY_BYTES`, it sets `self.close_connection = True` **before** sending the 413, so the server tears the connection down rather than treating it as a keep-alive turn. This is the right move: the server rejects without draining the (potentially huge) upload, so a client still streaming the body would otherwise desync the keep-alive stream and hit a connection-abort while reading the response. Tested: `test_oversize_content_length_rejected_with_413` (sends an oversized Content-Length with no body and still gets a clean 413). **No finding.**

### KCViewport changes — bbox/labels: **no leak, bounded per-frame cost**

- **bbox disposal:** `buildBBoxAndDims()` (`KCViewport.ts` ~208-245) adds a `LineSegments` (12-edge wireframe) to `this.modelGroup`. `removeModelChildren()` (~173-182) iterates `[...this.modelGroup.children]`, removes each, and disposes its geometry + material (with array-material handling). So the bbox, the mesh, and the edge-overlay `LineSegments` are all disposed on the next `loadMesh`/`clearModel`. `dispose()`'s full-scene traverse (~158-164) is the backstop. The original question — "is the bbox added to modelGroup disposed by removeModelChildren?" — answer: **yes**. No GPU-resource leak across re-loads.
- **per-frame label projection:** `updateLabels()` runs every frame from `loop()`. It clones+projects 3 anchor `Vector3`s and writes `opacity`/`transform`/`textContent` on 3 DOM pills. The 3 clones are short-lived (GC'd), not retained — no leak. The DOM writes touch only `opacity` and `transform` (compositor-only properties, no layout thrash) plus `textContent` on a `<span>`; with a single persistent viewport this is negligible. Label text uses `textContent`, not `innerHTML` — no XSS surface, and the values are numeric dims anyway. No leak, no meaningful perf regression. **No finding.**

### Re-verification of the load-bearing invariants

- **gate-FAILED-can't-slice — STILL HOLDS, three layers:** server slice refusal `webapp.py` ~707-711 (sliced False / reason gate_failed / no G-code), server send refusal ~594-598, UI hides the slice control `ExportPanel.tsx` (~68, ~69-74, ~106-110). The fail-closed default (the stored gate status defaults to `"fail"` when a report is absent, ~668) is intact. Tested server-side (`test_web_refuses_to_slice_a_gate_failed_part`) **and now in the rendered UI** (`ExportPanel.test.tsx`: a failed part shows no slice button but keeps the model download). The remediation strengthened this with the component test.
- **/assets and /vendor traversal guard — STILL HOLDS:** the name guard (reject empty / forward-slash / backslash / double-dot) is unchanged in both `_serve_asset` and `_serve_vendor`; the refactor that routes the read into `_serve_static` happens **after** the guard, so the guard is never bypassed. Tested: `test_serves_spa_index_and_assets_and_rejects_traversal` and `test_serves_vendored_threejs_and_rejects_traversal` (both cover `nope.js`, trailing-slash, `sub/x.js`, and `..%2fx` → 404).
- **No XSS — STILL HOLDS:** zero sinks in `frontend/src` (fresh grep over `innerHTML`/`dangerouslySetInnerHTML`/`eval`/`new Function`/`document.write`/`outerHTML`/`insertAdjacentHTML`); the new label code uses `textContent`.
- **No leaked sensitive data — STILL HOLDS:** the connector-status and send error branches return a typed `reason` + a generic user `note`, never a stack trace; the unexpected-error branches show only `type(e).__name__` plus the message, no traceback, and that contract is tested (`test_connector_status_unexpected_error_is_not_5xx` asserts the dev detail string is not present in the payload).
- **Build reproducibility — STILL HOLDS:** verified above (no drift after a fresh build), now a hard CI gate.

## What's working (credit where due, post-fix)

- The ENG-401 fix took the stronger remediation path (a build-reproducibility CI gate, not just a doc note), turning the property the original audit verified by hand into something a push can't bypass. That's the highest-leverage fix in the batch and it was done right.
- The HEAD implementation is the clean approach — reuse `do_GET` unchanged and suppress the body at the single chokepoint (the three write helpers), rather than duplicating routing for HEAD. The `finally` reset and the `getattr(..., False)` default make it robust to error paths and to handler reuse.
- The ETag fix is a content hash with `no-cache` revalidation — exactly the correct policy for the project's deliberate stable-filename build, and it composes cleanly with the existing traversal guard.
- Test coverage grew with the fixes, not after them: 400 non-live Python tests and 19 vitest cases including new jsdom component tests that pin the gate-aware UI behaviour. The HEAD, ETag/304, 413, and disk-eviction fixes each ship with a dedicated test.
- No new dependencies of concern: `npm audit` still 0, the only frontend additions are the jsdom + Testing Library dev-deps for the component tests.

## What I could not check (disclosed)

- I did not run the 4 `@pytest.mark.live` OrcaSlicer cases in this pass (per the brief — to avoid contending parallel live slicer runs). They are gated by `ci.sh` and were reported green in the remediation's full `bash scripts/ci.sh` run; the contract they cover (`test_live_web_design_then_slice_then_download`) is unchanged by these fixes, which are all in the HTTP/serving/viewport layers, not the slicer path.
- I did not drive the SPA in a live browser this pass (the UX-fix rendered screenshots are the QA/UI-UX role's lane and were captured in the remediation's desktop+mobile pass). My KCViewport analysis is by code reading plus the disposal/leak reasoning above.

## Bottom line for the gate

All eight original engineering findings (ENG-401..408) are genuinely resolved in the current code at head `fa39fdd` — verified against the source, not the remediation note. The adversarial pass on the fix code found no regressions and no new findings at any severity. Engineering counts are **0/0/0/0/0**. Stage 4 clears the engineering bar for merge + tag.
