# Executive Audit — KimCad Stage 8.5 Slice 1 ("My Designs": local persistence + library + export/import + search/sort)

**Audit date:** 2026-06-03
**Audit type:** Stage-gate, full five-role team, balanced posture
**Subject:** The complete Slice 1 diff `main...stage-8.5-usability`, HEAD `657bc3b` (code only — `docs/**` and `src/kimcad/web/assets/**` build output excluded)
**Gate bar:** 0/0/0/0/0 (every finding fixed, Blocker→Nit) before Scott's approval.

---

## Executive summary

Slice 1 is careful, defensively-written, well-tested code that genuinely fixes the deal-killer it set out to kill: build a part, the URL silently becomes `#/design/<id>`, reload the page, and the part + sliders + readiness all come back — verified live, no lost work. The five load-bearing safety invariants (path safety, decompression-bomb bounding, never-raises persistence, body caps, serialized/atomic writes) all hold under direct adversarial probing: a real 200 MiB zip bomb was rejected, every path-traversal id and zip-slip archive was refused with nothing written outside the store, and no probe leaked a traceback. The console is silent and every library state (loading/empty/populated/no-match/error) exists.

The audit found **one Critical**: on Windows, the "atomic" `os.replace` in the meta write collides with the gallery's own concurrent `meta.json` reads, so **~43% of saves return HTTP 500 under the realistic "auto-save while My Designs is open" load** (data never corrupts; the *edit* is lost, not the library). The rest is a tail of Major/Minor reliability, UX-reassurance, and test-coverage gaps that cluster around three roots: (1) the live mesh + meta writes aren't fully concurrency-safe on Windows, (2) auto-save has **no "Saved" signal** so the user can't tell the headline feature worked, and (3) the frontend auto-save lifecycle is untested. No Blockers; nothing security-reachable.

## Severity roll-up (all roles, as found)

| Severity | Eng | UX | Docs | Test | QA | **Total** |
|---|---|---|---|---|---|---|
| Blocker  | 0 | 0 | 0 | 0 | 0 | **0** |
| Critical | 0 | 0 | 0 | 0 | 1 | **1** |
| Major    | 1 | 3 | 1 | 1 | 1 | **7** |
| Minor    | 4 | 4 | 4 | 4 | 3 | **19** |
| Nit      | 3 | 3 | 1 | 2 | 1 | **10** |
| **Total**| 11 | 10 | 6 | 7 | 6 | **37** |

## Top findings (sorted by severity / leverage)

