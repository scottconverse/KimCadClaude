# Getting started on Windows

> **The easy way (the beta installer):** download `KimCad-Setup-<version>.exe` from the
> releases page, double-click it, and follow
> **[docs/install-guide.md](install-guide.md)** — no terminal at any point. The installer
> bundles everything below, and the in-app setup wizard's **Set up KimCad's AI** button
> handles the AI engine and the model downloads automatically — no manual Ollama install.
>
> **The rest of this page is the FROM-SOURCE path** — for developers, or anyone who
> prefers to run KimCad from a code checkout. (Even here, KimCad can set up its own AI
> engine on first launch — Step 2 below is just the manual equivalent.)

This walks you from nothing to a running KimCad, step by step. No CAD experience needed —
and no programming. You'll copy a few commands into a terminal; each one is given exactly
as you should type it. Setup means installing Python and KimCad's own files, then letting
KimCad set up its AI (or installing Ollama yourself, below) — about 15–30 minutes, most of
it download time. If anything goes wrong, [troubleshooting.md](troubleshooting.md) has the
fixes for every common snag.

## What you'll need

- A Windows 10/11 PC with about **12 GB free disk space** as headroom (the AI engine
  ~1.4 GB plus the ~7.7 GB of models) and ideally 16 GB+ of RAM.
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

## Step 2 — Set up the local AI

KimCad sets up its own local AI on first run, so this step is largely automatic. Once
KimCad is running (Step 4), its setup wizard's **Set up KimCad's AI** button does the whole
flow: if you already have Ollama it uses it automatically, otherwise it downloads Ollama's
official **portable** build (~1.4 GB, a one-time engine download — no separate install, no
system tray, no admin) into KimCad's own data folder, then fetches the two AI models — the
designer (`qwen2.5:7b`, ~4.7 GB) and the small vision model that reads photos and sketches
(`qwen2.5vl:3b`, ~3 GB), ~**7.7 GB** total — with a progress bar.

> **Already have Ollama, or prefer to do it by hand?** Install Ollama from
> <https://ollama.com/download> if you don't have it, then pull the two models yourself:
>
> ```
> ollama pull qwen2.5:7b
> ollama pull qwen2.5vl:3b
> ```
>
> Either way KimCad uses whatever's there. `ollama list` (or `kimcad models` once installed)
> shows both `qwen2.5:7b` and `qwen2.5vl:3b` once they're present.

## Step 3 — Get KimCad

Download the code as a ZIP from the project's GitHub page (the green **Code** button →
**Download ZIP**), then unzip it somewhere easy. **Watch the folder nesting:** GitHub's
ZIP unpacks into a folder named like `KimCadClaude-main` — that *inner* folder (the one
containing `README.md` and `pyproject.toml`) is your KimCad folder. Move/rename it to
`C:\KimCad` so it matches the commands below. (If you know git: `git clone` works too.)

Then, in your terminal — from the folder that contains `pyproject.toml`:

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
  `cd C:\KimCad`, `.venv\Scripts\activate`, `kimcad web`. KimCad starts its own AI engine
  automatically (and a system Ollama, if you installed one, starts itself with Windows).
- **Your designs are saved automatically** — see [guide-my-designs.md](guide-my-designs.md).
- **Stopping:** press `Ctrl+C` in the terminal, or just close it.

## If something went wrong

Every common failure has a fix in **[troubleshooting.md](troubleshooting.md)** — the
landing page and the terminal also tell you what's wrong in plain words (e.g. "Your local
AI isn't ready yet" with a one-click **Set up KimCad's AI** / **Check again**). Nothing you
can do in setup harms your PC; the worst case is deleting the KimCad folder and redoing
Step 3 (Python keeps working; KimCad's portable AI engine lives in its own data folder, and
any system Ollama you installed stays put — uninstall those from Windows Settings → Apps if
you ever want them gone too).
