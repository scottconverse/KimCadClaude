# KimCad Tester Directive 008 — Smoke Verification (0.9.2 — messaging clean-up)

**NONCE:** `KCT-008-20260617-092`  ← echo this verbatim on line 1 of your report.
**Build under test:** **`0.9.2`** — published GitHub pre-release (tag `v0.9.2`, source commit
`3f9eb57` on `main`). This is `0.9.1` + a full GauntletGate remediation pass: 19 findings
(1 Critical · 3 Major · 8 Minor · 7 Nit) all driven to 0/0/0/0/0.
**What changed since 0.9.1 (directive-007):** All changes are messaging/copy/reliability — no
installer-bundling change, no new features, no first-run flow change.

**Download:** `https://github.com/scottconverse/KimCadClaude/releases/tag/v0.9.2`
→ download `KimCad-Setup-0.9.2.exe`
**Expected SHA-256:** `B56C8D4DEC6E99848E3C2D4816089F5E2F290CD4ED933834A9E7FDB94F84980A`
**Expected size:** ~203 MB (203.5 MB)
**Source commit:** `3f9eb57` (tag `v0.9.2`)

---

## Scope: this is a smoke test, NOT a full clean-machine reinstall

The 0.9.2 changes are messaging and internal reliability fixes. The installer bundling,
first-run flow, and model-download pipeline are **UNCHANGED** from 0.9.1 (which you
validated end-to-end in directive-007). You do NOT need to repeat the full cold-machine
gauntlet. What you DO need to verify:

1. **Installer SHA + version** — the downloaded binary matches the stated hash and reports 0.9.2.
2. **Engine-down message** — the exact wording when KimCad can't reach its AI engine.
3. **Settings nav** — section links within Settings scroll correctly without dismissing the panel.
4. **Model-store path in docs** — the installed copy's README reflects `%LOCALAPPDATA%\KimCad\models`,
   not "Ollama's standard model store."

If you have the 0.9.1 install still present on the tester machine, upgrade in-place
(install over it) — you do NOT need to uninstall and reinstall from scratch.

---

## Hard rules

1. **EVIDENCE, NOT NARRATION.** Every claim cites a file committed under `tester/evidence/008/`
   (screenshot `.png`, raw dump `.txt`, hash). No artifact → not a finding.
2. **PROVE THE BUILD FIRST.** Phase 1 (hash + version) is a hard gate. Any mismatch ⇒ STOP and report.
3. **Report to** `tester/reports/report-008.md`. Severity-tag findings: Blocker / Critical / Major / Minor / Nit.

---

## Phase 1 — Verify the build  *(hard gate)*

**1a. Hash check**
```
certutil -hashfile KimCad-Setup-0.9.2.exe SHA256
```
Expected: `B56C8D4DEC6E99848E3C2D4816089F5E2F290CD4ED933834A9E7FDB94F84980A` (case-insensitive)

**1b. Install and check version**
Install normally (double-click or silent). Then open the app → About section in Settings.
Expected: `0.9.2`

**Evidence required:** `tester/evidence/008/01-hash.txt`, `tester/evidence/008/02-version.png`

If hash or version mismatches → **STOP, report Blocker, do not proceed.**

---

## Phase 2 — Engine-down message  *(highest-priority new check)*

The headline fix of 0.9.2. The error message when KimCad can't reach its AI engine must say:

> **"KimCad couldn't reach your local AI — it isn't running. You can restart it from Settings, then try again."**

No variant of "Ollama" should appear in any user-facing error message.

**How to trigger it:**
- Stop the managed engine (Task Manager → end `ollama.exe` if running).
- Open KimCad. Try to run a design. The canvas / error toast should show the exact message above.

Check ALL surfaces:
- Landing canvas (idle state when AI is down)
- Design request error toast / status chip
- Settings → AI setup panel (engine status indicator)

**Evidence required:**
- `tester/evidence/008/03-engine-down-canvas.png`
- `tester/evidence/008/04-engine-down-settings.png`

**What to report:**
- If exact message matches → ✅ PASS
- Any surface says "Ollama" → Minor finding (or Critical if in a primary error path)
- Any surface shows "install Ollama from ollama.com" → **Critical**

---

## Phase 3 — Settings nav  *(quick Nit-level check)*

Open Settings. Click a section nav link in the left sidebar (e.g., "About", "AI setup").
Expected: panel stays open, page scrolls to the section.
Old (broken) behavior: clicking "About" dismissed the Settings panel entirely.

**Evidence required:** `tester/evidence/008/05-settings-nav.png`

---

## Phase 4 — Model-store path in docs  *(quick TW fix check)*

Check the installed README (`C:\Program Files\KimCad\README.md` or the About section).
Confirm that descriptions of where models are stored say `%LOCALAPPDATA%\KimCad\models`,
NOT "Ollama's standard model store."

**Evidence required:** `tester/evidence/008/06-model-path-docs.txt`

---

## Phase 5 — Regression smoke  *(one design end-to-end)*

Type a simple prompt (e.g., "a small coin tray, 80 mm across"). Confirm:
1. A plan appears and a parametric part renders.
2. The gate/slice flow completes (produces a print file).

**Evidence required:** `tester/evidence/008/07-smoke-design.png`

---

## Report format

`tester/reports/report-008.md`:

```
KCT-008-20260617-092

## Verdict: [SHIP / SHIP-WITH-MINORS / DO-NOT-SHIP]

## Phase 1 — Build: [PASS/FAIL]
## Phase 2 — Engine-down message: [PASS/FAIL] + findings
## Phase 3 — Settings nav: [PASS/FAIL]
## Phase 4 — Model-store docs: [PASS/FAIL]
## Phase 5 — Regression smoke: [PASS/FAIL]

## Findings (Blocker/Critical/Major/Minor/Nit)
[list]

## Evidence index
[file list under tester/evidence/008/]
```

---

## Sign-off threshold

- **SHIP → SIGN-OFF-008:** Phase 1 + Phase 2 PASS, no Blocker/Critical.
- **DO NOT SHIP:** Any Blocker or Critical. Report immediately.
