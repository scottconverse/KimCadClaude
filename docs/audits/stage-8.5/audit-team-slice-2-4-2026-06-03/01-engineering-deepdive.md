# 01 — Principal Engineer Deep-Dive

**Audit:** KimCad Stage 8.5 Slices 2–4 ("live design refinement" batch)
**Branch / HEAD:** `stage-8.5-usability` @ `2ea65e9`
**Diff base:** `d56b251..HEAD` (excluding `docs/audits` and built `src/kimcad/web/assets`)
**Role:** Principal Engineer (architecture, correctness, security, performance, data provenance)
**Posture:** Balanced
**Date:** 2026-06-03

---

## Summary

This batch threads three usability slices onto the existing design loop: a multi-turn
conversation thread with refine + version timeline + compare (Slice 2), inline numeric editing
of parameter sliders (Slice 3), and an app-wide mm/inch display toggle (Slice 4). On the backend
the only surface change is a new `_sanitize_history` boundary and a `history=` parameter threaded
from `/api/design` into the already-tested `pipeline.run(...)`.

The engineering quality here is high. The five load-bearing safety invariants I was asked to
verify all hold, and several of them hold **twice** — once in the React layer and again
independently on the server, which is exactly the posture you want for anything that drives
geometry that becomes a physical print. The mm boundary in particular is airtight: the native
range input is kept entirely in spec mm, only the label and `aria-valuetext` convert, and even a
client that bypasses the UI cannot push a non-mm / non-finite / out-of-range value into the
geometry engine because the server re-coerces and re-clamps every value (`templates.py:53-61`,
`219-225`).

I found no Blocker and no Critical. The findings are two Minor correctness edges (a sub-0.1 mm
typed-precision swallow in mm mode, and typed values bypassing slider `step` granularity), one
Minor robustness gap (an unbounded per-content history length on a single turn vs. the per-turn
cap), and a small set of Nits. None of these block the slice.

**Verification performed:**
- Read every in-scope source file in full (App.tsx, RightPanel.tsx, ChatPanel.tsx, VersionRail.tsx,
  Workspace.tsx, useUnits.ts, api.ts, webapp.py) plus the provider message-assembly
  (`llm_provider.py:188-229`), the pipeline `run`/`rerender` signatures, and the template
  clamp/coerce path (`templates.py`).
- Ran `tests/test_webapp.py` → **63 passed**.
- Ran the frontend Vitest suite → **96 passed (9 files)**, including the Slice 3/4 mm-boundary and
  no-op-guard regression tests and the Slice 2 version-branching tests.

**Not checked (stated honestly):** real-hardware print path (out of altitude per the brief); the
live `gemma4:e4b` model call (not exercised in this audit — the model path is the same tested wiring
from earlier stages); the minified `web/assets` build output (reviewed source, not the bundle).

---

## Invariant verification

| # | Invariant | Verdict | Key evidence |
|---|-----------|---------|--------------|
| 1 | mm boundary — every value to onRerender/onChange is mm; native range stays in spec mm | **HOLDS** | RightPanel.tsx:87, 93, 160-172 |
| 2 | History sanitization — malformed turns rejected, server-side caps, context-not-instructions | **HOLDS** (one Minor) | webapp.py:151-167, 853; llm_provider.py:200-202 |
| 3 | Version-state integrity — branch truncates forward, no OOB, coherent restore | **HOLDS** | App.tsx:166-180, 224-241, 306-317 |
| 4 | Numeric edit — clampToSpec bounds every commit, NaN/empty reverts, no bad value to backend | **HOLDS** (two Minor) | RightPanel.tsx:24-27, 84-94; templates.py:53-61, 219-225 |
| 5 | Refine flow — history snapshot taken BEFORE the user turn is appended; double-submit guarded | **HOLDS** | App.tsx:213-220; ChatPanel.tsx:79-87, 149 |

Detail on each below in the findings and "What's working" sections.

---

## Findings

### ENG-001 — History per-turn content cap bounds chars, not the post-cap total; a 20×4000 history is ~80 KB of model context

- **Severity:** Minor
- **Category:** Security / Performance
- **Evidence:** `src/kimcad/webapp.py:50-51, 159-167`. `_sanitize_history` caps `MAX_HISTORY_TURNS = 20`
  turns and truncates each turn's `content` to `MAX_HISTORY_CONTENT = 4000` chars. The 1 MiB body
  cap (`MAX_BODY_BYTES`, webapp.py:670) already bounds the request itself. But the *sanitized* output
  can still be 20 × 4000 = 80 000 chars of conversation prepended to the model prompt on every refine
  turn, on top of the system prompt and schema. There is no cap on the aggregate sanitized size.
