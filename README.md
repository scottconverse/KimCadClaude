# KimCad

**AI-assisted parametric design for functional 3D prints.**

Describe a functional or mechanical part in plain English; KimCad turns it into a
printer-ready file through a conversation. An LLM writes parametric
[OpenSCAD](https://openscad.org/) code, OpenSCAD renders manifold geometry, a
validation-and-printability pipeline checks it against your printer and material,
and [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer) produces the output. No
CAD skills required, and the core path runs CPU-only — no discrete GPU.

> Status: **early development.** The deterministic pipeline, the gated G-code export
> (CLI `--slice` and the web UI), and Manifold3D mesh hardening are in. Real-hardware
> print validation on Kim's printers is the final stage — see ROADMAP.

## What it does

```
prompt → design plan (JSON) → OpenSCAD → render → mesh validation
       → Printability Gate → auto-orient → harden (Manifold3D)
       → [confirm] slice → validated print job + report
```

The engine is deterministic where it counts. Parametric CSG produces closed,
manifold geometry by construction, so output is dimensionally meaningful — not
lumpy neural meshes.

## Requirements

- Python 3.11+
- OpenSCAD 2021.01+ (built with `lib3mf` for 3MF export; STL is the fallback)
- OrcaSlicer (CLI)
- An LLM backend. KimCad is **local-first**: out of the box it talks to a local
  runtime ([Ollama](https://ollama.com/) or LM Studio), so no API key and no network
  are required. A cloud API (DeepSeek or any OpenAI-compatible endpoint) is an
  optional fallback you can opt into via `config/local.yaml`.

OpenSCAD and OrcaSlicer are fetched as pinned portable builds into `tools/` by the
setup step (see below); a system install can be pointed to via `config/local.yaml`.

## Setup

```
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
```

Then fetch the CAD/slicer binaries into `tools/` (standard library only — no extra
dependency):

```
python scripts/fetch_tools.py
```

On Windows this fetches both OpenSCAD and OrcaSlicer as verified, checksum-pinned
portable builds. The OrcaSlicer pin is **v2.4.0-alpha** on purpose: the 2.3.2
"stable" build is the only stable that carries the Bambu P2S profile, but it
crashes on every CLI slice on a GPU-less machine (upstream issue #12906), whereas
2.4.0-alpha handles that case and ships the same P2S profile. The macOS/Linux
builds are not yet verified (spec §7.5); install those manually and point
`config/local.yaml` at them.

Finally, pull the local model. KimCad defaults to [Ollama](https://ollama.com/) on
`localhost:11434`, running `gemma4:e4b` — a small (~4B-effective) model picked because
it fits the target machine (a 32 GB box with a 780M iGPU) and stays fast and stable
there:

```
ollama pull gemma4:e4b
```

That is all the LLM setup required — no API key, no network. To point at a different
local model or a cloud fallback (DeepSeek / any OpenAI-compatible endpoint), set the
active backend and its key in `config/local.yaml`; see `config/default.yaml` for the
shape and the pre-defined `cloud_deepseek` / `custom_openrouter` backends.

## Usage

A bare prompt is treated as the `design` verb:

```
kimcad "a wall hook with two M4 screw holes 30 mm apart and a 35 mm arm"
```

KimCad asks at most one clarifying question, then writes OpenSCAD, renders and
validates the mesh, runs the Printability Gate against your printer/material, orients
and hardens the part, and writes the validated model plus a plain-text report under
`output/`. Override defaults with `--printer`, `--material`, or `--backend` (keys come
from `config/default.yaml`).

Add `--slice` to also turn a gate-passing part into a printable G-code 3MF — this is
the explicit print confirmation, so nothing is sliced without it:

```
kimcad "a 40 mm cable clip" --printer bambu_a1 --material pla --slice
```

The report then names the exact OrcaSlicer machine/process/filament profiles used and
the proven G-code line count. Kim's Bambu P2S and A1 are fully sliceable; the Elegoo
Neptune 4 Max is selectable but not yet sliceable (the shipped OrcaSlicer has its
machine + filament profiles but no matching process profile — see ROADMAP), so a slice
for it reports that cleanly and the validated model is still produced.

### Web UI (Phase 2, early)

For a browser experience instead of the CLI:

```
kimcad web
```

This serves a local page at `http://127.0.0.1:8765` where you describe a part and get
back the design plan, the printability verdict, the target-vs-actual dimensions, and a
3D preview of the rendered model — the same pipeline as the CLI, driven from the
browser. Use `--demo` to serve a fixed sample part instantly with no model call (handy
for trying the interface), and `--port` to change the port.

The server binds to `127.0.0.1` (your machine only) by default. `--host` can bind it
elsewhere, but do **not** expose it on a public interface without putting your own
authentication/proxy in front — it runs the pipeline for anyone who can reach it.

Once a part passes the gate you can pick a printer + material and, after an explicit
confirmation, generate a printable G-code 3MF and download it — slicing runs on the
already-validated mesh, so confirming a print never re-runs the model. The validated
3D model itself is always downloadable as the export fallback, including for printers
that can't yet produce G-code.

### The done-gate

Phase 1 is judged by a fixed benchmark — the ten Appendix B prompts in
`bench/prompts.yaml`. The gate passes at 8 / 10 dimensionally-correct, sliceable
results:

```
kimcad bench --min-success-rate 0.8
```

It exits non-zero when the batch misses the threshold, so it doubles as a CI check.

### Local development checks

Lint and tests run locally as a pre-push gate (handy when GitHub-hosted CI minutes
aren't available). Enable the hook once per clone:

```
git config core.hooksPath .githooks
```

After that, every `git push` runs `scripts/ci.sh` (ruff + pytest) and blocks the push
if anything fails. The same checks are defined for hosted CI in
`.github/workflows/ci.yml` for when Actions minutes are available.

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
