"""Tests for the connector factory (Stage 2, Slice 4) + shared connector helpers (Stage 3)."""

import io
import urllib.error

import pytest

from kimcad.config import Config
from kimcad.connectors import build_connector, connector_is_simulated
from kimcad.moonraker_connector import MoonrakerConnector
from kimcad.octoprint_connector import OctoPrintConnector
from kimcad.printer_connector import (
    AuthError,
    ConnectorError,
    LoopbackConnector,
    auth_error_if_upload_rejected,
    decode_json,
    read_error_body,
)
from kimcad.prusalink_connector import PrusaLinkConnector


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


def test_build_moonraker_connector_unauthenticated():
    # Moonraker often needs no key (trusted LAN) -> a missing key is NOT an error.
    cfg = _config({"klip": {"type": "moonraker", "base_url": "http://host:7125"}})
    c = build_connector(cfg, "klip")
    assert isinstance(c, MoonrakerConnector) and c.name == "klip"


def test_build_moonraker_with_optional_key(monkeypatch):
    monkeypatch.setenv("MOON_KEY", "secret")
    cfg = _config(
        {"klip": {"type": "moonraker", "base_url": "http://host:7125", "api_key_env": "MOON_KEY"}}
    )
    c = build_connector(cfg, "klip")
    assert isinstance(c, MoonrakerConnector)


def test_build_moonraker_without_base_url_errors():
    cfg = _config({"klip": {"type": "moonraker"}})
    with pytest.raises(ConnectorError, match="base_url"):
        build_connector(cfg, "klip")


def test_moonraker_is_not_simulated():
    cfg = _config({"klip": {"type": "moonraker", "base_url": "http://host:7125"}})
    assert connector_is_simulated(cfg.connector_config("klip")) is False


def test_build_prusalink_connector_with_key(monkeypatch):
    monkeypatch.setenv("PRUSA_KEY", "secret")
    cfg = _config(
        {"prusa": {"type": "prusalink", "base_url": "http://host", "api_key_env": "PRUSA_KEY"}}
    )
    c = build_connector(cfg, "prusa")
    assert isinstance(c, PrusaLinkConnector) and c.name == "prusa"


def test_build_prusalink_without_key_is_a_clear_error(monkeypatch):
    monkeypatch.delenv("PRUSA_KEY", raising=False)
    cfg = _config(
        {"prusa": {"type": "prusalink", "base_url": "http://host", "api_key_env": "PRUSA_KEY"}}
    )
    with pytest.raises(ConnectorError, match="PRUSA_KEY"):
        build_connector(cfg, "prusa")


def test_build_prusalink_without_base_url_errors():
    cfg = _config({"prusa": {"type": "prusalink", "api_key_env": "K"}})
    with pytest.raises(ConnectorError, match="base_url"):
        build_connector(cfg, "prusa")


def test_prusalink_is_not_simulated():
    cfg = _config({"prusa": {"type": "prusalink", "base_url": "http://host"}})
    assert connector_is_simulated(cfg.connector_config("prusa")) is False


def test_build_prusalink_uses_configured_storage(monkeypatch):
    monkeypatch.setenv("PRUSA_KEY", "secret")
    cfg = _config(
        {"prusa": {"type": "prusalink", "base_url": "http://host", "api_key_env": "PRUSA_KEY",
                   "storage": "local"}}
    )
    c = build_connector(cfg, "prusa")
    assert c._storage == "local"


def test_unknown_connector_name_errors():
    with pytest.raises(ConnectorError, match="unknown connector"):
        build_connector(_config({"mock": {"type": "loopback"}}), "nope")


def test_unknown_connector_type_errors():
    with pytest.raises(ConnectorError, match="unknown type"):
        build_connector(_config({"weird": {"type": "telepathy"}}), "weird")


# --- decode_json: a non-JSON HTTP-200 body raises a clean ConnectorError (QA-001) ---------


def test_decode_json_parses_object():
    assert decode_json(b'{"a": 1}', name="x") == {"a": 1}


