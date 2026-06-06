# Stage 7 — Test Engineer Deep-Dive (audit-team backfill)

**Auditor role:** Senior Test Engineer (independent, skeptical)
**Date:** 2026-06-05
**Branch:** `stage-0-7-audit-backfill` (HEAD `800016a`)
**Scope:** Stage 7 — Smart Mesh readiness (`smart_mesh.py`), PrintProof3D arm's-length wrapper (`printproof3d.py`), learning store (`history.py`), and the `report.readiness` attachment through the pipeline + design API.
**Method:** read every source + test file line-by-line, then ran the suites read-only.

---

## What I ran (evidence)

```
.venv/Scripts/python.exe -m pytest -m "not live" -q -k "smart or readiness or printproof or history or mesh"
  -> 82 passed, 695 deselected in 5.44s
cd frontend && npm run -s test
  -> Test Files 23 passed (23) | Tests 278 passed (278)
```

No skips, no xfail, no `.only`, no `assert True` placeholders, no commented-out assertions anywhere in the four Stage 7 test files. Every test makes real, specific assertions.

---

## Test-suite shape (one sentence)

For Stage 7 the suite is **bottom-heavy and genuinely behavioral**: pure-function units for the scorer (`test_smart_mesh.py`), injected-runner units for the wrapper (`test_printproof3d.py`), local-FS round-trip + every degrade path for the store (`test_history.py`), and a real-pipeline integration layer (`test_pipeline_readiness.py`) that drives the actual `Pipeline.run`/`rerender` with a fake provider + box renderer — not mocks of the integration seam. The frontend has a dedicated `RightPanel readiness card` describe block (`RightPanel.test.tsx:154`) covering the gauge, verdict, confidence, risks, recommendations, attribution, the located-risk geometry path, the history line, and the empty placeholder.

---

## Coverage of the four named invariants — VERDICT vs CLAIM

| Invariant | Tested? | Evidence |
|---|---|---|
| Readiness synthesis (score/verdict/confidence/risks/recs) | **Yes, thoroughly** | `test_smart_mesh.py:40-216` — every gate tone, every PP severity, clamping, dedupe, purity |
| Readiness is ADVISORY — never flips a gate verdict | **Yes** | `test_pipeline_readiness.py:60` (gate-FAIL part still completes the gate-fail path AND carries readiness); readiness rides *on the report*, scored from gate status, never mutating `gate_status`. Worst-of-two-signals logic tested at `test_smart_mesh.py:113,125` |
| Never claims the engine ran when it didn't | **Mostly — one real hole (TEST-S7-101)** | Honest gate-only attribution tested when the engine *raises* (`test_pipeline_readiness.py:214`) and when it's *absent* (`:44`). NOT tested when the binary is configured but `validate_model` returns `None` (the common real case: binary path set, file missing/unparseable). |
| Engine missing/failed -> gate-only, never a 500/fabricated result | **Yes** | `test_printproof3d.py:58,77,82,88` cover no-binary / no-report / runner-raises / unparseable; `test_pipeline_readiness.py:214` covers the never-breaks-the-build pipeline path |
| History bounds / never-blocks-the-loop / no leakage | **Yes** | cap at `test_history.py:130`; best-effort-unwritable `:142`; thread-safety under 40 writers `:151`; corrupt/non-list/malformed-record degrade `:106-128`. Record shape is coarse-by-design (no prompt/geometry) — no-leakage is structural |
| `report.readiness` payload shape | **Yes (serializer) — partial (located-risk + HTTP body)** | `_readiness_payload`/`_report_payload` unit-tested `test_pipeline_readiness.py:304,321`; located-risk geometry keys only exercised on the frontend (TEST-S7-103) and no live HTTP test asserts `readiness` in the response body (TEST-S7-104) |

---

## Findings

### TEST-S7-101 — Major — Coverage
**The "engine configured but degrades to None" honesty path is untested.**

`_compute_readiness` (pipeline.py:587-607) runs the engine when `binary is not None`. `validate_model` returns `None` — not raises — whenever the binary file is absent, writes no report, or emits unparseable JSON (printproof3d.py:70,105-111). This `None` path is the **most likely real-world degrade** (user sets a path in Settings, binary later missing). The pipeline tests cover only the *raise* path (`test_pipeline_readiness.py:214`, `boom`) and the *engine-absent* path (`:44`, no binary). No test sets a configured binary and has `validate_model` return `None`, then asserts the card honestly reads `attribution == "KimCad printability gate"` / `confidence == "Medium"` / `sources` excludes `"printproof3d"`.

**Why it matters:** a regression that mislabels a gate-only verdict as "PrintProof3D validation engine" when the engine silently didn't run would ship the exact dishonesty the whole attribution machinery exists to prevent — and the suite would stay green.
**Blast radius:**
- Adjacent code: `_compute_readiness` (the `binary is not None and run_engine` branch), `_attribution`/`_confidence`/`sources` in smart_mesh.py.
- User-facing: the card's confidence + attribution line.
- Migration: none.
- Tests to update: add one to `test_pipeline_readiness.py` (monkeypatch `validate_model` -> `lambda ...: None`, binary configured).
- Related: PP-side `None` returns ARE unit-tested; this is the *pipeline composition* gap.

**Fix path:** add `test_engine_configured_but_returns_none_degrades_honestly` mirroring `test_printproof3d_failure_never_breaks_the_build` but with `validate_model` returning `None` instead of raising; assert gate-only attribution + Medium confidence + `"printproof3d" not in readiness.sources`.