- **Why this matters:** This is not an injection or memory-exhaustion vector — the body cap and the
  per-turn cap both hold, and a single refine is one model call, not a fan-out. The cost is prompt
  bloat: a hostile or pathological client can reliably push ~80 KB of context into each
  `pipeline.run`, which on a CPU-bound local model (the stated deployment) is a latency tax, not a
  crash. It's a Minor because the exposure is a single-user loopback app and the worst case is a slow
  turn, not a downed feature.
- **Blast radius:** not required at Minor. Note for context: the same `_sanitize_history` output feeds
  both `generate_design_plan` and `generate_openscad` (llm_provider.py:201, 225), so any future
  aggregate cap lands in one place and covers both.
- **Fix path:** If you want a belt for the prompt budget, add an aggregate guard in `_sanitize_history`
  — e.g. stop appending turns once the running sum of `len(content)` exceeds a budget (say 16–24 KB),
  keeping the most-recent turns (the loop already iterates `raw[-MAX_HISTORY_TURNS:]`, so prefer
  newest). Optional; the current caps are defensible for the single-user target.

### ENG-002 — mm-mode no-op guard rounds to 1 dp, silently swallowing a typed sub-0.1 mm change

- **Severity:** Minor
- **Category:** Correctness
- **Evidence:** `src/kimcad/components/RightPanel.tsx:18-21, 69-71, 92`. In mm mode, `formatDisplay(mm)`
  returns `formatValue(mm, spec)`, which for a non-integer spec is `value.toFixed(1)` (one decimal).
  The commit no-op guard at line 92 is `if (formatDisplay(mm) === formatDisplay(value)) return`. So if
  the current value is `2.0` and the user types `2.04`, `clampToSpec(2.04)` keeps `2.04` (non-integer
  spec, no step snapping), but `formatDisplay(2.04)` = `"2.0"` === `formatDisplay(2.0)` = `"2.0"`, and
  the change is dropped — `onChange` never fires.
- **Why this matters:** A user typing a precise sub-0.1 mm value in mm mode (e.g. nudging a wall from
  2.0 to 2.04) sees nothing happen and no error. It is genuinely niche: the finest real spec step is
  0.2 mm (`templates.py:313` wall thickness) and most are 1.0 mm, and the *display* itself only shows
  1 dp, so the user can't see the difference they typed anyway. No bad value reaches the backend —
  this is a swallow, not a corruption — so it does not touch invariant 4's safety guarantee. It's a
  Minor papercut, not a defect that ships a wrong part.
- **Blast radius:** not required at Minor. Same root as ENG-003 (the typed-edit precision model).
- **Fix path:** If sub-0.1 mm mm-mode entry is intended to be honored, compare the no-op guard at the
  numeric precision the value is actually committed at rather than the 1-dp display string — e.g. guard
  on `Math.abs(mm - value) < epsilon` (epsilon ~ a fraction of `spec.step`) instead of string equality.
  The inch path already needs the rounded-string compare (the seed is 2-dp rounded), so keep that
  branch and split the mm branch to a numeric compare. Low priority.

### ENG-003 — Typed numeric input clamps min/max but does not snap to `step`; the slider does

- **Severity:** Minor
- **Category:** Correctness
- **Evidence:** `src/kimcad/components/RightPanel.tsx:24-27, 87`. `clampToSpec` clamps to `[min, max]`
  and rounds only when `spec.integer` is true. A non-integer dimension (`step: 1.0`, `integer: false`
  — the common case, `templates.py:304`) typed as `83.7` commits `83.7` and the part re-renders at
  83.7 mm. The native range input, by contrast, enforces `step` (RightPanel.tsx:168), so dragging only
  produces multiples of `step`. The two entry paths therefore have different granularity.
- **Why this matters:** This is mostly by design — the deterministic re-render accepts a continuous
  value and the gate re-validates the resulting geometry (`pipeline.rerender` → `match_family` →
  `clamp_values`, `templates.py:248`), and the server is the source of truth. So nothing unsafe ships:
  the backend independently clamps to range, and an 83.7 mm box is a perfectly buildable box. The only
  observable effect is that a typed value can sit "between steps" where a dragged value cannot, which is
  a mild inconsistency a careful user might notice. Minor, arguably intentional.
