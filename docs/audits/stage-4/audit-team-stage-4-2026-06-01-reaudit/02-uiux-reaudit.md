# UI/UX Re-Audit — KimCad (Stage 4 gate)

**Re-audit date:** 2026-06-01
**Role:** Senior UI/UX Designer
**Method:** Live render of the built SPA in demo mode (`kimcad.cli web --demo`, port 8842) via the `kimcad-web` launch config and the Claude_Preview MCP. Driven at **1340×880 (desktop)** and the **375×812 (mobile)** preset. Verification is **DOM-authoritative** — `preview_eval` (`getBoundingClientRect` / `getComputedStyle` / projected DOM), `preview_inspect`, served-bundle inspection (`/assets/kimcad.js`, `/assets/Workspace.js`, `/assets/index.css`), and runtime WCAG contrast computation. The full flow was driven on both viewports: landing → click `.kc-chip` → workspace (design) → `.kc-slice-btn` (slice/export) → mobile reload + re-drive.
**Predecessor:** `../audit-team-stage-4-2026-06-01/02-uiux-deepdive.md` (original 11 findings UX-001…UX-012; UX-002 was a documented deliberate choice and was not re-flagged).
**Auditor posture:** Balanced.

---

## Tooling note (read first — affects how evidence was gathered)

`preview_screenshot` **timed out on every attempt (30s)** — including on the plain landing page with **no `<canvas>` present** — so it is a fault of the screenshot subsystem in this session, not the app or the WebGL loop. The page itself was fully healthy throughout: `preview_eval` returned instantly on every call, the console was **clean (0 errors / 0 warnings)** across the entire desktop + mobile flow, and `preview_inspect`/`preview_eval` (which the tool docs themselves flag as *more accurate than screenshots* for colors, fonts, spacing, and dimensions) gave complete coverage. The brief anticipated this and directed DOM-authoritative verification; that is what this report rests on. Two consequences:

- I could not produce raster screenshots. Every claim below is backed by a measured DOM/computed-style value instead.
- The WebGL canvas runs with `preserveDrawingBuffer: false`, so canvas-pixel sampling reads blank — I could not pixel-verify that the in-canvas **bounding box** (3D `LineSegments`) actually draws. I verified its *construction* in source/served bundle, not its pixels. (This matters only for the bbox half of UX-001; the dimension-pill failure below is DOM-visible and unaffected.)

---

## Headline result

**All original UX findings resolved? → NO.** Ten of eleven are genuinely resolved in the render. **One — UX-001 — is only partially resolved: the orientation chip, drag hint, dynamic aria-label, and (in-source) bounding box are all present and correct, but the projected W/D/H dimension pills render permanently EMPTY and invisible (`opacity:0`, no text).** The single most-emphasized deliverable of the original Major finding — the on-canvas dimension labels that make the preview "print-aware" — does not appear in the running product. This is a **new Major regression** (the elements ship but are non-functional), filed below as **UX-R01**.

The contrast fix (UX-003), the gear removal (UX-006), reduced-motion (UX-007), the mobile hero stack (UX-005), touch targets (UX-004), the dynamic aria-label (UX-009), the first-person sub-copy (UX-010), the cube avatar (UX-011), and the .3mf-first export framing (UX-012) are all **confirmed in the render** and several are implemented *better* than the original fix path suggested.

## Severity roll-up (this re-audit)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 (UX-R01 — new) |
| Minor | 1 (UX-R02 — new) |
| Nit | 0 |

---

## Per-finding verdicts (original findings)

### UX-001 — The 3D viewport's print-aware affordances — **PARTIALLY RESOLVED** ⚠️

The original Major called for four affordances: dimension pills, bounding box, orientation chip, drag hint. Render verdict, element by element:

