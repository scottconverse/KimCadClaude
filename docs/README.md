# KimCad `docs/` index

A map of what's current vs. historical, so the user-facing doc surface stays clean.

## Current (read these)
- **`USER-MANUAL.md`** — the complete guide in three tiers (everyday use · the technical/CLI surface · architecture). **The single best starting point.**
- **`install-guide.md`** — the double-click Windows installer: SmartScreen, checksums, what goes where, first run.
- **`supported-printers.md`** — the printer/connection matrix, API-validated vs metal-validated kept honest.
- **`beta/first-hardware-contact.md`** — the scripted checklist for the first real-printer session (at Kim's).
- **`getting-started-windows.md`** — the FROM-SOURCE setup walkthrough (developers / code-checkout users).
- **`troubleshooting.md`** — symptom → cause → fix for every known setup/runtime snag.
- **`design/`** — the controlling UI/UX design + the v3.0 product spec (`design/KimCad-Unified-Product-Spec-v3.0.md`). Build to this.
- **`guide-my-designs.md`** — user-facing guide for the "My Designs" library.
- **`guide-sliders-and-units.md`** — user-facing guide for the live parameter sliders + mm/inch units.
- **`guide-photo-onramp.md`** — user-facing guide for starting a design from a photo or a dimensioned sketch (and the local-only promise).
- **`guide-settings-and-cloud.md`** — user-facing guide for Settings, incl. exactly what the cloud opt-in sends and where the key is stored.
- **`printproof3d-integration.md`** — how the PrintProof3D validation engine plugs in (arm's-length; bundled at Stage 11).
- **`cadquery-backend.md`** — the optional CadQuery parallel geometry backend (Stage 8): setup, the worker sandbox, STEP export.
- **`benchmarks/`** — model + template benchmark notes (how to re-run them).
- **`audits/`** — the audit trail: per-slice `audit-lite`, per-stage `audit-team` + `wiring-audit` packages, and `RUN-LEDGER-2026-06-05.md` (the live finish-the-product tracker).

Project-level current docs live at the repo root: `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`,
`CHANGELOG.md`, `HANDOFF.md` (start at HANDOFF's "RESUME HERE" box).

## Historical (kept for provenance — NOT current instructions)
Completed-stage directive / handoff snapshots are retained for the record but are superseded by the
docs above. Treat them as history, not as build instructions, e.g.:
- `stage-5-completion-directive-2026-06-02.md`, `design/stage-8.5-slice-5-onramps.md`,
  `stage-8.5-usability-plan.md` (Stage 8.5 shipped and is tagged; note its "gemma vision" lines
  were superseded at Stage 9 — see `benchmarks/stage-9-vision-onramps.md`), and any other
  `stage-*-directive` / `stage-*-completion` / dated slice-directive files.

If you're resuming work, the source of truth is: HANDOFF.md (resume box) + `audits/RUN-LEDGER-2026-06-05.md`
+ `ROADMAP.md` + the v3.0 spec — not the historical directives.
