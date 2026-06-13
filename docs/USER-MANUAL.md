# KimCad — User Manual

**AI-assisted parametric design for functional 3D prints.**
Describe a part in plain words — or photograph or sketch one — and KimCad turns it into a
checked, print-ready file, entirely on your own machine.

This manual has three parts, each for a different reader. Start wherever you fit:

| Part | For | Covers |
|---|---|---|
| **[1 · Everyday use](#part-1--everyday-use)** | anyone who wants to make a part | install, the three ways to start, refining, checking, printing |
| **[2 · The technical surface](#part-2--the-technical-surface)** | CLI users, tinkerers, integrators | commands, config, connectors, the MCP server, the CadQuery engine |
| **[3 · Architecture](#part-3--architecture)** | developers and the curious | the pipeline, the modules, the trust boundaries, how it's built |

> **Version:** this manual tracks the `0.9.0b1` Windows beta. KimCad's version shows in
> **Settings → About** and from `kimcad --version`.

---

# Part 1 · Everyday use

## What KimCad is (and isn't)

KimCad turns a description of a *functional* part — a bracket, a holder, a clip, an
enclosure — into a 3D-printable file. You don't draw anything and you never edit CAD code.

It is **deterministic where it counts**: common shapes are built by a parametric template
engine, not guessed by a neural network, so the geometry is solid, watertight, and
dimensionally meaningful. Everything runs **on your computer** — no account, no internet
required, and nothing you type, photograph, or sketch leaves the machine unless you
explicitly turn on the optional cloud feature.

KimCad is best at single mechanical parts. It is *not* a freeform artistic modeler and not
a multi-part assembly tool.

## Installing (Windows)

The easiest path is the **double-click installer** — no terminal, no Python, no developer
tools.

1. Download `KimCad-Setup-<version>.exe` from the
   [releases page](../../releases/latest).
2. Double-click it. Windows SmartScreen will warn you because the beta isn't code-signed —
   click **More info → Run anyway**. (You can verify the download first: the release
   publishes a `.sha256` checksum beside the installer.)
3. Follow the wizard. KimCad installs to Program Files by default (or a per-user folder if
   you install without administrator rights).

Full details, including the checksum check and exactly what goes where, are in the
**[install guide](install-guide.md)**.

**Requirements:** Windows 11 (or Windows 10 with the WebView2 Runtime, which Edge installs
automatically, plus .NET Framework 4.7.2+, in-box since Windows 10 1803), about 20 GB free
disk (mostly the AI models), 16 GB+ RAM recommended. **No graphics card needed.**

> Prefer to run from source? See the [README's Setup section](../README.md#setup).

## First run

Launch KimCad from the Start-Menu shortcut. A setup wizard walks you through three things:

1. **The AI.** KimCad's design intelligence runs locally through **Ollama** (free). If you
   don't have Ollama, the wizard's **Get Ollama** button takes you to the download; install
   it and click *check again*. Then the wizard's **Download now** button fetches KimCad's
   two AI models (about 13 GB total) with a progress bar. Designing in words works the
   moment the first one finishes.
2. **Your printer.** Pick the printer your parts will be checked and sliced against. You can
   change it any time in Settings.
3. **Direct printing** (optional). You can always download a file; connecting a printer to
   send jobs directly is set up later, in Settings.

If you skip setup, nothing is lost — you can reopen the wizard any time from **Settings →
Run the setup walkthrough again**.

## The three ways to start a design

KimCad gives you three on-ramps on the start page. **Words are the primary path**; photos
and sketches are shortcuts that produce an editable starting description.

### 1. Describe it in words

Type what you want, in plain language, and press **Design it** (or Enter):

> *a wall hook with two M4 screw holes 30 mm apart and a 35 mm arm*

Be specific about the numbers that matter — sizes, hole diameters, spacings. KimCad may ask
one clarifying question, then builds the part.

### 2. Start from a photo

Click **Describe with a photo** (or drop an image on it). KimCad's local vision model reads
the photo into a rough, editable description — *"a cylindrical cup about 80 mm tall and
70 mm across."* **A photo can't tell scale**, so the sizes are estimates; fix anything
that's off before you continue. The photo is read on your machine and never saved.

### 3. Start from a sketch

Click **Start from a sketch**. Unlike a photo, a dimensioned sketch **carries its sizes** —
write "80 mm", "40 × 20 × 10 mm" on the drawing and KimCad reads them as written. A good
sketch is one part per page, dark lines on a light background, dimensions labeled with
units. Check the numbers came through before continuing.

Full details: **[Starting from a photo or sketch](guide-photo-onramp.md)**.

## Browse the part library

Not sure what to type? KimCad comes with a **library of ready-made parts** — about 90 of them
— that you can browse instead of describing one from scratch. Open it from the start page,
search by what you're after (*"tray"*, *"hook"*, *"planter"*, *"spacer"*), and pick the card
that fits. KimCad designs it for you on the spot, then you shape it with the sliders just like
any other part. There's everything from boxes, hooks, and brackets to picture frames, trinket
dishes, plant pots, ornaments, candle holders, display stands, and everyday hardware like
washers and standoffs.

You don't *have* to use the library — describing a part in your own words works just as well,
and KimCad can design plenty of things that aren't in the library. Think of it as a starting
shelf, not a fence.

### What the "Verify before use" tag means

Most library parts are exactly what you set — change a number, get that number, no surprises.
A few carry a small **Verify before use** tag. That isn't a warning that the part is broken;
the shape is just as real and just as checked as any other. The tag means the part has to *fit
something in the real world* — a screw, a glass tube, a phone, a Gridfinity drawer, a monitor's
mounting holes — or carry a load, and only you can confirm that fit. For example, the printed
"nut" and "bolt" have a smooth hole and shaft rather than real cut threads, and a "VESA plate"
gives you the standard hole pattern to line up with your own device. So when you see the tag,
just measure twice, or print a quick test, before you rely on it. Everything else in the
library has no tag because there's nothing extra to check.

(For the complete list of every part, its tag, and what it does, see the
**[part-library catalog](templates.md)**.)

## Refining a part

Once a part appears, you refine it by **talking** — there's no mode switch. In the
conversation panel, tap a quick change (*Make it bigger*, *Thicker walls*) or type your own:

> *make it 10 mm taller* · *add a 5 mm fillet on the top edge* · *move the holes 5 mm apart*

Each change creates a new **version** you can step back to. For template-backed parts you
also get **live sliders**: drag a dimension and the part re-renders **locally in under a
second**, with no AI call. You can type exact numbers, and switch the whole app between
**mm and inches** at will.

## The 3D preview and the printability check

The preview is the **real, gated mesh** — the exact geometry that will be sliced, not a
stand-in. Drag to orbit, scroll to zoom, right-click-drag to pan. Size pills and an
orientation chip update as you turn it, so you can sanity-check the part on the bed.

Every part gets a **Smart Mesh readiness** card: a 0–100 score, a plain verdict, the risks
(overhangs, thin walls, poor bed contact), and concrete recommendations. In the installed
beta this is backed by the bundled **PrintProof3D** validation engine, which adds real
overhang/bridge/bed-adhesion analysis on top of KimCad's own Printability Gate. The card
shows its **confidence** honestly and never claims an analysis ran when it didn't.

The **Printability Gate** is the authority: a part that fails it (too big for the printer,
un-manifold, walls too thin) **cannot be sliced or sent** — you can still download the model
to inspect it, but KimCad won't pretend it's printable.

## Getting your part out

When a part passes the gate, you can:

- **Download the print file.** Pick your printer and material, confirm, and KimCad slices the
  validated mesh into a printer-ready `.gcode.3mf` with a plain-English estimate (time,
  layers, filament length + weight). The model itself is always downloadable too: `.STL` for
  every part, plus an editable `.STEP` for standard (template-built) parts when the optional
  CAD export engine is installed (Settings → Editable CAD export).
- **Send it straight to a printer.** If you've set up a printer connection (Settings →
  Printer connections), send the sliced job directly: pick the connection, confirm in
  KimCad's own dialog (it never auto-starts a print), and watch the live status. A built-in
  **test connection** (`mock`) proves the whole send path without any hardware.

> **Beta status:** connections are validated against the printers' real software protocols
> but **not yet on physical hardware** — that's the beta's job. See
> [supported printers](supported-printers.md).

## My Designs, Settings, and privacy

- **My Designs** keeps every part automatically, on your machine, under `~/.kimcad/designs/`.
  Reopen, rename, duplicate, delete, or **export** a design as a portable `.kimcad` file (a
  backup, not a printable STL). A refresh or coming back tomorrow restores your work.
  ([guide](guide-my-designs.md))
- **Settings** holds your default printer and material, units, the AI-model health, the
  printer connections, and the optional cloud feature.
  ([guide](guide-settings-and-cloud.md))
- **Privacy:** everything is local-first. The one exception is **Cloud acceleration** (off by
  default) — if you turn it on and add an OpenRouter key, your *text* design prompts can be
  sent to a cloud model for hard requests. **Your photos and sketches always stay local**,
  read by the on-device vision model, even with cloud on. Your cloud key is kept in the
  Windows Credential Manager and shown only masked.

## When something goes wrong

**[Troubleshooting](troubleshooting.md)** is symptom-first and covers every known snag — the
AI not running, a model not downloaded, the app window not opening, SmartScreen, where your
files live, and more.

---

# Part 2 · The technical surface

This part assumes you're comfortable with a terminal. Everything here also works from a
source checkout (see the [README Setup](../README.md#setup)); the installed app bundles it
all.

## The command line

A bare prompt is the `design` verb:

```
kimcad "a 40 mm cable clip"
```

KimCad writes OpenSCAD, renders and validates the mesh, runs the Printability Gate, orients
and hardens the part, and writes the model plus a plain-text report under `output/`.

| Command | What it does |
|---|---|
| `kimcad design "<prompt>"` | design a part. Flags: `--printer`, `--material`, `--backend`, `--out`, `--slice`, `--send <connector>`, `--proceed-anyway` |
| `kimcad web [--port N] [--demo]` | the browser UI on `http://127.0.0.1:8765` (loopback only) |
| `kimcad shell [--demo]` | the **windowed app** (WebView2) — what the installer's shortcut runs |
| `kimcad models` | examine your hardware + installed models and recommend one (advisory only) |
| `kimcad bench [--min-success-rate R]` | run the 10-prompt benchmark (the done-gate; exits non-zero below the threshold) |
| `kimcad bakeoff --backends a,b` | compare two model backends on the benchmark |
| `kimcad --version` | the single-sourced version string |

`--slice` is the **explicit print confirmation** — only with it does a gate-passing part
become a printable `.gcode.3mf`:

```
kimcad "a 40 mm cable clip" --printer bambu_a1 --material pla --slice
```

The report then names the exact OrcaSlicer machine/process/filament profiles and the proven
G-code line count.

## Configuration

Config is layered: shipped defaults in `config/default.yaml`, your overrides in
`config/local.yaml` (a relative path resolves against the project root in dev; in the
installed app it lives under `%LOCALAPPDATA%\KimCad`). Override the model, printers,
materials, binary paths, and connectors there. Run `kimcad models` for a hardware-matched
model recommendation — it only advises, it never edits your config.

**The AI model.** KimCad defaults to **Ollama** on `localhost:11434` running `gemma4:e4b`
for design and `qwen2.5vl:3b` for reading photos/sketches. Both are local; images never
leave the machine. To use a different local model or a cloud backend, set the active backend
in `config/local.yaml`.

**Cloud (optional, off by default).** Turn on Cloud acceleration in Settings (or configure a
cloud backend in files) to route *text* prompts through [OpenRouter](https://openrouter.ai/)
or any OpenAI-compatible endpoint. The key is read from the OS credential store (or a
disclosed file fallback) and never logged. Verify the cloud model name against your
provider's current list before relying on it.

## Printers and direct send

A sliced job can be sent to a **printer connection** through a swappable connector. Every
send requires explicit confirmation and refuses anything that isn't a proven slice.

| Connector | Printers | Config |
|---|---|---|
| `loopback` | the built-in `mock` test connection | — |
| `bambu` | Bambu Lab P2S / A1 (native LAN) | `base_url` (IP), `serial`, access-code env var, `use_ams` |
| `octoprint` | any OctoPrint host | `base_url`, `api_key_env` |
| `moonraker` | Klipper (Voron, Creality-Klipper, …) | `base_url`, optional `api_key_env` |
| `prusalink` | Prusa MK4 / MK3.9 / MINI / XL | `base_url`, `api_key_env`, optional `storage` |

Credentials are **always** read from an environment variable (named by `api_key_env`), never
stored in config and never logged. The shipped `bambu_p2s`, `bambu_a1`, `moonraker`, and
`prusalink` entries are visible fill-in templates — set them up in **Settings → Printer
connections** (fields + the env-var name with a `setx` line), or edit `config/default.yaml`.

Send from the CLI (`--send <connector>`), the web/app UI (pick → confirm → live status), or
an agent over MCP. Each connector has a **runnable mock server** for offline testing:
`python -m kimcad.mock_printer` (OctoPrint), `mock_moonraker`, `mock_prusalink`. Full matrix
and validation status: **[supported printers](supported-printers.md)**.

**Response reasons.** A send or status check carries a typed `reason` (`config`, `unknown`,
`offline`, `busy`, `auth`, `gate_failed`, `bad_response`, `error`) plus a plain `note`, so
UI/API consumers branch on *why* rather than on message text.

## The MCP server (agent integration)

```
python -m kimcad.mcp_server
```

exposes the printer as MCP tools — list connections, status, capabilities, and a
confirmation-gated `send_print` — so an agent can drive KimCad. The same confirm-and-prove
rules apply: nothing prints without explicit confirmation and a real slice.

## The CadQuery engine (editable `.STEP` CAD export)

With [CadQuery](https://cadquery.readthedocs.io/) installed, every **template-built part**
also offers an **editable `.STEP`** download — the precision CAD model, which opens in
Fusion 360, FreeCAD, SolidWorks and the like so you can keep modeling. KimCad builds it from
its **own trusted CadQuery twin** of the template (never AI-written code), lazily on the
first download, always matching the live slider values.

It's entirely optional, and the app walks you through it: **Settings → Editable CAD
export** shows whether the engine is installed and the one-time setup
(`py -3.13 -m pip install cadquery`, then *check again* — KimCad finds it automatically).
The worker runs in a separate interpreter (arm's-length, like OpenSCAD/OrcaSlicer). Pin or
disable it via `binaries.cadquery_python` in `config/local.yaml`. Details:
**[cadquery-backend.md](cadquery-backend.md)**.

> The installed beta does **not** bundle CadQuery — the engine is the one opt-in piece, and
> nothing else changes without it. (Stage 8's LLM-CadQuery *fallback generator* was removed
> after its measured lift came in at 0 — no AI-written Python ever runs anymore.)

## The benchmark (the done-gate)

```
kimcad bench --min-success-rate 0.8
```

runs the ten Appendix B prompts in `bench/prompts.yaml` and passes at 8/10
dimensionally-correct, sliceable results. It exits non-zero below the threshold, so it
doubles as a CI check. `kimcad bakeoff --backends <a>,<b>` runs the benchmark once per
backend and recommends whether to switch — it only recommends; flipping the default is a
manual choice.

---

# Part 3 · Architecture

KimCad's design bet, preserved from the v3.0 spec: **deterministic CSG geometry,
local-first, the UX as a gate.** Parametric construction produces closed, manifold geometry
by construction — dimensionally meaningful output, not lumpy neural meshes — and every
quality claim is something the code can prove.

## The pipeline

```
prompt → DesignPlan (validated JSON) → OpenSCAD / CadQuery → render → mesh validation
       → Printability Gate → auto-orient → harden (Manifold3D)
       → Smart Mesh readiness → [confirm] slice (OrcaSlicer) → validated job + report
```

1. **DesignPlan.** The LLM produces a structured plan (Pydantic-validated IR), not raw
   geometry. For common shapes a **deterministic template engine** (`templates.py`, **86
   parametric families** — see the [part-library catalog](templates.md)) emits OpenSCAD
   directly — no model — which is why live-slider re-renders take under a second. Each family
   is tier-labeled (*benchmarked* vs *baseline*) and render-verified against its analytic
   bounding box. For anything off-template, the LLM writes OpenSCAD (or, on the parallel path,
   CadQuery).
2. **Render.** OpenSCAD renders manifold geometry; `cadquery_runner` shells out to a
   sandboxed worker for the parallel backend. Both return the same `RenderResult`, so the
   tail is backend-agnostic.
3. **Validate.** The mesh is loaded, checked for watertightness, and conservatively repaired.
4. **The Printability Gate** — pass / warn / fail with reasons: a NaN/inf-safe dimensional
   check against the printer envelope, wall-thickness against the nozzle, and more. **This is
   the slice authority**; nothing past it is advisory.
5. **Orient & harden.** Auto-orientation finds a stable resting pose; Manifold3D guarantees a
   2-manifold mesh before slicing.
6. **Smart Mesh readiness** layers the arm's-length **PrintProof3D** engine (when present)
   over the gate for a confidence-scored report.
7. **Slice** (only on explicit confirmation) runs the real OrcaSlicer CLI on the
   already-validated mesh — confirming a print never re-runs the model.

## Module map (orientation)

| Module | Responsibility |
|---|---|
| `ir.py` | the DesignPlan IR — validates LLM JSON before any geometry is written |
| `templates.py` | the deterministic template engine (the quality moat) |
| `llm_provider.py` | all LLM communication (local Ollama / cloud), plan + codegen + the local vision read |
| `openscad_runner.py` / `cadquery_runner.py` | sanitize-and-render; the trust boundary for generated code |
| `validation.py` / `printability.py` / `orientation.py` / `hardening.py` | the validation → gate → orient → harden stack |
| `slicer.py` | the OrcaSlicer CLI integration |
| `pipeline.py` | the orchestrator that wires it all and builds the report |
| `printer_connector.py` + `*_connector.py` | the send abstraction + leaf connectors (incl. `bambu_connector.py`) |
| `webapp.py` / `shell.py` | the local web layer and the WebView2 app window |
| `design_registry.py` | per-design server state + its locking protocols |
| `paths.py` | the dev↔installed path seam (read root vs writable root) |
| `model_pull.py` | in-app model downloads with progress |
| `mcp_server.py` | the agent-facing MCP surface |

## Trust boundaries

- **Generated code is untrusted.** OpenSCAD source and CadQuery scripts are statically
  sanitized (an `ast` block-list, not a strip, so valid geometry is never mangled) and run in
  separate processes — CadQuery additionally behind a geometry-only facade with restricted
  builtins and env/cwd isolation.
- **The web server is loopback-only** by default; binding elsewhere requires an explicit
  `--allow-remote` and a warning, because the server is unauthenticated by design (one
  trusted local user).
- **Secrets never touch disk or logs.** The cloud key lives in the OS credential store (with
  a disclosed file fallback); connector credentials live in environment variables; the
  subprocess environment is scrubbed before any tool runs.
- **Vision stays local.** The photo/sketch read is structurally pinned to a loopback host —
  an image is refused before it can leave the process.
- **Prints require proof + confirmation.** A connector refuses anything that isn't a
  motion-bearing slice, and never starts a job without an explicit `confirm`.

## The installed layout (the paths seam)

In a dev checkout everything lives under the repo root. The installer ships a different
shape, and `paths.py` is the single switch between them (set by the launcher's
`KIMCAD_INSTALL_ROOT`): **reads** (config templates, the bundled tools, the SPA) come from
the read-only install dir; **writes** (design output, the app's browser profile) go to
`%LOCALAPPDATA%\KimCad`; user designs and settings stay in `~/.kimcad`. The installer bundles
an embeddable CPython 3.13, the app + its pinned dependencies, the committed SPA, OpenSCAD,
OrcaSlicer, and the PrintProof3D engine — pinned by SHA-256 and proven by an automated
staging smoke (`verify_install.py`) on every push.

## How it's verified

One authoritative gate, `scripts/ci.sh`, runs identically in the pre-push hook and on the
self-hosted CI runner: `ruff`, the full `pytest` suite (including the **live** OrcaSlicer
slice and the CadQuery sandbox tests), the frontend **Vitest** suite, a committed-SPA
build-reproducibility check, and the installer-staging smoke. Every build stage passed a
multi-role audit at zero findings across all severities before it was tagged; the audit trail
lives under [`docs/audits/`](audits/). The design rationale is in
[ARCHITECTURE.md](../ARCHITECTURE.md) and the v3.0 spec under
[`docs/design/`](design/).

---

*KimCad is open source under Apache-2.0. Questions and ideas:
[Discussions](../../discussions). The road ahead: [ROADMAP.md](../ROADMAP.md).*
