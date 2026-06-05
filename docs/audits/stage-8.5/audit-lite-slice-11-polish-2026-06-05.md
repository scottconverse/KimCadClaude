# Audit Lite — Stage 8.5 Slice 11 (responsive / a11y / copy / polish)
**Date:** 2026-06-05
**Scope:** The staged change on `stage-8.5-usability`: a keyboard-shortcuts system + accessible help overlay (`ShortcutsHelp.tsx`, global keydown effect in `App.tsx`), a `humanizeObjectType()` copy util wired into RightPanel + MyDesigns, softened "parametric template" jargon copy, and modal/`kbd` CSS. Generated build artifacts (`src/kimcad/web/assets/*`) and the tracking doc (`docs/audits/RUN-LEDGER-2026-06-05.md`) are out of scope per instruction.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-caveats. The slice is small, well-commented, and genuinely accessible — the copy util is correct and the modal nails the role/aria-modal/focus/Escape/backdrop pattern. But there is one real interaction bug: while a design is running, opening the shortcuts help and pressing Escape to dismiss it **also silently cancels the in-flight design**, because the design-cancel Esc listener doesn't honor `defaultPrevented`. That, plus a focus-trap that is structurally under-exercised by its test and a missing focus-restore-on-close, are the things to fix before the stage gate. No Blocker, no security exposure, no data loss.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 3
- Minor: 2
- Nit: 2

## Findings

### FINDING-001 Major: Esc that only means "close the help" also aborts a running design
**Dimension:** Correctness / UX
**Evidence:**
- `frontend/src/App.tsx:172-180` — the design-cancel effect listens on `window` and aborts on `Escape` whenever `busy`, with **no `e.defaultPrevented` guard**:
  ```
  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape') designAbortRef.current?.abort()
  }
  ```
- `frontend/src/components/ShortcutsHelp.tsx:18-24` — the dialog's own `document` Esc listener calls `onClose()` and `e.preventDefault()` but does **not** stop propagation.
- `frontend/src/App.tsx:198-201` — `?` toggles the help with no `busy` guard, so the help can be opened mid-design.
- Trace: design running (`busy=true`) → user presses `?` → help opens → user presses `Esc` to dismiss it. ShortcutsHelp's listener fires `onClose` + `preventDefault`. App's *shortcuts* effect (`App.tsx:185-221`) correctly bails on `e.defaultPrevented` (line 187). App's *design-cancel* effect (line 175) does not check `defaultPrevented`, so it aborts the design. Net: one Esc closes the help **and** kills the in-progress design the user didn't intend to cancel.
**Why it matters:** A design run is the app's single most expensive user operation (LLM + render, "ready in under 15 minutes" per the wizard copy). Losing it to a keystroke the user believed only closed a help overlay is a real, surprising data/work loss. It also contradicts the slice's stated intent that the two Esc behaviors are cleanly separated ("design-cancel Esc is above", `App.tsx:184`).
**Fix path:** Make the design-cancel effect honor intent — add `if (e.defaultPrevented) return` at `App.tsx:176` (so any modal that handled Esc suppresses the cancel), and/or guard it with `if (showShortcuts) return`. Either makes the help's Esc win without touching the design. Add an App-level test: busy + help open, press Esc → help closes, `designAbortRef.abort` NOT called.
**Blast radius:**
- Adjacent code: any future modal that relies on Esc while `busy` (InfoTip already binds a document Esc at `InfoTip.tsx:25-26` — same `defaultPrevented`-blind pattern, but InfoTip doesn't preventDefault so it doesn't currently collide; worth the same guard for consistency).
- Shared state: `designAbortRef` / `busy`. No persisted state.
- User-facing change: after fix, Esc-with-help-open no longer cancels a run; Esc-with-no-modal still cancels (unchanged).
- Migration concern: none.
- Tests to update: add the busy+help+Esc case to `App.test.tsx`; the existing MS-1 design-cancel Esc tests should still pass unchanged.

