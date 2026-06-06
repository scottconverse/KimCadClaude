# Stage 7 — Documentation Deep-Dive (Technical Writer)

**Audit:** Stage 7 backfill (Smart Mesh + PrintProof3D + readiness report + learning store)
**Date:** 2026-06-05
**Auditor role:** Senior Technical Writer (independent, skeptical)
**Repo:** `C:\Users\scott\dev\kimcad` — branch `stage-0-7-audit-backfill` @ `800016a`
**Mode:** AUDIT-ONLY (gaps recorded; needed drafts noted as findings, not written)

## Scope

Verify the docs truthfully describe Smart Mesh readiness, the PrintProof3D arm's-length
engine, and the learning store. Docs reviewed: `README.md` (readiness section), `ROADMAP.md`
(Stage 7), `CHANGELOG.md` (Stage 7), `docs/printproof3d-integration.md`, `ARCHITECTURE.md`
(readiness/gate boundary). Cross-checked against `src/kimcad/smart_mesh.py`,
`src/kimcad/printproof3d.py`, `src/kimcad/history.py`, with corroboration from
`src/kimcad/config.py` and `src/kimcad/pipeline.py`.

---

## What's working (credit where due)

This is some of the most honest, code-faithful documentation I have audited. Specific praise:

- **The advisory-vs-authority boundary is stated cleanly and consistently** across all five
  docs. README:46-48, ARCHITECTURE.md:31-33, ROADMAP.md:207-208, CHANGELOG.md:305, and
  `docs/printproof3d-integration.md:78-84` all say the same true thing: the deterministic
  Printability Gate is the slice authority; Smart Mesh / PrintProof3D are advisory; a
  gate-passed part slices even with an engine advisory, a gate-failed part never slices. This
  matches `pipeline.py` (readiness is computed but never feeds the slice decision) and
  `smart_mesh.py:164-182` (tone is the worst of the two signals).
- **The "never claims the engine ran when it didn't" claim is real.** README:47-48 and
  `printproof3d-integration.md:50` both assert it; `smart_mesh.py:219-225` (`_attribution`)
  returns `"KimCad printability gate"` whenever `printproof is None`, and only
  `"PrintProof3D validation engine"` when a report parsed. Verified true.
- **The arm's-length / never-linked / never-raises description is accurate.**
  `printproof3d-integration.md:9-26` matches `printproof3d.py` line-for-line: subprocess with
  no shell (`_subprocess_runner`, line 50), gated on the parsed report file not the exit code
  (lines 50, 105-111), every failure mode degrades to `None` (lines 70, 88-89, 100-111),
  `validate_model` never raises (docstring line 64 + the broad guards).
- **The report contract JSON (`printproof3d-integration.md:57-71`) matches the parser.**
  `status` required and restricted to pass/warning/fail (`_parse_report`, line 166); unknown
  severities skipped (lines 175-176, `_VALID_PP_SEVERITIES`); non-list `issues`/`suggested_fixes`
  tolerated (lines 170, 178); extra/malformed fields skipped. Honest and precise.
- **The learning store description is honest and matches `history.py`.** Coarse record (no
  geometry/prompt), best-effort/never-raises, atomic write, factual-not-flattering comparison
  wording ("a personal best" = strict beat; tie = "on par"; no history = no line) — all verified
  against `compare_phrase` (lines 53-78) and `HistoryStore` (lines 81-141).
- **All cross-doc links and asset paths resolve.** `docs/guide-my-designs.md`,
  `docs/guide-sliders-and-units.md`, `docs/benchmarks/stage-5-template-families.md`,
  `docs/design/screens/10-smartmesh-report.png`, and the audit dir
  `docs/audits/stage-7/audit-team-stage-7-2026-06-02/` all exist. No dead links found.
- **Config keys are documented and real.** `binaries.printproof3d` and `paths.history`
  (CHANGELOG.md:319-320, integration doc:37-46) match `config/default.yaml:17,20-24` and
  `config.py:122-143`. The "default path is `tools/printproof3d/...`, drop a binary there"
  claim (integration doc:42-44) is verified against the default config + `printproof3d_binary()`.

