# Stage 7 — Test Engineer Deep-Dive

**Auditor:** Test Engineer (audit-team, balanced posture)
**Date:** 2026-06-02
**Scope:** Stage-7 test suites — `test_smart_mesh.py`, `test_printproof3d.py`, `test_pipeline_readiness.py`, `test_history.py`, plus frontend `RightPanel.test.tsx` / `designStatus.test.ts`. Implementation cross-read: `smart_mesh.py`, `history.py`, `printproof3d.py`, `pipeline.py`, `webapp.py`.

---

## Suite run results (I ran them myself)

| Suite | Command | Result |
|---|---|---|
| Stage-7 Python subset | `pytest tests/test_smart_mesh.py tests/test_printproof3d.py tests/test_pipeline_readiness.py tests/test_history.py -q` | **55 passed** in 0.52s |
| Full Python suite | `pytest tests -q` | **664 passed** in 95.2s |
| Frontend (vitest) | `npm --prefix frontend run test` | **43 passed** (6 files) in 1.58s |

No skips, no xfails, no `.only`/`.skip` in the Stage-7 files. Zero flake observed across the runs. The numbers match the claimed baseline (664 / 43) exactly.

---

## Test-suite shape (one-liner)

Heavy, well-isolated unit layer with a genuine injected-runner integration seam at the pipeline. `assess_readiness`, `compare_phrase`, and `_parse_report` are pure and exhaustively unit-tested; the PrintProof3D subprocess and the OrcaSlicer live path are the only real-process integrations, and the deep engine is exercised via an injected fake — honest about what it does and does not prove. No E2E browser layer for the readiness card (vitest renders the component with React Testing Library against stubbed fetch), which is acceptable at this altitude.

---

## What's working (credit where real)

- **The degrade-path matrix on `validate_model` is genuinely strong.** Every failure mode is exercised: no binary (`binary=None`), runner writes nothing, runner raises, unparseable report, non-dict body, bad status, unknown severity skipped, non-list `issues`/`suggested_fixes` (PP-001). These are the never-raises contract's teeth and they are actually pulled. (`test_printproof3d.py:56–124`)
- **The injected-runner / injected-`validate_model` pattern is the right call.** The wrapper is tested offline without the Rust binary (`_runner_writing`, `test_printproof3d.py:46`), and the pipeline tests `monkeypatch` `kimcad.pipeline.validate_model` so engine integration is exercised without a real subprocess (`test_pipeline_readiness.py:132`). This is integration-as-integration, not a unit test wearing a costume.
- **The bed-positioning assertion is REAL, not a flag.** `fake_validate` actually calls `trimesh.load(str(mesh_path))` and reads `mesh.bounds[0]`, then the test asserts each min-corner component `abs(...) <= 0.01` (`test_pipeline_readiness.py:114–146`). It loads the STL the pipeline wrote and checks real geometry — it does not trust a boolean. This is the single most falsifiable assertion in the slice and it earns its keep.
- **Worst-of-two is covered in both directions.** The engine-worse-than-gate case is tested three ways: a blocker sinks a clean gate pass (`test_printproof_blocker...`), a `fail` *status* with only a `major` issue still forces "Not print-ready" (SM-001, `test_smart_mesh.py:113`), and a `warning` status drops a clean pass to "with notes" (`:125`). The "card is never rosier than the engine" invariant is well-pinned.
- **`compare_phrase` wording is exhaustively pinned and the honesty edge is tested.** Personal-best-only-on-strict-beat, tie-is-not-personal-best, below-all, **tie reads "On par" not "below"** (SLICE5-001, `test_history.py:52`), same-type narrowing at the threshold, and the all-parts fallback. The non-flattering contract is enforced by tests, not just docstring.
- **History best-effort/never-raise is covered end to end:** missing file, corrupt JSON, non-list JSON, malformed-record-skip-but-keep-rest, cap at `_MAX_RECORDS` (via monkeypatch), and an unwritable path (parent is a file). All assert no raise + sane fallback. (`test_history.py:92–138`)
- **No test pollution.** Every `HistoryStore` in the tests is `tmp_path`-scoped (`test_history.py`, `test_pipeline_readiness.py`); I grepped `config.history_path()` and it appears only in `cli.py`/`webapp.py` production code, never in a test. No test writes to the real user history file.
- **The pre-push gate is real and is a superset of hosted CI.** `.githooks/pre-push` → `scripts/ci.sh` runs ruff + full pytest (`-ra` so a skipped live-slice is visible, not silently green) + vitest + SPA build-reproducibility (committed `src/kimcad/web` must equal a fresh build) + a `KIMCAD_RELEASE=1` hard-gate that refuses to release when the OrcaSlicer live tests or the frontend toolchain are absent. This is a disciplined gate, not theater.

