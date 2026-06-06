# Changelog

All notable changes to KimCad are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

> The project stays at `0.1.0` while pre-release; each stage is tagged as it lands.
> **Stages 0–7 are tagged (`stage-0` … `stage-7`).** Stage 5 (deterministic template engine +
> live sliders) and **Stage 6 (the model layer — advisor, tiered fallback, 3-axis grading,
> bake-off, plan-failure robustness) both merged + tagged 2026-06-02** (Stage 6 through the full
> `audit-team` gate + remediation at 0/0/0/0/0). **Stage 7 (Smart Mesh + PrintProof3D + readiness
> report + learning store) merged + tagged `stage-7` 2026-06-02** — through the full 5-role
> `audit-team` stage gate + remediation at 0/0/0/0/0. **Stage 8.5 (Usability) is DONE — merged to
> `main` and tagged `stage-8.5`.** All 11 slices shipped; the stage gate passed both the runtime
> wiring-audit and the 5-role audit-team, with every finding remediated and independently re-audited
> twice to 0/0/0/0/0 (see `docs/audits/stage-8.5/stage-gate-2026-06-05/`). Slices 1–7 below for reference:
> Slice 1 (persistence + "My Designs"), Slices 2–4 (refine-as-a-conversation + version history,
> numeric parameter entry, mm/inch units), Slice 5 (the on-ramps design — no code), Slice 6 (the
> in-app Settings screen — model status, opt-in cloud, experimental toggle), and Slice 7 (the
> "describe with a photo" on-ramp). Slices 1, 2–4, and 6 have each passed their `audit-team` gate at
> 0/0/0/0/0; Slice 7 is at its slice-end gate. All pending Scott's stage approval. These sections
> accumulate toward the `0.1.0` release.
> New runtime dependency (Stage 1): **`manifold3d>=3.0`** — installed by default
> (a compiled wheel; relevant to the install footprint on the 32 GB target), though the
> *import* is optional at runtime (hardening is skipped with a note if it is absent).

