# Engineering Deep-Dive — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Role:** Principal Engineer
**Scope audited:** Entire repo at commit `f92c2b1` / tag `v0.9.0b2` — the stdlib `http.server` backend (`src/kimcad/`, esp. `webapp.py`, `pipeline.py`, `llm_provider.py`, the connectors, `cadquery_*`, `openscad_runner.py`, `hardening.py`, `subprocess_env.py`, `settings_store.py`, `paths.py`), the committed React/TS SPA (`frontend/src/`), the packaging/installer path (`scripts/build_installer.py`, `requirements.lock`, `pyproject.toml`), and the gate (`scripts/ci.sh`). Audit-only — no product code modified.
**Auditor posture:** Balanced

---

## TL;DR

This is unusually disciplined code for a beta. The trust model is coherent and *honestly documented*: loopback-by-default, a constant-time per-boot session-token guard on every state-changing POST, an explicit `--allow-remote` escape hatch with a truthful "NO authentication" warning, and two well-reasoned layers of sandboxing around generated geometry code (static AST block-list + a restricted-builtins out-of-process worker) whose own docstring is candid that the durable boundary is local-machine trust. The connector M-code/HTTP surfaces sanitize filenames before they reach `M32`/`M28`/`rr_upload`, and the command paths use argv lists (no shell). The fast (non-tool) test suite is fully green (1249 passed) and `pip-audit` reports no known CVEs. The real concerns are *not* in the security primitives — they are: (1) a packaging/provenance leak where the optional `bambu` extra's transitive deps (including a full `bottle` web framework) ship to **every** installer user while the symmetric `serial` extra does **not**, contradicting both `pyproject.toml`'s "optional/graceful-absence" framing and the README; (2) a robustness gap in the plan→template-match path that makes the **default local model fail 2 of 3 of the app's own showcased landing prompts**, dead-ending at the experimental offer rather than building; and (3) the previously-flagged `ARCHITECTURE.md` drift that still documents a *removed* untrusted-codegen path as live. Architectural debt is low; the highest-leverage fixes are a lockfile-generation policy and a small widening of the template-match net.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 4 |
| Minor | 6 |
| Nit | 3 |

## What's working

- **The session-token CSRF guard is correct and honest.** `webapp.py:1317-1319` uses `hmac.compare_digest` (constant-time), gates *every* POST when a token is set (`do_POST` runs the check before dispatch), and the design rationale at `do_POST` and `cli.py:479-481` is explicit that this is anti-cross-origin only, NOT remote auth — so the `--allow-remote` warning stays accurate. The token is per-boot (`secrets.token_urlsafe(32)`, `webapp.py:2615`), unguessable, and never persisted. The side-effecting GETs that can't carry the token (`_serve_step`, the health re-probe) are separately protected by the `Sec-Fetch-Site` cross-site refusal (`webapp.py:1034-1053`).
- **The exclusive Windows bind is the right call and well-justified.** `_ExclusiveBindServer` (`webapp.py:2556-2567`) disables `SO_REUSEADDR` on Windows so a second `kimcad web` fails deterministically instead of silently fighting for the port, with `handle_error` (`:2569-2582`) downgrading benign client-disconnect classes to one quiet line.
- **Generated-geometry sandboxing is layered and candidly bounded.** The OpenSCAD sanitizer (`openscad_runner.py:218-241`) blocks (not strips) `minkowski`/`import`/`surface`/out-of-library `use|include`, scans comment-blanked full source so a newline-split construct can't slip past, and runs the binary in an isolated cwd with a secret-scrubbed env (`subprocess_env.scrubbed_env`). The CadQuery worker (`cadquery_worker.py`) runs untrusted code in a *separate interpreter* with a restricted `__builtins__` (no `open`/`eval`/`exec`/`compile`), a geometry-only cadquery facade with every submodule stripped, and an `__import__` that allows only `cadquery`/`math`. Its module docstring (`:24-55`) is refreshingly honest that layer 1 (the static sanitizer) — not the worker — closes the `__globals__` escape class, and that OS-level confinement is **not** implemented.
- **Connector injection surfaces are sanitized at the boundary.** `MarlinConnector._sd_name` (`marlin_connector.py:271-277`) reduces SD filenames to `[A-Za-z0-9]{≤8}.gco`; `DuetConnector._safe_upload_name` (`duet_connector.py:253-259`) keeps only `[A-Za-z0-9-_]` before it reaches `M32 "0:…"` and `rr_upload?name=…`. Both protect against quote/newline/second-command injection. The Marlin G-code stream is checksummed (`_checksum_line`) with a bounded resend budget so a noisy link can't loop forever.
- **The send/print safety chain is multiply defended.** `ensure_sendable` requires `confirm is True` (not merely truthy) AND a proven motion-bearing slice (`printer_connector.py:10-18`); `_handle_send` adds a server-side gate-fail belt-and-suspenders (`webapp.py:1785-1791`); the slice/send paths re-derive the gate verdict from stored metadata rather than trusting a `.kimcad` blob (`webapp.py:586-588`).
- **Per-design state hygiene is genuinely careful.** `DesignRegistry.evict_locked` (`design_registry.py:97-116`) drops an id from *every* registry plus its on-disk dir in lockstep, with `_require_lock()` asserting the locked-method contract at runtime. The geometry-version protocol (`bump_version_locked`/`register_gcode_locked`) provably prevents a re-render landing mid-slice from leaving stale G-code downloadable.
- **The loopback guard is parsed, not string-matched.** `model_pull.is_loopback_url` (`model_pull.py:46-55`) and `cli._is_loopback_host` (`cli.py:505-514`) both use `ipaddress.ip_address(...).is_loopback`, explicitly closing the `127.evil.example` prefix-match hole the slice-10.4 audit caught.
- **Secret-at-rest handling degrades honestly.** `settings_store` stores the OpenRouter key in the OS credential store via `keyring`, probes backend *health* (not just import) before claiming "keyring" (`:64-70`), falls back to the disclosed file when unusable, and `key_storage()` tells the UI which — no implied safety it can't deliver. The subprocess scrub matches whole NAME segments so look-alikes (`TOKENIZER_PATH`) survive while real secrets are stripped (`subprocess_env.py:20-36`).
- **Body and gate hygiene.** 1 MiB body cap rejected *before* read with a bounded drain to avoid a Windows connection-abort on the 413 (`webapp.py:1271-1304, 1241-1271`); non-object JSON bodies rejected with a distinct message; tool-missing surfaces as a typed recoverable response, never a raw `FileNotFoundError`. Ruff clean; 1249 non-tool tests green; `pip-audit` clean.

