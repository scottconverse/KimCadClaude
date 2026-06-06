# Stage 4 — Documentation Deep-Dive (backfill audit)

**Role:** Senior Technical Writer (independent)
**Scope:** Whether the docs truthfully describe the CURRENT React SPA shell + Three.js viewport + web-serving behavior delivered in Stage 4 ("React SPA shell + viewport").
**Mode:** Audit-only. No docs were edited. Severe gaps are recorded with a proposed fix, not drafted.
**Date:** 2026-06-05
**Branch reviewed:** `stage-0-7-audit-backfill` (HEAD; `main` @ `fb65e6f` is the Stage 8.5 merge).
**Method:** Read README.md, ROADMAP.md, CHANGELOG.md, HANDOFF.md, ARCHITECTURE.md, docs/README.md, docs/guide-my-designs.md, frontend/README.md, docs/design/README.md; cross-checked every load-bearing Stage-4 claim against `src/kimcad/webapp.py` and `frontend/src/**` and the committed build at `src/kimcad/web/`.

---

## Verdict

The **Stage-4-specific technical claims are accurate**: the React+TS+Vite SPA exists, compiles to a committed `src/kimcad/web/` (`index.html` + `assets/` + `vendor/`), is served verbatim by the stdlib `http.server`, the vanilla Three.js `KCViewport` loads the real exported STL via `/api/mesh/<id>`, and browser-send is honestly described as deferred. Stage 4 is well-documented at the feature level and the docs do not overclaim what Stage 4 itself delivered.

The problem is **status drift, and it is systemic and self-contradicting.** The git tags say Stage 8.5 is DONE/merged/tagged (`stage-8.5` exists; `main` head = the Stage 8.5 merge commit), but README, ROADMAP, CHANGELOG, HANDOFF, ARCHITECTURE, and the My-Designs guide all still carry "Stage 8.5 in progress / on branch / not yet merged or tagged" language — in several files **right next to** a contradicting "Stage 8.5 DONE" statement. This is the exact "one truth per doc" failure HANDOFF §7 itself records as a load-bearing lesson from the Stage-4 merge. It directly degrades a reader's ability to trust the stated stage status — including Stage 4's place in the shipped product — so it is in scope for this Stage-4 doc audit.

No Blockers. The documented Stage-4 install/launch path (`kimcad web`) works as written; nothing instructs a user to do something that fails.

---

## Severity counts

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 3 |
| Nit | 2 |
| **Total** | **8** |

---

## What's working (credit where due)

- **The Stage-4 feature description is accurate and honest.** README §"Web UI", ARCHITECTURE "The web layer", CHANGELOG "Stage 4" block, and frontend/README all describe the same true thing: a React/TS/Vite SPA compiled to committed static files, served by a dependency-free stdlib server, with "no Node needed to run." Verified against `src/kimcad/webapp.py:808` (`/` serves `index_html`), `:847` (`/assets/`), `:844` (`/vendor/`), and the committed `src/kimcad/web/index.html` (mounts `#root`, references `/assets/kimcad.js` + `/assets/index.css`).
- **The viewport claim is true.** "Vanilla Three.js `KCViewport` ... loads the REAL exported `*.oriented.stl` from `GET /api/mesh/<id>`" (CHANGELOG Stage 4 block; ARCHITECTURE) is backed by `frontend/src/viewport/KCViewport.ts` and `webapp.py:851` (`/api/mesh/` serving). Not react-three-fiber, as the ROADMAP specified.
- **Browser-send deferral is handled with unusual honesty.** README, ARCHITECTURE, frontend/README, and the CHANGELOG Stage-4 block all consistently state the SPA does "status + slice + download" only, that `/api/send` exists server-side but the SPA doesn't call it, and that the CLI/MCP are the send paths. The CHANGELOG even explicitly supersedes the now-removed Stage-2 "Web send-to-printer" item (CHANGELOG:253-256). This is a model of accurate scope-boundary documentation.
- **No Node at runtime** is stated everywhere it matters and is verifiably true (committed build output).
- **docs/README.md** is a genuinely good "what's current vs historical" index — the kind of map that keeps a doc surface trustworthy. It is, ironically, the one doc that gets the discipline right.

