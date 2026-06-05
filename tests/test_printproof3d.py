"""Stage 7 Slice 2 — the PrintProof3D arm's-length wrapper.

The subprocess runner is injected, so these exercise invoke -> parse and every graceful-degrade
path without the real engine binary. A canned report mirrors the real `validate-model` output.
"""

from __future__ import annotations

import json
from pathlib import Path

from kimcad.config import Config, Material, Printer
from kimcad.printproof3d import (
    _MAX_HL_TRIANGLES,
    _parse_report,
    _sanitize_geometry,
    material_profile,
    printer_profile,
    validate_model,
)
from kimcad.smart_mesh import PrintProofReport

BAMBU = Printer(key="bambu_p2s", name="Bambu Lab P2S", build_volume=(256.0, 256.0, 256.0),
                nozzle_diameter=0.4)
PLA = Material(key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0,
               shrinkage=0.002)

# A canned ValidationReport mirroring the real engine's shape (see schemas/validation_report).
_CANNED = {
    "status": "warning",
    "confidence_level": "high",
    "target_printer_profile": "Bambu Lab P2S",
    "target_material_profile": "PLA",
    "model": {"file_name": "part.stl", "units": "mm",
              "bounding_box": {"min_x": 0, "min_y": 0, "min_z": 0, "max_x": 20, "max_y": 20, "max_z": 20}},
    "issues": [
        {"id": "OVERHANG_UNSUPPORTED", "severity": "major",
         "message": "A 55 deg overhang on the arm has no support.",
         "suggested_fixes": ["Add supports under the arm."],
         "location": {"region": "overhang", "geometry": None}},
        {"id": "LOW_BED_CONTACT", "severity": "minor",
         "message": "Small first-layer footprint.", "suggested_fixes": [], "location": None},
    ],
    "sliced_settings_assumed": None,
}


def _runner_writing(report: dict):
    """A fake runner that writes `report` to the -o path in argv (what the real subprocess does)."""
    def run(argv, timeout):
        out = argv[argv.index("-o") + 1]
        Path(out).write_text(json.dumps(report), encoding="utf-8")
    return run


# --- validate_model: the happy path + every degrade path ------------------------------------

def test_validate_model_returns_none_without_a_binary():
    assert validate_model("part.stl", BAMBU, PLA, binary=None) is None


def test_validate_model_parses_a_canned_report():
    r = validate_model("part.stl", BAMBU, PLA, binary=Path("fake-binary"),
                       runner=_runner_writing(_CANNED))
    assert isinstance(r, PrintProofReport)
    assert r.status == "warning"
    assert r.confidence_level == "high"
    ids = [i.id for i in r.issues]
    assert ids == ["OVERHANG_UNSUPPORTED", "LOW_BED_CONTACT"]
    ov = r.issues[0]
    assert ov.severity == "major"
    assert ov.suggested_fixes == ("Add supports under the arm.",)
    assert ov.region == "overhang"
    assert r.issues[1].region is None  # location was null


def test_validate_model_degrades_to_none_when_no_report_is_written():
    assert validate_model("part.stl", BAMBU, PLA, binary=Path("x"),
                          runner=lambda argv, t: None) is None


def test_validate_model_degrades_to_none_when_the_runner_raises():
    def boom(argv, t):
        raise RuntimeError("engine crashed")
    assert validate_model("part.stl", BAMBU, PLA, binary=Path("x"), runner=boom) is None


def test_validate_model_degrades_to_none_on_unparseable_report():
    def write_garbage(argv, t):
        Path(argv[argv.index("-o") + 1]).write_text("<html>500</html>", encoding="utf-8")
    assert validate_model("part.stl", BAMBU, PLA, binary=Path("x"), runner=write_garbage) is None


# --- _parse_report: defensive mapping --------------------------------------------------------

def test_parse_report_rejects_non_dict_and_bad_status():
    assert _parse_report([1, 2, 3]) is None
    assert _parse_report("nope") is None
    assert _parse_report({"status": "weird", "issues": []}) is None


def test_parse_report_skips_an_issue_with_an_unknown_severity():
    r = _parse_report({"status": "warning", "confidence_level": "high", "issues": [
        {"id": "A", "message": "m", "severity": "bogus", "suggested_fixes": []},
        {"id": "B", "message": "m", "severity": "major", "suggested_fixes": []},
    ]})
    assert [i.id for i in r.issues] == ["B"]  # the unrecognized-severity issue is dropped, not guessed


def test_parse_report_tolerates_missing_optional_fields():
    r = _parse_report({"status": "pass", "issues": []})
    assert r.status == "pass"
    assert r.confidence_level == ""  # defaulted
    assert r.issues == ()


def test_parse_report_degrades_not_raises_on_a_non_list_issues_or_fixes():
    # PP-001: a valid-JSON dict report with a malformed (non-list) issues / suggested_fixes must
    # degrade (parse with empty issues/fixes), never raise -- the never-raises contract.
    r = _parse_report({"status": "pass", "issues": 5})  # issues is an int, not a list
    assert isinstance(r, PrintProofReport)
    assert r.issues == ()
    r2 = _parse_report({"status": "warning", "confidence_level": "high", "issues": [
        {"id": "A", "message": "m", "severity": "major", "suggested_fixes": 7},  # fixes not a list
    ]})
    assert r2.issues[0].suggested_fixes == ()


# --- profile generation matches the engine schema -------------------------------------------

