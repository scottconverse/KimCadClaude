# Stage 6 — Test Engineer Deep-Dive (backfill 2026-06-05)

**Auditor role:** Senior Test Engineer (independent, skeptical)
**Scope:** the model layer — hardware/availability advisor (`model_advisor.py`), the
bake-off harness (`bakeoff.py`), the tiered fallback chain (`llm_provider.py`
`FallbackProvider`), and the model-unreachable / model-status graceful-degrade paths in
`pipeline.py` + `webapp.py`.
**Method:** read source first, then tests; ran the model-layer subset read-only; cross-checked
every CLAIM in the test docstrings against the SOURCE behavior they assert.
**Run command / result:**
`.venv/Scripts/python.exe -m pytest -m "not live" -q -k "advisor or model or bakeoff or fallback or provider or status"`
→ **175 passed, 600 deselected, 0 skipped, 0 failed** (37 s). No flakiness, no retries, no `--retry` config.

---

## Severity counts

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 2 |
| Nit      | 1 |
| **Total**| **4** |

---

## What's working (credit where due)

This is, honestly, one of the more disciplined test slices I've audited. Specifics:

- **The pure decision is tested as pure, and proven pure.** `recommend()` has a dedicated
  same-inputs-same-output test (`test_recommend_is_pure_same_inputs_same_output`,
  test_model_advisor.py:120) on top of behavioral coverage of every branch: best-installed-that-fits,
  upgrade-suggestion, pull-when-nothing-fits, small-box→cloud, unknown-RAM→cloud, and
  nothing-fits-no-cloud→`primary=None` (test_model_advisor.py:50-124, 221-226).
- **The ENG-006 ranking is asserted correctly, not as a smell.** gemma4:e4b ranks top and the
  advisor never recommends Qwen over it; when only a China model is installed, the non-China escape
  steers to gemma4:e4b by NAME (test_model_advisor.py:50-57, 103-112). These assertions match the
  catalog tiers in source — they are correct.
- **`_installed_match` false-tag rejection is table-tested** including the exact bug it guards
  (`qwen…:1.5b` must NOT satisfy a `…:7b` spec) and the `:latest`/bare-name tolerance
  (test_model_advisor.py:128-140). `_ollama_tags_url` proxy-path safety (ENG-601) is table-tested
  including a proxied sub-path that must be discarded (test_model_advisor.py:143-152).
- **The Ollama probe tolerates a 200-OK-but-garbage body** — four adversarial bodies (list-not-dict,
  nameless entry, HTML 502 page, missing `models` key) all yield `[]` and never raise
  (TEST-004, test_model_advisor.py:185-202). Down/refused is covered (test_model_advisor.py:177-182).
- **`probe_ollama`'s entire reason-to-exist is pinned**: reachable-but-empty is distinguished from
  down (test_webapp.py:2179-2211) — three states (models / up-empty / down) each asserted.
- **The graceful-degrade path is tested end-to-end through a real HTTP server**, not mocked at the
  edge: an Ollama connection error at the PLAN step AND a drop during CODEGEN both return a typed
  `model_unavailable` 200 (never a 500/traceback) — test_webapp.py:2656-2720. The error propagates
  through the real pipeline; this is a genuine integration test.
- **`friendly_label`, cp1252-console safety, `probe_hardware` never-raises, and the GPU-present
  branch** are all covered (test_model_advisor.py:207-256).
- **Fallback routing is thorough**: primary-success-skips-alt, fallback on each of the three
  transport errors (conn/timeout/404), no-alt-propagates, thread-local stickiness (incl. a real
  two-thread test), `max_attempts→1` reduction, and — the high-value negative — an ARBITRARY
  (non-transport) error must NOT trigger fallback and must leave alt untouched (TEST-001,
  test_fallback_provider.py:402-412). That last one is exactly the test that stops a future
  `except Exception` refactor from silently retrying a bug on the alt model.
