# Stage 8.5 (Usability) — Test Engineer RE-AUDIT (post-remediation)

**Repo:** `C:\Users\scott\dev\kimcad`  **Branch:** `stage-8.5-usability` @ `6c98674`
**Date:** 2026-06-05  **Role:** Test Engineer (independent re-audit; no source modified)
**Supersedes:** the original 04-test-deepdive.md (original @ `95b25e0`, findings TEST-001..005)

---

## Test runs I actually executed (this re-audit, at commit 6c98674)

- Python (fast, non-live marker): 761 passed, 4 deselected in 127.16s.
- Frontend (vitest run): 257 passed across 22 files in 8.77s.

Zero unjustified skips. The 4 deselected are the live marker (the real OrcaSlicer slice + send). My
machine has the OpenSCAD binary + geometry deps, so every renderer/regate test ran for real. Growth vs
the original run (757 py + 249 vitest): plus 4 pytest passing (the 4 new backend tests added by
remediation: ENG-001 stale-slice, ENG-002 _regate_mesh x2, TEST-003 key-in-logs) and plus 8 vitest
(249 to 257: useHashRoute hook x3, Topbar TEST-004/UX-005/UX-013, VersionRail v1 cue, ChatPanel UX-008
x2 + compare deltas). Combined: 1018 passing. Suites run clean; no flakes across the runs I did.

---

## Per-finding verdict (original TEST-001..005)

### TEST-001 (Major -> RESOLVED) — hosted CI now runs the frontend

`.github/workflows/ci.yml` now has TWO hosted jobs (commit be1e138):
- `python` (lines 20-32): ruff + the non-live pytest run on ubuntu.
- `frontend` (lines 34-50, NEW): `npm ci`, then the vitest run, then `npm run build`, on ubuntu-node-20.

This closes the original gap exactly: a vitest regression or a frontend that won't compile now fails a
hosted check, no longer gated ONLY by a per-clone local pre-push hook. The build step (lines 45-46)
compiles the SPA from source, so a frontend that won't build can't ship green.

Byte-exact repro is honestly documented as staying the Windows hook. The header (lines 7-11) and the
"Build reproducibility" step (lines 47-50) state the committed-assets diff is INFORMATIONAL here because
Vite/Rolldown output differs across platforms (Linux Rolldown binding vs Windows-built committed assets),
and that byte-exact repro + the live OrcaSlicer proof + npm audit remain the Windows pre-push gate's job.
That is an honest, accurate division of labor — not a paper-over. Verified would-catch-it: a broken
component or a non-compiling SPA fails `frontend`; the one thing the hosted job can NOT prove (committed
`src/kimcad/web` equals a fresh build, byte-exact) is precisely what it says it can't, and it points at
the right gate. RESOLVED.

Residual (not a finding): the workflow ships disabled ("Enable with gh workflow enable CI", line 13) to
save Actions minutes — same posture as before. The job is correct and will gate once enabled; that's a
Scott/ops switch, not a test defect. Noted for the orchestrator.

### TEST-002 (Minor -> RESOLVED, with a one-line residual) — useHashRoute hook tested directly

`useHashRoute.test.ts:26-54` adds a renderHook(useHashRoute) block (TEST-002) with three real behavior
tests:
- hashchange branch (lines 27-35): dispatch a hashchange, assert `route` updates to `designs`.
- replaceState-direct-update branch (lines 37-44): navigate(..., {replace:true}) updates `route`
  synchronously AND sets window.location.hash — the exact branch the original finding called out
  (replaceState fires no hashchange, so the hook updates state directly, `useHashRoute.ts:41`).
- push branch (lines 46-53): navigate() without replace sets the hash and routes there.

These assert the hook's output, not just that it rendered. RESOLVED.

Residual (Nit, not re-raised): the original fix-path also suggested asserting the listener is removed on
unmount (`useHashRoute.ts:36`). That teardown branch still has no direct assertion — the lowest-value
third of the finding; a one-liner of standard React. Leave as an optional add.

