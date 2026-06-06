"""Stage 8 — the deterministic CadQuery backend bench (live; skipped without an interpreter)."""

from __future__ import annotations

import pytest

from kimcad.cadquery_bench import CASES, format_report, run_cadquery_bench
from kimcad.cadquery_runner import find_cadquery_interpreter

_CQ = find_cadquery_interpreter()


def test_bench_cases_are_defined():
    # A pure check that runs without an interpreter: the bench has cases and each declares a 3-axis
    # envelope, so the suite notices if the bench is accidentally emptied.
    assert len(CASES) >= 5
    for c in CASES:
        assert len(c.expected_bbox_mm) == 3
        assert "result" in c.code  # every case must assign the exported `result`


@pytest.mark.live
@pytest.mark.skipif(_CQ is None, reason="no cadquery interpreter")
def test_every_cadquery_bench_case_renders_watertight_at_its_envelope():
    results = run_cadquery_bench(_CQ)
    failed = [r for r in results if not r.passed]
    assert not failed, "CadQuery bench had failures:\n" + format_report(results)
