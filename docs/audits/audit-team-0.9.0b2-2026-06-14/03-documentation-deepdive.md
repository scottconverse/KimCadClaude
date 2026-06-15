# Documentation Deep-Dive — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Role:** Technical Writer
**Scope audited:** README.md, ARCHITECTURE.md, ROADMAP.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, HANDOFF.md; `docs/` — USER-MANUAL.md, FAQ.md, api.md, install-guide.md, supported-printers.md, definition-of-done.md, templates.md, MODEL-GUIDE.md, troubleshooting.md, getting-started-windows.md, README.md (docs index), the `guide-*.md` set, cadquery-backend.md, printproof3d-integration.md, dev/cross-platform-packaging.md, beta/first-hardware-contact.md. Marketing surface (the README hero + the absent landing page) in scope.
**Writer mode:** audit-only — gaps are flagged with exact citations; no replacement docs drafted (remediation held for owner go-ahead).
**Auditor posture:** Balanced.
**Canonical version under audit:** `0.9.0b2` / `0.9.0-beta.2` (single-sourced from `pyproject.toml:10`; `dist/release-manifest.json` confirms `version: "0.9.0b2"`, `source_commit: f92c2b1…`, asset `KimCad-Setup-0.9.0b2.exe`).

---

## TL;DR

The KimCad doc set is, structurally, one of the better open-source corpora I've reviewed — `docs/api.md`, `docs/supported-printers.md`, `docs/templates.md`, `CONTRIBUTING.md`, `SECURITY.md`, and the `[0.9.0b2]` CHANGELOG section are all current, honest, and accurate to the shipping 0.9.0b2 software (Duet/Marlin connectors, 29-printer catalog, session-token guard, macOS/Linux-from-source all correctly reflected). The front door and the flagship narrative docs, however, are **mid-migration and currently lie about the build**: `README.md` and `docs/install-guide.md` still send testers to the superseded `KimCad-Setup-0.9.0b1.exe`, and `docs/USER-MANUAL.md` — the doc the project itself calls "the single best starting point" — is pinned to `0.9.0b1` and is missing **every** 0.9.0b2 headline feature from its narrative and its three-audience structure. A user who downloads per the README, or verifies the checksum per the install guide, fails. There is **no `docs/index.html` landing page** and **no `README-FULL.pdf`/`USER-MANUAL.pdf`** anywhere on disk. A prior cleanup review (`cleanup-review-0.9.0b2-2026-06-14.md`) caught most of the version drift but missed at least one live contradiction (FAQ "about 90"). The docs are not dishonest by intent — they are honest about *uncertainty* (mock-vs-metal is scrupulously separated everywhere) — they are stale-by-omission, and the staleness is concentrated exactly on the highest-traffic surfaces.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 1 |
| Critical | 2 |
| Major | 4 |
| Minor | 6 |
| Nit | 3 |

## What's working

- **`docs/api.md` is exemplary** — every shipped HTTP endpoint is documented with request/response shape, status taxonomy, and error semantics, and it already documents the new session-token guard (KC-26) in depth and honestly (`docs/api.md:240-260`), plus `/api/print-outcome` (`:118-131`). It is more current than ARCHITECTURE.md. Keep this as the reference standard.
- **`docs/supported-printers.md` is current and rigorous** — it carries the full 29-printer catalog, the four-claim honesty key (profile-shipped / catalog / reference / metal-validated), AND the new `duet` + `marlin` connectors with their honest limitations (`:83-92`). This is the model for how the rest of the docs should treat 0.9.0b2.
- **`docs/templates.md` is registry-generated and cannot drift** — header states 86 families = 39 benchmarked + 47 baseline (`docs/templates.md:1-7`), which I verified against `kimcad.templates.default_registry()` at runtime: **86 families, 39 benchmarked / 47 baseline — exact match.**
- **`SECURITY.md` and `CONTRIBUTING.md` are both current** — SECURITY documents the session token correctly (`SECURITY.md:21-30`); CONTRIBUTING reflects the post-beta gate work (KC-12 fork smoke, KC-20 e2e, KC-22 diff-coverage) at `CONTRIBUTING.md:66-121`.
- **The `[0.9.0b2]` CHANGELOG section is excellent** (`CHANGELOG.md:27-75`) — it accurately and specifically records Duet/Marlin, the 29-printer catalog, the session token, e2e, diff-coverage, and macOS/Linux-from-source.
- **Honesty discipline is consistent and genuine** — across README, FAQ, USER-MANUAL, supported-printers, definition-of-done, the mock-validated-vs-metal-validated boundary is kept distinct everywhere it could be misread. This is the single best trait of the corpus and should be protected through the rewrite.
- **Internal relative links resolve** — a programmatic crawl of every `](path)` link across all 30+ markdown docs found zero broken user-facing relative targets (the only miss is a dev-internal `HANDOFF.md → memory/` reference). Referenced benchmark files (`stage-5-template-families.md`, `stage-8-cadquery-backend.md`, `stage-9-vision-onramps.md`) all exist.

