# Audit Lite — Stage 7 Slice 1: Smart Mesh readiness model + scoring
**Date:** 2026-06-02
**Scope:** `src/kimcad/smart_mesh.py` (the `PrintProofReport`/`PrintProofIssue` typed input, `Risk`/`MeshReadiness`, and the pure `assess_readiness` synthesis) + `tests/test_smart_mesh.py` (12 cases).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one Major. The readiness synthesis is honest, pure, and well-tested — it never claims a part is "Ready to print" over a visible risk, it credits "KimCad printability gate" (not the engine or history) when no engine ran, and scoring is monotonic. The one real gap: `assess_readiness` derives the verdict from the gate status + its own severity penalties but **ignores PrintProof3D's own `status`** — so a PrintProof3D `fail` whose worst issue is only `major` could render as "Printable with notes," a card contradicting the validation engine it cites. Plus two Nits and a small test gap.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 1
- Nit: 2

## Findings

### SM-001 Major: the verdict ignores PrintProof3D's own `status`, so the card can contradict the engine
**Dimension:** Correctness / Honesty
**Evidence:** `smart_mesh.py:120-156`. The verdict is computed from `gate_status`, `score`, and `has_fail_risk` only — `printproof.status` ("pass"/"warning"/"fail") is never read; PrintProof3D contributes solely through per-issue penalties and risk tone (`:137-144`). So a report with `status="fail"` whose worst issue is `severity="major"` (penalty 18 → score 92−18=74) yields verdict "Printable with notes" while the engine's overall verdict is `fail`. The card attributes itself to "PrintProof3D validation engine" yet can disagree with it.
**Why it matters:** On a UX-first, honesty-first product, the readiness card must not be more optimistic than the validation engine it names as its source. Re-deriving the verdict purely from KimCad's penalty weights assumes PrintProof3D's status↔severity mapping matches those weights; it may not. Trusting the engine's explicit status is the robust, honest design.
**Fix path:** Fold `printproof.status` into the verdict floor: a PrintProof3D `fail` forces "Not print-ready" (tone fail); a `warning` forces at least "Printable with notes." Keep the existing gate/score/risk logic as the other inputs (take the worst of the two). Add tests: (a) `status="fail"` with only a `major` issue → "Not print-ready"; (b) `status="warning"` on an otherwise-clean part → "Printable with notes."

### SM-002 Minor: the `_gate_risk_title` unknown-code fallback is untested
**Dimension:** Tests
**Evidence:** `smart_mesh.py:106-113` falls back to the first clause of the finding message (truncated) when a gate code isn't in `_GATE_RISK_TITLE`. Every test uses a known code (`wall.thin`, `dim.mismatch`, `dim.match`), so the fallback branch — including the truncation — is unexercised. A future gate code would hit untested code on the user-facing risk title.
**Why it matters:** The risk title is user-facing; an unmapped code is exactly when the fallback runs, and it's the path with the truncation logic (and the ellipsis of SM-003).
**Fix path:** Add a test with an unknown code and a long message, asserting the title is the message's first clause and is truncated sanely.

### SM-003 Nit: non-ASCII "…" ellipsis in a risk title that can reach the cp1252 console
**Dimension:** Correctness (console-safety convention)
**Evidence:** `smart_mesh.py:112` — `return (head[:48] + "…")` uses U+2026. Risk titles flow into the print report and the UI; the report is printed to a Windows cp1252 console. "…" is cp1252-representable (byte 0x85) so it won't crash, but the repo's standing convention is ASCII-only for strings that can be printed, and every other producer uses `...`/`--`.
**Fix path:** Use `"..."`.

### SM-004 Nit: `_confidence` takes `gate_status` but never uses it
**Dimension:** Correctness (dead parameter)
**Evidence:** `smart_mesh.py` `_confidence(printproof, mesh_unanalysable, gate_status)` is called with `gate_status` (`:167`) but the body only branches on `mesh_unanalysable` and `printproof`. The parameter is dead.
**Fix path:** Drop the unused `gate_status` parameter (or use it — but confidence is about *how much validation backed the verdict*, not the verdict itself, so dropping it is correct).

