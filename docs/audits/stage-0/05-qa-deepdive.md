# 05 — QA Engineer Deep-Dive

**Project:** KimCad — plain-English → printable 3D part pipeline
**Stage:** Stage 0 (pre-merge / pre-tag)
**Role:** QA Engineer (runtime behavior, not static review)
**Date:** 2026-05-30
**Environment:** Windows 11 Pro (10.0.26200), Python 3.14, KimCad CLI at `C:\Users\scott\dev\kimcad\.venv\Scripts\kimcad.exe`, OpenSCAD `tools/openscad/openscad.exe` (43.9 MB), Ollama running (`gemma4:e4b`) but real LLM path deliberately avoided.

I tested the **running product**: the CLI surface, the web UI in `--demo` mode over real HTTP (happy path + adversarial), the binary STL it serves, and the deterministic OpenSCAD render stage exercised directly against the real binary. The Test Engineer audits the test suite; I trust nothing and verify by running.

---

## Summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 4 |
| Nit      | 1 |
| **Total**| **6** |

**No Blockers, no Criticals.** The product runs. The API contract is clean across happy and error paths, the deterministic render stage is fast and correct, and STL bytes served over HTTP are real and well-formed. The headline finding is a **gate false-positive that fires on the demo itself** (and on every fully-closed hollow container) — the first thing a reviewer or user sees is a "stray-geometry mistake" warning on a part that is, in fact, correct.

---

## What I ran (evidence trail)

All commands run from `C:\Users\scott\dev\kimcad`.

1. `./.venv/Scripts/kimcad.exe --help` and `design/web/bench --help` — all clean, accurate usage.
2. `./.venv/Scripts/kimcad.exe web --demo --port 8791 --host 127.0.0.1` (background) — came up, served, then killed cleanly (PID 31912, port confirmed free after).
3. A 12-case HTTP harness via `urllib` against the demo server (GET `/`, GET `/index.html`, POST `/api/design`, GET mesh URL, unknown routes, empty/whitespace/malformed/no-key POST bodies, bad mesh IDs).
4. A 6-case raw-socket harness for wire-level edge cases (malformed `Content-Length`, empty/negative/missing mesh id, path-traversal, missing `Content-Length`).
5. Direct render of `snap_box`, `tube`, `box`, `wall_hook`, and a control cube through `kimcad.openscad_runner.render_scad` with the real binary, then `trimesh` analysis of each mesh.
6. CLI exit-code probes (`--help`=0, no-args=2, bad-subcommand→treated as prompt=3, `design --help`=0).

I triggered the real LLM path exactly **once, inadvertently** — `kimcad frobnicate` normalized to a design prompt and asked Ollama for a clarification (returned in seconds, no full render). See QA-004. No `bench` run was started; no existing port or process was disturbed.

---

## Findings

### QA-001 (Major) — Printability gate flags the demo (and every closed hollow box) as a "stray-geometry mistake"

**Category:** Flow / Correctness (runtime)

**Evidence:**
1. `kimcad web --demo --port 8791`, then `POST /api/design` with `{"prompt":"a small box"}`.
2. Observed response: `report.gate_status: "warn"`, with a finding:
   `{"level":"warn","code":"shells.multiple","message":"2 disconnected bodies — usually a stray-geometry mistake."}`
   — alongside four `pass` findings (watertight, dims match, fits plate, wall ok).
3. The demo emits `snap_box(width=80, depth=60, height=40, wall=2)` from `library/containers.scad` — a single `difference()` of an outer cube minus an inner cube: one closed, hollow box.
4. Rendered that exact snippet through `render_scad` with the real binary. OpenSCAD's own report: **`Simple: yes`**, 16 vertices, **1 CGAL polyhedron**, watertight. So the geometry kernel considers it one simple solid.
5. Loaded the resulting mesh in `trimesh`: `is_watertight=True`, `volume=38784.0`, but `mesh.body_count == 2` and `len(mesh.split(only_watertight=False)) == 2`.
6. Confirmed the gate uses exactly this: `validation._body_count` returns `int(mesh.body_count)` → `printability._check_shells` warns when `report.n_bodies > 1` (`printability.py:207-213`).

