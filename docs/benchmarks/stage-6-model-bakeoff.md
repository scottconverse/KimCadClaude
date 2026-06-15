# Stage 6 — Model bake-off (Qwen vs gemma): the verdict + how to reproduce it

> **⚠ SUPERSEDED for the default-model choice (2026-06-15).** This Stage 6 verdict was specifically about `qwen2.5-coder:1.5b` — a *code-completion* model that can't emit a valid `DesignPlan` (0/10). A later head-to-head ([`docs/MODEL-GUIDE.md`](../MODEL-GUIDE.md)) evaluated the *instruct* model `qwen2.5:7b` with the grammar-`format` provider fix, and it now plans 4/4 and is **the default chat model.** `gemma4:e4b` remains a defined, vision-capable alternative. The reproduction harness below is still valid; only the "keep gemma4:e4b as default" conclusion is replaced.

## Verdict (settled 2026-06-02)

The Stage 6 model swap asked whether `qwen2.5-coder:1.5b` should replace `gemma4:e4b` as the default
local model. It was run live on the target box, and the answer is **no — keep `gemma4:e4b`.**

```
Bake-off: 2 model(s), 10 case(s) each
  backend          model                  completed  graded  match  dims  slice  mean_s
  local_qwen       qwen2.5-coder:1.5b          0/10    0/10    n/a   n/a    n/a     n/a
  local (default)  gemma4:e4b                  8/10    4/10    9/9   5/9    8/9   595.7
  note: local_qwen completed 0/10 cases -- no axes could be graded
Recommendation: KEEP default local -- the current default local (gemma4:e4b) is already the best.
```

`qwen2.5-coder:1.5b` scored **0/10**: it fails the pipeline's first step (the design plan), returning
the JSON *schema* echoed back instead of a plan instance — confirmed not a config artifact (it fails
identically with JSON mode forced). It's a code-completion model, the wrong tool for the
natural-language → structured-plan step, so its coding ability never gets exercised. A *larger* qwen
isn't the answer either: a 3B/7B is bigger than gemma's ~4B-effective, so it would be slower on this
CPU box, defeating the "faster small default" premise. **`gemma4:e4b` stays the default.** `local_qwen`
remains defined in `config/default.yaml` as a selectable `--backend` so the comparison can be re-run.

(The result above is the live run; `output/bakeoff/bakeoff.txt` is regenerated each run and is gitignored.)

## What the bake-off measures

For each backend it runs the 10 Appendix-B prompts (`bench/prompts.yaml`) end to end and grades each
case on completion plus the spec's three quality axes:

- **completed** — the pipeline ran through the Printability Gate (the coarse done-gate).
- **matches-request** — the planned `object_type` is the kind of thing the prompt asked for.
- **correct-dimensions** — the built part matches its dimensional plan and fits the requested envelope.
- **slices-clean** — the part sliced to a real, motion-bearing G-code toolpath (only graded with `--slice`).

The headline comparison metric is the **3-axis graded rate** (`graded_passed / total`), not bare
completion. An axis with nothing assessed shows `n/a`, and a backend that completed zero cases shows
`n/a` for the axes and the mean (it never timed any real work) plus an explicit zero-completion note.

## How to reproduce the bake-off

Both models are pulled on the target box, so it can be re-run there directly.

### Prerequisites
1. Ollama running (`ollama serve`).
2. Both models pulled: `ollama pull gemma4:e4b` and `ollama pull qwen2.5-coder:1.5b`.
3. The bundled OpenSCAD + OrcaSlicer (already fetched into `tools/` by `scripts/fetch_tools.py`).

Confirm what's installed with `kimcad models` (the hardware/availability advisor).

### Run it

```
kimcad bakeoff
```

Defaults to `--backends local_qwen,local` and **slices every part** (real OrcaSlicer) so all three axes
are compared. Useful flags:

- `--backends local_qwen,local` — the config backend keys to compare (≥2); each backend's `model_name`
  is what runs.
- `--no-slice` — skip slicing for a faster quality-only pass (drops the slices-clean axis).
- `--printer` / `--material` — override the default P2S / PLA.
- `--out output/bakeoff` — where per-case artifacts and the summary land.

**Runtime:** on the CPU-only box, gemma is ~10 min/prompt and slicing adds OrcaSlicer time per case, so a
full 2-model × 10-case sliced run is tens of minutes to an hour-plus. The result is written to
`output/bakeoff/bakeoff.txt` before it prints, so a console hiccup never discards the run.

## The recommendation rule

`compare_runs` recommends switching the default only if the challenger **beats the current default on
the 3-axis graded rate**, or **ties it but is faster**; otherwise it recommends keeping the default — a
challenger must earn the swap. The harness **only recommends** — it never edits config.

## Making a switch (human step)

If a future bake-off ever recommends a switch and Scott agrees, set the default by one of:

- per-machine: add `llm: { active: <key> }` to `config/local.yaml` (gitignored), or
- shipped default: change `llm.active` in `config/default.yaml`.

Either way, **keep `gemma4:e4b` defined** as the non-China alternative (and a vision-capable model for
the future Stage 9 image on-ramp) — `kimcad models` surfaces it, and it stays selectable via `--backend local`.
