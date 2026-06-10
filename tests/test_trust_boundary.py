"""Stage C (trust boundary): the local-trust posture is EXPLICIT and DEFENDED, not assumed.

ENG-002: a non-loopback bind requires --allow-remote. ENG-003: the OpenSCAD child runs
secret-scrubbed (shared scrub with the CadQuery worker). ENG-008: the photo on-ramp's
local-only promise is pinned by a test, not by wiring convention. ENG-001's keyring
behavior is covered in test_settings_store.py.
"""

from __future__ import annotations

import subprocess

import pytest

from kimcad import cli


# --- ENG-002: refuse a silent non-loopback bind ------------------------------------------


def test_web_refuses_non_loopback_without_allow_remote(capsys):
    code = cli.main(["web", "--host", "0.0.0.0", "--port", "8799"])
    err = capsys.readouterr().err
    assert code == 2
    assert "--allow-remote" in err
    assert "NO authentication" in err


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
def test_loopback_hosts_need_no_flag(host):
    assert cli._is_loopback_host(host) is True


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "myhost.local", "::"])
def test_non_loopback_hosts_are_gated(host):
    assert cli._is_loopback_host(host) is False


# --- ENG-003: the OpenSCAD child env is secret-scrubbed -----------------------------------


def test_openscad_child_env_omits_planted_secrets(tmp_path, monkeypatch):
    """Plant secrets in the parent env; the env handed to subprocess.run must omit them
    while keeping benign vars and the OPENSCADPATH overlay."""
    import kimcad.openscad_runner as osr

    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-planted")
    monkeypatch.setenv("PRINTER_TOKEN", "tok-planted")
    monkeypatch.setenv("TOKENIZER_PATH", "keep-me")  # look-alike must survive (REAUDIT-N1)

    seen = {}

    def _fake_run(cmd, **kwargs):
        seen["env"] = kwargs.get("env")
        out = tmp_path / "part.3mf"
        out.write_bytes(b"mesh")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(osr.subprocess, "run", _fake_run)
    stub = tmp_path / "openscad.exe"
    stub.write_bytes(b"")
    osr.render_scad("cube(5);", binary=stub, out_dir=tmp_path)

    env = seen["env"]
    assert env is not None
    assert "OPENROUTER_API_KEY" not in env
    assert "PRINTER_TOKEN" not in env
    assert env.get("TOKENIZER_PATH") == "keep-me"
    assert "OPENSCADPATH" in env  # the overlay the child actually needs survives


def test_scrub_is_shared_single_source():
    """ENG-003: both runners consume kimcad.subprocess_env — the scrub can't drift apart."""
    from kimcad import subprocess_env
    from kimcad.cadquery_runner import _is_secret_env

    assert _is_secret_env is subprocess_env.is_secret_env
    assert subprocess_env.is_secret_env("AWS_SECRET_ACCESS_KEY") is True
    assert subprocess_env.is_secret_env("PASSWORDLESS_MODE") is False


# --- ENG-008: the photo on-ramp's local-only promise is pinned ----------------------------


def test_describe_photo_routes_local_even_with_cloud_enabled(monkeypatch, tmp_path):
    """The trust rule 'the photo never leaves your machine' must hold even when the user
    has cloud acceleration enabled + configured — describe_photo always routes to the
    LOCAL vision provider."""
    from kimcad.config import Config
    from kimcad.webapp import build_web_pipeline

    # Cloud fully enabled + configured in settings.
    from kimcad.settings_store import SettingsStore

    store = SettingsStore(Config.load().settings_path())
    store.update({"cloud_enabled": True, "openrouter_api_key": "sk-or-x", "cloud_model": "gpt"})

    calls = {}

    # The local vision path goes through Ollama's native /api/chat via urllib — intercept it.
    import kimcad.llm_provider as lp

    def _fake_local_vision(self, image_bytes, printer, material):
        calls["local"] = True
        return "a rough box"

    monkeypatch.setattr(lp.LLMProvider, "describe_photo", _fake_local_vision)
    pipeline = build_web_pipeline(demo=False)
    seed = pipeline.provider.describe_photo(b"fakebytes", Config.load().printer(None),
                                            Config.load().material(None))
    assert calls.get("local") is True
    assert seed == "a rough box"