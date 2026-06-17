# KimCad 0.9.0b4 (+ restored UI) — Playwright Interface & Wiring Walkthrough

**Date:** 2026-06-16/17
**Build under test:** `0.9.0b4`, `origin/main` @ `356867d` — the b4 rollback (`c8e9f44`) **plus the restored post-b4 UI** (commits `3a00818` Kim avatar, `d4b6d6f` avatar asset, `9af7cc7` designer pass), re-applied as `356867d`. Gate green (pytest 1600 passed incl. live OrcaSlicer; vitest 396 passed; build-repro clean). Snapmaker fully out.
**Method:** the **real** app driven live — `kimcad web` on port 8714 (real `qwen2.5:7b` planner, real OrcaSlicer, isolated home), driven through a real browser via Playwright/preview. **No static substitute, no `--demo`, no command-string assertions.** Where a wire produces an artifact, the artifact itself was fetched and proven.

---

## Verdict

**The b4+restored-UI product is genuinely wired and working end-to-end, and the restored UI is intact and rendering.** The critical path — describe → design (real on-device model) → render → printability gate → **slice → real print file** → download — is live-proven, including fetching the produced `.3mf` and confirming it carries real motion G-code. All three restored UI elements (Kim's avatar in the top bar + chat, the Settings sticky section-nav, the wizard cloud `<details>` disclosure) render and behave correctly. **Version `0.9.0b4`, zero Snapmaker / toolhead / multi-material anywhere, every printer single-material. Zero console errors across the whole journey.** No Blockers, no Criticals.

---

## Restored-UI verification (the reason for `356867d`)

| Restored wire | Verified | Evidence |
|---|---|---|
| **Kim avatar — top bar logo** | ✅ renders, no 404 | `.kc-logo` `background-image: url(.../assets/kim-avatar.png)`, 32×32; network `GET /assets/kim-avatar.png → 200 OK`; visible in screenshot (incl. dark mode) |
| **Kim avatar — chat AI rows** | ✅ renders | `.kc-ava` 28×28 with `kim-avatar` background present during the design "thinking" row |
| **Settings sticky section-nav** | ✅ wired | 4 groups (Design defaults / AI / Output & tools / System) with correct links, `aria-current` tracking, all 4 anchors (`grp-design/ai/output/system`) present |
| **Wizard cloud disclosure** | ✅ wired | `.kc-wiz-cloud` is a `<details>` ("Advanced — cloud speed-ups · optional · local always works"), collapsed by default, toggles open to reveal the OpenRouter key field |

---

## Wiring assessment (live-driven, with evidence)

| Area | Wires exercised | Result | Evidence |
|---|---|---|---|
| **Landing** | home, My Designs, Settings, Shortcuts, prompt + Design it, photo/sketch on-ramps, 3 TRY chips, library link, capability strip | All present + wired; clean console | a11y snapshot; `preview_console_logs` → none |
| **Design** | typed a custom prompt + clicked **Design it** → real `qwen2.5:7b` plan | Real design ran, honest "runs on your computer's AI… can take a few minutes" + phase label "Planning the shape" + Cancel | live eval (`Designing your part…` → result) |
| **Workspace / gate** | render + printability gate | Part rendered (canvas present); **Readiness 92/100, gate Passed**; Inspector tabs Parameters · Quality · Export | eval: readiness panel + tabs |
| **Part fidelity** | the produced part matches the prompt | dims **100 mm across, 22 mm tall, 6 mm rim** — exactly "a round trinket dish, 100 mm across and 22 mm tall, with a 6 mm rim" | eval: dimension scan |
| **Export / SLICE** | printer picker (29 printers, **no Snapmaker**), single Material dropdown (PLA/PETG/TPU/ABS), **Slice & prepare file** | Real OrcaSlicer produced **Download print file (.3mf)** (`/api/gcode/1`) + STL + STEP | eval + artifact fetch |
| **Slice artifact (PROOF)** | fetched `/api/gcode/1` and ran the project's `prove_gcode_3mf` | **PASS** — 576,665 bytes; **138,593 G-code lines, has_motion=True, 110 layers, 34.18 cm³, est. 59m 44s** | `prove_gcode_3mf` output |
| **Download wires** | the three export links | "Download print file (.3mf)", "Download 3D model (.STL)", "Download editable CAD (.STEP)" all present; `.3mf` downloaded (576 KB) | eval + Invoke-WebRequest 200 |
| **Send** | SendPanel | **Send** control present (gated; not fired — mock connector) | eval |
| **Settings** | Settings panel + new section-nav | 4-group sticky nav + sections; **version 0.9.0b4**, **0 Snapmaker mentions** | eval |
| **My Designs** | opened My Designs | 15 persisted designs with Import / New design / Sort-by / per-card Rename·Duplicate·Backup(.kimcad)·Delete | eval |
| **Shortcuts** | `?` modal | "Keyboard shortcuts" modal with ?, N, D, comma, Esc; Close button works | eval |
| **Dark mode** | color-scheme dark | body `rgb(24,23,21)` bg / `rgb(245,239,229)` text; avatar still renders; polished | inspect + screenshot |
| **Mobile (375px)** | responsive | no horizontal overflow (scrollW == clientW == 375); avatar still loads | eval |

---

## Findings

**No Blockers / Criticals.** The product is wired and the critical path is real-verified, on b4+restored-UI.

- **[Minor — UX] Export connector badge reads "mock · Ready · simulated".** "simulated" refers to the *connection* (the built-in mock, no hardware), but next to the slice controls it can be misread as "the slice is simulated," and the raw config key "mock" leaks unprettified (siblings use `displayName()`). Pre-existing in b4 (not from the UI restore). *Evidence:* Export panel text "mock Ready · simulated". (This is audit finding UX-001.)
- **[Nit — A11y] Settings section-nav sets `aria-current="true"` on every link in the active group**, not the single current item (both "Printer & material" and "Display" carry it when `grp-design` is active). From the restored designer pass (`9af7cc7`). Reasonable as a "current section" indicator but semantically loose. *Evidence:* eval `current: ["Printer & material","Display"]`.
- **[Nit — Hygiene] UTF-8 BOM at the top of `FirstRunWizard.tsx` and `SettingsPanel.tsx`** introduced by the designer pass. Harmless (vitest/build pass) but non-idiomatic. To be stripped in remediation.

---

## What's working (specific)

- The **on-device design path** is real and honest — runs the local model, shows elapsed phase, tells the user nothing leaves the machine.
- The **printability gate → slice** coupling is sound; the gate verdict gates the slice.
- The **restored UI is fully intact**: avatar renders in both locations (incl. dark mode), the Settings section-nav and wizard cloud disclosure work, and the SPA was rebuilt reproducibly (build-repro green).
- The catalog is honest single-material; **no Snapmaker/multi-toolhead remnants** anywhere in the running UI.
- **Zero console errors** across landing → design → gate → slice → export.

---

## Coverage & honesty note

Live-driven against the real app with evidence: Landing, the three restored UI wires, Design (real model), Workspace/render/gate, part-fidelity, Export + **the real Slice wire and its proven artifact**, downloads, Send (present/gated), Settings (+ new section-nav) + version + Snapmaker-absence, My Designs, Shortcuts modal, dark mode, mobile viewport. **Zero console errors** throughout.

Wires not re-clicked live this pass — the photo/sketch on-ramp dialogs, the part Library modal, refine chips/VersionRail, and the SendPanel actual send — are exercised by the **396 passing frontend vitest tests + the Playwright e2e suite** (`tests/e2e/`: design-refine, export-gate, etc.), which ran green in the same gate that pushed `356867d` (1600 pytest passed, incl. the e2e browser journeys). They are called out here explicitly rather than claimed as live-clicked.
