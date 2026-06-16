# Report 004 — KimCad 0.9.0b4 clean-machine acceptance test
**NONCE:** `KCT-004-20260616-B4`
Status: IN PROGRESS (appended per-phase). Box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI).

## Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS (1 disclosed deviation) | `evidence/004/01-systeminfo.txt`,`02-clean.txt` — clean of KimCad; node absent; WebView2 149.0.4022.69. Deviation: Ollama 0.30.8 + qwen models pre-present (left from ACCEPTED b3 per SIGN-OFF item #3); not re-pulled. |
| 1 — download + SHA-256 | PASS | `evidence/004/03-sha256.txt` — 203,472,459 bytes; sha `532b3f8b…066d2c` = expected & matches published `03-published-SHA256SUMS.txt`. |
