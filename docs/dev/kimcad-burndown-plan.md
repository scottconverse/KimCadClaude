# KimCad post-beta issue burndown (KC-1 … KC-13 + Codex harvest)

**Author:** Claude (full dev team) · **Started:** 2026-06-11 · **Branch:** work on `main` per standing authorization, slice-by-slice.

## Context

The `0.9.0b1` beta shipped and the repo is public. Two independent evaluators judged
kimcadclaude the winner of the head-to-head vs `kimcadcodex` ("better product"), and Scott
granted explicit standing permission to **harvest anything useful from the `kimcadcodex` repo
and its local git** (`C:\Users\scott\Desktop\Code\kimcadcodex`). The old never-read rule is
revoked (one-way merge into kimcadclaude; no Codex credit in user-facing copy).

Directive: **file KC-1…KC-13 as GitHub issues, then address every single one until it is no
longer an issue.** Fold in the evaluator-named harvest targets as additional issues.

## Cadence (unchanged)

Per slice → (plan exists) → build → `/audit-lite` → fix → push. Per stage/epic end →
`/walkthrough` + `/audit-team` → fix to 0/0/0/0/0 → push. Gate = `scripts/ci.sh` (ruff, full
pytest incl. live OrcaSlicer/CadQuery, vitest, SPA build-repro, installer staging smoke).
Self-hosted runner on this box. Every background dispatch gets a watchdog/wakeup.

## The issues

### P0 — do first
- **KC-4 — Measure the CadQuery fallback lift on `gemma4:e4b`.** Run `docs/benchmarks/
  stage-8-cadquery-backend.md` §2: the prompt set twice (CadQuery off vs enabled), compare
  gate-PASS counts. **Decides KC-2/KC-3 difficulty.** If lift ≈ 0 → drop the LLM-CadQuery
  fallback generator → KC-3 evaporates, KC-2 collapses to the safe STEP-from-templates path.
  Pin the measured number in the doc (kill the "unmeasured" caveat).
- **KC-1 — Cloud-key ("password") save bug.** Reproduce-first. Store layer
  (`settings_store.py`) is already hardened (ENG-101/102/106, keyring health-probe, vault
  rollback) and the init-race is fixed (`webapp.py:748`). Remaining suspect surface: the webapp
  `/api/settings` save handler and the frontend Settings save-state (does the key field round-
  trip / re-mask / report storage location correctly?). Write a failing test that reproduces,
  then fix.
- **KC-2 — Make CadQuery / STEP export reachable for installed users.** Today STEP only appears
  when a CadQuery interpreter is discoverable, which the installer does not ship. Recommended
  path (gated by KC-4): **STEP from trusted-template CadQuery only** — bundle a minimal CadQuery
  worker that runs ONLY our own template-emitted scripts (no LLM Python), giving installed users
  the editable .STEP download without opening the RCE surface. Alternative paths 2/3 (ship full
  CadQuery + LLM fallback) require KC-3.

### P1
- **KC-3 — CadQuery worker OS-level confinement.** Only needed if KC-4 says the LLM-CadQuery
  fallback earns its keep. Confine the worker (Windows Job Object / restricted token; no net, no
  fs writes outside scratch). Blocks KC-2 paths 2/3.
- **KC-5 — Pinned-binary CVE scanning.** Track CVEs for the pinned OpenSCAD/OrcaSlicer/
  PrintProof3D/Ollama binaries; wire a check into the gate.
