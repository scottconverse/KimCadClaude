# Documentation Deep-Dive — KimCad Snapmaker U1 + Multi-Toolhead Feature

**Audit date:** 2026-06-16
**Role:** Technical Writer
**Scope audited:** CHANGELOG.md, docs/api.md, docs/supported-printers.md, README.md, ARCHITECTURE.md, config/default.yaml — scoped to commits cc80fed + 3553665 (Snapmaker U1 + generic multi-toolhead support)
**Writer mode:** audit-only (flag gaps, no rewrites)
**Auditor posture:** Balanced

---

## TL;DR

The feature shipped as working code — `SnapmakerConnector`, `toolhead_count`, `toolhead_temps`, pause/resume/cancel, multi-slot slicing — but the documentation layer was not updated to match. CHANGELOG.md has zero mention of the feature. `docs/api.md` documents none of the new fields on `/api/options`, `/api/connector-status`, or `POST /api/slice`. `docs/supported-printers.md` does not list the Snapmaker U1 at all. A user with a Snapmaker U1 who reads any of the public-facing docs will find nothing. The `config/default.yaml` connector template is comment-only and explains almost nothing about the `snapmaker` type, its relation to Moonraker, or what the user must fill in. ARCHITECTURE.md is the one bright spot — it accurately maps connector modules — but it too has no entry for `SnapmakerConnector`.

---

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 3 |
| Major | 3 |
| Minor | 1 |
| Nit | 1 |

---

## What's working

- **`config/default.yaml` snapmaker_u1 printer entry** — build volume is VERIFIED-tagged against the shipped Orca profile, the four filament profiles are named, and `toolhead_count: 4` is present with an explanatory inline comment. Good engineering hygiene here.
- **ARCHITECTURE.md module table** is thorough and accurate for all pre-existing connectors. The pattern of one-line summaries per module is clear and maintainable.

---

## What couldn't be assessed

- Whether the Snapmaker U1 appears in any external marketing page or landing page (none exists for KimCad outside the README and GitHub).
- Live UI screenshots confirming the N-material dropdowns render correctly (UI review is a separate role).

---

## Doc asset inventory

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| CHANGELOG.md | Yes | Weak for this feature | DOC-001 |
| docs/api.md | Yes | Missing new fields entirely | DOC-002, DOC-003 |
| docs/supported-printers.md | Yes | Missing Snapmaker U1 | DOC-004 |
| README.md | Yes | No mention of Snapmaker or multi-toolhead | DOC-005 |
| ARCHITECTURE.md | Yes | No entry for SnapmakerConnector | DOC-006 |
| config/default.yaml (connector template) | Yes (comment-only) | Sparse; underdocumented | DOC-007 |
| docs/USER-MANUAL.md | Yes | No multi-toolhead workflow section | DOC-008 (Minor) |

---

## Persona walk-through

### First-time user

A user with a Snapmaker U1 follows the README to the supported-printers page. They search for "Snapmaker" — nothing. They check CHANGELOG.md for recent additions — nothing. They look at the API docs to see if they need to supply multiple materials — nothing. This user cannot discover or configure the feature from the docs alone. They must read `config/default.yaml` and infer from the commented-out block, which names `type: snapmaker` without explaining what that means or how it differs from `type: moonraker`.

### Returning user

A developer familiar with KimCad who wants to wire up a Snapmaker U1 will find the connector template comment in `default.yaml`, but it does not explain: (a) that the Snapmaker U1 runs Klipper/Moonraker underneath, (b) why `type: snapmaker` exists rather than `type: moonraker`, (c) that pause/resume/cancel are now available, or (d) what `filament_slot_0..3` does in the slice POST. They would need to read the source to understand this.

### New team member

ARCHITECTURE.md lists every other connector module with a one-line summary. `snapmaker_connector.py` is absent. A new contributor adding a fifth toolhead or debugging the U1 path has no orientation other than reading the source.

---

## Findings

### [DOC-001] — Critical — Completeness — CHANGELOG.md has no entry for Snapmaker U1 or multi-toolhead

**Evidence**

`CHANGELOG.md` — the entire file. A search for "snapmaker", "toolhead", "multi-material", "pause", "resume", "cancel" returns zero matches. The two commits (cc80fed, 3553665) that shipped the entire feature are entirely absent from the changelog.

**Why this matters**

A beta tester upgrading from `0.9.0b3` reads the changelog to understand what changed. They will not find the Snapmaker U1, the new multi-material slicing path, the pause/resume/cancel controls, or the new `toolhead_count`/`toolhead_temps` fields. Any returning user tracking the feature list is silently uninformed. This is a significant regression in changelog integrity — the KimCad changelog has historically been thorough and per-feature.

