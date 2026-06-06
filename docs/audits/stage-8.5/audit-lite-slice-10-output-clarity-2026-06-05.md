# Audit Lite — Stage 8.5 Slice 10: Output clarity & print preview
**Date:** 2026-06-05
**Scope:** The staged diff on `stage-8.5-usability` implementing Slice 10 — break the slice estimate into labeled stats (time / layers / filament length + weight), a "your design → print file" framing, clearer export-format surfacing, and a copy-the-link affordance. Generated SPA build artifacts (`src/kimcad/web/assets/*`) excluded per the pre-push reproducibility gate.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship with two small fixes. This is a clean, honest, well-tested slice — the filament-weight regex handles both vendor wordings, the derived weight is correctly labeled an estimate, the formatters never fabricate zeros, and the gate/cache/idempotency invariants are untouched. Two findings hold it back from a clean pass: the in-repo backend API contract in HANDOFF.md still documents the old `/api/slice` response shape (Major doc drift), and one reachable honesty wart where a degenerate zero-volume slice renders an "estimated weight" footnote with no weight beside it (Minor, and untested).

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 1
- Nit: 1

## Findings

### FINDING-001 Major: HANDOFF.md backend API contract omits the two new `/api/slice` response fields
**Dimension:** Docs
**Evidence:** `HANDOFF.md:291-292` documents the seam the SPA wires to: `POST /api/slice/<id> {printer,material} → {sliced,reason?,estimate,gcode_url?}`. This slice grew that response with `estimate_detail` (`src/kimcad/webapp.py:548-552`) and `gcode_filename` (`src/kimcad/webapp.py:1565-1567`), both now consumed by the SPA (`frontend/src/api.ts:144,147`; `frontend/src/components/ExportPanel.tsx:207,268,285`). `git status --short -- "*.md"` is empty — no doc file was touched in this slice, staged or unstaged, so the contract is stale as written. The block even calls itself "the seam the SPA wires to," which is exactly the field this change invalidated.
**Why it matters:** HANDOFF.md is the deliberately-maintained source of truth a future session (or the eventual stage-merge docs-consistency pass) reads to know the contract. A documented contract that omits two live, SPA-consumed fields is drift; the skill's hard guardrail puts behavior-altering doc drift at "at least Major." The same convention was honored at Slice 5 (the `gcode_url`/`estimate` fields were added to this very contract line), so the precedent is to keep this line current per slice.
**Fix path:** Update `HANDOFF.md:292` to `→ {sliced,reason?,estimate,estimate_detail?,gcode_url?,gcode_filename?}` (and optionally one phrase noting `estimate_detail` carries the structured time/layers/filament-length/weight breakout plus the `filament_g_estimated` honesty flag). One-line edit.

