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
a Topbar with one "New design" button`. State *was* **all in-memory** (no routing, no persistence — a
browser refresh wiped the current part) — **Slice 1 has since added routing + local persistence + the
"My Designs" library**; the baseline below describes the rest still open. There is **no** settings screen, **no** units handling
(mm only), **no** saved-designs surface, **no** follow-up/refine input in the workspace, **no**
problem visualization on the model, and **no** real progress during the multi-minute model call.

---

## Process (same bar as Stages 5–7, plus a runtime wiring gate)
Each slice: build → real `audit-lite` (with a **rendered** desktop+mobile browser check, since this
is UI) → fix every finding to 0/0/0/0/0 → push. Slice/stage end: full 5-role `audit-team` (static —
code/docs/tests) → fix to 0/0/0/0/0 → **`wiring-audit` (runtime — drives the real app in a browser
and proves every control is genuinely wired + persists, not just cosmetic)** → fix to 0/0/0/0/0 →
THEN hand to Scott for his walkthrough + approval. Stage end: merge → tag. The two audit lanes are
not interchangeable — `audit-team` reads the code, `wiring-audit` drives the running interface; run
both. UX is the acceptance gate, not an afterthought.

---

## Slice 1 — Persistence + "My Designs" (your work stops vanishing) — ✅ DONE (on branch `stage-8.5-usability`; `audit-team` + two re-audits → 0/0/0/0/0; pending Scott's approval)
**Goal:** the app remembers what you made; you can come back to it.
- 🔴 **Persist designs locally** — plan, parameters, the mesh, a thumbnail, a name, a timestamp. (The Stage-7 learning store already records metadata; this is the real saved-design store + API.)
- 🔴 **Auto-save the current design + restore on reload** — a refresh (or a crash) no longer loses the part.
- 🔴 **URL routing / a real address per design** — back button works, refresh works, a design is linkable/shareable.
- 🔴 **A "My Designs" library** — thumbnail grid with name + date; click to reopen; reopen restores the part *and* its sliders.
- 🟠 **Rename / duplicate-and-tweak / delete** a saved design.
- 🟠 **Export / import a design file** — portability (back it up, send it to someone, move machines).
- 🟡 Sort + search the library; a sensible empty state ("nothing saved yet — make your first part").

## Slice 2 — Iterative refinement (the "conversation" actually works) — ✅ IMPLEMENTED (on branch `stage-8.5-usability`; pending the Slice 2–4 `audit-team` + `wiring-audit` gate + Scott's approval)
**Goal:** you can change a part by talking to it — today you can't, at all.
- 🔴 **A follow-up input in the workspace** — "make it 10mm taller / add mounting holes" refines the *current* part instead of forcing "New design" and starting over (which also loses the part).
- 🔴 **Answer a clarifying question inline** — the model can ask one, but right now there's no input to answer it; the flow dead-ends.
- 🟠 **Version timeline within a design** — v1 → vN, revisit any, **undo / step back**; "describe a change" is non-destructive (old version kept).
- 🟠 **Compare two versions.** **Built:** a compare *summary* card (each version's summary / gate / readiness) with a **"what changed" delta** (per-axis dimension changes + readiness delta), rather than a two-viewport geometry side-by-side — the delta answers "which do I keep?" without the second 3D view.
- 🟡 The conversation reads as a real thread (multi-turn), not prompt + one reply.

## Slice 3 — Direct editing & numeric control — ✅ IMPLEMENTED (on branch `stage-8.5-usability`; pending the Slice 2–4 `audit-team` + `wiring-audit` gate + Scott's approval)
**Goal:** you can set exact values, and you can adjust AI-made parts at all.
- 🔴 **Manual numeric entry** for parameters — type "42.5", not just drag a slider (and it's units-aware, see Slice 4).
- 🔴 **A way to adjust AI-generated (non-template) parts** — today they're fully read-only (no sliders, no refine input). **Built:** non-template parts are adjusted through the **Slice-2 conversation refine** ("make it 10mm taller" → a new version), with an in-card hint pointing there — the refine path covers the same need without faking sliders on a non-parametric mesh. **Deferred (future option):** inline editable key dimensions on non-template parts / promoting more parts to parametric.
- 🟠 Constrain/validate typed input (min/max, ordering) with clear inline feedback.
- 🟡 Keyboard nudges on a focused slider (arrow keys = ±step).

## Slice 4 — Units (mm **and** inches) — ✅ IMPLEMENTED (on branch `stage-8.5-usability`; pending the Slice 2–4 `audit-team` + `wiring-audit` gate + Scott's approval)
**Goal:** a US maker isn't walled out.
- 🔴 **A units preference (mm/inch), persisted**, applied to the editable + read-out surfaces — **Built:** sliders (value label + numeric input + `aria-valuetext`), the size/bbox readout, and the printability **dims table** all convert on one toggle (a shared store keeps the cards in lockstep). **Deferred (future slice):** converting the **readiness card** and the **slice estimate** to the chosen unit.
- 🔴 **Inch input** — **Deferred (future slice):** parsing inch *text* on entry ("2in", common fractions) and the **prompt** understanding "a 2-inch cube". Slice 4 ships unit-aware *numeric* entry (type an inch value into the slider's number field; it commits the mm-converted value) but not free-text inch parsing; the backend stays canonical mm.
- 🟠 Store canonical mm, display the chosen unit; round-trip without drift; sensible rounding per unit (inch shows 3 dp so thin, nozzle-multiple walls stay editable).
- 🟡 A quick unit toggle near the dimensions, not buried in settings.

## Slice 5 — Advanced on-ramps & trust (DESIGN ONLY — no code; Scott's review is the gate)
**Goal:** figure out the UI/UX **and the trust posture** for the three advanced on-ramps *before* a line of them is built — UI-first, the way the rest of the product is gated. (Inserted 2026-06-03 at Scott's direction: the photo on-ramp, the cloud path, and the experimental generator all get designed first, here, rather than bolted on later.)
- **Design the surfaces** (flows + mockups against the Workshop design system): (a) the **model picker** (gemma4:e4b the default, always); (b) the **cloud opt-in** (OpenRouter — an API-key field + a clear local/cloud label); (c) the **experimental raw-codegen generator** toggle; (d) the **photo input mode** (an alternate "describe with a photo" on-ramp).
- **Lock the trust rules below** in writing as hard constraints on the builds that follow.
- Deliverable: a design doc + mockups, reviewed and approved by Scott. No product code ships in this slice.

### Trust rules — HARD constraints on Slices 6–7 (settled; not re-decided ad hoc)
- **gemma4:e4b is the only default** — text, codegen, **and vision** (the photo on-ramp uses *its* vision). Nothing silently switches models; no alternative is offered in the UI; a Chinese model (Qwen/MiniCPM/Qwen-VL) is never a default or a recommendation. Qwen stays a manual `--backend` only.
- **Cloud is always opt-in, OFF by default, and labeled** "this sends data off your machine" at the point of use. Local-first stays the resting truth.
- **API key = a normal Settings field** (this is a consumer product): the user enters it and saves it; on reopening Settings it's shown **masked — last 5–6 characters only**. Never stored in the repo or logs; the full secret is never echoed back.
- **The experimental raw-codegen generator is OFF by default, labeled untrusted/experimental**, and runs **only** through the existing `openscad_runner` sandbox (blocked-code check — bans file-I/O `import()`/`surface()`, `use`/`include` outside the bundled `library/`, and `minkowski()` — plus cwd isolation, render timeout, output-size cap). It never bypasses the Printability Gate.
- **Photo on-ramp** uses gemma4:e4b's **local** vision; the photo never auto-sends; it produces a *rough seed* the user then refines (Slice 2 conversation + Slice 3 numeric entry), not a finished part.

## Slice 6 — Settings + engine discoverability (config files → in-app) — ✅ IMPLEMENTED (in-app Settings screen, model status, cloud opt-in, experimental toggle, tools health/about/reset; `audit-team` → 0/0/0/0/0; pending Scott's approval. The optional-engine one-click-enable for CadQuery/PrintProof3D is deferred to Stage 8, where CadQuery lands.)
**Goal:** there's an actual place in the app to see and change things — and to *discover* the optional engines and the advanced on-ramps. Builds the cloud + experimental toggles per the Slice-5 design.
- 🔴 **An in-app Settings screen** — default printer + material, units, and where the model/tools status lives. Today every one of these is YAML a normal person never opens.
- 🔴 **Model status + control** — is Ollama running? is `gemma4:e4b` pulled? Surfaced clearly; gemma4:e4b stays the default (no model menu that pushes alternatives).
- 🔴 **Optional-engine management** — CadQuery (precision CAD, Stage 8) and PrintProof3D (deeper validation) shown as **available, one-click-enable** capabilities with install/download status. "Off by default" must mean *not downloaded*, **not hidden**.
- 🟠 **Cloud opt-in (per the Slice-5 design)** — an OpenRouter **API-key field (enter + save + masked redisplay, last 5–6 chars)** with a clear local/cloud label; off by default; "sends data off your machine" stated at the point of use.
- 🟠 **Experimental raw-codegen toggle (per the Slice-5 design)** — off by default, labeled untrusted, routed through the `openscad_runner` sandbox; never bypasses the Printability Gate.
- 🟠 **Contextual enable** — the Export panel's "STEP/BREP" offers to turn on CadQuery right there; the readiness card surfaces "deeper validation available." Discovery at the moment of need.
- 🟡 Tools health (OpenSCAD / OrcaSlicer present?), an About/version, a reset.

## Slice 7 — Photo on-ramp ("describe with a photo") — ✅ IMPLEMENTED (MS-1 local-vision backend + `POST /api/photo-seed`; MS-2 the on-ramp UI; audit-lite-gated per micro-slice; slice-end `audit-team` + `wiring-audit` → 0/0/0/0/0; pending Scott's walkthrough)
**Goal:** start a design from a photo, **locally** — pulled forward from Stage 9 because it's UI-first and built per the Slice-5 design.
- 🔴 **A "use a photo" input mode** — upload/drop a photo; **gemma4:e4b's local vision** reads it into a description + rough proportions that **seed the existing text→DesignPlan path** (it does not replace or bypass it). No cloud required.
- 🔴 **Honest framing** — the result is a *rough starting point* refined with the conversation (Slice 2) + numeric entry (Slice 3); a photo carries no scale, so dimensions are estimates until the user sets them. No "photo → finished part" promise.
- 🟠 **The photo never auto-sends** — local vision by default; any cloud vision path is opt-in + labeled per the trust rules.
- 🟡 Sensible states — an unreadable / over-large image, a "couldn't read that photo," and real progress while the vision model runs on CPU.

## Slice 8 — Show problems on the model (text → visual)
**Goal:** the validator already knows *where* the overhang is — show it.
- 🟠🔴 **Highlight problem regions in the 3D viewport** — overhangs, poor bed contact, etc., colored on the actual model. (PrintProof3D returns the exact triangles; KimCad currently throws that geometry away and shows a word. Keep + forward it.)
- 🟠 **Click a risk in the readiness card → focus/zoom that region** on the model; hover to preview.
- 🟡 A legend + an on/off toggle for the overlays; the same treatment for locatable gate findings.

## Slice 9 — Onboarding, the model-down wall, progress, help
**Goal:** a new user (or a stalled model) doesn't hit a dead end that reads as "broken."
- 🔴 **The model-not-running state** — if Ollama isn't up, a clear, recoverable "your local AI isn't running — here's how to start it," not a raw error string.
- 🔴 **Real progress on long runs** — a CPU model call takes minutes; today it's one spinner + "Designing your part…", which reads as frozen. Show steps (planning → generating → rendering → validating) and "this can take a minute on your hardware."
- 🟠 **First-run setup** (pulled forward from Stage 10/11) — detect Ollama, offer to pull the model with progress, pick a printer.
- 🟠 **In-app help / a glossary** — plain-language tooltips on gate / readiness / manifold / slice.
- 🟡 Audit **every** surface's empty / loading / error state for human, recoverable copy (the "no too small" sweep).

## Slice 10 — Output clarity & print preview
**Goal:** you can see what you're actually going to get.
- 🟠 **Break out the estimate** — time, filament length **and** weight, layer count (maybe a rough cost), not one text blob.
- 🟠 **A print preview** — a sliced/layer view, or at least a clearer "this is your part → this is the print."
- 🟡 Surface the export formats clearly (STL / 3MF today; STEP / BREP arrives with Stage 8); a copy-the-file affordance.

## Slice 11 — Responsive, accessibility, copy, polish (cross-cutting)
**Goal:** finished, not just functional. The explicit "no too small" tier.
- 🟠 **Mobile actually usable** — the stacked workspace, the viewport on touch, and the new gallery/settings screens work on a phone (not just "non-overlapping").
- 🟠 **Accessibility sweep** — focus management across the new screens, keyboard nav, ARIA, the gallery/settings/overlay surfaces.
- 🟡 **Copy pass** — plain English everywhere; kill the jargon ("manifold", "gate"); consistent voice.
- 🟡 **Keyboard shortcuts** — new design, slice, save, navigate the gallery.
- 🟡 Loading skeletons, hover/focus states, transitions; one more pass over every empty/error state.

---

## Sequencing note (one open decision)
Named "8.5," but several slices interlock with **Stage 8 (CadQuery)**: the settings/engine-enable
surface (Slice 6) is exactly what makes CadQuery discoverable, persistence (Slice 1) is what saves a
STEP export, and units (Slice 4) matter for precision CAD. **Recommendation: do Stage 8.5 first (or
at least Slices 1, 4, 6 before the CadQuery backend)** so CadQuery lands into a product that can
actually surface, persist, and present it — rather than adding a second power feature on top of a
foundation that still loses your work on refresh. Open to doing 8 → 8.5 if you'd rather finish the
backend first.

## Honest scope
This is large — it's the step that turns a clever demo into a tool someone keeps open. That's the
point. The deal-killers (🔴) are the floor; the 🟠/🟡 tiers are what make it feel finished. All in.
