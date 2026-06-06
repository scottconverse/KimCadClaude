# Stage 8 (CadQuery parallel backend) — Executive Audit

**Date:** 2026-06-06 · **Branch:** `stage-8-cadquery` · **Posture:** balanced · **Writer mode:** audit-only
**Roles run:** Principal Engineer · Senior UI/UX · Technical Writer · Test Engineer · QA Engineer (all 5).

## Executive summary

Stage 8 adds CadQuery as an optional, gracefully-absent **parallel geometry backend** to OpenSCAD —
a mutual fallback that lifts the prompt pass rate, plus editable **STEP** export. Its highest-stakes
surface, executing untrusted LLM-generated Python out-of-process, is **well-engineered and honestly
documented**: all five roles independently attempted to break the sandbox and the production path
held (the `ast` sanitizer closes the dunder/introspection/`__globals__` escape class; the worker's
geometry-only facade + restricted builtins are a real second net). **No Blockers, no Criticals.**
The 7 Majors are hardening + signaling gaps, not defects in the core: worker env/cwd isolation, a
release-gate backstop so the sandbox tests can't silently skip, engine-provenance in the UI, and a
documentation precision nuance — all cheap and additive. Every finding has been remediated (or
accepted with rationale); see `REMEDIATION.md`.

## Severity roll-up (across all roles, as found)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 7 |
| Minor | 16 |
| Nit | 11 |

Per-role: Engineering 0/0/2/4/3 · UI/UX 0/0/2/3/2 · Docs 0/0/1/3/3 · Test 0/0/2/4/2 · QA 0/0/0/2/1.

## Top findings (by leverage)

1. **ENG-001 / QA-001 / QA-002 (Major/Minor, Security)** — the sandbox rests on the AST sanitizer
   with no OS-level backstop; a single-token regression could re-open RCE. *Fixed:* env/cwd
   isolation + a through-`render_cadquery` escape-class canary + a release-gate backstop; full OS
   confinement deferred to Stage 11 with rationale.
2. **ENG-002 (Major, Security)** — the worker inherited the full parent env (API keys) and ran
   in-tree. *Fixed:* secret-scrubbed env + isolated cwd.
3. **TEST-001 (Major, CI)** — the worker-sandbox RCE tests are live-only with no release backstop
   (skip to green on an interpreter-less gate). *Fixed:* `KIMCAD_RELEASE=1` hard-fails when no
   CadQuery interpreter is present.
4. **TEST-002 (Major, Coverage)** — worker timeout/crash/non-`open` builtins untested. *Fixed.*
5. **UX-001 (Major, Journey)** — a maker couldn't tell which engine built their part. *Fixed:* an
   "Engine: …" provenance chip on the Printability card.
6. **UX-002 (Major, Copy)** — the STEP teaser was a dead end. *Fixed:* states the engine is
   auto-chosen per part; points at the provenance chip.
7. **DOC-001 (Major, Security precision)** — the worker `__import__` doc understated its rejection
   of non-cadquery/math imports. *Fixed* in all four locations.

## What's working (credited, specific)

- The two-layer sandbox is genuinely robust and **honestly documented** — the docs state what each
  layer cannot do (the `__globals__` class is closed by the sanitizer, not the worker) and that OS
  confinement is not yet implemented. The cleanest doc set the writer lane has audited on this project.
- The mutual fallback **never downgrades** a passing OpenSCAD result and adds zero branching to the
  deterministic spine (the orient/harden/gate tail is backend-agnostic).
- Tests are **tripwires, not tautologies** — mutation runs confirmed each sanitizer guard's test
  fails when weakened, and removing the facade's submodule-strip produced real RCE caught by a test.
- Graceful absence is first-class and tested; the config probe is thread-safe + cached.
- The export copy (the "as-designed, not print-oriented" STEP caveat) is model UX writing.

## Disposition

All findings remediated or accepted-with-rationale this pass (`REMEDIATION.md`), then independently
re-audited (`REAUDIT.md`). The full deep-dives are `01-engineering` … `05-qa-deepdive.md`.

## Next-sprint watchlist

- **OS-level worker confinement (Stage 11):** the durable second wall (network-off + restricted
  token/job object) lands with the installer/bundling work.
- **Live union-lift measurement:** quantify the dual-backend pass-rate lift on the current model
  (documented procedure in `docs/benchmarks/stage-8-cadquery-backend.md`).
- **Saved-design engine provenance:** the My Designs library doesn't yet carry `backend`; a small
  follow-up if engine should show there too.
