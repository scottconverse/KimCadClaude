# UI/UX Deep-Dive — KimCad (Stage 8: CadQuery backend + editable STEP export)

**Audit date:** 2026-06-06
**Role:** Senior UI/UX Designer
**Scope audited:** The Stage 8 UI delta only — the Export & print card's new editable-STEP affordance and the reworded export-formats note. Files in scope: `frontend/src/components/ExportPanel.tsx` (the `step_url` branch + both formats-note variants), `frontend/src/api.ts` (`step_url`, `report.backend` types). Also assessed: whether a maker can tell which engine built their part, and whether the STEP affordance is discoverable, honest, and consistent with the rest of the Export card.
**Auditor posture:** Balanced

---

## TL;DR

This is a small, well-considered UI delta. The copy is the strongest dimension: the formats note is honest, plain-spoken, and correctly caveats the STEP as the *as-designed* shape (not the print-oriented mesh) — exactly the distinction a maker needs and the kind of thing teams usually omit. The download semantics are clean (`<a download>`, real `.STL`/`.STEP` labels). The weakest dimension is **visual hierarchy + system signaling**: the new STEP link reuses `.kc-download-model` but its extra class `.kc-download-step` has *no CSS rule at all*, so the STL and STEP links render as two visually identical terracotta text links stacked with no differentiation, no icon, and no grouping affordance. The single most important takeaway: **a maker cannot tell which engine (OpenSCAD vs CadQuery) built their part anywhere in the UI** — the presence/absence of the STEP link is the only signal, and it's an inference, not a statement. That's a discoverability/honesty gap worth a Major.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 3 |
| Nit | 2 |

## What's working

