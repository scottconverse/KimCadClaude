# Sprint Punch List — Snapmaker U1 + Multi-Toolhead Feature

**Audit date:** 2026-06-16

---

## Must-fix (Criticals)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | ENG-001 | Critical | Engineering | Fix `any(slots)` collapse in `_handle_slice`: when a multi-head printer's slot fields are all absent/empty, guard with explicit check so the key doesn't silently become the single-head form. Either raise a clear validation error or keep `filament_slots=None`. | S |
| 2 | TEST-001 | Critical | Test | Add `test_slicer.py` coverage for `resolve_filament_slots()`: happy path (all keys present → correct paths), missing-key error (raises `OrcaProfileError`), empty material_keys list. | S |
| 3 | TEST-002 | Critical | Test | Add `test_slicer.py` test for the `--filament-config` multi-head branch in `slice_model()`: mock the slicer binary, pass `SliceSettings(filaments=(path1, path2))`, assert `--filament-config path1 --filament-config path2` is in the subprocess call. | S |
| 4 | UX-001 | Critical | UI/UX | Add CSS rules for `.kc-send-temps` and `.kc-temp-chip` in `frontend/src/index.css` (or equivalent). Chips should render as inline-flex pill badges with a subtle border/background matching the existing tone system. Verify at light + dark themes. | S |
| 5 | DOC-001 | Critical | Docs | Add Snapmaker U1 + multi-toolhead entry to `CHANGELOG.md` under the appropriate version section: new connector type, toolhead_count field, N material dropdowns, T1–TN temp chips, pause/resume/cancel. | S |
| 6 | DOC-002 | Critical | Docs | Update `docs/api.md`: (a) add `toolhead_count: integer` to the `PrinterOption` response table; (b) add `nozzle_temp_c` and `toolhead_temps` to the connector-status response; (c) add `filament_slot_0..filament_slot_N-1` to the `/api/slice` POST body table with a note on when they apply. | M |
| 7 | DOC-004 | Critical | Docs | Add Snapmaker U1 row to `docs/supported-printers.md` with build volume, toolhead count, connector type, and a note pointing to the commented-out `local.yaml` block in `config/default.yaml`. | S |

---

## Should-fix (high-leverage Majors)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | TEST-003 | Major | Test | Add `test_webapp.py` HTTP-layer tests for multi-head slice: (a) POST with `filament_slot_0/1` builds tuple key; (b) same slots → cache hit; (c) different slots → cache miss; (d) single-head printer ignores slot fields. | M |
| 2 | ENG-002 | Major | Engineering | Fix `slice_model()` branch: `if settings.filaments and len(settings.filaments) > 1` → change to `if settings.filaments` (any non-empty filaments tuple, including length-1, should use `--filament-config`). | S |
| 3 | UX-002 | Major | UI/UX | Change label from `T{i+1} Material` to `Extruder {i+1} filament` (or `Slot {i+1}`). Add a one-line helper note below the slot block: "Each extruder can use a different filament — assign a material to each." | S |
| 4 | DOC-006 | Major | Docs | Add `snapmaker_connector.py` to the module table in `ARCHITECTURE.md` alongside `moonraker_connector.py`. | S |

---

## Suggested sequencing

Fix ENG-001 and ENG-002 together (same file area, both surgical). Add TEST-001/002/003 in the same commit — they're all in `test_slicer.py` / `test_webapp.py` and can share a mock-slicer fixture. Then ship the CSS fix (UX-001) as a standalone one-commit change. Batch the four doc updates (DOC-001/002/004/006) into a single doc commit. The copy fix (UX-002) is one line and can ride with the CSS commit.

ENG-001 must precede TEST-003: write the correct behavior first, then assert it.

---

## Items deferred to next sprint

- **ENG-003** — `toolhead_count` at slice time from static config vs live connector: requires product decision on whether KimCad should re-query capabilities before slicing.
- **ENG-004** — Null temp from disconnected extruder shortens `toolhead_temps` tuple below `toolhead_count`.
- **UX-003** — No layout cap on N dropdowns (Slice CTA scrolls off at N > 3).
- **UX-004** — Per-slot assignments invisible in post-slice summary.
- **UX-005** — Explicit `htmlFor`/`id` on dynamic slot labels for accessibility.
- **TEST-004** — Mock always returns 4 extruders; partial configurations (2-of-4, 3-of-4) never tested.
- **QA-001** — `test_capabilities_toolhead_count_at_least_1` floor guard never actually exercised.

---

## Sign-off gate

- [ ] All 7 Criticals fixed and verified (ENG-001, TEST-001, TEST-002, UX-001, DOC-001, DOC-002, DOC-004)
- [ ] Regression pass: run full pytest + vitest suite after changes
- [ ] CHANGELOG entry reflects the feature accurately
- [ ] `api.md` field names match what `api.ts:postSlice` actually sends (`filament_slot_0`, `filament_slot_1`, etc.)

---

*Full detail for every ID in the matching deep-dive files.*
