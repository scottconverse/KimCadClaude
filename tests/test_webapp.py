"""Offline tests for the Phase-2 web layer.

The HTTP plumbing is thin; the logic worth testing is design_response — the pure
mapping from a PipelineResult to the JSON the page renders. Driven by a fake provider
and a stub renderer, so no LLM, no binary, and no socket are involved.
"""

import pytest

from kimcad.config import Config
from kimcad.pipeline import Pipeline
from kimcad.webapp import (
    DemoProvider,
    design_response,
    make_handler,
    slice_registered_mesh,
    web_options,
)

# TEST-007: shared with test_pipeline.py — see tests/conftest.py.
from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer as _shared_box_renderer
from conftest import make_plan as _plan


def _box_renderer(extents, *, fail_times=0):
    # This suite's call sites expect only the render fn (not the (fn, state) tuple
    # the shared helper returns), so unwrap it for an unchanged signature.
    render, _state = _shared_box_renderer(extents, fail_times=fail_times)
    return render


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


# --- webapp hardening (ENG-004 / QA-003 / ENG-010) ----------------------------
#
# These exercise the real HTTP layer over an ephemeral port, like the test above, but
# focus on request-size caps, a malformed Content-Length, and extension-based mesh
# content types.

import contextlib  # noqa: E402
import http.client  # noqa: E402
import threading  # noqa: E402
from http.server import ThreadingHTTPServer  # noqa: E402

from kimcad.webapp import MAX_BODY_BYTES  # noqa: E402


@contextlib.contextmanager
def _serve(pipe, root):
    """Run a handler on an ephemeral port; yield ('127.0.0.1', port)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(pipe, root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post_with_raw_length(host, port, content_length, body=b""):
    """POST /api/design forcing an explicit Content-Length header value (which may be
    oversized or non-numeric), bypassing urllib's automatic length computation."""
    conn = http.client.HTTPConnection(host, port, timeout=10)
    try:
        conn.putrequest("POST", "/api/design", skip_host=False, skip_accept_encoding=True)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(content_length))
        conn.endheaders()
        if body:
            conn.send(body)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def test_oversize_content_length_rejected_with_413(tmp_path):
    """A Content-Length above MAX_BODY_BYTES is rejected up front with 413; the body is
    never read or processed (we send no body at all and still get a clean 413)."""
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        status, body = _post_with_raw_length(host, port, MAX_BODY_BYTES + 1)
    assert status == 413
    assert b"too large" in body.lower()


def test_malformed_content_length_is_clean_400(tmp_path):
    """A non-numeric Content-Length yields a clean 400, not a connection reset or a
    crash on the request thread (QA-003)."""
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        status, body = _post_with_raw_length(host, port, "not-a-number")
    assert status == 400
    assert b"invalid request body" in body.lower()


class _MeshPipeline:
    """A minimal pipeline stand-in whose run() writes a real mesh file with a chosen
    extension and returns a completed PipelineResult pointing at it.

    The real Pipeline always exports the oriented mesh as ``.oriented.stl``, so the
    .3mf branch of _serve_mesh's content-type map can't be reached through it. This
    duck-typed pipeline lets the HTTP layer serve a genuine .3mf (and .stl) so the
    extension -> content-type mapping (ENG-010) is exercised end to end over a socket.
    """

    def __init__(self, suffix: str):
        self._suffix = suffix

    def run(self, prompt, out_dir, **kw):
        import trimesh

        from kimcad.ir import DesignPlan
        from kimcad.pipeline import PipelineStatus, PrintReport

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"part.oriented{self._suffix}"
        trimesh.creation.box(extents=[20, 20, 20]).export(str(path))
        plan = DesignPlan(object_type="block", summary="s", bounding_box_mm=[20, 20, 20])
        report = PrintReport(
            object_type="block", summary="s", printer="P", material="M",
            gate_status="pass", headline="", target_bbox_mm=[20, 20, 20],
            actual_bbox_mm=(20.0, 20.0, 20.0), findings=[], watertight=True,
            repaired=False, repairs=[], n_bodies=1, volume_mm3=8000.0,
            orientation="flat", orientation_stability=1.0, sanitizer_removed=[],
        )
        from kimcad.pipeline import PipelineResult

        return PipelineResult(
            status=PipelineStatus.completed, prompt=prompt, plan=plan,
            report=report, mesh_path=path,
        )


