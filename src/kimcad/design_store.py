"""Stage 8.5 Slice 1 — the saved-designs store ("My Designs" + local persistence).

The shipped SPA kept everything in memory: a browser refresh, or hitting "New design," lost the
current part, and there was no library of past work — a flat deal-killer for repeated use. This
store persists each built design under ``~/.kimcad/designs/<id>/`` (``meta.json`` + ``mesh.stl`` +
``thumb.png``), so designs survive a server restart, list in a gallery, and **reopen fully** — the
re-render state (the base plan + template family) is saved too, so a reopened template part's live
sliders still work.

Local-first + **best-effort**, like the Stage-7 history store: everything lives in the per-user home
(never the repo), nothing leaves the machine, and any read/write failure degrades (the gallery shows
fewer designs / a save is skipped) rather than ever breaking a build. Writes are serialized + atomic.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Serialize the read-modify-write of the index + per-design writes across the threaded web server.
_WRITE_LOCK = threading.Lock()
# Bound the library so it can't grow without limit; the oldest beyond this are dropped on save.
_MAX_DESIGNS = 200


@dataclass
class SavedDesign:
    """A persisted, reopenable design. ``payload`` is the design API response (plan / report /
    readiness / template / parameters) the SPA restores from; ``plan`` is the serialized DesignPlan
    used to rebuild the live-slider re-render state on reopen (template-backed designs only)."""

    id: str
    name: str
    prompt: str
    created_at: str
    object_type: str
    gate_status: str
    readiness_score: int | None
    template_family: str | None
    payload: dict[str, Any]
    plan: dict[str, Any] | None


def _index_entry(d: SavedDesign, *, has_thumb: bool) -> dict[str, Any]:
    """The lightweight record the gallery list returns (no heavy payload)."""
    return {
        "id": d.id,
        "name": d.name,
        "created_at": d.created_at,
        "object_type": d.object_type,
        "gate_status": d.gate_status,
        "readiness_score": d.readiness_score,
        "has_thumb": has_thumb,
    }


class DesignStore:
    """A local, best-effort store of saved designs. All methods never raise."""

    def __init__(self, root: Path):
        self.root = root

    # --- paths --------------------------------------------------------------
    def _dir(self, design_id: str) -> Path:
        return self.root / design_id

    def mesh_path(self, design_id: str) -> Path | None:
        p = self._dir(design_id) / "mesh.stl"
        return p if p.exists() else None

    def thumb_path(self, design_id: str) -> Path | None:
        p = self._dir(design_id) / "thumb.png"
        return p if p.exists() else None

    # --- read ---------------------------------------------------------------
    def get(self, design_id: str) -> SavedDesign | None:
        """Load one design's full record, or None if absent/corrupt. Never raises. A traversal-
        unsafe id (slashes, ``..``) returns None — ids are server-minted uuids."""
        if not _safe_id(design_id):
            return None
        meta = self._dir(design_id) / "meta.json"
        try:
            raw = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return SavedDesign(
                id=str(raw["id"]),
                name=str(raw.get("name", "Untitled")),
                prompt=str(raw.get("prompt", "")),
                created_at=str(raw.get("created_at", "")),
                object_type=str(raw.get("object_type", "")),
                gate_status=str(raw.get("gate_status", "")),
                readiness_score=raw.get("readiness_score"),
                template_family=raw.get("template_family"),
                payload=raw.get("payload") if isinstance(raw.get("payload"), dict) else {},
                plan=raw.get("plan") if isinstance(raw.get("plan"), dict) else None,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def list(self) -> list[dict[str, Any]]:
        """The gallery index — lightweight entries, newest first. Skips any unreadable design;
        never raises."""
        out: list[tuple[str, dict[str, Any]]] = []
        try:
            children = [c for c in self.root.iterdir() if c.is_dir()] if self.root.exists() else []
        except OSError:
            return []
        for child in children:
            d = self.get(child.name)
            if d is None:
                continue
            out.append((d.created_at, _index_entry(d, has_thumb=self.thumb_path(d.id) is not None)))
        # Newest first; created_at is ISO-8601 so a string sort is chronological.
        out.sort(key=lambda t: t[0], reverse=True)
        return [entry for _, entry in out]

    # --- write (best-effort, serialized, atomic) ----------------------------
    def save(
        self,
        *,
        design_id: str,
        name: str,
        prompt: str,
        created_at: str,
        object_type: str,
        gate_status: str,
        readiness_score: int | None,
        template_family: str | None,
        payload: dict[str, Any],
        plan: dict[str, Any] | None,
        mesh_path: Path,
        thumb_png: bytes | None,
    ) -> bool:
        """Persist a design (copying its mesh + an optional thumbnail). Returns True on success.
        Best-effort: any failure is swallowed and returns False (the SPA just doesn't get a saved
        copy) — a logging miss never breaks a build."""
        if not _safe_id(design_id):
            return False
        try:
            with _WRITE_LOCK:
                d = self._dir(design_id)
                d.mkdir(parents=True, exist_ok=True)
                meta = {
                    "id": design_id,
                    "name": name or "Untitled",
                    "prompt": prompt,
                    "created_at": created_at,
                    "object_type": object_type,
                    "gate_status": gate_status,
                    "readiness_score": readiness_score,
                    "template_family": template_family,
                    "payload": payload,
                    "plan": plan,
                }
                shutil.copyfile(mesh_path, d / "mesh.stl")
                if thumb_png:
                    (d / "thumb.png").write_bytes(thumb_png)
                _atomic_write_json(d / "meta.json", meta)
                self._prune()
            return True
        except Exception:  # noqa: BLE001 - persistence is best-effort; never break a build
            return False

    def rename(self, design_id: str, name: str) -> bool:
        if not _safe_id(design_id):
            return False
        try:
            with _WRITE_LOCK:
                meta_path = self._dir(design_id) / "meta.json"
                raw = json.loads(meta_path.read_text(encoding="utf-8"))
                raw["name"] = (name or "Untitled").strip()[:120]
                _atomic_write_json(meta_path, raw)
            return True
        except Exception:  # noqa: BLE001
            return False

    def delete(self, design_id: str) -> bool:
        if not _safe_id(design_id):
            return False
        try:
            with _WRITE_LOCK:
                shutil.rmtree(self._dir(design_id), ignore_errors=True)
            return True
        except Exception:  # noqa: BLE001
            return False

    def duplicate(self, design_id: str, new_id: str) -> bool:
        """Copy a saved design under ``new_id`` (a fresh server-minted id), with its name suffixed
        '(copy)' and a new created_at left to the caller via the copied meta (the caller stamps)."""
        if not (_safe_id(design_id) and _safe_id(new_id)):
            return False
        try:
            with _WRITE_LOCK:
                src = self._dir(design_id)
                if not src.exists():
                    return False
                dst = self._dir(new_id)
                shutil.copytree(src, dst, dirs_exist_ok=True)
                meta_path = dst / "meta.json"
                raw = json.loads(meta_path.read_text(encoding="utf-8"))
                raw["id"] = new_id
                raw["name"] = (str(raw.get("name", "Untitled"))[:110] + " (copy)").strip()
                _atomic_write_json(meta_path, raw)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _prune(self) -> None:
        """Drop the oldest designs beyond the cap. Called under the write lock."""
        entries = self.list()
        for entry in entries[_MAX_DESIGNS:]:
            shutil.rmtree(self._dir(entry["id"]), ignore_errors=True)


def _safe_id(design_id: str) -> bool:
    """A store id must be a plain token (no path separators / parent refs) so it can't escape the
    store root. Server-minted ids are uuid hex; this guards a hand-crafted API request."""
    return bool(design_id) and design_id.replace("-", "").replace("_", "").isalnum()


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON via a temp file + ``os.replace`` so a concurrent reader never sees a half-write."""
    payload = json.dumps(data, indent=2, allow_nan=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)
