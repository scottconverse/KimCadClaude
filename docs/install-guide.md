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
Get-FileHash .\KimCad-Setup-0.9.3.exe -Algorithm SHA256
```

The hash must match the `.sha256` file from the same release page exactly.

### Verifying the release files

Beyond the single `.sha256` beside the installer, each release also publishes two files that let
you verify everything in one pass and confirm exactly what source the build came from:

- **`SHA256SUMS.txt`** — one line per release artifact (`<sha256>  <filename>`). Drop it next to
  the files you downloaded and let PowerShell check them all at once:

  ```
  Get-Content .\SHA256SUMS.txt | ForEach-Object {
    $hash, $name = $_ -split '\s+', 2
    $actual = (Get-FileHash $name.Trim() -Algorithm SHA256).Hash
    "{0}  {1}" -f ($(if ($actual -eq $hash.ToUpper()) {'OK   '} else {'FAIL '}), $name.Trim())
  }
  ```

  Every line should report `OK`. A `FAIL` (or a missing file) means a tampered or incomplete
  download — re-download from the release page.

- **`release-manifest.json`** — records the build's metadata, including the **exact source commit**
  the installer was built from and a `unsigned_build` flag. The flag is **expected**: KimCad's beta
  is honestly unsigned (there is no code-signing certificate, and therefore **no signed
  attestation**). The manifest is how you confirm provenance instead — match its commit against the
  tagged release on GitHub.

These two files are the release's integrity story; there is no signed attestation to look for.

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
- **KimCad's managed AI engine** (a portable Ollama) and the downloaded models — never
  Program Files. The engine lives under your per-user data folder
  (`%LOCALAPPDATA%\KimCad\ollama`) and the models go in `%LOCALAPPDATA%\KimCad\models`;
  both are removable with the app data.

## First run

1. The wizard's **Set up KimCad's AI** button does everything in one flow — no manual
   Ollama install required. KimCad sets up its own local AI engine: if you already have
   Ollama installed it **uses it automatically**, otherwise it downloads Ollama's official
   **portable** build (~**1.4 GB**, a one-time engine download — no separate install, no
   system tray, no admin) into KimCad's own data folder and runs it headless. Then it
   fetches KimCad's two AI models (about **7.7 GB** total to download — chat ~4.7 GB +
   vision ~3 GB) with a progress bar. Designing in words works as soon as the first model
   finishes.
2. Pick your printer, and you're designing.

> **Already have Ollama?** KimCad uses it automatically — nothing to do. And if automatic
> setup ever fails (e.g. you're offline), you can install Ollama yourself from
> [ollama.com](https://ollama.com/) and press **Check again**.

Everything runs on your computer. Nothing you design, photograph, or sketch leaves your
machine unless you explicitly turn on the cloud option in Settings.

## Requirements

Windows 11 (or Windows 10 with the WebView2 Runtime — Microsoft ships it automatically
via Edge — and .NET Framework 4.7.2+, in-box since Windows 10 1803), about **12 GB of free
disk space** as headroom (the AI engine ~1.4 GB plus the ~7.7 GB of models, with room to
spare), 16 GB+ RAM recommended. No graphics card needed.

## macOS / Linux

The double-click installer is Windows-only for the beta. On **macOS and Linux**, KimCad runs
**from a source install** — `pip install`, then `kimcad web` opens the same UI in your browser.
See the [README Setup section](../README.md#setup) for the steps (you install OpenSCAD/OrcaSlicer
yourself and point `config/local.yaml` at them). *This cross-platform path is code-verified but
not yet exercised on real mac/Linux hardware.* Zero-terminal installers for macOS/Linux are scoped
and deferred — see [cross-platform packaging](dev/cross-platform-packaging.md).

## If something goes wrong

[`docs/troubleshooting.md`](troubleshooting.md) covers every known snag, symptom-first.
