# KimCad Backend Foundation — Engineering Deep-Dive (Stages 0–3 Backfill)

**Auditor role:** Independent Principal Engineer (audit-team)
**Date:** 2026-06-06
**Repo:** `C:\Users\scott\dev\kimcad` @ branch `stage-0-7-audit-backfill`
**Scope:** Shipped backend — Stage 0 (pipeline core), Stage 1 (gated export), Stage 2 (connectors), Stage 3 (printer coverage).
**Mode:** AUDIT-ONLY. No source modified.

---

## Method & what was checked

Read every in-scope module in full: `ir.py`, `openscad_runner.py`, `validation.py`, `printability.py`, `orientation.py`, `hardening.py`, `pipeline.py`, `benchmark.py`, `cli.py` (Stage 0); `slicer.py` (Stage 1); `printer_connector.py`, `connectors.py`, `octoprint_connector.py` (Stage 2); `config.py`, `moonraker_connector.py`, `prusalink_connector.py`, `capability.py` (Stage 3). Also traced the gate-is-authority path through `webapp.py` (`/api/slice`, `/api/send`, reopen/import re-gate) and `mcp_server.py`, and the persistence stores (`history.py`, `design_store.py`) where they bear on the safety invariants.

Ran the non-live suite: **778 passed, 4 live deselected, 0 failed** (152s). Probed the sanitizer, the motion-proof regex, the gate's behavior under non-finite mesh extents, and zip-bomb/path-traversal guards with live Python.

Verified the six load-bearing safety invariants from the audit brief. Five hold strongly. One has a narrow, real bypass (ENG-001).

---

## Severity rollup

```
Blocker:  0
Critical: 0
Major:    1
Minor:    3
Nit:      2
-----
Total:    6
```

No Blockers. No Criticals. This is a mature, defensively-engineered backend with prior-audit IDs baked into the code as living comments. The bar is "zero findings"; it is not quite met, but the single Major is a narrow, fixable correctness gap, not a structural problem.

---

## What's working (credit where due)

- **The gate-is-authority invariant is enforced server-side, fail-closed, in every flow.** The web layer keys slice/send refusal off `gate_status_by_rid` (webapp.py:1268, 1727, 1736), the CLI refuses to `--send` a gate-failed part (cli.py:282–290), and all three populate sites default to `"fail"` when a report is absent (webapp.py:1430, 1578, 1848). `_evict` (webapp.py:746) drops the registry and gate-status cache in lockstep, and an evicted rid loses its mesh_path too — so it 404s before the gate check ever matters. The re-render path bumps `geometry_version` and clears the slice cache under lock (webapp.py:1849–1857), closing the stale-geometry race. This is genuinely careful work.
- **The send-gate (invariants b/c) is centralized and strict.** `ensure_sendable` (printer_connector.py:193) requires `confirm is not True` to raise `NotConfirmed` — and the comment explicitly rejects `bool()`-coercion because `bool("no")` is True (mirrored at mcp_server.py:194). Every connector's `send` calls `ensure_sendable` first, which re-proves the slice via the authoritative streaming-capped `prove_gcode_3mf` before `extract_single_plate_gcode` trusts the file. Defense-in-depth ordering is correct.
- **No cross-vendor profile fallback (invariant d).** `resolve_slice_settings` (slicer.py:391) treats `orca_filament_profiles` as the sole source of truth; a material with no entry raises `OrcaProfileError` rather than mapping to a generic. `_find_profile_json` fails loud on ambiguity (slicer.py:382) rather than silently taking the first match. The Elegoo `tpu`-omission in config is the policy applied correctly.
- **Sanitizer + path-traversal safety (invariant e) is sound.** Verified live: `import`/`surface`/`minkowski`/out-of-`library` `use`/`include` all blocked, including across newlines (comments blanked first, full-source scan). Traversal (`library/../../etc`) rejected. Uppercase `MINKOWSKI()` is *not* blocked — but OpenSCAD identifiers are case-sensitive, so it's an unknown-module no-op, not a bypass. `subprocess.run` is never `shell=True`; no `eval`/`exec`/`os.system` in the Python backend.
- **Secrets never logged (invariant f).** Keys live only in the `X-Api-Key` request header; error messages reference the env-var *name* (`cc.api_key_env`), never the value. `read_error_body` reads only the response body, never request headers. `config/local.yaml` is gitignored; stores live in `~/.kimcad/` outside the repo.
- **Connector error taxonomy is excellent.** The `reason`/`user_message` split, the HTTPError-before-URLError ordering (a subclass-ordering bug fixed and commented everywhere), the mid-write-reset auth re-probe (`auth_error_if_upload_rejected`), and "unknown beats wrong" state mapping (Klipper/PrusaLink unknown state → `error`, not silently "ready") are all the right calls and well-tested.
- **Dependency pins are honest and present.** `manifold3d>=3.0`, `trimesh>=4.4` (4.12.2 installed), `numpy>=2.0`, `scipy>=1.13`, `lxml>=5.0` all installed; the hardening import-guard is documented as a *resilience* fallback for a broken install, not an optional-feature switch.

