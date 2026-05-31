# KimCad — Unified Product Specification

**AI-Assisted Parametric Design and Print Execution for Functional 3D Prints**
(working name "KimCad"; formerly "PrintForge" / "AI-Driven Text-to-3D-Print Pipeline")

**Version 3.0 — 2026-05-31** · Scott Converse, Architecture & Product Direction
Open-source, non-commercial · **Windows-first** (macOS/Linux beta later, non-blocking)
Reference hardware: Beelink mini-PC — AMD Ryzen AI 9 HX 370, Radeon 890M, XDNA2 NPU, 32 GB

> **Status:** This is the controlling specification. It supersedes v2.1. It carries forward everything still true from v2.1 and folds in the product-direction decisions made 2026-05-31. The concrete visual/interaction design referenced in §5 will be regenerated from *this* document; until then §5 states UX requirements and acceptance criteria, not pixel-level design.
>
> **Canonical package (ground-up complete).** This document is the *direction, decisions, and acceptance* layer. The concrete buildable layer — schemas, contracts, prompts, the API surface, the PrintProof3D integration contract, the build/installer recipe, and the genuinely-new pieces (Smart Mesh data model + readiness score, image-provider interface, printer-adapter config) — lives in the companion **`KimCad-Build-Spec-v3.0.md`**. Together with **`DECISION-LOG-v3.md`** these three files in `docs/spec/` are the complete, self-contained spec: a fresh builder handed only this folder can build the product from the ground up. (The build spec's contracts are extracted from the current code and marked where the v3.0 TARGET differs from what exists today.)

---

## 0. About this document

v3.0 is the synthesis of the v2.1 unified spec and the 2026-05-31 product-direction working session. v2.1's architectural bet (deterministic CSG geometry, local-first, UX-as-gate) was right and is preserved. v3.0 changes scope in three deliberate ways the older spec deferred or excluded: **image input, real printer execution, and a learning layer are now core**, not optional. It also records, for the first time, decisions that were made in code without a written trail (notably the deterministic-template architecture) and names the specific open-source components to be used so guidance cannot evaporate again. The full audit trail is in `docs/spec/DECISION-LOG-v3.md`.

Load-bearing facts (model availability, pricing, library status, market data) were verified 2026-05-31. They move weekly; re-verify §7 and any named library/model before committing it, and again at the start of each stage (the standing "verify-before-rely" rule, §7.5).

### What changed from v2.1 → v3.0

| Area | v2.1 | v3.0 | Why |
|---|---|---|---|
| Platform | Windows/macOS/Linux, equal | **Windows-first** for beta and final; mac/Linux beta alongside, never blocking | Windows is the overwhelming bulk of the audience; don't spend cycles finalizing other OSes before a Windows release |
| Core CAD engine | "an LLM writes parametric OpenSCAD" | **Deterministic templates generate CAD; the user never edits OpenSCAD.** LLM emits a validated DesignPlan only | Reliability/latency: the local model can't free-form correct OpenSCAD at conversational speed. Ratifies what the code already does |
| Out-of-template requests | Hard reject ("unsupported") | **Tiered fallback** — no hard reject; offer the experimental LLM-OpenSCAD generator (Tier 2 local, Tier 3 cloud) | The product must never dead-end; the sandbox for untrusted OpenSCAD already exists |
| Template breadth | 5 seed → 20+ | **Library-agnostic, multi-library** (BOSL2 + others), dozens of families, composable | 10 is a seed, not a ceiling; the library is the quality moat |
| Image-to-3D | Experimental, optional, Phase 5, "never blocks" | **Required but strictly opt-in** — a photo→DesignPlan on-ramp exposed only when the user chooses it; never on the required path | Major capacity gap (broken part / found part / sketch → printable); image output is untrusted data into the validated DesignPlan — same trust boundary, new input |
| Printer execution | Out of scope for v1 (file output only) | **Core for beta** — discover, status, upload, start, monitor, capture outcome; every start user-confirmed | The product should close the loop to a real printer |
| Smart Mesh / learning | Absent | **Core pillar** — readiness score, risks, recommendations, confidence, historical comparison; learns from run/print history | Turns accumulated print outcomes into better up-front guidance |
| CadQuery | Deferred (exec() risk) | **Adopted as a parallel deterministic backend** behind a renderer interface; OpenSCAD stays the default/fallback | Native STEP/3MF + real fillets + render-free geometry tests; exec() risk doesn't apply — these templates are KimCad-authored, not LLM-generated |
| Local model | "8–9B coder, e.g. Qwen3 8B" | **Qwen2.5-Coder 1.5B** fast default + **Gemma 4 E4B** as the proven, one-click non-China alternative (and local vision fallback); schema-constrained output | The ~80s draft is bandwidth-bound 6.7B generation; a small model + constrained decoding gets to ~15–20s |
| Cloud access | DeepSeek V4 Flash default + OpenRouter escape hatch | **OpenRouter as the cloud router** (pick/swap any model, incl. free vision models); local always works | Don't hardwire one vendor; cloud is an accelerant, never a requirement |
| Code signing | Phase 4 polish (SmartScreen/Gatekeeper) | **No signing cert for beta** — unsigned + explicit SmartScreen warning explained in the install walkthrough + GitHub provenance + SHA-256 checksums | No cert; the warning is acceptable and the walkthrough prepares the user |
| Own-code license | "MIT or Apache, confirm with counsel" | **Apache-2.0** | Patent grant + clear notice terms; owner is fine with permissive reuse |
| Stage 6 | (n/a) | **Reclassified as a packaged Windows local-CAD release candidate — NOT the beta** | Beta requires real printer execution + Smart Mesh + image input |
| Real-hardware test | Implied release gate | **Removed as a release gate** — validated at simulator/conformance altitude; real-hardware proof is a post-release community/Kim program | The owner has no printers; Kim and volunteer printer-owners validate post-release, feeding Smart Mesh |

---

## 1. Executive Summary

KimCad is an open-source Windows-first application that turns a plain-English description — or a photo — of a functional or mechanical object into a printer-ready file and, optionally, sends it to a real printer, through a conversation. You describe (or photograph) what you want, see a 3D preview with real dimensions, refine it by talking and by dragging parameter sliders, pass a printability check, and either download a sliced file or print it directly. No CAD skills required, and you never edit OpenSCAD.

The engine is deterministic where it counts: a local model emits a **validated DesignPlan (JSON)**; **deterministic templates** turn that plan into CAD (OpenSCAD today, CadQuery as a parallel backend) so geometry is manifold and dimensionally meaningful by construction; a validation-and-printability pipeline checks it against your printer and material; an open-source slicer produces the output; and a **Smart Mesh** layer scores print-readiness from the geometry, the profiles, the slicer output, and accumulated history. The whole core path runs locally on a CPU/iGPU with no discrete NVIDIA GPU. **Cloud is always an accelerant, never a requirement** (§1.2).

Image input (photo → rough geometry → DesignPlan seed) and real printer execution are first-class but **opt-in**: image input appears only when the user chooses it, and a print is sent only after explicit confirmation. Neither blocks or replaces the local, file-output core.

### 1.1 Design philosophy (priority order — non-negotiable hard gate)

**User experience is the most important thing.** Every decision — what to build, how, and when it is "done" — starts from what the user sees, feels, and experiences. Code serves the interface, not the reverse. (The owner's standard: without a great, easy-to-use UI/UX, the product is trash in the marketplace of ideas. UI/UX is a first-class workstream and a primary acceptance gate in **every** stage — never late-stage polish.)

**Documentation and QA/Testing are second.** Docs are how users understand what was built; tests prove it works. Both are deliverables. A feature without docs and tests is not a feature.

**Writing code is a supporting function.** UX wins over code elegance; doc completeness wins over shipping speed; test coverage wins over feature count. When trade-offs collide, UX wins. Never declare work done without verifying the user experience.

### 1.2 Key constraints

- **Non-commercial, open-source.** KimCad's own code is **Apache-2.0**. Bundled/used third-party components may be copyleft (GPL/AGPL/LGPL) **provided their license permits free distribution and free use by commercial entities** — that is the filter. Components that forbid free commercial use (e.g. pymeshfix/MeshFix, ManifoldPlus — non-commercial only) are excluded. Optional experimental adapters and any non-commercial/RAIL-restricted model weights are fenced from the core, clearly labeled, and never required to run the product.
- **Windows-first.** Beta and final target Windows. macOS/Linux betas may ship alongside but must not block or gate the Windows release.
- **Local-first, no discrete NVIDIA GPU required for the core path** (reference: Ryzen AI 9 HX 370 / Radeon 890M / 32 GB).
- **Local always works — no hard cloud dependency.** Every cloud-accelerated feature degrades to a local fallback. Cloud cannot mask failure of the local path.
- **Installs as one thing.** A single all-in-one Windows installer bundles everything the core path needs (CAD engine, slicer, LLM runtime, validation harness, app). No separate hunt for OpenSCAD or a slicer.
- **No code-signing certificate for beta.** Beta ships unsigned with an explicit SmartScreen warning explained in the install walkthrough, official GitHub release provenance, and published SHA-256 checksums.
- **Single-person direction augmented by AI coding agents.** LLM backend is provider-agnostic (local + cloud via OpenRouter, behind one OpenAI-compatible interface).

---

## 2. Positioning & Scope

KimCad is a **"make me a functional, printable part — and print it"** tool. It is not a "turn arbitrary images into art meshes" tool. The functional-part workflow plays to deterministic CAD's strengths; everything serves that promise.

**In scope (the product):**
- Text → validated DesignPlan → deterministic CAD → validated, printable, sliced file, refined conversationally.
- **Photo → rough geometry → DesignPlan seed** (opt-in on-ramp; §6.10). The image bootstraps approximate dimensions/features into the DesignPlan; the user confirms and refines. The delivered geometry is KimCad's own deterministic output, not the raw image-mesh.
- **Real printer execution** (opt-in; §6.11): discover, query status, upload, user-confirmed start, monitor, capture outcome.
- **Smart Mesh** readiness and learning (§6.12).
- **CadQuery** as a parallel deterministic CAD backend (§6.3), behind the same DesignPlan→template interface as OpenSCAD.

**Explicitly out of scope (non-goals):**
- Text → image → image-to-3D as the *primary* path. The image on-ramp is a seed for the deterministic pipeline, not a route to ship raw neural meshes.
- Exposing KimCad as an MCP **server** for external agent control — designed-for but **post-beta** (§6.11).
- Selling KimCad, or any feature that requires payment to run the core path.

---

## 3. Product Architecture

### 3.1 The pipeline

```
[opt-in] Photo ─► vision-LLM / image-mesh ─► measured seed ─┐
                                                            ▼
User prompt ─► [1] Clarify (one question if a critical dim is missing)
            ─► [2] DesignPlan (JSON IR)  ◄─ printer + material + build-volume constraints
            ─► [3] CAD generation
                   Tier 1: deterministic template  (OpenSCAD or CadQuery backend)
                   Tier 2: local LLM-OpenSCAD       (experimental, offered, not default)
                   Tier 3: cloud LLM-OpenSCAD via OpenRouter (opt-in, hard cases)
            ─► [4] Render → mesh        (subprocess, sandboxed, timeout, retry-once)
            ─► [5] Mesh validation      (Trimesh; manifold booleans via manifold3d backend)
            ─► [6] PRINTABILITY GATE     (KimCad gate + PrintProof3D validation engine)
            ─► [7] Auto-orientation      (largest stable facet → Z=0)
            ─► [8] Slicer (OrcaSlicer CLI)  — only after explicit printer/material confirmation
            ─► [9] Print report + SMART MESH readiness (score, risks, recs, confidence, history)
            ─► [10] [opt-in] Printer execution  — user-confirmed start, monitor, capture outcome
```

Steps 1, 2, 6, and 9 remain where "printable" stops meaning "a file exists." Steps marked opt-in (photo on-ramp, Tier 3 cloud, printer execution) never sit on the required local path.

### 3.2 Boundaries
- The local model is untrusted until DesignPlan schema validation passes.
- Generated CAD source is untrusted and runs sandboxed (§6.4, §12). Deterministic templates are KimCad-authored, trusted code.
- Image-mesh / vision-LLM output is untrusted data that flows into the validated DesignPlan — same trust boundary as text, new input channel.
- OpenSCAD, OrcaSlicer, and PrintProof3D are external binaries invoked at arm's length (subprocess / local service), never linked into the KimCad process.
- The app binds localhost only by default. A print start, a cloud call, and any network/printer contact are explicit, user-initiated actions.

---

## 4. Definition of Done (the UX gate)

"Done" is defined by the user experience, not by the existence of an output file. A feature is not done until all of the following are true. This governs every stage.

- **It does what the user asked, dimensionally.** Bounding box matches stated dimensions within tolerance, asserted and surfaced (§6.6).
- **It is printable, not merely sliceable.** Passes the Printability Gate for the selected printer/material, or the user explicitly chose "proceed anyway" after seeing warnings.
- **It is documented** (user-facing behavior in docs; change in changelog).
- **It is tested, including the print-quality dimension** (unit/integration green; relevant benchmark prompts score acceptably).
- **It is usable.** Meets the §4.2 usability acceptance criteria for the current stage. Usability is a gate, not a nice-to-have.

### 4.1 The benchmark harness is the done-gate
Ten canonical functional prompts (Appendix B), each scored automatically on three axes — **slices-clean**, **matches-request** (bounding box/volume within tolerance via `math.isclose` on Trimesh properties), **correct-dimensions** (explicit features measure correctly). Doubles as the model A/B harness (scores models/prompt revisions on output geometry, not on grading source). Grows to 50+.

### 4.2 Usability acceptance criteria (hard requirement, measured)
- **Time-to-first-result (cold start):** a first-time user on a clean Windows machine reaches a downloaded, sliced file in ≤ 15 minutes, including install, using only the in-app wizard.
- **First-run completion:** ≥ 90% of test users finish the first-run wizard without outside help.
- **Unaided task success:** on the 10 benchmark prompts, a first-time user reaches a dimensionally-correct, sliceable preview without touching CAD code in ≥ 8/10.
- **Slider latency:** a parameter-slider change re-renders in < 1 s (local, no LLM round-trip). *(Today the UI exposes number inputs, not sliders — closing this is a named deliverable.)*
- **Loop responsiveness:** any operation over 1 s shows progress; the UI never fully blocks.
- **No dead ends:** every error/empty state presents at least one concrete next action (retry / regenerate / edit / switch provider / try experimental generator / proceed-anyway).
- **Discoverability:** the core actions — describe, manipulate the preview, slice, download/print — are visible without scrolling; advanced controls (code toggle, version tree, click-to-point, image on-ramp, printer execution) are discoverable but off the primary path.
- **Accessibility floor:** full keyboard navigation, WCAG 2.1 AA contrast, legible at 100% zoom.
- **Test protocol:** moderated think-aloud usability test with 5 representative makers at every UI-bearing stage gate. A stage does not pass its Definition of Done until thresholds are met or a deviation is explicitly accepted in writing.

### 4.3 Beta vs Final acceptance
**Beta (Windows) requires, all at simulator/code-complete altitude — real-hardware proof is NOT a beta gate:**
- Local model mandatory; faster default + non-China alternative, both benchmark-validated.
- Deterministic DesignPlan→CAD for every supported benchmark family; tiered LLM-OpenSCAD fallback present.
- Image-to-3D opt-in on-ramp present (cloud default, local fallback), never on the core path.
- Smart Mesh v1 (readiness + learning store + report) present.
- Real printer execution present via the PrintProof3D adapter spine, **simulator/conformance-validated**, every start user-confirmed.
- Full main flow with no command line; sliders + live preview; print-aware preview; print report.
- Windows installer with dependency checks; unsigned + SmartScreen-warning walkthrough; GitHub provenance; SHA-256 checksums.
- Docs, changelog, tests, benchmark evidence.

**Final adds (breadth + real-world validation):**
- Top-5 printer-maker profiles validated; expanded template library (dozens of families).
- Post-release **real-hardware validation** by Kim and volunteer printer-owners; outcomes ingested by Smart Mesh.
- Hardened Bambu execution (TLS + access code + job control); broader firmware coverage proven against real devices where available.
- Optional macOS/Linux betas; optional KimCad-as-MCP-server; optional cloud image-mesh providers beyond the default.

---

## 5. User Experience Specification

UX is the top priority. This section defines requirements and acceptance; the concrete visual/interaction design will be regenerated from this v3.0 document.

### 5.1 First run & installation
One bundled Windows installer (OpenSCAD + OrcaSlicer + local LLM runtime + PrintProof3D + app). The user installs one thing; binary paths are pre-wired with a settings escape hatch. The first-run walkthrough: shows and explains the **unsigned-app / SmartScreen warning and exactly what to click**; chooses the local model (fast default vs the non-China alternative) and offers an optional cloud key (via OpenRouter); picks a default printer profile from the bundled top-5 set; and optionally configures a printer for direct execution. The cold-start path is held to the §4.2 time-to-first-result budget.

### 5.2 Core interaction loop
Conversational + direct-manipulation, both first-class:
- **Conversational refinement** — "make it wider," "thicken to 5 mm," "tilt 10°." Each turn re-plans, regenerates, re-renders, re-validates.
- **Clarification** — when a critical dimension is missing, ask one question rather than guess (max one open question per plan).
- **Parameter sliders (major UX win, currently missing).** Template parameters are exposed as **sliders with live preview**; dragging re-runs generation locally and re-renders in < 1 s with no LLM call. This replaces today's number-input-only controls.
- **Click-to-point spatial referencing** — a click in the Three.js preview injects coordinates into the next prompt ("add an M3 hole at x=12, y=40").
- **Undo / version stack** — every refinement is a node in a linear (floor) or branching (better) history.
- **Model picker** — the user can switch the active model (fast default ↔ non-China alternative ↔ cloud via OpenRouter) without editing config.

### 5.3 The image on-ramp (opt-in)
A grayed/secondary "use a photo" affordance, surfaced only when the user chooses it. Flow: upload photo → the system estimates approximate dimensions/features → **pre-fills the DesignPlan** → the user confirms/corrects → the normal deterministic pipeline takes over. Defaults to the free cloud vision path; falls back to a local vision-capable model offline. Photo upload to any cloud provider is explicitly disclosed and consented. The image never produces the delivered geometry directly.

### 5.4 The preview is print-aware
Bounding-box overlay with live X/Y/Z dimensions; the build plate for the selected printer; post-auto-orient orientation and where supports would be needed; inline Printability Gate warnings.

### 5.5 Output is a validated print job + readiness, not just a file
On slice, the user gets the file, a **print report** (dimensions, est. time/filament, profile, bed-fit, warnings, confidence), and the **Smart Mesh readiness** summary (score, risks, recommendations, confidence, comparison to similar past prints). Safe default export is a 3MF project; G-code is generated only after explicit printer/profile/material confirmation (§5.6).

### 5.6 Direct print (opt-in) and the model/printer-file separation
G-code is printer-specific and risky. The default export stays a printer-agnostic 3MF. Direct printer execution is a separate, explicit action: pick the configured printer, see its live status (idle? build volume? temps?), confirm geometry/printer/material/profile, then **start** — with one final user confirmation before any command leaves the app. KimCad never auto-starts a print.

### 5.7 Error handling & failure taxonomy
Every error/empty/loading/partial state presents a concrete next action. No hard rejects: an out-of-template request offers the experimental LLM-OpenSCAD generator with a clear "may not be perfect" warning; a failed cloud call falls back to local; a printer that won't connect explains why (e.g. Bambu Developer Mode + access code) and how to fix it.

---

## 6. Technical Implementation

### 6.1 LLM integration layer
One module wraps all model communication via the OpenAI-compatible chat-completions format — local runtimes (Ollama, LM Studio) and cloud (via **OpenRouter** as the universal router) all speak it. Two core functions: `generate_design_plan(prompt, history, constraints) → DesignPlan(JSON)` and the optional `generate_openscad(design_plan, history, config) → str` (the Tier 2/3 fallback only). Use **schema-constrained output** (Ollama `format: <DesignPlan JSON schema>`, or `response_format` json_schema on the OpenAI-compatible path), `temperature 0`, a `num_predict` cap (~768), small `num_ctx`, and `keep_alive` to make DesignPlan JSON essentially always valid and fast.

### 6.2 The Design-Plan IR
Before any geometry, the model emits a JSON plan: `object_type`, `dimensions{}`, `features[]`, `tolerances{}`, `printer`, `material`, `assumptions[]`, `open_questions[]` (max 1). Validated for intent before generation; drives clarification; makes refinement auditable. CAD is generated from the plan, never from prose.

### 6.3 CAD generation — deterministic templates, tiered fallback, multi-library, two backends
- **Tier 1 (default): deterministic templates.** KimCad-authored parametric templates turn a DesignPlan into CAD. The user never edits CAD. This is the reliability/latency/security play and the quality moat.
- **Backends behind one `render(plan) → artifact` interface:**
  - **OpenSCAD** (default) — manifold-by-construction, sandboxed subprocess, the safe path.
  - **CadQuery** (parallel) — Python/OCCT, native STEP + 3MF, real B-rep fillets/chamfers, render-free pytest geometry assertions. Adopted for families that benefit (brackets, enclosures, heat-set bosses). **The v2.1 exec()-risk objection does not apply: these templates are KimCad-authored deterministic code, not LLM-generated.** OpenSCAD remains the fallback where OCCT booleans prove fragile.
- **Multi-library substrate.** Templates compose from existing parametric OpenSCAD libraries rather than hand-authoring geometry from scratch. **Evaluate and adopt a set:** BOSL2 (anchor; known limits), plus NopSCADlib, Round-Anything (filleting where BOSL2 struggles), dotSCAD, threadlib/threads.scad, gridfinity, MCAD. Target dozens of families; composition (primitives × features) multiplies coverage.
- **Tier 2 (experimental, offered): local LLM-OpenSCAD.** When no template fits, offer the local model a best-effort OpenSCAD generation, clearly labeled "may not be perfect," run through the same sandbox + validation gates.
- **Tier 3 (opt-in): cloud LLM-OpenSCAD via OpenRouter** for hard cases, when the user opts in.

### 6.4 Sandboxing
Generated CAD runs in an isolated temp directory with time/memory/output-size limits and cleanup. For OpenSCAD: forbid `import()/include()/use` outside the approved library path; ban `minkowski()` at high `$fn`; treat all generated source as untrusted (§12). Configurable binary paths.

### 6.5 Mesh validation (Trimesh + manifold backend)
Load → `is_watertight` → if not, `fix_normals/fix_winding/fill_holes` → re-check → report stats (vertices, faces, volume, bounding box). Install `manifold3d` so Trimesh routes booleans through the fast guaranteed-manifold backend (version-pinned against the known trimesh/manifold3d break). Manifold3D is **not** a repair tool; for repair beyond Trimesh's basics, use a permissive layered path (Trimesh → Open3D) — never pymeshfix/ManifoldPlus (non-commercial).

### 6.6 The Printability Gate (+ PrintProof3D)
The named subsystem between mesh validation and slicing; emits pass/warn/fail with reasons + a "proceed anyway" escape hatch. Checks: dimensional assertion (headline), bounding box vs build volume, min wall thickness vs nozzle, disconnected/tiny shells, overhang/support estimate, hole/tolerance vs material shrinkage, bed-contact heuristic, profile/material sanity. **PrintProof3D** (§6.12) is the deeper validation engine behind this gate: real STL manifold/bounds/overhang/bed-adhesion checks and stateful G-code bounds/thermal validation against printer+material profiles, emitting a structured report (status/issues/severity/suggested-fixes/confidence) that maps to Smart Mesh.

### 6.7 Auto-orientation
Compute stable resting poses (convex hull / largest stable facet), rotate so a sensible face sits at Z=0, surface the chosen orientation, allow override.

### 6.8 Output formats — 3MF default, STL fallback, STEP via CadQuery
Default to 3MF (units + metadata native). OpenSCAD exports 3MF only when built with lib3mf — detect and fall back to binary STL with a warning. **CadQuery exports 3MF and STEP natively in-process** (no subprocess), a point in its favor for the families it backs.

### 6.9 OrcaSlicer integration, bundling & printer profiles
OrcaSlicer bundled and invoked as a subprocess (`--slice 1 --load-settings ... --export-3mf ...`); version pinned; PrusaSlicer CLI as fallback. Built-in profile resource directory ships with it. **Required top-5 maker coverage** (2025 FDM units): Bambu Lab, Creality, Elegoo, Anycubic, Prusa, with tested machine/process/filament profiles for common models and materials (PLA, PETG, TPU, ABS/ASA). One fully-tested profile (Bambu P1S) proves the path; full top-5 is a Final deliverable, validated by community/Kim on real hardware. Users can import their own profiles.

### 6.10 Image-to-3D on-ramp (opt-in; required capability)
Two paths behind one opt-in "use a photo" interface; **neither sits on the required local path**:
- **Default — vision-LLM via OpenRouter.** A multimodal model (free vision models available on OpenRouter) estimates dimensions/features from the photo directly into the DesignPlan. Cheapest, simplest, OpenRouter-native.
- **Accuracy upgrade — real image-mesh (BYO key).** A pluggable provider interface: **TripoSG via fal.ai/Replicate** (MIT weights, open default) with **Meshy** optional. The mesh is measured with Trimesh to seed dimensions, then discarded — KimCad does not ship the provider's mesh, so the provider's output license (e.g. Meshy free-tier CC-BY) does not attach to KimCad's deliverable. Photo upload is disclosed.
- **Local fallback (offline).** A local vision-capable model — **Gemma 4 E4B** (multimodal, Ollama) — or CPU TripoSG. Slower/rougher but works with no key and no internet. (The 890M is outside ROCm, so local image-mesh is CPU-bound; acceptable as a fallback.)

### 6.11 Printer execution (opt-in; core for beta)
- **Spine: PrintProof3D adapters** (Rust; §6.12) — RepRapFirmware, OctoPrint, Moonraker/Klipper, PrusaLink (Digest), Marlin serial — invoked at arm's length (CLI / local REST / its MCP interface). Real protocol code, **simulator/conformance-validated** (not yet hardware-proven).
- **Bambu** is the one weak adapter today (telemetry/upload work; job-control is a no-op; no TLS). Finish it (MQTT-over-TLS:8883 + access code + start/pause/cancel) using the Python **`bambulabs-api`** (MIT) as reference — or route the Bambu path through `bambulabs-api` directly while PrintProof3D handles the rest.
- **Capabilities:** discover, query status (idle? build volume? temps? — used to auto-populate the printer profile), upload, **user-confirmed start**, monitor, capture outcome. Bambu LAN control requires the user to enable Developer Mode + access code; the UX explains this.
- **Safety:** localhost-only; credentials handled as secrets; **every start requires an explicit final user confirmation**; KimCad never auto-starts.
- **"MCP" placement:** MCP is the right shape for KimCad as an *outbound* server (external agents drive KimCad) — **post-beta**, behind auth. It is **not** the inbound transport to printers; reaching printers is deterministic backend plumbing.

### 6.12 Smart Mesh + learning memory (core pillar)
- **Validation engine:** PrintProof3D (`github.com/scottconverse/printerproof3d`, **MIT**, in development; full local access). Verified working 2026-05-31: health check passes (fmt + clippy `-D warnings` + 56 tests), real `validate-model`/`validate-gcode` runs produce correct JSON reports; schemars-generated schema with a drift-guard. To-dos: add the LICENSE file, finish the Bambu adapter, and treat all adapter green as **mock-conformance altitude** until hardware-validated.
- **Smart Mesh v1 = PrintProof3D's per-run validation *plus* KimCad's own learning/history layer.** PrintProof3D is the stateless validator (per artifact: status/issues/severity/suggested-fixes/confidence). KimCad adds: a local run/print-history store; ingestion of mesh stats, DesignPlan, printer specs, slicer warnings, G-code metadata, printer status, outcomes, and user feedback; and outputs a **readiness score, risks, recommendations, confidence, and historical comparison**. PrintProof3D is the engine Smart Mesh is built on, **not** Smart Mesh itself.
- **Learning loop:** post-release real-print outcomes from Kim and volunteer printer-owners are exactly the run-history/outcome data Smart Mesh learns from — the "no in-house printers" constraint is the data pipeline.

### 6.13 Platform
Windows-first. The bundled installer carries all binaries. macOS/Linux betas may follow but do not gate Windows. Config via a user config file (overrides only; defaults pre-wired).

---

## 7. Model Strategy (verified 2026-05-31 — re-verify before each stage)

The decision: a **small, fast local model for DesignPlan JSON**, a **proven non-China alternative**, and **OpenRouter as the cloud router**. The full matrix is maintained out-of-band in `MODEL_GUIDE.md` because it rots fast.

### 7.1 Local default — sized for the loop
The ~80 s draft on `deepseek-coder:6.7b` is **CPU/memory-bandwidth-bound generation**; the iGPU/NPU can't rescue token-gen. Fix = smaller model + constrained decoding. **Default: Qwen2.5-Coder 1.5B** (Q4_K_M, fall back to Q8_0 if JSON validity suffers) — expected ~12–22 s. Fallback for robustness: Qwen2.5-Coder 3B. **Both validated** via the model-prompt-plan benchmark before being selectable.

### 7.2 Proven non-China alternative — Gemma 4 E4B
Some users are uncomfortable with China-origin open models, so a **one-click non-China alternative is mandatory**: **Gemma 4 E4B** (Google; multimodal MoE, ~4B active, on Ollama as `gemma4:e4b` / `gemma4:e4b-it-q4_K_M`; ~2–3× MTP speedup). Slower than the Qwen default but proven to work, and **doubles as the local vision fallback** for the image on-ramp (§6.10). The model picker keeps this a user choice, not a config edit.

### 7.3 Cloud router — OpenRouter
One key, 300+ models, OpenAI-compatible, free vision/text models available. KimCad does not hardwire a cloud vendor; OpenRouter is the router for any cloud LLM use (DesignPlan acceleration, Tier-3 OpenSCAD fallback, image vision-LLM). Cloud is optional; local always works.

### 7.4 Settings UI — model choice
Fast local default (Qwen2.5-Coder) · proven alternative (Gemma 4 E4B) · cloud via OpenRouter. No key required for local; offline and private.

### 7.5 Standing rule — verify capability is actually wired
A documented capability is not a working one. Before any model/runtime/library/adapter is committed as a default, a smoke test must prove the specific tag/version loads and produces valid output (incl. schema-constrained JSON, tool calls, or adapter conformance) on the target hardware. Re-verify §7 and `MODEL_GUIDE.md` at the start of every stage.

---

## 8. CAD Component Library (multi-library, grown deliberately)

The library is the quality moat — it does more for first-try accuracy than any model upgrade. **10 deterministic families is a seed, not a ceiling.** Architecture: a **library-agnostic template layer** that composes from several vetted OpenSCAD libraries (and CadQuery for STEP/fillet families) behind one interface, so breadth grows by reuse, not from-scratch authoring. Evaluate/adopt: BOSL2 (anchor), NopSCADlib, Round-Anything, dotSCAD, threadlib, gridfinity, MCAD. Each template carries a standardized header (parameters, defaults, min FDM wall thickness) and a manifest the planner composes against. Target dozens of families plus combinatorial variants; the tiered LLM-OpenSCAD fallback (§6.3) covers the long tail so the product never dead-ends.

---

## 9. Build Plan (Stages 7–10)

Stages 0–6 are complete. **Stage 6 is a packaged Windows local-CAD release candidate — not the beta.** The remaining work is four large, coherent stages (no small-slice sprawl). Detailed deliverables/acceptance per stage live in `internal/agent-workflows/ROADMAP-v3-stages-7-10.md`.

- **Stage 7 — Spec Rebaseline (docs only, no feature code).** This document (v3.0) becomes controlling; correct stale framing; reclassify Stage 6; define beta/final; refresh the control-plane and work-queue; write the decision log. *(In progress.)*
- **Stage 8 — Smart Mesh + Learning + Image on-ramp + model swap + template expansion + sliders.** The quick-win model swap (Qwen/Gemma, validated) first; Smart Mesh v1 (PrintProof3D validation + KimCad learning/history); image-to-3D opt-in on-ramp; multi-library template expansion + tiered fallback; CadQuery parallel backend; **real sliders + live preview**. UI/UX is the acceptance gate.
- **Stage 9 — Real Printer Execution.** PrintProof3D adapter spine + finished Bambu; discover/status/upload/confirmed-start/monitor/outcome; conformance-validated against simulators/mocks. (No real-hardware gate.)
- **Stage 10 — Windows Beta Gate.** Installer dependency checks; downloaded-release validation; full no-CLI flow; SmartScreen-warning walkthrough; checksums + GitHub provenance; full audit; GitHub beta release. Post-release: Kim + community real-hardware validation feeding Smart Mesh.

---

## 10. Hardware Requirements (capability classes)

Present requirements as capability classes; the Beelink is the dev reference, not the spec. **Reference:** Ryzen AI 9 HX 370 (12C Zen 5), Radeon 890M, XDNA2 NPU (50 TOPS), 32 GB. **GPU reality:** the 890M cannot run image-to-3D models locally at speed — it's outside stable ROCm support; the NPU is not used by current GGUF runtimes. Therefore local image-mesh is CPU-bound (slow, fallback only); the cloud path is the default for the image on-ramp. Local DesignPlan generation runs fine on CPU with the small models in §7.

---

## 11. Risk Assessment

- **Bambu firmware lockdown (Jan 2025):** LAN control needs Developer Mode + access code (disables cloud). Affects every Bambu approach; surfaced in UX. *Mitigation:* clear walkthrough; `bambulabs-api` reference; finish the TLS path.
- **PrintProof3D maturity / single-owner / mock-only altitude:** real code, but no hardware-proven adapters and no license file yet. *Mitigation:* it's owner's MIT code with full local access; add the license; treat adapter green as conformance-altitude; hardware-validate post-release.
- **Image-to-3D cloud dependency + privacy:** photos leave the machine on the cloud path. *Mitigation:* opt-in only, disclosed, with a local fallback; the mesh is a discarded seed.
- **OCCT/CadQuery bundling:** hundreds of MB + PyInstaller freezing effort. *Mitigation:* parallel backend behind an interface; prove on a few families; keep OpenSCAD default.
- **Local model JSON reliability at small sizes:** *Mitigation:* schema-constrained decoding; benchmark-gate every model; Gemma 4 E4B as the robust alternative.
- **Unsigned installer / SmartScreen friction:** *Mitigation:* explicit walkthrough that prepares the user; checksums + GitHub provenance.
- **No in-house printers:** *Mitigation:* simulator/conformance validation as the release gate; Kim + community for real-hardware proof; outcomes feed Smart Mesh.

---

## 12. Security & Threat Model

KimCad binds a local web server that runs subprocesses derived from model output and can contact printers. Posture:
- **Localhost-only by default.** No LAN/remote exposure unless the user deliberately opts in.
- **Generated CAD is untrusted.** Sandbox (§6.4). Deterministic templates are trusted KimCad code; the Tier-2/3 LLM-OpenSCAD path runs in the same sandbox.
- **CadQuery note:** CadQuery executes Python, but only **KimCad-authored deterministic template code** — never LLM-generated Python. The v2.1 reason for excluding CadQuery (exec of generated Python) does not apply. KimCad still never `exec()`s model-generated Python.
- **Printer execution is explicit and user-confirmed.** No auto-start. Credentials (API keys, Bambu access codes) handled as secrets, never logged. Network/serial contact only on user action.
- **Cloud calls and photo uploads are opt-in and disclosed.** No data leaves the machine on the core local path.
- **G-code is printer-specific, sensitive output** — explicit printer/material/profile confirmation before export or print (§5.5–5.6).

---

## 13. Licensing & Packaging Strategy

- **KimCad's own code: Apache-2.0** (patent grant + clear notice terms; owner is fine with permissive reuse, including commercial, and considers copyleft protection increasingly moot).
- **License filter for dependencies:** copyleft is fine **iff** the license permits free distribution and free commercial use. Excluded: non-commercial-only libraries (pymeshfix/MeshFix, ManifoldPlus) and any non-commercial/RAIL-restricted model weights.
- **Bundled components:** OpenSCAD (GPL-2.0), OrcaSlicer (AGPL-3.0), PrintProof3D (**MIT**, owner's), CadQuery (Apache-2.0) + OCCT (LGPL). All invoked at arm's length (subprocess / local service / separate binary) — "mere aggregation," so KimCad's Apache-2.0 orchestrator is unaffected. The "don't link, do bundle" rule holds; AGPL §13 does not bite (stock, unmodified, localhost-only). Ship each component's license + notices + a source offer for the exact versions.
- **No code-signing for beta.** Ship unsigned with an explicit SmartScreen-warning walkthrough, official GitHub release provenance, and published SHA-256 checksums. Signing/notarization is a possible Final/post-beta item, not a beta blocker.
- **Image-mesh / experimental adapters** are fenced from the core, clearly labeled, never required to run the product.

---

## 14. Open Questions & Decision Log

Full decision history with reasoning and provenance: `docs/spec/DECISION-LOG-v3.md`. Summary of what's **decided** in v3.0: Windows-first; Apache-2.0; deterministic templates (OpenSCAD default + CadQuery parallel) with tiered LLM-OpenSCAD fallback; multi-library template expansion; image-to-3D required-but-opt-in (OpenRouter vision-LLM default, TripoSG/Meshy mesh upgrade, Gemma 4 E4B local fallback); real printer execution via PrintProof3D spine + bambulabs-api Bambu; Smart Mesh = PrintProof3D validation + KimCad learning; Qwen2.5-Coder default + Gemma 4 E4B non-China alternative; OpenRouter cloud router; no beta code-signing; Stage 6 reclassified; real-hardware proof removed as a release gate.

**Still open:** exact Gemma 4 E4B tag + Qwen quantization (benchmark to settle); the adopted OpenSCAD library set (evaluate BOSL2 + complements); whether to finish Bambu in Rust vs route via `bambulabs-api`; trademark/domain check for "KimCad"; CadQuery family coverage extent.

---

## Appendix B — Benchmark prompt set (the done-gate)

Ten canonical functional prompts, each with expected geometric properties for automated scoring (slices-clean · matches-request · correct-dimensions):

1. Wall hook · 2. L-bracket with two M4 mounting holes · 3. Box with snap-fit lid · 4. Pegboard hook · 5. Cable clip · 6. Spacer (ID/OD/height) · 7. Simple enclosure (internal volume) · 8. Wall-mounted spool holder · 9. Plate (50×50×10 mm) with a centered 5 mm hole · 10. Drawer divider.

Scored on Trimesh properties (`is_watertight`, `math.isclose(volume, expected)`, `bounding_box == expected`) plus feature-specific assertions (e.g. hole diameter). The same harness A/B-tests models and prompt revisions and gates every offered model (§7).

*End of Unified Specification — v3.0. Supersedes v2.1. Load-bearing facts verified 2026-05-31; re-verify per §7.5.*
