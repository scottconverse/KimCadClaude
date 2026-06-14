"""KC-20 (#25) Slice 5b: settings, My Designs, and error recovery.

Drives the real `kimcad web --demo` SPA: a Settings toggle flips and holds, a designed part is
saved and reappears in My Designs, and a forced server failure on the design call surfaces a
graceful, recoverable error rather than a crash.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser]


def test_settings_toggles_the_experimental_generator(landing: Page, console_errors: list[str]) -> None:
    page = landing
    page.get_by_role("button", name="Settings").click()

    switch = page.get_by_role("switch", name="Enable the experimental shape generator")
    expect(switch).to_be_visible()
    before = switch.get_attribute("aria-checked")
    switch.click()
    expect(switch).not_to_have_attribute("aria-checked", before or "")

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


@pytest.mark.real_tool
def test_a_designed_part_is_saved_and_appears_in_my_designs(design) -> None:  # noqa: ANN001
    # A distinctive prompt so it's unambiguous in the list (the suite's isolated home may hold
    # other designs from earlier journeys in the same session).
    prompt = "an 18 mm spacer ring for the e2e"
    page: Page = design(prompt)

    # Designs auto-save; the topbar's Saved control opens the My Designs view, which lists it.
    page.get_by_role("button", name="Saved — open My Designs").click()
    expect(page.get_by_label("Search your designs")).to_be_visible()
    expect(page.get_by_text(prompt).first).to_be_visible()


@pytest.mark.real_tool
def test_a_slice_failure_degrades_gracefully_and_stays_recoverable(design) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")
    page.get_by_role("tab", name="Export").click()

    # Force the slice to fail server-side; the SPA must surface a readable failure note, not crash.
    page.route(
        "**/api/slice/**",
        lambda route: route.fulfill(status=500, json={"error": "Slicer crashed"}),
    )
    page.get_by_role("button", name="Slice & prepare file").click()

    # The error is shown, and recovery is intact: the Slice button is usable again (not stuck on
    # "Slicing…") and the model download fall-back remains so the user can still inspect the part.
    expect(page.locator(".kc-export-error")).to_be_visible()
    expect(page.get_by_role("button", name="Slice & prepare file")).to_be_visible()
    expect(page.get_by_role("link", name=re.compile(r"Download 3D model"))).to_be_visible()
