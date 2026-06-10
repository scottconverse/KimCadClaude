# Engineering Deep-Dive — KimCad, Stage 9 (image & sketch on-ramp)

**Audit date:** 2026-06-10
**Role:** Principal Engineer
**Scope audited:** The Stage 9 diff only — git range `574b7c4..e8339d9` (commit e8339d9): `src/kimcad/design_registry.py` (new), `webapp.py` rewiring, `llm_provider.py` vision-model targeting + `VisionModelMissing`, `config.py` (`LLMBackend.vision_model`), `cli.py` models output, frontend `PhotoOnramp`/`Landing`/`api.ts`, and the Stage 9 tests. Walkthrough report (zero findings) verified against source, not re-run.
**Auditor posture:** Adversarial — six specific hunt directives (alias-rebinding seam, `_locked` contract, counter atomicity, HTTPError mapping, `vision_model` on cloud backends, sketch attack surface).

---

## TL;DR

The `DesignRegistry` extraction is the right refactor done carefully: the three load-bearing protocols (lockstep eviction, cap enforcement, geometry-version guard) are now methods instead of comments, every `_locked` call site verifiably holds `reg.lock`, and the transitional alias seam is clean — all eleven aliased names are bound exactly once and never reassigned. The sketch on-ramp reuses the photo path's guards (12 MiB cap, localhost bind, nothing persisted, local-only vision) with full parity. The one finding that matters: the new `HTTPError` handling maps **only 404** to a typed error, so a realistic Ollama 5xx (out-of-memory loading the 3B vision model, runner crash) falls through to the 422 "try a clearer shot" — the exact blame-the-user misattribution this stage's QA-A-003 lineage set out to eliminate, and that branch logs nothing server-side. Everything else is hygiene.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 3 |
| Nit | 1 |

## What's working

- **The alias-rebinding seam is provably clean.** `rg '^\s*(registry|gcode_registry|step_registry|gate_status_by_rid|geometry_version|slice_cache|template_state|design_snapshot|rid_saved_id|lock|_evict)\s*='` over `webapp.py` returns exactly the eleven binding lines (689–698, 767) and nothing else. Every subsequent use is an in-place mutation (`registry[rid] = …`, `.move_to_end`, `.get`, `.pop`) of the *same* objects `reg` owns, so the aliases cannot diverge from `reg`'s fields. The seam is also honestly documented as transitional with the Stage-10 flattening named in both the module docstring (design_registry.py:17–18) and the binding comment (webapp.py:683–687).
- **The `_locked` contract is honored at every call site.** All six `_locked` invocations sit inside a `with lock:` block: `enforce_caps_locked` at webapp.py:1565 (block opens 1540) and 1717 (block opens 1692); `register_gcode_locked` at 1809 (block 1806); `cache_slice_locked` at 1896 (block 1893); `bump_version_locked` at 1979 and `next_mesh_version` at 1994 (block 1971). `new_rid` (1486, 1678) correctly takes the lock itself. No direct mutation of `reg`'s collections bypasses a protocol it should use — the remaining direct writes (`registry[rid] = mesh_path`, `gate_status_by_rid[rid] = …`, `template_state[rid] = …`, `design_snapshot[rid] = …`) are registration writes the protocols never claimed to own, all under `lock`.
- **The version-guard semantics survived the refactor byte-for-byte.** `bump_version_locked` is exactly the old three-step (bump + gcode pop + cache sweep) folded into one method; `register_gcode_locked`/`cache_slice_locked` reproduce the old compare-then-write under the same lock, and the slice handler still captures `sliced_ver` in the same consistent-snapshot read (webapp.py:1837–1842). `tests/test_design_registry.py` pins the race-window behavior in both directions, and the walkthrough's live journey 5 (slice → re-render → old G-code 404s) confirms it end-to-end.
- **Sketch/photo security parity is real.** Both endpoints share `MAX_PHOTO_BYTES` (12 MiB, webapp.py:58, enforced server-side at 1377/1415 via the same `_read_raw_body` 413 guard and mirrored client-side in `api.ts` `uploadSketch`), the server binds `127.0.0.1` by default (webapp.py:2016), nothing is persisted, and the image is base64'd to *local* Ollama only. The seed output re-enters the system as untrusted text into the validated DesignPlan path — the same trust boundary as typed input.
- **`VisionModelMissing` is a well-shaped typed error** — carries the model name, embeds the exact `ollama pull` recovery command, and both endpoints map it before the generic branches (webapp.py:1395–1397, 1431–1433). Unit tests pin the 404→typed mapping, the dedicated-model targeting, and the web-layer mapping for both on-ramps (`test_llm_provider.py`, `test_webapp.py`).
- **The frontend parameterization is the cheap, correct shape** — one `KIND_COPY` table differing only in endpoint, copy, and glyph; no logic forked, so photo-path fixes automatically cover the sketch path.

