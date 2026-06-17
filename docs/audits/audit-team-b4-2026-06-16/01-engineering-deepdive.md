# Engineering Deep-Dive — KimCad 0.9.0b4 (+ restored UI)

**Audit date:** 2026-06-17
**Role:** Principal Engineer
**Scope audited:** Full product. Python backend (`src/kimcad/**`, 20,021 LOC across 47 modules), the stdlib HTTP server + trust boundary (`webapp.py`), the untrusted-code geometry sandbox (OpenSCAD + CadQuery runners/worker), connector/credential handling, the saved-design store + zip/path handling, config/paths/settings, dependency surface (`requirements.lock`), and the shipped SPA's dangerous-sink surface. Builds on `docs/audits/walkthrough-b4-2026-06-16/WALKTHROUGH.md` (live critical path proven) rather than repeating it.
**Auditor posture:** Adversarial on security (ran real escape payloads through the real sanitizers); balanced elsewhere.
**Build under test:** `origin/main` @ `356867d`, version `0.9.0b4`. Gate green (pytest 1600, vitest 396, build-repro clean).

---

## TL;DR

This is a mature, audit-scarred codebase — most modules carry embedded prior-finding IDs (ENG-*, QA-*, KC-*) with the rationale inline, and the discipline shows. The security posture on the two highest-risk surfaces — the untrusted-LLM-code geometry sandbox and the web trust boundary — is genuinely strong and **held against every escape payload I threw at it live**. The dependency surface is current and clean (pip-audit: zero known CVEs). I found **no Blockers and no Criticals reachable through the in-app (UI) trust model.** The headline finding is a **Major** defense-in-depth gap: the cloud (OpenRouter) `base_url` is not scheme/host-validated, so a tampered or maliciously-shipped `config/local.yaml` can exfiltrate the user's API key to an attacker host — the inverse of the rigorous loopback-pinning already applied to the vision and model-pull paths. The remaining findings are Minor/Nit consistency, resource-leak, and hygiene items. Architectural debt is low; the seams (injected pipeline, paths seam, DesignRegistry, subprocess_env) are well-chosen.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 6 |
| Nit | 5 |

## What's working

- **The CadQuery sandbox is a real two-layer, honestly-documented defense.** I ran the full escape battery through the *real* `sanitize_cadquery` (`.venv\Scripts\python.exe`): `import os`, `from os import system`, `().__class__.__bases__[0].__subclasses__()`, `{}["__class__"]`, `{}[b"__class__"]`, `getattr`, `"{0.__class__}".format(cq)`, `g().gi_frame`, `fn.__globals__`, `__import__("os")`, and a `chr(95)`-built dunder — **every one BLOCKED**; clean geometry passed. The worker's restricted `__builtins__` + module-stripped facade (`cadquery_worker.py:72-118`) is a correct second layer, and the module docstring (`cadquery_worker.py:24-55`) is refreshingly honest that layer 2 alone cannot close the `__globals__` escape class — layer 1 does — and that OS-level confinement is *not yet* implemented. That candor is exactly right.
- **OpenSCAD sanitizer blocks on the full source with comments blanked.** Verified live: `minkowski()`, a newline-split `minkowski\n()`, `import()`, `surface()`, `use <../../etc>`, `use </etc/passwd>`, and `use <C:library/x>` all BLOCKED; `library/`-internal `use` and plain geometry passed (`openscad_runner.py:218-241`, `_approved_library_path:116-126`).
- **Fail-closed trust boundary on the print path.** A gate-FAILED part returns `PipelineStatus.gate_failed` and never reaches the slicer (`pipeline.py:601-616`); the web layer independently re-enforces it at `/api/slice` (`webapp.py:2427`), `/api/send` (`webapp.py:1819`), and re-derives the verdict from the actual mesh on reopen/import (`_regate_mesh`, `webapp.py:592-611`; `_handle_design_reopen` syncs the report to the re-gated verdict, `webapp.py:2300-2308`) — so a tampered `.kimcad` claiming `gate_status:"pass"` is re-validated, not trusted.
- **Secret hygiene throughout.** No `shell=True`, no `verify=False`/unverified TLS context, no `eval`/`exec` outside the documented sandbox worker, no `dangerouslySetInnerHTML` anywhere in `frontend/src`. Both untrusted-code runners run with a shared secret-scrubbed env (`subprocess_env.py`, whole-segment matching so `TOKENIZER_PATH` survives while `OPENROUTER_API_KEY` is stripped). The OpenRouter key lives in the OS keyring with a disclosed file fallback, a real-read health probe (`settings_store.py:64-77`), vault rollback on write failure (`:252-264`), and correct `@keyring` sentinel collision refusal (`:228-243`).
- **Zip-slip / decompression-bomb safe import.** `.kimcad` import reads only three known members *by exact name* (never the archive's own paths) with a 64 MiB per-member inflate ceiling (`design_store.py:30-36, 269-297, 359-367`); ids are validated to an ASCII token before any path resolution (`_safe_id:326-330`).
- **Resource/DoS bounds are present and reasoned:** body-size caps with a Windows-RST-safe drain (`webapp.py:1257-1292`), a design-route admission semaphore returning 429 (`:1351-1362`), bounded LRU registries, the slice/render locks, and a connect/read timeout split on the LLM client (`llm_provider.py:255`).
- **Dependency surface is current and clean.** `pip-audit -r requirements.lock` → "No known vulnerabilities found"; pinned versions are June-2026-current (openai 2.41, pydantic 2.13, trimesh 4.12, numpy 2.2, lxml 6.1).

## What couldn't be assessed

- **OS-level sandbox confinement** is, by the worker's own admission, not implemented — so the *residual* risk (a novel CPython introspection escape the static sanitizer doesn't yet name) cannot be ruled out by static review. The sanitizer-anchored model is sound and I could not break it, but "I could not break it" is not "it is unbreakable." Covered live by the walkthrough + QA/Test roles for the benign path; the adversarial path is bounded by layer-1 source rejection.
- **Real cloud-vendor runtime behavior** (the actual OpenRouter / DeepSeek HTTP exchange) and **real printer-hardware** connector behavior are exercised only against fakes/mocks in-tree; the live LLM + live slice are covered by the walkthrough + QA/Test roles, not by this static pass.
- **Filesystem ACLs** on the per-user `~/.kimcad` tree (the settings file holds connector `base_url`s; the keyring holds the secret) were not inspected at the OS-permission level.

