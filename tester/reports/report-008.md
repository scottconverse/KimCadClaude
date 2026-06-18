KCT-008-20260617-092

# Report 008 — KimCad 0.9.2 smoke verification (messaging clean-up)

## Verdict: SHIP

0.9.2 passes the smoke gate. Build identity confirmed (SHA + version), and **both directive-007 Minor
fixes are verified**: the engine-down message is now an exact, Ollama-free string, and the managed
engine stores models under `%LOCALAPPDATA%\KimCad\models` (no `~/.ollama` orphan). Settings nav and a
regression design both pass. No Blocker / Critical / Major / Minor. One Nit (stale internal code
comment). Per the sign-off threshold (Phase 1 + Phase 2 PASS, no Blocker/Critical) → **SHIP**.

Box: DESKTOP-2BR3SJR (Ryzen 7 8745HS / Radeon 780M / 27.8 GB / Win11 Pro 26200). Method: fresh install
on the true-clean box (0.9.1 had been fully removed; first-run flow is unchanged from 0.9.1 per the
directive, so an in-place upgrade wasn't possible — disclosed). UI driven by attaching Playwright over
CDP to the **real WebView2 shell** (`pythonw kimcad_launcher.py`); harness mode `shell-webview2`.

## Phase 1 — Build: **PASS**
- 1a hash: `B56C8D4D…84980A` matches expected exactly; size 203,510,557 B (~203.5 MB). `01-hash.txt`.
- 1b version: `/api/health` + `verify_install.py` + Settings → version all report **0.9.2**. `02-version.png`, `02-version.txt`.

## Phase 2 — Engine-down message: **PASS** (the headline)
With the managed engine stopped, both surfaces show the **exact** target string, verbatim:
> "KimCad couldn't reach your local AI — it isn't running. You can restart it from Settings, then try again."
- Landing canvas / design-request error: exact match. `03-engine-down-canvas.png`, `03-engine-down.txt`.
- Settings → AI panel: exact match. `04-engine-down-settings.png`.
- **No "Ollama" anywhere** in the down-state surfaces; **no "ollama.com"**. (`ollama_anywhere=False`.)
- No HTTP 500 / traceback.

This resolves directive-007 **Minor-1** (which read "Make sure Ollama is running").

## Phase 3 — Settings nav: **PASS**
In Settings, clicking a left-sidebar section link (tested "Experimental") **kept the Settings panel
open** and stayed at `#/settings` — it did not dismiss the panel (the old broken behavior).
`05-settings-nav.png`, `05-settings-nav.txt`.

## Phase 4 — Model-store path: **PASS** (verified functionally)
The directive's literal premise (an install README saying `%LOCALAPPDATA%\KimCad\models` rather than
"Ollama's standard model store") is **N/A** — there is no install README, and Settings/About contains
no model-store description. Verified the fix the stronger way, functionally: during this run's
cold-start the models downloaded to **`%LOCALAPPDATA%\KimCad\models` (7.5 GB)** while
**`~/.ollama` stayed at 0 MB** (timeline in `d008-download.log`). Resolves directive-007 **Minor-2**
(model orphan). `06-model-path-docs.txt`.

## Phase 5 — Regression smoke: **PASS**
"a small coin tray, 80 mm across" → plan + parametric part rendered (84 s, Readiness 92 on the managed
qwen2.5:7b), then **Slice & prepare produced a real print file** (`print_file_button=True`,
`orca_err=False`). `07-smoke-design.png`, `07-smoke-design.txt`.

## Findings
- **[Nit] Stale internal code comment** in `site-packages/kimcad/model_pull.py`: "under the user
  profile by default, or wherever `OLLAMA_MODELS` points" — describes pre-fix behavior. Internal only
  (not user-facing); models actually land in `%LOCALAPPDATA%\KimCad\models`. Tidy-up, no impact.

No Blocker / Critical / Major / Minor.

## Cold-start sanity (incidental)
Re-ran the full managed-engine cold setup on the clean box: engine → `%LOCALAPPDATA%\KimCad\ollama`
(~1.9 GB), models → `%LOCALAPPDATA%\KimCad\models` (7.5 GB), AI Ready, `ollama` never on PATH. The
0.9.1 first-run flow is intact in 0.9.2 (as the directive stated — no first-run change).

## Evidence index (`tester/evidence/008/`)
- `01-hash.txt` — SHA-256 + size
- `02-version.png`, `02-version.txt` — version 0.9.2 in Settings
- `03-engine-down-canvas.png`, `03-engine-down.txt` — exact down-state message, no Ollama
- `04-engine-down-settings.png` — Settings AI panel down-state
- `05-settings-nav.png`, `05-settings-nav.txt` — nav keeps panel open
- `06-model-path-docs.txt` — model-store functional verification (KimCad\models, no ~/.ollama)
- `07-smoke-design.png`, `07-smoke-design.txt` — regression design + slice
- `engine-setup-started.png` — cold-start kickoff

— TESTER (DESKTOP-2BR3SJR)
