# KimCad — Full Plan to Finished Product (v3.0 Windows beta)

Every stage is a **complete, shippable deliverable** — it ends with the product working,
tested, and committed, not a half-built slice. Each lists full scope, exit criteria,
dependencies, and an honest size. Where something genuinely can't be proven yet, it says so.

**Numbering note:** stages below use the **repo tag numbering** (`stage-0` … `stage-11`), which
is what the git tags follow. **Stages 3–11 are the current 9-stage v3.0 Windows-beta plan**
(Stage 3 is done; Stages 4–11 are ahead). The canonical product spec is in-repo at
`docs/design/KimCad-Unified-Product-Spec-v3.0.md` (+ the design handoff under `docs/design/`).

## The target (this is the whole game)
- **Hardware: a 32 GB-RAM machine with an AMD 780M integrated GPU — no discrete GPU.**
  This is *both* the development target and the deployment target. If it doesn't run well
  here, it doesn't ship. There is no GPU box coming; "wait for the GPU" is off the table.
- **Model (current): `gemma4:e4b`** — a small (~4B-effective) on-device model via local Ollama
  that fits and runs fast on this class of machine. `gemma3:12b` was the wrong call (too big,
  slow, crashed the server). **Stage 6 swaps the default to `Qwen2.5-Coder 1.5B`** (benchmarked
  on the target box first) with `gemma4:e4b` kept as the non-China alternative + vision fallback,
  per spec §7.5. Local-first; cloud is opt-in via `config/local.yaml`.
- **Printers live at Kim's house, not here.** So *all* real-hardware validation — every real
  print, every live printer connection — happens **only after Stage 11**: once the beta gate
  ships the installable v3.0 Windows beta, **Kim runs that beta on her real hardware** as the
  first real-world tester. Everything before that is built and tested against mocked/emulated
  printers. **Kim's printers: Bambu Lab P2S + A1, and Elegoo Neptune 4 Max.**

## Confirmed deviations (do not re-add)
P2S not P1S; code-signing dropped (unsigned beta); recruited usability study replaced by
in-app telemetry + public beta feedback.

## Current baseline (honest, as of Stage 3 — DONE, merged, tagged)
The Phase-1 pipeline + the local web UI are built and tested. **Stage 3 is merged to `main` and
tagged `stage-3` @ `96aba02`.** Verification: **400 tests passing** (including 4 live OrcaSlicer
slices) and **`ruff` clean**. The pre-push hook (`.githooks/pre-push` → `scripts/ci.sh` = ruff +
the FULL pytest incl. live) gates every push. Connectors cover OctoPrint + Moonraker/Klipper +
PrusaLink/Prusa + a loopback mock + KimCad's own MCP server, with per-printer per-material
profiles and a ready/not-ready status UI. **Next = Stage 4 (React SPA shell + viewport).**

Still ahead before beta: the React SPA + viewport (Stage 4), the deterministic template engine +
live sliders (Stage 5 — the critical-path that makes instant sliders possible), the model swap
(Stage 6), Smart Mesh + PrintProof3D (Stage 7), CadQuery (Stage 8), image on-ramp (Stage 9),
direct-print UI + Bambu-native (Stage 10), and the Windows installer + beta gate (Stage 11).
**No part has driven real hardware yet — that's after Stage 11, at Kim's.**

---

## Stage 0 — Refit to the target model and close Phase 1  ✅ DONE
**Goal:** the pipeline works on `gemma4:e4b` on the target box and clears the done-gate there.
- ✅ Planner + codegen validated on `gemma4:e4b`; prompts simplified for the smaller model.
- ✅ 10-prompt benchmark re-run on e4b to a real number, ≥ 8/10 on the target hardware.
**Exit (met):** `kimcad bench --min-success-rate 0.8` passes on `gemma4:e4b`, on the target box.