- **The STEP honesty caveat is genuinely good.** `ExportPanel.tsx:200-202` — "It's the as-designed shape; print orientation is applied only to the printable mesh." This pre-empts the #1 confusion a CAD-literate maker would have (why doesn't the STEP match the oriented STL?). Specific, true, and unprompted. Credit the writer.
- **Download semantics are correct and accessible.** Both model links are real anchors with the `download` attribute and human file-type labels — "Download editable CAD (.STEP)" / "Download 3D model (.STL)" (`ExportPanel.tsx:188-195`). No JS-only download, no `<div onClick>`. Screen readers get a proper link role and a meaningful accessible name.
- **The two-state note is a thoughtful touch.** When there's no STEP, the copy still *teaches* — "An editable .STEP is available when a part is built with the CadQuery engine" (`ExportPanel.tsx:207-208`) — instead of silently hiding the capability. That's the right call for discoverability of a feature most users won't have triggered yet.
- **Contrast clears AA.** The terracotta link text (`--kc-accent-strong` #b1542f) on the card surface (#faf6ee) measures **4.66:1** (AA normal-text pass); the muted formats-note (#6f6857 on #faf6ee) at 11.5px measures **5.14:1**. Verified by computation, not eyeballed.
- **The note correctly tracks state.** The STEP sentence only appears in the `step_url`-present branch; the OpenSCAD branch gets the "available with CadQuery" teaser. No orphaned copy, no lying about a download that isn't there.

## What couldn't be assessed

- **The STEP-present rendered state.** Per the task brief, a live CadQuery part is hard to produce (needs the model + a failing-OpenSCAD prompt). The live demo at `http://127.0.0.1:8765` serves an OpenSCAD part only. The STEP-link visual was assessed from `ExportPanel.tsx` + the (absent) `.kc-download-step` CSS + the reused `.kc-download-model` rule + the shipped bundle CSS (confirmed no `.kc-download-step` rule in `/assets/index.css`). Findings about the STEP link's *appearance* are therefore source-derived, flagged as "appears to" where I couldn't see pixels.
- **The actual STEP file contents / OCC export fidelity** — out of UI/UX scope (engineering owns BREP correctness).
- The demo SPA is a built bundle (`#root` + `kimcad.js`); component source is the source of truth as the brief directs.

---

## First impressions

Arriving at the Export & print card after a design completes (live, OpenSCAD demo part), the card reads cleanly: printer/material selects, a primary "Slice & prepare file" accent button, and below a quiet formats area with one terracotta "Download 3D model (.STL)" link and a small grey note. The note's mention of a CadQuery engine is the first time the word "engine" appears in the export flow — and as a first-timer I have no idea what produced *my* part, so the line reads as a hypothetical ("if you'd used the other engine…") rather than as information about the thing in front of me. The download options sit as plain text links beneath a much louder accent button; the hierarchy says "slicing is the main event, files are an afterthought," which is reasonable for a print tool, but it does mean the editable-CAD export — a genuinely valuable capability for a CAD-literate maker — is the quietest thing on the card.

## Journey walkthroughs

### Journey: Design completes → export a CadQuery part as editable CAD

1. **Part designed (CadQuery), gate passes.** The Export card shows printer/material/slice as normal — nothing on this card, or on the Printability or Readiness cards, says "built with CadQuery." (Verified: `RightPanel.tsx` PrintabilityCard renders gate/headline/dims/findings only; `report.backend` is typed in `api.ts:49` but never rendered anywhere in the UI.)
2. **User scrolls to the formats area.** Two stacked terracotta links appear: "Download 3D model (.STL)" and "Download editable CAD (.STEP)". They are visually identical — same color, weight, size, no icon, no separator (`.kc-download-step` has no styling). A maker scanning quickly could read them as one repeated control or miss that the second is a *different, higher-value* format.
3. **User reads the note.** The note correctly explains all three formats and the as-designed caveat. This is where the maker *finally* learns CadQuery built the part — buried in a 12px footnote, by inference ("the CadQuery engine"), after the download decision.
4. **Download.** Works (real `<a download>`). Good.

The journey has no dead end and no broken state — it works. The friction is that the part's provenance (which engine) and the relative value of the two exports are both under-communicated, and the maker learns the most important fact (this is an editable precision model) last and quietest.

### Journey: Design completes → OpenSCAD part, user wants editable CAD

Live-verified on the demo. The user sees the STL link and the teaser note: "An editable .STEP is available when a part is built with the CadQuery engine." This is honest but a **dead end with no door** — it tells the maker the capability exists but gives no path to it (no "what is the CadQuery engine?", no link to settings, no hint about *how* a part comes to be CadQuery-built). For a feature the product wants to promote, that's a missed conversion. See UX-002.

---

## Findings

> **Finding ID prefix:** `UX-`
> **Categories:** Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / Motion / IA

### [UX-001] — Major — Journey / IA — A maker cannot tell which engine built their part

**Evidence**
`api.ts:44-56` types `ReportPayload.backend?: string` ('openscad' | 'cadquery') and the comment says "Which geometry backend built the part." But no component renders it. `RightPanel.tsx:534-605` (PrintabilityCard) shows gate badge, headline, dims table, and findings — never the backend. The Readiness card's `attribution` (`RightPanel.tsx:341-344`) is about PrintProof3D vs. the gate, not the geometry engine. The *only* place the engine surfaces to the user is implicitly, via whether the STEP link/note appears in `ExportPanel.tsx:191-210`. Grep across `frontend/src` confirms `report.backend` has zero render sites.

**Why this matters**
Stage 8 introduces a parallel geometry backend specifically because it can build parts OpenSCAD can't, and it unlocks editable STEP. But the product never tells the maker which engine they got. The result: the STEP affordance appears and disappears between designs with no stated cause, and the "available with the CadQuery engine" teaser refers to a thing the user has no way to observe or identify on their own part. For an ex-Apple, UX-first product, "the system silently changed which engine it used and won't tell you" is exactly the kind of opacity that erodes trust. It also makes UX-002's teaser a true dead end — you can't act on "use the CadQuery engine" if you can't tell when you have it.

**Blast radius**
- Adjacent code / pages using the same pattern: `RightPanel.tsx` PrintabilityCard is the natural home for an engine badge (it already renders the gate badge with `kc-status-badge` + tone classes — reuse that chip pattern). `ExportPanel.tsx` formats note is the secondary surface that already names the engine.
- Shared state: `report.backend` already flows through `DesignResponse` → no new API. Saved designs (`SavedDesignSummary` in `api.ts:97-106`) do *not* carry backend; if the team wants engine shown in the My Designs library too, that field needs adding (separate, smaller follow-up).
- User-facing: every completed design would gain a one-word provenance signal; no behavior change to downloads.
- Tests to update: `RightPanel.test.tsx` would need an assertion for the new badge; `ExportPanel.test.tsx:78` already stubs `backend: 'cadquery'` so the existing STEP test is unaffected.
- Related findings: UX-002 (teaser dead end — fixing this is the prerequisite for that teaser to be actionable).

**Fix path**
Render the backend as a small, neutral chip on the Printability card, reusing the existing `kc-status-badge` styling, e.g. **"Built with: CadQuery"** / **"Built with: OpenSCAD"**. Keep it factual and quiet — it's provenance, not a status. Suggested copy for the chip label: `Engine: CadQuery` (or `Engine: OpenSCAD`). If a badge feels too heavy, a single muted line under the headline works: *"Built with the CadQuery engine — editable CAD export available below."* That one line does double duty: states provenance *and* points to the STEP download.

---

### [UX-002] — Major — Journey / Copy — The "STEP available with CadQuery" teaser is a dead end with no path forward

**Evidence**
`ExportPanel.tsx:204-209` (the no-STEP branch): "An editable .STEP is available when a part is built with the CadQuery engine." Live-verified on the OpenSCAD demo part — this is the exact rendered copy. There is no link, tooltip, or hint explaining what the CadQuery engine is, how a part comes to be built with it, or where (if anywhere) the user could choose it.

**Why this matters**
The sentence advertises a capability the maker doesn't have on this part and then strands them. A maker who wants editable CAD now knows it's possible but has no idea how to get it — and per UX-001 can't even tell which engine they're on. Advertising-without-a-door is a classic activation leak: it raises desire and provides no satisfaction path. For a feature Stage 8 exists to deliver, that's a real conversion gap, not a cosmetic one.

**Blast radius**
- Adjacent code: `ExportPanel.tsx:204-209` only; the fix is copy + possibly a link target. If backend selection is CLI-only / automatic today (the `SettingsPanel.tsx:217` comment notes "the manual backend override stays CLI-only"), then the honest fix is to set expectations rather than promise a control that doesn't exist in the GUI.
- User-facing: every maker who designs an OpenSCAD part and reads the note.
- Migration: none.
- Tests to update: `ExportPanel.test.tsx:64-71` asserts the teaser text — update if the wording changes.
- Related findings: UX-001 (provenance), UX-006 (Nit on "engine" jargon).

**Fix path**
Make the teaser either *explain* or *not promise control the GUI lacks*. If the engine is auto-selected (KimCad picks CadQuery when it's the better fit), say so — that's reassuring, not limiting:
> *"Parts that need precision geometry are built with the CadQuery engine, which adds an editable .STEP export. This one used OpenSCAD."*
That states provenance (covers UX-001 on the OpenSCAD side), explains the capability, and sets the honest expectation that the engine is chosen for the part — no phantom control implied. If there *is* a user-facing way to influence it, link to it ("Learn more" / the Settings experimental section).

---

### [UX-003] — Minor — Visual hierarchy — STL and STEP downloads are visually indistinguishable; `.kc-download-step` is unstyled

**Evidence**
`ExportPanel.tsx:192` adds class `kc-download-step` to the STEP link, but there is **no `.kc-download-step` rule** in `frontend/src/styles.css` (grep: zero matches) — confirmed also absent from the shipped bundle (`/assets/index.css`, fetched live: no `kc-download-step`). The STEP link therefore inherits only `.kc-download-model` (`styles.css:1728-1738`): 12.5px, weight 600, terracotta, no icon. The STL link uses the identical rule. In `.kc-formats` (`styles.css:1832-1837`) they stack with a 4px gap and no divider. Net: two identical-looking terracotta text links one above the other.

**Why this matters**
The two exports are *different in kind* — a print-mesh (.STL) vs. an editable precision model (.STEP) — but the UI presents them as visually equal, interchangeable-looking links. A maker skimming may treat them as a repeat, or not register that the second is the higher-value editable format. The unstyled `.kc-download-step` class strongly suggests differentiation was intended and never landed.

**Blast radius**
- Adjacent code: `.kc-download-model` (`styles.css:1728`) is the shared base; `.kc-formats` container; the class hook `.kc-download-step` already exists in markup awaiting a rule.
- User-facing: the STEP download's perceived distinctness and value.
- Tests to update: none (visual only; no test asserts STEP styling).
- Related findings: UX-001 (both are about under-signaling the CadQuery value).

**Fix path**
Add a `.kc-download-step` rule to give the editable-CAD export a distinct, slightly-elevated treatment — e.g. a small leading icon (a "pencil"/edit or cube glyph), a subtle left border or a `kc-surface-2` pill, so it reads as "and here's the special one." Keep it secondary to the slice button. Even a one-line visual separator or a tiny "Editable" tag would resolve the sameness. (Severity Minor, not Major: the function works and the labels already differ in words — this is a recognizability/polish gap, and for an Apple-grade UX bar I'd prioritize it within the Minor tier.)

---

### [UX-004] — Minor — Accessibility / Responsive — Text-link download targets fall short of the 44×44 touch minimum

**Evidence**
`.kc-download-model` (`styles.css:1728-1734`) is a plain inline-ish text link at 12.5px with only `margin-top: 2px` — no padding, no min-height. Both the STL and STEP links share this. At a 4px stack gap (`.kc-formats`, `styles.css:1835`), the two tap targets sit ~16-18px tall and close together.

**Why this matters**
On a touch device, 12.5px text links spaced 4px apart are easy to mis-tap — and here a mis-tap means downloading the wrong file format (STL when you wanted the editable STEP, or vice versa). WCAG 2.1 target-size guidance is 44×44px. This pre-dates Stage 8 (the STL link had it too), but Stage 8 *doubled* the count of small adjacent text-link targets, so the delta makes it more likely to bite.

**Blast radius**
- Adjacent code: `.kc-download-model` (shared by both links); `.kc-formats` spacing. Fixing the base rule fixes both at once.
- User-facing: all touch users on the export card.
- Tests to update: none.
- Related findings: UX-003 (same two elements; a pill/padded treatment for STEP would also enlarge its target).

**Fix path**
Give the format links vertical padding (≥ ~8px top/bottom) or a min-height so each clears ~40-44px, and widen the inter-link gap to ≥8px. If UX-003's pill treatment is adopted, that largely resolves this too. Note in the report that this is a pre-existing pattern issue surfaced by Stage 8, not introduced by it.

---

### [UX-005] — Minor — Copy — Formats note runs long and front-loads the .3mf the user can't always download

**Evidence**
`ExportPanel.tsx:196-203` (STEP-present note): a four-clause sentence covering .3mf, .STL, .STEP, and the orientation caveat. It leads with the .3mf — but the .3mf only exists *after* the user slices (`PrintSummary`, `ExportPanel.tsx:290-298`); at the moment the formats note first renders (post-design, pre-slice) there is no .3mf to download yet. The note describes a file the user may not have produced.

**Why this matters**
The note is accurate but mistimed: it explains the .3mf "from slicing above" before the user has sliced, so the first thing they read about is the one format that isn't there yet, while the two formats they *can* download right now (STL, and STEP if CadQuery) come second and third. Minor comprehension friction, and it makes an otherwise-strong note feel denser than it needs to.

**Blast radius**
- Adjacent code: both note branches (`ExportPanel.tsx:196-210`).
- User-facing: every maker reading the formats note.
- Tests to update: `ExportPanel.test.tsx:84` asserts a substring of this note — keep the substring stable or update the test.
- Related findings: none.

**Fix path**
Lead with what they can act on now, and gate the .3mf clause behind having sliced (or soften it to "once you slice"). Suggested rewrite for the STEP-present branch:
> *"The **.STL** opens in other slicers and CAD tools. The **.STEP** is the editable, precision CAD model from the CadQuery engine — open it in any CAD program to keep modeling (it's the as-designed shape; print orientation is applied only to the printable mesh). Once you slice, you'll also get a printer-agnostic **.3mf** that's safe to share."*

---

### [UX-006] — Nit — Copy — "engine" is mild jargon; "CadQuery" is an unexplained proper noun

**Evidence**
`ExportPanel.tsx:201, 208` — "the CadQuery engine." The term "CadQuery" is a library name exposed verbatim to end users with no gloss.

**Why this matters**
A maker doesn't necessarily know or care what "CadQuery" is; it's an implementation detail surfaced as user-facing copy. It's defensible (it's honest, and power users may recognize it), hence Nit — but a more outcome-focused phrasing ("the precision CAD engine") would read better to a general maker. Flag once.

**Fix path**
Optional: refer to it by what it does ("the precision CAD engine") and mention "CadQuery" parenthetically once, or drop the proper noun entirely in the maker-facing note and keep it in tooltips/docs.

---

### [UX-007] — Nit — Copy — `.STEP` vs `.step` casing

**Evidence**
The link label says "(.STEP)" (`ExportPanel.tsx:193`); STEP files conventionally use a lowercase `.step`/`.stp` extension. STL is likewise shown uppercase ("(.STL)").

**Why this matters**
Purely cosmetic — uppercasing the extension reads as a *format name* rather than a literal filename, which is a reasonable house style (and it's consistent with the STL label). Flagging only for consistency-of-intent; no action needed unless the team wants extensions to mirror real filenames.

**Fix path**
Leave as-is (consistent house style) or lowercase both for filename-fidelity. Team's call.

---

## States audit matrix

For the in-scope export-formats surface:

| Component / state | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| Formats area — OpenSCAD part | ✓ | n/a | ✓ (teaser note, no STEP) | n/a | — | Live-verified; UX-002 (teaser dead end) |
| Formats area — CadQuery part (STEP present) | ✓ (source) | n/a | n/a | n/a | — | Source-verified only; UX-003 styling gap |
| Gate-failed part | ✓ | n/a | ✓ (STL still offered, no slice) | ✓ | — | `ExportPanel.tsx:122-126` — handled well; STEP correctly suppressed with the formats note since `result.mesh_url` still renders |
| Backend provenance (engine shown) | ✗ | — | — | — | — | **Missing entirely** — UX-001 |

The download links themselves have no loading/error state, which is correct — they're plain hrefs; the browser owns download progress and failure. No missing-state finding there.

## Accessibility snapshot

- **Keyboard navigation:** Both download links are real `<a href download>` — natively focusable and in tab order. Pass.
- **Focus visibility:** Inherits the global focus treatment (`styles.css` uses `outline: 2px solid var(--kc-accent)` for focus, line ~156). Not separately verified on the STEP link in a rendered CadQuery state, but it inherits the anchor defaults — appears fine.
- **Color contrast:** Verified by computation. STL/STEP link text #b1542f on #faf6ee = **4.66:1** (AA pass, normal text). Formats note #6f6857 on #faf6ee at 11.5px = **5.14:1** (AA pass). Export error #a8431f on #faf6ee = **5.59:1**. No contrast finding in scope.
- **Screen reader labeling:** Link accessible names are the visible text ("Download editable CAD (.STEP)") — clear and self-describing. The `<strong>` emphasis in the note is decorative and doesn't harm the reading. Pass. One gap (not a contrast/label issue): per UX-001 the engine provenance is not conveyed to AT either, since it's not rendered at all.
- **Reduced motion:** No new animation introduced by this delta. n/a.
- **Touch target size:** Below 44×44 for the text links — UX-004 (pre-existing pattern, amplified by adding a second adjacent link).

## Patterns and systemic observations

- **Provenance is the systemic gap.** Stage 8's whole premise is "a different engine sometimes builds your part." The UI added the *output* of that (a STEP link) without adding the *fact* of it (which engine ran). The highest-leverage single fix in this delta is surfacing `report.backend` once, in the Printability card — it simultaneously fixes UX-001 and gives UX-002's teaser something to point at. The data is already on the wire; this is a pure presentation gap.
- **The export card's link tier is under-designed for a two/three-file world.** It was built for one model link; Stage 8 makes it a multi-format export region, and the styling/spacing/target-size assumptions (`.kc-download-model`, `.kc-formats`) haven't caught up (UX-003, UX-004). Worth a small, coordinated pass on `.kc-formats` rather than three separate touch-ups.
- **Copy quality is high and should be the template.** The as-designed caveat and the two-state teaser are model UX writing. The fixes above are refinements to genuinely good copy, not rescues of bad copy.

## Appendix: surfaces reviewed

- Live: `http://127.0.0.1:8765/` (demo SPA, OpenSCAD part) — Export & print card, formats note (OpenSCAD/no-STEP state), built CSS at `/assets/index.css` (confirmed no `.kc-download-step` rule, 54,511 bytes).
- Source: `frontend/src/components/ExportPanel.tsx` (lines 106-215 export card + 186-211 formats area; 220-315 PrintSummary for context), `frontend/src/api.ts` (`DesignResponse.step_url` line 86, `ReportPayload.backend` line 49), `frontend/src/components/ExportPanel.test.tsx` (full), `frontend/src/components/RightPanel.tsx` (PrintabilityCard 534-605, Readiness 505-532, attribution 341-344), `frontend/src/styles.css` (`.kc-download-model` 1728-1738, `.kc-formats` 1832-1843, `.kc-muted-note` 866-871, design tokens 44-73).
- Contrast computed against Workshop light-theme tokens; viewport assessment for touch targets is from CSS metrics (no live CadQuery render available).
