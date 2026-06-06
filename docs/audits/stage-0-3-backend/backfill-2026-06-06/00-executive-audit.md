# Backend foundation (shipped stages 0–3) — backfill audit, executive summary
**Date:** 2026-06-06 · **Scope:** the CURRENT `main` code of the backend stages — Stage 0 (the
deterministic pipeline: ir, openscad_runner, validation, printability gate, orientation, hardening,
pipeline, benchmark, cli), Stage 1 (gated export: slicer, prove_gcode_3mf, gate-is-authority),
Stage 2 (send-to-printer: printer_connector, connectors, octoprint), Stage 3 (printer coverage:
config profiles, moonraker/prusalink, ready/not-ready). Audited statically + at the live CLI/API.

## Method (real skills, independent agents)
These backend stages are tightly coupled (pipeline → gate → slice → connector), so one `audit-team`
ran across stages 0–3 with findings TAGGED per stage. Four role agents: engineering, test, QA
(runtime via the real CLI), docs. The UI/UX role was skipped — these stages have no UI surface
beyond what the Stage 4–7 backfills already covered (justified, noted). Round 2: an independent
re-audit with false-green checks.

## Round-1 severity rollup (deduped, by stage)
Blocker 0 · Critical 0 · **Major ~5** · Minor ~9 · Nit ~6. The backend is genuinely strong and
safety-conscious: the load-bearing invariants — gate-failed-never-sliced/sent, explicit-confirm
send, proven-motion-G-code gate, no cross-vendor profile mis-slice — all hold fail-closed across
CLI/web/MCP (verified by direct attack at the real CLI).

## The standout find — a real safety bug (fixed + verified)
- **ENG-001 (Major, stage 0):** a degenerate render with a **NaN/inf bounding-box extent silently
  PASSED** the dimension + build-volume gates — IEEE NaN compares False against every tolerance, so
  an unmeasurable part read as printable and could be sliced. Fixed: `validate_mesh` records a
  non-finite-bbox error, and the gate now runs a `_check_finite_extents` FAIL **first**, so a
  non-finite size fails closed. Regression test confirmed a real guard (the gate PASSES on a
  matching NaN plan if the check is removed).

## Other Majors (fixed)
- **QA-301 (stage 1/3):** a bad `--printer`/`--material`/backend/connector name dumped a raw
  `KeyError` traceback. Now a friendly `UnknownConfigKey(RuntimeError)` ("Available: …") — the CLI
  prints it cleanly and the web slice handler returns 400 (not 500).
- **DOC-001 (stage 0):** the ROADMAP "Current baseline" was frozen "as of Stage 4" with stale test
  counts; refreshed to Stage 8.5, counts de-pinned (CHANGELOG is the record).
- **DOC-002 (stage 3):** the CLI `--send` help advertised moonraker/prusalink as ready though they
  ship commented-out; reworded to the shipped-active connectors.
- **TEST-001/002 (coverage):** the ±0.5 mm dimension-tolerance boundary now has an edge test
  (50.4 PASS / 50.6 FAIL); the gate-failed-not-sent refusal is confirmed covered by the existing CLI
  test (`ensure_sendable` is correctly shape-gate-only — the printability refusal is enforced
  upstream).

## Minors / Nits (fixed)
- **ENG-002:** prove_gcode_3mf now caps the total zip entry count before filtering (a crafted
  high-entry archive can't pin a core just being enumerated). **ENG-004:** the no-stable-pose
  orientation fallback reports 0.0 stability, not a misleading max-confidence 1.0. **ENG-005:**
  `slice_model`'s default timeout aligned to the production 600 s. **QA-303:** the readiness card no
  longer recommends "Slice for <material>" when that material has no profile on the chosen printer.
- **DOC-004/006:** README notes that the Bambu reference printers have no native send connector yet
  (Stage 10) and that the build-volume envelopes are the nominal sizes pending physical confirmation.
  **DOC-003/008:** CHANGELOG forward-references the Stage-3 removal of the generic profile fallback;
  the CLI docstring no longer says "Phase-1". **TEST-003/004:** breadth across all shipped
  printers/materials + a direct `wall.ok` PASS assertion.

## Accepted / deferred (with rationale — re-audit confirmed none is a hidden defect)
- **QA-302** (loopback mock reports "printing" for a queued job — cosmetic, mock-only, real
  connectors report real state). **QA-304** (the raw OS error is only in the developer/log message;
  the user-facing `user_message` is already clean — the OS detail aids debugging). **QA-305**
  (`--proceed-anyway` exits 0 — intentional: the user asked to slice-for-inspection anyway).
  **ENG-003** (a sanitize string-literal heuristic edge — the load-bearing `BlockedCodeError`
  security guard banning minkowski/file-I/O/`use`/`include` is intact, and the codegen path is
  off-by-default). **DOC-005/007/009** (inter-doc cross-reference nits — the user-facing docs are
  accurate).
- **ENG-006 → Scott (hardware):** the configured build-volume envelopes for the Bambu P2S/A1 carry
  `VERIFY` markers — confirming the *physical* envelope needs the actual printers (a Scott/hardware
  item). Mitigation already in place: the Stage 5 slicer-footprint cap bounds the on-screen design
  to the verified *sliceable* area, and DOC-006 now states the envelopes are nominal-pending-confirm.

## Round-2 re-audit
CLEAN — all actioned findings verified; false-green checks pass (ENG-001 + QA-301 fail if reverted);
the safety invariants re-confirmed; 783 pytest pass.

## Note on the historical Stage-0 package
The earlier `audit-stage0-2026-05-29/` (the pre-merge Stage-0 audit) was migrated from the repo root
into `docs/audits/stage-0/` for tidiness; this backfill supersedes it against the current code.

## Final verdict
**BACKEND STAGES 0–3 BACKFILL: CLEAN — 0/0/0/0/0 (engineering/test/docs/QA) + the safety invariants
verified.** Gate green: ruff, geometry backends, 783 pytest (not-live), 284 vitest, SPA build
reproducible. Live OrcaSlicer slice runs on push. (One hardware-only item, ENG-006, is surfaced to
Scott.)
