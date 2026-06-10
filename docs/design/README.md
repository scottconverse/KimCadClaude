# Handoff: KimCad — Consumer AI → 3D-Print Interface

> ## ⚠ SUPERSEDED POSTURE — read before building to this doc
> This design reference predates two **settled, load-bearing** product decisions. Where the prototype
> below contradicts these, the decisions win (build to them, not to the prototype's visuals):
> - **Model:** `gemma4:e4b` is THE default and the only model the UI presents (text, codegen, AND
>   vision). The "Choose a model" step's **Qwen2.5-Coder "RECOMMENDED"** card (§ first-run wizard) is
>   superseded — Qwen was evaluated via a live bake-off and **rejected (0/10)**; it is not a default,
>   not "recommended", and not bundled. The model surface is a **status readout** (is gemma4:e4b
>   pulled / running?), never a menu of alternatives, and never a Chinese model.
> - **Photo on-ramp vision is LOCAL by default.** The image on-ramp's "Default analysis runs on a
>   free OpenRouter vision model — your photo leaves the device" is superseded: the photo is read by
>   **gemma4:e4b's local vision** by default and never auto-sends. Any cloud vision path is strictly
>   opt-in and labeled at the point of use. Cloud (OpenRouter) is OFF by default everywhere.
>
> **Stage 9 correction (2026-06-10) to the vision half of the above:** gemma4:e4b's vision is
> **broken on this stack** (measured — it deterministically hallucinates and reports "no visible
> image was provided"; see `docs/benchmarks/stage-9-vision-onramps.md`). Images are read by a
> dedicated small LOCAL vision model, **`qwen2.5vl:3b`** (config `llm.vision_model`), in the same
> Ollama. The local-only promise is unchanged; gemma4:e4b remains THE design model and the
> no-model-menu rule stands — the vision model is a companion, never an alternative.
>
> Everything else in this doc (layout, Workshop tokens, states, copy craft) remains the build target.
> The controlling spec (`KimCad-Unified-Product-Spec-v3.0.md`) carries the same corrections.

## Overview

KimCad is a Windows-first desktop app that turns a **plain-English description — or a photo — of a functional part** into a printer-ready file, and optionally sends it to a real printer, through a conversation. The user describes what they want, sees a print-aware 3D preview with real dimensions, refines it by talking and by dragging parameter sliders, passes a Printability Gate, reviews a print report + Smart Mesh readiness score, and either downloads a file or prints directly. **No CAD skills, and the user never edits OpenSCAD.**

This bundle is the **UI/UX design** for that product (spec §5), realized as a working HTML/React prototype. It covers the full end-to-end flow plus the v3.0 additions: first-run wizard, image on-ramp, model picker, Smart Mesh readiness, and direct printer execution.

The controlling product spec is included alongside this README: **`KimCad-Unified-Product-Spec-v3.0.md`**. Where this document references a section like “§5.2”, it points there.

---

## About the Design Files

The files in `prototype/` are a **design reference created in HTML + React (via in-browser Babel) + Three.js** — a prototype showing intended look, layout, and behavior. **They are not production code to copy directly.**

Your task is to **recreate these designs in the target codebase’s environment** using its established patterns and libraries:
- KimCad today is a **local web app** (localhost server, browser UI). A React + TypeScript SPA (Vite) talking to a local backend is the natural target; adapt freely if the codebase already has a stack.
- The 3D preview uses **Three.js** — keep that (or react-three-fiber).
- Treat the prototype’s inline styles/CSS as **design tokens and measurements to extract**, not as a stylesheet to ship. Rebuild with the codebase’s styling system (CSS Modules, Tailwind, styled-components, etc.).
- All the “AI”, slicing, printer I/O, and geometry generation in the prototype is **simulated** (timeouts + canned data). Wire those seams to the real subsystems described in the spec (DesignPlan LLM, deterministic templates, OpenSCAD/CadQuery, OrcaSlicer, PrintProof3D, printer adapters).

## Fidelity

**High-fidelity.** Final colors, typography, spacing, radii, shadows, motion, and interaction states are all specified here and present in the prototype. Recreate the UI pixel-faithfully using the codebase’s libraries. The one deliberately flexible axis is the **theme** — three “design directions” (Workshop / Studio / Daylight) are provided as a token set; pick one as the shipping default (recommended: **Workshop**) or keep all three as a user preference.

---

## Tech in the prototype (and what to replace)

| Prototype uses | In production |
|---|---|
| React 18 via CDN + in-browser Babel | Real React + TS build (Vite/Next) |
| Three.js 0.137 (`KCViewport` class) | Three.js or react-three-fiber — keep the geometry approach |
| `setTimeout` “thinking”, canned replies | Streaming calls to the local DesignPlan model (§6.1) |
| `kcPrintability()` JS heuristic | KimCad gate + **PrintProof3D** validation engine (§6.6, §6.12) |
| `kcSmartMesh()` canned score/history | Smart Mesh: PrintProof3D per-run + local history store (§6.12) |
| `kcEstimate()` volume math | Real OrcaSlicer output (time/filament) (§6.9) |
| `kcOpenSCAD()` returns display text | Deterministic template → OpenSCAD/CadQuery render (§6.3) |
| Photo on-ramp “analyzing” timeout | LOCAL vision model `qwen2.5vl:3b` (§6.10; Stage 9 correction above) |
| Print dialog “sending” timeout | PrintProof3D printer adapters (§6.11) |
| `localStorage` for setup-done flag | App config / settings store (§6.13) |

---

## Global Layout & Chrome

The app is a single full-viewport surface, never page-scrolls; internal panels scroll independently.

**Top bar** (height 58px, `--surface` bg, 1px `--hair` bottom border, 18px side padding):
- **Left:** logo cube (32×32, 9px radius, `--accent` bg, white cube glyph) + wordmark “Kim**Cad**” (`--font-display`, 21px, “Kim” weight 600 `--ink`, “Cad” weight 800 `--accent`).
- **Right (flex, gap 10px):** printer chip → model picker → settings gear → “New design” button.
  - **Printer chip:** pill, `--surface-2` bg, 1px `--hair`, 7×12px pad, 10px radius. Green status dot (7px, with 3px soft ring) + printer name (12.5px/600 `--ink`) + volume in mono 11px `--muted` (e.g. `256×256×256 mm`). Reflects the printer chosen in setup.
  - **Settings gear:** 38×38, 10px radius, `--surface-2`, `--muted` icon → `--accent` on hover. Reopens the first-run wizard (the “settings escape hatch”).
  - **New design:** solid `--ink` bg, `--bg` text, 12.5px/600, 8×15px pad, 10px radius. Resets to the landing/empty state.

**Main workspace** is a 3-column CSS grid: `360px | 1fr | 392px`.
- Responsive: `330 | 1fr | 360` ≤1320px; `300 | 1fr | 330` ≤1140px; stacks vertically ≤1000px.
- **Left (360):** Conversation panel (`--surface`, right 1px `--hair`).
- **Center (1fr):** 3D viewport (`--bg` page, 14px padding around a 16px-radius dark viewport card).
- **Right (392):** scrollable stack of cards (`--bg` column): Parameters → Printability check → (after slice) Smart Mesh → Print report.

---

## Design Tokens

### Color — three “directions” (theme token sets)

Each direction sets the same CSS variables. **Accent** is a separate token (default seeded per direction; 5 accent options offered). Light surfaces wrap a **dark viewport** in every direction — that contrast is the signature (friendly app, precise engineering window).

**Workshop** (recommended default — warm/sand):
```
--bg:#f0ebe0  --surface:#faf6ee  --surface-2:#f4eee2
--ink:#272219  --muted:#6f6857
--hair:rgba(39,34,25,.10)  --hair-strong:rgba(39,34,25,.16)
--viewport-bg:#14171c
--accent:#c8623a   (terracotta)
```
**Studio** (cool/neutral):
```
--bg:#e9ecf1  --surface:#ffffff  --surface-2:#f1f3f7
--ink:#1a1e27  --muted:#5b6473
--hair:rgba(26,30,39,.10)  --hair-strong:rgba(26,30,39,.16)
--viewport-bg:#10131a
--accent:#4b59d6   (indigo)
```
**Daylight** (warm-white/green):
```
--bg:#f4f3ee  --surface:#ffffff  --surface-2:#f3f2ec
--ink:#211f18  --muted:#6b6a60
--hair:rgba(33,31,24,.10)  --hair-strong:rgba(33,31,24,.16)
--viewport-bg:#121611
--accent:#2f9e6a   (green)
```
**Accent options (all directions):** `#c8623a` `#4b59d6` `#2f9e6a` `#b8902a` `#9a4bd6`.

**Semantic status colors** (constant across themes):
- Pass / success: text `#1d7a4e`, fills `color-mix(in srgb,#2f9e6a 15–18%, surface)`
- Warn / caution: text `#876312`, accent `#c9962f`, fills `color-mix(#c9962f 11–22%)`
- Fail / blocked: text `#a8431f`, accent `#c8623a`, fills `color-mix(#c8623a 16–20%)`

Use `color-mix(in srgb, var(--accent) N%, transparent|var(--surface))` heavily for tinted accent backgrounds (chips, selected cards, ring tints).

### Typography
- **Display** (`--font-display`): **Bricolage Grotesque** (default) or **Space Grotesk** (alt). Used for headings, card titles, wordmark, numbers-as-headlines.
- **Body** (`--font-body`): **Hanken Grotesk**.
- **Mono** (`--font-mono`): **JetBrains Mono** — dimensions, parameter values, code, checksums, technical metadata.
- Base font-size scales with density: `font-size: calc(15px * var(--fs))` on the shell.
- Key sizes: hero title `clamp(30px,4.4vw,47px)`/700; wizard H1 32/700; card titles 15–16/600–700; body 13–14; labels/eyebrows 11px/700 uppercase letter-spacing .08–.11em; dimension labels mono 11px/600.
- Use `text-wrap: pretty` on prose.

### Density (token multipliers)
Set `--pad`, `--gap`, `--fs` on `:root`. Cozy `1.18/1.18/1.06` · **Comfortable `1/1/1` (default)** · Compact `.82/.8/.94`. Cards use `padding: calc(15px*var(--pad))`, stacks use `gap: calc(N*var(--gap))`.

### Radius
Cards/viewport **16px**; modals **20px**; buttons **10–13px**; inputs 10–12px; chips/pills **999px**; small toggles 6–9px; avatars/icon-tiles 9px.

### Shadow
- Card rest: `0 1px 3px rgba(0,0,0,.05)` (subtle) — most cards rely on 1px `--hair` borders, not shadow.
- Hero input: `0 18px 50px -22px rgba(0,0,0,.4)`.
- Dropdowns/menus: `0 20px 54px -20px rgba(0,0,0,.42)`.
- Modals: `0 32px 80px -28px rgba(0,0,0,.55)`.
- Toast: `0 14px 34px rgba(0,0,0,.28)`.

### Motion
- Entrance: `kc-fadeup` — translateY(8–10px)→0 over .22–.5s ease. (Keep transform-only or transform+opacity; if you animate opacity, ensure content is visible even if animation is interrupted.)
- Spinners: 11px ring, 2px border, `--accent` top, .7s linear.
- Step/scan pulses: 1.1–1.7s ease-in-out.
- Hover transitions: .12–.18s. Slider/score-ring fills transition .6s ease.
- Auto-rotate the 3D model ~0.0026 rad/frame; pause on drag, resume after 4s idle.

---

(Continued in this file — see “Screens”, “Interactions”, “State”, “Assets”, “Files”.)

---

## Screens / Views

Screenshots are in `screens/` (referenced below). Numbers match the PDF walkthrough.

### 1. First-run wizard (§5.1) — `screens/01–05`
Full-viewport overlay (z 9800), 2-column grid `300px | 1fr`.
- **Left rail** (`--surface-2`, right 1px `--hair`, 26×24px pad): wordmark; vertical **step list** (5 steps, 11×12px pad, 11px radius; active = `--surface` bg + 1px shadow + 600; done = green-check numbered badge; numbers are 23px circles, mono). Bottom: a **time-budget note** card (clock icon + “Most first prints are ready in under 15 minutes — install included.”) and a quiet “Skip setup” text button.
- **Right body** scrolls; content max-width 620px, 52×44px top/side padding; sticky **footer** (Back · progress dots · Continue/Start-designing) with blurred translucent bg.
- **Step 1 — Welcome (`01`):** H1 “Welcome to KimCad” + lede. A card titled “About the SmartScreen warning” explaining the unsigned-beta blue screen, with a **mock of the Windows “Windows protected your PC” dialog** (dark `#1b2733` card: bold white title, muted body, a “More info → **Run anyway**” line where *More info* is a blue underline link and *Run anyway* is an accent pill, a muted “Don’t run” button, and a hint line “1. Click **More info** · 2. Click **Run anyway**”). Below: two trust rows with green checks — “Published from the official GitHub release” and “SHA-256 verified `a3f9 2c71 …`” (checksum in mono). Then a **bundle row**: label “Bundled in one installer — nothing else to download:” + pill chips (App, OpenSCAD, OrcaSlicer, Qwen2.5-Coder, PrintProof3D, CadQuery), each with a green check.
- **Step 2 — Choose a model (`02`):** two radio **model cards** (Qwen2.5-Coder, with a “RECOMMENDED” accent tag, and Gemma 4 E4B) — each shows name (display 16/700), a mono accent tag line (`Fast · Local · 1.5B`), a description, and an 18px radio dot (filled accent when selected; whole card border→accent + 5% accent tint when on). Below, a collapsed dashed **“Add an OpenRouter key (optional)”** toggle that expands to a labeled password input with the note “Used only when you opt into a cloud model or photo analysis. Never required to run KimCad.”
- **Step 3 — Pick your printer (`03`):** 5-up **maker grid** (Bambu Lab, Creality, Prusa, Elegoo, Anycubic) — each a tile with printer icon + name (selected = accent border/tint, accent icon). Below, a **model list** of radio rows for the selected maker: name (14/600) left, build volume in mono `--muted` right (e.g. `Prusa MK4 … 250×210×220 mm`).
- **Step 4 — Connect (optional) (`04`):** lede names the chosen printer. Two big radio options: “Just download files” (download icon) vs “Connect this printer” (plug icon, shows the connection label). Selecting connect reveals a **form** whose fields adapt to the maker’s protocol (Bambu → IP + Access code; OctoPrint/Moonraker → URL + API key; PrusaLink → IP + Password), an amber **note** explaining the protocol caveat (e.g. Bambu Developer Mode disables cloud), and a **“Test connection”** button that turns into a green “Connected — <printer> is idle”. Skippable.
- **Step 5 — Ready (`05`):** centered green check badge, “You’re all set”, and a **recap card** (Model / Printer / Direct print rows). “Start designing” dismisses the wizard, persists setup, and applies the chosen model + printer to the app.

### 2. Landing / empty state (§5.2) — `screens/06`
Centered hero (max-width 680). Pill badge (green dot + “Ready to print in ~15 minutes · no CAD skills”); display title (“What do you want to make today?” — copy varies by AI-tone token); muted sub. A large **input card** (`--surface`, 1.5px border→accent on focus, 18px radius, big shadow): multiline textarea + accent “Design it →” button (disabled until non-empty). A **“Try:” example row** of pill buttons (4 canned prompts). A divider row with the **photo on-ramp affordance**: “Have a broken or existing part? **Start from a photo**” (camera icon, accent link) flanked by hairlines. Absolute-bottom **3-step footer**: “1. Describe — 2. Preview & refine — 3. Check & download” (numbers in accent mono).

### 3. Image on-ramp → DesignPlan confirm (§5.3, §6.10) — `screens/07`
Centered modal (max-width 480, 20px radius). Three internal stages:
- **Upload:** explanatory sub; a dashed **dropzone** (click/drag, upload icon) with “Drop a photo or **browse**”; a “**Try with a sample part**” secondary button; an amber **disclosure**: “Default analysis runs on a free OpenRouter vision model — your photo leaves the device. Switch to **Gemma 4 E4B** to analyze locally & offline.”
- **Analyzing:** a 200×150 dark photo frame (the dropped image or a “sample-part.jpg” placeholder) with an animated **scanline** sweeping top→bottom (accent gradient), and “⟳ Estimating geometry & dimensions…”.
- **Plan (shown in `07`):** an editable **DesignPlan draft**. Small photo thumb + “DETECTED · DESIGNPLAN DRAFT” eyebrow + detected object type (display 18/700) + a target-icon line “86% match · confirm before building”. A **fields list**: each row is a label + value (mono) + a **confidence pill** (HIGH/MEDIUM/LOW, color-coded); the low-confidence “Mounting holes” field is *editable* via an M3/M4/M5 segmented control. An amber note (“Arm appears snapped near the base — KimCad will rebuild it solid.”). Actions: “Use a different photo” (ghost) + “Build this part →” (primary). Confirming feeds the seed into the normal pipeline (skips the text clarify).

### 4. Clarifying question (§5.2) — `screens/08`
In the conversation panel. AI bubble with `clarify` styling (accent-tinted bg, accent-tinted border) preceded by a short intro bubble, followed by **quick-reply chips** (e.g. M3 / M4 / M5) rendered as accent-outline pills that fill accent on hover. Max **one** open question per plan.

### 5. Workspace — conversation + print-aware preview + controls (§5.2, §5.4) — `screens/09`
- **Left — Conversation:** “CONVERSATION” eyebrow header; scrolling message list. **AI messages**: 28px accent avatar (cube glyph) + bubble (`--surface-2`, 1px hair, top-left corner squared to 5px). **User messages**: right-aligned accent bubble, white text, top-right squared. A **thinking** state renders a 4-row checklist (“Reading request → Design plan → Generating geometry → Checking printability”) with per-row spinner→check. **Composer** (bottom, sticky): a **refine chip row** (“Make it wider”, “Thicker walls”, “Make it taller”, “Add a hook”), an optional **click-point chip** (mono `x · y · z` with clear ×), a textarea + accent send button.
- **Center — Viewport:** dark 16px-radius card holding a **Three.js** scene: the parametric part rendered as an accent **wireframe** (blueprint style; also Solid and Hologram render modes), a faint **build-plate grid** (printer-sized) with a plate border, a translucent **bounding box** with live **X/Y/Z dimension labels** (mono, dark glass pills anchored to box edges, projected to screen each frame), drag-orbit + scroll-zoom + auto-rotate. **Overlays:** top-left “Add point” toggle (enables click-to-point raycast; places a marker + emits coords to the composer) and a help hint (“drag to rotate · scroll to zoom”); a **“Auto-oriented · plate-down · change”** chip (top-left, dark glass); when picking, an accent “Click a spot…” banner; bottom **version rail** (dark glass, “HISTORY” + node chips `v1 Initial design`, `v2 …`, click to restore).
- **Right — Parameters card:** title “Parameters” + a “Show code / Hide code” mono toggle. Sub: “Drag a slider — the model re-renders instantly, no AI round-trip.” Then **slider rows**: label (+ optional axis tag like `X`/`Z` in a mono chip) and value (mono, with unit). The range track is an accent-filled gradient up to `--pct`, thumb 17px white with 2px accent ring. Dragging re-renders the 3D in <1s with no LLM call (§4.2). “Show code” reveals a dark mono **OpenSCAD** block (read-only, display-only).

### 6. Printability Gate (§6.6) — bottom of `screens/09`
Card titled “Printability check” with a verdict badge (Ready / N notes / Blocked, color-coded). A **Material** segmented control (PLA/PETG/TPU/ABS). A list of **check rows**: each a 19px status icon tile (pass/warn/fail colored) + label (14/600) + detail (`--muted` 11.5px). Checks (reactive to params/printer): dimensions-match, fits-build-volume (uses the selected printer’s volume), wall-thickness-vs-nozzle, supports/overhang, hole-tolerance, bed-contact. A full-width accent **“Slice & prepare file”** button (disabled if any fail; shows a spinner “Slicing on <printer>…” while working). The whole gate is the seam for the **PrintProof3D** engine (§6.12).

### 7. Smart Mesh readiness + Print report (§5.5, §6.12) — `screens/10`
Appear after slicing.
- **Smart Mesh card** (accent-tinted gradient bg): title “Smart Mesh readiness” + confidence badge. Top row: a **score ring** (68px SVG donut, 0–100, colored by band — pass/warn/fail, animated fill) + a verdict band (“Ready to print”, display 18/700, colored) + a **historical comparison** line (history icon + “Top 13% of 14 similar wall-mounted spool holders · 93% printed clean”). **Risks** section (warn/fail checks → label + suggested fix). **Recommendations** list (green-check bullets). Footer: “Learned from your local print history · PrintProof3D validation engine.”
- **Print report card** (accent-tinted border): title + confidence badge. **Rows** (label left, mono value right with sub-hints): Dimensions (`70 × 49 × 150 mm`, “fits <printer>”), Material (`PLA · 0.2 mm layer · 20% infill`), Estimated print (`1 h 45 m`, “33 g filament”), Supports (“Under arm only”). An amber warning row if any gate notes. **Export row**: primary “Download .3MF”, ghost “STEP” (CadQuery), ghost “G-code” (locked to printer). Note: “3MF is printer-agnostic & safe to share · STEP for CAD editing · G-code locks to <printer>.” Then a full-width **“Send to <printer>”** accent-outline button (turns green “Printing on <printer> →” after a job starts).

### 8. Direct print dialog (§5.6, §6.11) — `screens/11`
Centered modal. A dark **live-status panel**: printer name + green dot + state pill (“Idle · ready”); a 2×2 grid (Nozzle/Bed temps, Plate free, AMS material) in mono; a connection line “LAN · Developer Mode · KimCad never auto-starts a print”. Then **confirm rows** (Geometry / Printer / Material / Estimated). A full-width **“Confirm & start print”** + note “One final confirmation before any command leaves the app.” On confirm: a “Uploading & starting job…” spinner, then a **“Print started”** success state (green check badge, a thin progress bar at ~4%, “Layer 1 / ~N · monitoring live”, Done button). KimCad **never auto-starts** — the explicit final click is required.

---

## Interactions & Behavior

- **App state machine:** `landing → (text submit OR photo build) → clarify (text path only) → generating → workspace`. Slicing reveals Smart Mesh + report. “New design” resets to landing; the gear reopens the wizard.
- **Generating sequence:** a staged checklist (~0.7s/step) gates the first model appearance; refinements show a shorter pass.
- **Conversational refinement:** free-text or refine-chips map to parameter changes (wider → +plate width; thicker → wall ≥4.4mm; taller → +height; hook/arm → +arm length; fillet → +fillet) and push a version node. Each change re-runs the gate and clears the sliced state.
- **Sliders:** instant local re-render (<1s, no LLM). Clears sliced state.
- **Click-to-point:** toggle “Add point” → cursor crosshair → click raycasts the mesh → marker + coord chip in composer → next message (“add a hole here”) consumes the point and adds a feature at that location, pushing a version.
- **Version history:** linear stack; clicking a node restores its params/holes.
- **Printability is reactive:** e.g. wall < 3mm ⇒ a “Thin wall” warn appears; bbox > printer volume ⇒ a “Exceeds build volume” fail that disables slicing. Smart Mesh score recomputes from the gate + material.
- **Material change** recomputes estimate and Smart Mesh.
- **No dead ends (§5.7):** every error/empty state must offer a concrete next action (retry / regenerate / edit / switch model / try experimental generator / proceed-anyway). The prototype shows the happy path; preserve this principle.
- **Safety:** G-code export and any print start require explicit confirmation; default export is 3MF; localhost-only posture (§12).
- **Accessibility floor (§4.2):** full keyboard nav, WCAG 2.1 AA contrast, legible at 100% zoom, hit targets ≥44px. Build these in (the prototype is mouse-first).

---

## State Management

Core app state (see `prototype/jsx/app.jsx`):
- `phase` (`landing`|`workspace`), `messages[]`, `params{}` (the 7 template parameters), `holes[]` (click-placed), `material`, `versions[]` + `activeVersion`.
- `thinking` + `thinkingStep`, `builtOnce`, `sliced` + `slicing`.
- `pointChip` + `pickMode` (click-to-point), `showCode`.
- v3.0: `model` (`qwen`|`gemma`|`cloud`), `printer{name,volume,nozzle,conn}`, `photoOpen`, `printOpen`, `printed`, `fromPhoto`, `firstRun` (persisted via `kc_setup_v3`).
- Derived (memoized): `gate = kcPrintability(params, holes, printer)`, `smartMesh = kcSmartMesh(params, gate, material)`, `scadText = kcOpenSCAD(params, holes)`.

**Data contracts to implement** map cleanly onto the spec: the **DesignPlan IR** (§6.2) replaces `params` as the source of truth; `kcPrintability` → KimCad gate + PrintProof3D report (status/issues/severity/suggested-fixes/confidence, §6.6/§6.12); `kcSmartMesh` → readiness from PrintProof3D + a local run/print-history store (§6.12).

---

## Tweaks panel (design-exploration tool — not a shipping feature)

The prototype includes a “Tweaks” panel (toggle in the toolbar) to explore **design direction, accent, type pairing, density, preview render style, and AI tone**. This is a *design tool* for choosing the shipping look — not a product feature to build. Use it to pick defaults; the recommended baseline is Workshop direction / terracotta accent / Bricolage / Comfortable / Blueprint render / Friendly tone.

---

## Assets

- **Fonts (Google Fonts):** Bricolage Grotesque, Hanken Grotesk, Space Grotesk, JetBrains Mono. Self-host in production.
- **Icons:** a small inline-SVG set (`KCIcon` in `prototype/jsx/panels.jsx`), 24×24 stroke icons (cube, sliders, layers, printer, camera, upload, pin, ruler, check, warn, history, target, gear, plug, key, shield, clock, etc.). Replace with the codebase’s icon library (e.g. Lucide) — names map closely.
- **3D:** geometry is generated at runtime in `prototype/jsx/preview.jsx` (`KCViewport`). No mesh assets. The cube logo glyph is an inline SVG (origin: this design).
- **Imagery:** none shipped; the photo on-ramp uses the user’s upload or a labeled placeholder. No external/brand images.
- **No third-party brand assets** are used. Printer-maker names are referenced as text only.

---

## Files (in `prototype/`)

- `KimCad.html` — entry; loads fonts, React/Babel/Three CDNs, and the jsx modules; mounts `<KimCadApp/>`.
- `jsx/data.jsx` — **design tokens** (directions, fonts, density, accents), demo content, and the simulated engine: `kcBBox`, `kcEstimate`, `kcPrintability`, `kcSmartMesh`, `kcOpenSCAD`; model defs, printer profiles + connection info, bundle list, photo DesignPlan, printer status. **Start here for tokens & contracts.**
- `jsx/styles.jsx` — the full CSS (`KC_CSS`), token-driven; the source of truth for exact measurements/states.
- `jsx/preview.jsx` — `KCViewport` Three.js controller (geometry build, bbox + projected labels, orbit/zoom, click-to-point raycast, render modes) + the `Preview` React wrapper.
- `jsx/panels.jsx` — `KCIcon`, `ChatPanel`, `ParamPanel`, `PrintabilityCard`, `ReportCard`, `VersionRail`.
- `jsx/advanced.jsx` — `ModelPicker`, `PhotoOnramp` (+ DesignPlan confirm), `SmartMeshCard` (+ `ScoreRing`), `PrintDialog`.
- `jsx/wizard.jsx` — `FirstRunWizard` (5 steps).
- `jsx/app.jsx` — `KimCadApp` orchestrator (state machine, layout, Topbar, Landing, generating sequence, Tweaks wiring).
- `jsx/tweaks-panel.jsx` — design-exploration panel shell (not a product feature).

To run the reference: open `prototype/KimCad.html` in a browser (needs internet for the CDN libraries + fonts).

The controlling spec is `../KimCad-Unified-Product-Spec-v3.0.md`. A visual walkthrough is `../KimCad-Walkthrough.html` (open and print to PDF) and the same screens are in `screens/`.

---

## Addendum — Stage 8.5 usability (2026-06-03): finishing the deferred design intent

A code-grounded review of the *shipped* SPA (2026-06-03) found the core loop works but much of the
product around it — including several surfaces **already designed in this prototype** — was deferred
during the build, leaving deal-killer gaps (no persistence; no in-workspace refinement; no settings;
mm-only; problems shown as text, not on the model; no progress on long runs). **Stage 8.5 builds
these now**, before the CadQuery backend. What/why: `../KimCad-Unified-Product-Spec-v3.0.md`
Addendum B + `../stage-8.5-usability-plan.md`.

**Build to THIS prototype where it already exists** (high-fidelity design source — recreate it
faithfully in the React/TS SPA):
- **`panels.jsx` → `VersionRail`** — the version history / timeline for Stage 8.5 Slice 2 (iterative
  refinement). The SPA today has no version rail; build it from here.
- **`wizard.jsx` → `FirstRunWizard` (5 steps)** — Slice 7 onboarding / first-run (detect Ollama,
  pull the model, pick a printer). Designed here, never built.
- **`advanced.jsx` → `ModelPicker`** — Slice 5 model selection inside the new Settings surface.
- **`preview.jsx` → `KCViewport` click-to-point raycast + render modes** — the basis for Slice 6
  (click a risk → focus that region on the model; highlight problem faces).
- `ChatPanel` / `ParamPanel` (`panels.jsx`) — the in-workspace **refine-by-talking** input + numeric
  param entry (Slices 2–3) follow these.

**New surfaces this prototype did NOT cover** (design fresh, in the prototype's token system +
Workshop theme; note them back here as built):
- A **"My Designs" library + local persistence** (Slice 1) — the prototype assumed a single live
  session; the product needs saved designs, reopen, auto-save/restore, and a real per-design URL.
- A **full Settings screen** (Slice 5) beyond the model picker — printer/material defaults, units,
  optional-engine (CadQuery / PrintProof3D) enable + install status.
- **Units (mm/inch)** (Slice 4) across every dimension surface.
- **On-model problem highlighting** (Slice 6) — coloring overhang/adhesion faces, beyond the
  prototype's click-to-point.

Each slice's rendered (desktop + mobile) audit-lite is the fidelity check against this design.