## Stage 1 — Gated export: a real, validated print file  ✅ DONE
**Goal:** any validated part → confirmed → a verified G-code/3MF file. *(No printer needed.)*
- ✅ Printer/material/profile model; profile names → on-disk profile files; explicit
  material/profile confirmation (CLI `--slice`, web select + confirm); OrcaSlicer wired behind
  the confirmation gate.
- ✅ **G-code proof per run:** the exported 3MF is opened and verified to carry real
  motion-bearing toolpaths (G0/G1/G2/G3); the slicer's time/layer/filament estimate is parsed
  and surfaced; empty/garbage fails loudly.
- ✅ **Manifold3D** pre-slice hardening (round-trips to a guaranteed 2-manifold, never silent;
  optional at runtime); download/export delivery path.
**Exit (met):** confirm a part → verified non-empty G-code with an estimate, multiple part types.
> All three of Kim's printers are sliceable and proven (Bambu P2S, Bambu A1, Elegoo Neptune 4 Max)
> via a live end-to-end slice through the bundled OrcaSlicer.

## Stage 2 — Send-to-printer connector + MCP (software-complete)  ✅ DONE
**Goal:** the full send path exists and is tested — live printing waits for the real-hardware phase at Kim's (after Stage 11).
- ✅ **`PrinterConnector` abstraction** (a `Protocol`): capabilities / status / send / job-status,
  swappable per connection; a built-in **`mock`** loopback connector exercises the whole path.
- ✅ **OctoPrint connector** (stdlib `urllib`, API key env-only — never stored/logged) + a runnable
  mock OctoPrint server so the real REST path is tested offline.
- ✅ **Capability reconciliation** (printer-reported build volume / nozzle / materials auto-fills a
  blank profile field and flags config-vs-printer mismatch; config stays authoritative).
- ✅ **Explicit per-send confirmation** everywhere — `confirm is True` (not merely truthy), and the
  file must prove out as a real motion-bearing slice — in CLI (`--send`), web, and **MCP**.
- ✅ **MCP server** (dependency-free JSON-RPC 2.0 over stdio): `list_connectors` / `printer_status`
  / `printer_capabilities` / `send_print`.
**Exit (met):** confirmed part → "sent" through a connector to a mock printer; status flows through.

## Stage 3 — Printer coverage + ready/not-ready UI (software-complete)  ✅ DONE — tagged `stage-3` @ `96aba02`
**Goal:** multi-brand support and live status, all built and mock-tested.
- ✅ **Connector coverage:** OctoPrint + **Moonraker/Klipper** + **PrusaLink/Prusa**, each a real
  REST connector over stdlib `urllib` with a runnable mock server, + KimCad's MCP server.
- ✅ **Per-printer, per-material filament profiles, honestly:** the cross-vendor "Generic
  <MATERIAL>" fallback was **removed** (it mis-resolved e.g. Elegoo + TPU to a Bambu profile);
  each printer is offered only the materials it has a verified profile for (the Elegoo Neptune 4
  Max ships no TPU → TPU is "not available" for it, and the UI explains why).
- ✅ **Ready / not-ready connection-status UI:** a per-connection badge (ready / busy / offline /
  needs-setup / simulation) that never 5xxes and never leaks a credential, with a typed `reason`
  vocabulary shared across status and send; the **web `/api/slice` + `/api/send` refuse a
  gate-FAILED part server-side**, mirroring the CLI.
- ✅ Tested against each printer-API contract via mocks/emulators; passed the `audit-team` gate at
  **0/0/0/0/0** across all five roles + an independent Codex spot-check, then merged + tagged.
**Exit (met):** OctoPrint / Moonraker / PrusaLink selectable with live (emulated) status; the
ready/not-ready UI works; safety gate guards hold on every send path (CLI/web/MCP).
> **Still a gap (folded into later stages):** a **Bambu-native** connector (Stage 10, via
> `bambulabs-api`) and the Creality-Connect / Prusa-Connect cloud paths.

---