---

## Findings

### TEST-S7-001 (Minor) — No test asserts a gate-failed part is recorded to history

**Category:** Coverage

**Evidence:** `pipeline.py:439–457` calls `self._record_history(plan, report)` *before* the gate-fail early return (the `gate.status is Level.FAIL` block is at `:443`). `_record_history` (`:540`) records unconditionally of gate status — and this is *intended*: `history.py:31`/`:48` docstrings explicitly say records may be "gate-failed and none necessarily printed". Yet the only recording test, `test_history_comparison_folds_in_and_the_build_is_recorded` (`test_pipeline_readiness.py:244`), exercises a **completed** part. `test_gate_failed_run_still_attaches_readiness` (`:60`) asserts readiness but passes no `history=` store, so it never touches the record path. No test pins "a gate-failed build still lands in the store."

**Why this matters:** The comparison line ranks against prior records including gate-failed ones. If a refactor moved the `record_history` call below the gate-fail return (a plausible "only record successes" change someone might make on intuition), gate-failed parts would silently stop being recorded, the documented behavior would regress, and **no test would fail**. This is exactly the worst-of-two-style invariant the slice cares about, left unpinned on the integration path.

**Blast radius:**
- Adjacent code: `pipeline.py` `_assemble` record ordering; `history.py` `record`/`compare_phrase` pool composition.
- User-facing: the "compared to your past prints" line's denominator (does a blocked attempt count?). Observable in the readiness card comparison text.
- Migration: none.
- Tests to update: add one to `test_pipeline_readiness.py` near `:269`.
- Related findings: none.

**Fix path:** Add a test: build a gate-failing part (reuse the wrong-size renderer from `test_gate_failed_run_still_attaches_readiness`) with a `tmp_path` `HistoryStore`, then assert `len(store.load()) == 1` and `records[0].gate_status == "fail"`.

---

### TEST-S7-002 (Minor) — The `mesh_unanalysable`-beats-engine confidence precedence is untested

**Category:** Coverage

**Evidence:** `_confidence` (`smart_mesh.py:198–205`) checks `if mesh_unanalysable: return "Low"` *before* `if printproof is not None: return "High"`. So an unanalysable mesh forces **Low** even when the deep engine ran. The only Low test (`test_smart_mesh.py:156`) runs the **gate-only** path (no `printproof=`). No test passes both `printproof=<report>` and `_mesh(errors=[...])` together, so the precedence — Low must win over the engine's High — is asserted by no test.

**Why this matters:** This is the conservative-honesty rule for the card ("any verdict is provisional when we couldn't analyse the geometry"). If someone reorders the two branches so the engine's presence wins, the card would claim **High** confidence on a part KimCad couldn't fully analyse — overstating certainty on exactly the parts where it should hedge. A 2-line edit could do it and the suite stays green.

**Blast radius:**
- Adjacent code: `_attribution` (`smart_mesh.py:208`) has the same branch order; same risk on the attribution string.
- User-facing: the confidence chip ("High/Medium/Low confidence") and the "(mesh only partly analysable)" attribution suffix.
- Tests to update: add to `test_smart_mesh.py`.

**Fix path:** Add `test_unanalysable_mesh_keeps_confidence_low_even_with_the_engine`: `assess_readiness(_gate(PASS...), _mesh(errors=["..."]), printproof=<a high-confidence report>)` and assert `r.confidence == "Low"` and that the attribution still carries "partly analysable".

---

