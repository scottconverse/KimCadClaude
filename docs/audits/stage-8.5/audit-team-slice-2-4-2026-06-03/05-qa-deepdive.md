# QA Engineer Deep-Dive — KimCad Stage 8.5 Slices 2–4 (Live Design Refinement)

**Auditor role:** Senior QA Engineer (runtime behavior across layers)
**Date:** 2026-06-03
**Posture:** Balanced
**Altitude:** Software-complete. No real hardware exercised (and not flagged — out of scope). The `gemma4:e4b` model is NOT running; all design generation went through the LLM-free `DemoProvider` / deterministic `snap_box` template path, exactly as intended for this gate. "LLM not exercised" is therefore NOT a finding.
**Tooling limitation:** The Claude_Preview JPEG screenshot tool times out and was not used. All browser-layer evidence is DOM / computed-property / `getBoundingClientRect` / network-panel / console inspection via `preview_eval` + `preview_network` + `preview_console_logs`. This is a tooling limitation, not a product defect, and does not fail the gate.

---

## Environment

- **Server under test:** model-free demo server, `http://localhost:8765` (running, returned HTTP 200 throughout).
- **Backend source:** `src/kimcad/webapp.py` (stdlib `http.server`, no framework). The deterministic template tier lives in `src/kimcad/templates.py` (`_clamp`, `_coerce_finite`, `clamp_values`).
- **Frontend:** committed Vite build output served from `src/kimcad/web/` (`index.html` + `assets/kimcad.js` minified + `Workspace.js`). No TS source is in this checkout, so the browser-layer audit exercised the *running built product* (the correct QA target).
- **Layers exercised:** HTTP/API (curl + `urllib`) and Browser/DOM (Claude_Preview).
- **Object type:** `box` → `snap_box` template → 4 live parameters (width, depth, height in 10–250 mm; wall 0.8–8 mm).

---

## Summary verdict

**No Blocker, Critical, or Major findings.** The Stage 8.5 Slices 2–4 surface is in strong runtime shape. The two highest-risk claims for this slice both hold under direct observation:

1. **mm boundary holds.** With the display unit set to **inches**, every re-render POST to the backend carries **millimetres**, never inches — proven with the captured request body, not inferred.
2. **History is bounded server-side.** Oversized / malformed / non-list conversation history is sanitized and capped (≤20 turns, ≤4000 chars/turn) with no 500 and no oversized passthrough — proven both over HTTP and by exercising the sanitizer directly.

Version state (undo / redo / compare / branch-truncation), numeric-edit semantics (in-range / clamp / NaN-empty / Escape), and the API error contract all behaved correctly. The browser console was **completely clean** (zero logs, zero warnings, zero errors) across every flow, and there were **zero failed network requests**.

Findings below are all Minor / Nit — observations and hardening notes, none blocking.

### Severity counts

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 3 |
| Nit      | 2 |
| **Total**| **5** |

---

## What I exercised LIVE vs. couldn't

**Exercised live (observed running behavior):**
- `POST /api/design` — success, empty/whitespace prompt, wrong-typed prompt, non-object body, invalid JSON, oversized body (413), oversized/malformed/non-list `history`.
- `POST /api/render/<id>` — in-range, over-max clamp, under-min clamp, NaN / +Inf / −Inf coercion, missing `values`, non-dict `values`, unknown id (404), non-numeric id (404).
- Browser: design submit → workspace; unit mm⇄in toggle; numeric editor open/commit/clamp/empty-revert/Escape-cancel; slider drag re-render; **captured the actual `/api/render` request body with units=inches**; version rail undo, redo, compare (both columns), branch-from-old-version forward truncation; refine submit with history threading; oversized refine prompt; full console + network sweep.
- `_sanitize_history` unit-exercised directly against the running package code.

**Could NOT exercise (stated plainly):**
- Real LLM generation (`gemma4:e4b` not running) — by design; the demo provider returns a *fixed* `[80,60,40]` bbox regardless of prompt text, so v1 "box" and v2 "make it taller" produce identical geometry in demo mode. This is the demo limitation, not a version bug.
- Real-hardware slicing / printer send (no hardware; out of altitude).
- JPEG visual-regression screenshots (tool times out). Visual properties verified via DOM/computed style instead.

---

## The two load-bearing proofs

### PROOF 1 — Re-render POSTs carry mm when the display unit is inches ✅

**Method:** In the running SPA, toggled the unit control to **in** (verified `activeUnit: "in"`, displayed values converted: 80 mm → `3.15in`, 60 → `2.36in`, 40 → `1.57in`, 2 → `0.08in`; underlying `<input type=range>` values stayed `80/60/40/2` mm — conversion is display-only). Patched `window.fetch` to capture request bodies to `/api/render`, opened the Width numeric editor (which showed the value AND its min/max in inches: val `3.15`, min `0.3937` in = 10 mm, max `9.8425` in = 250 mm), typed **5** (inches), committed with Enter.