---

## Findings

### ENG-001 — [Major] [stage 0] Correctness/Security — A NaN axis in the rendered bounding box silently passes the dimensional and build-volume gates

**Evidence:** `printability.py:144–163` (`_check_dimensions`) and `printability.py:174–186` (`_check_build_volume`). Both use ordinary float comparisons (`delta > tol`, `g > b`). IEEE-754 makes every comparison with NaN return `False`, so a NaN axis is never flagged. `validation.py:86–87` computes `bbox` directly from `mesh.extents` with no finiteness guard, and `validate_mesh` records no error for a non-finite extent.

Reproduced live:
- A `MeshReport` with `bounding_box_mm=(nan, 50, 50)` against a `[50,50,50]` plan → gate status **PASS** (`dim.match`, `volume.fits`).
- A real `Trimesh` built with one non-finite vertex → `validate_mesh` returns `bounding_box_mm=(10.0, 10.0, inf)`, `watertight=True`, `errors=[]`. (`inf` *is* caught by the gate; `nan` is not — NaN is the live hole.)

**Why this matters:** The dimensional assertion is described in-code as "the headline" safety check (printability.py:30). A part whose mesh produces a NaN extent on any axis — reachable from degenerate OpenSCAD geometry feeding 0/0 through trimesh's normalization/extents math — passes the gate as "dimensions match" and "fits the build plate," then becomes eligible for slicing and sending. The load-bearing gate is bypassed silently, with no error and no warning. The team already clamps non-finite *parameter* inputs on the re-render path (webapp.py:1830–1837), which shows awareness of non-finite flow — but the *rendered-mesh* extents are not guarded.

