# Adversarial Re-Audit — Stage 8.5 Slice 1 fixes (QA)

**Re-audit date:** 2026-06-03
**Posture:** Adversarial / skeptical — goal was to make the fixes fail and to surface any NEW runtime regression introduced by the remediation.
**Subject:** The fix pass for the audit-team Slice 1 findings (QA-001, QA-002, QA-003, QA-006, ENG-001/ENG-003) plus a full regression sweep.
**Method:** Live demo server (`python -m kimcad.cli web --demo --port 8770`), driven with raw `requests` + `socket`; UI sanity driven in a real browser via Claude_Preview on a second demo instance (port 8765). Both instances share the per-user store `~/.kimcad/designs`.
**Source reviewed:** `src/kimcad/design_store.py` (`_atomic_write_json` retry, `_safe_id`, bounded zip read), `src/kimcad/webapp.py` (save 503 contract, `rid_saved_id` map, mutate-404, 405 shape, body guards), `src/kimcad/pipeline.py` L440–447 (atomic mesh export).

---

## Item 1 — QA-001 (Critical): the Windows `os.replace` save race — **PASS**

The original audit reproduced **13/30 saves (43%) returning HTTP 500** under "auto-save while My Designs is open." The fix adds a `PermissionError` retry-with-backoff in `_atomic_write_json` and converts a best-effort save miss from 500 → soft 503.

Reproduced the original stress at increasing intensity. **Across every configuration the HTTP 500 count is exactly ZERO.** Measured save-status distributions (update-in-place, same `design_id` + `saved_id`, concurrent with list + export readers):

| Stress config | Saves | Reader threads | **200** | **503 (soft)** | **404 (evicted)** | **500** |
|---|---|---|---|---|---|---|
| Phase 1 (5 savers × 6) | 30 | 4 list + 4 export | 30 | 0 | 0 | **0** |
| Phase 2 HARD (10 savers × 20) | 200 | 6 list + 6 export | 192 | 8 | 0 | **0** |
| Aggressive burst (12 × 25) | 300 | 16 readers | 3 | 6 | 291* | **0** |
| Clean burst (10 × 20, no new designs) | 200 | 8 readers | **200** | 0 | 0 | **0** |

Reader traffic during the HARD run: **3688 `GET /api/designs` (all 200)** and **4677 `GET .../export` (4661 × 200, 16 × 404)**. The export 404s are the benign `exists()`-then-read window during a concurrent replace/prune — a clean 404, never a 500.

- The **8 soft 503s** (HARD run, 4%) and **6 soft 503s** (aggressive burst) are the intended best-effort path. Body verified: `{"error":"Couldn't save right now — your work is still here; retrying.","saved":false}`. The retry absorbed the race from 43% hard-500 → 0% 500 + a small soft-503 tail.
- *The 291 × 404 in the aggressive burst were traced to root cause: the in-memory `MAX_REGISTRY=50` LRU eviction (this session had created >50 designs across phases), NOT the replace race. Isolation proof: a **clean burst that creates no new designs returned 200 × 200 saves, 0 of any error code.** A controlled test confirms an evicted rid returns the documented best-effort 404 ("That design is no longer available to save."), never a 500.
- **No leaked `meta.json.tmp`** found anywhere under `~/.kimcad/designs/*/*.tmp` after any run (the final-failure path `unlink(missing_ok=True)` + re-raise works).

### Rename race (item 1b) — **PASS**
32 concurrent renames (4 threads × 8) of one design while 4 readers polled list+export: **32 × 200, 0 silent `ok:false`.** No silent rename failures.

---

## Item 2 — QA-002 (Major): duplicate library entries — **PASS**

Fired **8 concurrent `POST /api/designs/save` for the SAME rid with NO `saved_id`.** Result: all 8 returned **200**, every response carried the **same single id**, and the library grew by **exactly ONE entry** (verified by `GET /api/designs` count delta). The per-rid `rid_saved_id` map converges the rapid auto-saves to one entry.

**No wrong-design cross-update** (the explicit "rid_saved_id maps to wrong design" regression watch): two distinct live designs auto-saved (no saved_id) got two distinct ids; re-saving A reused A's id and renamed A only — B's name stayed `DESIGN-B` untouched.

---

## Item 3 — QA-003 (Minor): mutate verb status — **PASS**

| id | rename | delete | duplicate | reopen | thumb | export |
|---|---|---|---|---|---|---|
| `..%2f..%2fetc` (unsafe) | 404 | 404 | 404 | 404 | 404 | 404 |
| `deadbeef99` (well-formed absent) | 404 | 404 | 404 | 404 | 404 | 404 |

