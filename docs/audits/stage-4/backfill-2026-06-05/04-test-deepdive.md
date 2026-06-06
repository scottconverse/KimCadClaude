# Stage 4 — Test Engineer Deep-Dive

**Scope:** Stage 4 = "React SPA shell + viewport." Test-coverage REALITY vs. CLAIM for the
frontend (vitest) and the web flow on the backend (pytest: `test_webapp.py`, plus the slice/config
tests that touch it). Audit-only. Evidence is `file:line` and live run output.

**Auditor stance:** professionally paranoid. A green suite is evidence the tests passed, nothing more.

---

## Run reality (I ran them)

- **Frontend vitest:** `npm run -s test` → **23 test files, 262 tests, all passing**, 9.45s.
- **Backend (web flow):** `.venv/Scripts/python.exe -m pytest tests/test_webapp.py tests/test_slicer.py
  tests/test_config.py -m "not live" -q` → **149 passed, 4 deselected**, 53.7s.

No `.skip`, `.only`, `xit`, `it.todo`, `@pytest.mark.skip/xfail`, `assert True`, or commented-out
assertions were found in the Stage-4 surface. No retry/flaky-retry config. No snapshot tests. The
suite is honest about what it runs.

---

## Test-suite shape (one paragraph)

Bottom-and-middle heavy, no Selenium/Playwright e2e — and for this app that is the *right* shape.
The frontend leans on Testing-Library **behavior** tests (queries by role/label, real `fireEvent`,
fake timers for debounce, `waitFor` for async) rather than snapshots; the three.js viewport is
stubbed so the *wrapper logic* and the *pure highlight math* are tested without WebGL
(`KCViewport.test.ts` exercises `meshDisplayOffset`/`buildHighlightObject` directly). The backend
"web" tests are genuine **integration** tests: they stand up the real `http.server` on a socket
(`_serve`/`_serve_with_designs`) and drive it over real HTTP with the real `Pipeline` + real
OpenSCAD/trimesh geometry — not mocked handlers. That combination (real server + real geometry +
real client) is exactly what catches wiring bugs, and it is the strongest thing in this audit.

---

## What's working (credit where due)

- **Adversarial backend coverage is real.** Out-of-order re-render dropped as stale
  (`test_webapp.py:1438`), concurrent re-renders serialized (`:1546`), concurrent saves make one
  entry (`:1824`), idempotent slice — one real slice per key (`:1019`), path traversal rejected on
  three static + thumb endpoints (`:315`, `:336`, `:1727`), oversize/`malformed Content-Length`
  → clean 413/400 (`:214`, `:224`), unexpected pipeline error → clean 500 with no traceback
  (`:900`). This is the thinking the severity framework wants to see.
- **JSON-safety / input-validation is thorough.** Non-dict body → 400 (`:842`), non-string prompt
  → 400 (`:852`), unknown printer key → 400 (`:872`), unsupported method → 405 (`:927`), HEAD
  returns headers without a body (`:943`), unreadable/`not-JSON` responses surface a readable error
  on the client (`api.test.ts:47`, `:171`, `:280`).
- **The gate-failed-never-sliced invariant is tested at the HTTP layer for a fresh design**
  (`test_webapp.py:64`) — real 50-vs-20 mismatch → `gate_failed`, slice refused, *no* g-code
  produced, and `send()` is independently guarded (`webapp.py:1241`). Defense-in-depth, both ends.
- **The geometry_version stale-slice guard is tested end-to-end** by simulating a re-render landing
  mid-slice (`:1438`): the slice returns `sliced:false reason:stale` and registers no g-code
  (GET /api/gcode → 404). That is the hard concurrency case, covered.
- **Frontend error/empty/loading/disabled states are covered, not skipped.** Empty states
  (`ExportPanel.test.tsx:58`, `RightPanel.test.tsx:123`, `VersionRail.test.tsx:33`), re-render
  error with a recoverable next action (`RightPanel.test.tsx:439`), cancel/escape on every
  long-running flow — design (`App.test.tsx:368`), refine (`:420`), Escape key (`:444`), slice
  (`ExportPanel.test.tsx:71`) — each asserting NO leaked "aborted" error. The cancel-vs-error
  distinction (`isAbortError`) is unit-tested against a real `DOMException` (`api.test.ts:111`).
- **Regression discipline is visible.** Many tests cite the finding they lock down (TEST-001
  duplicate-create race, ENG-001/002, FINDING-001 "Esc closes help without cancelling the run",
  FOUND-001 inch no-op drift). Fixes arrive with tests — the owner's standing rule is being honored.
