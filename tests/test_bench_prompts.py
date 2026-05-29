"""Integrity guard for the §4 done-gate prompt set.

`bench/prompts.yaml` *is* the Phase-1 done-gate (`kimcad bench
--min-success-rate 0.8`). A malformed edit — a dropped case, a duplicate id,
or a bounding box that exceeds the build volume — would silently mis-score the
gate instead of failing loudly. These tests fail loudly instead.
"""

from pathlib import Path

from kimcad.benchmark import load_cases

PROMPTS = Path(__file__).resolve().parents[1] / "bench" / "prompts.yaml"

# Smallest reference build volume (Bambu P2S, 256 mm cube); every case must fit
# so the unattended batch never trips the build-volume check on the default
# printer. See config/default.yaml.
MIN_BUILD_VOLUME_MM = 256


def test_prompts_file_exists():
    assert PROMPTS.is_file(), f"done-gate prompt set missing at {PROMPTS}"


def test_has_exactly_ten_cases():
    # Appendix B is a fixed set of 10; the §4.2 threshold (0.8) is "8 / 10".
    assert len(load_cases(PROMPTS)) == 10


def test_case_ids_are_unique():
    ids = [c.id for c in load_cases(PROMPTS)]
    assert len(set(ids)) == len(ids), f"duplicate case ids: {ids}"


def test_prompts_are_non_empty():
    empty = [c.id for c in load_cases(PROMPTS) if not c.prompt.strip()]
    assert not empty, f"empty prompt(s): {empty}"


def test_bboxes_fit_smallest_build_volume():
    too_big = [
        (c.id, c.max_bbox_mm)
        for c in load_cases(PROMPTS)
        if c.max_bbox_mm
        and any(d > MIN_BUILD_VOLUME_MM for d in c.max_bbox_mm)
    ]
    assert not too_big, f"bbox exceeds {MIN_BUILD_VOLUME_MM} mm build volume: {too_big}"
