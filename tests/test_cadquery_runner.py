"""Stage 8 Slice 1 — the CadQuery backend's in-process runner + out-of-process worker.

Two layers are exercised:
- :func:`sanitize_cadquery` is a pure token-based function, tested WITHOUT any interpreter.
- :func:`render_cadquery` and the worker need a real <=3.13 + cadquery interpreter, so those
  tests are marked ``live`` and skipped when no such interpreter is discovered (mirroring the
  live OrcaSlicer tests). They also independently prove the worker's restricted-builtins
  sandbox stops an escape even if the static sanitizer were bypassed.
"""

from __future__ import annotations

import json
import subprocess

import pytest
import trimesh

import kimcad.cadquery_runner as cqr
from kimcad.cadquery_runner import (
    WORKER_PATH,
    _read_worker_result,
    _worker_env,
    find_cadquery_interpreter,
    render_cadquery,
    sanitize_cadquery,
)
from kimcad.openscad_runner import BlockedCodeError, RenderFailed, RenderTimeout

_CQ = find_cadquery_interpreter()
_needs_cq = pytest.mark.skipif(_CQ is None, reason="no Python with cadquery discovered")

_BOX = 'result = cq.Workplane("XY").box(40, 30, 20)'


# --- pure sanitizer (no interpreter) --------------------------------------------------------

def test_clean_geometry_is_safe():
    s = sanitize_cadquery(
        'result = cq.Workplane("XY").box(40, 30, 20).faces(">Z").workplane().hole(8)'
    )
    assert s.safe
    assert s.blocked == []


def test_allowed_imports_pass():
    s = sanitize_cadquery("import cadquery as cq\nfrom math import pi\nresult = cq.Workplane().sphere(pi)")
    assert s.safe


def test_disallowed_import_is_blocked():
    s = sanitize_cadquery("import os\nresult = cq.Workplane().box(1, 1, 1)")
    assert not s.safe
    assert any("os" in b for b in s.blocked)


def test_disallowed_from_import_is_blocked():
    s = sanitize_cadquery("from subprocess import run\nresult = None")
    assert not s.safe
    assert any("subprocess" in b for b in s.blocked)


def test_banned_name_is_blocked():
    s = sanitize_cadquery('data = open("/etc/passwd").read()\nresult = None')
    assert not s.safe
    assert any("open" in b for b in s.blocked)


def test_dunder_escape_is_blocked():
    # The classic restricted-exec escape — block any dunder token outright.
    s = sanitize_cadquery("result = ().__class__.__bases__[0].__subclasses__()")
    assert not s.safe
    assert any("dunder" in b.lower() for b in s.blocked)


def test_attribute_pivot_to_os_is_blocked():
    # The Stage-8 Slice-1 audit Blocker: reach os via the injected cadquery module's
    # attribute graph. Blocked statically (attr 'os' and '.system' are banned) — and the
    # worker's geometry-only facade removes the capability entirely (live test below).
    s = sanitize_cadquery("cq.exporters.os.system('echo hi')\nresult = cq.Workplane().box(1,1,1)")
    assert not s.safe
    assert any(".os" in b or "'os'" in b for b in s.blocked)


def test_banned_method_attr_is_blocked():
    s = sanitize_cadquery("x.system('echo hi')\nresult = None")
    assert not s.safe
    assert any("system" in b for b in s.blocked)


def test_global_statement_names_are_scanned():
    s = sanitize_cadquery("def f():\n    global os\n    os = 1\nresult = None")
    assert not s.safe
    assert any("os" in b for b in s.blocked)


# NEW-007 (re-audit): the introspection / __globals__ escape class is closed by the sanitizer.

def test_dunder_string_subscript_is_blocked():
    # obj["__globals__"]["__import__"] hides the dunder inside a string literal — invisible to
    # the Name/Attribute checks, so the Subscript-key check must catch it.
    s = sanitize_cadquery('x = cq.version\nm = x["__globals__"]["__import__"]\nresult = None')
    assert not s.safe
    assert any("__globals__" in b for b in s.blocked)


