# Audit Lite — Stage 8, Slice 5 (CadQuery backend docs + deterministic engine bench)
**Date:** 2026-06-06
**Scope:** The new CadQuery docs (`docs/cadquery-backend.md`, `docs/benchmarks/stage-8-cadquery-backend.md`), the deterministic engine bench (`src/kimcad/cadquery_bench.py` + `tests/test_cadquery_bench.py`), and the Stage-8 additions to `README.md` / `ROADMAP.md` / `CHANGELOG.md` / `ARCHITECTURE.md` — verified against the actual source (`cadquery_runner.py`, `cadquery_worker.py`, `config.py`, `config/default.yaml`, `pipeline.py`, `webapp.py`, `prompts/system_cadquery.md`).
**Reviewer:** Claude (audit-lite) — independent Technical-Writer + Test-Engineer pass.

## TL;DR
Ship-with-caveats. The security model, config knobs, STEP behavior, and the bench are all accurately documented and the code genuinely backs them — the honest "OS confinement NOT implemented / `__globals__` closed by the sanitizer, not the worker" framing is exactly right, and the bench really exercises the real worker (live test ran, 5/5 at exact envelopes). The blocking issue is a **status overstatement**: ROADMAP claims Stage 8 was "gated, merged, tagged `stage-8`" and ROADMAP/CHANGELOG claim "5 slices each `audit-lite` 0/0/0/0/0" — but there is no `stage-8` tag, `origin/main` has no CadQuery code, the work is uncommitted, and Slice 5's audit (this one) didn't exist when those lines were written. Fix the two status claims and it ships.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 2
- Minor: 1
- Nit: 1

## Findings

### SLICE5-001 Major: ROADMAP claims Stage 8 was "merged, tagged `stage-8`" — it was not
**Dimension:** Docs (drift vs. reality)
**Evidence:** `ROADMAP.md:264` — the Stage-8 exit line reads: *"**Exit (met):** an optional, real CadQuery backend with STEP/BREP export, switchable in config, that lifts the pass rate as a fallback — gated, merged, tagged `stage-8`."* Verified against git: `git tag -l` lists only `stage-8.5` (no `stage-8`); `git ls-tree origin/main src/kimcad/` shows **no** `cadquery_*` files (CadQuery does not exist on `main`); the working tree is uncommitted on branch `stage-8-cadquery` (`git status`: 4 modified docs + 4 untracked Slice-5 files). The same section's header at `ROADMAP.md:239` correctly says "✅ DONE (on branch `stage-8-cadquery`)", so the file contradicts itself within one section.
**Why it matters:** "merged + tagged" is the project's load-bearing definition of a stage being truly closed (per the Stage-8.5 exit, which *was* merged+tagged). Stating it for Stage 8 when no tag exists and `main` has none of the code is a factual misstatement of release state — exactly the "doc says it's done when it isn't" trust-killer. A reader (or a future agent resuming) would believe the branch is already integrated.
**Fix path:** Change `:264` to state the real status — "**Exit:** … switchable in config, that lifts the pass rate as a fallback. **Pending merge + tag** (`stage-8`) after the Slice-5 gate; currently on branch `stage-8-cadquery`." Keep it consistent with the accurate `:239` header. Do not write "tagged" until `git tag stage-8` actually exists on a merged `main`.

### SLICE5-002 Major: "5 slices, each `audit-lite` 0/0/0/0/0" is stated as fact, but Slice 5's audit did not exist when written
**Dimension:** Docs (unverifiable claim stated as fact)
**Evidence:** `CHANGELOG.md:34` — "Built in 5 slices, each through the real `audit-lite` (independent agent) to **0/0/0/0/0** (`docs/audits/stage-8/`)"; `ROADMAP.md:245` — "**Built in 5 slices, each through the real `audit-lite` … to 0/0/0/0/0**". The audit directory at the time of writing held **slices 1–4 only**: `audit-lite-slice-1-2026-06-06.md`, `…-slice-1-reaudit-…`, `-slice-2-`, `-slice-3-`, `-slice-3-reaudit-`, `-slice-4-` — no `slice-5`. Slice 5's audit is *this document*, produced now. So at write time the "all 5 = 0/0/0/0/0" claim covered an audit that hadn't been run, and it can only become true if this Slice-5 audit also lands at 0/0/0/0/0 — which it does not (this pass found 2 Major).
**Why it matters:** It's a self-referential / premature claim — the changelog asserts a clean-audit outcome for work that includes the very doc making the claim. Even setting the circularity aside, "each … to 0/0/0/0/0" is now falsified by this audit's two Major findings against Slice 5 itself.
**Fix path:** Either (a) scope the claim honestly — "Slices 1–4 each `audit-lite` 0/0/0/0/0; Slice 5 (docs+bench) audited and remediated before the stage gate" — or (b) hold the "all 5 = 0/0/0/0/0" line until after Slice 5's findings are fixed and a clean re-audit confirms it. Don't bake an outcome into the doc that the audit hasn't yet produced.

