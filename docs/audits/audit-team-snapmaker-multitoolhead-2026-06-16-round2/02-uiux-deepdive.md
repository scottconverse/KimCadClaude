# UI/UX Deep-Dive — KimCad Snapmaker U1 / Multi-Toolhead — ROUND 2 (post-remediation)

**Audit date:** 2026-06-16
**Role:** Senior UI/UX Designer
**Round:** 2 (re-audit after remediation of round-1 findings)
**Scope re-audited:** `frontend/src/components/ExportPanel.tsx`, `frontend/src/components/SendPanel.tsx`, `frontend/src/styles.css`, `frontend/src/api.ts`, plus the two component test suites (`ExportPanel.test.tsx`, `SendPanel.test.tsx`)
**Auditor posture:** Balanced, evidence-first
**Runtime note:** The live app cannot be Playwright-driven on this box (exclusive Windows port bind). Verification is by static code + CSS reading and by the vitest component suites, which assert the rendered DOM (classes, labels, ids, chip text). Items that genuinely require a browser to confirm are flagged explicitly.

---

## TL;DR

Every round-1 UX finding is resolved with concrete file:line evidence, and the fixes are backed by passing component tests. The critical gap (no CSS for the temperature chips) is closed with real, theme-defined design tokens — verified to exist in both light and dark themes. The jargon copy is rewritten to "Extruder n" with an explanatory muted note, the N-slot layout is wrapped in a compact responsive grid, the post-slice summary now lists per-extruder materials from client state, the dynamic labels carry explicit `htmlFor`/`id`/`aria-labelledby`, a one-shot pre-send thermal read was added, and the `toFixed` null-crash risk is guarded with an em-dash fallback. `tsc --noEmit` is clean; 31/31 component tests pass.

I found no new defects of Minor severity or higher introduced by the fixes. One Nit (grid `auto-fill` vs `auto-fit` cosmetic) and a small set of items needing browser confirmation are noted below, none blocking.

**Round-1 UX: 0 OPEN / 7 RESOLVED (+ the bonus null-crash RESOLVED).**

---

## Round-1 finding resolution table

| ID | Sev (R1) | Title | Status | Evidence |
|---|---|---|---|---|
| UX-001 | Critical | No CSS for `kc-temp-chip` / `kc-send-temps` | **RESOLVED** | `styles.css:3307` `.kc-send-temps` (inline-flex, wrap, gap), `styles.css:3312` `.kc-temp-chip` (pill: border `--kc-hair-strong`, radius `--kc-r-chip`, bg `--kc-surface-2`, ink `--kc-ink`, mono `--kc-font-mono`). All five tokens defined in `:root` (`styles.css:46–50, 78, 85`) AND overridden in the dark block (`:111–115`). Chips used at `SendPanel.tsx:261–266` (pre-send) and `328–334` (post-send). |
| UX-002 | Major | "T1 Material" jargon, no context | **RESOLVED** | `ExportPanel.tsx:178` label now `Extruder {i + 1}`; muted explanatory note at `:170–173` ("Assign a filament to each extruder — the slicer tunes temperature and retraction per slot."). Test asserts both: `ExportPanel.test.tsx:327–330`. |
| UX-003 | Major | No layout cap on N dropdowns | **RESOLVED** | Slot map wrapped in `<div className="kc-material-slots">` (`ExportPanel.tsx:175`); CSS grid `repeat(auto-fill, minmax(170px, 1fr))` at `styles.css:1962–1966`. Slots now group and reflow (2-up at card width) instead of an unbounded vertical stack, keeping the Slice button reachable. |
| UX-004 | Major | Post-slice summary omits per-slot materials | **RESOLVED (frontend, as recommended)** | `slotMaterialNames` mapped KEY→display name at `ExportPanel.tsx:87–90`; passed to `PrintSummary` at `:256`; lead renders "Extruder 1: PLA, Extruder 2: TPU" at `:360–365, 371`. Test asserts the rendered lead: `ExportPanel.test.tsx:384`. Round-1's "longer-term backend echo" remains an optional enhancement, not a defect. |
| UX-005 | Minor | No explicit label `htmlFor`/`id` | **RESOLVED** | `ExportPanel.tsx:177` `htmlFor={`kc-slot-${i}`}`, `:178` `<span id={`kc-slot-label-${i}`}>`, `:180–181` `id` + `aria-labelledby`. Test asserts the association: `ExportPanel.test.tsx:335–337` (`slot0.getAttribute('aria-labelledby') === 'kc-slot-label-0'`). |
| UX-006 | Minor | No pre-send thermal state | **RESOLVED** | One-shot `getConnectorStatus` on selection for a configured, non-simulated connector (`SendPanel.tsx:130–152`), rendered as a "Printer status" line with chips (`:256–276`), cleared when a send takes over (`:166`). Test: `SendPanel.test.tsx:288–304` (shows line + chips, one call, not a poll) and `:306–314` (suppressed for simulated). |
| UX-007 | Nit | Degree spacing | **RESOLVED (no change, as advised)** | Round-1 explicitly required no change; output `T1: 205°C` is the informal-style convention and is unambiguous. Consistent across pre- and post-send chips. |
| Bonus | (Eng) | `toFixed` on null toolhead temp crashes | **RESOLVED** | Null-guard `t != null ? t.toFixed(0) : '—'` at `SendPanel.tsx:264` (pre-send) and `:331` (post-send); nozzle fallback guarded at `:271`. Test asserts the em-dash path: `SendPanel.test.tsx:300–301` (`T2: —°C` from `[205, null]`). |

