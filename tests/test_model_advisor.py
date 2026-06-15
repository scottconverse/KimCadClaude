"""Stage 6 — the hardware/availability-aware model advisor.

The decision (:func:`recommend`) is pure, so most of this is exercised with synthetic
hardware + installed lists. The probes are I/O and best-effort; they're covered by parsing
their (mocked) outputs and by a smoke test that the real probe never raises.
"""

from __future__ import annotations

import io
import json

import pytest

from kimcad.model_advisor import (
    MODEL_CATALOG,
    HardwareProfile,
    InstalledModel,
    ModelSpec,
    _installed_match,
    _ollama_tags_url,
    probe_hardware,
    probe_installed_models,
    recommend,
)


def _hw(ram_gb=32.0, gpu=None, vram=None, cpu=8):
    return HardwareProfile(os_label="Windows 11", cpu_count=cpu, ram_gb=ram_gb,
                           gpu_name=gpu, vram_gb=vram)


def _installed(*names):
    return [InstalledModel(name=n) for n in names]


# --- fits() ----------------------------------------------------------------------

def test_fits_gates_on_ram_for_local_and_always_true_for_cloud():
    spec = next(s for s in MODEL_CATALOG if s.name == "llama3.1:8b")  # 18 GB floor
    assert spec.fits(_hw(ram_gb=32)) is True
    assert spec.fits(_hw(ram_gb=8)) is False
    assert spec.fits(_hw(ram_gb=None)) is False  # unknown RAM is never a claimed fit
    cloud = next(s for s in MODEL_CATALOG if s.location == "cloud")
    assert cloud.fits(_hw(ram_gb=2)) is True  # cloud has no local resource cost


# --- recommend(): the pure decision ----------------------------------------------

def test_recommends_the_best_installed_model_that_fits():
    # qwen2.5:7b is the top local tier (the bake-off planner). With it and gemma4 both installed,
    # the advisor picks qwen2.5:7b on measured merit — origin no longer deprioritizes a model.
    rec = recommend(_hw(ram_gb=32), _installed("qwen2.5:7b", "gemma4:e4b"))
    assert rec.primary.name == "qwen2.5:7b"
    assert rec.installed is True
    assert rec.upgrade is None  # qwen2.5:7b is the top local tier; nothing higher to pull


def test_recommends_installed_model_and_names_an_upgrade_the_box_could_run():
    # Box fits qwen2.5:7b, but only the lower-tier gemma4:e4b is installed -> use gemma now,
    # name the better qwen2.5:7b as the upgrade to pull.
    rec = recommend(_hw(ram_gb=32), _installed("gemma4:e4b"))
    assert rec.primary.name == "gemma4:e4b"
    assert rec.installed is True
    assert rec.upgrade is not None and rec.upgrade.name == "qwen2.5:7b"
    assert rec.upgrade.tier > rec.primary.tier


def test_recommends_a_pull_when_nothing_installed_fits():
    rec = recommend(_hw(ram_gb=32), installed=[])
    assert rec.installed is False
    assert rec.primary is not None and rec.primary.location == "local"
    assert "pull" in rec.reason.lower()


def test_small_box_falls_back_to_cloud():
    # Below every local floor (smallest is qwen2.5:3b @ 5 GB) -> the opt-in cloud backend.
    rec = recommend(_hw(ram_gb=4), _installed("gemma4:e4b"))
    assert rec.primary is not None and rec.primary.location == "cloud"
    assert rec.installed is False


def test_unknown_ram_falls_back_to_cloud_not_a_guessed_local():
    rec = recommend(_hw(ram_gb=None), _installed("gemma4:e4b"))
    assert rec.primary is not None and rec.primary.location == "cloud"
    assert "ram" in rec.reason.lower()


