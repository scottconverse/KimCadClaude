# #19 — Template Catalog Breadth + Honest Tiering — Implementation Plan

> **For agentic workers:** this is executed slice-by-slice on `main` (KimCad standing cadence), each slice TDD → audit-lite → gate → push. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Meaningfully broaden KimCad's deterministic template catalog from 7 to ~32 families — every new family with real OpenSCAD geometry, an analytic bbox the Printability Gate validates, a trusted CadQuery STEP twin, and a visible honesty **tier** — without importing the reference repo's breadth-inflation.

**Architecture:** Families stay pure pydantic data in `src/kimcad/templates.py::_build_default_families()`. Each binds a real `library/*.scad` module (authored by us — the reference ships none liftable), declares its envelope analytically (`bbox_x/y/z`), and gets a CadQuery twin in `cadquery_templates.py::_EMITTERS`. A new `tier` field (`benchmarked` | `baseline`) threads to `/api/templates` → `api.ts` → `LibraryModal` as a badge. The gate is tier-blind — every family is render-verified regardless of label.

**Tech Stack:** Python 3.13 (pydantic v2, stdlib http), OpenSCAD library modules, CadQuery (trusted-twin worker), React/TS SPA (vitest), pytest with `live`/`real_tool`/`needs_cadquery` markers.

---

## Context & load-bearing findings (from the 6-agent subsystem map, 2026-06-13)

1. **Our architecture is already more honest than the reference's.** Every family in our registry is auto-subjected to live render-vs-analytic-bbox tests (OpenSCAD 0.01 mm, CadQuery twin 0.5 mm), a deterministic-rerender bench (0.05 mm, <5 s), and a STEP-coverage gate. **A family cannot ship unverified.** The reference's "275 capabilities" = 37 real bespoke generators + **238 label-only families that all collapse to 5 generic primitives** (ring/tray/clip/panel/block) by keyword-matching the family *name*. A "servo mount" emits a plain box.

2. **Nothing is drop-in liftable.** The reference emits OpenSCAD as Python f-strings; its own seed `.scad` modules are dead code; it barely uses vendored BOSL2. Porting = authoring our own `library/*.scad` from ~38 trivial CSG recipes (cube/cylinder/linear_extrude). This matches our existing convention.

3. **Three printable modules already exist UNUSED in our repo:** `pegboard_hook` (hooks.scad), `spool_holder` (holders.scad), `l_bracket` (bracket.scad) — cheap first families (geometry done; need registry entry + verified-render pin + twin).

4. **The `tier` field is a clean 4-hop add** (TemplateFamily → /api/templates dict → api.ts type → LibraryModal card) and the gate never sees it (`run_gate(report, plan, printer, material)` has no family/tier param — baseline families are gated identically).

