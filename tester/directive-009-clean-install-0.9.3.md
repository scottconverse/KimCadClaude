# KimCad Tester Directive 009 — Clean-Machine Gauntlet (0.9.3 — Zen Design World branding)

**NONCE:** `KCT-009-20260618-093`  ← echo this verbatim on line 1 of your report.
**Build under test:** **`0.9.3-rc1`** — a **published GitHub pre-release** (tag `v0.9.3-rc1`,
source commit `<RC-COMMIT-SHA>` on `main`). This is `0.9.2` + the full Zen Design World branding
overhaul: Kim Everywhere across every surface + gold/black palette across the whole app + installer
icon + native window icon + favicon.
**What changed since 0.9.2 (directive-008):**
- **Palette evolved to Kim's Zen Design World aesthetic** — warm white + gold (light mode), deep
  black + gold (dark mode). Every surface uses `--kc-accent: #d4af37`. The old Workshop terracotta
  is gone.
- **"Kim Everywhere"** — Kim's face is the brand mark on every visible surface: installer .exe icon,
  desktop shortcut, Start-menu tile, native app window (title bar / taskbar / Alt-Tab), browser tab
  favicon, first-run wizard rail (56px) + Welcome step (120px), topbar logo (32px), in-app empty
  state hero (96px), chat avatars (28px). All as real `<img alt="Kim">` (a11y-correct).
- **Avatar asset upgraded** 64px → 256px source — no soft-rendering at any size.
- **Build identity:** version `0.9.3`, pyproject + frontend lockstep, README badge shows `0.9.3`.

**No functional / business-logic / API / pipeline changes since 0.9.2.** The slicer, model
download, OrcaSlicer integration, photo on-ramp, Smart Mesh gate, multi-firmware connectors —
all unchanged. This is a branding overhaul, not a feature release.

> **⚠ THIS RUN'S WHOLE POINT — branding survives a real end-user install on a truly clean machine.**
> Every surface a real user sees from "I clicked the .exe" through "my first part is sliced" must
> show Kim and the Zen palette. The functional flows that worked in 0.9.2 must still work; this
> directive RE-RUNS the directive-007/008 end-to-end path AND adds the branding-survival checklist.

**Download (FROM THE REPO):** the **`v0.9.3-rc1` GitHub pre-release** —
`https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.3-rc1` → download the asset
**`KimCad-Setup-0.9.3.exe`** (in a browser, like any user would).
**Expected SHA-256:** `<SHA-FROM-PUBLISH>`
**Expected size:** `<BYTES-FROM-PUBLISH>` bytes (~203 MB)
**Source commit:** `<RC-COMMIT-SHA>` (tag `v0.9.3-rc1`)

---

## Hard rules
1. **EVIDENCE, NOT NARRATION.** Every claim cites a file you committed under `tester/evidence/009/`
   (screenshot `.png`, raw dump `.txt`, hash, JSON). No artifact → not a finding.
2. **PROVE THE BUILD FIRST.** Phase 3 is a hard gate. Any failure ⇒ STOP and report.
3. **Report to** `tester/reports/report-009.md`; append `STATUS.md` heartbeat after each phase (~10 min).
   Severity-tag findings: Blocker / Critical / Major / Minor / Nit.
4. **A branding regression is at least Major.** If Kim is absent or the old terracotta palette shows
   up anywhere — including a single icon, a single span, a missed CSS rule — log it.

## Ground rules
- Test the INSTALLED app from the **downloaded double-click installer**, not a dev build. You may
  `git clone` read-only for `scripts/verify_install.py`. Do NOT build the repo / venv / pip install.
- Model inference is CPU/iGPU (30–120 s/plan is normal) — record times, don't call slow a fail.
- First run needs internet + ~12 GB free disk (engine ~1.4 GB + models ~7.7 GB).

---

## Phase 0 — Make the machine TRULY clean  *(evidence: 01-systeminfo.txt, 02-clean.txt)*

**Scott's emphatic requirement:** delete EVERY remnant of previous installs, including LLM artifacts.
Cached models from a previous KimCad/Ollama install will mask real bugs in the cold-start flow.

**Run these (PowerShell as Administrator):**

