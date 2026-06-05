# Engineering Deep-Dive — KimCad Stage 8.5 (Usability) Stage Gate

- **Role:** Principal Engineer
- **Scope:** repo `C:\Users\scott\dev\kimcad`, branch `stage-8.5-usability` @ `95b25e0` (to merge → `main`, tag `stage-8.5`)
- **Date:** 2026-06-05
- **Method:** static review of the whole-stage diff (`main...stage-8.5-usability`, ~20k lines across 141 files), full read of the backend modules in scope, the new stores, the photo/vision seed path, and the load-bearing frontend surfaces (SettingsPanel, ExportPanel, PhotoOnramp, ChatPanel). Ran `ruff check src/` (clean), the full Python non-live suite, and the frontend vitest suite. Did **not** start the web server (covered by the QA role + the completed wiring-audit at `docs/audits/stage-8.5/stage-gate-2026-06-05/wiring-audit-stage-8.5-2026-06-05.md`).

## Verification environment note (read this first)

The audit machine's Python environment was **missing three declared runtime dependencies** — `scipy`, `networkx`, `manifold3d` (all pinned in `pyproject.toml` lines 19-26). With them absent, **32 tests failed**: `auto_orient` doesn't lay parts flat, watertight/body-count checks degrade, and `trimesh.load()` of the rendered 3MF can't build a scene graph — cascading into `test_geometry`, `test_templates`, `test_library_modules`, `test_pipeline_readiness`, and two `test_webapp` template/render tests. **After installing the declared deps, the full non-live suite is green: 757 passed, 0 failed, 7 skipped, 4 deselected.** The frontend suite is **249 passed / 22 files**. These failures were 100% environmental and are **not** Stage 8.5 regressions. (See ENG-007 — the dev-setup story should make this trap impossible to fall into.)

`ruff check src/` — **All checks passed.**

---

## Load-bearing invariant verdicts

Each invariant was traced to code. Verdict + evidence:

### 1. Local-first; cloud OFF by default; key masked, never logged or in the repo — **HOLDS**

- Cloud is opt-in and **fails to local on every gap**: `_SettingsAwareProvider._active()` (`src/kimcad/webapp.py:369-390`) returns the local provider unless `cloud_enabled` AND a non-empty `openrouter_api_key` AND a non-empty `cloud_model` are all present; a cloud-build exception also degrades to local (`388-389`).
- The UI default is OFF with an explicit privacy callout: `SettingsPanel.tsx:264-290` ("This sends your prompt off your machine. Off by default…"), switch `aria-checked` driven by `settings.cloud_enabled`.
- The key is **only ever returned masked** — `_mask_key()` (`webapp.py:408-416`) returns a fixed dot-run + last 5 chars, and reveals nothing for an implausibly short value; `settings_response()` sets `cloud_key_masked` and a boolean `has_cloud_key` but never the raw key (`419-429`). The POST handler stores it (`1089-1095`) but the GET never echoes it.
- The key is **never logged**: the only `print()`/stderr writes in `webapp.py` are the server banner (`1713-1718`); `llm_provider.py`'s fallback log prints the backend *key name*, not the API key (`350-354`). No logging of `openrouter_api_key` anywhere.
- The key never lands in the repo: `settings_store.py` writes to `~/.kimcad/settings.json` (`config.py:156-166`), a per-user path outside the repo, and `_ALLOWED_KEYS` (`settings_store.py:35-47`) bounds what is persisted.
- **Vision is always local even when cloud TEXT is enabled**: `_SettingsAwareProvider.describe_photo()` (`webapp.py:398-405`) builds a *dedicated local* `LLMProvider` rather than routing through the cloud — the photo never leaves the machine. The PhotoOnramp UI states this honestly (`PhotoOnramp.tsx:176-180, 197`).

### 2. gemma4:e4b is the only default model; no UI offers an alternative or a Chinese model — **HOLDS**