5. **The bbox must be LINEAR over the slider range.** A module `max(...)` floor that bends the envelope (wall_hook's `arm_z0`) is handled by pinning the param's min so the analytic formula stays exact (wall_hook `plate_h` min=24 precedent).

## Locked decisions (dev authority; grounded in Scott's honesty hard rule)

- **D1 — Real geometry only.** Port the ~25 most useful real (Tier-A) families as first-class. **Do NOT replicate the 238 label-only families** — that is the dishonest breadth Scott rejected for printers ("saying we support X when really Y isn't honest").
- **D2 — No new dependencies.** No BOSL2 vendor, no OCCT/CadQuery-only families. Author plain-primitive OpenSCAD (cube/cylinder/linear_extrude), matching our current modules. (The 3 reference "precision" fillet families are deferred; fillet support can fold into existing OpenSCAD families later if wanted.)
- **D3 — Every new family gets a STEP twin.** No weakening of `test_every_shipped_family_has_a_step_emitter`. All families are simple prismatic/cylindrical CSG, so twins are cheap and the "every shipped part exports editable STEP" promise stays intact.
- **D4 — Tier = real-world fitness, NOT code quality.** Since every family is gate-verified geometry, `tier` communicates whether the user must check fitness before real use:
  - **`benchmarked`** — what-you-set-is-what-you-get; no hidden fitness caveat (boxes, plates, spacers, brackets, hooks, clips, dividers, raceways, funnels, handles, stands…).
  - **`baseline`** — real verified geometry, but a fitness caveat the user must verify: threaded relief ≠ certified threads (nut/bolt), Gridfinity-*compatible* geometry (bin/baseplate), VESA *pattern* (verify your device), heat-set pocket (verify your insert spec), French cleat (verify load). UI shows "verify dimensions, fit & load before real use."
- **D5 — Default tier = `benchmarked`.** Existing 7 families compile unchanged; `baseline` is opt-in per family.
- **D6 — Replace the brittle `==7` tripwires** (test_templates.py:60, :119; test_template_bench.py:155) with a single maintained `EXPECTED_FAMILY_NAMES` frozenset asserted against the registry — one place to update per slice, still a deliberate "declare your new family" tripwire, DRY.

## Target catalog (32 families: 7 existing + 25 net-new)

Existing (all → `benchmarked`): snap_box, box, enclosure, tube, wall_hook, cable_clip, drawer_divider.

Net-new, by slice (aliases below are **collision-checked** against the 36 existing normalized aliases — duplicates raise at import):

| # | family | tier | .scad module | geometry (twin) | key params | bbox formula |
|---|--------|------|-------------|-----------------|-----------|--------------|
| **Slice 2 — modules already in repo** ||||||
| 1 | `pegboard_hook` | benchmarked | hooks.scad (exists) | plate + 2 pegs + arm + lip | plate_w, hole_spacing, arm_length | [plate_w, peg_len+plate_t+arm_length, hole_spacing+2·arm_size+16] |
| 2 | `spool_holder` | benchmarked | holders.scad (exists) | back plate + axle arm | plate_w, spool_width, plate_h | [plate_w, plate_t+spool_width+15, plate_h] |
| 3 | `l_bracket` | benchmarked | bracket.scad (exists) | 2 orthogonal plates + 2 holes | arm, width, thick | [arm, width, arm] |
| **Slice 3 — ring/cylinder batch** (new `rings.scad`) ||||||
| 4 | `washer` | benchmarked | rings.scad (new) | annulus | od, id, thickness | [od, od, thickness] |
| 5 | `dowel_pin` | benchmarked | rings.scad (new) | solid cylinder | diameter, length | [diameter, diameter, length] |
| 6 | `bumper_foot` | benchmarked | rings.scad (new) | cyl − counterbore | diameter, height, hole_d | [diameter, diameter, height] |
| 7 | `mounting_flange` | benchmarked | rings.scad (new) | disc − bore − 4 bolt holes | diameter, thickness, bore_d | [diameter, diameter, thickness] |
| **Slice 4 — plate/panel batch** (new `plates.scad`) ||||||
| 8 | `plate_with_hole` | benchmarked | plates.scad (new) | cube − center cyl | width, depth, height, hole_d | [width, depth, height] |
| 9 | `faceplate` | benchmarked | plates.scad (new) | plate + 4 corner holes | width, height, thickness, hole_d | [width, height, thickness] |
| 10 | `vesa_plate` | **baseline** | plates.scad (new) | plate + square hole pattern | width, height, thickness, vesa_spacing | [width, height, thickness] |
| **Slice 5 — bracket/mount batch** (new `mounts.scad` additions) ||||||
| 11 | `corner_gusset` | benchmarked | gussets.scad (new) | linear_extrude triangle | width, leg, thickness | [width, leg, leg] |
| 12 | `pcb_standoff` | benchmarked | mounts.scad (add) | base + 4 standoffs + holes | board_w, board_d, standoff_h | [board_w, board_d, base_t+standoff_h] |
| 13 | `french_cleat` | **baseline** | cleats.scad (new) | 45° stepped profile | length, depth, rise | [length, depth, rise] |
| 14 | `heatset_pocket` | **baseline** | mounts.scad (add) | boss + blind pocket | boss_d, height, pocket_d | [boss_d, boss_d, height] |
| **Slice 6 — box/tray batch** (new `boxes2.scad` / additions) ||||||
| 15 | `snap_fit_box` | benchmarked | containers.scad (add) | body + lid + tabs (lid beside body) | width, depth, height, wall | [width, depth+gap+depth, height] (lid printed beside) |
| 16 | `lidded_box` | benchmarked | containers.scad (add) | box + hinge cylinder | width, depth, height, wall | [width, depth+hinge_r, height] |
| 17 | `clamp_block` | benchmarked | clamps.scad (new) | block − slot − screw hole | width, depth, height, slot_w | [width, depth, height] |
| 18 | `cable_raceway` | benchmarked | raceway.scad (new) | floor + 2 walls + cover | length, width, height, wall | [length, width, height] |
| 19 | `handle_grip` | benchmarked | handles.scad (new) | 2 posts + top rail | span, height, depth | [span, depth, height] |
| 20 | `stand_dock` | benchmarked | stands.scad (new) | base + backrest + lip | width, depth, back_h | [width, depth, back_h] |
| **Slice 7 — specialty/baseline batch** ||||||
| 21 | `funnel` | benchmarked | funnels.scad (new) | hollow truncated cone | inlet_d, height, outlet_d, wall | [inlet_d, inlet_d, height] (inlet ≥ outlet) |
| 22 | `gridfinity_bin` | **baseline** | gridfinity.scad (new) | 42 mm-pocket bin + foot | grid_w, grid_d, height | [42·grid_w, 42·grid_d, height] |
| 23 | `gridfinity_baseplate` | **baseline** | gridfinity.scad (new) | plate + grid ribs | grid_w, grid_d, height | [42·grid_w, 42·grid_d, height] |
| 24 | `threaded_nut` | **baseline** | threads.scad (new) | hex prism − bore (relief only) | hex_d, height, relief_d | [hex_d, hex_d·1.1547, height] |
| 25 | `threaded_bolt` | **baseline** | threads.scad (new) | hex head + shaft (relief only) | head_d, length, thread_d, head_h | [head_d, head_d·1.1547, head_h+length] |

> Exact defaults / min / max / bbox constants are **render-verified per family during TDD** (pinned in `tests/test_library_modules.py::NEW_MODULES`), never guessed — same discipline as the existing 7 (`templates.py:319-321`). The table fixes the *shape, params, aliases, tier, and bbox structure*; TDD nails the numbers.

---

## The per-family RECIPE (the shared TDD code for slices 2–7)

Every net-new family follows this exact loop. This recipe IS the implementation for each table row — apply it per family, substituting the row's data.

- [ ] **R1 — Author / confirm the `.scad` module.** In `library/<file>.scad`, write `module <name>(<params>, fn=...)` with: every param defaulted, a **documented analytic bounding box in the header comment**, corner-at-origin convention (matches `_CF`). If the row reuses an existing module (slice 2), skip to R2. Avoid `max(...)`-induced bbox bending, or pin the param min to keep the envelope linear (wall_hook precedent).
- [ ] **R2 — Pin the module via a real render (TDD red→green).** Add a `NEW_MODULES` entry in `tests/test_library_modules.py` (file, representative call, expected bbox). Run `pytest tests/test_library_modules.py -k <name>` (marked `real_tool`) — it renders the REAL module, asserts watertight, and compares the rendered envelope to the documented bbox within 0.01 mm. Adjust the bbox literal to the measured value.
- [ ] **R3 — Add the `TemplateFamily`** in `_build_default_families()`: `name`, `summary`, `object_types` (the row's collision-checked aliases — singular + needed plurals/synonyms), `library_file`, `module`, `params` (ParamSpec: `name` = module param name, `dim_keys`, `bbox_axis` only for true envelope axes), `fixed_args`, `bbox_x/y/z` (BBoxTerm tuples matching R2's measured envelope; empty `ref` = constant), `gaps` (only if two sliders can collapse the geometry), and `tier=` per the row (omit for benchmarked = default).
- [ ] **R4 — Register + update the tripwire.** Append the family to the `return (...)` tuple and add its `name` to `EXPECTED_FAMILY_NAMES` (slice 1's frozenset). Importing `kimcad.templates` now proves no empty-axis / no alias-collision.
- [ ] **R5 — Write the CadQuery twin** `def _<name>(v): -> str` in `cadquery_templates.py`: assigns `result`, **no imports**, every value via `_f(...)`, passes the sanitizer, geometry mirrors the `.scad` corner-for-corner. Register `"<name>": _<name>` in `_EMITTERS` keyed by `family.name`. (Reuse helpers — the ring batch shares one annulus pattern.)
- [ ] **R6 — Run the auto-attached gates.** `pytest tests/test_templates.py tests/test_cadquery_templates.py tests/test_template_bench.py -k <name> -v` — the data-driven parametrized tests now cover the family: OpenSCAD render-vs-bbox (0.01 mm), CadQuery twin render-vs-bbox (0.5 mm, >1024-byte .step), emitter-contract+sanitizer, STEP coverage, deterministic re-render <5 s.
- [ ] **R7 — Behavioral test** (only if the family has novel clamp/alias rules): add a targeted test in `tests/test_templates.py` (alias routing, a gap that prevents collapse). Skip for families with no special clamp behavior.
- [ ] **R8 — Commit the family** (or the slice's batch): `git add -A && git commit`.

---

## Slice 1 — Tier scaffolding (no new families) — FULL TDD

**Files:**
- Modify: `src/kimcad/templates.py` (add `tier` field to `TemplateFamily`; tag the 7 families; add `EXPECTED_FAMILY_NAMES`)
- Modify: `src/kimcad/webapp.py:896-903` (add `"tier": f.tier`)
- Modify: `frontend/src/api.ts:387-395` (add `tier` to `TemplateFamilyInfo`)
- Modify: `frontend/src/components/LibraryModal.tsx:98-112` (tier badge + search)
- Modify: `frontend/src/styles.css` (`.kc-library-tier*`)
- Modify: `tests/test_templates.py` (replace `==7`/name-set tripwires with `EXPECTED_FAMILY_NAMES`; add tier-default test)
- Modify: `tests/test_template_bench.py:155` (use `len(EXPECTED_FAMILY_NAMES)`)
- Test: `tests/test_webapp.py` (/api/templates includes tier), `frontend/src/components/LibraryModal.test.tsx` (badge)

- [ ] **Step 1: Failing test — `tier` field defaults to benchmarked.** In `tests/test_templates.py`:
```python
def test_every_family_has_a_tier_and_defaults_to_benchmarked():
    fams = default_registry().families()
    assert all(f.tier in ("benchmarked", "baseline") for f in fams)
    # the 7 shipped families are all benchmarked geometry
    assert all(f.tier == "benchmarked" for f in fams)
```
Run: `pytest tests/test_templates.py -k tier -v` → FAIL (`TemplateFamily has no attribute tier`).

- [ ] **Step 2: Add the field.** In `templates.py`, in `TemplateFamily` (after `gaps`):
```python
# Honesty tier surfaced in the library picker. "benchmarked" = what-you-set-is-what-you-get;
# "baseline" = real, gate-verified geometry but a fitness caveat the user must check before
# real use (e.g. thread RELIEF not certified threads, Gridfinity-compatible, VESA pattern).
# Inert to the Printability Gate — every family is render-verified regardless of label (#19).
tier: Literal["benchmarked", "baseline"] = "benchmarked"
```
Add `from typing import Literal` at the top. Run Step 1 → PASS (default applies to all 7).

- [ ] **Step 3: Failing test — registry matches the declared name set (DRY tripwire).** Replace the `==7` / exact-name-set assertions in `test_templates.py` with:
```python
EXPECTED_FAMILY_NAMES = frozenset({
    "snap_box", "box", "enclosure", "tube", "wall_hook", "cable_clip", "drawer_divider",
})  # grows with each #19 slice — the single place to declare a new family

def test_registry_matches_the_declared_family_set():
    names = {f.name for f in default_registry().families()}
    assert names == EXPECTED_FAMILY_NAMES
```
Update `test_template_bench.py:155` `assert len(report.families) == 7` → `assert len(report.families) == len(EXPECTED_FAMILY_NAMES)` (import the frozenset). Run → PASS now (still 7).

- [ ] **Step 4: Failing test — /api/templates carries tier.** In `tests/test_webapp.py`, extend the templates-endpoint test:
```python
assert all("tier" in fam for fam in body["families"])
assert {fam["tier"] for fam in body["families"]} <= {"benchmarked", "baseline"}
```
Run → FAIL (key absent).

- [ ] **Step 5: Add tier to the payload.** In `webapp.py` the `/api/templates` dict (after `"param_count"`): `"tier": f.tier,`. Run Step 4 → PASS.

- [ ] **Step 6: Failing vitest — LibraryModal renders a tier badge.** In `LibraryModal.test.tsx`, with a fixture family `{ ..., tier: 'baseline' }`, assert a "Verify before real use" affordance renders; a `benchmarked` family does not. Update `TemplateFamilyInfo` fixtures to include `tier`. Run vitest → FAIL.

- [ ] **Step 7: Render the badge.** In `api.ts` add `tier: 'benchmarked' | 'baseline'` to `TemplateFamilyInfo`. In `LibraryModal.tsx` card (`kc-library-card-meta` area), render for `f.tier === 'baseline'` a `<span className="kc-library-tier kc-library-tier-baseline" title="Real, verified geometry — but check dimensions, fit & load before real use">Verify before use</span>`; benchmarked renders no badge (the default, uncluttered). Include `f.tier` in the `filtered` search predicate so "baseline"/"verify" matches. Add `.kc-library-tier*` CSS (AA contrast both themes — reuse the risk-tone token palette). Run Step 6 → PASS.

- [ ] **Step 8: Docs + CHANGELOG.** Add a "Template tiers" note to `docs/cadquery-backend.md` or a new `docs/templates.md`; CHANGELOG `Added` entry for the tier surfacing.

- [ ] **Step 9: Full gate + commit.** `bash scripts/ci.sh` green → `git commit -m "#19 slice 1: template honesty tier (benchmarked/baseline) surfaced in the library"`.

---

## Slices 2–7 — family batches

Each slice applies the **RECIPE** to its table rows, then: audit-lite → `bash scripts/ci.sh` green → commit `#19 slice N: <batch> (<families>)` → push (fetch-rebase first). Batch families that share a `.scad` file and a twin helper to amortize authoring. After each push, update `EXPECTED_FAMILY_NAMES` is already done in R4. Keep `docs/supported-*`/CHANGELOG current per slice.

- **Slice 2** — pegboard_hook, spool_holder, l_bracket (geometry exists; confirm `l_bracket`'s `use <fasteners.scad>` sibling include resolves at render cwd — the one open risk).
- **Slice 3** — washer, dowel_pin, bumper_foot, mounting_flange (one `rings.scad`, one shared annulus twin helper).
- **Slice 4** — plate_with_hole, faceplate, vesa_plate(baseline).
- **Slice 5** — corner_gusset, pcb_standoff, french_cleat(baseline), heatset_pocket(baseline).
- **Slice 6** — snap_fit_box, lidded_box, clamp_block, cable_raceway, handle_grip, stand_dock.
- **Slice 7** — funnel, gridfinity_bin(baseline), gridfinity_baseplate(baseline), threaded_nut(baseline), threaded_bolt(baseline). Nut/bolt carry the explicit "thread RELIEF only, not certified threads" caveat in summary + docs.

## Slice 8 — Epic close

- [ ] `/walkthrough` the library browser with the full catalog (both themes; pick a benchmarked and a baseline family; verify the badge, the seed routing, a real design→gate→slice for ≥3 new families).
- [ ] `/audit-team` scoped to the #19 diff → remediate to **0/0/0/0/0**.
- [ ] Update `docs/supported-printers.md` sibling doc / a `docs/templates.md` catalog with the full tiered list + counts; CHANGELOG epic summary.
- [ ] Close #19 with evidence (catalog count, tier breakdown, gate-green, audit clean).

## Definition of done

Catalog ≥ 30 families, each: real `.scad` geometry + analytic bbox proven against a real render + STEP twin proven watertight at bbox + deterministic re-render < 5 s + a visible tier. No family ships unverified; no `==N` magic tripwire (replaced by `EXPECTED_FAMILY_NAMES`); the 238 label-only families are deliberately NOT ported (documented). Epic audited to 0/0/0/0/0. Gate green every slice.

## Self-review notes

- **Spec coverage:** issue #19 asks "meaningfully broader, every new family tier-labeled in UI + docs, gate still validates each." Covered: 7→32 (D1), tier field + badge + docs (slice 1, D4), gate is tier-blind and auto-validates every family (finding 4 + R6).
- **Alias collisions:** all net-new aliases checked against the 36 existing normalized aliases; tube owns ring/spacer/standoff/sleeve/bushing and box owns tray/bin/container/open-* — new families avoid them (e.g. washer ≠ "ring", funnel ≠ "spout"-only check, gusset ≠ "bracket" conflict with l_bracket — l_bracket owns "bracket"; gusset uses "corner gusset/corner brace/triangle brace").
- **Type consistency:** `tier` is `Literal["benchmarked","baseline"]` in Python and `'benchmarked' | 'baseline'` in TS; `EXPECTED_FAMILY_NAMES` is the single source for the count in both test files.
- **Open risk to resolve in slice 2:** `bracket.scad`'s sibling `use <fasteners.scad>;` include path resolution (flagged by the map); verify the rendered emit resolves it before relying on l_bracket.
