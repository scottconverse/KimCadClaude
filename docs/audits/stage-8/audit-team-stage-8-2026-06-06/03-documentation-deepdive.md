# Documentation Deep-Dive — KimCad Stage 8 (CadQuery parallel backend)

**Audit date:** 2026-06-06
**Role:** Technical Writer
**Scope audited:** Stage 8 documentation only — `docs/cadquery-backend.md` (NEW), `docs/benchmarks/stage-8-cadquery-backend.md` (NEW), and the Stage 8 edits to `README.md`, `ROADMAP.md`, `CHANGELOG.md`, `ARCHITECTURE.md`. Verified against `src/kimcad/cadquery_runner.py`, `cadquery_worker.py`, `config.py`, `config/default.yaml`, `webapp.py`, `pipeline.py`, `prompts/system_cadquery.md`, `cadquery_bench.py`, and `git tag` / `git log`.
**Writer mode:** audit-only (no rewrites; flag only)
**Auditor posture:** Balanced

---

## TL;DR

The Stage 8 documentation is unusually accurate and honest — a model of doc-vs-code discipline. Every load-bearing claim I tested (the two-layer security model, the AST block-list specifics, the config knobs, the STEP API surface, the bench parameters) matches the source verbatim. The single most important integrity check passes cleanly: **no doc claims Stage 8 is done / merged / tagged `stage-8`** — there is no `stage-8` git tag, the branch is `stage-8-cadquery`, and every doc consistently states "built + per-slice-audited; gate → merge → tag PENDING." The security narrative is honest in both directions — it explicitly states what the worker layer *cannot* independently do (the `__globals__` class is closed by the sanitizer, not the worker) and that OS-level confinement is **not yet implemented**. The union-lift claim is correctly hedged ("measure it live," with an explicit honesty note) and not pinned to a fabricated number. Findings are confined to a handful of small clarity/precision items — no Blocker, no Critical, one Major (a security-precision nuance that could mildly *under*-credit or be misread), and a few Minor/Nit polish items.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 3 |
| Nit | 3 |

## What's working

