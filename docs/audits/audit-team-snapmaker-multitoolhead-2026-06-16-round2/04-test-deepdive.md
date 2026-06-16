# Test Suite Deep-Dive (ROUND 2 — post-remediation) — KimCad Snapmaker U1 / Multi-Toolhead

**Audit date:** 2026-06-16 (round 2)
**Role:** Test Engineer
**Scope re-audited:** the round-1 TEST findings (TEST-001..008) and the new tests added to close them.
**Auditor posture:** Balanced, adversarial on test *quality* (does each new test FAIL if the code regresses?).
**Verification:** ran the affected suites — backend `71 passed` (test_slicer.py + test_snapmaker_connector.py + the 5 new webapp multi-head tests); frontend `90 passed` (ExportPanel.test.tsx + api.test.ts + SendPanel.test.tsx). Tests are green AND meaningful, not vacuous.

---

## TL;DR

Every round-1 TEST finding is **RESOLVED with a real, regression-proving test** — not a hollow green. The remediation closed the multi-head blind spots in all three layers (slicer, webapp HTTP, frontend) and added the previously-absent frontend test suite. The standout improvements: the mock Moonraker now takes `extruder_count`, so 1/2/4-head presence is genuinely driven (no longer "always 4"); the null-temp head case is exercised with a bespoke handler and an **exact-tuple** assertion `(210.0, 200.0, 195.0)`; the webapp cache miss/hit test proves the slice ran exactly twice for three POSTs (two distinct tuples + one repeat); and `api.ts`'s single-entry-slot collapse is pinned with `toEqual({printer, material})`. No vacuous assertions found among the new tests. The round-1 weak `>= 1` assertion (TEST-008) was replaced by exact `== 1` / `== 2` / `== 4` toolhead-count tests.

## Severity roll-up (tests, round 2)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

**TEST: 0/0/0/0/0**

---

## Per-finding resolution table

| ID | R1 sev | Status | Proving test(s) | Adversarial verdict |
|---|---|---|---|---|
| TEST-001 | Critical | **RESOLVED** | `test_resolve_filament_slots_happy_path`, `test_resolve_filament_slots_missing_profile_key_raises` (test_slicer.py:314–338) | Happy path asserts **ordered** per-slot resolution: `paths[0]/[1]/[2]` map to specific profile stems and `len==3`, so a wrong-order or wrong-key bug fails. Error path matches the exact `"not available on printer"` message — a swallowed/renamed error fails. Not vacuous. |
| TEST-002 | Critical | **RESOLVED** | `test_slice_uses_filament_config_for_multi_toolhead` (test_slicer.py:89) | Asserts `cmd.count("--filament-config") == 4` (precise flag count, not "in cmd"), `"--load-filaments" not in cmd`, and each slot path present. A dropped/duplicated flag or a fallen-through `else` fails. The 1-element regression (`test_slice_uses_filament_config_for_single_element_filaments`) pins ENG-002: count `== 1`, no `--load-filaments`. |
| TEST-003 | Major | **RESOLVED** | 4 webapp tests (test_webapp.py:1532–1609) | Explicit-slots forwards `("pla","petg","pla","abs")`; no-slots fills the full 4-tuple `("pla","pla","pla","pla")` (proves it does NOT collapse to single-head); cache test asserts `len(calls)==2` for 3 POSTs (true miss/hit, keyed on the tuple — confirmed against webapp.py:2492 `key=(rid,printer_key,tuple)`); single-head asserts `filament_slots is None`. All four catch a distinct regression. |
| TEST-004 | Major | **RESOLVED** | mock_moonraker `extruder_count` param + `test_capabilities_toolhead_count_2`, `test_status_partial_toolhead_temps` | The mock no longer always returns 4 — `_status_for` slices `_EXTRUDER_OBJECTS[:extruder_count]` (mock_moonraker.py:75). 2-head capabilities asserts `== 2`; partial temps assert `len == 2`. Drives the real `max(1, sum(...))` count logic and the per-head temp loop. Mock-lies risk closed. |
| TEST-005 | Major | **RESOLVED** | `test_web_options_carries_toolhead_count` (test_webapp.py:552) | Asserts `bambu_p2s == 1` AND `snapmaker_u1 == 4` from the real `web_options(Config.load())` — exercises the runtime API path, not a source constant. Wrong/missing field fails. |
| TEST-006 | Minor | **RESOLVED** | ExportPanel.test.tsx multi-head block (281–386), api.test.ts (446–477), SendPanel.test.tsx (288–314) | Frontend suite now exists. ExportPanel test renders N "Extruder n" pickers for `toolhead_count>1`, then switches BACK to single-head and asserts the `materialSlots` reset useEffect collapses to one "Material" select; also asserts `aria-labelledby` wiring and the per-extruder post-slice summary. api.test.ts pins the POST body (`filament_slot_0..2`, no stray `_3`) AND the single-entry collapse `toEqual({printer,material})`. Real UI-path coverage. |
| TEST-007 | Minor | **RESOLVED (positive)** | Import sentinel intact; `prove_gcode` G10/G28/G92 boundary tests (test_slicer.py:522–536) | Round-1 noted this as a positive (no action). The import sentinel still stands (collection-time ERROR on a missing module). Bonus: the motion-regex boundary is now explicitly tested both negative (G10/G28/G92 ≠ motion) and positive (arc-only G2/G3 passes). |
| TEST-008 | Nit | **RESOLVED** | `test_capabilities_toolhead_count_at_least_1` rewritten to `== 1` via `extruder_count=1`; plus `==2`/`==4` | The weak `>= 1` is gone — now an exact `== 1` under a genuine single-head mock. A broken `capabilities()` returning 999 (or always-4) now fails. Combined with the TEST-004 mock fix as recommended. |

