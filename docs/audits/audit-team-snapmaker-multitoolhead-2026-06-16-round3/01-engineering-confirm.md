# Engineering Confirmation — Round 3 (Principal Engineer)

**Scope:** Single residual ENG-101 (Minor) carried from round 2. Focused confirmation audit.
**Date:** 2026-06-16
**Verdict: ENG-101 RESOLVED. ENG roll-up: 0/0/0/0/0.**

---

## ENG-101 — RESOLVED

The previous ENG-004 fix dropped a null-temperature head from `toolhead_temps`, which
shifted array indices so a disconnected *middle* head mislabeled every head after it (the
SendPanel labels chips `T{i+1}` by array position). The round-3 fix makes the tuple
**index-stable**: a present-but-non-reporting head keeps its slot as `None`; only a fully
absent extruder object (a fewer-head machine) is dropped.

### 1. `snapmaker_connector.py` `status()` — CONFIRMED

`src/kimcad/snapmaker_connector.py` lines 118–134:

```python
temps: list[float | None] = []
for obj in _EXTRUDER_OBJECTS:
    block = status.get(obj)
    if block is None:
        continue  # extruder object absent → this machine simply has fewer heads
    t = block.get("temperature")
    temps.append(float(t) if t is not None else None)
...
nozzle_temp_c=temps[0] if temps else None,
toolhead_temps=tuple(temps) if temps else None,
```

- `continue` fires **only** when the extruder object is absent (`block is None`) — i.e. a
  fewer-head machine drops the slot.
- A present head with `temperature: null` now **appends `None`**, preserving its T-index.
- `nozzle_temp_c = temps[0]` (T0) — unchanged, correct.

### 2. `printer_connector.py` `PrinterStatus.toolhead_temps` type — CONFIRMED

`src/kimcad/printer_connector.py` line 154:

```python
toolhead_temps: tuple[float | None, ...] | None = None
```

Type widened to admit `None` elements. ENG-101 rationale documented at lines 152–153.

### 3. Test `test_status_preserves_index_for_null_temp_head` — CONFIRMED + HAS TEETH

`tests/test_snapmaker_connector.py` lines 133–172. A local stub server returns
`extruder1.temperature = None` with the other three reporting. The test asserts:

```python
assert st.toolhead_temps == (210.0, None, 200.0, 195.0)
assert st.nozzle_temp_c == pytest.approx(210.0)  # T0
```

**Teeth proven** — I reproduced the old skip-null behavior against the same payload: it
yields `(210.0, 200.0, 195.0)` (length 3), which `!= (210.0, None, 200.0, 195.0)` → the
assert FAILS. So a regression to skip-null is caught.

### 4. REGRESSION HUNT — JSON serialization through the API — CONFIRMED VALID

The critical new question: does a `None` element survive `/api/connector-status`
serialization as valid JSON (not NaN)?

`src/kimcad/webapp.py` `_handle_connector_status`, lines 1822–1823:

```python
if st.toolhead_temps:
    resp["toolhead_temps"] = list(st.toolhead_temps)
```

Then `self._json(...)` runs `json.dumps`. I executed the **exact** path with a
`PrinterStatus(online=True, state=PrinterState.printing, toolhead_temps=(210.0, None, 200.0, 195.0))`:

```
truthiness guard (if st.toolhead_temps): True
json.dumps output: [210.0, null, 200.0, 195.0]
valid-json roundtrip: [210.0, None, 200.0, 195.0]
contains NaN: False
full resp json: {"name": "mock", "toolhead_temps": [210.0, null, 200.0, 195.0]}
```

`None → null` (valid JSON), **never NaN**. Python's `json.dumps` emits literal `null` for
`None`, so the response is well-formed and any strict JSON client parses it. No regression.

### 5. Truthiness guard + sibling status tests — CONFIRMED

- `if st.toolhead_temps:` fires `True` for a non-empty tuple even when it contains `None`
  elements (a non-empty tuple is always truthy) — proven above. The guard correctly
  includes the toolhead_temps key when heads exist and omits it only when the tuple is
  `None`/empty.
- Full suite:

```
$ .venv/Scripts/python.exe -m pytest tests/test_snapmaker_connector.py -q
.................                                                         [100%]
17 passed in 10.80s
```

All sibling cases hold: 4-head all-report (`test_status_returns_toolhead_temps_tuple`),
idle-cold (`test_status_idle_temps_are_cold`), partial 2-head
(`test_status_partial_toolhead_temps`), and nozzle=T0 (`test_status_nozzle_temp_c_is_t0`).

---

## New findings

None. The fix is correct, complete, index-stable, JSON-safe end-to-end, and regression-guarded.

## ENG roll-up

**ENG: 0/0/0/0/0** (Blocker 0 / Major 0 / Minor 0 / Nit 0 / Info 0).
