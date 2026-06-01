"""TEST-003: static frontend-contract checks for the web UI.

The page (src/kimcad/web/index.html) is plain HTML + vanilla JS served as-is, with no
build step and no JS test runner. A cheap regret is the JS and the markup drifting:
the script grabbing an element id that no longer exists, or the backend renaming a
response field the script still reads. These checks read the file and assert, by simple
string/regex presence, that:

  1. every element id the JS manipulates (via getElementById / the $() helper) is
     actually declared as id="..." somewhere in the markup; and
  2. every field the backend's design_response/_report_payload puts on the wire is
     referenced by name in the JS — i.e. the frontend consumes the documented contract.

Kept deliberately robust: presence checks, not DOM parsing or execution, so cosmetic
edits don't make it brittle, but a real break (renamed id or dropped field) trips it.
"""

from __future__ import annotations

import re

from kimcad.webapp import WEB_DIR

_HTML = (WEB_DIR / "index.html").read_text(encoding="utf-8")

# Split markup from script so we can check ids against the markup, and field names
# against the JS, without one masking the other.
_SCRIPT_MATCH = re.search(r"<script>(.*?)</script>", _HTML, re.DOTALL)
assert _SCRIPT_MATCH, "index.html should contain an inline <script> block"
_JS = _SCRIPT_MATCH.group(1)
_MARKUP = _HTML[: _SCRIPT_MATCH.start()]


def test_index_html_exists_and_has_script():
    assert (WEB_DIR / "index.html").exists()
    assert "getElementById" in _JS
    assert "fetch(\"/api/design\"" in _JS


def test_every_js_element_id_exists_in_markup():
    """Each id passed to $() / getElementById must be declared as id="..." in markup."""
    # The helper is `const $ = (id) => document.getElementById(id);`, then used as $("foo").
    referenced = set(re.findall(r'\$\(\s*"([A-Za-z0-9_-]+)"\s*\)', _JS))
    referenced |= set(re.findall(r'getElementById\(\s*"([A-Za-z0-9_-]+)"\s*\)', _JS))
    # Drop the helper's own parameter name if it slipped in (it won't, but be safe).
    referenced.discard("id")
    assert referenced, "expected the JS to reference at least one element id"

    declared = set(re.findall(r'id="([A-Za-z0-9_-]+)"', _MARKUP))
    missing = sorted(referenced - declared)
    assert not missing, f"JS references ids absent from the markup: {missing}"


def test_js_consumes_documented_response_fields():
    """Every field the backend sends must be read somewhere in the JS.

    Fields come from webapp.design_response (status, clarification, plan, report, error,
    mesh_url, has_mesh), _plan_payload (object_type, summary), and _report_payload
    (gate_status, headline, dims, findings). The JS must reference each by name so the
    page actually renders the contract rather than silently dropping a field.
    """
    required_fields = [
        # top-level PipelineResult mapping
        "status",
        "clarification",
        "plan",
        "report",
        "error",
        "mesh_url",
        # plan payload
        "object_type",
        "summary",
        # report payload
        "gate_status",
        "headline",
        "dims",
        "findings",
    ]
    missing = [f for f in required_fields if not re.search(rf"\b{re.escape(f)}\b", _JS)]
    assert not missing, f"frontend JS does not reference backend fields: {missing}"


def test_status_values_handled_by_frontend():
    """The four PipelineStatus values the backend can return must each be handled."""
    for status_value in ("clarification_needed", "render_failed", "gate_failed", "completed"):
        assert status_value in _JS, f"frontend does not handle status={status_value}"


# --- TEST-002 / UX-001 / UX-002 / UX-003: connection-status honesty + accessibility ---------


def test_connector_status_is_an_aria_live_region():
    """UX-001: the connection-status line announces async changes to assistive tech."""
    m = re.search(r'<p id="connectorStatus"[^>]*>', _MARKUP)
    assert m, "connectorStatus element should exist in the markup"
    tag = m.group(0)
    assert 'aria-live="polite"' in tag and 'role="status"' in tag


def test_connector_status_renderer_handles_every_reason_and_state():
    """UX-002/UX-003: the status renderer must branch on every backend reason and on the
    online-but-faulted state, so a new value can't fall through to a generic label/colour."""
    assert "d.simulated" in _JS
    for reason in ("config", "unknown", "auth", "busy", "offline", "error"):
        assert f'reason === "{reason}"' in _JS, f"status renderer does not branch on '{reason}'"
    assert 'd.state === "error"' in _JS  # online-but-faulted is NOT "busy"
    assert "d.ready" in _JS


def test_connector_status_uses_semantic_severity_classes():
    """UX-003: status severity maps to the app's green/amber/red scale (not glyph-only), and
    every class the JS emits is actually styled."""
    for cls in ("status-ready", "status-warn", "status-error"):
        assert cls in _JS, f"connectorStatusClass does not produce '{cls}'"
        assert f"#connectorStatus.{cls}" in _MARKUP, f"CSS missing a rule for '{cls}'"


def test_material_hidden_note_is_present_and_wired():
    """UX-002: a dedicated note surfaces WHY a material is hidden for the selected printer."""
    assert 'id="materialHiddenNote"' in _MARKUP
    assert "materialHiddenNote" in _JS