**Root cause:** A fully-enclosed hollow solid has **two disconnected surface shells** — the outer skin and the sealed inner cavity skin — that share no edges. `trimesh.body_count` counts surface shells, so it returns 2. But this is *correct, intended* geometry: a sealed box with walls. The gate conflates "2 surface shells" with "2 stray solid bodies / a modeling mistake," so it warns on the canonical-correct output of a container.

**Scope check (ran each through the real binary + trimesh):**
| Module | watertight | bodies | warns? |
|---|---|---|---|
| `snap_box` (closed box) | yes | **2** | **yes (false positive)** |
| `enclosure` (closed, wraps snap_box) | yes | 2 (by construction) | **yes (false positive)** |
| `tube` (open-ended spacer) | yes | 1 | no |
| `box` (open-top container) | yes | 1 | no |
| `wall_hook` (bracket) | yes | 1 | no |
| solid cube (control) | yes | 1 | no |

So the false-positive is specific to **fully-closed hollow solids** — exactly `snap_box` and `enclosure`, the two "sealed container" library modules — and **the demo showcases one of them.**

**Why this matters:** Stage-0 is a merge/tag gate. The single most-visible runtime artifact — the no-LLM demo, the thing a reviewer or first-time user runs to see the product work — returns a `warn` badge and the words "usually a stray-geometry mistake" on a part that is correct. It erodes trust in the gate (the one component whose entire job is trust) and will recur for any real user who asks for a closed box, a sealed enclosure, or any boxed electronics housing. A gate that cries wolf on correct geometry trains users to ignore it — which defeats the printability gate's purpose.

**This is "working as designed but wrong"** — flag belongs to Engineering as well. The check itself is reasonable in intent (stray bodies *are* usually mistakes); the heuristic is just too blunt to distinguish a sealed cavity from a stray body.

**Fix path (suggest):** Distinguish "disconnected solid bodies" from "nested/enclosed shells." Options, in order of preference:
- Test whether the extra shell is **enclosed within** another (a cavity) vs. **disjoint in space** (a true stray body). `trimesh` bounding-box containment or a ray/point-in-volume test on each split component separates a sealed void from a floating chunk. Only warn on genuinely disjoint bodies.
- Alternatively, gate on **positive-volume disjoint components**: split, drop components whose oriented volume is negative (cavities), and warn only if ≥2 positive-volume components remain spatially separated.
- At minimum (cheap interim), soften the copy so it doesn't assert "mistake" on watertight parts, and special-case the library's own closed-container modules so the demo is clean.

**Blast radius:**
- Adjacent code: `src/kimcad/printability.py::_check_shells` (the heuristic), `src/kimcad/validation.py::_body_count` (the count source). One fix point each.
- Shared state: `MeshReport.n_bodies` is consumed by the gate, the CLI text report (`report.to_text()`), and the web payload (`_report_payload` → UI findings list). Changing what `n_bodies` *means* ripples to all three surfaces; prefer adding a distinct "disjoint stray bodies" measure rather than redefining `n_bodies`.
- User-facing: every closed-container design flips from `warn` to `pass` (or a quieter info note). The web demo badge changes from `warn` to `pass`. The CLI report drops the warning line.
- Migration: none (no stored data).
- Tests to update: any unit test asserting `snap_box`/`enclosure` produces a `shells.multiple` warn, or asserting `n_bodies == 2` is a warning condition. (Test-suite-side ownership belongs to the Test Engineer; QA notes the dependency.)
- Related findings: QA-002 (demo badge), and Engineering's gate-heuristic findings if any.

---

### QA-002 (Minor) — `--demo` mode (the showcase path) ships a `warn` badge, not a clean `pass`

**Category:** Flow / UX-runtime

**Evidence:** Same run as QA-001. The demo is meant to "exercise real geometry in under a second" to demonstrate the product (per `webapp.py::DemoProvider` docstring). What it actually demonstrates is a `warn` verdict. The 3D preview, dims table, and STL all render correctly, but the gate badge is amber with a "mistake" finding.

**Why this matters:** A demo's job is to put the product's best foot forward. An amber "stray-geometry mistake" on the canned sample undercuts that, and a reviewer skimming the demo could reasonably conclude the gate is broken (it isn't — it's over-eager, per QA-001).

**Fix path:** Resolved for free once QA-001 lands (the false-positive disappears). If QA-001 is deferred, switch the demo provider's library call to a module that renders as a single body — e.g. the open-top `box(...)` or `tube(...)` — so the showcase is a clean `pass`. This is a one-line change in `webapp.py::DemoProvider.generate_openscad`.

