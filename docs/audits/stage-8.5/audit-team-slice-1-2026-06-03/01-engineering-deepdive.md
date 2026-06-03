# Engineering Deep-Dive — KimCad Stage 8.5 Slice 1 ("My Designs" / saved-design persistence)

**Audit date:** 2026-06-03
**Role:** Principal Engineer
**Scope audited:** Stage 8.5 Slice 1 backend + correctness/security/perf/data surface — `src/kimcad/design_store.py`, `src/kimcad/config.py` (`designs_path`), the new `src/kimcad/webapp.py` design endpoints + helpers, and `frontend/src/api.ts` (data-shape only). Diff `main...stage-8.5-usability`, HEAD `657bc3b`. Tests `tests/test_design_store.py` + `tests/test_webapp.py`.
**Auditor posture:** Balanced

---

## TL;DR

This is careful, defensively-written code. The five load-bearing safety invariants the slice was built around — path safety, decompression-bomb bounding, never-raises persistence, request-body capping, and serialized/atomic writes — all hold under direct probing. I built a real 200 MiB zip bomb and a path-traversal import; both were rejected exactly as designed. `_safe_id` correctly blocks every separator/parent-ref escape, `import_bytes` reads only the three known members by exact name (no `extractall`, no archive paths), and every store method swallows failures to `None/False/[]`. The architectural debt is low and the test suite is genuinely strong (75 passing, including adversarial cases the team wrote themselves). What I found is a short tail of Minor data-integrity and robustness edges that are real and worth logging but are gated behind a single-user localhost altitude and scripted-API-only reachability — none rise to Critical. No Blockers.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 4 |
| Nit | 3 |

## What's working

- **Path safety is real, not asserted.** `_safe_id` (`design_store.py:287-290`) gates every id-taking method — `_dir` consumers `mesh_path`, `thumb_path`, `get`, `save`, `rename`, `delete`, `duplicate`, `export_bytes`, `import_bytes`. I probed `../x`, `a/b`, `..`, `.`, `a.b`, `a:b`, `a\x08`, empty — all rejected. The thumb endpoint's traversal test (`test_designs_thumb_endpoint_rejects_traversal`) plants a real `thumb.png` at `../secret/thumb.png` and proves the bytes are never served (404, no `SECRET` in body). Invariant 1 holds.
- **Zip-slip is structurally impossible, not filtered.** `import_bytes` (`design_store.py:250-278`) never calls `extractall` and never uses an archive-supplied path — it reads `meta.json`/`mesh.stl`/`thumb.png` by literal name via `_read_zip_member` and writes to `dst/<name>`. A crafted `../evil.txt` member is simply ignored (`test_import_rejects_a_non_design_or_zip_slip_archive` confirms the file is never written). This is the right design: you can't slip what you never read by path.
- **The decompression-bomb guard actually bounds the inflated read.** `_read_zip_member` (`design_store.py:301-309`) does `z.open(name).read(_MAX_IMPORT_MEMBER + 1)` then rejects if over the ceiling. I verified end-to-end: a 200 MiB-of-zeros member compresses to 204 KB (well under the 32 MiB compressed cap, so it sails past `_read_raw_body`), and the bounded inflated read rejects it cleanly. The compressed/inflated distinction is correctly understood and correctly implemented. Invariant 2 holds.
- **Never-raises is consistently applied.** Every `DesignStore` method wraps its body in `try/except Exception` and degrades. I traced the NaN edge: a NaN `volume_mm3` makes `save()`'s `_atomic_write_json(allow_nan=False)` raise `ValueError`, which is caught → `save` returns `False` (degrade), and the endpoint returns a clean `500 {"error": "Couldn't save the design."}` JSON, never a traceback. Reopen reads only JSON-native types (meta was written with `allow_nan=False`), so reopen's `_json` can't be driven to raise either. Invariant 3 holds.
- **Body caps are correct on both paths.** `_read_json_body` (1 MiB) and `_read_raw_body` (32 MiB import) both reject oversized `Content-Length` up front with `413 + close_connection` (no drain), and a malformed/negative/empty length yields a clean `400`. Tests `test_oversize_content_length_rejected_with_413` / `test_malformed_content_length_is_clean_400` pin the JSON path; the import path mirrors the guard. Invariant 4 holds.
- **Atomic meta + write ordering protects readers.** `_atomic_write_json` (temp + `os.replace`) means a concurrent reader never sees a half-written `meta.json`, and `save` writes `meta.json` last — so a mid-save crash leaves a dir whose `get()` returns `None` (invisible to the gallery), not a corrupt listing. `_WRITE_LOCK` serializes the read-modify-write across the threaded server.
- **The S1B-002 snapshot-staleness fix is correct and tested.** `_handle_render` refreshes `design_snapshot[rid]` after every re-render (`webapp.py:1156-1160`), so a save after dragging sliders persists the re-rendered parameters. `test_save_after_rerender_persists_the_rerendered_parameters` proves wall=3.0 survives the round-trip where the bug would have persisted 2.0.
- **Snapshot memory is bounded.** The in-memory `design_snapshot` dict is evicted in lockstep with `registry` via `_evict` (`webapp.py:429`) under the `MAX_REGISTRY=50` cap — no unbounded growth. The on-disk library is bounded by `_MAX_DESIGNS=200` via `_prune`. Both bounds exist and are exercised (`test_cap_drops_oldest`).
- **Test quality is high.** The team wrote the adversarial tests themselves: zip-slip, oversized member, traversal id on the thumb endpoint, corrupt-meta degrade, unwritable-root degrade, cap eviction, full round-trip, update-in-place. This is the coverage a reviewer hopes to find and rarely does.

