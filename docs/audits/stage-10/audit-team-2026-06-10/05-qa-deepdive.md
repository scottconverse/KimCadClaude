# QA Engineer Deep-Dive — Stage 10 (commit d9495a8)

**Date:** 2026-06-10 · **Role:** Senior QA Engineer (audit-team) · **Scope:** the Stage 10
diff at runtime — the layers the stage-gate walkthrough did NOT reach. The walkthrough
(docs/audits/walkthrough-stage-10-2026-06-10/WALKTHROUGH-REPORT.md) already proved the six
happy/sad journeys; none are repeated here. This pass hunted at the API/protocol/CLI layers:
method contracts, malformed/oversized/concurrent input, typed-reason fidelity against the
README table, registry behavior under parallel load and past eviction, and server-log
discipline under abuse.

**Method:** live servers, real requests. Demo server on **:8732**; REAL-mode server on
**:8733** with an isolated home (`USERPROFILE` → fresh `%TEMP%\kimcad-qa-home`, real Ollama
with both models present — the model-pull POST exercised only as the verified no-op, no
download ever started). Two additional scratch demo servers (**:8735** wrong
`OCTOPRINT_API_KEY`, **:8736** correct key) plus the repo's own `kimcad.mock_printer` on
:5000 to drive the `auth` / `offline` / success reasons over the real OctoPrint REST path —
no real printer exists or was touched. One scratch in-process server (**:8734**) with an
in-memory-only monkeypatched connector to prove the 500-path logging claim. All processes
killed and scratch/temp dirs removed at the end; no product source modified.

Per-slice audit-lites (docs/audits/stage-10/audit-lite-slice-10.1–10.4) were read first;
nothing already found-and-fixed there is re-reported.

---

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---------|----------|-------|-------|-----|
| 0 | 0 | 1 | 5 | 0 |

---

## Findings

### QA-1001 — Major — Console — Every `log_error` in the web server is silenced; the 500 response and troubleshooting.md both point users at a terminal that contains nothing

**Evidence:**
`src/kimcad/webapp.py:762` overrides `log_message` to `pass` ("keep the console quiet").
In the stdlib, `BaseHTTPRequestHandler.log_error` is implemented as
`self.log_message(format, *args)` (verified against the running venv's `http.server`
source), so the override silences **`log_error` too**. Every diagnostic the server tries
to keep — `webapp.py:1417` (`send failed: …`), `:1465`/`:1507` (`vision read failed`),
`:1602` (`design run failed`), `:1964` (`slice failed`), `:2013` (`re-render failed`) —
goes nowhere.

Runtime proof (scratch port 8734, demo mode, connector factory monkeypatched in-memory to
raise `RuntimeError`):

```
send -> 500: {"error": "Something went wrong on the server.
              The terminal running `kimcad web` has the detail."}
stderr captured during the 500: 0 bytes
```

The browser was told the terminal has the detail; the terminal got **zero bytes**. The
0-byte stderr logs of all four long-running audit servers (after ~150 requests of abuse)
confirm the same in normal operation. Two user-facing surfaces repeat the false promise:
the 500 JSON itself (4 occurrences: `webapp.py:1419`, `:1604`, `:1966`, `:2015`) and
`docs/troubleshooting.md:158` — "The terminal running `kimcad web` **always** has the
detailed error".

**Expected:** the deliberate `log_error` calls reach the terminal (request-line noise from
`log_message` can stay suppressed — they are separate hooks).

**Why this matters:** the repo's own error-handling stance is "the browser gets a generic
non-leaking line, the server log gets the detail." Half of that contract is broken: when a
real user hits an unexpected 500 (the exact moment a bug report is born), the detail is
destroyed everywhere — the troubleshooting guide's "send the terminal's last lines" advice
yields an empty paste, and a developer debugging a field report has nothing.

**Blast radius:**
- Adjacent code: all six `log_error` call sites above; any future `log_error` inherits the
  silence. Fix in one place — give `Handler` an explicit `log_error` that writes to
  `sys.stderr` (keep `log_message` quiet as designed).
- User-facing: failure-path messages become honest; no success-path change.
- Docs: troubleshooting.md:158's "always" becomes true again instead of needing rewording.
- Tests to update: none known — no test pins the silence; consider one that asserts a
  synthetic 500 emits a stderr line.
- Related findings: none (the per-slice audit-lites all assumed "goes to the server log"
  worked — e.g. slice-10.3 ENG-002 cites the webapp catch-alls as the safe degradation).

