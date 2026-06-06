# 03 — Documentation Deep-Dive (Technical Writer)

**Audit:** KimCad Stage 8.5 (Usability) — stage gate
**Branch / commit:** `stage-8.5-usability` @ `95b25e0` ("Stage 8.5 Slice 11: responsive / a11y / copy / polish")
**Date:** 2026-06-05
**Role:** Senior Technical Writer — audit-only (flag gaps; draft a replacement only if a doc is broken enough to block readiness)
**Scope:** README.md, ARCHITECTURE.md, ROADMAP.md, CHANGELOG.md, HANDOFF.md, docs/stage-8.5-usability-plan.md, docs/design/README.md + KimCad-Unified-Product-Spec-v3.0.md, docs/printproof3d-integration.md, docs/guide-my-designs.md, config/default.yaml comments, frontend/src/glossary.ts. Cross-checked against the actual `src/kimcad/webapp.py` route set after Stage 8.5.

---

## Verdict at a glance

The user-facing and operational docs (README, ARCHITECTURE, ROADMAP, CHANGELOG, the new `guide-my-designs.md`, the config comments, and the in-app glossary) are in **strong shape** — accurate, current to Stage 8.5, honest about what's on-branch-vs-merged, and notably honest about deferrals (no fabricated layer viewer, weight-estimate honesty, "nothing leaves the machine"). The CHANGELOG and ARCHITECTURE in particular are best-in-class for this repo.

The findings cluster in **two doc surfaces that lag the settled product posture**:
1. **HANDOFF.md's "Backend API contract" block** still describes only the Stage-4 seam and omits the entire Stage-8.5 endpoint surface that the branch actually shipped — a behavior-changing contract drift (Major).
2. **docs/design/README.md** (the design-reference prototype doc) still presents **Qwen2.5-Coder as the RECOMMENDED model** and the **photo on-ramp defaulting to cloud OpenRouter vision ("your photo leaves the device")** — both directly contradicting the settled `gemma4:e4b`-only, local-vision-only posture that the rest of the docs and the shipped code enforce. Unlike the v3.0 spec (which carries explicit "⚠ SUPERSEDED" banners over its obsolete Qwen content), the design README has **no** such correction (Major).

No Blockers. No Criticals. Nothing here would block a user from installing or using the product. The two Majors mislead a **maintainer** (stale contract, stale design source) rather than an end user.

**Severity rollup (this role):** Blocker 0 · Critical 0 · Major 2 · Minor 4 · Nit 3 = **9**

---

## What's working (credit where due)