## What couldn't be assessed

- **Real concurrent load.** The concurrency findings below are traced statically + by reading the lock discipline; I did not build a multi-threaded fuzz harness hammering `save` against `render` on the same rid. The reasoning is in the finding; a stress test would confirm the window's width.
- **The LLM path** is out of scope and not running (per the brief). Template-backed designs are exercised; LLM-backed save/reopen is covered only by the "no parameters" assertions.
- **OrcaSlicer / OpenSCAD live paths** are gated behind `@pytest.mark.live` / `skipif(binary present)` and were not run here (no binary in this environment); they are not part of this slice's surface.

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

### [ENG-001] — Major — Correctness / Data integrity — `save()` copies the live mesh outside the lock that a concurrent re-render holds, so a same-id save+re-render can capture a torn STL

**Evidence**
- `_handle_design_save` reads `mesh_path = registry.get(rid)` under the webapp `lock`, **releases** `lock`, then calls `store.save(...)` (`webapp.py:881-917`).
- `store.save` does `shutil.copyfile(mesh_path, d / "mesh.stl")` under `_WRITE_LOCK` — a *different* lock from both the webapp `lock` and the `render_lock` (`design_store.py:178`).
- A concurrent `/api/render/<same-rid>` rewrites that exact file: both `Pipeline.run` and `Pipeline.rerender` default to `basename="part"` and write `out_dir / "part.oriented.stl"` (`pipeline.py:439-440`), and the re-render's `out_dir` is `web_root/str(rid)` — the same path `registry[rid]` points to. The export is non-atomic: `hardened.export(str(mesh_path))` (`pipeline.py:440`) streams directly to the destination, no temp+replace.
- So the file `save` is copying can be truncated/rewritten mid-copy by a re-render of the same design id. `render_lock` serializes re-renders against *each other*, but nothing serializes a re-render against a save's copy.

**Why this matters**
A saved `mesh.stl` could be a half-written STL — a silently corrupt library entry that fails to load on reopen or slices wrong. It never raises (the copy succeeds on partial bytes), so it fails *silently*, which is the worst kind of data bug: invisible until the user reopens a saved part weeks later and it's broken.

**Why it's Major and not Critical:** exposure is low. This is a single-user localhost server; the SPA serializes the user's own clicks (you cannot drag a slider and click Save in the same instant from one browser). The window is only reachable by a scripted API client issuing `POST /api/designs/save` and `POST /api/render/<rid>` concurrently on the same live rid. Under the stated altitude that's a thin slice of reality — but it's a real data-integrity hazard with no guard, and the fix is cheap.

