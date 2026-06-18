# GauntletGate Full — Test Engineer — KimCad 0.9.2

**Role:** Test Engineer
**Severity roll-up:** Blocker 0 · Critical 1 · Major 2 · Minor 2 · Nit 1

---

## Findings

### TE-001 — Critical — Codegen-down test asserts status only; no `"engine"` guard

**File:** `tests/test_webapp.py:3695`
**Assertion:**
```python
assert d["status"] == "model_unavailable" and d["has_mesh"] is False
```
**Problem:** `test_design_with_model_down_during_codegen_is_recoverable` is one of the three
`model_unavailable` tests updated in 0.9.2, yet it is the ONLY one that does NOT assert
`"engine" in d["error"]`. The test covers the codegen-phase drop path
(`generate_openscad` raises `APIConnectionError`), which feeds through the same
`webapp.py:2121` branch that emits `MODEL_UNAVAILABLE_MESSAGE`. If that branch were
accidentally reverted to the old "Ollama" wording — or to any arbitrary string not
containing "engine" — this test would still pass. The other two tests
(`test_design_with_model_down_returns_recoverable_status_not_500` at line 3661 and
`test_design_native_ollama_path_down_is_recoverable_not_500` at line 3731) DO carry the
guard; their coverage is adequate. This one does not.

**Why it matters:** The codegen-phase drop is a real production path (plan succeeds, model
falls over on the SCAD generation call). A vocabulary regression on the most user-visible
error surface — "Ollama" leaking back into the message — goes undetected through this test.

**Fix path:** Add `assert "engine" in d["error"]` (and optionally `assert "Ollama" not in
d["error"]`) to line 3695, parallel to the guards in the other two tests.

---

### TE-002 — Major — `OLLAMA_MODELS` test does not exercise installed mode

**File:** `tests/test_ollama_runtime.py:83–99`
**What the test proves:** `start_serve()` passes `OLLAMA_MODELS = str(writable_root() /
"models")` to the spawned process when called with `env={}`. The assertion calls
`writable_root()` directly inside the test, so it confirms the value matches whatever
`writable_root()` returns IN THE CURRENT PROCESS ENVIRONMENT — which in CI/dev is always the
dev-mode path (repo root), because `KIMCAD_INSTALL_ROOT` is not set.

**What it does NOT prove:** Whether `OLLAMA_MODELS` resolves to the correct per-user
`%LOCALAPPDATA%\KimCad\models` path when `KIMCAD_INSTALL_ROOT` is set (the actual installed
app). In installed mode, `writable_root()` returns `%LOCALAPPDATA%\KimCad`; in dev mode it
returns the repo root. The test passes in both modes, but it can only ever run in dev mode in
CI — so it NEVER exercises the installed-mode value.

**Why it matters:** The entire purpose of `OLLAMA_MODELS` pinning is to put models under the
uninstall scope. In dev mode that is the repo root (harmless); in installed mode it MUST be
the per-user data dir. The test cannot catch a regression that breaks the installed-mode path
for `OLLAMA_MODELS`.

**Fix path:** Add a parameterized or second test that monkeypatches `KIMCAD_INSTALL_ROOT` and
`LOCALAPPDATA` (as `test_paths.py:test_installed_mode_splits_read_and_write_roots` does),
then calls `start_serve()` and asserts `OLLAMA_MODELS` is under the per-user appdata dir, not
the repo root.

---

### TE-003 — Major — `"engine" in body["error"]` is a weak substring guard; does not exclude "Ollama"

**Files:** `tests/test_webapp.py:1438`, `3661`, `3731`
**What the tests prove:** `body["error"]` contains the substring `"engine"`. This is a
positive membership test only — it confirms the new vocabulary arrived, but does NOT confirm
the old banned vocabulary is absent.

**What can slip through:** A future maintainer who changes `MODEL_UNAVAILABLE_MESSAGE` to
something like `"Ollama engine isn't running"` — a plausible edit that re-introduces the
banned name — would pass all three assertions. The test comment says `# no "Ollama" leak`
but the assertion never checks for it.

