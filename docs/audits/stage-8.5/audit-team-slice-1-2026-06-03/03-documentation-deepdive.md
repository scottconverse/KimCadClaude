# Documentation Deep-Dive — KimCad (Stage 8.5 Slice 1: persistence + "My Designs")

**Audit date:** 2026-06-03
**Role:** Technical Writer
**Scope audited:** `HANDOFF.md`, `ROADMAP.md`, `docs/stage-8.5-usability-plan.md`, `docs/design/KimCad-Unified-Product-Spec-v3.0.md` (Addendum B), `docs/design/README.md` (Stage 8.5 addendum), the three Slice-1 `audit-lite` reports under `docs/audits/stage-8.5/`, and the inline docstrings in `src/kimcad/design_store.py`, `src/kimcad/config.py`, and the new `src/kimcad/webapp.py` "My Designs" endpoints. Cross-checked against the code that shipped on branch `stage-8.5-usability` (HEAD `657bc3b`) and against the real test counts. Repo README/CHANGELOG/ARCHITECTURE reviewed for the front-door status claim.
**Writer mode:** audit-only (no drafts produced)
**Auditor posture:** Balanced

---

## TL;DR

The Stage 8.5 docs are honest about status and largely accurate: **nothing** claims Slice 1 or Stage 8.5 is done / merged / tagged / shipped — every "merged + tagged" claim correctly belongs to Stages 4–7, and the plan, HANDOFF top, spec Addendum B and design README all state Stage 8.5 is **in progress** with 8 slices to go. The spec addenda describe the feature that actually shipped (local-first `~/.kimcad/designs` persistence, the My Designs library, export/import `.kimcad`, search/sort). The two real problems are an **internal contradiction inside ROADMAP.md** — its "Current baseline" paragraph still says "Next = Stage 8 (CadQuery)" and omits Stage 8.5 entirely, contradicting the same file's own Stage 8.5 "IN PROGRESS" section — and **one stale/self-inconsistent test count in the backend-persistence `audit-lite` report** (claims `14 + 67 = 75`; the files actually held `12 + 56` at that commit, and 14+67 isn't 75). Two smaller inline-doc inaccuracies round it out (a `duplicate()` docstring describing a "caller stamps a new created_at" contract no caller fulfills). No Blockers, no Critical. The missing user-facing manual for this feature is a fair watchlist item, not a gap to hold the slice on at this mid-stage altitude.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 4 |
| Nit | 1 |

## What's working

- **Status honesty is clean across the board.** A grep for "Slice 1 … done/merged/tagged/shipped" returns nothing; every "merged to `main` and tagged" line in `HANDOFF.md` (lines 22, 86, 94, 100) and `ROADMAP.md` (lines 52, 55, 138, 180, 183) is correctly attached to Stages 4–7. `HANDOFF.md:1` ("Stage 8.5 (Usability) IN PROGRESS"), `ROADMAP.md:208` ("🔧 IN PROGRESS"), spec Addendum B ("RATIFIED … executed BEFORE the CadQuery parallel backend"), and the design README addendum all consistently mark 8.5 as in-flight. This is the exact discipline the orchestrator's hard-lesson check demands, and it held.
- **The spec addenda match what was built.** Spec Addendum B and the design-README addendum describe local-first persistence, a "My Designs" library, reopen/auto-save/restore, a per-design URL, export/import, and units/settings/on-model-problems as *future* slices — and the persistence + library + export/import + search/sort that actually shipped in Slice 1 is faithfully scoped as Slice 1. The design README is careful to separate "build to THIS prototype where it exists" (VersionRail, FirstRunWizard, ModelPicker, raycast) from "new surfaces this prototype did NOT cover" (My Designs library, full Settings, units, on-model highlighting) — an accurate reading of the prototype.
- **The most recent `audit-lite` (export/import) is count-accurate.** Its final line ("`test_design_store.py` 16 + `test_webapp.py` 59 = 75 passed; `npm run test` 56 passed") matches reality exactly: I collected 16 + 59 = 75 python tests and ran them green, and vitest reports 56 passed across 8 files. The frontend-mydesigns report's counts (`test_webapp.py` 57, vitest 52/8 files) are also accurate *at that report's commit* (`94b6ce2`) — verified by checking the files out at that SHA.
- **The audit-lite reports don't overclaim their own gate.** Each says the Slice-1 `audit-team` "runs next" — none claims audit-team passed (correct: the `audit-team-slice-1-2026-06-03/` dir is empty until this run). The "verified live" claims (captured PNG thumbnail, `#/design/<uuid>` URL, hard-refresh restore, export 200 `application/zip` round-trip) are specific and consistent with the code paths (`_handle_design_save`, `_handle_design_reopen`, `App.tsx` restore effect, `_serve_design_export`).
- **The store/config docstrings are mostly precise and load-bearing-accurate.** `design_store.py`'s module docstring ("never the repo … any read/write failure degrades rather than ever breaking a build … Writes are serialized + atomic"), the `_read_zip_member` "bounded decompression read … a zip bomb can't inflate to gigabytes" claim, the `import_bytes` "zip-slip safe: only the three known files … the archive's own paths are never used" claim, and `config.py`'s `designs_path()` "defaults to `~/.kimcad/designs/` … never land in the repo" all describe the real behavior I read in the code. These are exactly the safety claims that must be true, and they are.