- **The bake-off comparison is tested against the source's real tiebreak order** (graded → completion
  → speed), including the epsilon-tie-then-faster switch, the win-but-slower path, the
  incumbent-absent path, and the "challenger didn't clear the bar" keep — all with cp1252 assertions
  on the console strings (test_bakeoff.py:43-138). `run_bakeoff` wiring is covered with an injected
  fake pipeline and the slice-request kwarg is asserted (test_bakeoff.py:170-281).
- **The cloud key is proven not to echo back** from `/api/model-status` (test_webapp.py:2238-2256)
  and is cleared on reset (test_webapp.py:2259-2282).

**Suite shape:** heavy, well-targeted unit coverage of the pure logic; a thin but REAL integration
band (live in-process HTTP server driving the actual webapp + pipeline for the degrade paths); the
truly-live band (real Ollama, both models pulled) is correctly carved out as the documented hand-off,
not faked. No over-mocking of the integration points I checked — the fallback unit tests mock the
two providers (correct: they test the ROUTER, not the providers), while the degrade tests use real
wiring. The few mocks of `_build_client` (test_fallback_provider.py:309 etc.) are to avoid a live
network client during pure WIRING assertions — appropriate.

---

## Findings

### TEST-101 (Major) — Coverage — No test pins the cloud/LLM API key out of the fallback log or any LLMProvider error
**Category:** Coverage
**Evidence:**
- `FallbackProvider._call` prints `[kimcad] primary model failed (…); switching to alt backend
  '{self.alt.backend.key}'` to stderr (llm_provider.py:359-364). `LLMProvider._build_client` and
  `_complete` handle the secret key (llm_provider.py:168-206).
- The printer connectors each have an explicit `test_api_key_never_appears_in_error`
  (test_octoprint_connector.py:269, test_moonraker_connector.py:179, test_prusalink_connector.py:155).
  **The model layer has no equivalent.** Grep of test_llm_provider.py + test_fallback_provider.py for
  any key-leak / `capsys` / `caplog` / stderr assertion returns nothing.
- The model-status response is proven key-free (test_webapp.py:2238), but that's the HTTP response,
  not the LLM-layer logs/exceptions where a cloud (OpenRouter/DeepSeek) key is actually in scope.

**Why this matters:** the cloud fallback is the one model-layer path that holds a real secret. Today
the log prints the backend *key* (a name like `"cloud"`), not the secret — correct — but nothing
*guards* that. A future refactor that interpolates the backend object, the base_url with an embedded
token, or the underlying OpenAI error (which can carry request detail) into that stderr line or into
a re-raised exception would leak a key and ship green: every existing positive test would still pass.
This is the same bug class the connector suite explicitly defends against; the model layer is the gap.
**Blast radius:**
- Adjacent code: `FallbackProvider._call` (llm_provider.py:359), `_complete` raise path
  (llm_provider.py:206), `_build_client` RuntimeError (llm_provider.py:176-180).
- User-facing: none today; a regression would be a credential disclosure in logs.
- Migration: none. Additive test.
- Tests to update: none; add new.
- Related findings: cross-tags the connector suite's existing key-leak tests as the pattern to mirror.

**Fix path:** add `test_fallback_log_and_errors_never_contain_the_api_key` — construct a
`FallbackProvider` whose alt backend carries a sentinel secret, force a primary transport error,
capture stderr with `capsys`, and assert the sentinel is absent from the log; assert the same for the
`_build_client` RuntimeError message and any re-raised `_complete` error.

---

