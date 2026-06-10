# Stage 10 stage gate — Executive audit (audit-team, 2026-06-10)

**Scope:** the Stage 10 diff (`253b08c..d9495a8` on `main`) — Slice 10.1 (DesignRegistry alias
flattening), Slice 10.2 (SendPanel direct-print UI), Slice 10.3 (Bambu-native connector,
mock-tested), Slice 10.4 (wizard model downloads + Settings vision row). All five roles,
balanced posture, writer audit-only. Deep-dives: `01`–`05` in this directory.

**Verdict at audit time: 0 Blocker / 0 Critical / 10 Major / 21 Minor / 5 Nit (36 findings).**
Remediation to 0/0/0/0/0 follows per the project's standing rule; the remediation record is
appended to this file when complete.

## Executive summary

Stage 10 shipped the direct-print loop end-to-end — the SendPanel's trust rules held under
live abuse, the Bambu connector's mock contract proved substantially faithful to the real
library, the registry flattening left zero lock-discipline violations, and the model-download
surface survived adversarial bodies and a 12-way parallel POST storm with perfect idempotency.
What the gate found wrong clusters in three honest patterns: (1) **capabilities shipped ahead
of their management surfaces** — six copy strings send users to a Settings section that
doesn't exist, and the in-app download has no life outside the one-shot wizard; (2)
**real-hardware edges the FakePrinter structurally can't exhibit** — the busy gate fails open
on an UNKNOWN state read, sessions never send MQTT DISCONNECT, wrong credentials never map to
`auth`; and (3) **diagnosability gaps at the failure boundary** — every 500 promises terminal
detail the silenced `log_error` never writes, and one poll-lifecycle test was proven vacuous.
Nothing blocks the stage; the hardware-edge Majors matter before Kim's beta, not before this
tag — and all 36 are being fixed now regardless.

## Severity roll-up

| Role | Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|---|
| 01 Engineering | 0 | 0 | 2 | 5 | 2 |
| 02 UI/UX | 0 | 0 | 2 | 4 | 1 |
| 03 Documentation | 0 | 0 | 3 | 3 | 2 |
| 04 Test | 0 | 0 | 2 | 4 | 0 |
| 05 QA | 0 | 0 | 1 | 5 | 0 |
| **Total** | **0** | **0** | **10** | **21** | **5** |

## Top 10 findings (cross-role, by severity then blast radius)

1. **UX-1001 / DOC-1001 (Major, merged)** — Every setup pointer in the send flow dead-ends:
   "see Settings" names a connections section that doesn't exist; the `auth` hint names a key
   field no UI has; the server's per-piece diagnosis (`/api/connector-status` notes) is
   unreachable in-app. *The flagship feature's only signposts point at nothing.*
