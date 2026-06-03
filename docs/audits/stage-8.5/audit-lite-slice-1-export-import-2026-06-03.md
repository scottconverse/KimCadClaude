# Audit Lite — Stage 8.5 Slice 1: export/import + search/sort
**Date:** 2026-06-03
**Scope:** `DesignStore.export_bytes`/`import_bytes`, the webapp export/import endpoints + `_read_raw_body`, `api.exportDesignUrl`/`importDesign`, the MyDesigns toolbar (export link, import button, search, sort), the toolbar CSS, and the tests. Security + UX weighted.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one Major + one Minor. Export/import + search/sort complete Slice 1 cleanly: export is a real attachment zip, import is **zip-slip-safe** (reads only the three known files by exact name — never the archive's paths — verified by a `../evil.txt` test), the body is size-capped, and the flow round-trips (export → import → reopen with restored sliders), verified live. The one real gap: `import_bytes` decompresses each zip member with an **unbounded** `z.read()`, so a crafted `.kimcad` (a decompression bomb) could exhaust memory on import. Plus a small test gap on the empty-search state.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)".

**As found:** 0 Blocker · 0 Critical · 1 Major · 1 Minor · 0 Nit.

## Findings

### EI-001 Major: import decompresses zip members unbounded → a decompression bomb can exhaust memory
**Dimension:** Security / Correctness
**Evidence:** `design_store.py:258,261,262` — `import_bytes` does `json.loads(z.read("meta.json"))`, `z.read("mesh.stl")`, `z.read("thumb.png")`. `ZipFile.read()` inflates the entry fully into memory. `MAX_IMPORT_BYTES` (32 MiB) bounds the *compressed* upload, but a single highly-compressed member can inflate to gigabytes (a classic zip bomb), so importing a crafted `.kimcad` OOMs / crashes the local server.
**Why it matters:** Export/import exists *for sharing* designs, so a user will import files from others — exactly the channel a malicious `.kimcad` arrives through. It's local-only and recoverable (restart), so a resource-exhaustion DoS rather than data loss/RCE — but it's reachable and trivially weaponized, and the fix is small.
**Fix path:** Read each member with a bounded read instead of `z.read()`: `with z.open(name) as f: data = f.read(LIMIT + 1)` and reject (return False → 400) if `len(data) > LIMIT`. Add a `_MAX_IMPORT_FILE` (e.g. 64 MiB) per-entry ceiling — generous for a real STL, fatal to a bomb. The `ValueError` it raises is already swallowed by `import_bytes`'s broad `except → False`. Add a test: a zip whose `mesh.stl` declares/inflates past the cap → `import_bytes` returns False (no OOM).
**Blast radius:** Adjacent: only `import_bytes` reads zip members. Shared state: none. User-facing: a bomb import now cleanly 400s instead of hanging/crashing. Migration: none. Tests to update: add the bomb-rejection test.

### EI-002 Minor: the empty-search ("no matches") state has no test
**Dimension:** Tests
**Evidence:** `MyDesigns.tsx` renders `No designs match "<query>"` when `shown.length === 0` with designs present; the frontend search test filters to *one* match, not *zero*, so the empty-results branch is unpinned.
**Why it matters:** A regression that broke the empty-results message (e.g. showing a blank grid or the "nothing saved" empty state instead) would pass the suite.
**Fix path:** Add a MyDesigns test: with one design, type a non-matching query → assert the "No designs match" text shows and no card renders.

## What's working
- **Import is zip-slip-safe.** `import_bytes` reads ONLY `meta.json`/`mesh.stl`/`thumb.png` by exact name and writes them to `dst/<name>` — it never calls `extractall` and never uses the archive's own paths. The store test plants a `../evil.txt` entry and asserts it's *not* written outside the dir; the valid design still imports. The new id is server-minted (uuid) and `_safe_id`-guarded.
- **The body is capped.** `_read_raw_body` rejects `> MAX_IMPORT_BYTES` (413 + `close_connection`) and an empty/missing-length body (400, via `declared <= 0`), mirroring `_read_json_body` — the import endpoint can't read an unbounded *compressed* body. (The gap is the *inflated* size — EI-001.)
- **Best-effort, no traceback leaks.** `export_bytes` catches `(OSError, BadZipFile) → None`; `import_bytes` wraps everything in `except Exception → False`; a corrupt/truncated/non-zip upload → 400 (tested `import-rejects-garbage`), never a 500.
- **The round-trip is real and verified.** Export → 200 `application/zip`, `Content-Disposition: attachment; filename="kimcad-design-<id>.kimcad"`, PK header, 2905 bytes (live). Import re-keys meta's id to the fresh uuid, the imported design coexists with the original (count 2), and reopens with its template sliders restored (HTTP test). The frontend Import reloads + opens the new design and resets the file input so the same file can be re-imported.
- **UX is solid (verified live).** Per-card Export is a plain `<a download>` (no JS); the Import button proxies a hidden `.kc-sr-only` file input (the standard accessible pattern) and shows "Importing…" + an error on a bad file; search filters by name (case-insensitive, tested), sort offers Newest/Oldest/Name; the toolbar only renders when designs exist. Mobile 375: head/toolbar/search all within the viewport, no overflow.
- **Tested.** Store: export round-trip, export-none-for-unsafe-id, import-rejects-non-zip/missing-mesh/**zip-slip**. Webapp: HTTP export→import→reopen, garbage→400. Frontend: export href + download attr, search filter, import-file→`importDesign`+`onOpen`. 15 store + 55 vitest, all green; ruff + tsc + build clean.

## Watch items
- **`_read_raw_body` reads inside no try/except** (a mid-upload socket error would escape the handler) — but this mirrors the existing `_read_json_body` pattern, so it's consistent, not a new regression. If hardened later, do both together.

## Escalation recommendation
No escalation needed. One Major (a bounded-read fix for the decompression bomb) and one Minor test gap on a slice whose round-trip + zip-slip safety + UX are verified working. Fix both, re-audit to 0/0/0/0/0, push — and this closes Slice 1, so the Slice-1 `audit-team` runs next.

---

## Re-audit (resolution) — 0/0/0/0/0

- **EI-001 (Major) — FIXED.** `import_bytes` now reads each member via `_read_zip_member` — a bounded read (`f.read(_MAX_IMPORT_MEMBER + 1)`, ceiling 64 MiB) that raises `ValueError` (→ swallowed → import rejected, 400) if a member inflates past the cap, so a decompression bomb can't exhaust memory. New test `test_import_rejects_an_oversized_member` (cap shrunk to 8 → a normal entry exceeds it → `import_bytes` returns False, nothing written).
- **EI-002 (Minor) — FIXED.** New MyDesigns test: a non-matching search query renders the "No designs match" message and removes the card.

Verified: ruff clean; `test_design_store.py` 16 + `test_webapp.py` 59 = 75 passed; `npm run test` 56 passed; `tsc` + `build` clean. **Roll-up: 0/0/0/0/0.** This closes Stage 8.5 Slice 1 (persistence + My Designs + export/import + search/sort) — the Slice-1 `audit-team` runs next.
