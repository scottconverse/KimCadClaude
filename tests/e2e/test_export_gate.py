"""KC-20 (#25) Slice 4: the print path — gate pass (slice + download) and gate fail.

Drives the real `kimcad web --demo` SPA's Export tab: a gate-passing part slices to a downloadable
print file and always offers the model download; a part that fails the printability gate (the
demo:gatefail scenario, via the experimental generator) is refused slicing but still downloadable
to inspect. Demo renders real geometry (OpenSCAD) and slices the small box quickly.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# Needs the real OpenSCAD (render) + OrcaSlicer (slice) binaries, like the live tool contract.
pytestmark = [pytest.mark.browser_serial, pytest.mark.needs_browser, pytest.mark.real_tool]


def test_a_gate_passing_part_slices_to_a_downloadable_print_file(design, console_errors: list[str]) -> None:  # noqa: ANN001
    page: Page = design("a 40 mm desk cable clip")
    page.get_by_role("tab", name="Export").click()

    # The model download is always offered; slicing produces the print file.
    expect(page.get_by_role("link", name=re.compile(r"Download 3D model"))).to_be_visible()
    page.get_by_role("button", name="Slice & prepare file").click()
    expect(page.get_by_role("link", name=re.compile(r"Download print file"))).to_be_visible(
        timeout=60_000
    )
    expect(page.get_by_text("Print file ready")).to_be_visible()

    assert console_errors == [], f"unexpected browser console errors: {console_errors}"


def test_an_out_of_template_part_offers_the_experimental_generator(design_prompt) -> None:  # noqa: ANN001
    # demo:gatefail has no template match, so the pipeline offers the sandboxed experimental
    # generator in the conversation rather than designing straight away.
    page: Page = design_prompt("demo:gatefail")
    expect(page.get_by_role("button", name="Try the experimental generator")).to_be_visible()


def test_a_gate_failing_part_is_refused_slicing_but_still_downloadable(design_prompt) -> None:  # noqa: ANN001
    page: Page = design_prompt("demo:gatefail")
    page.get_by_role("button", name="Try the experimental generator").click()
    page.wait_for_url("**/design/**", timeout=30_000)

    # The experimental part was generated but fails the printability gate — the conversation says so.
    expect(page.get_by_role("log")).to_contain_text(
        re.compile(r"didn.t pass the printability check"), timeout=30_000
    )

    # Export refuses to slice it (no Slice button) but still offers the model download to inspect.
    page.get_by_role("tab", name="Export").click()
    # The Export panel's own note (distinct from the conversation message) explains the refusal.
    expect(page.get_by_text(re.compile(r"can.t be sliced"))).to_be_visible()
    expect(page.get_by_role("button", name="Slice & prepare file")).to_have_count(0)
    expect(page.get_by_role("link", name=re.compile(r"Download 3D model"))).to_be_visible()
