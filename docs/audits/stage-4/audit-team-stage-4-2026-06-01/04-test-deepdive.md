# Stage-4 Gate Audit — Test Engineer Deep-Dive

**Role:** Senior Test Engineer
**Date:** 2026-06-01
**Scope:** The Stage-4 test surface only — `tests/test_frontend.py` (rewritten contract checks),
the `tests/test_webapp.py` `/assets/` serve+traversal test, and the vitest suite
`frontend/src/*.test.ts` (api / designStatus / connectorStatus), wired into `scripts/ci.sh`.

---

## Test-suite shape (one-paragraph orientation)

For the Stage-4 frontend surface the shape is: **a thin band of fast TS unit tests (12 vitest
cases over the three pure/typed modules — api, designStatus, connectorStatus), a set of
static "contract" greps in Python against the built artifacts and the TS source, and a
genuinely strong HTTP integration layer in `test_webapp.py` that drives the real server over an
ephemeral socket.** There are **no component-render tests** (no jsdom; KCViewport, ExportPanel,
ChatPanel, RightPanel, ConnectorStatus are untested at the component level). The integration
layer (Python HTTP) is the strongest part of the whole surface and deserves credit. The static
"contract" greps are the weakest — they assert *presence of a word*, not *rendering of a field*,
and several of them do not bite when the behavior they claim to protect is removed.

**Run status (verified this audit):**
- `vitest run` → **12 passed (12)**, 233 ms. No `.skip`/`.only`/`xit`/`todo`.
- `pytest tests/test_frontend.py tests/test_webapp.py -q` → **49 passed**, 17.8 s.
- `pytest -m "not live" -q` → **398 passed, 0 skipped**, 4 deselected (live), 79 s. Clean.

---

## Finding summary

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 1 |
| Minor    | 4 |
| Nit      | 1 |
| **Total**| **6** |

---

## Findings

### TEST-001 (Major) — The field-contract grep does not bite: it passes on comments, CSS class names, and unrelated identifiers, not on actual rendering

**Category:** Quality / Coverage (false-pass)

**Evidence — proven by mutation, not inferred.** I gutted the entire `PrintabilityCard` in
`frontend/src/components/RightPanel.tsx` — removed *every* `report.*` property access (the gate
badge, the headline, the dims table, the findings list — `report.` count went from 11 to 0),
leaving only empty stub elements that still carried `className="kc-dims"` and
`className="kc-findings"`. A real user would see a completely broken printability panel. I then
ran the real test:

```
$ pytest tests/test_frontend.py::test_frontend_source_consumes_documented_response_fields -q
AssertionError: frontend consumer source does not reference backend fields: ['headline']
```

It caught **only `headline`**. The removal of `gate_status`, `dims`, and `findings` rendering
went **undetected**, because:
- `gate_status` survives on the JSDoc comment in `designStatus.ts:8`
  (`/** Map the printability gate_status onto ... */`).
- `dims` survives on the leftover CSS class `className="kc-dims"` (`RightPanel.tsx:56`).
- `findings` survives on a comment (`RightPanel.tsx:7`) **and** the CSS class
  `className="kc-findings"` (`RightPanel.tsx:80`).

A systematic property-access-removal sweep (proxy for "stop rendering this field") shows the
test **still passes with zero property access** for 8 of the 14 required fields:

```
status, plan, report, error, summary, gate_status, dims, findings  → FALSE-PASS
```

The reasons are mundane and pervasive: `status` matches the local React state `const [status,
setStatus]`, the helper call `connectorTone(status)`, and `role="status"`; `error` matches the
unrelated `const [error, setError]` in App.tsx; `report`/`plan` match comments and the local
`const report`/`const plan` even when the data-source access is gone.

The test's own docstring claims it ensures "the UI actually renders the documented contract
rather than silently dropping a field." For at least `gate_status`, `dims`, and `findings` that
claim is demonstrably false — the field can stop being rendered and the test stays green. This
is the textbook "Grep-passing ≠ UI-correct" lie (test-engineer brief, item 2).

