# KimCad — Handoff (2026-05-31, end of session)

## ⛔ READ FIRST — the project is PAUSED on purpose

**Do not resume building until BOTH of these are true:**
1. **Scott's canonical KimCad 3.0 spec is loaded** and treated as the source of truth. It
   **supersedes the old v2.1 spec** and may re-plan the stages around the integration
   architecture in §4 below.
2. **The new restrictive pipeline skill is installed, enabled, and locked in.** It governs
   this project from here on (it enforces the process in §6). The next run starts in a
   **fresh session** under that skill.

Everything below is the accurate state of the code + the strategic decisions, so the fresh
session resumes cold without losing anything. **This doc is the source of truth — do not
rebuild from memory or from a vacuum** (see §7: I have lost context Scott gave me before).

---

## 1. Where the code actually is

- **Repo:** `github.com/scottconverse/KimCadClaude` (private). GitHub is the only git remote.
- **`main`:** tags **`stage-0`**, **`stage-1`**, **`stage-2`** — all done, audited to
  **0/0/0/0/0** with `audit-team`, merged + tagged.
- **Stage 3 IN PROGRESS** on branch **`stage-3-printer-coverage`** — **pushed, NOT merged,
  NOT tagged** (no stage-gate `audit-team` has been run yet).
- **Tests: 361 passing, `ruff` clean.** Local CI via the pre-push hook
  (`.githooks/pre-push` → `scripts/ci.sh` = ruff + pytest); enable per clone with
  `git config core.hooksPath .githooks`. Fast inner loop: `pytest -m "not live"` skips the
  OrcaSlicer-invoking tests. CI warns (and hard-fails under `KIMCAD_RELEASE=1`) if the
  bundled OrcaSlicer is absent, so a green run without it can't be mistaken for a real one.
- **Project root:** `C:\Users\scott\dev\kimcad` — deliberately **OUTSIDE OneDrive** (venv +
  slicer binaries trigger OneDrive sync storms; source lives on GitHub).

### Stage 3 slices done (each independently audit-lited to 0/0/0/0/0)
1. **Moonraker (Klipper) connector** — `moonraker_connector.py` + `mock_moonraker.py`. Covers
   Creality-Klipper / Voron / RatRig / Mainsail / Fluidd. Also promoted shared
   `extract_single_plate_gcode` + `read_error_body` into `printer_connector.py`, added
   `JobState.paused`, and made `connector_is_simulated` derive from each connector class's
   `drives_hardware` (a `_CONNECTOR_CLASSES` registry — single source of truth).
2. **Per-printer per-material filament profiles** — every Kim printer × material verified to
   resolve, be machine-compatible, AND **live-slice to proven G-code** (P2S/A1: pla/petg/tpu/abs;
   Elegoo: pla/petg/abs). **The Elegoo Neptune 4 Max has NO shipped TPU profile**, so TPU is
   honestly "not available" on it — and the **cross-vendor `_GENERIC_FILAMENT` fallback was
   removed** (it silently mis-resolved Elegoo+TPU to a Bambu profile). `/api/options` now reports
   each printer's available + generic materials so the UI offers only what a printer can print.
3. **Ready/not-ready connection-status UI** — `GET /api/connector-status/<name>` + a badge
   (●Ready / ◐Online-but-busy / ○Offline / ○Needs-setup / ●Simulation). Never 5xx; never leaks
   the API key.
4. **PrusaLink (Prusa) connector** — `prusalink_connector.py` + `mock_prusalink.py`. Built from
   the researched PrusaLink API (X-Api-Key auth, the IDLE/PRINTING/PAUSED/FINISHED/STOPPED/
   ATTENTION state set, `PUT /api/v1/files/<storage>/<name>` with `Print-After-Upload`).
   Configurable `storage` (usb default). An unrecognized printer state now reports `error`, not
   "ready" (also applied to Moonraker).

**Connectors today:** OctoPrint (Stage 2) + Moonraker + PrusaLink + the in-memory
`LoopbackConnector` mock + **KimCad's own MCP server** (`mcp_server.py`, exposes send-to-printer
as agent tools). The `PrinterConnector` Protocol is the seam everything plugs into.

**Stage 3 NOT done:** no `audit-team` stage-gate, not merged, not tagged. Bambu-native is the one
brand gap (see §4). Whether to finish/gate Stage 3 as-is or re-plan it is a **3.0-spec decision.**

---

## 2. What's built (Stages 0–2, all at 0/0/0/0/0)

Deterministic pipeline, end to end:
```
prompt → Design-Plan JSON IR (Pydantic v2) → [clarify?] → LLM OpenSCAD → sandboxed render
→ Trimesh validation → Printability Gate → auto-orient → harden (Manifold3D)
→ [confirm] slice (OrcaSlicer) → prove G-code → [confirm] send via a PrinterConnector → report
```
- **Gated G-code export (Stage 1):** profile name→on-disk-path resolution; slice behind explicit
  confirmation; `prove_gcode_3mf` (the 3MF must carry a real motion-bearing toolpath; estimate
  parsed); Manifold3D pre-slice hardening; download fallback.
