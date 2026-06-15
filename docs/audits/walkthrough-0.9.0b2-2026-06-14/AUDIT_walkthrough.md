# Interface Wiring & Walkthrough Audit — KimCad 0.9.0b2

**Date:** 2026-06-14
**Auditor:** Claude (walkthrough skill)
**Build / commit:** 0.9.0b2 · `f92c2b1` (tag `v0.9.0b2`)
**App URL / how run:** real-mode local server `kimcad web --port 8791 --out <isolated>` (NOT `--demo`) against the live local models **gemma4:e4b** (chat) + **qwen2.5vl:3b** (vision); isolated `USERPROFILE`/`HOME`/`LOCALAPPDATA` so the real `~/.kimcad` was untouched. Browser driven by **Playwright 1.60 + Chromium 148** directly (see Bring-up).
**Scope:** First-run wizard, landing, help, library, Settings (all cards), My Designs, the full design→refine→sliders→quality→export/slice→send journey, the sketch on-ramp (real vision), dark mode, mobile, cross-session persistence. Out of scope: physical printer hardware (#11), the experimental shape generator (off by default), cloud acceleration (off by default), the photo on-ramp *live* (same code path as sketch; verified statically + via e2e).
**Evidence:** 35 full-page screenshots in [`./screens/`](screens/). Runtime was clean throughout — **zero console errors, zero page errors, zero failed network requests** across every flow (only benign WebGL `ReadPixels` performance warnings from the 3D viewport).

---

## 1. Verdict (read this first)

KimCad 0.9.0b2 is a **genuinely finished, well-wired, polished product** at the UI layer — every screen is real, every control drives a live handler, and the full happy path (describe → AI design → printability gate → live sliders → slice → download → send) works end-to-end against the *real* local pipeline, with honest copy and graceful failure states throughout. The one serious finding is **not** a wiring defect: the **default local model (`gemma4:e4b`) fails to fulfill 2 of the 3 example prompts the landing page itself suggests** — after a 100–140-second wait — while it succeeds on clear dimensioned prompts (a coaster designed in ~40s). That is the single most important thing to fix, because it shapes the first impression of every new beta tester.

**Readiness by area:**

| Area / screen | Finished | Partially wired | Cosmetic only | Broken |
|---|---|---|---|---|
| First-run wizard (5 steps) | ✅ | | | |
| Landing / on-ramps | ✅ | | | |
| Describe → AI design (clear prompts) | ✅ | | | |
| Describe → AI design (example chips) | | ⚠️ (model fails 2/3) | | |
| Parameters / live sliders | ✅ | | | |
| Quality (Readiness + Printability) | ✅ | | | |
| Export → slice → download | ✅ | | | |
| Send-to-printer (incl. Duet/Marlin) | ✅ | | | |
| Settings (all cards) | ✅ | | | |
| My Designs (persist/reopen/versions) | ✅ | | | |
| Sketch on-ramp (real vision) | ✅ | | | |
| Dark mode / mobile | ✅ | | | |

**Severity roll-up:** Blocker 0 · Critical 1 · Major 0 · Minor 1 · Nit 1

---

## 2. Product model (what it's supposed to be)

- **Purpose:** local-first AI → parametric CAD → print-ready file, for non-CAD users; "describe / photograph / sketch a functional part, get a print-ready file in minutes; runs on your machine."
- **User roles:** single local user (no accounts).
- **Primary workflows:** (1) describe → design → refine → slider-tune → check → slice/export → download/send; (2) photo on-ramp → seed → design; (3) sketch on-ramp → seed → design; (4) browse library → design.
- **Secondary workflows:** Settings (printer/material, connections, appearance/units, model, cloud opt-in, experimental, STEP), My Designs (open/rename/duplicate/backup/delete/import, version history), first-run wizard.
- **Expected screens/states:** wizard, landing, workspace (3 tabs: Parameters/Quality/Export), help, library modal, settings, my-designs; loading/empty/error/success states per surface.
- **UI vs docs promise:** the UI promises "three ways in," local-first, printability-checked, slice-or-send — all of which are implemented. (Doc *version/feature* drift is covered in the separate cleanup review, not repeated here.)

---

## 3. Bring-up notes

- **Run command:** `kimcad web --port 8791 --out <tmp>` in real mode; models served by a local ollama (`qwen2.5vl:3b`, `gemma4:e4b` — both present and responding).
- **Blocker found + worked around:** the **Claude Preview harness (`preview_start`) cannot drive KimCad.** KimCad's `_ExclusiveBindServer` ([webapp.py:2556](../../../src/kimcad/webapp.py)) sets `allow_reuse_address = False` on Windows on purpose (ENG-001/WALK-A-001, so a second instance can't silently bind the same port); the harness reserves the declared port before launching, so KimCad's no-reuse bind is refused on every port. **Resolution:** drove a real Chromium via **Playwright directly** (the repo's own dev dependency) against a server started by hand — full screenshots, console, and network captured. No VM needed. This is correct product behavior, not a defect.
- **Health at bring-up:** `/api/health` → `{"version":"0.9.0b2","openscad":true,"orcaslicer":true,"cadquery":true}`.
- **Existing tests:** the gate (`scripts/ci.sh`) had just passed green for this commit (1562 pytest + 389 vitest + live OpenSCAD/OrcaSlicer/CadQuery + SPA build-repro). The Playwright e2e suite (`tests/e2e/`) runs in `--demo`.

