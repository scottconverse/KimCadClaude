# QA Engineer Deep-Dive — KimCad Stage 8.5 (Usability) Stage Gate

**Date:** 2026-06-05
**Branch / head:** `stage-8.5-usability` @ `95b25e0`
**Reviewer:** QA Engineer (audit-team, 5-role)
**Scope:** Adversarial / edge / error **runtime** behavior across layers (API, CLI, web) — the lane
the wiring-audit deliberately did not exhaust. Audit-only: no product source modified.
**Builds on:** `wiring-audit-stage-8.5-2026-06-05.md` (PASS 0/0/0/0), which proved the happy-path web
flows are genuinely wired + persisted. This report pushes the *unhappy* paths.

## How this differs from the wiring-audit
The wiring-audit drove the **demo** SPA in a browser and proved every control it could reach is
bound to real backend state. The demo provider, however, returns `object_type:"box"` with a plan
that always **passes** the printability gate — so the wiring-audit never exercised the safety-critical
**refusal** paths (gate-failed slice/send), the malformed-input error contract, or concurrency. This
deep-dive does, including a purpose-built live HTTP harness that forces a gate **failure** over a real
socket. I drove ~75 adversarial requests against a live `kimcad web --demo` server (port 8770) plus a
second in-process server wired to a gate-failing provider, and ran the CLI's error/exit-code paths.

## Severity rollup (QA lane)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 2  (QA-001, QA-002)
- Nit: 1   (QA-003)
- **Total: 3** — all low-severity. No defect threatens the gate.

---

## What's working (credit where due — verified by running, not by reading)

Everything below was driven live at `95b25e0` and behaved correctly. This is a genuinely hardened
runtime; the adversarial sweep found no way to crash it, leak a stack, escape the sandbox, or
dispatch an unsafe part.

**Error contract (uniform, actionable, no dead ends — spec section 5.7):**
- Malformed JSON body returns `400 {"error":"Request body isn't valid JSON."}`
- Non-object JSON (array / `null` / scalar) returns `400 {"error":"Request body must be a JSON object."}`
  — this is the exact crash the code's QA-001 comment guards against (a list/scalar would otherwise
  `AttributeError` on `.get`), and it holds at runtime.
- Empty / missing / wrong-typed `prompt` returns `400 {"error":"Please describe the part you want."}`
- Oversized body (over 1 MiB) returns `413 {"error":"Request body too large."}` AND the server sets
  `close_connection` so it does not drain a hostile upload (QA-004). It correctly rejects on a
  **spoofed** large `Content-Length` (declared 9999999, tiny body) too.
- Malformed `Content-Length` header returns a clean `400`, not an `int()` crash on the worker thread.
- Every error body is the app's JSON shape with a plain-English, actionable message — no blank
  bodies, no HTML error pages, no stack traces.

**Safety invariants (the load-bearing ones) — proven at RUNTIME:**
- **A gate-FAILED part cannot be sliced or sent.** Forced a real dimensional-mismatch gate failure
  (plan 50 mm, render 20 mm) over a live HTTP socket: `POST /api/slice/<id>` returned
  `200 {"sliced":false,"reason":"gate_failed", note:"...download the model to inspect, but it can't
  be sliced or sent to a printer."}` with **no `gcode_url`** — so no G-code ever exists to send.
  `POST /api/send/<id>` then returned `404 "Slice the part first..."`. The CLI mirrors this
  (`--send` on a gate-failed part refuses; tests `test_cli.py::test_gate_failed_part_is_never_sent`
  and `..._even_with_proceed_anyway` pass at HEAD).
- **Re-rendering into a new shape invalidates the prior slice.** Sliced a part (got `/api/gcode/3`,
  fetched it = 200), then `POST /api/render/3` with `width=120`; the old `/api/gcode/3` immediately
  returned **404**. A stale slice of the previous geometry can never be served, sliced, or sent —
  the exact safety property in the `_handle_render` docstring, confirmed live.
- **The simulated connector is honestly labelled.** `GET /api/connector-status/mock` returns
  `simulated:true`; a real (passing) part **sent** to `mock` returns `200 {"sent":true,"simulated":true}`.
  The send-gate also requires an explicit `connector` (no connector returns `400 "No connector chosen."`),
  matching section 5.6 "KimCad never auto-starts a print."
- **No raw traceback can leak.** A grep of `webapp.py` finds zero `traceback`/`format_exc`/
  `print_exc`. The three 5xx-capable paths (`/api/slice`, `/api/render`, `/api/send` last-resort)
  return `{"error":"<ClassName>: <message>"}` — class + message only, never a stack — and I could not
  trigger any of them with adversarial input. The demo server's console stayed clean across all ~75
  requests (no logged exception).

