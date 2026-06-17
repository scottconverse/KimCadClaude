# Test Suite Deep-Dive — KimCad 0.9.0b4 (+ restored UI)

**Audit date:** 2026-06-16
**Role:** Test Engineer
**Scope audited:** `tests/**` (pytest, incl. `tests/e2e/` Playwright), `frontend/src/**/*.test.{ts,tsx}` (vitest), `.github/workflows/{ci,pr-smoke,cost-hygiene}.yml`, `scripts/ci.sh`, `.githooks/pre-push`, `pyproject.toml` pytest config, `tests/conftest.py`.
**Auditor posture:** Adversarial (no-false-greens lens applied hard).
**Repo state:** `origin/main` @ `356867d`.

---

## TL;DR

This is a **strong, behavior-first test suite with a genuinely fail-closed gate** — the opposite of the withdrawn-b5 failure class. The single most important thing I set out to disprove (that "live"/"real-tool" coverage is mockable or doesn't actually run in CI) I could not: the gate runs the real OrcaSlicer/OpenSCAD/CadQuery/Chromium binaries, asserts EXECUTION not collection (`KIMCAD_CI_STRICT=1` fails the whole build on *any* skip on the provisioned box, plus an explicit `-m live … 0 skipped` re-run), and the slicer's success is proven by opening the real `.gcode.3mf` zip and requiring motion-bearing G-code (`prove_gcode_3mf`), not by asserting a constructed command string. I reproduced a real end-to-end slice and a real qwen2.5:7b plan myself (proof below). The suite is roughly **1045 pytest functions + 376 frontend `it()` blocks**, bottom-heavy on fast unit tests with a thin-but-real integration/e2e layer that drives actual tools.

The most important class of bug that can still slip through is in **the real LLM → OpenSCAD → render → slice chain end to end**: no automated test exercises a real model past the *plan* step. The only real-model assertion in the gate (`test_landing_examples`) stops at plan→family mapping; the full pipeline tests all use `FakeProvider`, and e2e runs `--demo` (no model). The second is **printer connectors never make a real network round-trip** (mock-transport only — the hardware blind spot, partly #11). Neither is a shipped-broken feature; both are "the gate would not catch a regression here."

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

## What's working (credit where due)

- **The gate proves EXECUTION, not collection (no green-by-skip).** `scripts/ci.sh` line 61: under `KIMCAD_CI_STRICT=1` any `N skipped` on the provisioned runner fails the build; `.github/workflows/ci.yml` adds a dedicated step that re-runs `pytest -m live` and throws on `(\d+) skipped`. This is the exact control the b5 string-assert failure lacked. **This is the strongest part of the suite.** I confirmed it empirically: `pytest -m live` ran **110 passed, 0 skipped** in 15m14s on this box.
- **The slicer success criterion is real, not a string.** `slice_model` → `prove_gcode_3mf` (`src/kimcad/slicer.py:268`) opens the exported `.gcode.3mf` zip, requires ≥1 `.gcode` member and ≥1 G0/G1/G2/G3 motion command, with zip-bomb bounds. The live test (`tests/test_slicer.py:575`) asserts `line_count > 100`, `layer_count >= 90`, a parsed time estimate, and `filament_mm > 0` across 10 printers — a near-empty-toolpath profile regression breaches it.
- **The real LLM plan path IS run by the gate** — via `test_landing_examples.py` + STRICT. I confirmed qwen2.5:7b is pulled and the 6 cases pass with a real 156 s inference (not a mock). It stops at plan→family, but it is real and gated.
- **Persistence testing is adversarial and complete.** `test_history.py` / `test_design_store.py` / `test_settings_store.py` cover real-disk round-trips, corrupt/non-list/malformed-record degrade paths, unwritable-path best-effort, path-traversal rejection (`../etc`, separators), caps, AND a thread-safety-under-concurrency test with atomic write + lock.
- **Security boundaries are tested behaviorally.** CadQuery sanitizer escape classes (dunder, frame introspection, `str.format` pivot, attribute-pivot-to-os, banned imports) are blocked end-to-end through the real entry point; subprocess env-scrub for planted secrets is verified and single-sourced (`test_trust_boundary.py`). The CadQuery worker-sandbox RCE canaries are `live` and ran in the 110 (0-skip) live subset.
- **No institutionalized flakiness.** Zero `retries`/`reruns`/`pytest-rerunfailures` config anywhere; zero snapshot tests (no frozen-bug risk); only 5 short, justified `sleep`s (server-startup poll, pull simulation, concurrency). Frontend has **zero** `.skip`/`.only`/`xit`.
- **Restored UI has layered coverage.** FirstRunWizard: vitest unit tests (focus-trap a11y, unmount-safety/`disposedRef`, honest recap states, in-app pull progress) **and** a real-Chromium e2e walk-through (`tests/e2e/test_wizard.py`). SettingsPanel: 4-group section-nav, AI nav status dot, cloud opt-in + privacy copy that tracks the live backend, key masking (never raw), reversible Replace, units persistence, tool health.
- **The print path is e2e-proven through the UI.** `tests/e2e/test_export_gate.py` drives render (real OpenSCAD) → slice (real OrcaSlicer) → download in a real browser, including the gate-fail refusal branch, with a clean-console watcher on every journey.

## What couldn't be assessed

- **CI run history / flake rate over time** — I have the current green run and the gate design, but not historical CI logs to confirm zero retries-in-practice. The *design* forbids retries; I'm trusting that, having found no retry config.
- The full-catalog (`build_printer_catalog.py --verify`) all-29-printer live slice is a manual proof-of-record; I did not re-run all 29 (the gate doesn't either — see TEST-103).

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest 8 (+ pytest-playwright), vitest 4 (React Testing Library), Playwright 1.60 (headless Chromium) |
| Test pyramid shape | Bottom-heavy unit, with a **real** (not faked) integration/e2e layer driving actual binaries — healthy shape |
| Coverage tool | pytest-cov (`--cov=kimcad --cov-branch`) + diff-cover gate (changed lines ≥80% overall / ≥70% per module) on PR smoke |
| Reported coverage | Not pinned to a single % in repo; the meaningful gate is diff-coverage on changed lines, which is more honest than a headline number |
| Flakiness posture | Clean — no retry/rerun config; no snapshots; minimal, justified sleeps |
| CI blocking? | Yes, and hard. STRICT no-green-by-skip + live-subset re-run + SPA build-repro + pip-audit. Self-hosted on the target box (push/dispatch only, no fork-PR) |

---

## Findings

### [TEST-101] — Major — Coverage — The real LLM → SCAD → render → slice chain is never run end-to-end by any automated test

**Evidence**
- The only `@pytest.mark.live` tests are OrcaSlicer/CadQuery/OpenSCAD (`grep -rln "mark.live" tests/` → slicer, webapp, cadquery_*, config). **None** drives a real model.
- The full-pipeline tests (`tests/test_pipeline.py`, `test_pipeline_backends.py`) contain **no** `mark.live` and use `FakeProvider` (conftest.py:276) which returns a canned plan + canned SCAD.
- The one real-model test, `tests/test_landing_examples.py:56`, runs a real qwen plan but asserts only that `default_registry().match(plan)` is non-None — it stops at **plan → family**, never generating OpenSCAD, never rendering, never slicing the model's output.
- The e2e suite documents the gap itself: `tests/e2e/conftest.py:20` — *"the suite always runs `--demo`, so the LLM→plan path … [is] deliberately OUT of e2e scope."*
- The conftest claims "The real model path is covered by the unit/benchmark suites" — but `test_benchmark.py` tests the benchmark **harness** (scoring/grading) with stubs; it does not run a real model in the gate either.

**Why this matters**
The product's core promise is "describe a part → get a printable model." A regression where the real model produces a plan whose generated OpenSCAD fails to render, or renders to a non-watertight/un-sliceable mesh, would pass the entire automated gate: the plan→family check would still match, FakeProvider would still render its canned box, and demo mode would still slice its template part. This is precisely the b5 failure shape (a real path broken while a proxy assertion stays green) — narrower here because the *slicer* and *renderer* contracts ARE proven live, but the **model's own output flowing through them** is not.

**Blast radius**
- Adjacent code: `kimcad/pipeline.py`, `llm_provider.generate_openscad`, `openscad_runner`, `smart_mesh`/`hardening` (the model→geometry seam).
- Shared assumption: that a plan which maps to a family also yields buildable SCAD — untested for real model output.
- User-facing: the primary "design it" flow with a non-template prompt.
- Migration: none — additive test.
- Tests to update: none; add a new `@pytest.mark.live` pipeline test.
- Related findings: TEST-102 (the real-model test is misclassified, so STRICT, not the live-subset assertion, is its only guard).

**Fix path**
Add one `@pytest.mark.live` test in `test_pipeline.py` that runs the real `LLMProvider` (default backend) on 1–2 prompts through `plan → generate_openscad → render → prove the STL is watertight → slice → prove_gcode_3mf`. Mark it `live` so the live-subset re-run guards it explicitly (not just STRICT's skip-grep). Keep it to 1–2 prompts to bound wall-clock.

---

### [TEST-102] — Major — CI / Mocking — The only real-LLM gate test is unmarked `live`, so it's guarded only by a fragile skip-grep heuristic

**Evidence**
- `tests/test_landing_examples.py:56` `test_default_model_plans_each_landing_example_to_a_family` runs the real model but is **not** `@pytest.mark.live`. It guards itself with a runtime `pytest.skip(... "no Ollama lane — TEST-003")` (line 59).
- Therefore the gate's explicit live-contract step (`ci.yml:125`, which runs `pytest -m live` and throws on any skip) **does not see this test at all** (my 110-passed live subset did not include it).
- Its *only* protection against silently skipping (model not pulled → green-by-skip) is `ci.sh:61`: `grep -qE '[0-9]+ skipped'` under STRICT. That is a string-match on pytest's summary line — robust today, but it's the sole thread holding the real-LLM contract to the gate, and it lives in a different mechanism than every other live contract.

**Why this matters**
If `KIMCAD_CI_STRICT` is ever unset on the runner, or the model is unpulled, this test skips and the real-LLM coverage vanishes **silently and green** — the model-eval record shows the default model is a live, recently-changed decision (qwen2.5:7b), exactly the kind of thing a gate should pin. A single env-var regression converts the one real-model assertion into a no-op without turning the build red via the dedicated live mechanism.

**Blast radius**
- Adjacent code: `scripts/ci.sh` STRICT block; `.github/workflows/ci.yml` `KIMCAD_CI_STRICT` env.
- Shared assumption: that STRICT's skip-grep is always on — it's the only guard for this one test.
- User-facing: none directly; this is gate-integrity.
- Related findings: TEST-101 (same root: real-model coverage is thin and loosely wired).

**Fix path**
Either (a) mark the test `@pytest.mark.live` so it joins the explicit `pytest -m live … 0 skipped` contract (preferred — one mechanism for all live contracts), adding a small Ollama probe to ci.yml so its absence fails loudly rather than skips; or (b) add an `Assert the real-LLM contract ran` step mirroring the live-subset step. Today it passes (I verified 6/6, 156 s real inference), but the wiring should match its importance.

---

### [TEST-103] — Minor — Coverage — Only 10 of ~29 catalog printers get a live-slice in the gate; the rest get build-volume verification but not a sliceability proof

**Evidence**
- `tests/test_slicer.py:565` parametrizes the live slice over 10 printers (3 reference + 1 representative per curated vendor).
- The full all-printer × all-material live slice lives in `scripts/build_printer_catalog.py --verify` (`verify_slices`, line 286) — a **manual** catalog-build tool, not invoked by `ci.sh` or any workflow (`grep -rn build_printer_catalog` → only doc references in tests).
- Mitigation found: `tests/test_config.py:206` (`test_configured_build_volumes_match_the_shipped_orca_profiles`, `real_tool`-gated) iterates **all** configured printers (`cfg.raw["printers"]`, `checked >= 25`) and verifies each build_volume against its shipped Orca machine profile chain.

**Why this matters**
Build-volume match ≠ sliceability. A profile-format or inherits-chain regression that breaks slicing for one of the 19 un-sampled printers (e.g., a renamed process profile) would pass the gate; only the manual `--verify` would catch it. Low exposure (profiles are vendor-stable), but it's a real gap between "the gate proves it" and "a human remembered to run `--verify`."

**Fix path**
Either run a thin all-printer live slice in the gate (gated by a longer timeout budget), or document `build_printer_catalog.py --verify` as a required step on any profile/catalog edit and add a hygiene test asserting the recorded proof-of-record timestamp is newer than the catalog YAML's mtime.

---

### [TEST-104] — Minor — Coverage — Printer connectors are tested only against a mocked transport; no real (or recorded) network round-trip to any printer

**Evidence**
- Every connector test (`test_bambu_connector.py`, `test_octoprint_connector.py`, `test_prusalink_connector.py`, `test_moonraker_connector.py`, `test_duet_connector.py`, `test_marlin_connector.py`) mocks the transport. No VCR/cassette/recorded fixtures (`grep -rln "vcr|cassette|betamax"` → none for connectors).
- The connectors self-report `drives_hardware is True` (e.g. `test_bambu_connector.py:426`) yet no test exercises a real socket/HTTP/MQTT/FTPS exchange. Marlin's real serial path is explicitly "metal-only (#11)" (`test_marlin_connector.py:6`).

**Why this matters**
The connector unit tests are genuinely good at the **state machine** (TOCTOU re-check after upload, fail-closed on unknown/failed state, multi-plate/zero-plate/motionless-file refusal, auth-vs-generic error mapping). But the actual wire contract — does this firmware accept this exact upload+start sequence — is unproven by any automated test. A field-reported "send fails on real printer X" class of bug has no regression net.

**Fix path**
Record HTTP/MQTT cassettes from one real printer per protocol family (OctoPrint/Moonraker/PrusaLink/Duet are HTTP — VCR-friendly) and replay them as integration tests. Bambu MQTT + Marlin serial legitimately need hardware (#11); document them as the accepted hardware blind spot rather than implying the mocked tests cover the wire.

---

### [TEST-105] — Minor — Quality — A restored-UI test asserts a model name that the test itself supplies via the mock, and that disagrees with the real default

**Evidence**
- `frontend/src/components/FirstRunWizard.test.tsx:47` — *"shows gemma4:e4b as THE design model"* — but the mock (`vi.mock('../api')`, line 17) returns `getModelStatus → { model: 'gemma4:e4b' }`. The component renders whatever the API returns, so the assertion would pass identically for any string.
- The real default is `qwen2.5:7b` (`src/kimcad/config.py:77` `DEFAULT_CHAT_MODEL`), and the component's own fallback is `qwen2.5:7b` (`FirstRunWizard.tsx:308,590`). The component comment (line 20) also says "the model is gemma4:e4b" — stale.

**Why this matters**
This is the "mock returns the value the test asserts" smell. The test verifies display plumbing (good) but its name implies it pins the product's design model — it does not. The component's real fallback (`qwen2.5:7b`, the path when the API is unreachable) is never exercised because the mock always supplies a value. A reader trusting the test name would believe the design model is gemma4:e4b, which is wrong.

**Fix path**
Rename the test to reflect what it checks ("renders the design model returned by the API with its health"), update the stale `gemma4:e4b` comment in `FirstRunWizard.tsx:20` to `qwen2.5:7b`, and add one case that mocks `getModelStatus` rejecting (or omitting `model`) to exercise the real `qwen2.5:7b` fallback literal.

---

### [TEST-106] — Nit — Ergonomics — Orphaned bytecode + a stale `build/` tree carry the withdrawn Snapmaker code

**Evidence**
- `src/kimcad/__pycache__/snapmaker_connector.cpython-313.pyc` and `tests/__pycache__/test_snapmaker_connector.cpython-313-pytest-9.0.3.pyc` exist with **no** corresponding source (both `.py` were reverted with the b5/b6 withdrawal, `c8e9f44`).
- `build/lib/kimcad/snapmaker_connector.py` (full withdrawn source) survives in the gitignored `build/` setuptools tree (49 `.py` files total).

**Why this matters**
Harmless to the gate and the shipped wheel (both are gitignored / not collected without source), but it's exactly the "digital trash, clean up as you go" the project standard calls out, and stale `build/lib` source can mislead a future sdist build or a grep-based audit.

**Fix path**
`rm -rf build/` and prune orphaned `__pycache__` (or add a `make clean` / hygiene-test that fails when a `*.pyc` has no sibling source).

---

### [TEST-107] — Nit — Quality — `test_default_model` Ollama probe is `lru_cache`d per session, masking a model that disappears mid-run

**Evidence**
- `tests/test_landing_examples.py:43` `@functools.lru_cache(maxsize=1)` on `_default_model()`. Fine for a single run, but if the gate ever interleaves a model-pull/remove test in the same process, the cached "pulled" verdict could go stale.

**Why this matters**
Purely theoretical today (the suite doesn't remove the default model mid-run). Flagged once for completeness; not worth action unless model-lifecycle tests are added to the same process.

---

## My independent real-tool proof (no-false-greens verification)

I did not trust the suite's claims. I ran the real tools myself.

**1. Independent real OrcaSlicer slice end-to-end** (distinctive 23×17×11 mm box so it cannot be a cached suite artifact), via `from kimcad.slicer import slice_model, prove_gcode_3mf`:

```
OrcaSlicer binary: …\tools\orcaslicer\orca-slicer.exe exists=True
machine=Bambu Lab P2S 0.4 nozzle.json process=0.20mm Standard @BBL P2S.json filament=Bambu PLA Basic @BBL P2S.json
Wrote mesh: …\auditbox.stl (684 bytes)
=== SLICE RESULT ===
gcode_path: …\auditbox.gcode.3mf  exists=True  size=59431 bytes
duration_s: 1.6
has_motion: True
line_count: 10987
gcode members: ('Metadata/plate_1.gcode',)
estimated_time: 6m 34s
layer_count: 55
filament_mm: 773.84
=== INDEPENDENT RE-PROVE FROM DISK ===
has_motion=True line_count=10987 layers=55 time=6m 34s
PROOF OK
```

Real motion-bearing G-code (10,987 lines, 55 layers), proven by opening the actual zip — not a string assertion.

**2. Real qwen2.5:7b → plan path** (`pytest tests/test_landing_examples.py`):
`6 passed in 156.04s` — a genuine ~156 s local inference, 0 skipped. The default model IS pulled (`ollama list` → qwen2.5:7b, 4.7 GB) and the real model+matcher+wording chain connects.

**3. Full vitest suite** (`npm --prefix frontend run test`):
`Test Files 32 passed (32) / Tests 396 passed (396)` — matches the claim.

**4. Full live pytest subset** (`pytest -m live -ra`):
`110 passed, 1490 deselected in 914.05s (0:15:14)` — **0 skipped**, exit 0. The complete real-tool contract (the 10-printer OrcaSlicer slice matrix, the CadQuery worker-sandbox RCE canaries, OpenSCAD-real renders) executes and passes with no green-by-skip. This is the empirical proof that the gate's STRICT + live-subset machinery is not theater.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `@pytest.mark.skip` (unconditional) | 0 |
| `@pytest.mark.skipif` (env-gated, justified) | ~28 (all binary/interpreter/profile/OS-gated; STRICT fails the gate if any fire on the provisioned box) |
| runtime `pytest.skip()` | 7 (5 in conftest marker-routing; 1 manifold; 1 the real-LLM landing test — TEST-102) |
| `@pytest.mark.xfail` | 0 (the one grep hit is a comment explaining why xfail was *not* used) |
| `.only` / `.skip` / `xit` (frontend) | 0 |
| `assert True` / placeholder | 0 |
| `TODO: add test` / `FIXME: test` | 0 |
| `--retry` / `reruns` / flaky-retry config | None (not institutionalized) |
| snapshot tests | 0 |

The skip story here is the good kind: every skip is environment-routing with an explicit marker, and the gate's STRICT mode + live-subset re-run convert any skip on the provisioned box into a red build. This is the single most important thing the b5 failure was missing.

## Blind spots by class

- **Real-model output flowing through render+slice** — untested end-to-end (TEST-101). The highest-leverage gap.
- **Real printer wire contracts** — mock-only; no recorded or hardware round-trip (TEST-104).
- **Un-sampled catalog printers' sliceability** — build-volume verified, slice not gate-proven (TEST-103).
- **Real `qwen2.5:7b` fallback literal in the wizard** — never hit because the mock always supplies a model (TEST-105).
- Empty/boundary/concurrency/corruption for persistence and the slicer/proof path — **well covered** (not a blind spot; credited above).

## Patterns and systemic observations

- **Fail-closed gate culture is the defining pattern, and it's good.** STRICT-no-skip, live-subset re-run, `prove_gcode_3mf` instead of a string assert, SPA build-reproducibility, pip-audit, diff-coverage on changed lines. The team clearly internalized the b5 lesson and built machinery so it can't recur the same way — and the 110-passed/0-skipped live run proves the machinery is live, not aspirational.
- **Regression-test-with-fix discipline is visible.** Findings are encoded as named tests (QA-504 arrange-message, ENG-003 cache, TEST-1001 disposedRef unmount, KC-7 build-volume). Bugs come back as tests.
- **The one soft spot is the real-model lane.** It exists (landing-examples) but is thin and loosely wired (unmarked `live`, lru-cached probe, stops at the plan). The same root underlies TEST-101/102/105. Tightening that lane — one live pipeline test + marking the existing real-LLM test `live` — would close the most meaningful remaining gap and align the real-model contract with the (excellent) machinery already protecting the slicer.

## Appendix: test artifacts reviewed

`tests/conftest.py`, `tests/test_slicer.py`, `tests/test_landing_examples.py`, `tests/test_llm_provider.py`, `tests/test_pipeline.py`, `tests/test_benchmark.py`, `tests/test_bakeoff.py`, `tests/test_webapp.py` (live web path), `tests/test_trust_boundary.py`, `tests/test_cadquery_runner.py`, `tests/test_history.py` / `test_design_store.py` / `test_settings_store.py`, `tests/test_printer_catalog.py`, `tests/test_config.py` (KC-7), `tests/test_bambu_connector.py` + connector suite, `tests/test_cli.py`, `tests/test_build_installer.py`, `tests/test_project_hygiene.py`; `tests/e2e/conftest.py`, `test_smoke.py`, `test_wizard.py`, `test_design_refine.py`, `test_export_gate.py`; `frontend/src/components/FirstRunWizard.test.tsx`, `SettingsPanel.test.tsx`; `.github/workflows/ci.yml` + `pr-smoke.yml`, `scripts/ci.sh`, `.githooks/pre-push`, `pyproject.toml`. Tools exercised live: OrcaSlicer (`tools/orcaslicer/orca-slicer.exe`), Ollama qwen2.5:7b, vitest, the full live pytest subset (110 tests).