### SLICE5-003 Minor: README/CHANGELOG/ARCHITECTURE inherit the unproven "lifts the pass rate" framing without the hedge the bench doc carries
**Dimension:** Docs (honesty / consistency)
**Evidence:** `README.md:11-13` ("a fallback that lifts the pass rate"), `README.md:138` ("a pass-rate boost"), `CHANGELOG.md:30-32` ("the union lifts the done-gate"), `ARCHITECTURE.md` pipeline row ("the union lifts the done-gate"). The benchmark doc itself is scrupulously honest about this: `docs/benchmarks/stage-8-cadquery-backend.md:57-59` explicitly notes the union lift "varies with the model and the prompt set and is **not pinned to a fixed number**" and must be re-run live. The structural argument that the union *can only raise, never lower* the pass count is sound and code-backed (`pipeline.py:863-871` runs CadQuery only on a primary gate-fail; `_better_result` at `:941-958` ties-favor-primary), so "can lift" is defensible — but the top-level docs state it as an achieved property without the "not yet measured on the current model" caveat the bench doc is careful to give.
**Why it matters:** Low — the claim is logically defensible and the authoritative bench doc hedges correctly. But the marketing-facing surfaces (README intro, CHANGELOG headline) read as if a measured lift exists. The Stage-6 bake-off lesson (cited in the bench doc) is precisely "don't trust a stale/assumed figure."
**Fix path:** Soften the top-level phrasing to match the bench doc's honesty — e.g. "a fallback **designed to** lift the pass rate (it can only add passes, never remove them; the per-model lift is measured live — see the bench doc)." One clause; keeps the structural guarantee, drops the implied measurement.

### SLICE5-004 Nit: ARCHITECTURE says an OpenSCAD part has "neither" a `step_url` nor a `backend` — but every report carries `backend`
**Dimension:** Docs (precision)
**Evidence:** `ARCHITECTURE.md:153-155` — "A **CadQuery-built** part (Stage 8) also exposes `GET /api/step/<id>` … (the design response carries a `step_url` and the report a `backend`); **an OpenSCAD part has neither**." But `pipeline.py:213` defines `backend: str = "openscad"` as a default on **every** `PrintReport` — an OpenSCAD part's report does carry `backend` (value `"openscad"`). Only `step_url` / `step_path` is genuinely absent for OpenSCAD (`pipeline.py:217`, `webapp.py:1498-1499` adds `step_url` only when `step_ok`).
**Why it matters:** Trivial — the intended meaning (these fields are what *distinguish* a CadQuery part) is clear. But read literally, "has neither … a `backend`" is wrong.
**Fix path:** Reword to "an OpenSCAD part has no `step_url`, and its `backend` reads `openscad`." Or drop `backend` from the "neither" clause.

