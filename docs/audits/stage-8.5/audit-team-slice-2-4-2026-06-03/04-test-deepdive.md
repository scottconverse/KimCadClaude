# Test Engineer deep-dive — KimCad Stage 8.5 Slices 2–4

**Scope:** `git diff d56b251..HEAD` (branch `stage-8.5-usability`, HEAD `2ea65e9`), excluding `docs/audits` and `src/kimcad/web/assets`.
**Date:** 2026-06-03
**Reviewer posture:** balanced; coverage-reality vs. claim.

---

## Test counts I actually ran

| Suite | Command | Result observed |
|---|---|---|
| Frontend (full) | `npm --prefix .../frontend run test` | **9 files, 96 passed** (3.86s) |
| Frontend (in-scope files only) | `npx vitest run App.test.tsx RightPanel.test.tsx useUnits.test.ts` | **3 files, 53 passed** |
| Backend (full webapp) | `python -m pytest tests/test_webapp.py -q` | **63 passed** (29.94s) |
| Backend (history tests only) | `pytest -k "sanitize or threads_sanitized"` | **2 passed**, 61 deselected |

Claimed "96 passed" is **confirmed exactly**. The Slice 2–4 frontend work contributes 53 of the 96; the backend `_sanitize_history` work contributes 2 of the 63 webapp tests. All suites are green, deterministic on this run, and finish fast. No `.skip` / `.only` / `xit` / `it.todo` / `assert True` anywhere in the frontend test tree.

---

## Test-suite shape (one-liner)

Heavy, well-targeted **component + hook unit tests** (RightPanel, useUnits) and **App-level state-machine tests** (App.test.tsx) with a fully **mocked Workspace** and **mocked api**; backend is **real-HTTP-over-ephemeral-port integration** plus pure-function unit tests. No E2E / rendered-browser layer in this batch (handled by the separate wiring-audit lane). The Slice 2–4 numeric/unit tests are genuinely non-vacuous — they pin real mm-vs-inch failure modes, not truthy artifacts. The gap is **two brand-new/heavily-changed UI components (VersionRail, ChatPanel) that no test ever renders**, because the only component that mounts them (Workspace) is stubbed out.

---

## What's working (credit where due)

- **The mm-boundary tests are real, not vacuous.** `RightPanel.test.tsx:470` enters `4` in inch mode and asserts the emitted value is `closeTo(101.6, 5)` — proving the backend receives **mm (4×25.4), not the raw 4**. `:489` enters `40` in and asserts the emit is exactly `200` (the mm spec max), proving the **clamp happens in mm space**, not 1016 or 40. These would catch a unit-conversion regression cold.
- **The no-op guard (FOUND-001) is pinned on both sides.** `:516` commits the unchanged 2-dp inch seed (`3.15`) and asserts `onRerender` is **not** called (no drift to 80.01 mm, no wasted re-render); `:533` commits a real change (`3.5` in → `closeTo(88.9)` mm) and asserts it **does** fire once. Both branches of the guard at `RightPanel.tsx:92` are exercised. This is exactly the tests-with-fixes culture the severity framework rewards.
- **App-level version state-machine is well covered.** Branching/truncation (`App.test.tsx:270` — refine after switch-back drops forward versions, stays at 2), switch-restore (`:210` — mesh_url + msg-count revert), version push per design (`:194`), compareCard set (`:292`), history threaded into the second `postDesign` call (`:248`), stale out-of-order re-render discard (`:105`), and reopen-without-re-save (`:140`) are all asserted on observable state, not internals.
- **`useUnits` hook is thoroughly unit-tested** including the mm→display→mm round-trip within 0.01 mm (`useUnits.test.ts:58`) and the 2-dp inch formatting (`:73`) — the conversion math itself is solid.
- **Backend `_sanitize_history` caps are directly unit-tested** (`test_webapp.py:1635`): bad-role drop, non-str-content drop, non-dict drop, order preservation, 20-turn cap keeping the most recent, and the 4000-char per-turn truncation are each asserted on the real function. The HTTP-path test (`:1659`) proves sanitized history reaches `generate_design_plan` and that a non-list / missing history degrades to `None` (never a 400/500). The bound-before-pipeline is covered transitively (the handler at `webapp.py:853` calls the unit-tested `_sanitize_history` before `design_response`).
- **localStorage hygiene between tests** is handled (`RightPanel.test.tsx:14`, `beforeEach` at `:424`) so the persisted inch preference can't leak into mm-assuming tests — a real flakiness source that was anticipated.

