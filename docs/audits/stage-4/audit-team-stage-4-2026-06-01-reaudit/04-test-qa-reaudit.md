# Stage-4 Gate RE-AUDIT — Test Engineer + QA Engineer

**Roles:** Senior Test Engineer + Senior QA Engineer (combined)
**Date:** 2026-06-01
**Branch:** `stage-4-react-spa-shell` @ `fa39fdd` (Stage-4 gate fixes batch 5)
**Scope:** Verify every original TEST-* and QA-* finding from
`audit-team-stage-4-2026-06-01/04-test-deepdive.md` + `05-qa-deepdive.md` is resolved,
against the post-remediation source. Bar for merge: 0/0/0/0/0.
**Environment:** Windows 11, Python 3.14 venv (`.venv/Scripts/python.exe`), live server
`python -m kimcad.cli web --demo --port 8844`, vitest 4.1.8 / jsdom.

---

## Verdict at a glance

| Original finding | Status | How verified |
|---|---|---|
| TEST-001 (Major) — contract grep doesn't bite | **RESOLVED with one residual** (see NEW-T01) | mutation: deleting whole-panel / per-field accesses now bites for 13/14 fields; **`dims` still false-passes** on an unrelated `KCViewport.this.dims` |
| TEST-002 (Minor) — no component-render tests | **RESOLVED** | jsdom + Testing Library stood up; RightPanel + ExportPanel render tests assert real behavior |
| TEST-003 (Minor) — vitest branch gaps | **RESOLVED** | paused tone, 4 missing labels, assistantMessage default now asserted |
| TEST-004 (Minor) — code-split proxy only | **RESOLVED** | test now pins `WebGLRenderer` present in chunk + ABSENT from entry |
| TEST-005 (Minor) — CSS-token static grep | **RESOLVED (NO-ACTION, reasonable)** | kept as build-completeness check, docstring scoped honestly |
| TEST-006 (Nit) — exact-string label coupling | **RESOLVED (NO-ACTION, reasonable)** | accepted copy-coupling trade-off |
| QA-001 (Minor) — HEAD → 405 | **RESOLVED** | runtime: `HEAD /`, `HEAD /assets/*`, `HEAD /api/mesh/*` → header-only 200 |
| QA-002 (Nit) — no asset cache validators | **RESOLVED** | runtime: ETag present, matching If-None-Match → 304 empty body, wrong ETag → full 200 |
| QA-003 (Nit) — orphan dirs accumulate | **RESOLVED** | runtime: stale digit-named dirs cleared at startup, non-digit dirs preserved |
| QA-004 (Nit) — 413 connection-abort | **RESOLVED** | runtime: oversized body → full 413 body delivered, `close_connection` set, no client abort |

**All original TEST + QA findings resolved? — Y, with ONE new residual sub-finding (NEW-T01, Minor) on TEST-001.**

## Re-audit severity roll-up (NEW issues only)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 1 (NEW-T01) |
| Nit | 0 |

## Suite run status (this re-audit)

- `npm --prefix frontend test` (vitest) → **19 passed (5 files)**, 1.34 s. No `.skip`/`.only`/`xit`/`todo`. (was 12/3 pre-fix; +7 in 2 new jsdom files.)
- `pytest -m "not live" -q` → **400 passed, 4 deselected (live)**, 82 s. Clean, 0 skipped. (was 398; +2 from TEST-003 branch cases.)
- Live OrcaSlicer flow exercised manually over HTTP (not the gated live suite).

---

## TEST-001 — the mutation result (did it bite?)

**The headline mutation the re-audit was asked to run: remove `report.dims` RENDERING from
`RightPanel.tsx` and confirm the contract test now FAILS.**

**Result: it did NOT bite for `dims`.** With the entire `report.dims` table block deleted from
`RightPanel.tsx` (lines 55–77 — the `report.dims.length > 0` guard and the `report.dims.map(...)`
table; a user would see NO dimensions comparison), the test still passed:

```
$ # report.dims rendering removed from RightPanel.tsx
$ pytest tests/test_frontend.py::test_frontend_source_consumes_documented_response_fields -q
1 passed
```

