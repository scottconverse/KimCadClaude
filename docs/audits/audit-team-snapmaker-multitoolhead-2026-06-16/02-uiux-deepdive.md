# UI/UX Deep-Dive — KimCad Snapmaker U1 / Multi-Toolhead

**Audit date:** 2026-06-16
**Role:** Senior UI/UX Designer
**Scope audited:** ExportPanel.tsx (multi-material slot dropdowns, commits cc80fed + 3553665), SendPanel.tsx (toolhead temperature chips after a real send)
**Auditor posture:** Balanced

---

## TL;DR

The multi-toolhead additions are structurally sound and follow the existing `kc-field` visual language. The critical gap is that `kc-temp-chip` and `kc-send-temps` have zero CSS — the chips will render as unstyled inline text jammed into the live-status line, breaking both the visual language and scan-ability at the one moment the user most wants clear feedback. Secondary issues are jargon copy ("T1 Material" means nothing to a newcomer) and a complete absence of pre-send context (the user sees N dropdowns with no explanation of what multi-material slicing actually does to their print). The print estimate after slicing does not reflect per-slot materials, so users can't verify their slot assignments produced the expected output.

---

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 3 |
| Minor | 2 |
| Nit | 1 |

---

## What's working

- **`kc-field` reuse is correct** — The multi-slot dropdowns slot cleanly into the existing label/select pattern. No layout regressions on the single-head path.
- **Reset-on-printer-change is handled** — The `useEffect` on `[printer, selectedMaterial]` correctly re-initializes `materialSlots`, so switching back to a single-head printer collapses the N dropdowns cleanly; the transition is not abrupt.
- **Simulated-send honesty** — Temperature chips are gated on `!r.simulated`, so a test-connection send never emits fake thermal readings. Good discipline.
- **`aria-hidden` on status dots** — Decorative dots in the live-status line carry `aria-hidden="true"`. Correct.
- **`focus-visible` on `kc-field select`** — The CSS at line 1954 applies a visible accent-colored outline on keyboard focus. The new dynamic dropdowns inherit this for free.

---

## What couldn't be assessed

- **Runtime layout at high toolhead_count (8, 16)** — The harness cannot drive the live app on this box (exclusive Windows port bind). Analysis is based on CSS and TSX only; the flex-column stacking behavior at N > 4 cannot be observed directly. Flagged under UX-003.
- **Screen reader announcement order** — The order in which a screen reader reads the dynamically inserted slot labels was inferred from DOM structure, not live tested.
- **Actual temperature chip rendering** — No CSS exists for `kc-temp-chip` / `kc-send-temps`; visual appearance is what the browser's user-agent stylesheet and inherited text styles produce (unknown without runtime observation).

---

## First impressions

A user who has just selected the Snapmaker U1 (or any multi-toolhead printer) and lands on the Export & print card sees the single "Material" label disappear and N labels appear in its place, labeled "T1 Material", "T2 Material", etc. There is no sentence, no tooltip, no inline note explaining that T1/T2 refer to extruder slots on a multi-toolhead printer, or what assigning different materials to each slot will do to the print. For a user who has only used single-extrusion printers — the dominant 3D printing user — the UI is opaque at first contact.

---

## Journey walkthroughs

### Journey: User with Snapmaker U1 → multi-material export

1. User selects Snapmaker U1 from the Printer dropdown. The single "Material" select is replaced by two (or more) selects labeled "T1 Material", "T2 Material".
2. User assigns materials. No confirmation that slot 1 = primary, slot 2 = secondary, or what that means for support structures vs. body vs. purge.
3. User clicks "Slice & prepare file". The `postSlice` call sends `filament_slot_0`, `filament_slot_1`, etc. The `PrintSummary` renders with `slice.material` — this is the PRIMARY material key from the single `selectedMaterial` argument to `postSlice`, not a multi-slot summary. The print summary line reads "Sliced for [printer] in [T1 material]." — the T2 material assignment is invisible in the success state.
4. User sends to printer (real connection). After send, `live.toolhead_temps` may populate. The chips render as unstyled text inside the `kc-send-live` flex row — no visual separation from the status label, no background, no border.

---

## Findings

### [UX-001] — Critical — State — Temperature chips render as unstyled inline text; no CSS for `kc-temp-chip` or `kc-send-temps`

**Evidence**

