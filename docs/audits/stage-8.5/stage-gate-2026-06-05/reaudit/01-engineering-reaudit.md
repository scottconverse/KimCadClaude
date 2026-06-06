# Engineering Re-Audit (Closure) — KimCad Stage 8.5 Stage Gate

- Role: Principal Engineer (independent re-audit)
- Scope: repo `C:\Users\scott\dev\kimcad`, branch `stage-8.5-usability` @ `6c98674` (working tree clean)
- Date: 2026-06-05
- Original report under review: `docs/audits/stage-8.5/stage-gate-2026-06-05/01-engineering-deepdive.md` (7 findings: 0 Blocker / 0 Critical / 2 Major / 4 Minor / 1 Nit).

## Verification gates (re-run at HEAD)

- `ruff check src` — All checks passed.
- `pytest -m "not live" -q` — 761 passed, 0 failed, 4 deselected. Matches the expected 761.
- Frontend `vitest` — 257 passed / 22 files. Matches the expected 257.
- Targeted regression tests — 43 passed (`test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale`, `test_rerender_invalidates_a_cached_slice`, `test_regate_mesh_*`, full `test_model_advisor.py`).
- Geometry backends (`scipy`, `networkx`, `manifold3d`) all import here — the ENG-007 trap that produced 32 false failures in the original run does not recur.

## Per-finding verdicts

### ENG-001 — Major — slice/render same-`rid` race — RESOLVED

A per-design monotonic `geometry_version` stamp (`webapp.py:645`), evicted in lockstep via `_evict` (`webapp.py:735`).

- A slice captures the version under `lock` at slice start: `sliced_ver = geometry_version.get(rid, 0)` (`webapp.py:1673`).
- A re-render bumps the version AND clears the cache/G-code in the SAME `lock` critical section: `geometry_version[rid] = ... + 1` (`webapp.py:1783`), then `gcode_registry.pop(rid, None)` + `slice_cache` clear (`webapp.py:1786-1788`). Atomic — no window between bump and invalidation.
- `_respond_slice` registers the G-code only if the version still matches, else returns `sliced:false reason:"stale"` and registers nothing: the version guard returns early BEFORE `gcode_registry[rid] = gcode_path` (`webapp.py:1635-1646`).
- The cache write is guarded too: `slice_cache[key]` is only set when the version still matches (`webapp.py:1709-1713`).

Race closed. Interleave trace: slice reads `ver=0` (1673) → render bumps to `1` + clears under `lock` (1783-1788) → slice's `_respond_slice` sees `1 != 0` → drops as stale, registers nothing. The send path's gate re-check (`webapp.py:1235`) is an added backstop.

Normal path intact: sequential slice with no intervening render matches → registers + serves correctly (confirmed by `test_rerender_invalidates_a_cached_slice`, `calls["n"] == 2`).

Regression test meaningful: `test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale` (test_webapp.py:1438) fires a real re-render from inside the stubbed slicer (true mid-slice interleave), then asserts `sliced is False`, `reason == "stale"`, no `gcode_url`, and `GET /api/gcode/<rid>` → 404. Exercises the real race window.

No regression: `counter` is monotonic (`itertools.count(1)`), so an evicted rid is never reused — no false version match.

### ENG-002 — Major — reopen/import trust — RESOLVED

`_regate_mesh(config, mesh_path, plan_dict)` (`webapp.py:532-551`) re-derives the gate verdict from the ACTUAL copied mesh + plan: `validate_mesh(load_mesh(...))` → `run_gate(...)` → `str(gate.status)`. Returns `None` only when re-validation can't run (empty plan, or any caught exception).