- **Blast radius:** not required at Minor. Shares the typed-edit root with ENG-002.
- **Fix path:** If step-snapping is desired for typed entry too, snap in `clampToSpec` after the range
  clamp: `Math.round((clamped - spec.min) / spec.step) * spec.step + spec.min`, guarded for
  `spec.step > 0`. Decide deliberately — some users *want* to type an exact off-step dimension, and the
  backend supports it. Leaving it as-is is a legitimate product choice.

### ENG-004 — `handleSwitchVersion` restores a snapshot's `result` (with its possibly-evicted `mesh_url`) without re-validation

- **Severity:** Minor
- **Category:** Correctness / Data provenance
- **Evidence:** `src/kimcad/App.tsx:232-241`. Switching versions does `applyResult(ver.result)`, where
  `ver.result.mesh_url` is the URL captured when that version was created. The server registry is an
  LRU capped at `MAX_REGISTRY = 50` (webapp.py:43, 878-880) and evicts the oldest design dirs
  (`_evict`, webapp.py:452-463). After enough new designs/renders in one session, an older version's
  `mesh_url` can 404.
- **Why this matters:** In practice this is hard to hit — 50 live designs in a single session before
  stepping back is a lot, and the `api.ts:195` comment already acknowledges "mesh_url still valid if
  server hasn't evicted." When it does happen, the viewport simply fails to load the mesh for that
  restored version; the right-panel data (plan, report, parameters) is all in the snapshot and renders
  fine, so the app degrades to a data-only view rather than crashing. No state corruption, no OOB
  index (the `if (!ver) return` guard at line 234 and the rail's `length >= 2` gate keep indices safe).
  Minor.
- **Blast radius:** not required at Minor.
- **Fix path:** Acceptable to leave. If you want graceful handling, have the viewport surface a small
  "this version's preview is no longer cached — refine or compare to regenerate" note when the mesh
  fetch 404s on a restored version, rather than a silent empty viewport.

### ENG-005 — `parseFloat` accepts trailing garbage in the numeric input (`"12abc"` → 12)

- **Severity:** Nit
- **Category:** Correctness
- **Evidence:** `src/kimcad/components/RightPanel.tsx:84, 99`. `parseFloat(draft)` parses a leading
  number and ignores the rest, so `"12abc"` yields `12` and commits. The `<input type="number">`
  (line 126) makes most browsers reject non-numeric keystrokes at the DOM level, so this is mostly
  unreachable through the UI; it's reachable via programmatic `fireEvent.change` (as the tests do) or
  paste in some browsers.
- **Why this matters:** Benign — the result is still clamped to range and finite, and the worst case is
  that `"12abc"` is read as a deliberate `12`. No safety impact. Flagging once as a Nit because
  `Number()` (which returns `NaN` for `"12abc"` and would then hit the existing NaN-revert at line 85)
  is stricter and arguably more correct for an exact-entry field.
- **Fix path:** Optional. Swap `parseFloat(draft)` for `Number(draft.trim())` if you want trailing
  garbage to revert rather than truncate; the existing `Number.isNaN` revert then catches it.

### ENG-006 — `getSnapshot` reads `localStorage` synchronously on every render via `useSyncExternalStore`

- **Severity:** Nit
- **Category:** Performance
- **Evidence:** `src/kimcad/useUnits.ts:21-27, 60`. `useSyncExternalStore(subscribe, getSnapshot, ...)`
  calls `getSnapshot` (a synchronous `localStorage.getItem` in a try/catch) on each render of every
  component using the hook (ParametersCard + PrintabilityCard + every SliderRow indirectly via the card).
- **Why this matters:** Effectively nothing. `localStorage.getItem` of a 2-char key is sub-microsecond,
  and the returned primitive is `Object.is`-stable so it causes no extra renders (the hook's own comment
  at lines 19-20 documents this deliberately). I note it only to confirm I traced the provenance and
  found it sound — the single-source-of-truth external store is the *right* call here (independent
  `useState` instances would drift, as the comment at lines 11-12 correctly argues). No action.
- **Fix path:** None recommended. This is the correct pattern.

---

## What's working

Specific, honest credit — this batch is well built.

- **The mm boundary is genuinely airtight, and defended in two layers.** On the client, `SliderRow`
  keeps the native `<input type=range>` entirely in spec mm — `min/max/step/value` are all the raw mm
  spec values, and `onChange` emits `Number(e.target.value)` (mm); only the visible label and
  `aria-valuetext` convert via `toDisplay` (RightPanel.tsx:160-172). The numeric-commit path runs
  `fromDisplay()` *before* `clampToSpec()` (line 87), so an inch entry becomes mm before it's bounded.
  On the server, `templates.py:_coerce_finite` (53-61) and `_clamp` (219-225) re-coerce every value to
  a finite number in range, so even a client that POSTs `{"width": "40in-as-a-string"}` or `inf` or a
  wild out-of-range number cannot reach `emit_scad`. This is exactly the right posture for values that
  become a physical print. The `FOUND-001` regression test (RightPanel.test.tsx) locks in the inch
  no-op guard so a focus+blur can't drift a dimension.

- **The history trust boundary is correct, and history is context, not instructions.** `_sanitize_history`
  (webapp.py:151-167) rejects non-list input, non-dict turns, and any role other than `user`/`assistant`,
  and truncates content per turn — so a client can never smuggle a `system` turn. In the provider
  (`llm_provider.py:200-202`, `224-225`), the system prompt is always position 0, history is inserted as
  prior conversation turns, and the current prompt is appended last. There is no path for client history
  to override the system prompt or the schema, and the plan output still goes through
  `parse_design_plan` schema validation. The sanitizer never raises and degrades to a standalone turn on
  garbage — a clean fail-open-to-safe design.

- **Version branching truncates forward history correctly — no zombies.** `runDesign` slices
  `prevVers.slice(0, fromVersionIdx + 1)` before appending the new version (App.tsx:169-177), so refining
  from an older version drops the abandoned forward versions and re-numbers contiguously. The
  index math can't go out of range (`if (!ver) return` guards, App.tsx:227, 234; the rail renders only at
  `length >= 2`, VersionRail.tsx:16), and `handleSwitchVersion` restores `{messages, result}` together and
  clears the in-flight save indicator (App.tsx:235-240) so a restored version doesn't inherit a stale
  "saving" state. The branch-after-switch-back case has a dedicated test.

