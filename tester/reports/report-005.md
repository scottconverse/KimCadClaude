KCT-005-20260616-B5

# Report 005 — KimCad 0.9.0b5 clean-machine acceptance test (Snapmaker U1 / multi-toolhead)
Status: COMPLETE. Box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI).

## 1. Verdict
**SHIP THE BUILD, BUT THE SNAPMAKER U1 HEADLINE IS BLOCKED.** The b5 build is sound and every
regression from b4 still passes (3/3 chips, custom design+slider+slice+export, photo on-ramp,
model-down recovery, non-geometric graceful handling, clean uninstall). The new Snapmaker U1
multi-toolhead **UI is fully built and correct** — the printer is in the catalog, the four
Extruder dropdowns appear (and collapse to one for a single-head printer), the bed is configured
to the right 270.5 × 271.0 × 270.05 mm volume, and the connector ships as a clean unconfigured
template.

**However, a real user choosing the Snapmaker U1 cannot get a print file.** Clicking
"Slice & prepare file" fails 100% of the time with `orca-slicer exited -2: Invalid option
--filament-config`. No print file is produced — only the geometry .STL export remains. This
fails the headline goal of the run ("prove the new feature works on a clean box"). Single-head
printers (Bambu P2S) slice fine and produce a real 417 KB print file, so the bug is isolated to
the multi-toolhead slice code path passing an OrcaSlicer CLI flag the bundled slicer rejects.

**One Critical finding (Snapmaker slice). No Blockers/Majors/Minors/Nits beyond it.**

## 2. Environment
AMD Ryzen 7 8745HS / Radeon 780M / 28,450 MB / Win 11 Pro build 26200, 125% DPI. SER8 mini-PC.
WebView2 149.0.4022.69 present, no Node. `health`: `{"version":"0.9.0b5","openscad":true,
"orcaslicer":true,"cadquery":false}`. Evidence: `01-systeminfo.txt`, `02-clean.txt`.
(Test note: UI driven via local Chrome over CDP against the app's own server on this box — real
780M GPU — because interactive computer-use approval is unavailable in this autonomous run. PNGs
are real screenshots of the installed app. App server started via the installed
`kimcad_launcher.py web --port 8765`.)

## 3. Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS (1 disclosed deviation) | `01-systeminfo.txt`,`02-clean.txt` — no prior KimCad, no Node, WebView2 present. Deviation: Ollama 0.30.8 + qwen2.5:7b + qwen2.5vl:3b pre-present (left from ACCEPTED b4 per SIGN-OFF-004 item 3); not re-pulled. |
| 1 — download + SHA-256 | PASS | `03-sha256.txt` — 204,770,673 bytes; sha `f4bd7af7…43e63` = expected exactly. |
| 2 — install (silent per-user) | PASS | `04-installed.txt`,`04-install.log` — exit 0, ~21s, `%LOCALAPPDATA%\Programs\KimCad`; reg `KimCad 0.9.0b5` v`0.9.0b5` (HKCU), no admin. |
| 3 — BUILD-IDENTITY GATE | **PASS (all 4)** | 3a model `qwen2.5:7b` `05-model.txt`+`09-settings-model.png`. 3b 3 exact chips `06-landing-chips.png`. 3c `07-verify-install.txt` → `VERIFY-INSTALL: ALL GREEN` (v0.9.0b5). 3d **Snapmaker U1 in picker** `08-snapmaker-in-picker.png`+`08-snapmaker-check.txt` (`<option value="snapmaker_u1">Snapmaker U1</option>`). |
| 4 — Ollama + models | PASS (pre-present) | `09-ollama.txt` — qwen2.5:7b (4.7 GB) + qwen2.5vl:3b (3.2 GB); model-status running+present. |
| 5 — core regression (3 chips) | **PASS (3/3)** | All 3 chips built real 3-D parts, 0 console errors. chip1 box `10-chip1-project-box.png` 36s R86; chip2 clip `11-chip2-cable-clip.png` 34s R92; chip3 dish `12-chip3-trinket-dish.png` 28s R92. Consoles `10/11/12-*-console.txt` (0). WebGL `13-webgl-renderer.txt`. |
| 5 — custom design+slider+slice+export | PASS | "a 75mm square drink coaster, 4mm thick" 22s R92; 5 sliders (od/h/rim_w/rim_h/floor_t), h max=15mm (b4 fix holds); od slider moved 75→128 re-rendered. STL 38,284 B + 3MF 9,620 B. `14-custom-design.png`,`15-slider-rerender.png`,`16-sliced.png`,`17-export.{stl,3mf,txt}`. 0 console errors. |
| 5 — photo/sketch on-ramp | PASS | Sketch attached via CDP DOM.setFileInputFiles → "Reading your photo…" seeded. `18-photo-onramp.png`,`18-photo-console.txt`. |
| **5b — Snapmaker U1 / multi-toolhead** | **PARTIAL — UI all PASS, SLICE FAILS (Critical)** | See sub-table below. |
| 6 — model-down recovery | PASS | Ollama stopped → submit → "KimCad couldn't reach your local AI. Make sure Ollama is running, then try again." + "Try again" button. NOT a 500/traceback. 0 console errors. `27-model-down.png`,`27-model-down.txt`. (b4 fix still holds.) |
| 6 — non-geometric prompt | PASS | "a feeling of nostalgia" → graceful clarifying question ("What overall size… key dimensions in mm"). No traceback. Geometric refine chips NOT offered (no part exists). `28-non-geometric.png`,`28-non-geometric.txt`. |
| 7 — uninstall | PASS | Silent uninstall — install dir GONE, HKCU reg GONE, Start-Menu shortcut GONE. User data `%LOCALAPPDATA%\KimCad` RETAINED, `~/.kimcad` RETAINED. Clean (no file-lock this run — app-server python killed before uninstall). `04-installed.txt`. |

