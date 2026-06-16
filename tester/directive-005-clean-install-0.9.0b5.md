# KimCad Tester Directive 005 — Clean-Machine Acceptance Test (0.9.0b5 — Snapmaker U1 / multi-toolhead)

**NONCE:** `KCT-005-20260616-B5`  ← echo this verbatim on line 1 of your report.
**Release:** v0.9.0b5
**Headline of this run:** the new **Snapmaker U1 + generic multi-toolhead** support (Phase 5b). Everything
else is regression — prove the new feature works on a clean box AND that nothing that worked in b4 broke.
**Download:** `KimCad-Setup-0.9.0b5.exe` from https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.0b5
**Expected SHA-256:** `f4bd7af7f3f5f155c849f7c96611b4f4da8ee386a4bb9aac537e2e4cb5543e63`
**Expected size:** 204,770,673 bytes   **Source commit:** `c047688`

> ⚠️ This is the FIRST build with the Snapmaker U1. If your installed app's printer list has **no
> Snapmaker U1**, you are on the wrong build — STOP at the Phase-3 gate and report a Blocker.

---

## Hard rules (same as directives 003 / 004)

1. **EVIDENCE, NOT NARRATION.** Every claim in the report must cite a file you committed under
   `tester/evidence/005/` — a screenshot (`.png`), a raw command dump (`.txt`), a hash, a JSON body.
   A claim with no committed artifact is not a finding and will be thrown out.
2. **PROVE THE BUILD FIRST.** Phase 3 is a hard gate. Four things must ALL be true in committed
   artifacts before you touch Phases 4+: (a) `model = qwen2.5:7b` (NOT `gemma4:e4b`); (b) the three
   exact landing chips; (c) `verify_install.py` ends `VERIFY-INSTALL: ALL GREEN`; (d) **the Snapmaker
   U1 is present in the printer catalog with 4 toolheads** (the b5 identity marker). Any failure ⇒ STOP.
3. **Report to** `tester/reports/report-005.md`; append a `STATUS.md` heartbeat line after each phase
   (every ~10 min, even mid-phase). Severity-tag findings: Blocker / Critical / Major / Minor / Nit.

## Ground rules

- **Test the INSTALLED app**, not a dev build. You may `git clone` this repo **read-only** to get
  `scripts/verify_install.py` (the tester branch carries the fixed verifier). Do **NOT** build the
  repo, create a venv, or `pip install`. Do **NOT** run `git config core.hooksPath .githooks`. Plain
  git only. **Never force-push.**
- Model inference is CPU/iGPU and slow (30–120 s/plan is normal) — record times, don't call slow a fail.

> **Phase-2 install heads-up:** driving the GUI installer with computer-use may be blocked (Windows
> masks installer windows). Try silent first:
> `KimCad-Setup-0.9.0b5.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=install.log`, then check the
> uninstall registry for "KimCad 0.9.0b5". If it hangs / the GUI is unclickable, ask Scott to
> double-click + click through it (he's at the box); then drive the **installed** app (grantable as
> "KimCad"). Don't burn the run fighting the installer — the app test is the headline.

---

## Phase 0 — Confirm the clean machine  *(evidence required)*
Evidence: `01-systeminfo.txt`, `02-clean.txt`
```
winver; systeminfo | Select-String "OS Name","Total Physical","Processor"
Get-Command node,ollama,kimcad -ErrorAction SilentlyContinue | Select-Object Name,Source
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
  "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" -ErrorAction SilentlyContinue |
  Where-Object DisplayName -like "*KimCad*" | Select-Object DisplayName,DisplayVersion
```
**PASS:** no prior KimCad, no Ollama, no Node; WebView2 Runtime present.

## Phase 1 — Download + integrity  *(evidence required)*
- Obtain `KimCad-Setup-0.9.0b5.exe`. `Get-FileHash .\KimCad-Setup-0.9.0b5.exe -Algorithm SHA256` →
  commit `03-sha256.txt`. **PASS only if it equals `f4bd7af7f3f5f155c849f7c96611b4f4da8ee386a4bb9aac537e2e4cb5543e63`**
  and the size is `204,770,673` bytes.

## Phase 2 — Install  *(evidence required)*
- Install (silent-first per the heads-up). Capture any install screens (SmartScreen, wizard, finish).
  Record admin-needed?, install location, time. Commit `04-installed.txt` (install dir + uninstall
  registry entry showing **0.9.0b5**).

## Phase 3 — BUILD-IDENTITY GATE  *(before any functional test — evidence required)*
All **four** must pass or STOP and report a Blocker:
1. **Model** — Settings → AI and/or `kimcad models`; capture the design model → `05-model.txt` + shot.
   MUST be `qwen2.5:7b`.
2. **Landing chips** — screenshot the start page's 3 examples → `06-landing-chips.png`. MUST read
   exactly: `an 80 × 60 × 40 mm project box with a lid`, `a desk cable clip for an 8 mm cable`,
   `a round trinket dish, 90 mm across`.
