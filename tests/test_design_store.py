"""Stage 8.5 Slice 1 — the saved-designs store.

Best-effort local persistence: save/list/get/reopen-payload/rename/delete/duplicate, every degrade
path (missing, corrupt, traversal-unsafe id, unwritable), and the cap. Nothing may raise.
"""

from __future__ import annotations

import json
from pathlib import Path

from kimcad.design_store import DesignStore, _safe_id


def _save(store: DesignStore, tmp_path: Path, *, design_id: str, name: str, when: str,
          object_type: str = "box", family: str | None = "snap_box") -> bool:
    mesh = tmp_path / f"{design_id}.stl"
    mesh.write_text("solid x\nendsolid x\n", encoding="utf-8")
    return store.save(
        design_id=design_id, name=name, prompt=f"a {object_type}", created_at=when,
        object_type=object_type, gate_status="pass", readiness_score=92, template_family=family,
        payload={"status": "completed", "template": family, "parameters": [{"name": "width"}]},
        plan={"object_type": object_type, "summary": "t"}, mesh_path=mesh,
        thumb_png=b"\x89PNG\r\n\x1a\n" + b"fakepng",
    )


def test_save_then_get_round_trips(tmp_path):
    store = DesignStore(tmp_path / "designs")
    assert _save(store, tmp_path, design_id="aaa1", name="My Box", when="2026-06-03T00:00:00+00:00")
    d = store.get("aaa1")
    assert d is not None
    assert d.name == "My Box" and d.object_type == "box" and d.readiness_score == 92
    assert d.template_family == "snap_box"
    assert d.payload["template"] == "snap_box"
    assert d.plan == {"object_type": "box", "summary": "t"}
    assert store.mesh_path("aaa1") is not None
    assert store.thumb_path("aaa1") is not None


def test_list_is_newest_first_and_lightweight(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="old1", name="Old", when="2026-06-01T00:00:00+00:00")
    _save(store, tmp_path, design_id="new1", name="New", when="2026-06-03T00:00:00+00:00")
    idx = store.list()
    assert [e["id"] for e in idx] == ["new1", "old1"]  # newest first
    assert idx[0]["has_thumb"] is True
    assert "payload" not in idx[0]  # the index is lightweight (no heavy payload)


def test_get_is_none_for_missing_or_traversal_unsafe_id(tmp_path):
    store = DesignStore(tmp_path / "designs")
    assert store.get("nope") is None
    assert store.get("../etc") is None  # traversal-unsafe -> rejected, not a read outside root
    assert store.get("a/b") is None


def test_safe_id_guards_path_separators():
    assert _safe_id("abc123") and _safe_id("a-b_c")
    assert not _safe_id("../x") and not _safe_id("a/b") and not _safe_id("") and not _safe_id("a.b")


def test_mesh_and_thumb_path_reject_traversal_ids(tmp_path):
    # S1B-001: these accessors are served directly by the thumb endpoint, so they must reject a
    # traversal id rather than resolve a path outside the store root.
    store = DesignStore(tmp_path / "designs")
    assert store.mesh_path("../etc") is None
    assert store.thumb_path("a/b") is None
    assert store.mesh_path("..") is None and store.thumb_path("..") is None


def test_list_degrades_on_a_corrupt_meta(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="good1", name="Good", when="2026-06-02T00:00:00+00:00")
    bad = (tmp_path / "designs" / "bad1")
    bad.mkdir(parents=True)
    (bad / "meta.json").write_text("{not json", encoding="utf-8")
    idx = store.list()
    assert [e["id"] for e in idx] == ["good1"]  # the corrupt one is skipped, the good one survives


def test_rename(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="r1", name="Before", when="2026-06-03T00:00:00+00:00")
    assert store.rename("r1", "After")
    assert store.get("r1").name == "After"
    assert store.rename("../x", "nope") is False  # unsafe id


def test_delete(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="d1", name="Doomed", when="2026-06-03T00:00:00+00:00")
    assert store.delete("d1")
    assert store.get("d1") is None
    assert store.list() == []


def test_duplicate(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="src1", name="Original", when="2026-06-03T00:00:00+00:00")
    assert store.duplicate("src1", "dup1")
    dup = store.get("dup1")
    assert dup is not None and dup.id == "dup1"
    assert "(copy)" in dup.name
    assert store.mesh_path("dup1") is not None  # the mesh copied too
    # both exist independently
    assert {e["id"] for e in store.list()} == {"src1", "dup1"}


