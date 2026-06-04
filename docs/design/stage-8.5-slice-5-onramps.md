# Stage 8.5 · Slice 5 — Advanced on-ramps & trust (DESIGN ONLY)

**Status:** design draft for Scott's review. **No product code ships in this slice** — this is the
UI-first gate that settles *how* the three advanced on-ramps look, behave, and earn trust **before**
a line of Slice 6/7 code is written. Scott's approval here is the gate.

**Companion mockup:** `docs/design/prototype/slice-5-onramps.html` — open it in a browser. It renders
every surface below against the real Workshop tokens (warm sand / terracotta / dark viewport), so you
can see and feel them, not just read about them.

**Grounded in:** the v3.0 spec (§5.2 model picker, §5.3 + §6.10 photo on-ramp, §6.3 Tier-2/3
fallback, §6.1 OpenRouter) and the **settled** model decision (spec Addendum, line 17): `gemma4:e4b`
is the default; Qwen was bake-off-rejected and is a manual `--backend` only. The spec body's older
"Qwen default" wording is superseded — this design follows the settled truth.

---

## The four surfaces

| # | Surface | Lives in | Built in | Default |
|---|---------|----------|----------|---------|
| A | **AI model status + picker** | Settings → AI | Slice 6 | `gemma4:e4b`, local, always |
| B | **Cloud opt-in (OpenRouter)** | Settings → AI | Slice 6 | OFF |
| C | **Experimental raw-codegen generator** | Settings → AI **+** offered inline on an out-of-template request | Slice 6 | OFF |
| D | **Photo input mode** ("describe with a photo") | Landing + workspace (an input mode, *not* Settings) | Slice 7 | n/a — opt-in affordance |

A, B, C all live in one **Settings → AI** section so the model story reads as one place. D is an
*input on-ramp*, so it belongs where you start a design (landing + the workspace prompt), surfaced as
a secondary affordance next to the text box — never on the primary path.

---

## Trust rules — HARD constraints on the Slice 6/7 builds (settled; not re-decided ad hoc)

These are load-bearing. The builds that follow inherit them as acceptance criteria, not suggestions.

1. **`gemma4:e4b` is the only default — text, codegen, AND vision.** The photo on-ramp uses *its*
   local vision. Nothing silently switches models. The UI never offers a Chinese model
   (Qwen / MiniCPM / Qwen-VL) as a default or a recommendation; Qwen stays a manual `--backend`
   only, never surfaced in the UI. The model "picker" shows gemma4:e4b as THE model with its health
   — it is not a menu that pushes alternatives.
2. **Cloud is always opt-in, OFF by default, and labeled at the point of use** — "this sends your
   design prompt off your machine." Local-first is the resting truth; every cloud feature degrades
   to the local path. The app binds localhost only; a cloud call is an explicit, user-initiated act.
3. **API key = a normal Settings field** (this is a *consumer* product, not a Fortune-50 networked
   one): the user types it in and saves it; on reopening Settings it shows **masked — last 5–6
   characters only** (e.g. `····················wQ9f2`). Never stored in the repo or logs; the full
   secret is never echoed back to the screen or the network beyond the OpenRouter call itself.
4. **The experimental raw-codegen generator is OFF by default, labeled untrusted/experimental**, and
   runs **only** through the existing `openscad_runner` sandbox (blocked-code check — bans file-I/O,
   `import()`/`surface()`, `use`/`include` outside the bundled `library/`, and `minkowski()`; plus
   cwd isolation, a render timeout, and an output-size cap). It **never** bypasses the Printability
   Gate. It is *offered* when a request has no template match (no dead-ends), with a clear
   "may not be perfect" warning — never silently taken.
5. **Photo on-ramp uses gemma4:e4b's LOCAL vision; the photo never auto-sends.** It produces a
   *rough seed* (a description + approximate proportions) that pre-fills the existing text→DesignPlan
   path — the user then refines it with the conversation (Slice 2) and numeric entry (Slice 3). A
   photo carries no scale, so dimensions are estimates until the user sets them. No "photo →
   finished part" promise. Any cloud vision path is itself opt-in + labeled per rule 2.

---

## Surface A — AI model status + picker

**Goal:** the user can see their AI is healthy and understand what's running, without a menu that
sells them other models.

**What it shows (Settings → AI, top block):**
- **Model:** `gemma4:e4b` · **Local** badge · a status dot + line: *Running* (green) / *Pulled, not
  running — Start* (amber, with a one-click start) / *Not installed — Get the model* (with progress).
- A plain one-liner: *"KimCad's local AI. Runs on your machine, on your CPU — no internet required,
  nothing leaves your computer."*
- **No dropdown of alternative models.** gemma4:e4b is THE model. (Power users can point at a
  different backend from the CLI; that is intentionally not a UI affordance — see trust rule 1.)

**States:** Running · Stopped (→ Start) · Not installed (→ Get model, with a progress bar) · Checking.
Every non-running state gives a concrete next action (no dead-end), per the §4.2 usability gate.

---

## Surface B — Cloud opt-in (OpenRouter)

**Goal:** a user who *wants* a faster/cloud model for a hard case can opt in, with the privacy cost
stated plainly and the key handled like a normal consumer setting.

**Flow (Settings → AI, "Cloud acceleration" block):**
1. A single toggle: **Use a cloud model (optional)** — OFF by default. Sub-label:
   *"Local always works. Turning this on lets KimCad send a design prompt to a cloud model via
   OpenRouter for a hard request. **This sends your prompt off your machine.**"*