### TEST-003 (Minor -> RESOLVED as a regression guard; weaker than the brief's fix-path) — key-never-in-logs

`test_webapp.py:2302` (test_cloud_key_never_appears_in_logs, capsys) POSTs a settings update carrying a
sentinel key, then GETs `/api/settings` and `/api/model-status`, captures BOTH stdout and stderr, and
asserts the secret is in neither — plus a sanity assert (line 2325) that the key really persisted to
disk, proving the test exercised the real key path and isn't a no-op. The key-bearing endpoints are all
driven. RESOLVED for the stated invariant.

Honesty caveat (verified, downgrades how load-bearing this test is — NOT re-raised): the server's default
request log is overridden to a no-op (`webapp.py:749`, "keep the console quiet"), and every
settings-handler exception path emits message-only — no stack, no body (lines 1267, 1303, 1368). So today
there is no code path that would write the key to a log, and the capsys check passes partly because the
request log is silenced. The test is a genuine guard against a future print(body) or a logging call that
interpolates the settings dict reaching stdout/stderr — the realistic regression — but it does NOT
exercise the brief's stronger recommendation of inducing a settings-handler exception to prove a
traceback doesn't stringify the key. Given the handler code emits no body and no stack, the residual leak
risk is low and the guard is adequate; stays Minor-resolved, not escalated. Flagging the caveat so it
isn't mistaken for proof that "no path can ever stringify the key" — it proves "the key isn't printed
today," which is the right-sized claim.

### TEST-004 (Minor -> RESOLVED) — Topbar active-route behavior asserted

`Topbar.test.tsx:35-41` (TEST-004) renders with activeRoute='designs', asserts the My Designs button
carries aria-current="page" (active state), AND that clicking it calls onMyDesigns. The settings route
already had this; designs now does too — a behavior assertion (active state + nav callback), exactly the
upgrade the original finding asked for. (The glossary-definition-correctness half of TEST-004 was
optional/Nit in the original; the help-tip tests at `App.test.tsx:290,319` still assert tip presence per
term rather than per-term definition text — unchanged, but that was the explicitly-optional tail.)
RESOLVED for the load-bearing half (active-route).

### TEST-005 (Nit -> RESOLVED / accepted + documented) — api-mock seam

The wholesale `./api` mock at the component layer is accepted, documented in the remediation ledger as a
deliberate choice backed by the strong socket-level backend round-trips. No contract test was added; none
was warranted at this stage (the original finding said as much). The `api.ts` fetch-seam unit tests plus
the test_webapp.py real-socket round-trips bracket the seam. Accepted as designed.

---

## Scrutiny of the remediation's NEW tests (do they prove what they claim?)

I went after the new tests adversarially — does each assert behavior, and is anything green despite a
broken thing?

ENG-001 stale-slice test — GENUINE. test_a_slice_that_finishes_after_a_rerender_is_dropped_as_stale
(`test_webapp.py:1438`) is the standout. It stubs the slicer to fire a real concurrent re-render for the
same rid mid-slice (line 1452), which bumps geometry_version and clears the cache, then asserts the slice
responds sliced:false reason:"stale", returns NO gcode_url, and the g-code endpoint 404s (lines
1465-1468). I traced the implementation: _handle_slice captures sliced_ver under the lock
(`webapp.py:1673`), and _respond_slice (line 1639) AND the cache-write (line 1712) both re-check
geometry_version.get(rid) == sliced_ver under the lock before registering/caching. The render handler
bumps the version + drops the cached slice/gcode (lines 1783-1788). The test exercises the real race
window, not a render-only check. Real proof of the safety invariant.