---

## Findings

> **Finding ID prefix:** `ENG-`

### [ENG-001] — Major — Security — Cloud `base_url` is not scheme/host-validated; a tampered config can exfiltrate the OpenRouter key

**Evidence**
`llm_provider.py:256` builds the client with the backend's `base_url` verbatim: `OpenAI(base_url=backend.base_url, api_key=key, ...)`. `config.py:329` reads `base_url=b["base_url"]` straight from `config/local.yaml`'s `llm.backends.*` with no scheme or host allow-list. The *in-app* Settings flow is safe-by-construction — `_SettingsAwareProvider._active` (`webapp.py:450`) does `replace(self._config.llm_backend("custom_openrouter"), model_name=model)`, so the user supplies only the **key** and **model name**, never the URL, and the shipped `custom_openrouter` backend is pinned to `https://openrouter.ai/api/v1` (`config/default.yaml:98-100`). The gap is the config-file path: any backend in `local.yaml` (or a `llm.active`/`alt_backend` pointed at a hand-added one) can name an arbitrary `http://attacker/v1`, and the saved key is then sent to it as a Bearer credential. Contrast the rigor elsewhere: vision is structurally pinned to loopback (`llm_provider.py:434-441`) and model-pull validates loopback with an IP-parse that defeats `127.evil.example` (`model_pull.py:46-55`). The cloud chat path has the inverse risk and no equivalent guard.

**Why this matters**
A billable, user-owned API key is exfiltrated to an attacker-controlled host if `config/local.yaml` is tampered with, or if a malicious config is ever shipped/imported/copied between machines. It is not reachable through the UI (which is why this is Major, not Critical), but it is a real key-disclosure path that contradicts the loopback discipline the rest of the LLM surface enforces, and "config is trusted" is a weaker assumption than the project makes everywhere else.

**Blast radius**
- Adjacent code: `config.llm_backend` / `llm_alt_backend` (any backend key), `_real_provider`/`FallbackProvider` (`webapp.py:396-402`), `_SettingsAwareProvider` (the in-app path is already safe but shares the builder).
- Shared state: `config/local.yaml`, the keyring secret.
- User-facing: none for legitimate users; closes a silent exfil path.
- Migration: none — additive validation. A user with a deliberately custom cloud host would need an allow-list entry or an explicit opt-out flag.
- Tests to update: add a test that a non-https / non-allow-listed cloud `base_url` is refused when a saved key is in play; none should currently assert the gap.
- Related findings: ENG-002 (same "config-driven value reaches a sink unvalidated" root).

