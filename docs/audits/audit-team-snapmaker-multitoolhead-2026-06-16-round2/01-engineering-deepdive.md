# Engineering Deep-Dive (Round 2 — Remediation Validation) — KimCad Snapmaker U1 + Multi-Toolhead

**Audit date:** 2026-06-16 (round 2)
**Role:** Principal Engineer
**Posture:** Balanced — validating the remediation of round-1 ENG-001…ENG-008, then independently hunting for regressions introduced by the fixes.
**Scope re-read in full:** `src/kimcad/{webapp.py,slicer.py,snapmaker_connector.py,printer_connector.py,config.py,mock_moonraker.py}`, plus the new/updated tests in `tests/test_webapp.py`, `tests/test_snapmaker_connector.py`, `tests/test_slicer.py`, and `frontend/src/components/SendPanel.tsx`.

---

## TL;DR

All eight round-1 engineering findings are genuinely resolved, each with a code change that matches the intended fix and — for the substantive ones (ENG-001, ENG-002, ENG-004, ENG-007, ENG-008) — a dedicated regression test that asserts the corrected behavior. The import-cycle concern in ENG-007 was handled correctly (the constant lives in `config.py`, the cycle root, and is imported into `printer_connector.py`); `import kimcad.webapp` succeeds cleanly. The `extruder_count` mock parameter is backward-compatible (defaults to 4, preserving every existing test). The unconditional multi-head `filament_slots` tuple did **not** disturb the single-head path (it stays `None`, verified by test).

One **new Minor** finding (ENG-101): the implemented ENG-004 fix *omits* a null-temperature head from `toolhead_temps` rather than padding it, which shifts the array indices. The frontend `SendPanel` labels chips by array index (`T{i+1}`), so a missing **middle** head causes the remaining heads to render under the wrong "T" label. Narrow exposure, no crash, no data loss — but it is a real provenance mismatch between the chip label and the physical toolhead.

No Blockers, no Criticals, no Majors remain open.

## Round-1 → Round-2 resolution status

| ID | Sev (r1) | Status | Evidence of fix |
|---|---|---|---|
| ENG-001 | Critical | **RESOLVED** | `webapp.py:2479-2489` — for `toolhead_count > 1`, `filament_slots = slots` is set **unconditionally** (the `any(slots)` short-circuit is gone); each slot falls back to `material_key`, so the tuple is always length-N. Cache key `webapp.py:2492` therefore stays a tuple for multi-head and can no longer collapse to the single-head string form. Regression test `test_slice_multihead_with_no_slots_fills_full_tuple` (`tests/test_webapp.py:1552-1565`) asserts a no-slots multi-head POST yields `("pla","pla","pla","pla")`. |
| ENG-002 | Major | **RESOLVED** | `slicer.py:220` is now `if settings.filaments:` (was `len(...) > 1`); `webapp.py:660` is `if filament_slots:`. A length-1 tuple now correctly drives `--filament-config`. |
| ENG-003 | Major | **RESOLVED (documented decision)** | `webapp.py:2475-2477` comment + `slice_registered_mesh` docstring `webapp.py:633-638` explicitly state config `toolhead_count` is authoritative and a live connector is deliberately NOT queried (slicing must work with the printer off). This is the round-1 "Option 1, defensible for beta" path, now made explicit. |
| ENG-004 | Minor | **RESOLVED (alternate approach) — see ENG-101** | `snapmaker_connector.py:114-120,127` keeps the `if t is not None` guard and documents the contract (`:39-43`, `:88-92`): null heads are *omitted*, tuple may be shorter than `toolhead_count`, no null/NaN enters the tuple. Test `test_status_omits_head_reporting_null_temperature` (`tests/test_snapmaker_connector.py:133-170`). The crash risk (`float(None)`) is closed. The chosen direction (omit, not pad) introduces a new index-labeling mismatch — logged separately as ENG-101. |
| ENG-005 | Minor | **RESOLVED** | `webapp.py:2506-2510` — `_slot_kw` retained with a comment explaining that, post-ENG-001, `filament_slots` is either `None` or a full length-N tuple (never `()`), so the `is None` discriminator is exact and 4-arg test stubs stay unbroken. The implicit `None`-vs-`()` contract is now explicit. |
| ENG-006 | Minor | **RESOLVED (documented coupling)** | `snapmaker_connector.py:39-43` class docstring documents the coupling between `capabilities().toolhead_count` (counts query-present objects) and `status().toolhead_temps` (omits null-temp heads), exactly the action item from round 1. |
| ENG-007 | Nit | **RESOLVED** | `config.py:32-36` defines `DEFAULT_TOOLHEAD_COUNT = 1` once, with a comment explaining it is placed in `config.py` (the cycle root) to avoid `config → printer_connector → slicer → config`. Used at `config.py:58` (`Printer`) and `config.py:298`; imported into `printer_connector.py:37` and used at `:140` (`PrinterCapabilities`). `import kimcad.webapp` verified clean (see below). |
| ENG-008 | Nit | **RESOLVED** | `mock_moonraker.py:19-21` imports `_EXTRUDER_OBJECTS` from `kimcad.snapmaker_connector` and iterates it at `:75`; the literals are gone. Comment confirms no cycle (the connector does not import the mock). |

