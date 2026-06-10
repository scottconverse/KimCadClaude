# Troubleshooting

Symptom → cause → fix, for every snag we know about. Most of these KimCad now detects
itself and tells you in plain words; this page is the longer version with the exact
commands.

## "KimCad couldn't reach your local AI" / designs never start

**Cause:** Ollama (the local AI runtime) isn't running, or was never installed.

**Fix:** start Ollama from the Start menu (look for the llama icon in the system tray),
then click **Check again** on the landing page — or just try your design again. If Ollama
isn't installed yet, see [getting-started-windows.md](getting-started-windows.md), Step 2.
`kimcad models` in a terminal shows exactly what KimCad can see.

## "requirements.lock not found" / "no such file" during setup

**Cause:** your terminal isn't in the KimCad folder — usually because GitHub's ZIP
unpacked into a nested folder (`KimCadClaude-main` inside the folder you unzipped to).

**Fix:** `cd` into the folder that contains `pyproject.toml` and `requirements.lock`
(check with `dir`), then re-run the command. See Step 3 of the
[getting-started guide](getting-started-windows.md).

## "The model isn't available on your local AI server" / "The model isn't pulled yet"

**Cause:** Ollama is running but the model was never pulled (or was removed). The first
wording is the terminal's; the second is the web page's — same cause, same fix.

**Fix:**

```
ollama pull gemma4:e4b
```

Then try again. `ollama list` should show `gemma4:e4b`.

## "KimCad's vision model isn't pulled yet"

**Cause:** the photo and sketch features use a dedicated small vision model that wasn't
downloaded (it's a separate pull from the main design model).

**Fix:**

```
ollama pull qwen2.5vl:3b
```

Then try the photo or sketch again. `kimcad models` shows both models' status.

## The photo or sketch feature returns nothing / an empty description

**Cause:** usually an outdated Ollama (older builds mishandle vision requests), or a very
low-contrast image.

**Fix:** update Ollama to the current release from <https://ollama.com/download>, then try
again with a clear, well-lit image. (Your models and settings survive the update.)

## The in-app model download fails or stalls

The setup wizard's **Download now** asks your local Ollama to fetch KimCad's models, so a
failure there is almost always one of three things:

- **"Not enough disk space"** — the two models need about 13 GB together (KimCad checks
  before downloading). Free up space, then press **try again**.
- **"Your local AI (Ollama) isn't running"** — start Ollama, then **try again**.
- **The download stopped partway** — usually the internet connection. Ollama resumes a
  partial download, so pressing **try again** continues rather than starting over.

The wizard downloads only KimCad's own two models; you never need to pick one. You can
always pull manually instead: `ollama pull gemma4:e4b` and `ollama pull qwen2.5vl:3b`.

## A Bambu printer connection says "needs the optional bambulabs-api package"

Direct send to a Bambu printer uses an optional add-on. In a terminal, run
`pip install bambulabs-api`, restart KimCad, and the connection will be available to set
up. Then fill in the printer's IP and serial in `config/default.yaml` (`bambu_p2s` /
`bambu_a1`) and set the access-code environment variable the entry names — the printer
shows both codes under **Settings → WLAN** (access code) and **Settings → Device**
(serial), with LAN mode enabled. Without all four pieces the connection stays listed as
"not set up yet" and tells you which piece is missing.

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
terminal) and try again; if it repeats, restart Ollama. Your saved designs are unaffected.

## Something else broke

The terminal running `kimcad web` always has the detailed error (the browser deliberately
shows only a short message). For anything security-related, see [SECURITY.md](../SECURITY.md);
for everything else, an issue report with the terminal's last lines is gold.
