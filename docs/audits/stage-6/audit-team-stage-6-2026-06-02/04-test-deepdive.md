# Stage 6 — Test Engineer Deep-Dive

**Auditor:** Test Engineer (audit-team)
**Date:** 2026-06-02
**Branch:** `stage-6-model-swap`
**Repo:** `C:\Users\scott\dev\kimcad`
**Scope:** the model layer — `model_advisor`, `FallbackProvider`, `benchmark` (3-axis grading),
`bakeoff`, and the `plan_failed` / `PlanParseError` safety path across pipeline / CLI / frontend.

---

## Suite execution (cited, actual)

- **Full pytest:** `588 passed in 113.94s` (`.venv\Scripts\python.exe -m pytest tests -q`). 0 failed, 0 skipped, 0 xfail. Matches the expected 588.
- **Vitest:** `Test Files 6 passed (6) / Tests 36 passed (36)` in 2.00s. Matches the expected 36.
- **Stage-6 core four** (`test_model_advisor`, `test_fallback_provider`, `test_bakeoff`, `test_benchmark`): `95 passed in 1.59s`.

No skips, no `xfail`, no `.only`, no retry/rerun config, no `assert True` placeholders, no commented-out
assertions anywhere in the in-scope files. That is a genuinely clean shortcut census — see "What's working".

## Test-suite shape

Bottom-heavy and honest: the model layer is built as **pure decision functions** (`recommend`,
`compare_runs`, the three `grade_*` helpers, `_installed_match`) with thin I/O wrappers, and the
tests hit the pure cores directly with synthetic inputs. Integration points (Ollama HTTP, the OpenAI
SDK, the live pipeline) are mocked at their true boundaries (`urllib.request.urlopen`, the chat client,
a duck-typed pipeline), not faked one layer in. The safety-critical narrowings (`plan_failed` vs
`gate_failed`, connection-not-masked, fallback-only-on-transport-errors) each have a dedicated
mutation-killing test. This is the right shape for a model layer; the gaps below are edge/degenerate
paths and one missing console-encode pin, not core-behavior holes.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 4 |
| Nit      | 3 |
| **Total**| **7** |

No Blocker/Critical/Major. The seven items are coverage seams on defensive/degenerate paths plus
one missing-but-low-risk console-encode test. Every in-scope safety property the directive asked
about is actually tested (not merely asserted in prose) — verified by reading each test against the
code and by mutation-think (would the test fail if I inverted the logic). Details below.

---

## Verification of the directive's "look hard" checklist

Each item: **does a test exist, and would it FAIL if the property were broken?**

**1a. Connection error NOT masked as plan_failed — VERIFIED.**
`tests/test_pipeline.py:129 test_connection_error_is_not_swallowed_as_plan_failed` raises a real
`openai.APIConnectionError` from the provider and asserts `pytest.raises(APIConnectionError)`.
`pipeline.py:291` catches **only** `PlanParseError`, so the connection error propagates. Mutation check:
widen the catch to include `APIConnectionError` → this test fails. Real, not tautological.

**1b. Non-parse `ValueError` propagates (narrowing pinned) — VERIFIED.**
`tests/test_pipeline.py:144 test_a_non_parse_error_is_not_masked_as_plan_failed` raises a plain
`ValueError` from the provider and asserts it propagates. Because `pipeline.run` catches only
`PlanParseError` (not the `_PLAN_PARSE_ERRORS` tuple, which DOES include `ValueError` but lives one
layer down inside `LLMProvider`), this is a correct, decisive pin. Mutation check: change `pipeline.py:291`
to `except (PlanParseError, ValueError)` → fails. (Seam noted in TEST-005.)

**1c. Exit-code uniqueness plan_failed→6, distinct from gate_failed→5 — VERIFIED.**
`tests/test_cli.py:150 test_design_plan_failed_exit_6_clean_no_traceback` asserts `code == 6` with the
inline comment "not 5 -- no collision". The sibling `test_design_gate_failed_exit_5` (line 139) pins
`code == 5`. I enumerated every `return <int>` in `cli.py`: 0/1/2/3/4/5/6 are all distinct and each design
status maps to its own code. Both the 6 and the 5 case are independently tested, so the *uniqueness*
(not just "6 exists") is real. The exit-6 test also asserts `"Traceback" not in out` — pins the
clean-message contract.

