# Runtime QA Deep-Dive — KimCad Stage 4 (React SPA shell + viewport)

**Audit date:** 2026-06-05
**Role:** QA Engineer (independent, adversarial)
**Scope audited:** The running web product — the React/TS SPA shell, the 3D viewport, and the stdlib HTTP API behind it (`src/kimcad/webapp.py`). Core flow exercised end to end (load → demo generate → viewport render → adjust params → slice → export/send), then attacked.
**Environment:** Windows 11, Python 3.14.3 `http.server` (demo mode, LLM-free). Primary target instance `http://127.0.0.1:8767/`; a second identical-build managed instance on `:8765` was used to drive the SPA in a real (Chromium-based) preview browser. Real OpenSCAD + OrcaSlicer binaries present and exercised (slicing produced real G-code, 78k–93k lines). API checks via curl; UI checks via the preview browser (DOM + real network logs authoritative).
**Auditor posture:** Adversarial.

---

## TL;DR

The Stage 4 product behaves as claimed and survives a deliberate attack battery. The full happy path works in both the real browser and at the API: a demo prompt designs a part, the 3D viewport renders it (desktop and mobile), live sliders re-render geometry locally with no model round-trip, a real OrcaSlicer slice produces downloadable G-code, and a simulated send is honestly labeled. The two most safety-critical invariants hold under direct API attack — a **gate-failed part cannot be sliced or sent** (refused server-side, no G-code ever produced), and a **re-render immediately invalidates a prior slice** so a stale-geometry G-code can never be downloaded or sent. Input handling is uniformly defensive: malformed JSON, wrong-typed prompts, oversized bodies, out-of-range slider values, path traversal, and bad ids all return clean, friendly 4xx with the app's JSON error shape — no unhandled 500s, no tracebacks, no NaN/invalid-JSON, no broken viewport. The browser console was clean (zero errors/warnings) across every flow. **No Blocker, Critical, or Major findings.** Two Minor and two Nit observations, all about polish, not correctness.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 2 |

## What's working

- **Gate-failed parts are unslice­able and unsendable, enforced server-side.** Generated a gate-failing oversized part (`demo:gatefail`, rid 2, 300×300×300 mm, exceeds build volume). `POST /api/slice/2` → `200 {"sliced": false, "reason": "gate_failed", ...}` (refused), `GET /api/gcode/2` → 404, `POST /api/send/2` → 404 (no slice to send). The mesh itself remains downloadable for inspection (correct per spec). This holds for a direct API client, not just the browser that hides the controls.
- **Re-render invalidates a prior slice (no stale geometry can ship).** Sliced rid 4 (`GET /api/gcode/4` → 200, 142,827 bytes). Then `POST /api/render/4 {"values":{"width":140}}`. Immediately after, `GET /api/gcode/4` → 404 and `POST /api/send/4` → 404. The shape a user already changed can never be downloaded or sent.
- **Full happy path, in the real browser and at the API.** UI: typed a prompt, clicked "Design it" → `POST /api/design` 200 → viewport `<canvas>` rendered (546×705) → gate "Ready to print" / readiness 92/100 → slider drag → `POST /api/render/5` 200 + fresh mesh → `POST /api/slice/5` 200. API: identical chain plus `POST /api/send/1` → `{"sent": true, "simulated": true, ...}`. Real slice estimates were plausible (e.g. "~1h 14m, 250 layers, 53.48 cm³, 66.3 g").
- **Out-of-range slider values are clamped and the client is told.** `POST /api/render/1 {"values":{"width":99999}}` → width applied 250 (the max) with `adjusted_params: [{"name":"width","requested":99999,"applied":250.0}]`. A `"NaN"` string coerces to the default and is likewise reported. The SPA sliders are range-bounded (10–250 mm, wall 0.8–8) so they never trip this in normal use; this is correct belt-and-suspenders for a raw API client.
- **Uniform, friendly error contract.** Malformed JSON → 400 "Request body isn't valid JSON."; non-object body (`[...]`, `null`) → 400 "must be a JSON object."; empty/whitespace/numeric prompt → 400 "Please describe the part you want."; oversized body (>1 MiB) → 413; unknown printer → 400; garbage import → 400 "isn't a valid KimCad design export."; unknown route → 404. Every error is the app's JSON shape — no empty bodies, no stack traces.
- **HTTP hygiene.** `HEAD` on a GET resource → 200 header-only; `PUT/DELETE/PATCH/OPTIONS` → 405 with `Allow: GET, HEAD, POST`; static assets carry content-hash `ETag` + `no-cache` (304 on revalidation observed). Path traversal on `/assets/`, `/vendor/`, and design ids all rejected → 404 before touching the filesystem.
- **Hash routing is sound.** The SPA uses `#/designs`, `#/settings`, `#/design/<id>`; the hash never reaches the server, so a refresh/bookmark on any route loads `/` (200, SPA shell) and resolves client-side. No broken deep links.
- **Clean console + clean network on the legitimate flow.** Zero console errors/warnings across landing, wizard, workspace, My Designs, slider, and slice. Every legitimate API request returned 200/304; no 4xx/5xx on the happy path.
- **Mobile layout reflows.** At 375×812 the workspace stacks to a clean single column (versions → conversation → viewport → parameters → CTA); the viewport renders the part with dimension labels; no broken layout.
- **First-run wizard shows once.** Skipping it persists across reload (no re-prompt).

