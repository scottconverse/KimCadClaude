# Audit Lite — Stage 8.5 Slice 6 MS-1: Settings store + screen shell
**Date:** 2026-06-04
**Scope:** The first Settings micro-slice — a `~/.kimcad/settings.json` store (`settings_store.py`), `config.settings_path()`, the `/api/settings` GET/POST endpoints + `web_options` saved-default overlay (`webapp.py`), and the Settings screen shell (route + Topbar button + `SettingsPanel.tsx` with Printer/Material + Units), plus tests.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after two Minor fixes (applied + re-verified). The store is safe (only the two allowlisted keys persist; the POST validates printer/material against config and 400s an unknown value; everything is best-effort and never 500s) and the saved-default overlay is backward-compatible. Two Minors: no direct way to leave the Settings screen back to designing, and the store-absent degraded path lacked an endpoint test. Both fixed.

## Severity rollup
**As found:** 0 Blocker · 0 Critical · 0 Major · 2 Minor · 0 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: no direct path from the Settings screen back to designing
**Dimension:** UX
**Evidence:** `App.tsx` — `onWorkspace` excludes the `settings` route, so `showNewDesign` is false there; the Topbar offers only "My Designs" and "Settings" on that screen, and the KimCad brand wordmark (`Topbar.tsx`) is not interactive. From Settings the user can reach My Designs but has no one-click route back to the landing / a new design.
**Why it matters:** It's not a dead-end (My Designs is reachable, and it has its own "New"), but a settings screen you can't directly leave back to the main task is mild friction — and the same gap exists on the My Designs route.
**Fix path:** Make the brand wordmark a home link (navigate to the landing) — the conventional, expected affordance, and it resolves the escape from *both* Settings and My Designs in one place.
**Status:** ✅ Fixed — the brand is now a `<button class="kc-brand">` that navigates home; `onHome` threaded from App. A Topbar test asserts it.

### FOUND-002 Minor: the store-absent degraded path (`saved:false`) has no endpoint test
**Dimension:** Tests
**Evidence:** `webapp.py` `_handle_settings_post` returns `saved:false` when `get_settings_store()` is None (the store couldn't be built), and `SettingsPanel.tsx` shows an honest "didn't stick" error on it — but no backend test exercises the store-None branch, so a regression that silently flipped it to `saved:true` would pass.
**Why it matters:** The honest `saved` flag is the contract that stops the UI claiming "Saved" when persistence failed; it deserves a lock.
**Fix path:** Add a webapp test that monkeypatches the settings store to None (or `settings_path` into an unwritable location) and asserts the POST returns 200 with `saved:false` and doesn't 500.
**Status:** ✅ Fixed — `test_settings_post_reports_unsaved_when_store_unavailable` added (monkeypatches `get_settings_store` via a read-only path stand-in) → `saved:false`, 200, no 500.

## What's working
- **The store is safe by construction.** `update()` only writes `_ALLOWED_KEYS` (`default_printer`, `default_material`) — a crafted or stale client can't stuff arbitrary keys/nested data into the file (`test_update_ignores_unknown_keys` proves it). The POST handler independently validates each value against the live config printer/material keys, returning a clean **400** on an unknown value rather than persisting garbage. `None` clears an override back to the config default.
- **Best-effort, never breaks the app.** Every store read/write is wrapped: `all()` returns `{}` on a missing/corrupt/non-object file; `update()` returns `False` (a no-op) on any failure; the endpoints never 500. The atomic write (temp + `os.replace` with the Windows `PermissionError` retry) and `_WRITE_LOCK` mirror `design_store` exactly — the same proven pattern.
- **The saved default is authoritative app-wide, with a graceful fallback.** `effective_defaults` overlays the saved choice onto the config default, and a saved key that no longer exists in config (a printer removed between sessions) falls back rather than dangling. `/api/options` now reads through it, so the ExportPanel + design flow respect the user's chosen default — and the change is backward-compatible (the two existing `web_options(config)` test callers still work; the printers/materials shape is unchanged).
- **Honest UX.** The Saving/Saved/error indicator is driven by the server's `saved` flag, not optimistic — it can't claim "Saved" when the store didn't persist. Selects are label-associated (`htmlFor`/`id`); the units row reuses the existing accessible `kc-unit-toggle` (`role="group"` + `aria-pressed`); the 640px rule stacks the rows and gives the select a 44px touch target.
- **Tests are non-vacuous.** The roundtrip test proves persistence AND that `/api/options` reflects the saved default; the unknown-key test proves the 400; the `saved:false` frontend test proves the honest error; the null-clear test proves the fallback. 122 vitest + 81 backend pass.

## Watch items
- **Units split-brain (by design, worth a note for later slices):** printer/material persist server-side; units stay client-side (`useUnits` / localStorage). That's the right call (units is a pure display pref that must re-render the app in lockstep), but a future "export/import settings" or multi-device story would need to reconcile the two stores. Not a finding now.
- **A `select value=""` edge** if a config ever ships with no default printer/material (`effective_defaults` would return null → the select shows the first option with an empty value). Unreachable today (the shipped config always has defaults); revisit only if a default is ever made optional.

## Escalation recommendation
No escalation needed. Two Minors, fixed inline; the store + endpoint design is safe and backward-compatible. The slice-end audit-team + wiring-audit (after MS-2–5) remain the gate before the Slice 6 report.
