# Runtime QA Deep-Dive — KimCad (Stage-4 gate)

**Audit date:** 2026-06-01
**Role:** QA Engineer
**Scope audited:** The running local web server (`kimcad web --demo`) — HTTP layer only: SPA shell + static assets, the design/mesh/slice/gcode/send API, connector status, and the printability-gate safety guards. The browser UI/UX is the UI/UX role's surface (port 8842); I drove the wire on port 8843 with `urllib` + a raw socket.
**Environment:** Windows 11, Python 3.14.3 venv (`.venv/Scripts/python.exe`), `python -m kimcad.cli web --demo --port 8843`, server `BaseHTTP/0.6`, branch `stage-4-react-spa-shell` @ `c65a42d`. Default printer `bambu_p2s`, default material `pla`, default connector `mock`.
**Auditor posture:** Adversarial

---

## TL;DR

The running product does what it claims and survived the adversarial battery cleanly. The full flow works end to end on the live server: prompt → gate-PASS design with real geometry → STL mesh download → a *real* OrcaSlicer slice (78,127-line G-code, valid time/filament estimate, correct machine/process/filament profiles) → downloadable 3MF (valid PK-zip, correct `Content-Disposition`) → send to the mock loopback connector (honestly flagged `simulated:true`). The headline safety property holds on the wire: a gate-FAILED part (verified live via an injected dim-mismatch pipeline) is refused server-side by both `/api/slice` (`reason:gate_failed`, no G-code produced) and `/api/send` — a direct API client cannot dispatch a gate-rejected part. No 5xx, no stack-trace leak, no traversal bypass, and no credential leak surfaced anywhere. I found **zero Blocker/Critical/Major** issues. The only items are one Minor HTTP-contract deviation (HEAD returns 405) and three Nits.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 1 |
| Nit | 3 |

## What's working

