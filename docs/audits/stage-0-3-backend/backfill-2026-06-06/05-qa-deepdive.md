# QA Engineer Deep-Dive — KimCad backend foundation (Stages 0–3)

**Audit type:** `audit-team` QA role (RUNTIME behavior), backfill on current code.
**Branch:** `stage-0-7-audit-backfill` @ `a83024d`
**Date:** 2026-06-06
**Environment:** Windows 11 Pro (26200), Python 3.14.3 (`.venv`), Ollama up with `gemma4:e4b` (9.6 GB),
OpenSCAD + OrcaSlicer binaries present under `tools/`, demo web server live at `http://127.0.0.1:8765/`.
No `config/local.yaml` (all defaults from `config/default.yaml`).
**Method:** exercised the real CLI end-to-end with the live model + real OpenSCAD + real OrcaSlicer;
drove the `Pipeline`/connector layer directly with stub providers to force the safety-critical
gate-failure paths deterministically; probed the running web API. Evidence (exact stdout + exit codes)
in `qa-evidence/01..15-*.txt`. Scratch driver scripts removed after capture.

This is the QA lane: I trust nothing the code *says* and verify by *running*. Distinct from the Test
Engineer (who audits the suite). For reference, the non-live suite is currently green:
**778 passed, 4 deselected** (`pytest -m "not live"`, 123.7s).

---

## Severity summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 2 |
| Nit      | 2 |
| **Total**| **5** |

**No Blocker or Critical found.** The three safety invariants in scope — (1) a gate-FAILED part is
never sliced-by-default and never *sent*; (2) send refuses without an explicit `confirm=True`; (3) send
refuses anything that isn't a proven motion-bearing G-code 3MF — all held under direct attack. The one
Major is a CLI error-handling gap (raw traceback on a bad `--printer`/`--material`/`--backend`), not a
safety hole.

---

## What's working (credited — I tried to break these and could not)

The safety story is the strongest part of this backend, and it is real at runtime, not just in tests:

- **[stage 1] Design → gate → slice happy path is solid.** A live-model design of a closed box passes
  the gate, exports a watertight hardened STL, and (`--slice`) produces a **real** motion-bearing G-code
  3MF — independently proven: 38,398 G-code lines, `has_motion=True`, real estimate (~23m23s, 125 layers,
  11.63 cm³). Exit 0. (`01-`, `02-`)
- **[stage 1] Gate-FAIL fails closed, by default.** Forced `volume.exceeds` (real 600 mm cube through the
  real renderer + real gate): status `gate_failed`, `sliced=False`, **no G-code on disk**. (`06-`)
- **[stage 1/2] A gate-failed part is NEVER sent — verified through the actual CLI.** Forced a sliceable
  gate failure (`dim.mismatch`: declares 40×30×20, builds 20³ — fits the bed, slices fine). With
  `--proceed-anyway --send mock`, the CLI sliced the part to inspectable G-code **on disk** but printed
  *"Not sending to mock: this part FAILED the printability gate… a gate-failed part is never sent to a
  printer."* Dispatch refused. This is the two-layer defense (inspect-export vs. dispatch) working at the
  real user surface, not a replication. (`07-`, `15-`)
- **[stage 2] The connector confirm-gate is airtight.** `send` requires `confirm` as a keyword and
  requires it to be **exactly `True`** — `confirm=False`, a missing `confirm`, and even a merely-truthy
  `confirm=1` are all refused with `NotConfirmed`, *before* any network call. (`04-`, `11-`)
- **[stage 2] The proven-slice gate rejects every junk input.** With `confirm=True`, send still refuses:
  a non-zip "3MF", a valid zip with no `.gcode` member, a 3MF whose G-code has no motion command, and a
  missing file. Only the real proven 3MF is accepted. (`04-`)
- **[stage 1] Cross-vendor profile safety holds.** Every printer resolves to its **own** vendor's
  machine + filament profiles; an Elegoo PLA slice embeds `;ELEGOO NEPTUNE 4 MAX` in the toolpath (not a
  Bambu header). TPU-on-Elegoo (no configured profile) is a clean *"not available"* — never silently
  mapped to a Bambu TPU profile that would mis-slice. (`12-`, `13-`, `14-`)