**Blast radius:**
- Adjacent code: `src/kimcad/webapp.py::DemoProvider` only.
- User-facing: demo badge goes green.
- Migration / tests: none material.
- Related findings: QA-001 (root cause).

---

### QA-003 (Minor) — Malformed `Content-Length` header crashes the request thread; client gets a connection reset, not a clean 400

**Category:** API / Robustness

**Evidence:**
1. Raw socket POST to `/api/design` with header `Content-Length: abc` and body `{"prompt":"box"}`.
2. Observed: **empty response, connection reset** (0 bytes read by the client).
3. Server console (captured from the backgrounded demo process) showed the exact traceback:
   ```
   File "C:\Users\scott\dev\kimcad\src\kimcad\webapp.py", line 178, in do_POST
       length = int(self.headers.get("Content-Length") or 0)
   ValueError: invalid literal for int() with base 10: 'abc'
   ```
4. `webapp.py:178` (`length = int(...)`) sits **outside** the `try` block that begins at line 179, so the `ValueError` escapes `do_POST`, the handler thread dies, and stdlib resets the connection without sending a response.

**Why this matters:** The handler's own comment (line 192) promises "never leak a traceback to the browser." This input path violates the spirit of that: a malformed header produces an unhandled exception, a stack trace dumped to the server console, and a bare connection reset to the client instead of the clean `400 {"error": ...}` every other bad-input path returns. Real browsers always send a numeric `Content-Length`, so the exposure is low — this bites a buggy/crafted client or a proxy, not the normal UI. Hence Minor, not higher. But it's an unhandled exception on a public-ish input surface, and the server is localhost-only by design (`config: host 127.0.0.1`), which further caps the blast radius.

**Fix path (suggest):** Move the `int(...)` inside the existing `try/except (ValueError, TypeError)` at lines 179-184, or wrap it: parse `Content-Length` defensively and return `400 {"error":"invalid request body"}` on a non-numeric value, matching the malformed-JSON path.

**Blast radius:**
- Adjacent code: `src/kimcad/webapp.py::Handler.do_POST` (lines 174-199). Single function.
- Shared state: none.
- User-facing: malformed-header requests now get a structured 400 instead of a reset; no change for legitimate clients.
- Migration / tests: add a unit/integration test for a non-numeric `Content-Length` (currently uncovered — Test Engineer dependency).
- Related findings: none.

---

### QA-004 (Minor) — Typo'd subcommands silently become design prompts (no "unknown command" path)

**Category:** CLI / UX-runtime

**Evidence:**
1. `kimcad frobnicate` did **not** error. `_normalize_argv` (`cli.py:88-92`) rewrites any first-arg that isn't in `{design,bench,web}` and doesn't start with `-` into `["design", <arg>]`.
2. So `frobnicate` became the prompt "frobnicate", invoked the real pipeline, and printed:
   `I need one detail before building:\n  Please provide a detailed description...` (exit code 3).
3. By the same rule, `kimcad benhc`, `kimcad wbe`, `kimcad desgin` etc. all become **real LLM design runs on the typo** — minutes of CPU on the slow on-device model, or a clarification round-trip — with no "did you mean bench?" signal.

**Why this matters:** The bare-prompt convenience (`kimcad "a wall bracket"` → `design`) is a deliberate, documented feature (cli.py docstring, README) and is good UX. The side effect is that there is **no way to get an unknown-command error** — a fat-fingered verb is indistinguishable from a one-word prompt, so a typo silently spends real compute instead of failing fast. Low severity because the bare-prompt feature is intended and the cost is bounded (clarification usually short-circuits), but it's a genuine footgun for a CLI whose other verbs are slow.

**Fix path (suggest):** Keep bare-prompt support, but treat a **single bare token that resembles a known verb** (small edit-distance to `bench`/`web`/`design`, or a lone alphanumeric word with no spaces) as a likely typo and prompt "Did you mean `bench`? To design a part, quote a full description." Low effort; preserves the feature while closing the footgun.

**Blast radius:**
- Adjacent code: `src/kimcad/cli.py::_normalize_argv`. Single function.
- User-facing: typo'd verbs get a hint instead of a silent LLM run; legitimate one-word prompts (rare, since prompts are descriptive) would need a way through — keep that in mind in the heuristic.
- Migration / tests: add coverage for the typo case.
- Related findings: none.

