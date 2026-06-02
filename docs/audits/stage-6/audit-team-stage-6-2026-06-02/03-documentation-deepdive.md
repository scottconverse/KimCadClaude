# 03 — Documentation Deep-Dive — KimCad Stage 6 (model layer)

**Role:** Technical Writer (audit-team)
**Date:** 2026-06-02
**Branch:** `stage-6-model-swap` (head `96033c2`)
**Mode:** Audit-only (flag + evidence + fix path; no rewrites)
**Posture:** Balanced

## Scope

The Stage 6 documentation edits and the docs that must stay consistent with them:
`ARCHITECTURE.md`, `CHANGELOG.md`, `ROADMAP.md`, `HANDOFF.md`,
`docs/benchmarks/stage-6-model-bakeoff.md`, `bench/prompts.yaml` (header), `README.md`, and the five
per-slice `audit-lite` reports under `docs/audits/stage-6/`. Cross-checked against the code:
`model_advisor.py`, `bakeoff.py`, `llm_provider.py`, `benchmark.py`, `cli.py`, `config/default.yaml`,
`pipeline.py`.

---

## Severity rollup

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 4 |
| Minor | 3 |
| Nit | 2 |
| **Total** | **10** |

No Blocker. One **Critical**: the Stage 6 bake-off hand-off doc still frames the model swap as an open
question and shows a worked example in which Qwen *wins* and the tool recommends switching to it — the
exact opposite of the actual, settled verdict (Qwen rejected 0/10; gemma stays). That doc is the single
public artifact whose whole subject is the Stage 6 decision, and it currently teaches the reader the
wrong outcome.

The good news up front: the **load-bearing accuracy checks pass**. No doc claims Stage 6 is
merged/tagged; CHANGELOG correctly keeps it under `[Unreleased]`; ARCHITECTURE's module table accurately
describes every new/changed module against the actual code; and the headline verdict (`qwen 0/10`,
`gemma4:e4b` 8/10 completed / 4/10 graded, KEEP default) matches the committed `output/bakeoff/bakeoff.txt`
artifact in CHANGELOG, ROADMAP, and the HANDOFF body. The failures are concentrated in two stale files
(the bake-off doc and parts of HANDOFF) and a not-updated-for-Stage-6 README.

---

## Findings

### DOC-001 (Critical) — Accuracy — The Stage 6 bake-off doc still presents the swap as open and shows Qwen *winning*; the actual verdict (Qwen rejected, gemma stays) is nowhere in it

**Evidence:** `docs/benchmarks/stage-6-model-bakeoff.md`

- Title (`:1`): "Stage 6 — Model bake-off (Qwen vs gemma): **how to run the live comparison**".
- `:3`: "The Stage 6 model swap **asks whether** `qwen2.5-coder:1.5b` **should replace** `gemma4:e4b` as the default local model. The decision is **evidence-driven**: run the Phase-1 benchmark with each model and compare them..."
- `:6-7`: "The harness (`kimcad bakeoff`) is built and tested; **the live run needs a box with Ollama and both models pulled — that's this hand-off.**"
- The worked "Reading the result" example (`:60-66`) shows:
  ```
  local_qwen     qwen2.5-coder:1.5b     10/10     9/10    10/10   9/10   8/10     61.0
  Recommendation: SWITCH default to local_qwen -- ... (3-axis graded rate 9/10 vs 8/10) ...
  ```
  i.e. an illustrative table in which Qwen completes 10/10, grades 9/10, is ~2.3× faster, and the tool **recommends switching to it**.

The actual committed result (`output/bakeoff/bakeoff.txt`, run live 2026-06-02) is the inverse:
```
local_qwen     qwen2.5-coder:1.5b          0/10    0/10    0/0    0/0    0/0      0.0
local (def)    gemma4:e4b                  8/10    4/10   9/10   5/10   8/10    595.7
Recommendation: KEEP default local -- the incumbent local (gemma4:e4b) is already the best.
```

Every other current doc (CHANGELOG `:30`, ROADMAP `:18-20` / `:156-176`, HANDOFF body `:9-12` / `:65-70`)
states the verdict plainly. This doc — the one whose entire subject is the bake-off decision — never does.

