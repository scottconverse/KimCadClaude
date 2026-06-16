# Report 003 — KimCad 0.9.0b3 clean-machine acceptance test
**NONCE:** `KCT-003-20260616-B3`

_Status: IN PROGRESS (appended per-phase). Tester box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI)._

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
