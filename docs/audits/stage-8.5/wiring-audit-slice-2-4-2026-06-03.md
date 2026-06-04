# Wiring Audit — Stage 8.5, Slices 2–4 (runtime gate)

**Date:** 2026-06-03
**Target:** model-free demo server at `http://localhost:8765` (object_type `box` → `snap_box` template → 4 live sliders + a 3-row printability dims table; refine / version / numeric-edit / unit flows all exercised without a model).
**Method:** drove the **real running app** in a Playwright-backed browser preview (Claude_Preview serverId `9d8a04f7-215b-4921-bb2c-c29a4862f866`). Evidence is DOM state, computed styles, `getBoundingClientRect`, captured outgoing **request bodies** (via an installed `window.fetch` interceptor), captured response bodies (`preview_network`), `localStorage`, and the console/failed-network streams. This is a runtime wiring gate, not a static code read — every verdict below is backed by an observed state or network change.

**Altitude / known constraints (not failures):**
- No real hardware; the AI model is not running — this is the deliberate **demo path** (fixed `snap_box` template, fixed bbox).
- The JPEG screenshot tool **times out** in this environment, so all visual evidence is DOM / computed-style / bounding-box / network — **stated, not a failure**.
- The demo provider returns a **fixed bbox**, so refine versions are geometrically identical. The Compare card therefore reads "No dimensional change between these versions." — **expected**, not a version bug.

**Verdict:** **WIRING-AUDIT: PASS** — all Slice 2–4 controls genuinely wired (state + network change, persist where applicable), 0 unresolved findings. One cosmetic **Nit** logged (a compare-card gate-chip CSS class typo; both chips still render the correct "Passed" label and green tone).

---

## Per-control wiring table

| # | Control (Slice) | Verdict | Decisive evidence |
|---|-----------------|---------|-------------------|
| 1 | **Refine input** (S2) | ✅ WIRED | Typing "make it taller" + Send appended a 2nd user+assistant pair (4 msgs) and created **v2** (version rail appeared, 2 pills). A 2nd refine ("widen it") captured `POST /api/design` with `prompt:"widen it"` + a **4-turn `history` array** (a box→reply→make it taller→reply) — prior turns genuinely threaded to the backend. |
| 2 | **Version pills / Undo / Redo** (S2) | ✅ WIRED | Click v1 pill → thread restores to 2 msgs, right panel shows v1 dims (80/60/40), **Undo disabled** at v1, **Redo present** below latest. Redo steps v1→v2 (msgs 2→4); Undo steps v2→v1 (msgs 4→2, Undo re-disabled). At latest v3: 6 msgs, **Redo hidden**, Undo enabled. |
| 3 | **Compare** (S2) | ✅ WIRED | Click Compare → `.kc-compare-card` injected: title "Comparing v2 → v3", two cols each with summary, **gate chip "Passed"** (gateLabel) + Readiness 92/100, and `.kc-compare-delta` reading **"No dimensional change between these versions."** (expected: fixed demo bbox). |
| 4 | **Numeric edit** (S3) | ✅ WIRED | Click value → inline `type=number` input (seed 80, min 10/max 250). Type 150 + Enter → `POST /api/render/16 {width:150,…}`, editor closes, pval+slider re-sync to 150. **Out-of-range** 9999 → inline alert "Enter 10–250 mm" + `aria-invalid`, Enter **clamps to 250** (`POST …{width:250}`, re-sync 250). **Empty** → reverts, **0 render POSTs**. **Escape** after typing 123 → cancels, **0 render POSTs**, value unchanged. |
| 5 | **Unit toggle + persistence** (S4) | ✅ WIRED | Toggle "in" → **sliders AND dims table convert in lockstep** (250mm→9.843in; dims X 250→9.843; headers "(mm)"→"(in)") via the shared `useUnits` store; `localStorage 'kc-units'==='in'`. **Reload** → pref persists (`kc-units` still 'in', in-button active, UI returns in inches). Toggle back to mm → `kc-units==='mm'`, headers "(mm)", values back in mm (no drift). |
| 6 | **mm boundary** (load-bearing) | ✅ WIRED | In **inch mode**, numeric-edit width to "2" (inches) → captured `POST /api/render/17` body = `{"values":{"width":50.8,"depth":60,"height":40,"wall":2}}` — carries **mm (50.8 = 2×25.4)**, never the inch value. **No inches-to-backend leak.** |
| 7 | **Autosave / persistence through new flow** (S1) | ✅ WIRED | Design + refine auto-saved: URL became `#/design/<id>`, repeated `POST /api/designs/save` (200), Topbar "Saved · My Designs". Fresh full-reload navigation to `#/design/9145c09c…` **restored the part** (4 sliders at persisted 50.8/60/40/2 mm, gate "Passed", thread seeded v1, refine input present). The 2in→50.8mm edit survived save→reopen with **no drift**. Design also appears in the **My Designs** library grid (12 cards, thumbnails, Rename/Duplicate/Export/Delete). |