**1d. FallbackProvider falls back ONLY on connection/timeout/404, not arbitrary exceptions — VERIFIED.**
Positive: `test_fallback_on_api_connection_error` / `_api_timeout_error` / `_model_not_found` (lines 96–117)
each prove alt is reached. The catch in `llm_provider.py:279` is exactly
`(APIConnectionError, APITimeoutError, NotFoundError)`. **Gap (TEST-001):** there is no NEGATIVE test —
no test raises an *arbitrary* exception (e.g. `RuntimeError`, `ValueError`) from the primary and asserts
it propagates WITHOUT touching alt. The narrowing is therefore asserted only by the positive set; an
accidental broadening to `except Exception` would NOT be caught by any current test. This is the one
"the test wouldn't fail if you broke it" finding in the suite.

**1e. Thread-local stickiness is thread-local — VERIFIED (well).**
`test_stickiness_is_thread_local` (line 159) runs thread A (fails over to alt → "alt_ok") and a separate
thread B (primary now healthy → "primary_ok") and asserts B is NOT stuck on alt. This is a genuine
concurrency test, not a single-thread proxy. Mutation check: make `_local` a plain instance attribute
instead of `threading.local()` → B would return "alt_ok" → fails. Strong test.

**1f. Bake-off recommend-only / no config mutation — PARTIALLY VERIFIED (TEST-002).**
`compare_runs` and `run_bakeoff` are pure by construction and the tests confirm they only *return* a
`Recommendation`/`Bakeoff`. `bakeoff.py` imports nothing that writes config and the docstring says the
flip "is intentionally NOT done here." But there is no explicit *assertion* that config is never written
(e.g. no test that runs the bake-off and checks the config file / `config.raw` is byte-identical after).
The property holds structurally; it just isn't pinned against a future regression where someone adds an
auto-apply. Minor.

**1g. `_pipeline_for_backend` builds a bare provider (no fallback) — VERIFIED indirectly, NOT directly (TEST-003).**
`cli.py:176 _pipeline_for_backend` deliberately constructs a bare `LLMProvider` (no `FallbackProvider`)
so a silent failover can't contaminate a per-model bake-off measurement. There is **no test** that calls
`_pipeline_for_backend` and asserts the resulting pipeline's provider is a bare `LLMProvider` and NOT a
`FallbackProvider` — even when an `alt_backend` is configured. The analogous property for the *design*
path IS tested (`test_build_pipeline_uses_fallback_provider...` / `_uses_bare_provider...`), so the bake-off
path is the asymmetric gap. This guards a real correctness property (measurement isolation), so it's
worth a 3-line test. Minor.

**2. 3-axis grading honesty — VERIFIED, thoroughly.**
- "None never blocks `graded_passed`": `test_graded_passed_unassessed_axes_do_not_block` (all axes None →
  passes) and `test_graded_passed_one_failed_axis_blocks` (one False → blocks) together pin the
  `axis is not False` semantics. Mutation check: change to `axis is True` → the unassessed test fails.
- "None excluded from `axis_tally` denominator": `test_axis_tally_and_graded_rate` asserts
  `axis_tally("slices_clean") == (1, 1)` where two of three cases are None → denominator is 1, not 3.
  Decisive.
- `grade_correct_dimensions` "ceiling can only fail, never assert" + the undersized-fits-ceiling
  regression: `test_grade_correct_dimensions_undersized_fits_ceiling_is_not_a_pass` (5×5×1 vs 50×50×10 →
  `None`, explicitly tagged "BENCH-001 regression"), `_ceiling_only_is_unassessed` (within ceiling but no
  gate confirm → None), `_exceeds_ceiling_fails`, `_match_within_ceiling_passes`, `_mismatch_beats_ceiling`.
  This axis is the best-covered piece of the whole layer — every branch of the tri-state is pinned, and
  the dangerous "fits-under-ceiling looks like a pass" bug is a named regression test.

