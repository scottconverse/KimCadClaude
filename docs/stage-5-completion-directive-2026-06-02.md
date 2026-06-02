# Stage 5 Completion Directive - Live Sliders, Benchmarks, Gate

**Audience:** Claude working in KimCadClaude  
**Repo:** `C:\Users\scott\dev\kimcad`  
**Branch:** `stage-5-template-engine`  
**Current expected head:** `1a0af61`  
**Mode:** manual KimCad process, no bridge, no agent pipeline, no Antigravity

## Intent

Finish **Stage 5: deterministic template engine + live sliders** end to end.

Do not micro-slice this stage into tiny commit rituals. Treat the remaining work as two coherent implementation chunks plus a stage gate:

1. **Slice 4:** frontend live-slider UI.
2. **Slice 5:** deterministic-family benchmark/proof plus docs.
3. **Stage gate:** full audit-team/audit-full, fixes, re-audit, native gate, merge, tag.

Run the real audit process at meaningful boundaries: audit-lite after Slice 4, audit-lite after Slice 5, and audit-full only at the end of Stage 5. Fix every finding from Blocker through Nit before pushing each chunk. Do not stop after a self-review labeled as audit-lite.

## Source Of Truth

Before coding, read these in the repo and build from them, not from memory:

- `HANDOFF.md`
- `ROADMAP.md`
- `docs/design/KimCad-Unified-Product-Spec-v3.0.md`
- `docs/design/README.md`
- `docs/design/prototype/jsx/panels.jsx`
- `docs/design/prototype/jsx/styles.jsx`
- current frontend files under `frontend/src/`
- current backend/API contract in `src/kimcad/webapp.py`, `src/kimcad/pipeline.py`, and `src/kimcad/templates.py`

The key v3.0 UX acceptance point for this stage is: **drag a parameter slider -> deterministic local re-render in under one second, no model round trip, viewport updates, gate/report updates, stale slices cleared.**

## Non-Negotiables

- Work only in `C:\Users\scott\dev\kimcad`.
- Never use OneDrive or any Microsoft cloud-sync path.
- Do not use any bridge. There is no bridge for this work.
- Do not invoke agent-pipeline or Antigravity. KimCadClaude is a solo Claude build under the manual process.
- Stay on `stage-5-template-engine` until the stage is actually ready to merge.
- Do not merge or tag until Stage 5 passes audit-full/re-audit and the native Windows gate.
- Use native Windows for the supported gate. WSL/Linux can fail on the Windows-installed Rolldown binding; do not report that as a product failure or as a blanket green.
- Keep the accepted send-gate boundary: the web design flow does not expose expert override, and gate-failed web designs remain downloadable but not sliceable/sendable. CLI/MCP expert behavior is separate and intentionally documented.

## Slice 4 - Frontend Live Sliders

### Goal

Replace the Stage 4 read-only Parameters card with real slider controls for template-backed designs, wired to the Stage 5 backend re-render endpoint.

### Backend Contract Already Available

`POST /api/design` returns, for template-backed designs:

- `template`: family name
- `parameters`: array of `{name, label, value, min, max, step, unit, integer}`
- `mesh_url`: `/api/mesh/<id>`

`POST /api/render/<id>` accepts:

- `{ "values": { "<paramName>": <number>, ... } }`

and returns the same payload shape as `/api/design`, including:

- updated `plan`
- updated `report`
- updated `parameters`
- versioned `mesh_url` with a cache-busting query

The backend clamps/validates values, invalidates cached slices/G-code, serializes concurrent renders, and returns fresh gate status.

### Required UI Behavior

- Template-backed designs show live slider rows for every backend parameter.
- LLM-backed/non-template designs keep a clear read-only/no-sliders state.
- Each slider row shows:
  - label
  - current value in mono
  - unit when present
  - range track styled in the Workshop design language
  - accessible input name
- Dragging a slider updates local UI immediately.
- Re-render is debounced around 150 ms so dragging feels live without flooding the backend.
- While re-rendering:
  - keep the last mesh visible
  - show a quiet updating state in the parameters card
  - do not blank the viewport unless there is no model
- On re-render success:
  - replace the app-level `DesignResponse`
  - update parameter values from the server response, not from assumptions
  - update dimensions/report/findings
  - reload the viewport from the returned versioned `mesh_url`
  - clear stale slice UI state by virtue of the changed `mesh_url`
- On re-render failure:
  - keep the last successful mesh/result visible
  - show a plain error with a concrete next action
  - never leave controls stuck disabled
- `designIdFromMeshUrl` must correctly extract ids from versioned URLs such as `/api/mesh/7?v=2`.
- Browser export remains gate-aware:
  - gate-failed web designs cannot be sliced in the browser
  - model download remains available
  - no browser send UI is introduced in Stage 5

### Likely Files

