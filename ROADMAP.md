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
- **Model: `gemma4:e4b`** — a small (~4B-effective) on-device model via local Ollama that fits and
  runs fast on this class of machine. `gemma3:12b` was the wrong call (too big, slow, crashed the
  server). **Stage 6 evaluated `Qwen2.5-Coder 1.5B` as a candidate default and ruled it out** — the
  live bake-off showed it can't produce a design plan at all (a code-completion model echoes the
  JSON schema instead of an instance), so **gemma4:e4b stays the default**. A bigger Qwen would be
  larger than gemma and therefore slower on this CPU box, defeating the speed goal. Local-first;
  cloud is opt-in via `config/local.yaml`.
- **Printers live at Kim's house, not here.** So *all* real-hardware validation — every real
  print, every live printer connection — happens **only after Stage 11**: once the beta gate
  ships the installable v3.0 Windows beta, **Kim runs that beta on her real hardware** as the
  first real-world tester. Everything before that is built and tested against mocked/emulated
  printers. **Kim's printers: Bambu Lab P2S + A1, and Elegoo Neptune 4 Max.**

## Confirmed deviations (do not re-add)
P2S not P1S; code-signing dropped (unsigned beta); recruited usability study replaced by
in-app telemetry + public beta feedback.

## Current baseline (honest, as of Stage 4 — DONE, merged, tagged)
The Phase-1 pipeline, the local web UI, and the designed React SPA + Three.js viewport are built
and tested. **Stage 3 is tagged `stage-3` @ `96aba02` and Stage 4 is tagged `stage-4`** (off the `dcbcd1a`
merge, with the lightweight tag advanced to the later docs-consistency commit so it carries these
corrected docs), both merged to `main` (in sync with `origin/main`). Verification: **404 tests passing** (including 4
live OrcaSlicer slices), **`ruff` clean**, and the frontend `npm test` (vitest, 19 passed) + `build`
pass on Windows with `npm audit` = 0. The supported gate is **native Windows**: the pre-push hook
(`.githooks/pre-push` → `scripts/ci.sh` = ruff + the FULL pytest incl. live) gates every push, and
the frontend steps pass natively. (Running `scripts/ci.sh` under WSL/Linux fails only on the
Windows-installed `node_modules` — Vite 8 / Rolldown's Linux native binding isn't present — which is
an environment mismatch, not a code defect; a Linux `npm ci` would install it.) Connectors cover
OctoPrint + Moonraker/Klipper + PrusaLink/Prusa + a loopback mock + KimCad's own MCP server, with
per-printer per-material profiles and a ready/not-ready status UI. The React SPA (Workshop design
system, vanilla Three.js viewport, wired design→gate→slice→download flow) replaced the minimal web
UI. **Stage 5 (deterministic template engine + live sliders — the critical path) is DONE** — merged
to `main` (merge commit `14896d6`) and tagged `stage-5` (the engine, the tiered pipeline, the
`/api/render` re-render API, the live SPA sliders, and a deterministic-family benchmark proving the
<1 s no-model re-render; through the full `audit-team` gate + re-audit at 0/0/0/0/0). **Stage 6 (the
model layer — hardware-aware advisor, tiered fallback, 3-axis grading, model bake-off, and plan-failure
robustness) is DONE — merged to `main` and tagged `stage-6`** (through the full `audit-team` gate +
remediation at 0/0/0/0/0). Its data-backed verdict: keep `gemma4:e4b` (the Qwen candidate failed the
bake-off). **Stage 7 (Smart Mesh + PrintProof3D + readiness report + learning store) is DONE —
merged to `main` and tagged `stage-7`** (slices 1–6 each `audit-lite` 0/0/0/0/0; the full 5-role
`audit-team` stage gate + remediation closed at 0/0/0/0/0). **Next = Stage 8.5 (Usability), then
Stage 8 (CadQuery)** — the usability stage was inserted ahead of the CadQuery backend (8.5-first,
ratified 2026-06-03) because the deal-killer UX gaps must be closed before adding a second geometry
engine. Stage 8.5 is currently IN PROGRESS on branch `stage-8.5-usability` (see the Stage 8.5
section below); nothing in it is merged or tagged yet.

Still ahead before beta: usability (Stage 8.5, in progress), CadQuery
(Stage 8), image on-ramp (Stage 9), direct-print UI + Bambu-native (Stage 10), and the Windows
installer + beta gate (Stage 11). **No part has driven real hardware yet — that's after Stage 11,
at Kim's.**

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

## Stage 4 — React SPA shell + viewport  ✅ DONE — merged + tagged `stage-4`
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
  parameters in Stage 4; the real live sliders arrived with the Stage 5 template engine, below).
