# Directive 002 — Clean-machine acceptance test, EVIDENCE-FIRST (the CORRECTED KimCad build)

**NONCE:** `KCT-002-20260615-CORRECTED` ← echo this verbatim at the top of your report.
**From:** DEV  **To:** TESTER (clean Windows 11 box)  **Supersedes:** directive-001.

This is a retry. The first run failed for two reasons, and this directive fixes both. Read these
two rules before anything else — they are the whole point:

> **RULE 1 — EVIDENCE, NOT NARRATION.** Every single claim in your report must point to a file you
> committed under `tester/evidence/002/` — a screenshot (`.png`), a raw command dump (`.txt`), a hash,
> a JSON body. **A claim with no committed artifact is not a finding and will be thrown out.** Do not
> write "WebGL is real" or "the connectors are fine" — commit the pixels and the raw output that
> prove it. If you didn't capture it, you didn't test it.
>
> **RULE 2 — PROVE THE BUILD FIRST.** The build on the public Releases page is **STALE** (wrong model,
> old example chips). Testing it is worthless. Phase 3 is a hard gate: prove you're on the CORRECTED
> build before you test anything. If the gate fails, STOP and report it — do not continue.

---

## The build under test

- **File:** `KimCad-Setup-0.9.0b2.exe` — **Scott will give you this file / tell you where it is.**
- **Expected SHA-256:** `2AF9F3DDFB5A54442FCA7838A44183FD77DD4E69B1B46577527396B68F7D2EE5`
  (size **203,472,984 bytes**), built from source commit `1b65d12`.
- ⚠️ **DO NOT download the installer from the GitHub Releases page.** That published `0.9.0b2`
  (sha `f75495a0…`) is the STALE build and is the WRONG thing to test.
- ⚠️ The corrected build has the **same filename and the same version string** (`0.9.0b2`) as the
  stale one — **the version number cannot tell them apart.** Only the **SHA-256** (Phase 1) and the
  **model + chips** (Phase 3) distinguish them.

## Ground rules

- **Test the INSTALLED app**, not a dev build. You may `git clone` this repo **read-only** to get this
  directive and `scripts/verify_install.py`. Do **NOT** build the repo, create a venv, or `pip install`.
- This branch already contains the **fixed** `scripts/verify_install.py` (the merge brought it in), so
  the copy you clone with the `tester` branch is correct — use it as-is.
- Do **NOT** run `git config core.hooksPath .githooks`. Plain git only. **Never force-push.**
- **Evidence:** commit raw artifacts to `tester/evidence/002/`, named `NN-short-name.png|.txt`.
  Reference each one by path in the report.
- **Report after EVERY phase** — append your results to `tester/reports/report-002.md` and push, so a
  crash never loses the run. Heartbeat: append a one-line `STATUS.md` entry every ~10 min, even
  mid-phase.
- Severity-tag findings: Blocker / Critical / Major / Minor / Nit.
- **Model inference is CPU/iGPU and slow** (30–120 s per plan is normal, not a failure) — record times.

---

## Phase 0 — Confirm the clean machine  *(evidence required)*
- Commit `NN-systeminfo.txt` (`systeminfo`). Commit `NN-clean.txt` capturing: `python --version`,
  `node --version` (expect "not recognized"), `ollama --version` (expect not-found on a fresh box),
  and whether the **WebView2 Runtime** is present.
- **PASS:** no dev toolchain, no prior KimCad install.

## Phase 1 — Integrity  *(evidence required)*
- Get the installer from Scott. Run `Get-FileHash .\KimCad-Setup-0.9.0b2.exe -Algorithm SHA256` →
  commit `NN-sha256.txt`.
- **PASS only if it EXACTLY equals `2AF9F3DD…8F7D2EE5`.** If it equals `f75495a0…`, you have the
  **WRONG (published) build** — STOP and report as a Blocker.

## Phase 2 — Install  *(evidence required)*
- Double-click the `.exe`. **Screenshot every screen** (SmartScreen prompt if it appears, each wizard
  page, the finish page) → `tester/evidence/002/`. Record: admin needed? install location? elapsed
  time? any error dialog (screenshot it).
- Commit `NN-installed.txt`: the install location + the matching uninstall-registry entry
  (`DisplayName`, `DisplayVersion`, `InstallLocation`).

