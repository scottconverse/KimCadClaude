# Changelog

All notable changes to KimCad are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/); this project uses semantic versioning.

## [Unreleased]

> The project versions toward the `0.9.0b1` Windows beta (Stage 11); each stage is tagged as it lands.
> **Stages 0–7 are tagged (`stage-0` … `stage-7`).** Stage 5 (deterministic template engine +
> live sliders) and **Stage 6 (the model layer — advisor, tiered fallback, 3-axis grading,
> bake-off, plan-failure robustness) both merged + tagged 2026-06-02** (Stage 6 through the full
> `audit-team` gate + remediation at 0/0/0/0/0). **Stage 7 (Smart Mesh + PrintProof3D + readiness
> report + learning store) merged + tagged `stage-7` 2026-06-02** — through the full 5-role
> `audit-team` stage gate + remediation at 0/0/0/0/0. **Stage 8.5 (Usability) is DONE — merged to
> `main` and tagged `stage-8.5`.** All 11 slices shipped; the stage gate passed both the runtime
> wiring-audit and the 5-role audit-team, with every finding remediated and independently re-audited
> twice to 0/0/0/0/0 (see `docs/audits/stage-8.5/stage-gate-2026-06-05/`). Slices 1–7 below for reference:
> Slice 1 (persistence + "My Designs"), Slices 2–4 (refine-as-a-conversation + version history,
> numeric parameter entry, mm/inch units), Slice 5 (the on-ramps design — no code), Slice 6 (the
> in-app Settings screen — model status, opt-in cloud, experimental toggle), and Slice 7 (the
> "describe with a photo" on-ramp). Slices passed their gates progressively; the stage closed at
> the full audit-team gate. These sections accumulate toward the `0.9.0b1` beta release.
> New runtime dependency (Stage 1): **`manifold3d>=3.0`** — installed by default
> (a compiled wheel; relevant to the install footprint on the 32 GB target), though the
> *import* is optional at runtime (hardening is skipped with a note if it is absent).

