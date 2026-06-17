# GauntletGate — Walkthrough lane (first-run truth + interface wiring)

**Project:** KimCad · **Commit:** `09b979c` (0.9.0b4 + cold-start managed-Ollama fix + audit-watchlist remediation)
**Date:** 2026-06-17 · **Lane:** Walkthrough (inside `/gauntletgate all`)
**Method:** the REAL app (`kimcad web`) driven via the live preview/Playwright harness on port 8718, in a **constructed + verified** true first-run state (Ollama ABSENT). This lane's report is an input to the Full lane.

---

## First-run verdict

> **Reaches the core feature ✅ — first-run coverage VALID.**

A brand-new user on a machine with **no Ollama** is no longer dead-ended. The first-run wizard's "Set up your AI" step now performs the setup in-app (one button, "Set up KimCad's AI") — the prior Critical (UX-COLD-001: "go install Ollama yourself → check again", with "Design it" disabled and no in-product path forward) is **resolved and verified live**.

## Environment-provisioning attestation (verified — not assumed)

| What | State used | How VERIFIED |
|---|---|---|
| Profile / `USERPROFILE` / app-data isolation | fresh temp dir `…\kimcad-gate-coldhome` | App wrote `…\kimcad-gate-coldhome\AppData\Local\KimCad\{config,output}` and (on the engine fetch) `…\KimCad\ollama\` into the isolated path; `/api/settings` returned **defaults** (`cloud_enabled:false`, no connectors) — proving the real `~/.kimcad/settings.json` (`cloud_enabled:true` + Bambu/OctoPrint connectors) did **not** leak. The real profile was confirmed untouched after the run. |
| First-run flags | unset | Wizard auto-opened ("Welcome to KimCad" dialog) on launch — the returning-user path was not taken. |
| External dependency: **Ollama** | **ABSENT** | (1) PATH stripped of the Ollama dir → `shutil.which("ollama")` miss; (2) `LOCALAPPDATA`→temp → the `…\Programs\Ollama\ollama.exe` fallback miss; together `find_system_ollama()` returned **None** (empirically confirmed). (3) The configured LLM `base_url` was overlaid to a dead loopback port (`127.0.0.1:11533`) so the server probe genuinely failed → `/api/model-status` = `running:false`. The user's real Ollama on `:11434` was deliberately left running (untouched, non-invasive) and is not what the app probed. |
| Data store | empty | Fresh isolated `~/.kimcad`; `/api/settings` = shipped defaults. |
| Network | online | Real GitHub fetch of the portable engine succeeded (bytes streamed). |

**Isolation verified?** YES (the app provably used the clean state). **→ First-run coverage: VALID.**

> Note: the prior cold-start audit's **QA-COLD-004** (the `USERPROFILE` override in the launch config silently did not isolate the profile) was the exact failure this lane guarded against. Root cause re-confirmed here: `Path.home()` *does* honor `USERPROFILE` for the venv interpreter (probed directly); the prior harness used a `cmd /c "… set USERPROFILE …"` chain that didn't propagate reliably. This lane used a constructed child environment instead and **proved** the isolation took before trusting any finding.

## Provisioning matrix — cells walked

| | dependency ABSENT | dependency PRESENT |
|---|---|---|
| **first-run, empty data** | ✅ WALKED THIS LANE (cold wizard, core action gated-with-path-forward, setup wire fired) | established by prior full `/walkthrough` (b4+UI, design→gate→slice→download→real `.3mf`) |
| **returning, populated** | n/a (a returning user has set up) | established by prior full `/walkthrough` |

The mandatory **dependency-ABSENT** row was walked live this lane. The dependency-PRESENT rows were exercised end-to-end by the prior full `/walkthrough` on the same head's UI (real Playwright, real OrcaSlicer slice, proven motion-bearing `.3mf`); the Full lane's QA role re-exercises the real tool.

## Findings (cold surface)

**No Blockers, no Criticals.** The headline cold-start fix is present and works.

| ID | Severity | Finding | Evidence | Status |
|---|---|---|---|---|
| (resolved) UX-COLD-001 | — | Onboarding dead-end on a fresh machine | Step 2 now shows status **"Not set up yet"** + copy *"KimCad sets up its AI for you — no separate install…"* + one button **"Set up KimCad's AI"**; clicking it drives `/api/model-pull` → engine row `status:"pulling"`, `total:1,461,613,335` (≈1.4 GB), `completed` climbing (52→134 MB), partial zip landing in the isolated managed dir; wizard renders **"AI engine setting up… 14%"**. No "Get Ollama / install / check again" detour anywhere on the step. | **VERIFIED FIXED** |
| (resolved) ENG-COLD-002 | — | Non-default port misclassified as "cloud, ready" | `/api/model-status` cold = `{backend:"local", running:false, model_present:false}` with the dead-port loopback `base_url` — classified **local** (loopback host), probed, honestly reported down. The `"11434"`-substring bug is gone (code at `webapp.py:1683`). | **VERIFIED FIXED** |
| (resolved) UX-COLD-003 | — | Cold landing left "Design it" + chips interactive-looking | Cold banner now reads *"Your local AI isn't ready yet — finish setup (the wizard's "Set up KimCad's AI") to design."* and **"Design it" is `disabled:true`** (confirmed via DOM). The banner routes to the fix. | **VERIFIED FIXED** |
| (resolved) UX-COLD-005 | — | Inconsistent 10–13 GB figure at peak-abandonment | Wizard copy now standardized (~7.7 GB models / ~1.4 GB engine; the engine row's `total` matches the pinned 1.4 GB). | **VERIFIED FIXED** |

## Wiring / runtime checks

- **Console:** clean across the cold walkthrough (no errors/warnings).
- **`/api/health`:** `{version:"0.9.0b4", openscad:true, orcaslicer:true, cadquery:true}` — installed-mode pathing resolves all bundled binaries.
- **Auto-start on launch:** `serve()` → `ensure_serving_background()` probes the default `:11434` (no-op when a system Ollama is up) and does **not** auto-fetch in the cold/overlaid state — the cold state persists until the user clicks Set up. No surprise background download.
- **Visual:** professional, coherent UI (Kim avatar in topbar + wizard, designer-pass disclosure for cloud speed-ups). Screenshots on file (this session's transcript): cold Welcome, cold "Set up your AI", and "AI engine setting up… 14%".

## Hand-off to Full

First-run is VALID and clean. The Full lane's QA/Test roles should extend (not redo) this: re-exercise the REAL tool (live Ollama on `:11434` + OrcaSlicer) for the warm design→gate→slice path, and audit the API/protocol/perf/security/docs layers this lane doesn't cover.
