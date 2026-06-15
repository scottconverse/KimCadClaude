# Sprint Punch List — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**For sprint ending:** before the 0.9.0b2 beta is handed to the first external tester

Actionable fixes for the current sprint. Each item: ID, severity, owner hint (role), one-line fix, size (S/M/L). Full detail is in the matching deep-dive.

> **Note:** all remediation is currently **held** pending the owner's go-ahead. This list is the plan, not work-in-progress.

---

## Must-fix (Blockers + Criticals)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | DOC-001 | Blocker | Docs | Fix `docs/install-guide.md:16` so the `Get-FileHash` command names `KimCad-Setup-0.9.0b2.exe` (or a `<version>` placeholder); bump the front-door version markers (README badge/CTA/filename L5/14/30, USER-MANUAL banner L15, definition-of-done L47) from `0.9.0b1` → `0.9.0b2` | S |
| 2 | UX-001 / TEST-001 / QA-001 / ENG-002 | Critical | UX+Test+QA+Eng | Curate the 3 landing example chips (and the textarea placeholder) to prompts the **default** model reliably builds (dimensioned, template-mapped), AND broaden `templates.py:323-331` alias matching so natural phrasing hits existing families; add a real-model CI canary that plans each shipped chip | M–L |
| 3 | QA-002 | Critical | QA | Validate the generated OpenSCAD source is real code before spending the render budget — fail fast (clear error) when codegen emits non-code (literal `coaster`, bare `//`); see `pipeline.py` render path | M |
| 4 | DOC-002 / ENG-003 | Critical | Docs+Eng | Rewrite `ARCHITECTURE.md:81/83/91` to match the **removed** LLM-CadQuery fallback (4 LLM jobs not 5; OpenSCAD-only codegen; `cadquery_templates.py` is the trusted STEP-twin engine) | S |
| 5 | DOC-003 | Critical | Docs | Add the 3 shipped b2 subsystems to `ARCHITECTURE.md`: Duet/Marlin connectors + mocks (module map + factory list), the per-boot session-token guard (web-layer trust boundary), macOS/Linux paths + shell degradation | S–M |

---

## Should-fix (high-leverage Majors)

| # | ID | Severity | Role | What to do | Size |
|---|---|---|---|---|---|
| 1 | UX-002 | Major | UX | When there is no current part (incl. after a failed design), disable/hide the geometric refine chips ("Make it bigger/taller/Thicker walls") so a click can't fire another ~2-min likely-failure (`ChatPanel.tsx:137`, `App.tsx:448`) | S |
| 2 | TEST-002 | Major | Test | Extend `test_version_single_source` to scan README + docs for stale version literals (would have caught the drift); add the real-model chip canary from must-fix #2 | S |
| 3 | ENG-001 | Major | Eng | Stop shipping the `bambu` extra's heavy deps (bottle, paho-mqtt, pythonnet) to every installer user via `requirements.lock`; make it truly optional and add `pyserial`/Marlin-USB install guidance symmetrically | M |
| 4 | DOC-004 | Major | Docs | (Part of the approved manual rebuild) cover Duet/Marlin, the 29-printer catalog, the session-token guard, and macOS/Linux across all 3 manual audiences; reconcile "about 90" → 86 families (also `FAQ.md:142`) | M |
| 5 | DOC-005 | Major | Docs | (Approved) build `docs/index.html` marketing landing page — honest value prop, quick-start, architecture section, links to installer/manual/repo — and enable GitHub Pages | M–L |
| 6 | UX-003 | Major | UX | Add a keyboard path to orbit/zoom/measure the 3D viewport (WCAG 2.1.1) | M |

---

## Suggested sequencing

1. **DOC-001 first** — it's a ~10-minute Blocker and the only thing that strictly gates handing the build to a tester (the broken integrity command + wrong version). Pair it with TEST-002 so the fix is locked in by a test.
2. **The default-model cluster (must-fix #2 + #3, should-fix #1)** next — it's the highest-leverage user-facing work. Do the chip curation + template-match broadening + the codegen-validation together, behind the new CI canary, because they share the same pipeline/Landing surface (one coordinated change, per the exec's blast-radius callout).
3. **The ARCHITECTURE.md pass (must-fix #4 + #5)** is cheap and independent — batch it any time.
4. **ENG-001** before cutting the *next* installer (it changes the staged dependency set).
5. **DOC-004 / DOC-005** are the larger approved doc builds — run them after the must-fixes land so they describe the corrected state.

---

## Items deferred to next sprint

- **ENG-004** — `/api/design` concurrency cap / async — structural; only acute under `--allow-remote` (not the default). → watchlist.
- **TEST-003** — live-Ollama error-path tests — needs a CI Ollama lane. → watchlist.
- **Default-model strategy** (stronger default model vs cloud-default) — product decision, not a code fix. → watchlist.
- **#11** real-hardware connector validation — already parked (hardware-blocked).

---

## Sign-off gate

- [ ] DOC-001 fixed and verified (the published `Get-FileHash` command matches the real asset).
- [ ] Default-model cluster fixed AND a real-model CI canary added (so it can't regress).
- [ ] ARCHITECTURE.md no longer describes the removed fallback and lists the 3 b2 subsystems.
- [ ] Regression pass on any code touched (blast radius per deep-dives).
- [ ] Docs updated for any user-facing / API change.

---

*Generated from the audit-team skill. Full detail for every ID is in the matching role deep-dive.*