---

## Adversarial quality probes (did I try to break them?)

- **Cache miss/hit (the one most likely to pass vacuously):** the test issues POST `a`, POST `b` (different tuple), POST `a` again, and asserts `len(calls) == 2`. If the cache key wrongly ignored the slot tuple, the second POST would hit the cache and `len == 1`; if it ignored caching entirely, `len == 3`. The exact `== 2` pins both directions. Confirmed the cache key in source is the tuple (webapp.py:2492), so the green is earned. **Not vacuous.**
- **`--filament-config` flag count:** asserted with `.count(...) == 4`, not membership. A duplicated or missing flag fails. **Precise.**
- **null-temp tuple:** `test_status_omits_head_reporting_null_temperature` stands up a custom handler emitting `extruder1: null` and asserts the EXACT result `(210.0, 200.0, 195.0)` plus `None not in temps` plus `nozzle_temp_c == 210.0` (first REAL temp). Proves no-crash AND the correct compacted tuple AND the right primary. **Strong.**
- **single-entry slot collapse (frontend):** api.test.ts asserts `oneSlot toEqual({printer:'p2s', material:'pla'})` and `filament_slot_0` undefined — matches `api.ts`'s `materialSlots.length > 1` guard. A regression to `>= 1` would emit `filament_slot_0` and fail. **Pinned.**
- **reset useEffect (frontend):** the ExportPanel test switches dual→single and `waitFor`s `Extruder 1` to disappear and `Material` to reappear — exercises the reset effect, not just the initial render. **Real.**

No `.skip` / `.only` / `xfail` / empty-body / placeholder assertions were introduced. Shortcut census: clean (0).

---

## Remaining gaps (NEW findings)

None at any severity. The multi-head feature's untested paths from round 1 — `resolve_filament_slots` (both branches), the `--filament-config` CLI branch (incl. 1-element), the webapp `filament_slot_*` POST body (explicit / defaulted / single-head / cache), `toolhead_count` in `/api/options`, partial/null toolhead presence in the mock, and the entire frontend slot UI + POST body — are all now covered by tests that fail on regression.

Minor observations (NOT findings — no action required):
- The webapp multi-head tests monkeypatch `slice_registered_mesh`, so the wiring from HTTP → kwargs is proven but the slicer subprocess itself is (correctly) covered separately in test_slicer.py and the `@pytest.mark.live` end-to-end. This is the right seam, not over-mocking — the integration point (`resolve_filament_slots` → `--filament-config`) is exercised in test_slicer.py against the real command builder.
- No single test spans browser→HTTP→slicer for multi-head (true E2E), but that mirrors the pre-existing single-head posture and the live slice is gated on a real binary; not a regression introduced by this feature.

---

## OPEN-only roll-up

**Nothing open. TEST: 0/0/0/0/0.**

All eight round-1 TEST findings are RESOLVED with regression-proving tests; the remediation also closed the systemic frontend-test gap for this feature. Verified green (71 backend + 90 frontend in the affected files) and verified meaningful by adversarial inspection of the assertions.
