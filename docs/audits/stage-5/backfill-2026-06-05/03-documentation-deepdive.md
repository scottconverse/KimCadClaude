# Documentation Deep-Dive — KimCad (Stage 5: deterministic template engine + live sliders) — BACKFILL

**Audit date:** 2026-06-05
**Role:** Technical Writer (independent, skeptical)
**Branch:** `stage-0-7-audit-backfill` (head `0aeae99`); Stage 5 merged to `main` and tagged `stage-5`.
**Scope audited:** the docs that describe Stage 5 (template engine + live sliders + units) against the
current code: `README.md` (template-engine + "live parameter sliders" + units claims, benchmark
reference), `ROADMAP.md` (Stage 5 section + exit criteria), `CHANGELOG.md` (Stage 5 subsection),
`docs/benchmarks/stage-5-template-families.md`, `ARCHITECTURE.md` (tiered-engine intro, pipeline,
`templates.py` / `template_bench.py` module rows, live-sliders web-layer paragraph), `docs/README.md`
(the docs index), and `docs/guide-my-designs.md` (the one shipped user guide). Cross-checked against
`src/kimcad/templates.py`, `src/kimcad/webapp.py` (`/api/render`, `_result_to_payload`,
`_readiness_payload`), `src/kimcad/template_bench.py`, `frontend/src/components/RightPanel.tsx`
(sliders + units), and live git state.
**Writer mode:** audit-only (no rewrites; a needed user-guide draft is recorded as a finding).
**Auditor posture:** skeptical / balanced.

---

## TL;DR

The architecture/changelog/roadmap/readme set that describes Stage 5 is **accurate, internally
consistent, and honest** — and the prior Stage-5 `audit-team` findings (DOC-001…DOC-006) have all
been remediated: `stage-5` is tagged, `HANDOFF.md`'s "Slice 4 next" staleness is gone, and the
benchmark file's hand-stamped `Generated:` date was removed. Every load-bearing technical claim I
re-checked against code still holds: the seven family names + count, the `POST /api/render/<id>`
contract (deterministic re-render, no model, clamped values, versioned/cache-busted `mesh_url`,
slice/G-code invalidation, serialized drags), the "gate/report/values update from server truth"
claim (`_result_to_payload` does return `report` + `readiness` + `parameters`), the "no model call"
enforcement (the `_NoModelProvider` that raises), and the benchmark numbers (all families
0.143–0.538 s, under the <1 s interactive target). No overclaim on performance — every "<1 s" /
"well under a second" mention is anchored to the committed per-family proof and the proof itself
separates the interactive target (1 s, reported) from the automated gate ceiling (5 s, enforced).

The real gap is **completeness, not accuracy**: Stage 5 shipped two headline *user-facing* features —
the live parameter sliders (with direct numeric entry) and the mm/inch units toggle — and **neither
has any user-facing how-to documentation**. The README advertises both ("live parameter sliders,"
"type exact numbers, switch between mm and inches") but there is no guide telling a user where the
sliders appear, that LLM-backed parts have none, how numeric entry / clamping behaves, or where the
units toggle lives. By contrast the *other* Stage 8.5 feature, "My Designs," got a polished
`docs/guide-my-designs.md`. The sliders are the marquee Stage-5 capability and the entire reason the
deterministic engine exists, so the missing guide is the highest-value doc debt here (DOC-101, Major).

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 2 |
| Nit | 1 |

## What's working (credit where due)

- **Performance honesty is exemplary.** `README.md:37-39`, `ARCHITECTURE.md:12-14`, and
  `CHANGELOG.md:286-288` all say "well under a second" / "well under the <1 s interactive target" and
  every one points at `docs/benchmarks/stage-5-template-families.md`. The proof file shows the real
  measured per-family numbers (0.143–0.538 s) and explicitly separates the 1 s interactive target
  from the 5 s automated-gate ceiling; `template_bench.py:44-48` matches (`RERENDER_TARGET_S = 1.0`
  reported vs `RERENDER_CEILING_S = 5.0` enforced). No bare superlative, no unsubstantiated stat.
