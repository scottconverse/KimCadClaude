# Cross-platform packaging — decision (KC-8 / #13)

**Status:** Decided, 2026-06-14. **Decision:** ship first-class **from-source support** on macOS/Linux now (this issue); **defer zero-terminal installer artifacts** (`.dmg` / `.AppImage`) to a post-beta hosted-runner packaging lane. The macOS *distributable* installer is gated on an external dependency (an Apple Developer certificate) that only the project owner can procure.

This document is the "scoped with a decision" deliverable the issue calls for. It records what runs off-Windows today, the concrete buildable recipe for each platform, the in-repo changes a port still needs, and the next action when the installer lane is greenlit.

---

## TL;DR

| | macOS | Linux |
|---|---|---|
| **Runs from source** (`pip install` + `kimcad web`) † | ✅ — browser UI, design plan/codegen, CadQuery | ✅ — same |
| **Produces a printable part from source** | ⚠️ After the user installs OpenSCAD/OrcaSlicer + points `config/local.yaml` at them | ⚠️ Same |
| **Zero-terminal installer artifact** | ⛔ Deferred — needs an Apple Developer cert ($99/yr, owner-only) for a Gatekeeper-passing `.dmg` | ⛔ Deferred — feasible unsigned, but a multi-day effort with a fragile WebKit2GTK relocatability risk |
| **Recommended packaging tool** | briefcase (BeeWare) → Cocoa `.app` + `.dmg` | AppImage (browser-fallback variant first) |
| **Engineering effort (CI-green beta)** | ~3–5 focused days | ~4–6 focused days |

† Code-substantiated (static analysis + the cross-platform test design), not yet exercised on real macOS/Linux hardware — see the honesty note in §1.

The Windows beta is unaffected. Nothing here changes the shipped Windows installer.

---

## 1. What runs off-Windows today

The runtime-readiness audit (4-agent investigation, 2026-06-14) found **no blocker to running KimCad's process and web UI on macOS/Linux from a `pip install -e .` checkout.** Every platform-specific import is guarded — `import ctypes` is behind `if system == "Windows"` (model_advisor.py), `import webview` is in `try/except ImportError` (shell.py), `import keyring` likewise (settings_store.py) — so nothing crashes at import, and the stdlib HTTP server binds and serves. `keyring` is cross-platform (Keychain on macOS, SecretService on Linux) and degrades to the disclosed file fallback when no backend is usable. `kimcad shell` (the pywebview window) degrades to `kimcad web` when pywebview is absent, which is the normal off-Windows case (pywebview is `sys_platform == "win32"`-gated in `pyproject.toml`).

> **Honesty note:** this is **code-substantiated** (static analysis of the import surface + the cross-platform test design, which auto-skips `windows_only` tests off-Windows), **not yet exercised on real macOS/Linux hardware** — the dev box is Windows. This is the same "validated, not yet metal-validated" posture the printer connectors carry. A hosted-runner CI lane (§6) would convert it to empirical proof.

**What did *not* work off-Windows before this slice, and is now fixed (this issue):**

- **`scripts/fetch_tools.py`** could not provision OpenSCAD/OrcaSlicer off-Windows and failed with a bare `SystemExit` (`No pin for 'orcaslicer' on platform 'mac'`). It now prints an **actionable** message naming the official download, the `config/local.yaml` override, and the browser fallback.
- **`config/default.yaml`** defaulted to Windows `.exe` paths with no hint for other OSes. It now carries a commented macOS/Linux example block.
- **`src/kimcad/paths.py`** resolved its writable + webview-profile dirs to a **Windows-shaped** `~/AppData/Local` fallback on every OS. It now resolves to the platform-idiomatic location: `~/Library/Application Support/KimCad` (macOS), `$XDG_DATA_HOME/KimCad` → `~/.local/share/KimCad` (Linux), `%LOCALAPPDATA%\KimCad` (Windows, byte-identical to before).

After these fixes, the honest from-source story on macOS/Linux is: **install KimCad + OpenSCAD + OrcaSlicer, set two paths in `config/local.yaml`, run `kimcad web`, design in the browser.** A render attempt without the tools degrades cleanly (`ToolMissingError`, checked before any subprocess spawn), never a crash.

---

## 2. Why the installer artifacts are deferred