def test_decode_json_empty_is_empty_dict():
    assert decode_json(b"", name="x") == {}
    assert decode_json(None, name="x") == {}


def test_decode_json_non_object_is_empty_dict():
    # A JSON list/scalar is coerced to {} so downstream `.get` is safe (a printer that answers
    # 200 with `[]` must not become an AttributeError later).
    assert decode_json(b"[1, 2, 3]", name="x") == {}
    assert decode_json(b"42", name="x") == {}


def test_decode_json_garbage_raises_clean_connector_error():
    # A captive portal / wrong device answering 200 with HTML must surface as a typed, clean
    # ConnectorError — never a raw JSONDecodeError traceback.
    with pytest.raises(ConnectorError) as exc:
        decode_json(b"<html>not json</html>", name="my-printer")
    assert exc.value.reason == "bad_response"
    assert "my-printer" in exc.value.user_message
    assert "unexpected response" in exc.value.user_message


# --- auth_error_if_upload_rejected: a mid-upload reset on a bad key -> AuthError (ENG-001) --
#
# A server that rejects auth on an upload sends 401 and closes before draining the body; on a
# large body the client's write fails first with a connection RESET (a ConnectionError, not an
# HTTPError), which would otherwise be mislabeled "offline". These cover the disambiguation
# logic deterministically, without depending on OS socket-buffer timing.


def _request_raising(exc):
    def _request(method, path, **kw):
        raise exc

    return _request


def _request_returning(status):
    def _request(method, path, **kw):
        return status, b""

    return _request


def _http_error(code):
    return urllib.error.HTTPError("http://x", code, "rejected", {}, None)


@pytest.mark.parametrize("code", [401, 403])
def test_upload_reset_with_rejected_probe_is_auth(code):
    err = auth_error_if_upload_rejected(
        ConnectionResetError("reset"),
        request=_request_raising(_http_error(code)),
        api_key="k",
        name="p",
        probe_path="/probe",
    )
    assert isinstance(err, AuthError) and err.reason == "auth"


def test_upload_reset_with_ok_probe_is_not_auth():
    # The re-probe succeeds -> the reset wasn't auth; fall through to offline.
    err = auth_error_if_upload_rejected(
        ConnectionAbortedError("reset"),
        request=_request_returning(200),
        api_key="k",
        name="p",
        probe_path="/probe",
    )
    assert err is None


def test_upload_reset_with_unreachable_probe_is_not_auth():
    err = auth_error_if_upload_rejected(
        ConnectionResetError("reset"),
        request=_request_raising(urllib.error.URLError("down")),
        api_key="k",
        name="p",
        probe_path="/probe",
    )
    assert err is None


def test_non_connection_oserror_is_not_probed():
    # A connect-time URLError (printer off) is NOT the ambiguous mid-write case -> stays offline,
    # even though a probe would 401. Only a raw ConnectionError triggers the re-probe.
    err = auth_error_if_upload_rejected(
        urllib.error.URLError("refused"),
        request=_request_raising(_http_error(401)),
        api_key="k",
        name="p",
        probe_path="/probe",
    )
    assert err is None


def test_no_api_key_is_not_probed():
    # No configured key -> a reset can't be an auth rejection -> stays offline.
    err = auth_error_if_upload_rejected(
        ConnectionResetError("reset"),
        request=_request_raising(_http_error(401)),
        api_key=None,
        name="p",
        probe_path="/probe",
    )
    assert err is None


# --- read_error_body: bounded, whitespace-collapsed, never raises (TEST-002) ----------------


class _FakeErr:
    def __init__(self, data):
        self._d = io.BytesIO(data)

    def read(self, n):
        return self._d.read(n)


def test_read_error_body_collapses_whitespace():
    assert read_error_body(_FakeErr(b"  hello   world\n  ")) == "hello world"


def test_read_error_body_is_capped():
    assert len(read_error_body(_FakeErr(b"x" * 1000), cap=10)) == 10


def test_read_error_body_never_raises_on_a_failing_read():
    class _Boom:
        def read(self, n):
            raise OSError("boom")

    assert read_error_body(_Boom()) == ""
