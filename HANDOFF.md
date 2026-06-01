# KimCad — Handoff (2026-06-01, end of session)

## ⛔ READ FIRST

- **Stage 4 is DONE, merged to `main`, and tagged `stage-4`.** Next is **Stage 5 (deterministic
  template engine + live sliders — the critical path)**.
- **Source of truth = this doc + the in-repo v3.0 spec + the design handoff** (both under
  `docs/design/`). Do NOT rebuild from memory — I have lost context across sessions before.
- **The agent-pipeline skill is DEAD for this project.** Scott killed it (it can't run from the
  wrong cwd / an uninitialized repo). This project runs the **manual process** in §6. Do NOT
  re-invoke `agent-pipeline-claude:run`.

---

## ✅ Stage 4 — DONE (merged + tagged `stage-4`)

Branch **`stage-4-react-spa-shell`** (off `main` @ `efd2b72`). The pre-Stage-4 cleanup already
landed on `main` (ROADMAP rewrite to the 9-stage v3.0 plan; HANDOFF branch-name fix; stale audit
dir removed; audit-lite 0/0/0/0/0; pushed). The React SPA is built in **slices** — each run through
the real `audit-lite` **skill** to 0/0/0/0/0, then full `ruff` + `pytest`, then pushed. Slice audit
reports are committed under `docs/audits/stage-4/`.

**ALL 5 SLICES DONE + PUSHED**, each through the real `audit-lite` skill to 0/0/0/0/0 with rendered
desktop+mobile visual checks (slice reports under `docs/audits/stage-4/`): **1** build seam (React 18 +
TS + Vite 8 → committed `src/kimcad/web/`, served at `/`+`/assets/`); **2** Workshop design system +
self-hosted latin fonts + topbar + landing; **3** 3-col workspace + vanilla Three.js `KCViewport` loading
the REAL `*.oriented.stl` via `STLLoader`; **4** wired flow (prompt→`/api/design`→conversation + plan +
printability report, all 4 statuses) + field-contract tests reinstated + **vitest** stood up (wired into
`scripts/ci.sh`); **5** printer/material selectors + gate-aware slice (`/api/slice/<id>`) + G-code/model
download + read-only connector status. Branch head was **`c65a42d`**. CI gate = ruff + full pytest + vitest.

**✅ STAGE-4 GATE: PASSED — 0/0/0/0/0, merged + tagged `stage-4`.** The 5-role `audit-team` (rendered +
runtime) ran 2026-06-01; package at **`docs/audits/stage-4/audit-team-stage-4-2026-06-01/`** (`00-executive-
audit.md` + `REMEDIATION.md`; the re-audit + closure are in the `…-reaudit/` sibling). The original roll-up
was 0/0/6/19/9; **all 34 findings + the 3 re-audit findings (UX-R01 harness-artifact, NEW-T01, UX-R02) are
resolved with proof** — see REMEDIATION.md + 00-reaudit-closure.md. (History below is the as-found record.)
The original roll-up: **0 Blocker · 0 Critical · 6 Major · 19 Minor · 9 Nit (34).** No Blockers/Criticals — every safety invariant verified clean (gate-fail-can't-slice in 3
layers + tested; no traversal bypass; no XSS; no credential leak; build byte-reproducible; runtime green
end-to-end with a real OrcaSlicer slice). **NEXT: fix ALL 34 (Major→Nit) per the 00-executive punch list →
re-audit → 0/0/0/0/0 → full ruff+pytest+vitest → push → MERGE + TAG `stage-4` MYSELF → only THEN report.**
The 6 Majors: **TEST-001** the field-contract test is a substring spell-checker (mutation-proven — deleting
the printability panel left it green except `headline`; tighten to require `.field`/quoted shapes, strip
comments); **UX-003** primary-button text fails WCAG-AA contrast (white on `#c8623a` = 3.99:1 — darken the
text-bearing fill); **UX-001** viewport lacks the design's dimension pills + bbox + drag hint; **DOC-401**
README/ARCHITECTURE overclaim a browser "send to printer" that doesn't exist — **DESCOPE the doc** (send is
Stage 10), don't build it; **DOC-402** no CHANGELOG Stage-4 entry (+ stale vanilla-UI lines); **ENG-401**
CI should assert committed build == fresh build. **All now FIXED — merged + tagged `stage-4` at 0/0/0/0/0.**