A *zero-terminal installer* is not a single switch — each OS is its own packaging project, and neither can be **stage-verified on this Windows dev box** (the existing two-step gate — `build_installer.py --stage-only` + `verify_install.py` — ships an embeddable **Windows** CPython, compiles with Inno Setup into a `.exe`, and runs `python.exe`/`pythonw.exe` against `.exe` tools and `%LOCALAPPDATA%`; it is intrinsically Windows-only and must be re-targeted per OS). The genuine constraints:

- **macOS signing/notarization needs an Apple Developer Program membership ($99/yr) + a Developer ID Application certificate + notarization credentials** — none exist in the repo or CI, and only the owner can procure them. Without them the `.app`/`.dmg` builds but is Gatekeeper-quarantined on download (worse than the documented Windows SmartScreen friction, which at least offers "Run anyway"). An *unsigned, locally-runnable* `.app` is buildable; a *distributable* `.dmg` is not, until the cert exists.
- **Linux's fully-self-contained native window (bundling WebKit2GTK + its helper processes via `linuxdeploy-plugin-gtk`) is the fragile part** and is unproven on this stack. The lower-risk first target is the **browser-fallback AppImage** (ship without the GTK window; the bundle launches `kimcad web` and opens the user's browser) — which sidesteps WebKit2GTK relocatability entirely.
- **Tool provisioning is not yet real off-Windows.** `fetch_tools.py` has only verified Windows pins; real macOS (`.dmg`) and Linux (`.AppImage`) OpenSCAD/OrcaSlicer pins (URLs + SHA-256 + the OrcaSlicer-2.4.0-alpha P2S-profile build, per arch) must be sourced, verified, and given `.dmg`/`.AppImage` handling before a CI build can assemble a working bundle.

Per the issue's own done-when ("**scoped with a decision**, or installers exist and stage-verify"), the decision is the in-scope deliverable; the installer artifacts are a follow-on stage.

---

## 3. macOS recipe (when greenlit)

- **Tool:** **briefcase** (BeeWare). It produces a real Cocoa `.app` whose `Info.plist`/entitlements match what WKWebView + the Hardened Runtime require, and it has first-class signing/notarization support. (Alternatives: py2app — lower-level, more manual entitlements; PyInstaller — single-binary, but its `--onefile` extraction fights notarization of nested native `.dylib`s from scipy/numpy/manifold3d/lxml.)
- **Bundle:** `KimCad.app/Contents/{MacOS/launcher, Resources/{site-packages, web, prompts, config, library, tools}}`, packaged into a per-arch `.dmg` (arm64 + x86_64 separately — the fetched OpenSCAD `.dmg` and OrcaSlicer mac DMG are per-arch native binaries, so there is no universal2 path).
- **Webview backend:** macOS pywebview uses **WKWebView via PyObjC** (not WebView2). Needs `pyobjc-core` + `pyobjc-framework-Cocoa` + `pyobjc-framework-WebKit` (a separate macOS lockfile — the committed `requirements.lock` is Windows-resolved and pins `pythonnet`/`pywin32-ctypes`).
- **Signing/notarization:** **EXTERNAL BLOCKER.** Apple Developer membership + Developer ID Application cert (CI secret: base64 `.p12` + password) + notarization key (App Store Connect API `.p8` + Issuer/Key ID). Every nested `.dylib` must be signed individually.
- **Stage-verify (no Apple credentials needed):** on a hosted `macos-latest` runner, the existing `verify_install.py` contract is reusable because it exercises the **server**, not the GUI — it runs `launcher web --demo`, polls `/api/health`, asserts the SPA + assets + prompts serve and a demo `/api/design` renders a mesh. So an **unsigned, stage-verified** `.app` is achievable on free hosted CI before the cert exists.
- **Effort:** ~3–5 days for an ad-hoc-signed `.app`/`.dmg` passing a mac-adapted verify; +1–2 days once Apple credentials exist to wire signing + notarization + stapling.

---

## 4. Linux recipe (when greenlit)

