"""Stage 10 Slice 10.4 — in-app model downloads: the pull job (unit, fake stream) and the
webapp routes (typed statuses, the fixed server-side pull list, the loopback-only rule)."""

from __future__ import annotations

import contextlib
import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import kimcad.model_pull as mp
from kimcad.config import Config
from kimcad.model_pull import (
    _ENGINE_EST_GB,
    _ENGINE_ROW,
    _EST_GB,
    ModelPullJob,
    is_loopback_url,
    ollama_native_root,
)
from kimcad.webapp import make_handler


class _FakeStream:
    """A context-managed iterable of pull-progress lines, like urlopen on /api/pull."""

    def __init__(self, lines: list[dict]):
        self._lines = [json.dumps(line).encode() + b"\n" for line in lines]

    def __enter__(self):
        return iter(self._lines)

    def __exit__(self, *a):
        return False


def _wait_done(job: ModelPullJob, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snap = job.snapshot()
        if not snap["running"]:
            return snap
        time.sleep(0.02)
    raise AssertionError("pull job never finished")


# --- the job (unit) ----------------------------------------------------------------------


def test_pull_tracks_progress_and_finishes_done():
    calls: list[str] = []

    def opener(req, timeout=None):
        calls.append(req.full_url)
        return _FakeStream([
            {"status": "pulling abc", "total": 1000, "completed": 250},
            {"status": "pulling abc", "total": 1000, "completed": 1000},
            {"status": "success"},
        ])

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("gemma4:e4b", "chat")], probe_dir=Path.cwd(), opener=opener)
    snap = _wait_done(job)
    m = snap["models"]["gemma4:e4b"]
    assert m["status"] == "done"
    assert m["completed"] == 1000 and m["total"] == 1000
    assert calls == ["http://127.0.0.1:11434/api/pull"]


def test_a_failed_chat_pull_does_not_block_the_vision_pull():
    """Each model is independently useful (words-only design vs the image on-ramps)."""

    def opener(req, timeout=None):
        if b"gemma4" in req.data:
            return _FakeStream([{"error": "pull model manifest: not found"}])
        return _FakeStream([{"status": "success", "total": 10, "completed": 10}])

    job = ModelPullJob()
    job.start(
        "http://127.0.0.1:11434",
        [("gemma4:e4b", "chat"), ("qwen2.5vl:3b", "vision")],
        probe_dir=Path.cwd(), opener=opener,
    )
    snap = _wait_done(job)
    assert snap["models"]["gemma4:e4b"]["status"] == "error"
    assert "internet connection" in snap["models"]["gemma4:e4b"]["error"]
    assert snap["models"]["qwen2.5vl:3b"]["status"] == "done"


def test_a_runaway_upstream_error_is_clipped_in_the_display_string():
    # ENG-012: a hostile/runaway streamed-JSON `error` (e.g. a megabyte of attacker text) must
    # not be interpolated unbounded into the user-facing message — clip to the codebase's [:300].
    huge = "Z" * 5000  # an unrecognized error so it hits the generic "The download stopped: …" arm

    def opener(req, timeout=None):
        return _FakeStream([{"error": huge}])

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("gemma4:e4b", "chat")], probe_dir=Path.cwd(), opener=opener)
    snap = _wait_done(job)
    msg = snap["models"]["gemma4:e4b"]["error"]
    assert msg.count("Z") == 300  # exactly the [:300] window, not all 5000 chars
    assert "The download stopped" in msg


def test_friendly_error_clips_raw_text_directly():
    # ENG-012 at the unit boundary: _friendly_error never echoes more than 300 chars of raw text.
    assert mp._friendly_error("Q" * 1000).count("Q") == 300


# --- UX-COLD-001: one-click cold setup (ensure runtime, then pull) ------------------------


def _ok_opener(req, timeout=None):
    return _FakeStream([{"status": "success", "total": 10, "completed": 10}])


