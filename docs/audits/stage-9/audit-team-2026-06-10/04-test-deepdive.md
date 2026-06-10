# Test Suite Deep-Dive — KimCad (Stage 9 diff, scoped)

**Audit date:** 2026-06-10
**Role:** Test Engineer
**Scope audited:** The Stage 9 diff's test story only — commit `e8339d9`, range `574b7c4..e8339d9`. Test artifacts: `tests/test_design_registry.py` (new), `tests/test_llm_provider.py` (+2), `tests/test_webapp.py` (sketch/photo-seed + vision-missing additions, 1 rewritten), `tests/test_fallback_provider.py` (Stage 9 delegation test), `frontend/src/components/PhotoOnramp.test.tsx` (+3 sketch-mode), `frontend/src/api.test.ts` (unchanged — that absence is itself a finding), `frontend/src/App.test.tsx`, `frontend/src/components/FirstRunWizard.test.tsx`.
**Auditor posture:** Adversarial (stage-gate)

---

## TL;DR

The Stage 9 test story is mostly honest work: the five DesignRegistry protocol tests exercise the real methods (not mocks), the vision-model swap correctly retired every stale `think:false`/gemma-vision assertion, both image endpoints have a route-level test pinning the typed `ollama pull` hint, and the new sketch UI tests drive a **real `File` through the input-change event** — the walkthrough's "no real File" concern is materially overstated. The two genuine holes are quieter: `uploadSketch` (the sketch on-ramp's entire client transport contract — size cap, model-unavailable mapping, abort) has **zero** tests while its `uploadPhoto` twin has five; and the lockstep-eviction test asserts "every registry" while **silently excluding `meshes`**, pinning an asymmetry that — combined with the webapp's fail-open gate read — makes any future direct `evict_locked` call a gate-bypass seam. The transitional alias-rebinding seam is only partially pinned: four of nine aliases would fail a test if reassigned; five would not.

## Severity roll-up (tests)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **The protocol tests test the real object.** `tests/test_design_registry.py` constructs a real `DesignRegistry` against a real tmp filesystem — no mocks anywhere in the file. The version-guard test (`test_version_guard_drops_a_stale_slice_and_gcode`, lines 62–75) is a model regression test: it simulates the exact mid-slice re-render race the 2026-06-09 audit flagged, asserts both the refusal AND that the current version still registers.
- **The old vision behavior was cleanly retired, not left to rot.** `tests/test_webapp.py:2854` was *rewritten* (`test_llm_describe_photo_uses_native_chat_with_the_vision_model`): the `assert captured["body"]["think"] is False` pin became `assert captured["body"]["model"] == "qwen2.5vl:3b"`. I grepped every test file for `think`/`gemma`: the remaining gemma4 assertions (`test_model_advisor.py`, `test_bakeoff.py`, `test_cli.py:378`, `test_webapp.py:2307`) all concern the **chat** model, where gemma4:e4b is still correct. No test asserts the old broken vision wiring.
- **The wizard trust test was sharpened, not weakened.** `FirstRunWizard.test.tsx:44–55` replaced the now-too-broad `queryByText(/qwen/i)` with the actual invariant: no `qwen2.5-coder`, exactly ONE `.kc-wiz-modelcard`. That's pinning intent, not strings.
- **Both image endpoints' typed missing-model path is route-tested in one loop.** `test_webapp.py:3156` (`test_photo_and_sketch_seed_map_missing_vision_model_to_typed_pull_hint`) drives real HTTP through `_serve`, asserts `ollama pull qwen2.5vl:3b` appears and `"clearer"` does **not** — the negative assertion guards the exact trust failure (blaming the user's image) Stage 9 set out to fix.
- **The component tests drive a real `File`.** `PhotoOnramp.test.tsx:28–34` (`pickFile`) dispatches `fireEvent.change` on the real `<input type="file">` with a real `File`, and the sketch tests walk input-change → reading → confirm-card → `onSeed` (`PhotoOnramp.test.tsx:175–190`), including the endpoint-routing assertion `expect(mockUpload).not.toHaveBeenCalled()`.
- **The 404→typed-error mapping has a unit pin with the recovery command asserted** (`test_llm_provider.py:test_missing_vision_model_raises_typed_with_pull_command`).
- **Verified runs (this audit, this machine):** `pytest tests/test_design_registry.py tests/test_llm_provider.py tests/test_fallback_provider.py` → 42 passed; `pytest tests/test_webapp.py -k "seed or vision or evicted or rerender"` → 20 passed; `vitest src/components/PhotoOnramp.test.tsx src/api.test.ts` → 60 passed.

