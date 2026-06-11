# Supported printers (beta)

Honesty key — two different claims, kept separate on purpose:

- **API-validated:** the connection protocol works against the printer's own software
  interface (real or conformance-mock), proven by tests. **No physical print has run.**
- **Metal-validated:** a real part printed on the real machine. *Nothing is
  metal-validated yet* — that's the beta's own job (see
  `docs/beta/first-hardware-contact.md`).

## Design + slice profiles (what KimCad checks and slices against)

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
| `moonraker` | Klipper (Voron, Creality-Klipper, …) | API-validated (conformance mock) |
| `prusalink` | MK4 / MK3.9 / MINI / XL | API-validated (conformance mock) |
| `mock` | none (built-in test connection) | proves the send path, drives nothing |

The Elegoo Neptune 4 Max has **no direct-send connection** — its path is download the
`.gcode.3mf` and load it via USB/screen (its Klipper variant may work via `moonraker`;
untested, so unlisted).

Every send requires your explicit in-app confirmation, and a part that failed the
printability check can never be sent.
