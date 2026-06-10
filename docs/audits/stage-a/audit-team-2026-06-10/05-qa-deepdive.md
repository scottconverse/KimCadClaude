# Runtime QA Deep-Dive — KimCad, Stage A (first-run hardening)

**Audit date:** 2026-06-10
**Role:** QA Engineer
**Scope audited:** Stage A runtime behavior NOT covered by the live walkthrough (`docs/audits/walkthrough-stage-a-2026-06-10/WALKTHROUGH-REPORT.md`): the `bench`/`bakeoff`/`models` CLI error paths with an unreachable model, web `/api/photo-seed`, `/api/sketch-seed`, and `/api/render/<id>` error paths, the ToolMissingError web surface and its SPA rendering, and the new stderr phase output's encoding behavior on Windows legacy-codepage consoles and redirects.
**Environment:** Windows 11 Pro 10.0.26200, Python 3.13.13 (`.venv`), commit `5aad7f3`. Ollama was left RUNNING throughout (per directive); model-down was simulated via a temporary gitignored `config/local.yaml` backend (`deadport`) pointing at `http://127.0.0.1:9655/v1` (nothing listening). Tool-missing was simulated by temporarily overriding `binaries.orcaslicer` to a nonexistent path. Both overrides were reverted after testing; all test servers (:8705 demo, :8706 real-mode/deadport, :8707 demo/no-orca) were stopped; test output dirs removed.
**Auditor posture:** Adversarial

This report deliberately does NOT re-run what the walkthrough proved (CLI `design` vs genuinely-stopped Ollama, web `model_unavailable` vs stopped Ollama, wizard/pill states, demo design→slice→download, WALK-A-001 double-bind, WALK-A-002 retry stacking).

---

## TL;DR

Stage A's friendly model-down mapping is real and solid on the surfaces it was built for — `design` (CLI and web) handles a connection-refused dead port exactly as well as it handled a stopped Ollama, the new stderr phase lines never crash any console configuration tested, and the web error endpoints survived a full adversarial sweep with zero 500s and zero server-side tracebacks. But the mapping does not extend to the surfaces next door: `kimcad bench`/`bakeoff` leak raw `APIConnectionError` per case and exit 0 on a 0% run; a never-fetched OrcaSlicer never reaches the QA-003 friendly message (profile resolution fails first with a raw filesystem path); and photo/sketch upload with the model down blames the user's photo instead of the down model. Three Majors, all the same theme: Stage A's promise is kept on the main road and broken on the side roads.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 2 |
| Nit | 2 |

## What's working

- **`kimcad models` with the server down is clean** — `kimcad models --base-url http://127.0.0.1:9655/v1` returned in 3s, exit 0, with a complete hardware readout, "(none detected -- is Ollama running, with models pulled?)", and a correct recommendation. No traceback, no hang. The output is deliberately pure ASCII (`->`, `--`), so it is codepage-proof.
- **`kimcad design` against a connection-refused port shares the fixed mapping** — exit 2, the exact `MODEL_UNAVAILABLE_MESSAGE` + the `ollama pull` recovery line on stderr, one deduped phase line ("Planning the shape…") on stderr, stdout completely empty. The walkthrough proved this against a stopped Ollama; this proves the same path for the refused-connection flavor.
- **stdout/stderr discipline holds** — phases and errors go to stderr; stdout stays reserved for the report. Pipes work.
- **No UnicodeEncodeError anywhere** — `_force_utf8_output` (cli.py:35) successfully reconfigures redirected streams: stderr redirected to a file came out as valid UTF-8 with the U+2026 ellipsis intact (`file` reports "Unicode text, UTF-8"). Direct console output on modern Python goes through WriteConsoleW and is codepage-independent. The em-dash/ellipsis characters in `_PHASE_LABELS` and the error messages cannot crash the CLI in any configuration tested.
- **Web `/api/design` on a dead port returns the typed state** — 200 `{"status": "model_unavailable", "error": "KimCad couldn't reach your local AI…"}` in 10s on :8706. The walkthrough proved stopped-Ollama; this proves connection-refused.
- **`/api/render/<id>` survived a full adversarial sweep with zero 500s** — unknown id → 404 "That design couldn't be found."; non-numeric id → 404; `values` as a list → 400 "Provide the parameter values to re-render."; malformed JSON → 400 "Request body isn't valid JSON."; and the QA-501 fix holds live: `{"width":Infinity,"height":1e400,"depth":"abc","wall":50}` returned 200 with `adjusted_params` echoing `requested: null` for every non-finite/non-numeric input and `{"requested": 50.0, "applied": 8.0}` for the out-of-range clamp — exactly the documented contract, no `allow_nan` 500.
- **`/api/photo-seed` body guards work** — empty body → 400 "Empty upload.", declared 99,999,999 bytes → 413 "File too large." with the connection closed, 2KB of `/dev/urandom` in demo mode → clean 200 with the canned demo seed.
- **Tool-missing slice path degrades without a 500 and without leaking a traceback** — with `binaries.orcaslicer` pointing nowhere, `/api/slice/1` returned 200 `{"sliced": false, reason, note}` (wrong *reason*, see QA-A-002, but the typed-degradation shape is right) and the mesh stayed downloadable.
- **Server-side log hygiene is perfect** — across all three servers and every error path exercised (model-down design, model-down photo/sketch, tool-missing slice, all the 4xx probes), the server consoles contained zero tracebacks and zero error spam.
- **Bench persists its verdict before printing** — `output/bench/summary.txt` was written (UTF-8) before stdout printing, exactly as the code comment promises; a console encoding failure can't discard a long run.

