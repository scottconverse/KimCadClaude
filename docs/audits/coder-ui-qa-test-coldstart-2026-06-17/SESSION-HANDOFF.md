# KimCad — Session Handoff (paused 2026-06-17 for compaction)

## Where things stand (the canonical truth)
- **`origin/main` @ `09b979c`** = canonical **0.9.0b4** + the **cold-start managed-Ollama onboarding fix** + the **audit-watchlist remediation**. Full self-hosted gate GREEN (1657 pytest + 405 vitest + build-repro + live OrcaSlicer + CadQuery worker-sandbox). No tag (Scott controls tags).
- **`origin/tester` @ `5fbd59b`** = **directive-007** (`tester/directive-007-clean-install-0.9.0b4-coldstart.md`), the clean-machine cold-start gauntlet. NONCE `KCT-007-20260617-CS`. Its Expected SHA-256 + size are deliberate **TODO** (filled after the installer is built, like directive-005).

## What shipped in this session (recap)
1. Rolled back the withdrawn b5/b6 Snapmaker saga → coherent b4; restored 3 unrelated post-b4 UI commits (Kim avatar + designer pass).
2. Full `/walkthrough` + 5-role `/audit-team` on b4+UI → remediated to 0/0/0/0/0 (commit `e7deafb`).
3. **Cold-start fix** (the headline — Scott hit a first-run DEAD-END: no Ollama → wizard told him to install it himself): KimCad now **manages its own AI** — reuse a system Ollama, else auto-fetch the pinned + SHA-256-verified portable engine and run it headless; the wizard's **"Set up KimCad's AI"** does it in one flow. New modules `kimcad/ollama_runtime.py` + `kimcad/ollama_fetch.py`; one-click `start_setup` on `/api/model-pull`; auto-start wired into `serve`/`shell`. (UX-COLD-001 / ENG-COLD-002.)
4. Drove the audit **watchlist to zero** (no-deferral): ENG-004 worker network-deny (subprocess-proven), TEST-103 catalog verify-record (hygiene test now enforces), webapp.py single-source route table, UX-009 keep. Only genuine deps remain: **#11** real-metal send + the native-Winsock-bypass / OS-FS half of ENG-004 (admin-level firewall/AppContainer).
5. Delivered the `/walkthrough` skill-fix prompt (cold-start blind-spot) + recorded the lesson to memory.

## NEXT ACTIONS (in order) — this is where we paused
1. **Run `gauntletgate` on `09b979c` BEFORE building the installer.** Scott explicitly wanted this dev-side adversarial readiness gate run first; he was about to pick a lane. I recommended **`all`** (lite + walkthrough + full). Run it, fix anything it finds, THEN build.
2. **Build the installer from `09b979c`** for directive-007. **Blocker:** no installer carries the cold-start fix (it's unreleased main-HEAD), and **Inno Setup is NOT on this box**. Awaiting Scott's **A/B/C**:
   - **A (recommended):** I set up Inno Setup here (admin) + `scripts/build_installer.py` from `09b979c`, then Scott transports `KimCad-Setup-0.9.0b4-coldstart.exe` to the clean machine (private — no public tag).
   - **B:** draft (non-public) pre-release with the installer asset.
   - **C:** from-source clean install (tests the cold-start logic, not the installer double-click).
3. After the build: **fill directive-007's Expected SHA-256 + size** (a one-line tester-branch commit, as directive-005 did) → the tester runs the gauntlet on the clean (NO-Ollama) machine.

## Key references
- Cold-start audit dir: `docs/audits/coder-ui-qa-test-coldstart-2026-06-17/` (FINDINGS, VERIFICATION-LOG, walkthrough-skill-update-prompt).
- Watchlist closure: `docs/audits/audit-team-b4-2026-06-16/next-sprint-watchlist.md` (Closure section).
- Memory: `kimcad-b4-audit-state`, `walkthrough-coldstart-blindspot`.
- The clean test machine MUST start with **no Ollama** (Phase 0) — that's the whole point of directive-007.
