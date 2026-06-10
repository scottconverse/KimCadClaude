# Audit Lite — Stage A Slice 3: non-developer docs (DOC-001 / DOC-004)
**Date:** 2026-06-10
**Scope:** New `docs/getting-started-windows.md` (nothing → first part, for a non-developer) and `docs/troubleshooting.md` (symptom → cause → fix for every known snag); README Setup gains the non-developer pointer and is framed as the developer-shaped path; `docs/README.md` index updated.
**Reviewer:** Claude (audit-lite) — claim-by-claim verification against the code, the audit's standard for this repo's docs.

## TL;DR
Ship. Every executable claim in both docs verifies against the current code: the command sequence matches README/lockfile reality, the default port (8765), the model tag (`gemma4:e4b`), `kimcad models`, `fetch_tools.py` re-run safety + both checksum pins (now true for OpenSCAD too, post-bootstrap), the OrcaSlicer 2.3.2 GPU-less crash rationale, the STL fallback behavior, and the new Slice A1 error messages quoted in the troubleshooting entries ("KimCad couldn't reach your local AI", "isn't installed at", "Port … is already in use") all match the strings the code now emits. One defect found and fixed during this pass (a pandoc-only `{#anchor}` that GitHub would have rendered literally).

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0** (anchor defect fixed pre-commit).

## Claim spot-checks
- Setup sequence = venv → `pip install -r requirements.lock` → `pip install -e ".[dev]"` → `fetch_tools.py` → `ollama pull gemma4:e4b` → `kimcad web` — matches README + lockfile + `cli.py`.
- Troubleshooting entries quote the *actual* Slice A1 message fragments, so a user can find the entry by searching the error they saw.
- The empty-vision entry documents the Ollama-version failure mode previously only in a code comment (`llm_provider.py`) — the DOC-004 root case.
- Internal links resolve: `troubleshooting.md` ↔ `getting-started-windows.md`, `guide-my-designs.md`, `../SECURITY.md` all exist at the stated paths.
- DOC-001's fix-path options: this implements option (b) (interim walkthrough unblocking pre-installer beta) while the README note stays honest that the installer is still coming.

## Escalation recommendation
No escalation — docs-only slice at zero findings.