**Blast radius**

- Adjacent docs: Release notes (if any), HANDOFF.md — both would inherit the same omission.
- User-facing: every user upgrading from `0.9.0b3` is affected.
- Related findings: DOC-004 (supported-printers), DOC-005 (README).

**Fix path**

Add an entry under `[Unreleased]` (or a `[0.9.0b5]` block if this ships as a patch):

```
### Added
- **Snapmaker U1 support + generic multi-toolhead.** A new `snapmaker` connector type
  (`SnapmakerConnector`) extends the Moonraker connector with 4-extruder capability and
  temperature reporting (`toolhead_temps` T0–T3). The Snapmaker U1 is now in the printer
  catalog (`config/default.yaml`). `POST /api/slice` accepts `filament_slot_0`..`N-1`
  fields for multi-material slicing. `GET /api/options` now returns `toolhead_count` per
  printer; `GET /api/connector-status` now returns `nozzle_temp_c` and `toolhead_temps`.
- **Pause / resume / cancel** on Moonraker and Snapmaker connectors; the `PrinterConnector`
  Protocol now declares these three methods.
```

---

### [DOC-002] — Critical — API — `docs/api.md` missing all new fields from `/api/options`, `/api/connector-status`, and `POST /api/slice`

**Evidence**

`docs/api.md`:
- `GET /api/options` (line ~185): documented as returning printer + material catalog. No mention of `toolhead_count` per printer, which `webapp.py` line 555 now emits.
- `GET /api/connector-status` (line ~133): documented as returning `ready/busy/offline/needs_setup`. No mention of `nozzle_temp_c` or `toolhead_temps`, which `webapp.py` lines 1811–1814 now conditionally emit.
- `POST /api/slice` (line ~99): documented as accepting `{"printer": "...", "material": "..."}`. No mention of `filament_slot_0`..`filament_slot_N-1` for multi-toolhead printers, which `webapp.py` lines 2464–2473 parse.

**Why this matters**

Any developer integrating against the KimCad API (including the MCP server user, a CLI script writer, or a future frontend contributor) will not know these fields exist. They will either miss the multi-material path entirely, or they will discover it by reading the source. The API doc is the authoritative contract; without these fields it is wrong, not merely incomplete.

**Blast radius**

- Adjacent docs: `frontend/src/api.ts` is correctly updated (the TypeScript types were part of the feature commit), but the human-readable API reference is not. Anyone reading `docs/api.md` gets a stale picture while the TS types tell a different story.
- User-facing: affects any caller of `/api/connector-status` who checks docs for the response shape; affects any caller of `/api/slice` trying to slice for a multi-toolhead printer.
- Related findings: DOC-001 (changelog), DOC-003 (PrinterCapabilities in api.md).

**Fix path**

Update the three endpoint descriptions in `docs/api.md`:

1. `/api/options` — add `toolhead_count` to the per-printer response shape with a note: "Present for multi-toolhead printers; 1 for single-toolhead."
2. `/api/connector-status` — add optional `nozzle_temp_c` (float, degrees C) and `toolhead_temps` (array of floats, T0..TN-1) to the response, noting they are only present when the connector reports them.
3. `POST /api/slice` — add `filament_slot_0`..`filament_slot_{N-1}` to the request body, explaining: "For printers with `toolhead_count > 1`, supply one material key per slot instead of `material`. Unused slots default to the first slot's material."

---

### [DOC-003] — Critical — API — `docs/api.md` has no mention of `snapmaker` connector type in the connections documentation

**Evidence**

`docs/api.md` — `GET/POST /api/connections` section (line ~133): lists the connector type vocabulary implicitly via the `config/default.yaml` template names (`mock`, `octoprint`, `moonraker`, `prusalink`, `bambu`, `duet`, `marlin`). The `snapmaker` type does not appear anywhere in the API doc. The `docs/supported-printers.md` direct-send table (line ~79) also lists every connector type except `snapmaker`.

**Why this matters**

A user configuring the Snapmaker U1 via `GET/POST /api/connections` reads the docs to understand what `type` values are valid. `snapmaker` is absent. They may fall back to `moonraker` (plausible, since the U1 runs Klipper) and lose the multi-toolhead capability detection silently.

**Blast radius**

- Adjacent docs: `docs/supported-printers.md` direct-send table repeats the same omission (DOC-004).
- User-facing: Snapmaker U1 users who want direct-send integration are blocked from configuring it correctly via the docs.

**Fix path**

Add `snapmaker` to the direct-send table in `docs/supported-printers.md` (a new row: Snapmaker U1 with `snapmaker` type, noting it extends Moonraker with 4-extruder capability detection). Add a one-liner to `docs/api.md` in the connections section: "`type: snapmaker` — for Snapmaker U1 (Klipper/Moonraker-based, 4-toolhead); extends `moonraker` with per-extruder status."

