# Runtime QA Deep-Dive — KimCad 0.9.0b4 (+ restored UI)

**Audit date:** 2026-06-17
**Role:** QA Engineer
**Scope audited:** The **real running product** — HTTP API surface (every endpoint, success + failure + adversarial), one full real end-to-end (design → gate → real OrcaSlicer slice → proven .3mf), and adversarial safety/concurrency edges. Real on-device `qwen2.5:7b` planner, real bundled OrcaSlicer, isolated `KIMCAD_HOME`.
**Environment:** Windows 11; `.venv\Scripts\python.exe -m kimcad.cli web --port 8745` (REAL mode, **not** `--demo`); Ollama `qwen2.5:7b` live; bundled OrcaSlicer at `tools/orcaslicer/orca-slicer.exe`; build `0.9.0b4` @ `356867d`. Client: curl + the project's own `kimcad.slicer.prove_gcode_3mf`.
**Auditor posture:** Adversarial.

---

## TL;DR

The product behaves as claimed under real runtime, and it holds up under deliberate abuse. I ran the full critical path against the **real** model and the **real** slicer and proved the produced `.3mf` carries genuine motion G-code (`has_motion=True`, 21,172 lines, 20 layers). The two safety-critical invariants both held server-side: a **gate-FAILED part cannot be sliced or sent** (refused with `reason:"gate_failed"`, no G-code ever produced), and the **CSRF session-token guard** refuses every tokenless/wrong-token state-changing POST (403). Every error path I could reach returns a clean JSON error with a correct status code — **no 500s, no stack traces, no credential or filesystem-path leaks anywhere**, and the server stderr log is traceback-free across the entire adversarial session. No Blockers, no Criticals. Findings are a small set of Minor/Nit polish items.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **Real end-to-end is real.** A round coaster designed by `qwen2.5:7b` → gate PASS (dims 90×90×4 mm match the prompt) → **real OrcaSlicer** slice → `/api/gcode/2` fetched → `prove_gcode_3mf` confirms **`has_motion=True`, 21,172 lines, 20 layers, 11.3 cm³, 18m 11s**, real Bambu profiles. This is not `--demo`; the slicer ran.
- **Gate-fail enforcement is server-side, not just UI.** A 500 mm cube failed the gate (`volume.exceeds`); `POST /api/slice/<id>` returned `{"sliced": false, "reason": "gate_failed"}`, `GET /api/gcode/<id>` stayed 404 (nothing produced), and `POST /api/send/<id>` was consequently refused. A malicious client cannot bypass the gate by calling the API directly.
- **CSRF guard works.** A per-boot session token is injected into the SPA shell and required on every POST via `X-KimCad-Session`. Tokenless POST → 403 `reason:"session"`; wrong token → 403; constant-time compare. Cross-origin drive-by POSTs to loopback cannot read the same-origin token.
- **Error contract is uniform and clean.** Bad id, non-numeric id, int-overflow id, empty body, malformed JSON, wrong type, path-traversal in ids/asset names — all return clean JSON 4xx with human-readable messages. No tracebacks, no internal class names, no paths.
- **connector-status never 5xx, never leaks.** All 7 connectors + bogus names return 200 with honest "not configured" notes; scanned bodies for `password/token/api_key/secret/path/traceback` → zero hits.
- **Admission cap holds.** 3 concurrent `/api/design` POSTs → 2 ran (200), the 3rd cleanly refused **429** with `reason:"busy"` + `Retry-After`. The server does not stack unbounded heavy pipelines.
- **Idempotent re-slice.** Re-slicing the same (mesh, printer, material) returned **200 in 0.97 s** (cached) vs ~30 s for the first real slice — the OrcaSlicer run is not repeated.
- **Body-size DoS guard.** A >1 MiB body returns a typed **413 "Request body too large."** (not a Windows connection-reset), draining the socket so the client reliably reads the 413.
- **CadQuery STEP path is valid.** `/api/step/2` returns a well-formed `ISO-10303-21` STEP (header + DATA + END-ISO-10303-21).
- **Experimental generator is correctly gated OFF by default** and freeform prompts (dolphin sculpture, twisted vase) did not crash the server — health stayed green throughout.

