# Changelog

All notable changes to KimCad are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

> The project stays at `0.1.0` while pre-release; each stage is tagged as it lands.
> **Stage 1 (gated G-code export) tagged `stage-1` on 2026-05-30.**
> New runtime dependency this stage: **`manifold3d>=3.0`** — installed by default
> (a compiled wheel; relevant to the install footprint on the 32 GB target), though the
> *import* is optional at runtime (hardening is skipped with a note if it is absent).

### Added
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
