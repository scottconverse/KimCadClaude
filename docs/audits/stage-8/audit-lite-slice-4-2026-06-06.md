# Audit Lite — Stage 8, Slice 4: STEP (editable-CAD) export end to end
**Date:** 2026-06-06
**Scope:** The working-tree (uncommitted) changes on branch `stage-8-cadquery` that add an editable-CAD (STEP) download for a CadQuery-built part — `GET /api/step/<id>`, the `step_registry`, the design-POST wiring, the `PrintReport.step_path` field, the `ExportPanel` link/copy, the rebuilt SPA bundle, and the new backend + frontend tests.
**Reviewer:** Claude (audit-lite), independent / skeptical pass

## TL;DR
Ships. This is a tight, well-scoped slice that reuses the existing, hardened download pattern (`_serve_gcode`) almost verbatim and threads the new field cleanly through pipeline → webapp → SPA. Security is sound (int-parsed id, server-controlled path, no traversal vector — verified live), the registry is evicted in lockstep with the mesh registry and the on-disk STEP is cleaned on eviction, the reopen/save/export/slider paths correctly do NOT false-advertise a STEP, the build is reproducible (identical hash across rebuilds), and the tests exercise the real HTTP route plus the negative (404 / no-step) cases. The only items are copy-completeness nits.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 1

## Findings

### FINDING-001 Minor: the CadQuery formats-note drops the `.3mf` explanation
**Dimension:** UX / Docs
**Evidence:** `frontend/src/components/ExportPanel.tsx:196-209`. When `result.step_url` is present (CadQuery part), the note reads only "The .STL opens in other slicers… The .STEP is the editable, precision CAD model…" — the `.3mf` sentence ("printer-agnostic and safe to share") is present only in the `else` (OpenSCAD) branch (line 205). A CadQuery user therefore loses the one-line explanation of what the `.3mf` is.
**Why it matters:** The `.3mf` is the actual primary print artifact; it's still downloadable for a CadQuery part via the slice flow (`PrintSummary`, `ExportPanel.tsx:296` "Download print file (.3mf)"), so this is purely an explanatory-copy gap, not a functional loss. But the most-capable part (CadQuery) gets the least-complete file explanation, which is slightly backwards. Per the standing UI-first principle, copy completeness counts.
**Fix path:** Add the `.3mf` clause back into the `step_url` branch, e.g. "The .3mf print file is printer-agnostic and safe to share; the .STL opens in other slicers and CAD tools; the .STEP is the editable, precision CAD model…". One-line edit; update the corresponding assertion in `ExportPanel.test.tsx` if you assert on the 3mf string.

### FINDING-002 Nit: download filename is the generic literal `part.step`
**Dimension:** UX
**Evidence:** `src/kimcad/webapp.py:958` — `self._send_download(step_path.read_bytes(), "application/step", "part.step")`. Every STEP downloads as `part.step` regardless of the design. (Note: `_serve_gcode` derives its filename from the on-disk path; this handler hardcodes it.)
**Why it matters:** Minor friction — a user exporting several parts gets `part.step`, `part(1).step`, etc. It is also the *safe* choice (a hardcoded literal cannot carry a header-injection payload into `Content-Disposition`), so this is a deliberate-looking trade, not a defect. Calling it out only so the choice is on the record.
**Fix path:** Optional. If a friendlier name is wanted, derive it from the object_type/prompt with strict sanitization (alnum/`-`/`_` only) before putting it in the header — do NOT pass the raw registry path or any user string through unsanitized.

