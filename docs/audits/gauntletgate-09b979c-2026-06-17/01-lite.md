# GauntletGate — Lite lane (fast pass on the b4→09b979c delta)

**Project:** KimCad · **Commit:** `09b979c` · **Date:** 2026-06-17 · **Lane:** Lite (feeder inside `/gauntletgate all`)
**Scope:** the change delta from the b4 baseline (`c784a23`) → `09b979c` — the cold-start managed-Ollama onboarding fix + the b4+UI audit-watchlist remediation + the restored UI commits. 84 files, +4954/-576.

## TL;DR
**Ship (within the full gate).** The delta is well-structured, security-conscious, and well-tested; the headline first-run fix is verified live (see the Walkthrough lane). The Lite pass found **no Blocker / no Critical**. This is the warm-up/feeder — the advancement decision rests on Walkthrough + Full.

## Severity roll-up (Lite)
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 (Lite surfaced nothing rising to a formal finding; deeper per-dimension coverage is delegated to the Full lane's 5 roles.)

## Five dimensions (compressed)

**Correctness & Security — strong.**
- `ollama_fetch.py`: pinned version+URL+SHA-256; hash verified **before** any extraction; `_safe_extract` is zip-slip-guarded (`target.resolve().relative_to(dest)`); streams to a temp file, removed on finish; friendly typed errors. Mirrors `design_store`'s import rigor.
- `ollama_runtime.py`: reuse-system-first (`find_system_ollama` = PATH then `LOCALAPPDATA\Programs\Ollama`); headless `ollama serve` (`OLLAMA_HOST` pinned loopback, `CREATE_NO_WINDOW`, deliberately no `OLLAMA_MODELS` so the store is shared); `ensure_serving` is bounded-poll; all effects injected (unit-tested) with a **`real_tool` integration test** for the actual fetch→serve (no-false-greens).
- ENG-COLD-002 fix (`webapp.py:1683`): local-vs-cloud classification now by **loopback host** (`Config._is_local_base_url`), not the `"11434"` substring. Verified live cold (`/api/model-status` honest).
- `cadquery_worker._deny_network()`: neutralizes socket/`_socket` constructors before `exec` of untrusted codegen — defense-in-depth (Full's PE verifies it genuinely denies).
- `webapp.py` single-source route table (`_GET_ONLY_PATHS`/`_POST_ONLY_PATHS`/`_is_get_only`) — kills the GET/POST-only drift hazard.

**First-run — the headline.** Verified live in a true cold state (Walkthrough lane): the dead-end is gone, the one-click "Set up KimCad's AI" wire fires into the real fetch path, console clean.

**UX.** One real action replaces the old install-it-yourself detour; honest "Not set up yet"; cloud behind an "Advanced (optional · local always works)" disclosure. Verified live.

**Docs.** Managed-Ollama reframe applied across README/USER-MANUAL/install-guide/FAQ/troubleshooting/getting-started/index.html + CHANGELOG `[Unreleased]` + installer note. (Full's Technical Writer verifies completeness + any stale "install Ollama yourself" residue + size/version consistency.)

**Tests / Runtime — confirmed green this lane.**
```
ruff check (changed src + tests): All checks passed!
pytest tests/test_ollama_runtime.py test_ollama_fetch.py test_ollama_runtime_real.py
       test_model_pull.py test_cadquery_worker.py test_config.py test_settings_store.py test_shell.py
  → 101 passed in 27.36s   (includes the real_tool ollama-runtime test + the cadquery network-deny subprocess tests)
```

## What's working (credited)
- The **no-false-greens discipline** is baked in: a `real_tool` test exercises the actual portable-engine fetch+serve, not a mock.
- Effect-injection design makes the orchestration fully unit-testable without sacrificing the real-path proof.
- Security rigor on the new network surface: hash-before-extract, zip-slip guard, loopback-only classification, worker network-deny.

## Escalation recommendation
Already escalated — the user invoked `all`; the Walkthrough + Full lanes are running. Lite found no Blocker/Critical and no reason to halt the gate.