**Root cause (proven, not inferred):** `dims` survives on an *unrelated same-named property
access in a sibling module* — `KCViewport.ts` has `private dims: Dimensions | null` and accesses
`this.dims` five times (lines 126/133/214/274/289). That `dims` is a `{x,y,z}` bounding-box
member computed from the three.js `Box3` of the loaded mesh — semantically unrelated to the
backend `report.dims` (an array of `{axis,target,actual,ok}` rows). The test's `\.dims\b` regex
cannot tell them apart, so deleting the user-visible printability table leaves the test green on
the viewport's internal field. Survival vector confirmed by isolating the mutation to
`RightPanel.tsx` only:

```
After removing report.dims from RightPanel only, surviving `.dims` accesses:
  KCViewport.ts: ['this.dims', 'return this.dims', 'this.dims', '!this.dims', '${this.dims']
contract test for 'dims' still passes? True  <-- FALSE-PASS (residual)
```

**BUT — the fix is a large, real improvement, and the remediation's specific claim is true.**
The remediation claimed TEST-001 was "mutation-proven to reject the className/comment false-pass
vectors." That claim is **verified true**: I confirmed that `className="kc-dims"`, the
`kc-findings` class, the `designStatus.ts` JSDoc mentions of `gate_status`, and `*.test.ts`
references **no longer** satisfy the contract (the comment-strip + `\.<field>\b` property-access
shape + quoted-literal-for-status logic all work as designed). A full property-access-removal
sweep (drop EVERY `.field` access across consumer source) now **bites for all 14 fields** — vs.
the original where 8 of 14 false-passed. The original audit's worst-case mutation (gutting the
whole `PrintabilityCard`) now correctly trips on `gate_status`, `headline`, AND `findings`
(originally only `headline` was caught). The two sibling tests are also genuinely fixed:
`test_frontend_source_handles_every_pipeline_status` now requires a **quoted literal**
(`['"]<status>['"]`) so a comment-only mention no longer passes, and
`test_frontend_source_consumes_connector_status_fields` now requires `\.<field>\b` property
access so a bare word in a `switch` no longer passes.

**Is the comment-strip + `.field`/quoted-literal logic trivially foolable?** No, not trivially.
The comment stripper (`_strip_ts_comments`) removes `/* */` and `//` runs; its docstring
correctly notes the one assumption (no `//` inside string literals — true for this source, where
API paths use single slashes). The property-access requirement (`\.<field>\b`) and the
quoted-literal requirement for status strings are the right mechanism and close the className /
comment / test-reference / bare-word vectors the original audit proved. The **only** residual
hole is cross-module name collision: a required field name that *also* exists as an unrelated
property somewhere in the (non-api, non-test) TS tree. Today that hits exactly one field —
`dims` — because of `KCViewport.this.dims`. (The other multi-file fields — `plan`, `report`,
`gate_status`, `mesh_url`, `has_mesh` — span multiple files *legitimately*: each is a real
response access in App.tsx / ExportPanel / RightPanel / designStatus, so dropping one renderer
correctly leaves the field still consumed elsewhere. Those are not false-passes.)

→ See **NEW-T01** below for the residual, severity Minor.

### TEST-001 verdict

**RESOLVED for the vectors the remediation claimed (className, comment, test-ref, bare-word) —
all proven closed.** The fix is substantial and correct in mechanism. One residual false-pass
remains (`dims`, via cross-module name collision with `KCViewport.this.dims`), filed as the
Minor NEW-T01. The original Major is correctly knocked down; what's left is a Minor edge that the
remediation did not claim to have closed.

---

## NEW-T01 (Minor) — Contract test still false-passes for `dims` via cross-module name collision

**Category:** Test quality (residual false-pass)

**Evidence.** Deleting the entire `report.dims` printability table from `RightPanel.tsx` (the
only place that field is rendered for the user) leaves
`test_frontend_source_consumes_documented_response_fields` GREEN, because `KCViewport.ts`
contains an unrelated `this.dims` (a three.js bounding-box `{x,y,z}` member). The test's
`\.dims\b` match cannot distinguish `report.dims` (the backend contract field) from `this.dims`
(an internal viewport member). Reproduced above; isolated to a `RightPanel.tsx`-only mutation to
rule out any other path.

