# Executive Audit — KimCad 0.9.0b2

**Audit date:** 2026-06-14
**Audit scope:** Full — entire repository at `C:\Users\scott\Desktop\Code\kimcadclaude` (commit `f92c2b1`, tag `v0.9.0b2`)
**Posture:** Balanced
**Roles engaged:** Principal Engineer · Senior UI/UX Designer · Technical Writer · Test Engineer · QA Engineer (all 5)

---

## Executive summary

KimCad 0.9.0b2 is an unusually **well-engineered and well-hardened** local-first product: the server shrugged off ~30 adversarial inputs with zero 500s and zero leaked tracebacks, the connector mocks are genuinely adversarial, the design system is AA-contrast- and focus-guarded, and `ruff`/`pip-audit` are clean. **It ships safely.** But two themes keep every reader from a clean bill of health. First — and surfaced independently by four of the five roles — **the default local model (`gemma4:e4b`) cannot reliably fulfill the product's own promises**: it fails ~2–3 of the 3 example prompts the landing page itself suggests (100–160 s each), sometimes emitting non-code as OpenSCAD source, and the demo-only e2e suite is structurally blind to it. Second, the **documentation front door is a release behind and, in one spot, actively broken**: the install guide's SHA-256 verify command names an installer the 0.9.0b2 release doesn't publish, so the only integrity check on an unsigned binary fails. Neither is a code defect — the wiring is sound — but both shape a new beta tester's first hour. **Single most important takeaway:** before pointing Kim at the repo, fix the broken checksum command and curate the example prompts (or strengthen the default planner); everything else is polish.

---

## Readiness at a glance

| Dimension | Status | Summary |
|---|---|---|
| Architecture & code | Solid | Clean module boundaries, real security controls; only Majors (dependency packaging, sync request thread) — no Blockers/Criticals |
| UI / UX | Concerns | Beautiful, accessible UI; but the featured first action fails on the default model and the failure path can loop |
| Documentation | Serious issues | 1 Blocker (broken checksum-verify), 2 Critical (ARCHITECTURE.md drift); front-door docs a release behind |
| Test suite | Concerns | Large, strict, honest gate — but structurally blind to real-model quality and to README version drift |
| Runtime QA | Solid (with one product caveat) | Server hardening is exceptional; every functional failure traced to the default model's output, not KimCad's code |

---

## Severity roll-up

> Counts are summed across all five role deep-dives (per-role stated counts). Several Criticals/Majors share one root cause — see Cross-role findings; the de-duplicated unique-issue picture is smaller than the raw total.

| Severity | Count | What it means |
|---|---|---|
| Blocker | 1 | Cannot ship as-is to testers (DOC-001 — broken integrity-verify command) |
| Critical | 5 | Fix this sprint |
| Major | 12 | Fix this or next sprint |
| Minor | 22 | Batch for hygiene |
| Nit | 12 | Preference-level |
| **Total** | **~52** | across 5 roles (≈30 unique after cross-role dedup) |

---

## Top 10 findings

| # | ID | Severity | Role | Title | Blast |
|---|---|---|---|---|---|
| 1 | DOC-001 | Blocker | Docs | Front-door docs point testers at `0.9.0b1`; `install-guide.md:16` SHA-256 command names a file the b2 release doesn't publish → integrity check fails | The one trust step on an unsigned installer is broken |
| 2 | UX-001 / TEST-001 / QA-001 / ENG-002 | Critical | UX+Test+QA+Eng | Default model fails the landing's **own** example prompts (2–3 of 3) after 100–160 s; demo-only e2e is blind to it | New users' most natural first action fails; CI can't catch it |
| 3 | QA-002 | Critical | QA | Real-mode codegen sometimes emits **non-code** (literal `coaster`, bare `//`) as OpenSCAD source → `render_failed` after burning the full planning budget | Worse UX than plan-fail; wastes 2 min then errors |
| 4 | DOC-002 / ENG-003 | Critical | Docs+Eng | `ARCHITECTURE.md:81/83/91` documents the **removed** LLM-CadQuery untrusted-codegen path as live | A phantom threat surface; misleads security review + contributors |
| 5 | DOC-003 | Critical | Docs | `ARCHITECTURE.md` omits all 3 shipped b2 subsystems: Duet/Marlin, session-token guard, macOS/Linux | A contributor could silently break the session-token trust boundary |
| 6 | UX-002 | Major | UX | After a failed design, geometric refine chips stay active → clicking one fires **another** ~2-min likely-failure (a loop) | Turns one graceful failure into repeated dead-ends |
| 7 | ENG-001 | Major | Eng | The `bambu` optional extra (bottle, paho-mqtt, pythonnet) ships to **every** installer user via `requirements.lock`; symmetric `serial`/pyserial does **not** | Marlin-USB users hit an install wall on the official build |
| 8 | ENG-004 | Major | Eng | `/api/design` runs the full 100–160 s pipeline synchronously per request thread, no concurrency cap | Cheap local DoS under the shipped `--allow-remote` mode |
| 9 | DOC-004 / DOC-005 | Major | Docs | USER-MANUAL omits Duet/Marlin/session-token/macOS/Linux (all 3 audiences); no `docs/index.html` landing page | The approved manual rebuild + landing page must close these |
| 10 | TEST-002 | Major | Test | `test_version_single_source` doesn't scan README → suite green while README ships `0.9.0b1` (4 spots) | The exact gap that let the version drift ship |

