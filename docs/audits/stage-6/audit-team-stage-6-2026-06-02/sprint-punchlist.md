# Stage 6 — Sprint Punch List

Every finding, sorted by severity. Owner-hint = the role that surfaced it. All are remediated this sprint (fix-everything standard) before merge + tag.

## Critical
- [ ] **DOC-001** (Docs) — Re-frame `docs/benchmarks/stage-6-model-bakeoff.md`: add a verdict section at the top (Qwen 0/10 rejected, gemma stays / KEEP), replace the Qwen-wins worked example with the real `output/bakeoff/bakeoff.txt` (or label it clearly illustrative), drop "that's this hand-off" (the run happened here).

## Major
- [ ] **UX-001** (UI/UX) — Drive the web assistant-row tone from `result.status` for `plan_failed`/`render_failed`/`gate_failed`; give the Parameters + Printability cards a distinct "failed" branch instead of the idle placeholder. Rebuild SPA.
- [ ] **UX-002** (UI/UX) — Bake-off `to_text`: render `n/a` (not `0/0`) for an axis with `assessed==0`; add a zero-completion note.
- [ ] **DOC-002** (Docs) — HANDOFF title → "Stage 6 ALL 5 SLICES DONE … pending the stage gate" (match the body).
- [ ] **DOC-003** (Docs) — HANDOFF: replace head `1928e13` (2 places) with the branch tip / current head.
- [ ] **DOC-004** (Docs) — README: document `kimcad models` + `kimcad bakeoff` + the model decision.
- [ ] **DOC-005** (Docs) — `config/default.yaml` `local_qwen` comment → past tense (evaluated 2026-06-02, rejected 0/10; gemma stays; retained as a selectable `--backend`).

## Minor
- [ ] **ENG-601** (Eng) — `_ollama_tags_url`: parse with `urllib.parse.urlsplit` and reconstruct `scheme://netloc/api/tags` instead of splitting on `/v1`.
- [ ] **ENG-602** (Eng) — Rename `bakeoff.Recommendation` → `BakeoffDecision` (avoid the collision with `model_advisor.Recommendation`).
- [ ] **UX-003** (UI/UX) — Soften the `models` upgrade line: "a larger model that may plan better — run `kimcad bakeoff` to confirm" (stop asserting an unmeasured quality gain).
- [ ] **UX-004** (UI/UX) — Bake-off: one term for the incumbent — `(default)` tag + "the current default" reason (drop "incumbent" jargon, drop the abbreviated `(def)`).
- [ ] **UX-005** (UI/UX) — `benchmark.py` per-case error line: `f" -- {o.error}"` (ASCII, not the em-dash).
- [ ] **UX-006** (UI/UX) — Bake-off: `mean_s` → `n/a` when a backend completed 0 cases (don't imply "fast").
- [ ] **DOC-006** (Docs) — HANDOFF Stage-5 section: replace the stale "NEXT = Stage 6 (model swap) … make it the default if it clears the bar" block with a pointer to the authoritative Stage 6 section.
- [ ] **DOC-007** (Docs) — Add a dated one-line note to the Slice-4 audit-lite report that the bake-off doc was re-framed after the live run (the closure's "doc accurate" line predates the verdict).
- [ ] **DOC-008** (Docs) — "vision fallback" → forward-looking ("a vision-capable model for the future Stage 9 image on-ramp") in HANDOFF, the bake-off doc, and `model_advisor.py`'s catalog note.
- [ ] **TEST-001** (Test) — Add a negative test: an arbitrary primary exception (`RuntimeError`) propagates and alt is NOT called.
- [ ] **TEST-002** (Test) — Pin bake-off no-config-mutation (snapshot `config.raw` before/after `run_bakeoff`).
- [ ] **TEST-003** (Test) — Test `_pipeline_for_backend` builds a bare `LLMProvider` (not `FallbackProvider`) even with an `alt_backend` configured.
- [ ] **TEST-004** (Test) — Test `probe_installed_models` malformed-body paths (JSON list / no `name` / non-JSON) → `[]`, never raises.

## Nit
- [ ] **ENG-604** (Eng) — Move `import os` to the module top in `model_advisor.py`.
- [ ] **DOC-009** (Docs) — `cli.py` docstring: "Five subcommands" + add `models` / `bakeoff`.
- [ ] **DOC-010** (Docs) — HANDOFF: unify gemma timing to ≈10 min/prompt (per the 595.7 s artifact).
- [ ] **UX-007** (UI/UX) — `models` installed list: append the friendly catalog label when a tag matches.
- [ ] **UX-008** (UI/UX) — `bakeoff --help`: drop the hard-coded "= qwen vs gemma" gloss from the `--backends` default.
- [ ] **TEST-005** (Test) — Test the real `LLMProvider.generate_design_plan` does NOT wrap an `APIConnectionError` as `PlanParseError`.
- [ ] **TEST-006** (Test) — Add the degenerate advisor cases (`recommend()` → `primary is None`; `fits()`/`summary()` with a discrete GPU present, asserting `.isascii()`).
- [ ] **TEST-007** (Test) — Add `main(["bakeoff", ...])` validation tests (no prompts file / <2 backends / unknown key → exit 2) + an advisor `summary().encode("cp1252")` / `reason.isascii()` pin.

## Accepted-by-design (no change; rationale recorded)
- **ENG-603 / ENG-605 / UX-009 (Nit)** — the broad `except Exception` in the best-effort RAM probe (correct for the contract), the never-reset thread-local stickiness (the right call for a dead primary; a future `alt_backend` user-doc sentence covers it — see watchlist), and the deliberate web/CLI tone split (conversational vs diagnostic). Each role marked these "none required"; recorded here so the acceptance is explicit, not an oversight.
