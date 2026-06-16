# Documentation Deep-Dive (Round 2 — post-remediation) — KimCad Snapmaker U1 + Multi-Toolhead

**Audit date:** 2026-06-16 (round 2)
**Role:** Technical Writer
**Scope re-audited:** CHANGELOG.md, docs/api.md, docs/supported-printers.md, README.md, ARCHITECTURE.md, config/default.yaml, docs/USER-MANUAL.md — Snapmaker U1 + generic multi-toolhead feature
**Method:** open each file, verify each round-1 finding with file:line evidence; cross-check every doc claim against `src/kimcad/webapp.py`, `src/kimcad/snapmaker_connector.py`, `config/default.yaml`, the shipped Orca profile JSON, and the verification tests.
**Auditor posture:** Balanced

---

## TL;DR

The remediation is thorough and, more importantly, **accurate**. All nine round-1 findings (4 Critical, 3 Major, 1 Minor, 1 Nit) are RESOLVED with verifiable file:line evidence. The new prose does not merely mention the feature — it correctly describes the *implemented* behavior: the `filament_slot_N` fallback-to-`material` semantics match `webapp.py` exactly, the "always slices per-slot for multi-head" claim matches the code, `toolhead_count` is sourced from config (authoritative) as the code comments document, and the `toolhead_temps`-can-be-shorter-than-`toolhead_count` subtlety is carried honestly into both `api.md` and the connector docstring. The printer count was reconciled to **~30** across README, supported-printers, and USER-MANUAL. The build-volume figure (270.5 × 271.0 × 270.1) is faithful to the codebase's own KC-7 convention (max corner of `printable_area` + `printable_height`), which a binary-gated test enforces against the shipped Orca profile — so it is not a fabricated number. One micro-discrepancy remains (the Z figure is the round of a 270.05 source) and one tiny internal-consistency nit; both are Nit-grade and arguably acceptable as-is.

**Final documentation roll-up: 0 Blocker / 0 Critical / 0 Major / 0 Minor / 1 Nit.**

---

## Round-1 finding resolution table

| ID | Sev (R1) | Title | Status | Evidence |
|---|---|---|---|---|
| DOC-001 | Critical | CHANGELOG has no Snapmaker/multi-toolhead entry | **RESOLVED** | `CHANGELOG.md:9-29` — full `[Unreleased] → Added` block: the `snapmaker` connector type, per-extruder temps, the catalog entry (build volume, 4 toolheads, PLA/PETG/TPU/ABS, "API-validated against a conformance mock — no real-hardware validation yet"), per-slot multi-material slicing with the `filament_slot_N` semantics, the new `/api/options` + `/api/connector-status` fields, and pause/resume/cancel on the Protocol. |
| DOC-002 | Critical | api.md missing new fields on options / connector-status / slice | **RESOLVED** | `docs/api.md:104-115` (`/api/slice` — `filament_slot_0..N-1`, fallback, always-per-slot); `:148-154` (`/api/connector-status` — `nozzle_temp_c`, `toolhead_temps`, shorter-than-count caveat); `:209-214` (`/api/options` — `toolhead_count`, 1 vs N, U1=4). |
| DOC-003 | Critical | api.md has no `snapmaker` connector type | **RESOLVED** | `docs/api.md:161-165` — `snapmaker` added to the connector `type` vocabulary with the "extends moonraker / 4-toolhead / inherits send/job/pause/resume/cancel" description. Also `docs/supported-printers.md:83` (new direct-send row). |
| DOC-004 | Critical | supported-printers.md does not list the U1 | **RESOLVED** | `docs/supported-printers.md:67` (curated table row: `Snapmaker | U1 (4-toolhead — PLA/PETG/TPU/ABS) | 270.5 × 271.0 × 270.1`); `:83` (direct-send row); preamble `:6` count updated to `~30`. |
| DOC-005 | Major | README omits U1 / multi-toolhead | **RESOLVED** | `README.md:25` (Slice-&-print bullet now lists Snapmaker + "Multi-toolhead printers like the Snapmaker U1 expose per-extruder material selection — one dropdown per extruder"); `:41` (brand list adds Snapmaker, count `~30`); `:311` (connector table row). |
| DOC-006 | Major | ARCHITECTURE.md has no `SnapmakerConnector` entry | **RESOLVED** | `ARCHITECTURE.md:100` — module-map row for `snapmaker_connector.py` describing the `MoonrakerConnector` subclass, the `capabilities()`/`status()` overrides, `toolhead_temps` (T0–T3), inherited send/job/pause/resume/cancel, "the multi-toolhead exemplar." Also wired into the connector-factory line `:109`. |
| DOC-007 | Major | default.yaml connector template comment-only / underdocumented / in wrong block | **RESOLVED** | `config/default.yaml:509-518` — the template now lives in the global `connectors:` block (parallel to `moonraker`/`prusalink`), with an expanded comment: why `type: snapmaker` not `moonraker`, auto-detect + per-extruder temps, port 7125 is Moonraker's default, optional API key, ships visible-but-unconfigured. The printer stanza `:451-465` cross-references it (`:465`). |
| DOC-008 | Minor | No user-facing multi-toolhead workflow in USER-MANUAL | **RESOLVED** | `docs/USER-MANUAL.md:204-217` — a "Multi-toolhead printers" subsection: one dropdown per extruder (Extruder 1..N → T0..T(N-1)), assign filament per head, omitted slots print in the default, slots used in order, single-extruder printers unaffected, plus the config-is-authoritative caveat. |
| DOC-009 | Nit | snapmaker comment dropped the "trusted LAN" qualifier | **RESOLVED** | `config/default.yaml:512` and `:518` — both now read "Moonraker typically runs unauthenticated on a trusted LAN," matching the `moonraker:` entry's phrasing. |

