# Audit Lite — Stage 8.5 Slice 6 MS-3: cloud opt-in + masked token
**Date:** 2026-06-04
**Scope:** The cloud (OpenRouter) opt-in — the saved, masked OpenRouter token + live cloud routing: the settings-aware provider, the masking helper, the `/api/settings` cloud fields, the cloud-aware `/api/model-status`, the provider token override, the store allowlist, and the SettingsPanel Cloud section. Safety weighted highest.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/0/0** — ships after one Minor fix (applied). The load-bearing safety property holds: the user's OpenRouter token is **never returned by the API in full and never logged** — verified across every code path. KimCad does not hardwire a cloud vendor (the user supplies the model, per spec §7.3), and cloud routing degrades to local on any gap. One Minor (the entry field should opt out of browser autofill), fixed.

## Severity rollup
**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.
**After remediation:** 0/0/0/0/0.

## Findings

### FOUND-001 Minor: the token input doesn't opt out of browser autofill
**Dimension:** UX / Safety-adjacent
**Evidence:** `SettingsPanel.tsx` — the entry field (a dotted/obscured input) has no `autoComplete`/`spellCheck`. That kind of field prompts the browser to offer to *store* the value and may *autofill* a saved one — inappropriate here (it isn't a site login, and an unrelated autofill could overwrite the field).
**Why it matters:** Not a leak (the value never leaves the field except to the save POST), but a maker pasting their OpenRouter token shouldn't get a "store this?" prompt or a surprise autofill. It's the hygiene expected of a sensitive field.
**Fix path:** Add `autoComplete="off"` and `spellCheck={false}`; add a test asserting the obscured type + autofill off.
**Status:** ✅ Fixed — `autoComplete="off"` + `spellCheck={false}` added; a SettingsPanel test asserts it.

## What's working
- **The token is never echoed — verified across all paths (the load-bearing property).** The settings payload returns only the masked form (a fixed dot run + the last 5) plus a boolean "has a token"; the raw value is never added. GET and POST both go through that one builder. The model-status cloud branch returns only the model name + flags — the stored value is read solely to test presence, never returned. A backend test asserts the test value is absent from the full JSON of both the POST and GET responses while present on disk. **No leak path found.**
- **The token is never logged.** The request logger is overridden to a no-op (webapp.py:600 — "keep the console quiet"), so the request line and body are never written to the console/logs. The only console writes are the startup banner and "Stopping." Neither carries the value.
- **No hardwired vendor (spec §7.3).** KimCad does not pick or pre-select a cloud model — the user supplies it in a free-text field, and the settings-aware provider replaces the `custom_openrouter` backend's model with the user's value. The field is empty by default with a neutral placeholder, so no model — Chinese or otherwise — is recommended. This corrects the earlier "KimCad picks" draft to match the spec.
- **Local always works / degrade-safe.** The settings-aware provider routes to LOCAL whenever cloud is off, the token or model is missing, or the cloud build throws (wrapped → local); the per-call settings read is wrapped (→ empty on failure). A cloud misconfiguration can never break a local design. The cloud provider is cached per (token, model) so it isn't rebuilt each call.
- **The provider override is backward-compatible.** The client builder uses an explicit token when given, else falls back to the env var exactly as before — the 41 existing provider tests pass unchanged.
- **Honest, safe UX.** Off by default; the "this sends your prompt off your machine" privacy callout is at the point of use; the entry field is dotted/obscured; a saved token shows masked + a Replace button (the full value is never re-rendered); the Saving/Saved/"didn't stick" indicator is driven by the server's honest flag. The user types it themselves — KimCad never enters it. a11y: `role="switch"` + `aria-checked` on the toggle, labelled inputs, real `<button>`s, OpenRouter links open in a new tab.
- **Tests are non-vacuous and safety-focused.** The masking contract test pins the never-echoed property; the routing test pins local/cloud/local-when-unconfigured selection; the clear test pins blank-clears; the frontend tests pin the toggle, the save, the masked+Replace display, and the model save.

## Watch items
- **File permissions (POSIX hardening).** The token is stored plaintext in `~/.kimcad/settings.json` with default umask perms (commonly 0644 on a shared Unix box). This matches the approved consumer-app posture (Scott settled: a normal local Settings field, never in the repo/logs), and the target is single-user Windows-first — but on POSIX a `chmod 0600` after write would be cheap defense-in-depth. A follow-up, not a blocker.
- **Generic 500 echoes the exception text (pre-existing).** The design handler's catch-all returns the exception text. A cloud auth failure's exception comes from the OpenAI client, which OpenRouter/OpenAI redact the token from — so no leak in practice — but a friendlier "your cloud model couldn't be reached" message (with an explicit guard that the error never carries the value) is a good stage-close hardening. Pre-existing, out of MS-3 scope.

## Escalation recommendation
No escalation needed. Zero leaks found, one Minor (autofill hygiene) fixed. The slice-end audit-team + wiring-audit (after MS-4–5) remain the gate — and because this slice handles a sensitive value, the audit-team's QA role should re-confirm the never-echoed property against the running server.