## What's working
- **Security of `GET /api/step/<id>` is solid.** `_serve_step` (`webapp.py:945-958`) int-parses the id (`ValueError → 404`), looks the path up in the server-written `step_registry` under `lock`, and 404s if absent or the file is gone — there is no caller-controlled path component, so no traversal / arbitrary-file-read is reachable. Verified live on `http://127.0.0.1:8765`: `/api/step/999999` → 404, url-encoded `../../../etc/passwd` → 404, `/api/step/0` → 404, `/api/step/-1` → 404. The `Content-Disposition` filename is a hardcoded literal (`part.step`), so no header-injection vector. It is a faithful clone of the already-audited `_serve_gcode`.
- **Lifecycle is leak-free and in lockstep.** `step_registry` is written only alongside `registry` under the same `lock` (`webapp.py:1466-1469`), so `step_registry ⊆ registry` always — it has no independent growth path. Eviction is driven by the mesh `registry` cap (`MAX_REGISTRY`, line 1491-1493) and `_evict` drops `step_registry[rid]` (line 769) AND `shutil.rmtree`s `web_root/<rid>` (line 777) — and the STEP is written into that very dir (`web_root/str(rid)`, line 1436), so the on-disk file is cleaned with the design dir. No registry-entry or disk leak found.
- **The "reopened design won't expose STEP" behavior is enforced structurally, not by accident.** `step_url` is added to the response only at `webapp.py:1495-1496`, *after* the saveable snapshot is built at line 1487; `_design_snapshot` constructs a fresh payload dict (`webapp.py:265`) at that earlier moment, so the persisted payload never contains `step_url`. `_result_to_payload` (the shape used by save/reopen/slider re-render) does not emit `step_url` either. Reopen returns `dict(d.payload)` (line 1649) and never registers `step_registry`, so a reopened CadQuery part correctly shows no STEP link. The save/`.kimcad` export path persists only that snapshot payload, so it can't carry a stale `step_url` either. This is exactly the bounded, intentional limitation the slice claims — and it's a clearly acceptable one (the STEP is regenerable by re-rendering).
- **Slider re-render can't false-advertise or lose a CadQuery STEP** because CadQuery (LLM-fallback) parts are not template-backed, so they have no `template_state` and `GET /api/render/<id>` 404s for them (`webapp.py:1834-1845`) — they never enter the mutate path. So the mutate path's lack of `step_registry` handling is harmless for this slice.
- **Wiring is correct and the field is real end to end.** `RenderResult.step_path` exists on the shared dataclass (`openscad_runner.py:112`, default `None`), the CadQuery worker actually exports it (`cadquery_worker.py:179-181`) and the runner only sets it when the file exists (`cadquery_runner.py:228,238`), the pipeline passes `emit_step=True` and threads `render.step_path` into `PrintReport.step_path` (`pipeline.py:395,1028`), and `_report_payload` adds `backend` (`webapp.py:140`). `step_ok` guards on both truthiness and `Path(...).exists()` (line 1465) before advertising — so a missing/empty STEP never yields a dead link. No AttributeError risk: every backend's `RenderResult` carries `step_path`.
- **As-designed STEP semantics are honest.** The UI copy explicitly states "It's the as-designed shape; print orientation is applied only to the printable mesh" (`ExportPanel.tsx:200-201`), and the `PrintReport` field comment says the same. Exporting the un-oriented CAD is the standard, correct choice (orientation is a print-prep concern, not a design-geometry concern); the copy does not mislead.
- **Build is reproducible.** `npm --prefix frontend run build` succeeds (incl. `tsc --noEmit`, so the new TS types compile), and the committed `Workspace.js` is byte-stable across two consecutive rebuilds (sha256 `87ea2f4d…a255e18` both times). `git status` shows only the single expected `M Workspace.js`. The STEP copy and `kc-download-step`/`step_url` wiring are present in the bundle. The push gate (committed == fresh) will pass.
- **Tests genuinely exercise the route + the negative paths.** `test_cadquery_part_exposes_a_step_download` drives the real socket — POSTs `/api/design`, asserts `report.backend == "cadquery"` and a `step_url`, then GETs it and checks 200 + `ISO-10303-21` body + `application/step` content-type. `test_openscad_part_has_no_step_url_and_unknown_step_is_404` asserts an OpenSCAD part has no `step_url` AND that `/api/step/999999` raises a 404. Pipeline-level tests cover both the carries-STEP and no-STEP cases. Frontend: a test asserts the link renders with the right `href` for a CadQuery part and a separate test asserts it is absent for OpenSCAD. Backend `120 passed`, vitest `12 passed` — both reproduced locally this session.

## Watch items
- The live-slider mutate path (`_handle_design_mutate`, `webapp.py:1862-1920`) does not register `step_registry` or emit `step_url`. It's harmless *today* because CadQuery parts aren't template-backed and can't reach it — but if a future slice makes a CadQuery part parametric/re-renderable, this path will need to register the fresh STEP (and invalidate the old one) the same way it already invalidates the gcode/slice cache. Worth a code comment at line 1900-ish noting the STEP is intentionally not handled here yet.
- `application/step` is the de-facto MIME used here and is fine for a download. If any client ever content-sniffs, note the more-registered type is `application/STEP` / `model/step` (RFC-wise unsettled); the `download` attribute makes this a non-issue for the browser flow.

## Escalation recommendation
No escalation needed. Zero Blocker/Critical/Major findings; the change is small, self-contained, reuses an already-audited pattern, and is well-tested. The two findings are copy/cosmetic and do not block merge. A full `audit-team` run would be overkill for this slice.

---

## Remediation (maintainer, 2026-06-06) — 0/0/0/0/0

- **FINDING-001 (Minor) — FIXED.** The CadQuery formats note now re-includes the `.3mf`
  print-file explanation alongside `.STL` and `.STEP`, so a CadQuery part's note is no longer
  missing the shareable print-file line (ExportPanel.tsx, `step_url` branch). SPA rebuilt;
  ExportPanel vitest 12 passed.
- **FINDING-002 (Nit) — FIXED.** The STEP download filename is now `kimcad-part-<id>.step`
  (the int-parsed `sid`, so no Content-Disposition header-injection risk) instead of the
  constant `part.step` — each design's STEP downloads under a distinct name.

Re-verified: ruff clean; webapp step/content-type tests pass; vitest pass; SPA build reproducible.
