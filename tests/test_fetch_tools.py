import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "fetch_tools.py"
_spec = importlib.util.spec_from_file_location("kimcad_fetch_tools", _SCRIPT)
ft = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = ft  # dataclass needs the module registered to resolve itself
_spec.loader.exec_module(ft)


def _pin(sha):
    return ft.ToolPin(
        url="https://example/x.zip",
        archive="zip",
        exe_name="x.exe",
        dest_subdir="x",
        verified=True,
        sha256=sha,
    )


def test_sha256_matches_hashlib(tmp_path):
    f = tmp_path / "blob.bin"
    f.write_bytes(b"kimcad" * 1000)
    assert ft._sha256(f) == hashlib.sha256(b"kimcad" * 1000).hexdigest()


def test_verify_checksum_passes_on_match(tmp_path, capsys):
    f = tmp_path / "a.zip"
    f.write_bytes(b"payload")
    ft._verify_checksum("tool", _pin(hashlib.sha256(b"payload").hexdigest()), f)
    assert "ok" in capsys.readouterr().out


def test_verify_checksum_aborts_on_mismatch(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"payload")
    with pytest.raises(SystemExit, match="checksum mismatch"):
        ft._verify_checksum("tool", _pin("0" * 64), f)


def test_verify_checksum_records_when_unpinned(tmp_path, capsys):
    # sha256=None means "trust on first fetch": print the digest, do not abort.
    f = tmp_path / "a.zip"
    f.write_bytes(b"payload")
    ft._verify_checksum("tool", _pin(None), f)
    out = capsys.readouterr().out
    assert hashlib.sha256(b"payload").hexdigest() in out


def test_orcaslicer_win_pin_is_verified_and_checksummed():
    # The slicer pin is load-bearing (real-print path); guard it from regressing
    # to an unverified or checksum-less state.
    pin = ft.PINS["orcaslicer"]["win"]
    assert pin.verified is True
    assert pin.sha256 and len(pin.sha256) == 64
    assert pin.archive == "zip"


def test_parse_version_handles_tags_and_garbage():
    assert ft._parse_version("v2.4.0") == (2, 4, 0)
    assert ft._parse_version("2.4.0-alpha") == (2, 4, 0)
    assert ft._parse_version("v2.10.3-rc1") == (2, 10, 3)
    assert ft._parse_version("nightly") is None


def test_pinned_tag_extracts_release_tag():
    assert ft._pinned_tag(ft.PINS["orcaslicer"]["win"]) == "v2.4.0-alpha"


def test_orcaslicer_pin_has_upgrade_check_config():
    import fnmatch

    pin = ft.PINS["orcaslicer"]["win"]
    assert pin.github_repo == "OrcaSlicer/OrcaSlicer"
    assert fnmatch.fnmatch("OrcaSlicer_Windows_V2.4.0_portable.zip", pin.asset_glob)


def _rel(tag, prerelease, asset_name="OrcaSlicer_Windows_V9_portable.zip"):
    return {
        "tag_name": tag,
        "prerelease": prerelease,
        "draft": False,
        "assets": [{"name": asset_name, "browser_download_url": f"https://x/{asset_name}"}],
    }


def test_check_upgrade_reports_newer_stable(monkeypatch, capsys):
    # A stable at-or-above the pinned base is reported; a newer *prerelease* is not.
    releases = [_rel("v2.5.0-beta", True), _rel("v2.4.0", False), _rel("v2.3.2", False)]
    monkeypatch.setattr(ft, "_github_releases", lambda repo: releases)
    ft.check_upgrade("orcaslicer", ft.PINS["orcaslicer"]["win"])
    out = capsys.readouterr().out
    assert "STABLE AVAILABLE" in out
    assert "v2.4.0" in out
    assert "2.5.0" not in out  # prerelease must be ignored


def test_check_upgrade_ignores_prerelease_and_older(monkeypatch, capsys):
    releases = [_rel("v2.5.0-beta", True), _rel("v2.3.2", False)]
    monkeypatch.setattr(ft, "_github_releases", lambda repo: releases)
    ft.check_upgrade("orcaslicer", ft.PINS["orcaslicer"]["win"])
    out = capsys.readouterr().out
    assert "no stable release" in out


def test_check_upgrade_skips_stable_without_matching_asset(monkeypatch, capsys):
    # A stable that ships no Windows-portable asset is no use to us.
    releases = [_rel("v2.6.0", False, asset_name="OrcaSlicer_Linux_V2.6.0.AppImage")]
    monkeypatch.setattr(ft, "_github_releases", lambda repo: releases)
    ft.check_upgrade("orcaslicer", ft.PINS["orcaslicer"]["win"])
    assert "no stable release" in capsys.readouterr().out


def test_check_upgrade_survives_network_error(monkeypatch, capsys):
    def boom(repo):
        raise ft.urllib.error.URLError("offline")

    monkeypatch.setattr(ft, "_github_releases", boom)
    ft.check_upgrade("orcaslicer", ft.PINS["orcaslicer"]["win"])
    assert "upgrade check failed" in capsys.readouterr().out
