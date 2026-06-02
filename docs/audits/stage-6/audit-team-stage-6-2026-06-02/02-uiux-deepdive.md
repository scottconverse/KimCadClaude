# Stage 6 — UI/UX Deep-Dive

**Auditor:** Senior UI/UX Designer (audit-team)
**Date:** 2026-06-02
**Repo / branch:** `C:\Users\scott\dev\kimcad` @ `stage-6-model-swap` (head `96033c2`)
**Scope:** Stage 6 user-facing surfaces only — the `kimcad models` advisor, `kimcad bakeoff`
comparison/recommendation, the `plan_failed` experience (CLI + web), and the benchmark 3-axis
rollup text. There is no new GUI screen in Stage 6; per the audit brief that is *not* a fault.
I judged the quality of the text/CLI interfaces that ship and the one web message that changed.

Method: I ran the real commands against this machine (`.venv\Scripts\python.exe -m kimcad.cli ...`),
read the persisted artifacts (`output/bench/summary.txt`, `output/bakeoff/bakeoff.txt`), rendered the
current `BenchSummary.to_text` with a representative summary, and read the frontend render path
(`designStatus.ts` → `ChatPanel.tsx` / `RightPanel.tsx` / `ExportPanel.tsx`) plus the styles that back
them. Where I quote output below, it is the literal text I saw.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 2 |
| Minor    | 4 |
| Nit      | 3 |
| **Total**| **9** |

No Blockers, no Criticals. The user-facing copy is, on the whole, unusually thoughtful — honest about
what the tool did and did not do, with the advisory/never-auto-switch boundary stated clearly in three
separate places. The two Majors are both about the **web plan-failure state** (it reads like an idle
state, not a failure) and the **bakeoff table's degenerate-run row** (a model that completed nothing
shows misleading `0/0` cells with no "did not run" signal). Everything else is polish.

---

## What's working (specific credit)

These are real strengths, not generic praise:

1. **The advisory boundary is stated, repeatedly and clearly, in plain English.** The `models` command
   closes with: *"The model is never hardwired. To choose one: set `llm.active` (or a backend's
   `model_name`) in config/local.yaml, or pass `--backend <key>` to design/web/bench."* The `bakeoff`
   output closes with: *"(Flipping the configured default model is Scott's call, not the harness's.)"*
   For a tool whose entire Stage 6 thesis is "recommend, never auto-switch," saying so at the point of
   recommendation is exactly right. The user is never left wondering whether the tool changed something.

2. **The recommendation tells the user how to act, and offers a next step.** `models` doesn't just name
   a model — it names the install state (`(installed)`), an upgrade with the exact pull command
   (`Upgrade you could run: Qwen2.5-Coder 7B  (ollama pull qwen2.5-coder:7b)`), and, when relevant, a
   non-China alternative. That is a complete "what now?" answer, not a dead-end verdict.

3. **The SWITCH/KEEP recommendation is unambiguous and reasoned.** The live bakeoff produced:
   *"Recommendation: KEEP default local -- the incumbent local (gemma4:e4b) is already the best."*
   The verb (`KEEP`/`SWITCH`) leads, the backend is named, and the reason follows. A reader scanning
   the last line knows the verdict and why without parsing the table.

4. **The web `plan_failed` copy is genuinely good and does not leak internals.** `designStatus.ts`
   deliberately ignores `result.error` for this case and renders:
   *"I couldn't turn that into a workable plan — the model's response wasn't usable. Try describing the
   part a little differently, or switch to a model better suited to planning."* First-person, blames the
   model (not the user), and gives two concrete next moves. The intent is locked by a test
   (`designStatus.test.ts`: `expect(planFailed).not.toContain('ValidationError')`). This is the
   single best piece of copy in the stage.

5. **The CLI `plan_failed` message keeps a short, useful hint without dumping a traceback.**
   `PLAN_FAILED_MESSAGE` points the user at `kimcad models` and only appends a one-token
   `(details: <ExceptionType>)` — not the multi-line pydantic dump. The split (clean message + tiny
   diagnostic token) is the right altitude for a CLI.

