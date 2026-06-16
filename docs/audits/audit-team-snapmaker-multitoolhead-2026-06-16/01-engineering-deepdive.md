# Engineering Deep-Dive — KimCad Snapmaker U1 + Multi-Toolhead Feature

**Audit date:** 2026-06-16
**Role:** Principal Engineer
**Scope audited:** commits cc80fed + 3553665; SnapmakerConnector, multi-toolhead slicer path, pause/resume/cancel on MoonrakerConnector, webapp multi-head cache + filament POST extraction, ExportPanel/SendPanel UI stubs (via the feature description), 14+7 new tests
**Auditor posture:** Balanced

---

## TL;DR

The inheritance approach is sound: `SnapmakerConnector` overrides only `capabilities` and `status`, and the inherited `send`/`job_status`/`pause`/`resume`/`cancel` methods are single-extruder-agnostic (they don't reference `extruder` by name), so the delegation is safe. The `pause`/`resume`/`cancel` error handling is consistent with the established `send`/`capabilities` pattern. The slice-cache key design has one correctness defect that can silently serve a stale slice. `resolve_filament_slots` is fail-fast (good), but a single-slot `filament_slots=("pla",)` with `toolhead_count=1` takes a surprising branch. The mock extruder implementation matches real Moonraker semantics closely enough for a conformance oracle. No Blockers; one Critical; two Majors.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **Inheritance safety** — `send`, `job_status`, `pause`, `resume`, `cancel` in `MoonrakerConnector` are all stateless over extruder identity (they use `/printer/objects/query?print_stats&virtual_sdcard` and the print-control REST endpoints, none of which are extruder-specific). Inheriting them unchanged is correct.
- **`_EXTRUDER_OBJECTS` query order is deterministic** — `("extruder", "extruder1", "extruder2", "extruder3")` is a module-level constant tuple; Python iterates it in definition order, so `toolhead_temps[0]` is always T0. That holds across CPython, PyPy, and any Python version this project targets.
- **`resolve_filament_slots` is fail-fast and clear** — an unconfigured material key raises `OrcaProfileError` immediately with the offending key named; it does not silently substitute a fallback profile that could mis-slice.
- **mock_moonraker extruder fidelity** — idle temps (25.0) and printing temps (210/205/200/195 for T0–T3) are differentiated by the `state["printing"]` flag, which is exactly how a real Moonraker reports extruder state. The separate `heater_bed` object is present and the `_status_for` function only populates objects the caller asked for, so query-object isolation is correct.
- **pause/resume/cancel error handling** — each method follows the exact pattern of `send`/`capabilities`: `HTTPError` → `AuthError` on 401/403, `ConnectorError` on other 4xx/5xx; `URLError/OSError` → `PrinterOffline`. No swallowed exceptions; no inconsistency.
- **Thread safety** — `MoonrakerConnector` holds only immutable per-instance state (`_base`, `_key`, `_timeout`) and the `_lock` in the mock is scoped to the handler factory (not a class-level global). The webapp `slice_lock` + `reg.lock` double-check pattern is correct.
- **Test breadth** — 14 Snapmaker tests + 7 Moonraker pause/resume/cancel tests cover all three states (print, pause, cancel), auth rejection, and offline. All state assertions go into the mock's shared dict, not just the connector's return value, so the tests validate server-side side effects.

## What couldn't be assessed

- OrcaSlicer `--filament-config` flag behavior against the actual Snapmaker U1 profile JSONs (no binary or profile tree available in this audit; conformance verified only at the command-construction level in `slice_model`).
- Frontend components `ExportPanel.tsx` / `SendPanel.tsx` were not supplied for review; the backend contract they depend on is assessed here.
- Real Snapmaker U1 Moonraker endpoint behavior (firmware version, whether `extruder1`/`extruder2`/`extruder3` are always present or require loaded filament).

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

---

### ENG-001 — Critical — Correctness — Cache key collision: single-material string key vs. tuple key not truly isolated

**Evidence**

`webapp.py`, line 2476:
```python
key = (rid, printer_key, filament_slots if filament_slots else material_key)
```

When `toolhead_count == 1` (all existing printers), `filament_slots` is `None` and `key[2]` is a plain string (e.g. `"pla"`). When `toolhead_count > 1` but *only one slot is filled* and `any(slots)` is true, `filament_slots` is a 1-tuple (e.g. `("pla",)`). These are different Python objects: `"pla" != ("pla",)` — so no accidental collision there. The real defect is the inverse: if `toolhead_count > 1` but **all** `filament_slot_N` fields come in as falsy (absent, empty string, `null`), the `any(slots)` guard at line 2472 is False, `filament_slots` stays `None`, and the key becomes `(rid, printer_key, material_key)` — the single-head form. A previously cached single-head slice for the same `(rid, printer_key, material_key)` will be served as the multi-head result, silently skipping the `--filament-config` path and producing a single-filament G-code for a 4-toolhead print job. The user gets no error; they get the wrong slice.

**Why this matters**

A Snapmaker U1 user who clears or omits filament slots on the confirmation dialog gets a cached single-material slice served as if they had run a 4-head job. The G-code will succeed (it's a valid slice) but will not actually use the additional toolheads. This is a silent correctness failure: wrong output with no diagnostic.

**Blast radius**
- Adjacent code: `slice_registered_mesh` in `webapp.py`, the `_slot_kw` construction at line 2490, and `reg.cache_slice_locked` — all participate in the same incorrect cache hit.
- Shared state: `reg.slice_cache` (the `OrderedDict` shared across threads via `reg.lock`).
- User-facing: Snapmaker U1 users only; produces a functionally incorrect print job that the printer will accept (it will print in single-material mode).
- Migration: none (in-process cache; clears on server restart).
- Tests to update: no existing test covers the empty-slots-on-multi-head-printer path; a new test should assert that omitting all `filament_slot_N` fields on a 4-head printer results in a 4-element `filament_slots` tuple or an explicit error, not a cache fallback.
- Related findings: none.

**Fix path**

Two options:
1. **Preferred:** When `toolhead_count > 1`, always build a tuple key even when all slots are empty, by removing the `any(slots)` short-circuit — `filament_slots = slots` unconditionally. `slice_registered_mesh` already handles the `filament_slots=("",...)` case by calling `resolve_filament_slots`, which will raise `OrcaProfileError` on an empty key, surfacing as a clean 500 (better: add an explicit empty-string guard in `resolve_filament_slots` or a `400` branch in `_handle_slice`).
2. **Alternative:** Include `toolhead_count` in the cache key as a fourth element to prevent shape-collision even if the slot logic changes.

---

### ENG-002 — Major — Correctness — `slice_model` multi-head branch fires for `len(filaments) > 1`, not `>= 1`; a single-slot multi-head job silently falls back to `--load-filaments`

**Evidence**

`slicer.py`, lines 218–222:
```python
if settings.filaments and len(settings.filaments) > 1:
    for fp in settings.filaments:
        cmd += ["--filament-config", str(fp)]
else:
    cmd += ["--load-filaments", str(settings.filament)]
```

`resolve_filament_slots` can return a 1-element list (`toolhead_count=1` is guarded upstream, but `toolhead_count=1` with `filament_slots` explicitly provided is not prevented). More likely: if a 4-toolhead job has all four slots pointing to the same material, `filament_paths` will have 4 entries (correct). The `>1` condition is true. No real defect in that path. The real defect: if `toolhead_count > 1` but `webapp.py` somehow sends a 1-element `filament_slots` tuple (e.g., if the `any(slots)` guard fires on a partially filled form), `settings.filaments` becomes a 1-tuple, `len(filaments) > 1` is `False`, and the command falls back to `--load-filaments settings.filament` — the *single-head* filament from `resolve_slice_settings` — potentially a mis-matched profile. This path is only reachable if ENG-001's `any(slots)` logic changes, but the `>1` guard is still a latent defect that will bite during any refactor.

**Why this matters**

A 1-slot `filaments` tuple is a coherent request (a single-tool print on a multi-tool printer) but the code silently switches to the unrelated `settings.filament` (the single-head resolved filament from `resolve_slice_settings`). These may differ if the printer has a different profile per toolhead.

**Blast radius**
- Adjacent code: `slice_registered_mesh` in `webapp.py` constructs `settings.filaments` from `filament_paths`; `slice_model` consumes it.
- User-facing: silent mis-slice on a 1-slot multi-head print; wrong filament profile used.
- Tests to update: `test_slice_model` or a new `test_slice_model_single_filament_slot`.
- Related findings: ENG-001 (shares the multi-head/single-head ambiguity root).

**Fix path**

Change the branch condition to `if settings.filaments and len(settings.filaments) >= 1:` (i.e., `if settings.filaments:`). A 1-element `--filament-config` list is valid OrcaSlicer CLI usage for a single-filament multi-head printer.

---

### ENG-003 — Major — Data provenance — `toolhead_count` from config is authoritative at slice time; connector-reported count is never reconciled

**Evidence**

`config.py` line 292: `toolhead_count=int(p.get("toolhead_count", 1))` — this is the static config value.
`snapmaker_connector.py` line 71: `toolhead_count = max(1, sum(1 for obj in _EXTRUDER_OBJECTS if obj in status))` — this is the live-detected count.

The webapp's `_handle_slice` reads `printer_cfg.toolhead_count` (line 2467) from the config — **not** from the connector. If a Snapmaker U1 has only 2 loaded toolheads at print time (the other 2 extruder objects absent from Moonraker), the slicer will still generate a 4-toolhead G-code and attempt to resolve 4 filament profiles. The connector's live `capabilities()` call already does the right detection, but that result is never threaded back into the slice decision.

**Why this matters**

A partially-loaded U1 (e.g., 2 toolheads mounted, 2 absent) will produce a slice for 4 toolheads that the printer cannot execute correctly. No error is raised; the printer accepts the G-code and exhibits undefined behavior on the absent heads.

**Blast radius**
- Adjacent code: `_printer_entry` in `webapp.py` exposes `toolhead_count` to the UI from config; the UI uses it to render N dropdowns. Both the UI and slicer are consistent with config, but both drift from live hardware.
- User-facing: incorrect multi-head G-code sent to a partially loaded printer.
- Migration: none (behavior change only).
- Tests to update: no test currently simulates a count mismatch between config and connector.
- Related findings: none.

**Fix path**

This is an architectural trade-off: calling `capabilities()` on every slice adds a round-trip. Acceptable paths:
1. Accept the limitation and document it: the config's `toolhead_count` is what is sliced for; users must ensure it matches hardware.
2. In `_handle_slice`, after building `filament_slots`, cap `len(filament_slots)` to the connector-reported `toolhead_count` (fetched lazily, with a timeout fallback to the config value).

Option 1 is defensible for a beta. Option 2 is the right long-term fix.

---

### ENG-004 — Minor — Correctness — `status()` returns `toolhead_temps=None` when idle (all extruders at 25 °C) due to empty-tuple guard

**Evidence**

`snapmaker_connector.py` lines 100–113:
```python
for obj in _EXTRUDER_OBJECTS:
    block = status.get(obj)
    if block is not None:
        t = block.get("temperature")
        if t is not None:
            temps.append(float(t))
...
toolhead_temps=tuple(temps) if temps else None,
```

When the printer is idle but all 4 extruders are at 25 °C, `temps` has 4 elements and `toolhead_temps` is correctly `(25.0, 25.0, 25.0, 25.0)`. But `test_status_idle_temps_are_cold` at line 111 asserts `st.toolhead_temps is not None`, which passes. This is actually correct — no defect. However, if the mock ever returns a `temperature: null` for an offline extruder object (e.g., `{"extruder3": {"temperature": null}}`), the `if t is not None` guard silently drops that extruder from the tuple. The tuple length then mismatches `toolhead_count` in config (4) without any diagnostic. A downstream consumer iterating `toolhead_temps[i]` by config index would raise `IndexError`.

**Why this matters**

Rare in practice (current mock never returns null temperature), but a real Snapmaker U1 with a disconnected toolhead may return null. The SendPanel's temperature chips are at risk.

**Fix path**

Use `temps.append(float(t) if t is not None else 0.0)` (or `math.nan`) so the tuple length always matches the number of extruder objects returned, and document the sentinel. Add a test for null temperature in a queried extruder.

---

### ENG-005 — Minor — Hygiene — `_slot_kw` backward-compat pattern is correct but fragile as a call-site convention

**Evidence**

`webapp.py`, lines 2490–2492:
```python
_slot_kw = {} if filament_slots is None else {"filament_slots": filament_slots}
info, gcode_path = slice_registered_mesh(
    get_config(), mesh_path, printer_key, material_key, **_slot_kw
)
```

This pattern is used to avoid passing `filament_slots=None` when the parameter is absent, relying on `slice_registered_mesh`'s default `filament_slots: tuple[str, ...] | None = None`. It works, but it is an unusual indirection that makes the call site harder to read. More importantly, if `filament_slots` is an empty tuple `()`, `_slot_kw` would be `{"filament_slots": ()}` and `slice_registered_mesh` receives `filament_slots=()`, which passes `bool(())` == `False` to the `if filament_slots and len(filament_slots) > 1` guard, falling through to single-head. This is consistent (an empty tuple means "no multi-head override"), but the `_slot_kw = {} if filament_slots is None else ...` check means an empty tuple is NOT `None` and DOES get passed, where the function then ignores it. The behavior is correct but the contract is implicit.

**Fix path**

Either: (a) pass `filament_slots` directly (always), let `slice_registered_mesh` handle `None` and `()` uniformly, and document the `()` == no-override contract. Or (b) keep `_slot_kw` but add a comment explaining the `None`-vs-`()` distinction.

---

### ENG-006 — Minor — Correctness — `SnapmakerConnector.capabilities()` counts extruder objects present in the _response_, not in the _query_

**Evidence**

`snapmaker_connector.py`, line 71:
```python
toolhead_count = max(1, sum(1 for obj in _EXTRUDER_OBJECTS if obj in status))
```

`status` is `result.get("status") or {}` from Moonraker's response. A real Moonraker only returns objects it knows about — if `extruder3` is not configured, it will not appear in the response even when queried. This is correct behavior. However, the counting expression relies on the fact that `_query` returns a subset of what was asked. The comment in the class docstring says "queries `toolhead configfile extruder extruder1 extruder2 extruder3`" which matches `_EXTRUDER_OBJECTS`. No defect, but note that if Moonraker ever returns an object with `extruder3: {}` (present but empty, no `temperature` key), it will count as a toolhead in `capabilities` but produce no entry in `status().toolhead_temps`. This is the same root as ENG-004.

**Fix path**

No immediate action; document the coupling between `capabilities().toolhead_count` and `status().toolhead_temps` length in the class docstring.

---

### ENG-007 — Nit — Hygiene — `toolhead_count` default is `1` in both `Printer` and `PrinterCapabilities` — good, but the two defaults could drift

**Evidence**

`config.py` line 52: `toolhead_count: int = 1` on `Printer`.
`printer_connector.py` line 139: `toolhead_count: int = 1` on `PrinterCapabilities`.

Two separate defaults for the same semantic concept. If one is changed, the other may not be.

**Fix path**

Define `_DEFAULT_TOOLHEAD_COUNT = 1` in a shared location (e.g., `printer_connector.py`) and reference it in both dataclasses. Low priority.

---

### ENG-008 — Nit — Hygiene — `_EXTRUDER_OBJECTS` defined in `snapmaker_connector.py`, not in `moonraker_connector.py`, but `mock_moonraker.py` hardcodes the same names

**Evidence**

`mock_moonraker.py` lines 67–73 hardcode `extruder`, `extruder1`, `extruder2`, `extruder3` by string literal. These match `_EXTRUDER_OBJECTS` in `snapmaker_connector.py` but are not imported from it. A rename of an object key would require updating both files.

**Fix path**

Import `_EXTRUDER_OBJECTS` from `snapmaker_connector` in `mock_moonraker.py`, or define the canonical names in a shared constant. Low priority given the names are Klipper/Moonraker protocol constants unlikely to change.

---

## Patterns and systemic observations

**Single root: multi-head vs. single-head branch disambiguation is implicit everywhere.** ENG-001, ENG-002, and ENG-003 all stem from the same pattern: `None` or `()` or `len == 1` as a proxy for "this is a single-head job." The code has three different check styles (`if filament_slots`, `len > 1`, `is None`) for the same concept. A single `is_multi_head(printer, filament_slots)` helper that centralizes the check would eliminate all three findings' root cause in one place.

**Mock fidelity is high.** The mock_moonraker implementation correctly models Moonraker's behavior for the objects used by this feature. The extruder temperature differentiation by `state["printing"]` is the correct semantic (idle extruders should report ambient, not setpoint). The pause/resume/cancel state machine is correct (pause → `paused=True, printing=False`; resume → `paused=False, printing=True`; cancel → `printing=False, paused=False`).

## Dependency snapshot

No new dependencies introduced. The feature uses only stdlib (`urllib`, `json`) already present.

| Dependency | Version | Concern |
|---|---|---|
| (no new dependencies) | — | — |

## Appendix: artifacts reviewed

- `src/kimcad/snapmaker_connector.py`
- `src/kimcad/moonraker_connector.py` (full, including new pause/resume/cancel)
- `src/kimcad/printer_connector.py` (full, including `PrinterCapabilities.toolhead_count`, `PrinterStatus.toolhead_temps`)
- `src/kimcad/connectors.py` (full, snapmaker branch in `build_connector`)
- `src/kimcad/config.py` (`Printer.toolhead_count`, `Config.printer()`)
- `src/kimcad/slicer.py` (`SliceSettings.filaments`, `resolve_filament_slots`, `slice_model` branch)
- `src/kimcad/webapp.py` (`_handle_slice`, `slice_registered_mesh`, `_handle_connector_status`, `_printer_entry`)
- `src/kimcad/mock_moonraker.py` (extruder1/2/3 additions, pause/resume/cancel)
- `config/default.yaml` (snapmaker_u1 entry)
- `tests/test_snapmaker_connector.py` (full)
- `tests/test_moonraker_connector.py` (pause/resume/cancel section)
