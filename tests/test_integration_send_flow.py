"""TST-4 / TST-6 — end-to-end pipeline integration: render -> gate -> slice -> send.

TST-4 is the one automated test that drives the WHOLE chain as a single real flow over the
web API: design a real 20 mm box (FakeProvider plan + a real trimesh render), run the
printability gate, slice it through the REAL OrcaSlicer, and send the proven G-code to the
built-in ``mock`` loopback connector — asserting ``sent: true, simulated: true``. The same
test then proves the safety interlock end-to-end: a gate-FAILED variant (the plan asks for
50 mm but the mesh is 20 mm, so the dimensional gate fails) is refused at BOTH the slice step
(no G-code is ever produced) AND, as defense in depth, at the send step.

It is marked ``live`` + ``real_tool`` and skips cleanly when OpenSCAD/OrcaSlicer aren't
present, so the fast inner loop (``pytest -m "not live"``) and tool-less CI both stay green.

TST-6 is a documented manual-verification marker for the managed-engine self-heal (the Ollama
watchdog respawn), which is hard to make hermetic — see the test/docstring below.
"""

from __future__ import annotations

import contextlib
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from kimcad.config import Config
from kimcad.ir import DesignPlan
from kimcad.pipeline import Pipeline
from kimcad.webapp import make_handler

# The same LLM-free provider + real-box renderer + fixed Printer/Material the other suites pin.
from conftest import BAMBU, PLA, FakeProvider
from conftest import box_renderer as _shared_box_renderer


def _box_renderer(extents, *, fail_times=0):
    """conftest.box_renderer returns ``(render_fn, state)``; the Pipeline wants just the
    callable (same unwrap test_webapp.py uses)."""
    render, _state = _shared_box_renderer(extents, fail_times=fail_times)
    return render


def _plan(bbox) -> DesignPlan:
    return DesignPlan(
        object_type="block",
        summary="an integration-test block",
        dimensions={},
        bounding_box_mm=bbox,
        printer="bambu_p2s",
        material="pla",
        open_questions=[],
    )


def _pipeline(provider, renderer, **kw) -> Pipeline:
    return Pipeline(Config.load(), BAMBU, PLA, provider, renderer=renderer, **kw)


