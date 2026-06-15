# Test Suite Deep-Dive — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Role:** Test Engineer
**Scope audited:** Full repo. `tests/` (66 pytest files, ~18 kLOC, incl. `tests/e2e/` Playwright-over-pytest suite and the `mock_*` HTTP oracles in `src/kimcad/`), `frontend/src/**/*.test.ts(x)` (32 vitest files), the gate `scripts/ci.sh`, `tests/conftest.py`, `tests/e2e/conftest.py`, and `pyproject.toml` marker/config.
**Auditor posture:** Balanced

---

## TL;DR

This is a large, disciplined, genuinely adversarial suite — among the best I have audited at this size. The connector mocks are conformance oracles, not rubber stamps (session-exhaustion, completion-state reset, password-never-leaks, malicious-job-name sanitization are all exercised); the session-token guard is tested for the true 403/200 contract on both client and server; the shortcut census is clean (zero `.only`, zero `xfail`, zero unconditional skips, zero retry/rerun config). The gate is strict and self-aware — it converts "skipped on a provisioned box" into a hard failure and hard-fails a release when the live-tool contracts go unproven. **The one structural blind spot is the demo-vs-real divide for the LLM:** *no automated test ever invokes a real Ollama model*, and the e2e suite runs exclusively in `--demo`, where `DemoProvider.generate_design_plan` ignores the prompt and returns a fixed 80×60×40 box. So the suite proves the entire pipeline *plumbing* end-to-end but provides **zero signal on the default model's planning quality** — the exact class of failure a real-model walkthrough just found (gemma4:e4b failing 2 of 3 of the landing page's own example prompts). The `kimcad bench` harness that *would* catch this is fully built and unit-tested for its grading logic, but is not wired into CI and its prompt set diverges from the landing examples. A secondary, verified blind spot: `test_version_single_source` does not scan the README, which currently ships the wrong version.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 2 |
| Minor | 4 |
| Nit | 2 |

## What's working

- **The connector mocks are adversarial conformance oracles, not happy-path stubs.** `src/kimcad/mock_duet.py` models a finite RRF session table (`session_cap`, `err 2` when full), advances `fractionPrinted` per type-3 poll, and faithfully *resets* `fraction=0.0` + returns to idle `"I"` on completion (`mock_duet.py:27-31`) — which is what lets `test_done_is_latched_after_progress_then_idle` (`test_duet_connector.py:265-278`) prove the connector's completion *latch* instead of trusting a progress number. The 403-auth path (`mock_duet.py:62-70`), the 413 body cap with a bounded drain (`:122-134`), and a wrong/missing-password→`AuthError` distinction are all real (`test_duet_connector.py:119-143`). `test_session_is_released_so_repeated_polls_never_exhaust` (`:211-222`) asserts `state["sessions"]==0` and `max_sessions_seen<=1` — green is *earned*.
- **The session-token guard IS tested for the true 403/200 contract — on both sides.** Server: `test_webapp.py:560-598` asserts a tokenless POST is 403 across six representative routes (plain, path-prefixed, upload), a *wrong* token is 403, and the *correct* token routes through to a positive **200** (not merely `!= 403`), plus GETs are never gated and the no-token default leaves the guard off (`:621-632`). Client: `frontend/src/api.session-token.test.ts` proves the header is stamped across three POST shapes, omitted for the dev placeholder, and that a `403 reason:"session"` throws `SessionExpiredError` *and* fires the recovery handler while a plain 403 stays an ordinary error (`:78-108`). The prompt's worry that this is "only tested when-absent" does not hold — both directions of the contract are covered.
- **The benchmark *grading* logic is rigorously tested for the right failure modes.** `test_benchmark.py` includes the BENCH-001 regression (`:184-187`: a grossly undersized part that fits the ceiling must NOT grade as a dimensional pass) and the "ceiling-only is unassessed" distinction (`:178-181`) — these are exactly the ways a naive grader would lie. The 3-axis rollup (matches-request / correct-dimensions / slices-clean) is thoroughly exercised.
- **The gate is honest about its own skips.** `scripts/ci.sh:61-66` (STRICT mode) turns any skip on a provisioned runner into a hard red; `:122-149` hard-fails a *release* when the OrcaSlicer or CadQuery live contracts couldn't run. `conftest.py:169-189` collapses a degraded geometry backend into one actionable line locally but raises `UsageError` under CI. This is mature "no green by skip" engineering.
- **e2e is real, not simulated, and watches the console.** `tests/e2e/conftest.py` spawns a real `kimcad web --demo` subprocess on a free port, drives real Chromium, and the `console_errors` fixture (`:165-180`) fails a journey on any non-benign console error or pageerror — so a silently-swallowed broken API call is caught. Server startup has a 45s deadline with a captured log tail (`:135-153`), and the process is reaped on teardown (`:155-162`).
- **Clean flakiness posture.** No `--reruns`, no `retries:`, no `flaky` anywhere in `pyproject.toml`, vitest config, or `package.json`. Flakiness has not been institutionalized. The e2e box-throttling problem is handled with *generous explicit timeouts* (`conftest.py design` fixture, 30s render wait) rather than retries — the right call.
- **Hermeticity is enforced suite-wide.** Autouse fixtures isolate `~/.kimcad` per test (`conftest.py:210-226`), stub the OS keyring in-memory (`:253-262`), and default CadQuery discovery to "nothing found" (`:191-207`) so machine state never leaks into results.

