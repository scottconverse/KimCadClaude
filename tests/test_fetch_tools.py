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
