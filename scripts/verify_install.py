"""Stage 11 Slice 11.5 — the scriptable core of the clean-profile install test.

Points at an INSTALL tree (the real ``{app}`` dir, or ``dist/staging``) and proves the
installed KimCad actually works, with no dev venv anywhere in the loop:

  1. the embedded interpreter + launcher report the right version;
  2. the server comes up (demo mode) on the installed payload;
  3. ``/api/health`` sees the bundled OpenSCAD + OrcaSlicer;
  4. a demo design renders and its mesh downloads;
  5. writes landed under ``%LOCALAPPDATA%\\KimCad`` — never the install dir.

Usage:  python scripts/verify_install.py "C:\\Program Files\\KimCad" [--port 8741]
Exit 0 = all green; non-zero prints the first failure. Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("install_dir", type=Path)
    ap.add_argument("--port", type=int, default=8741)
    args = ap.parse_args(argv)

    app = args.install_dir.resolve()
    py = app / "python" / "python.exe"
    launcher = app / "kimcad_launcher.py"
    for p in (py, launcher, app / "tools" / "openscad", app / "config" / "default.yaml"):
        if not p.exists():
            return fail(f"install tree incomplete: {p} missing")

    # 1. Version through the embedded interpreter.
    out = subprocess.run([str(py), str(launcher), "--version"],
                         capture_output=True, text=True, timeout=120)
    if out.returncode != 0 or not out.stdout.startswith("kimcad "):
        return fail(f"--version: rc={out.returncode} out={out.stdout!r} err={out.stderr[-300:]!r}")
    print(f"ok: {out.stdout.strip()}")

    # 2-4. The server on the installed payload (demo: no model needed).
    proc = subprocess.Popen(
        [str(py), str(launcher), "web", "--demo", "--port", str(args.port)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    base = f"http://127.0.0.1:{args.port}"
    try:
        deadline = time.monotonic() + 60
        health = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{base}/api/health", timeout=3) as r:
                    health = json.load(r)
                break
            except OSError:
                if proc.poll() is not None:
                    return fail(f"server died at startup:\n{proc.stdout.read()[-1200:]}")
                time.sleep(0.5)
        if health is None:
            return fail("server never answered /api/health within 60s")
        print(f"ok: server up, version {health['version']}")
        if not (health.get("openscad") and health.get("orcaslicer")):
            return fail(f"bundled tools not seen by the app: {health}")
        print("ok: bundled OpenSCAD + OrcaSlicer present")

        req = urllib.request.Request(
            f"{base}/api/design", data=json.dumps({"prompt": "a 40 mm desk cable clip"}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            design = json.load(r)
        mesh_url = design.get("mesh_url")
        if not mesh_url:
            return fail(f"demo design returned no mesh: {str(design)[:400]}")
        with urllib.request.urlopen(base + mesh_url, timeout=60) as r:
            mesh = r.read()
        if len(mesh) < 1000:
            return fail(f"mesh download suspiciously small ({len(mesh)} bytes)")
        print(f"ok: demo design rendered, mesh downloaded ({len(mesh)} bytes)")

        # 5. Writes landed in the per-user tree, not the install dir.
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "KimCad" / "output" / "web"
        if not local.exists():
            return fail(f"expected writes under {local} - the paths seam isn't routing")
        stray = [p for p in (app / "output",) if p.exists()]
        if stray:
            return fail(f"the install dir was written to: {stray}")
        print(f"ok: writes under {local}, install dir untouched")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("VERIFY-INSTALL: ALL GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