### TEST-S7-003 (Minor) — `_MIN_SAME_TYPE` is tested at 3 and 1, but not the boundary-minus-one (exactly 2) in `compare_phrase` directly

**Category:** Coverage / Boundary

**Evidence:** `test_compare_phrase_narrows_to_same_type_once_there_are_enough` uses **exactly 3** same-type boxes and asserts narrowing (`test_history.py:62`) — the boundary *at* threshold is covered, good. The fallback test uses **1** box (`:73`). The store-level test at `:147` hits 2 same-type via `HistoryStore.comparison`. But `compare_phrase` is the pure function and the "2 same-type → still falls back to all parts" boundary (one below `_MIN_SAME_TYPE`) is not asserted directly on it — it's only reached transitively through the store.

**Why this matters:** Off-by-one in the `len(same) >= _MIN_SAME_TYPE` guard (`history.py:52`) is the classic boundary bug. The at-3 case would catch `>` vs `>=`, so this is genuinely Minor (the dangerous mutation is already covered). Logged for completeness, not as a gap that lets a real bug through.

**Fix path:** Optional: add a 2-same-type case to `test_compare_phrase_falls_back_to_all_parts...` asserting scope is "parts", not "box parts".

---

### TEST-S7-004 (Nit) — Two assertions lean toward tautology but are saved by a sibling

**Category:** Quality

**Evidence:** `test_assess_readiness_is_pure_same_inputs_same_output` (`test_smart_mesh.py:195`) asserts `a == b`. `MeshReadiness` is a non-frozen `@dataclass`, so `==` is structural — this is a real determinism check, not a tautology, and it's fine. Separately, `test_parse_report_tolerates_missing_optional_fields` asserts `r.issues == ()` on an input with `"issues": []` — close to asserting the obvious, but the *adjacent* PP-001 test (`:115`) covers the load-bearing non-list case, so the pair is fine. No action needed; noting that the purity test's value depends on the dataclass staying value-comparable (if it ever gains a non-compared field, the test weakens silently).

**Fix path:** None required. If `MeshReadiness` is ever made `frozen`/`eq=False`-tuned, revisit.

---

## Blind-spot sweep (checked, found covered)

- PrintProof3D `fail` status with a non-blocker issue — **covered** (SM-001, `:113`).
- `nit` severity not surfacing as a risk — **covered** (`:145`).
- Score clamp to [0,100] — **covered** (`:167`, 5 blockers → 0).
- Recommendation dedupe — **covered** (`:186`).
- Re-render runs no engine + records no history — **covered** (`:156`, `:269`).
- Engine-explodes-never-breaks-build — **covered** (`test_printproof3d3d_failure_never_breaks_the_build`, `:214`) and degrades to gate-only attribution.
- `_report_payload` readiness block + `_readiness_payload(None)` — **covered** (`:288`, `:305`).
- Frontend readiness card branches: warn+risks+SR "Warning:" cue, pass-tone class + gate attribution, comparison line, idle placeholder, failed "no part to assess" placeholder, `readinessTone` neutral fallback, `gateLabel` reframe not duplicating "ready to print" — **all covered** (`RightPanel.test.tsx:135–213`, `designStatus.test.ts:29–58`).

---

## Severity rollup

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 1 |
| **Total** | **4** |

No Blocker, no Critical, no Major. The three Minors are all "a documented/real behavior on the integration path has no test pinning it" — each names a plausible refactor that would regress silently. None blocks the Stage-7 tag; all are cheap to close and worth doing this slice.

---

## Culture observation (for the exec report)

This is a disciplined test culture. The team writes the never-raises contract *as tests* (the degrade matrix), uses dependency injection to test the real integration seam offline, and — notably — the bed-positioning test loads the actual STL rather than trusting a flag, which is the kind of falsifiable assertion most teams skip. The gaps are not shortcuts or lies; they are three honest coverage holes on the pipeline-integration branches (gate-failed recording, confidence precedence, one boundary), where the pure-function layer is exhaustive but the integration layer's behavioral invariants are a notch less pinned. Fixing the three Minors brings the integration layer up to the (high) bar the unit layer already sets.
