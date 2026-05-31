# Architecture

KimCad turns a plain-English request into a printer-ready part by driving a
**deterministic pipeline** around a single LLM-shaped step. The model writes a
structured plan and OpenSCAD code; everything that decides whether the result is
dimensionally correct and printable is ordinary, testable code — not the model.

## The pipeline

```
prompt
  → design plan (JSON IR)            # LLM: structured intent, validated before geometry
  → [clarify?]                       # ask at most one question if the part can't be sized
  → OpenSCAD codegen                 # LLM: writes OpenSCAD, composing the module library
  → sandboxed render                 # untrusted code is sanitized, then OpenSCAD shells out
  → mesh validation                  # load mesh, check watertight, conservative repair
  → Printability Gate                # pass / warn / fail vs the chosen printer + material
  → auto-orient                      # rotate onto the most stable facet, drop to the bed
  → [confirm + slice?]               # OrcaSlicer → G-code, only on explicit confirmation
  → print report                     # plain-text (or JSON for the web UI) summary
```

`pipeline.py` owns this spine. Two LLM-shaped steps (design plan, codegen) sit inside
it; every other stage is deterministic. The renderer, the slicer, and the LLM provider
are all **injected**, so the whole orchestration — including the retry loop and the
gate escape hatch — runs offline in tests against real `trimesh` geometry, with no
binary and no network.

### Failure handling, fail-closed

Two failure classes are fed back to the model and retried inside one attempt budget
(`max_render_retries`, default 2), then the loop fails closed:

- **render / blocked-code errors** — the code produced no geometry; the error text is
  returned to the model with a request to fix it.
- **fixable gate failures** — it rendered, but the size is wrong (`dim.mismatch`),
  it doesn't fit the build volume (`volume.exceeds`), or the mesh isn't watertight
  (`mesh.not_watertight`). A per-axis target-vs-built breakdown is fed back so a part
  with two wrong axes converges in one retry rather than one axis at a time. Gate
  retries are skipped when the caller passed `--proceed-anyway`.

G-code is only ever produced after explicit printer confirmation
(`Pipeline.run(confirm_print=...)`); the slicer is otherwise never called.

**Status of the slicer (deliberate Stage-0 scope):** `slicer.py` is implemented and
unit-tested, and an end-to-end slice was proven once on a Bambu P2S profile, but it is
**not yet wired into the default CLI or web flow** — the CLI doesn't pass `confirm_print`
and the web "Send to printer" button is a stub. Connecting it (profile-name → on-disk-path
resolution, material/profile confirmation, the G-code proof step) is **Stage 1 — the gated
export loop** in `ROADMAP.md`. It is listed here so the gap is logged, not hidden.

## Module map

| Module | Responsibility |
|---|---|
| `ir.py` | The Design-Plan IR (Pydantic v2): `DesignPlan`, `Feature`, `Tolerances`. Validates LLM JSON before any geometry is written; salvages almost-valid JSON (`normalize_plan_dict`); decides the one-question clarification policy (`first_clarification`). |
| `llm_provider.py` | All LLM communication, over the OpenAI SDK as the universal client (local Ollama / LM Studio, DeepSeek, any OpenAI-compatible endpoint). Two jobs: `generate_design_plan` and `generate_openscad`. Builds the constraints block and library manifest injected into the prompts. Retries connection/timeout errors so a flaky local server doesn't fail a case. The client is injectable for offline tests. |
| `openscad_runner.py` | Sanitize-and-render. **Trust boundary:** generated OpenSCAD is untrusted, so before it reaches the binary it is checked — `import()`/`surface()` file I/O, `minkowski()` (a CPU/RAM DoS at high `$fn`), and any `use`/`include` reaching outside the approved `library/` path are **blocked** (the orchestrator re-prompts) rather than silently stripped. Also deterministically repairs two common model slips: injecting a missing library `use` line, and appending a dropped trailing `;`. Then it shells out (`openscad -o part.3mf part.scad`) in an isolated temp dir with a timeout and an output-size guard, falling back to STL if the binary lacks `lib3mf`. |
| `validation.py` | Loads a rendered mesh (flattening a multi-part scene), checks watertightness, attempts conservative repairs (fill holes, fix normals/winding/inversion), and reports geometry stats — volume, bounding box, body count. The bounding box here feeds the gate's dimensional assertion. |
| `printability.py` | The **Printability Gate**: pass / warn / fail with reasons. Phase-1 checks: dimensional assertion (rendered bbox vs the plan envelope, flat 0.5 mm tolerance, no relative term), build-volume fit, declared wall thickness vs the material/nozzle minimum, and disconnected-shell detection. A non-watertight mesh is a hard fail. Single source of truth for the dimensional tolerance (`dim_tolerance`), shared with the retry feedback and the web UI. |
| `orientation.py` | Auto-orientation: compute stable resting poses via the convex hull, rotate the part so the most probable resting face sits at Z = 0, and drop it to the bed. The chosen pose and its stability are surfaced in the report. |
| `slicer.py` | OrcaSlicer CLI integration: turns a validated mesh into a sliced, G-code-bearing 3MF. Takes explicit on-disk profile JSON paths (`SliceSettings`); mapping config profile *names* to those paths is a pending binary-verification step. Never called without confirmation (enforced upstream in the pipeline). |
| `pipeline.py` | The orchestrator described above: wires every stage, owns the render/gate retry loop, builds the `PrintReport`, and enforces the confirm-before-slice rule. |
| `benchmark.py` | The Phase-1 done-gate harness. Runs a fixed set of plain-English prompts end to end and scores the batch against a pass-rate threshold. Data-driven (prompts and thresholds from `bench/*.yaml`) and decoupled from execution (a `run_one` callable) so the scoring is unit-testable without an LLM or binaries. Persists per-case artifacts (plan, report, outcome) for offline diagnosis. |
| `cli.py` | The `kimcad` command — `design` (the default verb for a bare prompt), `bench`, and `web`. Wires already-tested pieces together; turns foreseeable setup problems (bad config, missing key, missing prompt file) into a plain-English message and a non-zero exit rather than a traceback. |
| `webapp.py` | The local web layer (see below). |

