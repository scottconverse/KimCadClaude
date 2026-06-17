# Documentation Deep-Dive — KimCad 0.9.0b4

**Audit date:** 2026-06-16
**Role:** Technical Writer
**Scope audited:** README.md, CHANGELOG.md, ARCHITECTURE.md, ROADMAP.md, CONTRIBUTING.md, SECURITY.md, docs/index.html, and docs/{api, supported-printers, USER-MANUAL, install-guide, FAQ, troubleshooting, getting-started-windows, MODEL-GUIDE, templates, cadquery-backend, definition-of-done, README}.md + the four guide-*.md + config/default.yaml comments. Verified against the live tree at origin/main @ 356867d.
**Writer mode:** audit-only (flag gaps; no rewrites/drafts produced)
**Auditor posture:** Adversarial

---

## TL;DR

The KimCad doc set is genuinely strong: large, internally cross-linked, persona-aware, and unusually honest about beta limits (mock-not-metal, unsigned installer, descoped features). All the high-stakes counts are coherent against the code — **29 printers** (3 reference + 26 curated, 7 vendors), **86 families** (39 benchmarked / 47 baseline), **6 connectors**, **version 0.9.0b4** — and there is **no stale Snapmaker / multi-toolhead / b5 / b6 leak in any live doc** (the only mention is the sanctioned CHANGELOG `[Unreleased]` note). A first-time user would succeed. The defects are drift, not rot: a **stale `gemma4:e4b`-as-default** claim that survives in ROADMAP and ARCHITECTURE (the real default planner is `qwen2.5:7b`), a **"signed attestation" promise** in the README and landing page that the product explicitly does *not* fulfill (the build is `unsigned_build: true` and the install guide only documents a checksum), and a **model-download size figure that disagrees four ways** across docs (4.7 / 8 / 9 / 13 GB). No Blockers. The install path works.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 4 |
| Minor | 5 |
| Nit | 3 |

## What's working

- **No Snapmaker / b5 / b6 drift in live docs.** A full sweep of all root + `docs/` markdown, `index.html`, and `config/default.yaml` found the multi-toolhead/Snapmaker/b5/b6 strings *only* in the CHANGELOG `[Unreleased]` note (the legitimate withdrawal record). The revert was scrubbed cleanly from the user-facing surface — a hard thing to get 100% right.
- **The canonical counts are coherent and code-true.** `docs/templates.md` is *generated from the live registry* and even ships the regeneration one-liner (templates.md:13–21); USER-MANUAL, ARCHITECTURE, index.html, and api.md all agree on 86 / 39 / 47, ~29 printers, 6 connectors, and `0.9.0b4`. Verified live: `default_registry()` → 86 families {benchmarked: 39, baseline: 47}; `Config.load()` → 29 printers, 3 reference, 7 vendors.
- **USER-MANUAL.md is the standout.** Three-persona structure (everyday / technical / architecture), a real glossary, an accurate module map, the correct default model, and an honest privacy section. It is publishable as-is.
- **Honesty discipline is exemplary.** supported-printers.md's four-tier key (profile-shipped / catalog / reference / metal-validated), the "no physical print is certified" line repeated everywhere it could be misread, the descoped photo→3D branch, and the removed LLM-CadQuery generator are all stated plainly. SECURITY.md and api.md are precise that the session token is *defense-in-depth, not CSRF, not auth*, and that it does not protect `--allow-remote`.
- **No broken internal links.** Every file path referenced by README / docs index / SECURITY / api was confirmed present on disk (first-hardware-contact, cross-platform-packaging, all four benchmark docs, the smart-mesh screen PNG, the stage-11 dispositions, frontend/README, LICENSE).

## What couldn't be assessed