- Tests + a real run-through on the running app.
**Exit:** the existing flow works end-to-end through the new React UI; the viewport renders; the
Workshop baseline is in place; the built SPA is served as static files by the Python server.
**Needs:** target box + Node (build-time only). **Size:** ~2–3 weeks.

## Stage 5 — Deterministic template engine + live sliders
**Status: DONE — merged to `main` (merge commit `14896d6`) and tagged `stage-5`. Slices 1–5 each
passed `audit-lite` at 0/0/0/0/0; the full `audit-team` stage gate + re-audit closed at 0/0/0/0/0;
native Windows gate green.**
**Goal:** the **critical-path** `templates.py` module — parametric, deterministic templates that
re-render in **<1 s with no LLM call** — which is what makes true live sliders possible.
- ✅ A `templates.py` engine of seven named parametric families (`snap_box`, `box`, `enclosure`,
  `tube`, `wall_hook`, `cable_clip`, `drawer_divider`) over the proven `library/` modules; the
  planner's `object_type` picks a family and its named parameters are filled from the plan;
  re-render is a pure deterministic emit + render (no model in the loop).
- ✅ **Named live sliders** wired to template parameters: drag → debounced `POST /api/render/<id>`
  → re-render locally, viewport reloads, gate/report/values update from server truth; stale
  slices invalidated. LLM-backed parts stay read-only.
- ✅ The LLM-writes-OpenSCAD path stays as the fallback for prompts no template covers (tiered).
- ✅ A deterministic-family **benchmark** (`python -m kimcad.template_bench`) proving every family
  renders watertight at its declared envelope, no-model, in <1 s — recorded in
  `docs/benchmarks/stage-5-template-families.md`.
**Exit:** named parameter sliders drag → re-render in <1 s with no model call across the template
families; the tiered template→LLM fallback is proven. **Needs:** target box. **Size:** ~2–3 weeks.

## Stage 6 — Model layer: hardware-aware advisor + tiered fallback + bake-off (DONE — merged + tagged `stage-6`)
**Goal:** a data-backed default model on the target box, with the machinery to choose, fall back, and
compare models. **Outcome:** the candidate swap (`Qwen2.5-Coder 1.5B`) was evaluated and **rejected** —
`gemma4:e4b` stays the default.
- **Hardware/availability advisor** (`kimcad models`): probes RAM/CPU/GPU + installed Ollama models
  and recommends one — advisory only, never rewrites config; the model stays choosable (config
  backends + `config/local.yaml` + `--backend`). Surfaces a non-China alternative when the pick is
  China-origin.
- **Tiered fallback** (`FallbackProvider`): a primary connection/timeout/model-not-found error
  transparently retries an opt-in alt backend (`llm.alt_backend`); off by default. Cloud
  (DeepSeek/OpenRouter) opt-in only.
- **Richer 3-axis benchmark grading** (slices-clean / matches-request / correct-dimensions) layered
  on the completion done-gate, plus a **model bake-off** (`kimcad bakeoff`) that runs the benchmark
  per backend and recommends switch-or-keep (it recommends only — flipping the default is a human
  call).
- **Plan-failure robustness:** a model returning un-parseable output fails clean (`plan_failed`)
  instead of a raw traceback.
- **Bake-off verdict (run live on the target box):** `Qwen2.5-Coder 1.5B` scored **0/10** — it fails
  the design-plan step (echoes the schema), even with JSON mode forced. `gemma4:e4b` is the only
  working local option, so it remains the default. A larger Qwen is bigger than gemma → slower on
  CPU → fails the "faster default" premise. (Bigger benchmark prompt set is deferred to a later
  stage; the 10 Appendix-B prompts remain the done-gate.)
**Exit (met):** a data-backed on-target default (`gemma4:e4b`, confirmed) + a proven
fallback/advisor/bake-off toolchain. **Status:** DONE — merged to `main`, tagged `stage-6`.

