# KimCad Stage 8.5 Slice 1 — Playwright Interface Wiring Audit

> Audited 2026-06-03 · branch `stage-8.5-usability` @ `985f271` ("Stage 8.5 Slice 1 — audit-team stage gate: fix all 37 findings -> 0/0/0/0/0") · auditor: Claude (audit-only mode)

## Executive Summary

**Verdict: Slice 1 is genuinely wired end-to-end. It is not a cosmetic shell.** Every "My Designs"
control I exercised fires a real backend request, mutates real on-disk state under
`~/.kimcad/designs/`, and the UI reflects the result. There are no dead or decorative controls in
the persistence/library surface. The one substantive gap is a mobile touch-target size issue on the
card action buttons (Low/Medium) — everything else is working.

The deal-killer the task was most worried about — "looks wired but isn't" — does not apply here.
I confirmed the wiring at three independent layers for each operation: the browser network panel
(the request fired and returned 200), the on-disk effect (a design dir appeared / changed / vanished
under `~/.kimcad/designs/`), and the re-listed/re-rendered UI. Create→auto-save→persist works; a
**page reload truly restores the part and its sliders** (not a blank workspace); and the Topbar save
indicator is driven by the **actual save POST lifecycle** (`Saving…` while in flight →
`Saved · My Designs` once persisted), not a fake timer — I watched it transition live in lock-step
with the `POST /api/designs/save` request and the `#/design/<id>` URL flip.

Robustness is strong: every adversarial HTTP probe (absent id, path-traversal id, empty rename,
garbage save id, junk/empty import) returned a clean 4xx with a friendly JSON error and **no 500 and
no traceback body**. The path-traversal guard is genuinely enforced — nothing is served from outside
`~/.kimcad/designs/`. Across the entire browser session (design, save, reload-restore, reopen,
rename, duplicate, export, import, two-step delete, search, sort, routing, back/forward, desktop +
mobile) there were **zero console errors and zero failed network requests**.

Findings: **0 Critical · 0 High · 1 Medium · 3 Low.** Slice 1 is shippable from a wiring standpoint;
the findings are polish, not blockers.

## Methodology

- **Reviewed:** `docs/stage-8.5-usability-plan.md` (Slice 1 spec / acceptance bar), the backend store
  `src/kimcad/design_store.py`, the web layer `src/kimcad/webapp.py` (design + persistence
  endpoints, lines ~536–1064), `src/kimcad/config.py` (`designs_path()` → `~/.kimcad/designs`),
  `src/kimcad/cli.py` (`web --demo`). The frontend ships as a **minified production React bundle**
  (`src/kimcad/web/assets/kimcad.js` = React vendor; `Workspace.js` = app code, minified). No
  unminified app source is checked in, so frontend wiring was verified by **driving the live app +
  network/DOM/disk observation** rather than reading JSX — which is exactly this skill's decisive
  evidence standard.
- **Launched:** `.venv/Scripts/python.exe -m kimcad.cli web --demo` via the preview tooling
  (`.claude/launch.json` "kimcad-demo"). The preview harness started its own demo instance on
  **port 8765** (it did not reuse my manual 8772 instance), so all browser-driven flows and all
  HTTP probes target `http://127.0.0.1:8765`. Both ports share the same per-user store
  (`~/.kimcad/designs`), so disk observations are identical regardless. The manual 8772 instance was
  stopped to avoid a duplicate; 8772 is free.
