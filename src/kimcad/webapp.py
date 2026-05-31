"""Local web UI for KimCad (Phase 2, first slice).

A small, dependency-free web layer over the existing pipeline: a browser sends a
prompt, the same :class:`~kimcad.pipeline.Pipeline` runs, and the result — design
plan, printability verdict, target-vs-actual dimensions, and a 3D preview of the
rendered part — comes back as JSON the page renders.

Design notes:
- No web framework. The pipeline-to-payload mapping (:func:`design_response`) is a
  pure function, so the whole response shape is unit-tested offline with a fake
  provider and a stub renderer — no LLM, no binary, no socket. The HTTP layer is a
  thin stdlib ``http.server`` wrapper around it.
- The pipeline is injected, exactly as the CLI builds it, so the web layer reuses the
  tested wiring rather than duplicating it.
- Slicing to G-code requires explicit per-print confirmation. The design POST never
  slices; instead the user picks a printer + material and confirms, and a separate
  ``POST /api/slice/<id>`` slices the *already-validated, oriented* mesh — so confirming
  a print never re-runs the (slow) model. ``GET /api/gcode/<id>`` then downloads the
  proven G-code 3MF.
"""

from __future__ import annotations

import itertools
import json
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kimcad.printability import dim_tolerance

WEB_DIR = Path(__file__).parent / "web"

# Hardening caps (ENG-004): bound in-memory state and request size.
MAX_REGISTRY = 50  # keep at most the last N rendered meshes; evict oldest
MAX_BODY_BYTES = 1_048_576  # 1 MiB — prompts are tiny; reject anything larger

# ENG-010: map mesh file extensions to a content type.
_MESH_CONTENT_TYPES = {".stl": "model/stl", ".3mf": "model/3mf"}


def _plan_payload(plan: Any) -> dict[str, Any]:
    return {
        "object_type": plan.object_type,
        "summary": plan.summary,
        "target_bbox_mm": list(plan.bounding_box_mm) if plan.bounding_box_mm else None,
    }


def _report_payload(report: Any) -> dict[str, Any]:
    dims = []
    if report.target_bbox_mm:
        for axis, target, actual in zip("XYZ", report.target_bbox_mm, report.actual_bbox_mm):
            dims.append(
                {
                    "axis": axis,
                    "target": round(float(target), 2),
                    "actual": round(float(actual), 2),
                    "ok": abs(actual - target) <= dim_tolerance(target),
                }
            )
    return {
        "gate_status": report.gate_status,
        "headline": report.headline,
        "dims": dims,
        "findings": [
            {"level": level, "code": code, "message": message}
            for level, code, message in report.findings
        ],
        "watertight": report.watertight,
        "volume_mm3": round(float(report.volume_mm3), 1),
        "orientation": report.orientation,
    }


def design_response(pipeline: Any, prompt: str, out_dir: Path) -> tuple[dict[str, Any], Path | None]:
    """Run one prompt through the pipeline and shape the result for the UI.

    Pure mapping over a :class:`PipelineResult`; returns the JSON-able payload plus the
    rendered mesh path (or None) so the HTTP layer can expose it for the 3D preview.
    """
    result = pipeline.run(prompt, out_dir)
    payload: dict[str, Any] = {"status": result.status.value, "prompt": prompt}

    if result.clarification:
        payload["clarification"] = result.clarification
    if result.plan is not None:
        payload["plan"] = _plan_payload(result.plan)
    if result.report is not None:
        payload["report"] = _report_payload(result.report)
    if result.error:
        payload["error"] = result.error

    mesh_path = result.mesh_path if (result.mesh_path and result.mesh_path.exists()) else None
    payload["has_mesh"] = mesh_path is not None
    return payload, mesh_path


class DemoProvider:
    """A fast, LLM-free provider for demos and UI verification.

    Returns a fixed plan and a library-module call, so the full stack — render, gate,
    orient, 3D preview — exercises real geometry in under a second, without waiting on
    the CPU-bound model.
    """

    def generate_design_plan(self, prompt, printer, material, history=None):  # noqa: ANN001
        from kimcad.ir import DesignPlan

        return DesignPlan(
            object_type="box",
            summary=f"Demo part for: {prompt[:80]}",
            dimensions={"wall": 2.0},
            bounding_box_mm=[80, 60, 40],
            printer=printer.key,
            material=material.key,
        )

    def generate_openscad(self, plan, printer, material, history=None):  # noqa: ANN001
        return "use <library/containers.scad>;\nsnap_box(width=80, depth=60, height=40, wall=2);"


def build_web_pipeline(*, demo: bool = False, backend: str | None = None) -> Any:
    """Construct the pipeline for the web app, mirroring the CLI's wiring."""
    from kimcad.config import Config
    from kimcad.pipeline import Pipeline

    config = Config.load()
    printer = config.printer(None)
    material = config.material(None)
    provider: Any = DemoProvider() if demo else _real_provider(config, backend)
    return Pipeline(config, printer, material, provider)


