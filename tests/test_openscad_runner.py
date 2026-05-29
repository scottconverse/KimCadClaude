import subprocess
from pathlib import Path

import pytest

from kimcad import openscad_runner as osr
from kimcad.openscad_runner import (
    BlockedCodeError,
    OversizeOutput,
    RenderFailed,
    RenderTimeout,
    ensure_terminated,
    inject_library_uses,
    render_scad,
    sanitize_scad,
)


def test_ensure_terminated_appends_missing_semicolon():
    code = "use <library/hooks.scad>;\nwall_hook(plate_w = 25, plate_h = 60)"
    out, did = ensure_terminated(code)
    assert did
    assert out.rstrip().endswith(");")


def test_ensure_terminated_preserves_trailing_comment():
    code = "wall_hook(plate_w = 25)  // the hook"
    out, did = ensure_terminated(code)
    assert did
    assert ");" in out and out.rstrip().endswith("// the hook")


def test_ensure_terminated_noop_when_already_terminated():
    code = "wall_hook(plate_w = 25);\n"
    out, did = ensure_terminated(code)
    assert not did and out == code


def test_ensure_terminated_noop_on_block_close():
    code = "difference() {\n  cube(10);\n}\n"
    out, did = ensure_terminated(code)
    assert not did and out == code

_MAP = {"rounded_box": "fillets.scad", "rounded_rect": "fillets.scad", "box": "box.scad"}


def test_inject_adds_missing_library_use():
    # The model called a real helper but forgot its `use` line.
    code = "rounded_box(80, 60, 40, r = 3);"
    out, added = inject_library_uses(code, _MAP)
    assert "use <library/fillets.scad>;" in out
    assert added == ["use <library/fillets.scad>;"]


def test_inject_is_noop_when_use_present():
    code = "use <library/fillets.scad>;\nrounded_box(80, 60, 40);"
    out, added = inject_library_uses(code, _MAP)
    assert added == []
    assert out == code


def test_inject_dedupes_one_use_per_file():
    # Two helpers from the same file -> a single `use` line.
    code = "rounded_box(10, 10, 10);\nrounded_rect(10, 10);"
    out, added = inject_library_uses(code, _MAP)
    assert added == ["use <library/fillets.scad>;"]
    assert out.count("use <library/fillets.scad>;") == 1


def test_inject_skips_locally_defined_module():
    # A user-supplied definition must not be shadowed by a library import.
    code = "module rounded_box(w, d, h) { cube([w, d, h]); }\nrounded_box(10, 10, 10);"
    _out, added = inject_library_uses(code, _MAP)
    assert added == []


def test_inject_ignores_substring_false_positive():
    # `box(` must not trigger on `rounded_box(`.
    code = "rounded_box(10, 10, 10);"
    _out, added = inject_library_uses(code, _MAP)
    assert added == ["use <library/fillets.scad>;"]  # fillets, not box.scad


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


def test_render_resolves_relative_out_dir(tmp_path, monkeypatch):
    # Regression: the binary runs with cwd=out_dir, so a relative out_dir would make
    # the -o/scad paths resolve under themselves (out_dir/out_dir/part.3mf) and the
    # real renderer fails with "not a directory". render_scad must resolve to absolute.
    monkeypatch.chdir(tmp_path)
    captured: dict = {}

    def _run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["cwd"] = kwargs.get("cwd")
        Path(cmd[2]).write_bytes(b"mesh")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(osr.subprocess, "run", _run)
    result = render_scad(
        "cube(5);",
        binary=Path("openscad"),
        out_dir=Path("rel/out"),
        output_format="3mf",
    )

    out_arg = Path(captured["cmd"][2])
    scad_arg = Path(captured["cmd"][3])
    assert out_arg.is_absolute()
    assert scad_arg.is_absolute()
    assert Path(captured["cwd"]).is_absolute()
    assert out_arg == (tmp_path / "rel" / "out" / "part.3mf").resolve()
    assert result.output_path.is_absolute()


def test_render_timeout(tmp_path, monkeypatch):
    def _run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 1))

    monkeypatch.setattr(osr.subprocess, "run", _run)
    with pytest.raises(RenderTimeout):
        render_scad("cube(5);", binary=Path("openscad"), out_dir=tmp_path, timeout_s=1)
