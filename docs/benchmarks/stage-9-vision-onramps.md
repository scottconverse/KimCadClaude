# Stage 9 — Vision on-ramps: on-target measurements and the photo→3D verdict

**Date:** 2026-06-10 · **Box:** the target hardware (AMD 780M iGPU, ~32 GB RAM, CPU inference) · **Ollama:** 0.30.6 · **Method:** synthetic dimensioned sketches (PIL-drawn, Arial labels) POSTed through KimCad's real `/api/sketch-seed` on a live real-mode server, plus raw `/api/chat` isolation probes. Every number below is a real timed run on this machine; the harness is committed as `scripts/bench_vision.py` (see `How to re-run` at the end).

## Finding 1 — gemma4:e4b's vision is BROKEN on this stack (Critical)

The pinned chat model claims the `vision` capability (`ollama show`), but images never
reach it:

| Probe | Result |
|---|---|
| `/api/chat`, `think:false`, red circle labeled "HELLO" | "a **circle** and the word **apple**" (6.5 s) |
| Same request, green triangle labeled "WORLD" | **identical** "circle / apple" output (6.3 s) |
| `/api/chat`, thinking enabled, either image | *"I cannot determine… because **no visible image was provided**"* |
| `/api/generate`, image attached | empty response |
| JPEG instead of PNG | same hallucination |

Identical deterministic output for grossly different images + the model's own "no image
provided" admission = the image tokens never reach gemma4:e4b. **Product implication:**
the Stage 8.5 photo on-ramp never worked against the real pinned model on this stack —
every working impression came from demo mode. (The plumbing is NOT the bug: see Finding 2.)

## Finding 2 — the fix: a dedicated local vision model (qwen2.5vl:3b)

Split test: **moondream** (1.7 GB) through the *same* request shape read "WORLD" off the
triangle in 8.9 s — Ollama's image plumbing works; gemma4:e4b's vision is what's broken.
moondream, however, returns empty for instruction-style sketch prompts — too small for
the job. **qwen2.5vl:3b** (3.2 GB, OCR-strong):

| Test | Result | Time |
|---|---|---|
| Sanity (green triangle, "WORLD") | shape + word both read | 28.6 s (cold) |
| Simple plate sketch (100 × 50 mm labels) | both dims + "rectangular plate" | 22.7 s |
| L-bracket sketch (80 / 60 / 15 mm + "5 mm thick") | **3/3 dims + thickness + shape** | 23.9 s |
| **End-to-end through KimCad** `/api/sketch-seed` (L-bracket) | **5/5**: *"The L-bracket is 80 mm long, 60 mm high, and 15 mm deep with a wall thickness of 5 mm. It fits within the Bambu Lab P2S build volume."* | 27.7 s |

Shipped accordingly: `vision_model: qwen2.5vl:3b` on the local backend (config-
overridable), `_describe_image` targets it, a missing pull surfaces as a typed
"ollama pull qwen2.5vl:3b" message (never "your image was unreadable"), and
`kimcad models` reports the vision model's install state. ~20–30 s per read on this CPU
is within the on-ramp's existing "this can take a moment" framing and its Cancel button.

## Finding 3 — the photo→3D reconstruction verdict: NOT VIABLE on this hardware (descoped honestly)

ROADMAP Stage 9 allowed for a "smallest viable image-to-3D" experiment (TripoSG-class →
reference mesh → measured bbox), to be **descoped honestly if it can't run acceptably on
the 780M**. Verdict: **descoped.**

- TripoSG-class models are ~1.5 B-parameter diffusion/transformer pipelines built for CUDA
  GPUs. This box has no CUDA device; ROCm-on-Windows for the 780M iGPU is not practically
  supported by torch, and CPU inference for this class runs **minutes-per-mesh** with a
  multi-GB weights download plus a ~2.5 GB torch dependency tree — against a product whose
  whole pipeline targets sub-minute interactivity on this exact box.
- A cloud reconstruction path would auto-send the user's photo off-machine, contradicting
  the shipped, repeatedly-stated promise ("your photo never leaves your machine"). Not
  acceptable as a default; not worth shipping as a buried opt-in for a rough seed the
  local vision path already provides.
- The ROADMAP's own exit criterion — *"photo→plan working OR honestly marked not-viable on
  this hardware"* — is met on the first branch: photo→plan ships via the local-vision seed
  (now actually working, per Findings 1–2), and the reconstruction experiment is marked
  not-viable here.

## Disk/footprint note
qwen2.5vl:3b adds ~3.2 GB beside gemma4:e4b's 9.6 GB. moondream (1.7 GB) was a diagnostic
pull only and can be removed (`ollama rm moondream`).

## How to re-run

The probes are committed (`scripts/bench_vision.py`; needs `pip install pillow` to draw the
images — not a KimCad runtime dependency). With Ollama running:

```
python scripts/bench_vision.py sanity --model gemma4:e4b     # reproduces Finding 1 (misread)
python scripts/bench_vision.py sanity --model qwen2.5vl:3b   # reproduces Finding 2 (read)
kimcad web --port 8702          # a REAL-mode server in another terminal
python scripts/bench_vision.py sketch --server http://127.0.0.1:8702   # end-to-end, timed
```

Fonts and antialiasing differ per box, so expect equivalent reads, not byte-identical
phrasing; what must reproduce is which labels are read (sanity: triangle + WORLD; sketch:
>=3 of the 4 written dimensions) and the order-of-magnitude timing.
