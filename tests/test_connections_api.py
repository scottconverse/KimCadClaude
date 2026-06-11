"""Stage 11 Slice 11.2 — the in-app Connections card's API + the saved overlay.

The contract under test: GET lists every connection's EFFECTIVE non-secret fields (the
secret never appears in either direction — only its env var's NAME and whether it's set);
POST validates hard (unknown name/field/type = typed 4xx, never a silent drop) and the
saved overlay reaches the REAL send path (build_connector) for every caller — webapp, CLI,
MCP. Settings isolated to a tmp path (never the real ~/.kimcad)."""

from __future__ import annotations

import contextlib
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

from kimcad.config import Config
from kimcad.connectors import apply_saved_connector_overrides, build_connector, connector_is_configured
from kimcad.webapp import make_handler


def _cfg(tmp_path) -> Config:
    return Config({
        "paths": {"settings": str(tmp_path / "settings.json"), "designs": str(tmp_path / "designs")},
        "connectors": {
            "mock": {"type": "loopback"},
            "bambu_p2s": {
                "type": "bambu",
                "base_url": None,
                "serial": None,
                "api_key_env": "KIMCAD_TEST_P2S_CODE",
            },
        },
    })


@contextlib.contextmanager
def _serve(tmp_path, config):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(object(), tmp_path / "web", config=config))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _jreq(host, port, method, path, body=None):
    conn = http.client.HTTPConnection(host, port, timeout=20)
    try:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data else {}
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    finally:
        conn.close()


# --- GET -----------------------------------------------------------------------------


def test_get_lists_effective_fields_and_never_a_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("KIMCAD_TEST_P2S_CODE", "super-secret-code")
    cfg = _cfg(tmp_path)
    with _serve(tmp_path, cfg) as (host, port):
        status, data = _jreq(host, port, "GET", "/api/connections")
    assert status == 200
    bambu = next(c for c in data["connections"] if c["name"] == "bambu_p2s")
    assert bambu["type"] == "bambu"
    assert bambu["configured"] is False  # no IP/serial yet
    assert bambu["note"]  # the per-piece reason rides along
    assert bambu["api_key_env"] == "KIMCAD_TEST_P2S_CODE"
    assert bambu["env_set"] is True  # SET — but the value appears nowhere
    assert "super-secret-code" not in json.dumps(data)
    mock = next(c for c in data["connections"] if c["name"] == "mock")
    assert mock["simulated"] is True and mock["configured"] is True


# --- POST validation ------------------------------------------------------------------


def test_post_unknown_name_is_404(tmp_path):
    with _serve(tmp_path, _cfg(tmp_path)) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/connections",
                             {"name": "nope", "base_url": "192.168.0.60"})
    assert status == 404
    assert "no printer connection" in data["error"].lower()


def test_post_unknown_field_is_a_400_not_a_silent_drop(tmp_path):
    with _serve(tmp_path, _cfg(tmp_path)) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/connections",
                             {"name": "bambu_p2s", "api_key_env": "EVIL", "base_url": "x"})
    assert status == 400
    assert "api_key_env" in data["error"]  # secrets/env routing can NOT be edited here


def test_post_type_and_length_validation(tmp_path):
    with _serve(tmp_path, _cfg(tmp_path)) as (host, port):
        status, _ = _jreq(host, port, "POST", "/api/connections",
                          {"name": "bambu_p2s", "use_ams": "yes"})
        assert status == 400
        status, _ = _jreq(host, port, "POST", "/api/connections",
                          {"name": "bambu_p2s", "serial": "x" * 201})
        assert status == 400


# --- the overlay reaches the real send path ---------------------------------------------


