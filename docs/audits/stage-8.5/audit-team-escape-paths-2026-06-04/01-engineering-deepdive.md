# 01 — Principal Engineer deep-dive: escape-paths stage

**Stage:** 8.5 usability — "escape-paths" (a Cancel/abort for every blocking UI action).
**Branch:** `stage-8.5-usability` @ `7fb2642`. **Scope diff:** `git diff 8618027..HEAD -- frontend/src`.
**Lens:** frontend correctness, async/state hazards, abort edge cases, leaks. Frontend-only (React/TS).
**Date:** 2026-06-04. **Reviewer:** Principal Engineer (audit-team).
**Build:** `npm run build` clean (tsc --noEmit + vite build, no errors). **Tests:** `vitest run` — **171 passed (14 files)** on clean HEAD.

---

## Verdict

The escape-paths change is **well-engineered and lands its core goal**: each of the four long-running, blocking actions (design, photo-read, slice, import) now aborts cleanly, classifies a cancel as a cancel (not a failure), guards against stale/superseded applies, and tears down its timers/listeners/controllers. The two prior audit-lite gates' fixes (ESC-MS1-001 seq-guard, -002 compound CSS selector, -003 quiet first-cancel; ESC-SWEEP-001 import unmount-abort, -002 slice-actions CSS) **all hold** in the committed code — re-verified line by line.

Two **real** findings sit outside the four primary flows, both rooted in the **restore-on-load path reusing the design-busy overlay without owning its inputs**: a garbage elapsed-timer value on a cold load to a saved-design URL (**Major**), and a dead Cancel/Escape during that restore (**Minor**). Neither is in the diff's headline four flows, but both are squarely in the stage's mandate ("no action traps the user / progress always honest").

### Harness note (must read)
During this audit the working tree was carrying **rotating seeded mutations** (markers literally tagged `/* MUTATION: ... */`) that cycled through `App.tsx` (`isAbortError`-guard removal, `handleCancelDesign` abort removal, `runDesign` seq-guard removal), `api.ts` (`isAbortError` → `return false`), and `ExportPanel.tsx`. Each, while present, turns the suite **RED** (e.g. seq-guard removal fails "drops a superseded design's late result"; abort removal fails the Cancel/Escape tests; `isAbortError→false` fails the cancel-classification tests across all four flows). This is a fault-injection harness, not the shipping code. **The audit below is against the committed HEAD blobs**, which I confirmed correct at every rotated site (`git show HEAD:...`) and which test **171/171 green**. The rotation also independently confirms the suite is **non-vacuous** — every load-bearing line has a test that dies without it. I restored `frontend/src` to clean HEAD before finishing.

---

## Severity rollup

- Blocker: 0
- Critical: 0
- Major: 1
- Minor: 2
- Nit: 1
- **Total: 4**

---

## Findings

### ENG-001 — Major — Correctness
**Stale-busy elapsed timer renders a garbage value (~28-million-minute "elapsed") on a cold load to a saved-design URL**

**Evidence:**
- `frontend/src/App.tsx:57` — `const busyStartRef = useRef<number>(0)` (initialized to `0`).
- `frontend/src/App.tsx:208` — `busyStartRef.current = Date.now()` is set **only** inside `runDesign`. (`grep busyStartRef` → 3 hits: decl @57, read @97, write @208; nowhere else.)
- `frontend/src/App.tsx:382` — the restore effect does `setBusy(true)` for `reopenDesign`, but never sets `busyStartRef.current`.
- `frontend/src/App.tsx:97` — the elapsed effect ticks `setDesignElapsed(Math.max(0, Math.round((Date.now() - busyStartRef.current) / 1000)))`.
- `frontend/src/components/Viewport.tsx:144-152` — whenever `busy` is true the overlay renders `{fmtElapsed(busyElapsed)} elapsed`, and `fmtElapsed` (Viewport.tsx:8-11) does `${Math.floor(s/60)}:${(s%60)...}`.