```powershell
# 0a. Uninstall any prior KimCad via Apps & Features OR:
$kim = Get-WmiObject Win32_Product -Filter "Name LIKE 'KimCad%'" -ErrorAction SilentlyContinue
if ($kim) { $kim | ForEach-Object { $_.Uninstall() } }

# 0b. Uninstall any standalone Ollama (Apps & Features → Ollama → Uninstall, OR):
$ollama = Get-WmiObject Win32_Product -Filter "Name LIKE 'Ollama%'" -ErrorAction SilentlyContinue
if ($ollama) { $ollama | ForEach-Object { $_.Uninstall() } }

# 0c. NUKE the LLM artifacts (this is the critical "delete remnants" step):
Remove-Item -Recurse -Force "$env:USERPROFILE\.ollama" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\Programs\Ollama" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\KimCad" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "$env:USERPROFILE\.kimcad" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "${env:ProgramFiles}\KimCad" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "${env:ProgramFiles(x86)}\KimCad" -ErrorAction SilentlyContinue

# 0d. Kill any orphan ollama process:
Get-Process ollama -ErrorAction SilentlyContinue | Stop-Process -Force

# 0e. Verify clean:
Get-Command node,ollama,kimcad -ErrorAction SilentlyContinue
# Expected: nothing returned (all three NOT FOUND).
Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"   # Expected: False
Test-Path "$env:USERPROFILE\.ollama\models"                # Expected: False
Test-Path "$env:LOCALAPPDATA\KimCad"                       # Expected: False
Test-Path "$env:USERPROFILE\.kimcad"                       # Expected: False
# WebView2:
Get-AppxPackage -Name "Microsoft.WebView2*" | Select-Object Name,Version
```

**`02-clean.txt` evidence:** capture all of the above. The directive INVALIDATES if any cache
remains. Re-run 0c then re-verify.

`winver` + OS/CPU/RAM/GPU. **PASS only if:** no prior KimCad, no Ollama, no `.ollama` / `.kimcad`,
no `LOCALAPPDATA\KimCad`, no Node, WebView2 present, ~12 GB free disk.

---

## Phase 1 — Download from the repo + integrity  *(03-sha256.txt)*

Download `KimCad-Setup-0.9.3.exe` from the `v0.9.3-rc1` release page above **in a browser, like any
user would** (record the URL bar). DO NOT use `gh release download` — we are testing the user path.

```powershell
Get-FileHash KimCad-Setup-0.9.3.exe -Algorithm SHA256
(Get-Item KimCad-Setup-0.9.3.exe).Length
```

**PASS only if hash equals `<SHA-FROM-PUBLISH>` AND size equals `<BYTES-FROM-PUBLISH>`.**

---

## Phase 2 — Install (DOUBLE-CLICK)  *(04-installed.txt, 04-install.log, 04-installer-icon.png)*

**A. Watch the .exe icon BEFORE you double-click.** In File Explorer, the
`KimCad-Setup-0.9.3.exe` file icon itself MUST show Kim (round avatar, gold ring) — NOT the generic
Windows installer icon, NOT the Python snake. Screenshot the file in Explorer →
`04-installer-icon.png`. **If the .exe shows the Python snake or a generic icon, Major — SetupIconFile
didn't ship.**

**B. Double-click the .exe.** SmartScreen warns (unsigned beta → More info → Run anyway) — record it.
The installer wizard chrome should show Kim's icon in the title bar (gold ring round avatar) →
`04-install-wizard-icon.png`.

**C. Click through normally.** Record admin?/location/time. Confirm uninstall registry shows
**0.9.3** AND has the Kim icon:

```powershell
Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
                 "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object { $_.DisplayName -like "KimCad*" } |
  Select-Object DisplayName,DisplayVersion,DisplayIcon
```

→ `04-uninstall-registry.txt`. The `DisplayIcon` value should resolve to `kim.ico`.

---

## Phase 3 — BUILD-IDENTITY GATE  *(all four; evidence each)*

1. **Source commit + version** — `verify_install.py <INSTALL_DIR>` ends `VERIFY-INSTALL: ALL GREEN`,
   build reflects `0.9.3` / `<RC-COMMIT-SHA>` (About/Settings or verifier) → `05-verify-install.txt`.