- **Send-to-printer + MCP (Stage 2):** the `PrinterConnector` abstraction, OctoPrint connector +
  mock server, capability reconciliation, CLI `--send`, web send, and the MCP server. **Two
  load-bearing safety properties** (re-verified under live MCP exercise): per-send `confirm is
  True` (identity, not truthy) on every path; nothing sent that isn't a proven slice. A
  gate-FAILED part is never sent even with `--proceed-anyway`. API keys env-only, never logged.
- **All three of Kim's printers slice live** (Bambu P2S, Bambu A1, Elegoo Neptune 4 Max). Elegoo
  naming quirk: process profiles are `Neptune4Max` (no spaces, under `process/EN4SERIES/`);
  machine profile is `Neptune 4 Max` (with spaces).
- **Web UI** (`kimcad web`, stdlib server): describe → plan → printability verdict → dims → 3D
  preview (three.js vendored) → confirm → slice → confirm → send / download.

---

## 3. Environment / pins

- **Model:** `gemma4:e4b` via local Ollama (`localhost:11434`, OpenAI-compatible). ~9 min/prompt
  on the 32 GB / **AMD 780M iGPU, CPU-only** target — stable. **NOT `gemma3:12b`** (OOM-crashed).
  Local-first; cloud (DeepSeek/OpenRouter) is opt-in only via `config/local.yaml`. **No usable
  CUDA GPU on this box** — this constrains §4 (image-to-3D models need CUDA).
