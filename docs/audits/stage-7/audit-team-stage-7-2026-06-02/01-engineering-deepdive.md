# 01 — Principal Engineer Deep-Dive — KimCad Stage 7 (Smart Mesh + PrintProof3D)

**Audit date:** 2026-06-02
**Scope:** Stage 7 surface — `smart_mesh.py`, `printproof3d.py`, `history.py`, the
`pipeline.py` Stage-7 additions, `webapp.py` / `cli.py` / `config.py` injection seams, and
`config/default.yaml`.
**Repo / commit:** `C:\Users\scott\dev\kimcad`, branch `stage-7-smart-mesh`, head `a89841c`.
**Suite:** `664 passed in 95.70s` (full), Stage-7 subset `55 passed in 0.48s`. Verified locally
with `.venv/Scripts/python.exe`.
**Posture:** balanced — credit the solid parts, flag every real issue Blocker→Nit with evidence.

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 3 |
| Nit      | 3 |
| **Total**| **7** |

**No Blocker or Critical found.** The load-bearing Stage-7 invariants — never-breaks-the-build,
the gate-FAIL→no-slice authority boundary, injection safety, and local-first privacy — all hold
under direct testing. The single Major is a concurrency data-loss defect in the learning store
that is reachable through the threaded web server but never threatens a build.

---

## What's working

This is disciplined, well-tested defensive code. Specifics worth crediting:

- **The never-raises contract is real, not aspirational.** `validate_model` degrades to `None`
  on every failure mode — no binary, no report file, a raising runner, an unparseable report, a
  profile-build error (`printproof3d.py:68,80-81,92-96,97-103`). I fed `assess_readiness`
  degenerate inputs (empty gate, empty mesh, blank codes, an unexpected `gate.status` string) and
  it never raised; an unknown status falls back via `_GATE_BASE.get(..., 70)` (`smart_mesh.py:125`).
  `_parse_report` rejects non-dict bodies, bad statuses, non-list `issues`/`suggested_fixes`, and
  unknown severities without raising (`printproof3d.py:106-138`).
- **The worst-of-two tone is exactly right and well-commented.** The card is never more optimistic
  than *either* KimCad's own read *or* the engine's `status` — a `fail` engine report forces
  "Not print-ready" even when its worst individual issue only nudged the score
  (`smart_mesh.py:152-171`). The unit tests pin this precisely (`test_smart_mesh.py:113-131`).
- **Bed-positioning on a COPY.** `_compute_readiness` copies the hardened mesh and translates the
  copy to the bed origin before validation, so the artifact that ships is never mutated by the
  readiness pass (`pipeline.py:509-510`). The contract is documented at the call and the callee
  (`printproof3d.py:64-67`) and pinned by `test_printproof3d_validates_a_bed_positioned_mesh`.
- **Injection-safe by construction.** The binary path comes only from config
  (`config.printproof3d_binary()`), never from a prompt or model output; argv is a list with
  `shell` defaulting to False; `check=False` is deliberate because a non-zero exit is a *fail
  verdict*, not a crash, and the parsed report file is the source of truth
  (`printproof3d.py:43-48,83-103`).
- **Honest attribution and confidence.** Confidence is High only when the engine actually ran and
  the geometry was analysable, Medium for gate-only, Low when the mesh couldn't be analysed; the
  attribution string names exactly what backed the verdict and is augmented (not overwritten) when
  history folds in (`smart_mesh.py:198-214`, `pipeline.py:537`).
- **Local-first privacy holds.** The store defaults to `~/.kimcad/history.json` — per-user, outside
  the repo (`config.py:128-137`); the record is coarse (type, score, gate, material, largest
  dimension), with an explicit "no geometry, no prompt" comment (`history.py:27-39`,
  `pipeline.py:540-559`). No network egress anywhere in the Stage-7 surface.
- **The demo path is correctly excluded from history** so a UI smoke check never pollutes a user's
  store (`webapp.py:197-198`).
- **The advisory boundary is clean.** Readiness is attached to the report (`pipeline.py:433`) but
  the gate-FAIL→no-slice decision (`pipeline.py:443`) is unchanged and reads `gate.status`, not
  readiness. Readiness cannot weaken the slice gate.
- **Frontend is XSS-safe.** The readiness card renders every engine/gate-derived string
  (`comparison`, `attribution`, risk `title`/`detail`) as React `children`, which auto-escapes;
  no `innerHTML`/`dangerouslySetInnerHTML` on the readiness path (`web/assets/Workspace.js`).
- **Test coverage is genuinely good** — 55 Stage-7 tests covering purity, every degrade path,
  bed-positioning, the rerender-skips-engine contract, history round-trip, and all comparison
  wordings.