## Stage 4 — React SPA shell + viewport  ⬅ NEXT
**Goal:** replace the minimal web UI with the designed app shell, served locally, with a real 3D
viewport — the §5 design at high fidelity.
- **React + TypeScript + Vite SPA** compiled to static files and **served by the existing local
  Python server** (Node/Vite are build-time only; they never ship). The built SPA is byte-identical
  across Win/Mac/Linux.
- **Workshop design system baseline** from `docs/design/` (warm sand `#f0ebe0` / terracotta
  `#c8623a` / dark viewport `#14171c`; Bricolage Grotesque / Hanken Grotesk / JetBrains Mono).
- **Dark Three.js viewport foundation** using **vanilla Three.js** (port `KCViewport` from
  `docs/design/prototype/jsx/preview.jsx` behind a thin React wrapper — not react-three-fiber).
- **Wire the existing text → plan → gate → slice → download flow** through the new UI (read-only
  first; real live sliders need the Stage 5 template engine, so only non-functional / read-only
  slider scaffolding here if any).
- Tests + a real run-through on the running app.
**Exit:** the existing flow works end-to-end through the new React UI; the viewport renders; the
Workshop baseline is in place; the built SPA is served as static files by the Python server.
**Needs:** target box + Node (build-time only). **Size:** ~2–3 weeks.

## Stage 5 — Deterministic template engine + live sliders
**Goal:** the **critical-path** `templates/` module — parametric, deterministic templates that
re-render in **<1s with no LLM call** — which is what makes true live sliders possible.
- A `templates/` engine of named parametric families; the planner picks a template + fills named
  parameters; re-render is a pure deterministic pass (no model in the loop).
- **Named live sliders** wired to template parameters: drag → re-render instantly, fully local.
- The LLM-writes-OpenSCAD path stays as the fallback for prompts no template covers (tiered).
**Exit:** named parameter sliders drag → re-render in <1s with no model call across the template
families; the tiered template→LLM fallback is proven. **Needs:** target box. **Size:** ~2–3 weeks.

## Stage 6 — Model swap (Qwen default) + tiered fallback
**Goal:** swap the default model to `Qwen2.5-Coder 1.5B`, benchmarked on the target box, with a
tiered fallback chain.
- Benchmark `Qwen2.5-Coder 1.5B` on the 780M box; make it the default if it clears the bar; keep
  `gemma4:e4b` as the non-China alternative + vision fallback. No "bigger model on a GPU" escape.
- Tiered fallback (template → primary model → alt model); cloud (DeepSeek/OpenRouter) opt-in only.
- Grow the benchmark past 10 prompts; richer 3-axis grading (slices-clean / matches-request /
  correct-dimensions).
**Exit:** a data-backed on-target default model + a proven fallback chain. **Needs:** target box.
**Size:** ~2–3 weeks.

## Stage 7 — Smart Mesh + PrintProof3D + readiness report
**Goal:** real print-quality validation surfaced as a designed report.
- **Smart Mesh** readiness (overhang/support detection, true wall-thickness from the mesh, fix the
  multiple-shells false-flag on hollow containers); the **PrintProof3D** validation harness wired
  in; a print-readiness **report card** matching the design (not a raw text panel).
- Tests per check; the gate hard-fails real defects, not just size/watertightness.
**Exit:** a part produces a Smart Mesh readiness report; PrintProof3D integration validated;
passing parts are genuinely print-ready. **Needs:** target box. **Size:** ~2–3 weeks.

## Stage 8 — CadQuery parallel backend
**Goal:** a second, type-safe CAD backend and real CAD export.
- `kimcad.cadquery` parallel to `kimcad.openscad`, **real OCCT on Python 3.13** (CadQuery supports
  3.9–3.13 — pin 3.13; not a trimesh stub); a CadQuery module library + prompts; **STEP/BREP
  export**; renderer choice in config, parity-validated.
