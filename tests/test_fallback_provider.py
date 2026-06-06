"""Stage 6 Slice 2 -- tiered LLM fallback chain (FallbackProvider).

Covers:
  - primary success -> alt is never called
  - primary failure on APIConnectionError / APITimeoutError / NotFoundError -> alt called
  - no alt configured -> primary error propagates unchanged
  - thread-local stickiness: once on alt, subsequent calls skip primary
  - primary.max_attempts reduced to 1 when alt is configured (fail-fast)
  - primary.max_attempts unchanged when no alt (retain full retry budget)
  - Config.llm_alt_backend() returns None when key absent or null
  - Config.llm_alt_backend() returns the backend when key is set
  - _build_pipeline wires FallbackProvider when alt_backend configured
  - _build_pipeline uses bare LLMProvider when alt_backend not configured
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import httpx
import pytest

from kimcad.llm_provider import FallbackProvider, LLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_provider(return_val: object = "ok", error: Exception | None = None) -> MagicMock:
    """Return a mock LLMProvider with controllable outcomes."""
    p = MagicMock(spec=LLMProvider)
    p.backend = MagicMock()
    p.backend.key = "mock_backend"
    p.max_attempts = 3
    if error is not None:
        p.generate_design_plan.side_effect = error
        p.generate_openscad.side_effect = error
    else:
        p.generate_design_plan.return_value = return_val
        p.generate_openscad.return_value = return_val
    return p


def _request() -> httpx.Request:
    return httpx.Request("POST", "http://localhost:11434/v1/chat/completions")


def _conn_err() -> Exception:
    from openai import APIConnectionError
    return APIConnectionError(request=_request())


def _timeout_err() -> Exception:
    from openai import APITimeoutError
    return APITimeoutError(request=_request())


def _not_found_err() -> Exception:
    from openai import NotFoundError
    resp = httpx.Response(
        404,
        request=_request(),
        content=b'{"error":{"message":"model not found"}}',
    )
    return NotFoundError("model not found", response=resp, body=None)


# ---------------------------------------------------------------------------
# Routing: primary success
# ---------------------------------------------------------------------------

def test_primary_success_alt_never_called():
    primary = _mock_provider(return_val="plan")
    alt = _mock_provider(return_val="plan_alt")
    fp = FallbackProvider(primary, alt)
    result = fp.generate_design_plan("prompt", MagicMock(), MagicMock())
    assert result == "plan"
    alt.generate_design_plan.assert_not_called()


def test_primary_success_openscad_alt_never_called():
    primary = _mock_provider(return_val="scad_code")
    alt = _mock_provider(return_val="scad_alt")
    fp = FallbackProvider(primary, alt)
    result = fp.generate_openscad(MagicMock(), MagicMock(), MagicMock())
    assert result == "scad_code"
    alt.generate_openscad.assert_not_called()


# ---------------------------------------------------------------------------
# Routing: primary failure -> alt
# ---------------------------------------------------------------------------

def test_fallback_on_api_connection_error():
    primary = _mock_provider(error=_conn_err())
    alt = _mock_provider(return_val="plan_alt")
    fp = FallbackProvider(primary, alt)
    result = fp.generate_design_plan("p", MagicMock(), MagicMock())
    assert result == "plan_alt"


def test_fallback_on_api_timeout_error():
    primary = _mock_provider(error=_timeout_err())
    alt = _mock_provider(return_val="plan_alt")
    fp = FallbackProvider(primary, alt)
    result = fp.generate_design_plan("p", MagicMock(), MagicMock())
    assert result == "plan_alt"


def test_fallback_on_model_not_found():
    primary = _mock_provider(error=_not_found_err())
    alt = _mock_provider(return_val="plan_alt")
    fp = FallbackProvider(primary, alt)
    result = fp.generate_design_plan("p", MagicMock(), MagicMock())
    assert result == "plan_alt"


def test_no_alt_connection_error_propagates():
    from openai import APIConnectionError
    primary = _mock_provider(error=_conn_err())
    fp = FallbackProvider(primary, alt=None)
    with pytest.raises(APIConnectionError):
        fp.generate_design_plan("p", MagicMock(), MagicMock())


def test_no_alt_timeout_error_propagates():
    from openai import APITimeoutError
    primary = _mock_provider(error=_timeout_err())
    fp = FallbackProvider(primary, alt=None)
    with pytest.raises(APITimeoutError):
        fp.generate_design_plan("p", MagicMock(), MagicMock())


# ---------------------------------------------------------------------------
# Thread-local stickiness
# ---------------------------------------------------------------------------

def test_sticky_alt_subsequent_calls_skip_primary():
    """Once a thread falls back to alt, following calls bypass primary entirely."""
    primary = _mock_provider(error=_conn_err())
    alt = _mock_provider(return_val="alt_ok")
    fp = FallbackProvider(primary, alt)

    # First call: primary fails, alt kicks in.
    fp.generate_design_plan("p", MagicMock(), MagicMock())

    # Reset primary call counts so we can observe the second call clearly.
    primary.generate_openscad.reset_mock()
    primary.generate_design_plan.reset_mock()

    # Second call on the same thread: should go directly to alt, never touching primary.
    fp.generate_openscad(MagicMock(), MagicMock(), MagicMock())
    primary.generate_openscad.assert_not_called()
    alt.generate_openscad.assert_called_once()


def test_stickiness_is_thread_local():
    """Stickiness on one thread does NOT affect a separate thread."""
    primary_errors: list[Exception] = [_conn_err()]

    def _primary_gdp(*args, **kwargs):
        if primary_errors:
            raise primary_errors.pop(0)
        return "primary_ok"

    primary = MagicMock(spec=LLMProvider)
    primary.backend = MagicMock()
    primary.backend.key = "p"
    primary.max_attempts = 3
    primary.generate_design_plan.side_effect = _primary_gdp
    alt = _mock_provider(return_val="alt_ok")

    fp = FallbackProvider(primary, alt)

    results: dict[str, str] = {}

    def thread_a():
        # This thread triggers the fallback.
        results["a"] = fp.generate_design_plan("p", MagicMock(), MagicMock())

    def thread_b():
        # Primary has no more errors; this thread should succeed on primary.
        results["b"] = fp.generate_design_plan("p", MagicMock(), MagicMock())

    ta = threading.Thread(target=thread_a)
    ta.start()
    ta.join()

    tb = threading.Thread(target=thread_b)
    tb.start()
    tb.join()

    assert results["a"] == "alt_ok"   # thread A fell back to alt
    assert results["b"] == "primary_ok"  # thread B hit primary (no error, no stickiness)


# ---------------------------------------------------------------------------
# max_attempts reduction
# ---------------------------------------------------------------------------

def test_primary_max_attempts_reduced_when_alt_configured():
    primary = _mock_provider()
    primary.max_attempts = 6
    alt = _mock_provider()
    FallbackProvider(primary, alt)
    assert primary.max_attempts == 1


def test_primary_max_attempts_unchanged_when_no_alt():
    primary = _mock_provider()
    primary.max_attempts = 6
    FallbackProvider(primary, alt=None)
    assert primary.max_attempts == 6


# ---------------------------------------------------------------------------
# Config.llm_alt_backend()
# ---------------------------------------------------------------------------

def test_config_llm_alt_backend_returns_none_when_not_set():
    from kimcad.config import Config
    cfg = Config({"llm": {"active": "local", "backends": {"local": {
        "provider": "x", "base_url": "http://localhost", "model_name": "m",
        "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
        "supports_structured_output": False,
    }}}})
    assert cfg.llm_alt_backend() is None


def test_config_llm_alt_backend_returns_none_when_explicitly_null():
    from kimcad.config import Config
    cfg = Config({"llm": {"active": "local", "alt_backend": None, "backends": {"local": {
        "provider": "x", "base_url": "http://localhost", "model_name": "m",
        "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
        "supports_structured_output": False,
    }}}})
    assert cfg.llm_alt_backend() is None


def test_config_llm_alt_backend_returns_backend_when_key_set():
    from kimcad.config import Config, LLMBackend
    backends = {
        "local": {
            "provider": "x", "base_url": "http://localhost", "model_name": "local_m",
            "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
            "supports_structured_output": False,
        },
        "cloud": {
            "provider": "deepseek", "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-v4-flash", "api_key_env": "DS_KEY",
            "temperature": 0.2, "max_tokens": 8192, "supports_structured_output": True,
        },
    }
    cfg = Config({"llm": {"active": "local", "alt_backend": "cloud", "backends": backends}})
    alt = cfg.llm_alt_backend()
    assert isinstance(alt, LLMBackend)
    assert alt.key == "cloud"
    assert alt.model_name == "deepseek-v4-flash"


# ---------------------------------------------------------------------------
# _build_pipeline wiring
# ---------------------------------------------------------------------------

def test_build_pipeline_uses_fallback_provider_when_alt_backend_configured(monkeypatch):
    from kimcad.config import Config
    import kimcad.cli as cli_mod

    backends = {
        "local": {
            "provider": "x", "base_url": "http://localhost", "model_name": "m",
            "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
            "supports_structured_output": False,
        },
        "cloud": {
            "provider": "y", "base_url": "https://api.example.com/v1", "model_name": "cloud_m",
            "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
            "supports_structured_output": True,
        },
    }
    printers = {"p": {"name": "P", "build_volume": [200, 200, 200], "nozzle_diameter": 0.4}}
    materials = {"m": {"name": "PLA", "nozzle_temp": 210, "bed_temp": 55,
                        "wall_multiplier": 2.0, "shrinkage": 0.002}}
    cfg = Config({
        "llm": {"active": "local", "alt_backend": "cloud", "backends": backends},
        "printers": printers, "defaults": {"printer": "p", "material": "m", "output_format": "3mf"},
        "materials": materials, "binaries": {"openscad": "x", "orcaslicer": "y"},
        "limits": {"openscad_timeout_simple_s": 30, "openscad_timeout_complex_s": 120,
                   "max_output_bytes": 1024, "slice_timeout_s": 60},
        "connectors": {},
    })

    captured_provider = []

    class _FakePipeline:
        def __init__(self, config, printer, material, provider, **kwargs):
            captured_provider.append(provider)

    args = MagicMock()
    args.printer = None
    args.material = None
    args.backend = None

    # _build_pipeline does `from kimcad.pipeline import Pipeline` at call time, so we
    # must patch on the source module (kimcad.pipeline), not on kimcad.cli.
    with patch("kimcad.pipeline.Pipeline", _FakePipeline), \
         patch("kimcad.llm_provider.LLMProvider._build_client", return_value=MagicMock()):
        cli_mod._build_pipeline(cfg, args)

    assert len(captured_provider) == 1
    assert isinstance(captured_provider[0], FallbackProvider)
    assert captured_provider[0].alt is not None


def test_build_pipeline_uses_bare_provider_when_no_alt(monkeypatch):
    from kimcad.config import Config
    import kimcad.cli as cli_mod

    backends = {"local": {
        "provider": "x", "base_url": "http://localhost", "model_name": "m",
        "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
        "supports_structured_output": False,
    }}
    printers = {"p": {"name": "P", "build_volume": [200, 200, 200], "nozzle_diameter": 0.4}}
    materials = {"m": {"name": "PLA", "nozzle_temp": 210, "bed_temp": 55,
                        "wall_multiplier": 2.0, "shrinkage": 0.002}}
    cfg = Config({
        "llm": {"active": "local", "backends": backends},
        "printers": printers, "defaults": {"printer": "p", "material": "m", "output_format": "3mf"},
        "materials": materials, "binaries": {"openscad": "x", "orcaslicer": "y"},
        "limits": {"openscad_timeout_simple_s": 30, "openscad_timeout_complex_s": 120,
                   "max_output_bytes": 1024, "slice_timeout_s": 60},
        "connectors": {},
    })

    captured_provider = []

    class _FakePipeline:
        def __init__(self, config, printer, material, provider, **kwargs):
            captured_provider.append(provider)

    args = MagicMock()
    args.printer = None
    args.material = None
    args.backend = None

    with patch("kimcad.pipeline.Pipeline", _FakePipeline), \
         patch("kimcad.llm_provider.LLMProvider._build_client", return_value=MagicMock()):
        cli_mod._build_pipeline(cfg, args)

    assert len(captured_provider) == 1
    assert isinstance(captured_provider[0], LLMProvider)  # bare, not wrapped


# ---------------------------------------------------------------------------
# webapp._real_provider wiring (the UI-facing path -- must mirror the CLI)
# ---------------------------------------------------------------------------

def _web_config(*, alt: bool) -> object:
    from kimcad.config import Config
    backends = {
        "local": {
            "provider": "x", "base_url": "http://localhost", "model_name": "m",
            "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
            "supports_structured_output": False,
        },
        "cloud": {
            "provider": "y", "base_url": "https://api.example.com/v1", "model_name": "cloud_m",
            "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
            "supports_structured_output": True,
        },
    }
    llm: dict[str, object] = {"active": "local", "backends": backends}
    if alt:
        llm["alt_backend"] = "cloud"
    return Config({"llm": llm})


def test_real_provider_uses_fallback_when_alt_configured():
    from kimcad import webapp
    cfg = _web_config(alt=True)
    with patch("kimcad.llm_provider.LLMProvider._build_client", return_value=MagicMock()):
        provider = webapp._real_provider(cfg, None)
    assert isinstance(provider, FallbackProvider)
    assert provider.alt is not None


def test_real_provider_uses_bare_provider_when_no_alt():
    from kimcad import webapp
    cfg = _web_config(alt=False)
    with patch("kimcad.llm_provider.LLMProvider._build_client", return_value=MagicMock()):
        provider = webapp._real_provider(cfg, None)
    assert isinstance(provider, LLMProvider)  # bare, not wrapped


# ---------------------------------------------------------------------------
# TEST-001: an arbitrary (non-transport) primary error must NOT trigger fallback
# ---------------------------------------------------------------------------

def test_arbitrary_primary_error_propagates_and_skips_alt():
    # FallbackProvider falls back ONLY on transport errors (connection/timeout/404). An
    # arbitrary exception (a real bug) must propagate with alt NEVER touched -- otherwise a
    # broaden-to-`except Exception` refactor would silently retry a bug on the alt model
    # (a cost/privacy surprise) and ship green past the positive-only fallback tests.
    primary = _mock_provider(error=RuntimeError("a real bug, not a transport failure"))
    alt = _mock_provider(return_val="alt_ok")
    fp = FallbackProvider(primary, alt)
    with pytest.raises(RuntimeError):
        fp.generate_design_plan("p", MagicMock(), MagicMock())
    alt.generate_design_plan.assert_not_called()


# ---------------------------------------------------------------------------
# TEST-003: the bake-off's per-backend pipeline is BARE (no fallback contamination)
# ---------------------------------------------------------------------------

def test_pipeline_for_backend_is_bare_even_with_alt_configured():
    # The bake-off measures each model in isolation: _pipeline_for_backend must build a BARE
    # LLMProvider (never FallbackProvider) even when an alt_backend IS configured -- a silent
    # fallback would swap in the other model mid-run and corrupt the head-to-head comparison.
    from kimcad.config import Config
    import kimcad.cli as cli_mod

    backends = {
        "local": {"provider": "x", "base_url": "http://localhost", "model_name": "m",
                  "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
                  "supports_structured_output": False},
        "cloud": {"provider": "y", "base_url": "https://api.example.com/v1", "model_name": "c",
                  "api_key_env": None, "temperature": 0.2, "max_tokens": 512,
                  "supports_structured_output": True},
    }
    cfg = Config({"llm": {"active": "local", "alt_backend": "cloud", "backends": backends}})

    captured = []

    class _FakePipeline:
        def __init__(self, config, printer, material, provider, **kwargs):
            captured.append(provider)

    with patch("kimcad.pipeline.Pipeline", _FakePipeline), \
         patch("kimcad.llm_provider.LLMProvider._build_client", return_value=MagicMock()):
        cli_mod._pipeline_for_backend(cfg, "local", MagicMock(), MagicMock())

    assert len(captured) == 1
    assert isinstance(captured[0], LLMProvider)
    assert not isinstance(captured[0], FallbackProvider)  # the alt is deliberately ignored


def test_fallback_switch_message_never_leaks_the_api_key(capsys):
    # TEST-101: the model layer is the secret-holding path. When the primary fails and the chain
    # switches to the cloud alt, it logs to stderr — that line must name the backend by its config
    # KEY only, never the API-key VALUE. (The connectors have this guard; the model layer must too.)
    sentinel = "KIMCAD-SENTINEL-apikey-must-never-appear-in-logs"
    primary = _mock_provider(error=_conn_err())
    alt = _mock_provider(return_val="ok")
    alt.backend.key = "cloud_alt"  # the config name — safe to print
    # Plant the sentinel where a careless log line might pull it from, to prove it doesn't.
    alt.backend.api_key = sentinel
    primary.backend.api_key = sentinel
    fp = FallbackProvider(primary, alt)
    fp.generate_design_plan("a box", MagicMock(), MagicMock())
    err = capsys.readouterr().err
    assert "cloud_alt" in err  # the switch message names the backend by its config key
    assert sentinel not in err  # ...and never the API-key value
