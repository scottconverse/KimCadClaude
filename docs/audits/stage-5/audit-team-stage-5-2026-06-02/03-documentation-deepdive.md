# Documentation Deep-Dive — KimCad (Stage 5: deterministic template engine + live sliders)

**Audit date:** 2026-06-02
**Role:** Technical Writer
**Scope audited:** Stage 5 doc edits + the code they describe — `ARCHITECTURE.md` (tiered-engine intro, pipeline diagram, `templates.py` / `template_bench.py` module-map rows, live-sliders web-layer paragraph), `CHANGELOG.md` (Stage 5 subsection under `[Unreleased]`), `ROADMAP.md` (Stage 5 status + section), `README.md` (template-engine + live-slider mentions), `HANDOFF.md` (Stage 5 IN PROGRESS section), `docs/benchmarks/stage-5-template-families.md`. Cross-checked against `src/kimcad/templates.py`, `src/kimcad/webapp.py`, `src/kimcad/template_bench.py`, `src/kimcad/pipeline.py`, and live git state.
**Writer mode:** audit-only (no rewrites; inaccuracies/contradictions flagged as findings)
**Auditor posture:** Balanced

---

## TL;DR

The four user/architecture-facing docs that describe Stage 5 — `ARCHITECTURE.md`, `CHANGELOG.md`, `ROADMAP.md`, `README.md` — are accurate, internally consistent, and honest. Every load-bearing technical claim I checked against the code holds: the seven family names and count, the `POST /api/render/<id>` shape, the versioned/cache-busted `mesh_url`, the slice/G-code invalidation, "no model call," and the benchmark numbers all match the implementation. Critically for the Stage-4 lesson, **none of these four docs claims Stage 5 is done/merged/tagged** — ROADMAP and CHANGELOG correctly keep it "implemented on the branch / pending the stage gate" and under `[Unreleased]` with no `stage-5` tag (verified: the tag does not exist). The one serious problem is **`HANDOFF.md`, which is badly stale**: its title and body say "Slice 4 next / backend done," cite the wrong branch-head SHA (`1a0af61`), the wrong ahead-count (5), and two wrong test counts (404 and 470) — when the branch is actually at `91b691c`, 8 commits ahead, with Slices 4 *and* 5 committed and 484 tests collected. That is the exact "one truth per doc" failure HANDOFF itself warns against, recurring one stage later. Fix HANDOFF and the doc set is gate-clean.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **Stage-5 status discipline in ROADMAP and CHANGELOG is exactly right.** `ROADMAP.md:131-132` reads *"Status: implemented on `stage-5-template-engine` (Slices 1–5); pending the stage gate (audit-full → native Windows gate → merge → tag `stage-5`)."* `CHANGELOG.md:6-12` keeps Stage 5 under `[Unreleased]` and the top-of-section note tags only through `stage-1`; it never claims a `stage-5` tag. Verified against git: tags are `stage-0..stage-4` only, no `stage-5`. This is the Stage-4 "self-contradicting DONE banner" lesson correctly applied.
- **The headline performance claim is honest and well-hedged.** Docs say "well under a second" / "<1 s interactive target" and point to the committed proof. The proof file (`docs/benchmarks/stage-5-template-families.md`) shows the real measured numbers (0.133–0.453 s) *and* documents a separate 5 s automated gate ceiling, and `template_bench.py:44-48` matches: `RERENDER_TARGET_S = 1.0` (reported, not gated) vs `RERENDER_CEILING_S = 5.0` (the hardware-independent gate). No overclaim, and the looser CI gate is disclosed rather than hidden.
- **Every family name and the count of seven match the code.** `ARCHITECTURE.md:81`, `CHANGELOG.md:170-171`, `ROADMAP.md:135-136`, and `README.md` all list `snap_box, box, enclosure, tube, wall_hook, cable_clip, drawer_divider`; `templates.py:428` returns exactly those seven in that order. No drift.
- **The `/api/render` contract is described accurately in three places.** ARCHITECTURE's live-sliders paragraph (`ARCHITECTURE.md:159-167`), the CHANGELOG "Live re-render API" bullet (`CHANGELOG.md:181-185`), and the README slider mention all match `webapp.py:779-827`: deterministic re-render via `Pipeline.rerender` (no model), clamped values returned, a **versioned** `mesh_url` (`?v={next(version_counter)}`, line 826), cached slice/G-code **invalidated** (lines 820-822), and concurrent drags **serialized** under `render_lock` (line 806). "An LLM-backed part has no `parameters` and stays read-only" matches `webapp.py:790-793`.
- **"No model call" is verifiable, not just asserted.** ARCHITECTURE and CHANGELOG both say the benchmark *enforces* no-model by wiring a provider that raises; `template_bench.py:53-61` is exactly that `_NoModelProvider`. The injection-safety + byte-determinism claims map to `templates.py:191-197` (`emit_scad` is pure string substitution over `_fmt`-formatted finite numbers) and the clamping/ordering claims to `_clamp` / `_apply_gaps` / the tube `gaps=(("id","od",1.0),)` at `templates.py:374`.
- **The two new module-map rows are precise.** `ARCHITECTURE.md:81` (`templates.py`) and `:82` (`template_bench.py`) accurately describe the registry, the `ParamSpec` slider schema, analytic bbox, alias/collision handling, and the raises-if-called provider — all confirmed in source.
- **README front-door framing stays honest.** `README.md:13-18` keeps the status as "early development," scopes the slice proof to "software/profile validation, not yet a real print," and defers real-hardware to the final stage — correct and not flagged.