### TEST-S7-102 — Minor — Coverage
**`_fallback_readiness` (pipeline.py:285) — the last-resort defensive card — is never exercised.**

`_compute_readiness` wraps `assess_readiness` in a try/except whose `except` returns `_fallback_readiness(gate)` (pipeline.py:605-607). Grep confirms no test references `_fallback_readiness`. It's the airtight-never-raises backstop; if a future edit to `assess_readiness` made it raise on some input, the fallback's own correctness (does it set a sane tone/verdict/attribution?) is unverified.
**Blast radius:** isolated defensive function. **Fix path:** a 3-line unit — `monkeypatch.setattr("kimcad.pipeline.assess_readiness", boom)`, run a part, assert the report carries a gate-only `_fallback_readiness` card and the build still completes.

### TEST-S7-103 — Minor — Coverage
**The Python `_readiness_payload` located-risk branch (issueId/region/geometry) is untested on the Python side.**

`_readiness_payload` (webapp.py:106-116) conditionally spreads `issueId`/`region`/`geometry` only when a risk carries them. The single Python serializer test (`test_pipeline_readiness.py:321`) feeds a plain `Risk("Overhang unsupported", ..., "warn")` with no geometry, so those three conditional keys are **never produced by a Python test** — only the frontend's mocked payload (`RightPanel.test.tsx:185-199`) exercises them. A bug in the Python conditional (wrong key casing `issueId`, leaking a `None` geometry) would pass Python tests.
**Blast radius:** the viewport highlight contract (Python emits `issueId`/`geometry`; KCViewport consumes). **Fix path:** extend the `_readiness_payload` unit with a located `Risk(..., issue_id="OVERHANG_UNSUPPORTED", region="overhang", geometry={"type":"point","x":0,"y":0,"z":0})` and assert the three camelCase keys appear (and are absent for a gate-derived risk).

### TEST-S7-104 — Minor — Coverage
**No end-to-end HTTP test asserts `readiness` survives into the `/api/design` response body.**

`test_webapp.py` has many live `/api/design` round-trips (`:130,456,712,...`) but none assert `readiness` (grep: no match for `readiness` in `test_webapp.py`). The serializer is unit-tested directly, so the risk is low, but the wire contract the React app actually fetches (`_result_to_payload` -> `report.readiness`) is verified only by composition, never by a real request body.
**Fix path:** in an existing `/api/design` HTTP test, assert `data["report"]["readiness"]["verdict"]` is present.

---

## What's working (credit where due)

- **The advisory-not-gate invariant is real and tested.** Readiness is scored *from* `gate.status` and attached *to* the report; it never writes back to `gate_status`. The gate-FAIL-still-completes test (`test_pipeline_readiness.py:60`) and the gate-FAIL-still-recorded test (`:286`) prove the gate decision is independent.
- **The "never rosier than the engine" worst-of-two-signals rule** has dedicated regression tests with finding IDs in the test bodies (SM-001 at `test_smart_mesh.py:113,125`) — a fail/warning engine status forces the verdict down even when the score wouldn't.
- **Every degrade path on the wrapper is a named test**, and they assert the *result* (`None`), not the mock — no-binary, no-report, runner-raises, unparseable JSON, non-list issues/fixes, unknown severity dropped-not-guessed (`test_printproof3d.py:96-126`). This is the opposite of over-mocking: the injected `Runner` is the documented seam, and the canned report mirrors the real schema.
- **The store's never-break-the-loop contract is genuinely proven**, including real OS-level adversarial cases: an unwritable path (parent is a file, `:142`) and 40-thread concurrency reproducing the torn read-modify-write the lock fixes (`:151`, references ENG-701). Bounds, corrupt-file, non-list, and per-record skip are all covered.
- **`compare_phrase` honesty edges are tested**, including the tie-is-"on par"-not-"below" boundary (SLICE5-001, `:52`) and the exactly-2-same-type-still-falls-back boundary (TEST-S7-003, `:80`) — boundary thinking is present, not just happy path.
- **Regression-test culture is visible:** test bodies cite the finding IDs they close (SM-001, SM-002, PP-001, SLICE3-001/002, SLICE5-001, ENG-701, TEST-S7-001/002/003). Fixes came with tests.
- **The frontend card is tested against rendered output** (gauge aria-label, tone class, located-vs-plain risk button, history line, jargon InfoTips) — not snapshots, real role/text queries.

---

## Severity summary

```
Blocker:  0
Critical: 0
Major:    1   (TEST-S7-101)
Minor:    3   (TEST-S7-102, TEST-S7-103, TEST-S7-104)
Nit:      0
-----
Total:    4
```

No Blockers. No Critical. The one Major is a single concrete missing test (the most-likely real degrade path: engine configured, binary gone). The three Minors are defensive-path / serializer-edge / wire-body gaps, each closable with one small test. Given the zero-findings beta bar, all four should be closed; none changes product behavior, only proof.

**Verdict: NOT-PASS at the zero-findings bar — 1 Major + 3 Minor coverage gaps. Underlying Stage 7 logic is sound and well-tested; the gaps are missing proofs, not broken behavior. Closing the four tests above clears it.**

Report path: `C:\Users\scott\dev\kimcad\docs\audits\stage-7\backfill-2026-06-05\04-test-deepdive.md`
