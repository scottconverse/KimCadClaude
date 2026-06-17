# KimCad Tester Directive 007 — Clean-Machine Gauntlet (0.9.0b4 + zero-install AI / managed Ollama)

**NONCE:** `KCT-007-20260617-CS`  ← echo this verbatim on line 1 of your report.
**Build under test:** `0.9.0b4` **plus the cold-start onboarding overhaul** — **source commit `09b979c`**
on `main` (this is the canonical b4 product + the managed-Ollama fix; it is NOT a tagged release).
**What changed since the shipped b4 (directive-004):** KimCad now **sets up its own local AI** instead
of making the user install Ollama by hand.
  - On first run it **reuses a system Ollama if one exists, otherwise downloads Ollama's portable
    engine itself** (~1.4 GB) into KimCad's data folder and runs it headless — **no separate install,
    no system tray, no "Get Ollama → install it → check again" dead-end.**
  - The wizard's **"Set up KimCad's AI"** button does the whole thing in one flow: ensure the engine,
    then download the chat + vision models (~7.7 GB), on one progress bar.
  - Detection fix (ENG-COLD-002): the AI is detected by loopback host, not a literal port string, so a
    non-default Ollama port is no longer misread as "cloud, ready."
  - Hardening (ENG-004): the CadQuery worker now denies network egress before running generated code.

> **⚠ THIS RUN'S WHOLE POINT (no prior run could test it):** every earlier clean-machine test ran on a
> box where Ollama was already installed, so the **fresh-machine first-run was never actually walked**.
> A real user (Scott) installed b4 cold and hit a **dead-end**. This directive validates the fix on a
> box with **NO Ollama** — that the user reaches a working AI **without ever manually installing
> Ollama.** Phase 3 (cold marker) + Phase 4 (the managed-engine fetch) are THE headline; treat them as
> the gate.

**Download:** `KimCad-Setup-0.9.0b4-coldstart.exe` — **⚠ BUILD ARTIFACT PENDING.** This build is
unreleased `main@09b979c`; the installer is being built/transported separately (see "Build note" at the
bottom). **DEV will fill the Expected SHA-256 + size before you start Phase 1** (same as directive-005).
**Expected SHA-256:** `<DEV will fill>`   **Expected size:** `<DEV will fill>` bytes
**Source commit:** `09b979c`

---

## Hard rules (same as 003–006)
1. **EVIDENCE, NOT NARRATION.** Every claim cites a file you committed under `tester/evidence/007/`
   (screenshot `.png`, raw dump `.txt`, hash, JSON). No artifact → not a finding.
2. **PROVE THE BUILD FIRST.** Phase 3 is a hard gate (four checks). Any failure ⇒ STOP and report.
3. **Report to** `tester/reports/report-007.md`; append `STATUS.md` heartbeat after each phase (~10 min).
   Severity-tag findings: Blocker / Critical / Major / Minor / Nit.

## Ground rules
- Test the INSTALLED app, not a dev build. You may `git clone` read-only for `scripts/verify_install.py`.
  Do NOT build the repo / venv / pip install. Do NOT set `core.hooksPath`. Plain git. Never force-push.
- Model inference is CPU/iGPU (30–120 s/plan is normal) — record times, don't call slow a fail.
- **The whole engine + model download is large (~1.4 GB engine + ~7.7 GB models). Record sizes/times;
  a long honest download with a progress bar is the expected behavior, not a fail.**

> **Phase-2 install heads-up:** GUI installer automation may be blocked. Try silent first:
> `KimCad-Setup-0.9.0b4-coldstart.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=install.log`,
> check the uninstall registry for "KimCad 0.9.0b4". If it hangs, ask Scott to click through it.

## Phase 0 — Confirm the TRULY clean machine  *(evidence: 01-systeminfo.txt, 02-clean.txt)*
`winver` + OS/CPU/RAM. Then the critical precondition — **prove there is NO Ollama and no models:**
- `Get-Command node,ollama,kimcad` → **all must be NOT FOUND.**
- `Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"` → **False.**
- `Test-Path "$env:USERPROFILE\.ollama\models"` (or list it) → **absent/empty** (no pre-pulled models).
- Uninstall-registry KimCad check → none. WebView2 present.
**PASS only if:** no prior KimCad, **no Ollama anywhere, no models**, no Node, WebView2 present. If Ollama
is present this run is INVALID for the headline — wipe it or use a genuinely clean box first.

## Phase 1 — Download + integrity  *(03-sha256.txt)*
`Get-FileHash KimCad-Setup-0.9.0b4-coldstart.exe -Algorithm SHA256`. **PASS only if it equals the
Expected SHA-256 above and the size matches.** (DEV fills both before you start.)

## Phase 2 — Install  *(04-installed.txt, 04-install.log)*
Silent-first. Record admin?/location/time. Confirm uninstall registry shows **0.9.0b4**.