- **OrcaSlicer v2.4.0-alpha** (pinned, checksum-verified, gitignored `tools/`). 2.3.2 segfaults on
  GPU-less CLI slicing (upstream #12906); 2.4.0-alpha is the only build that both slices here AND
  ships the P2S profile. `scripts/fetch_tools.py` fetches OpenSCAD + OrcaSlicer.
- **Deps:** `manifold3d>=3.0` (default; import optional at runtime). All connectors are stdlib —
  **zero new runtime deps in the connector layer** so far. `pip install -e ".[dev]"`.

---

## 4. OSS-integration architecture (INPUT to the 3.0 spec)

Scott gave me this candidate list **long ago in chat**; I lost it across sessions and rebuilt the
connector layer without it. Researched + **fact-corrected** this session. **Key insight: this is
ONE pipeline with a fallback at every tier — not 5 isolated yes/nos:**

```
photo/sketch OR text
  → [vision-LLM  |  TripoSG ⇄ TRELLIS]        (INPUT: CPU floor ⇄ GPU/cloud ceiling)
  → Manifold3D repair + Trimesh measure        (seed the DesignPlan)
  → DesignPlan (validated schema — trust boundary)
  → [CadQuery ⇄ OpenSCAD]                       (GENERATION: mutual fallbacks)
  → Printability Gate
  → [PrintProof3D oracle]                       (VALIDATION: optional independent 2nd opinion)
  → slice (OrcaSlicer)
  → [native connector | MCP-proxy]              (OUTPUT: stdlib primary ⇄ MCP fallback)
```

- **mcp-3d-printer-server (DMontgomery40) — the Bambu answer.** **License is GPL-2.0, NOT MIT**
  (the original list was wrong). Node 18+, stdio/http MCP. Speaks Bambu LAN **MQTT(8883/TLS) +
  FTPS(990)** itself, plus OctoPrint / Klipper / Prusa Connect / Creality / Duet / Repetier.
  **Bambu models: p1s/p1p/x1c/x1e/a1/a1mini/h2d — NO P2S** (Kim's reference printer is not listed;
  her A1 is). **Plan:** add an **`mcp` connector type** (an `McpProxyConnector` implementing the
  existing `PrinterConnector` Protocol by calling the server's MCP tools) → Bambu A1 via MCP, P2S
  falls back to slice-and-download until supported. Consume it as a **separate process**
  (arm's-length, like shelling out to AGPL OrcaSlicer — GPL doesn't infect); **opt-in Node only
  when an `mcp` connector is configured.** Use it ONLY as transport, not its slicing/STL ops
  (KimCad owns those). **This replaces the earlier paho-mqtt-dependency proposal.**
- **TripoSG (MIT, 1.5B) / TRELLIS.2 (MIT, 4B) — image-to-3D seed.** **Both need a CUDA GPU**
  (TripoSG ≥8GB VRAM, no CPU path); **not feasible on the 780M/CPU-only box.** So image input is
  **tiered: vision-LLM (CPU floor)** — a multimodal local model reads the photo/sketch, estimates
  dimensions, and feeds the **existing text→DesignPlan path** — **⇄ TripoSG⇄TRELLIS (GPU/cloud
  ceiling)** — mesh → Trimesh measures → seeds the plan. Same trust boundary (model output =
  untrusted data into the validated DesignPlan). **Image input ships on CPU via the vision-LLM;
  the 3D-gen tier waits for GPU/cloud.**
- **Manifold3D (Apache 2.0) — ALREADY IN** (Stage 1 `hardening.py`). Extend later for booleans
  (multi-part assembly; repair the image-gen mesh before measuring).
- **CadQuery (Apache 2.0) — the renderer fallback.** **CadQuery ⇄ OpenSCAD as mutual fallbacks:**
  the LLM emits either, run the gate, retry with the OTHER backend on failure (different
  generators fail differently → the union lifts the 8/10 done-gate). Plus STEP/editable-CAD export
  OpenSCAD can't do. A pass-rate lever, not a someday-swap.
- **Faster models — shaky premise.** Qwen2.5-Coder / DeepSeek-Coder 6.7B are BIGGER than
  gemma4:e4b → likely SLOWER on CPU. The real play unifies tiers: pick ONE small **vision-capable**
  model good at structured code → image-understanding + DesignPlan + codegen. Benchmark-driven on
  the actual box.
- **PrintProof3D** (separate Rust validation harness at
  `C:\Users\scott\Documents\antigravity\eager-archimedes\PrintProof3D`, **simulator-only**): use
  as an **optional independent validation ORACLE** — a pipeline hook right before send (present →
  re-validate the G-code/profile; absent → warn), **NOT a core dependency** (it duplicates
  validation KimCad already does; coupling a Rust binary is the cost). It's an **Antigravity
  artifact** — fine as an external test oracle, but must not become part of the head-to-head-judged
  *solo* deliverable.

**Build order if the 3.0 spec keeps these:** MCP-proxy connector (closes Bambu A1) + CadQuery⇄
OpenSCAD dual-path (lifts the done-gate) first; then the vision-LLM image floor; design the
TripoSG seam now, implement on GPU/cloud; PrintProof3D hook + Manifold3D booleans ride along.

---

## 5. Open decisions for the 3.0 spec / Scott

- **Bambu:** MCP-proxy connector (above) vs a native KimCad Bambu connector (paho-mqtt). Recommend
  MCP-proxy; verify the server actually drives the **P2S** before relying on it for Kim's main
  printer.
- **Stage 3:** finish + gate it as-is (OctoPrint/Moonraker/Prusa + per-material + status UI), or
  re-plan the remaining stages around the §4 architecture in the 3.0 spec.
- **PrintProof3D:** optional oracle (recommended) vs built-in (the competitor AI wants built-in;
  my reasoning against built-in is in the session transcript — coupling, two-sources-of-truth on a
  safety gate, simulator-only ceiling, and it muddies the solo head-to-head).
- **Image input:** vision-LLM floor now vs wait for GPU/cloud for TripoSG. Recommend building the
  vision-LLM floor (CPU-feasible) and designing the TripoSG seam.

---

## 6. The process (the new pipeline skill enforces it)

Per **slice** (each chunk where you'd normally stop and check in):
1. **Invoke the `audit-lite` skill** on the slice — NOT a prose self-review.
2. Fix **every** finding (Blocker→Nit).  3. **Re-run `audit-lite`.**  4. Fix.  5. Push.
6. Straight to the next slice — no pausing.

At **stage end:** push the final slice → run **`audit-team`** on the pushed branch → fix →
re-audit → … until **0/0/0/0/0** or a genuinely human-required blocker → **merge + tag** → only
then a full status report. **Branch per stage; the pre-push hook gates every push.**

---

## 7. Why the harness — behavioral failures to NOT repeat

- **Run the actual audit tool, every slice, no substitution.** A prior session wrote prose
  self-reviews labeled "audit-lite" and skipped the real skill; the self-review is exactly what
  the gate exists to override, because the self-review has been wrong (model size, axis swap,
  Elegoo). This session ran genuinely-independent reviewers every slice and they caught real
  defects (the MCP confirm-coercion hole, the `job_status` subclass-ordering bug, the Elegoo+TPU
  mis-resolution).
- **The handoff/memory is the source of truth — I forget things across sessions.** Scott gave me
  the §4 OSS list in chat earlier and I lost it, then rebuilt the connector layer from scratch
  without it. Read this doc + the 3.0 spec; don't reconstruct from memory.
- **Do deep, systems-level analysis — don't default to "this is too hard / defer."** When Scott
  asked me to assess the §4 candidates, my first pass analyzed each in isolation and reached for
  "defer/can't" each time. He called it out: *"your entire answer is 'this seems too hard'… you
  missed a ton of options like 'one is a fallback for the other'."* The right move is the tiered/
  fallback architecture in §4 — how the pieces COMBINE and back each other up — not isolated nos.

---

## 8. Context

KimCad is a **solo build** (no Antigravity/Codex/bridge/pipeline — that machinery is for Scott's
other engagements) and a **head-to-head test vs a competitor AI** building the same spec; Scott
judges which is better. **UX is priority #1** (Scott: 10 yrs at Apple). Real prints happen only at
Kim's house, only at the final stage (Kim is the beta tester — Bambu P2S + A1, Elegoo Neptune 4
Max). See `ROADMAP.md` (the v2.1 11-stage plan — the 3.0 spec may replace it) and `ARCHITECTURE.md`
(module map).