## What couldn't be assessed

- **The live "verified" artifacts in the audit-lite reports** (e.g. "a real captured thumbnail (PNG, 10.5 KB)", "export … 2905 bytes (live)") are point-in-time runtime captures; I confirmed the code paths that produce them and ran the full test suites green, but I did not re-drive the running browser to reproduce the exact byte sizes. The QA/UX deep-dives in this audit-team package own the live re-drive; from a docs-accuracy standpoint these claims are internally consistent and plausible.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md (repo front door) | Yes | Adequate — but stops at Stage 7; no mention of persistence / My Designs | DOC-004 |
| ROADMAP.md | Yes | Strong overall, but self-contradicting "Current baseline" para | DOC-001 |
| HANDOFF.md | Yes | Strong — accurate Stage 8.5 framing | — (credited) |
| docs/stage-8.5-usability-plan.md | Yes | Strong — accurately scopes Slice 1 as delivered | — (credited) |
| Spec Addendum B (v3.0 spec) | Yes | Strong — matches build | — (credited) |
| Design README Stage 8.5 addendum | Yes | Strong — matches build + prototype | — (credited) |
| audit-lite — backend persistence | Yes | Adequate — wrong/self-inconsistent test count | DOC-002 |
| audit-lite — frontend My Designs | Yes | Strong — count-accurate at its commit | — |
| audit-lite — export/import | Yes | Strong — count-accurate against current code | — |
| CHANGELOG.md | Yes | Adequate — `[Unreleased]` stops at Stage 7; no Slice-1 entry | DOC-004 |
| Inline docstrings (design_store / webapp) | Yes | Strong, with two local inaccuracies | DOC-003, DOC-005, DOC-006 |
| User manual / guide for My Designs | No | Missing — fair at this mid-stage | DOC-004 (watchlist) |

---

## Persona walk-through

### First-time user
The repo README still presents KimCad as a Stage-7 product (`README.md:12` "Status: **early development**" then a feature list ending at Smart Mesh readiness, "*Stage 7 — done*"). A first-time user reading the front door would not learn that their work now persists or that a "My Designs" library exists — but they also won't be *misled* into expecting a feature that isn't there. At this altitude (mid-stage, unmerged branch) the under-description is acceptable; the overclaim direction (the dangerous one) is absent.

### Returning user
There is no user-facing help for the new persistence/library surface yet — no doc explains where designs are stored (`~/.kimcad/designs`), what `.kimcad` export files are, or how reopen/restore works. The in-app UI copy (empty states, "Importing…", inline rename) carries this for now, which is reasonable for a mid-stage slice. A returning *developer* is well served: `design_store.py`'s module docstring is an excellent orientation to the store's contract.

### New team member
A new engineer is well oriented. `HANDOFF.md` accurately frames Stage 8.5, the slice sequence, and "RESUME HERE = Stage 8.5, Slice 1"; the plan doc enumerates every slice's punch list; the design README points at the exact prototype components to build to. The one trap is DOC-001: a new engineer who reads ROADMAP's "Current baseline" paragraph first could come away believing Stage 8 (CadQuery) is next, directly contradicting the resume instruction everywhere else.

---

## Findings