**3. model_advisor — VERIFIED, with two small holes.**
- Exact-tag `_installed_match` incl. `:1.5b ≠ :7b`: `test_installed_match` is parametrized with the
  `1.5b vs 7b` regression (line 128), the `:1.5b-instruct` false-match guard, the bare-`gemma4`(=`:latest`)
  vs `:e4b` case, and the tagless-spec cases. Mutation check: change `_installed_match` to a `startswith`
  match → the `1.5b/7b` and `-instruct` rows fail. Strong.
- Never-raise probe paths: `test_probe_installed_models_returns_empty_when_ollama_is_down` (OSError →
  `[]`) and `test_probe_hardware_never_raises_and_reports_os` cover the down/exception paths. **Hole
  (TEST-004):** `probe_installed_models` with a *malformed body* (200 OK but non-dict JSON, or `models`
  missing / a model dict with no `name`) is not tested — the `isinstance(data, dict)` guard and the
  `if not name: continue` branch at `model_advisor.py:232–236` are unexercised. The "bad body" never-raise
  path the directive called out is therefore only half-covered (down is tested; garbage-response is not).
- `recommend()` purity: `test_recommend_is_pure_same_inputs_same_output` (line 117) pins `a == b`.

**4. Assertion-free / tautological / mock-the-thing-under-test tests — NONE FOUND.**
I read every in-scope test for: assertions that would pass with the feature inverted, tests that assert
on a mock's configured return rather than on behavior, and import-only tests. The `_build_pipeline` /
`_real_provider` wiring tests use a `_FakePipeline` only to *capture* the provider, then assert on the
provider's real concrete type (`isinstance(..., FallbackProvider)` vs `LLMProvider`) — that's testing the
wiring decision, not the mock. The mocks are at true I/O boundaries. No tautologies found.

**5. Coverage holes — see TEST-001..007 (all Minor/Nit). The notable ones:**
`_pipeline_for_backend` (TEST-003), the `FallbackProvider` arbitrary-exception negative case (TEST-001),
`probe_installed_models` malformed-body (TEST-004), the `recommend()` empty-catalog terminal branch and
the GPU-present `fits()` path (TEST-006), and the `_cmd_bakeoff` CLI validation branches (TEST-007).

**6. cp1252 / console-safety of printed strings — MIXED (TEST-002 sub-finding / TEST-007).**
- `benchmark.to_text` is encode-tested twice (`test_to_text_is_console_safe` asserts `.encode("cp1252")`
  and `">=" in text`; `test_to_text_shows_three_axis_block_and_is_console_safe` asserts the `ok/XX/--`
  axis marks stay cp1252). Good.
- `bakeoff.to_text` and both `compare_runs` reason paths are encode-tested AND `.isascii()`-tested
  (`test_to_text_table_and_recommendation_are_console_safe`, `_did_not_clear_reason_is_console_safe`,
  `_no_switch_when_incumbent_absent`). Good.
