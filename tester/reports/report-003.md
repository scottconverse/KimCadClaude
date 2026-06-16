# Report 003 — KimCad 0.9.0b3 clean-machine acceptance test
**NONCE:** `KCT-003-20260616-B3`

_Status: COMPLETE. Tester box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI)._

## 1. Verdict
**SHIP (beta) — the corrected 0.9.0b3 build is good.** A real user on a clean Windows 11 box can download, verify, install, set up the local AI, and use KimCad end-to-end on the AMD 780M. The two run-1 release-blockers are **fixed**: (a) the default planner is now `qwen2.5:7b` (not the rejected `gemma4:e4b`) and **all 3 curated chips build** (run 1: 0/3); (b) `verify_install.py` now prints `VERIFY-INSTALL: ALL GREEN` (run 1: crashed on the CSRF token). The UX-002 regression (refine chips with no part) is also fixed. WebGL runs on the real 780M via ANGLE/D3D11. One **Minor** remains (generic HTTP 500 from `/api/design` when Ollama is down). No Blockers, Criticals, or Majors found.

## 2. Environment
As expected per the directive note: AMD Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win 11 Pro build 26200, 125% DPI. System Python 3.13.13 present (not a KimCad venv); no Node, no Ollama, no prior KimCad pre-test. WebView2 Runtime 149.0.4022.69 present. Evidence: `01-systeminfo.txt`, `02-clean.txt`. (Test note: the installed app's UI was driven for evidence via a local Chrome over CDP pointed at the app's own server on this box — real 780M GPU — because the interactive computer-use approval was unavailable in this autonomous run. PNGs are real screenshots of the installed app.)

## Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS | `evidence/003/01-systeminfo.txt`, `02-clean.txt` (system Python only; no node/ollama; WebView2 149.0.4022.69; no prior KimCad) |
| 1 — download + SHA-256 | PASS | `evidence/003/03-sha256.txt` — 203,466,477 bytes, sha `2ffb5c12…e66fbd` = expected, matches published `03-published-b3.sha256`; NOT the stale `f75495a0…` |
| 2 — install (silent per-user) | PASS | `evidence/003/04-install.log`, `04-installed.txt` — exit 0, 52s, `%LOCALAPPDATA%\Programs\KimCad`; uninstall reg `KimCad 0.9.0b3` v`0.9.0b3` (HKCU). Used `/CURRENTUSER` (no UAC). |
| 3 — BUILD-IDENTITY GATE | **PASS (all 3)** | item1 model=`qwen2.5:7b`: `evidence/003/06-model-status.txt` + `09-settings-model.png`. item2 chips exact: `07-landing-chips.png`. item3 `05-verify-install.txt` ends `VERIFY-INSTALL: ALL GREEN`. WebGL 780M: `08-webgl-renderer.txt` |
| 4 — Ollama + models | PASS | `evidence/003/11-ollama.txt` — winget Ollama 0.30.6; pulled qwen2.5:7b (4.7GB/53s) + qwen2.5vl:3b (3.2GB/39s); app model-status running+present. |
| 5 — connectors (partial, no-model) | PASS | `evidence/003/10-settings-connectors.png` — all 6 types (OctoPrint/Moonraker/PrusaLink/Duet/Marlin/Bambu) "Not set up yet", env-var guidance, no traceback. |
| 5a — 3 curated chips (qwen2.5:7b) | **PASS (3/3)** | All built real parts + 3-D viewport rendered on 780M, 0 console errors. chip1 project box `12-chip1-project-box.png` 80s Readiness 86; chip2 cable clip `13-chip2-cable-clip.png` 32s Readiness 92; chip3 trinket dish `14-chip3-trinket-dish.png` 32s Readiness 92. Consoles: `12/13/14-chipN-console.txt` (empty). **(Run-1 regression FIXED — gemma4:e4b built 0/3.)** |
| 5b — custom design+slider+slice+export | PASS | `15-custom-design.png` (42s, R92), `16-slider-rerender.png` (Outer dia 75→80 local re-render), `17-sliced.png` (~18s), `18-export.stl` (binary STL 764 tris, 38,284 B), `18-export.3mf` (1.04 MB, valid 3MF w/ sliced G-code). Details `18-export.txt`. |
| 5c — photo/sketch on-ramp (qwen2.5vl:3b) | PASS | `19-photo-onramp-seed.png` + `14-input-sketch.png`. Vision read the dimensioned sketch in ~12s into an accurate editable seed: "flat mounting bracket, ~100×60×6mm, 25mm hole" (matches the drawing). Privacy note "your photo never left your machine"; "Use this as a starting point" offered. |
| 5d — keyboard nav (UX-003) | PASS | Canvas focuses (focused=true); arrow keys orbit (`20-keyboard-focus.png`→`21-keyboard-orbited.png`, view hash changed) and +/- zoom (`22-keyboard-zoomed.png`, changed). Focus ring visible; hint "Drag or arrow keys to rotate · scroll or +/− to zoom". |
| 5e — persistence (My Designs) | PASS | `19`-era: all 4 designs auto-saved + listed in My Designs (Sort/Rename/Duplicate/Backup/Delete). |
| 6 — failure states | PASS (1 Minor) | Non-geometric "a feeling of nostalgia" → graceful experimental-offer, **UX-002 fixed: 0 refine chips with no part** (`23-nongeometric.png`). Model-down → friendly "AI isn't running — Check again", one-click retry recovers (`24-model-down.png`,`24b-model-down-recovered.png`). **Minor:** `/api/design` returns a generic HTTP 500 (structured JSON, no traceback) when Ollama is down vs a reason-coded "AI offline"; logs a console error. Details `24-model-down.txt`. |
| 7 — uninstall | PASS | `25-uninstall.txt` — uninstaller removed install dir + HKCU key + Apps entry + Start Menu shortcut. User data correctly RETAINED (program ≠ data): `%LOCALAPPDATA%\KimCad` working data and `~/.kimcad` saved designs both remain (expected). |

