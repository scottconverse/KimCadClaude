# Technical Writer — Deep Dive (Stage 8.5 escape-paths sweep)

**Role:** Senior Technical Writer (docs). Audit-only for this gate — flag, don't rewrite.
**Date:** 2026-06-04
**Scope under audit:** `git diff 8618027..HEAD` on `stage-8.5-usability` — the escape-paths sweep
(Cancel/abort on every blocking action, an elapsed timer + Esc on the "Designing…" overlay, and
honest "runs on your computer's AI, can take a few minutes" copy). This is a **user-facing behavior
change**, so the question is: does any existing doc now misstate reality, and is the user-facing change
recorded where a reader would look (the CHANGELOG)?
**Posture:** balanced. I verified each claim against the source before flagging (quotes below).

**Docs reviewed:** `CHANGELOG.md`, `README.md`, `HANDOFF.md`, `docs/stage-8.5-usability-plan.md`, the
committed slice audit-lites (`docs/audits/stage-8.5/audit-lite-escape-*`), and the changed-code
inline docstrings/comments.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 2 |
| Nit      | 0 |
| **Total** | **3** |

No doc claims the escape stage is "done/merged/tagged" (the one hard prohibition — clean). The
findings are: an undocumented user-facing change in the CHANGELOG (Major), a now-stale HANDOFF resume
pointer (Minor), and a plan-internal-consistency gap (Minor).

---

## Findings

### DOC-ESC-001 — Major — The escape-paths sweep is undocumented in CHANGELOG `[Unreleased]`
**Category:** Completeness / Accuracy
**Evidence:** `CHANGELOG.md` `[Unreleased]` → `### Added` lists Stage 8.5 Slices 1, 2–4, 6, and 7
(lines 27–62), each with an "(on branch, not yet merged/tagged)" tag. There is **no entry** for the
escape-paths sweep — nothing states that long/blocking actions are now cancelable, that the
"Designing…" screen shows a live elapsed timer + Esc-to-cancel, or that the photo read / slice /
import each gained a Cancel. The sweep is a real, shipped (on-branch), user-facing behavior change —
two commits (`5118918`, `7fb2642`) touching the design overlay, photo on-ramp, slicing, importing,
and the honest "runs on your computer's AI, can take a few minutes; you can cancel anytime" copy
(now live in `ChatPanel.tsx` and `Viewport.tsx`). Per the Technical Writer brief and the project's
own Keep-a-Changelog format, a user-facing change belongs under `[Unreleased]`. Its absence is the
one genuine documentation gap in this change.
**Why this matters:** The returning user / reviewer scanning the CHANGELOG to see "what changed on the
branch" would not learn that blocking actions are now escapable — the single most user-visible effect
of this work. Inaccurate-by-omission for a behavior change; trust in the CHANGELOG as the change record
erodes when a visible behavior shift isn't recorded.
**Blast radius:**
- Adjacent docs: none repeat the error; `README.md` and `HANDOFF.md` also omit the escape behavior but
  their omission is separately tracked (DOC-ESC-002) / acceptable (README is a status summary, not a
  per-change log).
- User-facing: the change is real and shipping toward the `0.1.0` release notes; an un-logged change
  tends to be missed at release-notes assembly.
- Migration: none.
- Tests to update: none.
- Related findings: DOC-ESC-002 (stale HANDOFF pointer), DOC-ESC-003 (plan consistency) — same root:
  the escape sweep landed without its doc trail.
**Fix path:** Add one `### Added` bullet under `[Unreleased]`, in the established voice and with the
"(on branch, not yet merged/tagged)" tag, e.g.: *"Stage 8.5 escape-paths sweep (on branch, not yet
merged/tagged): every long or blocking action can now be cancelled — the 'Designing…' screen shows a
live elapsed timer and a Cancel button (and Esc cancels too), and the photo read, slicing, and
importing each gained a Cancel. A cancel releases the UI immediately; the local model may finish its
current pass in the background. Honest copy added: long actions 'run on your computer's AI [and] can
take a few minutes.'"*

