# Stage 8 — CadQuery backend benchmark

Two things are worth measuring for the CadQuery parallel backend: that the **engine itself**
produces valid printable geometry, and that running it alongside OpenSCAD **lifts the prompt
pass rate**. The first is a fast deterministic bench (committed, runs in CI); the second needs a
live model and is documented here as a runnable procedure.

## 1. Deterministic engine bench (no model)

`kimcad.cadquery_bench` renders a fixed spread of CadQuery scripts through the real
out-of-process worker and checks each is watertight at its declared envelope. No LLM is in the
loop, so it is byte-deterministic and proves the OCCT export round-trips to a manifold mesh at
the right size.

Cases: a plain box, a through-hole, a cylinder, a filleted plate, and a boolean-union L-bracket
(the shape the codegen prompt teaches). Each is a pure `cq` script that assigns `result` — the
same contract the LLM codegen targets.

Run it (needs a ≤3.13 interpreter with cadquery — see `docs/cadquery-backend.md`):

```python
from kimcad.cadquery_bench import run_cadquery_bench, format_report
from kimcad.cadquery_runner import find_cadquery_interpreter
print(format_report(run_cadquery_bench(find_cadquery_interpreter())))
```

Or via the test (skips cleanly when no interpreter is present):

```
pytest tests/test_cadquery_bench.py
```

Expected: **5/5 cases pass** (rendered, watertight, bbox within 0.5 mm of the declared
envelope on every axis). Measured on the dev box (AMD 780M, CPU-only) against cadquery 2.7.0 /
OCP 7.8.x on Python 3.13 (as-measured environment, **not** a version requirement): all five pass.
Note the bbox check compares *sorted* dims (orientation-invariant) within 0.5 mm, so it proves
"watertight at the right overall size," not axis assignment — the runner test
`test_render_cadquery_builds_a_box` is the tight per-axis check.

## 2. Dual-backend union (the pass-rate lever) — live procedure

The claim is that the union of OpenSCAD and CadQuery clears more prompts than either alone,
because different generators fail differently. This needs the real local model
(`gemma4:e4b` via Ollama), so it is not part of CI. To reproduce:

1. Ensure Ollama is running with `gemma4:e4b`, and a ≤3.13 + cadquery interpreter is
   discoverable.
2. Run the prompt set (`bench/prompts.yaml`) twice — once with the CadQuery backend forced off
   (`binaries.cadquery_python: false` in `config/local.yaml`) and once with it enabled
   (`null`) — and compare how many prompts reach a gate-PASS.
3. The enabled run should pass a superset: any prompt the OpenSCAD path already passes is
   untouched (the fallback only fires when OpenSCAD fails), and some prompts OpenSCAD fails on
   are rescued by CadQuery.

Because the fallback only engages on an OpenSCAD failure, enabling CadQuery can only **raise**
the pass count, never lower it — the OpenSCAD-primary result is always kept unless CadQuery
strictly beats it (`Pipeline._better_result`). The deterministic bench above guarantees the
CadQuery path is itself sound; this procedure quantifies the union lift on the day's model.

> Note (honesty): the per-prompt union lift varies with the model and the prompt set and is not
> pinned to a fixed number here — re-run it on the current model rather than trusting a stale
> figure (the lesson from the Stage-6 bake-off doc).