---

### QA-005 (Minor) — `config/default.yaml` `server:` block (host/port 8080) is dead config; the CLI ignores it

**Category:** Config / Consistency

**Evidence:**
1. `config/default.yaml` defines `server: { host: "127.0.0.1", port: 8080 }`, and the file's own header comment says "Copy to `config/local.yaml` to override on a given machine."
2. Grepped the source: nothing reads `server.port` or `server.host`. The web defaults are hardcoded — `cli.py:65` (`--port default=8765`) and `webapp.py:207` (`port: int = 8765`).
3. So a user who edits `config/default.yaml` (or `local.yaml`) to set `server.port: 9000`, following the documented override path, sees **no effect**: the server still binds 8765 unless `--port` is passed on the command line.

**Why this matters:** The config file invites an override that does nothing — a quiet trap. Worse, the dead value (8080) disagrees with the real default (8765), so anyone reading the config to learn the port gets the wrong answer. Minor because `--port` works and localhost binding is the safe default, but misleading config is a documentation-grade defect.

**Fix path (suggest):** Either (a) wire `server.host`/`server.port` as the defaults for the `web` subcommand (config value, overridable by `--host`/`--port`), or (b) delete the `server:` block from the YAML and rely on flags. (a) is the better fit for a config-driven, local-first tool and aligns the file with user expectation. Whichever is chosen, reconcile the port number so 8080/8765 stop disagreeing.

**Blast radius:**
- Adjacent code: `src/kimcad/cli.py` (web arg defaults), `src/kimcad/webapp.py::serve`, `config/default.yaml`.
- Shared state: `Config` loader — if wiring it in, add a `server` accessor mirroring `printer()/material()`.
- User-facing: config-set port would start taking effect (intended).
- Migration: none.
- Related findings: Documentation/Engineering may already note dead config keys.

---

### QA-006 (Nit) — Web UI loads three.js from a public CDN, contradicting the local-first / localhost-only posture

**Category:** Browser / Offline

**Evidence:** `src/kimcad/web/index.html:104-106` pulls `three.min.js`, `STLLoader.js`, and `OrbitControls.js` from `https://cdn.jsdelivr.net`. The product is explicitly local-first (no cloud LLM calls; `config: host 127.0.0.1` localhost-only per the threat model). The UI already degrades gracefully if the CDN fails (`showModel` checks `typeof THREE === "undefined"` and shows a fallback note, line 186-189) — so this is a Nit, not a functional bug.

**Why this matters:** On an air-gapped or offline machine (a plausible state for a local-first 3D-print tool), the 3D preview silently won't load — the user sees the fallback note, not the model — even though everything else (render, gate, STL) works offline. It also means the localhost-only tool reaches out to a third party on every page load. Cosmetic/posture issue, not a defect, since the fallback is clean and the model is still saved and downloadable.