All mutate verbs now return **404** (body `{"error":"That design couldn't be found."}`), never `200 {ok:false}`. Reopen/thumb/export also 404 as required.

---

## Item 4 — QA-006 (Nit): method-not-allowed shape — **PASS**

`PUT` / `DELETE` / `PATCH` (and `OPTIONS`) on `/api/designs` each return **405** with `Content-Type: application/json`, `Allow: GET, HEAD, POST`, and JSON body **`{"error":"Method not allowed."}`** (non-empty).

---

## Item 5 — ENG-001/ENG-003: atomic mesh export — **PASS**

Confirmed the live path (temp + `os.replace`, `pipeline.py` L445–447) didn't break normal rendering/slicing-input: a design renders (`has_mesh:true`, `status:completed`); `GET /api/mesh/<rid>` returns a valid non-empty STL (1284 B, `Content-Type: model/stl`); a `POST /api/render/<rid>` re-render returns 200 with a fresh cache-busted mesh url that also serves a valid STL. Reopen-with-sliders re-render on a saved design returns 200. (A torn read can't be forced externally; the atomic export is verified not to have broken the happy path.)

---

## Item 6 — Regression sweep — **PASS (no new regressions)**

- **Path traversal** on every endpoint (reopen/thumb/export/mesh/gcode/rename/delete/duplicate/render/slice) across 6 traversal payloads (`..%2f..%2fetc%2fpasswd`, `..\..\windows`, `....//`, `a/../../b`, `foo%00bar`, …): **zero 5xx, zero traceback leaks, zero file-content leaks** (no `root:`/`[fonts]`).
- **Zip-slip import** (`../evil.txt` + `..\evil2.txt` members + valid meta/mesh): import returned 200 (the design was created from the two known members), and the resulting design dir contains **only `mesh.stl` + `meta.json`** — the slip members were ignored. **No `evil*.txt` escaped** anywhere in or above the designs dir.
- **Decompression bomb** (200 MiB-inflating `mesh.stl`, 204 KB compressed): **clean 400** ("That file isn't a valid KimCad design export."), **server stays up** (`/api/options` → 200 immediately after).
- **Oversized import** (Content-Length 33 MiB > 32 MiB cap, raw socket, body not drained): **413 Content Too Large** returned before reading the body.
- **Malformed/garbage bodies** — save garbage/json-list/scalar → 400 `invalid request body`; rename no-name → 400; design int-prompt / blank-prompt → 400; import non-zip → 400; import empty → 400. **Zero 5xx, zero tracebacks.**
- **Full round-trip** create → auto-save → list → reopen (saved_id echoed, template restored, sliders re-render 200) → export → delete → reopen-404 → import → reopen-200, name `ROUNDTRIP` preserved: **clean end to end.** The 503/404 best-effort contracts did not confuse the round-trip.
- **NEW-regression watches** — all clear: no leaked `.tmp`; the 503 contract is a clean soft body; `rid_saved_id` does not cross-update; the mutate-404 change did not break the happy-path rename/delete/duplicate (round-trip delete returned `200 {ok:true}`, duplicate/rename worked in browser).

---

## Item 7 — UI sanity (browser, Claude_Preview) — **PASS**

Drove the SPA in a real browser (port 8765). After building "a 40 mm desk cable clip," the **Topbar shows "Saved · My Designs"** (the UX-001 auto-save indicator renders). Opening **My Designs** shows cards with **Rename / Duplicate / Export (.kimcad) / Delete** actions — the **"Export (.kimcad)"** label renders verbatim — plus Import + Sort (Newest / Oldest / Name A–Z). **Console is clean** (no errors or warnings). Inspection was DOM / accessibility-tree based (snapshot + eval); the JPEG screenshot tool was not needed, so no JPEG-timeout limitation applies.

---

## Verdict

**RESIDUAL FINDINGS: none.** Every re-checked finding (QA-001, QA-002, QA-003, QA-006, ENG-001/ENG-003) holds under adversarial load. QA-001 in particular went from a measured 43% HTTP-500 rate to **0% HTTP 500 across 730 stressed saves** (a small soft-503 tail is the intended best-effort contract).

**NEW REGRESSIONS: none.** The remediation introduced no new runtime regression: no leaked `.tmp` files, no cross-design update via the `rid_saved_id` map, no traceback leaks, the 503/404 best-effort contracts don't break the round-trip, and the path-safety / zip-slip / bomb / oversize / malformed-body invariants all still hold. The only non-200 save codes observed (soft 503, evicted-rid 404) are documented best-effort outcomes, not failures.