### FINDING-002 Major: Focus is not restored to the trigger when the shortcuts dialog closes
**Dimension:** UX (accessibility)
**Evidence:** `frontend/src/components/ShortcutsHelp.tsx:14-39` — the effect focuses `closeRef` on mount but the cleanup only removes the keydown listener; nothing captures the previously-focused element or restores it on unmount. Compare the dialog's deliberate focus-*in* (line 15) — the focus-*out* half of the contract is absent. (The task brief flagged this as "may be missing — check and judge severity." Confirmed missing.)
**Why it matters:** WAI-ARIA dialog practice requires returning focus to the element that invoked the dialog on close. Because `?` can be pressed with focus anywhere (e.g. on the canvas/body), after close a keyboard or screen-reader user is dumped to document start / lost focus context. It's a standards-level a11y regression for a slice whose whole job is a11y polish.
**Fix path:** On mount, capture `const prev = document.activeElement as HTMLElement | null`; in the effect cleanup, `prev?.focus?.()`. Add a test: render in a host with a focused button, unmount, assert focus returned. (Modest caveat: when `?` is pressed from `document.body` there is no meaningful trigger to restore to — restoring to `body` is acceptable and still better than leaving focus on a detached node.)

### FINDING-003 Major: The focus-trap test is a tautology — it never exercises a real wrap
**Dimension:** Tests
**Evidence:**
- `frontend/src/components/ShortcutsHelp.test.tsx:46-53` — the "traps Tab focus" test focuses `focusable[last]`, fires Tab, asserts focus is `focusable[0]`. But the dialog renders exactly **one** focusable element (the Close button — `ShortcutsHelp.tsx:75-77`; the `<kbd>` items are non-focusable). So `first === last === the only button`, and "wraps to first" is trivially true no matter what the handler does.
- The trap handler (`ShortcutsHelp.tsx:33-37`) has three real branches: `shiftKey && (active===first||active===root)`, `!shiftKey && active===last`, and the implicit "let it through". **None of the Shift+Tab branch, nor the `active===root` branch, is tested.** A regression that broke Shift+Tab or reverse-wrap would pass this suite green.
**Why it matters:** Per the skill's hard guardrail, a behavior without a test is at least Major. The focus-trap is asserted as a feature ("wraps both directions", per the brief) but only the degenerate single-element forward case is covered. The trap is *correct* on read, but it is effectively unverified.
**Fix path:** Either (a) test the trap against a fixture with ≥2 focusable elements covering forward-wrap, Shift+Tab reverse-wrap, and the `active===root` (focus on the dialog container) case; or (b) since the production dialog only ever has one focusable control, simplify the handler to the single-element case and document that, then test Tab + Shift+Tab both keep focus on Close. Option (b) is the smaller, more honest change given the real DOM.

### FINDING-004 Minor: Modifier-guard test only covers Ctrl, not Meta/Alt; typing-guard only covers the prompt input
**Dimension:** Tests
**Evidence:** `frontend/src/App.test.tsx:548-552` asserts `ctrlKey: true` is ignored, but the guard at `App.tsx:187` also covers `metaKey` (Cmd, the primary Mac modifier) and `altKey` — neither is tested. The typing-guard test (`App.test.tsx:534-538`) fires `?` on the prompt `<input>` only; the guard also covers `TEXTAREA`, `SELECT`, and `contentEditable` (`App.tsx:190-196`), none exercised.
**Why it matters:** The guards are the load-bearing safety of a global bare-key listener (don't hijack OS combos, don't fire mid-typing). Coverage gaps here are exactly where a future refactor silently regresses a Mac user's Cmd+N or a shortcut firing inside a textarea.
**Fix path:** Parametrize the modifier test over `{ctrlKey},{metaKey},{altKey}`; add one typing-guard assertion firing a bare key on a `<textarea>` or `contentEditable` host. Cheap, high-value.

