KCT-009-20260618-093

# Report 009 — KimCad 0.9.3 clean-machine gauntlet (Zen Design World branding)

## 1. Verdict: SHIP

0.9.3's "Zen Design World" branding overhaul survives a real clean-machine install end-to-end, and
no functional flow regressed from 0.9.2. **Kim is everywhere** and the **gold/black Zen palette has
zero terracotta**. Every in-app Kim mark is a real `<img alt="Kim">` (a11y-correct). The cold-start
managed-AI, 3 curated chips, single-material slice→real `.3mf`, and photo on-ramp all pass equivalently
to 0.9.1/0.9.2. **No Blocker / Critical / Major / Minor.** One **Nit** (silent-uninstall data retention,
a consent-prompt artifact — see §5).

Method/harness disclosure: install used the **silent fallback** (`/VERYSILENT`); the in-app UI was
driven by attaching **Playwright over CDP to the real WebView2 shell** (`pythonw kimcad_launcher.py`),
mode `shell-webview2`. **Native OS surfaces** (desktop/Start-menu/taskbar/Alt-Tab/title-bar icons)
cannot be screenshotted by this autonomous harness (computer-use needs human approval, unavailable on
a watchdog tick), so they are verified via **icon asset + shortcut wiring on disk** — disclosed per
surface below.

## 2. Build identity (Phase 1 + 3)
- **SHA-256** `f2c97ece…dd25b8` + size `204,050,711` — match the published v0.9.3 asset exactly (`03-sha256.txt`).
- **verify_install.py → `VERIFY-INSTALL: ALL GREEN`**, version **0.9.3** (`05-verify-install.txt`); `/api/health` → `0.9.3`.
- **Model** `qwen2.5:7b` planner (`06-model.txt`). **3 landing chips** exact (`07-landing-chips.*`).
- **Cold-start marker**: wizard "Set up your AI" shows **"Set up KimCad's AI"**, no Get-Ollama deadend (`08-coldstart*`).
- **Install identity**: registry `KimCad 0.9.3`, **DisplayIcon = kim.ico** (`04-installed.txt`, `04-uninstall-registry.txt`).

## 3. Branding survival checklist (Phase 4 + 2A)
| Surface | Result | Evidence | Note |
|---|---|---|---|
| Installer .exe icon (2A) | **PASS** | `04-installer-icon.png` | Extracted embedded icon = Kim; 0% green (not the Python snake) |
| 4a desktop shortcut | **PASS (wiring)** | `09-branding-summary.txt` | `Desktop\KimCad.lnk` IconLocation = `kim.ico,0` (on-disk; native render not auto-screenshotable) |
| 4b Start-menu tile | **PASS (wiring)** | `09-branding-summary.txt` | `Start Menu\KimCad\KimCad.lnk` IconLocation = `kim.ico,0` |
| 4c title bar / 4d taskbar / 4e Alt-Tab | **PASS (wiring)** | `09a-kim-ico.png`, `09-branding-summary.txt` | window icon derives from same `kim.ico` (pythonw + kim.ico); kim.ico ships at install root + web; native render needs human eyeball |
| 4f wizard rail | **PASS** | `15-wizard-rail.png`,`15-wizard-imgs.txt` | `<img alt="Kim" src="kim-avatar.png">` **56px**, gold ring |
| 4g Welcome portrait | **PASS** | `16-wizard-welcome.png` | Kim img **120px**, gold ring |
| 4h topbar logo | **PASS** | `17-topbar-logo.png`,`18-landing-hero.png` | Kim img **32px** gold ring + "Kim**Cad**" wordmark, "Cad" in gold |
| 4i landing hero | **PASS** | `18-landing-hero.png` | Kim img **96px**, gold ring above H1 |
| 4j chat avatars | **PASS** | `19-chat-avatars.*`,`44-branding-during-design.png` | **28px** real `<img alt="Kim">`, **0 CSS-bg avatars** (a11y-correct) |
| 4k favicon | **PASS** | `20-favicon.png` | `favicon.ico` == `kim.ico` (hash-identical, same Kim) |
| 4l palette light | **PASS** | `21-palette-light.png`,`21-palette.txt` | accent `#d4af37`, warm-white `rgb(250,250,247)`, black text; **no terracotta** |
| 4l palette dark | **PASS** | `22-palette-dark.png` | accent `#e3c24f`, deep-black `rgb(12,10,6)`, warm-white text; **no terracotta** |
| 4m a11y | **PASS** | `23-a11y.txt` | every Kim mark a real `<img alt="Kim">`; Narrator not run in autonomous mode → verified alt-text presence via DOM instead |

