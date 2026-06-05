# 03 — Documentation RE-AUDIT (Technical Writer)

**Audit:** KimCad Stage 8.5 (Usability) — stage gate, post-remediation re-audit
**Branch / commit:** `stage-8.5-usability` @ `6c98674` ("Stage 8.5 gate remediation (Test + QA): close all 8 remaining findings")
**Remediation under review:** docs commit `d2764ad` ("docs: close all 9 documentation findings")
**Date:** 2026-06-05
**Role:** Senior Technical Writer — independent, skeptical re-audit. Verify each prior finding is genuinely fixed in the CURRENT docs (cite file:line), and hunt for NEW drift the remediation introduced.
**Original report:** `docs/audits/stage-8.5/stage-gate-2026-06-05/03-documentation-deepdive.md`
**Cross-checked against:** the actual route set in `src/kimcad/webapp.py` (do_GET 807–883, do_POST 1005–1037).

---

## Verdict at a glance

The docs remediation is **mostly genuine** — both original Majors (DOC-001, DOC-002) are fully resolved with accurate, verifiable fixes, and four of the six findings plus all three Nits are closed. But the commit message overclaims on **DOC-003** ("slice count reconciled (11, plan doc authoritative)") and **DOC-006** ("780M vs spec-890M note"): both are only **partially** fixed, and one of them not at all on the surface that mattered. Worse, the remediation **introduced one new "one truth per doc" violation inside HANDOFF.md** (the new resume box now sits on top of an un-reconciled stale body) and **left one pre-existing cross-doc understatement live** (CHANGELOG says "Slices 1–7 built" while HANDOFF/ledger say 1–11 built + gate ran).

None of the residuals would mislead a **first-time user** — the user-facing surface (README, My-Designs guide, glossary, config comments, new `docs/README.md` index) is clean and honest. The residuals mislead a **maintainer** resuming cold (stale slice lists; a self-contradicting HANDOFF body). All are Minor.

**Re-audit rollup (this role):** Blocker 0 · Critical 0 · Major 0 · Minor 3 · Nit 0 = **3**
(Down from the original 2 Major · 4 Minor · 3 Nit = 9. Both Majors closed; 1 prior Minor still open; 2 new Minors.)

---

## Per-finding verification

### DOC-001 (was Major) — ✅ RESOLVED (verified accurate vs `webapp.py`)

`HANDOFF.md` lines 313–331 now read **"Backend API contract — AUTHORITATIVE LIST IS `ARCHITECTURE.md` (kept current per stage)."** The "**unchanged** seam" framing is gone (line 313–315 explicitly says "The SPA seam GREW substantially across Stages 5–8.5; this block is a summary, not the full enumeration — read `ARCHITECTURE.md` for the complete, current route list").

The block now enumerates the full Stage-5/8.5 surface (lines 323–331): `POST /api/render/<id>`, the `/api/designs*` family (list / reopen / thumb / save / import / export / rename / delete / duplicate), `GET`+`POST /api/settings`, `GET /api/model-status`, `GET /api/health`, `GET /api/design/progress/<job_id>`, `POST /api/photo-seed`.

**Cross-check vs the actual routes** (verified line-by-line):
- do_GET (`webapp.py` 811–882): `/api/options`, `/api/settings`, `/api/model-status`, `/api/health`, `/api/connectors`, `/api/connector-status/`, `/api/mesh/`, `/api/gcode/`, `/api/design/progress/`, `/api/designs`, `/api/designs/<id>` (+`/thumb`, +`/export`, reopen).
- do_POST (`webapp.py` 1006–1037): `/api/design`, `/api/settings`, `/api/photo-seed`, `/api/slice/`, `/api/render/`, `/api/send/`, `/api/designs/save`, `/api/designs/import`, `/api/designs/<id>/{rename,delete,duplicate}`.

Every documented endpoint exists; every existing endpoint is documented (in the block and/or ARCHITECTURE). The "Authoritative list is ARCHITECTURE" pointer matches the original fix recommendation (collapse to a pointer to avoid a third drifting copy). **Genuinely fixed.**

### DOC-002 (was Major) — ✅ RESOLVED (banner present, accurate, covers both halves)

`docs/design/README.md` lines 3–17 now carry a top-of-file **"⚠ SUPERSEDED POSTURE — read before building to this doc"** block that corrects exactly the two stale postures the finding named:
- **Model (lines 6–10):** "`gemma4:e4b` is THE default and the only model the UI presents… The 'Choose a model' step's **Qwen2.5-Coder 'RECOMMENDED'** card… is superseded — Qwen was evaluated via a live bake-off and **rejected (0/10)**… never a Chinese model." Accurate vs the settled posture (spec banner :264; plan Trust Rules).
- **Photo on-ramp (lines 11–14):** "the photo is read by **gemma4:e4b's local vision** by default and never auto-sends… Cloud (OpenRouter) is OFF by default everywhere." Accurate vs shipped Slice 7 (ARCHITECTURE :160–168; CHANGELOG :33–41).