## What couldn't be assessed

- **Real-model planning quality** — by design, nothing in the gate invokes Ollama, so I could not (and the suite cannot) observe gemma4:e4b's output on any prompt. This is the subject of TEST-001 below; it is the blind spot, not a tooling limitation on my end.
- **CI run history / flake rate over time** — this is a self-hosted single-box gate with no accessible historical run database; I assessed determinism by reading config (clean) rather than from a flake dashboard.
- **Mutation score** — no mutation-testing tool (mutmut/Stryker) is configured, so the "do the assertions actually pin behavior" question was answered by reading assertions, not by a mutation run. The assertions I read are strong; a mutation pass would quantify it.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (backend + e2e via pytest-playwright), vitest + Testing Library (frontend) |
| Test pyramid shape | Bottom-heavy and healthy: deep unit/component coverage, a solid integration tier (real `mock_*` HTTP servers, real OpenSCAD/OrcaSlicer/CadQuery under markers), and a thin-but-real e2e cap (21 browser journeys). The one missing layer is a *model-quality* tier (see TEST-001). |
| Coverage tool | `coverage.py` via a diff-coverage gate (`scripts/check_diff_coverage.py`, ≥80% overall / ≥70% per changed module), enforced on PRs (`pr-smoke.yml`), itself unit-tested (`test_check_diff_coverage.py`). No whole-repo % is published — appropriately, since a number would mislead. |
| Reported coverage | None published as a headline number. The diff gate is the operative metric — a good choice that avoids the "80% line coverage" trap. |
| Flakiness posture | Clean. No retry/rerun config anywhere. e2e uses explicit timeouts + a serialization lock, not retries. |
| CI blocking? | Yes, and strictly. `ci.sh` is the authoritative pre-push gate (pre-push hook) and the self-hosted Actions runner; STRICT mode + release-mode hard-fails close the "green by skip" loophole. |

---

## Findings

> **Finding ID prefix:** `TEST-`
> **Categories:** Coverage / Shortcut / Flakiness / Quality / Ergonomics / Mocking / Regression / CI

### [TEST-001] — Critical — Coverage — Nothing in the gate exercises the real model; the e2e suite runs in `--demo`, so default-model planning quality is unverified

