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

import base64
import hashlib
import itertools
import json
import re
import shutil
import threading
import uuid
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from kimcad.printability import dim_tolerance

WEB_DIR = Path(__file__).parent / "web"

# Hardening caps (ENG-004): bound in-memory state and request size.
MAX_REGISTRY = 50  # keep at most the last N rendered meshes; evict oldest
MAX_BODY_BYTES = 1_048_576  # 1 MiB — prompts are tiny; reject anything larger
# A design import carries a mesh (+ thumb), so it needs more headroom than a JSON body. Still
# bounded so a hostile upload can't exhaust memory.
MAX_IMPORT_BYTES = 32 * 1_048_576  # 32 MiB
# A photo for the vision on-ramp (Slice 7). Generous for a phone photo, bounded so a hostile
# upload can't exhaust memory; the local vision model also downsizes it.
MAX_PHOTO_BYTES = 12 * 1_048_576  # 12 MiB
# Stage 8.5 Slice 2: bound the client-supplied conversation history threaded into the model on a
# follow-up turn, so a crafted request can't blow up the prompt context.
MAX_HISTORY_TURNS = 20
MAX_HISTORY_CONTENT = 4000  # chars per turn
# ENG-001: also bound the AGGREGATE sanitized history, not just per-turn — 20 turns × 4000 chars
# would otherwise prepend ~80 KB of context to every refine, a latency tax on a CPU-bound local
# model. Keep the most-recent turns within this budget (newest are the most relevant for a refine).
MAX_HISTORY_TOTAL_CONTENT = 16000  # chars across all kept turns

# ENG-010: map mesh file extensions to a content type.
_MESH_CONTENT_TYPES = {".stl": "model/stl", ".3mf": "model/3mf"}

# Stage 4: content types for the built SPA static assets (JS/CSS/fonts/images) served from
# web/assets/. The React/TS SPA is compiled by Vite (build-time only) into src/kimcad/web;
# the Python server serves the committed build output with no Node toolchain at runtime.
_ASSET_CONTENT_TYPES = {
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".svg": "image/svg+xml; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
}


def _plan_payload(plan: Any) -> dict[str, Any]:
    return {
        "object_type": plan.object_type,
        "summary": plan.summary,
        "target_bbox_mm": list(plan.bounding_box_mm) if plan.bounding_box_mm else None,
    }


def _readiness_payload(readiness: Any) -> dict[str, Any] | None:
    """Shape the Smart Mesh readiness verdict for the report card (Stage 7). None when the
    pipeline didn't attach one (older results / non-completed paths)."""
    if readiness is None:
        return None
    return {
        "score": readiness.score,
        "verdict": readiness.verdict,
        "tone": readiness.tone,
        "confidence": readiness.confidence,
        "risks": [
            {
                "title": r.title,
                "detail": r.detail,
                "tone": r.tone,
                # Slice 8: forward the highlight geometry + id/region when this risk has a located
                # problem, so the viewport can show it on the model and the card can click-to-focus.
                **({"issueId": r.issue_id} if getattr(r, "issue_id", None) else {}),
                **({"region": r.region} if getattr(r, "region", None) else {}),
                **({"geometry": r.geometry} if getattr(r, "geometry", None) else {}),
            }
            for r in readiness.risks
        ],
        "recommendations": list(readiness.recommendations),
        "comparison": readiness.comparison,
        "attribution": readiness.attribution,
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
        "readiness": _readiness_payload(getattr(report, "readiness", None)),
    }


def _result_to_payload(result: Any) -> dict[str, Any]:
    """Shape a :class:`PipelineResult` into the JSON the UI consumes — shared by the initial
    design response and the live-slider re-render so both expose an identical contract:
    status, plan, report, and (for a template-backed part) the `template` family name plus
    the typed, range-bounded `parameters` snapshot the sliders bind to."""
    payload: dict[str, Any] = {"status": result.status.value}
    if result.clarification:
        payload["clarification"] = result.clarification
    if result.plan is not None:
        payload["plan"] = _plan_payload(result.plan)
    if result.report is not None:
        payload["report"] = _report_payload(result.report)
    if result.template is not None:
        # A deterministic, instantly re-renderable part: advertise its family and the typed,
        # range-bounded parameters the live sliders drive.
        payload["template"] = result.template.family.name
        payload["parameters"] = result.template.parameters()
    if result.error:
        payload["error"] = result.error
    payload["has_mesh"] = bool(result.mesh_path and result.mesh_path.exists())
    return payload


def _sanitize_history(raw: Any) -> list[dict[str, str]] | None:
    """Coerce client-supplied conversation history into the ``[{role, content}]`` shape the model
    accepts (Stage 8.5 Slice 2 — a follow-up turn threads the prior conversation for context).
    Defensive: keep only well-formed user/assistant turns, cap the count + each content length, and
    never raise. Returns None when there's nothing usable (the call then behaves like a fresh turn)."""
    if not isinstance(raw, list):
        return None
    # Walk newest-first so the aggregate budget keeps the most-recent (most relevant) turns, then
    # reverse back to chronological order. Bound by turn count, per-turn length, AND total length.
    out: list[dict[str, str]] = []
    total = 0
    for turn in reversed(raw):
        if len(out) >= MAX_HISTORY_TURNS:
            break
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        content = turn.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            continue
        clipped = content[:MAX_HISTORY_CONTENT]
        if total + len(clipped) > MAX_HISTORY_TOTAL_CONTENT:
            break  # adding this older turn would blow the aggregate budget — stop here
        out.append({"role": role, "content": clipped})
        total += len(clipped)
    out.reverse()
    return out or None


# MS-3: cap on live design-progress slots (abandoned/cancelled runs are LRU-evicted).
_MAX_PROGRESS_SLOTS = 32
# A client-supplied job_id keys in-memory progress state, so it's validated to a short, safe token
# (a UUID fits) before use; anything else disables progress tracking for that run (best-effort).
_JOB_ID_RE = re.compile(r"\A[A-Za-z0-9-]{1,64}\Z")


def _valid_job_id(value: Any) -> str | None:
    return value if isinstance(value, str) and _JOB_ID_RE.match(value) else None


def design_response(
    pipeline: Any,
    prompt: str,
    out_dir: Path,
    history: list[dict[str, str]] | None = None,
    *,
    allow_experimental: bool = True,
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], Path | None, Any]:
    """Run one prompt through the pipeline and shape the result for the UI.

    ``history`` is the prior conversation (``[{role, content}]``) for a follow-up/refine turn, so the
    model sees the context of the part being changed; ``None`` runs the prompt standalone.

    ``progress`` (MS-3) is an optional phase callback forwarded to the pipeline so a long run can
    report planning→generating→rendering→validating to the UI's progress poll.

    Returns the JSON-able payload, the rendered mesh path (or None) for the 3D preview, and
    the :class:`PipelineResult` itself so the HTTP layer can register per-design re-render
    state (the base plan + template family) for the live-slider endpoint.
    """
    result = pipeline.run(
        prompt, out_dir, history=history, allow_experimental=allow_experimental, progress=progress
    )
    payload = _result_to_payload(result)
    payload["prompt"] = prompt
    mesh_path = result.mesh_path if (result.mesh_path and result.mesh_path.exists()) else None
    return payload, mesh_path, result