- `frontend/src/api.ts`
- `frontend/src/api.test.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/Workspace.tsx`
- `frontend/src/components/RightPanel.tsx`
- `frontend/src/components/RightPanel.test.tsx`
- `frontend/src/components/ExportPanel.tsx` if slice-state clearing needs stronger wiring
- `frontend/src/styles.css`
- committed build output under `src/kimcad/web/` after frontend build

### Tests And Visual Verification

Add or update tests for:

- `DesignResponse` includes `template` and `parameters`.
- `postRender` posts to `/api/render/<id>` with `{values}`.
- `designIdFromMeshUrl` handles query strings.
- `RightPanel` renders sliders for template-backed results.
- Slider changes call the re-render callback after debounce.
- Server-returned parameter values replace local values.
- Non-template designs do not show fake sliders.
- Rerender errors are visible and recoverable.
- Export state clears when `mesh_url` changes, if current behavior is insufficient.

Run frontend tests, build, and a real rendered browser check:

- Desktop viewport.
- Mobile/narrow viewport.
- Confirm the UI has no text overlap, no clipped slider labels/values, and the viewport reloads the mesh after a slider change.
- Confirm a gate-failed rerender disables browser slicing but still allows model download.

After implementation, run the real **audit-lite skill** on Slice 4, including rendered desktop and mobile checks. Fix every finding from Blocker through Nit. Re-run audit-lite until 0/0/0/0/0. Then run the appropriate native checks, commit, and push.

## Slice 5 - Benchmark, Proof, Docs

### Goal

Prove the Stage 5 deterministic-template promise across the supported families and update the project docs so the next stage inherits a clean truth.

### Benchmark/Proof Requirements

Create a meaningful benchmark/proof for the seven built-in families:

- `snap_box`
- `box`
- `enclosure`
- `tube`
- `wall_hook`
- `cable_clip`
- `drawer_divider`

For each family, prove:

- deterministic emit uses no model call
- render succeeds against the real OpenSCAD binary when available
- actual mesh bbox matches the family expected bbox within tolerance
- re-render with changed parameters uses no model call
- re-render completes inside the stage target budget on the native Windows target where measurable
- gate/report updates reflect the current parameter values

Do not fake the performance claim. If timing is hardware/environment dependent, record the environment and make the assertion honest.

### Docs To Update

Update docs that need to know Stage 5 status and behavior:

- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `ROADMAP.md`
- `HANDOFF.md`
- relevant README/API notes if observable behavior changed
- add or update `docs/audits/stage-5/` reports as produced by the real audit process

Docs must state the send-gate boundary accurately:

- protected web/CLI design flows do not send gate-failed parts
- browser flow does not slice gate-failed parts
- CLI `--proceed-anyway` may slice for expert inspection
- MCP `send_print` is a confirmed low-level transport primitive over a proven slice, not a printability-gate-aware design flow

### Audit And Push

After Slice 5, run the real **audit-lite skill** on the complete Slice 5 benchmark/docs chunk. Fix every finding from Blocker through Nit. Re-run audit-lite until 0/0/0/0/0. Then run native checks, commit, and push.

## Stage-End Gate

After Slice 4 and Slice 5 are both pushed:

1. Run the full **audit-team/audit-full** stage audit on the entire Stage 5 branch.
2. Fix every finding from Blocker through Nit.
3. Re-run audit-full until 0/0/0/0/0.
4. Run the native Windows gate:
   - ruff over `src` and `tests`
   - full pytest, including live OrcaSlicer tests
   - frontend vitest
   - frontend build reproducibility against committed `src/kimcad/web`
   - `npm audit` with 0 vulnerabilities
5. Confirm branch is clean and pushed.
6. Merge Stage 5 to `main`.
7. Tag `stage-5` at the correct final Stage 5 artifact commit.
8. Update HANDOFF/ROADMAP if the merge/tag changes their status.
9. Only then report completion to Scott.

## What Not To Do

- Do not split the remaining work into comment-sized or one-test micro-slices.
- Do not stop after Slice 4 unless genuinely context-forced; if forced, leave exact state and next action in `HANDOFF.md`.
- Do not call a prose self-review an audit-lite.
- Do not run audit-full before the end of Stage 5.
- Do not wire browser send UI in Stage 5.
- Do not introduce a generic slider schema separate from the backend `parameters` contract.
- Do not hand-roll geometry logic in the frontend. The frontend only edits parameter values and asks the deterministic backend to render.
- Do not weaken the web gate guard.
- Do not claim native gate success from WSL/Linux.

## Done Criteria

Stage 5 is done only when:

- sliders are live and usable in the rendered app
- slider drag re-renders locally without model calls
- viewport reloads the returned versioned mesh
- gate/report/parameters update from server truth
- stale slice/G-code state cannot be reused after geometry changes
- deterministic family benchmark/proof is documented
- Slice 4 and Slice 5 audit-lite loops are closed at 0/0/0/0/0
- stage-end audit-full/re-audit is closed at 0/0/0/0/0
- native Windows gate is green
- branch is merged to `main`
- `stage-5` tag points at the final correct artifact