### Added
- **Stage 8.5 — Usability — DONE (merged to `main`, tagged `stage-8.5`).** All 11 slices shipped and
  the stage gate passed both lanes: the runtime **wiring-audit** (drove the live app — every control
  proven genuinely wired + persisted) and the 5-role **audit-team**, which rolled up 42 findings
  (0 Blocker / 0 Critical / 11 Major / 20 Minor / 11 Nit). Every finding was fixed — including two
  real safety bugs (a slice/re-render geometry-version race that could serve a stale-shape print, and
  reopen/import trusting a stored gate verdict instead of re-validating the mesh), each with a
  regression test — then independently re-audited twice to **0/0/0/0/0** across all five lanes
  (`docs/audits/stage-8.5/stage-gate-2026-06-05/`). Final: 763 pytest (non-live) + 4 live OrcaSlicer
  + 262 vitest; ruff clean; SPA build byte-reproducible. The slices, beyond 1–7 below:
  - **Slice 8 — problems on the model:** PrintProof3D's flagged regions are highlighted in the 3D
    viewport (overhangs / poor bed contact), with click-a-risk-to-focus and a legend/toggle.
  - **Slice 9 — onboarding / model-down / progress / help:** a recoverable "your local AI isn't
    running" wall, live step-progress (planning → generating → rendering → validating), a first-run
    setup wizard, and in-app glossary "(i)" tips. gemma4:e4b is THE model throughout (never qwen).
  - **Slice 10 — output clarity + print preview:** the slice estimate broken out (time / layers /
    filament length + weight; weight estimated from volume × material density when the profile reports
    none, labeled as such), a "design → print file" framing, named print file + copy-link, and clear
    export formats. (A true G-code toolpath/layer viewer is scheduled for Stage 10's direct-print UI.)
  - **Slice 11 — responsive / a11y / copy / polish:** keyboard shortcuts + a discoverable "?" help
    modal, plain-English copy, the right-column visual hierarchy + icon-tile printability checks
    restored, refine-by-talking chips, an always-on printer-status chip, and a mobile sticky CTA.
- **Stage 8.5 — escape paths on every action (on branch, not yet merged/tagged):** every long or
  blocking action is now cancelable, so the app never traps you. The "Designing your part…" screen
  shows an honest "this runs on your computer's AI — it can take a few minutes" note, a live elapsed
  timer, and a **Cancel** (plus Esc); the photo "Reading…" read, slicing, and importing each get a
  **Cancel** that aborts the request and returns you to the prior control with no error. Requests are
  abortable end to end (an AbortSignal threaded through the API client).
- **Stage 8.5 Slice 7 — "describe with a photo" on-ramp (on branch, not yet merged/tagged):** a
  secondary affordance on the landing + workspace reads a photo with gemma4:e4b's **local** vision
  into a rough, editable text seed that pre-fills the existing text→DesignPlan path. It's a starting
  point, never a "photo → finished part" promise: the user confirms/edits the seed (a photo carries
  no scale, so sizes are estimates) before anything runs. The photo is read locally and **never
  auto-sends off the machine** (vision is pinned to the local provider even when cloud TEXT is on),
  is never persisted, and never logged; an unreadable/oversized photo is a clean 422/413, never a
  500. New `POST /api/photo-seed` + `LLMProvider.describe_photo` (Ollama's native `/api/chat` with
  `think:false`).
- **Stage 8.5 Slice 6 — in-app Settings screen (on branch, not yet merged/tagged):** model status
  (gemma4:e4b, local, with a health line — no menu of alternatives), an off-by-default **cloud
  opt-in** via OpenRouter (the user picks the model; the API key is a normal Settings field, saved
  locally and shown masked to the last few characters, never echoed back in full or stored in the
  repo/logs), an off-by-default **experimental raw-codegen generator** (sandboxed, never bypasses the
  Printability Gate, offered inline on an out-of-template request), plus tools health + about + a
  two-step reset. New `settings_store.py`, `/api/settings`, `/api/model-status`.
- **Stage 8.5 Slices 2–4 (on branch, not yet merged/tagged):** refine a part as a **conversation**
  with full **version history** (a timeline with step-back/undo + a "what changed" compare);
  **numeric parameter entry** alongside the live sliders; and a **mm / inch units** toggle so a US
  maker isn't walled out. (Gated together by the Slice 2–4 `audit-team` + `wiring-audit` at
  0/0/0/0/0.)
- **Stage 8.5 Slice 1 — local persistence + "My Designs" library (on branch `stage-8.5-usability`, not yet merged/tagged):**
  - Designs are saved automatically to a local, best-effort store under `~/.kimcad/designs/<id>/`
    (`meta.json` + `mesh.stl` + `thumb.png`) — never the repo, nothing leaves the machine. A built
    part auto-saves and the SPA routes to `#/design/<id>`, so a refresh restores the part + its
    live sliders instead of losing the work.
  - A **My Designs** gallery (`#/designs`): thumbnail grid with reopen, inline rename, duplicate,
    two-step delete, search by name, and sort (newest / oldest / name). Reopen re-registers the
    design into the live loop so its template sliders work again.
  - **Export / import** a design as a portable `.kimcad` zip (zip-slip-safe — only the three known
    files are read by exact name; a bounded inflated-read rejects a decompression bomb; the
    compressed upload is capped at 32 MiB).
  - A new `design_store.py` module (`DesignStore`) and `config.paths.designs`; new
    `/api/designs*` endpoints (list / save / reopen / thumb / export / import / rename / delete /
    duplicate). Writes are serialized + atomic (with a Windows `os.replace` retry); a save indicator
    in the Topbar surfaces "Saving… / Saved / retrying."
