"""Stage 11 Slice 11.4 — THE path seam between the dev tree and the installed app.

Dev (a git checkout): everything lives under the repo root — config/, tools/, output/ —
exactly as it always has. Installed (the Stage-11 installer): the app lives under Program
Files (read-only!), so READS (config templates, tools, the SPA) come from the install
root while WRITES (design output, the WebView2 profile) go to ``%LOCALAPPDATA%\\KimCad``.
The per-user ``~/.kimcad`` (settings, saved designs) is already writable and unchanged.

The launcher the installer ships sets ``KIMCAD_INSTALL_ROOT`` before Python starts; its
presence IS the installed-mode switch. Nothing else may infer installedness — one switch,
set in one place, testable by setting one env var.
"""

from __future__ import annotations

import os
from pathlib import Path

_ENV = "KIMCAD_INSTALL_ROOT"


def is_installed() -> bool:
    """Whether we're running as the installed app (the launcher set the switch)."""
    return bool(os.environ.get(_ENV))


def install_root() -> Path:
    """Where the read-only app payload lives: the install dir when installed, the repo
    root in a dev checkout (this file's grandparent's parent — src/kimcad/paths.py)."""
    env = os.environ.get(_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def writable_root() -> Path:
    """Where the app may WRITE: ``%LOCALAPPDATA%\\KimCad`` when installed (Program Files
    is read-only), the repo root in dev (output/ next to the code, as always)."""
    if is_installed():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "KimCad"
    return install_root()


def output_dir() -> Path:
    """The design-output tree (meshes, slices, the web server's per-design dirs)."""
    return writable_root() / "output"


def webview_profile_dir() -> Path:
    """The app window's WebView2 profile (SHELL-005) — uninstaller-visible, ours alone.
    ALWAYS per-user (browser profiles are user state, not repo artifacts — a dev-tree
    profile would pollute the checkout)."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "KimCad" / "webview"
