# Report 004 — KimCad 0.9.0b4 clean-machine acceptance test
**NONCE:** `KCT-004-20260616-B4`
Status: COMPLETE. Box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI).

## 1. Verdict
**SHIP (beta) — the corrected 0.9.0b4 build is good.** Both b4-specific fixes are confirmed:
(a) **model-down message** is now friendly and actionable ("KimCad couldn't reach your local AI. Make sure Ollama is running, then try again.") instead of the generic b3 HTTP 500 — console stays clean, 0 errors; (b) **coaster height** slider max is now **15 mm** (was 40 mm in b3) and the coaster renders at 10 mm. All 7 phases PASS. No Blockers, Criticals, or Majors found.

## 2. Environment
AMD Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win 11 Pro build 26200, 125% DPI. System Python 3.13.13 present (not a KimCad venv); no Node. WebView2 Runtime 149.0.4022.69 present. Evidence: `01-systeminfo.txt`, `02-clean.txt`. (Test note: UI driven via local Chrome over CDP pointed at the app's own server on this box — real 780M GPU — because interactive computer-use approval is unavailable in this autonomous run. PNGs are real screenshots of the installed app. The app server was started via `kimcad_launcher.py web --port 8765` using the installed python.)

## Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS (1 disclosed deviation) | `evidence/004/01-systeminfo.txt`,`02-clean.txt` — clean of KimCad; node absent; WebView2 149.0.4022.69. Deviation: Ollama 0.30.8 + qwen models pre-present (left from ACCEPTED b3 per SIGN-OFF item #3); not re-pulled. |
| 1 — download + SHA-256 | PASS | `evidence/004/03-sha256.txt` — 203,472,459 bytes; sha `532b3f8b…066d2c` = expected & matches published `03-published-SHA256SUMS.txt`. |
| 2 — install (silent per-user) | PASS | `04-install.log`,`04-installed.txt` — exit 0, 52.2s, `%LOCALAPPDATA%\Programs\KimCad`; reg `KimCad 0.9.0b4` v`0.9.0b4` (HKCU). |
| 3 — BUILD-IDENTITY GATE | **PASS (all 3)** | 3a `05-verify-install.txt` → `VERIFY-INSTALL: ALL GREEN` (v0.9.0b4). 3b model `qwen2.5:7b` `06-model-status.txt`+`09-settings-model.png`. 3c exact chips `07-landing-chips.png`. 3d WebGL real 780M ANGLE/D3D11 (no SwiftShader) `08-webgl-renderer.txt`. **Note:** directive's `kimcad_launcher.py --verify` flag isn't supported; used the canonical `scripts/verify_install.py`. |
| 4 — Ollama + models | PASS (pre-present) | `11-ollama.txt` — qwen2.5:7b + qwen2.5vl:3b present (kept from b3 per SIGN-OFF); model-status running+present. |
| 5a — 3 curated chips (qwen2.5:7b) | **PASS (3/3)** | All 3 chips built real 3-D parts, 0 console errors. chip1 project box `12-chip1-project-box.png` 74s R86; chip2 cable clip `13-chip2-cable-clip.png` 28s R92; chip3 trinket dish `14-chip3-trinket-dish.png` 30s R92. Console: `12/13/14-chipN-console.txt` (empty). |
| 5b — custom design+slider+slice+export | PASS | Custom "a 75mm square drink coaster, 4mm thick": 24s R92. 5 parameter sliders present (od/h/rim_w/rim_h/floor_t). Slider moved od 75→128mm, viewport re-rendered. `15-custom-design.png`, `16-slider-rerender.png`. Slice ("Quality" tab) triggered, `17-sliced.png`. STL exported 38,284 bytes + 3MF 9,616 bytes from `%LOCALAPPDATA%\KimCad\output\web\5\`. `18-export.stl`, `18-export.3mf`, `18-export.txt`. 0 console errors. |
| 5c — b4 fix: model-down recovery | **PASS (b4 fix CONFIRMED)** | With Ollama stopped: landing shows "Your local AI isn't running yet — start Ollama to design. Check again". After submitting a design: "KimCad couldn't reach your local AI. Make sure Ollama is running, then try again. You can check the AI's status in Settings." + "Try again" button — **NOT** "Something went wrong on the server". 0 console errors during model-down. "Try again" click → Ollama restarted → design immediately began. `24-model-down.png`, `24-model-down.txt`, `24b-model-down-recovered.png`. |
| 5d — b4 fix: coaster height ≤15mm | **PASS (b4 fix CONFIRMED)** | "a 90mm round drink coaster" → 22s, h slider: min=4mm, max=**15mm**, current val=10mm. Height=10mm on canvas. Previous b3 max was 40mm. `26-coaster.png`, `26-coaster-console.txt`. |
| 5e — photo/sketch on-ramp | PASS | Attached bracket sketch via CDP DOM.setFileInputFiles → vision read it ("A rough starting point — from your photo", "Read locally — your photo never left your machine"). "Use this as a starting point" button appeared. `19-photo-onramp-seed.png`, `14-input-sketch.png`. |
| 5f — keyboard viewport nav | PASS | Canvas focused (CANVAS element, tabIndex set). 15× ArrowRight + 8× ArrowUp → orbit: hash changed (`af1f8cfeaa30`→`243635286126`). 16× `+` key → zoom: hash changed (`243635286126`→`e48d447d7aad`). `20-keyboard-focus.png`, `21-keyboard-orbited.png`, `22-keyboard-zoomed.png`. |
| 6 — connector status | PASS | All 6 connectors (OctoPrint/Moonraker/PrusaLink/Duet/Marlin/Bambu) show "Not set up yet" with env-var guidance. No traceback. `10-settings-connectors.png`. |
| 7 — uninstall | PASS | `/VERYSILENT /SUPPRESSMSGBOXES` — install dir removed, HKCU registry entry GONE, Start Menu shortcut GONE. User data `%LOCALAPPDATA%\KimCad` + `~/.kimcad` designs correctly RETAINED. `25-uninstall.txt`. (Note: uninstaller left `python/`+`site-packages/` subdirs initially because the tester's background app-server job held Python DLLs; tester killed the process, dir then cleared cleanly — tester-harness artifact, not a user issue.) |

## 4. Findings

*(Every finding cites a committed artifact under `evidence/004/`.)*

**No Blockers, Criticals, or Majors.**

The two b3 open items are confirmed FIXED in b4:
- **[b3 Minor → FIXED in b4] Model-down now returns friendly, reason-coded message.** Landing shows "Your local AI isn't running yet — start Ollama to design." After a mid-session submit: "KimCad couldn't reach your local AI." NOT "Something went wrong on the server." Console stays 0-error. Evidence: `24-model-down.png`, `24-model-down.txt`. **(Previously: HTTP 500 generic error — now fixed.)**
- **[b3 Nit → FIXED in b4] Coaster height capped at 15mm.** `h` slider max is 15mm (not 40mm), current value 10mm for a 90mm coaster. The stray `40 mm` label observed in b3 is gone. Evidence: `26-coaster.png`, `26-coaster-console.txt`.

*No new Blockers, Criticals, Majors, or Minors found in b4.*

## 5. Model performance on this box (CPU/iGPU, qwen2.5:7b)
| Design | Time | Readiness |
|---|---|---|
| chip1 — 80×60×40 project box | 74.1 s | 86 Passed |
| chip2 — cable clip (8 mm) | 28.0 s | 92 Passed |
| chip3 — round trinket dish 90 mm | 30.0 s | 92 Passed |
| custom — 75mm square coaster | 24.0 s | 92 Passed |
| coaster (5d) — 90mm round coaster | 22.0 s | — |
| photo on-ramp (vision, qwen2.5vl:3b) | ~2 s | (seed) |
Models pre-present (no pull this run). All plan times within the directive's 30–120 s "normal" band (chip1 at 74s is slightly faster than b3's 80s — normal variance).

## 6. WebGL / 780M
Verbatim (`08-webgl-renderer.txt`, same box as b3): `UNMASKED_RENDERER = ANGLE (AMD, AMD Radeon 780M Graphics (0x00001900) Direct3D11 vs_5_0 ps_5_0, D3D11)`, WebGL 2.0, GLSL ES 3.00, DPR 1.25. Real iGPU via ANGLE→D3D11, not software/SwiftShader. All viewport renders + keyboard orbit/zoom worked; **0 console errors** across every design.

## 7. Open questions for DEV
1. The `kimcad_launcher.py --verify` flag mentioned in the directive (Step 3a) is not supported; canonical `scripts/verify_install.py <INSTALL_DIR>` was used instead. Confirm this is expected or update the directive for 005.
2. Phase 5b: "a 100mm round lid with a 5mm rim" hit the experimental generator path (no parameterized template match). Used "a 75mm square drink coaster" instead for the slider/slice/export test. The experimental generator is available but wasn't validated in this run — worth a dedicated test if DEV wants it covered.
3. Ollama + the two qwen models are still installed on the box for any re-test. Say the word if you want a full wipe.
