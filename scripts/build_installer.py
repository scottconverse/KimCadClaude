"""Stage 11 Slice 11.5 — build the Windows installer (stdlib only, like fetch_tools.py).

Stages ``dist/staging/`` as the EXACT tree the installer lays down, then compiles
``installer/kimcad.iss`` with the pinned Inno Setup into
``dist/KimCad-Setup-<version>.exe``:

    staging/
      python/            the python.org EMBEDDABLE CPython (pinned URL + SHA-256)
      site-packages/     pip install --target of requirements.lock + kimcad itself
      config/            the shipped templates (default.yaml; local.yaml is per-user)
      library/           the OpenSCAD include library the prompts reference
      tools/             OpenSCAD + OrcaSlicer (reuses the repo's fetched copies;
                         falls back to scripts/fetch_tools.py)
      kimcad_launcher.py the entry point (sets KIMCAD_INSTALL_ROOT in-process)

The launcher contract: the Start-Menu shortcut runs
``{app}\\python\\pythonw.exe "{app}\\kimcad_launcher.py"`` — no console, no compiled
stub, no ``._pth`` surgery (the launcher owns sys.path + the env switch).

Run from the repo root, inside the dev venv:  ``python scripts/build_installer.py``
(``--stage-only`` skips the Inno compile; ``--skip-pip`` reuses an existing
site-packages staging for fast iteration).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
STAGING = DIST / "staging"

# The EXACT interpreter the test suite proved (the dev venv is 3.13.13) — pinned.
# Bump policy (11.5-audit FINDING-005): bump ONLY together with the dev venv (rebuild it,
# run the full suite green, then update URL + SHA here in the same commit) — the installer
# must never ship an interpreter line the suite hasn't proven.
PY_EMBED_URL = "https://www.python.org/ftp/python/3.13.13/python-3.13.13-embed-amd64.zip"
PY_EMBED_SHA256 = "8766a8775746235e23cf5aee5027ab1060bb981d93110577adcf3508aa0cbd55"

# 11.5-audit FINDING-001: the RELEASE strip — dirs/files in site-packages that are dev/
# build toolchain, not runtime. Includes the underscore twins and the exe-stub bin dir;
# enforced by an assertion after the strip, and the full verify_install exercises the
# remaining tree (trimesh/scipy/manifold/slicing) so an over-strip fails loudly.
RELEASE_STRIP = (
    "pytest", "_pytest", "py.test", "pluggy", "iniconfig", "coverage", "ruff",
    "pygments", "pip", "wheel", "pip_audit", "bin",
)

# The pinned Inno Setup compiler (installed once on the build box; jrsoftware.org's
# installer for 6.7.3, sha256 4d11e8050b6185e0d49bd9e8cc661a7a59f44959a621d31d11033124c4e8a7b0).
ISCC_DEFAULT = Path(r"C:\kimcad-ci-tools\innosetup6\ISCC.exe")


def _version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml must declare the version"
    return m.group(1)


def _download_verified(url: str, sha256: str, dest: Path) -> None:
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha256:
        print(f"  cached: {dest.name}")
        return
    print(f"  downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as r:
        data = r.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != sha256:
        raise RuntimeError(f"SHA-256 mismatch for {url}: expected {sha256}, got {actual}")
    dest.write_bytes(data)
    print(f"  sha256 ok ({sha256[:12]}…)")


def stage_python() -> None:
    print("python: staging the embeddable runtime …")
    cache = DIST / "cache" / "python-embed.zip"
    _download_verified(PY_EMBED_URL, PY_EMBED_SHA256, cache)
    target = STAGING / "python"
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(cache) as zf:
        zf.extractall(target)
    # The stock ._pth stays untouched (python313.zip + '.'): the launcher owns sys.path.
    assert (target / "pythonw.exe").exists()


def stage_site_packages(skip_pip: bool) -> None:
    target = STAGING / "site-packages"
    if skip_pip and target.exists():
        print("site-packages: reusing existing staging (--skip-pip)")
        return
    print("site-packages: pip install --target (requirements.lock + kimcad) …")
    if target.exists():
        shutil.rmtree(target)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target),
         "-r", str(ROOT / "requirements.lock")],
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(target),
         "--no-deps", "--upgrade", str(ROOT)],
        check=True,
    )
    # The installed app is a RELEASE: the dev/test toolchain has no business in it.
    for unwanted in RELEASE_STRIP:
        for p in list(target.glob(f"{unwanted}*")) + list(target.glob(f"{unwanted.capitalize()}*")):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            else:
                p.unlink(missing_ok=True)
    # Stray artifacts pip --target leaves behind.
    for p in list(target.glob("*.whl")) + list(target.glob("*coverage*.pth")):
        p.unlink(missing_ok=True)
    # ENFORCED, not promised (the 11.5 audit caught a cosmetic strip): nothing from the
    # strip list may remain.
    leftovers = [p.name for n in RELEASE_STRIP for p in target.glob(f"{n}*")]
    assert not leftovers, f"release strip incomplete: {leftovers}"


def stage_payload() -> None:
    print("payload: config/, library/, the launcher …")
    for name in ("config", "library"):
        src = ROOT / name
        dst = STAGING / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    # local.yaml is the USER overlay — never shipped (paths.user_config_path puts it
    # under %LOCALAPPDATA% for installed apps).
    (STAGING / "config" / "local.yaml").unlink(missing_ok=True)
    shutil.copy2(ROOT / "installer" / "kimcad_launcher.py", STAGING / "kimcad_launcher.py")
    shutil.copy2(ROOT / "LICENSE", STAGING / "LICENSE")


def stage_tools() -> None:
    print("tools: OpenSCAD + OrcaSlicer …")
    target = STAGING / "tools"
    repo_tools = ROOT / "tools"
    needed = ("openscad", "orcaslicer")
    if all((repo_tools / n).exists() for n in needed):
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        for n in needed:
            shutil.copytree(repo_tools / n, target / n)
        print("  reused the repo's fetched, checksum-pinned copies")
        return
    # Fresh build box: fetch into the repo first (the pinned fetcher), then re-run.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_tools.py")], check=True)
    stage_tools()


def smoke_staging() -> None:
    """The staged tree must IMPORT and report the right version under the EMBEDDED
    python (not the dev venv) before an installer is built from it."""
    print("smoke: the staged tree under the embedded interpreter …")
    out = subprocess.run(
        [str(STAGING / "python" / "python.exe"), str(STAGING / "kimcad_launcher.py"),
         "--version"],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    expected = f"kimcad {_version()}"
    if out.returncode != 0 or out.stdout.strip() != expected:
        raise RuntimeError(
            f"staging smoke failed: rc={out.returncode} out={out.stdout!r} err={out.stderr[-500:]!r}"
        )
    print(f"  ok: {out.stdout.strip()}")


def compile_installer(iscc: Path) -> Path:
    version = _version()
    print(f"inno: compiling KimCad-Setup-{version}.exe …")
    if not iscc.exists():
        raise RuntimeError(
            f"Inno Setup compiler not found at {iscc} - install the pinned 6.7.3 there "
            "(or pass --iscc)."
        )
    # 11.5-audit FINDING-006: an explicit numeric quad for Windows VersionInfo (the file
    # properties dialog) — PEP 440 pre-release tags don't belong in a Win32 version.
    quad_match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    quad = ".".join(quad_match.groups()) + ".0" if quad_match else "0.0.0.0"
    subprocess.run(
        [str(iscc), f"/DAppVersion={version}", f"/DAppVersionQuad={quad}",
         f"/DStagingDir={STAGING}", f"/O{DIST}", str(ROOT / "installer" / "kimcad.iss")],
        check=True,
    )
    out = DIST / f"KimCad-Setup-{version}.exe"
    assert out.exists(), f"Inno reported success but {out} is missing"
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    (DIST / f"KimCad-Setup-{version}.exe.sha256").write_text(sha + "\n", encoding="utf-8")
    print(f"  built {out.name} ({out.stat().st_size / 1e6:.1f} MB, sha256 {sha[:16]}…)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stage-only", action="store_true", help="stage dist/staging, skip Inno")
    ap.add_argument("--skip-pip", action="store_true", help="reuse an existing site-packages staging")
    ap.add_argument("--iscc", type=Path, default=ISCC_DEFAULT, help="path to ISCC.exe")
    args = ap.parse_args(argv)

    STAGING.mkdir(parents=True, exist_ok=True)
    stage_python()
    stage_site_packages(args.skip_pip)
    stage_payload()
    stage_tools()
    smoke_staging()
    if args.stage_only:
        print("staged only (no installer) - dist/staging is ready")
        return 0
    compile_installer(args.iscc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
