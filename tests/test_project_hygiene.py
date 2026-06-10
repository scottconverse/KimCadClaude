from __future__ import annotations

from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_declared_apache_license_has_root_license_file() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["license"]["text"] == "Apache-2.0"

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "http://www.apache.org/licenses/LICENSE-2.0" in license_text


def test_audit_run_outputs_are_ignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert "/output_test/" in gitignore
    assert ".pytest_run_full.txt" in gitignore


def test_security_policy_exists() -> None:
    security_text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")

    assert "Security Policy" in security_text
    assert "report security issues" in security_text


def test_lockfile_pins_python313_numpy_wheel_floor() -> None:
    lock_lines = (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()

    assert "numpy==2.2.6" in lock_lines
    assert "scipy==1.17.1" in lock_lines