def _design_snapshot(payload: dict[str, Any], result: Any, prompt: str) -> dict[str, Any]:
    """The saveable snapshot for a completed design (Stage 8.5 "My Designs"): the API payload (sans
    the volatile, id-specific ``mesh_url``), the facts the library indexes by, and the serialized
    plan needed to restore the live-slider re-render state when the design is reopened."""
    report = payload.get("report") or {}
    readiness = report.get("readiness") or {}
    plan_dump = None
    try:
        if result.plan is not None:
            plan_dump = result.plan.model_dump(mode="json")
    except Exception:  # noqa: BLE001 - a non-serializable plan just means reopen is view-only
        plan_dump = None
    return {
        "payload": {k: v for k, v in payload.items() if k != "mesh_url"},
        "plan": plan_dump,
        "prompt": prompt,
        "object_type": (payload.get("plan") or {}).get("object_type", ""),
        "gate_status": report.get("gate_status", ""),
        "readiness_score": readiness.get("score") if isinstance(readiness, dict) else None,
        "template_family": payload.get("template"),
    }


def _decode_data_url_png(value: Any) -> bytes | None:
    """Decode a ``data:image/png;base64,...`` thumbnail (captured from the viewport canvas) to raw
    PNG bytes, or None if absent / not a PNG data URL / undecodable / implausibly large. The HTTP
    body cap already bounds the input; this is the belt-and-suspenders content check."""
    if not isinstance(value, str) or "," not in value:
        return None
    head, b64 = value.split(",", 1)
    if "image/png" not in head:
        return None
    try:
        raw = base64.b64decode(b64, validate=True)
    except Exception:  # noqa: BLE001 - a malformed thumbnail just means no thumbnail
        return None
    return raw if 0 < len(raw) <= 2_000_000 else None


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
        # ENG-506: in demo mode this is now SHADOWED by the template tier — object_type "box"
        # matches the snap_box family, so the geometry is emitted deterministically and this
        # never runs. Kept as the documented LLM-codegen contract shape (and exercised by the
        # LLM-path tests via FakeProvider); it would run only if the demo plan named a
        # non-template object_type.
        return "use <library/containers.scad>;\nsnap_box(width=80, depth=60, height=40, wall=2);"

    def describe_photo(self, image_bytes, printer, material):  # noqa: ANN001
        # Slice 7: a canned vision seed so the photo on-ramp is exercisable in demo/UI checks
        # without the real (CPU-bound) vision model. The image is ignored; the fixed seed stands in.
        return (
            "A small rectangular box, roughly 80 mm wide, 60 mm deep, and 40 mm tall — these sizes "
            "are rough guesses from the photo (a photo has no scale), so adjust them."
        )


def build_web_pipeline(*, demo: bool = False, backend: str | None = None) -> Any:
    """Construct the pipeline for the web app, mirroring the CLI's wiring."""
    from kimcad.config import Config
    from kimcad.history import HistoryStore
    from kimcad.pipeline import Pipeline

    config = Config.load()
    printer = config.printer(None)
    material = config.material(None)
    provider: Any = DemoProvider() if demo else _real_provider(config, backend)
    # Slice 6 MS-3: wrap the real provider so a Settings cloud opt-in routes the next request to the
    # user's OpenRouter model (their key), and otherwise stays local. The demo provider is left bare.
    if not demo:
        provider = _SettingsAwareProvider(provider, config)
    # Real designs are remembered for the learning comparison; the demo stays stateless so a UI
    # check never pollutes the user's history (and the demo builds the same part anyway).
    history = None if demo else HistoryStore(config.history_path())
    return Pipeline(config, printer, material, provider, history=history)


def _real_provider(config: Any, backend: str | None) -> Any:
    from kimcad.llm_provider import FallbackProvider, LLMProvider

    primary = LLMProvider(config.llm_backend(backend))
    alt_cfg = config.llm_alt_backend()
    alt = LLMProvider(alt_cfg) if alt_cfg is not None else None
    return FallbackProvider(primary, alt) if alt is not None else primary


class _SettingsAwareProvider:
    """Routes each LLM call to the local provider by default, or to a cloud (OpenRouter) provider
    when the user has enabled cloud + saved an OpenRouter key + a model in the in-app Settings
    (Slice 6 MS-3). Per the spec, KimCad does NOT hardwire a cloud vendor — OpenRouter is the router
    and the user picks the model.

    It reads the settings file per call (a design call is slow + rare, so the small JSON read is
    negligible) so a Settings toggle takes effect on the next request without a server restart. Cloud
    is opt-in and degrades to LOCAL on any gap — not enabled, no key, no model, or a cloud build
    failure — because local must always work."""

    def __init__(self, local: Any, config: Any):
        self._local = local
        self._config = config
        self._cloud_cache: dict[tuple[str, str], Any] = {}

    def _settings(self) -> dict[str, Any]:
        try:
            from kimcad.settings_store import SettingsStore

            return SettingsStore(self._config.settings_path()).all()
        except Exception:  # noqa: BLE001 - a settings read failure just means "no cloud override"
            return {}

    def _active(self) -> Any:
        s = self._settings()
        if not s.get("cloud_enabled"):
            return self._local
        key = s.get("openrouter_api_key")
        model = s.get("cloud_model")
        if not (isinstance(key, str) and key and isinstance(model, str) and model):
            return self._local  # enabled but not fully configured -> local
        cache_key = (key, model)
        prov = self._cloud_cache.get(cache_key)
        if prov is None:
            try:
                from dataclasses import replace

                from kimcad.llm_provider import LLMProvider

                backend = replace(self._config.llm_backend("custom_openrouter"), model_name=model)
                prov = LLMProvider(backend, api_key=key)
                self._cloud_cache[cache_key] = prov
            except Exception:  # noqa: BLE001 - a cloud build failure degrades to local
                return self._local
        return prov

    def generate_design_plan(self, *args: Any, **kwargs: Any) -> Any:
        return self._active().generate_design_plan(*args, **kwargs)

    def generate_openscad(self, *args: Any, **kwargs: Any) -> Any:
        return self._active().generate_openscad(*args, **kwargs)

    def describe_photo(self, image_bytes: bytes, printer: Any, material: Any) -> str:
        """Vision is ALWAYS local — the photo never auto-sends, even when cloud TEXT is enabled
        (Slice 7 trust rule: local vision by default, the photo stays on the machine). Build a
        dedicated local Ollama vision provider rather than routing through the cloud."""
        from kimcad.llm_provider import LLMProvider

        local = LLMProvider(self._config.llm_backend("local"))
        return local.describe_photo(image_bytes, printer, material)


