"""Capture in-app branding mockups (wizard with Kim face, Landing with Kim face).

Drives the live demo at :8701 with Playwright; injects Kim's portrait into the
right DOM hooks for the wizard rail + Welcome step and the empty-state Landing
hero. Combined with the Zen gold/black CSS override.

NO app source is modified — this is a live mockup for visual review.
"""
from __future__ import annotations
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:8701"
HERE = Path(__file__).resolve().parent
OUT = HERE / "inapp"
OUT.mkdir(parents=True, exist_ok=True)

# We need the avatar inline because it's not served by the demo app — read the
# 1254px master, base64 it, and use a data: URI so the injected DOM doesn't
# depend on demo-server routes.
AVATAR_B64 = base64.b64encode((HERE / "assets" / "kim-avatar.png").read_bytes()).decode("ascii")
AVATAR_URI = f"data:image/png;base64,{AVATAR_B64}"

GOLD_CSS = """
:root, html:not([data-theme="dark"]) {
  --kc-bg:#fafaf7!important; --kc-surface:#ffffff!important; --kc-surface-2:#f4f1ea!important;
  --kc-ink:#0c0a06!important; --kc-ink-muted:#5a554c!important;
  --kc-hair:#e8e4d8!important; --kc-hair-strong:#d6d0bf!important;
  --kc-accent:#d4af37!important; --kc-accent-strong:#b8901f!important; --kc-accent-deep:#8f6e15!important;
  --kc-accent-soft:#f3e6a5!important; --kc-accent-bg:#faf2d4!important;
}
html[data-theme="dark"] {
  --kc-bg:#0c0a06!important; --kc-surface:#161310!important; --kc-surface-2:#1f1c17!important;
  --kc-ink:#f5efe5!important; --kc-ink-muted:#b8b1a3!important;
  --kc-hair:#2a2620!important; --kc-hair-strong:#3a3530!important;
  --kc-accent:#e3c24f!important; --kc-accent-strong:#efd06b!important; --kc-accent-deep:#c9a634!important;
  --kc-accent-soft:#4a3d18!important; --kc-accent-bg:#2a2210!important;
}
/* Injection styles for the mocked-in Kim portraits */
.mockup-kim-rail { width: 56px; height: 56px; border-radius: 50%;
  box-shadow: 0 0 0 2px var(--kc-accent), 0 2px 8px rgba(0,0,0,.12);
  display: block; margin: 0 0 12px; }
.mockup-kim-welcome { width: 120px; height: 120px; border-radius: 50%;
  box-shadow: 0 0 0 3px var(--kc-accent), 0 8px 24px rgba(0,0,0,.16);
  display: block; margin: 0 auto 24px; }
.mockup-kim-landing { width: 96px; height: 96px; border-radius: 50%;
  box-shadow: 0 0 0 2.5px var(--kc-accent), 0 6px 18px rgba(0,0,0,.14);
  display: block; margin: 0 auto 18px; }
"""

SKIP_WIZARD = "window.localStorage.setItem('kc-first-run-done','1')"
INJECT_WIZARD_KIM = f"""
  // wizard rail: prepend Kim above the wordmark
  const rail = document.querySelector('.kc-wiz-brand');
  if (rail && !rail.querySelector('.mockup-kim-rail')) {{
    const img = document.createElement('img');
    img.className = 'mockup-kim-rail';
    img.src = '{AVATAR_URI}';
    img.alt = 'Kim';
    rail.parentElement.insertBefore(img, rail);
  }}
  // welcome step: large portrait above H1
  const h1 = document.querySelector('#kimcad-first-run-heading, .kc-wiz-h1');
  if (h1 && !h1.previousElementSibling?.classList?.contains('mockup-kim-welcome')) {{
    const img = document.createElement('img');
    img.className = 'mockup-kim-welcome';
    img.src = '{AVATAR_URI}';
    img.alt = 'Kim';
    h1.parentElement.insertBefore(img, h1);
  }}
"""
INJECT_LANDING_KIM = f"""
  const h = document.querySelector('.kc-hero-title');
  if (h && !h.previousElementSibling?.classList?.contains('mockup-kim-landing')) {{
    const img = document.createElement('img');
    img.className = 'mockup-kim-landing';
    img.src = '{AVATAR_URI}';
    img.alt = 'Kim';
    h.parentElement.insertBefore(img, h);
  }}
"""


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        def make_ctx(wizard=False):
            c = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=2,
            )
            if not wizard:
                c.add_init_script(SKIP_WIZARD)
            return c

        # ===== WIZARD =====
        # Before: current wizard (gold palette only, no Kim face)
        c = make_ctx(wizard=True)
        p = c.new_page()
        p.goto(BASE, wait_until="networkidle")
        p.add_style_tag(content=GOLD_CSS)
        p.wait_for_timeout(900)
        p.screenshot(path=str(OUT / "wizard-before.png"))
        print("  saved wizard-before.png")
        c.close()

        # After: wizard with Kim injected
        c = make_ctx(wizard=True)
        p = c.new_page()
        p.goto(BASE, wait_until="networkidle")
        p.add_style_tag(content=GOLD_CSS)
        p.wait_for_timeout(900)
        p.evaluate(INJECT_WIZARD_KIM)
        p.wait_for_timeout(400)
        p.screenshot(path=str(OUT / "wizard-after.png"))
        print("  saved wizard-after.png")
        c.close()

        # ===== LANDING (empty state) =====
        # Before: current empty state (gold palette, no Kim)
        c = make_ctx(wizard=False)
        p = c.new_page()
        p.goto(BASE, wait_until="networkidle")
        p.add_style_tag(content=GOLD_CSS)
        p.wait_for_timeout(700)
        p.screenshot(path=str(OUT / "landing-before.png"))
        print("  saved landing-before.png")
        c.close()

        # After: empty state with Kim injected near hero
        c = make_ctx(wizard=False)
        p = c.new_page()
        p.goto(BASE, wait_until="networkidle")
        p.add_style_tag(content=GOLD_CSS)
        p.wait_for_timeout(700)
        p.evaluate(INJECT_LANDING_KIM)
        p.wait_for_timeout(400)
        p.screenshot(path=str(OUT / "landing-after.png"))
        print("  saved landing-after.png")
        c.close()

        browser.close()
    print("done.")


if __name__ == "__main__":
    main()