## Stage 7 — Smart Mesh + PrintProof3D + readiness report  ✅ DONE — merged + tagged `stage-7`
**Status: DONE — merged to `main` and tagged `stage-7`** (the tag advanced past the merge to the
docs-DONE commit so the tagged artifact's docs say "done", not "pending" — the Stage-4 lesson).
Slices 1–6 each passed `audit-lite` at 0/0/0/0/0; the full 5-role `audit-team` stage gate ran
2026-06-02 (0B/0C/1Maj/11Min/9Nit) and was remediated to **0/0/0/0/0**
(`docs/audits/stage-7/audit-team-stage-7-2026-06-02/`). The readiness card was rendered-checked
(desktop + mobile) live.
**Goal:** real print-quality validation surfaced as a designed report.
- ✅ **Smart Mesh** readiness synthesis (`smart_mesh.py`): a pure verdict — score / risks /
  recommendations / confidence — folding the Printability Gate, mesh integrity, and an *optional*
  PrintProof3D report; the tone is the worst of KimCad's own read and the engine's, so it never
  over-promises.
- ✅ **PrintProof3D** wired in at **arm's length** (`printproof3d.py`): the owner's MIT Rust engine
  runs as a subprocess (never linked), validating the bed-positioned hardened mesh; best-effort and
  injection-safe — a missing/un-built engine degrades to the gate, never raises. Optional via
  `binaries.printproof3d`.
- ✅ A print-readiness **report card** (`RightPanel.tsx`) matching the design — a score gauge,
  verdict, confidence badge, risks, recommendations, and honest attribution (not a raw text panel).
- ✅ A local-first **learning store** (`history.py`) adding an honest "compared to your past parts"
  line; strictly factual, never flattering.
- ✅ Tests per check (Python + vitest); the deterministic gate remains the slice authority and
  PrintProof3D adds advisory depth (folding engine fails into the slice-gate is a noted follow-up).
**Exit:** a part produces a Smart Mesh readiness report; PrintProof3D integration validated;
passing parts are genuinely print-ready. **Remaining for the stage gate:** the full `audit-team` at
0/0/0/0/0 → merge → tag `stage-7`. **Needs:** target box. **Size:** ~2–3 weeks.

## Stage 8.5 — Usability: turn the demo into a tool people keep  🔧 IN PROGRESS (branch `stage-8.5-usability`)
**Status: IN PROGRESS — executed BEFORE the Stage 8 CadQuery backend (8.5-first, ratified 2026-06-03;
spec Addendum B).** Full punch list: `docs/stage-8.5-usability-plan.md`.
**Goal:** fix the deal-killers that make the working core loop unusable for real, repeated use — and
finish the design-spec surfaces (`docs/design/`) that were deferred during the build.
**Why first:** the built UI is all in-memory (a refresh wipes the part), has no saved-designs
library, no in-workspace refinement (the "conversation" is one-shot), no settings screen, mm-only,
shows problems as text not on the model, and gives no real progress on long model runs. CadQuery
would otherwise stack a second power feature on a base that loses your work on refresh.
**Slices** (each `audit-lite` → 0/0/0/0/0 with a rendered desktop+mobile check; stage-end `audit-team`
→ 0/0/0/0/0 → merge → tag): (1) persistence + "My Designs"; (2) iterative refinement + version
history (build the prototype's `VersionRail`); (3) direct numeric editing; (4) units (mm/inch);
(5) settings + engine discoverability (`ModelPicker`); (6) problems shown on the model (viewport
raycast/highlight); (7) onboarding / model-down / progress / help (`FirstRunWizard`); (8) output
clarity + print preview; (9) responsive, accessibility, copy, polish.
**Exit:** a person can make a part, leave, come back, refine it, set units, see problems on the model,
and discover the optional engines — without hitting a wall. **Needs:** target box. **Size:** large.

## Stage 8 — CadQuery parallel backend  (after Stage 8.5)
**Goal:** a second, type-safe CAD backend and real CAD export. **Feasibility proven** 2026-06-03:
CadQuery 2.7 + real OCCT (OCP 7.8.1) installs + exports STEP/BREP/STL cleanly on Python 3.13 in an
isolated venv. Note: the main KimCad venv is **3.14** (CadQuery tops out at 3.13), so the backend
runs as an **arm's-length subprocess worker in its own 3.13 venv** (like OpenSCAD/OrcaSlicer/
PrintProof3D), not an in-process import — keeps the main runtime on 3.14 and the heavy OCCT
dependency optional. Discoverability (the enable UI) lands in Stage 8.5 Slice 5.
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
- **Bundle the PrintProof3D engine + turn Smart Mesh's deeper validation ON by default.** The
  Stage-7 integration is arm's-length and verified (KimCad generates the engine's profiles, calls
  it, parses the report); it's only off today because the engine binary isn't shipped. Bundle the
  engine `.exe` in the installer alongside OpenSCAD/OrcaSlicer (or fetch+pin it via
  `scripts/fetch_tools.py` once it cuts a stable, per-platform published release) into
  `tools/printproof3d/` — the path the default config already names — so a default install gets the
  real overhang/bridge/bed-adhesion validation, not gate-only. Gate this on the engine reaching a
  stable release (it's `0.5.0-rc2` today); the arm's-length wrapper already degrades to gate-only if
  the engine is absent or misbehaves, so it can't destabilize the install.
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
