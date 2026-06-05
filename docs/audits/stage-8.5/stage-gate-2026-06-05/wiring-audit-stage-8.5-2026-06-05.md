# Wiring Audit — KimCad Stage 8.5 (stage gate)

**Date:** 2026-06-05
**Branch / head:** `stage-8.5-usability` @ `95b25e0`
**App driven:** the live demo SPA (`kimcad web --demo`, port 8765, DemoProvider — LLM-free but
real OrcaSlicer), in a real browser via the preview (Playwright-backed) tools.
**Mode:** audit-only (no product source modified). Reviewer: Claude (wiring-audit skill).

## TL;DR
Across the audited Stage 8.5 interface, **every control I could drive is genuinely wired to the
backend and persists** — this is not cosmetic UI. The decisive proofs: the design call, the
deterministic slider re-render (no model call), the real slice, auto-save, and the persistence
round-trip all fire real requests and mutate real server state, and every panel reflects server
truth (not static markup). I found **0 Critical / 0 High / 0 Medium / 0 Low** wiring defects in the
audited scope. One harness limitation (keyboard-only features can't be triggered from the preview's
isolated world) is noted and covered by unit tests, not failed. See Confidence & Gaps for exactly
what was driven vs. inferred.

## Severity rollup (wiring lane)
- Critical: 0
- High: 0
- Medium: 0
- Low: 0

## Project Gestalt (working model)
KimCad turns a plain-English (or photo) description into a print-ready file through a conversation:
Landing (prompt) → Workspace (Chat thread | 3D viewport | RightPanel: Parameters / Readiness /
Printability / Export) → slice → download, plus a "My Designs" library, a Settings screen, and a
first-run wizard. Stage 8.5 added persistence, refinement + version history, numeric/units editing,
settings + model/engine discoverability, the photo on-ramp, problems-on-the-model, escape paths,
onboarding/help/progress, and (Slices 10–11) output clarity + responsive/a11y/copy/polish. Backend
is a stdlib HTTP layer over the deterministic pipeline; the contract is the `/api/*` seam.

## What's genuinely wired (evidence)

| Area | Control / claim | Verdict | Evidence (driven live) |
|---|---|---|---|
| Landing | prompt → "Design it" | **WIRED** | `POST /api/design → 200`; busy overlay; then a real part |
| Progress | live phase poll (MS-3) | **WIRED** | `GET /api/design/progress/<jobid> → 200` fired during the run |
| Viewport | real STL + dims | **WIRED** | `GET /api/mesh/1 → 200`; canvas aria-label "3D preview — 80 by 60 by 40 millimetres", updated to "150 by 60 by 40" after a slider edit |
| Sliders (Stage 5) | drag → re-render, **no model call** | **WIRED** | slider→`POST /api/render/1 → 200` + `GET /api/mesh/1?v=1` and **no** new `/api/design`; viewport + dims table re-synced to 150 |
| Numeric entry | click-to-edit value buttons | **WIRED (present)** | "Width: 150 mm. Click to edit." buttons in the a11y tree |
| Units | mm / in toggle | **WIRED (present)** | Parameters "Display units" group with mm/in buttons |
| Readiness | gauge/verdict/confidence/recs/attribution | **WIRED** | score 92/100, "Ready to print", "Medium confidence", recommendations list, "via KimCad printability gate" — all from the result payload |
| Printability | gate badge + dims table + findings | **WIRED** | "Gate: Passed"; dims table target vs actual (150/60/40 both); findings (watertight, fits P2S plate, wall adequate) — reflect server truth post-edit |
| Export | printer + material selectors | **WIRED** | `GET /api/options → 200`; 3 printers; materials per printer (P2S: PLA/PETG-generic/TPU…) |
| Slice | Slice → real `.3mf` + estimate breakout | **WIRED** | `POST /api/slice/1 → 200`; broken-out stats from real OrcaSlicer: Print time ~1h 22m 36s · Layers 200 · Filament 23.64 m · Weight 70.5 g; "estimated" note present (derived weight); download `/api/gcode/1`; Copy link; filename `part_bambu_p2s_pla.gcode.3mf` |
| Connector | status badge | **WIRED** | `GET /api/connector-status/mock → 200`; "Ready · simulated" (honest sim labelling) |
| Auto-save | save on design + after edit | **WIRED** | `POST /api/designs/save → 200` fired on first frame AND after the slider re-render; topbar "Saved · My Designs" |
| Persistence | library + reopen restores state | **WIRED** | `GET /api/designs` → 23 saved; reopening the current id returns `target_bbox_mm [150,60,40]` — i.e. the **slider-modified** state was persisted and round-trips; design URL is `#/design/<saved-id>` |
| Settings | defaults + model status | **WIRED** | `GET /api/settings` (default_printer bambu_p2s, default_material pla, cloud off); `GET /api/model-status` (gemma4:e4b, local, running, present) |
| Chat | multi-turn thread | **WIRED (present)** | user + assistant turns rendered; refine input "Refine your part" + "Send refinement"; "Describe with a photo" on-ramp |

