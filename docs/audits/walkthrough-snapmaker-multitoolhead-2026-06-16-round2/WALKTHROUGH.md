# Walkthrough — Snapmaker U1 + Multi-Toolhead Feature (Round 2, post-remediation)

Date: 2026-06-16
Scope: re-verification after remediation touching `webapp.py`, `slicer.py`, `snapmaker_connector.py`,
`mock_moonraker.py`, `ExportPanel.tsx`, `SendPanel.tsx`, `styles.css`, `api.ts`, `config/default.yaml`.
Predecessor: `docs/audits/walkthrough-snapmaker-multitoolhead-2026-06-16/WALKTHROUGH.md` (Pass-with-one-note).

## Verdict

**PASS.** All six round-1 focus areas remain correctly wired after the remediation, the single
round-1 note (missing webapp HTTP test for the multi-head POST) is **closed**, and the single-head
path is **intact** and explicitly test-covered. No regressions found. Adversarial cross-layer review
of the `>1` → truthy-check change confirms the three layers (frontend `api.ts`, `webapp._handle_slice`,
`slice_registered_mesh`/`slicer.slice_model`) now agree on a consistent contract.

### How verified
- Live API: `kimcad web --demo --port 9185`, isolated `USERPROFILE`, probed with `urllib`, then killed.
  Health `{"version":"0.9.0b4",...}`.
- Python tests: `.venv/Scripts/python.exe -m pytest` — multi-head webapp block + full snapmaker
  connector suite: **22 passed**.
- Vitest DOM tests (node located at `C:\CivicCastTester\tools\node-v24.14.0-win-x64`): ExportPanel +
  SendPanel — **31 passed (2 files)**.

---

## Evidence by focus area

### FA-1: /api/options → snapmaker_u1 toolhead_count:4 — **Working**

Live `GET /api/options` (port 9185):
```json
{ "key":"snapmaker_u1", "name":"Snapmaker U1",
  "build_volume":[270.5,271.0,270.05], "sliceable":true,
  "materials":["pla","petg","tpu","abs"], "generic_materials":[], "toolhead_count":4 }
```
`toolhead_count(snapmaker_u1)=4`, `toolhead_count(bambu_p2s)=1` (live). `config/default.yaml`
`snapmaker_u1.toolhead_count: 4` → `Config.printer()` (`config.py:291`) → `_printer_entry`
(`webapp.py:555`) → API. Backed by `test_web_options_carries_toolhead_count` (PASS). **Working.**

### FA-2: SnapmakerConnector registry → build_connector("snapmaker") — **Working**

`connectors.py:21` import; `:35` `_CONNECTOR_CLASSES["snapmaker"]: SnapmakerConnector`; `:200–208`
`build_connector` `if cc.type == "snapmaker": return SnapmakerConnector(...)` (not MoonrakerConnector).
`snapmaker_connector.py:32` `class SnapmakerConnector(MoonrakerConnector)`. Live proof: `/api/connectors`
lists `snapmaker_u1`; `/api/connector-status/snapmaker_u1` returns a typed
`{"reason":"config","note":"...has no address configured."}` — a real SnapmakerConnector was built and
reported cleanly (no crash/500). **Working.**

### FA-3: slicer.py + webapp multi-head path (truthy-check remediation) — **Working**

The remediation changed the gate from `len(...) > 1` to a truthy check, consistently across all layers:
- `slicer.py:220` `if settings.filaments:` → repeated `--filament-config fp`; else `--load-filaments`
  (single). (ENG-002 comment at `:218`.)
- `webapp.py:660` `slice_registered_mesh`: `if filament_slots:` rebuilds `SliceSettings(filaments=...)`.
- `webapp.py:2479–2489` `_handle_slice`: for `toolhead_count > 1`, builds a length-N tuple where each
  slot falls back to `material_key`, then sets `filament_slots = slots` **unconditionally** (the old
  `if any(slots):` gate is gone). Cache key (`:2492`) stays a tuple for multi-head so it can never
  collapse to the single-head string key.

Adversarial check: a single-head printer keeps `toolhead_count == 1`, so `filament_slots` is never set
(`None`) → `if filament_slots:`/`if settings.filaments:` both False → single `--load-filaments` path.
A multi-head printer always yields a full length-N tuple (even length-1-style edge cases use the
config count of 4). The three truthy checks agree; no path mismatch. `resolve_filament_slots`
(`slicer.py:410`) unchanged. **Working.**

### FA-4: ExportPanel multi-toolhead UI — **Working**

`ExportPanel.tsx`:
- `:166` renders on `(selectedPrinter?.toolhead_count ?? 1) > 1`.
- `:175` `<div className="kc-material-slots">` grid wrapper (CSS `styles.css:1962`).
- `:177–198` N `<label htmlFor="kc-slot-{i}">` + `<span id="kc-slot-label-{i}">Extruder {i + 1}</span>` +
  `<select id="kc-slot-{i}" aria-labelledby="kc-slot-label-{i}">` — relabeled from "T{n} Material" to
  "Extruder {n}" (UX-002).
- `:170–173` muted guidance note "Assign a filament to each extruder…".
- Per-slot post-slice summary: `:86–90` `slotMaterialNames`, `:254–257` passed to `PrintSummary`,
  `:358–365` lists "Extruder 1: PLA, Extruder 2: TPU".