- **Tool:** **AppImage** (browser-fallback variant first). Build a relocatable CPython 3.13 (python-build-standalone) + site-packages + SPA/prompts + tools, assembled with `linuxdeploy` + `appimagetool`. The app's `KIMCAD_INSTALL_ROOT` + single-launcher design maps almost 1:1 onto an AppImage's `AppRun`, so the proven Windows launcher contract ports with minimal change. AppImage runs **unsandboxed** — so the subprocess `exec` of OpenSCAD/OrcaSlicer and the loopback socket bind just work (a Flatpak sandbox would block both without holes that defeat the point). OpenSCAD and OrcaSlicer both ship Linux AppImages upstream, so the tools story is "drop two vendor AppImages under `tools/` and `exec` them."
- **Webview:** Linux pywebview uses the **GTK backend (WebKit2GTK via PyGObject)**. The fully-self-contained native window (bundling WebKit2GTK) is the fragile, unproven part — hence the **browser-fallback** beta variant first (ship without the window; `kimcad web` + open the browser). No `pyobjc`/`pythonnet`; a separate Linux dependency set.
- **Signing:** **none required** — Linux has no Gatekeeper/SmartScreen equivalent. An unsigned AppImage runs after `chmod +x`. (Optional GPG detach-sign, not blocking.)
- **Stage-verify:** generalize `verify_install.py` first (it hardcodes `python.exe`, `printproof3d.exe`, and `%LOCALAPPDATA%` asserts), then build the AppDir on a hosted `ubuntu-latest` runner and run the `web --demo` smoke (no `xvfb` needed for the browser-fallback path — only a GTK window would need it). PrintProof3D ships only as a Windows `.exe`, so on Linux that engine is absent (Smart Mesh already falls back gracefully). OrcaSlicer profiles live inside the AppImage's squashfs, so the build must `--appimage-extract` to materialize `resources/profiles` next to the binary (where `orca_profiles_root()` expects them).
- **Effort:** ~4–6 days for a CI-green browser-fallback AppImage; +3–5 days if the fully-self-contained WebKit2GTK native-window variant is required.

---

## 5. In-repo code changes a port still needs

The readiness fixes in this slice (paths.py XDG/Library, fetch_tools actionable hints, default.yaml guidance) clear part of the path. The remaining Windows-specific assumptions a port must address:

- **`shell.py` — `webview.start(gui="edgechromium")`** is WebView2-pinned. A mac/Linux shell must select the backend per-OS (`cocoa` / `gtk`|`qt`, or `gui=None` for auto-detect), relax the `pyproject` `pywebview` marker to install per-OS extras, and rewrite the WebView2/.NET-missing error text. *(Not needed for the browser-fallback variant, which never opens a window.)*
- **`fetch_tools.py` — real macOS/Linux pins + extractors.** Add verified OpenSCAD `.dmg` (hdiutil/7z) and `.AppImage` (chmod +x, run directly) handling and the per-OS OrcaSlicer pins (the 2.4.0-alpha P2S-profile build, per arch/OS), with SHA-256s.
- **`verify_install.py` — generalize** the `python.exe` / `printproof3d.exe` / `%LOCALAPPDATA%` hardcodes so the gate runs per-OS.
- **`build_installer.py` — per-OS bundler.** Replace the embeddable-zip + Inno approach with briefcase (mac) and a `build_appimage.py` (Linux); most of the staging logic (site-packages, payload, tools) is reusable.
- **Separate per-OS lockfiles** (mac: pyobjc; Linux: PyGObject — neither in the Windows-resolved `requirements.lock`).
- **`config/default.yaml` — per-OS binary keys** (or resolve the exe-name from a per-OS table mirroring `fetch_tools.PINS.exe_name`) so `binary_path()` finds a non-`.exe` binary without the user hand-editing `local.yaml`.

`_ExclusiveBindServer.allow_reuse_address` is already correctly `win32`-guarded — no change needed.

---

## 6. Next action (when greenlit)

Hosted `macos-latest` and `ubuntu-latest` GitHub runners are **free for public repos** (consistent with the project's hosted-runners-for-public-repos policy), so the installer lanes can build and **stage-verify on GitHub's infra** without touching the self-hosted Windows box. Recommended sequencing:

1. **Linux browser-fallback AppImage first** — no external blocker, lowest risk, proves the per-OS staging + generalized verify on free CI.
2. **macOS unsigned `.app`** — buildable + stage-verifiable on `macos-latest` without credentials; proves the briefcase config + WKWebView backend.
3. **macOS signed/notarized `.dmg`** — only after the owner procures the Apple Developer cert (the one true external gate).
4. **Linux native-window AppImage** — only if the browser-fallback proves insufficient for users.

Each step is its own slice with its own audit + stage-verify gate, exactly like the Windows installer was (Stage 11).