---

## Findings

### TEST-001 (Major) — Coverage — VersionRail component has zero rendered-component coverage

**Evidence:** No `VersionRail.test.tsx` exists (`Glob frontend/src/components/VersionRail*` → no files). `VersionRail.tsx` is **brand new this batch** (78 lines, added in commit `6a8387a`). The only test touching version UI is `App.test.tsx`, which **mocks `./components/Workspace`** wholesale (`App.test.tsx:17-57`) and replaces VersionRail with stub buttons that call `onSwitchVersion(0)` / `onCompare(0, 1)` with hard-coded indices. The real component's own logic is never executed:
- `if (versions.length < 2) return null` (`VersionRail.tsx:17`) — the **hidden-until-2-versions** guard is untested.
- `disabled={!canUndo}` where `canUndo = versionIdx > 0` (`:18`, `:50`) — the **Undo disabled-at-v1 bound** is untested.
- `{canRedo && (...)}` where `canRedo = versionIdx < versions.length - 1` (`:19`, `:55`) — the **Redo-hidden-at-latest** branch is untested.
- `compareA = Math.max(0, versions.length - 2)`, `compareB = versions.length - 1` (`:21-22`) — the **default compare-pair computation** is untested. App.test.tsx's `do-compare` passes `(0,1)` literally, so this math never runs.
- `aria-current` / `aria-label` on the pills (`:36-37`) — untested.

**Why this matters:** Undo/Redo bounds are a classic off-by-one bug class (Redo visible when already at the latest version; Undo enabled at v1 stepping to index -1). A regression that, say, flipped `canUndo` to `versionIdx >= 0` would let a user "undo" off the front of the array — the whole suite would stay green. The owner's standing rule is that a new feature without a real regression test isn't done; VersionRail is a new feature with no direct test.

**Blast radius:**
- Adjacent code: `App.handleSwitchVersion` (`App.tsx:232`) and `handleCompare` (`:224`) consume these indices; a bad index from VersionRail is silently swallowed by their `if (!ver) return` guard, so a bounds bug would manifest as a no-op button, not a crash — harder to notice without a test.
- User-facing: every multi-version session (the core Slice 2 flow) renders this rail.
- Tests to update: none break; this is additive.
- Related findings: TEST-002 (same root cause — mocked Workspace).

**Fix path:** Add `VersionRail.test.tsx` that renders the real component with 1 / 2 / 3 versions and `versionIdx` at the ends and middle. Assert: hidden at <2; Undo disabled iff `versionIdx===0`; Redo absent iff at the last index; `onCompare` called with `(length-2, length-1)` on the Compare click; `aria-current` on the active pill.

---

### TEST-002 (Major) — Coverage — ChatPanel (incl. CompareCard) has zero rendered-component coverage

**Evidence:** No `ChatPanel.test.tsx` exists. `ChatPanel.tsx` grew by 156 lines this batch (refine input + CompareCard + thread rendering, commits `295e653` / `2112d72`). Like VersionRail it is only reachable through the **mocked** Workspace, so none of this executes under test:
- `CompareCard` (`ChatPanel.tsx:20-50`) — renders the two-column v_a→v_b diff with gate badges and readiness scores. The `App.test.tsx:292` test only asserts `compareCard ? 'yes' : 'no'` on the **stub**; the real card's column content, the `scoreA != null` conditional (`:26`,`:44`), and the `v${a.index} → v${b.index}` header are untested.
- Refine-input gating: `canRefine = hasResult && !busy` (`:80`) controls whether the textarea renders at all — untested.
- The clarification-vs-refine **placeholder swap** (`:157-161`, keyed on `result?.status === 'clarification_needed'`) — untested.
- Enter-to-submit / Shift+Enter-newline (`:89-94`) and the empty-draft disabled Send (`:169`) — untested.
- The top-level-error de-dupe `messages.every(m => m.content !== error)` (`:140`) — untested.

