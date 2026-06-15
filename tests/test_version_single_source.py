"""Stage 11 Slice 11.3 — the version is single-sourced from pyproject's metadata.

The tripwire: no source file other than ``pyproject.toml`` (and this test) may carry the
declared version — or the pre-Stage-11 literal ``0.1.0`` — as a string. Every surface
reads ``kimcad.__version__``."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _declared() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version = "([^"]+)"', text, re.MULTILINE)
    assert m, "pyproject.toml must declare the version"
    return m.group(1)


def test_package_metadata_matches_pyproject():
    import kimcad

    assert kimcad.__version__ == _declared(), (
        "installed metadata is stale — re-run `pip install -e . --no-deps`"
    )


def test_no_source_file_carries_a_version_literal():
    declared = _declared()
    offenders: list[str] = []
    for tree, pattern in ((ROOT / "src" / "kimcad", "*.py"), (ROOT / "frontend" / "src", "*.ts*")):
        for p in tree.rglob(pattern):
            text = p.read_text(encoding="utf-8", errors="replace")
            if f'"{declared}"' in text or "'" + declared + "'" in text or '"0.1.0"' in text:
                offenders.append(str(p.relative_to(ROOT)))
    assert offenders == [], f"version literals outside pyproject: {offenders}"


def test_readme_beta_badge_matches_the_declared_version():
    """TEST-002 (audit-team 2026-06-14): the README's canonical current-version marker — the
    shields.io beta badge — must track pyproject, so a stale badge (the 0.9.0b1-badge-on-a-
    0.9.0b2-build drift that misdirected testers) fails the gate. Prose/history references are
    deliberately NOT scanned: the Stage-by-stage history block legitimately names prior releases."""
    declared = _declared()
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"img\.shields\.io/badge/beta-([0-9][^-\s)]*)-", text)
    assert m, "README must carry the shields.io beta-<version> badge"
    assert m.group(1) == declared, (
        f"README beta badge is {m.group(1)!r} but pyproject declares {declared!r} — "
        "bump the badge (audit DOC-001 version-drift guard)"
    )


def test_frontend_package_version_is_in_lockstep():
    """11.3-audit FINDING-001/002: package.json AND its lock carry the npm-semver twin of
    pyproject's PEP 440 version (0.9.0b1 <-> 0.9.0-beta.1) — enforced, not promised."""
    import json
    import re

    declared = _declared()
    # 11.4-audit FINDING-005: every PEP 440 pre-release form maps (b/rc/a -> npm
    # beta/rc/alpha); an unmapped form still fails CLOSED on the package.json compare.
    m = re.fullmatch(r"(\d+\.\d+\.\d+)(a|b|rc)(\d+)", declared)
    kinds = {"a": "alpha", "b": "beta", "rc": "rc"}
    expected = f"{m.group(1)}-{kinds[m.group(2)]}.{m.group(3)}" if m else declared
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == expected
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["version"] == expected


def test_installer_scripts_take_the_version_as_a_parameter():
    """11.3-audit FINDING-002 (forward guard): any Inno script must receive the version
    via /D define (the build script reads pyproject), never carry a literal."""
    declared = _declared()
    iss_dir = ROOT / "installer"
    if not iss_dir.exists():
        return  # Slice 11.5 creates it; the guard arms itself then
    for p in iss_dir.rglob("*.iss"):
        text = p.read_text(encoding="utf-8", errors="replace")
        assert declared not in text, f"{p.name} hardcodes the version - use /DAppVersion"


def test_cli_version_flag_prints_the_single_source():
    out = subprocess.run(
        [sys.executable, "-m", "kimcad.cli", "--version"],
        capture_output=True, text=True, timeout=60,
    )
    assert out.returncode == 0
    assert out.stdout.strip() == f"kimcad {_declared()}"


def test_health_endpoint_reports_the_single_source(tmp_path):
    import http.client
    import json
    import threading
    from http.server import ThreadingHTTPServer

    import kimcad
    from kimcad.webapp import make_handler

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(object(), tmp_path / "web"))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_address[1], timeout=10)
        conn.request("GET", "/api/health")
        body = json.loads(conn.getresponse().read())
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert body["version"] == kimcad.__version__
