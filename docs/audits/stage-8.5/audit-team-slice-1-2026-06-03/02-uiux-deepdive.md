# UI/UX Deep-Dive — KimCad (Stage 8.5 Slice 1: "My Designs" library + auto-save persistence)

**Audit date:** 2026-06-03
**Role:** Senior UI/UX Designer
**Scope audited:** The Stage 8.5 Slice 1 surfaces — the "My Designs" library (`MyDesigns.tsx`: DesignCard, search, sort, Import, empty/loading/error/no-match states), the routing + create→auto-save→restore journey (`App.tsx`, `useHashRoute.ts`), the Topbar "My Designs" nav (`Topbar.tsx`), the library + toolbar CSS (`styles.css`), and the thumbnail-capture UX (`Viewport.tsx`, `KCViewport.ts`).
**Auditor posture:** Balanced
**Method:** Source review + live rendered check against the model-free demo server (`kimcad web --demo --port 8765`), driven with the Claude_Preview tools (DOM, computed-style, bounding-box, network, console inspection at desktop 1280 and mobile 375). The JPEG screenshot tool timed out (a known limitation of this environment) and was NOT used to pass/fail anything — every visual claim below is backed by DOM/computed-style/bounding-box evidence, stated as such. See "What couldn't be assessed."

---

## TL;DR

Slice 1 genuinely fixes the deal-killer: I created a part, the URL silently became `#/design/<id>`, I reloaded, and the part, sliders, and readiness all came back — verified live, no lost work. The library itself is well-built: every required state exists (loading / empty / populated / no-match / error), the two-step delete arms and auto-disarms, inline rename is autofocused with a label and Escape-to-cancel, search/sort are labelled, Export is a real per-card `<a download>`, contrast clears AA everywhere I sampled (5.1:1 on muted text), and there's no mobile horizontal overflow at 375. The strongest dimension is state coverage; the weakest is **the auto-save is completely silent** — there is no "Saved" signal anywhere, so the user still can't tell their work was kept, which is the exact anxiety this slice set out to kill. The single most important takeaway: the persistence *mechanism* shipped, but the persistence *reassurance* didn't — and two touch/keyboard affordance gaps (card-action buttons miss the 44px touch floor and the branded focus ring) keep the library from being fully usable by touch and keyboard users.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 4 |
| Nit | 3 |

---

## What's working

- **The core journey actually works, end to end** — On the demo, submitting "a small box" auto-saved (URL → `#/design/38a7557d…`), and a full page reload restored the prompt, the live sliders, the readiness card, and the 3D canvas with no error. The deal-killer ("your work vanishes the moment you move on") is fixed at the mechanism level. Verified live, not just read.
- **Complete state coverage on the library** — loading ("Loading your designs…"), empty ("Nothing saved yet."), populated grid, no-match ("No designs match "zzzz".", toolbar stays so the user can clear), and a `role="alert"` load-error path all exist and were each triggered live. This is the dimension most products get wrong, and Slice 1 got it right.
- **Two-step delete is the right safety pattern** — first click arms to "Delete?" + "Cancel" (confirmed live), auto-disarms after 3.5s, and Cancel restores cleanly. A saved design isn't lost to one stray click. Destructive action is visually demoted (muted until armed) rather than a loud red button baiting the click.
- **Inline rename is considerate** — the input is autofocused, carries `aria-label="Design name"`, commits on Enter/blur, and Escape cancels back to the original name (all verified live). The empty/whitespace guard in `commitRename` prevents a blank name.
- **Honest, model-free auto-naming** — when the client auto-saves with an empty name, the server names the entry after the user's prompt (`name = snap.prompt or "Untitled"`, `webapp.py` ~L903), truncated to 120 chars, with the card showing an ellipsis + a `title` tooltip on overflow. Real designs get human-readable names without a naming dialog. Good restraint.
- **Empty-state copy is warm and on-brand** — "Nothing saved yet." + "Describe a part and it's kept here automatically — come back to it anytime." + a "Design your first part" CTA. Friendly, sets the auto-save expectation, and gives the user a forward action. This is the most important screen for a first-time user and it's handled with care.
- **Accessibility fundamentals are mostly there** — search has `aria-label`, sort has an `.kc-sr-only` "Sort by" label, the thumbnail placeholder is `aria-hidden`, the open button has a descriptive `aria-label` ("Open <name>"), tab order is logical and every control is keyboard-reachable (verified: file-input → Import → New design → Search → Sort → per card Open → name → Rename → Duplicate → Export → Delete), and the load error is `role="alert"`.
- **Contrast passes AA everywhere sampled** — muted action/date text 5.14:1, empty-state hint 4.66:1, design name 14.66:1, danger text 5.59:1 (computed from the actual token values against the actual surfaces). No contrast findings.
- **Thumbnail capture is sensibly engineered** — `preserveDrawingBuffer` lets the gallery snapshot the framed part, downscaled to a 320px PNG on an offscreen canvas, captured at the "auto-oriented, plate-down" framing the user already sees — so the saved thumb represents the part the way the user last saw it. Reasonable, cheap, and the typed placeholder ("box") is a clean fallback when no thumb exists.

