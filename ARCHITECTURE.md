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
  → harden (Manifold3D)              # round-trip into a guaranteed 2-manifold; the
                                     #   hardened mesh is what is exported and sliced
  → [confirm + slice?]               # OrcaSlicer → G-code, only on explicit confirmation,
                                     #   then proven (the 3MF must carry a real toolpath)
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

**Gated export (Stage 1, wired).** The slicer is now connected through the normal flow,
behind that confirmation: the CLI `--slice` flag sets `confirm_print`, and the web UI
slices on a separate confirmed `POST /api/slice/<id>`. Profile *names* in the config
resolve to the shipped on-disk profile JSONs (`resolve_slice_settings`), and a slice is
not trusted until it is **proven** — the exported 3MF is opened and must carry a real,
motion-bearing toolpath (`prove_gcode_3mf`), from which the print estimate (time, layers,
filament) is also parsed. All three of Kim's printers (Bambu P2S, Bambu A1, Elegoo
Neptune 4 Max) are wired and proven; a printer configured *without* a process profile is
refused cleanly with the validated mesh still exported as the download fallback.

## Module map

| Module | Responsibility |
|---|---|
| `ir.py` | The Design-Plan IR (Pydantic v2): `DesignPlan`, `Feature`, `Tolerances`. Validates LLM JSON before any geometry is written; salvages almost-valid JSON (`normalize_plan_dict`); decides the one-question clarification policy (`first_clarification`). |
| `llm_provider.py` | All LLM communication, over the OpenAI SDK as the universal client (local Ollama / LM Studio, DeepSeek, any OpenAI-compatible endpoint). Two jobs: `generate_design_plan` and `generate_openscad`. Builds the constraints block and library manifest injected into the prompts. Retries connection/timeout errors so a flaky local server doesn't fail a case. The client is injectable for offline tests. |
| `openscad_runner.py` | Sanitize-and-render. **Trust boundary:** generated OpenSCAD is untrusted, so before it reaches the binary it is checked — `import()`/`surface()` file I/O, `minkowski()` (a CPU/RAM DoS at high `$fn`), and any `use`/`include` reaching outside the approved `library/` path are **blocked** (the orchestrator re-prompts) rather than silently stripped. Also deterministically repairs two common model slips: injecting a missing library `use` line, and appending a dropped trailing `;`. Then it shells out (`openscad -o part.3mf part.scad`) in an isolated temp dir with a timeout and an output-size guard, falling back to STL if the binary lacks `lib3mf`. |
| `validation.py` | Loads a rendered mesh (flattening a multi-part scene), checks watertightness, attempts conservative repairs (fill holes, fix normals/winding/inversion), and reports geometry stats — volume, bounding box, body count. The bounding box here feeds the gate's dimensional assertion. |
| `printability.py` | The **Printability Gate**: pass / warn / fail with reasons. Phase-1 checks: dimensional assertion (rendered bbox vs the plan envelope, flat 0.5 mm tolerance, no relative term), build-volume fit, declared wall thickness vs the material/nozzle minimum, and disconnected-shell detection. A non-watertight mesh is a hard fail. Single source of truth for the dimensional tolerance (`dim_tolerance`), shared with the retry feedback and the web UI. |
| `orientation.py` | Auto-orientation: compute stable resting poses via the convex hull, rotate the part so the most probable resting face sits at Z = 0, and drop it to the bed. The chosen pose and its stability are surfaced in the report. |
| `hardening.py` | Pre-slice mesh hardening: round-trips the oriented mesh through **Manifold3D** into a guaranteed 2-manifold before it is exported and sliced (watertight is necessary but not sufficient — a watertight mesh can still carry non-manifold edges a slicer mis-handles). Best-effort and optional at runtime: if Manifold3D is absent or rejects the mesh, the already-validated mesh is passed through unchanged with a note. Never raises. |
| `slicer.py` | OrcaSlicer CLI integration: turns a validated mesh into a sliced, G-code-bearing 3MF. Resolves config profile *names* to the shipped on-disk profile JSONs (`resolve_slice_settings`, fail-loud on a missing/ambiguous name), runs OrcaSlicer as an argv list (no shell), and **proves** the result — the 3MF must carry a real motion-bearing toolpath (`prove_gcode_3mf`), which also yields the print estimate. Never called without confirmation (enforced upstream in the pipeline). |
| `pipeline.py` | The orchestrator described above: wires every stage, owns the render/gate retry loop, builds the `PrintReport`, and enforces the confirm-before-slice rule. |
| `printer_connector.py` | The send-to-printer **abstraction**: the `PrinterConnector` `Protocol` (capabilities / status / send / job-status), the frozen `PrinterCapabilities` / `PrinterStatus` / `PrintJob` models, the `ConnectorError` family, and the shared `ensure_sendable()` gate — it sends only when `confirm is True` (not merely truthy) **and** the file proves out as a real motion-bearing slice, otherwise nothing is sent. Ships a thread-safe in-memory `LoopbackConnector` (the `mock` connector) so the whole path is testable with no hardware. |
| `octoprint_connector.py` | A real OctoPrint REST connector over stdlib `urllib` (`X-Api-Key` header). The API key comes from the environment only — never stored in config, never logged. A reachable-but-rejected printer (401/403) raises a distinct `AuthError` rather than masquerading as offline; single-plate G-code is extracted with a hard size cap. |
| `mock_printer.py` | A runnable mock OctoPrint server (stdlib `http.server`) — version / printerprofiles / printer / files / job endpoints with API-key auth — so the OctoPrint connector is exercised end-to-end offline. `python -m kimcad.mock_printer`. |
| `capability.py` | Capability reconciliation: `reconcile(printer, caps)` auto-fills a **blank** profile field from the printer's reported build volume / nozzle / materials and flags any config-vs-printer mismatch (config stays authoritative; the disagreement is surfaced with the actual numbers, never silently overridden). |
| `connectors.py` | The connector **factory**: `build_connector(config, name)` resolves a configured connection (`mock` / `octoprint`) and reads any API key from its env var, with clear errors for an unknown name, unknown type, or missing base-url / key (it names the missing env var, never its value). |
| `mcp_server.py` | The printer **MCP server** — a dependency-free MCP server (newline-delimited JSON-RPC 2.0 over stdio) exposing `list_connectors` / `printer_status` / `printer_capabilities` / `send_print` so an agent can drive the printer. The protocol is a pure `handle()` method (unit-tested with no subprocess); `send_print` passes the confirm value straight through to the `confirm is True` gate without coercion, so a truthy-but-not-`True` value cannot send. `python -m kimcad.mcp_server`. |
| `benchmark.py` | The Phase-1 done-gate harness. Runs a fixed set of plain-English prompts end to end and scores the batch against a pass-rate threshold. Data-driven (prompts and thresholds from `bench/*.yaml`) and decoupled from execution (a `run_one` callable) so the scoring is unit-testable without an LLM or binaries. Persists per-case artifacts (plan, report, outcome) for offline diagnosis. |
| `cli.py` | The `kimcad` command — `design` (the default verb for a bare prompt), `bench`, and `web`. `design --slice` is the explicit slice confirmation; `design --send <connector>` additionally sends the proven G-code through a connector behind the same confirmation gate (a gate-failed part is never sent; an offline printer is reported and the file is left on disk). Wires already-tested pieces together; turns foreseeable setup problems (bad config, missing key, missing prompt file) into a plain-English message and a non-zero exit rather than a traceback. |
| `webapp.py` | The local web layer (see below). |

`config.py` loads `config/default.yaml` overlaid with an optional, gitignored
`config/local.yaml`, exposing typed `Printer` / `Material` / `LLMBackend` / `Connector`
accessors. A `Printer`'s build volume and nozzle may be left blank, to be auto-filled by
capability reconciliation against a connected printer.

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
serves a fixed sample part with no model call. Once a part passes the gate, the user
picks a printer + material and, after an explicit confirmation, `POST /api/slice/<id>`
slices the already-validated mesh (idempotent and serialized, so a re-confirm doesn't
re-run the model or the slicer) and `GET /api/gcode/<id>` downloads the proven 3MF;
`GET /api/options` feeds the printer/material pickers. After a successful slice the page
can also **send** the job to a printer connection: `GET /api/connectors` lists the
configured connections and `POST /api/send/<id>` sends behind an explicit confirm step,
returning the job + printer status. A send failure (offline/unreachable printer) is a
soft result, not an error — the download stays as the fallback, and the validated model
itself is always downloadable too.

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