**Fix path:** add to `Handler`:
`def log_error(self, fmt, *args): print("kimcad web: " + (fmt % args), file=sys.stderr)`
(or route to `logging`). One method; verify with the repro above.

---

### QA-1002 — Minor — API — Method-contract asymmetry: POST on two existing GET resources returns 404, and the blanket 405 advertises an `Allow` header that lies per-route

**Evidence (real server :8733, identical on demo):**

```
POST /api/model-pull/progress -> 404 {"error": "Not found."}     (resource exists for GET)
POST /api/designs             -> 404 {"error": "Not found."}     (resource exists for GET)
POST /api/health              -> 405 Allow: GET, HEAD            (the intended contract)
GET  /api/model-pull          -> 404                              (resource exists for POST)
PUT  /api/model-pull          -> 405 Allow: GET, HEAD, POST       (GET on this route 404s)
```

The code's own rule (webapp.py:1090-1091, "QA-002: a POST to an existing GET-only resource
is 405 … a 404 would wrongly imply the resource doesn't exist") is enforced via an
allowlist that omits `/api/model-pull/progress` and `/api/designs` — both newer than the
list. Conversely `do_GET` has no symmetric postonly branch, so `GET /api/model-pull`
404s while `PUT` on the same path 405s with `Allow: GET, HEAD, POST` — an `Allow` header
naming a method the route doesn't accept (`_method_not_allowed`, webapp.py:765-770, is
global, not per-route).

**Expected:** wrong-method on an existing resource → 405 with a truthful per-route `Allow`.

**Why this matters:** integrators (the MCP server, future API consumers) debugging a
wrong-method call get "Not found" for a URL that demonstrably exists, and an `Allow`
header that sends them to a 404. Nobody's data breaks; their afternoon does.

**Blast radius:**
- Adjacent code: the `getonly` list in `do_POST` (webapp.py:1092-1093); `do_GET`'s
  fall-through 404; `_method_not_allowed`'s static `Allow`. Any new GET route added
  without touching the list re-creates the gap — consider deriving both directions from
  one route table.
- Tests to update: `tests/test_webapp.py` pins the QA-002 405 behavior for the older
  routes; add the two missing paths + a GET-on-model-pull pin.
- Related findings: none.

**Fix path:** add the two paths to the getonly 405 list; add a small postonly list
(`/api/model-pull`, …) to `do_GET`/`do_HEAD` returning 405 `Allow: POST`; make
`_method_not_allowed` take the route's real method set (or drop `GET` from the blanket
header only where untrue).

---

### QA-1003 — Minor — API/Protocol — An oversized POST body never receives the documented 413; `/api/model-pull` has no body guard at all

**Evidence:**
- `POST /api/send/3` with a 1.1 MB and a 4 MB JSON body (limit: `MAX_BODY_BYTES` = 1 MiB)
  → the client gets `ConnectionAbortedError (WinError 10053)` on **both** sizes; the 413
  JSON (`webapp.py:1025-1031`) is never observed. The server replies-then-closes while the
  client is still streaming; Windows RSTs the socket and the response is lost.
- `POST /api/model-pull` with a 2 MiB body → same client-side abort, because
  `_handle_model_pull` never calls `_read_json_body` at all — there is no size check, no
  drain, and no read of the body on that route (webapp.py:1132-1188; harmless for request
  parsing only because the server is HTTP/1.0, one request per connection).
- Server health after every oversized hit: `GET /api/health` → 200, zero log noise, no
  traceback — the server itself degrades cleanly.

**Expected:** a misbehaving client gets the typed 413 JSON the code intends (the QA-004
comment at webapp.py:1026-1028 shows the abort risk was seen but believed limited to
still-streaming clients; in practice it eats the response for every oversized body tested).

**Why this matters:** the repo's standard is "clients misbehaving never traceback the
terminal" — held — but the client-side contract half is unmet: an integrator who
accidentally posts a large payload (e.g. a fat history array) gets a bare connection reset
with no status code to branch on, on every body-bearing route.

**Blast radius:**
- Adjacent code: `_read_json_body` (all POST routes), `_read_body_bytes`
  (webapp.py:1862, photo/sketch seeds — same reply-then-close pattern), and
  `_handle_model_pull` (no guard).
- Tests to update: the existing 413 unit tests pass because the test client writes the
  whole body before reading — they can't see this; a socket-level test would.
- Related findings: QA-1002 (same "contracts at the wire" theme).

**Fix path:** drain-with-cap before responding (read and discard up to a few MiB when
`declared > MAX_BODY_BYTES`, then send 413 + close) — that lands the response for
realistic oversizes; route `/api/model-pull` through `_read_json_body` (ignoring the
parsed dict) so it gains the same guard and explicitly documents that the body is ignored.