Brand var set (verbatim): `--kc-accent:#e3c24f --kc-accent-strong:#efd06b --kc-accent-deep:#c9a634
--kc-on-accent:#1a1408 --kc-warn-accent:#e6b35c`; light topbar accent computed `#d4af37`.

## 4. Functional regression (Phase 5 + 6) vs 0.9.1/0.9.2 baseline — all PASS
- **Managed-engine cold setup** (Phase 5): clicked "Set up KimCad's AI" → engine→`%LOCALAPPDATA%\KimCad\ollama` (1.87 GB), models→`%LOCALAPPDATA%\KimCad\models` (7.34 GB), both present in ~2.5 min, AI **Ready**. `ollama` not on PATH, no system install, managed `ollama serve` (PID 460). d007 fix intact. `33-managed-engine.txt`,`32-ai-ready.png`.
- **3 curated chips** (Phase 6): 3/3, **0 console errors** — box 73.4 s R86, clip 35.2 s R92, dish 30.2 s R92. `40-chip*`, `41-chip*-console.txt`.
- **Custom slice**: coaster → **Slice & prepare → real print file** `part_bambu_p2s_pla.gcode.3mf` 115,360 B, `orca_err=False`. `43-export.*`.
- **Photo on-ramp**: seeded (vision qwen2.5vl:3b). `45-photo-onramp.png`.
- **Branding-during-design**: topbar Kim + chat Kim avatar + gold accents hold mid-design. `44-branding-during-design.png`.
- **WebGL (verbatim, `42-webgl.txt`)**: `ANGLE (AMD, AMD Radeon 780M Graphics (0x00001900) Direct3D11 vs_5_0 ps_5_0, D3D11)`.

## 5. Uninstall (Phase 7) — residue
Silent uninstall: install dir GONE, registry GONE, **`~/.kimcad` designs PRESERVED**, no orphan engine
process — all correct. **However the 9.21 GB `%LOCALAPPDATA%\KimCad` (engine+models) remained.**
Honest analysis (`51-post-uninstall.txt`): not a lock (freely deletable after; the 6 lingering
msedgewebview2 are Windows CBS, not KimCad), not the d007 orphan (models are correctly in
`KimCad\models`). Root cause: **0.9.3 added a "remove your KimCad data?" consent prompt** (per the
directive's own Phase 7) which `/SUPPRESSMSGBOXES` suppresses → defaults to KEEP data. An interactive
user clicking "YES, remove data" would reclaim it. (0.9.2's silent uninstall deleted the data; 0.9.3
deliberately gates it behind consent — a reasonable safety change.)

## 6. Findings
- **[Nit] Silent uninstall retains the 9.21 GB engine+model data dir** because the new
  "remove your KimCad data?" prompt is suppressed under `/SUPPRESSMSGBOXES` (defaults to keep). Not a
  regression; the interactive path with "YES" reclaims it. **Recommend** DEV/Scott confirm the
  interactive uninstall (a) reclaims the 9.21 GB and (b) shows Kim's icon on the uninstall dialog
  (DisplayIcon=kim.ico is wired). Evidence: `51-post-uninstall.txt`.

No Blocker / Critical / Major / Minor.

## 7. Machine context
DESKTOP-2BR3SJR — AMD Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win 11 Pro 26200. WebView2 149.0.4022.69.
Phase 0 proved truly clean (no Ollama exe/models, no `.ollama`/`.kimcad`/`LOCALAPPDATA\KimCad`, no Node);
852 GB free. `01-systeminfo.txt`, `02-clean.txt`. Box restored true-clean after the run.

— TESTER (DESKTOP-2BR3SJR)
