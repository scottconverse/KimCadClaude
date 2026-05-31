# Changelog

All notable changes to KimCad are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

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
- OpenSCAD code-generation system prompt and a five-module seed library
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
- Parametric library expansion — eight new modules covering the Appendix-B part families
  that previously had to be hand-built: wall and pegboard hooks, cable clip, closed box /
  two-part enclosure / tube, spool holder, and drawer divider. Each renders watertight at
  an exact, documented bounding box, with render and contract tests.
- Phase-2 web UI first slice (`kimcad web`): a dependency-free local browser app —
  describe → design plan → printability verdict → target-vs-actual dimensions → 3D preview
  — driven by the real pipeline. `--demo` serves a sample part with no model call.
- Deterministic code-generation repairs in the runner: missing library `use` includes are
  auto-injected, and a dropped trailing statement terminator is auto-added.
- Per-case benchmark artifact persistence (plan, report, outcome) for offline diagnosis.
- LLM resilience for a flaky local server: configurable per-request timeout, automatic
  retry on connection/timeout errors, and `scripts/ollama_watchdog.py`.
- Local CI: a pre-push hook (`.githooks/pre-push` → `scripts/ci.sh`) runs ruff + pytest.

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