1. **QA-001 (Critical)** — `os.replace` in `_atomic_write_json` raises `PermissionError [WinError 5]` against concurrent `meta.json` readers on Windows → 13/30 saves (43%) return HTTP 500 under auto-save-while-gallery-open; rename silently fails. *(→ ENG-001/ENG-004 atomicity root.)*
2. **UX-001 (Major)** — Auto-save is completely silent; no "Saved" signal anywhere, so the user can't tell the slice's headline value worked (Scott's "how do people even know it's there?", still unanswered).
3. **QA-002 (Major)** — Auto-save without a `saved_id` mints a new library entry per call; a fast build→edit before the first save's id round-trips creates duplicate gallery entries (reproduced; the inherited library already had a dup). *(= TEST-001 client side.)*
4. **TEST-001 (Major)** — The frontend auto-save lifecycle (create-race `creatingRef` guard, debounce, update-in-place) is entirely untested: the `Workspace` stub never calls `onModelReady`, so `persist()`/`saveDesign()` is dark in every test.
5. **ENG-001 (Major)** — `save()` copies the live mesh outside the lock a concurrent re-render holds, and the pipeline exports the mesh non-atomically, so a same-id save+re-render can capture a torn STL (silent corrupt entry). *(= ENG-003; one fix.)*
6. **UX-002 (Major)** — Library card controls have no branded `:focus-visible` ring; the thumbnail "open" button risks no visible keyboard focus at all.
7. **UX-003 (Major)** — Card action buttons (Rename/Duplicate/Export/Delete) are ~25px tall, 4px apart, excluded from the coarse-pointer 44px floor — error-prone on touch, destructive Delete flush against Export. *(= QA-005.)*
8. **DOC-001 (Major)** — `ROADMAP.md` "Current baseline" still says "Next = Stage 8 (CadQuery)" and its "Still ahead" list omits Stage 8.5, contradicting the same file's own 8.5 "IN PROGRESS" section + HANDOFF + plan + spec.

## Cross-role findings (one issue, multiple lenses)

- **Atomicity / Windows concurrency — QA-001 + ENG-001 + ENG-003 + ENG-004 + TEST-004.** The auto-save fires frequently and concurrently with reads; the persistence atomicity story is solid on POSIX but has a Windows hole (`os.replace` vs open handles) and an orphan-dir edge. Highest-leverage fix area: a retry-on-`PermissionError` in `_atomic_write_json` + atomic mesh export + an orphan-reclaiming prune + a concurrency test.
- **Duplicate-entry race — QA-002 + TEST-001.** The same auto-save timing that drives QA-001 produces duplicate library entries when the first save's id hasn't round-tripped; the client guard (`creatingRef`) is untested. Fix: a server-side per-`rid` save identity + the missing client test.
- **Duplicate timestamp — UX-006 + DOC-003.** `duplicate()` copies the source's `created_at` (so a copy doesn't sort newest), and its docstring claims a "caller stamps" contract no caller fulfills. Fix: stamp a fresh `created_at` + correct the docstring.
- **`_safe_id` precision — ENG-002 + TEST-006.** `_safe_id` accepts Unicode alphanumerics (and Windows reserved names), not just ASCII — not an escape (it can't leave the root), a robustness gap vs documented intent. Fix: ASCII allowlist + a rejection test.
- **Touch targets — UX-003 + QA-005.** Same ~25px card-action height from two lenses.

## What's working (credited, specific)

- **The deal-killer is fixed at the mechanism level** — create→auto-save→reload→restore verified end to end in the browser (part, prompt, sliders, readiness all return); a deleted id's reopen/export both 404 (no stale state).
- **Security invariants hold under adversarial probing** — path traversal (`..%2f…`, dotted/slash ids) rejected on every endpoint; zip-slip (`../evil.txt` member) ignored with nothing escaping; a 200 MiB zip bomb rejected by the bounded read; oversized uploads 413; no traceback leaks across ~80 hostile requests.
- **Complete state coverage + console silence** — loading/empty/populated/no-match/error all exist and were triggered live; zero console errors/warnings across the whole session.
- **Strong, honest backend test suite** — 75 pytest (incl. real-socket HTTP integration, the bomb cap, the export→import round-trip with coexistence, traversal on the live thumb endpoint, the stale-snapshot regression) + 56 vitest, all green.
- **Status-honesty discipline held** — no doc claims Slice 1 / Stage 8.5 is done/merged/tagged; spec addenda match the shipped feature; the safety docstrings (zip-slip, bounded-read, never-raises, local-first) are accurate.

## This-sprint punch list

See `sprint-punchlist.md` — every Blocker/Critical/Major + all cheap/urgent Minors and Nits. Per Scott's standing rule, **all 37 findings are fixed this slice** (no deferral), re-audited to 0/0/0/0/0 before approval.

## Next-sprint watchlist

See `next-sprint-watchlist.md` — structural items to carry to Stage 8.5 stage-end (full README/CHANGELOG/ARCHITECTURE refresh + a user-facing My Designs guide; a server-side save-identity model; broader concurrency fuzzing).

## Blast-radius notes for the dev team

- The **atomic-mesh-export** fix lands in `pipeline.py` and hardens the *pre-existing* mesh-GET path, not just save — regression-test the viewport mesh fetch + slice input after it.
- The **`_atomic_write_json` retry** touches every writer (save/rename/duplicate/import/prune) — one change, global effect; verify under the new concurrency test.
- The **save-not-a-500** change alters the save endpoint's failure contract (500 → 503/`saved:false`) — the SPA must treat a non-2xx save as best-effort (it already swallows it) and ideally retry.

## Resolution

See `## Remediation — 2026-06-03` below.

---

## Remediation — 2026-06-03 — 0/0/0/0/0

All 37 findings (1 Critical · 7 Major · 19 Minor · 10 Nit) were fixed in-slice — none deferred — and the fixes were independently re-audited (two adversarial passes: a runtime QA re-audit that reproduces the original stress, and a static fix-verification across every finding). Both returned **RESIDUAL: none, NEW: none**. Re-audit reports: `reaudit-qa-2026-06-03.md`, `reaudit-static-2026-06-03.md`.

**The Critical, confirmed dead at runtime.** QA-001's fix (`_atomic_write_json` retries `os.replace` on Windows `PermissionError` + the save endpoint returns a soft 503, not a hard 500): across **730 stressed update-in-place saves while 8–16 reader threads polled list/export**, the re-audit measured **0 HTTP 500** (down from the original 43%). The only non-200s were the intended soft 503 (`saved:false`, "your work is still here; retrying") and 404s from the pre-existing `MAX_REGISTRY=50` registry eviction (not the write race).

**Highest-leverage fixes, by root:**
- *Atomicity / Windows concurrency (QA-001, ENG-001/003/004, TEST-004):* `os.replace` retry; atomic mesh export in `pipeline.py` (temp + `os.replace`, `file_type="stl"`); `_prune` reclaims orphan dirs and skips the index parse under the cap; a threaded store concurrency test.
- *Duplicate-entry race (QA-002, TEST-001):* a server-side `rid_saved_id` map converges rapid auto-saves to one entry; the frontend `Workspace` test stub now fires `onModelReady`, pinning the `creatingRef` create-race + update-in-place.
- *Save reassurance (UX-001, UX-007):* a Topbar "Saving… / Saved · My Designs / retrying" indicator with a self-healing retry; per-card action errors surfaced.
- *Card affordances (UX-002, UX-003/QA-005):* branded `:focus-visible` rings on every card control; the coarse-pointer 44px floor + wider gap + Delete separated from Export.
- *Contracts (QA-003, QA-006):* mutate verbs 404 on unsafe/absent id; method-not-allowed returns a JSON body.
- *Polish + safety (ENG-002/006/007/008, UX-004/005/006/009, DOC-003):* ASCII-tight `_safe_id`; `clip_name` helper; `Export (.kimcad)` label; active-nav state; a duplicate stamps a fresh `created_at`.
- *Docs (DOC-001/002/004/005/006):* ROADMAP single-truth restored; the stale audit-lite count corrected; README/CHANGELOG/ARCHITECTURE updated + a new `docs/guide-my-designs.md`; config docstring + a stray comment word.

UX-008 and UX-010 required no change (the auditor judged them already-satisfied: the "Importing…" cue is adequate; card-hover motion is covered by the global reduced-motion block).

**Verification:** ruff clean; pytest **694 passed** (non-live) — design-store + webapp subset **81 passed** (was 75, +6); vitest **66 passed** (was 56, +10); `tsc` + `build` clean; committed SPA assets regenerated. The full suite incl. live OrcaSlicer runs on push via the pre-push hook.

**Roll-up after remediation: 0 / 0 / 0 / 0 / 0.**