def test_frame_introspection_attrs_are_blocked():
    s = sanitize_cadquery("b = some_gen.gi_frame.f_builtins\nresult = None")
    assert not s.safe
    assert any("gi_frame" in b or "f_builtins" in b for b in s.blocked)


def test_str_format_field_pivot_is_blocked():
    # "{0.gi_frame}".format(x) hides an attribute access inside the format string; blocking the
    # .format attribute closes it (an f-string instead exposes real AST nodes, caught elsewhere).
    s = sanitize_cadquery('s = "{0.gi_frame}".format(obj)\nresult = None')
    assert not s.safe
    assert any("format" in b for b in s.blocked)


def test_banned_word_inside_a_string_is_not_a_false_positive():
    # "import os" appears only inside a string literal passed to .text(); not executable.
    s = sanitize_cadquery('result = cq.Workplane().text("import os subprocess eval", 5, 1)')
    assert s.safe, s.blocked


def test_syntax_error_is_blocked_not_crashed():
    s = sanitize_cadquery("result = cq.Workplane(.box(")
    assert not s.safe
    assert any("parse" in b.lower() for b in s.blocked)


def test_blocked_messages_are_deduped():
    s = sanitize_cadquery("a = open\nb = open\nc = open\nresult = None")
    open_msgs = [b for b in s.blocked if "open" in b]
    assert len(open_msgs) == 1


def test_render_cadquery_rejects_blocked_code_without_an_interpreter(tmp_path):
    # Sanitization happens before any subprocess, so a blocked script never reaches the worker —
    # provable with no interpreter at all (a bogus path is never invoked).
    with pytest.raises(BlockedCodeError):
        render_cadquery(
            "import os\nresult = None",
            interpreter=tmp_path / "nonexistent-python",
            out_dir=tmp_path,
        )


def test_bytes_dunder_subscript_is_blocked():
    # ENG-003: a dunder hidden in a BYTES constant subscript key, not just a str one.
    s = sanitize_cadquery('m = x[b"__globals__"]\nresult = None')
    assert not s.safe
    assert any("__globals__" in b for b in s.blocked)


# ENG-001: a through-render_cadquery escape-class canary. The sanitizer runs BEFORE any subprocess,
# so each known escape raises BlockedCodeError at the real entry point with NO interpreter — a
# single-branch sanitizer regression would fail these loudly (not only the unit-branch tests).
@pytest.mark.parametrize("payload", [
    "import os\nresult = None",
    "cq.exporters.os.system('x')\nresult = None",
    'm = cq.version.__globals__["__builtins__"]["__import__"]("os")\nresult = None',
    "r = ().__class__.__bases__[0].__subclasses__()\nresult = None",
    'm = x["__globals__"]\nresult = None',
    "b = g.gi_frame.f_builtins\nresult = None",
    's = "{0.gi_frame}".format(x)\nresult = None',
])
def test_render_cadquery_blocks_escape_class_end_to_end(tmp_path, payload):
    with pytest.raises(BlockedCodeError):
        render_cadquery(payload, interpreter=tmp_path / "no-python", out_dir=tmp_path)


def test_worker_env_scrubs_secrets(monkeypatch):
    # ENG-002: the worker subprocess env must NOT carry API keys / tokens / secrets.
    monkeypatch.setenv("OPENROUTER_API_KEY", "sekret")
    monkeypatch.setenv("SOME_TOKEN", "t")
    monkeypatch.setenv("DB_PASSWORD", "p")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("KIMCAD_HARMLESS", "ok")
    # REAUDIT-N1: segment-precise — look-alikes that merely CONTAIN a secret word survive.
    monkeypatch.setenv("TOKENIZER_PATH", "x")
    monkeypatch.setenv("PASSWORDLESS_MODE", "y")
    env = _worker_env()
    assert "OPENROUTER_API_KEY" not in env
    assert "SOME_TOKEN" not in env
    assert "DB_PASSWORD" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env.get("KIMCAD_HARMLESS") == "ok"  # non-secret vars survive
    assert env.get("TOKENIZER_PATH") == "x"  # not stripped — 'TOKENIZER' != 'TOKEN'
    assert env.get("PASSWORDLESS_MODE") == "y"  # not stripped — 'PASSWORDLESS' != 'PASSWORD'


