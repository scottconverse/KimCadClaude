# Stage 6 (model layer) — Principal Engineer deep-dive

**Audit date:** 2026-06-02
**Branch:** `stage-6-model-swap` (head `96033c2`), diffed against `main`
**Scope:** `model_advisor.py` (new), `bakeoff.py` (new), `llm_provider.py` (FallbackProvider + Provider Protocol + PlanParseError), `config.py` (`llm_alt_backend`), `cli.py` (`models`/`bakeoff` subcommands, `_pipeline_for_backend`, plan_failed handling), `webapp.py` (`_real_provider`), `pipeline.py` (plan_failed + wrapped `generate_design_plan`), `benchmark.py` (3-axis grading), `config/default.yaml` (`alt_backend`, `local_qwen`).
**Posture:** balanced — credit what's solid, flag every real issue with file:line + fix path + blast radius for Major+.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 2 |
| Nit      | 3 |
| **Total**| **5** |

**No Blockers, Criticals, or Majors.** Every load-bearing property in the audit charter was verified true, by reading the code and by running targeted runtime checks. The two Minors and three Nits are hygiene/robustness polish that do not block the gate.

---

## Verification performed (what I actually ran)

- **Full suite:** `.venv\Scripts\python.exe -m pytest tests -q` → **588 passed in 98.89s**, exit 0. Matches the expected baseline.
- **Lint:** `.venv\Scripts\python.exe -m ruff check src/kimcad` → **All checks passed!**
- **openai error taxonomy (the central correctness claim):** ran a Python check against the installed `openai==2.38.0`. `APIConnectionError`, `APITimeoutError`, and `NotFoundError` are **NOT** subclasses of any member of the wrapped parse-error set `(ValueError, TypeError, KeyError, AttributeError, ValidationError)`. MROs: `APIConnectionError → APIError → OpenAIError → Exception`; `NotFoundError → APIStatusError → APIError → OpenAIError → Exception`. A genuine network/transport error therefore can **never** be reclassified as `PlanParseError`. Verified.
- **FallbackProvider** (runtime, fake providers, no network): primary `max_attempts` reduced to 1 when an alt exists ✓; thread that fell back stays on alt for `generate_openscad` (the codegen retries) ✓; a fresh thread starts with `_on_alt=False` (retries primary) ✓; with no alt, the primary error propagates unchanged ✓.
- **`_complete` retry set:** `NotFoundError` propagates immediately from `_complete` (it is not in the `(APIConnectionError, APITimeoutError)` retry tuple), which is exactly what lets `FallbackProvider._call` catch the 404 and fail over. Verified at runtime.
- **model_advisor** (runtime): `recommend()` is pure (same inputs → same primary; inputs unmutated) ✓; `_installed_match` exact-tag — a `qwen2.5-coder:1.5b` install does **not** satisfy a `:7b` spec ✓; probes are best-effort (junk URL → `[]`, non-dict `/api/tags` body → `[]`, RAM-unknown → cloud fallback) ✓; non-China escape surfaces gemma when the primary is China-origin ✓.
- **bakeoff `compare_runs`** (runtime, all branches): a strictly-worse challenger never recommends a switch ✓; a strictly-better graded rate switches ✓; a tie on graded that is faster switches ✓; a tie that is slower keeps the incumbent ✓; an incumbent absent from the bake-off never auto-switches ✓; an empty `runs` list raises `ValueError` ✓; empty `BenchSummary` has no div-by-zero (`graded_success_rate=0.0`, `mean_duration_s=0.0`, `axis_tally=(0,0)`) ✓.
- **grade_correct_dimensions tri-state** (runtime): within-ceiling/no-gate → `None` (never asserts True from the ceiling alone); exceeds-ceiling → `False`; `dim.match` → `True`; `dim.mismatch` → `False`; no info → `None`. Ceiling is upper-bound-only. Verified.
- **Advisory-only / no config mutation** (grep): `model_advisor.py` does only read I/O (`open("/proc/meminfo")` read, `urllib.request.urlopen(.../api/tags)` GET); `bakeoff.py` has zero write/config-mutation hits. No `local.yaml` write, no `os.environ[...] =`, no `.active =`.
- **Dependencies:** `git diff main...stage-6-model-swap` on `pyproject.toml`/`requirements*`/`setup*` is **empty** — no new dependency added. `pydantic` and `openai` were already present.

---

## Findings

