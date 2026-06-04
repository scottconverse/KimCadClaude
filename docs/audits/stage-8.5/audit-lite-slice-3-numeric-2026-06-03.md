# Audit Lite — Stage 8.5 Slice 3: numeric editing
**Date:** 2026-06-03
**Scope:** Inline numeric input on parameter value labels in `RightPanel.tsx` (click-to-edit, Enter/blur commits, Escape cancels, live out-of-range error), plus updated LLM-part hint text and matching CSS. Four new tests in `RightPanel.test.tsx`.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/1/0** — ship after one Minor fix. The numeric editing feature is correct and well-guarded. One Minor: `commitEdit` duplicates the same `onChange(name, clampToSpec(raw))` call in both branches of the `raw < min || raw > max` check — the in-range and out-of-range paths do the identical thing. Harmless, but dead code. Fix is a single-line de-dup. Tests are non-vacuous. 78 vitest pass.

> **FINAL (after remediation): 0/0/0/0/0.** As-found below; see fix applied.

## Severity rollup

**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.

## Findings

### FOUND-001 Minor: `commitEdit` has a dead-code branch — both paths call the same `onChange`
**Dimension:** Correctness
**Evidence:** `RightPanel.tsx`, `commitEdit()`:
```
if (raw < spec.min || raw > spec.max) {
  onChange(spec.name, clampToSpec(raw, spec))  // ← branch A
  return
}
onChange(spec.name, clampToSpec(raw, spec))    // ← branch B — identical
```
Both branches call `clampToSpec` and `onChange` with the same arguments. The early `return` separates them but the result is the same — `clampToSpec` handles the clamping in both cases, so the `if` condition is never needed. The error *display* during typing (live validation) is correct; only the commit logic has the redundant branch.
**Why it matters:** Not a bug (behaviour is correct), but a reader studying the code will expect branch A and branch B to do different things. It could introduce a real bug if someone later edits only one branch thinking they differ.
**Fix path:** Remove the `if (raw < spec.min || raw > spec.max)` block entirely; keep only the unconditional `onChange(spec.name, clampToSpec(raw, spec))`.

## What's working

- **Clamp logic is correct.** `clampToSpec` does `Math.max(min, Math.min(max, raw))` then `Math.round` for `spec.integer`. No off-by-one on min/max. Verified for positive, negative, and integer cases.
- **NaN / empty input silently reverts.** `parseFloat('')` → `NaN` → `if (Number.isNaN(raw)) return` — no `onChange` fired, no error shown, the value stays as it was. Correct and unobtrusive.
- **Escape key cancels with no side effects.** `handleKeyDown` sets `editing=false` and `inputError=null`. `onChange` is never called. The value button is restored. The Escape test confirms this.
- **Slider drag clears the edit mode.** The range input's `onChange` calls `setEditing(false)` before forwarding to the parent — so the inline input closes if the user drags while mid-edit, with no stuck-open state.
- **`step` attr on the number input matches `spec.step`** — the browser's native validation nudges align with the slider's step. No drift.
- **Accessibility.** The button has `aria-label` announcing the full value + unit + "Click to edit." The number input has `aria-label` with label + unit, `aria-invalid` on error, `aria-describedby` pointing to the error span. The error span has `role="alert"` for live announcement. Focus-visible ring on the button.
- **LLM-part hint is actionable.** Updated from a vague "describe a change to start a new version" to an explicit "use the conversation on the left" with concrete examples ("make it 10mm taller", "add M3 mounting holes"). Directly pairs with the Slice 2 refine input.
- **Tests are non-vacuous.** The commit test asserts `onRerender` was called with the right value object (`{width: 120}`); the clamp test asserts `{width: 200}` (not 500); the cancel test asserts `onRerender` was NOT called. Each pin a distinct failure mode.

## Watch items
- The `setTimeout(() => inputRef.current?.select(), 0)` in `startEdit` is used to auto-select the input text. In jsdom tests this works because `setTimeout(fn, 0)` resolves synchronously with fake timers or after a tick. In real browsers it's fine too. Not a concern.

## Escalation recommendation
No escalation needed. One Minor (dead-code branch in `commitEdit`, fixed inline). 78 tests pass. Ship.
