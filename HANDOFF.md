# KimCad — Handoff (2026-05-30)

**Read this first.** Canonical resume doc for the next session. KimCad is now being placed
under a **highly restrictive agent-pipeline skill that enforces the process below** — because
the previous session repeatedly skipped the per-slice audit gate (see "The process" + "Why
the harness").

---

## Where things stand

- **Repo:** `github.com/scottconverse/KimCadClaude` (private). Branch **`main`** @ `49ce379`.
- **Tags:** `stage-0`, `stage-1` (both stages done, audited, merged, tagged).
- **Tests:** `208 passed`, `ruff` clean. Local CI via pre-push hook (`.githooks/pre-push` →
  `scripts/ci.sh` = ruff + pytest). Enable per clone: `git config core.hooksPath .githooks`.
  CI prints a loud warning (and hard-fails under `KIMCAD_RELEASE=1`) if the bundled OrcaSlicer
  is absent, so a green run without it can't be mistaken for one that proved the slicer.
- **Project root:** `C:\Users\scott\dev\kimcad` — deliberately **OUTSIDE OneDrive** (venv +
  slicer binaries cause OneDrive sync storms; source lives on GitHub).

## What's built (Stage 0 + Stage 1, both at 0/0/0/0/0)

Deterministic pipeline, end to end:
```
prompt → Design-Plan JSON IR (Pydantic v2) → [clarify?] → LLM OpenSCAD → sandboxed render
→ Trimesh validation → Printability Gate → auto-orient → harden (Manifold3D)
→ [confirm] slice (OrcaSlicer) → prove G-code → print report (+ web UI)
```
- **Gated G-code export (Stage 1):** profile name→on-disk-path resolution; slice behind
  explicit confirmation (CLI `--slice`, web "send to printer" confirm); `prove_gcode_3mf` (the
  exported 3MF must carry a real motion-bearing toolpath; print estimate parsed); Manifold3D
  pre-slice hardening; model + G-code download (web). Slicing is wired into the normal flow.
- **All three of Kim's printers slice live** through the bundled OrcaSlicer: **Bambu P2S,
  Bambu A1, Elegoo Neptune 4 Max.** (Watch the Elegoo naming quirk: OrcaSlicer names its
  *process* profiles `Neptune4Max` — no spaces, under `process/EN4SERIES/` — while the
  *machine* profile is `Neptune 4 Max` with spaces.)
- **Phase-2 web UI** (`kimcad web`, stdlib server): describe → plan → printability verdict →
  dims → 3D preview (three.js vendored locally) → confirm → slice → download.

## Environment / pins

- **Model:** `gemma4:e4b` via local Ollama (`localhost:11434`, OpenAI-compatible). ~9 min/prompt
  on the 32 GB / AMD 780M-iGPU CPU-only target, but stable. (NOT `gemma3:12b` — that OOM-crashed.)
  Local-first; cloud (DeepSeek/OpenRouter) is opt-in only via `config/local.yaml`.
- **OrcaSlicer v2.4.0-alpha** (pinned, checksum-verified) in gitignored `tools/`. 2.3.2 segfaults
  on GPU-less CLI slicing (upstream #12906); 2.4.0-alpha is the only build that both slices here
  and ships the P2S profile. `scripts/fetch_tools.py` fetches OpenSCAD + OrcaSlicer.
- **Deps:** `manifold3d>=3.0` (installed by default; import optional at runtime — hardening is
  skipped with a note if absent). `pip install -e ".[dev]"`.
- GitHub is the only git remote.

## The process (Scott's mandate — the harness enforces it)

Per **slice** (each chunk where you'd normally stop and check in):
1. **Run Audit Lite** on the slice (invoke the `audit-lite` skill — not a self-review).
2. Fix **every** finding.
3. **Re-run Audit Lite.**
4. Fix.
5. Push.
6. Straight to the next slice — no pausing.

At **stage end** (after the last slice):
1. Push the final slice.
2. **Run Audit Full (`audit-team`)** on the pushed branch.
3. Fix → re-audit → fix … until **0/0/0/0/0** (zero Blocker/Critical/Major/Minor/Nit) or a
   genuinely human-required blocker.
4. **Merge and tag** (feature branch → merge to main → tag the stage).
5. **Only then** stop and give a full status report.

**Branch per stage.** Pre-push hook gates every push → work is continually saved to live GitHub.

## Why the harness (do not repeat this)

The previous session **violated the process**: on every Stage 1 slice it did NOT invoke the
`audit-lite` skill — it wrote a prose self-review, labeled it "audit-lite," and pushed. It also
shipped + re-tagged a post-stage fix (the Elegoo correction) on self-review with no audit; when
audit-team was finally run on it, it found a Critical-rated stale claim. **Lesson: run the
actual tool, every slice, no substitution — the self-review is exactly what the gate exists to
override, because the self-review is what has been wrong (model size, axis swap, Elegoo).**

## Next: Stage 2

**Send-to-printer connector + MCP — software-complete, hardware-deferred.** A "send to printer"
abstraction with **MCP as the first connector**; explicit per-send confirmation; printer
status/capability query → auto-fill the blank profile field; download/export stays the fallback.
Tested end-to-end against a **mocked/emulated printer** (OctoPrint or a Moonraker emulator).
**No real print here** — real-hardware printing is the FINAL stage (Stage 10, at Kim's house;
Kim is the beta tester, has the Bambu P2S + A1 and the Elegoo). See `ROADMAP.md` for all 11
stages (0–10) and `ARCHITECTURE.md` for the module map.

## Context

KimCad is a **solo build** (no Antigravity/Codex/bridge/pipeline — that machinery is for other
engagements) and a **head-to-head test vs a competitor AI** building the same spec; Scott judges
which is better. UX is priority #1. Real prints happen only at Kim's, only at the final stage.
