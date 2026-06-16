# Directive 001 — Full clean-machine install + functional acceptance test (KimCad 0.9.0b2)

**NONCE:** `KCT-INSTALL-20260615-b2`  ← echo this verbatim at the top of your report.
**From:** DEV  **To:** TESTER (`DESKTOP-2BR3SJR`)  **Build under test:** 0.9.0b2 (tag `v0.9.0b2`)

## Mission
Prove that a **real user** on a **clean Windows 11 machine** — no Python, no Node, no dev toolchain —
can download, verify, install, and actually *use* KimCad end-to-end on real AMD hardware (Radeon
780M, so the WebGL 3-D viewport runs on a GPU the build box never tested). Find what breaks. This is
the install/UX truth check the demo-only CI can't give us.

## Ground rules (read first)
- **Test the INSTALLED app, not a dev build.** You may `git clone` the repo **read-only** to get this
  directive and `scripts/verify_install.py` — but do **NOT** `pip install -e`, build the frontend, or
  run the repo's venv. The whole point is the shipped artifact.
- **Do not run `git config core.hooksPath .githooks`** on your clone (it would arm the build box's
  heavy gate). Plain pushes only.
- **CPU/iGPU inference is expected to be slow.** This box has no NVIDIA GPU, so Ollama runs the model
  on CPU/780M. A design plan taking **30–120 s** is normal, **not** a failure. Record the times.
- **Evidence or it didn't happen.** Every phase: capture screenshots (`evidence/001/NN-*.png`),
  command output, the browser console, and the server log. Commit them. Cite them in the report.
- **Severity-tag every defect** Blocker / Critical / Major / Minor / Nit (same framework as the repo's
  `docs/audits/`). Distinguish "the app is broken" from "this box is weird."

## Environment note (already known, confirm anything that changed)
AMD Ryzen 7 8745HS, Radeon 780M, 32 GB, Win 11 Pro build 26200. The DxDiag showed some pre-existing
**Windows servicing/CBS update errors** (0x80070570) unrelated to KimCad — only flag them if they
actually block the installer or the app.

---

## Phase 0 — Confirm the machine is clean
- [ ] Record: `python --version` (expect "not found" or a system Python that is NOT a KimCad venv),
      `node --version`, whether Ollama is already installed, whether the **WebView2 Runtime** is
      present (`reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients" ` or just note if
      Edge is installed — WebView2 ships with it).
- **PASS:** no KimCad dev environment exists; you're starting from a real user's footing.

## Phase 1 — Download + integrity
- [ ] Download `KimCad-Setup-0.9.0b2.exe` from
      <https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.0b2>.
- [ ] Compute SHA-256: `Get-FileHash .\KimCad-Setup-0.9.0b2.exe`.
- [ ] Compare to the published checksum (the release's `.sha256` / `SHA256SUMS.txt`).
      **Expected:** `f75495a045f0e03f1a4207ef94cb1240a87eb8934ae5758eeb66e33794fd6059`
- [ ] Note the SmartScreen experience (unsigned → "More info → Run anyway"). Screenshot it.
- **PASS:** hash matches exactly. **FAIL (Blocker)** if it doesn't — stop and report.

## Phase 2 — Install
- [ ] Double-click the installer. Record: does it need admin? Where does it install? Does it
      bootstrap the **WebView2 Runtime** if it was missing? How long does it take? Any error dialog?
- [ ] Confirm the install tree exists (the embedded `python\python.exe`, `tools\openscad`,
      `tools\orcaslicer` or equivalent, `tools\printproof3d`, `site-packages\kimcad`, the SPA).
- **PASS:** clean install, app shortcut created, tree present.

## Phase 3 — Scriptable install proof (the project's own gold-standard check)
Run the repo's installer verifier **using the embedded interpreter** (no dev Python needed), pointed
at the install dir:
```
& "<INSTALL_DIR>\python\python.exe" "<REPO_CLONE>\scripts\verify_install.py" "<INSTALL_DIR>"
```
It proves, end-to-end: version match, the server comes up (demo mode), `/api/health` sees bundled
OpenSCAD + OrcaSlicer, a demo design renders + the mesh downloads, the SPA shell + a JS asset serve,
and writes land under `%LOCALAPPDATA%\KimCad` (never the install dir).
- [ ] Paste the **full** output. **PASS:** it prints `VERIFY-INSTALL: ALL GREEN`. Any `FAIL:` line is
      at least Critical — quote it.

## Phase 4 — Real model setup
- [ ] If Ollama is absent, install it (winget `Ollama.Ollama` or the official installer) and start it.
- [ ] Pull the two models — either via the app's **first-run wizard "Download now"** button (preferred:
      tests that path) or `ollama pull qwen2.5:7b` + `ollama pull qwen2.5vl:3b`. **Record download
      sizes + times.**