**Blast radius**
- Adjacent code: the same non-atomic-export + cross-lock-copy pattern is the model for any future "snapshot the live mesh" feature (e.g. a future "save as STL" or auto-save-on-render). Fix the pattern once.
- Shared state: `registry[rid]` → the on-disk `web_root/<rid>/part.oriented.stl`; `render_lock`; `_WRITE_LOCK`.
- User-facing: a corrupt saved design that fails to reopen/slice. No change to the happy path.
- Migration: none — additive locking, no stored-data shape change.
- Tests to update: none break; add one concurrent save-vs-render test on a shared rid (the team already has the threading harness in `test_concurrent_rerenders_are_serialized` to copy from).
- Related findings: ENG-003 (the non-atomic export is the shared root).

**Fix path**
Make the live-mesh export atomic at the source: in the pipeline, export to `part.oriented.stl.tmp` then `os.replace` onto the final name, so any reader (the save copy, the mesh GET) sees a whole file. That single change neutralizes the torn-read for *all* readers, not just save. Alternatively (or additionally) have `_handle_design_save` copy the mesh into a temp under the webapp `lock` (or `render_lock`) before handing a stable path to `store.save`. The atomic-export fix is preferred — it's one line of discipline that also hardens the mesh GET endpoint.

---

### [ENG-002] — Minor — Security / Robustness — `_safe_id` accepts arbitrary Unicode alphanumerics (`isalnum()` is Unicode-aware), not just ASCII `[A-Za-z0-9-_]`

**Evidence**
- `_safe_id` (`design_store.py:290`): `design_id.replace("-", "").replace("_", "").isalnum()`. Python's `str.isalnum()` returns `True` for Unicode letters/digits, so I verified `²` (U+00B2), `٠` (Arabic-Indic zero), `①`, `Ａ` (fullwidth), `Ⅰ` (Roman numeral) all pass `_safe_id`.
- This is **not** a traversal escape — none contain a separator or `..`, so `self.root / design_id` stays under the root (I confirmed the join). The store's ids are server-minted uuid hex, so this is only reachable via a hand-crafted API request (e.g. a crafted `saved_id` to `/api/designs/save`, which is the only id the client supplies).

**Why this matters**
The docstring claims "a plain token (no path separators / parent refs)" and the intent is clearly ASCII. Accepting Unicode lets a scripted client create design dirs with names that may collide under filesystem normalization (NFC/NFD on different OSes), confuse the `list()` sort, or be un-typeable for the user. The worst case is a weird-but-contained dir under the store root — a robustness/hygiene gap, not an escape. Flagging as Minor (Security category for visibility), not higher, because it cannot leave the root.

**Blast radius**
- Adjacent code: every method routes through `_safe_id`; tightening it is a single-function change with global effect.
- Tests to update: `test_safe_id_guards_path_separators` should gain a Unicode-alnum case asserting rejection.

**Fix path**
Replace the `isalnum()` check with an explicit ASCII allowlist, e.g. `all(c.isascii() and (c.isalnum() or c in "-_") for c in design_id)` or a precompiled `re.fullmatch(r"[A-Za-z0-9_-]+", design_id)`. This matches the documented intent exactly and removes the normalization ambiguity.

---

### [ENG-003] — Minor — Correctness / Data integrity — the live-mesh export is non-atomic, so the mesh GET (and slice input) can also serve a torn file during a re-render

**Evidence**
- `pipeline.py:440` `hardened.export(str(mesh_path))` writes `part.oriented.stl` in place. `_serve_mesh` (`webapp.py:611-623`) does `mesh_path.read_bytes()` with no coordination against a re-render rewriting the same path.
- Same root as ENG-001, but the reader here is the browser's mesh fetch / a slice read rather than the save copy. `render_lock` protects re-renders from each other but not from a concurrent GET.

**Why this matters**
A re-render in flight while the viewport (or a slice) fetches the mesh could return a partial STL → a transient render glitch or a slice on a torn mesh. Self-corrects on the next fetch, and the single-user SPA mostly serializes these, so impact is low — but it's the same missing-atomicity root as ENG-001 and is fixed by the same one-line change.

**Blast radius**
- Adjacent code: `_serve_mesh`, the slice path's mesh read, ENG-001's save copy — all three readers of `part.oriented.stl`.
- Migration: none.
- Tests to update: none break.
- Related findings: ENG-001 (same fix closes both).