*(UX-003 — the 3D viewport is keyboard-inaccessible, WCAG 2.1.1 — is the strongest runner-up Major.)*

---

## Cross-role findings

### A. The default model can't fulfill the product's own promises *(highest leverage in the audit)*
- **Surfaced in:** ENG-002, UX-001, TEST-001, QA-001, QA-002 (+ UX-002 as the failure-path amplifier).
- **What it is:** the default local planner (`gemma4:e4b`, ~4B) plus **exact-alias-only** template matching (`templates.py:323-331`) means natural-phrasing prompts — including the landing page's own "TRY" chips *and* the textarea placeholder — frequently dead-end at `needs_experimental` (off by default) or emit garbage code, after a 100–160 s wait. Because the e2e suite runs in `--demo` (a `DemoProvider` that returns a fixed box for any prompt), **CI is structurally blind** to this. The walkthrough got a clean coaster success in ~40 s while the QA pass got 3/3 failures in its window — so the behavior is **hit-or-miss/non-deterministic**, not always-fail; that variance is itself part of the problem.
- **Why it's the most important issue:** it's the default config, the featured path, and a new beta tester's (Kim's) most likely first action.
- **Blast radius of the fix:** touches `Landing.tsx` (the chips/placeholder), `templates.py` (alias matching), `pipeline.py` (plan-parse/codegen validation), config defaults, and needs a **real-model CI canary** over the shipped chips. Coordinate as one change, not five.
- **Recommended approach (decision for the owner):** (a) curate the example chips to prompts the default model reliably builds + broaden template alias matching [cheapest, highest impact]; and/or (b) recommend a stronger default planning model; and/or (c) validate generated code is real OpenSCAD before spending the render budget (fixes QA-002); plus (d) a CI canary so it can't regress.

### B. ARCHITECTURE.md describes a removed untrusted-codegen path as live
- **Surfaced in:** ENG-003, DOC-002.
- **What it is:** the root architecture doc still credits the LLM-CadQuery fallback (removed in `llm_provider.py:339`, `pipeline.py:79-88`) as a live generator — a security-relevant doc lie that README/USER-MANUAL/cadquery-backend.md already contradict.
- **Recommended approach:** rewrite the 3 rows in one ARCHITECTURE.md pass, alongside DOC-003 (add the 3 missing b2 subsystems).

### C. Version/release drift shipped because the version-single-source test doesn't cover prose
- **Surfaced in:** DOC-001 (Blocker), TEST-002 (the test gap), + the README/install-guide/USER-MANUAL/Discussion instances.
- **What it is:** `test_version_single_source` pins code surfaces but never scans the README/docs, so the suite stayed green while the front door fell a release behind — including the broken checksum command.
- **Recommended approach:** fix the docs AND extend the test to scan README/docs, so it can't recur.

---

## What's working

- **Engineering:** the per-boot session-token guard, the exclusive Windows bind, the layered + honestly-documented geometry sandboxes (OpenSCAD/CadQuery/Manifold), connector filename escaping (M32-injection-safe), and lockstep registry eviction. `ruff` clean, `pip-audit` clean, fast pytest subset 1249 green. *(01-engineering-deepdive.md)*
- **UI/UX:** the design system is audit-ledgered, AA-contrast-guarded, focus-managed, and reduced-motion/touch-target complete — well above a 0.9-beta bar; loading/empty/error states are honest and well-written. *(02-uiux-deepdive.md)*
- **Documentation:** `api.md`, `supported-printers.md`, `templates.md`, `CONTRIBUTING`, `SECURITY`, and the `[0.9.0b2]` CHANGELOG section are accurate and current. *(03-documentation-deepdive.md)*
- **Tests:** genuinely adversarial connector mocks (session-exhaustion, completion-state reset, password-leak guards); the session-token guard is tested for the true **403/200** contract; a clean shortcut census (zero `.only`/`xfail`/unconditional-skip/retry-config); a strict, self-aware gate. *(04-test-deepdive.md)*
- **Runtime quality:** ~30 adversarial inputs (oversized→413-with-drain, non-finite→null-coercion, non-object-JSON→distinct-400, session 403/200, 405-with-Allow, inert `<script>`) produced **zero 500s, zero leaked tracebacks, zero dropped connections**; real `~/.kimcad` data untouched. *(05-qa-deepdive.md)*