### FINDING-005 Minor: `?` while an InfoTip is open opens the help on top of the tip without closing it
**Dimension:** UX
**Evidence:** `frontend/src/components/InfoTip.tsx:25-26` closes the tip on Esc but not on other keys; the InfoTip trigger is a `<button>` (`InfoTip.tsx:41-50`), which is not in the App typing-guard's tag list, so pressing `?` while that button holds focus passes the guard and opens the shortcuts modal. The InfoTip's role="note" panel stays open underneath.
**Why it matters:** Minor visual/stacking oddity (tip note left dangling behind/around the modal). Not a trap — Esc closes the modal, and the modal sits at z-index 200 so it's clearly on top. Low frequency, easy recovery.
**Fix path:** Optional. If desired, have opening the shortcuts help also dismiss transient popovers, or leave as-is (acceptable for a help overlay). Flagging for completeness, not urgency.

### FINDING-006 Nit: Two overlays share `z-index: 200` — latent layering fragility (currently unreachable)
**Dimension:** UX
**Evidence:** `.kc-modal-backdrop` (`frontend/src/styles.css:1778`) and `.kc-wiz-overlay` (`styles.css:3000`) both set `z-index: 200`. The shortcuts effect guards `if (showWizard) return` (`App.tsx:197`), and `?` is the only opener, so the help cannot be opened while the wizard is up — the two never co-render today. But if a future change opens the help programmatically, equal z-index makes stacking order depend on DOM order (`App.tsx:565-566` renders wizard first, then shortcuts, so shortcuts would win — by accident, not intent).
**Why it matters:** No user impact now. It's a brittle invariant relying on the open-guard rather than the z-index.
**Fix path:** Give the shortcuts backdrop a higher z-index (e.g. 210) so layering is correct by construction regardless of co-render. One-line, optional.

### FINDING-007 Nit: `humanizeObjectType` lower-cases but never title-cases; comment says "plain words" — confirm that's the intended register
**Dimension:** Correctness / Copy
**Evidence:** `frontend/src/objectType.ts:5-13` maps `snap_box` → `snap box` (all lowercase). In RightPanel it renders as the value of a `Type` row (`RightPanel.tsx:297-299`) and in MyDesigns as a thumbnail label (`MyDesigns.tsx:105`). Both are mid-sentence / label contexts where lowercase reads fine; just flagging that there is no capitalization, which is a deliberate-looking choice but undocumented as such.
**Why it matters:** Purely register/consistency. The util is otherwise correct and well-tested (`objectType.test.ts` covers separators, collapse, trim, and the `''`/`null`/`undefined`/whitespace → `'part'` fallback — a thorough, honest test).
**Fix path:** None required. If a capitalized label is wanted in the MyDesigns thumb, CSS `text-transform: capitalize` is the non-invasive route (keeps the util presentation-neutral). Leave as-is otherwise.

## What's working
- **`humanizeObjectType` is correct and honestly tested.** `objectType.ts:5-13` handles mixed/repeated separators (`_`,`-`), collapses whitespace, trims, and falls back to `'part'` for empty/null/undefined/whitespace — every one of those branches is asserted in `objectType.test.ts:5-23`. The "never blank" fallback is real, not aspirational. Both display sites (`RightPanel.tsx:299`, `MyDesigns.tsx:105`) are wired through it; a grep confirms no raw `object_type` slug still reaches the UI.
- **The shortcuts modal is a genuinely accessible dialog.** `ShortcutsHelp.tsx` sets `role="dialog"`, `aria-modal="true"`, `aria-labelledby` pointing at a real `<h2 id>`, focuses Close on mount, Escape closes, backdrop-click closes, and inner-click `stopPropagation` prevents accidental close — and all of those (except focus-restore and the trap depth) are covered in `ShortcutsHelp.test.tsx`.
- **The global keydown guards are well-designed.** `App.tsx:187-196` correctly excludes INPUT/TEXTAREA/SELECT/contentEditable and any ctrl/meta/alt combo, and checks `defaultPrevented` — so OS/browser combos and in-field typing pass straight through. The wizard-owns-keyboard guard (`:197`) and the "while help open, don't also navigate" guard (`:203-206`) are thoughtful.
- **The stale-closure problem is correctly solved.** `shortcutsRef` (`App.tsx:101-110`, refreshed each render at `:505-510`) lets the once-bound listener call current handlers without rebinding — the right pattern, and the comment explains why.
- **The softened RightPanel copy is a clear win.** `RightPanel.tsx:313-317` replaces "generated directly, not from a parametric template" with plain English; the corresponding test assertion was updated honestly (`RightPanel.test.tsx:134`) rather than left stale.
- **Verification I ran myself:** `tsc --noEmit` clean; targeted `vitest run` of the four affected files (`objectType`, `ShortcutsHelp`, `App`, `RightPanel`) = 75/75 passed. CSS tokens used by the modal (`--kc-r-card`, `--kc-shadow-hero`, `--kc-hair-strong`, `--kc-surface-2`, `--kc-font-mono`, `--kc-ink`) all resolve in `styles.css`. I did not re-run the full 244-test suite or the SPA build (taken as given per the brief).

