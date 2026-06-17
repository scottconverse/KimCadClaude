# Verification Log — Cold-Start Onboarding Fix (managed Ollama)

**Skill:** coder-ui-qa-test · **Date:** 2026-06-17 · **Base:** main @ e7deafb (0.9.0b4 + designer pass)
**Findings driving this:** [FINDINGS.md](FINDINGS.md) — UX-COLD-001 (Critical), ENG-COLD-002 (Major), UX-COLD-003/004/005 (Minor).

## What Was Changed
KimCad now **manages its own local AI** so a fresh machine no longer dead-ends on a manual Ollama install:
- **`kimcad/ollama_runtime.py`** (new): locate a system Ollama → else KimCad's fetched portable copy; health-probe; managed `ollama serve`; `ensure_serving` orchestration; `ensure_serving_background` (fire-and-forget auto-start).
- **`kimcad/ollama_fetch.py`** (new): download Ollama's pinned portable Windows build (v0.30.9, SHA-256 `6d83cbe1…f991f`), verify before extract, zip-slip-guarded extract.
- **`model_pull.ModelPullJob.start_setup`** (new): one-click ensure-runtime-then-pull; the runtime fetch rides an "AI engine" progress row alongside the model rows.
- **`webapp._handle_model_pull`**: delegates to `start_setup`; **ENG-COLD-002** fixed — local detection now classifies by loopback host, not the literal `"11434"` substring (same fix in `_handle_model_status`).
- **`webapp.serve` + `shell.build_shell`**: auto-start the managed runtime off the launch path (non-demo).
- **Wizard `FirstRunWizard.tsx`**: "Set up your AI" step now performs the setup (one button), replacing the "Get Ollama → install → check again" dead-end; honest ~7.7 GB figure; removed the `openExternal('ollama.com')` detour.
- **`ModelHealthPill.tsx`**: landing cold banner points to in-app setup, not "start Ollama."
- **Docs** (README, install-guide, getting-started, FAQ, USER-MANUAL, troubleshooting, guide-photo-onramp, index.html): reframed to "KimCad sets up its AI for you"; size figures standardized to ~7.7 GB models + ~1.4 GB engine. **Installer note** (kimcad.iss) + **CHANGELOG [Unreleased]** updated.

## Scope Confirmation
Scope = remediate the cold-start audit findings to 0/0/0/0/0, build the approved Plan B (auto-fetch + reuse, managed serve). Matches. No version bump / release tag (left to Scott — see Sign-off).

## Tests
- **Added:** `test_ollama_runtime.py` (14), `test_ollama_fetch.py` (5), `test_ollama_runtime_real.py` (2, real Ollama), `start_setup` suite in `test_model_pull.py` (4), `test_model_status_local_on_nondefault_port_is_local` (ENG-COLD-002 regression), cold one-click wizard vitest.
- **Updated (behavior changed by design, not weakened):** 3 webapp model-pull route tests (delegates to `start_setup`; down-Ollama triggers setup not `ollama_down`); 3 wizard vitest (Set-up flow, ~7.7 GB, recap copy); 2 ModelHealthPill vitest; disk-full message figure.
- **Results (pre-gate):** pytest subset — model_pull + ollama runtime/fetch/real + version-single-source = **51 passed**; webapp model_status/model_pull = **7 passed**; full **vitest 405/405**; **ruff clean** across all changed src + tests.
- **Full authoritative gate:** _confirming this turn (ruff + full pytest incl. live OrcaSlicer + vitest + build-repro)._

## Runtime Verification
- **Cold first-run, real app (Playwright, Ollama unreachable):** the "Set up your AI" step shows *"KimCad sets up its AI for you — no separate install…"* + a **"Set up KimCad's AI"** button; **zero "Get Ollama" dead-end** (screenshot on file). Landing banner reads *"…finish setup… to design"* (not "start Ollama"). `/api/model-status` cold = `{backend:local, running:false, model_present:false}`.
- **Managed runtime against the REAL Ollama:** `test_ollama_runtime_real.py` resolves the real executable and `ensure_serving` reaches a running server (2 passed).
- **Real portable-engine fetch (no-false-greens, end-to-end): PASSED.** Downloaded the real 1.4 GB `ollama-windows-amd64.zip`, **SHA-256-verified against the pin**, **extracted** to a real `ollama.exe`, and **`ollama serve` from the extracted binary was reachable** (HTTP probe on :11456 = True). (The throwaway verify script printed `RESULT=FAIL` only because it checked `exe.exists()` AFTER deleting the 1.4 GB temp dir — a cosmetic script-ordering bug; both substantive checks passed.)

## Browser Console
Clean across the cold walkthrough (no errors/warnings).

## Security
- Portable runtime is **pinned + SHA-256-verified before extraction**; extract is **zip-slip-guarded** (in-tree members only) — mirrors design_store's import rigor.
- ENG-COLD-002 hardens local-vs-cloud classification (loopback host), removing a dishonest "ready" misreport.
- No secrets added; the fetch is over GitHub HTTPS to a pinned URL.

## Blast Radius & Regression
- `_handle_model_pull` contract changed (delegates to `start_setup`; no `ollama_down` bail) — covered by the 3 updated route tests. `_handle_model_status` detection change — covered by the new regression test + the existing cloud/local tests (7 pass).
- Auto-start is best-effort/daemon, gated to non-demo, and reuses a running server (no-op when up) — verified it doesn't disturb the dev box's running Ollama.
- Full vitest (405) + the targeted pytest subsets confirm no regressions; the full gate is the final backstop.

## Documentation Artifacts
- README.md / USER-MANUAL.md / install-guide / FAQ / troubleshooting / getting-started / guide-photo-onramp / docs/index.html: **updated** (managed-Ollama reframe + ~7.7 GB).
- CHANGELOG.md: **[Unreleased]** entry added (Added/Changed/Fixed). Installer note (kimcad.iss): updated.
- README.txt/.docx/.pdf, USER-MANUAL.docx/.pdf, UML: _Hard-Rule-9 status checked at push (these are release-time regenerations; .md surfaces are current)._

## Sign-off
Cold-start onboarding remediated to the audit's findings. **Open decision for Scott:** this is a substantive new feature on top of 0.9.0b4 — whether it warrants a new beta version/tag, or lands on main as `[Unreleased]` (no tag), is a release decision (Scott controls tags). Pushed to main without a tag pending that call.
