"""KC-20 (#25) Slice 5b: settings, My Designs, and error recovery.

Drives the real `kimcad web --demo` SPA: a Settings toggle flips both ways (and is RESTORED so it
can't leak into the session-shared server state), a designed part is saved and reappears in My
Designs (keyed to a per-run unique prompt), and a client-mocked slice failure surfaces a graceful,
recoverable error rather than a crash.
"""

from __future__ import annotations

import re
import uuid

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser]


def test_settings_toggles_the_experimental_generator_both_ways(
    landing: Page, console_errors: list[str]
) -> None:
    page = landing
    page.get_by_role("button", name="Settings").click()

    switch = page.get_by_role("switch", name="Enable the experimental shape generator")
    expect(switch).to_be_visible()
    before = switch.get_attribute("aria-checked")

    # Toggle ON (or OFF), assert it flipped, then RESTORE it. The live_server is session-scoped, so
    # leaving experimental_enabled ON would persist server-side and flip allow_experimental for the
    # gate-fail journeys (which depend on it being OFF to OFFER the generator). Restoring keeps this
    # journey order-independent (ENG-2 / QA-1, audit-team 2026-06-14).
    switch.click()
    expect(switch).not_to_have_attribute("aria-checked", before or "")
    switch.click()
    expect(switch).to_have_attribute("aria-checked", before or "false")

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


@pytest.mark.real_tool
def test_a_designed_part_is_saved_and_appears_in_my_designs(design) -> None:  # noqa: ANN001
    # A per-RUN unique prompt so the assertion can only be satisfied by THIS run's save — never a
    # stale same-prompt entry from an earlier journey/partial run in the session-shared store
    # (QA-5 / ENG-9, audit-team 2026-06-14).
    prompt = f"a calibration ring {uuid.uuid4().hex[:8]}"
    page: Page = design(prompt)

    # Designs auto-save; the topbar's Saved control opens the My Designs view, which lists it.
    page.get_by_role("button", name="Saved — open My Designs").click()
    expect(page.get_by_label("Search your designs")).to_be_visible()
    expect(page.get_by_text(prompt)).to_be_visible()


@pytest.mark.real_tool
def test_a_client_mocked_slice_500_surfaces_an_error_and_stays_recoverable(design) -> None:  # noqa: ANN001
    # NOTE: this mocks the slice response CLIENT-side (page.route), so it proves the SPA's handling
    # of a 5xx — NOT the server's own graceful slice-refusal path (that soft sliced:False contract
    # is covered by the unit suite). The real_tool marker is required only for the design() render
    # above, not the mocked slice (TEST-5, audit-team 2026-06-14).
    page: Page = design("a 40 mm desk cable clip")
    page.get_by_role("tab", name="Export").click()

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
