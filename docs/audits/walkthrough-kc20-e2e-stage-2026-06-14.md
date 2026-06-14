# Walkthrough — #25 (KC-20) e2e stage close
**Date:** 2026-06-14
**Mode:** Audit (read-only; no product source modified)
**Target:** The KimCad SPA driven via the real `kimcad web --demo` server, at `main` (`35f7a80`), after the Playwright e2e suite landed.

## Purpose

The per-stage walkthrough for #25. The new e2e suite (18 journeys) is itself structured walkthrough coverage of the primary flows; this pass adds the **exploratory** dimension — driving the running SPA through the flows the scripted journeys do *not* assert, looking for dead/inert controls, broken wiring, and console errors.

## Product model (what the SPA promises)

A local-first AI→parametric-CAD→3D-print app: describe / photograph / sketch a part → a parametric design renders → refine it (sliders = local, chat = model) → check printability → slice → download or send to a printer. Secondary surfaces: the Inspector tabs (Parameters / Quality / Export), the version rail, click-to-measure, settings (units, dark mode, cloud opt-in, experimental generator), My Designs, the first-run wizard.

## Coverage map (e2e + exploratory)

| Flow | e2e journey | This walkthrough |
|---|---|---|
| First-run wizard (walk + skip) | ✅ Slice 5 | — |
| Prompt → design → workspace | ✅ Slice 2 | ✅ re-confirmed |
| Refine (chip + typed) | ✅ Slice 2 | ✅ typed refine → version rail updates |
| Parameter sliders (local re-render) | ✅ Slice 2 | — |
| Photo / sketch on-ramps | ✅ Slice 3 | — |
| Printability gate (pass + fail) | ✅ Slice 4 | — |
| Slice → download print file | ✅ Slice 4 | ✅ → SendPanel appears post-slice |
| Inspector Quality tab (readiness) | ✅ Slice 5 (switch) | ✅ readiness/confidence/printability bands render |
| Settings toggle | ✅ Slice 5 | ✅ opens; dark-mode/appearance control present |
| My Designs (save + reopen) | ✅ Slice 5 | — |
| Error recovery (slice failure) | ✅ Slice 5 | — |
| Click-to-measure | — (not scripted) | ✅ toggle present + toggles without error |
| Version rail (refine → v2) | — | ✅ updates on refine |
| Send-to-printer panel | — | ✅ renders post-slice (`Send to printer` / `Printer connection`) |
| Keyboard shortcuts overlay (`?`) | — | ✅ opens |
| Dark mode | — | ✅ control present in Settings |
| Mobile viewport (390×844) | — | ✅ landing renders, prompt visible |

## Exploratory findings

**None.** Every uncovered flow exercised was wired and functional — no inert/dead controls, no broken routes, no placeholder-as-feature. The browser console stayed **clean** (no errors / uncaught exceptions; only the filtered GL-driver perf warnings) across the entire exploratory session, including the design render, the typed refine, the slice, tab switches, the keyboard overlay, Settings, and the mobile re-render.

## Verdict

The SPA is **finished and wired** — the UI is connected to the real system end to end, and the new e2e suite gives it durable, console-clean regression coverage of every primary journey. The exploratory pass found the secondary surfaces (measure, version rail, send panel, shortcuts, dark mode, mobile) equally wired. This is consistent with the prior stage walkthroughs (stage-9, stage-10, stage-a, stage-bcd) and the 18 passing journeys.

No repair-mode work is warranted from this walkthrough. The #25 stage-close audit-team (engineering / test / QA / docs review of the e2e infrastructure) runs alongside this pass; any findings there are remediated separately to 0/0/0/0/0 before #25 closes.
