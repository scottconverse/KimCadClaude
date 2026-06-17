# GauntletGate — Full lane · Technical Writer deep-dive

**Project:** KimCad · **Commit:** `09b979c` (0.9.0b4 + cold-start managed-Ollama fix + audit-watchlist remediation)
**Date:** 2026-06-17 · **Lane:** Full (Technical Writer role) · **Baseline:** `c784a23` (0.9.0b4)
**Scope:** README / ARCHITECTURE / USER-MANUAL / install-guide / FAQ / troubleshooting / getting-started / docs/index.html / MODEL-GUIDE / CHANGELOG / ROADMAP / installer note — accuracy, completeness, honesty. Focus: is the managed-Ollama reframe consistent everywhere; are size figures (~7.7 GB models / ~1.4 GB engine) and the version string (0.9.0b4) consistent; does any doc still describe pre-fix behavior.

I read the Walkthrough lane report (`02-walkthrough.md`) first and did **not** re-walk the cold first-run UI. I extend it: the on-screen wizard copy it verified (`~7.7 GB` / `~3 GB`, "Set up KimCad's AI", no "Get Ollama" dead-end) is the source of truth I cross-checked the *prose docs* against.

---

## Verdict

**The managed-Ollama reframe is consistent and honest across every prose doc surface.** README, install-guide, troubleshooting, FAQ, USER-MANUAL, getting-started, ARCHITECTURE, ROADMAP, MODEL-GUIDE, docs/index.html, and the installer's user-facing final page all tell the same story: KimCad sets up its own AI engine, reuses a system Ollama if present, otherwise downloads the portable build (~1.4 GB) and the two models (~7.7 GB) via the in-app **Set up KimCad's AI** button — with manual `ollama pull` correctly demoted to an "if you prefer / if automatic setup fails" fallback. The version string is single-sourced and reads `0.9.0b4` everywhere. The b5/b6 Snapmaker withdrawal is documented honestly in the CHANGELOG.

**One Major finding blocks a clean pass:** this commit **lowered the documented free-disk recommendation from 20 GB to 12 GB** across four docs, but the runtime disk pre-check still demands **15 GB** and the disk-full error string still says **8 GB** — so a user who provisions exactly the newly-documented 12 GB is **hard-blocked** by KimCad's own pre-check with a message that contradicts the install guide. The headline size figure (~7.7 GB download) is now consistent in *prose*, but the *free-disk* number is freshly inconsistent with the code this commit shipped alongside.

**Roll-up:** 0 Blocker · 0 Critical · 1 Major · 2 Minor · 1 Nit.

---

## Findings

### [DOC-101] — Major — Accuracy — Docs lowered "free disk" to 12 GB but the runtime pre-check still blocks below 15 GB (and a third path says 8 GB)

