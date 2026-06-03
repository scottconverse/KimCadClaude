# UI/UX Deep-Dive - KimCad Stage 6 current main

**Audit date:** 2026-06-02  
**Role:** Senior UI/UX Designer  
**Scope audited:** Running demo web UI at `127.0.0.1:8766`, desktop viewport 1280 x 720, Stage 6 failure/status surfaces by source and tests.  
**Auditor posture:** Balanced

## TL;DR

The demo UI reached a coherent workspace state: conversation, live preview, dimensions, parameter sliders, printability report, connector status, printer/material selectors, and model download were all present with no console warnings/errors. The prior Stage 6 UX remediation for plan-failure and bake-off degenerate output is present in source/tests. Browser automation could not conclusively exercise a real slider drag or keyboard change, so this pass should not be treated as a full visual slider regression gate.

## Severity roll-up

| Severity | Count |
|---|---:|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 0 |

## What's working

- **First-run landing is understandable** - The page leads with a plain prompt field, examples, and a disabled submit until text exists.
- **Workspace hierarchy is clear** - The post-design screen separates conversation, 3D preview, parameters, printability, and export controls.
- **Failure-state remediation is present** - Source contains `isFailureStatus` paths in `RightPanel.tsx` so failed attempts no longer look like the untouched idle state.

## What couldn't be assessed

- Screenshot capture timed out in the Browser runtime.
- The Browser range-control automation did not conclusively reproduce a physical slider drag or keyboard increment. Direct `/api/render/<id>` verification proved the backend re-render path, but this pass cannot certify desktop/mobile pointer behavior.
- Mobile visual layout was not rendered in a mobile viewport during this pass.

## First impressions

The desktop demo reads like a working local design tool rather than a marketing shell. The status badge and printability table are visible without hunting. The "simulated" connector label is honest and useful.

## Journey walkthroughs

### Journey: prompt to printable demo part

1. Opened the local demo UI.
2. Entered `a 40 mm desk cable clip`.
3. Submitted the design.
4. Observed a workspace with a demo result, 3D preview, parameter sliders, pass-state printability report, and export controls.

Observed result: pass, no console warnings/errors.

## Findings

No UX findings.

## States audit matrix

| Component / page | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| Landing | Pass | Source-covered | Pass | N/A | N/A | Submit disabled until prompt exists. |
| Workspace | Pass | Source-covered | N/A | Source-covered | Pass | Demo result rendered cleanly. |
| Parameters card | Pass | Pass | Pass | Source-covered | Partial | Visual pointer/keyboard slider motion not conclusively exercised. |
| Printability card | Pass | N/A | Pass | Source-covered | Pass | Report table visible and readable. |

## Accessibility snapshot

- Keyboard navigation: not fully certified for sliders in this pass.
- Focus visibility: active slider surfaced in DOM snapshot.
- Screen reader labeling: sliders expose labels and `aria-valuetext` in `RightPanel.tsx`.
- Touch target size: not re-measured in this pass.

## Appendix: surfaces reviewed

- `http://127.0.0.1:8766/` demo UI
- `frontend/src/components/RightPanel.tsx`
- `frontend/src/components/Workspace.tsx`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`