**Captured request body (units = inches):**
```json
POST /api/render/7
{"values":{"width":127,"depth":60,"height":40,"wall":2}}
```
**5 in × 25.4 = 127 mm exactly.** The client converts inches → mm before POSTing; the backend never sees inches.

Corroborated a second time: with units = inches, editing Width to **4 in** produced server response `target_bbox_mm: [101.6, 60, 40]` and `width.value = 101.6` mm (4 × 25.4 = 101.6). The mm boundary holds.

### PROOF 2 — Oversized / malformed history is bounded server-side ✅

**HTTP layer** (`POST /api/design`), all returned HTTP 200 `status: completed`, no 500:
- 50-turn history → accepted, design completed
- single turn with 10 000-char content → accepted
- malformed mix (bare string, int, null, `system` role, missing `content`, non-string `content`) → accepted
- `history` as a string (not a list) → accepted (dropped)

**Direct sanitizer exercise** (`kimcad.webapp._sanitize_history`, caps confirmed `MAX_HISTORY_TURNS=20`, `MAX_HISTORY_CONTENT=4000`):
- 50 turns → kept **20** (the last 20; first retained content was `t30`)
- 10 000-char content → truncated to **4000** chars
- malformed mix → kept **only** the one well-formed `{role: assistant, content: ok}`
- non-list (string / dict / None) → `None`
- all-invalid list → `None`

History is sanitized and bounded; nothing oversized or arbitrary passes downstream.

---

## Findings

### QA-001 (Minor / Console) — Re-render + autosave fire on *every* numeric/slider commit, producing heavy write traffic

**Category:** Performance / Flow
**Evidence:** Network panel during slider/numeric edits shows the pattern repeats per commit:
```
POST /api/render/7 → 200
GET  /api/mesh/7?v=N → 200
POST /api/designs/save → 200
```
A single editing session of a handful of slider nudges produced ~12 `render` + ~12 `designs/save` round-trips (request ids 26148.24–26148.48). Each numeric-editor commit and each slider `change` triggers a re-render AND a full design autosave (snapshot + mesh write to the design store).

**Why this matters:** On the loopback single-user demo this is invisible. With a real (multi-second) renderer or a slower disk, rapid slider dragging could queue a burst of renders + disk writes. The server already serializes renders (`render_lock`) and converges autosaves to one library entry (`rid_saved_id`, QA-002), so there is no correctness risk — but the autosave-per-render cadence is more write amplification than the interaction needs.

**Blast radius:** Minor — no enumeration required. Touches `_handle_render` (autosave snapshot refresh) and the client's save-on-change cadence. If the real renderer lands, consider debouncing the client autosave (e.g. trailing-edge on drag-end) rather than per `change` event.

**Fix path (suggest):** Debounce the autosave on the client to drag-end / a short idle window; renders themselves are already serialized and idempotent so they can stay live.

---

### QA-002 (Minor / Flow) — `DemoProvider` ignores prompt text, so refine versions are geometrically identical in demo mode

**Category:** Flow
**Evidence:** `DemoProvider.generate_design_plan` returns a fixed `bounding_box_mm=[80,60,40]` for any prompt and ignores `history`. Live: refining v1 "box" → v2 "make it taller" produced **identical** geometry (both `[80,60,40]`); the version pills and compare card correctly differentiate by *prompt label* ("box" vs "make it taller") but the parts are the same shape.

**Why this matters:** This is **expected** for the model-free demo path and is explicitly out of scope for this gate (the model is not running). I record it only so a future reviewer driving the demo doesn't misread "two versions, same shape" as a version-state bug. The version *machinery* (create / restore / compare / truncate) is correct independent of the geometry; see "What's working".

**Not a product defect** — demo-path behavior, documented in the provider docstring.

---

### QA-003 (Minor / API) — Oversized-body rejection (413) closes the connection mid-upload, surfacing a client-side read error

**Category:** API
**Evidence:** `POST /api/design` with a ~2 MB body (over `MAX_BODY_BYTES = 1 MiB`) correctly returns **HTTP 413 Content Too Large**, then closes the connection (`self.close_connection = True`, per the QA-004 comment in `_read_json_body`). A client that is still streaming the body when the 413 lands sees its subsequent socket read aborted (observed: Python `urllib` raised `ConnectionAbortedError [WinError 10053]` *after* receiving the 413).

