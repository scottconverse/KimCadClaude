# UI/UX Deep-Dive — KimCad Stage 5 (live parameter sliders)

**Audit date:** 2026-06-02
**Role:** Senior UI/UX Designer
**Scope audited:** The Stage 5 live-slider surface — the Parameters card (sliders, debounced re-render, server-truth re-sync, updating/error/read-only states) and the viewport's quiet-swap behavior during re-render. Files: `frontend/src/components/RightPanel.tsx` (SliderRow + ParametersCard), `frontend/src/components/Viewport.tsx`, `frontend/src/App.tsx`, `frontend/src/components/Workspace.tsx`, `frontend/src/styles.css`. Design reference: `docs/design/prototype/jsx/panels.jsx` + `styles.jsx` (the v3.0 ParamPanel) and `docs/design/KimCad-Unified-Product-Spec-v3.0.md` §4.2 / §5.2.
**Auditor posture:** Balanced.

---

## TL;DR

The marquee Stage 5 deliverable — template parameters exposed as live sliders that re-render locally in under a second with no LLM round-trip (§4.2, §5.2) — is built well and lands the hard parts: the deterministic invariant is honored (the frontend never computes geometry, it edits values and asks the backend to render), a rapid drag coalesces to exactly one debounced POST, the server's clamped values become the new truth, stale responses can't clobber newer geometry, and the previous mesh stays framed during a re-render so the viewport never blanks. Visual fidelity to the Workshop "ParamPanel" prototype is near-exact (track-fill gradient, mono value readout, thumb treatment). The strongest dimension is interaction correctness; the weakest is touch-target sizing on mobile, where the slider is the one interactive control the codebase's own 44px coarse-pointer floor forgets to cover. Nothing here blocks the gate. The single most important takeaway: ship it, and fold in the mobile touch-target fix and a couple of copy/affordance polish items, because this is the feature a maker will touch most and it should feel as considered as the rest of the Workshop system.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 3 |
| Nit | 4 |

## What's working

- **The deterministic, sub-second re-render is real and felt.** Rendered live against the `--demo` server: a rapid five-step Width drag (120→140→160→180→200) collapsed to exactly **one** `POST /api/render/2`, which returned a cache-busted `/api/mesh/2?v=1` the viewport loaded. The slider and the Printability X-actual both re-synced to the server's truth (200, then 100 on a second drag). This is the §4.2 "slider change re-renders in < 1 s, local, no LLM" criterion, demonstrated end-to-end. `RightPanel.tsx:94-103`, `App.tsx:54-70`.
- **Server truth wins, visibly.** `ParametersCard` re-syncs local slider state to `result.parameters` on every result change (`RightPanel.tsx:81-87`), so a value the backend clamps replaces the local one rather than the reverse. Confirmed in the DOM: after the render returned width=200, the slider read 200 and the printability dims read X actual 200.
- **The viewport swap is genuinely quiet.** `Viewport.tsx`'s `hasModel` gate (`:22`, `:75-87`) suppresses the full-cover "Rendering…" overlay while a part is framed; `KCViewport.loadMesh` swaps atomically so the old mesh stays until the new one lands. No flash, no blank — exactly the behavior the spec's print-aware preview implies.
- **Fidelity to the Workshop design language is high.** The slider markup and CSS are a faithful port of the prototype `ParamPanel` (`panels.jsx:127-159`, `styles.jsx:84-97`): same `.kc-prow` / `.kc-plabel` / `.kc-pval` structure, same `--pct` linear-gradient track fill in terracotta, same 17px ringed thumb, same mono value with a muted unit. Track-fill percentage matched the value exactly at every slider (29.17% at 80/[10,250], 12.5% at 40, 16.67% at 2/[0.8,8]).
- **Accessibility was taken seriously for the slider value.** `aria-valuetext` carries the unit ("80 mm", "2 mm") so a screen reader doesn't drop the "mm" the way bare `aria-valuenow` would (`RightPanel.tsx:46-48`) — verified live on all four sliders. `:focus-visible` gives the slider a 2px accent ring with offset (`styles.css:857-860`), and `prefers-reduced-motion` is globally respected (`styles.css:602-610`).
- **Honest, non-technical copy across the states.** The card subtitle ("Drag a slider — the part re-renders locally in under a second, no AI round-trip."), the read-only LLM note, and the gate labels ("Ready to print" / "Printable — with notes" / "Not printable yet", `designStatus.ts:23-34`) are all plain-English and action-oriented. No raw codes surface to the user.
- **Layout is clean at both breakpoints.** Desktop (1280) and mobile (375): 4 sliders, no label/value overlap, no document horizontal scroll, no slider overflowing its column. Mobile stacks the workspace to a single column and the touch `@media` fattens the track from 5px to 9px.