## What couldn't be assessed

- **Rendered browser screenshots of the live sliders.** This is a docs/text audit; the actual on-screen slider UX (desktop + mobile rendered checks) is the QA/UX role's deliverable and the per-slice UI rule, not something verifiable from the prose. The docs' *description* of the slider behavior was checked against the backend contract and the frontend bullet (`CHANGELOG.md:186-191`, naming `RightPanel.tsx`), but I did not render the SPA.
- **Whether the committed benchmark numbers reproduce on the gate box today.** I confirmed the table is internally consistent with `template_bench.py` and that the file exists and is cross-referenced correctly; I did not re-run `python -m kimcad.template_bench` to regenerate it.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md | Yes | Strong | — |
| ARCHITECTURE.md | Yes | Strong | DOC-005 (Nit) |
| ROADMAP.md | Yes | Strong | — |
| CHANGELOG.md | Yes | Strong | DOC-004 (Minor) |
| HANDOFF.md | Yes | Weak (stale) | DOC-001 (Major), DOC-002 (Minor), DOC-006 (Nit) |
| docs/benchmarks/stage-5-template-families.md | Yes | Strong | DOC-003 (Minor) |
| Cross-references to the benchmark file | Valid | OK — file present at the cited path | — |

---

## Persona walk-through

### First-time user (README)
Reads `README.md`, sees "deterministic template engine emits parametric OpenSCAD directly — no model," and the live-slider sentence with a pointer to the proof. Accurate, no broken setup step introduced by Stage 5. Succeeds. No Stage-5 finding.

### Returning user (CHANGELOG / ROADMAP)
Wants "what's new in Stage 5 and is it shipped?" CHANGELOG's Stage 5 subsection answers the *what* precisely and keeps it under `[Unreleased]`; ROADMAP answers *is it shipped* honestly ("pending the stage gate"). Both correct. The only place this persona is misled is if they open `HANDOFF.md` (DOC-001).

### New team member (HANDOFF / ARCHITECTURE)
This is where the docs fail. A contributor resuming from `HANDOFF.md` is told the backend is done and **Slice 4 is next**, to resume at head `1a0af61`, 5 ahead of main — all stale. Slices 4 and 5 are already committed; the head is `91b691c`, 8 ahead. A contributor trusting it would redo finished work or check out the wrong commit. ARCHITECTURE, by contrast, orients them correctly. → DOC-001.

---

## Findings

> **Finding ID prefix:** `DOC-`
> **Categories:** Accuracy / Completeness / Onboarding / Architecture / API / Tone / Hygiene

### [DOC-001] — Major — Accuracy — HANDOFF.md is stale: wrong stage progress, branch head, ahead-count, and test counts

**Evidence**
`HANDOFF.md` describes a state that predates the last two commits on the branch.

- Title (`HANDOFF.md:1`): *"Stage 5 IN PROGRESS, backend done, Slice 4 next"*.
- `:5-6`: *"resume on branch `stage-5-template-engine` (head `1a0af61`, 5 ahead of `main`, NOT merged/tagged). The whole BACKEND is done (Slices 1-3); NEXT = Slice 4 (the frontend live sliders)."*
- `:21`: *"Branch `stage-5-template-engine` @ `1a0af61`, 5 commits ahead of `main`"*.
- `:50`: *"**470 pytest passing**"*.
- `:10` and `:132`: *"404 tests passing"* / *"Tests: 404 passing"* (the Stage-4 baseline, left in the body).

Verified live git state contradicts all of these:
- Branch head is **`91b691c`** ("Stage 5 Slice 5: deterministic-template benchmark/proof + Stage 5 docs"), not `1a0af61`.
- The branch is **8 commits ahead** of `main`, not 5. The log shows Slice 4 (`74b3cee` "frontend live parameter sliders") and Slice 5 (`91b691c`) both committed after `1a0af61`.
- **484 tests collected** (`pytest --collect-only`), not 470 and not 404.
- So "backend done, Slice 4 next" is two slices behind reality — Slices 4 and 5 are done; the remaining work is the stage gate, not Slice 4.

