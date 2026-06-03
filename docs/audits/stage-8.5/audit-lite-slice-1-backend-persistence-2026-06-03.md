# Audit Lite — Stage 8.5 Slice 1: backend persistence ("My Designs" store + endpoints)
**Date:** 2026-06-03
**Scope:** `src/kimcad/design_store.py` (the `DesignStore`), `Config.designs_path()`, the Stage-8.5 webapp additions (`_design_snapshot`, `_decode_data_url_png`, `design_snapshot`, `get_designs_store`, and the `GET/POST /api/designs*` endpoints incl. reopen), and the tests (`test_design_store.py` + 3 webapp cases).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two Majors + a Minor. The store is a clean, best-effort, atomic, traversal-aware persistence layer and the reopen path correctly re-registers a saved design (mesh + gate verdict + live-slider state) without weakening the slice gate. But the store's `mesh_path`/`thumb_path` are **not** `_safe_id`-guarded (the other store methods are), so the thumbnail endpoint is a reachable path-traversal read; and the per-design save snapshot is **not refreshed on a slider re-render**, so saving after adjusting a part persists the *fresh mesh but stale parameters*. Both fixed below.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)".

**As found:** 0 Blocker · 0 Critical · 2 Major · 1 Minor · 0 Nit.

## Findings

### S1B-001 Major: `mesh_path`/`thumb_path` aren't traversal-guarded → the thumbnail endpoint is a path-traversal read
**Dimension:** Correctness / Security
**Evidence:** `design_store.py:72-78` — `mesh_path`/`thumb_path` build `self.root / design_id / …` with **no** `_safe_id` check (unlike `get`/`rename`/`delete`/`duplicate`, which all guard). `webapp.py:844-850` (`_serve_design_thumb`) calls `store.thumb_path(design_id)` **directly** (no prior `get()` that would reject an unsafe id) and serves `path.read_bytes()`. So `GET /api/designs/..%2f..%2f<dir>/thumb` → unquoted to `../../<dir>` → `thumb_path` resolves to `root/../../<dir>/thumb.png` → if that file exists it's served. (`_handle_design_reopen` is *not* exploitable — it calls `get()` first, which guards and returns None → 404 before `mesh_src` is used — so the live vector is the thumb endpoint only.)
**Why it matters:** A reachable arbitrary-file read, even narrowed to files named `thumb.png` on a loopback server, is a real traversal gap; the guard exists everywhere else and was simply missed on the two path accessors. Security defaults high; the narrowing (loopback, filename-constrained, image response not JS-readable cross-origin) is why this is Major rather than Critical — but it's fixed regardless.
**Fix path:** Add `_safe_id` to `mesh_path` and `thumb_path` (return `None` for an unsafe id), mirroring the other store methods. Add a test: `GET /api/designs/..%2f..%2fx/thumb` → 404 and never reads outside the root.
**Blast radius:** Adjacent: any future caller of `mesh_path`/`thumb_path`. Shared state: the store root. User-facing: none (the thumb still serves for valid ids). Tests to update: add the traversal-rejection test.

### S1B-002 Major: the save snapshot isn't refreshed on a slider re-render → save-after-tweak persists stale parameters
**Dimension:** Correctness
**Evidence:** `design_snapshot[rid]` is populated in `_handle_design` (`webapp.py:826`) and on reopen (`:933`) but **not** in `_handle_render` — the re-render handler updates `registry[rid] = result.mesh_path` (`:1082`) and `template_state` (`:1092`) but leaves `design_snapshot[rid]` at the *original* design's payload/parameters. So after a user drags sliders (re-renders) and then saves, the store gets the **fresh mesh** (copied from `registry[rid]`) but the **stale payload** (original parameter values, original readiness). Reopening shows the new geometry with the old slider values — inconsistent. The round-trip test saves *without* a prior re-render, so it didn't catch this.
**Why it matters:** "Save my work" is the whole point of this slice; saving after adjusting a part — the common case — silently persists a mismatched snapshot. The reopened design's sliders won't reflect what was saved.
**Fix path:** In `_handle_render`, after updating `registry[rid]`, rebuild the snapshot: `design_snapshot[rid] = _design_snapshot(payload, result, <preserved prompt>)` (carry the prompt from the existing snapshot). Add a test: design → re-render at new values → save → reopen → the reopened `parameters` reflect the *re-rendered* values, not the original.
**Blast radius:** Adjacent: `_design_snapshot`. Shared state: `design_snapshot`. User-facing: a saved-after-tweak design reopens correctly. Tests to update: add the save-after-rerender test.