**Console:** clean throughout — `preview_console_logs` (all levels) returned **no logs / no errors / no warnings** across every step, including after reloads and the My Designs navigation.
**Network:** `preview_network filter:failed` returned **No failed requests** at every checkpoint. All observed requests (`/api/design`, `/api/render/*`, `/api/designs/save`, `/api/designs/*`, `/api/mesh/*`, `/api/options`, `/api/connectors`) were **200/304**.

---

## Captured network evidence (key payloads)

**Refine threads prior turns (request body, Test 1):**
```json
POST /api/design
{ "prompt": "widen it",
  "history": [
    {"role":"user","content":"a box"},
    {"role":"assistant","content":"Here you go — Demo part for: a box"},
    {"role":"user","content":"make it taller"},
    {"role":"assistant","content":"Here you go — Demo part for: make it taller"} ] }
```

**Numeric edit fires a deterministic re-render (request body, Test 4):**
```json
POST /api/render/16
{ "values": { "width": 150, "depth": 60, "height": 40, "wall": 2 } }
```

**mm boundary — inch-mode edit sends mm, not inches (request body, Test 6, load-bearing):**
```json
POST /api/render/17
{ "values": { "width": 50.8, "depth": 60, "height": 40, "wall": 2 } }
```
(`50.8 == 2 in × 25.4`. The display field is in inches — min 0.394in / max 9.843in — but `commitEdit` converts via `fromDisplay` before the POST.)

**Initial design response (Test 0, snap_box template):** `object_type:"box"`, `template:"snap_box"`, 4 parameters (width 10–250, depth 10–250, height 10–250, wall 0.8–8), gate `pass`, readiness 92, 3 dims — all unit `mm`.

**Unit persistence:** `localStorage['kc-units'] === 'in'` survived a full page reload; UI rehydrated in inches.

---

## Findings (Blocker → Nit)

**Blocker:** none.
**Critical:** none.
**Major:** none.
**Minor:** none.

**Nit (1):**