- **[stage 3] Hardware/model advisor runs clean.** `kimcad models` correctly probes the box (16-core,
  31 GB RAM, no discrete GPU) and recommends `gemma4:e4b` (installed). An unreachable Ollama URL degrades
  to "pull it first" — no traceback. (`09-`)
- **[stage 3] Connector-status behaves across all three states.** mock = ready/operational/simulated;
  octoprint = not-ready with `reason:"config"` + a plain user note; unknown = `reason:"unknown"`. Same
  over the live HTTP API (`/api/connector-status/<name>`) and the Python layer. (`10-`, live probe)
- **[stage 2/3] A real connector pointed at a dead endpoint degrades cleanly** — `status()` →
  offline (no exception); `send()` → `ConnectorError reason=offline` (no traceback); the confirm gate
  still fires first. (`11-`)
- **Secret hygiene is correct.** API keys are read from env at use-time and attached only as request
  headers — never logged (`read_error_body` explicitly excludes headers). The saved OpenRouter key is
  returned **only masked** (last-5, and only once long enough — short-key guard), never echoed in full.
- **No shell-injection surface.** Zero `shell=True` / `os.system` / `os.popen` in `src/kimcad`; all
  binaries run via `subprocess.run([...])` arg-lists, so prompt content is never shell-interpreted. A
  unicode + special-char + HTML/`%s` prompt built a valid part, exit 0. (`inject2`)
- **CLI input validation mostly fails fast and clean:** unknown `--send` connector (exit 2, plain msg,
  no design run), missing bench prompts file (exit 2), bakeoff with <2 backends (exit 2), bakeoff bad
  backend (exit 2), empty prompt (clean plan_failed, exit 6). (`05a-`, `09-`)

---

## Findings

### QA-301 (Major) — A bad `--printer` / `--material` / `--backend` name dumps a raw traceback (exit 1)

- **Category:** Install / CLI error-handling
- **Stage:** 1 (printer/material), with `--backend` spanning all design/bench/bakeoff verbs

**Evidence** (`08-badprinter-traceback.txt`):
```
$ python -m kimcad.cli design "a box" --out output/qa-audit/err --printer bambu_x9999
Traceback (most recent call last):
  ...
  File ".../kimcad/cli.py", line 170, in _build_pipeline
    printer = config.printer(args.printer)
  File ".../kimcad/config.py", line 171, in printer
    p = self._d["printers"][key]
KeyError: 'bambu_x9999'
EXIT 1
```
`--material unobtanium` and `--backend nope` reproduce identically (different KeyError, same shape).

**Observed:** raw Python traceback, exit code **1**.
**Expected:** a plain-English message naming the bad value and listing valid choices, exit code **2** —
exactly what the CLI module docstring promises ("a bad config… fail with a plain-English message and a
non-zero exit code rather than a traceback") and exactly what the sibling paths already do (unknown
`--send`, unknown bakeoff `--backend`, missing bench file all give clean exit-2 messages).

**Root cause:** `Config.printer()` (config.py:171), `Config.material()` (config.py:194), and
`Config.llm_backend()` (config.py:223) do bare dict `[key]` lookups that raise `KeyError`. The CLI's
top-level handler in `main()` only catches `RuntimeError` (cli.py:463), so `KeyError` escapes to the
interpreter. Note the bakeoff verb *pre-validates* its backend list against the config (cli.py:345-350)
and so is clean — design/bench do not pre-validate printer/material/backend.