### Added
- **Editable CAD (`.STEP`) export for every standard part (KC-2, #8).** Template-built parts
  now offer a `.STEP` download whenever the optional CadQuery engine is installed — built from
  KimCad's **own trusted CadQuery twin** of each template family (never AI-written code),
  lazily on first download, cached, and invalidated by any re-shape so it always matches the
  live sliders. New *Settings → Editable CAD export* card shows the engine's status and walks
  through the one-time install (`py -3.13 -m pip install cadquery` + *check again* — discovery
  is automatic). Without the engine, the Export panel points at Settings instead of dangling a
  dead promise (KC-11, #15).

### Removed
- **The LLM-CadQuery fallback generator (KC-4, #6 / KC-3, #9).** Its realized pass-rate lift
  **measured 0** on the shipping model (`docs/benchmarks/stage-8-cadquery-backend.md`), so the
  path — and with it the only place AI-written Python was ever executed — is gone. LLM codegen
  is OpenSCAD-only; CadQuery now runs exclusively KimCad's own template twins.

### Fixed
- **Cloud-key "Replace" is reversible (KC-1, #7).** Replacing the saved OpenRouter key now has
  a Cancel that returns to the masked view without touching the stored key; the full save
  round-trip (masked echo, keyring at rest, restart persistence) is pinned by an end-to-end
  test — no data-loss bug existed.
- **Printer build volumes pinned to truth (KC-7, #12).** Every configured printer's
  `build_volume` is now cross-checked in tests against the printable area of the shipped
  OrcaSlicer machine profile it slices with (inheritance-resolved) — the numbers can never
  silently drift.

- **Stage 11 — the Windows installer + the beta (`0.9.0b1`) — DONE (merged to `main`,
  tagged `stage-11` AND `beta`).** KimCad is now a double-click Windows app.
  - **New: `KimCad-Setup-0.9.0b1.exe`** — a single unsigned installer (SmartScreen
    walkthrough + SHA-256 verification in `docs/install-guide.md`) carrying an embedded
    CPython 3.13.13, the app + pinned dependencies, the built SPA, OpenSCAD, OrcaSlicer,
    and the **PrintProof3D validation engine (stable v0.5.0 — bundled and ON by default**,
    resolving the ROADMAP's gated-on-stable branch in favor). Start-Menu/Desktop shortcuts
    open **`kimcad shell`** — the app in its own WebView2 window on a stable local port;
    closing the window exits cleanly. Installs are proven by `scripts/verify_install.py`:
    version, server, bundled tools, **the SPA actually serving**, prompt templates, a demo
    design, and a full-tree diff showing the install dir is never written to (per-user
    data goes to `%LOCALAPPDATA%\KimCad`; saved designs stay in `~/.kimcad`, untouched by
    the uninstaller). Spaced install paths (`Program Files (x86)`-style) verified.
  - **New: Settings → Printer connections** — printers are set up inside the app now
    (address + serial + the AMS toggle; the access code/API key stays in a NAMED env var
    and never crosses the UI); the saved values feed the real send path for the SPA, CLI,
    and MCP alike. Moonraker + PrusaLink join the Bambu templates as shipped
    fill-in-able connections.
  - **New: first run on a clean box** — the wizard detects a missing/stopped Ollama and
    offers **Get Ollama** (system browser via the shell's one JS bridge); Settings gained
    the same guidance plus **"Run the setup walkthrough again"**, so skipping setup is
    never a dead end. The Stage-10 in-app model downloads cover the rest.
  - **Versioning:** `0.9.0b1` single-sourced from package metadata on every surface
    (CLI `--version`, `/api/health`, Settings About, the MCP serverInfo, the installer's
    name + VersionInfo) — tripwire-tested so no literal can drift.
  - **Fixed at the beta gate (Blocker): the wheel shipped no SPA and no prompt
    templates** — the editable dev install had masked missing package-data for the
    project's whole history; every earlier install proof exercised the API, never `/`.
    Packaging fixed, and `verify_install` now fetches the SPA shell + a real asset so it
    can never silently regress. The gate also drove the installer-staging smoke into CI
    (every push now stages the real install tree and verifies it), made the release strip
    real (no ruff/pytest/setuptools in the shipped payload, asserted), and hardened the
    launcher-contract tests.
  - **Dispositions** (docs/audits/stage-11/dispositions-2026-06-10.md): hosted CI stays
    off (owner decision — the self-hosted strict gate is the release gate); the Stage-8
    CadQuery-confinement deferral re-accepted with a stronger rationale (the beta
    installer ships without the CadQuery backend entirely); the per-user-install
    tradeoff disclosed.
  - **Docs:** `docs/install-guide.md` (SmartScreen, checksums, what-goes-where),
    `docs/supported-printers.md` (API-validated vs metal-validated kept honest — nothing
    is metal-validated until the beta runs at Kim's), `docs/beta/first-hardware-contact.md`
    (the scripted first-printer-contact checklist), getting-started rewritten around the
    installer with from-source as the developer path.
- **Stage 10 — Direct print from the app + Bambu-native + in-app model downloads — DONE
  (merged to `main`, tagged `stage-10`).**
  - **New: send a sliced part straight from the app.** Under a finished slice, a "Send to
    printer" panel: connector picker with honest labels (the built-in `mock` is "test
    connection — no real printer"; an unconfigured connection is disabled and, when
    selected, names its exact missing piece), the app's own confirm dialog as THE explicit
    start (the POST is the confirmation; the server re-checks the printability gate), a
    simulated send narrated as a test (never a print), live printer status followed after a
    real send (bounded polls that survive a transient miss), and every not-sent outcome a
    soft, typed note with a next step — the download stays the fallback.
  - **New: Bambu Lab native connector (P2S / A1, LAN mode)** over the OPTIONAL
    `bambulabs-api` package (`pip install bambulabs-api`, or `pip install "kimcad[bambu]"`):
    MQTT-over-TLS control + FTPS upload of the whole `.gcode.3mf` (Bambu's own format —
    started by plate, single-plate enforced, the FTP transfer-complete code required as
    proof). Hardware-safety edges fail CLOSED: only a state KNOWN free (IDLE/FINISH) may
    print — UNKNOWN/FAILED refuse, and the state is re-checked after the upload; a rejected
    access code maps to `auth` with the on-printer fix; sessions disconnect cleanly (the
    library never sends MQTT DISCONNECT on its own). `bambu_p2s`/`bambu_a1` config templates
    ship visible-but-unconfigured. *Validated wholly against a mock transport verified
    faithful to the real library — the first real-hardware run is the Stage 11 beta.*
  - **New: the setup wizard downloads the AI models in-app.** "Get the model" is a button:
    `POST /api/model-pull` streams Ollama's pull for whichever of KimCad's two models is
    missing (the list is fixed server-side — never a caller-supplied name; loopback-only;
    demo mode refused; disk pre-checked on the OLLAMA_MODELS drive before gigabytes move),
    with per-model progress, friendly failures (disk-full names the fix), the honest
    intermediate state ("designing in words works now"), and a finished pull re-probed so
    "Ready" stays measured. Settings' AI-model card gained the vision-model row, aware of a
    running download.
  - **Internal:** the Stage-9 DesignRegistry transitional aliases flattened on schedule
    (handlers read `reg.<field>` under `reg.lock`; the `_locked` contract is now asserted at
    runtime, making every test a lock-discipline detector); server `log_error` restored to
    the terminal (a silenced override had eaten every 500's promised detail); truthful
    per-path `Allow` headers; CLI `--send` validates the connector BUILDS before the
    multi-minute design run, and CLI errors go to stderr.
  - **Record-keeping:** the Stage 8.5 Slice-10 note "a true G-code toolpath/layer viewer is
    scheduled for Stage 10's direct-print UI" (below) is resolved as **deferred, not
    dropped** — Stage 10's scoped goals (ROADMAP) never included it and it did not ship;
    it's a post-beta candidate if testers ask for layer preview.
  - Stage gate: per-slice `audit-lite` ×4 remediated to 0/0/0/0/0 (a REAL deadlock and a
    REAL vacuous test caught pre-merge); live `/walkthrough` clean (zero findings); 5-role
    `audit-team` (36 findings: 0/0/10/21/5) fully remediated to 0/0/0/0/0 — package in
    `docs/audits/stage-10/`.
- **Stage 9 — Image & sketch on-ramps on a working local vision model — DONE (merged to `main`,
  tagged `stage-9`).**
  - **⚠ Setup-requirements change (upgrading from `stage-8.5`):** KimCad now needs a SECOND local
    model — `ollama pull qwen2.5vl:3b` (~3.2 GB) — for the photo and sketch on-ramps. Designing in
    words works without it; the wizard, health pill, `kimcad models`, and both image endpoints all
    say so with the exact pull command if it's missing.
  - **Fixed (Critical): the photo on-ramp never worked against the real model.** gemma4:e4b's
    vision is broken on this stack — identical deterministic hallucination for any image, and "no
    visible image was provided" with thinking enabled (measured; harness committed at
    `scripts/bench_vision.py`, evidence in `docs/benchmarks/stage-9-vision-onramps.md`). Every
    working Stage 8.5 photo impression came from demo mode — this corrects the Stage 8.5 entry's
    "reads a photo with gemma4:e4b's local vision" line below. Images are now read by a dedicated
    small local vision model (`llm.vision_model`, default `qwen2.5vl:3b`, config-overridable):
    5/5 end-to-end sketch read in ~28 s on the target CPU.
  - **New: the "start from a sketch" on-ramp** (`POST /api/sketch-seed` + the SPA affordance beside
    the photo one, on the landing page and in the workspace). A dimensioned sketch reads shape +
    the written sizes **as written** (a photo's sizes stay estimates); same editable-seed confirm
    flow, same local-only promise, same 12 MB cap. Guide: `docs/guide-photo-onramp.md` (now covers
    both on-ramps).
  - **Trust boundary hardened:** a structural loopback-only guard refuses to send an image to any
    non-local host (the local-only promise is enforced in the transport, not just by configuration),
    and the vision read has typed failures — a missing model returns `model_unavailable` + the pull
    command (never "your image was unreadable"); a non-404 read error maps to a friendly try-again
    message. `/api/model-status` reports the vision model alongside the design model.
  - **Photo→3D mesh reconstruction descoped** for this hardware after evaluation — ROADMAP Stage 9's
    "honestly marked not-viable" exit branch, taken with the measurements in the benchmark doc.
  - **Internal: `DesignRegistry`** (`src/kimcad/design_registry.py`) extracts the web layer's
    per-design state + its three locking protocols (lockstep eviction, LRU caps, the
    geometry-version stale-slice guard) out of the webapp closure into a tested class.
  - Stage gate: per-slice `audit-lite` 0/0/0/0/0; live `/walkthrough` (real browser, real vision
    model) clean; 5-role `audit-team` (32 findings: 0 Blocker / 0 Critical / 10 Major / 17 Minor /
    5 Nit) fully remediated to 0/0/0/0/0 — package in `docs/audits/stage-9/`.
- **Stage A — first-run hardening (beta-readiness remediation, 2026-06-10).** The most likely
  non-developer first-run failures now end in one friendly, actionable line on every surface —
  never a traceback or a silent multi-minute hang. Typed `ToolMissingError` (new
  `src/kimcad/errors.py`) for never-fetched OpenSCAD/OrcaSlicer, checked before any subprocess
  spawn and **before profile resolution**; CLI model-down fail-fast (a first-attempt connection
  error + a failed 2 s TCP probe of a *local* backend aborts immediately — measured live at ~20 s
  vs ~234 s before; cloud hosts are never probe-judged), with the OpenAI client at `max_retries=0`
  and a 5 s connect / `timeout_s` read split; live CLI phase output (`Planning the shape...`);
  port-in-use → friendly `--port` hint, with the server now binding **exclusively** on Windows so
  a second instance can't silently share the port; web: typed `model_unavailable` /
  `tool_missing` responses (design, slice, photo-seed, sketch-seed) and generic 500s that never
  leak exception class names; `bench`/`bakeoff` abort with the friendly model-down message instead
  of swallowing it per-case. UX: the first-run wizard recap tells the truth ("Almost ready" + the
  fix + an in-place re-check when the model isn't usable) and the Landing gets a warn-only
  model-health pill; both use persistently-mounted live regions (reliable screen-reader
  announcements, no focus loss on "Check again"). Docs: `docs/getting-started-windows.md` +
  `docs/troubleshooting.md` (non-developer Windows path, DOC-001/DOC-004), root `LICENSE`
  (Apache-2.0) + `SECURITY.md`, committed `requirements.lock` (verified cp313 pin set), the
  OpenSCAD fetch now sha256-pinned. CI: the authoritative gate runs on a **self-hosted runner on
  the target box** (full suite incl. the live OpenSCAD/OrcaSlicer/CadQuery tests — 18 executed,
  zero skips, asserted in CI), plus `pip-audit --strict` on the lockfile; `pull_request` triggers
  removed (self-hosted fork-RCE guard). Gate: per-slice audit-lite at 0/0/0/0/0, a live
  walkthrough against a genuinely stopped Ollama, and the 5-role audit-team stage gate with all
  42 findings remediated to 0/0/0/0/0 (`docs/audits/stage-a/audit-team-2026-06-10/`).
- **Stage 8 — CadQuery parallel geometry backend — DONE (merged to `main`, tagged `stage-8`).**
  A second,
  type-safe CAD backend that runs alongside OpenSCAD as a **mutual fallback** (when the OpenSCAD
  path can't render a part that passes the printability gate, KimCad generates it in CadQuery and
  keeps the better result — the union lifts the done-gate) and adds **editable STEP (BREP)
  export**, which OpenSCAD can't produce. CadQuery's OCCT kernel has no Python-3.14 wheels and the
  app runs on 3.14, so the backend runs **out of process** on a ≤3.13 interpreter
  (`kimcad.cadquery_worker`), shelled out like OpenSCAD/OrcaSlicer/PrintProof3D — optional and
  gracefully absent (no interpreter → backend off, OpenSCAD unchanged). Built in 5 slices, each
  through the real `audit-lite` (independent agent) with every finding remediated
  (`docs/audits/stage-8/`); the Slice-1 audit caught and the fix closed a real sandbox escape
  (`cq.exporters.os.system(...)` pivoting through the injected cadquery module — now neutralized by
  a geometry-only facade + an `ast` block-list). The 5-role `audit-team` stage gate (7 Major /
  16 Minor / 11 Nit, all remediated) + two independent re-audit lanes closed at 0/0/0/0/0; merged
  to `main` and tagged `stage-8`.
  - **Worker + runner:** the untrusted generated CadQuery is statically sanitized (`ast`
    block-list: non-cadquery/math imports, banned names/attrs, all dunders incl. string-subscripts
    + frame/`__globals__` introspection) and run in the worker with restricted builtins (an
    `__import__` that yields the geometry-only cadquery facade / `math` and raises ImportError for
    all else) against a geometry-only facade (every top-level cadquery submodule stripped); the
    script assigns `result` and does no I/O — the worker exports STL (+ STEP) to a result file
    (never stdout), in an isolated cwd with a secret-scrubbed env, with a timeout + output-size
    guard. OS-level process confinement is a tracked Stage-11 hardening.
  - **Discovery + config:** `binaries.cadquery_python` (null=auto-discover / false=off / a path),
    `limits.cadquery_timeout_s` (120s).
  - **Mutual fallback:** `generate_cadquery` + `prompts/system_cadquery.md`; OpenSCAD stays primary;
    the report/result carry the producing `backend`.
  - **STEP export:** `GET /api/step/<id>` + a "Download editable CAD (.STEP)" link for a CadQuery
    part (the as-designed geometry; print orientation applies only to the printable mesh).
  - **Docs + bench:** `docs/cadquery-backend.md` and a deterministic engine bench
    (`kimcad.cadquery_bench`, `docs/benchmarks/stage-8-cadquery-backend.md`).
- **Stage 8.5 — Usability — DONE (merged to `main`, tagged `stage-8.5`).** All 11 slices shipped and
  the stage gate passed both lanes: the runtime **wiring-audit** (drove the live app — every control
  proven genuinely wired + persisted) and the 5-role **audit-team**, which rolled up 42 findings
  (0 Blocker / 0 Critical / 11 Major / 20 Minor / 11 Nit). Every finding was fixed — including two
  real safety bugs (a slice/re-render geometry-version race that could serve a stale-shape print, and
  reopen/import trusting a stored gate verdict instead of re-validating the mesh), each with a
  regression test — then independently re-audited twice to **0/0/0/0/0** across all five lanes
  (`docs/audits/stage-8.5/stage-gate-2026-06-05/`). Final: 763 pytest (non-live) + 4 live OrcaSlicer
  + 262 vitest; ruff clean; SPA build byte-reproducible. The slices, beyond 1–7 below:
  - **Slice 8 — problems on the model:** PrintProof3D's flagged regions are highlighted in the 3D
    viewport (overhangs / poor bed contact), with click-a-risk-to-focus and a legend/toggle.
  - **Slice 9 — onboarding / model-down / progress / help:** a recoverable "your local AI isn't
    running" wall, live step-progress (planning → generating → rendering → validating), a first-run
    setup wizard, and in-app glossary "(i)" tips. gemma4:e4b is THE model throughout (never qwen).
  - **Slice 10 — output clarity + print preview:** the slice estimate broken out (time / layers /
    filament length + weight; weight estimated from volume × material density when the profile reports
    none, labeled as such), a "design → print file" framing, named print file + copy-link, and clear
    export formats. (A true G-code toolpath/layer viewer is scheduled for Stage 10's direct-print UI.)
  - **Slice 11 — responsive / a11y / copy / polish:** keyboard shortcuts + a discoverable "?" help
    modal, plain-English copy, the right-column visual hierarchy + icon-tile printability checks
    restored, refine-by-talking chips, an always-on printer-status chip, and a mobile sticky CTA.
- **Stage 8.5 — escape paths on every action:** every long or
  blocking action is now cancelable, so the app never traps you. The "Designing your part…" screen
  shows an honest "this runs on your computer's AI — it can take a few minutes" note, a live elapsed
  timer, and a **Cancel** (plus Esc); the photo "Reading…" read, slicing, and importing each get a
  **Cancel** that aborts the request and returns you to the prior control with no error. Requests are
  abortable end to end (an AbortSignal threaded through the API client).
- **Stage 8.5 Slice 7 — "describe with a photo" on-ramp:** a
  secondary affordance on the landing + workspace reads a photo with gemma4:e4b's **local** vision
  into a rough, editable text seed that pre-fills the existing text→DesignPlan path. It's a starting
  point, never a "photo → finished part" promise: the user confirms/edits the seed (a photo carries
  no scale, so sizes are estimates) before anything runs. The photo is read locally and **never
  auto-sends off the machine** (vision is pinned to the local provider even when cloud TEXT is on),
  is never persisted, and never logged; an unreadable/oversized photo is a clean 422/413, never a
  500. New `POST /api/photo-seed` + `LLMProvider.describe_photo` (Ollama's native `/api/chat` with
  `think:false`).
- **Stage 8.5 Slice 6 — in-app Settings screen:** model status
  (gemma4:e4b, local, with a health line — no menu of alternatives), an off-by-default **cloud
  opt-in** via OpenRouter (the user picks the model; the API key is a normal Settings field, saved
  locally and shown masked to the last few characters, never echoed back in full or stored in the
  repo/logs), an off-by-default **experimental raw-codegen generator** (sandboxed, never bypasses the
  Printability Gate, offered inline on an out-of-template request), plus tools health + about + a
  two-step reset. New `settings_store.py`, `/api/settings`, `/api/model-status`.
- **Stage 8.5 Slices 2–4:** refine a part as a **conversation**
  with full **version history** (a timeline with step-back/undo + a "what changed" compare);
  **numeric parameter entry** alongside the live sliders; and a **mm / inch units** toggle so a US
  maker isn't walled out. (Gated together by the Slice 2–4 `audit-team` + `wiring-audit` at
  0/0/0/0/0.)
- **Stage 8.5 Slice 1 — local persistence + "My Designs" library:**
  - Designs are saved automatically to a local, best-effort store under `~/.kimcad/designs/<id>/`
    (`meta.json` + `mesh.stl` + `thumb.png`) — never the repo, nothing leaves the machine. A built
    part auto-saves and the SPA routes to `#/design/<id>`, so a refresh restores the part + its
    live sliders instead of losing the work.
  - A **My Designs** gallery (`#/designs`): thumbnail grid with reopen, inline rename, duplicate,
    two-step delete, search by name, and sort (newest / oldest / name). Reopen re-registers the
    design into the live loop so its template sliders work again.
  - **Export / import** a design as a portable `.kimcad` zip (zip-slip-safe — only the three known
    files are read by exact name; a bounded inflated-read rejects a decompression bomb; the
    compressed upload is capped at 32 MiB).
  - A new `design_store.py` module (`DesignStore`) and `config.paths.designs`; new
    `/api/designs*` endpoints (list / save / reopen / thumb / export / import / rename / delete /
    duplicate). Writes are serialized + atomic (with a Windows `os.replace` retry); a save indicator
    in the Topbar surfaces "Saving… / Saved / retrying."
- **Stage 6 — model layer (merged + tagged `stage-6`):**
  - `kimcad models` — a hardware/availability-aware model advisor: probes RAM/CPU/GPU and the
    installed Ollama models and recommends the best one that fits, names an upgrade to pull, and
    surfaces a non-China alternative when the pick is China-origin. Advisory only — it never
    rewrites config; the model stays choosable.
  - Tiered LLM fallback (`FallbackProvider`): a primary connection/timeout/model-not-found error
    transparently retries an opt-in alt backend (`llm.alt_backend`, off by default).
  - Richer 3-axis benchmark grading (slices-clean / matches-request / correct-dimensions) layered
    on the completion done-gate, and `kimcad bakeoff` — a model bake-off that runs the benchmark
    per backend and recommends switch-or-keep (recommend only; flipping the default is a human call).
  - Plan-failure robustness: a model returning un-parseable output fails clean (`plan_failed`,
    CLI exit 6) instead of a raw traceback.
  - **Decision:** the `Qwen2.5-Coder 1.5B` candidate was evaluated via the live bake-off and
    **rejected** (0/10 — it can't produce a design plan); **`gemma4:e4b` stays the default.**
    A `local_qwen` backend is defined for the comparison and remains selectable via `--backend`.
- Project scaffold: src-layout package, configuration loader, dependency manifest,
  cross-platform line-ending normalization.
- Default configuration with Bambu P2S (reference) and Elegoo Neptune 4 Max printer
  profiles, four materials (PLA/PETG/TPU/ABS), and per-machine override via
  `config/local.yaml`.
- Design-Plan IR (Pydantic v2) with minimal single-question clarification.
- Provider-agnostic LLM layer over the OpenAI SDK — local Ollama / LM Studio,
  DeepSeek, and any OpenAI-compatible endpoint.
- Local-first posture: defaults to a local runtime (Ollama, `gemma4:e4b`); cloud
  backends are opt-in via `config/local.yaml`, no API key required out of the box.
- OpenSCAD code-generation system prompt and a five-file seed library
  (box, bracket, fasteners, fillets, mounts) injected into the prompt.
- Sandboxed OpenSCAD subprocess runner with native 3MF output (STL fallback).
- Trimesh mesh-validation pipeline and a Printability Gate (pass / warn / fail)
  checking dimensions, manifoldness, build-volume fit, and minimum wall thickness.
- Auto-orientation onto the most stable facet before slicing.
- OrcaSlicer CLI integration producing a validated print job and print report.
- Pipeline orchestrator (prompt → plan → code → render → validate → gate → orient →
  slice) and a `kimcad` CLI with `design` and `bench` verbs.
- Phase-1 benchmark harness — the ten Appendix B done-gate prompts
  (`bench/prompts.yaml`) scored against the §4.2 0.8 threshold.
- Cross-platform tools-fetch script (`scripts/fetch_tools.py`, standard library only),
  now with SHA-256 checksum verification (trust-on-first-fetch, then tamper-checked).
- Verified, checksum-pinned Windows OrcaSlicer build (v2.4.0-alpha) with end-to-end
  slice proof: a real generated part slices to a valid G-code-bearing 3MF on the
  Bambu P2S profile.
- Parametric library expansion — eight new modules across five new files covering the
  Appendix-B part families that previously had to be hand-built: wall and pegboard hooks
  (hooks.scad), cable clip (clips.scad), closed box / two-part enclosure / tube
  (containers.scad), spool holder (holders.scad), and drawer divider (organizers.scad).
  That brings the library to ten .scad files in all. Each module renders watertight at an
  exact, documented bounding box, with render and contract tests.
- Phase-2 web UI first slice (`kimcad web`): a dependency-free local browser app —
  describe → design plan → printability verdict → target-vs-actual dimensions → 3D preview
  — driven by the real pipeline. `--demo` serves a sample part with no model call.
- Deterministic code-generation repairs in the runner: missing library `use` includes are
  auto-injected, and a dropped trailing statement terminator is auto-added.
- Per-case benchmark artifact persistence (plan, report, outcome) for offline diagnosis.
- LLM resilience for a flaky local server: configurable per-request timeout, automatic
  retry on connection/timeout errors, and `scripts/ollama_watchdog.py`.
- Local CI: a pre-push hook (`.githooks/pre-push` → `scripts/ci.sh`) runs ruff + pytest.

#### Stage 1 — gated G-code export / print loop
- OrcaSlicer profile resolution: a configured printer + material maps to the three
  on-disk profile JSONs (machine / process / filament) under the shipped
  `resources/profiles` tree, with a `Generic <MATERIAL>` filament fallback. Replaces the
  former "known unknown" name→path placeholder. *(The generic cross-vendor fallback was
  later removed in Stage 3 — a name now resolves only against its own printer's profiles,
  to prevent a wrong-vendor mis-slice; see the Stage 3 entry.)*
- Slicing wired into the pipeline behind explicit print confirmation. `slice_model`
  now **proves** the exported 3MF carries real motion-bearing G-code (not just that a
  file was written), streaming the embedded toolpath to stay within the memory budget.
- CLI `--slice`: the explicit print confirmation. It announces the printer + material
  and the exact profiles to be used, then the report shows the proven G-code line count
  and the profiles actually used. Without `--slice`, nothing is sliced.
- Web send-to-printer: printer/material selectors (each flagged sliceable), an explicit
  confirmation step, `POST /api/slice/<id>` that slices the already-validated mesh (no
  model re-run), and `GET /api/gcode/<id>` to download the proven 3MF. The validated 3D
  model is always downloadable as the export fallback.
- Manifold3D pre-slice mesh hardening: the oriented mesh is round-tripped into a
  guaranteed 2-manifold before export/slice; optional at runtime (skipped, with a note,
  if `manifold3d` is absent). New dependency `manifold3d>=3.0` (installed by default; see
  the note at the top of this section).
- Bambu A1 printer profile added (one of Kim's printers).

#### Stage 2 — send-to-printer connector + MCP (software-complete, hardware-deferred)
- `PrinterConnector` abstraction (`printer_connector.py`): a `Protocol` covering
  capabilities / status / send / job-status, with a frozen `PrinterCapabilities` /
  `PrinterStatus` / `PrintJob` model and a shared `ensure_sendable()` gate. A built-in
  thread-safe `LoopbackConnector` (the **`mock`** connector) drives the whole send path
  in-memory, so every layer above can be tested with no hardware.
- OctoPrint connector (`octoprint_connector.py`): a real REST connector over stdlib
  `urllib` with an `X-Api-Key` header; the API key is read from an environment variable
  only — never stored in config and never logged. A reachable-but-rejected printer
  (401/403) surfaces as a distinct `AuthError`, not a generic "offline." Single-plate
  G-code is extracted with a hard size cap.
- Runnable mock OctoPrint server (`python -m kimcad.mock_printer`): a stdlib
  `http.server` implementing the version / printerprofiles / printer / files / job
  endpoints with API-key auth, so the OctoPrint connector is exercised end-to-end with
  no real printer.
- Capability reconciliation (`capability.py`): a printer's reported build volume /
  nozzle / materials auto-fills a **blank** profile field, and any config-vs-printer
  disagreement is flagged (config stays authoritative; the mismatch is surfaced, with the
  actual numbers, never silently overridden). A blank build-volume field now skips the
  build-plate-fit check with a `WARN` note (instead of failing); a blank nozzle skips the
  wall-thickness check (nothing to warn against, so no note).
- Connector config + factory: a `connectors:` block in `config/default.yaml`, a
  `build_connector(config, name)` factory, and clear errors for an unknown connector name,
  unknown type, or missing base-url / API-key env var (the factory names the missing env
  var, never its value).
- CLI `--send <connector>`: slices (the flag implies slicing) and sends behind the
  explicit-confirmation gate; an offline/unreachable printer is reported and the proven
  G-code is left on disk. A part that **failed** the printability gate is never sent — even
  with `--proceed-anyway`, which only exports it for inspection. A simulated (loopback)
  connection is labeled as such ("no real printer was used") rather than reported as a print.
- Web send-to-printer: after a successful slice, a connection selector + an explicit
  confirm step (`GET /api/connectors`, `POST /api/send/<id>`); the result surfaces the
  job + printer status, and the download stays as the fallback. Each connection is flagged
  `simulated` so the UI labels a no-hardware connection honestly (the confirm + success copy
  say plainly when a send is a simulation); a soft failure carries a typed `reason` plus a
  user-facing note (never the raw developer detail).
- Printer MCP server (`python -m kimcad.mcp_server`): a dependency-free MCP server
  (newline-delimited JSON-RPC 2.0 over stdio) exposing `list_connectors` /
  `printer_status` / `printer_capabilities` / `send_print`, so an agent can drive the
  printer. `send_print` passes the confirm value through to the same `confirm is True`
  gate without coercion — a truthy-but-not-`True` value cannot send.

#### Stage 3 — printer coverage + connector honesty (software-complete, hardware-deferred)
- Moonraker (Klipper) connector (`moonraker_connector.py`) + a runnable mock Moonraker server
  (`python -m kimcad.mock_moonraker`) — covers Creality-Klipper / Voron / RatRig / Mainsail /
  Fluidd. Optional `X-Api-Key`; an unrecognized Klipper state maps to `error`, never a false
  "ready."
- PrusaLink (Prusa) connector (`prusalink_connector.py`) + a mock PrusaLink server
  (`python -m kimcad.mock_prusalink`) — covers MK4 / MK3.9 / MINI / XL. Uploads via
  `PUT /api/v1/files/<storage>/<name>` with the path segments percent-encoded and
  `Print-After-Upload`; a 409 surfaces as a typed `busy`. Configurable `storage` (default `usb`).
- Per-printer, per-material filament profiles, honestly: every printer is offered only the
  materials it has a verified profile for. The cross-vendor `Generic <MATERIAL>` fallback was
  **removed** (it silently mis-resolved e.g. Elegoo + TPU to a Bambu profile); the Elegoo
  Neptune 4 Max genuinely ships no TPU profile, so TPU is reported "not available" for it.
  `/api/options` reports each printer's available materials, and the web UI explains which are
  hidden and why.
- Live **ready / not-ready connection status** (`GET /api/connector-status/<name>`): a badge for
  ready / busy / offline / needs-setup / simulation that never 5xxes and never leaks a credential.
- Connection-status + send **honesty hardening** (independent-audit gate fixes): a typed `reason`
  vocabulary (`config` / `unknown` / `auth` / `offline` / `busy` / `bad_response` / `error`)
  carried on both `/api/connector-status/<name>` and `/api/send/<id>` soft failures (each with a `simulated`
  flag); a rejected credential on a large upload is reported as `auth` rather than mislabeled
  "offline" (a mid-write socket reset is re-probed); a non-JSON HTTP-200 response degrades to an
  error status instead of raising; and the status line is an ARIA live region mapped onto the
  app's green/amber/red scale.

#### Stage 4 — React/TypeScript SPA shell + Three.js viewport + wired flow
- The browser UI is now a **React + TypeScript + Vite single-page app** (`frontend/`), compiled
  to plain static files committed under `src/kimcad/web/` and served by the same dependency-free
  stdlib `http.server` (shell at `/`, bundles at `/assets/<file>` behind a plain-filename-only
  traversal guard). **Node/Vite are build-time only** — `kimcad web` runs with no Node toolchain.
  This **replaces the earlier vanilla-HTML/JS page** (and that page's in-browser send controls).
- **Workshop design system** (the v3.0 design tokens) with self-hosted, latin-only variable fonts
  bundled for fully offline use (no CDN); a topbar + landing + a three-column workspace that
  stacks on mobile.
- A **vanilla Three.js viewport** (`KCViewport`) that loads and displays the REAL exported
  `*.oriented.stl` from `GET /api/mesh/<id>` (orbit / zoom / auto-rotate; three.js is code-split
  and lazy-loaded).
- The text → plan → gate → slice → download flow wired through the SPA: the conversation, the
  plan summary, the printability report (target-vs-actual dimensions + findings), printer/material
  selectors, gate-aware **Slice & prepare** (`POST /api/slice/<id>`), G-code + model download, and
  a **read-only** ready/not-ready connection badge.
- **Sending to a printer from the browser is intentionally deferred to a later stage** — the SPA
  does status + slice + download only; the CLI (`--send`) and the MCP server remain the send paths.
  (This supersedes the Stage-2 "Web send-to-printer" item above, which belonged to the now-removed
  vanilla UI.)
- Tooling/tests: a **vitest** unit harness for the SPA's pure logic (wired into `scripts/ci.sh`),
  frontend↔backend field-contract tests against the TypeScript source, and a build that the
  Python server-side tests gate (shell + `/assets/` serving + traversal rejection).

#### Stage 5 — deterministic template engine + live sliders
- **Deterministic template engine** (`templates.py`): a registry of seven parametric families
  (`snap_box`, `box`, `enclosure`, `tube`, `wall_hook`, `cable_clip`, `drawer_divider`) over the
  proven `library/` modules. A template-covered `object_type` builds **with no model call** — the
  OpenSCAD is emitted by pure, injection-safe string substitution and the gate target is the
  family's analytic bounding box. Typed, range-bounded parameters; values clamped to range with
  ordering constraints (a tube's bore stays inside its wall); alias/plural/case-normalized matching
  with a duplicate-alias guard. LLM-written OpenSCAD stays the fallback for uncovered types.
- **Pipeline tiering + the re-render path** (`pipeline.py`): a template match builds in one shot
  (no retry, no model — a too-wrong part fails closed, fixed by a parameter not by regenerating).
  `Pipeline.rerender(base_plan, family, values, …)` re-emits + renders + gates at new values with
  no model and no prompt, sharing the orient/harden/export tail with `run`.
- **Live re-render API** (`webapp.py`): `/api/design` now returns the `template` family name + the
  typed `parameters` snapshot; `POST /api/render/<id>` deterministically re-renders at new
  `{values}` (no model), returns the clamped values + a **versioned** (cache-busted) `mesh_url`,
  **invalidates** the cached slice/G-code for that id, and serializes concurrent re-renders — so a
  stale shape can never be sliced or sent.
- **Live parameter sliders in the SPA** (`RightPanel.tsx` et al.): a slider per backend parameter
  for template-backed designs; a drag updates immediately and debounces (~150 ms) a re-render, then
  the viewport reloads the versioned mesh while the previous one stays on screen and the
  gate/report/values update from server truth (a stale response can't clobber newer geometry).
  LLM-backed parts have no parameters and stay read-only. Sliders are labelled, mono-valued with
  units, and `aria-valuetext`-announced; the touch target fattens on mobile.
- **Deterministic-template benchmark/proof** (`template_bench.py`, `python -m kimcad.template_bench`):
  every family re-renders through the real pipeline path watertight at its declared envelope, with
  no model call, **well under the <1 s interactive target** (the automated gate asserts a
  conservative ≤5 s per-family ceiling so it stays hardware-independent; the exact per-family
  timings are in `docs/benchmarks/stage-5-template-families.md`).

#### Stage 7 — Smart Mesh + PrintProof3D + readiness report (merged + tagged `stage-7`)
- **Smart Mesh readiness synthesis** (`smart_mesh.py`): a pure `assess_readiness(gate, mesh_report,
  …, printproof=…)` that folds KimCad's Printability Gate, the mesh integrity stats, and an
  *optional* PrintProof3D report into one verdict — a 0–100 score, a plain verdict, a confidence,
  the risks, and concrete recommendations. The verdict tone is the **worst** of KimCad's own
  assessment and PrintProof3D's status, so the card is never more optimistic than either signal.
- **PrintProof3D arm's-length integration** (`printproof3d.py`): the owner's MIT Rust validation
  **engine** is run as a subprocess — never linked — to validate a rendered mesh; its
  `ValidationReport` JSON is parsed into a typed report Smart Mesh consumes. Best-effort and
  injection-safe: a missing/un-built engine, a profile error, or an unparseable report all degrade
  to "no engine" (Smart Mesh falls back to the gate, honestly at lower confidence) and **never
  raise**. KimCad generates the engine's printer/material profile JSON from its own config.
- **Pipeline + design-API wiring** (`pipeline.py`, `webapp.py`): every built part now carries a
  `MeshReadiness` (on the report, so both the completed and gate-failed paths expose it), computed
  on the final hardened mesh — **bed-positioned** on a copy before PrintProof3D validation. The
  deterministic slice gate is unchanged; readiness is advisory. `/api/design` + `/api/render`
  expose a `readiness` block; the live-slider re-render recomputes a fast gate-only readiness
  (the engine isn't re-run per drag).
- **Readiness report card** (`RightPanel.tsx`, matching the design at
  `docs/design/screens/10-smartmesh-report.png`): a designed card on the design screen — an SVG
  score gauge, the verdict, a confidence badge that names what backed it (gate vs engine), a risks
  list (with a non-color severity cue), a recommendations list, an optional history line, and an
  honest "via …" attribution. The Printability badge is reframed ("Gate: passed / needs review /
  failed") so it doesn't duplicate the readiness headline.
- **Smart Mesh learning store** (`history.py`): a local-first, best-effort JSON record of built
  parts (coarse — no geometry/prompt; default `~/.kimcad/history.json`, never the repo) that adds an
  honest "compared to your past parts" line to the card. Strictly factual — "a personal best" needs
  a strict beat of every prior, a tie reads "on par" not "below," and no history shows no line.
  Recorded once per fresh design, never on a slider drag.
- **Config:** optional `binaries.printproof3d` (the engine path; absent → degrade) and
  `paths.history` (relocate the learning store) — both documented in `config/default.yaml`.

### Changed
- Default local model is now `gemma4:e4b` (sized for a 32 GB / 780M-iGPU target — stable
  and fast there); `gemma3:12b` was too large for the target and is no longer used.
- Printability Gate: a non-watertight mesh is now a hard **fail** (previously detected but
  not gated), and the dimensional-match tolerance is a flat 0.5 mm with no percentage term.
- Design-plan and code-generation prompts steer the model to compose library modules and
  commit envelopes that match each module's documented bounding box.

### Fixed
- Code generation no longer misuses the walled-container `box()` module as a solid
  primitive; the system prompt and library manifest now steer plain solids to
  OpenSCAD built-ins, guarded by regression tests.
- Benchmark robustness: the planner no longer over-asks clarifications on already-sized
  parts, recoverable-but-invalid LLM JSON is normalized instead of crashing, and a
  dimensional failure is fed back to the model for a corrected attempt.
- Wall-hook envelope axis order made explicit (fixes an X/Y/Z swap); generated code may no
  longer assign geometry to a variable (an OpenSCAD syntax error).

### Notes
- The OrcaSlicer pin is v2.4.0-alpha, not 2.3.2 "stable": 2.3.2 is the only stable
  release carrying the Bambu P2S profile, but it segfaults on every CLI slice on a
  GPU-less machine (upstream issue #12906). 2.4.0-alpha fixes that and ships the same
  P2S profile, so it is pinned until a 2.4.x stable with the fix is released.
- Printer sliceability: all three of Kim's printers — Bambu P2S, Bambu A1, and Elegoo
  Neptune 4 Max — are fully sliceable (machine + process + filament profiles all ship)
  and proven end to end against the bundled OrcaSlicer. The Elegoo's process profiles
  ship under the name `Neptune4Max` (no spaces, nested under `process/EN4SERIES/`) while
  its machine profile uses `Neptune 4 Max` (with spaces); resolving the right name was
  the subtlety that an earlier (space-using) search missed.