_PRINTER_REQUIRED = {
    "bed_shape", "build_volume", "default_nozzle_diameter", "firmware_flavor", "has_enclosure",
    "known_quirks", "manufacturer", "max_bed_temp", "max_hotend_temp", "max_layer_height",
    "min_layer_height", "model", "nozzle_diameters", "protocol_family", "supported_file_types",
    "supports_cancel", "supports_chamber_temp", "supports_direct_upload", "supports_job_progress",
    "supports_mmu", "supports_pause_resume", "supports_webcam", "unsafe_commands",
}
_MATERIAL_REQUIRED = {
    "abbreviations", "bridge_difficulty", "cooling_fan_speed_pct", "dryness_sensitive",
    "enclosure_recommended", "max_bed_temp", "max_nozzle_temp", "min_bed_temp",
    "min_feature_size_mm", "min_nozzle_temp", "name", "overhang_difficulty", "warp_risk",
}


def test_printer_profile_has_all_required_fields_and_carries_kimcad_geometry():
    prof = printer_profile(BAMBU)
    assert _PRINTER_REQUIRED <= set(prof)
    assert prof["build_volume"] == {"type": "rectangular", "x": 256.0, "y": 256.0, "z": 256.0}
    assert prof["default_nozzle_diameter"] == 0.4
    assert prof["nozzle_diameters"] == [0.4]


def test_printer_profile_defaults_a_blank_build_volume():
    blank = Printer(key="x", name="X", build_volume=None, nozzle_diameter=None)
    prof = printer_profile(blank)
    assert prof["build_volume"]["x"] == 256.0  # sensible default, not a crash
    assert prof["default_nozzle_diameter"] == 0.4


def test_material_profile_has_all_required_fields_and_a_thermal_window():
    prof = material_profile(PLA)
    assert _MATERIAL_REQUIRED <= set(prof)
    assert prof["min_nozzle_temp"] < 210 < prof["max_nozzle_temp"]  # window brackets the temp
    assert prof["warp_risk"] in {"low", "medium", "high"}
    assert prof["name"] == "PLA"


def test_material_profile_risklevels_track_shrinkage():
    low = material_profile(PLA)  # shrinkage 0.002
    high = material_profile(Material("abs", "ABS", 250, 100, 2.5, shrinkage=0.006))
    assert low["warp_risk"] == "low"
    assert high["warp_risk"] == "high"
    assert high["enclosure_recommended"] is True  # bed 100 >= 90


# --- config seam -----------------------------------------------------------------------------

def test_config_printproof3d_binary_is_none_when_unset_or_missing():
    assert Config({"binaries": {}}).printproof3d_binary() is None
    assert Config({"binaries": {"printproof3d": "tools/nope/printproof3d.exe"}}).printproof3d_binary() is None


# --- Slice 8: capturing the issue location geometry (for viewport highlighting) -------------

def test_sanitize_geometry_accepts_the_three_engine_shapes():
    assert _sanitize_geometry({"type": "point", "x": 1, "y": 2, "z": 3}) == {
        "type": "point", "x": 1.0, "y": 2.0, "z": 3.0}
    bb = {"type": "bounding_box", "min_x": 0, "min_y": 0, "min_z": 0,
          "max_x": 1, "max_y": 2, "max_z": 3}
    assert _sanitize_geometry(bb) == {"type": "bounding_box", "min_x": 0.0, "min_y": 0.0,
                                      "min_z": 0.0, "max_x": 1.0, "max_y": 2.0, "max_z": 3.0}
    tri = {"type": "triangles", "triangles": [{"v0": [0, 0, 0], "v1": [1, 0, 0], "v2": [0, 1, 0]}]}
    out = _sanitize_geometry(tri)
    assert out["type"] == "triangles" and out["triangles"][0]["v1"] == [1.0, 0.0, 0.0]


def test_sanitize_geometry_rejects_malformed():
    assert _sanitize_geometry(None) is None
    assert _sanitize_geometry({"type": "bogus"}) is None
    assert _sanitize_geometry({"type": "point", "x": "nan", "y": 1, "z": 1}) is None
    assert _sanitize_geometry({"type": "point", "x": True, "y": 1, "z": 1}) is None  # bool != coord
    assert _sanitize_geometry({"type": "bounding_box", "min_x": 0}) is None  # missing fields
    # a triangle list with no VALID triangle degrades to None (not an empty highlight)
    assert _sanitize_geometry({"type": "triangles", "triangles": [{"v0": [0, 0]}]}) is None


def test_sanitize_geometry_caps_triangle_count():
    one = {"v0": [0, 0, 0], "v1": [1, 0, 0], "v2": [0, 1, 0]}
    out = _sanitize_geometry({"type": "triangles", "triangles": [one] * (_MAX_HL_TRIANGLES + 500)})
    assert len(out["triangles"]) == _MAX_HL_TRIANGLES


def test_parse_report_captures_issue_geometry():
    data = {
        "status": "warning", "confidence_level": "high",
        "issues": [{
            "id": "OVERHANG_UNSUPPORTED", "severity": "major", "message": "m",
            "suggested_fixes": [],
            "location": {"region": "overhangs", "geometry": {
                "type": "triangles", "triangles": [{"v0": [0, 0, 0], "v1": [1, 0, 0], "v2": [0, 1, 0]}]}},
        }],
    }
    rep = _parse_report(data)
    assert rep.issues[0].region == "overhangs"
    assert rep.issues[0].geometry["type"] == "triangles"


def test_parse_report_geometry_is_none_when_engine_gives_none():
    # The existing canned report has geometry: None / location: None — both must yield geometry None.
    rep = _parse_report(_CANNED)
    assert rep is not None
    assert all(i.geometry is None for i in rep.issues)
