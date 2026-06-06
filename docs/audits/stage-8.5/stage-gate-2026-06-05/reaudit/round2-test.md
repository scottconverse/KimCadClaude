# Stage 8.5 (Usability) — Test Engineer ROUND-2 RE-VERIFY (closure)

**Repo:** `C:\Users\scott\dev\kimcad`  **Branch:** `stage-8.5-usability` @ `a6dff43`
**Date:** 2026-06-05  **Role:** Test Engineer (independent round-2 re-verify; no source modified)
**Verifies:** the second-tier test additions that close round-1 findings RTEST-001..006 (from `reaudit/04-test-reaudit.md`, raised @ `6c98674`).

---

## What changed between round-1 (`6c98674`) and HEAD (`a6dff43`)

`git diff --stat 6c98674..a6dff43` (test files only):
- `frontend/src/components/ChatPanel.test.tsx`  +16  (RTEST-002, 2 tests)
- `frontend/src/components/Topbar.test.tsx`      +25  (RTEST-003, 1 test + `../api` mock)
- `frontend/src/components/Workspace.test.tsx`   +64  (RTEST-004, NEW file, 2 tests)
- `tests/test_webapp.py`                          +45  (RTEST-005 + RTEST-006, 2 tests)

That is exactly the +5 vitest and +2 pytest the counts below reconcile to. No other source/test files moved (the rest of the diff is docs/CSS/ledger).

---

## Per-item verdict

### RTEST-002 (Minor) — refine chips — RESOLVED
`ChatPanel.test.tsx:73` asserts clicking the "Make it taller" chip calls `onRefine('Make it taller')` (the exact chip text, not a generic call). `ChatPanel.test.tsx:79` renders with `result.status:'clarification_needed'` and asserts the chip group is **absent** while the answer input is still present. Mirrors the implementation at `ChatPanel.tsx:249-265` (chips gated on `status !== 'clarification_needed'`, each `onClick={() => onRefine(chip)}`).
**False-green check:** mutated `onRefine(chip)` → `onRefine('WRONG')`; RTEST-002 went red. Genuine.