**FIX RECORD — ALL 34 fixed + the 3 re-audit findings resolved, merged + tagged** (the per-batch detail
below is the as-fixed history; authoritative resolution is in `REMEDIATION.md` + `00-reaudit-closure.md`):
batch 1 (`2603566`) = **TEST-001** (the
spell-checker contract test — now strips comments + requires `.field`/quoted literals, proven to bite),
**DOC-401** (descoped the browser-"send" overclaim in README + ARCHITECTURE), **DOC-402** (CHANGELOG
Stage-4 entry), DOC-403/404 (frontend/README), DOC-406 (App comment). Batch 2 (`d39a9ee`) = **ENG-401**
(ci.sh now asserts committed SPA build == fresh build), ENG-408 (frontend release gate), TEST-004 (code-
split now fingerprints three.js IN the chunk / ABSENT from the entry), TEST-003 (vitest branch cases, 14).
**All 4 doc/test/CI Majors done.** **REMAINING (24): 2 Majors — UX-003** (primary-button text contrast
< WCAG-AA: white on `#c8623a` = 3.99:1; darken the text-bearing fill) **+ UX-001** (viewport lacks the
design's dimension pills + bbox + drag hint) — plus the UX Minor/Nit batch (UX-002 wireframe, UX-004
touch-targets, UX-005 mobile hero stack, UX-006 inert gear, UX-007 reduced-motion, UX-008 badge copy,
UX-009 dynamic aria-label, UX-010/011/012) which need a rebuild + a fresh RENDERED visual recheck; the
webapp.py polish (ENG-402 lock the reads, ENG-405 doc the fallback, QA-001 HEAD→200, QA-002 cache headers,
QA-003 orphan-dir cleanup, QA-004 413 keep-alive) which need full-pytest re-runs; DOC-405, TEST-002
(component-render tests or a justified deferral), TEST-005/006, ENG-403/404/406/407 (404 + 407 = verified
no-action). **Then re-audit → 0/0/0/0/0 → merge + tag.** Each finding's detail is in the per-role deep-dives.
(This was a context-forced stop after completing all 5 slices + the gate + 10/34 fixes — not a chosen checkpoint.)

**Carried watch items:** W1 optional shared `resolve()`-containment hardening for `/assets/` + `/vendor/`;
W2 reinstate field-contract tests (Slice 4/5); W3 DONE (prebuild clean); W4 pixel visual review at the
gate; W5 wire the inert landing/topbar chrome before merge; W6 add vitest for component-level JS tests.

**Backend API contract (the unchanged seam the SPA wires to):** `POST /api/design` {prompt} →
{status, clarification?, plan{object_type,summary,target_bbox_mm}, report{gate_status,headline,dims,
findings,...}, error?, has_mesh, mesh_url?}; `GET /api/mesh/<id>` (STL/3MF); `POST /api/slice/<id>`
{printer,material} → {sliced,reason?,estimate,gcode_url?}; `GET /api/gcode/<id>`; `GET /api/options`;
`GET /api/connectors`; `GET /api/connector-status/<name>`; `POST /api/send/<id>` {connector}. The
server reads `web/index.html` at startup and serves `/`, `/assets/<f>`, `/vendor/<f>`, plus the API.

---

## 1. Where the code is

- **Repo:** `github.com/scottconverse/KimCadClaude` (private). **GitHub is the only remote.**
- **`main`:** tags **`stage-0` / `stage-1` / `stage-2` / `stage-3`** — all done, audited to
  **0/0/0/0/0** with `audit-team`, merged + tagged. **Stage 3 tag @ `96aba02`.** `main` is in
  sync with `origin/main`.
- Branch **`stage-3-printer-coverage`** is merged to `main` (not deleted).
- **Tests: 400 passing (incl. 4 live OrcaSlicer slices), ruff clean.** Pre-push hook
  (`.githooks/pre-push` → `scripts/ci.sh` = ruff + the FULL pytest incl. live) gates every push;
  enable per clone with `git config core.hooksPath .githooks`. Fast inner loop:
  `pytest -m "not live"`. **LESSON (load-bearing): never claim "green" off `-m "not live"` + a
  local commit — run the FULL suite AND PUSH so the hook gates the live tests.**
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

## 4. The stage plan (9 stages to the v3.0 Windows beta; Stage 3 done)