def test_setup_server_already_up_pulls_missing_only():
    """Server already running -> the engine row completes instantly and only the MISSING model
    is pulled; KimCad never fetches a runtime it doesn't need."""
    from kimcad.model_advisor import InstalledModel

    def _no_resolve():
        raise AssertionError("must not resolve/fetch a runtime when the server is already up")

    job = ModelPullJob()
    job.start_setup(
        "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
        opener=_ok_opener, is_up=lambda _u: True, resolve=_no_resolve,
        probe=lambda _u, timeout=3.0: (True, [InstalledModel(name="qwen2.5:7b")]),
        sleep=lambda _s: None,
    )
    snap = _wait_done(job)
    assert snap["models"][_ENGINE_ROW]["status"] == "done"
    assert snap["models"]["qwen2.5vl:3b"]["status"] == "done"  # missing vision model pulled
    assert "qwen2.5:7b" not in snap["models"]  # chat already present -> not re-pulled


def test_setup_cold_fetches_runtime_then_pulls(tmp_path):
    """No system Ollama -> fetch the portable runtime (its bytes drive the engine row), start it,
    then pull both models. The whole cold path in one flow."""
    state = {"served": False}

    def _fetch(managed_dir, progress=None):
        if progress:
            progress(700, 1400)
            progress(1400, 1400)
        return managed_dir / "ollama.exe"

    job = ModelPullJob()
    job.start_setup(
        "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
        opener=_ok_opener,
        is_up=lambda _u: state["served"],
        resolve=lambda: None,
        fetch=_fetch,
        serve=lambda _e: state.__setitem__("served", True),
        probe=lambda _u, timeout=3.0: (True, []),  # nothing installed -> pull both
        managed_dir=tmp_path, sleep=lambda _s: None, wait_s=1.0, poll_s=0.01,
    )
    snap = _wait_done(job)
    assert snap["models"][_ENGINE_ROW]["status"] == "done"
    assert snap["models"][_ENGINE_ROW]["total"] == 1400  # fetch progress rode the engine row
    assert snap["models"]["qwen2.5:7b"]["status"] == "done"
    assert snap["models"]["qwen2.5vl:3b"]["status"] == "done"


def test_setup_fetch_failure_marks_engine_error(tmp_path):
    from kimcad.ollama_fetch import OllamaFetchError

    def _boom(managed_dir, progress=None):
        raise OllamaFetchError("integrity check failed")

    job = ModelPullJob()
    job.start_setup(
        "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
        is_up=lambda _u: False, resolve=lambda: None, fetch=_boom,
        managed_dir=tmp_path, sleep=lambda _s: None,
    )
    snap = _wait_done(job)
    assert snap["models"][_ENGINE_ROW]["status"] == "error"
    assert "integrity" in snap["models"][_ENGINE_ROW]["error"]
    assert set(snap["models"]) == {_ENGINE_ROW}  # never got the runtime up -> no model rows


def test_setup_serve_never_healthy_errors():
    job = ModelPullJob()
    job.start_setup(
        "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
        is_up=lambda _u: False,  # never comes up
        resolve=lambda: Path("/x/ollama"),
        serve=lambda _e: None, sleep=lambda _s: None, wait_s=0.05, poll_s=0.01,
    )
    snap = _wait_done(job)
    assert snap["models"][_ENGINE_ROW]["status"] == "error"
    assert "didn't come up" in snap["models"][_ENGINE_ROW]["error"]


def test_free_gb_probes_writable_root_in_installed_mode(monkeypatch, tmp_path):
    """TE-002: in installed mode _free_gb_on_receiving_drive must use writable_root()/"models"
    (set by KIMCAD_INSTALL_ROOT) instead of reading OLLAMA_MODELS from the parent env."""
    import shutil

    import kimcad.model_pull as mp_mod

    probed: list[object] = []
    real_usage = shutil.disk_usage

    def _fake_usage(path):
        probed.append(path)
        return real_usage(tmp_path)  # probe tmp_path so it succeeds on any OS

    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(tmp_path))
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "should_not_be_used"))
    monkeypatch.setattr(shutil, "disk_usage", _fake_usage)
    # Also patch it inside model_pull's own module namespace
    monkeypatch.setattr(mp_mod.shutil, "disk_usage", _fake_usage)
    mp_mod._free_gb_on_receiving_drive()
    assert probed, "disk_usage was never called"
    assert str(probed[0]).endswith("models"), (
        f"Expected probe under writable_root()/models, got {probed[0]}"
    )
    assert "should_not_be_used" not in str(probed[0]), (
        "Installed mode must not read OLLAMA_MODELS from the parent env"
    )