---

## Findings

### DOC-401 (Major) — Accuracy / Status — README status banner is stale and self-defeating for the whole product, Stage 4 included
**Evidence:** `README.md:13-23`. The status block reads: "...are in (**through Stage 7, tagged `stage-7`**). **Stage 8.5 (Usability) is in progress on branch `stage-8.5-usability` — not yet merged or tagged.**" Contradicted by `git tag` (which lists `stage-8.5`) and `git rev-parse main` = `fb65e6f` ("Merge Stage 8.5 (Usability) into main"). The actual shipped baseline is Stage 8.5, not Stage 7.
**Why this matters:** The README is the front door and the single most-read doc. A first-time reader (and any new team member) is told the product is two stages behind where it actually is. Because Stage 4 (the SPA shell + viewport) is the foundation everything above sits on, mis-stating the current stage also mis-frames where Stage 4 lives in the shipped artifact — a reader can't tell whether the SPA they're looking at is the merged one. Inaccurate status copy is the #1 trust-killer for docs.
**Blast radius:**
- Adjacent docs: same stale framing in `ROADMAP.md` (DOC-402), `CHANGELOG.md` (DOC-403), `HANDOFF.md` (DOC-404), `docs/guide-my-designs.md` (DOC-405). Single root cause: the Stage 8.5 merge updated some status statements but not the front-matter banners/feature blocks.
- User-facing: every reader of the repo landing page.
- Migration: none — copy-only fix.
- Tests: none (status prose isn't asserted by any test; that absence is itself why it drifted).
- Related findings: DOC-402, DOC-403, DOC-404, DOC-405.
**Fix path:** Update the README status block to "through Stage 8.5, tagged `stage-8.5`"; change the "Saving your work" heading (`README.md:48`, `### Saving your work *(Stage 8.5 — in progress, on branch)*`) to "(Stage 8.5 — done)" or drop the parenthetical. Coordinate as one commit with DOC-402..405 so the whole surface flips together (this is the "one truth per doc" / HANDOFF §7 discipline).

### DOC-402 (Major) — Accuracy / Status — ROADMAP contradicts itself on Stage 8.5 within the same document
**Evidence:** `ROADMAP.md:56-62` (Current baseline) states Stage 8.5 is "**DONE (merged to `main`, tagged `stage-8.5`)**" — yet the **same paragraph** at `:61` says "Stage 8.5 is currently IN PROGRESS on branch `stage-8.5-usability`", `:64` says "usability (Stage 8.5, **in progress**)", and the Stage 8.5 section header at `:214` says DONE while its body still reads as a forward-looking plan. The Stage-4 section (`:126`) is correct ("DONE — merged + tagged `stage-4`").
**Why this matters:** A doc that says both "done" and "in progress" about the same stage, two lines apart, forces the reader to guess which clause to believe — and erodes confidence in the *adjacent* stage statuses too, including the Stage-4 "DONE" line a reader is here to confirm. The ROADMAP is cited by HANDOFF as a source of truth, so the contradiction propagates.
**Blast radius:**
- Adjacent: DOC-401, DOC-403, DOC-404, DOC-405 (shared root cause).
- Migration: none — copy-only.
- Tests: none.
- Related findings: DOC-401, DOC-403.
**Fix path:** Make the ROADMAP say Stage 8.5 = DONE exactly once and consistently: fix `:61` and `:64`, and reconcile the Stage 8.5 section body (`:214-235`) so its "Status:" line (already "DONE") isn't followed by future-tense plan prose ("**Goal:**...", "**Exit:**...") that reads as not-yet-done.

### DOC-403 (Major) — Accuracy / Status — CHANGELOG "Added" entries all say "on branch, not yet merged/tagged" while the same section's header says merged + tagged
**Evidence:** `CHANGELOG.md:14-17` (Unreleased preamble) says "Stage 8.5 ... **merged to `main` and tagged `stage-8.5`**." But every Stage 8.5 *Added* entry below still carries the in-flight tag: `:50` "(on branch, not yet merged/tagged)", `:56`, `:65`, `:72`, `:77`. A changelog is the canonical record of what shipped; here the record disagrees with its own summary.
**Why this matters:** The CHANGELOG is what a returning user or an integrator consults to know what's actually released. Entries marked "not yet merged" for shipped, tagged work make the release record untrustworthy. (Per the writer severity guide, "CHANGELOG not being maintained / claims version that doesn't match reality" is Major.)
**Blast radius:**
- Adjacent: DOC-401, DOC-402, DOC-404, DOC-405.
- Migration: none.
- Tests: none.
- Related findings: DOC-401, DOC-402.
**Fix path:** Strip the "(on branch, not yet merged/tagged)" qualifiers from `CHANGELOG.md:50,56,65,72,77` now that `stage-8.5` is tagged; the `:29` consolidated "DONE" entry is correct and can stand as the canonical Stage 8.5 record.

### DOC-404 (Minor) — Accuracy / Status — HANDOFF's body contradicts its own RESUME box (acknowledged-but-uncorrected stale narrative)
**Evidence:** `HANDOFF.md:1-8` RESUME box correctly says Stage 8.5 is DONE/merged/tagged. But `:17` ("🔧 STAGE 8.5 (Usability) **IN PROGRESS** — branch `stage-8.5-usability`") and the long Slice-by-slice narrative (`:30` "RESUME HERE = Stage 8.5, Slice 11", `:67-89`) still read as live. The doc *flags* this itself at `:10-13` ("the slice-by-slice narrative below is HISTORICAL build-log detail ... stale SHAs ... do not treat its resume pointers as live").
**Why this matters:** Lower severity than DOC-401..403 because HANDOFF is a contributor/internal doc (not user-facing) and it *explicitly warns* the reader the narrative is stale, which limits the harm. But a new team member still has to wade through contradictory live-looking pointers. The self-warning is a mitigation, not a fix.
**Blast radius:**
- Adjacent: DOC-401..403, DOC-405.
- User-facing: none (internal handoff).
- Related findings: DOC-401.
**Fix path:** Either archive the historical slice narrative below the RESUME box into a `docs/audits/...` or `*-build-log.md` and leave HANDOFF as the short RESUME box + ledger pointer, or hard-flip `:17` to "DONE". The RESUME box + RUN-LEDGER are already designated source of truth, so trimming the contradicting body is the cleaner move.

### DOC-405 (Minor) — Accuracy / Status — My-Designs user guide is stamped "not yet merged/tagged" for shipped functionality
**Evidence:** `docs/guide-my-designs.md:3` — "*Stage 8.5 Slice 1 — implemented on branch `stage-8.5-usability` (not yet merged/tagged).*" The feature is merged + tagged.
**Why this matters:** This is a *user-facing* guide (linked from the README). A user reading "not yet merged/tagged" may reasonably conclude the auto-save / library they're being told about isn't actually available — undercutting a feature that does ship. Lower than DOC-401 only because the guide body itself is accurate and clear; the stale stamp is one line.
**Blast radius:**
- Adjacent: DOC-401 (README links here and shares the stale framing).
- User-facing: anyone following the README's "Saving your work" link.
- Related findings: DOC-401.
**Fix path:** Remove the parenthetical or change to "(Stage 8.5 — shipped)".

### DOC-406 (Minor) — Completeness / Onboarding — No user-facing explanation of *what the viewport shows or how to drive it*, and demo-vs-real is under-documented
**Evidence:** The viewport is described richly only in `docs/design/README.md:182` (a design spec for builders, not users) and in CHANGELOG/ARCHITECTURE as "orbit / zoom / auto-rotate." The README's user-facing Web UI section (`README.md:151-178`) says only "a 3D preview of the rendered model" — it never tells a real user the viewport is interactive (drag to orbit, scroll to zoom), what the dimension labels/bounding box mean, or how to read it. Demo mode is mentioned in exactly one clause (`README.md:160-162`, `--demo` "serves a fixed sample part instantly with no model call") with no explanation of how a user tells demo output apart from a real run. (Code confirms demo is real and labels itself: `webapp.py:1820` appends "(demo mode — no LLM)" to the response.)
**Why this matters:** Stage 4's headline deliverable is "a real 3D viewport." For the first-time-user persona, there is no user manual entry for the single most visible Stage-4 surface — they get a viewport with no instructions on what it is or how to interact with it, and no clear framing of demo vs. real. The design-spec description is the wrong altitude (it's for the team, not the user). This is a completeness gap, not an inaccuracy.
**Blast radius:**
- Adjacent: pairs with the QA/UX lanes if they flag the viewport's in-app affordance (the "drag to rotate · scroll to zoom" hint lives in the prototype design but its presence in the shipped SPA should be confirmed by those lanes).
- User-facing: every web-UI user.
- Migration: none — additive doc.
- Tests: none.
**Fix path:** Add a short "Using the viewport" subsection to the README Web UI section (or a `docs/guide-web-ui.md`): one paragraph on orbit/zoom/auto-rotate + what the dimension pills and bounding box mean, and one sentence distinguishing a `--demo` sample (labeled "demo mode — no LLM") from a real model run. Audit+draft would warrant a `doc-rewrites/guide-web-ui.md`; recorded here as a NOTE, not drafted (audit-only mode).