**Blast radius:**
- Adjacent code: `validation.py` `validate_mesh` (the right place to fix — one guard protects every gate consumer); `pipeline._axis_breakdown` (pipeline.py:99) and `benchmark.grade_correct_dimensions` (benchmark.py:144) share the same NaN-blind comparison and would inherit the fix.
- Shared state: every gate consumer (CLI, web slice/send, MCP, bench grading) trusts `MeshReport`; fixing at the validator is the single coordinated fix.
- User-facing: a malformed part would now correctly FAIL the gate (`mesh.not_watertight`/integrity) instead of passing — no change to legitimate parts (their extents are finite).
- Migration: none; additive validation.
- Tests to update: none break; add a regression asserting a non-finite extent FAILs the gate.
- **Fix path:** In `validate_mesh`, after computing `extents`/`volume`, assert finiteness — `if not np.all(np.isfinite(extents)): errors.append("mesh has non-finite extents"); watertight=False` (or force the gate's integrity check to FAIL on non-finite). Alternatively (belt-and-suspenders) add `if not math.isfinite(g): FAIL` to `_check_dimensions`/`_check_build_volume`.

---

### ENG-002 — [Minor] [stage 1] Correctness — `prove_gcode_3mf` bounds `.gcode` member *count* but not total `namelist()` size

**Evidence:** `slicer.py:275–281`. `_MAX_GCODE_MEMBERS=64` caps only entries ending `.gcode`; a crafted 3MF with millions of *non*-gcode entries still passes `is_zipfile` and forces `zf.namelist()` to materialize the full central directory in memory before the filter runs.

**Why this matters:** The proof is hardened against decompression bombs (streaming cap) and oversized members, but a high-entry-count central directory is a different DoS vector. Exposure is low — the 3MF is normally the slicer's *own* output, and the send path re-proves a file KimCad produced — so this is Minor, not Critical. **Fix path:** reject `len(zf.namelist()) > N` (a few thousand) before filtering.

---

### ENG-003 — [Minor] [stage 0] Correctness — `ensure_terminated` / `inject_library_uses` operate on a regex view that can mis-fire on string literals

**Evidence:** `openscad_runner.py:135–192`. `inject_library_uses` matches `\b{name}\s*\(` anywhere in source; `ensure_terminated` decides termination from a comment-stripped (but not string-stripped) view. An OpenSCAD `text("rounded_box(")` literal, or a module name appearing inside a string, could trigger a spurious `use <...>` injection or a wrong `;` append.

**Why this matters:** OpenSCAD string literals containing a library module name or a trailing `)` are rare in generated geometry, and a spurious `use` of a real library file or an extra `;` is almost always harmless (the sanitizer still gates the result). Real but low-impact. **Fix path:** blank string literals as well as comments before these heuristics, or skip injection when the token is inside a quoted span.

---

### ENG-004 — [Minor] [stage 0] Correctness — `auto_orient` swallows all exceptions from `compute_stable_poses` and silently leaves the part unoriented

**Evidence:** `orientation.py:36–43`. `except Exception: transforms, probs = [], []` collapses any failure (including a genuine geometry error) into "no stable pose found; left as-is" with `stability=1.0`.

**Why this matters:** A part that failed to orient is reported with `stability=1.0` (max confidence) and the description "no stable pose found" — the stability number contradicts the description, and a downstream reader keying off stability would over-trust an un-oriented part. Orientation isn't a safety gate, so impact is bounded, but the `1.0` stability for the failure case is misleading. **Fix path:** report `stability=0.0` for the heuristic/failure fallback, and narrow the `except` (or log the swallowed error to the report).

---

### ENG-005 — [Nit] [stage 1] Hygiene — `slice_model` default `timeout_s=300` is half the configured `slice_timeout_s=600`

**Evidence:** `slicer.py:189` default `timeout_s=300`; `config/default.yaml` `slice_timeout_s: 600`. Production paths (pipeline.py:355, webapp.py:593) pass the config value, so the default is dead for real runs — but a direct caller of `slice_model` would get half the intended budget on the CPU-only 780M target. **Fix path:** align the default to 600, or drop the default to force an explicit value.

---

### ENG-006 — [Nit] [stage 3] Hygiene — Build-volume `VERIFY` markers still stand on shipped reference printers

**Evidence:** `config/default.yaml` — `bambu_p2s` (`# VERIFY exact P2S envelope`) and `bambu_a1` (`# VERIFY exact A1 envelope`) both carry unresolved VERIFY markers while marked `reference_hardware: true`. The gate's build-volume FAIL is only as trustworthy as these numbers; an assumed `256³` that's wrong would pass parts that won't fit. Real hardware validation is post-release per the roadmap, so this is a Nit today, but it's the one data-provenance gap to close before the beta. **Fix path:** confirm the two envelopes against Bambu's published specs (or a connected machine via `capability.reconcile`, which already flags mismatches) and drop the markers.

---

## What I could not check
- No physical printer or real OrcaSlicer/OpenSCAD binary run (the 4 `live` tests were deselected by design); connector correctness is validated only against the bundled mocks/emulators.
- The shipped OrcaSlicer profile tree on disk was not enumerated — `resolve_slice_settings` correctness depends on the configured names resolving uniquely under `resources/profiles/`, which the config comments assert as verified against the pinned build.

## Verdict
A genuinely strong, safety-conscious backend: the gate-is-authority and send-confirmation invariants hold across CLI, web, and MCP, with fail-closed defaults and no cross-vendor fallback — the one Major (ENG-001) is a narrow NaN-comparison hole in the otherwise-load-bearing gate that should be closed with a finiteness guard in `validate_mesh` before beta.
