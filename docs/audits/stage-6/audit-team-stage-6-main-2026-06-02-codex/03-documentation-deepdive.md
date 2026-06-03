# Documentation Deep-Dive - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Role:** Technical Writer  
**Scope audited:** `HANDOFF.md`, `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `config/default.yaml`, `docs/benchmarks/stage-6-model-bakeoff.md`, prior Stage 6 audit/remediation docs.  
**Writer mode:** audit-only  
**Auditor posture:** Balanced

## TL;DR

Most Stage 6 docs now tell the correct story: qwen was tested, qwen lost, gemma stays, Stage 7 is next. The first handoff banner still contains a stale resume instruction from before merge/tag, and because `HANDOFF.md` is explicitly the read-first control surface, that is a Major doc defect. Fixing it is small and local.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Benchmark doc is now honest** - `docs/benchmarks/stage-6-model-bakeoff.md` leads with qwen rejected and gemma kept.
- **Roadmap is current** - `ROADMAP.md` marks Stage 6 done and Stage 7 next.
- **Config comment is honest** - `local_qwen` is described as evaluated and rejected, retained as selectable.
- **README covers new user-facing Stage 6 commands** - It documents `kimcad models` and `kimcad bakeoff`.

## What couldn't be assessed

All in-scope docs were accessible.

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md | Yes | Strong | None |
| ARCHITECTURE.md | Yes | Adequate | None |
| ROADMAP.md | Yes | Strong | None |
| HANDOFF.md | Yes | Weak first banner | DOC-001 |
| CHANGELOG.md | Yes | Adequate | None |
| Benchmark doc | Yes | Strong | None |
| Config comments | Yes | Adequate | None |

## Findings

### DOC-001 - Major - Accuracy - `HANDOFF.md` still tells a resumed agent to start at the completed Stage 6 gate

**Evidence**

- `HANDOFF.md:5-11` says Stage 6 is done, merged to `main`, tagged `stage-6`, remediated to 0/0/0/0/0, and next is Stage 7.
- `HANDOFF.md:18-19` then says: `RESUME HERE = the Stage 6 stage-end audit-team gate` and continues with "fix to 0/0/0/0/0 -> merge + tag `stage-6`."
- `HANDOFF.md:77-81` again says the Stage 6 gate is done, remediation passed, and the branch was merged/tagged.

**Why this matters**

`HANDOFF.md` is the source-of-truth handoff and first read for future sessions. A resumed agent following line 18 could re-run or plan work that the same document says is already complete.

**Blast radius**

- Other docs that repeat the same error: none found in `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `config/default.yaml`, or the Stage 6 bake-off doc.
- User-facing: process/handoff only, not runtime product behavior.
- Related findings: none.

**Fix path**

Edit the Stage 6 top banner to remove the stale `RESUME HERE` gate instruction and stale 588/36 counts. Replace it with a single current sentence: Stage 6 is complete/merged/tagged; resume at Stage 7 Smart Mesh + PrintProof3D. Re-run `audit-lite` on the doc-only fix.

## Drafts produced

Writer mode is audit-only; no drafts produced.

## Appendix: docs reviewed

- `HANDOFF.md`
- `README.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `ARCHITECTURE.md`
- `config/default.yaml`
- `docs/benchmarks/stage-6-model-bakeoff.md`
- `docs/audits/stage-6/audit-team-stage-6-2026-06-02/00-executive-audit.md`
- `docs/audits/stage-6/audit-team-stage-6-2026-06-02/REMEDIATION.md`

