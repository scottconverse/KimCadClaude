# Documentation Deep-Dive — KimCad, Stage 9 (vision on-ramps)

**Audit date:** 2026-06-10
**Role:** Technical Writer
**Scope audited:** Stage 9 documentation at commit `e8339d9` — `docs/benchmarks/stage-9-vision-onramps.md` (claims verified against shipped code), README two-pull Setup + vision claims, `docs/getting-started-windows.md` Step 2, `docs/troubleshooting.md` (two new vision entries), `docs/guide-photo-onramp.md` (vision-model rewrite), the first-run-wizard copy, plus cross-doc consistency (gemma4-vision residue, sketch-guide coverage, ROADMAP Stage 9 status, CHANGELOG).
**Writer mode:** audit-only
**Auditor posture:** Balanced

---

## TL;DR

The Stage 9 documentation that was touched is in very good shape: every load-bearing claim in the new benchmark doc checks out against the shipped code line-for-line (config default, the typed `VisionModelMissing` message, `kimcad models` output, `_describe_image` targeting `vision_model`), the README/getting-started two-pull setup is accurate and honest, and the troubleshooting entry's quoted error text exactly matches the string the product emits. The problems are in what *wasn't* touched: two current-indexed surfaces still teach that `gemma4:e4b` reads images (the Settings guide's "one tested local model" and the design control-plane's superseded-posture banner — the very capability Stage 9 proved broken), and the shipped sketch on-ramp has no user guide at all. ROADMAP/README status and the CHANGELOG entry are owed at the tag, as expected for this repo's conventions. No Blockers, no Criticals: a first-time user following the docs today succeeds.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 4 |
| Minor | 4 |
| Nit | 0 |

## What's working

- **The benchmark doc's shipped-code claims are all true — verified, not assumed.**
  `docs/benchmarks/stage-9-vision-onramps.md` ("Shipped accordingly: …") vs the code:
  - `vision_model: qwen2.5vl:3b` default — `src/kimcad/config.py:81` (`vision_model: str = "qwen2.5vl:3b"`), `config/default.yaml:66`, config-overridable via `config.py:306` (`b.get("vision_model", …)`). ✓
  - `_describe_image` targets it — `src/kimcad/llm_provider.py:387` sends `"model": self.backend.vision_model` (test `tests/test_llm_provider.py:300` pins "NOT the chat model"). ✓
  - Missing pull surfaces as a typed "ollama pull qwen2.5vl:3b" message, never "your image was unreadable" — `llm_provider.py:51-61` (`VisionModelMissing`), and **both** web endpoints map it to `status: model_unavailable` before the generic "Couldn't read that photo/sketch" 422 can fire (`src/kimcad/webapp.py:1395-1397`, `:1431-1433`; test `tests/test_webapp.py:3156`). ✓
  - `kimcad models` reports the vision model's install state — `src/kimcad/cli.py:507-515` prints `Vision model (photo/sketch on-ramps): qwen2.5vl:3b (installed | NOT installed -- ollama pull qwen2.5vl:3b)`. ✓
