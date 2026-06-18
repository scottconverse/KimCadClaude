"""Capture real KimCad product screenshots for the landing-page/docs redesign.

Drives the live `kimcad web --demo` server (deterministic; renders the real template via OpenSCAD,
no Ollama needed) with Playwright and writes crisp 2x PNGs to docs/redesign/shots/.

Usage:  .venv/Scripts/python.exe docs/redesign/capture_shots.py [base_url]
Default base_url = http://localhost:8701 (the kimcad-web-demo preview server).

This is build tooling, not product code — safe to re-run to regenerate shots.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8701"
OUT = Path(__file__).resolve().parent / "shots"
OUT.mkdir(parents=True, exist_ok=True)

SKIP_WIZARD = "window.localStorage.setItem('kc-first-run-done','1')"
DARK = "window.localStorage.setItem('kc-theme','dark')"
PROMPT = "an 80 x 60 x 40 mm project box with a lid"


def _design(page):
    page.get_by_label("Describe the part you want").fill(PROMPT)
    page.get_by_role("button", name="Design it").click()
    page.wait_for_url("**/design/**", timeout=45_000)
    expect(page.get_by_role("tab", name="Parameters")).to_be_visible(timeout=45_000)
    page.wait_for_timeout(1200)  # let the viewport mesh settle


def shot(page, name):
    p = OUT / name
    page.screenshot(path=str(p))
    print("  saved", p.name)


def main():
    captured = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def ctx(dark=False, mobile=False, wizard=False):
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
            return c

        # ---- desktop light ----
        try:
            c = ctx()
            page = c.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(800)
            shot(page, "01-empty-light.png"); captured.append("01")
            _design(page)
            shot(page, "02-workspace-light.png"); captured.append("02")
            page.get_by_role("tab", name="Quality").click()
            page.wait_for_timeout(700)
            shot(page, "03-quality-light.png"); captured.append("03")
            page.get_by_role("tab", name="Export").click()
            page.wait_for_timeout(700)
            shot(page, "04-export-light.png"); captured.append("04")
            c.close()
        except Exception as e:
            print("  [light flow] ERROR:", e)

        # ---- library browser ----
        try:
            c = ctx()
            page = c.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.get_by_role("button", name="Browse the part library").click()
            page.wait_for_timeout(900)
            shot(page, "05-library-light.png"); captured.append("05")
            c.close()
        except Exception as e:
            print("  [library] ERROR:", e)

        # ---- desktop dark ----
        try:
            c = ctx(dark=True)
            page = c.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(800)
            shot(page, "06-empty-dark.png"); captured.append("06")
            _design(page)
            shot(page, "07-workspace-dark.png"); captured.append("07")
            page.get_by_role("tab", name="Quality").click()
            page.wait_for_timeout(700)
            shot(page, "08-quality-dark.png"); captured.append("08")
            c.close()
        except Exception as e:
            print("  [dark flow] ERROR:", e)

        # ---- first-run wizard ----
        try:
            c = ctx(wizard=True)
            page = c.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(900)
            shot(page, "09-wizard.png"); captured.append("09")
            c.close()
        except Exception as e:
            print("  [wizard] ERROR:", e)

        # ---- mobile ----
        try:
            c = ctx(mobile=True)
            page = c.new_page()
            page.goto(BASE, wait_until="networkidle")
            page.wait_for_timeout(800)
            shot(page, "10-mobile-empty.png"); captured.append("10")
            _design(page)
            shot(page, "11-mobile-workspace.png"); captured.append("11")
            c.close()
        except Exception as e:
            print("  [mobile] ERROR:", e)

        browser.close()
    print("CAPTURED:", ", ".join(captured) if captured else "NONE")


if __name__ == "__main__":
    main()
