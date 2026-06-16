# Next-Sprint Watchlist — Snapmaker U1 + Multi-Toolhead Feature

**Audit date:** 2026-06-16

---

## Structural / architectural

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | ENG-003 | Engineering | `toolhead_count` at slice time comes from static config, never from the live connector's `capabilities()`. A Snapmaker U1 with fewer heads mounted (2-of-4) will receive a 4-head G-code the printer cannot execute. Options: (a) re-query capabilities before slicing, (b) display a live toolhead_count from the connector on the UI, (c) document the limitation explicitly. | Before Snapmaker U1 ships to beta users |
| 2 | ENG-004 | Engineering | When a real Snapmaker U1 returns `temperature: null` for a disconnected extruder, the `if t is not None` guard silently drops that extruder from `toolhead_temps`. The resulting tuple is shorter than `toolhead_count`, and any downstream code that does `toolhead_temps[toolhead_count - 1]` will `IndexError`. Add a sentinel (e.g. `float('nan')`) or pad to `toolhead_count` length. | Before real-hardware validation (#11) |

---

## Design debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | UX-003 | UI/UX | N material dropdowns have no layout cap. At `toolhead_count > 3` the Slice button can scroll below the visible area of the ExportPanel card. Consider: two-column auto-fill grid for the slot block, or a cap at display + a scroll container, or a compact chip-select row. Decide before any printer with > 4 toolheads is added to `default.yaml`. |
| 2 | UX-004 | UI/UX | The post-slice summary (`SliceResponse.material`) only echoes the primary slot. A user who assigned PLA to T1 and PVA support to T2 has no confirmation that T2 was honored. Options: (a) extend `SliceResponse` to include a `materials` array, (b) show the slot assignments in the success card from frontend state (no backend change). |
| 3 | UX-005 | UI/UX | Dynamic `T{i+1} Material` dropdowns use implicit label association only. Add explicit `id`/`htmlFor` pairs per slot so screen readers announce the correct label on focus. One-liner per slot in the `ExportPanel.tsx` map. |

---

## Documentation debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | DOC-003 | Docs | `snapmaker` connector type does not appear in `docs/api.md`'s connector configuration section or in `docs/supported-printers.md`'s direct-send column. A user following the docs cannot discover how to enable direct send for a Snapmaker U1. Add after the Moonraker section — the config block is already in `default.yaml` comments. |
| 2 | DOC-005 | Docs | No user-facing documentation explains the multi-toolhead workflow: when N dropdowns appear, what the slot assignments do, how the resulting G-code differs, and what the T1–TN temperature chips mean. A single paragraph in the user manual or a tooltip would unblock new multi-head users. |

---

## Test-culture debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | TEST-004 | Test | The mock Moonraker always returns all 4 extruder objects. Partial toolhead presence (1-of-4, 2-of-4) is never tested. Add a `extruder_count` parameter to `serve_mock_moonraker()` so tests can simulate a Snapmaker U1 variant with fewer heads mounted. |
| 2 | TEST-005 | Test | No frontend test covers the ExportPanel `materialSlots` reset useEffect (switching from 4-head to 1-head printer clears slots). Add a vitest component test using `@testing-library/react`. |
| 3 | TEST-006 | Test | Add to the PR definition-of-done checklist (`docs/dev/definition-of-done.md`): "CHANGELOG updated", "api.md updated for any new endpoint field or request body field", "supported-printers.md updated for any new printer entry". This audit found a systemic gap — enforce it structurally. |

---

## Performance and scaling

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | QA-001 | QA | The test named `test_capabilities_toolhead_count_at_least_1` asserts `caps.toolhead_count >= 1` but the mock returns 4, so the floor guard is never actually tested. Rename or restructure when TEST-004 (partial extruder mock) is implemented. | When TEST-004 is implemented |

---

## Decisions needing product/leadership input

- **ENG-003** — Does KimCad re-query live connector capabilities before slicing, or rely on static config? If re-query: adds a network round-trip to the slice path; must handle offline gracefully. If static config: must prominently warn users that the slot count shown is from config, not the connected hardware. Scott to decide before Snapmaker U1 exits beta.

---

## Review cadence

- Revisit at next sprint planning — elevate ENG-003/004 if real-hardware validation (#11) is imminent
- Revisit UX-003/004 if any printer with > 4 toolheads is proposed for the catalog

---

*Generated from the `audit-team` skill. Each entry cross-references its full treatment in the relevant role deep-dive.*
