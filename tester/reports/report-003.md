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