**Round-1 result: 9 / 9 RESOLVED. No round-1 finding remains OPEN.**

---

## Accuracy cross-check (the load-bearing part of this re-audit)

Resolution is necessary but not sufficient — a doc can mention a feature and still lie about it. Each new claim was checked against the implementation.

### (a) `filament_slot_N` semantics — VERIFIED ACCURATE

- **Doc claim** (`docs/api.md:114-115`): "Any omitted slot falls back to the `material` field. A multi-toolhead printer always slices per-slot; single-toolhead printers ignore the `filament_slot_*` fields and use `material`." Echoed in `CHANGELOG.md:17-21` and `USER-MANUAL.md:208-211`.
- **Code** (`src/kimcad/webapp.py:2479-2489`): for `printer_cfg.toolhead_count > 1`, the handler builds `slots = tuple(str(data.get(f"filament_slot_{i}") or material_key or "") for i in range(toolhead_count))` and sets `filament_slots = slots` **unconditionally** (ENG-001 comment). Each missing slot falls back to `material_key`; a multi-head printer is always sliced per-slot (the tuple is fully populated even when no slot fields are sent); single-head printers never enter the branch and use `material_key`.
- **Verdict:** the docs match the code precisely, including the unconditional-per-slot subtlety.

### (b) `toolhead_count` semantics — VERIFIED ACCURATE

- **Doc claim** (`docs/api.md:211-214`): "`toolhead_count` is an integer — 1 for a single-toolhead printer; N for a multi-toolhead printer (the Snapmaker U1 reports 4)." USER-MANUAL `:213-217` and api.md `/api/slice` both state the value comes from the printer **config**, authoritative, so slicing works while the printer is off.
- **Code:** `/api/options` emits `"toolhead_count": p.toolhead_count` (`webapp.py:555`); the slice path reads `get_config().printer(printer_key).toolhead_count` with the ENG-003 comment "read from the printer CONFIG (authoritative), not a live connector" (`webapp.py:2475-2479`). `config/default.yaml:456` sets `toolhead_count: 4`. The connector's live `capabilities()` independently derives 4 from active extruder objects (`snapmaker_connector.py:77`), but the slice path deliberately uses config — exactly as the docs say.
- **Verdict:** accurate, and the docs correctly disclose the config-authoritative design decision (a subtle point most doc passes miss).

### (c) Build-volume figure 270.5 × 271.0 × 270.1 vs config's 270.05 Z — ACCEPTABLE (consistent convention; 1 Nit)

