# KimCad Tester Directive 006 — Clean-Machine Acceptance Test (0.9.0b6 — single-head honest release)

**NONCE:** `KCT-006-20260616-B6`  ← echo this verbatim on line 1 of your report.
**Release:** v0.9.0b6
**What changed since b5:** the **Snapmaker U1 + the multi-toolhead UI were REMOVED**. b5's headline
multi-toolhead slice was found to fail 100% on the clean machine (KimCad builds a single solid mesh —
nothing to assign extra materials to — and OrcaSlicer rejected the multi-filament input). b6 ships the
product **single-material for every printer** and is honest about it; multi-material / multi-head is
"in development — coming soon." **This run proves the single-head product is clean and the U1 is gone.**
**Download:** `KimCad-Setup-0.9.0b6.exe` — `https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.0b6`
**Expected SHA-256:** `7b21961b138a71b1295482298df596df00812968531caf104ba8302fa7920e0f`
**Expected size:** `204,761,485` bytes   **Source commit:** `18b51f4`

---

## Hard rules (same as 003–005)

1. **EVIDENCE, NOT NARRATION.** Every claim cites a file you committed under `tester/evidence/006/`
   (screenshot `.png`, raw dump `.txt`, hash, JSON). No artifact → not a finding.
2. **PROVE THE BUILD FIRST.** Phase 3 is a hard gate (four checks below). Any failure ⇒ STOP and report.
3. **Report to** `tester/reports/report-006.md`; `STATUS.md` heartbeat after each phase (~10 min).
   Severity-tag findings: Blocker / Critical / Major / Minor / Nit.

## Ground rules
- Test the INSTALLED app, not a dev build. You may `git clone` read-only for `scripts/verify_install.py`.
  Do NOT build the repo / venv / pip install. Do NOT set `core.hooksPath`. Plain git. Never force-push.
- Model inference is CPU/iGPU (30–120 s/plan is normal) — record times, don't call slow a fail.

> **Phase-2 install heads-up:** GUI installer automation may be blocked. Try silent first:
> `KimCad-Setup-0.9.0b6.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=install.log`, check the
> uninstall registry for "KimCad 0.9.0b6". If it hangs, ask Scott to click through it; then drive the
> installed app (grantable as "KimCad").

## Phase 0 — Confirm the clean machine  *(evidence: 01-systeminfo.txt, 02-clean.txt)*
`winver` + OS/CPU/RAM; `Get-Command node,ollama,kimcad`; uninstall-registry KimCad check. PASS: no
prior KimCad, no Node; WebView2 present.

## Phase 1 — Download + integrity  *(03-sha256.txt)*
`Get-FileHash KimCad-Setup-0.9.0b6.exe -Algorithm SHA256`. **PASS only if it equals `7b21961b138a71b1295482298df596df00812968531caf104ba8302fa7920e0f`**
and size is `204,761,485` bytes.

## Phase 2 — Install  *(04-installed.txt, 04-install.log)*
Silent-first. Record admin?/location/time. Confirm uninstall registry shows **0.9.0b6**.

## Phase 3 — BUILD-IDENTITY GATE  *(all four; evidence each)*
1. **Model** `qwen2.5:7b` (Settings → AI / `kimcad models`) → `05-model.txt` + shot.
2. **Landing chips** — exactly: `an 80 × 60 × 40 mm project box with a lid`, `a desk cable clip for an
   8 mm cable`, `a round trinket dish, 90 mm across` → `06-landing-chips.png`.
3. **Verifier** — `verify_install.py <INSTALL_DIR>` → `07-verify-install.txt` ends `VERIFY-INSTALL: ALL GREEN`.
4. **b6 marker — Snapmaker U1 is GONE.** In the Export panel printer picker, confirm there is **NO
   "Snapmaker U1"** entry, and **no printer shows multiple "Extruder N" material dropdowns** — every
   printer shows a single "Material" dropdown. Screenshot the picker + a selected printer's single
   Material dropdown → `08-no-snapmaker-single-material.png`. If a Snapmaker U1 appears, or any printer
   shows >1 material dropdown, that's a **Blocker** (wrong build / removal didn't take) — STOP.

## Phase 4 — Real model setup  *(09-ollama.txt)*
Install Ollama; pull `qwen2.5:7b` + `qwen2.5vl:3b` (prefer the app's "Download now"); `ollama list`.

## Phase 5 — Core end-to-end (real model + real GPU)  *(evidence each — THE HEADLINE)*
For **each** of the 3 curated chips: screenshot part + viewport (`10-chipK-<name>.png`), record model +
time; devtools console (`11-chipK-console.txt`) + the **WebGL renderer string verbatim** (`13-webgl.txt`).
Then with evidence: a custom dimensioned prompt → design → slider re-render → **slice → a real print
file** → export `.3mf` + `.stl` (sizes, `17-export.txt`); photo/sketch on-ramp seed. A chip that
dead-ends or errors = **Critical**. **Confirm the slice produces a real `.3mf` print file** for a normal
single-material printer (this is the core product working).

## Phase 5b — Single-material confirmation  *(evidence)*
Pick 2–3 different printers (e.g. Bambu P2S, a Creality, a Prusa). For each, confirm: one **Material**
dropdown (no Extruder N), and slicing produces a print file. Screenshot one (`20-single-material-slice.png`).
Confirm Settings → Printer connections shows the normal connector templates and **no "Snapmaker U1"
connection**. `21-connections.png`.

## Phase 6 — Failure states  *(evidence)*
Stop Ollama → design → recoverable "AI not running" + retry (not a 500). Non-geometric prompt
(`a feeling of nostalgia`) → graceful; geometric refine chips NOT offered with no part.

## Phase 7 — Uninstall  *(evidence)*
Uninstall via Apps; confirm gone. Note whether `%LOCALAPPDATA%\KimCad` user data remains.

---

## Report → `tester/reports/report-006.md`
1. NONCE line 1. 2. Verdict: would a real user succeed on the single-head product? ship / caveats /
blocked. 3. Per-phase table | PASS/FAIL/PARTIAL | evidence. 4. Findings (each cites an artifact),
severity-tagged. 5. Model timings + the WebGL renderer string verbatim. 6. Open questions for DEV.

Commit the report + all of `tester/evidence/006/`, append `STATUS.md`, push. DEV verifies every claim
against its artifact.

— DEV