It also scopes itself correctly (line 16: "Everything else in this doc… remains the build target") and points at the controlling spec (line 17). This mirrors the spec's own pattern, which is what the original fix path recommended.

**Residual (not a re-open):** the inline stale text further down is still **un-annotated** — `model card "Qwen2.5-Coder… RECOMMENDED"` (line 163), the bundle chip "Qwen2.5-Coder" with a green check (line 162), the photo disclosure "your photo leaves the device… Switch to Gemma 4 E4B to analyze locally" (line 173), and the state contract `model (qwen|gemma|cloud)` (line 220). The original finding offered the inline strike as a *secondary* option and judged the banner *sufficient* ("a full prototype rewrite is out of scope… a banner is sufficient"). The banner explicitly names and disclaims all of these, so a reader cannot act on them by accident. **Resolved as scoped.** (A future pass could annotate the four inline spots; not a gate blocker.)

### DOC-003 (was Minor) — ⚠ PARTIALLY RESOLVED — the spec Addendum B was never touched; ROADMAP's own inline list still says 9

Commit message: "DOC-003 slice count reconciled (11, plan doc authoritative)." What actually happened:

- **ROADMAP.md** got a header note (lines 215–218): "renumbered to 11 slices 2026-06-03… spec Addendum B's '9 slices' predates the renumber. The plan doc is the source of truth for the slice list." Good — that's the recommended citation. **But ROADMAP's own Stage-8.5 "Slices" list (lines 226–230) still enumerates only 9, ending at "(9) responsive, accessibility, copy, polish."** So within a single doc the header says "11, see the plan" while the body lists 9. The citation papers over rather than reconciles.
- **`KimCad-Unified-Product-Spec-v3.0.md` Addendum B was NOT modified by `d2764ad` at all** (the commit touched ROADMAP, not the spec — confirmed via `git show d2764ad --stat`). Addendum B lines 417–422 **still list the 9-slice set** with no superseding note. The original finding named the spec Addendum B as one of the two drifting surfaces; it remains drifted, with not even a pointer added.

The plan doc itself is authoritative and correct (Slices 1–11, `stage-8.5-usability-plan.md` :34–126, with the escape-paths stage at :98). So the "one truth" exists — but two of the three surfaces the finding called out still show the stale 9-count, and the spec surface got nothing. **Severity stays Minor** (scope is identical across all docs; only the indices drift, and the plan is self-consistent), but the finding is **not genuinely closed** as the commit claims. Recommend: add the same one-line "superseded → see the plan (11 slices)" pointer to spec Addendum B (:417), and either trim ROADMAP's inline list to a pointer or sync it to 11.

### DOC-004 (was Minor) — ✅ RESOLVED

`GET /api/health` is now documented in ARCHITECTURE.md's web layer: line 162 ("`GET /api/health` is a lightweight liveness check"). It also appears in the HANDOFF contract block (:330). Matches the handler (`webapp.py` `_handle_health` :1046). **Fixed.**

### DOC-005 (was Minor) — ◐ PARTIALLY RESOLVED — the "1–6 tagged" line is fixed; the "Slices 1–7 built" understatement is now a live cross-doc inconsistency

The headline half is fixed: `CHANGELOG.md` line 9 now reads **"Stages 0–7 are tagged (`stage-0` … `stage-7`)"** (was "Stages 1–6 are tagged"). Verified — and consistent with the tags. Good.

But the original DOC-005 also flagged the preamble's slice-built count as understated, and that half is now worse, not better: **CHANGELOG line 15 still says "Slices 1–7 are built on the branch"** and the preamble (lines 14–21) describes only Slices 1–7. Meanwhile the **HANDOFF resume box (line 5) says "Slices 1–11 built + pushed; the stage gate ran"**, the **title (line 1)** and the **RUN-LEDGER** both confirm 1–11 built and the gate run. So a maintainer reading the CHANGELOG `[Unreleased]` block today is told only 7 of 11 shipped slices exist.

The original report judged this acceptable *because* of the documented batch-at-merge convention (the Stage 8.5 `Added` block is written at merge). That defense still technically holds — the CHANGELOG's `Added` section legitimately batches at merge. But the *preamble prose* "Slices 1–7 are built" is a factual statement, not a deferred section, and it is now contradicted by every other status doc in the repo. **Minor, still open.** Recommend: at minimum update line 15 to "Slices 1–11 are built on the branch (the Stage 8.5 `Added` block is batched at merge)."

