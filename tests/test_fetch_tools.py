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


# --- KC-8 (#13): off-Windows failures must be actionable, not a bare SystemExit -----------------

def test_missing_pin_off_windows_gives_an_actionable_install_hint(monkeypatch):
    # OrcaSlicer has no mac/Linux pin; on those platforms fetch must name the official download
    # + the config override + the browser fallback, not just 'No pin for ... on platform'.
    monkeypatch.setattr(ft, "_platform_key", lambda: "mac")
    with pytest.raises(SystemExit) as ei:
        ft.fetch_tool("orcaslicer", force=False)
    msg = str(ei.value)
    assert "config/local.yaml" in msg
    assert ft._OFFICIAL_DOWNLOADS["orcaslicer"] in msg
    assert "kimcad web" in msg  # the no-tools browser fallback is surfaced


def test_unverified_or_nonzip_pin_gives_the_same_hint_with_the_source(monkeypatch):
    # OpenSCAD's mac pin is a dmg + verified=False; the hint names the asset it tried.
    monkeypatch.setattr(ft, "_platform_key", lambda: "mac")
    with pytest.raises(SystemExit) as ei:
        ft.fetch_tool("openscad", force=False)
    msg = str(ei.value)
    assert ft._OFFICIAL_DOWNLOADS["openscad"] in msg
    assert ft.PINS["openscad"]["mac"].url in msg  # the auto-fetch source it tried
    assert "binaries.openscad" in msg


def test_unknown_tool_still_reports_a_usage_error(monkeypatch):
    # A genuine bad tool name stays a plain usage error (not the platform hint).
    monkeypatch.setattr(ft, "_platform_key", lambda: "linux")
    with pytest.raises(SystemExit, match="Unknown tool"):
        ft.fetch_tool("nope", force=False)