## What couldn't be assessed

- **Rendered pixels / actual thumbnail image quality.** The JPEG screenshot tool timed out (environment limitation, stated up front). All visual findings are DOM + computed-style + bounding-box based. I could not eyeball thumbnail framing/crop quality on a real captured PNG — in demo mode the saved entries had no thumbnail (the API was POSTed directly), so the gallery rendered the typed placeholder, not a real capture. The capture code path is reviewed but not visually verified end-to-end.
- **True touch-pointer behavior.** The preview environment reports `pointer: fine` (`matchMedia('(pointer: coarse)').matches === false`), so the `@media (pointer: coarse)` 44px-floor rules could not be exercised live. The touch-target finding below is therefore derived from reading the CSS selector list directly (which buttons the coarse rule does/doesn't target) plus measured desktop bounding boxes — stated as "appears to" where I couldn't render it.
- **Keyboard `:focus-visible` rendering.** The eval harness focuses elements programmatically, which does not trigger `:focus-visible`, so I could not capture the on-screen keyboard focus ring. The focus finding is grounded in a stylesheet scan (which selectors have `:focus-visible` rules) — that evidence is definitive about authored CSS, not about the UA fallback ring's exact appearance.

---

## First impressions

Arriving at `#/designs` with an empty library, the screen is calm and unambiguous: a big "My Designs" title, Import / New design on the right, and a centered "Nothing saved yet." with a clear "Design your first part" button. I knew what this was and what to do within a couple of seconds. The toolbar correctly stays hidden until there's something to search. Nothing felt adversarial. The one quiet dissonance: the word "My Designs" appears twice on screen (the Topbar nav button and the page H1) — harmless, but a tell that the nav button is doubling as a title.

Once a few designs existed, the gallery reads well — cards are scannable, the name and date sit together, and the four actions live in a tidy row at the bottom. My eye went to the thumbnail first (correct — that's the "reopen" target), then the name. The card hover lift (`translateY(-1px)` + shadow) is a nice, restrained affordance that says "this is clickable."

## Journey walkthroughs

### Journey: "Build a part → trust it was saved → come back to it"

This is the journey the whole slice exists to serve. Walked live:

1. **Landing → submit "a small box" → "Design it".** Part designs, viewport frames it. Good.
2. **Auto-save fires — silently.** The URL changes to `#/design/<id>` (so it IS persisted), but **nothing on screen tells the user this happened.** I scanned the entire workspace DOM/text: no "Saved", no "Auto-saved to My Designs", no toast, no badge, no save icon (`mentionsSaved: false`, zero save-indicator elements). → **UX-001 (Major).**
3. **Reload the page.** The part, prompt, sliders, and readiness all restore. No lost work, no error. This half of the journey is excellent.
4. **Navigate to "My Designs".** The new entry is there, named from the prompt, openable. The library round-trip is solid.

The gap is entirely in step 2: the product delivers the value but never *tells* the user it did, so the old "did my work survive?" anxiety persists. Scott's earlier note — "How do people even know it's there?" — is still unanswered by the running build.

### Journey: "Find and manage a past design"

Search filters by name live (verified), no-match state is clear and keeps the toolbar so the user can recover, sort offers Newest / Oldest / Name. Rename / Duplicate / Export / Delete all present and wired. One snag observed in the data: a duplicated design copied the original's `created_at` rather than stamping "now," so the copy and original share a timestamp — under "Newest first" their relative order is undefined. → **UX-006 (Minor).**

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion / IA

### [UX-001] — Major — Journey — Auto-save is completely silent; the user gets no "Saved" signal

**Evidence**
Route `#/design/<id>`, desktop 1280, live. After creating "a small box," the URL auto-changed to `#/design/38a7557d36344d31a465c7836cb605e2` (auto-save confirmed firing) but a full-DOM text + element scan found **no** save indicator of any kind: `mentionsSaved: false`, `mentionsSaveSignal: false`, `saveIndicatorEls: []`. Source confirms the design choice: `App.tsx` `persist()` calls `saveDesign(...)` then `navigate(...)` with no state surfaced to any view; there is no toast, badge, or "Saved" affordance in `App.tsx`, `Workspace.tsx`, or `Topbar.tsx`.

**Why this matters**
This is the headline value of Slice 1 — "your work no longer vanishes." The mechanism works, but the user has no way to *know* it works. They experience the exact same screen they'd see if nothing were saved, so the anxiety the slice set out to kill survives intact. First-time users in particular will not trust that closing the tab is safe, and may resort to the old coping behavior (keeping the tab open, re-describing parts). This directly undercuts the slice's acceptance criterion and is the product owner's stated concern ("How do people even know it's there?").

**Blast radius**
- Adjacent code / pages using the same pattern: the save signal would live in `App.tsx` (it owns `persist()` and knows create-vs-update + in-flight via `creatingRef`). A small `saveState` (`'saving' | 'saved' | 'error'`) threaded into `Topbar` (or a corner toast) is the natural home. The re-save-on-slider-change path (debounced) should reuse the same indicator so a drag shows a brief "Saving…→Saved."
- User-facing: every design-creation and every slider re-save would gain a visible cue; no flow regresses.
- Migration: none — purely additive UI state.
- Tests to update: `App.test.tsx` (add an assertion that a save surfaces a "Saved" affordance); none break.
- Related findings: UX-002 (the Topbar "My Designs" button could double as the destination signal), DOC: onboarding copy for auto-save.

**Fix path**
Add a lightweight, non-blocking save indicator. Recommended: a small inline status next to the Topbar brand or "New design" that transitions **"Saving…" → "Saved · in My Designs"** (the latter clickable, routing to `#/designs`), auto-fading the "Saved" after a few seconds but leaving a persistent low-key "Saved" dot while the design is persisted. On a save failure (currently swallowed best-effort), show "Couldn't save — retrying" rather than staying silent. Copy: `Saving…` → `Saved to My Designs`. Keep it quiet and out of the way — this is reassurance, not a celebration.

### [UX-002] — Major — Accessibility — Library's primary controls have no branded `:focus-visible` ring; the thumbnail "open" button may show no keyboard focus at all

**Evidence**
Route `#/designs`, live stylesheet scan. The only `:focus-visible` rules in the document are `.kc-btn:focus-visible` (and `.kc-icon-btn`,`.kc-chip`), `.kc-range:focus-visible`, `.kc-field select:focus-visible`, and `.kc-mydesigns-search:focus-visible`. **None** of the My Designs card controls are covered: `.kc-design-open`, `.kc-design-name`, `.kc-design-act`, `.kc-design-rename`, and `.kc-mydesigns-sort select` have no authored focus-visible style (coverage scan returned `false` for each). `.kc-design-open` additionally renders with `outline: none`-equivalent computed output and `border: 0` in CSS, so it is the highest risk for a *missing* keyboard focus indicator. (The branded accent ring `outline: 2px solid var(--kc-accent)` is used consistently for every other interactive surface in the app — its absence here is an inconsistency as well as an a11y gap.) Verification limit: programmatic focus can't trigger `:focus-visible`, so I confirmed the *authored-CSS gap* definitively but not the exact UA fallback ring on screen — see "What couldn't be assessed."

**Why this matters**
The thumbnail is the primary "reopen this design" target and the most-used control in the library. A keyboard or low-vision user tabbing through the gallery may not be able to see which card is focused — for `.kc-design-open` specifically there may be no visible ring at all. Even where the browser's default ring survives (name, act buttons, sort), it's the unbranded UA ring against a warm surface, inconsistent with the rest of the product and easy to miss. This is the difference between a keyboard-navigable library and a keyboard-*usable* one.

**Blast radius**
- Adjacent code / pages using the same pattern: add focus-visible rules in the My Designs CSS block (`styles.css` ~L1417–1540) for `.kc-design-open`, `.kc-design-name`, `.kc-design-act`, `.kc-design-rename`, `.kc-mydesigns-sort select`. The `.kc-mydesigns-sort select` should reuse the same treatment as `.kc-field select:focus-visible` (it's not a `.kc-field`, so it's currently uncovered). Consider promoting a single shared `:focus-visible` token rule.
- User-facing: keyboard/AT users gain a visible focus path through the gallery; mouse users unaffected.
- Migration: none.
- Tests to update: none known (no focus-style tests exist — a gap worth noting to the Test role).
- Related findings: UX-003 (touch targets) — both are "the card actions were styled for mouse-on-desktop only."

**Fix path**
Add to the My Designs block, mirroring the app's existing accent ring:
```css
.kc-design-open:focus-visible,
.kc-design-name:focus-visible,
.kc-design-act:focus-visible,
.kc-design-rename:focus-visible,
.kc-mydesigns-sort select:focus-visible {
  outline: 2px solid var(--kc-accent);
  outline-offset: 2px;
}
```
For `.kc-design-open`, an inset offset (e.g. `outline-offset: -2px`) reads better since the thumbnail fills the card top with no padding.

### [UX-003] — Major — Responsive / Accessibility — Card action buttons miss the 44px touch-target floor and sit 4px apart

**Evidence**
Route `#/designs`, measured live. `.kc-design-act` (Rename/Duplicate/Export/Delete) bounding box is **~55 × 25px** (height 25px at both desktop and the 375 mobile viewport). The `@media (pointer: coarse)` block in `styles.css` (~L579) applies the 44px `min-height` floor to `.kc-btn, .kc-icon-btn, .kc-chip, .kc-field select` only — `.kc-design-act` is **not** in that selector list, so it never gets the floor on a touch device. The four actions are laid out in a row with `gap: 4px` (`.kc-design-actions`). The destructive **Delete** sits immediately beside **Export**. (Touch-pointer media could not be rendered live — env reports `pointer: fine` — so this is read from the CSS selector list + measured boxes; stated as "appears to" for the on-device render.)

**Why this matters**
On a phone or tablet, each card action is roughly half the 44×44 minimum (WCAG 2.5.5 / Apple HIG), and with only 4px between them a fingertip can easily land on the wrong one — including hitting Delete when reaching for Export, the one mis-tap that loses (well, arms deletion of) a saved design. The two-step delete (UX credit above) mitigates the worst case, but a cramped, error-prone action row undercuts the "manage your library" half of the slice on the devices most likely to be used casually.

**Blast radius**
- Adjacent code / pages using the same pattern: `.kc-design-act` and `.kc-design-actions` in `styles.css`. The coarse-pointer rule (~L579) should add `.kc-design-act` to its floor list (or the action row should grow its tap area via padding while keeping the visual compact). The `<a download>` Export shares the class, so it's fixed in the same pass.
- User-facing: touch users get reliably tappable card actions; desktop layout can stay visually identical if the growth is applied only under `pointer: coarse`.
- Migration: none.
- Tests to update: none known.
- Related findings: UX-002 (same "desktop-mouse-only" root for the card controls).

**Fix path**
Extend the coarse-pointer floor to the card actions and widen the spacing on touch:
```css
@media (pointer: coarse) {
  .kc-design-act { min-height: 44px; display: inline-flex; align-items: center; }
  .kc-design-actions { gap: 8px; flex-wrap: wrap; }
}
```
Consider separating Delete from the other three (a small spacer or pushing it to the row's end) so the destructive action isn't flush against Export.

### [UX-004] — Minor — Copy — "Export" is ambiguous about *what* it exports

**Evidence**
Route `#/designs`, card action bar. The button reads **"Export"** and is an `<a download>` to `/api/designs/<id>/export` returning a `.kimcad` archive (per `exportDesignUrl` + `importDesign`'s `.kimcad` accept). Nothing on the card tells the user the format or that this is the KimCad round-trip file (not an STL/3MF for printing). The workspace separately offers model/g-code downloads, so a user could reasonably expect "Export" to hand them a printable mesh.

**Why this matters**
A maker who clicks "Export" expecting a printable STL gets a `.kimcad` zip they can't slice — a small but real moment of confusion, and a support question. The word is doing too much work alone.

**Blast radius**
- Adjacent code: label lives in `MyDesigns.tsx` (`DesignCard`); the matching Import button copy + `accept=".kimcad"` should stay consistent.
- Migration: none.

**Fix path**
Tighten the label or add a tooltip. Recommended label: **"Export (.kimcad)"**, or keep "Export" with `title="Download a .kimcad backup you can re-import"`. Pair with Import's affordance so the two read as a matched backup/restore set.

### [UX-005] — Minor — Copy / IA — "My Designs" appears twice (Topbar nav + page H1); the nav item doesn't signal "you are here"

**Evidence**
Route `#/designs`, live. Body text shows "My Designs" twice — the Topbar button (`Topbar.tsx`) and the page `<h1 class="kc-mydesigns-title">` (`MyDesigns.tsx`). The Topbar "My Designs" button has no active/selected state when the library is the current route (it's a plain `.kc-btn-ghost` regardless of route).

**Why this matters**
Minor redundancy, and a small IA miss: the nav doesn't reflect the current location, so the user loses the "where am I" cue that a highlighted nav item provides. Not confusing, but below the bar for a product that treats UI as a first-class gate.

**Blast radius**
- Adjacent code: `Topbar.tsx` (needs the current route to set an active class), `App.tsx` (already has `route` to pass down).
- Migration: none.

**Fix path**
Give the Topbar "My Designs" button an `aria-current="page"` + active styling when `route.name === 'designs'`. The duplicate label is acceptable (nav + title is a common pattern) once the nav shows selection.

### [UX-006] — Minor — Journey / State — A duplicated design copies the original's timestamp, making "Newest first" order nondeterministic

**Evidence**
Live API: after duplicating, both original ("box") and copy ("box (copy)") returned the **same** `created_at` (`2026-06-03T17:33:21.326940+00:00`). The sort comparator in `MyDesigns.tsx` sorts by `created_at.localeCompare`, so equal timestamps leave the two in an undefined relative order under Newest/Oldest.

**Why this matters**
A user who duplicates a design then sorts by Newest may not see the new copy at the top where they expect it; the copy can sort anywhere relative to its source. Low-impact, but it's the kind of small "the list didn't do what I expected" that erodes trust in the library's ordering.

**Blast radius**
- Adjacent code: the duplicate handler in `webapp.py` / `design_store.py` (it should stamp a fresh `created_at` for the copy). This is a backend behavior with a UX symptom — flag to the Engineering role for the actual fix.
- User-facing: duplicates would sort predictably to the top under "Newest."
- Migration: existing duplicates keep their copied timestamp (cosmetic).

**Fix path**
Stamp the duplicate's `created_at` to "now" at duplication time (Engineering). UX-side, no change needed once the data is correct.

### [UX-007] — Minor — State — Import errors and per-card action failures are swallowed without a card-level cue

**Evidence**
Source: `MyDesigns.tsx` `handleImportFile` sets a page-level `error` ("That file couldn't be imported.") on failure (good), but `DesignCard.act()` runs Rename/Duplicate/Delete with `.catch(() => {})` and surfaces nothing if the call fails — the card just un-busies as if it worked. The page-level import error also renders above the toolbar, far from where the user's eye is (the card grid).

**Why this matters**
If a duplicate or delete fails (disk full, store error), the user sees the spinner clear and assumes success — a silent failure on a data action. Lower exposure (these rarely fail locally), hence Minor, but a silent data-action failure is a trust risk.

**Blast radius**
- Adjacent code: `DesignCard.act()` and `commitRename` in `MyDesigns.tsx`.
- Migration: none.

**Fix path**
Surface a brief per-card or toast error on action failure ("Couldn't duplicate — try again"). Reuse the same toast channel proposed for UX-001's save indicator.

### [UX-008] — Nit — Copy — "Importing…" is the only in-flight cue; no progress for a large import

**Evidence**
`MyDesigns.tsx`: the Import button text swaps to "Importing…" and disables while in flight (verified in source). For a large `.kimcad` this is a fine spinner-equivalent; no finding beyond noting it's the minimum. Acceptable as-is.

**Fix path**
None required. If imports can be large/slow, consider a subtle progress treatment later.

### [UX-009] — Nit — Visual hierarchy — Card action labels and date share the same muted color

**Evidence**
`.kc-design-date` and `.kc-design-act` both compute to `rgb(111,104,87)` (`--kc-muted`). Both pass contrast (5.14:1). Purely a subjective hierarchy preference — the date (passive metadata) and the actions (interactive) reading at the same weight slightly flattens the "these are buttons" cue until hover.

**Fix path**
Optional: nudge the action labels a touch darker or add a hairline/hover affordance so they read as interactive at rest. Not required.

### [UX-010] — Nit — Motion — Card hover lift has no reduced-motion-specific consideration beyond the global override

**Evidence**
`.kc-design-card` transitions `transform`/`box-shadow` on hover; the global `@media (prefers-reduced-motion: reduce)` block zeroes transition durations app-wide, so this is already handled. Noted only for completeness — no action.

**Fix path**
None.

---

## States audit matrix

| Component / page | Default | Loading | Empty | Error | No-match / Partial | Notes |
|---|---|---|---|---|---|---|
| My Designs library | ✓ | ✓ "Loading your designs…" | ✓ "Nothing saved yet." + CTA | ✓ `role="alert"` "Couldn't load your designs." | ✓ "No designs match "…"" (toolbar retained) | All five states verified live. Exemplary coverage. |
| DesignCard | ✓ | ✓ busy dim (`kc-design-card-busy`) | — | ✗ action failure swallowed (UX-007) | — | Two-step delete + inline rename verified live. |
| Import control | ✓ | ✓ "Importing…" + disabled | — | ✓ page-level "That file couldn't be imported." (placement note, UX-007) | — | Hidden `.kc-sr-only` input, visible trigger button — correct SR pattern. |
| Toolbar (search+sort) | ✓ | — | hidden when empty (correct) | — | search filters live; sort 3 options | Gated on `hasAny` — verified hidden in empty state. |
| Create→auto-save→restore | ✓ | ✓ "Designing your part…" | — | ✓ "That design couldn't be opened." on bad reopen | — | Restore verified live; **no "saved" signal** (UX-001). |

## Accessibility snapshot

- **Keyboard navigation:** Logical, complete tab order verified live (file-input → Import → New design → Search → Sort → per card: Open → name → Rename → Duplicate → Export → Delete). Every control reachable. Escape cancels rename. Good.
- **Focus visibility:** **Gap (UX-002).** Only `.kc-mydesigns-search` has a branded `:focus-visible` rule among library controls; `.kc-design-open` (primary open target) is the highest risk for a missing visible ring. Inconsistent with the app's otherwise-consistent accent focus ring.
- **Color contrast:** Passes AA at every sampled pair — muted action/date 5.14:1, empty hint 4.66:1, name 14.66:1, danger 5.59:1 (computed from token values vs. actual surfaces). No findings.
- **Screen reader labeling:** Search `aria-label`, sort `.kc-sr-only` "Sort by", rename `aria-label="Design name"`, open `aria-label="Open <name>"`, placeholder `aria-hidden`, load error `role="alert"`. Strong. (File input has no label/aria-label, but it's `.kc-sr-only` and driven by a labelled visible Import button — the correct, accessible pattern; not a finding.)
- **Reduced motion:** Global `prefers-reduced-motion: reduce` block zeroes animation/transition durations app-wide; the viewport auto-rotate is also disabled. Card hover lift covered. Good.
- **Touch target size:** **Gap (UX-003).** Card action buttons ~25px tall, 4px apart, not in the coarse-pointer 44px-floor selector. Header `.kc-btn`s (Import/New design) and the slider are covered by the floor.

## Patterns and systemic observations

- **Root pattern behind UX-002 + UX-003:** the card-action controls (`.kc-design-act`, `.kc-design-open`, `.kc-design-name`) were styled for mouse-on-desktop and skipped both the app's focus-ring convention and the coarse-pointer touch floor that the rest of the chrome (`.kc-btn`, `.kc-range`, `.kc-field select`) follows. One coordinated pass on the My Designs CSS block fixes both — the highest-leverage UX fix in this slice after the save signal.
- **Root pattern behind UX-001 + UX-007:** the slice has no surface for transient feedback — auto-save success, save failure, and per-card action failure are all silent. A single small toast/status channel in `App.tsx` would close UX-001 (Major) and UX-007 (Minor) together. This is the second-highest-leverage fix.
- **The persistence mechanism is genuinely solid** — create→auto-save→restore verified, prompt-based naming, in-flight create guard against duplicate entries (`creatingRef`), debounced re-save, two-step delete, all the states. The slice's engineering is ahead of its *communication*. The remaining UX work is reassurance and affordance polish, not mechanism — which is the right place to be.

## Appendix: surfaces reviewed

- **Routes (live, demo server :8765):** `#/` (landing + create flow), `#/designs` (empty + populated + no-match), `#/design/<id>` (auto-saved + restored-on-reload).
- **Components/files:** `MyDesigns.tsx`, `App.tsx`, `Topbar.tsx`, `useHashRoute.ts`, `Landing.tsx`, `Workspace.tsx`, `Viewport.tsx`, `viewport/KCViewport.ts`, `styles.css` (My Designs + toolbar + coarse-pointer blocks), `api.ts`, `webapp.py` (save-naming + reopen paths).
- **Viewports:** desktop 1280, mobile 375 (no horizontal overflow at 375: `scrollWidth == clientWidth == 375`, grid collapses to one column).
- **Live interactions exercised:** create→auto-save, reload→restore, two-step delete arm/cancel, inline rename + Escape, search filter + no-match + restore, sort options, tab-order walk, history/back behavior, contrast computation, bounding-box measurement.
- **Limitation:** JPEG screenshots timed out (environment); no live touch-pointer or keyboard-`:focus-visible` rendering — see "What couldn't be assessed."
