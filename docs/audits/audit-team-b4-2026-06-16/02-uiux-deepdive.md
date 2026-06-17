# UI/UX Deep-Dive — KimCad 0.9.0b4 (+ restored UI)

**Audit date:** 2026-06-17
**Role:** Senior UI/UX Designer
**Build under test:** `0.9.0b4`, `origin/main` @ `356867d` (b4 rollback `c8e9f44` + restored post-b4 UI). React SPA in `frontend/src/`.
**Method:** the real app driven live — `kimcad web` on the real planner (`qwen2.5:7b`, real OrcaSlicer/OpenSCAD, 16 persisted designs). Driven through a real browser (preview harness): screenshots, DOM/ARIA inspection, sampled WCAG contrast in both themes, keyboard-event probing of the Inspector tablist and modals, mobile (375px) and desktop (1280px) viewports, and live API probes of `/api/connectors`, `/api/options`, `/api/model-status`, `/api/designs`. Server killed when done.
**Auditor posture:** Balanced.

---

## TL;DR

KimCad's UI is, top to bottom, a genuinely well-made product — the strongest dimension is its **honesty under uncertainty**: the on-device design path narrates its own slowness ("This runs on your computer's AI — it can take a few minutes… Nothing leaves your machine. 0:08 elapsed"), every data view I could reach has a designed empty/loading/error state, the readiness gate speaks plain English, and the color system passes WCAG AA in both light and dark themes. The weakest dimension is **accessibility of one custom widget**: the Inspector tablist advertises `role="tablist"` but implements no arrow-key navigation and gives every tab `tabindex=0`, breaking the WAI-ARIA Tabs contract a screen-reader user is promised. The single highest-leverage fix is wiring that tablist's keyboard model. Two restored-UI items need polish — the Settings section-nav marks a whole *group* as `aria-current` (two items light up at once) and its sub-items are non-functional anchors, and the 1.27 MB Kim avatar PNG ships to render at 32 px. No Blockers; the core describe→design→gate→slice→download journey is intact and a pleasure to walk.

## Severity roll-up (UX)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 3 |
| Minor | 5 |
| Nit | 4 |
| **Total** | **12** |

## What's working

- **The on-device loading state** (`Viewport` overlay, live-verified) — spinner + phase label ("Planning the shape") + progress dots + honest expectation copy + a live `0:08 elapsed` timer + a Cancel escape, all inside a `role="status"`. This is best-in-class UX for a slow local operation; most products would show a bare spinner and lose the user. Specific credit.
- **Empty states are designed, not blank** — Inspector Parameters reads "The part's adjustable parameters will appear here once it's designed."; Export reads "Once a part is designed you can pick a printer, slice it, and download the file."; the chat thread has a resting hint. No blank screens encountered.
- **The Quality/Printability panel** — Readiness 92/100 + "Ready to print" + confidence + recommendations + a target-vs-actual dimension table with watertightness checks. Honest, scannable, and it teaches the user what "printable" means.
- **Color system** — sampled AA-clean in both themes: light Design CTA 5.03:1, lede 4.66:1, chips 13.67:1; dark Design CTA 8.54:1, lede 7.64:1. Theme is a real token inversion (`kc-theme-dark` on `<html>`), instant and persisted.
- **Real keyboard model where it counts** — a skip-to-main-content link; `?`/N/D/comma/Esc shortcuts with a discoverable help modal; FirstRunWizard and Shortcuts modal both trap focus, move focus inside on open, and close on Esc (live-verified). `prefers-reduced-motion` is honored (2 media blocks).
- **Decorative imagery done right** — the avatar is a CSS-background `<span aria-hidden="true">` inside `<button aria-label="KimCad — home">`; zero `<img>` elements missing alt because all imagery is intentionally decorative background.
- **Honest, on-brand copy throughout** — "Nothing leaves your machine," "local always works," the cloud opt-in's blunt "This sends your prompt off your machine." The voice is consistent and trustworthy.
- **Zero console errors/warnings** across landing → wizard → My Designs → workspace → Inspector → Settings → a live design run → cancel.

## What couldn't be assessed