- Tests; confirm OpenCASCADE installs cleanly on this class of machine before committing.
**Exit:** an optional, real CadQuery backend with STEP/BREP export, switchable in config.
**Needs:** target box (Python 3.13 venv). **Size:** ~3–4 weeks.

## Stage 9 — Image & sketch on-ramp (opt-in, experimental)
**Goal:** a photo or dimensioned sketch seeds an editable, validated plan — **opt-in only**, honest
about the hardware.
- **Sketch path first** (a small vision model reads shape + written dimensions into the DesignPlan;
  no 3D reconstruction). **Photo path experimental** (smallest viable image-to-3D, e.g.
  TripoSG/OpenRouter → reference mesh → Trimesh measures bbox/features → seeds the plan); descope
  honestly if it can't run acceptably on the 780M.
- **Trust boundary enforced:** image output is untrusted, flows into the validated schema, never
  printed raw.
**Exit:** sketch→plan working on-target; photo→plan working *or* honestly marked not-viable on this
hardware. **Needs:** target box. **Size:** sketch ~1–2 weeks; photo unknown until measured.

## Stage 10 — Direct-print UI + Bambu-native + first-run wizard
**Goal:** the full direct-print experience in the SPA, plus the missing connector and onboarding.
- **Direct-print UI** surfaced in the React app (printer select → confirm → send → live status),
  behind the same `confirm is True` gate.
- **Bambu-native connector** (`bambulabs-api`) for the P2S + A1 (the gap left from Stage 3), plus
  the remaining cloud paths as feasible.
- **First-run setup wizard:** detect Ollama, pull the default model with a progress UI, pick a
  printer connection.
**Exit:** Bambu-native send path works (mock-tested); the first-run wizard onboards a clean profile;
direct-print UI is wired. **Needs:** target box + emulators. **Size:** ~2–3 weeks.

## Stage 11 — Windows installer + beta gate (FINAL pre-beta)
**Goal:** double-click installer → working KimCad on a 32 GB/780M Windows box, no terminal, then the
beta gate.
- **Windows shell via WebView2** (controlled render engine); package the built SPA + Python core +
  bundled OpenSCAD + OrcaSlicer; a single installer; unsigned (SmartScreen documented).
- First-run setup on a clean Windows profile; re-enable hosted CI; the **beta gate** (the full
  `audit-team` at 0/0/0/0/0 on the release).
- User docs: install guide, usage, supported-printer matrix (API-only until verified on metal).
**Exit:** clean install → working app from the installer, zero command line; beta gate passed; a
tagged beta release. **Needs:** target box + a clean test profile. **Size:** ~1.5–2.5 weeks.

---

## The beta on real hardware — at Kim's (post-Stage-11; the one and only physical phase)
Everything printer-physical happens here, after Stage 11 ships the installable v3.0 Windows beta.
**Kim runs that beta on her real hardware** as the first real-world tester; on her actual printers
(Bambu P2S + A1, Elegoo Neptune 4 Max) the *whole* loop is validated live — connectors, status, real
slicing, real sends, **real printed parts** — and whatever only shows up on real metal gets fixed.
Final-level library breadth lands here too. **Needs:** Kim + her printers.

## What this plan locks in
- **No "GPU box" assumption** — everything targets the 32 GB/780M machine; model work (Stage 6) and
  image-to-3D (Stage 9) are constrained to what runs *here*.
- **All real-printer validation happens after Stage 11** (once the beta ships), at Kim's; Stages
  2–10 build and mock-test with no hardware dependency.
- **Stage 5 (template engine) is the critical path** — instant sliders are impossible on the
  LLM-writes-OpenSCAD engine alone; UX-first and architecture-first converge there.
- **Nothing dropped:** print loop, gated export, G-code proof, send abstraction, MCP, download
  fallback, Manifold3D, multi-brand + Bambu-native coverage, ready/not-ready UI, template engine +
  live sliders, Smart Mesh + PrintProof3D, CadQuery + STEP/BREP, sketch **and** photo intake, the
  Windows installer — each is in a stage above.
