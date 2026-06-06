# Re-Audit (static + test-run) — Stage 8.5 Slice 1 remediation

**Re-audit date:** 2026-06-03
**Role:** Adversarial code re-auditor (independent verification of the 37-finding remediation)
**Method:** Read every live (uncommitted) file in the working tree, cited file:line for each fix; ran both test suites; adversarial new-defect hunt on the changed surface.
**Repo:** `C:\Users\scott\dev\kimcad` (HEAD uncommitted — live files read).

---

## TL;DR

All 37 findings are **VERIFIED-FIXED** in the working tree. No NOT-FIXED, no PARTIAL. Both suites pass green at higher counts than the audit baseline (backend 75→81, frontend 56→66). The remediation is clean: ruff passes, the frontend builds/typechecks, and the new tests assert the actual fixes (not vacuous). No NEW defect of Minor-or-higher severity was found. Two benign, contained observations are logged as Nits below; neither is a regression.

---

## Findings verification table

| ID | Sev | Status | Evidence (file:line) |
|---|---|---|---|
| QA-001 | Critical | VERIFIED-FIXED | `design_store.py:339-356` `_atomic_write_json` retries `os.replace` on `PermissionError` (bounded `_REPLACE_RETRIES=8`, linear backoff `:52-53`); on final attempt `tmp.unlink(missing_ok=True)` + `raise` → reaches `save()`'s `except → False` (`:199-200`); tmp not leaked on success (early `return :351`). Handler maps `not ok` → **503** `{saved:false}` (`webapp.py:939-943`), not 500. |
| ENG-001 | Major | VERIFIED-FIXED | `pipeline.py:445-447` exports to `{basename}.oriented.stl.tmp` then `os.replace`; `import os` present (`pipeline.py:20`). |
| QA-002 | Major | VERIFIED-FIXED | `webapp.py:396` `rid_saved_id` map; minted under `lock` and reused (`:906-913`); evicted in `_evict` (`:434`). Test `test_concurrent_saves_without_saved_id_make_one_entry` (`test_webapp.py:1610-1632`) asserts 6 concurrent no-saved_id saves → 1 entry. |
| TEST-001 | Major | VERIFIED-FIXED | `App.test.tsx:40` stub fires `onModelReady`; `:151-173` asserts `saveDesign` called exactly **once** across two overlapping frames; `:175-190` asserts create→no saved_id, re-save→carries `'x'`. Non-vacuous. |
| UX-001 | Major | VERIFIED-FIXED | `App.tsx:52` `saveState`; single self-healing retry guarded by `retryRef.current === null` (`:95-100`, no tight loop); `Topbar.tsx:39,52-71` renders Saving…/Saved·My Designs/Couldn't save — retrying; resting "Saved" driven by `savedId` (`App.tsx:236`, `Topbar.tsx:39`). |
| UX-002 | Major | VERIFIED-FIXED | `styles.css:1564-1574` `:focus-visible` for `.kc-design-name/-act/-rename` + `.kc-mydesigns-sort select` and `.kc-design-open` (inset offset). |
| UX-003 | Major | VERIFIED-FIXED | `styles.css:584` adds `.kc-design-act` to 44px coarse floor; `:595-597` gap 10px + wrap; `:599-601` `.kc-design-act-danger { margin-left:auto }` pushes Delete to end. (= QA-005) |
| DOC-001 | Major | VERIFIED-FIXED | `ROADMAP.md:56` "Next = Stage 8.5 (Usability), then Stage 8 (CadQuery)"; `:62` "Still ahead" now lists "usability (Stage 8.5, in progress)". |
| ENG-002 | Minor | VERIFIED-FIXED | `design_store.py:45` `_SAFE_ID_RE = re.compile(r"[A-Za-z0-9_-]+")`; `:330` `fullmatch`. (= TEST-006) |
| ENG-003 | Minor | VERIFIED-FIXED | Closed by ENG-001 atomic export + `file_type="stl"` (`pipeline.py:446`) so the `.tmp` suffix doesn't break trimesh. |
| ENG-004 | Minor | VERIFIED-FIXED | `design_store.py:310-314` `_prune` rmtree's an orphan dir (no `meta.json`). Test `test_prune_reclaims_an_orphan_dir` (`test_design_store.py:229-240`). |
| ENG-005 | Minor | VERIFIED-FIXED | `design_store.py:315-316` early-returns under cap; only parses `created_at` (`:317-320`) when over cap. |
| QA-003 | Minor | VERIFIED-FIXED | `webapp.py:1005-1007` mutate returns 404 when `store.get(id) is None`; duplicate failure → 500 (`:1014`). Test `test_designs_mutate_bad_id_is_404` (`test_webapp.py:1598-1607`). |
| QA-004 | Minor | VERIFIED-FIXED | `api.ts:279` over-cap reject up front; `:289-291` connection-error → friendly message; `MyDesigns.tsx:228` surfaces `e.message`. Tests `api.test.ts:163-177`. |
| DOC-002 | Minor | VERIFIED-FIXED | audit-lite-backend `:60-61` corrected to `12 + 56`, with a note retiring the non-additive `14 + 67 = 75`. |
| DOC-003 | Minor | VERIFIED-FIXED | `design_store.py:226-228` docstring now states a **fresh** created_at (param or now()), matching `:244`. (= UX-006) |
| DOC-004 | Minor | VERIFIED-FIXED | `README.md:16-18,45-50`, `CHANGELOG.md:14-28` `[Unreleased]`, `ARCHITECTURE.md:103,178-183` all updated; `docs/guide-my-designs.md` exists. All flag 8.5 as in-progress/not merged. |
| DOC-005 | Minor | VERIFIED-FIXED | `config.py:5` module docstring now mentions `paths.designs`. |
| UX-004 | Minor | VERIFIED-FIXED | `MyDesigns.tsx:143-145` label "Export (.kimcad)" + clarifying `title`. |
| UX-005 | Minor | VERIFIED-FIXED | `Topbar.tsx:74-76` `kc-btn-active` + `aria-current="page"` on designs route; `styles.css:1586-1590`. |
| UX-006 | Minor | VERIFIED-FIXED | `design_store.py:244` duplicate stamps fresh created_at. Test `test_duplicate_stamps_a_fresh_created_at` (`test_design_store.py:215-226`). |
| UX-007 | Minor | VERIFIED-FIXED | `MyDesigns.tsx:37,54-57,74-78,173-177` per-card `err` + `.kc-design-err role=alert`; `styles.css:1578-1582`. Test `MyDesigns.test.tsx:126-133`. |
| TEST-002 | Minor | VERIFIED-FIXED | `api.test.ts:128-183` importDesign 200/non-2xx/non-JSON/oversize/conn-fail + exportDesignUrl encode. Non-vacuous. |
| TEST-003 | Minor | VERIFIED-FIXED | `test_design_store.py:186` asserts imported dir == exactly `{meta.json, mesh.stl}`; `:187` no `evil.txt` anywhere. Now bites. |
| TEST-004 | Minor | VERIFIED-FIXED | `test_design_store.py:243-280` 6 savers + 4 listers, asserts no raise + all 6 persist. |
| QA-005 | Minor | VERIFIED-FIXED | Closed by UX-003 (`styles.css:584`). |
| ENG-006 | Nit | VERIFIED-FIXED | `design_store.py:239` `copytree(src, dst)` — no `dirs_exist_ok`. |
| ENG-007 | Nit | VERIFIED-FIXED | `clip_name` helper (`design_store.py:333-336`) used by save/rename/duplicate (`:183,209,243`); `_MAX_NAME=120` (`:47`). |
| ENG-008 | Nit | VERIFIED-FIXED | `webapp.py:924` save name path uses `clip_name(snap.get("prompt"))` (strips the prompt fallback). |
| DOC-006 | Nit | VERIFIED-FIXED | `webapp.py:899-902` save comment — stray "current" gone. |
| TEST-005 | Nit | VERIFIED-FIXED | `MyDesigns.test.tsx:109-124` switches sort to oldest + name, asserts DOM reorder. |
| TEST-006 | Nit | VERIFIED-FIXED | `test_design_store.py:206-212` asserts `_safe_id` rejects `é ² ٠ Ａ Ⅰ` + separators + null byte. |
| QA-006 | Nit | VERIFIED-FIXED | `webapp.py:448-461` `_method_not_allowed` sends `405 {"error":"Method not allowed."}` JSON + Allow header; wired to do_PUT/DELETE/PATCH/OPTIONS. |
| UX-008 | Nit | VERIFIED (no change) | Auditor said no change needed; "Importing…" cue present (`MyDesigns.tsx:255`). Defensible. |
| UX-009 | Nit | VERIFIED-FIXED | `styles.css:1509` `.kc-design-act { font-weight: 600 }` (reads interactive at rest). |
| UX-010 | Nit | VERIFIED (no change) | Hover lift covered by global `prefers-reduced-motion`. Defensible. |

