"""KC-20 (#25) Slice 1: the e2e harness smoke journey.

Proves the harness end-to-end — a real Chromium loads the real `kimcad web --demo` SPA, the
landing renders its primary affordances, and the page wires up with no console errors / uncaught
exceptions. The journey slices (design/refine/sliders, on-ramps, gate/slice/download, settings/
My Designs/recovery) build on this same harness.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser]


def test_landing_renders_its_primary_affordances_without_console_errors(
    page: Page, live_server: str, console_errors: list[str]
) -> None:
    page.goto(live_server)

    # The hero + the primary (text) on-ramp: the prompt box and the Design it submit.
    expect(page.get_by_role("heading", name="What do you want to make today?")).to_be_visible()
    prompt = page.get_by_label("Describe the part you want")
    expect(prompt).to_be_visible()
    expect(page.get_by_role("button", name="Design it")).to_be_visible()

    # The capability strip below the fold (the whole product arc) rendered.
    expect(page.get_by_role("region", name="What TinkerQuarry does")).to_be_visible()

    # The harness contract: the SPA booted against the real demo server with nothing thrown.
    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_landing_serves_the_session_token_meta_for_the_post_guard(
    page: Page, live_server: str
) -> None:
    # The real server injects a per-boot token into the shell (#31); the SPA reads it from this
    # meta to authorize state-changing POSTs. Proving it's present + non-placeholder here is what
    # lets the later design/refine journeys POST against the real guard instead of a bypass.
    page.goto(live_server)
    token = page.get_attribute('meta[name="kimcad-session-token"]', "content")
    assert token, "session-token meta is missing"
    assert token != "__KIMCAD_SESSION_TOKEN__", "session-token placeholder was not substituted"