**Why this matters:** picking the wrong printer/material by name is one of the most common CLI mistakes
a user makes (typo, or guessing a key like `elegoo` instead of `elegoo_neptune_4_max`). A traceback
reads as a crash, gives no list of valid keys, and returns the wrong exit code (1, not the contract's 2)
— so a wrapping script can't distinguish "bad input" from "internal error." It directly contradicts the
module's own documented error contract.

**Blast radius:**
- Adjacent code: `Config.printer` / `Config.material` / `Config.llm_backend` (config.py:169-234). The
  same bare-`[key]` pattern is in `connector_config` (config.py:211) and `limit` (config.py:250) — audit
  those for the same gap, though they're not reachable from a user-supplied flag today.
- Shared state: the fix is purely additive (raise a typed, friendly error or pre-validate the key against
  `config.raw["printers"|"materials"]` / `llm.backends` in `_cmd_design`/`_cmd_bench`, mirroring the
  bakeoff pre-check) — no data-shape or config change.
- User-facing: a typo'd flag goes from a traceback (exit 1) to a clean message (exit 2). The
  web/MCP layers call these same `Config` methods, so they benefit too.
- Tests to update: none known would break; **add** CLI tests asserting exit 2 + a no-traceback message
  for a bad `--printer`/`--material`/`--backend` (this is also a Test-Engineer gap — there's no test
  covering this user error, which is why it shipped).
- Related findings: none share the root cause.

**Fix path:** Either (a) make `Config.printer/material/llm_backend` raise a `RuntimeError` (already
caught → exit 2) with a message like *"Unknown printer 'bambu_x9999'. Configured printers: bambu_p2s,
bambu_a1, elegoo_neptune_4_max"* — `difflib` is already imported in cli.py for a "did you mean" hint; or
(b) pre-validate the flag value in `_cmd_design`/`_cmd_bench` exactly as bakeoff already does for
`--backends`. (a) is preferred — it fixes the web/MCP callers in one place.

---

### QA-302 (Minor) — Loopback `status()` reports `printing` immediately after a `queued` send

- **Category:** Flow / connector contract
- **Stage:** 2

**Evidence** (`03-design-box-send-mock.txt`):
```
Simulated send to mock (no real printer was used): job mock-1 (queued). ...
  Printer: printing
```

**Observed:** the send returns a `queued` job (progress 0.0), but the immediately-following
`connector.status()` reports the printer as `printing`. **Expected (arguably):** a freshly-queued job
hasn't started; `operational`/`queued` would read more honestly until the first `job_status` poll
advances it.

**Why this matters:** the mock is the connector users try first to "see the flow." A printer that jumps
to "printing" the instant a job is queued is a slightly dishonest demo of the lifecycle the loopback
otherwise models carefully (`queued → printing → done` over polls). This is *by design* — `status()`
keys "busy" off any non-terminal job (printer_connector.py:392-393), and a just-queued job is
non-terminal — but the design conflates "a job exists" with "the head is moving." Low impact (mock only;
no real hardware), hence Minor.

**Blast radius:**
- Adjacent code: `LoopbackConnector.status()` (printer_connector.py:387-399) and the CLI's post-send
  status print (`cli._send_print_job`, cli.py:233-238).
- User-facing: the demo lifecycle reads slightly wrong; no functional consequence.
- Migration: none. Tests to update: any test asserting `status()==operational` right after a queued send
  (none found today).

**Fix path:** treat only `printing`/`paused` jobs as "busy" in `status()`, or leave it and adjust the
CLI copy to say "job queued" rather than implying the printer is actively printing.

---

### QA-303 (Minor) — Readiness card suggests "Slice for <material> on the selected printer's profile" even when that material is not sliceable on that printer

- **Category:** Flow / copy correctness
- **Stage:** 1

**Evidence** (`13-elegoo-tpu-slice.txt`): TPU on the Elegoo (no TPU profile):
```
Note: cannot slice for Elegoo Neptune 4 Max + TPU — material 'tpu' is not available ...
...
  Suggest: Slice for TPU on the selected printer's profile.       <-- contradicts the note above
...
Slice: not sliceable as configured: material 'tpu' is not available on printer 'Elegoo Neptune 4 Max' ...
```

**Observed:** the Smart Mesh readiness card recommends slicing for TPU, while the same report (twice)
states TPU isn't available on this printer. The slice-availability and the readiness recommendation are
computed independently and disagree.

**Why this matters:** mildly confusing self-contradiction in one report — the user is told to do the
exact thing the report just said can't be done. The actual behavior is safe (no slice produced, mesh
exported as fallback, exit 0); only the suggestion copy is wrong. Minor.