**Evidence**
- No automated test invokes a real Ollama model. The `live` marker is scoped to the OrcaSlicer binary only (`pyproject.toml:90`), not to Ollama. Every LLM test stubs the chat client: `test_llm_provider.py:33-45` (`FakeChatClient` returns canned content), and `conftest.py`'s `FakeProvider` (`:276-305`) returns a fixed plan. Grepping the suite for a real-model invocation returns nothing — the model path is mocked everywhere.
- The e2e suite is hard-wired to `--demo`: `tests/e2e/conftest.py:119-126` always launches `kimcad ... web ... --demo`, and the module docstring states the LLM→plan path is "deliberately OUT of e2e scope" (`:20-23`).
- In demo mode the plan is canned regardless of the prompt: `webapp.py:DemoProvider.generate_design_plan` (`:317-340`) lowercases the prompt only to detect the `demo:gatefail` / `demo:experimental` keywords, and otherwise returns a fixed `object_type="box"`, `bounding_box_mm=[80,60,40]`. So when `test_export_gate.py:21` submits the landing example **"a 40 mm desk cable clip"**, the SPA renders an 80×60×40 box, not a clip — the journey passes on plumbing, says nothing about planning.
- The harness that *would* catch this, `kimcad bench`, is **not wired into CI** — no reference to `kimcad bench` / `--min-success-rate` / `run_benchmark` in `.github/workflows/` or `scripts/ci.sh`. Its grading logic is unit-tested with `FakePipeline` (`test_benchmark.py:103-350`), but those tests never run a model either.
- The landing examples and the bench set diverge. Landing (`frontend/src/components/Landing.tsx:9-13`): *"a wall-mounted holder for a 1 kg filament spool"*, *"a 40 mm desk cable clip"*, *"a hexagonal pen and tool organizer"*. The bench set (`bench/prompts.yaml`) carries a much more verbose cable-clip (`b05`) and a spool holder (`b08`) but **no hexagonal pen organizer at all** — so even a manual `kimcad bench` run does not test the third landing chip, and the two terse chips are not tested verbatim.

**Why this matters**
The real-model walkthrough found gemma4:e4b (the default local model) fails 2 of 3 of the landing page's own try-prompts. The landing page is the product's first impression and it *advertises* those exact prompts as one-click examples. The entire automated gate — 66 pytest files, 21 e2e journeys, a strict release gate — can be fully green while the default model produces a wrong or non-printable part for the prompts the UI tells first-time users to click. This is the canonical demo-vs-real divide: the suite tests everything *around* the model and nothing *of* it. The class of bug that slips through is "model regression / model swap silently degrades planning quality on first-run prompts" — invisible to CI, maximally visible to a new user.

**Blast radius**
- Test files affected: a new model-quality tier is needed; it would live alongside `test_bench_prompts.py` (structure-only today) and the `bench/` harness.
- Shared state: `bench/prompts.yaml` is the single prompt source; aligning it with `Landing.tsx:9-13` (esp. adding the hexagonal pen organizer) is a one-file change but couples two surfaces that currently drift independently.
- User-facing: directly governs first-run success rate — the activation metric.
- Migration: none. Additive — a new gated job and an aligned prompt case.
- Tests to update: none break; this is net-new coverage. The e2e suite legitimately stays in `--demo` (fast, deterministic plumbing checks) — the fix is a *separate* model tier, not changing e2e.
- Related findings: walkthrough/QA findings on the landing examples; DOC findings if the README/landing copy promises prompts the model can't yet satisfy.

**Fix path**
Two complementary moves, neither blocks the b2 tag but both belong this sprint:
1. **Add the landing examples verbatim to `bench/prompts.yaml`** (add a `b11` hexagonal pen-and-tool organizer with a sensible `max_bbox_mm`; ensure the terse clip/holder chips appear as their own cases) so the done-gate set is a superset of what the UI advertises.
2. **Wire a nightly (not per-push) `kimcad bench --min-success-rate 0.8 --slice` job** against the real default model on the self-hosted box, publishing the 3-axis rollup. Keep it off the blocking per-push gate (a CPU-bound model run would make the gate unusable) but make it a visible, alerting signal so a model regression can't reach a release silently. Until that lands, document explicitly (CHANGELOG/release notes) that model-quality is verified manually, not by CI — so a green gate is never mistaken for "the examples work."

