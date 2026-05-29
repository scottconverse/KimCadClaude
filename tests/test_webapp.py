"""Offline tests for the Phase-2 web layer.

The HTTP plumbing is thin; the logic worth testing is design_response — the pure
mapping from a PipelineResult to the JSON the page renders. Driven by a fake provider
and a stub renderer, so no LLM, no binary, and no socket are involved.
"""

from pathlib import Path

import trimesh

from kimcad.config import Config, Material, Printer
from kimcad.ir import DesignPlan
from kimcad.openscad_runner import RenderFailed, RenderResult, SanitizeResult
from kimcad.pipeline import Pipeline
from kimcad.webapp import DemoProvider, design_response, make_handler

BAMBU = Printer(key="bambu_p2s", name="Bambu Lab P2S", build_volume=(256, 256, 256), nozzle_diameter=0.4)
PLA = Material(key="pla", name="PLA", nozzle_temp=210, bed_temp=55, wall_multiplier=2.0, shrinkage=0.002)


class FakeProvider:
    def __init__(self, plan, scad="use <library/box.scad>;\nbox(20,20,20);"):
        self._plan = plan
        self._scad = scad

    def generate_design_plan(self, prompt, printer, material, history=None):
        return self._plan

    def generate_openscad(self, plan, printer, material, history=None):
        return self._scad


def _box_renderer(extents, *, fail_times=0):
    state = {"n": 0}

    def render(scad, out_dir: Path, basename: str) -> RenderResult:
        state["n"] += 1
        if state["n"] <= fail_times:
            raise RenderFailed(1, "synthetic render failure")
        path = out_dir / f"{basename}.stl"
        trimesh.creation.box(extents=extents).export(str(path))
        return RenderResult(
            output_path=path, output_format="stl", stdout="", stderr="",
            duration_s=0.01, sanitize=SanitizeResult(code=scad, removed=[]),
        )

    return render


def _plan(bbox, **kw):
    return DesignPlan(object_type="block", summary="a test block", bounding_box_mm=bbox,
                      printer="bambu_p2s", material="pla", **kw)


def _pipeline(provider, renderer, **kw):
    return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **kw)


def test_completed_payload_has_plan_report_and_mesh(tmp_path):
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    payload, mesh_path = design_response(pipe, "a 20mm block", tmp_path)

    assert payload["status"] == "completed"
    assert payload["plan"]["target_bbox_mm"] == [20, 20, 20]
    assert payload["report"]["gate_status"] == "pass"
    assert payload["has_mesh"] is True
    assert mesh_path is not None and mesh_path.exists()
    # every axis reported as an exact match
    assert {d["axis"] for d in payload["report"]["dims"]} == {"X", "Y", "Z"}
    assert all(d["ok"] for d in payload["report"]["dims"])


def test_dim_mismatch_is_reported_per_axis(tmp_path):
    # plan says 50 mm, render is 20 mm -> the axis is flagged not-ok and the gate fails
    pipe = _pipeline(FakeProvider(_plan([50, 50, 50])), _box_renderer((20, 20, 20)))
    payload, mesh_path = design_response(pipe, "a block", tmp_path)

    assert payload["status"] == "gate_failed"
    assert payload["report"]["gate_status"] == "fail"
    assert all(d["ok"] is False for d in payload["report"]["dims"])
    assert any(f["code"] == "dim.mismatch" for f in payload["report"]["findings"])
    assert mesh_path is not None  # a report (and mesh) is still produced for the user


def test_clarification_payload(tmp_path):
    pipe = _pipeline(
        FakeProvider(_plan(None, open_questions=["What overall size?"])),
        _box_renderer((20, 20, 20)),
    )
    payload, mesh_path = design_response(pipe, "a block", tmp_path)

    assert payload["status"] == "clarification_needed"
    assert payload["clarification"] == "What overall size?"
    assert payload["has_mesh"] is False
    assert mesh_path is None


def test_render_failed_payload(tmp_path):
    pipe = _pipeline(
        FakeProvider(_plan([20, 20, 20])),
        _box_renderer((20, 20, 20), fail_times=99),
        max_render_retries=1,
    )
    payload, mesh_path = design_response(pipe, "a block", tmp_path)

    assert payload["status"] == "render_failed"
    assert payload["error"]
    assert payload["has_mesh"] is False
    assert mesh_path is None


def test_demo_provider_returns_plan_and_module_call():
    prov = DemoProvider()
    plan = prov.generate_design_plan("anything", BAMBU, PLA)
    assert plan.bounding_box_mm == [80, 60, 40]
    scad = prov.generate_openscad(plan, BAMBU, PLA)
    assert "snap_box" in scad and "use <library/containers.scad>" in scad


def test_handler_builds_and_index_exists(tmp_path):
    from kimcad.webapp import WEB_DIR

    assert (WEB_DIR / "index.html").exists()
    handler = make_handler(_pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20))), tmp_path)
    assert handler is not None


def test_http_layer_serves_index_design_and_mesh(tmp_path):
    """Exercise the real HTTP routing end to end over an ephemeral port."""
    import json
    import threading
    import urllib.request
    from http.server import ThreadingHTTPServer

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(pipe, tmp_path))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        # GET / -> the page
        html = urllib.request.urlopen(base + "/", timeout=10).read().decode("utf-8")
        assert "<title>KimCad" in html

        # POST /api/design -> a completed result with a mesh URL
        req = urllib.request.Request(
            base + "/api/design",
            data=json.dumps({"prompt": "a 20mm block"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        data = json.load(urllib.request.urlopen(req, timeout=30))
        assert data["status"] == "completed"
        assert data["has_mesh"] and data["mesh_url"]

        # GET the served mesh -> non-empty bytes
        mesh = urllib.request.urlopen(base + data["mesh_url"], timeout=10).read()
        assert len(mesh) > 0

        # unknown route -> 404
        try:
            urllib.request.urlopen(base + "/nope", timeout=10)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
