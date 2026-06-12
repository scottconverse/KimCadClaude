# KimCad — Full Dev Handoff (Codex, new machine)

You are taking over as the **full dev team** for KimCad. You have merge/push authority on
`main`. Read this whole brief first. The previous dev's working plan/log (per-slice designs,
decisions, and debugging lessons) is committed at **`docs/dev/kimcad-burndown-plan.md`** —
read it end-to-end before writing code, and keep your own running plan/log the same way: a
living document in `docs/dev/`, updated every slice.

## What the product is

**KimCad** — local-first AI 3D-print design for non-experts. The user types a description
(or uploads a photo/sketch), a **local** LLM (Ollama, gemma family; optional user-keyed cloud
model) plans a part, a deterministic template engine + OpenSCAD render it parametrically,
live sliders re-render in real time, a **Printability Gate** (analytic checks + Smart Mesh /
PrintProof3D readiness scoring with a learning history store) judges it, OrcaSlicer (bundled)
slices it, and the part prints **directly to the printer over LAN** (Bambu LAN, OctoPrint,
Moonraker, PrusaLink). Privacy is a core promise: prompts and images never leave the machine
unless the user explicitly adds a cloud key.

- Repo: `github.com/scottconverse/KimCadClaude` — **PUBLIC, deliberately**: all GitHub
  resources (Actions hosted runners, storage, etc.) are free on public repos, and we use
  them. Internal dev artifacts (like `docs/dev/`) living in the open is accepted for now —
  at release everything moves to the currently-empty `kimcad` repo, and cleanup of internal
  dev history/artifacts happens THEN, not before. Product name in ALL user-facing docs/UI:
  **KimCad** (never "KimCadClaude"/"Claude"/"Codex" qualifiers).
- Shipped: **0.9.0b1 public Windows beta** (WebView2 double-click installer; release live with
  SHA256SUMS.txt + release-manifest.json attestation; unsigned — beta messaging explains why).
- Stack: React/TypeScript SPA in `frontend/` (vite build outputs into `src/kimcad/web/` —
  built assets are COMMITTED and must byte-match the source, CI checks reproducibility);
  Python backend `src/kimcad/` (stdlib http server `webapp.py`, pipeline, template engine,
  design registry, settings store w/ Windows keyring, printer connectors); bundled tools under
  `tools/` fetched by `scripts/fetch_tools.py` (OpenSCAD, OrcaSlicer, PrintProof3D).

## Non-negotiable engineering rules (Scott's standing directives)

1. **Plan before code** (Hard Rule 11): a plan file must exist under `.claude/plans/` before
   any commit. The burndown plan there is the living doc — keep updating it.
2. **The gate**: every push runs `scripts/ci.sh` — ruff, the FULL pytest suite **including
   live OpenSCAD/OrcaSlicer/CadQuery tool tests**, frontend vitest, **byte-exact SPA
   build-reproducibility**, installer staging smoke, pip-audit on `requirements.lock`, and
   `scripts/check_binary_advisories.py` (curated CVE table + pin-drift detector). A local
   pre-push hook runs the same gate. **Green gate or no push. No green-by-skip on the target
   box.**
