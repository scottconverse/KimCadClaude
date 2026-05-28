import subprocess
from pathlib import Path

import pytest

from kimcad import slicer as slicer_mod
from kimcad.slicer import SliceFailed, SliceSettings, SliceTimeout, slice_model

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