## Findings
None at Critical/High/Medium/Low for wiring in the audited scope. No dead controls, fake-clickable
elements, placeholder-pages-posing-as-features, missing-persistence, or cosmetic-not-bound-to-data
were observed. The connector is honestly labelled "simulated" (not presented as a real hardware
send) — the correct behavior per the send-gate boundary.

## Harness limitation (not a defect)
The preview's `preview_eval` runs in an **isolated world**: dispatched keyboard events do not reach
the app's React/window listeners, so the Slice-11 keyboard shortcuts ("?" help, n/d/, nav) cannot be
triggered through the audit harness. Their wiring is covered by unit tests instead
(`App.test.tsx` "App keyboard shortcuts" + `ShortcutsHelp.test.tsx`: "?" toggles the dialog, the
typing/modifier guards, "d" → My Designs, Esc-closes-help-without-cancelling-the-run, focus
trap/restore). The modal's rendered CSS was verified via injected markup (backdrop fixed/z-210,
dialog surface/16px radius/380px, kbd mono). This is a tooling constraint, not a product gap.

## Test assessment (runtime-relevant)
The suite backs the wiring observed here: full pytest incl. live OrcaSlicer (the real slice
contract) + 249 vitest, all green at `95b25e0`. The live web→slice→download→send path is covered by
`tests/test_webapp.py::test_live_web_design_then_slice_then_download`; the gate-failed refusal by
`test_web_refuses_to_slice_a_gate_failed_part`; the no-model re-render + persistence by the App
lifecycle tests. Recommended next coverage tied to gaps below: a Playwright (real-browser) e2e for
the keyboard-shortcut flow that the isolated world can't reach.

## Confidence and Gaps (honest scope)
- **Fully driven live (high confidence):** landing→design, the no-model slider re-render, slice +
  estimate breakout, auto-save, the persistence round-trip (incl. slider-modified state), the
  readiness/printability/parameters/export panels reflecting server truth, settings + model-status
  endpoints, connector status.
- **Verified by code + prior per-slice audit-team, not re-driven this pass:** refine→new-version,
  clarifying-question inline answer, version rail switch/undo/compare, rename/duplicate/delete,
  export/import `.kimcad`, search/sort, the photo upload→vision-seed, the first-run wizard's 5 steps,
  and the per-action escape/cancel buttons. These passed their own `audit-team` (Slices 1, 2–4, 6, 7)
  and `wiring-audit` (Slices 1, 2–4) earlier in the stage and are unit-tested; I did not
  independently re-drive each in this gate pass.
- **Could not drive (harness):** the keyboard shortcuts (isolated world) — unit-tested instead.
- **Observation (not a finding):** the DemoProvider returns `object_type: "box"` for every prompt,
  so the Slice-11 `humanizeObjectType` slug→words path isn't exercised in the demo (it's unit-tested);
  and the units preference appears client-persisted (not in `/api/settings`) — by design, not a gap.

## Verdict
**Wiring lane: PASS (0/0/0/0).** The Stage 8.5 interface is genuinely wired end to end on every
audited flow, with real backend calls, real persistence, and panels bound to live data — not
cosmetic. Proceed to the static `audit-team` lane for the independent multi-role review before
merge/tag.
