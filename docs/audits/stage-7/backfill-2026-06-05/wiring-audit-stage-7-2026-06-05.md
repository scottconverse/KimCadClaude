# KimCad Stage 7 (Smart Mesh readiness report) — Playwright Interface Wiring Audit

> Audited 2026-06-06 · branch `stage-0-7-audit-backfill` @ `800016a` · auditor: Claude (audit-only mode)
> Surface: the Smart Mesh **Readiness report card** in the right panel (`frontend/src/components/RightPanel.tsx` → `ReadinessCard`/`ReadinessBody`).
> Live target: LLM-free demo at http://127.0.0.1:8765/ (preview serverId `cfa2b84b…`).
> Evidence dir: `docs/audits/stage-7/backfill-2026-06-05/wiring-evidence/`.

## Executive Summary

**The Readiness card is genuinely wired, not cosmetic.** Every visible element — the 0-100 score gauge, the plain verdict, the confidence badge, the risks list, the recommendations, the history line, and the attribution — is rendered directly from the design response's `report.readiness` object, which the pipeline synthesizes in `smart_mesh.assess_readiness`. I proved this end to end against three distinct live states whose values differ exactly as the backend computes them: a clean box (**92 / "Ready to print" / pass**), a gate-failed oversized cube (**38 / "Not print-ready" / fail, with 2 real gate-derived risks**), and an injected PrintProof3D-located risk (**74 / "Printable with notes" / warn / High confidence**). No hardcoded or stubbed values were found in the card; the gauge dash array equals the score (`"<score> 100"`) in every case.

**The card is honestly advisory, and the gate stays the slice authority.** The verdict is computed as the worst of KimCad's own tone and PrintProof3D's tone (`smart_mesh.py:164-182`), so "Ready to print" is never shown over a risk. The separate Printability card continues to own the gate verdict ("Gate: Passed/Failed"), and Export/Slice gating is driven by gate status, not by the readiness score. The card honestly states when PrintProof3D did **not** run: confidence drops to "Medium" and attribution reads "via KimCad printability gate" rather than claiming the engine. Confidence/comparison gracefully degrade (Medium, no history line) — they never invent a baseline.

**The one path not exercisable in the live demo is the geometry-located risk** (risks shown ON the model with click-to-focus). It requires a configured PrintProof3D binary, which the demo (and any install without the engine) does not have — `config.printproof3d_binary()` returns `None`, so `validate_model` returns `None` and no risk ever carries `geometry`. I verified that wiring by injecting a PrintProof3D-shaped located risk into one live response: the "Show on model" toggle, the legend, the locatable risk **button**, and the `onFocusRisk` → viewport focus call all rendered and fired with no console errors. The actual 3D raycast/highlight render against a *real* engine geometry payload remains unverified (engine not installed) — stated plainly, not papered over.

**Headline: the surface is fully wired and honest. The findings are all Low/Medium** — a test-coverage seam (the snake→camel API mapping is untested), the inherent in-demo unreachability of the engine path, and minor polish. No Critical or High findings.

## Methodology

