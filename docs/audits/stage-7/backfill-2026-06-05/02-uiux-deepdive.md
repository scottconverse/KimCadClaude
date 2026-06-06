# Stage 7 — UI/UX Deep-Dive: Smart Mesh Readiness Card

**Role:** Senior UI/UX Designer (independent, adversarial)
**Date:** 2026-06-06
**Branch:** `stage-0-7-audit-backfill` (head `800016a`)
**App under test:** running demo, `http://127.0.0.1:8765/` (`kimcad web --demo`), live-driven via preview tools
**Scope:** the Smart Mesh readiness card — gauge, verdict, confidence badge, risks (+ tone treatment), recommendations, history line, per-risk viewport highlight; visual hierarchy, interaction states, copy honesty, accessibility, mobile.
**Method:** drove the real app to every reachable state; all load-bearing claims (esp. contrast) verified by DOM computed-style measurement + WCAG math, not screenshot alone. Viewports: desktop 1280 and mobile 390.

---

## States reached (evidence of coverage)

| State | How reached | Result |
|---|---|---|
| Idle / never-designed | `New design` → before submit | Helpful muted placeholder copy ✓ |
| Pass | default demo box ("a 40 mm desk cable clip") | score 92, "Ready to print", green, Medium confidence, gate-only ✓ |
| Warn (rich, PrintProof3D) | refined part ("Make it taller") | score 74, "Printable with notes", amber, **High confidence**, located overhang risk, recommendations, **history line**, PrintProof3D attribution ✓ |
| Fail (gate-failed) | `demo:gatefail` → "Try the experimental generator" | score 38, "Not print-ready", red, two critical gate risks (no geometry → plain rows), Gate: Failed ✓ |
| Risk with no geometry | gate-derived risks in the fail state | render as non-clickable plain rows (correct) ✓ |
| Located risk (geometry) | the overhang risk in the warn state | renders as a `<button>`, focusable, "⊙ on model", toggle + legend ✓ |
| Loading | transient during build | a brief busy state; not a designed skeleton (see UX-005) |

