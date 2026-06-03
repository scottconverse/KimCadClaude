# Documentation Deep-Dive - KimCadClaude full project

**Audit date:** 2026-06-02  
**Role:** Technical Writer  
**Scope audited:** README, architecture, roadmap, handoff, v3.0 unified spec, design handoff, benchmark docs, config comments, audit artifacts.  
**Writer mode:** audit-only  
**Auditor posture:** Balanced

## TL;DR

The project has unusually rich documentation, but it currently has more than one "source of truth." README/ROADMAP/HANDOFF mostly reflect the Stage 6 artifact, while the controlling v3.0 spec points to missing companion docs and stale model/stage decisions. This is the top project risk because future work is supposed to be directed by those docs.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 1 |
| Major | 1 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **README is strong for current usage** - It explains local-first setup, web UI, slicing, connectors, model advisor, and bake-off.
- **Roadmap is stage-aware** - It correctly says Stage 6 is done and Stage 7 is next.
- **Benchmark docs are useful** - Stage 5 and Stage 6 benchmark docs show concrete numbers and verdicts.
- **Handoff captures process lessons** - The manual audit-lite/audit-full process is documented clearly.

## What couldn't be assessed

All in-scope docs were accessible. The companion docs the v3.0 spec references were not present in the repo.

## Findings

### DOC-001 - Critical - Accuracy / Source of Truth - The controlling v3.0 spec points to missing files and obsolete model/stage truth

**Evidence**

- `docs/design/KimCad-Unified-Product-Spec-v3.0.md:12` says the complete canonical package consists of this spec plus `KimCad-Build-Spec-v3.0.md` and `DECISION-LOG-v3.md` in `docs/spec/`.
- `docs/spec/` does not exist in the repo.
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md:258` says the model decision is a small fast local model plus OpenRouter, and lines 336-339 summarize Qwen2.5-Coder as the decided default.
- Current Stage 6 docs and runtime say the opposite: qwen was rejected 0/10 and `gemma4:e4b` stays default.
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md:285-290` says Stage 7 is a spec rebaseline and Stage 8 contains model swap/template/sliders; `ROADMAP.md` and `HANDOFF.md` say Stages 5 and 6 already completed those, and next is Stage 7 Smart Mesh + PrintProof3D.
- `HANDOFF.md:242` explicitly says to work only with the unified spec and design spec and ignore companion build-spec/decision-log copies, contradicting the unified spec's line 12.

**Why this matters**

The spec is called controlling, and Scott explicitly asked whether it had been read before continuing work. A future agent following it literally would look for missing docs, reopen the settled model decision, and plan Stage 7 around a spec-rebaseline task rather than Smart Mesh.

**Blast radius**

- Adjacent docs: `HANDOFF.md`, `ROADMAP.md`, `README.md`, `docs/design/README.md`, Stage 7 directive/handoff artifacts.
- User-facing: none in the running product today.
- Process-facing: high; this is the root source for future autonomous work.
- Tests to update: none unless doc-consistency checks are added.
- Related findings: DOC-002, TEST-001.

**Fix path**

Make one source-of-truth decision and edit accordingly. Either move/create the referenced companion docs under `docs/spec/`, or remove the companion-package claim and mark this unified spec as the sole controlling document. Update model strategy and stage plan to reflect the actual Stage 6 verdict: `gemma4:e4b` default, qwen rejected, Stage 7 Smart Mesh + PrintProof3D next. Then run `audit-lite` on the doc rebaseline.

### DOC-002 - Major - Accuracy - `HANDOFF.md` still tells a resumed agent to start at the completed Stage 6 gate

**Evidence**

- `HANDOFF.md:5-11` says Stage 6 is done, remediated, merged, tagged, and next is Stage 7.
- `HANDOFF.md:18-19` says `RESUME HERE = the Stage 6 stage-end audit-team gate` and cites stale 588 pytest / 36 vitest counts.
- `HANDOFF.md:77-81` again says the Stage 6 gate and remediation are done and current counts are 609 pytest / 37 vitest.

**Why this matters**

This is the first-read handoff surface. A resumed agent can waste time redoing a completed gate or produce a contradictory directive.

**Blast radius**

- Adjacent docs: only `HANDOFF.md` in the reviewed set.
- User-facing: none.
- Process-facing: medium-high because this file controls resumes.
- Related findings: DOC-001.

**Fix path**

Delete the stale resume sentence and stale counts from the Stage 6 top banner. Replace with a single resume instruction: Stage 6 is complete; resume at Stage 7 Smart Mesh + PrintProof3D.

## Drafts produced

Writer mode is audit-only; no drafts produced.

## Appendix: docs reviewed

- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `HANDOFF.md`
- `CHANGELOG.md`
- `config/default.yaml`
- `docs/design/README.md`
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md`
- `docs/benchmarks/stage-5-template-families.md`
- `docs/benchmarks/stage-6-model-bakeoff.md`
- `docs/audits/stage-4/*`
- `docs/audits/stage-5/*`
- `docs/audits/stage-6/*`

