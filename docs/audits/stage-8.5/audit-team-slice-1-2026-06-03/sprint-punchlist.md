# Sprint Punch List — Stage 8.5 Slice 1

Every finding, sorted by severity. Per Scott's standing rule, **all are fixed this slice** (Blocker→Nit, no deferral) and re-audited to 0/0/0/0/0. Owner hint = the role that surfaced it. Size: S (≤30 min) / M (≤2 h) / L (>2 h).

| ID | Sev | Owner | What to do | Size |
|---|---|---|---|---|
| QA-001 | Critical | QA | Retry `os.replace` on `PermissionError` (bounded backoff) in `_atomic_write_json`; stop mapping best-effort `save()==False` to a hard 500 (use 503 + `saved:false`). | M |
| ENG-001 | Major | Eng | Export the live mesh atomically (`part.oriented.stl.tmp` + `os.replace`) in `pipeline.py` so no reader (save copy, mesh GET, slice) sees a torn STL. | S |
| QA-002 | Major | QA | Give the server a stable per-`rid` save identity so rapid saves of one live rid converge to one library entry. | M |
| TEST-001 | Major | Test | Extend `App.test.tsx` `Workspace` mock to fire `onModelReady`; assert `saveDesign` fires once (create) then with `saved_id` (update), never twice as a create. | M |
| UX-001 | Major | UX | Add a quiet, non-blocking save indicator ("Saving…" → "Saved to My Designs"; "Couldn't save — retrying" on failure). | M |
| UX-002 | Major | UX | Add branded `:focus-visible` rings to the card controls (`.kc-design-open/-name/-act/-rename`, sort select). | S |
| UX-003 | Major | UX | Extend the coarse-pointer 44px floor + wider gap to `.kc-design-act`; separate Delete from Export. (= QA-005) | S |
| DOC-001 | Major | Docs | Fix `ROADMAP.md` "Current baseline": "Next = Stage 8.5, then Stage 8" + add 8.5 to "Still ahead". | S |
| ENG-002 | Minor | Eng | ASCII-tighten `_safe_id` (`re.fullmatch(r"[A-Za-z0-9_-]+")`). (= TEST-006) | S |
| ENG-003 | Minor | Eng | Closed by ENG-001 (same atomic-export fix). | — |
| ENG-004 | Minor | Eng | Reclaim orphan design dirs (mesh, no meta) in `_prune`. | S |
| ENG-005 | Minor | Eng | `_prune`: cheap iterdir/stat; only parse `created_at` when over cap. | S |
| QA-003 | Minor | QA | Mutate verbs (rename/delete/duplicate) return 404 for unsafe/absent id, not `200 {ok:false}`. | S |
| QA-004 | Minor | QA | Surface a friendly "file too large (max 32 MB)" on an import connection/RST error client-side. | S |
| DOC-002 | Minor | Docs | Correct the backend-persistence audit-lite's non-additive test count. | S |
| DOC-003 | Minor | Docs | `duplicate()` docstring → match behavior (now stamps a fresh `created_at`). (= UX-006) | S |
| DOC-004 | Minor | Docs | Update README status + CHANGELOG `[Unreleased]` + ARCHITECTURE for the store/endpoints; add a concise My Designs user guide. | M |
| DOC-005 | Minor | Docs | Add `paths.designs` to the `config.py` module docstring. | S |
| UX-004 | Minor | UX | Label "Export (.kimcad)" + a `title` clarifying it's a re-importable backup, not a printable STL. | S |
| UX-005 | Minor | UX | Topbar "My Designs" gets `aria-current="page"` + active style on the designs route. | S |
| UX-006 | Minor | UX | Stamp a fresh `created_at` on duplicate so it sorts newest. (= DOC-003, Eng fix) | S |
| UX-007 | Minor | UX | Surface a per-card error when a Rename/Duplicate/Delete fails (no longer silent). | S |
| TEST-002 | Minor | Test | `api.test.ts` cases for `importDesign` (200 / non-2xx / non-JSON) + `exportDesignUrl` encoding. | S |
| TEST-003 | Minor | Test | Make the zip-slip assertion bite: assert the imported dir contains exactly `{meta.json, mesh.stl}`. | S |
| TEST-004 | Minor | Test | Threaded store test: N savers + a `list()` loop never raise; cap honored; save-vs-prune safe. | M |
| QA-005 | Minor | QA | Closed by UX-003. | — |
| ENG-006 | Nit | Eng | `duplicate`: drop `dirs_exist_ok=True`. | S |
| ENG-007 | Nit | Eng | One `_clip_name` helper (strip+clip 120) for rename/duplicate/save. | S |
| ENG-008 | Nit | Eng | Strip the prompt-fallback name (folds into ENG-007). | S |
| DOC-006 | Nit | Docs | Drop the stray "current" in the `_handle_design_save` comment. | S |
| TEST-005 | Nit | Test | Assert the `oldest` + `name` sort branches reorder. | S |
| TEST-006 | Nit | Test | Pin `_safe_id` rejection of a Unicode/reserved-name id. (= ENG-002) | S |
| QA-006 | Nit | QA | `do_PUT/DELETE/PATCH` return `405 {error}` JSON for contract parity. | S |
| UX-008 | Nit | UX | "Importing…" cue — acceptable as-is; no change. | — |
| UX-009 | Nit | UX | Nudge card action labels to read interactive-at-rest. | S |
| UX-010 | Nit | UX | Card hover lift — already covered by global reduced-motion; no change. | — |
