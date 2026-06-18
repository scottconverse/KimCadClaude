KCT-007-20260617-091

# Report 007 — KimCad 0.9.1 clean-machine gauntlet (zero-install AI / managed Ollama)
Status: COMPLETE. Box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI).

## 1. Verdict
**SHIP — the headline works.** A brand-new user with **no Ollama installed**, downloading the installer
from the GitHub release and running it, reaches a **working design without manually installing anything**.
On a verified-clean box (no Ollama, no models), the first-run wizard's **"Set up KimCad's AI"** button
downloaded KimCad's **own portable engine** (~1.4 GB into `%LOCALAPPDATA%\KimCad\ollama`) and the two
qwen models (~7.9 GB), reached **AI Ready**, and then designed/sliced real parts on the managed model —
all with **`ollama` never on PATH and no system Ollama install**. The old "Get Ollama → install it →
check again" dead-end is gone. Second launch reuses the engine instantly (no re-download); closing the
app shuts the managed engine down (no orphan). **No Blockers / Criticals / Majors.** Two **Minor**
polish items: (a) the engine-down message still says "Make sure Ollama is running" (leaks the
abstraction a user never sees), and (b) uninstall orphans 7.34 GB of models in `~/.ollama`.

## 2. Environment & method
AMD Ryzen 7 8745HS / Radeon 780M / 28,450 MB / Win 11 Pro 26200. WebView2 149.0.4022.69. Phase 0 proved
the box truly clean (no Ollama exe, no `~/.ollama` models, no Node) — the precondition every earlier
clean-run lacked. Evidence: `01-systeminfo.txt`, `02-clean.txt`.

**Method disclosure:** (1) Install used the **silent fallback** (`/VERYSILENT`), not the double-click —
GUI-wizard automation isn't drivable unattended on this harness; the installed app is the headline and
was driven for real. (2) The app UI was driven by attaching **Playwright over CDP to the real WebView2
shell** (`pythonw kimcad_launcher.py`, the actual Start-Menu entry point) — i.e. the genuine packaged
shell window (`Edg/149.0.4022.69`), not a proxy Chrome. Harness mode recorded in `00-harness-mode.txt`.

## 3. Per-phase results
| Phase | Result | Evidence |
|---|---|---|
| 0 — truly clean (no Ollama/models) | PASS | `01-systeminfo.txt`,`02-clean.txt` — no Ollama exe/models/Node, WebView2 present, 854 GB free. |
| 1 — download from repo + integrity | PASS | `03-sha256.txt` — 203,502,135 bytes; sha `6FDD91E9…629C` = expected exactly. |
| 2 — install | PASS (silent fallback) | `04-installed.txt`,`04-install.log` — exit 0, ~44s, reg `KimCad 0.9.1`, per-user, no admin. |
| 3 — BUILD-IDENTITY GATE (4/4) | **PASS** | 3.1 `05-verify-install.txt` → `VERIFY-INSTALL: ALL GREEN` v0.9.1. 3.2 model `qwen2.5:7b` `06-model.txt`. 3.3 exact 3 chips `07-landing-chips.*`. 3.4 **cold-start marker** `08-coldstart-setup-button.png`+`08-coldstart-analysis.txt`: wizard shows **"Set up KimCad's AI"**, copy "qwen2.5:7b — Not set up yet", **no "Get Ollama" deadend, no "start Ollama"**. |
| 4 — **managed-engine cold setup (HEADLINE)** | **PASS** | Clicked "Set up KimCad's AI" → in-app **engine fetch** `09-engine-fetch.png` (portable Ollama → `%LOCALAPPDATA%\KimCad\ollama`, NOT ollama.com) → **model fetch** `10-model-fetch.png` → **AI Ready** `11-ai-ready.png`. Proof it's KimCad's own: `12-managed-engine.txt` — `ollama` NOT on PATH, no `Programs\Ollama`, managed `ollama.exe serve` running under KimCad data. Models real: `10-model-fetch-complete.txt` (`/api/tags`: qwen2.5:7b 4.68 GB + qwen2.5vl:3b 3.2 GB). |
| 5 — core e2e (managed model) | **PASS (3/3)** | `13-chip*` 0 console errors: box 74s R86, clip 28s R92, dish 34s R92. Custom coaster 22s → **Slice & prepare → real print file** `part_bambu_p2s_pla.gcode.3mf` 115,338 B (`16-sliced-print-file.3mf`, `orca_err=False`). Photo on-ramp seeded (`photo-onramp.png`). **8 mm cable honored** (ENG-GG-002): `cable_d` slider val=8 "Cable diameter 8mm" `14b-cable-8mm.*`. WebGL `15-webgl.txt`. |
| 5b — multi-printer single-material | **PASS** | `17-single-material.txt` — 29 printers, **no Snapmaker U1**, **1 Material dropdown, 0 Extruder labels**. `18-connections.*` — normal connector templates, no Snapmaker. |
| 6 — reuse + teardown | **PASS** | `19-second-launch.txt` — 2nd launch AI Ready in 6s, **no setup step, no re-download** (engine 1958 MB / models 7.88 GB unchanged). `19b-engine-teardown.txt` — closing the window stops the managed engine + frees port 11434, **no orphan** (ENG-GG-001). |
| 7 — failure states | **PASS** (1 Minor) | `21-engine-down.*` — engine stopped → "KimCad couldn't reach your local AI… Try again" + "Set up your local AI first — see Settings", **no 500/traceback**. `22-non-geometric.*` — "a feeling of nostalgia" → graceful experimental-generator offer, **no refine chips** (no part). |
| 8 — uninstall | **PASS** (1 Minor) | `23-uninstall.txt` — program/registry/shortcut GONE, `%LOCALAPPDATA%\KimCad` (incl. engine) removed, **user designs `~/.kimcad` retained**; **7.34 GB models orphaned in `~/.ollama`**. |