- **The refine flow snapshots history at the right moment.** `handleRefine` calls `buildHistory()`
  *before* `setMessages((prev) => [...prev, userTurn])` (App.tsx:213-216). Because `buildHistory` closes
  over the pre-append `messages`, the model never sees the new prompt twice — it arrives once as the
  current user turn server-side. Double-submit is prevented by the `busy`/`canRefine` gating
  (ChatPanel.tsx:79-87, 149) and the disabled send button.

- **Compare can't crash on a missing side.** `App.handleCompare` guards `if (!a || !b) return`
  (App.tsx:226-228), the rail computes `compareA = max(0, length-2)` / `compareB = length-1` which are
  always valid at `length >= 2` (VersionRail.tsx:21-22), and `CompareCard` reads every field through
  optional chaining / nullish fallbacks (`a.result.plan?.summary ?? ...`, ChatPanel.tsx:22-27). A
  half-populated compare degrades gracefully.

- **The `useUnits` store design is the correct one.** Backing the preference with a module-level
  external store via `useSyncExternalStore` (rather than per-component `useState`) means toggling the
  unit re-renders the Parameters card and the Printability dims table in lockstep — the hook's own
  comment (useUnits.ts:11-12) names the exact drift bug this avoids, and it's right. The snapshot returns
  a stable primitive (no render loop), cross-tab `storage` events are handled, and `localStorage` access
  is wrapped so a storage-disabled context degrades to in-session mm. Clean.

- **Test coverage tracks the risk.** The batch adds focused tests where they matter: the mm boundary
  (inch entry emits mm, out-of-range inch clamps to the mm max), the no-op guard regression, version
  branching/truncation, history threading, and the full `useUnits` conversion round-trip. 63 webapp +
  96 frontend tests pass clean. This is the right places to spend test budget.

---

## Severity rollup (this role)

```
Blocker:  0
Critical: 0
Major:    0
Minor:    4   (ENG-001, ENG-002, ENG-003, ENG-004)
Nit:      2   (ENG-005, ENG-006)
-----
Total:    6
```

No invariant is violated. No finding blocks the slice. The Minors are papercuts and a deliberate-or-near
design choice (typed-edit precision/step), worth a quick decision but not a fix-before-merge gate.