2. When ON, the block expands to:
   - **OpenRouter API key** — a text field (`sk-or-…`) + **Save**. On save: a green *"Saved"* tick.
   - On reopening Settings, the field shows the **masked** value — last 5–6 chars only —
     with a **Replace** affordance (clearing it back to an entry field). The full key is never
     re-rendered. (Trust rule 3.)
   - A **local/cloud indicator** — when cloud is active, the workspace shows a small *"Cloud"* chip
     near the model status so the user always knows where a request is going; default reads *"Local."*
3. A link: *"Get a free OpenRouter key →"* (opens externally; we don't create the account for them).

**Honesty:** cloud is framed as an *accelerant for a hard case*, never a requirement. If a cloud call
fails, it falls back to local and says so. **Per the global safety rules, KimCad does not enter the
key for the user — the user pastes/saves it themselves.**

---

## Surface C — Experimental raw-codegen generator

**Goal:** never dead-end an out-of-template request — offer the experimental LLM-OpenSCAD generator —
while making its untrusted, may-not-be-perfect nature unmistakable.

**Two entry points:**
1. **Inline (the no-dead-end path):** when a request has no template match, the assistant turn
   offers it: *"I don't have a precise template for that. I can try an **experimental** generator
   that writes the shape directly — it's not always right, and it runs in a locked sandbox and still
   has to pass the printability check. Try it?"* → an explicit **Try the experimental generator**
   button. Never auto-run.
2. **Settings → AI toggle:** **Experimental: direct shape generator** — OFF by default, with an
   **Experimental · Untrusted** chip and the sub-label: *"Lets the AI write the 3D shape directly
   when no template fits. Off by default. Runs in a locked sandbox; never skips the printability
   check; results can be rough."*

**Guardrails shown to the user:** the warning copy names the two protections in plain English —
*"runs in a locked sandbox"* (the `openscad_runner` blocked-code check + isolation + timeout) and
*"still has to pass the printability check"* (never bypasses the gate, trust rule 4).

---

## Surface D — Photo input mode ("describe with a photo")

**Goal:** start a design from a photo, locally, as a *rough seed* — honestly framed, never a
"photo → finished part" promise.

**Flow:**
1. **Entry:** on the landing and the workspace prompt, a secondary affordance beside the text box —
   *"📷 Describe with a photo"* (clearly secondary; text is the primary path). Per §5.3 it is
   surfaced only when the user reaches for it.
2. **Pick/drop a photo** → an immediate local preview thumbnail. Copy: *"Your photo stays on your
   computer. KimCad's local vision reads it into a rough starting point — it never leaves your
   machine."* (Trust rule 5.)
3. **Reading state:** *"Reading your photo…"* with honest progress (local vision on CPU takes a
   moment) — the same no-frozen-spinner treatment Slice 9 will standardize.
4. **Rough-seed confirm card:** the vision result is shown as an *editable seed*, not a fait
   accompli: a draft description + estimated proportions (e.g. *"a rectangular box, roughly 80 × 50 ×
   30 mm — these are guesses from the photo; set the real sizes"*) + a clear note: *"A photo can't
   tell us scale, so these are estimates. Adjust anything, then continue."* → **Use this as a
   starting point** seeds the normal text→DesignPlan flow; from there it's the standard conversation
   (Slice 2) + sliders/numeric (Slice 3).
5. **Failure states:** unreadable image, too-large image, *"couldn't read that photo — try a clearer
   shot or describe it in words instead"* (always a concrete fallback).

**Hard boundary:** the photo is untrusted input into the *validated* DesignPlan — same trust boundary
as text, new channel (§3.2). The delivered geometry is KimCad's own deterministic output, never the
raw image-mesh.

---

## Settings information architecture (Slice 6 builds the screen; designed here)

A single Settings screen, sectioned top-to-bottom:

1. **Printer & material** — default printer (from the bundled top-5) + default material.
2. **Units** — mm / inch (the Slice 4 preference, surfaced here too).
3. **AI** — Surface A (model status) → Surface B (cloud opt-in) → Surface C (experimental toggle),
   in that order: the safe local default first, the opt-in cloud next, the untrusted experimental
   last.
4. **Tools** — OpenSCAD / OrcaSlicer presence + health.
5. **About** — version, an open-source/Apache-2.0 note, a reset.

Discovery-at-the-moment-of-need (per §4.2) is preserved: the experimental generator is *also* offered
inline on an out-of-template request; cloud isn't pushed, only available.

---

## What this unblocks

- **Slice 6** builds the Settings screen + Surfaces A/B/C (model status, cloud opt-in with the masked
  key, the experimental toggle) against these flows and trust rules.
- **Slice 7** builds Surface D (the photo on-ramp) against this flow, using gemma4:e4b local vision.

## Open questions for Scott
1. **Cloud model choice** — when cloud is on, do we (a) keep it invisible (KimCad picks a sensible
   OpenRouter model), or (b) expose a model field for power users? Recommend **(a)** for the consumer
   default with a future "advanced" disclosure — fewer ways to misconfigure; matches the "no menu that
   sells models" posture.
2. **Photo entry prominence** — secondary-but-visible (a small camera affordance always present) vs.
   tucked behind an "other ways to start" disclosure. Recommend **secondary-but-visible** — it's a
   headline capability worth seeing, still clearly not the primary path.
3. **Experimental inline offer** — offer it on *every* out-of-template miss, or only after the normal
   path visibly fails once? Recommend **on the miss** (no dead-end is the §4.2 rule), with the warning
   carrying the weight.