---

## This-sprint punch list (summary)

**Must-fix (1 Blocker + 5 Critical):** DOC-001 (broken checksum + version drift), the default-model headline (UX-001/TEST-001/QA-001/ENG-002), QA-002 (non-code codegen), DOC-002/ENG-003 (ARCHITECTURE fallback), DOC-003 (ARCHITECTURE omissions).
**Should-fix (high-leverage Majors):** UX-002 (failure loop), TEST-002 (version test gap), ENG-001 (dependency packaging), DOC-004 (manual b2 features), DOC-005 (landing page).

Full detail + sizes in [`sprint-punchlist.md`](sprint-punchlist.md).

---

## Next-sprint watchlist (summary)

ENG-004 (`/api/design` concurrency cap before any multi-user/`--allow-remote` push), UX-003 (keyboard access to the 3D viewport), the default-model **strategy** decision (stronger model vs cloud-default vs template-first planning), TEST-003 (live-Ollama error-path tests), README-FULL.pdf / professional manual format, and the parked #11 real-hardware connector validation. Full detail in [`next-sprint-watchlist.md`](next-sprint-watchlist.md).

---

## Blast-radius callouts

- **Default-model fix (cross-role A)** — coordinate `Landing.tsx` + `templates.py` + `pipeline.py` + config + a new CI canary as one change; don't patch the chips without also closing the CI blind spot or it regresses.
- **ENG-001 (dependency)** — moving `bambu` out of the universal `requirements.lock` (and adding `pyserial`) touches the installer staging, `verify_install`, and the size/footprint docs; regression-test a clean installer build.
- **DOC-001 / version drift** — fix README + install-guide + USER-MANUAL + definition-of-done + the pinned Discussion **and** extend `test_version_single_source`; otherwise the next bump drifts again.

---

## What we couldn't assess

- **Engineering:** the full live-tool pytest (313 live OpenSCAD/OrcaSlicer/CadQuery tests deselected for runtime — the strict CI runner runs them); real-hardware connector conformance (#11, mocks only); a live `gemma4:e4b` call (ENG-002 reproduced by code reading).
- **UI/UX:** live screen-reader output (NVDA/VoiceOver) and key-by-key tab order (judged from source/ARIA); the 320 px / 768 px / 1440 px viewports (only 390 px + ~1280 px captured).
- **Documentation:** the **pinned GitHub Discussion** content (on github.com, outside the local repo) — the owner should verify it against 0.9.0b2 before launch.
- **Test:** real-model planning quality (by design — CI never calls Ollama; that's the finding), CI flake-rate history, mutation score.
- **QA:** a single *successful* real-mode render inside its window — so QA alone couldn't say whether the model failure is non-determinism vs consistent; **the walkthrough's 40 s coaster success resolves this — it's non-deterministic/hit-or-miss.**

---

## Recommended next actions (for the owner / tech lead)

1. **Before any tester sees the repo:** fix DOC-001 (the install-guide checksum command + the front-door version markers) — it's a ~10-minute Blocker fix.
2. **Decide the default-model approach** (cross-role A) — curate chips + broaden template matching is the cheap, high-impact first move; add the real-model CI canary so it can't regress; consider validating generated `.scad` before rendering (QA-002).
3. **One ARCHITECTURE.md pass** to fix the removed-fallback drift (DOC-002/ENG-003) and add the 3 missing b2 subsystems (DOC-003).
4. **Build the approved landing page + rebuild the user manual** (DOC-004/DOC-005) covering the current feature set across all three audiences.
5. **Plan ENG-001 and ENG-004** into the next cycle (dependency packaging; request concurrency cap).

---

## Reference — role deep-dives

- [`01-engineering-deepdive.md`](01-engineering-deepdive.md) — Principal Engineer
- [`02-uiux-deepdive.md`](02-uiux-deepdive.md) — Senior UI/UX Designer
- [`03-documentation-deepdive.md`](03-documentation-deepdive.md) — Technical Writer
- [`04-test-deepdive.md`](04-test-deepdive.md) — Test Engineer
- [`05-qa-deepdive.md`](05-qa-deepdive.md) — QA Engineer

Writer mode was **audit-only** (no `doc-rewrites/` drafted) — the landing page + manual rebuild are approved for the remediation phase.

---

*Audit conducted by the audit-team skill on 2026-06-14. Findings are balanced and evidence-based. Every Blocker and Critical includes reproduction details and a blast-radius entry in the deep-dive.*