---

### QA-1004 — Minor — CLI — `--send` fail-fast validates only that the connector *name exists*, not that it's *buildable* — an unconfigured `bambu_p2s`/`octoprint` burns the full multi-minute design before failing

**Evidence:**
- `kimcad design "a tiny test cube" --send nosuchprinter` → instant
  `Unknown connector 'nosuchprinter'. Configured connectors: mock, octoprint, bambu_p2s, bambu_a1`,
  exit code **2**. The typo path is genuinely fast — good.
- Ordering proof: `kimcad design "a tiny test cube" --send bambu_p2s --backend nosuchbackend`
  → `Error: unknown LLM backend 'nosuchbackend'` (exit 2). The connector check passed and
  execution reached pipeline construction — i.e. for `bambu_p2s` (a shipped template with
  no IP) nothing stops the run until the post-design send raises the `config` error.
  `cli.py:286` checks only `args.send not in config.connectors()`; `build_connector`'s
  cheap, network-free config validation (missing IP / serial / access-code env / API-key
  env — `connectors.py:80-91`, `bambu_connector` arm) runs only after design + slice.
- The web layer proves how cheap the up-front check would be: `POST /api/send` to
  `bambu_p2s` returns the typed `config` refusal in milliseconds (see QA-1005 evidence).

**Expected:** the comment's own intent — "validate the connector up front so a typo fails
fast, not after a multi-minute run" — extended to the equally-common config gap. The
README's no-hardware tutorial (`kimcad design … --send octoprint`) makes "forgot to set
`OCTOPRINT_API_KEY`" a first-session path: today that user pays the full CPU-bound
generation (minutes on the target machine) and then reads "Not sent".

**Why this matters:** the shipped config now contains **three** listed-but-unconfigured
connectors (octoprint sans key, both bambu templates), so name-membership is the weakest
possible pre-check exactly when the stage made unconfigured-but-visible the normal state.

**Blast radius:**
- Adjacent code: `cli.py:286-289`. Replace the membership test with
  `build_connector(config, args.send)` in a `try/except ConnectorError` (print
  `e.user_message`, exit 2) — constructors are side-effect-free (no network: verified for
  loopback/octoprint/bambu arms; the bambu arm raises on missing config before importing
  the optional package).
- User-facing: failure arrives in <1 s with the same plain-English message instead of
  after minutes; the success path is unchanged (connector built twice, negligible).
- Tests to update: `tests/test_cli.py`'s unknown-connector case keeps passing; add an
  unconfigured-connector fail-fast case.
- Related findings: none.

---

### QA-1005 — Minor — API/Docs — `gate_failed` is a reason the send/slice API actually returns, but it's missing from README's typed-reason table

**Evidence:** the README table (README.md:313-321) documents
`config / unknown / offline / busy / auth / bad_response / error` as the complete typed
vocabulary "so the UI **and HTTP-API consumers** can branch on *why*". The running API
also returns `"reason": "gate_failed"` — from `POST /api/send/<id>` (webapp.py:1386-1391)
and `POST /api/slice/<id>` (webapp.py:1924-1928; observed live in the walkthrough's
journey 2: `{sliced: false, reason: "gate_failed", …}`). A grep of README and docs/ finds
no occurrence of `gate_failed` anywhere.