`SendPanel.tsx` lines 273–279 render:
```jsx
<span className="kc-send-temps">
  {live.toolhead_temps.map((t, i) => (
    <span key={i} className="kc-temp-chip">T{i+1}: {t.toFixed(0)}°C</span>
  ))}
</span>
```

`styles.css` contains no rule for `.kc-temp-chip` or `.kc-send-temps`. A grep across the entire CSS file returns zero matches. The `kc-send-live` container (`line 3289`) is a flex row with `gap: 6px` and `color: var(--kc-muted)`. Both spans will render as unstyled muted text fragments with no visual differentiation from the surrounding status label.

**Why this matters**

The temperature chips appear at the moment of highest user attention — just after a real print has started. They need to be scannable data units (pill shape, mono font, perhaps a warm accent color). As unstyled text inside a muted flex row they are invisible as information: "Printing — your job is running. T1: 210°C T2: 205°C" reads as one gray sentence. A user who glances at the status line cannot distinguish the temperatures from prose.

**Blast radius**
- Adjacent code: `kc-send-live` in `styles.css` (line 3289) is the parent; any future chip types added here will share the same missing-CSS problem.
- User-facing: every user of a multi-toolhead printer who sends a real job and has live status will see this. It is the only real-hardware feedback path in the new feature.
- Migration: none — purely additive CSS.
- Tests to update: none known (no visual regression tests on `SendPanel` live states).

**Fix path**

Add to `styles.css` immediately after `.kc-send-live`:

```css
.kc-send-temps {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin-left: 4px;
}
.kc-temp-chip {
  font-family: var(--kc-mono);
  font-size: 11.5px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--kc-bg-raised, var(--kc-bg));
  border: 1px solid var(--kc-hair-strong);
  color: var(--kc-ink);
  white-space: nowrap;
}
```

---

### [UX-002] — Major — Copy — "T1 Material" / "T2 Material" is jargon with no context; first-time multi-toolhead users are left to guess

**Evidence**

`ExportPanel.tsx` line 160:
```jsx
<span>T{i + 1} Material</span>
```

The single-head label at line 181 reads simply `Material`. The multi-head labels switch to `T{n} Material` with no inline help, tooltip, or explanatory note. The `T` prefix is Marlin/Klipper G-code convention (T0/T1 = toolhead index). It is not a consumer-facing term; Snapmaker's own UI calls these "Extruder 1" and "Extruder 2".

**Why this matters**

A user unfamiliar with multi-extrusion who has selected the Snapmaker U1 sees two dropdowns with no guidance on: which slot is the "primary" extruder, what happens when slots carry different materials, whether slot order matters for the specific model, or what a "generic profile" warning on a secondary slot means. This directly impairs the one configuration task the new feature introduces.

**Blast radius**
- Adjacent code: The same label pattern would apply to any future N-toolhead printer addition.
- User-facing: every new Snapmaker U1 user who has not operated a multi-extrusion printer before.
- Related findings: UX-004 (no post-slice confirmation of per-slot materials).

**Fix path**

Option A (preferred): Change the label to "Extruder {n} material" and add a one-line note above the slot block:

```
Assign a filament to each extruder — the slicer uses these profiles to tune temperature and retraction per slot.
```

Option B (minimal): Change label from `T{i+1} Material` to `Extruder {i+1}` and add a `title` tooltip on the `<span>`: `title="Which filament this extruder will print with"`.

Either option is a one-line TSX change plus a `<p className="kc-muted-note">` before the slot map.

---

### [UX-003] — Major — Responsive — N-dropdown vertical stack has no cap; at high toolhead_count the Export card becomes a scroll well

**Evidence**