**Path-traversal / sandbox escape — all closed:**
- `GET /api/mesh/..%2f..%2fconfig`, `/api/gcode/...`, `/assets/...`, `/vendor/...`,
  `/api/designs/..%2f..%2f.../thumb|export|reopen` all return `404`, none touch the filesystem
  outside their root (the id is parsed as `int()` for mesh/gcode, and `_safe_id`/separator guards
  reject the rest).
- **Zip-slip is contained at runtime.** Imported a crafted `.kimcad` whose member path was
  `../../evil.json`. Result: `200` (import succeeded) but on-disk **only** `mesh.stl` + `meta.json`
  landed in the new design dir, and a filesystem sweep of the designs root and its parent found
  **no `evil.json` anywhere** — the store reads only the three known names by exact name, never the
  archive's paths. Corrupt/truncated zip, zip missing required members, and a zip with invalid
  `meta.json` all return a clean `400`, never `500`.

**Render endpoint input-hardening (template sliders):**
- `values` not a dict / missing returns `400 "Provide the parameter values to re-render."`
- Non-numeric param value (`"width":"abc"`) silently falls back to the family default
  (`_coerce_finite`), geometry stays valid, `200`.
- Out-of-range (`width:1e9`, `height:-50`) is **clamped** into the family's range (bbox came back
  `[250,60,10]`, the max/min), `200`.
- `"Infinity"` string is caught by the finite check, falls back to default, `200`.
- Unknown param keys dropped. No adversarial render value reached `emit_scad` un-sanitized (TPL-003).

**Concurrency / idempotency:**
- 4 concurrent identical `POST /api/slice/<id>` calls completed in ~1.1 s total (not 4x a full
  slice) and **all returned the same cached G-code file** — the `slice_lock` + `slice_cache` work:
  the slicer ran once, the other three got the cache.

**Slice/save/settings edge cases:**
- Slice with unknown printer/material returns `400 "Unknown printer or material: '...'"` (not a 500).
- Slice with missing printer/material falls back to config defaults and slices (`200`).
- `POST /api/settings` unknown printer/material returns `400 "Unknown printer."/"Unknown material."`
- `POST /api/designs/save` missing/non-numeric id returns `400`; unknown id returns `404`.

**Credential redaction (privacy):** `GET /api/settings` never returns a full key — only
`has_cloud_key` (bool) + `cloud_key_masked`. There is **no** full-key field in the response payload.
(`_mask_key` reveals nothing for an implausibly short value; dots + last 5 otherwise.)

**Other endpoints:** `/api/health` (binaries present), `/api/model-status`
(gemma4:e4b, local, running, present — Ollama was reachable on this machine), `/api/connectors`
(mock=sim, octoprint=real), `/api/design/progress/<unknown>` returns `200 {"phase":null}` (a missing
job never errors the poller), HEAD on `/` returns `200` header-only zero body, unsupported verb
returns `405` with `Allow: GET, HEAD, POST`.

**CLI:** distinct, documented exit codes verified — unknown `--send` connector returns exit 2 with
the configured list; missing subcommand / typo / missing bench prompts / fewer-than-2 bakeoff
backends return exit 2 with plain-English messages, no tracebacks. The model-dependent exit codes
(`gate_failed=5`, `plan_failed=6`, `clarification_needed=3`, `render_failed=4`) are exercised by
`test_cli.py` against the real `main()` entrypoint with deterministic providers — all 15 relevant
tests pass at HEAD.

**Test suite (runtime-relevant):** `tests/test_webapp.py` 102 passed (incl. real OrcaSlicer slices,
~48 s); `tests/test_cli.py` exit/gate/send subset 15 passed.

---

## Findings

### QA-001 (Minor / API): a clamped or coerced slider value returns 200 with corrected geometry but no signal that the input was out of range
**Category:** API
**Evidence:**
1. `POST /api/render/<id>` with `{"values":{"width":1e9,"height":-50}}` returns `200`; response bbox
   is `[250,60,10]` (silently clamped to the family min/max).
2. `POST /api/render/<id>` with `{"values":{"width":"abc"}}` returns `200`; width silently reset to
   the family default. Same for `"Infinity"`.
   Expected (defensible either way): a hint in the payload that one or more values were clamped/
   coerced, so a **non-browser** API consumer (agent / MCP / a future multi-client mode) knows its
   input was not honored verbatim.
