"""ENG-004 (Stage 9): the per-design state protocols are METHODS now — test them directly,
not only through the 125 webapp route tests that exercise them in situ."""

from __future__ import annotations

from pathlib import Path

from kimcad.design_registry import DesignRegistry


def _reg(tmp_path) -> DesignRegistry:
    return DesignRegistry(tmp_path / "web")


def test_init_clears_stale_numeric_dirs_only(tmp_path):
    root = tmp_path / "web"
    (root / "7").mkdir(parents=True)
    (root / "assets").mkdir()
    (root / "assets" / "keep.js").write_text("x")
    DesignRegistry(root)
    assert not (root / "7").exists()  # stale per-design dir cleared
    assert (root / "assets" / "keep.js").exists()  # non-numeric content untouched


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