def test_a_disk_full_error_maps_to_the_friendly_fix():
    def opener(req, timeout=None):
        return _FakeStream([{"error": "write /models/blobs: no space left on device"}])

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("gemma4:e4b", "chat")], probe_dir=Path.cwd(), opener=opener)
    snap = _wait_done(job)
    assert "disk filled up" in snap["models"]["gemma4:e4b"]["error"]
    assert "7.7 GB" in snap["models"]["gemma4:e4b"]["error"]


def test_the_disk_precheck_fails_friendly_before_any_download(monkeypatch):
    """The common failure (a small SSD) is caught BEFORE gigabytes move."""
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(mp.shutil, "disk_usage", lambda p: Usage(100, 96, 4 * (1024**3)))
    opened: list = []

    job = ModelPullJob()
    snap = job.start(
        "http://127.0.0.1:11434", [("gemma4:e4b", "chat")],
        opener=lambda *a, **k: opened.append(a) or _FakeStream([]),
    )
    assert opened == []  # nothing was downloaded
    m = snap["models"]["gemma4:e4b"]
    assert m["status"] == "error"
    assert "Not enough disk space" in m["error"]


def test_start_is_idempotent_while_running():
    release = threading.Event()

    class _Blocking:
        def __enter__(self):
            release.wait(5)
            return iter([])

        def __exit__(self, *a):
            return False

    job = ModelPullJob()
    job.start("http://x", [("a", "chat")], probe_dir=Path.cwd(), opener=lambda *a, **k: _Blocking())
    snap2 = job.start("http://x", [("a", "chat"), ("b", "vision")], probe_dir=Path.cwd(),
                      opener=lambda *a, **k: _Blocking())
    assert snap2["running"] is True
    assert set(snap2["models"]) == {"a"}  # the SECOND start didn't fork a new pull list
    release.set()
    _wait_done(job)


def test_setup_is_idempotent_while_running(tmp_path):
    """TEST-GG-005: like start()'s idempotency, but for the one-click start_setup — two calls
    while a setup runs must yield ONE worker thread (a wizard re-mount can't fork a second
    runtime fetch/serve). Block in serve() so the worker stays alive across both calls."""
    release = threading.Event()
    serve_calls: list = []

    def _blocking_serve(_exe):
        serve_calls.append(1)
        release.wait(5)

    def _start():
        return job.start_setup(
            "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
            is_up=lambda _u: False, resolve=lambda: Path("/x/ollama"),
            serve=_blocking_serve, probe=lambda _u, timeout=3.0: (True, []),
            managed_dir=tmp_path, sleep=lambda _s: None, wait_s=1.0, poll_s=0.01,
        )

    job = ModelPullJob()
    _start()
    # spin until the worker is actually inside the blocking serve, so the 2nd call races a
    # genuinely-running job (not a not-yet-started thread).
    deadline = time.monotonic() + 5.0
    while not serve_calls and time.monotonic() < deadline:
        time.sleep(0.01)
    snap2 = _start()
    assert snap2["running"] is True
    release.set()
    _wait_done(job)
    assert serve_calls == [1]  # exactly one worker ran; the 2nd start_setup didn't fork


def test_doc_and_code_disk_estimates_fit_the_documented_headroom():
    """ENG-GG-002 / DOC-101: the rough model+engine estimates must fit under the documented
    12 GB free-disk headroom. Pin it so the contradiction (chat+vision+engine > the headroom)
    can never silently return — if someone bumps a size, this test forces a doc reconciliation."""
    documented_free_gb = 12.0
    assert sum(_EST_GB.values()) + _ENGINE_EST_GB <= documented_free_gb


