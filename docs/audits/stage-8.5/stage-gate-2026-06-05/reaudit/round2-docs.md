# Round-2 Documentation Re-verify (Technical Writer) — CLOSURE

**Audit:** KimCad Stage 8.5 (Usability) — stage gate, ROUND-2 focused doc re-verify (post second-tier remediation)
**Branch / commit:** `stage-8.5-usability` @ `a6dff43` ("Stage 8.5 gate: re-audit closures + second-tier remediation")
**Role:** Senior Technical Writer — independent, skeptical. Verify the Round-1 doc residuals (3 partial + 2 new) are genuinely resolved in the CURRENT docs (file:line), confirm no new drift, confirm user-facing + SUPERSEDED banners still accurate.
**Round-1 report under follow-up:** `reaudit/03-documentation-reaudit.md` (rollup 0·0·0·3·0)
**Round-2 doc edits live in:** `a6dff43` (`CHANGELOG.md` +2, `HANDOFF.md` +5, `README.md` +2, `ROADMAP.md` rewrite of the inline slice list).

---

## Verdict at a glance

The second-tier doc remediation is **genuine and complete** for the four items it set out to fix. All three Round-1 partials and the one new internal contradiction are resolved with accurate, verifiable edits; cross-checked against the authoritative plan doc and the tag set. **No new drift was introduced** by the round-2 edits — the README sentence is grammatically intact, the ROADMAP inline list now enumerates exactly 11 numbered slices matching the plan, and the CHANGELOG demotion of the 1–7 list to "for reference" is honest.

The single residual carried over from Round-1 is the **spec Addendum B's internal "9 slices"** (`docs/design/KimCad-Unified-Product-Spec-v3.0.md:417–422`), which was never touched. Per the round-2 charge, I judged whether it still misleads: **it does not rise to a finding.** ROADMAP and the plan are now explicitly authoritative and both carry the "renumbered to 11 / spec Addendum B's 9 predates the renumber" note that names this exact surface; Addendum B itself says "Full plan: `docs/stage-8.5-usability-plan.md`" (:391) and "Severity-tagged punch list in the plan doc. `ROADMAP.md` is the live operational roadmap" (:421–422). A reader is pointed off the stale count to the authoritative one from inside the same addendum. It is a Nit at most (a one-line "superseded → 11, see the plan" pointer at :417 would close it cosmetically), and I am not inflating the rollup with it.

**Round-2 re-audit rollup (this role):** Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 = **0**
(Round-1 was 0·0·0·3·0. All three Minors closed; no regressions.)

---

## Per-item verification

### DOC-003 — ✅ RESOLVED
ROADMAP's inline Stage-8.5 slice list was the surface Round-1 flagged as still showing 9 inside a doc whose header said 11. The body is now rewritten to enumerate exactly **11 numbered slices** (`ROADMAP.md:227–232`): (1) persistence; (2) refinement + version history; (3) numeric editing; (4) units; (5) advanced on-ramps design; (6) settings; (7) photo on-ramp; (escape-paths sweep, unnumbered, matching the plan's inserted stage); (8) problems on the model; (9) onboarding/wizard; (10) output clarity + print estimate; (11) responsive/a11y/copy/polish. The header list-label now reads **"Slices (renumbered to 11 — the authoritative list is `docs/stage-8.5-usability-plan.md`)"** (`ROADMAP.md:225`), and the "renumbered to 11 slices 2026-06-03 … spec Addendum B's '9 slices' predates the renumber. The plan doc is the source of truth" note is present (`ROADMAP.md:216–218`). Header and body now tell ONE story (11), cross-checked self-consistent against the plan (`docs/stage-8.5-usability-plan.md:34–126`, Slice 1 … Slice 11). The "papers over rather than reconciles" defect from Round-1 is gone.
**Residual:** none in ROADMAP. The spec Addendum B copy is untouched (see "Residual" below) but is no longer a finding given the authoritative pointers.

### DOC-005 — ✅ RESOLVED
The CHANGELOG preamble no longer asserts "Slices 1–7 are built" as the current build state. `CHANGELOG.md:15–17` now reads **"All 11 slices are built on the branch and the stage gate ran (wiring-audit + 5-role audit-team; remediation to 0/0/0/0/0 in progress — see `docs/audits/stage-8.5/stage-gate-2026-06-05/`). Slices 1–7 below for reference:"** — the 1–7 enumeration that follows (:18–23) is now explicitly demoted to reference detail, not a status claim. This reconciles with the HANDOFF resume box ("Slices 1–11 built", `HANDOFF.md:5`), the title (:1), and the RUN-LEDGER. The "1–6 tagged" headline half stays fixed at `CHANGELOG.md:9` ("Stages 0–7 are tagged"). The only remaining occurrences of the old "Slices 1–7 are built" / "Stages 1–6 are tagged" strings repo-wide are inside the historical audit deep-dive reports themselves — correct as archived artifacts, not live docs.
**Residual:** none.

### DOC-006 — ✅ RESOLVED
The README setup line now carries the 780M-vs-spec-890M reconciliation. `README.md:103–104`: "a 32 GB box with a 780M iGPU — **the v3.0 spec's reference box is the slightly stronger Beelink 890M, so anything that runs here runs on the spec reference too** — and stays fast and stable there". This is the exact doc/line Round-1 said the prior remediation missed; it now matches the same note already present in ROADMAP (:13–15) and HANDOFF §9. The note is consistent across all three docs (790M target < 890M spec reference → forward-compatible), and the inserted clause is grammatically clean within the sentence.
**Residual:** none.

