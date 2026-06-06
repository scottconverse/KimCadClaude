# Next-Sprint Watchlist — Stage 8.5 Slice 1

Forward-looking items. Slice 1's findings are all fixed in-slice; these are structural notes to carry into the rest of Stage 8.5 and to its stage-end gate.

## Carry to Stage 8.5 stage-end (the docs-at-stage-end cadence)
- **Front-door docs refresh (DOC-004 tail).** At stage end, do the full README status-block + feature-list update, a `CHANGELOG.md` Stage-8.5 "Added" section, an `ARCHITECTURE.md` "My Designs store + `/api/designs*`" entry, and a polished user-facing "saving your work / My Designs / export-import" guide. The in-slice fix lands the accurate-now subset; the polished manual belongs at the gate. (Matches the Stage-7 precedent.)

## Structural / decision items
- **Server-side save-identity model.** The per-`rid` save-identity map added for QA-002 is the minimal fix. A cleaner long-term model: the client owns a stable design identity from first frame (mint the id client-side or return it synchronously) so auto-save is idempotent by construction rather than by a server-side rid map that evicts with the registry. Revisit if multi-tab editing becomes a goal.
- **Concurrency fuzzing as a standing harness.** QA-001 was found only by a runtime multi-threaded probe; the unit suite was green. The in-slice concurrency test (TEST-004) pins the specific race — consider a small reusable threaded-store harness for future stages that touch the store.
- **`_safe_id` as the single id-trust boundary.** It's centralized and correct; the ASCII-tighten (ENG-002) lands now. Keep all future id-taking paths funneled through it — don't add a second id-resolution path.
- **Best-effort save UX contract.** With save no longer a 500 (QA-001), the SPA should eventually *retry* a failed best-effort save and reflect "Saving…/Saved/Retrying" (UX-001's indicator is the surface for it). A silent best-effort miss is acceptable short-term; a visible retry is the right end state.

## Carry from the Slice-1 wiring-audit
- **CI Playwright E2E for the core journeys.** `test_webapp.py` covers the HTTP contract and the
  `wiring-audit` covers the running app per-slice, but there is no automated browser E2E in CI for
  create→auto-save→reload-restore, the gallery CRUD, the save-indicator state machine, or a
  mobile-viewport assertion that `.kc-design-act` targets are ≥44px tall (the M-1 proof). Stand up a
  small Playwright suite so these lock in CI, not just in the manual wiring-audit. Natural fit with
  the Slice-11 accessibility/responsive sweep.

## Watch (not yet acute)
- **Orphan/`_prune` cost at scale.** The in-slice prune fix is O(N) stats + parse-only-over-cap; fine at the 200-design cap. If the cap grows, move to an index file or mtime proxy.
- **Touch-target convention.** UX-003 fixed the card actions; going forward, every new control should join the coarse-pointer 44px floor selector by default rather than per-component retrofits.