- **CHANGELOG.md is current and honest for Stage 8.5.** Slices 1, 2–4, 6, 7 and the escape-paths stage are each documented with a clear, repeated "(on branch, not yet merged/tagged)" tag (lines 27–68). The batch-at-merge convention is real and consistent with the HANDOFF's stated plan. The `[Unreleased]` preamble (lines 6–24) accurately states the tag status and the pre-release `0.1.0` posture.
- **ARCHITECTURE.md is the standout.** It documents the Stage-8.5 additions in the web layer explicitly — `/api/designs*`, `/api/settings`, `/api/model-status`, `/api/photo-seed` (lines 160–166), the saved-designs/My-Designs flow (lines 186–196), and a `design_store.py` module-map row (line 103). The module map matches the actual `src/kimcad/` tree. The pipeline diagram and the trust-boundary prose are accurate to the code.
- **README.md** leads with a clear one-sentence value prop and an honest, prominent "early development" status block (lines 13–23) that names Stage 8.5 as in-progress-on-branch, not done. Local-first + `gemma4:e4b` + cloud-opt-in posture is stated correctly and repeatedly. The Qwen rejection is stated honestly (lines 118–120).
- **ROADMAP.md** matches the repo tag numbering, correctly marks Stages 0–7 done/tagged and 8.5 in-progress, and the model/hardware/cloud posture (lines 16–22) is settled-and-correct.
- **docs/guide-my-designs.md** is exactly the kind of user-facing doc the product needed — plain English, honest ("It is **not** a printable STL"), and a real FAQ. No overclaim.
- **frontend/src/glossary.ts** is genuinely plain-English, jargon-free, and self-describes its own no-jargon rule. Honest copy throughout (e.g. confidence "High means a deeper engine inspected the 3D shape; lower means only the basic checks were possible").
- **config/default.yaml comments** are excellent and current — the `density`/weight-estimate contract (lines 147–151), the per-printer profile honesty (lines 84–90, 130–132), and the `local_qwen` "evaluated and REJECTED" note (lines 60–64) all match the shipped behavior.
- **docs/printproof3d-integration.md** accurately describes the arm's-length, off-by-default, advisory posture and the report contract — no overstatement of capability.
- **Layer/toolpath viewer is NOT overpromised.** Spec §5.4/§5.5 (lines 190–194) require a *print-aware preview* (bbox + dimensions + build plate + orientation/supports) and a *print report + readiness* — **not** a G-code layer viewer. Every doc that mentions the deferral (README, HANDOFF, the plan's Slice 10, lines 122–123) correctly frames the true sliced/layer viewer as a Stage-10 deferral the plan explicitly sanctions. This is honest and consistent across docs.
- **The v3.0 spec handles its own obsolescence well** — a CONTROL-PLANE STATUS banner (lines 8–18) plus inline "⚠ SUPERSEDED in part" callouts on §7 (line 264), §14 (line 346), and the model-guide section mean a reader can't act on the stale Qwen-default text by accident. This is the model the design README should follow (see DOC-002).

---

## Findings

### DOC-001 (Major · Accuracy) — HANDOFF "Backend API contract" omits the entire Stage-8.5 endpoint surface

**Evidence.** `HANDOFF.md` lines 306–317 ("Backend API contract (the unchanged seam the SPA wires to)") enumerates only the Stage-4 seam:
`POST /api/design`, `GET /api/mesh/<id>`, `POST /api/slice/<id>` (with `estimate_detail`+`gcode_filename` — correctly updated for Slice 10), `GET /api/gcode/<id>`, `GET /api/options`, `GET /api/connectors`, `GET /api/connector-status/<name>`, `POST /api/send/<id>`.

The actual route set in `src/kimcad/webapp.py` after Stage 8.5 (do_GET lines 742–818, do_POST lines 940–972) is materially larger. **Documented but missing from this block:**
- `POST /api/render/<id>` (Stage 5 live re-render) — webapp.py:953
- `GET /api/settings` + `POST /api/settings` — :749, :944
- `GET /api/model-status` — :752
- `GET /api/health` — :755
- `GET /api/design/progress/<id>` (Slice 9 MS-3 progress poll) — :797
- `POST /api/photo-seed` (Slice 7) — :947
- The whole `/api/designs*` family (Slice 1): `GET /api/designs` (:806), `GET /api/designs/<id>` reopen (:816), `GET /api/designs/<id>/thumb` (:811), `GET /api/designs/<id>/export` (:813), `POST /api/designs/save` (:960), `POST /api/designs/import` (:963), `POST /api/designs/<id>/{rename,delete,duplicate}` (:966–970).

The block's own header calls this seam "the **unchanged** seam" — which is now false: the seam grew by ~14 endpoints across Stages 5–8.5.

**Why this matters.** The HANDOFF is the project's stated **source of truth** for a maintainer resuming cold ("Do NOT rebuild from memory" — HANDOFF:163). A future maintainer (or the next audit) reading this block as the API contract would believe persistence, settings, photo-seed, progress, and live-render endpoints don't exist — exactly the Stage-8.5 deliverables. It violates the project's own "one truth per doc" rule (HANDOFF:437–439): ARCHITECTURE.md documents these endpoints correctly while HANDOFF asserts the seam is unchanged. Note this is a *handoff/contract* doc, not user-facing copy, so it misleads a maintainer, not an end user — hence Major, not Critical. (Per the severity framework, doc drift on a behavior-changing contract is at least Major.)

**Blast radius:**
- Adjacent docs: ARCHITECTURE.md "The web layer" (lines 133–196) is the authoritative, correct version — the fix is to make HANDOFF point to it or mirror it, not to re-derive a third copy. CHANGELOG already lists the endpoints per-slice correctly.
- Shared assumption: the "Backend API contract" block is referenced implicitly as the SPA↔backend seam; `frontend/src/api.ts` is the de-facto client-side contract and already calls all the new endpoints — so the *code* is consistent; only this doc lags.
- Migration: none — additive endpoints, no client break.
- Tests to update: none (tests already cover the routes; `tests/test_webapp.py` exercises `/api/health` etc.).
- Related findings: DOC-003 (the spec Addendum B slice list also drifts).

**Fix path (short — no draft needed).** Replace the "(the *unchanged* seam …)" framing and append the Stage-5/8.5 endpoints, OR collapse the block to a one-line pointer: "Authoritative API surface: ARCHITECTURE.md → *The web layer*; per-slice additions in CHANGELOG." Recommend the pointer — it removes the third copy that can drift again, consistent with the "one truth per doc" rule.

---

### DOC-002 (Major · Accuracy / Honesty) — docs/design/README.md still recommends Qwen and defaults the photo on-ramp to cloud vision, with no superseding note

**Evidence.** `docs/design/README.md` (the high-fidelity design-reference doc, dated by its Stage 8.5 Addendum to 2026-06-03):
- **Line 147 (wizard Step 2):** "two radio **model cards** (Qwen2.5-Coder, with a "RECOMMENDED" accent tag, and Gemma 4 E4B) … `Fast · Local · 1.5B`". The settled posture is the opposite: **gemma4:e4b is the only default; Qwen was rejected 0/10 and is a manual `--backend` only; no UI offers an alternative** (trust rules in `stage-8.5-usability-plan.md` lines 72–77; spec banner lines 17).
- **Line 146 (wizard Step 1 bundle chips):** lists "Qwen2.5-Coder" as a bundled component with a green check.
- **Line 157 (photo on-ramp):** "Default analysis runs on a **free OpenRouter vision model — your photo leaves the device**. Switch to Gemma 4 E4B to analyze locally & offline." The shipped Slice 7 + the trust rules are the **inverse**: the photo on-ramp uses gemma4:e4b's **local** vision, never auto-sends, and the photo never leaves the machine (CHANGELOG:33–41; ARCHITECTURE:160–166; plan:91–93).
- **Line 204 (state contract):** `model` (`qwen`|`gemma`|`cloud`) — encodes qwen as a first-class app state.

Unlike `KimCad-Unified-Product-Spec-v3.0.md`, which corrects every obsolete Qwen reference with a CONTROL-PLANE banner (spec:8–18) and inline "⚠ SUPERSEDED in part" callouts (spec:264, 346), **the design README's Stage 8.5 Addendum (lines 245–276) adds no model-posture correction.** It references "the trust rules" only indirectly via the plan/spec, leaving the Qwen-RECOMMENDED and cloud-default-vision text reading as current design intent.

**Why this matters.** This doc is explicitly the **fidelity check / acceptance target** for the SPA build ("Build to THIS prototype where it already exists" — README:254; "Each slice's rendered audit-lite is the fidelity check against this design" — README:276). A maintainer building or auditing the first-run wizard (FirstRunWizard, Slice 9 MS-4) against this doc would build *Qwen-recommended* model cards and a *cloud-default* photo flow — directly violating the load-bearing, repeatedly-settled gemma-only/local-vision rule. It's the highest-risk honesty gap in the doc set because it points the build at the wrong posture. (Major, not Critical: the *shipped* FirstRunWizard already does the right thing — gemma-only, honest download-vs-connect — per HANDOFF:45–50, so this is latent risk for future work, not a current product defect.)

**Blast radius:**
- Adjacent code: `frontend/src/components/FirstRunWizard.tsx` (already correct — gemma-only); `advanced.jsx → ModelPicker` in the prototype is the stale source.
- Shared assumption: every "build to the prototype" instruction inherits this doc's stale model posture.
- Migration: none (doc-only).
- Tests to update: none.
- Related findings: cross-role — this is the same root cause the spec already remediated; a Principal/QA finding on any future wizard work would point here.

**Fix path (short — no draft needed; audit-only mode is correct here).** Add a one-line superseding banner at the top of `docs/design/README.md` mirroring the spec's pattern, e.g.: "⚠ MODEL POSTURE SUPERSEDED (Stage 6/8.5): `gemma4:e4b` is the only default; Qwen was rejected and is a manual `--backend` only; the photo on-ramp uses **local** vision and never sends the photo off-machine. The wizard/model-picker/photo-on-ramp copy below predates this — see `../stage-8.5-usability-plan.md` Trust Rules and the spec's CONTROL-PLANE banner." Then strike or annotate lines 146–147, 157, 204. A full prototype rewrite is out of scope for audit mode and not warranted — a banner is sufficient and consistent with how the spec handled identical drift.

---

### DOC-003 (Minor · Accuracy) — spec Addendum B + ROADMAP describe a 9-slice Stage 8.5; the plan is now 11 slices

**Evidence.** `KimCad-Unified-Product-Spec-v3.0.md` Addendum B (lines 417–421) and `ROADMAP.md` (lines 221–226) both list the Stage 8.5 slices as a 9-item set ending at "(9) responsive, accessibility, copy, polish." The live `docs/stage-8.5-usability-plan.md` was **renumbered 2026-06-03** (plan:76; HANDOFF:76–77): the on-ramps design became Slice 5, settings Slice 6, the photo on-ramp Slice 7, an **escape-paths stage was inserted ahead of Slice 8** (plan:96–104), and the polish slice is now **Slice 11**. So the same stage is described with two different slice counts/numbers across docs.

**Why this matters.** Lower-stakes than DOC-001/002 — the *scope* is the same in all three; only the slice indices drift. A maintainer mapping "Slice 9" across docs would land on different things (polish in the spec/roadmap; onboarding/model-down in the plan). The plan doc is internally self-consistent and self-documents the renumber, so the confusion is contained.

**Fix path.** ROADMAP and spec Addendum B should either cite the plan as the authoritative slice list (one truth) or sync to the 11-slice numbering. Recommend the citation — the plan is the live operational doc and will keep moving.

---

### DOC-004 (Minor · Completeness) — `/api/health` is undocumented in every contract doc

**Evidence.** `GET /api/health` exists (webapp.py:755, `_handle_health`), is exercised by `tests/test_webapp.py`, and is called from `frontend/src/api.ts` — but appears in **no** doc's API surface (not the HANDOFF contract block, not ARCHITECTURE's web-layer list). ARCHITECTURE lists the other GETs but skips this one.

