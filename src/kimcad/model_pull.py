"""Stage 10 Slice 10.4 — in-app model downloads with progress.

The wizard's "Get the model" becomes an action instead of a copy-paste: KimCad asks the
LOCAL Ollama to pull the missing model(s) (``POST {base}/api/pull``, streamed) and exposes
per-model progress for the UI to poll. Strictly local-only — the webapp refuses to start a
pull against a non-loopback backend (this feature manages the on-device install, nothing
else), and the pull list is fixed to KimCad's own two models (the chat model + the vision
model), never a caller-supplied name — the no-model-menu rule holds on this surface too.

One job at a time, app-wide (:data:`JOB`): starting while a pull runs just returns the
running snapshot (idempotent — a wizard re-mount can't fork a second download). Failures
are per-model and friendly: a "no space left" from Ollama maps to a disk-space message with
the fix, and the disk is pre-checked against rough model sizes so the common case fails
BEFORE gigabytes are downloaded. A finished pull leaves Ollama owning the models — KimCad
holds no partial files (Ollama's pull is resumable on its side).
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Rough on-disk sizes for the disk pre-check (GB) — deliberately a little generous; the
# real total comes from Ollama's stream once the pull starts. Kept reconciled with the
# documented 12 GB free-disk headroom (DOC-101): chat + vision + engine must fit under it —
# pinned by a doc-vs-code test so the contradiction can't silently return.
_EST_GB = {"chat": 6.0, "vision": 4.0}
# The portable Ollama runtime's rough on-disk footprint (GB), added to the pre-check only when
# a fetch is actually needed (no system/managed exe yet).
_ENGINE_EST_GB = 1.5
_GB = 1024**3

# UX-COLD-001: the snapshot row that carries the managed-Ollama runtime fetch/start progress,
# shown by the wizard alongside the model rows so "set up the AI" is one honest progress flow.
_ENGINE_ROW = "AI engine"


def ollama_native_root(base_url: str) -> str:
    """Scheme + host[:port] of an OpenAI-compatible base_url (``…:11434/v1`` →
    ``…:11434``) — Ollama's native ``/api/pull`` is host-rooted, like ``/api/tags``."""
    parts = urlsplit(base_url)
    if parts.scheme and parts.netloc:
        return urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    return base_url.split("/v1", 1)[0].rstrip("/")


def is_loopback_url(base_url: str) -> bool:
    """Whether the backend host is this machine. The pull surface manages the ON-DEVICE
    install only — starting multi-GB downloads on some remote box is never what the
    wizard's button means. Parsed as an IP when possible (ENG-005, slice-10.4 audit: a
    string-prefix check accepted hostnames like ``127.evil.example``).

    ENG-GG-005: the loopback classification is delegated to the single source of truth,
    :meth:`kimcad.config.Config._is_local_base_url`, so the two classifiers can never drift
    apart. We keep this function's own input contract — it accepts a bare ``host``/``host:port``
    OR a full ``http://host/...`` URL — by normalizing a bare host into a URL before delegating."""
    from kimcad.config import Config

    url = base_url if "//" in base_url else f"http://{base_url}"
    return Config._is_local_base_url(url)


def _free_gb_on_receiving_drive(probe_dir: Path | None = None) -> float:
    """Free space (GB) on the drive that will actually receive the blobs. In installed mode,
    KimCad stores models under writable_root()/"models" (%LOCALAPPDATA%/KimCad/models).
    A bad env var never blocks: fall back to home. Shared by both the per-model ``start``
    pre-check and the cold ``_run_setup`` pre-check (ENG-GG-002), so the two agree."""
    # ENG-002: OLLAMA_MODELS is set in the child's env by _child_env(), not the parent's.
    # Use writable_root()/"models" directly in installed mode; fall back to probe_dir or home.
    from kimcad.paths import writable_root, is_installed
    models_dir = (str(writable_root() / "models") if is_installed() else None) or os.environ.get("OLLAMA_MODELS") or (probe_dir or Path.home())
    try:
        return shutil.disk_usage(models_dir).free / _GB
    except OSError:
        return shutil.disk_usage(Path.home()).free / _GB


