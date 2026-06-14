# Audit Lite — #27 (KC-22) diff-coverage gate
**Date:** 2026-06-14
**Scope:** The changed-line coverage gate: `scripts/check_diff_coverage.py` (new), `tests/test_check_diff_coverage.py` (new), the `.github/workflows/pr-smoke.yml` wiring, the `scripts/ci.sh` pointer comment, the `CONTRIBUTING.md` section, and the `pyproject.toml` / `requirements.lock` dependency additions.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. A small, self-contained CI gate that enforces changed-line coverage on incoming PRs (>= 80% overall, >= 70% for any module with >= 20 changed lines). It lives in the **hosted PR smoke** — the only place with a PR base to diff against — and fails open (clean SKIP) when the base ref can't be resolved, so an infra hiccup never blocks all PRs. One Minor finding (the subprocess wrapper and `main()` dispatch were untested) was found and **fixed in this pass**; the script is now at 98% line coverage (only the `__main__` entrypoint guard is uncovered, correctly).

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

(One Minor was surfaced and remediated within this pass — see Finding 001. Final state is 0/0/0/0/0.)

## Findings

### FINDING-001 Minor (RESOLVED in this pass): `run_diff_cover()` and `main()` had no automated coverage
**Dimension:** Tests
**Evidence:** The original `tests/test_check_diff_coverage.py` had 5 tests, all against the pure `evaluate()`. `run_diff_cover()` (the diff-cover subprocess invocation + the "no report produced" `RuntimeError` path) and `main()` (the base-ref skip guard, the nothing-to-gate path, and the pass/fail dispatch) were exercised only end-to-end by the gate itself, with no unit test.
**Why it matters:** A regression in the skip-guard (e.g. failing closed and blocking every PR) or the report-parse path would not be caught by the suite — only by a live PR failing. The standing rule is that changed logic carries a test.
**Fix path (done):** Added 7 tests covering both `run_diff_cover()` branches (parses the JSON diff-cover writes; raises with diff-cover's stderr when no report is produced) and all of `main()` (skip on unresolvable base ref, pass on zero changed lines, fail on under-coverage, pass on good coverage, non-zero exit when diff-cover itself errors). Script line coverage is now 98% (12 tests; only the `if __name__ == "__main__"` line is uncovered).

## What's working
- **Correct placement.** The gate runs in `pr-smoke.yml`, which checks out with `fetch-depth: 0` and has `origin/<base_ref>` to diff against. The self-hosted gate runs on push to `main` (where `main == HEAD`, nothing to diff) and correctly does **not** run diff-coverage — `scripts/ci.sh` documents this and the local self-check command.
- **Fails open, deliberately.** `main()` probes the base ref with `git rev-parse --verify --quiet` and SKIPs (exit 0) when it's unresolvable, so a shallow checkout or a missing remote ref can never hard-fail the gate. Documented in both the script and CONTRIBUTING.
- **Honest about the hermetic measurement.** Coverage in the PR smoke is the `-m "not live"` subset, so a line reachable only by a live tool test reads as uncovered. CONTRIBUTING calls this out explicitly ("keep diff-coverable logic unit-testable") rather than hiding it — no false sense of coverage.
- **Scoped to shipped code.** `pytest --cov=kimcad` means changed `tests/`, `scripts/`, and docs don't count toward or against the threshold — only `src/kimcad`, which is what the gate is meant to protect.
- **No injection surface.** `subprocess.run([...])` is called with argv lists (never `shell=True`); `compare_branch` originates from the workflow / local dev, not untrusted PR content.
- **Pure, testable core.** `evaluate()` is side-effect-free over a synthetic report shape, which is why the threshold logic (global floor, per-module floor, the >= 20-changed-line exemption, zero-changed pass) is exhaustively unit-tested.
- **ASCII-clean** per the project's console discipline; ruff clean.

## Watch items
- **Fail-open is a coverage gate, not a security gate.** If `origin/<base_ref>` ever silently stops resolving in CI (e.g. a checkout-action behavior change), the gate would SKIP green and stop enforcing — without an obvious signal. The SKIP line is printed, but nobody reads green logs. If diff-coverage enforcement becomes load-bearing, consider asserting the base ref *is* resolvable in the PR context and only fail-open for the local self-check. Not worth doing now (the gate is advisory belt-and-suspenders on top of the full self-hosted gate).

## Escalation recommendation
No escalation needed. The change is small, self-contained, CI-only (touches no shipped `src/kimcad` runtime path), verified end-to-end (live FAIL verdict + clean SKIP), and now fully unit-tested.
