# KimCad — Handoff: 0.9.2 patch (post-directive-007 Minor fixes)

**Date:** 2026-06-17  
**Reason for handoff:** Cowork version upgrade  
**Resumption prompt:** see bottom of this file

---

## Where we are

### Git state
- **`origin/main` HEAD:** `9ddea46` — "fix(tester-007): resolve 2 Minor findings from directive-007"
- **Published pre-release:** `v0.9.1` (tag at `3322936`) — the binary that was tester-tested
- **`origin/tester` HEAD:** `2ece763` — SIGN-OFF-007 committed (but this sign-off is WRONG — see below)

### The problem
Directive-007 (tester DESKTOP-2BR3SJR, clean-machine gauntlet) returned **SHIP — 0/0/0/0/0 findings... except 2 Minors**:

1. **Minor-1 (engine-down wording):** Chat showed "Make sure Ollama is running" — user never installed Ollama, not actionable
2. **Minor-2 (model orphan):** Managed-engine downloaded models to `~/.ollama`; uninstall left 7.34 GB behind

Both were fixed in source in commit `9ddea46` and the gate was run (1679 pytest / 405 vitest / build-repro green). But the SIGN-OFF-007 was issued and the campaign was closed WITHOUT rebuilding the installer. The `v0.9.1` binary in the published pre-release still has both Minors.

**Scott's rule: 0/0/0/0/0 means the SHIPPED ARTIFACT is clean — not just the source tree.** The session ended with Scott catching this and explicitly calling it a rationalization.

---

## What needs to happen (in order)

### Step 1 — Bump version to 0.9.2
Files to update (all in one commit, same pattern as the 0.9.1 sweep):
- `pyproject.toml`: `version = "0.9.2"`
- `frontend/package.json`: `"version": "0.9.2"`
- `frontend/package-lock.json`: `"version": "0.9.2"` (top-level + `node_modules/kimcad` if present)
- `CHANGELOG.md`: move the `[Unreleased]` section to `## [0.9.2] — 2026-06-17` (it already has the 2 Minor fixes documented)
- `installer/kimcad.iss`: `#define AppVersion "0.9.2"`
- `docs/install-guide.md`, `README.md`, `docs/troubleshooting.md`: any version references

The `scripts/bump_version.py` or `scripts/ci.sh` may have a version-check step — verify it passes after sweep.

### Step 2 — Rebuild the installer
```
python scripts/build_installer.py
```
Uses Inno Setup at `C:\kimcad-ci-tools\innosetup6`. Output: `dist/KimCad-Setup-0.9.2.exe`.  
Record SHA-256 and size:
```powershell
Get-FileHash dist\KimCad-Setup-0.9.2.exe -Algorithm SHA256
(Get-Item dist\KimCad-Setup-0.9.2.exe).Length
```

### Step 3 — Run the full gate
```
bash scripts/ci.sh
```
Must return 0 with 1679 pytest / 405 vitest / build-repro. The SPA was NOT changed (only Python + test files), so no rebuild needed before the gate — the gate's build-repro step will confirm.

### Step 4 — Commit and push
Commit the version sweep + rebuilt SPA bundle (if any frontend files touched) to `origin/main`.  
Tag: `git tag v0.9.2 && git push origin v0.9.2`

### Step 5 — Publish GitHub pre-release
```
gh release create v0.9.2 dist/KimCad-Setup-0.9.2.exe \
  --title "KimCad 0.9.2" \
  --prerelease \
  --notes-file dist/release-notes-0.9.2.md
```
Release notes should state: built on 0.9.1 + 2 Minor fixes from directive-007 (engine-down wording, model-orphan on uninstall).

### Step 6 — DEV-verify the 2 specific findings
Before touching the tester, DEV confirms the fixes are present in the new binary:
- **Minor-1**: Install 0.9.2, stop the managed engine, trigger a design → confirm the chat says "engine isn't running" not "Make sure Ollama is running"
- **Minor-2**: After the managed-engine first-run setup, confirm models land under `%LOCALAPPDATA%\KimCad\models`, NOT `~\.ollama\models`

### Step 7 — Issue a corrected SIGN-OFF-007 (or issue SIGN-OFF-007b)
SIGN-OFF-007 on `origin/tester` was premature (it closed on the `v0.9.1` binary with unfixed Minors). Options:
- Push a `SIGN-OFF-007b` to `origin/tester` that notes the correct resolution: findings fixed in `0.9.2` (commit `9ddea46`), rebuilt as `v0.9.2`, gate green, DEV-verified.
- The tester does NOT need to re-run the full 8-phase gauntlet — just the 2 specific findings (Minor-1 engine-down wording, Minor-2 model path). Those can be DEV-verified.

---

## Key files

| Purpose | Path |
|---------|------|
| Version in pyproject.toml | `pyproject.toml` line ~3 |
| Version in frontend | `frontend/package.json` line ~3 |
| Inno Setup | `installer/kimcad.iss` — `#define AppVersion` |
| Build script | `scripts/build_installer.py` |
| Gate | `scripts/ci.sh` |
| CHANGELOG | `CHANGELOG.md` — move `[Unreleased]` to `[0.9.2]` |
| Minor-1 fix | `src/kimcad/pipeline.py:202` — `MODEL_UNAVAILABLE_MESSAGE` |
| Minor-2 fix | `src/kimcad/ollama_runtime.py:_child_env()` — `OLLAMA_MODELS` |
| Tester branch | `origin/tester` — push `SIGN-OFF-007b` after 0.9.2 is confirmed |

## What is confirmed working (do not re-litigate)
- The gate at `9ddea46` is clean: 1679 pytest / 405 vitest / build-repro green
- directive-007 confirmed the cold-start headline works on a genuine clean machine
- ENG-GG-001 (engine teardown), QA-GG-002 (8mm cable), no Snapmaker — all confirmed by tester
- The only open question is whether the PUBLISHED BINARY has the 2 Minor fixes in it — it doesn't yet

## Open items beyond this patch
- **#11** — real-printer send (hardware; out of scope for software gate)
- System-Ollama reuse live test (needs a box with pre-installed Ollama + qwen2.5:7b)
- Native FS sandbox / ENG-004 partial (AppContainer / firewall; admin-level OS work)

---

## Resumption prompt

> Resume KimCad work. Handoff at `kimcadclaude/docs/handoffs/kimcad-0.9.2-handoff-2026-06-17.md`. Memory at `~/.claude/projects/C--Users-scott-Desktop-Code/memory/`. 
>
> Short version: directive-007 tester confirmed v0.9.1 SHIPS (0 Blockers/Criticals/Majors). Two Minors were fixed in source (commit `9ddea46`, gate green) but the installer was NOT rebuilt — the published `v0.9.1` binary still has both Minors. Scott caught this and called it out as a rationalization of the 0/0/0/0/0 rule.
>
> Next action: bump to `0.9.2`, rebuild the installer, run the gate, push, publish as pre-release, DEV-verify the 2 specific Minor findings are gone in the binary, push SIGN-OFF-007b to `origin/tester`. The handoff has step-by-step instructions.
