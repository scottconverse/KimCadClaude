# Getting started on Windows

This walks you from nothing to a running KimCad, step by step. No CAD experience needed —
and no programming. You'll copy a few commands into a terminal; each one is given exactly
as you should type it.

> **Heads-up:** until the one-click Windows installer ships (it's the last planned stage
> before beta), setup means installing three things yourself: Python, Ollama, and KimCad's
> own files. It takes about 15–30 minutes, most of it download time. If anything goes
> wrong, [troubleshooting.md](troubleshooting.md) has the fixes for every common snag.

## What you'll need

- A Windows 10/11 PC with about **15 GB free disk space** (most of it for the AI model)
  and ideally 16 GB+ of RAM.
- An internet connection for the downloads. (After setup, KimCad runs fully offline.)

## Step 1 — Install Python 3.13

1. Go to <https://www.python.org/downloads/> and download **Python 3.13** for Windows.
2. Run the installer. On the very first screen, **tick the box that says
   "Add python.exe to PATH"** — this matters; the commands below won't work without it.
3. Click "Install Now" and let it finish.

**Check it worked:** open a terminal (press the Windows key, type `powershell`, press
Enter) and type:

```
python --version
```

You should see `Python 3.13.x`. If you see an error or a Microsoft Store window opens,
see [troubleshooting](troubleshooting.md#python-isnt-found) ("Python isn't found").

## Step 2 — Install Ollama (the local AI runtime)

1. Go to <https://ollama.com/download> and download **Ollama for Windows**.
2. Run the installer. When it finishes, Ollama runs quietly in the background (you'll see
   a llama icon in the system tray).
3. In your terminal, pull KimCad's AI model (~5–10 GB — this is the big download):

```
ollama pull gemma4:e4b
```

**Check it worked:**

```
ollama list
```

You should see `gemma4:e4b` in the list.

## Step 3 — Get KimCad

Download the code as a ZIP from the project's GitHub page (the green **Code** button →
**Download ZIP**), then unzip it somewhere easy, e.g. `C:\KimCad`. (If you know git:
`git clone` works too.)

Then, in your terminal:

```
cd C:\KimCad
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.lock
pip install -e ".[dev]"
python scripts\fetch_tools.py
```

That last command downloads the two CAD tools KimCad drives (OpenSCAD and OrcaSlicer) —
about 200 MB, checksum-verified — into the `tools\` folder.

## Step 4 — Start KimCad and make your first part

```
kimcad web
```

Your terminal will say `KimCad web UI on http://127.0.0.1:8765`. Open that address in
your browser. A short first-run setup walks you through picking your printer; then type
something like *"a 40 mm desk cable clip"* and click **Design it**.

**The smoke test:** the part appears in the 3D view, the readiness card gives it a score,
and **Slice & prepare file** produces a downloadable print file. If all that happened —
you're fully set up. The first design takes a few minutes (the AI runs on your CPU); the
screen shows live progress the whole time.

## Day-to-day

- **Starting KimCad later:** open a terminal, then
  `cd C:\KimCad`, `.venv\Scripts\activate`, `kimcad web`. Ollama starts itself with
  Windows; if you've quit it, start it from the Start menu first.
- **Your designs are saved automatically** — see [guide-my-designs.md](guide-my-designs.md).
- **Stopping:** press `Ctrl+C` in the terminal, or just close it.

## If something went wrong

Every common failure has a fix in **[troubleshooting.md](troubleshooting.md)** — the
landing page and the terminal also tell you what's wrong in plain words (e.g. "Your local
AI isn't running yet — start Ollama"). Nothing you can do in setup harms your PC; the
worst case is deleting the folder and starting over.
