# Installing KimCad (the Windows beta)

KimCad installs like any Windows app: download `KimCad-Setup-<version>.exe`, double-click
it, and follow the wizard. No terminal, no Python, no developer tools.

## The SmartScreen warning (you will see it — here's why)

KimCad is open-source and the beta installer is **not code-signed** (signing certificates
are an ongoing cost the project hasn't taken on yet). Windows SmartScreen therefore shows
**"Windows protected your PC"** on first run. To proceed: click **More info → Run anyway**.

How to know the file is genuine: every release publishes the installer's **SHA-256
checksum** beside it. To check yours, in PowerShell:

```
Get-FileHash .\KimCad-Setup-0.9.0b1.exe -Algorithm SHA256
```

The hash must match the `.sha256` file from the same release page exactly.

## What the installer puts where

- **The app** (Python runtime, the design engine, OpenSCAD, OrcaSlicer, the PrintProof3D
  validation engine): the folder you choose — Program Files by default, or a per-user
  folder if you install without administrator rights. *Per-user installs trade away the
  read-only protection of Program Files (any program running as you could modify the
  app's files) — the same tradeoff per-user editors like VS Code make. Pick Program
  Files if unsure.*
- **Your designs and settings:** your user profile (`.kimcad`) — never Program Files,
  and never removed by the uninstaller.
- **App working data** (design output, the app window's browser profile):
  `%LOCALAPPDATA%\KimCad`. The uninstaller asks before removing it.

## First run

1. The wizard checks for **Ollama** (the free local AI runtime). Don't have it? The
   wizard's **Get Ollama** button takes you to the official download — install it, then
   come back and *check again*.
2. The wizard's **Download now** button fetches KimCad's two AI models (about 13 GB
   total) with a progress bar. Designing in words works as soon as the first finishes.
3. Pick your printer, and you're designing.

Everything runs on your computer. Nothing you design, photograph, or sketch leaves your
machine unless you explicitly turn on the cloud option in Settings.

## Requirements

Windows 11 (or Windows 10 with the WebView2 Runtime, which Microsoft ships automatically
via Edge), about **20 GB free disk space** (mostly the AI models), 16 GB+ RAM
recommended. No graphics card needed.

## If something goes wrong

[`docs/troubleshooting.md`](troubleshooting.md) covers every known snag, symptom-first.