- **KC-6 — Real-hardware connector validation.** Kim's run (`docs/beta/first-hardware-
  contact.md`). The one thing that cannot happen on this box. Track + prep, don't block.

### P2
- **KC-7 — ENG-006 build-volume verify.** Finish the half-closed build-volume validation finding.
- **KC-8 — macOS/Linux installers.** Beta is Windows-only; scope the cross-platform packaging.
- **KC-9 — Code signing.** Sign the Windows installer/exe to kill SmartScreen friction.
- **KC-11 — STEP copy dangling fix.** The STEP download affordance copy assumes CadQuery; fix it
  to degrade honestly when STEP is unavailable (ties to KC-2).
- **KC-12 — Hosted-CI smoke for external PRs.** Public repo now takes outside PRs that the self-
  hosted gate won't run; add a minimal hosted lint/unit smoke for fork PRs.

### P3
- **KC-10 — Bambu cloud mode.** LAN-only today; scope cloud-relay send.
- **KC-13 — Pin the 2 Discussions threads.** Manual UI step (GraphQL can't pin).

### Harvest (now authorized) — addresses evaluator-named Claude weaknesses
- **KC-14 — Broaden the template catalog (breadth).** Both evaluators: Claude's catalog is deep
  but narrow (8 families / 36 aliases) vs Codex's ~276. Harvest Codex's expanded-family +
  **honest baseline-tiering** pattern: add more selectable families, each tier-labeled
  ("benchmarked" vs "baseline — verify before real use"), every one still feeding the
  Printability Gate's analytic bbox.
- **KC-15 — Dedicated developer API reference.** Claude has none; Codex ships `api.md`. Write a
  real HTTP API reference for the kimcad web surface.
- **KC-16 — pytest marker discipline.** Claude's env-dependent tests FAIL off-target instead of
  skipping (named weakness). Harvest Codex's marker taxonomy (`real_tool`, `windows_only`,
  `live`, `external_simulator`, `browser_serial`) so a wrong-OS dev gets clean red/green. Keep
  the gate's "no green by skip" assertion on the target box.

## Order of execution

1. File all issues (KC-1…KC-16) with labels + dependency links.
2. **KC-4 first** (background live run) — it gates KC-2/KC-3 scope.
3. **KC-1** in parallel (deterministic; reproduce → fix → test).
4. KC-16 (marker discipline — fast, improves every subsequent gate signal).
5. Then by priority, re-scoping KC-2/KC-3 once KC-4 lands.
6. KC-6/KC-9/KC-10/KC-13 are partly out-of-band (hardware, signing cert, manual UI) — track and
   prep; don't fake completion.

## Progress log

- **2026-06-11.** Filed all 16 issues (#6–#21) with labels + dependency cross-refs.
- **KC-1 (#7) CLOSED** — commit `2c84366`. No data-loss bug reproduced (store, handler, real
  Windows keyring, and frontend all correct; init-race already fixed). Added the missing E2E
  web round-trip test (POST key → masked/persist/no-leak across restart) and a **Cancel** on the
  key "Replace" flow (the one genuine "my key vanished" UX gap) + vitest.
- **KC-16 (#21) CLOSED** — commit `df90b7f`. Marker taxonomy (`windows_only`/`real_tool`/
  `needs_manifold`/`needs_cadquery`) + conftest auto-skip; tagged 23 env tests; CONTRIBUTING
  documents it. Off-target failures (SO_EXCLUSIVEADDRUSE) now skip. 1014 collected; subset −51.
- **KC-4 (#6) CLOSED** — commit `<doc>`. **Realized lift = 0** on gemma4:e4b (all 10 prompts
  LLM-codegen, 4/10 PASS, 0 CadQuery wins). `scripts/measure_cadquery_lift.py`.
  → **KC-3 (#9) is moot** (no LLM-Python worker to confine once removed).
  → **KC-2 (#8) narrows to template-only STEP.**
- 3 commits local, **not yet pushed** (push runs the full ci.sh gate — batch after KC-2 cluster).

## KC-2 implementation design (the CadQuery cluster — next slice)

**Install mechanism DECIDED (Scott, 2026-06-11): Option F — guided manual install.** No bundle,
no runtime pip. Ship a Settings card (what CadQuery is, what it gives, "KimCad is already wired",
the `py -3.13 -m pip install cadquery` steps, a check-again/restart prompt). Auto-discovery
(`find_cadquery_interpreter`) already lights it up on restart. E (bundle for one-click) parked as
a future convenience. The CAPABILITY below (template→STEP) is built regardless of install path.

The user's core ask: "make cadquery work somehow." Post-KC-4 the safe answer:

1. **Remove the LLM-CadQuery fallback** (`provider.generate_cadquery` + the secondary
   `_GeomBackend` in `pipeline.py:881-888` + `_CADQUERY_FIX`). Verify the **experimental toggle
   is LLM-OpenSCAD** (it is — `generate_openscad`), so it's untouched. This removes the
   RCE surface → #9 moot.
2. **Keep + repurpose the trusted CadQuery worker** (`cadquery_runner`/`cadquery_worker`, proven
   by the §1 deterministic bench) to run ONLY our own template-emitted scripts.
3. **Template→STEP:** for a template-matched part, emit a CadQuery script from the SAME analytic
   parameters the template already declares, run it through the bundled trusted worker, attach
   the resulting `.step`. Start with the simplest families (box/plate/cylinder/hole) and widen.
   The existing analytic bbox per family is the contract.
4. **Bundle a minimal CadQuery interpreter** in the installer for that trusted path (or document
   STEP as available when a local CadQuery interpreter is present, if bundling is too heavy —
   decide during impl, favor bundling so installed users actually get STEP).
5. **KC-11 (#15):** make the STEP-download copy honest — show it when a template STEP exists,
   explain its absence otherwise. Folds into this slice.
- Sequence to avoid a STEP regression: build template→STEP FIRST, then delete the LLM fallback,
  in one cohesive slice. TDD each family's STEP envelope against the §1 bench harness.

## Harvest campaign (approved by Scott 2026-06-11 — ALL tiers)

Scott approved the full three-tier harvest list + skip list. kimcadcodex is now **PRIVATE**
(deprecating as we migrate). Naming rule: **"KimCad" only** in all docs (no Claude/Codex
qualifiers); repo stays public at KimCadClaude until an eventual move to the empty `kimcad`
repo (later, not now). New issues filed: **#23 UI-v2 epic, #24 FAQ, #25 Playwright e2e,
#26 Marlin+RRF, #27 diff-coverage, #28 README restructure, #29 model guide, #30 definition-of-
done, #31 session token, #32 refine parity, #33 troubleshooting, #34 installer clean-machine,
#35 wizard copy.** Release attestation folded into #14. pip-audit = #10. api.md = #20.
Printer picker story: docs half DONE (committed); picker = #22.

**Execution order:** KC-2/F slice (#8+#15, closes #9) → Tier-1 batch (#14, #10, #24, #20,
#34, #35) → UI-v2 epic (#23, staged slices) → templates (#19) + printer catalog/protocols
(#22, #26) → Playwright e2e (#25) → Tier-3 (#27..#33, #28..#30) trickled into gates.
Skip list honored: no vanilla-JS port, no Tkinter installer, no auto-start, no bambulabs-api
contract tests, no UPX/casadi.

## Progress log 2 (post-harvest-approval execution)

- **KC-2/F slice SHIPPED** — commits `7f86af9` (trusted twins) + `d48cd65` (full slice),
  pushed through the FULL gate green. **#8, #9, #15 closed.** All 7 families have CadQuery
  twins (live-proven watertight at analytic bbox); STEP builds lazily on first download
  (verified live: real worker, 4.1s, valid ISO-10303); LLM-CadQuery fallback fully removed
  (+ regression pin); Settings F-card + honest 3-state Export copy; docs rewritten
  (cadquery-backend.md, README, USER-MANUAL, CHANGELOG).
- **#14 closed** — beta-honest messaging verified across release page/install-guide/FAQ;
  `scripts/prepare_release_assets.py` attestation (SHA256SUMS.txt + release-manifest.json)
  **attached to the live beta release** + body updated. Signing = blocked on Scott's cert.
- **#34 closed** — both clean-machine bugs verified N/A by architecture (config-pathed
  binaries, HTTP Ollama probe, WINDIR `py` launcher); evidence on the issue.
- **#17 closed won't-fix** (Bambu cloud defeats the product's purpose — Scott).
- **Tier-1 commits `6ff7177` + `e2bdcba`** (pushed via gate, then close #10/#20/#24/#35):
  docs/FAQ.md (18 Qs), docs/api.md (full endpoint reference), README/docs-index links,
  binary-advisory gate (scripts/check_binary_advisories.py wired into ci.sh, drift detector
  proven), wizard copy voice pass (verb-object titles + reopen-anytime line).
- **kimcadcodex is PRIVATE.** Printer-library story in README/supported-printers (committed
  earlier as part of #22's doc half).

**UI-v2 SLICE 4 — SHIPPED** (commit `a6b30cc`, pushed through the FULL gate green 2026-06-12:
1024 pytest + 368 vitest + build-repro + live tools; rebased over Scott's PR #36 cost-hygiene
guardrails which landed on origin mid-slice). **DEV HANDOFF to Codex on a new machine prepared:**
`Desktop\Code\kimcad-handoff-codex.md` is the cut-and-paste brief (state, rules, all 13 open
issues in execution order, resume point = slice 5). Original slice-4 notes kept below:
click-to-measure tool. KCViewport.ts: MeasureState (points 0|1|2) + pure `measureBetween`
(translation-invariant) + setMeasureMode/clearMeasure/measureClick (raycast on click-not-drag,
<5px; markers+line in measureGroup; cleared on loadMesh re-shape; MISS = honest feedback not
silence); Viewport.tsx: Measure toggle + readout pill (formatMm/unit-aware) + measuring hint;
styles.css: .kc-measure-* (incl. a fixed typo '#ffb astonishing'→'#ffb38a'); tests:
KCViewport.measure.test.ts (math: distance/deltas/symmetry/translation-invariance) +
Viewport.test.tsx measure describe (mock got setMeasureMode; act imported; miss branch
pinned). **LIVE-PROVEN on the real engine: two raycast picks → "14.1 mm ΔX 13.6 · ΔY 0 ·
ΔZ 3.8"**; console clean. (Debug note: earlier "all raycasts miss" was a WEDGED preview
renderer — frozen rAF/stale camera — not a code bug; preview screenshot tool also degraded
that session, eval-only verification is fine. Eval races: page may already be in workspace —
poll for state, don't assume landing.)
**RESUME STEPS:** (1) full vitest run (expect 369: 368+1 new miss assertion), (2) tsc, (3)
vite build (SPA), (4) CHANGELOG entry (slice 4), (5) commit "UI-v2 slice 4 (#23): click-to-
measure" + push (gate). Then **slice 5**: Smart Mesh polish — relabel low-history confidence
('Track record: building', not 'Low confidence' — the reference audit's finding; our
ReadinessCard already has gauge+confidence+risks), check pill AA contrast in both themes.
Then **slice 6**: print-outcome capture (Came out clean/Had issues/Failed/Skip after a real
send → POST into the history store; check what /api/send + history already support). Epic
then closes #23 → /walkthrough + /audit-team per cadence.

**UI-v2 SLICE 5 - DONE (Codex, new machine, 2026-06-12):** fresh clone provisioned and
`scripts/ci.sh` is green before code (1024 pytest + 368 vitest + live OrcaSlicer + CadQuery
worker + build repro). Scope is the Smart Mesh polish from the handoff: ReadinessCard maps API
`Low` confidence to **"Track record: building"** (never "Low confidence") while preserving the
API contract; the confidence blurb now says the local track record is still building. Added
Vitest coverage for the label and expanded the tone-contrast guard to light + dark theme
tokens. Verified targeted Vitest (60), full Vitest (375), Vite/tsc build, and audit-lite at
0/0/0/0/0 (`audit-lite-ui-v2-slice-5-smart-mesh-2026-06-12.md`). Full `scripts/ci.sh` was rerun
after the slice build and reached 1024 pytest + 375 vitest; the pre-commit build-repro step
correctly stayed red until the rebuilt SPA bundle is committed, so the final green gate is
run after commit.

**UI-v2 SLICE 3 DONE** (commit "UI-v2 slice 3", in/through the gate): the part-library
browser — GET /api/templates (registry-driven; #19 catalog lands here automatically) +
LibraryModal (searchable cards, seed-prompt picks through the normal flow) + landing entry.
Verified live end to end. **Slice 4 next: click-to-point measurement + live X/Y/Z dimension
pills on the viewport** (reference: app.js:989-1006 raycasting + screen-projected pills; our
Viewport already shows dimension labels in the 3D scene — evaluate gap first: ours renders
40/60/80mm labels in-scene (screenshot proof), so slice 4 may reduce to the click-to-measure
tool only). Then slice 5 (Smart Mesh score ring relabel — our gauge exists; adopt 'Track
record: building' for low-history confidence + AA pill fixes) and slice 6 (print-outcome
capture feeding the history store).

**UI-v2 SLICE 2 DONE** (commit "UI-v2 slice 2", in/through the gate): the tabbed Inspector —
Parameters/Quality/Export under an always-visible verdict strip; tab state lifted to
Workspace; smart gate-fail→Quality default; panels stay mounted (drafts survive); mobile CTA
opens Export. vitest 362/362. **Slice 3 next: library browser modal** (searchable template
grid from the registry — pairs with #19's catalog; reference kc-library.jsx: header + search +
category tabs + family cards seeding a design) **+ version-rail polish** (our VersionRail
exists — compare against reference history rail, adopt what's better). Then slices 4-6.

**UI-v2 SLICE 1 DONE** (commit "UI-v2 slice 1", in/through the gate): dark mode by token
inversion + useTheme (light/dark/system) + Settings Display card + the hardcoded-color audit
+ the landing safe-center fix. Verified live both themes; vitest 358/358. Density deferred to
its own pass (calc() retrofit). **Slice 2 next: the three-pane workspace + tabbed Inspector**
(Conversation | viewport | Parameters/Quality/Export) — reference structure in kimcadcodex
src/kimcad/app/static (workspace-grid 360|1fr|392, breakpoints 1380/1099/1000) + the JSX
prototype kc-workspace.jsx. Then: (3) library modal + version rail, (4) click-to-point
measurement + dimension pills, (5) Smart Mesh score ring + confidence relabel ('Track
record: building'), (6) print-outcome capture. Epic ends with /walkthrough + /audit-team.

**Original slice-1 grounding (kept for reference):** UI-v2 epic (#23) — slice 1 GROUNDED: our `frontend/src/styles.css`
`:root` block ALREADY shares the reference design language (same #c8623a terracotta, same
Bricolage/Hanken/JetBrains fonts, same 16/20/11/999 radii, BETTER AA fill/text splits), so
slice 1 is additive: a `:root.kc-theme-dark` override block (adapt the reference dark values
— kimcadcodex `src/kimcad/app/static/styles.css:32-53`: ink #f5efe5, paper #181715, panel
#24211d, copper #ff8a4b, green #75d89c, viewport #0e1116, + their `--control-surface` lesson:
EVERY control fill must be a token or it stays white-on-white in dark) + density multipliers
(`--pad/--gap/--fs`, Compact = 0.82/0.8/0.94) + toggles (Settings + topbar) + localStorage
persistence + a hardcoded-color audit of our 92KB styles.css. Verify with preview walkthrough
both themes. Then slices 2-6 per #23. Then breadth (#19 templates, #22 picker, #26
Marlin/RRF), e2e (#25), Tier-3 (#27..#33). Out-of-band: #11 (Kim), #13 (scope), #18 (Scott's
pin click).

## Definition of done

Every issue either **closed with a verified fix** (gate green, test pinning the behavior) or
**closed as won't-fix/deferred with an explicit, documented reason** (e.g. KC-6 needs Kim's
hardware; KC-9 needs a signing cert Scott controls). No silent drops. Audit to 0/0/0/0/0 at the
epic gate.
