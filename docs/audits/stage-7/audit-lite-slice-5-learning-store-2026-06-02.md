# Audit Lite — Stage 7 Slice 5: Smart Mesh learning store + comparison line
**Date:** 2026-06-02
**Scope:** `src/kimcad/history.py` (the store + `compare_phrase`), `Config.history_path()`, the `Pipeline` history wiring (`_apply_history_comparison` / `_record_history` + the `record_history` gate), the CLI/web entrypoint injection, and the tests (`test_history.py`, +3 in `test_pipeline_readiness.py`). Honesty + privacy weighted heavily.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two Minors, both honesty-of-wording. The store is exactly the right shape: local-first JSON in the per-user home (never the repo), a coarse record (no geometry/prompt), best-effort everywhere (every degrade path returns cleanly and is tested), recorded once per fresh design and never on a slider drag, and compared against *prior* records so the line can't rank a part against itself. No test writes to the real home — verified every `HistoryStore` in the suite is `tmp_path`-scoped. The two Minors are both about the comparison *copy* overstating: "Below all N" fires when the score actually *ties* priors (not strictly below), and "prints" overstates what's really a set of designed (sometimes gate-failed, never-actually-printed) *parts*.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)".

**As found:** 0 Blocker · 0 Critical · 0 Major · 2 Minor · 0 Nit.

## Findings

### SLICE5-001 Minor: "Below all N" overstates when the score ties priors rather than beating none
**Dimension:** Correctness (honesty)
**Evidence:** `history.py` `compare_phrase` computes `beaten = sum(1 for s in scores if s < score)` and renders the `beaten == 0` branch as "Below all N of your past {scope} — worth a closer look." But `beaten == 0` means *no prior is strictly less* — which includes the case where some or all priors **equal** the score. So building the same part repeatedly at a stable score (e.g. the gate-pass score 92 three times, then a 4th identical 92) yields `beaten == 0` → "Below all 3 … worth a closer look," when the part is in fact *identical*, not worse. Reachable in the most common workflow there is: iterating on one part at a steady score.
**Why it matters:** The owner's hard rule is never to overclaim a fact. "Below all" is a factual misstatement when the part ties its predecessors, and it nudges the user to "take a closer look" at a part that's exactly as good as before — eroding trust in the very signal the card exists to provide.
**Fix path:** Split the strictly-below case from the ties case. Compute `behind = sum(1 for s in scores if s > score)`; reserve "Below all N" for `behind == n` (every prior strictly higher), and for the `ahead == 0` ties case emit a neutral "On par with your past {scope}." Add a test: priors all equal to the score → an "on par" line, not "below all."

### SLICE5-002 Minor: "prints" overstates — the store holds designed parts, some gate-failed and none necessarily printed
**Dimension:** Correctness (honesty) / Docs (user-facing copy)
**Evidence:** `compare_phrase` words the scope as "{object_type} prints" / "prints" and `_apply_history_comparison` appends "your local print history" to the attribution. But the store records every build that reaches `_assemble_result` — including **gate-FAILED** parts (which a user would never print) — and KimCad's output is a *sliceable part*, not a print (real printing is post-release at Kim's, per the spec). So "your past prints" claims printed output the user almost certainly never produced.
**Why it matters:** Same honesty rule. Telling a user "stronger than 7 of your 9 past prints" when they've printed nothing — and several of those nine failed the gate — overstates. "Parts" (or "designs") is accurate and unambiguous.
**Fix path:** Reword "prints" → "parts" in `compare_phrase`'s scope and "your local print history" → "your local build history" in the attribution. Update the existing wording assertions. (Recording gate-failed parts is *fine* and honest once they're called "parts," not "prints" — it gives a truthful score distribution; no need to filter them out.)

