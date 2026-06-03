# Audit Lite — Stage 7 Slice 4: Smart Mesh readiness report card (frontend)
**Date:** 2026-06-02
**Scope:** `frontend/src/api.ts` (readiness types), `frontend/src/designStatus.ts` (`readinessTone`), `frontend/src/components/RightPanel.tsx` (`ReadinessCard` / `ReadinessBody` / `ScoreGauge`), `frontend/src/styles.css` (the readiness card block), and the tests (`RightPanel.test.tsx` +3, `designStatus.test.ts` +1). UX is the highest-weighted dimension.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship after three Minors. The card is well-built and honest: a legible 0-100 arc gauge, a plain verdict, a confidence badge whose blurb faithfully names what backed the call (gate vs engine), risks/recommendations as actionable detail, and a muted attribution footer — all driven by a clean local `--tone` CSS variable so a tone change repaints the gauge/verdict/dots without flooding the card. Live DOM + computed-style inspection confirms the pass state renders correctly on desktop and mobile (the JPEG screenshot tool times out in this env — a documented Stage-5 limitation; the renderer itself is responsive). The three Minors are all polish: a duplicated "Ready to print" headline across two stacked cards, a color-only per-risk severity cue, and two untested render branches (the tone class + the comparison line).

## Severity rollup

> **FINAL (after remediation): 0 / 0 / 0 / 0 / 0.** As-found below; see "Re-audit (resolution)" at the bottom.

**As found:** 0 Blocker · 0 Critical · 0 Major · 3 Minor · 0 Nit.

## Findings

### SLICE4-001 Minor: a pass part shows "Ready to print" twice in stacked cards
**Dimension:** UX
**Evidence:** For a passing part the Readiness card renders the verdict "Ready to print" (`RightPanel.tsx:221`, from `smart_mesh._VERDICT["pass"]`) and the *immediately following* Printability card renders the gate badge "Ready to print" (`gateLabel('pass')`, `designStatus.ts`). Verified live on the demo: the Readiness verdict reads "Ready to print" and the Printability badge below it reads the same. Two adjacent cards lead with the identical phrase.
**Why it matters:** The two cards have distinct jobs — Readiness is the synthesized "should I print this?" headline (score + risks + recommendations + attribution); Printability is the technical gate detail (the dims table + findings). Leading both with the same sentence reads as redundancy, not reinforcement — below the Apple-grade bar for a stacked layout, and it blurs which card is the headline and which is the detail.
**Fix path:** Differentiate the technical card from the synthesized one. Cheapest: reframe the Printability badge as the *gate* result (e.g. "Gate: passed" / "Gate: needs review" / "Gate: failed") so it reads as the engine-level check feeding the Readiness headline, not a second verdict. (Alternatively, drop the Printability badge entirely and let it lead with the dims table, since Readiness now owns the verdict.) Keep one canonical "Ready to print" — on the Readiness card.

### SLICE4-002 Minor: a risk's severity tier (warn vs fail) is conveyed by dot color only
**Dimension:** UX (accessibility)
**Evidence:** Each risk renders a `.kc-risk-dot` whose color is the only signal of its tone (`RightPanel.tsx:234-235`); the dot is `aria-hidden`, and the risk's text is just `<b>{title}</b>` + detail with no severity word. So whether a risk is amber (warn) or red (fail) is communicated purely by hue — invisible to a screen reader and ambiguous for a red/green-deficient user. (The global card tone + score still convey the overall severity; this is specifically the *per-risk* tier.)
**Why it matters:** WCAG 1.4.1 (use of color): information carried by color needs a non-color equivalent. The risk text fully describes *what* is wrong, so this is narrow — but the warn/fail *tier* is genuinely color-only, and this is the project's UX-first acceptance bar.
**Fix path:** Give the dot a text equivalent: add a visually-hidden severity word inside the `<li>` (e.g. a `<span className="kc-sr-only">Warning: </span>` / `Critical: `) keyed off `r.tone`, or set an `aria-label` / `title` on the risk row. Optionally differentiate the dot by shape, not just hue, for sighted color-deficient users.

### SLICE4-003 Minor: the tone-class application and the comparison-line branch are untested
**Dimension:** Tests
**Evidence:** `RightPanel.test.tsx` asserts the warn card's text content (verdict/confidence/risk/recommendation/attribution) but never asserts the `kc-rtone-*` class that drives the whole visual tone, and no test exercises a **pass**-tone card (the gate-only attribution "via KimCad printability gate" is only verified live, not in a unit test) or the **comparison** line (`RightPanel.tsx:262` renders `readiness.comparison` when present — an untested branch, even though Slice 5 will populate it).
**Why it matters:** The tone class is the core correctness mechanism (it selects `--tone` for the gauge, verdict, and dots); a regression that dropped or mis-set it would pass every current assertion. The comparison branch is dead-untested until Slice 5, so a render bug there ships silently.
**Fix path:** Add: (a) a pass-tone assertion — `container.querySelector('.kc-readiness.kc-rtone-pass')` truthy and the gate-only attribution text present; (b) a comparison-line assertion — a readiness with `comparison: 'Matches your strongest past prints.'` renders it. Both are a few lines.

