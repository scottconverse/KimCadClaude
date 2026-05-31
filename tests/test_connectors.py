"""Tests for the connector factory (Stage 2, Slice 4)."""

import pytest

from kimcad.config import Config
from kimcad.connectors import build_connector
from kimcad.octoprint_connector import OctoPrintConnector
from kimcad.printer_connector import ConnectorError, LoopbackConnector


def _config(connectors: dict) -> Config:
    return Config(
        {
            "binaries": {"openscad": "x", "orcaslicer": "y"},
            "defaults": {"printer": "p", "material": "pla"},
            "printers": {"p": {"name": "P"}},
            "materials": {"pla": {"name": "PLA", "nozzle_temp": 210, "bed_temp": 55,
                                  "wall_multiplier": 2.0, "shrinkage": 0.002}},
            "connectors": connectors,
            "limits": {},
        }
    )


def test_default_config_has_mock_and_octoprint_connectors():
    cfg = Config.load()
    assert "mock" in cfg.connectors()
    assert "octoprint" in cfg.connectors()


def test_build_loopback_connector():
    c = build_connector(_config({"mock": {"type": "loopback"}}), "mock")
    assert isinstance(c, LoopbackConnector) and c.name == "mock"


def test_build_octoprint_connector_with_key(monkeypatch):
    monkeypatch.setenv("OCTO_KEY", "secret")
    cfg = _config(
        {"octo": {"type": "octoprint", "base_url": "http://host:5000", "api_key_env": "OCTO_KEY"}}
    )
    c = build_connector(cfg, "octo")
    assert isinstance(c, OctoPrintConnector) and c.name == "octo"


def test_build_octoprint_without_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("OCTO_KEY", raising=False)
    cfg = _config(
        {"octo": {"type": "octoprint", "base_url": "http://host:5000", "api_key_env": "OCTO_KEY"}}
    )
    with pytest.raises(ConnectorError, match="OCTO_KEY"):
        build_connector(cfg, "octo")


def test_build_octoprint_without_base_url_errors():
    cfg = _config({"octo": {"type": "octoprint", "api_key_env": "K"}})
    with pytest.raises(ConnectorError, match="base_url"):
        build_connector(cfg, "octo")


def test_unknown_connector_name_errors():
    with pytest.raises(ConnectorError, match="unknown connector"):
        build_connector(_config({"mock": {"type": "loopback"}}), "nope")


def test_unknown_connector_type_errors():
    with pytest.raises(ConnectorError, match="unknown type"):
        build_connector(_config({"weird": {"type": "telepathy"}}), "weird")