The **warn-via-gate-only** path and a **Low-confidence (mesh-unanalyzable)** path were **not reachable** through the running demo (the slider can't drive a wall below the 0.8 mm minimum, and the demo never produces an unanalyzable mesh). Those states' tokens were verified statically from source; their *runtime* rendering is unverified here and is itself a coverage note (UX-007).

---

## What's working (specific credit)

- **The pass-text green fix holds.** The recent AA-safe deep-green token (`--kc-pass-text` #15633d) does its job: the pass verdict measures **6.26:1** and the pass confidence badge **5.62:1** on the warm card surface — comfortably past AA. The split between fill-green (gauge) and text-green (labels) is exactly the right instinct.
- **Tone is never conveyed by color alone.** Each risk carries a screen-reader-only severity word ("Critical risk:" / "Warning:" / "Note:") via `.kc-sr-only`, verified present in the DOM. WCAG 1.4.1 is genuinely satisfied, not just claimed.
- **The gauge has a real text equivalent.** `role="img"` + `aria-label="Readiness score N out of 100"`, and the aria value tracks the visible number (verified 74↔74). A non-sighted user gets the score.
- **Honest attribution.** The card distinguishes advisory from authority well: "via KimCad printability gate" vs "via PrintProof3D validation engine", and the confidence blurb states the basis ("From KimCad's printability gate" / "Validated by the PrintProof3D engine"). Confidence (High/Medium/Low) is mapped to whether the deeper engine actually ran. This is exactly the right honesty posture for a "should I print this?" verdict.
- **The verdict never out-runs the risks.** Source + observed behavior confirm tone = worst of the KimCad signal and the PrintProof3D status, so "Ready to print" is never shown over a risk. Good restraint.
- **Recommendations use a forward arrow, not a check.** A green check would read as "already done"; the `→` reads as "next step." Thoughtful.
- **The located-risk interaction is well-built.** The risk becomes a real `<button>` with a descriptive `title`, a visible `:focus-visible` outline (2px solid tone), and a 62 px tall hit area. The "Show on model" toggle works and gates the legend/clickability only when geometry exists.
- **InfoTip is a model disclosure.** Real `<button>`, descriptive `aria-label`, `aria-expanded`, `aria-controls` (set only when open), `role="note"` panel, dismissed by Escape and outside-click/focus-out. This is better accessibility than most shipping products.
- **Mobile holds together.** At 390 px: no horizontal overflow, card fits (362 px), gauge centered, sticky "Check & download" CTA, risks/legend/recommendations all legible.

---

## Findings

### UX-001 (Major) — Warn confidence badge fails WCAG AA contrast
- **Category:** Accessibility / Color
- **Evidence:** warn state, `.kc-conf-badge` "High confidence"/"Medium confidence", desktop+mobile. Computed: text `--kc-warn` `rgb(135,99,18)` on the badge's warn tint `rgb(234,225,207)` (`color-mix(--kc-warn 14%, surface)`) = **4.23:1**. AA for this size (11.5 px, not large) requires 4.5:1.
- **Why this matters:** The confidence badge is small, load-bearing text — it tells the user how much to trust the verdict. The pass badge (5.62) and fail badge (4.57) both clear; **only the warn badge misses**, and warn is the single most common non-trivial outcome (any part with one caution lands here). The card-level prompt specifically asked to confirm the verdict/badge clear AA — the *verdict* does (4.72, large text needs only 3.0), but the *small badge* does not.
- **Blast radius:**
  - Adjacent code: `styles.css` `.kc-conf-badge` uses `color: var(--tone-text)` and `background: color-mix(in srgb, var(--tone) 14%, var(--kc-surface))`. For warn, `--tone-text` == `--tone` == `--kc-warn`; the tint reduces the effective contrast below the flat-surface value (4.72 → 4.23).
  - Shared state: `--kc-warn` (#876312) and the `14%` tint recipe are reused by the located-risk hover (`color-mix(--tone 12%)`) and the warn risk dot. A token darken affects only text-on-tint, not the dots.
  - User-facing: the warn confidence badge becomes legible to low-vision users; no layout change.
  - Migration: none.
  - Tests to update: none known (no contrast assertion exists — see UX-006 / cross-ref TEST report).
  - **Fix path:** introduce a darker warn *text* token mirroring the pass split — e.g. `--kc-warn-text: #6f5210` (deeper than #876312) and set `--tone-text: var(--kc-warn-text)` in `.kc-readiness.kc-rtone-warn`. `#6f5210` on the warn tint computes ≈ 5.7:1; on flat surface ≈ 6.4:1. Re-verify the located "⊙ on model" label (also `--tone`, 11 px) after the change — it currently measures 4.72 on flat surface (passes) but should adopt the same text token for consistency.

### UX-002 (Minor) — InfoTip and "Show on model" tap targets below 44×44
- **Category:** Accessibility / Responsive
- **Evidence:** mobile 390. `.kc-infotip-btn` measures **15×15 px**; the native "Show on model" checkbox measures **13×13 px**. WCAG 2.5.5 (and Apple HIG) call for ≥44×44 (AAA is 44; AA 2.5.8 is 24×24 minimum — the InfoTip also misses 24).
- **Why this matters:** On a phone these are fiddly to hit. The checkbox is partly mitigated by its text label extending the row's tap width (~107 px), but the row is only ~19 px tall, and the InfoTip "i" is a standalone icon with no expanded hit area — it misses even the 24 px AA floor.
- **Blast radius:**
  - Adjacent code: `.kc-infotip-btn` is reused on every card title and jargon term across the right panel (Readiness, Printability, confidence, risks, recommendations, gate) — fix once, applies everywhere. `.kc-hl-toggle input` is readiness-only.
  - User-facing: easier tapping on mobile across all in-app help affordances.
  - Migration: none.
  - **Fix path:** give `.kc-infotip-btn` a ≥24 px (ideally 44 px) hit area via padding + negative margin (so layout is unchanged) or a `::before` overlay; bump the checkbox's effective target by making the whole `.kc-hl-toggle` label ≥44 px tall on coarse pointers (`@media (pointer: coarse)`).

### UX-003 (Minor) — Legend swatch colors don't match the card's risk-dot colors
- **Category:** Visual consistency
- **Evidence:** warn state. Legend "issue" swatch = `#e5484d` (bright red) and "caution" swatch = `#f5a623` (bright orange); the corresponding risk **dots** render `--kc-fail` `#a8431f` (rust) and `--kc-warn` `#876312` (olive). Two different reds and two different ambers for the same severity within one card.
- **Why this matters:** The legend is teaching a color language ("orange = caution"), but the list row right beside it shows an olive dot for that same caution. The swatches intentionally match the *3D viewport* highlight colors (so the legend explains what's on the model), but a user reads the legend and the dots in one glance and sees a mismatch. It's a small honesty-of-signal gap, not a defect.
- **Fix path:** either (a) align the on-model highlight palette to the card tones (`--kc-warn`/`--kc-fail`) so dot, swatch, and highlight are one color per severity; or (b) keep the bright highlight palette but label the legend explicitly as "on-model colors" and make the card dots visually echo them. Option (a) is cleaner and removes a whole second palette. Recommend (a).

### UX-004 (Minor) — Gauge number is read twice by screen readers
- **Category:** Accessibility
- **Evidence:** `.kc-gauge` carries `aria-label="Readiness score 74 out of 100"`; the sibling `.kc-gauge-num` ("74/100") is **not** `aria-hidden`. A screen reader announces both the SVG label and the visible "74 /100" text, and the `<i>/100</i>` may read as "74 100" / "74 slash 100".
- **Why this matters:** Minor verbosity/awkwardness for SR users; the number is already fully conveyed by the SVG's aria-label.
- **Fix path:** add `aria-hidden="true"` to `.kc-gauge-num` (it's purely the visual presentation of the value the SVG already labels).

### UX-005 (Minor) — Loading state is not a designed skeleton
- **Category:** State
- **Evidence:** during a build the readiness card shows the idle muted placeholder until the result arrives; there is no in-card loading/skeleton treatment specific to "assessing readiness." The demo build is sub-second so this is barely felt, but a real local-LLM design can take many seconds.
- **Why this matters:** On real (non-demo) hardware the gap between submit and result is long enough that a skeleton or "Assessing…" state would reassure the user the readiness verdict is coming. Out of the demo's reach to observe, so flagged Minor.
- **Fix path:** add a lightweight skeleton (gauge ghost + two shimmer lines) keyed to the busy state, or an explicit "Checking print-readiness…" line in the card during assessment.

### UX-006 (Minor) — No automated contrast guard for tone tokens
- **Category:** Process / Accessibility (cross-cuts the Test report)
- **Evidence:** UX-001 (warn badge 4.23) shipped on a branch whose stated bar is zero findings, and the prior pass-text fix shows the team is contrast-aware — but there is no test asserting the readiness tone tokens clear AA against their actual backgrounds (flat surface AND the badge tint). A pure unit test over the documented color tokens would have caught the warn-badge miss.
- **Fix path:** add a small contrast unit test that, for each tone (pass/warn/fail), asserts verdict-on-surface ≥3.0 (large) and badge-text-on-tint ≥4.5 (small). Token math only; no browser needed. (See TEST deep-dive for placement.)

### UX-007 (Nit) — Warn-gate-only and Low-confidence states unverified at runtime
- **Category:** Coverage note
- **Evidence:** the running demo can't drive a gate-only WARN (wall slider floors at 0.8 mm = the minimum) or a Low-confidence/mesh-unanalyzable readiness. Their tokens were checked statically (warn text on flat surface = 4.72) but their assembled rendering wasn't observed.
- **Fix path:** add demo keyword scenarios (e.g. `demo:warn`, `demo:lowconf`) mirroring the existing `demo:gatefail`/`demo:experimental` hooks, so every readiness tone + confidence tier is exercisable by hand in the live demo (and by QA).

---

## Cross-cutting note

The card's information architecture and honesty are genuinely strong — this is a well-designed "should I print this?" surface, and the advisory-vs-authority framing is exactly right for a tool that must not overstate readiness. The one real release-gating item is **UX-001 (warn badge contrast, Major)**; everything else is polish. The warn tone is the most-traveled non-trivial path, which is why its small-text token miss earns Major rather than Minor.

---

## Severity rollup (this role)

- Blocker: 0
- Critical: 0
- Major: 1 (UX-001)
- Minor: 5 (UX-002..006)
- Nit: 1 (UX-007)
- **Total: 7**

**Verdict:** NOT a clean pass against a zero-findings bar. One Major (warn confidence-badge contrast below AA) must be fixed before release; five Minors and one Nit should follow. No Blockers/Criticals — the card is otherwise release-quality and a credit to the UI-first priority.
