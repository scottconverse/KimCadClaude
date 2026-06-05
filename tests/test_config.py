from kimcad.config import Config


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
