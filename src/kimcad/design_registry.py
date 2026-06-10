"""The per-design server state, extracted from the webapp closure (ENG-004, Stage 9).

One object owns every per-design registry/cache plus the lock and the three LOAD-BEARING
protocols the 2026-06-09 audit flagged as "correct but enforced by comments":

1. **Eviction in lockstep** — dropping a design id must clear EVERY registry it appears in
   AND its on-disk directory (:meth:`evict_locked`); forgetting one registry leaks state.
2. **Cap enforcement** — the mesh registry is LRU-bounded; evicting past the cap must run
   the full lockstep eviction (:meth:`enforce_caps_locked`).
3. **The geometry-version protocol** — a re-render bumps the version; a slice captures the
   version it sliced and is registered ONLY if it still matches (:meth:`bump_version_locked`
   / :meth:`register_gcode_locked` / :meth:`cache_slice_locked`), so a re-render landing
   mid-slice can never leave stale G-code registered.

Methods suffixed ``_locked`` REQUIRE ``self.lock`` to be held (they run inside the
handlers' existing multi-field transactions); the others take the lock themselves.
The webapp still binds local names to these fields (``registry = reg.meshes`` …) — a
transitional seam; the full name-flattening + router split is scheduled for Stage-10-start.
"""

from __future__ import annotations

import itertools
import shutil
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

# Hardening caps (ENG-004): bound in-memory state.
MAX_REGISTRY = 50  # keep at most the last N rendered meshes; evict oldest
# ENG-406: the slice cache is a DIFFERENT quantity (cached G-code results, not meshes);
# slices are heavier and re-confirms rarer, so a smaller bound is plenty.
MAX_SLICE_CACHE = 16


class DesignRegistry:
    """Owns the per-design state for one running web server."""

    def __init__(self, web_root: Path):
        self.web_root = web_root
        self.web_root.mkdir(parents=True, exist_ok=True)
        # QA-003: clear stale per-design dirs from a previous run — the in-memory state and
        # id counter reset each start, so old output/web/<id> dirs would otherwise accumulate.
        for child in self.web_root.iterdir():
            if child.is_dir() and child.name.isdigit():
                shutil.rmtree(child, ignore_errors=True)

        self.lock = threading.Lock()
        # ENG-004: bounded LRU-by-insertion registries — oldest evicted past the cap.
        self.meshes: "OrderedDict[int, Path]" = OrderedDict()
        self.gcode: "OrderedDict[int, Path]" = OrderedDict()
        self.step: "OrderedDict[int, Path]" = OrderedDict()  # Stage 8 Slice 4: STEP exports
        # ENG-001 (gate safety): the verdict per design id so slice/send refuse server-side.
        self.gate_status: dict[int, str] = {}
        # ENG-001 (stage-8.5): per-design geometry version (see protocol 3 above).
        self.geometry_version: dict[int, int] = {}
        # ENG-003: slices cached by (rid, printer, material); serialized by the caller's
        # slice_lock — this object only owns registration + invalidation.
        self.slice_cache: "OrderedDict[tuple[int, Any, Any], tuple[dict[str, Any], Path | None]]" = OrderedDict()
        # Stage 5: per-design template re-render state (base plan + family name).
        self.template_state: dict[int, tuple[Any, str]] = {}
        # Stage 8.5 Slice 1: the saveable snapshot per design id.
        self.snapshot: dict[int, dict[str, Any]] = {}
        # QA-002: a stable saved_id per live rid (auto-save convergence).
        self.saved_id: dict[int, str] = {}
        self._counter = itertools.count(1)
        self._version_counter = itertools.count(1)  # cache-busting suffix for re-renders

    # --- ids ------------------------------------------------------------------------

    def new_rid(self) -> int:
        with self.lock:
            return next(self._counter)

    def next_mesh_version(self) -> int:
        """Cache-busting suffix for a re-rendered mesh URL. Uniqueness is all the cache
        buster needs; the only call site runs inside a ``with reg.lock:`` transaction
        (ENG-004, stage-9 gate: no free-standing atomicity claim — the lock is the
        guarantee)."""
        return next(self._version_counter)

    # --- protocol 1+2: eviction in lockstep + cap enforcement ------------------------

    def evict_locked(self, rid: int) -> None:
        """QA-003: drop ``rid`` from EVERY registry/cache — ``meshes`` included (TEST-002,
        stage-9 gate: leaving the mesh behind while the gate verdict vanished was a
        fail-open seam, since the slice gate treats a MISSING verdict as not-failed) —
        AND remove its on-disk dir. Idempotent. REQUIRES ``self.lock`` held (runs inside
        the handlers' transactions; ``enforce_caps_locked`` pops the mesh first, which the
        ``pop(rid, None)`` here tolerates)."""
        self.meshes.pop(rid, None)
        self.gcode.pop(rid, None)
        self.step.pop(rid, None)
        self.gate_status.pop(rid, None)
        self.geometry_version.pop(rid, None)
        self.template_state.pop(rid, None)
        self.snapshot.pop(rid, None)
        self.saved_id.pop(rid, None)
        for k in [k for k in self.slice_cache if k[0] == rid]:
            self.slice_cache.pop(k, None)
        shutil.rmtree(self.web_root / str(rid), ignore_errors=True)

    def enforce_caps_locked(self, max_registry: int = MAX_REGISTRY) -> None:
        """ENG-004 / QA-003: cap the mesh registry, running the FULL lockstep eviction
        (incl. on-disk cleanup) for everything that falls off. REQUIRES ``self.lock``.
        The cap is a parameter so the caller's module global stays the (test-patchable)
        source of truth."""
        while len(self.meshes) > max_registry:
            old_rid, _ = self.meshes.popitem(last=False)
            self.evict_locked(old_rid)

    # --- protocol 3: the geometry-version protocol ------------------------------------

    def bump_version_locked(self, rid: int) -> int:
        """A re-render changed the geometry: bump the version and drop every cached slice
        AND the registered G-code of the old shape (safety: the old shape must never be
        downloadable or sendable after the part was re-shaped). REQUIRES ``self.lock``.
        Returns the new version."""
        v = self.geometry_version.get(rid, 0) + 1
        self.geometry_version[rid] = v
        self.gcode.pop(rid, None)
        for k in [k for k in self.slice_cache if k[0] == rid]:
            self.slice_cache.pop(k, None)
        return v

    def version_locked(self, rid: int) -> int:
        """The current geometry version (0 if never re-rendered). REQUIRES ``self.lock``."""
        return self.geometry_version.get(rid, 0)

    def register_gcode_locked(self, rid: int, gcode_path: Path, sliced_version: int) -> bool:
        """ENG-001: register finished G-code ONLY if the geometry version still matches the
        one captured when the slice started — a re-render landing mid-slice means this
        G-code is of the OLD shape. REQUIRES ``self.lock``. True when registered."""
        if self.geometry_version.get(rid, 0) != sliced_version:
            return False
        self.gcode[rid] = gcode_path
        return True

    def cache_slice_locked(
        self,
        rid: int,
        key: tuple[int, Any, Any],
        info: dict[str, Any],
        gcode_path: Path | None,
        sliced_version: int,
        max_cache: int = MAX_SLICE_CACHE,
    ) -> bool:
        """Cache a slice result under the same version guard, enforcing the cache cap.
        REQUIRES ``self.lock``. True when cached (False = stale, dropped)."""
        if self.geometry_version.get(rid, 0) != sliced_version:
            return False
        self.slice_cache[key] = (info, gcode_path)
        while len(self.slice_cache) > max_cache:
            self.slice_cache.popitem(last=False)
        return True
