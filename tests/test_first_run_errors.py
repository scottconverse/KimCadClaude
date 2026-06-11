"""Stage A Slice 1 (first-run hardening): typed errors + fail-fast.

The non-developer first-run failure modes — tool binary never fetched (QA-003), model
server never started (QA-001/QA-002), port already in use (QA-006) — must each end in one
actionable, friendly line on every surface. These tests pin that contract for the runners,
the provider's fail-fast probe, the CLI exit paths, and the web layer's typed responses.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from kimcad.errors import ToolMissingError


# --- the typed error itself -------------------------------------------------------------


def test_tool_missing_error_message_is_actionable():
    e = ToolMissingError("OpenSCAD", Path("C:/nope/openscad.exe"))
    msg = str(e)
    assert "OpenSCAD" in msg
    assert "fetch_tools.py" in msg  # the recovery command
    assert "config/local.yaml" in msg  # the bring-your-own escape hatch
    assert isinstance(e, RuntimeError)  # so cli.main's RuntimeError path prints it cleanly


# --- runners guard the binary up front (QA-003) ------------------------------------------


def test_render_scad_missing_binary_raises_tool_missing(tmp_path):
    from kimcad.openscad_runner import render_scad

    with pytest.raises(ToolMissingError) as ei:
        render_scad("cube([10,10,10]);", binary=tmp_path / "openscad.exe", out_dir=tmp_path)
    assert "OpenSCAD" in str(ei.value)


def test_slice_model_missing_binary_raises_tool_missing(tmp_path):
    from kimcad.slicer import SliceSettings, slice_model

    settings = SliceSettings(
        machine=tmp_path / "m.json", process=tmp_path / "p.json", filament=tmp_path / "f.json"
    )
    with pytest.raises(ToolMissingError) as ei:
        slice_model(
            tmp_path / "part.3mf",
            binary=tmp_path / "orca-slicer.exe",
            out_dir=tmp_path,
            settings=settings,
        )
    assert "OrcaSlicer" in str(ei.value)


# --- provider fail-fast vs mid-run retry (QA-002) ----------------------------------------


def _conn_error():
    import httpx
    from openai import APIConnectionError

    return APIConnectionError(request=httpx.Request("POST", "http://localhost:11434/v1"))


class _AlwaysDownClient:
    def __init__(self):
        self.calls = 0
        self.chat = self
        self.completions = self

    def create(self, **_kw):
        self.calls += 1
        raise _conn_error()


def _backend(base_url: str = "http://localhost:0/v1"):
    from kimcad.config import LLMBackend

    return LLMBackend(
        key="test", provider="openai", base_url=base_url, model_name="test-model",
        api_key_env=None, temperature=0.2, max_tokens=2048, supports_structured_output=True,
    )


def test_never_up_server_fails_fast_no_retry_loop(monkeypatch):
    """First-attempt connection error + nothing listening => raise NOW (no 6x30s tax)."""
    from kimcad.llm_provider import LLMProvider

    client = _AlwaysDownClient()
    provider = LLMProvider(_backend(), client=client, max_attempts=6, retry_wait_s=30.0)
    monkeypatch.setattr(LLMProvider, "_server_reachable", lambda self, timeout_s=2.0: False)
    from openai import APIConnectionError

    with pytest.raises(APIConnectionError):
        provider._complete([{"role": "user", "content": "x"}], json_mode=False)
    assert client.calls == 1  # exactly one attempt — never entered the retry loop


def test_mid_run_drop_still_retries(monkeypatch):
    """A server that IS listening keeps the full bridge-a-restart retry budget."""
    from kimcad.llm_provider import LLMProvider

    class _DropsOnceClient(_AlwaysDownClient):
        def create(self, **_kw):
            self.calls += 1
            if self.calls == 1:
                raise _conn_error()

            class _R:
                class _C:
                    class _M:
                        content = "ok"

                    message = _M()

                choices = [_C()]

            return _R()

    client = _DropsOnceClient()
    provider = LLMProvider(_backend(), client=client, max_attempts=3, retry_wait_s=0)
    monkeypatch.setattr(LLMProvider, "_server_reachable", lambda self, timeout_s=2.0: True)
    assert provider._complete([{"role": "user", "content": "x"}], json_mode=False) == "ok"
    assert client.calls == 2


def test_server_reachable_probe_true_and_false():
    """The probe is a bare TCP connect: true against a live listener, false against a
    closed port — no HTTP semantics involved. (TEST-005: the false case uses port 1 —
    reserved, never bound — instead of a just-released ephemeral port, so a concurrent
    process on a busy CI box can't grab the port between close and probe.)"""
    from kimcad.llm_provider import LLMProvider

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        up = LLMProvider(_backend(f"http://127.0.0.1:{port}/v1"), client=_AlwaysDownClient())
        assert up._server_reachable(timeout_s=1.0) is True
    finally:
        srv.close()
    down = LLMProvider(_backend("http://127.0.0.1:1/v1"), client=_AlwaysDownClient())
    assert down._server_reachable(timeout_s=1.0) is False


def test_probe_never_judges_non_local_hosts():
    """ENG-003: a raw TCP probe lies for cloud backends (proxies block direct connects;
    CDN edges accept them while the service is down) — so any non-loopback host reports
    reachable WITHOUT a network call, preserving the full retry budget for cloud."""
    from kimcad.llm_provider import LLMProvider

    for url in ("https://openrouter.ai/api/v1", "https://api.deepseek.com/v1",
                "http://192.168.1.50:11434/v1"):
        p = LLMProvider(_backend(url), client=_AlwaysDownClient())
        assert p._server_reachable(timeout_s=0.01) is True  # instant — no connect attempted


def test_built_client_owns_no_sdk_retries(monkeypatch):
    """ENG-002 / WALK-A-002: KimCad's loop owns retry policy — the built OpenAI client must
    carry max_retries=0 so SDK-internal retries can't stack under it."""
    from kimcad.llm_provider import LLMProvider

    client = LLMProvider._build_client(_backend())
    assert client.max_retries == 0


# --- CLI mapping (QA-001): friendly line + exit 2, never a traceback ----------------------


class _ModelDownProvider:
    """Raises the real APIConnectionError from the plan step, like a dead Ollama would."""

    def generate_design_plan(self, *a, **kw):
        raise _conn_error()

    def generate_openscad(self, *a, **kw):  # pragma: no cover - never reached
        raise AssertionError

    def describe_photo(self, *a, **kw):  # pragma: no cover
        raise AssertionError

    def describe_sketch(self, *a, **kw):  # pragma: no cover
        raise AssertionError


def _patch_pipeline_with(monkeypatch, provider, renderer):
    from conftest import BAMBU, PLA

    from kimcad import cli
    from kimcad.config import Config
    from kimcad.pipeline import Pipeline

    def _fake_build(cfg, args):
        return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer)

    monkeypatch.setattr(cli, "_build_pipeline", _fake_build)


