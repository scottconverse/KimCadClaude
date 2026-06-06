# Stage 6 Engine — Principal Engineer Deep-Dive (backfill audit)

- **Date:** 2026-06-05
- **Auditor role:** Principal Engineer (independent, audit-only)
- **Branch:** `stage-0-7-audit-backfill`
- **Scope:** Stage 6 model layer — `model_advisor.py`, `bakeoff.py`, the tiered fallback + plan-failure robustness in `llm_provider.py` (`FallbackProvider`, the `describe_photo` Protocol member) and `pipeline.py` (model-unreachable handling), plus the consumers in `cli.py` and `webapp.py` that wire them.
- **Method:** Static read of every file in scope and its call sites; data-provenance trace of the cloud API key; dedicated passes for the four scope questions (deterministic + safe decision; probes tolerate a down/garbage Ollama; graceful degradation on model-down; the cloud key is never logged). Did **not** run the suite live (audit-only) — the test files were read for coverage assessment.
- **Out of scope by directive:** the gemma4-vs-other-model choice. The advisor ranking gemma4 top-tier and deprioritizing Qwen is intentional and was treated as correct; no finding raised on it.

---

## Verdict

**PASS — zero findings (0 Blocker / 0 Critical / 0 Major / 0 Minor / 0 Nit).**

The Stage 6 engine is release-quality. The decision function is genuinely pure and deterministic, every probe degrades to a typed "unknown"/empty result instead of raising, a down or garbage-spewing Ollama produces a recoverable typed status rather than a 500/traceback, and the cloud API key is never logged, printed, or echoed in full. The areas a skeptical reviewer expects to find rot — the SSRF-shaped URL derivation, the false-positive installed-tag matching, the thread-local fallback stickiness, the console cp1252 surface, the key-redaction path — are each handled deliberately and, in most cases, carry a regression test and an explanatory comment tying back to a prior finding ID. This is the strongest module layer in the project I have reviewed.

I went looking for defects against the four scope questions and a full security/correctness/perf/robustness pass. I did not find one that pays its rent. The notes below are the candidates I evaluated and consciously **declined** to file, recorded so the next auditor doesn't re-chase them.

---

## What's working (specific, earned)

1. **`recommend` is actually pure.** No I/O, no clock, no global read; output is a function of `(hardware, installed, catalog)`. `test_recommend_is_pure_same_inputs_same_output` asserts it, and the structure backs the claim — the only non-determinism risk would be dict/set ordering, and the code sorts candidates explicitly by `tier` (with `max(..., default=None)`), so ties resolve deterministically by the catalog's declaration order. (`model_advisor.py:320-399`.)

2. **The probes never raise — verified, not asserted.** `_total_ram_gb`, `_probe_nvidia_gpu`, `probe_installed_models`, and `probe_ollama` each wrap their I/O in a catch that returns `None`/`[]`/`(False, [])`. `_probe_nvidia_gpu` correctly catches `FileNotFoundError`/`OSError`/`SubprocessError` (the missing-`nvidia-smi` case on the iGPU target) and tolerates a non-numeric VRAM field (`ValueError → (name, None)`). The garbage-body matrix in `test_probe_installed_models_tolerates_a_malformed_body` (list-not-dict, nameless entry, HTML 502 page, missing key) is exactly the adversarial set I would have written. (`model_advisor.py:146-283`.)

3. **`probe_ollama` distinguishes "down" from "up-but-empty."** The two-value return `(reachable, installed)` lets the Settings UI say "Start Ollama" vs "Get the model" — a real UX distinction that a single `[]` return (as `probe_installed_models` gives) would have collapsed. Both exist on purpose; the docstrings name the difference. (`model_advisor.py:261-283`, consumed at `webapp.py:1115-1126`.)

4. **`_ollama_tags_url` closes the proxy-path leak.** It rebuilds the URL from `(scheme, netloc, "/api/tags", "", "")`, discarding any path tail — so a `base_url` of `http://proxy/ollama/v1` becomes `http://proxy/api/tags`, not something that splices the proxied sub-path into the probe. The bare-host fallback is the only path that does string surgery, and it's reached only when there's no scheme+netloc to trust. `test_ollama_tags_url` covers the proxied case (ENG-601). (`model_advisor.py:224-234`.)

