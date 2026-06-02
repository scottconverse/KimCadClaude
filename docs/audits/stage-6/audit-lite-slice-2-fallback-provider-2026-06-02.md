# Audit Lite — Stage 6 Slice 2: tiered LLM fallback chain
**Date:** 2026-06-02
**Scope:** `src/kimcad/llm_provider.py` (`FallbackProvider` class), `src/kimcad/config.py` (`llm_alt_backend()`), `config/default.yaml` (`alt_backend: null`), `src/kimcad/cli.py` (`_build_pipeline` wiring), `src/kimcad/webapp.py` (`_real_provider` wiring), and `tests/test_fallback_provider.py` (16 cases).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two Minor fixes. The fallback chain does exactly what it claims: a dead primary (connection down, timeout, model not pulled) transparently retries against the alt, thread-local stickiness avoids re-trying the dead primary on every codegen retry call, and a missing alt lets the primary error propagate unchanged. Two real issues: `Pipeline.__init__` still declares `provider: LLMProvider` even though it now receives a `FallbackProvider`, and the webapp `_real_provider` path is not independently tested (only the CLI wiring is). Both are fixable in a few lines.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 2
- Nit: 1

## Findings

### FB-001 Minor: `Pipeline.provider` type annotation is stale after this change
**Dimension:** Docs / Correctness
**Evidence:** `src/kimcad/pipeline.py:217` — `provider: LLMProvider`. `_build_pipeline` (cli.py:144) now passes a `FallbackProvider` instance when an alt is configured. `FallbackProvider` does not inherit from `LLMProvider`; a static type checker (mypy) would flag every call site. More practically: a developer reading `Pipeline.__init__` gets a false picture of what the parameter accepts.
**Why it matters:** This is a docs/type-annotation gap, not a runtime defect — Python doesn't enforce the annotation. But it misleads type checkers and anyone extending the pipeline, and it will surface as a mypy error if the project adds strict type-checking.
**Fix path:** One of: (a) add `| FallbackProvider` to the annotation in `pipeline.py` (`provider: LLMProvider | FallbackProvider`), (b) define a `LLMProviderProtocol(Protocol)` in `llm_provider.py` with `generate_design_plan` and `generate_openscad`, and annotate `Pipeline.__init__` with that Protocol, or (c) annotate `provider: Any` with a comment. Option (b) is the cleanest for long-term extensibility; option (a) is the one-liner.