On a **fresh page load directly to `#/design/<id>`** (a bookmark, a shared link, or a plain refresh while viewing a saved design), the restore effect flips `busy=true` while `busyStartRef.current` is still its initial `0`. The timer then computes `(Date.now() - 0)/1000` ≈ 1.78 × 10⁹ seconds, and the "Designing your part…" overlay shows something like **`29708323:47 elapsed`** for the duration of the restore. (The overlay title "Designing your part…" is also wrong for a restore — it's reopening, not designing.)

**Why this matters:** This is a user-visible garbage string on a mainstream, non-edge flow — open a bookmarked saved design, share a link, or refresh the tab. It directly contradicts the stage's premise that progress is *always honest*. Visible window = however long `reopenDesign` takes (a large mesh on a cold disk read is exactly when it's longest, i.e. when the user is most likely to read the counter). No crash or data loss → Major, not Critical.

**Blast radius:**
- Adjacent code: the single `busy` flag now multiplexes two semantically different states (a design run vs. a restore). Any future overlay content keyed on `busy` inherits the same "whose start time?" ambiguity.
- Shared state: `busyStartRef`, `designElapsed`, the `busy` boolean — all read by Viewport's overlay and the elapsed effect.
- User-facing: the restore overlay (cold load / refresh / shared link to `#/design/<id>`).
- Migration: none.
- Tests to update: none catch this today — App.test.tsx's restore tests (`reopenDesign` mocked to resolve **synchronously**) never observe the busy window, so the stale timer is invisible to them. Add a test that holds `reopenDesign` pending and asserts the overlay's elapsed text is a sane small value (or absent).
- Related findings: ENG-002 (same restore-reuses-design-overlay root cause).

**Fix path:** Set `busyStartRef.current = Date.now()` in the restore effect right before `setBusy(true)` (App.tsx:382). Better, give the restore its own state so the overlay copy is correct too: either a separate `restoring` flag with a "Reopening your design…" overlay (no elapsed timer, no Cancel), or pass a `phase: 'designing' | 'restoring'` into Viewport so it picks the right title and suppresses the elapsed line during a restore. The minimal one-line fix (stamp `busyStartRef`) removes the garbage value; the phased fix also fixes the wrong title and ENG-002's dead Cancel in one move.

---

### ENG-002 — Minor — Correctness / UX
**Cancel button and Escape key are dead during a saved-design restore (a Cancel that does nothing)**

**Evidence:**
- `frontend/src/App.tsx:385` — `reopenDesign(route.id)` takes **no AbortSignal** (`api.ts:402` — `reopenDesign(id)` is a plain `getJson`, no signal param), and the restore effect never touches `designAbortRef`/`designSeqRef`.
- `frontend/src/App.tsx:262-264` — `handleCancelDesign` only does `designAbortRef.current?.abort()`; during a restore `designAbortRef.current` is null/stale, so Cancel is a no-op.
- `frontend/src/App.tsx:104-111` — the Escape listener (bound while `busy`) also only aborts `designAbortRef.current` → also a no-op during restore.
- `frontend/src/components/Viewport.tsx:153-159` — the overlay still renders a prominent **Cancel** button whenever `busy` is true, including during the restore.

So during a restore the user sees a "Designing your part…" overlay with a Cancel button and an Escape affordance that **do nothing to the reopen**. The reopen only aborts on a route change (`cancelled=true` in the effect cleanup, App.tsx:414), which Cancel doesn't trigger.

**Why this matters:** A dead primary action is precisely the "trap" this stage exists to remove — here on the restore path rather than the design path. Severity held to Minor because (a) the user is *not* fully trapped — `onWorkspace` is true during restore so the Topbar's New Design / Home still escape (App.tsx:425-433), and (b) `reopenDesign` is a local read, usually sub-second, so the window is short. But a visible-yet-inert Cancel undercuts trust in the very affordance the stage is selling.

**Blast radius:**
- Adjacent code: shares the `busy`-overlay reuse with ENG-001; a phased restore state fixes both.
- User-facing: restore window on cold load / refresh of a saved design.
- Migration: none.
- Tests to update: none cover Cancel-during-restore. Add one if the restore keeps a Cancel.
- Related findings: ENG-001.

**Fix path:** Tie the same fix as ENG-001. Either (preferred) give restore its own `restoring` state with a Cancel-less "Reopening…" overlay (a fast local read doesn't need a Cancel), **or** make `reopenDesign` accept a signal and have `handleCancelDesign`/Escape abort a restore controller too (then Cancel returns the user to wherever they came from). The first is less code and matches the honest framing (a restore isn't a minutes-long model run).

