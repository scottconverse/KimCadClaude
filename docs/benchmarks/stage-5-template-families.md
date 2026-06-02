# Stage 5 - deterministic template-family benchmark

Every built-in template family, re-rendered through the real `Pipeline.rerender` path (the same one `POST /api/render` runs): emit -> OpenSCAD -> validate -> orient -> harden -> export. No prompt, no model call -- `rerender` invokes no LLM, and the benchmark wires a provider that *raises* if one is ever called, so "no model" is enforced, not assumed.

**Generated:** 2026-06-02

**Environment**

- Platform: `Windows-11-10.0.26200-SP0`
- Processor: `AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD`
- Python: `3.14.3`

**Targets:** re-render under 1s (interactive); automated gate ceiling 5s; envelope tolerance 0.05 mm.

| Family | Re-render (s) | Under 1s | Initial (s) | bbox err (mm) | Watertight | No model |
| --- | ---: | :---: | ---: | ---: | :---: | :---: |
| `snap_box` | 0.133 | yes | 0.142 | 0.0000 | yes | yes |
| `box` | 0.144 | yes | 0.127 | 0.0000 | yes | yes |
| `enclosure` | 0.140 | yes | 0.135 | 0.0000 | yes | yes |
| `tube` | 0.377 | yes | 0.405 | 0.0000 | yes | yes |
| `wall_hook` | 0.453 | yes | 0.458 | 0.0000 | yes | yes |
| `cable_clip` | 0.393 | yes | 0.334 | 0.0000 | yes | yes |
| `drawer_divider` | 0.324 | yes | 0.332 | 0.0000 | yes | yes |

**Verdict: PASS** -- every family renders watertight at its declared envelope, deterministically, with no model call, under the 5s gate (all families under 1s).

