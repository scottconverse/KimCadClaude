# QA Engineer Deep-Dive — KimCad Stage 6 (Model Layer)

- **Role:** QA Engineer (runtime behavior of the running product)
- **Date:** 2026-06-02
- **Repo:** `C:\Users\scott\dev\kimcad`
- **Branch:** `stage-6-model-swap`
- **HEAD:** `96033c2b60e177ce3be4364e04838698b11492fe`
- **Env:** Windows 11 Pro (10.0.26200), Python 3.14.3 (`.venv\Scripts\python.exe`), Node/npm frontend, Ollama @ `localhost:11434` (gemma4:e4b, qwen2.5-coder:1.5b, others installed)
- **Posture:** Balanced — ran the product, observed real runtime behavior, captured exit codes. Avoided full gemma design runs (~10 min/prompt CPU floor — a known limitation, not a defect) and used the fast qwen `plan_failed` path instead.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 0 |
| Nit      | 0 |
| **Total**| **0** |

**Verdict: PASS.** Every runtime gate exercised behaved exactly as specified. No command crashed, hung, leaked a traceback, returned a colliding exit code, printed non-ASCII that could break a legacy Windows console, or mutated state it shouldn't. The full test suite (588 incl. live OrcaSlicer), vitest (36), and the production frontend build all pass clean. No findings to report at any severity.

---

## What I ran and observed (evidence)

All commands run from `C:\Users\scott\dev\kimcad`. Exit codes captured via PowerShell `$LASTEXITCODE`.

### 1. `models` — hardware/model advisor (advisory, no config change)

```
> .venv\Scripts\python.exe -m kimcad.cli models
Hardware
  Windows 11 | 16-core CPU | 31 GB RAM | no discrete GPU (CPU/iGPU inference)

Installed models (Ollama @ http://localhost:11434/v1)
  - gemma4:e4b-it-q4_K_M  (9.6 GB)
  - gemma4:e4b  (9.6 GB)
  - qwen2.5-coder:1.5b  (1.0 GB)
  - novaforgeai/deepseek-coder:6.7b-optimized  (3.8 GB)

Recommendation
  -> Gemma E4B  [gemma4:e4b]  (installed)
  Gemma E4B is the strongest model you have installed that fits this machine (...).
  Your hardware could also run Qwen2.5-Coder 7B -- pull it for a step up in quality.
  Upgrade you could run: Qwen2.5-Coder 7B  (ollama pull qwen2.5-coder:7b)

The model is never hardwired. To choose one: set `llm.active` (or a backend's
`model_name`) in config/local.yaml, or pass `--backend <key>` to design/web/bench.
===EXIT=0===
```

- Runs cleanly, exit **0**.
- Prints all three required sections: **Hardware**, **Installed models**, **Recommendation**.
- Explicitly **advisory**: the closing paragraph states "The model is never hardwired" and tells the user *how* to choose one (config or `--backend`). It does not change config itself.
- **State check:** `git status --porcelain` immediately after the run = clean (only the untracked audit dir). No config mutation.

### 2. `bakeoff` — help + fail-fast validation (no model run)

`bakeoff --help` (exit 0) documents `--backends` (default `local_qwen,local`), `--prompts`, `--out`, `--printer`, `--material`, `--no-slice`. Help text matches observed behavior.

Single backend (needs >=2):
```
> .venv\Scripts\python.exe -m kimcad.cli bakeoff --backends local
bakeoff needs at least two backends, e.g. --backends local_qwen,local
===EXIT=2===
```

Unknown backend (lists configured backends):
```
> .venv\Scripts\python.exe -m kimcad.cli bakeoff --backends nope,local
Unknown backend 'nope'. Configured backends: cloud_deepseek, local, local_qwen, custom_openrouter
===EXIT=2===
```

- Both validation paths **fail fast** with exit **2** and a clear, actionable message **before any model is loaded** (instant return — no Ollama call). The single-backend message even includes a copy-paste example; the unknown-backend message enumerates the configured backends.
- **State check:** clean after both runs.

### 3. `design ... --backend local_qwen` — the `plan_failed` path

```
> .venv\Scripts\python.exe -m kimcad.cli design "a simple box 50mm cube with 2mm walls" --backend local_qwen
The model didn't return a usable design plan -- its response couldn't be parsed into
the required structure. This usually means the chosen model is too small or not suited
to structured planning. Try a different model (run `kimcad models` to see what fits
your machine) or rephrase the request. (details: ValidationError)
===EXIT=6===
```

- Exit **6** — the expected `plan_failed` code, **distinct from `gate_failed` (5)**. Verified against `cli.py:259-263` and `cli.py:269-271`: `plan_failed -> 6`, `gate_failed -> 5`, `render_failed -> 4`, `clarification_needed -> 3`, unknown connector -> 2, success -> 0. All codes are distinct — no collision.
- **No Python traceback.** The message is a clean, authored string (`pipeline.py:118 PLAN_FAILED_MESSAGE`, code-commented as a deliberate replacement for a raw pydantic/JSON traceback). It tells the user *why* (model too small / not suited to structured planning) and *what to do next* (`kimcad models`, rephrase). The `(details: ValidationError)` suffix is the intentional terse diagnostic (`pipeline.py:301`), not a stack dump.
- qwen failed fast at parse (well under a minute), exactly as the brief predicted.
- **State check:** clean after run.

### 4. `bench --help` — `--slice` flag present and documented

