# Stage 6 — Model bake-off (Qwen vs gemma): how to run the live comparison

The Stage 6 model swap asks whether `qwen2.5-coder:1.5b` should replace `gemma4:e4b` as the
default local model. The decision is **evidence-driven**: run the Phase-1 benchmark with each
model and compare them on the spec's three quality axes plus completion and speed. The harness
(`kimcad bakeoff`) is built and tested; the live run needs a box with Ollama and both models
pulled — that's this hand-off.

## What it measures

For each backend it runs the 10 Appendix-B prompts (`bench/prompts.yaml`) end to end and grades
each case on:

- **completed** — the pipeline ran through the Printability Gate (the coarse done-gate).
- **matches-request** — the planned `object_type` is the kind of thing the prompt asked for.
- **correct-dimensions** — the built part matches its dimensional plan (the gate's per-axis
  check) and fits the requested envelope.
- **slices-clean** — the part sliced to a real, motion-bearing G-code toolpath (only graded
  when slicing is on — the default for a bake-off).

The headline comparison metric is the **3-axis graded rate** (`graded_passed / total`), not bare
completion — a model that finishes but builds the wrong size or unsliceable geometry shouldn't win.

## Prerequisites (on the target box)

1. Ollama running (`ollama serve`).
2. Both models pulled:
   - `ollama pull gemma4:e4b` (the incumbent default; usually already present)
   - `ollama pull qwen2.5-coder:1.5b` (the challenger)
3. The bundled OpenSCAD + OrcaSlicer (already fetched into `tools/` by `scripts/fetch_tools.py`).

Confirm what's installed with `kimcad models` (the hardware/availability advisor).

## Run it

```
kimcad bakeoff
```

Defaults to `--backends local_qwen,local` (qwen vs gemma) and **slices every part** (real
OrcaSlicer) so all three axes are compared. Useful flags:

- `--backends local_qwen,local` — the config backend keys to compare (≥2). Both are defined
  under `llm.backends` in `config/default.yaml`; they share the one Ollama and differ only in
  `model_name`.
- `--no-slice` — skip slicing for a faster quality-only pass (drops the slices-clean axis).
- `--printer` / `--material` — override the default P2S / PLA.
- `--out output/bakeoff` — where per-case artifacts and the summary land.

**Runtime warning:** on the CPU-only dev box each prompt is minutes of model time, and slicing
adds OrcaSlicer time per case, so a full 2-model × 10-case sliced bake-off is tens of minutes to
an hour-plus. Run it on the better test box when one is available, or use `--no-slice` for a
faster first read. The result table is written to `output/bakeoff/bakeoff.txt` before it prints,
so a console hiccup never discards the run.

## Reading the result

The output is a side-by-side table plus a recommendation, e.g.:

```
Bake-off: 2 model(s), 10 case(s) each
  backend        model                  completed graded  match   dims   slice  mean_s
  local (def)    gemma4:e4b             10/10     8/10    9/10    8/10   7/10    142.0
  local_qwen     qwen2.5-coder:1.5b     10/10     9/10    10/10   9/10   8/10     61.0
Recommendation: SWITCH default to local_qwen -- ... (3-axis graded rate 9/10 vs 8/10) ...
(Flipping the configured default model is Scott's call, not the harness's.)
```

The recommendation rule (in `compare_runs`): the challenger earns the swap only if it **beats the
incumbent on the 3-axis graded rate**, or **ties the graded rate but is faster**. Otherwise the
recommendation is to keep the incumbent — a challenger must earn the switch.

## Making the switch (human step)

The harness **only recommends**; it never edits config — flipping the default model is Scott's
call, like a merge or a tag. If the bake-off says switch and Scott agrees, set the default by one
of:

- per-machine: add `llm: { active: local_qwen }` to `config/local.yaml` (gitignored), or
- shipped default: change `llm.active` to `local_qwen` in `config/default.yaml`.

Either way, **keep `gemma4:e4b` defined** as the non-China alternative and the vision fallback —
`kimcad models` surfaces it, and it remains selectable via `--backend local`.
