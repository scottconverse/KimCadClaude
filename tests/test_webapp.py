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
    payload, mesh_path, _ = design_response(pipe, "a 20mm block", tmp_path)

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
    payload, mesh_path, _ = design_response(pipe, "a block", tmp_path)

    assert payload["status"] == "gate_failed"
    assert payload["report"]["gate_status"] == "fail"
    assert all(d["ok"] is False for d in payload["report"]["dims"])
    assert any(f["code"] == "dim.mismatch" for f in payload["report"]["findings"])
    assert mesh_path is not None  # a report (and mesh) is still produced for the user


def test_web_refuses_to_slice_a_gate_failed_part(tmp_path):
    # ENG-001 (Blocker): the web slice endpoint refuses a part that FAILED the printability gate
    # — mirroring the CLI, which already refuses to send one. No G-code is produced, so it can
    # never reach a printer; a direct API client can't dispatch a gate-rejected part. (send() is
    # also guarded server-side as defense-in-depth.)
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([50, 50, 50])), _box_renderer((20, 20, 20)))  # 50 vs 20 = FAIL
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(
            base + "/api/design", data=json.dumps({"prompt": "a block"}).encode(),
            headers={"Content-Type": "application/json"}), timeout=10))
        assert d["status"] == "gate_failed"
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        s = json.load(urllib.request.urlopen(urllib.request.Request(
            base + f"/api/slice/{rid}", data=json.dumps({"printer": "x", "material": "pla"}).encode(),
            headers={"Content-Type": "application/json"}), timeout=10))
    assert s["sliced"] is False and s["reason"] == "gate_failed"
    assert "gcode_url" not in s  # no G-code was produced for the failed part


def test_clarification_payload(tmp_path):
    pipe = _pipeline(
        FakeProvider(_plan(None, open_questions=["What overall size?"])),
        _box_renderer((20, 20, 20)),
    )
    payload, mesh_path, _ = design_response(pipe, "a block", tmp_path)

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
    payload, mesh_path, _ = design_response(pipe, "a block", tmp_path)

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
    assert b"valid json" in body.lower()


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


def _trimesh_can_export_3mf() -> bool:
    """Whether trimesh can export a .3mf in this runtime (it needs a 3MF backend, e.g. lxml).
    Without it, /api/design 500s on the .3mf path; skip cleanly rather than muddy the gate
    (TEST-004). The shipped/pinned venv has it, so the test runs and passes there."""
    import trimesh

    try:
        trimesh.creation.box(extents=[1, 1, 1]).export(file_type="3mf")
        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _trimesh_can_export_3mf(), reason="trimesh 3MF export unavailable in this runtime"
)
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


def test_serves_spa_index_and_assets_and_rejects_traversal(tmp_path):
    """Stage 4: ``/`` serves the built React SPA shell, ``/assets/<file>`` serves its
    compiled JS/CSS bundles with a sensible content type, and the assets route rejects
    anything but a plain filename (no path traversal) — exactly like /vendor/."""
    import re
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        r = urllib.request.urlopen(base + "/", timeout=10)
        assert r.status == 200
        assert "text/html" in r.headers.get("Content-Type", "")
        html = r.read().decode("utf-8")
        assert 'id="root"' in html
        # Every /assets/ bundle the shell references is served with the right content type.
        refs = re.findall(r'(?:src|href)="/assets/([^"]+)"', html)
        assert refs, "the served shell should reference at least one /assets/ bundle"
        seen_js = seen_css = False
        for name in refs:
            ar = urllib.request.urlopen(base + "/assets/" + name, timeout=10)
            assert ar.status == 200
            ctype = ar.headers.get("Content-Type", "")
            assert len(ar.read()) > 0
            if name.endswith(".js"):
                assert "javascript" in ctype
                seen_js = True
            elif name.endswith(".css"):
                assert "text/css" in ctype
                seen_css = True
        assert seen_js and seen_css, "shell should load both a JS bundle and a stylesheet"
        for bad in ("/assets/nope.js", "/assets/", "/assets/sub/x.js", "/assets/..%2fx"):
            try:
                urllib.request.urlopen(base + bad, timeout=10)
                raise AssertionError(f"expected 404 for {bad}")
            except urllib.error.HTTPError as e:
                assert e.code == 404


# --- Stage 1 Slice 3b: printer/material selection + slice-on-confirm -----------


def test_web_options_lists_printers_with_sliceable_flag():
    opts = web_options(Config.load())
    by_key = {p["key"]: p for p in opts["printers"]}
    # All three of Kim's printers ship machine + process + filament profiles.
    assert by_key["bambu_p2s"]["sliceable"] is True
    assert by_key["bambu_a1"]["sliceable"] is True
    assert by_key["elegoo_neptune_4_max"]["sliceable"] is True
    assert any(m["key"] == "pla" for m in opts["materials"])
    assert opts["default_printer"] == "bambu_p2s"
    assert opts["default_material"] == "pla"


def test_web_options_lists_per_printer_available_materials():
    # Each printer advertises only the materials it can actually print, so the UI offers
    # exactly those — the Elegoo Neptune 4 Max has no TPU profile, so TPU isn't listed for it.
    opts = web_options(Config.load())
    by_key = {p["key"]: p for p in opts["printers"]}
    assert set(by_key["bambu_p2s"]["materials"]) == {"pla", "petg", "tpu", "abs"}
    assert set(by_key["bambu_a1"]["materials"]) == {"pla", "petg", "tpu", "abs"}
    assert set(by_key["elegoo_neptune_4_max"]["materials"]) == {"pla", "petg", "abs"}
    assert "tpu" not in by_key["elegoo_neptune_4_max"]["materials"]


class _NoProcessConfig:
    """A config stand-in whose printer has no process profile, to drive the web-layer
    refusal path without depending on a specific shipped printer."""

    def printer(self, key):
        from kimcad.config import Printer

        return Printer(
            key="noproc", name="No-Process Printer", build_volume=(200, 200, 200),
            nozzle_diameter=0.4, orca_machine_profile="M", orca_process_profile=None,
        )

    def material(self, key):
        return Config.load().material("pla")

    def orca_profiles_root(self):
        from pathlib import Path

        return Path(".")


def test_slice_registered_mesh_refuses_printer_without_process(tmp_path):
    """The web-layer refusal: a printer with no process profile reports a note (reason
    no_profile), not an exception, and produces no G-code — deterministic, no binary."""
    mesh = tmp_path / "part.oriented.stl"
    mesh.write_bytes(b"solid x\nendsolid x\n")  # never reached; resolution fails first
    info, gcode_path = slice_registered_mesh(_NoProcessConfig(), mesh, "noproc", "pla")
    assert info["sliced"] is False
    assert info["reason"] == "no_profile"  # ENG-008: capability gap, not a failure
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