@contextlib.contextmanager
def _serve(pipe, root):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(pipe, root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(base, path, body, timeout=300):
    req = urllib.request.Request(
        base + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def _binary_and_profiles_present() -> bool:
    try:
        cfg = Config.load()
        return cfg.binary_path("orcaslicer").exists() and cfg.orca_profiles_root().exists()
    except Exception:  # pragma: no cover - config/binary absent
        return False


@pytest.mark.live  # invokes the real OrcaSlicer; `pytest -m "not live"` skips it
@pytest.mark.real_tool  # needs a fetched OpenSCAD/OrcaSlicer binary; auto-skips when absent
@pytest.mark.skipif(
    not _binary_and_profiles_present(), reason="OrcaSlicer binary/profiles not present"
)
def test_real_render_gate_slice_send_to_mock_as_one_flow(tmp_path):
    """TST-4: the full chain, live, as ONE flow — render -> gate -> slice (real OrcaSlicer) ->
    send to the `mock` connector — plus the gate-failed refusal at the send step.

    The happy path: a 20 mm box whose plan and mesh agree passes the gate, slices to a proven
    motion-bearing toolpath, and is accepted by the mock loopback connector with
    ``sent: true, simulated: true``.

    The refused path: a part whose plan (50 mm) and mesh (20 mm) disagree FAILS the dimensional
    gate. The web slice endpoint refuses to produce G-code for it, and the send endpoint refuses
    to dispatch it (``sent: false, reason: gate_failed``) — so a gate-rejected design can never
    reach a printer even via a direct API client.
    """
    # --- happy path: a well-formed 20 mm box, designed -> gated -> sliced -> sent ----------
    good = _pipeline(FakeProvider(_plan([20, 20, 20])), _box_renderer((20, 20, 20)))
    with _serve(good, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        d = _post(base, "/api/design", {"prompt": "a 20mm block"}, timeout=60)
        assert d["status"] != "gate_failed", "the 20mm box should pass the gate"
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])

        s = _post(base, f"/api/slice/{rid}", {"printer": "bambu_p2s", "material": "pla"})
        assert s["sliced"] is True
        assert s["gcode_lines"] > 100  # a real toolpath, not a near-empty stub

        sent = _post(base, f"/api/send/{rid}", {"connector": "mock"}, timeout=60)
        assert sent["sent"] is True
        assert sent["simulated"] is True
        assert sent["connector"] == "mock" and sent["job_id"]

    # --- refused path: a gate-FAILED variant is blocked at slice AND at send --------------
    bad = _pipeline(FakeProvider(_plan([50, 50, 50])), _box_renderer((20, 20, 20)))  # 50 != 20
    with _serve(bad, tmp_path) as (host, port):
        base = f"http://{host}:{port}"
        d = _post(base, "/api/design", {"prompt": "a 50mm block"}, timeout=60)
        assert d["status"] == "gate_failed"
        rid = int(d["mesh_url"].rsplit("/", 1)[-1])

        # The slice step refuses it: no G-code is produced for a gate-failed part.
        s = _post(base, f"/api/slice/{rid}", {"printer": "bambu_p2s", "material": "pla"})
        assert s["sliced"] is False and s["reason"] == "gate_failed"
        assert "gcode_url" not in s

        # And the send step refuses it too (defense in depth): a direct API client that POSTs a
        # send for the gate-rejected part is turned away rather than dispatching anything. Because
        # the slice was refused, no G-code exists, so the send is rejected — either with a 404
        # ("slice it first", the no-G-code path) or, had a stray G-code entry existed, the typed
        # ``sent: false, reason: gate_failed`` guard. Both outcomes mean: nothing was dispatched.
        req = urllib.request.Request(
            base + f"/api/send/{rid}",
            data=json.dumps({"connector": "mock"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            sent = json.load(urllib.request.urlopen(req, timeout=60))
            assert sent["sent"] is False  # never dispatched
        except urllib.error.HTTPError as e:
            assert e.code == 404  # no G-code was ever produced for the gate-failed part


@pytest.mark.skip(
    reason="TST-6: manual verification only — the managed-engine self-heal (Ollama watchdog "
    "respawn) is hard to make hermetic; see the docstring for the manual procedure."
)
def test_managed_engine_self_heal_is_verified_manually():
    """TST-6 (manual check, intentionally skipped): the managed-engine self-heal — the Ollama
    watchdog detecting a dead/killed `ollama serve` and respawning it — is verified by hand
    rather than in CI, because a hermetic test would have to start, kill, and re-detect a real
    OS process (and the bound port), which is racy and environment-specific.

    Manual procedure (run on a box with Ollama installed and the managed engine enabled):
      1. Start the app with the managed engine: `kimcad web` (the watchdog supervises
         `ollama serve`).  See scripts/ollama_watchdog.py and src/kimcad/ollama_watchdog.py.
      2. Confirm the model answers (the Settings card shows the engine healthy / a design runs).
      3. From another terminal, kill the engine process: `taskkill /IM ollama.exe /F`
         (Windows) or `pkill -f "ollama serve"` (POSIX).
      4. Within the watchdog's poll interval, observe it respawn `ollama serve` (the watchdog
         log line) and the engine return to healthy WITHOUT restarting the app.
      5. Confirm a subsequent design request succeeds against the respawned engine.

    The automated coverage that DOES run: test_ollama_watchdog.py exercises the watchdog's
    decision logic against a fake process (start/dead-detection/backoff) hermetically; this
    marker records that the real end-to-end respawn is a documented manual gate, so the skip is
    honest (a named manual check) rather than a silent gap.
    """
