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
    """The launcher contract paths.py states: KIMCAD_INSTALL_ROOT is set (and
    site-packages pathed) BEFORE any `import kimcad` runs — verified structurally on the
    module AST, so a refactor that moves the import above the env write fails here."""
    src = (ROOT / "installer" / "kimcad_launcher.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    env_set_line = None
    first_kimcad_import_line = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            seg = ast.get_source_segment(src, node) or ""
            if "KIMCAD_INSTALL_ROOT" in seg and env_set_line is None:
                env_set_line = node.lineno
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            if any(n.startswith("kimcad") for n in names):
                if first_kimcad_import_line is None or node.lineno < first_kimcad_import_line:
                    first_kimcad_import_line = node.lineno
    assert env_set_line is not None, "the launcher must set KIMCAD_INSTALL_ROOT"
    assert first_kimcad_import_line is not None, "the launcher must import kimcad"
    assert env_set_line < first_kimcad_import_line, (
        "KIMCAD_INSTALL_ROOT must be set BEFORE the first kimcad import"
    )


def test_verify_install_covers_the_five_contracts():
    text = (ROOT / "scripts" / "verify_install.py").read_text(encoding="utf-8")
    for marker in ("--version", "/api/health", "openscad", "/api/design", "LOCALAPPDATA"):
        assert marker in text, f"verify_install lost its {marker} check"