3. **Audit cadence**: per slice → audit-lite → fix everything → push. Per stage/epic end →
   full UI walkthrough + 5-role audit → remediate to **0/0/0/0/0 at ALL severities**
   (Blocker→Nit, every time; no "cleanup later" lists — Scott's hard rule).
4. **TDD**: failing test first for logic changes. Tests are hermetic: NEVER touch the real
   Windows Credential Manager (use the FakeKeyring pattern) or the real `~/.kimcad`.
   Env-dependent tests use the marker taxonomy (`live`, `real_tool`, `windows_only`,
   `needs_manifold`, `needs_cadquery`) — conftest auto-skips off-target.
5. **Security posture**: no secrets in code/logs; **the LLM-CadQuery fallback was REMOVED
   permanently** (measured lift = 0; removal is regression-pinned — never reintroduce LLM-
   authored Python execution). CadQuery runs ONLY trusted template-emitted scripts
   (`src/kimcad/cadquery_templates.py`, float-coerced values, per-family bbox contract).
6. **Product decisions that are settled — do not reopen**:
   - **LAN-only direct print is permanent.** Bambu *cloud* mode was closed won't-fix (#17):
     "our software gives back to the user direct print." Never add cloud-relay printing.
   - **CadQuery install = Option F**: guided manual install card in Settings (steps +
     check-again). No bundling, no runtime pip.
   - **Honest copy everywhere**: tiered claims ("benchmarked" vs "baseline — verify before
     real use"), honest empty/error states, no overpromising. The printer story leads with
     the full bundled Orca library (~65 brands / 1,447 profiles) with the 3 reference
     printers as the CI-proven tier.
   - `kimcadcodex` (private, deprecated reference repo) was a competing build; harvesting
     from it is authorized and largely COMPLETE — one-way migration, no credit in user-facing
     copy. The empty `kimcad` repo is the release home; the move + cleanup happen at release,
     not now.
7. **Autonomy**: don't ask Scott for anything his standing authorization already covers.
   When blocked, find a legitimate alternate path and keep working. Never end a work session
   without stating what's running, ETA, and the next check-in.

## Current state (as of 2026-06-12, HEAD `a6b30cc` on `main`)

- 0.9.0b1 beta live; post-beta burndown campaign in flight: **30 issues filed, 17 remain
  closed-complete + won't-fix; 13 open** (list below).
- UI v2 epic (#23) is 4/6 slices shipped: dark mode (slice 1), tabbed Inspector (slice 2),
  part-library browser (slice 3), click-to-measure (slice 4, commit `a6b30cc`, live-verified).
- `.github/workflows/cost-hygiene.yml` + `.github/COST_HYGIENE.md` landed via PR #36 (Scott) —
  respect those guardrails in any CI work (relevant to #16).
- All per-slice audits closed at 0/0/0/0/0; CHANGELOG current through slice 4.
- CI: the self-hosted runner `kimcad-windows` lives on the OLD dev box and is being retired
  with it. **Scott's standing CI direction: the repo is public, so GitHub-hosted runners are
  free and unlimited — use them.** Migrate the gate to hosted runners (`windows-latest` for
  the live Windows tool contract — `scripts/ci.sh` already self-provisions venv from
  `requirements.lock`, tools via `scripts/fetch_tools.py`, the `.venv-cq313` CadQuery worker
  venv, and frontend `node_modules`; verify the live OpenSCAD/OrcaSlicer/CadQuery tests run
  on a hosted Windows image, and keep the "no green by skip" assertion). Respect the cost-
  hygiene guardrails Scott added in PR #36 (`.github/COST_HYGIENE.md` +
  `.github/workflows/cost-hygiene.yml`). The local pre-push hook (`scripts/ci.sh`) remains
  the authoritative pre-push gate on your machine regardless — run it green ONCE on a fresh
  clone before any push. Hosted migration largely absorbs #16 (fork-PR smoke): once the gate
  is hosted, fork PRs get a signal for free — close #16 against that work with evidence.
- `gh` CLI must be authenticated as `scottconverse` on this machine.

## THE WORK — every open item, in execution order

### A. Finish the UI v2 epic (#23) — resume point
1. **Slice 5 — Smart Mesh polish**: relabel low-history confidence to **"Track record:
   building"** (never "Low confidence") in the ReadinessCard; verify pill AA contrast in BOTH
   themes; inherit the reference audit's fixes (score ring/confidence/history-comparison line
   — our gauge already exists, close the gaps).
2. **Slice 6 — print-outcome capture**: after a real send, ask **Came out clean / Had issues /
   Failed / Skip** → feed the answer into the existing history/learning store (check what
   `/api/send` + history already support first).
3. **Epic close**: full browser walkthrough + 5-role audit of the whole epic → fix to
   0/0/0/0/0 → close #23. Also decide the deferred **density pass** (Comfortable/Compact
   multipliers were slice-1 scope, deferred to a calc() retrofit) — do it or close it with a
   documented deferral.

### B. Breadth (the product's biggest visible wins)
4. **#19 — Template catalog breadth + honest tiering**: port ~30 bespoke template families
   from the reference repo (38 bespoke existed; 238 labels collapse to 5 baselines), each
   with an analytic bbox feeding the Printability Gate, each tier-labeled ("benchmarked" vs
   "baseline — verify before real use") in UI + docs. The library browser (`GET
   /api/templates`) picks new families up automatically.
5. **#22 — Printer picker catalog**: surface the bundled Orca profile tree (~65 vendors /
   1,447 machines) as picker entries — name, build volume, nozzle, profile names. Every entry
   born-verified by the existing `test_configured_build_volumes_match_the_shipped_orca_profiles`
   pin; curated tier live-slice-proven in the gate; honest "profile present, not slice-proven"
   long tail; update `docs/supported-printers.md` tiers.
