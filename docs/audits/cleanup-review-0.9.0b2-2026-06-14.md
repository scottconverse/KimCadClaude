# KimCad 0.9.0b2 — Post-Release Cleanup Review + Walkthrough

**Date:** 2026-06-14
**Scope:** Version consistency across all surfaces; documentation currency (README, user manual, landing page, seeded Discussions, architecture docs); and a product walkthrough of the near-final 0.9.0b2 build.
**Method:** 7 parallel read-only auditors (static) + a live isolated demo server (`kimcad web --demo`, 0.9.0b2) for runtime evidence.
**Posture:** balanced, audit-only. **No remediation applied, nothing committed or pushed — findings are held per Scott's instruction.**

---

## TL;DR

The **code, build, and release machinery is consistent and correct at 0.9.0b2, and the product is wired and runtime-verified.** The gap is entirely in the **human-readable prose**: the README, install guide, user manual, the pinned GitHub Discussion, and `ARCHITECTURE.md` all still present **0.9.0b1** as the current release and omit the headline 0.9.0b2 features — even though the *reference* docs (api.md, supported-printers.md, cadquery-backend.md) are current. The single most damaging instance: the **README download CTA and the pinned Discussion link `KimCad-Setup-0.9.0b1.exe`** — i.e. they point a new beta tester at the build I just superseded. Separately, **`ARCHITECTURE.md` describes a *removed* untrusted-code-exec path as live**, and **no GitHub Pages storefront exists** (which needs a scope decision).

