# Stage 10 stage-gate walkthrough — interface wiring audit

**Date:** 2026-06-10 · **Commit:** `d9495a8` (main) · **Scope:** the Stage 10 diff
(`253b08c..d9495a8`): Slice 10.1 DesignRegistry alias flattening (regression), Slice 10.2
SendPanel direct-print UI, Slice 10.3 Bambu-native connector (template/absence surfaces — no
hardware exists), Slice 10.4 wizard model downloads + Settings vision row.
**Method:** live browser preview driving the real SPA against two real servers — demo mode
(port 8701) for the journeys, real mode (port 8714, isolated `USERPROFILE`, real Ollama with
both models present) for the model surfaces — plus direct API probes and docs cross-checks.
**Mode:** audit (no product source modified). **No real downloads started, no printers
driven** (none exist; both models already present, verified the no-op exactly).

## Verdict

**PASS — zero findings.** Every journey worked as promised, every trust rule held, both
consoles stayed clean. One observation (below), no defects.

## Journey results

### 1. The full direct-print journey (demo) — PASS
"a 40 mm desk cable clip" → designed → **Slice & prepare file** → SendPanel appeared with
the connector picker reading exactly:
- `mock (test connection — no real printer)` — enabled
- `octoprint (not set up yet — see Settings)` — disabled
- `bambu_p2s (not set up yet — see Settings)` — disabled ← the Slice 10.3 templates,
  visible-but-unconfigured as designed
- `bambu_a1 (not set up yet — see Settings)` — disabled

**Send test job** opened the app's own confirm dialog: *"Send a test job to "mock"? No real
printer will run — this only exercises the send path."* with Keep working / Send test job.
Confirming produced the honest narration: *"Test job accepted by "mock" — the send path
works. No hardware ran."* Never narrated as a print. `/api/connectors` returns
`default: mock`, all four entries with truthful `configured`/`simulated` flags.

### 2. The gate-blocked state (demo:gatefail) — PASS
`demo:gatefail oversized cube` → experimental-generator offer → accepted → a 300 mm cube
rendered with the verdict *"Critical risk: Too big for the printer — exceeds the Bambu Lab
P2S build volume"*, the report saying *"This part didn't pass the printability check, so it
can't be sliced. You can still download the model to inspect it"*, and **no slice/send
affordance offered**. Server-side double-check: `POST /api/slice/3` → 200 soft
`{sliced: false, reason: "gate_failed", note: "…can't be sliced or sent to a printer."}` —
the refusal is the server's, not just the UI's.

### 3. Settings vision row (real mode, real Ollama) — PASS
The AI-model card shows *"Photo & sketch reader (`qwen2.5vl:3b`): downloaded."* under the
Running design model — real probe data, not a hardcoded label (screenshot taken).
`/api/model-status` returned `vision_model`/`vision_present: true` live.

### 4. Model downloads: demo refused, real no-op — PASS
- Demo server: `POST /api/model-pull` → **400**
  `{status: "not_local", error: "Demo mode doesn't download models — run KimCad without
  --demo to set up the local AI."}` — the typed refusal, exactly as the slice-10.4 audit
  fix specified. `/api/model-pull/progress` → `{running: false, models: {}}`.
- Real server (both models present): `POST /api/model-pull` → 200
  `{status: "ok", running: false, models: {}}` and progress unchanged before/after —
  **the no-op, verified twice; nothing downloaded.**
- The wizard's model step on the real server shows **Ready with no Download button**
  (truthful — nothing is missing) and the coarse sr-only live region is mounted (1 found).

### 5. Registry-flattening regression (stale-guard) — PASS
On the sliced rid 1: `HEAD /api/gcode/1` → 200 → `POST /api/render/1 {values: {width: 90…}}`
→ 200 (`/api/mesh/1?v=1`) → **`HEAD /api/gcode/1` → 404** (the old shape's G-code dropped by
the version bump) → `POST /api/slice/1` → 200 fresh slice → gcode 200 again. The three
locking protocols survived Slice 10.1's flattening in the live server.

### 6. Docs vs behavior — PASS
- README's Bambu setup note ("ship visible-but-unconfigured… listed disabled with the
  reason") — matches journey 1 exactly.
- troubleshooting's in-app-download entry (three causes incl. the typed disk/Ollama
  messages) — wording matches the implementation's messages.
- troubleshooting's bambulabs-api entry ("stays listed as 'not set up yet' and tells you
  which piece is missing") — both true: the picker carries the summary label and
  `GET /api/connector-status/bambu_p2s` returns the precise gap
  (*"The 'bambu_p2s' connection has no printer address (IP) configured."*).
- ARCHITECTURE's `model_pull.py` / `bambu_connector.py` rows — consistent with observed
  routes and behavior.

## Observation (not a finding)

The SPA picker's disabled label is the generic "not set up yet — see Settings"; the
per-piece diagnosis (missing IP vs serial vs access code vs package) lives in
`/api/connector-status/<name>` and the CLI. With four config fields, surfacing the specific
gap in the picker tooltip could save a Settings round-trip — UI-polish territory for the
audit-team's UX lane to weigh, not a wiring defect.

## Console / network

Zero console errors or warnings on either server across all journeys. No failed requests
other than the intentional 404 (post-re-render gcode — the stale-guard working) and 400s
(typed refusals).

## Tests assessment

The journeys exercised live what the suites pin: SendPanel trust rules (9 vitest), Bambu
config-template honesty (28 pytest), model-pull typed statuses + no-op + demo refusal
(14 pytest), registry protocols (8 + route pins). No uncovered workflow surfaced during
the walkthrough; the one residual hole — a real Bambu send — is hardware-gated by design
until the Stage 11 beta at Kim's.

## Cleanup

Both servers stopped; the isolated real-mode home (`%TEMP%\kimcad-walk9-home`) removed.
No product source was modified.
