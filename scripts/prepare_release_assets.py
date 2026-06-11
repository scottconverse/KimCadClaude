"""KC-9 (#14) — release attestation: SHA256SUMS.txt + release-manifest.json.

Until the installer is code-signed, the trust story is (1) download only from the official
GitHub release and (2) verify the checksum. This script makes that systematic: point it at
the built artifact(s) and it emits, next to them,

- ``SHA256SUMS.txt``      — ``<sha256>  <filename>`` per artifact (PowerShell-verifiable);
- ``release-manifest.json`` — product, version, build date, **source commit**, per-asset
  hashes + byte sizes, ``unsigned_build: true`` while no certificate exists, an explicit
  altitude statement, and a pointer to the SmartScreen walkthrough.

Attach all three (artifact + both attestation files) to the GitHub release.

Usage (defaults to the standard installer path):

    python scripts/prepare_release_assets.py [dist/KimCad-Setup-<version>.exe ...]
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=30
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:  # noqa: BLE001 - attestation degrades, never blocks a release build
        return "unknown"


def _version() -> str:
    try:
        sys.path.insert(0, str(ROOT / "src"))
        from kimcad import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return "unknown"


def main(argv: list[str]) -> int:
    version = _version()
    artifacts = [Path(a) for a in argv] or [ROOT / "dist" / f"KimCad-Setup-{version}.exe"]
    missing = [a for a in artifacts if not a.exists()]
    if missing:
        print(f"ERROR: artifact(s) not found: {', '.join(str(m) for m in missing)}")
        print("Build the installer first (scripts/build_installer.py).")
        return 2

    out_dir = artifacts[0].parent
    assets = []
    sums_lines = []
    for a in artifacts:
        digest = _sha256(a)
        assets.append({"name": a.name, "sha256": digest, "bytes": a.stat().st_size})
        sums_lines.append(f"{digest}  {a.name}")
        print(f"  {a.name}: sha256={digest[:16]}…  ({a.stat().st_size:,} bytes)")

    (out_dir / "SHA256SUMS.txt").write_text("\n".join(sums_lines) + "\n", encoding="utf-8")

    manifest = {
        "product": "KimCad",
        "version": version,
        "build_date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "source_commit": _git_commit(),
        # Honesty fields — what this build IS and ISN'T:
        "unsigned_build": True,  # flip when a code-signing certificate lands (KC-9, #14)
        "altitude": (
            "software-complete beta; slicing proven in CI for the reference printers; "
            "no physical print certified yet (the beta's own job)"
        ),
        "smartscreen_walkthrough": "docs/install-guide.md",
        "verify": 'PowerShell: Get-FileHash .\\<asset> -Algorithm SHA256  (match SHA256SUMS.txt)',
        "assets": assets,
    }
    (out_dir / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nWrote {out_dir / 'SHA256SUMS.txt'} and {out_dir / 'release-manifest.json'}")
    print("Attach the artifact(s) + both files to the GitHub release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
