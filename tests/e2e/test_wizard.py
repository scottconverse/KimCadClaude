"""KC-20 (#25) Slice 5a: the first-run onboarding wizard.

A FRESH browser context (no seeded first-run flag) shows the wizard, so these journeys — unlike
the rest of the suite, which suppresses it — drive the onboarding flow itself: walk Welcome ->
Set up your AI -> Pick your printer -> Direct printing -> You're all set -> Start designing, and
the Skip-setup shortcut. No design is triggered, so no render tool is needed.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser]


def test_the_first_run_wizard_walks_through_to_the_landing(
    page: Page, live_server: str, console_errors: list[str]
) -> None:
    page.goto(live_server)  # no first-run seed -> the wizard shows

    expect(page.get_by_role("heading", name="Welcome to KimCad")).to_be_visible()
    # Advance through the steps (a default printer is pre-selected) to the final step.
    start = page.get_by_role("button", name="Start designing")
    for _ in range(6):
        if start.is_visible():
            break
        page.get_by_role("button", name="Continue").click()
    start.click()

    # The wizard is gone and the landing's primary on-ramp is ready.
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_label("Describe the part you want")).to_be_visible()
    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_skip_setup_dismisses_the_wizard_straight_to_the_landing(
    page: Page, live_server: str
) -> None:
    page.goto(live_server)

    expect(page.get_by_role("heading", name="Welcome to KimCad")).to_be_visible()
    page.get_by_role("button", name="Skip setup").click()

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_label("Describe the part you want")).to_be_visible()
