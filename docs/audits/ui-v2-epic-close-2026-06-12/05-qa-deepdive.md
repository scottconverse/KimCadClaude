# 05 - QA Deep-Dive

## Scope

Running product QA against `kimcad web --demo`, plus focused API probes.

## What's Working

- Desktop and mobile routes rendered without horizontal overflow.
- The browser console was clean after remediation.
- `/api/templates` returns live registry data, so future template catalog additions flow into the library browser automatically.
- Unknown print-outcome id returns a clean 404, not a 500.

## Findings

No open runtime QA findings after remediation.

## Could Not Assess

The physical printer path was not exercised on real hardware. It was covered by the existing connector abstractions and a stubbed non-simulated connector test.