- **Reviewed (code):** `src/kimcad/smart_mesh.py`, `src/kimcad/printproof3d.py`, `src/kimcad/history.py`, `src/kimcad/pipeline.py` (`_compute_readiness`, `_attach_history`, `_record_history`, `_fallback_readiness`), `src/kimcad/webapp.py` (`_readiness_payload`, `_report_payload`, `DemoProvider`, `build_web_pipeline`), `frontend/src/components/RightPanel.tsx`, `frontend/src/components/Workspace.tsx`, `frontend/src/components/Viewport.tsx`, `frontend/src/viewport/KCViewport.ts`, `frontend/src/api.ts`.
- **Launch:** preview server `kimcad-demo` already running on :8765 (demo/LLM-free). Repo lives at `C:\Users\scott\dev\kimcad` (the prompt's `C:\dev\kimcad` does not exist; confirmed and used the correct path).
- **Tests run:** backend `pytest tests/test_smart_mesh.py tests/test_printproof3d.py tests/test_history.py tests/test_pipeline_readiness.py` → **64 passed**; frontend `vitest run src/components/RightPanel.test.tsx src/components/Viewport.test.tsx` → **49 passed**.
- **Browser coverage:** preview tools (snapshot, eval/DOM measurement, click, network, console, resize, screenshot). Drove: default demo box, the `demo:gatefail` → experimental → gate-fail path, an injected PrintProof3D located-risk variant, mobile (375px) layout. preview_eval runs in an isolated world; all card readings are DOM measurements and the design payloads were re-fetched directly for authoritative shapes.
- **Blockers/assumptions:** PrintProof3D binary not configured in the demo (expected) → engine-on path verified by response injection, not by a real engine. The demo always builds a box regardless of prompt (LLM-free `DemoProvider`) — expected; the readiness card is the audited surface.

## Project Gestalt

KimCad is a local-first AI→3D-print web tool. **Smart Mesh (Stage 7)** is the synthesis + history layer atop the per-artifact Printability Gate: `assess_readiness(gate, mesh_report, material_name, printproof?)` is a pure function that turns the gate result, mesh integrity, the material, and an *optional* PrintProof3D report into a single `MeshReadiness` (score, verdict, tone, confidence, risks, recommendations, comparison, attribution, sources). PrintProof3D is an arm's-length subprocess engine (`validate_model`, never raises, returns `None` when absent) whose issues fold in as score penalties + risks + geometry. `HistoryStore` adds a factual "compared to your past parts" line, local-only and best-effort. The pipeline attaches the result as `report.readiness`; `webapp._readiness_payload` shapes it into JSON (mapping `issue_id`→`issueId`, forwarding `geometry`); `RightPanel.ReadinessCard` renders it; `Workspace` forwards located risks to the viewport for on-model highlight and click-to-focus.

## Findings By Severity

### M-1  API readiness-payload mapping (snake→camel + geometry) has no test at the boundary
- **Severity:** Medium
- **Location / route:** `POST /api/design` → `src/kimcad/webapp.py:96-122` (`_readiness_payload`)
- **Element or workflow:** the JSON seam between the Python `Risk` dataclass (`issue_id`, `geometry`, `region`) and the frontend `ReadinessRisk` (`issueId`, `geometry`, `region`).
- **What the user sees:** located risks are clickable ("⊙ on model") and focus the viewport — when the engine runs.
- **What actually happens:** the mapping is correct (`webapp.py:113` emits `issueId` from `r.issue_id`), but **no test exercises it.** `test_webapp.py` has zero readiness assertions; backend tests cover the dataclass (`issue_id`) and frontend tests feed a camelCase fixture (`issueId`) — neither crosses the seam. A future rename of either key (or dropping the `geometry` forward) would leave all 113 unit tests green while the live card silently loses click-to-focus and on-model highlighting.
- **What should happen:** an API-level test asserts that a readiness with a geometry-bearing risk serializes to `issueId`/`geometry`/`region` exactly as the frontend type expects (per `frontend/src/api.ts:20-27`).
- **Evidence:** `wiring-evidence/readiness-payloads.txt`; `grep readiness tests/test_webapp.py` → only 2 incidental `score`/`verdict` hits, none on the payload; mapping at `webapp.py:106-118`; fixture at `RightPanel.test.tsx:195-197`.
- **Likely cause:** Slice 8 added the camelCase mapping in webapp but the regression test landed only on the React side.
- **Suggested fix:** add a `test_webapp` case that builds a `MeshReadiness` with a `Risk(..., issue_id="OVERHANG_UNSUPPORTED", geometry={"type":"point",...})`, runs it through `_readiness_payload`, and asserts the camelCase keys + geometry passthrough.
- **Suggested test coverage:** API/integration — `tests/test_webapp.py::test_readiness_payload_maps_located_risk`.

### M-2  The PrintProof3D / engine path is unreachable in the demo, so its live wiring is unverifiable without the binary
- **Severity:** Medium
- **Location / route:** `_compute_readiness` `src/kimcad/pipeline.py:587-600`; `config.printproof3d_binary()`; `build_web_pipeline` `webapp.py:343-360`.
- **Element or workflow:** "Show on model" toggle, located-risk buttons, click-to-focus, High-confidence/"Validated by the PrintProof3D engine" attribution, on-model 3D highlight.
- **What the user sees (engine off):** Medium confidence, "via KimCad printability gate", no on-model controls — correct and honest.
- **What actually happens:** with no binary, `validate_model` returns `None`; risks never carry geometry; the entire on-model/click-to-focus UI is dormant. A hands-on demo walkthrough can never see Stage 7's headline feature.
- **What should happen (product intent):** the engine path is real and intended; for it to be demoable/auditable end to end without a PrintProof3D install, a demo seam (analogous to `DemoProvider` / `demo:gatefail`) should surface a canned engine report with geometry.
- **Evidence:** live demo box + `demo:gatefail` both returned `attribution:"KimCad printability gate"`, `confidence:"Medium"`, zero geometry risks (`wiring-evidence/readiness-payloads.txt`); injection-verified the UI conditional path renders and `onFocusRisk` fires (no console errors); pipeline gate at `pipeline.py:588-589`.
- **Likely cause:** by design — the engine is optional and the demo stays engine-free; no demo fixture exists for a located risk.
- **Suggested fix:** add a `demo:overhang` (or similar) `DemoProvider` scenario, or a test-only injectable PrintProof3D report, that yields one `geometry`-bearing risk so the on-model highlight + focus path is exercisable in the running app and in an E2E test.
- **Suggested test coverage:** E2E (Playwright) — design → located risk shows "⊙ on model" → click focuses viewport; plus a `KCViewport` unit test that a `point`/`bounding_box`/`triangles` geometry produces a highlight mesh.

### L-1  Recommendation set on a clean part is thin and printer-generic
- **Severity:** Low
- **Location / route:** card Recommendations; `smart_mesh.py:186-191`.
- **What the user sees:** a passing box shows a single recommendation, "Slice for PLA on the selected printer's profile."
- **What actually happens:** with no risks and no engine fixes, the only recommendation is the material/slice note (`smart_mesh.py:190-191`); the overhang/orientation note (`:188-189`) only fires when an overhang risk exists.
- **What should happen:** acceptable, but a single generic line under a prominent "Recommendations" heading reads slightly hollow on a clean part.
- **Evidence:** live box card `recs:["Slice for PLA on the selected printer's profile."]`; screenshot (captured in session, pass card).
- **Likely cause:** intentional minimal Slice-1 recommendation set.
- **Suggested fix:** consider hiding the Recommendations section when the only item is the generic slice note, or enrich it (e.g. estimated time/material). Product call.
- **Suggested test coverage:** none required; UX decision.

### L-2  History comparison wording is unverifiable live in the demo (history disabled)
- **Severity:** Low
- **Location / route:** `kc-readiness-history`; `webapp.py:357-359` (`history = None` in demo); `history.compare_phrase`.
- **What the user sees:** no "compared to your past parts" line in the demo.
- **What actually happens:** the demo runs with `HistoryStore=None` so the card never shows a comparison; the wording logic (personal best / on par / below all / stronger than N) is unit-tested only (`test_history.py`) and was confirmed to render via injection ("Stronger than 4 of your 6 past parts.").
- **What should happen:** fine for the demo (avoids polluting real history), but the live comparison wording is not auditable through the demo UI.
- **Evidence:** `webapp.py:359`; injection render; `test_history.py` (24 cases in the run).
- **Suggested fix:** none for the demo; optionally an E2E using a real (non-demo) pipeline with a seeded history file.
- **Suggested test coverage:** covered by `test_history.py`; an E2E would be nice-to-have.

## Missing Or Partial Features

- **On-model risk highlight + click-to-focus (Stage 7 §6.12, Slice 8):** *Implemented but only partially verifiable live* — present and wired in code (Workspace `highlights` useMemo → Viewport `setHighlights`/`setHighlightsVisible`/`focus`; KCViewport `setHighlights`/`focusHighlight`), unit-tested (Viewport.test.tsx forwards `setHighlights`/visibility; RightPanel.test.tsx asserts the focus call), but unreachable in the demo (M-2) and the real 3D raycast render is unverified without the engine.
- **PrintProof3D engine integration:** *Implemented, dormant in demo* — wrapper, profile generation, parsing, sanitization all present and tested (`test_printproof3d.py`), but the engine binary is absent so the High-confidence path never lights up live.
- Everything else on the card (gauge, verdict, confidence badge+blurb, gate-derived risks, recommendations, attribution, graceful degradation) is **Implemented and working**, verified live.

## Backend Or System Capabilities Not Surfaced

- `MeshReadiness.sources` (e.g. `["printability-gate","printproof3d"]`) is computed (`smart_mesh.py:134,150`) but **not** included in `_readiness_payload` (`webapp.py:101-122`) and not shown in the UI. Minor — the human-readable `attribution` covers the same intent; flagging as an unsurfaced field, not a defect.
- `PrintProofReport.confidence_level` (the engine's free-form confidence string) is parsed (`printproof3d.py:194`) but never surfaced; the card uses KimCad's own High/Medium/Low. Intentional, noting for completeness.

## Confusing Or Misleading UI

- None material. The card is honest: it never claims the engine ran when it didn't, never shows "Ready to print" over a risk, and labels gate-only assessments plainly. The confidence blurb ("From KimCad's printability gate." vs "Validated by the PrintProof3D engine.") correctly tracks the actual source.
- Minor (L-1): a lone generic recommendation under a bold "Recommendations" heading on a clean part.

## Broken Or Suspicious Wiring Map

| UI element or workflow | Expected system connection | Actual connection | Status | Evidence |
| --- | --- | --- | --- | --- |
| Score gauge (number + arc) | `report.readiness.score` → gauge num + `strokeDasharray="<score> 100"` | Exact match: 92/38/74 across states; dash = score | Working | DOM: `gaugeNum`/`dashArray` per state; `RightPanel.tsx:357-383` |
| Verdict text | `report.readiness.verdict` | "Ready to print"/"Not print-ready"/"Printable with notes" match | Working | DOM `verdict`; `smart_mesh.py:182` |
| Tone (card color) | `report.readiness.tone` (worst-of-two) | `kc-rtone-pass/fail/warn` match | Working | DOM `toneClass`; `smart_mesh.py:164-182` |
| Confidence badge + blurb | `confidence` (High/Medium/Low) | Medium (gate) live; High (engine) on injection; correct blurb | Working | DOM; `RightPanel.tsx:343-347,404-412` |
| Risks list | `readiness.risks[]` (gate + engine) | 0 / 2 / 1 risks match; gate risks plain, engine risk a button | Working | DOM riskCount/risks; `smart_mesh.py:139-158` |
| Risk → on-model highlight | located risk `geometry` → `KCViewport.setHighlights` | Wired; verified by injection; not reachable in demo | Partial | M-2; `Workspace.tsx:60-65,101-102`; `Viewport.tsx:127` |
| Risk click → focus viewport | `onFocusRisk(issueId)` → `focusRisk` → viewport `focus` | Fires, no error (injection); forces highlightsOn=true | Partial (verified via injection) | `Workspace.tsx:67-70,110`; `RightPanel.tsx:457` |
| "Show on model" toggle | `onToggleHighlights` → `showHighlights` → `setHighlightsVisible` | Flips state; only shown when a located risk exists | Partial (verified via injection) | `Workspace.tsx:112`; `RightPanel.tsx:418-427`; `Viewport.tsx:131` |
| Recommendations | `readiness.recommendations[]` | Matches (slice note live; engine fix on injection) | Working | DOM recs; `smart_mesh.py:186-191` |
| History line | `readiness.comparison` (HistoryStore) | null in demo → omitted; renders on injection | Working (demo: correctly absent) | `webapp.py:359`; injection |
| Attribution | `readiness.attribution` | "via KimCad printability gate" / "via PrintProof3D validation engine" | Working | DOM attr; `smart_mesh.py:219-225` |
| Gate authority (separate card) | `report.gate_status` | "Gate: Passed/Failed" independent of readiness score | Working | DOM gateBadge; `RightPanel.tsx:541-546` |
| API payload mapping | `Risk.issue_id`→`issueId`, `geometry` passthrough | Correct in code; **untested at boundary** | Working but untested | M-1; `webapp.py:106-118` |

## Test Assessment

- **Backend:** `test_smart_mesh.py`, `test_printproof3d.py`, `test_history.py`, `test_pipeline_readiness.py` → 64 passed. They prove the pure synthesis (gate→score, worst-of-two tone, penalties, confidence/attribution), the engine wrapper's degrade-never-raise contract + geometry sanitization, the history wording, and the pipeline attaching readiness/`_fallback_readiness`. Strong unit coverage.
- **Frontend:** `RightPanel.test.tsx`, `Viewport.test.tsx` → 49 passed. They prove the card renders each field, located-vs-non-located risk branching, the focus call, and the viewport forwarding `setHighlights`/visibility. Good behavioral (not just render) coverage.
- **Gaps:** (1) **the JSON seam** — `_readiness_payload`'s snake→camel + geometry forward is untested at the API layer (M-1); (2) **no E2E** drives the on-model highlight / click-to-focus against a running app (M-2), because the demo can't produce a located risk; (3) no test feeds the frontend a *snake_case* risk to confirm it would NOT silently render (guards against the mapping regressing).
- **Highest-value tests to add (ranked):** 1) API test of `_readiness_payload` with a located risk → catches M-1 (a silent loss of click-to-focus). 2) A demo fixture + Playwright E2E for the located-risk → focus flow → catches M-2 and locks the headline Stage-7 feature. 3) A `KCViewport` unit test that each geometry shape builds a highlight → catches a raycast regression the demo can't reach.

