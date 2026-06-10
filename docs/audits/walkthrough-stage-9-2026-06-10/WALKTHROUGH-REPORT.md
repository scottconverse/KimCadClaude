# Stage 9 Walkthrough — image & sketch on-ramp (commit e8339d9)
**Date:** 2026-06-10 · **Mode:** audit · **Setup:** a REAL-mode server (:8714, home isolated to a scratch profile) driven through the actual browser preview for the vision journeys; a demo server (:8715) for the registry journey; terminal for `kimcad models`. All servers stopped, scratch home removed.

## Verdict
Stage 9's promises hold in the running product against the **real vision model in the real browser** — not API shortcuts: a dimensioned L-bracket sketch was drawn, injected as a genuine `File` into the sketch on-ramp's input, and the confirm card came back with **all three labeled dimensions plus the 5 mm thickness, correctly structured, in 9 seconds**. The seed then fed the real design flow, the cancel path fired, and the Stage-A draft preservation re-seeded the sketch-derived prompt on the landing — three stages' work verified in one user journey. The photo path — broken against the real model since Stage 8.5, fixed by this stage — read a synthetic shaded mug as *"a simple cylindrical mug with a handle… roughly 10 cm tall"* with the estimates note shown. **No findings.**

## What was exercised

| # | Journey | Result |
|---|---|---|
| 1 | **Sketch journey, real model, real browser** — both affordances on the landing → file injected into the sketch input → "Reading your sketch…" → confirm card | Seed: *"An L-bracket, 5 mm thick… Length along the long edge (80 mm), Width at the bottom (60 mm), Height… (15 mm)"* — 3/3 dims + thickness, 9 s; privacy line + read-as-written note both rendered |
| 2 | Seed → design flow → cancel | Design started from the seed; Cancel returned to the landing **with the sketch-derived draft preserved** (UX-001 interplay) |
| 3 | **Photo regression, real model** — shaded mug JPEG through the photo on-ramp | *"cylindrical mug with a handle… roughly 10 cm tall"*; estimates note shown (the photo path works against the real model for the first time) |
| 4 | `kimcad models` | "Vision model (photo/sketch on-ramps): qwen2.5vl:3b (installed)" line present; both models listed |
| 5 | **DesignRegistry stale-guard, live** (demo + real OrcaSlicer) — design → slice (200) → slider re-render → old G-code fetch | **404 after re-render** (the bump dropped it), fresh slice then succeeded — the refactor preserved the safety invariant byte-for-byte |
| 6 | Docs cross-check | getting-started's two-pull instruction matches the live `ollama list`/`kimcad models` reality; the troubleshooting "vision model isn't pulled" entry quotes the exact typed error string the code emits |

## Limitations (honest)
- The vision-model-MISSING typed path was verified by unit test + string match, not by deleting the model live.
- `preview_screenshot` timed out once mid-session (tool-side); evidence is the captured DOM text/values above rather than pixels for journey 1.

## Findings
**None.** One observation for the gate roles: the sketch on-ramp has no SPA-side test that drives a real `File` through the input change → confirm-card flow (the unit tests mock at the upload-function seam) — worth a note, not a defect, since the journey is proven live here.

## Wiring classification
All Stage 9 features: **implemented and working** against the real model. No cosmetic surfaces, no dead controls, zero console errors across both servers.
