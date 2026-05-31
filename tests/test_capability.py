"""Tests for capability reconciliation + the gate's blank-field guards (Stage 2, Slice 3)."""

from kimcad.capability import NoteKind, reconcile
from kimcad.config import Config, Material, Printer
from kimcad.ir import DesignPlan
from kimcad.printability import Level, run_gate
from kimcad.printer_connector import PrinterCapabilities
from kimcad.validation import MeshReport

_PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)


def _printer(build_volume=None, nozzle=None, name="P") -> Printer:
    return Printer(key="p", name=name, build_volume=build_volume, nozzle_diameter=nozzle)


def _caps(build_volume=None, nozzle=None, name="MockPrinter") -> PrinterCapabilities:
    return PrinterCapabilities(name=name, build_volume_mm=build_volume, nozzle_diameter_mm=nozzle)


def _report(bbox) -> MeshReport:
    return MeshReport(
        watertight=True, repaired=False, repairs=[], vertices=8, faces=12,
        volume_mm3=float(bbox[0] * bbox[1] * bbox[2]),
        bounding_box_mm=(float(bbox[0]), float(bbox[1]), float(bbox[2])), n_bodies=1,
    )


# --- reconcile ----------------------------------------------------------------


def test_blank_fields_are_filled_from_capabilities():
    r = reconcile(_printer(), _caps(build_volume=(250.0, 210.0, 210.0), nozzle=0.4))
    assert r.printer.build_volume == (250.0, 210.0, 210.0)
    assert r.printer.nozzle_diameter == 0.4
    assert r.note_for("build_volume").kind is NoteKind.filled
    assert r.note_for("nozzle_diameter").kind is NoteKind.filled
    assert not r.has_mismatch


def test_matching_config_is_confirmed_not_changed():
    r = reconcile(
        _printer(build_volume=(250.0, 210.0, 210.0), nozzle=0.4),
        _caps(build_volume=(250.5, 210.0, 209.6), nozzle=0.4),  # within 1mm tolerance
    )
    assert r.note_for("build_volume").kind is NoteKind.matches
    assert r.note_for("nozzle_diameter").kind is NoteKind.matches
    assert r.printer.build_volume == (250.0, 210.0, 210.0)  # config value kept
    assert not r.has_mismatch


def test_mismatch_keeps_config_but_flags():
    r = reconcile(
        _printer(build_volume=(256.0, 256.0, 256.0), nozzle=0.4),
        _caps(build_volume=(250.0, 210.0, 210.0), nozzle=0.6),
    )
    assert r.has_mismatch
    assert r.note_for("build_volume").kind is NoteKind.mismatch
    assert r.note_for("nozzle_diameter").kind is NoteKind.mismatch
    # config remains authoritative on a mismatch (the human verifies)
    assert r.printer.build_volume == (256.0, 256.0, 256.0)
    assert r.printer.nozzle_diameter == 0.4


def test_unknown_when_neither_side_has_a_value():
    r = reconcile(_printer(), _caps())
    assert r.printer.build_volume is None and r.printer.nozzle_diameter is None
    assert r.note_for("build_volume").kind is NoteKind.unknown
    assert r.note_for("nozzle_diameter").kind is NoteKind.unknown


def test_printer_value_kept_when_capabilities_silent():
    # config has values, the printer reports nothing -> keep config, no notes for them
    r = reconcile(_printer(build_volume=(256.0, 256.0, 256.0), nozzle=0.4), _caps())
    assert r.printer.build_volume == (256.0, 256.0, 256.0)
    assert r.notes == ()


def test_build_volume_tolerance_boundary():
    cfg = _printer(build_volume=(250.0, 210.0, 210.0), nozzle=0.4)
    at = reconcile(cfg, _caps(build_volume=(251.0, 210.0, 210.0), nozzle=0.4))  # exactly 1.0mm
    assert at.note_for("build_volume").kind is NoteKind.matches
    over = reconcile(cfg, _caps(build_volume=(251.01, 210.0, 210.0), nozzle=0.4))  # just over
    assert over.note_for("build_volume").kind is NoteKind.mismatch


# --- gate guards for blank fields ---------------------------------------------


def test_gate_warns_when_build_volume_unknown():
    plan = DesignPlan(object_type="x", summary="s", bounding_box_mm=[20, 20, 20])
    res = run_gate(_report((20, 20, 20)), plan, _printer(build_volume=None, nozzle=0.4), _PLA)
    assert any(f.code == "volume.unchecked" and f.level is Level.WARN for f in res.findings)
    assert not any(f.code == "volume.exceeds" for f in res.findings)
    # a missing build volume must not crash the gate or hard-fail it on volume
    assert res.status is not Level.FAIL


def test_filling_re_enables_the_gate_fit_check():
    # Before filling, a too-big part on a blank-volume printer is only WARNed as unchecked;
    # after reconcile fills the volume from the printer, the same part FAILS the fit check.
    blank = _printer(build_volume=None, nozzle=0.4, name="blank")
    plan = DesignPlan(object_type="x", summary="s", bounding_box_mm=[150, 150, 150])
    rep = _report((150, 150, 150))
    before = run_gate(rep, plan, blank, _PLA)
    assert any(f.code == "volume.unchecked" for f in before.findings)

    filled = reconcile(blank, _caps(build_volume=(100.0, 100.0, 100.0), nozzle=0.4)).printer
    after = run_gate(rep, plan, filled, _PLA)
    assert after.failed
    assert any(f.code == "volume.exceeds" for f in after.findings)


def test_gate_skips_wall_check_when_nozzle_unknown():
    plan = DesignPlan(
        object_type="box", summary="s", bounding_box_mm=[20, 20, 20], dimensions={"wall": 0.1}
    )
    res = run_gate(
        _report((20, 20, 20)), plan, _printer(build_volume=(256, 256, 256), nozzle=None), _PLA
    )
    # the thin wall would normally WARN; with no nozzle the check is skipped, no crash
    assert not any(f.code.startswith("wall.") for f in res.findings)


# --- blank fields load from config --------------------------------------------


def test_config_loads_blank_physical_fields_as_none():
    data = {
        "binaries": {"openscad": "x", "orcaslicer": "y"},
        "defaults": {"printer": "blank", "material": "pla"},
        "printers": {"blank": {"name": "Blank Printer"}},  # no build_volume / nozzle_diameter
        "materials": {"pla": {"name": "PLA", "nozzle_temp": 210, "bed_temp": 55,
                              "wall_multiplier": 2.0, "shrinkage": 0.002}},
        "limits": {},
    }
    p = Config(data).printer("blank")
    assert p.build_volume is None and p.nozzle_diameter is None