## What couldn't be assessed

- **The brief "Updating…" note in the live demo.** The note is conditionally rendered with `role="status"` (`RightPanel.tsx:109-113`) and is verified present in source, but in the `--demo` server the deterministic box render completes faster than the in-flight window, so it didn't persist long enough to capture in the DOM during a poll. Its existence, copy, and live-region role are confirmed by source; its on-screen dwell time on a real (slower, non-demo) render wasn't measurable here. This is an environment artifact, not a gap.
- **Real screenshots (JPEG).** The Claude_Preview screenshot path is broken in this environment (confirmed, consistent with the Slice-4 audit-lite note). All rendered findings below are from **live DOM + computed-style + bounding-box inspection plus the real `/api/render` network round-trip** at desktop (1280) and mobile (375) — for layout, overlap, clipping, color, track-fill, and the re-render behavior this is at least as strong as a static image, and stronger for the interaction. Stated plainly per the audit protocol; the gate is **not** failed for the absent JPEG.

---

## First impressions

Arriving at the workspace after designing "a box," the Parameters card reads immediately as the place to shape the part: a clear "Parameters" title, a one-line invitation to drag, and four labelled sliders each showing its current value in mono with a quiet unit. The terracotta track-fill makes the current position legible at a glance. Dragging feels direct — the value readout updates as you move, and the 3D preview reshapes a beat later without ever blanking. It feels like a tool that respects the maker: no AI spinner, no "thinking," just a part that changes when you move a control. The one thing that doesn't quite match the polish: on a phone the slider thumb is a little small to grab confidently relative to every other control on the screen, which all feel comfortably tappable.

## Journey walkthroughs

### Journey: Design a template part → tune it with sliders → see it stay printable

1. **Describe → design.** Prompt "a box" → the box renders, the Parameters card fills with Width/Depth/Height/Wall sliders at the plan's values, the Printability card shows "Ready to print" with matching dims. Clean.
2. **Drag a slider.** Move Width. The value readout tracks the thumb live; ~150 ms after the last move a single `/api/render` fires; the viewport swaps the mesh underneath without a blanking overlay; the slider and the printability dims re-sync to the server's returned values. This is the core loop and it's tight.
3. **Drag past a sensible range.** For `snap_box` the slider bounds sit inside the build volume, so a clamp/gate-fail isn't reachable by dragging here — a nice implicit safety property, though it means the "drag-to-fail → model still downloads" path the spec cares about isn't exercised by this family. The structural handling exists (a re-render that flips to gate-FAIL versions the mesh, which `ExportPanel` keys off to disable browser slicing while keeping the model download), but it isn't *demonstrable* from the slider UI for snap_box. Noted, not faulted.
4. **LLM-backed part (tier distinction).** A model-authored part shows the read-only Type/Size summary and the "no adjustable template parameters" note instead of sliders. By design (a tier distinction, not a gap) — and the copy handles it gracefully. See UX-005 for one phrasing nit.

No dead ends encountered in the slider flow. The error path (re-render POST fails) surfaces an actionable message and invites a retry (UX-002 covers a small wording issue).

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion

### [UX-001] — Minor — Accessibility / Responsive — Slider touch target is below the comfortable floor on mobile, and is the one control the 44px coarse-pointer rule skips

**Evidence**
Mobile (375px), live computed style. The `<input type="range" class="kc-range">` element's box is exactly **9px tall** with `padding: 0` (`styles.css:868-880` sets the touch `@media` track height to 9px; the thumb pseudo-element fattens to 26px). The element box that governs the along-track tap region is therefore a 9px strip, and the thumb grab is ~26px — both under the WCAG 2.5.5 / spec §4.2 "full keyboard nav + AA" comfortable-target expectation, which the project itself operationalizes as 44px. The coarse-pointer rule that gives every other control that floor —
```css
@media (pointer: coarse) {
  .kc-btn, .kc-icon-btn, .kc-chip, .kc-field select { min-height: 44px; }
}
```
(`styles.css:579-586`) — **omits `.kc-range`**. So the slider, the most-touched control of the marquee feature, is the single interactive element that doesn't get the 44px treatment.

