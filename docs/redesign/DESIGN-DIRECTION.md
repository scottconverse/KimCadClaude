# KimCad — Branding & Landing Redesign Direction
**Branch:** `kim-branding-overhaul` (local only, nothing pushed)
**Date:** 2026-06-18 (overnight study)
**For:** Scott — review with a cool head. Nothing here is shipped; it's a proposal + the work in progress.

---

## 0. What I studied (sources, so you can check my work)
- **Your brief (ground truth):** `Downloads/KimCad_design/uploads/KimCad-Redesign-Brief.md` — the real feature/UX redesign brief.
- **Kim's actual brand book:** `Zen_Design_World_Brand_Book.pdf` (her Google Drive) — her official brand spec.
- **Kim's marketing brief:** `Zen Design World — Marketing Brief 3.4.26.docx` (her Drive) — her voice, audience, positioning.
- The current shipped app + landing page (`docs/index.html`) and a full branding audit of the app's source.
- (Her site `zendesignworld.net` is JS-rendered so it wouldn't fetch as text; the brand book is the authoritative spec anyway.)

---

## 1. The big correction: the cube was never yours
Your brief literally lists **"Kim as brand mark + assistant avatar."** There is **no copper cube anywhere in it.** The cube mark came from a *generated* `KimCad Redesign.html` a prior session produced — a Claude artifact, not your design. So:
- **Kim's face (round avatar) is THE brand and the primary logo.** Bigger at the top of the landing page.
- A clean **geometric/abstract mark** is allowed **only** where a face doesn't do the branding job (e.g. a tiny favicon at 16px, a monochrome watermark in a dense technical diagram) — used with judgment, never as the default identity.

---

## 2. Kim's aesthetic = the north star ("Design in Balance")
From her brand book + marketing brief:
- **Essence:** *"refined minimalism and balanced creativity… harmony between technology and aesthetics."*
- **Personality:** *"Calm, intentional, creative, thoughtful — minimal and modern without being cold."*
- **Palette:** warm metallic **gold `#D4AF37`**, deep **black `#000000`**, **white**, charcoal `#333333`, soft silver `#BFBFBF`. **Gold-on-black = premium.**
- **Type:** Helvetica Neue (bold headlines) + Lato (body). Whitespace, symmetry, clarity. No drop shadows, no busy textures.
- **Her product:** ZenFrame — precision, sustainable PLA, gallery-quality, for makers/artists. Colorway range (Black, Denim, White, Aqua, Lavender, Cayenne, Petal Pink).
- **The lovely tie-in:** KimCad already has a **"Zen" frame/decor template family** named after her world. KimCad can literally help make ZenFrame-spirit objects.

**Design principles for the redesign (derived from the above):**
1. **Balance & whitespace over density.** Fewer, larger, more confident elements. Let it breathe.
2. **Warm minimalism, not cold.** Keep warmth; lose the clutter.
3. **One premium moment.** A gold-on-dark section for contrast and rhythm (her premium register).
4. **Gallery presentation.** Real product screenshots shown like curated objects, not crammed cards.
5. **Precision + craft + sustainability + local/private** — values KimCad and Zen Design World genuinely share.
6. **Kim, present and human** — her face as the warm mark; her voice (first person) given a face.

---

## 3. The one decision only you should make (palette)
There's a real tension and I will NOT resolve it unilaterally:
- **KimCad today** = "warm workshop": terracotta/copper accent (`#d2611f`), Bricolage Grotesque, cream paper. Baked into the whole app (tokens, dark theme).
- **Kim's brand** = gold/black/white, Helvetica, refined minimalism.

**Three options for tomorrow:**
- **(A) Keep KimCad's warm-workshop identity**, just apply her *principles* (balance, whitespace, restraint, one premium dark/gold moment). Lowest risk; app untouched. ← my default for tonight's landing-page proposal.
- **(B) Shift KimCad toward her Zen palette** (introduce gold as the premium accent, more black/white minimalism) — a deliberate brand evolution. Bigger; touches the app. Needs your call.
- **(C) Hybrid** — warm-workshop *product UI* (in-app), Zen-premium *marketing* (landing/docs). Defensible: the app is the workshop; the storefront is the gallery.

I'm building tonight's landing proposal as **(A) leaning toward (C)** — warm core + a premium gold/black gallery moment — so you can see the bridge and decide.

---

## 4. What I'm doing on this branch tonight (all reviewable, none pushed)
1. ✅ Study + this direction doc.
2. ⏳ Capture **real app screenshots** (light + dark) to use as honest product proof.
3. ⏳ **Redesign the landing page** as a concrete proposal: bigger Kim logo, real screenshots, whitespace, a premium gold/black section, dark mode, favicon + OG image, single clear CTA, responsive mobile nav. Saved as a *new* file so the current page is untouched for comparison.
4. ⏳ **App OS-branding fixes** (favicon = Kim, native window icon, installer/desktop icon, first-run Welcome shows Kim, avatar accessibility) — staged on the branch, not built into a release.
5. ⏳ A morning **review package**: side-by-side before/after, the open decisions, and exactly what's safe to ship vs what needs your sign-off.

---

## 5. The "three things we kept" — being careful
You mentioned a prior session blew up the design spec by rushing to delete, and only ~3 things were kept. I am **not** rushing any deletions. The brief's own "What's already right — do NOT redo it" list (3-pane workspace, 5-step wizard, conversation loop, print drawer, photo modal, Kim branding, type system) is preserved as-is. Anything I propose to change is additive or isolated to the landing/branding surfaces — the shipped app logic is not being gutted. We decide structural changes together tomorrow.
