# Sprint Punch-List — KimCad b4+UI audit (2026-06-17)

Fix-this-sprint items, by severity then area. Owner-hint = the role that surfaced it. Target: 0/0/0/0/0.

## Major

| ID | Area | Fix | Files |
|---|---|---|---|
| ENG-001 | Security | Validate cloud `base_url` (require https + host allow-list: openrouter.ai, deepseek host) when a saved key would be sent; documented escape hatch for custom endpoints. | `llm_provider.py`, `config.py` (+ test) |
| ENG-006 | Performance | Stream mesh/gcode/STEP downloads (`stat()` + `shutil.copyfileobj` in chunks); keep small-file fast path. | `webapp.py` `_serve_mesh/_serve_gcode/_serve_step` |
| UX-001 / ENG-010 | Copy | Run connector name through `displayName()` (mock → "Built-in preview · no printer connected"); reword "simulated" so it describes the connection, not the slice. | `ConnectorStatus.tsx`, `connectorStatus.ts` (+ tests) |
| UX-002 | A11y | Implement APG Tabs keyboard model on the Inspector tablist: roving tabindex + ArrowL/R (wrap) + Home/End; selection follows focus. | `RightPanel.tsx` (+ `RightPanel.test.tsx`) |
| UX-003 / ENG-011 | A11y/IA | Per-item Settings anchors (unique ids per card), observe per-item, single `aria-current`; keep mobile group labels visible (resolves UX-006). | `SettingsPanel.tsx`, `styles.css` (+ test) |
| DOC-001 / DOC-005 | Docs | Change "default planner = gemma4:e4b" → `qwen2.5:7b` in ROADMAP + ARCHITECTURE prose + config comment; keep gemma's fallback/vision-host role intact. | `ROADMAP.md`, `ARCHITECTURE.md`, `config/default.yaml` |
| DOC-002 | Docs | Replace "signed attestation" with "SHA-256 checksums + build manifest (unsigned_build)"; add a verify-the-attestation subsection to install-guide. | `README.md`, `docs/index.html`, `docs/install-guide.md` |
| DOC-003 / DOC-007 / DOC-009 | Docs | Canonical: download ≈ 8 GB (4.7 chat + 3 vision); free disk ≈ 13–20 GB. Fix FAQ/README/install-guide/troubleshooting/USER-MANUAL/getting-started. | (6 docs) |
| DOC-004 | Docs | Add Duet + Marlin to FAQ Q12. | `docs/FAQ.md` |
| TEST-101 | Tests | Add one `@pytest.mark.live` pipeline test: real model → generate_openscad → render → watertight → slice → `prove_gcode_3mf` (1–2 prompts). | `tests/test_pipeline.py` |
| TEST-102 | CI | Mark `test_landing_examples` real-LLM test `@pytest.mark.live` so the live-subset step guards it; add an Ollama probe to ci.yml. | `tests/test_landing_examples.py`, `.github/workflows/ci.yml` |

## Minor

| ID | Area | Fix |
|---|---|---|
| ENG-002 | Security | `binary_path` assert resolved target `is_file()`; warn if a configured binary escapes the install root. |
| ENG-003 | Correctness | Duet `status()`/`job_status()` → `try/finally _disconnect()` so a mid-poll URLError/OSError can't leak a board session. |
| ENG-005 | Reliability | Surface a one-time UI notice when a key save falls back from keyring to file storage (data already in `key_storage()`). |
| ENG-007 | Correctness | Native (default Ollama) plan path: probe `_server_reachable()` before the first attempt / set a short connect timeout. |
| ENG-008 / UX-005 | Hygiene | Strip the UTF-8 BOM from `FirstRunWizard.tsx` + `SettingsPanel.tsx`. |
| ENG-009 | Correctness | `job_status()` clean fixed `detail` (mirror the QA-003 `status()` treatment) in marlin/octoprint. |
| UX-004 | Perf/Asset | Ship a 64×64 optimized avatar (replace the 1.27 MB / 1254² PNG); update both committed copies via build. |
| UX-006 | Responsive | Keep Settings section-nav group headings visible on mobile (resolved with UX-003). |
| UX-007 | State | Investigate blank thumbnails (`has_thumb:true` but empty) + add a designed thumbnail fallback (object-type icon + name). |
| TEST-103 | Coverage | Document `build_printer_catalog.py --verify` as required on profile/catalog edits + a hygiene test asserting the proof-of-record is newer than the catalog YAML. |
| TEST-105 | Quality | Rename the FirstRunWizard model test to what it checks; fix the stale `gemma4:e4b` comment → `qwen2.5:7b`; add a case exercising the real `qwen2.5:7b` fallback. |
| QA-002 | API | Trim the unknown-printer slice error (bad key + pointer to `/api/options`) instead of inlining the whole catalog. |
| QA-003 | API | Distinguish "no parameter values supplied" from "values present but unusable/unknown keys" in `/api/render` 400. |

## Nit

| ID | Fix |
|---|---|
| ENG-012 | Clip raw upstream error text before display in `model_pull` (use the existing `[:300]` pattern). |
| ENG-013 | Bambu private-attr disconnect: debug-log when the private path raises + a test asserting it's reached against the fake. |
| DOC-006 | guide-sliders: note the example list is "one of 86 families." |
| DOC-008 | ROADMAP: add a one-line "all stages DONE/tagged; retained as the executed plan" banner; past-tense the Size/Needs lines. |
| DOC-010 | (Optional) standardize "~65 brand / 1,400+ machine" phrasing. |
| DOC-011 | Spot-check getting-started "~200 MB" fetch-tools figure against the pins. |
| TEST-106 | `rm -rf build/` + prune orphaned snapmaker `.pyc`; optional hygiene test. |
| TEST-107 | (Note only) lru-cached default-model probe — leave unless model-lifecycle tests join the same process. |
| UX-011 | "Saved" status chip → 44px hit area (padding) or make non-interactive. |
| QA-001 / QA-005 | Token-on POST-to-GET-only: prefer 405 over 403 for known GET-only paths, and emit the JSON error envelope (not empty body) in the token-off 405. |

## Verify-only (no code change unless confirmed shipped)

- **UX-008** — the stray `demo-gohello` design appears in the *isolated test home* used by the audits; confirm the app does not seed demo entries into a real user's library. If purely local test residue → no change.

## Deferred to watchlist (with reason)

- **ENG-004** (OS-level sandbox confinement) and **UX-009** (restyle Kim's avatar mark) → [next-sprint-watchlist.md](next-sprint-watchlist.md). ENG-004 is a substantial platform-specific sub-project (Job Object / restricted token + test matrix) the auditor frames as tracked hardening; UX-009 is a subjective brand decision (Scott's call).
- **QA-004, UX-010, UX-012, TEST-107** are credits / no-action notes.