## What couldn't be assessed

- **A real `send` to hardware.** Only the `mock` connector is configured (no printer on the box), so the actual print-dispatch wire was exercised only at the gated/refused layer, not against a live printer. This matches the walkthrough's note.
- **The experimental LLM-OpenSCAD raw-codegen path in its enabled state.** It's OFF by default; I confirmed the OFF gating and that freeform prompts route gracefully, but I did not toggle `experimental_enabled` on and drive a true no-template raw-codegen slice (would add several minutes of model time; out of the ~10–15 min budget). The deterministic + template + STEP paths are fully proven.
- **Browser-level console/CWV/mobile** — covered by the separate Playwright walkthrough (`docs/audits/walkthrough-b4-2026-06-16/WALKTHROUGH.md`); this pass was the API/runtime layer.

---

## Product shape

KimCad is a single-user, loopback web app (stdlib `http.server`, no framework) that turns a natural-language prompt into a printable part: a local LLM plans geometry, OpenSCAD/CadQuery render it, a printability gate validates it, and the bundled OrcaSlicer produces a real `.3mf` print file. QA therefore focused on the **HTTP API contract** (status-code correctness, error-shape uniformity, no-leak discipline), the **real artifact-producing pipeline** (one proven slice), and **adversarial safety** (gate bypass, CSRF, concurrency, DoS, traversal).

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| design (real qwen2.5:7b) → gate PASS | Pass | — |
| render (re-render by id) | Pass | QA-003 |
| **real OrcaSlicer slice → proven .3mf** | **Pass** | — |
| fetch gcode / mesh / step artifacts | Pass | — |
| idempotent re-slice (cache hit) | Pass | — |
| connectors / connector-status (all 7) | Pass | — |
| settings GET / POST | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Tokenless POST /api/design | 403 `reason:session` (correct) | — |
| Wrong session token | 403 (correct) | — |
| Slice a gate-FAILED part | Refused `sliced:false reason:gate_failed`; no gcode | — |
| Send a gate-failed (unsliced) part | 404 "Slice the part first" | — |
| 3× concurrent /api/design | 2×200 + 1×429 busy (cap holds) | — |
| Body >1 MiB | 413 typed, socket drained | — |
| Path traversal in `/api/mesh`, `/assets`, connector-status | safe 404 / "unknown name" | — |
| Bad/empty/non-numeric/overflow ids (gcode/mesh/step/designs) | clean 404 JSON | — |
| Malformed JSON / wrong-type / empty prompt | clean 400 JSON | — |
| Unknown printer at slice | 400 (not 500) + available list | QA-002 |
| Garbage/negative render params | 400 (not 500) | QA-003 |
| Freeform/no-template prompts, experimental OFF | routed/handled, server survived | — |
| `POST` to a GET-only resource | 405 (when token present) | QA-001 |
| connector-status leak scan (creds/paths) | zero hits | — |

---

## Findings

> **Finding ID prefix:** `QA-`

### [QA-001] — Minor — API — Session-token guard runs before the method check, so `POST` to a GET-only route returns 403 instead of 405

**Evidence**
1. With a session token configured (the real-mode default), `curl -X POST http://localhost:8745/api/health` returns **`403 {"reason":"session"}`**, not the documented `405 Method Not Allowed`.
2. The 405-with-truthful-Allow logic at `webapp.py:1403–1416` is correct, but `do_POST` checks the session token first (`webapp.py:1340`) and short-circuits before reaching the method-guard for any tokenless caller.
3. A tokenless `curl -I` (HEAD) and GET still behave correctly; only the POST-to-GET-only verb mismatch is shadowed.

