# 03 — Documentation Deep-Dive — Stage 8.5 Slices 2–4

**Role:** Technical Writer (audit-only — no rewrites; findings flag inaccuracies/gaps)
**Date:** 2026-06-03
**Scope:** Branch `stage-8.5-usability` @ `2ea65e9`. Batch =
`git diff d56b251..HEAD -- ":(exclude)docs/audits" ":(exclude)src/kimcad/web/assets"`
(Slices 2–4: conversation thread + refine, version timeline/undo/compare, numeric editing, mm/inch units).
**Docs reviewed:** `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `HANDOFF.md`, `ARCHITECTURE.md`,
`docs/stage-8.5-usability-plan.md`, `docs/guide-my-designs.md`; plus in-app user-facing copy in
`frontend/src/components/{ChatPanel,RightPanel,VersionRail}.tsx`, `frontend/src/App.tsx`,
`frontend/src/api.ts`, `frontend/src/useUnits.ts`.
**Posture:** balanced.

---

## Bottom line (for the orchestrator)

**No doc falsely claims Stage 8.5 or Slices 2–4 are done, merged, or tagged.** Every reference to
this work across all five narrative docs is correctly hedged ("in progress on branch
`stage-8.5-usability` — not yet merged or tagged"). The `git tag` list stops at `stage-7`,
confirming nothing in 8.5 is tagged. The DOC-CONSISTENCY hard requirement passes.

The findings are about **plan-doc staleness** (the plan still reads Slices 2–4 as open work despite
them being implemented, while Slice 1 was given a ✅ DONE marker — an inconsistency the project's own
"one truth per doc" lesson flags) and **plan-vs-build completeness gaps** (two 🔴 items in the
Slice-4 / Slice-3 punch lists — inch *input* parsing and "units everywhere incl. readiness + slice
estimate" — are not in this batch). The in-app copy is honest and accurate: it describes only
behavior that is actually wired.

The absent CHANGELOG / README / ARCHITECTURE / user-manual entries for the Slices 2–4 UX are
**intentionally batched to the Stage-8.5 close** (matching the Slice-1–3 cadence) — noted as a
stage-close watch item, not a this-sprint drift finding.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 2 |
| Nit | 1 |
| **Total** | **4** |

---

## Findings

### DOC-001 (Major) — Accuracy / Completeness — Plan doc reads Slices 2–4 as still-open while they are implemented; Slice 1 is marked DONE but 2–4 are not

**Evidence:** `docs/stage-8.5-usability-plan.md`
- Line 34: `## Slice 1 — Persistence + "My Designs" … — ✅ DONE (on branch \`stage-8.5-usability\`; \`audit-team\` + two re-audits → 0/0/0/0/0; pending Scott's approval)`
- Line 44: `## Slice 2 — Iterative refinement (the "conversation" actually works)` — **no status marker**
- Line 52: `## Slice 3 — Direct editing & numeric control` — **no status marker**
- Line 59: `## Slice 4 — Units (mm **and** inches)` — **no status marker**

Slices 2–4 are demonstrably implemented in this batch (commits `767dac1`, `295e653`, `6a8387a`,
`2112d72`, `44d7c2d`, `2ea65e9`; the conversation thread + refine input in `ChatPanel.tsx`,
`VersionRail.tsx`, numeric editing + the mm/in toggle in `RightPanel.tsx`, `useUnits.ts`). The plan
doc gives Slice 1 a precise ✅ DONE header but leaves 2–4 unmarked, so a reader can't tell that 2–4
are built-and-pending-gate vs not-yet-started. The two states read identically.