> **Finding ID prefix:** `DOC-`
> **Categories:** Accuracy / Completeness / Onboarding / Architecture / API / FAQ / Marketing / Tone / Hygiene

### [DOC-001] — Major — Accuracy (internal contradiction) — ROADMAP "Current baseline" says Stage 8 is next and omits Stage 8.5

**Evidence**
`ROADMAP.md:56` (inside the "Current baseline (honest, as of Stage 4)" section): **"Next = Stage 8 (CadQuery)."** The immediately following sentence, `ROADMAP.md:58–61`, lists what's "Still ahead before beta: CadQuery (Stage 8), image on-ramp (Stage 9), direct-print UI + Bambu-native (Stage 10), and the Windows installer + beta gate (Stage 11)" — **Stage 8.5 is absent entirely.** This directly contradicts the same file's own authoritative Stage 8.5 section at `ROADMAP.md:208–224` ("🔧 IN PROGRESS … executed BEFORE the Stage 8 CadQuery backend (8.5-first, ratified 2026-06-03)"), plus `HANDOFF.md:1,5`, spec Addendum B, and the design README addendum — all of which say 8.5 comes first and is in progress.

**Why this matters**
This is the precise "one truth per doc" failure mode `HANDOFF.md:375–377` records as a load-bearing lesson (Scott caught HANDOFF+ROADMAP self-contradicting after the Stage-4 merge). A new team member or Scott himself, reading the baseline paragraph first, is told the next thing to build is CadQuery — the opposite of the ratified 8.5-first decision and the "RESUME HERE = Stage 8.5" instruction everywhere else. A roadmap that says two different "next" things is no longer a reliable source of truth.

**Blast radius**
- Other docs that repeat the same error: none — this is isolated to ROADMAP's stale baseline paragraph; HANDOFF, the plan, and the spec addenda are all correct. The fix is to update *only* `ROADMAP.md:56` and the `:58–61` "Still ahead" list to insert Stage 8.5 ahead of Stage 8 (and re-point "Next =" to Stage 8.5).
- User-facing: none (internal planning doc); the risk is misdirected engineering effort.
- Migration: none.
- Related findings: none with the same root; this is a doc-sync miss from inserting 8.5 into a numbered plan.

**Fix path**
In `ROADMAP.md`, change `:56` from "Next = Stage 8 (CadQuery)." to "Next = Stage 8.5 (Usability), then Stage 8 (CadQuery)." and add Stage 8.5 to the "Still ahead" enumeration at `:58–61`. Small edit; restores single-truth.

---

### [DOC-002] — Minor — Accuracy (stale/self-inconsistent count) — backend-persistence audit-lite cites a wrong, non-additive test count

**Evidence**
`docs/audits/stage-8.5/audit-lite-slice-1-backend-persistence-2026-06-03.md:59` (the re-audit/resolution line): "Verified: ruff clean; `test_design_store.py` 14 + `test_webapp.py` 67 + `test_config.py` = 75 passed; no regression." Two problems: (1) **the arithmetic is broken** — 14 + 67 = 81, already over the stated 75 before `test_config.py` is even added; (2) **the per-file numbers are wrong for that commit** — checking the test files out at the backend-remediation SHA `13584ea` collects `test_design_store.py` = **12** and `test_webapp.py` = **56**, not 14 and 67. (At current branch HEAD the files are 16 and 59 — also not 14/67.) The other two Slice-1 audit-lites are count-accurate (verified), so this is an isolated transcription error, not a pattern.

**Why this matters**
This is exactly the class of stale-count error the audit process is primed to catch (the past "667 vs 668" miss). The report's *verdict* of 0/0/0/0/0 is not undermined — the tests do pass — but a verification line whose own numbers don't add up and don't match the files erodes trust in the report as evidence. An auditor or Scott cross-checking the count would find it doesn't reconcile.

**Fix path**
Correct the line to the real counts at that commit (`test_design_store.py` 12 + `test_webapp.py` 56 + `test_config.py` <n> = <correct total> passed), or restate it as the simple "the persistence tests pass green" without an unreconciled per-file breakdown. Recommend citing counts only for files actually run and ensuring they sum.

---

### [DOC-003] — Minor — Accuracy (docstring misdescribes behavior) — `duplicate()` claims "the caller stamps" a new created_at; no caller does

