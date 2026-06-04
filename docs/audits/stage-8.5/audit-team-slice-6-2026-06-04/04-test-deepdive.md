# Test Engineer Deep-Dive: Stage 8.5 Slice 6 (Settings + cloud routing + experimental gate)

Auditor role: Senior Test Engineer (balanced posture)
Scope: diff 16f9290..HEAD excluding docs/audits + src/kimcad/web/assets
Date: 2026-06-04

## Observed test counts (run, not claimed)

- Frontend (vitest), `npm --prefix frontend run test`: 144 passed, 13 files (matches the expected 144).
- Python Slice 6, `pytest test_webapp.py test_settings_store.py test_pipeline.py -q`: 4 FAILED, 109 passed.

The four failures are all in the MS-2 model-status block of test_webapp.py:
test_model_status_local_running_with_model, test_model_status_ollama_down_is_not_running,
test_model_status_running_but_model_absent, test_model_status_cloud_backend_reports_cloud.

They fail on the developer's own machine and pass on a clean one. Root cause is a test-isolation defect
(TEST-001 below), not a product bug. A suite that goes red depending on whose machine runs it is exactly
the "100% passing means 100% of what someone chose to check" trap, and it would ship a red gate.

## Test-suite shape

Two-sided unit coverage: the Python side drives the real HTTP layer over an ephemeral socket (genuine
integration for the server contract), and the frontend side mocks the api module and asserts component
wiring against that contract. No end-to-end test crosses the two (no test boots the SPA against the live
server), consistent with the rest of the project and acceptable at this altitude. The masked-key
contract, the experimental matrix, and the cloud-routing selection are all genuinely exercised —
non-vacuous, load-bearing tests. The gap is in isolation hygiene and one specific branch of probe_ollama.

---

## Findings

### TEST-001 (Critical, Flakiness/Isolation) — Four model-status tests read the developer's real per-user settings file; the suite is red on the author's machine

Evidence.
- test_webapp.py:1809-1885 — the four named tests do NOT monkeypatch Config.settings_path (every other
  Slice 6 test that touches settings does — e.g. lines 1725, 1756, 1928, 1944, 1975, 1996).
- webapp.py _handle_model_status reads saved_settings() first and short-circuits to the cloud payload
  when cloud_enabled + key + model are saved.
- The author's real per-user settings file on this machine has cloud_enabled true and a saved cloud model
  (an anthropic/claude router model). So the three "local" tests never reach their mocked probe_ollama
  (they get backend "cloud"), and the cloud test gets the machine's real model name instead of its own
  monkeypatched deepseek model. test_webapp.py:1885 asserts the model equals the monkeypatched value but
  observed the machine's saved value.
- Proof: re-running the four tests with the home dir pointed at an empty location gives 5 passed; running
  them as-is on this machine gives 4 failed.

