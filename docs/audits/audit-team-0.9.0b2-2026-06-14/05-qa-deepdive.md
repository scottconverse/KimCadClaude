# Runtime QA Deep-Dive — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Role:** QA Engineer
**Scope audited:** the running product across every layer — the Python stdlib HTTP server (`kimcad web`), its JSON API (`/api/health`, `/api/design`, `/api/render/<id>`, `/api/slice/<id>`, `/api/send/<id>`, `/api/connectors`, `/api/connections`, `/api/options`, `/api/templates`, `/api/photo-seed`, `/api/sketch-seed`), the session-token CSRF guard, the printer-connector "not configured" states, and the `kimcad` CLI (`--version`, `web`, `models`, `bakeoff`). Driven in **both** `--demo` (fast, deterministic API probing) and **real** mode (live `gemma4:e4b` chat + `qwen2.5vl:3b` vision via local Ollama).
**Environment:** Windows 11 Pro (26200), 16-core CPU / 28 GB RAM / no discrete GPU; Python venv at `.venv`; build `0.9.0b2` (tag `v0.9.0b2`, commit `f92c2b1`); two isolated servers — demo on `127.0.0.1:8795`, real on `127.0.0.1:8796` — each with an isolated `USERPROFILE`/`HOME`/`LOCALAPPDATA` under `%TEMP%\kimcad-qa` so the real `~/.kimcad` was untouched. Probed with PowerShell `Invoke-WebRequest` + `System.Net.Http.HttpClient` (to read error bodies reliably) and direct CLI invocation.
**Auditor posture:** Balanced (with targeted adversarial probing of every error path).

---

## TL;DR

KimCad 0.9.0b2's **running product is exceptionally clean and well-hardened** — the API layer survived a deliberate battery of malformed, oversized, out-of-range, non-finite, and injection-pattern inputs without a single 500, leaked traceback, dropped connection, or unhandled crash. The session-token CSRF guard, the 413 over-limit drain, the JSON-shape guards, the slider clamp/coerce logic, and the connector "not configured" states are all correct and honestly worded. The CLI verbs (`--version`, `models`, `bakeoff`, the non-loopback `web` refusal) behave per spec with the right exit codes. **The one serious runtime issue is the same one the walkthrough flagged, and I extended it:** the default local model (`gemma4:e4b`) does **not reliably fulfill the landing-page example prompts** — across my real-mode runs **all three** landing chips failed, and I found a *new, distinct* failure mode beyond the walkthrough's: the model frequently emits **non-code as the OpenSCAD source** (the literal word `coaster`, or a bare `//`), which fails the render stage (`render_failed`) rather than the plan stage. No security or privacy issue was uncovered while running; the script-tag prompt is returned as inert JSON, not reflected HTML.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 0 |
| Minor | 2 |
| Nit | 1 |

## What's working

