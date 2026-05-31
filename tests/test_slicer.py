import subprocess
from pathlib import Path

import pytest

from kimcad import slicer as slicer_mod
from kimcad.config import Config, Material, Printer
from kimcad.slicer import (
    OrcaProfileError,
    SliceFailed,
    SliceSettings,
    SliceTimeout,
    _find_profile_json,
    resolve_slice_settings,
    slice_model,
)

SETTINGS = SliceSettings(
    machine=Path("machine.json"),
    process=Path("process.json"),
    filament=Path("filament.json"),
)


def test_slice_builds_expected_command(tmp_path, monkeypatch):
    seen = {}

    def _run(cmd, **kwargs):
        seen["cmd"] = cmd
        Path(cmd[cmd.index("--export-3mf") + 1]).write_bytes(b"gcode3mf")
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(slicer_mod.subprocess, "run", _run)
    result = slice_model(
        tmp_path / "part.oriented.stl",
        binary=Path("orca-slicer"),
        out_dir=tmp_path,
        settings=SETTINGS,
        basename="part",
    )
    cmd = seen["cmd"]
    assert "--slice" in cmd and "1" in cmd
    assert "machine.json;process.json" in cmd
    assert "--allow-newer-file" in cmd
    assert result.gcode_path.name == "part.gcode.3mf"
    assert result.gcode_path.exists()


def test_slice_failed_on_nonzero(tmp_path, monkeypatch):
    def _run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 2, stdout="", stderr="bad profile")

    monkeypatch.setattr(slicer_mod.subprocess, "run", _run)
    with pytest.raises(SliceFailed):
        slice_model(
            tmp_path / "x.stl",
            binary=Path("orca-slicer"),
            out_dir=tmp_path,
            settings=SETTINGS,
        )


def test_slice_timeout(tmp_path, monkeypatch):
    def _run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

    monkeypatch.setattr(slicer_mod.subprocess, "run", _run)
    with pytest.raises(SliceTimeout):
        slice_model(
            tmp_path / "x.stl",
            binary=Path("orca-slicer"),
            out_dir=tmp_path,
            settings=SETTINGS,
            timeout_s=1,
        )


# --- profile name -> on-disk JSON resolution (Stage 1, Slice 1) ---------------

_PLA = Material(
    key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002
)
_PETG = Material(
    key="petg", name="PETG", nozzle_temp=240, bed_temp=75, wall_multiplier=2.5, shrinkage=0.004
)


def _profile_tree(root):
    """Build a minimal shipped-style profile tree and return ``root``."""
    layout = {
        "machine": ["Bambu Lab P2S 0.4 nozzle", "Elegoo Neptune 4 Max (0.4 nozzle)"],
        "process": ["0.20mm Standard @BBL P2S"],
        "filament": ["Bambu PLA Basic @BBL P2S", "Generic PETG", "Generic PLA @Elegoo"],
    }
    for kind, names in layout.items():
        d = root / "BBL" / kind
        d.mkdir(parents=True, exist_ok=True)
        for name in names:
            (d / f"{name}.json").write_text("{}", encoding="utf-8")
    return root


def _p2s(**over):
    base = dict(
        key="bambu_p2s",
        name="Bambu Lab P2S",
        build_volume=(256, 256, 256),
        nozzle_diameter=0.4,
        orca_machine_profile="Bambu Lab P2S 0.4 nozzle",
        orca_process_profile="0.20mm Standard @BBL P2S",
        orca_filament_profiles={"pla": "Bambu PLA Basic @BBL P2S"},
    )
    base.update(over)
    return Printer(**base)


def test_find_profile_json_resolves_by_kind_and_name(tmp_path):
    root = _profile_tree(tmp_path)
    p = _find_profile_json(root, "machine", "Bambu Lab P2S 0.4 nozzle")
    assert p.exists()
    assert "machine" in p.parts and p.stem == "Bambu Lab P2S 0.4 nozzle"