The same flaw is present in the two sibling tests:

- `test_frontend_source_handles_every_pipeline_status` uses a bare substring `in` (not even a
  word boundary). All four status strings appear in **both** a `case` branch and the line-37
  doc comment of `designStatus.ts`. Deleting every `case` branch in `assistantMessage` (the
  actual branching logic) leaves the test green on the comment alone — exactly the "merely named
  in a comment" failure the docstring says it prevents. Verified: with all `case ` lines
  stripped, all four still report `still_passes=True`.
- `test_frontend_source_consumes_connector_status_fields` is the weakest: **all five** fields
  (`ready/online/state/reason/simulated`) survive removal of every `.field` property access,
  because they all appear as bare words in `switch`/`if` conditions, comments, and the destructured
  `ConnectorStatusResponse` usage on the same lines.

**Why this matters.** This is the headline test of the Stage-4 frontend surface — it is the
thing standing between "the backend puts a field on the wire" and "the user sees it." It is
advertised (in its docstring and presumably in the gate narrative) as proof the rendered
contract holds. It is not that. It is a spell-checker: it verifies the *words* exist somewhere
in the TS tree. A refactor that drops a field's rendering while leaving a same-named local, a
CSS class, or a doc comment behind ships a visibly broken panel with a green gate. The bug class
it admits: **silent field-drop regressions in the printability and plan panels** — the two
panels Stage 4 exists to deliver.

**What's genuinely good about it (so the fix is targeted, not a rewrite):** excluding `api.ts`
is *correct* — declaring a field in an interface is not consuming it, so a field rendered
nowhere should still trip the test, and excluding the type module enforces that intent.
Excluding `*.test.ts` is also correct (a field named only in a test must not satisfy the
contract). The *intent* is right; the *mechanism* (substring grep over whole-file text) is too
loose to deliver it.

**Blast radius:**
- Adjacent code: all three static-contract tests in `tests/test_frontend.py`
  (`test_frontend_source_consumes_documented_response_fields`,
  `test_frontend_source_handles_every_pipeline_status`,
  `test_frontend_source_consumes_connector_status_fields`) share the identical root cause.
  Fix them together.
- Shared assumption: the gate narrative treats "static contract test green" as "the UI renders
  the contract." That inference is unsound and may be repeated in later-stage gates if the
  pattern is copied for sliders/send.
- User-facing: no behavior changes from fixing the *test*; the value is that future field-drop
  regressions in RightPanel/ChatPanel start failing CI.
- Migration: none.
- Tests to update: the three tests above; no production code change required.
- Related findings: this is the same root as the component-render gap (TEST-002) — both stem
  from there being no test that actually exercises the rendered output. They reinforce each
  other: with no render test *and* a contract test that doesn't bite, RightPanel's rendering is
  effectively unguarded.

**Fix path (concrete, low-cost):** tighten each check from "word appears anywhere" to "field is
*consumed* as a property." Two viable options, recommend the first:
1. **Require a property-access shape, not a bare word.** Match `\.<field>\b` (and, for the
   PipelineStatus strings, require them inside a quoted literal `['"]<status>['"]`, not in a
   comment) after stripping `//` and `/* */` comments from the source first. This makes the
   3-field printability removal I performed fail as it should, with near-zero added brittleness.
2. The structurally sound but heavier option is a real render test (see TEST-002); a tightened
   grep is the cheap win that closes the immediate hole this sprint.

---

### TEST-002 (Minor) — No component-render tests; RightPanel/ChatPanel/ExportPanel/ConnectorStatus/KCViewport are untested at the component level

**Category:** Coverage (blind spot)

**Evidence.** The vitest suite covers only the three framework-free modules: `api.ts` (fetch
wrappers + `designIdFromMeshUrl`), `designStatus.ts` (`gateTone`/`gateLabel`/`assistantMessage`),
and `connectorStatus.ts` (`connectorTone`/`connectorLabel`). There is no jsdom environment and
no `@testing-library/react` dependency in `frontend/package.json`. Therefore:
- `RightPanel.tsx` — the dims table, findings list, and gate-badge JSX are unit-untested. The
  *mappers* it calls (`gateTone`/`gateLabel`) are tested, but the wiring from `report.dims` /
  `report.findings` into rendered rows/items is not.
