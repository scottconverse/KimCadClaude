# Audit Lite — Stage 7 Slice 6: docs + config/tooling
**Date:** 2026-06-02
**Scope:** the Stage-7 doc updates (`CHANGELOG.md`, `ROADMAP.md`, `README.md`, `ARCHITECTURE.md`), the `config/default.yaml` `paths.history` comment block, and the new `docs/printproof3d-integration.md`. Docs accuracy/honesty/consistency is the weighted dimension.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one Nit. The docs clear the load-bearing bar: **nothing claims Stage 7 is done, merged, or tagged** — every surface says "implemented on `stage-7-smart-mesh`, pending the stage-end audit-team gate," CHANGELOG keeps it under `[Unreleased]`, and the only "merged/tagged" mention is the correct "not yet merged or tagged" line. The technical claims match the audited code (arm's-length engine, never-raises, gate-stays-slice-authority, factual comparison), the two pipeline diagrams agree on where readiness sits, cross-references resolve, and the config block is fully commented (no accidental override). The single Nit is a README sentence that implies the "compared to your past parts" line is always shown when it's actually conditional on prior history.

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)".

**As found:** 0 Blocker · 0 Critical · 0 Major · 0 Minor · 1 Nit.

## Findings

### SLICE6-001 Nit: the README implies the history comparison line always appears
**Dimension:** Docs (honesty/precision)
**Evidence:** `README.md` — "Every built part gets a **Smart Mesh readiness** report card — … synthesized from the Printability Gate plus, when it's configured, the optional … PrintProof3D … engine, and an honest 'compared to your past parts' line from a local-first history." The "when it's configured" qualifier scopes PrintProof3D but not the comparison line, which a reader can take as always-present. In fact the line only appears once there *is* prior history (and never in the `--demo` server, which is intentionally history-less), per `history.py` (`compare_phrase` returns `None` with no priors) and the Slice-5 wiring.
**Why it matters:** Minor precision, but the owner holds a strict no-overclaim bar, and a first-ever part shows no comparison — so "every built part gets … a comparison line" slightly overstates.
**Fix path:** Add a short qualifier, e.g. "…and, once you've made a few parts, an honest 'compared to your past parts' line from a local-first history." One clause; no structural change.

## What's working
- **The Stage-4 doc-honesty lesson is fully applied.** Grep across all five docs for Stage-7 "tagged / merged / done" returns only the *correct* "not yet merged or tagged" line. CHANGELOG keeps Stage 7 under `[Unreleased]` with an explicit "pending its stage-end audit-team gate" note; ROADMAP's Stage 7 section, baseline line, and "still ahead" line all say implemented-on-branch/pending-gate; README carries the "(Stage 7 — implemented on the `stage-7-smart-mesh` branch, pending its stage gate)" caveat. No status overclaim anywhere.
- **Claims match the audited code.** Spot-checked against source: the verdict tone is the worst of KimCad's read and the engine's status (`smart_mesh.assess_readiness`); `validate_model` is an arm's-length subprocess that never raises and is gated on the parsed report, not the exit code (`printproof3d.py`); readiness rides on the report for both completed and gate-failed paths and bed-positions a copy, with the gate unchanged/advisory (`pipeline.py`); the card's badge reframe and honest attribution (`RightPanel.tsx`); the local-first, coarse, factual history (`history.py`). The integration doc's CLI (`validate-model --model/--printer/--material/-o`), report schema, `cargo build --release`, degrade-never-raises, and "advisory; gate is the slice authority; folding engine fails into the slice gate is a follow-up" all match — and it correctly does **not** claim the engine blocks slicing today.
- **Internally consistent.** Both pipeline diagrams (README, ARCHITECTURE) place "Smart Mesh readiness" in the same spot — after harden, before confirm/slice. Config key names (`binaries.printproof3d`, `paths.history`) match exactly what `config.py` reads.
- **Config is accurate and inert.** The `paths.history` block is fully commented (verified — no active `paths:` key, so the home-dir default is untouched), and the prose is correct: default `~/.kimcad/history.json`, absolute override used as-is, relative resolves against the project root with **no `~` expansion of a config value** — which matches `Config.history_path` (`Path(raw)`; only the unset default uses `Path.home()`).
- **No broken cross-references.** The referenced `docs/benchmarks/stage-5-template-families.md` and the design screen `docs/design/screens/10-smartmesh-report.png` both exist; the per-slice audit reports they point at are present in `docs/audits/stage-7/`.

## Escalation recommendation
No escalation needed. A clean, honest docs slice with one wording Nit. Fix it and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team (Technical Writer role) will re-confirm the whole doc set.

---

## Re-audit (resolution) — 0/0/0/0/0

- **SLICE6-001 (Nit) — FIXED.** The README sentence now qualifies the comparison line as conditional ("…and, once you've designed a few parts, an honest 'compared to your past parts' line…"), so it no longer implies an always-present line. No other doc made the unqualified claim.

Verified: grep confirms no Stage-7 "tagged/merged/done" overclaim remains; the qualifier is in place. **Roll-up: 0/0/0/0/0.**