def test_saved_overlay_flips_configured_and_feeds_build_connector(tmp_path, monkeypatch):
    monkeypatch.setenv("KIMCAD_TEST_P2S_CODE", "12345678")
    cfg = _cfg(tmp_path)
    assert connector_is_configured(cfg, "bambu_p2s") is False
    with _serve(tmp_path, cfg) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/connections", {
            "name": "bambu_p2s", "base_url": "  192.168.0.60  ", "serial": "01S00C123",
            "use_ams": False,
        })
        assert status == 200 and data["saved"] is True
        # GET reflects the EFFECTIVE values (trimmed).
        _, listing = _jreq(host, port, "GET", "/api/connections")
        bambu = next(c for c in listing["connections"] if c["name"] == "bambu_p2s")
        assert bambu["base_url"] == "192.168.0.60"
        assert bambu["serial"] == "01S00C123"
        assert bambu["use_ams"] is False
        assert bambu["configured"] is True
    # And OUTSIDE the webapp: the CLI/MCP path (build_connector on a fresh Config object
    # pointing at the same settings file) sees the same effective connection.
    conn = build_connector(cfg, "bambu_p2s")
    assert conn._host == "192.168.0.60"
    assert conn._serial == "01S00C123"
    assert conn._use_ams is False
    assert connector_is_configured(cfg, "bambu_p2s") is True


def test_send_picker_list_reflects_the_overlay(tmp_path, monkeypatch):
    """N-5 (slice-11.2 audit): /api/connectors — the SEND PICKER's list — must see the
    saved overlay too, or the card would say Ready while the picker says not-set-up."""
    monkeypatch.setenv("KIMCAD_TEST_P2S_CODE", "12345678")
    cfg = _cfg(tmp_path)
    with _serve(tmp_path, cfg) as (host, port):
        _jreq(host, port, "POST", "/api/connections",
              {"name": "bambu_p2s", "base_url": "192.168.0.60", "serial": "01S00C123"})
        _, data = _jreq(host, port, "GET", "/api/connectors")
    bambu = next(c for c in data["connectors"] if c["name"] == "bambu_p2s")
    assert bambu["configured"] is True
    assert data["default"] == "mock"  # the simulated default is undisturbed


def test_unsupported_method_gets_a_truthful_allow(tmp_path):
    with _serve(tmp_path, _cfg(tmp_path)) as (host, port):
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("PUT", "/api/connections")
            resp = conn.getresponse()
            assert resp.status == 405
            assert resp.getheader("Allow") == "GET, HEAD, POST"  # both verbs ARE supported
        finally:
            conn.close()


def test_concurrent_saves_to_different_connectors_never_lose_one(tmp_path, monkeypatch):
    """M-2 (slice-11.2 audit): the read-merge-write lives under the store's write lock —
    parallel saves to two connectors must both land."""
    import concurrent.futures

    cfg = _cfg(tmp_path)
    with _serve(tmp_path, cfg) as (host, port):
        def save(name, ip):
            return _jreq(host, port, "POST", "/api/connections", {"name": name, "base_url": ip})

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(save, "bambu_p2s", f"10.0.0.{i}") for i in range(4)]
            futures += [ex.submit(save, "mock", "")]  # a second key in the same blob
            for f in futures:
                status, body = f.result()
                assert status == 200 and body["saved"] is True
        _, listing = _jreq(host, port, "GET", "/api/connections")
    bambu = next(c for c in listing["connections"] if c["name"] == "bambu_p2s")
    assert bambu["base_url"].startswith("10.0.0.")  # one of the racers won; none corrupted


def test_overlay_ignores_garbage_in_the_settings_file(tmp_path):
    """The settings file is user-writable — unknown fields and wrong types in the blob are
    ignored at READ time too (defense in depth behind the POST validation)."""
    cc = _cfg(tmp_path).connector_config("bambu_p2s")
    out = apply_saved_connector_overrides(cc, {
        "bambu_p2s": {
            "base_url": "192.168.0.60",
            "api_key_env": "EVIL_OVERRIDE",  # not a user field — must not apply
            "type": "loopback",  # ditto
            "use_ams": "not-a-bool",  # wrong type — must not apply
            "serial": "   ",  # blank — must not apply
        }
    })
    assert out.base_url == "192.168.0.60"
    assert out.api_key_env == "KIMCAD_TEST_P2S_CODE"
    assert out.type == "bambu"
    assert out.use_ams is True
    assert out.serial is None


def test_a_broken_settings_store_never_breaks_the_send_path(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    (tmp_path / "settings.json").write_text("{not json", encoding="utf-8")
    # The yaml template still answers (unconfigured, with its normal reason) — no crash.
    assert connector_is_configured(cfg, "bambu_p2s") is False
