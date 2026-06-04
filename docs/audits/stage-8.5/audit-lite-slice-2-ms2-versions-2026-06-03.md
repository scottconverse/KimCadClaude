# Audit Lite — Stage 8.5 Slice 2 MS-2: version timeline + undo
**Date:** 2026-06-03
**Scope:** Version history state in `App.tsx`, `VersionRail.tsx` pill-strip component, `DesignVersion` type in `api.ts`, CSS for version rail/pills, `Workspace.tsx` wrap update, and four new version tests in `App.test.tsx`.
**Reviewer:** Claude (audit-lite)

## TL;DR
**FINAL: 0/0/0/1/0** — ship after one Minor fix. The version timeline is correct and the branching logic holds. One Minor: `handleSwitchVersion` doesn't cancel the save indicator / resave timer when switching versions (the user switches back to v1 while v2 is still saving, and the "Saving…" indicator from v2 persists). Easy one-line fix. Tests are non-vacuous. 73 vitest pass.

> **FINAL (after remediation): 0/0/0/0/0.** As-found below; see fix applied.

## Severity rollup

**As found:** 0 Blocker · 0 Critical · 0 Major · 1 Minor · 0 Nit.

## Findings

### FOUND-001 Minor: `handleSwitchVersion` doesn't reset the save indicator
**Dimension:** UX / Correctness
**Evidence:** `App.tsx:219-228` — `handleSwitchVersion` sets messages, result, versionIdx, error, and rerenderError, but does NOT call `resetSaveIndicator()`. If the user switches to v2 (which starts a save), then immediately switches back to v1, the Topbar will still show "Saving…" for v2's save — which has no relation to v1. The `resaveTimer` may also fire for v2 after the user has moved back.
**Why it matters:** The save indicator shows false state — "Saving…" when the viewed design isn't being saved. Minor not Critical because the save still completes (just the label is misleading), and it's only visible for the brief window between switching and the save completing.
**Fix path:** Add `resetSaveIndicator()` to `handleSwitchVersion` before setting the version state. One line.

## What's working

- **Branching logic is correct.** `runDesign` (App.tsx:164-176) calls `setVersions((prevVers) => { const base = fromVersionIdx !== undefined ? prevVers.slice(0, fromVersionIdx + 1) : prevVers; ... })` — this correctly truncates the tail when branching. When refining from v1 (fromVersionIdx=0), `prevVers.slice(0, 1)` keeps only v1, and the new version is appended as the new v2. Verified: the branch test confirms 2 versions (not 3) after branch-from-v1.
- **`setVersions` inside `setMessages`'s functional updater is safe.** React batches both state updates in the same transaction, so there's no stale closure issue — `prevVers` is always current in the functional updater passed to `setVersions`.
- **`handleSwitchVersion` restores both messages AND result** (App.tsx:222-224) — the mesh_url in `ver.result` drives the viewport, confirmed by the switch-version test asserting `mesh-url` changes.
- **VersionRail returns null when `versions.length < 2`** — no chrome clutter on first design, and the workspace layout is unaffected.
- **Undo disabled on v1.** `canUndo = versionIdx > 0` (VersionRail.tsx:22). The `← Undo` button has `disabled={!canUndo}`. The `← Undo` still renders with `disabled` styling (`opacity: 0.35`) rather than disappearing — the right pattern (the user sees there's nothing to undo).
- **Redo conditional.** `{canRedo && <Redo button>}` — Redo only appears when the user has stepped back to a prior version. Clean.
- **Accessibility:** Each pill has `aria-label="Version N: <prompt>"` and `aria-current="true"` on the active version. The rail has `role="navigation" aria-label="Design versions"`. Focus-visible rings on both pills and step buttons.
- **Tests are non-vacuous:** version-count and version-idx are asserted directly from testids; the branch test asserts count=2 after 3 calls to confirm truncation; switch-version asserts both mesh-url AND msg-count change.

## Watch items
- The server's mesh registry has a cap (`MAX_REGISTRY=50`). If the user creates more than 50 versions (unlikely in a session), an early version's mesh_url will 404 on switch. Current behavior: the viewport would show the prior mesh until cleared. Worth a watch but not a blocker at this scale.

## Escalation recommendation
No escalation needed. One Minor (save indicator not reset on version switch, fixed inline). Tests solid. Ship.
