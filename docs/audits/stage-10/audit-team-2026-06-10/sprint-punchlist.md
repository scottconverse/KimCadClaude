# Stage 10 gate — sprint punch list (36 items, priority-ordered)

Owner hint = the role that surfaced it. Status column updated as remediation lands; the
stage tags only at 0/0/0/0/0.

| # | Finding | Sev | Item | Owner hint |
|---|---|---|---|---|
| 1 | ENG-1001 | Major | Bambu busy gate fails CLOSED on UNKNOWN at send time; re-check state after upload before start (TOCTOU) | Engineering |
| 2 | QA-1001 | Major | Restore `log_error` to the terminal (stderr), keeping the QA-901 client-disconnect suppression | QA |
| 3 | ENG-1002 | Major | Defensive MQTT disconnect in `_session` teardown (lib's `mqtt_stop` never DISCONNECTs) | Engineering |
| 4 | UX-1001/DOC-1001 | Major | Venue-honest copy sweep: every "see Settings" / auth-hint string in the send flow + wizard points where help actually exists (config file + env var + connector-status detail surfaced) | UI/UX + Writer |
| 5 | UX-1002 | Major | The download outlives the wizard honestly: recap not "all set" mid-pull; Settings vision row pull-aware (shows the running download instead of suggesting a manual one) | UI/UX |
| 6 | TEST-1001 | Major | Real poll-lifecycle pins: a non-vacuous unmount test (fake timers installed BEFORE render), supersede/generation-guard test, wizard disposedRef test | Test |
| 7 | TEST-1002 | Major | Adversarial-body test: POST /api/model-pull with `{"model": "evil/whatever"}` → the named model is NOT pulled | Test |
| 8 | DOC-1002 | Major | ARCHITECTURE endpoint list gains /api/model-pull + /progress; frontend/README stage span updated | Writer |
| 9 | DOC-1003 | Major | Resolve the dangling G-code-viewer promise (CHANGELOG:132 + HANDOFF:43): explicit disposition in the Stage 10 CHANGELOG entry + watchlist | Writer |
| 10 | ENG-1003 | Minor | A failed status poll reschedules (with a bounded retry budget) instead of killing the live-follow chain | Engineering |
| 11 | ENG-1005 | Minor | FTP 530 / auth-shaped failures map to `AuthError` (reason `auth`) so the auth hint can fire for Bambu | Engineering |
| 12 | ENG-1006 | Minor | A pull stream that closes without Ollama's terminal `success` line is NOT marked done | Engineering |
| 13 | ENG-1004 | Minor | Zero-plate gets its own copy; plate matching case-insensitive to match `prove_gcode_3mf` | Engineering |
| 14 | ENG-1007 | Minor | `JOB` injection seam (per-handler-factory override) so tests/multi-instance don't share the singleton | Engineering |
| 15 | UX-1003 | Minor | ConfirmDialog restores focus to the invoking element on close | UI/UX |
| 16 | UX-1004 | Minor | Connection display names: prettify the config key ("bambu_p2s" → "Bambu P2S (bambu_p2s)") or label honestly | UI/UX |
| 17 | UX-1005 | Minor | The wizard model pill reads "Ready (vision downloading)" / not bare "Ready" while the card offers/runs the vision pull | UI/UX |
| 18 | UX-1006 | Minor | Post-send live line: the user's own job reads as progress ("Printing — your job"), not amber "Busy" | UI/UX |
| 19 | QA-1004 | Minor | CLI --send validates the connector BUILDS (not just name membership) before the multi-minute design run | QA |
| 20 | QA-1002 | Minor | Method contracts: POST on /progress + /api/designs → 405; GET /api/model-pull → 405; Allow headers truthful | QA |
| 21 | QA-1003 | Minor | Oversized-body guard on /api/model-pull (read+discard or 413 before reset); document the 413-vs-abort reality | QA |
| 22 | QA-1005 | Minor | README reason table gains `gate_failed` | QA |
| 23 | QA-1006 | Minor | CLI errors print to stderr (stdout stays clean for the report) | QA |
| 24 | DOC-1004 | Minor | default.yaml comment matches the picker's actual generic label | Writer |
| 25 | DOC-1005 | Minor | The in-app download named at the remaining manual-pull-only surfaces (README Setup, getting-started Step 2, ModelHealthPill, Settings design-model action) | Writer |
| 26 | DOC-1006 | Minor | Document `pip install "kimcad[bambu]"` (the >=2.6 floor) alongside the bare package name | Writer |
| 27 | TEST-1003 | Minor | FakePrinter mirrors the real lib's 0.0-when-unreported nozzle; connector treats 0.0 as unknown (None) | Test |
| 28 | TEST-1004 | Minor | Pin `bambulabs-api` in requirements.lock (CI then cross-checks the fake against the real package forever) | Test |
| 29 | TEST-1005 | Minor | `_locked` methods assert `self.lock.locked()` — every test becomes a lock-discipline detector | Test |
| 30 | TEST-1006 | Minor | A named (timeout-bounded) deadlock regression test + concurrent double-start test | Test |
| 31 | ENG-1008 | Nit | /api/connectors comment matches the code (or the code matches the comment) | Engineering |
| 32 | ENG-1009 | Nit | The fallback model names defined once | Engineering |
| 33 | UX-1007 | Nit | The export card's connection line doesn't read green "Ready" directly above a gate-fail explanation | UI/UX |
| 34 | DOC-1007 | Nit | docs/README index gains cadquery-backend.md | Writer |
| 35 | DOC-1008 | Nit | Troubleshooting's bambulabs-api heading matches the user-facing wording | Writer |
| 36 | — | — | Tag-time package (CHANGELOG Stage 10 entry incl. #9, ROADMAP EXIT MET, README status ¶, HANDOFF resume box, RUN-LEDGER row) | Writer |