- **"No model call" is verifiable, not asserted.** ARCHITECTURE and CHANGELOG both say the benchmark
  enforces no-model by wiring a provider that raises; `template_bench.py:53-61` is exactly that
  `_NoModelProvider`. The injection-safety + determinism claims map to `templates.py:193-199`
  (`emit_scad` is pure string substitution over `_fmt`-formatted finite numbers).
- **Seven family names + count match the code everywhere.** `ARCHITECTURE.md:84`, `CHANGELOG.md:263`,
  `ROADMAP.md:149-150`, and `README.md` all list `snap_box, box, enclosure, tube, wall_hook,
  cable_clip, drawer_divider`; `templates.py:444` returns exactly those seven in that order.
- **The `/api/render` contract is described accurately in three places.** ARCHITECTURE's live-sliders
  paragraph (`:179-187`), the CHANGELOG "Live re-render API" bullet (`:274-281`), and the README
  slider mention all match `webapp.py:1764-1849`: deterministic re-render via `Pipeline.rerender`
  (no model), clamped values returned, a **versioned** `mesh_url`, cached slice/G-code **invalidated**
  (`webapp.py:1837-1839`), concurrent drags **serialized** under `render_lock` (`:1798`), and
  geometry-version bump so a stale slice can't be served (`:1834`). "An LLM-backed part has no
  `parameters` and stays read-only" matches `webapp.py:1784-1785`.
- **Prior-audit remediation verified.** `git tag` now shows `stage-5`; `HANDOFF.md` no longer
  contains "Slice 4 next / backend done"; the benchmark file no longer carries a `Generated:` date
  stamp. DOC-001…DOC-006 from `audit-team-stage-5-2026-06-02/03-documentation-deepdive.md` are closed.
- **README front-door framing stays honest.** `README.md:13-24` keeps status "early development,"
  scopes the slice proof to "software/profile validation, not yet a real print," and defers
  real-hardware to the final stage. Stage-5 status is correctly "DONE — tagged `stage-5`."

## What couldn't be assessed

- **Rendered browser screenshots of the sliders / units toggle.** This is a docs/text audit; the
  on-screen UX (desktop + mobile rendered checks) is the QA/UX role's deliverable. The docs'
  *description* of slider + units behavior was checked against the backend contract and
  `RightPanel.tsx`; I did not render the SPA.
- **Live reproduction of the benchmark numbers on today's gate box.** I confirmed the table is
  internally consistent with `template_bench.py` and the file exists at the cited path; I did not
  re-run `python -m kimcad.template_bench`.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md (Stage-5 claims) | Yes | Strong | DOC-101 (the features it advertises lack a guide) |
| ARCHITECTURE.md | Yes | Strong | — |
| ROADMAP.md | Yes | Strong | — |
| CHANGELOG.md | Yes | Strong | DOC-103 (Nit) |
| docs/benchmarks/stage-5-template-families.md | Yes | Strong | DOC-102 (Minor) |
| docs/README.md (index) | Yes | OK | DOC-102 (Minor — overstates benchmark notes) |
| User guide for sliders / units | **No** | **Missing** | DOC-101 (Major) |
| guide-my-designs.md (reference precedent) | Yes | Strong | — (the model to follow) |

---

## Findings