## What couldn't be assessed

- **CI history / flakiness over time** — single-machine audit; no access to runner history. No `retries` config found in vitest/pytest config, which is the right posture.
- **The live 5/5 on-target vision benchmark** claimed in the commit message (`docs/benchmarks/stage-9-vision-onramps.md`) — requires the target box with Ollama + qwen2.5vl:3b pulled; not reproducible here. Taken as documented, not verified.

---

## Test landscape

| Dimension | Observation |
|---|---|
| Framework(s) | pytest (backend), Vitest + Testing Library (SPA) |
| Test pyramid shape | Heavy unit + genuinely-integrated route tests (real `BaseHTTPRequestHandler` over real sockets via `_serve`); component tests with real DOM events, mocked at the network-function seam; no browser E2E (walkthrough skill fills that role manually) |
| Coverage tool | none configured (no coverage numbers claimed — honest) |
| Flakiness posture | clean; no retry config; the one timing-sensitive area (mid-slice re-render) is tested deterministically via the version protocol, not sleeps |
| CI blocking? | yes — `tests/conftest.py:92` turns missing hard deps RED on CI instead of skipping (zero-skip gate); all 25 `skipif`s in the suite are conditional live-dep guards (cadquery/OpenSCAD/manifold), none in Stage 9 files |

---

## Findings

### [TEST-001] — Major — Coverage — `uploadSketch`'s entire client transport contract is untested; its `uploadPhoto` twin has five tests

**Evidence**
`frontend/src/api.ts:391–411` adds `uploadSketch`: 12 MB size cap, fetch to `/api/sketch-seed`, abort passthrough, network-error copy, and the `status === 'model_unavailable'` → thrown-Error mapping. `frontend/src/api.test.ts` has a five-test `describe('uploadPhoto (Slice 7)')` block (lines 142–191: happy path, size cap, abort signal, network error, unreadable) and **zero** tests touching `uploadSketch` (grep: `uploadSketch` appears in `api.test.ts` nowhere). The component tests mock `uploadSketch` (`PhotoOnramp.test.tsx:10`), so nothing anywhere executes the real function under test.

**Why this matters**
This is the one place the walkthrough's "mocked at the upload-function seam" observation lands — not at the component (which does drive a real File), but at the function below the mock seam, which is net-new code with no test on either side of it. The bug class: if the `model_unavailable` mapping regresses (e.g. a refactor drops the status check), the response flows through as `{status, error}` with no `seed` → the component's empty-seed branch fires → the user sees *"try a clearer image with written dimensions"* for a missing model — precisely the user-blaming failure Stage 9's server side just eliminated. A size-cap or abort regression is equally invisible. `uploadSketch` is a near-copy of `uploadPhoto`; copy-paste twins drift, and only one twin is pinned.

**Blast radius**
- Adjacent code: `frontend/src/api.ts` `uploadPhoto`/`uploadSketch` pair; `PhotoOnramp.tsx` `KIND_COPY.sketch.upload`.
- User-facing: the sketch on-ramp — one of the two headline Stage 9 features — on Landing and workspace.
- Tests to update: none break; add ~5 tests mirroring the `uploadPhoto` block (the fetch-stub harness is already there).
- Related findings: TEST-004 (same negative-space discipline, server side).