### RTEST-003 (Minor) — Topbar printer chip — RESOLVED
`Topbar.test.tsx:6` now mocks `../api` so `getOptions()` resolves a printer (`Bambu Lab P2S`, `build_volume:[256,256,256]`). `Topbar.test.tsx:100` awaits the mount effect and asserts both the name `Bambu Lab P2S` and the volume string `256×256×256 mm` render. Matches `Topbar.tsx:51-71,88-98` (best-effort `getOptions` on mount, chip absent if it can't load).
**False-green check:** gated the chip render off (`{false && printerChip && (...)}`); RTEST-003 went red. Genuine. (The "degrades to absent on reject" half of the round-1 fix-path was not added as a second case — the chip's `try/catch`→absent is exercised indirectly by every other Topbar test that does NOT mock `../api` and still renders without the chip; acceptable, noted as residual below.)

### RTEST-004 (Minor) — mobile CTA — RESOLVED
`Workspace.test.tsx:46` asserts the "Check & download" CTA is **absent** with `result:null` and **present** after rerender with a meshed result (`has_mesh:true`) — i.e. gated on a mesh, exactly as `Workspace.tsx:117`. `Workspace.test.tsx:53` installs a real `#kc-export-card` with a `scrollIntoView` spy, clicks the CTA, and asserts the spy fired — proving the click scrolls the export card (`Workspace.tsx:121-125`).
**False-green check:** gated the CTA off (`{false && result?.has_mesh && (...)}`); both RTEST-004 tests went red. Genuine. The jsdom media-query caveat from round-1 stands (the mobile-only visibility is CSS, untestable in jsdom) but the element + handler — the load-bearing logic — are proven.

### RTEST-005 (Minor) — /api/render adjusted_params — RESOLVED
`test_webapp.py:1501` drives a real socket render: width 99999 → asserts `adjusted_params` present and lists `width`; then width 100 (in range) → asserts the key is **absent**. Exercises both branches of the diff logic at `webapp.py:1758-1773` (float-compare ≤1e-6, requested/applied pairing).
**False-green check:** removed the `payload["adjusted_params"] = adjusted` write; RTEST-005 went red. Genuine.

### RTEST-006 / QA-N1 (Nit→ part RESOLVED) — demo scenarios — RESOLVED (the load-bearing half)
`test_webapp.py:1515` runs the full demo chain over a real socket with the real OpenSCAD renderer: `demo:gatefail` + `experimental:false` → asserts `status == "needs_experimental"` (offered, never auto-run); opt-in `experimental:true` → asserts `report.gate_status == "fail"` (the 300mm cube exceeds the build plate); then `POST /api/slice/{rid}` → asserts `sliced:false, reason:"gate_failed"`; and a normal prompt → asserts non-fail. This is the strongest of the new tests — it proves the gate-failed state is reachable in the live demo AND still refused. Matches `webapp.py:296-302` (`demo:gatefail` → `oversized_block` object_type → experimental offer).
**False-green check:** disabled the `demo:gatefail` routing branch; the offer became `completed` and RTEST-006 went red. Genuine.
**Residual (accepted):** the `allow_nan` non-finite-to-clean-500 guard and the `_cloud_cache` LRU bound (the other two thirds of the original RTEST-006 batch) were left untested and dispositioned "defensive, accepted" in the ledger. See judgment below.

### RTEST-001 (Minor) — ENG-002 re-gate end-to-end seam — RESOLVED-BY-COMPOSITION (residual: the exact named seam still has no single dedicated test)
No new socket test was added that reopens a *stored-pass-over-an-unprintable-mesh* design and asserts gate-fail-on-reopen + slice refusal as one flow. The disposition (per the ledger) leans on three existing pieces, which together I judge **adequate for a Minor**:
- `test_webapp.py:1471` — `_regate_mesh` re-derives `"fail"` for a 300mm mesh *regardless of any stored verdict* (the safety claim's core: a tampered `gate_status:"pass"` cannot survive re-gating).
- `test_webapp.py:1485` — in-bounds re-gates non-fail; unreadable mesh / missing plan returns `None` (caller falls back to stored, never false-fails a real reopen).
- Reopen wiring at `webapp.py` `_handle_design_reopen` sets `gate_status_by_rid[rid] = regated or stored or "fail"`, and the new `demo:gatefail` test (`:1515`) proves the live `gate_status:"fail"` → `/api/slice` → `reason:"gate_failed"` refusal end to end (the second half of the seam). The pre-existing `test_rerender_into_a_gate_failed_shape_blocks_slice_and_send` (`:1336`) independently proves a runtime-derived fail blocks slice+send over the socket.
**Honest residual:** the one thing still not directly asserted by any single test is the *composed* path "reopen an altered design → it comes back gate-failed → that specific reopened rid is refused by /api/slice." The re-derivation (unit) and the fail→refuse (socket) are each proven; the join is proven only by reading the wiring. This is exactly the round-1 characterization (Minor: wiring present + unit-covered) — not escalated, but not silently called "fully tested" either. A ~25-line integration test would fully close it.

### allow_nan / cache-bound nits — ACCEPTABLY LEFT DEFENSIVE
- `allow_nan=False` guard (`webapp.py` `_json`): a non-finite number yields a clean 500 instead of invalid JSON. No code path today feeds a non-finite into `_json` from a normal request, so it is genuinely a defensive belt-and-suspenders. Acceptable untested at Nit.
- `_cloud_cache` LRU bound (max 4): key material (the original ENG-005 concern), so one eviction assertion would have been the higher-value of the two. Left untested. I concur it stays a Nit (the cache is bounded by construction — an `OrderedDict` with an explicit cap check — and the exposure is a slow leak, not a safety or correctness break), but I flag it as the single residual most worth a one-liner if a follow-up sweep happens. Not a Stage-8.5 blocker.

---

## Suites I actually ran (this round-2, at `a6dff43`)

- **Python (non-live):** `.venv\Scripts\python.exe -m pytest -m "not live" -q` → **763 passed, 4 deselected** in 133.58s. (+2 vs round-1's 761 = RTEST-005 + RTEST-006.) The 4 deselected are the `live` marker (real OrcaSlicer slice+send) — the only justified skips. Every renderer/re-gate test ran for real (OpenSCAD + trimesh present).
- **Frontend (vitest):** `npm --prefix frontend run test -- --run` → **262 passed across 23 test files** in 8.96s. (+5 vs round-1's 257 = 2 ChatPanel + 1 Topbar + 2 Workspace; Workspace.test.tsx is the new 23rd file.)
- **Combined: 1025 passing, 0 unjustified skips. Suites clean, no flakes.**

## False-green sweep (does any new test pass while the thing it names is broken?)

I broke each implementation and confirmed the corresponding test turns red, then restored (working tree verified clean, HEAD unchanged at `a6dff43`):

| Test | Mutation | Result |
|---|---|---|
| RTEST-005 adjusted_params | drop `payload["adjusted_params"]=adjusted` | RED ✓ |
| RTEST-006 demo:gatefail | disable `demo:gatefail` routing branch | RED ✓ |
| RTEST-002 refine chip | `onRefine(chip)` → `onRefine('WRONG')` | RED ✓ |
| RTEST-003 printer chip | gate chip render off | RED ✓ |
| RTEST-004 mobile CTA | gate CTA render off | RED ✓ (both cases) |

No test was found green-despite-broken. The new tests assert behavior, not render.

---

## Closure summary

| Item | Round-1 sev | Round-2 verdict |
|---|---|---|
| RTEST-001 re-gate e2e | Minor | RESOLVED by composition (residual: composed seam un-joined by a single test) |
| RTEST-002 refine chips | Minor | RESOLVED |
| RTEST-003 printer chip | Minor | RESOLVED |
| RTEST-004 mobile CTA | Minor | RESOLVED |
| RTEST-005 adjusted_params | Minor | RESOLVED |
| RTEST-006 demo scenarios | Nit | RESOLVED (load-bearing half); allow_nan/cache left defensive |

**Residuals (none blocking):**
1. RTEST-001's composed reopen→fail→refuse path is proven only by wiring + its two halves, not one integration test (~25 lines to fully close).
2. `_cloud_cache` LRU eviction has no assertion (key material; low-exposure; one-liner if a follow-up sweep runs).
3. RTEST-003's "chip absent when getOptions rejects" is covered indirectly (other Topbar tests render chip-less), not by an explicit reject case.

**Test-role rollup (round-2): Blocker 0 / Critical 0 / Major 0 / Minor 0 / Nit 0.**
All six round-1 second-tier findings are closed; the three residuals above are below Nit (defensive / indirectly-covered / wiring-proven) and do not re-raise. The new tests genuinely prove what they claim — verified by mutation, not just by green.

Counts: pytest **763 passed / 4 deselected** (non-live), vitest **262 passed / 23 files**, combined **1025 passing, 0 unjustified skips, no flakes.**

**Bottom line: Test role is clear for the Stage-8.5 gate.** Nothing here blocks merge + tag.
