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
import shutil
import threading
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

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

    Each printer carries a ``sliceable`` flag (it has an OrcaSlicer process profile) so
    the UI can mark any printer configured without one as not-yet-sliceable instead of
    letting the user pick one that will only refuse. (All three currently configured
    printers — Bambu P2S, Bambu A1, Elegoo Neptune 4 Max — are sliceable.)"""
    def _printer_entry(key: str) -> dict[str, Any]:
        p = config.printer(key)
        fp = p.orca_filament_profiles
        return {
            "key": key,
            "name": p.name,
            "sliceable": p.orca_process_profile is not None,
            # Materials this printer can actually print (has a verified filament profile for),
            # so the UI offers only what each printer supports — e.g. the Elegoo Neptune 4 Max
            # has no shipped TPU profile, so it doesn't offer TPU.
            "materials": list(fp.keys()),
            # Of those, the ones still using a vendor "Generic <MAT>" profile (vs a tuned,
            # brand-specific one) — so the UI can honestly flag only the generic combinations.
            "generic_materials": [m for m, name in fp.items() if name.startswith("Generic")],
        }

    printers = [_printer_entry(key) for key in config.raw.get("printers", {})]
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

    Returns ``(info, gcode_path)``. On any slicing problem — e.g. a printer configured
    with no process profile — ``info`` reports ``sliced: False`` with a plain-English
    note and ``gcode_path`` is None, rather than raising: the validated mesh is still
    downloadable, so the user just falls back to a plain model export.
    """
    from kimcad.slicer import OrcaProfileError, SliceError, resolve_slice_settings, slice_model

    printer = config.printer(printer_key)
    material = config.material(material_key)
    try:
        settings = resolve_slice_settings(config.orca_profiles_root(), printer, material)
        result = slice_model(
            mesh_path,
            binary=config.binary_path("orcaslicer"),
            out_dir=mesh_path.parent,
            settings=settings,
            # ENG-005: a per-(printer,material) basename so slicing the same mesh for a
            # different printer/material writes a distinct file rather than overwriting.
            basename=f"{mesh_path.name.split('.')[0]}_{printer.key}_{material.key}",
            timeout_s=config.limit("slice_timeout_s"),
        )
    except OrcaProfileError as e:
        # Profile gap (printer has no process profile, or this material isn't available on it)
        # — a known limitation, not an operational error. The note names the specific cause.
        return {"sliced": False, "reason": "no_profile", "note": str(e)}, None
    except SliceError as e:
        # Operational failure on a sliceable printer (bad slice / timeout).
        return {"sliced": False, "reason": "failed", "note": str(e)}, None
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
    # ENG-001 (gate safety): the printability verdict per design id, so the web slice/send
    # endpoints can refuse a gate-FAILED part server-side. The CLI already refuses to send a
    # gate-failed part; the web orchestrator must too, so a direct API client (not just the
    # browser, which hides the controls) can't dispatch a part the gate rejected. Evicted in
    # lockstep with `registry` via `_evict`.
    gate_status_by_rid: dict[int, str] = {}
    # ENG-003: cache slices by (rid, printer, material) so an identical re-confirm doesn't
    # re-run the (multi-minute, CPU-bound) slicer; serialize actual slices to protect the
    # target box and stop two OrcaSlicer runs racing on disk.
    slice_cache: "OrderedDict[tuple[int, Any, Any], tuple[dict[str, Any], Path | None]]" = (
        OrderedDict()
    )
    slice_lock = threading.Lock()
    counter = itertools.count(1)
    lock = threading.Lock()
    index_html = (WEB_DIR / "index.html").read_bytes()
    config_box: dict[str, Any] = {"config": config}

    def get_config() -> Any:
        if config_box["config"] is None:
            from kimcad.config import Config

            config_box["config"] = Config.load()
        return config_box["config"]

    def _evict(rid: int) -> None:
        """QA-003: drop a design id from every registry/cache AND remove its on-disk
        directory, so disk doesn't grow unbounded as the in-memory caps evict. Call under
        ``lock``."""
        gcode_registry.pop(rid, None)
        gate_status_by_rid.pop(rid, None)
        for k in [k for k in slice_cache if k[0] == rid]:
            slice_cache.pop(k, None)
        shutil.rmtree(web_root / str(rid), ignore_errors=True)

    class Handler(BaseHTTPRequestHandler):
        # QA-002: bound socket reads so a stalled/partial body (slowloris) can't pin a
        # worker thread forever. Slicing is CPU-bound, not socket I/O, so a slow slice is
        # unaffected; this only times out a client that opens a connection and dawdles.
        timeout = 30

        def log_message(self, *args: Any) -> None:  # keep the console quiet
            pass

        def _method_not_allowed(self) -> None:
            # QA-005: the resources exist for GET/POST, so an unsupported verb is 405
            # (method not allowed), not the stdlib default 501 (not implemented).
            self.send_response(405)
            self.send_header("Allow", "GET, POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_PUT = do_DELETE = do_PATCH = do_HEAD = do_OPTIONS = _method_not_allowed

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
            if self.path == "/api/connectors":
                from kimcad.connectors import connector_is_simulated

                cfg = get_config()
                names = list(cfg.connectors())
                # Each entry carries `simulated` (a loopback/no-hardware connection) so the UI
                # can label honestly instead of narrating a mock send as a real print (UX-001).
                conns = [
                    {"name": n, "simulated": connector_is_simulated(cfg.connector_config(n))}
                    for n in names
                ]
                # default = the first configured connector (config order); on a
                # no-hardware box that's the built-in "mock" loopback, intentionally.
                self._json(200, {"connectors": conns, "default": names[0] if names else None})
                return
            if self.path.startswith("/api/connector-status/"):
                # Strip any query string and URL-decode so a name with a space / non-ASCII
                # char (the client uses encodeURIComponent) matches the configured name.
                name = unquote(urlsplit(self.path).path.rsplit("/", 1)[-1])
                self._handle_connector_status(name)
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
                # Parse length inside the try so a bad header yields a clean 400,
                # not an int() crash on the request thread.
                if declared < 0:
                    raise ValueError("invalid Content-Length header")
                obj = json.loads(self.rfile.read(declared) or b"{}")
            except (ValueError, TypeError):
                self._json(400, {"error": "invalid request body"})
                return None
            # QA-001: a valid-JSON but non-object body (a list, scalar, or null) would
            # crash the handlers' data.get(...) with an AttributeError *before* their
            # traceback guards, dropping the connection with no response. Reject it here
            # so the docstring's "returns the parsed dict" promise holds for callers.
            if not isinstance(obj, dict):
                self._json(400, {"error": "invalid request body"})
                return None
            return obj

        def do_POST(self) -> None:
            if self.path == "/api/design":
                self._handle_design()
                return
            if self.path.startswith("/api/slice/"):
                self._handle_slice(self.path.rsplit("/", 1)[-1])
                return
            if self.path.startswith("/api/send/"):
                self._handle_send(self.path.rsplit("/", 1)[-1])
                return
            self._json(404, {"error": "not found"})

        def _handle_connector_status(self, name: str) -> None:
            """Live readiness of one printer connection: reachable and idle (ready), busy,
            offline, or not set up. Treats build/config problems (e.g. a missing API key) and
            status-read failures as non-error STATUSES, never a 5xx — and an offline printer is
            a normal status, not an error. Queried on demand by the UI (a slow real printer is
            shown as "checking")."""
            from kimcad.connectors import build_connector
            from kimcad.printer_connector import ConnectorError

            simulated = False
            try:
                connector = build_connector(get_config(), name)
                simulated = not getattr(connector, "drives_hardware", True)
                st = connector.status()
            except ConnectorError as e:
                # `simulated` is on every branch so the UI's typed rendering never falls through
                # (ENG-003/QA-002). A build/config failure is never a loopback, so it's False here.
                self._json(
                    200,
                    {"name": name, "ready": False, "reason": e.reason,
                     "simulated": simulated, "note": e.user_message},
                )
                return
            except Exception:  # malformed config / unexpected — a non-error status, never 5xx
                self._json(
                    200,
                    {"name": name, "ready": False, "reason": "error", "simulated": simulated,
                     "note": "couldn't check this connection"},
                )
                return
            ready = bool(st.online) and st.state.value == "operational"
            # `detail` lets the UI distinguish an online-but-faulted printer's cause (e.g.
            # "authentication failed (HTTP 401)") rather than a generic "busy" (UX-002/UX-003).
            self._json(
                200,
                {"name": name, "ready": ready, "online": st.online, "state": st.state.value,
                 "detail": st.detail, "simulated": simulated},
            )

        def _handle_send(self, raw_id: str) -> None:
            """Send an already-sliced part (by id) to a configured connector. The POST is
            the explicit per-send confirmation (the user confirmed in the UI)."""
            from kimcad.connectors import build_connector
            from kimcad.printer_connector import ConnectorError

            try:
                rid = int(raw_id)
            except ValueError:
                self._json(404, {"error": "not found"})
                return
            with lock:
                gcode_path = gcode_registry.get(rid)
            if gcode_path is None or not gcode_path.exists():
                self._json(404, {"error": "Slice the part first, then send it to a printer."})
                return
            # ENG-001: belt-and-suspenders — a gate-FAILED part is never dispatched even if a
            # gcode entry somehow exists (the slice guard above already blocks producing one).
            if gate_status_by_rid.get(rid) == "fail":
                self._json(200, {"sent": False, "reason": "gate_failed", "simulated": False,
                                 "note": "This part failed the printability gate; it can't be "
                                 "sent to a printer."})
                return
            data = self._read_json_body()
            if data is None:
                return
            connector_name = data.get("connector")
            if not connector_name:
                self._json(400, {"error": "No connector chosen."})
                return
            simulated = False
            try:
                connector = build_connector(get_config(), connector_name)
                simulated = not getattr(connector, "drives_hardware", True)
                job = connector.send(gcode_path, confirm=True)
            except ConnectorError as e:
                # not-sent is a soft outcome (offline / auth / refused / config / busy / unknown)
                # — the G-code is still downloadable, so report it without a 5xx. `reason` lets
                # the UI give a typed next step; `note` is the user-facing message; `simulated`
                # mirrors the status contract so a failed send is described as honestly as a sent
                # one (ENG-002).
                self._json(200, {"sent": False, "reason": e.reason,
                                 "simulated": simulated, "note": e.user_message})
                return
            except Exception as e:  # never leak a traceback
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            info: dict[str, Any] = {
                "sent": True,
                "connector": connector_name,
                "simulated": simulated,
                "job_id": job.job_id,
                "state": job.state.value,
            }
            try:
                st = connector.status()
                info["printer_state"] = st.state.value
                info["printer_detail"] = st.detail
            except ConnectorError:
                pass
            self._json(200, info)

        def _handle_design(self) -> None:
            data = self._read_json_body()
            if data is None:
                return
            # QA-007: a wrong-typed prompt (number, list) is a client error, not something
            # to silently str()-coerce and feed to the model.
            prompt_raw = data.get("prompt", "")
            if not isinstance(prompt_raw, str):
                self._json(400, {"error": "Please describe the part you want."})
                return
            prompt = prompt_raw.strip()
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
                    # ENG-001: remember the gate verdict so slice/send can refuse a failed part
                    # (default to "fail" — fail closed — if a report is somehow absent).
                    rep = payload.get("report") or {}
                    gate_status_by_rid[rid] = rep.get("gate_status") or "fail"
                    # ENG-004 / QA-003: cap the registry and clean up evicted dirs on disk.
                    while len(registry) > MAX_REGISTRY:
                        old_rid, _ = registry.popitem(last=False)
                        _evict(old_rid)
                payload["mesh_url"] = f"/api/mesh/{rid}"
            self._json(200, payload)

        def _respond_slice(self, rid: int, info: dict[str, Any], gcode_path: Path | None) -> None:
            out = dict(info)
            if gcode_path is not None and gcode_path.exists():
                with lock:
                    gcode_registry[rid] = gcode_path
                out["gcode_url"] = f"/api/gcode/{rid}"
            self._json(200, out)

        def _handle_slice(self, raw_id: str) -> None:
            """Slice an already-designed part (by mesh id) for the confirmed printer +
            material. The body carries the explicit print confirmation: a request to
            this endpoint *is* the user choosing to produce G-code.

            Idempotent + serialized (ENG-003/005): an identical (mesh, printer, material)
            re-confirm returns the cached slice instead of re-running OrcaSlicer, and a
            real slice holds ``slice_lock`` so two slices can't pin the box or race on disk.
            """
            try:
                rid = int(raw_id)
            except ValueError:
                self._json(404, {"error": "not found"})
                return
            mesh_path = registry.get(rid)
            if mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "Design the part first, then send it to a printer."})
                return
            # ENG-001: a part that FAILED the printability gate is never sliced or sent — mirror
            # the CLI's "download to inspect, never send" stance server-side (not just a hidden UI).
            if gate_status_by_rid.get(rid) == "fail":
                self._json(200, {"sliced": False, "reason": "gate_failed",
                                 "note": "This part failed the printability gate; download the "
                                 "model to inspect, but it can't be sliced or sent to a printer."})
                return
            data = self._read_json_body()
            if data is None:
                return
            key = (rid, data.get("printer") or None, data.get("material") or None)
            with lock:
                cached = slice_cache.get(key)
            if cached is not None and cached[1] is not None and cached[1].exists():
                self._respond_slice(rid, cached[0], cached[1])
                return
            with slice_lock:
                with lock:  # re-check: another thread may have just sliced this key
                    cached = slice_cache.get(key)
                if cached is not None and cached[1] is not None and cached[1].exists():
                    info, gcode_path = cached
                else:
                    try:
                        info, gcode_path = slice_registered_mesh(
                            get_config(), mesh_path, key[1], key[2]
                        )
                    except KeyError as e:
                        self._json(400, {"error": f"Unknown printer or material: {e}"})
                        return
                    except Exception as e:  # never leak a traceback to the browser
                        self._json(500, {"error": f"{type(e).__name__}: {e}"})
                        return
                    with lock:
                        slice_cache[key] = (info, gcode_path)
                        while len(slice_cache) > MAX_REGISTRY:
                            slice_cache.popitem(last=False)
            self._respond_slice(rid, info, gcode_path)

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
