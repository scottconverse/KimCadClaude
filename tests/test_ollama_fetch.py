"""Unit tests for the portable-Ollama fetcher (kimcad.ollama_fetch).

Network is injected (a synthetic in-memory zip via a fake opener), so download → SHA-256 verify
→ zip-slip-guarded extract is proven here with no network. The real ~1.4 GB fetch is a separate
real_tool integration test.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path

import pytest

from kimcad import ollama_fetch as of


def _make_zip(members: dict[str, bytes]) -> bytes:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return bio.getvalue()


class _FakeResp:
    def __init__(self, data: bytes, *, send_length: bool = True) -> None:
        self._buf = io.BytesIO(data)
        self.headers = {"Content-Length": str(len(data))} if send_length else {}

    def read(self, n: int) -> bytes:
        return self._buf.read(n)

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *a: object) -> bool:
        return False


def _opener(data: bytes, *, send_length: bool = True):
    def _open(url: str, timeout: float | None = None) -> _FakeResp:
        return _FakeResp(data, send_length=send_length)

    return _open


def test_fetch_happy_path_extracts_and_reports_progress(tmp_path: Path) -> None:
    data = _make_zip({"ollama.exe": b"BINARY-CONTENT", "lib/ollama/runner.dll": b"RUN"})
    sha = hashlib.sha256(data).hexdigest()
    progress: list[tuple[int, int]] = []

    exe = of.fetch_portable_ollama(
        tmp_path,
        url="http://example/ollama.zip",
        sha256=sha,
        opener=_opener(data),
        progress=lambda d, t: progress.append((d, t)),
        chunk=4,
    )

    assert exe == tmp_path / "ollama.exe"
    assert (tmp_path / "ollama.exe").read_bytes() == b"BINARY-CONTENT"
    assert (tmp_path / "lib" / "ollama" / "runner.dll").read_bytes() == b"RUN"
    # progress climbed to the full size
    assert progress and progress[-1][0] == len(data)
    # the temp download was cleaned up
    assert not list(tmp_path.glob("kimcad-ollama-*.zip"))


def test_fetch_unknown_length_falls_back_to_pinned_size(tmp_path: Path) -> None:
    data = _make_zip({"ollama.exe": b"X"})
    sha = hashlib.sha256(data).hexdigest()
    seen: list[tuple[int, int]] = []
    of.fetch_portable_ollama(
        tmp_path, sha256=sha, opener=_opener(data, send_length=False),
        progress=lambda d, t: seen.append((d, t)), chunk=1,
    )
    assert seen and all(t == of.PORTABLE_SIZE_BYTES for _, t in seen)


def test_fetch_rejects_hash_mismatch_without_extracting(tmp_path: Path) -> None:
    data = _make_zip({"ollama.exe": b"X"})
    with pytest.raises(of.OllamaFetchError, match="integrity"):
        of.fetch_portable_ollama(tmp_path, sha256="0" * 64, opener=_opener(data))
    assert not (tmp_path / "ollama.exe").exists()
    assert not list(tmp_path.glob("kimcad-ollama-*.zip"))  # temp cleaned even on failure


def test_fetch_rejects_zip_slip(tmp_path: Path) -> None:
    data = _make_zip({"../evil.txt": b"PWN", "ollama.exe": b"X"})
    sha = hashlib.sha256(data).hexdigest()
    with pytest.raises(of.OllamaFetchError, match="unsafe path"):
        of.fetch_portable_ollama(tmp_path, sha256=sha, opener=_opener(data))
    assert not (tmp_path.parent / "evil.txt").exists()


def test_fetch_errors_when_exe_missing_from_archive(tmp_path: Path) -> None:
    data = _make_zip({"lib/ollama/runner.dll": b"RUN"})  # no ollama.exe
    sha = hashlib.sha256(data).hexdigest()
    with pytest.raises(of.OllamaFetchError, match="wasn't found"):
        of.fetch_portable_ollama(tmp_path, sha256=sha, opener=_opener(data))