**Fix path**
When `cloud_enabled` and a saved key would be sent, validate the resolved cloud `base_url`: require `https` scheme and a host on a small allow-list (`openrouter.ai`, plus the shipped `cloud_deepseek` host), with an explicit, documented escape hatch for advanced users who knowingly add a custom endpoint. Mirror the loopback-validation pattern already in `model_pull.is_loopback_url`.

---

### [ENG-002] — Minor — Security — `binary_path` returns an unvalidated, exec-bound path

**Evidence**
`config.py:153-157` returns `Path(raw)` (or `PROJECT_ROOT / raw`) for any `binaries.*` config value with no existence/containment check; the result is handed to `subprocess.run` for OrcaSlicer/OpenSCAD/PrintProof3D. There is no traversal *escape* (absolute paths are honored by design, and that is correct for a bundled-binary app), but a relative `..\..\windows\system32\...` or an arbitrary absolute path resolves silently, and a non-existent path fails opaquely downstream rather than with a typed message (OrcaSlicer's own caller does pre-check `is_file()` — `slicer.py:205` — so the impact is partly absorbed).

**Why this matters**
Operator-controlled config only (not a remote-attacker path), so impact is low; flagged as defense-in-depth and for the same root as ENG-001 (config values reaching a subprocess sink without an assertion).

**Blast radius**
- Adjacent code: `orca_profiles_root` (`config.py:162`), `printproof3d_binary` (`:164-174`, which *does* check existence — the inconsistency is the tell).
- Migration: none. Fix is an `is_file()` assertion + an optional "binary escapes install root" warning.

**Fix path**
Low priority. If tightened, have `binary_path` assert the resolved target exists and is a file, and warn when a configured binary resolves outside the install root.

---

### [ENG-003] — Minor — Correctness — Duet connector leaks a board session on the mid-poll offline path

**Evidence** (from the connector sub-audit, verified against the module's own contract)
`duet_connector.py:240-241` (`status()`) and `:331-332` (`job_status()`) — the `except (urllib.error.URLError, OSError)` arm returns **without** `self._disconnect()`, unlike every other arm in those methods. The module docstring (`:17-19`) stresses it "ALWAYS `/rr_disconnect`s in a finally, so repeated status polling can't exhaust the board's session slots." If `_connect()` succeeded and then `_status_json()` raised URLError/OSError (a transient mid-poll blip), the RRF session is left open.

**Why this matters**
Largely benign (if `_connect()` itself raised, no session exists), but a transient network blip mid-poll partially defeats the session-exhaustion protection the module is built around — and Duet boards have a small fixed session-slot count, so repeated polling through flaky Wi-Fi could lock the user out of their own printer.

**Blast radius**
- Adjacent code: both `status()` and `job_status()` in `duet_connector.py`; pattern is Duet-specific (other connectors are stateless HTTP).
- User-facing: a Duet user on flaky Wi-Fi could see "too many connections" from their own board.
- Tests to update: add a fake that raises URLError *after* a successful connect and assert `_disconnect()` ran.

**Fix path**
Restructure both methods to a `try/finally` so `_disconnect()` runs on every exit path (the `_disconnect` is already a safe no-op when no session is open).

---

### [ENG-004] — Major — Security/Architecture — The sandbox has no OS-level confinement; layer-1 source rejection is the whole boundary

**Evidence**
`cadquery_worker.py:44-55` states plainly that a facade function still carries its real `__builtins__` via `__globals__`, that every such path needs a dunder/introspection attribute the static sanitizer blocks, and that "OS-level process confinement (no network, restricted working dir) ... is NOT yet implemented." The OpenSCAD child runs in an isolated temp cwd with `OPENSCADPATH` set (`openscad_runner.py:244-263`) but with no process-level sandbox either. Both children run with a secret-scrubbed env (good), but nothing stops a *successful* escape (were one found) from reading arbitrary user files or opening a socket.

**Why this matters**
The entire confidentiality/integrity boundary for executing untrusted LLM-authored code rests on the correctness of one static AST sanitizer. I could not break it, and the design is honest about the residual — but a single missed introspection primitive (or a future CadQuery/OCP version that re-exposes a stripped module) is a full local-RCE-equivalent with no second wall. For a beta on the user's own trusted machine the trust model holds; as the product grows (shared configs, imported designs that carry geometry source, any future multi-user mode) the absence of a hard wall becomes the architectural risk that forces work later.

**Blast radius**
- Adjacent code: `cadquery_runner.render_cadquery`, `cadquery_worker._run`, `openscad_runner.render_scad` — all three subprocess spawns.
- Shared state: the `subprocess_env` scrub (already correct), the per-design `out_dir` (not confined-to).
- Migration: adding OS confinement (a restricted job object / AppContainer on Windows, seccomp/landlock on Linux for the from-source path) is additive but platform-specific and needs its own test matrix.
- Related findings: none share the root; this is the deepest architectural item.

**Fix path**
Track and implement OS-level confinement for both untrusted-code subprocesses: on Windows, a restricted token / Job Object with no network and a working-dir-only filesystem view; keep the static sanitizer as layer 1. Until then, the current honest documentation + the secret-scrub is the right interim posture — do not let "the sanitizer is thorough" become a reason to skip the hard wall indefinitely.

---

### [ENG-005] — Minor — Reliability/Security — Silent keyring→file secret downgrade on a transient backend failure

**Evidence**
`settings_store.py:233-243` — if `kr.set_password` raises during a save, the key is written to the JSON file in plaintext (`current[_SECRET_KEY] = ... else v`) with no surfaced warning. The downgrade *is* disclosed after the fact via `key_storage()` (`:143-152`), and the legacy-migration failure is also swallowed (`:130-131`).

**Why this matters**
A user who set up keyring can be silently moved to plaintext-file storage if the OS credential backend transiently fails during one save. Disclosed-on-read, so not hidden, but the moment of downgrade is invisible.

**Blast radius**
- Adjacent code: `SettingsStore.update` / migration; the webapp's `settings_response` already forwards `key_storage` to the UI.
- User-facing: the key silently becomes file-stored; the Settings disclosure line is the only signal.

**Fix path**
Surface a one-time UI notice when a save falls back to file storage (the data to do so — `key_storage()` flipping to `"file"` — already exists), so the user can re-secure.

---

### [ENG-006] — Major — Performance/Correctness — Whole-file `read_bytes()` on every mesh/gcode/STEP download holds the response in memory

**Evidence**
`webapp.py:1255` (`_serve_mesh`: `mesh_path.read_bytes()`), `:1057` (`_serve_gcode`), `:1095` (`_serve_step`), `:1186`/`:1219` (static/index) all read the entire artifact into memory and write it in one shot via `_send`/`_send_download`. The walkthrough's proven `.3mf` was 576 KB and meshes are typically small, but `max_output_bytes` for a render/slice is **200 MiB** (`openscad_runner.py:274`, `cadquery_runner.py:197`), and an imported `.kimcad` mesh can be up to 64 MiB (`design_store.py:36`). Several concurrent downloads of large artifacts (a `--allow-remote` LAN, or just an enthusiastic single user) each buffer the whole file.

**Why this matters**
A legitimately large part (200 MiB mesh) buffered per concurrent request can spike RSS hard under `ThreadingHTTPServer`, which spawns a thread per connection with no global memory budget. Not a crash under the single-user norm, but a real ceiling and the kind of thing that bites exactly when a user makes the big complicated part they were excited about.

**Blast radius**
- Adjacent code: every `_serve_*`/`_send`/`_send_download` path; the static-asset cache (`static_cache`) also holds whole bodies (bounded set, acceptable).
- User-facing: large-part downloads; worse on `--allow-remote`.
- Migration: switching to a streamed/chunked write changes the `_send` contract (Content-Length is still known from `stat()`), low risk.

**Fix path**
Stream large artifacts: `stat()` for Content-Length, then `shutil.copyfileobj` from an open file handle to `self.wfile` in bounded chunks for the mesh/gcode/step download paths. Keep the small-file fast path. Consider a global concurrent-download budget alongside the existing design semaphore.

---

### [ENG-007] — Minor — Correctness — Native-schema (default local) plan path lacks the connect/read timeout split

**Evidence**
`llm_provider.py:349` uses bare `urllib.request.urlopen(req, timeout=self.backend.timeout_s)` for the Ollama-native grammar-constrained plan call — a single timeout covering connect+read — whereas the OpenAI path gets `httpx.Timeout(timeout_s, connect=5.0)` (`:255`). This is the *default* local code path (`_complete_plan` routes Ollama backends here, `:324-326`). The `_server_reachable` fail-fast only runs *after* the first attempt's connect has already blocked (`:354`).

**Why this matters**
A wedged-but-listening local server makes the default plan call block up to the full `timeout_s` (default 1200 s) on the OS connect before the fail-fast probe can fire — the exact slow-first-run experience the QA-004 connect/read split was introduced to prevent, silently absent on the path most users hit.

**Blast radius**
- Adjacent code: `_complete_native_schema`; the OpenAI `_complete` path is already correct.
- Tests to update: a fake that accepts the connection but never responds, asserting fail-fast.

**Fix path**
Probe `_server_reachable()` *before* the first attempt on this path, or set a short socket connect timeout on the urllib request.

---

### [ENG-008] — Minor — Hygiene — UTF-8 BOM in `FirstRunWizard.tsx` and `SettingsPanel.tsx`

**Evidence**
Noted by the walkthrough (WALKTHROUGH.md finding, "UTF-8 BOM at the top of `FirstRunWizard.tsx` and `SettingsPanel.tsx`") introduced by the designer pass `9af7cc7`. Harmless (vitest/build pass; `settings_store` even reads its own JSON with `utf-8-sig` defensively, `:138`) but non-idiomatic for TS source.

**Why this matters**
Cosmetic; a BOM in TS source can confuse some tools and diffs. Worth a one-line cleanup.

**Fix path**
Strip the BOM from both files (re-save as UTF-8 without BOM); add an editorconfig/lint rule if drift recurs.

---

### [ENG-009] — Minor — Correctness — `job_status` `detail` fields echo raw exception strings inconsistently

**Evidence** (connector sub-audit)
`marlin_connector.py:367-368` returns `detail=str(e)[:120]` (a raw exception string) and `octoprint_connector.py:234` uses `f"unreachable: {e}"`, whereas the connectors' `status()` methods were cleaned (QA-003) to emit fixed strings rather than raw `urllib`/`WinError` text. The `detail` field surfaces in the UI/API.

**Why this matters**
Inconsistent: a `status()` poll shows a clean detail, a `job_status()` poll on the same connector shows raw OS error text. No secret is in scope (the target host:port is not secret), so it is hygiene, not disclosure.

**Fix path**
Mirror the QA-003 treatment in `job_status`: return a clean fixed detail (e.g. "could not reach the printer") rather than `str(e)`.

---

### [ENG-010] — Nit — Security/UX — Export connector badge surfaces the raw config key "mock · simulated"

**Evidence**
Walkthrough UX-001: the Export panel renders "mock Ready · simulated" — the raw connector config key `mock` leaks unprettified (siblings use `displayName()`), and "simulated" next to the slice controls can be misread as "the slice is simulated" when it refers to the *connection*.

**Why this matters**
Honesty/clarity nit on a trust-sensitive surface (it is telling the user no real hardware is attached), but the wording invites the exact misread the feature exists to prevent.

**Fix path**
Run the connector name through `displayName()` and reword "simulated" to "no printer connected (simulated send)" on the export surface.

---

### [ENG-011] — Nit — A11y — Settings section-nav marks `aria-current="true"` on every link in the active group

**Evidence**
Walkthrough A11y finding (from designer pass `9af7cc7`): both "Printer & material" and "Display" carry `aria-current` when `grp-design` is active, rather than the single current item.

**Fix path**
Set `aria-current` on the single active link (or use `aria-current="true"` on the group container, not each child).

---

### [ENG-012] — Nit — Robustness — Raw upstream error text reflected into user-facing strings

**Evidence**
`model_pull.py:67` `f"The download stopped: {raw}. ..."` and `:181` `raise RuntimeError(str(line["error"]))` interpolate an untrusted streamed-JSON `error` field straight into a display string; `_friendly_error` doesn't bound it. Display-only, local Ollama, no eval — low impact.

**Fix path**
Truncate/clip `raw` before display (the codebase already uses `[:300]`/`[:500]` clips elsewhere — apply the same here).

---

### [ENG-013] — Nit — Robustness — Bambu disconnect reaches into a private paho attribute and fails silently

**Evidence**
`bambu_connector.py:160` `printer.mqtt_client._client.disconnect()  # noqa: SLF001` inside a broad `except Exception`. The comment explains the *why* (paho's `loop_stop()` sends no DISCONNECT, churning Bambu's connection cap), but a `bambulabs-api`/paho version bump that renames the attribute silently re-introduces the leak with no signal.

**Fix path**
Keep the workaround but log at debug when the private-attr path raises, and add a test asserting the disconnect path is reached against the fake — so a library shape change trips CI, not production.

---

## Patterns and systemic observations

1. **Config-as-trusted is the one soft spot in an otherwise rigorously-validated system.** ENG-001 and ENG-002 share a root: values from `config/local.yaml` (`base_url`, `binaries.*`) reach a network/subprocess sink without the assertion every *runtime/network* input gets. The fix is the same shape in both: validate at the boundary the way `model_pull.is_loopback_url` and the vision-host pin already do. This is the highest-leverage cluster.

2. **Sanitizer-anchored sandboxing is correct but single-walled (ENG-004).** The team has clearly invested heavily in layer 1 and is honest that layer 2 can't independently close the escape class. The durable answer — OS confinement — is the one piece of named-but-unbuilt hardening, and it is the right next security investment as the product's trust model widens.

3. **Memory-resident I/O (ENG-006).** The whole-file `read_bytes()` pattern is fine at the proven sizes but is the same shape repeated across every download path, with a 200 MiB ceiling behind it — a textbook "Minor each, Major as a pattern" item.

4. **Embedded-finding-ID discipline is a genuine strength.** Nearly every defensive branch cites the audit that produced it (ENG-/QA-/KC-). It makes the code self-documenting about *why* a guard exists and prevents regressions-by-cleanup. Keep it.

## Dependency snapshot

`pip-audit -r requirements.lock` → **No known vulnerabilities found.** Versions are current as of the audit date.

| Dependency | Version | Concern |
|---|---|---|
| openai | 2.41.0 | None — pinned, current; client built with `max_retries=0` + connect/read split. |
| pydantic | 2.13.4 | None — IR validation uses field validators correctly (`ir.py`). |
| trimesh | 4.12.2 | None — backed by scipy/networkx as declared; mesh load is the validation boundary. |
| lxml | 6.1.1 | None — trimesh's 3MF reader; current (older lxml had CVEs, this is past them). |
| manifold3d | 3.5.1 | Hard dep with a defensive import guard (`hardening.py`); degrades to gate-validated mesh. |
| keyring | 25.7.0 | None — health-probed with a real read, not import-success. |
| setuptools | 82.0.1 | None — build-only; well past the 2022–2024 CVE band. |
| pywebview | 6.2.1 | Windows-only marker; degrades to the browser path when absent. |

Dependency surface is clean — no abandoned packages, no reached CVEs, no obvious bloat. License is Apache-2.0; deps are permissively licensed.

## Appendix: artifacts reviewed

- Read in full: `webapp.py` (2677 lines), `design_store.py`, `cadquery_runner.py`, `cadquery_worker.py`, `openscad_runner.py`, `subprocess_env.py`, `ir.py`, plus targeted reads of `pipeline.py` (gate/slice/confirm spine), `settings_store.py` (secret-at-rest), `llm_provider.py` (client build + timeouts + reachability), `config.py` (backend/connector/binary resolution), `cli.py` (host-bind gate), `slicer.py` (subprocess construction).
- Reviewed via sub-audits (read in full by delegated engineers): all eight connector modules (`connectors.py`, `printer_connector.py`, `octoprint/prusalink/moonraker/duet/marlin/bambu_connector.py`); `paths.py`, `hardening.py`, `model_pull.py`.
- Live probes run with `.venv\Scripts\python.exe`: 13 CadQuery escape payloads + 9 OpenSCAD payloads through the real sanitizers (all dangerous ones BLOCKED, clean ones passed); `pip-audit -r requirements.lock` (clean); scoped greps confirming no `shell=True`, `verify=False`, unverified TLS context, `eval`/`exec` outside the worker, or `dangerouslySetInnerHTML` in `frontend/src`.
- Config inspected: `config/default.yaml` (LLM backends — confirmed `custom_openrouter` is pinned to `https://openrouter.ai/api/v1`), `pyproject.toml`, `requirements.lock`, `SECURITY.md`.
- Built on (not repeated): `docs/audits/walkthrough-b4-2026-06-16/WALKTHROUGH.md`.
