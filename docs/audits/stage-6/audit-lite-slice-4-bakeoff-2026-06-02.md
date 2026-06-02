# Audit Lite — Stage 6 Slice 4: model bake-off harness
**Date:** 2026-06-02
**Scope:** `src/kimcad/bakeoff.py` (`ModelRun`/`Recommendation`/`compare_runs`/`Bakeoff`/`run_bakeoff`), the `kimcad bakeoff` subcommand + `_pipeline_for_backend` + `_cmd_bakeoff` in `src/kimcad/cli.py`, the `local_qwen` backend in `config/default.yaml`, `docs/benchmarks/stage-6-model-bakeoff.md`, and `tests/test_bakeoff.py` (13 cases).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after two small fixes. The bake-off machinery is sound: the decision logic is pure and correct (no path recommends a switch to a worse model), the harness never mutates config (it only recommends — the human flips the default), each model is measured in isolation with no fallback contamination, and validation fails fast before burning CPU. Two issues, both minor: two of the `compare_runs` reason strings use em-dashes (non-ASCII — cp1252-encodable so no crash, but they break the module's own ASCII convention and those exact reason paths have no cp1252 test), and the `to_text` table applies its column widths to the wrong sub-token so the data rows don't line up with the header. One Minor + one Nit.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 1
- Nit: 1

## Findings

### BAKE-001 Minor: two `compare_runs` reason strings contain em-dashes (non-ASCII), and those paths have no cp1252 test
**Dimension:** Correctness / Tests
**Evidence:** `bakeoff.py:88` (incumbent-absent reason) and `bakeoff.py:125` (challenger-did-not-clear reason) both embed a literal `—` (U+2014). Confirmed live: `compare_runs(..., incumbent="zzz").reason` and the did-not-clear reason each report `reason.isascii() == False` with a `—` in the set. These reasons surface to the user through `Recommendation.reason`, which `Bakeoff.to_text` prints. The em-dash *is* representable in cp1252 (byte 0x97), so it won't crash a Windows console the way the old `≥` glyph did — but the rest of the module uses ASCII `--` (`to_text:163`), the `to_text` docstring advertises "cp1252-safe," and the two existing `to_text` tests only exercise the SWITCH reason and the "already the best" KEEP reason — neither em-dash-bearing path is encode-tested. If a future edit replaces one of these em-dashes with a genuinely non-cp1252 glyph (`≥`, `→`, `×`), nothing would catch it.
**Why it matters:** Console-safety is a load-bearing repo rule (the benchmark crashed on a non-cp1252 glyph once already), and new code should hold the ASCII line the module otherwise keeps. The untested reason paths are the real gap: a console-safety-sensitive string with no test is exactly how the prior crash slipped in.
**Fix path:** Replace the two `—` with ` -- ` (matching `to_text`'s own style) in `bakeoff.py:88` and `:125`. Add a cp1252 `.encode()` assertion to a test that hits the incumbent-absent and did-not-clear reasons (e.g. extend `test_no_switch_when_incumbent_absent_from_the_bakeoff` and add a did-not-clear case), so both reason strings are covered.

## What's working
- **The switch decision is correct and conservative.** `compare_runs` only sets `switch=True` when the challenger strictly beats the incumbent on the 3-axis graded rate (`bakeoff.py:96`) or ties the graded rate and is faster (`:109`); every other path keeps the incumbent. There is no path that recommends switching to a worse model — verified by reasoning over `_rank_key` (a challenger can only be `best` if its graded rate ≥ the incumbent's) and by the test matrix (switch/keep/tie-faster/graded-win-while-slower/incumbent-absent/none/empty). A challenger genuinely has to earn the swap.
- **The ranking key is sound.** `(graded_success_rate, success_rate, -mean_duration_s)` ranks on quality first, then completion, then speed (negation makes faster rank higher). No divide-by-zero or empty-summary hazard: `BenchSummary.mean_duration_s`, `success_rate`, and `graded_success_rate` all guard `total == 0 → 0.0`, so a zero-case or all-error run compares sanely rather than throwing.
- **No config mutation — recommend-only, as required.** Nothing in `bakeoff.py` or `_cmd_bakeoff` writes `config/*.yaml` or changes the active model; `_cmd_bakeoff` writes only `output/bakeoff/bakeoff.txt` (an artifact). The to_text footer and the hand-off doc both state plainly that flipping the default is the human's call. This matches the "harness recommends, Scott decides" contract (the same posture as never auto-merging/tagging).
- **No fallback contamination.** `_pipeline_for_backend` (`cli.py`) builds a bare `LLMProvider` for the named backend — explicitly *not* a `FallbackProvider` — with a comment explaining that a silent fallback would swap in the other model mid-run and corrupt the comparison. This is the right call and it's documented at the seam.
- **Fail-fast validation.** `_cmd_bakeoff` rejects `<2` backends and any unknown backend key *before* building a pipeline, listing the configured backends on the unknown-key error. Verified live: `--backends local` and `--backends nope,local` both error cleanly with no model call. Given a real bake-off is tens of minutes of CPU, failing on a typo'd key up front is the right ergonomics.
- **No output-dir collisions.** Each backend renders into `out_root/<backend>/<case-id>/` (`run_bakeoff:189`), so the two models' artifacts can't clobber each other, and the summary persists to `out_root/bakeoff.txt` at the root. Run order and the `model_name` mapping are preserved (test asserts `[r.backend ...] == ["local_qwen", "local"]`).
- **`slice_for_grade` defaults True for the bake-off** (`run_bakeoff:175`) — correctly stronger than the plain benchmark — and is threaded to `make_case_runner` so the slices-clean axis is actually graded; the `--no-slice` escape and the with/without-slice `confirm_print` pass-through are both tested.
- **Honest, accurate hand-off doc.** `docs/benchmarks/stage-6-model-bakeoff.md` matches the code: the default backends, slice-by-default, the decision rule, the persist-before-print behavior, the CPU-cost warning (minutes/prompt), and the human config-flip step (`llm.active` in `local.yaml`/`default.yaml`) are all stated accurately, with the "keep gemma as the non-China alternative" note intact.
- **The `_GRADED_TIE_EPS = 1e-9` epsilon is correct.** Graded rates are ratios of small integers (k/10); a real one-case difference is 0.1, eight orders of magnitude above the epsilon, so it's never swallowed. The epsilon only collapses exact float ties (0.8 == 0.8), which is its purpose.

## Watch items
- **`max(runs, key=_rank_key)` resolves an exact all-axes tie by list order** (first backend wins `best`). In the CLI that's the first `--backends` entry. It's harmless — an exact tie routes to the keep-incumbent branch (the challenger isn't strictly better and isn't faster), so `best` being the challenger doesn't produce a misleading SWITCH — but worth remembering if a future caller reads `Recommendation.best` directly rather than `switch`.
- **A backend whose model isn't pulled** scores 0 (each case raises → `status="error"` → not completed), which correctly makes it lose the bake-off rather than crashing the run. The hand-off doc already tells the user to pull both models; no code change needed.

## Findings (Nits)

### BAKE-002 Nit: `to_text` column widths are applied to the wrong sub-token, so rows don't align with the header
**Dimension:** UX
**Evidence:** `bakeoff.py:157-158` — `f"{s.passed}/{s.total:<7}"` left-justifies `s.total` *alone* in 7 columns (yielding e.g. `10/10     `), not the `passed/total` pair as a unit; same for `{mr_n:<4}` etc. The header (`:>9` right-justified) and the data therefore don't line up. Confirmed live: the `completed`/`graded`/`match` data columns sit slightly off their headers. The table is still readable, just not crisp.
**Fix path:** Format the token first, then pad the whole thing — e.g. `completed = f"{s.passed}/{s.total}"; ... f"{completed:>9}"` — so each data cell uses the same width and justification as its header.

## Escalation recommendation
No escalation needed. The decision logic — the part that actually matters for choosing the default model — is correct, pure, and well-tested; the two findings are a console-convention/test-gap (Minor) and a cosmetic table-alignment (Nit). The Stage-6 stage-end `audit-team` will cover the whole branch. Fix BAKE-001 + BAKE-002 and re-audit to 0/0/0/0/0.

---

## Re-audit (resolution) — 0/0/0/0/0

- **BAKE-001 (Minor) — FIXED.** The two em-dashes are replaced with ` -- ` (`bakeoff.py` incumbent-absent and did-not-clear reasons), so every `compare_runs` reason is now ASCII. Coverage added: `test_no_switch_when_incumbent_absent_from_the_bakeoff` now asserts `reason.isascii()` + `.encode("cp1252")`, a new `test_did_not_clear_reason_is_console_safe` exercises and encode-checks the did-not-clear path, and `test_to_text_table_and_recommendation_are_console_safe` now asserts the whole `to_text` output `.isascii()`. Verified live: both reason paths report `isascii() == True`.
- **BAKE-002 (Nit) — FIXED.** `to_text` now formats each cell as a whole token (`completed`, `graded`, `match`, `dims`, `slc`) and pads it to the header's width + right-justification, so the data columns line up under their headers. Verified live: the rendered table is column-aligned.

Verified after the fixes: `tests/test_bakeoff.py` **14 passed**; ruff clean; `to_text` output is ASCII and column-aligned. **Roll-up: 0/0/0/0/0.**

---

**Note added 2026-06-02 (post live run) — re: the "Honest, accurate hand-off doc" credit above.** That
line was correct when written: the doc accurately described how to *run* a then-unrun comparison. The
bake-off was then run live and `qwen2.5-coder:1.5b` was rejected (0/10), and the stage-end `audit-team`
flagged that the hand-off doc had gone stale (it still framed the swap as open and showed an illustrative
table where Qwen *won*) — finding **DOC-001** in
`docs/audits/stage-6/audit-team-stage-6-2026-06-02/`. `docs/benchmarks/stage-6-model-bakeoff.md` has since
been re-framed to lead with the verdict (gemma stays). This historical Slice-4 report is left as-is; the
re-framed doc supersedes the "accurate" credit.