- **The status honesty is exactly right, everywhere.** `git tag` shows `stage-0 … stage-7` and `stage-8.5` — **no `stage-8`**. Branch is `stage-8-cadquery`, not on `main`. README.md:25-27 ("**Stage 8 … is built** on branch `stage-8-cadquery` … its stage gate → merge → tag is still pending, so it isn't on `main` yet"), ROADMAP.md:62-66 ("**Stage 8 … is BUILT on branch `stage-8-cadquery`** … is not yet on `main`"), CHANGELOG.md:29-30 ("**BUILT (branch `stage-8-cadquery`; stage gate + merge + tag pending)**"), and ARCHITECTURE module map all agree. The prior "done-and-pending" contradiction bug has no residue here.
- **The security model matches the source line-for-line.** `docs/cadquery-backend.md:60-88` describes (1) the static sanitizer as the *primary* layer and (2) the worker runtime as the *secondary* layer, with an explicit "what the worker layer can **not** independently do." This is a faithful prose mirror of the module docstrings (`cadquery_runner.py:1-25`, `cadquery_worker.py:23-53`) and the actual code: AST block-list (`sanitize_cadquery`, lines 92-146), `_ALLOWED_IMPORT_ROOTS = {"cadquery","math"}` (line 52), the banned-names/attrs sets (lines 59-89), dunder name+attr+**string-subscript-key** checks (lines 122-136), frame/`__globals__` introspection attrs and `str.format` pivots (lines 77-89), restricted builtins + facade `__import__` (`cadquery_worker.py:81-112`), submodule-stripped facade (`_build_facade`, lines 66-78), result-to-file-not-stdout (lines 193-204), timeout + output-size guard (`render_cadquery`, lines 201-226).
- **The "honest division of guarantees" is genuinely honest.** Both the doc (`cadquery-backend.md:83-88`) and both module docstrings state plainly that a facade function still carries its real `__builtins__` in `__globals__`, that this escape class is closed by layer 1 (the sanitizer) and **not** by the worker, and that OS-level process confinement "is **not yet implemented**." This is the rare security doc that neither oversells nor undersells.
- **Config knobs are exact.** `cadquery-backend.md:48-56` and README.md:152 / ROADMAP.md:257-258 / CHANGELOG.md:48-49 all describe `binaries.cadquery_python` as `null`=auto / `false` or `""`=off / `"<path>"`=explicit-no-fallthrough, and `limits.cadquery_timeout_s` default `120`. This matches `config.py:150-185` (`cadquery_interpreter()` + `cadquery_timeout_s()`) and `config/default.yaml:25` (`cadquery_python: null`) and `:197` (`cadquery_timeout_s: 120`) verbatim, including the subtle "`false`/`""` force-off without probing" and "explicit path is authoritative, `include_defaults=False`" semantics.
- **The STEP claims are correct.** `cadquery-backend.md:100-106` — `step_url` on the design response, `GET /api/step/<id>`, "as-designed not print-oriented," and "a saved/reopened design persists only the mesh; its STEP is available on the fresh design or after a re-render." Verified against `webapp.py:900-901, 945-961, 1466-1499` (the `/api/step/<id>` route, the `step_registry`, `step_url` payload) and `pipeline.py:214-217` (the `step_path` doc-comment: "AS-DESIGNED geometry — orientation is applied only to the printable mesh … None for OpenSCAD parts").
- **The bench doc is precise.** `benchmarks/stage-8-cadquery-backend.md` names the five cases (box, through-hole, cylinder, filleted plate, boolean L-bracket), the 0.5 mm tolerance, the watertight check, and "5/5 pass" — all matching `cadquery_bench.py` (`CASES`, lines 47-69; `BBOX_TOLERANCE_MM = 0.5`, line 32; `_bbox_matches` + watertight via `validate_mesh`, lines 86-127; `{passed}/{len(results)}`, line 145).
- **The union-lift claim is correctly hedged.** Both the bench doc (lines 57-59, the explicit "honesty" note that the lift "is not pinned to a fixed number here — re-run it") and README.md:143-144 / CHANGELOG.md:33 ("the exact lift depends on the model and prompts — measure it live") avoid the trap of stating a fabricated measured number. The "can only raise, never lower" claim is backed by `Pipeline._better_result` (`pipeline.py:942-958`, "Ties favour the primary").
- **The script contract matches the prompt.** `cadquery-backend.md:90-98` (assign `result`, use `cq`, no imports except `math`, no I/O, hoist `# mm` dims, match `bounding_box_mm`, respect constraints) is a faithful summary of `prompts/system_cadquery.md:7-41`.

## What couldn't be assessed

- **The measured engine-bench performance numbers** in `benchmarks/stage-8-cadquery-backend.md:34-35` ("cadquery 2.7.0 / OCP 7.8.x on Python 3.13: all five pass; each render well under a second of worker time"). These are environment-specific measured figures; I could not re-run the bench here (no ≤3.13 + cadquery interpreter available in the audit environment, which is itself the documented graceful-absence path). They are stated as a one-time dev-box measurement, appropriately scoped ("Measured on the dev box (AMD 780M, CPU-only)"), so the framing is honest even though I did not independently reproduce them. Flagged as a low-grade precision item (DOC-005), not an accuracy defect.
- **The live dual-backend union procedure** (bench doc §2) requires the running model (`gemma4:e4b`) and is documented as a runnable procedure, not a claimed result — correct posture; nothing to verify.

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| `docs/cadquery-backend.md` (NEW) | Yes | Strong | DOC-001, DOC-004, DOC-006, DOC-007 |
| `docs/benchmarks/stage-8-cadquery-backend.md` (NEW) | Yes | Strong | DOC-005 |
| README.md (Stage 8 edits) | Yes | Strong | DOC-002, DOC-003 |
| ROADMAP.md (Stage 8 edits) | Yes | Strong | — |
| CHANGELOG.md (Stage 8 edits) | Yes | Strong | — |
| ARCHITECTURE.md (Stage 8 edits) | Yes | Strong | — |

---