## Recommended Repair Plan

1. **Immediate blockers:** none.
2. **Core wiring fixes:** none — the surface is wired.
3. **Feature completion:** M-2 — add a demo seam (e.g. `demo:overhang`) so the engine/located-risk path is exercisable live and in E2E.
4. **UI/UX cleanup:** L-1 (recommendation density / optional hide), L-2 (no action for demo).
5. **Test coverage:** M-1 (API mapping test), then the E2E + KCViewport tests from Test Assessment.

## Confidence And Gaps

- **Fully audited (live, with evidence):** the pass card (box, 92/pass/Medium), the gate-fail card (oversized cube via experimental, 38/fail/Medium, 2 gate risks rendered plain), data-drivenness (3 distinct scores match backend), confidence/attribution honesty when the engine is off, history graceful absence, mobile (375px) layout, gate-as-authority separation, no console errors.
- **Partially audited:** the PrintProof3D engine path (High confidence, located risks, on-model toggle, click-to-focus, history line) — rendered and the focus/toggle handlers fired correctly via a **stubbed/injected** response, but not via a real engine.
- **Unreachable:** the actual PrintProof3D subprocess + a real engine `ValidationReport` with geometry; the live 3D raycast/highlight render against engine coordinates — blocked by no PrintProof3D binary in the demo install.
- **Unverified:** that a real engine geometry payload raycasts to the correct triangles/point on the model in the viewport (needs the binary or a demo fixture + E2E); that the API actually emits `issueId`/`geometry` for a real located risk end to end (needs M-1's test or a real engine run).

## Appendix

- **Commands:** `pytest tests/test_smart_mesh.py tests/test_printproof3d.py tests/test_history.py tests/test_pipeline_readiness.py -q` (64 passed); `npx vitest run src/components/RightPanel.test.tsx src/components/Viewport.test.tsx` (49 passed).
- **Live calls:** `POST /api/design` with `{"prompt":"a 40 mm desk cable clip"}`, `{"prompt":"demo:gatefail"}` (+ experimental opt-in); one injected `/api/design` response carrying a PrintProof3D-shaped located risk.
- **Screenshots (captured in session):** pass card (92/Ready), fail card (38/Not print-ready, 2 risks), injected engine card (74/Printable with notes, on-model toggle + located risk button). Payload evidence: `wiring-evidence/readiness-payloads.txt`.
- **Key code refs:** `smart_mesh.py:123-206` (synthesis), `:164-182` (worst-of-two tone), `pipeline.py:587-607` (engine gate + fallback), `webapp.py:96-122` (payload + camelCase map), `RightPanel.tsx:385-530` (card), `Workspace.tsx:56-113` (highlight/focus wiring), `KCViewport.ts:208-218` (highlight API).
- **Note for future auditors:** the repo is at `C:\Users\scott\dev\kimcad` (not `C:\dev\kimcad`). The demo never configures PrintProof3D, so the engine/located-risk path needs injection or a new demo fixture to audit live.
