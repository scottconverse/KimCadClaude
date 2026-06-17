"""Fetch the portable Ollama runtime — the network half of the managed runtime (UX-COLD-001).

When a fresh machine has no system Ollama, KimCad downloads Ollama's official **portable**
Windows build (``ollama-windows-amd64.zip``, MIT-licensed, the artifact Ollama documents "for
embedding Ollama in existing applications, or running it as a system service via ``ollama
serve``") and unzips it into KimCad's per-user data dir. No installer, no admin, no tray app,
no background auto-updater — just the binary KimCad manages itself.

Pinned + integrity-checked: the version, URL, and SHA-256 are pinned to a known release
(verified against the GitHub release asset digest), and the download is rejected on hash
mismatch BEFORE anything is extracted. Extraction is zip-slip-guarded (exact, in-tree members
only), matching the rigor of :mod:`kimcad.design_store`'s import path.

Kept import-light and effect-injected: ``opener`` (the URL fetch) is a parameter, so the
download/verify/extract logic is unit-tested with a synthetic in-memory zip and a SHA-256 pin
(no network). The full REAL ~1.4 GB fetch+extract+serve is proven separately by the recorded
manual cold-start run (``docs/audits/coder-ui-qa-test-coldstart-2026-06-17/``) and by the
Walkthrough lane, which drives live bytes through this path.
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

# Pinned Ollama portable Windows build. Verified 2026-06-17 against the GitHub release asset
# digest (`gh api repos/ollama/ollama/releases/.../assets`). Bump deliberately: update the
# version AND the SHA-256 together, never one without the other.
PORTABLE_VERSION = "v0.30.9"
PORTABLE_ASSET = "ollama-windows-amd64.zip"
PORTABLE_URL = (
    f"https://github.com/ollama/ollama/releases/download/{PORTABLE_VERSION}/{PORTABLE_ASSET}"
)
PORTABLE_SHA256 = "6d83cbe1db06ec659e7f47c0897318d2093128bcbb7c5d140c142e71d65f991f"
# The exact byte size of the pinned v0.30.9 ``ollama-windows-amd64.zip`` release asset
# (`gh api .../assets`, same 2026-06-17 verification as the SHA above). Used only to show honest
# progress when the server omits a Content-Length. The integrity check is the SHA-256, never the
# size. (≈1.4 GB)
PORTABLE_SIZE_BYTES = 1_461_613_335


class OllamaFetchError(RuntimeError):
    """A friendly, displayable failure of the portable-runtime download/verify/extract."""


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract every member into ``dest``, refusing any absolute path or ``..`` traversal
    (zip-slip). Mirrors design_store's exact-member discipline: a hostile/corrupt archive can
    never write outside the managed dir."""
    dest = dest.resolve()
    for member in zf.infolist():
        name = member.filename
        if name.endswith("/"):
            continue  # directory entry; created implicitly by file members
        target = (dest / name).resolve()
        try:
            target.relative_to(dest)
        except ValueError:
            raise OllamaFetchError(
                f"refusing to extract unsafe path from the Ollama archive: {name!r}"
            ) from None
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(member) as src, open(target, "wb") as out:
            out.write(src.read())


def fetch_portable_ollama(
    dest_dir: Path,
    *,
    url: str = PORTABLE_URL,
    sha256: str = PORTABLE_SHA256,
    opener: Callable[[str], Any] = urllib.request.urlopen,
    progress: Callable[[int, int], None] | None = None,
    chunk: int = 1 << 20,
    timeout: float = 60.0,
) -> Path:
    """Download the pinned portable Ollama zip, verify its SHA-256, and extract it into
    ``dest_dir``. Returns the path to the extracted ``ollama.exe``. Reports
    ``progress(downloaded_bytes, total_bytes)`` as it streams (``total`` is 0 when unknown).
    Raises :class:`OllamaFetchError` on a hash mismatch (before extracting) or a bad archive.

    The download streams to a temp file (a 1.4 GB blob never sits whole in RAM) that is removed
    after extraction; a partial/failed download leaves nothing behind."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    tmp_fd, tmp_name = tempfile.mkstemp(prefix="kimcad-ollama-", suffix=".zip", dir=str(dest_dir))
    tmp = Path(tmp_name)
    try:
        with os.fdopen(tmp_fd, "wb") as out, opener(url, timeout=timeout) as resp:  # type: ignore[call-arg]
            total = 0
            try:
                total = int(resp.headers.get("Content-Length") or 0)
            except (AttributeError, TypeError, ValueError):
                total = 0
            if not total:
                total = PORTABLE_SIZE_BYTES
            done = 0
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                hasher.update(buf)
                done += len(buf)
                if progress is not None:
                    progress(done, total)
        got = hasher.hexdigest()
        if got.lower() != sha256.lower():
            raise OllamaFetchError(
                "The downloaded Ollama runtime failed its integrity check "
                f"(expected {sha256[:12]}…, got {got[:12]}…). Nothing was installed; "
                "check your internet connection and try again."
            )
        try:
            with zipfile.ZipFile(tmp) as zf:
                _safe_extract(zf, dest_dir)
        except zipfile.BadZipFile as e:
            raise OllamaFetchError(
                "The downloaded Ollama runtime archive was corrupt; nothing was installed. "
                "Check your internet connection and try again."
            ) from e
    finally:
        tmp.unlink(missing_ok=True)

    exe = dest_dir / ("ollama.exe" if os.name == "nt" else "ollama")
    if not exe.exists():
        raise OllamaFetchError(
            "The Ollama runtime download extracted, but the expected executable wasn't found. "
            "Please try again, or install Ollama from ollama.com."
        )
    return exe
