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
effect away). Real-tool coverage is honest about its branches: the auto-run `real_tool` test
(tests/test_ollama_runtime_real.py) exercises the *reuse* branch (detect a running server) AND a
*spawn* branch (start `ollama serve` on an alternate loopback port, poll healthy, tear it down);
the full ~1.4 GB portable *fetch+extract* is covered by the manual cold-start run recorded under
docs/audits/coder-ui-qa-test-coldstart-2026-06-17/ and by the Walkthrough lane (live bytes).

The fetch/extract/verify of the portable binary lives in :mod:`kimcad.ollama_fetch` (network) so
this module stays import-light and pure.
"""

from __future__ import annotations

import atexit
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


def _child_env(env: dict[str, str] | None, host: str) -> dict[str, str]:
    # ENG-GG-006: managed Ollama child has no business inheriting cloud credentials; use the
    # project-canonical scrub (subprocess_env) rather than a bespoke deny-list so the two stay in sync.
    from kimcad.subprocess_env import is_secret_env
    base = os.environ if env is None else env
    run_env = {k: v for k, v in base.items() if not is_secret_env(k)}
    run_env.setdefault("OLLAMA_HOST", host)
    # Store models under KimCad's own data dir (tester-007 Minor-2: default ~/.ollama leaves
    # 7+ GB orphaned after uninstall; the uninstaller already removes writable_root()).
    # This only affects the MANAGED path — reusing a system Ollama never calls _child_env.
    run_env["OLLAMA_MODELS"] = str(writable_root() / "models")
    return run_env


def start_serve(
    exe: Path,
    *,
    host: str = DEFAULT_HOST,
    spawn: _Spawn | None = None,
    env: dict[str, str] | None = None,
) -> object:
    """Launch ``ollama serve`` headless as a managed child. ``OLLAMA_HOST`` pins the loopback
    bind; ``OLLAMA_MODELS`` is pinned to KimCad's own data dir so models live under the app's
    uninstall scope (tester-007 Minor-2: default ``~/.ollama`` orphans 7+ GB after uninstall).
    The child env is scrubbed of cloud secrets (ENG-GG-006) and, on Windows, the child gets its
    own process group so teardown can signal it (ENG-GG-008). Returns the process handle;
    ``spawn`` is injectable for testing (defaults to :class:`subprocess.Popen`)."""
    spawn = spawn or subprocess.Popen
    run_env = _child_env(env, host)
    kwargs: dict[str, object] = {"env": run_env}
    if os.name == "nt":
        # Don't pop a console window for the managed server in the windowed (shell) app; give it its
        # own process group so the teardown path (stop_managed) can signal the whole group.
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        kwargs["creationflags"] = flags
    return spawn([str(exe), "serve"], **kwargs)


@dataclass(frozen=True)
class OllamaStatus:
    """The outcome of :func:`ensure_serving`. ``source`` is for logging/telemetry-free diagnosis:
    already-up | started | needs-fetch | unavailable."""

    running: bool
    source: str
    exe: Path | None = None


# ENG-GG-001 (gauntletgate): the managed `ollama serve` child must die WITH the app — the module
# docstring promises "stop it with the app", and an orphaned headless server (multi-GB for the
# portable build) on every cold-start machine is the exact leak this section prevents. We track ONLY
# a server KimCad itself started (never a reused system one), assign it to a Windows Job Object so it
# is killed even on a hard parent exit, and register an atexit terminate as a cross-platform floor.
_managed_lock = threading.Lock()
_managed_proc: subprocess.Popen | None = None  # type: ignore[type-arg]
_managed_job = None  # Windows HANDLE for the kill-on-close job object (kept alive = job alive)


def _assign_to_job_object(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Windows: put the child in a Job Object with KILL_ON_JOB_CLOSE so it dies when our process
    (and thus the job handle) goes away — the durable guarantee a bare Popen can't give. Best-effort:
    any failure leaves the atexit terminate as the floor. No-op off Windows."""
    global _managed_job
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        JobObjectExtendedLimitInformation = 9
        PROCESS_ALL_ACCESS = 0x1F0FFF

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_uint64) for n in (
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        job = k32.CreateJobObjectW(None, None)
        if not job:
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not k32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)
        ):
            k32.CloseHandle(job)
            return
        hproc = k32.OpenProcess(PROCESS_ALL_ACCESS, False, proc.pid)
        if not hproc:
            k32.CloseHandle(job)
            return
        try:
            if k32.AssignProcessToJobObject(job, hproc):
                _managed_job = job  # keep the handle alive for the process lifetime
            else:
                k32.CloseHandle(job)
        finally:
            k32.CloseHandle(hproc)
    except Exception:  # noqa: BLE001 — job assignment is a hardening floor; never crash launch
        pass


def _set_managed_proc(proc: subprocess.Popen) -> None:  # type: ignore[type-arg]
    """Record the server KimCad started so teardown can stop it; assign the Windows job object."""
    global _managed_proc
    with _managed_lock:
        _managed_proc = proc
    _assign_to_job_object(proc)


def stop_managed(timeout: float = 5.0) -> None:
    """Stop the managed `ollama serve` KimCad started (no-op if we reused a system server or never
    started one). Idempotent; best-effort. Wired into the shell window-close and the `serve()`
    shutdown path, and registered with atexit as a floor."""
    global _managed_proc
    with _managed_lock:
        proc = _managed_proc
        _managed_proc = None
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except Exception:  # noqa: BLE001 — escalate to kill if terminate didn't take
                proc.kill()
    except Exception:  # noqa: BLE001 — teardown is best-effort; never raise on exit
        pass


atexit.register(stop_managed)


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

    All effects are injected so this orchestration is fully unit-tested; the real reuse+spawn
    branches are covered by the ``real_tool`` test and the full fetch by the recorded manual run
    (see the module docstring). ENG-GG-001: when WE start the server (the real, non-injected path),
    the handle is recorded via :func:`_set_managed_proc` so :func:`stop_managed` can tear it down
    with the app — a reused system server (the ``already-up`` branch) is never touched."""
    resolve = resolve or resolve_ollama_exe
    is_up = is_up or (lambda u: is_server_up(u))
    # Only manage (track + teardown) a server we started through the REAL start path. Tests that
    # inject `start` exercise the orchestration with fakes and must not mutate the module's
    # managed-process state.
    started_by_default = start is None

    if is_up(base_url):
        return OllamaStatus(True, "already-up")

    exe = resolve()
    if exe is None:
        return OllamaStatus(False, "needs-fetch")

    start = start or (lambda e: start_serve(e))
    proc = start(exe)

    # Poll for health. A cold `ollama serve` is ready in ~1-2s; bound the wait so a wedged
    # start can't hang app launch — the caller surfaces "needs-fetch"/"unavailable" to the UI.
    waited = 0.0
    while waited < wait_s:
        if is_up(base_url):
            if started_by_default and isinstance(proc, subprocess.Popen):
                _set_managed_proc(proc)
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