- **Stage 6 — model layer (merged + tagged `stage-6`):**
  - `kimcad models` — a hardware/availability-aware model advisor: probes RAM/CPU/GPU and the
    installed Ollama models and recommends the best one that fits, names an upgrade to pull, and
    surfaces a non-China alternative when the pick is China-origin. Advisory only — it never
    rewrites config; the model stays choosable.
  - Tiered LLM fallback (`FallbackProvider`): a primary connection/timeout/model-not-found error
    transparently retries an opt-in alt backend (`llm.alt_backend`, off by default).
  - Richer 3-axis benchmark grading (slices-clean / matches-request / correct-dimensions) layered
    on the completion done-gate, and `kimcad bakeoff` — a model bake-off that runs the benchmark
    per backend and recommends switch-or-keep (recommend only; flipping the default is a human call).
  - Plan-failure robustness: a model returning un-parseable output fails clean (`plan_failed`,
    CLI exit 6) instead of a raw traceback.
  - **Decision:** the `Qwen2.5-Coder 1.5B` candidate was evaluated via the live bake-off and
    **rejected** (0/10 — it can't produce a design plan); **`gemma4:e4b` stays the default.**
    A `local_qwen` backend is defined for the comparison and remains selectable via `--backend`.
- Project scaffold: src-layout package, configuration loader, dependency manifest,
  cross-platform line-ending normalization.
- Default configuration with Bambu P2S (reference) and Elegoo Neptune 4 Max printer
  profiles, four materials (PLA/PETG/TPU/ABS), and per-machine override via
  `config/local.yaml`.
- Design-Plan IR (Pydantic v2) with minimal single-question clarification.
- Provider-agnostic LLM layer over the OpenAI SDK — local Ollama / LM Studio,
  DeepSeek, and any OpenAI-compatible endpoint.
- Local-first posture: defaults to a local runtime (Ollama, `gemma4:e4b`); cloud
  backends are opt-in via `config/local.yaml`, no API key required out of the box.
- OpenSCAD code-generation system prompt and a five-file seed library
  (box, bracket, fasteners, fillets, mounts) injected into the prompt.
- Sandboxed OpenSCAD subprocess runner with native 3MF output (STL fallback).
- Trimesh mesh-validation pipeline and a Printability Gate (pass / warn / fail)
  checking dimensions, manifoldness, build-volume fit, and minimum wall thickness.
- Auto-orientation onto the most stable facet before slicing.
- OrcaSlicer CLI integration producing a validated print job and print report.
- Pipeline orchestrator (prompt → plan → code → render → validate → gate → orient →
  slice) and a `kimcad` CLI with `design` and `bench` verbs.
- Phase-1 benchmark harness — the ten Appendix B done-gate prompts
  (`bench/prompts.yaml`) scored against the §4.2 0.8 threshold.
- Cross-platform tools-fetch script (`scripts/fetch_tools.py`, standard library only),
  now with SHA-256 checksum verification (trust-on-first-fetch, then tamper-checked).
- Verified, checksum-pinned Windows OrcaSlicer build (v2.4.0-alpha) with end-to-end
  slice proof: a real generated part slices to a valid G-code-bearing 3MF on the
  Bambu P2S profile.
- Parametric library expansion — eight new modules across five new files covering the
  Appendix-B part families that previously had to be hand-built: wall and pegboard hooks
  (hooks.scad), cable clip (clips.scad), closed box / two-part enclosure / tube
  (containers.scad), spool holder (holders.scad), and drawer divider (organizers.scad).
  That brings the library to ten .scad files in all. Each module renders watertight at an
  exact, documented bounding box, with render and contract tests.
- Phase-2 web UI first slice (`kimcad web`): a dependency-free local browser app —
  describe → design plan → printability verdict → target-vs-actual dimensions → 3D preview
  — driven by the real pipeline. `--demo` serves a sample part with no model call.
- Deterministic code-generation repairs in the runner: missing library `use` includes are
  auto-injected, and a dropped trailing statement terminator is auto-added.
- Per-case benchmark artifact persistence (plan, report, outcome) for offline diagnosis.
- LLM resilience for a flaky local server: configurable per-request timeout, automatic
  retry on connection/timeout errors, and `scripts/ollama_watchdog.py`.
- Local CI: a pre-push hook (`.githooks/pre-push` → `scripts/ci.sh`) runs ruff + pytest.

#### Stage 1 — gated G-code export / print loop
- OrcaSlicer profile resolution: a configured printer + material maps to the three
  on-disk profile JSONs (machine / process / filament) under the shipped
  `resources/profiles` tree, with a `Generic <MATERIAL>` filament fallback. Replaces the
  former "known unknown" name→path placeholder.
- Slicing wired into the pipeline behind explicit print confirmation. `slice_model`
  now **proves** the exported 3MF carries real motion-bearing G-code (not just that a
  file was written), streaming the embedded toolpath to stay within the memory budget.
- CLI `--slice`: the explicit print confirmation. It announces the printer + material
  and the exact profiles to be used, then the report shows the proven G-code line count
  and the profiles actually used. Without `--slice`, nothing is sliced.
- Web send-to-printer: printer/material selectors (each flagged sliceable), an explicit
  confirmation step, `POST /api/slice/<id>` that slices the already-validated mesh (no
  model re-run), and `GET /api/gcode/<id>` to download the proven 3MF. The validated 3D
  model is always downloadable as the export fallback.
- Manifold3D pre-slice mesh hardening: the oriented mesh is round-tripped into a
  guaranteed 2-manifold before export/slice; optional at runtime (skipped, with a note,
  if `manifold3d` is absent). New dependency `manifold3d>=3.0` (installed by default; see
  the note at the top of this section).
- Bambu A1 printer profile added (one of Kim's printers).

#### Stage 2 — send-to-printer connector + MCP (software-complete, hardware-deferred)
- `PrinterConnector` abstraction (`printer_connector.py`): a `Protocol` covering
  capabilities / status / send / job-status, with a frozen `PrinterCapabilities` /
  `PrinterStatus` / `PrintJob` model and a shared `ensure_sendable()` gate. A built-in
  thread-safe `LoopbackConnector` (the **`mock`** connector) drives the whole send path
  in-memory, so every layer above can be tested with no hardware.
- OctoPrint connector (`octoprint_connector.py`): a real REST connector over stdlib
  `urllib` with an `X-Api-Key` header; the API key is read from an environment variable
  only — never stored in config and never logged. A reachable-but-rejected printer
  (401/403) surfaces as a distinct `AuthError`, not a generic "offline." Single-plate
  G-code is extracted with a hard size cap.
- Runnable mock OctoPrint server (`python -m kimcad.mock_printer`): a stdlib
  `http.server` implementing the version / printerprofiles / printer / files / job
  endpoints with API-key auth, so the OctoPrint connector is exercised end-to-end with
  no real printer.
- Capability reconciliation (`capability.py`): a printer's reported build volume /
  nozzle / materials auto-fills a **blank** profile field, and any config-vs-printer
  disagreement is flagged (config stays authoritative; the mismatch is surfaced, with the
  actual numbers, never silently overridden). A blank build-volume field now skips the
  build-plate-fit check with a `WARN` note (instead of failing); a blank nozzle skips the
  wall-thickness check (nothing to warn against, so no note).
- Connector config + factory: a `connectors:` block in `config/default.yaml`, a
  `build_connector(config, name)` factory, and clear errors for an unknown connector name,
  unknown type, or missing base-url / API-key env var (the factory names the missing env
  var, never its value).
- CLI `--send <connector>`: slices (the flag implies slicing) and sends behind the
  explicit-confirmation gate; an offline/unreachable printer is reported and the proven
  G-code is left on disk. A part that **failed** the printability gate is never sent — even
  with `--proceed-anyway`, which only exports it for inspection. A simulated (loopback)
  connection is labeled as such ("no real printer was used") rather than reported as a print.
- Web send-to-printer: after a successful slice, a connection selector + an explicit
  confirm step (`GET /api/connectors`, `POST /api/send/<id>`); the result surfaces the
  job + printer status, and the download stays as the fallback. Each connection is flagged
  `simulated` so the UI labels a no-hardware connection honestly (the confirm + success copy
  say plainly when a send is a simulation); a soft failure carries a typed `reason` plus a
  user-facing note (never the raw developer detail).
- Printer MCP server (`python -m kimcad.mcp_server`): a dependency-free MCP server
  (newline-delimited JSON-RPC 2.0 over stdio) exposing `list_connectors` /
  `printer_status` / `printer_capabilities` / `send_print`, so an agent can drive the
  printer. `send_print` passes the confirm value through to the same `confirm is True`
  gate without coercion — a truthy-but-not-`True` value cannot send.

#### Stage 3 — printer coverage + connector honesty (software-complete, hardware-deferred)
- Moonraker (Klipper) connector (`moonraker_connector.py`) + a runnable mock Moonraker server
  (`python -m kimcad.mock_moonraker`) — covers Creality-Klipper / Voron / RatRig / Mainsail /
  Fluidd. Optional `X-Api-Key`; an unrecognized Klipper state maps to `error`, never a false
  "ready."
- PrusaLink (Prusa) connector (`prusalink_connector.py`) + a mock PrusaLink server
  (`python -m kimcad.mock_prusalink`) — covers MK4 / MK3.9 / MINI / XL. Uploads via
  `PUT /api/v1/files/<storage>/<name>` with the path segments percent-encoded and
  `Print-After-Upload`; a 409 surfaces as a typed `busy`. Configurable `storage` (default `usb`).
- Per-printer, per-material filament profiles, honestly: every printer is offered only the
  materials it has a verified profile for. The cross-vendor `Generic <MATERIAL>` fallback was
  **removed** (it silently mis-resolved e.g. Elegoo + TPU to a Bambu profile); the Elegoo
  Neptune 4 Max genuinely ships no TPU profile, so TPU is reported "not available" for it.
  `/api/options` reports each printer's available materials, and the web UI explains which are
  hidden and why.
- Live **ready / not-ready connection status** (`GET /api/connector-status/<name>`): a badge for
  ready / busy / offline / needs-setup / simulation that never 5xxes and never leaks a credential.
- Connection-status + send **honesty hardening** (independent-audit gate fixes): a typed `reason`
  vocabulary (`config` / `unknown` / `auth` / `offline` / `busy` / `bad_response` / `error`)
  carried on both `/api/connector-status/<name>` and `/api/send/<id>` soft failures (each with a `simulated`
  flag); a rejected credential on a large upload is reported as `auth` rather than mislabeled
  "offline" (a mid-write socket reset is re-probed); a non-JSON HTTP-200 response degrades to an
  error status instead of raising; and the status line is an ARIA live region mapped onto the
  app's green/amber/red scale.

#### Stage 4 — React/TypeScript SPA shell + Three.js viewport + wired flow
- The browser UI is now a **React + TypeScript + Vite single-page app** (`frontend/`), compiled
  to plain static files committed under `src/kimcad/web/` and served by the same dependency-free
  stdlib `http.server` (shell at `/`, bundles at `/assets/<file>` behind the `/vendor/`-style
  traversal guard). **Node/Vite are build-time only** — `kimcad web` runs with no Node toolchain.
  This **replaces the earlier vanilla-HTML/JS page** (and that page's in-browser send controls).
- **Workshop design system** (the v3.0 design tokens) with self-hosted, latin-only variable fonts
  bundled for fully offline use (no CDN); a topbar + landing + a three-column workspace that
  stacks on mobile.
- A **vanilla Three.js viewport** (`KCViewport`) that loads and displays the REAL exported
  `*.oriented.stl` from `GET /api/mesh/<id>` (orbit / zoom / auto-rotate; three.js is code-split
  and lazy-loaded).
- The text → plan → gate → slice → download flow wired through the SPA: the conversation, the
  plan summary, the printability report (target-vs-actual dimensions + findings), printer/material
  selectors, gate-aware **Slice & prepare** (`POST /api/slice/<id>`), G-code + model download, and
  a **read-only** ready/not-ready connection badge.
- **Sending to a printer from the browser is intentionally deferred to a later stage** — the SPA
  does status + slice + download only; the CLI (`--send`) and the MCP server remain the send paths.
  (This supersedes the Stage-2 "Web send-to-printer" item above, which belonged to the now-removed
  vanilla UI.)
- Tooling/tests: a **vitest** unit harness for the SPA's pure logic (wired into `scripts/ci.sh`),
  frontend↔backend field-contract tests against the TypeScript source, and a build that the
  Python server-side tests gate (shell + `/assets/` serving + traversal rejection).

#### Stage 5 — deterministic template engine + live sliders
- **Deterministic template engine** (`templates.py`): a registry of seven parametric families
  (`snap_box`, `box`, `enclosure`, `tube`, `wall_hook`, `cable_clip`, `drawer_divider`) over the
  proven `library/` modules. A template-covered `object_type` builds **with no model call** — the
  OpenSCAD is emitted by pure, injection-safe string substitution and the gate target is the
  family's analytic bounding box. Typed, range-bounded parameters; values clamped to range with
  ordering constraints (a tube's bore stays inside its wall); alias/plural/case-normalized matching
  with a duplicate-alias guard. LLM-written OpenSCAD stays the fallback for uncovered types.
- **Pipeline tiering + the re-render path** (`pipeline.py`): a template match builds in one shot
  (no retry, no model — a too-wrong part fails closed, fixed by a parameter not by regenerating).
  `Pipeline.rerender(base_plan, family, values, …)` re-emits + renders + gates at new values with
  no model and no prompt, sharing the orient/harden/export tail with `run`.
- **Live re-render API** (`webapp.py`): `/api/design` now returns the `template` family name + the
  typed `parameters` snapshot; `POST /api/render/<id>` deterministically re-renders at new
  `{values}` (no model), returns the clamped values + a **versioned** (cache-busted) `mesh_url`,
  **invalidates** the cached slice/G-code for that id, and serializes concurrent re-renders — so a
  stale shape can never be sliced or sent.
- **Live parameter sliders in the SPA** (`RightPanel.tsx` et al.): a slider per backend parameter
  for template-backed designs; a drag updates immediately and debounces (~150 ms) a re-render, then
  the viewport reloads the versioned mesh while the previous one stays on screen and the
  gate/report/values update from server truth (a stale response can't clobber newer geometry).
  LLM-backed parts have no parameters and stay read-only. Sliders are labelled, mono-valued with
  units, and `aria-valuetext`-announced; the touch target fattens on mobile.
- **Deterministic-template benchmark/proof** (`template_bench.py`, `python -m kimcad.template_bench`):
  every family re-renders through the real pipeline path watertight at its declared envelope, with
  no model call, **well under the <1 s interactive target** (the automated gate asserts a
  conservative ≤5 s per-family ceiling so it stays hardware-independent; the exact per-family
  timings are in `docs/benchmarks/stage-5-template-families.md`).

#### Stage 7 — Smart Mesh + PrintProof3D + readiness report (merged + tagged `stage-7`)
- **Smart Mesh readiness synthesis** (`smart_mesh.py`): a pure `assess_readiness(gate, mesh_report,
  …, printproof=…)` that folds KimCad's Printability Gate, the mesh integrity stats, and an
  *optional* PrintProof3D report into one verdict — a 0–100 score, a plain verdict, a confidence,
  the risks, and concrete recommendations. The verdict tone is the **worst** of KimCad's own
  assessment and PrintProof3D's status, so the card is never more optimistic than either signal.
- **PrintProof3D arm's-length integration** (`printproof3d.py`): the owner's MIT Rust validation
  **engine** is run as a subprocess — never linked — to validate a rendered mesh; its
  `ValidationReport` JSON is parsed into a typed report Smart Mesh consumes. Best-effort and
  injection-safe: a missing/un-built engine, a profile error, or an unparseable report all degrade
  to "no engine" (Smart Mesh falls back to the gate, honestly at lower confidence) and **never
  raise**. KimCad generates the engine's printer/material profile JSON from its own config.
- **Pipeline + design-API wiring** (`pipeline.py`, `webapp.py`): every built part now carries a
  `MeshReadiness` (on the report, so both the completed and gate-failed paths expose it), computed
  on the final hardened mesh — **bed-positioned** on a copy before PrintProof3D validation. The
  deterministic slice gate is unchanged; readiness is advisory. `/api/design` + `/api/render`
  expose a `readiness` block; the live-slider re-render recomputes a fast gate-only readiness
  (the engine isn't re-run per drag).
- **Readiness report card** (`RightPanel.tsx`, matching the design at
  `docs/design/screens/10-smartmesh-report.png`): a designed card on the design screen — an SVG
  score gauge, the verdict, a confidence badge that names what backed it (gate vs engine), a risks
  list (with a non-color severity cue), a recommendations list, an optional history line, and an
  honest "via …" attribution. The Printability badge is reframed ("Gate: passed / needs review /
  failed") so it doesn't duplicate the readiness headline.
- **Smart Mesh learning store** (`history.py`): a local-first, best-effort JSON record of built
  parts (coarse — no geometry/prompt; default `~/.kimcad/history.json`, never the repo) that adds an
  honest "compared to your past parts" line to the card. Strictly factual — "a personal best" needs
  a strict beat of every prior, a tie reads "on par" not "below," and no history shows no line.
  Recorded once per fresh design, never on a slider drag.
- **Config:** optional `binaries.printproof3d` (the engine path; absent → degrade) and
  `paths.history` (relocate the learning store) — both documented in `config/default.yaml`.

### Changed
- Default local model is now `gemma4:e4b` (sized for a 32 GB / 780M-iGPU target — stable
  and fast there); `gemma3:12b` was too large for the target and is no longer used.
- Printability Gate: a non-watertight mesh is now a hard **fail** (previously detected but
  not gated), and the dimensional-match tolerance is a flat 0.5 mm with no percentage term.
- Design-plan and code-generation prompts steer the model to compose library modules and
  commit envelopes that match each module's documented bounding box.

### Fixed
- Code generation no longer misuses the walled-container `box()` module as a solid
  primitive; the system prompt and library manifest now steer plain solids to
  OpenSCAD built-ins, guarded by regression tests.
- Benchmark robustness: the planner no longer over-asks clarifications on already-sized
  parts, recoverable-but-invalid LLM JSON is normalized instead of crashing, and a
  dimensional failure is fed back to the model for a corrected attempt.
- Wall-hook envelope axis order made explicit (fixes an X/Y/Z swap); generated code may no
  longer assign geometry to a variable (an OpenSCAD syntax error).

### Notes
- The OrcaSlicer pin is v2.4.0-alpha, not 2.3.2 "stable": 2.3.2 is the only stable
  release carrying the Bambu P2S profile, but it segfaults on every CLI slice on a
  GPU-less machine (upstream issue #12906). 2.4.0-alpha fixes that and ships the same
  P2S profile, so it is pinned until a 2.4.x stable with the fix is released.
- Printer sliceability: all three of Kim's printers — Bambu P2S, Bambu A1, and Elegoo
  Neptune 4 Max — are fully sliceable (machine + process + filament profiles all ship)
  and proven end to end against the bundled OrcaSlicer. The Elegoo's process profiles
  ship under the name `Neptune4Max` (no spaces, nested under `process/EN4SERIES/`) while
  its machine profile uses `Neptune 4 Max` (with spaces); resolving the right name was
  the subtlety that an earlier (space-using) search missed.