- **A real successful design-to-slice run end-to-end in this session** — I started a live design and confirmed the loading state, then cancelled to avoid a multi-minute local-model run; the *success* path (mesh render, gate, slice artifact) was instead assessed by opening a persisted design (id `46f26d2e…`, a passed trinket dish) into the workspace. The slice artifact itself is proven in the companion walkthrough.
- **Real connected-printer states** (Busy/Offline/Paused/Auth-failed) — only the built-in `mock` connector is configured, so only the `Ready · simulated` label was observable live. The other `connectorLabel` branches were read in source, not rendered.
- **Photo/sketch on-ramp dialogs and the LibraryModal** were not opened live (present and wired per snapshot + the vitest/e2e suite).
- **True screen-reader pass** (NVDA/VoiceOver) — ARIA was inspected programmatically; an audible SR session is the right next step for the tablist finding below.

---

## First impressions

A first-time user lands on a centered, calm screen: a green capability strip ("Ready to print in ~15 minutes · no CAD skills"), a confident headline ("What do you want to make today?"), one obvious primary action ("Design it →") with a placeholder that teaches by example, two image on-ramps, three "TRY" chips, a library link, and a 3-step process strip. Within 5 seconds you know what this does and what to do. On a fresh machine the **FirstRunWizard** overlays this — 5 steps, a clear stepper rail with checkmark/current states, a "Skip setup" escape, and a model card showing a live green "Ready" — a friendly, non-adversarial front door. The eye lands where the team wanted it. The only oddity is the brand mark itself: it's a **photorealistic human face** ("Kim") at 32 px in the top-left where a product logo usually sits. It's warm and distinctive, but at 32 px a detailed face reads as visual noise rather than a mark, and it sets a "this is a person/assistant" expectation the product only half-leans into (see UX-009).

## Journey walkthroughs

### Journey: New user → first part

Wizard (Welcome → Set up your AI → Pick your printer → Direct printing → Ready) → Skip/Finish → Landing → type a prompt → **Design it** → viewport loading overlay (phase + elapsed + Cancel) → part renders with dimension annotations → Inspector (Parameters editable locally; Quality shows the gate; Export to slice) → **Slice & prepare file** → Download .3mf/.STL/.STEP. This journey is coherent and has no dead ends: every wait is narrated, every gate verdict is explained, and the user can cancel or refine at any point. The refine affordance ("Refine by talking" + one-tap chips, gated on a real part existing) is a genuinely modern pattern.

### Journey: Return user → reopen a design

Topbar **My Designs** → card grid (search, sort, per-card Rename/Duplicate/Backup/Delete) → open a card → workspace with the part restored. Clean. Two snags surfaced here: several cards render **blank black thumbnails** despite `has_thumb:true` (UX-007), and a stray `demo-gohello` card looks like leftover test data in the user's library (UX-008).

---

## Findings

> Finding ID prefix: `UX-`. Categories: Visual hierarchy / Copy / State / Accessibility / Responsive / Journey / Pattern / IA.

### [UX-001] — Major — Copy — Export connector badge reads "mock · Ready · simulated"; the raw config key "mock" leaks unprettified

**Evidence**
Route: workspace → Inspector → Export tab (and the Export card body). Live DOM:
`<div class="kc-connector"><span class="kc-status-dot kc-tone-pass"></span><span class="kc-connector-name">mock</span><span class="kc-connector-label" role="status">Ready · simulated</span></div>`
`/api/connectors` returns `{"connectors":[{"name":"mock","simulated":true,"configured":true}, …], "default":"mock"}`. `ConnectorStatus.tsx` renders `name` (the raw key `mock`) directly; siblings elsewhere prettify via `displayName()`. The visible string is **"mock · Ready · simulated"** (the `·` is a CSS separator). Two problems: (a) `mock` is an internal key surfaced to the user, and (b) "simulated" sits one line above "this part can't be sliced"/the Slice button, where it can be misread as *the slice* being simulated rather than *the connection* being a no-hardware loopback.

**Why this matters**
A user about to commit a real print sees an unexplained word ("mock") and an ambiguous one ("simulated") at the exact moment they need confidence. It reads like a developer placeholder leaked into shipping UI — it dents trust precisely where trust is being asked for.