## Watch items
- The two `window`-level Esc listeners (design-cancel + shortcuts) plus the dialog's own `document` Esc listener mean three handlers can observe one Esc. FINDING-001 is the concrete bite; the general pattern (multiple global Esc listeners without a `defaultPrevented`/precedence contract) is worth a small shared convention as more modals land in later stages.
- Single-focusable-element dialogs (FINDING-003) will recur for every simple modal. A shared, tested `useFocusTrap`/`useDialog` hook would retire both the trap-depth and focus-restore gaps in one place.

## Escalation recommendation
No escalation needed. Zero Blockers, zero Criticals, no security or data-corruption exposure, and the findings are local to this slice — exactly the profile audit-lite is for. Fix FINDING-001 (the design-abort-on-help-Esc) before the Stage 8.5 gate; FINDING-002/003 round out the a11y/test contract the slice set out to deliver; the rest are cleanup. A full audit-team pass is not warranted by this change.

---

## Re-audit (2026-06-05)
**Reviewer:** Claude (audit-lite, independent re-audit)
**Scope:** Verify the seven prior findings are genuinely fixed against current file state (not prior line numbers), hunt for regressions/new issues the fixes introduced. Out of scope (per instruction): `src/kimcad/web/assets/*`, `docs/audits/RUN-LEDGER-2026-06-05.md`.
**Verification run myself:** `vitest run` of the 5 affected files = **84/84 passed**; `tsc --noEmit` = **clean (exit 0)**; plus targeted jsdom probes of focus behavior (below).

### TL;DR
Six of seven prior findings are genuinely resolved with correct fixes and real tests. **One new Minor finding (FINDING-008):** the FINDING-003 fix's third assertion *claims* to exercise the focus-trap's `active === root` branch but does not — in jsdom `dialog.focus()` on the no-`tabindex` dialog `<div>` is a no-op, so `activeElement` stays on the Close button and the assertion passes via the `active === first` branch instead. The `active === root` branch remains untested (and is effectively unreachable in production too — defensive code). Practical risk is low; the defect is the test's false coverage claim, not a product bug. **Net: NOT yet 0/0/0/0/0 — 0 Blocker / 0 Critical / 0 Major / 1 Minor (new) / 0 Nit.** No new Major/Critical introduced by any fix; the FINDING-001 fix is correct and the normal Esc-cancels-design path still works (proven by both tests passing together).

### Per-finding status