def _friendly_error(raw: str) -> str:
    low = raw.lower()
    if "no space" in low or "not enough" in low or "disk full" in low:
        return (
            "Your disk filled up during the download. Free some space "
            "(the models are about 7.7 GB, plus room to unpack), then try again."
        )
    if "file does not exist" in low or "not found" in low or "pull model manifest" in low:
        return "The model wasn't found on Ollama's registry — check your internet connection and try again."
    # ENG-012: clip the untrusted upstream error before it lands in a display string (the
    # codebase's [:300] bound — same as the connector _ERR_BODY_CAP).
    return f"The download stopped: {raw[:300]}. Check your internet connection and try again."


class ModelPullJob:
    """The app-wide pull job. All state behind ``lock``; the worker thread is a daemon so
    an app shutdown never hangs on a half-pulled model."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self._thread: threading.Thread | None = None
        # name -> {status: queued|pulling|done|error, completed: int, total: int, error: str}
        self._models: dict[str, dict[str, Any]] = {}

    # --- public API -------------------------------------------------------------------
    def _snapshot_locked(self) -> dict[str, Any]:
        """REQUIRES ``self.lock`` held — the lock is NOT reentrant, so the paths inside
        :meth:`start` must use this, never :meth:`snapshot` (deadlock, caught by test)."""
        # TEST-1005 (stage-10 gate): the _locked contract enforced, same as DesignRegistry.
        assert self.lock.locked(), "_snapshot_locked requires self.lock to be held"
        running = self._thread is not None and self._thread.is_alive()
        return {
            "running": running,
            "models": {n: dict(s) for n, s in self._models.items()},
        }

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return self._snapshot_locked()

    def start(
        self,
        base_url: str,
        missing: list[tuple[str, str]],
        *,
        probe_dir: Path | None = None,
        opener: Any = urllib.request.urlopen,
    ) -> dict[str, Any]:
        """Begin pulling ``missing`` — a list of ``(model_name, kind)`` with kind in
        ``chat``/``vision`` (sizes the disk pre-check). Idempotent while running."""
        with self.lock:
            if self._thread is not None and self._thread.is_alive():
                return self._snapshot_locked()  # one download at a time; report the running one
            if not missing:
                # ENG-002 (slice-10.4 audit): a no-op start clears the previous run's states —
                # stale "done"/"error" rows must never read as this request's outcome.
                self._models = {}
                return self._snapshot_locked()

            # The disk pre-check: fail friendly BEFORE gigabytes move. In installed mode,
            # models land in writable_root()/"models" — measure THAT drive.
            need_gb = sum(_EST_GB.get(kind, 5.0) for _, kind in missing)
            free_gb = _free_gb_on_receiving_drive(probe_dir)
            if free_gb < need_gb:
                # ENG-002: REPLACE the state — no residue from a previous run.
                self._models = {
                    name: {
                        "status": "error", "completed": 0, "total": 0,
                        "error": f"Not enough disk space: about {need_gb:.0f} GB is needed "
                        f"and only {free_gb:.0f} GB is free. Free some space, then try again.",
                    }
                    for name, _ in missing
                }
                return self._snapshot_locked()

            self._models = {
                name: {"status": "queued", "completed": 0, "total": 0, "error": ""}
                for name, _ in missing
            }
            self._thread = threading.Thread(
                target=self._run, args=(base_url, [n for n, _ in missing], opener), daemon=True
            )
            self._thread.start()
        return self.snapshot()

    # --- cold-start one-click setup (UX-COLD-001) -------------------------------------
    def start_setup(
        self,
        base_url: str,
        chat_model: str,
        vision_model: str,
        *,
        opener: Any = urllib.request.urlopen,
        is_up: Any = None,
        resolve: Any = None,
        fetch: Any = None,
        serve: Any = None,
        probe: Any = None,
        managed_dir: Path | None = None,
        sleep: Any = None,
        wait_s: float = 30.0,
        poll_s: float = 0.5,
    ) -> dict[str, Any]:
        """One-click cold setup (UX-COLD-001): ensure a managed Ollama is SERVING — reuse a
        running/system one, else fetch + start KimCad's portable copy — then pull whatever of the
        chat / vision models is missing. Both phases ride the SAME per-row snapshot the wizard
        already renders: an "AI engine" row (the runtime fetch) plus a row per model. Idempotent
        while running. All effects are injected for testing; defaults wire the real
        runtime/fetch/probe. ``base_url`` is the native (host-rooted) Ollama URL, as ``start``."""
        import time as _time

        from kimcad import ollama_fetch as _of
        from kimcad import ollama_runtime as _ort

        is_up = is_up or (lambda u: _ort.is_server_up(u))
        resolve = resolve or _ort.resolve_ollama_exe
        fetch = fetch or _of.fetch_portable_ollama
        serve = serve or (lambda e: _ort.start_serve(e))
        sleep = sleep or _time.sleep
        managed_dir = managed_dir if managed_dir is not None else _ort.managed_dir()
        if probe is None:
            from kimcad.model_advisor import probe_ollama as probe

        with self.lock:
            if self._thread is not None and self._thread.is_alive():
                return self._snapshot_locked()
            self._models = {
                _ENGINE_ROW: {"status": "queued", "completed": 0, "total": 0, "error": ""}
            }
            self._thread = threading.Thread(
                target=self._run_setup,
                args=(base_url, chat_model, vision_model, opener, is_up, resolve, fetch,
                      serve, probe, managed_dir, sleep, wait_s, poll_s),
                daemon=True,
            )
            self._thread.start()
        return self.snapshot()

    def _run_setup(  # noqa: PLR0913 — an orchestration step; every arg is an injected effect
        self, base_url: str, chat_model: str, vision_model: str, opener: Any, is_up: Any,
        resolve: Any, fetch: Any, serve: Any, probe: Any, managed_dir: Path, sleep: Any,
        wait_s: float, poll_s: float,
    ) -> None:
        # ENG-GG-002: the disk pre-check, hoisted into the cold one-click path so the common
        # failure (a small SSD) fails friendly BEFORE a single byte of runtime or model is
        # fetched/pulled. Estimate need = the portable engine (only if a fetch will be needed,
        # i.e. there's no system/managed exe to reuse) + the rough size of each MISSING model.
        server_up = is_up(base_url)
        fetch_needed = (not server_up) and resolve() is None
        if server_up:
            # The server is up, so we can ask which models are already installed; only the
            # genuinely-missing ones cost disk.
            try:
                _running, installed = probe(base_url)
            except Exception:  # noqa: BLE001 — a flaky probe never blocks the pre-check
                installed = []
            names = {getattr(m, "name", "") for m in installed}
            missing_kinds = [
                kind for tag, kind in ((chat_model, "chat"), (vision_model, "vision"))
                if not any(n == tag or n.startswith(tag + "-") for n in names)
            ]
        else:
            # Server down -> can't probe; assume both models are missing (the cold case pulls
            # whatever is actually missing once it's up — this is the conservative estimate).
            missing_kinds = ["chat", "vision"]
        need_gb = sum(_EST_GB.get(k, 5.0) for k in missing_kinds) + (
            _ENGINE_EST_GB if fetch_needed else 0.0
        )
        free_gb = _free_gb_on_receiving_drive(managed_dir)
        if need_gb and free_gb < need_gb:
            with self.lock:
                self._models[_ENGINE_ROW]["status"] = "error"
                self._models[_ENGINE_ROW]["error"] = (
                    f"Not enough disk space: about {need_gb:.0f} GB is needed and only "
                    f"{free_gb:.0f} GB is free. Free some space, then try again."
                )
            return

        # Phase 1 — ensure the runtime is serving.
        if not is_up(base_url):
            with self.lock:
                self._models[_ENGINE_ROW]["status"] = "pulling"
            exe = resolve()
            if exe is None:
                # No system Ollama and none fetched yet — download the portable runtime, its bytes
                # driving the engine row's progress.
                def _prog(done: int, total: int) -> None:
                    with self.lock:
                        self._models[_ENGINE_ROW]["completed"] = done
                        self._models[_ENGINE_ROW]["total"] = total

                try:
                    exe = fetch(managed_dir, progress=_prog)
                except Exception as e:  # noqa: BLE001 — a fetch failure is a friendly row, not a crash
                    with self.lock:
                        self._models[_ENGINE_ROW]["status"] = "error"
                        self._models[_ENGINE_ROW]["error"] = _friendly_error(str(e))
                    return
            try:
                serve(exe)
            except Exception:  # noqa: BLE001
                with self.lock:
                    self._models[_ENGINE_ROW]["status"] = "error"
                    self._models[_ENGINE_ROW]["error"] = (
                        "Couldn't start the local AI engine — check that no other application "
                        "is using port 11434, then try again."
                    )
                return
            waited = 0.0
            while waited < wait_s and not is_up(base_url):
                sleep(poll_s)
                waited += poll_s
            if not is_up(base_url):
                with self.lock:
                    self._models[_ENGINE_ROW]["status"] = "error"
                    self._models[_ENGINE_ROW]["error"] = (
                        "The local AI engine didn't come up in time. Try again."
                    )
                return
        with self.lock:
            self._models[_ENGINE_ROW]["status"] = "done"

        # Phase 2 — pull whatever models are missing (reuses _pull_one).
        try:
            _running, installed = probe(base_url)
        except Exception:  # noqa: BLE001
            installed = []
        names = {getattr(m, "name", "") for m in installed}

        def _present(tag: str) -> bool:
            return any(n == tag or n.startswith(tag + "-") for n in names)

        missing = [t for t in ((chat_model, "chat"), (vision_model, "vision")) if not _present(t[0])]
        with self.lock:
            for name, _kind in missing:
                self._models[name] = {"status": "queued", "completed": 0, "total": 0, "error": ""}
        for name, _kind in missing:
            with self.lock:
                self._models[name]["status"] = "pulling"
            try:
                self._pull_one(base_url, name, opener)
                with self.lock:
                    self._models[name]["status"] = "done"
            except Exception as e:  # noqa: BLE001 — per-model friendly status, never a crash
                with self.lock:
                    self._models[name]["status"] = "error"
                    self._models[name]["error"] = _friendly_error(str(e))

    # --- the worker -------------------------------------------------------------------
    def _run(self, base_url: str, names: list[str], opener: Any) -> None:
        for name in names:
            with self.lock:
                self._models[name]["status"] = "pulling"
            try:
                self._pull_one(base_url, name, opener)
                with self.lock:
                    self._models[name]["status"] = "done"
            except Exception as e:  # noqa: BLE001 — every failure becomes a per-model status
                with self.lock:
                    self._models[name]["status"] = "error"
                    self._models[name]["error"] = _friendly_error(str(e))
                # A failed chat-model pull doesn't block trying the vision model: each is
                # independently useful (words-only design vs the image on-ramps).
                continue

    def _pull_one(self, base_url: str, name: str, opener: Any) -> None:
        body = json.dumps({"model": name, "stream": True}).encode()
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/pull", data=body,
            headers={"Content-Type": "application/json"},
        )
        # No total timeout: a 10 GB pull takes as long as it takes. The read timeout bounds
        # a SILENT hang (no stream line for 5 minutes = something is wrong).
        saw_success = False
        with opener(req, timeout=300) as resp:
            for raw in resp:
                if not raw.strip():
                    continue
                try:
                    line = json.loads(raw)
                except (ValueError, TypeError):
                    continue  # a torn line mid-stream isn't an error
                if line.get("error"):
                    # ENG-012: clip the untrusted streamed-JSON error text (it reaches a display
                    # string via _friendly_error) — the codebase's [:300] bound.
                    raise RuntimeError(str(line["error"])[:300])
                if str(line.get("status", "")).lower() == "success":
                    saw_success = True
                with self.lock:
                    if "total" in line:
                        # UX-002 (slice-10.4 audit): Ollama reports totals PER LAYER, so a
                        # naive readout jumps backward when a small layer follows the big
                        # one. Track the largest layer (the model blob dominates the
                        # download) so the visible percent is monotonic-ish and honest.
                        total = int(line.get("total") or 0)
                        if total >= self._models[name]["total"]:
                            self._models[name]["total"] = total
                            self._models[name]["completed"] = int(line.get("completed") or 0)
        # ENG-1006 (stage-10 gate): "done" requires Ollama's terminal `success` line — a
        # stream that closed cleanly mid-pull (proxy drop, Ollama restart) must NOT render
        # a "✓ done" row that the next model-status probe contradicts.
        if not saw_success:
            raise RuntimeError("the download ended before Ollama confirmed it finished")


JOB = ModelPullJob()