3 ✅ printer coverage · **4 = React SPA shell + viewport** · 5 = deterministic template engine +
live sliders · 6 = model swap (Qwen default) + tiered fallback · 7 = Smart Mesh + PrintProof3D +
report · 8 = CadQuery parallel backend · 9 = image on-ramp (opt-in) · 10 = direct-print UI + Bambu
+ first-run wizard · 11 = Windows installer + beta gate. (Final-level breadth + real-hardware =
post-beta.) **KEY INSIGHT:** the instant-slider UX (re-render <1s, no LLM) is impossible on the
current **LLM-writes-OpenSCAD** engine — there is **no `templates/` module**; the deterministic
template engine (Stage 5) is the critical path, and UX-first + architecture-first converge there.

## 5. NEXT = Stage 4 — React SPA shell + viewport

- **Stack APPROVED by Scott: React + TypeScript + Vite SPA**, compiled to static files **served by
  the existing local Python server** (Node/Vite are build-time only; they never ship). Keep the
  **vanilla Three.js** viewport — port `KCViewport` from `docs/design/prototype/jsx/preview.jsx`
  behind a thin React wrapper (not r3f). Build the Workshop design system from `docs/design/`. The
  built SPA is byte-identical across Win/Mac/Linux → mac/Linux are a backend-packaging exercise,
  not a UI rewrite. Windows beta shell = **WebView2** later (controlled render engine);
  localhost-browser is the zero-dep fallback; Tauri later for one cross-OS shell.
- Wire the existing text→plan→gate→slice→download flow through the new UI (read-only first; real
  sliders need the template engine = Stage 5).
- First action: branch `stage-4-react-spa-shell` off `main`, then build per the §6 process.

## 6. THE PROCESS (manual)

**Per slice** (each chunk where you'd normally stop): (1) run the ACTUAL `audit-lite` **skill** on
the slice — NEVER a prose self-review — (2) fix EVERY finding (Blocker→Nit), (3) re-run
`audit-lite`, (4) fix, (5) push, (6) straight to the next slice, no pausing. **At stage end:** push
the final slice → run `audit-team` (Audit Full) on the branch → fix → **re-audit** → … until
**0/0/0/0/0** or a genuinely human-required blocker → **merge + tag** → only THEN a full report.
Branch per stage; the pre-push hook gates every push. **I (Claude) run the re-audits AND the
merge+tag MYSELF** — Scott's Codex audits are his discretionary spot-checks, NOT a gate I hand back
to him.

## 7. Behavioral lessons — load-bearing, do NOT repeat

- **RUN THE ACTUAL audit tool (the skill), every slice — never a prose self-review** labeled
  "audit-lite." My self-review is exactly what the gate exists to override (it's been wrong before).
- **FULL suite + PUSH before claiming green.** An independent Codex audit caught a Critical
  live-test regression I missed by filtering `-m "not live"` and not pushing (2026-06-01).
- **Never say "continuing" then stop** (idle reads as dead); **never assert a fact — a path, "it's
  pushed/merged," a count — without running the one-line check first.** Scott called both out hard
  (2026-06-01). See `~/.claude/.../feedback_no_fake_progress_no_unverified_facts.md`.
- The handoff/spec is the source of truth — don't rebuild from a vacuum.

## 8. Audit reports + bookkeeping TODO

- Stage 3 gate audits live OUTSIDE version control under `C:\Users\scott\dev\`:
  `kimcad-audit-stage3-gate-2026-06-01` (r1, found the Blocker, full package),
  `…-gate-r2-2026-06-01` (deep-dives only), `…-gate-r3-2026-06-01` (convergence **0/0/0/0/0**,
  deep-dives + `_fullsuite.log`). First self audit: `kimcad-audit-stage3-2026-05-31`.
- The independent **Codex** audit (caught the Critical) is marked stale at
  `C:\Users\scott\dev\kimcad-STALE-codex-audit-2026-06-01-SUPERSEDED` — a sibling of the repo,
  **outside** the working tree (it was moved out of `kimcad/` during the Stage-4 cleanup so the
  tree stays clean; the old in-repo `_STALE-...` path no longer exists).
- **TODO (Scott to direct):** commit the live gate-audit packages INTO the repo (e.g.
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

## 10. Context

KimCad is a **SOLO build** (no Antigravity/Codex/bridge/pipeline drives the build — that machinery
is for Scott's other engagements). It's a **head-to-head test vs a competitor AI** building the same
v3.0 spec; Scott judges which is better. **UX is priority #1** (Scott: 10 yrs at Apple). See
`docs/design/` (the §5 design), `ARCHITECTURE.md` (module map), `ROADMAP.md`, `CHANGELOG.md`.
