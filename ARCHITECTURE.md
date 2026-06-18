# Architecture

KimCad turns a plain-English request into a printer-ready part by driving a
**deterministic pipeline** around a single LLM-shaped step. The model writes a
structured plan and, for anything off the beaten path, the OpenSCAD code; everything
that decides whether the result is dimensionally correct and printable is ordinary,
testable code — not the model.

For the common shapes the geometry isn't model-written at all: a **deterministic template
engine** (Stage 5) maps the plan's `object_type` to one of **86 parametric families** —
spanning boxes, enclosures, tubes, hooks, clips and dividers, a decor world of frames, dishes,
planters, ornaments, stands and hangers, and a set of engineering hardware (washers, plates,
brackets, standoffs, Gridfinity, fasteners) — over the proven module library, and emits the
OpenSCAD by pure substitution. That tier is what makes **live parameter sliders** real —
dragging a slider re-renders locally in **well under a second with no model call** (measured
per family in `docs/benchmarks/stage-5-template-families.md`). Every family carries an honesty
tier (`benchmarked` vs `baseline`) and is render-verified against its analytic bounding box;
the full catalog is [`docs/templates.md`](docs/templates.md). LLM-written OpenSCAD remains the
fallback for object types no template covers, never the live-slider path.

## The pipeline

