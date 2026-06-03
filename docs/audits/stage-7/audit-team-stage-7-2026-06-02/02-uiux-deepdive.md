# 02 — Senior UI/UX Designer deep-dive — Stage 7 (Smart Mesh readiness card)

**Date:** 2026-06-02 · **Reviewer:** Claude (audit-team, UI/UX role) · **Posture:** balanced
**Scope under review:** the Stage-7 Smart Mesh **readiness CARD** on the design screen — `frontend/src/components/RightPanel.tsx` (`ReadinessCard` / `ReadinessBody` / `ScoreGauge` + the Printability badge reframe), `frontend/src/designStatus.ts` (`readinessTone`, `gateLabel`), `frontend/src/styles.css` (`.kc-readiness` / `.kc-rtone-*` / `.kc-gauge*` / risks / recs / `.kc-sr-only`), `frontend/src/api.ts` (`ReadinessPayload` / `ReadinessRisk`).

## How I did the rendered check

Three evidence sources, stated plainly:

1. **Live served app + API (loopback).** Started the committed build via `.venv/Scripts/python.exe -m kimcad.cli web --demo --port 8788` and probed it with `curl` (read-only, localhost only — no network egress). `GET /` serves the current bundle (`/assets/kimcad.js`, `/assets/index.css`). `POST /api/design {"prompt":"a box"}` returns the PASS readiness exactly as designed: `score 92`, `verdict "Ready to print"`, `tone "pass"`, `confidence "Medium"`, `attribution "KimCad printability gate"`, `risks: []`, `comparison: null`. The demo's natural state is a PASS card (no engine, no history), so warn/fail tones, risks, and the comparison line are **not** reachable live — I assessed those from source + the `RightPanel.test.tsx` fixtures, as the brief directs.
2. **Committed Slice-4 rendered evidence.** `docs/audits/stage-7/audit-lite-slice-4-readiness-card-2026-06-02.md` — live DOM + computed-style: pass card green gauge stroke `rgb(29,122,78)`, `stroke-dasharray 92px 100px`, verdict centered, mobile 375 no-overflow gauge-centered, "Ready to print" appears exactly once after the badge reframe.
3. **Source + contrast math.** I computed WCAG 2.1 contrast for every tone color against both warm surfaces myself (not eyeballed) — see UX-002.

The JPEG `preview_screenshot` tool is a documented timeout in this env; per the brief I did **not** fail the stage for the absent JPEG, and I did **not** flag "LLM not run."

---

## Severity rollup

| Severity | Count |
|----------|-------|
| Blocker  | 0 |
| Critical | 0 |
| Major    | 0 |
| Minor    | 2 |
| Nit      | 2 |

No Blockers, no Criticals, no Majors. The card meets the UX-first acceptance bar.

---

## Findings

### UX-001 — Minor — Visual hierarchy / Information architecture
**The readiness verdict and the printability gate badge still read as two near-parallel "verdicts," one immediately under the other.**

**Evidence:** `RightPanel.tsx:382-383` stacks `<ReadinessCard>` then `<PrintabilityCard>`. The Readiness card leads with a large centered verdict ("Ready to print", `.kc-readiness-verdict`, 17px display bold, `RightPanel.tsx:229`); the Printability card, one card down, leads with a status badge ("Passed" / "Needs review" / "Failed", `gateLabel`, `designStatus.ts:42-53`, rendered `RightPanel.tsx:310-312`). The Slice-4 reframe successfully removed the *literal* string duplication (verified live: "Ready to print" appears exactly once), and that was the right move. The residual issue is hierarchy, not wording: two consecutive cards each open with a green/amber/red pass-fail judgment, so the eye still has to work out which card is the headline and which is the supporting detail.

**Why it matters:** The Readiness card is meant to be *the* "should I print this?" answer; Printability is the technical evidence that feeds it. With both cards opening on a colored verdict token, a first-time user reads two confident green statements in a row and isn't told they're the same conclusion viewed at two altitudes. This is a polish gap against an Apple-grade stacked layout, not a comprehension failure — the words now differ and the Readiness card is visibly richer (gauge + risks + recs), which already does most of the disambiguation.

**Blast radius:**
- Adjacent code: only `RightPanel.tsx` (`ReadinessCard`, `PrintabilityCard`) and `designStatus.ts` `gateLabel`. No other surface renders these two cards.
- User-facing: every completed design shows both cards; change is purely presentational.
- Migration: none. Tests to update: `RightPanel.test.tsx:115` (`getByText('Passed')`) and `designStatus.test.ts` if `gateLabel` strings change — small.

**Fix path (pick one, both cheap):**
- *Preferred:* prefix the gate badge so it self-identifies as the upstream check — `gateLabel('pass') → "Gate: passed"`, `'warn' → "Gate: needs review"`, `'fail' → "Gate: failed"`. One word reframes it from "second verdict" to "the check behind the verdict above."
- *Alternative:* add a one-line section sublabel under the Printability `<h2>` — e.g. a `.kc-card-sub` reading "The detailed check behind the readiness score" — so the relationship is stated, not inferred.