**FINDING-001 (Major) — Esc-closes-help-while-busy aborts the run — RESOLVED.**
The design-cancel effect now early-returns when help is open: `App.tsx:178` `if (showShortcuts) return`, inside the `!busy`-guarded effect at `App.tsx:175-183`, dep array `[busy, showShortcuts]` at `App.tsx:183`. Dependency array is **correct**: because `showShortcuts` is in the deps, the listener is re-bound whenever it flips, so the value read inside `onKey` is never stale — there is no path where help is closed but a stale `showShortcuts===true` closure swallows a real cancel. Adversarial traces:
- *Help open + Esc:* design-cancel listener returns (showShortcuts captured `true`); ShortcutsHelp's own `document` Esc listener (`ShortcutsHelp.tsx:21-24`) fires `onClose`+`preventDefault`; the App shortcuts `window` listener sees `defaultPrevented` and returns (`App.tsx:190`). Help closes, design untouched — regardless of listener order, since the guard is value-based not order-based.
- *No help + Esc (normal cancel):* `showShortcuts===false` → guard is a no-op → `designAbortRef.current?.abort()` runs. The existing test "Escape key cancels an in-flight design (keyboard escape)" (`App.test.tsx:437-455`) still passes — the guard does NOT swallow the normal path.
- *Immediately after closing help:* the `true→false` transition re-binds the listener with `showShortcuts===false`, so the very next Esc cancels correctly.
New regression test "Esc closes the help without cancelling a running design (FINDING-001)" (`App.test.tsx:566-589`) asserts dialog gone + `busy==='true'` after Esc — passes. Both this and the normal-cancel test green simultaneously = the two Esc behaviors are genuinely separated. **No new trap.**

**FINDING-002 (Major) — focus not restored on close — RESOLVED.**
`ShortcutsHelp.tsx:17` captures `const previouslyFocused = document.activeElement as HTMLElement | null` on mount; cleanup at `ShortcutsHelp.tsx:42` calls `previouslyFocused?.focus?.()`. Correct no-op/no-throw behavior: `document.activeElement` is `<body>` (never null) when nothing was focused, and the double optional-chain (`?.focus?.()`) means even a null value can't throw. Restoring to `<body>` is acceptable per the original fix-path note. New test "restores focus to the trigger when it closes (a11y)" (`ShortcutsHelp.test.tsx:62-77`) creates a real trigger, focuses it, mounts, asserts focus moved to Close, unmounts, asserts focus returned to the trigger — genuine, not a tautology. Passes.

**FINDING-003 (Major) — focus-trap test was a tautology — RESOLVED (with caveat → FINDING-008).**
The rewritten test (`ShortcutsHelp.test.tsx:46-60`) now genuinely exercises: (a) Tab on the only focusable wraps to Close (`active===last` branch), and (b) Shift+Tab on the only focusable holds Close (`active===first` branch). These are real, non-degenerate assertions of two distinct handler branches (`ShortcutsHelp.tsx:35-40`) — a clear improvement over the prior single forward-case tautology. The Major is resolved. **However**, the third assertion's *claim* to cover the `active===root` branch is false — see FINDING-008.

**FINDING-004 (Minor) — modifier-guard only Ctrl; typing-guard only prompt input — RESOLVED.**
Modifier test is now parametrized `it.each([{ctrlKey},{metaKey},{altKey}])` (`App.test.tsx:557-564`), covering all three modifiers the guard checks (`App.tsx:190`). Typing-guard test now also covers a `contentEditable` element (`App.test.tsx:543-548`) in addition to the textarea. Both pass.

**FINDING-005 (Minor) — `?` over an open InfoTip leaves the tip dangling — RESOLVED.**
`InfoTip.tsx:33-35` adds a `focusin` handler that closes the tip when focus lands outside the wrapper; bound/unbound with the existing open-scoped listeners (`InfoTip.tsx:38,42`). New test "closes when focus moves outside the tip" (`InfoTip.test.tsx:40-50`) passes. **No spurious-close regression:** the handler closes only when `!wrapRef.current.contains(e.target)`; the panel is a non-focusable `role="note"` `<span>` (no tabindex, `InfoTip.tsx:61`) so focus can never land on it, and the only focusable child (the trigger button) is inside the wrapper → `contains` true → stays open. **No perf concern:** the `focusin` listener exists only while a tip is open (`if (!open) return`, `InfoTip.tsx:24`); at most one tip is open at a time.