**Why this matters**
The new-team-member persona resuming from HANDOFF (the doc that explicitly bills itself "Source of truth… Do NOT rebuild from memory," `:13`) would check out a stale commit, believe the frontend sliders are unbuilt, and risk re-doing Slice 4 or reporting wrong counts upward. This is precisely the "one truth per doc" lesson HANDOFF records from the Stage-4 merge (`:240-242`: *"A handoff/roadmap that says 'done' in one place and 'still ahead / fix all N' in another is a process miss"*) — recurring one stage later, now *across* docs (HANDOFF says Slice 4 next; ROADMAP says Slices 1–5 implemented).

**Blast radius**
- Other docs that repeat the same error: ROADMAP and CHANGELOG do **not** repeat it (they're current) — so the contradiction is HANDOFF-vs-the-rest, making HANDOFF the single stale node. The stale `404`/`470` counts are internal to HANDOFF (the count also appears at `:132`).
- User-facing: none (HANDOFF is a contributor doc). Onboarding/contributor-facing only.
- Migration: none — pure doc edit.
- Related findings: DOC-002 (HANDOFF's "Slice 4 next" pickup block is now obsolete), DOC-006 (the dated title).

**Fix path**
Update HANDOFF's Stage-5 section to the real state: head `91b691c`, 8 ahead of `main`, Slices 1–5 complete, **next = the stage gate (audit-team → fix → re-audit to 0/0/0/0/0 → native Windows gate → merge → tag `stage-5`)**. Replace both `404` and the `470` with the current count (484 collected; state the passing number from a full run). Single-source the count — ideally cite it once and reference it, so the Stage-4 double-count slip doesn't repeat.

---

### [DOC-002] — Minor — Accuracy — HANDOFF "Slice 4 pickup" block describes work already committed

**Evidence**
`HANDOFF.md:54-67` ("➡️ NEXT = Slice 4 (frontend live sliders) — the UI half. Exact pickup:") gives a step-by-step to *build* the live sliders in `RightPanel.tsx`, debounce a `POST /api/render/<id>`, etc. That work is committed in `74b3cee` ("Stage 5 Slice 4: frontend live parameter sliders"), and CHANGELOG (`:186-191`) already describes the sliders as shipped in `RightPanel.tsx`. Likewise `:68-70` frames Slice 5 (benchmark + docs) as still-to-come, but `91b691c` committed it and the benchmark file exists.

**Why this matters**
A contributor would follow a recipe for already-finished work. Lower severity than DOC-001 because it's the same root staleness; called out separately so the fix removes the obsolete instructions rather than just patching the header numbers.

**Blast radius**
- Related findings: DOC-001 (same root cause — HANDOFF not advanced after Slices 4–5 landed).

**Fix path**
Replace the Slice-4 and Slice-5 pickup blocks with the remaining gate steps; or fold both into a single "what's left = the stage gate" note.

---

### [DOC-003] — Minor — Accuracy — Benchmark proof's "Generated: 2026-06-02" predates its own file mtime / wording vs the date stamp

**Evidence**
`docs/benchmarks/stage-5-template-families.md:5` stamps *"**Generated:** 2026-06-02"*, but the committed file's mtime is 2026-06-01 (and it was committed in `91b691c`). The stamp is passed via `--date` (`template_bench.py:268,123-124`), so it's a hand-supplied label, not the actual generation timestamp. Minor: the *numbers* are the proof, and they're internally consistent; the date is cosmetic but slightly ahead of when the artifact was actually produced.

**Why this matters**
A reader auditing "when was this proof run?" gets a date that doesn't match the file's provenance. Trust-in-artifacts is a recurring theme in this project ("Artifacts outside VC can't prove when/how they were generated," `HANDOFF.md:259`); a mismatched self-reported date undercuts that, mildly.

**Blast radius**
- User-facing: none. Contributor/auditor-facing only.
- Related findings: none.

**Fix path**
Stamp the date the benchmark was actually generated, or drop the manual `--date` and let it reflect the run. Not gate-blocking.

---

### [DOC-004] — Minor — Tone/Hygiene — CHANGELOG Stage-5 benchmark bullet says "<1 s" as the proven bar while the gate certifies only ≤5 s

**Evidence**
`CHANGELOG.md:192-195`: *"every family re-renders through the real pipeline path watertight at its declared envelope, with no model call, in **well under the <1 s interactive target** — measured and recorded in `docs/benchmarks/stage-5-template-families.md`."* The benchmark *does* show every family under 1 s today (0.133–0.453 s), so this is accurate **for this run**. But the automated gate the proof asserts is the 5 s ceiling, not <1 s (`template_bench.py:48,80-88`). The phrasing "well under the <1 s interactive target" is true of the measurement but could read as if <1 s is the *enforced* contract.

**Why this matters**
Minor honesty nuance: a future slower box could keep the proof PASS-ing (≤5 s) while a family creeps over 1 s, at which point this bullet would read as overclaim. The benchmark file itself handles this correctly (separates "interactive target" from "gate ceiling"); the CHANGELOG bullet compresses it.

**Blast radius**
- Other docs: ARCHITECTURE/README say "well under a second" / "<1 s" too, but each points at the per-family proof, so they're anchored to the measured numbers. No fix needed there unless the numbers regress.
- Related findings: DOC-003 (same artifact).

**Fix path**
Optional: tweak to "measured at 0.13–0.45 s per family (interactive target <1 s; CI gate ≤5 s) — see the proof." Keeps the honest distinction the benchmark file already draws. Low priority.

---

### [DOC-005] — Nit — Architecture — ARCHITECTURE module-map intro count ("five original, five added") is a Stage-1 artifact unaffected by Stage 5

**Evidence**
`ARCHITECTURE.md:111` ("Ten `.scad` files in all — five original, five added"). Stage 5 added no `.scad` files (it builds on the existing library), so this is correct and *not* a Stage-5 regression. Flagged only because the Stage-5 template families lean on these modules and a reader cross-referencing `templates.py` `library_file` values (`containers.scad`, `box.scad`, `hooks.scad`, `clips.scad`, `organizers.scad`) will land here — and they all resolve correctly. Noting it as verified-clean, not broken.

**Why this matters**
No defect; included so the gate record shows the library cross-reference was checked and holds.

**Fix path**
None.

---

### [DOC-006] — Nit — Hygiene — HANDOFF dated title carries the now-stale "Slice 4 next" phase label

**Evidence**
`HANDOFF.md:1`: *"# KimCad — Handoff (2026-06-02 — Stage 5 IN PROGRESS, backend done, Slice 4 next)"*. The date is current but the phase label is wrong (see DOC-001). Pure header hygiene.

**Fix path**
Fold into the DOC-001 fix — retitle to the real phase ("Slices 1–5 complete, stage gate next").

---

## Marketing / honesty audit

No standalone marketing copy in the Stage-5 scope. The README hero and the ARCHITECTURE intro are the closest thing to value-prop copy, and both are honest: "deterministic template engine… no model," "well under a second," each anchored to the committed proof rather than left as a bare superlative. No overclaim, no unsubstantiated stat, no feature listed that isn't implemented. The "<1 s" phrasing nuance is captured at DOC-004 (Minor), not an overclaim today.

## Patterns and systemic observations

- **The user-facing trio (ARCHITECTURE / CHANGELOG / ROADMAP) and the README were updated together and are mutually consistent** — same seven family names, same `/api/render` contract, same honest status. That coordinated edit is the thing to keep doing.
- **HANDOFF is the lone lagging doc.** The recurring failure mode here is the *contributor* doc not being advanced when the *last* slice lands (it was updated mid-stage at `c005d24` "for a clean mid-stage resume," then Slices 4–5 landed after and it wasn't refreshed). The Stage-4 retro already named this exact pattern; the durable fix is to make "update HANDOFF head/count/next-step" part of the final-slice commit, and to single-source the test count so it can't drift in two places (it currently appears as `404` at `:10`/`:132` and `470` at `:50`).
- **No broken cross-references.** The benchmark file is cited from ARCHITECTURE, README, CHANGELOG, and ROADMAP, and it exists at exactly `docs/benchmarks/stage-5-template-families.md`. The audit dir `docs/audits/stage-5/` exists with all five slice audits.

## Appendix: docs reviewed

- `C:/Users/scott/dev/kimcad/ARCHITECTURE.md`
- `C:/Users/scott/dev/kimcad/CHANGELOG.md`
- `C:/Users/scott/dev/kimcad/ROADMAP.md`
- `C:/Users/scott/dev/kimcad/README.md`
- `C:/Users/scott/dev/kimcad/HANDOFF.md`
- `C:/Users/scott/dev/kimcad/docs/benchmarks/stage-5-template-families.md`

Code cross-checked: `src/kimcad/templates.py`, `src/kimcad/webapp.py` (`/api/render`, `_result_to_payload`), `src/kimcad/template_bench.py`, `src/kimcad/pipeline.py` (`rerender`, `PipelineResult`). Live state checked: `git rev-parse HEAD` (`91b691c`), `git rev-list --count main..HEAD` (8), `git tag` (no `stage-5`), `pytest --collect-only` (484 collected).