---

### UX-002 — Minor — Accessibility (contrast, confirmed sufficient) → downgraded to a watch note
**The amber/warn tone (`--kc-warn #876312`) clears AA, but with the least headroom of the three tones; worth pinning so a future palette nudge can't quietly drop it below 4.5:1.**

**Evidence:** I computed WCAG 2.1 luminance-contrast for each tone color against both warm surfaces (`--kc-surface #faf6ee`, `--kc-surface-2 #f4eee2`):

| Token | on `#faf6ee` | on `#f4eee2` |
|-------|-------------|-------------|
| `--kc-pass #1d7a4e` | **4.94:1** | 4.61:1 |
| `--kc-warn #876312` | **5.10:1** | 4.75:1 |
| `--kc-fail #a8431f` | **5.59:1** | 5.21:1 |
| `--kc-muted #6f6857` | 5.14:1 | 4.79:1 |

All three tones pass AA (4.5:1) for normal text as `--tone` on the verdict (`styles.css:1033`), gauge number (large text, 3:1 — trivially passes at 34px bold), conf-badge text (`styles.css:1048`, 11.5px = normal text, passes), and risk dots/detail. Critically, the brighter amber `--kc-warn-accent #c9962f` is used **only** as a background/dot fill (`styles.css:935, 1214, 1237`), never as text — so no thin amber text ever renders at the lower-contrast value. This is a correct, deliberate split.

**Why it's only a watch note, not a defect:** nothing here is below AA today. I am explicitly recording it as *passing* so the audit trail shows the contrast was measured, not assumed — and flagging that pass (4.94) and warn (4.75 on surface-2) sit in the 4.5–5.2 band, so any future darkening of the surfaces or lightening of the tone tokens should re-run this check.

**Fix path:** none required. Recommend adding the four ratios above as a comment near the `--kc-pass/warn/fail` definitions (`styles.css:62-65`) so the constraint is visible at the point of edit.