- **The benchmark doc is honest where honesty was hard.** Finding 1 states plainly that the Stage 8.5 photo on-ramp "never worked against the real pinned model on this stack — every working impression came from demo mode." Finding 3 descopes photo→3D reconstruction with concrete hardware reasoning and explicitly maps the verdict onto ROADMAP's own exit criterion. The disk-footprint note even tells the user how to remove the diagnostic moondream pull. This is exactly the candor the severity framework asks for.
- **Troubleshooting's new vision entries quote the real strings.** The heading `"KimCad's vision model isn't pulled yet"` (`docs/troubleshooting.md:38`) is verbatim the `VisionModelMissing` message prefix (`llm_provider.py:60`), the fix is the exact pull command, and it correctly notes the separate-pull nature and that `kimcad models` shows both models' status. The second entry (empty read → outdated Ollama / low-contrast image, `troubleshooting.md:51-57`) covers both photo *and* sketch and matches `guide-photo-onramp.md`'s "If it returns nothing" advice — consistent across surfaces.
- **README Setup's two-pull block is accurate and well-motivated.** `README.md:128-137` gives both pulls, explains *why* the second exists (gemma4's vision broken on this stack, with the model's own "no image was provided" admission), cites the benchmark doc, and re-states the local-only promise ("Both run in the same local Ollama; images never leave the machine").
- **getting-started Step 2 is genuinely non-developer-shaped.** `docs/getting-started-windows.md:39-55`: "pull KimCad's two AI models — the designer (~5–10 GB, the big download) and the small vision model that reads photos and sketches (~3 GB)", with a check step (`ollama list` should show both) and the `kimcad models` cross-confirmation. The ~3 GB figure matches the benchmark's 3.2 GB.
- **The guide-photo-onramp rewrite names the right model in the right place.** `docs/guide-photo-onramp.md:9-11`: the privacy promise now reads "a small local vision model (`qwen2.5vl:3b`, running in the same Ollama as the design model)" — corrected without breaking the guide's plain-words register.
- **The wizard copy threads a hard needle.** `frontend/src/components/FirstRunWizard.tsx:244-249` presents one model card and adds the vision model as a companion, not an alternative: "It's the tested default for designing parts; a separate small local vision model reads photos and sketches (`qwen2.5vl:3b` — pulled the same way)." The follow-up commit (`2dbcfc4`) pinned that intent in a test (`FirstRunWizard.test.tsx:52`) so the no-model-menu rule can't regress silently. That's documentation discipline applied to UI copy.
- **Error copy never blames the user's image for a setup problem.** The web layer's comments and behavior (`webapp.py:1388-1391`) and the on-ramp's client copy (`PhotoOnramp.tsx:49`) consistently distinguish "your sketch was unreadable" from "your AI isn't running / isn't pulled" — the trust-preserving distinction the docs promise ("it never blames your photo for a stopped server", `guide-photo-onramp.md:38`).

## What couldn't be assessed

- **The benchmark's measured numbers** (timings, the 5/5 end-to-end read, the probe transcripts). The harness scripts are disclosed as living outside the repo ("audit scratch"), so the numbers can't be re-derived from the repo. The doc is upfront about this; flagged as DOC-006 (Minor), not as an accuracy finding.
- **Live wizard rendering** — copy audited from source + tests; no live walkthrough run in this writer lane (the QA lane covers runtime).

---

## Doc asset inventory (Stage 9 scope)

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| `docs/benchmarks/stage-9-vision-onramps.md` | Yes | Strong — all shipped-code claims verified | DOC-006 |
| README Setup (two-pull) + vision claims | Yes | Strong | DOC-005 (status para only) |
| `docs/getting-started-windows.md` Step 2 | Yes | Strong | DOC-007 (disk estimate) |
| `docs/troubleshooting.md` vision entries | Yes | Strong | — |
| `docs/guide-photo-onramp.md` | Yes | Adequate — accurate for photo; silent on sketch | DOC-003 |
| Sketch on-ramp user guide | **No** | Missing for a shipped feature | DOC-003 |
| Wizard copy | Yes | Strong, test-pinned | — |
| `docs/guide-settings-and-cloud.md` | Yes | **Stale** — "one tested local model" | DOC-001 |
| `docs/design/` control plane (README banner, spec v3.0, stage-8.5 plan) | Yes | **Stale** — still asserts gemma4 vision as settled | DOC-002 |
| CHANGELOG Stage 9 entry | No (known) | Owed at the tag | DOC-004 |
| ROADMAP Stage 9 status / README status para | Stale | Owed at the tag | DOC-005 |
| `ARCHITECTURE.md` | Yes | Partially updated (`describe_sketch` yes; route list + vision-model story no) | DOC-008 |

---

## Persona walk-through

### First-time user
Succeeds. getting-started's Step 2 pulls both models with honest sizes and a check step; if they skip the second pull, the product tells them the exact recovery command and troubleshooting carries the same words. The only wrinkle: the "about 15 GB free" guidance is now tight (DOC-007).

### Returning user
Mostly succeeds. A photo question lands in `guide-photo-onramp.md` and gets accurate answers. A *sketch* question has no guide to land in — `docs/README.md`'s index doesn't say the word "sketch" anywhere (DOC-003). A "what does Settings show me?" question hits the stale "one tested local model" line (DOC-001).