5. **`_installed_match` refuses false tag matches.** A `qwen2.5-coder:1.5b` install does not satisfy a `:7b` spec, and a `:1.5b-instruct` variant does not satisfy a `:1.5b` spec — only the implicit `:latest` default is tolerated. This is the kind of bug (treating any same-family tag as "installed") that silently recommends a model the box can't actually run; it's explicitly guarded and parametrically tested. (`model_advisor.py:289-302`, `test_installed_match`.)

6. **`friendly_label` prefers the longest (most specific) catalog match**, so a sibling tag can't shadow the right label, and returns `None` for unknown families rather than guessing. (`model_advisor.py:237-247`.)

7. **The bake-off makes the challenger earn the swap.** `compare_runs` switches the default only on a strictly higher graded rate, or an equal graded rate **and** faster; a tie-or-worse keeps the incumbent. The epsilon (`_GRADED_TIE_EPS = 1e-9`) stops a one-case float wobble from flipping the default on noise. The incumbent-absent and no-incumbent branches both refuse to auto-switch and say why. Flipping the configured default is left to a human — correct, matches the merge/tag boundary. (`bakeoff.py:46-129`.)

8. **Console safety is treated as a first-class invariant.** Every string that reaches the cp1252 Windows console — `HardwareProfile.summary`, `recommend(...).reason`, the whole bake-off table and every recommendation reason — is asserted `.isascii()` **and** `.encode("cp1252")`-safe in tests (`test_advisor_printed_strings_are_console_safe`, `test_did_not_clear_reason_is_console_safe`, `test_to_text_table_and_recommendation_are_console_safe`). The source comments flag the ASCII-only rule at each emission point.