2. **Model** `qwen2.5:7b` named as the planner (Settings → AI / `kimcad models`) → `06-model.txt`.
3. **Landing chips** — exactly: `an 80 × 60 × 40 mm project box with a lid`, `a desk cable clip for
   an 8 mm cable`, `a round trinket dish, 90 mm across` → `07-landing-chips.png`.
4. **COLD-START MARKER (carried forward from d007).** With NO Ollama present, open first-run wizard
   → **"Set up your AI"** step. Confirm it offers a **"Set up KimCad's AI"** button. It must **NOT**
   say *"Get Ollama → install it → check again"* and must **NOT** redirect to ollama.com.
   → `08-coldstart-setup-button.png`.

---

## Phase 4 — KIM EVERYWHERE: the branding survival checklist  *(NEW — the headline of this directive)*

For each surface below, screenshot the surface and confirm Kim's face + gold accent are present.
**Each missing surface is a Major finding.** Reference image: the 1254px Kim master Scott shipped.

### 4a. Desktop shortcut icon  *(`10-desktop-shortcut.png`)*
The installer creates a desktop shortcut. The shortcut icon must show Kim's round avatar (gold ring),
NOT the Python snake. Screenshot the desktop with the shortcut visible at standard icon size.

### 4b. Start-menu tile  *(`11-start-menu-tile.png`)*
Open Start. Find KimCad. The tile must show Kim's avatar. Screenshot.

### 4c. Native app window — title bar  *(`12-window-titlebar.png`)*
Double-click the desktop shortcut. The app window opens. The **title bar** (top-left) must show
Kim's round avatar. Screenshot the window's top-left corner at native zoom.

### 4d. Taskbar icon  *(`13-taskbar.png`)*
The taskbar icon for the running KimCad window must show Kim. Screenshot the Windows taskbar.

### 4e. Alt-Tab thumbnail  *(`14-alttab.png`)*
Press Alt+Tab. The KimCad thumbnail in the switcher must show Kim's avatar in its app-identity badge.
Screenshot the Alt-Tab overlay.

### 4f. First-run wizard — rail  *(`15-wizard-rail.png`)*
On first launch (clean machine), the wizard opens. The left rail must show a ~56px round Kim avatar
with a gold ring, ABOVE the "KimCad" wordmark. Screenshot the wizard's left rail close-up.

### 4g. First-run wizard — Welcome step  *(`16-wizard-welcome.png`)*
The first wizard step ("Welcome to KimCad") must show a large (~120px) round Kim portrait CENTERED
above the H1, with a gold ring. Screenshot the full Welcome panel.

### 4h. Topbar logo (after wizard or skip-setup)  *(`17-topbar-logo.png`)*
Once in the workspace/landing, the topbar logo must be a 32px round Kim (gold ring) — NOT a
geometric shape, NOT a wordmark-only. Screenshot the topbar.

### 4i. Empty-state Landing — hero  *(`18-landing-hero.png`)*
The empty/landing screen ("What do you want to make today?") must show a 96px round Kim ABOVE the
H1, with a gold ring. Screenshot the full landing hero.

### 4j. Chat avatars (during design)  *(`19-chat-avatars.png`)*
Submit a design prompt. In the conversation thread (left column), every assistant turn shows a 28px
round Kim avatar (gold ring) — NOT a CSS-background-image placeholder, NOT an `aria-hidden` span.
Inspect-element check: the avatar is a real `<img alt="Kim">` (a11y-correct). Screenshot.

### 4k. Browser-tab / WebView2 chrome favicon  *(`20-favicon.png`)*
The WebView2 window chrome — if any tab-strip-like UI is visible — must show Kim's icon. (For a
pure pywebview app this may be subsumed by the title bar; if so, note it.) Screenshot.

### 4l. Palette is the new Zen aesthetic  *(`21-palette-light.png`, `22-palette-dark.png`)*
Open Settings (or use the topbar toggle) and flip light/dark. Confirm:
- **Light mode:** warm white surface, deep-black text, **gold accent `#d4af37` (or visually
  equivalent)** on the topbar wordmark "Cad" + on focus rings + on the primary button. **No
  terracotta orange anywhere.**