**Why this matters:** This is the canonical doc-accuracy failure: the document materially misrepresents
the outcome of the work it documents. A reader (the returning engineer, a reviewer, or future-Scott)
who opens the file named for the Stage 6 decision is told the decision is still pending *and* shown an
example in which the rejected model is the winner. The illustrative numbers aren't labelled as
hypothetical strongly enough to survive a skim, and they happen to invert reality — the highest-cost
kind of stale doc. It also still calls the live run "this hand-off," contradicting HANDOFF/ROADMAP, which
record that the live run was already done on this box (the "needs a better box / hand-off" assumption was
explicitly corrected).

**Blast radius:**
- Adjacent code: none (doc-only).
- Adjacent docs: HANDOFF `:70` points to this file as "Hand-off doc (how to re-run it live)" — re-frame both together. The "keep gemma as the non-China alternative **and the vision fallback**" line (`:82`) is shared with the HANDOFF "vision fallback" phrasing (DOC-008).
- Migration: none.
- Tests to update: none. (Note: the Slice-4 `audit-lite` "What's working" blessed this doc as "Honest, accurate" — see DOC-007; that closure predates the live run.)
- Related findings: DOC-005 (config `local_qwen` comment carries the same "becomes the default if it clears the bar" stale framing), DOC-006 (HANDOFF stale "swap" block).