### New team member
At risk of building to the wrong model. `docs/README.md:8` says of `docs/design/`: "Build to this" — and that bundle's superseded-posture banner still declares `gemma4:e4b` is THE model for "text, codegen, AND vision" and that the photo is "read by **gemma4:e4b's local vision**" (DOC-002). Stage 9's central finding is that this exact claim is false on the target stack. The benchmark doc and ARCHITECTURE partially correct the record, but the doc that's labeled authoritative contradicts them.

---

## Findings

> **Finding ID prefix:** `DOC-`

### [DOC-001] — Major — Accuracy — The Settings guide still says KimCad runs "one tested local model (`gemma4:e4b`)"

**Evidence**
`docs/guide-settings-and-cloud.md:14-18` ("The AI model" section):
> "A health readout, not a menu: KimCad runs one tested local model (`gemma4:e4b` via Ollama). Settings shows whether it's running and pulled…"

This is a current-facing user guide (indexed under "Current (read these)" in `docs/README.md:13`). Since Stage 9, KimCad runs **two** tested local models, and the photo/sketch features depend on the second one. The same guide's cloud section ("**Never your photo** — the photo on-ramp always stays local", line 27-28) implicitly attributes the photo read to that "one model."

**Why this matters**
The returning user diagnosing a photo/sketch failure from this guide will conclude the only model that matters is `gemma4:e4b`, check that it's pulled, and stay stuck — the missing piece (`qwen2.5vl:3b`) isn't mentioned anywhere in the doc that explains the AI surface. It also quietly re-implies the claim Stage 9 disproved: that gemma reads the photos.

**Blast radius**
- Other docs that repeat the error: this is the only *user-guide* instance; the design-plane instances are DOC-002.
- User-facing: the Settings screen itself shows only the chat model's status (no vision-model row in `frontend/src` Settings surfaces), so guide and UI currently agree with each other while both lag the product — fixing the guide may surface a product question (should Settings show the vision model's state too?) that belongs to the dev/UX lanes, not this one.
- Related findings: DOC-002, DOC-003.

**Fix path**
Two-sentence amendment to "The AI model": KimCad runs two tested local models — `gemma4:e4b` for designing and a small dedicated vision model (`qwen2.5vl:3b`) that reads photos and sketches; both local, both via Ollama; `kimcad models` (or the wizard) confirms both. Keep "a health readout, not a menu" — it's still the right framing.

### [DOC-002] — Major — Accuracy — The design control plane, indexed as "Build to this," still asserts gemma4:e4b's vision as a settled, load-bearing decision