**Why this matters**
On a phone a maker drags these sliders constantly. A 26px thumb and a 9px track strip make precise grabs and click-to-set-on-track fiddly, and disproportionately affect users with larger fingers or motor-control differences — exactly the population the 44px floor exists for. It's also an internal inconsistency: the design system clearly *intends* 44px for touch (it's coded for four other control types) and just missed the one that needs it most.

**Blast radius**
- Adjacent code: `styles.css` `.kc-range` touch block (`:868-880`) and the coarse-pointer rule (`:579-586`). Single file, two adjacent rules.
- User-facing: every mobile/tablet (coarse-pointer) user of the slider flow; no change for mouse users.
- Tests to update: none known (no test asserts touch-target geometry; consider adding one alongside the fix).
- Related findings: none; this is self-contained.

**Fix path**
Give the range a 44px-tall transparent hit area on coarse pointers while keeping the 9px visual track. Add `.kc-range` to the coarse-pointer `min-height: 44px` list, and pad the input so the box grows without thickening the painted track — e.g. in the `@media (max-width: 640px)` block:
```css
.kc-range { min-height: 44px; padding: 17px 0; background-clip: content-box; }
```
(or set the track via a `::-webkit-slider-runnable-track` of 9px inside a 44px input). Verify the track gradient still aligns after the padding. Bumping the thumb from 26px toward ~28-30px wouldn't hurt either.

---

### [UX-002] — Minor — Copy — The re-render error message reads slightly machine-ish and doesn't fit the warm voice of the rest of the card

**Evidence**
`RightPanel.tsx:131-135`. On a failed re-render the card shows:
> "Couldn't re-render: {rerenderError}. Adjust a slider to try again."

`rerenderError` is the raw thrown message (`App.tsx:64-66`, falling back to "Re-render failed."). Concatenating a colon-prefixed raw error into the sentence can produce things like "Couldn't re-render: Request failed (HTTP 500). Adjust a slider to try again." — the technical tail clashes with the otherwise plain-English voice ("Drag a slider — the part re-renders locally…").

**Why this matters**
The spec's failure-taxonomy rule (§5.7) is "every error state presents a concrete next action" in human terms. The next action ("adjust a slider") is good; the raw `HTTP 500` leakage is the kind of machine-noise the rest of the product carefully avoids. UX is priority #1, and this is the only place in the slider surface where a raw code can reach the user.

**Blast radius**
- Adjacent code: `RightPanel.tsx:131-135`; the message source in `App.tsx:54-70`.
- User-facing: only the re-render-failure path (rare in the local/deterministic flow, but the spec demands every state be designed).
- Tests to update: `RightPanel.test.tsx` if it asserts the exact error string.
- Related findings: none.

**Fix path**
Lead with the human sentence and demote the technical detail. Suggested rewrite:
> "That change didn't render. Your last version is still here — nudge a slider to try again."
Keep the raw `rerenderError` only as a secondary, smaller line (or a `title=`/tooltip) for the curious, not inline in the primary sentence. This also reassures the user that the previous part is intact (which it is — the viewport keeps the last mesh), a fact the current copy doesn't convey.

---

### [UX-003] — Minor — State — The "Updating…" note is the only feedback for an in-flight re-render, and it has no minimum dwell, so on fast renders the user gets no perceptible "something happened" signal

**Evidence**
`RightPanel.tsx:109-113` renders the `role="status"` "Updating…" note only while `rerendering` is true. In the `--demo` server the deterministic render returns faster than the note can visibly persist (it never appeared during DOM polling at ~30 ms cadence; the network showed the round-trip completing near-instantly). The viewport swap is intentionally quiet (no overlay), so on a fast machine a drag can produce a value change with no other transient acknowledgement that a re-render ran.

**Why this matters**
This is a subtle one and arguably a feature (quiet = calm). But §4.2's "any operation over 1 s shows progress" implies the inverse intent — sub-second ops can be silent — so this is defensible. The risk is only on borderline-latency renders where the note flickers for a few frames (visual jitter) rather than reading as a deliberate state. Flagging at Minor so the team decides intentionally rather than by accident.

**Blast radius**
- Adjacent code: `RightPanel.tsx:108-114`; the `rerendering` flag in `App.tsx`.
- User-facing: every re-render; the effect is most visible on machines where render time hovers around the perception threshold (~100-300 ms).
- Tests to update: none known.
- Related findings: none.