**Why this matters:** an HTTP-API consumer coding to the documented vocabulary (the
table's stated purpose) will drop the one reason that encodes the product's central safety
rule into a generic else-branch. The SPA handles it (SendPanel's reason map) — only the
docs lag.

**Blast radius:** doc-only — one table row (note it appears on slice + send and is
KimCad's own refusal, not a connector state). Related findings: none.

---

### QA-1006 — Minor — CLI — Error messages print to stdout, not stderr, so a piped/redirected `kimcad design` captures errors in the report stream

**Evidence:**
```
PS> $o = kimcad design "x" --send nosuch 2>$null         # stderr discarded
STDOUT:[Unknown connector 'nosuch'. Configured connectors: mock, octoprint, ...]
PS> kimcad design "x" --send nosuch 2>&1 1>$null          # stdout discarded
STDERRcount: 0                                            # stderr is empty
```
Exit code 2 in both — the machine contract is right; the stream is not. This is systemic
in `cli.py` (bare `print(...)` for errors throughout — e.g. `:288`, the not-sent path
`:238`), while the file's own QA-005 comment establishes the convention: "Phases go to
**stderr** so **stdout stays clean for the report**." An error is not the report.

**Why this matters:** `kimcad design … --send octoprint > report.txt` silently writes the
failure text into the artifact users will treat as the design report; scripted callers
watching stderr see nothing.

**Blast radius:** `cli.py` error prints (a `_err()` helper + mechanical sweep); tests that
capture stdout for error assertions (`tests/test_cli.py`) will need `capsys` err-side
updates. Related findings: none.

---

## What's working

Credit where due — this surface took a real beating and almost everything held:

- **The fixed-model-list rule holds under abuse.** `POST /api/model-pull` with a body
  naming `evil/13b-malware:latest` (and `models`/`name` variants), with a form-encoded
  content-type, and with no body at all: the body is ignored in every case, the snapshot
  shows only the server's own list, and progress stayed `{running: false, models: {}}`
  throughout. The demo server's typed 400 refusal held with a body present.
- **Model-pull is idempotent under real parallelism.** 12 simultaneous POSTs (threads,
  real server, both models present) → 12 × 200 with **one** identical body
  (`{"status": "ok", "running": false, "models": {}}`); progress unchanged after the
  storm. No double-start, no torn snapshot.
- **`/api/send` input handling is airtight.** Unsliced id → 404 with the actionable
  "Slice the part first…"; non-numeric / float-ish ids → clean 404; missing body → 400
  "No connector chosen."; garbage JSON → 400 "isn't valid JSON"; `[1,2,3]` → 400 "must be
  a JSON object"; numeric/empty/null connector → typed `unknown` / 400. Eight parallel
  sends to `mock` → eight clean 200s, zero corruption.
- **The typed-reason vocabulary is real, not aspirational.** Verified live on the wire:
  `unknown` (typo names), `config` (both bambu templates with the precise per-piece note
  — "no printer address (IP) configured" — and octoprint's missing key), `auth` (wrong
  `OCTOPRINT_API_KEY` against the mock → send `auth` + "rejected the API key", status
  `error` + detail "authentication failed (HTTP 403)" — exactly the README's documented
  split), `offline` (mock killed mid-session → "Is it powered on and connected?"), and
  the full **success path over the real OctoPrint REST** (`sent: true`, job id, live
  `printer_state: printing`). The README table is accurate for everything it lists
  (QA-1005 is an omission, not an error).
- **`/api/connector-status/<name>` never breaks.** Spaces, unicode+emoji, empty name,
  `../../mock` traversal-shaped names, unknown names, query strings: every one a clean
  200 with the uniform `{name, ready, reason, simulated, note}` shape. No 5xx reachable.
- **The registry is solid under load and past eviction.** 16 parallel design+slice runs:
  16 distinct rids, every thread's own mesh/slice/G-code correct, zero anomalies. A
  55-design flood evicted rid 2 in lockstep (gcode 404, mesh 404), and send/slice on the
  evicted id return the actionable 404s, not errors.
- **No traceback ever reached a terminal.** Across ~200 abusive requests on four servers
  (giant bodies, wrong methods, garbage JSON, parallel storms), every server's
  stdout/stderr stayed empty of tracebacks and the servers stayed healthy. (The flip side
  of that silence is QA-1001.)
- **HEAD support is genuine** (200 header-only on GET resources, correct Content-Length),
  and PUT/DELETE/PATCH/OPTIONS get the uniform JSON 405.
- **The CLI front door is honest.** `design --help`'s `--send` text matches the shipped
  config exactly (bambu templates included — the slice-10.3 doc fix landed); `kimcad
  models` reports the real hardware, both installed models with true sizes, and a
  truthful recommendation; unknown-connector exits 2 instantly.

## What I couldn't test (and why)

- **A real model download** — forbidden (multi-GB); exercised only as the verified no-op
  with both models present, plus the demo refusal.
- **A real printer send / Bambu hardware path** — no hardware exists; the Bambu surfaces
  were tested to their config-refusal boundary, and the OctoPrint wire path via the
  repo's mock. `busy` (PrusaLink 409 / Bambu pre-upload) and `bad_response` reasons are
  unit-tested but not reproduced live — driving them needs a connector config edit
  (read-only tree) or hardware.
- **Multi-hour soak / SR-assistive runtime** — out of scope for this pass; the a11y
  static gaps were already covered by the slice audit-lites.

## Cleanup

All five servers (8732, 8733, 8734, 8735, 8736) and the mock printer (5000) killed —
ports verified free; the isolated `USERPROFILE` (`%TEMP%\kimcad-qa-home`) deleted; the
`_qa-scratch/` directory deleted after evidence was excerpted into this report; no
product source touched (`git status --short`: only this audit's report files).
