# Stage 8.5 — Usability: turn the demo into a tool people keep

**Why this stage exists.** The core loop works (describe → 3D → sliders → printability/readiness →
slice → download), but the product *around* the loop is missing in ways that make it unusable for
real, repeated use. Several are flat deal-killers — people will leave the first time they hit them.
This stage fixes **all** of them. Nothing is "too small to include": the polish tier is in scope too.

**Severity legend**
- 🔴 **Deal-killer** — a real person abandons the product when they hit this.
- 🟠 **Major** — clearly unfinished; blocks real (not demo) use.
- 🟡 **Polish** — small, but it's the difference between "rough" and "finished." In scope.

**Grounded in the current build** (verified by reading the source, 2026-06-03): the whole app is
`Landing → Workspace(Chat | Viewport | RightPanel[Parameters, Readiness, Printability, Export]) +
a Topbar with one "New design" button`. State is **all in-memory** (no routing, no persistence — a
browser refresh wipes the current part). There is **no** settings screen, **no** units handling
(mm only), **no** saved-designs surface, **no** follow-up/refine input in the workspace, **no**
problem visualization on the model, and **no** real progress during the multi-minute model call.

---

## Process (same bar as Stages 5–7)
Each slice: build → real `audit-lite` (with a **rendered** desktop+mobile browser check, since this
is UI) → fix every finding to 0/0/0/0/0 → push. Stage end: full 5-role `audit-team` → 0/0/0/0/0 →
merge → tag. UX is the acceptance gate, not an afterthought.

---

## Slice 1 — Persistence + "My Designs" (your work stops vanishing)
**Goal:** the app remembers what you made; you can come back to it.
- 🔴 **Persist designs locally** — plan, parameters, the mesh, a thumbnail, a name, a timestamp. (The Stage-7 learning store already records metadata; this is the real saved-design store + API.)
- 🔴 **Auto-save the current design + restore on reload** — a refresh (or a crash) no longer loses the part.
- 🔴 **URL routing / a real address per design** — back button works, refresh works, a design is linkable/shareable.
- 🔴 **A "My Designs" library** — thumbnail grid with name + date; click to reopen; reopen restores the part *and* its sliders.
- 🟠 **Rename / duplicate-and-tweak / delete** a saved design.
- 🟠 **Export / import a design file** — portability (back it up, send it to someone, move machines).
- 🟡 Sort + search the library; a sensible empty state ("nothing saved yet — make your first part").

## Slice 2 — Iterative refinement (the "conversation" actually works)
**Goal:** you can change a part by talking to it — today you can't, at all.
- 🔴 **A follow-up input in the workspace** — "make it 10mm taller / add mounting holes" refines the *current* part instead of forcing "New design" and starting over (which also loses the part).
- 🔴 **Answer a clarifying question inline** — the model can ask one, but right now there's no input to answer it; the flow dead-ends.
- 🟠 **Version timeline within a design** — v1 → vN, revisit any, **undo / step back**; "describe a change" is non-destructive (old version kept).
- 🟠 **Compare two versions** side-by-side.
- 🟡 The conversation reads as a real thread (multi-turn), not prompt + one reply.

