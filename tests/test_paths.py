"""Stage 11 Slice 11.4 — the dev/installed path seam. ONE switch (KIMCAD_INSTALL_ROOT,
set by the installer's launcher): reads come from the install root, writes go to
%LOCALAPPDATA%\\KimCad. Dev behavior is byte-identical to before the seam — the whole
existing suite is that regression net; these tests pin the installed half."""

from __future__ import annotations

from pathlib import Path

import kimcad.paths as paths

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_dev_mode_is_the_repo_root(monkeypatch):
    monkeypatch.delenv("KIMCAD_INSTALL_ROOT", raising=False)
    assert paths.is_installed() is False
    assert paths.install_root() == REPO_ROOT
    assert paths.writable_root() == REPO_ROOT
    assert paths.output_dir() == REPO_ROOT / "output"
    # The browser profile is user state in EVERY mode — never inside the checkout.
    assert REPO_ROOT not in paths.webview_profile_dir().parents


def test_installed_mode_splits_read_and_write_roots(monkeypatch, tmp_path):
    install = tmp_path / "Program Files" / "KimCad"
    localapp = tmp_path / "Users" / "kim" / "AppData" / "Local"
    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(install))
    monkeypatch.setenv("LOCALAPPDATA", str(localapp))
    assert paths.is_installed() is True
    assert paths.install_root() == install  # reads: config/, tools/, the SPA
    assert paths.writable_root() == localapp / "KimCad"  # writes: never Program Files
    assert paths.output_dir() == localapp / "KimCad" / "output"
    assert paths.webview_profile_dir() == localapp / "KimCad" / "webview"


def test_installed_mode_without_localappdata_still_lands_per_user(monkeypatch, tmp_path):
    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(tmp_path / "app"))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    w = paths.writable_root()
    assert "KimCad" in str(w)
    assert str(Path.home()) in str(w)  # per-user, never the install dir


def test_macos_installed_writes_land_in_application_support(monkeypatch, tmp_path):
    # KC-8 (#13): on macOS the per-user app-data dir is ~/Library/Application Support/KimCad,
    # not the Windows-shaped ~/AppData/Local. monkeypatch sys.platform so the branch is
    # exercised on the Windows CI box too.
    monkeypatch.setattr(paths.sys, "platform", "darwin")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(tmp_path / "app"))
    appsupport = tmp_path / "home" / "Library" / "Application Support" / "KimCad"
    assert paths.writable_root() == appsupport
    assert paths.output_dir() == appsupport / "output"
    assert paths.webview_profile_dir() == appsupport / "webview"


def test_linux_installed_writes_follow_xdg_data_home(monkeypatch, tmp_path):
    # KC-8 (#13): on Linux writes follow $XDG_DATA_HOME, falling back to ~/.local/share.
    monkeypatch.setattr(paths.sys, "platform", "linux")
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(tmp_path / "app"))
    # Explicit XDG_DATA_HOME is honored.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    assert paths.writable_root() == tmp_path / "xdg" / "KimCad"
    # Without it, the XDG default ~/.local/share applies.
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert paths.writable_root() == tmp_path / "home" / ".local" / "share" / "KimCad"


def test_config_read_paths_follow_the_install_root(monkeypatch, tmp_path):
    """The yaml templates + tools resolve under the INSTALL root in installed mode —
    Config caches PROJECT_ROOT at import, so this exercises the same resolution rule
    paths.install_root applies (the launcher sets the env before Python starts; tests
    can't re-import config, so the rule itself is the contract under test)."""
    install = tmp_path / "app"
    (install / "config").mkdir(parents=True)
    (install / "config" / "default.yaml").write_text(
        "binaries:\n  openscad: tools/openscad/openscad.exe\n", encoding="utf-8"
    )
    monkeypatch.setenv("KIMCAD_INSTALL_ROOT", str(install))
    assert paths.install_root() / "config" / "default.yaml" == install / "config" / "default.yaml"
    assert (paths.install_root() / "config" / "default.yaml").exists()
