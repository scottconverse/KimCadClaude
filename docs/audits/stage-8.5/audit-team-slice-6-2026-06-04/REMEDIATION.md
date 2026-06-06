# Slice 6 — audit-team + wiring remediation → 0/0/0/0/0
**Date:** 2026-06-04
**Branch:** stage-8.5-usability

The full 5-role audit-team over the Slice 6 diff (16f9290..HEAD) found **1 Critical · 3 Major ·
~9 Minor · ~7 Nit**. No safety property was broken — the engineering + QA roles verified the
OpenRouter key is never echoed/logged (a live masked GET captured, no raw key in any response or the
DOM) and the experimental gate never bypasses the printability check and the consumer never
auto-runs. Every finding is fixed or resolved below.

## Critical
- **TEST-001 — the suite was red on the author's machine (model-status tests leaked the real
  `~/.kimcad`).** Once MS-3 made `/api/model-status` read the saved cloud setting, the four MS-2
  tests (which never monkeypatched `settings_path`) read the developer's real settings file — green
  on CI's empty home, red locally (and three were vacuous). **Fixed:** an **autouse `conftest.py`
  fixture** (`_isolate_kimcad_home`) isolates `settings_path` / `designs_path` / `history_path` to a
  fresh tmp dir for *every* test. The full backend suite is now deterministic + green; the three
  model-status tests reach their assertions again.

## Major
- **UX-101 / UX-102 / UX-103 — touch targets under 44px at a phone width.** The new `.kc-switch`
  toggles (24px), the small Save/Replace/Reset buttons (35px), and the legacy topbar nav `.kc-btn`
  (32px) were never folded into the standardized `(pointer: coarse), (max-width: 640px)` 44px rule.
  **Fixed:** one coordinated rule brings all three to 44px on touch + narrow viewports; the switch
  keeps its slim visual via `background-clip: content-box` + transparent padding (only the tap area
  grows), and the knob is centered so it stays put. **Re-measured live at 375px: switch 44px, small
  buttons 44px, topbar nav 44px.**
- **TEST-002 — `probe_ollama`'s reachable-vs-empty distinction (its whole reason to exist) had no
  direct test.** **Fixed:** a unit test mocks `urlopen` to prove reachable+models, reachable+empty
  (up but no model), and down → `(False, [])`.

## Minor
- **TEST-003** — cloud→local degrade on a cloud *build* error was untested. **Fixed:** a test forces
  the cloud backend lookup to raise and asserts `_active()` falls back to local.
- **TEST-004** — the never-echoed assertion was only on `/api/settings`. **Fixed:** a test asserts
  the key is absent from `/api/model-status`'s cloud response too.
- **TEST-005** — `postDesign`'s `experimental` body field + `postSettings({reset})` had no frontend
  test (the SettingsPanel suite mocks `../api`). **Fixed:** `api.test.ts` asserts the bodies.
- **ENG-S6-001** — `_mask_key` revealed a too-short key's last 5. **Fixed:** reveals nothing for a
  value ≤ 8 chars (a real OpenRouter key is 40+).
- **UX-104** — the experimental offer didn't name the decline path. **Fixed:** "Or describe it
  differently below."
- **UX-105** — the cloud chip read "Optional"/"On". **Fixed:** a clean "Off"/"On" binary.
- **DOC-002** — HANDOFF.md's "RESUME HERE = Slice 1" was stale. **Fixed:** points to Slice 7 with the
  current Slice 1–6 status + the renumber note.

## Nit
- **QA-001** — Reset left `cloud_enabled:false`/`experimental_enabled:false` as explicit keys.
  **Fixed:** a `{reset:true}` POST now `clear()`s the store to pristine (`{}` on disk) — verified by a
  test asserting the file is empty after reset.
- **DOC-003** — the cloud model field didn't disclose the bad-slug→local fallback. **Fixed:** an
  inline note ("a design never fails just because a cloud slug is wrong").

## Resolved as by-design / cadence-deferred (no code change)
- **ENG-S6-002 (Nit)** — `_cloud_cache` is unbounded. Correct for the single-user/loopback target
  (a handful of (key, model) pairs); only matters if a multi-client mode lands. Acknowledged.
- **ENG-S6-003 (Nit)** — the cloud model-status reports `running:true` without probing OpenRouter.
  Deliberate (probing would spend the user's key); the local fallback means a bad cloud key never
  breaks a design. Acknowledged.
- **DOC-001 (Minor) + DOC-004 (Nit)** — the README flow diagram + the in-app Apache-2.0 note get the
  comprehensive pass at **Stage 8.5 close** (the established README/CHANGELOG batching cadence —
  Slices 1–5 didn't touch the README per-slice; the Writer's own recommendation). Not an open defect.

## Wiring (runtime gate)
The audit-team's QA + UI/UX roles drove the running Settings screen live (demo on :8810): the
OpenRouter key never appears raw in any response or the DOM (only masked, last 5); printer/material/
cloud/experimental persist across a full reload; Reset clears everything (server + the on-disk key +
units→mm); unknown printer/material → 400; health/model-status never 500; **console clean, zero
failed requests**. The touch-target fixes were re-measured live at 375px (all 44px). The experimental
offer (`needs_experimental`) can't be driven on the demo (its "box" matches a template) — proven by
the pipeline/HTTP tests instead.

**Verification:** 147 vitest (13 files) + the full backend suite green; tsc/build/ruff clean. The
suite is now machine-independent (the TEST-001 fixture).
