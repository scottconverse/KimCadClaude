# Audit Lite — #25 (KC-20) Playwright e2e — Slice 5 (wizard, settings, My Designs, recovery)
**Date:** 2026-06-14
**Scope:** The final journey slice: `tests/e2e/test_wizard.py` (new, 2 journeys), `tests/e2e/test_settings_designs.py` (new, 3 journeys), and the `live_server` home-isolation + `design`-fixture timeout hardening in `tests/e2e/conftest.py`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship. Five journeys close the journey set: the first-run wizard walks through to the landing (and Skip dismisses it), a Settings toggle flips, a designed part is saved and reappears in My Designs, and a forced slice failure degrades gracefully with the model-download fall-back intact. Two real issues were found and **fixed in this pass**: the suite was writing to the **real** `~/.kimcad` (now isolated), and a cold-render flake (now hardened). The real-store pollution my earlier runs left was cleaned up.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · Minor: 0 · Nit: 0

(Two issues — one Major, one Minor — surfaced and were remediated within this pass. Final state is 0/0/0/0/0.)

## Findings

### FINDING-001 Major (RESOLVED in this pass): the e2e wrote to the real `~/.kimcad`
**Dimension:** Correctness / Runtime
**Evidence:** The `live_server` spawned `kimcad web --demo` with the inherited environment, so the designs/history/settings store resolved to the **real** `~/.kimcad`. The design journeys (Slices 2–5) saved every test part there (77 accumulated) and the Settings journey flipped `experimental_enabled` in the real `settings.json` — violating the standing "tests never touch real `~/.kimcad`" constraint. The My Designs journey was also non-deterministic because of the accumulated duplicates.
**Why it matters:** Test runs mutating real user state is a hard line; it also made the suite's My Designs assertion flaky.
**Fix path (done):** `live_server` now redirects the server's home to a throwaway `tmp_path_factory` dir (`USERPROFILE`/`HOME`), so the store is isolated per session and discarded. Verified: a full run adds **zero** designs to the real store. The earlier pollution was cleaned surgically — the 77 today-dated test designs (confirmed test prompts: 50× "a 40 mm desk cable clip", "demo:gatefail", the photo/sketch seeds) removed, the 14 pre-existing real designs (Jun 10–11) kept, and `experimental_enabled` reverted to its default (`False`), all other settings preserved. `history.json` was untouched (not modified today).

### FINDING-002 Minor (RESOLVED in this pass): a cold-render flake in the full suite
**Dimension:** Tests
**Evidence:** One full-suite run failed `test_a_typed_prompt_renders_a_parametric_part` (the first design); it passed in isolation and on re-run. The `design` fixture waited for the `Parameters` tab with the default 5s timeout, which a cold/under-load OpenSCAD render (the gate box thermally throttles) can exceed.
**Why it matters:** A flaky test in the blocking gate is exactly the kind of intermittent red the gate-integrity work fought to eliminate.
**Fix path (done):** Bumped the `Parameters`-tab wait to 30s in the `design` fixture. Two consecutive full-suite runs then passed 18/18 with stable timing (~22s).

## What's working
- **The onboarding flow is covered.** A fresh context (no first-run seed) shows the wizard; the journey walks Welcome → Set up AI → Pick printer → Direct printing → You're all set → "Start designing" to the landing, and the Skip-setup shortcut — the one flow the rest of the suite deliberately suppresses.
- **Settings + My Designs + recovery are real.** The Settings switch toggles and the change holds; a designed part auto-saves and is found in My Designs (a distinctive prompt makes it unambiguous in the isolated home); a server-side slice failure surfaces the `.kc-export-error` note while the Slice button returns to usable and the model download remains — recovery, not a dead end.
- **Honest error-recovery selection.** The recovery journey asserts the error *element* + the recovered state (button usable, fall-back present), not brittle error copy — verified against the live app (the server's message text varies).
- **Isolation proven, not assumed.** The fix was validated by checking the real store before/after a run (zero new designs), and the prior pollution was cleaned with confirmation that every removed item was a test artifact.

## Watch items
- **Session-scoped server shares settings.** The Settings toggle persists for the rest of the (isolated) session; future settings journeys should assert relative to their own change, not an absolute state.
- **First-design cold render** remains the slowest single step; the 30s fixture timeout covers it, but it's the journey to watch if the box slows further.

## Escalation recommendation
No escalation. This closes the #25 journey set (19 e2e journeys across Slices 1–5). Per the cadence, the next step is the **stage close**: `/audit-team` (0/0/0/0/0) + `/walkthrough` on the e2e-covered SPA — which #25 now enables — before #25 is closed.
