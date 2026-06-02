# Audit Lite — Stage 6 Slice 1: hardware/availability-aware model advisor
**Date:** 2026-06-02
**Scope:** `src/kimcad/model_advisor.py` (hardware + Ollama probes, the catalog, the pure `recommend()`), the `kimcad models` CLI command in `src/kimcad/cli.py`, and `tests/test_model_advisor.py` + the two `tests/test_cli.py` cases.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two small honesty fixes. The advisor does exactly what Scott asked: the model stays **choosable** (it only ever *prints* a recommendation — it never rewrites config or auto-switches), and it now **examines the machine + what's installed** to recommend the best model that actually fits, names an upgrade the box could pull, and surfaces a non-China alternative. The decision is pure and well-tested, the probes are genuinely best-effort (no path raises), and a real false-positive bug in `_installed_match` (a `:1.5b` install satisfying a `:7b` spec) was caught and fixed with a regression test. Two Minors, both honesty: a suggested alternative doesn't say it's not installed, and one catalog label asserts a model generation the tag doesn't support.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 2
- Nit: 1

## Findings

### ADV-001 Minor: the non-China alternative doesn't show whether it's installed
**Dimension:** Correctness / UX
**Evidence:** `model_advisor.py` `recommend()` sets `non_china_alternative` to the best-tier non-China local model that *fits* — it does not check whether it's installed. `cli.py` `_cmd_models` prints `Non-China local option: {label} [{name}]` with no install state. Verified live: on this box the advisor suggests `Llama 3.1 8B [llama3.1:8b]` as the non-China option, but `probe_installed_models` shows it is **not** installed (`gemma4:e4b`, `qwen2.5-coder:1.5b`, … are). The `upgrade` line already reads `ollama pull <name>`, so it's clear — only the non-China alternative is silent about needing a pull.
**Why it matters:** A user who reads "Non-China local option: Llama 3.1 8B" and switches `--backend` to it hits a dead end (the model isn't pulled). The advisor's whole job is to recommend what's *available*; suggesting an un-pulled model without saying so undercuts that.
**Fix path:** Carry an `installed: bool` on the alternative (or recompute it in the CLI) and print "(installed)" vs "(not installed — `ollama pull <name>`)" for the non-China option, the same way the primary and upgrade lines already convey it.

### ADV-002 Minor: the `gemma4:e4b` catalog label asserts an unverified model generation ("3n")
**Dimension:** Docs / Honesty
**Evidence:** `model_advisor.py:106` labels `gemma4:e4b` as **"Gemma 3n E4B"**. The repo's own source for this model — `config/default.yaml:29` — calls it only `gemma4:e4b  # on-device model (~4B effective)`; it never says "3n". The "3n" generation is an addition I can't verify from the tag (`gemma4`) or the config. (Scott's standing rule: don't assert facts you haven't verified.)
**Why it matters:** It's a display string, so low blast radius — but it's a stated fact about which model this is, and it's unsupported. The *tag* (`gemma4:e4b`) is what actually drives selection and is correct; the label shouldn't over-claim beyond it.
**Fix path:** Use a tag-faithful label that doesn't assert a generation number — e.g. `"Gemma E4B"` (matches the `e4b` suffix) — and let the `[gemma4:e4b]` tag shown alongside carry the precise identity.

### ADV-003 Nit: `_cmd_models` hardcodes the `"local"` backend key for the default probe URL
**Dimension:** Correctness
**Evidence:** `cli.py` `_cmd_models` derives the Ollama URL from `config.llm_backend("local").base_url`, falling back to `http://localhost:11434/v1`. A user whose local backend is keyed something other than `local` would get the localhost fallback rather than their configured URL.
**Why it matters:** Very low — the localhost fallback is correct for a standard Ollama, and `--base-url` overrides it. Only bites a non-standard local backend key.
**Fix path:** Optional: probe the *active* backend's `base_url` when it looks local (localhost/127.0.0.1), else the `local` key, else the default. Or leave it and rely on `--base-url`.

## What's working
- **Choosable + advisory-only, exactly as required.** `recommend()` and `_cmd_models` only compute and print; nothing writes config or changes the active model. The reminder ("the model is never hardwired… set `llm.active`/`model_name` or pass `--backend`") is printed verbatim. The model stays selectable.
- **The decision is pure and correctly ordered.** Best installed-and-fitting local model wins; a higher-tier model the box can run but hasn't pulled is surfaced as an `upgrade`; cloud is never primary when a local model fits; **unknown RAM does not claim a local fit** (it falls back to cloud rather than guess) — all covered by `test_model_advisor.py` (23 cases) including purity.
- **The `_installed_match` fix is real and tested.** A specific tag now must match exactly (`:1.5b` ≠ `:7b`, `:1.5b` ≠ `:1.5b-instruct`), with `:latest` tolerated. Without the fix the advisor claimed an un-installed model was installed — a runtime failure waiting to happen. The parametrized test pins it, and the live box now correctly reports `gemma4:e4b` (installed) rather than a phantom 7B.
- **Probes are genuinely best-effort.** `nvidia-smi` absent → `(None, None)`; Ollama down → `[]`; a non-dict `/api/tags` body → `[]`; per-OS RAM reads wrapped in `try/except → None`. Tests cover the Ollama-down and parse paths; the real `probe_hardware()` smoke test asserts it never raises.
- **Honest heuristics.** The RAM floors are labeled "conservative heuristics… not vendor specs" in the module docstring, and the origin/`non_china` flags (Alibaba/Google/Meta/DeepSeek) are factual. Catalog labels other than gemma (ADV-002) match their tags.
- **Console-safe.** All printed strings are ASCII (verified `.encode('cp1252')` succeeds), and the CLI additionally force-UTF8s stdout. No repeat of the benchmark cp1252 crash.

## Watch items
- `fits()` gates local models on RAM only; a discrete GPU's VRAM "only helps." A future high-VRAM/low-RAM box would be under-served (conservative, not wrong). Revisit if GPU-target users appear.
- The RAM floors and tiers are heuristics; the upcoming bake-off (the live Qwen-vs-gemma run on the target box) is where they get calibrated against reality.

## Escalation recommendation
No escalation needed. Small, self-contained slice; two Minor honesty fixes + one Nit. audit-team isn't warranted — the Stage 6 stage-end gate will cover the whole branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **ADV-001 (Minor) — FIXED, and deeper than first scoped.** The non-China escape now (a) only surfaces when the **primary is China-origin** (a `_non_china_escape` helper returns None when the pick is already non-China — fixing a redundant "non-China option" line that showed even when gemma was the pick), (b) **prefers an installed** non-China model over a higher-tier one that needs pulling (so the escape is usable now), and (c) carries `non_china_installed`, which the CLI prints as "(installed)" / "(not installed -- ollama pull X)". New tests: `test_no_non_china_alternative_when_primary_is_already_non_china`, `test_non_china_escape_prefers_an_installed_option`, plus the install-state assertion on the existing China-origin case. Verified live: with gemma (non-China) as the pick, the redundant line is gone.
- **ADV-002 (Minor) — FIXED.** The `gemma4:e4b` label is now `"Gemma E4B"` (tag-faithful; drops the unverified "3n" generation). The `[gemma4:e4b]` tag shown alongside carries the precise identity. Verified live.
- **ADV-003 (Nit) — FIXED.** `_cmd_models` now probes the **active** backend's URL when it looks local (localhost/127.0.0.1), else the conventional `local` backend, else the standard Ollama default — instead of hardcoding `local`.

Verified after the fixes: `tests/test_model_advisor.py` + `tests/test_cli.py` **49 passed**; ruff clean; `kimcad models` re-run live gives a clean, honest recommendation (Gemma E4B installed = pick; Qwen 7B = pull-to-upgrade; no redundant non-China line). **Roll-up: 0/0/0/0/0.**