- **Hole:** the **advisor** printed strings — `HardwareProfile.summary()`, `recommend().reason`, the
  `_cmd_models` output — have **no encode test**. I verified at runtime they are ASCII today (`->`, `--`,
  no em-dashes/×/³), and at runtime `main()` forces stdout to UTF-8 via `_force_utf8_output`, so this is
  defense-in-depth, not a live crash. But the deliberately-ASCII discipline (the code comments say "ASCII
  separators only -- printed to the cp1252 console") is unpinned for the advisor specifically. Captured in
  TEST-007.

---

## Findings

### TEST-001 (Minor · Coverage/Mocking) — No negative test that `FallbackProvider` ignores an arbitrary (non-transport) exception

**Evidence:** `src/kimcad/llm_provider.py:279` catches exactly
`(APIConnectionError, APITimeoutError, NotFoundError)`. `tests/test_fallback_provider.py` has positive
fallback tests for all three (lines 96–117) and propagation tests for the no-alt case (lines 120–133),
but **no test raises a `RuntimeError`/`ValueError`/`KeyError` from the primary and asserts it propagates
without alt being called.** Grep confirms: the only errors injected into a `FallbackProvider` primary are
the three transport types.

**Why it matters:** this is the one in-scope narrowing whose *exclusivity* is not pinned. If a refactor
broadened the catch to `except Exception` (a classic "make the demo robust" mistake), every existing
fallback test would still pass — a genuine bug (a plain bug in the primary being silently retried on the
alt, masking the defect and double-billing the alt model) would ship green. This is the textbook
"would the test fail if you broke it? — no" case.

**Blast radius:**
- Adjacent code: mirrors the pipeline-level narrowing (`pipeline.py:291`), which IS negatively tested
  (`test_a_non_parse_error_is_not_masked`). The fallback layer should match that rigor.
- User-facing: a masked primary bug would surface as "silently using the cloud model" — a privacy/cost
  surprise for a local-first tool.
- Tests to update: none; this is additive.
- Related findings: none.

**Fix path:** add ~5 lines to `tests/test_fallback_provider.py`:
```python
def test_arbitrary_primary_error_propagates_and_skips_alt():
    primary = _mock_provider(error=RuntimeError("a real bug"))
    alt = _mock_provider(return_val="alt_ok")
    fp = FallbackProvider(primary, alt)
    with pytest.raises(RuntimeError):
        fp.generate_design_plan("p", MagicMock(), MagicMock())
    alt.generate_design_plan.assert_not_called()
```

### TEST-002 (Minor · Coverage) — Bake-off "recommend-only / never mutates config" is structural, not pinned

**Evidence:** `bakeoff.py` only returns a `Bakeoff`/`Recommendation`; `_cmd_bakeoff` (`cli.py:320`) writes
only `bakeoff.txt` and prints. No test asserts that running a bake-off leaves the config untouched. The
directive explicitly asked "is there anything proving it never writes config?" — answer: no, only the
docstring ("Flipping the configured default model is Scott's call").

**Why it matters:** the no-auto-apply property is a deliberate human-gate (like merge/tag). A future
"convenience" PR that auto-writes `llm.active` on a SWITCH recommendation would pass every current test.
Pinning it converts a prose intention into a regression guard.

**Blast radius:**
- Adjacent code: `config.raw`, `config/local.yaml` write paths.
- User-facing: an auto-flip would silently change which model runs — exactly the kind of surprise the
  recommend-only design avoids.
- Tests to update: none; additive.
- Related findings: TEST-003 (both are bake-off isolation guarantees).

**Fix path:** in `tests/test_bakeoff.py`, after a `run_bakeoff(...)` with a fake pipeline, assert the
passed-in `config.raw` dict is unchanged (snapshot a copy before, `assert config.raw == before`), and/or
assert `_cmd_bakeoff` does not call any config writer. Low effort, high regression value.

### TEST-003 (Minor · Coverage) — `_pipeline_for_backend` (no-fallback isolation) is untested

**Evidence:** `cli.py:176 _pipeline_for_backend` builds a **bare** `LLMProvider` on purpose ("a silent
fallback would contaminate the comparison by swapping in the other model mid-run"). Grep of `tests/`
shows no test references `_pipeline_for_backend`. By contrast the design path's bare-vs-fallback choice
IS tested (`test_build_pipeline_uses_bare_provider_when_no_alt`,
`test_build_pipeline_uses_fallback_provider_when_alt_backend_configured`).

**Why it matters:** the measurement-isolation property is the whole reason the bake-off can be trusted to
compare models head-to-head. If someone "helpfully" routed `_pipeline_for_backend` through
`FallbackProvider` (so a flaky local model wouldn't fail a backend's batch), the bake-off would silently
measure the *alt* model for some cases and the comparison would be corrupt — and no test would catch it.

**Blast radius:**
- Adjacent code: `run_bakeoff` consumes `make_pipeline=lambda key: _pipeline_for_backend(...)`.
- User-facing: a corrupted bake-off could recommend the wrong default model — the exact decision this
  stage exists to make correctly.
- Tests to update: none; additive.
- Related findings: TEST-002.

**Fix path:** add a test that builds a config WITH `alt_backend` set, calls `_pipeline_for_backend`, and
asserts `isinstance(pipeline.provider, LLMProvider)` and `not isinstance(pipeline.provider,
FallbackProvider)` — the key being that even *with* an alt configured, the bake-off pipeline stays bare.

### TEST-004 (Minor · Coverage) — `probe_installed_models` malformed-body path untested

**Evidence:** `model_advisor.py:226–238` guards a 200-OK-but-garbage response: `isinstance(data, dict)`
(line 232) and `if not name: continue` (line 234–235). `tests/test_model_advisor.py` tests the happy parse
(line 151) and the connection-down `OSError → []` (line 171), but never a malformed body (e.g.
`urlopen` returns `[1,2,3]` JSON, or `{"models":[{"size":1}]}` with no name, or non-JSON 200).

**Why it matters:** Ollama version drift or a reverse-proxy returning an HTML error page with status 200
is a realistic "never raise" trigger. The directive named "bad body" as a probe path to confirm; today
it's unconfirmed. The guards look correct on read, but they're the kind of defensive branch that rots
silently.

**Blast radius:**
- Adjacent code: the `recommend()` flow downstream consumes the (possibly empty) list — already robust.
- User-facing: a raised exception here would crash `kimcad models`, the Stage-6 flagship command.
- Tests to update: none; additive.
- Related findings: none.

**Fix path:** parametrize a `_Resp` returning (a) a JSON list, (b) `{"models":[{"size":5}]}` (no name),
(c) `b"<html>502</html>"` — assert each yields `[]` (or skips the nameless entry) and never raises.

### TEST-005 (Nit · Coverage) — Real-provider connection-error placement is pinned only indirectly

**Evidence:** the property "a connection error from `_complete` during the *real*
`LLMProvider.generate_design_plan` escapes un-wrapped" rests on the `_complete` call being OUTSIDE the
`try` at `llm_provider.py:204–210`. `_complete`'s own retry/raise is tested
(`test_complete_raises_after_exhausting_retries`), and the pipeline boundary is tested with a fake
provider, but no test drives the *real* `generate_design_plan` with a client that raises
`APIConnectionError` to confirm it is NOT wrapped as `PlanParseError`.

**Why it matters:** if someone moved `raw = self._complete(...)` inside the `try`, a connection error
would become `PlanParseError("...", original=APIConnectionError)` → masked as `plan_failed` and the
fallback chain would never fire. Structurally safe today; unpinned.

**Fix path (optional):** one test using `FakeChatClient` whose `create` raises `APIConnectionError`,
asserting `provider.generate_design_plan(...)` raises `APIConnectionError`, not `PlanParseError`.

### TEST-006 (Nit · Coverage) — Two degenerate advisor branches unexercised

**Evidence (runtime-confirmed):**
- `recommend()` terminal branch `model_advisor.py:353` (`primary=None`, "No model in the catalog fits")
  is only reachable with a cloudless catalog; no test passes one. Confirmed reachable:
  `recommend(HardwareProfile('X',8,4.0), [], catalog=(local-only-99GB-floor,)) → primary is None`.
- `fits()` / `summary()` with a discrete GPU present: every `_hw()` helper uses `gpu=None`, so
  `has_discrete_gpu is True`, the GPU branch of `summary()` ("… GB VRAM"), and "GPU present + RAM unknown
  → still False" (RAM gates) are untested. Confirmed: `spec.fits(HardwareProfile('X',8,None,'RTX',24.0))
  is False` and `has_discrete_gpu is True`.

**Why it matters:** low — these are defensive/degenerate paths. But the GPU-present `summary()` string is
user-visible (`kimcad models` on any NVIDIA box) and has never been rendered in a test, so a formatting
bug there (e.g. a non-ASCII glyph, a None-format crash) wouldn't be caught.

**Fix path:** add `recommend(..., catalog=local_only)` asserting `primary is None`; add a `fits()`/
`summary()` case with `gpu_name="RTX 4090", vram_gb=24.0` asserting the VRAM string renders and
`.isascii()`.

### TEST-007 (Nit · Coverage/Console-safety) — No cp1252 encode test for advisor output; `_cmd_bakeoff` CLI branches untested

**Evidence:**
- Advisor: `HardwareProfile.summary()` / `recommend().reason` / `_cmd_models` printed lines have no
  `.encode("cp1252")` / `.isascii()` test, unlike `benchmark.to_text` and `bakeoff.to_text` which both
  do. The code comments commit to ASCII-only ("printed to the cp1252 Windows console") but nothing pins it.
- `_cmd_bakeoff` (`cli.py:320`): the validation branches — missing prompts file → exit 2, `<2 backends`
  → exit 2, unknown backend key → exit 2 — have **no test**. Grep shows zero `main(["bakeoff", ...])`
  invocations. (The pure `compare_runs`/`run_bakeoff`/`to_text` are well-tested; it's the CLI front-door
  validation that's bare.)

**Why it matters:** low-to-moderate. At runtime `main()` forces UTF-8 stdout, so the advisor encode gap
is belt-and-suspenders. The `_cmd_bakeoff` validation gaps are more material: a typo'd `--backends` is the
single most likely user error on a many-minutes-of-CPU command, and the "fail fast on unknown key" guard
(`cli.py:340`) — the thing standing between the user and a wasted hour — is unverified.

**Blast radius:**
- User-facing: `kimcad bakeoff` is a Stage-6 surface; its argument validation is the first thing a user
  hits and is currently untested.
- Tests to update: none; additive.
- Related findings: TEST-002, TEST-003 (the bake-off cluster — all three are "the bake-off command path is
  thinly tested above the pure core").

**Fix path:** add three `main(["bakeoff", ...])` tests asserting exit 2 for (no prompts file / one backend
/ unknown key), reusing the `_patch_pipeline`-style monkeypatch. Optionally add `summary().encode("cp1252")`
and `recommend(...).reason.isascii()` assertions in `test_model_advisor.py`.

---

## What's working (specific credit)

- **Clean shortcut census.** Across all in-scope files: zero skips, zero `xfail`, zero `.only`, zero retry
  config, zero `assert True` placeholders, zero commented-out assertions. The team is not gaming CI.
- **Named regression tests with provenance.** `test_grade_correct_dimensions_undersized_fits_ceiling_is_not_a_pass`
  cites "BENCH-001 regression"; `test_a_non_parse_error_is_not_masked` cites "PLAN-002"; the exit-6 test
  comments "not 5 -- no collision with gate_failed". This is a tests-with-fixes culture, exactly the
  posture an auditor wants to see.
- **Mocks at true boundaries.** Ollama is mocked at `urllib.request.urlopen`; the LLM at the OpenAI chat
  client; the pipeline as a duck-typed fake that only captures, not fakes-one-layer-in. No integration
  test is a unit test in disguise here.
- **Real concurrency test.** `test_stickiness_is_thread_local` spins two actual threads and proves the
  thread-local boundary — not a single-thread approximation.
- **Tri-state grading is exhaustively pinned.** Every True/False/None branch of all three `grade_*` helpers
  and of `graded_passed` / `axis_tally` has a dedicated test, including the honesty-critical "None excluded
  from denominator" and "None never blocks a pass."
- **Console-safety is treated as a first-class property** for the benchmark and bake-off rollups (both
  `.encode("cp1252")` and `.isascii()`), reflecting a real past crash (the `≥`→`>=` incident referenced in
  `test_to_text_is_console_safe`).
- **The exact-tag `_installed_match` bug is locked down** with the precise `1.5b ≠ 7b` and `:1.5b-instruct`
  rows — the regression that motivated the function is the test.
- **Design-path provider wiring is tested both ways** (bare vs fallback), for both the CLI and the webapp
  `_real_provider`, so the UI path provably mirrors the CLI.

---

## Bottom line

The Stage-6 model layer is **well-tested on every safety-critical property the gate cares about**:
plan_failed↔gate_failed exit uniqueness, connection-not-masked, the parse-narrowing, thread-local
stickiness, fallback-only-on-transport-errors (positive side), tri-state grading honesty, and the
exact-tag install match are each pinned by a test that would fail if the property were inverted. The
seven findings are all Minor/Nit: missing *negative*/edge coverage on defensive paths (arbitrary-exception
fallback, malformed-body probe, degenerate `recommend`), three thin spots in the bake-off *command* path
above its well-tested pure core (`_pipeline_for_backend`, no-config-mutation pin, `_cmd_bakeoff`
validation), and one missing advisor console-encode pin. None blocks the stage gate. Recommend closing
TEST-001 and TEST-003 this sprint (they each guard a real correctness property with a ~5-line test); the
rest are watchlist.