**Why this matters (new team member / returning reader):** the plan doc is the project's punch-list
source of truth (it's named as such in HANDOFF.md and ROADMAP.md). An unmarked slice that is in fact
built is exactly the "says X in one place, Y in another" failure the project's own load-bearing
lesson calls out — HANDOFF.md §7: *"One truth per doc. A handoff/roadmap that says 'done' in one
place and 'still ahead' in another is a process miss."* Here the miss is the inverse: built work
reading as not-built. It also makes the eventual stage-close bookkeeping harder (which slices got
their gate?).

**Note on altitude / posture:** the plan is a forward-looking design doc, and the project batches
narrative-doc updates to stage close — so the *absence* of CHANGELOG/README entries for 2–4 is fine
(see "Batched-doc watch item"). What's flagged here is narrower and real: the plan **already started**
marking slice status (Slice 1) and then stopped, creating an internal inconsistency *within the same
document*. Either mark 2–4 with the same "implemented on branch, pending stage gate" status it gave
Slice 1, or defer all per-slice status to stage close — but don't mark one and not the others.

**Fix path:** add a status line to the Slice 2/3/4 headers mirroring Slice 1's, e.g.
`— 🔧 IMPLEMENTED on branch \`stage-8.5-usability\`, pending the stage gate` (and reflect any
deferred sub-items, see DOC-002/DOC-003). Keep "pending gate" wording so it never reads as
merged/tagged.

**Blast radius:**
- Adjacent docs: none repeat the per-slice status (ROADMAP.md line 212–228 describes Stage 8.5 at
  the stage level and lists the slices as a plan, without per-slice done-markers — internally
  consistent on its own). The inconsistency is contained to `stage-8.5-usability-plan.md`.
- User-facing: none — this is an internal planning doc.
- Migration: none.
- Tests to update: none.
- Related findings: DOC-002, DOC-003 (the sub-items that are *not* built and should be reflected if
  the slices are marked implemented).

---

### DOC-002 (Minor) — Accuracy — Slice-4 punch list promises "inch input" parsing + prompt-understands-inches; only a display-unit toggle was built

**Evidence:** `docs/stage-8.5-usability-plan.md` lines 59–64:
- Line 61: `🔴 **A units preference (mm/inch), persisted**, applied **everywhere** — sliders, the dims table, size, bbox, readiness, the slice estimate.`
- Line 62: `🔴 **Inch input** — accept "2in", "2.5", and common fractions on entry; the prompt understands it too ("a 2-inch cube").`

What this batch actually built (`useUnits.ts`, `RightPanel.tsx`):
- A display-unit preference (mm/in) persisted in `localStorage` and applied to the **sliders +
  bbox** (Parameters card, `RightPanel.tsx:289`) and the **Printability dims table**
  (`RightPanel.tsx:462–472`). The numeric editor accepts a plain number *in the active display
  unit* and converts back to mm.
- **No "2in" / fraction string parsing** on entry (the numeric `<input type="number">` takes a bare
  number; `useUnits.ts` only does arithmetic mm↔in conversion — no unit-suffix or fraction parser).
- **No prompt-path inch understanding** in this batch — `webapp.py` / the LLM plan path are
  untouched for unit parsing (the Slice-4 audit-lite itself states *"Backend is untouched and stays
  mm-only"*, `docs/audits/stage-8.5/audit-lite-slice-4-units-2026-06-03.md`).
- "Applied everywhere … readiness, the slice estimate" is **partial**: the Readiness card and the
  slice estimate are not unit-converted (no `useUnits` use there).

**Why this matters:** a reader using the plan doc to judge what Slice 4 delivers would over-read the
🔴 inch-input and "everywhere" promises as shipped. **Importantly, this is a plan-doc-vs-build gap,
not a dishonest user-facing claim** — no shipped user doc or in-app string asserts inch input or
inch-aware readiness/estimate (the in-app placeholder deliberately uses mm, see "What's working").
So the user is never misled; only the internal plan over-states this batch's coverage.

**Fix path:** if the slices are marked implemented per DOC-001, annotate the deferred sub-items —
e.g. mark "Inch input parsing (2in / fractions / prompt)" and "readiness + slice-estimate unit
coverage" as **deferred within Slice 4** (or split to a later polish slice). Don't silently leave
them under an "implemented" header.

**Blast radius:**
- Adjacent code: a future inch-input parser would touch the numeric `<input>` in `RightPanel.tsx`
  and, for prompt understanding, the plan/LLM path (`ir.py` / prompts) — not in scope here.
- User-facing: none changed by the doc fix.
- Migration: none.
- Related findings: DOC-001, DOC-003.

---

### DOC-003 (Minor) — Accuracy — Slice-3 punch list promises a way to edit AI-generated (non-template) parts; this batch added numeric entry for template sliders + a refine-via-conversation path, not editable dimensions on LLM parts

**Evidence:** `docs/stage-8.5-usability-plan.md` lines 52–57:
- Line 53: `🔴 **A way to adjust AI-generated (non-template) parts** — today they're fully read-only … At minimum: editable key dimensions that re-render; ideally promote more parts to parametric.`

What this batch built for non-template (LLM) parts: the Parameters card hint (`RightPanel.tsx:294–301`)
now points the user to the **conversation refine input** ("type an exact change like *make it 10mm
taller*… and a new version will appear") — i.e. a *re-design via the model* path, wired and honest
(see "What's working"). The numeric-entry work (commit `44d7c2d`) added inline typing to the
**template** sliders, not to LLM parts. There are still **no editable key dimensions on an LLM part**
that re-render without a model round-trip — which is what the Slice-3 🔴 line literally specifies ("at
minimum: editable key dimensions that re-render").

**Why this matters:** the refine-via-conversation route is a legitimate (and well-copy'd) answer to
"AI parts are unusable," but it is a different mechanism than the plan's 🔴 wording ("editable key
dimensions that re-render"). A reader checking the plan against the build would mark this 🔴 as met
when the literal sub-requirement (local editable dims on LLM parts) is not. Again: **the in-app copy
is honest** — it promises a *new version* via the conversation, not a local edit — so no user is
misled. The gap is plan-text precision.

**Fix path:** reconcile the Slice-3 🔴 wording with the chosen approach — either restate it as
"adjust AI parts via the conversation refine input (a new version), with local editable dimensions
deferred," or explicitly carry "editable key dimensions on LLM parts" forward as not-yet-done.

**Blast radius:**
- Adjacent code: local-editable-dims-on-LLM-parts would be a real feature (extracting parametric
  handles from an LLM result) — sizeable, out of this batch's scope.
- User-facing: the current hint copy is accurate as-is; no change needed there.
- Related findings: DOC-001, DOC-002.

---

### DOC-004 (Nit) — Tone/Accuracy — "Compare two versions side-by-side" (plan) vs the summary-only compare card actually built

**Evidence:**
- `docs/stage-8.5-usability-plan.md` line 49: `🟠 **Compare two versions** side-by-side.`
- Built: `ChatPanel.tsx` `CompareCard` renders a two-column **summary** card —
  `v{a} → v{b}`, each column showing the plan summary, the gate status, and the readiness score
  (`ChatPanel.tsx:19–48`). It is a side-by-side *summary diff*, not a side-by-side 3D/geometry
  comparison.

**Why this matters (low):** "side-by-side" could be read as a dual-viewport geometry compare; the
build is a side-by-side metadata/summary card. The VersionRail's own comment is precise — *"Compare
shows a summary diff card in the thread"* (`VersionRail.tsx:3`) — so the code is honest; only the
one-line plan bullet is loose. Minor enough to be a Nit.

**Fix path:** if the plan slices are annotated (DOC-001), tighten the bullet to "Compare two
versions (a side-by-side summary: plan, gate, readiness)" so expectation matches delivery.

---

## Batched-doc watch item (stage-close, NOT a this-sprint finding)

The user-facing surfaces for Slices 2–4 are **intentionally not yet written**, matching the cadence
used for Slices 1–3 (Slice 1 got its CHANGELOG/README/guide entries; 2–4 are held for the stage
close). Specifically, at stage close the following will need entries so the docs stop trailing the
product:

- **CHANGELOG.md** `[Unreleased]` → `### Added`: a Stage 8.5 Slice 2/3/4 block (conversation thread
  + refine, version timeline/undo/compare, numeric editing, mm/inch toggle), kept under
  `[Unreleased]` and worded "on branch … not yet merged/tagged" until the stage is tagged. (Today
  the only 8.5 entry is Slice 1, CHANGELOG.md:23 — correctly hedged.)
- **README.md** — the "Saving your work" subsection (line 45) is Slice-1-only; a short "Refining a
  part / versions / units" note belongs here at stage close (or in the user guide).
- **ARCHITECTURE.md** — "The web layer" documents Slice-1 saved-designs (lines 178–188) but not the
  `history`-threaded `/api/design` follow-up, the version model, or the units display layer; add at
  stage close.
- **docs/guide-my-designs.md** (or a sibling user-manual page) — no walkthrough yet for refine /
  versions / units. A returning-user "how do I change a part / switch to inches" answer is currently
  absent.

This is flagged so it isn't forgotten at the gate; it is **not** counted as a Slices-2–4 drift
finding (the batched cadence is a deliberate, stated process choice).

---

## What's working (credit where due)

**The DOC-CONSISTENCY hard requirement passes cleanly.** Every Stage-8.5 reference is honest and
hedged, and this is not accidental — it's the project's hard-won "tag advanced to the docs-DONE
commit" discipline applied consistently:

- `README.md:16–17` — *"Stage 8.5 (Usability) is in progress on branch `stage-8.5-usability` — not
  yet merged or tagged."* Slice 1 explicitly labeled *"in progress, on branch"* (line 45).
- `CHANGELOG.md:14–17` — Stage 8.5 *"IN PROGRESS … not yet merged or tagged; Slice 1 … is
  implemented and pending its stage-gate approval."* All "merged + tagged" claims in the file are
  for Stages 5/6/7 only, which the `git tag` list confirms are real.
- `ROADMAP.md:59–60` — *"Stage 8.5 is currently IN PROGRESS on branch `stage-8.5-usability` …
  nothing in it is merged or tagged yet."* The Stage 8.5 section (212) carries the
  `🔧 IN PROGRESS (branch `stage-8.5-usability`)` banner.
- `HANDOFF.md:1,5` — title and ⛔-READ-FIRST both state 8.5 IN PROGRESS on the branch, Stage 7 done.
- The `CHANGELOG` `[Unreleased]` section correctly **retains** all 8.5 work (the only 8.5 entry,
  Slice 1, sits under `[Unreleased]`); nothing is prematurely cut into a tagged release block.

**The in-app copy is honest and matches wired behavior** — the standout strength of this batch:

- The LLM-part hint (`RightPanel.tsx:296–301`) — *"use the conversation on the left: type an exact
  change like 'make it 10mm taller' … and a new version will appear"* — describes a **real, fully
  wired** path: `postDesign(prompt, history)` (`api.ts`) → `_sanitize_history` + `pipeline.run(…,
  history=history)` (`webapp.py`) → `generate_design_plan(…, history=…)` /
  `generate_openscad(…, history=thread)` (`pipeline.py:339,720`), and a new version is pushed on any
  `has_mesh` result (`App.tsx` `runDesign`). The promise "a new version will appear" is literally
  true.
- The refine placeholder (`ChatPanel.tsx:158–161`) is context-aware and honest: it shows
  *"Answer the question above…"* when the model asked a clarifying question, and
  *"Refine your part — 'make it 10mm taller', 'add mounting holes'…"* otherwise. It correctly uses
  **mm** examples (not inches it can't parse), so it never implies inch-input that doesn't exist.
- The Parameters card sub-line was updated honestly from *"Drag a slider"* to *"Drag or click a
  value to type — the part re-renders locally, no AI round-trip"* (`RightPanel.tsx`), matching the
  new numeric-entry capability.
- Error/empty copy is plain and recoverable: the failed-design hint *"No part was produced, so
  there's nothing to adjust. Try describing it a little differently on the left."*
  (`RightPanel.tsx:304–306`).
- ARIA/labels on the new controls are accurate to behavior: VersionRail's *"Undo to previous
  version"* / *"Redo to next version"* / *"Compare the two most-recent versions"*
  (`VersionRail.tsx`), the unit toggle's `aria-label="Display units"`, and the numeric input's
  range-aware title/aria.

**Code comments are unusually precise and non-aspirational** — they consistently describe what the
code does, including honest caveats (`VersionRail.tsx:3` *"Compare shows a summary diff card"*;
`useUnits.ts` header explaining why an external store avoids the drift bug; `webapp.py`
`_sanitize_history` *"never raise … behaves like a fresh turn"*). This is the right altitude for
maintainer docs and made this audit fast and verifiable.

---

## Method note

Verified the merged/tagged claims against `git tag` (stops at `stage-7`) and the batch commit range
(`d56b251..2ea65e9`, six Slice-2/3/4 commits). Traced the in-app hint copy end-to-end through
`api.ts` → `webapp.py` → `pipeline.py` to confirm the refine/version behavior the copy promises is
actually wired, rather than taking the strings at face value. The nested `CivicSuite-*` tree under
the repo root was excluded (unrelated to KimCad). No OneDrive paths touched.
