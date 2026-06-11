# Supported printers (beta)

**The short version:** KimCad ships the **full OrcaSlicer profile library — roughly 65
printer brands and 1,400+ machine profiles** (Bambu Lab, Creality, Prusa, Anycubic, Elegoo,
Voron, Sovol, Qidi, Artillery, and dozens more) inside the installer. On top of that library,
three **reference printers** are wired end-to-end today — design checks, build-volume gate,
and a slice **proven in CI** on every push. Surfacing the rest of the library in the printer
picker is in progress ([#22](../../issues/22)); the profiles are already on your disk.

Honesty key — three different claims, kept separate on purpose:

- **Profile-shipped:** the machine's slicer profile is bundled (the ~1,400). The slicer
  knows the machine; KimCad doesn't yet offer it in the picker.
- **API-validated (reference tier):** KimCad checks designs against the machine's build
  volume and slices with its real profile, proven by tests on every push — and the
  connection protocol works against the printer's own software interface (real or
  conformance-mock). **No physical print has run.**
- **Metal-validated:** a real part printed on the real machine. *Nothing is
  metal-validated yet* — that's the beta's own job (see
  `docs/beta/first-hardware-contact.md`).

## Reference printers (design checks + slice proven in CI)

| Printer | Design checks | Slice profile | Notes |
|---|---|---|---|
| Bambu Lab P2S | ✅ | ✅ (proven to slice) | the reference printer |
| Bambu Lab A1 | ✅ | ✅ (proven to slice) | |
| Elegoo Neptune 4 Max | ✅ | ✅ (proven to slice) | |

"Proven to slice" = real OrcaSlicer produced a valid G-code 3MF for the profile in tests
— software validation, not yet a print.

## Direct-send connections

| Connection | Printers | Status |
|---|---|---|
| `bambu` (native LAN) | P2S, A1 | **API-validated against a verified mock** of the printer's MQTT/FTPS protocols; metal pending |
| `octoprint` | any OctoPrint box | API-validated against a real OctoPrint REST mock |
| `moonraker` | Klipper (Voron, Creality-Klipper, …) | API-validated (conformance mock); ships as a fill-in template in Settings → Printer connections |
| `prusalink` | MK4 / MK3.9 / MINI / XL | API-validated (conformance mock); ships as a fill-in template in Settings → Printer connections |
| `mock` | none (built-in test connection) | proves the send path, drives nothing |

The Elegoo Neptune 4 Max has **no direct-send connection** — its path is download the
`.gcode.3mf` and load it via USB/screen (its Klipper variant may work via `moonraker`;
untested, so unlisted).

Every send requires your explicit in-app confirmation, and a part that failed the
printability check can never be sent.