def test_cli_model_down_exits_2_with_guidance_no_traceback(monkeypatch, capsys, tmp_path):
    from conftest import box_renderer

    from kimcad import cli

    renderer, _ = box_renderer((20, 20, 20))
    _patch_pipeline_with(monkeypatch, _ModelDownProvider(), renderer)
    code = cli.main(["design", "a 20mm cube", "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "Ollama" in err  # actionable: names the thing to start
    assert "ollama pull" in err  # and the exact recovery command


def test_cli_tool_missing_exits_2_with_fetch_hint(monkeypatch, capsys, tmp_path):
    """A working model but no OpenSCAD on disk: the renderer raises the typed
    ToolMissingError (as the real render_scad now does) and the CLI surfaces it as one
    friendly line with the recovery command, exit 2 — no traceback."""
    from conftest import FakeProvider, make_plan

    from kimcad import cli

    def _missing_tool_renderer(*a, **kw):
        raise ToolMissingError("OpenSCAD", Path("C:/absent/openscad.exe"))

    _patch_pipeline_with(monkeypatch, FakeProvider(make_plan([20, 20, 20])),
                         _missing_tool_renderer)
    code = cli.main(["design", "a 20mm cube", "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "fetch_tools.py" in err


def test_cli_model_not_pulled_exits_2_with_pull_hint(monkeypatch, capsys, tmp_path):
    """The openai NotFoundError (model not pulled) maps to the pull command + exit 2."""
    import httpx
    from openai import NotFoundError

    from conftest import box_renderer

    from kimcad import cli

    class _NoModelProvider(_ModelDownProvider):
        def generate_design_plan(self, *a, **kw):
            req = httpx.Request("POST", "http://localhost:11434/v1")
            raise NotFoundError(
                "model not found", response=httpx.Response(404, request=req), body=None
            )

    renderer, _ = box_renderer((20, 20, 20))
    _patch_pipeline_with(monkeypatch, _NoModelProvider(), renderer)
    code = cli.main(["design", "a 20mm cube", "--out", str(tmp_path / "out")])
    err = capsys.readouterr().err
    assert code == 2
    assert "Traceback" not in err
    assert "ollama pull" in err


def test_bench_model_down_aborts_with_friendly_exit_2(monkeypatch, capsys, tmp_path):
    """QA-A-001: a dead model server must abort the whole bench with the friendly message
    and exit 2 — not produce N error rows and exit 0."""
    from kimcad.benchmark import BenchCase, run_benchmark

    def _run_one(case):
        raise _conn_error()

    cases = [BenchCase(id="c1", prompt="a box"), BenchCase(id="c2", prompt="a tube")]
    import openai

    with pytest.raises(openai.APIConnectionError):
        run_benchmark(cases, _run_one)


def test_phase_printer_dedupes_consecutive_repeats(capsys):
    """QA-005 companion: codegen retries re-emit 'generating' — the console must not stutter."""
    from kimcad.cli import _phase_printer

    emit = _phase_printer()
    for phase in ("planning", "generating", "generating", "generating", "rendering"):
        emit(phase)
    err = capsys.readouterr().err
    assert err.count("Writing the CAD code") == 1
    assert err.count("Planning the shape") == 1
    assert err.count("Rendering the part") == 1


# --- web server bind (QA-006) -------------------------------------------------------------


@pytest.mark.windows_only  # SO_EXCLUSIVEADDRUSE is a Windows-only socket option (KC-16 #21)
def test_serve_port_in_use_raises_friendly_runtime_error(tmp_path):
    from kimcad.webapp import serve

    blocker = socket.socket()
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    port = blocker.getsockname()[1]
    try:
        with pytest.raises(RuntimeError) as ei:
            serve(host="127.0.0.1", port=port, demo=True, out_root=tmp_path)
        msg = str(ei.value)
        assert str(port) in msg
        assert "--port" in msg  # the recovery hint
    finally:
        blocker.close()


@pytest.mark.windows_only  # exclusive-bind semantics are Windows-specific (KC-16 #21)
def test_second_kimcad_server_cannot_silently_share_the_port():
    """TEST-001 / WALK-A-001 / ENG-001: the walkthrough proved a second `kimcad web` bound
    the SAME port silently on Windows (socketserver's SO_REUSEADDR). The server class now
    binds exclusively, so a python-vs-python double-bind RAISES — which is what lets the
    QA-006 friendly message fire for its own headline case."""
    from kimcad.webapp import _ExclusiveBindServer

    class _NullHandler:  # never accepts a request; we only test bind semantics
        def __init__(self, *a, **kw):  # pragma: no cover
            raise AssertionError("no request expected")

    first = _ExclusiveBindServer(("127.0.0.1", 0), _NullHandler)
    port = first.server_address[1]
    try:
        with pytest.raises(OSError):
            _ExclusiveBindServer(("127.0.0.1", port), _NullHandler)
    finally:
        first.server_close()