def test_find_profile_json_disambiguates_same_name_across_kinds(tmp_path):
    # The same stem under two kinds must resolve to the requested kind.
    for kind in ("machine", "filament"):
        d = tmp_path / "BBL" / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / "Shared Name.json").write_text("{}", encoding="utf-8")
    m = _find_profile_json(tmp_path, "machine", "Shared Name")
    f = _find_profile_json(tmp_path, "filament", "Shared Name")
    assert "machine" in m.parts and "filament" not in m.parts
    assert "filament" in f.parts and "machine" not in f.parts


def test_find_profile_json_missing_raises(tmp_path):
    _profile_tree(tmp_path)
    with pytest.raises(OrcaProfileError, match="no process profile named"):
        _find_profile_json(tmp_path, "process", "Does Not Exist")


def test_resolve_maps_printer_material_to_three_jsons(tmp_path):
    root = _profile_tree(tmp_path)
    settings = resolve_slice_settings(root, _p2s(), _PLA)
    assert settings.machine.stem == "Bambu Lab P2S 0.4 nozzle"
    assert settings.process.stem == "0.20mm Standard @BBL P2S"
    assert settings.filament.stem == "Bambu PLA Basic @BBL P2S"
    for path, kind in (
        (settings.machine, "machine"),
        (settings.process, "process"),
        (settings.filament, "filament"),
    ):
        assert path.exists() and kind in path.parts


def test_resolve_falls_back_to_generic_filament(tmp_path):
    # PETG has no printer-specific entry -> the shipped "Generic PETG" is used.
    root = _profile_tree(tmp_path)
    settings = resolve_slice_settings(root, _p2s(), _PETG)
    assert settings.filament.stem == "Generic PETG"


def test_resolve_raises_when_no_process_profile(tmp_path):
    # The Elegoo case: machine + filament exist but the shipped build has no process
    # profile, so slicing must refuse with a clear error rather than mis-slice.
    root = _profile_tree(tmp_path)
    elegoo = Printer(
        key="elegoo_neptune_4_max",
        name="Elegoo Neptune 4 Max",
        build_volume=(420, 420, 480),
        nozzle_diameter=0.4,
        orca_machine_profile="Elegoo Neptune 4 Max (0.4 nozzle)",
        orca_process_profile=None,
        orca_filament_profiles={"pla": "Generic PLA @Elegoo"},
    )
    with pytest.raises(OrcaProfileError, match="no OrcaSlicer process profile"):
        resolve_slice_settings(root, elegoo, _PLA)


def test_resolve_raises_when_no_machine_profile(tmp_path):
    root = _profile_tree(tmp_path)
    with pytest.raises(OrcaProfileError, match="no OrcaSlicer machine profile"):
        resolve_slice_settings(root, _p2s(orca_machine_profile=None), _PLA)


def test_resolve_raises_when_configured_name_missing(tmp_path):
    root = _profile_tree(tmp_path)
    bad = _p2s(orca_machine_profile="Nonexistent Machine 9.9 nozzle")
    with pytest.raises(OrcaProfileError, match="no machine profile named"):
        resolve_slice_settings(root, bad, _PLA)


def _profiles_present() -> bool:
    try:
        return Config.load().orca_profiles_root().exists()
    except Exception:  # pragma: no cover - config absent
        return False


@pytest.mark.skipif(not _profiles_present(), reason="OrcaSlicer profiles not fetched")
def test_resolve_real_p2s_pla_profiles():
    """The configured Bambu P2S + PLA resolves to three real shipped JSON files."""
    cfg = Config.load()
    settings = resolve_slice_settings(
        cfg.orca_profiles_root(), cfg.printer("bambu_p2s"), cfg.material("pla")
    )
    assert settings.machine.exists()
    assert settings.process.exists()
    assert settings.filament.exists()


@pytest.mark.skipif(not _profiles_present(), reason="OrcaSlicer profiles not fetched")
def test_resolve_real_elegoo_refuses_without_process():
    """The configured Elegoo has no shipped process profile -> resolution refuses."""
    cfg = Config.load()
    with pytest.raises(OrcaProfileError):
        resolve_slice_settings(
            cfg.orca_profiles_root(),
            cfg.printer("elegoo_neptune_4_max"),
            cfg.material("pla"),
        )
