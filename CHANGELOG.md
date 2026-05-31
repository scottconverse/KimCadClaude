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
- Printer sliceability: the Bambu P2S and A1 are fully sliceable (machine + process +
  filament profiles all ship). The Elegoo Neptune 4 Max ships a machine + filament
  profile but **no process profile**, so it is selectable but not yet sliceable; slicing
  for it reports the gap cleanly and the validated model is still produced. Sourcing the
  Elegoo process profile is tracked in ROADMAP.
