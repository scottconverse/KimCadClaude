# Executive Audit — KimCad 0.9.0b4 (+ restored UI)

**Date:** 2026-06-17
**Build:** `0.9.0b4`, `origin/main` @ `356867d` (b4 rollback `c8e9f44` + restored post-b4 UI: Kim avatar, designer pass). Snapmaker fully removed.
**Gate state:** GREEN — pytest **1600 passed** (incl. the real OrcaSlicer live matrix), vitest **396 passed** (32 files), build-repro clean.
**Team:** Principal Engineer · Senior UI/UX Designer · Technical Writer · Test Engineer · QA Engineer — all 5 roles, full depth.
**Deep-dives:** [01-engineering](01-engineering-deepdive.md) · [02-uiux](02-uiux-deepdive.md) · [03-documentation](03-documentation-deepdive.md) · [04-test](04-test-deepdive.md) · [05-qa](05-qa-deepdive.md)
**Companion walkthrough:** [../walkthrough-b4-2026-06-16/WALKTHROUGH.md](../walkthrough-b4-2026-06-16/WALKTHROUGH.md)

---

## Executive summary

KimCad b4 (with the restored UI) is a **genuinely solid, ship-quality beta with no Blockers and no Criticals from any of the five roles.** The two highest-risk surfaces — the untrusted-LLM-code geometry sandbox and the no-auth loopback trust boundary — held against live adversarial probing (13 CadQuery + 9 OpenSCAD escape payloads all blocked; CSRF token + gate-fail enforcement verified server-side). The b5 false-green failure class is **structurally extinct**: the gate runs the real OrcaSlicer/OpenSCAD/CadQuery/Chromium binaries and proves the slice by opening the `.3mf` and requiring motion G-code — both the Test and QA roles independently produced real motion-bearing `.3mf`s (10,987 and 21,172 G-code lines). The restored UI is intact: the avatar renders in both locations (incl. dark mode), the Settings section-nav and wizard cloud disclosure work, the SPA rebuilt reproducibly, and the critical design→gate→slice→download path is live-proven end to end. The findings are **drift, polish, and defense-in-depth** — no shipped-broken behavior.

## Severity roll-up

| Role | Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|---|
| Principal Engineer | 0 | 0 | 3 | 6 | 5 |
| UI/UX Designer | 0 | 0 | 3 | 5 | 4 |
| Technical Writer | 0 | 0 | 4 | 5 | 3 |
| Test Engineer | 0 | 0 | 2 | 3 | 2 |
| QA Engineer | 0 | 0 | 0 | 3 | 2 |
| **Total (raw)** | **0** | **0** | **12** | **22** | **16** |

(Three findings are cross-listed in two roles — ENG-010≈UX-001 connector badge, ENG-011≈UX-003 aria-current, ENG-008≈UX-005 BOM — so ~47 unique issues.)

## Top 10 findings (all roles, by severity)

| # | ID | Sev | Dimension | One-liner |
|---|---|---|---|---|
| 1 | ENG-001 | Major | Security | Cloud OpenRouter `base_url` isn't scheme/host-validated — a tampered `config/local.yaml` can exfiltrate the saved API key (not UI-reachable). |
| 2 | ENG-004 | Major | Security/Arch | Untrusted-code sandbox has no OS-level confinement; layer-1 AST sanitizer is the whole wall (honest, but the next security investment). → **watchlist** |
| 3 | ENG-006 | Major | Performance | Every mesh/gcode/STEP download `read_bytes()` the whole file into memory behind a 200 MiB ceiling — RSS spike risk under concurrency. |
| 4 | UX-001 | Major | Copy | Export connector badge "mock · Ready · simulated" leaks the raw key and reads as "the slice is fake." |
| 5 | UX-002 | Major | A11y | Inspector tablist has no arrow-key navigation and all tabs `tabindex=0` — breaks the WAI-ARIA Tabs contract. |
| 6 | UX-003 | Major | A11y/IA | Settings section-nav marks a whole group `aria-current` (two items lit) and 9 sub-links share only 4 anchors. |
| 7 | DOC-001 | Major | Accuracy | ROADMAP + ARCHITECTURE still call `gemma4:e4b` the default planner; the real default is `qwen2.5:7b`. |
| 8 | DOC-002 | Major | Accuracy/Mktg | README + landing promise a "signed attestation"; the build is explicitly unsigned (checksum + manifest only). |
| 9 | DOC-003 | Major | Accuracy | Model-download size is stated 4 ways (4.7/8/9/13 GB) across docs. |
| 10 | DOC-004 | Major | Completeness | FAQ Q12 omits the Duet and Marlin connectors (ships 6, FAQ lists 4). |
| — | TEST-101/102 | Major | Coverage/CI | Real LLM→SCAD→render→slice chain never run e2e by the gate; the one real-LLM test is unmarked `live`. |