- **Tests run:** `pytest tests/test_design_store.py` → **20 passed** (the store's unit suite).
- **Browser coverage:** workspace landing, design submission, auto-save, reload-restore, `#/designs`
  gallery, Open/reopen, inline Rename, Duplicate, Export, Import (UI file-input flow), two-step
  Delete, Search (match + no-match empty state), Sort (Newest/Oldest/Name), Topbar routing + active
  state, browser Back/Forward, desktop 1280×800 and mobile 375×812.
- **Tools:** Claude Code preview tools (Playwright-backed: snapshot, click, fill, eval, inspect,
  network, console, resize, screenshot) as primary driver; Python `urllib`/`requests` from the venv
  for HTTP-layer persistence proofs and adversarial probes; direct `~/.kimcad/designs/` filesystem
  inspection for on-disk ground truth.
- **JPEG note:** the JPEG screenshot tool, which has historically timed out in this environment,
  **worked this run** — I captured rendered desktop and mobile screenshots of the gallery. Visual
  checks are therefore both DOM/computed-style-based AND screenshot-confirmed.
- **Assumptions / blockers:** demo mode returns a fixed "box" part with no LLM call, so the model
  pipeline itself was not exercised (out of Slice-1 scope). Two designs pre-existed the audit
  (`59a3fec5…` "box", `fe589c3c…` "box (copy)") and were preserved; all designs I created were
  cleaned up (see end).

## Project Gestalt

KimCad turns a plain-English prompt into a printable 3D part (describe → 3D → live sliders →
printability/readiness → slice → download). Pre-Stage-8.5 the SPA was **entirely in-memory**: a
refresh wiped the current part and there was no library of past work — a flat deal-killer for
repeated use. **Slice 1** adds local-first persistence and a "My Designs" library:

- A best-effort, never-raises **`DesignStore`** persists each design under
  `~/.kimcad/designs/<id>/` as `meta.json` (payload + serialized plan + template family) + `mesh.stl`
  + optional `thumb.png` (a viewport canvas capture). Writes are serialized + atomic; ids are
  ASCII-token-guarded against traversal; the library is capped at 200 with oldest-pruning.
- A set of **JSON/binary endpoints** in `webapp.py`: `GET /api/designs` (gallery index),
  `GET /api/designs/<id>` (reopen → re-register into live state, restore sliders),
  `POST /api/designs/save` (auto-save current part; updates-in-place via `saved_id`),
  `…/rename` · `…/duplicate` · `…/delete`, `GET …/<id>/export` (.kimcad zip),
  `POST /api/designs/import` (zip body → new id), `GET …/<id>/thumb`.
- A **hash-routed SPA**: `#/` workspace, `#/designs` gallery, `#/design/<id>` a real per-design
  address (linkable, reload-survivable, back-button-aware). A Topbar "My Designs" link + a live save
  indicator. The gallery is a thumbnail grid with name + date, per-card Open/Rename/Duplicate/
  Export/Delete, plus Search, Sort, Import, and empty/no-match states.

The UI promises: your work stops vanishing, and you can come back to it. **Observed live, it
delivers on that promise.**

## Findings By Severity

### Critical
None found.

### High
None found.

### M-1 Card action buttons fall below the recommended mobile touch-target size

- **Severity:** Medium
- **Location / route:** `#/designs` (gallery), mobile viewport (375×812)
- **Element or workflow:** `.kc-design-act` buttons — Rename / Duplicate / Export / Delete on each design card
- **What the user sees:** A compact single row of four small text buttons under each card.
- **What actually happens:** Computed height ≈ **25px** (`height: 25.39px`, `min-height: auto`,
  `font-size: 12px`), measured widths Rename 55px, Duplicate 63px, Export 100px, Delete 47px. These
  are well under the 44×44px (WCAG 2.5.5 / Apple HIG) touch-target guideline. The buttons *function*
  on mobile, but are easy to mis-tap, and adjacent (Export ↔ Delete) — a mis-tap on a destructive
  control.
- **What should happen:** Per the Stage 8.5 plan, the gallery + **card actions** should be "usable"
  on a phone, and the task brief explicitly calls for card action buttons to "meet a real touch
  size." Slice 9 ("Mobile actually usable" / "Accessibility sweep") is the formal home for this, but
  it's worth flagging now because the buttons are already present and small.
- **Evidence:** `preview_inspect .kc-design-act` → `{height: 25.3906px, min-height: auto,
  font-size: 12px}`; bounding boxes at 375px viewport = 55×25 / 63×25 / 100×25 / 47×25; mobile
  screenshot shows the four actions on one tight row. No horizontal overflow (`scrollWidth ==
  clientWidth == 375`), so this is purely target *size*, not layout breakage.
- **Likely cause:** The action buttons use a small text-button style with no `min-height`/touch
  padding floor; fine on desktop pointer, undersized for touch.
- **Suggested fix:** On the gallery card actions, set a `min-height: 44px` (and adequate horizontal
  padding) at mobile breakpoints, or convert to larger tap chips; add spacing between Export and the
  destructive Delete. Defer the formal sweep to Slice 9 if preferred, but track it.
- **Suggested test coverage:** A Playwright mobile-viewport assertion that each `.kc-design-act`
  bounding box is ≥44px tall at 375px width.

### L-1 The Open tap-target's accessible name and label can drift after rename (cosmetic label lag)

- **Severity:** Low
- **Location / route:** `#/designs`, design card Open button (`.kc-design-open[aria-label="Open …"]`)
- **Element or workflow:** The big thumbnail/Open button's `aria-label`.
- **What the user sees:** Nothing visibly wrong.
- **What actually happens:** Cards with a saved `thumb.png` render `<img>` inside the Open button
  (empty text, aria-label "Open box"); cards without a thumb render a **text fallback** showing the
  name. Both are correct — but it means the Open control's *visible* affordance differs between
  thumbed and un-thumbed cards (image vs. text). For the two pre-existing thumb-less designs the
  desktop grid shows a plain "Box" text tile rather than a 3D preview.
- **What should happen:** Consistent affordance; ideally a generated placeholder thumbnail for
  imported/legacy designs that lack `thumb.png` so the grid reads uniformly.
- **Evidence:** Desktop screenshot — cards 4–5 (`59a3fec5…`, `fe589c3c…`, `has_thumb:false`) show a
  text "Box" tile while cards 1–3 show rendered 3D thumbnails; DOM: thumbed Open button has
  `<img src="/api/designs/<id>/thumb">`, un-thumbed has text.
- **Likely cause:** Thumbnails are only captured on a UI save; designs imported via the API or
  created before the thumbnail path existed have no `thumb.png`, and the fallback is a text tile.
- **Suggested fix:** Render a neutral generated placeholder (or a server-side STL render) for
  thumb-less designs so the grid is visually consistent.
- **Suggested test coverage:** A test asserting a card with `has_thumb:false` still renders a
  non-empty visual placeholder, not blank.

### L-2 Reopen triggers an immediate re-save POST (one extra write per open)

- **Severity:** Low
- **Location / route:** `#/design/<id>` on reopen / reload-restore
- **Element or workflow:** Reopen flow → auto-save.
- **What the user sees:** Nothing — the design reopens and shows "Saved · My Designs".
- **What actually happens:** On every reopen/reload, after `GET /api/designs/<id>` and
  `GET /api/mesh/<rid>`, the SPA fires an additional `POST /api/designs/save`. It correctly updates
  **in place** (verified: design count did not increase, no duplicate dir created), so it's harmless
  — but it's a redundant write (and a fresh `thumb.png`/mesh copy) on a pure read/open.
- **What should happen:** Opening a design shouldn't need to immediately re-persist it unless the
  user changes something.
- **Evidence:** Network trace on reload — requests 35 (`GET …/<id>`), 37 (`GET /api/mesh/2`), then 41
  (`POST /api/designs/save`); on UI import-open, request 59 (`POST …/save`) after the reopen. Disk
  count stayed constant (no duplicate), confirming in-place update.
- **Likely cause:** The save effect runs whenever a design becomes the active part, including on
  restore, not only on user-initiated change.
- **Suggested fix:** Gate the auto-save on an actual change (dirty flag) rather than on mount/restore.
- **Suggested test coverage:** An integration test asserting that reopening a design issues no
  `POST /api/designs/save` until a parameter is changed.

### L-3 Empty/loading/error library states not all reachable in demo mode (partially verified)

- **Severity:** Low
- **Location / route:** `#/designs`
- **Element or workflow:** Empty state ("nothing saved yet"), loading state, error state.
- **What the user sees:** With designs present, the grid; with a non-matching search, a clean
  "No designs match …" message (verified).
- **What actually happens:** I verified the **no-match** empty state renders correctly. The
  **fully-empty** library state ("make your first part") and the **load-error** state were not
  reachable without deleting all designs (including the user's pre-existing two, which I would not
  touch) or forcing a store failure. The store degrades to an empty list on read failure by design
  (`DesignStore.list()` never raises), so the error path collapses into the empty path.
- **What should happen:** Per the Slice 1 spec ("a sensible empty state"), the zero-designs state
  should show first-run copy.
- **Evidence:** No-match: `main` text = `No designs match "zzzznomatch".` with 0 cards. Empty/error
  states: unverified live (see Confidence and Gaps).
- **Likely cause:** N/A — coverage gap, not a defect.
- **Suggested fix:** None required; add the test below to lock the empty-state copy.
- **Suggested test coverage:** A Playwright test against a temp empty `~/.kimcad/designs` asserting
  the first-run empty-state copy renders.

## Missing Or Partial Features

Measured against `docs/stage-8.5-usability-plan.md` Slice 1:

- **Persist designs locally (plan/params/mesh/thumbnail/name/timestamp)** — Implemented & working.
  On-disk `meta.json` carries id/name/prompt/created_at/object_type/gate_status/readiness_score/
  template_family/payload/plan; `mesh.stl` + `thumb.png` present.
- **Auto-save current design + restore on reload** — Implemented & working. Reload restored the part
  + 4 sliders; landing prompt absent (not blank).
- **URL routing / real address per design (back/refresh/linkable)** — Implemented & working.
  `#/design/<id>`, back-button returns to prior route, refresh restores via `GET /api/designs/<id>`.
- **"My Designs" library (thumbnail grid, name+date, click to reopen w/ sliders)** — Implemented &
  working.
- **Rename / duplicate / delete** — Implemented & working (all three persist; two-step delete arms
  "Delete?").
- **Export / import a design file** — Implemented & working (export = real `application/zip` .kimcad,
  PK bytes, 3 members; import = new coexisting entry that opens).
- **Sort + search + sensible empty state** — Search + Sort (Newest/Oldest/Name) working; no-match
  empty state working; fully-empty / first-run state present in spec but unverified live (L-3).

No Slice 1 feature is missing or non-functional. One sub-item (first-run empty state) is unverified
rather than absent.

## Backend Or System Capabilities Not Surfaced

- **Library cap / oldest-pruning (`_MAX_DESIGNS = 200`)** — real backend behavior with no UI
  surface (no "X of 200" indicator or pruning notice). Acceptable; noted for completeness.
- **`gate_status` / `readiness_score` in the index** — returned by `GET /api/designs` per entry but
  not shown on the gallery card (cards show name + date only). A small opportunity to surface
  printability at a glance; not a defect.
- **`prompt` stored per design** — persisted in `meta.json` and returned on reopen, not shown in the
  gallery. Minor.

## Confusing Or Misleading UI

- None material. The save indicator copy ("Saving…", "Saved · My Designs") is honest and matches the
  real state. Error copy on the adversarial paths is plain-English and friendly ("That design
  couldn't be found.", "Design the part first, then save it.", "That file isn't a valid KimCad design
  export."). The two-step Delete ("Delete" → "Delete?" → removes) is a clear, safe destructive
  pattern.
- Minor: thumb-less cards showing a text "Box" tile next to richly-rendered thumbnails reads slightly
  inconsistent (see L-1).

## Broken Or Suspicious Wiring Map

| UI element or workflow | Expected system connection | Actual connection | Status | Evidence |
| --- | --- | --- | --- | --- |
| Submit prompt "box" (workspace) | `POST /api/design` → build + register mesh | Request fires → 200; `GET /api/mesh/1` 200; URL → `#/design/<id>` | Working | net 20/22; hash `#/design/2291c671…` |
| Auto-save current design | `POST /api/designs/save` → write `~/.kimcad/designs/<id>/` | 200 `{saved:true}`; dir w/ meta.json+mesh.stl+thumb.png on disk | Working | net 25; `meta.json` 3550B + `thumb.png` 10476B |
| Save indicator (Topbar) | Reflect real save lifecycle | `kc-savestate-saving` "Saving…" during POST → `kc-savestate-saved` "Saved · My Designs" at persist | Working (not a timer) | live sample t=480 Saving… → t=720 Saved + hash flip |
| Reload page on `#/design/<id>` | `GET /api/designs/<id>` reopen → restore part + sliders | 200; canvas re-renders; 4 sliders restored; landing box absent | Working | net 35/37; sliders [80/60/40/2mm] |
| Topbar "My Designs" | Route to `#/designs` + active state | `#/designs`; button gets `kc-btn-active` + `aria-current="page"`; `GET /api/designs` 200 | Working | inspect: `activeRoute:"designs"`; net 17 |
| Open (card) | `GET /api/designs/<id>` → reopen | Pushes `#/design/<id>`; mesh re-served | Working | net 56/58; hash `#/design/8a93183e…` |
| Inline Rename | `POST …/<id>/rename` → meta.json name update | 200; re-list shows "box-renamed-audit" | Working | net 45; API re-list confirms new name |
| Duplicate | `POST …/<id>/duplicate` → new dir, fresh ts, " (copy)" | 200; count 3→4; new entry sorts newest; thumb copied | Working | net 47; new id `7793536d…` "… (copy)" |
| Export (.kimcad) | `GET …/<id>/export` → zip download | 200 `application/zip`; `Content-Disposition: attachment …kimcad`; PK; members meta/mesh/thumb | Working | HTTP probe: 11939B, `b'PK'` |
| Import (UI file input) | `POST /api/designs/import` → new id + open | 200 new id; coexists (count→); opens `#/design/<new>` | Working | net 51/56/58; id `8a93183e…` |
| Two-step Delete | `POST …/<id>/delete` → rmtree | Arms "Delete?"; confirm → 200; dir gone from disk + API (count 6→5) | Working | net 69; disk + API both confirm removal |
| Search | Client filter on name | "copy" → 1 of 5; "zzzznomatch" → 0 + "No designs match" | Working | filtered counts; no-match copy |
| Sort (Newest/Oldest/Name) | Client reorder | Each mode reorders distinctly | Working | Name=A–Z order; Oldest=pre-existing first |
| Browser Back | History pop → prior route | design→back→`#/designs`; design→back→`#/` (workspace) | Working | history.back() observed |
| Bad/absent/traversal id (reopen/rename/delete/dup/export/thumb) | Guard → clean 4xx | All 404/400, friendly JSON, no 500, no traceback | Working (safe) | HTTP probes table |

No row is Broken, Mocked, Missing, or Wrong-target. Every Slice 1 control is **Working**.

## Test Assessment

- **Current coverage:** `tests/test_design_store.py` — 20 passing unit tests over the `DesignStore`
  (save/get/list/rename/delete/duplicate/export/import, traversal guard, pruning). This proves the
  store layer well.
- **What it proves:** The persistence primitives are correct in isolation (atomic write, traversal
  rejection, zip-slip/zip-bomb resistance, prune cap).
- **What it does not prove (gaps):**
  - **No web-layer test for the persistence endpoints** — I found `tests/test_design_store.py` but
    no `test_webapp*`/endpoint test exercising `/api/designs/*`. The HTTP contract (status codes,
    in-place save via `saved_id`, the reopen→re-register flow, the 4xx guards) is unverified by the
    suite; I verified it live instead.
  - **No E2E/Playwright coverage** of the create→auto-save→reload-restore journey, the gallery CRUD,
    or the save-indicator state machine — the highest-value user journeys are untested in CI.
  - **No persistence round-trip test through the web layer** (write via `POST /save`, read back via
    `GET /api/designs/<id>`).
  - **No empty/error-state test** for the gallery (L-3).
- **Highest-value tests to add (ranked):**
  1. *(guards H/blocker-class regressions)* A web-layer test asserting bad/absent/traversal ids on
     reopen/rename/delete/duplicate/export/thumb return 4xx (not 500) with no traceback — API layer.
  2. *(guards the core promise)* A Playwright E2E: submit prompt → assert `POST /api/designs/save`
     fired and a dir exists → reload → assert part + sliders restored — E2E.
  3. *(guards in-place save)* A web-layer test that two saves of the same live design with the same
     `saved_id` yield exactly one design dir — API/integration.
  4. *(guards M-1)* A mobile-viewport Playwright assertion that `.kc-design-act` targets are ≥44px
     tall — E2E.
  5. *(guards L-3)* An empty-`~/.kimcad/designs` test asserting the first-run empty-state copy — E2E.

## Recommended Repair Plan

1. **Immediate blockers** — None. Slice 1 is shippable from a wiring standpoint.
2. **Core wiring fixes** — None required; all flows are wired and persist.
3. **Feature completion** — Verify/confirm the fully-empty first-run library state copy (L-3);
   consider surfacing `gate_status`/`readiness_score` on cards (enhancement, not required).
4. **UI/UX cleanup** — M-1 (mobile touch targets on card actions; separate destructive Delete);
   L-1 (placeholder thumbnail for thumb-less designs); L-2 (skip redundant re-save on pure reopen).
5. **Test coverage** — Add the five ranked tests above; the web-layer endpoint test (#1) and the
   create→reload-restore E2E (#2) are the two that would most cheaply lock in what I verified by hand.

## Confidence And Gaps

- **Fully audited (browser + network + disk evidence):** create→auto-save→persist; reload-restore of
  part + sliders; save-indicator state machine; `#/designs` routing + active state; Open/reopen;
  inline Rename (persisted, re-listed); Duplicate (new entry, sorts newest); Export (real zip via
  HTTP); Import (UI file-input flow → coexisting entry that opens); two-step Delete (armed + removed
  from disk/API); Search (match + no-match); Sort (all three modes); browser Back; desktop 1280 +
  mobile 375 layout; console + network health; adversarial 4xx/traversal probes.
- **Partially audited:** Sort "Newest first" was the default and verified by contrast; I did not
  re-toggle back to it explicitly (left on Oldest at end of sort test) — the reorder behavior is
  proven. The fully-empty and load-error gallery states (L-3) were reasoned from code but not driven
  live (would require deleting the user's pre-existing designs or injecting a store failure).
- **Unreachable in demo mode:** the real LLM design pipeline (demo returns a fixed box — out of
  Slice 1 scope); a forced save *failure* path ("retrying" copy) — I confirmed by code read
  (`webapp.py:943` returns the 503 "…your work is still here; retrying." and the indicator has a
  retrying class) but did not force a live failure.
- **Unverified:** frontend JSX-level wiring (the app ships minified; I verified behavior, not
  source). To confirm at source level would require the unminified frontend or a source map.
- **Note on test harness:** A few search/sort interactions needed React's `_valueTracker` reset to
  register synthetic input; this is a test-driver artifact, not a product bug — the same controls
  filtered/sorted correctly when driven via Playwright's native fill and via the value-tracker reset.

## Appendix

### Commands run
- `pytest tests/test_design_store.py -q` → 20 passed.
- `kimcad.cli web --demo` (preview harness → port 8765; manual instance on 8772 stopped).
- Python `urllib` probes against `http://127.0.0.1:8765/api/designs*` (export/import round-trip,
  re-list verification, adversarial id/traversal/garbage probes).
- `ls ~/.kimcad/designs` + `cat meta.json` for on-disk ground truth.

### Notable logs and errors
- Browser console: **no logs** (no errors/warnings) across the full session.
- Network: **no failed requests** (all 200/304; deliberate adversarial 4xx via direct HTTP only).

### Adversarial probe results (all clean 4xx, no 500, no traceback)
```
reopen absent      404 {"error":"That design couldn't be found."}
rename absent      404 {"error":"That design couldn't be found."}
delete absent      404 {"error":"That design couldn't be found."}
duplicate absent   404 {"error":"That design couldn't be found."}
export absent      404 {"error":"Not found."}
thumb absent       404 {"error":"Not found."}
reopen ../../../   404  (traversal id rejected by _safe_id)
reopen foo/bar     404
rename empty name  400 {"error":"Give the design a name."}
save bad/missing id 400 {"error":"Design the part first, then save it."}
import junk        400 {"error":"That file isn't a valid KimCad design export."}
import empty       400 {"error":"Empty upload."}
```

### Screenshots
- Mobile 375×812 gallery (single-column, real 3D thumbnails, save indicator "Saved · My Designs",
  active "My Designs" button) — captured inline during audit.
- Desktop 1280×800 gallery (multi-column grid; thumb-less pre-existing cards show "Box" text tile) —
  captured inline during audit.
- (JPEG screenshot tool worked this run; no fallback needed.)

---

## Remediation — 2026-06-03

All four findings addressed (0 Critical / 0 High / 1 Medium / 3 Low → 0/0/0/0).

- **M-1 (Medium) — FIXED.** The card-action 44px touch floor was previously gated only on
  `@media (pointer: coarse)`, which a desktop browser resized to 375px never reports — so the audit
  correctly measured ~25px. Added the same floor (`min-height: 44px` + wider gap + Delete pushed to
  the row end) under `@media (max-width: 640px)` in `styles.css`, so a narrow/phone-sized viewport
  gets tappable card actions regardless of pointer type. (A real px-height assertion needs the
  browser/E2E layer — jsdom doesn't lay out CSS — so it's tracked for the CI-E2E watchlist below.)
- **L-1 (Low) — FIXED.** Thumb-less cards (imports / legacy designs) now render a cube glyph + the
  type as an intentional "no preview yet" placeholder (`.kc-design-thumb-empty`), so the grid reads
  consistently next to rendered thumbnails instead of bare text.
- **L-2 (Low) — FIXED.** Added a `restoredRef` guard in `App.tsx`: a freshly reopened/restored
  design no longer fires a redundant `POST /api/designs/save` on its model-ready (it's already saved
  and unchanged); the next real edit (a re-render) clears the guard and re-saves in place. New test
  `does not re-save on a pure reopen until the user edits (L-2)` pins it.
- **L-3 (Low) — already covered; no code change.** The fully-empty first-run state and the
  load-error state were unreachable live only because that would mean deleting Scott's pre-existing
  designs. Both are already unit-tested in `MyDesigns.test.tsx` (`shows the empty state when there is
  nothing saved`; `surfaces a load error`), so the copy is locked at the unit layer.

**Correction to the Test Assessment.** The "no web-layer test for the persistence endpoints" note
was because the audit ran only `pytest tests/test_design_store.py`. `tests/test_webapp.py` does
exercise the `/api/designs/*` HTTP contract — the full create→save→list→reopen→export→import→delete
round trip, in-place save via `saved_id`, reopen-with-restored-sliders, the bad/absent/traversal id
4xx guards, mutate-id 404s, and a concurrent-save convergence test. The genuine gap is a **CI
Playwright E2E** of the browser journeys (create→reload-restore, gallery CRUD, the save-indicator
state machine) — that does not exist and is the right home for the M-1 px assertion; tracked on the
next-sprint watchlist (the per-slice `wiring-audit` covers it in the meantime).

**Verification:** vitest 67 passed (was 66, +1 for the L-2 test); `tsc` + `build` clean; committed
SPA assets regenerated; backend suite unaffected. **Roll-up after remediation: 0/0/0/0 (no
Blocker/Critical/High/Medium/Low open).**

### Cleanup
- Designs created during this audit and **deleted** afterward: `2291c671…`, `4906ad0c…`,
  `8a93183e…`, `7793536d…` (already deleted in-test via the UI), `b3a34f97…`.
- Pre-existing designs **preserved**: `59a3fec5…` ("box"), `fe589c3c…` ("box (copy)").
- Demo server stopped; ports 8765 and 8772 freed.
- `.claude/launch.json` port was pointed at the running demo for the preview harness (audit config,
  not product source).
- Scratch files `_audit_export_test.kimcad` / `_audit_export_b64.txt` (under `C:\dev\Claude`) removed.
