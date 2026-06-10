"""Re-run the Stage 9 vision-on-ramp probes (docs/benchmarks/stage-9-vision-onramps.md).

DOC-006 (stage-9 gate): the benchmark's numbers must be re-derivable from the repo.
This is the committed form of the audit-scratch harness those numbers came from:

1. ``sanity`` — a labeled shape (green triangle, the word WORLD) straight through Ollama's
   ``/api/chat`` with an image attached, against any model you name. This is the probe that
   showed gemma4:e4b hallucinating ("circle / apple", or "no visible image was provided"
   with thinking on) while moondream/qwen2.5vl read it fine — i.e. it separates "the
   model's vision is broken" from "Ollama's image plumbing is broken".
2. ``sketch`` — a PIL-drawn dimensioned L-bracket sketch through KimCad's REAL
   ``POST /api/sketch-seed`` on a live real-mode server, timing the read and counting
   which written dimensions came through.

Usage (from the repo root, venv active, Ollama running)::

    python scripts/bench_vision.py sanity --model qwen2.5vl:3b
    python scripts/bench_vision.py sanity --model gemma4:e4b      # reproduce Finding 1
    kimcad web --port 8702 &                                       # a REAL-mode server
    python scripts/bench_vision.py sketch --server http://127.0.0.1:8702

Pillow is needed only to DRAW the probe images (``pip install pillow``); it is not a
KimCad runtime dependency. Fonts/antialiasing differ per box, so expect equivalent — not
byte-identical — reads; what must reproduce is which labels are read, not the phrasing.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
import urllib.request

OLLAMA = "http://127.0.0.1:11434"


def _png(draw_fn) -> bytes:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Pillow is needed to draw the probe images: pip install pillow")
    img = Image.new("RGB", (640, 480), "white")
    draw_fn(ImageDraw.Draw(img))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def sanity_image() -> bytes:
    """The Finding-1/2 probe: a green triangle labeled WORLD."""

    def draw(d):
        d.polygon([(320, 80), (140, 360), (500, 360)], fill="#1a7f37")
        d.text((280, 400), "WORLD", fill="black")

    return _png(draw)


def bracket_sketch() -> bytes:
    """The Finding-2 end-to-end probe: an L-bracket with written dimensions."""

    def draw(d):
        # The L profile.
        d.line([(100, 100), (100, 380), (520, 380), (520, 310), (170, 310), (170, 100), (100, 100)],
               fill="black", width=4)
        # Written dimensions — the thing a sketch read must take AS WRITTEN.
        d.text((300, 420), "80 mm", fill="black")
        d.text((40, 230), "60 mm", fill="black")
        d.text((530, 340), "15 mm", fill="black")
        d.text((200, 200), "5 mm thick", fill="black")
        d.text((200, 60), "L-bracket", fill="black")

    return _png(draw)


def probe_chat(model: str, image: bytes, prompt: str, think: bool) -> tuple[str, float]:
    body = json.dumps({
        "model": model,
        "stream": False,
        "think": think,
        "messages": [{
            "role": "user",
            "content": prompt,
            "images": [base64.b64encode(image).decode()],
        }],
    }).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.load(resp)
    return out.get("message", {}).get("content", ""), time.monotonic() - t0


def run_sanity(model: str) -> int:
    img = sanity_image()
    print(f"[sanity] {model}: green triangle labeled WORLD -> /api/chat (think:false)")
    text, dt = probe_chat(model, img, "Describe the shape and any text in this image.", think=False)
    print(f"  {dt:5.1f}s  {text.strip()[:300]!r}")
    low = text.lower()
    ok = "triangle" in low and "world" in low
    print(f"  verdict: {'READ (vision works)' if ok else 'MISREAD (vision broken or hallucinating)'}")
    return 0 if ok else 1


def run_sketch(server: str) -> int:
    img = bracket_sketch()
    req = urllib.request.Request(f"{server.rstrip('/')}/api/sketch-seed", data=img,
                                 headers={"Content-Type": "image/png"}, method="POST")
    print(f"[sketch] L-bracket (80/60/15 mm + 5 mm thick) -> {server}/api/sketch-seed")
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=300) as resp:
        out = json.load(resp)
    dt = time.monotonic() - t0
    seed = (out.get("seed") or "").strip()
    print(f"  {dt:5.1f}s  seed: {seed[:300]!r}")
    hits = [d for d in ("80", "60", "15", "5") if d in seed]
    print(f"  dimensions read as written: {len(hits)}/4 ({', '.join(hits) or 'none'})")
    return 0 if len(hits) >= 3 else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("sanity", help="raw /api/chat image probe against one model")
    s1.add_argument("--model", default="qwen2.5vl:3b")
    s2 = sub.add_parser("sketch", help="dimensioned sketch through a live /api/sketch-seed")
    s2.add_argument("--server", default="http://127.0.0.1:8702")
    args = p.parse_args(argv)
    return run_sanity(args.model) if args.cmd == "sanity" else run_sketch(args.server)


if __name__ == "__main__":
    raise SystemExit(main())