## What couldn't be assessed

- **Real LLM behavior.** This is an intentional demo (LLM-free, fixed sample part); the model path (`gemma4:e4b`, cloud opt-in) was not exercised at runtime. `GET /api/model-status` reported the real local Ollama as running with the model present, but no real generation was driven. Out of scope for Stage 4.
- **Real printer hardware.** Only the `mock` (simulated, loopback) connector was driven; the `octoprint` connector reports `simulated: false` but no hardware was attached. Honestly labeled either way.
- **Cloud (OpenRouter) routing.** Not enabled; the masking/opt-in logic was read in code but not exercised live (no key configured).
- **Cross-browser breadth.** Driven only in the Chromium-based preview browser. Firefox/WebKit not tested (no runtime available in this environment).

---

## Product shape

KimCad Stage 4 is a single-page React/TS app served as a committed static build by a dependency-free Python `http.server`, with a thin JSON API over the existing pipeline. Because it is local-first and single-user/loopback, QA focused on (1) the core design→render→slice→export/send flow in a real browser, (2) the API contract and error handling under malformed/adversarial input, and (3) the two safety invariants that protect a user from printing a bad part: the gate-fail refusal and the stale-geometry invalidation.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Load SPA shell → mount | Pass | — (374-byte shell + `/assets/kimcad.js`; root mounts cleanly) |
| First-run wizard → skip → persists | Pass | — |
| Demo generate (UI: type prompt → "Design it") | Pass | — |
| Viewport renders part (desktop) | Pass | — (canvas 546×705, dim labels, auto-orient) |
| Viewport renders part (mobile 375×812) | Pass | QA-003 (Minor: canvas internal buffer wider than vw) |
| Live slider re-render (UI + API) | Pass | — (`/api/render` 200, fresh mesh, cache-busted) |
| Slice (UI + API, real OrcaSlicer) | Pass | — (78k–93k G-code lines, plausible estimates) |
| Download G-code | Pass | — |
| Send to mock connector | Pass | — (honestly labeled `simulated: true`) |
| My Designs library (list, thumbs, actions) | Pass | QA-004 (Nit: library accumulates refine-fragment names) |
| Settings / model-status / health reads | Pass | — |
| Experimental-offer path (non-template) | Pass | — (`needs_experimental`, no auto-run) |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Gate-failed part → slice | Refused `200 {sliced:false, reason:gate_failed}` | clean |
| Gate-failed part → send | 404 (no G-code) | clean |
| Gate-failed part → fetch G-code | 404 | clean |
| Slice → re-render → fetch old G-code | 404 (slice invalidated) | clean |
| Slice → re-render → send | 404 | clean |
| Out-of-range slider (width 99999) | Clamped to 250, `adjusted_params` reported | clean |
| NaN string slider value | Coerced to default, reported | clean |
| Malformed JSON to /api/design, /api/slice | 400 "isn't valid JSON" | clean |
| Non-object body (`[...]`, `null`) | 400 "must be a JSON object" | clean |
| Empty / whitespace / numeric prompt | 400 friendly | clean |
| Oversized body (>1 MiB) | 413, connection closed | clean |
| Bad/unknown design id (render/slice/send) | 404 friendly, distinct messages | clean |
| Unknown printer to /api/slice | 400 "Unknown printer or material" | clean |
| Garbage to /api/designs/import | 400 friendly | clean |
| Path traversal (`/assets/..%2f..`, design id) | 404 before FS touch | clean |
| Method abuse (PUT/DELETE/OPTIONS) | 405 + Allow header | clean |
| HEAD on GET resource | 200 header-only | clean |
| SPA deep-link refresh (`/designs` path) | N/A — hash routing, loads `/` | by design |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Browser / Mobile / Console / Install