def test_render_cadquery_timeout_is_raised(monkeypatch, tmp_path):
    # TEST-002: a worker that exceeds the wall-clock limit surfaces as RenderTimeout (no interpreter
    # needed — subprocess.run is stubbed to raise TimeoutExpired).
    def _boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="cq", timeout=1)

    monkeypatch.setattr(cqr.subprocess, "run", _boom)
    with pytest.raises(RenderTimeout):
        render_cadquery(_BOX, interpreter=tmp_path / "py", out_dir=tmp_path, timeout_s=1)


def test_read_worker_result_synthesizes_failure_on_a_missing_result_file(tmp_path):
    # TEST-002: a crashed/killed worker leaves no result file -> a clean RenderFailed dict synthesized
    # from captured stderr, not an unparseable-JSON crash.
    proc = subprocess.CompletedProcess(args=["cq"], returncode=139, stdout="", stderr="segfault!")
    result = _read_worker_result(tmp_path / "missing.json", proc)
    assert result["ok"] is False
    assert result["kind"] == "exec"
    assert "segfault!" in result["error"]


def _fake_completed(stdout="", returncode=0):
    return subprocess.CompletedProcess(args=["py"], returncode=returncode, stdout=stdout, stderr="")


def test_find_interpreter_swallows_oserror(monkeypatch):
    # TEST-006: a probe that errors (e.g. a bad `py` launcher) is skipped, never propagated.
    def _boom(*a, **k):
        raise OSError("no such launcher")

    monkeypatch.setattr(cqr.subprocess, "run", _boom)
    assert find_cadquery_interpreter([["py", "-9.9"]], include_defaults=False) is None


def test_find_interpreter_skips_a_candidate_that_prints_a_bogus_path(monkeypatch):
    # TEST-006/ENG-005: rc=0 but the sentinel-wrapped path doesn't exist -> skip (don't accept).
    bogus = cqr._PROBE_SENTINEL + r"C:\definitely\not\here\python.exe" + cqr._PROBE_SENTINEL
    monkeypatch.setattr(cqr.subprocess, "run", lambda *a, **k: _fake_completed(stdout=bogus))
    assert find_cadquery_interpreter([["py"]], include_defaults=False) is None


def test_find_interpreter_parses_the_sentinel_path_even_with_banner_noise(monkeypatch):
    # TEST-006/ENG-005: a startup banner before/after the sentinel-wrapped path doesn't corrupt
    # parsing; an existing path is returned.
    import sys as _sys

    noisy = "DeprecationWarning: blah\n" + cqr._PROBE_SENTINEL + _sys.executable + cqr._PROBE_SENTINEL
    monkeypatch.setattr(cqr.subprocess, "run", lambda *a, **k: _fake_completed(stdout=noisy))
    got = find_cadquery_interpreter([["py"]], include_defaults=False)
    assert got is not None and str(got) == _sys.executable


# --- live: the real worker on a real interpreter --------------------------------------------

@pytest.mark.live
@_needs_cq
def test_render_cadquery_builds_a_box(tmp_path):
    r = render_cadquery(_BOX, interpreter=_CQ, out_dir=tmp_path, basename="b")
    assert r.backend == "cadquery"
    assert r.output_format == "stl"
    assert r.output_path.exists()
    assert r.step_path is None  # not requested
    mesh = trimesh.load(str(r.output_path))
    ext = sorted(round(float(e)) for e in mesh.extents)
    assert ext == [20, 30, 40]


@pytest.mark.live
@_needs_cq
def test_render_cadquery_emits_step_when_requested(tmp_path):
    r = render_cadquery(_BOX, interpreter=_CQ, out_dir=tmp_path, basename="b", emit_step=True)
    assert r.step_path is not None
    assert r.step_path.exists()
    assert r.step_path.stat().st_size > 0


@pytest.mark.live
@_needs_cq
def test_script_without_a_result_object_fails_clean(tmp_path):
    with pytest.raises(RenderFailed) as exc:
        render_cadquery('cq.Workplane("XY").box(10, 10, 10)', interpreter=_CQ, out_dir=tmp_path)
    assert "result" in str(exc.value).lower()