**Why this matters.** Small. A health endpoint is conventionally self-explanatory, but a maintainer enumerating the surface from the docs would miss it. Folds naturally into the DOC-001 fix.

**Fix path.** Add `GET /api/health` to ARCHITECTURE's web-layer endpoint list when DOC-001 is addressed.

---

### DOC-005 (Minor · Accuracy) — CHANGELOG `[Unreleased]` says "Stages 1–6 are tagged" then immediately documents Stage 7 as tagged

**Evidence.** `CHANGELOG.md` line 9: "**Stages 1–6 are tagged (`stage-1` … `stage-6`).**" Lines 12–13 (same paragraph) then state Stage 7 "merged + tagged `stage-7` 2026-06-02." The "1–6" summary line is stale by one stage; `stage-7` is real and tagged (confirmed in HANDOFF:81, ROADMAP:54).

**Why this matters.** Minor internal inconsistency in one preamble sentence — the very next sentence corrects it, so no reader is left wrong, but it's exactly the "one truth per doc" slip the project flags. Also: Stage 8.5 Slices 8, 9 (MS-1..4), 10, and 11 are not yet in the CHANGELOG's `Added` section — which is *correct* per the documented batch-at-merge convention (HANDOFF:44–45), but the preamble's "Slices 1–7 are built on the branch" (line 15) now understates reality (Slices 8–11 are also built). Flag as a single Minor: refresh the preamble counts at the stage-merge CHANGELOG batch.