**Why this matters:** This is the **intended** hardening (reject without draining a hostile upload so a worker isn't pinned), and the 413 status + JSON error shape are delivered before the close. The only consequence is that a naive client may surface the connection reset rather than the clean 413. The browser SPA never hits this (its bodies are tiny — the largest observed real body was 274 bytes), so user impact is nil. Logging here only so an API integrator who streams large bodies understands the reset is by design.

**Blast radius:** Minor. Touches `_read_json_body` / `_read_raw_body` close-on-reject behavior. No fix required; if friendlier integrator behavior is ever wanted, the server could read-and-discard a bounded amount before closing, but that re-introduces the slowloris exposure the current behavior deliberately avoids. **Recommend: leave as-is**; document the close-on-413 in the API notes.

---

### QA-004 (Nit / API) — `/api/design` rejects a non-object JSON body with a generic `"invalid request body"` rather than naming the field

**Category:** API
**Evidence:** `POST /api/design -d '[1,2,3]'` → 400 `{"error":"invalid request body"}`. Correct status and uniform error shape; the message is just generic. Compare the prompt-specific 400 (`"Please describe the part you want."`).

**Why this matters:** Trivial. The status code is right and no crash occurs. A marginally more specific message ("Expected a JSON object.") would help an API integrator, but this is preference, not a defect.

---

### QA-005 (Nit / Browser) — `preview_eval` Promise returns occasionally serialize as `{}`; React controlled-input writes via raw prototype setter don't always flip button-enabled state

**Category:** Browser (test-harness interaction, not a product defect)
**Evidence:** During the audit, a few `preview_eval` calls returning a `Promise` serialized as `{}` (timing), and setting a React-controlled `<textarea>`/`<input>` via the native value setter did not reliably enable the dependent submit button until `preview_fill` was used instead. These are quirks of driving a React SPA through the eval bridge, not behaviors a real user (typing into the field) would encounter.

**Why this matters:** Recorded for transparency about method reliability. Every affected check was re-run successfully with `preview_fill` / synchronous reads, so no result depended on the quirk. **No product impact.**

---

## What's working (credit where due)

The running product survived the adversarial sweep cleanly. Specifics worth crediting:

**Unit handling (the riskiest surface) — solid.**
- mm⇄in toggle converts *display only*; the underlying slider state and every backend POST stay in mm.
- The numeric editor converts its value AND its min/max bounds into the active unit (e.g. 10–250 mm shows as 0.394–9.843 in), so the user edits and is clamped in their chosen unit while the wire stays mm.
- Round-trips are exact: 5 in edit → 127 mm POST → re-display 127 mm; 4 in → 101.6 mm.

**Server-side clamping — defense in depth.** Independently of the client:
- `POST /api/render` with `width: 9999` → clamped to **250** (max); `width: -5` → **10** (min); returned in the `parameters` snapshot.
- `NaN`, `Infinity`, `-Infinity` → coerced to the parameter default (80.0), no 500.
- So even a direct API client bypassing the SPA cannot drive an out-of-range or non-finite dimension into the geometry.

**History threading + bounding — correct and safe.** Refine POSTs carry the prior turns as `[{role,content}]` (observed: `{"prompt":"make it wider","history":[{"role":"user","content":"box"},{"role":"assistant","content":"Here you go — Demo part for: box"}]}`); the server sanitizer caps turns/length and drops malformed input without ever erroring.

**Version rail (undo / redo / compare / branch) — fully wired.**
- Undo at the first version correctly **disables Undo** and reveals **Redo** (no error at the start end).
- Redo at the latest version correctly **removes Redo** (no error at the latest end).
- Undo/redo are pure client state navigation — they fire **no** stray render POST.
- **Compare renders both columns** ("Comparing v1 → v2", each side showing summary, gate `pass`, and `Readiness 92/100`).
- **Branching truncates forward:** on v1 with an old v2 ahead, refining "make it wider" replaced the forward v2 ("make it taller") with the new branch, set it active, and removed Redo. The threaded history matched the active branch.
- Slider/numeric tweaks re-render the active version in place (they don't spuriously mint versions); versions are minted by refine submits — a clean, predictable model.
- Accessibility is present: version pills (`aria-label="Version 1: box"`), value buttons (`aria-label="Width: 129 mm. Click to edit."`), Undo/Compare aria-labels and titles.

**Numeric-edit semantics — all four cases correct at runtime.**
- In-range commit POSTs the value; over-range (Height 500) **clamps to 250** in the POST body and display.
- Empty input + Enter → **reverts** to the prior value and fires **no** POST (no NaN sent).
- Escape → **cancels** (typed value discarded, prior value retained, no POST).

**API error contract — uniform and correct.** Every probed error path returns the right status and the app's JSON error shape, never a 500 or a dropped connection-without-response: non-object body → 400, invalid JSON → 400, empty/whitespace prompt → 400, wrong-typed prompt → 400, render missing/non-dict `values` → 400, unknown render id → 404, non-numeric render id → 404, wrong HTTP method → 405 with `Allow: GET, HEAD, POST`, oversized body → 413.

**Observability — clean.** Across the entire browser session (design submit, unit toggle, numeric edit ×4 cases, slider drags, undo/redo, compare, branch, oversized refine): **zero console logs, zero warnings, zero errors, zero failed network requests.**

---

## Recommendation to the orchestrator

This slice's runtime behavior is gate-ready from a QA standpoint. The two load-bearing claims (mm-on-the-wire under inch display; server-bounded history) are both **proven with captured request bodies / direct code exercise**, not inference. There are no Blocker/Critical/Major findings. The three Minor items are hardening/observation notes (autosave write amplification is the most actionable, and only matters once the real renderer lands); the two Nits are cosmetic. Recommend **PASS** on the QA lane, with QA-001 (debounce client autosave) carried to the next-sprint watchlist for when the live model/renderer replaces the demo path.