### [QA-001] — Minor — API — `adjusted_params` echoes a non-numeric requested value verbatim

**Evidence**
1. `POST http://127.0.0.1:8767/api/render/1` body `{"values":{"width":"NaN"}}`.
2. Observed: `200`, `width` applied `80.0` (default), and `adjusted_params: [{"name":"width","requested":"NaN","applied":80.0}]`.
3. Expected: same clamping behavior, but the `requested` field reflects a value the consumer can act on, or the response notes the input was non-numeric/ignored rather than echoing the literal string `"NaN"` as if it were a requested measurement.

**Why this matters**
A raw API consumer reading `adjusted_params` to decide whether to warn its user gets a `requested` of `"NaN"` (a string), mixed in with the numeric requests from legitimate clamps. It's harmless (the geometry is correct and bounded), but the contract is slightly inconsistent — `requested` is sometimes a number, sometimes an arbitrary string. The browser never sends this (sliders are numeric), so no end user is exposed.

**Blast radius**
- Related endpoints/flows: `_handle_render` adjusted-params logic in `src/kimcad/webapp.py` (~lines 1761–1773). Only the `/api/render/<id>` contract.
- Tests to update: any render-contract test asserting `adjusted_params` shape (none observed asserting the non-numeric case).
- Related findings: none.

**Fix path**
In `_handle_render`, when the requested value can't be coerced to a float, either omit it from `adjusted_params`, normalize `requested` to `null`, or add an `"ignored": true` flag — so `requested` stays type-consistent for API integrators.

---

### [QA-002] — Minor — API — `octoprint` connector advertised but a hands-on user has no hardware behind it

**Evidence**
1. `GET http://127.0.0.1:8767/api/connectors` → `{"connectors":[{"name":"mock","simulated":true},{"name":"octoprint","simulated":false}],"default":"mock"}`.
2. `octoprint` is offered with `simulated: false`, but on this box no OctoPrint server is configured/reachable; a real send would resolve to a typed not-ready/offline status via `/api/connector-status/octoprint` (a non-error status, correctly never a 5xx).
3. Expected: this is honest and safe (the status path degrades gracefully), but a beta user who picks `octoprint` with nothing behind it relies on reaching the send/status step before learning it isn't set up.

**Why this matters**
Low exposure — the default is `mock`, the status contract is typed and never crashes, and the UI labels simulated vs. real. The only gap is discoverability: a not-configured real connector looks selectable. Flagged as a polish item, not a defect; the runtime behavior is correct.

**Blast radius**
- Related endpoints/flows: `/api/connectors`, `/api/connector-status/<name>`, `/api/send/<id>`.
- User-facing: connector picker in the export panel.
- Tests to update: none required.
- Related findings: none.

**Fix path**
Consider surfacing each connector's live readiness (or a "not set up" badge) in the picker by pre-fetching `connector-status`, so an unconfigured real connector reads as needing setup before the user commits to a send. Owned jointly with UI/UX.

---