def test_setup_disk_precheck_fails_before_fetch_or_pull(monkeypatch, tmp_path):
    """ENG-GG-002 / TEST-GG-002: the cold one-click path pre-checks disk BEFORE moving a byte.
    With the receiving drive nearly full, the engine row errors with 'Not enough disk space' and
    neither the runtime fetch nor the per-model opener is ever called."""
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(mp.shutil, "disk_usage", lambda p: Usage(100, 99, 1 * (1024**3)))
    fetched: list = []
    opened: list = []

    job = ModelPullJob()
    job.start_setup(
        "http://127.0.0.1:11434", "qwen2.5:7b", "qwen2.5vl:3b",
        opener=lambda *a, **k: opened.append(a) or _ok_opener(*a, **k),
        is_up=lambda _u: False,
        resolve=lambda: None,  # -> a fetch WOULD be needed (so the engine size counts too)
        fetch=lambda *a, **k: fetched.append(a) or (tmp_path / "ollama.exe"),
        serve=lambda _e: None,
        probe=lambda _u, timeout=3.0: (True, []),
        managed_dir=tmp_path, sleep=lambda _s: None, wait_s=1.0, poll_s=0.01,
    )
    snap = _wait_done(job)
    assert snap["models"][_ENGINE_ROW]["status"] == "error"
    assert "Not enough disk space" in snap["models"][_ENGINE_ROW]["error"]
    assert fetched == []  # the runtime was never fetched
    assert opened == []  # no model pull was ever opened
    assert set(snap["models"]) == {_ENGINE_ROW}  # never reached the per-model rows


def test_native_root_and_loopback_helpers():
    assert ollama_native_root("http://localhost:11434/v1") == "http://localhost:11434"
    assert ollama_native_root("http://127.0.0.1:11434/ollama/v1") == "http://127.0.0.1:11434"
    assert is_loopback_url("http://localhost:11434/v1") is True
    assert is_loopback_url("http://127.0.0.1:11434/v1") is True
    assert is_loopback_url("http://[::1]:11434/v1") is True
    assert is_loopback_url("http://192.168.0.9:11434/v1") is False
    assert is_loopback_url("https://api.example.com/v1") is False
    # ENG-005 (slice-10.4 audit): a HOSTNAME that merely starts with "127." is not loopback.
    assert is_loopback_url("http://127.evil.example:11434/v1") is False


def test_is_loopback_url_delegates_to_config_and_agrees_on_adversarial_hosts():
    """ENG-GG-005: is_loopback_url now delegates to Config._is_local_base_url (one source of
    truth), while keeping its own host-OR-url input contract. The two classifiers must agree on
    every adversarial host Engineering checked — pin that agreement so they can't drift apart."""
    # bare host / host:port AND full-URL forms; loopback (True) vs not (False).
    cases = {
        "127.0.0.1": True,
        "127.0.0.1:11434": True,
        "localhost": True,
        "localhost:11434": True,
        "127.evil.example": False,  # prefix trick, not loopback
        "192.168.0.9": False,
        "http://localhost:11434/v1": True,
        "http://127.0.0.1:11434/v1": True,
        "http://[::1]:11434/v1": True,
        "http://192.168.0.9:11434/v1": False,
        "https://api.example.com/v1": False,
    }
    for host, expected in cases.items():
        assert is_loopback_url(host) is expected, host
        # and the URL-form classification matches Config's single source of truth exactly.
        url = host if "//" in host else f"http://{host}"
        assert is_loopback_url(host) is Config._is_local_base_url(url), host


def test_a_new_start_replaces_the_previous_runs_states(monkeypatch):
    """ENG-002 (slice-10.4 audit): run 1's 'done' must never read as run 2's outcome —
    reproduced on the disk-precheck path before the fix."""
    from collections import namedtuple

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("gemma4:e4b", "chat")], probe_dir=Path.cwd(),
              opener=lambda *a, **k: _FakeStream([{"status": "success"}]))
    _wait_done(job)
    assert job.snapshot()["models"]["gemma4:e4b"]["status"] == "done"

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(mp.shutil, "disk_usage", lambda p: Usage(100, 96, 1 * (1024**3)))
    snap = job.start("http://127.0.0.1:11434", [("qwen2.5vl:3b", "vision")])
    assert set(snap["models"]) == {"qwen2.5vl:3b"}  # no residue from run 1
    # And a no-op start clears too.
    assert job.start("http://127.0.0.1:11434", [])["models"] == {}