**Fix path.** At the Stage 8.5 merge, update line 9 to "Stages 1–7 are tagged," refresh the "Slices 1–7" count to the full 1–11, and add the batched Stage 8.5 `Added` block. This is a normal stage-merge step, not a defect to fix mid-branch.

---

### DOC-006 (Minor · Accuracy) — README setup says target is a "780M iGPU" while the spec reference HW is the 890M

**Evidence.** `README.md` line 103 ("a 32 GB box with a 780M iGPU"), config/default.yaml:49, and ROADMAP:13 all say **780M**. The v3.0 spec reference hardware is the **Radeon 890M** (spec:8, 69, 306). HANDOFF:464–465 reconciles this honestly: "Spec reference HW is a Beelink 890M; our box is the 780M." So this is a *real* deliberate distinction (dev/deploy box = 780M; spec reference = 890M), not an error — but only the HANDOFF explains it; the README/ROADMAP state 780M without the reconciliation, and a reader cross-referencing the spec's 890M could think one is wrong.

**Why this matters.** Minor and arguably intentional. The numbers are honest; the gap is that the reconciliation lives only in the HANDOFF. Worth a one-line note in the README setup section so the spec/README difference reads as deliberate.

**Fix path.** Add a parenthetical to README:103: "(the dev/deploy target; the v3.0 spec's reference box is the 890M — KimCad targets the lower 780M floor)."

