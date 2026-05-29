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
    python scripts/fetch_tools.py --check-upgrade # report a stable newer than the pin

Only the stdlib is used (no ``requests``) so the fetch step has no dependency of
its own. Version pins are the ``PINS`` table below; re-check them against spec
§7.5 (the VERIFY markers) when the pinned spec is available — URLs and the exact
"latest stable" move over time.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import sys
import tempfile
import urllib.error
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
    github_repo: str | None = None  # "owner/repo" — enables --check-upgrade for this pin
    asset_glob: str | None = None  # fnmatch pattern for this platform's asset in a release


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
            github_repo="OrcaSlicer/OrcaSlicer",
            asset_glob="OrcaSlicer_Windows_*_portable.zip",
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


def _resolve_pin(name: str) -> ToolPin | None:
    """The pin for ``name`` on the current platform, or None if none is defined."""
    by_platform = PINS.get(name)
    if not by_platform:
        raise SystemExit(f"Unknown tool {name!r}. Known: {', '.join(PINS)}")
    return by_platform.get(_platform_key())


def fetch_tool(name: str, *, force: bool) -> Path:
    plat = _platform_key()
    pin = _resolve_pin(name)
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
        _verify_checksum(name, pin, archive_path)
        installed = _install_zip(pin, archive_path)
    finally:
        archive_path.unlink(missing_ok=True)
    print(f"{name}: installed -> {installed}")
    return installed


def _parse_version(tag: str) -> tuple[int, int, int] | None:
    """Extract ``(major, minor, patch)`` from a tag like ``v2.4.0`` or ``2.4.0-alpha``.

    The prerelease suffix is ignored for the numeric compare; whether a release
    counts as stable is read from the API's ``prerelease`` flag, not the tag text.
    """
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        return None
    major, minor, patch = (int(g) for g in m.groups())
    return major, minor, patch


def _pinned_tag(pin: ToolPin) -> str | None:
    """The release tag a GitHub-hosted pin points at (.../releases/download/<tag>/...)."""
    marker = "/releases/download/"
    if marker not in pin.url:
        return None
    return pin.url.split(marker, 1)[1].split("/", 1)[0]


def _github_releases(repo: str) -> list[dict]:
    url = f"https://api.github.com/repos/{repo}/releases?per_page=100"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "kimcad-fetch/0.1", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req) as resp:  # noqa: S310 (pinned host)
        return json.load(resp)


def check_upgrade(name: str, pin: ToolPin) -> None:
    """Report whether a stable release at least as new as the pin exists — notify only.

    This never downloads or rewrites the pin. The point of pinning is a vetted,
    checksummed build; adopting a new stable stays a reviewed commit (new URL +
    new sha256 + one smoke slice). This just removes the "remember to look" toil
    and deliberately refuses to chase prereleases — which is how the broken 2.3.2
    "stable" got caught in the first place.
    """
    if not pin.github_repo or not pin.asset_glob:
        print(f"{name}: no upgrade check configured (not a GitHub-release pin).")
        return

    pinned_tag = _pinned_tag(pin)
    pinned_base = _parse_version(pinned_tag or "")
    if pinned_base is None:
        print(f"{name}: can't parse the pinned version from {pin.url!r}; skipping.")
        return

    try:
        releases = _github_releases(pin.github_repo)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"{name}: upgrade check failed ({exc}); the pinned build is unaffected.")
        return

    best: tuple[tuple[int, int, int], str, str] | None = None  # (version, tag, asset_url)
    for rel in releases:
        if rel.get("prerelease") or rel.get("draft"):
            continue
        base = _parse_version(rel.get("tag_name", ""))
        if base is None or base < pinned_base:
            continue
        asset = next(
            (a for a in rel.get("assets", []) if fnmatch.fnmatch(a.get("name", ""), pin.asset_glob)),
            None,
        )
        if asset is None:
            continue  # a stable with no matching platform asset is no use to us
        if best is None or base > best[0]:
            best = (base, rel["tag_name"], asset["browser_download_url"])

    pinned_str = ".".join(map(str, pinned_base))
    if best is None:
        print(
            f"{name}: pinned at {pinned_tag} - no stable release >= {pinned_str} "
            "with a matching asset yet. Staying on the pin."
        )
        return

    _, tag, asset_url = best
    print(
        f"{name}: STABLE AVAILABLE -- {tag} (currently pinned at {pinned_tag}).\n"
        f"  asset: {asset_url}\n"
        "  To adopt it: download, record its sha256 in PINS, update the URL, and run\n"
        "  one smoke slice on the P2S before committing the bump."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch KimCad's external CAD/slicer binaries.")
    parser.add_argument("--only", choices=sorted(PINS), help="Limit to just this tool.")
    parser.add_argument("--force", action="store_true", help="Re-download even if present.")
    parser.add_argument(
        "--check-upgrade",
        action="store_true",
        help="Report if a stable release newer than the pin exists; fetch nothing.",
    )
    args = parser.parse_args(argv)

    tools = [args.only] if args.only else list(PINS)
    if args.check_upgrade:
        for name in tools:
            pin = _resolve_pin(name)
            if pin is None:
                print(f"{name}: no pin for platform {_platform_key()!r}.")
                continue
            check_upgrade(name, pin)
        return 0

    for name in tools:
        fetch_tool(name, force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