---

### [DOC-004] — Critical — Completeness — `docs/supported-printers.md` does not list the Snapmaker U1

**Evidence**

`docs/supported-printers.md` — entire file. The Snapmaker U1 is absent from the curated-printers table, the reference printers table, and the direct-send table. The `config/default.yaml` `snapmaker_u1` entry confirms the printer is catalog-ready (build volume VERIFIED, four filament profiles, `toolhead_count: 4`).

**Why this matters**

`docs/supported-printers.md` is the authoritative list of KimCad-supported hardware. A Snapmaker U1 user comparing KimCad against other tools will check this page first and conclude the printer is unsupported. The README links directly to this page. This is a user-visible gap that will cause missed adoption.

**Blast radius**

- Adjacent docs: README.md (line 41) says "a curated catalog of ~29 printers" — with the U1 added, that count is now stale.
- Related findings: DOC-001 (changelog), DOC-005 (README count).

**Fix path**

Add a row to the curated-printers table: `Snapmaker U1 | 270.5 × 271.0 × 270.1 | 4-toolhead (PLA/PETG/TPU/ABS)`. Add a row to the direct-send table: `snapmaker | Snapmaker U1 (Klipper/Moonraker-based) | API-validated (conformance mock); inherits full Moonraker send path; 4-extruder status`. Update the "~29 printers" count in the README and supported-printers preamble.

---

### [DOC-005] — Major — Completeness — README.md does not mention Snapmaker U1 or multi-toolhead support

**Evidence**

`README.md` lines 41–43: "A curated catalog of ~29 printers across the top makers (Bambu, Creality, Prusa, Anycubic, Elegoo, Qidi, Sovol)". Snapmaker is absent from the brand list. The README's "Slice & print" bullet (line 25): "Bambu LAN, OctoPrint, Moonraker, PrusaLink" — `snapmaker` is not listed. No mention of multi-material or multi-toolhead capability anywhere in the README.

**Why this matters**

The README is the product's front door. A Snapmaker user scanning the homepage for their brand will not find it. The brand list in the beta notes is the highest-visibility location; the omission is equivalent to saying the printer is not supported.

**Blast radius**

- Adjacent: `docs/supported-printers.md` repeats the brand list — same omission.
- Related findings: DOC-004.

**Fix path**

Add "Snapmaker" to the brand list in README.md line 41. Add `snapmaker` to the "Slice & print" connector list (line 25). Consider adding a one-liner about multi-toolhead: "Multi-toolhead printers (like the Snapmaker U1) expose per-slot material selection — N dropdowns, one per extruder."

---

### [DOC-006] — Major — Architecture — ARCHITECTURE.md has no entry for `SnapmakerConnector`

**Evidence**

`ARCHITECTURE.md` — Module map section (lines ~96–121): every connector module has a one-line entry (`bambu_connector.py`, `octoprint_connector.py`, `moonraker_connector.py`, `prusalink_connector.py`, `duet_connector.py`, `marlin_connector.py`). `snapmaker_connector.py` is not listed.

**Why this matters**

The module table is how a new contributor orients to the codebase. An absent entry for the Snapmaker connector means a new developer doesn't know it exists, doesn't know it overrides `capabilities()` and `status()` specifically, and doesn't know it is the multi-toolhead exemplar in the codebase. When adding a future multi-toolhead printer (e.g. Bambu X1 AMS), they lack the obvious reference.

**Blast radius**

- Adjacent: The module table is self-contained; no other doc duplicates it.
- Related findings: none.

**Fix path**

Add after the `moonraker_connector.py` entry: `| snapmaker_connector.py | \`SnapmakerConnector(MoonrakerConnector)\` for the Snapmaker U1 (Klipper/Moonraker-based, 4-toolhead). Overrides \`capabilities()\` to detect active extruder objects and report \`toolhead_count\`, and \`status()\` to build \`toolhead_temps\` (T0–T3). All send/job/pause/resume/cancel is inherited from \`MoonrakerConnector\`. |`

---

### [DOC-007] — Major — Onboarding — `config/default.yaml` snapmaker_u1 connector template is comment-only and explains too little

**Evidence**

`config/default.yaml` lines 465–470:
```yaml
# Connector template (copy to config/local.yaml and fill in base_url):
# connectors:
#   snapmaker_u1:
#     type: snapmaker
#     base_url: http://192.168.1.xxx:7125
#     # api_key_env: SNAPMAKER_API_KEY  # optional; Moonraker typically runs unauthenticated
```

