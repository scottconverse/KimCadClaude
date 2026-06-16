# Report 003 — KimCad 0.9.0b3 clean-machine acceptance test
**NONCE:** `KCT-003-20260616-B3`

_Status: IN PROGRESS (appended per-phase). Tester box DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200, 125% DPI)._

## Per-phase progress
| Phase | Result | Key evidence |
|---|---|---|
| 0 — clean machine | PASS | `evidence/003/01-systeminfo.txt`, `02-clean.txt` (system Python only; no node/ollama; WebView2 149.0.4022.69; no prior KimCad) |
| 1 — download + SHA-256 | PASS | `evidence/003/03-sha256.txt` — 203,466,477 bytes, sha `2ffb5c12…e66fbd` = expected, matches published `03-published-b3.sha256`; NOT the stale `f75495a0…` |