- **Config** (`config/default.yaml:453`): `build_volume: [270.5, 271.0, 270.05]`, tagged `# VERIFIED from shipped Orca printable_area`.
- **Source of truth** (`tools/orcaslicer/resources/profiles/Snapmaker/machine/Snapmaker U1 (0.4 nozzle).json:108-114`): `printable_area` corners `0.5x1 / 270.5x1 / 270.5x271 / 0.5x271`, `printable_height: "270.05"`.
- **Codebase convention** (`tests/test_config.py:206-227`, KC-7, binary-gated): every printer's `build_volume` must equal `(max(xs), max(ys), float(printable_height))` of its shipped Orca profile. For the U1 that is `(270.5, 271.0, 270.05)` — exactly the config value, and the same max-corner convention used for all ~30 catalog printers. So **270.5 × 271.0 is not a doc fabrication** — it is the established, test-enforced convention, not a Snapmaker-specific error.
- **The only residual:** the docs render Z as **270.1** (a 1-decimal round of 270.05). `CHANGELOG.md:14` hedges with "≈"; `docs/supported-printers.md:67` presents `270.5 × 271.0 × 270.1` as a plain figure in a column otherwise holding integer dimensions. Rounding 270.05 → 270.1 is standard round-half-up and changes no user decision (sub-0.1 mm on Z), so this is at most a **Nit** (NEW-DOC-01 below). It would read marginally cleaner as `270.05` to match the config verbatim, or with a "≈" like the CHANGELOG.

### (d) Printer count consistency (~30) — VERIFIED CONSISTENT across live docs

