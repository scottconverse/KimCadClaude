# Executive Audit — Snapmaker U1 + Multi-Toolhead Feature

**Audit date:** 2026-06-16
**Audit scope:** Scoped to commits cc80fed + 3553665 — Snapmaker U1 + generic multi-toolhead printer support
**Posture:** Balanced
**Roles engaged:** Principal Engineer, UI/UX Designer, Technical Writer, Test Engineer, QA Engineer

---

## Executive summary

The Snapmaker U1 and generic multi-toolhead feature is architecturally sound and correctly wired end-to-end: the connector inherits cleanly from MoonrakerConnector, the registry is correct, the API surfaces the right data, and the demo-mode runtime confirms expected behavior. However, the feature shipped with seven Critical findings across five dimensions that must be fixed before this is ready for Snapmaker users: a cache-key collapse that can silently serve the wrong G-code for a multi-head job, temperature chips with no CSS styling, and a complete absence of documentation updates across CHANGELOG, api.md, supported-printers.md, and ARCHITECTURE.md. Additionally, two new code paths — `resolve_filament_slots()` and the `--filament-config` multi-head CLI branch — have zero test coverage, meaning the suite would stay green while multi-toolhead slicing silently used the wrong profile. The fix workload is real but concentrated: the engineering bugs are surgical, the docs are a batch write, and the missing tests are a focused afternoon.

---

## Readiness at a glance

| Dimension | Status | Summary |
|---|---|---|
| Architecture & code | Concerns | Correct design; 1 Critical cache-key collapse + 1 Major 1-slot branch bug |
| UI / UX | Serious issues | Temperature chips have no CSS (Critical); 3 Major UX gaps in labeling, layout cap, and summary feedback |
| Documentation | Serious issues | Zero docs updated across all 5 surfaces — CHANGELOG, api.md, supported-printers, ARCHITECTURE |
| Test suite | Serious issues | 2 Critical gaps: resolve_filament_slots and --filament-config CLI branch have zero coverage |
| Runtime QA | Concerns | Runtime confirms correct behavior in demo mode; mock faithful for all-4-extruder case only |

---

## Severity roll-up

| Severity | Count | What it means |
|---|---|---|
| Blocker | 0 | No ship-stopper |
| Critical | 7 | Fix this sprint — wrong behavior or completely missing coverage/docs |
| Major | 12 | Fix this or next sprint |
| Minor | 10 | Batch for hygiene work |
| Nit | 6 | Preference-level; flag once |
| **Total** | **35** | |

---

## Top 10 findings

| # | ID | Severity | Role | Title | Blast |
|---|---|---|---|---|---|
| 1 | ENG-001 | Critical | Engineering | Cache key collapses when all slot fields absent — wrong slice served silently | Multi-head slice requests may receive prior single-head cached G-code |
| 2 | UX-001 | Critical | UI/UX | No CSS for `kc-temp-chip` / `kc-send-temps` — chips render unstyled | Temperature feedback broken for all Snapmaker sends at all viewport sizes |
| 3 | DOC-001 | Critical | Docs | CHANGELOG has zero mention of Snapmaker U1 or multi-toolhead | Users and integrators have no release-note discovery path |
| 4 | DOC-002 | Critical | Docs | `api.md` missing `toolhead_count`, `toolhead_temps`, `nozzle_temp_c`, `filament_slot_N` | API consumers building against docs will miss all new fields |
| 5 | DOC-004 | Critical | Docs | Snapmaker U1 absent from `docs/supported-printers.md` | Snapmaker users will conclude the printer is unsupported |
| 6 | TEST-001 | Critical | Test | `resolve_filament_slots()` has zero test coverage including its error path | Wrong-profile key silently mislices with no failing test |
| 7 | TEST-002 | Critical | Test | `--filament-config` multi-head CLI branch never exercised | Multi-toolhead slices silently use `--load-filaments` (single-head path) with no test catching it |
| 8 | ENG-002 | Major | Engineering | 1-element `filaments` tuple takes the single-head CLI branch | Single-slot explicit assignment produces wrong slicer invocation |
| 9 | UX-002 | Major | UI/UX | "T1 Material" label is Marlin jargon with no contextual explanation | New users cannot understand what slot assignment means without prior knowledge |
| 10 | TEST-003 | Major | Test | No HTTP-layer test for `_handle_slice` multi-head POST body or tuple cache key | Webapp multi-head path entirely unverified at the integration layer |

