# KimCad — User Manual

**AI-assisted parametric design for functional 3D prints.**
Describe a part in plain words — or photograph or sketch one — and KimCad turns it into a
checked, print-ready file, entirely on your own machine.

This manual has three parts, each for a different reader. Start wherever you fit:

| Part | For | Covers |
|---|---|---|
| **[1 · Everyday use](#part-1--everyday-use)** | anyone who wants to make a part | install, the three ways to start, refining, checking, printing, a glossary, and what to do when things go wrong |
| **[2 · The technical surface](#part-2--the-technical-surface)** | CLI users, tinkerers, integrators | commands, config layering, the printer connectors, the MCP server, the CadQuery/STEP engine |
| **[3 · Architecture](#part-3--architecture)** | developers and the curious | the pipeline, the modules, the trust boundaries, how it's built |

> **Version:** this manual tracks the current Windows beta (`0.9.3`). KimCad's version shows in
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

## Installing

### Windows — the double-click installer (no terminal)

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
automatically, plus .NET Framework 4.7.2+, in-box since Windows 10 1803), about 12 GB free
disk as headroom (the AI engine ~1.4 GB plus the ~7.7 GB of models, with room to spare),
16 GB+ RAM recommended. **No graphics card needed.**

### macOS and Linux — run from source

The zero-terminal installer is **Windows-only for now**. On **macOS and Linux you run KimCad
from source** today: install the package and launch the browser UI with `kimcad web` (full
steps are in [Part 2 → From a source checkout](#from-a-source-checkout-all-platforms) and the
[README Setup section](../README.md#setup)). You install OpenSCAD and OrcaSlicer yourself and
point `config/local.yaml` at them — only rendering and slicing need them; the UI itself runs
without. Your saved designs and settings land in the platform-idiomatic spot
(`~/Library/Application Support/KimCad` on macOS, `$XDG_DATA_HOME` / `~/.local/share/KimCad`
on Linux).

> The cross-platform from-source path is code-verified (guarded imports, the cross-platform
> test design) but **not yet exercised on real Mac/Linux hardware** — the dev box is Windows.
> Zero-terminal installers for macOS/Linux are scoped and deferred to a post-beta packaging
> lane.

## First run

Launch KimCad from the Start-Menu shortcut (Windows) or with `kimcad web` (Mac/Linux). A
setup wizard walks you through three things:

1. **The AI.** KimCad's design intelligence runs locally through **Ollama** (free) — and
   KimCad **sets that up for you**. The wizard's **Set up KimCad's AI** button does it in one
   flow: if you already have Ollama it uses it automatically; otherwise it downloads Ollama's
   official **portable** build (~1.4 GB, a one-time engine download — no separate install, no
   system tray, no admin) into KimCad's own data folder and runs it headless. It then fetches
   KimCad's two AI models (about 7.7 GB total) with a progress bar. Designing in words works
   the moment the first model finishes. The two models are **`qwen2.5:7b`** (the design
   planner) and **`qwen2.5vl:3b`** (the photo/sketch reader); both run **fully offline**.
   *(Already have Ollama? It's used automatically. If automatic setup ever fails — e.g.
   you're offline — you can install Ollama from [ollama.com](https://ollama.com/) and click
   **Check again**.)*
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

Not sure what to type? KimCad comes with a **library of ready-made parts** — **86 of them** —
that you can browse instead of describing one from scratch. Open it from the start page,
search by what you're after (*"tray"*, *"hook"*, *"planter"*, *"spacer"*), and pick the card
that fits. KimCad designs it for you on the spot, then you shape it with the sliders just like
any other part. There's everything from boxes, hooks, and brackets to picture frames, trinket
dishes, plant pots, ornaments, candle holders, display stands, and everyday hardware like
washers and standoffs.

You don't *have* to use the library — describing a part in your own words works just as well,
and KimCad can design plenty of things that aren't in the library. Think of it as a starting
shelf, not a fence.

### What the "Verify before use" tag means

Most library parts are exactly what you set — change a number, get that number, no surprises
(the library calls these **benchmarked**). A few carry a small **Verify before use** tag (the
**baseline** tier). That isn't a warning that the part is broken; the shape is just as real
and just as checked as any other. The tag means the part has to *fit something in the real
world* — a screw, a glass tube, a phone, a Gridfinity drawer, a monitor's mounting holes — or
carry a load, and only you can confirm that fit. For example, the printed "nut" and "bolt"
have a smooth hole and shaft rather than real cut threads, and a "VESA plate" gives you the
standard hole pattern to line up with your own device. So when you see the tag, just measure
twice, or print a quick test, before you rely on it. Everything else in the library has no tag
because there's nothing extra to check.

(For the complete list of every part, its tag, and what it does, see the
**[part-library catalog](templates.md)** — all 86 families, 39 benchmarked and 47 baseline.)

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
shows its **confidence** honestly — **High** when the engine ran and returned a usable
report, **Medium** on the gate alone, **Low** when the engine ran but couldn't fully analyse
the mesh — and never claims an analysis ran when it didn't.

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

KimCad's picker offers a **curated catalog of ~29 popular current machines** across the top
makers (Bambu, Creality, Prusa, Anycubic, Elegoo, Qidi, Sovol), each build-volume-checked and
slice-proven, on top of the full ~1,400-profile OrcaSlicer library on disk. Direct send today
covers six connection types — Bambu native LAN, OctoPrint, Moonraker (Klipper), PrusaLink,
and the new **Duet** and **Marlin** connectors.

> **Beta status:** connections are validated against the printers' real software protocols
> (against a faithful conformance mock) but **not yet on physical hardware** — that's the
> beta's job. See [supported printers](supported-printers.md).

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
  Windows Credential Manager (or the OS credential store) and shown only masked.

## Glossary — the words KimCad uses

Plain-language definitions of the recurring terms in this manual and on screen.

| Term | What it means |
|---|---|
| **manifold** | A "watertight" solid — a mesh with no holes, gaps, or self-intersections, so it has a real inside and outside. Only manifold parts slice cleanly; KimCad guarantees this before slicing. |
| **mesh** | The triangle skin that describes a 3D shape. The preview and the slicer both work on the mesh. |
| **fillet** | A rounded internal/external edge (the opposite of a sharp corner). "Add a 5 mm fillet" rounds an edge to a 5 mm radius — stronger and nicer to handle. |
| **chamfer** | A flat, angled cut across a corner (a bevel), versus a fillet's curve. |
| **overhang** | Part of the print that leans out past what's below it. Steep overhangs (past ~45°) droop without support; KimCad's readiness card flags them. |
| **bridge** | A flat span of plastic printed across open air between two supports (e.g. the top of a doorway). Long bridges can sag; the readiness card flags them. |
| **bed adhesion** | How well the first layer sticks to the printer bed. Too little bed contact and the print pops loose; the readiness card scores it. |
| **wall thickness** | How thick a wall is. Walls thinner than the nozzle can lay down won't print solidly; the Printability Gate checks this against your nozzle. |
| **the (Printability) Gate** | KimCad's pass/warn/fail check that decides whether a part is printable on *your* printer. A failed part cannot be sliced or sent — it's the authority, not advice. |
| **slice / slicer** | Converting a 3D model into the layer-by-layer toolpath a printer actually follows. KimCad slices with OrcaSlicer. The output is the print file. |
| **G-code** | The plain-text motion language a printer executes (move here, extrude this much). The end product of slicing. |
| **`.gcode.3mf`** | KimCad's print-ready output: G-code wrapped in a 3MF container (the modern print package). This is what you download or send. |
| **`.STL`** | A universal 3D-model file (just the mesh, no editability). Always downloadable for every part. |
| **`.STEP`** | A precision, *editable* CAD model you can reopen in Fusion 360 / FreeCAD / SolidWorks. Offered for template parts when the optional CadQuery engine is installed. |
| **`.kimcad`** | KimCad's own portable design backup (re-importable on another machine) — *not* a printable file. |
| **AMS** | Bambu's Automatic Material System — the multi-spool unit that auto-feeds filament. The Bambu connector has a `use_ams` option. |
| **Ollama** | The free local AI runtime KimCad talks to. It hosts the two models on your machine; nothing leaves the computer. |
| **manifold (the verb) / harden** | The final "make it watertight" step (using the Manifold3D library) that guarantees a 2-manifold mesh before slicing. |

## When something goes wrong

A symptom-first list of the most common snags. The full, exhaustive version is
**[Troubleshooting](troubleshooting.md)**.

| What you see | What to do |
|---|---|
| **"Windows protected your PC" (SmartScreen)** at install | Expected — the beta isn't code-signed. Click **More info → Run anyway**. You can verify the `.sha256` checksum from the release first if you like. |
| **The setup wizard can't find the AI** | Press **Set up KimCad's AI** — KimCad provisions and starts its own engine (reusing a system Ollama if one is present, else downloading the portable build), then **Check again**. If automatic setup fails (e.g. offline), install Ollama from [ollama.com](https://ollama.com/) as a fallback and retry. |
| **A model won't download / download stalls** | Re-open the wizard and press **Set up KimCad's AI** again — it resumes. You can also pull them yourself if you have Ollama: `ollama pull qwen2.5:7b` and `ollama pull qwen2.5vl:3b`. The models download to ~7.7 GB total (plus the ~1.4 GB engine on first run); keep ~12 GB free as headroom. |
| **A design takes a minute or two** | Normal for the first design after a cold start (the model is loading into memory). Template parts re-render from sliders instantly afterward. |
| **"This part can't be sliced"** | The Printability Gate failed it — usually too big for the selected printer, too-thin walls, or a non-manifold result. The card names the reason. Make it smaller / thicker, or pick a bigger printer, then retry. You can still download the model to inspect it. |
| **A photo's sizes are wrong** | A photo can't convey scale — the numbers are estimates. Edit them in the description (or use a *dimensioned sketch* instead, which carries real sizes). |
| **"Printer offline / not reachable"** when sending | The printer couldn't be reached. The G-code is left on disk to download. Check the IP/`base_url`, that the printer is on, and (for Bambu) that LAN/Developer mode is enabled. |
| **"Not set up" / credential rejected** when sending | The connection's API key / access code env var is missing or wrong. Re-check it in **Settings → Printer connections** (each shows the exact env-var name). |
| **A "Reload" banner appears after the app was left open** | The per-boot session token rotated when the server restarted. Click **Reload** once — it re-fetches a fresh token. (Harmless; see Trust boundaries.) |
| **Where are my files?** | Designs: `~/.kimcad/designs/`. App data: `%LOCALAPPDATA%\KimCad` (Windows) / `~/Library/Application Support/KimCad` (macOS) / `~/.local/share/KimCad` (Linux). The uninstaller never touches `~/.kimcad`. |
| **The app window won't open** | On Windows 10, ensure the WebView2 Runtime is installed (Edge installs it). See [Troubleshooting](troubleshooting.md). |

---

# Part 2 · The technical surface

This part assumes you're comfortable with a terminal. Everything here also works from a
source checkout; the installed app bundles it all.

## From a source checkout (all platforms)

KimCad runs from source on **Windows, macOS, and Linux** (Python 3.13):

```
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -e ".[dev]"
python scripts/fetch_tools.py     # OpenSCAD + OrcaSlicer (Windows: auto; macOS/Linux: see below)
ollama pull qwen2.5:7b            # the design planner
ollama pull qwen2.5vl:3b          # the photo/sketch vision reader
kimcad web                        # the browser UI on http://127.0.0.1:8765
```

On Windows `fetch_tools.py` provisions OpenSCAD and OrcaSlicer as checksum-pinned portable
builds. On **macOS/Linux** it can't auto-provision them yet — install OpenSCAD/OrcaSlicer
yourself and set absolute paths in `config/local.yaml` (`config/default.yaml` documents the
per-OS paths). The browser UI runs without either; only rendering and slicing need them.

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
| `kimcad web [--port N] [--host H] [--demo]` | the browser UI on `http://127.0.0.1:8765` (loopback only) |
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

**The AI model.** KimCad defaults to **Ollama** on `localhost:11434` running **`qwen2.5:7b`**
for design planning and **`qwen2.5vl:3b`** for reading photos/sketches. Both are local and the
app runs **fully offline**; images never leave the machine. `qwen2.5:7b` won the on-machine
bake-off (planned the prompt set 4/4 vs `gemma4:e4b` 1/4 and `llama3.1:8b` 0/4); design-plan
calls are schema-constrained at the token level (Ollama's native `format`) so a model that
wraps its JSON in prose still yields a parseable plan. **`gemma4:e4b` is only a fallback**
now (and still hosts the vision reader). The advisor downshifts smaller boxes (e.g. to
`qwen2.5:3b`). To use a different local model or a cloud backend, set the active backend in
`config/local.yaml`. (See the [model guide](MODEL-GUIDE.md) for the measured rationale.)

**Cloud (optional, off by default).** Turn on Cloud acceleration in Settings (or configure a
cloud backend in files) to route *text* prompts through [OpenRouter](https://openrouter.ai/),
DeepSeek, or any OpenAI-compatible endpoint. The key is read from the OS credential store (or
a disclosed file fallback) and never logged. Verify the cloud model name against your
provider's current list before relying on it.

## Printers and direct send

A sliced job can be sent to a **printer connection** through a swappable connector. Every
send requires explicit confirmation and refuses anything that isn't a proven slice. The
printer **picker** offers a curated **~29-machine catalog** (build-volume-gated, slice-proven
in CI) on top of the full ~1,400-profile OrcaSlicer library on disk. Direct send covers seven
connectors:

| Connector | Printers | Config |
|---|---|---|
| `loopback` | the built-in `mock` test connection | — |
| `bambu` | Bambu Lab P2S / A1 (native LAN) | `base_url` (IP), `serial`, access-code env var, `use_ams`; optional `bambulabs-api` pkg |
| `octoprint` | any OctoPrint host | `base_url`, `api_key_env` |
| `moonraker` | Klipper (Voron, Creality-Klipper, RatRig …) | `base_url`, optional `api_key_env` |
| `prusalink` | Prusa MK4 / MK3.9 / MINI / XL | `base_url`, `api_key_env`, optional `storage` (default `usb`) |
| `duet` | RepRapFirmware / Duet 2/3 boards | `base_url` (board IP), optional `api_key_env` (board password if one is set) |
| `marlin` | Marlin firmware (Ender-class + most consumer FDM) | `base_url` = USB serial port **or** `host:port` bridge |

Credentials are **always** read from an environment variable (named by `api_key_env`), never
stored in config and never logged. The shipped `bambu_p2s`, `bambu_a1`, `moonraker`,
`prusalink`, `duet`, and `marlin` entries are visible fill-in templates — set them up in
**Settings → Printer connections** (fields + the env-var name with a `setx` line), or edit
`config/default.yaml`.

**Bambu setup.** Enable LAN/Developer mode on the printer; note the **Access Code**
(*Settings → WLAN*) and **Serial** (*Settings → Device*). Fill `base_url` + `serial`, put the
access code in the named env var. Native MQTT-over-TLS control + FTPS upload via the optional
`bambulabs-api` package (`pip install bambulabs-api`); without it the connection reports "not
set up" with that exact hint — never a crash.

**Duet setup.** The `duet` connector drives RepRapFirmware boards over the classic `/rr_*`
HTTP interface (stdlib HTTP, **no extra dependency**): `rr_upload` to the SD `gcodes` folder,
`M32` start, `rr_status` progress. Set the board-password env var **only if** one is
configured; the connector opens a session per operation and always `rr_disconnect`s it.

**Marlin setup.** The `marlin` connector drives Marlin firmware over its raw M-code line
protocol — it uploads to the SD card (`M28`/`M29`, with line-number + checksum integrity) and
starts the print from SD (`M23`/`M24`, `M27` progress). The target is either:
- a **`host:port`** serial-over-network bridge (ser2net / ESP3D / OctoPrint serial relay) →
  stdlib TCP, **no extra dependency**; or
- a **USB serial port** (`COM3`, `/dev/ttyUSB0`) → needs the **optional `pyserial`** package
  (`pip install pyserial` or `pip install "kimcad[serial]"`). Without it a serial target
  reports that exact hint, never a crash.

> **Honest limits (Duet / Marlin).** Over the classic RRF `/rr_status` and Marlin `M27`
> surfaces there is **no per-file "is this job done?" query** — completion is *inferred* from
> the print returning to idle after progress was seen, so treat the first terminal state as
> final. Marlin truncates SD filenames to **8 characters**, so two designs sharing the first 8
> alphanumerics reuse the same SD file. Both connectors are **validated against a conformance
> mock**, not yet on physical metal — the first real-hardware run is the beta (#11).

Send from the CLI (`--send <connector>`), the web/app UI (pick → confirm → live status), or
an agent over MCP. Each connector has a **runnable mock server** for offline testing:
`python -m kimcad.mock_printer` (OctoPrint), `mock_moonraker`, `mock_prusalink`, `mock_duet`,
`mock_marlin`. Full matrix and validation status: **[supported printers](supported-printers.md)**.

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
   parametric families** — 39 benchmarked, 47 baseline; see the
   [part-library catalog](templates.md)) emits OpenSCAD directly — no model — which is why
   live-slider re-renders take under a second. Each family is tier-labeled (*benchmarked* vs
   *baseline*) and render-verified against its analytic bounding box. For anything
   off-template, the LLM writes OpenSCAD (or, on the parallel path, CadQuery).
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
| `printer_connector.py` + `*_connector.py` | the send abstraction + leaf connectors (`bambu_`, `octoprint_`, `moonraker_`, `prusalink_`, `duet_`, `marlin_`) |
| `webapp.py` / `shell.py` | the local web layer (incl. the session-token guard) and the WebView2 app window |
| `design_registry.py` | per-design server state + its locking protocols |
| `paths.py` | the dev↔installed + per-OS path seam (read root vs writable root) |
| `model_pull.py` | in-app model downloads with progress |
| `mcp_server.py` | the agent-facing MCP surface |

## Trust boundaries

- **Generated code is untrusted.** OpenSCAD source and CadQuery scripts are statically
  sanitized (an `ast` block-list, not a strip, so valid geometry is never mangled) and run in
  separate processes — CadQuery additionally behind a geometry-only facade with restricted
  builtins and env/cwd isolation.
- **The web server is loopback-only** by default; binding elsewhere requires an explicit
  `--host`/`--allow-remote` and a warning, because the server is unauthenticated by design
  (one trusted local user).
- **A per-boot session token guards state-changing requests.** The server mints a fresh
  random token each boot, injects it into the page shell
  (`<meta name="kimcad-session-token">`), and the SPA returns it as the **`X-KimCad-Session`**
  header on every POST. A state-changing request without the matching token (constant-time
  compared) is refused **`403`**. This is defense-in-depth against a **drive-by cross-origin
  POST** from a malicious web page — it can reach loopback but, being cross-origin, can't
  *read* the same-origin token (and the custom header forces a CORS preflight it can't
  satisfy). It is deliberately **not** full CSRF protection and **not** authentication: a
  single-user loopback app has no cookie session to forge. Because the token rotates per boot,
  a tab left open across a restart `403`s with `reason:"session"`, and the SPA shows a
  **one-click Reload** banner that re-fetches the fresh token. Both production start paths
  (`kimcad web` and the WebView2 shell) enforce the guard.
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
the read-only install dir; **writes** (design output, the app's browser profile) go to the
per-user data dir — `%LOCALAPPDATA%\KimCad` on Windows,
`~/Library/Application Support/KimCad` on macOS, `$XDG_DATA_HOME` / `~/.local/share/KimCad`
on Linux; user designs and settings stay in `~/.kimcad`. The Windows installer bundles an
embeddable CPython 3.13, the app + its pinned dependencies, the committed SPA, OpenSCAD,
OrcaSlicer, and the PrintProof3D engine — pinned by SHA-256 and proven by an automated
staging smoke (`verify_install.py`) on every push. (The zero-terminal installer is Windows
only for now; macOS/Linux run from source and provide their own OpenSCAD/OrcaSlicer.)

## How it's verified

One authoritative gate, `scripts/ci.sh`, runs identically in the pre-push hook and on the
self-hosted CI runner: `ruff`, the full `pytest` suite (including the **live** OrcaSlicer
slice, the CadQuery sandbox tests, and the connector conformance mocks), the frontend
**Vitest** suite, a **Playwright** end-to-end browser suite, a committed-SPA
build-reproducibility check, a diff-coverage gate, and the installer-staging smoke. Every
build stage passed a multi-role audit at zero findings across all severities before it was
tagged; the audit trail lives under [`docs/audits/`](audits/). The design rationale is in
[ARCHITECTURE.md](../ARCHITECTURE.md) and the v3.0 spec under
[`docs/design/`](design/).

---

*KimCad is open source under GPL-2.0. Questions and ideas:
[Discussions](../../discussions). The road ahead: [ROADMAP.md](../ROADMAP.md).*
</content>
</invoke>
