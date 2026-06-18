"""Unit tests for the managed Ollama runtime (kimcad.ollama_runtime).

UX-COLD-001: KimCad manages a headless Ollama so a fresh machine doesn't dead-end. Every
external effect (locate, probe, spawn, sleep) is injected, so the orchestration is proven here
without a real binary/socket/subprocess; the real fetch→serve path has a separate real_tool test.
"""

from __future__ import annotations

from pathlib import Path

from kimcad import ollama_runtime as ort


# --- find_system_ollama -----------------------------------------------------------------------


def test_find_system_ollama_prefers_path() -> None:
    found = ort.find_system_ollama(which=lambda name: r"C:\tools\ollama.exe" if name == "ollama" else None)
    assert found == Path(r"C:\tools\ollama.exe")


def test_find_system_ollama_falls_back_to_default_install_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ort.os, "name", "nt")
    progs = tmp_path / "Programs" / "Ollama"
    progs.mkdir(parents=True)
    (progs / "ollama.exe").write_text("stub")
    found = ort.find_system_ollama(which=lambda _name: None, localappdata=str(tmp_path))
    assert found == progs / "ollama.exe"


def test_find_system_ollama_none_when_absent(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ort.os, "name", "nt")
    assert ort.find_system_ollama(which=lambda _name: None, localappdata=str(tmp_path)) is None


# --- resolve_ollama_exe -----------------------------------------------------------------------


def test_resolve_prefers_system_over_managed(tmp_path: Path) -> None:
    managed = tmp_path / "ollama.exe"
    managed.write_text("managed")  # exists, but system should win
    got = ort.resolve_ollama_exe(
        which=lambda name: r"C:\sys\ollama.exe" if name == "ollama" else None,
        managed_exe=managed,
    )
    assert got == Path(r"C:\sys\ollama.exe")


def test_resolve_falls_back_to_managed_when_no_system(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ort.os, "name", "nt")
    managed = tmp_path / "ollama.exe"
    managed.write_text("managed")
    got = ort.resolve_ollama_exe(which=lambda _n: None, localappdata=str(tmp_path / "nope"), managed_exe=managed)
    assert got == managed


def test_resolve_none_when_nothing_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(ort.os, "name", "nt")
    missing = tmp_path / "absent" / "ollama.exe"
    got = ort.resolve_ollama_exe(which=lambda _n: None, localappdata=str(tmp_path / "nope"), managed_exe=missing)
    assert got is None


# --- is_server_up -----------------------------------------------------------------------------


def test_is_server_up_true_false() -> None:
    assert ort.is_server_up("http://x/v1", probe=lambda _u: True) is True
    assert ort.is_server_up("http://x/v1", probe=lambda _u: False) is False


def test_is_server_up_swallows_probe_errors() -> None:
    def boom(_u: str) -> bool:
        raise ConnectionError("refused")

    assert ort.is_server_up("http://x/v1", probe=boom) is False


# --- start_serve ------------------------------------------------------------------------------


def test_start_serve_invokes_serve_with_loopback_host() -> None:
    calls: dict[str, object] = {}

    def fake_spawn(args, **kwargs):
        calls["args"] = args
        calls["env"] = kwargs.get("env")
        return "PROC"

    exe = Path("/x/ollama")
    proc = ort.start_serve(exe, spawn=fake_spawn, env={})
    assert proc == "PROC"
    assert calls["args"] == [str(exe), "serve"]
    assert calls["env"]["OLLAMA_HOST"] == ort.DEFAULT_HOST
    # OLLAMA_MODELS must be pinned to KimCad's data dir so models are removed by uninstall
    # (tester-007 Minor-2: default ~/.ollama orphans 7+ GB after uninstall).
    from kimcad.paths import writable_root
    assert calls["env"]["OLLAMA_MODELS"] == str(writable_root() / "models")


# --- ensure_serving (the orchestration) -------------------------------------------------------