- `README.md:41` ("~30 printers", brand list now includes Snapmaker), `docs/supported-printers.md:6` ("~30 popular current machines"), `docs/USER-MANUAL.md:197` and `:368` ("~30") all agree.
- Curated-table row count in `supported-printers.md` now includes the Snapmaker row (`:67`).
- The only remaining "29"/"~29" strings are in **dated audit archives** (`docs/audits/cleanup-review-0.9.0b2-2026-06-14.md`, `docs/audits/audit-team-0.9.0b2-2026-06-14/*`, and round-1's own deep-dive) — historical records that correctly describe the pre-U1 state and must not be edited. `CHANGELOG.md:112` ("29-printer catalog") sits inside the frozen `[0.9.0b2]` release section, which was accurate at that tag; the live `[Unreleased]` block is the right place for the +1, and the README/preamble counts (the user-facing surfaces) are current. No live-doc contradiction.

### Other claims spot-checked

- **`toolhead_temps` is T0..T(N-1), can be shorter than `toolhead_count`** — `api.md:148-154`, `CHANGELOG.md:24-27`, `ARCHITECTURE.md:100` all carry this. Matches `snapmaker_connector.py:39-43, 114-128` (only extruders reporting a numeric temperature are appended; a `temperature: null` head is omitted) — accurate, including `nozzle_temp_c = temps[0] if temps else None` (`:125`).
- **"inherits the full Moonraker send/job/pause/resume/cancel"** — matches `snapmaker_connector.py:32-44` (only `capabilities`/`status` overridden) and `moonraker_connector.py` (pause/resume/cancel implemented). Accurate.
- **README `:25` "one dropdown per extruder"** and **USER-MANUAL `:206-208` "Extruder 1..N map to T0..T(N-1)"** — consistent with each other and with the API's per-slot model.
- **`snapmaker` in the connector factory** — `ARCHITECTURE.md:109` lists `snapmaker` in `build_connector`'s resolved set; matches `connectors.py` (per round-1 source read).

---

## New findings (round 2)

### [NEW-DOC-01] — Nit — Accuracy — Z build-volume figure shown as 270.1 (rounded) vs config/source 270.05

**Evidence**
- `docs/supported-printers.md:67`: `270.5 × 271.0 × 270.1` — plain figure, in a table column whose other rows are integer dimensions.
- `CHANGELOG.md:14`: `build volume ≈ 270.5 × 271.0 × 270.1 mm` (hedged with "≈", which is fine).
- Source: `config/default.yaml:453` stores Z as `270.05`; the Orca profile's `printable_height` is `"270.05"`.

**Why this matters (lightly):** No persona is misled in any actionable way — 0.05 mm on the Z envelope changes nothing a user decides, and the X/Y/Z convention itself is correct and test-enforced. It is purely a presentation micro-inconsistency: one source value (270.05) rendered two ways (verbatim in config, rounded in the table). The CHANGELOG already models the honest form by prefixing "≈".

**Fix path (optional):** in `supported-printers.md:67`, either print `270.05` to match config verbatim, or prefix the figure with "≈" as the CHANGELOG does. Either makes the rounding explicit. Genuinely a Nit — flag once, do not belabor; acceptable to leave as-is.

*(No blast radius — Nit.)*

### Internal-consistency observation (sub-Nit, no action required)

`docs/USER-MANUAL.md:369` says "Direct send covers **eight** connectors" and the following table (`:374-381`) lists exactly eight rows (`loopback`, `bambu`, `octoprint`, `moonraker`, `snapmaker`, `prusalink`, `duet`, `marlin`) — internally consistent and correct. `supported-printers.md:78-87` lists the same eight (it phrases it as "seven" direct-send types **plus** `mock` at `:200-202` of USER-MANUAL, counting `mock` separately) — the two pages count the built-in `mock`/`loopback` differently (USER-MANUAL includes it in "eight," supported-printers/`USER-MANUAL:200` says "seven" real ones + the test connection). Both statements are individually true; the small framing difference (does `mock` count as a "connector"?) is not a defect and needs no change. Noted only for completeness.

---

## What's working (credit where due)

- **The remediation is accurate, not just present.** Every new sentence was checked against the code and the shipped Orca profile; the docs describe the implemented behavior, including three subtleties that are easy to get wrong: per-slot-is-unconditional-for-multi-head, `toolhead_count`-comes-from-config-not-hardware, and `toolhead_temps`-can-be-shorter-than-`toolhead_count`. This is the opposite of the round-1 gap.
- **Honesty maintained.** Every new mention carries the project's standing honesty discipline: "API-validated against a conformance mock — no real-hardware validation yet" (`CHANGELOG.md:16`, `supported-printers.md:83`, README beta notes). No overclaim of metal validation.
- **The `config/default.yaml` template is now genuinely self-service** (`:509-518`) — it answers the exact questions round-1's persona walk-through said a user would ask (why `snapmaker` not `moonraker`, port 7125, optional key), and it lives where users look (the `connectors:` block) with a cross-reference from the printer stanza.
- **Cross-document coherence.** README, USER-MANUAL, supported-printers, api.md, ARCHITECTURE, and CHANGELOG now tell one consistent story about the U1, the count, the connector type, and the slice contract.

---

## OPEN-only roll-up

| Severity | Open count | IDs |
|---|---|---|
| Blocker | 0 | — |
| Critical | 0 | — |
| Major | 0 | — |
| Minor | 0 | — |
| Nit | 1 | NEW-DOC-01 (Z figure 270.1 vs 270.05 — optional; acceptable as-is) |

All nine round-1 findings RESOLVED. One new Nit, optional. Documentation is ship-ready for this feature.

---

## Appendix: artifacts reviewed (round 2)

- `C:\Users\scott\Desktop\Code\kimcadclaude\CHANGELOG.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\api.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\supported-printers.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\README.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\ARCHITECTURE.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\config\default.yaml`
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\USER-MANUAL.md`
- `C:\Users\scott\Desktop\Code\kimcadclaude\src\kimcad\webapp.py` (`_handle_slice` / `filament_slot_*`, `_printer_entry`, connector-status temps)
- `C:\Users\scott\Desktop\Code\kimcadclaude\src\kimcad\snapmaker_connector.py`
- `C:\Users\scott\Desktop\Code\kimcadclaude\tests\test_config.py` (KC-7 build-volume convention) and `tests\test_snapmaker_connector.py`
- `C:\Users\scott\Desktop\Code\kimcadclaude\tools\orcaslicer\resources\profiles\Snapmaker\machine\Snapmaker U1 (0.4 nozzle).json` (printable_area / printable_height source of truth)