**Why this matters:** The CompareCard is a Slice 2 headline feature (the whole point of "version compare"). A regression that swapped `scoreA`/`scoreB` columns, or that showed the refine box during a clarification when it should change copy, would ship green. The Enter/Shift+Enter handler is a common keyboard-UX bug surface (Enter inserting a newline instead of submitting).

**Blast radius:**
- Adjacent code: `App.handleRefine` (`App.tsx:212`) depends on the refine input firing `onRefine`; if the input is gated off by a `canRefine` regression, the entire refine flow dies silently.
- User-facing: every refine turn and every compare action passes through this component.
- Tests to update: none break; additive.
- Related findings: TEST-001 (shared root: Workspace mock erases both children).

**Fix path:** Add `ChatPanel.test.tsx`: render with a `compareCard` prop and assert both versions' summaries/gates/scores appear and are in the right columns; render with `busy=true` and assert the refine box is hidden; render with `result.status==='clarification_needed'` and assert the "Answer the question above…" placeholder; fire Enter and assert `onRefine`, fire Shift+Enter and assert it does **not** submit.

---

### TEST-003 (Major) — Coverage — Cross-card unit sync is asserted per-card, never as one toggle driving both cards

**Evidence:** The entire reason `useUnits` is backed by a module-level `useSyncExternalStore` rather than per-component `useState` is documented at `useUnits.ts:8-13`: *"toggling the unit in the Parameters card must instantly re-render the Printability dims table too. With independent useState instances they would drift until a remount — a real bug this design avoids."* That cross-component guarantee is **not** asserted end-to-end. The two tests that touch unit conversion use mutually exclusive fixtures:
- `RightPanel.test.tsx:447` (dims table → inches) renders `passResult`, which has `dims` but **no `parameters`** (so no sliders render).
- `RightPanel.test.tsx:458` (slider → inches) renders `templateResult`, whose `report.dims` is `[]` (`:78`) — so **no dims table renders**.

No single test renders a result carrying **both** sliders and a dims table, clicks the `in` toggle **once**, and asserts that **both** the ParametersCard slider readout **and** the PrintabilityCard dims cells convert. The hook's store mechanism is unit-tested in isolation (`useUnits.test.ts`), but the integration claim — two separate `useUnits()` consumers (`ParametersCard` at `RightPanel.tsx:191`, `PrintabilityCard` at `:446`) both re-render off one `setUnit` — has no test.

**Why this matters:** This is precisely the "Static ≠ Runtime / Mocks lie" trap. If someone "simplified" `useUnits` back to `useState` (a plausible future refactor that would look harmless), every existing test would still pass — because each card is tested alone — yet the actual product bug the design was built to prevent (Parameters shows inches, Printability still shows mm until remount) would return undetected. The test that would catch it does not exist.

**Blast radius:**
- Adjacent code: `setUnitPref` (`useUnits.ts:50`) and its listener set; any third future `useUnits()` consumer inherits the same untested assumption.
- Shared state: `localStorage['kc-units']` and the module-level `listeners` Set — global, single source of truth.
- User-facing: any design that is template-backed (has sliders) AND has a dims table — the common template path.
- Tests to update: none break; additive.

**Fix path:** Add one `RightPanel` test rendering a `templateResult` whose `report.dims` is **non-empty** (e.g. a width slider plus an `{axis:'X', target:80, actual:80}` dim). Click `in` exactly once. Assert in the same render pass: the slider value button reads `3.15 in` **and** the dims cells read `3.15`. That single test pins the cross-card store contract.

---

### TEST-004 (Minor) — Coverage — NaN / empty / non-numeric numeric-edit commit is untested

**Evidence:** `commitEdit` (`RightPanel.tsx:81-94`) has a distinct early-return branch: `const rawDisplay = parseFloat(draft); if (Number.isNaN(rawDisplay)) return`. The tests cover Enter-commit (`:373`), clamp-over-max (`:387`), and Escape-cancel (`:402`), but **no test commits an empty string or non-numeric value** (e.g. `fireEvent.change(numInput, {target:{value:''}})` then Enter). The task brief explicitly calls out "NaN/empty revert" as a behavior to scrutinize; it is not pinned.

