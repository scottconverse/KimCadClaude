"""Managed local Ollama runtime — make KimCad's AI work without the user installing Ollama.

UX-COLD-001 (2026-06-17 cold-start audit): a fresh machine has no Ollama, and the old
first-run just told the user to leave, install the full Ollama program, start it, and poll a
"check again" button — a multi-step manual detour before anything worked. Instead KimCad now
MANAGES a headless Ollama:

- **Reuse** a system Ollama if one is already installed/running (don't fight the user's setup);
- else **use a portable Ollama** KimCad fetched into its own per-user data dir (the
  `ollama-windows-amd64.zip` standalone build, MIT-licensed, intended by Ollama "for embedding
  Ollama in existing applications, or running it as a system service via `ollama serve`");
- start `ollama serve` as a **managed subprocess**, health-check it, and stop it with the app.

The model download stays the existing in-app, progress-bearing :mod:`kimcad.model_pull` flow —
this module only ensures the *server* is present and running. Everything here takes its external
effects (locate, probe, spawn, sleep) as injectable callables so the orchestration is unit-tested
without a real binary, socket, or subprocess (the b5 lesson: prove behaviour, don't mock the
effect away — the REAL fetch+serve path is exercised by a `real_tool` integration test).

The fetch/extract/verify of the portable binary lives in :mod:`kimcad.ollama_fetch` (network) so
this module stays import-light and pure.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from kimcad.paths import writable_root

# KimCad always manages Ollama on its conventional loopback port; the shipped local backend's
# base_url points here. We never bind a non-loopback host — the model server is for this machine.
DEFAULT_HOST = "127.0.0.1:11434"
DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"


def _exe_name() -> str:
    return "ollama.exe" if os.name == "nt" else "ollama"


# --- locating a usable ollama executable ------------------------------------------------------


def find_system_ollama(
    *,
    which: Callable[[str], str | None] | None = None,
    localappdata: str | None = None,
) -> Path | None:
    """A system-installed ``ollama`` executable, or None. Reuse the user's own Ollama before we
    ever fetch our own (don't duplicate a multi-GB runtime they already have). Mirrors the
    locate logic proven in ``scripts/ollama_watchdog.py``: PATH first, then the default Windows
    per-user install dir. ``which``/``localappdata`` are injectable for testing."""
    import shutil

    which = which or shutil.which
    found = which("ollama")
    if found:
        return Path(found)
    if os.name == "nt":
        la = localappdata if localappdata is not None else os.environ.get("LOCALAPPDATA", "")
        if la:
            cand = Path(la) / "Programs" / "Ollama" / "ollama.exe"
            if cand.exists():
                return cand
    return None


def managed_dir() -> Path:
    """Where KimCad keeps the portable Ollama it fetched — under the per-user writable data root
    (never the read-only install tree), alongside the rest of KimCad's app data."""
    return writable_root() / "ollama"


def managed_ollama_exe() -> Path:
    """The path to KimCad's own (portable) ``ollama`` executable — may not exist yet."""
    return managed_dir() / _exe_name()


def resolve_ollama_exe(
    *,
    which: Callable[[str], str | None] | None = None,
    localappdata: str | None = None,
    managed_exe: Path | None = None,
) -> Path | None:
    """The ollama executable KimCad should use: a system install if present, else KimCad's own
    portable copy if it's already been fetched, else None (the caller must fetch one first).
    ``managed_exe`` is injectable for testing; defaults to :func:`managed_ollama_exe`."""
    sys_exe = find_system_ollama(which=which, localappdata=localappdata)
    if sys_exe is not None:
        return sys_exe
    managed = managed_exe if managed_exe is not None else managed_ollama_exe()
    return managed if managed.exists() else None


# --- health probe -----------------------------------------------------------------------------


def is_server_up(
    base_url: str = DEFAULT_BASE_URL,
    *,
    probe: Callable[[str], bool] | None = None,
) -> bool:
    """True when an Ollama server answers at ``base_url``. Reuses the proven
    :func:`kimcad.model_advisor.probe_ollama` reachability check; any error (refused, timeout)
    reads as down, never an exception. ``probe`` is injectable for testing."""
    if probe is None:
        from kimcad.model_advisor import probe_ollama

        def probe(u: str) -> bool:
            running, _ = probe_ollama(u)
            return bool(running)

    try:
        return bool(probe(base_url))
    except Exception:  # noqa: BLE001 — a probe failure is "down", never a crash
        return False


# --- starting a managed `ollama serve` --------------------------------------------------------


class _Spawn(Protocol):
    def __call__(self, args: list[str], **kwargs: object) -> object: ...


def start_serve(
    exe: Path,
    *,
    host: str = DEFAULT_HOST,
    spawn: _Spawn | None = None,
    env: dict[str, str] | None = None,
) -> object:
    """Launch ``ollama serve`` headless as a managed child. ``OLLAMA_HOST`` pins the loopback
    bind; we deliberately do NOT set ``OLLAMA_MODELS`` — the portable server uses Ollama's
    standard model store (``~/.ollama/models``), so models are shared with (not duplicated by)
    any system Ollama the user later installs. Returns the process handle; ``spawn`` is
    injectable for testing (defaults to :class:`subprocess.Popen`)."""
    spawn = spawn or subprocess.Popen
    run_env = dict(os.environ if env is None else env)
    run_env.setdefault("OLLAMA_HOST", host)
    kwargs: dict[str, object] = {"env": run_env}
    if os.name == "nt":
        # Don't pop a console window for the managed server in the windowed (shell) app.
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return spawn([str(exe), "serve"], **kwargs)


@dataclass(frozen=True)
class OllamaStatus:
    """The outcome of :func:`ensure_serving`. ``source`` is for logging/telemetry-free diagnosis:
    already-up | started | needs-fetch | unavailable."""

    running: bool
    source: str
    exe: Path | None = None


def ensure_serving(
    base_url: str = DEFAULT_BASE_URL,
    *,
    resolve: Callable[[], Path | None] | None = None,
    is_up: Callable[[str], bool] | None = None,
    start: Callable[[Path], object] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    wait_s: float = 30.0,
    poll_s: float = 0.5,
) -> OllamaStatus:
    """Make an Ollama server reachable at ``base_url`` with the least disruption:

    1. If one is already up (a system Ollama the user runs) — reuse it, touch nothing.
    2. Else locate an executable (system install, or KimCad's fetched portable copy) and start
       ``ollama serve``, then poll until healthy (bounded by ``wait_s``).
    3. If no executable exists yet — return ``needs-fetch`` so the caller can fetch the portable
       binary (a network step the caller owns) and call again.

    All effects are injected so this orchestration is fully unit-tested; the real fetch→serve
    path is covered by a ``real_tool`` integration test."""
    resolve = resolve or resolve_ollama_exe
    is_up = is_up or (lambda u: is_server_up(u))

    if is_up(base_url):
        return OllamaStatus(True, "already-up")

    exe = resolve()
    if exe is None:
        return OllamaStatus(False, "needs-fetch")

    start = start or (lambda e: start_serve(e))
    start(exe)

    # Poll for health. A cold `ollama serve` is ready in ~1-2s; bound the wait so a wedged
    # start can't hang app launch — the caller surfaces "needs-fetch"/"unavailable" to the UI.
    waited = 0.0
    while waited < wait_s:
        if is_up(base_url):
            return OllamaStatus(True, "started", exe)
        sleep(poll_s)
        waited += poll_s
    return OllamaStatus(False, "unavailable", exe)


def ensure_serving_background(base_url: str = DEFAULT_BASE_URL, **kwargs: object) -> threading.Thread:
    """Fire-and-forget :func:`ensure_serving`, OFF the app-launch path so a slow/wedged start can
    never freeze the window opening. Best-effort: on ``needs-fetch``/``unavailable`` it simply does
    nothing and the UI's model-status guides the user (the wizard's one-click setup). Returns the
    thread (for tests)."""

    def _run() -> None:
        try:
            ensure_serving(base_url, **kwargs)  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 — auto-start is best-effort; it must never crash launch
            pass

    t = threading.Thread(target=_run, daemon=True, name="ollama-autostart")
    t.start()
    return t