6. **#26 — Marlin-serial + RRF/Duet connectors**: port connector + conformance simulator +
   tests per the existing mock-twin pattern (RRF HTTP `/rr_gcode`/`/rr_status`/`/rr_upload` =
   small; Marlin serial M-code = medium, huge Ender-class base). Metal validation folds into #11.

### C. Test & infra hardening
7. **#25 — Playwright e2e suite**: live-server fixture spawning the real server, per-test
   pages, console-error watcher, `browser_serial` marker; journeys: wizard, prompt→design→
   refine, sliders, photo/sketch, gate fail/pass, slice/download, settings, My Designs, error
   recovery. Wire into the gate behind a marker.
8. **#16 — Hosted-CI for everyone**: per the CI direction above, migrate the gate to free
   hosted runners (`windows-latest` for the live-tool gate; `ubuntu-latest` where Windows
   isn't required) — this gives fork PRs their signal and retires the self-hosted dependency
   in one move. Honor `.github/COST_HYGIENE.md`.
9. **#27 — Diff-coverage gate**: changed-lines ≥80% total / ≥70% per-module (when ≥20 lines)
   in `scripts/ci.sh`; document in CONTRIBUTING.

### D. Tier-3 polish
10. **#28 — README front-door restructure**: badge row + single download CTA on top, "What
    gets installed", "Why it's different", Beta Notes, SmartScreen pre-explained inline.
    Restructure, don't rewrite — keep the honesty.
11. **#31 — Session-token guard**: random per-boot token required (constant-time compare) on
    every state-changing request; 403 otherwise; document why full CSRF is out of scope.
12. **#32 — Refine-failure parity**: prove (pinning test) that a model failure during refine
    NEVER destroys the current design — return existing plan + one clarifying question; fix
    if we diverge.

### E. Out-of-band / blocked (track honestly, don't fake)
13. **#11 — Real-hardware connector validation** (Kim's printer; `docs/beta/first-hardware-
    contact.md`). Hardware-blocked; prep is done.
14. **#13 — macOS/Linux installers**: scoping only for now (beta is Windows-only).
15. **#18 — Pin the 2 seeded Discussions threads**: Scott's 30-second manual UI click
    (GraphQL can't pin) — remind him, don't attempt.
16. **Code signing**: blocked until Scott buys a cert; the attestation + beta messaging
    shipped under #14 is the interim answer.
17. **Release move to the empty `kimcad` repo** — happens when the product is finished and
    release-ready, on Scott's word. That move is also the cleanup point for internal dev
    artifacts (`docs/dev/`, competition-era history); don't scrub anything before then.

## Definition of done (campaign)

Every issue closed with a verified fix (gate green + pinning test) or closed won't-fix/
deferred with a documented reason. No silent drops. Epic/stage gates audited to 0/0/0/0/0.

## First actions on this machine

1. Clone the repo; read `docs/dev/kimcad-burndown-plan.md` end-to-end (per-slice logs,
   designs, debugging lessons), then `CHANGELOG.md`, `docs/api.md`, `CONTRIBUTING.md`,
   `scripts/ci.sh`, `.github/COST_HYGIENE.md`.
2. Provision + run `scripts/ci.sh` to green locally (this proves the toolchain) BEFORE any code.
3. Confirm `gh auth status` works as scottconverse.
4. Migrate CI to GitHub-hosted runners (free on this public repo) per the CI direction above.
5. Start with **slice 5** above. Per-slice cadence: plan → TDD → build → audit-lite → fix all
   → push through the gate. Report status with what's running / ETA / next check-in.