**Why this matters**
Purely a contract-tidiness issue for an integrator poking the API without a token: they see "bad token" where "wrong method" is the truer signal. No functional or security impact — the guard correctly refusing the unauthenticated POST is the right outcome; only the *status code* is less precise than intended. The SPA always sends the token, so users never see this.

**Blast radius**
- Adjacent code: `do_POST` token guard (`webapp.py:1340`) vs. the GET-only 405 block (`webapp.py:1407–1416`). Same ordering applies to every GET-only route (`/api/options`, `/api/model-status`, `/api/connectors`, etc.).
- Migration: none. Tests asserting 405 on these routes likely run with an empty token (guard off), so they still pass — meaning this divergence is **untested** in the token-on configuration.
- Tests to update: add a token-on case asserting 405 (or accept 403) for POST-to-GET-only.

**Fix path**
Optional: in `do_POST`, evaluate the GET-only/Allow check before the token guard for *known* GET-only paths, OR document that an authn failure (403) legitimately precedes the method check. Low priority; current behavior is defensible.

### [QA-002] — Minor — API — Unknown-printer slice error enumerates the entire printer catalog in the error string

**Evidence**
1. `POST /api/slice/2 {"printer":"NONEXISTENT_PRINTER_XYZ","material":"pla"}` → **400** with body `{"error":"Unknown printer or material: unknown printer 'NONEXISTENT_PRINTER_XYZ'. Available: anycubic_kobra2, anycubic_kobra2_max, ... bambu_p2s, ...creality..."}` — the full ~29-printer catalog inlined.
2. Status code is correct (400, not 500). The leak is only public catalog data (same list `/api/options` serves openly), so it's not a security concern.

**Why this matters**
The verbose error is helpful for a CLI/dev but is a large, unstructured string for an SPA to surface; the available list is already a structured field on `/api/options`. Mildly inconsistent with the otherwise-terse error contract.

**Blast radius**
- Adjacent code: `config.UnknownConfigKey` formatting; `_handle_slice` except branch (`webapp.py:2452–2455`).
- User-facing: an unknown-printer slice is unreachable from the real SPA (the picker only offers valid keys), so this fires only for direct API callers.
- Migration: none.

**Fix path**
Keep the 400; consider trimming the message to the bad key + a pointer to `/api/options`, or move the list to a structured `available` field. Cosmetic.

### [QA-003] — Minor — API — `/api/render/<id>` rejects parameters nested under a `parameters` wrapper with a generic "Provide the parameter values" 400