## What couldn't be assessed

- **The live-tool suite** (real OpenSCAD/OrcaSlicer/CadQuery renders, `live`/`real_tool`/`needs_cadquery`/`needs_browser` markers — 313 tests) was deselected for runtime; the fast subset (1249 tests) passed cleanly and `scripts/ci.sh` is the authoritative gate. I did not re-run the full gate end-to-end.
- **Real-hardware connector behavior.** Every connector is proven only against the in-repo mocks (`mock_marlin`, `mock_duet`, `mock_moonraker`, `mock_prusalink`, `mock_printer`); real-board field/firmware variance (the `#11` metal-validation item) is by definition out of reach here. Findings on the connectors are about the *code paths*, not field conformance.
- **The browser-visual SPA walkthrough** could not run under the preview harness (the exclusive-bind design refuses the harness's pre-reserved port — correct product behavior). I assessed the SPA statically and via the API contract; I did not click through rendered screens.
- **The gemma4:e4b landing-prompt failure** described in the brief was reproduced *by code reading* (the match path and the three `Landing.tsx` example strings), not by a live model run in this pass.

---

## Findings

> **Finding ID prefix:** `ENG-`
> **Categories:** Architecture / Correctness / Security / Performance / Data provenance / Dependencies / Hygiene

### [ENG-001] — Major — Dependencies / Data provenance — The optional `bambu` extra (incl. a full `bottle` web framework) ships to every installer user, while the symmetric `serial` extra does not

**Evidence**
- `pyproject.toml:45-51` declares `bambu` and `serial` as **optional** extras with the documented "graceful absence" posture ("without it the bambu connectors report 'not set up'…"; "Without pyserial, a serial-port target reports a clear install hint").
- `requirements.lock` pins `bambulabs-api==2.6.6`, and its transitive deps `bottle==0.13.4`, `paho-mqtt==2.1.0`, `pythonnet==3.1.0` — but contains **no `pyserial`** (verified: `grep -i serial requirements.lock` → no match).
- `scripts/build_installer.py:120` installs the shipped `site-packages` directly from `requirements.lock` (`pip install --target … -r requirements.lock`). The `RELEASE_STRIP_NAMES` set (`:55-58`) removes only dev/build toolchain (`pytest`, `ruff`, `pip`, `setuptools`, …) — it does **not** strip `bambulabs-api`/`bottle`/`paho-mqtt`.
- Net effect: a non-Bambu user's official installer carries a Bambu SDK, an MQTT stack, a `.NET` CLR loader (`pythonnet`), and the `bottle` HTTP framework — none reachable for them — while a Marlin/Ender user who installs via the *same* installer and prints over USB hits the `marlin_connector._open_serial` "install pyserial" wall (`marlin_connector.py:178-185`) despite having used the official build.

**Why this matters**
Three compounding problems. (1) **Provenance/contract drift:** the manifest says these are opt-in; the shipped artifact makes `bambu` mandatory-by-bundling and `serial` genuinely-optional — an asymmetry no doc explains. (2) **Supply-chain surface:** `bottle` and `pythonnet` (a CLR bridge) are non-trivial attack surface installed for users who never touch a Bambu printer; the project's whole posture is minimizing what runs locally. (3) **UX inconsistency:** the most common consumer FDM machine class (Marlin/Ender over USB) is the one extra *not* bundled, so the official installer can't drive it without a manual pip step the app's own framing says shouldn't be needed. There is no documented procedure for regenerating `requirements.lock` (searched `CONTRIBUTING.md`, `docs/`), so the asymmetry looks accidental — a freeze run that happened to have `bambu` installed but not `serial`.

**Blast radius**
- Adjacent code: `scripts/build_installer.py` (the strip list and the lock-install step); `scripts/verify_install.py` (exercises survivors — would need to cover/except any newly-stripped or newly-added package); `.github/workflows/ci.yml:58,73,157` all consume `requirements.lock` (venv provision + `pip-audit -r requirements.lock`), so a regenerated lock changes what CI installs and audits.
- Shared state: `requirements.lock` is the single pinned set for CI, the installer, and the documented from-source path (`README.md:151`). Any change ripples to all three.
- User-facing: installer size; whether a USB Marlin print works out-of-the-box; what third-party code a privacy-conscious local-first user is actually running.
- Migration: decide intent, then either (a) bundle BOTH extras (add `pyserial`; keep `bambulabs-api`) for a consistent "batteries-included installer," or (b) bundle NEITHER and lock only the base deps, adding both extras to the installer as explicit opt-in components. Either way, regenerate the lock from a declared command and document it.
- Tests to update: `scripts/verify_install.py` survivor checks; possibly a new test asserting the lock matches a documented generation command (parallel to `test_version_single_source.py`'s discipline).
- Related findings: ENG-007 (no lockfile-regeneration policy); cleanup-review M1 (USER-MANUAL omits the Marlin/Duet connectors — the same Marlin user is under-served in docs too).

**Fix path**
Decide the policy explicitly (recommend: batteries-included — bundle both `bambu` and `serial` so the official installer drives every supported connector, since that matches the consumer-first goal). Add a `scripts/regen_lock.py` (or a documented `pip-compile`/`pip freeze` command) that freezes `.[bambu,serial]` deterministically, and a `CONTRIBUTING.md` section naming it. If instead the goal is a lean base install, strip `bambulabs-api`/`bottle`/`paho-mqtt`/`pythonnet` from the release and surface both extras as installer checkboxes. Pin the decision in `ARCHITECTURE.md`'s packaging section.

---

### [ENG-002] — Major — Correctness / Data provenance — The default local model fails 2 of 3 of the app's own showcased landing prompts; the tiered engine dead-ends at the experimental offer instead of building

**Evidence**
- The three showcase prompts are hardcoded in `frontend/src/components/Landing.tsx:9-12`: "a wall-mounted holder for a 1 kg filament spool", "a 40 mm desk cable clip", "a hexagonal pen and tool organizer".
- All three *have* template families: `cable_clip` (`templates.py:487-490`, aliases incl. "cable clip"), `spool_holder` (`:553-558`, aliases "spool holder"/"filament spool holder"/"filament holder"/"spool bracket"), and a pen-cup family (`:1159-1160`, "pen holder"/"pencil cup"/…). So the failure is **not** a template-coverage gap.
- `TemplateRegistry.match` (`templates.py:323-331`) resolves `object_type` by **exact normalized alias** plus a single conservative `_singular()` fallback (`:73-77`) — no fuzzy/synonym/substring match. `_normalize` lowercases/strips separators only.
- When `match()` returns `None` AND `allow_experimental` is False (the consumer SPA sends `experimental:false` on a normal design — `webapp.py:1992-1995`), the pipeline returns `PipelineStatus.needs_experimental` (`pipeline.py:453-461`) — an *offer to try the experimental generator*, not a built part.
- The default consumer config is experimental-OFF (`settings_store.py:44-45` "OFF by default"; `webapp.py:1990-1991`), so the default path for any out-of-alias phrasing is the dead-end offer.

**Why this matters**
The brief reports gemma4:e4b fails 2 of 3 of these after 100-140 s. The mechanism is that a small model phrases `object_type` with natural variety ("filament spool wall mount", "pen and tool organizer", "hex desk organizer") that misses the *exact* alias set, so a part that the deterministic engine *could* build instantly is instead routed to the slow LLM-codegen offer the consumer has turned off — producing a no-result wall on the app's own first-impression prompts. This is the single worst new-user experience in the product, and it's a pipeline-robustness issue (brittle exact-match + a dead-end default), only partly a model-weakness issue. The 100-140 s cost is also paid *before* the dead-end, because the plan call runs first.

**Blast radius**
- Adjacent code: `templates.py:323-331` (`match`); `pipeline.py:447-461` (the tier decision); `Landing.tsx:9-12` (the showcased prompts); `ChatPanel.tsx:213` (the experimental-offer UI). The alias lists across all 86 families (`templates.py`) share this matching mechanism.
- Shared state: the `_index` alias map; the `experimental_enabled` setting; the model-default decision (gemma4:e4b).
- User-facing: every first-run user who clicks a landing chip; the activation/"it works" moment.
- Migration: none for data; a widened matcher changes which prompts build deterministically vs. fall back — needs a regression pass over the family-collision guard (`templates.py:309-311` rejects duplicate normalized aliases, so a fuzzy layer must run *after* exact-match and must not introduce ambiguous matches).
- Tests to update: add cases asserting the three landing prompts (and a few paraphrases) resolve to their families; `template_bench`/match tests; a pipeline test that the default config builds these rather than returning `needs_experimental`.
- Related findings: ENG-009 (the experimental dead-end is also a UX cul-de-sac); ties to the live-walkthrough's model observation.

**Fix path**
Two complementary levers, pick by appetite: (a) **widen the match net conservatively** — after exact+singular miss, try a bounded keyword/substring match against alias *head nouns* ("spool"→spool_holder, "cable clip/clip"→cable_clip, "pen"+"organizer/holder"→pen cup), gated to avoid the duplicate-alias ambiguity the collision guard already forbids; and/or run the model's `object_type` through a tiny normalization prompt or an embedding-nearest-alias step. (b) **Make the landing prompts deterministically buildable** — either pin the three showcase strings to exact aliases, or seed them with `object_type` hints. Lowest-risk immediate fix: broaden the alias lists for the three landing families and add the paraphrase-resolution test, then revisit a fuzzy layer. Independently, consider re-evaluating the default small model against these exact three prompts as a ship gate.

---

### [ENG-003] — Major — Docs (architecture) / Security-relevant — `ARCHITECTURE.md` documents the REMOVED LLM-CadQuery untrusted-codegen path as a live feature

**Evidence**
- `ARCHITECTURE.md:81` lists the LLM provider's jobs as "**Five jobs**: `generate_design_plan`, `generate_openscad`, `describe_sketch`, `generate_cadquery` (Stage 8 — the CadQuery parallel-backend codegen), and `describe_photo`."
- `ARCHITECTURE.md:91` describes the pipeline as having "a **parallel backend** … the pipeline falls back to **CadQuery codegen** (when an interpreter is available) and keeps the better result."
- The code contradicts both: the `Provider` Protocol exposes **four** methods, no `generate_cadquery` (`llm_provider.py:105-143`); the removal is explicit at `llm_provider.py:339` ("`generate_cadquery` was removed here — the LLM-CadQuery fallback's realized lift measured 0"); and `pipeline.py:79-88, 834` confirm "the LLM-CadQuery fallback backend was REMOVED." CadQuery now runs only the project's own *trusted* template twins (`webapp.py:1072-1125` lazy STEP from `emit_cadquery`), never LLM-written CadQuery. The canonical `docs/cadquery-backend.md:26-31` already records this as removed history.
- This was flagged as C2 in `docs/audits/cleanup-review-0.9.0b2-2026-06-14.md`; I confirm it independently and extend it below.

**Why this matters**
This is the *highest-risk subsystem description in the architecture doc* — the only place AI-written Python was ever exec'd. The root architecture document tells a new contributor or security reviewer that an untrusted-codegen fallback is live, when the codebase deliberately retired it. That is a phantom threat surface (a reviewer audits a path that doesn't exist) and a trap (someone re-wires `generate_cadquery` against a Protocol that no longer has it, or "restores" the exec path believing it's current). Beyond C2's two lines, the module map's `cadquery_runner`/`cadquery_worker`/`pipeline` rows (`ARCHITECTURE.md:83-84, 91`) all still frame CadQuery as the *LLM-codegen* parallel backend rather than the deterministic STEP-twin engine — so the drift is broader than the two rows the cleanup review named.

**Blast radius**
- Adjacent code: none (doc-only), but it mis-describes `llm_provider.py`, `pipeline.py`, `cadquery_runner.py`, `cadquery_worker.py`, and the `webapp` lazy-STEP path.
- Shared state: `ARCHITECTURE.md` is the contributor-facing system-of-record; `docs/cadquery-backend.md` is already correct, so they currently disagree.
- User-facing: none directly; affects contributor/security-reviewer mental model.
- Migration: doc edit only; pair with the cleanup-review's module-map omissions (`cadquery_templates.py`, `settings_store.py`, `subprocess_env.py` missing) so ARCHITECTURE.md gets one coherent pass.
- Tests to update: none exist for prose. Consider a lightweight doc-lint that greps `ARCHITECTURE.md` for `generate_cadquery` and fails (mirroring `test_version_single_source.py`'s spirit).
- Related findings: cleanup-review C2/M-arch; ENG-008 (the worker's honest "OS confinement not implemented" should also be reflected anywhere ARCHITECTURE.md implies a hard sandbox).

**Fix path**
Rewrite `:81` to four LLM jobs (drop `generate_cadquery`); rewrite `:91` so CadQuery is described as the deterministic template-STEP-twin engine, not an LLM fallback; reconcile the `cadquery_runner`/`cadquery_worker` rows to "runs the project's own trusted template-emitted CadQuery, not LLM output." Mirror `docs/cadquery-backend.md`. Add the doc-grep guard to `scripts/ci.sh` so this can't silently regress.

---

### [ENG-004] — Major — Performance / Correctness — Each `/api/design` runs the full LLM→render→gate pipeline synchronously on its request thread with no concurrency cap; thread-per-request under the threading server

**Evidence**
- `webapp.py:1972-2026` (`_handle_design`) calls `design_response(...)` inline on the request thread — that runs the plan call, OpenSCAD/CadQuery subprocess render, hardening, and gating end-to-end (`pipeline.py` `run`), a 100-140 s operation on the default local model (per the brief).
- The server is `ThreadingHTTPServer` (`_ExclusiveBindServer` subclass, `webapp.py:2556`), which spawns one unbounded thread per connection — there is no worker pool, semaphore, or in-flight cap on the expensive design route.
- Heavy shared serialization exists where it matters (`step_build_lock`, `slice_lock`, `reg.lock`), but the *design* route itself has no admission control: N concurrent design POSTs spawn N concurrent model calls + N subprocess renders.

**Why this matters**
On loopback single-user (the default and overwhelmingly common case) this is fine — a person issues one design at a time. But the route is reachable, and two failure modes are real: (1) a flaky SPA or a user mashing the button can stack multiple 100 s+ pipelines, each holding a subprocess + interpreter, thrashing CPU/RAM with no backpressure; (2) under `--allow-remote` (an explicitly supported, warned mode) any LAN client can trivially exhaust the box by firing concurrent design requests — there's no rate limit or in-flight bound, so it's a cheap local DoS on a mode the project ships. This is "plausible but not yet triggered in production," the textbook Major.

**Blast radius**
- Adjacent code: `_handle_slice`/`_handle_render` (`webapp.py:2369+`) are similarly heavy and similarly uncapped; the CadQuery probe warm-up thread (`webapp.py:2633`) and lazy STEP builds add to subprocess pressure.
- Shared state: CPU/RAM/subprocess count; `reg` registries (capped at 50, so memory of *results* is bounded, but not concurrent in-flight work).
- User-facing: latency/instability under accidental or hostile concurrency; the `--allow-remote` mode's resilience.
- Migration: none (additive admission control).
- Tests to update: add a test that a second design POST while one is in flight is queued/429'd rather than stacking (depends on chosen mechanism).
- Related findings: ENG-002 (the slow path is what gets stacked); the `--allow-remote` warning (`cli.py:491-497`) already discloses "anyone can use it" but not "anyone can exhaust it."

**Fix path**
Add a small admission gate on the expensive routes: a `threading.BoundedSemaphore` (e.g. 1-2 concurrent design/slice/render operations) that returns `429 Too Many Requests` with a `Retry-After` when full, rather than spawning unbounded heavy work. This is a ~15-line change at the top of `_handle_design`/`_handle_slice`/`_handle_render`. For `--allow-remote` specifically, document that it remains unauthenticated and now also bounded; a per-client rate limit is a larger follow-up not needed for the loopback default.

---

### [ENG-005] — Minor — Security — Connector `base_url` has no scheme allowlist before it reaches `urllib`/`socket`; a hand-edited config could point a connector at a non-HTTP scheme

**Evidence**
- `DuetConnector._request` (`duet_connector.py:93-98`) builds `urllib.request.Request(self._base + path, …)` with `self._base = base_url.rstrip("/")` straight from config/the Connections card. `MoonrakerConnector`/`PrusaLinkConnector`/`OctoPrintConnector` follow the same stdlib-`urllib` pattern.
- `apply_saved_connector_overrides` (`connectors.py:71-94`) validates the card's `base_url` only for type/length (`str`, `≤200` chars) — not scheme or host shape.
- `MarlinConnector._tcp_target` (`marlin_connector.py:128-139`) parses `host:port`/`tcp://` and otherwise treats the string as a serial port path — a `base_url` of `/dev/...` or `COM…` becomes a serial open.

**Why this matters**
The input is *not* attacker-supplied over the network — it's the user's own config file plus their own Connections card POST (which is itself behind the session token). So this is not an SSRF-from-the-web finding. But `urllib` honors `file://`, `ftp://`, etc., and a malformed/hand-edited `base_url` (or a future surface that accepts a less-trusted address) could resolve to an unintended scheme/local path with no guardrail. The blast radius today is low (self-inflicted, local), which is why this is Minor not Major — but a cheap scheme allowlist closes the class before any surface widens the trust on `base_url`.

**Fix path**
Add a shared `validate_printer_base_url(url)` (allow only `http`/`https`, require a netloc, reject userinfo) in `connectors.py`, called from `build_connector` for the HTTP connector types, and from `apply_saved_connector_overrides` for the card path. Marlin's serial/TCP target stays as-is but could reject obviously-HTTP strings for a clearer error.

---

### [ENG-006] — Minor — Security / Hygiene — The session-token-bearing index shell is served `no-cache` but not `no-store`; the token can land in a browser/proxy disk cache

**Evidence**
- `_serve_index_shell` (`webapp.py:1163-1194`) substitutes the per-boot token into the HTML body and serves it with `Cache-Control: no-cache` + an ETag (`:1186, 1193`). `no-cache` means *revalidate*, not *don't store* — the token-bearing body may be written to the browser's (or an intermediary's) disk cache and revalidated later.

**Why this matters**
For the loopback default there is no intermediary and the token rotates per boot, so exposure is small. But the token is the one bearer secret in the trust model; writing it to disk cache is gratuitous, and under `--allow-remote` an intermediary cache becomes possible. `no-store` is the correct directive for a response that embeds a per-session secret.

**Fix path**
Add `no-store` (or `no-store, no-cache, must-revalidate`) to the index-shell response and skip the ETag for it (a per-boot token body never benefits from cross-boot revalidation). Static asset caching (`_serve_static`) is unaffected and stays as-is.

---

### [ENG-007] — Minor — Dependencies / Hygiene — No documented procedure or test for regenerating `requirements.lock`

**Evidence**
- `requirements.lock` is the pinned set for CI, the installer, and the documented from-source path, but a search of `CONTRIBUTING.md`, `docs/`, and `scripts/` finds no command or policy for regenerating it. `pyproject.toml:56-65` documents *why* Playwright is excluded, but nothing documents *how* the lock is produced or *which* extras it includes — which is the root cause of ENG-001's bambu/serial asymmetry.

**Why this matters**
A lockfile that can't be reproduced from a declared command drifts silently (exactly the bambu-in/serial-out state today). The project already treats version as a single bulletproof source with a guarding test (`test_version_single_source.py`); the lock deserves the same rigor since it directly determines what ships to users.

**Fix path**
Add `scripts/regen_lock.py` (or document a `pip-compile pyproject.toml --extra bambu --extra serial`-style command) and a `CONTRIBUTING.md` note; optionally a test that the lock's top-level set matches the resolved extras, so a stray freeze can't change the shipped surface unnoticed.

---

### [ENG-008] — Minor — Security (defense-in-depth) — The CadQuery worker has no OS-level confinement (no filesystem/network jail); the sandbox rests entirely on the static sanitizer

**Evidence**
- `cadquery_worker.py:44-55` is explicit and honest: a facade function still carries its real `__builtins__` via `__globals__`, every escape needs a dunder/introspection attr that *layer 1 (the static AST sanitizer) blocks* — "so that escape class is closed by layer 1, not layer 2. The durable, defence-in-depth answer (OS-level process confinement: no network, restricted working dir) is tracked as a later hardening; it is NOT yet implemented."
- The worker subprocess runs with `scrubbed_env()` (secrets removed) but otherwise inherits the user's full filesystem and network access (`cadquery_runner.py:55-60`, `_run` at `:240`).

**Why this matters**
This is a *correctly documented* known limitation, not a hidden bug — hence Minor, and it only applies when the user has opted into the experimental generator (off by default). But it's worth keeping on the engineering watchlist: the entire CadQuery untrusted-code boundary is one regex/AST sanitizer (`sanitize_cadquery`) deep. A single missed introspection vector in layer 1 = full `import` power with the user's filesystem/network. The honest framing ("the ultimate boundary is local-machine trust") is the right disclosure; the residual risk is real for the experimental path.

**Fix path**
Track the documented OS-confinement hardening as a real backlog item (Windows job objects / restricted token, or running the worker under a restricted working dir with network disabled). Until then, keep the experimental generator off-by-default (it is) and ensure any UI that enables it restates the local-trust boundary. No code change required to *ship* b2; this is a watchlist entry.

---

### [ENG-009] — Minor — Correctness / UX — The `needs_experimental` dead-end pays the full plan-call latency before offering a path the consumer default has disabled

**Evidence**
- `pipeline.py:447-461`: the tier decision (`registry.match` → `None` → `needs_experimental`) happens **after** `generate_design_plan` has already run (the plan is needed to get `object_type`). So a user on the default config waits the full plan latency (100-140 s on the default model) only to receive an offer to enable a generator that is off by default.

**Why this matters**
Compounds ENG-002: the dead-end isn't just unsatisfying, it's *slow* to reach. The user pays the model tax and gets a toggle, not a part.

**Fix path**
Largely subsumed by ENG-002's fix (widen the match so these resolve before the dead-end). Independently, the `needs_experimental` response could surface the matched-family *suggestion* if a fuzzy near-match exists ("Did you mean a spool holder? Build it →"), turning the dead-end into a one-click deterministic build.

---

### [ENG-010] — Minor — Hygiene — `real_print_sends` is not cleared on registry eviction (small unbounded set)

**Evidence**
- `real_print_sends: set[int]` (`webapp.py:726`) gains an rid on every real (non-simulated) send (`:1834-1836`) and is read by `_handle_print_outcome` (`:1860`), but `DesignRegistry.evict_locked` (`design_registry.py:97-116`) — which clears every *other* per-rid registry in lockstep — does not touch it (it lives on the webapp closure, not the registry).

**Why this matters**
`itertools.count` never reuses an rid, so there's no correctness bug (no stale-rid collision). It's a pure slow memory leak bounded by the number of real sends in one server session — negligible in practice (a human sends a handful of prints), hence Minor. But it breaks the otherwise-clean "evict in lockstep across every per-rid structure" invariant the registry works hard to enforce.

**Fix path**
Either move `real_print_sends` into `DesignRegistry` so `evict_locked` clears it with the rest, or add a `real_print_sends.discard(old_rid)` hook where `enforce_caps_locked` runs. Low priority; do it when next touching the registry.

---

### [ENG-011] — Nit — Hygiene — `_handle_design`'s `experimental` flag defaults to `True` for an absent flag while the consumer SPA always sends `False`

**Evidence**
- `webapp.py:1995`: `allow_experimental = bool(data.get("experimental", True)) or …`. An absent flag defaults to running the experimental generator. The comment explains this is backward-compat for the API/CLI/tests, and the SPA always sends `false` — so the default only bites a hand-rolled API caller.

**Why this matters**
A surprising default (opt-out rather than opt-in) on a security-relevant toggle, mitigated by the SPA always being explicit. Defensible as documented; flagging once as a Nit because "absent → run untrusted codegen" is the kind of default that surprises a future API integrator.

**Fix path**
Consider defaulting absent → `False` and making the CLI/tests explicit, so "experimental" is opt-in everywhere. Cosmetic; no behavior change for the shipping SPA.

---

### [ENG-012] — Nit — Hygiene — `ExportPanel.tsx` uses the `#settings` fragment vs the router's `#/settings`

**Evidence**
- Flagged in the cleanup review (W-02): `ExportPanel.tsx:230` links `#settings`; the router uses `#/settings`. Works today via tolerant parsing but is fragile.

**Why this matters**
Cosmetic/robustness nit; a stricter future router would break the link. Including for completeness since it's an engineering-owned inconsistency.

**Fix path**
Normalize to `#/settings`.

---

### [ENG-013] — Nit — Hygiene — `marlin_connector._sd_name` 8-char truncation silently collides distinct designs onto one SD file

**Evidence**
- `marlin_connector.py:271-277`: the SD filename is the first 8 alphanumerics + `.gco`; the docstring acknowledges "designs sharing the first 8 alphanumeric characters reuse the same SD file (a deliberate compatibility tradeoff)."

**Why this matters**
This is a documented, deliberate firmware-compatibility tradeoff (8.3 filenames), so it's a Nit, not a defect. Worth one line because a user who sends "bracket_v1" then "bracket_v2" gets both as `BRACKET.gco` on the card — surprising, though the print itself is correct (the latest upload wins). The doc handles it.

**Fix path**
Optionally append a short hash suffix within the 8.3 budget (e.g. 4 chars of name + 4 of a content hash) if collisions prove confusing in the field. Not needed for b2.

---

## Patterns and systemic observations

1. **The security primitives are strong; the gaps are at the seams between code and its distribution/description.** The token guard, the bind, the sanitizers, the connector escaping, and the send-confirmation chain are all correct and *honestly documented*. The Major findings cluster instead at (a) packaging/provenance (ENG-001/007 — what actually ships vs. what the manifest says), (b) the architecture doc lagging a deliberate code removal (ENG-003), and (c) the consumer-default *experience* of the tiered engine (ENG-002/009). None of these is a code-correctness bug in the security core — they're integrity-of-the-whole-system issues, which is exactly where a disciplined codebase tends to drift.

2. **The tiered deterministic-first engine is the right architecture, but its match gate is too literal for a small-model front door.** Exact-alias matching is correct for *avoiding wrong matches*; it's brittle for *catching right ones* when the upstream is a 4B local model with natural phrasing variety. The fix is not to abandon determinism — it's to add one conservative resolution layer between the model's `object_type` and the alias index (ENG-002). This single root cause produces both the landing-prompt failures and the slow dead-end (ENG-009).

3. **"Honest disclosure" is a genuine strength worth preserving.** The codebase repeatedly documents its own limits precisely (the worker's `__globals__` caveat, the `--allow-remote` "NO auth" warning, the keyring/file fallback disclosure, the SD-filename collision note). This is rare and valuable. The one place it failed — ARCHITECTURE.md still claiming a removed exec path is live (ENG-003) — is the exception that proves the value of the rule, and argues for a doc-grep guard in CI so the prose can't drift from the code.

## Dependency snapshot

`pip-audit -r requirements.lock` → **No known vulnerabilities found.** Tree is otherwise clean and current.

| Dependency | Version | Concern |
|---|---|---|
| `bottle` | 0.13.4 | Full HTTP framework shipped to **all** installer users (transitive via the *optional* `bambulabs-api`); never imported by KimCad. Supply-chain surface for non-Bambu users — see ENG-001. |
| `pythonnet` | 3.1.0 | A .NET CLR loader shipped to all installer users (transitive via `pywebview`/`bambulabs-api`). Legitimate for the WebView2 shell on Windows; verify it's actually required for the shell vs. only pulled by the bambu chain. |
| `paho-mqtt` | 2.1.0 | MQTT stack shipped to all installer users (transitive via `bambulabs-api`); only reachable on the Bambu path. See ENG-001. |
| `bambulabs-api` | 2.6.6 | Declared **optional** (`bambu` extra) in `pyproject.toml` but present in `requirements.lock` → bundled for everyone. The asymmetry with the un-bundled `serial`/`pyserial` extra is the heart of ENG-001. |
| `openai` | 2.41.0 | Used as the universal client for *local* OpenAI-compatible endpoints (Ollama/LM Studio) and optional cloud; fine. Note lock is on 2.x while `pyproject.toml` floors `openai>=1.40` — wide but harmless. |
| Core geom (`trimesh` 4.12, `numpy` 2.2, `scipy` 1.17, `manifold3d` 3.5, `networkx` 3.6, `lxml` 6.1) | — | Current, no advisories. `manifold3d` correctly a hard pin with a defensive runtime guard (`hardening.py`). |

## Appendix: artifacts reviewed

- **Backend (read in full or in depth):** `webapp.py` (POST guard, bind, index-shell, `_handle_design`/`_handle_send`/`_serve_step`/`_read_json_body`, registry caps), `connectors.py`, `marlin_connector.py`, `duet_connector.py`, `printer_connector.py` (head), `openscad_runner.py`, `cadquery_runner.py` (head), `cadquery_worker.py`, `subprocess_env.py`, `hardening.py`, `settings_store.py` (head), `model_pull.py` (loopback guards), `llm_provider.py` (Protocol, `generate_design_plan`/`generate_openscad`, removal note), `pipeline.py` (tier/match/fallback, removal notes), `ir.py` (full — plan parse/normalize/clarify), `slicer.py` (slice argv), `cli.py` (`web` host/allow-remote), `design_registry.py` (full).
- **Frontend:** `Landing.tsx` (showcase prompts), `ChatPanel.tsx`/`App.tsx` (experimental offer wiring), `api.ts` (endpoint shape), component inventory.
- **Packaging/gate:** `pyproject.toml`, `requirements.lock`, `scripts/build_installer.py` (lock install + release strip), `scripts/ci.sh`, `.github/workflows/ci.yml` (lock consumers), `CONTRIBUTING.md`.
- **Docs:** `ARCHITECTURE.md` (module map + LLM/pipeline rows), `docs/audits/cleanup-review-0.9.0b2-2026-06-14.md` (verified + extended C2; cross-checked C1/M1).
- **Verification run this pass:** `ruff check src tests` → clean; `pytest -m "not live and not real_tool and not needs_cadquery and not needs_browser"` → **1249 passed, 313 deselected**; `pip-audit -r requirements.lock` → **no known vulnerabilities**.