def _design_and_get_content_type(tmp_path, suffix):
    import json
    import urllib.request

    with _serve(_MeshPipeline(suffix), tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        req = urllib.request.Request(
            base + "/api/design",
            data=json.dumps({"prompt": "a part"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        data = json.load(urllib.request.urlopen(req, timeout=30))
        assert data.get("mesh_url"), data
        resp = urllib.request.urlopen(base + data["mesh_url"], timeout=10)
        return resp.headers.get("Content-Type")


def test_mesh_content_type_is_3mf_for_3mf_file(tmp_path):
    """ENG-010: /api/mesh/<id> serves model/3mf when the served file is a .3mf."""
    assert _design_and_get_content_type(tmp_path / "a", ".3mf") == "model/3mf"


def test_mesh_content_type_is_stl_for_stl_file(tmp_path):
    """ENG-010: /api/mesh/<id> serves model/stl when the served file is a .stl."""
    assert _design_and_get_content_type(tmp_path / "b", ".stl") == "model/stl"


def test_serves_vendored_threejs_and_rejects_traversal(tmp_path):
    """QA-006: three.js is vendored locally and served from /vendor/ (offline 3D), and
    the route rejects anything but a plain filename (no path traversal)."""
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        r = urllib.request.urlopen(base + "/vendor/three.min.js", timeout=10)
        assert r.status == 200
        assert "javascript" in r.headers.get("Content-Type", "")
        assert len(r.read()) > 1000
        for bad in ("/vendor/nope.js", "/vendor/", "/vendor/sub/x.js", "/vendor/..%2fx"):
            try:
                urllib.request.urlopen(base + bad, timeout=10)
                raise AssertionError(f"expected 404 for {bad}")
            except urllib.error.HTTPError as e:
                assert e.code == 404


# --- Stage 1 Slice 3b: printer/material selection + slice-on-confirm -----------


def test_web_options_lists_printers_with_sliceable_flag():
    opts = web_options(Config.load())
    by_key = {p["key"]: p for p in opts["printers"]}
    assert by_key["bambu_p2s"]["sliceable"] is True
    assert by_key["bambu_a1"]["sliceable"] is True
    # The Elegoo ships a machine + filament but no process profile -> not yet sliceable.
    assert by_key["elegoo_neptune_4_max"]["sliceable"] is False
    assert any(m["key"] == "pla" for m in opts["materials"])
    assert opts["default_printer"] == "bambu_p2s"
    assert opts["default_material"] == "pla"


def test_slice_registered_mesh_refuses_printer_without_process(tmp_path):
    """Slicing for a printer with no process profile reports a note, not an exception,
    and produces no G-code (the Elegoo case) — deterministic, no binary needed."""
    mesh = tmp_path / "part.oriented.stl"
    mesh.write_bytes(b"solid x\nendsolid x\n")  # never reached; resolution fails first
    info, gcode_path = slice_registered_mesh(
        Config.load(), mesh, "elegoo_neptune_4_max", "pla"
    )
    assert info["sliced"] is False
    assert "process profile" in info["note"]
    assert gcode_path is None


def test_http_options_endpoint_serves_choices(tmp_path):
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        data = json.load(urllib.request.urlopen(f"http://{host}:{port}/api/options", timeout=10))
    assert any(p["key"] == "bambu_p2s" for p in data["printers"])
    assert data["default_material"] == "pla"


def test_http_slice_before_design_is_404(tmp_path):
    import json
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        req = urllib.request.Request(
            f"http://{host}:{port}/api/slice/999",
            data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404


def _binary_and_profiles_present() -> bool:
    try:
        cfg = Config.load()
        return cfg.binary_path("orcaslicer").exists() and cfg.orca_profiles_root().exists()
    except Exception:  # pragma: no cover
        return False


@pytest.mark.skipif(
    not _binary_and_profiles_present(), reason="OrcaSlicer binary/profiles not present"
)
def test_live_web_design_then_slice_then_download(tmp_path):
    """Full web path, live: design a part over HTTP, confirm a slice for P2S + PLA, and
    download the proven G-code 3MF as an attachment."""
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        dreq = urllib.request.Request(
            base + "/api/design",
            data=json.dumps({"prompt": "a 20mm block"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        ddata = json.load(urllib.request.urlopen(dreq, timeout=30))
        rid = ddata["mesh_url"].rsplit("/", 1)[-1]

        sreq = urllib.request.Request(
            base + f"/api/slice/{rid}",
            data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        sdata = json.load(urllib.request.urlopen(sreq, timeout=300))
        assert sdata["sliced"] is True
        assert sdata["gcode_lines"] > 100
        assert sdata["estimate"]  # print estimate surfaced to the UI
        assert sdata["profiles"]["process"] == "0.20mm Standard @BBL P2S"
        gcode_url = sdata["gcode_url"]

        resp = urllib.request.urlopen(base + gcode_url, timeout=30)
        body = resp.read()
        assert len(body) > 1000
        assert "attachment" in resp.headers.get("Content-Disposition", "")
