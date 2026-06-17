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


def test_concurrent_updates_keep_a_coherent_file_and_sentinel(tmp_path, _fake_keyring):
    """TEST-004 (stage-BCD gate): the threaded web server hammers update() concurrently —
    the file must stay parseable, the sentinel intact, and the last writer's non-secret
    values present (no lost-update corruption, no raw key on disk)."""
    import json
    import threading

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    store.update({"openrouter_api_key": "sk-or-base"})

    def writer(i: int) -> None:
        store.update({"cloud_model": f"model-{i}", "cloud_enabled": i % 2 == 0})

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(24)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["openrouter_api_key"] == "@keyring"  # sentinel survived the storm
    assert "sk-or-base" not in path.read_text(encoding="utf-8")
    assert on_disk["cloud_model"].startswith("model-")  # a coherent last write, not a mash
    assert store.all()["openrouter_api_key"] == "sk-or-base"


def test_bom_settings_file_still_reads_and_migrates(tmp_path, _fake_keyring):
    """QA-D-002 (stage-BCD gate): a UTF-8-BOM settings.json (PowerShell Out-File default)
    must parse — silently reading {} also silently blocked the plaintext-key migration."""
    import json

    path = tmp_path / "settings.json"
    payload = json.dumps({"openrouter_api_key": "sk-or-bom", "cloud_enabled": True})
    path.write_bytes(b"\xef\xbb\xbf" + payload.encode("utf-8"))
    store = SettingsStore(path)  # init migrates
    assert store.all()["cloud_enabled"] is True
    assert store.all()["openrouter_api_key"] == "sk-or-bom"
    assert _fake_keyring.passwords[("KimCad", "openrouter_api_key")] == "sk-or-bom"
    assert "sk-or-bom" not in path.read_text(encoding="utf-8-sig")


def test_literal_sentinel_value_is_refused_as_a_key(tmp_path, monkeypatch):
    """ENG-106 (stage-BCD gate): "@keyring" is reserved — in file-fallback mode storing it
    literally would be misread as the sentinel and the key would silently vanish."""
    from conftest import FakeKeyring

    from kimcad import settings_store

    monkeypatch.setattr(settings_store, "_keyring", lambda: FakeKeyring(fail=True))
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"openrouter_api_key": "@keyring", "cloud_enabled": True})
    assert "openrouter_api_key" not in store.all()  # refused, not corrupted
    assert store.all()["cloud_enabled"] is True  # the rest of the batch still landed


def test_update_failure_rolls_back_the_vault(tmp_path, _fake_keyring, monkeypatch):
    """ENG-102 (stage-BCD gate): "the prior settings stand" includes the VAULT — a file
    write failure after the vault was updated must restore the previous secret."""
    from kimcad import settings_store

    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.update({"openrouter_api_key": "sk-or-old"}) is True

    def _boom(*a, **kw):
        raise OSError("disk full")

    real_write = settings_store._atomic_write_json
    monkeypatch.setattr(settings_store, "_atomic_write_json", _boom)
    assert store.update({"openrouter_api_key": "sk-or-new"}) is False
    # Restore ONLY the write (monkeypatch.undo() would also strip the autouse fake-keyring
    # patch and let this test read the developer's real vault).
    monkeypatch.setattr(settings_store, "_atomic_write_json", real_write)
    # The vault still holds the OLD secret — the failed save didn't half-apply.
    assert _fake_keyring.passwords[("KimCad", "openrouter_api_key")] == "sk-or-old"
    assert store.all()["openrouter_api_key"] == "sk-or-old"


def test_transient_keyring_downgrade_is_flagged_once(tmp_path, monkeypatch):
    """ENG-005 (audit-team-b4): a key save where the credential backend passes the pre-save
    HEALTH PROBE but then refuses the set_password (a transient failure) downgrades keyring->file.
    That moment must be SIGNALLED once — take_secret_downgraded() returns True exactly once, then
    clears — and the key honestly lands in the file (key_storage()=="file")."""
    import json

    from kimcad import settings_store

    class ProbeOkSetFails:
        """Healthy get_password (the health probe + rollback read pass) but set_password raises —
        models a backend that flaked precisely during the save."""

        def __init__(self):
            self.passwords: dict[tuple[str, str], str] = {}

        def get_password(self, service, username):
            return self.passwords.get((service, username))

        def set_password(self, service, username, password):
            raise RuntimeError("credential store busy")

        def delete_password(self, service, username):
            self.passwords.pop((service, username), None)

    fake = ProbeOkSetFails()
    monkeypatch.setattr(settings_store, "_keyring", lambda: fake)
    path = tmp_path / "settings.json"
    store = SettingsStore(path)
    assert store.take_secret_downgraded() is False  # nothing happened yet

    assert store.update({"openrouter_api_key": "sk-or-transient"}) is True
    # The key honestly fell back to the file (the backend refused), and that's disclosed.
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["openrouter_api_key"] == "sk-or-transient"
    assert store.key_storage() == "file"
    # ...and the transient downgrade is signalled exactly ONCE (read-and-clear).
    assert store.take_secret_downgraded() is True
    assert store.take_secret_downgraded() is False


def test_keyring_success_does_not_flag_a_downgrade(tmp_path, _fake_keyring):
    """ENG-005: a normal save that lands in the keyring must NOT raise the downgrade signal —
    the flag is only for the transient keyring->file fallback, not the healthy path."""
    store = SettingsStore(tmp_path / "settings.json")
    assert store.update({"openrouter_api_key": "sk-or-ok"}) is True
    assert store.key_storage() == "keyring"
    assert store.take_secret_downgraded() is False


def test_broken_backend_is_disclosed_before_any_key_is_saved(tmp_path, monkeypatch):
    """QA-D-001 (stage-BCD gate): key_storage()'s pre-save answer must reflect backend
    HEALTH, not importability — a broken vault means a new key would land in the file."""

    from kimcad import settings_store

    monkeypatch.setattr(settings_store, "_keyring", lambda: None)  # health probe failed
    store = SettingsStore(tmp_path / "settings.json")
    assert store.key_storage() == "file"
