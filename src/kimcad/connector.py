"""KimCad Connector — the universal glue between CAD front-ends and KimCad's pipeline.

Think "OpenRouter, but for OpenSCAD manufacturing." One JSON-RPC/MCP surface that any
front-end can drive — OpenSCAD Studio, Claude Code, a CLI, a future web UI — with KimCad's
full text->print pipeline behind it, plus three *bring-your-own* resource planes:

  - **AI engines**   — bring your own key/endpoint (already handled by ``config.llm``).
  - **printers**     — bring your own connection (delegated to :class:`PrinterMCPServer`).
  - **SCAD libraries** — bring your own install (the *library chooser*). This is what lets a
    user plug in even GPLv3 libraries (NopSCADlib, dotSCAD) the same way they plug in an API
    key: KimCad never redistributes them, the user points at their own install, so there is
    no GPL-2.0 bundling conflict.

Transport mirrors :mod:`kimcad.mcp_server` exactly — newline-delimited JSON-RPC 2.0 over
stdio, with a pure :meth:`KimCadConnector.handle` so the whole protocol is unit-tested with
no subprocess and no transport. The printer tools are **composed** from the existing,
gate-clean :class:`PrinterMCPServer` (not duplicated), so this connector is a strict superset
of the printer server.

Everything heavy (the pipeline, config, providers) is lazy-imported inside methods, so the
protocol layer imports and tests without OpenSCAD, an API key, or the full dependency set.

Run it as an MCP server with ``python -m kimcad.connector`` (point your MCP client there).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Protocol

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "kimcad-connect"


class _ToolInputError(Exception):
    """A tool was called with missing/invalid arguments."""


def _require(args: dict[str, Any], key: str) -> Any:
    if key not in args or args[key] in (None, ""):
        raise _ToolInputError(f"missing required argument: {key}")
    return args[key]


# --- the library chooser (bring-your-own SCAD library) ----------------------


class LibraryStore(Protocol):
    """Persistence for user-registered external SCAD library roots."""

    def list(self) -> list[dict[str, str]]: ...
    def add(self, name: str, path: str) -> None: ...
    def remove(self, name: str) -> bool: ...


class FileLibraryStore:
    """A tiny JSON-file-backed registry of external library roots.

    v0 owns the *registry* (what the user has plugged in). Actually admitting those roots to
    the renderer — extending ``openscad_runner``'s ``library/`` allowlist and ``OPENSCADPATH``
    — is the next slice; this keeps the security-boundary change isolated and reviewable
    rather than smuggled in with the connector.
    """

    def __init__(self, path: Path):
        self._path = Path(path)

    def _read(self) -> list[dict[str, str]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, rows: list[dict[str, str]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def list(self) -> list[dict[str, str]]:
        return self._read()

    def add(self, name: str, path: str) -> None:
        rows = [r for r in self._read() if r.get("name") != name]
        rows.append({"name": name, "path": str(path)})
        self._write(rows)

    def remove(self, name: str) -> bool:
        rows = self._read()
        kept = [r for r in rows if r.get("name") != name]
        self._write(kept)
        return len(kept) != len(rows)


# --- serialization of a PipelineResult into a transport-safe dict ------------


def design_result_dict(res: Any) -> dict[str, Any]:
    """Serialize a :class:`~kimcad.pipeline.PipelineResult` into JSON-safe primitives.

    Defensive (``getattr``) on purpose: the connector should not break when the pipeline
    result grows new fields, and it stays decoupled from the exact shape of GateResult /
    PrintReport, which the front-end only needs summarized.
    """
    def _val(obj: Any, *attrs: str, default: Any = None) -> Any:
        for a in attrs:
            obj = getattr(obj, a, None)
            if obj is None:
                return default
        return obj

    status = _val(res, "status")
    gate = getattr(res, "gate", None)
    report = getattr(res, "report", None)
    template = getattr(res, "template", None)
    mesh_path = getattr(res, "mesh_path", None)

    return {
        "status": getattr(status, "value", status),
        "prompt": getattr(res, "prompt", None),
        "scad": getattr(res, "scad", None),
        "clarification": getattr(res, "clarification", None),
        "error": getattr(res, "error", None),
        "mesh_path": str(mesh_path) if mesh_path else None,
        "backend": getattr(res, "backend", None),
        "render_attempts": getattr(res, "render_attempts", None),
        "gate": None if gate is None else {
            "status": str(getattr(gate, "status", "")),
            "messages": list(getattr(gate, "messages", []) or []),
        },
        "readiness": None if report is None else {
            "score": _val(report, "readiness", "score"),
            "verdict": _val(report, "readiness", "verdict"),
        },
        "template": None if template is None else getattr(template, "name", str(template)),
    }


# --- the connector ----------------------------------------------------------

PipelineFactory = Callable[[str | None, str | None, str | None], Any]


class KimCadConnector:
    """Pure JSON-RPC request handler for the universal connector.

    Dependency-injected so the protocol is fully testable without real models or OpenSCAD:

    * ``config`` — a :class:`kimcad.config.Config` (or any object the factory/printer accept).
    * ``pipeline_factory(printer, material, backend) -> Pipeline`` — defaults to the same
      construction the CLI uses.
    * ``printer_server`` — a :class:`PrinterMCPServer` (or compatible) whose tools are exposed
      through this connector unchanged.
    * ``library_store`` — a :class:`LibraryStore` for the bring-your-own library chooser.
    """

    def __init__(
        self,
        config: Any,
        *,
        pipeline_factory: PipelineFactory | None = None,
        printer_server: Any | None = None,
        library_store: LibraryStore | None = None,
        default_out_dir: Path | None = None,
    ):
        self._config = config
        self._pipeline_factory = pipeline_factory or self._default_pipeline_factory
        self._printer = printer_server if printer_server is not None else self._default_printer_server()
        self._libraries = library_store if library_store is not None else self._default_library_store()
        self._default_out_dir = default_out_dir

    # --- defaults (lazy: importing kimcad heavy modules only when actually used) ----------
    def _default_printer_server(self) -> Any:
        from kimcad.mcp_server import PrinterMCPServer

        return PrinterMCPServer(self._config)

    def _default_library_store(self) -> LibraryStore:
        # Sit next to the history store under the user data dir when available; else cwd.
        base = getattr(self._config, "history_path", None)
        path = (Path(base()).parent if callable(base) else Path.cwd()) / "external_libraries.json"
        return FileLibraryStore(path)

    def _default_pipeline_factory(self, printer: str | None, material: str | None, backend: str | None) -> Any:
        # Mirrors kimcad.cli._build_pipeline so the connector drives the identical tested path.
        from kimcad.history import HistoryStore
        from kimcad.llm_provider import FallbackProvider, LLMProvider
        from kimcad.pipeline import Pipeline

        cfg = self._config
        prn = cfg.printer(printer) if printer else cfg.printer(None)
        mat = cfg.material(material) if material else cfg.material(None)
        primary = LLMProvider(cfg.llm_backend(backend))
        alt_cfg = cfg.llm_alt_backend()
        alt = LLMProvider(alt_cfg) if alt_cfg is not None else None
        provider = FallbackProvider(primary, alt) if alt is not None else primary
        return Pipeline(cfg, prn, mat, provider, history=HistoryStore(cfg.history_path()))

    # --- JSON-RPC framing (identical contract to mcp_server) -------------------------------
    @staticmethod
    def _result(req_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    @staticmethod
    def _tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    def _printer_tools(self) -> list[dict[str, Any]]:
        """Ask the composed printer server for its tools via the public tools/list protocol
        (no reaching into its internals)."""
        resp = self._printer.handle(
            {"jsonrpc": "2.0", "id": "_compose", "method": "tools/list"}
        )
        if isinstance(resp, dict) and isinstance(resp.get("result"), dict):
            return list(resp["result"].get("tools", []))
        return []

    def _tools(self) -> list[dict[str, Any]]:
        """Connector-native tools followed by the composed printer tools (strict superset)."""
        return _CONNECTOR_TOOLS + self._printer_tools()

    def handle(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC request. Returns the response, or None for a notification."""
        if not isinstance(request, dict):
            return self._error(None, -32600, "invalid request: expected a JSON object")
        method = request.get("method")
        req_id = request.get("id")
        if method == "initialize":
            return self._result(req_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": self._app_version()},
            })
        if method == "notifications/initialized":
            return None
        if method == "ping":
            return self._result(req_id, {})
        if method == "tools/list":
            return self._result(req_id, {"tools": self._tools()})
        if method == "tools/call":
            return self._call_tool(req_id, request.get("params") or {})
        return self._error(req_id, -32601, f"method not found: {method}")

    @staticmethod
    def _app_version() -> str:
        try:
            from kimcad import __version__

            return __version__
        except Exception:  # pragma: no cover - degrade rather than crash on a broken install
            return "0.0.0"

    def _call_tool(self, req_id: Any, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            return self._error(req_id, -32602, "tools/call params must be an object")
        name = params.get("name")
        if not name:
            return self._error(req_id, -32602, "tools/call requires a tool name")
        # Delegate any printer tool straight to the composed printer server, unchanged.
        if name in {t.get("name") for t in self._printer_tools()}:
            return self._printer.handle({
                "jsonrpc": "2.0", "id": req_id, "method": "tools/call", "params": params,
            })
        args = params.get("arguments")
        if not isinstance(args, dict):
            args = {}
        try:
            text = self._dispatch(name, args)
        except _ToolInputError as e:
            return self._result(req_id, self._tool_text(str(e), is_error=True))
        except Exception as e:  # never crash the server thread on a tool bug
            return self._result(req_id, self._tool_text(f"{type(e).__name__}: {e}", is_error=True))
        return self._result(req_id, self._tool_text(text))

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "design":
            return self._tool_design(args)
        if name == "list_libraries":
            return json.dumps({"external": self._libraries.list()})
        if name == "add_library":
            self._libraries.add(_require(args, "name"), _require(args, "path"))
            return json.dumps({"added": True, "external": self._libraries.list()})
        if name == "remove_library":
            removed = self._libraries.remove(_require(args, "name"))
            return json.dumps({"removed": removed, "external": self._libraries.list()})
        raise _ToolInputError(f"unknown tool: {name}")

    def _tool_design(self, args: dict[str, Any]) -> str:
        prompt = _require(args, "prompt")
        out_dir = Path(args["out_dir"]) if args.get("out_dir") else (
            self._default_out_dir or Path(tempfile.mkdtemp(prefix="kimcad-connect-"))
        )
        pipeline = self._pipeline_factory(
            args.get("printer"), args.get("material"), args.get("backend")
        )
        result = pipeline.run(
            prompt, out_dir,
            proceed_anyway=bool(args.get("proceed_anyway", False)),
            confirm_print=False,
        )
        return json.dumps(design_result_dict(result))


_CONNECTOR_TOOLS: list[dict[str, Any]] = [
    {
        "name": "design",
        "description": (
            "Turn a plain-English prompt into a print-ready part using KimCad's full pipeline "
            "(plan -> template-or-LLM geometry -> render -> mesh validation -> printability "
            "gate -> orient). Returns the generated .scad, the mesh path, the gate verdict, and "
            "readiness. This is the headline tool a front-end calls to hand a request to KimCad."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "what to design, in plain English"},
                "printer": {"type": "string", "description": "printer profile (default: configured)"},
                "material": {"type": "string", "description": "material (default: configured)"},
                "backend": {"type": "string", "description": "LLM backend key (default: configured)"},
                "out_dir": {"type": "string", "description": "output dir (default: a temp dir)"},
                "proceed_anyway": {"type": "boolean", "description": "accept a gate-failed part"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "list_libraries",
        "description": "List external SCAD library roots the user has plugged in (the library chooser).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_library",
        "description": (
            "Register an external SCAD library root the user installed themselves (e.g. NopSCADlib, "
            "dotSCAD). KimCad does not redistribute it — the user brings their own install, like an "
            "API key — so there is no license-bundling conflict."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "library name, e.g. NopSCADlib"},
                "path": {"type": "string", "description": "absolute path to the library root"},
            },
            "required": ["name", "path"],
        },
    },
    {
        "name": "remove_library",
        "description": "Unregister a previously added external SCAD library root.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "library name"}},
            "required": ["name"],
        },
    },
]


def main() -> None:  # pragma: no cover - the stdio loop is exercised via handle() in tests
    from kimcad.config import Config

    connector = KimCadConnector(Config.load())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except (ValueError, TypeError):
            continue
        try:
            response = connector.handle(request)
        except Exception:  # a handler bug must not take down the whole stdio server
            response = None
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":  # pragma: no cover
    main()