def test_ensure_serving_reuses_already_up_server() -> None:
    started: list[Path] = []
    st = ort.ensure_serving(
        is_up=lambda _u: True,
        resolve=lambda: (_ for _ in ()).throw(AssertionError("must not resolve when already up")),
        start=lambda e: started.append(e),
    )
    assert st.running is True and st.source == "already-up"
    assert started == []  # touched nothing


def test_ensure_serving_needs_fetch_when_no_executable() -> None:
    st = ort.ensure_serving(is_up=lambda _u: False, resolve=lambda: None, start=lambda e: None)
    assert st.running is False and st.source == "needs-fetch" and st.exe is None


def test_ensure_serving_starts_then_becomes_healthy() -> None:
    exe = Path("/x/ollama")
    started: list[Path] = []
    # down, down (after start), then up
    seq = iter([False, False, True])

    st = ort.ensure_serving(
        is_up=lambda _u: next(seq),
        resolve=lambda: exe,
        start=lambda e: started.append(e),
        sleep=lambda _s: None,
        poll_s=0.01,
        wait_s=1.0,
    )
    assert started == [exe]
    assert st.running is True and st.source == "started" and st.exe == exe


def test_ensure_serving_background_invokes_ensure(monkeypatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(
        ort, "ensure_serving", lambda base_url=ort.DEFAULT_BASE_URL, **k: called.append(base_url)
    )
    t = ort.ensure_serving_background("http://x/v1")
    t.join(timeout=2.0)
    assert called == ["http://x/v1"]


def test_ensure_serving_unavailable_when_start_never_healthy() -> None:
    exe = Path("/x/ollama")
    st = ort.ensure_serving(
        is_up=lambda _u: False,  # never comes up
        resolve=lambda: exe,
        start=lambda e: None,
        sleep=lambda _s: None,
        poll_s=0.1,
        wait_s=0.3,
    )
    assert st.running is False and st.source == "unavailable" and st.exe == exe


# --- ENG-GG-001: managed-process teardown (no orphan `ollama serve`) ---------------------------


class _FakeProc:
    """A stand-in for subprocess.Popen recording terminate/kill/wait for the teardown tests."""

    def __init__(self, alive: bool = True) -> None:
        self._alive = alive
        self.pid = 4242
        self.terminated = False
        self.killed = False

    def poll(self):
        return None if self._alive else 0

    def terminate(self):
        self.terminated = True
        self._alive = False

    def kill(self):
        self.killed = True
        self._alive = False

    def wait(self, timeout=None):  # noqa: ARG002
        return 0


def test_stop_managed_terminates_a_started_server(monkeypatch) -> None:
    proc = _FakeProc(alive=True)
    monkeypatch.setattr(ort, "_managed_proc", proc, raising=False)
    ort.stop_managed()
    assert proc.terminated is True
    assert ort._managed_proc is None  # cleared so a second call is a no-op


def test_stop_managed_is_a_noop_when_nothing_started(monkeypatch) -> None:
    monkeypatch.setattr(ort, "_managed_proc", None, raising=False)
    ort.stop_managed()  # must not raise
    assert ort._managed_proc is None


def test_stop_managed_does_not_terminate_an_already_exited_proc(monkeypatch) -> None:
    proc = _FakeProc(alive=False)  # poll() -> 0 (already gone)
    monkeypatch.setattr(ort, "_managed_proc", proc, raising=False)
    ort.stop_managed()
    assert proc.terminated is False and proc.killed is False
    assert ort._managed_proc is None


def test_injected_start_never_records_a_managed_proc(monkeypatch) -> None:
    """A reused system server (already-up) AND any injected-effect unit run must leave the module's
    managed-process state untouched — we only ever tear down a server WE started on the real path."""
    monkeypatch.setattr(ort, "_managed_proc", None, raising=False)
    exe = Path("/x/ollama")
    seq = iter([False, False, True])
    st = ort.ensure_serving(
        is_up=lambda _u: next(seq),
        resolve=lambda: exe,
        start=lambda e: _FakeProc(),  # injected → started_by_default is False
        sleep=lambda _s: None,
        poll_s=0.01,
        wait_s=1.0,
    )
    assert st.source == "started"
    assert ort._managed_proc is None  # injected path did NOT record (no global pollution)
