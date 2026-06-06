# KimCad (Stage 4 — React SPA shell + viewport) — Playwright Interface Wiring Audit

> Audited 2026-06-05 · branch `stage-0-7-audit-backfill` @ `b45298c` · auditor: Claude (independent, audit-only mode)
> Target driven: the LLM-free demo instance at `http://127.0.0.1:8765/`

## Executive Summary

**Verdict: the Stage-4 surface is genuinely wired end to end — not cosmetic.** Every core step of the primary flow (generate → render in the 3D viewport → adjust via live sliders → slice → export, plus persistence and reopen) was exercised against the running demo and proven with real network requests, state mutations, and re-query-after-action. The React SPA shell, hash routing (`#/`, `#/designs`, `#/settings`, `#/design/<id>`), the vanilla-Three.js viewport, the right-panel cards, autosave, and the My Designs library all reach the backend and persist. The console was clean (zero errors/warnings) across the whole walkthrough; every observed request returned 200. The 262 frontend tests pass and 108 `test_webapp.py` tests lock the API wiring — including a full `test_live_web_design_then_slice_then_download` E2E.

The one substantive defect found is a **responsive (mobile) overflow in the persistent top bar**: at the spec'd mobile width (390px), `.kc-topbar-actions` does not wrap (`flex-wrap: nowrap`, no mobile media rule), so the brand + action buttons need ~464px and overflow the viewport by ~90px, producing horizontal page scroll on every workspace route. This is Medium — the shell chrome is on every screen — and the fix is a small CSS change.

Beyond that, findings are Low (polish / a non-Stage-4 STL-format caveat in copy). No Critical or High wiring gaps were found: I specifically hunted for dead controls, mocked-as-real flows, missing persistence, and gate-bypass and found none. The demo's fixed-part behaviour and absent live LLM are intentional and are NOT flagged.

