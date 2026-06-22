from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_declared_gpl_license_has_root_license_file() -> None:
    # KimCad's own code is relicensed Apache-2.0 -> GPL-2.0 per the TinkerQuarry Option-B
    # decision (the combined work absorbs Studio's GPL-2.0-only front-end, which forces
    # GPL-2.0). See STRATEGY-RECON.md and THIRD_PARTY_LICENSES.md.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["license"]["text"] == "GPL-2.0-only"

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "Version 2, June 1991" in license_text


def test_third_party_licenses_file_present() -> None:
    # The bundled/invoked engines (OpenSCAD, OrcaSlicer) and permissive libraries must be
    # documented in-tree for a GPL-2.0 redistribution.
    notice = (ROOT / "THIRD_PARTY_LICENSES.md").read_text(encoding="utf-8")
    assert "OpenSCAD" in notice
    assert "OrcaSlicer" in notice


def test_audit_run_outputs_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "/output_test/" in gitignore
    assert ".pytest_run_full.txt" in gitignore
    assert ".kimcad-web-*.log" in gitignore
    assert "/.audit-tools/" in gitignore


def test_security_policy_exists() -> None:
    security_text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "Security Policy" in security_text
    assert "report security issues" in security_text


def test_lockfile_pins_python313_numpy_wheel_floor() -> None:
    lock_lines = (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()

    assert "numpy==2.2.6" in lock_lines
    assert "scipy==1.17.1" in lock_lines
