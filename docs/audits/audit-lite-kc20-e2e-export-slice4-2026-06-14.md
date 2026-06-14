# Audit Lite — #25 (KC-20) Playwright e2e — Slice 4 (print path: gate + slice/download)
**Date:** 2026-06-14
**Scope:** The print-path journeys: `tests/e2e/test_export_gate.py` (new, 3 journeys), the `design_prompt` fixture in `tests/e2e/conftest.py`, and a `real_tool` marker retrofit on the design-triggering modules (`test_design_refine.py`, `test_onramps.py`).
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. Three journeys cover the print path end to end: a gate-passing part slices to a downloadable `.3mf` print file (and always offers the model download); an out-of-template prompt offers the sandboxed experimental generator; and a gate-failing part is refused slicing but still downloadable to inspect. All pass. A correctness retrofit (`real_tool` on the design journeys) makes the suite skip cleanly without OpenSCAD. No findings.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

## Findings
None. Two assertions were corrected against the live app before commit: (a) `demo:gatefail` does **not** route straight to a design — it offers the experimental generator in the conversation first (hence the new `design_prompt` fixture that submits without waiting for `/design/`); (b) the gate-fail copy appears in *both* the conversation and the Export panel, so the Export assertion targets the panel's unique "can't be sliced" note to avoid a strict-mode match on two elements.

## What's working
- **The whole print arc, real.** Gate-pass → Export tab → "Slice & prepare file" → "Print file ready" + the `.3mf` download link, driven by the real demo server (real OpenSCAD render; the small box slices quickly). The model `.STL` download is asserted present alongside.
- **The gate-fail path is honestly exercised.** `demo:gatefail` flows through the experimental-generator offer → opt-in → the part is generated but fails the build-volume gate; the journey asserts the conversation says so, the Export panel refuses slicing (`Slice & prepare file` has count 0), and the model is still downloadable to inspect — the exact "you can look but can't print this" contract.
- **Correctness retrofit.** Every design-triggering journey renders via the real OpenSCAD binary, so `test_design_refine` + `test_onramps` + `test_export_gate` now carry `real_tool` alongside `needs_browser` — they skip cleanly where the binary is absent (a chromium-but-no-OpenSCAD box), matching the suite's env-gating discipline, while still running on the provisioned gate (both present → no green-by-skip under STRICT).
- **Console-clean** on the gate-pass journey; resilient role/text selectors with generous timeouts on the slice (60s) and the sandboxed generate (30s).

## Watch items
- **The slice journey depends on a fast demo slice.** It currently resolves in ~2s; the 60s timeout gives ample headroom, but if a future OrcaSlicer pin slows cold slicing on the throttling box, watch this journey's wall-clock in the gate.
- **Send-to-printer is not yet covered** — the `SendPanel` (loopback connector + confirmations) is deferred to Slice 5 with settings / My Designs / error recovery.

## Escalation recommendation
No escalation. Test-only slice on the established harness; all 13 e2e tests (Slices 1–4) pass together, ruff clean. Slice 5 (settings, My Designs, send/error recovery) closes the journey set, then `/audit-team` + `/walkthrough` at the #25 stage close.