6. **The chat region is a live region.** `ChatPanel` renders the conversation in
   `<div role="log" aria-live="polite" aria-busy={busy}>`, so the plan-failure message *is* announced
   to a screen reader when it arrives, and the "Designing your part…" busy state is conveyed via
   `aria-busy`. Decorative SVG avatars carry `aria-hidden="true"`. Accessibility was clearly considered.

7. **Console-safety was taken seriously and is mostly handled.** `cli.py` reconfigures stdout/stderr to
   UTF-8 (`_force_utf8_output`) precisely because the report uses glyphs like `×`, `³`, `°`; and the two
   *new* Stage 6 text producers (`bakeoff.to_text`, `model_advisor`) go further and use pure-ASCII
   separators (`--`, `->`). That is the correct response to the cp1252 history. (One residual gap is
   UX-005 below.)

---

## Findings

### UX-001 (Major) — Web: a plan-failure renders like an idle/neutral state, not a failure

**Category:** State / Visual hierarchy
**Evidence:** On a `plan_failed` result the web shows three things, none of which signal "this failed":
- **Chat:** the (good) plan-failure copy is rendered through the *plain* `AssistantRow` in
  `ChatPanel.tsx:67` — `<AssistantRow>{assistantMessage(result)}</AssistantRow>` — with **no**
  `tone="error"`. Only the transport-level network `error` gets `tone="error"` (line 65). So the
  failure message sits in the same neutral grey bubble as a successful *"Here you go — …"*. The
  `.kc-msg-error` red-tinted style (styles.css:708) exists but is never applied to status-based
  failures (`plan_failed` / `render_failed` / `gate_failed`).
- **Parameters card** (`RightPanel.tsx:163-167`): with no `plan` and no `parameters`, it shows the
  *idle placeholder* — *"The part's adjustable parameters will appear here once it's designed."*
- **Printability card** (`RightPanel.tsx:218-223`): with no `report`, it shows the *idle placeholder* —
  *"The printability check … appears here after a part is designed."*

So after a failed attempt, two of three panels say "…once it's designed / after a part is designed," as
if the user simply hasn't acted yet. The one panel that *does* speak is styled identically to success.
**Why it matters:** the message tells the truth but the *interface* contradicts it. A user who skims
(most users) sees neutral bubbles and "appears here once designed" and may conclude the request is still
processing, or that they did something wrong, rather than "the model failed; try rephrasing." This is
the highest-leverage UX issue in the stage because the failure path is exactly where users need the
clearest signal.
**Blast radius:**
- Adjacent code: `ChatPanel.tsx` `AssistantRow` (add a non-network failure tone); the same neutral-vs-error
  gap applies to `render_failed` and `gate_failed`, so fix the tone selection once for all
  status-based failures. `RightPanel` placeholder copy (Parameters + Printability cards).
- User-facing: every web design attempt that ends in `plan_failed` / `render_failed` / `gate_failed`.
- Migration: none (presentation only).
- Tests to update: `designStatus.test.ts` is unaffected (copy unchanged); add a component test asserting
  the error tone is applied for status-based failures if the team component-tests `ChatPanel`.
- Related findings: UX-002, DOC/QA may also flag the right-panel "idle vs failed" ambiguity.
**Fix path:** Drive the assistant-row tone from the result status, not just the transport error. In
`ChatPanel`: `const failed = result && ['plan_failed','render_failed','gate_failed'].includes(result.status)`
then `<AssistantRow tone={error || failed ? 'error' : undefined}>`. Separately, give the right-panel cards
a *failed* branch distinct from the idle branch — e.g. Parameters: *"No part was produced — there's
nothing to adjust yet. Try describing it a little differently on the left."* and Printability:
*"No part to check yet — the last attempt didn't produce a model."* The point is that a failed attempt
must never reuse the never-tried-yet copy.

---

### UX-002 (Major) — Bakeoff table: a model that completed nothing shows misleading `0/0` axis cells

