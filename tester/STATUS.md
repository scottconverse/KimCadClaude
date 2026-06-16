# Liveness ledger — append one line per heartbeat (newest at the bottom)

Format: `YYYY-MM-DD HH:MM TZ | DEV|TESTER | <what I'm doing / what I just saw>`

Both sides append every ~10 min. Keep BOTH sides' lines on a merge conflict — never overwrite.
Run 1 (directive-001) is closed — the tester box died mid-run and we restarted. This is run 2.

---

- 2026-06-15 ~22:55 MT | DEV | Run 2 opened. Wrote `directive-002-clean-install-evidence-first.md` (NONCE `KCT-002-20260615-CORRECTED`). Two new hard rules: EVIDENCE-for-every-claim (commit artifacts under `evidence/002/`), and a Phase-3 BUILD-IDENTITY gate (must read qwen2.5:7b + the curated chips, not the stale published build). Corrected installer = `KimCad-Setup-0.9.0b2.exe` sha `2AF9F3DD…8F7D2EE5` — Scott supplies it (NOT on the Releases page). Tester-branch verify_install.py is the FIXED version now (merged from main). Waiting for TESTER to pull, run, and write `reports/report-002.md` with evidence.