---

## Findings

### DOC-001 — Minor — Accuracy

**Title:** Integration doc overstates the confidence-rise trigger ("configured and present" → High)

**Evidence:**
`docs/printproof3d-integration.md:48-50`:
> "When the engine is configured and present, the readiness card's confidence rises to **High**
> ... without it, the card reads **Medium** / **"KimCad printability gate."**"

Code: `smart_mesh.py:209-216` (`_confidence`) returns `"High"` only when `printproof is not None`
**and** `mesh_unanalysable` is False. `printproof` is non-None only when the engine *both* ran
*and* produced a parseable `ValidationReport` (`printproof3d.py:70,105-111` return `None` on a
missing binary, a profile error, a runner raise, a missing/unreadable/unparseable report, or a
bad `status`). So an engine that is "configured and present" but times out, crashes before
writing, or emits a garbled report yields confidence **Medium**, attribution **"KimCad
printability gate"** — not High. Separately, `mesh_unanalysable` forces **Low** regardless of
the engine (`_confidence` line 212-213), which the doc's two-state ("High ... or Medium")
framing omits.

**Why this matters:** A returning user (or Kim, reading her own card) could expect High whenever
the binary is installed, then see Medium after a flaky engine run and reasonably think the
integration is broken. The card is actually behaving correctly — degrading honestly — but the
doc set the wrong expectation.

**Blast radius:**
- Adjacent docs: README:46-48 phrases this more safely ("when it's configured" + "never claims
  the engine ran when it didn't") and is not affected. Only the integration doc overstates.
- User-facing: expectation only; no behavior change.
- Migration: none. Tests to update: none.
- Related findings: DOC-002 (same doc, same "Low" omission).

**Fix path (note only — not drafted):** Recommend rewording integration doc:48-50 to "rises to
**High** when the engine runs and returns a usable report" and adding the third state: "if the
mesh can't be fully analysed the card reads **Low** regardless of the engine." A two-sentence
edit; no new doc needed.

---

### DOC-002 — Minor — Completeness

**Title:** The "Low" confidence state is undocumented across the user-facing docs

**Evidence:** `smart_mesh.py:82` defines confidence as `"High" | "Medium" | "Low"`, and
`_confidence` (lines 209-216) returns `"Low"` whenever `mesh_report.errors` is non-empty
(`mesh_unanalysable`, line 146). No user-facing doc mentions the Low state or what it means:
README:46-48 describes the card without listing the confidence levels; the integration doc
(48-50) describes only High/Medium. ARCHITECTURE.md:99 mentions "a confidence" generically.

**Why this matters:** A user who sees a "Low" confidence badge (mesh only partly analysable) has
no doc to consult for what it means or what to do. It's the most alarming of the three states and
the only one that isn't explained anywhere.

**Blast radius:**
- Adjacent docs: README readiness section + integration doc both candidates for the one-line add.
- User-facing: the Low badge appears on any part whose mesh can't be fully analysed (a real,
  reachable state, not theoretical).
- Migration: none. Tests: none.
- Related findings: DOC-001 (same root: confidence levels under-documented).

**Fix path (note only):** Recommend one sentence in the README readiness paragraph: "Confidence
is **Low** when the mesh couldn't be fully analysed (the verdict is provisional), **Medium** on
the gate alone, **High** when the deeper engine ran." No new doc.

---

### DOC-003 — Minor — Accuracy

**Title:** ROADMAP Stage 7 leaves stale pre-merge boilerplate inside a section marked DONE

**Evidence:** `ROADMAP.md:187-211`. The header (187-189) says "✅ DONE — merged + tagged
`stage-7`", but the body still carries pre-completion planning text:
- Line 210-211: **"Remaining for the stage gate:** the full `audit-team` at 0/0/0/0/0 → merge →
  tag `stage-7`. **Needs:** target box. **Size:** ~2–3 weeks."

