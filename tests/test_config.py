from pathlib import Path

import pytest

import kimcad.cadquery_runner as cadquery_runner
from kimcad.cadquery_runner import find_cadquery_interpreter
from kimcad.config import Config, UnknownConfigKey, UntrustedCloudHost


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


def test_binary_path_resolves_to_project_root(tmp_path, monkeypatch):
    # The SHIPPED default (config/default.yaml) resolves OpenSCAD under the bundled tools/ tree,
    # relative to the project root. This must be asserted against the SHIPPED config, isolated
    # from a developer's per-machine config/local.yaml — which may point binaries at an absolute
    # path outside tools/ (e.g. a system install under ..\_tools\...); tests must not depend on a
    # particular dev box's local override (the reason this previously went red on a box whose
    # local.yaml uses absolute tool paths). We load default-only (local=None).
    from kimcad import config as config_mod

    cfg = Config.load(local=None)
    # The shipped default is a tools/-relative path: confirm that contract directly, so this can't
    # silently regress to an absolute path that happens to contain "tools".
    raw = cfg.raw["binaries"]["openscad"]
    assert not Path(raw).is_absolute()
    assert Path(raw).parts[0] == "tools"
    # And prove the resolution flows through the project root and lands, absolute, under tools/.
    # binary_path() also enforces the binary EXISTS on disk (ENG-002), and the bundled tools/ tree
    # isn't fetched on every box — so materialize the resolved location in an isolated tmp PROJECT_ROOT
    # rather than writing into the real repo (which would race parallel runs / dirty the tree).
    monkeypatch.setattr(config_mod, "PROJECT_ROOT", tmp_path)
    target = tmp_path / raw
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"")
    p = cfg.binary_path("openscad")
    assert p.is_absolute()
    assert "tools" in p.parts


# --- ENG-002 (audit-team-b4): binary_path validates existence + warns on escape ----------

def test_binary_path_raises_typed_error_when_not_a_file(tmp_path):
    # ENG-002: a missing/typo'd binary path now fails with a typed, readable UnknownConfigKey
    # (a RuntimeError subclass the CLI/web layer already handle) instead of an opaque downstream
    # OSError from subprocess.run.
    missing = tmp_path / "does-not-exist.exe"
    cfg = Config({"binaries": {"openscad": str(missing)}})
    with pytest.raises(UnknownConfigKey, match="not a file"):
        cfg.binary_path("openscad")


def test_binary_path_warns_when_binary_escapes_install_root(tmp_path):
    # ENG-002: an absolute binary OUTSIDE the install root resolves (operator-controlled config is
    # honored by design) but warns — defense-in-depth against a config that points the exec sink at
    # an arbitrary system path. The file must exist so we pass the is_file() gate first.
    outside = tmp_path / "rogue.exe"
    outside.write_text("stub", encoding="utf-8")
    cfg = Config({"binaries": {"openscad": str(outside)}})
    with pytest.warns(UserWarning, match="outside the install root"):
        p = cfg.binary_path("openscad")
    assert p == outside


# --- ENG-001 (audit-team-b4): cloud base_url is scheme/host-validated --------------------

def test_shipped_cloud_hosts_are_derived_from_default_config():
    # ENG-001: the allow-list is READ from the shipped default.yaml backends (not hardcoded), so it
    # stays correct as backends are added. Today: openrouter.ai + api.deepseek.com.
    hosts = Config.shipped_cloud_hosts()
    assert "openrouter.ai" in hosts
    assert "api.deepseek.com" in hosts
    # localhost/loopback backends (the `local` default) must NOT be on the cloud allow-list.
    assert "localhost" not in hosts


def test_validate_cloud_base_url_accepts_shipped_https_hosts():
    # The shipped OpenRouter + DeepSeek endpoints pass unchanged.
    assert Config.validate_cloud_base_url("https://openrouter.ai/api/v1")
    assert Config.validate_cloud_base_url("https://api.deepseek.com/v1")


def test_validate_cloud_base_url_refuses_non_https():
    # ENG-001: an http:// cloud endpoint (downgrade) is refused with a clear error.
    with pytest.raises(UntrustedCloudHost, match="non-https"):
        Config.validate_cloud_base_url("http://openrouter.ai/api/v1")