**Fix path**
Clone the `uploadPhoto (Slice 7)` describe block for `uploadSketch` in `frontend/src/api.test.ts`: endpoint URL is `/api/sketch-seed`, size cap throws `/too large/`, abort forwards, network error says "sketch" not "photo", and — the one the photo block lacks too — `{status: 'model_unavailable', error: '…ollama pull…'}` rejects with the server's message verbatim. ~30 minutes.

---

### [TEST-002] — Major — Quality — The lockstep-eviction test asserts "EVERY registry" while silently excluding `meshes`; the exclusion is fail-open at the gate

**Evidence**
`src/kimcad/design_registry.py:83–95`: `evict_locked` pops `gcode`, `step`, `gate_status`, `geometry_version`, `template_state`, `snapshot`, `saved_id`, `slice_cache` — **not `self.meshes`**. The class docstring (line 7) says "dropping a design id must clear EVERY registry it appears in." The test `test_eviction_is_lockstep_across_every_registry_and_disk` (tests/test_design_registry.py:25–48) populates eight registries but never puts `rid` in `reg.meshes`, so the asymmetry is invisible to the suite. The contract is real but implicit: the only caller, `enforce_caps_locked` (line 103), pops `meshes` first. Meanwhile `src/kimcad/webapp.py:1317` and `:1839` read the gate **fail-open**: `gate_failed = gate_status_by_rid.get(rid) == "fail"` — a missing verdict is treated as not-failed.

**Why this matters**
The class of bug: a future caller (a Stage-10 DELETE-design endpoint, a session-reset handler — both plausible) calls `evict_locked(rid)` on a live design, reasonably trusting the docstring and the test name. Result: the mesh stays registered and servable at `GET /api/mesh/<rid>` while its gate verdict is gone — so `POST /api/slice/<rid>` on a gate-FAILED part now passes the fail-open check at webapp.py:1839 and slices/sends a part the printability gate rejected. ENG-001's server-side gate refusal is the project's signature safety property; the test suite currently pins the seam that would bypass it as correct. Unreachable today (verified: `evict_locked` has exactly two references — `enforce_caps_locked` and the dead `_evict` alias at webapp.py:767), which is why this is Major-latent rather than Critical.

**Blast radius**
- Adjacent code: `enforce_caps_locked` (pops `meshes` itself — popping again inside `evict_locked` is a harmless no-op, so the fix is safe for the existing caller); the dead `_evict = reg.evict_locked` alias at webapp.py:767.
- Shared state: `reg.meshes` ↔ `GET /api/mesh/<id>`; `reg.gate_status` ↔ the slice/send gate refusal (ENG-001).
- User-facing: none today; gate bypass on the first future direct-evict caller.
- Tests to update: `test_eviction_is_lockstep_across_every_registry_and_disk` — add `reg.meshes[rid] = d / "m.stl"` to the setup and `assert rid not in reg.meshes`; `test_cap_enforcement_runs_full_eviction_for_the_fallen` keeps passing unchanged.
- Related findings: TEST-006 (evict edge cases), engineering deep-dive's registry findings if any; the fail-open gate read itself is an engineering-role concern worth cross-tagging.

**Fix path**
Add `self.meshes.pop(rid, None)` as the first line of `evict_locked` and extend the lockstep test to include `meshes` (two lines each). Alternatively, if the dev wants meshes-stays-caller-owned, the docstring and the test name must both say so explicitly — but making the method match its own contract is cheaper and strictly safer.

---

### [TEST-003] — Major — Regression — The alias-rebinding seam is only partially pinned: reassigning 5 of the 9 transitional aliases would pass the entire suite

**Evidence**
`src/kimcad/webapp.py:688–697` binds nine local names to `reg`'s fields (`registry = reg.meshes` … `rid_saved_id = reg.saved_id`) — the documented transitional seam, correct only as long as every assignment **mutates** the shared object and nobody **rebinds** the local name. I traced which aliases are cross-pinned (a route test fails if the alias is reassigned to a fresh dict because the alias side and the `reg.`-method side would diverge):

