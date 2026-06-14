"""KC-20 (#25) Slice 3: the photo + sketch on-ramps.

Drives the real `kimcad web --demo` SPA's secondary on-ramps end to end: upload an image, the
local-vision read returns an editable seed (demo mode returns a canned seed deterministically — the
real vision model is CPU-bound and non-deterministic), the seed is editable, and "Use this as a
starting point" feeds the normal design flow. Proves the upload -> read -> confirm -> design wiring,
not the vision model's accuracy (that's the model's job, covered elsewhere).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# real_tool too: the on-ramp seed feeds the same design flow, which renders via the real OpenSCAD
# binary — so these skip cleanly where it's absent, like the rest of the design journeys.
pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser, pytest.mark.real_tool]


def test_photo_onramp_reads_a_seed_then_starts_a_design(
    landing: Page, sample_image: str, console_errors: list[str]
) -> None:
    # Set the file directly on the photo on-ramp's hidden input (Playwright doesn't need the
    # picker click). Demo's canned photo seed describes a rough box ("a photo has no scale").
    landing.locator(".kc-onramp-photo input[type=file]").set_input_files(sample_image)

    seed = landing.get_by_label("Edit the description read from your photo")
    expect(seed).to_be_visible()
    expect(seed).to_have_value(re.compile("rectangular box"))

    landing.get_by_role("button", name="Use this as a starting point").click()
    landing.wait_for_url("**/design/**", timeout=30_000)
    expect(landing.get_by_role("tab", name="Parameters")).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_sketch_onramp_reads_a_dimensioned_seed_then_starts_a_design(
    landing: Page, sample_image: str, console_errors: list[str]
) -> None:
    landing.locator(".kc-onramp-sketch input[type=file]").set_input_files(sample_image)

    # A sketch CARRIES dimensions, so demo's canned sketch seed reads as labelled measurements.
    seed = landing.get_by_label("Edit the description read from your sketch")
    expect(seed).to_be_visible()
    expect(seed).to_have_value(re.compile("rectangular bracket"))

    landing.get_by_role("button", name="Use this as a starting point").click()
    landing.wait_for_url("**/design/**", timeout=30_000)
    expect(landing.get_by_role("tab", name="Parameters")).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_the_photo_seed_is_editable_before_it_drives_the_design(
    landing: Page, sample_image: str
) -> None:
    landing.locator(".kc-onramp-photo input[type=file]").set_input_files(sample_image)

    seed = landing.get_by_label("Edit the description read from your photo")
    expect(seed).to_be_visible()
    # The whole point of the confirm card: the read is a STARTING point the user can correct.
    seed.fill("a 25 mm hex standoff")
    landing.get_by_role("button", name="Use this as a starting point").click()

    landing.wait_for_url("**/design/**", timeout=30_000)
    # The EDITED text — not the original canned seed — drove the design (it echoes in the log).
    expect(landing.get_by_role("log")).to_contain_text("hex standoff")
