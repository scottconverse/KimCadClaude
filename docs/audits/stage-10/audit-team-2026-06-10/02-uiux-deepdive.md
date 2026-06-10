# Senior UI/UX Designer — Stage 10 deep-dive

**Date:** 2026-06-10 · **Commit:** `d9495a8` (main) · **Scope:** the Stage 10 diff (`253b08c..d9495a8`):
SendPanel direct-print UI + styles, the wizard's model-download flow, the Settings vision row,
and the connector-picker copy fed by the Bambu templates.

**Method — the visual check was performed live.** Demo server on port 8731, driven with a real
Chrome browser (clicks, typing, screenshots, JS probes). Exercised: landing → Try chip → design →
slice → SendPanel (picker incl. disabled bambu entries, confirm dialog, mock send, narration);
the gate-failed journey (`demo:gatefail x` → experimental offer accepted → send area); the
first-run wizard (flag cleared) incl. the model-download step **with a live progress run**
(model-status/pull responses stubbed in-page via a fetch patch, since this box has both models —
the panel rendered real progress rows, 16% → 39%, against the stubbed stream); the recap step
mid-download; Settings AI-model card; the all-unconfigured SendPanel state (connectors response
stubbed); a soft not-sent outcome (send response stubbed). Desktop (1568px) **and** 375px (the
window manager refused a true resize, so the 375px pass used a same-origin 375×695 iframe of the
live app — media queries apply correctly inside it; screenshots taken of both widths). Focus
order, the dialog focus trap, live-region contents, contrast ratios, and touch-target sizes were
measured in-page. States I could not reach (a real printer job's live-status line) are assessed
from component source and marked code-inferred. The per-slice audit-lites and the walkthrough
report were read first; fixed findings are not re-reported. No product source modified; no probe
artifacts written to disk (browser-only); server killed at the end.

---

## First impressions (recorded before analysis)

Arriving cold at the landing: the headline ("What do you want to make today?"), one obvious
input, three Try chips, and a 1-2-3 journey line — within five seconds you know what the product
does and what to do first. The wizard's plain-words register ("Most first prints are ready in
under 15 minutes", "optional · local always works") is genuinely warm without being cute. The
new SendPanel inherits that voice: "test connection — no real printer", "No hardware ran."
Nothing in the new surfaces feels adversarial. What broke the spell, both times, was following
the product's own signposts: every road sign in the new send flow points at Settings, and
Settings doesn't contain the thing the signs promise.

---

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---------|----------|-------|-------|-----|
| 0 | 0 | 2 | 4 | 1 |

---

## Findings

### UX-1001 — Major — Journey / Copy — Every setup pointer in the send flow dead-ends: Settings has no printer-connection section

**Evidence (verified live + source):** The new send flow tells the user five times that printer
connections are set up "in Settings":

- `frontend/src/components/SendPanel.tsx:124` — picker option: *"(not set up yet — see Settings)"*
- `SendPanel.tsx:141` — *"Connect a real printer in Settings to print directly."*
- `SendPanel.tsx:148` — *"None of these printer connections is set up yet — finish setup in Settings."*
- `SendPanel.tsx:107` — auth hint: *"Check the connection's key or access code in Settings."*
- `SendPanel.tsx:108` — config hint: *"Finish setting this connection up in Settings."*
- (plus the wizard's direct-printing step, `FirstRunWizard.tsx:531`: *"Set up sending jobs from
  KimCad in Settings, when you're ready."* — pre-Stage-10 copy, same destination)

I opened Settings on the running app: it contains Printer & material (slicing profile defaults),
Units, and the AI-model card. **There is no printer-connection section, no IP/serial/access-code
field, no API-key field** (`SettingsPanel.tsx` — a full-text search for connector/connection/
address/access-code surfaces nothing). The real setup path is `config.yaml` + environment
variables, documented only in the README/troubleshooting.

Meanwhile the server already knows exactly what's missing per connector — verified live:
`GET /api/connector-status/bambu_p2s` → *"The 'bambu_p2s' connection has no printer address (IP)
configured."*; octoprint → *"needs an API key … See the README's send-to-printer setup."* The
picker flattens all of that to the generic "not set up yet — see Settings." (This is the
walkthrough's observation, weighed here: it is not polish, it is part of a Major journey gap.)

**Why this matters:** A user who wants the product's flagship new capability follows "see
Settings," lands on a page whose first card is literally titled **"Default printer — Bambu Lab
P2S"** — a confusable near-miss (it's the *checking/slicing profile*, not a connection). The
plausible outcome: they confirm "Bambu Lab P2S" is selected, return to the picker, find it still
disabled, and conclude the feature is broken. The auth hint is the sharpest case — after a failed
real send it directs the user to check *"the connection's key or access code in Settings"*, a
field that does not exist anywhere in the UI. The product's trust-first voice makes wrong
directions costlier: this product has taught users that its words are load-bearing.

**Fix path (pick one deliberately — this is a product decision, not just copy):**
1. *Copy-only (smallest honest fix):* point at the real venue. Picker option: `(not set up yet)`;
   note: *"Printer connections are set up in KimCad's config file — the README's
   send-to-printer section walks through it."* Auth hint: *"The connection's key or access code
   looks wrong — see the README's send-to-printer setup."* And surface the server's per-piece
   note: the picker already has `/api/connector-status/<name>`; show the diagnosis (e.g. as the
   note under the picker when a disabled connector is selected, or a `title` tooltip) so "what's
   missing" costs zero round-trips.
2. *Product fix (Stage 11 candidate):* an actual "Printer connections" card in Settings (read
   the templates, edit address/serial, env-var name for the secret). The five copy sites then
   become true.

**Blast radius:**
- Adjacent copy: the five SendPanel strings above + `FirstRunWizard.tsx:531`; `docs/troubleshooting.md`'s
  bambulabs-api entry says the picker "tells you which piece is missing" — true only via the API/CLI
  today, so option 1 also makes that line fully true in the UI.
- User-facing: every user who tries direct print with a real (unconfigured) printer — the exact
  Stage-11-beta persona (Kim).
- Migration: none for option 1; option 2 needs settings-endpoint write paths for connector fields.
- Tests to update: `SendPanel.test.tsx` pins the current label text (the "honest labels" cases) —
  copy changes will touch those assertions.
- Related findings: UX-1004 (raw config keys in the same picker).

---

### UX-1002 — Major — Journey / State — The in-app model download has no life outside the wizard: the recap says "You're all set" mid-download, and closing the one-shot wizard orphans the only progress surface

**Evidence (verified live, both widths):** With the design model present and the vision model
missing (the common shipped-default case), I started the in-app download on the wizard's model
step, then clicked through to the recap. The recap renders the green badge and **"You're all
set — KimCad is ready to design"** with recap rows Model / Printer / Direct printing — **zero
mention of the multi-GB download the user started sixty seconds earlier.** Cause:
`FirstRunWizard.tsx:230-231` — `modelOk` checks only `running && model_present`; the
slice-10.4 audit fix (UX-001, the `pullActive ? 'downloading now…'` branch at
`FirstRunWizard.tsx:574-578`) lives inside `{!modelOk && …}` and never renders in the
vision-only-gap case.

Downstream of that recap:
- "Start designing" closes the wizard; the wizard is **one-shot** (`App.tsx:86-99`,
  `kc-first-run-done`) — there is no way to reopen it, so the progress UI is gone for good.
  The server-side pull keeps running, invisibly.
- Settings is the natural place to look, and its new vision row mid-pull says *"not
  downloaded — photos and sketches won't work yet. Run `ollama pull qwen2.5vl:3b` (or use the
  setup wizard's download), then check again"* (`SettingsPanel.tsx:266-290`, copy at `:278`) —
  it tells the user to start a **competing manual pull** of a model that is already downloading,
  and points at a wizard they can no longer reach. The row never consults
  `/api/model-pull/progress`.

**Why this matters:** The welcome step promises photos and sketches as first-class on-ramps; the
user does the right thing (clicks Download); the product then tells them everything is done,
loses the thread entirely, and — if they go looking — hands them instructions that contradict
the download in flight. Exposure is high: clicking through a wizard takes seconds, a ~3 GB pull
takes many minutes, so *most* users who take the in-app download will close the wizard mid-pull.

**Fix path:**
1. Recap: when `pullActive` (or any `pull.models[*]` non-terminal), add a quiet line to the
   recap — *"The photo & sketch reader is still downloading — designing in words works now.
   It finishes on its own; Settings shows when it's ready."* (and consider demoting the headline
   to "You're nearly set" only if the *design* model is among the missing).
2. Settings vision row: read `/api/model-pull/progress` once on mount (and on "check again");
   when a pull is running, render *"downloading now — N%"* instead of the manual instruction.
   This also makes the row's claim measured rather than assumed, matching the product's rules.
3. Drop "(or use the setup wizard's download)" from the Settings copy, or make it true by giving
   Settings its own Download button reusing `startModelPull` (the endpoint is already
   idempotent — a no-op when nothing is missing).

**Blast radius:**
- Adjacent code: `FirstRunWizard.tsx` recap block (`:538-603`), `SettingsPanel.tsx` vision row;
  `api.ts` already exports `getModelPullProgress` — no new endpoint needed.
- Shared state: none (the pull job is server-side and already queryable).
- User-facing: first-run users on the default install (vision model absent) — the main onboarding
  cohort.
- Tests to update: `FirstRunWizard.test.tsx` (a vision-gap-mid-pull recap case),
  `SettingsPanel.test.tsx` (pull-in-flight row case — currently has no vision-row pull coverage).
- Related findings: slice-10.4 audit-lite UX-001 (same root, fixed only for the design-model
  branch); UX-1005 (the "Ready" pill that also ignores vision).

---

### UX-1003 — Minor — Accessibility — Closing the confirm dialog drops focus to `<body>` (no focus restore)

**Evidence (verified live):** With focus on "Send test job", opening the dialog moves focus to
"Keep working" (correct — safe action first, `ConfirmDialog.tsx:24-25`); dismissing it leaves
`document.activeElement === document.body`. The component has no focus-restore on unmount
(`ConfirmDialog.tsx` — the cleanup only removes the key listener). A keyboard or screen-reader
user who cancels is dumped to the top of the document and must Tab back through the whole
workspace to reach the send controls again; after a *confirmed* send the trigger button is
disabled while sending, so focus is lost on that path too (the `role="status"` result is at
least announced).

**Fix path:** Capture `document.activeElement` on mount, restore it (if still connected) on
unmount; when the trigger is disabled, fall back to the panel's select. ~6 lines in
`ConfirmDialog.tsx`, fixes every call site at once.

**Blast radius:** All ConfirmDialog call sites (SendPanel send, App.tsx new-design confirm),
plus the same missing-restore pattern in `ShortcutsHelp`/`FirstRunWizard` overlays if the team
wants symmetry (lower stakes there — those close into a fresh context by design). Tests:
one focus-restore case in a ConfirmDialog or SendPanel test.

---

### UX-1004 — Minor — Copy / IA — The picker shows raw config keys ("bambu_p2s") in a plain-words product

**Evidence (verified live):** The connection picker reads `mock` / `octoprint` / `bambu_p2s` /
`bambu_a1` — raw YAML keys — while the *Printer* dropdown four lines above says "Bambu Lab P2S",
and the printability report says "Bambu Lab P2S build volume". The confirm dialog and success
narration then quote the slug back: *"Start this print on "bambu_p2s"?"*. `/api/connectors`
(webapp.py) exposes only `name`/`configured`/`simulated` — no display name — so the UI has
nothing friendlier to show.

**Why this matters:** Register clash on adjacent controls ("Bambu Lab P2S" vs "bambu_p2s") reads
as two different systems; for the product's stated non-technical persona, underscore-slugs are
system-speak in the one place that drives physical hardware.

**Fix path:** Add an optional `label` to the connector config/template and `/api/connectors`
(template ships `label: "Bambu Lab P2S (direct)"` etc.); UI falls back to the key. Keep the key
in the confirm dialog as a secondary detail if disambiguation matters.

**Blast radius:** `config/default.yaml` templates, `connectors.py`/`webapp.py` (one field),
`SendPanel.tsx`, `SendPanel.test.tsx` label pins, README's connector table. CLI `--send` keys
stay keys.

---

### UX-1005 — Minor — State / Copy — The wizard model card's pill says "Ready" while the same card offers (or runs) the vision download

**Evidence (verified live):** With the design model present and vision missing, the card shows
the green pill **"● Ready"** (`modelLabel`/`modelTone`, `FirstRunWizard.tsx:26-35`, ignore
`vision_present`) directly above *"Photos and sketches need one more download…"* and, once
started, *"downloading… 17%"*. Two honest statements with one dishonest summary between them —
"Ready" + a download CTA in the same card makes a user wonder which to believe.

**Fix path:** When `vision_present === false`, label the pill "Ready for words" (tone stays ok),
or "Ready · 1 download left". One mapper change; the recap's `modelOk` is UX-1002's business and
should stay design-model-based.

**Blast radius:** `FirstRunWizard.test.tsx` label pins; Settings' pill says "Running" (a
different, honest claim) and needs no change.

---

### UX-1006 — Minor (code-inferred; hardware-gated) — After a real send, the live line shows amber "Busy — printing" for the user's own job

**Evidence (source):** `SendPanel.tsx:180-192` renders *"Job sent to X — the printer is
starting."* then the live line from `connectorLabel`/`connectorTone`
(`connectorStatus.ts:14-15,25`): a printing state maps to tone `warn` (amber dot) and the label
**"Busy — printing"**. For the job the user just started, "Busy" connotes *someone else's* job
and amber connotes *attention needed* — directly under a green-toned success sentence. Not
reachable without hardware (mock sends don't poll), so this is a Stage-11-beta first-session
paper cut waiting in the code.

**Fix path:** In the post-send context only, prefer a neutral/ok presentation: "Printing — N%"
(the status payload already carries progress for OctoPrint/Bambu) or at minimum "Printing" with
the pass tone while `result.sent` is the current job. Keep "Busy" for the *pre-send* status
surfaces where it genuinely means occupied.

**Blast radius:** `connectorStatus.ts` mappers are shared with `ConnectorStatus.tsx` (the Export
card header) — scope the change to SendPanel's call site (a small local mapper or a flag) rather
than the shared mapper, so the header's pre-send semantics stay. Tests: `SendPanel.test.tsx`
poll-lifecycle case asserts the label text.

---

### UX-1007 — Nit — Visual hierarchy — On a gate-failed design, the Export card leads with a green "mock — Ready · simulated" line directly above "this part didn't pass the printability check"

Verified live on `demo:gatefail x`: the card's first line is a green-dotted connection-readiness
status; the second paragraph explains the part can't be sliced. Two different "ready" subjects
(the connection vs. the part) stacked in one card; the green dot is the first thing the eye
hits in an all-red context. Pre-existing component placement (ConnectorStatus, Stage 6) but the
juxtaposition is new now that the card is the home of send. Consider suppressing the connection
status line when the gate verdict blocks slicing — it answers a question nobody can act on yet.

---

## What's working (credit where due — all verified live unless noted)

- **The trust rules hold at every surface I could reach.** The send fires only from the app's
  own confirm dialog; cancel sends nothing; the simulated connection is labeled a test at the
  option, button, dialog, and narration ("Test job accepted by "mock" — the send path works.
  **No hardware ran.**"). This is the product's signature move and the new panel executes it.
- **The gate-failed journey has no dead end and no false affordance.** No slice button, no send
  panel, an explanation in plain words, and the STL download named as the inspect path — with the
  server independently refusing (`POST /api/slice` soft-fails), so the UI's restraint is honest
  rather than cosmetic.
- **The all-unconfigured state explains itself** (slice-10.2 FINDING-003 fix verified): visible
  note, disabled button, download named as the always-works fallback. No dead-looking control
  without a stated reason.
- **The coarse live region is the right screen-reader design** (slice-10.4 A11Y-001 fix verified
  live): during an active pull the sr-only `role="status"` node reads "downloading qwen2.5vl:3b" —
  status words only, a handful of changes per download — while the visible rows carry the 1 Hz
  percent un-live. Textbook.
- **The soft not-sent outcome is a model error state:** typed note + reason-specific next step +
  "Your print file is still downloadable above", in a `role="status"` region (slice-10.2
  FINDING-004 fix verified). Failure narrated as a fork in the road, not a wall.
- **The honest intermediate download state** — "Designing in words works now — the photo & sketch
  reader is still downloading." — is exactly the right call on the model step (which is what makes
  its absence from the recap, UX-1002, stand out).
- **375px holds up.** SendPanel stacks cleanly (select 296×44, button 105×44 — both meet the
  44px touch floor), the confirm dialog is comfortable, the wizard's rail collapses to a chip
  grid, progress rows wrap without overflow (no horizontal scroll measured anywhere).
- **Contrast is AA across the new styles, measured:** accent button 5.03:1, muted notes 5.14:1,
  error text 5.59:1, field labels 5.14:1.
- **Focus discipline in the dialog itself is right:** `role="alertdialog"`, focus starts on the
  safe action, Tab is trapped (and the wizard's trap keeps the action line mounted through
  re-checks per UX-A-001). Escape-cancel verified at the handler level. Reduced-motion is
  honored globally (`styles.css:849`).
- **Picker defaulting is defensive:** with an unconfigured server default, the UI selects the
  first *configured* connector, and with none configured it still shows a value instead of a
  blank control.
- Console: no errors observed during my session (tracking started post-load; the walkthrough's
  full-session clean-console result stands).

---

## Cross-cutting note for the orchestrator

UX-1001 and UX-1002 share one root: **Stage 10 built new capabilities whose management surfaces
don't exist yet, and the copy papers over the gap by pointing at Settings/wizard anyway.** The
cheapest coordinated fix is a copy pass that only promises venues that exist (README/config for
connections; a progress-aware Settings vision row) — with the real Settings surfaces as a named
Stage-11 item. If the team fixes only two things from this report, fix those two before the
beta at Kim's: both bite the exact persona the beta is for, in their first hour.

## Cleanup

Demo server (port 8731) killed; no probe artifacts on disk; `git status --short` shows only the
audit output directory (plus the pre-existing untracked walkthrough report dir).