**Fix path**
Optional, low-priority: give the note a small minimum visible duration (e.g. keep it for ≥250 ms once shown) so it reads as a deliberate flash rather than a flicker, OR accept the quiet-swap as the intended design and document it. Recommend the latter unless think-aloud testing shows users feel the drag "did nothing" — the quiet swap is genuinely nice. Either way, make it a decision, not a default.

---

### [UX-004] — Nit — Visual hierarchy / Pattern — Sliders dropped the prototype's per-axis tag chip (W/D/H), losing a small scannability affordance

**Evidence**
The prototype `ParamPanel` renders an axis chip next to the label — `<span>{d.label}{d.axis && <i className="kc-axis">{d.axis}</i>}</span>` (`panels.jsx:144`), styled as a small mono pill (`styles.jsx:89-90`). The shipped `SliderRow` renders only the label text (`RightPanel.tsx:35-36`); there's no `.kc-axis` chip and no `axis` field on `ParamSpec`. So "Width / Depth / Height" no longer carry the compact X/Y/Z tag that ties a slider to the viewport's dimension pills.

**Why this matters**
Minor scannability and cross-reference loss: the viewport shows W/D/H dimension pills, and the axis chip was the visual bridge between "the Width slider" and "the X pill on the model." Its absence is not wrong — the labels are clear — but it's a small step down from the reference design's considered detail.

**Blast radius**
- Adjacent code: would touch `ParamSpec` (add optional `axis`), the backend parameter snapshot, `SliderRow`, and restore `.kc-axis` CSS. Cross-cuts FE+BE, hence Nit not Minor (cost > benefit unless cheap).
- Related findings: none.

**Fix path**
Optional. If the backend can cheaply emit an `axis` hint for dimensional params, restore the `.kc-axis` chip from the prototype so dimensional sliders read "Width [X]" etc., echoing the viewport pills. Skip if it requires non-trivial backend plumbing.

---

### [UX-005] — Nit — Copy — The LLM-backed read-only note explains the limitation but doesn't point forward

**Evidence**
`RightPanel.tsx:153-156`:
> "This part was written by the model, so it has no adjustable template parameters. You can still slice and download it."

**Why this matters**
Good, honest copy — it states the tier distinction (by design) and gives a next action (slice/download). The Nit: "written by the model" is slightly insider-y, and the note frames the absence as a limitation rather than offering the conversational refinement path that *is* available for these parts ("make it wider" via chat, per §5.2). A maker might read "no parameters" as "I can't change this," which isn't true.

**Blast radius**
- Adjacent code: `RightPanel.tsx:153-156`. Copy-only.
- Related findings: none.