2. **ENG-1001 (Major)** — The Bambu busy gate fails OPEN on an UNKNOWN state read at send
   time (the real lib's ready-flag flips on the FIRST MQTT message, before state lands) +
   an unchecked TOCTOU across the upload: a running job can get a second job started over it
   on real hardware — the one finding that can violate a stated safety invariant.
3. **ENG-1002 (Major)** — `mqtt_stop` in bambulabs-api 2.6.6 never sends DISCONNECT
   (verified in lib source); per-request sessions + 5 s status polling ≈ 120 TLS+MQTT
   handshakes per followed job against connection-limited Bambu firmware.
4. **QA-1001 (Major)** — the `log_message` override silences stdlib `log_error` too: every
   500 tells the browser "the terminal has the detail" and the terminal gets 0 bytes
   (runtime-proven). Failure-path diagnosability broken exactly where bug reports are born.
5. **UX-1002 (Major)** — the in-app download has no life outside the one-shot wizard:
   close it mid-pull and the recap says "You're all set", Settings' vision row contradicts
   the running pull and suggests a competing manual one.
6. **TEST-1001 (Major)** — the SendPanel "unmount stops the poll chain" test is empirically
   VACUOUS (passes with the cleanup deleted — fake timers installed after the real timer was
   scheduled can never fire it); the generation-guard and `disposedRef` fixes are unpinned.
7. **TEST-1002 (Major)** — no adversarial-body test pins the model-pull trust rule; a future
   `data.get("model")` convenience read would pass all 970 tests.
8. **DOC-1002 (Major)** — ARCHITECTURE.md (declared "the authoritative endpoint list") omits
   both new Stage 10 endpoints; frontend/README's stage span is stale.
9. **DOC-1003 (Major)** — CHANGELOG:132's standing promise of a "G-code toolpath/layer viewer
   … scheduled for Stage 10's direct-print UI" dangles — Stage 10 is complete without it and
   ROADMAP never scoped it; the tag-time entry must resolve it explicitly.
10. **ENG-1005 + UX-1006 (Minor pair, hardware-facing)** — a wrong access code surfaces as
    `error`/`offline` (never `auth`, so the auth hint can't fire), and the post-send live
    line reads amber "Busy — printing" for the user's OWN job.

## What's working well (specific, verified)

- **The trust architecture held everywhere it was attacked.** Confirm-is-the-POST,
  simulated-send-narrated-as-test, gate-failed refusals server-side, the fixed pull list
  under attacker-named bodies and parallel storms, `/api/send` input handling airtight,
  zero tracebacks across ~200 abusive requests (QA, live).
- **The FakePrinter contract is substantially the right contract** — the "226" FTP proof,
  None-on-swallowed-failure, the exact 7 GcodeState members, `int|str|None` percentage all
  match bambulabs-api 2.6.6 (Test, introspected). The 10.3 audit-lite's upload-proof fix is
  load-bearing: the lib genuinely swallows mid-transfer failures.
- **Slice 10.1's flattening is complete and clean** — systematic grep found zero per-design
  `reg.*` access outside `reg.lock` (Engineering).
- **Honesty discipline:** the mock-transport caveat is consistent at every Bambu mention;
  troubleshooting's exact-string contract verified against code; simulated sends never
  narrated as prints; GB sizes round up from real figures (Writer).
- **A11y and responsiveness:** the coarse SR live region works as designed, 375 px clean,
  all new text AA (UI/UX, live).

## This-sprint punch list

See `sprint-punchlist.md` — all 36 items, priority-ordered with owner hints. Being executed
now (the stage tags only at 0/0/0/0/0).

## Next-sprint watchlist

See `next-sprint-watchlist.md` — the Stage 11 items (a real connections Settings surface,
hardware-contact protocol for the Bambu edges, installer disk math, JOB singleton if the
server ever multi-instances).

## Blast-radius notes

- **The send-flow copy pass (UX-1001/DOC-1001)** touches SendPanel, FirstRunWizard, README,
  troubleshooting, and default.yaml comments together — they quote each other; change them
  as one sweep or they'll drift apart again.
- **Busy-gate fail-closed (ENG-1001)** changes UNKNOWN-at-send from "send anyway" to a typed
  refusal — the SendPanel soft-failure surface already renders `busy` correctly, but the
  FakePrinter tests asserting the UNKNOWN→error STATUS map must not be confused with the
  send-path refusal (different code paths).
- **`log_error` restoration (QA-1001)** will surface previously-invisible noise; pair it
  with the existing client-disconnect suppression (QA-901, Stage 9) so the fix doesn't
  reintroduce traceback spam.
- **Method-contract fixes (QA-1002)** alter 404→405 on two routes — no known client sends
  those methods, but MCP/CLI integrators read the `Allow` header; fix the header in the
  same change.

---

## Remediation record (all 36 → fixed, same day)

| Finding | Fix |
|---|---|
| ENG-1001 | Busy gate fails CLOSED: only IDLE/FINISH may print; UNKNOWN waits briefly for the state push then refuses typed `busy`; FAILED refuses with the on-printer fix; the state is RE-CHECKED after the upload (TOCTOU). |
| ENG-1002 | `_session` teardown reaches the paho client and sends a real MQTT DISCONNECT (the lib's `mqtt_stop` is `loop_stop()` only). |
| ENG-1003 | A failed status poll reschedules on the same bounded budget (pinned by a fake-timers test). |
| ENG-1004 | Plate matching case-insensitive; zero plates gets its own honest message (pinned). |
| ENG-1005 | FTPS 530/auth-shaped upload failures map to `AuthError` (reason `auth`) with the on-printer access-code fix. |
| ENG-1006 | "done" requires Ollama's terminal `success` line — a cleanly-closed mid-pull stream is an error, not a ✓. |
| ENG-1007 | `make_handler(pull_job=…)` injection seam; the module global stays the per-process default. |
| ENG-1008 | `/api/connectors` returns the first CONFIGURED connector as default (the comment's long-standing claim, now true with unconfigured templates shipped). |
| ENG-1009 | `DEFAULT_CHAT_MODEL`/`DEFAULT_VISION_MODEL` defined once in config.py. |
| QA-1001 | `log_error` restored to stderr (`[kimcad]` prefix); request chatter stays quiet; QA-901's disconnect suppression intact. |
| QA-1002 | `/api/model-pull/progress` + `/api/designs` POST → 405; GET `/api/model-pull` + `/api/design` → 405 `Allow: POST`; `_method_not_allowed` computes a TRUTHFUL per-path Allow (pinned). |
| QA-1003 | `/api/model-pull` drains a small body, 413s an absurd one (pinned). |
| QA-1004 | CLI `--send` BUILDS the connector before the design run — a config gap fails in <1s with the connector's own message (pinned). |
| QA-1005 | README reason table gains `gate_failed`. |
| QA-1006 | CLI error prints routed to stderr (tests updated to pin the new contract). |
| UX-1001/DOC-1001 | Venue-honest sweep: every "see Settings" pointer replaced (the venue is `config\default.yaml` + env vars); the picker now fetches and SHOWS the server's per-piece diagnosis for the selected unconfigured connection (pinned); auth hint names the env-var venue. |
| UX-1002 | The download outlives the wizard honestly: recap shows the in-flight pull (and the still-missing state); Settings' vision row is pull-aware ("downloading now (NN%)" — never a competing manual-pull suggestion; pinned). |
| UX-1003 | ConfirmDialog restores focus to the opener on close (isConnected-guarded). |
| UX-1004 | `displayName()` presents config keys in the product register ("Bambu P2S"); the wire value stays the exact key (pinned). |
| UX-1005 | The wizard model pill reads "Ready — words only" while the vision model is missing. |
| UX-1006 | Post-send, `printing` is narrated as "Printing — your job is running" (ok tone), never amber "Busy" (pinned). |
| UX-1007 | The connection pill sits out the gate-failed export card. |
| DOC-1002 | ARCHITECTURE gains the Stage 10 additions paragraph (both pull endpoints + SendPanel + Bambu); frontend/README span updated to 5–10. |
| DOC-1003 | The G-code-viewer promise resolved as deferred-not-dropped in the CHANGELOG Stage 10 entry + resolution markers at HANDOFF:44 and the ledger row. |
| DOC-1004 | default.yaml comment matches the picker's actual behavior (generic label + per-piece note when selected). |
| DOC-1005 | The in-app download named at README Setup, getting-started Step 2, ModelHealthPill (both messages), and Settings' design-model action. |
| DOC-1006 | `pip install "kimcad[bambu]"` documented alongside the bare package (troubleshooting + CHANGELOG). |
| DOC-1007 | docs/README index gains `cadquery-backend.md`. |
| DOC-1008 | Troubleshooting's Bambu heading de-quoted to match the user-facing wording. |
| TEST-1001 | The vacuous unmount test rebuilt with fake timers installed BEFORE render and a liveness proof (a 5s tick observably polls) — plus new supersede/generation-guard and wizard-disposedRef pins. |
| TEST-1002 | Adversarial-body pin: a POST naming `evil/backdoored:latest` changes nothing — config's models, nothing else. |
| TEST-1003 | FakePrinter parity noted; the connector treats the real lib's 0.0-when-unreported nozzle as unknown (None). |
| TEST-1004 | `bambulabs-api==2.6.6` (+ paho-mqtt, pillow) pinned in requirements.lock — CI now cross-checks the fake against the real package on every run (pip-audit clean). |
| TEST-1005 | `_locked` methods assert `lock.locked()` in DesignRegistry AND ModelPullJob — all 970+ tests are lock-discipline detectors now. |
| TEST-1006 | A bounded 8-thread concurrent-start test (exactly one pull runs; a regression deadlock fails red, never hangs the suite). |

**Re-verification after remediation:** recorded in the stage-10 tag commit (ruff clean, full
pytest, tsc clean, full vitest, SPA rebuilt, live demo spot-checks of the changed surfaces).