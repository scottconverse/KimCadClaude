# Engineering Deep-Dive — KimCad

**Audit date:** 2026-06-05
**Role:** Principal Engineer
**Scope audited:** Stage 4 — "React SPA shell + viewport" on branch `stage-0-7-audit-backfill` (head `b45298c`). Backend `src/kimcad/webapp.py` (routing, static-asset serving + path-traversal safety, JSON safety, concurrency/locking, the `geometry_version` stale-slice guard, the reopen re-gate `_regate_mesh`, cache eviction, error→HTTP mapping, and the two safety invariants); `frontend/src/api.ts` (the fetch seam); the React state model (`App.tsx`, `Workspace.tsx`, `useHashRoute.ts`); the 3D viewport (`Viewport.tsx`, `viewport/KCViewport.ts`); and the committed build at `src/kimcad/web/**`. Adjacent code read for call-site correctness: `pipeline.py`, `printer_connector.py`, `printability.py`, `config.py` (partial).
**Auditor posture:** Adversarial

---

## TL;DR

This is mature, defensively-written code. The two load-bearing safety invariants — a gate-failed mesh is never sliced or sent, and every send asserts `confirm is True` regardless of request body — are correctly enforced server-side and backed by direct tests (`test_webapp.py:64`, `:558`, `:1336`). The hardest concurrency case in the slice in this layer (a live-slider re-render landing mid-slice and a stale G-code being registered) is handled by the `geometry_version` stamp + a register-time version recheck, and it has a dedicated regression test. The static-asset and vendor routes reject path traversal at the boundary and are tested. Architecture is the right shape for a single-user loopback tool: a dependency-free `http.server` over a pure payload-mapping function, a code-split SPA that bundles three.js r184, hash routing with no server-side SPA fallback needed. No Blockers and no Criticals. The findings are a stale, unreferenced vendored three.js still exposed over HTTP, a build artifact with no drift guard against source, a handful of lock-discipline asymmetries that are benign under CPython today but fragile, and minor hygiene. Security posture for the threat model (localhost, single user) is sound.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 4 |
| Nit | 2 |

## What's working

