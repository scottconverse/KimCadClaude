"""Stage 8.5 Slice 6 — unit tests for the user settings store."""

from __future__ import annotations

from kimcad.settings_store import SettingsStore


def test_missing_file_reads_as_empty(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    assert store.all() == {}
    assert store.get("default_printer") is None
    assert store.get("default_printer", "fallback") == "fallback"


def test_update_persists_and_merges(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.update({"default_printer": "p2s"}) is True
    assert path.exists()
    assert store.all() == {"default_printer": "p2s"}
    # A second update merges rather than replacing.
    assert store.update({"default_material": "pla"}) is True
    assert store.all() == {"default_printer": "p2s", "default_material": "pla"}
    # A fresh store instance reads the same persisted state (it's on disk, not in memory).
    assert SettingsStore(path).all() == {"default_printer": "p2s", "default_material": "pla"}


def test_update_ignores_unknown_keys(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"default_printer": "p2s", "unknown_field": "ignored", "nested": {"x": 1}})
    # Only the allowed key is kept; the crafted/stale keys are dropped.
    assert store.all() == {"default_printer": "p2s"}


def test_update_none_clears_a_key(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"default_printer": "p2s", "default_material": "pla"})
    store.update({"default_printer": None})  # clear it (back to config default)
    assert store.all() == {"default_material": "pla"}


def test_corrupt_file_reads_as_empty(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{ this is not json", encoding="utf-8")
    store = SettingsStore(path)
    assert store.all() == {}
    # And a subsequent update still works (overwrites the garbage with valid JSON).
    assert store.update({"default_printer": "p2s"}) is True
    assert store.all() == {"default_printer": "p2s"}


def test_non_object_json_reads_as_empty(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")  # valid JSON, wrong shape
    assert SettingsStore(path).all() == {}


def test_creates_parent_dir_on_first_write(tmp_path):
    # The ~/.kimcad dir may not exist yet on a fresh machine; update() must create it.
    path = tmp_path / "fresh" / "nested" / "settings.json"
    store = SettingsStore(path)
    assert store.update({"default_material": "petg"}) is True
    assert path.exists()
    assert store.all() == {"default_material": "petg"}
