# Audit Lite — Stage 7 Slice 3: Smart Mesh readiness in the pipeline + design API
**Date:** 2026-06-02
**Scope:** `src/kimcad/pipeline.py` (the `_compute_readiness` method, the `report.readiness` wiring in `_assemble_result`, the `PrintReport.readiness` field + `to_text` block, new imports), `src/kimcad/webapp.py` (`_readiness_payload` + the `readiness` key in `_report_payload`), and `tests/test_pipeline_readiness.py` (8 cases as-found, 10 after remediation).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two Minors. The wiring is correct and safe: readiness is computed on the **final hardened mesh** for every built part, rides on the mutable `PrintReport` so both the gate-failed and completed paths expose it, and the deterministic slice gate is **completely untouched** — Slice 3 only adds an advisory verdict. The PrintProof3D call is bed-positioned on a *copy* and wrapped so it can never break the build, and attribution degrades honestly when the engine isn't there. The two real gaps are both narrow: (1) when the optional engine is configured, it runs synchronously on *every* live-slider re-render — a latency cliff for an opt-in path; (2) the new `to_text` readiness block has no test. Neither blocks; both are quick closes.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)" at the bottom for how each was closed.

**As found:** 0 Blocker · 0 Critical · 0 Major · 2 Minor · 0 Nit.

## Findings