## What's working
- **The synthesis is honest about what backed it.** A clean PASS with no engine → confidence "Medium" and attribution "KimCad printability gate"; the "your local print history" half of the attribution is correctly withheld until the learning store lands (Slice 5), and `comparison` is `None`. No path fabricates engine/history backing — verified by the gate-only tests.
- **"Ready to print" is never shown over a risk.** Any risk (gate WARN/FAIL or a PrintProof3D major+) drops a clean pass to "Printable with notes," and a fail-tone risk or sub-50 score forces "Not print-ready" (`:148-156`). The `test_printproof_major_issue_folds_in...` and `_blocker_makes_it_not_print_ready` cases pin this.
- **Scoring is monotonic and clamped.** Penalties only subtract; `max(0, min(100, score))` bounds it; `test_score_is_clamped_to_0_100` proves a pile of blockers floors at 0, never wraps or raises.
- **The typed PrintProof3D model matches the engine schema.** `status` (pass/warning/fail), `confidence_level` (free-form string), and `issues[]` (id/message/severity[blocker..nit]/suggested_fixes, + region from `IssueLocation`) line up with `validation_report.schema.json`; it's a deliberate, correct subset (model metadata / profile names aren't needed for synthesis) that the Slice-2 wrapper can fill without rework.
- **Clean decoupling.** `assess_readiness` is pure (no I/O) and imports only `printability` (GateResult/Level) + `validation` (MeshReport); neither imports `smart_mesh`, so the pipeline → smart_mesh direction has no cycle.
- **Tests pin behavior, not tautology.** The nit-not-a-risk, dedupe, no-material-rec-on-fail, and purity cases would each fail if the logic were inverted.

## Watch items
- **`minor` PrintProof3D issues surface as a "warn" risk and drop "Ready to print" → "Printable with notes."** Defensible (a note is a note), but as PrintProof3D's issue set grows, watch that low-value minors don't make every part read "with notes." Revisit the `_PP_RISK_TONE` minor mapping if the card gets noisy.
- The score anchors (92/70/38) and penalties are reasonable seeds; once real PrintProof3D reports + the Slice-5 history land, calibrate them against actual outcomes rather than leaving them as first-guess constants.

## Escalation recommendation
No escalation needed. One Major (gate the verdict on the engine's own status), one Minor test gap, two Nits — all local to a new, pure module. Fix and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team covers the whole branch.

---

## Re-audit (resolution) — 0/0/0/0/0

- **SM-001 (Major) — FIXED.** The verdict tone is now the **worst of two signals**: KimCad's own (gate/score/risk) tone and PrintProof3D's own `status` (`fail`→fail, `warning`→warn). A PrintProof3D `fail` report now forces "Not print-ready" regardless of how its penalties landed; a `warning` forces at least "Printable with notes." New tests `test_printproof_fail_status_forces_not_ready_even_with_only_a_major_issue` and `test_printproof_warning_status_drops_a_clean_pass_to_with_notes` pin both; the existing pass/blocker cases still hold (their status values were already consistent).
- **SM-002 (Minor) — FIXED.** `test_unknown_gate_code_uses_the_message_head_as_the_risk_title` exercises the unmapped-code fallback with a long message, asserting the title is the message's first clause, truncated to ≤51 chars with `...`, and ASCII.
- **SM-003 (Nit) — FIXED.** The truncation ellipsis is now ASCII `"..."` (was U+2026), keeping risk titles cp1252-safe for the CLI report.
- **SM-004 (Nit) — FIXED.** `_confidence` no longer takes the unused `gate_status` parameter.

Verified: `tests/test_smart_mesh.py` **15 passed**; ruff clean. **Roll-up: 0/0/0/0/0.**