### FINDING-002 Minor: a zero-volume slice shows the "estimated weight" footnote with no weight stat
**Dimension:** Correctness / UX (honesty)
**Evidence:** When the profile reports volume `0.0` and no grams, `_estimate_detail_with_weight` sets `filament_g = round(0.0 * density, 1) = 0.0` and `filament_g_estimated = True` (`src/kimcad/webapp.py:495-501`; confirmed by direct call: `{'filament_cm3': 0.0, 'filament_g': 0.0, 'filament_g_estimated': True}`). On the frontend, `formatFilamentWeight(0)` returns `null` because of the `g <= 0` guard (`frontend/src/printEstimate.ts:17`), so `buildEstimateRows` produces no Weight row — but `PrintSummary` renders the footnote off the raw flag `slice.estimate_detail?.filament_g_estimated` (`frontend/src/components/ExportPanel.tsx:250-255`), independent of whether a weight row actually rendered. Net result: "Weight is estimated from the print volume…" with nothing it refers to.
**Why it matters:** Honesty is load-bearing here. A dangling estimate caption with no referent is the small-scale version of the failure this slice exists to prevent (a label that implies data that isn't shown). Reachability is genuinely low — it needs a degenerate/near-empty slice that emits `filament used [cm3] = 0.00` and no grams, and gate-failed parts can't be sliced — so it's Minor, not higher.
**Fix path:** Two clean options. (a) Frontend: gate the footnote on a weight row existing, e.g. only render it when `rows.some(r => r.key === 'weight') && filament_g_estimated`. (b) Backend: in `_estimate_detail_with_weight`, require `cm3 > 0` (not just `is not None`) before deriving — then a zero volume yields `filament_g = None` and `filament_g_estimated = False`, which is the truthful state. Recommend (b): it keeps the honesty rule enforced at the source so any future consumer (CLI, MCP) inherits it, not just this one component. Add a regression test (see FINDING-003).

### FINDING-003 Nit: the estimated-footnote / zero-volume path has no test
**Dimension:** Tests
**Evidence:** Every test that exercises `filament_g_estimated: true` also supplies a renderable weight (`filament_g: 9.3`) — `frontend/src/components/ExportPanel.test.tsx:200-206`; the backend weight tests cover none / present / no-density / no-volume (`tests/test_webapp.py:1110-1151`) but not `cm3 == 0.0`. So the FINDING-002 edge would not be caught by the suite as it stands.
**Why it matters:** Bundled with the FINDING-002 fix this is a one-case regression test, not a standalone gap — hence Nit rather than the Major a real untested feature would earn. Calling it out so the fix lands with its guard test (the project's standing "a fix without a test isn't done" rule).
**Fix path:** When fixing FINDING-002 via option (b), add `test_weight_omitted_when_volume_is_zero` asserting `filament_g is None and filament_g_estimated is False` for `cm3 = 0.0`. If fixing via (a), add an ExportPanel case asserting the footnote is absent when no weight row renders.

## What's working
- **The dual-vendor weight regex is correct and robust.** `_FIL_G_RE` (`src/kimcad/slicer.py:57-59`) matches PrusaSlicer/Elegoo `filament used [g] = N` and Bambu `total filament weight [g] : N`, tolerates missing spaces and the no-space-before-colon variant, and on multi-material lines takes the first/primary-extruder value — consistent with how `_FIL_MM_RE`/`_FIL_CM3_RE` already behave. Verified directly against eight wordings; both spellings are tested (`tests/test_slicer.py:329-365`).
- **The derived weight is honestly labeled.** When the profile carries no grams, the weight is estimated from `cm³ × material.density` and flagged `filament_g_estimated`, surfaced as a plain-English footnote (`src/kimcad/webapp.py:486-502`; `frontend/src/components/ExportPanel.tsx:250-255`). The "prefer slicer grams, else estimate, else nothing" precedence is exactly right and well tested (`tests/test_webapp.py:1110-1151`), including the live P2S-PLA path that proves the real shipped profile reports `filament_density=0` and triggers the estimate (`tests/test_webapp.py:512-517`).
- **No fabricated zeros.** The formatters and `buildEstimateRows` drop any field the slicer didn't report rather than rendering `0`/`—` (`frontend/src/printEstimate.ts:9-46`), with explicit tests for the omit-unreported and all-null cases (`frontend/src/printEstimate.test.ts:47-69`); the backend mirrors this with the all-None detail + empty summary test (`tests/test_slicer.py:367-381`).
- **Copy-link is safe — no data-leak or injection vector.** `gcode_url` is always the server-side relative `/api/gcode/{rid}` (`src/kimcad/webapp.py:1564`), so `new URL(fileUrl, window.location.origin)` (`frontend/src/components/ExportPanel.tsx:211-214`) can only ever resolve to a localhost URL; there's no external-URL override path. The clipboard write is wrapped with a graceful catch for blocked/insecure contexts (`ExportPanel.tsx:216-226`), with an sr-only `role=status` confirmation for a11y.
- **The download filename is KimCad-derived, not user input.** `gcode_filename = gcode_path.name` (`src/kimcad/webapp.py:1567`) traces to a basename built from the pipeline-fixed mesh name plus config enum keys (`src/kimcad/webapp.py:530`) — no free-text reaches it, so no traversal/injection concern in the `download=` attribute or the rendered name.
- **Gate, cache, and idempotency invariants intact.** The gate-FAILED refusal (`src/kimcad/webapp.py:1591-1597`) and the cache/`slice_lock` idempotency path (`1601-1626`) are untouched; the only change to `_respond_slice` is the additive `gcode_filename`, which runs identically for cache-hit and fresh-slice. `estimate_detail` is computed in `slice_registered_mesh` and cached in `info`, so a re-confirm returns the identical breakout. Gate-awareness and cancel-escape regression tests still pass (`ExportPanel.test.tsx:43-112`).
- **Runtime verified in scope.** All 8 new backend tests and all 18 new frontend tests pass on this machine; `ruff check` is clean on the six changed Python files. (Full-suite green + reproducible SPA build were reported already-verified and not re-run.)

## Watch items
- `ARCHITECTURE.md:66` describes the parsed estimate as "(time, layers, filament)." "Filament" still reasonably covers length + weight, so it's not stale enough to be a finding — but if a future slice surfaces weight more prominently, consider naming it there.
- No CHANGELOG entry for Slice 10. Per-slice entries exist for Slices 1–7 but Slices 8 and 9 also lack them, so the recent pattern is to batch the changelog at stage-merge, not per-slice — consistent, not a regression. Just make sure Slice 10 lands in the Stage 8.5 changelog block at merge time.
- Multi-material honesty (pre-existing, out of scope): the estimate takes the first extruder's value for length/volume/weight. Fine for single-material prints (all Kim's profiles today); worth a note if multi-material lands later.

## Escalation recommendation
No escalation needed. This is a small, single-feature slice that stayed in its lane; the findings are one doc-line edit, one localized honesty guard, and its test. Nothing architectural, no Blocker/Critical, no cross-cutting blast radius — audit-lite is the right altitude. Re-audit the same scope after the two fixes (FINDING-001, FINDING-002) and their guard test land.

---

## Re-audit (2026-06-05)
**Reviewer:** Claude (audit-lite, independent re-audit pass)
**Scope:** The same staged diff on `stage-8.5-usability` after the three fixes (FINDING-001/002/003) were applied. Verified against current file state and the staged diff (`git diff --cached`), not the prior report's quoted line numbers. Build artifacts (`src/kimcad/web/assets/*`) excluded per the pre-push reproducibility gate.

### Verdict: CLEAN — 0 / 0 / 0 / 0 / 0
All three prior findings are genuinely resolved with evidence below. No new finding at any severity was introduced by the fixes. The slice is clean and ships.

### Prior findings — resolution status

**FINDING-001 (Major, Docs) — RESOLVED.**
`HANDOFF.md:291-295` now documents the grown contract: `POST /api/slice/<id> {printer,material} → {sliced,reason?,estimate,estimate_detail{time,layers,filament_mm,filament_cm3,filament_g,filament_g_estimated}?,gcode_url?,gcode_filename?}` plus a Slice-10 clause explaining `estimate_detail` is the structured breakout and that weight is `volume×material-density` when the profile reports none, flagged `filament_g_estimated`.
- **Accuracy verified field-by-field** against the live response. `estimate_detail`'s inner keys exactly match `GcodeProof.estimate_detail()` (`src/kimcad/slicer.py:159-169` → `time,layers,filament_mm,filament_cm3,filament_g`) plus the `filament_g_estimated` key injected by `_estimate_detail_with_weight` (`src/kimcad/webapp.py:503`). `estimate_detail` is emitted in `slice_registered_mesh` (`src/kimcad/webapp.py:552-556`) and `gcode_filename` is added in `_respond_slice` (`src/kimcad/webapp.py:1569`). Both are SPA-consumed (`frontend/src/api.ts:131-150`).
- **Completeness:** the documented `?` optionality is correct — `estimate_detail` is `None` when there's no proof (`webapp.py:552-556`), and `gcode_filename`/`gcode_url` are only present when a gcode file exists (`webapp.py:1563-1569`). The contract line is intentionally a compressed seam (it never enumerated `printer/material/gcode_lines/profiles`), so documenting the two new fields at that same altitude is complete relative to the established style — same convention honored when `gcode_url`/`estimate` were added at Slice 5. No residual drift.

**FINDING-002 (Minor, honesty) — RESOLVED, both guards correct and consistent.**
- **Backend guard** (`src/kimcad/webapp.py:495-503`): grams are derived only when `cm3 and cm3 > 0 and density`. A degenerate `cm3 == 0.0` short-circuits on `cm3` (falsy) → `filament_g` stays `None`, `filament_g_estimated` stays `False`. `density` falsy (`None` or `0.0`) also correctly blocks derivation. Negative `cm3` is caught by `cm3 > 0`. The truthful state (`None`/`False`) is what reaches the UI for the degenerate case. Verified by direct test run (below).
- **Frontend guard** (`frontend/src/components/ExportPanel.tsx:191-194`): `showEstNote = !!slice.estimate_detail?.filament_g_estimated && rows.some(r => r.key === 'weight')`. The footnote can render only when a weight row actually exists (`buildEstimateRows` adds a `weight` row only when `formatFilamentWeight(filament_g)` is non-null, i.e. `g > 0` — `frontend/src/printEstimate.ts:16-18,42-44`). Defence-in-depth: even if a backend ever emitted `filament_g_estimated:true` with no renderable grams, the caption stays suppressed.
- **Consistency:** the two guards agree on the invariant "no estimated-caption without a weight beside it" and meet it at both layers. When the slicer reports real grams, `filament_g_estimated:false` → no caption (correct); when KimCad derives, `true` + weight row → caption shows (correct).

**FINDING-003 (Nit, tests) — RESOLVED, the new tests exercise the guards.**
- Backend zero-volume case: `tests/test_webapp.py:1141-1156` (`test_weight_omitted_when_no_density_or_no_volume`) asserts all three honesty branches — no-density, no-volume, and `cm3 = 0.0` — each yields `filament_g is None and filament_g_estimated is False`. The `cm3 = 0.0` assertion directly exercises the `cm3 and cm3 > 0` guard. Companion positive/prefer-slicer tests at `1113-1138`.
- Frontend orphan-caption case: `frontend/src/components/ExportPanel.test.tsx:218-238` ("never shows the estimate footnote without a weight beside it") stubs `filament_cm3:0, filament_g:null, filament_g_estimated:true` and asserts both `Weight` row and the "weight is estimated" caption are absent — exercising the `rows.some(weight)` branch of `showEstNote`.
- Ran the targeted tests this pass: 3 backend guard tests passed (`pytest tests/test_webapp.py::test_weight_*`), and the full `ExportPanel.test.tsx` + `printEstimate.test.ts` vitest run was 19/19 passed. `tests/test_slicer.py` + `tests/test_config.py` = 45 passed (covers the `estimate_summary` lead-with-grams change and the new `density` config field). `ruff check` clean on all six changed Python files.

### New-issue hunt (did the fixes weaken anything?)
- **Dataclass safety:** `Material.density: float | None = None` (`src/kimcad/config.py:50`) is the only defaulted field and is last in the frozen dataclass, so every positional `Material(...)` construction in the test suite (conftest, test_capability/geometry/llm_provider/printproof3d/slicer) still constructs — verified by the green slicer/config runs. No constructor breakage.
- **`estimate_summary` change:** now leads with grams and suppresses the cm3 line when grams exist (`src/kimcad/slicer.py:151-155`). Its one downstream consumer (`src/kimcad/pipeline.py:731`) takes the string opaquely, and the slicer tests assert the new wording. No regression.
- **First-wins scan parity:** the new `_FIL_G_RE` scan honors the same `"fil_g" not in est` first-match guard as the mm/cm3 scans (`src/kimcad/slicer.py:329-332`), so multi-material lines take the primary-extruder value consistently. No new behavior wart.
- **Invariants re-checked:** local-first copy-link resolves only against `window.location.origin` over the server-relative `/api/gcode/{rid}` — no external-URL path, no leak/injection (`ExportPanel.tsx:195-198`, `webapp.py:1566`); honesty preserved (derived weight labeled, no fabricated zeros at either layer); gate-FAILED refusal and cache/`slice_lock` idempotency untouched (only additive `estimate_detail`/`gcode_filename`); tests present for all new behavior. None weakened.

### Final severity rollup (re-audit)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

Slice 10 is clean (0/0/0/0/0). Clear to merge into the Stage 8.5 line. (Reminder from the prior watch items, not a finding: fold the Slice 10 entry into the Stage 8.5 CHANGELOG block at stage-merge, consistent with the batch-at-merge pattern.)