## What couldn't be assessed

- **A live bench/bakeoff against the real model** — minutes of CPU per prompt on this machine; out of audit budget. All model-down behavior was exercised with 2-case prompt files against the dead port; the happy-path benchmark was not re-validated.
- **OpenSCAD's ToolMissingError on the design path, live** — reaching it requires a successful model plan first (minutes with the real model). Verified statically instead: `slicer.py:206`-style up-front check exists in the OpenSCAD runner, `webapp.py:1506` maps it to `render_failed` + `str(e)`, and the SPA (`src/kimcad/web/assets/kimcad.js`) renders `render_failed` as "I couldn't build that one — {error}", which would carry the fetch_tools recovery command. High confidence, not live-proven.
- **True legacy conhost glyph rendering** — I verified the byte/decode level (forced `[Console]::OutputEncoding` to cp437 and captured the mojibake), but could not visually observe a physical legacy conhost window from this harness.
- **Stopping Ollama** — prohibited by the audit directive; all down-states used a dead port. The walkthrough already covered genuinely-stopped Ollama for design/web.

---

## Product shape

A local-first text→CAD pipeline with three runtime surfaces: a CLI (`design`/`bench`/`web`/`models`/`bakeoff`), a localhost web SPA over a threaded stdlib HTTP server, and external tool subprocesses (OpenSCAD, OrcaSlicer) plus a local Ollama model server. Stage A's claim is that the likely first-run failures — model server down, model not pulled, tools never fetched — end in one friendly, actionable line on every surface. QA therefore focused on exit codes, stderr/stdout discipline, error-response shape, Windows console encoding, and whether the friendly mapping actually covers *every* surface that can hit those failures.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| `kimcad models --base-url <dead port>` | Pass (3s, exit 0, clean) | QA-A-007 (nit) |
| `kimcad design` → dead port, stdout+stderr redirected | Pass (exit 2, friendly, UTF-8) | — |
| `kimcad design` → dead port, captured under forced cp437 console encoding | Partial (no crash; mojibake) | QA-A-004 |
| `kimcad bench` → dead port, 2 cases, `--min-success-rate 0.7` | Fail (raw `APIConnectionError` per case; exit 1) | QA-A-001 |
| `kimcad bench` → dead port, 2 cases, no min rate | Fail (**exit 0** on 0/2) | QA-A-001 |
| `kimcad bakeoff` model-down (static — shares `run_benchmark`) | Fail (same gap, doubled) | QA-A-001 |
| Web `/api/design` real mode → dead port | Pass (200 `model_unavailable`, 10s) | — |
| Web `/api/photo-seed` + `/api/sketch-seed` real mode → dead port | Fail (422 blames the photo) | QA-A-003 |
| Web `/api/photo-seed` guards (empty / oversize / garbage) | Pass | QA-A-006 (nit) |
| Web `/api/render/<id>` adversarial sweep (incl. QA-501 non-finite) | Pass | — |
| Web `/api/slice/1` with OrcaSlicer binary absent | Fail (raw `no_profile` path leak, not the QA-003 message) | QA-A-002 |
| SPA rendering of tool-missing/slice-failure notes (static, bundled JS) | Pass (renders `note`/`error` verbatim) | feeds QA-A-002 |
| Server console hygiene across all of the above | Pass (zero tracebacks) | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Backend at a port that refuses instantly | design: friendly exit 2 — but 38s of pure backoff sleep on an instantly-refused connection (corroborates WALK-A-002; web took 10–14s) | (WALK-A-002, not re-filed) |
| Benchmark batch with every case failing on connection | Raw SDK class name in the verdict; exit 0 without `--min-success-rate`; "Mean wall-clock per prompt: 0.0s" | QA-A-001, QA-A-005 |
| 2KB of random bytes as a "photo" (real mode, model down) | 422 after 14s, message blames the photo | QA-A-003 |
| Content-Length: 99999999 | 413, connection closed | — |
| Malformed Content-Length header | 400 "Empty upload." (wrong copy, right refusal) | QA-A-006 |
| `Infinity` / `1e400` / string / out-of-range slider values | 200, contract-correct `adjusted_params`, no 500 | — |
| Unknown vs known-but-untemplated design id on `/api/render` | Distinct 404 messages as documented | — |
| OrcaSlicer binary path nonexistent | 200 typed failure, but raw profile-path note | QA-A-002 |
| Forced cp437 console capture of stderr phases | `Planning the shapeΓÇª` (U+2026 → 3 mojibake chars), no crash | QA-A-004 |

