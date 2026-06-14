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
import sys
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


def _per_user_data_root() -> Path:
    """KimCad's per-user app-data dir (design output, the webview profile), resolved to the
    platform-idiomatic location so an installed app writes where each OS expects:

    - Windows: ``%LOCALAPPDATA%\\KimCad`` (or ``~/AppData/Local/KimCad`` if the env var is unset);
    - macOS:   ``~/Library/Application Support/KimCad``;
    - Linux/other: ``$XDG_DATA_HOME/KimCad`` (or ``~/.local/share/KimCad`` per the XDG default).

    KC-8 (#13): the previous Windows-only ``~/AppData/Local`` fallback produced a Windows-shaped
    path on macOS/Linux. The Windows branch is byte-identical to before; the mac/Linux branches are
    new (only reachable off-Windows, where installed mode / the pywebview shell can actually run)."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "KimCad"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "KimCad"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "KimCad"


def writable_root() -> Path:
    """Where the app may WRITE: the per-user app-data dir when installed (the install root is
    read-only — Program Files on Windows), the repo root in dev (output/ next to the code)."""
    if is_installed():
        return _per_user_data_root()
    return install_root()


def output_dir() -> Path:
    """The design-output tree (meshes, slices, the web server's per-design dirs)."""
    return writable_root() / "output"


def user_config_path() -> Path:
    """The user's config OVERLAY (``config/local.yaml``) — repo-local in dev (as always),
    ``%LOCALAPPDATA%\\KimCad\\config\\local.yaml`` when installed: Program Files is
    read-only, and overriding a printer or binary path must not need elevation
    (11.4-audit FINDING-003)."""
    if is_installed():
        return writable_root() / "config" / "local.yaml"
    return install_root() / "config" / "local.yaml"


def webview_profile_dir() -> Path:
    """The app window's WebView2 profile (SHELL-005) — uninstaller-visible, ours alone.
    ALWAYS per-user (browser profiles are user state, not repo artifacts — a dev-tree
    profile would pollute the checkout), under the platform-idiomatic app-data dir."""
    return _per_user_data_root() / "webview"