**Evidence**
- `docs/README.md:8`: "`design/` — the controlling UI/UX design + the v3.0 product spec … **Build to this.**"
- `docs/design/README.md:3-14` (the "⚠ SUPERSEDED POSTURE" banner, i.e. the part that presents itself as the *corrected, settled* truth): "`gemma4:e4b` is THE default and the only model the UI presents (text, codegen, AND vision)" and "the photo is read by **gemma4:e4b's local vision** by default."
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md:272` (likewise a correction note, not the superseded original): Gemma "**doubles as the local vision fallback** for the image on-ramp (§6.10)"; same story at lines 40 and 243.
- `docs/stage-8.5-usability-plan.md:78,82,96` — indexed as current/authoritative at `docs/README.md:9` — "**gemma4:e4b is the only default** — text, codegen, **and vision** (the photo on-ramp uses *its* vision)."

**Why this matters**
These banners exist precisely to stop people from building to stale decisions — and they now *are* the stale decision. A new team member (or a future agent session) following the index's "Build to this" instruction lands on an authoritative-voiced claim that Stage 9 measured to be false on the target stack (`stage-9-vision-onramps.md` Finding 1). The failure mode isn't hypothetical: this repo's workflow leans heavily on these control-plane docs as session-cold context.

**Blast radius**
- Adjacent docs: `docs/design/README.md` (banner + tech table line 56 "local Gemma (§6.10)"), spec v3.0 (lines 40, 243, 272, 275 context), `docs/stage-8.5-usability-plan.md`, `docs/design/stage-8.5-slice-5-onramps.md` (already listed as historical at `docs/README.md:24` — needs no edit), `docs/design/prototype/slice-5-onramps.html:140,273` (prototype copy — historical, banner-covered once the banner is fixed).
- Shared assumption: "one model does everything" is also DOC-001's root; fix both in one pass.
- User-facing: none directly (internal docs), but it steers future build work.
- Migration: none — additive correction notes in the same ⚠-banner style the repo already uses (don't rewrite the superseded originals; extend the banners: "Stage 9 superseded the vision half of this decision: gemma4:e4b's vision is broken on this stack; a dedicated local vision model `qwen2.5vl:3b` reads images — see `docs/benchmarks/stage-9-vision-onramps.md`").
- Related findings: DOC-001, DOC-004 (the CHANGELOG entry should record the same correction); also consider reclassifying `stage-8.5-usability-plan.md` from "Current" to "Historical" in `docs/README.md` now that Stage 8.5 is tagged — it's a completed-stage plan.

**Fix path**
One short Stage-9 correction block added to each of: `docs/design/README.md` banner, the spec's CONTROL-PLANE/correction notes (lines 264/272 vicinity), and either a banner on `stage-8.5-usability-plan.md` or its move to the Historical list. ~10 lines total across three files.

### [DOC-003] — Major — Completeness / Onboarding — The sketch on-ramp shipped with no user guide, and the docs index never says "sketch"

**Evidence**
- The sketch on-ramp is shipped and user-visible (`frontend/src/components/Landing.tsx:104` — `kind="sketch"` on the Landing; `POST /api/sketch-seed` in `webapp.py:1410`).
- `docs/guide-photo-onramp.md` is photo-only: title "Starting a design from a photo"; every instruction says photo; nothing tells the user that sketches are read differently (dimensions read **as written**, not estimated — the copy table distinction the UI itself makes, `PhotoOnramp.tsx:33-50`).
- `docs/README.md:12` indexes only "`guide-photo-onramp.md` — … starting a design from a photo"; the word "sketch" appears nowhere in the index.
- Meanwhile `getting-started-windows.md:41` and `troubleshooting.md:39-49` both already say "photos **and sketches**" — so the doc set promises a capability the guides never explain.

**Why this matters**
The sketch path is Stage 9's *primary* deliverable (ROADMAP: "Sketch path first"), and its key user-facing behavior — write your dimensions on the sketch and they're read literally, vs. a photo's estimates — is exactly the kind of thing a guide exists to teach. A returning user who saw "Start from a sketch" on the landing page and wants to know what makes a good sketch (labels? units? line weight?) has nowhere to look.

**Blast radius**
- Adjacent docs: `docs/README.md` index entry; README's feature paragraph (mentions photo by name, sketch only as "image/sketch on-ramp (Stage 9)" in the stale status line — DOC-005).
- User-facing: discoverability of the sketch feature's contract (read-as-written dims, 12 MB cap, PNG/JPEG, the same local-only promise).
- Related findings: DOC-005 (the README status rewrite at the tag should name both on-ramps as shipped).

**Fix path**
Recommend **extending `guide-photo-onramp.md` to cover both on-ramps** rather than a separate sketch guide: the flow, the privacy promise, the cancel/limits, and the failure modes are shared (one component, one copy table in the code — the doc should mirror that structure). Retitle to "Starting a design from a photo or a sketch," add a short "Photos vs. sketches" section (estimates vs. read-as-written; what a good sketch looks like — clear written dimensions, e.g. "80 mm", one part per page), and update the `docs/README.md` index line. A separate guide is defensible if the team prefers one-page-per-feature, but it would duplicate the promise and failure-mode text nearly verbatim.

### [DOC-004] — Major — Hygiene / Accuracy — CHANGELOG owes the Stage 9 entry, including the correction of the Stage 8.5 photo-on-ramp claim *(KNOWN — developer writes it at the tag)*

**Evidence**
- `CHANGELOG.md` has no Stage 9 entry (latest substantive entries are Stage 8.5/8).
- `CHANGELOG.md:111` (the Stage 8.5 entry) records: "reads a photo with gemma4:e4b's **local** vision" — which Stage 9 established never actually worked against the real model on this stack.

**Why this matters**
This repo's changelog has been a genuinely reliable record (the Stage-0 audit used it to *resolve* doc conflicts). Stage 9 contains a user-visible defect fix (the photo on-ramp now actually works), a new required setup step (the second pull), and a new error surface — the three things changelogs exist for. The 8.5 entry's gemma-vision line is now a known-false record; convention says don't rewrite history, but the Stage 9 entry must carry the correction explicitly or the changelog silently contradicts itself.

**Blast radius**
- Adjacent docs: none repeat it; the entry is the single record.
- User-facing: anyone upgrading from `stage-8.5` needs the "you must now also `ollama pull qwen2.5vl:3b`" note — this is effectively a **setup-requirements change** and belongs at the top of the entry.
- Related findings: DOC-002 (same correction, control-plane side), DOC-005 (same tag-time package).

**Fix path**
At the tag: a Stage 9 entry covering (1) the gemma4-vision defect + the dedicated `vision_model` fix (cite the benchmark doc), (2) the new second pull as a requirements change, (3) the sketch on-ramp, (4) the typed `VisionModelMissing` surfaces (`kimcad models`, both endpoints), (5) the photo→3D descope verdict, and a one-line pointer back correcting the 8.5 entry's vision claim.

### [DOC-005] — Minor — Hygiene — ROADMAP still says "Next = Stage 9," and the README's status paragraph now contradicts its own Setup section

**Evidence**
- `ROADMAP.md:65-66`: "**Next = Stage 9 (image/sketch on-ramp).**"; `ROADMAP.md:68`: "Still ahead before beta: image on-ramp (Stage 9)…"; the Stage 9 section (`ROADMAP.md:272-282`) carries no status marker while every completed stage above it has ✅/DONE.
- `README.md:27`: "Next up: an image/sketch on-ramp (Stage 9)…" — in the same file whose Setup section (lines 128-137) already documents Stage 9's shipped vision model and cites the Stage 9 benchmark.
- `HANDOFF.md` resume box likewise says "next = Stage 9" (consistent with the same convention).

**Why this matters**
Verified as the prompt asked: yes, the baseline still says "Next = Stage 9." This is the repo's update-at-tag convention (status lines move when the stage merges and tags), so it's expected mid-gate — but the README is now *internally* inconsistent today: a first-time reader is told a feature is "next up" three paragraphs before being told to install its model. Mildly confusing, not misleading about capability (it understates rather than overclaims).

**Blast radius** *(optional for Minor; included because three files move together)*
- Files in the tag-time package: `ROADMAP.md` (status para + a ✅/exit-met block for Stage 9, noting the descope branch of the exit criterion was exercised honestly per the benchmark doc), `README.md:27` status sentence, `HANDOFF.md` resume box, plus DOC-004's CHANGELOG entry.
- Related findings: DOC-003 (the rewritten status line should name the sketch on-ramp as shipped, with a guide to point at), DOC-004.

**Fix path**
At the tag, as a single pass. The ROADMAP Stage 9 exit line should explicitly record the photo→3D "not-viable on this hardware" verdict so the roadmap's own exit criterion is visibly closed on the branch that was taken.

### [DOC-006] — Minor — Completeness — The Stage 9 benchmark isn't reproducible from the repo

**Evidence**
`docs/benchmarks/stage-9-vision-onramps.md:3`: "Harness scripts live outside the repo (audit scratch); every number below is a real timed run on this machine."

**Why this matters**
The repo's other benchmark docs set a higher bar — `stage-6-model-bakeoff.md` includes a "how to re-run it" section (preconditions + commands), and `stage-8-cadquery-backend.md` likewise. Stage 9's numbers (the broken-vision probes especially) are the evidence behind a default-config decision and a Critical-defect claim; if Ollama or the model tags shift, no one can re-derive them. The disclosure is honest, which is why this is Minor and not an accuracy finding.

**Fix path**
Either commit the small PIL sketch-generator + probe script (it's a few dozen lines by the doc's description) under `bench/` or `scripts/`, or add a "to re-run" section describing the probes precisely enough to reconstruct (the request shapes are already half-described in the Finding 1 table).

### [DOC-007] — Minor — Accuracy — getting-started's disk-space guidance wasn't updated for the second model

**Evidence**
`docs/getting-started-windows.md:14-15`: "about **15 GB free disk space** (most of it for the AI model)" — singular "model." Actual footprint now: 9.6 GB (gemma4) + 3.2 GB (qwen2.5vl) ≈ 12.8 GB of models, plus ~200 MB tools, the Python venv, and design output. 15 GB is now a near-exact fit, not a comfortable bound.

**Why this matters**
A first-time user on a small SSD who clears exactly 15 GB can land in a mid-pull disk-full failure — the one failure class troubleshooting has no entry for.

**Fix path**
"about **20 GB free disk space** (most of it for the two AI models)". One line.

### [DOC-008] — Minor — Architecture — ARCHITECTURE.md was only half-updated for Stage 9

**Evidence**
- The `llm_provider.py` row *does* mention `describe_sketch` ("Stage 9 Slice 1 — merged; the local-vision sketch read") — good.
- But the web-API route list (`ARCHITECTURE.md:168-174`) documents `POST /api/photo-seed` and not `POST /api/sketch-seed`, and the surrounding text ("describe_photo always builds a dedicated **local** provider") still describes the vision story without the dedicated `vision_model` / `VisionModelMissing` mechanics — the load-bearing Stage 9 change.

**Why this matters**
The new-team-member doc lists every other endpoint; the omission reads as "sketch-seed doesn't exist" and the vision-read description no longer matches `_describe_image`'s actual model targeting.

**Fix path**
Add `/api/sketch-seed` to the route list and one clause noting both seeds are read by the dedicated `vision_model` (default `qwen2.5vl:3b`) with a typed missing-model response. ~3 lines.

---

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.

## Marketing / honesty audit

The Stage 9 docs are notably honest: the benchmark doc admits a shipped feature never worked outside demo mode, the descope verdict is argued from hardware facts rather than buried, and the README's vision claim is scoped ("reads dimensioned sketches 3/3 — see [benchmark]") instead of generic "AI vision" puffery. The only honesty exposure is *residual*: the stale gemma4-vision claims (DOC-001/DOC-002) overclaim a capability the team itself disproved. No new overclaims introduced.

## Patterns and systemic observations

1. **Update-at-tag drift window.** README Setup was updated mid-stage but README status/ROADMAP/CHANGELOG wait for the tag — leaving a window where the front door contradicts itself (DOC-005). The convention is fine; consider making the *whole* README (status sentence included) part of the slice that touches it, with only ROADMAP/CHANGELOG/HANDOFF deferred to the tag.
2. **Correction banners need maintenance too.** The design-plane "⚠ SUPERSEDED" banners were written as one-time corrections and have themselves gone stale (DOC-002). Each new stage that overturns a "settled" decision should sweep the banners as part of its doc pass — a `grep gemma4 docs/design` would have caught this.
3. **The error-message ↔ troubleshooting contract is excellent and worth institutionalizing.** The `VisionModelMissing` string and its troubleshooting heading match verbatim, so a user can paste the error into search and land on the fix. This pattern (typed error → exact-match doc heading) is the best thing in this doc set; apply it to future error surfaces.

## Appendix: docs reviewed

- `docs/benchmarks/stage-9-vision-onramps.md`
- `README.md` (Setup, status paragraph, requirements)
- `docs/getting-started-windows.md`
- `docs/troubleshooting.md`
- `docs/guide-photo-onramp.md`
- `docs/guide-settings-and-cloud.md`
- `docs/README.md` (index)
- `docs/design/README.md`, `docs/design/KimCad-Unified-Product-Spec-v3.0.md` (vision sections), `docs/stage-8.5-usability-plan.md`, `docs/design/stage-8.5-slice-5-onramps.md`
- `ROADMAP.md` (status + Stage 9 section), `CHANGELOG.md`, `ARCHITECTURE.md`, `HANDOFF.md` (resume box)
- `docs/benchmarks/stage-6-model-bakeoff.md` (reproducibility-bar comparison)
- Code verified against: `src/kimcad/config.py`, `config/default.yaml`, `src/kimcad/llm_provider.py`, `src/kimcad/webapp.py`, `src/kimcad/cli.py`, `frontend/src/components/FirstRunWizard.tsx` (+ test), `frontend/src/components/PhotoOnramp.tsx`, `frontend/src/components/Landing.tsx`, `frontend/src/api.ts`, `tests/test_llm_provider.py`, `tests/test_webapp.py`