- Config default backend is `active: local` → `gemma4:e4b` (`config/default.yaml:29,48`). The `local_codegen` (qwen2.5-coder) backend exists but is commented as evaluated-and-REJECTED and is not active (`default.yaml:60-62`).
- The model-status endpoint hardcodes `gemma4:e4b` as the fallback name (`webapp.py:1019`) and never enumerates alternatives.
- The SPA shows gemma4:e4b as **THE** model with a health readout, no dropdown of choices: `SettingsPanel.tsx:216-262`, `FirstRunWizard.tsx:16-17, 210, 387`. Tests assert this explicitly: `FirstRunWizard.test.tsx:44-51` ("shows gemma4:e4b as THE model … never qwen", `queryByText(/qwen/i)` is null); `SettingsPanel.test.tsx:99-100`.
- The built bundle confirms it: only `gemma4:e4b` appears in `web/assets/*.js`; no `qwen` string.
- The `model_advisor.py` catalog (which *does* list Qwen entries) is **CLI-only** — referenced from `cli.py`/`bakeoff.py`, never from `webapp.py` or any frontend component. Its Stage 8.5 diff only refactored `_parse_tags` and added `probe_ollama`; `recommend()` and the catalog were untouched.

### 3. A gate-FAILED part is never sliced or sent (server-side); per-send confirm is identity; raw codegen runs only through the sandbox and never bypasses the Gate — **HOLDS**

- **Server-side gate enforcement, not just hidden UI:** `_handle_slice` reads `gate_status_by_rid` under `lock` and returns `sliced:false, reason:gate_failed` before any slice (`webapp.py:1587-1599`). `_handle_send` does the same belt-and-suspenders check (`1168-1180`) even if a gcode entry somehow existed. The verdict is stored fail-closed: `gate_status_by_rid[rid] = rep.get("gate_status") or "fail"` (`1332`, `1464`, `1675`).
- **Confirm is identity:** `ensure_sendable()` enforces `if confirm is not True: raise NotConfirmed` (`printer_connector.py:200`), and every connector's `send` calls it first (loopback/moonraker/octoprint/prusalink). `_handle_send` passes the literal `confirm=True` (`webapp.py:1192`) only after the gate check. The MCP path deliberately passes the raw value through to the `confirm is not True` gate and warns against `bool()`-coercion (`mcp_server.py:192-194`).
- **Raw codegen is sandboxed and gated:** the experimental LLM-OpenSCAD path runs through `_build_geometry` → `self.renderer` → `render_scad()` (`openscad_runner.py:244-299`), which **always** calls `sanitize_scad()` (blocks `minkowski`, `import`/`surface` file-I/O, and `use`/`include` outside `library/` — `202-225`), runs the binary with `cwd=out_dir` isolation + timeout + `max_output_bytes` cap, and the result still flows into `run_gate()` (`pipeline.py:798, 853`). There is no code path that emits geometry skipping the sanitizer. The experimental generator is **OFF for the consumer by default**: `allow_experimental` defaults to the request flag OR the saved `experimental_enabled` setting (`webapp.py:1270-1272`); the SPA sends `experimental:false` and *offers* the generator on a template miss (`needs_experimental` → `ChatPanel.tsx:196-208`) rather than auto-running it.

### 4. Re-render is deterministic (no model call) and invalidates the slice/G-code cache — **HOLDS**

- `Pipeline.rerender()` rebuilds from the template family + clamped values with **no provider call** and no prompt (`pipeline.py:647-714`); `_build_from_template` emits `match.scad()` (a pure function) and renders once (`813-854`).
- `_handle_render` invalidates the stale slice **and** G-code under `lock`: `gcode_registry.pop(rid, None)` and clears every `slice_cache` key for that rid after the geometry changes (`webapp.py:1676-1680`), refreshes the gate verdict (`1675`), and appends a cache-busting `?v=` to the mesh URL (`1691`). The mesh is exported atomically (`pipeline.py:496-498`, temp + `os.replace`) so a concurrent reader never sees a half-write.
- **Caveat:** the invalidation is correct *within* a render, but a render and a slice for the same `rid` are not mutually serialized — see **ENG-001 (Major)**, the one real hole in this invariant under concurrency.

### 5. HTTP-layer concurrency/safety — **MOSTLY HOLDS** (one Major: ENG-001)