---

## Findings

### ENG-701 (Major) — `HistoryStore.record` is a non-atomic read-modify-write; concurrent web requests lose history records

**Category:** Correctness / Concurrency

**Evidence:** `src/kimcad/history.py:103-115`
```python
def record(self, rec: PrintRecord) -> None:
    try:
        existing = self.load()                       # read
        existing.append(rec)                          # modify
        existing = existing[-_MAX_RECORDS:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(                         # write (non-atomic, full overwrite)
            json.dumps([asdict(r) for r in existing], indent=2), encoding="utf-8"
        )
    except OSError:
        return
```
The read (`load()`), the in-memory append, and the full-file overwrite (`write_text`) are three
separate steps with no lock and no atomic replace. The web server is
`ThreadingHTTPServer` (`webapp.py:30,888`), so every HTTP request runs on its own thread against
the **one** shared `HistoryStore` built in `build_web_pipeline` (`webapp.py:198`) pointing at the
single per-user `~/.kimcad/history.json`. Two concurrent design submissions therefore race in
`_record_history` → `record()`.

I reproduced the race directly against the real class:
- **2 concurrent writers** seeded with 1 record reliably end with **2** records instead of 3 —
  one lost update *every* trial.
- **8 writers** → `[1, 2, 2]` records (of 9 expected).
- **40 writers** → `[1, 6, 0]` records — in one trial the store collapsed to a single record,
  i.e. near-total loss of the learning history.

The collapse mechanism: `write_text` truncates-then-writes (not atomic), so a `load()` landing
mid-write reads a partial/empty file, hits `json.loads`' `ValueError`, returns `[]` (by design,
`history.py:78-83`), and the next writer then overwrites the file with that near-empty list.

**Why this matters:** The learning store is the entire basis of the "compared to your past
prints" line — Stage 7's headline differentiator. Under concurrency it silently discards build
history, so the comparison degrades or resets with no error and no user signal. It is *data loss
under normal operation* for the web entry point, though bounded to a non-load-bearing feature.
It does **not** break a build (the whole path is best-effort and swallowed) and it does **not**
affect the CLI in normal single-run use.

**Severity rationale:** Not Critical — no build breaks, no security/privacy impact, the lost data
is coarse advisory history, and the single-user CLI case is unaffected. But it is a genuine
data-loss defect reachable on the shipped threaded server with realistic usage (two tabs, rapid
re-submits), so it clears the Major bar (meaningful impact, plausible-to-likely exposure).

**Blast radius:**
- Adjacent code: only `HistoryStore.record`/`load` and their two callers
  (`pipeline._record_history`, `_apply_history_comparison`). The fix is local to `history.py`.
- Shared state: the single `~/.kimcad/history.json` shared across the threaded web server and any
  concurrent CLI invocation pointed at the same path.
- User-facing: the readiness card's "compared to your past prints" line and the personal-best
  call-out become unreliable; no other surface changes.
- Migration: none — file shape is unchanged.
- Tests to update: none break. Add a concurrency test (N threads → all records present) and,
  if you adopt advisory locking, a same-process serialization test.
- Related findings: none share the root cause.

**Fix path (recommended, in order of robustness):**
1. **Atomic write** — serialize to a sibling temp file in the same directory and `os.replace()`
   onto the target. `os.replace` is atomic on Windows and POSIX, which alone eliminates the
   truncated-read collapse (the worst symptom). This is a ~5-line change and the minimum bar.
2. **Cross-process advisory lock around the read-modify-write** — a lockfile (e.g. `msvcrt.locking`
   on Windows / `fcntl.flock` on POSIX, or the `filelock` package) so the load→append→write is
   mutually exclusive. This also closes the lost-update window between two *processes* (web +
   CLI on the same store), which the atomic write alone does not.
3. **Append-oriented format** — switch the store to JSON Lines (one record per line, opened in
   append mode with a single `write`). Appends don't read-modify-write, so concurrent appends
   don't lose data; `_MAX_RECORDS` trimming moves to a periodic compaction. Larger change; only
   worth it if the store is expected to see heavy concurrent write volume.

Recommend (1) + (2) together: atomic replace kills the catastrophic truncation, the advisory lock
kills the remaining lost-update window, and both keep the existing file format and tests intact.

---

### ENG-702 (Minor) — `record()` catches only `OSError`; defense-in-depth gap (currently masked by the caller)

**Category:** Correctness / Robustness

**Evidence:** `src/kimcad/history.py:103-115` — the `try` body runs `asdict(...)` and
`json.dumps(...)` but the `except` clause is `except OSError`. A serialization failure
(`TypeError`/`ValueError`) from a future non-trivial field would escape `record()`.

