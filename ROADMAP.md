# KimCad — Full Plan to Finished Product (reworked for the real target)

Every stage is a **complete, shippable deliverable** — it ends with the product working,
tested, and committed, not a half-built slice. Each lists full scope, exit criteria,
dependencies, and an honest size. Where something genuinely can't be proven yet, it says so.

## The target (this is the whole game)
- **Hardware: a 32 GB-RAM machine with an AMD 780M integrated GPU — no discrete GPU.**
  This is *both* the development target and the deployment target. If it doesn't run well
  here, it doesn't ship. There is no GPU box coming; "wait for the GPU" is off the table.
- **Model: `gemma4:e4b`** — a small (~4B-effective) on-device model that fits and runs fast
  on this class of machine. `gemma3:12b` was the wrong call: too big, slow, and it crashed
  the server repeatedly. The competitor is getting real results with the small model; we
  match the constraint instead of fighting it. **Switched in `config/default.yaml` already.**
  The upside is huge: the benchmark/dev loop goes from ~2 h and unstable to minutes and
  stable, so iteration stops being the bottleneck.
- **Printers live at Kim's house, not here. Kim is the beta tester.** So *all* real-hardware
  validation — every real print, every live printer connection — happens **only in the final
  beta phase (Stage 10)**. Everything before that is built and tested against mocked/emulated
  printers. **Kim's printers: several Elegoo machines + Bambu Lab P2S and A1.** So the
  connector/profile build order in Stages 1–3 is **Bambu (P2S + A1) and Elegoo first**; other
  brands follow as API-only coverage.

## Confirmed deviations (do not re-add)
P2S not P1S; code-signing dropped (unsigned beta); recruited usability study replaced by
in-app telemetry + public beta feedback.

## Current baseline (honest)
Phase-1 pipeline built + unit-tested (119 tests). Web UI is a first slice only. The done-gate
has **not** officially passed — and now it needs to pass **on `gemma4:e4b`**, which is the
real test, not the gemma3:12b runs I'd been doing. Slicing proven on one part, not wired in.
No installer, no printer connectivity, no image input, no real print.

---

## Stage 0 — Refit to the target model and close Phase 1 *(immediate)*
**Goal:** the pipeline works on `gemma4:e4b` on the target box, and clears the done-gate there.
- Validate the planner + codegen on `gemma4:e4b`; a smaller model needs tighter prompts, so
  expect to simplify the design-plan and codegen prompts and lean harder on the library
  modules (picking a module + filling parameters is exactly what a small model does well).
- Re-run the 10-prompt benchmark **on e4b** to a real number; reach **≥ 8/10**. Fast now, so
  this is hours-with-tuning, not days.
- Update `CHANGELOG.md`; self-audit; commit + push.
**Exit:** `kimcad bench --min-success-rate 0.8` passes on `gemma4:e4b`, on the target hardware.
**Needs:** the target box only. **Size:** ~2–4 days incl. prompt tuning.

## Stage 1 — Gated export: a real, validated print file
**Goal:** any validated part → confirmed → a verified G-code/3MF file. *(No printer needed.)*
- Full printer/material/profile model; resolve profile **names → on-disk profile files** (the
  known gap); explicit material/profile confirmation (CLI + web); OrcaSlicer wired into the
  normal flow.
- **G-code proof per run:** parse the slice output and verify it's real — actual G1 moves, a
  sane layer count, a print-time + filament estimate; empty/garbage fails loudly.
- **Manifold3D:** robust watertight check + *surfaced* (never silent) pre-slice repair; the
  gate still hard-fails defects, repair only runs on knowing export and reports what changed.
- Download/export is the delivery path. Tests; proven on several parts.
**Exit:** confirm a part → verified non-empty G-code with an estimate, multiple part types.
**Needs:** target box. **Size:** ~1 week.

## Stage 2 — Send-to-printer connector + MCP (software-complete, hardware-deferred)
**Goal:** the full send path exists and is tested — live printing waits for Kim's beta.
- "Send to printer" abstraction; **MCP as the first connector**; explicit per-send
  confirmation; printer status/capability query → auto-fill the blank profile field;
  download/export stays the fallback.
- Tested end-to-end against a **mocked/emulated printer** (OctoPrint or a Moonraker emulator
  runs fine on the dev box). **No real print here — that's Stage 10 at Kim's.**
**Exit:** confirmed part → "sent" through the connector to an emulated printer, or downloaded;
status flows through. **Needs:** target box + an emulator. **Size:** ~1 week.