def test_surfaces_a_non_china_alternative_when_primary_is_china_origin():
    # qwen2.5:7b (Alibaba) is the pick; a non-China option is surfaced as INFO (no longer a
    # deprioritization) — the best-fitting non-China one to pull when none is installed.
    rec = recommend(_hw(ram_gb=32), _installed("qwen2.5:7b"))
    assert rec.primary.non_china is False
    assert rec.non_china_alternative is not None and rec.non_china_alternative.non_china is True
    assert rec.non_china_installed is False  # flagged as not-yet-installed


def test_no_non_china_alternative_when_primary_is_already_non_china():
    # Gemma (non-China) is the pick -> no redundant non-China escape line.
    rec = recommend(_hw(ram_gb=32), _installed("gemma4:e4b"))
    assert rec.primary.non_china is True
    assert rec.non_china_alternative is None


def test_non_china_escape_names_gemma_when_primary_is_a_china_model():
    # qwen2.5:7b is the (China-origin) primary; the informational non-China option is the
    # highest-tier non-China local that fits — gemma4:e4b (tier 5) over llama3.1:8b (tier 4) —
    # flagged not-installed here.
    rec = recommend(_hw(ram_gb=32), _installed("qwen2.5:7b"))
    assert rec.primary.non_china is False
    assert rec.non_china_alternative is not None
    assert rec.non_china_alternative.name == "gemma4:e4b"
    assert rec.non_china_installed is False


def test_cloud_is_never_primary_when_a_local_model_fits_and_is_installed():
    rec = recommend(_hw(ram_gb=32), _installed("gemma4:e4b"))
    assert rec.primary.location == "local"


def test_recommend_is_pure_same_inputs_same_output():
    hw, inst = _hw(ram_gb=16), _installed("gemma4:e4b")
    a, b = recommend(hw, inst), recommend(hw, inst)
    assert a == b


# --- installed-match + url helpers ----------------------------------------------

@pytest.mark.parametrize("installed_name,spec_name,expected", [
    ("qwen2.5-coder:1.5b", "qwen2.5-coder:1.5b", True),            # exact
    ("qwen2.5-coder:1.5b-instruct", "qwen2.5-coder:1.5b", False),  # different tag, no false match
    ("qwen2.5-coder:1.5b", "qwen2.5-coder:7b", False),             # the bug: 1.5b != 7b
    ("gemma4", "gemma4:e4b", False),                              # bare 'gemma4' (=:latest) != :e4b
    ("gemma4:e4b", "gemma4:e4b", True),
    ("gemma4", "gemma4", True),                                    # tagless spec, bare install
    ("gemma4:e4b", "gemma4", True),                                # tagless spec matches any tag
    ("llama3.1:70b", "qwen2.5-coder:1.5b", False),
])
def test_installed_match(installed_name, spec_name, expected):
    spec = ModelSpec(spec_name, "x", 1.0, min_ram_gb=4, tier=1, origin="o", non_china=True)
    assert _installed_match(spec, _installed(installed_name)) is expected


@pytest.mark.parametrize("base,expected", [
    ("http://localhost:11434/v1", "http://localhost:11434/api/tags"),
    ("http://localhost:11434/v1/", "http://localhost:11434/api/tags"),
    ("http://192.168.0.5:11434/v1", "http://192.168.0.5:11434/api/tags"),
    # ENG-601: a proxied sub-path (or any path tail) is discarded, not leaked into the URL.
    ("http://proxy/ollama/v1", "http://proxy/api/tags"),
    ("https://host:11434/v1/extra", "https://host:11434/api/tags"),
])
def test_ollama_tags_url(base, expected):
    assert _ollama_tags_url(base) == expected


# --- probe_installed_models (mocked Ollama) -------------------------------------

def test_probe_installed_models_parses_tags(monkeypatch):
    payload = {"models": [
        {"name": "gemma4:e4b", "size": 4_700_000_000},
        {"name": "qwen2.5-coder:1.5b", "size": 1_000_000_000},
    ]}

    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        "kimcad.model_advisor.urllib.request.urlopen",
        lambda url, timeout=3.0: _Resp(json.dumps(payload).encode()),
    )
    models = probe_installed_models("http://localhost:11434/v1")
    names = {m.name for m in models}
    assert names == {"gemma4:e4b", "qwen2.5-coder:1.5b"}
    assert any(abs((m.size_gb or 0) - 4.7) < 0.01 for m in models)


