"""KC-20 (#25) Slice 2: the core design journeys — describe -> design -> refine -> sliders.

Drives the real `kimcad web --demo` SPA. Demo mode renders deterministically from the template
engine (no model): a typed prompt renders a parametric part, the Inspector tabs switch, a parameter
slider re-renders the preview locally, a quick-refine chip is recorded in the conversation, and New
design returns to a fresh draft. Each asserts the browser console stayed clean.

Note the demo-mode split observed against the real server: a *slider* is a client-side
param->geometry change, so the dimensioned preview updates live; a *refine* (chip or typed) round-
trips to the stubbed demo model, which echoes a fixed demo part into the conversation rather than
re-cutting geometry — so the refine journey asserts the conversation, not the preview dimensions.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# real_tool too: demo mode renders the part with the actual OpenSCAD binary (the snap_box family),
# so these journeys need it — they skip cleanly where it's absent, like the rest of the suite.
pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser, pytest.mark.real_tool]

_PREVIEW = re.compile(r"^3D preview")
_PARAMS = ("Width", "Depth", "Height", "Wall thickness")


def test_a_typed_prompt_renders_a_parametric_part(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")

    # The design route + the Parameters Inspector with all four sliders + the dimensioned preview.
    assert "/design/" in page.url
    expect(page.get_by_role("tab", name="Parameters")).to_be_visible()
    for param in _PARAMS:
        expect(page.get_by_label(param, exact=True)).to_be_visible()
    expect(page.get_by_label(_PREVIEW)).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_the_inspector_quality_tab_shows_the_readiness_score(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design()

    # Readiness lives on the Quality tab (Parameters is active by default), so it's hidden until
    # the tab is selected — switching to it surfaces the score band.
    readiness = page.get_by_label(re.compile(r"Readiness score"))
    expect(readiness).to_be_hidden()
    page.get_by_role("tab", name="Quality").click()
    expect(readiness).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


_DIMS = re.compile(r"\d+ by \d+ by \d+")


def test_a_parameter_slider_re_renders_the_preview_with_a_larger_width(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design()
    preview = page.get_by_label(_PREVIEW)

    # Wait for the DIMENSIONED label to land first (the initial mesh framing resolves async, after
    # the Parameters tab) — so the change we assert is attributable to the slider, not to the
    # initial render arriving late (TEST-2, audit-team 2026-06-14).
    expect(preview).to_have_attribute("aria-label", _DIMS, timeout=30_000)
    before_label = preview.get_attribute("aria-label")  # "3D preview — 80 by 60 by 40 millimetres"
    before_w = int(re.search(r"(\d+) by", before_label).group(1))

    # Nudge the Width slider (the exact "Width" aria-label is the range input; the click-to-edit
    # label is "Width: N mm…"). Arrow keys move it by its step, then a real /api/render re-renders.
    width = page.get_by_label("Width", exact=True)
    width.focus()
    for _ in range(6):
        width.press("ArrowRight")

    # The preview re-renders — wait for the label to change (a real render round-trip; generous
    # timeout for the throttling box, QA-4), then assert the WIDTH specifically increased, tying the
    # pass to the slider rather than to render timing.
    expect(preview).not_to_have_attribute("aria-label", before_label, timeout=30_000)
    after_w = int(re.search(r"(\d+) by", preview.get_attribute("aria-label")).group(1))
    assert after_w > before_w, f"slider should increase the preview width: {before_w} -> {after_w}"
    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_a_quick_refine_chip_is_recorded_in_the_conversation(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design()
    log = page.get_by_role("log")

    page.get_by_role("button", name="Make it bigger").click()

    # The refinement is echoed into the conversation and the demo server answers it.
    expect(log).to_contain_text("Make it bigger")
    expect(log).to_contain_text(re.compile(r"Demo part for: Make it bigger"))
    # And it pushed a new version — the version rail now shows v2, proving the refine→version-push
    # wiring landed, not just the conversation echo (TEST-6, audit-team 2026-06-14).
    expect(page.get_by_text("v2", exact=True)).to_be_visible()
    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_new_design_returns_to_a_fresh_landing(design) -> None:  # noqa: ANN001
    page: Page = design()

    page.get_by_role("button", name="New design").click()

    # Back to the empty landing — the primary on-ramp (the prompt box) is ready again.
    expect(page.get_by_label("Describe the part you want")).to_be_visible()
