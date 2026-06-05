# Stage 8.5 Stage-Gate — Punch List (fix ALL before merge → 0/0/0/0/0)

Per the project mandate every finding is fixed this gate, regardless of severity, then re-audited.
Owner hint in brackets = role that surfaced it. Ordered for remediation (quick/high-certainty first,
then the engineering safety Majors, then the UX cluster, then test/QA).

## Docs (quick, high-certainty)
- [ ] **DOC-001 (Major)[Docs]** HANDOFF.md "Backend API contract" still says "unchanged seam" + only Stage-4 routes → point it at ARCHITECTURE.md and list the Stage 5–8.5 endpoints. (`HANDOFF.md:306-317`)
- [ ] **DOC-002 (Major)[Docs]** `docs/design/README.md` still tags Qwen "RECOMMENDED" (:147), defaults photo to cloud vision (:157), encodes `model: qwen|gemma|cloud` (:204) → add a ⚠ SUPERSEDED banner correcting to gemma4:e4b-only / local-vision (matching the v3.0 spec's banner style).
- [ ] **DOC-003 (Minor)[Docs]** spec Addendum B + ROADMAP describe a 9-slice Stage 8.5 (now 11, renumbered) → reconcile the count.
- [ ] **DOC-005 (Minor)[Docs]** CHANGELOG preamble "Stages 1–6 tagged" then documents stage-7 tagged → fix the preamble.
- [ ] **DOC-006 (Minor)[Docs]** README/ROADMAP cite a 780M target; spec references 890M → add the HANDOFF reconciliation note to README/ROADMAP.
- [ ] **DOC-004/007/008 (Nit)[Docs]** minor wording/consistency nits noted in 03-documentation-deepdive.md.

## Engineering — safety/correctness
- [ ] **ENG-001 (Major)[Eng]** slice/render same-rid race can register a stale-geometry G-code after invalidation → shared per-rid lock OR geometry-version stamp checked in `_respond_slice`. (`webapp.py:1564-1565` vs `1671-1687`)
- [ ] **ENG-002 (Major)[Eng]** reopen/import trusts stored gate_status (no re-gate) → re-run the gate (or lazy re-gate before first slice) on reopen + import. (`webapp.py:1464`, `design_store.py:269-297`)
- [ ] **ENG-003 (Minor)[Eng]** `_json` lacks `allow_nan=False` → central serializer, clean 500 on non-finite. (`webapp.py:731`)
- [ ] **ENG-004 (Minor)[Eng]** `FallbackProvider` missing `describe_photo`; Protocol doesn't declare it → add both. (`llm_provider.py:71-90,299-374`)
- [ ] **ENG-005 (Minor)[Eng]** `_cloud_cache` unbounded (key material) → cap/LRU or key by model. (`webapp.py:359`)
- [ ] **ENG-006 (Nit)[Eng]** CLI `model_advisor` catalog ranks Qwen above gemma4 → deprioritize/drop Qwen so the CLI matches the "gemma4 is THE model" rule. (`model_advisor.py:99-118`)
- [ ] **ENG-007 (Minor)[Eng]** missing geometry deps → cascading misleading failures → conftest import smoke-check + reconcile manifold3d "optional" comment vs hard pin. (`conftest.py`, `pyproject.toml`)

## UI/UX
- [ ] **UX-001 (Major)[UI]** restore right-column hierarchy: accent-tinted readiness card + accent-bordered report card (per-card modifiers, not global). (`RightPanel.tsx`, `styles.css`)
- [ ] **UX-002 (Major)[UI]** restore Printability icon-tile checks (✓/⚠ + label + detail); decide single material source-of-truth. NEEDS the finding payload to carry label/detail — check `/api/design` first. (`RightPanel.tsx:528`)
- [ ] **UX-003 (Major)[UI]** add in-viewport/composer refine chips ("Make it wider"…) calling `onRefine`; drop or build the orientation "change" action (no dead label). (`ChatPanel.tsx`, `Viewport.tsx:167`)
- [ ] **UX-004 (Major)[UI]** mobile workspace: segmented Chat/3D/Details switcher OR sticky Slice/Download CTA so the verdict+action aren't buried. (`styles.css:460`, `Workspace.tsx`)
- [ ] **UX-005 (Major)[UI]** add a visible "?" Help button (Topbar) opening the shortcuts modal — lift `showShortcuts` state. (`Topbar.tsx`, `App.tsx`)
- [ ] **UX-006 (Major)[UI]** add the always-on printer-status chip to the Topbar (status readout: name + build volume; NOT a model menu). (`Topbar.tsx`)
- [ ] **UX-007 (Minor)[UI]** landing badge → "Ready to print in ~15 minutes · no CAD skills"; keep privacy line secondary. (`Landing.tsx:43`)
- [ ] **UX-008 (Minor)[UI]** suppress the duplicate chat "Designing…" row during a first design (viewport overlay owns it). (`ChatPanel.tsx:189`)
- [ ] **UX-009 (Minor)[UI]** match the reference donut score ring (full circle ~68px) or document the half-gauge as intentional. (`RightPanel.tsx:353`)
- [ ] **UX-010 (Minor)[UI]** surface refine chips for slider-less parts + a persistent micro-hint above the refine input. (`RightPanel.tsx:313`, `ChatPanel.tsx`)
- [ ] **UX-011 (Minor)[UI]** show a quiet v1 cue in VersionRail ("refine to create versions"). (`VersionRail.tsx:16`)
- [ ] **UX-012 (Minor)[UI]** add the one-line format-purpose note to the print-file row (keep honest STEP-later framing). (`ExportPanel.tsx`)
- [ ] **UX-013 (Minor)[UI]** dedup "Saved · My Designs" save link vs the "My Designs" nav button. (`Topbar.tsx`)
- [ ] **UX-014 (Nit)[UI]** unify apostrophe style in source copy.
- [ ] **UX-015 (Nit)[UI]** add a muted reason under a disabled Slice button when the printer has no profile. (`ExportPanel.tsx:154`)
- [ ] **UX-016 (Nit)[UI]** confirm photo thumb `alt=""` intentional (no change; document).
- [ ] **UX-017 (Nit)[UI]** lighten the recommendations "→" weight. (`styles.css:1479`)
- [ ] **UX-018 (Nit)[UI]** consider a circled-i / "?" for the InfoTip glyph (or keep italic-i; document). (`styles.css:2932`)

## Tests
- [ ] **TEST-001 (Major)[Test]** get the frontend (vitest) + SPA build-reproducibility gate running in hosted CI (not only the local pre-push hook). (`.github/workflows/ci.yml`)
- [ ] **TEST-002 (Minor)[Test]** direct test for `useHashRoute` hashchange + replaceState branch. (`useHashRoute.ts:27-41`)
- [ ] **TEST-003 (Minor)[Test]** add a "cloud key never appears in logs/exceptions" test (second leak vector). 
- [ ] **TEST-004 (Minor)[Test]** upgrade a few render-presence assertions to behavior assertions (Topbar active-route; glossary tip definitions).
- [ ] **TEST-005 (Nit)[Test]** note/accept the wholesale `api` mock seam (or add one contract test).

## QA
- [ ] **QA-001 (Minor)[QA]** `/api/render` silently clamps/coerces → return an `adjusted`/`clamped` hint so a raw API client knows values were changed. (`webapp.py` render handler)
- [ ] **QA-002 (Minor)[QA]** add a `--demo-scenario` (or similar) so the gate-failed + needs-experimental error states are reachable in the running demo. (`webapp.py` DemoProvider)
- [ ] **QA-003 (Nit)[QA]** unify the two bad-id error-message wordings.