ENG-002 _regate_mesh tests — GENUINE at the unit level; ONE integration seam left untested (NEW finding
RTEST-001). test_regate_mesh_rederives_fail_for_an_oversized_mesh (line 1471) exports a 300mm box (over
the 256mm Bambu build) and asserts _regate_mesh(...) == "fail"; the partner (line 1485) asserts an
in-bounds mesh re-gates non-fail and an unreadable mesh / missing plan returns None (so the caller falls
back to the stored verdict, never false-failing a real reopen). These assert the re-derivation behavior,
not a render. I verified the wiring: _handle_design_reopen calls _regate_mesh and sets
gate_status_by_rid[rid] = regated or stored or "fail" (`webapp.py:1530-1533`), and import flows through
reopen (import only stores; _handle_design_import at line 1598 returns an id, the design must be reopened
to register into live state) — so an altered imported .kimcad IS re-gated before any slice is possible.
The gap: no end-to-end socket test reopens an altered design (stored gate_status:"pass" over an
unprintable mesh) and asserts it comes back gate-failed AND refuses to slice. The unit test plus the
visible wiring make this low-risk, but the seam itself is unproven by a test.

Advisor tests (gemma4 top-tier, ENG-006) — GENUINE. `model_advisor.py:105-124` makes gemma4:e4b tier 7
(highest LOCAL) and the Qwen entries tier 1-2, with REJECTED notes. test_model_advisor.py asserts the
DECISION, not strings: gemma4 wins over an installed Qwen (lines 50-56, rec.primary.name == "gemma4:e4b",
upgrade is None); the non-China escape names gemma4 when only a China model is installed (lines 103-112);
no redundant escape when gemma4 is primary (lines 96-100); cloud is never primary when a local fits
(lines 115-117). These would fail if the ranking regressed. Solid.

UX tests — MIXED. The ones that exist assert behavior well:
- VersionRail v1 cue (`VersionRail.test.tsx:38`) asserts the cue text renders AND no version pills appear
  until v2 (lines 40-41) — real behavior.
- ChatPanel UX-008 (lines 56-66) asserts the duplicate "Designing" row is suppressed on a first design
  and the in-thread "Refining" row appears when a part is already on screen — real behavior, both ways.
- ChatPanel compare card (lines 150-173) asserts the actual computed deltas (H 40 to 52 mm,
  Readiness 90 to 88) and the gate-vocabulary mapping (pass to Passed, warn to Needs review, raw enum
  absent) — strong.
- Topbar "?" Help button (`Topbar.test.tsx:68`) asserts clicking it calls onShowShortcuts — real.
- RightPanel printability checks (UX-002, icon-led list, `RightPanel.tsx:573`) — the finding text
  ("Dimensions match") is asserted at `RightPanel.test.tsx:119`, and the warn/pass screen-reader cue is
  covered by the readiness severity-cue tests. Adequate.

  But three NEW user-facing UX features the remediation ADDED have ZERO test coverage (NEW findings
  RTEST-002/003/004): the refine chips, the Topbar printer-status chip, and the mobile sticky CTA.

QA tests — implemented, two untested (NEW findings RTEST-005/006). The adjusted_params clamp hint
(`webapp.py:1758-1773`) and the demo:gatefail / demo:experimental prompt scenarios (`webapp.py:290-300`)
are real, substantive code — neither has any test. QA-003 (unified bad-id wording) is covered by existing
404-wording assertions.

ENG-003/004/005 — implemented, lightly/indirectly tested. ENG-003 allow_nan=False guard
(`webapp.py:785-796`, a non-finite number yields a clean 500) has no test inducing a non-finite through
_json (the template-layer NaN test at `test_templates.py:166` is a different code path). ENG-004
FallbackProvider.describe_photo delegates through the generic _call (`llm_provider.py:385-389`) whose
fallback routing IS well-tested via generate_design_plan/generate_openscad — adequate by delegation.
ENG-005 _cloud_cache LRU bound (`webapp.py:376-377`, max 4) has no test proving eviction past the cap.

Any test green DESPITE a broken thing? No — I found no test that passes while the thing it names is
broken. The new tests that exist assert real behavior. The honesty issue here is OMISSION (new features
shipped without tests), not FALSE GREEN.