## 4. Findings
*(Each cites a committed artifact under `evidence/007/`.)* **No Blockers / Criticals / Majors.**

- **[Minor] Engine-down message leaks the "Ollama" abstraction.** With the managed engine stopped, the
  chat says *"KimCad couldn't reach your local AI. **Make sure Ollama is running**, then try again."*
  But in 0.9.1 the user never knowingly installs or runs "Ollama" — the app presents it as "KimCad's
  AI" and manages it. Telling them to "make sure Ollama is running" isn't actionable (there's no Ollama
  tray icon for them) and contradicts the directive's goal of down-state guidance that **never says
  "start Ollama."** The "Try again" + "Set up your local AI first — see Settings" parts are good; just
  the "Make sure Ollama is running" clause should be reworded to the managed-engine vocabulary.
  Evidence: `21-engine-down.png`, `21-engine-down.txt`.

- **[Minor] Uninstall orphans 7.34 GB of models in `~/.ollama`.** The managed engine downloads model
  blobs to the conventional `~/.ollama` (not under `%LOCALAPPDATA%\KimCad`). The uninstaller cleanly
  removes KimCad's own dirs (program, registry, shortcut, `%LOCALAPPDATA%\KimCad` incl. the engine
  binary) and correctly retains user designs (`~/.kimcad`) — but leaves **7.34 GB of models in
  `~/.ollama`** with no prompt. A user reclaims ~2.56 GB and is unknowingly left with ~7.3 GB of AI
  models they never chose to put there. Consider removing them on uninstall (with consent) or storing
  models under KimCad's data dir so they're covered by the existing cleanup. Evidence: `23-uninstall.txt`.

## 5. Engine/model download + WebGL
- **Engine fetch:** portable Ollama → `%LOCALAPPDATA%\KimCad\ollama` (~1.4 GB), began on button click.
- **Model fetch:** qwen2.5:7b (4.68 GB) + qwen2.5vl:3b (3.2 GB) → `~/.ollama` (7.34 GB on disk), ~5 min
  on this connection (engine→both-present ≈ 18:14→18:19). A long honest progress download, as expected.
- **Design times (managed qwen2.5:7b, CPU/iGPU):** box 74.4 s / clip 28.2 s / dish 34.2 s / coaster 22 s
  — within the 30–120 s band; **0 console errors** across all.
- **WebGL renderer (verbatim, `15-webgl.txt`):** `ANGLE (AMD, AMD Radeon 780M Graphics (0x00001900)
  Direct3D11 vs_5_0 ps_5_0, D3D11)` — real iGPU via ANGLE→D3D11.

## 6. Open questions for DEV
1. **Model storage location.** The directive assumed models live under `%LOCALAPPDATA%\KimCad`; in
   practice the managed engine uses `~/.ollama`. Intended? It's the root of the uninstall-orphan Minor,
   and it means a later *system* Ollama install would silently share/reuse these blobs.
2. **Down-state wording** (Minor above) — confirm the "Make sure Ollama is running" string is meant to
   stay, or reword to the managed-engine vocabulary used everywhere else.
3. **Reuse-of-system-Ollama path (Phase 6 optional)** was NOT tested — this box had no system Ollama by
   design (it's the cold-start box). Needs a separate box with a real system Ollama to verify the
   "reuse instead of fetch" branch.
4. Install used the silent fallback, not the double-click (harness limitation). The cold-start flow
   itself was driven for real on the installed app; only the installer chrome wasn't exercised.

— TESTER (DESKTOP-2BR3SJR)