- **End-to-end design→slice→download→send, live over HTTP.** `POST /api/design {"prompt":"a box"}` → 200 with `status:completed`, `has_mesh:true`, `gate_status:pass`, and a full per-axis dims report. `GET /api/mesh/<id>` → 200 `model/stl` (binary STL, 1284 bytes). `POST /api/slice/<id> {"printer":"bambu_p2s","material":"pla"}` → 200 `sliced:true`, real OrcaSlicer output (`gcode_lines:78127`, `estimate:"~50m 20s, 200 layers, 33.63 cm3 filament"`, profiles `Bambu Lab P2S 0.4 nozzle` / `0.20mm Standard @BBL P2S` / `Bambu PLA Basic @BBL P2S`). `GET /api/gcode/<id>` → 200 `model/3mf`, `Content-Disposition: attachment; filename="part_bambu_p2s_pla.gcode.3mf"`, valid `PK\x03\x04` zip header. `POST /api/send/<id> {"connector":"mock"}` → 200 `sent:true, simulated:true, job_id:"mock-1", state:queued, printer_state:printing`.
- **The gate-fail safety guard works on the running server**, not just in unit tests. With an injected pipeline (plan claims 50 mm, render is 20 mm → dim mismatch → gate FAIL) driven over a real socket: `/api/slice` returned `{"sliced":false,"reason":"gate_failed"}` with no `gcode_url`, and `/api/send` refused (no G-code exists to send). The belt-and-suspenders `gate_status_by_rid == "fail"` check in `_handle_send` (webapp.py:538) backstops even a hypothetical slipped-through G-code.
- **Path-traversal defense is airtight.** Every probe against `/assets/` returned 404: `../x`, `..%2fx`, `..%5cx`, `%2e%2e/x`, `..%2f..%2fwebapp.py`, a raw-backslash `..\x`, a nested `sub/x.js`, and a bare `/assets/`. Same for `/vendor/` (`../webapp.py`, `..\webapp.py`, `/vendor/` all 404). The guard rejects any `/`, `\`, or `..` segment before touching the filesystem (webapp.py:408-414, 394-396).
- **Clean 4xx on every malformed input — no 5xx, no traceback.** Non-string prompt (int/list) → 400 "Please describe the part you want."; non-object JSON body (list/scalar/null) → 400 "invalid request body"; malformed JSON → 400; negative/garbage `Content-Length` → 400; oversized body (>1 MiB) → 413 "Request body too large." (verified at the wire: full 413 response delivered, 195 bytes); non-numeric slice/send/mesh/gcode id → 404; unknown printer/material → 400 "Unknown printer or material: 'nope'"; unknown routes → 404.
- **`/api/connector-status/<name>` never 5xxes and never leaks a credential.** Valid, unknown, traversal-shaped (`../../passwd`), and markup-shaped (`<script>...`) names all returned 200 with a typed `reason` and a plain-English `note`. The un-set OctoPrint key surfaces as `reason:config`, note "needs an API key that isn't set up yet" — the key value is never echoed (config uses `api_key_env`, never an inline secret). Reflected names are returned as JSON string values under `Content-Type: application/json` (inert in a browser), not HTML.
- **Method discipline.** PUT/DELETE/PATCH/OPTIONS → 405 with `Allow: GET, POST` and `Content-Length: 0` (webapp.py:308-316), instead of the stdlib 501.
- **Slice idempotency / default-fallback.** A slice with an empty or missing body falls back to the configured default printer+material (bambu_p2s/pla) and an identical re-confirm returns the cached slice (same `gcode_lines`) rather than re-running the multi-minute slicer.
- **Latency is excellent for a local tool.** Static + read endpoints p50 ≈ 0.9–1.7 ms; demo design (render+gate+orient, no LLM) p50 ≈ 135 ms.

## What couldn't be assessed

- **Real-LLM design path.** I ran `--demo` (DemoProvider yields a fixed gate-PASS box) per scope; the live CPU-bound model path was out of scope for this gate.
- **Real printer hardware / real send.** Only the `mock` loopback connector is exercisable on this box; OctoPrint has no key set. Real-hardware send is a Stage-10 / post-release concern per the roadmap.
- **Browser-side behavior** (rendering, console health, XSS execution of reflected connector names, SPA error states) — that's the UI/UX role's surface on port 8842. I confirmed the API returns reflected input as inert JSON, but whether the SPA renders it as text vs. `innerHTML` is a frontend question for that role.
- **Concurrency at scale.** I confirmed the slice path serializes under `slice_lock`; I did not stress it with many concurrent real slices (each takes minutes).

---

## Product shape

KimCad's running surface here is a dependency-free `http.server` over the existing pipeline: the browser POSTs a prompt, the same `Pipeline` the CLI uses renders/gates/orients a part, and the result comes back as JSON the SPA renders, with separate confirm-gated endpoints to slice to G-code and send to a printer. Because there is no web framework and no auth (a single-user localhost tool), QA focused on (1) the API contract and status-code correctness, (2) the printability-gate safety guards that must hold server-side regardless of what the UI hides, (3) path-traversal on the two static roots, and (4) error-path hygiene (no 5xx / no traceback / no credential leak).

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Serve SPA shell (`GET /`, `/index.html`) | Pass | — |
| Serve built assets (`kimcad.js`, `index.css`, `Workspace.js`, woff2 font) | Pass | QA-002 (Nit), QA-003 (Nit) |
| Design a part (`POST /api/design`) → mesh (`GET /api/mesh/<id>`) | Pass | — |
| Slice (`POST /api/slice/<id>`) → download G-code (`GET /api/gcode/<id>`) | Pass | — |
| Send sliced part to mock connector (`POST /api/send/<id>`) | Pass | — |
| Options / connectors / connector-status reads | Pass | — |
| Gate-FAILED part is refused by slice + send | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| `/assets/` and `/vendor/` traversal (10 encodings incl. `%2e%2e`, `%2f`, `%5c`, raw `\`) | All 404 — no bypass | — |
| Non-string prompt (int, list) | 400 plain-English | — |
| Non-object JSON body (list / null / number) | 400 "invalid request body" | — |
| Malformed JSON / empty body | 400 | — |
| Oversized body (>1 MiB) | 413, full response delivered at the wire | QA-004 (Nit) |
| Negative / garbage `Content-Length` | 400 | — |
| Non-numeric & unknown ids on slice/send/mesh/gcode | 404 | — |
| Unknown printer / material on slice | 400 typed | — |
| Gate-FAILED part → slice / send (injected dim-mismatch pipeline, live socket) | Both refused, `reason:gate_failed`, no G-code | — |
| Connector-status with traversal/markup/unicode names | 200 typed, no 5xx, no leak | — |
| Disallowed verbs (PUT/DELETE/PATCH/OPTIONS) | 405 + `Allow` | — |
| HEAD on a GET resource | 405 (should be 200/headers) | QA-001 (Minor) |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Browser / Console / Install

### [QA-001] — Minor — API — `HEAD` requests are rejected with 405 instead of being treated as a header-only GET

**Evidence**
1. With the server running, `HEAD /` returns `405 Method Not Allowed` with `Allow: GET, POST`.
   - Repro: `urllib` Request with `method="HEAD"` to `http://127.0.0.1:8843/` → status 405.
2. Cause: `do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _method_not_allowed` (webapp.py:316) lumps HEAD in with the genuinely-unsupported verbs.
3. RFC 9110 §9.3.2: a server that supports GET on a resource SHOULD support HEAD on it, returning the same headers with no body. `/`, `/assets/*`, `/api/mesh/*`, `/api/gcode/*` all support GET.