**Fix path**
Export to a temp file + `os.replace` in the pipeline (see ENG-001 fix). Closing ENG-001 and ENG-003 is the same edit; that's why grouping them matters for the sprint.

---

### [ENG-004] — Minor — Correctness — a crashed/partial design dir (mesh written, `meta.json` not) is invisible to `list()` and therefore never pruned, so it can accumulate on disk

**Evidence**
- `save` writes `mesh.stl` (and `thumb.png`) *before* `_atomic_write_json(meta.json)` (`design_store.py:178-181`). A crash between the mesh write and the meta write leaves a dir with a mesh and no meta.
- `get()` returns `None` when `meta.json` is unreadable (`design_store.py:100-104`), so `list()` skips the dir — correct for the gallery, but it means `_prune` (which iterates `self.list()`, `design_store.py:280-284`) never sees the orphan and never reclaims it. The `_MAX_DESIGNS=200` cap counts only complete designs; orphans sit outside the cap forever.

**Why this matters**
On a machine that crashes mid-save repeatedly, orphan dirs accumulate unbounded under `~/.kimcad/designs/`, outside the 200-design cap. Low likelihood (a crash precisely between two writes), bounded blast (disk only, never a correctness/security issue), so Minor — but worth a cleanup pass.

**Blast radius**
- Adjacent code: `_prune`, `list`.
- User-facing: none (orphans are invisible).
- Migration: none.

**Fix path**
Two cheap options: (a) write the mesh/thumb to temp names and only rename them into place after `meta.json` lands, so a partial dir has no `mesh.stl` either; or (b) in `_prune`, also `iterdir()` for dirs whose `meta.json` is missing/unreadable and remove them. (a) is cleaner — it makes the whole design dir atomic-ish (meta is the last and only commit point).

---

### [ENG-005] — Minor — Hygiene / Performance — `_prune` recomputes the full library index (a `get()` per design dir) on every single save

**Evidence**
- `save` and `import_bytes` call `self._prune()` (`design_store.py:182`, `:275`), and `_prune` calls `self.list()` (`design_store.py:282`), which does an `iterdir()` + a `meta.json` read+parse for **every** design in the store (`list`, `design_store.py:123-138`) just to find the oldest beyond the cap.

**Why this matters**
At the 200-design cap, every save does 200 `meta.json` reads+JSON parses + a sort, under `_WRITE_LOCK` (serializing all other writes for that duration). For a local single-user store this is sub-millisecond-per-file and invisible in practice — so Minor/Performance, not higher. But it's O(N) disk work on the hot save path where O(1) would do, and it holds the global write lock while doing it.

**Blast radius**
- Adjacent code: `list`, `save`, `import_bytes`.
- User-facing: a barely-perceptible save latency at large N; none at typical N.

**Fix path**
`_prune` only needs `(created_at, id)` per dir, not the full `SavedDesign`. A lightweight scan that reads just the `created_at` (or stats mtime as a proxy) avoids parsing every full payload. Or skip pruning entirely when the dir count is under the cap (a cheap `iterdir` count guard before the full `list()`).

---

### [ENG-006] — Nit — Correctness — `duplicate` uses `copytree(..., dirs_exist_ok=True)`, which would silently merge into an existing dir on a `new_id` collision

**Evidence**
- `duplicate` (`design_store.py:221`) `shutil.copytree(src, dst, dirs_exist_ok=True)`. `new_id` is a fresh `uuid.uuid4().hex` minted by the caller (`webapp.py:983`), so a collision is astronomically improbable — but `dirs_exist_ok=True` means *if* it ever collided, the copy would overwrite/merge into the existing design rather than fail.

**Why this matters**
Defense-in-depth only; not reachable in practice with uuid ids. Worth a one-line note because the safer default (`dirs_exist_ok=False` + treat the `FileExistsError` as the existing `except Exception` → `False`) makes the collision a no-op rather than a silent overwrite.

**Fix path**
Drop `dirs_exist_ok=True` (default `False`); the surrounding `except Exception` already turns a collision into a clean `False`.

---

### [ENG-007] — Nit — Hygiene — `rename` truncates to 120 chars (`[:120]`) but `duplicate` truncates to 110 + " (copy)"; `save`'s name path also caps at 120 — three slightly different name-length rules