**Fix path**
Optional rewrite:
> "This part was generated directly, so it doesn't have preset sliders — but you can still refine it in chat ("make it 10 mm taller"), and slice and download it as-is."
Only if the chat-refinement path is actually wired for LLM parts at this stage; if not, leave the current copy (it's already honest).

---

### [UX-006] — Nit — Copy — "Updating…" vs the subtitle's "under a second" set slightly different expectations

**Evidence**
The card subtitle promises "re-renders locally in under a second" (`RightPanel.tsx:118-119`); the in-flight note says "Updating…" (`:111`). Minor: "Updating" is generic where the rest of the card is specific and confident about speed.

**Why this matters**
Trivial. The two strings are both fine; "Updating…" just under-sells the sub-second promise the subtitle makes.

**Fix path**
Optional. "Re-rendering…" would tie the note to the subtitle's vocabulary, or leave "Updating…" — it's perfectly clear. Lowest priority.

---

### [UX-007] — Nit — Accessibility — Programmatic focus shows a ring; confirm `:focus-visible` doesn't fire on pointer-drag (keyboard-only intent)

**Evidence**
The slider uses `:focus-visible` for its ring (`styles.css:857-860`) — correct, this is the keyboard-only selector. When I called `.focus()` programmatically the computed outline showed solid ~2px; that's expected for scripted focus and does not prove a mouse-drag will show the ring. I could not fully isolate pointer-drag vs keyboard focus behavior in this harness.

**Why this matters**
If a mouse drag were to trigger the visible ring it'd be visual noise, but `:focus-visible` is specifically designed to avoid that, and the CSS uses it correctly. This is a "confirm in a real browser with mouse vs Tab" item, not a defect — flagged so a manual pass closes it.

**Fix path**
During the moderated usability pass, Tab to a slider (ring should show) then mouse-drag another (ring should not persist). The code is correct by construction; this is verification only.

---

## States audit matrix

| Component / state | Default | Loading/in-flight | Empty | Error | Re-synced | Notes |
|---|---|---|---|---|---|---|
| Parameters card — template part | ✓ sliders at plan values | ✓ "Updating…" (`role=status`) | ✓ "parameters appear here once designed" | ✓ re-render error w/ retry (UX-002) | ✓ re-syncs to server truth | UX-001 (touch), UX-003 (dwell) |
| Parameters card — LLM part | ✓ read-only Type/Size + note | n/a (no sliders) | — | — | — | UX-005 copy nit |
| Viewport during re-render | ✓ last mesh stays | ✓ quiet swap, no overlay | ✓ "Your 3D preview appears here." | ✓ overlay only when no model to fall back to | ✓ versioned mesh | Solid degradation design |
| Printability card | ✓ badge + dims + findings | follows result | ✓ "appears after a part is designed" | gate-fail badge | ✓ dims re-sync on render | Copy well-considered |

No missing states. Every state the slider surface can enter is designed and carries a next action.

## Accessibility snapshot

- **Keyboard navigation:** Sliders are native `<input type="range">`, so arrow-key adjustment and Tab focus work for free. `:focus-visible` ring present (UX-007 is verification-only). Good.
- **Focus visibility:** 2px accent ring with 4px offset on `:focus-visible` (`styles.css:857-860`). Good.
- **Color contrast:** Tokens are documented to clear AA (`styles.css:54-59` comment); value text is `--kc-ink` on `--kc-surface` (high contrast), units are `--kc-muted` (smaller, secondary). Track fill is the brand terracotta on a hairline rail — decorative, not text, so AA-exempt. No contrast concerns sampled in the slider surface.
- **Screen reader labeling:** `aria-label` per slider + `aria-valuetext` with the unit (verified live: "80 mm", "2 mm"). This is the right pattern and was done deliberately. Strong.
- **Reduced motion:** Globally honored (`styles.css:602-610`); viewport auto-rotate is also disabled. Good.
- **Touch target size:** **The one weak spot** — slider is 9px box / 26px thumb on mobile and is excluded from the 44px coarse-pointer floor (UX-001). Every other control gets 44px.

## Patterns and systemic observations

- **The deterministic-invariant pattern is the quiet hero.** The slider UI never computes geometry; it sends a value map and renders the server's answer. This is correct, secure (no client-side CAD), and the reason the re-render is fast and trustworthy. It's consistent with the spec's Tier-1 deterministic-template philosophy and should be held as the model for any future direct-manipulation control.
- **The Workshop design system is being applied faithfully and consistently.** The slider port reuses the exact token vocabulary, radii, fonts, and the `--pct` track-fill technique from the prototype. The one systemic miss (the 44px touch floor not covering `.kc-range`) is a single-rule omission, not a pattern problem.
- **Quiet-by-design feedback** (no spinner on re-render, last mesh persists) is a mature choice that suits a maker tool. The only caution (UX-003) is to make the quietness deliberate, not accidental, and confirm it in think-aloud testing.

## Appendix: surfaces reviewed

- Route: `http://localhost:8782/` (KimCad `--demo` server, snap_box, 4 sliders).
- Viewports: desktop 1280×860, mobile 375×812.
- Live checks: slider count (4), `aria-label` / `aria-valuetext` / min / max / step per slider, track-fill `--pct` vs computed value (exact match), label/value overlap (none), document horizontal scroll (none), column overflow (none), mobile single-column stack + 9px touch track, the full drag→debounce→single `POST /api/render`→versioned mesh→re-sync round trip (network-verified), slider + printability re-sync to server truth (200, then 100), gate badge copy ("Ready to print"), `:focus-visible` ring (programmatic).
- Source reviewed: `RightPanel.tsx`, `Viewport.tsx`, `App.tsx`, `Workspace.tsx`, `api.ts`, `designStatus.ts`, `styles.css`; design reference `panels.jsx`, `styles.jsx`, spec §4.2/§5.2/§5.7.
- Prior evidence cross-referenced: `docs/audits/stage-5/audit-lite-slice-4-live-sliders-2026-06-02.md`.
- **Not capturable:** JPEG screenshots (Claude_Preview screenshot subsystem broken in this env — confirmed); the brief "Updating…" note dwell on a fast demo render (source-verified instead). Gate **not** failed for the absent JPEG, per protocol.