**Category:** Copy / Visual hierarchy (data honesty)
**Evidence:** The real, persisted `output/bakeoff/bakeoff.txt` from the live qwen-vs-gemma run:
```
Bake-off: 2 model(s), 10 case(s) each
  backend        model                  completed  graded  match   dims  slice   mean_s
  local_qwen     qwen2.5-coder:1.5b          0/10    0/10    0/0    0/0    0/0      0.0
  local (def)    gemma4:e4b                  8/10    4/10   9/10   5/10   8/10    595.7
Recommendation: KEEP default local -- the incumbent local (gemma4:e4b) is already the best.
(Flipping the configured default model is Scott's call, not the harness's.)
```
The challenger row reads `0/10` completed (clear), but then `0/0` for match / dims / slice and `0.0`
mean_s. The `0/0` is *technically* correct (the axis tally is `passed/assessed`, and nothing was
assessed because nothing completed), but to a reader it parses as "0 out of 0 — perfect? broken? N/A?"
The `0.0` mean_s for a model that ran for real and failed every case also reads as "instant," which is
the opposite of the truth (it produced unusable output, it wasn't fast).
**Why it matters:** the bakeoff table is *the* decision artifact for "switch the model or not." A
degenerate row (the most common failure shape — a too-small model that can't plan at all) is exactly the
case the table must communicate crisply, and right now it's the most ambiguous row. The recommendation
line saves it ("KEEP … already the best"), but the table above the line invites a double-take. Note the
header also reads `0/0` cleanly *only* because the recommendation rescues meaning — without it, a reader
could mistake `0/0` for "untested."
**Blast radius:**
- Adjacent code: `Bakeoff.to_text` (bakeoff.py:140-170) and `BenchSummary.axis_tally` (benchmark.py:199-204).
- User-facing: every bakeoff where a backend completes zero (or few) cases — i.e. the canonical "reject the
  challenger" run.
- Migration: none. `bakeoff.txt` is regenerated each run.
- Tests to update: bakeoff `to_text` formatting tests, if any assert exact column strings.
- Related findings: UX-006 (mean_s for a never-completing model).
**Fix path:** When `assessed == 0` for an axis, render `n/a` (or `--`) instead of `0/0`, matching the
`--` "not assessed" convention the benchmark per-case axes already use
(`BenchSummary._axis_mark` → `--`). Consider an explicit zero-completion note under the row, e.g.
*"(local_qwen completed 0/10 — no axes could be graded)"*, so the reader isn't left to infer it from a
row of `n/a`. This keeps the table honest about *measured vs unmeasured* rather than implying a 0-score.

---

### UX-003 (Minor) — `models` upgrade line implies "better" without saying how much, and may confuse on the reference box

**Category:** Copy
**Evidence:** Real `kimcad models` output on this machine:
```
Recommendation
  -> Gemma E4B  [gemma4:e4b]  (installed)
  Gemma E4B is the strongest model you have installed that fits this machine (...). Your hardware
  could also run Qwen2.5-Coder 7B -- pull it for a step up in quality.
  Upgrade you could run: Qwen2.5-Coder 7B  (ollama pull qwen2.5-coder:7b)
```
The advisor confidently suggests pulling Qwen2.5-Coder 7B "for a step up in quality" — but the *live
bakeoff in this same repo* found the qwen *1.5B* produces 0/10 plans, and the project has settled on
gemma. A user who follows the advisor's own upgrade suggestion (7B) has no way to know from this screen
that the qwen *family* was the rejected challenger. The advisor's "quality" claim is derived purely from
a static `tier` integer in the catalog (model_advisor.py: `tier=5` for 7B vs `tier=3` for gemma), not
from any measured result. The recommendation and the bakeoff are two different notions of "better" that
a user can't reconcile.
**Why it matters:** the tool gives advice the tool's own evidence partially contradicts. It's not wrong
to surface a larger model as a *theoretical* upgrade, but "for a step up in quality" overstates a static
heuristic as if it were measured. Low exposure (only the curious user who reads the upgrade line and acts
on it), hence Minor — but on an ex-Apple, honesty-first product this is the kind of unearned confidence
worth toning down.
**Blast radius:**
- Adjacent code: `model_advisor.recommend` upgrade reason string; `MODEL_CATALOG` tier values.
- User-facing: any machine where a higher-tier local model fits but isn't installed.
- Migration: none.
**Fix path:** Soften the claim to reflect that tiers are heuristic, not benchmarked: *"Your hardware
could also run Qwen2.5-Coder 7B — a larger model that may plan better, but run `kimcad bakeoff` to
confirm before switching."* That ties the upgrade suggestion back to the actual evidence path the stage
ships, and stops asserting a quality gain the advisor hasn't measured.

---

### UX-004 (Minor) — Bakeoff `(def)` tag and KEEP line use slightly different names for the same backend

**Category:** Copy (consistency)
**Evidence:** In `bakeoff.txt` the table tags the incumbent row `local (def)` (abbreviated), while the
recommendation says `KEEP default local` and the reason says `the incumbent local (gemma4:e4b)`. Three
labels for one thing in ~5 lines: `(def)`, `default`, `incumbent`. A first-time reader has to infer that
`(def)` = `default` = `incumbent`.
**Why it matters:** minor cognitive tax on the decision artifact. Not wrong, just three vocabularies
where one would read cleaner. Low severity.
**Fix path:** Pick one term. Recommend expanding the table tag from `(def)` to `(default)` (there's room —
the `backend` column is `<14`) and using "the current default" consistently in the reason instead of
"incumbent." "Incumbent" is also slightly jargon-y for a maker-audience tool; "current default" is plainer.

---

### UX-005 (Minor) — Benchmark `to_text` error line uses a Unicode em-dash while the new Stage 6 outputs are pure-ASCII

**Category:** Copy / Console-safety (consistency)
**Evidence:** `benchmark.py:254` — the per-case error suffix is `extra = f" — {o.error}" if o.error else ""`
(U+2014 em-dash). When I rendered the current `to_text` and captured it through a cp1252 stream, the
error line came back as: `... {req=--, dim=--, slice=--} � ValidationError ...` (the `—` degraded to a
replacement glyph). At the real CLI this is *normally* fine because `cli.py` reconfigures stdout to UTF-8
first — but that reconfigure is explicitly documented as best-effort ("`reconfigure` is absent on some
wrapped streams … the call is best-effort"), and the *new* Stage 6 producers (`bakeoff.to_text`,
`model_advisor`) deliberately avoid this by using ASCII `--`/`->`. So the benchmark rollup is the one
remaining user-facing producer that depends on the UTF-8 reconfigure succeeding, and it does so *on the
error line* — the line that only appears when something already failed.
**Why it matters:** if the reconfigure ever fails (the documented possibility — a wrapped/redirected
stream, an odd terminal), the crash lands precisely on a failed-case report, turning a clean failure into
a UnicodeEncodeError stack. The repo's whole cp1252 posture is "don't depend on the console encoding for
user-facing text." This one line still does. Low exposure (reconfigure usually succeeds), hence Minor.
**Blast radius:**
- Adjacent code: `benchmark.py:254` (the only *runtime-printed* non-ASCII in the benchmark rollup; the
  other em-dashes in this file are in docstrings/comments and are never printed). For completeness,
  `pipeline.py` report lines also use `—`/`×`/`³` (lines 83-87, 159, 163-171) — same UTF-8-reconfigure
  dependency, but those predate Stage 6 and are out of this stage's scope.
- User-facing: benchmark/bakeoff output whenever a case carries an error string.
- Migration: none.
- Tests to update: none known (the persisted `summary.txt`/`bakeoff.txt` are written UTF-8, so disk is safe).
**Fix path:** Match the Stage 6 ASCII convention in the benchmark rollup: `extra = f" -- {o.error}"`.
Two characters, removes the last runtime non-ASCII dependency in the benchmark text and makes the whole
3-axis rollup cp1252-safe regardless of reconfigure.

---

### UX-006 (Minor) — Bakeoff `mean_s = 0.0` for a model that ran and failed reads as "instant/fast"

**Category:** Copy (data honesty)
**Evidence:** `bakeoff.txt`: `local_qwen … 0/10 … 0.0` in the `mean_s` column. The mean wall-clock is
0.0 because every case errored at parse time (the model returned unusable output before any timed work),
so the recorded per-case duration is ~0. But a `mean_s` of `0.0` next to a real model name reads as
"blazing fast," which is the opposite of useful — the model didn't run fast, it failed early.
**Why it matters:** the speed column is a tiebreaker the recommendation logic actually uses
(`compare_runs` breaks graded ties on speed). A `0.0` from total failure is a fake "fast" that, in a
different comparison (two models that both complete few cases), could mislead the *reader* even though
the rank logic guards against it (graded rate dominates). Low exposure today; flagged for honesty.
**Fix path:** When a backend completed 0 cases, suppress or annotate the speed cell (e.g. `n/a` or a
trailing note "no completed cases timed"), consistent with the UX-002 `n/a` treatment. Don't print a
duration that implies performance the model never demonstrated.

---

### UX-007 (Nit) — `models` "Installed models" list shows raw Ollama tags with no friendly labels

**Category:** Copy
**Evidence:** The installed list prints raw tags: `- gemma4:e4b-it-q4_K_M  (9.6 GB)`,
`- novaforgeai/deepseek-coder:6.7b-optimized  (3.8 GB)`. The *recommendation* uses the friendly label
(`Gemma E4B  [gemma4:e4b]`), but the installed list above it doesn't, so the same model appears under two
guises a few lines apart (`gemma4:e4b-it-q4_K_M` vs `Gemma E4B [gemma4:e4b]`). A non-expert may not
realize they're the same family.
**Why it matters:** purely cosmetic; the raw tag is arguably the *right* thing to show in an installed
list (it's what `ollama` uses). Nit only.
**Fix path:** Optional — if a printed tag matches a catalog entry, append the friendly label in parens,
e.g. `- gemma4:e4b-it-q4_K_M  (9.6 GB)  — Gemma E4B`. Skip if it clutters; the recommendation already
bridges the two.

---

### UX-008 (Nit) — `bakeoff --help` default string embeds a parenthetical that slightly over-explains

**Category:** Copy
**Evidence:** `--backends` help: *"Comma-separated config backend keys to compare (default:
local_qwen,local = qwen vs gemma). Each must be defined under llm.backends."* The `= qwen vs gemma`
gloss is helpful, but it hard-codes the *current* mapping into help text that won't update if a backend's
model changes. Minor staleness risk.
**Why it matters:** trivial; help text drifting from config is a perennial low-grade issue. Nit.
**Fix path:** Optional — drop the `= qwen vs gemma` gloss, or move it to the command's long help where it
reads as an example rather than a contract.

---

### UX-009 (Nit) — Web plan-failure message uses an em-dash; fine on web, but note the cross-surface tone split

**Category:** Copy (consistency, cross-surface)
**Evidence:** Web copy (`designStatus.ts:45`): *"I couldn't turn that into a workable plan — the model's
response wasn't usable…"* (first-person, warm). CLI copy (`PLAN_FAILED_MESSAGE`): *"The model didn't
return a usable design plan -- its response couldn't be parsed into the required structure…"* (third-person,
technical). Both are good *for their surface*, but the voice differs (warm "I" on web vs neutral
"The model" on CLI). The CLAUDE-MD-style "talk like a person" lens would prefer the warmer first-person on
both — though a CLI being more terse/technical is a defensible deliberate choice.
**Why it matters:** not a defect — a stylistic split that's arguably correct (web = conversational, CLI =
diagnostic). Flagged once so the team decides deliberately rather than by accident. Nit.
**Fix path:** None required. If the team wants one voice, lift the web's first-person framing into the CLI
message; otherwise leave as a deliberate per-surface tone.

---

## Cross-cutting note (journey, not a numbered finding)

The Stage 6 surfaces form a coherent little decision journey: `models` (what should I run?) → `bakeoff`
(prove it before switching) → manual config edit (the human flip). That journey is *honest by design* —
nothing auto-switches, and the "it's your call" boundary is repeated at each step. The one seam is that the
two "which model is better?" signals — the advisor's static `tier` and the bakeoff's measured result — can
disagree (UX-003), and nothing on screen tells the user the advisor's "step up in quality" is a guess while
the bakeoff is evidence. Closing UX-003's wording gap stitches the journey together: the advisor would
point at the bakeoff instead of asserting a quality gain it hasn't measured.

## Do-not-flag (per brief, confirmed not raised)

Per the audit brief I did **not** raise: the model decision (gemma stays / qwen rejected — settled and
corroborated by the live `0/10` bakeoff on disk), the absence of real-hardware validation, gemma's
CPU-bound slowness, or the absence of a new GUI screen (out of Stage 6 scope). The `gemma4` vs `gemma3`
model-identity question touches the settled model decision and is left to the Principal/QA roles.
