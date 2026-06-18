"""Capture the app in current (terracotta) vs proposed (gold/black) palettes.

For each key screen, captures a 'before' (current shipped palette) and 'after'
(Zen Design World gold/black) pair. The 'after' palette is injected as a CSS
override stylesheet — no app source is modified. These are MOCKUPS for review,
not built code.

Usage: .venv/Scripts/python.exe docs/redesign/capture_palette.py
"""
from __future__ import annotations
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:8701"
OUT = Path(__file__).resolve().parent / "palette"
(OUT / "before").mkdir(parents=True, exist_ok=True)
(OUT / "after").mkdir(parents=True, exist_ok=True)

SKIP_WIZARD = "window.localStorage.setItem('kc-first-run-done','1')"
DARK = "window.localStorage.setItem('kc-theme','dark')"
PROMPT = "an 80 x 60 x 40 mm project box with a lid"

# Zen Design World gold/black palette override.
GOLD_LIGHT = """
  :root, html:not([data-theme="dark"]) {
    --kc-bg: #fafaf7 !important;
    --kc-surface: #ffffff !important;
    --kc-surface-2: #f4f1ea !important;
    --kc-ink: #0c0a06 !important;
    --kc-ink-muted: #5a554c !important;
    --kc-hair: #e8e4d8 !important;
    --kc-hair-strong: #d6d0bf !important;
    --kc-accent: #d4af37 !important;
    --kc-accent-strong: #b8901f !important;
    --kc-accent-deep: #8f6e15 !important;
    --kc-accent-soft: #f3e6a5 !important;
    --kc-accent-bg: #faf2d4 !important;
  }
"""

GOLD_DARK = """
  html[data-theme="dark"] {
    --kc-bg: #0c0a06 !important;
    --kc-surface: #161310 !important;
    --kc-surface-2: #1f1c17 !important;
    --kc-ink: #f5efe5 !important;
    --kc-ink-muted: #b8b1a3 !important;
    --kc-hair: #2a2620 !important;
    --kc-hair-strong: #3a3530 !important;
    --kc-accent: #e3c24f !important;
    --kc-accent-strong: #efd06b !important;
    --kc-accent-deep: #c9a634 !important;
    --kc-accent-soft: #4a3d18 !important;
    --kc-accent-bg: #2a2210 !important;
  }
"""


def _design(page):
    page.get_by_label("Describe the part you want").fill(PROMPT)
    page.get_by_role("button", name="Design it").click()
    page.wait_for_url("**/design/**", timeout=45_000)
    expect(page.get_by_role("tab", name="Parameters")).to_be_visible(timeout=45_000)
    page.wait_for_timeout(1200)


def shot(page, sub, name):
    p = OUT / sub / name
    page.screenshot(path=str(p))
    print(f"  saved {sub}/{name}")


def capture_round(pw, subdir, palette_css=None):
    """Capture the same 5 screens; optionally inject a palette override."""
    browser = pw.chromium.launch()

    def make_page(dark=False, wizard=False, mobile=False):
        c = browser.new_context(
            viewport={"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        init = []
        if not wizard:
            init.append(SKIP_WIZARD)
        if dark:
            init.append(DARK)
        if init:
            c.add_init_script("; ".join(init))
        page = c.new_page()
        return c, page

    def maybe_inject(page):
        if palette_css:
            page.add_style_tag(content=palette_css)
            page.wait_for_timeout(150)

    # light flow
    c, page = make_page()
    page.goto(BASE, wait_until="networkidle")
    maybe_inject(page)
    page.wait_for_timeout(600)
    shot(page, subdir, "01-empty-light.png")
    _design(page)
    maybe_inject(page)
    shot(page, subdir, "02-workspace-light.png")
    page.get_by_role("tab", name="Quality").click()
    page.wait_for_timeout(700)
    shot(page, subdir, "03-quality-light.png")
    c.close()

    # library
    c, page = make_page()
    page.goto(BASE, wait_until="networkidle")
    maybe_inject(page)
    page.get_by_role("button", name="Browse the part library").click()
    page.wait_for_timeout(900)
    shot(page, subdir, "04-library-light.png")
    c.close()

    # dark
    c, page = make_page(dark=True)
    page.goto(BASE, wait_until="networkidle")
    maybe_inject(page)
    page.wait_for_timeout(600)
    _design(page)
    maybe_inject(page)
    shot(page, subdir, "05-workspace-dark.png")
    c.close()

    # wizard
    c, page = make_page(wizard=True)
    page.goto(BASE, wait_until="networkidle")
    maybe_inject(page)
    page.wait_for_timeout(900)
    shot(page, subdir, "06-wizard.png")
    c.close()

    browser.close()


def main():
    full = (GOLD_LIGHT + GOLD_DARK)
    with sync_playwright() as pw:
        print("[before] capturing current terracotta palette...")
        capture_round(pw, "before", palette_css=None)
        print("[after] capturing gold/black mockup...")
        capture_round(pw, "after", palette_css=full)
    print("done.")


if __name__ == "__main__":
    main()