- Registries/caches are bounded LRU and evicted in lockstep via `_evict` (`webapp.py:675-686`); reads of shared state take `lock` for a consistent snapshot (`1168`, `1587`). `MAX_REGISTRY`/`MAX_BODY_BYTES`/`MAX_IMPORT_BYTES`/`MAX_PHOTO_BYTES` cap memory (`44-52`).
- **Job-id validation:** `_valid_job_id` constrains the progress key to `[A-Za-z0-9-]{1,64}` (`203-207`); progress slots are bounded + LRU-evicted (`1297-1298`) and always cleared in a `finally` (`1320-1325`).
- **Path-traversal safety:** `/api/mesh` and `/api/gcode` resolve the id via `int(raw_id)` into an in-memory registry — no filesystem path is ever built from client input (`890-902`, `820-829`). `/assets` and `/vendor` reject any `/`, `\`, or `..` before touching disk (`854-888`). The design store guards the one client-supplied id with `_safe_id` (ASCII token, no separators — `design_store.py:326-330`).
- **No traceback leakage:** every handler maps unexpected errors to `{"error": "Class: msg"}` (class+message, never a stack) — `1202-1206`, `1318`, `1622-1623`, `1666-1667`; the design POST maps an Ollama drop to a typed `model_unavailable` status instead of a 500 (`1303-1317`).
- **Socket hardening:** `Handler.timeout = 30` defeats slowloris (`688-692`); oversized bodies are rejected before reading with `close_connection = True` (`913-919`).

### 6. Slice-10 weight estimate (volume × density) + Material.density — correctness & honesty — **HOLDS**

- The slicer's *own* grams (from the profile's real density) are preferred; KimCad estimates only when the profile reports none: `_estimate_detail_with_weight` (`webapp.py:486-504`) sets `filament_g = round(cm3 * density, 1)` **only** when `cm3 > 0` and a positive `density` exists, and sets `filament_g_estimated = True`.
- A degenerate `cm3 == 0` is explicitly kept `None` so the UI never shows "0.0 g (estimated)" (`499-502`).
- `Material.density` is typed `float | None` (`config.py:48-50`) with realistic nominal values (PLA 1.24, PETG 1.27, TPU 1.21, ABS 1.04 — `default.yaml:153-156`), documented as nominal/estimated.
- The UI is honest: `formatFilamentWeight` returns null for non-finite/≤0 (`printEstimate.ts:16-19`); the estimated caption only renders when there is actually a weight row (`ExportPanel.tsx:210-211, 254-259`). No fabricated numbers — every estimate row is omitted rather than zero-filled (`printEstimate.ts:32-46`).

---

## Findings

### ENG-001 — Major — Correctness/Concurrency — A slice and a re-render of the same design are not mutually serialized; a stale-geometry G-code can be registered after invalidation

**Evidence:** `slice_lock` (`webapp.py:598`) serializes slices against slices; `render_lock` (`604`) serializes renders against renders — but they are *different* locks, so a slice and a render for the same `rid` can interleave. Sequence:

1. `_handle_slice` slices the **current** geometry, releases `slice_lock`, and holds `gcode_path` locally (`1609-1629`), having not yet registered it.
2. `_handle_render` for the same `rid` re-renders new geometry and, under `lock`, runs `gcode_registry.pop(rid, None)` + clears `slice_cache[rid]` + replaces `registry[rid]` with the new shape (`1671-1687`).
3. `_handle_slice`'s `_respond_slice` then executes `gcode_registry[rid] = gcode_path` under `lock` (`1564-1565`) — re-registering the **pre-reshape** G-code *after* the render's invalidation.

The result: `gcode_registry[rid]` points at G-code sliced from the old shape while `registry[rid]` is the new shape. A subsequent `/api/gcode/<rid>` download or `/api/send/<rid>` serves/sends a slice of the geometry the user already changed away from — the exact "stale slice served/sent" failure invariant 4 is meant to forbid.

**Why this matters:** It is the one concurrency hole in the slice/render safety story. In the shipped single-user loopback SPA it's hard to hit (the UI disables Slice while slicing and re-renders are slider-driven), so exposure is low — but it is reachable by a direct API client or by fast alternating interactions, and the consequence (printing the wrong shape) is exactly the high-cost outcome the gate architecture exists to prevent. The send path *does* re-check `gate_status` (`1170`), which limits blast radius to a *gate-passing* stale shape, not a gate-failed one.

**Blast radius:**
- Adjacent code: `_handle_slice` (`1572-1629`), `_handle_render` (`1631-1692`), `_respond_slice` (`1561-1570`), `_handle_send` (`1156-1221`). All four touch `gcode_registry`/`slice_cache` for a shared `rid`.
- Shared state: `gcode_registry`, `slice_cache`, `registry`, `render_lock`, `slice_lock`.
- User-facing: only under concurrent slice+render of one design; no change to the normal sequential flow.
- Migration: none.
- Tests to update: `test_webapp.py::test_rerender_invalidates_a_cached_slice` asserts the single-threaded invalidation; a new test should interleave a slice that completes *after* a render to lock in the fix.
- Fix path: have `_handle_render` and `_handle_slice` take the **same** lock for the per-rid critical section, or stamp each design with a monotonically increasing geometry-version (bump it on render) and have `_respond_slice` register the G-code only if the version it sliced still matches the current one (drop it otherwise). The version-stamp approach keeps slices and renders concurrent across *different* designs while closing the same-`rid` race.

### ENG-002 — Major — Data provenance — Reopened/imported designs are trusted from stored metadata and never re-gated; a crafted `.kimcad` import can mark a non-printable mesh as gate-passed

**Evidence:** On reopen, the gate verdict is read straight from the stored record — `gate_status_by_rid[rid] = d.gate_status or "fail"` (`webapp.py:1464`) — with no re-run of `run_gate` against the copied mesh. `import_bytes` (`design_store.py:269-297`) writes the imported `mesh.stl` and `meta.json` as-is (zip-slip-safe, but it does **not** validate that the stored `gate_status` matches the mesh). A `.kimcad` file authored with `gate_status: "pass"` over an unprintable mesh is therefore reopenable *and* sliceable (the slice gate at `1595` consults the trusted stored value).

**Why this matters:** The Printability Gate is the load-bearing safety mechanism, and reopen/import is a new Stage 8.5 trust boundary that bypasses it. In a single-user local app the file is the user's own, so this is not a remote-exploit vector — but provenance discipline says a persisted artifact reconstituted into the live slice/send path should be re-validated, not taken on faith from its own metadata. The slicer's own G-code proof (`prove_gcode_3mf`) is a partial backstop (it rejects motion-free slices), but it does not re-assert printability.

**Blast radius:**
- Adjacent code: `_handle_design_reopen` (`webapp.py:1442-1491`), `DesignStore.import_bytes` (`design_store.py:269-297`), `_handle_slice`/`_handle_send` gate reads.
- Shared state: `gate_status_by_rid`, the per-design `meta.json` schema.
- User-facing: reopened/imported designs would, after the fix, re-run the gate (a brief render) before becoming sliceable; an imported junk file would correctly refuse to slice.
- Migration: none (additive enforcement); existing saved designs already carry an honest `gate_status` from their original build.
- Tests to update: `test_design_store.py` import tests; add a "reopen re-gates the mesh" case.
- Fix path: on reopen (and after import), re-run `run_gate` against the copied mesh (or at minimum re-derive watertightness/volume) and store *that* verdict into `gate_status_by_rid`, rather than trusting `d.gate_status`. If a full re-gate is too slow for reopen, mark a reopened design "needs re-validation before slice" and re-gate lazily on the first slice request.

### ENG-003 — Minor — Correctness/Robustness — HTTP JSON responses don't set `allow_nan=False`; a non-finite numeric field would emit invalid JSON the browser rejects

**Evidence:** The stores correctly use `allow_nan=False` (`design_store.py:345`, `settings_store.py:54`, `history.py:127`, `printproof3d.py:83-86`), but the live API response serializer does not: `_json` → `json.dumps(obj)` (`webapp.py:731`) and the 405 body (`701`). If any payload number were `NaN`/`Infinity` (e.g. a degenerate `volume_mm3`, a bbox axis, a readiness score), Python emits the literal tokens `NaN`/`Infinity`, which are invalid JSON; the SPA's `readJson` then throws "KimCad returned an unreadable response" (`api.ts:166-172`) — a confusing failure with no actionable cause.

**Why this matters:** Low exposure (upstream geometry is validated and `_report_payload` rounds values), but `round(float('nan'), 1)` is still `nan`, so a single non-finite leak turns a successful design into an opaque client error. It's a one-line hardening that matches the discipline already applied in the stores.

**Fix path:** route all API responses through a single serializer that passes `allow_nan=False` and, on a `ValueError`, returns a clean `{"error": …}` 500 — so a non-finite value surfaces as a named error rather than corrupt JSON.

### ENG-004 — Minor — Architecture/Correctness — `FallbackProvider` has no `describe_photo`; a future caller wiring vision through it would raise

**Evidence:** `describe_photo` is defined on `LLMProvider`, `DemoProvider`, and `_SettingsAwareProvider`, but **not** on `FallbackProvider` (`llm_provider.py:299-374`). Today the web photo path is safe because `_SettingsAwareProvider.describe_photo` builds its own local provider and never delegates to the wrapped `FallbackProvider` (`webapp.py:398-405`), and `_handle_photo_seed` catches everything → 422 (`1238-1240`). But the `Provider` Protocol (`llm_provider.py:71-90`) doesn't even declare `describe_photo`, so this gap is invisible to type-checking and is a latent trap for any future code that calls `provider.describe_photo` on a fallback-wrapped provider.

**Why this matters:** Not a current bug (no live path hits it), but a correctness landmine: the contract is partial and the omission isn't caught by the type system. Cheap to close.

**Fix path:** add `describe_photo` to the `Provider` Protocol and implement it on `FallbackProvider` (delegating to `self.primary.describe_photo`, with the same primary→alt handling, or routing local per the trust rule). This makes the contract total and type-checked.

### ENG-005 — Minor — Security/Robustness — `_SettingsAwareProvider._cloud_cache` is keyed by `(key, model)` and unbounded; rotating keys/models slowly accumulates provider objects (and key material) in memory

**Evidence:** `self._cloud_cache: dict[tuple[str, str], Any]` (`webapp.py:359`) caches a built cloud provider per `(api_key, model)` and is never evicted (`378-387`). Each entry retains the full API key as a dict key for the process lifetime. A user who replaces their key or tries several model slugs accumulates one entry each.

**Why this matters:** Low impact (the design call is rare; entries are few), but unbounded caches of secret-bearing objects are worth bounding on principle, and it's inconsistent with the careful LRU caps everywhere else in this file (`MAX_REGISTRY`, progress slots, slice cache).

**Fix path:** cap the cache (e.g. `OrderedDict` with a small max, LRU-evict) or simply key it by `model` and rebuild on key change — the build cost is trivial relative to a multi-minute design call.

### ENG-006 — Nit — Hygiene — `model_advisor.MODEL_CATALOG` still carries Qwen entries with tiers above gemma4

The catalog (`model_advisor.py:99-118`) lists three Alibaba Qwen specs (`non_china=False`) at tiers 2/3/5, and `recommend()` (`314-358`) picks the highest-tier *installed* model — so on a box with `qwen2.5-coder:7b` (tier 5) pulled, the **CLI** advisor would recommend Qwen over gemma4 (tier 3). This is **not** reachable from the Stage 8.5 UI (the advisor is CLI-only and the UI shows gemma4:e4b as THE model), so it does not violate invariant 2 at the gate. Flagging it once as a standing inconsistency with Scott's "gemma4 is THE model, never float a Chinese model" rule: the CLI advisor can still surface Qwen. If the CLI is in scope for that rule, drop or hard-deprioritize the Qwen entries; if the CLI is intentionally a power-user tool, leave it — but the two policies should be reconciled deliberately, not by accident.

### ENG-007 — Minor — Dependencies/DX — Required runtime deps (`scipy`, `networkx`, `manifold3d`) are pinned but a bare environment fails 32 tests with cascading, misleading geometry errors

**Evidence:** All three are declared in `pyproject.toml` (`19-26`), yet on a machine without them the failures present as *logic* errors (`auto_orient` returns an un-flattened box, `trimesh.load` raises a deferred-import placeholder) rather than a clear "missing dependency" message — which is exactly the trap this audit hit and had to diagnose. `manifold3d` is documented as optional-at-runtime in the code comment but is a hard `>=3.0` dependency in the manifest, a small inconsistency.

**Why this matters:** A contributor (or a CI runner, or a future audit) that installs without the geometry extras will see a wall of red that looks like product breakage. The fix is process/DX, not product.

**Fix path:** (a) a smoke check in `conftest.py` (or a `pytest` collection hook) that asserts the geometry backends import and skips/xfails with a clear reason otherwise; (b) reconcile the `manifold3d` "optional" comment with its hard pin — either make it a real optional extra and guard the import, or drop the "optional" wording. Confirm CI installs the full dependency set so the gate signal is honest.

---

## What's working (specific, honest)

- **The slice/send gate is enforced where it counts — server-side.** A gate-FAILED part is refused at `/api/slice` *and* `/api/send` (`webapp.py:1595`, `1176`), fail-closed by default (`gate_status or "fail"`), not merely hidden in the UI. A direct API client cannot dispatch a rejected part. This is the single most important property of the product and it is correctly implemented and tested.
- **The confirm gate is genuinely an identity check.** `confirm is not True` (`printer_connector.py:200`), with an explicit comment and an MCP-layer note warning against `bool()`-coercion (`mcp_server.py:192-194`). This is the kind of detail that's usually wrong; here it's right and deliberate.
- **The OpenSCAD sandbox is thorough and defends against newline-split evasion.** `sanitize_scad` runs on the whole source with comments blanked, so `minkowski\n(...)`, split `import`, and `use\n</etc>` can't slip past (`openscad_runner.py:202-225`); blocking (not stripping) means no partial-strip bypass and no silent geometry loss. The cwd-isolation + `OPENSCADPATH` injection (`228-241`) lets the approved library resolve while keeping the working dir sandboxed.
- **Zip-bomb / resource bounds are real, not decorative.** `prove_gcode_3mf` streams members line-by-line, caps member count and *bytes actually read* (not the forgeable declared size — `slicer.py:273-295`); `_read_zip_member` bounds the inflated import read (`design_store.py:359-367`); the photo, body, and import sizes are all capped before reading (`webapp.py:44-52`).
- **Local-first is honored even in the seams.** The vision path stays local even when cloud text is enabled (`webapp.py:398-405`); cloud degrades to local on *every* gap; the key is masked-only and never logged. The PhotoOnramp UI's privacy copy is accurate to the implementation, not aspirational.
- **Atomic writes everywhere persistence touches disk.** Temp-file + `os.replace` with a Windows `PermissionError` retry/backoff in all three stores and the mesh export (`design_store.py:339-356`, `settings_store.py:50-66`, `pipeline.py:496-498`) — a concurrent reader never sees a half-write. This is the correct pattern and it's applied consistently.
- **Honest estimates, no fabricated numbers.** The weight estimate prefers the slicer's real density, only estimates when the profile emits none, refuses a degenerate `cm3==0`, flags `filament_g_estimated`, and the UI omits rows rather than zero-filling (`webapp.py:486-504`, `printEstimate.ts`, `ExportPanel.tsx:254-259`). Invariant 6 is a model of how to surface an estimate without lying.
- **Failure modes degrade, they don't crash.** Stores are best-effort and never raise; an Ollama drop maps to a typed recoverable `model_unavailable` status, not a 500 (`webapp.py:1303-1317`); readiness has a last-resort fallback if `assess_readiness` ever raised (`pipeline.py:285-297, 605-607`); no traceback ever reaches the browser.
- **Test coverage of the new surfaces is strong.** 757 Python tests / 249 frontend tests pass; the new code has dedicated suites (`test_design_store.py`, `test_settings_store.py`, the expanded `test_webapp.py` at 1205 lines, `printEstimate.test.ts`, `SettingsPanel.test.tsx`, `PhotoOnramp.test.tsx`), and several assert the *negative* invariants directly (no qwen, key never echoed in full, gate-failed refusal). `ruff` is clean.

---

## What I could not check

- **Runtime behavior of the running server** — out of scope by instruction; covered by the QA role and the completed wiring-audit.
- **Real OrcaSlicer / OpenSCAD output fidelity** — the live-assembled (`-m live`) tests were not run here; the non-live suite stubs the slicer. The wiring-audit + a clean-VM live re-gate remain the authority on from-scratch behavior.
- **Real Ollama / cloud round-trips** — provider logic is tested with fakes; I did not exercise a real gemma4:e4b or a real OpenRouter call.

---

## Severity summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 2 |
| Minor    | 4 |
| Nit      | 1 |
| **Total**| **7** |

**No Blockers, no Criticals.** All six load-bearing invariants hold as implemented; the two Majors are a same-`rid` slice/render concurrency race (ENG-001) and a reopen/import re-gating gap (ENG-002), both narrow in the single-user local context but both touching the gate-safety story directly. Neither blocks the stage gate on its own, but both are worth closing this sprint because they sit on the load-bearing safety path.