---

### Nits

- **DOC-N1 (Nit · Tone).** HANDOFF.md is a 480-line wall of dense, deeply-nested status prose. It's accurate and load-bearing, but a new maintainer's "where do I resume?" answer is buried. Consider a 5-line "Resume here" box at the very top. Not a defect.
- **DOC-N2 (Nit · Accuracy).** README:149 labels the Web UI section "(Phase 2, early)" while the same doc elsewhere uses the repo's Stage numbering. Harmless legacy label; align to Stage vocabulary on next pass.
- **DOC-N3 (Nit · Consistency).** `docs/` mixes a `guide-my-designs.md` (current, user-facing) with several stage-directive files (e.g. `stage-5-completion-directive-2026-06-02.md`, `stage-8.5-slice-5-onramps.md`) that are historical artifacts. They're not wrong, but a `docs/` index or an `archive/` subfolder for completed-stage directives would keep the user-doc surface clean. Cleanup, not correctness.

---

## Drafts produced

None. All findings are short-fix or banner-add; no doc is broken badly enough to require a `doc-rewrites/` replacement. The two Majors are a pointer-fix (DOC-001) and a one-line superseding banner (DOC-002) — audit-only mode is the right call.

## Would any doc mislead a user or a future maintainer?

- **A first-time user:** No. The README, the My-Designs guide, the in-app glossary, and the config comments are accurate, honest, and free of overclaim. Nothing tells a user the product does something it doesn't, and the layer-viewer (the obvious overclaim risk) is honestly deferred everywhere.
- **A future maintainer:** Yes, in two specific places. (1) HANDOFF's "Backend API contract" block (DOC-001) would have them believe the Stage-8.5 endpoints don't exist. (2) docs/design/README.md (DOC-002) would point a wizard/photo-on-ramp build at the rejected Qwen model and a cloud-default-vision flow that violates the load-bearing local-only trust rule. Both are doc-lag, not product defects — the shipped code and the other docs are correct — but they're exactly the "the docs say X, the code does Y" trap that erodes trust on the next resume.