---

### ENG-003 — Minor — Hygiene / Robustness
**`handleSlice` / `handleImportFile` overwrite their abort ref without aborting the prior controller (unlike `runDesign` and `handleFile`, which abort-then-replace)**

**Evidence:**
- `frontend/src/components/ExportPanel.tsx:80-82` — `handleSlice` does `const controller = new AbortController(); sliceAbortRef.current = controller` with **no** `sliceAbortRef.current?.abort()` first.
- `frontend/src/components/MyDesigns.tsx:230-231` — `handleImportFile` likewise overwrites `importAbortRef.current` without aborting the prior.
- Contrast `frontend/src/App.tsx:205` (`designAbortRef.current?.abort()` before replacing) and `frontend/src/components/PhotoOnramp.tsx:77` (`readAbortRef.current?.abort() // supersede any prior read`).

**Why this matters:** Today this is **unreachable** — the Slice button is `disabled={!canSlice}` where `canSlice` includes `!slicing` (ExportPanel.tsx:72-77), and the Import button is `disabled={importing}` (MyDesigns.tsx:273), so a second invocation can't start while one is in flight. So it is **not a live bug** — it's a latent inconsistency: if a future refactor adds another trigger (e.g. drag-drop import, or a keyboard shortcut) that bypasses the disabled button, the overwrite would orphan the first controller (the in-flight request keeps running, its `finally`'s `=== controller` guard then no-ops, leaving the older request's success path able to apply). Minor and defensive only.

**Blast radius:**
- Adjacent code: the four abort-ref handlers; two abort-prior, two rely on the disabled button instead.
- User-facing: none today.
- Migration: none.
- Tests to update: none required.

**Fix path:** For parity and defense-in-depth, prepend `sliceAbortRef.current?.abort()` / `importAbortRef.current?.abort()` before assigning the new controller, matching `runDesign` and `handleFile`. One line each; makes the pattern uniform so a future second-trigger can't regress it.

---

### ENG-004 — Nit — Hygiene
**`reset()` runs in `handleFile`'s abort branch *and* the `finally` nulls the ref — fine, but the double `clearPreview` revoke is worth a one-line note**

**Evidence:** `frontend/src/components/PhotoOnramp.tsx:97-105` — on abort, the catch calls `reset()` (which calls `clearPreview()` → `URL.revokeObjectURL`), then `finally` nulls `readAbortRef`. Separately the `previewUrl` effect cleanup (PhotoOnramp.tsx:44-47) also revokes on the next change/unmount. Revoking an already-revoked object URL is a harmless no-op, so there's no leak and no double-free hazard — but the two revoke owners (the explicit `clearPreview` and the effect cleanup) are easy to lose track of.

**Why this matters:** Purely a maintainability nit; no runtime effect. Calling it out once so a future edit doesn't assume a single revoke owner.

**Fix path:** Optional — a one-line comment noting the effect-cleanup is the backstop revoke and `clearPreview` is the eager one. No code change needed.

---

## What's working

- **The cancel-vs-failure classification is correct and honest, end to end.** `isAbortError` (`api.ts:238-240`) handles both the `DOMException` abort and the duck-typed `{name:'AbortError'}` shape. `uploadPhoto` (`api.ts:323-326`) and `importDesign` (`api.ts:442-446`) **re-throw** the abort before their friendly "couldn't read/import" wrapper, so a cancel never masquerades as a read/import failure. Each consumer's catch (`PhotoOnramp.tsx:97-99`, `ExportPanel.tsx:88-90`, `MyDesigns.tsx:237-239`, `App.tsx:240-245`) treats `isAbortError` as a quiet return and only a real error surfaces a message. This is the load-bearing distinction and it's right.

- **No stale-apply on the design path.** `runDesign` stamps `const seq = ++designSeqRef.current` (App.tsx:203), aborts the prior controller (205), then re-checks `seq !== designSeqRef.current` after the await in **all three** of the success (213), catch (239), and finally (252) bodies. A superseded run (New Design / a new submit / our own abort-on-replace) drops its late resolve cleanly. `handleNewDesign` both bumps `designSeqRef` and aborts (App.tsx:370-372). Verified by the "drops a superseded design's late result" test (App.test.tsx:362-385), which is non-vacuous (it reddens when the guard is removed).