### DOC-new-1 — ✅ RESOLVED
HANDOFF.md's self-contradiction (a current resume box sitting atop an un-reconciled stale body) is resolved by both a reconciled title and an explicit historical-marker. The title (`HANDOFF.md:1`) now reads **"Stage 8.5 (Usability): all 11 slices built & pushed; stage gate ran …"** — it no longer omits Slice 11 (Round-1 noted the old title said "Slices 1–8 + Slice 9 + Slice 10" while the box said 11). The resume box header is relabeled **"▶ RESUME HERE … — THIS BOX + the RUN-LEDGER are the SINGLE SOURCE OF TRUTH"** (`HANDOFF.md:3`), and a marker block immediately follows (`HANDOFF.md:10–13`): "⚠ **The slice-by-slice narrative below is HISTORICAL build-log detail** (written through Slice 9/10 and not line-by-line current — stale SHAs, 'RESUME = Slice 10', 'Slice 9 MS-x REMAINING', etc.). For current state use the RESUME box above + `docs/audits/RUN-LEDGER-2026-06-05.md`. The detail is kept for provenance; do not treat its resume pointers as live." This is exactly the reconciliation the task called for: title + box + marker now agree on the current truth, and the stale body (still present at :15–90, with its "RESUME = Slice 11", "MS-2/3/4 REMAINING", head `12a9686`) is explicitly fenced off as non-authoritative provenance. The two-truths problem is closed: there is one live truth (the box + ledger), one labeled-historical narrative.
**Residual:** none. (The stale body could be archived outright for tidiness, but the marker fully neutralizes its misleading potential — it is now provenance, not a competing resume pointer. Not a finding.)

---

## New-drift check (round-2 edits) — CLEAN

- **README** — the 890M parenthetical is inserted mid-sentence and the sentence still parses ("a 32 GB box with a 780M iGPU — … — and stays fast and stable there"). No new claim, no broken markdown. Clean.
- **ROADMAP** — inline list now enumerates 11 and only 11 numbered slices, matching the plan; the unnumbered "(escape-paths sweep)" correctly mirrors the plan's inserted escape stage rather than inflating the count to 12. No double-count, no orphaned old "(9)" tail. Clean.
- **CHANGELOG** — the "for reference" demotion is honest (the 1–7 list is reference, the status line says all 11 built + gate ran + remediation in progress, which matches the ledger). No overclaim — it does NOT say the gate passed, only that it "ran … remediation to 0/0/0/0/0 in progress". Clean.
- **HANDOFF** — the marker adds an accurate caveat without contradicting anything; the title now matches the box. Clean.
- **RUN-LEDGER** — the round-2 closure is recorded honestly (`RUN-LEDGER:38`: "docs reconciled (CHANGELOG/README/ROADMAP + HANDOFF 'historical body' marker)") and the Docs(9) row's prior overstatement (Round-1 DOC-new-2) is now substantively true because the residuals are actually fixed. The round-2 row is still `☐` ("Round-2 re-verify → confirm clean", :39) — appropriately open pending this closure. Clean.

## User-facing surface + SUPERSEDED banners — STILL ACCURATE

- **First-time user surface** (README, the My-Designs guide, glossary, config comments, `docs/README.md` index): unchanged in substance and still clean/honest. The README's only round-2 change is the truthful 890M note. No regression.
- **design/README SUPERSEDED banner** (`docs/design/README.md:3–17`): intact and still accurate — gemma4:e4b is THE model / Qwen rejected 0-of-10 / never Chinese; photo vision LOCAL by default / cloud OFF by default; correctly scoped ("Everything else … remains the build target") and points at the controlling spec. Matches the settled posture and the spec's own corrections. No drift.
- **Spec SUPERSEDED corrections**: the spec carries the same gemma-only / local-vision corrections (per Round-1, unchanged here); the design-README banner and the spec reinforce rather than contradict each other.

## Residual carried from Round-1 (judged, not a finding)

- **Spec Addendum B inline "9 slices"** (`docs/design/KimCad-Unified-Product-Spec-v3.0.md:417–422`) — untouched by round-2 (the commit did not modify the spec). Per the round-2 charge, judged: it does **not** still mislead, because (a) ROADMAP and the plan are now explicitly the authoritative slice list, both naming Addendum B's "9" as predating the renumber, and (b) Addendum B itself routes the reader to the plan ("Full plan: `docs/stage-8.5-usability-plan.md`", :391) and to ROADMAP as "the live operational roadmap" (:421–422). The stale count lives next to its own pointer off itself. **Nit-grade cosmetic only** — an optional one-line "superseded → 11 slices, see the plan" at :417 would close it fully. Not counted in the rollup.

---

## Round-2 severity rollup (this role)

```
Blocker:  0
Critical: 0
Major:    0
Minor:    0   (all three Round-1 Minors — DOC-003, DOC-005, DOC-new-1 — RESOLVED)
Nit:      0   (spec Addendum B inline count noted as optional cosmetic; not counted)
-----
Total:    0
```

**Docs gate read (round-2):** **CLEAN — docs role is at 0/0/0/0/0.** Every Round-1 residual is genuinely closed in the current docs at `a6dff43`, verified file:line and cross-checked against the authoritative plan and the tag set. No new drift was introduced. The user-facing surface and both SUPERSEDED banners remain accurate and honest. The one carried-over item (spec Addendum B's internal 9-count) does not mislead given the authoritative pointers now in place and is at most an optional one-line cosmetic — it is not a hold on the gate. Documentation clears for the Stage 8.5 merge/tag.

## Drafts produced
None. No doc requires a replacement draft. The only optional follow-up is a single-line cosmetic pointer at spec Addendum B (`:417`), which is not required for the gate.
