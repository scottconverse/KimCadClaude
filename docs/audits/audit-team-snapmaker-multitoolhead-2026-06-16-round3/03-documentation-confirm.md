# Round-3 Documentation Confirmation — Snapmaker U1 multi-toolhead

**Role:** Technical Writer (focused confirmation pass)
**Date:** 2026-06-16
**Scope:** Single residual open after round 2 — NEW-DOC-01 (Nit).

## NEW-DOC-01 — Z build-volume figure 270.1 (rounded) vs source 270.05

**Status: RESOLVED.**

Evidence (live docs now print the exact value, matching config):

- `docs/supported-printers.md:67` — Snapmaker row reads
  `| **Snapmaker** | U1 (4-toolhead — PLA/PETG/TPU/ABS) | 270.5 × 271.0 × 270.05 |`. ✓ exact.
- `CHANGELOG.md:14` — reads `build volume 270.5 × 271.0 × 270.05 mm` — the `≈` hedge was
  dropped because the figure is now verbatim. ✓ exact, no approximation marker.
- `config/default.yaml:453` — `build_volume: [270.5, 271.0, 270.05]` (VERIFIED from shipped
  Orca `printable_area`). Prose now matches config byte-for-byte on all three axes. ✓

## Remaining `270.1` in live docs

**None.** A repo-wide grep for `270\.1` returns matches ONLY inside
`docs/audits/audit-team-...-2026-06-16/` and `...-round2/` report archives (historical
records, must NOT be edited). No `270.1` survives in README.md, docs/supported-printers.md,
docs/USER-MANUAL.md, docs/api.md, CHANGELOG.md, or any other live doc.

## Regression hunt — count + brand consistency

No count/consistency claim was disturbed. The "~30 printers" curated-catalog count and the
brand list are consistent across all three live docs (Snapmaker present in each):

- `README.md:41` — "curated catalog of ~30 printers" across "Bambu, Creality, Prusa, Anycubic,
  Elegoo, Qidi, Sovol, Snapmaker".
- `docs/supported-printers.md:6` — "curated catalog of ~30 popular current machines".
- `docs/USER-MANUAL.md:197-198` — "curated catalog of ~30 popular current machines" across
  "Bambu, Creality, Prusa, Anycubic, Elegoo, Qidi, Sovol, Snapmaker".

## Test evidence

`.venv\Scripts\python.exe -m pytest tests/ -k "doc or supported or version or changelog or catalog" -q`

```
110 passed, 1522 deselected in 92.29s (0:01:32)
```

## New findings

None.

## DOC roll-up

**DOC: 0/0/0/0/0** (Blocker / Critical / Major / Minor / Nit all zero). Docs clean.