That "Remaining ... → merge → tag" line describes work the same section's header says is already
done, and "Size: ~2–3 weeks" is a future-estimate inside a shipped stage. The Stage 8.5 section
(213-234), which is also DONE, was cleaned of its "Remaining/Needs/Size" pre-merge tail; Stage 7
was not, making it internally contradictory.

**Why this matters:** A new team member reading ROADMAP can't tell whether Stage 7's gate is
actually closed — the header says yes, the body says "remaining." Inaccurate status docs erode
trust in the whole roadmap. (Note: the explicit lesson at ROADMAP.md:188-189 is precisely about
the tagged artifact's docs reading "done, not pending" — this residual contradicts that intent.)

**Blast radius:**
- Adjacent docs: CHANGELOG.md:290 and README:48 both state Stage 7 done cleanly; only ROADMAP
  carries the stale tail. Stage 6 (line 185) is clean; pattern is isolated to Stage 7.
- User-facing: none (internal planning doc).
- Migration: none. Tests: none.
- Related findings: none.

**Fix path (note only):** Recommend deleting/!rewriting ROADMAP.md:210-211's "Remaining for the
stage gate ... Size: ~2–3 weeks" to past tense or removing it, matching how Stage 8.5 was cleaned.
One-line edit.

---

### DOC-004 — Nit — Accuracy

**Title:** Integration doc "Privacy" calls the learning store the engine "feeds"

**Evidence:** `docs/printproof3d-integration.md:87-90`:
> "The Smart Mesh learning store it feeds (`~/.kimcad/history.json`) is likewise local-first ..."

PrintProof3D does not feed the history store. The store records the **readiness score** (which
PrintProof3D influences via penalties) plus type/gate/material/max-dim — see `history.py:40-50`
(`PrintRecord`) and `pipeline.py:626-645` (`_record_history`). The engine is one upstream input
to the score, not a writer of the store; "it feeds" reads as a direct data path that doesn't
exist.

**Why this matters:** Minor precision only; the privacy claim itself (nothing leaves the machine,
coarse record) is true and well-stated. The phrasing slightly mis-draws the data flow.

**Fix path (note only):** Reword to "The Smart Mesh learning store (`~/.kimcad/history.json`) is
likewise local-first and coarse." Drop "it feeds."

---

## Cross-cutting observations (not findings)

- **No "advisory vs authority" muddle anywhere.** The single most important boundary for this
  stage is described correctly in every doc. This is the headline good news.
- **No overclaim on PrintProof3D capability.** Every doc consistently scopes it as advisory in
  Stage 7 and defers "fold engine `fail` into the slice gate" to a Stage-11-gated follow-up
  (integration doc:78-84, ROADMAP.md:278-284, CHANGELOG.md:305-307). The "bundled at Stage 11 /
  arm's-length today / off by default because the binary isn't shipped" claims
  (integration doc:28-31, ROADMAP.md:278-284) match `printproof3d_binary()` returning `None`
  when the file is absent (`config.py:127-132`). No future capability is described as present.
- **The README readiness paragraph (46-48) is the strongest single piece of copy in the set** —
  honest, scoped, names the advisory nature and the "never claims it ran" guarantee in three
  sentences.

---

## Severity rollup

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 1 |
| **Total** | **4** |

## Verdict

**PASS (advisory docs are trustworthy).** No Blocker/Critical/Major. The Stage 7 documentation
truthfully describes Smart Mesh readiness, the PrintProof3D arm's-length engine, and the learning
store; the advisory-vs-authority boundary — the one thing that most needed to be right — is right
everywhere. The four findings are precision/completeness polish: a slightly overstated confidence
trigger and an undocumented "Low" state (DOC-001/002), a stale pre-merge tail in the otherwise
DONE ROADMAP Stage 7 section (DOC-003), and one imprecise data-flow phrase (DOC-004). None block
the stage; all are short, localized edits.