## Slice 3 — Direct editing & numeric control
**Goal:** you can set exact values, and you can adjust AI-made parts at all.
- 🔴 **Manual numeric entry** for parameters — type "42.5", not just drag a slider (and it's units-aware, see Slice 4).
- 🔴 **A way to adjust AI-generated (non-template) parts** — today they're fully read-only (no sliders, no refine input). At minimum: editable key dimensions that re-render; ideally promote more parts to parametric.
- 🟠 Constrain/validate typed input (min/max, ordering) with clear inline feedback.
- 🟡 Keyboard nudges on a focused slider (arrow keys = ±step).

## Slice 4 — Units (mm **and** inches)
**Goal:** a US maker isn't walled out.
- 🔴 **A units preference (mm/inch), persisted**, applied **everywhere** — sliders, the dims table, size, bbox, readiness, the slice estimate.
- 🔴 **Inch input** — accept "2in", "2.5", and common fractions on entry; the prompt understands it too ("a 2-inch cube").
- 🟠 Store canonical mm, display the chosen unit; round-trip without drift; sensible rounding per unit.
- 🟡 A quick unit toggle near the dimensions, not buried in settings.

## Slice 5 — Settings + engine discoverability (config files → in-app)
**Goal:** there's an actual place in the app to see and change things — and to *discover* the optional engines.
- 🔴 **An in-app Settings screen** — default printer + material, units, and where the model/tools status lives. Today every one of these is YAML a normal person never opens.
- 🔴 **Model status + control** — is Ollama running? is the model pulled? which model? Surfaced and switchable, not silent.
- 🔴 **Optional-engine management** — CadQuery (precision CAD, Stage 8) and PrintProof3D (deeper validation) shown as **available, one-click-enable** capabilities with install/download status. "Off by default" must mean *not downloaded*, **not hidden**.
- 🟠 **Contextual enable** — the Export panel's "STEP/BREP" offers to turn on CadQuery right there; the readiness card surfaces "deeper validation available." Discovery at the moment of need.
- 🟡 Tools health (OpenSCAD / OrcaSlicer present?), an About/version, a reset.

## Slice 6 — Show problems on the model (text → visual)
**Goal:** the validator already knows *where* the overhang is — show it.
- 🟠🔴 **Highlight problem regions in the 3D viewport** — overhangs, poor bed contact, etc., colored on the actual model. (PrintProof3D returns the exact triangles; KimCad currently throws that geometry away and shows a word. Keep + forward it.)
- 🟠 **Click a risk in the readiness card → focus/zoom that region** on the model; hover to preview.
- 🟡 A legend + an on/off toggle for the overlays; the same treatment for locatable gate findings.

## Slice 7 — Onboarding, the model-down wall, progress, help
**Goal:** a new user (or a stalled model) doesn't hit a dead end that reads as "broken."
- 🔴 **The model-not-running state** — if Ollama isn't up, a clear, recoverable "your local AI isn't running — here's how to start it," not a raw error string.
- 🔴 **Real progress on long runs** — a CPU model call takes minutes; today it's one spinner + "Designing your part…", which reads as frozen. Show steps (planning → generating → rendering → validating) and "this can take a minute on your hardware."
- 🟠 **First-run setup** (pulled forward from Stage 10/11) — detect Ollama, offer to pull the model with progress, pick a printer.
- 🟠 **In-app help / a glossary** — plain-language tooltips on gate / readiness / manifold / slice.
- 🟡 Audit **every** surface's empty / loading / error state for human, recoverable copy (the "no too small" sweep).

## Slice 8 — Output clarity & print preview
**Goal:** you can see what you're actually going to get.
- 🟠 **Break out the estimate** — time, filament length **and** weight, layer count (maybe a rough cost), not one text blob.
- 🟠 **A print preview** — a sliced/layer view, or at least a clearer "this is your part → this is the print."
- 🟡 Surface the export formats clearly (STL / 3MF today; STEP / BREP arrives with Stage 8); a copy-the-file affordance.

## Slice 9 — Responsive, accessibility, copy, polish (cross-cutting)
**Goal:** finished, not just functional. The explicit "no too small" tier.
- 🟠 **Mobile actually usable** — the stacked workspace, the viewport on touch, and the new gallery/settings screens work on a phone (not just "non-overlapping").
- 🟠 **Accessibility sweep** — focus management across the new screens, keyboard nav, ARIA, the gallery/settings/overlay surfaces.
- 🟡 **Copy pass** — plain English everywhere; kill the jargon ("manifold", "gate"); consistent voice.
- 🟡 **Keyboard shortcuts** — new design, slice, save, navigate the gallery.
- 🟡 Loading skeletons, hover/focus states, transitions; one more pass over every empty/error state.

---

## Sequencing note (one open decision)
Named "8.5," but several slices interlock with **Stage 8 (CadQuery)**: the settings/engine-enable
surface (Slice 5) is exactly what makes CadQuery discoverable, persistence (Slice 1) is what saves a
STEP export, and units (Slice 4) matter for precision CAD. **Recommendation: do Stage 8.5 first (or
at least Slices 1, 4, 5 before the CadQuery backend)** so CadQuery lands into a product that can
actually surface, persist, and present it — rather than adding a second power feature on top of a
foundation that still loses your work on refresh. Open to doing 8 → 8.5 if you'd rather finish the
backend first.

## Honest scope
This is large — it's the step that turns a clever demo into a tool someone keeps open. That's the
point. The deal-killers (🔴) are the floor; the 🟠/🟡 tiers are what make it feel finished. All in.