## Phase 3 — BUILD-IDENTITY GATE  *(do this BEFORE any functional testing — evidence required)*
All **three** must pass, or STOP:
1. **Model default.** Launch the app; open **Settings → AI** (and/or run the installed
   `kimcad models`). Capture the **chat/design** model → commit `NN-model.txt` **and** a screenshot.
   → **MUST be `qwen2.5:7b`.** If it shows **`gemma4:e4b`** → WRONG BUILD. STOP. Report
   "Blocker: stale published 0.9.0b2, not the corrected build."
2. **Landing chips.** Screenshot the start page's 3 example chips → `NN-landing-chips.png`. They MUST
   read **exactly**:
   - `an 80 × 60 × 40 mm project box with a lid`
   - `a desk cable clip for an 8 mm cable`
   - `a round trinket dish, 90 mm across`
   If you instead see `a wall-mounted holder for a 1 kg filament spool` or
   `a hexagonal pen and tool organizer` → WRONG BUILD. STOP. Report.
3. **Installer verifier.** From your repo clone, run the bundled verifier against the install dir using
   the app's **embedded** interpreter (no dev Python):
   `& "<INSTALL_DIR>\python\python.exe" "<REPO>\scripts\verify_install.py" "<INSTALL_DIR>"`
   → commit the **full** console output `NN-verify-install.txt`. **MUST end with
   `VERIFY-INSTALL: ALL GREEN`.**
- Proceed to Phase 4 ONLY if all three pass.

## Phase 4 — Real model setup  *(evidence required)*
- Install Ollama (record the method). Pull `qwen2.5:7b` + `qwen2.5vl:3b` — preferably via the app's
  first-run **"Download now"** (that tests the journey), else `ollama pull`. Commit `NN-ollama.txt`
  (`ollama list`) + download sizes/times.

## Phase 5 — Real end-to-end, real model + real GPU  *(evidence required — THE HEADLINE)*
For **each** of the 3 curated chips (click it, one at a time):
- Commit a screenshot of the resulting part + the 3-D viewport → `NN-chipK-<name>.png`.
- Record: did it **build on `qwen2.5:7b`**? time to first geometry?
- Open the WebView2 / browser **devtools console**; commit the console text → `NN-chipK-console.txt`.
  Capture the **WebGL renderer string verbatim** (in the console:
  `const g=document.querySelector('canvas').getContext('webgl2'); g.getParameter(g.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)`)
  → commit it. **This is how we KNOW** whether it's the real 780M (ANGLE/D3D11) or software — capture
  the string, do not assert.
- A curated chip that **dead-ends at the "experimental generator" offer** or errors = **Critical** —
  screenshot it.
Then, with evidence for each:
- **Custom design:** type a dimensioned prompt → design → drag a slider to re-render → **slice** →
  **export** a `.3mf` and a `.stl`. Commit a screenshot + the exported file sizes (`NN-export.txt`).
- **Photo/sketch on-ramp:** feed a dimensioned sketch/photo → screenshot the editable seed it produces.
- **Settings / connections:** add each connector type you can (Bambu, OctoPrint, Moonraker, PrusaLink,
  **Duet**, **Marlin**); screenshot that each shows a clean "not set up" state (no traceback). If you
  have a real printer on the LAN, note it (do not send a real job unless you intend to).
- **Keyboard (UX-003):** Tab to the 3-D viewport, arrow-orbit + `+`/`-` zoom; screenshot the focus ring
  and a changed view.

## Phase 6 — Failure states  *(evidence required)*
- Stop Ollama → run a design → screenshot the recoverable *"your local AI isn't running"* state with a
  retry (must NOT be a 500 / raw traceback).
- Type a non-geometric prompt (`a feeling of nostalgia`) → screenshot the graceful outcome, and confirm
  the geometric refine chips are **not** offered when there's no part (UX-002).

## Phase 7 — Uninstall  *(evidence required)*
- Uninstall via Apps; screenshot it's gone. Note whether `%LOCALAPPDATA%\KimCad` user data remains.

---

## Report → `tester/reports/report-002.md`
1. **NONCE** on line 1.
2. **Verdict:** would a real user succeed on the corrected build? ship / ship-with-caveats / blocked.
3. **Per-phase table:** Phase | PASS / FAIL / PARTIAL | the evidence file(s) that prove it.
4. **Findings:** each one **cites a committed evidence file**. Severity-tagged. *No file → not a finding.*
5. **Model timings** per chip + custom design. **WebGL renderer string, verbatim.**
6. Open questions for DEV.

Commit the report + all of `tester/evidence/002/`, append a `STATUS.md` line, and push. DEV will pick
it up. Anything you assert without a committed artifact behind it, DEV will treat as unverified.