| Alias | Cross-pinned by | Rebinding fails a test? |
|---|---|---|
| `registry` (meshes) | `test_evicted_design_dir_is_removed_from_disk` (test_webapp.py:1180) — writes via alias, evicts via `reg.enforce_caps_locked` | **yes** |
| `gcode_registry` | slice/download tests — write via `reg.register_gcode_locked`, read via alias | **yes** |
| `slice_cache` | cache-hit + `test_rerender_invalidates_a_cached_slice` (1607) | **yes** |
| `geometry_version` | `test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale` (1637) — captured via alias (webapp.py:1842), compared via `reg.register_gcode_locked` | **yes** |
| `gate_status_by_rid` | written (1547) and read (1317/1839) only via the alias; `reg.gate_status` touched only by `evict_locked` | **no** |
| `step_registry` | alias-only write (1543) / read (944) | **no** |
| `template_state` | alias-only (1551/1910/1981) | **no** |
| `design_snapshot` | alias-only (1561/1611/1987) | **no** |
| `rid_saved_id` | alias-only (1627/1630) | **no** |

For the five "no" rows, a reassignment severs lockstep eviction silently: evicted designs' gate verdicts, STEP paths, template state, snapshots, and saved-id mappings accumulate forever in the rebound dicts — re-introducing exactly the unbounded-state growth ENG-004 exists to prevent, with no failing test and no visible symptom until memory pressure.

**Why this matters**
The seam lives until Stage-10-start flattening (documented in the module docstring), which means at least one more slice of handler edits happens on top of it. "Mutate, never rebind" is a one-keystroke-to-violate invariant (`gate_status_by_rid = {}` in a misguided "reset" branch), and five-ninths of it is unguarded.