### SLICE3-001 Minor: PrintProof3D runs synchronously on every live-slider re-render
**Dimension:** Correctness / UX (performance)
**Evidence:** `pipeline.py:423` calls `_compute_readiness` from the shared `_assemble_result` tail, which `rerender` (`pipeline.py:547`) also flows through. When `config.printproof3d_binary()` is configured (`pipeline.py:482-492`), `_compute_readiness` exports a temp STL and runs `validate_model` — a subprocess with a 120 s timeout — *inside* the re-render. The web re-render endpoint debounces a drag to ~150 ms; with the engine on, each debounced drag would block on a fresh subprocess. By default the engine is **not** configured (and the binary isn't on disk), so `printproof3d_binary()` returns `None` and this path is skipped — re-renders stay snappy. The cliff only appears once an operator opts the engine in.
**Why it matters:** Live sliders are the headline UX of the template path; a synchronous deep-validation subprocess per drag would make them feel broken the moment the engine is enabled. It's off-by-default today, so no user is exposed yet — but it's a latent UX regression that must be fixed *before* the engine ships enabled, not after.
**Fix path:** Make the engine opt-out of the hot re-render path: give `_compute_readiness` a `run_engine: bool = True` flag (or a dedicated `_compute_readiness_fast`), pass `run_engine=False` from `rerender` so drags compute the instant gate-only readiness, and run the full engine validation once on the initial design (and/or behind an explicit "deep-check" action). The card already attributes honestly ("KimCad printability gate" / Medium) when the engine didn't run, so a gate-only readiness on drags is consistent, not misleading.

### SLICE3-002 Minor: the new `PrintReport.to_text()` readiness block is untested
**Dimension:** Tests
**Evidence:** `pipeline.py:181-194` adds a `Readiness: <score>/100 — <verdict> …` block plus per-risk / per-recommendation / comparison lines to `to_text()`. The existing `to_text` tests (`test_pipeline.py:176, 395, 463`) assert on size and slice/G-code content; none exercise the readiness branch. The new `test_pipeline_readiness.py` tests the dataclass field and the API payload, but not the human-readable render.
**Why it matters:** `to_text` is the CLI's user-facing print report. New display branches that no test pins can silently regress (a wrong f-string, a dropped line) without any suite failing — and the repo has a standing console-safety rule that an untested print path can't guard.
**Fix path:** Add one test that runs a completed build and asserts `report.to_text()` contains `"Readiness:"`, the verdict string, and — on a part with a risk — a `"Risk:"` line. Cheap, and it locks the format.

## What's working
- **The slice gate is genuinely untouched.** `report.readiness` is set at `pipeline.py:423`, strictly *before* the unchanged `if gate.status is Level.FAIL and not proceed_anyway: return` at `:425`. The advisory verdict rides alongside the deterministic authority without touching it — a gate-FAILED part is still not sliced, `proceed_anyway` still behaves identically, and the readiness on a failed/override part honestly reads "Not print-ready." The safety invariant holds.
- **Never-breaks-the-build is real, and tested.** The mesh-copy + `apply_translation` + temp-export + `validate_model` are all inside the `try/except Exception` at `pipeline.py:484-494`; a degenerate mesh (`bounds` None), an export error, or any engine fault degrades to `printproof=None`. `test_printproof3d_failure_never_breaks_the_build` injects a raising `validate_model` and confirms the build still completes on the gate-only verdict. `validate_model` itself was already proven never-raises in Slice 2.
- **Bed-positioning is correct and non-destructive.** `bed = hardened.copy(); bed.apply_translation(-bed.bounds[0])` puts the min-corner at the bed origin (trimesh `bounds[0]` is the min corner) on a *copy*, so the shipped `.oriented.stl` artifact is untouched and the slicer still positions it itself. The engine's positional checks get a valid bed-frame; its geometric checks are translation-invariant. `test_printproof3d_validates_a_bed_positioned_mesh_and_folds_in` loads the exact STL handed to the engine and asserts `min ≈ (0,0,0)` per-component — a real assertion, not vacuous.
- **Honest attribution, no over-claim.** When the engine is absent *or* degraded to `None`, `_attribution`/`_confidence` (smart_mesh) return "KimCad printability gate" / "Medium"; only a real engine report yields "PrintProof3D validation engine" / "High". The never-breaks test pins the degrade case to the gate attribution, so the card can't imply the engine validated when it didn't.
- **Stable, None-safe API contract.** `_report_payload` always emits a `readiness` key (`webapp.py`), `None` when absent, via `getattr(report, "readiness", None)` — so the Slice-4 frontend binds to a fixed shape. The payload carries exactly what a card needs (score, verdict, tone, confidence, risks[title/detail/tone], recommendations, comparison, attribution). `readiness` rides on `PrintReport`, a mutable `@dataclass`, so the late `report.readiness = …` assignment is valid and both result paths expose it.
- **Console-safety is consistent, not newly hazardous.** The added `to_text` lines reuse the em-dash already present in the existing `to_text` (`:165`, alongside `×`/`mm³`); the CLI force-UTF8s stdout. No new class of hazard — same convention the report already used.

## Watch items
- **Card vs. export affordance must be reconciled in Slice 4.** A PrintProof3D `fail` verdict can make the card read "Not print-ready" while the deterministic KimCad gate still PASSes, leaving the part sliceable/downloadable. For Slice 3 (pipeline + API) the *data* is correct and honestly attributed; the *UX* reconciliation — graying/penalizing the export when `readiness.tone == "fail"`, or a proceed-anyway-style confirm — is Slice 4's call. Flagging now so the card and the export button don't silently disagree.
- **`assess_readiness` sits just outside the never-raises guard** (`pipeline.py:495`). It's a pure function over the same `gate` + `mesh_report` the pipeline already built the report and made slice decisions from — so on any reachable input it can't raise. Noting only because the stated contract is "readiness must never break the build"; if you want it airtight, widen the guard to wrap the `assess_readiness` call too.
- **The engine runs even on a gate-FAILED part** (readiness is computed before the early return). That's a deliberate, useful choice — a failed part gets a richer "why" on its card — but it does spend a subprocess on a part that's already blocked. Fine while the engine is off-by-default; revisit if the SLICE3-001 fix lands so the failed-part case also stays cheap.

## Escalation recommendation
No escalation needed. Two narrow Minors on a correct, safety-preserving, well-tested wiring slice; the deterministic gate authority is intact and the engine boundary degrades cleanly. Fix both and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team covers the whole branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **SLICE3-001 (Minor) — FIXED.** `_compute_readiness` gained a `run_engine: bool = True` flag; the `rerender` path passes `run_engine=False`, so a live-slider drag computes the instant gate-only readiness and never spawns a subprocess, while the initial `run` keeps the full engine validation. New test `test_rerender_does_not_run_the_engine` injects a `validate_model` that fails the test if called and asserts a re-render still produces a gate-only readiness.
- **SLICE3-002 (Minor) — FIXED.** New test `test_to_text_renders_the_readiness_block` runs a completed build and asserts `to_text()` contains `"Readiness:"`, the verdict, and (on a part with an engine-surfaced risk, via an injected report) a `"Risk:"` line.

Verified: `tests/test_pipeline_readiness.py` **10 passed**; `test_pipeline.py` + `test_pipeline_templates.py` + `test_webapp.py` green; ruff clean. **Roll-up: 0/0/0/0/0.**