### DOC-407 (Nit) — Architecture / Completeness — ARCHITECTURE labels Stage 8.5 web endpoints "on the `stage-8.5-usability` branch" though they're merged
**Evidence:** `ARCHITECTURE.md:160` — "**Stage 8.5 additions (on the `stage-8.5-usability` branch):**". The endpoints (`/api/designs*`, `/api/settings`, `/api/render`, etc.) are merged. Nit (not Minor) because ARCHITECTURE is internal and the endpoint descriptions themselves are accurate against `webapp.py` (verified: `/api/render` at `:1018`, `/api/designs/save` at `:1025`, `/api/settings` at `:1009`, `/api/photo-seed` at `:1012`).
**Fix path:** Drop "(on the `stage-8.5-usability` branch)".

### DOC-408 (Nit) — Accuracy — frontend/README dev-server note slightly understates current build pipeline
**Evidence:** `frontend/README.md:39` describes `npm run build` as "tsc --noEmit (typecheck) + vite build." Minor wording — accurate enough — but the README elsewhere (`README.md:75`) tells users to run `npm --prefix frontend ci && npm --prefix frontend run build`, and the two are consistent. No correctness issue; flagged only because frontend/README's documented `/api/...` list (`:18-23`) predates the Stage 5–8.5 endpoint growth and could mislead a contributor into thinking the contract is frozen at the Stage-4 set.
**Fix path:** Add one line to frontend/README §"How it fits together" pointing at ARCHITECTURE.md as the authoritative, current route list (ARCHITECTURE already self-describes as authoritative — HANDOFF:318).

---

## Cross-role blast-radius note (for the orchestrator)

DOC-401 through DOC-405 are **one root cause** — the Stage 8.5 merge flipped some status statements but left the front-matter banners, the CHANGELOG "Added" qualifiers, and a user-guide stamp at "in progress." Fix them in a **single coordinated commit** so the surface flips atomically; otherwise the next reader hits a fresh contradiction. This is precisely the failure HANDOFF §7 records ("One truth per doc... Scott caught HANDOFF + ROADMAP self-contradicting after the Stage-4 merge"), recurring one stage later — worth promoting as a process finding: **status statements drift because no test or check asserts them.** A lightweight guard (a doc-lint that greps for "not yet merged/tagged" / "in progress" co-occurring with a matching `git tag`, or a single canonical status line the others reference) would prevent the next recurrence.

The Stage-4 *feature* docs are sound; the debt is entirely in stage-status hygiene plus one onboarding gap (DOC-406, the missing user-facing viewport guide).