- **Dark mode:** deep-black surface (`#0c0a06`-ish), warm white text, **brighter gold
  `#e3c24f`-ish** on accents. **No orange.**
Screenshot one full workspace view in each mode.

### 4m. A11y — screen reader names Kim  *(`23-a11y.txt`)*
Turn on Narrator briefly. Tab over the topbar logo. It should announce something like "Kim, image"
or "Kim, graphic" — NOT silence (the old behaviour). Same for chat avatars during a design. Record
the announcements as a text dump.

---

## Phase 5 — Managed-engine cold setup  *(re-prove directive-007 didn't regress)*

Click **"Set up KimCad's AI"** on the now-clean wizard:
- **Engine downloads in-app** (~1.4 GB) — NOT a redirect to ollama.com → `30-engine-fetch.png`.
- **Models download** (~7.7 GB) → `31-model-fetch.png`. Record total time/size.
- AI reads **Ready** without you having installed Ollama → `32-ai-ready.png`.
- **KimCad's engine is its OWN, not a system install:** `Get-Command ollama` STILL NOT FOUND;
  `Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"` STILL False; managed `ollama` process
  IS running (`Get-Process ollama`); engine lives under `%LOCALAPPDATA%\KimCad\ollama\ollama.exe`
  → `33-managed-engine.txt`.
- **If the wizard dead-ends, redirects to ollama.com, or can't reach a working AI without a manual
  Ollama install → Critical (the d007 fix regressed).**

---

## Phase 6 — Core end-to-end (real managed model + real GPU)  *(re-prove directive-007/008)*

For **each** of the 3 curated chips: screenshot part + viewport (`40-chipK-<name>.png`), record model
+ time; devtools console (`41-chipK-console.txt`) + WebGL renderer string verbatim (`42-webgl.txt`).
Then: a custom dimensioned prompt → design → slider re-render → **slice → a real `.3mf` print file**
→ export `.3mf` + `.stl` (sizes, `43-export.txt`); photo/sketch on-ramp seed.

**Branding-during-design spot check** (`44-branding-during-design.png`): take a screenshot of the
workspace MID-DESIGN with the conversation thread showing 3+ chat avatars + the topbar Kim + the
gold accent on the active state — prove the branding holds through real product use, not just on
the empty landing.

---

## Phase 7 — Uninstall + clean residue  *(prove the uninstall flow is also branded + correct)*

1. Apps & Features → KimCad → Uninstall. The uninstall confirmation dialog should show Kim's icon
   (top-left of the dialog) → `50-uninstall-dialog.png`. Click through it.
2. The "remove your KimCad data?" prompt: select **YES** to clean.
3. After uninstall:
   - `Test-Path "$env:LOCALAPPDATA\KimCad"` → False (managed engine + models gone — d007's
     uninstall-orphan minor must stay fixed).
   - `Test-Path "$env:USERPROFILE\.kimcad"` → True (saved designs preserved — by design).
   - Uninstall registry entry for KimCad is gone.
   - `Get-Process ollama` → no managed engine running.

→ `51-post-uninstall.txt`.

---

## Phase 8 — Report

Write `tester/reports/report-009.md` starting with the nonce on line 1. Sections:
1. Verdict (SHIP / SHIP-with-Minor / HOLD).
2. Build identity (Phase 1 + 3 results).
3. Branding survival checklist (Phase 4) — table: each surface PASS / FAIL / NOT-APPLICABLE with
   evidence file ref + 1-line note.
4. Functional regression check (Phase 5 + 6 results vs directive-007/008 baseline).
5. Uninstall (Phase 7) — any residue?
6. Findings (Blocker → Nit) with evidence refs.
7. Machine context (Phase 0 dump).

Then `git add tester/reports/report-009.md tester/evidence/009/ && git commit -m "TESTER d009 COMPLETE: ..." && git push origin tester`.

---

## Done state

- All branding surfaces (Phase 4a–4m) PASS → SHIP for branding.
- All Phase 5–6 functional checks pass equivalently to 0.9.2 → SHIP for function.
- Uninstall is clean → SHIP.
- DEV will then promote `v0.9.3-rc1` → final `v0.9.3` tag.
