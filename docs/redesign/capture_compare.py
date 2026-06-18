"""Capture before/after pairs of the OLD and NEW landing pages for review.

Old page (pre-redesign): http://localhost:8720/_old-landing.html
New page (redesign):    http://localhost:8720/index.html

Writes paired PNGs to docs/redesign/compare/ — used by SIDE-BY-SIDE.html.
"""
from __future__ import annotations
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8720"
OUT = Path(__file__).resolve().parent / "compare"
OUT.mkdir(parents=True, exist_ok=True)


def capture(pw, url, slug, dark=False, mobile=False, hero_only=False):
    browser = pw.chromium.launch()
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844} if mobile else {"width": 1440, "height": 900},
        device_scale_factor=2,
        color_scheme="dark" if dark else "light",
    )
    page = ctx.new_page()
    if dark:
        # Both pages persist theme via localStorage key "kc-theme" or via [data-theme]; set both
        page.add_init_script("""
          try { localStorage.setItem('kc-theme', 'dark'); } catch (e) {}
          document.documentElement.setAttribute('data-theme', 'dark');
        """)
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(800)  # let fonts settle
    if hero_only:
        page.screenshot(path=str(OUT / f"{slug}.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 900})
    else:
        page.screenshot(path=str(OUT / f"{slug}.png"), full_page=True)
    print(f"  saved {slug}.png")
    browser.close()


def main():
    with sync_playwright() as pw:
        # OLD page captures
        capture(pw, f"{BASE}/_old-landing.html", "old-hero", hero_only=True)
        capture(pw, f"{BASE}/_old-landing.html", "old-full")
        capture(pw, f"{BASE}/_old-landing.html", "old-mobile", mobile=True, hero_only=True)
        # NEW page captures
        capture(pw, f"{BASE}/index.html", "new-hero", hero_only=True)
        capture(pw, f"{BASE}/index.html", "new-full")
        capture(pw, f"{BASE}/index.html", "new-dark", dark=True, hero_only=True)
        capture(pw, f"{BASE}/index.html", "new-mobile", mobile=True, hero_only=True)
    print("done.")


if __name__ == "__main__":
    main()