## What couldn't be assessed

- Runtime behavior (real vision model, live race reproduction) — deliberately out of scope; the walkthrough covered it and its claims were verified against source instead.
- Free-threaded CPython behavior of `itertools.count` (ENG-004's note) — assessed from CPython semantics, not executed on a 3.13t build (the project targets standard 3.13, where the GIL claim holds).
- The walkthrough's own limitation stands: the vision-model-missing path was proven by unit test + string match, not by deleting the model live. The source verification here (404 mapping + both endpoint branches + tests) supports its claim.

---

## Findings

> **Finding ID prefix:** `ENG-`

### [ENG-001] — Major — Correctness — A non-404 Ollama HTTPError (5xx/429) blames the user's image and logs nothing

**Evidence**
`src/kimcad/llm_provider.py:402–410`:

```python
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise VisionModelMissing(self.backend.vision_model) from e
            raise
```

The re-raised `HTTPError` reaches the endpoint's catch-all (`webapp.py:1387–1403` photo, 1425–1439 sketch). It is not `VisionModelMissing`; `_is_model_unreachable` (pipeline.py:186–189) matches only class names `{"APIConnectionError", "APITimeoutError"}` — `HTTPError` is neither — so the handler falls through to `self._json(422, cant_read)`: *"Couldn't read that photo — try a clearer shot…"*. That branch has no `self.log_error(...)`, so the actual Ollama status code and error body vanish entirely.

**Why this matters**
Ollama answers HTTP 500 for several states that are *common on exactly this stage's target box*: "model requires more system memory" when loading qwen2.5vl:3b alongside the chat model, a crashed runner, or a corrupt model blob. It can also answer 429/503 under load. In every one of those cases the user is told their image was unreadable and to "try a clearer shot" — the precise trust-breaking misattribution that QA-A-003 and this very stage's `VisionModelMissing` work were built to eliminate. The user retries with better photos against a server that is failing for reasons no photo can fix, and the operator has zero server-side trace to diagnose it (the design endpoint's catch-all logs at webapp.py:1526; the two vision endpoints don't).

**Blast radius**
- Adjacent code: both `_handle_photo_seed` and `_handle_sketch_seed` share the branch shape — fix once in `_describe_image` (or a shared helper) and both inherit it. `pipeline._is_model_unreachable` is shared with the design path; widening it to swallow `HTTPError` there would wrongly classify cloud-backend 4xx as "model down", so the fix belongs in the vision layer, not in `_is_model_unreachable`.
- User-facing: the photo and sketch on-ramps' error copy under server-fault conditions changes from blame-the-image to an honest "your local AI hit a problem" with a server-side log line.
- Migration: none — additive error mapping.
- Tests to update: none break; add one (`HTTPError` 500 → typed/honest message + logged) beside `test_missing_vision_model_raises_typed_with_pull_command`.
- Related findings: ENG-005 (the `e.fp` close belongs in the same handler).

**Fix path**
In `_describe_image`, handle the non-404 branch explicitly: read a bounded prefix of `e.read()` (Ollama puts the reason in the body), log it to stderr (or raise a typed `VisionServerError(status, detail)` the web layer maps to `model_unavailable`-style copy: "Your computer's AI hit a problem reading the image — it may be out of memory. The terminal running `kimcad web` has the detail."), and `e.close()`. In the web handlers, add a `self.log_error` before the 422 fallback so *no* vision failure is ever silent server-side.

---

### [ENG-002] — Minor — Security — The "vision stays local" promise is enforced only by routing convention; `_describe_image` would post the image to a cloud `/api/chat` if ever reached on a cloud backend

**Evidence**
`LLMBackend.vision_model` defaults to `"qwen2.5vl:3b"` on **every** backend, cloud included (config.py:81, 306). `LLMProvider._describe_image` derives its URL from whatever `backend.base_url` it holds (llm_provider.py:371–376) — for `custom_openrouter` that is `https://openrouter.ai/api/chat` — and would transmit the base64 image off-machine before failing on the unknown model. `FallbackProvider.describe_photo/describe_sketch` (llm_provider.py:525–534) delegate to their primary, which is the *active* backend (`_real_provider`, webapp.py:381–387) — a cloud backend when `llm.active` or `--backend` says so. The only thing preventing this today is that the web layer always wraps the provider in `_SettingsAwareProvider`, whose `describe_*` explicitly build `LLMProvider(self._config.llm_backend("local"))` (webapp.py:456–471), and no CLI path calls `describe_*`.

**Why this matters**
The privacy line shown to the user ("It never leaves your machine") is a hard product promise, currently guaranteed by a single routing layer plus the absence of other callers — both acknowledged in comments ("the trust rule … is enforced by the caller, not here", llm_provider.py:117–119). One future caller that grabs `pipeline.provider` before wrapping, or a CLI vision command added without re-reading that comment, silently ships the image to the configured cloud router. The misleading `vision_model` default on cloud backends (a local Ollama tag on an OpenRouter config) makes that failure quieter, not louder. Exposure today is theoretical — hence Minor, not Critical — but it's a one-line guard away from being structural.

**Blast radius**
- Adjacent code: `_describe_image` (one guard covers photo + sketch); `FallbackProvider.describe_*` could alternatively refuse rather than delegate.
- User-facing: none today; the guard only changes behavior on a path that must never execute.
- Tests to update: add one asserting `_describe_image` raises on a non-local `base_url`.
- Related findings: none in this audit.

**Fix path**
Add a cheap structural assert at the top of `_describe_image`: if the derived host is not loopback (`localhost`/`127.0.0.1`/`::1`), raise a typed error ("vision is local-only; refusing to send an image to a remote endpoint") instead of posting. Optionally make `vision_model` default `None` on non-local backends in `Config.llm_backend` so the field stops implying cloud vision exists.

---

### [ENG-003] — Minor — Hygiene — `_evict = reg.evict_locked` is a dead binding

**Evidence**
`webapp.py:767` binds `_evict`, but `rg '_evict\('` over `src/` finds no call site — the two former callers (the cap loops) became `reg.enforce_caps_locked(...)` (webapp.py:1565, 1717), which calls `evict_locked` internally.

**Why this matters**
A dead alias on a *lock-required* method is a small trap: a future handler author seeing `_evict` available may call it outside `lock` (the name no longer carries the `_locked` suffix that signals the contract).

**Fix path**
Delete the binding; if a handler ever needs direct eviction, call `reg.evict_locked` so the suffix travels with the call. Fold into the scheduled Stage-10 name flattening.

---

### [ENG-004] — Minor — Hygiene — design_registry docstrings: a phantom method name and a build-dependent atomicity claim

**Evidence**
1. The module docstring cites ``:meth:`try_register_slice` `` (design_registry.py:12) — no such method exists; the protocol is implemented by `register_gcode_locked` + `cache_slice_locked`.
2. `next_mesh_version` (design_registry.py:76–79) claims "the counter itself is GIL-atomic" and, unlike `new_rid` (which takes the lock), relies on it. The claim is true on standard CPython (a single C-level `next()` on `itertools.count` cannot interleave under the GIL) and the sole call site (webapp.py:1994) holds `reg.lock` anyway — so this is **not a live bug**. But the claim is build-dependent: on free-threaded CPython (3.13t/3.14t), `itertools.count` is not thread-safe and can yield duplicates, which here would mean a duplicated cache-buster letting a browser serve a stale cached mesh after a re-render. The project targets standard Py 3.13, so today the asymmetry is only a documentation/consistency hazard.

**Why this matters**
The module's whole reason to exist is "invariants are methods now, not comments" — a docstring pointing at a method that isn't there, and a thread-safety claim that quietly assumes a specific interpreter build, erode exactly the discipline the file establishes. A reader extracting `next_mesh_version` to a new call site without the lock would be following the docstring's explicit permission.

**Fix path**
Fix the `:meth:` reference. For `next_mesh_version`, either take `self.lock` like `new_rid` (the call is rare; the cost is nil) or rewrite the docstring to "REQUIRES the caller to hold the lock" and drop the GIL claim — pick one contract, not both.

---

### [ENG-005] — Nit — Hygiene — The slice handler reads `geometry_version` through the alias instead of `reg.version_locked`

**Evidence**
`webapp.py:1842`: `sliced_ver = geometry_version.get(rid, 0)` (under `lock`) — semantically identical to `reg.version_locked(rid)`, which exists for exactly this read and is otherwise only used by tests.

**Why this matters**
It's the one protocol-3 touch still expressed as a raw dict read; when the Stage-10 flattening deletes the aliases this line must be converted anyway. Converting it now makes protocol 3 fully method-mediated and keeps `version_locked` from looking test-only. Relatedly, the `HTTPError.fp` left open in the 404 branch (llm_provider.py:409 — `e.close()` never called, relies on GC) is the same grade of tidiness; both belong in the ENG-001 touch-up.

**Fix path**
Replace with `reg.version_locked(rid)`; add `e.close()` in the `HTTPError` handler while ENG-001 is being fixed.

---

## Patterns and systemic observations

- **The refactor's discipline held under adversarial inspection.** The two failure modes this kind of extraction usually ships — an alias reassigned somewhere deep in a handler, or a `_locked` method called bare — are both absent, with grep-provable evidence. The "transitional seam" framing is honest and the exit (Stage-10 flattening) is already scheduled; ENG-003/ENG-005 are the punch list for that flattening.
- **The error-mapping pattern has one recurring blind spot: the middle of the status-code range.** Stage 9 (like QA-A-003 before it) maps the *named* failure states (connection down, 404) to honest typed responses and lets everything else fall into "your input was bad." ENG-001 is the third instance of this shape; the durable fix is a rule, not a patch: *any server-fault response (>=500) from a dependency must never be presented as a user-input problem, and must always log.* Worth writing into the webapp's error-handling conventions comment so Stage 10's direct-print UI (which will talk to printers — another HTTP dependency) doesn't repeat it.
- **Trust-boundary promises enforced at exactly one layer** (ENG-002) is the only structural risk this diff adds. One assert moves the promise from convention to mechanism.

## Dependency snapshot

No dependencies added or version-bumped in this range — the vision call uses stdlib `urllib`; the frontend change is component-local. Dependency surface of the diff is clean.

## Appendix: artifacts reviewed

- `docs/audits/walkthrough-stage-9-2026-06-10/WALKTHROUGH-REPORT.md` (claims verified in source)
- `git diff 574b7c4..e8339d9` (full), commit e8339d9
- `src/kimcad/design_registry.py` (entire file)
- `src/kimcad/webapp.py` — bindings 680–770; handlers: photo/sketch seed 1372–1444, design 1446–1569, save 1594–1660, reopen 1670–1731, raw-body 1784–1799, slice/respond 1801–1897, render 1899–1995; send 1303–1370; server bind 2000–2032
- `src/kimcad/llm_provider.py` — Provider protocol 100–135, `_describe_image`/describe_* 352–437, `FallbackProvider` 440–534, `VisionModelMissing` 51–62
- `src/kimcad/webapp.py` `_SettingsAwareProvider` 390–471, `DemoProvider.describe_*` 344–358, `build_web_pipeline`/`_real_provider` 361–387
- `src/kimcad/config.py` 73–81, 297–307; `src/kimcad/cli.py` 504–515; `src/kimcad/pipeline.py` 186–189
- `frontend/src/api.ts` (uploadSketch), `frontend/src/components/PhotoOnramp.tsx`, `Landing.tsx` (diff)
- `tests/test_design_registry.py`, `tests/test_llm_provider.py` (Stage 9 additions), `tests/test_webapp.py` (Stage 9 additions)
