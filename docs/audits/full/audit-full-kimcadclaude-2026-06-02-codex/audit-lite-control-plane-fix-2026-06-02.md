# Audit Lite — Control-plane docs fix (closes the Codex audit-full findings)
**Date:** 2026-06-02
**Scope:** The docs/CI fix that closes DOC-001 / DOC-002 / TEST-001 from the independent Codex `audit-full` (`docs/audits/full/audit-full-kimcadclaude-2026-06-02-codex/`). Files: `docs/design/KimCad-Unified-Product-Spec-v3.0.md`, `HANDOFF.md`, `README.md`, `.github/workflows/ci.yml`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after one Nit. All three Codex findings are closed: the v3.0 spec now carries an unmissable control-plane banner + per-section SUPERSEDED markers (no more missing-file chase, no stale Qwen default, no stale Stage-7-as-rebaseline), the HANDOFF resume bullet no longer contradicts itself, and the README/`ci.yml` now honestly describe hosted CI as a partial, non-authoritative smoke check. Only docs + `ci.yml` changed — no runtime code, exactly as the Codex audit directed. The one residual: `scripts/ci.sh`'s own header comment still claims it "runs the same checks GitHub Actions would," which is the very TEST-001 drift in a sibling file.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 1

## Findings

### CP-001 Nit: `scripts/ci.sh` header comment still says it runs "the same checks GitHub Actions would"
**Dimension:** Docs
**Evidence:** `scripts/ci.sh:2` — `# Local CI gate — runs the same checks GitHub Actions would, on this machine.` After the TEST-001 fix, hosted CI (`ci.yml`) is deliberately Python-only, so `ci.sh` runs *more* (vitest, build-reproducibility, live-slicer proof) — the comment now asserts the same equivalence TEST-001 just corrected, in the file the Codex audit named in TEST-001's blast radius (`scripts/ci.sh`).
**Why it matters:** Low blast (an internal shell comment), but it's the last instance of the "local == hosted" claim the fix set out to kill; leaving it re-introduces the drift for anyone reading the script.
**Fix path:** Reword to e.g. `# Local CI gate (the authoritative pre-push gate) — supersets hosted CI (.github/workflows/ci.yml), which is Python-only.`

## What's working
- **DOC-001 closed — the control plane is now unambiguous.** The `⚠ CONTROL-PLANE STATUS` banner (`KimCad-Unified-Product-Spec-v3.0.md:14-18`) sits immediately under the "Canonical package" note and states the three reconciliations plainly: (1) this spec is the sole controlling doc and the four referenced companion files are not in the repo, (2) the model decision is settled (`gemma4:e4b`, Qwen rejected 0/10), (3) the repo's tagged stage numbering is authoritative and NEXT = Stage 7 Smart Mesh. Per-section `⚠ SUPERSEDED` markers at the §7, §9, and §14 headers (`:264`, `:`§9, `:`§14) catch a reader who jumps to a section rather than reading top-down — so the still-present original lines (`§7.1` "Default: Qwen2.5-Coder 1.5B", `§9` stage bullets, `§14` decided list) are each fronted by an override. Preserving Scott's authored text under explicit supersede markers (rather than deleting it) is the right call for a controlling spec — it keeps the decision history while making current truth unmissable.
- **DOC-002 closed — the HANDOFF bullet is internally consistent.** `HANDOFF.md:5-12` now reads "STAGE 6 IS DONE … RESUME HERE = Stage 7 … Stage 6 is complete — do NOT re-run its gate." The orphaned tail ("RESUME HERE = the Stage 6 stage-end audit-team gate … 588 pytest + 36 vitest") is gone. No remaining "resume at the Stage 6 gate" instruction and no stale counts in the live banner.
- **TEST-001 closed — honest CI provenance.** `README.md:253-263` now names the local Windows pre-push hook as the authoritative gate (ruff, full pytest incl. live OrcaSlicer, vitest, build-reproducibility, release-mode live-tool proof) and calls hosted CI a deliberately partial, currently-disabled smoke check that is "not authoritative." `ci.yml:3-9`'s header comment matches. Verified accurate against `scripts/ci.sh` (it does run all five things the README lists) and against the standing fact that hosted CI is disabled for Actions-minutes reasons.
- **Correctly scoped — no runtime code touched.** `git status` shows only `.github/workflows/ci.yml`, `HANDOFF.md`, `README.md`, and the v3.0 spec changed; `git diff --name-only HEAD -- src tests frontend/src` is empty. This honors the Codex audit's "do not change runtime code while rebaselining the control plane."
- **No new contradictions.** The banner agrees with `ROADMAP.md` (Stage 6 done, gemma stays, Stage 7 = Smart Mesh), `HANDOFF.md`, and `CHANGELOG.md` (Stages 1–6 tagged). A grep of the live control-plane docs found no missed companion-file or "Qwen default" references; the only `588/36` strings left are inside the frozen Stage-6 audit records, which correctly capture the count at that audit's time.

## Watch items
- **Deep-anchor jumps in the spec.** The banner + section-header markers cover top-down and section-level reads. A reader who follows a deep link straight to `§7.1`/`§14`'s decided list (past the header marker) could still read the original Qwen line without the adjacent override. Low risk (anchors usually land on headers), but if the spec ever gets per-subsection anchors, consider a one-line inline strike on the literal "Default: Qwen2.5-Coder 1.5B" sentence itself.
- **Stage-numbering scheme (Codex next-sprint watchlist).** The banner declares the repo's tag numbering authoritative and treats §9 as the work backlog. That resolves the immediate drift, but the deeper "spec numbering vs repo-tag numbering" decision is Scott's to ratify before Stage 7 planning — surfaced, not closed.

## Escalation recommendation
No escalation needed. This was a tightly-scoped docs/control-plane pass closing an independent audit's 3 findings; it introduced one Nit and no contradictions. Fix CP-001 and this closes at 0/0/0/0/0.

---

## Re-audit (resolution) — 0/0/0/0/0

- **CP-001 (Nit) — FIXED.** `scripts/ci.sh:2` header rewritten: it now states the local gate is the AUTHORITATIVE pre-push gate and a SUPERSET of hosted CI (which is an intentionally partial Python-only smoke check), instead of "runs the same checks GitHub Actions would." This removes the last "local == hosted" claim across the repo, consistent with the TEST-001 fix.

**Roll-up: 0/0/0/0/0.** The three Codex audit-full findings (DOC-001 Critical, DOC-002 Major, TEST-001 Major) are closed: the v3.0 spec control-plane is unambiguous (banner + section markers; companion files marked absent; gemma settled; repo stage numbering authoritative; Stage 7 = Smart Mesh), the HANDOFF resume bullet is internally consistent, and README/`ci.yml`/`ci.sh` honestly describe hosted CI as partial and non-authoritative. Only docs + CI scripts changed — no runtime code.
