"""#27 (KC-22): the diff-coverage gate.

CHANGED lines (vs a base branch) must be **>= 80% covered overall**, and any single source module
with **>= 20 changed lines** must be **>= 70% covered**. This wraps `diff-cover` (which maps the git
diff onto a coverage.xml and reports per-file changed-line coverage) and adds the per-module floor,
the threshold a single file must clear so a big well-covered diff cannot mask one untested module.

Coverage is scoped to the kimcad package by running the suite with `pytest --cov=kimcad`, so changed
tests/, scripts/, and docs don't count toward (or against) the threshold: only shipped library code.

Usage:
    python scripts/check_diff_coverage.py [coverage.xml] [--compare-branch origin/main]

Exits non-zero (and names the under-covered modules) when the change is under-covered; exits 0 when
no covered-package lines changed vs the base (nothing to gate).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

GLOBAL_MIN = 80.0
MODULE_MIN = 70.0
MODULE_MIN_CHANGED = 20


def _changed_lines(stat: dict) -> int:
    """Changed lines in a file = covered changed lines + uncovered (violation) changed lines."""
    return len(stat.get("covered_lines", [])) + len(stat.get("violation_lines", []))


def evaluate(report: dict) -> list[str]:
    """Pure check: return human-readable failure strings (empty list == pass) for a diff-cover
    JSON report. Kept side-effect-free so it can be unit-tested with synthetic reports."""
    failures: list[str] = []
    total_lines = report.get("total_num_lines", 0) or 0
    total_pct = report.get("total_percent_covered", 100)
    if total_lines > 0 and total_pct < GLOBAL_MIN:
        failures.append(
            f"overall changed-line coverage {total_pct:.1f}% < {GLOBAL_MIN:.0f}% "
            f"({total_lines} changed lines)"
        )
    for path, stat in sorted(report.get("src_stats", {}).items()):
        changed = _changed_lines(stat)
        pct = stat.get("percent_covered", 100)
        if changed >= MODULE_MIN_CHANGED and pct < MODULE_MIN:
            failures.append(f"{path}: {pct:.1f}% < {MODULE_MIN:.0f}% ({changed} changed lines)")
    return failures


def run_diff_cover(coverage_xml: str, compare_branch: str) -> dict:
    """Run diff-cover against the coverage XML + base branch and return its JSON report."""
    with tempfile.TemporaryDirectory() as td:
        report_path = Path(td) / "diff-cover.json"
        proc = subprocess.run(
            [sys.executable, "-m", "diff_cover.diff_cover_tool", coverage_xml,
             "--compare-branch", compare_branch, "--json-report", str(report_path),
             "--fail-under", "0"],
            capture_output=True, text=True,
        )
        if not report_path.exists():
            raise RuntimeError(f"diff-cover produced no report:\n{proc.stderr or proc.stdout}")
        return json.loads(report_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diff-coverage gate (#27 / KC-22).")
    ap.add_argument("coverage_xml", nargs="?", default="coverage.xml",
                    help="path to the coverage XML (default: coverage.xml)")
    ap.add_argument("--compare-branch", default="origin/main",
                    help="base ref to diff against (default: origin/main)")
    args = ap.parse_args(argv)
    # Skip cleanly when the base ref isn't resolvable (e.g. a shallow checkout, or the self-hosted
    # CI running on push where main already equals HEAD): there is nothing meaningful to diff,
    # and a missing base must not hard-fail the gate.
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", args.compare_branch],
                      capture_output=True).returncode != 0:
        print(f"[diff-cov] SKIP: base ref {args.compare_branch!r} not available to diff against.")
        return 0
    try:
        report = run_diff_cover(args.coverage_xml, args.compare_branch)
    except (RuntimeError, OSError, ValueError) as e:
        print(f"[diff-cov] could not run diff-cover: {e}", file=sys.stderr)
        return 1
    if (report.get("total_num_lines", 0) or 0) == 0:
        print(f"[diff-cov] OK: no covered-package lines changed vs {args.compare_branch} - "
              "nothing to gate.")
        return 0
    failures = evaluate(report)
    if failures:
        print(f"[diff-cov] FAIL: changed kimcad code is under-covered (need >= {GLOBAL_MIN:.0f}% "
              f"overall, >= {MODULE_MIN:.0f}% per module of >= {MODULE_MIN_CHANGED} changed lines):")
        for f in failures:
            print("  - " + f)
        print("  Add tests covering the changed lines, or factor out genuinely untestable code.")
        return 1
    print(f"[diff-cov] OK: changed-line coverage {report.get('total_percent_covered'):.1f}% "
          f"(>= {GLOBAL_MIN:.0f}%); every changed module >= {MODULE_MIN:.0f}%.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
