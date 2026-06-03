# KimCad — Handoff (2026-06-02 — Stage 7 IN PROGRESS: Smart Mesh + PrintProof3D, Slice 1 done on `stage-7-smart-mesh`)

## ⛔ READ FIRST

- **🔧 STAGE 7 IN PROGRESS — branch `stage-7-smart-mesh`** (off `main`/`stage-6`; pushed; NOT merged).
  **= Smart Mesh + PrintProof3D + readiness report.** Architecture (spec §6.12): **PrintProof3D is the
  per-artifact validation ENGINE; Smart Mesh is KimCad's synthesis + history layer on top** that outputs
  the readiness report card (design screen `docs/design/screens/10-smartmesh-report.png`: a score gauge,
  verdict, confidence badge, risks, recommendations, comparison-to-past line, "PrintProof3D validation
  engine" attribution). **PrintProof3D is BUILT + available locally** at
  `C:\Users\scott\Documents\antigravity\eager-archimedes\PrintProof3D\target\release\printproof3d.exe`
  (owner's MIT Rust engine; NOT bundled in this repo) — CLI:
  `printproof3d validate-model --model <stl> --printer <profile.json> --material <profile.json> -o <report.json>`;
  output schema = `…\PrintProof3D\schemas\validation_report.schema.json` (status pass/warning/fail ·
  confidence_level · issues[] {id like `OVERHANG_UNSUPPORTED`, message, severity blocker|critical|major|minor|nit,
  suggested_fixes[], region}). **Slice plan (per-slice: real `audit-lite` → fix → push):**
  **(1) ✅ DONE** — `src/kimcad/smart_mesh.py` readiness model + scoring (pure `assess_readiness`; PrintProof3D
  report is an optional typed input; verdict tone = worst of KimCad's gate/score/risk AND the engine's own
  status; honest attribution; audit-lite 0/0/0/0/0, `docs/audits/stage-7/audit-lite-slice-1-...md`).
  **(2) ✅ DONE** — `src/kimcad/printproof3d.py` arm's-length wrapper: `validate_model(...)` invokes the CLI →
  parses the JSON into `PrintProofReport`; generates valid PrintProof3D printer+material profile JSON from
  KimCad's Printer/Material (`printer_profile`/`material_profile`); injectable `runner` (mockable); config
  `binaries.printproof3d` + `Config.printproof3d_binary()` (None when absent → degrade); NEVER raises.
  **LIVE-VERIFIED** against the real engine (returned a parsed report). audit-lite 0/0/0/0/0
  (`docs/audits/stage-7/audit-lite-slice-2-...md`).
  **(3) RESUME HERE** — pipeline + `PrintReport` + design-API integration: compute `assess_readiness(...)` in
  the assemble tail (invoking `validate_model(mesh, printer, material, binary=config.printproof3d_binary())`),
  fold `MeshReadiness` into `PrintReport` + the `/api/design` + `/api/render` responses; the gate hard-fails a
  PrintProof3D `fail` beyond size/watertight. **⚠ BED-POSITION the mesh first**: translate the oriented mesh so
  its min-corner sits at the bed origin `[0,build]` before calling `validate_model`, else every part trips a
  false `MODEL_OUT_OF_BOUNDS` (PrintProof3D measures extents from the origin). **(4)** the readiness report CARD
  (frontend, to design screen `10-smartmesh-report.png`) — UX-acceptance slice, RENDERED browser check.
  **(5)** learning/history store + the comparison line. **(6)** docs + PrintProof3D tooling/config + stage-end
  `audit-team` gate → 0/0/0/0/0 → merge + tag `stage-7`. NOTE: the "multiple-shells false-flag on hollow
  containers" the ROADMAP lists is ALREADY fixed (`validation.py` `_stray_body_count`) — don't redo it.
  Branch green: **638 pytest (incl. live) + 37 vitest**.

- **✅ STAGE 6 IS DONE — merged to `main` and tagged `stage-6`** (the tag was advanced past the merge to
  this docs-DONE commit so the tagged artifact's docs say "done", not "pending" — the Stage-4/5 lesson).
  All 5 slices (advisor, fallback, 3-axis grading, bake-off, plan-failure robustness) passed the real
  `audit-lite` to 0/0/0/0/0, then the full `audit-team` stage gate ran 2026-06-02 (0B/1C/6Maj/13Min/11Nit)
  and was remediated to **0/0/0/0/0** — package at `docs/audits/stage-6/audit-team-stage-6-2026-06-02/`
  (+ `REMEDIATION.md`). **The model decision is settled: `gemma4:e4b` stays; `qwen2.5-coder:1.5b` was
  evaluated via the live bake-off and rejected (0/10).** **RESUME HERE = Stage 7 (Smart Mesh + PrintProof3D + readiness report).** Stage 6 is complete — do NOT
  re-run its gate. The model decision is settled (gemma stays, qwen rejected) — do NOT reopen it.
- **✅ STAGE 5 IS DONE — merged to `main` (merge commit `14896d6`) and tagged `stage-5`** (the tag was
  advanced past the merge to this docs-DONE commit so the tagged artifact's docs say "done", not
  "pending" — the Stage-4 lesson). Slices 1–5 (engine, pipeline tiering, re-render API, live sliders,
  benchmark+docs) each passed the real `audit-lite` to 0/0/0/0/0, then the full `audit-team` stage
  gate + re-audit closed at 0/0/0/0/0 (`docs/audits/stage-5/audit-team-stage-5-2026-06-02/` +
  `…-reaudit/`).
- **Stage 4 is DONE — merged to `main` (merge commit `dcbcd1a`) and tagged `stage-4`** (the `stage-4`
  tag was advanced past the merge to the docs-consistency commit — see "Tag provenance" below — so
  the tag and the `main` head are the same commit, `181115e`).
- **Source of truth = this doc + the in-repo v3.0 spec + the design handoff** (both under
  `docs/design/`). Do NOT rebuild from memory — I have lost context across sessions before.
- **The agent-pipeline skill is DEAD for this project.** Scott killed it (it can't run from the
  wrong cwd / an uninitialized repo). This project runs the **manual process** in §6. Do NOT
  re-invoke `agent-pipeline-claude:run`.

---

## ✅ Stage 6 — DONE (merged to `main`, tagged `stage-6`) — model layer

**Scope (the "roadmap scope" Scott chose):** evaluate swapping the default from `gemma4:e4b` to
`qwen2.5-coder:1.5b` *if it clears a bake-off*, behind a tiered fallback, with richer grading to judge it.
**Outcome: the swap was rejected — qwen can't produce a plan; `gemma4:e4b` stays the default.** Standing
constraint (Scott, verbatim): *"the model must be choosable, not hardwired. The code should examine the
hardware then make a recommendation based on what's available."* (Already choosable via config backends +
`config/local.yaml` + `--backend`; Slice 1 added the missing hardware/availability probe.)

**All 5 slices done (each through the real `audit-lite` skill → 0/0/0/0/0; reports in `docs/audits/stage-6/`):**

- **Slice 1 — hardware/availability-aware advisor** (`model_advisor.py` + `kimcad models`). Best-effort
  RAM/CPU/GPU + Ollama `/api/tags` probes (degrade to None, never raise); a pure `recommend()` (best
  installed-and-fitting local wins; names an upgrade; non-China alternative only when the pick is
  China-origin; unknown RAM never claims a fit). **Advisory ONLY — never rewrites config.** `_installed_match`
  requires an exact tag (a `:1.5b` install must NOT satisfy a `:7b` spec — a real bug, fixed+regression-tested).
- **Slice 2 — tiered fallback** (`llm_provider.py` `FallbackProvider` + a `Provider` Protocol). A primary
  connection/timeout/404 error transparently retries an opt-in alt (`llm.alt_backend`, default null);
  thread-local stickiness; `primary.max_attempts→1` when an alt exists. Wired in `cli._build_pipeline` +
  `webapp._real_provider`. `pipeline.py` annotates `provider: Provider`.
- **Slice 3 — 3-axis benchmark grading** (`benchmark.py`). matches-request / correct-dimensions /
  slices-clean, each tri-state (a None/unassessed axis never blocks). Backward-compatible: the
  `--min-success-rate` done-gate still scores on completion; `graded_passed` is additive. `kimcad bench --slice`
  grades the slices-clean axis (real OrcaSlicer, opt-in).
- **Slice 4 — model bake-off** (`bakeoff.py` + `kimcad bakeoff`). Runs the benchmark per backend and
  recommends switch-or-keep (recommend ONLY — never edits config; the flip is the human's call). Each model
  measured in isolation (no fallback contamination). Added the `local_qwen` backend.
- **Slice 5 — plan-failure robustness** (`PlanParseError` in `llm_provider.py`; `PipelineStatus.plan_failed`).
  A model returning un-parseable output fails clean (CLI exit **6**, distinct from gate_failed's 5; clean web
  copy) instead of a raw pydantic traceback. The catch is narrow (only the parse boundary), so a real bug
  elsewhere — or a genuine connection error — still propagates.

**BAKE-OFF VERDICT (run LIVE on this box 2026-06-02 — both models pulled here; output in `output/bakeoff/`):**
`qwen2.5-coder:1.5b` = **0/10 completed** — it fails the design-plan step on every case (returns the JSON
schema instead of an instance; confirmed not a config artifact — fails identically with JSON mode forced).
`gemma4:e4b` = 8/10 completed, 4/10 fully graded, ~10 min/prompt. **A code-completion model is the wrong tool
for the NL→structured-plan step; a bigger qwen is larger than gemma → slower → fails the "faster" goal. So
`gemma4:e4b` STAYS the default — no config change.** Hand-off doc (how to re-run it live): `docs/benchmarks/stage-6-model-bakeoff.md`.

**STAGE GATE — DONE.** The full 5-role `audit-team` ran 2026-06-02 (0 Blocker · 1 Critical · 6 Major ·
13 Minor · 11 Nit = 31; the Critical was a stale bake-off doc showing qwen winning, the inverse of the
verdict). Every finding was remediated to **0/0/0/0/0** (`REMEDIATION.md`), the native Windows gate passed
(ruff; **609 pytest incl. live OrcaSlicer**; **37 vitest**; SPA build reproducible), and the branch was
merged to `main` + tagged `stage-6`. The model decision is SETTLED (gemma stays; qwen rejected) — do NOT
reopen it. **NEXT = Stage 7 (Smart Mesh + PrintProof3D + readiness report).**

---

## ✅ Stage 5 — DONE (merged to `main`, merge commit `14896d6`, tagged `stage-5`) — deterministic template engine + live sliders

**Merged + tagged.** Stage 5 makes the headline UX real: drag a parameter slider → re-render in
**<1 s with NO model call** (per-family timings in `docs/benchmarks/stage-5-template-families.md`).
On the old LLM-writes-OpenSCAD engine that was impossible (every change round-tripped the model).

**DONE — all five slices, each through the real `audit-lite` skill to 0/0/0/0/0 (reports committed in
`docs/audits/stage-5/`):**
- **Slice 1 — `src/kimcad/templates.py`:** a registry of 7 parametric families (snap_box, box,
  enclosure, tube, wall_hook, cable_clip, drawer_divider) built on the proven `library/*.scad`
  modules; a typed/range-bounded `ParamSpec` schema; OpenSCAD `emit` by pure string substitution
  (no model, injection-safe — only clamped finite numbers reach emit); analytic `expected_bbox` per
  family; param clamping + ordering constraints (tube id<od) + an alias-collision guard.
- **Slice 2 — `pipeline.py` tiering:** a template-covered `object_type` builds DETERMINISTICALLY
  (no model call, single-shot, fail-closed); everything else falls back to LLM codegen.
  `PipelineResult.template`; the gate plan's bbox + dimensions aligned to the template's values.
- **Slice 3 — the re-render API:** `pipeline.rerender()` + a shared `_assemble_result` tail;
  `webapp.py` `POST /api/render/<id>` (deterministic re-render, no model); `/api/design` returns the
  typed `parameters` snapshot + `template` name; a re-render invalidates the cached slice/G-code,
  serializes concurrent drags (`render_lock`), versions the `mesh_url`, `/api/mesh` strips the query.
- **Slice 4 — frontend live sliders (`frontend/src/components/RightPanel.tsx` et al.):** a slider per
  backend parameter for template-backed designs; drag → ~150 ms-debounced `POST /api/render/<id>`;
  the viewport reloads the versioned mesh while the previous one stays on screen; gate/report/values
  re-sync to server truth; a monotonic `renderSeq` guard drops stale responses; LLM-backed parts stay
  read-only; labelled + `aria-valuetext` + axis chips; mobile 44 px touch target.
- **Slice 5 — `src/kimcad/template_bench.py` + `docs/benchmarks/stage-5-template-families.md`:** a
  deterministic-family benchmark proving every family re-renders watertight at its declared envelope,
  byte-deterministic, NO model call (a `_NoModelProvider` raises if touched), in <1 s. Plus the
  Stage 5 doc updates (ARCHITECTURE/CHANGELOG/ROADMAP/README).

**Stage gate (audit-team, 2026-06-02):** the 5-role `audit-team` ran on the branch and rolled up
**0 Blocker · 0 Critical · 3 Major · 14 Minor · 14 Nit (31)** — no Blockers/Criticals; every
load-bearing safety invariant verified holding (injection-safe emit, no-model re-render, gate-fail
re-render drops the stale slice at runtime, concurrent re-renders serialized, send-gate boundary
intact). All 31 were remediated, then re-audited to **0/0/0/0/0**. Authoritative record:
`docs/audits/stage-5/audit-team-stage-5-2026-06-02/` (`00-executive-audit.md` + 5 deep-dives +
`sprint-punchlist.md` + `next-sprint-watchlist.md`).

**Native Windows gate (passed before merge):** ruff clean; full `pytest` green **incl. live
OrcaSlicer**; **vitest** green; SPA build byte-reproducible (the pre-push hook's `committed == fresh
build` check passed); `npm audit` 0. (Run `scripts/ci.sh` / the pre-push hook for the authoritative
count; do NOT hand-copy a number here that can go stale — that was DOC-001.)

**➡️ Stage 6 is now done on the branch (model decision settled: `gemma4:e4b` stays, the `Qwen2.5-Coder
1.5B` candidate was evaluated and rejected) — see the authoritative "Stage 6" section at the TOP of this
doc, not this older Stage-5 "next" note.**

---

## ✅ Stage 4 — DONE (merged to `main`, merge commit `dcbcd1a`, tagged `stage-4`)

The minimal web UI is now the designed React SPA, served locally, with a real 3D viewport — the
§5 design at high fidelity. Built in **5 slices** off branch `stage-4-react-spa-shell` (from `main`
@ `efd2b72`), each run through the real `audit-lite` **skill** to 0/0/0/0/0 with rendered
desktop+mobile visual checks, then full `ruff` + `pytest`, then pushed. Slice + gate audit reports
are committed under `docs/audits/stage-4/`.

**What shipped:** **1** build seam (React 18 + TS + Vite 8 → committed `src/kimcad/web/`, served at
`/` + `/assets/`); **2** Workshop design system + self-hosted latin fonts + topbar + landing; **3**
3-col workspace + vanilla Three.js `KCViewport` loading the REAL `*.oriented.stl` via `STLLoader`;
**4** wired flow (prompt → `/api/design` → conversation + plan + printability report, all 4 statuses)
+ field-contract tests + **vitest** stood up; **5** printer/material selectors + gate-aware slice
(`/api/slice/<id>`) + G-code/model download + read-only connector status.

**Gate: PASSED at 0/0/0/0/0.** The 5-role `audit-team` (rendered + runtime) ran 2026-06-01 on the
branch and rolled up **0 Blocker · 0 Critical · 6 Major · 19 Minor · 9 Nit (34)** — no
Blockers/Criticals; every safety invariant verified clean (a gate-failed part is never *sent* to a
printer by the web/CLI design flows — web blocks slice+send, CLI `--send` refuses, `--proceed-anyway`
slices for inspection only; see the send-gate boundary note in §2) — all tested; plus no traversal
bypass; no XSS; no credential leak; build byte-reproducible; runtime green
end-to-end with a real OrcaSlicer slice. All 34 were fixed, then a 5-role **re-audit** surfaced 3
more (UX-R01 dimension-pills harness-artifact, NEW-T01 contract-test cross-module collision, UX-R02
touch-target verification gap) — all resolved — converging to **0/0/0/0/0**, then merged + tagged.
Authoritative record is committed in-repo:
- Package: `docs/audits/stage-4/audit-team-stage-4-2026-06-01/` (`00-executive-audit.md` + 5 deep-dives
  + `REMEDIATION.md`).
- Re-audit: `docs/audits/stage-4/audit-team-stage-4-2026-06-01-reaudit/` (`00-reaudit-closure.md` +
  the role re-audits).

**Tag provenance (why the tag isn't the merge commit):** the Stage-4 feature merge is commit
`dcbcd1a`, but that merge still carried an earlier, self-contradicting version of HANDOFF/ROADMAP (a
"DONE" banner over leftover "Stage 4 is next / fix all 34" text). Those docs were corrected on `main`
*after* the merge, and the **lightweight `stage-4` tag was advanced from `dcbcd1a` to the
docs-consistency commit** so the tagged artifact carries the corrected docs rather than the
contradictory ones. The `stage-4` tag and the `main` head are therefore the same commit (verify:
`git rev-parse stage-4` == `git rev-parse main`); `dcbcd1a` remains the merge commit for provenance.

**Backend API contract (the unchanged seam the SPA wires to):** `POST /api/design` {prompt} →
{status, clarification?, plan{object_type,summary,target_bbox_mm}, report{gate_status,headline,dims,
findings,...}, error?, has_mesh, mesh_url?}; `GET /api/mesh/<id>` (STL/3MF); `POST /api/slice/<id>`
{printer,material} → {sliced,reason?,estimate,gcode_url?}; `GET /api/gcode/<id>`; `GET /api/options`;
`GET /api/connectors`; `GET /api/connector-status/<name>`; `POST /api/send/<id>` {connector}. The
server reads `web/index.html` at startup and serves `/`, `/assets/<f>`, `/vendor/<f>`, plus the API.
Browser **send** is intentionally NOT wired in the SPA (it's Stage 10) — the web UI is status +
slice + download; the CLI (`--send`) and MCP are the send paths today.

---

## 1. Where the code is

- **Repo:** `github.com/scottconverse/KimCadClaude` (private). **GitHub is the only remote.**
- **`main`:** tags **`stage-0` / `stage-1` / `stage-2` / `stage-3` / `stage-4`** — all done, audited
  to **0/0/0/0/0** with `audit-team`, merged + tagged. **Stage 3 tag @ `96aba02`; Stage 4 merge @
  `dcbcd1a`, with the `stage-4` tag advanced to the docs-consistency commit (= the post-cleanup
  `main` head — see "Tag provenance" above).**
  `main` is in sync with `origin/main`.
- Branches `stage-3-printer-coverage` and `stage-4-react-spa-shell` are merged to `main` (not deleted).
- **Tests: 404 passing (incl. 4 live OrcaSlicer slices), `ruff` clean.** Fast inner loop:
  `pytest -m "not live"` (= 400 passed, 4 deselected). **LESSON (load-bearing): never claim "green"
  off `-m "not live"` + a local commit — run the FULL suite AND PUSH so the hook gates the live tests.**
- **Supported gate = native Windows.** The pre-push hook (`.githooks/pre-push` → `scripts/ci.sh` =
  ruff + the FULL pytest incl. live) gates every push on Windows; enable per clone with
  `git config core.hooksPath .githooks`. The frontend steps — `npm --prefix frontend run test`
  (vitest, 19 passed) and `run build` — also pass natively on Windows, and `npm audit` = 0.
  **Do NOT report `bash scripts/ci.sh` as "green" from WSL/Linux:** `frontend/node_modules` is
  installed on Windows, so only `@rolldown/binding-win32-x64-msvc` is present; Vite 8 / Rolldown
  can't load its Linux native binding under WSL and the frontend step fails. That is an environment
  mismatch, not a code defect — a Linux `npm ci` would install `@rolldown/binding-linux-x64-gnu` —
  and the committed SPA build + the Python gate are unaffected. State the gate by environment; don't
  assert a cross-platform "ci.sh green".
- **Project root: `C:\Users\scott\dev\kimcad`** — deliberately OUTSIDE OneDrive (venv + slicer
  binaries trigger OneDrive sync storms). NEVER use any OneDrive path.

## 2. Stage 3 — what shipped (software-complete + mock-tested; NO real hardware)

- **Connectors:** OctoPrint + **Moonraker/Klipper** + **PrusaLink/Prusa** + the `LoopbackConnector`
  mock + KimCad's own MCP server. The `PrinterConnector` Protocol is the seam. Connectors are
  stdlib-only (zero new deps).
- **Per-printer per-material profiles, honestly:** the cross-vendor `_GENERIC_FILAMENT` fallback
  was REMOVED; each printer is offered only the materials it has a verified profile for. The
  **Elegoo Neptune 4 Max has NO TPU profile** → TPU is "not available" for it; the UI explains why.
- **Ready/not-ready connection-status UI:** `GET /api/connector-status/<name>`, a badge mapped to
  the app's green/amber/red scale, a typed `reason` vocabulary on every not-ready branch, ARIA
  live region. Never 5xx, never leaks a credential.
- **Honesty hardening (from 3 audit passes):** auth-vs-offline on a large-upload mid-write reset
  (shared `auth_error_if_upload_rejected`); `decode_json` for a garbage HTTP-200; typed `reason` +
  `simulated` symmetric on `/api/connector-status` AND `/api/send`; **the WEB GATE GUARD** — the
  Blocker both prior audits missed: `/api/slice` + `/api/send` now refuse a gate-FAILED part
  server-side (`gate_status_by_rid` in `webapp.py`), mirroring the CLI.
- **Send-gate boundary (documented decision, 2026):** the "don't dispatch a gate-FAILED part"
  block lives in the DESIGN FLOWS that know the verdict — the web (`/api/slice` + `/api/send`,
  no override) and the CLI (`--send`, which refuses). `--proceed-anyway` slices a failed part for
  **inspection only** (a real diagnostic for an engineer; never auto-sent). The MCP `send_print`
  primitive enforces explicit confirm + a proven motion-bearing slice but **NOT** the printability
  gate (it only gets a file path, no design context) — so a power user can deliberately override
  the gate (`--proceed-anyway` slice) and then explicitly `send_print` that file, two deliberate
  acts treated as clear intent on an engineering tool. Kept intentionally (3D-printer owners are
  power users); a universal "a failed part never prints" guarantee, if ever wanted, means tagging
  failed slices so connectors refuse them — revisit with the Stage-10 export/print UI. The code
  comment lives at `mcp_server.py` `send_print`.
- Real prints happen only at Kim's, the final stage (Stage 10 in the v3.0 plan). Kim's printers:
  Bambu **P2S** + A1, Elegoo Neptune 4 Max.

## 3. The canonical spec + design — IN THE REPO

- **`docs/design/KimCad-Unified-Product-Spec-v3.0.md`** — the controlling v3.0 product spec
  (supersedes v2.1). **Work ONLY with this + the design spec; ignore the companion build-spec /
  decision-log / other spec copies** (Scott's explicit directive).
- **`docs/design/`** — the design handoff: a pixel-level `README.md`, **11 screen PNGs**
  (`screens/`), and a **runnable React + Three.js reference prototype** (`prototype/jsx/`). This is
  the spec §5 UX at high fidelity = the **Stage-4+ acceptance target**. Default theme **Workshop**
  (warm sand `#f0ebe0` / terracotta `#c8623a` / dark viewport `#14171c`). Fonts: Bricolage
  Grotesque / Hanken Grotesk / JetBrains Mono. (Also extracted at
  `C:\Users\scott\dev\kimcad-design-handoff\`.)

## 4. The stage plan (9 stages to the v3.0 Windows beta; Stages 3–4 done)

3 ✅ printer coverage · 4 ✅ React SPA shell + viewport · 5 ✅ deterministic template engine +
live sliders · 6 ✅ model layer (advisor + fallback + grading + bake-off; gemma stays, qwen ruled
out) · **7 = Smart Mesh + PrintProof3D + report** · 8 = CadQuery parallel backend · 9 = image on-ramp
(opt-in) · 10 = direct-print UI + Bambu + first-run wizard · 11 = Windows installer + beta gate. (Final-level breadth + real-hardware =
post-beta.) **KEY INSIGHT:** the instant-slider UX (re-render <1s, no LLM) is impossible on the
current **LLM-writes-OpenSCAD** engine — there is **no `templates/` module**; the deterministic
template engine (Stage 5) is the critical path, and UX-first + architecture-first converge there.

## 5. Stage 5 scope — deterministic template engine + live sliders (✅ DONE — merged + tagged `stage-5`; see the Stage 5 section up top)

The **critical path**. Stage 4 delivered the SPA + viewport with **read-only** slider scaffolding
only, because true live sliders are impossible on the LLM-writes-OpenSCAD engine (re-render goes
through the model). Stage 5 builds the `templates/` module that makes instant, local re-render real:

- A `templates/` engine of named parametric families; the planner picks a template + fills named
  parameters; re-render is a pure deterministic pass — **<1s, no model in the loop**.
- **Named live sliders** wired to template parameters: drag → re-render instantly, fully local —
  upgrading the Stage-4 read-only scaffolding into functional controls.
- The LLM-writes-OpenSCAD path stays as the tiered fallback for prompts no template covers.
- **Exit:** named parameter sliders drag → re-render in <1s with no model call across the template
  families; the tiered template→LLM fallback is proven. Tests + a real run-through on the app.
- First action: branch `stage-5-template-engine` off `main`, then build per the §6 process.

## 6. THE PROCESS (manual)

**Per slice** (each chunk where you'd normally stop): (1) run the ACTUAL `audit-lite` **skill** on
the slice — NEVER a prose self-review — (2) fix EVERY finding (Blocker→Nit), (3) re-run
`audit-lite`, (4) fix, (5) push, (6) straight to the next slice, no pausing. **At stage end:** push
the final slice → run `audit-team` (Audit Full) on the branch → fix → **re-audit** → … until
**0/0/0/0/0** or a genuinely human-required blocker → **merge + tag** → only THEN a full report.
For a UI slice, `audit-lite` MUST include a real RENDERED browser visual check (desktop + mobile),
not a static token comparison. Branch per stage; the pre-push hook gates every push. **I (Claude)
run the re-audits AND the merge+tag MYSELF** — Scott's Codex audits are his discretionary
spot-checks, NOT a gate I hand back to him.

## 7. Behavioral lessons — load-bearing, do NOT repeat

- **RUN THE ACTUAL audit tool (the skill), every slice — never a prose self-review** labeled
  "audit-lite." My self-review is exactly what the gate exists to override (it's been wrong before).
- **FULL suite + PUSH before claiming green.** An independent Codex audit caught a Critical
  live-test regression I missed by filtering `-m "not live"` and not pushing (2026-06-01).
- **State the gate by environment.** Don't assert a blanket "ci.sh green" — the supported gate is
  native Windows (ruff + full pytest via the hook; npm vitest/build on Windows). `ci.sh` under
  WSL/Linux fails on a Windows-installed `node_modules` (missing the Linux Rolldown binding), which
  is an environment mismatch, not a defect. Codex caught me reporting an unqualified green (2026-06-01).
- **Never say "continuing" then stop** (idle reads as dead); **never assert a fact — a path, "it's
  pushed/merged," a count — without running the one-line check first.** Scott called both out hard
  (2026-06-01). See `~/.claude/.../feedback_no_fake_progress_no_unverified_facts.md`.
- **One truth per doc.** A handoff/roadmap that says "done" in one place and "still ahead / fix all
  N" in another is a process miss — fix or archive the obsolete narrative so there is a single
  current state. Scott caught HANDOFF + ROADMAP self-contradicting after the Stage-4 merge (2026-06-01).
- The handoff/spec is the source of truth — don't rebuild from a vacuum.

## 8. Audit reports + bookkeeping

- **Stage 4 gate audits are committed IN the repo** under `docs/audits/stage-4/` (per-slice
  `audit-lite-*`, the `audit-team-…` package + `REMEDIATION.md`, and the `…-reaudit/` closure) — they
  travel with and verify against the code.
- Stage 3 gate audits live OUTSIDE version control under `C:\Users\scott\dev\`:
  `kimcad-audit-stage3-gate-2026-06-01` (r1, found the Blocker, full package),
  `…-gate-r2-2026-06-01` (deep-dives only), `…-gate-r3-2026-06-01` (convergence **0/0/0/0/0**,
  deep-dives + `_fullsuite.log`). First self audit: `kimcad-audit-stage3-2026-05-31`.
- The independent **Codex** audit (caught the Critical) is marked stale at
  `C:\Users\scott\dev\kimcad-STALE-codex-audit-2026-06-01-SUPERSEDED` — a sibling of the repo,
  **outside** the working tree.
- **TODO (Scott to direct):** commit the live Stage-3 gate-audit packages INTO the repo (e.g.
  `docs/audits/stage-3/`) so they travel with + verify against the code, and write the missing
  **r2/r3 exec + punchlist**. Artifacts outside VC can't prove when/how they were generated.

## 9. Environment / pins

- **Model:** `gemma4:e4b` via local Ollama (`localhost:11434`, OpenAI-compatible). ~10 min/prompt on
  the 32 GB / **AMD 780M iGPU, CPU-only** box — stable (the live bake-off measured 595.7 s mean). **NOT `gemma3:12b`** (OOM). Local-first;
  cloud opt-in via `config/local.yaml`. *(Stage 6 evaluated the spec's `Qwen2.5-Coder 1.5B` candidate
  via the live bake-off and REJECTED it — 0/10, it can't produce a design plan — so `gemma4:e4b` stays
  the default. A `local_qwen` backend remains defined and selectable via `--backend`. Spec reference
  HW is a Beelink 890M; our box is the 780M.)*
- **OrcaSlicer v2.4.0-alpha** pinned (checksum-verified, gitignored `tools/`); `scripts/fetch_tools.py`
  fetches OpenSCAD + OrcaSlicer. `manifold3d>=3.0` (default; import optional at runtime).
- **Frontend toolchain (build-time only):** React 18 + TypeScript + **Vite 8** (Rolldown bundler).
  `node_modules` is Windows-installed (`@rolldown/binding-win32-x64-msvc`); rebuild on Windows with
  `npm --prefix frontend ci && npm --prefix frontend run build`. Node never ships at runtime.

## 10. Context

KimCad is a **SOLO build** (no Antigravity/Codex/bridge/pipeline drives the build — that machinery
is for Scott's other engagements). It's a **head-to-head test vs a competitor AI** building the same
v3.0 spec; Scott judges which is better. **UX is priority #1** (Scott: 10 yrs at Apple). See
`docs/design/` (the §5 design), `ARCHITECTURE.md` (module map), `ROADMAP.md`, `CHANGELOG.md`.
