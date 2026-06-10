# Audit-Lite — Stage 10 Slice 10.1: DesignRegistry alias-seam flattening

**Date:** 2026-06-10
**Scope:** Uncommitted working-tree changes on top of `253b08c` — `src/kimcad/webapp.py` (alias block deleted, all aliased reads/writes flattened to `reg.<field>` / `with reg.lock:`) and `src/kimcad/design_registry.py` (docstring seam note updated). One gitignored plan doc (`.claude/plans/stage-10-direct-print.md`) skimmed for sanity only.
**Claim under test:** BEHAVIOR-PRESERVING ONLY; 133 route+registry tests unchanged-green; ruff clean.

## TL;DR

The flattening is clean and genuinely behavior-preserving. Every changed line in the diff is exactly one of: (a) an alias→`reg.<field>` substitution, (b) `with lock:`→`with reg.lock:`, or (c) the two documented comment/docstring updates. No substitutions landed inside string literals, f-strings, dict keys, or log messages; no bare alias name or bare `lock` survives anywhere in `webapp.py` (only prose comments use the words "registry"/"lock" generically). Lock discipline is unchanged — every block that held `lock` (which WAS `reg.lock`) now holds `reg.lock` literally; the `slice_lock`/`render_lock`/`progress_lock` server-level locks were correctly left alone. No nested function or error path can NameError on a deleted name — a full-file scan found zero remaining references, not just zero in tested paths. Verified independently: **133 passed** (57.4s) and **ruff: All checks passed**. Three Nit-level comment-drift findings (stale references to the now-deleted names in a webapp comment, a test comment, and HANDOFF.md); zero functional findings.

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---------|----------|-------|-------|-----|
| 0 | 0 | 0 | 0 | 3 |

## Findings

### DOC-001 — Nit — Comment still names the deleted `lock` local — `src/kimcad/webapp.py:2003`

The re-render handler's cache-buster comment reads:

```
# mesh. Taken under `lock` for consistency with the other counter reads
```

`lock` no longer exists as a name in this file; the code (correctly) runs inside `with reg.lock:`. A future reader grepping for `lock` to understand the guarantee finds a phantom. The companion docstring in `design_registry.py:78` (`next_mesh_version`) was already updated to say "inside a ``with reg.lock:`` transaction", so this is the one spot the comment pass missed.

**Fix path:** change `` `lock` `` to `` `reg.lock` `` in the comment. One word.

### DOC-002 — Nit — TEST-003 comment describes the transitional aliases in present tense — `tests/test_webapp.py:1198-1200`

```
# TEST-003 (stage-9 gate): pin the lockstep eviction THROUGH the routes, so a
# silent rebinding of any transitional alias (step_registry, design_snapshot,
# rid_saved_id, …) fails a route test instead of leaking state quietly.
```

The aliases this test was built to pin no longer exist — the threat it names ("silent rebinding of a transitional alias") is now impossible by construction. The test itself remains valuable (it pins DesignRegistry's lockstep eviction through the routes) and MUST stay; only its stated rationale is stale. Out-of-diff file, so this is drift the slice exposed rather than introduced — but the slice's own plan named the "TEST-003 alias pins" as the regression net, so the comment is now the last live description of the seam as a current thing.

**Fix path:** reword to past tense, e.g. "…so a regression in DesignRegistry's lockstep eviction (which the Stage-9 transitional aliases originally motivated, flattened in Slice 10.1) fails a route test instead of leaking state quietly." No test logic change.

### DOC-003 — Nit — HANDOFF.md cites `gate_status_by_rid` as a live name in webapp.py — `HANDOFF.md:381`

```
server-side (`gate_status_by_rid` in `webapp.py`), mirroring the CLI.
```

The identifier is gone; the mechanism lives on as `DesignRegistry.gate_status` (`reg.gate_status` at the call sites, `src/kimcad/design_registry.py:55`). HANDOFF.md is a living handoff doc, not a historical audit record, so the dangling identifier will mislead the next grep. (Historical audit reports under `docs/audits/**` also mention the old names; those are records of their moment and were correctly left untouched.)

**Fix path:** change to `` (`reg.gate_status` — `DesignRegistry.gate_status` — in `webapp.py`) ``.

## What's working

- **The flattening is complete.** A whole-file scan of `webapp.py` for any non-attribute occurrence of `registry`, `gcode_registry`, `step_registry`, `gate_status_by_rid`, `slice_cache`, `template_state`, `design_snapshot`, `rid_saved_id`, or bare `lock` finds only generic prose in comments (lines 48, 694, 702, 913, 999, 1313, 1575, 1847, 2003) — zero code references. No NameError path survives anywhere, including the untested/error handlers; nothing depends on the deleted names via closure capture.
- **No scripted-rewrite collateral.** Every diff hunk was read line by line: 23 substitution sites, all exactly alias→`reg.<field>` or `with lock:`→`with reg.lock:`, plus the two documented comment updates (webapp.py:684-687, design_registry.py:17-18). No string literal, f-string, JSON payload key, dict key, or user-facing message changed — a targeted search for `reg.` inside string literals returns nothing, so observable HTTP output is bit-identical.
- **Lock discipline preserved exactly.** Every block that previously held `lock` (the alias for `reg.lock`) now holds `reg.lock`; the lock-ordering in the slice path (`slice_lock` outer, `reg.lock` inner re-check at webapp.py:1873-1875) is untouched, as are `render_lock` and `progress_lock`. The `_locked`-suffix method contract (`register_gcode_locked`, `cache_slice_locked`, `bump_version_locked`, `version_locked`, `enforce_caps_locked`) is still honored — each call site sits inside `with reg.lock:` as before.
- **Verification reproduced, not taken on faith.** `.venv\Scripts\python.exe -m pytest tests/test_webapp.py tests/test_design_registry.py -q` → **133 passed in 57.42s** (matches the claim; zero test-file changes in the diff, so the net is genuinely unchanged). `.venv\Scripts\python.exe -m ruff check src` → **All checks passed**.
- **Docstring honesty.** `design_registry.py`'s module docstring now states the seam was flattened "at Stage-10-start as scheduled" — accurate, and it closes the loop the Stage-9 audit-team watchlist opened.
- **Plan doc sanity (gitignored, not a finding source):** `.claude/plans/stage-10-direct-print.md` Slice 10.1 matches what was done (behavior-preserving, tests-unchanged net, router split explicitly deferred as "only if it pays" — it wasn't done, which is consistent). Minor naming slip in the plan (`snapshot`/`saved_id` vs the actual alias names `design_snapshot`/`rid_saved_id`) — immaterial.

## Tests dimension

Regression net is the unchanged 133 tests (125 route + 8 direct DesignRegistry protocol tests). That is the right net for a pure-rename slice: TEST-003 pins lockstep eviction through the routes, and the registry protocols are pinned directly. No new tests are owed — there is no new behavior to pin.

## Escalation recommendation

**No escalation.** Zero functional findings; three one-line comment/doc fixes. This is exactly the audit-lite profile — proceed to fix the three Nits (per the 0/0/0/0/0 standard) and move on to Slice 10.2. An audit-team pass belongs at the Stage 10 gate, not here.