- Reopen consumes it fail-closed: `gate_status_by_rid[rid] = regated or d.gate_status or "fail"` (`webapp.py:1533`). Re-derived value wins; stored value is the fallback only when re-gate couldn't run; ultimate fallback is `"fail"`.
- Import flows through reopen — verified end-to-end. `_handle_design_import` (`webapp.py:1598-1611`) only persists the file via `import_bytes` and returns `{"id": new_id}`; it never writes `gate_status_by_rid` or the live `registry`. The SPA then opens it: `MyDesigns.tsx:236-238` (`importDesign` → `onOpen(r.id)`) → `App.tsx:529` `reopenDesign`. The only path to sliceable is the re-gating reopen.
- Tampered "pass" over a bad mesh is now caught: `Level.__str__` returns `name.lower()` (`printability.py:47-48`), so `_regate_mesh` yields exactly `"pass"/"warn"/"fail"` — the same space the slice gate compares with `== "fail"` (`webapp.py:1670`). An oversized mesh re-derives `"fail"` regardless of the stored claim (test_regate_mesh_rederives_fail_for_an_oversized_mesh: 300mm box > 256mm build → `"fail"`).
- Legit reopen not false-failed: in-bounds watertight mesh re-gates non-`"fail"`; an unreadable mesh / missing plan returns `None` → falls back to stored (test_regate_mesh_passes_in_bounds_and_returns_none_on_error).
- No regression to import safety: `design_store.import_bytes` (`design_store.py:269-297`) is untouched — still zip-slip-safe.

### ENG-003 — Minor — `allow_nan=False` on HTTP JSON — RESOLVED

`_json` serializes with `allow_nan=False` and maps a non-finite leak to a clean 500 (`webapp.py:785-796`). Sweep: the only other `json.dumps` calls in `webapp.py` are line 756 (static 405 string) and the 792 fallback (static). Every numeric API response routes through `_json`. No bypass.

### ENG-004 — Minor — `describe_photo` contract — RESOLVED

`describe_photo` is declared on the `Provider` Protocol (`llm_provider.py:92-100`) and implemented on `FallbackProvider` (`llm_provider.py:385-389`), delegating through the same `_call` primary-to-alt fallback as the other two methods. Contract total and type-checked. The web vision path still routes to a dedicated local provider per the trust rule and never reaches the fallback delegation (`webapp.py:420-427`).

### ENG-005 — Minor — bounded LRU cloud cache — RESOLVED

`_SettingsAwareProvider._cloud_cache` is an `OrderedDict` capped at `_cloud_cache_max = 4` (`webapp.py:376-377`), LRU-touched on hit (`move_to_end`, line 398) and evicted oldest-first when over cap (`popitem(last=False)`, lines 408-409). Rotating models can no longer accumulate provider objects for the process lifetime.

### ENG-006 — Nit — model_advisor Qwen vs gemma4 — RESOLVED

`gemma4:e4b` is `tier=7` — the highest LOCAL tier in `MODEL_CATALOG` (`model_advisor.py:106`). The three Alibaba Qwen entries are deprioritized to tiers 1/1/2 with `non_china=False` and "never recommended over gemma4:e4b" notes (`model_advisor.py:109-117`); cloud DeepSeek is tier 6. `recommend()` picks the highest-tier installed model that fits (`model_advisor.py:335-343`):