**Evidence (doc vs runtime contradiction, all in this delta's blast zone):**
- This commit changed the documented free-disk recommendation from the b4 baseline's **20 GB** down to **12 GB**:
  - `git show c784a23:docs/install-guide.md` → *"about **20 GB free disk space** (mostly the AI models)"*; HEAD `docs/install-guide.md:83` → *"about **12 GB of free disk space** as headroom (the AI engine ~1.4 GB plus the ~7.7 GB of models, with room to spare)"*.
  - Same 20→12 change in `docs/getting-started-windows.md:22`, `docs/USER-MANUAL.md:56`, `docs/troubleshooting.md:107`.
- The runtime disk pre-check was **not** changed and still requires 15 GB: `src/kimcad/model_pull.py:33` `_EST_GB = {"chat": 11.0, "vision": 4.0}`; `model_pull.py:124` `need_gb = sum(_EST_GB...)` → **15 GB**; `model_pull.py:130-136` blocks the pull and emits `"Not enough disk space: about 15 GB is needed and only {free} GB is free."` when `free_gb < 15`.
- A **third, separate** number on the disk-full mid-download path: `model_pull.py:62-68` `_friendly_error` → *"the models are about **8 GB**, plus room to unpack."*

**Why it's a doc-accuracy defect (not just a code nit):** the docs are a contract. A careful user reads the install guide, frees the recommended ~12 GB, opens KimCad, clicks **Set up KimCad's AI**, and is **hard-stopped** before a byte moves with *"about 15 GB is needed and only 12 GB is free"* — a message that flatly contradicts the page they just followed. The pre-check threshold (15 GB) being generous over the real ~7.7 GB download (unpack headroom) is *fine*; the defect is that the documented free-disk floor was moved **below** that threshold, so the docs now promise a margin the product refuses to honor. The three different numbers a user can encounter for "the AI download" — **7.7 GB** (wizard button + prose), **8 GB** (disk-full string), **15 GB** ("needed" pre-check), against a **12 GB** "keep free" recommendation — are exactly the kind of size-figure drift the b4 audit's DOC-003 set out to kill (`docs/audits/audit-team-b4-2026-06-16/03-documentation-deepdive.md:127`). This commit fixed the *prose* total but reopened the inconsistency on the *free-disk* axis.

**Blast radius:** every first-run user who provisions to the documented 12 GB on a near-full small SSD — the exact "layperson on a modest laptop" the managed-Ollama reframe is *for*. They hit a confusing contradiction at the highest-trust moment (first launch), with no way to reconcile the two numbers from the UI. It does not corrupt data and a user with abundant disk never sees it, so it is Major, not Critical — but it directly undercuts the headline fix's promise of a frictionless first run.

**Fix path (pick one and propagate; do not leave three numbers):**
1. Cleanest: raise the documented free-disk recommendation back above the pre-check — e.g. *"keep about **16 GB** free as headroom"* — and relabel it consistently as headroom over the ~7.7 GB download in install-guide:83, getting-started:22, USER-MANUAL:56, troubleshooting:107. **Or**
2. Lower `_EST_GB` so `need_gb` lands at a value the 12 GB recommendation comfortably clears (e.g. chat 8.0 + vision 3.5 = 11.5), and update the `_friendly_error` "8 GB" string to the canonical ~7.7 GB.
   In both cases, reconcile `model_pull.py:67` ("8 GB") to the same canonical download figure used everywhere else.

**Suggested test:** a doc-vs-code consistency test asserting `sum(_EST_GB.values()) <= DOCUMENTED_FREE_DISK_GB`, with `DOCUMENTED_FREE_DISK_GB` a single named constant the docs are generated from or grep-checked against; plus update the now-stale `tests/test_model_pull.py:203` (`assert "8 GB" in ...`) to the chosen canonical string so the assertion can't silently re-pin the wrong number.

---

### [DOC-102] — Minor — Accuracy — Installer source comment still says the models are "ANOTHER ~13 GB"

**Evidence:** `installer/kimcad.iss:34` (an Inno Setup *comment*, not user-facing): *"the AI models are ANOTHER ~13 GB that the in-app wizard downloads — said plainly on the final page below."* The user-facing final page just below it (`kimcad.iss:73-79`) was correctly updated in this commit to *"a portable AI engine (about 1.4 GB...) plus the two models (about 7.7 GB total)"*. So the rendered installer text is right; only the stale 13 GB comment remains, and it claims to describe a final page that no longer says 13 GB.

**Why it's Minor:** invisible to end users (comment only), but it's a misleading breadcrumb for the next maintainer touching the installer — it asserts the final page says 13 GB when it says 7.7 GB, inviting a "fix" in the wrong direction.

**Fix:** update the comment to `; ...the AI models are ANOTHER ~7.7 GB (plus a ~1.4 GB portable engine on first run)...`.

**Suggested test:** none needed (comment); fold into the DOC-101 single-source-of-truth pass.

---

### [DOC-103] — Minor — Accuracy — README "What the installer puts on your machine" omits the managed AI engine

**Evidence:** `README.md:28-35` ("What the installer puts on your machine") lists the WebView2 shell + app, embedded CPython, OpenSCAD/OrcaSlicer/PrintProof3D, and per-user data — but does **not** mention that KimCad now sets up and stores its own portable Ollama engine under the data folder on first run. The managed engine is described thoroughly later (README:120-128, 172-181) and in install-guide/FAQ, and the Walkthrough verified it lands in `…\KimCad\ollama\`, so this is an omission-in-one-section, not a contradiction. The parallel install-guide "What the installer puts where" (`install-guide.md:48-59`) has the same gap — it never says where the portable engine lives.

**Why it's Minor:** the reframe is correct everywhere it's stated; this is a completeness gap in the two "what goes where" inventories, which a privacy- or disk-conscious user reads specifically to know what lands on their machine and where. Given the engine is a new ~1.4 GB on-disk artifact this commit introduced, it belongs in those inventories.

**Fix:** add one bullet to each inventory: *"KimCad's managed AI engine (portable Ollama) + the downloaded models — under the per-user data folder (`%LOCALAPPDATA%\KimCad\ollama`), not Program Files; removable with the app data."* Confirm the exact path against `ollama_runtime.py` before stating it.

---

### [DOC-104] — Nit — Consistency — `docs/troubleshooting.md` "Where is my stuff?" doesn't list the new engine location

`docs/troubleshooting.md:94-98` enumerates designs (`~/.kimcad`), app output (`%LOCALAPPDATA%\KimCad`), and the app folder, but not the managed engine dir. Same root cause as DOC-103; listed separately only because troubleshooting is where a user goes to reclaim disk. Roll into the DOC-103 fix.

---

## What's working (honest credit)

- **The managed-Ollama reframe is genuinely consistent across all prose surfaces.** I grepped for stale "install Ollama yourself / go install / detect Ollama / start Ollama" imperatives across all `*.md` (and the `.iss`/`.html`): every remaining hit in a *current user-facing* doc is correctly framed as a **fallback** ("Already have Ollama? It's used automatically"; "if automatic setup fails... you can install Ollama yourself") — `README.md:121,183-188`, `install-guide.md:62-75`, `troubleshooting.md:9-17`, `USER-MANUAL.md:80-90,261-262`, `getting-started-windows.md:43-62`, `FAQ.md:36`, `docs/guide-photo-onramp.md`. The only bare "detect Ollama / start Ollama" strings left are in **historical audit reports and the ROADMAP/HANDOFF plan-of-record** (`ROADMAP.md:344`, `HANDOFF.md:79`), which correctly describe the *as-planned* Stage 10 wizard and are not user-facing setup instructions. No current doc instructs a user to install Ollama as the primary path.
- **Headline download size (~7.7 GB) is now consistent in prose and on-screen.** README:124,176, install-guide:68-70, FAQ:33-40, USER-MANUAL:56,86,262, getting-started:23,51, index.html:271,354, MODEL-GUIDE:10-11, and the verified wizard button (`FirstRunWizard.tsx:368` "~7.7 GB" / 369 "~3 GB") all agree. The prior FAQ "9 GB chat-model" misattribution (b4 DOC-003) is fixed.
- **Version string is single-sourced and consistent at 0.9.0b4.** `pyproject.toml:10` is the lone literal; `src/kimcad/__init__.py:3-14` reads it from package metadata; README badge:5, USER-MANUAL:15, index.html:433 all say 0.9.0b4; the Walkthrough confirmed `/api/health` returns `version:"0.9.0b4"` live. `test_version_single_source.py` pins it. The README:63 / CHANGELOG:355 "`0.9.0b1`" references are correctly historical (the stage-11 *initial* beta tag), not a current-version claim.
- **The b5/b6 withdrawal is documented honestly.** `CHANGELOG.md:8-15` states plainly that 0.9.0b5/b6 were cut, un-published, tags removed, code fully reverted, and "the canonical release remains 0.9.0b4," with the real reason (single solid mesh → nothing to assign multi-material to; OrcaSlicer rejected the multi-filament CLI input). This is exactly the no-false-greens honesty the gate wants.
- **CHANGELOG Unreleased section accurately describes this commit's three deltas** (Added: zero-install managed Ollama; Changed: "Set up your AI" now sets up the AI + honest 7.7 GB; Fixed: ENG-COLD-002 loopback-host classification) and matches the code (`ollama_runtime.py`, `ollama_fetch.py`, `webapp.py:1683` per the Walkthrough).
- **ROADMAP, ARCHITECTURE, MODEL-GUIDE model story is coherent:** `qwen2.5:7b` default planner (won 4/4), `gemma4:e4b` demoted to non-China fallback + vision-host, `qwen2.5vl:3b` vision, grammar-`format` fix explained, origin-neutrality stated honestly. ROADMAP's "superseded at 0.9.0b3" annotations preserve the historical Stage 6 verdict without lying about the current default. `config/default.yaml:87-92` comment was updated to match.
- **Honest-beta framing is intact and consistent:** unsigned installer / SmartScreen, SHA256SUMS.txt + release-manifest.json (no signed attestation — index.html:399 was corrected this commit from "signed attestation" to the manifest story), connectors mock-validated not metal-proven, "real-hardware print validation is the beta's own job." No overclaiming spotted.

---

## Could not assess

- **The actual rendered installer wizard text at runtime.** I read `installer/kimcad.iss` source (the `CreateOutputMsgPage` strings are correct), but did not build/run the installer to see the rendered pages. The source is the authority for prose; runtime rendering not verified this lane.
- **Whether `release-manifest.json` / `SHA256SUMS.txt` are actually produced and match** the docs' description — that's a build/release-artifact check, not a doc-prose check; out of this role's scope (Engineering/QA lane territory). I verified only that the docs describe them consistently (install-guide:22-46, index.html:399, README:40).
- **The exact on-disk path of the managed engine** (`%LOCALAPPDATA%\KimCad\ollama` vs another subdir) — the Walkthrough observed `…\KimCad\ollama\`; I did not read `ollama_runtime.py` closely enough to state the canonical path for the DOC-103 fix, so that fix must confirm it against the code.
- **Live model-status/pull copy in the running app** beyond what the Walkthrough captured — I relied on its verified screenshots and DOM reads rather than re-driving the UI, per the lane brief.
- **MODEL-GUIDE benchmark cross-links** (`benchmarks/stage-6-model-bakeoff.md`, `stage-9-vision-onramps.md`) — I did not open those to confirm the cited 4/4 and vision numbers reproduce; the MODEL-GUIDE's own table is internally consistent.
