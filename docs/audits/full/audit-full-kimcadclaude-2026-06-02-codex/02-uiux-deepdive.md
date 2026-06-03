# UI/UX Deep-Dive - KimCadClaude full project

**Audit date:** 2026-06-02  
**Role:** Senior UI/UX Designer  
**Scope audited:** Current local React SPA in demo mode, design handoff/spec targets, source components for state coverage.  
**Auditor posture:** Balanced

## TL;DR

The current shipped SPA is a compact, usable Stage 6 experience: prompt, preview, parameters, printability, and export are visible in one desktop workspace. The broader v3.0 design is much larger than the current app, but the roadmap marks those surfaces as future work, so they are not defects in the current stage. No UX findings were raised in this pass.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **Clear first screen** - The landing page explains what to do and disables the primary action until a prompt exists.
- **Coherent workspace** - Conversation, viewport, parameters, printability, and export are separated into predictable regions.
- **Honest connector state** - The mock connector labels itself as simulated.
- **Printability language is useful** - The ready state names dimensional match, watertightness, volume fit, and wall thickness.

## What couldn't be assessed

- Mobile viewport was not tested in this pass.
- Screenshot capture was unavailable due a Browser runtime timeout in the earlier pass.
- A real physical pointer/touch slider drag was not conclusively reproduced through Browser automation, although the API and tests prove the re-render path.

## First impressions

The app feels like a local functional tool rather than a marketing page. It sets expectations clearly: describe, preview/refine, check/download.

## Journey walkthroughs

### Journey: demo prompt to exportable part

1. Opened the actual KimCad server on `127.0.0.1:9876`.
2. Entered `a 40 mm desk cable clip`.
3. Submitted the design.
4. Confirmed the workspace contained a 3D preview, parameter sliders, printability report, connector status, printer/material controls, slice action, and STL download link.

Result: pass. Browser console warnings/errors: none.

## Findings

No UX findings.

## States audit matrix

| Surface | Default | Loading | Success | Empty | Error | Notes |
|---|---|---|---|---|---|---|
| Landing | Pass | N/A | N/A | Pass | N/A | Submit disabled until prompt exists. |
| Workspace | Pass | Source-covered | Pass | N/A | Source-covered | Demo success path verified. |
| Parameters | Pass | Pass | Pass | Pass | Source-covered | Live re-render API verified separately. |
| Printability | Pass | N/A | Pass | Pass | Source-covered | Pass-state evidence verified. |
| Export/slice | Pass | Source-covered | Pass | N/A | Source-covered | API slice verified. |

## Accessibility snapshot

- Form input has an accessible label.
- Sliders have accessible labels and `aria-valuetext`.
- Printability table uses table semantics.
- Full keyboard/touch proof remains a next UI-gate item.

## Appendix: surfaces reviewed

- `http://127.0.0.1:9876/`
- `docs/design/README.md`
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md`
- `frontend/src/App.tsx`
- `frontend/src/components/RightPanel.tsx`
- `frontend/src/components/ExportPanel.tsx`
- `frontend/src/components/Viewport.tsx`