**FINDING-006 (Nit) — shared z-index 200 — RESOLVED.**
`.kc-modal-backdrop` z-index bumped to **210** in `styles.css` (staged hunk; sits above `.kc-wiz-overlay`'s 200), with a comment documenting the layering intent. Shortcuts help is now on top by construction, not by DOM-order accident.

**FINDING-007 (Nit) — lowercase register — RESOLVED (intentional, no change).**
`objectType.ts:5-13` unchanged; the lowercase-words choice is documented in the file header comment ("Lowercase words, spaces for separators", `objectType.ts:3`). Util correct and still fully tested (`objectType.test.ts:5-23`), wired at both display sites (`RightPanel.tsx:299`, `MyDesigns.tsx:105`); no raw `object_type` slug reaches the UI (remaining refs are `api.ts` type defs + test fixtures only). Confirmed intentional.

### NEW findings

#### FINDING-008 Minor: The focus-trap test's `active === root` assertion is a false-coverage tautology
**Dimension:** Tests
**Evidence:**
- `ShortcutsHelp.test.tsx:55-59` — the test does `dialog.focus()` then `fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })` and asserts `document.activeElement === close`, with a comment claiming it covers "the active===root branch."
- The dialog root is `<div role="dialog">` with **no `tabindex`** (`ShortcutsHelp.tsx:51-58`). I verified directly in jsdom (the test environment) that `.focus()` on a no-`tabindex` `<div>` is a **no-op**: `activeElement` does not change. Probe output, reproducing the exact in-test sequence (Close focused from the prior block, then `dialog.focus()`): `after close.focus, active id=b` → `after dialog.focus, active id=b, === dialog? false`.
- Therefore at the Shift+Tab in that third block, `active` is still the Close button (`=== first`), so the handler takes the **`active === first`** path (`ShortcutsHelp.tsx:37`), not the `active === root` path. The assertion passes for the wrong reason; the `active === root` sub-branch is never reached by any test.
**Why it matters:** It's the same defect-class the original FINDING-003 named — a test asserting coverage of a branch it doesn't actually exercise. A regression that broke the `active === root` sub-branch would still pass green. Severity is **Minor, not Major**, because: (1) the two other trap branches (forward-wrap, reverse-hold) ARE now genuinely exercised — the core of FINDING-003 is fixed; and (2) the `active === root` branch is effectively unreachable in production too (the root never gets `tabindex` and the trap only ever `.focus()`es the focusable buttons, never the root) — so it's defensive code whose mis-coverage carries low real risk.
**Fix path:** Two honest options. (a) Make the assertion real: add `tabindex="-1"` to the dialog root (common a11y practice so a dialog with no focusables can still receive initial focus) — then `dialog.focus()` works in jsdom, `active === root` is genuinely hit, and the test means what it says. (b) If the root deliberately stays non-focusable, delete the third assertion and its comment (it's dead) and document that `active === root` is unreachable defensive code. Option (a) is the better long-term move (it also future-proofs the trap for a zero-focusable dialog); option (b) is the smaller honest change. Either removes the false claim.

### Severity rollup (re-audit)
- Blocker: 0
- Critical: 0
- Major: 0  (all 3 prior Majors resolved)
- Minor: 1  (new FINDING-008; both prior Minors resolved)
- Nit: 0  (both prior Nits resolved)

### Verdict
**Not yet 0/0/0/0/0** — one new Minor (FINDING-008) remains: a single test assertion whose claimed `active===root` coverage is a jsdom no-op tautology. Every prior finding (3 Major / 2 Minor / 2 Nit) is genuinely resolved with correct fixes and real, passing tests; the FINDING-001 design-cancel separation is correct with no new trap and the normal cancel path intact. No new Major/Critical/Blocker introduced. The slice is shippable on product behavior; closing FINDING-008 (one assertion fix) gets it to a clean 0/0/0/0/0. No escalation to audit-team warranted.

### FINDING-008 — RESOLVED (fix applied 2026-06-05)
Applied option (a): `frontend/src/components/ShortcutsHelp.tsx` dialog root now carries `tabIndex={-1}`
(programmatically focusable, not a tab stop — excluded from the trap's focusable query). The trap test's
third case (`dialog.focus()` then Shift+Tab) now genuinely lands focus on the root and exercises the
`active === root` branch, which wraps focus to Close. ShortcutsHelp suite green (6/6). This was the only
item outstanding after the re-audit; with it closed the slice is **0/0/0/0/0**.