**Evidence**
- `rename`: `(name or "Untitled").strip()[:120]` (`design_store.py:194`).
- `duplicate`: `(str(raw.get("name", "Untitled"))[:110] + " (copy)").strip()` (`design_store.py:225`).
- `_handle_design_save`: `name_raw.strip()[:120]` and `(snap.get("prompt") or "Untitled")[:120]` (`webapp.py:899-903`).

**Why this matters**
Cosmetic inconsistency, not a bug — but the 110-vs-120 split means a duplicated name can end up a few chars longer/shorter than the same name set via rename. A single `_MAX_NAME = 120` constant + a `_clip_name` helper would centralize the rule.

**Fix path**
Extract a module-level name-clipping helper used by all three sites.

---

### [ENG-008] — Nit — Hygiene — `rename` strips before clipping while `save` clips a non-stripped prompt fallback; trivial, batch with ENG-007

**Evidence**
- `_handle_design_save` name-from-prompt fallback `(snap.get("prompt") or "Untitled")[:120]` (`webapp.py:903`) does not `.strip()`, so a prompt with leading whitespace becomes a leading-whitespace name. `rename`/`save`'s explicit-name path both strip.

**Fix path**
Fold into the ENG-007 `_clip_name` helper (strip + clip in one place).

---

## Patterns and systemic observations

- **Single high-leverage root: the live mesh is exported non-atomically.** ENG-001 and ENG-003 are the same underlying gap — `part.oriented.stl` is written in place by the pipeline, and three different readers (the save copy, the mesh GET, the slice input) can observe a torn file during a re-render. One fix (export to temp + `os.replace` in `pipeline.py`) closes both and hardens the existing mesh-serving path that predates this slice. This is the only finding here that touches data integrity, and it's the one to do first.
- **The never-raises / best-effort discipline is genuinely systemic and correct.** Every store method and every new endpoint degrades cleanly; I could not find a reachable `raise` that escapes a handler. The `try/except Exception` blanket is appropriate *here* (persistence is explicitly best-effort by design) where it would be a smell elsewhere — the team made the right call and documented why.
- **The id-validation surface is centralized and that's why it's safe.** All path resolution funnels through `_safe_id` + `self._dir`, and import never trusts archive paths. The only sharpening needed is ASCII-tightening (ENG-002). Centralization is what makes a one-line tightening safe to land.
- **Name-handling rules are duplicated across three sites** (ENG-007/008) — minor, but it's the kind of drift that compounds; a single helper retires both nits.

## Dependency snapshot

This slice adds **no new third-party dependencies**. `design_store.py` uses only the stdlib (`io`, `json`, `os`, `shutil`, `threading`, `zipfile`, `pathlib`, `dataclasses`). The webapp endpoints reuse the existing stdlib `http.server` stack and `uuid`/`datetime`. `DesignPlan` (de)serialization rides the already-present pydantic v2 (`model_dump(mode="json")` / `model_validate` confirmed real). `config.py`'s only dep is the already-present PyYAML.

Dependency surface for this slice is clean — no notable concerns, no CVE exposure introduced.

## Appendix: artifacts reviewed

- `src/kimcad/design_store.py` (full, 309 lines)
- `src/kimcad/config.py` (full; `designs_path` at :139-148)
- `src/kimcad/webapp.py` (full; new design endpoints + `_design_snapshot`, `_decode_data_url_png`, `get_designs_store`, `_read_raw_body`, `MAX_IMPORT_BYTES`)
- `frontend/src/api.ts` (full, data-shape review of the saved-design client fns)
- `tests/test_design_store.py` (full, 198 lines) and `tests/test_webapp.py` (full, 1596 lines)
- `src/kimcad/pipeline.py` (read `run`/`rerender`/`_finalize` export paths for the atomicity trace) and `src/kimcad/ir.py` (confirmed `DesignPlan` is a pydantic `BaseModel`)
- Ran `tests/test_design_store.py tests/test_webapp.py` → **75 passed** in ~28s
- Live probes: built a 200 MiB zip bomb (rejected by `_read_zip_member`), exercised `_safe_id` against ~20 adversarial ids (all separators/parent-refs rejected; Unicode-alnum accepted → ENG-002), traced NaN through `save`/reopen serialization (degrades, never raises)