---

### [TEST-002] — Major — Coverage — `test_version_single_source` does not pin the README (or CHANGELOG); the suite is green while the README ships the wrong version

**Evidence**
- `pyproject.toml` declares `version = "0.9.0b2"` (verified). `README.md` still shows `0.9.0b1` in **4 user-facing places** — the beta badge, the download CTA, and two prose lines (`README.md:5,14,30,63`).
- `test_version_single_source.py:32-40` (`test_no_source_file_carries_a_version_literal`) scans **only** `src/kimcad/**/*.py` and `frontend/src/**/*.ts*`. `test_installer_scripts_take_the_version_as_a_parameter` (`:61-70`) covers `installer/**/*.iss`. Nothing scans `README.md` or `CHANGELOG.md`.
- I ran the test to confirm the gap is live: `.venv/Scripts/python -m pytest tests/test_version_single_source.py -q` → **6 passed in 0.85s**, with the stale `0.9.0b1` README present. The "single source" tripwire does not fire on the most-read file in the repo.
- The installer build script *does* read pyproject (`scripts/build_installer.py:75-78`, `_version()`), so the shipped `.exe` name is correct — the gap is specifically the human-facing docs, which the test's own docstring implies are covered ("Every surface reads `kimcad.__version__`") but are not.

**Why this matters**
This is the textbook "static value in a file the test doesn't check" lie (test-engineer reference #1). The test's *name* and docstring assert "single source / every surface," and a reader (and the prior 11.3 audit it cites) trusts that claim — but the README, the file a GitHub visitor and a downloading beta tester see first, displays the *previous* version's badge and download label at the moment a `0.9.0b2` release is cut. A user downloads "0.9.0b1" per the README and gets a 0.9.0b2 binary, or worse, distrusts the page. The class of bug: user-facing version drift that the version *tripwire* specifically exists to prevent, sailing through green.

**Blast radius**
- Test files affected: `test_version_single_source.py` — extend `test_no_source_file_carries_a_version_literal` (or add a sibling) to scan `README.md` and the CHANGELOG's "Unreleased/current" header against the declared version, allowing historical version mentions only under dated `## [x.y.z]` sections.
- Shared state: the declared version in `pyproject.toml` is already the single source; this finding is purely about which *consumers* are pinned.
- User-facing: the README badge/CTA — the download funnel. Directly affects the b2 release's first impression.
- Migration: none. The fix is a test extension plus the one-time README correction.
- Tests to update: none break; the extended test would (correctly) go red until the README is corrected to `0.9.0b2`.
- Related findings: DOC findings on README freshness; this finding makes that drift *enforceable* rather than a manual checklist item.

**Fix path**
Correct the four `README.md` literals to `0.9.0b2` now (release blocker for the *docs*, not the code), then extend the test to scan `README.md` (and the CHANGELOG's current-release header) so the next bump can't reintroduce the drift. Match the existing approach: compare against `_declared()`, allow dated historical headings.

---

### [TEST-003] — Major — Coverage — Real-model error/retry contract is asserted only against mocks; the live failure surfaces (Ollama down, cold-pull, OOM, 404 vision) are never exercised end-to-end

**Evidence**
- The provider's error handling is well unit-tested *against fakes*: `test_llm_provider.py` covers a transient `APIConnectionError` retry (`:198-201`, explicitly "hermetic regardless of whether a real Ollama is running"), a 404 vision model → `ollama pull` recovery hint (`:306-322`), and a 5xx/429 not masquerading as missing (`:327+`). These prove the *translation* logic given a simulated response.
- But the real first-run failure modes — Ollama not installed, model not yet pulled (cold first run), model OOM/timeout on a low-RAM box, the vision model's "thinking-mode eats the whole token budget so vision returns empty" pathology that `llm_provider.py:357,382-384` documents in prose — are never exercised against a real Ollama. The `test_first_run_errors.py` and `test_model_pull.py` suites also mock the HTTP layer.

**Why this matters**
First-run is the highest-risk moment for a local-LLM desktop app: the model is multi-GB, the pull is slow, and low-RAM machines OOM. The suite proves "if Ollama returns shape X, we react with message Y" but not "Ollama actually returns shape X under these conditions." A change in Ollama's error JSON, status codes, or the gemma4 thinking-mode behavior would pass every mock-based test and break the real recovery UX. This is the integration-test-in-disguise smell (reference #8): real modules, mocked integration point.

**Blast radius**
- Test files affected: `test_llm_provider.py`, `test_first_run_errors.py`, `test_model_pull.py` — candidates for a small `live`-gated companion tier that hits a real local Ollama when present and skips cleanly otherwise (mirroring the OrcaSlicer/CadQuery pattern already in `ci.sh`).
- Shared state: the Ollama base URL / model tags in config; the model_advisor catalog.
- User-facing: first-run setup, model-health pill, the cold-pull progress flow.
- Migration: none — additive, marker-gated.
- Related findings: TEST-001 (same root: the real model is never touched by CI). A single "live-Ollama, nightly, non-blocking" tier could host both TEST-001's planning-quality cases and TEST-003's error-surface cases.

**Fix path**
Add an `ollama`/`live`-marked tier that, when a local Ollama with the default model is discoverable, asserts the real error surfaces (kill the daemon → expect the "Ollama down" recovery; request an un-pulled model → expect the pull-hint). Gate it like the existing live contracts in `ci.sh` (warn always, hard-fail on release). Keep it off the blocking per-push gate.

---

### [TEST-004] — Minor — Mocking — Marlin/Bambu/Moonraker/PrusaLink mocks not re-verified to the Duet bar in this pass; assumed parity flagged for spot-confirmation

**Evidence**
- I read `mock_duet.py` and `test_duet_connector.py` in full and found them exemplary (session-cap, completion reset, sanitization, password-leak guard). I did **not** read every line of `mock_marlin.py`, `mock_moonraker.py`, `mock_prusalink.py`, `mock_printer.py` and their test files in this pass; the connectors share a base (`printer_connector.py`) and the recent KC-21 audit-lite reports (`audit-lite-kc21-duet-connector-slice1`, `...-marlin-connector-slice2`) indicate the same adversarial pattern was applied per connector.
- The Bambu connector (`test_bambu_connector.py`) uses a different transport (MQTT/FTP-style) than the Duet HTTP mock, so its mock's adversarial depth (auth/LAN-mode, completion-state) warrants a direct read it didn't get here.

**Why this matters**
Connector parity is assumed, not verified, for 4 of 5 connectors in *this* pass. If one mock is less adversarial than Duet's — e.g. doesn't reset completion state, or doesn't model auth failure — its green is worth less than Duet's, and a real hardware regression could slip for that brand. This is a Minor because prior KC-21 audits cover the gap and the shared base limits divergence; it is logged so the assumption is explicit.

**Fix path**
Spot-confirm that each non-Duet mock models: (a) completion-state reset/latch, (b) an auth-failure path distinct from offline, (c) a malformed-200 → error-status (not raise). If any is missing, raise it to Major for that connector. (Out of scope to fully re-verify here; flagged for the QA pass or a follow-up.)

---

### [TEST-005] — Minor — Coverage — e2e `browser_serial` lock does not serialize across xdist workers; a future parallel run could race the one shared server

**Evidence**
- `tests/e2e/conftest.py:62-71` implements `_BROWSER_SERIAL_LOCK` as an in-process `threading.Lock`, and the docstring is candid that it "does NOT serialize across xdist workers — see the marker note" and "requires SINGLE-PROCESS runs." The session-scoped `live_server` (`:90-104`) is one shared server with server-side state persisting across journeys.

**Why this matters**
Today the suite runs single-process, so this is inert. But the moment someone adds `-n auto` to speed the gate (a natural optimization on the throttling box), the lock silently stops serializing, multiple workers hit one stateful server, and the design/settings journeys race — producing exactly the flaky-then-retry culture the suite has so far avoided. It's a latent trap, correctly documented but not enforced.

**Fix path**
Either enforce single-process for the e2e package (e.g. a `-p no:xdist` marker or a conftest guard that errors if `workerinput` is present on a `browser_serial` test), or make `live_server` worker-scoped with a per-worker port. A guard that fails loudly under xdist is the cheaper, safer option.

---

### [TEST-006] — Minor — Coverage — `DemoProvider` keyword scenarios (`demo:gatefail`/`demo:experimental`) are the only adversarial demo paths; the demo's fixed box masks pipeline behavior on real geometry variety

**Evidence**
- `webapp.py:DemoProvider` (`:317-350`) emits a fixed `snap_box` for all non-keyword prompts and only branches to an oversized cube on `demo:gatefail`. The e2e gate-pass journey (`test_export_gate.py:20-33`) therefore always slices the *same small box* regardless of prompt — so it proves "a box slices" but not "the slicer/gate handle a tall thin part, a part near build-volume limits, a multi-body part."

**Why this matters**
The e2e print-path coverage is one geometry shape wide. Real parts that stress the orient/gate/slice stages (tall aspect ratios, parts that need support, parts near the plate edge) are not represented in demo, so an orientation or slice regression on a non-box shape wouldn't surface in e2e. The unit/template suites cover geometry variety, but the *integrated* SPA→slice path sees one shape.

**Fix path**
Add 1–2 more `demo:` keyword scenarios that emit a tall/thin part and a near-build-volume part (still deterministic, template-rendered) so the e2e export journey exercises the gate/orient/slice path on more than a small box. Low cost, meaningfully widens the integrated coverage.

---

### [TEST-007] — Nit — Ergonomics — `test_webapp.py` is a 3,590-line single file

**Evidence**
- `wc -l tests/test_webapp.py` → 3590 lines in one module.

**Why this matters**
Purely ergonomic — a new contributor navigating the webapp tests faces one enormous file; targeted runs still work (`pytest tests/test_webapp.py::test_x`), so this is not a coverage or correctness issue. Logged once.

**Fix path**
Optional: split by concern (session-token, slice, render, send, options) into `tests/webapp/`. No urgency.

---

### [TEST-008] — Nit — Quality — Frontend assertions lean on `toBeTruthy()` where a more specific matcher would document intent

**Evidence**
- e.g. `App.test.tsx:223,226,507` use `expect(await screen.findByText(...)).toBeTruthy()`. These are *not* false-positive risks — `findByText`/`getByLabelText` throw if the element is absent, so the query itself is the assertion — but `toBeTruthy()` on an always-truthy element node reads as a weaker assertion than it is.

**Why this matters**
No behavior risk; the queries fail correctly. Purely a readability/intent nit — `toBeInTheDocument()` (jest-dom) or asserting on content would document the contract more clearly. Flagged once, not per occurrence.

**Fix path**
Optional: prefer `toBeInTheDocument()` / content assertions over `toBeTruthy()` on query results. Style preference, not a defect.

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@pytest.mark.skip` (unconditional) | 0 |
| `@pytest.mark.skipif` (conditional, all with clear env reasons) | ~26 (legitimate: binary/interpreter/manifold absent) |
| `.only` (left in) | 0 |
| `@pytest.mark.xfail` | 0 |
| `TODO: add test` / `FIXME: test` | 0 |
| Empty assertion / `assert True` placeholder | 0 |
| `--reruns` / `retries` / `flaky` normalized | No (none anywhere) |

This is a clean census. Every skip is a `skipif` gated on a *missing environment capability* (OpenSCAD/OrcaSlicer binary, CadQuery interpreter, manifold3d, Chromium), each with an explicit reason string, and the gate's STRICT mode converts those skips to hard failures on the provisioned box (`ci.sh:61-66`). There is no shortcut culture here.

## Blind spots by class

- **Model-quality / LLM regression (the big one).** No real-model invocation in CI; e2e is demo-only with a fixed plan. A model swap or thinking-mode regression that degrades planning on the landing examples is invisible to the gate. (TEST-001, TEST-003.)
- **User-facing version drift in docs.** README/CHANGELOG version literals are outside the "single source" tripwire; the README currently ships the wrong version with a green suite. (TEST-002.)
- **Geometry variety in the integrated print path.** e2e slices one box shape; tall/thin/multi-body/near-limit parts are unit-tested but not integration-tested through the SPA. (TEST-006.)
- **Cross-connector mock parity (assumed, not re-verified here).** Duet's mock is exemplary; the other four are assumed equivalent on the strength of shared base + prior KC-21 audits. (TEST-004.)
- **Parallel-run safety of e2e.** The serialization lock is single-process only; a future `-n auto` would race. (TEST-005.)

Notably *covered* (not blind spots): auth-boundary crossing (session token, cross-site STEP GET), malformed input (garbage-200 bodies, non-object JSON, malicious job names), credential leakage (password-never-in-error), completion-state edge cases (RRF idle-reset latch), empty/error states (offline, 5xx, 404-vision).

## Patterns and systemic observations

- **Findings are encoded into the tests as live tripwires.** Prior-audit IDs (ENG-001, TEST-001..004, QA-001/002, BENCH-001, KC-16/20/21/22/26) appear as inline comments tied to specific regression assertions. This is a healthy "tests-with-fixes" culture — bugs come back with a guard. (severity-framework: credit good regression posture.)
- **The gate is self-aware about its own lies.** `ci.sh` explicitly defends against tee-masking-exit-code, skip-as-false-green, and additive-untracked build drift — each with a comment naming the real incident it prevents (e.g. the 2026-06-13 pipe-masking near-miss). This is rare and worth crediting in the exec report.
- **The single structural weakness is intentional and documented, not accidental.** The team *chose* demo-only e2e for determinism (`e2e/conftest.py:20-23`) and built `kimcad bench` for model quality — they just haven't wired bench into an automated signal or aligned its prompts with the landing chips. The fix is integration, not invention.

## Appendix: test artifacts reviewed

- **Config / gate:** `scripts/ci.sh`, `pyproject.toml` ([tool.pytest.ini_options] markers + config), `scripts/check_diff_coverage.py` (read via `test_check_diff_coverage.py`), `scripts/build_installer.py` (`_version()`).
- **Fixtures:** `tests/conftest.py` (full), `tests/e2e/conftest.py` (full).
- **Backend tests (read in full or substantively):** `test_version_single_source.py`, `test_benchmark.py`, `test_bench_prompts.py`, `test_llm_provider.py` (header + error sections), `test_duet_connector.py`, `test_webapp.py` (session-token + cross-site sections).
- **Mocks:** `src/kimcad/mock_duet.py` (full); `mock_marlin/moonraker/prusalink/printer.py` (presence + base pattern, not line-by-line — see TEST-004).
- **e2e journeys:** `test_export_gate.py` (full), `test_smoke.py`/`test_wizard.py`/`test_design_refine.py`/`test_onramps.py`/`test_settings_designs.py`/`test_print_versions_mobile.py` (counts + harness coupling).
- **Frontend:** `frontend/src/api.session-token.test.ts` (full), `App.test.tsx` (assertion-style spot checks), inventory of all 32 vitest files.
- **Product surfaces cross-referenced:** `frontend/src/components/Landing.tsx` (example prompts), `src/kimcad/webapp.py` (`DemoProvider`, session-token guard), `src/kimcad/model_advisor.py` (gemma4 catalog), `bench/prompts.yaml`, `README.md`, `CHANGELOG.md`.
- **Verification run performed:** `pytest tests/test_version_single_source.py -q` → 6 passed (confirms TEST-002's green-with-stale-README claim).