- **No stale-apply on the photo/slice/import paths.** Each awaits the call (which throws on abort, skipping the success body) and nulls its ref in `finally` under a `=== controller` guard (`PhotoOnramp.tsx:104`, `ExportPanel.tsx:92`, `MyDesigns.tsx:241`) so a later request's finally can't clobber a newer ref. `handleNewDesign` can't repopulate the reset slate — it supersedes (seq bump) + aborts before the reset, and the in-flight run's success path is seq-gated.

- **Clean teardown / no leaks.** The elapsed-timer interval is created only while `busy` and cleared on `!busy` and on unmount (App.tsx:92-101). The Escape keydown listener is added only while `busy` and removed in the effect cleanup — no double-bind, no leak (App.tsx:104-111). PhotoOnramp/ExportPanel/MyDesigns each abort their in-flight request on unmount (`PhotoOnramp.tsx:73`, `ExportPanel.tsx:102`, `MyDesigns.tsx:253`) — ESC-SWEEP-001's missing import unmount-abort is fixed and present. PhotoOnramp revokes its preview object URL on change/unmount (PhotoOnramp.tsx:44-47).

- **Pointer-events is order-independent (ESC-MS1-002 fixed).** Base `.kc-viewport-overlay { pointer-events: none }` (styles.css:554) is overridden by the **compound** `.kc-viewport-overlay.kc-viewport-busy { pointer-events: auto }` (styles.css:567-571). Specificity 0,2,0 beats 0,1,0 regardless of source order, so a CSS reorder can't silently re-trap the user. The overlay element carries both classes (Viewport.tsx:145). No later rule re-disables it (grep confirms only these two `pointer-events` rules touch the overlay). The Cancel also has a `:focus-visible` outline and a 44px coarse-pointer min-height (styles.css) — keyboard- and touch-reachable.

- **Honest, well-scoped copy.** The overlay states the work runs locally and can take minutes and nothing leaves the machine (Viewport.tsx:148-151); the experimental offer now warns about the time + the cancel option before the user commits (ChatPanel.tsx). Nothing claims the *server-side* model work is killed — the framing is "the UI wait is released; the local job may finish in the background," which is the truthful description of a client abort.

- **Tests are thorough and non-vacuous.** Cancel + Escape + superseded-design (App.test.tsx:334-405), signal-forwarding for `postDesign`/`uploadPhoto` + `isAbortError` true/false/null (api.test.ts), and per-component cancel-returns-to-control-with-no-error for slice/import/photo (ExportPanel/MyDesigns/PhotoOnramp .test.tsx). Each makes the mocked request reject on `signal.abort` and asserts the pre-action control returns with no error surfaced. The seeded-mutation rotation independently proved every one of these dies when its target line is broken.

---

## Scope items verified sound (not flagged)

Per the audit brief, these are documented decisions; I confirmed each is a defensible call, not a gap:

- **Save (`postSettings`) gets no Cancel** — it's a non-blocking commit; the Settings screen stays interactive, so there is no trap to escape. Correct.
- **Model-pull has no in-app cancelable action** — it's an external "pull in Ollama, then re-check" with no in-band request to abort. Correct.
- **A global request timeout is deferred** to its own slice — the per-action Cancels already remove every interactive trap; a timeout is a belt-and-suspenders backstop, honestly scoped. Reasonable.
- **No true server-side cancel of OrcaSlicer/Ollama** — client-abort releases the UI; the local job may finish in the background. This is stated honestly in the copy and comments and is the correct, non-overclaiming framing.

## What I could not check

- **No live browser run this pass** — this is the static engineering lens (the running model-free demo at `127.0.0.1:8768` exists; the live wiring sweep is the QA/wiring-audit role's job). ENG-001/ENG-002 are derived from the code and are reproducible by loading `#/design/<id>` cold; a live confirmation by the QA role would close them definitively.
- **Working-tree state was unstable** during the audit due to the seeded-mutation harness (above). All findings and the build/test results are taken against the **committed HEAD** code, which I restored before finishing.