Observed: `405`. Expected: `200` with the same headers GET would send and an empty body (or, minimally, HEAD not advertised as disallowed).

**Why this matters**
Low impact for the current single-user browser SPA (browsers don't HEAD these). It bites generic HTTP tooling: a `curl -I`, a link-checker, a download manager probing size before fetch, or a future health-check that uses HEAD will get a 405 and may treat the endpoint as broken. It's a small honesty gap in the HTTP contract.

**Blast radius**
- Related endpoints/flows: all GET routes (`/`, `/assets/`, `/vendor/`, `/api/mesh`, `/api/gcode`, `/api/options`, `/api/connectors`, `/api/connector-status`).
- Tests to update: the method-not-allowed test would need to drop HEAD from the 405 set and add a HEAD-returns-headers assertion.
- Related findings: none.
- Migration: none (additive).

**Fix path**
Implement `do_HEAD` to dispatch through the GET routing but suppress the body (e.g. a flag on `_send`/`_json` that writes headers only, or override `BaseHTTPRequestHandler` to run `do_GET` with `wfile` writes guarded). Keep PUT/DELETE/PATCH/OPTIONS on the 405 path. If HEAD support is a deliberate non-goal for a localhost tool, document it and leave it — but then `Allow` should not imply the resource is GET-only when HEAD is also reasonable. Recommend implementing HEAD; it's a few lines and removes a contract wart.

---

### [QA-002] — Nit — Performance — Static assets are read from disk into memory on every request (no caching headers)

**Evidence**
1. `_serve_asset` / `_serve_vendor` call `path.read_bytes()` on each request (webapp.py:402, 416); the index HTML is cached (`index_html` read once at handler build, webapp.py:279) but the JS/CSS/font assets are not.
2. No `Cache-Control`, `ETag`, or `Last-Modified` header is sent, so a browser re-fetches `Workspace.js` (533 KB) and `three.min.js` (603 KB) on every page load.
3. Measured cost is trivial on localhost: `GET /assets/Workspace.js` p50 ≈ 1.7 ms.

**Why this matters**
Negligible for a single local user on loopback. Flagged only for completeness: a disk read + full re-transfer of ~1.1 MB of unchanging vendor JS on every reload is wasteful, and the absence of cache validators means the browser can't 304. Not worth blocking Stage 4.

**Fix path**
Optional: add `Cache-Control: public, max-age=...` (or an ETag from file mtime/size) on `/assets/` and `/vendor/` responses, and/or read the immutable vendor/asset bytes once into memory at handler-build time like `index_html`. Defer unless asset count grows.

---

### [QA-003] — Nit — Flow — Orphaned per-design output dirs accumulate under `output/web/` across server restarts

**Evidence**
1. After this session, `output/web/` contains rid dirs `1`–`11+`, several dated 2026-05-30 from prior runs.
2. The registry is in-memory only and the id counter (`itertools.count(1)`) resets to 1 on each restart; `_evict` (webapp.py:289) only removes dirs for ids evicted *during a session* (past the `MAX_REGISTRY=50` cap). On restart, old dirs are never reclaimed, and a fresh run's `1` collides with a stale `1` dir (new mesh overwrites inside it, but stale siblings linger).
3. `output/` is gitignored (`.gitignore:17`), so nothing leaks into version control.

**Why this matters**
Cosmetic/tidiness for a local tool. Disk growth is bounded within a session by the cap, but unbounded across many restarts. No correctness or security impact (gitignored, local-only).

**Fix path**
Optional: clear `web_root` on `serve()` startup, or persist+reuse the counter, or namespace each server run under a timestamped subdir. Low priority.

---

### [QA-004] — Nit — API — 413 response triggers a client-side connection-abort on HTTP/1.1 keep-alive clients

**Evidence**
1. `POST /api/design` with a >1 MiB body: at the wire (raw socket), the server sends a complete, well-formed `HTTP/1.0 413 Content Too Large` with `Content-Type: application/json`, `Content-Length: 36`, body `{"error": "Request body too large."}` (195 bytes total received) — correct.
2. A keep-alive `http.client` (`urllib`) client, however, raises `ConnectionAbortedError [WinError 10053]` when reading the 413 body, because the server responds and closes (`Connection: close`, HTTP/1.0) while a large request body is still unsent (TCP RST on the half-written upload).
3. Root cause is the well-known "respond-before-draining-the-request-body" pattern plus the stdlib default `protocol_version = "HTTP/1.0"` (no keep-alive). The status code is delivered; only a client that needs to read the *body* after sending a large upload can hit the abort.

**Why this matters**
Very low impact in practice: the browser SPA caps prompt size client-side and never POSTs a megabyte, and the 413 status itself is correctly delivered. It only bites a non-browser client that streams a large body and then tries to read the JSON error body. It is a correct, fail-closed rejection — just not a graceful one for the body read.

**Fix path**
Optional: after deciding to 413, drain a bounded amount of the remaining request body before closing (or send `Connection: close` and accept the abort as benign). The existing test `test_oversize_content_length_rejected_with_413` deliberately sends *no* body and so doesn't hit this; that's why it's green. Defer — the contract (reject oversized) is satisfied.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| `GET /` (SPA shell) p50 | 1.2 ms | — | pass |
| `GET /assets/Workspace.js` (533 KB) p50 | 1.7 ms | — | pass |
| `GET /api/options` p50 | 1.2 ms | — | pass |
| `GET /api/connector-status/mock` p50 | 0.9 ms | — | pass |
| `POST /api/design` (demo, render+gate+orient) p50 | 135 ms | <1 s for local | pass |
| Real OrcaSlicer slice | minutes (CPU-bound) | n/a — confirm-gated, cached, serialized | expected |
| Client bundle (`kimcad.js` + `Workspace.js`) | 148 KB + 533 KB | — | note (QA-002) |

(LCP/CLS/INP are browser metrics owned by the UI/UX role.)

## Security / privacy snapshot

- **Path traversal:** no bypass on `/assets/` or `/vendor/` across 10 encodings. The guard rejects `/`, `\`, `..` before any filesystem access.
- **Gate bypass:** none. A gate-FAILED part cannot be sliced or sent via the API (verified live), with a server-side belt-and-suspenders check in `_handle_send`.
- **Credential exposure:** none observed. Connector config uses `api_key_env` (env-var indirection); no key is inlined in config or echoed in any response. The "no API key set up" path is a typed status, never a 5xx.
- **Information disclosure:** no stack traces leak. The two last-resort `except Exception` handlers in `_handle_design`/`_handle_slice`/`_handle_send` return `{"error":"<ClassName>: <message>"}` (class+message only, no traceback) — and I could not trigger any of them with the adversarial battery; all my malformed inputs were caught by the typed guards first.
- **No auth surface by design** (localhost single-user tool). No CORS headers are emitted; same-origin SPA only. The module scripts carry `crossorigin` in the HTML, which is benign for same-origin.
- **Reflected input:** connector-status echoes the requested name into a JSON string under `application/json` (browser-inert). Whether the SPA renders it safely is a UI/UX-role question.

## Console and log observations

Server-side logging is intentionally silenced (`log_message` is a no-op, webapp.py:305), so the server console stayed clean throughout. No unhandled exceptions surfaced in the background process during the full battery (design, slice, send, ~40 adversarial probes, gate-fail injection). Browser console health is the UI/UX role's surface and was not assessed here.

## Patterns and systemic observations

- **Defense-in-depth is consistent.** The gate guard appears at both `/api/slice` and `/api/send`, fail-closed (an absent report defaults `gate_status` to `"fail"`, webapp.py:612). The traversal guard is identical on both static roots. The body-size and JSON-shape guards are centralized in `_read_json_body`. This is the right structure: a single behavior, applied uniformly, with the safety check living server-side rather than relying on the UI hiding a control.
- **Error responses are uniformly plain-English JSON** ("Design the part first, then send it to a printer.", "No connector chosen.", "Please describe the part you want."), which matches the product's voice and gives a direct-API consumer a usable next step.
- **The one HTTP-contract wart is HEAD (QA-001).** Everything else in the status-code matrix is correct and deliberate (405 not 501; 413 not 400/500; 400 vs 404 vs 200-soft-failure all chosen intentionally with inline rationale comments).
- I corroborated the live findings against the offline suite: `pytest tests/test_webapp.py` → **40 passed**, including the live design→slice→download→send integration test.

## Appendix: environments and artifacts

- **Server:** `python -m kimcad.cli web --demo --port 8843`, bound `127.0.0.1`, `BaseHTTP/0.6 Python/3.14.3`, HTTP/1.0.
- **OS:** Windows 11 Pro 26200. **venv:** `C:\Users\scott\dev\kimcad\.venv\Scripts\python.exe` (Python 3.14.3).
- **Repo:** branch `stage-4-react-spa-shell` @ `c65a42d`.
- **Tools:** `urllib.request` (method/header/body control), a raw `socket` capture for the wire-level 413, and an injected-pipeline harness (built from the repo's own `conftest` `FakeProvider`/`make_plan`/`box_renderer`) served via a real `ThreadingHTTPServer` to produce and probe a gate-FAILED part. No browser used (UI/UX role's surface). Probe scripts were temporary and removed after the run.
- **Cleanup:** background server stopped (port 8843 confirmed free); temporary probe files deleted.