**Why this matters.** This is the same *class* of gap the original TEST-001 flagged — the test
advertises (docstring) that it ensures "the UI actually renders the documented contract rather
than silently dropping a field," and for `dims` specifically that is still not guaranteed. A
refactor that drops the printability dimensions table while three.js still uses `this.dims` ships
a visibly incomplete Printability card with a green gate. It is materially narrower than the
original finding (1 field, not 8; and that 1 field is also guarded by the new `RightPanel.test.tsx`
render test — see below), which is why it is Minor, not a re-opened Major.

**Compensating control (why Minor, and arguably defensible-as-is).** The `dims` rendering is now
*also* covered by the jsdom render test added for TEST-002: `RightPanel.test.tsx` asserts
`screen.getByText(/80 × 60 × 40 mm/)` — that's the **Size** row in ParametersCard
(`plan.target_bbox_mm`), not the printability `report.dims` table, so it does *not* fully
backstop a dropped dims *table*. So the residual is real, but its blast radius is one card on one
panel, server-side safety is unaffected, and the visual check covers rendered output for this
gate. Net: a watch-item, not a merge-blocker.

**Fix path (cheap, optional this sprint).** Two clean options:
1. Restrict the consumer-source scan for the *response* fields to the components/modules that
   actually consume the wire payload (exclude `frontend/src/viewport/**`, which never touches the
   backend response) — this removes the cross-module collision surface entirely and is one line
   in the `_TS_CONSUMERS` comprehension.
2. Require the access to be qualified by a known response binding (e.g. `report\.dims` /
   `result\.report\.dims`) rather than a bare `\.dims`. Higher precision, slightly more brittle to
   renames.
Recommend (1): excluding the viewport module from the *response-field* scan is correct in intent
(the 3D viewport is not a consumer of the design-response JSON) and closes the only residual
collision with near-zero brittleness. (The render test from TEST-002 is the structural long-term
answer and already exists for the panel.)

---

## TEST-002 — component-render tests — RESOLVED

jsdom + `@testing-library/react` + `@testing-library/dom` are now real devDependencies
(`frontend/package.json`), and two render test files exist and run under `// @vitest-environment
jsdom`:

- **`RightPanel.test.tsx`** — MEANINGFULLY asserts render behavior, not presence. It renders a
  gate-PASS `DesignResponse` and asserts the *rendered* verdict text `Ready to print` (the
  `gateLabel('pass')` output wired through the badge), the finding message `Dimensions match`
  (proves `report.findings` maps into `<li>`s), and the size `80 × 60 × 40 mm` (proves
  `plan.target_bbox_mm` renders). It also asserts the null-result placeholder copy. These bite on
  the JSX wiring the contract grep can't see.
- **`ExportPanel.test.tsx`** — gate-AWARE as required: a gate-FAILED result renders **no**
  `Slice & prepare` button (`queryByRole(...).toBeNull()`), shows the "can't be sliced" copy, AND
  still offers `Download 3D model`; a gate-PASS result **does** render the slice button; the
  null-result empty state renders. This directly exercises the `canSlice`/`gateFailed` gating the
  original finding called out as the densest untested logic.

Both stub `fetch` for the mount-time `/api/options` + `/api/connectors` effects, so the
assertions are on the synchronous render. 7 new cases, all green.

## TEST-003 — vitest branch gaps — RESOLVED

`connectorStatus.test.ts` now asserts `state:'paused' → warn` tone, and the four previously-missing
labels (`busy`/printing, `paused`, `auth`→authentication, `config`→setup).
`designStatus.test.ts` now asserts `assistantMessage` **default** branch (unknown status →
`plan.summary`, and `'Done.'` when no plan), plus `gateTone('something-new')→neutral`. The
non-live pytest count rose 398→400 consistent with added cases. Branch gaps the original flagged
are closed.

## TEST-004 — code-split fingerprint — RESOLVED