**Evidence**
`src/kimcad/design_store.py:210–212` — `duplicate()`'s docstring: "Copy a saved design under `new_id` … with its name suffixed '(copy)' and **a new created_at left to the caller via the copied meta (the caller stamps)**." The method body (`:215–227`) copies the meta tree, re-keys `id`, and suffixes the name — it does **not** touch `created_at`. The only caller, `webapp.py:982–985` (`_handle_design_mutate`, duplicate branch), calls `store.duplicate(design_id, new_id)` and returns; it never stamps a created_at. I confirmed empirically: duplicating a design with `created_at` `2020-01-01T00:00:00+00:00` yields a copy whose `created_at` is still `2020-01-01T00:00:00+00:00` (name correctly becomes "Orig (copy)"). So the documented contract ("the caller stamps") is unfulfilled, and a duplicate sorts in the library at the *original's* timestamp rather than at the top.

**Why this matters**
A docstring that describes a contract no code honors will mislead the next engineer (e.g. someone debugging why a freshly-duplicated design doesn't appear newest-first will trust the docstring and look in the wrong place). The user-visible effect — a duplicate not sorting to the top of the gallery — is minor and was not flagged by the frontend audit-lite. The behavior may even be intentional (a copy keeping its source's date), in which case it's the docstring that's wrong, not the code.