3. **Verifier** — `& "<INSTALL_DIR>\python\python.exe" "<REPO>\scripts\verify_install.py" "<INSTALL_DIR>"`
   → commit full output `07-verify-install.txt`. MUST end `VERIFY-INSTALL: ALL GREEN`.
4. **Snapmaker present (b5 marker)** — in the app's printer picker (Export panel), confirm **Snapmaker
   U1** is listed. Screenshot → `08-snapmaker-in-picker.png`. Absent ⇒ wrong build, STOP.

## Phase 4 — Real model setup  *(evidence required)*
- Install Ollama; pull `qwen2.5:7b` + `qwen2.5vl:3b` (prefer the app's "Download now"). Commit
  `09-ollama.txt` (`ollama list`) + sizes/times.

## Phase 5 — Core end-to-end regression (real model + real GPU)  *(evidence required)*
For **each** of the 3 curated chips: screenshot the part + 3-D viewport (`10-chipK-<name>.png`), record
model + time; commit the devtools console (`11-chipK-console.txt`) and the **WebGL renderer string
verbatim**
(`const g=document.querySelector('canvas').getContext('webgl2'); g.getParameter(g.getExtension('WEBGL_debug_renderer_info').UNMASKED_RENDERER_WEBGL)`).
Then with evidence each: a custom dimensioned prompt → design → slider re-render → slice → export `.3mf`
+ `.stl` (sizes); photo/sketch on-ramp (seed screenshot). A chip that dead-ends or errors = **Critical**.

## Phase 5b — SNAPMAKER U1 / MULTI-TOOLHEAD  *(THE HEADLINE — evidence required)*
No real printer is needed: the bundled OrcaSlicer does the multi-material slice locally.
1. **Picker + build volume** — select **Snapmaker U1** in the Export panel. Screenshot
   (`20-snapmaker-selected.png`). Confirm it slices for a 270.5 × 271.0 × 270.05 mm bed.
2. **Multi-toolhead UI** — confirm the single "Material" dropdown is replaced by **four** dropdowns
   labeled **Extruder 1 … Extruder 4**, with a helper note about assigning a filament per extruder.
   Screenshot (`21-four-extruder-dropdowns.png`).
3. **Single-head regression** — switch to a 1-head printer (e.g. Bambu P2S). Confirm it shows **one**
   Material dropdown (NOT four). Screenshot (`22-singlehead-one-dropdown.png`). This proves the
   multi-head UI is gated on `toolhead_count`, not always on.
4. **Distinct-material multi-material slice** — back on Snapmaker U1, set Extruder 1 = PLA, 2 = PETG,
   3 = TPU, 4 = ABS. Design any simple part (or use a curated chip), then **Slice**. Confirm it
   produces a print file (no error). Export the `.3mf`; record its size. Screenshot the success state
   (`23-multimaterial-slice.png`) + the exported file listing (`24-multimaterial-3mf.txt`,
   `Get-Item ... | Select Name,Length`).
5. **Per-slot summary** — confirm the post-slice summary line names the per-extruder materials
   (e.g. "Extruder 1: PLA, Extruder 2: PETG, …"), not just one material. Screenshot
   (`25-per-slot-summary.png`).
6. **Connector listed, not-set-up** — Settings → Printer connections: confirm a **Snapmaker U1**
   connection appears as "not set up yet" (it ships as an unconfigured template), with a clean
   message and **no traceback**. Screenshot (`26-snapmaker-connection.png`).
7. **Temp-chip / pre-send (best-effort, no hardware)** — there is no real Snapmaker attached, so the
   live temperature chips can't be exercised. Just confirm that selecting the Snapmaker connection and
   opening the Send panel shows the clean not-set-up state (no error). Screenshot if anything looks off.

**Phase 5b PASS:** four Extruder dropdowns appear for the U1 (one for a single-head printer), a
4-material slice produces a real `.3mf`, the per-slot summary names each extruder's material, and the
Snapmaker connection reads as a clean unconfigured template. Any traceback, a single-material-only
slice, or the wrong dropdown count = a finding (severity per impact).

## Phase 6 — Failure states  *(evidence required)*
- Stop Ollama → design → screenshot the recoverable "AI not running" + retry (not a 500/traceback).
- Non-geometric prompt (`a feeling of nostalgia`) → screenshot the graceful outcome; confirm the
  geometric refine chips are NOT offered when there's no part.

## Phase 7 — Uninstall  *(evidence required)*
- Uninstall via Apps; screenshot it's gone. Note whether `%LOCALAPPDATA%\KimCad` user data remains.

---

## Report → `tester/reports/report-005.md`
1. NONCE on line 1. 2. Verdict: would a real user succeed with the Snapmaker U1 multi-toolhead flow?
ship / caveats / blocked. 3. Per-phase table: Phase | PASS/FAIL/PARTIAL | evidence file(s) — Phase 5b
gets its own sub-table for steps 1–7. 4. Findings, each citing a committed evidence file,
severity-tagged — *no file → not a finding*. 5. Model timings + the WebGL renderer string verbatim.
6. Open questions for DEV.

Commit the report + all of `tester/evidence/005/`, append a `STATUS.md` line, and push. DEV verifies
every claim against its committed artifact before believing any of it.

— DEV