**Resolved: 7/7 round-1 UX findings + the bonus null-crash. OPEN: 0.**

---

## Verification performed

- **Token reality check (the UX-001 risk):** Grepped every token the chip CSS references. `--kc-hair-strong`, `--kc-r-chip`, `--kc-surface-2`, `--kc-ink`, `--kc-font-mono` all resolve — defined in `:root` (`styles.css:42–89`) and the surface/ink/hair set re-defined for dark theme (`:108–118`). No undefined-variable fallbacks. The round-1 fix-path draft named `--kc-bg-raised` / `--kc-mono` (which do **not** exist); the shipped code correctly uses the real names instead. Good catch by the implementer.
- **Type safety:** `tsc --noEmit` exits 0. The new `slotMaterials?: string[]` prop, `ConnectorStatusResponse.toolhead_temps?: number[] | null` (`api.ts:173`), and `postSlice(..., materialSlots?)` (`api.ts:632–644`) all typecheck.
- **Tests:** `ExportPanel.test.tsx` + `SendPanel.test.tsx` → **31 passed / 31**. Coverage includes the multi-head expand/collapse, the per-extruder summary, the label association, the pre-send chip line, the simulated-connection suppression, and the null-temp em-dash.

---

## What's working (credit)

- **Real tokens, both themes.** The chip uses `--kc-surface-2` / `--kc-ink` / `--kc-hair-strong`, all of which flip in the dark block — so the pill has correct contrast in light *and* dark mode for free. This is the right way to have fixed UX-001.
- **The pre-send read is genuinely race-safe.** `SendPanel.tsx:133–152` keys the effect on `[chosen, wantsPreStatus]`, sets a `cancelled` flag in cleanup, and wraps the call in `Promise.resolve(...)` so a synchronously-throwing status path can't escape. `doSend` nulls `preStatus` (`:166`) the instant a send starts, and the render gate `!result && preStatus && (...)` (`:256`) guarantees the pre-send line and the post-send live banner are mutually exclusive — no double chip row, no flicker-into-stale.
- **Honest gating preserved.** Pre-send chips are gated on `configured && !simulated` (`:132`); post-send chips remain gated on `!result.simulated`. A test connection still never emits fake temperatures.
- **Per-extruder summary reads in plain English.** "Sliced for Snapmaker U1 — Extruder 1: PLA, Extruder 2: TPU. Here's your print:" (`ExportPanel.tsx:360–371`) — keys are mapped to display names, single-head path unchanged (`hasSlots` false → falls back to `in {material}`).