def test_probe_installed_models_returns_empty_when_ollama_is_down(monkeypatch):
    def _boom(url, timeout=3.0):
        raise OSError("connection refused")

    monkeypatch.setattr("kimcad.model_advisor.urllib.request.urlopen", _boom)
    assert probe_installed_models("http://localhost:11434/v1") == []


# TEST-004: a 200-OK-but-garbage body (Ollama drift / a proxy error page) must never raise.
@pytest.mark.parametrize("body", [
    b"[1, 2, 3]",                     # valid JSON, but a list not a dict
    b'{"models": [{"size": 5}]}',     # a model entry with no name -> skipped
    b"<html>502 Bad Gateway</html>",  # non-JSON 200 body
    b'{"no_models_key": true}',       # dict without "models"
])
def test_probe_installed_models_tolerates_a_malformed_body(monkeypatch, body):
    class _Resp(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(
        "kimcad.model_advisor.urllib.request.urlopen",
        lambda url, timeout=3.0: _Resp(body),
    )
    # Never raises; a malformed/garbage body yields [] (the nameless entry is skipped).
    assert probe_installed_models("http://localhost:11434/v1") == []


# --- friendly_label (UX-007) ----------------------------------------------------

@pytest.mark.parametrize("installed,expected", [
    ("gemma4:e4b", "Gemma E4B"),
    ("gemma4:e4b-it-q4_K_M", "Gemma E4B"),                       # quant/variant suffix
    ("qwen2.5:7b", "Qwen2.5 7B"),
    ("qwen2.5:3b", "Qwen2.5 3B"),
    ("novaforgeai/deepseek-coder:6.7b-optimized", None),         # not a catalog family
    ("totally-unknown:1b", None),
])
def test_friendly_label(installed, expected):
    from kimcad.model_advisor import friendly_label
    assert friendly_label(installed) == expected


# --- TEST-006: degenerate / GPU-present branches --------------------------------

def test_recommend_returns_no_primary_when_nothing_fits_and_no_cloud():
    # A catalog with only an un-fitting local model and no cloud entry -> primary is None.
    spec = ModelSpec("huge:999b", "Huge", 999.0, min_ram_gb=999, tier=9, origin="x", non_china=True)
    rec = recommend(_hw(ram_gb=8), installed=[], catalog=(spec,))
    assert rec.primary is None


def test_fits_and_summary_with_a_discrete_gpu_present():
    spec = next(s for s in MODEL_CATALOG if s.name == "llama3.1:8b")  # 18 GB floor
    hw = HardwareProfile(os_label="Linux", cpu_count=16, ram_gb=None, gpu_name="RTX 4090", vram_gb=24.0)
    # RAM gates the fit; unknown RAM is never a claimed fit even with a big discrete GPU.
    assert spec.fits(hw) is False
    summary = hw.summary()
    assert "RTX 4090" in summary  # the GPU branch renders
    assert summary.isascii()      # and stays cp1252-safe


# --- TEST-007: advisor printed strings are cp1252-safe --------------------------

def test_advisor_printed_strings_are_console_safe():
    hw = _hw(ram_gb=32)
    rec = recommend(hw, _installed("gemma4:e4b"))
    for s in (hw.summary(), rec.reason):
        s.encode("cp1252")   # must not raise on a Windows cp1252 console
        assert s.isascii()


# --- probe_hardware smoke (real machine, must never raise) -----------------------

def test_probe_hardware_never_raises_and_reports_os():
    hw = probe_hardware()
    assert isinstance(hw, HardwareProfile)
    assert hw.os_label  # platform always gives something
    assert hw.cpu_count is None or hw.cpu_count >= 1
    assert hw.summary()  # renders without error regardless of which fields probed