## Persona walk-through

### First-time user
A user reading README.md learns CadQuery is **optional** and "with no CadQuery installed, KimCad behaves exactly as before" (README.md:145). The enable path (install `cadquery` into a Python 3.13 env; auto-discovery probes `py -3.13/-3.12/-3.11` then `python3.x`) is correct and actionable. One small friction (DOC-002): the README never states *why* a separate 3.13 is needed before sending the user to install one — that "why" lives only in the deep-dive — but the link to `docs/cadquery-backend.md` is present, so the user is not blocked.

### Returning user
The "Optional: the CadQuery backend" README section and the dedicated `docs/cadquery-backend.md` are easy to locate and answer the real questions (how to enable, how to pin/disable, what STEP is, why it's out of process). The config-knob summary is consistent across README, ROADMAP, CHANGELOG, and the deep-dive — no drift to confuse a returning reader.

### New team member
Excellent. ARCHITECTURE.md:78-80 gives a tight, accurate module map for `cadquery_runner.py` / `cadquery_worker.py` / `cadquery_bench.py`, and the deep-dive's ASCII flow diagram (`cadquery-backend.md:27-36`) orients a new engineer to the main-app↔worker split immediately. The security section is the kind of writeup a new contributor can actually trust to not introduce a regression.

---

## Findings

> **Finding ID prefix:** `DOC-`
> **Categories:** Accuracy / Completeness / Onboarding / Architecture / API / Marketing / Tone / Hygiene

### [DOC-001] — Major — Accuracy (security precision) — The worker's `__import__` is described as "yields only a geometry-only facade," but it does more: it hard-rejects every non-cadquery/math import

**Evidence**
`docs/cadquery-backend.md:76-78`: "a restricted `__builtins__` (no `open`/`eval`/`exec`/`compile`/`input`; an `__import__` that yields only a geometry-only facade of cadquery / `math`)".

The actual `_safe_import` (`cadquery_worker.py:81-94`) does two things: it returns the **facade** for `cadquery` and the real `math` for `math`, **and it raises `ImportError` for anything else** (line 92: `raise ImportError(f"import of '{name}' is not allowed …")`). The doc's phrasing describes only the "yields" half and omits the "rejects everything else" half — the more security-relevant behavior. A reader could infer the worker's `__import__` merely *narrows* cadquery but is otherwise a normal importer (i.e., that `import os` would still work and just return something harmless), when in fact `import os` raises at the worker layer too.

This is a security-precision finding: the doc slightly **understates** a real defensive behavior of the worker. Per the technical-writer rule that a doc which materially misleads about security is at least Major, and because security claims are held to a higher bar, I am classifying the imprecision in the security narrative as Major even though the direction of the error is conservative (it understates, not overstates, the protection). The risk is that a future contributor reading this could "add back" a permissive import path believing the worker never blocked imports in the first place.

**Why this matters**
The new team member persona relies on this paragraph as the authoritative description of the worker's runtime guarantees. An incomplete description of the import boundary is exactly the kind of thing that gets "simplified away" in a later refactor, weakening the second layer. Stating the full behavior (facade for cadquery, real math, **ImportError for all else**) makes the worker's contribution explicit and defensible.

**Blast radius**
- Other docs that repeat the same partial phrasing: `cadquery_worker.py:33-40` docstring uses the same "yields only the cadquery FACADE / `math`" wording and likewise omits the explicit-reject clause; CHANGELOG.md:45 and ARCHITECTURE.md:79 say "restricted builtins against a geometry-only cadquery facade" without mentioning the import rejection. Consider fixing all four together so the worker's import behavior is described identically and completely.
- User-facing: none (internal/security doc).
- Migration: none — doc-only.
- Tests to update: none; verify the import-reject path is exercised by the sanitizer/worker unit tests (a test asserting `import os` raises ImportError at the worker would make the doc claim self-evidently true).
- Related findings: none (distinct from DOC-004).

**Fix path**
Extend the clause to: "…an `__import__` that returns the geometry-only cadquery facade for `import cadquery`, the real `math` for `import math`, and **raises `ImportError` for any other import**." Mirror the same correction in the `cadquery_worker.py` docstring, CHANGELOG, and ARCHITECTURE module-map row.

---

### [DOC-002] — Minor — Onboarding — README enable steps don't say *why* a separate ≤3.13 interpreter is required before telling the user to install one

**Evidence**
README.md:148-149 leads with the constraint ("CadQuery's OCCT kernel ships no Python-3.14 wheels and KimCad runs on 3.14, so CadQuery runs in a separate **≤3.13** interpreter") — so the README actually *does* state the why. The weaker spot is the deep-dive's "Enabling it" section (`cadquery-backend.md:39-46`), which opens with "Install a Python ≤3.13 and CadQuery into it" without restating the OCCT-wheel reason at that point; the reason lives one section up under "Why it runs out of process" (lines 19-26). A reader who jumps straight to "Enabling it" via a heading anchor sees the instruction before the rationale.

**Why this matters**
First-time users frequently deep-link to the "how do I turn this on" heading. Re-stating the one-line reason ("CadQuery has no 3.14 wheels, so it needs its own ≤3.13 Python") at the top of the enable steps removes a "wait, why a second Python?" stumble.

**Blast radius**
- User-facing: minor onboarding friction only; the section is otherwise correct and complete.
- Migration: none — doc-only.
- Related findings: none.

**Fix path**
Add a half-sentence at `cadquery-backend.md:40` cross-referencing or restating the OCCT-no-3.14-wheels reason. Optional polish.

---

### [DOC-003] — Minor — Accuracy (consistency) — README "Requirements: Python 3.11+" sits beside Stage 8 prose that the app "runs on 3.14"; the relationship is correct but never reconciled in one place

**Evidence**
README.md:69 lists "Python 3.11+" as the requirement floor. README.md:148 / CHANGELOG.md:34-35 / ROADMAP.md:242 say the app "runs on 3.14" and that the CadQuery worker needs a *separate* ≤3.13. These are not contradictory — 3.11+ is the supported range for the main app, the dev/gate box runs 3.14, and CadQuery (which tops out at 3.13) is the reason a second interpreter exists — but a reader holding only the "3.11+" line and the "needs ≤3.13 for CadQuery" line could briefly wonder whether their single 3.11 install both runs KimCad *and* hosts CadQuery (it can, which is actually the simplest setup, but the docs never say so).

**Why this matters**
A user on Python 3.11 or 3.12 may not realize their existing interpreter can host CadQuery directly (no second Python needed) — the "≤3.13 worker" framing, written from the 3.14-dev-box perspective, can read as "you always need a separate Python." Stating "if you already run KimCad on 3.11–3.13, you can install `cadquery` into that same interpreter" would help.

**Blast radius**
- User-facing: a setup-clarity gap for users on 3.11–3.13 (they may over-provision a second interpreter).
- Migration: none — doc-only.
- Related findings: DOC-002 (same onboarding section).

**Fix path**
Add a one-line note in `cadquery-backend.md` "Enabling it" that a 3.11–3.13 KimCad install can host CadQuery in-place; only a 3.14 install needs a separate ≤3.13.

---

### [DOC-004] — Minor — Accuracy (security nuance) — "every cadquery submodule is stripped … so there's no module object in scope to pivot through to `os`" is true for the facade but worth a one-word hedge

**Evidence**
`cadquery-backend.md:78-81` and `cadquery_worker.py:36-40`/`66-78`: the facade is built by `_build_facade`, which copies every public **non-underscore, non-ModuleType** attribute of `cadquery` (`cadquery_worker.py:74-77`). The claim "every cadquery submodule is stripped" is accurate for *module objects directly attached to the top-level `cadquery` namespace*. It does not (and the doc does not claim it does) guarantee that no class/function reachable through the facade exposes a module-valued attribute of its own. The doc is careful — it pairs this with the explicit "what the worker layer canNOT independently do" caveat and points all residual escapes at the sanitizer — so this is not an overclaim. The single word worth adding is that the facade strips submodules *of the top-level cadquery module*, which is what `_build_facade` actually iterates (`vars(cadquery).items()`).

**Why this matters**
Security docs are read adversarially by the next auditor. Scoping the "stripped" claim to exactly what the code iterates (top-level `vars(cadquery)`) pre-empts a "but what about `SomeClass.some_module`" objection and reinforces that the sanitizer, not the facade, is the closer of the introspection class.

**Blast radius**
- Other docs with the same phrasing: `cadquery_worker.py:36-40` docstring, ARCHITECTURE.md:79, CHANGELOG.md:45-46.
- Migration: none — doc-only.
- Related findings: DOC-001 (same security paragraph).

**Fix path**
Optional: "every cadquery **top-level** submodule (`exporters`, `importers`, …) is stripped from the facade." The existing sanitizer caveat already covers the residual; this is a precision nicety.

---

### [DOC-005] — Nit — Accuracy (precision) — The bench doc's measured numbers are version-pinned to one dev-box run and may age

**Evidence**
`benchmarks/stage-8-cadquery-backend.md:34-35`: "Measured on the dev box (AMD 780M, CPU-only) against cadquery 2.7.0 / OCP 7.8.x on Python 3.13: all five pass; each render is well under a second of worker time." These are honestly scoped one-time measurements, not claimed invariants, and the bench is deterministic so "5/5 pass" is a structural guarantee (DOC verified against `cadquery_bench.py`). The version pins (cadquery 2.7.0 / OCP 7.8.x) and the timing are environment facts that will drift as the dev box upgrades.

**Why this matters**
Low. The framing already says "Measured on the dev box," so this is appropriately hedged. The only risk is a future reader treating the pinned versions as a *requirement* rather than the *as-measured* environment.

**Blast radius**
- User-facing: none material.
- Related findings: none.

**Fix path**
Optional: add "(as-measured; not a version requirement)" after the cadquery/OCP versions. Nit.

---

### [DOC-006] — Nit — Tone/Hygiene — Mixed casing of "STEP" vs ".STEP" vs ".step"

**Evidence**
`cadquery-backend.md` uses `.STEP` (lines 13, 144 in README), `.step` (line 102, "writes a `.step`"), and bare "STEP" (passim). The on-disk extension is `.step` (`cadquery_runner.py:178`, `step_path = out_dir / f"{basename}.step"`), and the download is named `kimcad-part-{sid}.step` (`webapp.py:961`). The format name is "STEP"; the file extension is lowercase `.step`. The docs occasionally render the extension uppercase (`.STEP`), which is cosmetically inconsistent with what's written to disk and downloaded.

**Why this matters**
Trivial. No reader is misled (STEP files open regardless of extension case), but a consistent convention (format = "STEP"; extension = `.step`) reads cleaner.

**Blast radius**
- Other docs: README.md:13, 144 use `.STEP`; CHANGELOG.md:52 uses `(.STEP)`; ROADMAP.md:262-263 uses `.STEP`. ARCHITECTURE.md:154 uses "STEP/BREP".
- Related findings: none.

**Fix path**
Pick one: refer to the format as "STEP" and the file as `.step`. Nit; batch with other hygiene.

---

### [DOC-007] — Nit — Completeness — Deep-dive references `tests/test_pipeline_backends.py` and `tests/test_cadquery_bench.py`; worth a one-time existence check at gate time

**Evidence**
`cadquery-backend.md:114-116` cites `tests/test_pipeline_backends.py` ("covers the mutual fallback, including a live test") and the bench doc cites `tests/test_cadquery_bench.py:29-31`. I did not verify those test files exist or contain the described coverage (out of strict doc-scope, and the Test-Engineer lane owns it). Flagging so the gate cross-checks the doc's test citations against the actual test tree — a doc that names a test which doesn't exist would be a future accuracy regression.

**Why this matters**
Low now; the citation is plausible and consistent with the module structure. It becomes a Major accuracy bug only if the named test files are absent or don't cover what's claimed — hence flag-for-verification rather than asserting a defect.

**Blast radius**
- Related findings: hand off to the Test-Engineer deep-dive (verify `test_pipeline_backends.py` + `test_cadquery_bench.py` exist and match the prose).

**Fix path**
Gate step: confirm both test files exist and the "live test that drives the real worker" claim is real. If so, no change. If not, correct the doc.

---

## Marketing / honesty audit

The README hero and the ROADMAP "Current baseline (honest, …)" framing are honest and specific. No overclaim found in the Stage 8 surface:

- CadQuery is consistently described as **optional / gracefully absent**, with the OpenSCAD path unchanged when it's off (README.md:145, `cadquery-backend.md:15-17`, ROADMAP.md, CHANGELOG.md:36-37) — verified against `Config.cadquery_interpreter()` returning `None` on absence and the "graceful absence … same posture as the optional PrintProof3D engine" parallel.
- The pass-rate "union lift" is **not** stated as a fixed measured number anywhere; it is explicitly hedged and flagged with an honesty note referencing the Stage-6 stale-figure lesson (bench doc:57-59). This is exactly the discipline the project's prior audit feedback demanded.
- The security posture is stated with both its strengths (two layers, the specific escape class the Slice-1 audit caught and closed) **and** its honest limits (OS confinement not yet implemented; the worker layer alone cannot close the `__globals__` class). No "sandboxed / secure" absolutism.
- The "BUILT, not merged/tagged" status is stated plainly and identically across all four root docs.

## Patterns and systemic observations

- **Doc-vs-code drift is essentially absent in this stage.** This is the cleanest doc set I have audited on this project. The prose was clearly written against the source, not from memory, and the prior audit-lite corrections (the Stage-8 "done/pending" overclaim) have fully held — no residue in any of the six scoped docs.
- **The security narrative is duplicated across four locations** (deep-dive, both module docstrings, ARCHITECTURE, CHANGELOG) with near-identical wording. That consistency is a strength now, but it means the DOC-001 imprecision (the `__import__` "yields only" phrasing) is repeated in all of them — fix once, apply everywhere, to keep them in lockstep.
- **Minor casing/cross-reference hygiene** (STEP/.step; test-file citations) is the only real debt, and it is cosmetic.

## Appendix: docs reviewed

- `C:\Users\scott\dev\kimcad\docs\cadquery-backend.md`
- `C:\Users\scott\dev\kimcad\docs\benchmarks\stage-8-cadquery-backend.md`
- `C:\Users\scott\dev\kimcad\README.md` (Stage 8 sections: lines 11-29, 138-154)
- `C:\Users\scott\dev\kimcad\ROADMAP.md` (Stage 8 sections: lines 35-68, 240-266)
- `C:\Users\scott\dev\kimcad\CHANGELOG.md` (Stage 8 block: lines 6-55)
- `C:\Users\scott\dev\kimcad\ARCHITECTURE.md` (Stage 8 rows: lines 76, 78-80, 86, 153-154)

### Source files verified against (not docs, but the ground truth for accuracy)

- `src\kimcad\cadquery_runner.py` — `sanitize_cadquery`, `render_cadquery`, `find_cadquery_interpreter`, banned-name/attr sets, `_read_worker_result`
- `src\kimcad\cadquery_worker.py` — `_build_facade`, `_safe_import`, `_safe_builtins`, `_run`, `_emit`, security docstring
- `src\kimcad\config.py` — `cadquery_interpreter()`, `cadquery_timeout_s()`
- `config\default.yaml` — `binaries.cadquery_python`, `limits.cadquery_timeout_s`
- `src\kimcad\webapp.py` — `/api/step/<id>` route, `step_registry`, `step_url` payload
- `src\kimcad\pipeline.py` — `step_path` field doc, `_better_result`, the parallel-backend fallback
- `src\kimcad\prompts\system_cadquery.md` — the script contract
- `src\kimcad\cadquery_bench.py` — `CASES`, `BBOX_TOLERANCE_MM`, `_bbox_matches`, `format_report`
- `git tag` (no `stage-8`); `git branch --show-current` (`stage-8-cadquery`); `git log` (5 Stage 8 slice commits, top = `b945569`)

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.
