"""Protocol tests for the KimCad universal connector (kimcad.connector).

The connector's request handling is a pure method, so the whole JSON-RPC surface is exercised
with injected fakes — no real pipeline, no OpenSCAD, no API key, no printer. Mirrors the
testing approach of test_mcp_server.

Runnable two ways:
  * ``pytest tests/test_connector.py``  (the gate run, Python 3.13)
  * ``python tests/test_connector.py``  (standalone smoke; loads the module by path so it
    needs none of KimCad's heavy dependencies)
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_CONNECTOR_PATH = Path(__file__).resolve().parents[1] / "src" / "kimcad" / "connector.py"


def _load_connector_module():
    spec = importlib.util.spec_from_file_location("kimcad_connector_under_test", _CONNECTOR_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


CONN = _load_connector_module()


class _FakePrinterServer:
    """Stands in for PrinterMCPServer: speaks the same tools/list + tools/call protocol."""

    TOOLS = [
        {"name": "list_connectors", "description": "list printers", "inputSchema": {"type": "object", "properties": {}}},
        {"name": "send_print", "description": "send a job", "inputSchema": {"type": "object", "properties": {}}},
    ]

    def handle(self, request):
        method = request.get("method")
        rid = request.get("id")
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": rid, "result": {"tools": self.TOOLS}}
        if method == "tools/call":
            name = (request.get("params") or {}).get("name")
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"printer:{name}"}], "isError": False,
            }}
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "nope"}}


class _FakePipeline:
    def __init__(self):
        self.calls = []

    def run(self, prompt, out_dir, **kw):
        self.calls.append((prompt, out_dir, kw))
        gate = SimpleNamespace(status="pass", messages=["fits build volume"])
        readiness = SimpleNamespace(score=88, verdict="Ready to print")
        report = SimpleNamespace(readiness=readiness)
        status = SimpleNamespace(value="completed")
        return SimpleNamespace(
            status=status, prompt=prompt, scad="cube([10,10,10]);", clarification=None,
            error=None, mesh_path=out_dir / "part.3mf", backend="openscad",
            render_attempts=1, gate=gate, report=report, template=None,
        )


class _MemLibraryStore:
    def __init__(self):
        self._rows = []

    def list(self):
        return list(self._rows)

    def add(self, name, path):
        self._rows = [r for r in self._rows if r["name"] != name] + [{"name": name, "path": str(path)}]

    def remove(self, name):
        before = len(self._rows)
        self._rows = [r for r in self._rows if r["name"] != name]
        return len(self._rows) != before


def _make_connector():
    pipeline = _FakePipeline()
    conn = CONN.KimCadConnector(
        config=SimpleNamespace(),
        pipeline_factory=lambda printer, material, backend: pipeline,
        printer_server=_FakePrinterServer(),
        library_store=_MemLibraryStore(),
    )
    return conn, pipeline


def _call(conn, name, arguments=None, rid=1):
    return conn.handle({
        "jsonrpc": "2.0", "id": rid, "method": "tools/call",
        "params": {"name": name, "arguments": arguments or {}},
    })


def test_initialize_identifies_connector():
    conn, _ = _make_connector()
    resp = conn.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
    assert resp["result"]["serverInfo"]["name"] == "kimcad-connect"
    assert resp["result"]["protocolVersion"] == CONN.PROTOCOL_VERSION


def test_tools_list_is_superset_of_printer_tools():
    conn, _ = _make_connector()
    resp = conn.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    # connector-native
    assert {"design", "list_libraries", "add_library", "remove_library"} <= names
    # composed printer tools
    assert {"list_connectors", "send_print"} <= names


def test_design_runs_pipeline_and_serializes_result():
    conn, pipeline = _make_connector()
    resp = _call(conn, "design", {"prompt": "a 10mm cube"})
    assert resp["result"]["isError"] is False
    import json
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["status"] == "completed"
    assert payload["scad"] == "cube([10,10,10]);"
    assert payload["gate"]["status"] == "pass"
    assert payload["readiness"]["score"] == 88
    assert payload["mesh_path"].endswith("part.3mf")
    # the prompt actually reached the pipeline
    assert pipeline.calls and pipeline.calls[0][0] == "a 10mm cube"


def test_design_requires_prompt():
    conn, _ = _make_connector()
    resp = _call(conn, "design", {})
    assert resp["result"]["isError"] is True
    assert "prompt" in resp["result"]["content"][0]["text"]


def test_library_chooser_roundtrip():
    conn, _ = _make_connector()
    import json
    add = _call(conn, "add_library", {"name": "NopSCADlib", "path": "/home/kim/lib/NopSCADlib"})
    assert json.loads(add["result"]["content"][0]["text"])["added"] is True
    listed = json.loads(_call(conn, "list_libraries")["result"]["content"][0]["text"])
    assert listed["external"] == [{"name": "NopSCADlib", "path": "/home/kim/lib/NopSCADlib"}]
    removed = json.loads(_call(conn, "remove_library", {"name": "NopSCADlib"})["result"]["content"][0]["text"])
    assert removed["removed"] is True
    assert json.loads(_call(conn, "list_libraries")["result"]["content"][0]["text"])["external"] == []


def test_printer_tool_is_delegated():
    conn, _ = _make_connector()
    resp = _call(conn, "send_print", {"connector": "mock", "gcode_path": "x.gcode.3mf", "confirm": True})
    assert resp["result"]["content"][0]["text"] == "printer:send_print"


def test_unknown_tool_is_error_not_crash():
    conn, _ = _make_connector()
    resp = _call(conn, "no_such_tool")
    assert resp["result"]["isError"] is True


def test_unknown_method():
    conn, _ = _make_connector()
    resp = conn.handle({"jsonrpc": "2.0", "id": 9, "method": "frobnicate"})
    assert resp["error"]["code"] == -32601


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
        passed += 1
    print(f"\n{passed}/{len(fns)} connector protocol tests passed")