### DOC-ESC-002 — Minor — HANDOFF resume pointer is stale: doesn't reflect the escape sweep being built ahead of Slice 8
**Category:** Accuracy
**Evidence:** `HANDOFF.md` line 18: **"RESUME HERE = Stage 8.5, Slice 8 (problems on the model)."**
Lines 19–25 enumerate "Slices 1–7 are built on branch `stage-8.5-usability` and gated 0/0/0/0/0 … Slice
7 is now gated and pending Scott's walkthrough" — and stop there. The doc has no mention that an
**escape-paths sweep was inserted ahead of Slice 8** (per Scott's direction) and has since been built
and is at its own slice-end `audit-team` gate (this audit). So a reader resuming from HANDOFF would
think the next action is Slice 8 with nothing between Slice 7 and it — when in fact the escape sweep
was done in between. The top banner (lines 1, 5–6) is correct that Stage 8.5 is in progress / not
merged/tagged, so this is a *currency* gap, not a contradiction.
**Why this matters:** The new-team-member / next-session persona uses HANDOFF as the single source of
truth for "where am I." A resume pointer that silently skips the most recent work done is exactly the
"one truth per doc" lesson the HANDOFF itself records (§7). It risks a duplicated or out-of-order
effort.
**Blast radius:**
- Adjacent docs: `docs/stage-8.5-usability-plan.md` (DOC-ESC-003) shares the same gap — neither
  records the inserted escape sweep.
- User-facing: none (internal handoff doc).
- Migration: none.
- Related findings: DOC-ESC-001, DOC-ESC-003.
**Fix path:** When the escape stage clears its gate, update the HANDOFF resume line to note the
escape-paths sweep was inserted ahead of Slice 8, built, and gated (pending Scott's approval), and that
**RESUME = Slice 8** stands once approved. Keep the "not merged/tagged" truth. (Audit-only here — flag,
don't rewrite.)

### DOC-ESC-003 — Minor — Usability plan doesn't note the escape sweep was inserted ahead of Slice 8; its scope overlaps Slice 9
**Category:** Accuracy / Completeness
**Evidence:** `docs/stage-8.5-usability-plan.md` lists Slice 8 ("Show problems on the model," line 96)
and Slice 9 ("Onboarding, the model-down wall, progress, help," line 102). **Slice 9** explicitly owns
the very behavior this sweep just implemented — line 105: *"Real progress on long runs — a CPU model
call takes minutes; today it's one spinner + 'Designing your part…', which reads as frozen. Show steps
… and 'this can take a minute on your hardware.'"* The escape sweep shipped the elapsed timer + the
"can take a few minutes" copy + a Cancel on the design overlay — i.e. it delivered part of Slice 9's
"real progress on long runs" item early, and added the cancel/escape theme across slices, **but the
plan has no note that an escape sweep was inserted ahead of Slice 8** or that it pre-empts a piece of
Slice 9. As written, the plan is internally *consistent* only if a reader already knows the sweep
happened out-of-band; on its face it still implies the elapsed-timer/progress work is wholly ahead in
Slice 9.
**Why this matters:** Whoever picks up Slice 9 could re-build the elapsed timer / "takes a few minutes"
progress copy that already shipped, or be confused about what's left. The plan is the work map; an
inserted cross-cutting sweep that satisfies part of a later slice should be annotated so the later
slice's remaining scope is clear (steps: planning → generating → rendering → validating, and the
model-down wall, are still open; the elapsed timer + honest copy + cancel are done).
**Blast radius:**
- Adjacent docs: HANDOFF (DOC-ESC-002) shares the gap.
- User-facing: none.
- Migration: none.
- Related findings: DOC-ESC-001, DOC-ESC-002.
**Fix path:** Add a short note to the plan (e.g. a line under the Process section or a Slice 8/9
preamble) recording that the escape-paths sweep was inserted ahead of Slice 8 at Scott's direction, and
that it delivered the design-overlay elapsed timer + "runs on your computer's AI, can take a few
minutes" copy + Cancel/Esc — so Slice 9's remaining scope is the **stepped** progress, the model-down
wall, first-run setup, and help, not the elapsed-timer/cancel piece. (Audit-only — flag, don't rewrite.)

---

## Verified accurate (claims I checked and did NOT flag)

- **No doc claims the escape stage is done/merged/tagged.** Verified: `git tag` shows only
  `stage-0`…`stage-7`; HEAD carries no tag. `CHANGELOG.md` line 14 and `README.md` line 16 both say
  Stage 8.5 is **"IN PROGRESS … not yet merged or tagged."** `HANDOFF.md` lines 5–6, 26 say the same.
  The hard prohibition is satisfied.
- **README status block is accurate, not inaccurate.** `README.md` lines 16–23 list the in-progress
  Stage 8.5 features (persistence, refine-as-conversation, numeric entry, mm/inch, Settings, photo
  on-ramp) and correctly mark them on-branch. It does not mention the escape behavior, but the README
  status block is a curated *summary*, not a per-change log — its omission is not an inaccuracy (no
  false claim), so it is **not** flagged. (The CHANGELOG is the right home for the change record —
  DOC-ESC-001.)
- **Inline docstrings/comments in the changed code are accurate and honest.** Verified against the
  diff:
  - `api.ts` `postDesign` comment: *"a design can run the local model for minutes, so the user must be
    able to cancel and escape the 'Designing…' screen."* — matches behavior.
  - `api.ts` `isAbortError` docstring correctly scopes it to the aborted-fetch error vs a real failure.
  - `App.tsx` `handleCancelDesign` docstring states the honest server-side truth: *"the local model
    may finish its current pass in the background, but the user is no longer stuck waiting on it."* —
    this is exactly the correct "client-abort releases the UI; server may finish" framing.
  - The superseded-design comment ("a newer design replaced this one — drop the result") and the
    `designSeq` guard comment accurately describe the race protection.
  - `styles.css` comment explains the compound-selector `pointer-events: auto` override
    ("a CSS reorder must never silently re-trap the user") — accurate and load-bearing.
  - The new UI copy is honest and matches the diff: `Viewport.tsx` *"This runs on your computer's AI —
    it can take a few minutes … Nothing leaves your machine"*; `ChatPanel.tsx` *"It writes the design
    on your computer's AI, so it can take a few minutes; you can cancel anytime"*; `PhotoOnramp.tsx`
    *"This can take a moment on your computer's AI."* None over-promise (none claim a cancel kills the
    background job).
- **The committed slice audit-lites are accurate to the code.** `audit-lite-escape-sweep-2026-06-04.md`
  flagged ESC-SWEEP-001 (MyDesigns missing unmount-abort) and ESC-SWEEP-002 (missing `.kc-slice-actions`
  CSS); **both are fixed in the final commit** — `MyDesigns.tsx` now has
  `useEffect(() => () => importAbortRef.current?.abort(), [])` and `styles.css` now defines
  `.kc-slice-actions { display: flex; gap: 8px; align-items: center; }`. So those audit-lite findings
  are closed in-code and are not re-raised here.

---

## Out of scope (documented decisions — not flagged, per the brief)

- Save gets no Cancel (non-blocking commit); model-pull has no in-app action; the global timeout is
  deferred to its own slice. These are sound, documented decisions — the audit-lite records them and I
  do not re-litigate them.
- No demand for brand-new end-user docs mid-stage. The only doc-creation flagged is a one-line
  CHANGELOG entry for a user-facing change (DOC-ESC-001) — explicitly in scope — plus two currency
  fixes to existing internal docs.