- `ExportPanel.tsx` — the printer/material `useMemo` derivation, the `canSlice` gating
  (`gateFailed`, `sliceable`, slicing-in-flight), and the slice/error/download branches are
  untested. This is the most logic-dense component in the surface and has zero direct coverage.
- `ChatPanel.tsx`, `ConnectorStatus.tsx`, `Viewport.tsx`/`KCViewport.ts` — untested at the
  component level. KCViewport (the three.js wrapper) is the hardest to test and the least
  surprising omission.

**Why this matters.** The `assistantMessage`/`gateTone`/`connectorTone` *mappers* are well
tested, which de-risks the panels significantly — most of the branchy logic lives in the pure
modules, by design. The residual risk is in the JSX wiring and `ExportPanel`'s derived state:
e.g. a printer-change-with-stale-material bug, or a `canSlice` regression that lets a
gate-failed part be sliceable in the UI, would not be caught by any unit test.

**Why Minor, not Major (per the DO-NOT-FLAG guidance).** Component-render tests are an explicit,
acknowledged deferral for this stage, and the gap is meaningfully *compensated* by two things:
(a) the rendered visual check performed elsewhere in this gate, and (b) the server-side guards in
`test_webapp.py` that prove the *backend* refuses to slice a gate-failed part
(`test_web_refuses_to_slice_a_gate_failed_part`) — so even if the UI's `canSlice` were wrong, no
G-code reaches a printer. The defense-in-depth makes the UI-logic gap a watch-item, not a
release risk. It is, however, a **real systemic gap** that will grow when Stage 5 adds live
sliders and the send UI — `ExportPanel` is already the densest untested component and is about to
get denser.

**Blast radius:**
- Adjacent code: all of `frontend/src/components/*` and `frontend/src/viewport/*`.
- User-facing: panel rendering and the slice-gating UX.
- Migration: adding jsdom + testing-library is additive (devDependencies only; runtime ships no
  Node).
- Tests to update: none; this is net-new coverage.
- Related findings: TEST-001 (the contract grep doesn't compensate for this gap the way the
  gate narrative implies).

**Fix path:** add `@testing-library/react` + `jsdom` and a vitest `environment: 'jsdom'` and
write a handful of render tests for the two highest-value components: `RightPanel` (assert a
`fail`/`warn`/`pass` report renders the right badge text, the dims rows, and each finding) and
`ExportPanel` (assert a gate-failed result disables slicing and still offers the model download).
Recommend scoping this to those two components in Stage 5 rather than chasing full coverage —
`RightPanel` is what TEST-001's grep falsely claims to protect, and `ExportPanel` carries the
slice-gating UX.

---

### TEST-003 (Minor) — vitest branch gaps in the pure mappers (the modules that *are* tested)

**Category:** Coverage

**Evidence.** The 12 vitest cases exercise meaningful behavior — they are not shallow. `postDesign`
covers the 200 path, the non-2xx-with-`error` path, and the body-not-JSON path; `designIdFromMeshUrl`
covers valid / undefined / non-numeric; `postSlice` asserts the POST *target* (`/api/slice/7`)
and method; `assistantMessage` branches on all four PipelineStatus values plus two missing-field
fallbacks. That is good. But specific branches in the source are unexercised:
- `assistantMessage` **default** branch (unknown/future status) — `designStatus.ts:52-53` — not
  hit by any case (`grep "default" designStatus.test.ts` → none).
- `connectorTone` `state === 'paused'` → `warn` branch (`connectorStatus.ts:15`) — untested
  (only `reason:'busy'` and `state:'printing'` are asserted).
- `connectorLabel` covers 5 of its 9 outcomes. Untested labels: `Busy — printing`, `Paused`,
  `Authentication failed` (`reason:'auth'`), `Needs setup` (`reason:'config'`), and the final
  `Not ready` fallback.
