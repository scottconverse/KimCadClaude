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

import ipaddress
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
# real total comes from Ollama's stream once the pull starts.
_EST_GB = {"chat": 11.0, "vision": 4.0}
_GB = 1024**3


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
    string-prefix check accepted hostnames like ``127.evil.example``)."""
    host = (urlsplit(base_url).hostname or "") if "//" in base_url else base_url.split(":", 1)[0]
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host == "localhost"


def _friendly_error(raw: str) -> str:
    low = raw.lower()
    if "no space" in low or "not enough" in low or "disk full" in low:
        return (
            "Your disk filled up during the download. Free some space "
            "(the two models need about 13 GB together), then try again."
        )
    if "file does not exist" in low or "not found" in low or "pull model manifest" in low:
        return "The model wasn't found on Ollama's registry — check your internet connection and try again."
    return f"The download stopped: {raw}. Check your internet connection and try again."


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

            # The disk pre-check: fail friendly BEFORE gigabytes move. Ollama stores models
            # under the user profile by default, or wherever OLLAMA_MODELS points (ENG-003) —
            # measure the drive that will actually receive the blobs.
            need_gb = sum(_EST_GB.get(kind, 5.0) for _, kind in missing)
            models_dir = os.environ.get("OLLAMA_MODELS") or (probe_dir or Path.home())
            try:
                free_gb = shutil.disk_usage(models_dir).free / _GB
            except OSError:
                free_gb = shutil.disk_usage(Path.home()).free / _GB  # a bad env var never blocks
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
        with opener(req, timeout=300) as resp:
            for raw in resp:
                if not raw.strip():
                    continue
                try:
                    line = json.loads(raw)
                except (ValueError, TypeError):
                    continue  # a torn line mid-stream isn't an error
                if line.get("error"):
                    raise RuntimeError(str(line["error"]))
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
        # Stream ended without an error line: Ollama reports success as its last status
        # line, but the absence of an error + a closed stream is the working signal the
        # API documents. Presence is re-verified by the model-status probe the UI runs next.


JOB = ModelPullJob()