---

## NEW findings (introduced by the fixes)

### [UX-201] — Nit — Responsive — Slot grid uses `auto-fill` (not `auto-fit`); at N=2 on a very wide card the two pickers don't stretch to fill

**Evidence:** `styles.css:1964` `grid-template-columns: repeat(auto-fill, minmax(170px, 1fr))`. With `auto-fill`, empty trailing tracks are retained, so on a card wide enough for 3+ columns the two Snapmaker-U1 slots occupy the first two ~170px tracks and leave whitespace to the right rather than expanding to share the row. `auto-fit` would collapse empty tracks and let the two fields grow to fill.

**Why this matters:** Purely cosmetic, and only at card widths wider than ~540px of inner content — the Export card is column-constrained in the current layout, so in practice N=2 renders as two side-by-side pickers, which is the desired result. At N=4 the 2×2 reflow is correct either way.

**Fix path (optional):** Change `auto-fill` → `auto-fit` if a future wide-card layout is adopted. No change needed today.

**Blast radius:** none beyond `.kc-material-slots`; single CSS rule.

---

## Items needing runtime (browser) confirmation

These are not findings — the static + test evidence is consistent and I have no reason to believe they're broken. They simply cannot be pixel-verified on this box and should be eyeballed once before release:

- **Chip contrast in dark mode at the live moment.** `--kc-surface-2` (#2a2722) ink-on-chip vs the `--kc-send-live` muted parent — verified token-correct, but the exact rendered contrast of the pill against the dark status row was not sampled with a contrast tool.
- **Grid column count at real card width.** The 2-up-at-N=2 / 2×2-at-N=4 reflow is inferred from `minmax(170px, 1fr)` and the card's known width; confirm visually that the Slice button stays above the fold at N=4 on a 768px viewport.
- **Screen-reader announcement order** of the dynamically inserted "Extruder n" labels (now explicitly associated via `aria-labelledby`, which strengthens the round-1 implicit association — but live AT order was not tested).

---

## States audit matrix (post-remediation)

| Component / state | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| ExportPanel — multi-slot | ✓ | ✓ | ✓ | ✓ | ✓ | Slots initialize from effective material; grid groups them; muted note explains the section |
| SendPanel — pre-send | ✓ | n/a | ✓ | ✓ (silent) | ✓ | UX-006 thermal line; null temp → em-dash; suppressed for simulated/unconfigured |
| SendPanel — post-send (real) | ✓ | ✓ | ✓ | ✓ | ✓ | Chips now styled (UX-001); `[210, null]` renders `T2: —°C` not a crash |
| PrintSummary — multi-slot | ✓ | — | — | — | ✓ | Per-extruder material list (UX-004) from client state |

Every cell the round-1 audit marked ✗ is now ✓.

---

## OPEN-only severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 0 |
| Nit | 1 (UX-201 — `auto-fill` vs `auto-fit`, optional) |

**Round-1 carryover OPEN: 0.** All 7 round-1 UX findings + the bonus null-crash are RESOLVED with file:line evidence and passing tests. The single new item is a Nit with no user-felt impact in the current layout.

---

## Appendix: surfaces re-reviewed

- `frontend/src/components/ExportPanel.tsx` (full)
- `frontend/src/components/SendPanel.tsx` (full)
- `frontend/src/styles.css` — `.kc-material-slots` (1962), `.kc-send-temps` (3307), `.kc-temp-chip` (3312), token block (42–118), `.kc-field` (1933), `.kc-send-live` (3297)
- `frontend/src/api.ts` — `ConnectorStatusResponse` (163–174), `SliceResponse` (148–161), `PrinterOption.toolhead_count` (120), `postSlice` (632–644)
- `frontend/src/components/ExportPanel.test.tsx`, `SendPanel.test.tsx` (31 tests, all passing)
- Build gates run: `tsc --noEmit` → exit 0; targeted `vitest run` → 31/31 pass