### [QA-003] — Minor — Mobile — Viewport canvas internal width exceeds the mobile viewport width

**Evidence**
1. Resized the preview browser to mobile (375×812), navigated to a saved design (`#/design/<id>`).
2. Visible layout reflows correctly to a single column and the part renders with dimension labels (screenshot captured during the session).
3. DOM probe: `document.body.scrollWidth` reported `480` against `window.innerWidth` 375; the `overflow` heuristic returned false (no user-visible horizontal scrollbar appeared in the screenshot), suggesting the extra width is the WebGL canvas's internal/backing buffer rather than a laid-out element forcing page scroll.
4. Expected: no element wider than the viewport. Observed: visually clean, but the measured `scrollWidth` is larger than the viewport — worth a quick confirmation on a real phone that no horizontal scroll/jiggle occurs.

**Why this matters**
The visible layout was clean in the screenshot (no horizontal scrollbar, CTA and controls fully in-frame), so user impact is likely nil. But a `scrollWidth` > `innerWidth` is the classic signature of a subtle mobile overflow that can manifest as a 1–2px horizontal jiggle on some devices. Low confidence that it's user-visible; flagged so a real-device pass can confirm.

**Blast radius**
- Related flows: the workspace viewport on small viewports; `Viewport.tsx` / `KCViewport.ts` canvas sizing and the workspace grid CSS in `styles.css`.
- Tests to update: none (no mobile-overflow assertion exists).
- Related findings: none.

**Fix path**
Verify on a real phone (or device-emulation with a visible scrollbar). If a horizontal scroll exists, constrain the canvas/container to `max-width: 100%` / `overflow-x: hidden` on the workspace wrapper and ensure the canvas backing-store size derives from the clamped client width.

---

### [QA-004] — Nit — Flow — Auto-saved library accumulates refine-fragment names

**Evidence**
1. `GET http://127.0.0.1:8767/api/designs` returns ~24 entries; many are named for a refine fragment rather than a part — e.g. "make it taller", "widen it", "make it wider", "make it 10mm taller", and one truncated to "make it taller and add a lid and round the corners and chamfer every edge and also engrave my name on the bottom in a se".
2. Auto-save is intentional and correctly de-duplicated: each live design converges to ONE library entry (server `rid_saved_id` + `saved_id` reuse; client debounce; verified by the in-repo race-guard test TEST-001). So a single design + slider drags does not mint duplicates.
3. The long list is the cumulative result of many separate test sessions across days, each a distinct design — expected accumulation, not a save bug.

**Why this matters**
Purely cosmetic. When a design's name is derived from a follow-up turn's text, the auto-derived name reads as an instruction, not an object. A first-time user's library could fill with "make it taller" style names. Not a correctness issue; the dedup and persistence are sound.

**Fix path**
Consider deriving the auto-name from the design's `object_type` / original prompt rather than the latest refine turn, or prompt for a name on first explicit save. Owned by UI/UX.

---

### [QA-005] — Nit — Browser — Bare-key shortcuts are correctly suppressed while typing (no defect; documented to prevent a false report)

**Evidence**
1. The app binds bare-key shortcuts: `n` (new design), `d` (My Designs), `,` (settings), `?` (help) — `src/.../App.tsx` ~lines 188–224.
2. The handler correctly returns early when focus is in `INPUT`/`TEXTAREA`/`SELECT`/contenteditable (lines 190–203), and when the wizard or help overlay is open. Verified by reading the guard and by the fact that real typing into the prompt textarea did not trigger navigation.
3. During automated driving, synthetic key events dispatched by the test harness *without* true input focus did navigate (e.g. to `#/designs`) — a test-harness artifact, **not** a product bug. A human typing in the focused field is unaffected.

