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


# The documented onboarding sequence, by a unique heading substring per step (apostrophes avoided).
_WIZARD_STEPS = ("Welcome", "Set up your AI", "Pick your printer", "Direct printing", "all set")


def test_the_first_run_wizard_walks_through_to_the_landing(
    page: Page, live_server: str, console_errors: list[str]
) -> None:
    page.goto(live_server)  # no first-run seed -> the wizard shows

    # Step through asserting each heading in order, so the journey proves the actual documented
    # sequence rendered — not just "some number of Continues reached the end" — and fails with a
    # clear "which step" message if a step is added or its Continue is unexpectedly disabled
    # (QA-6 / TEST-8, audit-team 2026-06-14). A default printer is pre-selected, so Continue advances.
    for heading in _WIZARD_STEPS:
        expect(page.get_by_role("heading", name=heading)).to_be_visible()
        if heading == _WIZARD_STEPS[-1]:
            page.get_by_role("button", name="Start designing").click()
        else:
            page.get_by_role("button", name="Continue").click()

    # The wizard is gone and the landing's primary on-ramp is ready.
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_label("Describe the part you want")).to_be_visible()
    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_skip_setup_dismisses_the_wizard_straight_to_the_landing(
    page: Page, live_server: str
) -> None:
    page.goto(live_server)

    expect(page.get_by_role("heading", name="Welcome to TinkerQuarry")).to_be_visible()
    page.get_by_role("button", name="Skip setup").click()

    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.get_by_label("Describe the part you want")).to_be_visible()