### FB-002 Minor: webapp `_real_provider()` fallback wiring has no dedicated test
**Dimension:** Tests
**Evidence:** `tests/test_fallback_provider.py` — two `_build_pipeline` wiring tests cover the CLI path (lines 267–354). No corresponding test covers `kimcad.webapp._real_provider()` (webapp.py:178–184). The logic is identical (4 lines), but the webapp path is not independently verified.
**Why it matters:** The CLI and webapp are different entry points. If `_real_provider` were edited to diverge (e.g., skipping `llm_alt_backend()`), no test would catch it. Given the webapp is the UI-facing path and concurrency matters more there (thread-local stickiness is the webapp's main concern), the test gap is real.
**Fix path:** Add one test: `test_real_provider_uses_fallback_when_alt_configured`. Mirror the structure of the `_build_pipeline` test but call `webapp._real_provider(cfg, None)` after patching `FallbackProvider` (or capture the return type directly). Two lines of additional assertion close the gap.

### FB-003 Nit: `FallbackProvider.generate_design_plan` return type annotation is `object`
**Dimension:** Docs
**Evidence:** `src/kimcad/llm_provider.py:241` — `-> object`. `_call` returns `object`, and `generate_design_plan` returns that. In practice it's always a `DesignPlan`; the annotation is weaker than the reality and doesn't match `LLMProvider.generate_design_plan -> DesignPlan`.
**Why it matters:** Annotation only; no runtime impact. But it weakens type inference for callers and breaks symmetry with `LLMProvider`.
**Fix path:** Either use `-> DesignPlan` and add an `assert isinstance(result, DesignPlan)` guard before return, or (more practically, since `_call` is generic) use `-> Any`. The `# type: ignore[return-value]` on `generate_openscad` already signals the same tension — both could be resolved if a Protocol approach (FB-001 option b) is taken.

## What's working
- **Fallback fires on the right errors and ignores the rest.** The `except (APIConnectionError, APITimeoutError, NotFoundError)` clause is correctly scoped: connection-down, timeout-after-retries, and model-not-pulled (404) all trigger the alt. Parse errors, `ValueError` from bad LLM JSON, and `RuntimeError` from codegen correctly propagate from primary — they're output problems, not connection problems, and the alt would produce the same bad output.
- **Fail-fast is implemented correctly.** `primary.max_attempts = 1` is set in `__init__` when an alt exists, so a dead Ollama fails in one attempt (~immediate connection refused) rather than 6 × 30 s ≈ 3 minutes. Without an alt, the primary keeps its full retry budget (the no-alt case has no stickiness or max_attempts reduction). Both paths are tested.
- **Thread-local stickiness is correct and tested.** Once a thread falls back, subsequent calls bypass primary (avoids 1-attempt timeout on every codegen retry). Separate threads start clean — `test_stickiness_is_thread_local` proves that a thread-B which sees no error uses primary, independent of thread-A's fallback state. This is the right behavior for both the CLI (single-thread, one run) and a forked-process WSGI server (each worker is independent).
- **Config wiring is clean and backward-compatible.** `alt_backend: null` in `default.yaml` means existing deployments see no change — `llm_alt_backend()` returns `None`, `_build_pipeline` and `_real_provider` hand a bare `LLMProvider` to `Pipeline`, and `FallbackProvider` is never constructed. No migration needed.
- **Warning goes to stderr, is ASCII, and names the alt backend key.** The print at `llm_provider.py:228` uses `file=sys.stderr` (not polluting stdout), is all-ASCII (cp1252-safe), and includes the alt's key for debuggability. Verified: no em-dashes or non-ASCII in any printed path.
- **Alt error propagates unchanged.** If the alt also fails, its error propagates — the `FallbackProvider` makes exactly one attempt on alt, with no catch. This is correct: two dead backends shouldn't silently swallow errors.
- **CLI and webapp wiring are symmetric.** `_build_pipeline` and `_real_provider` use identical 4-line patterns: build primary, read `llm_alt_backend()`, build alt if non-None, wrap in `FallbackProvider` if alt exists. No risk of one path wiring FallbackProvider differently from the other.

## Watch items
- **Long-lived thread pools and stickiness**: `_local.on_alt = True` is never reset. In a thread-pool WSGI server (e.g., Gunicorn `--workers=4 --threads=2`), a thread that fell back once stays on alt permanently until the process is recycled. If Ollama recovers mid-session, existing threads keep hitting the cloud alt until restart. Acceptable for the current scope (dev server, power-user feature), but worth documenting in a comment near `_local` so the behavior is explicit when a production WSGI deployment arrives.
- **`max_attempts = 1` mutation is side-effectful**: `FallbackProvider.__init__` mutates `primary.max_attempts` in place. In the current codebase, `LLMProvider` is always freshly constructed before being wrapped, so this is safe. If a future caller reuses a pre-existing `LLMProvider` across multiple `FallbackProvider` constructions, the mutation would compound. Harmless today; worth a comment flagging it.

## Escalation recommendation
No escalation needed. Both Minor findings are small (one annotation update, one ~5-line test addition). The logic is clean, the tests cover every meaningful path, and the design is sound. Fix FB-001 and FB-002, close to 0/0/0/0/0.

---

## Re-audit (resolution) — 0/0/0/0/0

- **FB-001 (Minor) — FIXED via the Protocol route.** A new `Provider(Protocol)` in `llm_provider.py:48` declares exactly the two methods the pipeline calls (`generate_design_plan`, `generate_openscad`) with their real types. `Pipeline.__init__` now annotates `provider: Provider` (`pipeline.py:217`), and the import is `from kimcad.llm_provider import Provider`. Both `LLMProvider` and `FallbackProvider` satisfy it structurally (no inheritance). Verified live: `inspect.signature(Pipeline.__init__)` shows `provider: Provider`, and `Provider` is a runtime Protocol. This matches the real contract — the pipeline needs the two methods, not a concrete class — exactly as preferred.
- **FB-002 (Minor) — FIXED.** Two webapp tests added: `test_real_provider_uses_fallback_when_alt_configured` and `test_real_provider_uses_bare_provider_when_no_alt`, mirroring the CLI pair. They call `webapp._real_provider(cfg, None)` directly and assert the wrapped/bare type. The user-facing path is now independently covered, so a future divergence in `_real_provider` would be caught.
- **FB-003 (Nit) — FIXED, fell out of the Protocol cleanup as predicted.** `FallbackProvider.generate_design_plan` now returns `DesignPlan` (not `object`), `generate_openscad` returns `str`, params are the real `Printer`/`Material`/`DesignPlan` types, and `_call` returns `Any` — which removed the `# type: ignore[return-value]` that had flagged the same tension. The two methods are now type-symmetric with `LLMProvider`'s.
- **Watch items addressed with one-line comments (no scope creep).** The thread-pool stickiness behaviour and the in-place `max_attempts` mutation each got a brief explanatory comment in `FallbackProvider.__init__` — no behavioural change, no new design.

Verified after the fixes: `tests/test_fallback_provider.py` **18 passed** (16 + 2 new webapp tests); full suite **535 passed**; ruff clean across all six changed files. **Roll-up: 0/0/0/0/0.**
