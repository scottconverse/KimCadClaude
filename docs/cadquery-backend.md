# CadQuery — KimCad's parallel geometry backend (Stage 8)

KimCad's primary geometry backend is OpenSCAD (the template engine emits it, and the LLM
codegen path targets it). **CadQuery is a parallel backend** that runs alongside it for two
reasons:

1. **A pass-rate lever.** Different generators fail differently. When the OpenSCAD path can't
   produce a part that both renders and passes the printability gate, KimCad falls back to
   generating the part in CadQuery. The union of two independent generators clears more prompts
   than either alone.
2. **Editable CAD export.** CadQuery's OCCT kernel exports **STEP** (BREP) — precision,
   editable CAD geometry that OpenSCAD cannot produce. A CadQuery-built part offers a
   `.STEP` download you can open in any CAD program to keep modeling.

CadQuery is **optional and gracefully absent**: if no suitable interpreter is found, the
backend simply stays off and OpenSCAD continues to work exactly as before — the same posture
as the optional PrintProof3D engine.

## Why it runs out of process

**Security isolation.** Generated CadQuery code is untrusted model output; running it in a
separate interpreter with restricted builtins (on top of the static sanitizer) keeps it at
arm's length from the app — exactly how OpenSCAD and OrcaSlicer are already shelled out
(spec §6.4/§12). KimCad targets **Python 3.13** and CadQuery's OCCT (`OCP`) wheels run on
3.13 too, so this is no longer a version workaround — the process boundary stays because
it's the second of the two security layers.

```
main app (3.13)                              worker (own 3.13 venv + cadquery)
─────────────────                            ─────────────────────────────────
cadquery_runner.render_cadquery(code)
  ├─ sanitize_cadquery(code)   ── static block-list (layer 1)
  ├─ write script to a temp dir
  └─ subprocess: <python> cadquery_worker.py ──►  exec(script) in a restricted
        (request JSON on stdin)                    namespace (layer 2); export
        ◄── result JSON in a result file           STL (+ STEP); measure bbox
```

## Enabling it

1. Install CadQuery into a Python 3.13 environment (its OCCT wheels are large). The repo
   convention is a dedicated worker venv next to the app's:
   `py -3.13 -m venv .venv-cq313` then `.venv-cq313\Scripts\pip install cadquery`.
   (Installing `cadquery` into the app venv also works — the worker still runs it in a
   separate process — but the dedicated venv keeps the heavy OCCT install out of the app's
   dependency surface.)
2. KimCad auto-discovers it. With `binaries.cadquery_python: null` (the default in
   `config/default.yaml`), KimCad probes the repo-local `.venv-cq313` first, then
   `py -3.13/-3.12/-3.11` (Windows), then `python3.13/3.12/3.11` on `PATH`, and uses the
   first one whose `import cadquery` succeeds.

Config knobs (`config/default.yaml`, override in `config/local.yaml`):

- `binaries.cadquery_python`:
  - `null` (default) → auto-discover.
  - `false` or `""` → force the backend **off** even if an interpreter exists.
  - `"<path-to-python.exe>"` → use that exact interpreter (must have cadquery); no
    auto-discovery fall-through.
- `limits.cadquery_timeout_s` (default `120`) → wall-clock limit for one worker render.

When no interpreter is found, the fallback is skipped and only OpenSCAD runs — no error, no
behavior change.

## Security — executing untrusted generated Python

The generated CadQuery is **untrusted LLM output**, and CadQuery scripts are Python. KimCad
runs locally on the user's own machine — the same trust model as executing generated OpenSCAD —
but Python is more powerful, so the script is constrained by two layers with an honest division
of what each guarantees:

1. **Static sanitizer (the primary layer)** — `cadquery_runner.sanitize_cadquery` parses the
   script with `ast` and **blocks** (the orchestrator re-prompts, nothing is stripped):
   - any import except `cadquery`/`math`;
   - banned names/attributes (`os`, `open`, `eval`, `system`, …);
   - **every `__dunder__`** name, attribute, *and* string-subscript key (`x["__globals__"]`) —
     the path nearly every restricted-exec escape uses;
   - frame/function introspection attributes (`gi_frame`, `f_builtins`, `func_globals`, …) and
     `str.format` field pivots.
2. **Worker runtime (the secondary layer)** — the script runs with a **restricted
   `__builtins__`** (no `open`/`eval`/`exec`/`compile`/`input`; an `__import__` that returns the
   geometry-only cadquery facade for `import cadquery`, the real `math` for `import math`, and
   **raises `ImportError` for any other import**) against a **geometry-only facade** — every
   *top-level* cadquery submodule (`exporters`, `importers`, `occ_impl`, …) is stripped from the
   facade, so there's no module object in scope to pivot through to `os`. The script does **no I/O
   at all**: it only assigns a `result` object; the worker performs every export, and writes its
   result to a dedicated file (never stdout) so a native fd-1 write can't corrupt the contract.
   The worker subprocess also runs in the **isolated render directory** with a **secret-scrubbed
   environment** (the LLM/printer API keys are withheld), so a hypothetical escape can't read a
   key from the env or write outside the render dir's tree. The render has a timeout and an
   output-size guard (covering both the STL and the STEP).

What the worker layer can **not** independently do, by CPython design: a cadquery function still
carries its real `__builtins__` in `__globals__`, reachable via a dunder/introspection attribute
— which the **static sanitizer** blocks. So that escape class is closed by layer 1, not layer 2.
There are therefore two regression backstops: a `render_cadquery`-level escape-class test suite
(so a sanitizer regression fails loudly through the real entry point, not just a unit branch), and
a **release gate** (`KIMCAD_RELEASE=1`) that hard-fails if the worker-sandbox live tests couldn't
run. The durable, fuller answer — **OS-level process confinement** (no network, a restricted
token / job object) — is a tracked **Stage 11** hardening (it lands with the installer/bundling
work); it is **not yet implemented**. The env-scrub + isolated-cwd above are the in-tree
mitigations until then.

## The script contract (what the codegen prompt teaches)

`src/kimcad/prompts/system_cadquery.md` instructs the model to:

- assign the finished solid to **`result`** (the worker exports it);
- use the pre-imported **`cq`** — write no imports (only `math` is allowed);
- do **no** file I/O — the worker exports;
- hoist dimensions to named `# mm` variables; build one connected, watertight solid; match the
  plan's `bounding_box_mm` on every axis; respect the printer constraints.

## STEP export

A CadQuery part also writes a `.step` (BREP) alongside its mesh. It's surfaced as a
`step_url` on the design response and downloaded via `GET /api/step/<id>`. The STEP is the
**as-designed** geometry — print orientation is applied only to the printable mesh, not to the
STEP you open in CAD. (A *saved/reopened* design persists only the mesh; its STEP is available
on the fresh design, or after a re-render.)

## Proving it works

- **Deterministic engine bench:** `kimcad.cadquery_bench` renders a fixed spread of scripts
  (box, through-hole, cylinder, filleted plate, boolean L-bracket) through the real worker and
  checks each is watertight at its declared envelope — no model. See
  `docs/benchmarks/stage-8-cadquery-backend.md`.
- **Pipeline integration:** `tests/test_pipeline_backends.py` covers the mutual fallback,
  including a live test that drives the real worker as the fallback.
