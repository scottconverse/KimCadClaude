# KimCad Tester Directive 004 — Clean-Machine Acceptance Test (0.9.0b4)

**NONCE:** `KCT-004-20260616-B4`
**Release:** v0.9.0b4
**Download:** https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.0b4
**Expected SHA-256:** `532B3F8B3BFE70ACD418C9AA99E1E9FF5397A896D2421A268A00DF552C066D2C`
**Expected size:** 203,472,459 bytes

---

## Hard rules (same as directive-003)

1. **Evidence first.** Every claim in the report must cite a file you committed under
   `tester/evidence/004/` before making the claim. No exceptions.
2. **Phase 3 build-identity gate.** Before you proceed past Phase 3, three things must all
   be true simultaneously in committed artifacts: (a) `model = qwen2.5:7b` in model-status
   output — NOT `gemma4:e4b`; (b) landing page shows the three exact chips ("an 80 × 60 × 40 mm
   project box with a lid", "a desk cable clip for an 8 mm cable", "a round trinket dish,
   90 mm across"); (c) `verify_install.py` ends `VERIFY-INSTALL: ALL GREEN`. If any of the
   three fails, STOP and report — do not proceed to Phases 4–7.
3. **Report goes to** `tester/reports/report-004.md`. Append a STATUS line after each phase.

---

## Phases

### Phase 0 — Confirm clean machine
Evidence files: `01-systeminfo.txt`, `02-clean.txt`

Capture:
```
winver; systeminfo | Select-String "OS Name","Total Physical","Processor"
Get-Command node,ollama,kimcad -ErrorAction SilentlyContinue | Select-Object Name,Source
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object DisplayName -like "*KimCad*" | Select-Object DisplayName,DisplayVersion
```

PASS: No prior KimCad install, no Ollama, no Node. WebView2 Runtime present.

---

### Phase 1 — Download + SHA-256 verify
Evidence files: `03-sha256.txt`, `03-published-SHA256SUMS.txt`

```powershell
$f = "$env:TEMP\KimCad-Setup-0.9.0b4.exe"
Invoke-WebRequest -Uri "https://github.com/scottconverse/KimCadClaude/releases/download/v0.9.0b4/KimCad-Setup-0.9.0b4.exe" -OutFile $f
(Get-FileHash $f -Algorithm SHA256).Hash | Tee-Object tester/evidence/004/03-sha256.txt
(Get-Item $f).Length | Tee-Object -Append tester/evidence/004/03-sha256.txt
Invoke-WebRequest -Uri "https://github.com/scottconverse/KimCadClaude/releases/download/v0.9.0b4/SHA256SUMS.txt" -OutFile tester/evidence/004/03-published-SHA256SUMS.txt
```

PASS: SHA-256 matches `532B3F8B3BFE70ACD418C9AA99E1E9FF5397A896D2421A268A00DF552C066D2C`
and size is 203,472,459 bytes.

---

### Phase 2 — Silent per-user install
Evidence files: `04-install.log`, `04-installed.txt`

```powershell
Start-Process -FilePath $f -ArgumentList "/VERYSILENT /CURRENTUSER /SUPPRESSMSGBOXES /NORESTART /LOG=`"$env:TEMP\kimcad-install.log`"" -Wait
Copy-Item "$env:TEMP\kimcad-install.log" tester/evidence/004/04-install.log
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object DisplayName -like "*KimCad*" | Select-Object DisplayName,DisplayVersion,InstallLocation |
  Tee-Object tester/evidence/004/04-installed.txt
```

PASS: Exit 0, install dir exists under `%LOCALAPPDATA%\Programs\KimCad`, registry shows
`KimCad 0.9.0b4`.

---

### Phase 3 — BUILD-IDENTITY GATE (must commit all three before proceeding)
Evidence files: `05-verify-install.txt`, `06-model-status.txt`, `07-landing-chips.png`,
`08-webgl-renderer.txt`

**Step 3a — verify_install:**
```powershell
$root = "$env:LOCALAPPDATA\Programs\KimCad"
& "$root\python\python.exe" "$root\kimcad_launcher.py" --verify 2>&1 |
  Tee-Object tester/evidence/004/05-verify-install.txt
```
PASS: Last line is `VERIFY-INSTALL: ALL GREEN`.

**Step 3b — launch the app, check model:**
Start KimCad. Open Settings → About / Model Status. Capture:
```
tester/evidence/004/06-model-status.txt   ← text: model name + running state
tester/evidence/004/09-settings-model.png ← screenshot of the Settings model card
```
PASS: `model = qwen2.5:7b` (NOT gemma4:e4b or anything else).

**Step 3c — landing chips screenshot:**
Take a screenshot of the landing page showing all three chip buttons.
`tester/evidence/004/07-landing-chips.png`
PASS: Chips read exactly "an 80 × 60 × 40 mm project box with a lid",
"a desk cable clip for an 8 mm cable", "a round trinket dish, 90 mm across".

**Step 3d — WebGL renderer:**
In the app's browser context (or Chrome pointed at the KimCad server), run:
```javascript
const g = document.createElement('canvas').getContext('webgl2');
const ext = g.getExtension('WEBGL_debug_renderer_info');
[g.getParameter(ext.UNMASKED_VENDOR_WEBGL), g.getParameter(ext.UNMASKED_RENDERER_WEBGL)]
```
Save verbatim output to `tester/evidence/004/08-webgl-renderer.txt`.
PASS: Does NOT contain "SwiftShader". Real GPU via ANGLE/D3D11 preferred.

---

### Phase 4 — Ollama + model setup
Evidence files: `11-ollama.txt`

```powershell
winget install Ollama.Ollama --scope user --silent --accept-source-agreements --accept-package-agreements
ollama pull qwen2.5:7b
ollama pull qwen2.5vl:3b
ollama list | Tee-Object tester/evidence/004/11-ollama.txt
```

Restart KimCad so it detects the running models. Check model-status shows both `running: true`
and `model_present: true`.

---

### Phase 5a — 3 curated chips on qwen2.5:7b
Evidence files: `12-chip1-project-box.png`, `12-chip1-console.txt`,
`13-chip2-cable-clip.png`, `13-chip2-console.txt`,
`14-chip3-trinket-dish.png`, `14-chip3-console.txt`

Click each landing chip in order. Wait for the 3-D viewport to render. Capture:
- A screenshot of the rendered part
- The browser console log (should be EMPTY — no errors, no warnings)
- Note the time and Readiness score shown

PASS: All 3 chips produce a rendered 3-D part with Readiness ≥ 80, 0 console errors.

---

### Phase 5b — Custom design + slider + slice + export
Evidence files: `15-custom-design.png`, `16-slider-rerender.png`, `17-sliced.png`,
`18-export.stl`, `18-export.3mf`, `18-export.txt`

Type a freeform prompt (e.g., "a 100mm round lid with a 5mm rim"). Wait for render.
Move one parameter slider and confirm the viewport re-renders.
Slice the part (Bambu P2S / PLA or any available profile).
Export both STL and 3MF.

PASS: Slider triggers visible re-render; slice completes; both exports are non-zero files.
Save file sizes to `18-export.txt`.

---

### Phase 5c — b4-specific: model-down recovery (NEW in this directive)
Evidence files: `24-model-down.png`, `24-model-down.txt`, `24b-model-down-recovered.png`

**This test verifies the b4 Minor fix: when Ollama is stopped mid-session, the app should
show a friendly "Your local AI isn't running" message — NOT a generic server error.**

1. With KimCad running, stop Ollama: `Stop-Service -Name ollama -ErrorAction SilentlyContinue` 
   OR `taskkill /IM ollama.exe /F`
2. Attempt a design (type a prompt and submit).
3. Screenshot the result: `24-model-down.png`
4. Note the exact text shown (save to `24-model-down.txt`) — it should say something like
   "Your local AI isn't running" or "KimCad couldn't reach your local AI", NOT
   "Something went wrong on the server."
5. Restart Ollama: `ollama serve` (background) or restart the Ollama service.
6. Click the "Check again" button (or retry). Screenshot recovery: `24b-model-down-recovered.png`

PASS: Step 4 shows a friendly, actionable message (no "server error" / no stack trace).
Step 6 recovers cleanly.

---

### Phase 5d — b4-specific: coaster height constraint (NEW in this directive)
Evidence files: `26-coaster.png`, `26-coaster-console.txt`

**This test verifies the b4 Nit fix: a coaster prompt should produce a realistic thin
coaster, not a 40mm-tall one.**

Type the prompt: `a 90mm round drink coaster`
Wait for the 3-D render. Screenshot: `26-coaster.png`. Console: `26-coaster-console.txt`.

Read the on-canvas dimension labels (shown next to the part in the viewport).
Save the height dimension to `26-coaster-console.txt` (or annotate the screenshot).

PASS: The height dimension shown is ≤ 15mm. (Default is 6mm; anything above 15mm is a fail.)

---

### Phase 5e — Photo/sketch on-ramp
Evidence files: `19-photo-onramp-seed.png`, `14-input-sketch.png`

Use the "describe with a photo" or "upload a sketch" on-ramp with any real image or sketch.
Verify the vision read produces a seed (dimensions + description) and the "Use this as a
starting point" button appears.

PASS: Seed shown with at least one dimension extracted.

---

### Phase 5f — Keyboard viewport navigation
Evidence files: `20-keyboard-focus.png`, `21-keyboard-orbited.png`, `22-keyboard-zoomed.png`

Click the 3-D canvas to focus it. Use arrow keys to orbit; use +/- to zoom.
Screenshot before and after each action.

PASS: View changes on arrow keys and +/-.

---

### Phase 6 — Connector status (no printers needed)
Evidence files: `10-settings-connectors.png`

Open Settings → Connectors. Screenshot all 6 connector types.
PASS: All 6 (OctoPrint, Moonraker, PrusaLink, Duet, Marlin, Bambu) show "Not set up yet"
or similar — no traceback, no Python error.

---

### Phase 7 — Uninstall
Evidence files: `25-uninstall.txt`

```powershell
$uninst = (Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object DisplayName -like "*KimCad*").UninstallString
Start-Process -FilePath $uninst -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES" -Wait
# Verify removal
Test-Path "$env:LOCALAPPDATA\Programs\KimCad" | Tee-Object tester/evidence/004/25-uninstall.txt
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" |
  Where-Object DisplayName -like "*KimCad*" | Tee-Object -Append tester/evidence/004/25-uninstall.txt
```

PASS: Install dir gone; registry entry gone. User data at `%LOCALAPPDATA%\KimCad` and
`~/.kimcad` is RETAINED (expected — uninstaller removes the app, not your saved designs).

---

## Report format

File: `tester/reports/report-004.md`

```markdown
# Report 004 — KimCad 0.9.0b4 clean-machine acceptance test
**NONCE:** KCT-004-20260616-B4
Status: IN PROGRESS / COMPLETE

## Per-phase progress
| Phase | Result | Key evidence |
|-------|--------|-------------|
| 0 — clean machine | PASS/FAIL | ... |
...

## Findings
*(Each finding cites a committed artifact.)*

## Verdict
SHIP / HOLD — [reason]
```

Commit evidence files + report updates after each phase. Push to the `tester` branch.

---

## Done criteria

All 7 phases PASS, Phase 3 build-identity gate satisfied, 0 Blocker/Critical/Major findings,
and the two b4-specific tests (Phase 5c model-down recovery + Phase 5d coaster height) both
PASS. Dev will write `tester/SIGN-OFF-004` when criteria are met.