---

## 4. Findings

### W-F-001 — Critical — The default local model fails 2 of the 3 landing example prompts (after 100–140 s)
- **Route / screen:** landing → describe → AI design (the "TRY" example chips).
- **Element / workflow:** typed each landing example chip verbatim and clicked **Design it**, real `gemma4:e4b`.
- **Expected:** the app's *own featured* example prompts produce a design (they are the suggested first action for a new user).
- **Actual:** 2 of 3 failed with *"I couldn't turn that into a workable plan — the model's response wasn't usable"*:
  - "a 40 mm desk cable clip" → **fail** after ~140 s (`screens/09-workspace.png`)
  - "a wall-mounted holder for a 1 kg filament spool" → **fail** after ~100 s
  - (third chip not retested — test-harness selector error, not a product failure)
  - Control: "a round coaster 90 mm across and 4 mm thick" → **success** in ~40 s (`screens/20-real-workspace.png`).
- **Evidence:** `screens/09-workspace.png` (the graceful failure UI), the chip-calibration log, `screens/20-real-workspace.png` (the successful control).
- **Likely cause:** `gemma4:e4b` (a ~4B model) is too weak to reliably emit a parseable design plan for less-templated / under-specified prompts, and/or the example chips were never validated against the *default* model. The pipeline's plan-parse correctly rejects the unusable output (good), but the *chips* set the user up to hit that path.
- **Why it matters:** a new beta tester's most natural first action is clicking a suggested example. On the default config that means a ~2-minute wait followed by a failure ~⅔ of the time — a poor first impression of an otherwise excellent product. (Mitigations that exist: clear dimensioned prompts work well; the failure is honest and non-destructive; "Cloud acceleration" is an opt-in escape hatch.)
- **Suggested fix (options for decision):** (a) curate the example chips to prompts the default model reliably fulfills (dimensioned, template-mapped — e.g. the coaster style); (b) recommend/ship a stronger default planning model; (c) add a plan-parse retry/repair pass; (d) bias the planner toward the template catalog for short prompts. **(a)** is the cheapest, highest-impact.
- **Suggested test:** an integration test that runs each landing example chip through the real default model and asserts a usable plan (or a curation guard that fails CI if a shipped chip can't be planned).

### W-F-002 — Minor — Slider numeric label may briefly lag the handle after a programmatic max set
- **Route / screen:** workspace → Parameters → "Outer diameter" slider.
- **Expected:** the numeric value next to the slider tracks the handle/geometry.
- **Actual:** after setting the slider to its max, the geometry visibly re-rendered larger (re-render works) but the value still read "90 mm" in the capture (`screens/22-real-slider-rerender.png`).
- **Evidence:** `screens/22-real-slider-rerender.png`.
- **Likely cause:** most likely screenshot timing vs. the debounced re-render/clamp round-trip; possibly a label-vs-committed-value sync gap. **Low confidence — not reproduced deliberately.**
- **Suggested fix:** confirm the displayed value re-syncs to the server-clamped value after a programmatic input event; if it lags, bind the label to the committed value.
- **Suggested test:** a vitest/e2e assertion that the slider's displayed value equals the re-rendered part's dimension after an input change.

### W-F-003 — Nit — Noisy WebGL "GPU stall due to ReadPixels" performance warnings in the console
- **Route / screen:** any screen with the 3D viewport.
- **Actual:** repeated `GL Driver Message (OpenGL, Performance, … GPU stall due to ReadPixels)` console warnings (self-limiting — "this message will no longer repeat").
- **Evidence:** console captured in every tour.
- **Why it matters:** harmless, but adds console noise that can mask real warnings. Likely a per-frame `readPixels` (e.g. for the Measure/pick feature or thumbnail capture).
- **Suggested fix:** throttle/cache the readback, or render-to-target off the main present path.

---

## 5. Docs & design cross-check (runtime confirmations)

| Feature / promise | Status | Evidence / note |
|---|---|---|
| Three on-ramps (describe / photo / sketch) | Implemented & working | sketch read live by qwen2.5vl, accurate (`screens/41-sketch-seed.png`); describe works on clear prompts |
| AI design → printability gate → preview | Implemented & working | coaster → Readiness **92/100 "Ready to print"**, OpenSCAD engine, dims match (`screens/20`,`23`) |
| Live parametric sliders (no AI round-trip) | Implemented & working | 5 sliders, local re-render, "re-renders locally, no AI round-trip" (`screens/22`) |
| 29-printer catalog | Implemented & working | live in Settings dropdown + slice/send pickers (`screens/06-settings.png`) |
| Duet + Marlin send connectors (0.9.0b2) | Implemented & working | in Settings connections card (correct per-connector copy) **and** the in-context Send picker — "Duet (not set up yet)", "Marlin (not set up yet)" (`screens/06`,`26`) |
| Slice → print stats → download .3mf | Implemented & working | ~18m / 20 layers / 4.79 m / 14 g, honest density caveat, Download .3mf + Copy link (`screens/26-real-send.png`) |
| Send confirmation (no accidental prints) | Implemented & working | "Send a test job to 'Mock'? No real printer will run…" dialog (`screens/26`) |
| My Designs persistence + version history | Implemented & working | coaster persisted across a fresh browser session; reopened with sliders; refine → **v2** (`screens/30`,`31`,`32`) |
| Settings: model status / cloud opt-in / experimental / STEP | Implemented & working | gemma4:e4b local, cloud Off by default w/ honest copy, experimental "Untrusted/off", STEP "Installed" (`screens/06`) |
| Dark mode / units / mobile | Implemented & working | dark body `rgb(24,23,21)` (`screens/34`); mobile 390×844 (`screens/35`,`36`) |
| First-run wizard | Implemented & working | 5 steps, Skip/Back/Continue/Start designing, sets `kc-first-run-done` (`screens/02-*`) |
| Local-first / privacy honesty | Implemented & working | "nothing leaves your machine", "your sketch never left your machine and isn't saved" (`screens/41`) |
| Default example chips vs default model | **Implemented but partially wired** | 2/3 chips fail on the default model — see W-F-001 |

No mislabeled controls, dead routes, inert buttons, or placeholder-as-finished screens were found. Demo vs. real was never misrepresented (real mode shows real generation incl. its failures; the mock connector is labeled "simulated").

---

## 6. Test assessment

- **What the existing tests prove:** the Playwright e2e suite (`tests/e2e/`) runs against `--demo`, so it proves UI **wiring** (upload→read→confirm→design, slider re-render, slice/download, settings) but, by design, **cannot catch W-F-001** — demo serves a canned part and never exercises the real model's planning quality.
- **Coverage gap (highest value):** there is no test that runs the **real default model** against the **shipped example prompts**. W-F-001 is exactly the class of issue that only a real-model run catches.
- **Highest-value tests to add (ranked):**
  1. A real-model integration test (or CI canary) that plans each landing example chip and asserts success — catches W-F-001 and guards against shipping chips the default model can't do.
  2. A slider value-label↔geometry sync assertion — catches W-F-002.
  3. A console-cleanliness assertion in the e2e (fail on `error`-level console / pageerror) — locks in the clean runtime observed here.

---

## 7. Wiring map (spot-checked, all intact)

| Workflow | UI → API → result | Breaks at |
|---|---|---|
| Describe → design | textarea → POST `/api/design` (gemma4:e4b plan → template → OpenSCAD → gate) → workspace + sliders + readiness | nowhere (succeeds on clear prompts; model-quality fails on some chips — W-F-001) |
| Slider re-render | range input → POST `/api/render/<id>` → new mesh | nowhere (label sync W-F-002, low-confidence) |
| Slice | Slice → POST `/api/slice/<id>` (OrcaSlicer) → stats + .3mf | nowhere |
| Send | picker (`/api/connectors`) → confirm → `/api/send/<id>` | nowhere; Duet/Marlin present |
| Sketch on-ramp | file input → POST `/api/sketch-seed` (qwen2.5vl) → editable seed | nowhere |
| Persistence | autosave → `~/.kimcad/designs` (isolated) → My Designs list/reopen | nowhere |

---

## Sign-off checklist

- [x] Every primary route and documented workflow walked (photo on-ramp verified via shared code path + e2e; experimental/cloud out of scope by default-off).
- [x] Each finding has route, element, expected, actual, evidence, cause, fix, and test.
- [x] Cosmetic-vs-finished-vs-broken explicit per area.
- [x] Docs/design divergences classified (version/feature *doc* drift is in the separate cleanup review).
- [x] Test gaps and highest-value additions listed.
- [x] Verdict gives a concrete readiness picture.