**Fix path**
Either (a) correct the docstring to state that `created_at` is preserved from the source (if that's the intended behavior), or (b) if a duplicate *should* surface as new, have the caller (`_handle_design_mutate`) stamp a fresh `created_at` after `duplicate()` returns, and keep the docstring. Recommend (a) unless a product decision says duplicates should sort to top — this is a UX/product call, not just a doc fix.

---

### [DOC-004] — Minor — Completeness — repo README + CHANGELOG don't reflect Slice 1 (no user-facing doc for persistence / My Designs)

**Evidence**
`README.md:12–18` still reads "Status: **early development**" with a feature list that ends at Smart Mesh readiness ("*Stage 7 — done; tagged `stage-7`.*") — no mention of persistence, the My Designs library, export/import, or `~/.kimcad/designs`. `CHANGELOG.md:7–18` (`[Unreleased]`) stops at Stage 7 with no Stage-8.5 / Slice-1 entry. Neither was touched on the branch (`git diff main...stage-8.5-usability -- README.md CHANGELOG.md ARCHITECTURE.md` returns nothing). There is no user manual or guide explaining where designs are stored, what a `.kimcad` file is, or how reopen/restore behaves.

**Why this matters**
A returning user has no front-door signal that their work now persists or that a library exists. This is an *under*-description, not an overclaim — the safe direction — and the project's documented process pushes README/CHANGELOG/ARCHITECTURE updates to **stage end** (the Stage-7 pattern: docs land in the final slice before audit-team → merge → tag, per `HANDOFF.md:79`). Stage 8.5 is mid-flight with 8 slices left, so deferring the front-door + changelog + user-manual write to stage end is consistent with the established cadence. Flagging at Minor/watchlist, not Critical: a polished user manual is not owed at this altitude.

**Blast radius**
- Other docs affected: `ARCHITECTURE.md` will also need a "My Designs store" entry at stage end (the new `design_store.py` module + the `/api/designs*` endpoints).
- User-facing: returning users lack discovery of persistence until in-app UI carries it (it does, for now).
- Related findings: none.

**Fix path**
No action required *this slice*. Add to the next-sprint watchlist: at Stage 8.5 stage end, update README's status block + feature list, add a `CHANGELOG.md` Stage-8.5 "Added" section, extend `ARCHITECTURE.md` with the store + endpoints, and write the user-facing "My Designs / saving your work / export-import" guide. Confirm this matches the Stage-7 docs-at-stage-end pattern (it does).

---

### [DOC-005] — Minor — Accuracy (docstring scope drift) — `printproof3d_binary()` and a few config docstrings say "Stage 7" where the file now also serves Stage 8.5

**Evidence**
`src/kimcad/config.py` is internally consistent and accurate (`designs_path()` at `:139–148` correctly says "Stage 8.5" and "`~/.kimcad/designs/`"). This is a low-severity observation only: the `config.py` module docstring (`:1–6`) predates Stage 8.5 and enumerates "binary paths, API keys via env, model choice" without the new `paths.designs` key it now also resolves. Not wrong, just not refreshed.

**Why this matters**
Trivial drift; the typed accessor's own docstring is correct, so no one is misled in practice. Noted for the stage-end hygiene pass.

**Fix path**
At stage end, add `paths.designs` to the `config.py` module-level summary alongside `paths.history`. Nit-adjacent; batch with other hygiene.

---

### [DOC-006] — Nit — Accuracy — `_handle_design_save` comment says "current" mid-sentence as a stray word

**Evidence**
`src/kimcad/webapp.py:886–888` — the inline comment "so adjusting a part and re-saving keeps one library entry, current); otherwise mint a fresh id." The word "current" before the close-paren reads as a leftover edit fragment; the sentence parses cleanly without it.

**Why this matters**
Purely cosmetic; doesn't change meaning. Flagged once, not belabored.

**Fix path**
Drop the stray "current". Batch with the stage-end hygiene pass.

---

## Drafts produced

Writer mode is **audit-only**; no drafts produced in this pass. All gaps are flagged as findings above.

## Marketing / honesty audit

No marketing or landing copy is in scope for this slice. The one front-door honesty surface — `README.md` — is *under*-claiming (stops at Stage 7), which is the safe direction. No overclaim of Stage 8.5 capability anywhere. The spec Addendum B's framing ("a real user abandons the product on contact") is candid about the gaps the stage fixes rather than puffery. Honesty posture across the Stage 8.5 docs is strong.

## Patterns and systemic observations

- **Status discipline held; count discipline slipped once.** The hard-won "never claim done/merged/tagged early" rule is fully observed across all six in-scope docs. The weaker spot is *count* precision: one of three audit-lites carries an unreconciled test count (DOC-002). Recommend a one-line standard for audit-lite resolution sections: cite only files actually run, and ensure the per-file numbers sum to the stated total.
- **Insert-a-stage doc-sync risk.** DOC-001 is the classic hazard of slotting "8.5" into a numbered plan: most docs were updated, but one stale "next = Stage 8" paragraph survived inside ROADMAP. When a stage is inserted, grep every doc for the old "next" target as part of the change.
- **Docstrings are generally excellent and safety-accurate** — the zip-slip, bounded-read, never-raises, and local-first claims all hold against the code. The two inaccuracies (DOC-003, DOC-005) are localized scope/contract drift, not a systemic problem.
- **Docs-at-stage-end is a deliberate, consistent cadence** (Stage 7 precedent), so the README/CHANGELOG/ARCHITECTURE/user-manual gap (DOC-004) is expected mid-stage, not a process miss — provided it's actually closed at the stage gate.

## Appendix: docs reviewed

- `C:\Users\scott\dev\kimcad\HANDOFF.md`
- `C:\Users\scott\dev\kimcad\ROADMAP.md`
- `C:\Users\scott\dev\kimcad\docs\stage-8.5-usability-plan.md`
- `C:\Users\scott\dev\kimcad\docs\design\KimCad-Unified-Product-Spec-v3.0.md` (Addendum B)
- `C:\Users\scott\dev\kimcad\docs\design\README.md` (Stage 8.5 addendum)
- `C:\Users\scott\dev\kimcad\docs\audits\stage-8.5\audit-lite-slice-1-backend-persistence-2026-06-03.md`
- `C:\Users\scott\dev\kimcad\docs\audits\stage-8.5\audit-lite-slice-1-frontend-mydesigns-2026-06-03.md`
- `C:\Users\scott\dev\kimcad\docs\audits\stage-8.5\audit-lite-slice-1-export-import-2026-06-03.md`
- `C:\Users\scott\dev\kimcad\src\kimcad\design_store.py` (docstrings)
- `C:\Users\scott\dev\kimcad\src\kimcad\config.py` (docstrings)
- `C:\Users\scott\dev\kimcad\src\kimcad\webapp.py` (new "My Designs" endpoint docstrings/comments)
- `C:\Users\scott\dev\kimcad\README.md` and `C:\Users\scott\dev\kimcad\CHANGELOG.md` (front-door status check)
- Cross-checks: `git diff/log main...stage-8.5-usability`; live test collection + runs (`pytest` 75 passed, `vitest` 56 passed); historical counts at SHAs `13584ea` and `94b6ce2`; empirical `duplicate()` created_at behavior.
