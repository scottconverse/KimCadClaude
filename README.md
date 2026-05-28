# KimCad

**AI-assisted parametric design for functional 3D prints.**

Describe a functional or mechanical part in plain English; KimCad turns it into a
printer-ready file through a conversation. An LLM writes parametric
[OpenSCAD](https://openscad.org/) code, OpenSCAD renders manifold geometry, a
validation-and-printability pipeline checks it against your printer and material,
and [OrcaSlicer](https://github.com/SoftFever/OrcaSlicer) produces the output. No
CAD skills required, and the core path runs CPU-only — no discrete GPU.

> Status: **early development (Phase 1).** CLI-first; the web UI lands in Phase 2.

## What it does

```
prompt → design plan (JSON) → OpenSCAD → render → mesh validation
       → Printability Gate → auto-orient → slice → validated print job + report
```

The engine is deterministic where it counts. Parametric CSG produces closed,
manifold geometry by construction, so output is dimensionally meaningful — not
lumpy neural meshes.

## Requirements

- Python 3.11+
- OpenSCAD 2021.01+ (built with `lib3mf` for 3MF export; STL is the fallback)
- OrcaSlicer (CLI)
- An LLM backend: a cloud API key (DeepSeek recommended) **or** a local runtime
  (Ollama / LM Studio) for offline use.

OpenSCAD and OrcaSlicer are fetched as pinned portable builds into `tools/` by the
setup step (see below); a system install can be pointed to via `config/local.yaml`.

## Setup

```
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

Then fetch the CAD/slicer binaries (script lands with Task #2) and set your API key:

```
# Windows (PowerShell):  $env:DEEPSEEK_API_KEY = "sk-..."
# macOS/Linux:  export DEEPSEEK_API_KEY="sk-..."
```

## Platform notes

| | Windows | macOS | Linux |
|---|---|---|---|
| Python | 3.11+ | 3.11+ | 3.11+ |
| OpenSCAD | portable `.zip` in `tools/` | `.app` payload | AppImage |
| OrcaSlicer | portable `.zip` in `tools/` | `.app` payload | AppImage |

## License

Core: Apache-2.0. Bundled OpenSCAD (GPL-2.0) and OrcaSlicer (AGPL-3.0) are invoked
as separate subprocesses, never linked — see the spec's licensing section.

## Project layout

```
src/kimcad/      application package
library/         seed OpenSCAD module library (the quality moat)
config/          default + local configuration
bench/           benchmark harness (the Phase-1 done-gate)
tests/           unit + integration tests
tools/           fetched OpenSCAD + OrcaSlicer binaries (gitignored)
```