- `gateLabel` default ("Checked") and `gateTone`'s `something-new`→`neutral` *is* covered (good).

**Why this matters.** These are honest readiness/printability labels shown to the user. An
untested branch is a branch that can silently change — e.g. someone edits the `auth`/`config`
copy and no test notices. Low blast (pure functions, no data risk), hence Minor.

**Fix path:** add ~5 assertions to the existing `connectorStatus.test.ts` and `designStatus.test.ts`
describe blocks — paused tone, the four missing labels, and the `assistantMessage` default. These
are one-line additions to suites that already exist; near-zero cost, closes the mapper gaps so the
*tested* modules are actually fully tested.

---

### TEST-004 (Minor) — The code-split test asserts a size *relationship* as a proxy for "three.js is split out" — robust today, but indirect

**Category:** Quality (assertion strength)

**Evidence.** `test_viewport_chunk_is_code_split_from_the_entry` asserts
`Workspace.js.size > kimcad.js.size`. Measured today: `Workspace.js` = 532,675 B, `kimcad.js`
= 147,903 B → **3.6×**. The margin is large because three.js (~the whole 3D engine) lives in the
lazy chunk while the entry is just the app shell + React, so the assertion is **not brittle in
practice** — a normal app-code edit will not flip the inequality.

The weakness is that it's an *indirect* proxy. It does not verify that three.js is *absent from
the entry* — it would still pass if three.js were accidentally bundled into **both** chunks (the
entry would just be relatively smaller). It also doesn't verify the dynamic `import()` in
`App.tsx:8` actually produces a *separately fetched* chunk (vs. an eager import that Rollup
happened to name `Workspace.js`). So it confirms "a Workspace chunk exists and is bigger than the
entry," which is *evidence of* but not *proof of* the lazy-load that keeps the landing screen
light.

**Why Minor/Nit-adjacent.** The thing it's a proxy for is real and currently true, and the size
gap gives it a comfortable safety margin. It's worth strengthening but not worth blocking on.

**Fix path (optional, cheap):** additionally assert that the entry bundle does **not** contain a
three.js fingerprint (e.g. `"three.module"` / a known three export string) — that directly pins
"three is not in the entry," which is the actual property the lazy-load is supposed to deliver.
Keep the size check too; the two together are robust.

---

### TEST-005 (Minor) — `test_built_css_carries_workshop_tokens` is a static asset grep (correct for its purpose, but credit-where-due on its limits)

**Category:** Quality (static ≠ runtime)

**Evidence.** `test_built_css_carries_workshop_tokens` asserts the literal strings `#c8623a`,
`#14171c`, and the three font-family names exist in the concatenated built CSS;
`test_workshop_fonts_are_bundled_for_offline_use` asserts a latin `*.woff2` exists per family.
These are presence checks on the build output — they confirm the tokens survived the Vite build
and the fonts are self-hosted (the offline requirement). That is the *right* check for "did the
build include the theme + fonts," and it correctly bites on a missing/empty build.