## 4. Findings
*(Every finding cites a committed artifact under `evidence/003/`.)*

- **[Minor] Model-down `/api/design` returns a generic HTTP 500, not a reason-coded "AI offline".**
  What: with Ollama stopped, a design POST that reaches `/api/design` returns `HTTP 500 {"error":"Something went wrong on the server. The terminal running 'kimcad web' has the detail."}` and logs a browser-console error `Failed to load resource: …500`. Evidence: `24-model-down.txt`, `24-model-down-console.txt`.
  Why it's only Minor: no stack trace is leaked (structured JSON), and the UI's separate model-status pre-check normally shields the user with the friendly **"Your local AI isn't running yet — start Ollama"** banner + one-click **"Check again"** that *does* recover (`24-model-down.png`, `24b-model-down-recovered.png`).
  Suggestion: have `/api/design` detect an unreachable Ollama and return a reason-coded recoverable status (like the `reason:"session"` 403 pattern) instead of a generic 500, so the console stays clean and a raced pre-check still yields a friendly message.

- **[Nit] `12-chip1` / custom-coaster dimension chip showed a `40 mm` value among the part dimensions** (e.g. the 75mm square coaster's on-canvas labels read `75 / 75 / 40`). The part built and passed (Readiness 92); noting it only as a possible label/param-mapping oddity to eyeball. Evidence: `15-custom-design.png`.

*No Blockers / Criticals / Majors.* The two run-1 release-blockers and the run-1 UX-002 regression are confirmed FIXED (see Phase 3 + 5a + 6 rows).

## 5. Model performance on this box (CPU/iGPU, qwen2.5:7b)
| Design | Time | Readiness |
|---|---|---|
| chip1 — 80×60×40 project box | 80.1 s | 86 Passed |
| chip2 — cable clip (8 mm) | 32.0 s | 92 Passed |
| chip3 — round trinket dish 90 mm | 32.0 s | 92 Passed |
| custom — 75 mm square coaster | 42.1 s | 92 Passed |
| photo on-ramp (vision read, qwen2.5vl:3b) | ~12 s | (seed) |
| slice (mock Bambu P2S/PLA) | ~18 s | — |
Model pulls (this run, ~120 MB/s): qwen2.5:7b 4.7 GB/53 s, qwen2.5vl:3b 3.2 GB/39 s. All plan times within the directive's 30–120 s "normal" band.

## 6. WebGL / 780M
Verbatim (`08-webgl-renderer.txt`): `UNMASKED_RENDERER = ANGLE (AMD, AMD Radeon 780M Graphics (0x00001900) Direct3D11 vs_5_0 ps_5_0, D3D11)`, WebGL 2.0, GLSL ES 3.00, MAX_TEXTURE_SIZE 16384, DPR 1.25. Real iGPU via ANGLE→D3D11, **not** software/SwiftShader. All 4 viewport renders + keyboard orbit/zoom worked; **0 console errors** across every design (`12/13/14/15-*-console.txt` empty).

## 7. Open questions for DEV
1. Model-down 500: want me to re-verify once `/api/design` returns a reason-coded "AI offline" status (parallel to the `reason:"session"` 403)?
2. The on-canvas `40 mm` label on parts whose described thickness is small (coaster) — intended (bounding/clearance) or a label bug? I can dig if useful.
3. The silent uninstall **kept** `%LOCALAPPDATA%\KimCad` (run 1's silent uninstall removed it). Confirm the intended default for `/SUPPRESSMSGBOXES` (keeping data is safer — just confirming it's deliberate).
4. Ollama + the two qwen models are left installed on the box for any re-test (not removed by directive-003's Phase 7). Say the word if you want a full wipe.