- **WIRE-N1 — Compare card: second gate chip uses the wrong CSS class prefix (`kc-tone-` instead of `kc-gate-`).**
  - **Severity:** Nit (cosmetic; both chips render the correct "Passed" label and a green pass tone — no wiring/data impact).
  - **Location:** `frontend/src/components/ChatPanel.tsx`, `CompareCard`. Column A (line 74) emits `` className={`kc-compare-gate kc-gate-${gateTone(gateA)}`} ``; Column B (line 81) emits `` className={`kc-compare-gate kc-tone-${gateTone(gateB)}`} ``.
  - **What the user sees:** the two version columns' gate chips have **slightly different backgrounds** — v2's chip (`.kc-gate-pass`, `frontend/src/styles.css:1948`) is translucent green (`…/0.14`); v3's chip (`.kc-tone-pass`, `frontend/src/styles.css:1104`) is an opaque pale-green (`color-mix(… 15%, --kc-surface)`). Observed computed backgrounds: `color(srgb 0.113 0.478 0.305 / 0.14)` vs `color(srgb 0.850 0.891 0.839)`. Text color identical (`rgb(29,122,78)`), padding/radius identical.
  - **What should happen:** both chips should use the purpose-built `.kc-gate-*` family so the two columns match.
  - **Likely cause:** copy/paste typo — `kc-tone-` left in the second column instead of `kc-gate-`.
  - **Suggested fix:** in `ChatPanel.tsx` line 81 change `` kc-tone-${gateTone(gateB)} `` → `` kc-gate-${gateTone(gateB)} ``.
  - **Suggested test:** a `ChatPanel` render test asserting **both** `.kc-compare-gate` chips carry a `kc-gate-*` class (and none carry `kc-tone-*`).

---

## What's wired well

- **Refine → history threading is real, not cosmetic.** The follow-up doesn't just append a bubble — it serializes the full prior conversation into the `/api/design` request `history`, so the backend has genuine multi-turn context. Verified at the wire.
- **Version model is honest and consistent.** Pills, Undo, Redo, and direct-jump all converge on one `versionIdx`/`handleSwitchVersion` path; the disabled-at-v1 / hidden-at-latest edge states match the spec exactly; restoring a version restores BOTH the thread and the right-panel result.
- **Numeric entry has a complete commit contract.** In-range commits + renders + re-syncs to the server's clamped truth; out-of-range clamps to spec with a self-describing inline alert; empty and Escape both correctly **suppress the network call** (the no-op/empty guards in `commitEdit` work as written). No stray POSTs.
- **Units use a single shared external store.** Toggling one control re-renders every consumer (sliders + dims table) in lockstep — the `useSyncExternalStore` design avoids the per-component `useState` drift it was built to prevent. Preference persists across reload via `localStorage`.
- **Canonical-mm boundary holds.** The display layer is unit-aware, but the backend contract stays pure mm: an inch-mode edit converts to mm *before* the POST. This is the highest-risk leak point and it's clean.
- **The new version/thread state did not break Slice 1 persistence.** Autosave still fires, the URL is still a real per-design address, and a cold reopen restores the refined part (with the refined values, no drift) and re-seeds v1. The design lands in the My Designs library.
- **Zero console errors, zero failed requests** across the entire driven session (including reloads and route changes).

---

## Confidence and gaps

- **Fully audited (driven live, evidence captured):** refine input + history threading; version pills / Undo / Redo incl. disabled/hidden edge states; Compare card + gate chips + delta; numeric edit (in-range / out-of-range clamp / empty revert / Escape cancel) with render-POST presence/absence proven; unit toggle lockstep conversion + reload persistence + toggle-back; the mm-in-inch-mode boundary POST body; autosave + cold-reopen restore + My Designs library presence; console + failed-network streams.
- **Exercised on the box/`snap_box` template path only** (the demo's single object type). The slider/numeric/unit wiring is template-generic, but a second template family was not available to drive in the demo — noted, not a gap in the tested path.
- **Demo-path caveats (by design):** fixed bbox means Compare deltas are always "No dimensional change" here; a real model run would populate per-axis deltas — the delta *renderer* is wired (`diffVersions`), it simply has no diff to show on identical geometry. The clarifying-question inline-answer sub-flow (S2) wasn't triggerable on the demo provider (it returns a completed part, never `clarification_needed`); the refine input is the same input that would carry that answer, and it is proven wired.
- **Not in scope here:** the JPEG/visual-pixel layer (tool times out — DOM/computed-style used instead); real-hardware slicing/print; the AI model round-trip latency/progress UI (Slice 9, not this gate).

**Bottom line:** every Slice 2–4 control the gate calls for is genuinely wired end-to-end and persists where applicable, with one cosmetic Nit. **WIRING-AUDIT: PASS.**
