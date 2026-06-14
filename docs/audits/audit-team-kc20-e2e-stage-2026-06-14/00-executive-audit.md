# Audit Team — #25 (KC-20) Playwright e2e stage close
**Date:** 2026-06-14
**Scope:** The Playwright e2e suite delivered as #25 (KC-20) across 5 slices — `tests/e2e/`, the `needs_browser`/`real_tool`/`browser_serial` gating, the ci.yml provisioning, and the CONTRIBUTING/ci.sh docs. A 4-role review (Principal Engineer, Test Engineer, QA Engineer, Technical Writer) run via Workflow, scoped to find what the per-slice audit-lites missed.

## Executive summary

The e2e suite is sound in its core design — real-server/real-browser, console-clean, honestly scoped — and the harness isolation + flake fixes from the per-slice audit-lites held up. But the holistic review surfaced **30 cross-cutting findings (13 Major / 12 Minor / 5 Nit)** that per-slice passes couldn't see: an output-isolation gap (the render tree still wrote into the repo), an order-dependent state contamination (the experimental toggle leaked into the session-shared server), a CVE-scan blind spot (playwright unaudited), a console filter that masked all 4xx/5xx, a slider assertion that could pass on render timing, real coverage gaps (send-to-printer, version-rail, mobile), and a cluster of doc inaccuracies. **All 30 are remediated; the suite is at 0/0/0/0/0.**

## Severity roll-up

| | Found | Remediated |
|---|---|---|
| Blocker | 0 | — |
| Critical | 0 | — |
| Major | 13 | 13 |
| Minor | 12 | 12 |
| Nit | 5 | 5 |
| **Total** | **30** | **30** |

## What's working (credited by the roles)

- **Home isolation is genuinely correct** — `USERPROFILE`/`HOME` redirect verified to take priority over `HOMEDRIVE`/`HOMEPATH` on Windows, so `Path.home()` resolves into the throwaway dir.
- **The console watcher is attached before navigation** (fixture-dependency ordering), and `pageerror` is captured unconditionally — the "nothing thrown" contract covers boot, not just post-load.
- **The session-token e2e is load-bearing** — it proves journeys POST through the real per-boot #31 guard, not a bypass.
- **Marker discipline is honest** — `needs_browser` is cached + explicit; `browser_serial` is documented as inert-under-default-runner; the `__init__.py` package shim correctly resolves the conftest module clash.

## Findings → remediation (all landed this pass)

**Major**
- **ENG-1** render output wrote into repo `output/` → added `--out` to `kimcad web`; `live_server` passes `--out <home>/output` (verified: repo `output/web` no longer grows). Docstring corrected.
- **ENG-2 / QA-1** experimental-toggle state leaked into the session-shared server (order-dependent) → the settings journey now toggles **both ways and restores** the flag; order-independent.
- **ENG-3** playwright unscanned by pip-audit → added a second ci.yml pip-audit over a freeze-derived list of the browser tooling (verified clean; a full-env audit chokes on the editable `kimcad`).
- **TEST-1 / QA-7** console filter masked all 4xx/5xx (and asset 404s) → narrowed to GL-driver noise only; a full run revealed **no** masked failures (the demo path is genuinely clean).
- **TEST-2 / QA-4** slider test could pass on initial-render timing → now waits for the dimensioned label first, then asserts the **width specifically increased**, with a 30s render-budget timeout.
- **TEST-3** real model path uncovered → documented explicitly as out-of-e2e-scope (suite header + CONTRIBUTING); covered by the unit/benchmark suites.
- **TEST-4** missing flows → added **send-to-printer**, **version-rail navigation** (Undo→Redo), and **mobile sticky-CTA** journeys; remaining lower-blast-radius gaps (measure/dark/keyboard/cloud) recorded + confirmed wired by the walkthrough.
- **QA-2** server-start failure was undiagnosable (stderr→DEVNULL) → capture child output to a file; the startup `RuntimeError` now carries the real traceback / "port in use" line.
- **QA-3** e2e wall-clock invisible → `--durations=15` on the gate pytest (slowest journey ~3.4s) + a coupling note.
- **DOC-1/2/3** CONTRIBUTING said "deterministic without the slicer" (wrong — most journeys need OpenSCAD/OrcaSlicer via `real_tool`), claimed a 2-marker invariant (4 modules add `real_tool`), and omitted `browser_serial` from the markers table → all corrected; `fetch_tools` added to the runnable block.

**Minor**
- **ENG-4 / DOC-4** version drift → pyproject pins `playwright==1.60.0`/`pytest-playwright==0.8.0` (matching the gate); ci.yml installs with `-c requirements.lock` so the post-lock install can't perturb the audited tree.
- **ENG-5** probe fail-closed on any error → retries once; prints the reason on a double-failure instead of a silent STRICT-red.
- **ENG-6** probe checked existence, not launchability → now launches + closes Chromium.
- **ENG-7** killed process unreaped → `wait(timeout=5)` after `kill()`.
- **TEST-5** slice-failure test was client-mocked but read as server coverage → renamed + docstring states it's a client mock; `real_tool` is for the design render.
- **TEST-6** refine asserted only the demo echo → now also asserts the version rail shows **v2** (the version-push wiring).
- **TEST-7** `browser_serial` overstated xdist safety → documented single-process requirement (table + docstring).
- **QA-5** My Designs matched a substring → now keyed to a **per-run UUID** prompt.
- **QA-6** wizard magic-6 loop → asserts each step **heading** in order, fails with a clear "which step" message.
- **DOC-5** ci.sh e2e comment undersold the `real_tool`/OrcaSlicer coupling → cross-referenced.

**Nit**
- **ENG-8** port TOCTOU → now diagnosable (the startup error includes the server's "port in use" line); per-session fresh port keeps collision risk negligible.
- **ENG-9 / QA-5** designs-store accretion → UUID prompt (above).
- **TEST-8 / QA-6** wizard brittleness → step-heading assertions (above).
- **QA-7 / TEST-1** asset-404 masking → narrowed filter (above).
- **DOC-6** `page`-fixture docstring lumped server state with browser state → corrected (browser state resets per test; server state persists per session).

## Verification

- Full e2e suite: **21 passed** (18 original + 3 new coverage journeys), `--durations` shows the slowest at ~3.4s.
- CLI: **33 passed** (incl. 2 new `--out` tests).
- `pip-audit` over the browser tooling: **no known vulnerabilities**.
- ruff clean; full collection clean (1499 tests); core modules (`test_webapp`, `test_shell`) unaffected.
- Output isolation + real-`~/.kimcad` isolation re-confirmed (no new writes to either).

The remaining authoritative proof is the full self-hosted gate on push (live OpenSCAD/OrcaSlicer/CadQuery + the e2e suite under STRICT no-skip). The companion **walkthrough** ([walkthrough-kc20-e2e-stage-2026-06-14.md](../walkthrough-kc20-e2e-stage-2026-06-14.md)) found the SPA fully wired across every uncovered flow.

**Verdict: 0/0/0/0/0. #25 closes on the gate's green.**