In practice this is safe **today** for two reasons I verified: (a) `PrintRecord` fields are simple
scalars/strings and `json.dumps` with the default `allow_nan=True` does not raise even on `inf`/`NaN`
(it emits the non-standard `Infinity`/`NaN` token); and (b) the only caller,
`pipeline._record_history`, wraps the call in a broad `except Exception` (`pipeline.py:546-559`),
so a hypothetical raise is caught one frame up and the build still completes.

**Why this matters:** The module's own docstring and method contract promise "never raises," but
the implementation only honors that for `OSError`. The promise currently holds only because the
caller backstops it. If a future caller invokes `record()` directly (a batch importer, a test
fixture, a CLI `history` subcommand), the contract would silently not hold.

**Severity rationale:** Minor — no current reachable failure, fully masked by the caller, no user
impact today. It's a latent contract gap, not a live bug.

**Fix path:** Broaden the `record()` except to `except (OSError, TypeError, ValueError)` (or
`except Exception` to match the stated "never raises" contract and the discipline used elsewhere in
the module). One-line change; aligns the implementation with its docstring.

---

### ENG-703 (Minor) — Profile JSON can emit non-standard `Infinity`/`NaN` tokens, which the strict Rust engine will reject

**Category:** Correctness / Interop / Data provenance

**Evidence:** `src/kimcad/printproof3d.py:147-199`. `printer_profile`/`material_profile` cast
config values to `float` and hand them to `json.dumps` at `printproof3d.py:78-79`. Python's
`json.dumps` defaults to `allow_nan=True`, so a `NaN`/`inf` build-volume, nozzle, or temp value
serializes to the literal token `Infinity`/`NaN` — valid for Python's own `json.loads` but invalid
per RFC 8259 and rejected by strict parsers, including Rust's `serde_json`.

I confirmed `json.dumps(printer_profile(Printer(..., build_volume=(nan,256,256), ...)))` succeeds
and embeds `NaN` rather than raising.

**Why this matters:** If a malformed config ever produced a non-finite geometry value, KimCad would
hand PrintProof3D a JSON document its parser refuses. This degrades cleanly (the engine writes no
report or an unparseable one → `validate_model` returns `None` → gate-only readiness), so it is
**not** a never-raises hole — but the engine appears "broken/absent" for a reason that's actually a
KimCad-side serialization quirk, which is a confusing failure to diagnose.

**Why it's only Minor:** Config values reaching here are already `float()`-coerced from validated
config; a non-finite value would require an already-malformed `default.yaml`/`local.yaml`. Exposure
is low and the degrade is safe.

**Fix path:** Pass `allow_nan=False` to the two `json.dumps` calls that build engine profiles
(`printproof3d.py:78-79`). With `allow_nan=False`, a non-finite value raises `ValueError` — which is
already caught by the surrounding `except (..., ValueError, ...)` at `printproof3d.py:80-81` and
degrades to `None`. This turns a silent invalid-JSON handoff into the existing clean degrade path.
Optionally clamp/validate non-finite geometry at config load and warn.

---

### ENG-704 (Minor) — `_record_history` stamps a UTC timestamp but the store / comparison never use it for recency or de-duplication

**Category:** Architecture / Data

**Evidence:** `pipeline.py:555` records `created_at=datetime.now(timezone.utc).isoformat()`, and
`PrintRecord.created_at` is loaded (`history.py:96`), but nothing reads it: `_MAX_RECORDS` trimming
is purely positional (`history.py:109`), and `compare_phrase` ignores time entirely
(`history.py:41-66`). There is also no de-duplication, so a live-slider design that the user
submits as a *fresh* prompt repeatedly, or a CI/benchmark loop, inflates the comparison pool with
near-identical parts and skews "stronger than N of your M."

**Why this matters:** The comparison can drift from "your meaningfully different past parts" toward
"your last M submissions," and the stored timestamp implies a recency capability the product
doesn't actually deliver. This is a mild honesty/quality gap in the headline feature, not a
correctness bug.

**Severity rationale:** Minor — the comparison stays factual and bounded; this is about signal
quality and an unused field, not a failure.

**Fix path:** Either (a) use `created_at` to bound the comparison window (e.g. last 90 days /
last N) so the line reflects recent work, or (b) drop the field if recency isn't a product goal.
If keeping it, consider light de-duplication (same type + same rounded `max_dim_mm` + same
material within a short window) so a repeated identical design doesn't multiply in the pool.

---

### ENG-705 (Nit) — `assess_readiness` and `printproof3d_binary()` sit just outside `_compute_readiness`'s inner try

**Category:** Robustness / Defense-in-depth