*(This entry is informational; it does not count against the rollup as a defect. Listed for evidence-altitude completeness per the brief's contrast ask.)*

---

### UX-003 — Minor — State / Copy — confidence blurb's tense + the "Low" path's user-facing word
**The `Low` confidence blurb uses British "analysed" and the attribution string exposes a slightly clinical phrase to the end user.**

**Evidence:** `RightPanel.tsx:185` — `CONFIDENCE_BLURB.Low = 'Provisional — the mesh could only be partly analysed.'` uses British spelling ("analysed"), while the rest of the product copy is US English (e.g. "Re-rendering", "supports", "printer's profile"). Same word appears server-side in `smart_mesh.py:210` attribution `"KimCad printability gate (mesh only partly analysable)"`, which renders verbatim as `via KimCad printability gate (mesh only partly analysable)` (`RightPanel.tsx:276`). "analysable" / "partly analysable" is engineer-altitude phrasing surfaced to the user.

**Why it matters:** Spelling drift within one product reads as inattention. The Low-confidence path is also the *most anxiety-inducing* state for a user (their part "could only be partly" checked) and currently the copy is the most technical of the three. This is the empty-confidence/degraded-data state the role checklist specifically asks to be designed, not just functional.

**Blast radius:**
- Adjacent code: `RightPanel.tsx:185` (frontend blurb) and `smart_mesh.py:210` (`_attribution`, backend). Two files, two strings; the backend string is also covered by `tests/test_smart_mesh.py` (a string change needs the assertion updated).
- User-facing: only the Low-confidence readiness path (mesh errors present) — not the common case.
- Migration: none.

**Fix path (rewrites included):**
- `RightPanel.tsx:185` → `Low: 'Provisional — the mesh could only be partly analyzed.'`
- `smart_mesh.py:210` → `"KimCad printability gate — mesh only partly checked"` (US spelling + plainer verb; "checked" matches the gate badge "Passed/Needs review/Failed" vocabulary the user already saw). Update the corresponding assertion in `tests/test_smart_mesh.py`.

---

### UX-004 — Nit — Copy — recommendation list uses a check (✓) glyph for actions the user has *not* done yet
**Evidence:** `RightPanel.tsx:264` renders each recommendation with a green `✓` (`.kc-rec-check`, `styles.css:1126` `color: var(--kc-pass)`). A checkmark conventionally connotes "done / satisfied." These are *to-do* next steps ("Add supports under the overhang.", "Slice for PLA…"), so a green check is a mild semantic mismatch — it can read as "already handled."

**Why it's a Nit:** the heading "Recommendations" (`RightPanel.tsx:239` analog at `:260`) plus the imperative verb in each item carries the meaning; the glyph is decorative and `aria-hidden`, so no assistive-tech impact. Purely a visual-affordance preference.

**Fix path:** swap `✓` for a neutral forward/action marker — an arrow (`→`) or a small bullet — keeping the green tint if desired. One-character change in `RightPanel.tsx:265`.

---

### UX-005 — Nit — Visual hierarchy — gauge is a *half* arc but the number sits low in its bounding box
**Evidence:** `ScoreGauge` draws a semicircular arc (`viewBox 0 0 120 70`, `RightPanel.tsx:205`) with the number absolutely positioned at `bottom: 2px` (`styles.css:1011`). Centering the big number under a half-gauge is the right call, but at small column widths the 34px number's baseline crowds the arc's open bottom edge. The Slice-4 mobile-375 check found "gauge centered (188 vs 187.5)" with no overflow, so this is cosmetic spacing, not a layout break.

**Fix path:** optional — nudge `.kc-gauge-num { bottom: 2px → 6px }` or reduce the viewBox bottom padding so the number sits visually centered in the arc's mouth. Verify against the same mobile-375 DOM check.

---

## What's working (specific credit)

- **The worst-of-two honesty, surfaced as a card.** `smart_mesh.assess_readiness` takes `max(kc_tone, pp_tone)` (`smart_mesh.py:170`) so the verdict is never more optimistic than either KimCad's own gate *or* the cited PrintProof3D engine — and the UI renders that honesty faithfully: the confidence badge + `CONFIDENCE_BLURB` (`RightPanel.tsx:182-186`) name *exactly* what backed the call ("Medium" / "From KimCad's printability gate." for the gate-only path — confirmed live; "High" / "Validated by the PrintProof3D engine." only when the engine ran). The card never overstates. This is the spec's "PrintProof3D is the engine, not Smart Mesh itself" made visible, and it's the single best UX decision in the slice.
- **The local `--tone` mechanism.** `.kc-rtone-{pass,warn,fail}` set *only* a scoped `--tone` color (`styles.css:964-978`), consumed by the gauge fill, the verdict text, the conf-badge, and each risk dot — deliberately **not** the `.kc-tone-*` full-background badge classes. One class flips the whole card's semantic color through a single variable, with no background flood and a smooth `stroke 0.3s` transition (`styles.css:1003-1005`). Clean, maintainable, and visually restrained.
- **The badge reframe (UX-001's parent fix) is genuinely good.** Slice 4 caught the literal "Ready to print" duplication and `gateLabel` now returns "Passed / Needs review / Failed" (`designStatus.ts:42-53`) — verified live to appear once. The fix is documented in code with intent comments. UX-001 is the *residual* hierarchy nuance, not a regression.
- **The gauge is honest and accessible.** `pathLength={100}` makes the dash equal the score directly (`RightPanel.tsx:212-213`), so the fill is a true 0–100 proportion independent of the arc's real length; `Math.max(0, Math.min(100, …))` clamps defensively. `role="img"` + `aria-label="Readiness score 92 out of 100"` (`RightPanel.tsx:206`) gives assistive tech the number, and the score also renders as plain text (`.kc-gauge-num`) — never color-only.
- **Per-risk severity is no longer color-only.** Each risk carries a `.kc-sr-only` severity word via `RISK_TONE_WORD` (fail → "Critical risk", warn → "Warning", `RightPanel.tsx:190-194, 247`) ahead of the title, so the warn/fail *tier* has a non-color text equivalent (WCAG 1.4.1); the dot and the rec check are correctly `aria-hidden`. The `RightPanel.test.tsx:151` assertion pins "Warning:" so a regression that dropped it fails CI. **Nothing on the card is conveyed by color alone.**
- **Stale-comparison-on-drag is not a defect.** `ReadinessBody` is a pure function of its `readiness` prop — `{readiness.comparison && <p …>}` (`RightPanel.tsx:274`) with no local state caching the line. A re-render that returns a fresh result with `comparison: null` re-renders the body and the history line simply disappears; there is no `useState`/ref retaining a previously shown comparison (contrast the deliberate slider-value retention in `ParametersCard`, which is scoped to params only). So the Slice-5 watch item — "does a drag leave a stale comparison line?" — resolves **clean**: the card clears it. Confirmed by code structure; the comparison-present branch is also unit-tested (`RightPanel.test.tsx:186-200`).
- **Robust to sparse data.** Every optional section is guarded (`risks`/`recommendations` by `length > 0`, `comparison`/`confidence`/`attribution` by truthiness), with idle and failed placeholders that mirror the sibling cards (`RightPanel.tsx:287-298`). No `undefined.map`, no blank screen — the empty, populated, and failed states are all designed.

## Watch items (no action required this stage)

- **Export affordance vs an engine-on fail readiness.** Today readiness tone tracks the gate exactly (engine off), so a "Not print-ready" card always coincides with a blocked export. They can only diverge once PrintProof3D ships *enabled* and returns a fail the deterministic gate didn't. Reconcile (gate export on `readiness.tone === 'fail'`, or a proceed-anyway confirm) before the engine ships on. Same boundary as Slice-3's SLICE3-001.
- **Risk React key collision.** `key={`${r.title}:${r.detail}`}` (`RightPanel.tsx:244`) collides if two risks share an identical title+detail. Not reachable from current engine output; noting for completeness.
