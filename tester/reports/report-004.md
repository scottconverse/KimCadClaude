# Report 004 — KimCad 0.9.0b4 clean-machine acceptance test
**NONCE:** `KCT-004-20260616-B4`
Status: IN PROGRESS (appended per-phase). Box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI).

## Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS (1 disclosed deviation) | `evidence/004/01-systeminfo.txt`,`02-clean.txt` — clean of KimCad; node absent; WebView2 149.0.4022.69. Deviation: Ollama 0.30.8 + qwen models pre-present (left from ACCEPTED b3 per SIGN-OFF item #3); not re-pulled. |
| 1 — download + SHA-256 | PASS | `evidence/004/03-sha256.txt` — 203,472,459 bytes; sha `532b3f8b…066d2c` = expected & matches published `03-published-SHA256SUMS.txt`. |
| 2 — install (silent per-user) | PASS | `04-install.log`,`04-installed.txt` — exit 0, 52.2s, `%LOCALAPPDATA%\Programs\KimCad`; reg `KimCad 0.9.0b4` v`0.9.0b4` (HKCU). |
| 3 — BUILD-IDENTITY GATE | **PASS (all 3)** | 3a `05-verify-install.txt` → `VERIFY-INSTALL: ALL GREEN` (v0.9.0b4). 3b model `qwen2.5:7b` `06-model-status.txt`+`09-settings-model.png`. 3c exact chips `07-landing-chips.png`. 3d WebGL real 780M ANGLE/D3D11 (no SwiftShader) `08-webgl-renderer.txt`. **Note:** directive's `kimcad_launcher.py --verify` flag isn't supported; used the canonical `scripts/verify_install.py`. |
| 4 — Ollama + models | PASS (pre-present) | `11-ollama.txt` — qwen2.5:7b + qwen2.5vl:3b present (kept from b3 per SIGN-OFF); model-status running+present. |
