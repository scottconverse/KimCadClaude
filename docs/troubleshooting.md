# Troubleshooting

Symptom → cause → fix, for every snag we know about. Most of these KimCad now detects
itself and tells you in plain words; this page is the longer version with the exact
commands.

## "KimCad couldn't reach your local AI" / designs never start

**Cause:** KimCad's AI engine isn't set up or isn't running yet. KimCad runs its **own**
engine (it reuses a system Ollama if one is installed, otherwise it downloads and runs
Ollama's portable build for you), so there's normally nothing for you to start by hand.

**Fix:** click **Set up KimCad's AI** (or **Check again**) on the landing page — it
provisions and starts the engine, then retries — or just try your design again. If
automatic setup fails (for example, you're offline so the portable engine can't download),
install Ollama yourself from [ollama.com](https://ollama.com/) as a fallback and press
**Check again**. `kimcad models` in a terminal shows exactly what KimCad can see.

## "requirements.lock not found" / "no such file" during setup

**Cause:** your terminal isn't in the KimCad folder — usually because GitHub's ZIP
unpacked into a nested folder (`KimCadClaude-main` inside the folder you unzipped to).

**Fix:** `cd` into the folder that contains `pyproject.toml` and `requirements.lock`
(check with `dir`), then re-run the command. See Step 3 of the
[getting-started guide](getting-started-windows.md).

## "The model isn't available on your local AI server" / "The model isn't pulled yet"

**Cause:** the AI engine is running but the model was never downloaded (or was removed).
The first wording is the terminal's; the second is the web page's — same cause, same fix.

**Fix:** in the app, re-open the setup wizard and press **Set up KimCad's AI** — it fetches
whichever model is missing with a progress bar. (If you're running your own Ollama, you can
pull it by hand instead:)

```
ollama pull qwen2.5:7b
```

Then try again. `kimcad models` should show `qwen2.5:7b`.

## "KimCad's vision model isn't pulled yet"

**Cause:** the photo and sketch features use a dedicated small vision model that wasn't
downloaded (it's a separate pull from the main design model).

**Fix:** re-open the setup wizard and press **Set up KimCad's AI** — it fetches the missing
vision model with a progress bar. (Running your own Ollama? Pull it by hand instead:)

```
ollama pull qwen2.5vl:3b
```

Then try the photo or sketch again. `kimcad models` shows both models' status.

## The photo or sketch feature returns nothing / an empty description

**Cause:** usually a very low-contrast image, or — if you're using your own (older) system
Ollama — a build that mishandles vision requests. (KimCad's own portable engine is a current
build, so this is mostly a concern when you've pointed KimCad at a pre-existing install.)

**Fix:** try again with a clear, well-lit image. If you're on your own system Ollama, update
it to the current release from <https://ollama.com/download> (your models and settings
survive the update); or let KimCad use its own engine via **Set up KimCad's AI**.

## (Installed app) The KimCad window won't open, or opens blank

The windowed app needs two Microsoft components that ship with Windows 11 (and most
updated Windows 10): the **WebView2 Runtime** and **.NET Framework 4.7.2+**. If the
window won't start, KimCad prints one line naming them — install "WebView2 Runtime" from
Microsoft and try again. The browser always works meanwhile: run KimCad's `kimcad web`
from the install folder, or just reinstall after updating Windows.

If the window opens but shows nothing, the install may be damaged — re-run the installer
(your designs and settings are not touched by reinstalls).

## "Missing or invalid session token. Reload KimCad." / actions suddenly fail

This is **expected and harmless** after KimCad restarts while an older window/tab is still
open. KimCad uses a fresh security token each time it starts (a defense against malicious web
pages quietly poking the local server), so a page left open from a previous run holds the old
token and its actions are refused. KimCad shows a **Reload** banner at the top of the window —
click it (or press **Ctrl+R** / **F5**, or reopen the app window). Viewing existing designs keeps
working; only actions (design, save, slice, send) are blocked until you reload. Reloading fixes
it instantly.

## (Installed app) "Windows protected your PC" when running the installer

That's SmartScreen reacting to an unsigned open-source installer — expected for the beta.
**More info → Run anyway.** To verify the download first, check its SHA-256 against the
release page: see [install-guide.md](install-guide.md).

## (Installed app) Where is my stuff?

Saved designs + settings: the `.kimcad` folder in your user profile (never removed by the
uninstaller). The app's working output: `%LOCALAPPDATA%\KimCad`. KimCad's managed AI engine
(the portable Ollama) and the downloaded models: under your per-user data folder
(`%LOCALAPPDATA%\KimCad\ollama` for the engine, `%LOCALAPPDATA%\KimCad\models` for the models) —
never Program Files, and removable with the app data. The app itself: the folder you chose at
install time.
## The in-app AI setup or model download fails or stalls

The setup wizard's **Set up KimCad's AI** provisions the engine (reusing a system Ollama, or
downloading the portable build) and then fetches KimCad's models, so a failure there is
almost always one of these:

- **"Not enough disk space"** — the two models download to about **7.7 GB** together (chat
  ~4.7 GB + vision ~3 GB), and the portable engine adds a one-time ~1.4 GB on first run. Keep
  about **12 GB** free as headroom (KimCad checks before downloading). Free up space, then
  press **try again**.
- **The AI engine couldn't be set up** — usually because you're offline so the portable
  build can't download. Reconnect and press **Set up KimCad's AI** again; or install Ollama
  from [ollama.com](https://ollama.com/) as a fallback and press **Check again**.
- **The download stopped partway** — usually the internet connection. The engine resumes a
  partial download, so pressing **try again** continues rather than starting over.

The wizard downloads only KimCad's own two models; you never need to pick one. If you're
running your own Ollama you can also pull manually: `ollama pull qwen2.5:7b` and
`ollama pull qwen2.5vl:3b`.

## A Bambu printer connection needs the optional bambulabs-api package

Direct send to a Bambu printer uses an optional add-on. In a terminal, run
`pip install bambulabs-api` (or `pip install "kimcad[bambu]"`, which pins the tested version floor), restart KimCad, and the connection will be available to set
up. Then fill in the printer's IP and serial in `config/default.yaml` (`bambu_p2s` /
`bambu_a1`) and set the access-code environment variable the entry names — the printer
shows both codes under **Settings → WLAN** (access code) and **Settings → Device**
(serial), with LAN mode enabled. Without all four pieces the connection stays listed as
"not set up yet" and tells you which piece is missing.

## A Marlin printer over USB needs the optional pyserial package

The `marlin` connection talks to the printer over a serial line. If you point its `base_url`
at a **USB serial port** (`COM3`, `/dev/ttyUSB0`), KimCad needs the optional `pyserial`
package — run `pip install pyserial` (or `pip install "kimcad[serial]"`), restart KimCad, and
the serial path is available. If it isn't installed, sending to a serial-port target tells you
exactly that. A **network** Marlin target (a `host:port` ser2net/ESP3D/relay bridge) needs
nothing extra. KimCad uploads the print to the printer's SD card and starts it from there; the
SD filename is shortened to 8 characters, so two designs whose names share the first 8
letters/digits land on the same SD file.

## "OpenSCAD isn't installed at …" or "OrcaSlicer isn't installed at …"

**Cause:** the CAD tools were never fetched (or the download was interrupted), so
`tools\openscad\` / `tools\orcaslicer\` is empty.

**Fix:** from the KimCad folder, with your venv active:

```
python scripts\fetch_tools.py
```

It's safe to re-run any time — it verifies checksums and skips what's already there. If
you'd rather use your own installed copy, point `binaries.openscad` /
`binaries.orcaslicer` at it in `config\local.yaml` — but read the next entry first.

## Slicing crashes or fails instantly with your own OrcaSlicer

**Cause:** OrcaSlicer **2.3.2** (the current "stable") has an upstream bug that crashes
CLI slicing on machines without a discrete GPU — which is exactly the kind of machine
KimCad targets.

**Fix:** use the bundled copy (`python scripts\fetch_tools.py` fetches a pinned
**2.4.0-alpha** that fixes the crash and still ships the right printer profiles). If you
point KimCad at your own OrcaSlicer, make it 2.4.0-alpha or newer.

## "Port 8765 is already in use"

**Cause:** another KimCad (or something else) is already listening on that port — usually
a KimCad you started earlier and forgot.

**Fix:** close the other one, or start this one on a different port:

```
kimcad web --port 8766
```

## No "Download editable CAD (.STEP)" button / the STEP download fails

**Cause (no button):** the optional CAD export engine (CadQuery) isn't installed — the
Export panel then says so and points at Settings. Note the experimental generator's parts
are `.STL`-only by design; only standard (template-built) parts can export STEP.

**Fix:** *Settings → Editable CAD export* walks through the one-time setup
(`py -3.13 -m pip install cadquery`, then *check again* — no restart needed). The first
STEP download after that takes a few seconds while KimCad prepares the file.

**Cause (button present but the download errors):** the engine install is broken or was
removed mid-session. Re-run the pip install, then *check again* in Settings; the terminal
running `kimcad web` logs the underlying error.

## Parts download as .stl instead of .3mf

**Cause:** an OpenSCAD build without 3MF support (lib3mf). KimCad notices and falls back
to STL automatically — your part is still fine.

**Fix (optional):** use the bundled OpenSCAD (`python scripts\fetch_tools.py`), which has
3MF support.

## Settings says my key is "kept in a settings file"

**Cause:** the secure credential store (Windows Credential Manager) wasn't usable on your
machine, so KimCad fell back to keeping the key in its local settings file — and told you
so under the key field. The key still works; it's just less protected at rest.

**Fix (optional):** nothing is required — but anyone who can read your files could read
the key, so prefer a low-value key, or remove it (the **Remove** button) when not using
cloud acceleration. If Credential Manager starts working again (e.g. after a Windows
repair), re-saving the key moves it there automatically.

## Python isn't found

**Cause:** Python was installed without "Add python.exe to PATH", or the Microsoft Store
stub is intercepting the command.

**Fix:** re-run the Python installer → "Modify" → tick **Add python.exe to PATH**. If a
Store window opens when you type `python`: Windows Settings → Apps → Advanced app
settings → **App execution aliases** → turn off the two `python.exe` aliases.

## A design takes forever / looks frozen

**What's normal:** the AI runs on your CPU — a real design takes a few minutes, and both
the web page and the terminal show live progress phases the whole time ("Planning the
shape…", "Rendering the part…"). If you see phases ticking, it's working.

**What's not:** no progress at all for 10+ minutes. Press Cancel (or `Ctrl+C` in the
terminal) and try again; if it repeats, restart KimCad (which restarts its AI engine), or
re-run **Set up KimCad's AI** from the wizard. Your saved designs are unaffected.

## Something else broke

The terminal running `kimcad web` always has the detailed error (the browser deliberately
shows only a short message). For anything security-related, see [SECURITY.md](../SECURITY.md);
for everything else, an issue report with the terminal's last lines is gold.