A real environmental caveat shaped the session and is recorded honestly in Confidence & Gaps: three KimCad servers were running concurrently (8765/8766/8767) and a second live session was independently driving the same `localhost:8765` backend through the same shared preview-Chrome. This periodically navigated my page mid-action (e.g. a prompt I typed was overwritten by another session's prompt). I worked around it by capturing each wiring proof in single, self-contained steps and by confirming wiring via the API directly where the UI context was churned out from under me. It did not change any verdict, but it prevented a couple of multi-step UI captures (a live screenshot of the rendered slice-result card, and the experimental-offer card), which I instead proved at the API + code level.

## Methodology

- **Reviewed (code):** `frontend/src/App.tsx`, `useHashRoute.ts`, `api.ts`; components `Workspace`, `Topbar`, `Landing`, `ChatPanel`, `RightPanel` (incl. `ParametersCard`/`ReadinessCard`/`PrintabilityCard`), `ExportPanel`, `VersionRail`, `MyDesigns`, `SettingsPanel`, `FirstRunWizard`, `Viewport`; the served bundle wiring (`src/kimcad/web/index.html`, `web/assets/*`); backend routes + `DemoProvider` in `src/kimcad/webapp.py`; `styles.css`; `ROADMAP.md` (Stage 4 §).
- **Reviewed (docs/design intent):** ROADMAP Stage 4 goal/exit, the inline component contracts.
- **App launch:** did NOT start a server — drove the pre-running LLM-free demo at `http://127.0.0.1:8765/` (registered to the preview tool as `serverId d994560c…`, port 8765).
- **Tests run:** `npm test` (vitest) in `frontend/` → **262 passed / 23 files**, exit 0. Counted backend tests: `test_webapp.py` = 108 test fns, `test_frontend.py` = 9; 36 backend test files total. (Did not run the full pytest suite — out of Stage-4 wiring scope and the demo already exercises the live stack.)
- **Browser coverage:** landing, FirstRunWizard (Welcome + AI-model steps + Skip), the design flow → workspace, slider re-render, Export card, My Designs library + reopen-by-click, Settings route, deep-link reopen (`#/design/<id>`), demo error scenarios (`demo:gatefail`, `demo:experimental`), desktop (1280) and mobile (390/375) viewports.
- **Tools:** Claude Code preview tools (`preview_snapshot/click/fill/eval/inspect/network/console_logs/resize/screenshot`) against the demo serverId; `curl` for direct API verification of slice/g-code/thumb/scenario payloads. Per the known limitation, keyboard-only features and React-controlled inputs were driven via the native-value-setter + dispatched `input`/`change` events (which reach React's root listener); persistence verified by reopen + direct API.
- **Artifacts:** evidence dir `docs/audits/stage-4/backfill-2026-06-05/wiring-evidence/` (screenshots captured inline in this session). No product source/docs/tests modified. No scratch scripts left behind.
- **Blockers/assumptions:** see Confidence & Gaps (concurrent servers + shared preview context; the preview-tool server handle dropped near the end of the session).

## Project Gestalt

KimCad is a local-first "describe a part in plain English → get a print-ready file" web tool: a Python stdlib HTTP server (`webapp.py`) serves a compiled React/TS/Vite SPA as static assets and exposes a JSON API. The primary user flow is: **landing prompt → POST `/api/design` (plan → OpenSCAD → printability gate → orient) → mesh streamed to a dark Three.js viewport → adjust template parameters via live sliders (debounced POST `/api/render/<id>`, deterministic, no model) → slice with bundled OrcaSlicer (POST `/api/slice/<id>`) → download STL/3MF.** Work autosaves to a local design store ("My Designs") and is reopenable by hash deep-link. The model is `gemma4:e4b` via local Ollama; cloud (OpenRouter) is an opt-in fallback. Stage 4's scope is the **app shell + routing + viewport** and wiring the existing flow through it; Stages 5/7/8.5 layered on live sliders, the readiness engine, and the library/settings/wizard. The demo provider returns a fixed `snap_box` template part (so sliders + gate + readiness all exercise real geometry) and offers keyword scenarios (`demo:gatefail`, `demo:experimental`) so the error/offer states are reachable without a model.

Live observation refined the model: the served `/assets/kimcad.js` is the real 194KB production bundle (the on-disk 7-line `web/assets/kimcad.js` is a dev stub; `Workspace.js` is the 564KB lazy chunk) — the viewport bundle is code-split and only fetched on first design, exactly as `App.tsx` intends.

## Findings By Severity

### M-1 Top bar overflows the viewport on mobile widths (no flex-wrap)
- **Severity:** Medium
- **Location / route:** every route (the shell `header.kc-topbar`); observed on `#/design/<id>` and applies app-wide.
- **Element or workflow:** `.kc-topbar-actions` (Saved indicator + My Designs + Settings + ? + New design; printer chip hidden ≤560px).
- **What the user sees:** at phone widths the action buttons run off the right edge; the page gains a horizontal scrollbar and the right-most control ("New design") is partially off-screen.
- **What actually happens:** `.kc-topbar-actions` is `display:flex; gap:10px` with **no `flex-wrap`** (defaults to `nowrap`) and there is no mobile media rule to wrap/collapse it. Measured at `clientWidth=390`: actions box width 343, right edge at **480** (90px past the viewport); `document.scrollWidth` **480 > clientWidth 390** → horizontal overflow. Brand (121) + actions (343) need ~464px vs a 390px viewport. The printer chip is correctly hidden ≤560px (`styles.css:1953`) but that alone doesn't recover the fit.
- **What should happen:** the shell must not introduce horizontal scroll at the spec'd mobile width. ROADMAP Stage 4 calls for the "§5 design at high fidelity"; the design system is UI-first (per Scott's standing UI priority). The bar should wrap, collapse to an overflow/menu, or shrink controls on narrow screens.
- **Evidence:** `preview_eval` at clientWidth 390 → `{actionsRight:480, actionsWidth:343, flexWrap:"nowrap", overflowX:true, docScrollW:480}`; with chip hidden, visible action kids = Saved 55 / My Designs 72 / Settings 74 / ? 32 / New design 69 + brand 121 → sumNeeded 464. CSS: `frontend/src/styles.css:176-180` (`.kc-topbar-actions` — no wrap); chip hide at `styles.css:1953-1957`. Mobile workspace screenshot captured this session.
- **Likely cause:** the topbar was tuned for desktop; mobile media work covered the chip and the in-content mobile CTA (`styles.css:1959-1977`) but not wrapping the action row itself.
- **Suggested fix:** add `flex-wrap: wrap; justify-content: flex-end;` to `.kc-topbar-actions`, and/or a `@media (max-width: 480px)` rule that collapses secondary buttons (Settings/?) behind an overflow control or reduces their padding; ensure `header.kc-topbar` allows the row to wrap (two-line topbar) without clipping. Verify `document.scrollWidth <= clientWidth` at 360/390px.
- **Suggested test coverage:** a viewport/responsive test (Playwright or a jsdom layout assertion) asserting no horizontal overflow of the shell at ≤390px on the landing and workspace routes — there is currently no responsive/overflow test for the topbar.

### L-1 STL download copy says STEP/BREP "arrive with the CAD engine" — forward-looking promise in shipping UI
- **Severity:** Low
- **Location / route:** workspace right panel → Export & print card.
- **Element or workflow:** the formats note under "Download 3D model (.STL)".
- **What the user sees:** "STEP and BREP precision formats arrive with the CAD engine."
- **What actually happens:** accurate as intent, but it advertises a not-yet-shipped capability in the released beta UI; a user could read it as imminent.
- **What should happen:** either keep (acceptable roadmap signalling) or soften to avoid implying a dated commitment.
- **Evidence:** `frontend/src/components/ExportPanel.tsx:191-195`.
- **Likely cause:** deliberate roadmap teaser.
- **Suggested fix:** optional — phrase as "planned" rather than "arrive with", or drop until the engine lands.
- **Suggested test coverage:** none warranted (copy).

### L-2 `.kimcad` export is a sibling action to a print export and can read as "another download format"
- **Severity:** Low
- **Location / route:** `#/designs` → each design card.
- **Element or workflow:** "Export (.kimcad)" link beside Rename/Duplicate/Delete.
- **What the user sees:** an "Export (.kimcad)" link; the title attribute clarifies it's a re-importable backup, not a printable STL.
- **What actually happens:** correctly wired (`/api/designs/<id>/export` → zip; verified the endpoint and round-trips with Import). The only risk is conceptual confusion with the print/STL export in the workspace.
- **What should happen:** fine as-is; the tooltip already disambiguates ("a .kimcad backup you can re-import — not a printable STL").
- **Evidence:** `frontend/src/components/MyDesigns.tsx:147-154`; `api.ts:459-490` (export/import + size cap).
- **Likely cause:** naming overlap between "export the project" and "export a print file".
- **Suggested fix:** optional — label "Backup (.kimcad)" to fully separate it from print export.
- **Suggested test coverage:** existing import/export tests suffice.

## Missing Or Partial Features

No missing or broken Stage-4 features found. Everything the Stage-4 surface promises is implemented and wired:

- **App shell + hash routing** — `#/` (landing), `#/designs`, `#/settings`, `#/design/<id>` all reachable and functional; deep-link reopen restores the part, the prompt thread, and the live sliders (verified: a 150mm width edit survived a full reopen). *Implemented & working.*
- **3D viewport** — real mesh loaded from `/api/mesh/<id>`, dim pills projected from the bbox (showed 80/60/40, updated to 150/60/40 on re-render), auto-orient chip, drag/zoom hint. *Implemented & working.*
- **Primary flow generate→render→adjust→slice→export** — all five steps proven with live requests (see Wiring Map). *Implemented & working.*
- **Persistence / autosave / My Designs** — autosave on model-ready and coalesced on slider settle; library lists newest-first with real thumbnails; reopen/rename/duplicate/delete/import/export all wired. *Implemented & working.*
- **Demo error/offer states** — `demo:gatefail` → `gate_failed` (model still downloadable), `demo:experimental` → `needs_experimental` offer (not auto-run). *Implemented & working.*

(Settings, wizard, readiness, live sliders, photo on-ramp are post-Stage-4 surfaces; all observed working too.)

## Backend Or System Capabilities Not Surfaced

- **`POST /api/send/<id>` (direct-to-printer send)** exists in the backend route table (`webapp.py:1021`) and connector status is surfaced (the Export card shows `ConnectorStatus`), but there is no live "send to printer" button in the Stage-4 UI — by design: ROADMAP defers the full direct-print/send UI to Stage 10, and `ExportPanel.tsx:17` says so explicitly. Not a defect; noted for completeness.
- No other backend capability appeared stranded: options/settings/health/model-status/connectors/progress are all consumed by the UI.

## Confusing Or Misleading UI

- None rising above Low. The two Low items (L-1 STL/STEP copy, L-2 .kimcad export naming) are the only mild ambiguities. Labels match behaviour elsewhere (gate "Passed" vocabulary is consistent across Printability and Compare cards; the Saved indicator and My Designs link are deliberately de-duplicated per UX-013).

## Broken Or Suspicious Wiring Map

| UI element or workflow | Expected system connection | Actual connection | Status | Evidence |
| --- | --- | --- | --- | --- |
| Landing "Design it" | POST `/api/design` → plan/gate/mesh | Fires; returns completed payload + `/api/mesh/<id>` | Working | net `POST /api/design` 200; payload had plan+report+template+params+mesh_url |
| Viewport render | GET `/api/mesh/<id>` → Three.js mesh | Canvas present, dim pills 80/60/40, plate-down chip | Working | net `GET /api/mesh/1` 200; eval `{canvas:true, dimPills:["80 mm","60 mm","40 mm"]}` |
| Live slider (Width) | debounced POST `/api/render/<id>` → cache-busted mesh | Re-render fired; label + viewport pill → 150mm | Working | net `POST /api/render/1` 200 then `GET /api/mesh/1?v=1`; eval widthLabel "150mm", dimPill "150 mm" |
| Autosave | POST `/api/designs/save` on model-ready + on settle | Two saves (create then coalesced edit); URL → `#/design/<id>`; Topbar "Saved" | Working | net 2× `POST /api/designs/save` 200; eval saveState " Saved", hash `#/design/<id>` |
| Slice & prepare file | POST `/api/slice/<id>` → OrcaSlicer → 3MF | `sliced:true`, 88210 g-code lines, est ~1h22m, `gcode_url:/api/gcode/1` | Working | curl POST `/api/slice/1` 200 (1.1s); response carries filename `part_bambu_p2s_pla.gcode.3mf` |
| Download print file | GET `/api/gcode/<id>` → 3MF bytes | 200, `model/3mf`, 193,376 bytes | Working | curl `GET /api/gcode/1` → 200 image/3mf 193KB |
| Download 3D model (.STL) | href = current mesh_url | `/api/mesh/1?v=1` (tracks re-render) | Working | eval downloadStl "/api/mesh/1?v=1" |
| Gate-failed refusal | gate fail → slice disabled, model still downloadable | `gate_failed`, has_mesh:true; `canSlice` false on `gate_status==='fail'` | Working | curl `demo:gatefail` → status gate_failed; `ExportPanel.tsx:72-78` |
| Experimental offer (no template) | status `needs_experimental` → offer, not auto-run | Returned needs_experimental, has_mesh:false | Working | curl `demo:experimental` (experimental:false) → needs_experimental |
| My Designs library | GET `/api/designs` + per-card thumbs | 25 cards, newest-first, real PNG thumbs | Working | net `GET /api/designs` 200; thumb 200 image/png 14,967 bytes; eval cards 25 |
| Reopen (card click) | GET `/api/designs/<id>` → restore part+thread+sliders | Workspace restored; 150mm edit persisted; original prompt shown | Working | net `GET /api/designs/645d…` 200 → mesh+connectors; eval params ["150mm","60mm","40mm","2mm"], userMsg original |
| Deep-link reopen | `#/design/<id>` on load → reopen effect | reopen fetch + mesh fired (verified in net) | Working | net `GET /api/designs/645d…` + `Workspace.js` + `GET /api/mesh/2` |
| Topbar printer chip | GET `/api/options` → name + build volume | "Bambu Lab P2S 256×256×256 mm" | Working | snapshot chip aria-label; net `GET /api/options` 200 |
| Settings route | GET `/api/settings` + `/api/model-status` + `/api/health` | 7 cards; AI "Running"; Tools both "Installed"; v0.1.0 | Working | eval cards list; modelStat "Running"; toolStats ["Installed","Installed"] |
| First-run wizard | `/api/model-status`; persist printer; localStorage flag | Renders gemma4:e4b "Ready"; Skip sets `kc-first-run-done=1` | Working | eval firstRunFlag "1" after Skip; wizard step shows model "Ready" |
| Topbar action row (mobile) | wrap/fit at ≤390px | overflows by ~90px (no flex-wrap) | **Broken (responsive)** | M-1; eval overflowX true at clientWidth 390 |

Status legend: Working · Partial · Broken · Mocked · Missing · Wrong-target.

## Test Assessment

- **Frontend:** 262 vitest tests across 23 files pass (App, api, all components, hooks). This is strong unit/integration coverage of the SPA logic and component rendering.
- **Backend:** `test_webapp.py` (108 tests) covers the routes I exercised — design/render/slice/mesh/save/reopen/import/export/gcode/options/settings/health/connectors — including behaviour-level checks: `test_live_web_design_then_slice_then_download` (the exact primary flow), `test_web_refuses_to_slice_a_gate_failed_part`, `test_rerender_invalidates_a_cached_slice`, `test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale`, `test_slice_is_idempotent_one_real_slice_per_key`, eviction/concurrency. These are real wiring/behaviour tests, not render-only.
- **What the suite proves vs not:** it proves the API contracts and the SPA's logic in jsdom. It does **not** prove **responsive layout** — there is no test asserting the shell doesn't overflow at mobile widths (this gap is exactly what let M-1 ship). There is also no true browser-level E2E (Playwright) of the click-through flow; coverage relies on jsdom + the live demo. Click-to-type on a slider value and the experimental-offer-card button are covered by component tests but not by a browser E2E.
- **Highest-value tests to add (ranked):**
  1. **Responsive/overflow guard for the shell at ≤390px** (catches M-1) — Playwright or a layout assertion; the only test tied to a real defect found here.
  2. A browser **E2E happy path** (generate→slider→slice→download) to lock the integration the demo proves but no automated browser test does.
  3. A deep-link **reopen E2E** asserting a persisted slider edit survives `#/design/<id>` reload (the persistence proof I did by hand).

## Recommended Repair Plan

1. **Immediate blockers** — none. The app is shippable from a wiring standpoint.
2. **Core wiring fixes** — none (all primary-flow wiring verified working).
3. **Feature completion** — none in Stage-4 scope (direct-send UI is intentionally Stage 10).
4. **UI/UX cleanup** — **M-1** (topbar mobile overflow: add `flex-wrap`/mobile collapse); optionally **L-1**, **L-2** (copy/label clarity).
5. **Test coverage** — add the responsive-overflow guard (catches M-1), a browser E2E for the primary flow, and a reopen-persistence E2E.

## Confidence And Gaps

- **Fully audited (exercised end to end with evidence):** landing → design submit; viewport mesh load; live slider re-render; autosave + Topbar saved state; My Designs list + reopen-by-click (persistence of a 150mm edit confirmed); Settings route data wiring; first-run wizard (Welcome + AI-model step + Skip persistence); slice → g-code download (via API, with response payload + file bytes verified); gate-fail and experimental-offer scenarios (via API payloads); desktop (1280) and mobile (390/375) topbar layout; console (clean) and network (all 200) across the walkthrough.
- **Partially audited:** VersionRail compare/undo/redo and the photo on-ramp (read in code and present in DOM/tests; not driven live this session because the shared preview context kept resetting multi-step flows). The Settings cloud-key save/replace and reset were read in code, not live-toggled. Wizard steps 3–5 (printer pick persistence, direct-printing choice, recap) were read in code; only steps 1–2 were driven.
- **Unreachable:** a **live, in-browser screenshot of the rendered slice-result (PrintSummary) card** and of the **experimental-offer card** — twice the slice click's UI result was navigated away by a concurrent session before it settled. Their wiring is nonetheless proven (slice: API `sliced:true` + real 193KB 3MF download; offer: API `needs_experimental` + `ChatPanel.tsx` render path). Near the end of the session the preview tool's server registration dropped (`preview_list` returned empty) while the backend stayed up at 8765; I did not restart the server (out of scope per instructions), so the final couple of captures were not retaken.
- **Unverified:** behaviour under a *real* (non-demo) LLM run, and real direct-print send — both out of this demo's scope by design. The full pytest suite was not run (counted, not executed); the frontend vitest suite was run green.
- **Environmental note (material to reproducibility):** three KimCad servers (8765/8766/8767) ran concurrently and a second live session drove the same `localhost:8765` backend through the same shared preview Chrome, intermittently navigating my page and overwriting inputs (e.g. my "a 50mm cube box" prompt surfaced as another session's "a QA bracket 100x50x30"). This is an environment artifact, not a product defect, and did not alter any verdict — but it is why several proofs were captured at the API layer and why a few UI screenshots were not retaken.

## Appendix

**Commands run**
- `npm test` (in `frontend/`) → 262 passed / 23 files, exit 0.
- `curl POST /api/slice/1 {printer:bambu_p2s,material:pla}` → 200, `sliced:true`, gcode_lines 88210, `/api/gcode/1`.
- `curl GET /api/gcode/1` → 200, `model/3mf`, 193,376 bytes.
- `curl GET /api/designs/<id>/thumb` → 200, `image/png`, 14,967 bytes.
- `curl POST /api/design {prompt:"demo:gatefail",experimental:true}` → `gate_failed`, has_mesh:true.
- `curl POST /api/design {prompt:"demo:experimental",experimental:false}` → `needs_experimental`, has_mesh:false.
- `curl GET /api/model-status` → `{model:gemma4:e4b, backend:local, running:true, model_present:true}`.
- `curl GET /api/health` → `{version:0.1.0, openscad:true, orcaslicer:true}`.

**Notable logs/errors**
- Browser console: **no logs** (zero errors/warnings) across the walkthrough.
- Network: all observed requests 200 (a single `GET 127.0.0.1:8767` ERR_ABORTED belonged to the *other* concurrent session, not the demo under test).

**Screenshots created (this session)**
- Desktop landing with FirstRunWizard (Workshop design system).
- Desktop workspace: viewport + conversation + Parameters + Readiness 92/100.
- Settings route (7 cards, Workshop styling).
- Mobile (390px) workspace showing topbar overflow (evidence for M-1) + mobile "Check & download" CTA.
- (Scratch screenshots intended for `docs/audits/stage-4/backfill-2026-06-05/wiring-evidence/`.)

**Setup notes for future auditors**
- The served `/assets/kimcad.js` is the real production bundle; the 7-line on-disk `web/assets/kimcad.js` is a dev stub — don't mistake it for a broken bundle.
- localStorage is per-origin: `localhost:8765` and `127.0.0.1:8765` are different stores (the first-run flag won't carry between them) — pick one origin and stay on it.
- If multiple KimCad servers are up, ensure only the demo (8765) is running before a live audit, or the shared preview Chrome will be driven by the other sessions.
- Drive React-controlled inputs/sliders via the native value setter + dispatched `input`/`change` events; `preview_eval` runs in an isolated world for *reads/dispatch*, and a dispatched real DOM event still reaches React's root listener (confirmed: the slider re-render fired).