def test_save_is_best_effort_on_an_unwritable_root(tmp_path):
    # Root path is a FILE -> mkdir fails -> save returns False, never raises.
    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")
    store = DesignStore(afile / "designs")
    mesh = tmp_path / "m.stl"
    mesh.write_text("solid\nendsolid\n", encoding="utf-8")
    ok = store.save(
        design_id="x1", name="n", prompt="p", created_at="2026-06-03T00:00:00+00:00",
        object_type="box", gate_status="pass", readiness_score=None, template_family=None,
        payload={}, plan=None, mesh_path=mesh, thumb_png=None,
    )
    assert ok is False
    assert store.list() == []


def test_cap_drops_oldest(tmp_path, monkeypatch):
    import kimcad.design_store as ds
    monkeypatch.setattr(ds, "_MAX_DESIGNS", 3)
    store = DesignStore(tmp_path / "designs")
    for i in range(5):
        _save(store, tmp_path, design_id=f"c{i}", name=f"d{i}",
              when=f"2026-06-0{i+1}T00:00:00+00:00")
    ids = {e["id"] for e in store.list()}
    assert len(ids) == 3
    assert ids == {"c4", "c3", "c2"}  # the 3 newest


def test_atomic_meta_is_valid_json_after_save(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="j1", name="J", when="2026-06-03T00:00:00+00:00")
    meta = json.loads((tmp_path / "designs" / "j1" / "meta.json").read_text(encoding="utf-8"))
    assert meta["id"] == "j1" and meta["name"] == "J"


def test_export_then_import_round_trips(tmp_path):
    store = DesignStore(tmp_path / "designs")
    _save(store, tmp_path, design_id="exp1", name="Exported", when="2026-06-03T00:00:00+00:00")
    blob = store.export_bytes("exp1")
    assert blob is not None and blob[:2] == b"PK"  # a zip
    assert store.import_bytes(blob, "imp1") is True
    imported = store.get("imp1")
    assert imported is not None and imported.id == "imp1" and imported.name == "Exported"
    assert store.mesh_path("imp1") is not None  # mesh came across
    # original + imported coexist
    assert {e["id"] for e in store.list()} == {"exp1", "imp1"}


def test_export_is_none_for_missing_or_unsafe_id(tmp_path):
    store = DesignStore(tmp_path / "designs")
    assert store.export_bytes("nope") is None
    assert store.export_bytes("../etc") is None


def test_import_rejects_a_non_design_or_zip_slip_archive(tmp_path):
    import io
    import zipfile
    store = DesignStore(tmp_path / "designs")
    # Not a zip.
    assert store.import_bytes(b"not a zip", "x1") is False
    # A zip MISSING the required mesh.stl -> rejected.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("meta.json", '{"id":"a","name":"n"}')
    assert store.import_bytes(buf.getvalue(), "x2") is False
    # A zip-slip attempt: an entry named ../evil.txt must NOT be written outside the design dir.
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as z:
        z.writestr("meta.json", '{"id":"a","name":"n"}')
        z.writestr("mesh.stl", "solid\nendsolid\n")
        z.writestr("../evil.txt", "pwned")
    assert store.import_bytes(buf2.getvalue(), "x3") is True  # the valid design imports
    assert not (tmp_path / "evil.txt").exists()  # the traversal entry was ignored, not written


def test_import_rejects_an_oversized_member(tmp_path, monkeypatch):
    # EI-001: a member that inflates past the per-member ceiling is rejected (no OOM / unbounded
    # read). Shrink the cap so a normal entry exceeds it, proving the bounded read.
    import io
    import zipfile
    import kimcad.design_store as ds
    monkeypatch.setattr(ds, "_MAX_IMPORT_MEMBER", 8)
    store = DesignStore(tmp_path / "designs")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("meta.json", '{"id":"a","name":"a long enough name to exceed the tiny cap"}')
        z.writestr("mesh.stl", "solid x\nendsolid x\n")
    assert store.import_bytes(buf.getvalue(), "big1") is False  # rejected, not read unbounded
    assert store.get("big1") is None  # nothing written
