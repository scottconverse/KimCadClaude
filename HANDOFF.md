# KimCad — Handoff (2026-06-02 — Stage 5: Slices 1–5 complete, stage gate passing, pending merge+tag)

## ⛔ READ FIRST

- **🔨 STAGE 5 — ALL FIVE SLICES COMPLETE on branch `stage-5-template-engine`, NOT yet merged/tagged.**
  Slices 1–5 (engine, pipeline tiering, re-render API, live sliders, benchmark+docs) are each through
  the real `audit-lite` skill to 0/0/0/0/0, and the full `audit-team` stage gate has run + been
  remediated to 0/0/0/0/0 (package in `docs/audits/stage-5/audit-team-stage-5-2026-06-02/`). **NEXT =
  the final native Windows gate → merge to `main` → tag `stage-5`.** See the "Stage 5" section below.
- **Stage 4 is DONE — merged to `main` (merge commit `dcbcd1a`) and tagged `stage-4`** (the `stage-4`
  tag was advanced past the merge to the docs-consistency commit — see "Tag provenance" below — so
  the tag and the `main` head are the same commit, `181115e`).
- **Source of truth = this doc + the in-repo v3.0 spec + the design handoff** (both under
  `docs/design/`). Do NOT rebuild from memory — I have lost context across sessions before.
- **The agent-pipeline skill is DEAD for this project.** Scott killed it (it can't run from the
  wrong cwd / an uninitialized repo). This project runs the **manual process** in §6. Do NOT
  re-invoke `agent-pipeline-claude:run`.

---

## 🔨 Stage 5 — Slices 1–5 complete; stage gate passing; pending merge + tag (deterministic template engine + live sliders — the critical path)

**Branch `stage-5-template-engine`, ahead of `main`, NOT merged/tagged.** Stage 5 makes the headline
UX real: drag a parameter slider → re-render in **<1 s with NO model call** (measured 0.13–0.45 s per
family; proof in `docs/benchmarks/stage-5-template-families.md`). On the old LLM-writes-OpenSCAD
engine that was impossible (every change round-tripped the model).

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

**Verified at remediation head:** **`pytest` full suite green incl. live OrcaSlicer**; ruff clean;
**vitest green**; SPA build byte-reproducible; `npm audit` 0. (Run `scripts/ci.sh` / the pre-push hook
for the authoritative count; do NOT hand-copy a number here that can go stale — that was DOC-001.)

**➡️ NEXT = the stage gate's tail:** native Windows gate (ruff + full pytest incl. live + vitest +
`npm run build` reproducibility + `npm audit` 0) → merge to `main` → tag `stage-5` at the final
artifact → flip this section + ROADMAP to DONE → report to Scott. (Tag pushes have been DENIED by the
out-of-context Agent Pipeline hook before — if the `stage-5` tag push is blocked, surface it to Scott
as the one authorization needed.)

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

3 ✅ printer coverage · 4 ✅ React SPA shell + viewport · **5 = deterministic template engine +
live sliders** · 6 = model swap (Qwen default) + tiered fallback · 7 = Smart Mesh + PrintProof3D +
report · 8 = CadQuery parallel backend · 9 = image on-ramp (opt-in) · 10 = direct-print UI + Bambu
+ first-run wizard · 11 = Windows installer + beta gate. (Final-level breadth + real-hardware =
post-beta.) **KEY INSIGHT:** the instant-slider UX (re-render <1s, no LLM) is impossible on the
current **LLM-writes-OpenSCAD** engine — there is **no `templates/` module**; the deterministic
template engine (Stage 5) is the critical path, and UX-first + architecture-first converge there.

## 5. Stage 5 scope — deterministic template engine + live sliders (IN PROGRESS — see the 🔨 section up top for current state + the Slice-4 pickup)

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

- **Model:** `gemma4:e4b` via local Ollama (`localhost:11434`, OpenAI-compatible). ~9 min/prompt on
  the 32 GB / **AMD 780M iGPU, CPU-only** box — stable. **NOT `gemma3:12b`** (OOM). Local-first;
  cloud opt-in via `config/local.yaml`. *(v3.0 spec TARGETS `Qwen2.5-Coder 1.5B` as the new fast
  default + `gemma4:e4b` as the non-China alternative & vision fallback — benchmark on the actual
  box before adopting, per spec §7.5. Spec reference HW is a Beelink 890M; our box is the 780M.)*
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