## What's working (specific, credited)

- **Sandbox + trust boundary hold under live attack.** Every escape payload blocked; fail-closed gate→slice/send enforced server-side and re-derived on import/reopen; CSRF token constant-time-compared; zero tracebacks/500s/credential leaks across the adversarial QA session.
- **The b5 lesson is institutionalized.** `KIMCAD_CI_STRICT` fails the build on *any* skip on the provisioned box; a dedicated `-m live … 0 skipped` step re-runs the real-tool contract; `prove_gcode_3mf` proves motion G-code, not a command string. The live subset ran 110 passed / 0 skipped.
- **Dependency surface clean** — `pip-audit` zero CVEs, current pins.
- **UX honesty + state coverage** — on-device loading narrates its own slowness with an elapsed timer + Cancel; every reachable view has a designed empty/loading/error state; AA contrast in both themes; focus-trapped modals; reduced-motion respected.
- **Docs are large, cross-linked, persona-aware, and honest** about beta limits; all headline counts (29 printers / 86 families / 6 connectors / 0.9.0b4) are code-true; zero Snapmaker leak into any live doc.

## Cross-cutting themes

1. **The `gemma4:e4b`→`qwen2.5:7b` default-planner switch was never fully propagated** — surfaces as DOC-001 (ROADMAP/ARCHITECTURE), DOC-005 (config comment), and TEST-105 (a frontend test asserting the stale name). One coordinated fix.
2. **"Config-as-trusted" is the one soft spot** in an otherwise rigorously-validated system (ENG-001, ENG-002): values from `config/local.yaml` reach network/subprocess sinks without the assertion every runtime input gets.
3. **ARIA-present-but-contract-not-honored** on two custom widgets (UX-002 tablist, UX-003 section-nav) — a finishing-discipline gap, not systemic neglect.
4. **Memory-resident I/O** (ENG-006): the whole-file read pattern repeated across every download path — Minor each, Major as a pattern.

## Blast-radius notes (fixes that ripple)

- **UX-001 connector badge:** the connector name + label feed `ConnectorStatus`, `SendPanel`, and `ConnectionsCard` — centralize the `displayName()` prettification so it's fixed once and every future connector key is covered. Update `ConnectorStatus.test.tsx` / `connectorStatus.test.ts`.
- **DOC-001 model name:** `gemma4:e4b` is still a *real* role (the non-China fallback / vision host) — do NOT blind find-replace; change only the "default planner" assertions.
- **UX-003 section-nav:** per-item anchors require new ids on the Settings cards + updating the IntersectionObserver + `SettingsPanel.test.tsx`; keep mobile group labels visible (UX-006 resolves together).
- **ENG-006 streaming:** changes the `_send` contract (Content-Length from `stat()`), low risk; keep the small-file fast path.
- **ENG-001 cloud URL allow-list:** needs a documented escape hatch for advanced users who deliberately add a custom endpoint.

## Verdict

**Ship-quality b4.** No Blocker/Critical. The remediation is a punch-list of drift/polish/defense-in-depth (see [sprint-punchlist.md](sprint-punchlist.md)); one Major (ENG-004 OS sandbox) is a genuine forward-looking architectural investment (see [next-sprint-watchlist.md](next-sprint-watchlist.md)). Remediating the punch-list to 0/0/0/0/0 is in progress this sprint.