- The actual GitHub **release assets** (whether `SHA256SUMS.txt` + `release-manifest.json` from `scripts/prepare_release_assets.py` are in fact attached to the b4 release) — assessed from the build script, not the live release page.
- Rendered behavior of `docs/index.html` in a browser (read as source; counts/copy verified statically).
- The `docs/design/` spec and `docs/benchmarks/*` bodies were confirmed to *exist* and be linked, but their internal accuracy was out of this pass's scope.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md | Yes | Strong (2 drift spots) | DOC-002, DOC-003 |
| ARCHITECTURE.md | Yes | Strong (1 stale claim) | DOC-001 |
| ROADMAP.md | Yes | Adequate (stale default model) | DOC-001, DOC-008 |
| USER-MANUAL.md | Yes | Strong | — |
| api.md | Yes | Strong | — |
| FAQ.md | Yes | Adequate (wrong download size; missing connectors) | DOC-003, DOC-004 |
| CHANGELOG.md | Yes | Strong | — |
| CONTRIBUTING.md | Yes | Strong | — |
| SECURITY.md | Yes | Strong | — |
| install-guide.md | Yes | Adequate (attestation gap, size) | DOC-002, DOC-003 |
| supported-printers.md | Yes | Strong | — |
| troubleshooting.md | Yes | Strong | DOC-003 (size echo) |
| getting-started-windows.md | Yes | Adequate (size range) | DOC-003, DOC-007 |
| MODEL-GUIDE.md | Yes | Strong | — |
| templates.md | Yes | Strong (registry-generated) | — |
| cadquery-backend.md | Yes | Strong | — |
| definition-of-done.md | Yes | Strong | DOC-002 (attestation wording, the honest version) |
| docs/index.html (landing) | Yes | Strong (1 overclaim) | DOC-002 |
| guide-*.md (4) | Yes | Strong | DOC-006 |
| config/default.yaml comments | Yes | Strong (1 stale parenthetical) | DOC-005 |
| LICENSE | Yes | Present (Apache-2.0) | — |

---

## Persona walk-through

### First-time user
Succeeds. README hero answers "what / who / how" in the first five seconds; the install-guide is a clean double-click path with the SmartScreen warning pre-explained; troubleshooting is symptom-first. The one friction: the model-download size they're told to expect changes depending on which doc they landed on (DOC-003), and a careful reader who follows the README's "verify … the signed attestation" instruction (DOC-002) will hunt the release page for a signed artifact that isn't there.

### Returning user
Well served. FAQ answers the real recurring questions (SmartScreen, the download, privacy, `.STEP`, recovery, "is it ready"). The docs index (`docs/README.md`) is a genuine map with current-vs-historical separation. Gap: a returning user with a Duet or Marlin printer who opens the FAQ won't find those two connectors mentioned — the FAQ's "Which printers work?" lists only Bambu/OctoPrint/Moonraker/PrusaLink (DOC-004).

### New team member
Strong. CONTRIBUTING.md documents the single authoritative gate, the test markers, the fork-PR smoke, the diff-coverage gate, and lock regeneration. ARCHITECTURE.md's module map is accurate and detailed. The only orientation hazard is the stale `gemma4:e4b`-as-default claim in ARCHITECTURE's local-first section and across ROADMAP (DOC-001), which would mislead a new engineer about which model the product actually runs.

---

## Findings

### [DOC-001] — Major — Accuracy — ROADMAP and ARCHITECTURE still name `gemma4:e4b` as the default planner; the real default is `qwen2.5:7b`

**Evidence**
The product default planner is `qwen2.5:7b` — confirmed in `config/default.yaml:66` (`model_name: qwen2.5:7b`), `src/kimcad/model_advisor.py` (default planner `qwen2.5:7b`), the CHANGELOG `[0.9.0b3]` "Default on-device planner is now `qwen2.5:7b` (was `gemma4:e4b`)", README, USER-MANUAL, MODEL-GUIDE, and index.html. But:
- `ARCHITECTURE.md:287–288` (the "Local-first and the injectable seam" section): *"out of the box it talks to a local runtime (Ollama or LM Studio) running `gemma4:e4b`"*. This is internally self-contradictory — the same file's module map at line 111 correctly states the default planner is `qwen2.5:7b`.
- `ROADMAP.md` repeatedly presents `gemma4:e4b` as **the default**: line 18 (*"Model: `gemma4:e4b`"* under "The target"), line 23, line 55 (*"keep `gemma4:e4b`"*), line 111 (Stage 0 goal), line 208, lines 222–227 (Stage 6 *"`gemma4:e4b` stays the default"*). The b2/b3/b4 deltas (ROADMAP:80–106) correctly note the switch, so the document contradicts itself.