- **The slice/send safety invariants are enforced where it counts — the server, not the UI.** `_handle_slice` (webapp.py:1679) and `_handle_send` (webapp.py:1241) both re-check `gate_status_by_rid[rid] == "fail"` and refuse, so a direct API client that never saw the hidden UI controls still can't dispatch a gate-failed part. The send path defaults the verdict to `"fail"` when a report is somehow absent (webapp.py:1397) — fail-closed. Verified by `test_web_refuses_to_slice_a_gate_failed_part` and the re-render-into-failure test (test_webapp.py:1336).
- **`confirm=True` is an identity check, not truthiness, and the web layer can't be tricked into downgrading it.** `ensure_sendable` uses `if confirm is not True` (printer_connector.py:200) and `_handle_send` always passes the literal `confirm=True` (webapp.py:1257). `test_web_path_always_sends_with_confirm_true` (test_webapp.py:558) pins that a body field `confirm:false` is ignored — exactly the regression a future refactor would introduce.
- **The mid-slice re-render race is actually closed.** Two locks (`slice_lock`, `render_lock`) plus a `geometry_version` counter that the slice captures (`sliced_ver`) and re-checks at register time (`_respond_slice`, webapp.py:1639); a re-render bumps the version and clears the cache under `lock` (webapp.py:1783-1788). A slice of the stale shape is refused with `reason:"stale"` rather than served. This is the kind of bug that ships silently and corrupts a print; it has a named test (test_webapp.py:1439).
- **Path-traversal defense at the boundary, mirrored across both static routes.** `_serve_asset` and `_serve_vendor` reject any name containing `/`, `\`, or `..` before touching the filesystem (webapp.py:924, 945), and `_serve_mesh`/`_serve_gcode` key off an `int(id)` into a server-built registry (no client-controlled path component reaches `open`). Tested for `..%2f`, subpaths, and empty names (test_webapp.py:315, 336).
- **Reopen/import is re-gated from the actual mesh, not trusted on stored metadata.** `_regate_mesh` (webapp.py:532) re-runs `validate_mesh` + `run_gate` on the copied mesh so a crafted `.kimcad` claiming `gate_status:"pass"` over an unprintable mesh is caught, with a deliberate fall-back-to-stored only when the geometry backends can't run (avoids false-failing a legitimate reopen).
- **JSON safety + uniform error contract.** `_json` serializes with `allow_nan=False` and maps a stray NaN/Inf to a clean 500 instead of emitting invalid JSON (webapp.py:790); bodies are size-capped before reading (webapp.py:978), non-object JSON bodies are rejected as 400 before handlers dereference them (webapp.py:1000), 405 carries an `Allow` header and the app's JSON error shape, and tracebacks are never leaked (class+message only).
- **Viewport lifecycle is disciplined.** `KCViewport.dispose` traverses the scene disposing geometries + materials, calls `renderer.dispose()` AND `forceContextLoss()` to release the WebGL context proactively (KCViewport.ts:315), removes every listener via a `cleanups` array, disconnects the `ResizeObserver`, and cancels the rAF + resume timer. `loadMesh` uses a `loadToken` to discard a superseded async load and dispose its orphaned geometry (KCViewport.ts:171-176). React-side, the design flow uses monotonic `designSeqRef`/`renderSeq` guards so a late/cancelled result can't apply into a fresh session (App.tsx:320, 335).

## What couldn't be assessed

- The TS/Vitest suite and `npm audit` were not executed in this pass (audit-only, no build run); three.js version was read from the committed lockfile/bundle (`0.184.0` / "r184" in the bundle) rather than from a live `npm audit`. The Python `test_webapp.py` coverage was read, not run.
- Real-browser runtime behavior (WebGL context exhaustion across many New-design cycles, actual memory retention) was inspected by code only — no live profiling. KCViewport's mitigations look correct, but the empirical leak question is a QA/runtime task.
- `printability.run_gate` / `validation.validate_mesh` internals were treated as a trusted boundary (read for signature/behavior, not re-audited — they belong to earlier stages).

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

### [ENG-401] — Major — Dependencies/Security — Stale, unreferenced vendored three.js (2010–2021) still exposed over HTTP at `/vendor/`

**Evidence**
`src/kimcad/web/vendor/three.min.js` carries the header `Copyright 2010-2021 Three.js Authors`. The Stage-4 SPA bundles its own three.js r184 (confirmed: `grep -c "vendor/three" src/kimcad/web/assets/*.js` → 0; the built bundle contains the string `three.js r184`). No HTML/TS/JS in `src/kimcad/web/` or `frontend/src/` references `/vendor/` any longer — the only remaining mention is a comment in `frontend/vite.config.ts:14` ("legacy three.js, still served at /vendor/"). Yet `webapp.py:844` still routes `/vendor/<name>` to `_serve_vendor`, which serves these files, and `test_webapp.py:315` still asserts the route works — so the dead path is pinned in place by a test.

**Why this matters**
A multi-year-old minified three.js is shipped and served by the running app even though the product no longer loads it. Old three.js releases have had advisories (e.g. prototype-pollution / ReDoS-class issues in loaders and font/SVG parsing over the years). Because the route is reachable on the loopback server, any future code (or a copy-paste of the route) that loads `/vendor/three.min.js` would silently pull a vulnerable, unmaintained copy instead of the bundled r184. It is also ~600 KB of binary committed into the Python package for no runtime purpose, and it actively misleads: a reader sees two three.js versions and can't tell which is live.

**Blast radius**
- Adjacent code: `_serve_vendor` (webapp.py:919-936) and the route dispatch at webapp.py:844; the three vendored files (`three.min.js`, `OrbitControls.js`, `STLLoader.js`); the pinning test `test_serves_vendored_threejs_and_rejects_traversal` (test_webapp.py:315) and the ETag test at test_webapp.py:971.
- Shared state: none — the route is self-contained.
- User-facing: none today (nothing loads it). The risk is latent.
- Migration: none. Removal is a clean deletion; package size drops ~600 KB.
- Tests to update: delete/repurpose test_webapp.py:315 and the vendor ETag test (test_webapp.py:971) — keep the traversal-rejection assertion by re-pointing it at `/assets/` (already covered at test_webapp.py:336, so the vendor traversal test is now redundant).
- Related findings: ENG-403 (build/source drift) — both stem from "the committed `web/` tree carries artifacts with no single source-of-truth check."

**Fix path**
Decide one of two, and make it explicit. (a) **Remove it** — delete `web/vendor/`, the `_serve_vendor` route, and its tests; drop the vite.config comment. This is the recommendation: the SPA self-bundles three, so the vendored copy has no consumer. (b) If `/vendor/` is meant as a deliberate offline-fallback contract, re-vendor the CURRENT three.js (r184) from `frontend/node_modules/three` so the served copy matches the bundle, add a build step that re-vendors on `npm run build`, and document the contract. Leaving a 2021 copy in place satisfies neither goal.

### [ENG-402] — Major — Architecture/Correctness — The committed SPA build (`src/kimcad/web/assets/**`, `index.html`) has no guard that it matches `frontend/src`

**Evidence**
`src/kimcad/web/assets/{kimcad.js,Workspace.js,index.css,*.woff2}` and `src/kimcad/web/index.html` are committed build output (the package serves them at runtime with no Node toolchain — `package.json` description and the webapp module docstring both state this). The build is produced by `npm run build` (`tsc --noEmit && vite build`) with a `prebuild` that `rimraf`s `../src/kimcad/web/assets`. Nothing in the Python tests, CI config, or a pre-commit/pre-push hook verifies the committed bundle was regenerated from the current `frontend/src`. `git status --porcelain` is clean at audit time (no live drift today), so the current commit is consistent — but consistency is maintained only by developer discipline. `index_html = (WEB_DIR / "index.html").read_bytes()` is also read ONCE at handler-construction (webapp.py:683), so a rebuild while the dev server runs serves the stale shell until restart.

**Why this matters**
This is the classic data-provenance trap the role brief calls out: the value the user sees (the entire frontend) is read from a checked-in artifact, not from source. A developer who edits `frontend/src/components/Viewport.tsx`, runs the TS tests (which pass against source), and commits WITHOUT `npm run build` ships a backend serving the OLD compiled UI — and every Python test still passes because they exercise `webapp.py`, not the bundle. The bug is invisible to the test suite and bites only when a human loads the page. For a beta whose bar is zero findings, "the shipped UI silently lags the source" is a real release hazard, even though the tree happens to be in sync right now.

**Blast radius**
- Adjacent code: the whole `frontend/src` → `src/kimcad/web/assets` build relationship; `index.html`'s hard-coded `/assets/kimcad.js` + `/assets/index.css` references (the lazy `Workspace.js` chunk is loaded dynamically, so a stale `index.html` that predates a chunk-name change would 404 the workspace).
- Shared state: the committed `web/` tree is the single artifact every runtime serve depends on.
- User-facing: a stale bundle means UI fixes/feature work appear "not shipped" despite a green build.
- Migration: none — additive guard.
- Tests to update: add a new check; existing tests unaffected.
- Related findings: ENG-401 (vendor staleness is the same root — committed artifacts with no freshness check).

**Fix path**
Add a drift guard the CI/pre-push hook runs: in a clean checkout, run `npm ci && npm run build` in `frontend/`, then `git diff --exit-code src/kimcad/web` — a non-empty diff fails the gate with "the committed SPA build is stale; run npm run build". That makes the artifact's provenance enforceable rather than aspirational. Separately (Minor, ENG-405), consider re-reading `index.html` per request in dev, or document that a rebuild requires a server restart.

### [ENG-403] — Minor — Correctness/Concurrency — Lock-free reads of shared registries in `_serve_mesh`/`_serve_gcode`

**Evidence**
`_serve_mesh` (webapp.py:957) and `_serve_gcode` (webapp.py:887) call `registry.get(...)` / `gcode_registry.get(...)` WITHOUT holding `lock`, while every writer (`_handle_design` webapp.py:1392, `_handle_render` webapp.py:1775, `_evict` webapp.py:729, reopen webapp.py:1531) mutates those same `OrderedDict`s under `lock`. The slice/send paths, by contrast, correctly take `lock` for their reads (webapp.py:1233, 1668).

**Why this matters**
Under CPython a single `dict.get` is atomic (the GIL protects it; a concurrent `popitem` on another thread won't corrupt a `.get` and won't raise — iteration is the only thing that can `RuntimeError`). So this is not a live bug today. It's an asymmetry that quietly assumes the GIL: the same code under a free-threaded (PEP 703 / 3.13t no-GIL) interpreter, or if `_serve_mesh` ever grew to read two registries together and reason about them, would have a real torn-read window. It reads as "the author knew to lock here (slice/send) but not there (serve)," which invites a future maintainer to mis-copy.

**Blast radius**
- Adjacent code: the four registry dicts and `_evict`; the GET serve handlers.
- User-facing: at worst a 404 on a mesh that was evicted the same instant (already handled — the code re-checks `.exists()`).
- Tests to update: none.

**Fix path**
Wrap the two `.get` reads in `with lock:` for consistency with the slice/send paths (the read is O(1) and the lock is held for microseconds — no contention on a single-user server). Cheap, and it removes the GIL assumption.

### [ENG-404] — Minor — Performance — `_serve_static` reads the whole file and SHA-256s it on every request (incl. the 304 path)

**Evidence**
`_serve_static` (webapp.py:896) does `body = path.read_bytes()` then `hashlib.sha256(body).hexdigest()` on every GET/HEAD, computing the ETag from scratch — including when the request carries a matching `If-None-Match` and will return a body-less 304. The largest asset is `Workspace.js` at ~565 KB; `kimcad.js` ~194 KB; the bundle is re-read and re-hashed on each load.

**Why this matters**
The whole point of the conditional-GET / 304 path is to avoid resending the body; here we still read AND hash the full file just to produce the ETag for comparison, so the 304 saves network but not disk+CPU. On a single-user loopback this is negligible in absolute terms (a few ms), so it's Minor — but it's wasted work on the hot asset path and trivially avoidable.

**Blast radius**
- Adjacent code: `_serve_static` and its two callers (`_serve_asset`, `_serve_vendor`).
- User-facing: marginal load latency only.
- Tests to update: the ETag tests (test_webapp.py:971, and the 304 assertions in the asset test) must still pass — an mtime+size ETag would change the ETag value but not the contract; verify those tests assert "an ETag is present and 304 works," not a specific hash.

**Fix path**
Since asset filenames are stable (un-hashed) and the files only change on rebuild, cache `(etag, body)` per path keyed on `(st_mtime_ns, st_size)` via `os.stat` — compute the hash once, serve from the cache thereafter, and skip the `read_bytes` entirely on a 304. Or, simpler, derive the ETag from `stat` (`f'"{mtime_ns:x}-{size:x}"'`) and only `read_bytes` when actually sending a body.

### [ENG-405] — Minor — Correctness — `index.html` is read once at startup; a rebuild during a running server serves the stale shell

**Evidence**
`index_html = (WEB_DIR / "index.html").read_bytes()` executes once inside `make_handler` (webapp.py:683) and is closed over by `do_GET` (webapp.py:809). The asset files, by contrast, are read per-request in `_serve_static`. So after a `vite build` regenerates `index.html` (e.g. if a chunk filename changed), a still-running server keeps serving the previous shell — which can reference an asset name that no longer exists.

**Why this matters**
Mostly a dev-loop papercut, and it slightly contradicts the per-request freshness of the assets. In production (a packaged release) the file never changes under a running process, so impact is low — hence Minor.

**Blast radius**
- Adjacent code: `do_GET` root handler; couples to ENG-402 (build drift).
- Tests to update: none.

**Fix path**
Read `index.html` per request (it's tiny) the same way assets are, or document the restart requirement. Reading per-request also lets it pick up a rebuilt shell without a server bounce.

### [ENG-406] — Minor — Hygiene — `MAX_REGISTRY` is overloaded as the cap for the mesh registry, the slice cache, AND the design-snapshot eviction chain

**Evidence**
`MAX_REGISTRY = 50` (webapp.py:45) bounds the mesh `registry` (webapp.py:1406, 1553) and is ALSO reused as the cap for `slice_cache` (webapp.py:1714). The slice cache is keyed by `(rid, printer, material)`, so its natural size is "designs × printer/material combos," a different quantity than "live designs." Using one constant for two semantically different bounds is a latent foot-gun.

**Why this matters**
Today both being 50 is fine. But if someone raises `MAX_REGISTRY` to keep more live designs, they'd unintentionally also grow the slice cache (each entry can hold a G-code path/dir), and vice-versa. The coupling is invisible at the constant's definition (the comment there only describes the mesh registry).

**Blast radius**
- Adjacent code: webapp.py:1406, 1553, 1714.
- Tests to update: none.

**Fix path**
Introduce a separate `MAX_SLICE_CACHE` constant (can default to the same value) so the two bounds can move independently and the intent is documented at the definition.

### [ENG-407] — Nit — Hygiene — `OrbitControls.js` is vendored but the SPA's KCViewport implements its own spherical-camera controls

**Evidence**
`src/kimcad/web/vendor/OrbitControls.js` is shipped, but `KCViewport.ts` rolls its own azimuth/polar/radius drag+wheel controls (KCViewport.ts:466-525) and never imports OrbitControls. Subsumed by ENG-401's "remove the vendor tree" recommendation; flagged once so the cleanup is complete.

**Fix path**
Remove alongside ENG-401.

### [ENG-408] — Nit — Architecture — A single global `render_lock`/`slice_lock` is correct for single-user but assumes it

**Evidence**
`render_lock` and `slice_lock` are global (not per-rid) by deliberate design (webapp.py:653-658 comment: "single-user/loopback, so contention across different designs is nil; key it by rid only if a multi-client mode lands"). The reasoning is sound and documented.

**Why this matters**
Not a defect — the choice is right for the threat/usage model and is annotated with the future trigger (ENG-503). Flagged only so the multi-client assumption is on the record: if KimCad ever serves more than one user, slicing design A would serialize behind slicing design B for no reason.

**Fix path**
None now. The existing comment already names the condition under which to revisit (per-rid locks). Keep it.

---

## Patterns and systemic observations

- **The committed `src/kimcad/web/` tree is an artifact directory with no provenance enforcement** — this is the single highest-leverage root. It produces ENG-401 (stale vendored three), ENG-402 (build-vs-source drift), ENG-405 (stale index.html), and ENG-407 (orphan OrbitControls). One coordinated fix — (1) a CI/pre-push "build is fresh" gate, (2) delete the unused `web/vendor/` tree, (3) read `index.html` per request — closes four findings and makes "what the server serves" provably equal to "what's in source."
- **Lock discipline is deliberate and well-commented where it's strict, and the one place it's loose (serve-path reads) is benign under CPython.** The codebase clearly understands its concurrency model (the `geometry_version` stale-slice guard is genuinely subtle and correct). ENG-403 is about consistency, not a live bug. This is a strong signal: the safety-critical paths got the careful treatment.
- **Safety invariants are tested at the server boundary, not just asserted in comments.** The gate-failed refusal, the `confirm is True` identity, and the mid-slice race all have named regression tests. This is exactly the discipline a release-quality beta needs, and it should be held as the standard for any new endpoint.
- **The error-mapping contract is uniform and honest:** typed soft outcomes (offline/auth/no-profile/stale) return 200 with a `reason` + plain-English `note`; unexpected failures return a clean 500 with class+message and never a stack; size limits return 413 with `close_connection`. A direct API consumer gets a consistent shape across every endpoint.

## Dependency snapshot

Runtime Python deps are pinned with floors in `pyproject.toml` and are mainstream (pydantic, trimesh, numpy, scipy, networkx, lxml, manifold3d, openai). The Stage-4-relevant frontend dep is three.js.

| Dependency | Version | Concern |
|---|---|---|
| three (bundled in SPA) | 0.184.0 (r184) | Current. No concern — this is the version the running UI uses. |
| three (vendored `web/vendor/three.min.js`) | ~2021-era (header "2010-2021") | **Stale + unreferenced + HTTP-exposed.** See ENG-401. Remove or re-vendor to r184. |
| OrbitControls.js (vendored) | matches the stale vendor three | Orphaned — KCViewport rolls its own controls. ENG-407. |
| react / react-dom | 18.3.1 | Current, no concern. |
| vite / vitest | 8.x / 4.x | Build-time only (never ships at runtime). No runtime concern. |

`npm audit` was not run in this pass (see "What couldn't be assessed"); recommend running it against `frontend/` as a routine gate. The bundled r184 is current, so the practical CVE surface in the SHIPPED UI is low.

## Appendix: artifacts reviewed

- `src/kimcad/webapp.py` (full, 1829 lines)
- `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/components/Workspace.tsx` (partial), `frontend/src/components/Viewport.tsx`, `frontend/src/viewport/KCViewport.ts`, `frontend/src/useHashRoute.ts`
- `src/kimcad/web/index.html`, `src/kimcad/web/assets/**` (listing + bundle grep), `src/kimcad/web/vendor/**` (listing + header)
- `src/kimcad/pipeline.py` (rerender + status/model-unreachable seams), `src/kimcad/printer_connector.py` (confirm/ensure_sendable seam)
- `pyproject.toml`, `frontend/package.json`, `frontend/vite.config.ts` (refs)
- `tests/test_webapp.py` (coverage survey: gate-failed refusal, traversal, confirm identity, mid-slice race, render value guards, ETag/304)
- `git status --porcelain` (drift check at audit time: clean)