Why this matters. A suite whose green depends on the content of a per-user file outside the repo is
non-deterministic across machines and across the same machine over time (the moment a developer uses the
cloud feature they are auditing, the audit's own tests break). CI on a clean runner hides it; the next
engineer who exercises the product locally gets a red bar they did not cause and cannot reproduce in CI.
It also means three of these tests are currently vacuous on this machine — their mocked probe_ollama and
their running/model_present assertions are never reached, so they verify nothing about the local-probe
path they exist to cover.

Fix path. Add an autouse fixture in conftest.py that points Config.settings_path at a per-test tmp file
(and ideally history_path/designs_path too), so no test can touch the real per-user dir. That single
fixture fixes all four and hardens the whole suite against this class. Minimal alternative: add the same
settings_path monkeypatch line these four tests are missing.

Blast radius.
- Adjacent code: any test that constructs make_handler without isolating settings is exposed to the same
  leak — the non-_jreq _serve helper (line 185) does not isolate settings either, so the experimental
  tests rely on each setting their own monkeypatch. An autouse fixture closes the whole class.
- Shared state: the per-user settings.json, history, and designs files the suite can currently touch.
- User-facing: none (test-only). Migration: none.
- Tests to update: the four named tests, plus a one-time conftest fixture; no product change.
- Related findings: TEST-002 (the probe_ollama reachable-distinction is only mock-tested, partly because
  these tests stub the function instead of the socket).

---

### TEST-002 (Major, Coverage) — probe_ollama's reachable-vs-empty distinction (its whole reason to exist) has no direct test; the endpoint tests mock it away

Evidence.
- model_advisor.py probe_ollama is new and its docstring states its entire purpose: it distinguishes a
  down server (False, []) from an up-but-empty one (True, []) — the exact signal the Settings UI uses to
  say "start Ollama" vs "get the model."
- Every model-status test (test_webapp.py:1814, 1829, 1841, 1855) monkeypatches ma.probe_ollama to return
  a hand-built tuple. Nothing exercises the real probe_ollama, so the one behavior that differentiates it
  from the pre-existing probe_installed_models (which returns [] for BOTH down and empty) is untested. A
  regression that made probe_ollama return (False, []) for an up-but-empty server — collapsing the very
  distinction it was written for — would pass the entire suite green.
- model_advisor.py already has unit tests for the pure decision layer, so the no-socket unit-test pattern
  is established and cheap here.

Why this matters. Owner's standing rule: a new behavior without a real regression test is at least Major.
This is a new function whose only novel behavior is untested. The "running but model absent" UI state — a
primary onboarding affordance — rests on a code path nothing pins.

Fix path. Add a unit test for probe_ollama that stubs urllib.request.urlopen (not the function): a
models-empty response asserts (True, []); a models-present response asserts (True, [InstalledModel]); a
URLError/OSError/timeout asserts (False, []). That covers the three branches the endpoint relies on at the
right altitude (no live Ollama needed).

Blast radius.
- Adjacent code: _handle_model_status consumes (running, installed); a regression here silently mislabels
  the model state in the UI.
- User-facing: the Settings "Start Ollama" / "Get the model" guidance.
- Tests to update: none break; additive. Related findings: TEST-001 (the endpoint-level mocking hides this).

---

### TEST-003 (Minor, Coverage) — The cloud-to-local degrade has a unit test for "enabled-but-unconfigured" but not for "cloud build raises" or the per-key cache reuse

Evidence.
- test_webapp.py:2039-2065 (test_settings_aware_provider_routes_by_cloud_setting) is a genuinely strong
  test: it proves local-by-default, local-when-enabled-but-no-key/model, and a real cloud LLMProvider
  carrying the user's model when fully configured. This covers the three selection branches the task names.
- Not covered: the except-degrades-to-local arm in _SettingsAwareProvider._active (webapp.py) — a
  LLMProvider construction that raises must degrade to local, exactly as the docstring promises. There is
  no test where LLMProvider construction throws. Also untested: the _cloud_cache reuse (a second call with
  the same key+model returns the SAME provider object) — a regression that rebuilt the client per design
  call would be invisible.

Why this matters. The degrade-to-local arm is the safety net that makes cloud opt-in non-fatal; if a bad
key or a transient import error ever raised instead of degrading, a cloud user's local fallback would
break too. Small, pure branch, cheap to pin.

Fix path. Two short asserts in the existing test: monkeypatch LLMProvider construction to raise and assert
_active() returns local; and call _active() twice fully-configured and assert object identity (cache hit).

Blast radius. Test-only; additive. _active() is the single routing chokepoint, so one test guards both
generate_design_plan and generate_openscad.

---

### TEST-004 (Minor, Coverage) — The masked-key never-echoed contract is well-tested for /api/settings, but the same key flows through /api/model-status and that response is not asserted secret-free

Evidence.
- test_webapp.py:1988-2021 (test_cloud_key_saved_locally_but_never_returned_in_full) is the load-bearing
  trust test and it is non-vacuous and correct: it asserts the full secret is absent from the entire
  serialized GET and POST responses, asserts the masked form ends with the last 5, and confirms the real
  key did persist to disk. This is exactly the never-echoed property the task asks for.
- Gap: that same test then calls /api/model-status (line 2020) and asserts backend/model, but does not
  re-assert that the secret is absent from that payload. _handle_model_status reads the key from settings;
  a future change that echoed it (e.g. a "configured key" hint in the status payload) would slip past every
  test, because the secret-absence assertion is only wired to /api/settings, not to every endpoint that
  reads the key.

Why this matters. The "secret never leaves in a response" property is a per-endpoint invariant, but it is
tested on only one endpoint. Defense in depth for a trust-critical property is cheap and the test already
sits at the exact call site.

Fix path. Add one assertion after test_webapp.py:2021 that the secret is not in the serialized
model-status payload.

Blast radius. Test-only.

---

### TEST-005 (Minor, Coverage) — The api.ts settings/health/model-status wrappers and postDesign(experimental) have no direct frontend test; SettingsPanel tests mock the whole api module

Evidence.
- SettingsPanel.test.tsx:12 mocks ../api wholesale. The component wiring is thoroughly tested against that
  mock contract (the reset payload at lines 233-241, the masked key/Replace at 160-167, the experimental
  toggle at 180-191, the cloud save at 144-158 — all real, non-vacuous, asserting exact posted payloads).
- But the actual api.ts functions added in api.ts (getSettings, postSettings, getModelStatus, getHealth,
  and the new experimental arg to postDesign) are never executed by a test — they are thin getJson/postJson
  wrappers. The postDesign change in particular alters the request body shape (prompt+experimental always,
  history conditional). If postDesign stopped sending experimental, the Python side would silently fall
  back to its True default and the consumer "offer instead of run" behavior would regress — and no frontend
  test would catch it (the SettingsPanel tests do not touch postDesign; ChatPanel tests mock
  onTryExperimental).

Why this matters. This is the seam between the two halves of the otherwise-good two-sided coverage. Both
sides are tested against a contract, but nothing asserts the client actually emits that contract on the
wire. Minor because the wrappers are trivial and shared with already-tested helpers, but the experimental
body field is the one piece of real logic in postDesign and it is unpinned.

Fix path. A small api.test.ts that stubs fetch and asserts postDesign('x', undefined, false) posts a body
containing experimental:false (and getSettings hits /api/settings). One test covers the whole new surface.

Blast radius. Test-only; additive.

---

## What's working (credit where due)

- The masked-key contract is real and load-bearing-correct
  (test_cloud_key_saved_locally_but_never_returned_in_full). It asserts the full secret is absent from the
  entire serialized GET and POST responses, that the masked form ends in the last 5, and that the raw key
  did persist to disk — tested the right way (whole-payload membership check, not a field spot-check). The
  clear-key test (test_cloud_key_can_be_cleared) covers the blank-to-cleared path.
- The experimental gate matrix is complete and non-vacuous. Server side: false offers needs_experimental
  with openscad_calls == 0 (codegen proven not to run, both at the pipeline layer test_pipeline.py:166 and
  the HTTP layer test_webapp.py:1923), true runs codegen, absent runs codegen (back-compat default), and
  setting-on runs even when the SPA sends false (test_design_experimental_setting_on_auto_runs). The
  pipeline test also asserts the plan is kept and no mesh is produced on the offer. Frontend: the offer
  renders on needs_experimental and the Try button wires to onTryExperimental (ChatPanel.test.tsx:96), and
  is absent on a normal completed result. This is the full false-offer / true-run / absent-run /
  setting-on-run matrix the task asked for.
- Cloud routing selection is unit-tested at the right altitude — local default, local-when-unconfigured,
  and a real cloud LLMProvider with the user's model — without any network call. The cloud model-status
  short-circuit is also proven NOT to probe Ollama (the boom guard at test_webapp.py:1877), the correct way
  to pin "cloud does not touch the local path."
- The settings store is thoroughly and honestly tested (test_settings_store.py): allowlist-only
  persistence (crafted/nested keys dropped), None clears a key, missing/corrupt/non-object-JSON all read as
  {}, merge-not-replace, fresh-instance reads from disk, and parent-dir creation on first write. The kind
  of edge-case census most suites skip.
- The store-write-failure path is honestly surfaced
  (test_settings_post_reports_unsaved_when_store_write_fails): a non-persisting store yields 200 with
  saved:false, never a dishonest saved:true and never a 500.
- The health endpoint degrades, not crashes (test_health_missing_binary_is_a_status_not_a_500): a
  binary_path that raises yields present:false, matching the never-500 contract.
- Frontend tests assert exact posted payloads, not just "something was called" — the Reset test pins the
  full six-field clear payload, the cloud-key save pins the openrouter_api_key field, the model field pins
  the on-blur cloud_model field. These would catch a wiring drift.
- No shortcuts: no .only, .skip, xit, it.todo, assert-True, xfail, or TODO/FIXME in the in-scope tests. The
  four pytest skipif markers are all legitimate environment guards (3MF backend, OpenSCAD binary present),
  and the one live-marked test is correctly excluded from the default gate.

---

## Summary

- Counts: Frontend 144/144 pass. Python Slice 6: 4 fail / 109 pass on this machine (113 pass on a clean
  home dir). The 4 failures are TEST-001.
- Severity: Critical 1, Major 1, Minor 3 (no Blockers).
- Most important missing test: the conftest.py autouse fixture that isolates Config.settings_path from the
  real per-user settings file (TEST-001) — it both makes the suite deterministic and un-vacuums three
  model-status tests that currently never reach their own assertions.