**Why this matters**
The new-team-member and returning-power-user personas read ARCHITECTURE and ROADMAP as the authoritative "what does it actually run" reference. A contributor configuring a box, debugging a planning failure, or reasoning about the model layer would pull the wrong model. Inaccurate docs erode trust precisely with the audience most able to notice.

**Blast radius**
- Other docs that repeat the same error: scoped to ROADMAP.md and the one ARCHITECTURE.md paragraph; README/USER-MANUAL/MODEL-GUIDE/index.html/config-value are already correct, so this is a localized lag, not a systemic one.
- Shared assumption: `gemma4:e4b` is still a *real* role (the non-China fallback that hosts the vision-model slot), so a blind find-replace is wrong — only the **"default planner"** assertions should change to `qwen2.5:7b`, leaving the fallback/host mentions intact.
- Related findings: DOC-005 (the same root, surfacing in a config comment).

**Fix path**
In ARCHITECTURE.md:287–288 change the running model to `qwen2.5:7b` (keep the injectable-seam point). In ROADMAP.md, update the "default" assertions to `qwen2.5:7b` and recast the Stage-6 verdict as historical ("Stage 6 kept gemma4:e4b; the b3 bake-off later superseded it with qwen2.5:7b"), or add a one-line "Superseded at 0.9.0b3" banner to the affected stage blocks.

---

### [DOC-002] — Major — Accuracy/Marketing — "Signed attestation" is promised in the README and landing page, but the build is explicitly unsigned and the install guide never delivers it

**Evidence**
- `README.md:40`: *"the [install guide] … shows how to verify the SHA-256 checksum **and the signed attestation** attached to the release."*
- `docs/index.html:399`: *"The install guide shows how to verify the SHA-256 checksum **and the signed attestation** attached to each release."*
- The actual release artifact (`scripts/prepare_release_assets.py:1,8,85`) is `SHA256SUMS.txt` + `release-manifest.json` with **`"unsigned_build": True`** and the header comment *"Until the installer is code-signed, the trust story is …"*. There is no code-signing certificate (stated repeatedly: README:40, FAQ Q1, install-guide:9, ROADMAP "code-signing dropped").
- `docs/install-guide.md:12–19` documents **only** the `.sha256` checksum via `Get-FileHash`; it says nothing about a SHA256SUMS file, a manifest, or any "signed attestation."
- `docs/definition-of-done.md:52` is the more honest phrasing — *"SHA-256 attestation + a manifest with the exact source commit"* (no "signed").

**Why this matters**
Two public-facing surfaces (the front door and the marketing landing) promise a *signed* attestation the product cannot honor — "signed" implies a cryptographic signature, which is exactly the thing the project has dropped. A security-conscious user who follows the instruction to "verify the signed attestation" finds (a) the install guide gives no such procedure, and (b) the release explicitly self-labels unsigned. Per the technical-writer rubric this is the #1 doc failure mode — implying a capability that doesn't exist. It is also a self-inflicted credibility hit in the one place (a maker tool's trust story) where honesty is the differentiator the docs otherwise lean on.

**Blast radius**
- Adjacent copy: README:40 and index.html:399 share the verbatim phrase; fix both.
- User-facing: the SmartScreen/trust narrative across README, FAQ, install-guide, troubleshooting — the install guide must actually describe verifying the SHA256SUMS/manifest if the docs are going to point at it.
- Migration: none (copy + an install-guide section).
- Related findings: ties to definition-of-done.md:52, which already uses the correct (unsigned) wording — align the two surfaces down to the DoD's honesty bar.