### Phase 5b sub-table (Snapmaker U1 / multi-toolhead — the headline)
| Step | Result | Evidence |
|---|---|---|
| 1 — picker + build volume | PASS | Snapmaker U1 selectable in Export picker (`20-snapmaker-selected.png`). Bed = **270.5 × 271.0 × 270.05 mm** confirmed in the bundled OrcaSlicer profile (`20-snapmaker-bed.txt`: `printable_area 0.5x1;270.5x1;270.5x271;0.5x271`, `printable_height 270.05`). |
| 2 — four Extruder dropdowns | **PASS** | Selecting U1 replaces the single Material dropdown with **Extruder 1–4**, each PLA/PETG/TPU/ABS-ASA, with helper note "Assign a filament to each extruder — the slicer tunes temperature and retraction per slot." `21-four-extruder-dropdowns.png`, `20-5b-summary.txt` (4 material selects, labels Extruder 1..4). |
| 3 — single-head regression | **PASS** | Switching to Bambu P2S shows **one** "Material" dropdown, zero Extruder labels — multi-head UI is correctly gated on toolhead_count, not always-on. `22-singlehead-one-dropdown.png`. |
| 4 — distinct-material multi-material slice | **FAIL (Critical)** | Snapmaker U1, Extruder 1=PLA/2=PETG/3=TPU/4=ABS, click "Slice & prepare file" → **`orca-slicer exited -2: Invalid option --filament-config`**. No print file produced; only "Download 3D model (.STL)" remains (no "Download print file (.3mf)"). `23-multimaterial-slice.png`, `24-multimaterial-3mf.txt`, `24-slice-inspect.txt`, `24-slice-scope.txt`. |
| 5 — per-slot summary | **FAIL (consequence of step 4)** | Because the slice errors out there is no post-slice summary line naming per-extruder materials. The pre-slice assignment UI is correct, but no successful slice → no summary. `24-multimaterial-3mf.txt`. |
| 6 — connector listed, not-set-up | **PASS** | Settings → Printer connections shows **Snapmaker U1** as an unconfigured template ("not set up yet"), clean message, **no traceback**. `26-snapmaker-connection.png`. |
| 7 — pre-send not-set-up | PASS | Selecting the Snapmaker connection shows the clean not-set-up state, no error (no hardware attached). Covered by `26-snapmaker-connection.png`. |