- [ ] Confirm both are seen: `& "<INSTALL_DIR>\python\python.exe" -m kimcad models` (or the wizard's
      status). Expect `qwen2.5:7b` (designer) + `qwen2.5vl:3b` (vision).
- **PASS:** both models present and the app reports them green.

## Phase 5 — Real end-to-end functional test (the actual product, real model, real GPU)
Launch the desktop app (the WebView2 window). Walk it as a real user. Screenshot every major state.
- [ ] **First-run wizard:** does it detect Ollama, offer the model pull, explain LAN printing? Walk it.
- [ ] **The 3 landing example chips** — click each, one at a time. Each should build a real part on the
      **default** model and render in the 3-D viewport:
      1. `an 80 × 60 × 40 mm project box with a lid`
      2. `a desk cable clip for an 8 mm cable`
      3. `a round trinket dish, 90 mm across`
      Record for each: did it produce a part? time to first geometry? did the **3-D viewport render**
      on the 780M (orbit/zoom with the mouse)? **Watch the browser console for WebGL errors/warnings**
      — this GPU is new to us. **PASS:** all 3 build + render; **FAIL (Critical)** if a curated chip
      dead-ends at the "experimental generator" offer or errors.
- [ ] **Custom design + refine:** type a dimensioned prompt of your own → design → drag a slider to
      re-render → **slice** → **export** a `.3mf` and a `.stl`. Open the exported file to confirm it's
      real geometry. Record times.
- [ ] **Photo/sketch on-ramp:** feed a dimensioned hand sketch or photo → the vision model reads it →
      an editable seed appears → "use as starting point" → it designs. (Any clear printed/drawn shape
      works.)
- [ ] **Keyboard accessibility (UX-003):** Tab to the 3-D viewport, then use the **arrow keys** to
      orbit and `+`/`-` to zoom. Confirm it responds (focus ring visible).
- [ ] **Settings / connections:** open Settings → add a printer connection of each type you can
      (Bambu LAN, OctoPrint, Moonraker, PrusaLink, **Duet**, **Marlin**). With **no hardware**, confirm
      each shows a clean "not set up / can't reach" state — **no traceback, no crash**. If you happen
      to have a real printer on the LAN, say so (bonus #11 hardware data — but don't send a real job
      unless you intend to).

## Phase 6 — Failure-state behavior (the recent hardening)
- [ ] **Model down:** stop Ollama, then try a design. Expect a friendly *"your local AI isn't running,
      start Ollama"* recoverable state with a one-click retry — **not** a 500 or a raw traceback.
- [ ] **Un-buildable prompt:** type something deliberately non-geometric ("a feeling of nostalgia").
      Expect a graceful outcome (a clarifying question or the experimental offer) and — per the UX-002
      fix — the geometric refine chips ("Make it bigger" …) should **not** be offered when there's no
      part on screen. Confirm no infinite "designing…" hang.
- [ ] **Reload/persistence:** refresh the window; reopen a saved design from "My Designs."

## Phase 7 — Uninstall
- [ ] Uninstall via Windows "Apps." Confirm the install tree is removed. Note whether
      `%LOCALAPPDATA%\KimCad` user data remains (expected: user data is separate from the program).

---

## Report format — write to `reports/report-001-full-install-test.md`
Start with the NONCE line, then:
1. **Verdict** (1–3 sentences): would a real user succeed? ship-as-is / ship-with-caveats / blocked.
2. **Environment** (anything that differed from the note above).
3. **Per-phase results table:** Phase | PASS/FAIL/PARTIAL | key evidence (hash, time, screenshot
   path, console excerpt).
4. **Defects** — each with: severity, what you did, what you expected, what happened, evidence path.
5. **Model performance on this box:** plan times for each of the 3 chips + the custom design (so we
   know the real-world CPU/iGPU experience).
6. **WebGL / 780M notes:** anything the viewport did on AMD that looked off.
7. **Open questions for DEV.**

Commit the report + `evidence/001/*`, append a STATUS line, and push. Then start your 10-minute
heartbeat (pull, check for `directive-002`, append STATUS, repeat). DEV is polling every 10 min.
