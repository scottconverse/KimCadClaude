"""KC-20 (#25) stage-close additions (TEST-4, audit-team 2026-06-14): the high-blast-radius flows
the first journey pass left uncovered — version-rail navigation, the send-to-printer surface, and
the mobile sticky CTA. Driven against the real `kimcad web --demo` SPA.

Known remaining gaps (lower blast radius; confirmed wired by the stage walkthrough, not yet
regression-covered here): click-to-measure, the light/dark theme toggle, the global keyboard
shortcuts overlay, and the cloud (OpenRouter) opt-in.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser, pytest.mark.real_tool]


def test_the_version_rail_navigates_between_refine_versions(design) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")

    # A refine creates v2; the rail then offers Compare + Undo across the two versions.
    page.get_by_role("button", name="Make it bigger").click()
    expect(page.get_by_role("button", name="Version 2: Make it bigger")).to_be_visible()
    expect(page.get_by_role("button", name=re.compile(r"Compare v1 and v2"))).to_be_visible()

    # Stepping back actually moves: after Undo, a Redo affordance appears (the nav changed state,
    # not just rendered buttons).
    page.get_by_role("button", name="Undo to previous version").click()
    expect(page.get_by_role("button", name=re.compile(r"Redo", re.I))).to_be_visible()


def test_the_send_to_printer_surface_appears_after_slicing(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")
    page.get_by_role("tab", name="Export").click()
    page.get_by_role("button", name="Slice & prepare file").click()

    # Once a real print file exists, the direct-print surface is offered with a safe simulated send.
    # We assert the surface is wired; we do NOT trigger a real send.
    expect(page.get_by_text("Send to printer")).to_be_visible(timeout=60_000)
    expect(page.get_by_role("button", name="Send test job")).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_a_narrow_viewport_shows_the_mobile_sticky_cta(design) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")

    # On a phone-width viewport the workspace surfaces a sticky "Check & download" CTA (the
    # three-column layout collapses) — a whole rendering mode with no other e2e proof.
    page.set_viewport_size({"width": 390, "height": 844})
    expect(page.locator(".kc-mobile-cta")).to_be_visible()
