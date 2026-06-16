# Walkthrough — Snapmaker U1 + Multi-Toolhead — Round 3 (residual-fix confirmation)

**Date:** 2026-06-16
**Scope:** Confirm NO regression to the end-to-end multi-toolhead feature after a small residual-fix pass.
**Verdict:** **PASS** — clean. No regression found. No open issues.

## Changes under review this round

1. **ENG-101** — `snapmaker_connector.py::status()` keeps a null-temperature head's index as `None` instead of dropping it (index-stable T-labels).
2. **UX-201** — `.kc-material-slots` CSS `auto-fill` → `auto-fit` (collapses empty tracks).
3. **NEW-DOC-01** — docs Z build-volume figure `270.1` → `270.05`.
4. Frontend `api.ts`: `toolhead_temps` widened to `(number | null)[] | null`. SPA rebuilt.

## Method

Harness cannot drive the live browser UI on this box (exclusive port bind), so verification was at
the **API layer + source code + vitest DOM tests + pytest**, per directive.

- Server: `python -m kimcad.cli web --demo --port 9186` (entry point `kimcad.cli`), isolated
  `USERPROFILE`/`HOME` temp profile, background. Health polled → 200 on first try
  (`{"version":"0.9.0b4","openscad":true,"orcaslicer":true,"cadquery":true}`).
- venv python: `C:\Users\scott\Desktop\Code\kimcadclaude\.venv\Scripts\python.exe`.

## API results observed (all PASS)

| Check | Result |
|---|---|
| `GET /api/options` → `snapmaker_u1` | `toolhead_count: 4`, `build_volume: [270.5, 271.0, 270.05]` — **PASS** |
| `GET /api/options` → `bambu_p2s` | `toolhead_count: 1` — **PASS** |
| `GET /api/connectors` → `snapmaker_u1` | `simulated:false, configured:false` — **PASS** |
| `GET /api/connectors` → `default` | `"mock"` — **PASS** |
| `GET /api/connector-status/snapmaker_u1` | HTTP **200**, `ready:false, reason:"config"`, note "has no address configured" — clean, no 500 — **PASS** |
| `GET /api/connector-status/mock` | HTTP **200**, `ready:true, online:true, state:"operational", simulated:true, nozzle_temp_c:25.0` — **PASS** |

## Code / test confirmation (all PASS)

**Multi-toolhead UI intact (`ExportPanel.tsx`):**
- Per-extruder dropdowns labeled `Extruder N` (`{i + 1}`) inside `.kc-material-slots`.
- Single-head branch renders the one `Material` dropdown with NO slots (`toolhead_count <= 1`).
- Per-slot post-slice summary (`PrintSummary` → `Extruder 1: …, Extruder 2: …`) intact.
- Slice sends `filament_slot_N` only when `toolhead_count > 1` (`postSlice` guards `length > 1`).

**CSS (UX-201):** Source `styles.css:1966` and the **rebuilt** SPA asset
`src/kimcad/web/assets/index.css` both have `.kc-material-slots { … repeat(auto-fit, minmax(170px,1fr)) }`.
The two other `auto-fill` rules in source are unrelated grids (lines 2223, 2549) — not material-slots. No stale `auto-fill` on the changed selector.

**SendPanel null-guard (`SendPanel.tsx`):** Both the pre-send status line (l.264) and the live
banner (l.331) render each temp as `t != null ? t.toFixed(0) : '—'`, correctly handling a `null`
element in the now-`(number|null)[]` array. `toolhead_temps?: (number | null)[] | null` confirmed in `api.ts`.

**Backend ENG-101 (`snapmaker_connector.py::status()`):** Present-but-null head appends `None`
(index-stable); absent head is skipped. `nozzle_temp_c = temps[0]`. No NaN/null ever malforms JSON.

**Tests run green:**
- pytest `test_snapmaker_connector.py` + `test_slice_uses_filament_config_for_single_element_filaments` → **18 passed**.
  - `test_status_preserves_index_for_null_temp_head` asserts `toolhead_temps == (210.0, None, 200.0, 195.0)`, `nozzle_temp_c == 210.0` — proves ENG-101 directly.
- vitest `SendPanel.test.tsx` + `ExportPanel.test.tsx` → **31 passed** (2 files).
  - SendPanel test renders `toolhead_temps: [205, null]` → `T2: —°C` without crashing on `toFixed` — proves the null-guard for the widened type.

**Single-head path intact:** `bambu_p2s` reports `toolhead_count: 1`; ExportPanel renders one
material dropdown, no `filament_slots`. Proven by
`tests/test_slicer.py::test_slice_uses_filament_config_for_single_element_filaments`.

**Docs (NEW-DOC-01):** `docs/supported-printers.md:67` now `270.5 × 271.0 × 270.05`. No stale
`270.1` remains in any shipped doc (README / CHANGELOG / docs, excluding prior audit reports). Config `default.yaml:453` and tests already used `270.05`.

## Adversarial checks (nothing broken)

- Looked for `auto-fill` accidentally left on `.kc-material-slots` in built asset → not present (auto-fit).
- Looked for a `toFixed` on a possibly-null element without a guard → both call sites guarded.
- Looked for index-shift regression when a middle head is null → test asserts index stability.
- Verified `connector-status/snapmaker_u1` returns a soft 200 (not a 500) for the unconfigured case.
- Verified the loopback `mock` connector still answers cleanly.

## Cleanup

Server killed (post-kill health HTTP 000, connection refused; port 9186 free). Isolated temp
profile dir removed.

## Open issues

**None.** Clean pass.