**Blast radius**
- Adjacent code: `frontend/src/components/ConnectorStatus.tsx` (the `name` render); `frontend/src/connectorStatus.ts` (`connectorLabel`, the "Ready · simulated" string); the same connector list feeds `SendPanel`/`ConnectionsCard` — verify the key→label prettification is centralized so this is fixed once.
- Shared state: the connector registry (`/api/connectors`) — any future connector key (`octoprint`, `moonraker`, `bambu`…) will surface raw the same way unless prettified.
- User-facing: the Export panel for every part with the default mock connector (i.e. every user who hasn't connected hardware — the common case).
- Migration: none; presentation-only.
- Tests to update: `ConnectorStatus.test.tsx`, `connectorStatus.test.ts` (assert prettified name + new label).
- Related findings: none (isolated copy/IA defect).

**Fix path**
Prettify the connector name (add a `displayName()` mapping: `mock → "Built-in (no printer connected)"`) and disambiguate the label so it describes the *connection*, not the slice. Suggested copy: render the row as **"Built-in preview · no printer connected"** with the green dot, and reserve "Ready" for real connected hardware. If keeping a compact form, **"No printer connected — files only"** is clearer than "mock · Ready · simulated." Never show the raw `mock` key.

---

### [UX-002] — Major — Accessibility — Inspector tablist has no arrow-key navigation and no roving tabindex

**Evidence**
Route: workspace → Inspector (`<div role="tablist" aria-label="Inspector">` with three `role="tab"`: Parameters / Quality / Export). Live keyboard probe: focusing the first tab and dispatching `ArrowRight`, `ArrowRight`, `Home` left focus and `aria-selected` unchanged on "Parameters" every time — there is no keydown handler. All three tabs report `tabindex=0` (no roving tabindex). The ARIA wiring is otherwise correct: each tab has a unique `id`, `aria-controls` to a `role="tabpanel"`, panels `aria-labelledby` back, and inactive panels are `hidden`. Click activation works.

**Why this matters**
`role="tablist"` is a promise. A screen-reader user hears "Parameters, tab, 1 of 3" and reaches for Left/Right arrows — the documented, expected interaction (WAI-ARIA APG Tabs pattern). Nothing happens, which reads as a broken control. With every tab at `tabindex=0`, keyboard users must Tab through all three (rather than arrowing within one Tab stop), and the standard Home/End jumps don't exist. There *is* a workaround (Tab + Enter still reaches and activates each tab), which is why this is Major and not Critical — but it's the one place the otherwise-strong a11y story falls down, and it's a custom widget so no native fallback rescues it.

**Blast radius**
- Adjacent code: the Inspector tablist component (`frontend/src/components/RightPanel.tsx` / `Workspace.tsx` — wherever `role="tablist"` is authored). Check whether any other custom tablist exists; if a shared `<Tabs>` primitive is introduced, it fixes all of them.
- User-facing: every keyboard and screen-reader user in the workspace — the primary post-design surface.
- Migration: none.
- Tests to update: add a keyboard-interaction test (ArrowRight/Left/Home/End move selection + focus); update `RightPanel.test.tsx`.
- Related findings: UX-003 (the Settings section-nav `aria-current` misuse — both are "ARIA attribute present but semantics not fully honored," same root discipline gap).

**Fix path**
Implement the APG Tabs keyboard model: roving tabindex (active tab `tabindex=0`, others `tabindex=-1`); `ArrowRight`/`ArrowLeft` (with wrap) and `Home`/`End` move focus and selection between tabs; `aria-selected` follows. Automatic-activation (select-on-focus) suits this 3-tab panel. Keep the existing id/aria-controls wiring — it's already correct.

---

### [UX-003] — Major — Accessibility / IA — Settings section-nav marks an entire group `aria-current` and its sub-items are non-functional anchors

**Evidence**
Route: `#/settings`. The sticky left nav (`.kc-set-nav`, `aria-label="Settings sections"`) has 4 group headings and 9 sub-links, but **only 4 anchor targets** (`#grp-design`, `#grp-ai`, `#grp-output`, `#grp-system`). Live DOM with `grp-design` active: both "Printer & material" and "Display" carry `aria-current="true"` — because `SettingsPanel.tsx` sets `aria-current={activeGroup === g.id}` on *every* link in the group, and every link in a group shares the same `href="#grp-design"`. So (a) two items highlight at once, and (b) clicking "Display" jumps to the same anchor as "Printer & material" — the sub-items look like per-section nav but only navigate per-group. On mobile (375px) the group `<span>` headings are `display:none`, leaving 9 ungrouped pills with two adjacent ones both showing the active accent — the dual-highlight is most jarring here.

**Why this matters**
A section-nav's whole job is to answer "where am I, and where can I jump?" This one answers ambiguously (two items lit) and over-promises (9 jump targets, 4 destinations). A user clicking "Display" expecting to land on the Display card lands on the group top instead — a small but repeated "that didn't do what I clicked" friction. It's a restored-UI item (`9af7cc7`) and was flagged in the walkthrough; worth fixing rather than shipping loose.

**Blast radius**
- Adjacent code: `frontend/src/components/SettingsPanel.tsx` (the nav map + `activeGroup` IntersectionObserver + the `aria-current` expression); `styles.css` `.kc-set-navlink[aria-current='true']` and the `@media (max-width:860px)` rule that hides group labels.
- User-facing: the Settings screen for all users; the effect compounds on mobile.
- Migration: none.
- Tests to update: `SettingsPanel.test.tsx` (assert exactly one `aria-current` item; assert sub-anchors resolve to distinct ids).
- Related findings: UX-002 (same ARIA-discipline root).

**Fix path**
Two coherent options — pick one:
1. **Make the nav per-item (recommended).** Give each card a unique `id` (`#set-printer`, `#set-display`, `#set-aimodel`…), point each sub-link at its own anchor, observe per-item, and set `aria-current="true"` on the single in-view item. This delivers the navigation the design implies.
2. **Make it honestly per-group.** Drop the sub-items to plain non-link text under one clickable group heading per `#grp-*`; set `aria-current` on the one active group heading. Keep the mobile group labels visible (don't `display:none` them) so the grouping survives.
Either way, never have two `aria-current` items simultaneously.

---

### [UX-004] — Minor — Pattern / Performance — 1.27 MB / 1254×1254 avatar PNG renders at 32px (topbar) and 28px (chat)

**Evidence**
`/assets/kim-avatar.png` is **1254×1254 px, 1,298,074 bytes** (measured live: `naturalDims {1254,1254}`, `decodedBodySize 1298074`). It renders via CSS `background:…center/cover` at `.kc-logo` 32×32 and `.kc-ava` 28×28. It is committed twice in the repo (`frontend/src/assets/` and the built `src/kimcad/web/assets/`), each 1.27 MB — the single largest asset in the bundle.

**Why this matters**
The browser decodes a ~1.5-megapixel image to paint a 32-px circle (~1500× the pixels needed), and 1.3 MB ships on first load (later cached, `transferSize 0` on repeat). For an offline-first desktop app the network cost is muted, but the decode/memory cost and the repo/installer bloat are real, and it's a Minor only because it's not user-visibly broken.

**Blast radius**
- Adjacent code: `styles.css` `.kc-logo` / `.kc-ava`; the two committed PNGs; the build pipeline that copies assets into `src/kimcad/web/assets/`.
- User-facing: imperceptible visually; affects bundle/installer size and first-paint decode.
- Migration: none (asset swap).
- Tests to update: none known.
- Fix path: ship a 64×64 (2× for retina at 32px) optimized PNG/WebP — a few KB — and let the build copy that. Optionally an `<img srcset>` if larger renders appear later.

---

### [UX-005] — Minor — Hygiene — UTF-8 BOM atop FirstRunWizard.tsx and SettingsPanel.tsx

**Evidence**
`head -c 3` on both files returns `ef bb bf` (a UTF-8 BOM); Topbar.tsx and ChatPanel.tsx are clean (`69 6d 70` = "imp"). Introduced by the restored designer pass. Build and vitest pass, so no runtime effect.

**Why this matters**
Harmless today but non-idiomatic for TS source; a stray BOM can confuse some tooling/diffs and is the kind of thing that quietly spreads. Strip in remediation.

**Fix path:** re-save both files as UTF-8 without BOM; add an editorconfig/lint guard if the team wants to prevent recurrence.

---

### [UX-006] — Minor — Responsive / IA — Settings section-nav loses its group headings on mobile

**Evidence**
`@media (max-width:860px)`: `.kc-set-navgroup { display: contents }` and `.kc-set-navgroup > span { display: none }`. Live at 375px: `groupLabelDisplay: "none"`, 9 links wrap in a flat row with no "Design defaults / AI / Output & tools / System" context.

**Why this matters**
The grouping is the nav's information scent; removing it on the smallest screens (where orientation matters most) leaves an undifferentiated pill cluster. Combined with UX-003's dual-highlight, mobile users get the least context and the most ambiguity.

**Fix path:** keep the group labels visible on mobile (e.g. render them as small section dividers in the wrapped row), or collapse the nav into a single-select "Jump to…" control on narrow screens. Resolve alongside UX-003.

---

### [UX-007] — Minor — State — My Designs cards show blank thumbnails despite `has_thumb:true`

**Evidence**
Route: `#/designs`. Screenshot shows several cards with solid black/blank thumbnail areas while others render the part; `/api/designs` reports `has_thumb:true` for entries whose `thumb_url` paints empty.

**Why this matters**
A thumbnail is a card's primary scanning cue; a wall of black cards makes the library hard to scan and looks broken. The `has_thumb:true`-but-blank mismatch suggests a thumbnail-generation or aspect/background issue rather than a missing-state design gap.

**Blast radius**
- Adjacent code: `MyDesigns.tsx` (thumbnail render + fallback); the thumbnail-generation path server-side (`/api/designs/:id/thumb`).
- User-facing: the library grid for any user with designs whose thumbnails failed.
- Fix path: investigate the generation failure; **and** add a designed thumbnail-fallback (object-type icon + name on a tinted tile) so a missing thumb is never a black void. This is also a QA/test gap (no test asserts the fallback).

---

### [UX-008] — Minor — Journey — Stray `demo-gohello` entry in the user's saved designs

**Evidence**
`#/designs` shows a card labeled "demo-gohello ×" among 16 real designs. Looks like leftover demo/seed/test data in the live home directory.

**Why this matters**
Test artifacts in a user-facing library erode the "this is my workspace" feeling and can confuse a first walkthrough. (Likely environment data rather than shipped seed data — confirm which.)

**Fix path:** confirm whether any demo data is seeded by the app on first run; if so, remove it or clearly mark/segregate demo content. If purely local test residue, no code change — but worth verifying the app never ships seed entries into a real user's library.

---

### [UX-009] — Nit — Visual hierarchy — Realistic human-face avatar as the 32px brand mark

**Evidence**
`.kc-logo` is a photoreal face at 32px in the topbar logo slot. (Distinct from UX-004's file-size issue — this is the design choice.)

**Why this matters**
At 32px a detailed face loses legibility as a mark and competes with the "KimCad" wordmark beside it; it also implies a persona ("Kim") the product references only lightly. It's warm and differentiating — a defensible choice — but a simplified/stylized mark (or a higher-contrast crop) would scale better as an identity. Subjective; flag once.

**Fix path:** consider a stylized illustration or a tighter, simplified crop for the mark; keep the photo for larger contexts if the persona is intentional.

---

### [UX-010] — Nit — Copy — Wizard escape + final-step honesty (credit, no defect)

The wizard's escape is consistently "Skip setup," and the final step toggles "You're all set" / "Almost ready" honestly based on live model status. Noting as a credit, not a defect — this is exactly the right restraint.

---

### [UX-011] — Nit — Accessibility — "Saved" status chip is 21px tall (below the 44px touch target)

**Evidence**
Live mobile measure: the topbar "Saved" indicator/button is 21px tall. It doubles as a quiet shortcut to My Designs (the adjacent full-size "My Designs" button is the primary path).

**Why this matters**
Below the 44px touch minimum, but it's a redundant secondary affordance with a 44px sibling, so impact is low. Flag once.

**Fix path:** increase its hit area (padding) to 44px, or treat it as purely a status indicator (non-interactive) since "My Designs" already provides the link.

---

### [UX-012] — Nit — Pattern — Cloud `<details>` disclosure is a good modern choice (credit, with a small note)

**Evidence**
Wizard step 2: "Advanced — cloud speed-ups (optional · local always works)" is a native `<details>`/`<summary>`, collapsed by default, keyboard-operable, revealing the OpenRouter key + model fields on toggle. `open` is bound to the cloud-on state. Verified live.

**Why this matters**
This is exactly the right pattern — progressive disclosure of an advanced, off-by-default, privacy-sensitive feature using a native element (free keyboard + SR support). Credit. Minor note: collapsing the `<details>` after typing a key does not silently discard intent — the source persists the key only if cloud is "on" at finish, which is deliberate and documented. No change required.

---

## States audit matrix

| Component / page | Default | Loading | Empty | Error | Partial | Notes |
|---|---|---|---|---|---|---|
| Landing | ✓ | — | ✓ (resting hints) | ✓ (best-effort chrome degrades silently) | — | Strong |
| FirstRunWizard | ✓ | ✓ (model "Checking…") | ✓ | ✓ (Ollama-down guidance, settings-load failure) | ✓ (download mid-flight) | Excellent honesty |
| Design / Viewport | ✓ | ✓ (phase + elapsed + Cancel) | ✓ ("part will appear here") | ✓ (model_unavailable → Try again) | ✓ (needs_experimental offer) | Best-in-class loading |
| Inspector → Parameters | ✓ | — | ✓ | — | — | Editable locally |
| Inspector → Quality | ✓ | — | ✓ | — | ✓ (warn-gate caution) | Honest gate UX |
| Inspector → Export | ✓ | ✓ (Slicing… + Cancel) | ✓ | ✓ (slice fail note) | ✓ (gate-failed: model still downloadable) | UX-001 here |
| ConnectorStatus | ✓ | ✓ ("Checking…") | ✓ (absent if none) | ✓ (offline/busy/auth/config labels, source) | — | UX-001; non-mock states unverified live |
| My Designs | ✓ | — | ✓ (assumed) | — | ✗ blank thumbs | UX-007/UX-008 |
| Settings | ✓ | ✓ ("Loading your settings…") | — | ✓ ("Couldn't load your settings") | ✓ (independent health/model loads) | UX-003/UX-006 |
| Shortcuts modal | ✓ | — | — | — | — | Focus-trapped, Esc closes |

## Accessibility snapshot

- **Keyboard navigation:** Skip-link present; modals (Wizard, Shortcuts) trap focus, focus-in on open, Esc to close — verified. **Gap:** Inspector tablist has no arrow-key model (UX-002).
- **Focus visibility:** `:focus-visible` rules apply a 2px accent outline with offset (e.g. `.kc-brand:focus-visible`) — visible indicator present.
- **Color contrast:** Sampled AA-clean both themes (light CTA 5.03:1 / lede 4.66:1 / chips 13.67:1; dark CTA 8.54:1 / lede 7.64:1). No AA failures found on text I sampled.
- **Screen-reader labeling:** Decorative avatar is `aria-hidden` inside a labeled button; InfoTips are real `<button aria-label aria-expanded>`; save/status use `role="status"`/`aria-live="polite"`; 0 `<img>` missing alt (all imagery is CSS background). **Gap:** dual `aria-current` in Settings nav (UX-003).
- **Reduced motion:** Respected (2 `prefers-reduced-motion` media blocks).
- **Touch target size:** Most controls 44px (the team clearly targeted it). Exceptions: brand logo 32px (acceptable for a logo), "Saved" chip 21px (UX-011).

## Patterns and systemic observations

- **One root, two findings (UX-002 + UX-003): ARIA attributes are present but their interaction contract isn't fully honored.** Both the tablist (`role="tablist"` without keyboard model) and the section-nav (`aria-current` on a whole group) declare a semantic the behavior doesn't deliver. The team's a11y instincts are clearly strong (skip-link, focus traps, reduced-motion, labeled icon buttons, decorative-image discipline) — this is a finishing-discipline gap on two custom widgets, not a systemic neglect. A shared, APG-correct `<Tabs>` primitive and a "single `aria-current`" lint/test would close both for good.
- **State coverage is a genuine strength** — the matrix above is nearly full. The few gaps (blank thumbnails, non-mock connector states) are isolated, not a missing-states pattern.
- **Honesty is the product's signature** — the copy never overstates ("local always works," "Nothing leaves your machine," the elapsed timer, the warn-gate caution echoed next to the Slice button). Protect this in any copy change (esp. UX-001).

## Appendix: surfaces reviewed

- Routes: `/` (landing, light + dark), `#/designs`, `#/design/46f26d2e3c094b799b3d1d09f7f78017` (workspace), `#/settings`; FirstRunWizard (steps 1–2 + Skip); Shortcuts modal.
- Viewports: 375×812 (mobile), 1280×900 (desktop), and the harness default ~800px.
- Components: Topbar/`.kc-logo`, ChatPanel/`.kc-ava`, Viewport loading overlay, RightPanel Inspector tablist + Parameters/Quality/Export panels, ExportPanel + ConnectorStatus, SettingsPanel + section-nav, FirstRunWizard cloud `<details>`, MyDesigns grid, ShortcutsHelp.
- Live probes: `/api/health`, `/api/connectors`, `/api/options` (29 printers, default `bambu_p2s`, 4 materials), `/api/model-status` (qwen2.5:7b local, running, model+vision present), `/api/settings`, `/api/designs` (16 entries). Contrast sampled via computed styles; tablist/modal keyboard behavior probed via dispatched KeyboardEvents. Console: 0 errors/warnings. Server stopped (ports 8714 + manual 8744 both freed).
