# Slice 7 audit-team — Remediation to 0/0/0/0/0

**Date:** 2026-06-04 · Every finding from the 5-role audit, with its resolution. Re-verified: ruff clean, 740 backend tests pass, 162 frontend tests pass, build clean.

## Engineering (01)

| ID | Sev | Resolution |
|---|---|---|
| ENG-001 | Minor | **Fixed.** Moved `import base64`, `import urllib.request`, `from urllib.parse import urlsplit, urlunsplit` to module top in `llm_provider.py`. The `webapp.py` late `from kimcad.llm_provider import LLMProvider` is intentionally **kept** — the never-route-to-cloud trust test patches `lp.LLMProvider` at call time. |
| ENG-002 | Minor | **Fixed.** `describe_photo` now prints a one-line stderr breadcrumb on an empty vision response (an outdated Ollama that ignores `think:false` presents like an unreadable photo). Matches the existing `FallbackProvider` stderr style; the user still gets the graceful 422. |
| ENG-003 | Minor | **Fixed.** `cfg = get_config()` moved **inside** the `_handle_photo_seed` try, closing the last theoretical 500 path (now a config error there is also the best-effort 422). |
| ENG-004 | Nit | **No change (resolved as designed).** The curly apostrophe / em-dash is **consistent house style** across the entire UI copy and prompts (the reviewer confirmed "No defect"); making one error string ASCII would *introduce* inconsistency. |

## UI/UX (02)

| ID | Sev | Resolution |
|---|---|---|
| UX-001 | Minor | **Fixed.** The error copy no longer over-promises a route the card doesn't afford: now "Couldn't read that photo — try a clearer shot, or **cancel** and describe the part in words." (truthful — Cancel → the text box). Changed in lockstep in `webapp.py` (`cant_read`) and `PhotoOnramp.tsx` (the empty-seed + catch messages). |
| UX-002 | Minor | **Fixed.** The confirm/error card's `aria-label` is now phase-specific: "Reading your photo" / "A rough starting point from your photo" / "Photo couldn't be read" — orients AT users instead of echoing the button they pressed. |
| UX-003 | Nit | **Fixed.** Unified the re-pick label to "Use a different photo" in both the confirm and error states. |

## Docs (03)

| ID | Sev | Resolution |
|---|---|---|
| DOC-001 | Major | **Fixed.** `CHANGELOG.md` `[Unreleased]` preamble corrected, and `### Added` entries added for Slices 2–4, 6, and 7 (Slice 5 noted as design-only). |
| DOC-002 | Major | **Fixed.** `README.md` status banner now names the real branch state (persistence, refine-as-conversation + version history, numeric entry, mm/inch, in-app Settings, and the local-vision photo on-ramp); the "Saving your work" header de-pinned from Slice 1. |
| DOC-003 | Minor | **Fixed.** `HANDOFF.md` date bumped to 2026-06-04; resume block updated (Slice 6 gated; Slice 7 built + gated; resume now = Slice 8). |
| DOC-004 | Minor | **Fixed.** `docs/stage-8.5-usability-plan.md` Slice 6 + Slice 7 headers now carry status markers matching the others (Slice 6 IMPLEMENTED, with the CadQuery/PrintProof3D one-click-enable honestly noted as deferred to Stage 8; Slice 7 IMPLEMENTED + gated). |
| DOC-005 | Minor | **Fixed.** `ARCHITECTURE.md` — `llm_provider.py` is now "Three jobs" (adds `describe_photo`); a Stage-8.5 web-layer paragraph documents `/api/photo-seed`, `/api/settings`/`/api/model-status`, `/api/designs*`, and the local-only photo guarantee. |
| DOC-006 | Nit | **Fixed.** `system_photo_seed.md` "millimetres" → "millimeters" (US, matches the rest of the docs + the US-maker audience). |

## Tests (04)

| ID | Sev | Resolution |
|---|---|---|
| TEST-701 | Major | **Fixed.** Added `test_photo_seed_empty_upload_is_400` — a 0-length body → 400 "Empty upload.", and asserts vision was never invoked. |
| TEST-702 | Major | **Fixed.** Added two `uploadPhoto` api.test.ts cases: a `{ok:false, 422}` surfaces the backend `error` message; a non-JSON body throws a readable error. Closes the mock-both-sides seam. |
| TEST-703 | Minor | **Fixed.** Added a drag-and-drop test: `fireEvent.drop` on the affordance runs the read flow and confirms `preventDefault` fired. |
| TEST-704 | Minor | **Fixed.** Added a re-pick test: "Use a different photo" → a 2nd file → `createObjectURL` called twice and the 1st blob URL revoked (object-URL leak guard on re-pick). |
| TEST-705 | Nit | **No change (resolved as designed).** The FakeProvider-vs-real-router split is correct (the 200 contract on a fake provider, the trust property on the real router); the reviewer flagged it only as a note. |

## QA (05)

No findings (0/0/0/0/0 in the runtime lane). A runtime `wiring-audit` re-drive follows the remediation.
