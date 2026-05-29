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
- Slicing to G-code is intentionally NOT triggered here: the spec requires explicit
  per-print confirmation, and the slicer profile-path mapping is a separate task. The
  UI surfaces the validated 3MF/STL and marks G-code as a deliberate next step.
"""

from __future__ import annotations

import itertools
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kimcad.printability import dim_tolerance

WEB_DIR = Path(__file__).parent / "web"


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


def make_handler(pipeline: Any, web_root: Path) -> type[BaseHTTPRequestHandler]:
    """Build a request handler bound to a pipeline and an output directory."""
    web_root.mkdir(parents=True, exist_ok=True)
    registry: dict[int, Path] = {}
    counter = itertools.count(1)
    lock = threading.Lock()
    index_html = (WEB_DIR / "index.html").read_bytes()

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

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(200, index_html, "text/html; charset=utf-8")
                return
            if self.path.startswith("/api/mesh/"):
                self._serve_mesh(self.path.rsplit("/", 1)[-1])
                return
            self._json(404, {"error": "not found"})

        def _serve_mesh(self, raw_id: str) -> None:
            try:
                mesh_path = registry.get(int(raw_id))
            except ValueError:
                mesh_path = None
            if mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "mesh not found"})
                return
            self._send(200, mesh_path.read_bytes(), "model/stl")

        def do_POST(self) -> None:
            if self.path != "/api/design":
                self._json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                prompt = str(data.get("prompt", "")).strip()
            except (ValueError, TypeError):
                self._json(400, {"error": "invalid request body"})
                return
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
                payload["mesh_url"] = f"/api/mesh/{rid}"
            self._json(200, payload)

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
    pipeline = build_web_pipeline(demo=demo, backend=backend)
    web_root = out_root if out_root is not None else Path("output") / "web"
    httpd = ThreadingHTTPServer((host, port), make_handler(pipeline, web_root))
    mode = " (demo mode — no LLM)" if demo else ""
    print(f"KimCad web UI on http://{host}:{port}{mode}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        httpd.server_close()
