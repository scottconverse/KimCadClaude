# Test Engineer Deep-Dive — Stage 8.5 "Escape Paths"

**Auditor role:** Senior Test Engineer (balanced posture)
**Date:** 2026-06-04
**Repo:** `C:\Users\scott\dev\kimcad`
**Scope:** the escape-stage test diff `git diff 8618027..HEAD -- frontend/src` (commits `5118918`, `7fb2642` on top of `8618027`)
**Observed result:** `npm --prefix .../frontend run test` → **14 test files passed, 171 tests passed** (Duration ~6.5s, vitest 4.1.8). Re-confirmed green after every mutation was reverted.

---

## Test-suite shape (one sentence)

Bottom-heavy, behavior-oriented Vitest + Testing-Library suite: fast jsdom component/integration tests that drive the real components against a mocked `./api` (and a mocked `fetch`); the escapes are tested at the right altitude (mocks that honor `signal.abort`, not real OrcaSlicer/Ollama). No browser E2E layer — expected for this stage and explicitly out of altitude.

---

## Non-vacuity verdict: the cancel/seq guards are REAL (proven by mutation)

I did not trust the green. I mutated the product (reverted each fix in place) and re-ran. Results:

| # | Mutation (product change) | Expected catcher | Result |
|---|---|---|---|
| 1 | `handleCancelDesign()` body emptied (no `abort()`) — `App.tsx:262` | App "cancel aborts…" test | **CAUGHT** — `App.test.tsx:335` failed (busy never cleared, `getByLabelText` timed out). Escape-key test still passed → the two paths are independent. |
| 2 | Escape listener `if (e.key === 'Escape')` → `'EscapeXXX'` — `App.tsx` keydown effect | App "Escape key cancels…" test | **CAUGHT** — only `App.test.tsx:387` failed. Proves the keyboard path is verified in isolation. |
| 3 | seq guard removed on success path `if (seq !== designSeqRef.current) return` — `App.tsx:213` | App "drops a superseded design's late result" test | **CAUGHT** — `App.test.tsx:362` failed at `:383` (stale design A's mesh `/api/mesh/1` clobbered B's `/api/mesh/2`). |
| 4 | `isAbortError()` → always `false` — `api.ts:238` | api unit test + the 4 component cancel tests | **PARTIALLY CAUGHT** — `api.test.ts:84` failed AND `PhotoOnramp.test.tsx:129` failed. **ExportPanel, MyDesigns, and App cancel tests did NOT fail.** (See TEST-801/802.) |
| 5 | ExportPanel catch leaks the raw abort message (`setError(err.message)`, mirroring a real `isAbortError` miss) — `ExportPanel.tsx:89` | ExportPanel cancel test | **NOT CAUGHT** — `ExportPanel.test.tsx:64` still passed. The negative assertion only checks for the literal copy "slicing failed", not for *any* error. |

Mutations 1–3 are clean kills: the design-cancel, Escape-key, and seq-guard tests are genuinely non-vacuous — each fails the instant its guard is removed. Mutation 4/5 expose a real assertion-strength gap in three of the four component cancel tests (below). Working tree was returned to clean (`git diff --stat -- frontend/src` empty) and the full suite re-verified at 171/171.

---

## Findings

### TEST-801 (Major) — Three of the four "cancel returns clean" tests don't actually assert "no error" — they'd pass if a cancel surfaced an error banner
**Category:** Quality / Mocking (weak assertion)

**Evidence:**
- `ExportPanel.test.tsx:101` — the only post-cancel negative assertion is `expect(screen.queryByText(/slicing failed/i)).toBeNull()`. The real regression (an unrecognized abort) sets `error` to the raw thrown message `'aborted'`, **not** the string "Slicing failed", so the assertion passes anyway. Mutation 5 confirms it: leaking `err.message` on cancel keeps the test green.
- `MyDesigns.test.tsx:160–175` — the cancel test asserts **only** that the `Import` button reappears (`:175`). The comment at `:173` says "no error surfaced" but **there is no assertion for it.** The Import button reappears regardless, because `setImporting(false)` runs in `finally`. Mutation 4 (`isAbortError`→false) left this test green.
- `App.test.tsx:335` (first-design cancel) — asserts return-to-landing (`:358`) and `queryByTestId('busy')` null (`:359`); under a first design there is no prior `resultRef.current`, so even the correct code adds no thread message and the wrong code's `setError` doesn't move the user off the landing. The test can't distinguish a clean cancel from an errored one. Mutation 4 left it green.

