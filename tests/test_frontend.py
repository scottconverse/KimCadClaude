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


# --- Stage 4 Slice 2: the Workshop design system is actually in the built output ----------

_ASSETS_DIR = WEB_DIR / "assets"


def _built_css() -> str:
    css_files = list(_ASSETS_DIR.glob("*.css"))
    assert css_files, "no built CSS bundle found in web/assets — did the SPA build run?"
    return "\n".join(p.read_text(encoding="utf-8") for p in css_files)


def test_built_css_carries_workshop_tokens():
    """The Workshop theme's signature tokens survive the build: the terracotta accent, the
    dark viewport colour, and the three named font families."""
    css = _built_css()
    assert "#c8623a" in css, "built CSS missing the Workshop accent (terracotta)"
    assert "#14171c" in css, "built CSS missing the dark viewport colour"
    for family in ("Bricolage Grotesque", "Hanken Grotesk", "JetBrains Mono"):
        assert family in css, f"built CSS missing the {family} font family"


def test_workshop_fonts_are_bundled_for_offline_use():
    """Each Workshop family ships as a self-hosted latin woff2 in the build (no CDN), so the
    UI renders correctly fully offline on the target box."""
    for stem in ("bricolage-grotesque", "hanken-grotesk", "jetbrains-mono"):
        matches = list(_ASSETS_DIR.glob(f"{stem}-latin*.woff2"))
        assert matches, f"missing bundled latin woff2 for {stem} (offline fonts incomplete)"


_FRONTEND_SRC = WEB_DIR.parents[2] / "frontend" / "src"
_TS_FILES = sorted(_FRONTEND_SRC.rglob("*.ts*"))


def _strip_ts_comments(src: str) -> str:
    """Remove `/* */` and `//` comments so a field/status NAMED ONLY IN A COMMENT can't satisfy
    the contract. (Good enough for our own source — no `//` appears inside its string literals;
    API paths use single slashes.)"""
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.DOTALL)
    src = re.sub(r"//[^\n]*", " ", src)
    return src


# "Consumer" source = the components/logic that USE the wire fields, COMMENTS STRIPPED, with the
# api.ts type declaration + *.test.ts excluded (declaring/naming a field is not consuming it).
# The field checks below require a real property ACCESS (`.<field>`) or a quoted literal — so a
# className like `kc-dims`, a JSDoc mention, or a test reference can NOT satisfy the contract.
# (Hardened after the Stage-4 audit-team mutation-proved the prior bare-substring grep was a
# spell-checker: deleting the whole printability panel left it green except `headline`.)
_TS_CONSUMERS = "\n".join(
    _strip_ts_comments(p.read_text(encoding="utf-8"))
    for p in _TS_FILES
    if p.name != "api.ts" and ".test." not in p.name
)


def test_frontend_source_consumes_documented_response_fields():
    """The SPA's TypeScript *consumer* source references every field the backend's
    design_response / _plan_payload / _report_payload puts on the wire, so the UI actually
    renders the documented contract rather than silently dropping a field. (Replaces the old
    inline-vanilla-JS check; the field rendering moved into the React/TS source in Slice 4.)"""
    required_fields = [
        # top-level design_response mapping
        "status",
        "clarification",
        "plan",
        "report",
        "error",
        "mesh_url",
        "has_mesh",
        # plan payload
        "object_type",
        "summary",
        "target_bbox_mm",
        # report payload
        "gate_status",
        "headline",
        "dims",
        "findings",
    ]
    # Require a real property ACCESS (`.<field>`), not a bare substring, so deleting a field's
    # RENDERING — not just its name — trips the test.
    missing = [f for f in required_fields if not re.search(rf"\.{re.escape(f)}\b", _TS_CONSUMERS)]
    assert not missing, (
        f"frontend consumer source does not ACCESS backend fields "
        f"(a className/comment doesn't count): {missing}"
    )


def test_frontend_source_handles_every_pipeline_status():
    """Each PipelineStatus value must appear as a QUOTED LITERAL (a real branch), not merely
    named in a comment or a test, in the consumer source."""
    for status_value in ("clarification_needed", "render_failed", "gate_failed", "completed"):
        assert re.search(rf"""['"]{re.escape(status_value)}['"]""", _TS_CONSUMERS), (
            f"frontend does not branch on status={status_value}"
        )


def test_frontend_source_consumes_connector_status_fields():
    """The connection-status UI (Slice 5) ACCESSES the typed readiness snapshot the server sends
    (ready / online / state / reason / simulated) as properties — a comment naming them doesn't
    count — so the honest readiness badge can't silently drop a field."""
    for field in ("ready", "online", "state", "reason", "simulated"):
        assert re.search(rf"\.{re.escape(field)}\b", _TS_CONSUMERS), (
            f"connector-status UI does not access '{field}'"
        )


def test_viewport_chunk_is_code_split_from_the_entry():
    """Stage 4 Slice 3: three.js (the 3D viewport) is lazy-loaded, so it lands in a separate
    chunk (Workspace.js) rather than bloating the initial entry bundle. The committed build
    must show that split — the workspace chunk present and clearly larger than the entry, since
    three.js dwarfs the app shell."""
    entry = _ASSETS_DIR / "kimcad.js"
    chunk = _ASSETS_DIR / "Workspace.js"
    assert entry.is_file(), "entry bundle kimcad.js is missing"
    assert chunk.is_file(), "code-split Workspace chunk missing — is the viewport still lazy-loaded?"
    assert chunk.stat().st_size > entry.stat().st_size, (
        "the Workspace chunk should be larger than the entry (three.js lives in the chunk)"
    )
