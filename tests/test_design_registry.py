"""ENG-004 (Stage 9): the per-design state protocols are METHODS now — test them directly,
not only through the 125 webapp route tests that exercise them in situ."""

from __future__ import annotations

import os
import time
from pathlib import Path

from kimcad.design_registry import DesignRegistry


def _reg(tmp_path) -> DesignRegistry:
    return DesignRegistry(tmp_path / "web")


def test_init_clears_stale_numeric_dirs_only(tmp_path):
    root = tmp_path / "web"
    (root / "7").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "assets" / "keep.js").write_text("x")
    # Backdate the stale per-design dir past the cleanup grace window (QA-GG-003) so it qualifies
    # as "from an ended run".
    old = time.time() - 3600
    os.utime(root / "7", (old, old))
    DesignRegistry(root)
    assert not (root / "7").exists()  # stale per-design dir cleared
    assert (root / "assets" / "keep.js").exists()  # non-numeric content untouched


def test_init_spares_a_recently_touched_dir(tmp_path):
    # QA-GG-003: a concurrent `kimcad web` instance is actively writing output/web/3 — a second
    # instance's startup cleanup must NOT delete it (doing so 404'd the first instance's live mesh).
    root = tmp_path / "web"
    (root / "3").mkdir(parents=True)  # freshly created → within the grace window
    DesignRegistry(root)
    assert (root / "3").exists()  # spared, not clobbered


def test_eviction_is_lockstep_across_every_registry_and_disk(tmp_path):
    reg = _reg(tmp_path)
    rid = reg.new_rid()
    d = reg.web_root / str(rid)
    d.mkdir(parents=True)
    with reg.lock:
        reg.meshes[rid] = d / "m.stl"
        reg.gcode[rid] = d / "g.3mf"
        reg.step[rid] = d / "s.step"
        reg.gate_status[rid] = "pass"
        reg.geometry_version[rid] = 3
        reg.template_state[rid] = (object(), "box")
        reg.snapshot[rid] = {"x": 1}
        reg.saved_id[rid] = "abc"
        reg.slice_cache[(rid, "p", "m")] = ({}, None)
        reg.slice_cache[(999, "p", "m")] = ({}, None)  # another design's entry survives
        reg.evict_locked(rid)
    assert rid not in reg.gcode and rid not in reg.step
    assert rid not in reg.gate_status and rid not in reg.geometry_version
    assert rid not in reg.template_state and rid not in reg.snapshot
    assert rid not in reg.saved_id
    assert (rid, "p", "m") not in reg.slice_cache
    assert (999, "p", "m") in reg.slice_cache
    assert not d.exists()  # on-disk dir reclaimed


def test_cap_enforcement_runs_full_eviction_for_the_fallen(tmp_path):
    reg = _reg(tmp_path)
    with reg.lock:
        for i in range(1, 5):
            reg.meshes[i] = Path(f"m{i}.stl")
            reg.gate_status[i] = "pass"
        reg.enforce_caps_locked(max_registry=2)
    assert list(reg.meshes) == [3, 4]  # oldest evicted first
    assert 1 not in reg.gate_status and 2 not in reg.gate_status  # lockstep, not just meshes


def test_version_guard_drops_a_stale_slice_and_gcode(tmp_path):
    reg = _reg(tmp_path)
    rid = reg.new_rid()
    with reg.lock:
        captured = reg.version_locked(rid)  # 0 — the version this slice runs against
        reg.bump_version_locked(rid)  # a re-render lands mid-slice
        assert reg.register_gcode_locked(rid, Path("g.3mf"), captured) is False
        assert rid not in reg.gcode
        assert reg.cache_slice_locked(rid, (rid, "p", "m"), {}, None, captured) is False
        assert (rid, "p", "m") not in reg.slice_cache
        # The CURRENT version registers fine.
        now = reg.version_locked(rid)
        assert reg.register_gcode_locked(rid, Path("g.3mf"), now) is True
        assert reg.cache_slice_locked(rid, (rid, "p", "m"), {}, None, now) is True


def test_bump_drops_old_gcode_and_cached_slices(tmp_path):
    reg = _reg(tmp_path)
    rid = reg.new_rid()
    with reg.lock:
        v = reg.version_locked(rid)
        reg.register_gcode_locked(rid, Path("old.3mf"), v)
        reg.cache_slice_locked(rid, (rid, "p", "m"), {}, None, v)
        reg.bump_version_locked(rid)
        # Safety: the old shape can't be downloaded or sent after the part re-shaped.
        assert rid not in reg.gcode
        assert (rid, "p", "m") not in reg.slice_cache


def test_eviction_clears_the_mesh_itself(tmp_path):
    """TEST-002 (stage-9 gate): evict_locked must pop `meshes` too — leaving the mesh
    while the gate verdict vanished was FAIL-OPEN (the slice gate treats a missing verdict
    as not-failed)."""
    reg = _reg(tmp_path)
    rid = reg.new_rid()
    with reg.lock:
        reg.meshes[rid] = Path("m.stl")
        reg.gate_status[rid] = "fail"
        reg.evict_locked(rid)
    assert rid not in reg.meshes  # the mesh is gone WITH its verdict — fail-closed


def test_evict_is_idempotent_and_tolerates_unknown_rids(tmp_path):
    """TEST-006: double-evict and never-registered rids are no-ops, never errors."""
    reg = _reg(tmp_path)
    with reg.lock:
        reg.evict_locked(424242)  # never registered
        rid = 7
        reg.meshes[rid] = Path("m.stl")
        reg.evict_locked(rid)
        reg.evict_locked(rid)  # again — idempotent
    assert rid not in reg.meshes


def test_slice_cache_cap_actually_evicts(tmp_path):
    """TEST-006: the cache cap demonstrably drops the oldest entry."""
    reg = _reg(tmp_path)
    rid = reg.new_rid()
    with reg.lock:
        v = reg.version_locked(rid)
        for i in range(3):
            assert reg.cache_slice_locked(rid, (rid, f"p{i}", "m"), {}, None, v, max_cache=2)
    assert (rid, "p0", "m") not in reg.slice_cache  # oldest evicted
    assert (rid, "p2", "m") in reg.slice_cache