**Why it matters:** For the shipped SPA this is a non-issue — the sliders are range-bounded
client-side, so they can only ever POST in-range values, and silent clamping is the *safe* behavior
(it guarantees valid geometry, TPL-003). The gap only bites a programmatic client that sends raw
values and assumes they were applied. Severity is Minor because exposure is low (no such client ships
today) and the failure mode is "geometry is safe but not exactly what I asked," not data loss or a
crash.
**Blast radius:** `coerce_values`/`clamp_values` in `templates.py` are the single chokepoint — a fix
is additive (return a `clamped: [...]` list alongside the payload) and touches only `_handle_render`'s
response shaping; no migration, no stored-data change.
**Fix path:** Consider having `coerce_values` report which keys it clamped/coerced and surface an
`adjusted_params` array in the render payload. Low priority.

### QA-002 (Minor / Flow): the demo provider cannot reach the gate-failed / template-miss UI paths, so those error states are untested *through the running demo*
**Category:** Flow (test-coverage observation, design-intentional)
**Evidence:** `DemoProvider.generate_design_plan` always returns `object_type:"box"` with a
gate-passing bbox. Consequently the demo UI never renders: the gate-FAILED report+refusal, the
"out-of-template → offer the experimental generator" path (section 5.7), or the dimensional-mismatch
warning. The wiring-audit (demo-driven) therefore could not have observed them, and a manual demo
walkthrough cannot either. I reached them only by standing up a **separate** server with a
gate-failing provider.
**Why it matters:** These are exactly the section 5.7 "no dead ends" states that most need real-eyes
QA, and the one runtime fixture that ships for hands-on verification (the demo) structurally hides
them. They *are* covered by unit/integration tests (`test_webapp.py::test_web_refuses_to_slice_a_gate_
failed_part`, `::test_rerender_into_a_gate_failed_shape_blocks_slice_and_send`, and the App component
tests for the experimental-generator offer), so this is a Minor gap in *demo coverage*, not a product
defect.
**Blast radius:** none (no code change implied). It is a recommendation about the demo fixture.
**Fix path:** Consider a `--demo-scenario` flag (or a special prompt token, e.g. a prompt containing
"fail") that makes the demo provider emit a gate-failing or non-template plan, so a human can click
through the refusal + experimental-offer states without an LLM. Optional, low priority.

### QA-003 (Nit / API): two small error-message wording inconsistencies on bad ids
**Category:** API (cosmetic)
**Evidence:**
- `POST /api/slice/abc` (non-numeric) returns `404 "Not found."`, but `POST /api/slice/999999`
  (unknown numeric) returns `404 "Design the part first, then send it to a printer."` Both are 404s;
  the messages differ for what a user experiences identically (a stale/bad id). Minor copy drift, not
  wrong.
- `GET /api/mesh/abc` and `/api/mesh/999999` both return `404 "mesh not found"` (lowercase, terse)
  while most other 404s use sentence-case with a period. Purely stylistic.
**Why it matters:** Negligible — these are developer-facing API responses; the SPA maps statuses, not
raw strings. Flagging once per the framework; not worth a ticket on its own.
**Fix path:** If a copy pass happens, align the bad-id messages. No action otherwise.

---

## What I could not test (honest scope)
- **A real cloud (OpenRouter) round-trip** — requires a user key; I verified only the local routing,
  the masked-key redaction contract, and that cloud-disabled degrades to local. The cloud path is
  unit-tested (`_SettingsAwareProvider`).
- **A real printer send** — no hardware on this machine; I verified the simulated (`mock`) send end
  to end and that a real-but-unconfigured connector (`octoprint`) returns a clean not-ready status
  with an actionable note (`reason:config`, "needs an API key... see the README"), never a 5xx.
- **A true over-64-MiB decompression-bomb import** — I confirmed the bound exists
  (`_MAX_IMPORT_MEMBER`, a per-member inflated-read ceiling) and that corrupt/oversized-declared and
  missing-member archives are cleanly rejected; I did not synthesize a multi-GB-inflating member to
  trip the ceiling live.
- **Browser keyboard shortcuts** — out of my lane (the wiring-audit noted the isolated-world harness
  limit; they are unit-tested).
- **Real-hardware print validation** — explicitly a post-release gate per spec section 4.3, not a
  Stage 8.5 item.

## Verdict
**QA lane: PASS.** Zero Blocker/Critical/Major. The Stage 8.5 runtime is adversarially robust: a
uniform actionable error contract, no traceback leakage, traversal and zip-slip closed, the
gate-failed slice/send refusal and the re-render slice-invalidation both proven over live HTTP, honest
simulated-connector labelling, and a safe input-coercion chokepoint for the live sliders. The three
findings are all low-severity (2 Minor + 1 Nit) and none blocks the gate. Recommend proceeding;
optionally fold the two Minors into a future polish pass.