The comment does not explain:
1. That `type: snapmaker` exists and is distinct from `type: moonraker` (a user who glances at the moonraker entry would just use that).
2. Why port 7125 specifically (Moonraker default — worth naming).
3. That multi-material slicing uses `filament_slot_0`..`filament_slot_3` in the API.
4. That pause/resume/cancel are available for this printer type.

The comment also appears inside the printer stanza (`snapmaker_u1:`) rather than in the global `connectors:` block, which is where connectors live. This works, but a user reading the top-level `connectors:` block will never see this template.

**Why this matters**

The `config/default.yaml` is the primary self-service setup guide for a user running KimCad from source. An incomplete connector template means the Snapmaker U1 user has to read the source or the test file to understand the setup.

**Blast radius**

- Adjacent: `docs/getting-started-windows.md` and Settings → Printer connections UI both rely on the config schema being self-explanatory.
- Related findings: DOC-003.

**Fix path**

Move or duplicate the template comment to the global `connectors:` block (parallel to the `moonraker:`, `duet:`, `marlin:` entries). Expand it:

```yaml
# Snapmaker U1 (Klipper/Moonraker-based, 4-toolhead). Uses the 'snapmaker' type (not
# 'moonraker') to auto-detect active extruders and report per-extruder temperatures.
# Port 7125 is the Moonraker default; the API key is OPTIONAL.
# snapmaker_u1:
#   type: snapmaker
#   base_url: http://192.168.1.xxx:7125
#   api_key_env: SNAPMAKER_API_KEY   # optional; omit if Moonraker runs unauthenticated
```

---

### [DOC-008] — Minor — Completeness — No user-facing explanation of multi-toolhead workflow (N material dropdowns, filament slots)

**Evidence**

`docs/USER-MANUAL.md` — no section on multi-toolhead printers, material slot selection, or the `filament_slot_0..N-1` fields. `docs/guide-sliders-and-units.md` — covers sliders and units but not material selection for multi-extruder prints. The SPA now renders N material dropdowns for printers with `toolhead_count > 1`, but there is no user-facing explanation of what these mean (assign a filament to each extruder, they correspond to T0..TN-1).

**Why this matters**

A Snapmaker U1 user sees four material dropdowns and may not understand whether they must fill all four, whether unused extruders should get a filler material, or how the per-slot selection maps to the actual extruder objects T0–T3. This is a new workflow with no existing analogue in the single-extruder documentation.

**Blast radius**

- Adjacent: FAQ.md also has no entry covering multi-toolhead.

**Fix path**

Add a paragraph to the "Slice & prepare" section of `docs/USER-MANUAL.md`: "Multi-toolhead printers (like the Snapmaker U1) show one material dropdown per extruder (T0..TN-1). Assign the filament for each toolhead. Extruders left at the default material will print in that material. The slice uses these slots in order."

---

### [DOC-009] — Nit — Tone — `config/default.yaml` comment says "Moonraker typically runs unauthenticated" but this is only true on a trusted LAN

**Evidence**

`config/default.yaml` line 470: `# api_key_env: SNAPMAKER_API_KEY  # optional; Moonraker typically runs unauthenticated`

The existing `moonraker:` connector comment (line 510) says "Moonraker's API key is OPTIONAL (often unauthenticated on a trusted LAN)" — which is more precise. The Snapmaker comment drops the "trusted LAN" qualifier.

**Fix path**

Change to: `# optional; Moonraker typically runs unauthenticated on a trusted LAN`

---

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.

---

## Patterns and systemic observations

This feature followed the project's established technical discipline (tests, mock server updates, TypeScript type updates, `connectors.py` factory wiring) but did not touch any of the prose documentation layers. Every prior feature at the KimCad stage-gate level included parallel changelog, API doc, and supported-printers updates as part of the commit. The gap here is consistent across all five prose layers simultaneously, suggesting documentation was not in the definition-of-done checklist for this commit. Recommend adding `docs/api.md`, `CHANGELOG.md`, and `docs/supported-printers.md` to the per-feature checklist.

---

## Appendix: docs reviewed

- `C:\Users\scott\Desktop\Code\kimcadclaude\CHANGELOG.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\api.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\supported-printers.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\README.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\ARCHITECTURE.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\config\default.yaml`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\USER-MANUAL.md` (partial — searched for relevant terms)
- `C:\Users\scott\Desktop\Code\kimcadclaude\src\kimcad\snapmaker_connector.py` (source read for accuracy checks)
- `C:\Users\scott\Desktop\Code\kimcadclaude\src\kimcad\webapp.py` (searched for field names)
- `C:\Users\scott\Desktop\Code\kimcadclaude\src\kimcad\printer_connector.py` (searched for field names)
