"""KimCad printer MCP server (ROADMAP Stage 2 — "MCP as the first connector").

Exposes send-to-printer as MCP tools so an agent (Claude, etc.) can list the configured
printer connections, query a printer's status/capabilities, and — only with an explicit
``confirm: true`` — send an already-sliced G-code 3MF to a printer.

This is a minimal, dependency-free MCP server: newline-delimited JSON-RPC 2.0 over stdio,
implementing just ``initialize`` / ``tools/list`` / ``tools/call`` / ``ping``. The request
handling is a pure method (:meth:`PrinterMCPServer.handle`) so the whole protocol is
unit-tested with no subprocess and no transport. Run it as an MCP server with
``python -m kimcad.mcp_server`` (point your MCP client's command at that).

Safety: the ``send_print`` tool refuses unless ``confirm is True`` and the file proves out
as a real motion-bearing slice — the same gate every connector enforces. No real hardware
is driven until Kim's beta (Stage 10); "mock" is a built-in loopback.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from kimcad.connectors import build_connector
from kimcad.printer_connector import ConnectorError

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kimcad-printer"

_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_connectors",
        "description": "List the configured printer connections KimCad can send a job to.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "printer_status",
        "description": "Get a printer connection's current status (online, state, temps).",
        "inputSchema": {
            "type": "object",
            "properties": {"connector": {"type": "string", "description": "connector name"}},
            "required": ["connector"],
        },
    },
    {
        "name": "printer_capabilities",
        "description": "Get a printer's reported capabilities (build volume, nozzle, materials).",
        "inputSchema": {
            "type": "object",
            "properties": {"connector": {"type": "string", "description": "connector name"}},
            "required": ["connector"],
        },
    },
    {
        "name": "send_print",
        "description": (
            "Send an already-sliced G-code 3MF to a printer connection and start it. "
            "Requires confirm=true (explicit per-send confirmation); refuses any file that "
            "isn't a proven, motion-bearing slice. Returns the ENQUEUED job (and "
            "simulated=true when the connection is a no-hardware simulation, e.g. 'mock'); "
            "poll printer_status / a follow-up for progress."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "connector": {"type": "string", "description": "connector name"},
                "gcode_path": {"type": "string", "description": "path to a *.gcode.3mf"},
                "confirm": {"type": "boolean", "description": "must be true to send"},
            },
            "required": ["connector", "gcode_path", "confirm"],
        },
    },
]


def _status_dict(s: Any) -> dict[str, Any]:
    return {
        "online": s.online,
        "state": s.state.value,
        "detail": s.detail,
        "nozzle_temp_c": s.nozzle_temp_c,
        "bed_temp_c": s.bed_temp_c,
    }


def _caps_dict(c: Any) -> dict[str, Any]:
    return {
        "name": c.name,
        "build_volume_mm": list(c.build_volume_mm) if c.build_volume_mm else None,
        "nozzle_diameter_mm": c.nozzle_diameter_mm,
        # None = not reported (e.g. OctoPrint), distinct from [] = reports none.
        "materials": list(c.materials) if c.materials is not None else None,
    }


def _job_dict(j: Any) -> dict[str, Any]:
    return {"job_id": j.job_id, "state": j.state.value, "progress": j.progress, "detail": j.detail}


class PrinterMCPServer:
    """Pure request handler for the printer MCP server. ``config`` is any object exposing
    ``connectors()`` / ``connector_config()`` (a :class:`kimcad.config.Config`)."""

    def __init__(self, config: Any):
        self._config = config

    # --- JSON-RPC framing ---------------------------------------------------
    @staticmethod
    def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC request. Returns the response, or None for a notification."""
        if not isinstance(request, dict):
            # A valid JSON value that isn't a Request object (e.g. a top-level array) is
            # Invalid Request per JSON-RPC 2.0 — not Method-not-found (QA-002).
            return self._error(None, -32600, "invalid request: expected a JSON object")
        method = request.get("method")
        req_id = request.get("id")
        if method == "initialize":
            return self._result(
                req_id,
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
                },
            )
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return self._result(req_id, {})
        if method == "tools/list":
            return self._result(req_id, {"tools": _TOOLS})
        if method == "tools/call":
            return self._call_tool(req_id, request.get("params") or {})
        return self._error(req_id, -32601, f"method not found: {method}")

    def _call_tool(self, req_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return self._error(req_id, -32602, "tools/call params must be an object")
        name = params.get("name")
        if not name:
            return self._error(req_id, -32602, "tools/call requires a tool name")
        args = params.get("arguments")
        if not isinstance(args, dict):
            args = {}
        try:
            text = self._dispatch(name, args)
        except ConnectorError as e:
            return self._result(req_id, self._tool_text(str(e), is_error=True))
        except _ToolInputError as e:
            return self._result(req_id, self._tool_text(str(e), is_error=True))
        except Exception as e:  # never crash the server thread on a tool bug
            return self._result(
                req_id, self._tool_text(f"{type(e).__name__}: {e}", is_error=True)
            )
        return self._result(req_id, self._tool_text(text))

    def _dispatch(self, name: str | None, args: dict[str, Any]) -> str:
        if name == "list_connectors":
            return json.dumps({"connectors": list(self._config.connectors())})
        if name == "printer_status":
            connector = build_connector(self._config, _require(args, "connector"))
            return json.dumps(_status_dict(connector.status()))
        if name == "printer_capabilities":
            connector = build_connector(self._config, _require(args, "connector"))
            return json.dumps(_caps_dict(connector.capabilities()))
        if name == "send_print":
            connector = build_connector(self._config, _require(args, "connector"))
            # Pass the raw confirm value through — the connector's `confirm is not True`
            # gate decides. (Do NOT bool()-coerce here: bool("no") is True, which would
            # let a stringy/truthy non-true value defeat the explicit-confirmation gate.)
            job = connector.send(Path(_require(args, "gcode_path")), confirm=args.get("confirm"))
            return json.dumps(
                {
                    "sent": True,
                    "simulated": not getattr(connector, "drives_hardware", True),
                    "job": _job_dict(job),
                }
            )
        raise _ToolInputError(f"unknown tool: {name}")


class _ToolInputError(Exception):
    """A tool was called with missing/invalid arguments."""


def _require(args: dict[str, Any], key: str) -> Any:
    if key not in args or args[key] in (None, ""):
        raise _ToolInputError(f"missing required argument: {key}")
    return args[key]


def main() -> None:  # pragma: no cover - the stdio loop is exercised via handle() in tests
    from kimcad.config import Config

    server = PrinterMCPServer(Config.load())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (ValueError, TypeError):
            continue
        try:
            # handle() itself maps a non-object request to -32600; pass it straight through.
            response = server.handle(request)
        except Exception:  # a handler bug must not take down the whole stdio server
            response = None
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    main()