## Stage 3 — Printer coverage + ready/not-ready UI (software-complete)
**Goal:** multi-brand support and live status, all built and mock-tested.
- MCP coverage for OctoPrint, Klipper/Moonraker, Bambu, Prusa Connect, Creality; per-printer
  capability/status checks; a "ready / not ready" UI; honest labeling (nothing is
  hardware-verified until Kim's beta).
- Tested against each printer-API contract via mocks/emulators.
**Exit:** any supported brand selectable with live (emulated) status; the ready/not-ready UI
works. **Needs:** target box + emulators. **Size:** ~1.5–2 weeks.

## Stage 4 — Web UI to a genuinely usable product
**Goal:** the browser app is a coherent tool end to end.
- Async job + progress (the model call runs in the background; the page never freezes); live
  parameter sliders (drag → re-render); smarter one-question clarify flow; the full print-loop
  UI surfaced (printer select, confirm, send, status); **vendor three.js** for offline 3D.
- Tests + a real run-through on the running app.
**Exit:** describe → preview → tweak → validate → print/send, offline-capable, on the target box.
**Needs:** target box. **Size:** ~2–3 weeks.

## Stage 5 — One-click installable build (for a machine like this one)
**Goal:** double-click installer → working KimCad on a 32 GB/780M Windows box, no terminal.
- Electron wrap; electron-builder → a single `KimCad-Setup.exe` (NSIS); bundle OpenSCAD +
  OrcaSlicer + the Python core; first-run setup that detects Ollama + pulls **`gemma4:e4b`**
  with a progress UI; unsigned (SmartScreen documented).
- Tested on a clean Windows profile on this hardware class.
**Exit:** clean install → working app from the `.exe`, zero command line. (This is the
competitor's "installable, testable" — built to actually run on Kim's-class hardware.)
**Needs:** target box + a clean test profile. **Size:** ~1.5–2.5 weeks.

## Stage 6 — Printability & part-quality hardening (Phase 3)
**Goal:** the gate catches real print-quality problems, not just size/watertightness.
- Overhang/support detection; true wall-thickness measured from the mesh; fix the
  multiple-shells false-flag on hollow containers; real snap-fit/lid geometry (the deferred
  shortcut, paid back); a library quality pass. Tests per check.
**Exit:** passing parts are genuinely print-ready. **Needs:** target box. **Size:** ~2–3 weeks.

## Stage 7 — Model + benchmark + telemetry, tuned *for the target* (Phase 4)
**Goal:** provably good on the target hardware, with a real benchmark suite.
- Tune `gemma4:e4b` hard for this task; also bench the other small local options already on the
  box (e.g. `deepseek-coder:6.7b`) and pick the best **on-target** default with data — no
  "bigger model on a GPU" escape; the constraint is the point.
- Validate the cloud fallbacks (DeepSeek/OpenRouter) as an opt-in only.
- Grow the benchmark well past 10 prompts; **richer 3-axis grading** (slices-clean /
  matches-request / correct-dimensions) instead of pass-if-it-completes.
- **Telemetry:** in-app metrics vs the §4.2 thresholds + a public beta feedback loop (the
  confirmed replacement for the recruited study).
**Exit:** a strict suite, a data-backed on-target model choice, live quality instrumentation.
**Needs:** target box. **Size:** ~2–3 weeks.

## Stage 8 — Image & sketch → DesignPlan (experimental, honest about the hardware)
**Goal:** a photo of a part, or a dimensioned sketch, seeds an editable, validated plan —
*if it can run acceptably on a 780M box.*
- **Sketch path first (more feasible):** a small vision model reads the sketch's shape + written
  dimensions straight into the DesignPlan — no 3D reconstruction, lighter weight.
- **Photo path (experimental):** the smallest viable image-to-3D model → reference mesh →
  Trimesh measures bbox + rough features → seeds the plan. **Honest caveat:** TripoSG/TRELLIS-
  class models are heavy; on a 780M iGPU they may be too slow to be usable. This path is
  best-effort — we try the smallest/quantized variant, measure it on the target, and **descope
  it if it can't run acceptably** rather than pretend. Lowest priority (you already said so).
- Trust boundary enforced throughout: image output is untrusted, flows into the validated
  schema, never printed raw.
**Exit:** sketch→plan working on-target; photo→plan working *or* honestly marked not-viable
on this hardware. **Needs:** target box (this is the constraint, not a missing GPU).
**Size:** sketch ~1–2 weeks; photo unknown until measured on-target.

## Stage 9 — CadQuery parallel renderer + richer export (long-term)
**Goal:** a second, type-safe CAD backend and real CAD export formats.
- `kimcad.cadquery` parallel to `kimcad.openscad`; CadQuery module library + prompts;
  **STEP/BREP export** (editable CAD for sharing/interop, not just mesh/STL); renderer choice in
  config, parity-validated. Tests.
**Exit:** optional CadQuery backend with STEP/BREP, switchable in config.
**Needs:** target box; OpenCASCADE is a heavy dep — confirm it installs cleanly on this class
of machine before committing. Revisit only if OpenSCAD's limits bite. **Size:** ~3–4 weeks.

## Stage 10 — Beta with Kim: real hardware, real prints, release (FINAL)
**Goal:** the one and only real-hardware phase — everything printer-physical happens here.
- **Kim is the beta tester.** On her actual printer(s), validate the *whole* loop live: the
  connectors and status from Stages 2–3, real slicing, real sends, and **real printed parts**.
- Fix whatever only shows up on real hardware (it always does).
- User docs: install guide, usage, supported-printer matrix (now with real "verified on metal"
  marks for Kim's printers, API-only for the rest).
- Beta release (OSS, unsigned, beta posture); re-enable hosted CI; tag a release.
**Exit:** a shipped beta that has produced real printed parts on Kim's hardware.
**Needs:** Kim + her printers. **Size:** ~1–2 weeks + print iteration.

---

## What changed from the first draft, and what didn't
- **Removed entirely:** the "GPU box" assumption. Everything targets the 32 GB/780M machine.
  Model work (Stage 7) and image-to-3D (Stage 8) are constrained to what runs *here* — a smaller
  model where needed, and image-to-3D honestly flagged as maybe-not-viable rather than deferred
  to imaginary hardware.
- **Moved:** all real-printer validation out of the mid-stages into the single final beta with
  Kim (Stage 10). Stages 2–3 now build and mock-test the software with no hardware dependency.
- **Foundational fix:** the model is now `gemma4:e4b`, which makes the dev loop fast and stable
  and matches what the competitor proved works.
- **Still nothing dropped:** print loop, gated export, G-code proof, send abstraction, MCP,
  download fallback, Manifold3D, multi-brand coverage, ready/not-ready UI, photo **and** sketch
  intake, CadQuery **and** STEP/BREP — each is in a stage above.
- **One open question I'm not glossing:** which printer(s) Kim has — that decides which connector
  and profile to build first.