## What's working
- **Honest attribution, faithfully rendered.** The confidence badge + `CONFIDENCE_BLURB` name exactly what backed the verdict — "Medium confidence" / "From KimCad's printability gate." for the gate-only path (verified live), "High" / "Validated by the PrintProof3D engine." only when Slice 3 says the engine ran. The card doesn't hardcode or overstate; it renders the server's honest signal. This is the spec's "PrintProof3D is the engine Smart Mesh is built on, not Smart Mesh itself" made visible.
- **Clean tone mechanism, no background flood.** `kc-rtone-{pass,warn,fail}` set *only* a local `--tone` color (`styles.css`), which the gauge fill, verdict, and per-risk dots consume — deliberately NOT the `.kc-tone-*` badge classes that paint a full background. Computed-style check: the pass gauge fill is `rgb(29,122,78)` (`--kc-pass`) with `stroke-dasharray: 92px, 100px`, and the verdict text is the same green — the variable path works end to end. A fail readiness would repaint all three red via `--kc-fail` through the identical path.
- **The gauge is honest and accessible.** `pathLength={100}` makes the dash equal the score directly, independent of the arc's real length, so the fill is a true 0-100 proportion; `Math.max(0, Math.min(100, …))` clamps defensively atop the backend's own clamp. `role="img"` + aria-label "Readiness score 92 out of 100" gives assistive tech the number, and the score is also shown as plain text — not color-only.
- **Robust to sparse data.** Every optional section is guarded: empty `risks`/`recommendations` hide their block (`length > 0`), a null `comparison` hides the line, an empty `confidence` hides the badge, and an unknown confidence string falls back to `''` in the blurb. The card renders only when `result?.report?.readiness` exists, with idle and failed placeholders that mirror the sibling cards. No `undefined.map`, no crash on a partial payload.
- **Responsive.** Mobile (375): no element overflow, no document horizontal scroll, gauge centered (188 vs 187.5), all rows within the viewport. Desktop (1280): the verdict's right edge (~1235) clears the column with no overflow.
- **No regression.** The existing Parameters / Printability / Export cards and their tests are untouched; vitest is 41 passed (was 37). The new card slots in without disturbing the slider re-render flow.

## Watch items
- **Export affordance vs a PrintProof3D-fail readiness (engine-on follow-up).** In every *default* config (engine off / not on disk) the readiness tone tracks the gate exactly — readiness "fail" ⟺ gate FAIL ⟺ ExportPanel already blocks — so the card and the export button agree today. They can only diverge once the engine is enabled and returns a fail/blocker the deterministic gate didn't, leaving a "Not print-ready" card above a still-enabled export. Same opt-in boundary as Slice 3's SLICE3-001; reconcile (gate the export on `readiness.tone === 'fail'`, or a proceed-anyway-style confirm) before the engine ships enabled.
- **Risk `key={title:detail}` collisions.** Two risks with an identical title+detail would collide on the React key. Not reachable from the current engine output, noting only for completeness.

## Escalation recommendation
No escalation needed. Three polish-level Minors on a correct, honest, responsive, well-isolated UI slice; the tone mechanism and a11y fundamentals are sound and the data contract degrades gracefully. Fix the three and re-audit to 0/0/0/0/0; the Stage-7 stage-end audit-team covers the full branch (including the engine-on export reconciliation).

---

## Re-audit (resolution) — 0/0/0/0/0

- **SLICE4-001 (Minor) — FIXED.** `gateLabel` now frames the Printability gate badge as the technical check — "Passed" / "Needs review" / "Failed" — instead of reusing the readiness headline. Live re-verify on the demo: card order Parameters → Readiness → Printability → Export; the Readiness verdict reads "Ready to print" and the Printability badge reads "Passed"; the string "Ready to print" now appears **exactly once** in the whole DOM (was twice). `gateLabel`'s test was updated to pin the new framing (and to assert it is *not* the readiness phrase); the RightPanel test that checked the old badge now checks "Passed".
- **SLICE4-002 (Minor) — FIXED.** Each risk now carries a screen-reader-only severity word (`RISK_TONE_WORD`: fail → "Critical risk", warn → "Warning", via a new `.kc-sr-only` utility), so the warn/fail tier has a non-color text equivalent (WCAG 1.4.1), not just the dot hue. A new assertion confirms the "Warning:" cue renders for a warn risk.
- **SLICE4-003 (Minor) — FIXED.** Added a pass-tone test (asserts `.kc-readiness.kc-rtone-pass`, the gate-only "via KimCad printability gate" attribution, "Medium confidence", and the score-92 gauge label) and a comparison-line test (a readiness with `comparison` set renders the history line).

Verified: vitest **43 passed** (was 37); `npm run build` clean (tsc --noEmit + vite build), committed assets regenerated; live DOM re-check confirms the reframed badge + single "Ready to print" + intact readiness card on the demo. **Roll-up: 0/0/0/0/0.**