- **Session-token CSRF guard (#31) is correct and constant-time.** POST `/api/design` with no `X-KimCad-Session` header → **403** `{"error":"Missing or invalid session token. Reload KimCad.","reason":"session"}`; with a wrong token → **403** (same body); with the valid per-boot 43-char token read from the served index.html meta tag → **200**. The `reason:"session"` discriminator lets the SPA show a reload affordance instead of a generic domain error.
- **Error-path hygiene is uniform and friendly.** Malformed JSON → **400** `"Request body isn't valid JSON."`; a JSON array/scalar/string body → **400** `"Request body must be a JSON object."`; empty/whitespace/missing prompt → **400** `"Please describe the part you want."`; unknown route → **404** `"Not found."`; missing render/slice/send ID → **404**. Every one is a typed JSON error, not a traceback.
- **413 over-limit drain holds (the Windows-RST fix).** A 1.1 MiB body to `/api/design` (cap 1 MiB) returned a clean, fully-read **413** `"Request body too large."` with no connection abort; a 13 MiB image to `/api/photo-seed` (cap 12 MiB) returned **413** `"File too large."`; an empty image body → **400** `"Empty upload."`.
- **Slider re-render is bulletproof against adversarial input.** `/api/render/<id>` with `1e9` clamps to the parameter max (170) and **reports the clamp** via `adjusted_params: {"name":"width","requested":999.0,"applied":170.0}`; a negative value clamps to min; a string/`null`/`Infinity`/`NaN` falls back to the current value; a bool coerces to min; an unknown key is ignored — **all return 200 with valid geometry, no `allow_nan` 500** (the QA-501 non-finite guard works).
- **Method-not-allowed is correct.** POST to a GET-only route (`/api/health`) → **405** with `Allow: GET, HEAD` (not a misleading 404).
- **Connector "not configured" states are specific and actionable.** `/api/connections` returns a per-connector `note` for each unconfigured printer — Duet ("no address configured"), Marlin ("no address or serial port configured"), OctoPrint ("needs an API key… See the README"), Bambu ("no printer address (IP) configured"). The send path returns structured `{"sent":false,"reason":"config"|"unknown","note":...}` with HTTP 200 (the request was well-formed; the connector isn't ready) rather than a confusing 4xx.
- **Demo-vs-real honesty.** The mock connector send returns `"simulated":true`; the design pipeline in demo returns a real readiness report; real mode shows real generation including its failures. Demo mode is strictly opt-in (`--demo`).
- **CLI is correct.** `kimcad --version` → `kimcad 0.9.0b2`; a typo'd subcommand → exit 2 with the valid-choices list; `kimcad models` probes hardware + lists installed Ollama models + recommends one (advisory, never rewrites config); `kimcad bakeoff` fails fast (exit 2) on a single backend or an unknown backend key; `kimcad web --host 0.0.0.0` without `--allow-remote` refuses with the no-auth security warning (exit 2).
- **Injection safety.** A `<script>alert(1)</script>` prompt is returned as inert JSON (`Content-Type: application/json`), not reflected as HTML; a CJK + emoji prompt is handled at 200.
- **Performance is snappy where it doesn't depend on the model.** `/api/health` ~68 ms; a demo design ~191 ms.

## What couldn't be assessed

- **Full browser-visual click-through under a harness.** As documented in the prior walkthrough and cleanup review, KimCad deliberately sets `allow_reuse_address = False` on Windows (`webapp.py:2556` `_ExclusiveBindServer`), so the Claude Preview harness — which reserves the port before launch — cannot drive it. I substituted direct API/CLI probing against hand-started isolated servers and built on the walkthrough's 35-screenshot Playwright pass. This is correct product behavior, not a defect.
- **Real-model success on the coaster "control."** The walkthrough reported the coaster succeeding (readiness 92) in a *non-isolated* real-mode run; in my isolated runs the coaster failed three times with garbage codegen. I could not determine with certainty whether the difference is (a) small-model non-determinism or (b) something about the isolated home degrading generation — see QA-001 and QA-002. I verified the failure is model-output garbage (the generated `.scad` literally contained `coaster`), not an environment artifact, but could not get a single successful real-mode render in my window.
- **Live vision-model rejection of non-image uploads.** In demo mode the photo/sketch-seed endpoints return a canned seed even for random bytes (the demo provider short-circuits the vision model), so I could not confirm via demo whether the *real* vision path validates that an upload is a decodable image. The size guards (400 empty / 413 oversized) fire in both modes; the *content* validation is real-mode-only and was not exercised to a conclusion.
- **Physical printer hardware (#11)** — out of scope, no hardware.

---

## Product shape

KimCad is a **local-first desktop CAD app for non-CAD users**: a Python stdlib HTTP server serves a React SPA on loopback, the SPA drives a JSON API, and the API runs a "describe → AI plan → template/OpenSCAD codegen → printability gate → slice/send" pipeline against a local Ollama model. It is single-user with no accounts; the only auth-adjacent surface is a same-origin per-boot session token (a CSRF mitigation, explicitly *not* remote auth). Because of that shape, QA focused on: (1) **API contract + error correctness** under adversarial input, (2) the **session-token guard**, (3) **connector readiness/honesty**, (4) the **CLI surface** and its exit codes, and (5) **real-model behavior** on the prompts the product itself suggests.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Server bring-up (demo + real) → `/api/health` | Pass | — |
| Session-token guard (no/bad/valid token) | Pass | — |
| Describe → design (demo) | Pass | — |
| Describe → design (real, landing chips) | **Fail** | QA-001, QA-002 |
| Live slider re-render (clamp/coerce/non-finite) | Pass | — |
| Slice (demo) → stats + .3mf | Pass | — |
| Send → mock / unconfigured / unknown / duet | Pass | — |
| Photo / sketch seed (size guards) | Pass | QA-003 (content-validation untested in demo) |
| CLI `--version` / bad subcommand | Pass | — |
| CLI `models` | Pass | — |
| CLI `bakeoff` validation (single / unknown backend) | Pass | — |
| CLI `web` non-loopback refusal | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| POST state-changing route with no session token | 403 (typed JSON, `reason:"session"`) | — |
| POST with a wrong session token | 403 (constant-time compare) | — |
| Malformed JSON body | 400 `"…isn't valid JSON."` | — |
| Valid JSON but array/scalar/string body | 400 `"…must be a JSON object."` | — |
| Body > 1 MiB (cap) on `/api/design` | 413, drained, read cleanly (no RST) | — |
| Image > 12 MiB on `/api/photo-seed` | 413 `"File too large."` | — |
| Empty image upload | 400 `"Empty upload."` | — |
| Slider value `1e9` / negative / bool | Clamped, 200, `adjusted_params` reported | — |
| Slider value `Infinity` / `NaN` / `null` / string | Coerced to current value, 200, no `allow_nan` 500 | — |
| Unknown slider key | Ignored, 200 | — |
| Unknown / nonexistent design ID (render/slice/send) | 404 (typed) | — |
| POST to a GET-only route | 405 with `Allow: GET, HEAD` | — |
| `<script>` prompt | Returned as inert JSON, not reflected HTML | — |
| CJK + emoji prompt | 200 | — |
| Send to unconfigured / unknown connector | `sent:false` + actionable note, HTTP 200 | — |
| Real model on all 3 landing example chips | **All 3 failed** (plan_failed ×1, render_failed ×2) | QA-001, QA-002 |
| `kimcad bakeoff` single / unknown backend | exit 2, names valid backends | — |
| `kimcad web --host 0.0.0.0` (no `--allow-remote`) | exit 2, no-auth warning | — |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Browser / Mobile / Console / Protocol / Install / Auth

### [QA-001] — Critical — Flow — The default local model fails all three landing example prompts (and the "control" coaster) in real mode

**Evidence**
Real-mode server (`kimcad web --port 8796`, no `--demo`) against the live default model `gemma4:e4b` (confirmed installed and recommended by `kimcad models`). I typed each of the three landing example chips — sourced from `frontend/src/components/Landing.tsx:9-13`:
```
EXAMPLES = [
  'a wall-mounted holder for a 1 kg filament spool',
  'a 40 mm desk cable clip',
  'a hexagonal pen and tool organizer',
]
```
Results (POST `/api/design`, valid session token):

1. `a hexagonal pen and tool organizer` → **`render_failed`** after **161 s**. `plan.object_type="Organizer"` (a plan *was* produced), but render failed: `openscad exited 1: … Current top level object is empty.`
2. `a 40 mm desk cable clip` → **`plan_failed`** after **88 s**, user message: *"The model didn't return a usable design plan -- its response couldn't [be parsed]."* (matches the walkthrough's W-F-001).
3. `a round coaster 90 mm across and 4 mm thick` (the walkthrough's successful *control*) → **`render_failed`** at **74 s, 89 s** on two separate runs.

So in my window, **3/3 landing chips and the control all failed** — a broader failure than the walkthrough's 2/3.

**Observed vs expected:** Expected — the app's *own featured* example prompts (the suggested first action for a new user) produce a design. Observed — a 75–160 s wait followed by a graceful but disappointing failure on every prompt I tried.

**Why this matters**
A new beta tester's most natural first action is clicking a suggested example chip. On the default config that currently means a 1–3 minute wait followed by a failure. The failure copy is honest and non-destructive (good), but the *first impression* of an otherwise excellent product is "it didn't work." This is the single most important runtime issue to fix before pointing testers at the build. (Mitigations that exist: the failure is honest and graceful; "Cloud acceleration" is an opt-in escape hatch; clear template-mapped prompts sometimes work.)

**Blast radius**
- Related flows: every on-ramp that ends in `/api/design` against the default model — describe, *and* the photo/sketch on-ramps (their seeds feed the same planning + codegen pipeline). Cloud-accelerated runs are unaffected.
- Related code: `frontend/src/components/Landing.tsx` (the chips), `kimcad/pipeline.py` (plan-parse + codegen retries), `kimcad/llm_provider.py` (the default backend), `bench/prompts.yaml` (the validated prompt set the chips diverge from).
- Tests to update: there is **no test that runs the real default model against the shipped landing chips** — see QA-002 and TEST deep-dive. Add a real-model integration canary (or a curation guard) so a chip the default model can't fulfill fails CI.
- Migration: none (curation of chips is a string change; a stronger default model is a config/packaging decision).
- Related findings: QA-002 (the new render-stage garbage-codegen mode), walkthrough W-F-001, TEST deep-dive (real-model coverage gap).

**Fix path**
Options for a product decision (cheapest first): (a) **curate the example chips** to prompts the default model reliably fulfills (dimensioned, template-mapped — the `bench/prompts.yaml` set is the proven inventory); (b) ship/recommend a stronger default planning model; (c) add a plan-parse + codegen **repair/retry** pass; (d) bias the planner toward the template catalog for short prompts. (a) is the highest-impact, lowest-risk. Pair with the QA-002 fix.

---

### [QA-002] — Critical — API — Real-mode codegen emits non-code as the OpenSCAD source (a new failure mode beyond plan_failed)

**Evidence**
While reproducing QA-001 I inspected the generated `part.scad` files the real-mode server wrote (isolated `--out`):

- `…/web/1/part.scad` (hexagonal organizer) contained the single line: `//` (an empty comment).
- `…/web/2/part.scad` and `…/web/3/part.scad` (coaster, two separate runs) each contained the single word: `coaster`.

These are not valid OpenSCAD, so `render_scad` correctly failed:
```
openscad exited 1: ERROR: Parser error: syntax error in file part.scad, line 2
Can't parse file '…\web\2\part.scad'!
…
Current top level object is empty.
```
This is distinct from QA-001's *plan*-stage failure: here the model produced a plan, advanced to codegen, and the **codegen stage emitted the object name (or a bare comment) instead of code** — which the pipeline surfaces as `render_failed`, a different status, exit code, and user message than `plan_failed`.

> **Environment note (so this finding can't be mis-triaged):** the OpenSCAD stderr also carried `ERROR: Could not find My Documents location`. I traced this to my **isolated `USERPROFILE`** (a temp dir with no registered Windows *Documents* shell folder) — it is a benign OpenSCAD startup warning that a normal user with a real profile does **not** see, and it does **not** cause the failure. The actual failure is the parser error on the garbage `.scad`. I am reporting only the garbage-codegen defect, not the My-Documents line.

**Observed vs expected:** Expected — codegen emits parseable OpenSCAD (or the pipeline retries/repairs until it does). Observed — codegen emitted the literal prompt subject as the file body.

**Why this matters**
The render-failed path is a *worse* user experience than plan-failed because the user has already waited through planning before it fails, and because the codegen retries (`kimcad/pipeline.py`) did not recover the garbage into valid code in any of my runs. It also means the failure surface is broader than the walkthrough characterized (which saw only `plan_failed`): some chips don't even get rejected at the plan gate — they burn the full render budget first. The reproducibility (3 garbage `.scad` files across 3 runs, including the walkthrough's "control" prompt) suggests the default model's codegen is unreliable, not a one-off.

**Blast radius**
- Related code: `kimcad/pipeline.py` (the codegen → retry → render loop; whatever writes the LLM response into `part.scad`), `kimcad/openscad_runner.py` (`render_scad`, `_run`), `kimcad/llm_provider.py` (the codegen prompt + default backend).
- Related flows: every real-mode `/api/design` and slider/on-ramp path that reaches codegen.
- Tests to update: a unit/integration test that feeds the codegen stage a known-garbage model response and asserts the pipeline either repairs it or fails *fast* at the plan gate (not after a full render attempt); plus the QA-001 real-model canary.
- Migration: none.
- Related findings: QA-001 (same root: weak default model on these prompts); TEST deep-dive (no real-codegen test); walkthrough W-F-001 (saw the plan-stage half of this).

**Fix path**
Two complementary moves: (1) before writing the model output to `part.scad`, **validate it looks like OpenSCAD** (e.g. non-empty after comment-stripping, contains at least one statement/primitive) and treat a non-code response as a *plan/codegen* failure that triggers the repair/retry path or a fast, honest failure — never a slow render of garbage; (2) the QA-001 chip-curation / stronger-default-model decision. A cheap guard: if the codegen output, stripped of comments and whitespace, is shorter than the shortest valid primitive call, reject it before invoking OpenSCAD.

---

### [QA-003] — Minor — API — Demo-mode photo/sketch-seed accepts non-image bytes (real-mode content validation unverified)

**Evidence**
In demo mode, POST `/api/photo-seed` and `/api/sketch-seed` with **200 bytes of random data** (not a decodable image), `Content-Type: image/png`, valid session token → **200** with a canned seed (`"A small rectangular box, roughly 80 mm wide…"` / `"A rectangular bracket, 60 mm long…"`). The size guards *do* fire correctly in both modes (empty → 400 `"Empty upload."`; 13 MiB → 413 `"File too large."`). The demo provider intentionally short-circuits the vision model, so this is expected for demo — but it means **demo mode does not exercise image-content validation**, and I could not confirm from demo whether the *real* vision path rejects an undecodable upload gracefully (vs. handing garbage to `qwen2.5vl:3b` and getting an arbitrary hallucinated seed, or erroring).

**Why this matters**
Low user impact (a user uploading a corrupt/non-image file is an edge case, and the real vision model likely degrades to a plausible-but-wrong seed the user can edit). Worth confirming so a real-mode garbage upload returns a clear "couldn't read that image" rather than a confident wrong seed or a 500.

**Blast radius**
- Related code: `kimcad/webapp.py` `_handle_photo_seed` / `_handle_sketch_seed`, the real vision provider in `kimcad/llm_provider.py`.
- Tests to update: a real-mode (or mocked-decode) test that a non-decodable image yields a clear error, not a hallucinated seed.

**Fix path**
Confirm the real-mode path decodes/validates the image (e.g. a Pillow `Image.open` round-trip) before sending it to the vision model, and returns a 400 `"That file isn't a readable image."` on failure. If validation already exists in real mode, no code change — just add the test so the contract is locked.

---

### [QA-004] — Nit — Console — WebGL "GPU stall due to ReadPixels" performance warnings in the 3D viewport

**Evidence**
Carried over from the walkthrough (console captured in every tour): the Three.js 3D viewport emits repeated `GL Driver Message (OpenGL, Performance, … GPU stall due to ReadPixels)` warnings (self-limiting). Not reproduced anew here (no browser harness), but consistent with the 559 KB `Workspace.js` Three.js viewport and a per-frame `readPixels` (likely the measure/pick or thumbnail-capture path).

**Why this matters**
Harmless, but adds console noise that can mask real warnings.

**Fix path**
Throttle/cache the readback, or render-to-target off the main present path. (Same as walkthrough W-F-003.)

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| API `/api/health` latency | ~68 ms | <200 ms | pass |
| API demo `/api/design` latency | ~191 ms | <500 ms (canned) | pass |
| Real `/api/design` (default model) | 74–161 s | n/a (CPU inference) | see QA-001 |
| Server cold-start to first `/api/health` 200 (demo) | a few seconds | — | acceptable |
| Client bundle — `kimcad.js` | 224 KB | — | reasonable |
| Client bundle — `Workspace.js` (Three.js viewport) | 559 KB | — | reasonable for a 3D CAD app |
| Web fonts (3× woff2) | ~113 KB total | — | fine |

LCP/CLS/INP not measured this pass (no browser harness); the walkthrough reported a clean runtime (zero console errors/page errors/failed requests) across all flows.

## Security / privacy snapshot

- **Session-token CSRF guard works** as designed (403 no/bad token, 200 valid; constant-time compare via `hmac.compare_digest`). It is correctly scoped as a same-origin CSRF mitigation, not remote auth — and the `kimcad web` non-loopback path refuses without `--allow-remote` and prints the "NO authentication" warning.
- **No injection surface found at runtime:** a `<script>` prompt comes back as inert JSON; the API never returns user input as HTML.
- **No traceback/info leak:** every error path returns a typed JSON message; the render-failure detail goes to the server log, the browser gets a generic line (QA-008 pattern in `_handle_render`).
- **Secret-scrubbed subprocess env:** OpenSCAD/CadQuery children run with `scrubbed_env()` (no API keys/tokens), bounding blast radius of the untrusted-code path.
- **Home isolation verified:** my isolated `USERPROFILE`/`HOME`/`LOCALAPPDATA` kept new design records out of the real `~/.kimcad` — the real `designs/` *contents* are all dated 6/11 (unchanged); no design data was written or harmed by this audit.

## Console and log observations

No browser console captured this pass (harness constraint). Server logs were clean: error paths logged their class+detail server-side while returning a generic browser message; no unhandled exceptions or dropped connections across the full adversarial battery. The only noise is the documented WebGL ReadPixels warning (QA-004) and — *in my isolated harness only* — the benign OpenSCAD "Could not find My Documents location" line, which a normal user does not see.

## Patterns and systemic observations

- **The API layer is defensively excellent.** Across ~30 adversarial inputs there was not one 500, leaked traceback, or dropped connection. The team has clearly hardened each endpoint against the exact classes a QA pass throws at it (oversized → 413 with drain; non-finite → null coercion; non-object JSON → distinct 400; clamp → reported). This is the cleanest runtime I have audited at beta.
- **The single systemic risk is model quality, not wiring.** Every functional failure I found traces to the *default model's output* on under-specified prompts (QA-001/QA-002), not to a bug in KimCad's own code. The pipeline *handles* the bad output correctly (honest failure, no crash); the gap is that (a) the product features prompts the default model can't do, and (b) garbage codegen reaches the renderer instead of being caught earlier. Both fixes are cheap relative to their first-impression impact.
- **Honesty is consistent.** Demo vs real is never misrepresented; simulated sends are labeled; "not configured" connectors say exactly what's missing; clamped slider inputs are reported back.

## Appendix: environments and artifacts

- **OS:** Windows 11 Pro 10.0.26200; 16-core CPU, 28 GB RAM, no discrete GPU.
- **Build:** KimCad `0.9.0b2` (tag `v0.9.0b2`, commit `f92c2b1`); `/api/health` → `{"version":"0.9.0b2","openscad":true,"orcaslicer":true,"cadquery":true}`.
- **Models:** Ollama @ `localhost:11434` — `gemma4:e4b` (9.6 GB, chat default) + `qwen2.5vl:3b` (3.2 GB, vision), both confirmed installed via `kimcad models`.
- **Servers:** demo `127.0.0.1:8795` (`--demo --out <temp>`), real `127.0.0.1:8796` (`--out <temp>`), each with an isolated `USERPROFILE`/`HOME`/`LOCALAPPDATA` under `%TEMP%\kimcad-qa`.
- **Tools:** PowerShell `Invoke-WebRequest` + `System.Net.Http.HttpClient` (for reliable error-body reads), direct `.venv\Scripts\python.exe -m kimcad.cli` invocation. No browser harness (Preview cannot drive KimCad's exclusive Windows bind — known/correct).
- **Prior evidence built on:** `docs/audits/walkthrough-0.9.0b2-2026-06-14/AUDIT_walkthrough.md` (35 Playwright screenshots) and `docs/audits/cleanup-review-0.9.0b2-2026-06-14.md` (API-level runtime evidence). This deep-dive extends, not duplicates, them.
- **Cleanup:** both servers stopped (verified no listeners on 8795/8796), `%TEMP%\kimcad-qa` removed, real `~/.kimcad` design data verified untouched (contents dated 6/11).
