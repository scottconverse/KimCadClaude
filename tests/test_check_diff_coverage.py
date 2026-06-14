"""#27 (KC-22): the diff-coverage gate's threshold logic. Unit-tests the pure `evaluate()` over
synthetic diff-cover reports (no git/coverage needed); the live diff-cover run is exercised by
the gate itself (scripts/ci.sh STRICT path + the hosted PR smoke)."""
import importlib.util
import json
from pathlib import Path

import pytest


class _Proc:
    """Minimal subprocess.run() return stand-in (only the fields this script reads)."""

    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_diff_coverage.py"
_spec = importlib.util.spec_from_file_location("kimcad_check_diff_coverage", _SCRIPT)
cdc = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(cdc)


def _report(total_pct, total_lines, files):
    """Build a diff-cover-shaped report. `files` maps path -> (percent, covered_count, violation_count)."""
    return {
        "total_percent_covered": total_pct,
        "total_num_lines": total_lines,
        "src_stats": {
            p: {
                "percent_covered": pct,
                "covered_lines": list(range(cov)),
                "violation_lines": list(range(cov, cov + viol)),
            }
            for p, (pct, cov, viol) in files.items()
        },
    }


def test_passes_when_changed_code_is_well_covered():
    assert cdc.evaluate(_report(95.0, 40, {"src/kimcad/a.py": (95.0, 38, 2)})) == []


def test_fails_below_the_global_80_floor():
    fails = cdc.evaluate(_report(75.0, 40, {"src/kimcad/a.py": (75.0, 30, 10)}))
    assert any("overall" in f and "80" in f for f in fails)


def test_fails_a_big_module_below_70_even_when_global_passes():
    # Global 82% passes the overall floor, but one module at 60% with 25 changed lines fails the
    # per-module floor; a fully-covered module alongside it is not flagged.
    fails = cdc.evaluate(_report(82.0, 60, {
        "src/kimcad/big.py": (60.0, 15, 10),  # 25 changed lines @ 60% -> fail
        "src/kimcad/ok.py": (100.0, 35, 0),
    }))
    assert any("big.py" in f and "70" in f for f in fails)
    assert not any("ok.py" in f for f in fails)


def test_small_under_covered_module_is_exempt_under_20_changed_lines():
    # A module with <20 changed lines at low coverage is NOT failed (the per-module floor only
    # applies at >= 20 changed lines), so a 1-line tweak to a rarely-hit branch doesn't block.
    fails = cdc.evaluate(_report(85.0, 30, {
        "src/kimcad/tiny.py": (50.0, 5, 5),  # 10 changed lines -> exempt
        "src/kimcad/rest.py": (100.0, 20, 0),
    }))
    assert not any("tiny.py" in f for f in fails)


def test_no_changed_covered_lines_is_a_pass():
    assert cdc.evaluate({"total_num_lines": 0, "total_percent_covered": 0, "src_stats": {}}) == []


# --- run_diff_cover(): the diff-cover subprocess wrapper ---------------------------------------

def test_run_diff_cover_parses_the_json_report_diff_cover_writes(monkeypatch):
    written = {"total_percent_covered": 91.0, "total_num_lines": 12, "src_stats": {}}

    def fake_run(argv, capture_output=False, text=False):
        # diff-cover writes its JSON to the path passed after --json-report; emulate that.
        out = Path(argv[argv.index("--json-report") + 1])
        out.write_text(json.dumps(written), encoding="utf-8")
        return _Proc(returncode=0)

    monkeypatch.setattr(cdc.subprocess, "run", fake_run)
    assert cdc.run_diff_cover("coverage.xml", "origin/main") == written


def test_run_diff_cover_raises_when_diff_cover_produces_no_report(monkeypatch):
    # If diff-cover errors and never writes the report file, the wrapper must surface a clear
    # error (carrying diff-cover's stderr) rather than blow up on a missing file.
    monkeypatch.setattr(cdc.subprocess, "run",
                        lambda *a, **k: _Proc(returncode=2, stderr="diff-cover exploded"))
    with pytest.raises(RuntimeError, match="diff-cover exploded"):
        cdc.run_diff_cover("coverage.xml", "origin/main")


# --- main(): the base-ref skip guard + the pass/fail dispatch -----------------------------------

def _git_ref(returncode):
    """A subprocess.run patch that answers the `git rev-parse --verify` probe with `returncode`."""
    return lambda *a, **k: _Proc(returncode=returncode)


def test_main_skips_cleanly_when_the_base_ref_is_unresolvable(monkeypatch, capsys):
    monkeypatch.setattr(cdc.subprocess, "run", _git_ref(1))  # ref not found
    assert cdc.main(["coverage.xml", "--compare-branch", "origin/nope"]) == 0
    assert "SKIP" in capsys.readouterr().out


def test_main_passes_when_no_covered_lines_changed(monkeypatch, capsys):
    monkeypatch.setattr(cdc.subprocess, "run", _git_ref(0))
    monkeypatch.setattr(cdc, "run_diff_cover", lambda xml, base: {"total_num_lines": 0})
    assert cdc.main(["coverage.xml"]) == 0
    assert "nothing to gate" in capsys.readouterr().out


def test_main_fails_when_changed_lines_are_under_covered(monkeypatch):
    monkeypatch.setattr(cdc.subprocess, "run", _git_ref(0))
    monkeypatch.setattr(cdc, "run_diff_cover",
                        lambda xml, base: _report(10.0, 50, {"src/kimcad/x.py": (10.0, 5, 45)}))
    assert cdc.main(["coverage.xml"]) == 1


def test_main_passes_when_changed_lines_are_well_covered(monkeypatch):
    monkeypatch.setattr(cdc.subprocess, "run", _git_ref(0))
    monkeypatch.setattr(cdc, "run_diff_cover",
                        lambda xml, base: _report(96.0, 50, {"src/kimcad/x.py": (96.0, 48, 2)}))
    assert cdc.main(["coverage.xml"]) == 0


def test_main_reports_a_diff_cover_failure_as_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(cdc.subprocess, "run", _git_ref(0))
    def boom(xml, base):
        raise RuntimeError("no report")
    monkeypatch.setattr(cdc, "run_diff_cover", boom)
    assert cdc.main(["coverage.xml"]) == 1
    assert "could not run diff-cover" in capsys.readouterr().err