## What's working
- **The security model is documented accurately and honestly — the highest-risk dimension is clean.** Every claim in `docs/cadquery-backend.md:60-88` and the `cadquery_worker.py:23-52` docstring matches the code: the `ast` block-list (`_ALLOWED_IMPORT_ROOTS`, `_BANNED_NAMES`, `_BANNED_ATTRS` at `cadquery_runner.py:52-89`) covers imports, OS/exec/file names, frame/`__globals__`/generator introspection attrs, **and** `str.format`/`format_map`; the dunder check fires on Name (`:122`), Attribute (`:127`), string-subscript keys (`:131-136`), and `global`/`nonlocal` name strings (`:137-141`). The worker's restricted builtins (`_safe_builtins` at `:97-112`) genuinely withhold `open`/`eval`/`exec`/`compile`/`input`/`getattr` and inject a facade-only `__import__`; the geometry-only facade (`_build_facade` at `:66-78`) strips every submodule. Result-to-dedicated-file-not-stdout (`_emit` at `:193-204`, `_read_worker_result` at `:292-304`), the timeout, and the output-size guard (`render_cadquery:196-226`) are all real.
- **The honest-limits statement is exactly right and rare to see done well.** Both docs state plainly that the `__globals__`→real-`__builtins__` escape class is closed by the **static sanitizer (layer 1), not the worker (layer 2)**, and that OS-level process confinement is **NOT yet implemented** (`cadquery-backend.md:83-88`, `cadquery_worker.py:42-52`). The code confirms it: a facade function still carries real `__globals__`, and only the dunder/introspection block stops the pivot. No security property is overstated.
- **The config knobs match the code and the shipped default to the letter.** `cadquery-backend.md:48-55` (`binaries.cadquery_python` null/false/""/path; `limits.cadquery_timeout_s` default 120) matches `config.py:150-185` (`cadquery_interpreter()` force-off on `False`/`""`, authoritative path with `include_defaults=False`, auto-discover otherwise; `cadquery_timeout_s()` default 120) and `config/default.yaml:18-25,197`.
- **The bench really exercises the real worker, and the 5 declared bboxes are correct.** `pytest tests/test_cadquery_bench.py -v` ran the live case (not skipped — a cadquery interpreter is present), 2 passed in ~21s. Direct run prints `5/5 cases passed` with measured bboxes hitting the declared envelopes **exactly**: box 40×30×20, box_with_hole 40×40×20, cylinder 24×24×30 (correct read of `cylinder(height=30, radius=12)`), rounded_plate 50×40×6, l_bracket 40×20×40. `run_cadquery_bench` calls `render_cadquery` → the actual subprocess worker (`cadquery_bench.py:110-117`), then `validate_mesh` for watertight + bbox. `ruff check` clean.
- **The tolerance design is sound, not hand-wavy.** 0.5 mm + sorted-dims compare (`cadquery_bench.py:32,86-91`): loose enough that the filleted/curved cases (which could tessellation-drift) still passed with zero drift, yet tight enough to catch a real size error (a 24-vs-30 axis confusion is 6 mm). Sorted compare correctly tolerates a valid axis permutation. The no-interpreter shape test (`test_cadquery_bench.py:13-19`) guards against the bench being silently emptied.
- **The STEP claims are accurate, including the subtle reopen case.** `GET /api/step/<id>` (`webapp.py:900-902,945-961`), `step_url` set only when a STEP exists (`:1498-1499`), as-designed/orientation-only-on-mesh (`pipeline.py:214-216`). The doc's parenthetical — "a saved/reopened design persists only the mesh; its STEP is available on the fresh design, or after a re-render" — is *correct and non-obvious*: `_design_snapshot` (`:264-265`) is called at `webapp.py:1490` **before** `step_url` is added at `:1499`, so the saved payload never carries a STEP link; reopen (`:1599-1665`) copies only the mesh and never re-registers a STEP.
- **The script contract matches the prompt.** `cadquery-backend.md:90-98` (assign `result`, pre-imported `cq`, only `math`, no I/O, hoist `# mm` dims, one watertight solid, match bbox) matches `prompts/system_cadquery.md:7-42` rule-for-rule; the bench's `l_bracket` case is the exact union-of-two-boxes shape the prompt teaches (`system_cadquery.md:62-72`).
- **The union "can only raise" claim is code-backed.** `pipeline.py:851-871` runs CadQuery only when the OpenSCAD primary fails the gate; `_backend_succeeded` (`:927-939`) and `_better_result` (`:941-958`, ties favor primary) guarantee the OpenSCAD-primary result is kept unless CadQuery strictly beats it — exactly as `stage-8-cadquery-backend.md:52-55` describes.
- **No stale "Next = Stage 8 / CadQuery is next" leftovers in live docs.** ROADMAP "Next = Stage 9", README "Next up: … Stage 9", and the baseline header (still correctly "as of Stage 8.5 — DONE, merged, tagged") are consistent. Remaining "Stage 8 (CadQuery)" hits are all accurate (new section headers) or in historical audit/plan files.

## Watch items
- The Slice-1 sandbox-escape story (`cq.exporters.os.system(...)`) is retold in CHANGELOG/ROADMAP. It's accurate and well-told — just make sure the regression test for that exact pivot lives in the Slice-1/3 test files (out of this slice's scope, but it's the thing that must never silently regress; the bench does **not** cover it — it's a positive-geometry bench, not an escape-attempt suite).
- When Stage 8 is actually merged + tagged, grep all four top-level docs again for "branch `stage-8-cadquery`" and flip them to the tagged phrasing in one pass (the same insert-a-stage doc-sync hazard that produced the Stage-8.5 DOC-001).

## Escalation recommendation
**No escalation needed.** Two Major findings, both narrow documentation status-overstatements with one-line fixes, no architectural or security root cause — the code is sound and the security docs are notably honest. This is squarely in audit-lite territory; a full `audit-team` would be overkill. Fix SLICE5-001 and SLICE5-002 (the false "merged/tagged" and the premature "all-5 clean" claims) before the stage gate, address SLICE5-003/004 opportunistically, and the slice ships.

---

## Remediation (maintainer, 2026-06-06) — 0/0/0/0/0

- **SLICE5-001 (Major) — FIXED.** Every doc no longer claims Stage 8 is "DONE / tagged
  `stage-8` / merged." ROADMAP header, exit line, and baseline; CHANGELOG entry; README status
  line; ARCHITECTURE all now state the stage is **built + per-slice audited, with the stage gate
  → merge → tag `stage-8` still pending** (the work is on branch `stage-8-cadquery`, not `main`).
  A `grep` confirms no residual "tagged/merged/DONE stage-8" overclaim remains.
- **SLICE5-002 (Major) — FIXED.** The "5 slices each 0/0/0/0/0" wording is replaced with "each
  through `audit-lite` with every finding remediated" (no self-referential absolute claim).
- **SLICE5-003 (Minor) — FIXED.** README/CHANGELOG/ARCHITECTURE now state the structural
  guarantee ("the fallback fires only on an OpenSCAD failure, so it can only raise the pass rate,
  never lower it") and explicitly defer the magnitude to a live measurement — no implied measured
  number.
- **SLICE5-004 (Nit) — FIXED.** The ARCHITECTURE `/api/step` line no longer says an OpenSCAD part
  has "neither" — the report always names the `backend`; only `step_url` is absent.

Re-verified: ruff clean; `tests/test_cadquery_bench.py` 2 passed (live bench 5/5); docs grep clean.