```
> .venv\Scripts\python.exe -m kimcad.cli bench --help
...
  --slice               Also slice each part (real OrcaSlicer) to grade the
                        slices-clean axis. Slower; off by default. The
                        matches-request and correct-dimensions axes are graded
                        either way.
===EXIT=0===
```

- The `--slice` flag exists and carries a clear, accurate description (default off; explains which grading axes are affected). Exit **0**.

### 5. Full runtime gate

**Python suite (incl. live OrcaSlicer):**
```
> .venv\Scripts\python.exe -m pytest tests -q
........ [ ... 100%]
588 passed in 103.32s (0:01:43)
===EXIT=0===
```
**588 passed, 0 failed, exit 0** — exact expected count, live OrcaSlicer tests included.

**Frontend vitest:**
```
> npm --prefix C:/Users/scott/dev/kimcad/frontend run test
 Test Files  6 passed (6)
      Tests  36 passed (36)
===EXIT=0===
```
**36 passed, exit 0** — exact expected count.

**Frontend production build:**
```
> npm --prefix C:/Users/scott/dev/kimcad/frontend run build
> tsc --noEmit && vite build
✓ 31 modules transformed.
✓ built in 395ms
===EXIT=0===
```
`tsc --noEmit` passes (no type errors) and `vite build` succeeds, exit **0**. Bundle: `kimcad.js` 147.6 kB (48.6 kB gzip), `Workspace.js` 538.4 kB (137.8 kB gzip — the Three.js viewer, expected to be the heavy chunk), `index.css` 15.9 kB.

**Build reproducibility note (positive):** the build's `prebuild` step `rimraf`s and regenerates the git-tracked `src/kimcad/web/assets`. After the full build, `git status` showed **no** modified assets — the regenerated output is byte-identical to what's committed. Deterministic build; nothing to flag.

### 6. Console-safety (legacy Windows console, cp1252)

Forced `PYTHONIOENCODING=cp1252` (the legacy Windows codepage that throws `UnicodeEncodeError` on characters like →, —, smart quotes) and re-ran the output-heavy paths:

- `models` under cp1252: full output rendered, exit **0**, no `UnicodeEncodeError`.
- `bakeoff --backends nope,local` under cp1252: clean error, exit **2**, no `UnicodeEncodeError`.

The CLI uses ASCII-safe substitutes by design — `->` (not →), `--` (not —), straight backticks — so it is console-safe even outside UTF-8 terminals. None of the commands in this audit emitted a `UnicodeEncodeError` under any encoding tried.

### State-mutation audit (whole session)

`git status --porcelain` was checked after `models`, after each `bakeoff` validation, after `design`, and after the frontend build. **Across the entire QA session the only working-tree change is the untracked `docs/audits/stage-6/audit-team-stage-6-2026-06-02/` directory** (this report's home). HEAD stayed at `96033c2`. No CLI command mutated `config/local.yaml` or any tracked source. The advisory `models` command and the fail-fast `bakeoff` paths are confirmed read-only / non-mutating.

---

## What's working

- **The hardware/model advisor (`models`) is exactly what it claims to be:** advisory, read-only, accurate about the machine (16-core, 31 GB, no dGPU), honest about what fits, and it surfaces a sensible upgrade path without ever touching config. The "the model is never hardwired" framing is a good UX call — it makes the no-hidden-default contract explicit to the user.
- **Fail-fast validation on `bakeoff` is real and cheap.** Both error paths return in milliseconds with exit 2 and actionable messages (one with a copy-paste example, one enumerating the configured backends) — no Ollama round-trip, no wasted minutes. This is exactly the behavior you want guarding a multi-minute operation.
- **Exit-code discipline is clean and intentional.** 0/2/3/4/5/6 are distinct and documented in-code with a comment explaining *why* `plan_failed` (6) is separate from `gate_failed` (5). The runtime confirmed exit 6, not a collision with 5.
- **The `plan_failed` path is a model-failure handled gracefully:** a too-small model (qwen 1.5b) produces an unparseable plan, and instead of a pydantic traceback the user gets a plain-English diagnosis plus a next step. This is the kind of error handling that keeps a CLI usable by non-engineers.
- **Console-safety is baked in.** ASCII-only output survives cp1252; no UnicodeEncodeError surface anywhere I pushed.
- **The runtime gate is green across all three pillars:** 588 Python tests (with live OrcaSlicer) + 36 vitest + a clean, type-checked, reproducible production build. No flakiness observed; the full Python suite ran in 103s with zero failures.
- **No surprise state mutation.** The CLI's advisory/validation commands are genuinely read-only, and the frontend build is byte-reproducible against committed assets.

---

## What I could not test (and why — not findings)

- **A full gemma `design` run end-to-end.** Out of scope by design: ~10 min/prompt on this CPU-only box is a known hardware limitation, explicitly excluded from the stage gate. I exercised the failure/validation surfaces instead, which is where the Stage-6 model-layer risk actually lives.
- **Real printer hardware / real-hardware slicing-to-print.** Explicitly post-release (Kim + community). Live OrcaSlicer *slicing* is covered by the 588-test suite; physical printing is not in scope.
- **The settled model decision** (gemma stays, qwen rejected) — per the brief this is a closed product decision, not a QA target. I verified the *mechanism* (advisor recommends gemma; qwen fails the plan path cleanly), not the *choice*.

---

## Sign-off

From a QA standpoint the Stage-6 model layer is **ready to merge+tag**. Every claimed behavior I could exercise behaved as specified, exit codes are correct and collision-free, the CLI is console-safe and non-mutating, and the full runtime gate is green. Zero findings at any severity.