**Evidence:** `pipeline.py:491-521`. The `try/except` guards only the engine subprocess block
(`pipeline.py:508-518`). `binary = self.config.printproof3d_binary()` (line 506) and the final
`assess_readiness(...)` (line 519) are outside it, and `_compute_readiness` is itself called
outside any try in `_assemble_result` (line 433). I verified both are non-raising in practice
(`assess_readiness` survives degenerate inputs; `printproof3d_binary()` does a `Path.exists()` that
returns False rather than raising on Windows), so there is no live hole.

**Why it's a Nit:** No reachable raise; it's purely a "the guard could hug the whole synthesis"
observation. Tightening it is cheap insurance for a module whose entire reason for existing is
never-breaks-the-build.

**Fix path:** Either widen the existing `try` in `_compute_readiness` to cover `binary = ...` and
the final `assess_readiness` call (returning a minimal safe `MeshReadiness` on the unreachable
raise), or add a unit test asserting `_compute_readiness` never raises on a malformed
gate/mesh_report. Low priority.

---

### ENG-706 (Nit) — `_subprocess_runner` discards captured stdout/stderr; an engine failure is undiagnosable

**Category:** Hygiene / Observability

**Evidence:** `printproof3d.py:48` — `subprocess.run(argv, timeout=timeout_s,
capture_output=True, check=False)` captures stdout/stderr and then drops the `CompletedProcess`.
When the engine runs but writes no report (or a bad one), the wrapper returns `None` with no trace
of *why* (the engine's own error text is gone).

**Why it's a Nit:** Correct for the never-raises contract and fine for users; only an operator
debugging a wired-up engine would miss it. PrintProof3D is off by default, so exposure is minimal.

**Fix path:** When the report is missing/unparseable, log the captured `stderr` (truncated) at
debug level before returning `None`. Keeps the degrade behavior; adds a breadcrumb.

---

### ENG-707 (Nit) — `default.yaml` ships a `printproof3d` binary path that doesn't exist on disk

**Category:** Hygiene / Config clarity

**Evidence:** `config/default.yaml:14` sets `printproof3d: tools/printproof3d/printproof3d.exe`.
`printproof3d_binary()` returns `None` when the file is absent (`config.py:121-126`), so the engine
is correctly off by default — this is intended and **not** a defect. The nit: a populated-looking
path reads as "configured" to someone scanning the YAML, when the actual on/off switch is file
presence. The adjacent comment explains it, but the value still invites confusion.

**Fix path:** Consider leaving the key commented-out (like the `paths.history` block right below it
at `default.yaml:16-21`) so "configured" and "present" mean the same thing, with the example path
in the comment. Purely cosmetic.

---

## Invariant verification summary (what I checked and the result)

| Invariant | Result | Evidence |
|-----------|--------|----------|
| 1. Never-breaks-the-build (any reachable raise into a build) | **HOLDS** | `validate_model` never raises (every degrade → `None`), verified across no-binary / no-report / raising-runner / unparseable / profile-error. `assess_readiness` never raises on degenerate inputs (probed). `_record_history` + `_apply_history_comparison` wrap in `except Exception`. Only Nit ENG-705 (guard could hug more) and Minor ENG-702 (narrow catch, masked by caller). |
| 2. Slice gate unchanged + readiness advisory | **HOLDS** | Gate-FAIL→no-slice at `pipeline.py:443` reads `gate.status`, not readiness; readiness only attached to the report. |
| 2. PrintProof3D injection-safe | **HOLDS** | Binary from config only; argv list; `shell` False; `check=False` intentional; report-file (not exit code) is source of truth. |
| 3. Honesty of attribution / confidence / score (worst-of-two) | **HOLDS** | `smart_mesh.py:152-171,198-214`; pinned by `test_smart_mesh.py:113-131`. |
| 4. Privacy / local-first / no egress | **HOLDS** | Coarse per-user JSON at `~/.kimcad/`, outside repo; no network in scope. |
| 5. Concurrency / temp-dir + history read-modify-write | **VIOLATED (Major ENG-701)** for the history write under the threaded server. Temp-dir usage in `validate_model` / `_compute_readiness` is fine (unique `TemporaryDirectory` per call). |

## What I could not check

- **No real PrintProof3D binary** is present (off by default), so the wrapper was exercised only
  against injected/faked runners and canned reports — correct per the audit altitude (software-
  complete, engine optional). The JSON contract is validated against the schema-shaped `_CANNED`
  fixture and the required-fields tests, not the live Rust engine.
- **No real hardware / no LLM exercised** — out of altitude per the brief; not flagged.
- **The `Infinity`/`NaN` rejection by the Rust parser (ENG-703)** is inferred from `serde_json`'s
  RFC-8259 strictness, not observed against the actual engine.
