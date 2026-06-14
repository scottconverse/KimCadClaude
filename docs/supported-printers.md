# Supported printers (beta)

**The short version:** KimCad ships the **full OrcaSlicer profile library — roughly 65
printer brands and 1,400+ machine profiles** (Bambu Lab, Creality, Prusa, Anycubic, Elegoo,
Voron, Sovol, Qidi, Artillery, and dozens more) inside the installer. On top of that library,
the printer picker now offers a **curated catalog of ~29 popular current machines across the
top makers** — each one with a build-volume gate and a slice **proven in CI** — and three of
those are **reference printers** wired end to end (slice + native connection). The rest of the
1,400-profile library is on your disk and can be promoted into the catalog as each machine is
slice-verified ([#22](../../issues/22)).

Honesty key — four different claims, kept separate on purpose:

- **Profile-shipped:** the machine's slicer profile is bundled (the ~1,400). The slicer knows
  the machine; KimCad doesn't offer it in the picker yet.
- **Catalog (slice-proven):** KimCad offers the machine in the picker, checks designs against
  its build volume (verified against the shipped Orca profile on every CI run), and a real
  OrcaSlicer slice of a test part is **proven in CI** with its machine + process + filament
  profiles. **No direct-send connection and no physical print** — you export the `.gcode.3mf`
  (or `.stl`) and load it via USB/SD/your slicer.
- **Reference tier (also API-validated):** everything in the catalog tier, PLUS a direct-send
  connection proven against the printer's own software interface (real or conformance-mock).
  These are KimCad's target hardware. **No physical print has run.**
- **Metal-validated:** a real part printed on the real machine. *Nothing is metal-validated
  yet* — that's the beta's own job (see `docs/beta/first-hardware-contact.md`).

## Reference printers (catalog + direct-send connection)

| Printer | Design checks | Slice profile | Connection |
|---|---|---|---|
| Bambu Lab P2S | ✅ | ✅ (proven to slice) | `bambu` native LAN (mock-validated) |
| Bambu Lab A1 | ✅ | ✅ (proven to slice) | `bambu` native LAN (mock-validated) |
| Elegoo Neptune 4 Max | ✅ | ✅ (proven to slice) | export `.gcode.3mf` (USB/screen) |

## Curated printers (build-volume gate + slice proven in CI)

Each printer below is offered in the picker, its build volume is verified against its shipped
OrcaSlicer machine profile on every CI run, and a 20 mm box was sliced through the real
OrcaSlicer with its machine + process + filament profiles (the "proven to slice" bar). Materials
are listed per printer **in the app** — only the materials whose shipped filament profile
actually slices on that machine are offered (e.g. the Bambu A1 mini offers no ABS; the Elegoo
Neptune family offers no TPU), so a material that isn't shown is honestly "not available on this
printer" rather than silently mis-mapped. Direct-send is not wired for these (export and load).

| Brand | Machines | Build volume(s) (mm) |
|---|---|---|
| **Bambu Lab** | P1P, P1S, X1 Carbon, X1E | 256 × 256 × 250 |
| | A1 mini | 180 × 180 × 180 |
| **Creality** | K1, K1C, Ender-3 V3 | 220 × 220 × 250 |
| | K1 Max | 300 × 300 × 300 |
| | K2 Plus | 350 × 350 × 350 |
| | Ender-3 V3 KE | 220 × 220 × 245 |
| | CR-10 SE | 220 × 220 × 265 |
| **Prusa** | MK4 | 250 × 210 × 220 |
| | MINI / MINI+ | 180 × 180 × 180 |
| **Anycubic** | Kobra 2 | 220 × 220 × 250 |
| | Kobra 2 Max | 420 × 420 × 500 |
| | Kobra S1 | 250 × 250 × 250 |
| **Elegoo** | Neptune 4 | 225 × 225 × 265 |
| | Neptune 4 Pro | 235 × 230 × 265 |
| | Neptune 4 Plus | 320 × 320 × 385 |
| **Qidi** | Q1 Pro | 245 × 245 × 240 |
| | X-Max 3 | 325 × 325 × 315 |
| | X-Plus 3 | 280 × 280 × 270 |
| **Sovol** | SV06 / SV07 | 220 × 220 × 250 |
| | SV08 | 350 × 350 × 345 |

"Proven to slice" = real OrcaSlicer produced a valid, motion-bearing G-code 3MF for the
profile in CI — software validation, not yet a physical print. The catalog is generated and
re-verified by `scripts/build_printer_catalog.py --verify`; more of the bundled 1,400-profile
library is promoted into this table as each machine clears the slice bar (some current
omissions — e.g. a few Prusa input-shaper and Klipper relative-extruder profiles — fail a
headless slice and are intentionally left in the profile-shipped tier until fixed).

## Direct-send connections

| Connection | Printers | Status |
|---|---|---|
| `bambu` (native LAN) | P2S, A1 | **API-validated against a verified mock** of the printer's MQTT/FTPS protocols; metal pending |
| `octoprint` | any OctoPrint box | API-validated against a real OctoPrint REST mock |
| `moonraker` | Klipper (Voron, Creality-Klipper, …) | API-validated (conformance mock); ships as a fill-in template in Settings → Printer connections |
| `prusalink` | MK4 / MK3.9 / MINI / XL | API-validated (conformance mock); ships as a fill-in template in Settings → Printer connections |
| `mock` | none (built-in test connection) | proves the send path, drives nothing |

The curated (non-reference) printers have **no direct-send connection** — their path is export
the `.gcode.3mf` (or `.stl`) and load it via USB/SD/your printer's own software. A Klipper-based
machine can often be wired through `moonraker`; that's untested per-machine, so it's unlisted.

Every send requires your explicit in-app confirmation, and a part that failed the printability
check can never be sent.
