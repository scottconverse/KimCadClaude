# Audit Lite — Stage 4, Slice 5: printer/material → slice → download + connector status
**Date:** 2026-06-01
**Scope:** The Export & print flow — printer/material selectors, gate-aware slice-on-confirm (`/api/slice/<id>`), G-code + model download, and a read-only connector-status badge. `ExportPanel.tsx`, `ConnectorStatus.tsx`, `connectorStatus.ts`, `api.ts` (getOptions/getConnectors/getConnectorStatus/postSlice + designIdFromMeshUrl), tests. Branch `stage-4-react-spa-shell`. (Full direct-print/send UI = Stage 10; live sliders = Stage 5.)
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. The full text → plan → gate → slice → download flow works end-to-end — verified by a rendered check that produced a REAL OrcaSlicer estimate and a downloadable G-code. Gate-awareness holds on both the UI and the server, the connector status is honest about simulation, and the new logic is unit-tested. One UX Nit (a material `<select>` that briefly lagged a printer change) was found and fixed.

## Severity rollup (round 1)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 1

## Severity rollup (round 2 — after fix)
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0 → **0/0/0/0/0, gate cleared**

## Rendered visual check (mandatory for UI slices — done)
Designed a demo box, then exercised the real Export & print card at desktop + mobile: connector "mock · Ready · simulated" (green dot), Printer = Bambu Lab P2S, Material = PLA; clicking **Slice & prepare file** produced a live OrcaSlicer estimate ("~50m 20s, 200 layers, 33.63 cm³ filament") plus a **Download G-code** button and a **Download 3D model (STL)** link. Mobile stacks the card cleanly.

## Findings (fixed this pass)

### UX-501 Nit: material select could briefly show a stale/blank value on a printer change
**Dimension:** UX · **Evidence:** `material` was separate state corrected by a `useEffect` that runs *after* render, so for one render after switching to a printer with a different material set (e.g. one without TPU), the controlled `<select value={material}>` held a value not in its options — a blank flash and a React "value not in options" console warning. **Fix:** derive an always-valid `selectedMaterial` (user pick → configured default → first available) and bind the select + slice call to it, dropping the correcting effect. No lag, no warning. **(Fixed; build + vitest green.)**

## What's working
- **Gate-aware, belt-and-suspenders:** the UI refuses to slice a `gate_status === 'fail'` part (renders an inspect-only message, no slice controls) AND the server independently refuses (`gate_status_by_rid` → reason `gate_failed` in webapp.py). A failed part can still download the model to inspect.
- **Honest connector status:** `connectorStatus.ts` maps the typed snapshot to green/amber/red + a label, marks a loopback "Ready · simulated" (never narrates a mock as a real print), degrades offline/busy/auth/config honestly, and `ConnectorStatus.tsx` renders nothing on no-connector / unreadable-list — never crashes, renders only name+tone+label (no credential surface).
- **Robust id + race handling:** `designIdFromMeshUrl` parses the trailing id and returns null for missing/odd urls (unit-tested); the slice button is disabled while slicing; a new design clears the previous slice; the only re-design path unmounts the panel, so a stale slice can't display.
- **Real test coverage:** vitest `connectorStatus.test.ts` (tone/label incl. simulated + offline) + `api.test.ts` (designIdFromMeshUrl, getOptions, postSlice asserts the POST target) — 12 vitest cases across 3 files; the Python connector-status contract test reinstates the readiness-field check (W2, per Scott's Slice-5 plan).
- **a11y:** each select is wrapped in a `<label>` (implicit association), the connector label is `role="status"`, downloads are real `<a>` links; selects get a focus-visible ring.
- **Green:** ruff clean; `bash scripts/ci.sh` green (full pytest incl. live + vitest 12); build clean, no orphans; `npm audit` = 0.

## Watch items
1. **W9 — surface a "couldn't load printers" state.** `getOptions` failure is silent (the model download still works). On localhost it ~never fails, so the graceful degradation is fine, but a small notice would be friendlier if a future config error breaks options.
2. **W10 — slice-result cancelled-guard if in-place re-design ever lands.** Today the only re-design path unmounts ExportPanel, so an in-flight slice can't clobber a newer design. If a future slice adds in-place re-design (no unmount), add a generation guard like the viewport's `loadToken`.

## Escalation recommendation
No escalation needed — but this is the **last Stage-4 slice**, so the next step is the Stage-4 `audit-team` (Audit Full) gate over the whole branch, which is the right place for the cross-cutting pixel-level UI review + a fresh adversarial pass before merge + tag.
