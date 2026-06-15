# Next-Sprint Watchlist — KimCad 0.9.0b2

**Audit date:** 2026-06-14

Forward-looking items that don't belong in the current sprint — they need architectural thinking, a product/leadership decision, or infrastructure the current sprint can't stand up. Keeping them visible prevents debt from going acute.

---

## Structural / architectural

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | ENG-004 | Engineering | `/api/design` runs the full 100–160 s pipeline synchronously on the request thread with no concurrency cap — add a queue/async + a cap | Before promoting `--allow-remote` or any multi-user/LAN-shared deployment |
| 2 | ENG-002 / cross-role A | Engineering | Template matching is exact-alias-only (`templates.py:323-331`); a fuzzy/semantic match would let natural phrasing hit existing families | When expanding the template catalog or the example set |

## Design debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | UX-003 | UX | Keyboard access to the 3D viewport (orbit/zoom/measure) — currently mouse/touch only (WCAG 2.1.1) |
| 2 | UX-004 | UX | Verify the 320 px small-phone breakpoint (dense Settings forms + the slider value-edit popover are the risk) |
| 3 | UX-007 | UX | Computed contrast of the low-alpha viewport overlay text ("Drag to rotate", dimension chips) over a dynamic 3D scene |

## Documentation debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | DOC-005 | Docs | The approved `docs/index.html` landing page + GitHub Pages (also in this sprint's should-fix — keep here until it actually ships) |
| 2 | DOC-006 | Docs | A professionally formatted, complete user manual (the approved rebuild) — format-flexible (need not be PDF) but must cover everything across all 3 audiences; decide whether a `README-FULL.pdf` is also wanted |
| 3 | DOC-007 | Docs | Verify the **pinned GitHub Discussion** against 0.9.0b2 (it's on github.com, not in the repo — the audit couldn't reach it) |

## Test-culture debt

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | TEST-001 | Test | A real-model CI canary lane (a small Ollama in CI, or a nightly) that plans the shipped example prompts — closes the demo-only blind spot permanently |
| 2 | TEST-003 | Test | Real-model error/retry surfaces (Ollama down, cold-pull, OOM, 404 vision) are tested only against mocks — add live-Ollama coverage |
| 3 | TEST-004 | Test | Re-verify the Marlin/Bambu/Moonraker/PrusaLink mocks to the same adversarial bar as the Duet mock (parity currently assumed) |

## Performance and scaling

| # | ID | Role | What to consider | Trigger to act |
|---|---|---|---|---|
| 1 | QA-004 / W-F-003 | QA/Walkthrough | WebGL `ReadPixels` "GPU stall" warnings flood the console — throttle/cache the readback | When adding any new per-frame readback (thumbnails/measure) |
| 2 | cross-role A | QA | The 100–160 s local-model latency on CPU is the product's slowest path — the loading UX sets expectations well, but a faster default model or GPU path would transform first-run | When a stronger small model or a GPU build is viable |

## Dependency and supply chain

| # | ID | Role | What to consider |
|---|---|---|---|
| 1 | ENG-001 | Engineering | `bambu` extra (bottle, paho-mqtt, pythonnet) ships universally via `requirements.lock` — split it out; this is in the sprint should-fix but track footprint impact here too |

## Decisions needing product/leadership input

- **Default-model strategy (cross-role A)** — the owner must choose the direction: (a) curate prompts to the current model's competence, (b) recommend/ship a stronger default planner, (c) make cloud-acceleration more prominent for hard requests, or (d) template-first planning. Engineering can't pick this alone.
- **DOC-006 / README-FULL.pdf** — is a published PDF a required release artifact, or are the `.md`/landing page the system of record? (Owner has indicated format-flexible but complete + professional.)
- **#11 real-hardware connector validation** — parked (hardware-blocked); the gate to promote out of beta. No action until hardware is available.

---

## Review cadence

- **Next sprint planning** — elevate anything acute (the default-model strategy decision should be made before the next beta).
- **Quarterly** — retire what's addressed; re-check the watchlist.
- **On any move to multi-user / `--allow-remote` / LAN** — ENG-004 becomes acute; re-audit the request path.

---

*Generated from the audit-team skill. Each entry cross-references its full treatment in the relevant role deep-dive.*