def _real_provider(config: Any, backend: str | None) -> Any:
    from kimcad.llm_provider import LLMProvider

    return LLMProvider(config.llm_backend(backend))


def web_options(config: Any) -> dict[str, Any]:
    """The printer + material choices the UI offers, plus the configured defaults.

    Each printer carries a ``sliceable`` flag (it has an OrcaSlicer process profile)
    so the UI can mark printers — like the Elegoo, which currently has none — as
    not-yet-sliceable instead of letting the user pick one that will only refuse."""
    printers = [
        {
            "key": key,
            "name": config.printer(key).name,
            "sliceable": config.printer(key).orca_process_profile is not None,
        }
        for key in config.raw.get("printers", {})
    ]
    materials = [
        {"key": key, "name": config.material(key).name}
        for key in config.raw.get("materials", {})
    ]
    defaults = config.raw.get("defaults", {})
    return {
        "printers": printers,
        "materials": materials,
        "default_printer": defaults.get("printer"),
        "default_material": defaults.get("material"),
    }


def slice_registered_mesh(
    config: Any, mesh_path: Path, printer_key: str | None, material_key: str | None
) -> tuple[dict[str, Any], Path | None]:
    """Slice an already-validated, oriented mesh for the chosen printer + material.

    Returns ``(info, gcode_path)``. On any slicing problem — most importantly a printer
    with no process profile (the Elegoo case) — ``info`` reports ``sliced: False`` with
    a plain-English note and ``gcode_path`` is None, rather than raising: the validated
    mesh is still downloadable, so the user just falls back to a plain model export.
    """
    from kimcad.slicer import SliceError, resolve_slice_settings, slice_model

    printer = config.printer(printer_key)
    material = config.material(material_key)
    try:
        settings = resolve_slice_settings(config.orca_profiles_root(), printer, material)
        result = slice_model(
            mesh_path,
            binary=config.binary_path("orcaslicer"),
            out_dir=mesh_path.parent,
            settings=settings,
            basename=mesh_path.name.split(".")[0],
            timeout_s=config.limit("slice_timeout_s"),
        )
    except SliceError as e:
        return {"sliced": False, "note": str(e)}, None
    return (
        {
            "sliced": True,
            "printer": printer.name,
            "material": material.name,
            "gcode_lines": result.gcode_proof.line_count if result.gcode_proof else None,
            "estimate": result.gcode_proof.estimate_summary() if result.gcode_proof else "",
            "profiles": {
                "machine": settings.machine.stem,
                "process": settings.process.stem,
                "filament": settings.filament.stem,
            },
        },
        result.gcode_path,
    )


