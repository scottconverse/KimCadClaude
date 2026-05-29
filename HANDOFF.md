# KimCad — Handoff (reboot pause, 2026-05-29)

Workflow paused for a machine reboot. All code is committed and pushed to
`github.com/scottconverse/KimCadClaude` (private). Background processes (benchmark,
Ollama watchdog, Ollama) were stopped and will not survive the reboot — restart them
to resume (see "Resume after reboot" below).

## Where things stand

**Phase 1 (deterministic pipeline) is built and tested. The one open item is a clean
full-benchmark run scoring ≥ 8/10 — the Phase-1 done-gate.**

- 119 tests pass, lint clean (`scripts/ci.sh` = ruff + pytest; runs as a pre-push hook).
- Phase-2 web UI first slice (`kimcad web`) is in and audited (`audit-lite-web-ui-2026-05-29.md`).

### The benchmark situation (important)
The geometry/envelope work is **validated** — every failing part family has been fixed
and seen passing at exact dimensions in smoke/partial runs:
- b01 hook, b02 bracket, b03 box, b06 spacer, b07 enclosure — passed exact in earlier runs.
- b04 pegboard, b05 clip — passed exact (attempt 1) in the `output/smoke-fix.yaml` smoke
  after the design-plan envelope fix.
- b09 plate (built-in) and b10 divider (has an envelope example) are expected to pass.
- b08 spool holder — same fix pattern as b04/b05 (verified module bbox); only ever failed
  on an Ollama API timeout, not geometry.

**Every full-run failure so far was the local Ollama server, not KimCad code** — first an
API timeout, then a hard crash mid-run (b03–b10 got `APIConnectionError`). Three
mitigations are now in place:
1. `LLMBackend.timeout_s` default 1200 s (CPU generations can exceed the 10-min default).
2. Connection/timeout **retry** in `LLMProvider._complete` (6 attempts × 30 s) — bridges
   a brief server drop or restart.
3. `scripts/ollama_watchdog.py` — restarts `ollama serve` if it dies during a run.

So: a clean full run is expected to clear ≥ 8/10. It just needs to be re-run after reboot.

## Resume after reboot

1. **Start Ollama** (Ollama desktop app, or `ollama serve`). Confirm `gemma3:12b` is present:
   `curl http://localhost:11434/api/tags` (or the Ollama app's model list).
2. **(Recommended) Start the watchdog** in the background so an Ollama crash can't kill the
   run: `python scripts/ollama_watchdog.py`.
3. **Run the done-gate** (~2 h on CPU): `kimcad bench --min-success-rate 0.8`
   (console script at `.venv/Scripts/kimcad.exe`). Per-case artifacts land in
   `output/bench/<id>/` (plan.json, report.txt, part.scad, mesh).
4. **If ≥ 8/10:** update `CHANGELOG.md` with the result, run `audit-lite` on the session's
   changes, commit, and push. **If < 8/10:** read `output/bench/<failed>/{plan.json,report.txt}`
   — a failure is almost always plan-bbox vs module-bbox (design-plan envelope) or an
   Ollama hiccup (check `output/ollama-watchdog.log`).

## Environment notes
- CPU-only Ollama on this box → ~minutes per LLM call; a full 10-prompt run is ~2 h.
- Ollama has crashed mid-run twice this session (local instability) — hence the watchdog.
- Hosted GitHub Actions CI is **disabled** (out of Actions minutes until Monday). Local
  pre-push hook is the active gate. Re-enable hosted CI Monday: `gh workflow enable CI`.
- Repo binaries (`tools/`), `.venv/`, and `output/` are gitignored — regenerate with
  `scripts/fetch_tools.py` and `pip install -e ".[dev]"`.

## Open follow-ups (not blocking the done-gate)
- Vendor three.js locally for offline 3D preview (web UI currently loads it from a CDN).
- Map OrcaSlicer profile names → on-disk profile paths so `--confirm-print` slices via the UI.
- Phase 2 remainder (full UI), Phases 3–5.