---

## NEW findings (this re-audit)

### RTEST-001 (Minor / Coverage) — ENG-002 re-gate has no end-to-end "altered reopen refuses to slice" test
_regate_mesh is unit-tested (`test_webapp.py:1471,1485`) and the reopen wiring is visible
(`webapp.py:1530-1533`, regated-or-stored), but no socket-level test reopens a design whose stored
gate_status is "pass" over an oversized/unprintable mesh and asserts the reopened design (a) comes back
gate-failed and (b) is refused by `/api/slice`. The safety claim — "an altered/stale stored verdict
can't make an unprintable part sliceable on reopen" — rests on reading the wiring, not a test.
Fix path: one integration test: save a genuinely-oversized design (or alter stored meta to
gate_status:"pass"), reopen over the socket, assert the returned gate_status == "fail" and that a slice
POST for the new rid returns sliced:false reason:"gate_failed". ~25 lines. Minor (wiring present +
unit-covered; this closes the seam).

### RTEST-002 (Minor / Coverage) — the new refine chips (UX-003/010) have zero tests
`ChatPanel.tsx:252-265` renders four one-tap refine chips ("Make it wider" / "Make it taller" /
"Thicker walls" / "Add mounting holes"), each calling onRefine(chip), hidden during a
clarification_needed state (line 249). No test asserts the chips render, that clicking one calls
onRefine with that exact text, or that they're hidden on a clarification. A new interactive surface with
logic (the clarification gate) and no behavior test.
Fix path: in ChatPanel.test.tsx, render with a completed result, click "Make it wider", assert
onRefine('Make it wider'); render with clarification_needed and assert the chip group is absent. Minor.

### RTEST-003 (Minor / Coverage) — the Topbar printer-status chip (UX-006) has zero tests
`Topbar.tsx:48-96` adds an always-on printer chip that calls getOptions() on mount and renders the
default printer's name + build volume. Topbar.test.tsx does NOT mock `../api`, so the chip's best-effort
fetch is swallowed and the chip never renders in those tests; `App.test.tsx:29` mocks getOptions only to
prevent a mount crash and never asserts the chip's content. So no test asserts the chip renders the
printer name or the build volume, nor that it degrades to absent when options fail.
Fix path: a Topbar.test.tsx case that mocks getOptions to return a printer with a build_volume, awaits
the effect, asserts the chip shows the name + a "256 x 256 x 256" volume; a second that getOptions
rejecting leaves the chip absent (not an erroring control). Minor.

### RTEST-004 (Minor / Coverage) — the mobile sticky "Check & download" CTA (UX-004) has zero tests
`Workspace.tsx:116-127` adds a mobile-only sticky CTA jumping to the print actions. The "UX-004" comment
tags in the test suite are about inch formatting and the .kimcad label — unrelated. No test renders the
mobile CTA or asserts it scrolls/links to the export actions. (Mobile layout is partly CSS-media-query
driven and hard to assert in jsdom, which lowers the value, but the CTA element + its click handler are
testable.) Fix path: render Workspace with a completed result, assert the kc-mobile-cta button exists and
its click invokes the scroll/navigate-to-export handler. Minor (leaning Nit given the media-query
caveat).

### RTEST-005 (Minor / Coverage) — adjusted_params clamp hint (QA-001) untested
`webapp.py:1758-1773` adds an adjusted_params array to the `/api/render` response when a requested value
differs from the applied (clamped/coerced) value, with real diff logic (float-compare, the
requested/applied pairing). No test drives a render with an out-of-range value and asserts the response
carries adjusted_params with the right requested/applied, nor that an in-range value omits it. The
contract could silently regress. Fix path: a render POST for an rid with a width over the spec max,
assert adjusted_params lists {name:"width", requested:..., applied:max}; a second with an in-range value
asserts the key is absent. Minor.

