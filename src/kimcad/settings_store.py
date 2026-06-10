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

# ENG-001 (stage-C): the OpenRouter key is a BILLABLE credential — at rest it lives in the OS
# credential store (Windows Credential Manager via `keyring`), not the JSON file. The JSON
# carries this sentinel so readers know a key exists; `all()` resolves it transparently, so
# every consumer (masking, the provider) is unchanged. When no keyring backend is usable the
# store falls back to the file — and `key_storage()` reports which, so the UI can DISCLOSE
# the location instead of implying safety it can't deliver.
_SECRET_KEY = "openrouter_api_key"
_KEYRING_SENTINEL = "@keyring"
_KEYRING_SERVICE = "KimCad"


def _keyring():
    """The keyring module, or None when unavailable/broken (then the file fallback rules).

    QA-D-001 (stage-BCD gate): import success is NOT backend health — an importable-but-broken
    backend would otherwise be disclosed as "keyring" right up until the save quietly landed in
    the file. Probe with a real read (an absent entry returns None without raising; a broken
    backend raises), so ``key_storage()``'s pre-save answer matches where a key would GO."""
    try:
        import keyring

        keyring.get_password(_KEYRING_SERVICE, "__health_probe__")
        return keyring
    except Exception:  # noqa: BLE001 - any import/backend failure means "no keyring"
        return None


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
    """A best-effort JSON key/value store for user settings at ``~/.kimcad/settings.json``,
    with the OpenRouter secret held in the OS credential store (ENG-001)."""

    # ENG-101 (stage-BCD gate): the migration runs ONCE per settings path per process — the web
    # layer constructs a fresh store per request, and a per-request read-migrate-write would race
    # concurrent saves. Guarded by _WRITE_LOCK alongside the membership check.
    _migrated_paths: set[str] = set()

    def __init__(self, path: Path):
        self._path = path
        # One-time legacy migration: a pre-Stage-C settings.json holds the key in PLAINTEXT.
        # Move it into the credential store and rewrite the file with the sentinel. The WHOLE
        # read-migrate-write runs under _WRITE_LOCK (ENG-101: a read taken outside the lock and
        # written back under it was a lost-update race against concurrent saves). Best-effort:
        # a failure leaves the legacy file as-was (still functional, still disclosed by
        # key_storage() == "file").
        try:
            with _WRITE_LOCK:
                key = str(path)
                if key in SettingsStore._migrated_paths:
                    return
                SettingsStore._migrated_paths.add(key)
                raw = self._read_raw()
                secret = raw.get(_SECRET_KEY)
                if isinstance(secret, str) and secret and secret != _KEYRING_SENTINEL:
                    kr = _keyring()
                    if kr is not None:
                        kr.set_password(_KEYRING_SERVICE, _SECRET_KEY, secret)
                        raw[_SECRET_KEY] = _KEYRING_SENTINEL
                        self._path.parent.mkdir(parents=True, exist_ok=True)
                        _atomic_write_json(self._path, raw)
        except Exception:  # noqa: BLE001 - migration is best-effort; never break startup
            pass

    def _read_raw(self) -> dict[str, Any]:
        """The file contents verbatim — the sentinel NOT resolved. ``utf-8-sig`` so a BOM'd
        file (QA-D-002: e.g. saved by PowerShell's default Out-File) still parses instead of
        silently reading as empty — which would also have blocked the plaintext migration."""
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8-sig"))
            return raw if isinstance(raw, dict) else {}
        except Exception:  # noqa: BLE001 - best-effort; a missing/corrupt file means "no overrides"
            return {}

    def key_storage(self) -> str:
        """Where the OpenRouter secret lives at rest: ``"keyring"`` (the OS credential store)
        or ``"file"`` (the JSON fallback — the UI must disclose this)."""
        raw = self._read_raw()
        if raw.get(_SECRET_KEY) == _KEYRING_SENTINEL:
            return "keyring"
        if _SECRET_KEY in raw:
            return "file"
        # No key saved yet: report where a NEW key would go.
        return "keyring" if _keyring() is not None else "file"

    def all(self) -> dict[str, Any]:
        """The saved settings as a dict, with the secret sentinel resolved from the credential
        store (consumers see the real value, same as before ENG-001). Returns {} on any
        read/parse failure (the UI then falls back to config defaults). Never raises."""
        raw = self._read_raw()
        if raw.get(_SECRET_KEY) == _KEYRING_SENTINEL:
            kr = _keyring()
            secret = None
            if kr is not None:
                try:
                    secret = kr.get_password(_KEYRING_SERVICE, _SECRET_KEY)
                except Exception:  # noqa: BLE001 - a broken backend reads as "no key"
                    secret = None
            if secret:
                raw[_SECRET_KEY] = secret
            else:
                raw.pop(_SECRET_KEY, None)
        return raw

    def get(self, key: str, default: Any = None) -> Any:
        return self.all().get(key, default)

    def clear(self) -> bool:
        """Reset to pristine: drop every saved override so the file holds no keys (the app falls
        back to the shipped config defaults). Returns True on success, False on failure (no-op).
        Never raises."""
        try:
            with _WRITE_LOCK:
                self._delete_secret()  # ENG-001: a reset wipes the credential-store entry too
                self._path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_json(self._path, {})
            return True
        except Exception:  # noqa: BLE001 - best-effort
            return False

    def update(self, updates: dict[str, Any]) -> bool:
        """Merge ``updates`` (only ``_ALLOWED_KEYS``; a value of None clears that key) into the
        saved settings and atomically write. The OpenRouter secret goes to the OS credential
        store (the file gets the sentinel); when no keyring backend is usable it falls back to
        the file — ``key_storage()`` then reports "file" so the UI discloses it. Returns True
        on success, False on any failure (the save is a no-op, the prior settings stand).
        Never raises."""
        vault_rollback: tuple[str | None, bool] | None = None  # (previous secret, had_entry)
        try:
            with _WRITE_LOCK:
                current = self._read_raw()
                for k, v in updates.items():
                    if k not in _ALLOWED_KEYS:
                        continue
                    if v is None:
                        if k == _SECRET_KEY:
                            self._delete_secret()
                        current.pop(k, None)
                    elif k == _SECRET_KEY:
                        # ENG-106: the sentinel is a RESERVED value — a literal "@keyring" key
                        # stored to the file fallback would later be misread as the sentinel
                        # (the key silently vanishes). No real API key collides with it; refuse.
                        if str(v) == _KEYRING_SENTINEL:
                            continue
                        kr = _keyring()
                        stored = False
                        if kr is not None:
                            try:
                                prev = kr.get_password(_KEYRING_SERVICE, _SECRET_KEY)
                                kr.set_password(_KEYRING_SERVICE, _SECRET_KEY, str(v))
                                vault_rollback = (prev, prev is not None)
                                stored = True
                            except Exception:  # noqa: BLE001 - backend refusal → file fallback
                                stored = False
                        current[_SECRET_KEY] = _KEYRING_SENTINEL if stored else v
                    else:
                        current[k] = v
                self._path.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_json(self._path, current)
            return True
        except Exception:  # noqa: BLE001 - persistence is best-effort; never break the app
            # ENG-102: "the prior settings stand" must include the VAULT — a file-write failure
            # after the vault was already updated would otherwise leave the new secret live
            # while update() reports failure. Best-effort rollback to the previous entry.
            if vault_rollback is not None:
                kr = _keyring()
                if kr is not None:
                    try:
                        prev, had_entry = vault_rollback
                        if had_entry and prev is not None:
                            kr.set_password(_KEYRING_SERVICE, _SECRET_KEY, prev)
                        else:
                            kr.delete_password(_KEYRING_SERVICE, _SECRET_KEY)
                    except Exception:  # noqa: BLE001 - rollback is best-effort
                        pass
            return False

    @staticmethod
    def _delete_secret() -> None:
        """Best-effort removal of the secret from the credential store."""
        kr = _keyring()
        if kr is None:
            return
        try:
            kr.delete_password(_KEYRING_SERVICE, _SECRET_KEY)
        except Exception:  # noqa: BLE001 - absent entry / broken backend — nothing to remove
            pass