- **api.ts seam is tested for the hot paths** — payload shape, error message propagation, AbortSignal
  forwarding, `experimental` default, `job_id` threading, mesh-id parsing with cache-bust strip,
  import size-cap + connection-fail (`api.test.ts` throughout).

---

## Findings

### TEST-401 — Major — Coverage — The reopen/import re-gate → slice-refusal chain has no end-to-end test

**Category:** Coverage (systemic — the security-relevant defense is untested as wired)

**Evidence:**
- The *helper* `_regate_mesh` is unit-tested in isolation: an oversized mesh re-derives `"fail"`
  even if a tampered `.kimcad` claimed `"pass"` (`test_webapp.py:1471`), and an in-bounds mesh /
  unreadable mesh / missing plan behave correctly (`:1485`).
- The *wiring* that makes that matter lives in `_handle_design_reopen`: it calls `_regate_mesh` and
  stores the result in the slice guard — `gate_status_by_rid[rid] = regated or d.gate_status or "fail"`
  (`webapp.py:1530`–`1533`). The slice endpoint reads `gate_status_by_rid` to refuse a failed part
  (the guard pattern proven for fresh designs at `webapp.py:1235`/`1241`).
- **No test exercises the full chain:** reopen (or import-then-reopen) a design whose stored verdict
  is `"pass"` but whose actual geometry re-gates to `"fail"`, then POST `/api/slice/<newrid>` and
  assert `sliced:false reason:"gate_failed"`. `grep -n "reopen|regate" test_webapp.py` shows the
  reopen round-trip (`:1665`, `:1740`, `:1761`, `:1790`) only ever uses a *passing* template box;
  none feed a fail-re-gating mesh through reopen into slice. The import handler itself
  (`webapp.py:1598`) just stores bytes and returns an id — the re-gate happens on the subsequent
  *reopen*, so import-of-a-tampered-export is only ever defended by that untested reopen path.

**Why this matters — the bug class this allows through:** the three pieces (helper returns "fail",
reopen stores it in the guard, slice reads the guard) are each green, but their *composition* is
unverified. A refactor that drops the `regated or` term on `webapp.py:1533`, or changes the reopen
handler to seed the guard from the stored `d.gate_status` instead of `regated`, would leave **every
test green** while making a tampered/oversized `.kimcad` sliceable on reopen — i.e. a part that
fails the build-plate gate could be sent to a printer. This is the canonical "tests pass DESPITE
broken wiring" hole: the unit test guards the math, nothing guards the seam.

**Blast radius:**
- Adjacent code: `webapp.py:1530`–`1533` (reopen re-gate), `webapp.py:1598` (import), the slice
  guard at the `/api/slice` handler (reads `gate_status_by_rid`), and `_handle_design_send`
  (`webapp.py:1241`) which shares the same guard.
- Shared state: `gate_status_by_rid` — the single source of "may this rid be sliced/sent." Reopen
  and fresh-design both write it; slice and send both read it. One untested writer (reopen) feeds
  two security-relevant readers.
- User-facing: a malicious or corrupted import that lands on a printer. Low day-to-day exposure
  (local-first, single user), but the defense was *built deliberately* (ENG-002) and should be
  proven, not assumed.
- Tests to add: one HTTP-level test — build an oversized mesh, write a `.kimcad` (or seed the store
  snapshot) with `gate_status:"pass"`, reopen via `GET /api/designs/<id>`, then
  `POST /api/slice/<newrid>` and assert `sliced:false reason:"gate_failed"` and GET /api/gcode →
  404. Mirror the existing `test_web_refuses_to_slice_a_gate_failed_part` (`:64`) but through reopen.
- Related findings: TEST-402 (the reopen payload returns the stale verdict — same root seam).

---

### TEST-402 — Minor — Coverage/Quality — Reopen returns the STORED gate verdict in the report, and no test pins the displayed value to the re-gated one

**Category:** Coverage

**Evidence:** On reopen the slice *guard* uses the re-gated value (`webapp.py:1533`), but the
JSON *payload* returned to the SPA is the unmodified stored payload — `payload = dict(d.payload)`
(`webapp.py:1556`) — and the snapshot still records `"gate_status": d.gate_status` (`:1549`). So a
design that re-gates to `"fail"` is correctly slice-blocked **but** the reopened response still
carries `report.gate_status:"pass"`, which `RightPanel` renders as "Gate: Passed"
(`RightPanel.test.tsx:118`). No test asserts the reopened *report* reflects the re-gate, so this
inconsistency (slice blocked, UI says passed) is invisible to the suite.