**Fix path (suggest):** Vendor the three.js files into `src/kimcad/web/` and serve them locally (they're small, pinned to 0.128.0). Removes the external dependency and makes the preview work offline. The static-serve path already exists for `index.html`; extend it to the JS assets.

---

## What's working (credit where due)

The running product is in good shape. Specifically verified:

- **API contract is clean and consistent.** Every path returns the right status and a structured JSON error body: GET `/` and `/index.html` → 200 HTML (10,871 bytes); POST `/api/design` valid → 200 with a complete, well-typed payload (`status`, `plan`, `report`, `has_mesh`, `mesh_url`, `prompt`); unknown GET route → 404 `{"error":"not found"}`; POST to wrong path → 404; empty prompt → 400 `{"error":"Please describe the part you want."}`; whitespace-only prompt → 400 (correctly stripped); no `prompt` key → 400; malformed JSON → 400 `{"error":"invalid request body"}`. Eleven of twelve happy/error cases behaved exactly as a careful integrator would expect.
- **Served STL bytes are real and structurally valid.** GET `/api/mesh/1` returned 1,284 bytes of `model/stl` binary; parsed the binary-STL header → declared 24 triangles → expected size `84 + 24*50 = 1284` → **exact match**. Not a placeholder, not truncated — a real mesh.
- **The JSON payload is correct UTF-8.** The `×` in the headline ("80.0 × 60.0 × 40.0 mm") is a genuine U+00D7 in the response body, decodes cleanly; the `_force_utf8_output` work in `cli.py` and JSON encoding both hold up. (My terminal's cp1252 mojibake on `×` was a display artifact, not a product bug — verified by decoding the raw bytes.)
- **The deterministic render stage is fast and correct against the real binary.** `snap_box` rendered to a valid 3MF in **0.16 s**, no STL fallback needed, clean sanitize (nothing removed/blocked). The OpenSCAD kernel reported a simple watertight solid. Five different library modules (`snap_box`, `tube`, `box`, `wall_hook`, control cube) all rendered watertight with correct volumes.
- **Adversarial inputs are handled safely.** Path-traversal on the mesh route (`/api/mesh/../../webapp.py`) → 404 (the route only does `int()` lookups in a registry dict, so `../` can't escape — good design). Empty mesh id, negative id, non-numeric id, missing `Content-Length` → all clean 404/400. The pipeline-exception path (`do_POST` lines 190-194) wraps the design call in a try and returns a structured 500 without leaking a traceback to the browser.
- **CLI surface is clean.** All four help screens (`--help`, `design/web/bench --help`) are accurate and complete. Exit codes are meaningful: `--help`=0, no-args=2, clarification-needed=3, with distinct codes wired for render-failed (4) and gate-failed (5). stdout/stderr discipline is reasonable (usage to stderr on no-args; errors to stderr in `main`).
- **Sandbox posture is sound by construction.** The OpenSCAD runner sanitizes untrusted codegen (strips out-of-library `use`/`include`, blocks `import`/`surface` file I/O and `minkowski`), runs in an isolated temp dir with a timeout and a 200 MB output guard, and the approved-library-path check rejects traversal and drive-absolute paths. I exercised the render path; the sanitize record came back clean for legitimate input.

---

## What I could NOT test (stated honestly)

- **The real LLM pipeline end-to-end.** By design — the on-device `gemma4:e4b` path is slow (minutes/call) and the brief said to avoid it. I exercised it inadvertently once (QA-004, `frobnicate`) and it returned a clarification quickly, but I did **not** verify a full real-LLM design→render→gate run, real-model plan quality, the clarification *loop* (the UI re-submits the full prompt + appended answer rather than continuing a session — `index.html:245-248` — which I noted statically but did not exercise live), retry/backoff on a flaky Ollama, or the `render_failed` (exit 4) and `gate_failed` (exit 5) CLI paths.
- **The benchmark.** Not run (too slow; brief said don't). Did not verify `--min-success-rate` exit-code behavior, batch resilience, or the `summary.txt` persistence-before-print logic at runtime.
- **The slicer / G-code path.** Intentionally not wired in the web UI (the "Prepare print" button is disabled by design); `tools/orcaslicer` not exercised.
- **Cross-browser / mobile / Core Web Vitals.** The UI is a single localhost dev page for a desktop CLI tool; I verified the HTML/JS over HTTP and the served assets, but did not load it in Chromium/Firefox/WebKit or measure CWV — out of scope for a local-first dev tool, but stated for completeness.
- **Concurrency / mesh-registry growth under load.** Noted statically that the mesh `registry` dict (`webapp.py:137`) never evicts — every design accumulates a `{id: path}` entry for the process lifetime. For a single-user localhost session this is negligible; I did not load-test it.

---

## Top findings for the orchestrator

1. **QA-001 (Major)** — Gate false-positives "stray-geometry mistake" on every fully-closed hollow box; **the demo trips it**. Highest-leverage fix; touches the gate's credibility.
2. **QA-002 (Minor)** — Demo (showcase path) shows a `warn`, not a clean `pass` (resolved free by QA-001).
3. **QA-003 (Minor)** — Malformed `Content-Length` crashes the request thread → connection reset instead of clean 400 (`webapp.py:178` outside the try).
4. **QA-004 (Minor)** — Typo'd subcommands silently become real LLM design runs (no unknown-command path).
5. **QA-005 (Minor)** — `config server:` block (port 8080) is dead config; disagrees with the real default (8765).

**Blockers: none. Criticals: none. Security: nothing reachable** — traversal blocked, no traceback leak to the browser, localhost-only binding, untrusted-codegen sandbox intact.
