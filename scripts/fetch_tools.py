"""Fetch the pinned OpenSCAD + OrcaSlicer portable builds into ``tools/``.

KimCad invokes OpenSCAD and OrcaSlicer as external subprocesses (never linked),
so the binaries live outside the package in a gitignored ``tools/`` tree at the
paths ``config/default.yaml`` expects:

    tools/openscad/openscad.exe       (or ``openscad`` / ``OpenSCAD`` per platform)
    tools/orcaslicer/orca-slicer.exe

Usage:

    python scripts/fetch_tools.py                 # fetch everything for this OS
    python scripts/fetch_tools.py --only openscad # just OpenSCAD
    python scripts/fetch_tools.py --force         # re-download even if present

Only the stdlib is used (no ``requests``) so the fetch step has no dependency of
its own. Version pins are the ``PINS`` table below; re-check them against spec
§7.5 (the VERIFY markers) when the pinned spec is available — URLs and the exact
"latest stable" move over time.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"


@dataclass(frozen=True)
class ToolPin:
    """One downloadable build of one tool for one platform."""

    url: str
    archive: str  # "zip" — the only format we extract today
    exe_name: str  # the executable to locate inside the archive
    dest_subdir: str  # under tools/ — must match config/default.yaml binary paths
    verified: bool  # True only for URLs confirmed reachable during development
    sha256: str | None = None  # pinned digest of the archive; None = print-and-record


# VERIFY §7.5: pins below. Windows OpenSCAD is the only entry exercised live so
# far; the rest are best-known and marked verified=False until confirmed.
PINS: dict[str, dict[str, ToolPin]] = {
    "openscad": {
        "win": ToolPin(
            url="https://files.openscad.org/OpenSCAD-2021.01-x86-64.zip",
            archive="zip",
            exe_name="openscad.exe",
            dest_subdir="openscad",
            verified=True,
            sha256="fb0caabf5bbc89f8f2f80c10b79ae64d697aaff6efd58b2756f5d6270edb7ba7",
        ),
        "mac": ToolPin(
            url="https://files.openscad.org/OpenSCAD-2021.01.dmg",
            archive="dmg",
            exe_name="OpenSCAD",
            dest_subdir="openscad",
            verified=False,
        ),
        "linux": ToolPin(
            url="https://files.openscad.org/OpenSCAD-2021.01-x86_64.AppImage",
            archive="appimage",
            exe_name="openscad",
            dest_subdir="openscad",
            verified=False,
        ),
    },
    "orcaslicer": {
        # Pinned to v2.4.0-alpha (2026-05-25). NOT the 2.3.2 "stable" release:
        # 2.3.2 has an upstream Windows CLI slicing crash (OrcaSlicer issue #12906
        # and duplicates) that segfaults in DynamicPrintConfig config-apply on
        # every slice on a GPU-less box — reproduced here on a plain cube and on
        # every BBL printer profile. 2.4.0-alpha fixes it (it degrades gracefully
        # when no OpenGL context is available, skipping only the thumbnail) and
        # still ships the Bambu Lab P2S profiles. It is the only build that both
        # slices on this platform and carries the P2S reference profile, so we pin
        # it until a 2.4.x stable with the same fix is released.
        "win": ToolPin(
            url=(
                "https://github.com/OrcaSlicer/OrcaSlicer/releases/download/"
                "v2.4.0-alpha/OrcaSlicer_Windows_V2.4.0-alpha_portable.zip"
            ),
            archive="zip",
            exe_name="orca-slicer.exe",
            dest_subdir="orcaslicer",
            verified=True,
            sha256="35d2e20a82ab9cbad8d3721802441bc07296974bede2d24a7fd0c52a0c4b72e0",
        ),
    },
}


def _platform_key() -> str:
    if sys.platform.startswith("win"):
        return "win"
    if sys.platform == "darwin":
        return "mac"
    return "linux"


def _download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "kimcad-fetch/0.1"})
    with urllib.request.urlopen(req) as resp, dest.open("wb") as out:  # noqa: S310 (pinned host)
        shutil.copyfileobj(resp, out)
    print(f"  saved {dest.stat().st_size / 1_048_576:.1f} MB")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_checksum(name: str, pin: ToolPin, archive_path: Path) -> None:
    """Verify the download against the pinned digest, or print it to be recorded.

    A pin with ``sha256=None`` is "trust on first fetch": we print the computed
    digest so it can be pasted back into PINS, turning later fetches into a
    tamper check. Once pinned, a mismatch aborts before anything is installed.
    """
    digest = _sha256(archive_path)
    if pin.sha256 is None:
        print(f"  sha256 {digest}  <- record this in PINS[{name!r}] to pin it")
        return
    if digest.lower() != pin.sha256.lower():
        raise SystemExit(
            f"{name}: checksum mismatch.\n  expected {pin.sha256}\n  got      {digest}\n"
            "The download is corrupt or the pinned release was re-published. Do not install."
        )
    print(f"  sha256 ok ({digest[:12]}...)")


def _find_exe_root(extract_root: Path, exe_name: str) -> Path:
    """Return the directory that directly contains ``exe_name``.

    Portable archives nest everything under a single versioned top folder; the
    binary needs its sibling DLLs/resources, so we return the whole containing
    directory rather than just the file.
    """
    matches = [p for p in extract_root.rglob(exe_name) if p.is_file()]
    if not matches:
        raise FileNotFoundError(
            f"{exe_name} not found in the downloaded archive — the pin URL or "
            f"exe_name in PINS is wrong (looked under {extract_root})."
        )
    # Shallowest match wins (the real binary, not a bundled helper copy).
    return min(matches, key=lambda p: len(p.relative_to(extract_root).parts)).parent


def _install_zip(pin: ToolPin, archive_path: Path) -> Path:
    dest_dir = TOOLS_DIR / pin.dest_subdir
    with tempfile.TemporaryDirectory() as tmp:
        extract_root = Path(tmp)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(extract_root)
        payload_root = _find_exe_root(extract_root, pin.exe_name)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(payload_root, dest_dir)
    return dest_dir / pin.exe_name


# KC-8 (#13): OpenSCAD/OrcaSlicer are auto-fetched only on Windows today (the verified, pinned
# zip builds). On macOS/Linux from source there is no verified pin / the asset is a dmg/AppImage we
# don't extract yet — so point the user at the official download + the config override instead of a
# bare SystemExit. The browser UI runs without these; only rendering and slicing need them.
_OFFICIAL_DOWNLOADS = {
    "openscad": "https://openscad.org/downloads.html",
    "orcaslicer": "https://github.com/OrcaSlicer/OrcaSlicer/releases",
}


def _manual_install_hint(name: str, plat: str, pin: ToolPin | None) -> str:
    src = _OFFICIAL_DOWNLOADS.get(name, "the project's official downloads page")
    tried = f" (auto-fetch source: {pin.url})" if pin is not None else ""
    return (
        f"{name} can't be auto-fetched on {plat!r} yet{tried}.\n"
        f"Install it from {src}, then set binaries.{name} in config/local.yaml to its path "
        f"(or put the executable on your PATH).\n"
        f"KimCad's browser UI (`kimcad web`) runs without it — only rendering and slicing need it."
    )


def fetch_tool(name: str, *, force: bool) -> Path:
    plat = _platform_key()
    by_platform = PINS.get(name)
    if not by_platform:
        raise SystemExit(f"Unknown tool {name!r}. Known: {', '.join(PINS)}")
    pin = by_platform.get(plat)
    if pin is None:
        raise SystemExit(_manual_install_hint(name, plat, None))

    dest_exe = TOOLS_DIR / pin.dest_subdir / pin.exe_name
    if dest_exe.exists() and not force:
        print(f"{name}: already present at {dest_exe} (use --force to refresh).")
        return dest_exe

    # Not auto-fetchable on this platform: no verified pin, or an asset format we don't extract
    # (mac dmg / Linux AppImage). Either way, give the actionable manual-install path.
    if not pin.verified or pin.archive != "zip":
        raise SystemExit(_manual_install_hint(name, plat, pin))

    print(f"{name}: fetching for {plat} ...")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        archive_path = Path(tmp.name)
    try:
        _download(pin.url, archive_path)
        _verify_checksum(name, pin, archive_path)
        installed = _install_zip(pin, archive_path)
    finally:
        archive_path.unlink(missing_ok=True)
    print(f"{name}: installed -> {installed}")
    return installed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch KimCad's external CAD/slicer binaries.")
    parser.add_argument("--only", choices=sorted(PINS), help="Fetch just this tool.")
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    args = parser.parse_args(argv)

    tools = [args.only] if args.only else list(PINS)
    for name in tools:
        fetch_tool(name, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