9. **The cloud API key has a clean provenance.** Traced end to end: it enters at `POST /api/settings` (`webapp.py:1177-1183`, type-validated, trimmed, `None` clears it), is stored by `SettingsStore`, is read per-call by `_SettingsAwareProvider._active` (`webapp.py:399-424`), and is handed to `OpenAI(api_key=...)` (`llm_provider.py:183`). It is returned to the client **only** masked (`_mask_key`: 16 dots + last 5, and *nothing* for an implausibly short value so the last-5 can't expose most of it — `webapp.py:442-450`). There is no `logger`/`logging` anywhere in the model layer, and the only two `print()` calls (`llm_provider.py:301,360`) emit a vision hint and a backend *key name* + exception *type name* — never the key. **The key is never logged.**

10. **Model-down degrades to a typed status, not a 500.** The pipeline deliberately does **not** catch the connection/timeout error (documented at `pipeline.py:391-393`); the web layer owns it and maps it via `_is_model_unreachable` to `PipelineStatus.model_unavailable` + `MODEL_UNAVAILABLE_MESSAGE` with HTTP 200 (`webapp.py:1391-1406`). `_is_model_unreachable` duck-types by class name, so the pipeline needn't import the OpenAI client and a fake provider can raise a stand-in (`pipeline.py:158-161`). The `PlanParseError` path is separately mapped to `plan_failed` with a clean message and never masks an unrelated bug (only the parse boundary is wrapped — `llm_provider.py:227-230`, `pipeline.py:379-390`).

11. **`_SettingsAwareProvider` caps key-bearing provider objects.** The cloud-provider LRU is bounded to 4 (`webapp.py:388-389,420-421`), so rotating keys/models can't accumulate provider instances (each holding key material) for the process lifetime — a deliberate fix (ENG-005) to a real memory/secret-retention concern.

12. **Vision stays local even when cloud text is enabled.** `_SettingsAwareProvider.describe_photo` ignores the cloud route entirely and builds a dedicated **local** Ollama provider (`webapp.py:432-439`), enforcing the Slice-7 trust rule at the routing layer, not just by convention. The web photo endpoint wraps the whole vision call in a blanket catch that returns a clean 422 ("Couldn't read that photo"), never a 500 or a traceback (`webapp.py:1311-1333`).

---

## Candidates evaluated and declined (so they aren't re-chased)

These are the spots a thorough reviewer pokes. Each was checked and judged **not** a finding; recorded with the reasoning.

- **`LLMProvider.describe_photo`'s `urlopen` is not wrapped in try/except** (`llm_provider.py:295-296`), unlike the advisor probes. *Declined.* The only callers are (a) the web photo endpoint, which wraps the call in `except Exception → 422` (`webapp.py:1326`), and (b) `FallbackProvider.describe_photo`, which routes through `_call` (connection/timeout/404 → alt, else propagate). There is **no** CLI or unattended caller of `describe_photo` (grep confirms zero `photo`/`vision`/`describe_photo` references in `cli.py`). So the raw exception can never reach a user as a 500; the boundary owns it. Wrapping it inside the provider would be defensible defense-in-depth but is not required and would slightly blur the "transport error vs unreadable photo" distinction the current design keeps. Not even a Nit — it's a deliberate, correct division of responsibility.

- **`describe_photo` derives `/api/chat` from `self.backend.base_url`** (`llm_provider.py:264-269`) — could a non-local base_url send the photo off-machine? *Declined.* The trust rule is enforced one layer up: the only production path (`_SettingsAwareProvider.describe_photo`) constructs the provider from `llm_backend("local")`, whose base_url is the localhost Ollama, regardless of the cloud toggle. The directive explicitly states the trust rule is enforced by the caller, not here; the code matches that.

- **`mean_duration_s` averages `duration_s` over ALL outcomes, including non-completed ones, and `_rank_key` uses it as the final tiebreak** (`benchmark.py:206-210`, `bakeoff.py:46-50`). Could a 0-completion model that "failed fast" win on speed? *Declined.* The rank key is `(graded_success_rate, success_rate, -mean_duration_s)`. A 0-completion model has both leading keys at 0, so the speed tiebreak only ever decides between two models that are *equally* zero-quality — it can never elevate a non-functional model above a working one. `to_text` already prints `mean_s = "n/a"` for a 0-completion model and emits an explicit "completed 0/N — no axes could be graded" note (`bakeoff.py:171,176-179`). Correct as written.

- **`FallbackProvider` thread-local `on_alt` is never reset; a recovered primary isn't retried on a long-lived WSGI worker until the process recycles** (`llm_provider.py:336-341`). *Declined.* This is documented in the class docstring as an accepted trade-off for the power-user opt-in path, and it is the *right* default for a dead primary (a fresh thread/request retries the primary). The production web wiring uses `_SettingsAwareProvider` (per-call routing), not a long-lived `FallbackProvider` pinned to one thread, so the staleness window is narrow in practice. Acceptable; explicitly reasoned.

- **`FallbackProvider.__init__` mutates the passed-in primary's `max_attempts` to 1 in place** (`llm_provider.py:330-335`). *Declined.* The hazard (reusing one primary across constructions compounds the reduction) is called out in the comment, and the only constructor (`_real_provider`, `webapp.py:363-369`) builds a fresh `LLMProvider` per `FallbackProvider`. No live reuse exists. Worth keeping the comment; not a defect.

- **`recommend` can return a China-origin primary** when the only installed-and-fitting model is Qwen (`model_advisor.py:342-364`). *Declined per directive and on the merits.* This only happens when the user has *manually* pulled Qwen and nothing else fitting is installed; the non-China escape then steers them to gemma4 (`test_non_china_escape_names_gemma_when_only_a_china_model_is_installed`). This is the intended "surface a non-China alternative" behavior, not a defect.

---

## Coverage I relied on (and its altitude)

The Stage 6 engine is unit-tested at a high standard: `test_model_advisor.py` (purity, fits/RAM gating, installed-match matrix, URL-derivation matrix incl. the proxy case, malformed-body matrix, cp1252 safety, real-probe smoke) and `test_bakeoff.py` (switch/keep/tie logic, incumbent-absent, empty-runs raise, table console-safety, run_bakeoff wiring with a fake pipeline). These are **offline unit/contract** altitude — pure-function and mocked-I/O. The directive correctly notes the **live** bake-off (real Ollama, both models pulled) is the hand-off step and is not unit-tested; that is the right boundary for this module, but it means a release-readiness gate still needs a from-scratch live-assembled run to prove the wired pipeline actually plans/codegens/slices on the real model. That live altitude is out of this module's scope but is the one thing this static pass cannot certify.

## What I could not check

- I did not execute the test suite (audit-only pass) — coverage above is assessed from reading the test files, not from a green run.
- I did not run a live Ollama-down / garbage-Ollama scenario against the running web app; the graceful-degradation verdict is from tracing the code paths and the typed-status mapping, not from a live repro. A QA-role live pass should confirm the `model_unavailable` wall renders as designed.
- Dependency CVE scan (pip-audit) was not run in this pass; the model layer's only third-party import is the OpenAI SDK (via `_build_client`) and `pyyaml`/`pydantic` (elsewhere) — no obviously abandoned or pinned-vulnerable package in scope.