- `:202–214` single-head branch renders the one "Material" select.

Vitest (`ExportPanel.test.tsx`): "renders one labeled 'Extruder n' picker per toolhead… collapses back
to a single Material select" and "surfaces the per-extruder material assignments in the post-slice
summary" both **PASS** (asserts `kc-slot-0`, `aria-labelledby=kc-slot-label-0`, Extruder 1/2 present,
Extruder 3 absent, single→multi→single transitions). **Working.**

### FA-5: SendPanel temp chips (CSS + null-guard + pre-send status) — **Working**

`SendPanel.tsx`:
- Live banner chips `:327–335`: `kc-temp-chip` with null-guard `t != null ? t.toFixed(0) : '—'`.
- **New pre-send status line** (UX-006) `:130–152` one-shot read for a configured non-simulated
  connector; rendered `:256–276` as `<p className="kc-send-live kc-presend-status">` with "Printer
  status" label + chips (also null-guarded); cleared on send (`:166`) so the live banner takes over.
- CSS: `styles.css:3307` `.kc-send-temps`, `:3312` `.kc-temp-chip` (border/radius/mono), `:3297`
  `.kc-send-live`. (`.kc-presend-status` is a co-class on `.kc-send-live`; no separate rule needed.)

Vitest (`SendPanel.test.tsx`): "shows a pre-send 'Printer status' line with temperature chips"
asserts `T1: 205°C` and the null element renders `T2: —°C` (ENG-004); "shows no pre-send status line
for a simulated (test) connection" confirms the simulated exclusion. Both **PASS**. **Working.**

### FA-6: /api/connector-status carries toolhead_temps + nozzle_temp_c — **Working**

`webapp.py:1820–1823`: `if st.nozzle_temp_c is not None: resp["nozzle_temp_c"]=...` and
`if st.toolhead_temps: resp["toolhead_temps"]=list(...)`. Live proof:
`GET /api/connector-status/mock` →
`{"name":"mock","ready":true,"online":true,"state":"operational","simulated":true,"nozzle_temp_c":25.0}`
— the nozzle-temp branch fires. `toolhead_temps` is conditionally included (the `mock` loopback reports a
single nozzle temp, so it is correctly omitted). The snapmaker tuple path is covered by
`test_status_returns_toolhead_temps_tuple` and `test_status_nozzle_temp_c_is_t0` (PASS). **Working.**

---

## Round-1 note closure

`tests/test_webapp.py` now has full multi-head POST coverage (the round-1 gap), all PASS:
- `test_slice_multihead_forwards_filament_slots` — `filament_slot_0..3` → `("pla","petg","pla","abs")`.
- `test_slice_multihead_with_no_slots_fills_full_tuple` — no slot fields → `("pla","pla","pla","pla")`
  (proves the unconditional-tuple remediation: never collapses to the single-head key).
- `test_slice_multihead_distinct_slots_are_distinct_slices_same_are_cached` — tuple is part of the
  cache key (distinct tuples = 2 slices, repeat = cache hit).
- `test_slice_single_head_ignores_filament_slots` — `bambu_p2s` with `filament_slot_*` fields present →
  slicer called with `filament_slots is None`.

**Note CLOSED.**

## Single-head path intact

- `test_slice_single_head_ignores_filament_slots` (PASS): a single-head printer ignores stray
  `filament_slot_*` fields and slices with `filament_slots=None` (one material).
- ExportPanel single-head branch (`:202`) renders one "Material" select; vitest verifies the
  multi→single collapse.
- `slicer.py:223` / `webapp.py:660` truthy checks route a `None`/empty `filaments` to the single
  `--load-filaments` path. Live `bambu_p2s` (`toolhead_count:1`) confirmed in `/api/options`.

**Single-head path: INTACT.**

---

## Findings

- **No new findings.** No Blocker / Critical / Major / Minor / Nit.
- Carried-over round-1 observations (non-defects, unchanged): `/api/printers` is not a route — the
  printer list is `/api/options` (named correctly in `api.ts` `getOptions()`); `nozzle_diameter_mm` is
  surfaced via `PrinterCapabilities` (live connector), not the static `/api/options`. Neither is a
  regression.

## Environment notes (not feature findings)

- Live `/api/design` POST over plain `urllib` returns 403 `reason:session` (CSRF/session token is a
  browser-only flow). The end-to-end slice path is instead proven by the four `test_webapp.py` tests,
  which drive the real HTTP server through the session layer. Not a defect.
- Node.js is not on PATH on this box; vitest was run via the located runtime at
  `C:\CivicCastTester\tools\node-v24.14.0-win-x64`. Tests pass identically.

## What's working (summary)

Config→API pipeline (toolhead_count:4); SnapmakerConnector registry + dedicated build_connector branch;
the cross-layer truthy-check multi-head slice contract (api.ts → _handle_slice → slice_registered_mesh →
slicer.slice_model); ExportPanel per-extruder UI (grid, "Extruder n" relabel, htmlFor/id, per-slot
summary); SendPanel temp chips with null-guard + pre-send status line + CSS; conditional
toolhead_temps/nozzle_temp_c in connector-status. 22 Python + 31 vitest tests green.
