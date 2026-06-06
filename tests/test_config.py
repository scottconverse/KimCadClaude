from pathlib import Path

import pytest

import kimcad.cadquery_runner as cadquery_runner
from kimcad.cadquery_runner import find_cadquery_interpreter
from kimcad.config import Config


def test_unknown_printer_material_backend_raise_friendly_errors():
    # QA-301: an unknown --printer/--material/backend/connector must raise a friendly RuntimeError
    # naming the valid options (the CLI catches RuntimeError and prints it cleanly) — never a bare
    # KeyError traceback for a simple typo.
    cfg = Config.load()
    for fn, kind in ((cfg.printer, "printer"), (cfg.material, "material"),
                     (cfg.llm_backend, "LLM backend"), (cfg.connector_config, "connector")):
        with pytest.raises(RuntimeError, match=f"unknown {kind}"):
            fn("definitely-not-a-real-key")


def test_every_shipped_printer_and_material_resolves():
    # TEST-003: breadth across ALL shipped printers/materials (not just the defaults) — each must
    # construct without raising, so a malformed profile in default.yaml fails the suite, not a user.
    cfg = Config.load()
    raw = cfg.raw
    assert raw["printers"] and raw["materials"]
    for pk in raw["printers"]:
        p = cfg.printer(pk)
        assert p.name and p.key == pk
    for mk in raw["materials"]:
        m = cfg.material(mk)
        assert m.name and m.key == mk


def test_loads_default_config():
    cfg = Config.load()
    p = cfg.printer()  # default printer
    assert p.key == "bambu_p2s"
    assert p.build_volume == (256, 256, 256)
    assert p.nozzle_diameter == 0.4
    assert p.reference_hardware is True


def test_material_min_wall():
    cfg = Config.load()
    pla = cfg.material("pla")
    # wall_multiplier 2.0 * nozzle 0.4 = 0.8
    assert abs(pla.min_wall_mm(0.4) - 0.8) < 1e-9


def test_material_carries_nominal_density():
    # Slice 10: materials carry a nominal density (g/cm³) so print weight can be estimated from
    # the slicer's reported volume when the OrcaSlicer profile itself reports none.
    cfg = Config.load()
    assert cfg.material("pla").density == 1.24
    assert cfg.material("petg").density == 1.27
    assert cfg.material("tpu").density == 1.21
    assert cfg.material("abs").density == 1.04


def test_llm_backend_default_is_local():
    # KimCad is local-first: the default backend needs no API key and no network.
    cfg = Config.load()
    b = cfg.llm_backend()
    assert b.key == "local"
    assert b.api_key_env is None
    assert b.base_url.startswith("http://localhost")


def test_cloud_backend_remains_available_as_fallback():
    cfg = Config.load()
    b = cfg.llm_backend("cloud_deepseek")
    assert b.provider == "deepseek"
    assert b.base_url.startswith("https://")


def test_llm_backend_has_generous_default_timeout():
    # A CPU-only local model can take many minutes per call; the client timeout must be
    # well above the OpenAI default so slow generations don't error out mid-run.
    b = Config.load().llm_backend()
    assert b.timeout_s >= 1200.0


def test_llm_backend_timeout_is_overridable():
    cfg = Config({"llm": {"active": "x", "backends": {"x": {
        "provider": "openai_compatible", "base_url": "http://localhost:11434/v1",
        "model_name": "m", "timeout_s": 300}}}})
    assert cfg.llm_backend().timeout_s == 300.0


def test_binary_path_resolves_to_project_root():
    cfg = Config.load()
    p = cfg.binary_path("openscad")
    assert p.is_absolute()
    assert "tools" in p.parts


# --- Stage 8: CadQuery interpreter discovery + config -------------------------------------

def test_cadquery_python_false_disables_without_probing(monkeypatch):
    # `false` forces the backend off — and must NOT spawn a discovery probe.
    called = []
    monkeypatch.setattr(
        cadquery_runner, "find_cadquery_interpreter", lambda *a, **k: called.append(1)
    )
    cfg = Config({"binaries": {"cadquery_python": False}})
    assert cfg.cadquery_interpreter() is None
    assert called == []


def test_cadquery_python_empty_string_disables_without_probing(monkeypatch):
    # SLICE2-002: an explicitly-cleared value ("") is treated like `false` (off), not as a
    # falsy value that silently auto-discovers.
    called = []
    monkeypatch.setattr(
        cadquery_runner, "find_cadquery_interpreter", lambda *a, **k: called.append(1)
    )
    cfg = Config({"binaries": {"cadquery_python": ""}})
    assert cfg.cadquery_interpreter() is None
    assert called == []


def test_cadquery_python_explicit_path_is_authoritative(monkeypatch):
    seen = {}

    def fake(cands=(), *, include_defaults=True):
        seen["cands"] = list(cands)
        seen["include_defaults"] = include_defaults
        return Path("/explicit/python")

    monkeypatch.setattr(cadquery_runner, "find_cadquery_interpreter", fake)
    cfg = Config({"binaries": {"cadquery_python": "/explicit/python"}})
    assert cfg.cadquery_interpreter() == Path("/explicit/python")
    assert seen["cands"] == ["/explicit/python"]
    assert seen["include_defaults"] is False  # no auto-discovery fall-through


def test_cadquery_python_null_auto_probes(monkeypatch):
    seen = {}

    def fake(cands=(), *, include_defaults=True):
        seen["cands"] = list(cands)
        seen["include_defaults"] = include_defaults
        return None

    monkeypatch.setattr(cadquery_runner, "find_cadquery_interpreter", fake)
    cfg = Config({"binaries": {"cadquery_python": None}})
    assert cfg.cadquery_interpreter() is None
    assert seen["cands"] == []
    assert seen["include_defaults"] is True


def test_cadquery_interpreter_is_cached(monkeypatch):
    n = {"calls": 0}

    def fake(*a, **k):
        n["calls"] += 1
        return Path("/p")

    monkeypatch.setattr(cadquery_runner, "find_cadquery_interpreter", fake)
    cfg = Config({"binaries": {"cadquery_python": None}})
    assert cfg.cadquery_interpreter() == Path("/p")
    assert cfg.cadquery_interpreter() == Path("/p")
    assert n["calls"] == 1  # probed at most once per Config


def test_cadquery_timeout_default_and_override():
    assert Config.load().cadquery_timeout_s() == 120
    assert Config({"limits": {"cadquery_timeout_s": 45}}).cadquery_timeout_s() == 45


@pytest.mark.live
@pytest.mark.skipif(find_cadquery_interpreter() is None, reason="no cadquery interpreter")
def test_real_cadquery_interpreter_is_discovered():
    p = Config.load().cadquery_interpreter()
    assert p is not None
    assert p.exists()
