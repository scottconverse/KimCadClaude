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
from kimcad.model_pull import ModelPullJob, is_loopback_url, ollama_native_root
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


def test_a_disk_full_error_maps_to_the_friendly_fix():
    def opener(req, timeout=None):
        return _FakeStream([{"error": "write /models/blobs: no space left on device"}])

    job = ModelPullJob()
    job.start("http://127.0.0.1:11434", [("gemma4:e4b", "chat")], probe_dir=Path.cwd(), opener=opener)
    snap = _wait_done(job)
    assert "disk filled up" in snap["models"]["gemma4:e4b"]["error"]
    assert "13 GB" in snap["models"]["gemma4:e4b"]["error"]


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


def test_pull_reports_a_down_ollama_as_a_typed_status(tmp_path, monkeypatch):
    import kimcad.model_advisor as ma

    monkeypatch.setattr(ma, "probe_ollama", lambda url: (False, []))
    with _serve(tmp_path, _cfg()) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/model-pull")
    assert status == 200
    assert data["status"] == "ollama_down"
    assert "start it" in data["error"].lower()


def test_pull_starts_only_the_missing_models_fixed_server_side(tmp_path, monkeypatch):
    """The chat model is present, the vision model isn't — exactly the vision model is
    pulled, and the list came from CONFIG, not from any request body."""
    import kimcad.model_advisor as ma

    class _M:
        def __init__(self, name):
            self.name = name

    monkeypatch.setattr(ma, "probe_ollama", lambda url: (True, [_M("gemma4:e4b")]))
    started: dict = {}

    def fake_start(self, base, missing, **kw):
        started["base"] = base
        started["missing"] = missing
        return {"running": True, "models": {n: {"status": "queued"} for n, _ in missing}}

    monkeypatch.setattr(mp.ModelPullJob, "start", fake_start)
    with _serve(tmp_path, _cfg()) as (host, port):
        status, data = _jreq(host, port, "POST", "/api/model-pull")
    assert status == 200 and data["status"] == "ok"
    assert started["base"] == "http://127.0.0.1:11434"  # native root, not the /v1 base
    assert started["missing"] == [("qwen2.5vl:3b", "vision")]
