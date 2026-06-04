# Audit Lite — Stage 8.5 Slice 6 MS-5: tools health + about/reset
**Date:** 2026-06-04
**Scope:** The final Settings micro-slice — `GET /api/health` (`webapp.py`), `getHealth` (`api.ts`), and the SettingsPanel Tools (OpenSCAD/OrcaSlicer presence) + About (version + open-source note) + a two-step "Reset to defaults", plus tests.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after one Minor fix (applied). The health endpoint never 500s, the tool status is real (driven by the actual binary check), and the reset clears everything (server settings + client units + drafts) behind a two-step confirm. One Minor: a failed health fetch left the Tools section showing "Checking…" forever — now it shows an honest "Couldn't check".

## Severity rollup
**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: a failed health fetch shows "Checking…" forever
**Dimension:** UX
**Evidence:** `SettingsPanel.tsx` — the health load is `getHealth().then(setHealth).catch(() => {})`, and the Tools rows render `health ? (installed/not-found) : 'Checking…'`. If `getHealth` rejects (server hiccup), `health` stays `null`, so both rows show "Checking…" indefinitely — a perpetual-loading state that reads as a hang, not a failure. This is inconsistent with the AI-model section, which has an explicit "Couldn't check" error state.
**Why it matters:** Honesty/consistency: a failed check should say so, not look like it's still loading. Same standard the model-status section already meets.
**Fix path:** Track a health error (a `healthError` flag or a `'checking'|'ready'|'error'` state) and render "Couldn't check" on failure.
**Status:** ✅ Fixed — a `healthError` state added; the Tools rows show "Couldn't check" on a failed fetch. Tests added for the failure path and the reset-cancel path.

## What's working
- **The health endpoint is bullet-proof.** `_handle_health` wraps each `binary_path(name).exists()` in its own try/except, so a missing binary OR a missing/typo'd config key is `present:false`, never a 500. A test monkeypatches `binary_path` to raise and asserts `present:false` + 200. The version comes from the real `kimcad.__version__`.
- **The tool status is honest, not faked.** "Installed"/"Not found" reflects the actual on-disk binary check; a test asserts OpenSCAD reads Installed (its binary is committed under `tools/`) and the real version string renders. The status is a text label, not color-only — colorblind-safe.
- **The reset is complete and confirmed.** `resetAll()` clears every server-side override (printer/material → config default via null, cloud off + model/key blanked, experimental off) AND the client-only units (back to mm) AND the in-component drafts (keyDraft/modelDraft/replacingKey) — so after a reset the cloud section collapses, the key field is empty (has_cloud_key → false), the model field is blank, and units are mm, with nothing stale. It's a deliberate two-step confirm (Reset… → Reset everything / Cancel), not a one-click destructive action, and the danger button is visually distinct. A test asserts the exact clearing payload + units→mm.
- **Best-effort client load.** Health loads independently of the settings, so a slow/failed health check never blocks the printer/material/units/AI/cloud sections.
- **Honest scope.** MS-5 ships the *real* tools (OpenSCAD/OrcaSlicer) only — it does not fake a "one-click enable" for CadQuery (Stage 8, unbuilt) or PrintProof3D (optional/absent), which would be a dishonest control. That deferral is the right call.

## Watch items
- **CadQuery / PrintProof3D engine management (deferred, by design).** The plan's "optional-engine one-click-enable" needs those engines to exist first (Stage 8 / optional). When they land, the Tools section is the place to surface them with real install/download status. Noted for the stage that builds them, not a gap now.
- **The reset routes through `change()`** so it shows the honest Saving/Saved/"didn't stick" indicator — good. If a future reset needs to also clear *client* state that can't fail (units), note that units reset happens optimistically before the server round-trip; acceptable since localStorage writes don't fail in practice.

## Escalation recommendation
No escalation needed. One Minor (health-error state) fixed. This completes Slice 6's micro-slices; the slice-end **audit-team + wiring-audit** are the gate before the Slice 6 report — and the wiring-audit should drive the Settings screen end to end (persistence, model status, the masked-key round-trip, the experimental offer, tools health, and the reset).