---

## Findings

### [QA-A-001] — Major — Install/Flow — `kimcad bench` and `kimcad bakeoff` bypass Stage A's model-down mapping: raw `APIConnectionError` per case and exit 0 on a 0% run

**Evidence**
1. Add a backend pointing at a dead port (`http://127.0.0.1:9655/v1`) to `config/local.yaml`; create a 2-case prompts YAML.
2. `kimcad bench --prompts <2-case.yaml> --backend deadport --out output_test/qa-bench --min-success-rate 0.7`
3. Observed (22s): `Benchmark: 0/2 completed (0%) … XX q01: error … -- APIConnectionError: Connection error.` for every case; exit 1.
4. Same command without `--min-success-rate`: identical output, **exit 0**.
5. Expected (Stage A's own bar, set by `design`): one fail-fast, friendly "KimCad couldn't reach your local AI… Start Ollama…" line and a non-zero exit — not N timed-out cases each described by a raw SDK class name.

Root cause: the pipeline correctly propagates `APIConnectionError`, but `run_benchmark` (`src/kimcad/benchmark.py:308`) catches every per-case exception and records `f"{type(e).__name__}: {e}"` as a case outcome — so the exception never reaches `cli.main`'s `_is_model_unreachable` mapping (`src/kimcad/cli.py:504`). `kimcad bakeoff` runs `run_benchmark` once per backend (`src/kimcad/bakeoff.py`), so a down model produces a 0%-vs-0% "comparison" (mean 0.0s each → tie → "keep the current default"), exit 0, after burning the whole multi-backend wall-clock.

**Why this matters**
With the real 20-prompt Appendix-B set and a stopped (timing-out, not refusing) Ollama, the user pays roughly 20 × the ~21s measured fail time ≈ 7 minutes for a worthless 0/20 verdict that never says "start Ollama" — and `bench` reports success (exit 0) to any script or CI step that isn't passing `--min-success-rate`. The bake-off doubles the waste. These are exactly the commands a contributor runs right after a fresh setup, i.e. when Ollama most plausibly isn't running.

**Blast radius**
- Adjacent code: `src/kimcad/benchmark.py:294-319` (`run_benchmark`), `src/kimcad/cli.py:324-400` (`_cmd_bench`, `_cmd_bakeoff`), `src/kimcad/bakeoff.py` (`run_bakeoff`). The fix wants a cheap model preflight (e.g. one probe via the existing `model_advisor.probe_ollama`, or re-raise when `_is_model_unreachable(e)` on the *first* case) before/inside the batch loop — keep the per-case catch for genuine single-case failures.
- Shared state: `_is_model_unreachable` / `MODEL_UNAVAILABLE_MESSAGE` in `src/kimcad/pipeline.py:180-189` are the single source of truth; the fix should reuse them, not fork the wording.
- User-facing: bench/bakeoff fail fast with the same friendly line as `design`; summary text for a partially-down run changes shape.
- Tests to update: `tests/test_cli.py` bench-path tests; benchmark harness tests asserting the swallow-everything behavior (`run_benchmark` "one bad case can't abort the batch" contract needs a carve-out for model-unreachable).
- Related findings: QA-A-005 (the 0.0s duration lie comes from the same except arm); WALK-A-002 (retry stacking multiplies the per-case wasted time 20×).

**Fix path**
Recommend: in `make_case_runner.run_one` (or `run_benchmark`), re-raise when `_is_model_unreachable(e)` so the existing `cli.main` mapping fires; alternatively preflight the backend once per bench/bakeoff with a 3s probe and exit 2 with `MODEL_UNAVAILABLE_MESSAGE` before any case runs. Also make a 0-completed bench exit non-zero even without `--min-success-rate`.

### [QA-A-002] — Major — Install/Flow — A never-fetched OrcaSlicer never reaches the QA-003 friendly message: profile resolution fails first with a raw filesystem path

**Evidence**
1. Set `binaries.orcaslicer: tools/DOES_NOT_EXIST/orca-slicer.exe` in `config/local.yaml` (equivalent to a fresh clone where `python scripts/fetch_tools.py` was never run — the whole `tools/orcaslicer/` tree is absent).
2. `kimcad web --port 8707 --demo`; POST `/api/design`; POST `/api/slice/1` with `{}`.
3. Observed: 200 `{"sliced": false, "reason": "no_profile", "note": "no machine profile named 'Bambu Lab P2S 0.4 nozzle' found under C:\\Users\\scott\\Desktop\\Code\\kimcadclaude\\tools\\DOES_NOT_EXIST\\resources\\profiles"}`. The SPA renders that note verbatim in the export panel (`Workspace.js`: `p.note || "KimCad couldn’t slice this part."`).
4. Expected: the `ToolMissingError` message — "OrcaSlicer isn't installed at … Run `python scripts/fetch_tools.py` to download it…" (`src/kimcad/errors.py`), which Stage A built precisely for this scenario (QA-003).

Root cause: `config.orca_profiles_root()` derives the profile tree from the OrcaSlicer binary path (`src/kimcad/config.py:133-136`), and both slice paths call `resolve_slice_settings(...)` **before** `slice_model`'s up-front binary check (`src/kimcad/webapp.py:613` and `src/kimcad/pipeline.py:419`; the `ToolMissingError` raise is at `src/kimcad/slicer.py:206`). When the binary is missing, its profile tree is necessarily missing too, so `OrcaProfileError` ("no_profile", raw path) always wins and the friendly tool-missing message is unreachable on the exact first-run scenario it was written for. Same ordering affects the CLI `--slice` path (`_slice_intent` catches `OrcaProfileError` and prints the same raw-path note).

**Why this matters**
The QA-003 acceptance scenario — fresh machine, skipped fetch step, first slice attempt — gets an error that names a printer profile and an absolute path into a directory the user never created, with no recovery command. The honest typed-degradation plumbing all works; it just delivers the wrong diagnosis. This is "implemented but unreachable," the same shape as WALK-A-001.

**Blast radius**
- Adjacent code: `src/kimcad/webapp.py:600-632` (`slice_registered_mesh`), `src/kimcad/pipeline.py:415-425` (pipeline slice), `src/kimcad/cli.py:194-209` (`_slice_intent`) — all three call `resolve_slice_settings` first and need the binary-existence check hoisted ahead of it (or `resolve_slice_settings` should detect a missing binary/profiles root and raise `ToolMissingError` itself).
- Shared state: `config.binary_path("orcaslicer")` / `orca_profiles_root()` coupling is the root; fix once in config or slicer, not three call sites.
- User-facing: web slice panel and CLI `--slice` runs on a tool-less install start showing the fetch_tools recovery line; `reason` for this case should become `tool_missing` (the SPA already renders `note` generically, so no frontend change needed).
- Tests to update: any slicer/webapp test asserting `no_profile` for a missing binary; add a regression test "binary absent ⇒ ToolMissingError before profile resolution."
- Related findings: walkthrough WALK-A-001 (same "guard exists but unreachable" pattern); QA-A-003 (same theme: right plumbing, wrong diagnosis).

**Fix path**
Recommend checking `Path(binary).is_file()` (raising `ToolMissingError`) at the top of `slice_registered_mesh` / the pipeline slice step / `_slice_intent`, or inside `resolve_slice_settings` when the profiles root's binary is absent — then map it to `reason: "tool_missing"` (web) which `webapp.py:1877` already handles.

### [QA-A-003] — Major — Flow/API — Photo and sketch upload with the model down blames the user's image: 422 "try a clearer shot" instead of the model-unavailable truth

**Evidence**
1. `kimcad web --port 8706 --backend deadport` (real mode, dead port — the stand-in for stopped Ollama).
2. POST `/api/photo-seed` with 2KB of bytes.
3. Observed (14s): 422 `{"error": "Couldn’t read that photo — try a clearer shot, or cancel and describe the part in words."}`. `/api/sketch-seed`: same pattern ("try a clearer image"). Nothing logged server-side.
4. Expected: the same honest model-down message every other surface gives — `/api/design` on the *same server moments later* correctly returned `model_unavailable` "KimCad couldn't reach your local AI…".

Root cause: `_handle_photo_seed` / `_handle_sketch_seed` (`src/kimcad/webapp.py:1383-1429`) wrap the vision call in a blanket `except Exception → 422 cant_read`, with no `_is_model_unreachable(e)` branch and no server-side log.

**Why this matters**
Ollama-down is Stage A's headline failure mode. A user whose model isn't running uploads a perfectly good photo, waits ~14s, and is told their *photo* is the problem — so the natural next step is retaking the photo and retrying forever, not starting Ollama. The design path tells the truth; this path actively misleads on the same underlying condition. The silent `except` also means a genuinely interesting vision failure leaves no trace in the server log (counter to the QA-008 pattern used elsewhere).

**Blast radius**
- Adjacent code: both handlers (`_handle_photo_seed`, `_handle_sketch_seed`) share the pattern — fix both. The check and message already exist (`_is_model_unreachable`, `MODEL_UNAVAILABLE_MESSAGE` in `src/kimcad/pipeline.py`), and `_handle_design` (`webapp.py:1498`) is the model to copy.
- User-facing: photo/sketch upload with Ollama down starts saying "start Ollama" (the SPA's photo flow shows the `error` string it gets, so a wording-only change flows through; verify the SPA treats it as retryable-after-start rather than photo-specific).
- Tests to update: webapp photo/sketch-seed tests; add a model-down case asserting the model-unavailable message (or a typed status) rather than `cant_read`.
- Related findings: QA-A-002 (right plumbing, wrong diagnosis); walkthrough Slice-9 web mapping (the pattern this should have inherited).

**Fix path**
Recommend a `_is_model_unreachable(e)` branch in both handlers returning the model-unavailable message (422 with that error string, or the typed `model_unavailable` shape if the SPA can render it there), plus a `self.log_error` for the residual unexpected-exception arm.

### [QA-A-004] — Minor — Console — Phase-label ellipsis mojibakes on legacy-codepage (OEM) console captures; no crash anywhere

**Evidence**
1. In Windows PowerShell 5.1 with `[Console]::OutputEncoding` forced to cp437 (the stock OEM default on most machines; this machine's profile had overridden it to UTF-8), capture kimcad's stderr through a pipe: `cmd /c "...kimcad.exe design x --backend deadport ... 2>&1 1>nul"`.
2. Observed: `  Planning the shapeΓÇª` — the U+2026 in `_PHASE_LABELS` (`src/kimcad/cli.py:243-248`) arrives as three mojibake characters (code points 915,199,170). With UTF-8 console encoding the same capture is perfect (code point 8230).
3. No crash in any configuration: stderr redirected to a file is valid UTF-8 (verified with `file`); direct console writes go through WriteConsoleW on Python 3.13 and are codepage-independent; `_force_utf8_output` covers pipes/files.

**Why this matters**
Stock Windows PowerShell 5.1 users who pipe or capture kimcad output (`kimcad bench | Tee-Object run.log`, CI wrappers, `2>&1` captures) see garbled phase lines — and the stdout report's `×`/`³`/`°` glyphs garble the same way. Cosmetic, never data-corrupting (the persisted `summary.txt`/`bakeoff.txt` are written UTF-8 directly), and self-inflicted by the legacy host's decode side — but it lands on the default console configuration of the OS this product targets. The error messages themselves are pure ASCII and always survive.

**Fix path**
Recommend either accepting it (document `chcp 65001` / `$OutputEncoding` guidance in troubleshooting.md) or using ASCII `...` in `_PHASE_LABELS` — the labels are the only new non-ASCII on the stderr path and the cheapest to make codepage-proof. The report glyphs are a pre-Stage-A decision; don't churn them for this.

### [QA-A-005] — Minor — Flow — Bench reports "Mean wall-clock per prompt: 0.0s" when cases error, hiding the real cost of a failing run

**Evidence**
The 2-case dead-port bench above took 22s of wall clock but printed `Mean wall-clock per prompt: 0.0s` — the per-case `except` arm in `run_benchmark` (`src/kimcad/benchmark.py:308-318`) hardcodes `duration_s=0.0` because the timing lives inside `run_one`, which raised. The persisted `summary.txt` carries the same fiction.

**Why this matters**
Any bench/bakeoff with errored cases under-reports duration, and the bake-off's speed tiebreak (`_rank_key`, `bakeoff.py`) compares these 0.0 means — a backend that errors fast on half its cases looks "faster" than one that honestly completes. Low exposure today; misleading in exactly the diagnostic moment the numbers matter.

**Fix path**
Recommend timing in `run_benchmark` around the `run_one` call (or a try/finally inside `run_one`) so errored cases carry their real duration.

### [QA-A-006] — Nit — API — Malformed `Content-Length` on uploads is refused with the wrong copy ("Empty upload.")

A non-numeric `Content-Length` header on `/api/photo-seed` parses to the `declared = -1` sentinel in `_read_raw_body` (`src/kimcad/webapp.py:1778-1789`) and falls into the `declared <= 0` arm — 400 "Empty upload." for a request that wasn't empty. Right refusal, wrong sentence. One-line fix: a distinct message (or 400 "Bad request") for the `-1` case.

### [QA-A-007] — Nit — Flow — `kimcad models` can't tell "Ollama down" from "no models pulled"

`_cmd_models` uses `probe_installed_models` (returns `[]` for both states) rather than the `probe_ollama` variant the Settings UI uses to distinguish them (`src/kimcad/model_advisor.py:263-285`). The output hedges honestly ("is Ollama running, with models pulled?"), so this is preference, not a defect — but the better probe already exists one function away, and the CLI could say which problem the user actually has.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| `kimcad models` vs dead server | 3s, exit 0 | <5s | pass |
| `kimcad design` fail-fast vs refused port (CLI) | 38s | ≈7s intended | fail — pure backoff sleep on an instantly-refused connect; corroborates WALK-A-002 (not re-filed) |
| Web `/api/design` fail vs refused port | 10s | | same root |
| Web `/api/photo-seed` fail vs refused port | 14s | | same root |
| `kimcad bench`, 2 cases, model down | 22s (≈11s/case) | ≈3s with a preflight | fail — see QA-A-001 |
| CLI startup (`--help`) | <1s | <2s | pass |

## Security / privacy snapshot

Nothing new. The error paths exercised leak no tracebacks, no exception class names to the browser (the bench *terminal* output leaks `APIConnectionError`, filed as part of QA-A-001's friendliness gap, not a security issue), and the 413 guard closes the connection on oversize uploads. Photo/sketch bytes are not persisted on the failure paths (verified: nothing written under the web root for the failed seeds). Servers bind 127.0.0.1.

## Console and log observations

Zero tracebacks and zero error spam across all three server consoles for every error path exercised. The one log gap: photo/sketch-seed failures log nothing at all (part of QA-A-003) — the opposite extreme from the QA-008 "log server-side, generic to browser" discipline used everywhere else.

## Patterns and systemic observations

One pattern explains all three Majors: **Stage A's friendly mapping lives at the surface layer (`cli.main`, `_handle_design`) but the failure can be intercepted below it** — `run_benchmark` swallows it (QA-A-001), profile resolution preempts it (QA-A-002), a blanket `except` mislabels it (QA-A-003). The mapping itself (`_is_model_unreachable` + `MODEL_UNAVAILABLE_MESSAGE` + `ToolMissingError`) is well-built and single-sourced; the fixes are all "route this surface's exception to the mapping that already exists," not new machinery. A grep for `except Exception` between the pipeline and the user is the cheapest way to find any remaining side roads before Stage B.

## Appendix: environments and artifacts

- Windows 11 Pro 10.0.26200; Python 3.13.13 (`.venv\Scripts\kimcad.exe`); commit `5aad7f3`; Ollama left running throughout.
- Tools: curl 8.x (Git bash), PowerShell 5.1 (cp437-forced capture test), cmd.exe, `file`, netstat/taskkill.
- Servers: :8705 (`--demo`), :8706 (`--backend deadport`, real mode), :8707 (`--demo` + bogus `binaries.orcaslicer`). All stopped after testing.
- Temporary overrides in gitignored `config/local.yaml` (a `deadport` backend at `http://127.0.0.1:9655/v1`; a bogus `binaries.orcaslicer`) — **reverted**; restored file verified byte-identical to the backup. Test outputs under `output_test/qa-*` removed. Working tree after the audit: only the audit-report directories untracked.
- Exact commands run are reproduced inside each finding's Evidence block; the bench prompts file was a 2-case YAML (`q01` cube / `q02` cylinder) in `%TEMP%`.
