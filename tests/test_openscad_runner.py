import subprocess
from pathlib import Path

import pytest

from kimcad import openscad_runner as osr
from kimcad.openscad_runner import (
    BlockedCodeError,
    OversizeOutput,
    RenderFailed,
    RenderTimeout,
    render_scad,
    sanitize_scad,
)


def test_sanitize_keeps_approved_library_use():
    code = "use <library/box.scad>;\nbox(10, 10, 10);"
    result = sanitize_scad(code)
    assert result.safe
    assert "use <library/box.scad>;" in result.code
    assert result.removed == []


def _live_lines(code: str) -> list[str]:
    """Source lines that OpenSCAD would actually execute (comments dropped)."""
    return [ln for ln in code.splitlines() if not ln.lstrip().startswith("//")]


def test_sanitize_strips_foreign_use_and_import():
    code = 'use <library/box.scad>;\nuse </etc/secrets.scad>;\nimport("/etc/passwd");\ncube(5);'
    result = sanitize_scad(code)
    assert result.safe  # stripping is not fatal
    assert "use <library/box.scad>;" in result.code
    live = "\n".join(_live_lines(result.code))
    assert "/etc/secrets.scad" not in live
    assert "/etc/passwd" not in live
    assert len(result.removed) == 2


def test_sanitize_blocks_path_traversal_use():
    result = sanitize_scad("use <library/../../../etc/passwd.scad>;")
    assert "etc/passwd" not in "\n".join(_live_lines(result.code))
    assert len(result.removed) == 1


def test_sanitize_blocks_minkowski():
    result = sanitize_scad("minkowski() { cube(10); sphere(2); }")
    assert not result.safe
    assert any("minkowski" in b for b in result.blocked)


def test_render_refuses_blocked_code(tmp_path):
    with pytest.raises(BlockedCodeError):
        render_scad(
            "minkowski(){cube(1);sphere(1);}",
            binary=Path("openscad"),
            out_dir=tmp_path,
        )


def _fake_run_writing(content: bytes = b"mesh", returncode: int = 0, stderr: str = ""):
    def _run(cmd, **kwargs):
        out_path = Path(cmd[2])  # cmd = [binary, "-o", out, scad]
        if returncode == 0:
            out_path.write_bytes(content)
        return subprocess.CompletedProcess(cmd, returncode, stdout="", stderr=stderr)

    return _run


def test_render_happy_path(tmp_path, monkeypatch):
    monkeypatch.setattr(osr.subprocess, "run", _fake_run_writing())
    result = render_scad(
        "use <library/box.scad>;\nbox(10,10,10);",
        binary=Path("openscad"),
        out_dir=tmp_path,
        output_format="3mf",
    )
    assert result.output_format == "3mf"
    assert result.output_path.exists()
    assert result.output_path.suffix == ".3mf"
    assert not result.fell_back_to_stl


def test_render_falls_back_to_stl_when_no_lib3mf(tmp_path, monkeypatch):
    calls = {"n": 0}

    def _run(cmd, **kwargs):
        calls["n"] += 1
        out_path = Path(cmd[2])
        if out_path.suffix == ".3mf":
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr="ERROR: lib3mf not available"
            )
        out_path.write_bytes(b"mesh")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(osr.subprocess, "run", _run)
    result = render_scad(
        "cube(5);",
        binary=Path("openscad"),
        out_dir=tmp_path,
        output_format="3mf",
    )
    assert result.fell_back_to_stl
    assert result.output_format == "stl"
    assert result.output_path.suffix == ".stl"
    assert calls["n"] == 2


def test_render_failed_on_real_error(tmp_path, monkeypatch):
    monkeypatch.setattr(
        osr.subprocess,
        "run",
        _fake_run_writing(returncode=1, stderr="ERROR: Parser error in line 3"),
    )
    with pytest.raises(RenderFailed) as exc:
        render_scad("cube(;", binary=Path("openscad"), out_dir=tmp_path)
    assert "Parser error" in str(exc.value)


def test_render_oversize_guard(tmp_path, monkeypatch):
    monkeypatch.setattr(osr.subprocess, "run", _fake_run_writing(content=b"x" * 1024))
    with pytest.raises(OversizeOutput):
        render_scad(
            "cube(5);",
            binary=Path("openscad"),
            out_dir=tmp_path,
            max_output_bytes=100,
        )


def test_render_timeout(tmp_path, monkeypatch):
    def _run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

    monkeypatch.setattr(osr.subprocess, "run", _run)
    with pytest.raises(RenderTimeout):
        render_scad("cube(5);", binary=Path("openscad"), out_dir=tmp_path, timeout_s=1)