---

## Cross-role findings

### CR-1: Multi-head webapp path entirely unverified (TEST-003 + QA-003 + Walkthrough)
- **Surfaced in:** TEST-003, QA-003, pre-audit walkthrough
- **What it is:** The `_handle_slice` handler's multi-head branch — `filament_slot_0..N-1` extraction, tuple cache key, `_slot_kw` dispatch — has no HTTP-layer test in `test_webapp.py` and no QA exercise. The walkthrough flagged this first; two roles independently confirmed it.
- **Why this matters:** The ENG-001 cache-key collapse lives in this exact path. A bug in the most critical new server-side logic has zero automated catching.
- **Recommended approach:** Add 3–4 parametrized `test_webapp.py` tests: (a) multi-head POST with `filament_slot_N` fields builds the tuple key; (b) empty slot fields fall back correctly (or are caught per ENG-001 fix); (c) same slots → cache hit; (d) different slots → cache miss.

### CR-2: Mock always returns 4 extruders — partial configurations untested (TEST-004 + QA-001/002)
- **Surfaced in:** TEST-004 (Major), QA-001 (Major), QA-002 (Minor)
- **What it is:** `mock_moonraker` unconditionally injects extruder1/2/3 whenever they appear in the query. The test named `test_capabilities_toolhead_count_at_least_1` claims to test the floor guard but the mock returns all 4, so the guard is never actually exercised. A Snapmaker U1 with fewer than 4 heads mounted would produce a shorter `toolhead_temps` tuple than `toolhead_count` indicates.
- **Recommended approach:** Add a `mock_moonraker` parameter (e.g. `extruder_count=4`) that controls how many extruder objects are returned. Use it to test 1-of-4 and 2-of-4 configurations.

### CR-3: Documentation absent across all surfaces — systemic miss (DOC-001/002/003/004/006)
- **Surfaced in:** All 5 Doc findings
- **What it is:** CHANGELOG, api.md, supported-printers.md, ARCHITECTURE.md — all five documentation layers were untouched by both feature commits. This is not a targeted omission; it is a process gap.
- **Recommended approach:** Treat CHANGELOG + api.md + supported-printers as required artifacts in the PR definition-of-done checklist (the project already has a DoD doc at `docs/dev/definition-of-done.md` — add these three).

---

## What's working

- **Engineering:** The inheritance design is clean and safe. MoonrakerConnector's `send()`, `job_status()`, `pause()`, `resume()`, and `cancel()` all work correctly on a Snapmaker U1 without modification — the `_EXTRUDER_OBJECTS` query and `toolhead_count` counting logic are correct. The `_slot_kw` backward-compat pattern correctly protects 9 existing `test_webapp.py` stubs from breaking.
- **UI/UX:** The conditional N-dropdown rendering (single-head vs multi-head) is architecturally correct and the `useEffect` reset on printer change is properly scoped to the right dependencies. The `materialSlots` state is correctly initialized and propagated to `postSlice`.
- **Documentation:** The `config/default.yaml` commented-out connector block is genuinely helpful — it shows users exactly what a real `snapmaker` connector entry looks like and which fields to fill in.
- **Tests:** The 14 Snapmaker connector tests are well-structured and cover the primary happy and failure paths (offline, wrong key, auth, idle temps, printing temps, all three control ops). The mock Moonraker is a high-quality adversarial HTTP server, not a stub.
- **Runtime QA:** Demo-mode runtime confirmed: `snapmaker_u1` appears in `/api/options` with `toolhead_count: 4` and correct build volume. Single-head extruder presence correctly produces `toolhead_count=1` and a length-1 `toolhead_temps` tuple. The 500-on-pause failure path correctly raises `ConnectorError`.

---