**Why this matters:** a user reopens a part, sees "Gate: Passed," then slicing is silently refused
— a confusing, contradictory state. It's Minor (local-first, edge case: only a tampered/corrupted
or environment-shifted mesh hits it), but it's a real gap between what's enforced and what's shown,
and it shares a root with TEST-401.

**Fix path:** when adding the TEST-401 integration test, also assert the reopened payload's
`report.gate_status` matches the re-gated verdict; fix the handler to overwrite
`payload["report"]["gate_status"]` (and the readiness framing) with `regated` when it differs.

---

### TEST-403 — Minor — Coverage — Several `api.ts` library/settings/connector functions are unexercised

**Category:** Coverage

**Evidence:** `api.test.ts` covers the design/render/slice/photo/import hot paths thoroughly, but
these exported seam functions have **no frontend test**: `getSettings`, `getModelStatus`,
`getHealth`, `getConnectors`, `getConnectorStatus`, `getDesigns`, `saveDesign`, `reopenDesign`,
`renameDesign`, `deleteDesign`, `duplicateDesign` (`api.ts:309`–`456`). Their *backend* endpoints
are tested (`test_webapp.py` settings/model-status/health/connectors/designs blocks), and the App
tests mock these out (`App.test.tsx:8`–`37`), so the round-trip is covered at the ends — but the
client wrappers themselves (URL construction, `encodeURIComponent` on ids, error propagation
through `getJson`/`postJson`) are not asserted on the frontend. `saveDesign`'s `saved_id` arg and
`renameDesign`/`deleteDesign`/`duplicateDesign`'s id-encoding are the kind of thing a typo silently
breaks.

**Why this matters:** these are exercised only indirectly via mocks, so a wrong URL or a dropped
`encodeURIComponent` on a design id would not be caught by the frontend suite (the App tests assert
on the mock, not the real wrapper). Bug class: silent endpoint-string drift on the My-Designs and
Settings surfaces.

**Blast radius:** Minor — low; the backend tests would catch a server-side break and the App tests
catch the integration shape. Adding a thin `api.test.ts` block (one assertion per function on the
fetched URL + a non-2xx error propagation) closes it cheaply.

---

### TEST-404 — Nit — Quality — `KCViewport` engine paths (loadMesh/captureThumbnail/dispose) are stubbed everywhere; only the pure helpers run

**Category:** Quality / Mocking

**Evidence:** Every viewport consumer mocks `KCViewport` (`Viewport.test.tsx:16`, `App.test.tsx:40`).
Only the pure math helpers run for real (`KCViewport.test.ts`). The actual WebGL methods —
`loadMesh`, `captureThumbnail`, `clearModel`, `getDimensions`, `dispose` — have no test of their
own behavior.

**Why this matters:** this is the *correct* tradeoff (WebGL doesn't run in jsdom), and the highlight
*math* — the part with real correctness risk — IS tested directly. Flagging once, per the
"distinguish symptom from pattern" guidance: it's an accepted, well-bounded blind spot, not a defect.
The thumbnail-capture path is the only one with downstream consequences (auto-save uses it via
`onModelReady`, tested at the App level at `App.test.tsx:202`), so even that is covered at the seam.

**Fix path:** none required for beta. If a viewport regression ever ships, consider a smoke test
behind a `webgl`/headless-gl gate. Logged for completeness.

---

## Coverage gap → risk map (summary)

| Gap | Risk left open | Severity |
|---|---|---|
| Reopen/import re-gate → slice refusal never tested end-to-end | A tampered/oversized `.kimcad` could become sliceable/printable after a refactor, all tests green | Major (TEST-401) |
| Reopen payload returns stale gate verdict; not pinned by a test | UI shows "Gate: Passed" while slice is silently refused | Minor (TEST-402) |
| 11 `api.ts` library/settings/connector wrappers untested on the frontend | Silent endpoint-URL / id-encoding drift on My-Designs & Settings | Minor (TEST-403) |
| KCViewport WebGL methods stubbed | Viewport runtime regressions (accepted; math is tested) | Nit (TEST-404) |

---

## Severity counts

- **Blocker:** 0
- **Critical:** 0
- **Major:** 1 (TEST-401)
- **Minor:** 2 (TEST-402, TEST-403)
- **Nit:** 1 (TEST-404)

## Verdict

Stage 4's test suite is genuinely strong and behavioral — real-server integration + behavior-first
frontend tests, full green (262 + 149), with disciplined regression locks — and the only material
gap is that the deliberately-built reopen/import re-gate defense is proven at the helper but never
through the wired slice-refusal path (TEST-401); for a beta whose bar is zero findings, close that
one and the two Minors before the gate.
