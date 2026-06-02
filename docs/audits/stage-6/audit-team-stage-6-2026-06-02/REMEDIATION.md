# Stage 6 — Remediation closure (audit-team → 0/0/0/0/0)

**Date:** 2026-06-02
**Branch:** `stage-6-model-swap`
**Start:** 0 Blocker / 1 Critical / 6 Major / 13 Minor / 11 Nit (31 findings)
**End:** **0/0/0/0/0** — every finding fixed (the project's fix-everything standard).

Each finding below maps to its fix + the verification. Gate after remediation: **609 pytest passed**
(incl. live OrcaSlicer), **37 vitest**, frontend build reproducible, ruff clean.

## Critical
- **DOC-001** — `docs/benchmarks/stage-6-model-bakeoff.md` rewritten to **lead with the verdict** (Qwen
  0/10 rejected, gemma stays, KEEP), with the real `output/bakeoff/bakeoff.txt` numbers replacing the
  Qwen-wins illustrative table, and the "this hand-off / live run needs a box" framing dropped (the run
  happened here). Now a "verdict + how to reproduce" doc, not "how to run an open comparison."

## Major
- **UX-001** — Web failure now reads as a failure: `ChatPanel` drives the assistant-row error tone from
  `isFailureStatus(result.status)` (plan/render/gate), and `RightPanel`'s Parameters + Printability cards
  show a distinct "no part was produced" branch instead of the never-tried-yet idle placeholder. New
  `designStatus.isFailureStatus` + a test; SPA rebuilt.
- **UX-002 / UX-006** — `Bakeoff.to_text` renders `n/a` (not `0/0`) for an axis with nothing assessed and
  `n/a` (not `0.0`) for the mean of a 0-completion model, plus an explicit "completed 0/N — no axes could
  be graded" note. Backend column width is now dynamic so the rows always align.
- **DOC-002** — HANDOFF title now matches the body ("ALL 5 SLICES DONE … pending the stage gate").
- **DOC-003** — HANDOFF no longer pins a stale head hash (`1928e13`); it says "the branch tip" (2 places).
- **DOC-004** — README documents `kimcad models` (advisory, never rewrites config) and `kimcad bakeoff`
  (compare backends; recommend-only), plus the gemma-stays / qwen-rejected decision.
- **DOC-005** — `config/default.yaml` `local_qwen` comment rewritten to past tense (evaluated 2026-06-02,
  rejected 0/10; gemma stays; retained as a selectable `--backend`).

## Minor
- **ENG-601** — `_ollama_tags_url` now uses `urllib.parse.urlsplit`/`urlunsplit` (scheme://netloc/api/tags),
  discarding any path tail; + 2 new parametrized cases (proxied sub-path).
- **ENG-602** — `bakeoff.Recommendation` renamed `BakeoffDecision` (no collision with
  `model_advisor.Recommendation`). The user-facing `"Recommendation:"` output label is unchanged.
- **UX-003** — `models` upgrade line softened: "a larger model that may plan better; run `kimcad bakeoff`
  to confirm … (the tiers here are heuristics, not measured)."
- **UX-004** — Bake-off uses one term: `(default)` tag + "the current default" reason (dropped the
  abbreviated `(def)` and the "incumbent" jargon).
- **UX-005** — `benchmark.py` per-case error line uses ASCII ` -- ` (was an em-dash) — the last runtime
  non-ASCII in the benchmark rollup is gone.
- **DOC-006** — HANDOFF's stale Stage-5 "NEXT = Stage 6 (model swap) … make it the default if it clears
  the bar" block replaced with a pointer to the authoritative Stage 6 section.
- **DOC-007** — A dated note added to the Slice-4 `audit-lite` report that its "doc is accurate" line
  predates the verdict and the doc has since been re-framed (DOC-001).
- **DOC-008** — "vision fallback" requalified as forward-looking ("a vision-capable model for the future
  Stage 9 image on-ramp") in the bake-off doc + HANDOFF; the `model_advisor` catalog "vision-capable" note
  was already factual and kept.
- **TEST-001** — `test_arbitrary_primary_error_propagates_and_skips_alt`: a `RuntimeError` from the primary
  propagates and alt is never called (pins the fallback narrowing's exclusivity).
- **TEST-002** — `test_bakeoff_does_not_mutate_config`: a full `_cmd_bakeoff` run leaves `config.raw`
  byte-identical (pins recommend-only / no-auto-apply).
- **TEST-003** — `test_pipeline_for_backend_is_bare_even_with_alt_configured`: the bake-off pipeline is a
  bare `LLMProvider` (not `FallbackProvider`) even with an alt configured (measurement isolation).
- **TEST-004** — `test_probe_installed_models_tolerates_a_malformed_body`: JSON list / nameless model /
  non-JSON 200 each yield `[]`, never raise.

## Nit
- **ENG-604** — `import os` moved to the `model_advisor.py` module top.
- **DOC-009** — `cli.py` docstring now says "Five subcommands" and lists `models` + `bakeoff`.
- **DOC-010** — HANDOFF gemma timing unified to ~10 min/prompt (per the 595.7 s artifact).
- **UX-007** — `models` installed list appends the friendly catalog label when a tag matches
  (`gemma4:e4b-it-q4_K_M  -- Gemma E4B`); new `friendly_label` + tests.
- **UX-008** — `bakeoff --help` dropped the hard-coded "= qwen vs gemma" gloss.
- **TEST-005** — `test_generate_design_plan_does_not_wrap_a_connection_error_as_plan_parse_error`: the real
  provider lets an `APIConnectionError` escape un-wrapped.
- **TEST-006** — degenerate advisor cases: `recommend()` → `primary is None`; `fits()`/`summary()` with a
  discrete GPU present (asserts the VRAM string renders and `.isascii()`).
- **TEST-007** — `main(["bakeoff", ...])` validation tests (missing prompts / <2 backends / unknown key →
  exit 2) + an advisor `summary()`/`reason` cp1252 + `.isascii()` pin.

## Accepted-by-design (no code change; recorded)
- **ENG-603** (broad `except Exception` in the best-effort RAM probe — correct for the contract),
  **ENG-605** (never-reset thread-local stickiness — the right call for a dead primary; a future
  `alt_backend` user-doc note is on the watchlist), **UX-009** (deliberate web/CLI tone split). Each role
  marked these "none required."

## Verification
- `python -m pytest tests` → **609 passed** (incl. live OrcaSlicer).
- `npm --prefix frontend run test` → **37 passed**; `run build` → reproducible (committed assets == fresh).
- `ruff check src/kimcad tests` → clean.
- Stale-framing grep across non-audit docs → clean (the lone `SWITCH default to local_qwen` match is a
  test asserting the SWITCH path, not doc framing).
- Live: `kimcad models` shows friendly labels + the softened upgrade; the bake-off table renders `n/a`
  for the degenerate qwen row with the zero-completion note.

**Roll-up: 0/0/0/0/0.** Ready for the native Windows gate (pre-push hook), merge, and tag `stage-6`.
