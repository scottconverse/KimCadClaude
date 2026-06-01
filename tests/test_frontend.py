"""TEST-003: static frontend-contract checks for the web UI.

Stage 4 replaced the old single-file vanilla-JS page with a React + TypeScript SPA built
by Vite (build-time only) into ``src/kimcad/web`` and served by the Python server. The
committed build output is what ships — there is no Node toolchain at runtime — so these
checks read the built artifacts on disk and assert, by simple presence, that:

  1. the built ``index.html`` shell mounts the SPA (``id="root"``) and references its
     bundled module + stylesheet under ``/assets/``; and
  2. every asset the shell references actually exists in ``web/assets/`` (so a stale or
     missing build can't be served as a blank page).

The server-side half of the contract — that ``/`` serves this shell and ``/assets/<file>``
serves the bundles (with traversal rejected) — is covered in tests/test_webapp.py.

The frontend↔backend FIELD contract (the SPA consuming ``gate_status`` / ``clarification`` /
the printer-status vocabulary, etc.) is asserted against the TypeScript source as those
flows are wired in the later Stage 4 slices (design flow, then printer/slice/send); the
shell built in the first slice does not consume those fields yet, so there is nothing to
assert about them here.

Kept deliberately robust: presence checks on the build output, not DOM parsing or JS
execution, so cosmetic edits don't make it brittle, but a missing/stale build trips it.
"""

from __future__ import annotations

import re

from kimcad.webapp import WEB_DIR

_HTML = (WEB_DIR / "index.html").read_text(encoding="utf-8")


def test_built_spa_shell_exists_and_mounts_root():
    """The served page is the built SPA shell: it has the React mount point and pulls in
    a bundled ES module (no inline <script> — the app is compiled, not hand-written)."""
    assert (WEB_DIR / "index.html").exists()
    assert 'id="root"' in _HTML, "SPA shell must contain the #root mount element"
    assert re.search(r'<script[^>]+type="module"[^>]+src="/assets/[^"]+\.js"', _HTML), (
        "SPA shell must load a bundled ES module from /assets/"
    )


def test_built_spa_references_only_existing_assets():
    """Every /assets/<file> the shell references must exist on disk, so the committed build
    is internally consistent (a renamed/cleared bundle can't be served as a blank page)."""
    refs = set(re.findall(r'(?:src|href)="/assets/([^"]+)"', _HTML))
    assert refs, "expected the shell to reference at least one bundled asset"
    missing = sorted(name for name in refs if not (WEB_DIR / "assets" / name).is_file())
    assert not missing, f"index.html references assets that aren't built: {missing}"


def test_built_spa_loads_a_stylesheet():
    """The Workshop theme ships as a bundled stylesheet (not inline), so the shell must
    link one from /assets/."""
    assert re.search(r'<link[^>]+rel="stylesheet"[^>]+href="/assets/[^"]+\.css"', _HTML), (
        "SPA shell must link a bundled stylesheet from /assets/"
    )