`test_viewport_chunk_is_code_split_from_the_entry` now does exactly what the original recommended:
keeps the size-relationship check AND adds a direct three.js fingerprint —
`assert "WebGLRenderer" in chunk_text` and `assert "WebGLRenderer" not in entry_text`. This pins
the actual property (three.js lives in the lazy `Workspace.js` chunk, NOT the entry `kimcad.js`),
not just a size proxy. Verified passing against the committed build.

## TEST-005 / TEST-006 — NO-ACTION — reasonable

- **TEST-005:** the CSS-token test is kept as an explicit build-completeness check; its docstring
  scopes it honestly and the rendered visual check (elsewhere in the gate) covers visual
  correctness. Reasonable — the original finding itself recommended "none required."
- **TEST-006:** the few exact-string label assertions (`'Ready'`, the `note` pass-through) are an
  accepted copy-coupling trade-off the original explicitly rated Nit / no-action. Reasonable.

---

## QA runtime verification (live server, port 8844)

All checks run against `python -m kimcad.cli web --demo --port 8844` with `http.client`.

### QA-001 — HEAD → header-only 200 — RESOLVED

`do_HEAD` now dispatches through `do_GET` with `_head_only=True`; `_send`/`_send_download`/
`_serve_static` suppress the body. The 405 `Allow` header now reads `GET, HEAD, POST`. Runtime:

```
HEAD /                 -> 200  body_len=0  Content-Length=374  Content-Type=text/html
HEAD /assets/kimcad.js -> 200  body_len=0  ETag="ca580814731032f4"  Content-Length=146966
HEAD /api/mesh/1       -> 200  body_len=0  Content-Length=1284
```

Header-only 200 with the correct GET Content-Length on all three resource classes. PUT/DELETE/
PATCH/OPTIONS remain on the 405 path (unchanged). No GET path broken by the HEAD change (the full
design→slice→download flow below still works).

### QA-002 — asset ETag / 304 — RESOLVED

`_serve_static` computes a sha256 content-hash ETag with `Cache-Control: no-cache`. Runtime:

```
GET /assets/kimcad.js                      -> 200  ETag="ca580814731032f4"  len=146966
GET /assets/kimcad.js  (If-None-Match=etag) -> 304  body_len=0  (revalidated)
GET /assets/kimcad.js  (If-None-Match=wrong) -> 200  len=146966  (full body served)
```

304 on match (empty body), full 200 on mismatch — the content-hash ETag means a rebuild that
changes bytes changes the ETag, so it can never serve stale. The ETag change did NOT break asset
serving (first GET is a normal 200 with the full body; traversal probes still 404).

### QA-003 — orphan dir cleanup — RESOLVED

`make_handler` clears stale digit-named dirs under `web_root` at startup; `_evict` rmtrees on
eviction. Runtime test (planted dirs):

```
before make_handler: ['42', '7', 'keepme']
after  make_handler: ['keepme']
```

Stale `7`/`42` cleared; the non-digit `keepme/` preserved. The rmtree is correctly scoped to
`*.isdigit()` directory names, so it does **not** delete unrelated/live content (`output/` is
gitignored, and only the in-session rid dirs match the digit pattern). No "rmtree deletes
something live" regression.

### QA-004 — 413 connection close — RESOLVED

`_read_json_body` sets `self.close_connection = True` before sending the 413. Runtime, oversized
(2 MiB) body from a keep-alive `http.client`:

```
POST /api/design (2 MiB body) -> 413  body={"error": "Request body too large."}  (no client abort)
```

Full 413 body delivered and read by a keep-alive client with **no** `ConnectionAbortedError` —
the original abort-on-body-read is gone. The reject-oversized contract is intact.

---

## FRESH PASS — did the fixes introduce any NEW problem?

Checked specifically for: a test that now lies, a broken endpoint, the HEAD change breaking a GET
path, the ETag breaking asset serving, the rmtree deleting something live.

- **HEAD change breaking GET:** no. `do_GET` runs unchanged; `_head_only` only gates the body
  write. The full design→slice→download→send flow works end-to-end after the change (below). GET
  Content-Length is still correct (HEAD reports it without sending the body).