def _mask_key(key: Any) -> str | None:
    """A masked form of an API key for redisplay — a fixed dot run + the last 5 characters. None
    when there's no key. The full key is NEVER returned by the API (only this masked form). A real
    OpenRouter key is 40+ chars; for an implausibly short value we reveal nothing (the last-5 would
    otherwise expose most/all of it)."""
    if not isinstance(key, str) or not key:
        return None
    tail = key[-5:] if len(key) > 8 else ""
    return "•" * 16 + tail


def settings_response(config: Any, saved: dict[str, Any]) -> dict[str, Any]:
    """The full Settings payload: the printer/material choices + effective defaults, plus the cloud
    opt-in state. The OpenRouter key is returned ONLY masked (last 5) — never in full."""
    payload = web_options(config, saved)
    key = saved.get("openrouter_api_key")
    payload["cloud_enabled"] = bool(saved.get("cloud_enabled"))
    payload["cloud_model"] = saved.get("cloud_model") if isinstance(saved.get("cloud_model"), str) else ""
    payload["has_cloud_key"] = isinstance(key, str) and bool(key)
    payload["cloud_key_masked"] = _mask_key(key)
    payload["experimental_enabled"] = bool(saved.get("experimental_enabled"))
    return payload


def effective_defaults(config: Any, saved: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """The default printer + material the app should use: the user's saved Settings choice when it's
    still a known config key, else the shipped config default. A saved key that no longer exists
    (a printer/material removed from config between sessions) falls back rather than dangling."""
    defaults = config.raw.get("defaults", {})
    saved = saved or {}
    printer_keys = set(config.raw.get("printers", {}))
    material_keys = set(config.raw.get("materials", {}))
    sp = saved.get("default_printer")
    sm = saved.get("default_material")
    return (
        sp if sp in printer_keys else defaults.get("printer"),
        sm if sm in material_keys else defaults.get("material"),
    )


def web_options(config: Any, saved_settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """The printer + material choices the UI offers, plus the effective defaults (the user's saved
    Settings choice overlaid on the shipped config default — Stage 8.5 Slice 6).

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
    default_printer, default_material = effective_defaults(config, saved_settings)
    return {
        "printers": printers,
        "materials": materials,
        "default_printer": default_printer,
        "default_material": default_material,
    }


def _estimate_detail_with_weight(proof: Any, material: Any) -> dict[str, Any]:
    """The slicer's structured estimate, with a filament *weight* filled in.

    Prefer the slicer's own grams (it used the profile's real density). When the profile
    carried no density — several shipped vendor profiles set ``filament_density = 0``, so the
    slicer reports volume but no weight — estimate grams from the reported volume (cm³) and the
    material's nominal density, and flag it (``filament_g_estimated``) so the UI can say so."""
    detail = proof.estimate_detail()
    estimated = False
    if detail.get("filament_g") is None:
        cm3 = detail.get("filament_cm3")
        density = getattr(material, "density", None)
        # Require a real positive volume: a degenerate cm3 of 0 would derive a "0.0 g (estimated)"
        # that the UI can't honestly show (no weight, but an "estimated" caption) — keep it None.
        if cm3 and cm3 > 0 and density:
            detail["filament_g"] = round(cm3 * density, 1)
            estimated = True
    detail["filament_g_estimated"] = estimated
    return detail


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
            # ENG-005: a per-(printer,material) basename so slicing the same mesh for a different
            # printer/material writes a distinct file rather than overwriting. The mesh is always
            # named `part.oriented.<suffix>` by the pipeline, so the segment before the first dot
            # is the stable base name.
            basename=f"{mesh_path.name.partition('.')[0]}_{printer.key}_{material.key}",
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
            # Structured estimate so the SPA can lay out a labeled breakout (time / layers /
            # filament length / filament weight) instead of the single ``estimate`` string.
            # Weight is filled from volume × the material's density when the profile emits none.
            "estimate_detail": (
                _estimate_detail_with_weight(result.gcode_proof, material)
                if result.gcode_proof
                else None
            ),
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
    # QA-003: clear stale per-design dirs from a previous run. The in-memory registry + id
    # counter reset on each start, so old output/web/<id> dirs (no longer referenced) would
    # otherwise accumulate; `_evict` only reclaims within a session.
    for child in web_root.iterdir():
        if child.is_dir() and child.name.isdigit():
            shutil.rmtree(child, ignore_errors=True)
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
    # Stage 5: serialize live-slider re-renders so two rapid drags can't interleave writes to the
    # same per-design output dir (mirrors slice_lock). Re-renders are sub-second; the latest wins.
    # A single global lock (not per-id) is intentional: the web UI is single-user/loopback, so
    # contention across different designs is nil; key it by rid only if a multi-client mode lands
    # (ENG-503).
    render_lock = threading.Lock()
    # Stage 5: per-design re-render state for the live-slider endpoint — the base plan + the
    # matched template family name, so /api/render/<id> can deterministically rebuild the
    # part at new parameter values with no model call. Only template-backed designs are
    # registered here (an LLM-backed part has no adjustable parameters). Evicted via _evict.
    template_state: dict[int, tuple[Any, str]] = {}
    # Stage 8.5 Slice 1: a per-design saveable snapshot (the API payload + serialized plan + the
    # facts the "My Designs" library needs), so a save request — which carries only the design id,
    # a name, and a thumbnail — can persist the design without the client re-sending everything.
    # Evicted via _evict alongside the rest of the per-design state.
    design_snapshot: dict[int, dict[str, Any]] = {}
    # QA-002: a stable saved_id per live rid, so rapid auto-saves of the same design (fired before
    # the client has learned the server-minted id) converge to ONE library entry instead of minting
    # a duplicate each time. Evicted via _evict alongside the rest of the per-design state.
    rid_saved_id: dict[int, str] = {}
    counter = itertools.count(1)
    version_counter = itertools.count(1)  # cache-busting suffix for re-rendered meshes
    lock = threading.Lock()
    # MS-3: live design-phase slots keyed by a client-supplied job_id, so the SPA can poll
    # GET /api/design/progress/<job_id> WHILE a (multi-minute) design runs on another request
    # thread and show the current phase. Bounded + LRU-evicted; an entry is removed when its run
    # finishes (the poll then gets a null phase and the client, whose POST has resolved, stops).
    # Its own lock so a poll never contends with the rid counter / registry lock.
    design_progress: "OrderedDict[str, str]" = OrderedDict()
    progress_lock = threading.Lock()
    index_html = (WEB_DIR / "index.html").read_bytes()
    config_box: dict[str, Any] = {"config": config}

    def get_config() -> Any:
        if config_box["config"] is None:
            from kimcad.config import Config

            config_box["config"] = Config.load()
        return config_box["config"]

    # Stage 8.5 Slice 1: the saved-designs store, built lazily from config. Best-effort — if it
    # can't be created the persistence endpoints degrade (empty library / save no-ops) and the
    # live design loop is untouched.
    designs_box: dict[str, Any] = {"store": None, "tried": False}

    def get_designs_store() -> Any:
        if not designs_box["tried"]:
            designs_box["tried"] = True
            try:
                from kimcad.design_store import DesignStore

                designs_box["store"] = DesignStore(get_config().designs_path())
            except Exception:  # noqa: BLE001
                designs_box["store"] = None
        return designs_box["store"]

    # Stage 8.5 Slice 6: the user settings store, built lazily from config. Best-effort — if it
    # can't be created, /api/settings degrades to the shipped config defaults (read) / no-ops (write).
    settings_box: dict[str, Any] = {"store": None, "tried": False}

    def get_settings_store() -> Any:
        if not settings_box["tried"]:
            settings_box["tried"] = True
            try:
                from kimcad.settings_store import SettingsStore

                settings_box["store"] = SettingsStore(get_config().settings_path())
            except Exception:  # noqa: BLE001
                settings_box["store"] = None
        return settings_box["store"]

    def saved_settings() -> dict[str, Any]:
        """The user's saved settings as a dict (empty when the store is absent/unreadable)."""
        store = get_settings_store()
        return store.all() if store is not None else {}

    def _evict(rid: int) -> None:
        """QA-003: drop a design id from every registry/cache AND remove its on-disk
        directory, so disk doesn't grow unbounded as the in-memory caps evict. Call under
        ``lock``."""
        gcode_registry.pop(rid, None)
        gate_status_by_rid.pop(rid, None)
        template_state.pop(rid, None)
        design_snapshot.pop(rid, None)
        rid_saved_id.pop(rid, None)
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
            # QA-005: the resources exist for GET/HEAD/POST, so an unsupported verb is 405
            # (method not allowed), not the stdlib default 501 (not implemented). QA-006: return
            # the app's JSON error shape (not an empty body) so the error contract is uniform.
            body = json.dumps({"error": "Method not allowed."}).encode("utf-8")
            self.send_response(405)
            self.send_header("Allow", "GET, HEAD, POST")
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not getattr(self, "_head_only", False):
                self.wfile.write(body)

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _method_not_allowed

        def do_HEAD(self) -> None:
            # QA-001: HEAD on a GET resource returns the same status + headers as GET with NO
            # body (so curl -I / health checks / link-checkers get a header-only 200, not a 405).
            # The GET handlers run unchanged; `_send`/`_send_download` suppress the body when set.
            self._head_only = True
            try:
                self.do_GET()
            finally:
                self._head_only = False

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not getattr(self, "_head_only", False):
                self.wfile.write(body)

        def _json(self, status: int, obj: dict[str, Any]) -> None:
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json")

        def _send_download(self, body: bytes, content_type: str, filename: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if not getattr(self, "_head_only", False):
                self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                self._send(200, index_html, "text/html; charset=utf-8")
                return
            if self.path == "/api/options":
                self._json(200, web_options(get_config(), saved_settings()))
                return
            if self.path == "/api/settings":
                self._handle_settings_get()
                return
            if self.path == "/api/model-status":
                self._handle_model_status()
                return
            if self.path == "/api/health":
                self._handle_health()
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
            if self.path.startswith("/assets/"):
                # Strip any query string (Vite may version an asset URL) before the lookup.
                self._serve_asset(urlsplit(self.path).path[len("/assets/") :])
                return
            if self.path.startswith("/api/mesh/"):
                # urlsplit drops any ?v=<n> cache-buster (the live-slider re-render appends one
                # so the browser fetches the fresh mesh) before parsing the id.
                self._serve_mesh(urlsplit(self.path).path.rsplit("/", 1)[-1])
                return
            if self.path.startswith("/api/gcode/"):
                self._serve_gcode(urlsplit(self.path).path.rsplit("/", 1)[-1])
                return
            # MS-3: poll the live phase of an in-flight design (planning/generating/rendering/
            # validating). Always 200 — an unknown or finished id returns a null phase, so the
            # client's poller never errors. Distinct from "/api/designs" (the saved-designs list).
            if self.path.startswith("/api/design/progress/"):
                # The id isn't re-validated here: it only does a dict lookup (no path/IO), and an
                # invalid id simply misses an entry that could only have been seeded by a valid one.
                jid = unquote(urlsplit(self.path).path[len("/api/design/progress/") :])
                with progress_lock:
                    phase = design_progress.get(jid)
                self._json(200, {"phase": phase})
                return
            # Stage 8.5 — saved designs ("My Designs").
            if self.path == "/api/designs":
                self._handle_designs_list()
                return
            if self.path.startswith("/api/designs/"):
                tail = unquote(urlsplit(self.path).path[len("/api/designs/") :])
                if tail.endswith("/thumb"):
                    self._serve_design_thumb(tail[: -len("/thumb")])
                elif tail.endswith("/export"):
                    self._serve_design_export(tail[: -len("/export")])
                else:
                    self._handle_design_reopen(tail)
                return
            self._json(404, {"error": "Not found."})

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

        def _serve_static(self, path: Path, content_type: str) -> None:
            # QA-002: serve a read-only static file with an ETag for cheap revalidation. The
            # build's filenames are STABLE (un-hashed), so a content-hash ETag + `no-cache`
            # (revalidate) is the correct caching: never stale after a rebuild (the ETag changes
            # with the content), and a matching `If-None-Match` returns a body-less 304.
            body = path.read_bytes()
            etag = '"' + hashlib.sha256(body).hexdigest()[:16] + '"'
            if self.headers.get("If-None-Match") == etag:
                self.send_response(304)
                self.send_header("ETag", etag)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", etag)
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if not getattr(self, "_head_only", False):
                self.wfile.write(body)

        def _serve_vendor(self, name: str) -> None:
            # Vendored, read-only static assets (three.js) served locally so the 3D preview
            # works offline. Only a plain filename in web/vendor/ is allowed — any path
            # separator or traversal is rejected before touching the filesystem (mirrors
            # _serve_asset's guard exactly).
            if not name or "/" in name or "\\" in name or ".." in name:
                self._json(404, {"error": "Not found."})
                return
            path = WEB_DIR / "vendor" / name
            if not path.is_file():
                self._json(404, {"error": "Not found."})
                return
            ctype = (
                "text/javascript; charset=utf-8"
                if path.suffix == ".js"
                else "application/octet-stream"
            )
            self._serve_static(path, ctype)

        def _serve_asset(self, name: str) -> None:
            # Built SPA static assets (JS/CSS/fonts/images) served from web/assets/. Mirrors the
            # vendor guard exactly: only a plain filename is allowed — any path separator or
            # traversal is rejected before touching the filesystem. ENG-405/406: an unknown
            # suffix falls back to application/octet-stream — a safe default (the SPA build only
            # emits the mapped types), and the type map (`_ASSET_CONTENT_TYPES`) is the single
            # source for the asset content types.
            if not name or "/" in name or "\\" in name or ".." in name:
                self._json(404, {"error": "Not found."})
                return
            path = WEB_DIR / "assets" / name
            if not path.is_file():
                self._json(404, {"error": "Not found."})
                return
            ctype = _ASSET_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
            self._serve_static(path, ctype)

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
                # QA-004: we reject without draining the oversized upload, so tell the client to
                # close rather than treat this as a keep-alive turn (a client still streaming the
                # body would otherwise hit a connection-abort reading the response).
                self.close_connection = True
                self._json(413, {"error": "Request body too large."})
                return None
            try:
                # Parse length inside the try so a bad header yields a clean 400,
                # not an int() crash on the request thread.
                if declared < 0:
                    raise ValueError("invalid Content-Length header")
                obj = json.loads(self.rfile.read(declared) or b"{}")
            except (ValueError, TypeError):
                # QA-004: name the actual problem (malformed JSON) rather than a generic message.
                self._json(400, {"error": "Request body isn't valid JSON."})
                return None
            # QA-001: a valid-JSON but non-object body (a list, scalar, or null) would
            # crash the handlers' data.get(...) with an AttributeError *before* their
            # traceback guards, dropping the connection with no response. Reject it here
            # so the docstring's "returns the parsed dict" promise holds for callers.
            # QA-004: a distinct message so the client knows the shape (not the syntax) is wrong.
            if not isinstance(obj, dict):
                self._json(400, {"error": "Request body must be a JSON object."})
                return None
            return obj

        def do_POST(self) -> None:
            if self.path == "/api/design":
                self._handle_design()
                return
            if self.path == "/api/settings":
                self._handle_settings_post()
                return
            if self.path == "/api/photo-seed":
                self._handle_photo_seed()
                return
            if self.path.startswith("/api/slice/"):
                self._handle_slice(self.path.rsplit("/", 1)[-1])
                return
            if self.path.startswith("/api/render/"):
                self._handle_render(self.path.rsplit("/", 1)[-1])
                return
            if self.path.startswith("/api/send/"):
                self._handle_send(self.path.rsplit("/", 1)[-1])
                return
            # Stage 8.5 — saved designs ("My Designs").
            if self.path == "/api/designs/save":
                self._handle_design_save()
                return
            if self.path == "/api/designs/import":
                self._handle_design_import()
                return
            if self.path.startswith("/api/designs/"):
                tail = unquote(self.path[len("/api/designs/") :])
                for verb in ("rename", "delete", "duplicate"):
                    if tail.endswith("/" + verb):
                        self._handle_design_mutate(tail[: -(len(verb) + 1)], verb)
                        return
            self._json(404, {"error": "Not found."})

        # Stage 8.5 Slice 6 — the in-app Settings screen.
        def _handle_settings_get(self) -> None:
            """The user's effective settings + the choices the Settings screen offers (printers,
            materials, the active default of each, and the cloud opt-in state). The OpenRouter key
            is returned only MASKED — never in full."""
            self._json(200, settings_response(get_config(), saved_settings()))

        def _handle_health(self) -> None:
            """Tool + app health for the Settings screen (Slice 6 MS-5): whether the bundled
            OpenSCAD + OrcaSlicer binaries are present on disk, plus the app version. Best-effort —
            a missing binary or config key is a STATUS (present:false), never a 500."""
            from kimcad import __version__

            cfg = get_config()

            def _present(name: str) -> bool:
                try:
                    return cfg.binary_path(name).exists()
                except Exception:  # noqa: BLE001 - a missing config key is "not present", not a 500
                    return False

            self._json(200, {
                "version": __version__,
                "openscad": _present("openscad"),
                "orcaslicer": _present("orcaslicer"),
            })

        def _handle_model_status(self) -> None:
            """The AI model's health for the Settings screen (Slice 6 MS-2). For the local (Ollama)
            backend: whether Ollama is reachable and the active model (gemma4:e4b) is pulled — so the
            UI can show Running / Start Ollama / Get the model. Best-effort + bounded (a short probe
            timeout); a config gap or a down model server is a STATUS, never a 500."""
            cfg = get_config()
            # Slice 6 MS-3: if the user enabled cloud + saved a key + a model, the EFFECTIVE backend
            # is their OpenRouter model — report that, not the local default.
            saved = saved_settings()
            ck = saved.get("openrouter_api_key")
            cm = saved.get("cloud_model")
            if saved.get("cloud_enabled") and isinstance(ck, str) and ck and isinstance(cm, str) and cm:
                self._json(200, {"model": cm, "backend": "cloud", "running": True, "model_present": True})
                return
            try:
                backend = cfg.llm_backend()
            except Exception:  # noqa: BLE001 - a config gap shouldn't 500 the status
                backend = None
            model_name = (backend.model_name if backend else "gemma4:e4b") or "gemma4:e4b"
            base_url = (backend.base_url if backend else "") or ""
            # Local (Ollama) vs a cloud backend: an ollama provider or a localhost:11434 base_url.
            is_local = backend is not None and (backend.provider == "ollama" or "11434" in base_url)
            payload: dict[str, Any] = {
                "model": model_name,
                "backend": "local" if is_local else "cloud",
            }
            if is_local:
                from kimcad.model_advisor import probe_ollama

                running, installed = probe_ollama(base_url)
                names = {m.name for m in installed}
                # gemma4:e4b may be pulled as the bare tag or a quantized variant
                # (gemma4:e4b-it-q4_K_M). Match the exact tag, or one that extends it with a
                # `-<variant>` suffix — the separator anchors the prefix so an unrelated tag that
                # merely starts with the same characters can't false-match.
                present = any(n == model_name or n.startswith(model_name + "-") for n in names)
                payload["running"] = running
                payload["model_present"] = present
            else:
                # A cloud backend is "ready" when configured; reachability isn't probed in-band (it
                # would need the key). MS-3 surfaces the cloud label + key state separately.
                payload["running"] = True
                payload["model_present"] = True
            self._json(200, payload)

        def _handle_settings_post(self) -> None:
            """Persist a Settings change (default printer / material). Each key is validated against
            the configured choices — an unknown value is a 400, never silently saved — then written.
            Returns the new effective settings with a ``saved`` flag (false if the store couldn't
            persist) so the UI can tell the user honestly whether the choice stuck. Never 500s."""
            data = self._read_json_body()
            if data is None:
                return
            cfg = get_config()
            # Slice 6 MS-5: a full reset clears every saved override (pristine), not a set-each-to-
            # false — so the file holds no stale keys after a reset (QA-001).
            if data.get("reset") is True:
                store = get_settings_store()
                ok = store.clear() if store is not None else False
                payload = settings_response(cfg, saved_settings())
                payload["saved"] = ok
                self._json(200, payload)
                return
            printer_keys = set(cfg.raw.get("printers", {}))
            material_keys = set(cfg.raw.get("materials", {}))
            updates: dict[str, Any] = {}
            if "default_printer" in data:
                dp = data.get("default_printer")
                if dp is not None and dp not in printer_keys:
                    self._json(400, {"error": "Unknown printer."})
                    return
                updates["default_printer"] = dp  # None clears the override (back to config default)
            if "default_material" in data:
                dm = data.get("default_material")
                if dm is not None and dm not in material_keys:
                    self._json(400, {"error": "Unknown material."})
                    return
                updates["default_material"] = dm
            # Slice 6 MS-3 — cloud (OpenRouter) opt-in fields.
            if "cloud_enabled" in data:
                updates["cloud_enabled"] = bool(data.get("cloud_enabled"))
            if "cloud_model" in data:
                cm = data.get("cloud_model")
                if cm is not None and not isinstance(cm, str):
                    self._json(400, {"error": "Invalid model."})
                    return
                # An empty/blank model clears it (back to unconfigured); a string saves it.
                updates["cloud_model"] = cm.strip() if (isinstance(cm, str) and cm.strip()) else None
            if "openrouter_api_key" in data:
                k = data.get("openrouter_api_key")
                if k is not None and not isinstance(k, str):
                    self._json(400, {"error": "Invalid API key."})
                    return
                # A blank/None key clears it; a real key is stored. It's never echoed back.
                updates["openrouter_api_key"] = k.strip() if (isinstance(k, str) and k.strip()) else None
            # Slice 6 MS-4 — the experimental raw-codegen generator toggle (OFF by default).
            if "experimental_enabled" in data:
                updates["experimental_enabled"] = bool(data.get("experimental_enabled"))
            store = get_settings_store()
            if store is None:
                saved_ok = False
            elif updates:
                saved_ok = store.update(updates)
            else:
                saved_ok = True
            payload = settings_response(cfg, saved_settings())
            payload["saved"] = saved_ok
            self._json(200, payload)

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
            resp = {"name": name, "ready": ready, "online": st.online, "state": st.state.value,
                    "detail": st.detail, "simulated": simulated}
            # QA-001/QA-002: a not-ready live snapshot carries a typed `reason` too (not just the
            # build/config branch), so a `reason`-only consumer (agent/MCP/future SPA) sees a
            # uniform contract. The state maps onto the vocabulary; an online-but-faulted printer
            # (incl. a rejected key, which status() reports as `error`) reads as `error` with
            # `detail` naming the cause.
            if not ready:
                resp["reason"] = {
                    "offline": "offline", "printing": "busy", "paused": "busy", "error": "error",
                }.get(st.state.value, "error")
            self._json(200, resp)

        def _handle_send(self, raw_id: str) -> None:
            """Send an already-sliced part (by id) to a configured connector. The POST is
            the explicit per-send confirmation (the user confirmed in the UI)."""
            from kimcad.connectors import build_connector
            from kimcad.printer_connector import ConnectorError

            try:
                rid = int(raw_id)
            except ValueError:
                self._json(404, {"error": "Not found."})
                return
            # ENG-402: read the shared registries together under the lock (consistent snapshot).
            with lock:
                gcode_path = gcode_registry.get(rid)
                gate_failed = gate_status_by_rid.get(rid) == "fail"
            if gcode_path is None or not gcode_path.exists():
                self._json(404, {"error": "Slice the part first, then send it to a printer."})
                return
            # ENG-001: belt-and-suspenders — a gate-FAILED part is never dispatched even if a
            # gcode entry somehow exists (the slice guard above already blocks producing one).
            if gate_failed:
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
            except Exception as e:  # never leak a traceback — the class + message only, no stack
                # QA-003 (re-audit): this last-resort 500 is for a truly UNEXPECTED error (the
                # connectors raise typed ConnectorErrors for the expected cases). Showing the
                # exception class + message (never the stack) is the deliberate, tested contract.
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

        def _handle_photo_seed(self) -> None:
            """Slice 7: read an uploaded photo and return a ROUGH text seed (a description +
            estimated proportions) for the text->DesignPlan path. The photo is read by the LOCAL
            vision model and is NEVER auto-sent off the machine. Best-effort: an unreadable photo or
            a vision failure is a clean 422, never a 500; nothing is persisted."""
            image = self._read_raw_body(MAX_PHOTO_BYTES)
            if image is None:
                return  # _read_raw_body already sent a 413/400
            cant_read = {
                "error": "Couldn’t read that photo — try a clearer shot, or cancel and describe "
                "the part in words."
            }
            try:
                cfg = get_config()
                seed = pipeline.provider.describe_photo(image, cfg.printer(None), cfg.material(None))
            except Exception:  # noqa: BLE001 - never leak a traceback; vision is best-effort
                self._json(422, cant_read)
                return
            seed = (seed or "").strip()
            if not seed:
                self._json(422, cant_read)
                return
            self._json(200, {"seed": seed})

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
            # Stage 8.5 Slice 2: an optional conversation history threads the prior turns into the
            # model so a follow-up ("make it 10mm taller") refines in context. Sanitized + bounded;
            # a malformed history is dropped (the turn just runs standalone), never a 400/500.
            history = _sanitize_history(data.get("history"))
            # Slice 6 MS-4: the experimental raw-codegen generator is OFF for the consumer by
            # default. An ABSENT flag defaults True (backward-compatible for the API / CLI / tests);
            # the consumer SPA always sends `experimental:false` on a normal design (so a template
            # miss OFFERS the generator instead of auto-running it) and `true` only when the user
            # clicks "try the experimental generator". The Settings toggle force-enables it.
            allow_experimental = bool(data.get("experimental", True)) or bool(
                saved_settings().get("experimental_enabled")
            )
            # MS-3: optional client-supplied progress id. When valid, the run reports each phase
            # into design_progress so a parallel poll (GET /api/design/progress/<id>) shows it. The
            # phase callback no-ops when no (valid) job_id was sent, so progress is purely additive.
            job_id = _valid_job_id(data.get("job_id"))

            def _on_phase(phase: str) -> None:
                if job_id is None:
                    return
                with progress_lock:
                    # If the slot was already popped (run finished) this no-ops — a late phase
                    # write can never resurrect a cleaned-up entry.
                    if job_id in design_progress:
                        design_progress[job_id] = phase

            with lock:
                rid = next(counter)
            try:
                # Seed the progress slot INSIDE the try so the finally below ALWAYS clears it (no
                # leak even if the run raises). The pipeline emits "planning" first, so the slot
                # exists before the first _on_phase write.
                if job_id is not None:
                    with progress_lock:
                        design_progress[job_id] = "planning"
                        design_progress.move_to_end(job_id)
                        while len(design_progress) > _MAX_PROGRESS_SLOTS:
                            design_progress.popitem(last=False)
                payload, mesh_path, result = design_response(
                    pipeline, prompt, web_root / str(rid), history=history,
                    allow_experimental=allow_experimental, progress=_on_phase,
                )
            except Exception as e:  # never leak a traceback to the browser
                # Local import: avoids an import cycle (pipeline pulls in webapp helpers elsewhere).
                from kimcad.pipeline import (
                    MODEL_UNAVAILABLE_MESSAGE,
                    PipelineStatus,
                    _is_model_unreachable,
                )

                # Slice 9: an Ollama drop anywhere in the run (the plan step, or codegen past it) is
                # a recoverable model-down state, not a 500. The pipeline propagates the connection
                # error (the caller owns it); the web layer maps it to the typed status the SPA shows.
                if _is_model_unreachable(e):
                    self._json(200, {"status": PipelineStatus.model_unavailable.value,
                                     "error": MODEL_UNAVAILABLE_MESSAGE, "has_mesh": False})
                    return
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            finally:
                # The run is done (success, model-down, or error) — drop the progress slot. A poll
                # racing this gets a null phase; the client's POST has resolved, so it stops polling.
                if job_id is not None:
                    with progress_lock:
                        design_progress.pop(job_id, None)
            if mesh_path is not None:
                with lock:
                    registry[rid] = mesh_path
                    # ENG-001: remember the gate verdict so slice/send can refuse a failed part
                    # (default to "fail" — fail closed — if a report is somehow absent).
                    rep = payload.get("report") or {}
                    gate_status_by_rid[rid] = rep.get("gate_status") or "fail"
                    # Stage 5: register the re-render context for a template-backed part so the
                    # live-slider endpoint can rebuild it deterministically at new values.
                    if result.template is not None:
                        template_state[rid] = (result.plan, result.template.family.name)
                    # Stage 8.5: retain the saveable snapshot so "save to My Designs" needs only
                    # the design id + a name + a thumbnail from the client.
                    design_snapshot[rid] = _design_snapshot(payload, result, prompt)
                    # ENG-004 / QA-003: cap the registry and clean up evicted dirs on disk.
                    while len(registry) > MAX_REGISTRY:
                        old_rid, _ = registry.popitem(last=False)
                        _evict(old_rid)
                payload["mesh_url"] = f"/api/mesh/{rid}"
            self._json(200, payload)

        # --- Stage 8.5: saved designs ("My Designs") --------------------------------------
        def _handle_designs_list(self) -> None:
            store = get_designs_store()
            items = store.list() if store is not None else []
            for it in items:
                it["thumb_url"] = (
                    f"/api/designs/{it['id']}/thumb" if it.get("has_thumb") else None
                )
            self._json(200, {"designs": items})

        def _serve_design_thumb(self, design_id: str) -> None:
            store = get_designs_store()
            path = store.thumb_path(design_id) if store is not None else None
            if path is None or not path.exists():
                self._json(404, {"error": "Not found."})
                return
            try:
                data = path.read_bytes()
            except OSError:  # a concurrent delete/prune between exists() and read() -> 404, not a 500
                self._json(404, {"error": "Not found."})
                return
            self._send(200, data, "image/png")

        def _handle_design_save(self) -> None:
            """Persist the current design to the library. The client sends only the design id (the
            live rid), an optional name, and a viewport thumbnail; the saveable snapshot + mesh are
            already held server-side."""
            data = self._read_json_body()
            if data is None:
                return
            store = get_designs_store()
            if store is None:
                self._json(503, {"error": "Saved designs aren't available right now."})
                return
            try:
                rid = int(data.get("design_id"))
            except (TypeError, ValueError):
                self._json(400, {"error": "Design the part first, then save it."})
                return
            with lock:
                snap = design_snapshot.get(rid)
                mesh_path = registry.get(rid)
            if snap is None or mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "That design is no longer available to save."})
                return
            from kimcad.design_store import clip_name

            # Update-in-place when the client passes a known `saved_id` (so adjusting a part and
            # re-saving keeps one library entry); otherwise reuse the id we minted for this live rid
            # last time (QA-002 — converges rapid auto-saves of one design to a single entry), or
            # mint a fresh one. Preserve the original created_at + name on an update.
            requested = data.get("saved_id")
            existing = store.get(requested) if isinstance(requested, str) else None
            store_id = requested if existing is not None else None
            if store_id is None:
                with lock:
                    prior = rid_saved_id.get(rid)
                    if prior is None:
                        prior = uuid.uuid4().hex
                        rid_saved_id[rid] = prior
                    store_id = prior
                existing = store.get(store_id)  # None on this rid's very first save
            created_at = (
                existing.created_at if existing is not None
                else datetime.now(timezone.utc).isoformat()
            )
            name_raw = data.get("name")
            if isinstance(name_raw, str) and name_raw.strip():
                name = clip_name(name_raw)
            elif existing is not None:
                name = existing.name
            else:
                name = clip_name(snap.get("prompt"))
            ok = store.save(
                design_id=store_id,
                name=name,
                prompt=snap.get("prompt", ""),
                created_at=created_at,
                object_type=snap.get("object_type", ""),
                gate_status=snap.get("gate_status", ""),
                readiness_score=snap.get("readiness_score"),
                template_family=snap.get("template_family"),
                payload=snap.get("payload", {}),
                plan=snap.get("plan"),
                mesh_path=mesh_path,
                thumb_png=_decode_data_url_png(data.get("thumbnail")),
            )
            if not ok:
                # QA-001: a save is best-effort (a transient persistence miss — e.g. a brief
                # Windows file-lock contention the store now retries through — should not look like
                # a server crash). Report it as a soft 503 the SPA can quietly retry, not a hard 500.
                self._json(503, {"error": "Couldn't save right now — your work is still here; retrying.", "saved": False})
                return
            self._json(200, {"id": store_id, "name": name, "saved": True})

        def _handle_design_reopen(self, design_id: str) -> None:
            """Reopen a saved design: re-register it into the live state under a fresh id so the
            mesh serves and (for a template part) the live sliders work again, then return the
            stored API payload pointed at the new mesh url."""
            store = get_designs_store()
            d = store.get(design_id) if store is not None else None
            mesh_src = store.mesh_path(design_id) if store is not None else None
            if d is None or mesh_src is None:
                self._json(404, {"error": "That design couldn't be found."})
                return
            with lock:
                rid = next(counter)
            dest_dir = web_root / str(rid)
            dest_dir.mkdir(parents=True, exist_ok=True)
            mesh_dest = dest_dir / "reopened.stl"
            try:
                shutil.copyfile(mesh_src, mesh_dest)
            except OSError:
                self._json(500, {"error": "Couldn't open that design."})
                return
            with lock:
                registry[rid] = mesh_dest
                gate_status_by_rid[rid] = d.gate_status or "fail"
                if d.template_family and d.plan is not None:
                    try:
                        from kimcad.ir import DesignPlan

                        template_state[rid] = (
                            DesignPlan.model_validate(d.plan),
                            d.template_family,
                        )
                    except Exception:  # noqa: BLE001 - reopen stays view-only if the plan won't restore
                        pass
                design_snapshot[rid] = {
                    "payload": d.payload,
                    "plan": d.plan,
                    "prompt": d.prompt,
                    "object_type": d.object_type,
                    "gate_status": d.gate_status,
                    "readiness_score": d.readiness_score,
                    "template_family": d.template_family,
                }
                while len(registry) > MAX_REGISTRY:
                    old_rid, _ = registry.popitem(last=False)
                    _evict(old_rid)
            payload = dict(d.payload)
            payload["mesh_url"] = f"/api/mesh/{rid}"
            payload["prompt"] = d.prompt
            payload["saved_id"] = design_id  # the SPA knows this is an already-saved design
            self._json(200, payload)

        def _handle_design_mutate(self, design_id: str, verb: str) -> None:
            store = get_designs_store()
            if store is None:
                self._json(503, {"error": "Saved designs aren't available right now."})
                return
            # QA-003: an unsafe or absent id is a 404 (matching reopen/thumb/export), not a
            # 200 {"ok": false} a status-only client would misread as success.
            if store.get(design_id) is None:
                self._json(404, {"error": "That design couldn't be found."})
                return
            if verb == "delete":
                self._json(200, {"ok": store.delete(design_id)})
                return
            if verb == "duplicate":
                new_id = uuid.uuid4().hex
                ok = store.duplicate(design_id, new_id)
                self._json(200 if ok else 500, {"ok": ok, "id": new_id if ok else None})
                return
            # rename
            data = self._read_json_body()
            if data is None:
                return
            name = data.get("name")
            if not isinstance(name, str) or not name.strip():
                self._json(400, {"error": "Give the design a name."})
                return
            self._json(200, {"ok": store.rename(design_id, name)})

        def _serve_design_export(self, design_id: str) -> None:
            store = get_designs_store()
            data = store.export_bytes(design_id) if store is not None else None
            if data is None:
                self._json(404, {"error": "Not found."})
                return
            self._send_download(data, "application/zip", f"kimcad-design-{design_id}.kimcad")

        def _handle_design_import(self) -> None:
            """Import a .kimcad design export (a zip POSTed as the raw body) into a fresh id."""
            store = get_designs_store()
            if store is None:
                self._json(503, {"error": "Saved designs aren't available right now."})
                return
            data = self._read_raw_body(MAX_IMPORT_BYTES)
            if data is None:
                return  # a 413/400 was already sent
            new_id = uuid.uuid4().hex
            if not store.import_bytes(data, new_id):
                self._json(400, {"error": "That file isn't a valid KimCad design export."})
                return
            self._json(200, {"id": new_id})

        def _read_raw_body(self, max_bytes: int) -> bytes | None:
            """Read the raw request body behind a size guard (for a binary import). Returns the
            bytes, or None after sending a 413/400 (mirrors _read_json_body's guard)."""
            raw_len = self.headers.get("Content-Length")
            try:
                declared = int(raw_len) if raw_len is not None else 0
            except (ValueError, TypeError):
                declared = -1
            if declared > max_bytes:
                self.close_connection = True
                self._json(413, {"error": "File too large."})
                return None
            if declared <= 0:
                self._json(400, {"error": "Empty upload."})
                return None
            return self.rfile.read(declared)

        def _respond_slice(self, rid: int, info: dict[str, Any], gcode_path: Path | None) -> None:
            out = dict(info)
            if gcode_path is not None and gcode_path.exists():
                with lock:
                    gcode_registry[rid] = gcode_path
                out["gcode_url"] = f"/api/gcode/{rid}"
                # The on-disk basename of the print file, so the UI can name it and the
                # download lands as a recognizable .gcode.3mf (not an opaque id).
                out["gcode_filename"] = gcode_path.name
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
                self._json(404, {"error": "Not found."})
                return
            # ENG-402: read the shared registries together under the lock (consistent snapshot).
            with lock:
                mesh_path = registry.get(rid)
                gate_failed = gate_status_by_rid.get(rid) == "fail"
            if mesh_path is None or not mesh_path.exists():
                self._json(404, {"error": "Design the part first, then send it to a printer."})
                return
            # ENG-001: a part that FAILED the printability gate is never sliced or sent — mirror
            # the CLI's "download to inspect, never send" stance server-side (not just a hidden UI).
            if gate_failed:
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

        def _handle_render(self, raw_id: str) -> None:
            """Stage 5 live-slider re-render: rebuild a template-backed part (by id) at new
            parameter values — deterministically, with NO model call. The fresh geometry
            replaces the design's mesh and INVALIDATES any cached slice/G-code for it, so a
            stale slice of the previous shape can never be served, sliced, or sent."""
            try:
                rid = int(raw_id)
            except ValueError:
                self._json(404, {"error": "Not found."})
                return
            with lock:
                state = template_state.get(rid)
                known = rid in registry
            if state is None:
                # QA-002: distinguish a genuinely-unknown id from a known LLM-backed design that
                # simply has no template parameters — so an API consumer isn't sent debugging the
                # wrong thing. Both are 404 (no sliders to drive either way).
                if not known:
                    self._json(404, {"error": "Design not found."})
                else:
                    self._json(404, {"error": "This design has no adjustable parameters."})
                return
            data = self._read_json_body()
            if data is None:
                return
            values = data.get("values")
            if not isinstance(values, dict):
                self._json(400, {"error": "Provide the parameter values to re-render."})
                return
            base_plan, family_name = state
            try:
                # RENDER-001: serialize the geometry write so concurrent drags can't corrupt
                # the shared per-design output dir (same discipline as the slice path).
                with render_lock:
                    result = pipeline.rerender(base_plan, family_name, values, web_root / str(rid))
            except Exception as e:  # never leak a traceback to the browser
                self._json(500, {"error": f"{type(e).__name__}: {e}"})
                return
            payload = _result_to_payload(result)
            if result.mesh_path is not None and result.mesh_path.exists():
                with lock:
                    registry[rid] = result.mesh_path
                    registry.move_to_end(rid)  # an actively re-rendered design stays LRU-fresh
                    rep = payload.get("report") or {}
                    gate_status_by_rid[rid] = rep.get("gate_status") or "fail"
                    # Geometry changed: drop any cached slice + G-code for this id so the old
                    # shape can't be downloaded or sent after the part was re-shaped (safety).
                    gcode_registry.pop(rid, None)
                    for k in [k for k in slice_cache if k[0] == rid]:
                        slice_cache.pop(k, None)
                    if result.template is not None:  # refresh the (bbox-aligned) base plan
                        template_state[rid] = (result.plan, result.template.family.name)
                    # Stage 8.5: keep the saveable snapshot current so a save AFTER adjusting
                    # sliders persists the re-rendered parameters (not the original), matching the
                    # fresh mesh. Carry the original prompt from the prior snapshot.
                    prior_prompt = (design_snapshot.get(rid) or {}).get("prompt", "")
                    design_snapshot[rid] = _design_snapshot(payload, result, prior_prompt)
                    # A unique suffix busts the browser's cache so the viewport fetches the new
                    # mesh. Taken under `lock` for consistency with the other counter reads
                    # (ENG-502) — uniqueness is all the cache-buster needs.
                    payload["mesh_url"] = f"/api/mesh/{rid}?v={next(version_counter)}"
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