**Why this matters:** A user who clears the field and presses Enter (or blurs) hits this path. The current code silently drops the edit and closes the editor — correct — but a regression that let `parseFloat('')` (→ NaN) slip through to `clampToSpec`/`onChange` would emit `NaN` to the backend (which `clampToSpec`'s `Math.max(min, Math.min(max, NaN))` returns as `NaN`), producing a broken re-render. The boundary is exactly the kind the framework flags as "happy path only — token coverage of empty/edge."

**Fix path:** Add a test: open the editor, `change` to `''` (and separately to `'abc'`), press Enter, assert `onRerender` was **not** called and the value button is restored to its prior reading. Low effort, closes a real edge.

---

### TEST-005 (Minor) — Coverage — Integer-parameter branches (round-on-clamp, integer formatting) are untested

**Evidence:** Every param in `RightPanel.test.tsx` is built via the `param()` helper, which defaults `integer: false` (`:68`), and **no test overrides it to `true`**. Two integer-specific branches therefore never execute under test:
- `formatValue` (`RightPanel.tsx:20`): `if (spec.integer) return String(Math.round(value))`.
- `clampToSpec` (`:26`): `return spec.integer ? Math.round(clamped) : clamped`.

**Why this matters:** Integer params are a real spec type (hole counts, fin counts, teeth). Committing `4.5` to an integer slider should round to `5` (or `4`) and emit an integer; an inch-mode integer edit is even more exposed (3.15 in → 80.01 mm, which for an integer param must round). A regression dropping the `Math.round` would emit fractional values to a parameter the template treats as a count.

**Fix path:** Add a slider test with `param({ integer: true, ... })`: commit a fractional value and assert the emitted value is the rounded integer; assert the display formats without a decimal.

---

### TEST-006 (Nit) — Quality — Redundant `.toBeTruthy()` on throwing queries

**Evidence:** ~30 assertions of the form `expect(screen.getByText(/.../)).toBeTruthy()` (e.g. `RightPanel.test.tsx:118-120`). `getByText`/`getByRole` already throw when the element is absent, so the query *is* the assertion and `.toBeTruthy()` adds nothing.

**Why this matters:** Purely cosmetic — these tests are not vacuous (the query enforces presence). Flagging once per the framework's "flag once, don't belabor." Prefer `screen.getByText(...)` as a bare statement or `toBeInTheDocument()` for intent clarity. No action required for the gate.

---

## Coverage-hole summary (in-scope Slice 2–4 behaviors)

| Behavior | Tested? | Finding |
|---|---|---|
| inch edit commits mm (4 in → 101.6 mm) | ✅ real | — |
| inch clamp (40 in → 200 mm max) | ✅ real | — |
| no-op guard suppresses unchanged inch commit | ✅ real (both sides) | — |
| numeric clamp (mm, over-max) | ✅ | — |
| Escape cancels numeric edit | ✅ | — |
| NaN / empty numeric commit reverts | ❌ | TEST-004 |
| integer-param round-on-clamp / formatting | ❌ | TEST-005 |
| cross-card unit sync (one toggle → both cards) | ❌ (per-card only) | TEST-003 |
| version branching / truncation | ✅ (App-level) | — |
| switch-restore (messages + result) | ✅ (App-level) | — |
| undo/redo **bounds** + disabled states | ❌ (App state ok; VersionRail UI not) | TEST-001 |
| compare default-pair computation | ❌ | TEST-001 |
| CompareCard rendered content | ❌ | TEST-002 |
| refine-input gating / placeholder swap / Enter-submit | ❌ | TEST-002 |
| history sanitize: 20-turn cap, 4000-char cap, malformed drop | ✅ (unit) | — |
| history bound-before-pipeline | ✅ (transitive via handler→unit-tested fn) | — |

---

## Bottom line

The **new numeric/unit logic is genuinely well-tested** — the mm-boundary and no-op-guard tests are model regression pins, not truthy theater, and they pass. The systemic gap is that **two new/heavily-changed Slice 2 UI components (VersionRail, ChatPanel) are never rendered by any test** because the component that mounts them is mocked, so their own branching (undo/redo bounds, compare-pair math, compare-card columns, refine gating) is invisible to the suite. Combined with the **un-asserted cross-card unit-sync contract** (the single most load-bearing reason `useUnits` exists), these are three Major coverage holes a refactor could silently reintroduce a real bug through.