Two of the tests that check the vision-model-down path (`test_photo_and_sketch_seed_map_missing_vision_model_to_typed_pull_hint`,
line 3872) DO contain `"ollama pull qwen2.5vl:3b"` by design (the pull command is part of
the error message), so a blanket exclusion guard is not appropriate everywhere — but it IS
appropriate for the `MODEL_UNAVAILABLE_MESSAGE` path specifically, where the invariant is
"must not contain Ollama".

**Fix path:** Add `assert "Ollama" not in d["error"]` (case-sensitive, matching the
invariant stated in the pipeline.py comment) to all three assertions that check the
`MODEL_UNAVAILABLE_MESSAGE` branch. This does not conflict with the vision-model tests,
which fire a different code path (`VisionModelMissing`, not `_is_model_unreachable`).

---

### TE-004 — Minor — No round-trip test verifies `MODEL_UNAVAILABLE_MESSAGE` text appears verbatim in the API response

**Files:** `src/kimcad/pipeline.py:202–205`, `tests/test_webapp.py:1438,3661,3731`
**What exists:** Three tests confirm `"engine" in body["error"]` via an HTTP round-trip
through the real webapp handler. This proves the message reaches the API.

**What is missing:** No test imports `MODEL_UNAVAILABLE_MESSAGE` from `pipeline` and asserts
`body["error"] == MODEL_UNAVAILABLE_MESSAGE` (or `MODEL_UNAVAILABLE_MESSAGE in body["error"]`).
The constant is the single-source of truth for this string; the tests currently verify only
that a fragment of the intended string is present, not that the actual constant is the one
being served. If `MODEL_UNAVAILABLE_MESSAGE` were renamed or the webapp emitted a different
string (e.g., a hardcoded literal in `webapp.py`), the existing tests would still pass.

**Fix path:** In at least one of the three tests, replace the substring check with:
```python
from kimcad.pipeline import MODEL_UNAVAILABLE_MESSAGE
assert body["error"] == MODEL_UNAVAILABLE_MESSAGE
```
This anchors the test to the constant, making a silent divergence between the constant and
the webapp impossible.

---

### TE-005 — Minor — CLI path (`cli.py:634`) emits `MODEL_UNAVAILABLE_MESSAGE` but has no test verifying the new vocabulary

**Files:** `src/kimcad/cli.py:634`, `tests/`
**What exists:** `cli.py` imports and emits `MODEL_UNAVAILABLE_MESSAGE` when
`_is_model_unreachable(e)` is true. There is no test in the suite that exercises
`kimcad.cli`'s model-down path and asserts `"engine"` (or the full constant) appears in
stderr.

**Why it matters:** The CLI is a documented user-facing surface. A vocabulary regression
(e.g., "Ollama" leaking back in) on the CLI path would be invisible to the current test
suite. The webapp path has three tests; the CLI path has none for this property.

**Fix path:** Add a test (modeled on existing CLI tests) that patches
`_is_model_unreachable` to return `True`, calls the CLI's design flow, and asserts the
stderr output contains `MODEL_UNAVAILABLE_MESSAGE` text and does NOT contain `"Ollama"`.

---

### TE-006 — Nit — `designStatus.test.ts` fixture uses a partial error string, not the real constant

**File:** `frontend/src/designStatus.test.ts:72–73`
**Assertion:**
```typescript
assistantMessage({ ...base, status: 'model_unavailable', error: "the engine isn't running" }),
).toContain("engine isn't running")
```
The fixture passes a hand-written string `"the engine isn't running"` rather than the real
`MODEL_UNAVAILABLE_MESSAGE` value. The test comment says this is "a substring unique to the
backend error, not the default", but it is a substring of the FIXTURE, not the actual
constant. This is fine for the frontend logic test (it only exercises the `result.error ||
fallback` branch); it just means the frontend test cannot catch a drift where the backend's
actual constant changes to a string that no longer contains that fragment.

This is a nit rather than a higher severity because: (1) the backend tests validate the
constant content at a higher layer, and (2) the frontend test is intentionally testing
frontend branching logic, not end-to-end message content.

