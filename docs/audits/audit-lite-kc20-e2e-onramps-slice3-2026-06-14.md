# Audit Lite — #25 (KC-20) Playwright e2e — Slice 3 (photo/sketch on-ramps)
**Date:** 2026-06-14
**Scope:** The photo + sketch on-ramp journeys: `tests/e2e/test_onramps.py` (new, 3 journeys) and the `sample_image` fixture (+ the 1×1 PNG constant) added to `tests/e2e/conftest.py`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. Three journeys drive the secondary on-ramps end to end: a photo upload returns an editable seed → "Use this as a starting point" → design; the same for a sketch; and the seed is editable before it drives the design (the edited text, not the canned read, reaches the workspace). All pass. No findings.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

## Findings
None. The journeys passed on the first run — grounded by reading the real flow: `PhotoOnramp` uploads to `uploadPhoto`/`uploadSketch`, and `DemoProvider.describe_photo`/`describe_sketch` (webapp.py) return **canned** seeds in demo mode (the image is ignored), so the upload → read → confirm → design path is deterministic without the CPU-bound vision model.

## What's working
- **Real upload, real wiring.** Files are set directly on the on-ramp's hidden `input[type=file]` (scoped by `.kc-onramp-photo` / `.kc-onramp-sketch`) — a genuine browser file upload through the real `uploadPhoto`/`uploadSketch` API to the real server, no stub. The journey proves the confirm card renders the read, "Use this as a starting point" feeds the design flow, and a part renders.
- **The editable-confirm contract is exercised.** The third journey edits the seed (`"a 25 mm hex standoff"`) and asserts the *edited* text drove the design (it echoes in the conversation log) — proving the confirm card is a correctable starting point, not a one-way pipe. This is exactly the honest-UX promise the on-ramp was built around (a photo carries no scale; the user adjusts).
- **Honest scope.** The journeys assert the *wiring* (upload → seed → design), not the vision model's reading accuracy — which is non-deterministic and the model's job (covered by the unit/benchmark suite). The docstring says so.
- **Self-contained fixture.** `sample_image` writes a real 1×1 PNG to `tmp_path` (no committed binary asset); demo ignores the content, so it's all the upload needs. Console-clean across all three.

## Watch items
- **Demo-seed coupling.** The journeys assert substrings of the canned demo seeds (`rectangular box`, `rectangular bracket`). Deterministic, but a change to those demo strings would require updating the assertions — the right place to notice such a change.
- **Real-mode vision path is not e2e-exercised** (it's CPU-bound + non-deterministic) — by design; the on-ramp's *model* behavior is covered by the Stage-9 benchmark, the e2e covers the UI flow.

## Escalation recommendation
No escalation. Test-only slice on the established harness; all 10 e2e tests (Slices 1–3) pass together, ruff clean. Slice 4 (print prep → gate fail/pass → slice/download) is next.