**Fix path:** Re-frame the doc from "how to run an open comparison" to "the Stage 6 bake-off: how it was
run and what it found." Add a short verdict section at the top stating Qwen `2.5-coder:1.5b` = 0/10
(can't produce a design plan — echoes the schema), gemma `4:e4b` = 8/10 completed / 4/10 graded, KEEP
default; keep the "how to re-run it" steps below as a reproduction guide. Replace the example table with
the real `output/bakeoff/bakeoff.txt` (or clearly label it "illustrative — not the actual result, which
was KEEP"). Drop "that's this hand-off" — the run happened here.

---

### DOC-002 (Major) — Accuracy — HANDOFF title contradicts its own body: "IN PROGRESS … Slices 1 & 2 done" vs "ALL 5 SLICES DONE"

**Evidence:** `HANDOFF.md`

- Title `:1`: "# KimCad — Handoff (2026-06-02 — **Stage 6 IN PROGRESS: model swap — Slices 1 & 2 done**, on branch `stage-6-model-swap`)".
- Body `:5`: "**🔧 STAGE 6 — ALL 5 SLICES DONE on branch `stage-6-model-swap`**".
- Body `:33`: "## 🔧 Stage 6 — **ALL 5 SLICES DONE** … model layer, pending the stage gate".

The title says two of five slices are done and the stage is in progress; the body (the authoritative
"READ FIRST" block) says all five are done and only the stage gate remains. The "single current truth"
rule the project's own §7 lesson states ("One truth per doc … fix or archive the obsolete narrative") is
violated in the first line of the resume document.

**Why this matters:** HANDOFF is the resume artifact — the first thing read after a reboot or compaction.
The title is what a reader anchors on; here it understates progress by three slices and mislabels the
stage as in-progress. This is the same self-contradiction class Scott caught after the Stage-4 merge
(noted at HANDOFF `:298`), recurring.

**Blast radius:**
- Adjacent docs: the title is the only place that says "Slices 1 & 2"; the four §4 stage-plan summary
  lines and the §9 environment note all agree with the body (all five done, gemma stays).
- Migration: none.
- Related findings: DOC-003 (stale head hash in the same banner), DOC-006 (stale "next = swap" block).

**Fix path:** Update the title to match the body — e.g. "Stage 6 ALL 5 SLICES DONE on `stage-6-model-swap`,
pending the stage gate."

---

### DOC-003 (Major) — Accuracy — HANDOFF states the branch head is `1928e13`; the actual head is `96033c2`

**Evidence:** `HANDOFF.md`

- `:5`: "ALL 5 SLICES DONE on branch `stage-6-model-swap` (pushed, **head `1928e13`**; NOT merged/tagged…)".
- `:33`: "## Stage 6 — ALL 5 SLICES DONE (branch `stage-6-model-swap`, **head `1928e13`**)".

`git rev-parse --short HEAD` on `stage-6-model-swap` = **`96033c2`**. `1928e13` is the *Slice 5* commit;
the current head is `96033c2` ("docs: Stage 6 final state -- all 5 slices done, qwen ruled out, gemma
stays (pending gate)"). The banner also says all 5 slices are "done" while pinning a head that predates
the final docs commit that records the verdict — internally inconsistent, and the assertion is a stated
fact (a commit hash) that doesn't hold. This is exactly the "never assert a fact — a path, a count, a
hash — without running the one-line check" lesson (HANDOFF `:294`).

**Why this matters:** A reader using the head hash to verify which commit the handoff describes lands on
the wrong commit (one without the verdict docs). It's a low-effort, high-trust-cost slip.

**Blast radius:**
- Adjacent docs: two occurrences in HANDOFF only; no other doc cites a Stage 6 head hash.
- Migration: none. A handoff that pins a head is inherently staleable — consider phrasing it as "head =
  the branch tip" rather than a frozen hash that drifts every commit.

**Fix path:** Replace both `1928e13` with `96033c2`, or drop the hash and say "the branch tip."

---

### DOC-004 (Major) — Completeness — README is not updated for Stage 6: no `kimcad models`, no `kimcad bakeoff`, no model decision

**Evidence:** `README.md`

- The "Usage" section documents `design` (`:91-116`), `web` (`:118-146`), `--send` (`:149-217`), and "The
  done-gate" `bench` (`:219-229`). It never mentions the two verbs Stage 6 added: **`kimcad models`** (the
  hardware/availability advisor) and **`kimcad bakeoff`** (the model comparison).
- The model section (`:77-89`) names `gemma4:e4b` as the default but says nothing about the Stage 6
  advisor, the tiered fallback (`llm.alt_backend`), or that a Qwen candidate was evaluated and rejected.
- The "Status" banner (`:13-17`) lists the deterministic pipeline, gated export, and Manifold3D, but
  hasn't been advanced past Stage 1/5 framing — no mention of the model layer.

`cli.py` `_SUBCOMMANDS` (`:30`) = `{design, bench, web, models, bakeoff}`; the front-door doc covers three
of five.

**Why this matters:** The README is the front door for the first-time user and the returning user. Two
shipped, user-facing commands are absent from it, so a user has no way to discover `kimcad models` ("what
model should I run on this box?") — which is precisely the question the advisor exists to answer and the
one a new user on unknown hardware most needs. This is a completeness gap, not a lie, so Major rather than
Critical; but for a UX-first project the missing advisor doc is a real adoption cost.

**Blast radius:**
- Adjacent docs: ARCHITECTURE `:94-96` already documents both verbs accurately; the README can borrow
  that language. The bake-off doc (post-DOC-001 fix) is the deep reference `kimcad bakeoff` should link to.
- Migration: none.
- Related findings: DOC-001 (the bake-off doc the README would link to is itself stale).

**Fix path:** Add a short "Choosing a model" subsection under Usage documenting `kimcad models` (advisory,
never rewrites config) and a one-liner on `kimcad bakeoff` (compare backends; recommend-only) linking to
the corrected bake-off doc. Add one sentence noting the default is `gemma4:e4b` and that the Stage 6
Qwen candidate was evaluated and rejected (or keep that detail to CHANGELOG and just document the verbs).

---

### DOC-005 (Major) — Accuracy — `config/default.yaml` `local_qwen` comment still says it "Becomes the default only if it clears the bar," implying the swap is pending

**Evidence:** `config/default.yaml:42-48`
```yaml
    local_qwen:
      ...
      model_name: qwen2.5-coder:1.5b        # candidate default -- a small code model. Pull with
                                            # `ollama pull qwen2.5-coder:1.5b`, then compare vs
                                            # `local` (gemma) with `kimcad bakeoff`. Becomes the
                                            # default only if it clears the bar (Scott's call).
```

The comment frames `local_qwen` as a "candidate default" that "Becomes the default only if it clears the
bar." That bar has been run and **not cleared** (0/10). The config comment is the same stale "swap if it
clears" framing the task flagged, and it sits in the shipped config a user reads.

**Why this matters:** `config/default.yaml` is read by anyone configuring the tool; the comment tells them
Qwen is a live candidate to become the default, contradicting the settled verdict. It's a stated forward
intent that is no longer true. Comments in shipped config carry the same accuracy obligation as prose docs.

**Blast radius:**
- Adjacent code: none — `local_qwen` is correctly retained as a selectable `--backend` (CHANGELOG `:32`,
  ROADMAP `:177` confirm it stays defined). Only the comment is stale.
- Adjacent docs: shares the "clears the bar" framing with the bake-off doc (DOC-001) and HANDOFF `:124`
  (DOC-006) — fix as a set.
- Migration: none. The backend key stays; only the comment changes.

**Fix path:** Reword to past tense / reference outcome — e.g. "the Stage 6 bake-off challenger; evaluated
2026-06-02 and rejected (0/10 — can't produce a design plan), so `local` (gemma) stays the default.
Retained as a selectable `--backend` for re-running the comparison."

---

### DOC-006 (Minor) — Accuracy — HANDOFF's Stage 5 section still carries a "NEXT = Stage 6 (model swap): make it the default if it clears the bar" block

**Evidence:** `HANDOFF.md:123-125`
> **➡️ NEXT = Stage 6 (model swap):** benchmark `Qwen2.5-Coder 1.5B` on the target box; **make it the
> default if it clears the bar**; keep `gemma4:e4b` as the non-China alternative + vision fallback; a
> tiered fallback chain (template → primary → alt; cloud opt-in). See ROADMAP §"Stage 6".

This is a leftover forward-looking block inside the (now-superseded) Stage 5 "NEXT" narrative. It describes
Stage 6 as upcoming work whose plan is "make qwen the default if it clears the bar" — which is both
out-of-date (Stage 6 is done) and states the rejected swap as the plan. The authoritative Stage 6 block at
the top of HANDOFF (`:33-76`) already records the real outcome; this trailing block contradicts it.

**Why this matters:** Lower exposure than DOC-002/003 because it's in the historical Stage 5 section a
reader reaches after the authoritative banner, but it's the third instance of the stale "swap if it clears"
framing and a reader scanning for "what's next" could land on it. Same "one truth per doc" issue, lower blast.

**Blast radius:**
- Adjacent docs: the stale framing is shared with DOC-001 (bake-off doc) and DOC-005 (config comment).
- Migration: none.

**Fix path:** Replace the block with a one-line pointer to the authoritative Stage 6 section, or update it
to "NEXT = Stage 6 stage gate (model decision settled: gemma stays, qwen rejected)."

---

### DOC-007 (Minor) — Accuracy — Slice-4 `audit-lite` closure blesses the bake-off doc as "Honest, accurate" — true when written, stale now

**Evidence:** `docs/audits/stage-6/audit-lite-slice-4-bakeoff-2026-06-02.md:32`
> **Honest, accurate hand-off doc.** `docs/benchmarks/stage-6-model-bakeoff.md` matches the code: the
> default backends, slice-by-default, the decision rule … are all stated accurately…

That closure was correct *at the time* (the doc accurately described how to run a then-unrun comparison,
and the slice was reviewing the harness, not the live result). But it now reads as a standing certification
that the bake-off doc is accurate, while DOC-001 shows the doc is materially stale post-verdict. The other
four slice closures spot-check clean against the current code (see "Spot-check of slice closures" below).

**Why this matters:** Committed audit reports travel with the code as evidence. A "this doc is accurate"
line that no longer holds can be cited later as proof the doc was vetted. Low blast (the report is a
point-in-time artifact, dated), but worth a one-line note so it isn't read as current.

**Blast radius:**
- Related findings: DOC-001 (the doc this closure blessed).
- Migration: none.

**Fix path:** No rewrite of the historical report needed; when fixing DOC-001, the corrected bake-off doc
supersedes this. Optionally add a dated one-line note to the Slice-4 report that the doc was re-framed
after the live run. (The stage-gate re-frame of DOC-001 is the real action.)

---

### DOC-008 (Minor) — Accuracy / Honesty — "vision fallback" is asserted for `gemma4:e4b` but nothing in the shipped code uses it for vision

**Evidence:**
- `HANDOFF.md:124`: "keep `gemma4:e4b` as the non-China alternative + **vision fallback**".
- `docs/benchmarks/stage-6-model-bakeoff.md:82`: "keep `gemma4:e4b` defined as the non-China alternative
  and **the vision fallback**".
- `model_advisor.py:108` catalog note: "the non-China local alternative + **vision-capable**."

No shipped code path uses gemma (or any model) for vision — the image/sketch on-ramp is Stage 9
(ROADMAP `:197-207`), unbuilt. "Vision-capable" (the catalog note) is a defensible factual property of the
model; "vision fallback" (HANDOFF/bake-off doc) reads as a current role in KimCad's pipeline that doesn't
exist yet.

**Why this matters:** Minor — it's a forward-looking rationale for keeping gemma defined, not a
user-facing capability claim on the README, so blast is small. But "fallback" implies a wired role; per
the project's strict no-unverified-facts posture, an aspirational capability shouldn't be stated as a
present one.

**Blast radius:**
- Adjacent docs: three files share the phrasing.
- Migration: none.

**Fix path:** Qualify as forward-looking — "kept defined as the non-China alternative (and a
vision-capable model for the future Stage 9 image on-ramp)" — or drop "fallback" where it implies a wired role.

---

### DOC-009 (Nit) — Accuracy — `cli.py` module docstring says "Three subcommands" and omits `models` and `bakeoff`

**Evidence:** `cli.py:3-8`
```python
Three subcommands:

    kimcad "a wall bracket for a 25mm pipe"     # design a part (default verb)
    kimcad design "..." [...] [--slice]
    kimcad bench [...]
    kimcad web [...]   # local browser UI (Phase 2)
```
The docstring says "Three subcommands" (already off — it lists four including `web`) and Stage 6 added two
more (`models`, `bakeoff`) that aren't listed. `_SUBCOMMANDS` (`:30`) is the source of truth: five.

**Why this matters:** Developer-facing docstring only; no user impact. But it's a stated count that's wrong
and a list that's incomplete after the Stage 6 verbs landed.

**Fix path:** "Five subcommands" and add the `models` / `bakeoff` lines. (ARCHITECTURE `:96` already lists
all five correctly — mirror it.)

---

### DOC-010 (Nit) — Tone/Consistency — HANDOFF §9 reports "~9 min/prompt" for gemma while the body reports "~10 min/prompt" and the artifact says 595.7 s mean

**Evidence:** `HANDOFF.md`
- `:319`: "`gemma4:e4b` … **~9 min/prompt** on the 32 GB / AMD 780M iGPU, CPU-only box".
- `:68`: "`gemma4:e4b` = 8/10 completed, 4/10 fully graded, **~10 min/prompt**".
- `output/bakeoff/bakeoff.txt`: gemma `mean_s 595.7` (= 9.9 min/prompt).

Two different round figures (~9 vs ~10 min) for the same measurement in the same doc. The artifact's 595.7 s
rounds to ~10 min, so `:68` is closer; `:319` is a slightly older ~9 min figure.

**Why this matters:** Nit — both are "about ten minutes," no decision rides on it. Flagged only for the
single-source-of-truth tidiness the project values.

**Fix path:** Use one figure (≈10 min/prompt, per the 595.7 s artifact) in both places, or cite the
artifact.

---

## Spot-check of the per-slice `audit-lite` closures vs. current code

The five slice reports claim re-audit closure at **0/0/0/0/0**. Spot-checked against the head-`96033c2`
code; the closures hold:

- **Slice 1 (model advisor)** — ADV-002 closure says the gemma label was changed to `"Gemma E4B"` (dropping
  the unverified "3n" generation). Verified: `model_advisor.py:107` reads
  `ModelSpec("gemma4:e4b", "Gemma E4B", ...)`. ADV-001's `non_china_installed` plumbing and the
  China-origin-only escape are present (`recommend()` / `_non_china_escape`). **Matches.**
- **Slice 2 (FallbackProvider)** — closure says `Pipeline.__init__` was re-annotated `provider: Provider`.
  Verified: `pipeline.py:228` = `provider: Provider`; `FallbackProvider` + the `Provider` Protocol exist in
  `llm_provider.py`. **Matches.**
- **Slice 3 (3-axis grading)** — BENCH-001 closure says a ceiling-only fit no longer returns `True`.
  Verified: `benchmark.py:143` `verdict = True if "dim.match" in gate_codes else None` — the ceiling can
  only flip the verdict to `False`, never assert `True` on its own. **Matches.**
- **Slice 4 (bake-off)** — BAKE-001/002 closures (ASCII reason strings, column-aligned `to_text`). Verified:
  `bakeoff.py` reason strings use ` -- ` not em-dashes; `to_text` formats each cell as a whole token then
  pads. **Matches.** (Caveat: this report's "doc is accurate" line is now stale — DOC-007.)
- **Slice 5 (plan-failure robustness)** — PLAN-001 closure says `plan_failed` returns exit **6** (distinct
  from `gate_failed`'s 5). Verified: `cli.py:259-263` returns `6` for `PipelineStatus.plan_failed`;
  `pipeline.py:109` defines the status, `:299` sets it; `PlanParseError` is raised only at the parse
  boundary in `llm_provider.py`. **Matches.**

No false closure found. The one caveat is temporal (DOC-007), not a code mismatch.

---

## What's working (credit where due)

- **No "done / merged / tagged" overclaim on Stage 6.** CHANGELOG keeps Stage 6 under `[Unreleased]` and
  states explicitly "implemented on `stage-6-model-swap`, pending the stage gate — NOT yet merged/tagged"
  (`:9-18`). ROADMAP `:154-177` and the HANDOFF body `:5` / `:33` all say "implemented, pending gate." The
  hard lesson from prior stages (docs claiming a stage is done before the gate) is **not** repeated. This
  is the single most important check and it passes.
- **The model verdict reads accurately in the load-bearing docs.** CHANGELOG `:30-32`, ROADMAP `:18-20`
  and `:171-176`, and the HANDOFF body `:9-12` / `:65-70` all state: Qwen `2.5-coder:1.5b` evaluated via the
  live bake-off and **rejected** (0/10 — can't produce a design plan); `gemma4:e4b` **stays** the default;
  `local_qwen` retained as a selectable `--backend`. All three match the committed `output/bakeoff/bakeoff.txt`.
- **ARCHITECTURE's module table is accurate against the code.** The Stage 6 rows are correct:
  `model_advisor.py` (`:94` — best-effort RAM/CPU/GPU + Ollama probes that degrade to None, pure
  `recommend()`, advisory-only), `bakeoff.py` (`:95` — per-backend benchmark, isolation, recommend-only),
  the `FallbackProvider` + `PlanParseError` additions to `llm_provider.py` (`:73`), the 3-axis tri-state
  grading in `benchmark.py` (`:93`), and the new `models` / `bakeoff` CLI verbs (`:96`). Each verified
  present and behaving as described.
- **`bench/prompts.yaml` header is accurate.** The header (`:13-17`) correctly describes the 3-axis grading
  (matches-request / correct-dimensions / slices-clean), that slices-clean is only graded with
  `--slice`, and that the 3-axis rollup is what the bake-off compares — all matching `benchmark.py`.
- **CHANGELOG Stage 6 entry is specific and honest** — names each capability, the `alt_backend` default-off
  posture, the `plan_failed` exit-6 behavior, and the decision, with no inflation.
- **The docstrings remain excellent.** `model_advisor.py`, `bakeoff.py`, and `llm_provider.py` module/class
  docstrings explain *why* (e.g. why the bake-off uses no fallback, why `primary.max_attempts→1`, why RAM
  floors are heuristics) — they're a genuine asset and should be the template for the rest of the codebase.
- **The five slice `audit-lite` reports are thorough and their closures are real** (spot-check above): each
  found genuine issues (the `_installed_match` exact-tag bug, the undersized-part grading over-claim, the
  exit-code collision) and the fixes are in the code.

---

## Cross-role hand-off notes

- **DOC-001** (the stale bake-off doc) pairs with any Engineering/QA finding on `kimcad bakeoff` — the doc
  is the user's only guide to a command whose output now contradicts the doc's example.
- **DOC-004** (README missing `kimcad models`) is also a UX/onboarding gap — the advisor is the
  hardware-aware "what should I run?" answer a first-time user on unknown hardware needs, and it's
  undiscoverable from the front door.
- The stale "swap if it clears the bar" framing has **three instances** sharing one root (the decision
  flipped from the original plan): DOC-001 (bake-off doc), DOC-005 (config comment), DOC-006 (HANDOFF block).
  Fix them as one coordinated pass so a single current truth — "evaluated, rejected, gemma stays" — lands
  everywhere.