| Affordance | DOM evidence | Verdict |
|---|---|---|
| Orientation chip | `.kc-viewport-chip` text = **"Auto-oriented · plate-down"**, `opacity:1`, rendered top-left of the viewport card (both desktop + mobile) | ✅ RESOLVED |
| Drag hint | `.kc-viewport-hint` text = **"Drag to rotate · scroll to zoom"**, `opacity:1`, bottom-left (both viewports) | ✅ RESOLVED |
| Bounding box | `KCViewport.buildBBoxAndDims()` builds a 12-edge `LineSegments` box (`KCViewport.ts:220–237`); present in served `Workspace.js`. Could not pixel-verify (canvas `preserveDrawingBuffer:false`), but construction is correct and the model frames in view | ✅ RESOLVED (code-verified; pixels not capturable) |
| **Projected W/D/H dimension pills** | **3× `.kc-dim-pill` exist in the DOM but are permanently `opacity:0` with empty `textContent`, collapsed to a 14×4px sliver at the card's top-left corner (x≈375,y≈73). Reproduced after a clean reload, after a forced camera drag, and on BOTH desktop and mobile.** | ❌ **NOT RESOLVED** |

**The pills are the regression — see UX-R01 below.** Because the chip, hint, dynamic aria-label, and bbox are all in place, the *infrastructure* of UX-001 landed; the headline visual (the floating `80 mm / 60 mm / 40 mm` labels anchored to the box) is missing in the running app. Net: the original UX-001 is **not** fully closed.

### UX-003 — Primary-button + accent-link contrast (WCAG AA) — **RESOLVED** ✅

Measured at runtime (WCAG 2.1 relative-luminance, computed in-page), against the **actual effective backgrounds**:

| Element | Foreground | Effective background | Ratio | AA (normal ≥4.5) |
|---|---|---|---|---|
| "Design it" (landing CTA) | white | **#b1542f** (rgb 177,84,47) ✓ the spec'd `--kc-accent-strong` | **5.03:1** | ✅ PASS |
| "Slice & prepare file" (export CTA) | white | #b1542f | **5.03:1** | ✅ PASS |
| "Download 3D model (STL)" accent link | #b1542f | card surface #faf6ee | **4.66:1** | ✅ PASS |
| "Download print file (.3mf)" primary | #f0ebe0 | ink #272219 | **13.29:1** | ✅ PASS |