**Fix path**
Replace "the signed attestation" with "the SHA-256 checksums (`SHA256SUMS.txt`) and the build manifest (`release-manifest.json`, which records the exact source commit and is flagged `unsigned_build`)" in README:40 and index.html:399, and add a short "Verifying the attestation files" subsection to install-guide.md that walks through both — or, if only the single `.sha256` is published, drop the attestation claim entirely and keep the checksum line.

---

### [DOC-003] — Major — Accuracy/Consistency — The model-download size disagrees four ways across the docs (4.7 / 8 / 9 / 13 GB)

**Evidence**
The real Ollama pull of `qwen2.5:7b` is ~4.7 GB and `qwen2.5vl:3b` is ~3 GB (MODEL-GUIDE.md:10–11; README:174; index.html:352–353; CHANGELOG cites ~3.2 GB for the vision model). But the user-facing "what you'll download" figure is stated as, variously:
- `docs/FAQ.md:33`: *"The local **chat model** is roughly a **9 GB** one-time download"* — wrong on two counts: it attributes 9 GB to the chat model *alone* (≈2× its real ~4.7 GB), and README:464's docs-table even advertises the FAQ as covering "the 9 GB download."
- `docs/install-guide.md:40` and `docs/troubleshooting.md:96`: *"about **13 GB** total"* (this matches the code's *disk-headroom pre-check* string in `src/kimcad/model_pull.py:63`, but is presented to users as the download size).
- `docs/USER-MANUAL.md:82,256`: *"about **8 GB** total"* / *"~8 GB free."*
- `docs/getting-started-windows.md:46–47`: *"the designer (~**5–10 GB**, the big download) and the small vision model (~**3 GB**)."*
- `docs/MODEL-GUIDE.md`: implies ~7.7 GB total (4.7 + 3).

So the same fact is 4.7 / 7.7 / 8 / 9 / 13 GB depending on the page, and the FAQ's number is also misattributed.

**Why this matters**
This is the single most-asked onboarding question (it's literally FAQ Q4 and a troubleshooting entry). A user provisioning disk or judging a download is given a 2.7× spread, and the most prominent answer (FAQ, echoed in the README TOC) is the most wrong. It reads as carelessness in exactly the spot a nervous first-timer checks.

**Blast radius**
- Adjacent copy: FAQ:33, README:464, install-guide:40, troubleshooting:96, USER-MANUAL:82+256, getting-started:46–47 — six surfaces, one fact.
- Shared state: the 13 GB figure is the code's *disk-free pre-check* (`model_pull.py:63`), deliberately generous; docs should distinguish "download size (~8 GB)" from "free disk recommended (~13–20 GB)" rather than conflate them.
- Migration: none (copy).
- Related findings: DOC-007, DOC-009 (same root, other surfaces).

**Fix path**
Pick one canonical pair — download ≈ **4.7 GB (chat) + 3 GB (vision) ≈ 8 GB total**, free-disk recommendation ≈ **13–20 GB** — and propagate it. Fix FAQ:33 to say "the two models total ~8 GB (the chat model ~4.7 GB, vision ~3 GB)" and update README:464's TOC blurb to match. Keep the install-guide/troubleshooting "13 GB" only if relabeled as the free-space check, not the download.

---

### [DOC-004] — Major — FAQ/Completeness — The FAQ's printer answer omits the Duet and Marlin connectors

**Evidence**
`docs/FAQ.md:85–92` (Q12 "Which printers work?") lists direct send as *"Bambu (native), OctoPrint, Moonraker/Klipper, and PrusaLink"* — four connectors. The product ships **six**: the same four plus **`duet`** (RepRapFirmware) and **`marlin`** (the Ender-class installed base), both added at 0.9.0b2 and documented everywhere else (README:312–313, USER-MANUAL:200–201 & 363–364, supported-printers.md:83–84, ARCHITECTURE module map, index.html:338, troubleshooting:115–124). Verified in code: 6 leaf connectors (`bambu`, `duet`, `marlin`, `moonraker`, `octoprint`, `prusalink`) registered in `src/kimcad/connectors.py`.

**Why this matters**
Marlin is explicitly "the huge Ender-class installed base" — the single largest population of hobbyist printers. A returning user with an Ender or a Duet board who consults the FAQ (the doc designed to answer the support inbox's real questions) is told their printer isn't covered when it is. This is the textbook "FAQ missing an answer to a real recurring question" Major.

**Blast radius**
- Adjacent copy: only FAQ Q12 lags; the rest of the doc set is already correct and consistent on six connectors.
- User-facing: affects the largest hardware cohort's first impression of support breadth.
- Migration: none (one sentence).
- Related findings: none; isolated FAQ lag behind the b2 connector addition.

**Fix path**
Add "Duet/RepRapFirmware, and Marlin (Ender-class, over USB serial or a network bridge)" to the FAQ Q12 connector list, mirroring USER-MANUAL.md:200–201.

---

### [DOC-005] — Minor — Accuracy — config/default.yaml comment calls the local backend "(gemma)"

**Evidence**
`config/default.yaml:90`, in the `local_qwen` backend comment: *"so `local` (gemma) stays the default."* The `local` backend's `model_name` two stanzas up (line 66) is `qwen2.5:7b`, not gemma. Same stale-default root as DOC-001, surfacing in a config comment a power user reads when overriding models.

**Why this matters**
A power user editing `config/local.yaml` reads these comments as ground truth; the parenthetical misnames the current default. Low exposure (comment only, the value itself is correct), hence Minor.

**Fix path**
Change "(gemma)" to "(qwen2.5:7b)" on line 90.

---

### [DOC-006] — Minor — Consistency — guide-sliders-and-units.md describes the template engine as "seven families"

**Evidence**
`docs/guide-sliders-and-units.md:5`: *"a box, tray, enclosure, tube, hook, cable clip, or drawer divider"* — the original Stage-5 seven. The catalog is now 86 families. The guide is dated "Stage 5 — shipped" and is technically describing the slider mechanism (which is correct), but a reader could infer the library is seven parts.

**Why this matters**
Minor — the guide's *mechanism* description is accurate and it isn't a catalog reference, but the example list reads as exhaustive and undersells the library by an order of magnitude. Low stakes; easy fix.

**Fix path**
Add "(one of KimCad's 86 template families — see [the catalog](templates.md))" after the example list, or soften "a box, tray, …" to "e.g. a box, tray, …".

---

### [DOC-007] — Minor — Consistency — getting-started uses a wide "~5–10 GB" range for the chat-model download

**Evidence**
`docs/getting-started-windows.md:46`: *"the designer (~5–10 GB, the big download)."* A 2× range for a fixed ~4.7 GB artifact. Subsumed by DOC-003 but called out separately because it's the from-source path's only size figure and uses a range rather than a wrong point value.

**Fix path**
Replace "~5–10 GB" with "~4.7 GB" once DOC-003's canonical numbers are chosen.

---

### [DOC-008] — Minor — Onboarding — ROADMAP's self-description as a forward plan is stale now that every stage is DONE

**Evidence**
`ROADMAP.md` mixes tenses: the header and "Current baseline" present Stages 4–11 as "ahead" (line 8: *"Stages 4–11 are ahead"*; Stage 4 block line 180 *"Size: ~2–3 weeks"* in future tense), while the body and the b2/b3/b4 sections confirm all stages are merged + tagged and the beta shipped. A reader can't tell at a glance whether the roadmap is a plan or a history.

**Why this matters**
Minor — it's confusing rather than wrong (the DONE markers are present), but a roadmap whose framing contradicts its own status costs the new-contributor persona a few minutes of reconciliation.

**Fix path**
Add a one-line status banner at the top ("All stages 0–11 are DONE and tagged; the beta shipped at 0.9.0b1 and is at 0.9.0b4. The stage blocks below are retained as the executed plan.") and convert the remaining future-tense "Size/Needs" lines to past tense or move them under an "(as planned)" note.

---

### [DOC-009] — Nit — README's TOC blurb propagates the wrong download figure

**Evidence**
README.md:464 TOC blurb advertises the FAQ as covering "the 9 GB download" — propagating the FAQ's wrong figure into the README itself. (Rolled into DOC-003's fix; noted as a Nit-level second occurrence for completeness.)

**Fix path**
Update alongside DOC-003.

---

### [DOC-010] — Nit — "~65 brand" phrasing varies cosmetically across docs

**Evidence**
The bundled-library size is phrased as "~65-brand / 1,400+ machine-profile" (README:34), "roughly 65 printer brands and 1,400+ machine profiles" (supported-printers.md:3), and "~65 brands, 1,400+ machines" (FAQ:88). Same numbers, cosmetic phrasing drift. Harmless.

**Fix path**
None required; optionally standardize the phrasing.

---

### [DOC-011] — Nit — getting-started fetch-tools size figure unverified

**Evidence**
getting-started-windows.md:87 states the OpenSCAD+OrcaSlicer fetch is "about 200 MB." Not independently verified against the pinned archive sizes this pass; flagged only as an unverified point-figure to spot-check, not a known error.

**Fix path**
Spot-check against the `fetch_tools.py` pins; adjust if off.

---

## Marketing / honesty audit

`docs/index.html` (the landing page) is, on the whole, a model of honest product copy: an explicit "Honest beta status" section (line 397) stating real-hardware validation is unproven, the unsigned-installer warning up front (line 172), accurate model names and sizes in the tech table (lines 352–353), the correct 86-family / ~29-printer / 6-connector claims, and no neural-mesh or "instant" overclaim. The **one** marketing-honesty defect is DOC-002 — the "signed attestation" line (index.html:399) promises a cryptographic-signature capability the project has explicitly dropped. That single phrase is out of step with the page's otherwise-disciplined honesty and should be corrected to match the unsigned reality. No vague value props, no unsubstantiated stats (the 4/4 bake-off claim is backed by a committed, re-runnable harness), no phantom features.

## Patterns and systemic observations

- **Single root cause, two surfaces:** DOC-001 and DOC-005 are the same b3 model-switch lag (gemma → qwen2.5:7b) reaching the slowest-moving docs (ROADMAP, ARCHITECTURE's prose, a config comment). The fast-moving user docs already updated; this is a stage-boundary "docs move with the code" miss (definition-of-done.md:33–34 mandates exactly this) on the *internal* docs.
- **No canonical number for the model download:** DOC-003/007/009 all stem from no single source-of-truth figure; the docs variously quote the real download, a rounded total, a wrong total, and the code's disk-headroom pre-check interchangeably. A one-line "download ≈ 8 GB / free disk ≈ 13–20 GB" canonical, referenced everywhere, would close all three.
- **The honesty bar is set high and mostly held.** The DoD, SECURITY, supported-printers, and CHANGELOG are exceptionally candid. The two honesty *misses* (DOC-002 "signed", DOC-004 missing connectors) are lag/overreach against that bar, not a different standard — which is why they're worth fixing: they're the exceptions a careful reader will notice precisely because the rest is trustworthy.

## Appendix: docs reviewed

Root: README.md, CHANGELOG.md, ARCHITECTURE.md, ROADMAP.md, CONTRIBUTING.md, SECURITY.md, LICENSE.
docs/: README.md (index), api.md, supported-printers.md, USER-MANUAL.md, install-guide.md, FAQ.md, troubleshooting.md, getting-started-windows.md, MODEL-GUIDE.md, templates.md, cadquery-backend.md, definition-of-done.md, index.html, guide-my-designs.md, guide-sliders-and-units.md, guide-photo-onramp.md, guide-settings-and-cloud.md.
Code/config cross-checks: config/default.yaml, src/kimcad/{connectors.py, model_advisor.py, model_pull.py, templates.py, config.py}, tests/test_printer_catalog.py, tests/test_templates.py, scripts/{prepare_release_assets.py, build_installer.py}. Live verification: `default_registry().families()` (86 / 39 benchmarked / 47 baseline) and `Config.load()` (29 printers, 3 reference, 7 vendors).

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.