What it cannot tell you (and shouldn't be read as telling you): that the token is *applied to the
right element*, or that the font actually *renders* (a `@font-face` can reference a woff2 that
exists but is never used by any selector). This is the "Static ≠ Runtime" caveat (brief item 1) —
flagged here at Minor only so the gate narrative doesn't over-read a CSS grep as a visual proof.
The rendered visual check elsewhere in this gate is what closes that gap.

**Fix path:** none required — this test is correctly scoped to "the build is internally
complete." Recommend the gate's "What's working" note this is a build-completeness check, not a
visual-correctness check, to keep the altitude honest.

---

### TEST-006 (Nit) — `gateLabel`/`connectorLabel` assertions couple to user-facing copy via regex

**Category:** Quality (brittleness)

**Evidence.** `designStatus.test.ts` asserts `gateLabel('fail')` matches `/not printable/i` and
`connectorStatus.test.ts` asserts labels match `/offline/i`, `/simulated/i`, etc. These regex
matches are appropriately *loose* (they tolerate copy tweaks like "Not printable yet" → "Not
printable") which is good. The one fully-literal coupling is `connectorLabel(...)` `.toBe('a
specific reason')` and `.toBe('Ready')` — exact-string, so a copy change to the `note`
pass-through or the "Ready" label would require a test edit.

**Why Nit.** This is the correct trade-off (you *want* to pin "Ready" exactly and the `note`
pass-through exactly), not a defect. Mentioned once for completeness; no action needed.

---

## What's working (credit where due)

- **The HTTP integration layer in `test_webapp.py` is the strongest test in the whole surface.**
  `test_serves_spa_index_and_assets_and_rejects_traversal` drives the **real** server over an
  ephemeral socket: it GETs `/`, parses the actual served shell, fetches *every* `/assets/`
  bundle the shell references, asserts the right content types (javascript / text/css) and
  non-empty bodies, **and** verifies traversal rejection on four hostile paths
  (`/assets/nope.js`, `/assets/`, `/assets/sub/x.js`, `/assets/..%2fx`). This is a genuine
  integration test, not a unit test in disguise — it proves the serve+security contract end to
  end. Credit.
- **The static contract tests get the *exclusions* right even though the *mechanism* is loose.**
  Excluding `api.ts` (declaration ≠ consumption) and `*.test.ts` (a field named only in a test
  must not count) reflects correct thinking about what "consuming a field" means. The intent is
  sound; only the matching is too coarse (TEST-001).
- **The vitest cases test behavior, not implementation.** `postDesign` covers all three response
  shapes including both error paths; `postSlice` pins the actual POST *target and method*
  (`expect(fetchMock).toHaveBeenCalledWith('/api/slice/7', {method:'POST'})`) rather than just
  the return value; `assistantMessage` branches on all four statuses plus fallbacks. No
  assert-True placeholders, no import-only tests.
- **Zero shortcuts.** No `.skip`/`.only`/`xit`/`it.todo` in the vitest files; the non-live pytest
  run is `398 passed, 0 skipped` — the suite isn't green-because-skipped.
- **CI wiring is honest and well-reasoned.** `scripts/ci.sh` runs vitest under `set -e` (a vitest
  failure blocks the push on a dev box), degrades gracefully to a *loud SKIP note* when
  `frontend/node_modules`/`npm` are absent (the committed build still ships), and — importantly —
  refuses to let a release tag be cut from a run where the live OrcaSlicer tests were skipped
  (`KIMCAD_RELEASE=1` → hard fail). The `-ra` flag surfaces skip reasons so a green-without-binary
  run can't masquerade as a proven one. This is mature CI-signal hygiene.
- **The `_trimesh_can_export_3mf` skip-guard is the right pattern** (skip cleanly rather than muddy
  the gate when an optional backend is absent) — and on the pinned venv it didn't trigger, so the
  3MF content-type path actually ran this audit.

---

## Pattern observation for the exec report

The single most valuable finding for leadership: **the Stage-4 "field contract" test is a
spell-checker, not a contract test.** It is positioned in the gate narrative as proof that the
SPA renders every field the backend sends, but a proven mutation (gutting the entire printability
panel) showed it catches only 1 of 4 dropped fields — the rest survive on CSS class names, doc
comments, and same-named local variables. Combined with the absence of any component-render test,
the rendering of the two panels Stage 4 exists to deliver (printability + plan) is effectively
unguarded by automated tests; it is currently held up by the manual rendered visual check alone.
Neither issue is a Blocker — the backend's own guards prevent a gate-failed part from being
sliced regardless of UI state, and the visual check covers the rendered output for *this* gate —
but the test surface is advertising a level of protection it does not provide, and that gap will
widen as Stage 5 adds slider and send UI to the already-untested `ExportPanel`. Recommended this
sprint: tighten the three contract greps to require property-access/quoted-literal shapes (cheap,
high leverage); next sprint: add jsdom render tests for `RightPanel` and `ExportPanel`.