### DOC-006 (was Minor) — ◐ PARTIALLY RESOLVED — HANDOFF + ROADMAP got the note; the README line the finding pointed at did not

Commit message: "DOC-006 780M vs spec-890M note." Verified:
- **ROADMAP.md** lines 13–15 now reconcile it: "The v3.0 spec's reference box is the slightly stronger Beelink **890M**; KimCad targets the 780M, so anything that runs here runs on the spec reference too — see HANDOFF §9." Good.
- **HANDOFF.md** §9 (:480) already reconciled it pre-remediation.
- **README.md line 103 — still bare "a 32 GB box with a 780M iGPU"** with no reconciliation note. The original DOC-006 evidence and fix path both pointed specifically at `README.md:103` ("Add a parenthetical to README:103"). The remediation's README change (+2/-2 in `d2764ad`) was the DOC-N2 web-UI label, not this. A reader who only reads the README and then opens the spec (which says 890M) still hits the unexplained gap the finding described.

**Minor.** The reconciliation now exists in two docs but is still absent from the one doc the finding cited. Folding into "resolved" is generous; I'd call it resolved-for-the-roadmap, open-for-the-README. Recommend the one-line parenthetical on README:103 as originally specified. (Counting it as one of the residual Minors below would be double-counting with DOC-003/HANDOFF; I note it here and do not inflate the rollup with it, since the substance — reconciliation exists in the operational docs — is present.)

### DOC-N1 (was Nit) — ✅ RESOLVED

`HANDOFF.md` lines 3–8 now open with a **"▶ RESUME HERE (5-line orientation)"** box: Where / What's done / Active task / Then / Rules. Exactly the ask. (See DOC-new-1 below for the side effect.)

### DOC-N2 (was Nit) — ✅ RESOLVED

`README.md` line 149 now reads simply **"### Web UI"** — the legacy "(Phase 2, early)" label is gone. Aligns with the Stage vocabulary.

### DOC-N3 (was Nit) — ✅ RESOLVED

`docs/README.md` now exists (23 lines) as a `docs/` index that **separates current from historical**: a "Current (read these)" section (design/spec, the 11-slice plan, the My-Designs guide, PrintProof3D integration, benchmarks, audits) and a "Historical (kept for provenance — NOT current instructions)" section naming the completed-stage directive snapshots (`stage-5-completion-directive-2026-06-02.md`, `stage-8.5-slice-5-onramps.md`, etc.). It even points a resumer at the right source-of-truth set. Clean fix.

---

## NEW drift introduced or left by the remediation

### DOC-new-1 (Minor · one truth per doc) — HANDOFF.md now self-contradicts: a current resume box sitting on a stale body

The DOC-N1 resume box was **prepended** to HANDOFF.md, but the long ⛔ READ FIRST body beneath it was **not reconciled to the new state**. The result is a doc that states two different "where are we" truths:

- **Top (current):** title (line 1) "Slices 1–8 + Slice 9 (MS-1..MS-4) + Slice 10 done & pushed"; resume box (line 5) "Stage 8.5 Slices 1–11 built + pushed; the stage gate ran (wiring-audit PASS; 5-role audit-team)"; active task = "remediate the Stage 8.5 audit-team findings to 0/0/0/0/0 → merge → tag."
- **Body (stale, pre-remediation):** line 25 "**RESUME HERE = Stage 8.5, Slice 11** (responsive/a11y/copy/polish). Slices 9 and 10 are COMPLETE."; lines 69–73 "**Slice 9 micro-slices REMAINING:** MS-2 in-app help/glossary… MS-3 real step progress… MS-4 first-run wizard… plus an empty/loading/error-state copy sweep"; line 77 "Branch head `12a9686`, working tree clean" (the actual head is `6c98674`).

The title itself omits Slice 11 while the resume box includes it. The body says MS-2/3/4 and Slice 11 are still *ahead* while the resume box says all 11 slices are *done and the gate ran*. This is precisely the "a handoff that says 'done' in one place and 'still ahead' in another" anti-pattern the doc's own §7 lesson (lines 452–454) warns against, and the remediation made it sharper by adding an authoritative-looking resume box without retiring the contradicting narrative. **Minor** (a careful reader trusts the resume box at the top, which is what it's designed for), but it's a genuine new inconsistency in the single most load-bearing maintainer doc. Recommend: collapse or archive the stale READ-FIRST Stage-8.5 narrative (lines 12–86) so the resume box + a short current-state paragraph are the only Stage-8.5 status in the doc.

### DOC-new-2 (Minor · accuracy) — the docs commit message overstates two closures