def test_disk_precheck_measures_the_ollama_models_drive(monkeypatch):
    """ENG-003: OLLAMA_MODELS relocates the blobs — measure THAT drive, not blindly home."""
    seen: list = []
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setenv("OLLAMA_MODELS", "D:\\models")
    monkeypatch.setattr(mp.shutil, "disk_usage", lambda p: seen.append(p) or Usage(1, 0, 999 * (1024**3)))
    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("a", "chat")],
              opener=lambda *a, **k: _FakeStream([{"status": "success"}]))
    _wait_done(job)
    assert seen[0] == "D:\\models"


def test_progress_never_regresses_to_a_smaller_layer():
    """UX-002: Ollama reports totals PER LAYER — a small trailing layer must not yank the
    visible percent backward."""

    def opener(req, timeout=None):
        return _FakeStream([
            {"status": "pulling big", "total": 1000, "completed": 900},
            {"status": "pulling small", "total": 10, "completed": 1},  # the config layer
            {"status": "success"},
        ])

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("a", "chat")], probe_dir=Path.cwd(), opener=opener)
    snap = _wait_done(job)
    assert snap["models"]["a"]["total"] == 1000  # the big layer stayed the yardstick
    assert snap["models"]["a"]["completed"] == 900


# --- the routes --------------------------------------------------------------------------


def _cfg(base_url: str = "http://127.0.0.1:11434/v1") -> Config:
    return Config({"llm": {"active": "local", "backends": {"local": {
        "provider": "ollama", "base_url": base_url, "model_name": "gemma4:e4b",
    }}}})


@contextlib.contextmanager
def _serve(tmp_path, config):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(object(), tmp_path / "web", config=config))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield "127.0.0.1", httpd.server_address[1]
    finally:
        httpd.shutdown()
        httpd.server_close()


def _jreq(host, port, method, path):
    conn = http.client.HTTPConnection(host, port, timeout=20)
    try:
        conn.request(method, path)
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    finally:
        conn.close()


def test_progress_route_returns_the_job_snapshot(tmp_path):
    with _serve(tmp_path, _cfg()) as (host, port):
        status, data = _jreq(host, port, "GET", "/api/model-pull/progress")
    assert status == 200
    assert "running" in data and "models" in data


def test_pull_refuses_demo_mode(tmp_path):
    """ENG-004 (slice-10.4 audit): a demo-mode walkthrough click must never start a real
    multi-GB download."""
    from types import SimpleNamespace

    from kimcad.webapp import DemoProvider

    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        make_handler(SimpleNamespace(provider=DemoProvider()), tmp_path / "web", config=_cfg()),
    )
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        status, data = _jreq("127.0.0.1", httpd.server_address[1], "POST", "/api/model-pull")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 400
    assert data["status"] == "not_local"
    assert "Demo mode" in data["error"]


def test_pull_refuses_a_non_loopback_backend(tmp_path):
    """The wizard's button manages THIS computer's install — never a remote box."""
    with _serve(tmp_path, _cfg("http://192.168.0.9:11434/v1")) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/model-pull")
    assert status == 400
    assert data["status"] == "not_local"


def test_pull_down_ollama_triggers_setup_not_a_deadend(tmp_path, monkeypatch):
    """UX-COLD-001 (cold-start audit): a down/absent Ollama no longer dead-ends ("go start it
    yourself"). The POST kicks the one-click setup (ensure the runtime, then pull) — we assert the
    handler invokes start_setup, not the old ollama_down bail."""
    called: dict = {}

    def fake_start_setup(self, base, chat, vision, **kw):
        called["yes"] = True
        return {"running": True, "models": {_ENGINE_ROW: {"status": "pulling"}}}

    monkeypatch.setattr(mp.ModelPullJob, "start_setup", fake_start_setup)
    with _serve(tmp_path, _cfg()) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/model-pull")
    assert status == 200 and data["status"] == "ok"
    assert called.get("yes") is True  # setup was kicked, not a dead-end
    assert data["status"] != "ollama_down"  # the old dead-end is gone