```
prompt
  → design plan (JSON IR)            # LLM: structured intent, validated before geometry
  → [clarify?]                       # ask at most one question if the part can't be sized
  → geometry                         # template-covered object_type → DETERMINISTIC emit (no
                                     #   model); otherwise LLM writes OpenSCAD from the library
  → sandboxed render                 # untrusted code is sanitized, then OpenSCAD shells out
  → mesh validation                  # load mesh, check watertight, conservative repair
  → Printability Gate                # pass / warn / fail vs the chosen printer + material
  → auto-orient                      # rotate onto the most stable facet, drop to the bed
  → harden (Manifold3D)              # round-trip into a guaranteed 2-manifold; the
                                     #   hardened mesh is what is exported and sliced
  → Smart Mesh readiness             # synthesize a readiness verdict (score/risks/recs) from
                                     #   the gate (+ optional PrintProof3D engine, + local
                                     #   history); advisory — the gate stays the slice authority
  → [confirm + slice?]               # OrcaSlicer → G-code, only on explicit confirmation,
                                     #   then proven (the 3MF must carry a real toolpath)
  → print report                     # plain-text (or JSON for the web UI) summary + readiness
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
| `errors.py` (Stage A) | Typed, user-facing error classes shared across CLI, pipeline, and web. `ToolMissingError` (a `RuntimeError`): raised BEFORE any subprocess spawn when a fetched tool binary (OpenSCAD / OrcaSlicer) isn't on disk, carrying the exact `fetch_tools.py` recovery command — the CLI prints it and exits 2; the web layer maps it to a typed, recoverable response (design: `render_failed` + message; slice: `sliced:false, reason:tool_missing`). Generic web 500s never leak exception class names (detail goes to the server log). |
| `ir.py` | The Design-Plan IR (Pydantic v2): `DesignPlan`, `Feature`, `Tolerances`. Validates LLM JSON before any geometry is written; salvages almost-valid JSON (`normalize_plan_dict`); decides the one-question clarification policy (`first_clarification`). |
| `llm_provider.py` | All LLM communication, over the OpenAI SDK as the universal client (local Ollama / LM Studio, DeepSeek, any OpenAI-compatible endpoint). Four jobs: `generate_design_plan` (for a local Ollama backend the plan call is schema-constrained at the token level via Ollama's native `/api/chat` `format`, so a model that wraps its JSON in prose, `//` comments, or fences still yields a parseable `DesignPlan`), `generate_openscad`, `describe_sketch` (Stage 9 Slice 1 — merged; the local-vision sketch read), and `describe_photo` (Stage 8.5 — a **local**-vision read of an uploaded photo into a rough text seed, via Ollama's native `/api/chat` with `think:false`; the photo never auto-sends off the machine). Builds the constraints block and library manifest injected into the prompts. Retries connection/timeout errors so a flaky local server doesn't fail a case - with a Stage A fail-fast: a FIRST-attempt connection error plus a failed 2 s TCP probe of a LOCAL backend host means the server was never up, so the call raises immediately instead of burning the 6×30 s budget (cloud/non-loopback hosts are never probe-judged and keep the full budget); the client splits connect (5s) from read (timeout_s) and runs with max_retries=0 so SDK-internal retries can't stack under KimCad's own loop. Raises `PlanParseError` at the parse boundary when model output can't become a `DesignPlan` (so the pipeline can fail clean, not crash). `FallbackProvider` wraps a primary with an opt-in alt backend, transparently retrying it on a primary connection/timeout/404; both satisfy the `Provider` `Protocol` the pipeline depends on. The client is injectable for offline tests. |
| `openscad_runner.py` | Sanitize-and-render. **Trust boundary:** generated OpenSCAD is untrusted, so before it reaches the binary it is checked — `import()`/`surface()` file I/O, `minkowski()` (a CPU/RAM DoS at high `$fn`), and any `use`/`include` reaching outside the approved `library/` path are **blocked** (the orchestrator re-prompts) rather than silently stripped. Also deterministically repairs two common model slips: injecting a missing library `use` line, and appending a dropped trailing `;`. Then it shells out (`openscad -o part.3mf part.scad`) in an isolated temp dir with a timeout and an output-size guard, falling back to STL if the binary lacks `lib3mf`. |
| `cadquery_runner.py` (Stage 8) | The in-process (app venv) side of the **deterministic CadQuery `.STEP` export**: it runs only KimCad's OWN trusted template twins (`cadquery_templates.py`), parameterized by clamped finite floats — **no LLM authors CadQuery** (the Stage-8 LLM-CadQuery codegen was removed after KC-4/#6 measured its realized lift at 0). `sanitize_cadquery` (an `ast` block-list) is kept as **defense-in-depth** around those trusted scripts — non-cadquery/math imports, banned builtin/module names + attributes (`os`, `open`, `system`, …), and **every** `__dunder__` name/attribute/string-subscript key plus frame/`__globals__` introspection attrs and `str.format` field pivots are **blocked** (re-prompted, never stripped). `render_cadquery` writes the script to an isolated temp dir and runs the worker as a subprocess (timeout + output-size guard), returning the same `RenderResult` the OpenSCAD path does (with `backend="cadquery"` and a `step_path`). `find_cadquery_interpreter` is the graceful discovery probe. CadQuery is optional — absent ⇒ no `.STEP` export (the OpenSCAD geometry path is unaffected). |
| `cadquery_worker.py` (Stage 8) | The **out-of-process worker**, run in its own interpreter (isolation kept as **defense-in-depth** — KimCad and CadQuery both run on Python 3.13; the template-twin script runs at arm's length even though KimCad itself authors it). Stdlib + cadquery only — never imports `kimcad`. Executes the (already-sanitized) script with a **restricted `__builtins__`** (an `__import__` that returns the geometry-only cadquery facade / real `math` and raises `ImportError` for anything else) against a **geometry-only facade** (every top-level submodule stripped, so there's no module object to pivot through to `os`); the script does no I/O — it assigns `result` and the worker exports STL (+ STEP) and measures the bbox, writing its JSON result to a dedicated file (never stdout). The runner spawns it in an isolated cwd with a secret-scrubbed env; OS-level confinement is a tracked Stage-11 hardening. Defence in depth; the honest boundary is local-machine trust. See `docs/cadquery-backend.md`. |
| `cadquery_bench.py` (Stage 8) | The deterministic CadQuery-engine **proof/benchmark** — the counterpart to `template_bench.py` for the second backend. Renders a fixed spread of fixed `cq` scripts (box, through-hole, cylinder, filleted plate, boolean L-bracket) through the real worker and checks each is watertight at its declared envelope — no model. `docs/benchmarks/stage-8-cadquery-backend.md`. |
| `cadquery_templates.py` | The **trusted CadQuery twins**: a deterministic `cq`-script generator for each template family, parameterized by the same clamped finite floats as the OpenSCAD path, producing the editable watertight `.STEP` export. KimCad authors every twin — **no LLM** — so the STEP path carries none of the removed LLM-codegen risk (see `cadquery_runner.py`). The actual source of `.STEP` today. |
| `validation.py` | Loads a rendered mesh (flattening a multi-part scene), checks watertightness, attempts conservative repairs (fill holes, fix normals/winding/inversion), and reports geometry stats — volume, bounding box, body count. The bounding box here feeds the gate's dimensional assertion. |
| `printability.py` | The **Printability Gate**: pass / warn / fail with reasons. Phase-1 checks: dimensional assertion (rendered bbox vs the plan envelope, flat 0.5 mm tolerance, no relative term), build-volume fit, declared wall thickness vs the material/nozzle minimum, and disconnected-shell detection. A non-watertight mesh is a hard fail. Single source of truth for the dimensional tolerance (`dim_tolerance`), shared with the retry feedback and the web UI. |
| `orientation.py` | Auto-orientation: compute stable resting poses via the convex hull, rotate the part so the most probable resting face sits at Z = 0, and drop it to the bed. The chosen pose and its stability are surfaced in the report. |
| `hardening.py` | Pre-slice mesh hardening: round-trips the oriented mesh through **Manifold3D** into a guaranteed 2-manifold before it is exported and sliced (watertight is necessary but not sufficient — a watertight mesh can still carry non-manifold edges a slicer mis-handles). Best-effort and optional at runtime: if Manifold3D is absent or rejects the mesh, the already-validated mesh is passed through unchanged with a note. Never raises. |
| `slicer.py` | OrcaSlicer CLI integration: turns a validated mesh into a sliced, G-code-bearing 3MF. Resolves config profile *names* to the shipped on-disk profile JSONs (`resolve_slice_settings`, fail-loud on a missing/ambiguous name), runs OrcaSlicer as an argv list (no shell), and **proves** the result — the 3MF must carry a real motion-bearing toolpath (`prove_gcode_3mf`), which also yields the print estimate. Never called without confirmation (enforced upstream in the pipeline). |
| `pipeline.py` | The orchestrator described above: wires every stage, owns the render/gate retry loop, builds the `PrintReport`, and enforces the confirm-before-slice rule. Tiered: a template-covered `object_type` builds deterministically in one shot (no model, no retry — a too-wrong part fails closed, fixed by a parameter not by regenerating); everything else falls back to LLM codegen, which is **OpenSCAD-only** — the Stage-8 LLM-CadQuery parallel backend was removed after its measured lift was 0 (KC-4/#6), so no LLM ever writes CadQuery; CadQuery runs only KimCad's trusted template twins (`cadquery_templates.py`) for the editable `.STEP` export. `rerender(base_plan, family, values, …)` is the live-slider path — re-emit + render + gate at new values with no model and no prompt, sharing the orient/harden/export/slice tail with `run`. |
| `templates.py` | The **deterministic template engine** (Stage 5; catalog grown to **86 families** in #19) over the proven `library/` modules (`library/dishes.scad` for the decor world — frames, hangers, dishes, holders, planters, ornaments, stands, joinery — and `library/parts.scad` for engineering hardware — washers, plates, brackets, standoffs, boxes, raceways, Gridfinity, fasteners). Each family is pure data: a typed, range-bounded `ParamSpec` set (the live-slider schema), the library module to call, fixed args, an analytic bounding box, and an **honesty `tier`** (`benchmarked` = what-you-set-is-what-you-get; `baseline` = real, gate-verified geometry with a real-world fit/load/pattern caveat to check before relying on it — e.g. a thread-relief nut/bolt, a Gridfinity-compatible footprint, a VESA hole pattern). `match(plan)` resolves an `object_type` (alias/plural/separator-normalized, collision-checked) to a family and derives its values from the plan; `emit_scad` produces OpenSCAD by **pure string substitution** — only clamped, finite numbers reach emit, so it's injection-safe and byte-deterministic. Values are clamped to range with ordering constraints (a tube's bore stays inside its wall). The tier is inert to the Printability Gate: **every** family, whatever its label, is render-verified against its declared analytic bounding box, with a trusted CadQuery `.STEP` twin. The catalog reference is [`docs/templates.md`](docs/templates.md). |
| `template_bench.py` | The deterministic-template **proof/benchmark** — the counterpart to `benchmark.py`. Renders + re-renders every family through the real `Pipeline.rerender` path and measures it: watertight at the declared envelope, byte-deterministic emit, **no model call** (it wires a provider that *raises* if invoked), and the re-render time. `python -m kimcad.template_bench [--write PATH]` writes the markdown proof. |
| `printer_connector.py` | The send-to-printer **abstraction**: the `PrinterConnector` `Protocol` (capabilities / status / send / job-status), the frozen `PrinterCapabilities` / `PrinterStatus` / `PrintJob` models, the `ConnectorError` family, and the shared `ensure_sendable()` gate — it sends only when `confirm is True` (not merely truthy) **and** the file proves out as a real motion-bearing slice, otherwise nothing is sent. Ships a thread-safe in-memory `LoopbackConnector` (the `mock` connector) so the whole path is testable with no hardware. |
| `bambu_connector.py` (Stage 10) | The Bambu-native LAN connector (P2S / A1): MQTT-over-TLS for state/control + FTPS upload via the **optional** `bambulabs-api` package — absent package degrades to an actionable "pip install" config message, never a crash (the CadQuery graceful-absence posture). KimCad's sliced `.gcode.3mf` is Bambu's native format, so `send` uploads it whole (no G-code extraction) and starts plate 1; a running job is refused as a soft `busy`; sessions are short-lived MQTT connections (camera never started), always closed. The access code comes from an env var, never config. Wholly tested against an injected fake transport; first hardware run is the Stage 11 beta. |
| `octoprint_connector.py` | A real OctoPrint REST connector over stdlib `urllib` (`X-Api-Key` header). The API key comes from the environment only — never stored in config, never logged. A reachable-but-rejected printer (401/403) raises a distinct `AuthError` rather than masquerading as offline; single-plate G-code is extracted with a hard size cap. |
| `mock_printer.py` | A runnable mock OctoPrint server (stdlib `http.server`) — version / printerprofiles / printer / files / job endpoints with API-key auth — so the OctoPrint connector is exercised end-to-end offline. `python -m kimcad.mock_printer`. |
| `moonraker_connector.py` | A Moonraker (Klipper) REST connector over stdlib `urllib` — covers Creality-Klipper / Voron / RatRig / Mainsail / Fluidd. Optional `X-Api-Key` (Moonraker often runs unauthenticated on a LAN). Maps Klipper `print_stats.state` onto the normalized states; an unrecognized state reports `error`, never a false "ready." |
| `mock_moonraker.py` | A runnable mock Moonraker server (`python -m kimcad.mock_moonraker`) — the `/printer/objects/query` + `/server/files/upload` subset with optional API-key auth — so the Moonraker connector is exercised end-to-end offline. |
| `prusalink_connector.py` | A PrusaLink (Prusa) REST connector over stdlib `urllib` (`X-Api-Key`) — covers MK4 / MK3.9 / MINI / XL. Uploads with `PUT /api/v1/files/<storage>/<name>` (path segments percent-encoded) + `Print-After-Upload`; a 409 surfaces as a typed `busy`. Storage is configurable (default `usb`). |
| `mock_prusalink.py` | A runnable mock PrusaLink server (`python -m kimcad.mock_prusalink`) — the `/api/v1/info` + `/api/v1/status` + `PUT /api/v1/files/...` subset with API-key auth and Overwrite/409 semantics. |
| `duet_connector.py` (#26) | A Duet / **RepRapFirmware** connector (RRF 2/3) over the classic `/rr_*` HTTP interface: `/rr_connect` (an optional board password allocates a session — always `/rr_disconnect`ed), `/rr_upload` of the `.gcode` to the SD `gcodes` folder, `M32` start, `rr_status` progress with a done-latch. The upload name is sanitized (alnum + `-_`) so it can't inject into the `M32` command string; bed-temp shapes (dict/number/list) are tolerated. Validated against `mock_duet.py`; metal validation folds into #11. |
| `mock_duet.py` (#26) | A runnable **adversarial** mock Duet/RRF server — `/rr_*` with fault injection and a session pool — so the connector is exercised offline; it faithfully RESETS progress on completion so a passing test is earned. |
| `marlin_connector.py` (#26) | A **Marlin** connector (the Ender-class installed base) over the raw M-code line protocol, on a USB serial port (optional `pyserial`) or a `host:port` serial-over-network bridge: `M115` handshake, line-number + checksum SD upload (`M28`/`M29`, honoring `Resend:`), `M23`/`M24` start, `M27` progress, best-effort `M29` on a mid-stream error. The SD filename is an 8.3 alnum (`_sd_name`). Validated against `mock_marlin.py`; metal validation folds into #11. |
| `mock_marlin.py` (#26) | A runnable **adversarial** mock Marlin firmware — the M-code line protocol with `Resend`/`Error` fault injection and faithful completion reset — so the connector is exercised offline. |
| `capability.py` | Capability reconciliation: `reconcile(printer, caps)` auto-fills a **blank** profile field from the printer's reported build volume / nozzle / materials and flags any config-vs-printer mismatch (config stays authoritative; the disagreement is surfaced with the actual numbers, never silently overridden). |
| `connectors.py` | The connector **factory**: `build_connector(config, name)` resolves a configured connection (`mock` / `octoprint` / `moonraker` / `prusalink` / `duet` / `marlin`) and reads any credential from its env var, with clear errors for an unknown name (`reason="unknown"`), unknown type, or missing base-url / credential (it names the missing env var, never its value). `connector_is_simulated` derives the honest no-hardware label from each class's `drives_hardware` via a single class registry. |
| `mcp_server.py` | The printer **MCP server** — a dependency-free MCP server (newline-delimited JSON-RPC 2.0 over stdio) exposing `list_connectors` / `printer_status` / `printer_capabilities` / `send_print` so an agent can drive the printer. The protocol is a pure `handle()` method (unit-tested with no subprocess); `send_print` passes the confirm value straight through to the `confirm is True` gate without coercion, so a truthy-but-not-`True` value cannot send. `python -m kimcad.mcp_server`. |
| `benchmark.py` | The Phase-1 done-gate harness. Runs a fixed set of plain-English prompts end to end and scores the batch against a pass-rate threshold. Data-driven (prompts and thresholds from `bench/*.yaml`) and decoupled from execution (a `run_one` callable) so the scoring is unit-testable without an LLM or binaries. Beyond the coarse completion gate it grades each case on the spec's three axes — **matches-request / correct-dimensions / slices-clean** — each tri-state so an unmeasured axis never counts; `--slice` grades the slices-clean axis with a real slice. Persists per-case artifacts (plan, report, outcome) for offline diagnosis. |
| `model_advisor.py` (Stage 6) | The hardware/availability-aware **model advisor** behind `kimcad models`. Best-effort probes of RAM / CPU / GPU and the installed Ollama models (each degrades to `None`, never raises), plus a pure `recommend()` that picks the best installed-and-fitting local model **by measured merit, not origin** (KimCad runs fully offline through Ollama, so model origin carries no data-governance weight; the default planner is `qwen2.5:7b`), names an upgrade the box could pull, and surfaces a non-China alternative as informational only. **Advisory only — it never rewrites config or switches the model;** the model stays choosable via config backends, `config/local.yaml`, and `--backend`. |
| `bakeoff.py` (Stage 6) | The **model bake-off** behind `kimcad bakeoff`. Runs the benchmark once per backend (each model measured in isolation — no fallback) and compares them on the 3-axis graded rate, completion, and speed, then **recommends** switch-or-keep. Recommend-only by design: flipping the configured default model is a human decision, so the harness never edits config. |
| `smart_mesh.py` (Stage 7) | **Smart Mesh readiness** synthesis. A pure `assess_readiness(gate, mesh_report, …, printproof=…)` that folds the Printability Gate, the mesh integrity stats, and an *optional* PrintProof3D report into one verdict — a 0–100 score, a plain verdict, a confidence, the risks, and concrete recommendations. The tone is the **worst** of KimCad's own read and PrintProof3D's status, so the card is never more optimistic than either signal; attribution is honest about what backed it (gate / engine / history). No I/O — fully unit-tested. |
| `printproof3d.py` (Stage 7) | The **PrintProof3D arm's-length wrapper**. Runs the owner's MIT Rust validation **engine** as a subprocess (argv list, no shell, **never linked**) against the bed-positioned mesh and parses its `ValidationReport` JSON into the typed report Smart Mesh consumes. Generates the engine's printer/material profile JSON from KimCad's own config. Best-effort + injectable runner: a missing/un-built engine, a profile error, a runner raise, or an unparseable report all degrade to `None` (Smart Mesh falls back to the gate) — it **never raises**, and is gated on the parsed report file, not the exit code (a non-zero exit is a fail *verdict*, not a crash). |
| `history.py` (Stage 7) | The **Smart Mesh learning store**. A local-first JSON record of built parts (coarse — type / readiness score / gate / material / largest dimension; no geometry, no prompt) at `~/.kimcad/history.json` by default (never the repo). Pure `compare_phrase()` produces the honest "compared to your past parts" line — strictly factual (a personal best needs a strict beat of every prior; a tie reads "on par," never "below"; no history → no line). All best-effort: every degrade path returns cleanly and **never raises**. |
| `cli.py` | The `kimcad` command — `design` (the default verb for a bare prompt), `bench`, `web`, `models` (the hardware advisor), and `bakeoff` (the model comparison). `design --slice` is the explicit slice confirmation; `design --send <connector>` additionally sends the proven G-code through a connector behind the same confirmation gate (a gate-failed part is never sent; an offline printer is reported and the file is left on disk). Wires already-tested pieces together; turns foreseeable setup problems (bad config, missing key, missing prompt file) and un-parseable model output into a plain-English message and a stable non-zero exit rather than a traceback. |
| `design_store.py` (Stage 8.5) | The **saved-designs store** ("My Designs"). Local-first, best-effort persistence of each built design under `~/.kimcad/designs/<id>/` (`meta.json` + `mesh.stl` + `thumb.png`) — never the repo, nothing leaves the machine. `save` / `list` / `get` / `rename` / `delete` / `duplicate` / `export_bytes` / `import_bytes`, all guarded by an ASCII-only `_safe_id` (no path escape) and serialized by a write lock with atomic `os.replace` meta writes (retried on the Windows open-handle race). Import is **zip-slip safe** — only the three known files are read by exact name (never the archive's paths) and a bounded inflated-read rejects a decompression bomb. Every method swallows failures (degrade, never raise), so a persistence miss never breaks a build. |
| `design_registry.py` (Stage 9) | `DesignRegistry` — the web layer's per-design state, extracted from the webapp closure. One object owns every per-design registry/cache (mesh, G-code, STEP, gate verdict, geometry version, slice cache, template state, snapshot, saved-id) plus the lock and the three load-bearing protocols: lockstep eviction (incl. on-disk cleanup), LRU cap enforcement, and the geometry-version guard that drops a slice landing after a mid-flight re-render. `_locked`-suffixed methods require the caller to hold `reg.lock`. |
| `model_pull.py` (Stage 10) | The in-app model download: one app-wide job (`JOB`) that streams Ollama's native `/api/pull` for KimCad's OWN two models (the list is fixed server-side — the no-model-menu rule), with per-model progress for the UI to poll. Loopback-only (it manages the on-device install), disk pre-checked before gigabytes move, per-model friendly failures (disk-full maps to the fix), and idempotent start (a wizard re-mount can't fork a second download). |
| `ollama_runtime.py` (Stage 11) | The **managed-engine lifecycle**: downloads the official portable Ollama binary (SHA-256-verified, version-pinned), starts it headless with `OLLAMA_HOST` / `OLLAMA_MODELS` set to KimCad's data dir (so models land in `%LOCALAPPDATA%\KimCad\models`, not `~\.ollama`), and tears it down on process exit. `_child_env()` scrubs cloud credentials from the subprocess env via the project-canonical `is_secret_env()` (see `subprocess_env.py`) rather than a bespoke deny-list. Reuses a system Ollama if one is already up on the default port; starts the managed binary only when none is found. |
| `paths.py` (Stage 11) | THE dev/installed path seam: `KIMCAD_INSTALL_ROOT` (set by the installed launcher before Python starts) switches reads to the install root and writes to the per-user data dir; dev behavior is repo-rooted and unchanged. The per-user dir is **platform-idiomatic** (KC-8/#13): `%LOCALAPPDATA%\KimCad` on Windows, `~/Library/Application Support/KimCad` on macOS, `$XDG_DATA_HOME`/`~/.local/share/KimCad` on Linux. `config.PROJECT_ROOT` routes through it; the user config overlay (`local.yaml`) is per-user when installed. The browser UI `kimcad web` is supported **from source on macOS/Linux**; the zero-terminal installer + the `kimcad shell` window are Windows-only for now (`shell.py` degrades to `kimcad web` off-Windows). |
| `shell.py` (Stage 11) | The windowed app (`kimcad shell`): a pywebview/WebView2 window over the same server `kimcad web` runs, on a STABLE loopback port (8766+, never ephemeral — the origin holds the SPA's localStorage); window close stops the server; the one JS bridge is `open_external` (http/s only, system browser); pywebview absent or the WebView2/.NET runtime missing degrades to one friendly line naming `kimcad web`. |
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

The original modules — five seed files plus five early additions — back the first ten template families:

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

The #19 catalog expansion to 86 families added two large theme libraries on top of these:

- **dishes.scad** — Kim's decor world: frames, picture/art hangers, dishes & trays, candle and
  plant holders, planters, ornaments & gift boxes, stands, ledges & rails, and frame joinery.
- **parts.scad** — everyday engineering hardware: washers, dowel pins, plates & faceplates,
  brackets & gussets, standoffs, boxes & raceways, a bar pull, a funnel, Gridfinity bin/baseplate,
  and thread-relief nut/bolt blanks.

The full per-family catalog — display name, honesty tier, and a one-line summary, grouped by
theme — is in [`docs/templates.md`](docs/templates.md) (generated from the live registry).

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
`GET /api/options` feeds the printer/material pickers. A **CadQuery-built** part (Stage 8) also
exposes `GET /api/step/<id>` — the editable STEP/BREP CAD download (the design response carries a
`step_url`); the report always names the producing `backend`, and an OpenSCAD part simply has no
`step_url`. The page also shows a **read-only
ready/not-ready connection badge** (`GET /api/connectors` + `GET /api/connector-status/<name>`,
each flagged `simulated` so a no-hardware connection is labelled honestly rather than narrated
as a real print). **Stage 10: the browser sends too** — the SPA's SendPanel (under a finished slice) drives
`POST /api/send/<id>` through the app's own confirm dialog (the POST is the user's
confirmation; the server re-checks the gate verdict and refuses anything but a proven,
gate-passed slice). The CLI (`--send`) and the MCP server drive the same endpoint.
A send failure (offline/unreachable, bad key, misconfig) is a soft result, not an error — it
carries a typed `reason` and a user-facing `note` (never the raw developer detail), and the
download stays as the fallback, as does the validated model itself.

**Stage 8.5 additions (shipped; tagged `stage-8.5`):** `/api/designs*` persist + reopen the
"My Designs" library; `/api/settings` + `/api/model-status` back the in-app Settings screen (the
saved cloud API key is masked on redisplay and never echoed back in full); `GET /api/health` is a
lightweight liveness check; `GET /api/design/progress/<job_id>` is the step-progress poll the
"Designing…" screen reads; `POST /api/render/<id>` is the deterministic live-slider re-render (no
model call); and `POST /api/photo-seed` reads an uploaded photo with the **local** vision model into
a rough text seed (never persisted, never logged, never auto-sent). `_SettingsAwareProvider` routes a design prompt to the user's
opt-in cloud model when configured, but `describe_photo` always builds a dedicated **local** provider,
so the photo path is unreachable from the cloud-TEXT routing — the photo can't leave the machine.

**Stage 9 additions:** `POST /api/sketch-seed` is the sketch twin of `/api/photo-seed` (a
dimensioned sketch reads shape + the written sizes, taken as written). Both seeds are read by the
dedicated **local** vision model `llm.vision_model` (default `qwen2.5vl:3b` — gemma4:e4b's vision
is broken on this stack; see `docs/benchmarks/stage-9-vision-onramps.md`), with a structural
loopback-only guard before any image leaves the process and typed failures: a missing model
returns `{"status": "model_unavailable"}` with the exact pull command, and a non-404 read failure
maps to a friendly try-again message. `/api/model-status` reports the vision model's presence
alongside the design model's. Per-design server state moved into `DesignRegistry`
(`design_registry.py`).

**Stage 11 additions:** the app ships as a double-click installer (`scripts/build_installer.py`
stages embeddable CPython + site-packages + tools + the SPA; pinned Inno Setup compiles it;
`scripts/verify_install.py` proves an install end-to-end incl. the SPA actually serving) with
a read/write split at runtime: the install dir is read-only (config templates, tools, code) and
all writes go to the per-user data dir via `paths.py`; `GET/POST /api/connections` backs the
Settings Printer-connections card (the saved overlay feeds `build_connector` for every caller, and
now includes the `duet` and `marlin` types alongside Bambu/OctoPrint/Moonraker/PrusaLink).

**Packaging policy — batteries-included (ENG-001):** `requirements.lock` is the single pinned set the
installer, CI, and the documented from-source path all consume. The official installer ships **both**
optional connector extras — `bambulabs-api` (the `bambu` extra) *and* `pyserial` (the `serial` extra) —
so every supported printer, including a USB Marlin/Ender, works out of the box without a manual `pip`
step. The two extras stay opt-in in `pyproject.toml` (a lean `pip install kimcad` for non-printer use),
but the *bundled* build is deliberately symmetric. `CONTRIBUTING.md` documents the lock-regeneration
command, and `tests/test_build_installer.py::test_lock_bundles_both_connector_extras_symmetrically`
fails the gate if either extra drops out of the lock.

**Session-token guard (#31 / KC-26):** the server mints a fresh `secrets.token_urlsafe` per boot,
injects it into the served `index.html` shell (`<meta name="kimcad-session-token">`), and **refuses
any state-changing `POST`** that doesn't return it as the `X-KimCad-Session` header — a `403` after a
constant-time `hmac.compare_digest`. This is defense-in-depth against a **drive-by cross-origin POST**
from a malicious page: it can reach loopback but, being cross-origin, can't read the same-origin token,
and the custom header forces a CORS preflight it can't satisfy. Deliberately **not** full CSRF
protection — KimCad is a single-user loopback app with no cookie session to forge — so a per-boot
bearer the attacker can't read is the proportionate measure (`docs/api.md` + `SECURITY.md`). `GET`s
are never gated; a stale token after a server restart surfaces a one-click reload in the SPA, and the
two side-effecting GETs that can't carry a header (the lazy STEP build, the slice download) are exempt
by design. Off when no token is configured (the tests / embedding default).



**Stage 10 additions:** the direct-print UI surfaces the existing send path in the SPA
(SendPanel under a finished slice — connector picker from `GET /api/connectors`, the app's
confirm dialog as the explicit start, live status follow via `GET /api/connector-status/<name>`);
`POST /api/model-pull` starts the in-app download of KimCad's OWN two models (the list is fixed
server-side — never a caller-supplied name; loopback-only; demo mode refused; a down Ollama is a
typed status) and `GET /api/model-pull/progress` is the per-model progress poll the wizard and
Settings read (`model_pull.py`). The Bambu-native connector (`bambu_connector.py`) joins the
send path behind the same `ensure_sendable` gate.

**The browser UI is a React + TypeScript SPA** (Stage 4), compiled by Vite from `frontend/`
into `src/kimcad/web/` (`index.html` + `assets/`). Node/Vite are **build-time only** — the
committed build output is served verbatim by this same stdlib server (the SPA shell at `/`,
its bundles at `/assets/<file>` behind a traversal guard that allows only a plain filename; three.js
is bundled into those assets, so there's no separately-served vendor copy), so `kimcad web`
runs with no Node toolchain on the target box. The JSON endpoints above are the unchanged
contract between the SPA and the pipeline. Rebuild the UI with
`npm --prefix frontend ci && npm --prefix frontend run build` (see `frontend/README.md`).

**Live parameter sliders (Stage 5).** For a template-backed design, `/api/design` returns the
family name plus the typed `parameters` snapshot, and the SPA renders a slider per parameter.
Dragging one debounces a `POST /api/render/<id>` with the new `{values}`; the server re-renders
deterministically (the `Pipeline.rerender` path — no model), returns the clamped values + a
**versioned** `mesh_url` (cache-busted), and the viewport reloads while the previous mesh stays
on screen. A re-render **invalidates the cached slice/G-code** for that id and is serialized
against concurrent drags, so a stale shape can never be sliced or sent; an LLM-backed part has
no `parameters` and stays read-only. The slider ranges are the family's own bounds, so a part
that the gate would reject can't even be dialed in.

**Saved designs / "My Designs" (Stage 8.5).** The SPA has routes (`#/`, `#/designs`,
`#/design/<id>`) and persists work via `design_store.py`. When the viewport frames a part the
client auto-saves it (`POST /api/designs/save`, carrying a viewport-captured thumbnail) and routes
to `#/design/<id>`, so a refresh restores the part + sliders (`GET /api/designs/<id>` re-registers
it into the live loop). The library (`GET /api/designs`) backs the gallery; `rename` / `delete` /
`duplicate` mutate it; `GET .../export` and `POST /api/designs/import` move a design as a portable
`.kimcad` zip. Save is best-effort — a transient failure returns a soft `503` the SPA retries
(surfaced as a Topbar "Saving… / Saved / retrying" indicator), never a hard error; the server mints
a stable id per live design so rapid auto-saves converge to one library entry. The pipeline exports
the oriented mesh atomically (temp + `os.replace`), so a save-copy or mesh fetch never reads a torn
STL mid-re-render.

## Local-first and the injectable seam

KimCad is **local-first**: out of the box it talks to a local runtime (Ollama or LM
Studio) running the default planner `qwen2.5:7b` (with `gemma4:e4b` as the non-China
fallback), so there's no API key and no network requirement. A cloud
API (DeepSeek or any OpenAI-compatible endpoint) is an opt-in fallback configured in
`config/local.yaml`.

The same seam that makes that swap trivial — the **LLM provider, renderer, and slicer
are all injected** into the pipeline — is what makes the engine testable. With a fake
provider and a stub renderer, the entire orchestration runs offline against real
`trimesh` geometry: no model, no binary, no socket. The deterministic stages
(validation, gate, orientation) are pure enough to test directly. So the parts that
decide whether a part is correct are verified without ever invoking the one
non-deterministic component.