---

## New-defect hunt (adversarial)

- **`os.replace` retry sleep vs readers:** the sleep happens under `_WRITE_LOCK`, but `get()`/`list()` readers do **not** take that lock — readers are never blocked by the backoff. Correct. **No defect.**
- **`clip_name` empty/over-long edge:** verified empirically — `clip_name('')`/`'   '`/`None` → "Untitled" (never empty); duplicate's `clip_name(...)[: 120-7] + " (copy)"` caps at exactly 120. **No defect.**
- **`rid_saved_id` → deleted design:** a stale rid→id after a delete makes `store.get(store_id)` return None → save re-creates under the same id (a re-save), harmless; the mapping is evicted with the rid in `_evict`. **No defect.**
- **mutate-404 vs happy path:** the 404 only triggers when `store.get(id) is None`; a real id still passes through to 200. Tests `test_duplicate`/rename/delete still pass (81 green). **No defect.**
- **`duplicate` created_at vs old `test_duplicate`:** the old test (`test_design_store.py:98`) passes no created_at and only checks "(copy)" + coexistence — unaffected by the fresh-stamp change. Confirmed green. **No defect.**
- **`file_type="stl"` exported bytes:** trimesh's STL export is format-determined by `file_type`, not the filename; forcing it only tells trimesh to emit STL (which the `.stl` extension previously implied). No test asserts exact STL bytes; pipeline/webapp suites green. **No defect.**