- With gemma4 present (alone or alongside Qwen), gemma4 is always the primary (test_recommends_the_best_installed_model_that_fits asserts gemma4 wins even with `qwen2.5-coder:7b` also present).
- With ONLY Qwen present, Qwen is the primary-to-use-now (can't run an un-pulled model) but gemma4 is surfaced as both the `upgrade` and the non-China escape (test_non_china_escape_names_gemma_when_only_a_china_model_is_installed asserts `non_china_alternative.name == "gemma4:e4b"`). Correct UX; gemma4 is always the steered alternative.

The advisor is CLI-only (not reachable from the Stage 8.5 UI), so this never bore on the gemma4-only invariant at the gate; the policy inconsistency is now reconciled deliberately. Resolved as intended.

### ENG-007 — Minor — geometry-dep DX trap + manifold3d comment — RESOLVED

`tests/conftest.py:29-44` adds a `pytest_collection_modifyitems` hook that imports `scipy`, `networkx`, `manifold3d` and raises one clear `pytest.UsageError` naming the missing backend(s) — replacing the prior ~30 misleading geometry errors. The `hardening.py` docstring is reconciled with the hard pin (`manifold3d>=3.0`): the import guard is documented as DEFENSIVE-for-resilience, not an optional-feature switch; the guard itself is preserved at `harden_mesh`.

---

## Load-bearing invariants — re-verified after the remediation churn

| Invariant | Verdict | Key evidence |
|---|---|---|
| Local-first; cloud OFF by default; degrades to local on every gap | HOLDS | `_SettingsAwareProvider._active()` returns local unless enabled + saved key + model all present; cloud build failure → local (`webapp.py:387-411`). |
| Saved key masked-only, never echoed/logged | HOLDS | `_mask_key` returns a fixed mask + last 5, nothing for short values (`webapp.py:430-438`); `settings_response` returns `cloud_key_masked`/`has_cloud_key` only (`441-451`). ENG-005's bounded cache reduces in-memory residency. |
| Vision is always local even with cloud text enabled | HOLDS | `describe_photo` builds a dedicated local provider (`webapp.py:420-427`). ENG-004 did not reroute it through the fallback. |
| gemma4:e4b is THE model; UI offers no alternative / no Chinese model | HOLDS | model-status hardcodes `gemma4:e4b` (`webapp.py:1084`); no `qwen` string in `src/kimcad/web/assets` or the built `frontend/dist`. ENG-006 raised gemma4 to the top advisor tier. |
| Gate-FAILED part never sliced or sent (server-side, fail-closed) | HOLDS | `_handle_slice` refuses `reason:gate_failed` (`webapp.py:1679-1683`); `_handle_send` belt-and-suspenders refusal (`1241-1245`); verdict stored fail-closed (`gate_status or "fail"`). |
| Confirm is identity (`confirm is not True`) | HOLDS | `ensure_sendable` (`printer_connector.py:200`); `_handle_send` passes literal `confirm=True` only AFTER the gate check (`webapp.py:1257`). |
| Re-render deterministic + invalidates slice/G-code cache | HOLDS — now strengthened | `_handle_render` clears `gcode_registry`/`slice_cache` and bumps `geometry_version` atomically under `lock` (`webapp.py:1775-1788`). ENG-001 closed the one residual concurrency hole. |

No invariant regressed. The remediation strengthened the concurrency-safety and re-render-invalidates-slice invariants without weakening any other. Atomic-write discipline, OpenSCAD sandboxing, zip-bomb bounds, and traceback suppression are untouched and intact.

---

## New findings introduced by the remediation

None. No regression was found. The version-stamp (ENG-001) is consistent under eviction (monotonic ids prevent false matches); the re-gate (ENG-002) is fail-closed and value-space-consistent with the existing gate comparison; the `allow_nan` guard (ENG-003) has no bypass; the Protocol/FallbackProvider addition (ENG-004) is purely additive; the bounded cache (ENG-005) is correct LRU; the advisor re-tiering (ENG-006) preserves all other behavior; the conftest hook (ENG-007) fails fast without affecting a properly-provisioned environment.

---

## What I could not check (unchanged from the original, by instruction)

- Runtime behavior of the running server (covered by the QA role + the completed wiring-audit; a clean-VM live re-gate remains the authority on from-scratch behavior).
- Real OrcaSlicer / OpenSCAD output fidelity (`-m live` not run here; the non-live suite stubs the slicer).
- Real Ollama / OpenRouter round-trips (provider logic tested with fakes).

---

## Final engineering rollup (re-audit)

| Severity | Original | Resolved | Remaining open | New |
|----------|----------|----------|----------------|-----|
| Blocker  | 0 | — | 0 | 0 |
| Critical | 0 | — | 0 | 0 |
| Major    | 2 | 2 | 0 | 0 |
| Minor    | 4 | 4 | 0 | 0 |
| Nit      | 1 | 1 | 0 | 0 |
| Total    | 7 | 7 | 0 | 0 |

All 7 engineering findings are genuinely fixed in the current code, each backed by a code citation, a passing regression/helper test, or both. No regression was introduced. No invariant regressed.

Engineering re-audit verdict: CLEAR (0 open findings).