## Phase 3 — BUILD-IDENTITY GATE  *(all four; evidence each)*
1. **Source commit** — `verify_install.py <INSTALL_DIR>` ends `VERIFY-INSTALL: ALL GREEN`, and the build
   reflects `09b979c` (About/Settings or the verifier's reported version) → `05-verify-install.txt`.
2. **Model** `qwen2.5:7b` named as the planner (Settings → AI / `kimcad models`) → `06-model.txt` + shot.
3. **Landing chips** — exactly: `an 80 × 60 × 40 mm project box with a lid`, `a desk cable clip for an
   8 mm cable`, `a round trinket dish, 90 mm across` → `07-landing-chips.png`.
4. **COLD-START MARKER (the headline gate).** With NO Ollama present, open the first-run wizard →
   **"Set up your AI"** step. Confirm it offers a **"Set up KimCad's AI"** button and copy like *"KimCad
   sets up its AI for you — no separate install."* It must **NOT** say *"Get Ollama → install it → check
   again"* and must **NOT** send you to ollama.com as the required path. Also: the landing "AI not ready"
   banner (if shown) must point to in-app setup, not "start Ollama." Screenshot → `08-coldstart-setup-button.png`.
   **If you see the old "Get Ollama / install it / check again" dead-end, or "Design it" is the only path
   and there's no in-app setup → that's the OLD build → Blocker → STOP** (wrong artifact; DEV mis-shipped).

## Phase 4 — THE HEADLINE: managed-engine cold setup  *(evidence each — this is the run's reason)*
Still on the Ollama-free machine, click **"Set up KimCad's AI"** and prove the app sets up the AI
ITSELF, with the user never installing Ollama by hand:
- Confirm it **starts downloading an "AI engine"** (the portable Ollama, ~1.4 GB) in-app — NOT a redirect
  to ollama.com, NOT a "go install it" prompt. Screenshot the engine-download progress → `09-engine-fetch.png`.
- Then the **model(s) download** (~7.7 GB) on the same flow → `10-model-fetch.png`. Record total time/size.
- When it finishes, the AI reads **Ready** WITHOUT you having installed Ollama. → `11-ai-ready.png`.
- **Prove KimCad's engine is its OWN, not a system install:** after setup, `Get-Command ollama` should
  STILL be NOT FOUND on PATH, and `Test-Path "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"` STILL False;
  but a managed `ollama` process IS running (`Get-Process ollama`) and the engine lives under KimCad's
  data dir (`%LOCALAPPDATA%\KimCad\ollama\ollama.exe` — confirm it exists). → `12-managed-engine.txt`.
- **If the wizard dead-ends, redirects to ollama.com, or can't reach a working AI without a manual Ollama
  install → Critical (the fix failed on a real clean machine).** A slow-but-completing download is a PASS.

## Phase 5 — Core end-to-end (real managed model + real GPU)  *(evidence each)*
For **each** of the 3 curated chips: screenshot part + viewport (`13-chipK-<name>.png`), record model +
time; devtools console (`14-chipK-console.txt`) + the **WebGL renderer string verbatim** (`15-webgl.txt`).
Then: a custom dimensioned prompt → design → slider re-render → **slice → a real `.3mf` print file** →
export `.3mf` + `.stl` (sizes, `16-export.txt`); photo/sketch on-ramp seed. A chip that dead-ends or
errors = **Critical**. Confirm the slice produces a real `.3mf` for a normal single-material printer.

## Phase 5b — Multi-printer single-material  *(evidence)*
Pick 2–3 printers (e.g. Bambu P2S, a Creality, a Prusa). Each: one **Material** dropdown (no Extruder N),
slicing produces a print file → `17-single-material-slice.png`. Settings → Printer connections shows the
normal connector templates, **no "Snapmaker U1"** anywhere → `18-connections.png`.

## Phase 6 — Reuse / second-launch (the OTHER managed-runtime branch)  *(evidence)*
- **Second launch:** fully close + reopen KimCad. Confirm the AI is ready **immediately with NO setup
  step** (the managed engine auto-starts; no re-download of the ~1.4 GB engine) → `19-second-launch.png`.
- **(Optional, if a box with a real system Ollama is available)** install Ollama + pull `qwen2.5:7b`
  first, then run KimCad: confirm it **REUSES** the system Ollama (no second engine fetched; model-status
  reads it) → `20-reuse-system-ollama.png`. If no such box, note it as not-tested (DEV will cover the
  reuse path another way).

## Phase 7 — Failure states  *(evidence)*
Stop the running engine/Ollama → design → recoverable "AI not ready / set up" + retry (NOT a 500/traceback).
Non-geometric prompt (`a feeling of nostalgia`) → graceful. Geometric refine chips NOT offered with no part.

## Phase 8 — Uninstall  *(evidence)*
Uninstall via Apps; confirm gone. Note whether `%LOCALAPPDATA%\KimCad` (incl. the managed `ollama/` engine
+ downloaded models) remains, and whether the uninstaller offers to remove it. Record the disk reclaimed.

---

## Report → `tester/reports/report-007.md`
1. NONCE line 1. 2. Verdict: **would a brand-new user with NO Ollama reach a working design without
manually installing anything?** ship / caveats / blocked. 3. Per-phase table | PASS/FAIL/PARTIAL |
evidence. 4. Findings (each cites an artifact), severity-tagged. 5. Engine + model download sizes/times +
the WebGL renderer string verbatim. 6. Open questions for DEV.

Commit the report + all of `tester/evidence/007/`, append `STATUS.md`, push. DEV verifies every claim
against its artifact.

---

## Build note (DEV → DEV/Scott, not the tester's concern)
The build is unreleased `main@09b979c` (b4 + the cold-start managed-Ollama fix). Before the tester starts
Phase 1, the `KimCad-Setup-0.9.0b4-coldstart.exe` installer must be built from `09b979c` (Inno Setup via
`scripts/build_installer.py`) and transported to the clean machine, and the **Expected SHA-256 + size
filled in above** (a one-line follow-up commit, exactly as directive-005 did). This is NOT a public
release tag — it is a test artifact for the clean-machine gauntlet.

— DEV