**Verification commands run:**

```
.venv\Scripts\python.exe -c "import kimcad.webapp; from kimcad.config import DEFAULT_TOOLHEAD_COUNT; print(DEFAULT_TOOLHEAD_COUNT)"
  -> import OK; DEFAULT_TOOLHEAD_COUNT= 1          # ENG-007 cycle-free confirmed

.venv\Scripts\python.exe -m pytest tests/test_snapmaker_connector.py tests/test_moonraker_connector.py -q
  -> 47 passed

.venv\Scripts\python.exe -m pytest tests/test_slicer.py -q
  -> 49 passed

.venv\Scripts\python.exe -m pytest tests/test_webapp.py -q -k "slice or toolhead or multihead"
  -> 23 passed
```

Import-cycle reasoning independently confirmed: `printer_connector.py:37` imports `DEFAULT_TOOLHEAD_COUNT` from `config`; `printer_connector.py:38` imports from `slicer`; `slicer.py:37` imports `Material, Printer` from `config`. Had the constant lived in `printer_connector`, `config` importing it back would close the loop. Anchoring it in `config` (which imports neither) is the correct placement.

---

## NEW findings (introduced or surfaced by the round-1 fixes)

### ENG-101 — Minor — Data provenance — Omitting a null-temp head shifts `toolhead_temps` indices, so SendPanel mislabels the remaining heads

**Category:** Data provenance / Correctness (UI)

**Evidence**

The ENG-004 fix in `snapmaker_connector.py:114-120` builds the tuple by *appending only present temps*:

```python
temps: list[float] = []
for obj in _EXTRUDER_OBJECTS:
    block = status.get(obj)
    if block is not None:
        t = block.get("temperature")
        if t is not None:
            temps.append(float(t))
...
toolhead_temps=tuple(temps) if temps else None,
```

When a **middle** head reports `temperature: null`, it is dropped and the later heads slide forward in the tuple. The existing test makes this explicit (`tests/test_snapmaker_connector.py:167-168`): with T1 null, `toolhead_temps == (210.0, 200.0, 195.0)` — i.e. T2's 200 °C now sits at array index 1 and T3's 195 °C at index 2.

The frontend renders chips by **array index**, not by physical head id (`frontend/src/components/SendPanel.tsx:262-266` and `:329-334`):

```jsx
{preStatus.toolhead_temps.map((t, i) => (
  <span key={i} className="kc-temp-chip">
    T{i + 1}: {t != null ? t.toFixed(0) : '—'}°C
  </span>
))}
```

So with T1 disconnected, the user sees three chips — `T1: 210`, `T2: 200`, `T3: 195` — where the second and third chips are actually the physical T2 and T3. The label "T2: 200" is wrong (physical T2 is 200, but it is being shown because the array collapsed, and physical T1 — which exists in config — has silently vanished from the display rather than showing as unavailable).