### ENG-601 (Minor / Correctness) — `_ollama_tags_url` discards a non-`/v1` path tail
**Evidence:** `src/kimcad/model_advisor.py:217-220`. The mapping splits on `"/v1"` and keeps only the host: `_ollama_tags_url("https://x/v1/foo")` → `https://x/api/tags`, silently dropping `/foo`; and a base_url with no `/v1` at all (`http://host:11434`) becomes `http://host:11434/api/tags` (correct by luck, since Ollama's native API is host-rooted).
**Why this matters:** For every real Ollama/LM-Studio base_url in the catalog and config (`http://localhost:11434/v1`, `http://127.0.0.1:11434/v1`) the mapping is exactly right, so this is purely advisory robustness, not a live defect — the `models` command points at a conventional local URL. The only way to reach the odd case is a hand-passed `--base-url` with a sub-path, which no documented flow produces.
**Fix path:** Optional. If hardening is wanted, parse with `urllib.parse.urlsplit` and reconstruct `scheme://netloc/api/tags` rather than string-splitting on `/v1`. Low priority.

### ENG-602 (Minor / Hygiene) — Name collision: two `Recommendation` dataclasses across the model layer
**Evidence:** `src/kimcad/model_advisor.py:118` defines `Recommendation` (hardware/model advisor verdict); `src/kimcad/bakeoff.py:38` defines a different `Recommendation` (bake-off switch decision). Same module package, same class name, two unrelated shapes.
**Why this matters:** No runtime bug today — they are never imported into the same namespace (the CLI imports each lazily inside its own command handler, and `recommend()`/`compare_runs()` return their own local type). But a future `from kimcad.model_advisor import Recommendation` alongside `from kimcad.bakeoff import Recommendation` would shadow silently, and the shared name makes the two concepts harder to grep/disambiguate.
**Fix path:** Rename one for clarity, e.g. `bakeoff.Recommendation → BakeoffDecision` (or `model_advisor.Recommendation → ModelRecommendation`). Pure rename; update the handful of internal references and tests. Defer-able; flag now so it doesn't ossify.

### ENG-603 (Nit / Robustness) — `_total_ram_gb` Windows branch trusts `GlobalMemoryStatusEx` without `ctypes` import guard symmetry
**Evidence:** `src/kimcad/model_advisor.py:137-174`. The whole body is wrapped in a single `try/except Exception → None`, so a missing `ctypes.windll` (non-CPython, e.g. a hypothetical PyPy-on-Windows) degrades to `None` correctly. This is fine — noting only that the best-effort contract is honored by the broad catch, which I confirmed at runtime returns a sane float on this Windows box.
**Fix path:** None required. The broad `except Exception` is the right call for a best-effort probe per the module's stated contract.

### ENG-604 (Nit / Hygiene) — `import os` is function-local in `probe_hardware`
**Evidence:** `src/kimcad/model_advisor.py:205` imports `os` inside `probe_hardware()` while the module already imports `json`, `platform`, `subprocess`, `urllib.*` at top level.
**Why this matters:** Cosmetic only. `os.cpu_count()` is the single use. The local import avoids nothing here (os is always available).
**Fix path:** Move `import os` to the module top with the other stdlib imports. Trivial.

### ENG-605 (Nit / Docs-in-code) — FallbackProvider thread-local stickiness is never reset (documented, but worth a one-line operational note in the CLI/web wiring)
**Evidence:** `src/kimcad/llm_provider.py:259-264` and the class docstring at `:232-248`. On a long-lived WSGI/`ThreadingHTTPServer` worker thread, once that thread falls back to alt it stays on alt until the process recycles — a recovered primary isn't retried on that thread. This is **explicitly documented** in the code as an accepted trade-off for "this power-user opt-in path," and the default config ships `alt_backend: null` (so the fallback chain is off unless a user opts in).
**Why this matters:** Not a defect — it's a deliberate, documented design choice and the right one for a dead-primary scenario (the alternative, re-probing a dead primary on every call, is what the design exists to avoid). Flagging only so the eventual user-facing fallback docs mention "a recovered primary resumes on the next fresh worker / restart," so an operator isn't surprised that a web session stays on cloud after Ollama comes back.
**Fix path:** None in code. A sentence in the (future) `alt_backend` user doc.

---

## What's working (specific, honest)

- **The central safety property is airtight.** The plan-failure path is built exactly the way you'd want: the network call (`_complete`) sits **outside** the try, and only `parse_design_plan(normalize_plan_dict(json.loads(...)))` is wrapped (`llm_provider.py:204-210`). The wrapped set `(ValueError, TypeError, KeyError, AttributeError, ValidationError)` is provably disjoint from the openai transport-error hierarchy (verified against `openai==2.38.0`). `pipeline.run` catches **only** `PlanParseError` (`pipeline.py:291-302`) and re-raises nothing broader. A real `APIConnectionError`/`APITimeoutError`/`NotFoundError` propagates and is not masked as a "model too small" plan failure. This is the kind of narrow, intentional error boundary that prevents the worst class of debugging nightmare (a transport outage misreported as a model-quality problem).
- **Advisory-only is real, not aspirational.** Both new modules are side-effect-free with respect to config. `model_advisor` does read-only probing; `bakeoff` does zero writes. `recommend()` and `compare_runs()` are pure and I confirmed it at runtime (idempotent output, unmutated inputs). The "flipping the default is Scott's call" boundary is enforced by simply not having a code path that writes config — the cleanest possible enforcement.
- **No fallback contamination in the bake-off.** `_pipeline_for_backend` (`cli.py:176-184`) deliberately builds a **bare** `LLMProvider`, never a `FallbackProvider`, with an explicit comment explaining why (a silent fallback would swap in the other model mid-run and poison the comparison). Each model is measured in isolation. Exactly right.
- **FallbackProvider thread-locality is correct and well-reasoned.** Stickiness keeps a fallen-back request on alt for its remaining codegen retries (no re-eating the primary's retry budget per call); a fresh thread retries primary; `primary.max_attempts` is reduced to 1 only when an alt exists, with an in-place-mutation safety note that holds because the pipeline builders construct a fresh primary per `FallbackProvider`. The fall-back trigger is narrow and correct — only connection/timeout/404, not arbitrary errors.
- **The 3-axis grading is honest about what it measured.** Tri-state `None` axes are excluded from the denominator (`axis_tally`, `benchmark.py:199-204`) and never block `graded_passed` (`benchmark.py:63-75`). `grade_correct_dimensions` treats the prompt's `max_bbox_mm` as an upper bound only — it can flip a verdict to `False` but never asserts `True` on its own (a grossly-undersized part also fits under a ceiling). The done-gate (`--min-success-rate`) still scores on completion (`meets`, `benchmark.py:218-219`), preserving backward-compatibility, while the bake-off compares the stricter graded rate. The separation of "did it finish" from "is it good" is the correct model.
- **bakeoff decision logic makes the challenger earn the swap.** A worse model is never recommended; ties break on speed; an incumbent that isn't in the bake-off triggers no auto-switch (with a clear reason telling the operator to re-run including the incumbent). Empty input raises rather than silently returning a bogus recommendation. All branches verified at runtime.
- **Probes degrade gracefully under every failure I threw at them** — missing binary, Ollama down, junk URL, non-dict JSON body, unreadable meminfo — each returns the "unknown"/empty sentinel, never an exception. The `_probe_nvidia_gpu` argv is a fixed list (`["nvidia-smi", "--query-gpu=...", ...]`) with no shell, so there is no shell-injection surface; the Ollama probe URL is derived from a config base_url, not user input on the hot path.
- **Clean CLI ergonomics:** the `bakeoff` and `models` commands validate backends/URLs up front and persist results to disk **before** printing (so a cp1252 console-encoding error can't discard a multi-minute CPU run — `cli.py:362-366`, `:312-314`). Fail-fast on a typo'd backend key. Distinct exit code (6) for plan_failed vs gate_failed (5).
- **Test coverage is substantial and targeted:** +281 lines `test_bakeoff.py`, +395 `test_fallback_provider.py`, +230 `test_benchmark.py`, +186 `test_model_advisor.py`, +87 `test_pipeline.py`, +28 `test_llm_provider.py`. 588 tests pass. The pure decision functions are unit-tested without a live model, which is exactly the right testability seam.

---

## What I could not check (called out per role guidance)

- **No live model run.** This audit did not run a real Ollama bake-off (gemma vs qwen) — that needs a box with both models pulled and is ~10 min/prompt of CPU, out of scope for a code audit. The model decision (gemma stays, qwen ruled out) is treated as settled per the charter and was not re-litigated.
- **No real-hardware print.** Out of scope (post-release per project plan).
- The `gemma` ~10-min/prompt CPU latency is a known target-box limitation, not a Stage 6 defect, and was not flagged.

---

## Gate recommendation (engineering lens)

From the engineering side, **Stage 6 is merge-ready.** Zero Blocker/Critical/Major findings. The load-bearing properties — advisory-only, no fallback contamination, narrow error boundary that doesn't mask transport failures, pure decision functions, honest tri-state grading — all hold under both reading and runtime verification. The two Minors (ENG-601 URL-tail, ENG-602 dataclass name collision) and three Nits are polish that can land in a hygiene pass; none gate the merge. Full suite green (588/588), ruff clean.
