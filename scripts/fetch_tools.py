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
        # VERIFY: confirm the exact release tag + asset name before relying on it.
        "win": ToolPin(
            url="https://github.com/SoftFever/OrcaSlicer/releases/latest",
            archive="zip",
            exe_name="orca-slicer.exe",
            dest_subdir="orcaslicer",
            verified=False,
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


def fetch_tool(name: str, *, force: bool) -> Path:
    plat = _platform_key()
    by_platform = PINS.get(name)
    if not by_platform:
        raise SystemExit(f"Unknown tool {name!r}. Known: {', '.join(PINS)}")
    pin = by_platform.get(plat)
    if pin is None:
        raise SystemExit(f"No pin for {name!r} on platform {plat!r}.")

    dest_exe = TOOLS_DIR / pin.dest_subdir / pin.exe_name
    if dest_exe.exists() and not force:
        print(f"{name}: already present at {dest_exe} (use --force to refresh).")
        return dest_exe

    if not pin.verified:
        raise SystemExit(
            f"{name} ({plat}) is not yet a verified pin (URL: {pin.url}).\n"
            "Confirm the release/asset against spec §7.5, set verified=True in "
            "scripts/fetch_tools.py, then re-run."
        )
    if pin.archive != "zip":
        raise SystemExit(
            f"{name} ({plat}) ships as a {pin.archive}; only zip extraction is "
            "automated today. Install it manually and point config/local.yaml at it."
        )

    print(f"{name}: fetching for {plat} ...")
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        archive_path = Path(tmp.name)
    try:
        _download(pin.url, archive_path)
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
