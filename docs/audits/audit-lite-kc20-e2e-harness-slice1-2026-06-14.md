# Audit Lite — #25 (KC-20) Playwright e2e — Slice 1 (harness)
**Date:** 2026-06-14
**Scope:** The e2e harness + smoke journey: `tests/e2e/{__init__.py, conftest.py, test_smoke.py}` (new), the `needs_browser` probe/skip in `tests/conftest.py`, the `browser_serial`/`needs_browser` markers + dev deps in `pyproject.toml`, the Playwright provisioning step in `.github/workflows/ci.yml`, the `scripts/ci.sh` note, and the CONTRIBUTING docs.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. Slice 1 of #25 lands the e2e architecture (harvested from kimcadcodex, rebuilt for this repo's stdlib `kimcad web` server) + one smoke journey proving it end-to-end: real headless Chromium loads the real `kimcad web --demo` SPA, the landing renders, the session-token meta is substituted, and the console stays clean. Gated by `needs_browser` so non-provisioned environments skip; the provisioned gate runs it. One regression (a `conftest` module-name collision that broke the existing suite's `from conftest import BAMBU`) was caught during verification and **fixed in-pass**.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

(One Major regression was introduced and remediated within this pass before any commit — see Finding 001. Final state is 0/0/0/0/0; full collection 1478 tests, no errors.)

## Findings

### FINDING-001 Major (RESOLVED in this pass): a second `conftest.py` shadowed the top-level `conftest` module
**Dimension:** Tests
**Evidence:** Adding `tests/e2e/conftest.py` broke full collection with `ImportError: cannot import name 'BAMBU' from 'conftest'` for 7 modules. The existing suite imports shared fixtures via `from conftest import BAMBU, ...`; under pytest's `prepend` import mode (no package structure), the new nested `conftest.py` claimed the same top-level `conftest` module name and shadowed `tests/conftest.py`.
**Why it matters:** It would have red-lined the entire gate (collection failure), not just the e2e tests.
**Fix path (done):** Added `tests/e2e/__init__.py` so the subtree is a package and its conftest imports as `e2e.conftest` (not top-level `conftest`). Verified: full collection is clean (1478 tests, 0 errors); the 7 previously-erroring modules pass; the e2e fixtures still apply.

## What's working
- **Real wiring, not mocks.** The harness drives the **real** `kimcad web --demo` server in real Chromium — no DOM mocks, no stubbed APIs. Demo mode makes the design path deterministic without Ollama/slicer, and the per-boot session-token guard (#31) is live, so the e2e exercises the genuine token-injection flow (the smoke asserts the `<meta>` placeholder was substituted) rather than a bypass.
- **Console-clean contract.** Every test collects browser console errors/warnings **and uncaught page exceptions** (`pageerror`) and asserts none — so a journey proves the SPA is *wired*, not just that text rendered. The smoke ends with `console_errors == []` against the real server.
- **Environment-adaptive gating.** The `needs_browser` marker (a cached `sync_playwright` Chromium probe) skips cleanly where Chromium is absent (fresh clone, hosted fork-PR smoke), and runs on the provisioned gate — so it never green-by-skips under STRICT (ci.yml runs `playwright install chromium`) and never hard-fails elsewhere. Mirrors the existing `real_tool`/`needs_cadquery` discipline.
- **Installer kept pristine.** Playwright is deliberately **out of `requirements.lock`** (test-only browser tooling), so the user-facing installer's dependency set + release-strip are untouched — verified: ci.yml's installer-staging smoke needs no change. Provisioned via a pinned ci.yml step + the Chromium download a pip lock can't express.
- **No perturbation.** pytest-playwright installs cleanly alongside the suite; the existing 1476 tests collect + pass unchanged (1478 total with the 2 smoke tests).
- **Robust, not flaky.** The smoke uses Playwright's auto-waiting `expect(...)` + `page.goto` (no arbitrary sleeps); selectors are role/label-based (`get_by_role`, `get_by_label`), resilient to markup churn.

## Watch items
- **e2e in the main gate.** The suite runs inside the main `pytest` invocation (per the issue: "wire into the gate behind a marker"). Slice 1 adds ~6s; as journeys grow (design/refine, on-ramps, gate, settings, recovery), watch total gate time on the throttling box — if it bloats, split e2e into its own job.
- **The `needs_browser` probe is heavier** than the other marker probes (it starts a Playwright driver vs a cheap import/path check) — cached once per session, so acceptable, but if a future provisioning issue makes it fail it will *skip* (→ STRICT gate red, correctly forcing a fix).
- **Benign-console filter.** The watcher ignores `Failed to load resource: the server responded` (handled 4xx/5xx) — the proven kimcadcodex filter. It could in principle mask a genuinely broken asset load; journey slices should assert positive UI state too, not rely on console-clean alone.

## Escalation recommendation
No escalation needed. Test-infra + CI-provisioning slice; verified end-to-end (real server + real browser, 1478 collected clean); the one regression was caught pre-commit and fixed. Slice 1 of N — the journey slices (design/refine/sliders → on-ramps → gate/slice/download → settings/My-Designs/recovery) build on this harness, with `/audit-team` + `/walkthrough` at the #25 stage close.