**Why this matters:** the entire promise of the escape stage is "Cancel returns you to a *clean* pre-action state — no scary error from your own cancel." These three tests verify the user is un-stuck (button/affordance returns) but **not** that the cancel was silent. A future refactor that drops or inverts the `if (!isAbortError(err))` guard in `ExportPanel.tsx:89` or `MyDesigns.tsx` would ship an error banner on a normal Cancel and the suite would stay green. That is exactly the bug class this stage exists to prevent.

**Contrast (the one that's done right):** `PhotoOnramp.test.tsx:129` asserts all three — affordance returns (`:140`), the "Reading your photo…" text is gone (`:142`), and `onSeed` was not called (`:143`). It is the model the other three should copy, and it's the only component cancel test mutation 4 caught.

**Blast radius:**
- Adjacent code: same weak-assertion shape in `ExportPanel.test.tsx:64`, `MyDesigns.test.tsx:160`, `App.test.tsx:335`. Fix once per file.
- User-facing: a regression here shows an error toast/banner on a user-initiated Cancel — a trust hit, not a crash.
- Migration: none.
- Tests to update: add a strict "no error element" assertion to each. For ExportPanel assert `queryByText` against the actual error container (`.kc-export-error`) is null rather than a copy-specific regex; for MyDesigns add an assertion that the import error text is absent; for App assert the error-toned message is absent.
- Related findings: TEST-802 (shared root cause — `isAbortError` is the single classifier all four depend on, yet only two tests pin it).

**Fix path:** In each cancel test, after the control returns, assert the *absence of any error surface*, not the absence of one specific string. Recommended concrete add for ExportPanel: `expect(container.querySelector('.kc-export-error')).toBeNull()`. For MyDesigns: assert the component's error paragraph is not rendered. For App: `expect(screen.queryByTestId('msg-count')).toBeNull()` already implies landing, but add an explicit check that no error-toned assistant message exists once a refine-cancel variant is added (see TEST-803).

---

### TEST-802 (Minor) — `isAbortError`'s real-browser `DOMException` branch is never exercised
**Category:** Coverage

**Evidence:** `api.ts:238–240` classifies via `err instanceof DOMException ? err.name === 'AbortError' : (err as {name?})?.name === 'AbortError'`. Every test (unit `api.test.ts:83–88` and all four component cancel tests) throws a **plain `Error` with `name:'AbortError'`** — i.e. only the right-hand (`else`) branch is covered. A real aborted `fetch` in a browser throws a `DOMException` named `AbortError`, which takes the **left** branch. That branch has zero test coverage.

**Why this matters:** the production abort path is the `DOMException` one; the tests validate a hand-rolled stand-in. If the `instanceof DOMException` check were ever broken (e.g. a polyfill/SSR shim where `DOMException` is undefined), the suite wouldn't notice. Low exposure (the `else` branch would still catch a real DOMException by `.name`), hence Minor not Major.

**Fix path:** add one case to the `isAbortError` unit test (`api.test.ts:83`): `expect(isAbortError(new DOMException('x', 'AbortError'))).toBe(true)`. jsdom provides `DOMException`, so this runs as-is.

---

### TEST-803 (Minor) — The refine-cancel branch (cancel while a result already exists → "Cancelled — back to you." thread note) is untested
**Category:** Coverage

**Evidence:** `App.tsx:243–245` — on abort, `if (resultRef.current)` appends an assistant message `'Cancelled — back to you.'`. The only App cancel test (`App.test.tsx:335`) cancels a **first** design (no prior result), so `resultRef.current` is null and this branch never executes. There is no test that designs once, refines, then cancels the refine and asserts the "Cancelled — back to you." note appears (and that the prior version/result is preserved, not wiped).

**Why this matters:** cancelling a *refine* is a distinct, realistic flow (the user has a part, asks for a change, the model stalls, they back out). The intended UX — stay in the workspace, keep the current part, get a gentle note — is entirely unverified. A regression that wipes the workspace or drops the note on a refine-cancel would pass CI.

**Fix path:** add an App test: design → completes (mesh present) → refine → `postDesign` hangs on signal → Cancel → assert the part/version count is unchanged, `busy` is false, and a non-error assistant message containing "Cancelled" is present.

---

### TEST-804 (Minor) — The rich busy overlay + Cancel button + elapsed timer in `Viewport.tsx` have no rendering test (App.test mocks Workspace away)
**Category:** Coverage (Static-vs-runtime / mocking)

**Evidence:**
- `App.test.tsx:18–66` replaces `./components/Workspace` with a stub that renders a fake `cancel-design` button wired to `onCancelDesign` and `data-testid` spans for `busy`/`busy-elapsed`. The **real** Cancel button, the "Designing your part…" overlay, and the `fmtElapsed()` `m:ss` timer live in `Viewport.tsx:144–160` (added this stage) and are **never rendered by any test**.
- No `Viewport.test.tsx` and no `Workspace.test.tsx` exist (`find frontend/src -name "Viewport*.test.*" -o -name "Workspace*.test.*"` → none).
- `fmtElapsed()` (`Viewport.tsx`) — pure formatter (`0` → `0:00`, `65` → `1:05`, clamps negatives) — has no unit test.

**Why this matters:** App.test proves the *wiring* (clicking a button bound to `onCancelDesign` aborts), which is the load-bearing behavior — credit where due. But nothing verifies that the actual on-screen Cancel control exists, is labeled, fires `onCancelDesign`, or that the elapsed counter renders as `m:ss`. The classic static-vs-runtime gap: the handler is tested, the control the user clicks is not. A markup regression (Cancel button removed, mislabeled, or not wired) ships green. Severity is Minor because the wiring is covered and the `wiring-audit` lane is expected to drive the real DOM separately — but within the *unit* suite this is a genuine blind spot for a brand-new interactive control.

**Blast radius:**
- Adjacent code: `Viewport.tsx` busy overlay + `fmtElapsed`; `Workspace.tsx` only forwards props (`busyElapsed`, `onCancelDesign`) and is also untested.
- Tests to update: add a small `Viewport.test.tsx` (render `busy` + a stub `KCViewport` or accept the canvas mount) asserting the Cancel button renders, calls `onCancelDesign`, and the timer text matches `\d+:\d{2}`; plus a `fmtElapsed` unit table.
- Related findings: none code-side; pairs with the QA/wiring lane which should click the real button in a browser.

---

### TEST-805 (Nit) — `postSlice` signal-forwarding has no api-layer unit assertion, unlike `postDesign`/`uploadPhoto`/`importDesign`
**Category:** Coverage (consistency)

**Evidence:** `postDesign` (`api.test.ts:74`) and `uploadPhoto` (`api.test.ts:119`) each have an explicit "forwards the AbortSignal to fetch" unit test; `importDesign`'s is asserted via `MyDesigns.test.tsx:11` (`expect.any(AbortSignal)`). `postSlice` gained a `signal?` param (`api.ts:356`) but its existing unit test (`api.test.ts:300`) doesn't assert the signal reaches `fetch`. It **is** covered behaviorally end-to-end by `ExportPanel.test.tsx:64` (the hanging slice honors `init.signal.abort`), so this is consistency-only, not a real gap. Nit.

**Fix path:** mirror the `postDesign` signal test for `postSlice` (one assertion: `init.signal` is the passed signal).

---

## What's working (credit where due)

- **The design-cancel, Escape-key, and seq-guard guards are genuinely non-vacuous** — mutation 1/2/3 each produced a clean, single-test kill. The seq-guard test (`App.test.tsx:362`) is a particularly good piece of test design: it races design A (hangs) against design B (completes), resolves A *late*, and asserts B's mesh and version count are untouched (`:383–384`). That's the real concurrency hazard, tested at the real seam.
- **The Escape-key path is verified independently of the Cancel button** — mutating one leaves the other's test green. Two distinct escape affordances, two distinct tests. Good.
- **`PhotoOnramp.test.tsx:129` is the gold standard cancel test** — it asserts un-stuck + no-error + no-side-effect (`onSeed` not called), and it's the only component cancel test that catches the `isAbortError` mis-classification. The other three should be brought up to this bar.
- **api-layer signal forwarding is directly asserted** for `postDesign` and `uploadPhoto` (real `AbortController`, real `init.signal` identity check) — not just "it didn't throw."
- **`isAbortError` is pinned both ways** in the unit test (`api.test.ts:83`): true for an `AbortError`, false for a real failure *and* for `null`. That negative-and-null coverage is exactly right and is why mutation 4 was caught at the unit layer.
- **The updated `importDesign` assertion was tightened, not loosened** — `MyDesigns.test.tsx:11` moved from `toHaveBeenCalledWith(file)` to `toHaveBeenCalledWith(file, expect.any(AbortSignal))`, which *adds* a constraint (the second arg must be an `AbortSignal`). No vacuity introduced; the existing import flow still asserts `onOpen('imp9')`. Good regression hygiene.
- **No shortcuts found** — zero `.skip`/`.only`/`xit`/`it.todo`/`assert true`/commented-out assertions in the diff. No retry/flakiness config. Suite is deterministic and runs in ~6.5s.

---

## Coverage matrix (the 6 escape surfaces)

| Escape | Wiring tested? | Clean-return asserted strictly? | Notes |
|---|---|---|---|
| Design cancel (button) | Yes (`App.test:335`, mutation-proven) | Partial — un-stuck yes, no-error no | TEST-801 |
| Escape key | Yes (`App.test:387`, mutation-proven) | Un-stuck yes | Solid |
| Seq guard (superseded) | Yes (`App.test:362`, mutation-proven) | Yes — version count + mesh pinned | Strongest test |
| Photo read cancel | Yes (`PhotoOnramp:129`, mutation-proven) | **Yes — all three** | Gold standard |
| Slice cancel | Yes end-to-end (`ExportPanel:64`) | **No** — copy-specific only | TEST-801 |
| Import cancel | Yes end-to-end (`MyDesigns:160`) | **No** — no error assertion | TEST-801 |
| Refine-cancel branch | No | No | TEST-803 (untested branch) |
| Real Cancel UI / timer (Viewport) | No (mocked away) | No | TEST-804 |

Every one of the four escapes plus the Esc key plus the seq guard has *at least* wiring coverage — no escape is entirely untested. The gaps are assertion *strength* (TEST-801) and two specific *branches/render paths* (TEST-803/804), not missing escapes.

---

## Regression posture

No existing test was loosened to vacuity. The one changed assertion (`MyDesigns.test.tsx:11`) was tightened. The `postJson`→`signal?` threading and the `postDesign` rewrite to own-fetch did not break any caller: full suite 171/171 before and after, and the existing `postSlice`/`getOptions`/`uploadPhoto`/`importDesign` happy-path tests still pass unchanged. No test asserts a now-stale behavior.

---

## Summary for orchestrator

- **Finding counts:** Blocker 0 · Critical 0 · Major 1 · Minor 4 · Nit 1 (total 6)
- **Top findings:** TEST-801 (Major) — 3 of 4 component cancel tests assert "un-stuck" but not "no error," so an abort-misclassification regression ships green (proven by mutation 5); TEST-803/804 (Minor) — the refine-cancel thread-note branch and the real Viewport Cancel button + elapsed timer are untested (App mocks Workspace).
- **Blockers:** none.
- **Pattern/culture:** the suite is honest and bottom-heavy — the headline guards (design-cancel, Escape, seq-guard, photo-cancel) are mutation-verified non-vacuous, and `PhotoOnramp:129` shows the team *knows* how to write a strict cancel test. The systemic weakness is that the same rigor wasn't applied to the slice/import cancel tests, which check the user is un-stuck but not that the cancel was silent.
- **Observed pass count:** 171/171 (14 files). Restored to green after all 5 mutations reverted; working tree confirmed clean.