**Fix path:** Low priority. Consider pulling the expected-message fragment from a shared
fixture constant once a TS equivalent of `MODEL_UNAVAILABLE_MESSAGE` exists, or add a
comment explaining the fixture is intentionally synthetic.

---

## What's working (specific and credited)

**Fix 1 — `MODEL_UNAVAILABLE_MESSAGE` vocabulary coverage is broadly good.** Two of the
three updated tests (`test_design_with_model_down_returns_recoverable_status_not_500` at
line 3661 and `test_design_native_ollama_path_down_is_recoverable_not_500` at line 3731)
correctly assert `"engine" in d["error"]` through a full HTTP round-trip, exercising the
webapp handler, the pipeline's propagation contract, and the JSON response shape. The
photo-seed test (line 1438) does the same for the `/api/photo-seed` endpoint. Coverage is
real-process, not mocked-at-the-HTTP-layer.

**Fix 2 — `OLLAMA_MODELS` pinning test is structurally sound for the dev-mode path.**
`test_start_serve_invokes_serve_with_loopback_host` injects a fake `spawn` and inspects the
`env` dict passed to it — the test proves the assignment actually reaches the child process
environment, not just that the variable is set internally. This is the right testing pattern
for a subprocess-launch concern.

**`_child_env()` is called on the only real spawn path.**
`start_serve()` calls `_child_env()` unconditionally at line 168 before any platform
branching — there is no code path through `start_serve` that could skip it. `ensure_serving`
(the orchestrator) calls `start_serve` on the managed-start branch. The injected-`start`
tests in `test_ollama_runtime.py` bypass `start_serve` entirely, which is correct —
they're testing the orchestration, not the env setup. The unit test for `start_serve` is the
right level.

**`designStatus.test.ts` frontend tests cover the branching logic correctly.** The test
at line 71–74 verifies both: (a) when the backend returns an `error` string, it's
passed through to the user; (b) when no `error` is returned, a sensible `/local AI/i` default
fires. This matches the `result.error || fallback` implementation in `designStatus.ts:80`.
The "engine isn't running" discriminating-substring check is meaningful for confirming (a)
uses the backend error, not the fallback.

**Version single-source test is comprehensive.** `test_version_single_source.py` covers:
pyproject metadata, installed package version, no-literal-in-source scan, README badge,
frontend package.json and lockfile, installer script parametrization, CLI `--version` flag,
and `/api/health` endpoint — all eight surfaces synchronized. The 0.9.2 bump is fully
enforced.

**`test_paths.py` covers `writable_root()` in both dev and installed mode across all three
platforms.** The parametrized tests for Windows/macOS/Linux installed-mode resolution give
the `writable_root()` function the coverage it needs. Since `OLLAMA_MODELS` calls
`writable_root()` directly, these tests are load-bearing for the correctness of the installed
path — the gap (TE-002) is only that no test calls `start_serve` under those mocked
conditions.

---

## Coverage gaps

| ID | Severity | Gap |
|----|----------|-----|
| TE-001 | Critical | Codegen-down test missing `"engine"` guard — vocabulary regression on this path is undetectable |
| TE-002 | Major | `OLLAMA_MODELS` test never runs under `KIMCAD_INSTALL_ROOT` — installed-mode path untested |
| TE-003 | Major | No `"Ollama" not in ...` exclusion guard on any `MODEL_UNAVAILABLE_MESSAGE` assertion |
| TE-004 | Minor | No test binds `body["error"]` to the `MODEL_UNAVAILABLE_MESSAGE` constant directly |
| TE-005 | Minor | CLI model-down path emits the constant but has no test for vocabulary |
| TE-006 | Nit | Frontend fixture uses a hand-written string, not the real backend constant |

**No Blockers.** The most serious gap (TE-001) is Critical: a regression on the codegen-down
path vocabulary would ship silently past the test suite. The Major gaps (TE-002, TE-003) are
gaps in coverage depth, not missing tests entirely. No critical path is wholly untested.