`config.py` loads `config/default.yaml` overlaid with an optional, gitignored
`config/local.yaml`, exposing typed `Printer` / `Material` / `LLMBackend` accessors.

## The OpenSCAD module library

`library/` is a set of proven, parametric OpenSCAD modules — the quality moat. The
manifest (`library/manifest.yaml`) is injected into the codegen system prompt so the
model composes from these via `use <library/NAME.scad>;` rather than reinventing
geometry, and the same manifest drives the runner's auto-`use` injection, so the
prompt and the runner can never drift on which modules exist. Each module documents an
exact bounding box, which the gate then asserts against.

Ten `.scad` files in all — five original, five added:

- **box.scad** — hollow walled container (not a solid cube).
- **bracket.scad** — L bracket with mounting holes.
- **fasteners.scad** — metric screw/nut/heat-set cut tools (M2–M8).
- **fillets.scad** — cheap rounding (2D hull/offset, never minkowski).
- **mounts.scad** — hole-grid and VESA mounting patterns.
- **hooks.scad** — `wall_hook`, `pegboard_hook`.
- **clips.scad** — `cable_clip`.
- **containers.scad** — `snap_box`, `enclosure`, `tube`.
- **holders.scad** — `spool_holder`.
- **organizers.scad** — `drawer_divider`.

## The web layer

`webapp.py` is a small, dependency-free layer over the same pipeline — no web
framework, just a stdlib `http.server`. A browser POSTs a prompt to `/api/design`; the
same `Pipeline` the CLI builds runs it, and the result (design plan, printability
verdict, target-vs-actual dimensions, and a 3D preview of the rendered mesh) returns as
JSON the page renders. The pipeline-to-payload mapping (`design_response`) is a pure
function, so the whole response shape is unit-tested offline with a fake provider and a
stub renderer. The pipeline is injected exactly as the CLI wires it, so the web layer
reuses the tested path rather than duplicating it.

The server binds to `127.0.0.1` only by default (`kimcad web`, default port 8765, set
with `--port`/`--host`). In-memory state and request size are bounded; a `--demo` mode
serves a fixed sample part with no model call. Slicing to G-code is deliberately not
triggered from the UI yet — it surfaces the validated 3MF/STL and leaves confirmed
G-code generation to a later slice.

## Local-first and the injectable seam

KimCad is **local-first**: out of the box it talks to a local runtime (Ollama or LM
Studio) running `gemma4:e4b`, so there's no API key and no network requirement. A cloud
API (DeepSeek or any OpenAI-compatible endpoint) is an opt-in fallback configured in
`config/local.yaml`.

The same seam that makes that swap trivial — the **LLM provider, renderer, and slicer
are all injected** into the pipeline — is what makes the engine testable. With a fake
provider and a stub renderer, the entire orchestration runs offline against real
`trimesh` geometry: no model, no binary, no socket. The deterministic stages
(validation, gate, orientation) are pure enough to test directly. So the parts that
decide whether a part is correct are verified without ever invoking the one
non-deterministic component.