### Nit-level observations (NOT regressions, logged for completeness)

1. **`_safe_id` now accepts all-separator ids** (`_safe_id('---')`/`'___'` → True; the old `isalnum()` rejected them). This is a benign *widening* of the regex relative to the prior guard — `root/---` stays inside the store root (no traversal), and server-minted ids are uuid hex. Matches the documented "ASCII token [A-Za-z0-9_-]" intent. Severity: Nit, contained, not a defect.
2. **App.tsx save-retry has no max-attempt cap:** on a *durable* save failure the 1.5s-throttled retry repeats indefinitely in the background (cancelled on new-design / new-submit via `resetSaveIndicator`). It cannot tight-loop or grow the stack and is user-cancellable; the store now retries the Windows race internally so a 503 is rare. Severity: Nit (a backoff cap would be tidier), not a defect.

---

## Test counts observed (run by me, live tree)

- Backend: `pytest tests/test_design_store.py tests/test_webapp.py -q` → **81 passed** in ~29s (audit baseline was 75; +6 new tests: orphan-prune, fresh-created_at, unicode-safe_id, concurrent-saves, mutate-404, converge-one-entry).
- Frontend: `npm run test` (vitest) → **66 passed across 8 files** in ~3.4s (audit baseline was 56; +10: TEST-001 ×2, TEST-002 ×6, TEST-005 sort, UX-007 per-card error).
- `ruff check` on the 4 backend modules → **All checks passed!**
- `npm run build` (vite + tsc) → built clean.

---

## Verdict

**RESIDUAL: none**  **NEW: none**

All 37 findings VERIFIED-FIXED with cited evidence; both suites green (81 backend / 66 frontend); ruff clean; frontend builds. Two Nit-level observations logged (all-separator `_safe_id`, uncapped save-retry) — neither is a regression nor a defect. The remediation is sound and the 0/0/0/0/0 claim holds under independent verification.
