"""Stage 11 Slice 11.5 — the installer build pipeline's contracts (no Inno, no network:
the REAL build + install + verify ran on the build box and is recorded in the slice
commit; these pin the pieces CI can check on every run)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_build_script_version_matches_pyproject():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "build_installer", ROOT / "scripts" / "build_installer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    declared = re.search(
        r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"),
        re.MULTILINE,
    ).group(1)
    assert mod._version() == declared
    # The embeddable pin matches the dev interpreter line the suite proves (3.13.x).
    assert "/3.13." in mod.PY_EMBED_URL
    assert re.fullmatch(r"[0-9a-f]{64}", mod.PY_EMBED_SHA256)


def test_iss_requires_the_version_and_staging_as_defines():
    """The Inno script must REFUSE to compile without the build script's /D defines —
    that's how the single-source rule survives into the installer."""
    text = (ROOT / "installer" / "kimcad.iss").read_text(encoding="utf-8")
    assert "#ifndef AppVersion" in text and "#error" in text
    assert "#ifndef StagingDir" in text
    assert "{#AppVersion}" in text  # the version is consumed, never written
    # The shortcut contract: pythonw (no console) + the launcher.
    assert r"python\pythonw.exe" in text
    assert "kimcad_launcher.py" in text


def test_launcher_sets_the_seam_before_any_kimcad_import():
    """The launcher contract paths.py states: KIMCAD_INSTALL_ROOT is set AND
    site-packages is pathed BEFORE any `import kimcad` runs — verified structurally on
    the module AST (min line numbers, BG-E005), so a refactor that reorders any of the
    three fails here."""
    src = (ROOT / "installer" / "kimcad_launcher.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    env_lines: list[int] = []
    syspath_lines: list[int] = []
    kimcad_import_lines: list[int] = []
    for node in ast.walk(tree):
        seg = ast.get_source_segment(src, node) or ""
        if isinstance(node, ast.Subscript) and "KIMCAD_INSTALL_ROOT" in seg:
            env_lines.append(node.lineno)
        if isinstance(node, ast.Call) and "sys.path.insert" in seg.split("(")[0]:
            syspath_lines.append(node.lineno)
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(n.startswith("kimcad") for n in names):
                kimcad_import_lines.append(node.lineno)
    assert env_lines, "the launcher must set KIMCAD_INSTALL_ROOT"
    assert syspath_lines, "the launcher must path site-packages"
    assert kimcad_import_lines, "the launcher must import kimcad"
    assert min(env_lines) < min(kimcad_import_lines), "env must precede the kimcad import"
    assert min(syspath_lines) < min(kimcad_import_lines), "sys.path must precede the kimcad import"


def test_every_runtime_dep_is_in_the_lock():
    """BG-E007: a pyproject runtime dep missing from requirements.lock ships a BROKEN
    artifact (the staging installs the lock + kimcad --no-deps) — caught here, on every
    run, not at the next manual build."""
    import tomllib

    py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock_names = {
        line.split("==")[0].strip().lower().replace("_", "-")
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if "==" in line
    }
    missing = []
    for dep in py["project"]["dependencies"]:
        name = re.split(r"[><=!;\[ ]", dep.strip(), maxsplit=1)[0].lower().replace("_", "-")
        if name and name not in lock_names:
            missing.append(name)
    assert missing == [], f"pyproject runtime deps missing from requirements.lock: {missing}"


def test_lock_bundles_both_connector_extras_symmetrically():
    """ENG-001: the installer is batteries-included — it must ship BOTH optional connector
    extras so every supported printer works out of the box, not Bambu-only. The lock once
    carried `bambulabs-api` (the `bambu` extra) but not `pyserial` (the `serial` extra), so a
    Marlin/Ender USB user — installing the SAME official build — hit a "pip install pyserial"
    wall the app's own framing says shouldn't exist. This tripwire fails if either extra's
    top-level package drops out of requirements.lock, locking the symmetry in."""
    lock_names = {
        line.split("==")[0].strip().lower().replace("_", "-")
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()
        if "==" in line
    }
    for pkg in ("bambulabs-api", "pyserial"):
        assert pkg in lock_names, (
            f"{pkg} missing from requirements.lock — the connector-extra asymmetry is back (ENG-001)"
        )


def test_verify_install_sends_the_session_token_on_the_design_post():
    """Clean-machine finding (2026-06-15): scripts/verify_install.py POSTed /api/design with no
    X-KimCad-Session header, so the per-boot session-token guard (#31/KC-26) 403'd it and the
    verifier could never reach ALL GREEN against a real `kimcad web` server. It must read the token
    the server injects into the page shell and echo it (un-substituted placeholder / absent → none)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "verify_install", ROOT / "scripts" / "verify_install.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    h = mod._session_headers('<meta name="kimcad-session-token" content="abc123tok" />')
    assert h["X-KimCad-Session"] == "abc123tok"
    assert h["Content-Type"] == "application/json"

    # Guard off (un-substituted placeholder) or no meta at all → no token header (open-by-default).
    for shell in ('<meta name="kimcad-session-token" content="__KIMCAD_SESSION_TOKEN__" />',
                  "<html>no token meta</html>"):
        h2 = mod._session_headers(shell)
        assert "X-KimCad-Session" not in h2
        assert h2["Content-Type"] == "application/json"


def test_verify_install_covers_the_five_contracts():
    text = (ROOT / "scripts" / "verify_install.py").read_text(encoding="utf-8")
    for marker in ("--version", "/api/health", "openscad", "/api/design", "LOCALAPPDATA"):
        assert marker in text, f"verify_install lost its {marker} check"