**Scope proof that the bug is Snapmaker-specific (`24-slice-scope.txt`):**
- A. Bambu P2S single-head slice → **OK**, real print file `part_bambu_p2s_pla.gcode.3mf` (416,960 B) downloadable. Evidence `22-bambu-print-file.3mf`, `22-bambu-slice.txt`, `22-singlehead-slice-ok.png`.
- B. Snapmaker U1, all 4 extruders = PLA → **same `--filament-config` error**.
- C. Snapmaker U1, 4 distinct materials → **same `--filament-config` error**.
The failure is triggered by selecting the Snapmaker U1 (multi-toolhead) path, independent of whether materials differ.

## 4. Findings
*(Every finding cites a committed artifact under `evidence/005/`.)*

- **[CRITICAL] Snapmaker U1 multi-toolhead slice cannot produce a print file — `orca-slicer exited -2: Invalid option --filament-config`.**
  The headline b5 feature's UI is complete and correct, but the actual slice fails 100% of the
  time for the Snapmaker U1. KimCad's multi-extruder slice path invokes the bundled OrcaSlicer
  with an unsupported CLI flag `--filament-config` (confirmed absent from `orca-slicer --help`).
  Single-head printers don't pass this flag and slice normally (Bambu produced a 417 KB print
  file). A clean-box user who picks the one new printer, assigns filaments, and clicks
  "Slice & prepare file" gets a red error and only the geometry `.STL` — no print file.
  Reproduces with same-material and distinct-material assignment alike.
  **Likely fix:** use OrcaSlicer's real multi-filament flag (e.g. `--load-filaments`) / correct
  argument format for the bundled build. Evidence: `24-multimaterial-3mf.txt`,
  `24-orca-rootcause.txt`, `24-slice-inspect.txt`, `24-slice-scope.txt`, `23-multimaterial-slice.png`,
  and the contrasting success `22-bambu-print-file.3mf` / `22-bambu-slice.txt`.

**No Blockers** (the build installs/launches/passes the identity gate; all non-Snapmaker flows work).
**No Majors, Minors, or Nits** beyond the Critical above. The two b4 fixes still hold (model-down
friendly message; coaster h max = 15 mm).

## 5. Model performance on this box (CPU/iGPU, qwen2.5:7b) + WebGL
| Design | Time | Readiness |
|---|---|---|
| chip1 — 80×60×40 project box | 36.1 s | 86 |
| chip2 — desk cable clip (8 mm) | 34.1 s | 92 |
| chip3 — round trinket dish 90 mm | 28.1 s | 92 |
| custom — 75 mm square coaster | 22.0 s | 92 |
| chip3 re-run (5b design) | 74 s | 92 |
All within the directive's 30–120 s "normal" band (one chip3 re-run at 74 s = normal CPU variance).
Models pre-present (no pull this run).

**WebGL renderer string (verbatim, `13-webgl-renderer.txt`):**
`ANGLE (AMD, AMD Radeon 780M Graphics (0x00001900) Direct3D11 vs_5_0 ps_5_0, D3D11)`
Real iGPU via ANGLE→D3D11, not SwiftShader. **0 console errors** across every design.

## 6. Open questions for DEV
1. **Critical above:** which OrcaSlicer CLI flag should the multi-toolhead path use? `--filament-config`
   is not accepted by the bundled `orca-slicer.exe`. (Single-head path works, so only the
   multi-extruder branch needs the fix.) Once fixed, re-run Phase 5b steps 4–5 to confirm a real
   multi-material `.3mf` and the per-slot summary line.
2. The Export panel's status badge reads "mock · Ready · simulated" — this refers to the
   Direct-printing connection (no hardware), not the slice. Confirm that's intended labeling; it's
   easy to misread as "the slice is simulated."
3. `verify_install.py` was used from the repo (the directive's `kimcad_launcher.py --verify` flag is
   still not implemented — carried over from report-004 open item 1). Update the directive template.
4. Ollama + the two qwen models remain installed on the box for the re-test of the fix.