def test_pull_ignores_an_attacker_named_model_in_the_body(tmp_path, monkeypatch):
    """TEST-1002 (stage-10 gate): the pull list is fixed SERVER-side. A request body
    naming a model must change NOTHING — this pins the trust rule adversarially, so a
    future convenience `data.get("model")` read fails loudly."""

    started: dict = {}

    def fake_start_setup(self, base, chat, vision, **kw):
        started.update(chat=chat, vision=vision)
        return {"running": True, "models": {}}

    monkeypatch.setattr(mp.ModelPullJob, "start_setup", fake_start_setup)
    with _serve(tmp_path, _cfg()) as (host, port):
        conn = http.client.HTTPConnection(host, port, timeout=20)
        try:
            body = json.dumps({"model": "evil/backdoored:latest", "models": ["evil:1"]}).encode()
            conn.request("POST", "/api/model-pull", body=body,
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            data = json.loads(resp.read())
        finally:
            conn.close()
    assert resp.status == 200 and data["status"] == "ok"
    # The model names come from CONFIG (chat + vision), never the request body.
    assert started["chat"] == "gemma4:e4b" and started["vision"] == "qwen2.5vl:3b"
    assert "evil" not in started["chat"] and "evil" not in started["vision"]


def test_pull_refuses_an_absurd_body_with_a_typed_413(tmp_path):
    """QA-1003 (stage-10 gate) + gate-integrity 2026-06-13: a giant body gets a clean, typed
    413 — NOT a Windows connection reset. The handler must drain the inbound body before
    closing; an undrained close RSTs the client's read of the 413 (ConnectionAbortedError).
    The original 100 KB body fit the loopback socket buffer, so the reset stayed latent/flaky
    (it slipped a real failure past the gate on 2026-06-13). A 2 MiB body exceeds the buffer,
    making the race deterministic; the loop hardens it."""
    big = b"x" * (2 * 1024 * 1024)  # > the socket buffer -> a no-drain close surfaces the RST
    with _serve(tmp_path, _cfg()) as (host, port):
        for _ in range(5):
            conn = http.client.HTTPConnection(host, port, timeout=20)
            try:
                conn.request("POST", "/api/model-pull", body=big,
                             headers={"Content-Type": "application/octet-stream"})
                resp = conn.getresponse()
                data = json.loads(resp.read())
            finally:
                conn.close()
            assert resp.status == 413
            assert "no request body" in data["error"]


def test_concurrent_starts_never_fork_a_second_pull():
    """TEST-1006 (stage-10 gate): N threads racing start() yield ONE worker (the
    already-fixed deadlock's sibling hazard), and the test is bounded — a regression
    deadlock fails as a red assertion, not a hung suite."""
    release = threading.Event()
    opened: list = []

    class _Gated:
        def __enter__(self):
            opened.append(1)
            release.wait(5)
            return iter([json.dumps({"status": "success"}).encode()])

        def __exit__(self, *a):
            return False

    job = ModelPullJob()
    results: list = []

    def racer():
        results.append(job.start("http://127.0.0.1:11434", [("a", "chat")],
                                 probe_dir=Path.cwd(), opener=lambda *a, **k: _Gated()))

    threads = [threading.Thread(target=racer) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert not any(t.is_alive() for t in threads), "start() deadlocked under contention"
    release.set()
    _wait_done(job)
    assert len(opened) == 1  # exactly one pull ran, no matter how many starts raced
    assert len(results) == 8  # every racer got a snapshot back


def test_pull_setup_uses_native_root_and_config_models(tmp_path, monkeypatch):
    """The handler delegates to start_setup with the NATIVE (host-rooted) URL and the chat +
    vision model names from CONFIG — never a request body. Which of those are actually missing is
    decided inside start_setup (see test_setup_server_already_up_pulls_missing_only)."""
    started: dict = {}

    def fake_start_setup(self, base, chat, vision, **kw):
        started.update(base=base, chat=chat, vision=vision)
        return {"running": True, "models": {}}

    monkeypatch.setattr(mp.ModelPullJob, "start_setup", fake_start_setup)
    with _serve(tmp_path, _cfg()) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/model-pull")
    assert status == 200 and data["status"] == "ok"
    assert started["base"] == "http://127.0.0.1:11434"  # native root, not the /v1 base
    assert started["chat"] == "gemma4:e4b" and started["vision"] == "qwen2.5vl:3b"
