# Third-party licenses & attribution

KimCad (the engine inside **TinkerQuarry**) is licensed **GPL-2.0-only** — see [LICENSE](LICENSE).
This file documents the third-party components it ships with, invokes, or depends on, and why the
combined work is GPL-2.0-compatible.

> **Why GPL-2.0:** TinkerQuarry (Option B) absorbs the **OpenSCAD-Studio** front-end, which is
> **GPL-2.0-only**. A combined work containing GPL-2.0-only code must itself be GPL-2.0. KimCad's
> own code was therefore relicensed Apache-2.0 → GPL-2.0. See
> [`STRATEGY-RECON.md`](../STRATEGY-RECON.md) for the full analysis. *(Not legal advice; get counsel
> sign-off before a public 1.0.)*

## 1. KimCad's own code & templates

GPL-2.0-only. Includes the Python engine (`src/kimcad/`), the SCAD template families
(`library/*.scad` — KimCad's own work, not third-party), and the built SPA (`src/kimcad/web/`,
reskinned to TinkerQuarry from the absorbed Studio front-end).

## 2. Absorbed front-end

| Component | License | Notes |
|---|---|---|
| OpenSCAD-Studio front-end (React/TS, reskinned) | **GPL-2.0-only** | the source of the GPL-2.0 obligation on the combined work; not relicensed (cannot be) |

## 3. External engines — invoked as separate subprocesses / user-installed tools

These are **not** linked into KimCad and **not** redistributed in this repository; the user installs
them (via the toolchain step) and KimCad calls them as separate processes. They keep their own
licenses.

| Engine | License | How used |
|---|---|---|
| **OpenSCAD** | GPL-2.0-**or-later** | geometry kernel: KimCad shells out to render `.scad` → mesh |
| **OrcaSlicer** | **AGPL-3.0** | slicer: KimCad shells out to produce G-code. Invoked as a separate program (mere aggregation / use); its AGPL terms govern *OrcaSlicer*, not KimCad's code. Not redistributed here. |
| Ollama + models (qwen2.5:7b / qwen2.5vl:3b) | Ollama: MIT · models: Apache-2.0 (Qwen) | local AI, separate process at `:11434` |

## 4. Bundled SCAD libraries (planned vendoring — all GPLv2-compatible)

Per [STRATEGY-RECON](../STRATEGY-RECON.md), the permissive SCAD stack vendored into the approved
`library/` path. All are GPLv2-compatible (✅ redistributable in a GPL-2.0 product):

| Library | License |
|---|---|
| BOSL2 | BSD-2-Clause |
| Round-Anything | MIT |
| threads.scad | CC0-1.0 |
| YAPP_Box | MIT |
| Catch'n'Hole | MIT |
| gridfinity-rebuilt | MIT |
| MCAD | LGPL-2.1 |

**Not bundled** (GPLv3/LGPLv3, incompatible with GPL-2.0): NopSCADlib (GPL-3.0+), dotSCAD
(LGPL-3.0) — supported only via an optional, user-installed, arms-length path.

## 5. Python runtime dependencies

Installed separately via `pip` (declared in `pyproject.toml`); **not redistributed in this
repository**, so this is aggregation / mere use rather than a combined-work distribution.

| Package | License |
|---|---|
| pydantic, pyyaml, trimesh | MIT |
| numpy, scipy, networkx, lxml | BSD-3-Clause |
| manifold3d | Apache-2.0 \* |
| openai (client) | Apache-2.0 \* |

\* Apache-2.0 is not GPLv2-*compatible* for *combining into one distributed work*, but these are
installed by the user as separate packages and used at arm's length (imported at runtime, not
vendored/redistributed here) — aggregation, which GPL-2.0 permits. If KimCad ever vendors them into
its own distribution, revisit this.

## 6. Front-end dependencies

The SPA (`frontend/`) builds against React, Three.js, and related libraries — predominantly **MIT**
— installed via `npm` (`package.json`), not redistributed as source here.

---

Corrections welcome — open an issue if any license here is inaccurate or out of date.
