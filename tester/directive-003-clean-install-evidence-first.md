# Directive 003 — Clean-machine acceptance test, EVIDENCE-FIRST (KimCad 0.9.0b3, published)

**NONCE:** `KCT-003-20260616-B3` ← echo this verbatim at the top of your report.
**From:** DEV  **To:** TESTER (clean Windows 11 box)  **Supersedes:** directive-001 and directive-002.

The corrected build is now a **published, downloadable release** — no hand-transferred file. Two hard
rules still apply (they are the whole point):

> **RULE 1 — EVIDENCE, NOT NARRATION.** Every claim in your report must point to a file you committed
> under `tester/evidence/003/` — a screenshot (`.png`), a raw command dump (`.txt`), a hash, a JSON
> body. **A claim with no committed artifact is not a finding and will be thrown out.** Don't write
> "WebGL is real" — commit the pixels and the raw output that prove it.
>
> **RULE 2 — PROVE THE BUILD FIRST.** Phase 3 is a hard gate: prove you're on the corrected build
> (model = `qwen2.5:7b`, the curated chips) before you test anything. If it fails, STOP and report.

---

## The build under test

- **Download `KimCad-Setup-0.9.0b3.exe`** from the Releases page:
  <https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.0b3>
  (or `releases/latest` — **v0.9.0b3** is now the newest). This IS the corrected build.
- **Expected SHA-256:** `2FFB5C12BD2EC65D8E233875E001DB45AF5040B386CF17D8CC02BD0CA1E66FBD`
  (size **203,466,477 bytes**), source commit `23833dd`. The release also carries
  `KimCad-Setup-0.9.0b3.exe.sha256` and `SHA256SUMS.txt` — verify against them.
- ⚠️ Make sure you have **0.9.0b3**, not the older `v0.9.0b2`. The Phase-3 gate (model + chips) is your
  backstop if you grab the wrong one.

## Ground rules

- **Test the INSTALLED app**, not a dev build. You may `git clone` this repo **read-only** for this
  directive and `scripts/verify_install.py` (the tester branch carries the fixed verifier — use it).
  Do **NOT** build the repo, create a venv, or `pip install`.
- Do **NOT** run `git config core.hooksPath .githooks`. Plain git only. **Never force-push.**
- **Evidence:** commit raw artifacts to `tester/evidence/003/`, named `NN-short-name.png|.txt`.
  Reference each in the report by path.
- **Report after EVERY phase** — append to `tester/reports/report-003.md` and push, so a crash never
  loses the run. Heartbeat: append a one-line `STATUS.md` entry every ~10 min, even mid-phase.
- Severity-tag findings: Blocker / Critical / Major / Minor / Nit.
- Model inference is CPU/iGPU and slow (30–120 s/plan is normal, not a failure) — record times.

> **Phase-2 install heads-up:** driving the GUI installer with computer-use may be blocked (Windows
> masks installer windows from the agent). **Try a silent install first:**
> `KimCad-Setup-0.9.0b3.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=install.log`, then check the
> uninstall registry for "KimCad 0.9.0b3". If that hangs or the GUI is unclickable, ask Scott to
> double-click + click through it (he's at the box) — then you drive the **installed** app (grantable
> as "KimCad"). Don't burn the run fighting the installer; the app test is the headline.

## Phase 0 — Confirm the clean machine  *(evidence required)*
- Commit `NN-systeminfo.txt` (`systeminfo`) and `NN-clean.txt`: `python --version`, `node --version`
  (expect "not recognized"), `ollama --version`, WebView2 Runtime presence. **PASS:** no dev
  toolchain, no prior KimCad.

## Phase 1 — Download + integrity  *(evidence required)*
- Download the installer from the v0.9.0b3 release. Run
  `Get-FileHash .\KimCad-Setup-0.9.0b3.exe -Algorithm SHA256` → commit `NN-sha256.txt`.
- **PASS only if it equals `2FFB5C12…E66FBD`** (and matches the release `.sha256`).

## Phase 2 — Install  *(evidence required)*
- Install (silent-first per the heads-up above). Capture whatever install screens you can as evidence
  (SmartScreen prompt, wizard pages, finish) → `tester/evidence/003/`. Record: admin needed? install
  location? time? Commit `NN-installed.txt` (install location + uninstall-registry entry).

## Phase 3 — BUILD-IDENTITY GATE  *(before any functional test — evidence required)*
All **three** must pass, or STOP and report a Blocker:
1. **Model default** — Settings → AI and/or `kimcad models`; capture the chat/design model →
   `NN-model.txt` + a screenshot. **MUST be `qwen2.5:7b`.** `gemma4:e4b` ⇒ wrong build, STOP.
2. **Landing chips** — screenshot the start page's 3 examples → `NN-landing-chips.png`. MUST read
   exactly: `an 80 × 60 × 40 mm project box with a lid`, `a desk cable clip for an 8 mm cable`,
   `a round trinket dish, 90 mm across`. Old chips (filament spool / hex pen organizer) ⇒ wrong build.
3. **Verifier** — `& "<INSTALL_DIR>\python\python.exe" "<REPO>\scripts\verify_install.py" "<INSTALL_DIR>"`
   → commit the full output `NN-verify-install.txt`. MUST end with `VERIFY-INSTALL: ALL GREEN`.

## Phase 4 — Real model setup  *(evidence required)*
- Install Ollama; pull `qwen2.5:7b` + `qwen2.5vl:3b` (prefer the app's "Download now"). Commit
  `NN-ollama.txt` (`ollama list`) + sizes/times.

## Phase 5 — Real end-to-end, real model + real GPU  *(evidence required — THE HEADLINE)*
For **each** of the 3 curated chips (click it):
- Screenshot the part + the 3-D viewport → `NN-chipK-<name>.png`. Record: built on `qwen2.5:7b`? time?
- Open devtools console; commit `NN-chipK-console.txt`. Capture the **WebGL renderer string verbatim**
  (`const g=document.querySelector('canvas').getContext('webgl2'); g.getParameter(g.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)`)
  → commit it. A chip that dead-ends at the experimental offer or errors = **Critical** (screenshot).
Then, with evidence each: custom dimensioned prompt → design → slider re-render → slice → export
`.3mf` + `.stl` (screenshot + file sizes); photo/sketch on-ramp (screenshot the seed); Settings →
each connector type shows a clean "not set up" (screenshot, no traceback); keyboard — Tab to viewport,
arrow-orbit + `+`/`-` zoom (screenshot focus ring + changed view).

## Phase 6 — Failure states  *(evidence required)*
- Stop Ollama → design → screenshot the recoverable "AI not running" + retry (not a 500/traceback).
- Non-geometric prompt (`a feeling of nostalgia`) → screenshot the graceful outcome; confirm the
  geometric refine chips are NOT offered when there's no part (UX-002).

## Phase 7 — Uninstall  *(evidence required)*
- Uninstall via Apps; screenshot it's gone. Note whether `%LOCALAPPDATA%\KimCad` user data remains.

---

## Report → `tester/reports/report-003.md`
1. NONCE on line 1.  2. Verdict: would a real user succeed? ship / caveats / blocked.
3. Per-phase table: Phase | PASS/FAIL/PARTIAL | evidence file(s).  4. Findings, each citing a
committed evidence file, severity-tagged — *no file → not a finding*.  5. Model timings + the WebGL
renderer string verbatim.  6. Open questions for DEV.

Commit the report + all of `tester/evidence/003/`, append a `STATUS.md` line, and push. DEV verifies
every claim against its committed artifact before believing any of it.