@pytest.mark.live
@_needs_cq
def test_degenerate_result_fails_clean(tmp_path):
    # A zero-extent / empty workplane must be reported, not silently exported as a broken mesh.
    with pytest.raises(RenderFailed):
        render_cadquery('result = cq.Workplane("XY")', interpreter=_CQ, out_dir=tmp_path)


@pytest.mark.live
@_needs_cq
def test_oversize_output_is_guarded(tmp_path):
    from kimcad.openscad_runner import OversizeOutput

    with pytest.raises(OversizeOutput):
        render_cadquery(_BOX, interpreter=_CQ, out_dir=tmp_path, max_output_bytes=10)


def _run_worker_directly(tmp_path, script_src: str) -> dict:
    """Invoke the worker subprocess DIRECTLY (bypassing sanitize_cadquery) to test the
    worker's OWN defenses in isolation. Returns the parsed result dict."""
    script = tmp_path / "script.py"
    script.write_text(script_src, encoding="utf-8")
    result_path = tmp_path / "result.json"
    request = {
        "script_path": str(script),
        "stl_path": str(tmp_path / "out.stl"),
        "step_path": None,
        "result_path": str(result_path),
    }
    subprocess.run(
        [str(_CQ), str(WORKER_PATH)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=120,
    )
    return json.loads(result_path.read_text(encoding="utf-8"))


@pytest.mark.live
@_needs_cq
def test_worker_sandbox_blocks_open_even_if_the_sanitizer_were_bypassed(tmp_path):
    # Defence in depth: a script that tries to open a file fails — the worker's restricted
    # builtins have no `open`, so nothing touches the filesystem.
    marker = tmp_path / "pwned.txt"
    result = _run_worker_directly(tmp_path, f'result = open(r"{marker}", "w")')
    assert result["ok"] is False
    assert not marker.exists()


@pytest.mark.live
@_needs_cq
@pytest.mark.parametrize("expr", ["eval('1')", "exec('x=1')", "getattr(cq, 'Workplane')"])
def test_worker_withholds_dangerous_builtins_beyond_open(tmp_path, expr):
    # TEST-002: the worker's restricted builtins withhold eval/exec/getattr (not just open) — each
    # fails at the worker layer with a clean error, proving the allowlist holds if the sanitizer
    # were bypassed (the script is sent DIRECTLY to the worker).
    result = _run_worker_directly(tmp_path, f"result = {expr}")
    assert result["ok"] is False
    assert result["kind"] == "exec"


@pytest.mark.live
@_needs_cq
def test_worker_facade_has_no_module_pivot_to_os(tmp_path):
    # The Slice-1 audit Blocker, proven closed at the worker layer: even bypassing the static
    # sanitizer, `cq.exporters` does not exist on the geometry-only facade, so the
    # `cq.exporters.os.system(...)` attribute-graph pivot raises and writes nothing.
    marker = tmp_path / "pwned_via_facade.txt"
    src = f'cq.exporters.os.system(r"echo x > {marker}")\nresult = cq.Workplane().box(1,1,1)'
    result = _run_worker_directly(tmp_path, src)
    assert result["ok"] is False
    assert not marker.exists()


@pytest.mark.live
@_needs_cq
def test_worker_writes_result_to_file_not_stdout(tmp_path):
    # FINDING-002: the result is on a dedicated result_path file, never stdout — so a script
    # (or OCCT's C++ layer) writing to fd 1 can't corrupt the contract. Verify a successful
    # render leaves its JSON in the file with an empty stdout.
    script = tmp_path / "script.py"
    script.write_text('result = cq.Workplane("XY").box(10, 10, 10)', encoding="utf-8")
    result_path = tmp_path / "result.json"
    request = {
        "script_path": str(script),
        "stl_path": str(tmp_path / "out.stl"),
        "step_path": None,
        "result_path": str(result_path),
    }
    proc = subprocess.run(
        [str(_CQ), str(WORKER_PATH)],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.stdout.strip() == ""  # nothing on stdout
    assert json.loads(result_path.read_text(encoding="utf-8"))["ok"] is True