@pytest.mark.live  # TEST-008: invokes the real OrcaSlicer; `pytest -m "not live"` skips it
@pytest.mark.skipif(
    not _binary_and_profiles_present(), reason="OrcaSlicer binary/profiles not present"
)
def test_live_web_design_then_slice_then_download(tmp_path, monkeypatch):
    """Full web path, live: design a part over HTTP, confirm a slice for P2S + PLA,
    download the proven G-code 3MF, then send it to the mock connector (+ error branches)."""
    import json
    import urllib.error
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

        # ENG-003: an identical re-confirm is served from cache, same proven result.
        sdata2 = json.load(urllib.request.urlopen(
            urllib.request.Request(
                base + f"/api/slice/{rid}",
                data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=30,
        ))
        assert sdata2["gcode_lines"] == sdata["gcode_lines"]
        assert sdata2["gcode_url"] == gcode_url

        resp = urllib.request.urlopen(base + gcode_url, timeout=30)
        body = resp.read()
        assert len(body) > 1000
        assert "attachment" in resp.headers.get("Content-Disposition", "")

        # Stage 2: send the sliced job to the built-in "mock" connector.
        send = json.load(urllib.request.urlopen(urllib.request.Request(
            base + f"/api/send/{rid}",
            data=json.dumps({"connector": "mock"}).encode(),
            headers={"Content-Type": "application/json"},
        ), timeout=30))
        assert send["sent"] is True
        assert send["connector"] == "mock" and send["job_id"]
        assert send["simulated"] is True  # UX-001: the mock is a simulation, flagged as such
        assert send.get("printer_state")  # status flows through

        # an unknown connector is a soft "not sent" (the download still works), not a 5xx, and
        # carries a typed reason + a user-facing note. An unknown NAME is reason="unknown"
        # (distinct from a misconfigured "config"), and the soft failure mirrors the status
        # contract's `simulated` field (QA-003 / ENG-002).
        bad = json.load(urllib.request.urlopen(urllib.request.Request(
            base + f"/api/send/{rid}",
            data=json.dumps({"connector": "no_such"}).encode(),
            headers={"Content-Type": "application/json"},
        ), timeout=30))
        assert bad["sent"] is False and bad["note"]
        assert bad["reason"] == "unknown"
        assert bad["simulated"] is False

        # TEST-001: the POST is the confirmation; a body "confirm" field must NOT be able to
        # downgrade the gate. Pin that the web path always calls send(confirm is True), even
        # when the body says confirm=false. (If a body confirm is ever wired in, this trips.)
        import kimcad.connectors as conn_mod
        from kimcad.printer_connector import JobState, PrinterState, PrinterStatus, PrintJob

        seen: dict[str, object] = {}

        class _Recorder:
            name = "rec"
            drives_hardware = True

            def send(self, gcode, *, confirm, job_name=None):
                seen["confirm"] = confirm
                return PrintJob("r1", JobState.printing)

            def status(self):
                return PrinterStatus(online=True, state=PrinterState.operational)

        monkeypatch.setattr(conn_mod, "build_connector", lambda c, n: _Recorder())
        json.load(urllib.request.urlopen(urllib.request.Request(
            base + f"/api/send/{rid}",
            data=json.dumps({"connector": "mock", "confirm": False}).encode(),
            headers={"Content-Type": "application/json"},
        ), timeout=30))
        assert seen["confirm"] is True  # identity True, regardless of the body's confirm

        # no connector chosen -> clean 400
        try:
            urllib.request.urlopen(urllib.request.Request(
                base + f"/api/send/{rid}", data=b"{}",
                headers={"Content-Type": "application/json"},
            ), timeout=10)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400

        # a status() error after a successful send still reports sent=True (status guarded)
        from kimcad.printer_connector import ConnectorError

        class _StatusBoom:
            name = "boom"

            def send(self, gcode, *, confirm, job_name=None):
                return PrintJob("j1", JobState.printing)

            def status(self):
                raise ConnectorError("status link down")

        monkeypatch.setattr(conn_mod, "build_connector", lambda c, n: _StatusBoom())
        ok = json.load(urllib.request.urlopen(urllib.request.Request(
            base + f"/api/send/{rid}",
            data=json.dumps({"connector": "mock"}).encode(),
            headers={"Content-Type": "application/json"},
        ), timeout=30))
        assert ok["sent"] is True and ok.get("printer_state") is None

        # an unexpected (non-ConnectorError) failure -> clean 500, no traceback leaked
        def _boom(c, n):
            raise RuntimeError("kaboom")

        monkeypatch.setattr(conn_mod, "build_connector", _boom)
        try:
            urllib.request.urlopen(urllib.request.Request(
                base + f"/api/send/{rid}",
                data=json.dumps({"connector": "mock"}).encode(),
                headers={"Content-Type": "application/json"},
            ), timeout=10)
            raise AssertionError("expected 500")
        except urllib.error.HTTPError as e:
            assert e.code == 500
            body = e.read()
            assert b"RuntimeError: kaboom" in body and b"Traceback" not in body


# --- Stage 2 Slice 4b: send-to-printer web endpoints --------------------------


def test_connectors_endpoint_lists_configured_connectors(tmp_path):
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        data = json.load(urllib.request.urlopen(f"http://{host}:{port}/api/connectors", timeout=10))
    # Each entry is {name, simulated} so the UI can label a no-hardware connection honestly.
    by_name = {c["name"]: c for c in data["connectors"]}
    assert "mock" in by_name
    assert by_name["mock"]["simulated"] is True  # the loopback is a simulation
    if "octoprint" in by_name:
        assert by_name["octoprint"]["simulated"] is False  # a real connector
    assert data["default"] is not None


def test_connector_status_mock_is_ready(tmp_path):
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        d = json.load(urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/mock", timeout=10))
    assert d["ready"] is True and d["online"] is True
    assert d["state"] == "operational" and d["simulated"] is True


def test_connector_status_missing_key_is_needs_setup(tmp_path, monkeypatch):
    # The shipped octoprint connector needs OCTOPRINT_API_KEY; unset -> a "needs setup"
    # status (reason=config), never a 5xx.
    import json
    import urllib.request

    monkeypatch.delenv("OCTOPRINT_API_KEY", raising=False)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        d = json.load(urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/octoprint", timeout=10))
    assert d["ready"] is False and d["reason"] == "config" and d["note"]


def test_connector_status_offline_printer_is_not_ready(tmp_path, monkeypatch):
    import json
    import urllib.request

    import kimcad.connectors as conn_mod
    from kimcad.printer_connector import LoopbackConnector

    # A reachable connector whose printer is offline -> ready False, state offline (not a 5xx).
    monkeypatch.setattr(conn_mod, "build_connector", lambda c, n: LoopbackConnector(online=False))
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        d = json.load(urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/mock", timeout=10))
    assert d["ready"] is False and d["online"] is False and d["state"] == "offline"


def test_connector_status_unknown_name_is_typed_unknown(tmp_path):
    # QA-003: an unknown connection name reports a distinct reason="unknown" (not "config"), so
    # the UI can tell a typo'd name from a genuine "needs setup". ENG-003/QA-002: every branch
    # of the endpoint carries the `simulated` field (no UI fall-through).
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        d = json.load(urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/bogus", timeout=10))
    assert d["ready"] is False and d["reason"] == "unknown"
    assert d["simulated"] is False


# --- TEST-003 / ENG-002: /api/send soft-failures are symmetric with /api/connector-status ----


def _register_stub_gcode(host, port, monkeypatch, gcode_path):
    """Design a part over HTTP, then register a stub sliced G-code for it WITHOUT running the
    real slicer (monkeypatching slice_registered_mesh), so send-path tests are fast + offline.
    Unknown/config sends fail at build_connector and a stubbed loopback send never reaches
    ensure_sendable, so the registered file only needs to exist. Returns (base_url, rid)."""
    import json
    import urllib.request

    monkeypatch.setattr(
        "kimcad.webapp.slice_registered_mesh",
        lambda cfg, mesh, printer, material: ({}, gcode_path),
    )
    base = f"http://{host}:{port}"
    d = json.load(urllib.request.urlopen(urllib.request.Request(
        base + "/api/design", data=json.dumps({"prompt": "a 20mm block"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=10))
    rid = int(d["mesh_url"].rsplit("/", 1)[-1])
    s = json.load(urllib.request.urlopen(urllib.request.Request(
        base + f"/api/slice/{rid}", data=json.dumps({"printer": "x", "material": "pla"}).encode(),
        headers={"Content-Type": "application/json"}), timeout=10))
    assert "gcode_url" in s  # the stub slice registered the G-code
    return base, rid


def _post_send(base, rid, connector):
    import json
    import urllib.request

    return json.load(urllib.request.urlopen(urllib.request.Request(
        base + f"/api/send/{rid}", data=json.dumps({"connector": connector}).encode(),
        headers={"Content-Type": "application/json"}), timeout=10))


def test_send_unknown_connector_is_typed_unknown_not_simulated(tmp_path, monkeypatch):
    g = tmp_path / "g.gcode.3mf"
    g.write_bytes(b"stub")
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base, rid = _register_stub_gcode(host, port, monkeypatch, g)
        bad = _post_send(base, rid, "no_such")
    assert bad["sent"] is False and bad["reason"] == "unknown"
    assert bad["simulated"] is False and bad["note"]


def test_send_simulated_connector_failure_carries_simulated_true(tmp_path, monkeypatch):
    # ENG-002: a failed send to a SIMULATED connector reports simulated=True, symmetric with
    # status — the asymmetry that let the stale live send assertion hide.
    from kimcad.printer_connector import LoopbackConnector, PrinterOffline

    def _boom(self, gcode_path, *, confirm, job_name=None):
        raise PrinterOffline("mock offline", user_message="The mock connection is offline.")

    monkeypatch.setattr(LoopbackConnector, "send", _boom)
    g = tmp_path / "g.gcode.3mf"
    g.write_bytes(b"stub")
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base, rid = _register_stub_gcode(host, port, monkeypatch, g)
        res = _post_send(base, rid, "mock")
    assert res["sent"] is False and res["reason"] == "offline"
    assert res["simulated"] is True and res["note"]


def test_connector_status_busy_is_online_but_not_ready(tmp_path, monkeypatch):
    import json
    import urllib.request

    import kimcad.connectors as conn_mod
    from kimcad.printer_connector import PrinterState, PrinterStatus

    class _Busy:
        name = "busy"
        drives_hardware = True

        def status(self):
            return PrinterStatus(online=True, state=PrinterState.printing)

    monkeypatch.setattr(conn_mod, "build_connector", lambda c, n: _Busy())
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        d = json.load(urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/mock", timeout=10))
    # online + busy (printing) is NOT ready, but IS online — distinct states.
    assert d["online"] is True and d["ready"] is False and d["state"] == "printing"


def test_connector_status_unexpected_error_is_not_5xx(tmp_path, monkeypatch):
    # A non-ConnectorError failure building/reading a connection is a graceful "error" status,
    # never a 5xx/dropped connection — and the dev detail isn't leaked into the payload.
    import json
    import urllib.request

    import kimcad.connectors as conn_mod

    def _boom(c, n):
        raise RuntimeError("kaboom-secret")

    monkeypatch.setattr(conn_mod, "build_connector", _boom)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        resp = urllib.request.urlopen(
            f"http://{host}:{port}/api/connector-status/mock", timeout=10)
        assert resp.status == 200
        d = json.load(resp)
    assert d["ready"] is False and d["reason"] == "error"
    assert "kaboom-secret" not in json.dumps(d)


def test_send_before_slice_is_404(tmp_path):
    import json
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        req = urllib.request.Request(
            f"http://{host}:{port}/api/send/999",
            data=json.dumps({"connector": "mock"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected 404")
        except urllib.error.HTTPError as e:
            assert e.code == 404


# --- Stage-gate fixes: web error-handling + resource hardening ----------------


def test_non_dict_json_body_is_clean_400(tmp_path):
    """QA-001: a valid-JSON but non-object body must yield a clean 400, not an empty
    response from an uncaught AttributeError."""
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        status, body = _post_with_raw_length(host, port, len(b"[1,2,3]"), body=b"[1,2,3]")
    assert status == 400
    assert b"json object" in body.lower()


def test_non_string_prompt_is_400(tmp_path):
    """QA-007: a wrong-typed prompt is rejected, not silently str()-coerced."""
    import json
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        req = urllib.request.Request(
            f"http://{host}:{port}/api/design",
            data=json.dumps({"prompt": 12345}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400


def test_unknown_printer_key_is_400(tmp_path):
    """TEST-004: slicing with a printer key the config doesn't know is a clean 400."""
    import json
    import urllib.error
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        ddata = json.load(urllib.request.urlopen(
            urllib.request.Request(
                base + "/api/design",
                data=json.dumps({"prompt": "a box"}).encode(),
                headers={"Content-Type": "application/json"},
            ), timeout=30))
        rid = ddata["mesh_url"].rsplit("/", 1)[-1]
        try:
            urllib.request.urlopen(urllib.request.Request(
                base + f"/api/slice/{rid}",
                data=json.dumps({"printer": "no_such_printer", "material": "pla"}).encode(),
                headers={"Content-Type": "application/json"},
            ), timeout=10)
            raise AssertionError("expected 400")
        except urllib.error.HTTPError as e:
            assert e.code == 400
            assert b"Unknown printer or material" in e.read()


def test_unexpected_pipeline_error_is_clean_500_no_traceback(tmp_path):
    """TEST-008: an unexpected exception in the pipeline surfaces as a 500 with the error
    class but no stack trace leaked to the browser."""
    import json
    import urllib.error
    import urllib.request

    class _Boom:
        def run(self, prompt, out_dir, **kw):
            raise RuntimeError("boom")

    with _serve(_Boom(), tmp_path) as (host, port):
        req = urllib.request.Request(
            f"http://{host}:{port}/api/design",
            data=json.dumps({"prompt": "a box"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=10)
            raise AssertionError("expected 500")
        except urllib.error.HTTPError as e:
            assert e.code == 500
            body = e.read()
            assert b"RuntimeError: boom" in body
            assert b"Traceback" not in body


def test_unsupported_method_is_405(tmp_path):
    """QA-005: an unsupported verb on an existing resource is 405, not 501."""
    import http.client

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("PUT", "/api/design")
            resp = conn.getresponse()
            assert resp.status == 405
            assert "GET" in (resp.getheader("Allow") or "")
        finally:
            conn.close()


def test_head_returns_headers_without_body(tmp_path):
    """QA-001: HEAD on a GET resource returns a header-only 200 (not 405) — same status +
    Content-Length as GET, with no body."""
    import http.client

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("HEAD", "/")
            resp = conn.getresponse()
            assert resp.status == 200
            assert resp.getheader("Content-Type", "").startswith("text/html")
            assert int(resp.getheader("Content-Length")) > 0
            assert resp.read() == b""  # HEAD carries no body
        finally:
            conn.close()


def test_static_assets_carry_an_etag_and_revalidate_304(tmp_path):
    """QA-002: static assets (vendor/assets) carry an ETag; a matching If-None-Match gets a
    body-less 304 (correct revalidation for the build's stable, un-hashed filenames)."""
    import http.client

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        conn = http.client.HTTPConnection(host, port, timeout=10)
        try:
            conn.request("GET", "/vendor/three.min.js")
            resp = conn.getresponse()
            etag = resp.getheader("ETag")
            resp.read()
            assert etag, "a static asset should carry an ETag"
            conn.request("GET", "/vendor/three.min.js", headers={"If-None-Match": etag})
            resp2 = conn.getresponse()
            assert resp2.status == 304
            assert resp2.read() == b""
        finally:
            conn.close()


def test_evicted_design_dir_is_removed_from_disk(tmp_path, monkeypatch):
    """QA-003: past the registry cap, an evicted design's on-disk directory is removed."""
    import json
    import urllib.request

    import kimcad.webapp as webapp_mod

    monkeypatch.setattr(webapp_mod, "MAX_REGISTRY", 2)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        for _ in range(3):  # cap is 2 -> the first design's dir is evicted
            urllib.request.urlopen(
                urllib.request.Request(
                    base + "/api/design",
                    data=json.dumps({"prompt": "a box"}).encode(),
                    headers={"Content-Type": "application/json"},
                ), timeout=30)
    assert not (tmp_path / "1").exists()  # evicted dir cleaned up
    assert (tmp_path / "3").exists()      # newest survives


def _design_rid(base):
    import json
    import urllib.request

    ddata = json.load(urllib.request.urlopen(
        urllib.request.Request(
            base + "/api/design",
            data=json.dumps({"prompt": "a box"}).encode(),
            headers={"Content-Type": "application/json"},
        ), timeout=30))
    return ddata["mesh_url"].rsplit("/", 1)[-1]


def test_slice_is_idempotent_one_real_slice_per_key(tmp_path, monkeypatch):
    """NEW-1 (ENG-003 proof): an identical (rid, printer, material) re-confirm must hit
    the cache, NOT re-run the slicer. Driven by a counting fake so a cache miss is
    observable (the prior live test couldn't distinguish a hit from a second slice)."""
    import json
    import urllib.request

    import kimcad.webapp as webapp_mod

    calls = {"n": 0}

    def counting_slice(config, mesh_path, printer, material):
        calls["n"] += 1
        gp = mesh_path.parent / f"{mesh_path.name.split('.')[0]}_{printer}_{material}.gcode.3mf"
        gp.write_bytes(b"PKfake")
        return (
            {"sliced": True, "printer": printer, "material": material, "gcode_lines": 5,
             "estimate": "", "profiles": {"machine": "m", "process": "p", "filament": "f"}},
            gp,
        )

    monkeypatch.setattr(webapp_mod, "slice_registered_mesh", counting_slice)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        rid = _design_rid(base)

        def slice_once():
            return json.load(urllib.request.urlopen(
                urllib.request.Request(
                    base + f"/api/slice/{rid}",
                    data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
                    headers={"Content-Type": "application/json"},
                ), timeout=30))

        d1 = slice_once()
        d2 = slice_once()
    assert calls["n"] == 1  # the second identical request was served from cache
    assert d1["gcode_url"] == d2["gcode_url"]


def test_slice_unexpected_error_is_clean_500(tmp_path, monkeypatch):
    """NEW-4: the slice-side except-Exception guard returns a clean 500 (no traceback)."""
    import json
    import urllib.error
    import urllib.request

    import kimcad.webapp as webapp_mod

    def boom(*args, **kwargs):
        raise RuntimeError("slice boom")

    monkeypatch.setattr(webapp_mod, "slice_registered_mesh", boom)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        rid = _design_rid(base)
        try:
            urllib.request.urlopen(urllib.request.Request(
                base + f"/api/slice/{rid}",
                data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
                headers={"Content-Type": "application/json"},
            ), timeout=10)
            raise AssertionError("expected 500")
        except urllib.error.HTTPError as e:
            assert e.code == 500
            body = e.read()
            assert b"RuntimeError: slice boom" in body
            assert b"Traceback" not in body


def test_handler_has_read_timeout(tmp_path):
    """NEW-2: the handler sets a socket read timeout (QA-002 slowloris guard)."""
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    handler_cls = make_handler(pipe, tmp_path)
    assert handler_cls.timeout == 30


def test_concurrent_identical_slices_run_once(tmp_path, monkeypatch):
    """The slice_lock double-checked re-check: while one request is mid-slice (holding the
    lock), a second identical request blocks, then on acquiring the lock finds the cache
    already populated and reuses it — so the slicer runs exactly once. Exercises the
    re-check branch that the sequential idempotency test can't reach."""
    import json
    import threading
    import urllib.request

    import kimcad.webapp as webapp_mod

    in_slice = threading.Event()
    release = threading.Event()
    calls = {"n": 0}

    def slow_slice(config, mesh_path, printer, material):
        calls["n"] += 1
        in_slice.set()
        release.wait(timeout=10)  # hold slice_lock until the test releases
        gp = mesh_path.parent / f"x_{printer}_{material}.gcode.3mf"
        gp.write_bytes(b"PK")
        return ({"sliced": True, "printer": printer, "material": material}, gp)

    monkeypatch.setattr(webapp_mod, "slice_registered_mesh", slow_slice)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        rid = _design_rid(base)

        def post_slice(out):
            out.append(json.load(urllib.request.urlopen(
                urllib.request.Request(
                    base + f"/api/slice/{rid}",
                    data=json.dumps({"printer": "bambu_p2s", "material": "pla"}).encode(),
                    headers={"Content-Type": "application/json"},
                ), timeout=15)))

        r1, r2 = [], []
        t1 = threading.Thread(target=post_slice, args=(r1,))
        t1.start()
        assert in_slice.wait(timeout=10)  # t1 is inside the slice, holding slice_lock
        t2 = threading.Thread(target=post_slice, args=(r2,))
        t2.start()
        # TEST-007: t2 should reach slice_lock and block on it before we release t1, so the
        # under-lock re-check branch (not the pre-lock cache hit) serves it. There is no public
        # "blocked on a lock" hook, so we settle briefly. This is a deliberately accepted, bounded
        # risk: if the settle is too short on a heavily loaded runner, t2 instead takes the
        # pre-lock cache-hit path — still correct behavior (calls stays 1, urls match), just a
        # different valid branch. The test can therefore only under-cover, never flaky-FAIL.
        import time
        time.sleep(0.5)
        release.set()
        t1.join(timeout=15)
        t2.join(timeout=15)
    assert calls["n"] == 1  # t2 reused t1's cached slice via the re-check branch
    assert r1 and r2 and r1[0]["gcode_url"] == r2[0]["gcode_url"]


# --- Stage 5: template parameters on /api/design + the live-slider re-render endpoint -----

import json as _json  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request as _urlreq  # noqa: E402

from kimcad.ir import DesignPlan  # noqa: E402


def _box_plan(**dims) -> DesignPlan:
    return DesignPlan(
        object_type="box", summary="a box",
        dimensions=dims or {"width": 80, "depth": 60, "height": 40, "wall": 2},
        printer="bambu_p2s", material="pla",
    )


def _req_json(host, port, method, path, obj=None):
    """Issue a JSON request; return (status, parsed_body), reading the body even on 4xx/5xx."""
    body = _json.dumps(obj).encode() if obj is not None else None
    req = _urlreq.Request(
        f"http://{host}:{port}{path}", data=body, method=method,
        headers={"Content-Type": "application/json"} if body is not None else {})
    try:
        with _urlreq.urlopen(req, timeout=20) as r:
            return r.status, _json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, _json.load(e)


def test_design_payload_exposes_template_parameters(tmp_path):
    # A template-covered object_type (a "box") returns the typed slider snapshot the UI binds to.
    pipe = _pipeline(FakeProvider(_box_plan()), _box_renderer((80, 60, 40)))
    payload, mesh_path, result = design_response(pipe, "a box", tmp_path)
    assert payload["status"] == "completed"
    assert payload["template"] == "snap_box"
    params = {p["name"]: p for p in payload["parameters"]}
    assert set(params) == {"width", "depth", "height", "wall"}
    assert params["width"]["value"] == 80
    assert params["width"]["min"] <= params["width"]["value"] <= params["width"]["max"]
    assert params["wall"]["step"] == 0.2 and params["wall"]["unit"] == "mm"
    assert result.template is not None
    assert mesh_path is not None


def test_llm_design_payload_has_no_parameters(tmp_path):
    # An LLM-backed part (an object_type the registry doesn't cover) has no adjustable params.
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    payload, _mesh, result = design_response(pipe, "a block", tmp_path)
    assert "template" not in payload and "parameters" not in payload
    assert result.template is None


def test_render_endpoint_rejects_non_template_design(tmp_path):
    # An LLM-backed design id has no re-render context -> 404 (there are no sliders to drive).
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a block"})
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        status, body = _req_json(host, port, "POST", f"/api/render/{rid}", {"values": {"width": 50}})
    assert status == 404
    assert "no adjustable parameters" in body["error"]


def test_render_endpoint_rejects_bad_values(tmp_path):
    # A template-backed design, but a malformed body (no/non-dict "values") -> clean 400.
    pipe = _pipeline(FakeProvider(_box_plan()), _box_renderer((80, 60, 40)))
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a box"})
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        status, body = _req_json(host, port, "POST", f"/api/render/{rid}", {"nope": 1})
    assert status == 400
    assert "parameter values" in body["error"]


def test_render_endpoint_unknown_id_is_design_not_found(tmp_path):
    # QA-002 / TEST-006: a genuinely-unknown id is "Design not found.", distinct from a known
    # LLM-backed id ("no adjustable parameters", above) — so an API consumer can tell them apart.
    pipe = _pipeline(FakeProvider(_box_plan()), _box_renderer((80, 60, 40)))
    with _serve(pipe, tmp_path) as (host, port):
        status, body = _req_json(host, port, "POST", "/api/render/999999", {"values": {"width": 50}})
    assert status == 404
    assert "not found" in body["error"].lower()
    assert "no adjustable parameters" not in body["error"]


def test_rerender_into_a_gate_failed_shape_blocks_slice_and_send(tmp_path, monkeypatch):
    # TEST-001 — the live-slider feature's single most important safety property: a part that
    # PASSES the gate, gets sliced, then is re-rendered into a gate-FAILING shape must become both
    # non-sliceable AND non-sendable, so the old good G-code can never ship. The stub renderer is
    # fixed at 80x60x40, so the defaults pass but a width=120 re-render (expected_bbox X=120 vs the
    # rendered 80) trips dim.mismatch -> gate FAIL. No binary needed.
    import kimcad.webapp as webapp_mod

    def _fake_slice(config, mesh_path, printer, material):
        gp = mesh_path.parent / "part.gcode.3mf"
        gp.write_bytes(b"PK\x03\x04")
        return {"sliced": True}, gp

    monkeypatch.setattr(webapp_mod, "slice_registered_mesh", _fake_slice)
    pipe = _pipeline(FakeProvider(_box_plan()), _box_renderer((80, 60, 40)))
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a box"})
        assert d["report"]["gate_status"] == "pass"
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        # The passing part slices fine.
        _s, s1 = _req_json(host, port, "POST", f"/api/slice/{rid}",
                           {"printer": "bambu_p2s", "material": "pla"})
        assert s1.get("gcode_url"), "the passing part should slice"
        # Re-render into a gate-FAILING shape (expects width 120, the stub still renders 80).
        _s, r = _req_json(host, port, "POST", f"/api/render/{rid}",
                          {"values": {"width": 120, "depth": 60, "height": 40, "wall": 2}})
        assert r["report"]["gate_status"] == "fail", "the re-rendered shape must fail the gate"
        # The stale slice is gone, and the now-invalid part can be neither sliced nor sent.
        s_gcode, _ = _req_json(host, port, "GET", f"/api/gcode/{rid}", None)
        assert s_gcode == 404, "the stale slice must be invalidated"
        _s, s2 = _req_json(host, port, "POST", f"/api/slice/{rid}",
                           {"printer": "bambu_p2s", "material": "pla"})
        assert s2["sliced"] is False and s2["reason"] == "gate_failed"
        assert "gcode_url" not in s2
        # And it can't be SENT: the re-render dropped the slice, so send refuses (whether via the
        # "slice first" 404 or the gate-fail branch — either way `sent` is never True).
        _s, snd = _req_json(host, port, "POST", f"/api/send/{rid}", {"connector": "mock"})
        assert snd.get("sent") is not True, "a gate-failed re-rendered part must not be sendable"


def _openscad_present() -> bool:
    try:
        return Config.load().binary_path("openscad").exists()
    except Exception:
        return False


@pytest.mark.skipif(not _openscad_present(), reason="OpenSCAD binary not fetched")
def test_render_endpoint_reshapes_a_template_part_without_the_model(tmp_path):
    # End-to-end over a socket with the REAL renderer: design a box, then drag it bigger via
    # /api/render — deterministically (no model call), getting a fresh fetchable mesh at the new size.
    prov = FakeProvider(_box_plan(width=80, depth=60, height=40, wall=2))
    pipe = Pipeline(Config.load(), BAMBU, PLA, prov)  # real OpenSCAD renderer (no override)
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a box"})
        assert d["template"] == "snap_box" and "parameters" in d
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        x0 = next(dim["actual"] for dim in d["report"]["dims"] if dim["axis"] == "X")
        assert abs(x0 - 80) <= 0.1

        status, r = _req_json(host, port, "POST", f"/api/render/{rid}",
                              {"values": {"width": 120, "depth": 90, "height": 60, "wall": 3}})
        assert status == 200 and r["status"] == "completed"
        x1 = next(dim["actual"] for dim in r["report"]["dims"] if dim["axis"] == "X")
        assert abs(x1 - 120) <= 0.1, f"re-render should reshape to width 120, got {x1}"
        assert r["template"] == "snap_box"
        mreq = _urlreq.urlopen(f"http://{host}:{port}{r['mesh_url']}", timeout=20)
        assert mreq.status == 200 and len(mreq.read()) > 0
    assert prov.openscad_calls == 0  # the deterministic path never called the model


@pytest.mark.skipif(not _openscad_present(), reason="OpenSCAD binary not fetched")
def test_rerender_invalidates_a_cached_slice(tmp_path, monkeypatch):
    # Safety: after a part is re-shaped, a previously cached slice for it is dropped so the OLD
    # geometry can't be sliced/sent. The slicer is stubbed (module-level slice_registered_mesh)
    # to avoid the multi-minute real slice; the real renderer still drives the geometry change.
    import kimcad.webapp as webapp_mod
    calls = {"n": 0}

    def _fake_slice(config, mesh_path, printer, material):
        calls["n"] += 1
        gp = mesh_path.parent / "part.gcode.3mf"
        gp.write_bytes(b"PK\x03\x04")
        return {"sliced": True}, gp

    monkeypatch.setattr(webapp_mod, "slice_registered_mesh", _fake_slice)
    prov = FakeProvider(_box_plan())
    pipe = Pipeline(Config.load(), BAMBU, PLA, prov)  # real renderer
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a box"})
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        _s, s1 = _req_json(host, port, "POST", f"/api/slice/{rid}",
                           {"printer": "bambu_p2s", "material": "pla"})
        assert s1.get("gcode_url"), "first slice should produce g-code"
        _s, _r = _req_json(host, port, "POST", f"/api/render/{rid}",
                           {"values": {"width": 100, "depth": 70, "height": 50, "wall": 2}})
        _s, s2 = _req_json(host, port, "POST", f"/api/slice/{rid}",
                           {"printer": "bambu_p2s", "material": "pla"})
        assert s2.get("gcode_url")
    assert calls["n"] == 2, "re-render must invalidate the cached slice, forcing a re-slice"


def test_concurrent_rerenders_are_serialized(tmp_path):
    # RENDER-001: a deliberately slow renderer records its [enter, exit] interval; with the
    # render_lock, two concurrent /api/render calls for the same id must NOT overlap (else they
    # would race on the shared per-design output dir). The 0.3s body makes overlap detectable.
    import threading
    import time

    import trimesh

    from kimcad.openscad_runner import RenderResult, SanitizeResult

    intervals = []
    ilock = threading.Lock()
    # TEST-005: a jitter-free invariant alongside the wall-clock interval check — the count of
    # renders *currently inside* the body must never exceed 1 if render_lock is serializing them.
    state = {"inside": 0, "max": 0}

    def slow_render(scad, out_dir, basename):
        with ilock:
            state["inside"] += 1
            state["max"] = max(state["max"], state["inside"])
        try:
            t0 = time.monotonic()
            time.sleep(0.3)
            p = out_dir / f"{basename}.stl"
            trimesh.creation.box(extents=(80, 60, 40)).export(str(p))
            with ilock:
                intervals.append((t0, time.monotonic()))
            return RenderResult(output_path=p, output_format="stl", stdout="", stderr="",
                                duration_s=0.3, sanitize=SanitizeResult(code=scad, removed=[]))
        finally:
            with ilock:
                state["inside"] -= 1

    pipe = Pipeline(Config.load(), BAMBU, PLA, FakeProvider(_box_plan()), renderer=slow_render)
    results = {}
    with _serve(pipe, tmp_path) as (host, port):
        _s, d = _req_json(host, port, "POST", "/api/design", {"prompt": "a box"})
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])
        intervals.clear()  # count only the two re-renders, not the initial design render

        def go(k, w):
            results[k] = _req_json(host, port, "POST", f"/api/render/{rid}",
                                   {"values": {"width": w, "depth": 60, "height": 40, "wall": 2}})

        t1 = threading.Thread(target=go, args=("a", 100))
        t2 = threading.Thread(target=go, args=("b", 120))
        t1.start()
        t2.start()
        t1.join(20)
        t2.join(20)

    assert len(intervals) == 2 and results.get("a") and results.get("b")
    assert results["a"][0] == 200 and results["b"][0] == 200
    # Jitter-free invariant: the two re-renders were never inside the renderer simultaneously.
    assert state["max"] == 1, "two re-renders ran concurrently — render_lock is not serializing"
    # Belt-and-suspenders: their wall-clock intervals also don't overlap.
    (a0, a1), (b0, b1) = sorted(intervals)
    assert a1 <= b0 + 0.001, "re-renders overlapped — render_lock is not serializing them"


# --- Stage 8.5: saved designs ("My Designs") endpoints --------------------------------------
import contextlib as _ctx2  # noqa: E402
import http.client as _hc  # noqa: E402
import json as _json2  # noqa: E402
import threading as _thr2  # noqa: E402
from http.server import ThreadingHTTPServer as _THS2  # noqa: E402
from pathlib import Path as _Path2  # noqa: E402

# A 1x1 transparent PNG as a data URL (a stand-in viewport thumbnail).
_TINY_PNG = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@_ctx2.contextmanager
def _serve_with_designs(pipe, root, designs_dir):
    """Serve with the saved-designs store pointed at a tmp dir (never the real ~/.kimcad)."""
    root = _Path2(root)
    root.mkdir(parents=True, exist_ok=True)
    cfg = Config({"paths": {"designs": str(designs_dir)}})
    httpd = _THS2(("127.0.0.1", 0), make_handler(pipe, root, config=cfg))
    _thr2.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _req(host, port, method, path, body=None):
    conn = _hc.HTTPConnection(host, port, timeout=20)
    try:
        data = _json2.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        return resp.status, resp.read()
    finally:
        conn.close()


def _jreq(host, port, method, path, body=None):
    status, raw = _req(host, port, method, path, body)
    return status, _json2.loads(raw)


def _template_box_pipeline():
    from kimcad.ir import DesignPlan

    plan = DesignPlan(
        object_type="box", summary="a box",
        dimensions={"width": 80, "depth": 60, "height": 40, "wall": 2},
        bounding_box_mm=None, printer="bambu_p2s", material="pla",
    )
    return _pipeline(FakeProvider(plan), _box_renderer((80, 60, 40)))


def test_designs_full_round_trip(tmp_path):
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, design = _jreq(h, p, "POST", "/api/design", {"prompt": "a box"})
        assert st == 200 and design["status"] == "completed"
        rid = int(design["mesh_url"].rsplit("/", 1)[-1])
        assert design.get("parameters")  # template-backed -> has live sliders

        st, saved = _jreq(h, p, "POST", "/api/designs/save",
                          {"design_id": rid, "name": "My Box", "thumbnail": _TINY_PNG})
        assert st == 200 and saved["name"] == "My Box"
        sid = saved["id"]

        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert st == 200
        entry = next(d for d in lst["designs"] if d["id"] == sid)
        assert entry["name"] == "My Box" and entry["object_type"] == "box"
        assert entry["thumb_url"] == f"/api/designs/{sid}/thumb"

        st, raw = _req(h, p, "GET", f"/api/designs/{sid}/thumb")
        assert st == 200 and raw[:8] == b"\x89PNG\r\n\x1a\n"

        # Reopen -> fresh fully-functional design (mesh serves; sliders + re-render restored).
        st, reopened = _jreq(h, p, "GET", f"/api/designs/{sid}")
        assert st == 200 and reopened["saved_id"] == sid and reopened.get("parameters")
        newrid = int(reopened["mesh_url"].rsplit("/", 1)[-1])
        st, mesh = _req(h, p, "GET", f"/api/mesh/{newrid}")
        assert st == 200 and len(mesh) > 0
        # Re-render at the part's own size (the stub renderer always emits 80x60x40): a 200 +
        # 'completed' proves the template re-render state was restored on reopen (a missing one
        # would render-fail), without coupling to the stub's fixed output size.
        st, rr = _jreq(h, p, "POST", f"/api/render/{newrid}",
                       {"values": {"width": 80, "depth": 60, "height": 40, "wall": 2}})
        assert st == 200 and rr["status"] == "completed"  # re-render on a reopened design works

        st, _ = _jreq(h, p, "POST", f"/api/designs/{sid}/rename", {"name": "Renamed"})
        assert st == 200
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert next(d for d in lst["designs"] if d["id"] == sid)["name"] == "Renamed"

        st, dup = _jreq(h, p, "POST", f"/api/designs/{sid}/duplicate")
        assert st == 200 and dup["ok"] and dup["id"]
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert len(lst["designs"]) == 2

        st, _ = _jreq(h, p, "POST", f"/api/designs/{sid}/delete")
        assert st == 200
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert sid not in [d["id"] for d in lst["designs"]] and len(lst["designs"]) == 1


def test_designs_save_without_a_design_is_404(tmp_path):
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, _ = _jreq(h, p, "POST", "/api/designs/save", {"design_id": 9999, "name": "x"})
        assert st == 404


def test_designs_reopen_unknown_is_404(tmp_path):
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, _ = _jreq(h, p, "GET", "/api/designs/deadbeef01")
        assert st == 404


def test_designs_thumb_endpoint_rejects_traversal(tmp_path):
    # S1B-001: a traversal id on the thumb endpoint must be rejected, never reading a file outside
    # the store root. Plant a thumb.png at the traversal target and prove it is NOT served.
    store_root = tmp_path / "store"
    secret = tmp_path / "secret"
    secret.mkdir(parents=True)
    (secret / "thumb.png").write_bytes(b"\x89PNG\r\n\x1a\nSECRETBYTES")
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", store_root) as (h, p):
        st, raw = _req(h, p, "GET", "/api/designs/..%2fsecret/thumb")
        assert st == 404
        assert b"SECRET" not in raw


def test_save_after_rerender_persists_the_rerendered_parameters(tmp_path):
    # S1B-002: saving after a slider re-render must persist the RE-RENDERED parameters, not the
    # original (the snapshot is refreshed on re-render so it matches the saved mesh).
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, design = _jreq(h, p, "POST", "/api/design", {"prompt": "a box"})
        rid = int(design["mesh_url"].rsplit("/", 1)[-1])
        original_wall = next(pp for pp in design["parameters"] if pp["name"] == "wall")["value"]
        assert original_wall == 2.0

        # Re-render at a new wall (same size so the stub's 80x60x40 still passes the gate).
        st, rr = _jreq(h, p, "POST", f"/api/render/{rid}",
                       {"values": {"width": 80, "depth": 60, "height": 40, "wall": 3.0}})
        assert st == 200 and rr["status"] == "completed"
        assert next(pp for pp in rr["parameters"] if pp["name"] == "wall")["value"] == 3.0

        st, saved = _jreq(h, p, "POST", "/api/designs/save", {"design_id": rid, "name": "tweaked"})
        st, reopened = _jreq(h, p, "GET", f"/api/designs/{saved['id']}")
        reopened_wall = next(pp for pp in reopened["parameters"] if pp["name"] == "wall")["value"]
        assert reopened_wall == 3.0  # the stale-snapshot bug would persist the original 2.0


def test_save_update_in_place_keeps_one_entry(tmp_path):
    # Re-saving with the existing saved_id updates that entry (one library entry, name preserved),
    # so adjusting a part and saving again doesn't spawn duplicates.
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, design = _jreq(h, p, "POST", "/api/design", {"prompt": "a box"})
        rid = int(design["mesh_url"].rsplit("/", 1)[-1])
        st, saved = _jreq(h, p, "POST", "/api/designs/save", {"design_id": rid, "name": "v1"})
        sid = saved["id"]
        _jreq(h, p, "POST", f"/api/render/{rid}",
              {"values": {"width": 80, "depth": 60, "height": 40, "wall": 3.0}})
        st, saved2 = _jreq(h, p, "POST", "/api/designs/save", {"design_id": rid, "saved_id": sid})
        assert st == 200 and saved2["id"] == sid  # same entry, not a new id
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert len(lst["designs"]) == 1 and lst["designs"][0]["name"] == "v1"  # name preserved
        st, reopened = _jreq(h, p, "GET", f"/api/designs/{sid}")
        assert next(pp for pp in reopened["parameters"] if pp["name"] == "wall")["value"] == 3.0


def _import_zip(host, port, blob):
    conn = _hc.HTTPConnection(host, port, timeout=20)
    try:
        conn.request("POST", "/api/designs/import", body=blob,
                     headers={"Content-Type": "application/zip"})
        resp = conn.getresponse()
        return resp.status, _json2.loads(resp.read())
    finally:
        conn.close()


def test_designs_export_import_round_trip(tmp_path):
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, design = _jreq(h, p, "POST", "/api/design", {"prompt": "a box"})
        rid = int(design["mesh_url"].rsplit("/", 1)[-1])
        st, saved = _jreq(h, p, "POST", "/api/designs/save", {"design_id": rid, "name": "Portable"})
        sid = saved["id"]
        st, blob = _req(h, p, "GET", f"/api/designs/{sid}/export")
        assert st == 200 and blob[:2] == b"PK"  # a zip download
        st, imp = _import_zip(h, p, blob)
        assert st == 200 and imp["id"] and imp["id"] != sid  # a fresh id
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert len(lst["designs"]) == 2  # original + imported
        st, reopened = _jreq(h, p, "GET", f"/api/designs/{imp['id']}")
        assert reopened.get("parameters")  # the imported design reopens, sliders restored


def test_designs_import_rejects_garbage(tmp_path):
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, body = _import_zip(h, p, b"not a real zip")
        assert st == 400


def test_designs_mutate_bad_id_is_404(tmp_path):
    # QA-003: rename/delete/duplicate of an unsafe or absent id is a 404 (matching reopen/thumb/
    # export), not a 200 {"ok": false} a status-only client would misread as success.
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        for verb in ("rename", "delete", "duplicate"):
            body = {"name": "x"} if verb == "rename" else {}
            st, _ = _jreq(h, p, "POST", "/api/designs/..%2f..%2fetc/" + verb, body)
            assert st == 404, f"unsafe id / {verb}"
            st, _ = _jreq(h, p, "POST", "/api/designs/deadbeef99/" + verb, body)
            assert st == 404, f"absent id / {verb}"


def test_concurrent_saves_without_saved_id_make_one_entry(tmp_path):
    # QA-002: rapid auto-saves of the SAME live rid without a saved_id must converge to ONE library
    # entry (the server reuses a stable per-rid id), not mint a duplicate per call.
    import threading
    with _serve_with_designs(_template_box_pipeline(), tmp_path / "web", tmp_path / "store") as (h, p):
        st, design = _jreq(h, p, "POST", "/api/design", {"prompt": "a box"})
        rid = int(design["mesh_url"].rsplit("/", 1)[-1])
        results: list[tuple[int, str]] = []

        def fire() -> None:
            st, saved = _jreq(h, p, "POST", "/api/designs/save",
                              {"design_id": rid, "name": "Race"})
            results.append((st, saved.get("id")))

        threads = [threading.Thread(target=fire) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)
        assert all(st == 200 for st, _ in results)  # the retry absorbs the Windows replace race
        assert len({sid for _, sid in results}) == 1  # one shared id across all concurrent saves
        st, lst = _jreq(h, p, "GET", "/api/designs")
        assert len(lst["designs"]) == 1  # exactly one library entry, no duplicates


def test_sanitize_history_keeps_only_wellformed_bounded_turns():
    # Slice 2: the client-supplied conversation history is sanitized before it reaches the model.
    from kimcad.webapp import MAX_HISTORY_CONTENT, MAX_HISTORY_TURNS, _sanitize_history
    assert _sanitize_history(None) is None
    assert _sanitize_history("not a list") is None
    assert _sanitize_history([]) is None
    assert _sanitize_history([{"role": "user", "content": "hi"}]) == [{"role": "user", "content": "hi"}]
    # Drops bad roles, non-str content, and non-dict entries; preserves order of the good ones.
    assert _sanitize_history([
        {"role": "user", "content": "ok"},
        {"role": "system", "content": "drop me (bad role)"},
        {"role": "assistant", "content": 5},  # non-str content
        "not a dict",
        {"role": "assistant", "content": "kept"},
    ]) == [{"role": "user", "content": "ok"}, {"role": "assistant", "content": "kept"}]
    # Caps the number of turns (keeps the most recent).
    many = [{"role": "user", "content": str(i)} for i in range(MAX_HISTORY_TURNS + 5)]
    capped = _sanitize_history(many)
    assert len(capped) == MAX_HISTORY_TURNS and capped[-1]["content"] == str(MAX_HISTORY_TURNS + 4)
    # Caps each turn's content length.
    long = _sanitize_history([{"role": "user", "content": "y" * (MAX_HISTORY_CONTENT + 100)}])
    assert len(long[0]["content"]) == MAX_HISTORY_CONTENT


def test_sanitize_history_bounds_aggregate_content_keeping_newest():
    # ENG-001: even within the per-turn + turn-count caps, the TOTAL kept content is bounded, and
    # the most-recent turns are the ones retained (newest is the relevant context for a refine).
    from kimcad.webapp import (
        MAX_HISTORY_CONTENT,
        MAX_HISTORY_TOTAL_CONTENT,
        _sanitize_history,
    )

    # 20 maxed-out turns would be 20 * 4000 = 80 KB; the aggregate cap must trim that down.
    big = [
        {"role": "user", "content": f"{i}-" + "x" * MAX_HISTORY_CONTENT}
        for i in range(20)
    ]
    out = _sanitize_history(big)
    total = sum(len(t["content"]) for t in out)
    assert total <= MAX_HISTORY_TOTAL_CONTENT
    # The kept turns are the most recent ones, in chronological order (last turn is index 19).
    assert out[-1]["content"].startswith("19-")
    # Earlier (older) turns were dropped to honor the budget, so fewer than all 20 survive.
    assert len(out) < 20


def test_design_threads_sanitized_history_to_the_model(tmp_path):
    # Slice 2: a follow-up turn's prior conversation reaches generate_design_plan as `history`, so
    # the model refines in context — and a malformed history never 400s/500s (it's dropped).
    from conftest import FakeProvider
    captured: dict = {}

    class Recording(FakeProvider):
        def generate_design_plan(self, prompt, printer, material, history=None):  # noqa: ANN001
            captured["history"] = history
            return super().generate_design_plan(prompt, printer, material, history=history)

    pipe = _pipeline(Recording(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, _ = _jreq(host, port, "POST", "/api/design", {
            "prompt": "make it 10mm taller",
            "history": [
                {"role": "user", "content": "a 20mm box"},
                {"role": "assistant", "content": "Here you go — a 20mm box."},
                {"role": "bogus", "content": "dropped"},
            ],
        })
        assert st == 200
        assert captured["history"] == [
            {"role": "user", "content": "a 20mm box"},
            {"role": "assistant", "content": "Here you go — a 20mm box."},
        ]
        # No history key -> standalone (None), and a non-list history is dropped to None, never an error.
        st, _ = _jreq(host, port, "POST", "/api/design", {"prompt": "a fresh box"})
        assert st == 200 and captured["history"] is None
        st, _ = _jreq(host, port, "POST", "/api/design", {"prompt": "a box", "history": "garbage"})
        assert st == 200 and captured["history"] is None


# --- Stage 8.5 Slice 6: the Settings endpoint -------------------------------


def test_settings_get_post_roundtrip_and_options_reflects(tmp_path, monkeypatch):
    """Slice 6: /api/settings GET returns the choices + effective defaults; POST persists a new
    default printer/material; GET and /api/options both then reflect it (the saved default is
    authoritative app-wide)."""
    from kimcad import config as config_mod

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, get1 = _jreq(host, port, "GET", "/api/settings")
        assert st == 200
        printer_keys = [p["key"] for p in get1["printers"]]
        material_keys = [m["key"] for m in get1["materials"]]
        assert get1["default_printer"] in printer_keys
        assert get1["default_material"] in material_keys
        # Pick a DIFFERENT printer + material than the current default to prove the change sticks.
        new_printer = next(k for k in printer_keys if k != get1["default_printer"])
        new_material = next(k for k in material_keys if k != get1["default_material"])
        st, resp = _jreq(host, port, "POST", "/api/settings",
                         {"default_printer": new_printer, "default_material": new_material})
        assert st == 200 and resp["saved"] is True
        assert resp["default_printer"] == new_printer
        assert resp["default_material"] == new_material
        # A fresh GET reflects the persisted choice.
        st, get2 = _jreq(host, port, "GET", "/api/settings")
        assert get2["default_printer"] == new_printer and get2["default_material"] == new_material
        # And /api/options (what the rest of the app reads) reflects it too.
        st, opt = _jreq(host, port, "GET", "/api/options")
        assert opt["default_printer"] == new_printer and opt["default_material"] == new_material
        # The choice actually landed on disk (not just in memory).
        assert settings_file.exists()


def test_settings_post_rejects_unknown_keys(tmp_path, monkeypatch):
    """An unknown printer/material value is a clean 400 — never a 500, never a silent save."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, _ = _jreq(host, port, "POST", "/api/settings", {"default_printer": "no-such-printer"})
        assert st == 400
        st, _ = _jreq(host, port, "POST", "/api/settings", {"default_material": "no-such-material"})
        assert st == 400
        # Nothing was persisted by the rejected requests.
        st, opt = _jreq(host, port, "GET", "/api/settings")
        assert st == 200  # still serving the config defaults, no corruption


def test_settings_clear_override_falls_back_to_config_default(tmp_path, monkeypatch):
    """Sending null clears an override, restoring the shipped config default."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, get1 = _jreq(host, port, "GET", "/api/settings")
        config_default = get1["default_printer"]
        new_printer = next(k for k in [p["key"] for p in get1["printers"]] if k != config_default)
        _jreq(host, port, "POST", "/api/settings", {"default_printer": new_printer})
        st, mid = _jreq(host, port, "GET", "/api/settings")
        assert mid["default_printer"] == new_printer
        # Clear it -> back to the config default.
        _jreq(host, port, "POST", "/api/settings", {"default_printer": None})
        st, after = _jreq(host, port, "GET", "/api/settings")
        assert after["default_printer"] == config_default


def test_settings_post_reports_unsaved_when_store_write_fails(tmp_path, monkeypatch):
    """When the local store can't persist (e.g. a read-only ~/.kimcad), POST returns 200 with
    saved:false — never a 500, never a dishonest saved:true — so the UI can tell the user their
    choice didn't stick."""
    from kimcad import config as config_mod
    from kimcad import settings_store as ss_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    # Simulate a persistence failure at the store layer.
    monkeypatch.setattr(ss_mod.SettingsStore, "update", lambda self, updates: False)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, get1 = _jreq(host, port, "GET", "/api/settings")
        new_printer = next(k for k in [p["key"] for p in get1["printers"]] if k != get1["default_printer"])
        st, resp = _jreq(host, port, "POST", "/api/settings", {"default_printer": new_printer})
        assert st == 200
        assert resp["saved"] is False


# --- Stage 8.5 Slice 6 MS-2: the model-status endpoint ----------------------


def test_model_status_local_running_with_model(tmp_path, monkeypatch):
    """The local (Ollama) backend, reachable and with the model pulled, reports running + present."""
    from kimcad import model_advisor as ma
    from kimcad.model_advisor import InstalledModel

    monkeypatch.setattr(ma, "probe_ollama", lambda base_url, timeout=3.0: (True, [InstalledModel(name="gemma4:e4b")]))
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200
        assert s["backend"] == "local"
        assert s["model"] == "gemma4:e4b"
        assert s["running"] is True and s["model_present"] is True


def test_model_status_matches_quantized_variant(tmp_path, monkeypatch):
    """A quantized install (gemma4:e4b-it-q4_K_M) still counts as the model being present."""
    from kimcad import model_advisor as ma
    from kimcad.model_advisor import InstalledModel

    monkeypatch.setattr(ma, "probe_ollama",
                        lambda base_url, timeout=3.0: (True, [InstalledModel(name="gemma4:e4b-it-q4_K_M")]))
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200 and s["model_present"] is True


def test_model_status_ollama_down_is_not_running(tmp_path, monkeypatch):
    """Ollama unreachable -> running:false (the UI says "start Ollama"); a STATUS, never a 500."""
    from kimcad import model_advisor as ma

    monkeypatch.setattr(ma, "probe_ollama", lambda base_url, timeout=3.0: (False, []))
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200
        assert s["running"] is False and s["model_present"] is False


def test_model_status_running_but_model_absent(tmp_path, monkeypatch):
    """Ollama up but the model not pulled -> running:true, model_present:false (the UI says
    "get the model") — distinct from the down case, which the (reachable, models) probe enables."""
    from kimcad import model_advisor as ma
    from kimcad.model_advisor import InstalledModel

    monkeypatch.setattr(ma, "probe_ollama", lambda base_url, timeout=3.0: (True, [InstalledModel(name="llama3:8b")]))
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200
        assert s["running"] is True and s["model_present"] is False


def test_model_status_cloud_backend_reports_cloud(tmp_path, monkeypatch):
    """A cloud backend reports backend:'cloud' + running:true (configured) and does NOT probe
    Ollama — the cloud path MS-3 builds on."""
    from kimcad import config as config_mod
    from kimcad import model_advisor as ma
    from kimcad.config import LLMBackend

    cloud = LLMBackend(
        key="cloud_deepseek", provider="deepseek", base_url="https://api.deepseek.com/v1",
        model_name="deepseek-v4-flash", api_key_env="DEEPSEEK_API_KEY", temperature=0.2,
        max_tokens=8192, supports_structured_output=True,
    )
    monkeypatch.setattr(config_mod.Config, "llm_backend", lambda self, key=None: cloud)
    # If the handler wrongly probed Ollama for a cloud backend, this would blow up the test.
    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("cloud backend must not probe Ollama")
    monkeypatch.setattr(ma, "probe_ollama", _boom)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200
        assert s["backend"] == "cloud"
        assert s["running"] is True and s["model"] == "deepseek-v4-flash"


# --- Stage 8.5 Slice 6 slice-end remediation -----------------------------------


def test_probe_ollama_distinguishes_reachable_from_empty(monkeypatch):
    """probe_ollama returns reachable=True even when Ollama has no models (unlike
    probe_installed_models, which returns [] for both down AND empty) — the whole reason it exists."""
    import io
    import json as _j
    import urllib.error

    from kimcad import model_advisor as ma

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _serve_json(payload):
        return lambda url, timeout=3.0: _Resp(_j.dumps(payload).encode())

    monkeypatch.setattr(ma.urllib.request, "urlopen", _serve_json({"models": [{"name": "gemma4:e4b"}]}))
    reachable, models = ma.probe_ollama("http://localhost:11434/v1")
    assert reachable is True and [m.name for m in models] == ["gemma4:e4b"]

    monkeypatch.setattr(ma.urllib.request, "urlopen", _serve_json({"models": []}))
    reachable, models = ma.probe_ollama("http://localhost:11434/v1")
    assert reachable is True and models == []  # UP but empty

    def _down(url, timeout=3.0):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(ma.urllib.request, "urlopen", _down)
    reachable, models = ma.probe_ollama("http://localhost:11434/v1")
    assert reachable is False and models == []  # DOWN


def test_settings_aware_provider_degrades_to_local_on_cloud_build_error(tmp_path, monkeypatch):
    """If building the cloud provider raises, the router falls back to LOCAL — never breaks a design."""
    from kimcad import config as config_mod
    from kimcad.settings_store import SettingsStore
    from kimcad.webapp import _SettingsAwareProvider

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    cfg = config_mod.Config.load()
    SettingsStore(settings_file).update(
        {"cloud_enabled": True, "openrouter_api_key": "or-fake-key", "cloud_model": "x/y"}
    )
    orig = config_mod.Config.llm_backend

    def _raise_for_cloud(self, key=None):
        if key == "custom_openrouter":
            raise RuntimeError("boom")
        return orig(self, key)

    monkeypatch.setattr(config_mod.Config, "llm_backend", _raise_for_cloud)
    local = object()
    assert _SettingsAwareProvider(local, cfg)._active() is local


def test_model_status_cloud_never_returns_the_key(tmp_path, monkeypatch):
    """The model-status cloud branch reads the key only to test presence — it must NOT appear in
    the response."""
    import json as _j

    from kimcad import config as config_mod
    from kimcad.settings_store import SettingsStore

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    SECRET = "or-fake-key-ABCDEwQ9f2"
    SettingsStore(settings_file).update(
        {"cloud_enabled": True, "openrouter_api_key": SECRET, "cloud_model": "anthropic/claude-sonnet"}
    )
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, s = _jreq(host, port, "GET", "/api/model-status")
        assert st == 200 and s["backend"] == "cloud"
        assert SECRET not in _j.dumps(s)


def test_settings_reset_clears_everything_to_pristine(tmp_path, monkeypatch):
    """A {reset:true} POST clears EVERY override (no stale false keys left on disk)."""
    import json as _j

    from kimcad import config as config_mod

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, g0 = _jreq(host, port, "GET", "/api/settings")
        new_printer = next(k for k in [p["key"] for p in g0["printers"]] if k != g0["default_printer"])
        _jreq(host, port, "POST", "/api/settings", {
            "default_printer": new_printer, "cloud_enabled": True,
            "openrouter_api_key": "or-fake-wQ9f2", "experimental_enabled": True,
        })
        st, r = _jreq(host, port, "POST", "/api/settings", {"reset": True})
        assert st == 200 and r["saved"] is True
        assert r["default_printer"] == g0["default_printer"]  # back to config default
        assert r["cloud_enabled"] is False
        assert r["has_cloud_key"] is False
        assert r["experimental_enabled"] is False
        # The file holds NO stale keys.
        assert _j.loads(settings_file.read_text(encoding="utf-8")) == {}


# --- Stage 8.5 Slice 6 MS-5: tools health + version ----------------------------


def test_health_reports_tools_and_version(tmp_path):
    """GET /api/health reports OpenSCAD/OrcaSlicer presence + the app version; never 500s."""
    from kimcad import __version__

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, h = _jreq(host, port, "GET", "/api/health")
        assert st == 200
        assert h["version"] == __version__
        # The bundled binaries are configured + present in the repo (tools/…).
        assert isinstance(h["openscad"], bool) and isinstance(h["orcaslicer"], bool)
        assert h["openscad"] is True  # tools/openscad/openscad.exe is committed


def test_health_missing_binary_is_a_status_not_a_500(tmp_path, monkeypatch):
    """A missing/unconfigured binary is present:false, never a 500."""
    from kimcad import config as config_mod

    def _boom(self, name):  # noqa: ANN001
        raise KeyError(name)

    monkeypatch.setattr(config_mod.Config, "binary_path", _boom)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, h = _jreq(host, port, "GET", "/api/health")
        assert st == 200
        assert h["openscad"] is False and h["orcaslicer"] is False


# --- Stage 8.5 Slice 6 MS-4: the experimental-generator gate --------------------


def test_design_experimental_false_offers_instead_of_codegen(tmp_path, monkeypatch):
    """The consumer default: a non-template request with experimental:false returns the offer
    (needs_experimental) and never runs the codegen model — no dead-end, no auto-run."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    provider = FakeProvider(_plan([20, 20, 20]))  # object_type "block" -> non-template
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, r = _jreq(host, port, "POST", "/api/design",
                      {"prompt": "a topographic coaster", "experimental": False})
        assert st == 200
        assert r["status"] == "needs_experimental"
        assert not r.get("has_mesh")
        assert provider.openscad_calls == 0


def test_design_experimental_true_runs_codegen(tmp_path, monkeypatch):
    """Opting in (experimental:true) runs the sandboxed codegen and completes."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    provider = FakeProvider(_plan([20, 20, 20]))
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, r = _jreq(host, port, "POST", "/api/design",
                      {"prompt": "a topographic coaster", "experimental": True})
        assert st == 200
        assert r["status"] == "completed" and r["has_mesh"] is True
        assert provider.openscad_calls >= 1


def test_design_no_flag_defaults_to_running_codegen(tmp_path, monkeypatch):
    """An ABSENT flag (raw API / CLI / older client) keeps the backward-compatible auto-run —
    the consumer SPA is the layer that opts OUT by sending experimental:false."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    provider = FakeProvider(_plan([20, 20, 20]))
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, r = _jreq(host, port, "POST", "/api/design", {"prompt": "a topographic coaster"})
        assert st == 200 and r["status"] == "completed"


def test_design_experimental_setting_on_auto_runs(tmp_path, monkeypatch):
    """With the Settings toggle ON, a non-template request auto-runs even when the SPA sends
    experimental:false (the setting force-enables it)."""
    from kimcad import config as config_mod
    from kimcad.settings_store import SettingsStore

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    SettingsStore(settings_file).update({"experimental_enabled": True})
    provider = FakeProvider(_plan([20, 20, 20]))
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, r = _jreq(host, port, "POST", "/api/design",
                      {"prompt": "a topographic coaster", "experimental": False})
        assert st == 200 and r["status"] == "completed"


# --- Stage 8.5 Slice 6 MS-3: cloud opt-in + the masked OpenRouter key -----------


def test_cloud_key_saved_locally_but_never_returned_in_full(tmp_path, monkeypatch):
    """TRUST-CRITICAL: the OpenRouter key is stored on disk (the user's machine) but the API never
    returns it in full — only a masked form (last 5). GET + POST both honor this."""
    import json as _j

    from kimcad import config as config_mod

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    SECRET = "or-fake-openrouter-key-ABCDEwQ9f2"
    with _serve(pipe, tmp_path) as (host, port):
        st, resp = _jreq(host, port, "POST", "/api/settings", {
            "cloud_enabled": True,
            "openrouter_api_key": SECRET,
            "cloud_model": "anthropic/claude-sonnet",
        })
        assert st == 200 and resp["saved"] is True
        # The full key is NEVER anywhere in the response.
        assert SECRET not in _j.dumps(resp)
        assert resp["has_cloud_key"] is True
        assert resp["cloud_key_masked"].endswith(SECRET[-5:])
        assert resp["cloud_enabled"] is True
        assert resp["cloud_model"] == "anthropic/claude-sonnet"
        # A fresh GET also never returns it raw.
        st, g = _jreq(host, port, "GET", "/api/settings")
        assert SECRET not in _j.dumps(g)
        assert g["cloud_key_masked"].endswith(SECRET[-5:])
        # But the real key DID land on disk (local consumer storage, the user's machine).
        on_disk = _j.loads(settings_file.read_text(encoding="utf-8"))
        assert on_disk["openrouter_api_key"] == SECRET
        # And model-status now reports the user's cloud model, not the local default.
        st, ms = _jreq(host, port, "GET", "/api/model-status")
        assert ms["backend"] == "cloud" and ms["model"] == "anthropic/claude-sonnet"


def test_cloud_key_can_be_cleared(tmp_path, monkeypatch):
    """A blank key clears it — has_cloud_key false, masked null."""
    from kimcad import config as config_mod

    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: tmp_path / "settings.json")
    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        _jreq(host, port, "POST", "/api/settings", {"openrouter_api_key": "or-fake-key-wQ9f2"})
        st, g1 = _jreq(host, port, "GET", "/api/settings")
        assert g1["has_cloud_key"] is True
        _jreq(host, port, "POST", "/api/settings", {"openrouter_api_key": ""})
        st, g2 = _jreq(host, port, "GET", "/api/settings")
        assert g2["has_cloud_key"] is False and g2["cloud_key_masked"] is None


def test_settings_aware_provider_routes_by_cloud_setting(tmp_path, monkeypatch):
    """The provider routes to LOCAL by default, to a cloud OpenRouter provider (the user's model +
    key) when cloud is enabled + configured, and back to LOCAL when enabled-but-unconfigured."""
    from kimcad import config as config_mod
    from kimcad.llm_provider import LLMProvider
    from kimcad.settings_store import SettingsStore
    from kimcad.webapp import _SettingsAwareProvider

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    cfg = config_mod.Config.load()
    local = object()  # a sentinel local provider
    prov = _SettingsAwareProvider(local, cfg)

    # No settings -> local.
    assert prov._active() is local
    # Cloud enabled but no key/model -> still local (degrade, never break).
    SettingsStore(settings_file).update({"cloud_enabled": True})
    assert prov._active() is local
    # Fully configured -> a cloud LLMProvider carrying the user's chosen model.
    SettingsStore(settings_file).update(
        {"openrouter_api_key": "or-fake-key-value", "cloud_model": "anthropic/claude-sonnet"}
    )
    active = prov._active()
    assert active is not local
    assert isinstance(active, LLMProvider)
    assert active.backend.model_name == "anthropic/claude-sonnet"


# --- Stage 8.5 Slice 7: the photo on-ramp (local vision seed) -------------------


def _post_photo(host, port, body, content_length=None, content_type="image/png"):
    import json as _j

    conn = http.client.HTTPConnection(host, port, timeout=15)
    try:
        conn.putrequest("POST", "/api/photo-seed", skip_host=False, skip_accept_encoding=True)
        conn.putheader("Content-Type", content_type)
        conn.putheader("Content-Length", str(content_length if content_length is not None else len(body)))
        conn.endheaders()
        if body:
            conn.send(body)
        resp = conn.getresponse()
        raw = resp.read()
        return resp.status, (_j.loads(raw) if raw else {})
    finally:
        conn.close()


def test_photo_seed_returns_a_rough_seed(tmp_path):
    """POST a photo -> a rough text seed from the LOCAL vision provider (the fake/demo provider
    returns a canned seed, so the on-ramp is exercisable without the real vision model)."""
    provider = FakeProvider(_plan([20, 20, 20]))
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, d = _post_photo(host, port, b"\x89PNG-fake-image-bytes")
        assert st == 200
        assert "seed" in d and "rough" in d["seed"].lower()
        assert getattr(provider, "photo_calls", 0) == 1  # local vision ran once


def test_photo_seed_oversized_is_413(tmp_path):
    from kimcad.webapp import MAX_PHOTO_BYTES

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        # Declare an oversized Content-Length; the body is never read.
        st, _ = _post_photo(host, port, b"", content_length=MAX_PHOTO_BYTES + 1)
        assert st == 413


def test_photo_seed_empty_upload_is_400(tmp_path):
    """An empty body (Content-Length 0) is a clean 400 'Empty upload.' — not a 500 and not a vision
    attempt on zero bytes (TEST-701: the 400 branch of _read_raw_body for this route)."""
    provider = FakeProvider(_plan([20, 20, 20]))
    pipe = _pipeline(provider, _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, d = _post_photo(host, port, b"", content_length=0)
        assert st == 400 and "empty" in d["error"].lower()
        assert getattr(provider, "photo_calls", 0) == 0  # vision was never invoked on an empty body


def test_photo_seed_unreadable_is_422_not_500(tmp_path):
    """A vision failure is a clean 422 with a friendly message, never a 500."""

    class _BadVision(FakeProvider):
        def describe_photo(self, image_bytes, printer, material):  # noqa: ANN001
            raise RuntimeError("vision boom")

    pipe = _pipeline(_BadVision(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, d = _post_photo(host, port, b"img")
        assert st == 422 and "photo" in d["error"].lower()


def test_photo_seed_empty_seed_is_422(tmp_path):
    """An empty/blank seed (the model couldn't make out a part) is a 422, not a silent 200."""

    class _EmptyVision(FakeProvider):
        def describe_photo(self, image_bytes, printer, material):  # noqa: ANN001
            return "   "

    pipe = _pipeline(_EmptyVision(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        st, _ = _post_photo(host, port, b"img")
        assert st == 422


def test_llm_describe_photo_uses_native_chat_with_think_false(monkeypatch):
    """The local vision call hits Ollama's NATIVE /api/chat (not /v1) with the image attached and
    think disabled — the wiring the live probe proved is required for a non-empty vision response."""
    import io
    import json as _j

    from kimcad import llm_provider as lp
    from kimcad.config import LLMBackend

    backend = LLMBackend(
        key="local", provider="openai_compatible", base_url="http://localhost:11434/v1",
        model_name="gemma4:e4b", api_key_env=None, temperature=0.0, max_tokens=400,
        supports_structured_output=False,
    )
    captured: dict = {}

    class _Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = _j.loads(req.data)
        return _Resp(_j.dumps({"message": {"content": "a rough box, ~80mm"}}).encode())

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    seed = lp.LLMProvider(backend).describe_photo(b"imgbytes", BAMBU, PLA)
    assert seed == "a rough box, ~80mm"
    assert captured["url"].endswith("/api/chat")  # NATIVE endpoint, not /v1
    assert captured["body"]["think"] is False
    assert captured["body"]["messages"][1]["images"]  # the image was attached


def test_photo_never_routes_to_cloud_even_when_cloud_enabled(tmp_path, monkeypatch):
    """LOAD-BEARING trust rule: the photo is ALWAYS read by the LOCAL vision model and is NEVER
    auto-sent to the cloud — even with cloud TEXT fully enabled (key + model saved). The router's
    ``describe_photo`` must build a LOCAL provider and must NOT consult the cloud-capable
    ``_active()`` path (which is what would send a request to OpenRouter)."""
    from kimcad import config as config_mod
    from kimcad import llm_provider as lp
    from kimcad.settings_store import SettingsStore
    from kimcad.webapp import _SettingsAwareProvider

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(config_mod.Config, "settings_path", lambda self: settings_file)
    cfg = config_mod.Config.load()
    # Cloud TEXT fully enabled + configured — exactly the state in which a design prompt WOULD be
    # routed to the user's OpenRouter model. The photo must still stay local.
    SettingsStore(settings_file).update(
        {"cloud_enabled": True, "openrouter_api_key": "or-fake-key-value",
         "cloud_model": "anthropic/claude-sonnet"}
    )

    built: list[str] = []

    class _SpyProvider:
        def __init__(self, backend, *a, **kw):  # noqa: ANN001
            built.append(backend.key)  # record WHICH backend the photo was sent to
            self.backend = backend

        def describe_photo(self, image_bytes, printer, material):  # noqa: ANN001
            return "a rough box (local vision)"

    # describe_photo does ``from kimcad.llm_provider import LLMProvider`` at call time, so patching
    # the module attribute makes it build the spy instead of a real client.
    monkeypatch.setattr(lp, "LLMProvider", _SpyProvider)

    prov = _SettingsAwareProvider(object(), cfg)
    # Hard guard: the cloud-capable router must NOT be consulted for a photo.
    def _no_active() -> object:
        raise AssertionError("describe_photo must not route a photo through the cloud-capable _active()")

    monkeypatch.setattr(prov, "_active", _no_active)

    seed = prov.describe_photo(b"imgbytes", BAMBU, PLA)
    assert seed == "a rough box (local vision)"
    # The photo used the LOCAL backend, never the cloud (custom_openrouter) one — even though cloud
    # TEXT is fully enabled above.
    assert built == [cfg.llm_backend("local").key]
    assert "custom_openrouter" not in built


def test_design_with_model_down_returns_recoverable_status_not_500(tmp_path):
    """Slice 9 MS-1: when the local AI (Ollama) is unreachable, /api/design returns a recoverable
    `model_unavailable` status with a friendly message — never a raw 500/traceback."""
    import json
    import urllib.request

    class _OllamaDown:
        openscad_calls = 0

        def generate_design_plan(self, prompt, printer, material, history=None):
            # A connection error named like the OpenAI client's, matched by the duck-typed backstop.
            raise type("APIConnectionError", (Exception,), {})("connection refused")

        def generate_openscad(self, plan, printer, material, history=None):
            return ""

    pipe = _pipeline(_OllamaDown(), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f"http://{host}:{port}/api/design",
                data=json.dumps({"prompt": "a box", "experimental": True}).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=15,
        )
        assert resp.status == 200  # recoverable status, not a 500
        d = json.load(resp)
    assert d["status"] == "model_unavailable"
    assert d["has_mesh"] is False
    assert "Ollama" in d["error"]


def test_design_with_model_down_during_codegen_is_recoverable(tmp_path):
    """Slice 9 MS-1: a connection drop during CODEGEN (past the plan step) is ALSO mapped to the
    recoverable model_unavailable status, not a 500 — the web backstop covers any propagated error,
    wherever in the run it was raised."""
    import json
    import urllib.request

    from kimcad.templates import TemplateRegistry

    class _DownAtCodegen:
        openscad_calls = 0

        def generate_design_plan(self, prompt, printer, material, history=None):
            return _plan([20, 20, 20])  # a valid plan -> proceeds toward codegen

        def generate_openscad(self, plan, printer, material, history=None):
            raise type("APIConnectionError", (Exception,), {})("dropped mid-codegen")

    # Empty registry -> no template matches -> the LLM codegen path runs (and raises).
    pipe = _pipeline(_DownAtCodegen(), _box_renderer((20, 20, 20)), registry=TemplateRegistry(()))
    with _serve(pipe, tmp_path) as (host, port):
        resp = urllib.request.urlopen(
            urllib.request.Request(
                f"http://{host}:{port}/api/design",
                data=json.dumps({"prompt": "a box", "experimental": True}).encode(),
                headers={"Content-Type": "application/json"},
            ),
            timeout=15,
        )
        assert resp.status == 200
        d = json.load(resp)
    assert d["status"] == "model_unavailable" and d["has_mesh"] is False


# MS-3 — live design-progress poll (planning/generating/rendering/validating).
def test_progress_endpoint_unknown_id_returns_null(tmp_path):
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        data = json.load(
            urllib.request.urlopen(base + "/api/design/progress/never-started", timeout=10)
        )
    assert data == {"phase": None}


def test_progress_reports_planning_midrun_then_clears(tmp_path):
    import json
    import threading as _t
    import urllib.request

    started = _t.Event()
    release = _t.Event()

    class _BlockingProvider(FakeProvider):
        # Park the run inside the plan step (after the pipeline emits "planning") until the test
        # has observed the phase, so the cross-thread progress read is deterministic, not racy.
        def generate_design_plan(self, prompt, printer, material, history=None):  # noqa: ANN001
            started.set()
            release.wait(timeout=10)
            return super().generate_design_plan(prompt, printer, material, history=history)

    pipe = _pipeline(_BlockingProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        job = "job-abc123"
        out: dict = {}

        def _post():
            req = urllib.request.Request(
                base + "/api/design",
                data=json.dumps({"prompt": "a block", "job_id": job}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            out["data"] = json.load(urllib.request.urlopen(req, timeout=30))

        th = _t.Thread(target=_post)
        th.start()
        assert started.wait(timeout=10)  # the run is parked in the plan step
        prog = json.load(
            urllib.request.urlopen(base + f"/api/design/progress/{job}", timeout=10)
        )
        assert prog == {"phase": "planning"}
        release.set()
        th.join(timeout=30)
        assert out["data"]["status"] == "completed"
        # The slot is cleaned up once the run finishes.
        after = json.load(
            urllib.request.urlopen(base + f"/api/design/progress/{job}", timeout=10)
        )
    assert after == {"phase": None}


def test_design_accepts_invalid_job_id_without_tracking(tmp_path):
    # A malformed job_id must not 400 the design — progress is best-effort; the run still completes.
    import json
    import urllib.request

    pipe = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(pipe, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        req = urllib.request.Request(
            base + "/api/design",
            data=json.dumps({"prompt": "a block", "job_id": "bad id!#"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        data = json.load(urllib.request.urlopen(req, timeout=30))
    assert data["status"] == "completed"