## What's working
- **Best-effort is real and exhaustively tested.** `load` returns `[]` on missing/corrupt/non-list JSON and skips a malformed record (keeping the rest); `record` swallows `OSError` on an unwritable path (parent-is-a-file test); `comparison` rides on `load`. In the pipeline, `_apply_history_comparison` wraps the store read in `try/except Exception` and `_record_history` wraps the whole record in `try/except Exception`, with `max(report.actual_bbox_mm) if report.actual_bbox_mm else 0.0` guarding an empty bbox. Every "never breaks a build" claim is backed by a test.
- **Honest by construction (where it counts).** No history → `comparison` returns `None`, so the card invents no baseline. "A personal best" fires only on a strict beat of every prior (`beaten == n`); a tie at the top correctly falls to "Stronger than B of N" (tested). The two Minors above are the residual wording edges, not a systemic overclaim.
- **Privacy / local-first is sound.** The store is plain local JSON; the default path is `~/.kimcad/history.json` — per-user, outside the repo tree (so it can't be committed), persisting across projects. The record is coarse: type, score, gate, material, largest dimension, a timestamp — no prompt, no geometry, no file path. Nothing is transmitted anywhere.
- **No test or dev-home pollution.** Verified by grep: every `HistoryStore` constructed in the suite is `tmp_path`-scoped; the default `Pipeline(history=None)` means the many direct-construction tests write nothing; the CLI tests monkeypatch `_build_pipeline`; the demo web pipeline is `history=None`. No test path reaches `HistoryStore(config.history_path())`, so the real `~/.kimcad` is never touched and the suite stays deterministic.
- **Correct recording semantics.** Recorded once per fresh `run`, never on a `rerender` (the `record_history` gate), and the comparison is computed *before* recording, so it ranks against prior parts — not against the part itself. Pinned by `test_history_comparison_folds_in_and_the_build_is_recorded` (store grows to 3, the new score is the last record) and `test_rerender_does_not_record_history` (store stays at 1 across two drags).
- **Console-safe.** The attribution suffix is ASCII; the comparison strings reuse the em-dash already pervasive in `PrintReport.to_text`, which the CLI prints through `_force_utf8_output(sys.stdout)` (and persists to `summary.txt` as UTF-8) — so no new encoding hazard, consistent with the shipped to_text. The web card renders the string as UTF-8 JSON.
- **No frontend change needed.** The card (Slice 4) and `to_text` (Slice 3) already render `comparison` when present; Slice 5 only populates it. The `MeshReadiness` mutation is valid (it's a non-frozen dataclass).

## Watch items
- **`paths.history` could be pointed into the repo.** A relative `paths.history` resolves against `PROJECT_ROOT`, so a user *could* configure the store into the repo tree and then commit it. The default is safe (home dir); noting only because the override has no guard. If you want it bulletproof, warn (or refuse) when the resolved path is under the repo.
- **The comparison appears on the initial design only, not on a live-slider drag.** That's the right call (a drag re-ranking against the part's own just-saved parent would be noise), but it means dragging a slider leaves the *previous* comparison line on screen until the next fresh design. Confirm in Slice 6/stage-end that the card doesn't show a stale comparison after a drag changed the score materially (the rerender payload's readiness has `comparison: null`, so the card should clear it — verify the card binds to the new value, not a retained one).

## Escalation recommendation
No escalation needed. Two wording-level honesty Minors on an otherwise clean, private, well-tested, best-effort store. Fix both and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team covers the full branch (including the stale-comparison-on-drag watch item).

---

## Re-audit (resolution) — 0/0/0/0/0

- **SLICE5-001 (Minor) — FIXED.** `compare_phrase` now splits strictly-below from ties: `ahead = sum(s < score)`, `behind = sum(s > score)`; "A personal best" requires `ahead == n`, "Below all N" requires `behind == n` (every prior strictly higher), and the `ahead == 0` ties case reads "On par with your N past {scope}." — never "below." New test `test_compare_phrase_says_on_par_when_it_ties_priors_without_beating_any` (3 priors all at the score → "On par", not "Below all", not "personal best").
- **SLICE5-002 (Minor) — FIXED.** "prints" → "parts" throughout `compare_phrase`, and the attribution suffix is now "and your local build history" (source tag "build-history"), since the store holds designed parts (some gate-failed, none necessarily printed). Wording assertions in `test_history.py` and the attribution assertion in `test_pipeline_readiness.py` updated accordingly.

Verified: `tests/test_history.py` **13 passed** + `tests/test_pipeline_readiness.py` **13 passed** (26 total); ruff clean on history.py/pipeline.py. **Roll-up: 0/0/0/0/0.**