**Blast radius:**
- Adjacent code: readiness recommendation generation (`smart_mesh.assess_readiness` /
  `pipeline._compute_readiness`) vs. slice resolution (`slicer.resolve_slice_settings`).
- Migration: none. Tests to update: none known; add an assertion that the "slice for X" suggestion is
  suppressed when `resolve_slice_settings` would raise `OrcaProfileError` for the same printer+material.

**Fix path:** gate the "Slice for <material>…" recommendation on slice availability (catch
`OrcaProfileError` / reuse the same check the report already ran), or reword it generically.

---

### QA-304 (Nit) — Offline connector's developer-facing message leaks the raw OS WinError

- **Category:** Console / copy
- **Stage:** 2

**Evidence** (`11-octoprint-offline.txt`):
```
ConnectorError reason=offline: octoprint unreachable: <urlopen error [WinError 10061] No connection
could be made because the target machine actively refused it>
```
`str(e)` carries the raw `WinError 10061`. This is the **developer-facing** detail; the `user_message`
("could not connect") is the clean one the UI shows, so this is cosmetic — flagged once. Consider
trimming the OS error to a friendly tail in the developer string too.

---

### QA-305 (Nit) — `--proceed-anyway` exit code is 0 for a gate-failed part

- **Category:** CLI / exit codes
- **Stage:** 1

When `--proceed-anyway` is used on a gate-FAILED part, the CLI exits **0** (`15-cli-real-sendgate.txt`)
even though the gate failed and (with `--send`) the dispatch was refused. The default (no
`--proceed-anyway`) correctly exits **5** for a gate fail. Exit 0 here is defensible (the user explicitly
overrode the gate, and the run "completed" what they asked), but a script can no longer tell a clean part
from an overridden-failing one by exit code alone. Preference, not a defect — flagged once. Consider a
distinct non-zero code (or documenting that proceed-anyway always exits 0) if scripts need to branch.

---

## What I could not test (named honestly)

- **A live-model–induced gate FAIL through the unmodified CLI.** With `gemma4:e4b` + the deterministic
  template engine, I could not get the model to *naturally* produce a gate-failing part — the templates
  clamp out-of-range dimensions (a 500×500×400 request clamped to 155³ and *passed*, see
  `05a-`). So the gate-fail safety path was forced via a stub provider on the real `Pipeline` and via the
  real `cli.main()` with the builder monkeypatched (`06-`, `07-`, `15-`). The renderer, gate, slicer, and
  send-gate exercised are all the real ones; only the plan/SCAD source was stubbed to make the failure
  deterministic. I consider the invariant verified, with this caveat stated.
- **Real printer hardware.** Out of scope by design (Stage 10 / Kim's beta). All send testing used the
  loopback mock and a real connector pointed at a closed port. The bundled mock servers
  (`mock_printer`/`mock_moonraker`/`mock_prusalink`) were read but not separately spun up — the loopback
  + dead-endpoint tests cover the confirm-gate and offline-degradation contracts.
- **The full live benchmark / bakeoff runs** (multi-minute, many model calls) — out of scope for a
  backend-foundation QA pass; the verbs' argument validation and fail-fast paths were tested instead.

---

## Verdict

The Stage 0–3 backend foundation is **runtime-sound on every safety-critical invariant in scope** —
zero Blockers, zero Criticals. The fail-closed gate, the explicit-confirm send gate, the proven-slice
gate, and cross-vendor profile isolation all withstood direct attack at the real CLI surface. The single
Major (QA-301) is a polish gap in CLI error-handling — a bad `--printer`/`--material`/`--backend`
crashes with a traceback instead of the clean exit-2 message the code's own contract promises — worth
fixing this sprint because it's a high-frequency user error with an already-proven fix pattern (the
bakeoff verb) sitting right next to it. The two Minors and two Nits are honest-copy / exit-code polish.