Verdict: **ship-as-is is fine for the binary** (it's correct), but the **doc/version drift should be fixed before pointing testers at the repo**, or they'll fetch the wrong build.

---

## Severity rollup (consolidated, de-duplicated)

| Severity | Count | Items |
|---|---|---|
| Blocker | 0 | — |
| Critical | 2 | C1 version-drift-misdirects-testers · C2 ARCHITECTURE.md documents removed fallback as live |
| Major | 3 | M1 b2 features missing from narrative/manual/arch/discussions · M2 manual 86-vs-90 contradiction · M3 no landing page (decision) |
| Minor | 5 | def-of-done heading · no PDF · manual glossary · arch module-map omissions · discussions radar staleness |
| Nit | 3 | discussions disk-figure · `#settings` anchor · version-agnostic CTA |

Raw per-role counts (before dedup): versions 0/0/3/1/0 · readme 0/2/2/1/1 · user-manual 0/3/2/2/1 · landing 2/0/1/0/0 · discussions 0/1/2/1/1 · architecture 0/1/3/2/0 · walkthrough-static 0/0/0/1/1.

---

## Findings

### C1 — Critical — Version drift misdirects beta testers to the superseded 0.9.0b1 build
**Dimension:** Version / Docs
**Evidence (all point at b1 while the shipped build is 0.9.0b2 / `KimCad-Setup-0.9.0b2.exe`):**
- `README.md:5` badge `beta-0.9.0b1`; `README.md:14` download CTA "`0.9.0b1` beta"; `README.md:30` `KimCad-Setup-0.9.0b1.exe` (VER-001, RM-01, RM-02)
- `docs/install-guide.md:16` SHA-256 verify command `Get-FileHash .\KimCad-Setup-0.9.0b1.exe` — errors against the real download (VER-002)
- `docs/USER-MANUAL.md:15` "this manual tracks the `0.9.0b1` Windows beta" (VER-003, UM-01)
- **GitHub Discussion #1 (pinned Announcement)** "KimCad 0.9.0b1 — the Windows beta is here" links `KimCad-Setup-0.9.0b1.exe` (DISC-01)

**Why it matters:** These are the highest-traffic surfaces a tester reads first. Following the README CTA or the pinned announcement downloads the prior build (missing the 54 commits of b2 hardening), and the install guide's integrity-check command fails on the actual file — undermining the exact trust step it teaches.
**Fix path:** Bump the b1 markers to b2 on README (lines 5/14/30), install-guide (line 16), USER-MANUAL (line 15); post/repin a 0.9.0b2 Announcement and unpin the b1 one. Prefer the `KimCad-Setup-<version>.exe` placeholder already used at `README.md:139` so it can't drift again. **Leave** legitimate history (CHANGELOG older sections, "after the 0.9.0b1 tag" phrasing, the Stage-11 history line).
**Blast radius:** Pure docs/Discussions text — no code, no tests. The root cause is that the README/manual are manually maintained outside the `test_version_single_source.py` net; add them to the release checklist.

### C2 — Critical — `ARCHITECTURE.md` documents the REMOVED LLM-CadQuery fallback as a live feature
**Dimension:** Docs (security-relevant)
**Evidence:** `ARCHITECTURE.md:81,83,91` describe `generate_cadquery` / "parallel backend … falls back to CadQuery codegen" / `sanitize_cadquery` over "untrusted generated script" as current. But `llm_provider.py:339` ("generate_cadquery was removed"), the 4-method Provider Protocol (`llm_provider.py:105-143`), and `pipeline.py:79-81` confirm the LLM-CadQuery fallback was **removed** (measured lift 0); CadQuery now runs only the project's own trusted template twins. The canonical `docs/cadquery-backend.md:26-31` already labels it removed history.
**Why it matters:** This is the highest-risk subsystem (the only place AI-written Python was ever exec'd). The root architecture doc tells an auditor/contributor that an untrusted-codegen path is still live — a phantom threat surface, and a trap for anyone re-wiring against it.
**Fix path:** Rewrite the three rows to match `cadquery-backend.md`: 4 LLM jobs (drop `generate_cadquery`); LLM codegen is OpenSCAD-only; reframe `cadquery_runner`/`cadquery_templates` as the deterministic STEP-twin engine, not an untrusted-script fallback.
**Blast radius:** Doc-only, but pairs with M-arch findings (module map omissions) — fix together in one ARCHITECTURE.md pass.

### M1 — Major — The headline 0.9.0b2 features are missing from the narrative / manual / architecture / discussions
*(The reference docs — api.md, supported-printers.md, cadquery-backend.md, README connector table — ARE current; this is a narrative/summary lag.)*
- **Session-token guard (#31):** absent from README Web-UI security section (RM-03), USER-MANUAL Trust Boundaries (UM-04), ARCHITECTURE.md web layer (ARCH-03). *(Runtime-confirmed working — see Walkthrough.)*
- **Duet + Marlin connectors (#26):** absent from USER-MANUAL connector table (UM-02), ARCHITECTURE.md module map + factory list (ARCH-02), Discussions help-test/Q&A (DISC-03); README headline list omits them (RM-05, W-01).
- **29-printer catalog (#22):** absent from USER-MANUAL (UM-03); Discussions radar still lists "more connectors/printers" as future (DISC-04).
- **macOS/Linux from source (#13):** USER-MANUAL is Windows-only framed (UM-06); ARCHITECTURE.md omits it (ARCH-04); Discussion #4 lists it as "no promises, no timeline" though it shipped (DISC-02).
- README beta-notes/history never names 0.9.0b2 (RM-04).

**Why it matters:** The manual is the canonical how-to for the most safety-sensitive surface (send-to-printer); a Marlin/Ender or Duet owner finds no path. The narrative reads as if the project stopped at b1.
**Fix path:** Add the four features to the manual (connector table + printer step + trust boundaries + platform note), ARCHITECTURE.md (module map + web-layer + platform), README (headline connector list + a short b2 history entry), and refresh Discussions #2/#3/#4. Mirror the already-correct `supported-printers.md` / `api.md` wording.

### M2 — Major — USER-MANUAL internal contradiction: "about 90" vs 86 families
**Evidence:** `docs/USER-MANUAL.md:108` "about 90 of them" vs `:347` "86 parametric families"; registry-authoritative count is **86** (`docs/templates.md:3`, runtime `/api/templates` = 86). **Fix:** change `:108` to 86.

### M3 — Major (decision) — No GitHub Pages marketing landing page exists
**Evidence:** No `docs/index.html`; `gh api .../pages` → 404 (Pages disabled); no gh-pages branch / deploy workflow (LP-1/2/3). The only HTML in `docs/` are design *prototypes*. **Note:** task #11 ("Landing page: professional layout…") is marked **completed**, which does not match the repo state — flagging honestly rather than letting that stand.
**Why it matters:** The project's own standards call for a GitHub Pages storefront; a public beta has no served value-prop page (the README is the de-facto front door).
**Decision needed (Scott):** build a real `docs/index.html` storefront + enable Pages, **or** formally de-scope it (README = canonical landing surface) and reconcile task #11. The honest README + supported-printers copy is strong raw material either way.

### Minor / Nit
- **Minor** `docs/definition-of-done.md:47` heading names `0.9.0b1` for criteria that still apply (VER-004) — generalize.
- **Minor** No `README-FULL.pdf` / `USER-MANUAL.pdf` anywhere (ARCH-06, UM-07) — project standards expect them. *Decision:* required release artifacts, or drop the expectation (the `.md`/`.html` are the system of record)?
- **Minor** USER-MANUAL has no standalone glossary for the non-technical audience (UM-08).
- **Minor** ARCHITECTURE.md module map omits `cadquery_templates.py` (the actual STEP source), `settings_store.py`, `subprocess_env.py` (ARCH-05).
- **Minor** Discussions #4 radar understates shipped work (DISC-04).
- **Nit** Discussions #3 "~20 GB" disk figure not reconciled with FAQ's per-component numbers (DISC-05).
- **Nit** `ExportPanel.tsx:230` uses `#settings` vs the router's `#/settings` (works today via tolerant parse; fragile) (W-02).
- **Nit** README version-in-CTA/badge is hand-maintained (root cause of C1) — consider a version-agnostic CTA + release-checklist item (RM-06).

---

## Walkthrough — runtime evidence (live, 0.9.0b2)

Driven against a real isolated demo server (`kimcad web --demo`, isolated `USERPROFILE`/`HOME`/`LOCALAPPDATA`; real `~/.kimcad` and `%LOCALAPPDATA%\KimCad` verified untouched). The **static wiring map** confirmed all 24 `api.ts` endpoints map to real routes, every control drives a live handler, and demo mode is strictly opt-in. **Runtime API confirmation of the highest-risk b2 flows:**

| Check | Result |
|---|---|
| `/api/health` | `version 0.9.0b2`, openscad/orcaslicer/cadquery all true ✓ |
| Duet + Marlin in `/api/connectors` | present (`duet`, `marlin`) alongside mock/octoprint/moonraker/prusalink/bambu_p2s/bambu_a1 ✓ |
| `/api/connections` (Settings card source) | `duet`→type `duet`, `marlin`→type `marlin` ✓ |
| `/api/options` | **29 printers**, 4 materials ✓ |
| `/api/templates` | **86 families** ✓ |
| Session-token guard | POST no-token → **403**, bad token → **403**, valid per-boot 43-char token → **200** ✓ |
| Design pipeline (demo) | returns `report.readiness`, **4 sliders**, `mesh_url`, `step_url` ✓ |
| Home isolation | no writes to real data dirs ✓ |

**Limitation (honest):** the **browser-visual** pass (screenshots, click-through of each screen) could **not** run under the preview harness. KimCad deliberately disables `SO_REUSEADDR` on Windows (`webapp.py:2556` `_ExclusiveBindServer`, ENG-001/WALK-A-001) so a second instance can't silently bind the same port; the preview harness reserves the declared port before launching, and KimCad's no-reuse bind then refuses it. **This is correct product behavior, not a defect.** The static wiring map + the API-level runtime confirmations above substitute for the visual pass. A future visual walk needs a harness that lets the server own its port (e.g. start the server first, attach a connect-only browser driver).

---

## What's working (credit, specific)

- **Version single-source is bulletproof where it's automated:** `pyproject.toml` is the lone literal; `test_version_single_source.py` forbids any other code literal and checks the PEP440↔npm twin (incl. the lockfile); CLI/`/api/health`/MCP all read it dynamically; the installer is version-agnostic (`*.iss` via `/DAppVersion`).
- **Product wiring is solid and runtime-confirmed:** connectors (incl. the new Duet/Marlin), 29-printer catalog, 86 families, the session-token guard, and the design pipeline are all live, not just coded.
- **Reference docs are current and honest:** `supported-printers.md`, `api.md`, `cadquery-backend.md`, `cross-platform-packaging.md`, and the README connector table + platform notes + beta-honesty (unsigned/SmartScreen/#11-pending) are accurate.
- **Discussions** is enabled with all five boards seeded by genuine, human, welcoming posts (two correctly pinned) — they're stale on version/features, not low-effort.
- **The user manual's structure** (three audiences, plain-language beta honesty, real ASCII architecture diagrams) is strong — it's the *content currency*, not the craft, that lags.

---

## Decisions for Scott

1. **Landing page (M3):** build a GitHub Pages storefront, or de-scope it (and reconcile task #11's "completed" status)?
2. **PDFs (Minor):** are `README-FULL.pdf` / `USER-MANUAL.pdf` required release artifacts, or do we drop that expectation?
3. **Remediation go-ahead:** C1/C2/M1/M2 plus the minors are fast, low-risk **doc-only** edits I can batch to 0/0/0/0/0 and re-verify. Holding per your instruction — say the word and I'll fix and re-audit.

*No product code was modified; nothing was committed or pushed.*