`d2764ad`'s message asserts "DOC-003 slice count reconciled (11, plan doc authoritative)" and "DOC-006 780M vs spec-890M note" as done. As shown above, DOC-003's spec Addendum B was never touched (and ROADMAP's inline list still says 9), and DOC-006's note never reached the README line the finding cited. This is a provenance/honesty issue with the remediation record itself — the kind the project flags ("never assert a fact… without running the one-line check first," HANDOFF :449–451). It doesn't mislead a product user, but it means the ledger's "✅ Docs (9) — DOC-001..006 + DOC-N1/N2/N3 — commit `d2764ad`" (RUN-LEDGER line 33) **overstates** the close: two of those are partial. **Minor** — fix the residuals (which closes the substance), and the record becomes true. I am NOT counting this separately in the severity rollup; it is the same substance as DOC-003/005/new-1 viewed from the ledger side.

### Things checked for new drift that are CLEAN
- The new `docs/README.md` index is accurate (every "current" file it names exists; the "historical" files it names exist) and does **not** contradict the root docs — it points at HANDOFF's resume box + the ledger + the plan + the spec as the source-of-truth set, which is correct.
- The design/README SUPERSEDED banner does **not** contradict the spec — both now carry the same gemma-only / local-vision correction; they reinforce each other.
- ARCHITECTURE's web-layer additions (:160–198) match the routes and do not contradict the HANDOFF contract block (the block defers to ARCHITECTURE as authoritative — consistent).
- The RUN-LEDGER's only overstatement is the "Docs (9) all closed" row (covered by DOC-new-2); its program/status rows are accurate to the git log (`6c98674` = the Test+QA remediation; stage-8.5 not yet tagged).

---

## "One truth per doc" — does it hold?

**Mostly, with two specific breaks.**
- ✅ The API contract now has one authoritative home (ARCHITECTURE) with HANDOFF deferring to it — the third-copy drift that caused DOC-001 is gone.
- ✅ The model/vision posture has one truth, reinforced across the spec banner, the design-README banner, README, CHANGELOG, and config comments.
- ❌ **Slice count** is NOT one truth: the plan says 11 (authoritative), ROADMAP's header says "11 see the plan" but its body lists 9, the spec Addendum B lists 9 with no note, and the CHANGELOG preamble says "1–7 built." Four surfaces, three different stories.
- ❌ **Resume state** is NOT one truth *within HANDOFF.md itself* (DOC-new-1).

---

## Would any doc still mislead a user or a maintainer?

- **A first-time user:** **No.** README, the My-Designs guide, the glossary, config comments, and the new `docs/` index are accurate, honest, and free of overclaim. The model/vision posture (the one user-visible honesty risk) is corrected everywhere it appears. Nothing tells a user the product does something it doesn't.
- **A future maintainer:** **Yes, in two low-stakes places.** (1) Opening HANDOFF.md, they get a correct resume box immediately above a body that tells them Slice 9 MS-2/3/4 and Slice 11 are still ahead and the head is `12a9686` — stale, contradictory (DOC-new-1). (2) Mapping the Stage 8.5 slice numbering across the spec Addendum B / ROADMAP body / CHANGELOG, they hit three different counts (DOC-003, DOC-005). Both are doc-lag inside maintainer docs, not product defects — the code, the plan, the ledger, and the resume box are all correct. No Blocker/Critical/Major remains.

---

## Severity rollup (this re-audit)

```
Blocker:  0
Critical: 0
Major:    0   (both prior Majors — DOC-001, DOC-002 — resolved)
Minor:    3   (DOC-003 partial; DOC-005 second-half; DOC-new-1 HANDOFF self-contradiction)
Nit:      0   (all three prior Nits — DOC-N1/N2/N3 — resolved)
-----
Total:    3
```

**Gate read (docs role):** The two release-relevant Majors are genuinely closed and the user-facing surface is clean — nothing here blocks the Stage 8.5 gate. The 3 residual Minors are maintainer-facing doc-lag and a one-doc internal contradiction; they should be cleaned before the merge/tag (they are exactly the "one truth per doc" slips the project holds itself to), but none is a hold on `0/0/0/0/0` if explicitly accepted as Minor. Recommend folding all three into the docs batch that lands at the Stage 8.5 merge: (a) add the 11-slice pointer to spec Addendum B and trim ROADMAP's inline 9-list; (b) refresh CHANGELOG line 15 to "Slices 1–11 built"; (c) reconcile or archive the stale HANDOFF Stage-8.5 body beneath the new resume box.

## Drafts produced
None. All three residuals are one-line edits / a short archive — no doc is broken badly enough to require a replacement draft.