**Evidence**
1. `POST /api/render/2 {"parameters":{"diameter":-500}}` → **400 "Provide the parameter values to re-render."**
2. Same 400 for `{"parameters":{"nonexistent_param":99999,"diameter":"not-a-number"}}`.
3. The endpoint correctly does **not** 500 on garbage/negative/wrong-type values — it bails to a 400. But the message implies "you sent no values" when values *were* sent (just in a shape the handler didn't accept, or with keys it rejected), which could confuse an integrator about whether the wrapper key or the values are wrong.

**Why this matters**
Defensive behavior is correct (no crash). The diagnostic is just imprecise for a direct API caller. The SPA's live-slider re-render sends the shape the handler expects, so end users are unaffected.

**Blast radius**
- Adjacent code: `_handle_render` body parsing (`webapp.py:2478+`).
- User-facing: none via the SPA slider; affects only hand-rolled API calls.
- Migration: none.

**Fix path**
Distinguish "no parameter values supplied" from "parameter values present but unusable/unknown keys" in the 400 message. Low priority.

### [QA-004] — Nit — Console — Benign "client disconnected mid-response" lines in server stderr

**Evidence**
Server stderr accumulated four `[kimcad] client disconnected mid-response (127.0.0.1)` lines — all from my own curl timeouts during long real-model designs, not from a defect. No tracebacks, no 500s. Noted only for completeness; the logging is actually a *credit* (errors correctly route to stderr per the QA-1001 fix at `webapp.py:803–808`).

### [QA-005] — Nit — API — `POST` to a GET-only route emits a 405 with an empty body (no JSON error envelope) in the token-off path

**Evidence**
The token-off 405 block (`webapp.py:1411–1416`) sends `Allow: GET, HEAD` with `Content-Length: 0` — an empty body, unlike the `_method_not_allowed` helper which returns the JSON `{"error":"Method not allowed."}` envelope. Minor inconsistency in the error-shape contract between the two 405 emitters. Harmless (status + Allow header are correct).

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| Server cold-start to first `/api/health` 200 | ~3–4 s | — | pass (stdlib server) |
| `/api/health`, `/api/options`, `/api/connectors` | <50 ms each | <200 ms | pass |
| Real design (qwen2.5:7b, simple part) | ~40 s | n/a (local LLM) | acceptable; honest in-UI "can take a few minutes" |
| Real OrcaSlicer slice (first) | ~30 s | n/a | acceptable |
| Idempotent re-slice (cache hit) | **0.97 s** | — | excellent (no re-run) |

## Security / privacy snapshot

- **CSRF:** per-boot session token enforced on all POSTs; constant-time compare; tokenless/wrong → 403. Proportionate for a single-user loopback app.
- **IDOR/traversal:** ids are int-parsed or treated as opaque names; `..%2F..%2F` in `/api/mesh`, `/assets`, and `/api/connector-status` all resolve safely to 404 / "unknown name" with no filesystem access.
- **Information leakage:** no stack traces, no internal class names, no credentials, no absolute paths in any error body. connector-status leak-scan across all 7 connectors: zero hits.
- **DoS:** 1 MiB body cap (413, socket drained); design admission cap (429) bounds concurrent heavy pipelines.
- **Gate bypass:** not possible via the API — slice/send are refused server-side for gate-failed parts.

## Console and log observations

Server stderr is **traceback-free** across the full adversarial session (`grep -ciE "traceback|error|exception|500"` → 0). The only lines are benign client-disconnect notices from curl timeouts. Error logging correctly goes to stderr while per-request chatter stays silent.

## Patterns and systemic observations

The error-handling discipline is consistent and mature: every reachable failure resolves to a typed status code with a clean JSON envelope, tiered appropriately (400 client error / 404 missing / 405 method / 413 too-large / 429 busy / 200-with-reason for "valid request, refused outcome" like gate-fail and tool-missing). The 200-with-`reason` pattern for refused-but-valid requests (gate_failed, tool_missing, busy is 429) is a deliberate, well-commented choice. The few Minor findings are all message-precision / contract-tidiness, not behavior bugs.

## Appendix: environments and artifacts

- **Build:** KimCad 0.9.0b4 @ `356867d`, real mode, port 8745, isolated `KIMCAD_HOME`.
- **Real model:** Ollama `qwen2.5:7b` (live).
- **Real slicer:** bundled OrcaSlicer (`tools/orcaslicer/orca-slicer.exe`), proven via `kimcad.slicer.prove_gcode_3mf`.
- **Real-slice proof (pasted):**
  ```
  GcodeProof(entries=('Metadata/plate_1.gcode',), line_count=21172,
             has_motion=True, estimated_time='18m 11s', layer_count=20,
             filament_mm=4696.35, filament_cm3=11.3, filament_g=None)
  ```
  (`/api/gcode/2` → 127,909 bytes, `Content-Type: model/3mf`, `Content-Disposition: attachment; filename="part_bambu_p2s_pla.gcode.3mf"`)
- **Tools:** curl, the project's `prove_gcode_3mf`, direct Python introspection.
- **Cleanup:** all `.qa-*.json/.stl/.step/.3mf` scratch files removed; server process killed; isolated home discarded.