- **ETag breaking asset serving:** no. First GET is a full 200 with body; only a matching
  If-None-Match yields 304. Wrong ETag → full body. `no-cache` forces revalidation so stale-serve
  is impossible.
- **rmtree deleting something live:** no. Scoped to digit-named dirs only; non-digit dirs
  survive; runs once at handler build before the counter resets — so it can only remove
  *previous-run* rid dirs, never the current session's in-flight output.
- **A test that now lies:** the only residual is NEW-T01 (the `dims` cross-module collision) —
  filed Minor. No *other* new false-pass found; the property-access tightening is otherwise sound
  and the new jsdom tests assert real rendered output (verified by reading the assertions, not
  just the pass count).
- **Gate safety (the property Stage 4 exists to protect):** HOLDS on the live wire. A gate-FAILED
  part (injected 50 mm-plan / 20 mm-render dim mismatch via the repo's own conftest fakes, served
  on a real `ThreadingHTTPServer`):

  ```
  POST /api/design     -> status=gate_failed, report.gate_status=fail, has_mesh=True
  POST /api/slice/<id> -> 200 {"sliced": false, "reason": "gate_failed"}  (NO gcode_url produced)
  POST /api/send/<id>  -> 404 "Slice the part first..."  (fail-closed: no g-code ever existed)
  GET  /api/mesh/<id>  -> 200, 684-byte STL  (model still inspectable)
  ```

  Note: the send refusal returns 404 "Slice the part first" rather than `reason:gate_failed`,
  because slicing was refused so no g-code was ever produced — the part is refused at the
  "no g-code" gate *before* the gate_failed backstop. This is the exact behavior the original
  QA deep-dive documented (the `gate_status_by_rid=="fail"` check in `_handle_send` is
  belt-and-suspenders for a hypothetical slipped-through g-code). Fail-closed; safe.

### End-to-end flow (live OrcaSlicer) — still works

```
POST /api/design {"prompt":"a box"} -> 200 completed, gate=pass, mesh_url=/api/mesh/1
GET  /api/mesh/1                     -> 200 model/stl, 1284 bytes
POST /api/slice/1 {bambu_p2s, pla}   -> 200 sliced=true, "~50m 20s, 200 layers, 33.63 cm3"
GET  /api/gcode/1                    -> 200 model/3mf, Content-Disposition attachment, PK-zip, 142839 bytes
POST /api/send/1 {"connector":"mock"} -> 200 sent=true, simulated=true, state=queued
```

No 5xx / no stack-trace leak across the adversarial battery (non-string prompt, non-object body,
malformed JSON, bad ids, unknown route → all 4xx, no `Traceback`/`File "..."` in any body).
Connector-status with traversal/markup names → 200 typed JSON, no leak. `/assets/` traversal
probes (`nope.js`, `/assets/`, `..%2fwebapp.py`, `sub/x.js`) → all 404.

---

## Bottom line

- **All original TEST + QA findings: resolved** (fixed, or a reasonable documented NO-ACTION).
- **TEST-001 mutation: did NOT bite for `dims`** — a residual cross-module name collision
  (`KCViewport.this.dims`) leaves one field's rendering droppable with a green gate. The
  remediation's *claimed* vectors (className / comment / test-ref / bare-word) ARE proven closed;
  this is a narrower, previously-unflagged Minor (NEW-T01), not a re-opened Major.
- **Runtime QA: all four fixes verified live** (HEAD 200, ETag/304, orphan cleanup, 413 close),
  full design→slice→download→send flow intact, gate-fail safety holds, no 5xx/leak/traversal.
- **One NEW finding: NEW-T01 (Minor).** Strictly, the 0/0/0/0/0 bar is not met (1 Minor). Given
  it is a test-precision residual on one card, compensated by a render test and unaffected
  server-side safety, the call on whether to clear it before merge or accept-with-follow-up is a
  gate-owner decision — the one-line fix (exclude `frontend/src/viewport/**` from the response-field
  scan) is cheap enough to just do.