**Why this matters**

A Snapmaker U1 user with one disconnected/cold middle toolhead is shown temperatures attributed to the wrong heads, and the disconnected head disappears from the panel entirely (no "T-: —°C" placeholder). For a temperature read this is informational, not actuating, so the impact is bounded: no wrong G-code, no send decision keys off this. But it is a genuine provenance defect — the value a user sees is attributed to the wrong source.

Notably, the round-1 ENG-004 fix path recommended the **opposite** approach: "Use `temps.append(float(t) if t is not None else 0.0)` (or `math.nan`) so the tuple length always matches the number of extruder objects returned." The implemented fix chose omission instead and documented it as intentional. The frontend already guards each element for null (`t != null ? ... : '—'`, `SendPanel.tsx:264,331`) and the test fixture `SendPanel.test.tsx:295` feeds `[205, null]` — so the UI was *already built to render a per-slot null placeholder*. A null-preserving (index-stable) backend tuple would render correctly with no frontend change and would fix this finding.

**Blast radius**
- Adjacent code: both chip-rendering blocks in `SendPanel.tsx` (`:262`, `:329`); `webapp.py:1822-1823` (`/api/connector-status` serializes `list(st.toolhead_temps)` verbatim — it forwards whatever shape the connector emits).
- Shared state: the `PrinterStatus.toolhead_temps` contract (`printer_connector.py:152`) and its documented coupling to `capabilities().toolhead_count` (`snapmaker_connector.py:39-43`). A null-preserving change would make the tuple length equal `toolhead_count`, *strengthening* that coupling rather than weakening it.
- User-facing: Snapmaker U1 pre-send and live status chips when a non-last head is null. Last-head-null is unaffected (drop ≡ truncate at the tail).
- Migration: none (in-flight status only; nothing persisted).
- Tests to update: `test_status_omits_head_reporting_null_temperature` (`tests/test_snapmaker_connector.py:133`) asserts the *omit* behavior — it would flip to assert `(210.0, None, 200.0, 195.0)`. `SendPanel.test.tsx:295` already exercises the null-placeholder path, so the frontend needs no test change.
- Related findings: ENG-004 (root), ENG-006 (the count/temps coupling this would tighten).

**Fix path**

Preferred: make the tuple index-stable by emitting one slot per queried extruder object that is present in the response, using `None` for a present-but-null temperature:

```python
temps: list[float | None] = []
for obj in _EXTRUDER_OBJECTS:
    block = status.get(obj)
    if block is not None:                       # head exists on this printer
        t = block.get("temperature")
        temps.append(float(t) if t is not None else None)
# nozzle_temp_c = first NON-None temp
first_real = next((t for t in temps if t is not None), None)
```

Widen `PrinterStatus.toolhead_temps` to `tuple[float | None, ...] | None` (`printer_connector.py:152`) and `api.ts:173` to `(number | null)[] | null`. This keeps `len(toolhead_temps) == capabilities().toolhead_count`, aligns the chip index with the physical head, and the SendPanel renders the gap as `T2: —°C` using machinery it already has. If index-stability is explicitly *not* wanted, then the current behavior should at least be surfaced by tagging each emitted temp with its head id rather than relying on positional rendering — but the null-preserving option is simpler and lower-risk.

This is correctly Minor, not higher: it is read-only telemetry, only triggers on a disconnected non-last head, and there is no safety or data-integrity consequence.

---

## Independent regression sweep — things checked and cleared

These were probed specifically because the fixes touched them; each is **clear**:

- **Single-head path unchanged (ENG-001 fix).** For `toolhead_count == 1`, `webapp.py:2479` is false, `filament_slots` stays `None`, the cache key (`:2492`) is the string `material_key`, and `_slot_kw` is `{}` so `slice_registered_mesh` is called with the legacy 4-arg signature. Confirmed by `test_slice_single_head_ignores_filament_slots` (`tests/test_webapp.py:1593-1609`, asserts `filament_slots is None`).
- **`extruder_count` mock param is backward-compatible (ENG-004/006/008 support).** `mock_moonraker._initial_state` and `serve_mock_moonraker` default `extruder_count=4` (`mock_moonraker.py:191,215`), so every pre-existing call site keeps all four heads. `_status_for` slices `_EXTRUDER_OBJECTS[: state["extruder_count"]]` (`:75`), faithfully modeling a real Moonraker that simply omits objects it doesn't have. 47 connector tests pass.
- **DEFAULT_TOOLHEAD_COUNT import is truly cycle-free (ENG-007).** `import kimcad.webapp` (which transitively pulls config, printer_connector, slicer, snapmaker_connector, mock paths) imports cleanly; value resolves to 1. Reasoning cross-checked against the actual import edges above.
- **mock importing snapmaker_connector creates no cycle (ENG-008).** `snapmaker_connector.py` imports only `moonraker_connector` and `printer_connector`; it never imports `mock_moonraker`. `import kimcad.mock_moonraker` succeeds.
- **New cache-key edge: multi-head with `material=None`.** If a multi-head POST omits both `material` and all slots, each slot becomes `str(None or "")` → `""`, giving the tuple `("","","","")` (truthy → stays a tuple, key does not collapse). Downstream `resolve_filament_slots` raises `OrcaProfileError` on the empty key (`slicer.py:425-429`), which `slice_registered_mesh` catches and returns as `{"sliced": False, "reason": "no_profile"}` (`webapp.py:683-686`) — a clean, typed soft-failure, not a 500 or a wrong slice. No new defect.
- **`--filament-config` length-1 path (ENG-002 fix).** A length-1 `filaments` tuple now takes the `--filament-config` branch (`slicer.py:220-222`). Covered indirectly by `test_resolve_filament_slots_happy_path` and the multi-head webapp wiring tests.
- **bed_temp null-safety unaffected.** `snapmaker_connector.py:126` reads `(status.get("heater_bed") or {}).get("temperature")` — already None-safe; the ENG-004 change did not touch it.

## What's working (round 2)

- **Fixes are test-backed, not just code-changed.** ENG-001, ENG-002, ENG-004, and the cache-distinctness behavior each gained a named regression test that asserts the *corrected* outcome (e.g. `tests/test_webapp.py:1552,1568,1593`; `tests/test_snapmaker_connector.py:133`). This is the right way to remediate — the bug can't silently regress.
- **The hardest fix (ENG-007 cycle) was reasoned, not guessed.** The placement comment at `config.py:32-36` names the exact cycle it avoids; the choice is correct and verified by a clean import.
- **ENG-003 was resolved by an honest documented decision rather than over-engineering.** Querying the live connector on every slice would add a round-trip and break offline slicing; the code now states the config-authoritative contract plainly in two places. Defensible for the beta.
- **The remediation did not expand scope or introduce new dependencies.** Still stdlib-only; no new packages.

## What couldn't be assessed

- Real Snapmaker U1 firmware behavior for a physically disconnected middle toolhead (does Moonraker return `extruder1: {"temperature": null}`, or omit the object entirely?). ENG-101's user-visible impact depends on the *present-but-null* case; if real firmware instead *omits* the object, the same index shift still occurs (the object is absent → not appended), so the finding stands either way, but the exact trigger condition is unverified against hardware.
- OrcaSlicer `--filament-config` acceptance of a single-path invocation on the real U1 profile tree (no binary/profiles in this audit; verified only at command-construction level).
- Frontend was read but not executed in a browser; the index-labeling claim is from reading `SendPanel.tsx` render code + its test fixtures, which is sufficient to establish the mismatch.

---

## Final severity roll-up — STILL-OPEN findings only

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 1 |
| Nit | 0 |

**Open:** ENG-101 (Minor) — null-temp head omission shifts `toolhead_temps` indices, mislabeling SendPanel chips for a disconnected middle head.

**Round-1 findings resolved:** 8 / 8. **Still open from round 1:** 0.