### RTEST-006 (Nit / Coverage) — demo scenarios (QA-002) + ENG-003 allow_nan + ENG-005 cache-bound untested
Three small remediation additions with no direct test: the demo:gatefail / demo:experimental
prompt-keyword scenarios in DemoProvider (`webapp.py:290-300`, demo-only, low stakes); the
_json allow_nan=False non-finite-to-clean-500 guard (`webapp.py:785-796`); and the _cloud_cache LRU
bound (`webapp.py:376-377`, max 4 — key material, the original ENG-005 concern). Each is a few lines and
low-exposure, but the allow_nan and cache-bound are the kind of guard worth one assertion so they can't
quietly regress. Fix path: one test that an out-of-range number through any endpoint yields a clean 500
(not invalid JSON); one that the cloud cache evicts past 4 entries; (optional) one that demo:gatefail
reaches a gate-failed offer. Nit (batch-able; all low-exposure).

---

## Safety-invariant census (re-checked at 6c98674)

| Invariant | Tested? | Where |
|---|---|---|
| Gate-failed part never sliced/sent | Yes | `test_webapp.py:64` |
| Re-render invalidates the cached slice | Yes | `test_webapp.py:1335,1407` |
| Slice that finishes AFTER a re-render is dropped as stale (ENG-001) | Yes (NEW) | `test_webapp.py:1438` |
| Reopen/import re-gates, not trusting stored verdict (ENG-002) | Unit yes; e2e seam no | `:1471,1485` / RTEST-001 |
| Cloud key never on the wire | Yes | `test_webapp.py:2055,2202` |
| Cloud key never in logs/stdout/stderr | Yes (NEW) | `test_webapp.py:2302` |
| Photo never routes to cloud (even cloud-enabled) | Yes | `test_webapp.py:2398,2491` |
| Traversal / zip-slip / oversized import bounded | Yes | `test_design_store.py:51,164,190` |
| Non-finite number to clean 500 (ENG-003) | No | RTEST-006 |
| Cloud-key cache bounded (ENG-005) | No | RTEST-006 |

The two load-bearing safety Majors from the original engineering audit (ENG-001 stale-slice, ENG-002
re-gate) now have real tests; the only safety-adjacent items left untested are the ENG-003/005 guards
(Nit-level exposure) and the ENG-002 end-to-end seam (Minor).

---

## Summary for the orchestrator

Original TEST findings: TEST-001 RESOLVED, TEST-002 RESOLVED (Nit residual: unmount-teardown assertion),
TEST-003 RESOLVED (regression guard; weaker than brief's induced-exception fix-path, but adequate — no
code path stringifies the key today), TEST-004 RESOLVED (active-route half), TEST-005 accepted/documented.
5/5 addressed.

New findings: 5 Minor + 1 Nit, all the same shape — remediation features shipped without their tests
(refine chips, printer chip, mobile CTA, adjusted_params, the ENG-002 e2e seam) plus a batch of small
untested guards (demo scenarios, allow_nan, cache-bound). None is a Blocker/Critical/Major. No test is
green-despite-broken; the issue is omission, not false coverage.

New-finding rollup (Test role only): Blocker 0 / Critical 0 / Major 0 / Minor 5 / Nit 1 (total 6).

Test counts I ran: pytest 761 passed, 4 deselected (non-live); vitest 257 passed across 22 files.
Combined 1018 passing, 0 unjustified skips. Suites clean.

Bottom line: The remediation genuinely fixed the original TEST findings and the load-bearing safety
Majors, and the new tests that exist assert behavior, not just render. It is NOT at 0/0/0/0/0 for the
Test role — a cluster of NEW user-facing features and small guards were added without coverage. These are
all Minor/Nit and batch-able in one short pass (~6 tests). Recommendation: close them before tagging
stage-8.5, since the mandate is fix-ALL-then-0/0/0/0/0; a feature added during a remediation that has no
test is exactly the drift the re-audit exists to catch.