def test_validate_cloud_base_url_refuses_unlisted_host():
    # ENG-001: the core exfiltration vector — a tampered local.yaml naming an attacker host — is
    # refused even over https.
    with pytest.raises(UntrustedCloudHost, match="unrecognized cloud host"):
        Config.validate_cloud_base_url("https://attacker.example/v1")


def test_validate_cloud_base_url_exempts_loopback():
    # A local/loopback endpoint never leaves the box, so the cloud allow-list doesn't apply
    # (and a 127.x trick host is still treated as loopback only when it parses as a loopback IP).
    assert Config.validate_cloud_base_url("http://localhost:11434/v1")
    assert Config.validate_cloud_base_url("http://127.0.0.1:11434/v1")
    # ...but a deceptive hostname that merely *starts* 127 is NOT loopback -> still gated.
    with pytest.raises(UntrustedCloudHost):
        Config.validate_cloud_base_url("http://127.evil.example/v1")


def test_validate_cloud_base_url_escape_hatch_env_var(monkeypatch):
    # ENG-001: the documented opt-out for advanced users who knowingly add a custom endpoint.
    # Fail closed by default; KIMCAD_ALLOW_CUSTOM_CLOUD_HOST=1 lets a custom host through.
    monkeypatch.delenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", raising=False)
    with pytest.raises(UntrustedCloudHost):
        Config.validate_cloud_base_url("https://my-proxy.internal/v1")
    monkeypatch.setenv("KIMCAD_ALLOW_CUSTOM_CLOUD_HOST", "1")
    assert Config.validate_cloud_base_url("https://my-proxy.internal/v1")


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
@pytest.mark.needs_cadquery
@pytest.mark.skipif(find_cadquery_interpreter() is None, reason="no cadquery interpreter")
def test_real_cadquery_interpreter_is_discovered():
    p = Config.load().cadquery_interpreter()
    assert p is not None
    assert p.exists()


def _resolve_orca_machine_value(profiles_root, profile_name: str, key: str):
    """Read ``key`` from an Orca machine profile, walking the ``inherits`` chain (a child
    profile holds overrides; geometry usually lives in a shared parent)."""
    import json

    def _find(name: str):
        hits = list(profiles_root.rglob(f"{name}.json"))
        assert hits, f"machine profile {name!r} not found under {profiles_root}"
        return json.loads(hits[0].read_text(encoding="utf-8"))

    seen = set()
    name = profile_name
    while name and name not in seen:
        seen.add(name)
        data = _find(name)
        if key in data:
            return data[key]
        name = data.get("inherits")
    return None


@pytest.mark.real_tool
@pytest.mark.skipif(
    not Config.load().orca_profiles_root().exists(), reason="OrcaSlicer profiles not fetched"
)
def test_configured_build_volumes_match_the_shipped_orca_profiles():
    """KC-7 (#12): the build_volume each printer is gate-checked against must MATCH the
    printable area of the very Orca machine profile we slice with — verified against the
    shipped profile JSONs (inherits-chain resolved), so the numbers can never silently
    drift from the slicer's own truth. Closes the config VERIFY markers with data."""
    cfg = Config.load()
    root = cfg.orca_profiles_root()
    checked = 0
    for key in cfg.raw.get("printers", {}):
        p = cfg.printer(key)
        if p.build_volume is None or not p.orca_machine_profile:
            continue
        area = _resolve_orca_machine_value(root, p.orca_machine_profile, "printable_area")
        height = _resolve_orca_machine_value(root, p.orca_machine_profile, "printable_height")
        assert area is not None and height is not None, f"{key}: no geometry in profile chain"
        # printable_area is corner points like ["0x0","256x0","256x256","0x256"] — take the max.
        xs, ys = zip(*[(float(c.split("x")[0]), float(c.split("x")[1])) for c in area])
        profile_volume = (max(xs), max(ys), float(height))
        assert profile_volume == tuple(p.build_volume), (
            f"{key}: config build_volume {p.build_volume} != shipped Orca profile "
            f"{profile_volume} ({p.orca_machine_profile!r})"
        )
        checked += 1
    # The 3 reference printers + the #22 curated catalog (popular current machines) all carry a
    # build_volume gate-checked against their shipped Orca profile; this lower bound grows with the
    # catalog and guards against a regression that drops the volume verification.
    assert checked >= 25