**Blast radius**
- Adjacent code: every handler in `make_handler`; the Stage-10 flattening task (which retires this finding entirely — pin cheaply now, don't gold-plate).
- Tests to update: none break; one test extends.
- Related findings: TEST-002 (the cross point for the unpinned five IS `evict_locked`); the dead `_evict` alias (Nit, below).

**Fix path**
Cheapest pin, no new harness: extend `test_evicted_design_dir_is_removed_from_disk` (test_webapp.py:1180) to also assert, after the third design evicts the first, that `GET /api/step/1` → 404 and `POST /api/designs/save` for rid 1 → 404 (snapshot gone). That crosses the alias↔`reg` seam for `step_registry` and `design_snapshot` through real routes. `gate_status_by_rid`/`template_state`/`rid_saved_id` have no clean post-eviction route observable (the mesh 404s first), so for those, accept the residual risk and let Stage-10 flattening retire it — note it in the flattening task so the aliases are deleted, not migrated.

---

### [TEST-004] — Minor — Coverage — No negative-space test: a non-404 `HTTPError` must NOT map to `VisionModelMissing`

**Evidence**
`src/kimcad/llm_provider.py:403–410` maps only `e.code == 404` to `VisionModelMissing`; everything else re-raises. `tests/test_llm_provider.py` tests the 404 arm only. Nothing pins that a 500 (Ollama OOM-killing the model is a real occurrence) does **not** produce the "run `ollama pull`" message.

**Why this matters**
The 404-only restriction is load-bearing for message accuracy: a refactor widening the except to all `HTTPError`s would pass the entire suite, and a user with the model already pulled would be told to pull it — an un-followable instruction, the same trust failure in a new coat. Secondary observation for the cross-role pass: today a 500 falls through `_is_model_unreachable` (pipeline.py:189 — name-matched `APIConnectionError`/`APITimeoutError` only, and the native-`urllib` vision path raises neither) to the generic 422 *"try a clearer shot"* — so an Ollama-side 500 still blames the user's image. The chosen behavior, whatever it is, deserves a pin.

**Blast radius**
- Adjacent code: the twin `except` blocks in webapp.py photo-seed/sketch-seed handlers.
- Tests to update: none; add one (~10 lines, the `_404` monkeypatch helper already in the file generalizes).
- Related findings: TEST-001 (negative-space discipline on the client side).

**Fix path**
One unit test: monkeypatch `urlopen` to raise `HTTPError(…, 500, …)`, assert the raise is `HTTPError` (not `VisionModelMissing`). Optionally one route test pinning what the user sees on a 500.

---

### [TEST-005] — Minor — Coverage — The new `kimcad models` vision line is executed by existing tests but never asserted

**Evidence**
`src/kimcad/cli.py:504–515` adds the vision-model status line with three behaviors: "installed", "NOT installed -- ollama pull qwen2.5vl:3b", and an `except Exception` fallback to the hardcoded name. `tests/test_cli.py:366–399` (`test_models_command_prints_hardware_and_recommendation`, `test_models_command_handles_no_ollama`) run the command — line coverage without assertion — and grep for `vision` across `test_cli.py` returns nothing.

**Why this matters**
The commit positions `kimcad models` as "the one-stop setup check" for the vision model. If the `any(m.name == vision …)` comparison regresses (e.g. quantized-tag matching — note the chat model needed exactly that fix, `_model_matches` with tag-suffix handling, test_model_advisor.py:132 — and the vision check uses naive `==`, so `qwen2.5vl:3b-q4_K_M` would read as NOT installed), no test notices and the one-stop check lies.

**Blast radius**
- Adjacent code: `_model_matches` in model_advisor (the tag-tolerant comparison the vision check arguably should reuse — cross-tag for engineering).
- Tests to update: extend the two existing tests, two asserts each.

**Fix path**
In `test_models_command_prints_hardware_and_recommendation` (installed list = gemma only) assert `"ollama pull qwen2.5vl:3b" in out`; add a case with qwen2.5vl:3b installed asserting `"(installed)"`.

---

### [TEST-006] — Minor — Coverage — DesignRegistry edge seams untested: never-registered evict, double-evict, slice-cache cap

**Evidence**
`tests/test_design_registry.py` (5 tests) covers the three protocols' happy and guard paths but not: `evict_locked` on a never-registered rid; double-evict idempotence; `enforce_caps_locked` boundary (cap=0, len==cap exactly); and the `MAX_SLICE_CACHE` eviction loop in `cache_slice_locked` (design_registry.py:147–148) — grep confirms no test anywhere fills the slice cache past its cap (the registry cap has a route test; the slice-cache cap has none at any level).

**Why this matters**
All four are safe today by construction (`pop(…, None)`, `rmtree(ignore_errors=True)`), which is exactly when a cheap pin is worth it: the next person who "tidies" `pop(rid, None)` into `del self.gcode[rid]` gets a KeyError on the first cap eviction of a design that never sliced — and no test catches it. The slice-cache cap is the standing ENG-406 bound on the heaviest objects in memory; it has never been demonstrated to evict.

**Blast radius**
- Tests to update: none; add ~3 tests (~25 lines) in `tests/test_design_registry.py`.
- Related findings: TEST-002 (same file, same setup helper).

**Fix path**
One test: `evict_locked(999)` then `evict_locked(999)` again — no raise, dirs untouched. One test: fill `slice_cache` to `max_cache + 2` via `cache_slice_locked`, assert oldest keys evicted and len == cap. Fold the cap==len boundary into the existing cap test.

---

### [TEST-007] — Nit — Quality — Docstring points test-writers at a method that doesn't exist

**Evidence**
`src/kimcad/design_registry.py:12`: "…is registered ONLY if it still matches (:meth:`bump_version_locked` / :meth:`try_register_slice`)" — there is no `try_register_slice`; the methods are `register_gcode_locked` / `cache_slice_locked`.

**Why this matters / Fix path**
The module docstring is the map the next test author uses. Rename the reference. (Flagged here because it's a test-discoverability cost; ownership is engineering.)

---

### [TEST-008] — Nit — Shortcut — Missing trailing newline in `PhotoOnramp.test.tsx`; dead `_evict` alias

**Evidence**
`frontend/src/components/PhotoOnramp.test.tsx` ends without a newline (`\ No newline at end of file` in the diff). `src/kimcad/webapp.py:767` assigns `_evict = reg.evict_locked` which is never called (its two former call sites were replaced by `reg.enforce_caps_locked`).

**Fix path**
Add the newline; delete the dead alias (or call it from a future delete-design handler — see TEST-002 first).

---

## Shortcut census

| Shortcut pattern | Count |
|---|---|
| `.skip` / `xit` / `@skip` (frontend) | 0 |
| `@pytest.mark.skipif` / `pytest.skip` (backend) | 25 across 13 files — **all** conditional live-dep guards (cadquery interpreter, OpenSCAD binary, manifold3d), none in Stage 9 files, and `conftest.py:92` turns them RED on CI (zero-skip gate) |
| `.only` (left in) | 0 |
| `TODO: add test` / similar | 0 |
| Empty assertion / placeholder | 0 |
| `--retry` / retries normalized | no |

This is a clean census. The skip posture (skip locally with one actionable line, fail CI) is better than most production codebases.

## Blind spots by class

- **Copy-paste-twin drift (client transport):** `uploadSketch` untested while `uploadPhoto` has five tests (TEST-001).
- **Negative space on typed-error mapping:** non-404 → not-VisionModelMissing unpinned, both sides of the wire (TEST-001, TEST-004).
- **Contract-vs-implementation drift on the new class:** "every registry" excludes `meshes`, fail-open downstream (TEST-002).
- **Invariant-by-convention (mutate, don't rebind):** 5 of 9 aliases unpinned until Stage-10 flattening (TEST-003).
- **Caps that have never evicted:** the slice-cache bound (TEST-006).
- **Covered-but-unasserted output:** the `kimcad models` vision line (TEST-005).
- *Not* a blind spot, despite the walkthrough note: the SPA input-change → confirm-card flow runs with a real `File`; the mock sits at the network function, and that function's photo twin is unit-tested. The sketch twin is the gap, not the component flow.

## Patterns and systemic observations

- **Tests are written as regression pins with intent comments** (audit-finding IDs in test names/docstrings: ENG-001, QA-003, "Trust rule 1"). When behavior changed (vision model), the old pin was rewritten with the rationale in the docstring rather than deleted or left stale. This is strong test culture and the main reason this stage-gate found Majors only at the seams, not the centers.
- **The recurring weakness is negative space**: the suite pins what the code DOES, thinly pins what it must NOT do (non-404 mapping, alias rebinding, evict-of-live-rid). Three of the six substantive findings are the same habit.
- **The DesignRegistry extraction *improved* testability** (protocols are now directly testable; 5 tests exist where zero direct tests could before) — but the transitional alias seam transfers an invariant from "enforced by structure" to "enforced by convention," and the test suite only chased it halfway (TEST-003).

## Appendix: test artifacts reviewed

- Read in full: `tests/test_design_registry.py`, `src/kimcad/design_registry.py`, `frontend/src/components/PhotoOnramp.tsx`, `frontend/src/components/PhotoOnramp.test.tsx` (head + diff)
- Diffs reviewed: `tests/test_webapp.py`, `tests/test_llm_provider.py`, `src/kimcad/llm_provider.py`, `src/kimcad/webapp.py`, `src/kimcad/cli.py`, `src/kimcad/config.py`, `config/default.yaml`, `frontend/src/api.ts`, `frontend/src/api.test.ts` (absence of change), `frontend/src/App.test.tsx`, `frontend/src/components/FirstRunWizard.test.tsx`
- Greps: `think|gemma` across `tests/` and `frontend/src/**/*.test.*`; alias usage trace across `webapp.py`; shortcut census across both suites
- Runs (all green): pytest `test_design_registry.py + test_llm_provider.py + test_fallback_provider.py` (42 passed), `test_webapp.py -k "seed or vision or evicted or rerender"` (20 passed), `test_cli.py -k models` (2 passed); vitest `PhotoOnramp.test.tsx + api.test.ts` (60 passed)