## What couldn't be assessed

- **The pinned GitHub Discussions content** (Discussions #2/#3/#4 referenced from `README.md:43` and the docs) lives on github.com and was not fetched in this pass — it is outside the local repo. The prior cleanup-review flagged Discussions staleness (its DISC-04/DISC-05); I confirm only that README points testers at `../../discussions/2` and cannot verify that thread's current text. **Recommend the orchestrator/owner verify the pinned Discussion against 0.9.0b2 before launch** — it is a first-contact surface for testers.
- **Rendered marketing/landing copy** — there is no landing page to assess (see DOC-005); the README hero is the de-facto marketing surface and is audited below.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| README.md | Yes | Weak (version-stale front door) | DOC-001, DOC-009 |
| ARCHITECTURE.md | Yes | Adequate (documents removed feature; omits 3 shipped ones) | DOC-002, DOC-003 |
| User manual (`docs/USER-MANUAL.md`) | Yes | Weak (version-stale + missing all b2 features + audience gaps) | DOC-001, DOC-004, DOC-007 |
| API reference (`docs/api.md`) | Yes | **Strong** | — (credited) |
| FAQ (`docs/FAQ.md`) | Yes | Adequate (one live contradiction) | DOC-006 |
| CHANGELOG.md | Yes | Strong for `[0.9.0b2]`; stale `[Unreleased]` header | DOC-010 |
| CONTRIBUTING.md | Yes | Strong | — (credited) |
| SECURITY.md | Yes | Strong | — (credited) |
| LICENSE | Yes | Present (Apache-2.0) | — |
| Supported printers | Yes | **Strong** | — (credited) |
| Install guide | Yes | Weak (wrong installer filename in verify cmd) | DOC-001 |
| ROADMAP.md | Yes | Adequate (no forward `[0.9.0b2]` entry) | DOC-011 |
| Landing / marketing page (`docs/index.html`) | **No** | **Missing** | DOC-005 |
| Offline manual (`README-FULL.pdf` / `USER-MANUAL.pdf`) | **No** | **Missing** | DOC-008 |

---

## Persona walk-through

### First-time user
Lands on `README.md`. The hero value-prop (`:3`) is clear and honest, and the "fastest path" CTA is well-shaped. But the download badge reads `0.9.0b1` (`:5`), the CTA reads `` `0.9.0b1` beta`` (`:14`), and the "what the installer puts on your machine" line names `KimCad-Setup-0.9.0b1.exe` (`:30`) — while the actual shipping artifact is `KimCad-Setup-0.9.0b2.exe`. The download link itself (`../../releases/latest`) is version-agnostic and will resolve, so a user *may* still get b2; but a user who reads the filename, or who verifies the checksum using `docs/install-guide.md:16` (`Get-FileHash .\KimCad-Setup-0.9.0b1.exe`), is hashing a filename that won't exist in the b2 release — the verification step fails. **First-time success is at risk and the trust-critical checksum step is broken.** (DOC-001.)

### Returning user
Goes to the FAQ or the USER-MANUAL for a specific answer. The FAQ is well-organized and answers the real questions (SmartScreen, the 9 GB download, privacy, "is it ready"), but Q19 still says the library has "about 90" families (`docs/FAQ.md:142`) — the real count is 86, and this contradicts `docs/templates.md` and the in-app `/api/templates`. A returning user who set up a Duet or Marlin printer (both shipped in b2) will find **nothing** in the USER-MANUAL about them — the manual's connector table (`docs/USER-MANUAL.md:264-270`) lists only five connectors and omits both. (DOC-004, DOC-006.)

### New team member
Reads ARCHITECTURE.md to get oriented, then CONTRIBUTING.md to set up. CONTRIBUTING is strong and current. ARCHITECTURE.md, however, will actively mislead them: it documents the **LLM-CadQuery fallback generator as a live pipeline path** (`ARCHITECTURE.md:81,83,91`) — a feature that was *removed* in b2 (`src/kimcad/llm_provider.py:339`: "generate_cadquery was removed here"), so a new engineer will go looking for `generate_cadquery` and codegen-fallback wiring that no longer exists. The module map also omits the two shipped connectors (`duet_connector.py`, `marlin_connector.py`) and the trust-boundary section omits the session-token guard entirely. (DOC-002, DOC-003.)

---

## Findings

> **Finding ID prefix:** `DOC-`
> **Categories:** Accuracy / Completeness / Onboarding / Architecture / API / FAQ / Marketing / Tone / Hygiene

### [DOC-001] — Blocker — Accuracy/Onboarding — Front-door docs point testers at the superseded `0.9.0b1` build and break the checksum-verify step

**Evidence**
The canonical version is `0.9.0b2` (`pyproject.toml:10`; `dist/release-manifest.json` → `KimCad-Setup-0.9.0b2.exe`, sha `f75495a0…`). Stale `0.9.0b1` references on install-critical surfaces:
- `README.md:5` — `![beta](…/beta-0.9.0b1-…)` badge.
- `README.md:14` — CTA: ``### ▶ [**Download KimCad for Windows**](../../releases/latest) — `0.9.0b1` beta``.
- `README.md:30` — ``KimCad-Setup-0.9.0b1.exe`` — "one double-click…".
- `README.md:63` — "the **beta gate** — the `0.9.0b1` release."
- `docs/install-guide.md:16` — ``Get-FileHash .\KimCad-Setup-0.9.0b1.exe -Algorithm SHA256`` — the verify command names a file the b2 release does not publish.
- `docs/USER-MANUAL.md:15` — "this manual tracks the `0.9.0b1` Windows beta."
- `docs/definition-of-done.md:47` — "## The beta bar (what `0.9.0b1` actually means)".

**Why this matters**
This is the project's own honesty standard applied to itself, and it currently fails. The SHA-256 verification is the *only* integrity check a tester has against an unsigned installer that trips SmartScreen — and the documented command (`install-guide.md:16`) references a filename absent from the b2 release, so the one trust-establishing step a security-conscious user performs will not match. A user reading `README.md:30` is told the installer is named `…0.9.0b1.exe`. For an unsigned beta whose entire pitch rests on "trust us, here's how to verify," shipping docs that misname the artifact and break the verify step is a Blocker per the framework (documented install/verify path does not work) — and it is the highest-leverage fix in this audit.

**Blast radius**
- Other docs repeating the error: `ROADMAP.md:75` (historical narrative — lower stakes), `CHANGELOG.md` `[Unreleased]` header `:8/:22` (DOC-010). The README hero badge/CTA is hand-maintained (no single-source), which is the *root cause* — every release will reintroduce this unless a release-checklist item or a generated badge is added.
- User-facing: every first-time installer and every checksum-verifier.
- Migration: none — pure doc edit. But coordinate so all seven sites flip together; a partial fix (e.g. README but not install-guide) leaves the verify step broken.
- Related findings: DOC-009 (version-agnostic CTA as the durable fix), DOC-010 (CHANGELOG header), DOC-004 (USER-MANUAL version banner is one of these sites and also has deeper gaps).

**Fix path**
Replace all `0.9.0b1` → `0.9.0b2` on the seven cited lines; in `install-guide.md:16` use the actual b2 filename (or, better, a version-agnostic `Get-FileHash .\KimCad-Setup-*.exe`). Durable fix in DOC-009. *(This is the prior cleanup-review's C1, here with exact line citations and one added site — `definition-of-done.md:47` — and escalated to Blocker because the verify command, not just a cosmetic label, is wrong.)*

---

### [DOC-002] — Critical — Accuracy/Architecture — `ARCHITECTURE.md` documents the REMOVED LLM-CadQuery fallback generator as a live pipeline path

**Evidence**
The LLM-CadQuery *fallback generator* (AI-written CadQuery code) was removed in b2 — `src/kimcad/llm_provider.py:339`: "KC-2/KC-4 (#8/#6): generate_cadquery was removed here — the LLM-CadQuery fallback's [measured lift was 0]". README and USER-MANUAL both correctly state this (`README.md:216-218`, `docs/USER-MANUAL.md:312-313`). ARCHITECTURE.md still describes it as a live feature in three places:
- `:81` (`llm_provider.py` module entry) — lists "`generate_cadquery` (Stage 8 — the CadQuery parallel-backend codegen)" among the provider's "five jobs."
- `:83` (`cadquery_runner.py` entry) — frames `sanitize_cadquery` as guarding "the untrusted **generated** script," i.e. AI-written CadQuery.
- `:91` (`pipeline.py` entry) — "the pipeline **falls back to CadQuery codegen** (when an interpreter is available) and keeps the better result" — describes the removed dual-codegen race as current behavior.

**Why this matters**
This is the architecture doc — the one source a new engineer trusts to understand what the system does before touching it. It claims a code path that no longer exists and, worse, claims that *AI-written Python is executed* in a fallback — exactly the security-sensitive behavior the team removed and now advertises as gone everywhere else. The contradiction between ARCHITECTURE ("AI writes CadQuery") and README/USER-MANUAL ("no AI-written Python ever runs anymore") undermines trust in *both*. An engineer will waste time hunting for `generate_cadquery` and a codegen-fallback branch in `pipeline.py` that aren't there.

**Blast radius**
- Adjacent docs: `docs/cadquery-backend.md` should be checked for the same framing (the optional CadQuery engine now builds STEP only from *trusted template twins*, never AI code — verify it says so).
- User-facing: none directly, but it's a recruiting/onboarding and security-credibility surface.
- Code reality to match: `cadquery_runner.py`/`cadquery_worker.py` still exist and still sandbox CadQuery — but only the *trusted template-twin* STEP path now uses them, not an LLM generator. The doc must redraw that line.
- Migration: none — doc edit.
- Related findings: DOC-003 (same module map omits live features), DOC-012 (module-map staleness pattern).

**Fix path**
Rewrite the three `cadquery` references to describe the *current* arrangement: CadQuery is an optional STEP-export engine driven by KimCad's own trusted template twins (`cadquery_templates.py`); the LLM-CadQuery fallback generator was removed in b2 (no AI-written Python executes). Keep the sandbox description (it still guards the worker), but stop attributing the input to the LLM. *(Cleanup-review C2; confirmed independently with the source-of-truth line.)*

---

### [DOC-003] — Critical — Completeness/Architecture — `ARCHITECTURE.md` omits all three shipped 0.9.0b2 subsystems: Duet/Marlin connectors, the session-token guard, and macOS/Linux

**Evidence**
Three headline b2 features (all in the `[0.9.0b2]` CHANGELOG, all in code) are absent from ARCHITECTURE.md:
1. **Duet + Marlin connectors** — `src/kimcad/duet_connector.py`, `marlin_connector.py`, `mock_duet.py`, `mock_marlin.py` all exist and are in `config/default.yaml` `connectors:` (verified: connectors = `duet, marlin, mock, moonraker, octoprint, prusalink, bambu_*`). The ARCHITECTURE module map (`:94-104`) documents `bambu`, `octoprint`, `moonraker`, `prusalink` connectors + their mocks but has **no row for `duet_connector.py` or `marlin_connector.py`** (grep for `duet|marlin` in ARCHITECTURE.md → 0 hits).
2. **Session-token guard (KC-26)** — implemented in `src/kimcad/webapp.py` (`:678, :1307-1324, :2611-2619`; `X-KimCad-Session` header, `hmac.compare_digest`, per-boot `secrets.token_urlsafe(32)`). ARCHITECTURE.md "Trust boundaries" (`:384-398`) lists loopback-only, untrusted-codegen, secrets-off-disk, vision-local, prints-need-proof — but **not** the session token (grep for `session.token|X-KimCad|csrf` → 0 hits). `api.md` and `SECURITY.md` document it; the architecture doc doesn't.
3. **macOS/Linux from source** — README has a full "Platform notes" matrix (`README.md:438-455`); `paths.py` resolves platform-idiomatic data dirs in b2. ARCHITECTURE.md "installed layout" (`:400-409`) is Windows-only and never mentions macOS/Linux (grep for `macOS|Linux` → 0 hits).

**Why this matters**
The architecture doc is where a contributor goes to learn the system's shape before extending it. A contributor adding a connector has no map entry to copy from for the two newest ones; a contributor touching the web layer's request handling won't learn from the architecture that a session-token guard exists and must be preserved (a real regression risk — they could remove or bypass it); a contributor on a Mac will read an architecture that implies Windows-only. The doc is now a stage behind the code on three fronts simultaneously, which is the pattern that erodes a doc's authority fastest.

**Blast radius**
- Adjacent docs: the ARCHITECTURE web-layer section (`:155-222`) enumerates endpoints but predates the session-token gating of POSTs — it should note that state-changing requests are now token-gated.
- Shared concern: this is the same root as DOC-002 — ARCHITECTURE.md was not updated for the b2 cycle while api.md/supported-printers/CHANGELOG were. Fix all four ARCHITECTURE gaps (DOC-002 + the three here) in one pass.
- User-facing: none directly; contributor/security-reviewer surface.
- Migration: none — doc edit.
- Related findings: DOC-002, DOC-004 (USER-MANUAL Part 3 has the identical session-token omission), DOC-012.

**Fix path**
Add module-map rows for `duet_connector.py` + `marlin_connector.py` (+ their mocks); add a "Session token (KC-26)" bullet to Trust boundaries pointing at the api.md detail; extend the installed-layout section (or add a Platform note) for macOS/Linux per the README matrix. *(Cleanup-review M1 covered the narrative gap broadly; this isolates the ARCHITECTURE-specific, file-and-line-cited subset and is escalated to Critical because the missing session-token boundary is a behavior a contributor could silently break.)*

---

### [DOC-004] — Major — Completeness/Onboarding — The USER-MANUAL (the "single best starting point") is missing every 0.9.0b2 feature and its three-audience structure now has holes

**Evidence**
`docs/README.md:6` calls USER-MANUAL "**The single best starting point.**" The manual advertises three audiences (`docs/USER-MANUAL.md:7-13`: Part 1 everyday / Part 2 technical / Part 3 architecture). Yet a grep across the whole file finds **zero** mentions of `duet`, `marlin`, `session token`, `macOS`, or `Linux`:
- **Part 2 connector table** (`:264-270`) lists only `loopback`, `bambu`, `octoprint`, `moonraker`, `prusalink` — Duet and Marlin (shipped b2) are absent.
- **Part 2 mock-server list** (`:279`) names `mock_printer`, `mock_moonraker`, `mock_prusalink` — omits `mock_duet`, `mock_marlin`.
- **Part 3 Trust boundaries / Architecture** has no session-token entry (the manual's `Part 3` mirrors ARCHITECTURE's omission — DOC-003).
- **No platform coverage** — Part 1 "Installing (Windows)" (`:36`) is the only platform path; macOS/Linux-from-source (a b2 first-class claim per CHANGELOG `:47-60`) appears nowhere, so the "technical/integrator" audience on a Mac is unserved.
- **Version banner** `:15` says `0.9.0b1` (also DOC-001).

**Why this matters**
This is the doc the project itself routes users to first, and it now under-describes the product across all three of its stated audiences: the non-technical reader gets a connector list that's missing two printer families; the technical reader gets a CLI/connector surface and an architecture section that omit shipped subsystems; the Mac/Linux reader is told nothing. A returning user who bought a Duet or an Ender (Marlin) — the single largest installed base in consumer FDM — finds the flagship manual silent on their hardware while `supported-printers.md` covers it. The manual isn't *wrong*, it's a release behind, and because it's the designated front door for depth, the gap is more damaging here than in a secondary guide.

**Blast radius**
- Adjacent docs: same root as DOC-002/003 — the b2 update reached api.md/supported-printers/CHANGELOG but not the narrative docs (README hero, USER-MANUAL, ARCHITECTURE). A single coordinated "narrative refresh" pass closes DOC-001, -002, -003, -004, -006 together.
- User-facing: every reader who follows `docs/README.md`'s recommendation to start here.
- Migration: none — doc edit. **Note:** a full professionally-formatted user manual rewrite is already APPROVED for the remediation phase (see "Approved remediation scope" below) — this finding defines what that rewrite must add.
- Related findings: DOC-001, DOC-003, DOC-006, DOC-007, DOC-005.

**Fix path**
Refresh the manual for b2: add Duet/Marlin to the Part 2 connector + mock-server tables (mirror `supported-printers.md:83-92`'s honest limitations); add a session-token paragraph to Part 3 Trust boundaries (mirror `api.md:240-260`); add a macOS/Linux-from-source path (Part 1 or a platform note). The approved manual rebuild should treat these as required content, not optional.

---

### [DOC-005] — Major — Marketing/Onboarding — No `docs/index.html` landing page exists

**Evidence**
`find docs -name index.html` → none; `ls docs/index.html` → "NO docs/index.html". The README hero (`README.md:1-43`) is the only marketing/landing surface, and it is currently version-stale (DOC-001). The repo has the substrate for a GitHub Pages site (`docs/` tree) but no `index.html`.

**Why this matters**
For an open-source desktop app whose adoption depends on a confident first impression, a README-on-GitHub is a weaker front door than a real landing page: it cannot show the product, segment audiences (non-technical buyer vs. CLI integrator vs. contributor), or carry the honest beta framing in a designed, scannable layout. A project with a mediocre/absent landing page loses users to competitors with a great one — this is a strategic adoption finding, not just hygiene. The good news: the raw material (honest value prop, clear differentiators, the four-claim printer honesty key, the 86-family catalog) already exists across the current docs and is high quality, so a landing page would be assembling proven copy, not inventing claims.

**Blast radius**
- Adjacent: a landing page must source its claims from the *current* docs (templates.md, supported-printers.md, api.md), **not** from the stale README/USER-MANUAL — otherwise it will inherit DOC-001/004/006 errors at launch. Build the landing page *after* (or alongside) the version-drift fixes so it can't ossify `0.9.0b1` again.
- User-facing: every prospective user who arrives from a link, search, or share before reaching the repo.
- Migration: none.
- Related findings: DOC-009 (the page must use a version-agnostic download CTA), DOC-001 (don't seed it with stale copy), DOC-008 (a "download the full manual (PDF)" link belongs on it).

**Fix path**
Building `docs/index.html` is **already APPROVED** for remediation (see scope note). Audit-mode constraint here is only to specify what it must cover — done in "Approved remediation scope" below. *(Cleanup-review M3 logged this as a decision; the decision is now made — build it.)*

---

### [DOC-006] — Major — Accuracy/FAQ — FAQ states "about 90" library families; the real count is 86 (a live contradiction the prior cleanup missed)

**Evidence**
`docs/FAQ.md:142` — "KimCad ships a **library of about 90 ready-made part families**…". The registry-authoritative count is **86** (verified at runtime: `default_registry().families()` → 86; `docs/templates.md:1-3` "86 parametric part families"; `/api/templates` returns 86). The identical error also sits at `docs/USER-MANUAL.md:107` ("about 90 of them"). **The prior cleanup-review (`cleanup-review-0.9.0b2-2026-06-14.md:64-65`, finding M2) flagged only the USER-MANUAL instance and missed the FAQ one** — so a remediation that follows the cleanup-review alone will leave FAQ wrong.

**Why this matters**
The FAQ is a returning-user/answer-seeking surface, and "about 90" directly contradicts the generated, can't-drift catalog the same user is pointed to (`templates.md`) and the count the app shows. It's a small number but a credibility tell: if the count is wrong, what else is? Flagging it here ensures the FAQ instance isn't dropped.

**Blast radius**
- Other docs repeating the error: `docs/USER-MANUAL.md:107` (the cleanup-review's M2 — same family of fix). Both should change to "86" or, better, to "more than 80" / "dozens of" if the maintainer wants a hand-written sentence that never goes stale as the registry grows.
- User-facing: returning users browsing the library.
- Migration: none.
- Related findings: DOC-004 (same manual section).

**Fix path**
Set FAQ:142 and USER-MANUAL:107 to 86 (or a deliberately count-agnostic phrasing, since the catalog grows). Add a release-checklist note that hand-written family counts must reconcile with `templates.md`.

---

### [DOC-007] — Minor — Completeness/Onboarding — The USER-MANUAL's non-technical (Part 1) audience has no glossary and assumes terms it never defines

**Evidence**
Part 1 (`docs/USER-MANUAL.md:20-199`) targets "anyone who wants to make a part" but uses, without definition, terms a non-technical buyer won't know: "manifold"/"watertight" (`:159`, `:148`), "mesh" (`:147`), "the gate"/"Printability Gate" (`:158`), "slice"/"G-code 3MF" (`:166`), ".STEP"/".STL" (`:170`), "Ollama" (`:62`). The prior cleanup-review noted "no standalone glossary" as a Minor (UM-08); confirmed.

**Why this matters**
The manual explicitly serves three audiences and names "the curious / non-technical" as Part 1's reader, but reads at a maker-literate level. The non-technical persona is precisely the one KimCad's "no CAD skills" pitch is courting — leaving them to infer "manifold" undercuts the value prop in the doc meant to onboard them.

**Blast radius**
- User-facing: non-technical first-time users.
- Migration: none.
- Related findings: DOC-004 (the approved manual rebuild should add a glossary as part of the non-technical tier).

**Fix path**
Add a short glossary (or first-use inline gloss) for the ~8 load-bearing terms; the approved professional manual should carry one. Audit-only — not drafted here.

---

### [DOC-008] — Minor — Completeness/Hygiene — No offline `README-FULL.pdf` / `USER-MANUAL.pdf` exists, against project standards

**Evidence**
`find . -name "*.pdf"` (excluding `.venv`) → none. The project's own `coder-ui-qa-test` documentation standards expect a distributable PDF manual; the prior cleanup-review logged this as Minor (ARCH-06/UM-07) and as an open decision ("required artifacts, or drop the expectation?").

**Why this matters**
A bundled/downloadable PDF is the offline reference for a tool that runs air-gapped (KimCad's whole pitch is "no network"). A user who installed offline has no docs unless they're on disk or printable. Low exposure (most users have the web docs), hence Minor, but it's a stated standard currently unmet.

**Blast radius**
- User-facing: offline/air-gapped users.
- Migration: none — but if adopted, a PDF becomes a per-release artifact that must be regenerated (another version-drift surface — generate it from the canonical manual, don't hand-maintain).
- Related findings: DOC-005 (the landing page should link the PDF if one exists).

**Fix path**
Owner decision: either generate `USER-MANUAL.pdf` from the (rebuilt) manual as a release artifact, or formally drop the expectation and record that the `.md`/`.html` is the system of record. Audit flags; does not decide.

---

### [DOC-009] — Minor — Hygiene/Marketing — The README download CTA and badge are hand-maintained per-version, which is the root cause of the version drift

**Evidence**
`README.md:5` (badge) and `:14`/`:30`/`:63` (CTA + body) hard-code the version string; the actual download link `../../releases/latest` (`:14`) is already version-agnostic and resolves correctly. So the *link* is fine — only the human-readable labels drift, and they drift every release because nothing single-sources them (contrast `pyproject.toml:10`, which the code reads via `importlib.metadata`).

**Why this matters**
Every release will reintroduce DOC-001 unless the CTA/badge stop naming a version, or a release-checklist step flips them. This is the durable fix behind the Blocker.

**Blast radius**
- Related findings: DOC-001 (this is its root cause), DOC-006/008 (same "hand-maintained number drifts" pattern).

**Fix path**
Make the CTA version-agnostic ("Download the latest Windows beta") and use a shields.io endpoint or release-driven badge; or add a release-checklist item that updates README + install-guide + USER-MANUAL banner + CHANGELOG header in lockstep.

---

### [DOC-010] — Minor — Accuracy/Hygiene — CHANGELOG `[Unreleased]` header still frames the project as "versioning toward `0.9.0b1`"

**Evidence**
`CHANGELOG.md:8` — "> The project versions toward the `0.9.0b1` Windows beta (Stage 11)…"; `:22` — "These sections accumulate toward the `0.9.0b1` beta release." This sits directly above the excellent, current `[0.9.0b2]` section (`:27+`), creating an internal time-warp: the doc both has shipped b1 *and* b2 and still says it's "versioning toward" b1.

**Why this matters**
Low user impact (the `[0.9.0b2]` content below is correct), but it's a confusing contradiction in the canonical history doc and contributes to the version-drift impression.

**Blast radius**
- Related findings: DOC-001, DOC-011 (ROADMAP has the mirror gap — no forward b2 entry).

**Fix path**
Update the `[Unreleased]` preamble to reflect that b1 and b2 have shipped and what (if anything) now accumulates toward the next release.

---

### [DOC-011] — Minor — Completeness — ROADMAP.md has no forward `[0.9.0b2]` entry and its newest narrative ends at "THE BETA IS BUILT" (b1)

**Evidence**
`ROADMAP.md:75-78` — the most recent concrete milestone narrative is the Stage 11 / `KimCad-Setup-0.9.0b1.exe` "THE BETA IS BUILT. Next: Kim runs it on her real printers." There is no section reflecting the b2 cycle (Duet/Marlin, 29-printer catalog, session token, e2e, macOS/Linux) that the CHANGELOG `[0.9.0b2]` documents.

**Why this matters**
The ROADMAP is where a contributor or watcher checks "where is this going / where is it now." It now lags the CHANGELOG by a full release, so the two project-history docs disagree on the current frontier. The `0.9.0b1` reference at `:75` is defensible as *history* (it narrates the b1 build), so this is a completeness gap, not an accuracy error.

**Blast radius**
- Related findings: DOC-010 (CHANGELOG header), DOC-001.

**Fix path**
Add a b2 milestone section (or an "after the first beta" block) summarizing the post-beta hardening and the remaining gates (real-hardware #11, code signing, macOS/Linux installers).

---

### [DOC-012] — Nit — Hygiene/Architecture — ARCHITECTURE.md module map omits a few real modules and has a formatting bleed at the `webapp.py` row

**Evidence**
Prior cleanup-review (ARCH-05) noted the map omits `cadquery_templates.py` (the actual trusted STEP source), `settings_store.py`, and `subprocess_env.py`; confirmed those files' roles are described in prose but absent from the table. Separately, `ARCHITECTURE.md:117` runs the `webapp.py` row and the `config.py` description together on one line (a table-cell/paragraph merge): "`webapp.py` | The local web layer (see below). |`config.py` loads…" — a rendering glitch.

**Why this matters**
Cosmetic / completeness polish on a contributor doc; no user impact. Flagged once.

**Blast radius**
- Related findings: DOC-002, DOC-003 (same doc, same refresh pass).

**Fix path**
Add the three missing module rows; fix the `:117` line break so `config.py` is its own paragraph/row. Roll into the DOC-002/003 ARCHITECTURE refresh.

---

### [DOC-013] — Nit — Accuracy — `docs/definition-of-done.md` "written plan exists first" claim may overstate current practice

**Evidence**
`docs/definition-of-done.md:9` — "1. **A written plan exists first** (`.claude/plans/` in this repo's practice)…". The user's global instruction record notes the plan-gate hard rule was removed (2026-06-14), so a doc asserting plans-first as a definition-of-done step may no longer match enforced practice.

**Why this matters**
Very low exposure (a contributor-process doc), and the claim is aspirational/descriptive rather than user-facing. Flagged so the owner can reconcile the doc with whether the plan-first step is still required or now optional.

**Blast radius**
- Related findings: none (isolated process claim). Owner/process decision, not an engineering change.

**Fix path**
Confirm whether plan-first is still a done-criterion; soften to "where used" or remove if no longer enforced. Audit flags; does not decide.

---

## Drafts produced

Writer mode is **audit-only**; no drafts produced in this pass. Remediation (including the two APPROVED builds below) is held for owner go-ahead.

## Approved remediation scope (call-outs for the remediation phase)

Two items are already approved to be **built** in remediation; this audit specifies what they must cover so the build is scoped correctly:

**A. `docs/index.html` — marketing landing page (addresses DOC-005).** Must:
- Lead with the honest value prop already proven in `README.md:3` (plain-English/photo/sketch → checked, print-ready, fully local) and the four differentiators (`README.md:20-26`).
- Use a **version-agnostic** download CTA → `releases/latest` (never hard-code `0.9.0b1/b2` — DOC-009), and carry the unsigned-beta + SmartScreen + SHA-256-verify framing honestly.
- Segment the three audiences (non-technical maker · CLI/integrator · contributor) with a path to each (USER-MANUAL Part 1/2/3, api.md, CONTRIBUTING).
- Source every factual claim from the **current** docs (templates.md = 86 families; supported-printers.md = 29 printers + the four-claim honesty key incl. Duet/Marlin; "no metal-validated print yet"). Do **not** inherit copy from the stale README/USER-MANUAL until DOC-001/004/006 are fixed.
- Keep the mock-vs-metal honesty boundary visible (this is KimCad's strongest trust asset).
- Link the PDF manual if DOC-008 is resolved to "build it."

**B. Professionally formatted, complete user manual (addresses DOC-004, DOC-007).** The three-audience structure already exists (`docs/USER-MANUAL.md:7-13`) and is the right frame — the rebuild must *complete* it:
- **Non-technical tier:** add a glossary (DOC-007); cover the install → first-run → describe → check → print path end-to-end (mostly present, refresh for b2).
- **Technical tier:** add **Duet + Marlin** to the connector + mock-server tables with their honest limitations (mirror `supported-printers.md:83-92`); add the **macOS/Linux-from-source** path (mirror CHANGELOG `:47-60`); keep the CLI/config/MCP/CadQuery surface (present, accurate).
- **Architecture tier:** add the **session-token guard** to trust boundaries (mirror `api.md:240-260` / `SECURITY.md:21-30`); align the CadQuery description with the *removed* LLM-CadQuery fallback (DOC-002); add Duet/Marlin to the module/connector map.
- Set the version banner to `0.9.0b2` (DOC-001) and make the count language registry-reconciled (DOC-006).

## Marketing / honesty audit

The README hero is the live marketing surface and is, content-wise, a model of honest beta copy — no overclaim, specific differentiators, the "Beta notes — honest status" block (`README.md:37-43`) states unsigned-installer/SmartScreen, mock-vs-metal, and the curated-29 honestly. The **only** marketing-honesty defect is the version drift (DOC-001): the hero advertises a build (`0.9.0b1`) the project no longer ships. There is no inflated stat, no fictional feature, no euphemized limitation — the corpus's honesty discipline (CONTRIBUTING `:137-139` codifies it: "never narrates a simulated action as a real one") is real and consistently applied. Protect that discipline through the landing-page build: the single risk is a new marketing surface re-introducing a hard-coded version or softening the mock-vs-metal line for punchiness. Don't.

## Patterns and systemic observations

1. **The b2 update reached the reference docs but not the narrative docs.** api.md, supported-printers.md, templates.md, CHANGELOG `[0.9.0b2]`, SECURITY, CONTRIBUTING are all current; README hero, USER-MANUAL, ARCHITECTURE, ROADMAP, and the CHANGELOG `[Unreleased]` header all lag a release. The single highest-leverage remediation is one coordinated "narrative refresh" pass (DOC-001, -002, -003, -004, -006, -010, -011) sourced *from* the already-current reference docs.
2. **Hand-maintained numbers and version strings are the recurring drift vector** — the version label (DOC-001/009), the "about 90" count (DOC-006), and the absent PDF (DOC-008) all stem from values typed by hand instead of generated/single-sourced. `templates.md` (registry-generated) and the code version (`importlib.metadata`) prove the project already knows how to kill drift; extend that to the README badge/CTA and family counts, and add a release checklist.
3. **The honesty boundary is a genuine asset, applied evenly** — mock-vs-metal is the project's credibility moat and is maintained scrupulously across every doc. This is rare and worth saying plainly: the docs' *truthfulness about uncertainty* is excellent; their failure is *staleness*, not dishonesty.

## Appendix: docs reviewed

Repo root: `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `CHANGELOG.md` (head + `[0.9.0b2]`), `CONTRIBUTING.md`, `SECURITY.md`, `HANDOFF.md` (scanned), `pyproject.toml` (version source), `config/default.yaml` (printers/connectors/materials), `dist/release-manifest.json` + `SHA256SUMS.txt` (canonical version/artifact).
`docs/`: `README.md` (index), `USER-MANUAL.md`, `FAQ.md`, `api.md`, `install-guide.md`, `supported-printers.md`, `definition-of-done.md`, `templates.md`, `MODEL-GUIDE.md`, `troubleshooting.md`, `getting-started-windows.md`, `guide-my-designs.md` / `guide-sliders-and-units.md` / `guide-photo-onramp.md` / `guide-settings-and-cloud.md` (scanned), `cadquery-backend.md`, `printproof3d-integration.md`, `dev/cross-platform-packaging.md`, `beta/first-hardware-contact.md`, `audits/cleanup-review-0.9.0b2-2026-06-14.md` (prior review, for scope reconciliation).
Code cross-checks: `src/kimcad/llm_provider.py:339` (removed `generate_cadquery`), `src/kimcad/webapp.py:678/1307-1324/2611-2619` (session token), `src/kimcad/{duet,marlin}_connector.py` + `mock_{duet,marlin}.py` (existence), `kimcad.templates.default_registry()` (86 families / 39 benchmarked / 47 baseline), `config/default.yaml` (29 printers, 8 connectors), `.github/workflows/ci.yml:41` (self-hosted runner — confirms the docs' "self-hosted CI" claim is currently accurate). Programmatic link-crawl of all markdown docs (0 broken user-facing relative links).