def make_handler(
    pipeline: Any, web_root: Path, *, config: Any = None
) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to a pipeline and an output directory.

    ``config`` is used for the printer/material options and for slicing the validated
    mesh on confirmation; it is loaded lazily on first need when not supplied, so the
    design-only tests can keep calling ``make_handler(pipeline, root)``.
    """
    web_root.mkdir(parents=True, exist_ok=True)
    # ENG-004: bounded LRU-by-insertion registries — oldest entries evicted past the cap.
    registry: "OrderedDict[int, Path]" = OrderedDict()
    gcode_registry: "OrderedDict[int, Path]" = OrderedDict()
    counter = itertools.count(1)
    lock = threading.Lock()
    index_html = (WEB_DIR / "index.html").read_bytes()
    config_box: dict[str, Any] = {"config": config}

    def get_config() -> Any:
        if config_box["config"] is None:
            from kimcad.config import Config

            config_box["config"] = Config.load()
        return config_box["config"]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # keep the console quiet
            pass

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, obj: dict[str, Any]) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

        def _send_download(self, body: bytes, content_type: str, filename: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(200, index_html, "text/html; charset=utf-8")
                return
            if self.path == "/api/options":
                self._json(200, web_options(get_config()))
                return
            if self.path.startswith("/vendor/"):
                self._serve_vendor(self.path[len("/vendor/") :])
                return
            if self.path.startswith("/api/mesh/"):
                self._serve_mesh(self.path.rsplit("/", 1)[-1])
                return
            if self.path.startswith("/api/gcode/"):
                self._serve_gcode(self.path.rsplit("/", 1)[-1])
                return
            self._json(404, {"error": "not found"})

        def _serve_gcode(self, raw_id: str) -> None:
            try:
                gcode_path = gcode_registry.get(int(raw_id))
            except ValueError:
                gcode_path = None
            if gcode_path is None or not gcode_path.exists():
                self._json(404, {"error": "g-code not found"})
                return
            ctype = _MESH_CONTENT_TYPES.get(gcode_path.suffix.lower(), "application/octet-stream")
            self._send_download(gcode_path.read_bytes(), ctype, gcode_path.name)

        def _serve_vendor(self, name: str) -> None:
            # Vendored, read-only static assets (three.js) served locally so the 3D
            # preview works offline. Only a plain filename in web/vendor/ is allowed — any
            # path separator or traversal is rejected before touching the filesystem.
            if not name or "/" in name or "\\" in name or ".." in name:
                self._json(404, {"error": "not found"})
                return
            path = WEB_DIR / "vendor" / name
            if not path.is_file():
                self._json(404, {"error": "not found"})
                return
            ctype = "text/javascript" if path.suffix == ".js" else "application/octet-stream"
            self._send(200, path.read_bytes(), f"{ctype}; charset=utf-8")

        def _serve_mesh(self, raw_id: str) -> None:
            try:
                mesh_path = registry.get(int(raw_id))
            except ValueError:
                mesh_path = None
            if mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "mesh not found"})
                return
            # ENG-010: content type follows the file extension, not a hardcoded STL.
            content_type = _MESH_CONTENT_TYPES.get(
                mesh_path.suffix.lower(), "application/octet-stream"
            )
            self._send(200, mesh_path.read_bytes(), content_type)

        def _read_json_body(self) -> dict[str, Any] | None:
            """Read + parse the JSON request body behind the size guard. Returns the
            parsed dict, or None after having already sent a 413/400 response."""
            # ENG-004: reject oversized bodies before reading them (bodies are tiny).
            raw_len = self.headers.get("Content-Length")
            try:
                declared = int(raw_len) if raw_len is not None else 0
            except (ValueError, TypeError):
                declared = -1  # malformed header -> treat as bad request below
            if declared > MAX_BODY_BYTES:
                self._json(413, {"error": "Request body too large."})
                return None
            try:
                # QA-003: parse length inside the try so a bad header yields a clean 400,
                # not an int() crash on the request thread.
                if declared < 0:
                    raise ValueError("invalid Content-Length header")
                return json.loads(self.rfile.read(declared) or b"{}")
            except (ValueError, TypeError):
                self._json(400, {"error": "invalid request body"})
                return None

        def do_POST(self) -> None:
            if self.path == "/api/design":
                self._handle_design()
                return
            if self.path.startswith("/api/slice/"):
                self._handle_slice(self.path.rsplit("/", 1)[-1])
                return
            self._json(404, {"error": "not found"})

        def _handle_design(self) -> None:
            data = self._read_json_body()
            if data is None:
                return
            prompt = str(data.get("prompt", "")).strip()
            if not prompt:
                self._json(400, {"error": "Please describe the part you want."})
                return
            with lock:
                rid = next(counter)
            try:
                payload, mesh_path = design_response(pipeline, prompt, web_root / str(rid))
            except Exception as e:  # never leak a traceback to the browser
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            if mesh_path is not None:
                with lock:
                    registry[rid] = mesh_path
                    # ENG-004: cap the registry — drop the oldest entries past MAX_REGISTRY.
                    while len(registry) > MAX_REGISTRY:
                        registry.popitem(last=False)
                payload["mesh_url"] = f"/api/mesh/{rid}"
            self._json(200, payload)

        def _handle_slice(self, raw_id: str) -> None:
            """Slice an already-designed part (by mesh id) for the confirmed printer +
            material. The body carries the explicit print confirmation: a request to
            this endpoint *is* the user choosing to produce G-code."""
            try:
                rid = int(raw_id)
            except ValueError:
                self._json(404, {"error": "not found"})
                return
            mesh_path = registry.get(rid)
            if mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "Design the part first, then send it to a printer."})
                return
            data = self._read_json_body()
            if data is None:
                return
            try:
                info, gcode_path = slice_registered_mesh(
                    get_config(), mesh_path, data.get("printer") or None, data.get("material") or None
                )
            except KeyError as e:
                self._json(400, {"error": f"Unknown printer or material: {e}"})
                return
            except Exception as e:  # never leak a traceback to the browser
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            if gcode_path is not None and gcode_path.exists():
                with lock:
                    gcode_registry[rid] = gcode_path
                    while len(gcode_registry) > MAX_REGISTRY:
                        gcode_registry.popitem(last=False)
                info["gcode_url"] = f"/api/gcode/{rid}"
            self._json(200, info)

    return Handler


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    demo: bool = False,
    backend: str | None = None,
    out_root: Path | None = None,
) -> None:
    """Start the local web UI (blocking)."""
    from kimcad.config import Config

    config = Config.load()
    pipeline = build_web_pipeline(demo=demo, backend=backend)
    web_root = out_root if out_root is not None else Path("output") / "web"
    httpd = ThreadingHTTPServer((host, port), make_handler(pipeline, web_root, config=config))
    mode = " (demo mode — no LLM)" if demo else ""
    print(f"KimCad web UI on http://{host}:{port}{mode}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()
