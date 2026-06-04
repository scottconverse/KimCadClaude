"""Stage 8.5 Slice 6 — the user settings store.

A small, local-first, best-effort persister for the choices the in-app Settings screen owns:
the default printer + material today, and (later slices) the LLM backend, the cloud opt-in, and
the experimental-generator toggle. It lives in the per-user home (``~/.kimcad/settings.json``),
never the repo, so it persists across sessions and nothing leaves the machine.

Same posture as the history + designs stores: every read/write is wrapped so a failure degrades
(the UI falls back to the shipped config defaults / a save no-ops) rather than ever breaking a
build. Writes are serialized + atomic (a temp file + ``os.replace``) so a concurrent reader on the
threaded web server never sees a half-write.

The store is a dumb key/value JSON bag. Validation (e.g. "is this a known printer key?") is the
caller's job — the web layer has the config to check against; the store just persists.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

# Serialize the read-modify-write across the threaded web server.
_WRITE_LOCK = threading.Lock()
# os.replace() can raise PermissionError on Windows if a reader has the file open momentarily;
# retry briefly (mirrors design_store).
_REPLACE_RETRIES = 8
_REPLACE_BACKOFF = 0.01  # seconds, linear backoff

# The keys the store will persist. Anything else handed to update() is ignored, so a crafted or
# stale client can't stuff arbitrary data into the file. New slices add their keys here.
_ALLOWED_KEYS = frozenset(
    {
        "default_printer",
        "default_material",
        # Slice 6 MS-3 — cloud (OpenRouter) opt-in. The key is the user's own secret, stored on
        # their machine (never the repo/logs) and never echoed back in full by the API.
        "cloud_enabled",
        "openrouter_api_key",
        "cloud_model",
        # Slice 6 MS-4 — the experimental raw-codegen generator (OFF by default).
        "experimental_enabled",
    }
)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via a temp file + os.replace so a concurrent reader never sees a half-write.
    Retries os.replace on Windows PermissionError; cleans up the temp + re-raises on final failure
    so the caller's best-effort except degrades cleanly."""
    payload = json.dumps(data, indent=2, allow_nan=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == _REPLACE_RETRIES - 1:
                tmp.unlink(missing_ok=True)
                raise
            time.sleep(_REPLACE_BACKOFF * (attempt + 1))


class SettingsStore:
    """A best-effort JSON key/value store for user settings at ``~/.kimcad/settings.json``."""

    def __init__(self, path: Path):
        self._path = path

    def all(self) -> dict[str, Any]:
        """The saved settings as a dict. Returns {} on any read/parse failure (the UI then falls
        back to config defaults). Never raises."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001 - best-effort; a missing/corrupt file means "no overrides"
            return {}

    def get(self, key: str, default: Any = None) -> Any:
        return self.all().get(key, default)

    def update(self, updates: dict[str, Any]) -> bool:
        """Merge ``updates`` (only ``_ALLOWED_KEYS``; a value of None clears that key) into the
        saved settings and atomically write. Returns True on success, False on any failure (the
        save is a no-op, the prior settings stand). Never raises."""
        try:
            with _WRITE_LOCK:
                current = self.all()
                for k, v in updates.items():
                    if k not in _ALLOWED_KEYS:
                        continue
                    if v is None:
                        current.pop(k, None)
                    else:
                        current[k] = v
                self._path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_json(self._path, current)
            return True
        except Exception:  # noqa: BLE001 - persistence is best-effort; never break the app
            return False
