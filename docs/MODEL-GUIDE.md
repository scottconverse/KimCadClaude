# KimCad model guide — which AI runs, and why

KimCad ships with two local models, both running via [Ollama](https://ollama.com) on your
own machine (CPU-only; no graphics card needed). Neither choice is folklore — each was
measured on the reference hardware, and the benchmark harness ships in the repo so every
number below stays re-checkable.

| Role | Model | Ollama tag | Size | Why this one |
|---|---|---|---|---|
| **Chat / design planning** — your words → a validated design plan, and the (opt-in) experimental geometry | Gemma 4 E4B | `gemma4:e4b` | ~9 GB | Won the Stage-6 bake-off outright (below) |
| **Vision** — reads photos and dimensioned sketches into editable seeds | Qwen 2.5 VL 3B | `qwen2.5vl:3b` | ~3 GB | The dedicated vision reader; the chat model's vision path produces empty output on this stack (measured, Stage 9) |

The setup wizard downloads both with live progress; everything afterward runs offline.

## The chat-model decision (the Stage-6 bake-off, run live on the target box)

The question was whether `qwen2.5-coder:1.5b` — much smaller, much faster — should replace
`gemma4:e4b` as the default. Measured over the 10-prompt Appendix-B benchmark, end to end:

| Backend | Completed | Plan→object match | Mean time |
|---|---|---|---|
| `gemma4:e4b` (default) | **8/10** | 9/9 | ~600 s/case |
| `qwen2.5-coder:1.5b` | **0/10** | n/a | n/a |

The small coder model fails the *first* step — it echoes the JSON schema back instead of
producing a plan instance (confirmed not a config artifact), so its coding ability never
gets exercised: it's a code-completion model, the wrong tool for natural-language →
structured-plan work. A larger Qwen wouldn't help the premise either — at 3B/7B it's bigger
than Gemma's ~4B-effective and therefore slower on the CPU target. **`gemma4:e4b` stays.**
Full write-up: [stage-6-model-bakeoff.md](benchmarks/stage-6-model-bakeoff.md).

## The vision-model decision (Stage 9)

`gemma4:e4b` advertises vision, but on this serving stack its image path spends the whole
token budget "thinking" and returns empty content — measured, not assumed. The dedicated
`qwen2.5vl:3b` reads both photos and dimensioned sketches reliably, so vision gets its own
small model. Write-up: [stage-9-vision-onramps.md](benchmarks/stage-9-vision-onramps.md).
Images are **always processed locally** and never leave the machine.

## What to expect, practically

- **Latency:** roughly one to two minutes for the AI planning step of a fresh design on the
  reference hardware (a recent CPU, 32 GB RAM); template parts then re-render from the
  sliders instantly with no model call. The first design after a cold start is the slowest
  (the model is loading).
- **There is no model menu.** KimCad ships THE measured default rather than a picker — a
  trust rule, not a limitation (an untested model choice would silently change quality).
  Power users can still point a different backend via `config/local.yaml` and `--backend`,
  and `local_qwen` stays defined so the comparison can be re-run.
- **Cloud (opt-in only):** Settings → Cloud acceleration routes *prompts* (never images) to
  a model you choose via OpenRouter, with your own key, for hard requests. Local always
  works; a wrong cloud slug falls back to local rather than failing the design.

## Re-running the measurements

```
kimcad bench --min-success-rate 0.8     # the 10-prompt done-gate against the current model
kimcad bakeoff --backends local,local_qwen   # head-to-head, 3-axis graded
```

Both write their verdicts under `output/`; the lesson from Stage 6 is institutional now:
**measure on the current model rather than trusting a stale figure.**