### S1B-003 Minor: `_serve_design_thumb` reads the file outside a guard (TOCTOU race)
**Dimension:** Runtime
**Evidence:** `webapp.py:847-850` checks `path.exists()` then `path.read_bytes()`; if the file is deleted between the two (a concurrent `delete`/`_prune`), `read_bytes()` raises `OSError`, which escapes the handler (unlike `_handle_design`, which wraps its work in try/except → 500). A narrow race on a best-effort path.
**Why it matters:** A thumbnail read shouldn't be able to throw an unhandled exception onto a request thread, even in a rare race.
**Fix path:** Wrap the read: `try: data = path.read_bytes() except OSError: self._json(404, …); return`.

## What's working
- **The slice gate is preserved on reopen.** `_handle_design_reopen` sets `gate_status_by_rid[rid] = d.gate_status or "fail"` (`webapp.py:923`), so a reopened gate-failed part still can't be sliced/sent (defaults to "fail" if absent — fail-closed). `_evict` was correctly extended to drop `design_snapshot[rid]`, so the registry cap stays consistent.
- **Best-effort discipline is real.** Every `DesignStore` method swallows failures and returns `[]`/`None`/`False` (verified: corrupt-meta-skip, unwritable-root, missing-file all tested); `get_designs_store()` degrades to `None` and the endpoints then 503/empty. Writes are atomic (temp + `os.replace`) and serialized (`_WRITE_LOCK`).
- **Traversal is guarded on the mutating methods.** `get`/`rename`/`delete`/`duplicate` all call `_safe_id` (which correctly rejects `..`, slashes, dots — tested), and the reopen handler is protected by its leading `get()`. Only the two read-path accessors slipped (S1B-001).
- **Reopen is genuinely functional, and the test proves it.** The round-trip test reopens *and re-renders* the reopened design, proving `template_state` was restored — not just that a payload came back. The snapshot correctly strips the volatile `mesh_url` and reopen rewrites it to the fresh rid.
- **No test/prod pollution.** The webapp designs tests pass a `Config` with `paths.designs` → `tmp_path`; the store tests are `tmp_path`-scoped; no test reaches `get_designs_store()` with a real config (the lazy store is never built in the non-designs tests). The real `~/.kimcad/designs/` is never touched.
- **The thumbnail decode is bounded** (`_decode_data_url_png`: PNG-only, base64-validated, ≤2 MB), atop the 1 MiB request-body cap.

## Watch items
- **Save-vs-evict race.** `_handle_design_save` reads `registry[rid]` under `lock` then `store.save` copies the mesh *outside* the lock (correctly — it's slow I/O); if a concurrent design evicts this rid in between, the copy fails and save returns a clean 500. Best-effort handles it; noting only because it's a (very narrow) race. No fix needed.

## Escalation recommendation
No escalation needed. Two Majors (a missed traversal guard + a stale-snapshot-on-rerender) and a Minor race, all local and trivially fixed, on an otherwise clean, well-tested, safety-preserving persistence layer. Fix all three, add the two tests, re-audit to 0/0/0/0/0, then push.

---

## Re-audit (resolution) — 0/0/0/0/0

- **S1B-001 (Major) — FIXED.** `mesh_path` and `thumb_path` now call `_safe_id` first and return `None` for a traversal id, mirroring the other store methods. New test `test_designs_thumb_endpoint_rejects_traversal` plants a `thumb.png` at the traversal target and asserts `GET /api/designs/..%2fsecret/thumb` → 404 with the outside file never served; `test_mesh_and_thumb_path_reject_traversal_ids` pins the store-level guard.
- **S1B-002 (Major) — FIXED.** `_handle_render` now rebuilds `design_snapshot[rid] = _design_snapshot(payload, result, prior_prompt)` after updating the registry, so a save-after-slider-drag persists the re-rendered parameters. New test `test_save_after_rerender_persists_the_rerendered_parameters` (re-render wall 2.0 → 3.0 → save → reopen → reopened wall is 3.0, not the stale 2.0).
- **S1B-003 (Minor) — FIXED.** `_serve_design_thumb` wraps `read_bytes()` in `try/except OSError → 404`, so a delete/read race can't throw an unhandled exception onto a request thread.

Verified: ruff clean; the persistence tests pass green — at this remediation commit (`13584ea`):
`test_design_store.py` 12 + `test_webapp.py` 56, plus the `designs_path` config test; no
regression. (DOC-002: the original line cited a non-additive `14 + 67 = 75`; corrected here to the
real per-file counts at that commit. At branch HEAD the suite has since grown.) **Roll-up: 0/0/0/0/0.**
