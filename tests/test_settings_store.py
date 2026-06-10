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


def test_clear_drops_all_overrides(tmp_path):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.update({"default_printer": "p2s", "cloud_enabled": True})
    assert store.all() != {}
    assert store.clear() is True
    assert store.all() == {}  # pristine — no stale keys
    import json

    assert json.loads(path.read_text(encoding="utf-8")) == {}


def test_creates_parent_dir_on_first_write(tmp_path):
    # The ~/.kimcad dir may not exist yet on a fresh machine; update() must create it.
    path = tmp_path / "fresh" / "nested" / "settings.json"
    store = SettingsStore(path)
    assert store.update({"default_material": "petg"}) is True
    assert path.exists()
    assert store.all() == {"default_material": "petg"}


# --- ENG-001 (stage-C): the OpenRouter secret lives in the OS credential store -----------


def test_secret_goes_to_keyring_file_holds_sentinel(tmp_path, _fake_keyring):
    import json

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.update({"openrouter_api_key": "sk-or-secret123"}) is True
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["openrouter_api_key"] == "@keyring"  # NEVER the secret
    assert "sk-or-secret123" not in path.read_text(encoding="utf-8")
    assert _fake_keyring.passwords[("KimCad", "openrouter_api_key")] == "sk-or-secret123"
    # all() resolves the sentinel transparently - consumers are unchanged.
    assert store.all()["openrouter_api_key"] == "sk-or-secret123"
    assert store.key_storage() == "keyring"


def test_legacy_plaintext_key_migrates_on_init(tmp_path, _fake_keyring):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"openrouter_api_key": "sk-or-legacy", "cloud_enabled": True}),
                    encoding="utf-8")
    store = SettingsStore(path)  # init runs the one-time migration
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["openrouter_api_key"] == "@keyring"
    assert _fake_keyring.passwords[("KimCad", "openrouter_api_key")] == "sk-or-legacy"
    assert store.all()["openrouter_api_key"] == "sk-or-legacy"
    assert store.all()["cloud_enabled"] is True  # non-secrets untouched


def test_broken_keyring_falls_back_to_file_and_discloses(tmp_path, monkeypatch):
    import json

    from conftest import FakeKeyring

    from kimcad import settings_store

    monkeypatch.setattr(settings_store, "_keyring", lambda: FakeKeyring(fail=True))
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.update({"openrouter_api_key": "sk-or-fallback"}) is True
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["openrouter_api_key"] == "sk-or-fallback"  # honest file fallback
    assert store.key_storage() == "file"  # ...and DISCLOSED as such
    assert store.all()["openrouter_api_key"] == "sk-or-fallback"


def test_clearing_the_key_removes_it_from_keyring_too(tmp_path, _fake_keyring):
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.update({"openrouter_api_key": "sk-or-gone"})
    assert ("KimCad", "openrouter_api_key") in _fake_keyring.passwords
    store.update({"openrouter_api_key": None})
    assert ("KimCad", "openrouter_api_key") not in _fake_keyring.passwords
    assert "openrouter_api_key" not in store.all()


def test_reset_clears_the_keyring_entry(tmp_path, _fake_keyring):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"openrouter_api_key": "sk-or-reset", "cloud_enabled": True})
    assert store.clear() is True
    assert ("KimCad", "openrouter_api_key") not in _fake_keyring.passwords
    assert store.all() == {}


def test_sentinel_with_missing_keyring_entry_reads_as_no_key(tmp_path, _fake_keyring):
    import json

    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"openrouter_api_key": "@keyring"}), encoding="utf-8")
    store = SettingsStore(path)
    # The credential-store entry is gone (e.g. deleted by the user in Credential Manager):
    # the key honestly reads as absent, never as the literal sentinel.
    assert "openrouter_api_key" not in store.all()
