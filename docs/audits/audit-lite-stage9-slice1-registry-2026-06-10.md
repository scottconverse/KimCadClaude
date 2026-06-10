# Audit Lite — Stage 9 Slice 1 (sequenced last): DesignRegistry extraction (ENG-004)
**Date:** 2026-06-10
**Scope:** New `src/kimcad/design_registry.py` — one class owns the per-design state (9 registries/caches + the lock + both counters + the web-root lifecycle) and the three load-bearing protocols as methods: `evict_locked` (lockstep eviction incl. disk), `enforce_caps_locked` (LRU cap with full eviction), and the geometry-version guard (`bump_version_locked` / `register_gcode_locked` / `cache_slice_locked`). webapp's closure binds local names to the object's fields (the documented Stage-10 flattening seam) and the ~8 protocol call sites became method calls; the duplicated bump/invalidate and cap-loop logic is gone from the handlers.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. The audit's actual ask — "the invariants live as structure, not comments" — is met: forgetting a registry in eviction, skipping the cap's disk cleanup, or registering a stale slice is now impossible without editing the one class that owns the rule. Deliberately bounded: read-site names stay (same underlying objects), full flattening + the router split scheduled for Stage-10-start where the new handlers land. The regression net (125 webapp route tests, incl. the threading-Event race tests for the slice/render locks) passes unchanged, plus 5 new direct protocol tests.

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**

## Adversarial checks performed
- **Shadowing hazard:** the original declarations below the new block would have silently shadowed the aliases — caught and removed during the edit; ruff + the suite confirm no duplicate bindings remain.
- **Test-patchability preserved:** `test_webapp` monkeypatches `webapp.MAX_REGISTRY`; the cap methods take the cap as a parameter read from webapp's module global at call time — the eviction test passes unmodified.
- **Semantics-preserving proof:** `bump_version_locked` folds the handler's three-step invalidation (bump + gcode pop + cache sweep) into one method — the new `test_bump_drops_old_gcode_and_cached_slices` pins exactly that union; the race-window behavior (stale slice dropped at register time) is pinned both directions in `test_version_guard_drops_a_stale_slice_and_gcode`.
- **Locking contract:** `_locked` suffix marks the methods requiring the caller's transaction; `new_rid`/`try`-free methods take the lock themselves — the existing `with lock:` transactions in handlers are byte-identical in scope.
- **Init parity:** stale-dir cleanup moved into the constructor; `test_init_clears_stale_numeric_dirs_only` pins numeric-only deletion (assets untouched).

## Tests
5 new direct protocol tests; **923 pytest** (full, incl. live) · 125 webapp route tests unchanged · ruff clean.

## Escalation recommendation
No escalation. Stage 9 is feature-complete → proceed to the stage gate.