## This-sprint punch list (summary)

**Must-fix (Criticals):** 7 items
**Should-fix (high-leverage Majors):** 4 items

See `sprint-punchlist.md` for the full ordered list with sizes and owner hints.

Priority order: ENG-001 (cache collapse) → TEST-001+002 (slicer coverage) → UX-001 (CSS) → DOC batch (CHANGELOG + api.md + supported-printers) → TEST-003 (webapp HTTP tests) → ENG-002 (1-slot branch) → UX-002 (label copy).

---

## Next-sprint watchlist (summary)

- ENG-003: `toolhead_count` comes from static config, not live connector — needs product decision
- ENG-004: Null temp from disconnected extruder silently shortens tuple
- UX-003: No layout cap on N dropdowns (scrolls Slice button off-screen at N > 3)
- UX-004: Per-slot assignments invisible in post-slice summary
- DOC-006: ARCHITECTURE.md missing SnapmakerConnector entry

See `next-sprint-watchlist.md` for full entries.

---

## Blast-radius callouts

- **ENG-001 fix** — Changing the `any(slots)` collapse guard in `_handle_slice` will affect the cache-key computation for all multi-head slice requests. Existing single-head requests are unaffected (they never hit the multi-head branch). Regression-test the cache idempotency tests in `test_webapp.py` after the fix.
- **TEST-001/002 fix** — Adding coverage for `resolve_filament_slots` and the `--filament-config` branch will require either real OrcaSlicer profile fixture files or a mock slicer. The existing slicer tests use a mock binary — follow that pattern.
- **UX-001 fix** — Adding `kc-temp-chip` CSS is additive. No existing styles will conflict. Verify at both light and dark theme tokens.
- **DOC batch** — `api.md` update must document the exact field names (`filament_slot_0`, `filament_slot_1`, ..., `filament_slot_N-1`) as the frontend generates them — check the `postSlice` body construction in `api.ts:640–642` for the ground-truth naming.

---

## What we couldn't assess

- **QA / Runtime:** Live Snapmaker U1 device behavior, real Moonraker endpoint responses for all 4-extruder objects, and actual multi-toolhead OrcaSlicer invocation. All flagged in `05-qa-deepdive.md` and fold into #11 (Kim's hardware validation).
- **UI/UX:** Temperature chip visual appearance and the N-dropdown layout at high toolhead counts (no runtime Playwright available on this box). Flagged with specific CSS class names to inspect.

---

## Recommended next actions

1. **Fix ENG-001 first** — the cache-key collapse is a silent wrong-G-code bug. Fix the `any(slots)` guard so that a multi-head printer with empty/absent slot fields either raises a clear error or does not collapse to the single-head key. Add TEST-003 coverage in the same commit.
2. **Add slicer tests** (TEST-001 + TEST-002) — one test file with `resolve_filament_slots` happy path + missing-key error, and one test for the `--filament-config` CLI branch using the existing mock slicer pattern.
3. **Add CSS for kc-temp-chip** (UX-001) — two class rules, 10 lines of CSS. Unblock temperature feedback for all Snapmaker sends.
4. **Write the doc batch** (DOC-001/002/003/004) — CHANGELOG entry, api.md additions for 3 surfaces, supported-printers.md Snapmaker row. One commit, ~30 lines.
5. **Add multi-head printer connector type to DoD checklist** — so the next connector addition doesn't repeat this pattern.

---

## Reference — role deep-dives

- [`01-engineering-deepdive.md`](01-engineering-deepdive.md) — Principal Engineer
- [`02-uiux-deepdive.md`](02-uiux-deepdive.md) — Senior UI/UX Designer
- [`03-documentation-deepdive.md`](03-documentation-deepdive.md) — Technical Writer
- [`04-test-deepdive.md`](04-test-deepdive.md) — Test Engineer
- [`05-qa-deepdive.md`](05-qa-deepdive.md) — QA Engineer

---

*Audit conducted by the audit-team skill on 2026-06-16. Findings are balanced and evidence-based. Every Critical includes reproduction details and a blast-radius entry in the deep-dive.*