`ExportPanel.tsx` lines 157–176: `materialSlots.map(...)` renders one `kc-field` per slot in a flex-column (inherited from the card's normal stacking). `toolhead_count` is a server-provided integer with no client-side cap. `PrinterOption.toolhead_count` in `api.ts` (line 121) is typed `number | undefined` — no maximum.

The Snapmaker U1 has 2 toolheads. But the type allows 8 or 16 (conceivable for future gang-print or pen-plotter configurations). At N = 8 the Export card would render 8 `kc-field` rows between the Printer selector and the Slice button, with no visual grouping.

**Why this matters**

Even at N = 4 the Export card becomes a long scroll target. At N > 4 the Slice button (the primary CTA) scrolls off the visible area of the card on typical laptop viewports, which is a journey dead-end: the user fills in slots but cannot see the action to proceed. This cannot be verified at runtime here but is a structural risk in the layout.

**Blast radius**
- Adjacent code: `kc-slice-actions` (line 1960) and the Slice button sit after the slot map; any increase in N pushes the button further down.
- User-facing: any printer with toolhead_count > 3.
- Migration: none.

**Fix path**

Add a two-column grid layout for the slot dropdowns when `toolhead_count > 2`:

```css
.kc-material-slots {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
```

Wrap the slot map in `<div className="kc-material-slots">`. This keeps the Slice button visible and groups the slots as a coherent block distinct from the single Printer selector.

---

### [UX-004] — Major — State — Post-slice `PrintSummary` shows only the primary material; per-slot assignments are invisible after slicing

**Evidence**

`ExportPanel.tsx` line 326:
```jsx
<p className="kc-print-lead">
  Sliced{slice.printer ? ` for ${slice.printer}` : ''}
  {slice.material ? ` in ${slice.material}` : ''}. Here's your print:
</p>
```

`SliceResponse` has a single `material?: string` field (api.ts line 154). The `postSlice` call passes `selectedMaterial` as the primary material and `materialSlots` as per-slot overrides, but the response only echoes a single `material`. The print summary line therefore reads "Sliced for Snapmaker U1 in PLA" when the user assigned PLA to T1 and TPU to T2 — the T2 assignment is silently dropped from the success state.

**Why this matters**

A user who assigned a support-dissolution filament (e.g. PVA) to T2 and PLA to T1 cannot verify from the success UI that their T2 assignment was honored. The only route to confirmation is downloading and inspecting the .3mf file. This creates doubt at exactly the moment the user should feel confident to start the print.

**Blast radius**
- Adjacent code: `PrintSummary` component (ExportPanel.tsx line 288); `SliceResponse` type in api.ts; backend `/api/slice/` response schema.
- User-facing: any multi-toolhead slice where T2+ assignments matter.
- Related findings: UX-002 (slot label jargon), UX-003 (no slot grouping).
- Backend change required: `SliceResponse` needs a `materials?: string[]` or `material_slots?: Record<string, string>` field echoed from the slicer.

**Fix path**

Short-term (frontend only): If `materialSlots.length > 1`, display the slots in the `PrintSummary` lead line from the client state (the value is available in scope):

```
Sliced for Snapmaker U1 — Extruder 1: PLA, Extruder 2: TPU. Here's your print:
```

The client already has `materialSlots` at the time `PrintSummary` renders, but it is not passed down as a prop. Pass it: `<PrintSummary slice={slice} materialSlots={selectedPrinter?.toolhead_count > 1 ? materialSlots : undefined} />`.

Longer-term: the backend should echo per-slot materials in `SliceResponse` for authoritative confirmation.

---

### [UX-005] — Minor — Accessibility — Dynamic slot `<label>` elements lack unique `htmlFor`/`id` association; screen readers may not announce the slot name with the select

**Evidence**

`ExportPanel.tsx` lines 158–175: each slot renders a `<label className="kc-field">` wrapping a `<span>` and a `<select>`. There is no `htmlFor` on the label or `id` on the select. The wrapping `<label>` gives an implicit association, which is valid HTML and works in most browsers. However, the implicit association relies on the label element containing only one interactive descendant; the `<span>` inside the label is not interactive so the association is correct. This is technically valid but the lack of an explicit `id`/`htmlFor` pair means some assistive technology combinations (notably older NVDA + Firefox) may not announce the slot label when the select receives focus.

**Why this matters**

A keyboard-only or screen reader user navigating the slot selects hears "T1 Material, combo box" on current mainstream AT. On some older combinations they may only hear "combo box."

**Fix path**

Add explicit IDs:
```jsx
<label key={i} className="kc-field" htmlFor={`kc-slot-${i}`}>
  <span id={`kc-slot-label-${i}`}>Extruder {i + 1}</span>
  <select id={`kc-slot-${i}`} aria-labelledby={`kc-slot-label-${i}`} ...>
```

---

### [UX-006] — Minor — State — Temperature chips have no "before-send" state; the user sees no thermal information before starting the print

**Evidence**

`SendPanel.tsx` lines 273–279: `live?.toolhead_temps` is populated only after `r.sent && !r.simulated` triggers the `pollStatus` chain. Before the send, the live state is `null`. There is no pre-send thermal check: the user cannot see whether the printer is already at temperature (idle warm) or cold (will require a preheat).

**Why this matters**

Snapmaker U1 users who return to a part after a prior print may want to know the printer is already warm before committing to the send dialog. The current flow hides all thermal information until AFTER the confirmation dialog fires. This is acceptable but a missed opportunity for the "is my printer ready?" moment.

**Fix path**

On the "configured, non-simulated" branch, an optional `GET /api/connector-status/{name}` is already made for the setup-note fetch (`needsNote` path). This is not done for the pre-send thermal check. Consider a lightweight pre-send status fetch to populate `live` before the user opens the confirm dialog — or at minimum display nozzle temps in the confirm dialog body for multi-toolhead connections. This is an enhancement, not a bug.

---

### [UX-007] — Nit — Copy — "T{i+1}: {t.toFixed(0)}°C" in the chip is correct but dense; the degree symbol runs into the number

**Evidence**

`SendPanel.tsx` line 277: `` `T${i+1}: ${t.toFixed(0)}°C` ``

Renders as "T1: 210°C" — no space before the degree symbol. Convention for temperature display is "210 °C" (space before unit, SI style) or "210°C" (no space, informal). The current output is consistent with the informal style and is unambiguous. Not a correctness issue.

**Fix path**

No change required. If a style guide is adopted later, align with it then.

---

## States audit matrix

| Component / page | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| ExportPanel — single-head | ✓ | ✓ | ✓ | ✓ | — | No change from prior audit |
| ExportPanel — multi-slot | ✓ | ✓ | — | — | — | No empty-slot state (slots always initialize from `selectedMaterial`); no per-slot validation error if slot value is blank string |
| SendPanel — pre-send | ✓ | — | — | — | — | No thermal/status pre-send state; UX-006 |
| SendPanel — post-send (real) | ✓ | — | ✓ | ✓ | ✗ | Temp chips: no CSS (UX-001); partial = some toolhead_temps null is unhandled (see below) |
| PrintSummary — multi-slot | ✓ | — | — | — | ✗ | Per-slot material echo missing (UX-004) |

**Partial data note:** `toolhead_temps` is typed `number[] | null`. If the array is partially populated (e.g. `[210, null]` from a printer that only reports T1), `t.toFixed(0)` will throw on `null`. The map is `live.toolhead_temps.map((t, i) => <span ...>T{i+1}: {t.toFixed(0)}°C</span>)` — no null guard. This is an edge-case crash path, not a normal-operation issue, but should be noted for Engineering.

---

## Accessibility snapshot

- **Keyboard navigation:** All new `<select>` elements inherit keyboard operability from the browser's native control. No custom widget is introduced. Acceptable.
- **Focus visibility:** `kc-field select:focus-visible` (line 1954) provides a visible accent outline. New slots inherit this. Pass.
- **Color contrast:** `kc-field > span` uses `var(--kc-muted)` for the label text. This is a shared token used throughout the app and passes WCAG AA in the existing theme (assumption based on prior audits; token value not sampled here).
- **Screen reader labeling:** Dynamic slots use implicit label association (UX-005, Minor). `kc-temp-chip` spans carry no ARIA label beyond their text content — "T1: 210°C" is readable by screen readers as-is.
- **Reduced motion:** No animation introduced. Pass.
- **Touch target size:** Native `<select>` elements with `padding: 8px 10px` (line 1945) produce targets well above 44px tall on all mainstream platforms. Pass.

---

## Patterns and systemic observations

The approach of inline-expanding a single control into N controls on printer selection is a valid progressive-disclosure pattern, but this feature skips the explanatory layer that makes the expansion meaningful. Every other multi-option surface in KimCad pairs its controls with a `kc-muted-note` explaining the context (the gate-failed note, the no-slicer-profile note, the warn-gate caution note are all present and correct). The multi-slot section is the one exception. Add a single muted note above the slot block and the feature crosses from "functional" to "understandable."

---

## Appendix: surfaces reviewed

- `frontend/src/components/ExportPanel.tsx` (full file)
- `frontend/src/components/SendPanel.tsx` (full file)
- `frontend/src/api.ts` — `ConnectorStatusResponse`, `SliceResponse`, `PrinterOption`, `postSlice`
- `frontend/src/styles.css` — `.kc-field`, `.kc-send-panel`, `.kc-send-live`, `.kc-send-temps` (absent), `.kc-temp-chip` (absent)
- Viewport sizes: not observable at runtime; layout analysis is static/structural only
