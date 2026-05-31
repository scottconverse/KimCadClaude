"""Tests for the printer MCP server (Stage 2, Slice 5)."""

import json
import zipfile
from pathlib import Path

from kimcad.config import Config
from kimcad.mcp_server import PROTOCOL_VERSION, PrinterMCPServer


def _server() -> PrinterMCPServer:
    return PrinterMCPServer(Config.load())  # default config has the "mock" loopback connector


def _write_gcode_3mf(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Metadata/plate_1.gcode", "G28\nG1 X10 Y10 E1\nG1 X20 Y20 E2\n")
    return path


def _call(server: PrinterMCPServer, name: str, arguments: dict) -> dict:
    resp = server.handle(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": arguments}}
    )
    return resp["result"]


def _text(result: dict) -> str:
    return result["content"][0]["text"]


# --- protocol -----------------------------------------------------------------


def test_initialize_returns_server_info():
    resp = _server().handle({"jsonrpc": "2.0", "id": 0, "method": "initialize"})
    assert resp["result"]["protocolVersion"] == PROTOCOL_VERSION
    assert resp["result"]["serverInfo"]["name"] == "kimcad-printer"
    assert "tools" in resp["result"]["capabilities"]


def test_initialized_notification_has_no_response():
    assert _server().handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_ping():
    assert _server().handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}


def test_tools_list_advertises_the_four_tools():
    resp = _server().handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"list_connectors", "printer_status", "printer_capabilities", "send_print"}
    send = next(t for t in resp["result"]["tools"] if t["name"] == "send_print")
    assert set(send["inputSchema"]["required"]) == {"connector", "gcode_path", "confirm"}


def test_unknown_method_is_jsonrpc_error():
    resp = _server().handle({"jsonrpc": "2.0", "id": 4, "method": "frobnicate"})
    assert resp["error"]["code"] == -32601


# --- tools --------------------------------------------------------------------


def test_list_connectors_tool():
    res = _call(_server(), "list_connectors", {})
    assert res["isError"] is False
    assert "mock" in json.loads(_text(res))["connectors"]


def test_printer_status_tool():
    res = _call(_server(), "printer_status", {"connector": "mock"})
    data = json.loads(_text(res))
    assert data["online"] is True and data["state"] == "operational"


def test_printer_capabilities_tool():
    res = _call(_server(), "printer_capabilities", {"connector": "mock"})
    data = json.loads(_text(res))
    assert data["nozzle_diameter_mm"] == 0.4 and "pla" in data["materials"]


def test_send_print_tool_with_confirm(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    res = _call(_server(), "send_print", {"connector": "mock", "gcode_path": str(g), "confirm": True})
    assert res["isError"] is False
    data = json.loads(_text(res))
    assert data["sent"] is True and data["job"]["job_id"]


def test_send_print_tool_refuses_without_confirm(tmp_path):
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    res = _call(
        _server(), "send_print", {"connector": "mock", "gcode_path": str(g), "confirm": False}
    )
    assert res["isError"] is True
    assert "confirmation" in _text(res)


def test_send_print_truthy_string_confirm_is_still_refused(tmp_path):
    # A stringy/truthy-but-not-True confirm must NOT defeat the gate (no bool() coercion).
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    for sneaky in ("no", "false", "yes", "1"):
        res = _call(
            _server(), "send_print",
            {"connector": "mock", "gcode_path": str(g), "confirm": sneaky},
        )
        assert res["isError"] is True, sneaky
        assert "confirmation" in _text(res), sneaky


def test_send_print_tool_refuses_non_slice(tmp_path):
    bad = tmp_path / "bad.gcode.3mf"
    bad.write_bytes(b"not a slice")
    res = _call(
        _server(), "send_print", {"connector": "mock", "gcode_path": str(bad), "confirm": True}
    )
    assert res["isError"] is True and "printable slice" in _text(res)


def test_tool_unknown_connector_is_tool_error():
    res = _call(_server(), "printer_status", {"connector": "ghost"})
    assert res["isError"] is True and "unknown connector" in _text(res)


def test_tool_missing_argument_is_tool_error():
    res = _call(_server(), "printer_status", {})
    assert res["isError"] is True and "missing required argument" in _text(res)


def test_unknown_tool_is_tool_error():
    res = _call(_server(), "no_such_tool", {})
    assert res["isError"] is True and "unknown tool" in _text(res)


def test_non_dict_params_is_invalid_params_not_a_crash():
    # A malformed tools/call (non-object params, or missing tool name) must be a clean
    # JSON-RPC -32602 error, never an unhandled crash.
    s = _server()
    r1 = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": [1, 2, 3]})
    assert r1["error"]["code"] == -32602
    r2 = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {}})
    assert r2["error"]["code"] == -32602  # missing tool name


def test_non_object_request_is_invalid_request(tmp_path):
    # QA-002: a valid JSON value that isn't a Request object (a top-level array, a scalar)
    # is -32600 Invalid Request, not -32601 Method-not-found.
    s = _server()
    for bad in ([1, 2, 3], "ping", 5):
        resp = s.handle(bad)
        assert resp["error"]["code"] == -32600, bad


def test_send_print_non_true_confirm_values_are_all_refused(tmp_path):
    # ENG-209: cover the numeric and boolean-ish values, not just strings. NONE may send.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    for sneaky in (1, 1.0, 0, False, None, "true", "no", [True]):
        res = _call(
            _server(), "send_print",
            {"connector": "mock", "gcode_path": str(g), "confirm": sneaky},
        )
        assert res["isError"] is True, sneaky
        assert "confirmation" in _text(res), sneaky


def test_send_print_reports_simulated_for_the_mock(tmp_path):
    # UX-001/QA-003: a successful send to a no-hardware connector is flagged simulated so an
    # agent doesn't treat it as a real print.
    g = _write_gcode_3mf(tmp_path / "p.gcode.3mf")
    res = _call(_server(), "send_print", {"connector": "mock", "gcode_path": str(g), "confirm": True})
    assert res["isError"] is False
    data = json.loads(_text(res))
    assert data["sent"] is True and data["simulated"] is True