**Why this matters**
Recorded only so this harness artifact is not mistaken for a navigation bug in a later pass. The guard is complete and correct.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| SPA shell size | 374-byte HTML + bundled `/assets/kimcad.js` (code-split: separate `Workspace.js` chunk lazy-loaded) | — | reasonable; code-splitting present |
| Demo design (`POST /api/design`) | sub-second (LLM-free demo) | — | fast (demo) |
| Live re-render (`POST /api/render`) | sub-second | <1s for "live" sliders | pass |
| Real slice (`POST /api/slice`, OrcaSlicer) | ~tens of seconds, CPU-bound | n/a (real slicing) | expected; serialized under a lock |
| Static asset caching | content-hash ETag + `no-cache`; 304 on revalidate | — | correct |
| Console health | 0 errors, 0 warnings across all flows | clean | pass |

(LCP/CLS/INP not separately instrumented in this environment; the visual load was immediate and stable with no layout shift observed.)

## Security / privacy snapshot

- **No IDOR / traversal reachable.** Asset, vendor, and design-id paths reject `/`, `\`, and `..` before any filesystem access (verified: `/assets/..%2f..%2fwebapp.py` → 404; `/api/designs/..%2f..%2fconfig/export` → 404).
- **Server-side gate enforcement.** The gate-fail refusal is enforced in the API, not just hidden in the UI — a direct client cannot slice or send a gate-failed part.
- **No traceback leakage.** Unexpected errors are mapped to typed statuses or `{"error":"<Class>: <msg>"}` without a stack; malformed input never 500s.
- **Body-size + history caps.** 1 MiB JSON body cap (413), 32 MiB import cap, 12 MiB photo cap, bounded conversation history — a hostile upload can't exhaust memory.
- **Key handling (read in code, not exercised live).** The OpenRouter key is only ever returned masked (`_mask_key`, last-5); cloud is opt-in and degrades to local on any gap. Not driven at runtime (no key configured) — flagged under "What couldn't be assessed".
- No auth surface exists by design (local, single-user, loopback) — not a finding for this product shape.

## Console and log observations

`preview_console_logs` returned **no errors and no warnings** across the entire session: landing, first-run wizard, workspace, viewport render, slider re-render, slice, My Designs, settings, and mobile. The legitimate network stream was all 200/304; the only non-200 entries were (a) deliberate adversarial probes returning the expected 4xx/413/404, and (b) one `GET 127.0.0.1:8767/ ERR_ABORTED` caused by my own reload being superseded by the next navigation (harness artifact, not an app failure).

## Patterns and systemic observations

- The codebase shows a mature, defense-in-depth posture: nearly every handler carries an inline reference to a prior finding (ENG-/QA-) it remediates (gate safety, stale-geometry versioning, NaN-safe JSON, traceback suppression, traversal guards, body caps, LRU eviction with on-disk cleanup). The runtime behavior matches these claims — this is the rare case where the comments and the observed behavior agree.
- The two highest-leverage safety invariants (gate-fail refusal; re-render invalidates slice) are enforced server-side and verified to hold under direct API attack, which is exactly where a UI-only guard would have failed.
- The product is honest about simulation: the `mock` connector and any simulated send are labeled `simulated: true`, and weight estimates derived from volume×density are flagged `filament_g_estimated: true`.

## Appendix: environments and artifacts

- **Target instance:** `http://127.0.0.1:8767/` (demo mode), Python 3.14.3 `http.server`, KimCad version `0.1.0`, OpenSCAD + OrcaSlicer present.
- **Browser-driven instance:** identical build on `:8765` via the preview browser (Chromium-based); used because the preview tooling attaches to a managed server. Both instances run the same committed build, so functional findings apply to both.
- **Viewports tested:** desktop (native) and mobile (375×812).
- **Tools:** `curl` (API contract + adversarial), preview browser (`preview_eval`/`preview_screenshot`/`preview_network`/`preview_console_logs`/`preview_resize`), source read of `src/kimcad/webapp.py` and `frontend/src/`.
- **Key evidence captured in-session (screenshots):** first-run wizard; My Designs with real 3D thumbnails; full desktop workspace (viewport + readiness 92/100 "Ready to print" + parameter sliders); mobile single-column workspace with rendered part. Real slice responses logged (78,127 and 92,697 G-code lines with plausible time/filament estimates).
- **Branch:** `stage-0-7-audit-backfill`, head `b45298c`.