A full sweep of *every* accent-colored text node on the rendered workspace (normal + large) returned **zero AA failures**. The brand token `--kc-accent` (#c8623a, was 3.99:1 white-on-fill) is correctly retained for fills/avatar/chips/focus rings, while text-bearing fills and links use the darker `--kc-accent-strong` (#b1542f). Both CTAs use exactly the rgb(177,84,47) the brief specified. Comprehensively fixed.

### UX-004 — Touch targets ≥44px on coarse pointers — **RESOLVED** ✅ (better mechanism; caveat on live verification)

The fix is `@media (pointer: coarse) { .kc-btn, .kc-icon-btn, .kc-chip, .kc-field select { min-height: 44px } }` (`styles.css:578–586`; present in served `index.css`). The "Design it" button carries `.kc-btn` and the example pills carry `.kc-chip`, so both are covered. **Verification caveat:** the Claude_Preview mobile preset resizes the viewport but reports `pointer: fine`, so the 44px rule does not apply in *this* render (I measured the button at 39px and chips at 32px because the coarse rule was inactive — not because the fix is wrong). When I injected the equivalent `min-height:44px` to simulate a coarse pointer, the button and chips both computed to **exactly 44px**. The mechanism is sound and arguably superior to a width breakpoint (a 375px-wide *desktop* window is not a touch device and shouldn't get fat targets). **Recommend a one-time check on real touch hardware** to close the loop, since the harness can't emulate `pointer: coarse`. Marked RESOLVED on the strength of correct selectors + served CSS + simulation.

### UX-005 — Hero input stacks on mobile — **RESOLVED** ✅

At 375px, `.kc-input-card` computes `flex-direction: column; align-items: stretch` (via `@media (max-width:640px)`, `styles.css:590`). The textarea is now full-width (**298px**, up from the original cramped ~184px) and the "Design it" button sits **below** it (`btnBelowTextarea: true`), full-width. No horizontal scroll (`scrollWidth 375 == innerWidth 375`). Clean.

### UX-006 — Inert Settings gear — **RESOLVED** ✅

The gear is **gone**. `document.querySelectorAll('.kc-icon-btn')` → **0 elements** on landing *and* workspace, desktop *and* mobile; `[aria-label="Settings"]` not found. The topbar now reads just "KimCad". The dead-click affordance is removed entirely (the remediation chose removal over the toast option — clean and honest).

### UX-007 — `prefers-reduced-motion` — **RESOLVED** ✅

Two-layer fix, both verified in the **served** bundle:
- CSS: `@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration:.01ms!important; animation-iteration-count:1!important; transition-duration:.01ms!important } }` — present in served `/assets/index.css`. Neutralizes `kc-fadeup`, `kc-spin`, and all transitions.
- JS: `KCViewport` constructor reads `matchMedia('(prefers-reduced-motion: reduce)')` and sets `autoRotate = false` (`KCViewport.ts:59–63`); the served `Workspace.js` chunk contains the `reduceMotion`/`prefers-reduced-motion` logic. Auto-rotate, the most impactful motion, is gated. (The preview env didn't emulate reduce-motion, so I verified via source + served bundle per the brief's fallback.)

### UX-008 — Outcome-first badge + green dot — **RESOLVED** ✅

`.kc-badge` now renders a leading **`.kc-badge-dot` with `background: rgb(29,122,78)` (#1d7a4e, the pass-green)** ✓, and the copy leads with the user benefit: **"No CAD skills needed · runs entirely on your machine."** The green "system ready" dot is in, and the lead phrase is now the user-facing benefit ("No CAD skills needed") rather than the architecture. This addresses the finding (dot + outcome-first lead). *Minor note, not a re-flag:* the second clause still carries the "runs entirely on your machine" architecture framing; "Ready to print in ~15 minutes" from the design wasn't adopted (reasonably — the ~15-min claim may not be substantiatable yet). Resolved at the level the finding asked for.

### UX-009 — Dynamic canvas aria-label — **RESOLVED** ✅

`canvas[aria-label]` = **"3D preview — 80 by 60 by 40 millimetres"** once a part is loaded (driven from `dims` state via `vp.getDimensions()`, `Viewport.tsx:73–75`). It correctly reflects the design result and falls back to "3D preview" when empty/designing. This is now the *only* place an assistive-tech user gets the dimensions on the viewport — which raises the stakes on the dead pills (UX-R01): a sighted low-vision user gets nothing on-canvas.

### UX-010 — First-person hero sub-copy — **RESOLVED** ✅

Sub-copy now reads: **"Describe a functional part in plain words — I'll design it, check that it's actually printable, and get it ready for your printer."** The first-person "I'll" voice matches the conversational persona ("Here you go —"). Resolved.

### UX-011 — Assistant cube avatar — **RESOLVED** ✅

The AI reply renders as `.kc-ai-row` → `.kc-ava` (28×28px, `background rgb(200,98,58)` #c8623a, 9px radius) wrapping a white cube `CubeGlyph`, then the `.kc-msg-ai` bubble (`ChatPanel.tsx:19–28`). Measured: avatar **28×28**, does **not** break the bubble layout (clean flex row, bubble unaffected). The thinking/loading row carries the same avatar. (I initially mis-read a child-div selector as avatar-less; on direct inspection the `.kc-ai-row`/`.kc-ava` wrapper is present and correct.) Resolved.

### UX-012 — `.3mf` export framing — **RESOLVED** ✅ (at Stage-4 scope)

The export panel now leads with **"Download print file (.3mf)"** as the dark **primary** button, with "Download 3D model (STL)" demoted to a secondary accent link below it. 3MF-first framing matches the design's intent. The one-line *explanatory* copy ("3MF is printer-agnostic & safe to share · STEP for CAD editing · G-code locks to <printer>") is **not** present — but the original finding explicitly scoped that prose to the Stage-10 print-report build-out. Resolved at the Stage-4 level (format priority is correct).

### UX-002 — solid render vs blueprint wireframe — **not re-flagged** (documented deliberate choice, per brief).

---

## New findings (introduced by / surviving the fixes)

### [UX-R01] — Major — State / Accessibility — The projected dimension pills ship but render permanently empty and invisible

**Evidence (DOM-authoritative, reproduced 3 ways, both viewports).**
After designing a part, the viewport stage contains `<canvas>` + three `<span class="kc-dim-pill" aria-hidden="true" style="opacity: 0;">` + the chip + the hint. The three pills, across every sample:
- `textContent` = `""` (empty), `style="opacity: 0"`, computed `opacity` = `0`;
- collapsed to **14×4px** parked at the card's top-left corner (x≈375, y≈73 — i.e. never positioned by the projection code);
- unchanged after: (a) a clean `location.reload()` + re-drive; (b) a forced synthetic pointer drag of the canvas (which moves the camera and should trigger `updateLabels` on the next frame); (c) on **both** desktop (1340) and mobile (375).

Meanwhile the same instance proves the rest of the pipeline ran: the canvas `aria-label` carries the dims ("…80 by 60 by 40 millimetres"), and the chip + hint render — so `this.dims` is set and the model loaded. The render loop is active.

**Why this matters.** These pills *are* the headline of the original UX-001 Major — the floating `80 mm / 60 mm / 40 mm` labels anchored to the bounding box that turn the viewport from "decorative spinning box" into the product's promised **print-aware preview**. The dev shipped the DOM elements and the projection method (`KCViewport.updateLabels()`, which sets `el.textContent = `${dims[k]} mm`` and `opacity:'1'` every frame), the REMEDIATION explicitly claims "projected W/D/H dimension pills" as delivered, and a rendered desktop+mobile pass was claimed to "confirm … dimension pills" — but in the running product they are invisible. A user (and the auditor) sees no dimension labels on the canvas at all. This is the regression-class that is *worse* than "not built": it looks done in the diff and the DOM, but is dead at runtime.

**Likely root cause (for the dev — not required for the verdict).** `updateLabels()` early-returns on `!this.labels || !this.labelAnchors || !this.dims` (`KCViewport.ts:274`). `this.dims` is provably set (aria-label) and `this.labelAnchors` is set in the same method that sets `dims`, so by elimination **`this.labels` is null on the live instance** — i.e. the `{x,y,z}` label refs passed into the `KCViewport` constructor (`Viewport.tsx:21–25`) were null at construction time, so the per-frame label update silently no-ops. (A projection `v.z>=1` cause is ruled out: the model is framed and centered, and that path would still leave `opacity:0` but is geometrically impossible for all three bottom-edge anchors of an in-view box.) The served `Workspace.js` contains the correct `updateLabels` body, so this is a wiring/lifecycle bug, not a stale build. Recommend: assert non-null labels at construction (or rebuild the labels object inside the mesh-load effect rather than the once-only mount effect), and add a render-level test that asserts a designed part yields ≥1 `.kc-dim-pill` with non-empty text and `opacity:1`.

**Blast radius.** `frontend/src/components/Viewport.tsx` (ref wiring / effect ordering), `frontend/src/viewport/KCViewport.ts` (`updateLabels` guard). User-facing: every designed part, 100% of the core flow, desktop + mobile. No existing test catches it (the claimed "rendered pass" did not actually assert pill text).

**Fix path.** Wire the labels so `this.labels` is non-null when a mesh loads (e.g. build the labels object in the `meshUrl` effect, or guard the mount effect on all three refs being present and re-init if they weren't). Then add a real render assertion (a Playwright/Vitest-DOM check post-design: `.kc-dim-pill` count 3, each `textContent` matches `/\d+ mm/`, `opacity === '1'`). Severity **Major** (not Critical): the part is still usable and the dimensions are available in the side-panel Parameters table and the aria-label; what's lost is the on-canvas print-aware labeling that was the whole point of UX-001 and the differentiating moment of the product.

### [UX-R02] — Minor — Accessibility (verification gap) — Touch-target fix can't be confirmed live; relies on `pointer: coarse`

**Evidence.** The 44px touch-target rule is correctly gated on `@media (pointer: coarse)` and covers the right selectors, but no available tooling emulates a coarse pointer, and the preview reports `pointer: fine`. I confirmed the rule's *effect* by simulation (injecting `min-height:44px` → button and chips both compute to 44px) and confirmed the rule is in the served CSS. **This is not a defect in the app** — it's a residual verification gap: the only thing standing between "verified by simulation" and "verified live" is real touch hardware. Filed as Minor so it isn't lost. **Fix path:** do a single manual check on a phone/tablet (or a device-emulation browser that sets coarse pointer) to confirm the live 44px, then this closes to nil.

---

## Fresh-pass regression sweep (did the fixes break anything new?)

Checked specifically for the failure modes the brief called out, plus a general sweep:

- **Dimension pills overlapping / mispositioned?** Worse than overlap — they're **dead** (UX-R01). Not an overlap bug; an empty-render bug.
- **Avatar breaking the bubble layout?** No. `.kc-ai-row` is a clean flex row; the 28px avatar sits beside the bubble without distorting it; user messages remain avatar-less and right-aligned. ✅
- **Contrast change making a button look muddy?** No. #b1542f is a clean, saturated terracotta one step down from the brand accent; white-on-it is 5.03:1 and reads crisp. The brand accent is preserved for fills/avatar/chips, so the palette stays coherent. ✅
- **Mobile stack breaking?** No. Hero stacks cleanly (textarea full-width, button below); workspace collapses to a single 375px column in chat→viewport→panels order; **no horizontal scroll** on landing or workspace. ✅
- **Chip / hint / orientation overlap in the viewport?** No. Chip top-left (y≈85), hint bottom-left (y≈837 desktop), no collision; both `pointer-events:none` so they don't block canvas drag. ✅
- **Console health across the full flow?** **0 errors, 0 warnings** — landing → design → slice → mobile re-drive. ✅
- **`.3mf` primary vs STL secondary hierarchy?** Correct and legible; primary dark button + secondary accent link, no ambiguity. ✅

No *new* visual breakage was introduced by the fixes beyond the dead-pills regression. The avatar, contrast, stack, and gear-removal fixes are clean.

---

## States re-check (rendered)

| Component | Rendered states confirmed | Notes |
|---|---|---|
| Landing input | default / busy-disable / placeholder-empty; **mobile now stacks** | UX-005 fixed |
| Conversation | user bubble / thinking row (avatar+spinner) / AI reply (avatar+bubble) | UX-011 avatar present |
| Viewport | empty ("preview appears here") / designing / rendered-with-chip+hint+dynamic-aria | **pills dead (UX-R01)**; bbox code-verified only |
| Parameters | empty / populated (Type, Size 80×60×40 mm) | unchanged, good |
| Printability | populated pass (green "Ready to print", axis table, 4 findings) | unchanged, good |
| Export & print | populated (~50m20s / 200 layers / 33.63 cm³); **.3mf primary**, STL secondary | UX-012 fixed |

---

## Does it now match the Workshop design?

**Yes on the system and now on nearly all the surfaces — with one runtime hole.** The palette/type/spacing/topbar/layout fidelity that was already strong is intact; the re-audit's nine resolved fixes close the previously-flagged surface gaps (contrast, gear, reduced-motion, mobile hero, avatar, dynamic aria, first-person copy, .3mf-first, green-dot badge), several implemented more cleanly than asked. The **one** place the running product still diverges from the design — and from the dev's own remediation claim — is the viewport's **projected dimension labels**, which ship as DOM elements but render empty and invisible (UX-R01). Close that one Major and the Stage-4 UI is a faithful realization of the Workshop design.

---

## Appendix — surfaces & methods

- **Server:** `kimcad-web` launch config (`.venv python -m kimcad.cli web --demo --port 8842`).
- **Viewports:** 1340×880 (desktop), 375×812 (mobile preset). Full demo flow driven on both.
- **Contrast:** WCAG 2.1 relative-luminance computed in-page against measured effective backgrounds; thresholds 4.5:1 normal / 3:1 large.
- **Served bundles inspected:** `/assets/kimcad.js`, `/assets/Workspace.js` (code-split three.js + viewport chunk — confirmed it carries `labelAnchors`/`updateLabels`/`reduceMotion`/the `mm` template), `/assets/index.css` (confirmed reduced-motion + coarse-pointer + 640px-stack rules present).
- **Source cross-referenced:** `frontend/src/viewport/KCViewport.ts`, `frontend/src/components/{Viewport,ChatPanel,Workspace}.tsx`, `frontend/src/styles.css`.
- **Console:** clean (0/0) across the full desktop + mobile flow.
- **Tooling limitation:** `preview_screenshot` timed out on every attempt (incl. canvas-free landing) — a screenshot-subsystem fault, not the app; all verification is DOM/computed-style/served-bundle, per the brief's DOM-authoritative directive. Canvas pixels not sampleable (`preserveDrawingBuffer:false`) → in-canvas bbox verified by construction, not pixels.