### TEST-102 (Minor) — Coverage — `_non_china_escape` "prefer an already-installed alternative" branch is untested
**Category:** Coverage
**Evidence:** `_non_china_escape` (model_advisor.py:305-317) returns `(spec, is_installed)` and
**prefers an installed non-China model over one that needs pulling** (`installed_nc or candidates`).
Every `recommend` test asserts `non_china_installed is False` (test_model_advisor.py:93, 112); no test
ever drives the `is_installed=True` branch. (A grep for a `non_china_installed is True` assertion finds
only stale `.pyc` cache files, no live source.)
**Why this matters:** the "preferred-because-installed, usable-now" branch is the user-helpful half of
the feature and is entirely unexercised. A regression that always returned the needs-pull candidate
(or dropped the installed-preference sort) would pass the whole suite. Severity Minor: the primary
recommendation is unaffected; only the alternative's installed-flag/choice would silently degrade.
**Fix path:** add a case where a China model is the primary AND a non-China local model (e.g.
`llama3.1:8b`) IS installed and fits; assert `non_china_alternative.name == "llama3.1:8b"` and
`non_china_installed is True`.

---

### TEST-103 (Minor) — Coverage — `Bakeoff.to_text` zero-completion / "n/a" rendering and tie-on-completion table are untested
**Category:** Coverage
**Evidence:** `to_text` has a non-trivial formatting branch for a model that completed 0 cases — it
emits a `note: <backend> completed 0/<n> cases` line and renders axis cells + `mean_s` as `"n/a"`
rather than a misleading `0/0` / `0.0` (bakeoff.py:166-180). The two `to_text` tests
(test_bakeoff.py:143-166) only exercise the all-passing SWITCH and the KEEP table; neither produces a
zero-completion run, so the `"n/a"` cells and the `note:` line never render under test.
**Why this matters:** the `"n/a"`-vs-`"0/0"` distinction exists specifically so a non-functional model
doesn't *read* as a fast 0-score — exactly the failure mode that masked a dead LLM in a prior gate
(per project memory). If that branch regressed to printing `0.0`/`0/0`, a human reading the bake-off
table could misjudge a broken model as merely low-scoring. Untested.
**Fix path:** add a `to_text` case with one run whose summary has `passed == 0`; assert the output
contains `completed 0/` in a `note:` line and that the axis/`mean_s` cells render `n/a`, not `0.0`.

---

### TEST-104 (Nit) — Quality — `describe_photo` empty-seed stderr breadcrumb (ENG-002) is not asserted
**Category:** Quality
**Evidence:** `LLMProvider.describe_photo` prints a one-line "vision returned empty… update Ollama"
hint to stderr when the seed is empty (llm_provider.py:298-306). The describe_photo tests
(test_webapp.py:2571-2644) cover the native `/api/chat` + `think:false` request shape and the
local-only routing, but not the empty-seed breadcrumb path.
**Why this matters:** minor — it's a debug breadcrumb, not user-visible behavior; the graceful "couldn't
read that photo" handling lives in the caller and is covered elsewhere. Flagging once for completeness.
**Fix path:** optional — assert the stderr hint appears when the mocked vision response yields an empty
`message.content`.

---

## Patterns / culture observations (for the exec report)

- **Regression-test discipline is real here.** Multiple tests are tied to a specific finding ID
  (TEST-001, TEST-003, TEST-004, ENG-006, ENG-601, UX-007) with a docstring explaining the bug the
  test exists to prevent — including *negative* tests (arbitrary-error-must-not-fall-back;
  bare-provider-in-bake-off-not-fallback) that defend against plausible future refactors, not just the
  happy path. That is exactly the posture the standing rule ("a fix without a regression test is not
  done") asks for.
- **Console-safety (cp1252) is treated as a first-class, repeatedly-asserted contract**, appropriate
  for a Windows consumer app.
- **The one real gap is a security-adjacent one** (TEST-101): the model layer is the only place that
  holds a cloud secret and the only edge-vs-connectors place WITHOUT a key-leak guard. That is the
  single highest-value test to add this slice.

## Verdict

The Stage-6 model layer's test coverage is **strong and substantially matches its claims** — no
Blockers, no Criticals, no shortcuts, no skips outside legitimate environment gates, no over-mocking
of integration points, and a genuine end-to-end degrade test. **One Major** (missing cloud-key leak
guard at the LLM layer) and **two Minor** coverage gaps keep it short of the zero-findings bar. Add
TEST-101 + TEST-102 + TEST-103 and this slice is at the release bar.