> **Finding ID prefix:** `DOC-` (101+ to avoid collision with the prior Stage-5 audit's DOC-001…006).
> **Categories:** Accuracy / Completeness / Onboarding / Architecture / Marketing.

### [DOC-101] — Major — Completeness/Onboarding — No user-facing guide for the live sliders or the mm/inch units toggle, both advertised in the README

**Evidence**
The README advertises two Stage-5 user features with no accompanying how-to:
- `README.md:37-39`: *"the browser UI shows **live parameter sliders**: drag one and the part
  re-renders locally in well under a second…"*
- `README.md:20`: *"…type exact numbers, switch between mm and inches…"*

These are real and shipped — sliders + numeric entry + a mm/inch unit conversion live in
`frontend/src/components/RightPanel.tsx` (the `SliderRow`, `useUnits`, `toDisplay`/`fromDisplay`,
inch-step scaling at lines ~40-169). But there is **no** user-facing doc explaining any of it:
- `docs/` has a guide only for the *other* Stage 8.5 feature: `docs/guide-my-designs.md`. There is
  no `guide-sliders.md` / `guide-units.md` (`git ls-files "docs/guide-*.md"` → only `guide-my-designs.md`).
- `docs/guide-my-designs.md` *mentions* sliders only in passing ("its live sliders restored,"
  lines 16/36/62) — it never explains what they are, where they appear, that **LLM-backed parts have
  no sliders and stay read-only**, that values clamp to a printable range, how to type an exact value,
  or where the units toggle is.
- The README points the user at no slider/units guide (unlike the My Designs feature, which links
  `docs/guide-my-designs.md` from `README.md:57`).

**Why this matters**
The deterministic template engine *exists* to make instant live sliders possible (ROADMAP calls
Stage 5 "the critical path"); the sliders are the marquee user-facing payoff of the whole stage, and
units (mm/inch) is explicitly framed as "so a US maker isn't walled out" (`CHANGELOG.md:74-76`). The
**first-time user** who reads the README hero and opens the app gets no doc that tells them: only
template-backed parts have sliders (so a hand-typed prompt that falls to the LLM path will show none —
a confusing "where are my sliders?" moment with no answer in the docs); that dragging re-renders
locally with no model; that they can type an exact number; or where to switch to inches. The
**returning user** has no page to look up "how do I set inches?" The precedent (`guide-my-designs.md`)
shows the project's own bar for a shipped user feature — sliders + units fall below it.

**Blast radius**
- Adjacent docs: the My Designs guide is the template to mirror; a new sliders/units guide should be
  added to the `docs/README.md` "Current (read these)" list and linked from the README, exactly as
  `guide-my-designs.md` is.
- User-facing: affects every user of a template-backed part (the common path) and every non-metric
  user — i.e. the primary intended audience, not an edge case.
- Migration: none — additive doc.
- Tests to update: none.
- Related findings: none in this backfill; complements the UX role's slider-discoverability findings
  if any.

**Fix path**
Draft `docs/guide-sliders-and-units.md` (audit+draft recommended given Major severity), covering: where
sliders appear and that they only exist for template-backed designs (LLM parts are read-only), drag vs.
type-an-exact-value, the printable range clamp, the live re-render (no model, instant), and the mm/inch
toggle + that backend values stay mm. Add it to `docs/README.md` "Current" and link it from the README
near the slider sentence (mirroring the My Designs link).

---

### [DOC-102] — Minor — Accuracy — The docs index claims the benchmark notes cover "how to re-run them," but the Stage-5 benchmark file has no re-run instructions

**Evidence**
`docs/README.md:10`: *"**`benchmarks/`** — model + template benchmark notes (how to re-run them)."*
The Stage-6 file delivers on this (`docs/benchmarks/stage-6-model-bakeoff.md:1` is titled "…the
verdict + how to reproduce it"). The Stage-5 file does **not**: `docs/benchmarks/stage-5-template-families.md`
contains the results table and a verdict but no "how to re-run" line (grep for `re-run` / `python -m`
/ `regenerate` / `reproduce` → no matches). The actual invocation (`python -m kimcad.template_bench
[--write PATH]`) lives only in `ARCHITECTURE.md:85`, `CHANGELOG.md:284`, `ROADMAP.md:156`, and the
module docstring (`template_bench.py:16`) — not in the benchmark note the index points a reader to.

**Why this matters**
A contributor/auditor following the index to "re-run" the template benchmark lands on a file that
doesn't tell them how, and has to go hunt the command elsewhere. Minor: the command does exist and is
documented in three other places; this is an index-vs-artifact mismatch, not a broken capability.

**Blast radius**
- User-facing: none (contributor/auditor-facing).
- Related findings: none.

**Fix path**
Add a one-line "Re-run: `python -m kimcad.template_bench --write docs/benchmarks/stage-5-template-families.md`"
to the Stage-5 benchmark file (matching the Stage-6 file's "how to reproduce" section), or soften the
index wording for the Stage-5 entry. Prefer adding the line — it's the same fix the Stage-6 file already has.

---

### [DOC-103] — Nit — Marketing/Tone — CHANGELOG benchmark bullet still phrases "<1 s" as the bar while the enforced gate is ≤5 s

**Evidence**
`CHANGELOG.md:286-288`: *"…with no model call, **well under the <1 s interactive target** (the
automated gate asserts a conservative ≤5 s per-family ceiling…)."* This is the same nuance the prior
audit raised as DOC-004 (Minor) and is *accurate today* — every family is sub-second and the
parenthetical already discloses the 5 s gate, so the honest distinction is preserved. Re-noting it only
as a Nit because the lead phrase "well under the <1 s interactive target" still reads, at a glance, as
if <1 s is the enforced contract; the benchmark file itself draws the cleaner line ("Targets: re-render
under 1s (interactive); automated gate ceiling 5s"). No action required unless the numbers ever regress.

**Why this matters**
No defect today; flagged so the gate record shows the performance-claim wording was re-checked and
holds. The parenthetical disclosure keeps it from being an overclaim.

**Fix path**
Optional: align the lead phrase with the benchmark file's "measured 0.14–0.54 s; interactive target
<1 s; CI gate ≤5 s." Low priority.

---

## Marketing / honesty audit

No standalone marketing copy in scope. The README hero and ARCHITECTURE intro are the closest to
value-prop copy and both are honest: "deterministic template engine… no model," "well under a second,"
each anchored to the committed per-family proof rather than left as a bare superlative. No feature is
listed that isn't implemented; the units and slider claims are true (the gap is the *missing guide*,
DOC-101, not a false claim). The "<1 s" phrasing nuance is captured at DOC-103 (Nit), not an overclaim.

## Patterns and systemic observations

- **The architecture/changelog/roadmap/readme quartet remains mutually consistent and code-true** —
  same seven families, same `/api/render` contract, same honest "<1 s / ≤5 s" split. The coordinated
  edit discipline the prior audit praised has held through merge + tag.
- **The doc debt is asymmetric across Stage 8.5/Stage 5 user features:** "My Designs" got a full user
  guide; the sliders and units (the *headline* Stage-5 payoff) got none. The durable fix is to treat a
  user-facing feature guide as part of the shipping bar — the My Designs guide is the in-repo model.
- **No broken cross-references.** The benchmark file is cited from ARCHITECTURE, README, CHANGELOG,
  ROADMAP and exists at exactly `docs/benchmarks/stage-5-template-families.md`. The `guide-my-designs.md`
  link from the README resolves.

## Appendix: docs reviewed
- `C:/Users/scott/dev/kimcad/README.md`
- `C:/Users/scott/dev/kimcad/ROADMAP.md`
- `C:/Users/scott/dev/kimcad/CHANGELOG.md`
- `C:/Users/scott/dev/kimcad/ARCHITECTURE.md`
- `C:/Users/scott/dev/kimcad/docs/README.md`
- `C:/Users/scott/dev/kimcad/docs/benchmarks/stage-5-template-families.md`
- `C:/Users/scott/dev/kimcad/docs/benchmarks/stage-6-model-bakeoff.md` (precedent for re-run notes)
- `C:/Users/scott/dev/kimcad/docs/guide-my-designs.md` (precedent for a user-feature guide)
- `C:/Users/scott/dev/kimcad/docs/audits/stage-5/audit-team-stage-5-2026-06-02/03-documentation-deepdive.md` (prior findings — verified remediated)

Code cross-checked: `src/kimcad/templates.py`, `src/kimcad/webapp.py` (`_handle_render`,
`_result_to_payload`, `_readiness_payload`, `_report_payload`), `src/kimcad/template_bench.py`,
`frontend/src/components/RightPanel.tsx` (sliders + `useUnits`). Live state: `stage-5` tag present;
`HANDOFF.md` "Slice 4 next" removed; benchmark `Generated:` stamp removed.
