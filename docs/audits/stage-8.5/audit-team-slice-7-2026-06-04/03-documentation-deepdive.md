# 03 — Documentation Deep-Dive — Stage 8.5 Slice 7 ("describe with a photo" on-ramp)

**Role:** Technical Writer · **Mode:** AUDIT-ONLY (flag, don't rewrite) · **Posture:** Balanced
**Date:** 2026-06-04 · **Branch:** `stage-8.5-usability` · **Diff under review:** `76c6f89..HEAD` (commits `c6778d1` MS-1 backend, `39b9b09` MS-2 UI)
**Repo:** `C:\Users\scott\dev\kimcad` (working tree clean; nothing uncommitted)

## Scope & method

Read in full: `HANDOFF.md`, `README.md`, `CHANGELOG.md`, `ROADMAP.md`, `ARCHITECTURE.md`,
`docs/design/stage-8.5-slice-5-onramps.md` (the approved Surface D design), `docs/stage-8.5-usability-plan.md`
(the slice plan), and the two committed Slice 7 audit-lite reports. Paired every Slice-7 claim with the
actual code in the diff: `llm_provider.describe_photo`, `webapp._handle_photo_seed` /
`_SettingsAwareProvider.describe_photo` / `DemoProvider.describe_photo`, `src/kimcad/prompts/system_photo_seed.md`,
`frontend/src/components/PhotoOnramp.tsx`, `frontend/src/api.ts`, `Landing.tsx`, `ChatPanel.tsx`.

**Headline:** The Slice-7 *code-level* documentation — every inline docstring, comment, prompt, and
user-facing string — is **accurate and honest**. There is no over-promise, no "photo → finished part"
claim, no implication the photo leaves the machine. The HONESTY bar (the load-bearing concern for this
slice) is **met**. All findings are in the **project-level prose docs** (CHANGELOG / README / HANDOFF /
ROADMAP / usability-plan) that Slice 7 did not touch, leaving them describing a project state one to six
slices behind reality. None blocks the slice, but two are Major staleness/contradiction items the team
should clear at the stage-end doc pass.

Diff confirms Slice 7 changed **zero** doc files — only `docs/audits/stage-8.5/audit-lite-slice-7-*` and
code/tests. So every prose-doc staleness below is a sin of omission at the Slice-7 boundary, consistent
with the "full doc polish is later" convention — but the two Major items predate good single-source-of-truth
hygiene the project itself codified (HANDOFF §7: "One truth per doc").

## Severity rollup

- Blocker: 0
- Critical: 0
- Major: 2
- Minor: 3
- Nit: 1
- **Total: 6**

No premature "done / merged / tagged / released / shipped" claim about Slice 7 or Stage 8.5 exists in any
doc — VERIFY #1 passes. CHANGELOG correctly keeps everything under `[Unreleased]` and untagged. The
problem is the inverse: the docs *under-report* progress and contradict each other on *which* slice is current.

---

## Findings

### DOC-001 — Major — Accuracy / Completeness — CHANGELOG `[Unreleased]` is frozen at Slice 1; Slices 2–7 are entirely missing

**Evidence:** `CHANGELOG.md:14-17` (the `[Unreleased]` preamble):
> "**Stage 8.5 (Usability) is IN PROGRESS on branch `stage-8.5-usability` — not yet merged or tagged;** Slice 1 (local persistence + the "My Designs" library) is implemented and pending its stage-gate approval."

And the only Stage-8.5 entry in the `### Added` section is `CHANGELOG.md:23-37` — "Stage 8.5 Slice 1 — local persistence…". There is **no** CHANGELOG entry for Slice 2 (refinement + version history), Slice 3 (numeric editing), Slice 4 (units), Slice 6 (Settings + cloud opt-in + experimental toggle), or **Slice 7 (the photo on-ramp under audit)**. The commit log (`git log --oneline`) and the committed audit artifacts (`docs/audits/stage-8.5/audit-team-slice-2-4-…`, `…-slice-6-…`, the two `…-slice-7-…` audit-lites) prove all of those slices are built and gated on this branch.

**Why this matters:** The CHANGELOG is the canonical "what changed" record (its own header cites Keep a Changelog). A reader — or the eventual `0.1.0` release-notes author who accumulates these `[Unreleased]` sections — would conclude Stage 8.5 added *only* persistence, silently dropping refinement, numeric entry, units, the entire Settings screen, the cloud opt-in, the experimental generator, **and the photo on-ramp**. That's six slices of user-facing capability invisible in the change record. The "Slice 1 … pending its stage-gate approval" line is now affirmatively false: Slice 1 already cleared its `audit-team` (`docs/audits/stage-8.5/audit-team-slice-1-2026-06-03`).

**Blast radius:**
- Adjacent docs repeating the same stale "Slice 1" framing: `README.md:16-20` and `:45-53` (DOC-002), `HANDOFF.md:18-23` (DOC-003).
- Migration: none. Doc-only.
- Related findings: DOC-002, DOC-003, DOC-004 — all share the root cause "the per-slice builds didn't update the project-level prose docs, only the audit folder."
- Recommended grouping: a single stage-end CHANGELOG pass that adds the Slice 2/3/4/6/7 entries (the audit-lite reports + slice headers are accurate source text) is cheaper than six separate edits.

**Fix path:** At the Slice-7 (or stage-end) doc pass, add `[Unreleased]` `### Added` sub-entries for Slices 2, 3, 4, 6, 7 and correct the preamble to name the current slice. For Slice 7 specifically: "Stage 8.5 Slice 7 — 'describe with a photo' on-ramp: a secondary affordance reads a photo with gemma4:e4b's **local** vision into a rough, editable text seed that pre-fills the existing text→DesignPlan path; the photo is never persisted, never logged, and never auto-sends off the machine; a photo carries no scale, so sizes are estimates."

---

### DOC-002 — Major — Accuracy — README "Saving your work" + status banner state only Slice 1 is in progress; the camera on-ramp the user now sees is undocumented and the banner is stale

**Evidence:**
- `README.md:16-19` (status banner): "**Stage 8.5 (Usability) is in progress on branch `stage-8.5-usability` — not yet merged or tagged:** local-first persistence and a "My Designs" library now keep your work between sessions…" — names *only* persistence.
- `README.md:45` (section header): "### Saving your work *(Stage 8.5 Slice 1 — in progress, on branch)*" — labels Slice 1 as the live in-progress edge, when Slice 7 is.
- The README never mentions units (Slice 4), the in-app Settings screen / cloud opt-in (Slice 6), or the **photo on-ramp** (Slice 7) — yet the running SPA now shows a "📷 Describe with a photo" affordance on the landing screen (`Landing.tsx:71-72`) and in the workspace (`ChatPanel.tsx:246-248`). A first-time reader of the README who opens the app meets a feature the front door never mentioned.

**Why this matters:** README is the front door and the honesty surface the Writer role weighs most. The banner isn't *false* about persistence, but it's materially incomplete — it implies persistence is the sum of Stage 8.5 progress, when five further slices (including a whole Settings screen and a new input on-ramp) are built on the branch. The "Slice 1 — in progress" tag is now wrong (Slice 1 is gated; Slice 7 is the in-progress edge). Per the project's own "don't over- or under-state capability" posture, under-stating still misleads.

**Blast radius:**
- Adjacent: CHANGELOG (DOC-001), HANDOFF (DOC-003) carry the same Slice-1-centric framing.
- User-facing: the README is the install/first-run path; a reader forms an inaccurate mental model of what the branch build does.
- Migration: none.
- Note: the README link at `:53` to `docs/guide-my-designs.md` is **valid** — that file exists and is tracked (verified via `git ls-files`). No dead link.

**Fix path (stage-end):** Update the `:16-19` banner to name the current slice edge and the on-ramps surface generally ("…persistence, units, an in-app Settings screen, and a local-vision 'describe with a photo' on-ramp are on the branch"). Either retag the `:45` section "(Stage 8.5 — in progress, on branch)" without pinning it to Slice 1, or add a short "Describe with a photo" subsection. Do **not** add a full end-user photo guide now — mid-stage, a one-line honest mention suffices (matches the project's deferral convention).

---

### DOC-003 — Minor — Accuracy — HANDOFF resume pointer is one slice stale (says Slice 6 is "at its slice-end gate" and resume = Slice 7; Slice 6 is gated, Slice 7 is built and at *its* gate)

**Evidence:** `HANDOFF.md:1` dates the doc "2026-06-03". `HANDOFF.md:18-23`:
> "**RESUME HERE = Stage 8.5, Slice 7 (photo on-ramp).** Slices 1–6 are built on branch `stage-8.5-usability` and audit-lite-gated 0/0/0/0/0 (Slices 2–4 also passed the full audit-team + wiring-audit; **Slice 6 — the Settings screen — is at its slice-end gate**)…"

Reality on the branch as of 2026-06-04: Slice 6 has **completed** its `audit-team` (`docs/audits/stage-8.5/audit-team-slice-6-2026-06-04/` exists with a `REMEDIATION.md`), and Slice 7 (MS-1 backend + MS-2 UI) is **built** (commits `c6778d1`, `39b9b09`), audit-lite-gated (the two committed Slice-7 reports), and now *at* its own `audit-team` (this very audit, `audit-team-slice-7-2026-06-04`). So "RESUME HERE = Slice 7" is correct in spirit but "Slice 6 is at its slice-end gate" is stale, and the doc predates Slice 7 being built at all.

**Why this matters:** HANDOFF is the explicit cross-session source of truth (`HANDOFF.md:109`, §7 "the handoff/spec is the source of truth"). A resume pointer that lags the real branch state risks a future session re-doing Slice 6's gate or mis-judging where Slice 7 stands. Lower than Major because the top-line "resume at Slice 7" still lands on the right work, and a clean working tree means no in-flight loss — it's a status-freshness gap, not a misdirection.

**Blast radius:**
- Related: DOC-001, DOC-002 (same "docs lag the branch" root).
- Migration: none.

**Fix path:** Refresh the `:18-23` resume block to: "Slices 1, 2–4, and 6 are built and have each passed their `audit-team` (+ wiring-audit for 2–4); **Slice 7 (the photo on-ramp) is built (MS-1 backend + MS-2 UI), audit-lite-gated, and at its slice-end `audit-team` now.**" Bump the doc date.

---

### DOC-004 — Minor — Accuracy — The usability slice-plan marks Slices 1–4 DONE/IMPLEMENTED but leaves Slice 6 and Slice 7 with *no* status marker, despite both being built

**Evidence:** `docs/stage-8.5-usability-plan.md`:
- Slice 1 header `:34` — "✅ DONE (… `audit-team` + two re-audits → 0/0/0/0/0; pending Scott's approval)".
- Slices 2/3/4 headers `:44`, `:52`, `:59` — "✅ IMPLEMENTED (… pending the Slice 2–4 `audit-team` + `wiring-audit` gate …)".
- Slice 5 header `:66` — "(DESIGN ONLY — no code …)".
- **Slice 6 header `:79` — "## Slice 6 — Settings + engine discoverability (config files → in-app)"** — *no status marker at all.*
- **Slice 7 header `:89` — "## Slice 7 — Photo on-ramp ("describe with a photo")"** — *no status marker at all.*

Both Slice 6 and Slice 7 are built and gated on the branch (commit log + audit folders), yet read as not-started here, while the earlier slices carry explicit ✅ markers. The asymmetry makes the plan internally inconsistent about its own progress.

**Why this matters:** This is the doc a session reads to know "what's done vs. ahead." An unmarked built slice reads as future work; a reader could think Slice 6/7 haven't begun. Minor because the commit log and audit folders disambiguate, but the plan should be self-consistent.

**Blast radius:**
- Related: DOC-003 (HANDOFF), DOC-001/002 (CHANGELOG/README) — the same slices are under-reported across all four.
- Migration: none.

**Fix path:** Add a status marker to the Slice 6 (`:79`) and Slice 7 (`:89`) headers matching the others — e.g. Slice 6 "✅ IMPLEMENTED (… `audit-team` → 0/0/0/0/0; pending Scott's approval)"; Slice 7 "✅ IMPLEMENTED (MS-1 backend + MS-2 UI; audit-lite-gated; at the slice-end `audit-team`)".

---

### DOC-005 — Minor — Architecture — ARCHITECTURE module map and web-layer section don't yet mention the photo on-ramp (the `describe_photo` method, `/api/photo-seed`, and the Settings/cloud endpoints from Slice 6)

**Evidence:**
- `ARCHITECTURE.md:76` (the `llm_provider.py` row): "Two jobs: `generate_design_plan` and `generate_openscad`." The module now has a **third** public job — `describe_photo` (`llm_provider.py:238-282` in the diff), the local-vision photo→seed read. The "Two jobs" count is now strictly inaccurate.
- The web-layer section (`ARCHITECTURE.md:133-188`) inventories the JSON endpoints (`/api/design`, `/api/slice/<id>`, `/api/render/<id>`, `/api/designs*`, `/api/connectors`, …) but does not mention `POST /api/photo-seed` (added `webapp.py:871-873`, handler `:1147-1168`), nor the Slice-6 `/api/settings` surface or the `_SettingsAwareProvider` cloud/local routing that the photo path's local-only guarantee depends on.

**Why this matters:** ARCHITECTURE is the new-engineer orientation doc. The "Two jobs" line will actively mislead someone counting the provider's surface; the missing endpoint means a reader mapping the API contract won't find the photo route. This is the kind of "outdated count / signature" the Writer methodology calls a Major-when-it-blocks / Minor-otherwise — here it's Minor: it misleads on detail but doesn't block setup, and the project's convention is to fold the architecture update into the stage-end doc pass.

**Blast radius:**
- Adjacent: a new `webapp.py` row or web-layer paragraph would also be the natural home for the Slice-6 `/api/settings` + cloud-opt-in description, which is *also* absent (a pre-existing Slice-6 gap, surfaced here, not introduced by Slice 7).
- Migration: none.
- Note on the load-bearing privacy invariant: the *code* documents it correctly (`webapp.py:369-374` docstring — "Vision is ALWAYS local — the photo never auto-sends, even when cloud TEXT is enabled"), so the trust property is captured where it's enforced; ARCHITECTURE just doesn't echo it yet.

**Fix path (stage-end):** Change `:76` to "Three jobs: `generate_design_plan`, `generate_openscad`, and `describe_photo` (local-vision photo→seed)." Add a sentence to the web-layer section: "`POST /api/photo-seed` reads an uploaded photo with the **local** vision model into a rough text seed (never persisted, never auto-sent); `_SettingsAwareProvider.describe_photo` always builds a dedicated local provider, so the photo path is unreachable from the cloud-TEXT routing." Optionally add a `describe_photo`/photo-on-ramp note to the module map.

---

### DOC-006 — Nit — Tone/Consistency — `system_photo_seed.md` uses "millimetres" (British spelling) while the rest of the prose docs use US "millimeter"/"mm"

**Evidence:** `src/kimcad/prompts/system_photo_seed.md:4`: "Estimate rough sizes in **millimetres** only…". The README, ROADMAP, ARCHITECTURE, and CHANGELOG consistently use "mm" or US "millimeter." The target audience is explicitly a US maker (`docs/stage-8.5-usability-plan.md:59` Slice 4 — "a US maker isn't walled out").

**Why this matters:** Purely cosmetic — the model will read it fine and the user never sees this prompt. Flagged once for voice consistency; not worth a workflow item. (No blast radius — Nit.)

**Fix path:** Optional: change "millimetres" → "millimeters" (or "mm") if a copy pass is touching the file anyway. Do not open an edit solely for this.

---

## What's working (credit where due)

The Slice-7 documentation is, at the code/UX-copy altitude, a model of honest writing. Specifics worth keeping:

- **The honesty bar is fully met — no over-promise anywhere.** Every user-facing string frames the photo as a *rough, editable starting point*, never a finished part, and never implies the photo leaves the machine:
  - `PhotoOnramp.tsx:158` "A rough starting point"; `:159` "Read locally — your photo never left your machine"; `:146-147` "Your photo stays on your computer … It never leaves your machine"; `:171-173` "A photo can't tell us scale, so any sizes are estimates. Adjust anything, then continue." This is exactly the approved Surface-D copy (`docs/design/stage-8.5-slice-5-onramps.md:127-152`) and exactly the trust rule (`:55-59`).
- **The inline docstrings are accurate and load-bearing-correct.** `llm_provider.describe_photo`'s docstring (diff, `llm_provider.py:238-247`) correctly explains the native-`/api/chat` + `think:false` choice, that the seed is "ROUGH proportions (a photo carries no scale)," and that it "never becomes the delivered geometry … the same trust boundary as typed text." `webapp._handle_photo_seed`'s docstring states the never-500 / nothing-persisted / never-auto-sent guarantees that the code actually implements. `_SettingsAwareProvider.describe_photo`'s docstring names the single most important property of the slice — "Vision is ALWAYS local … even when cloud TEXT is enabled" — right where it's enforced. The referenced helpers (`_load_prompt`, `build_constraints_block`) both exist (verified).
- **Stale-comment hygiene was handled correctly on refactor — the exact failure the Writer methodology warns about.** `Landing.tsx`'s prior comment said "The photo on-ramp is a later stage and is intentionally absent"; Slice 7 **replaced** it (diff, `Landing.tsx:3-6`) with an accurate description rather than leaving the contradiction. `DemoProvider.describe_photo`'s comment (`webapp.py:279-280`) reads "The image is ignored; the fixed seed stands in" — note this already fixed the inaccuracy the MS-1 audit-lite flagged as Nit PHOTO-002, so that finding is **closed** and is correctly **not** re-raised here.
- **The system prompt is well-aimed and honest** (`system_photo_seed.md`): "A photo carries NO scale… Never invent precise dimensions," "a STARTING POINT the user will refine and resize — not a final spec," and an explicit "if you can't make out a clear single object … say so" — it instructs the model toward exactly the honest framing the UI promises.
- **The API client comments mirror the server truth** (`api.ts:282-310` in the diff): the 12 MiB cap comment correctly notes it "mirrors webapp `MAX_PHOTO_BYTES`," and the header comment restates the local-only / never-auto-send property.
- **No premature-completion claim anywhere.** VERIFY #1 fully passes: searched all tracked `*.md` for done/shipped/merged/tagged/released against Slice 7 / Stage 8.5 — every Stage-8.5 mention is correctly qualified "in progress … not yet merged or tagged." CHANGELOG keeps it under `[Unreleased]`, untagged.
- **The README's `docs/guide-my-designs.md` link is valid** (file tracked), so no dead-link debt was introduced.

## Cross-role blast-radius note (for the orchestrator)

DOC-001/002/003/004 are four facets of **one** root cause: the per-slice builds (Slices 2–7) updated the in-repo **audit** artifacts but not the four project-level prose docs (CHANGELOG, README, HANDOFF, usability-plan). The cheapest fix is a single stage-end documentation pass that brings all four current in one coordinated edit — which the project's own process already schedules ("docs at stage end," HANDOFF §6) and its own lesson already demands ("One truth per doc," HANDOFF §7). None of these block the Slice-7 gate; they are the stage-end doc-debt line item. No Engineering/Test/QA finding is expected to share this root — it is purely a prose-doc-freshness cluster.
