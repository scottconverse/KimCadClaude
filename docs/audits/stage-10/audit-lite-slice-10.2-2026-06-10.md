# Audit Lite — Stage 10 Slice 10.2: direct-print UI (SendPanel) in the SPA
**Date:** 2026-06-10
**Scope:** Uncommitted working-tree changes on top of `8f82662` — `frontend/src/components/SendPanel.tsx` (new) + `SendPanel.test.tsx` (new), `frontend/src/api.ts` (`SendResponse` + `sendDesign`), `api.test.ts` (+3), `ExportPanel.tsx` (mounts SendPanel under a finished slice), `ConnectorStatus.tsx` (comment only), `styles.css` (`.kc-send-*`). Cross-checked server-side against `src/kimcad/webapp.py` (`_handle_send`, `/api/connectors`) and `src/kimcad/printer_connector.py` (reason vocabulary). `src/kimcad/web/assets/*` (committed Vite build output) excluded per instruction.
**Reviewer:** Claude (audit-lite, independent single pass)

## TL;DR
Ship with caveats. The trust rules hold everywhere I could reach them: a send fires only through the app's ConfirmDialog (pinned by test), a simulated send is narrated as a test at every surface (option label, button, dialog, success copy), and the server contract (gate re-check, soft `sent:false` outcomes) is consumed correctly. Two Majors before the slice is done: the live-status poll chain has no cancellation guard (an in-flight status fetch resurrects the chain after unmount or a superseding send — when it bites, the UI shows the *old* connector's live status under the *new* job), and three user-facing doc surfaces still state the browser cannot send. Scoped vitest run: 60/60 green, verified live.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 2
- Minor: 2
- Nit: 1

## Findings

### FINDING-001 Major: Poll chain has no cancellation/generation guard — an in-flight status fetch resurrects it after unmount or a superseding send
**Dimension:** Correctness
**Evidence:** `frontend/src/components/SendPanel.tsx:56-71` and `:84-88`. `stopPoll()` clears only `pollTimer.current`. If `getConnectorStatus` is *in flight* when `stopPoll()` runs (every poll opens a ~5s-cadence fetch window), its `.then` still executes: it calls `setLive(s)` and, while `stillGoing`, assigns `pollTimer.current = setTimeout(...)` — rescheduling the supposedly-stopped chain. Two concrete consequences: (a) **unmount** — `ExportPanel.tsx:67-70` and `:88` unmount SendPanel on every new design *and every re-slice*, so re-slicing while a real job is being followed is a realistic path; the resurrected chain then polls an unmounted component for up to the remaining cap (≤120 polls / ~10 min). (b) **superseding send** — `doSend` calls `stopPoll()` then starts a new chain; if the old chain's fetch resolves after that, its reschedule *overwrites* `pollTimer.current`, orphaning the new chain's timer (now uncancellable) and letting the old chain keep calling `setLive` with the **old connector's status, displayed under the new job's "Job sent to …" banner** (`SendPanel.tsx:166-170`). That last part is an honesty surface: live status attributed to the wrong printer during a real print.
**Why it matters:** The window is narrow (fetch must be in flight at the instant of stop), but when it hits, the wrong-printer status display *persists* — it is not a one-frame glitch — and the unmount leak generates background traffic against the connector for minutes.
**Fix path:** Add a generation ref: `const pollGen = useRef(0)`; increment it in `stopPoll()`; capture `const gen = pollGen.current` at chain start and bail in both `.then` and `.catch` continuation when `gen !== pollGen.current`. Add a fake-timers test: start a real-send follow, unmount (or re-send) while the status promise is pending, resolve it, assert no further `getConnectorStatus` calls.
**Blast radius:** Local to SendPanel; `ConnectorStatus.tsx` has its own one-shot fetch with a `cancelled` flag (correct pattern — copy it). No shared state, no migration. Tests to update: `SendPanel.test.tsx` (new lifecycle case).

### FINDING-002 Major: Three user-facing doc surfaces still say the browser cannot send
**Dimension:** Docs
**Evidence:** `README.md:283` ("Sending to a printer from the browser is a later stage — today the web UI is status + slice + download; the CLI and MCP send."), `ARCHITECTURE.md:160` ("**Sending to a printer from the browser is a later stage**"), `frontend/README.md:26` ("browser send is a later stage; the CLI and MCP send today."). All three are user-guide/architecture statements that are false in this tree — the SPA now sends. (ROADMAP/CHANGELOG status lines, and README:31's "Next up: a direct-print UI (Stage 10)", move at the stage tag per repo convention and are **not** flagged.)
**Why it matters:** Doc drift on changed observable behavior; these were the exact lines DOC-401 (Stage 4) added to *prevent* an overclaim — left as-is they now underclaim and contradict the shipped UI.
**Fix path:** Update the three lines in this slice: browser send exists, gated by the same confirm + printability rules; CLI/MCP remain alternatives.
**Blast radius:** Doc-only; the Stage-4 audit reports quoting the old lines are historical records and stay as-is.

### FINDING-003 Minor: When every connector is unconfigured, the panel shows a blank select and a disabled button with no inline explanation
**Dimension:** UX
**Evidence:** `SendPanel.tsx:36-38` — zero configured connectors leaves `chosen === ''`, which matches no `<option>` (controlled select renders with nothing selected); the button (`:124`) is disabled with the generic label "Send to printer". The only explanation ("not set up yet — see Settings") lives inside the dropdown options (`:115`), visible only after opening it. Reachable: `/api/connectors` (webapp.py:838-857) serves whatever the user's config lists; a config with only real, key-less connectors (the shipped OctoPrint template state, mock removed) produces exactly this.
**Why it matters:** A dead-looking control with no stated reason is the kind of silent dead-end the rest of this panel is careful to avoid.
**Fix path:** When `usable.length === 0`, render a placeholder option ("No connection set up yet") and a one-line note pointing at Settings — mirroring the existing unconfigured-option copy. Add the all-unconfigured render to `SendPanel.test.tsx`.

### FINDING-004 Minor: Transport-error message is not announced (missing `role="status"`)
**Dimension:** UX (a11y)
**Evidence:** `SendPanel.tsx:149` — the catch-path error `<p>` has no live-region role, while the soft not-sent note (`:152`) and the success block (`:160`) both carry `role="status"`. A network/500 failure after confirming a send updates silently for screen-reader users.
**Why it matters:** The failure path is precisely where an unannounced update hurts most — the user confirmed a print and hears nothing.
**Fix path:** Add `role="status"` to the error paragraph. (Rest of a11y checks out: ConfirmDialog is a focus-trapped `alertdialog` with Escape-cancel and focus on the safe action — `ConfirmDialog.tsx:24-52`; select is labeled; select + button are natively keyboard-reachable.)

### FINDING-005 Nit: Comments overstate a server-side confirm requirement
**Dimension:** Docs (inline)
**Evidence:** `SendPanel.tsx:17-18` and `api.ts` (sendDesign header) say the server "requires confirm server-side". The server does not check a confirm field: `_handle_send` (webapp.py:1302-1304, 1338) treats the POST itself as the per-send confirmation and passes `confirm=True` unconditionally; the `NotConfirmed` guard (`printer_connector.py:79-82`) is an internal API-misuse trap, not a wire-level check. What the server *does* re-check is the gate verdict — that part of the comment is accurate.
**Why it matters:** A future reader could assume a wire-level confirm exists and weaken the UI dialog. The actual contract: the dialog is the *only* user-confirm in the browser path.
**Fix path:** Reword both comments to "the POST is the per-send confirmation; the server independently re-checks the printability gate".

## What's working
- **Trust rules are pinned, not just implemented.** `SendPanel.test.tsx:73-87` proves cancel-sends-nothing and confirm-sends-once; `:55-62` pins the simulated labeling at option, button, and helper-note level; the success copy for a simulated send says "No hardware ran" and never "print" (`SendPanel.tsx:163`, verified live in demo mode per the dev log and consistent with the code).
- **Server contract consumed correctly.** Cross-checked `_handle_send` (webapp.py:1302-1369): soft outcomes arrive as HTTP 200 `sent:false` + `reason` + `note`, and `sendDesign` passes them through without throwing (api.ts; pinned at `api.test.ts` "soft not-sent outcome"). `gate_failed` arrives with a complete server note; the UI's empty-string hint for it (`SendPanel.tsx:101`) correctly defers to that note.
- **Reason map matches the server vocabulary.** Reasons reachable on `/api/send` soft-failures: `gate_failed`, `config`, `unknown`, `auth`, `offline`, `busy`, `bad_response`, `error` (printer_connector.py:48-65 + webapp.py:1323, 1339-1346). The hint map covers the four actionable ones + gate_failed; the unmapped three fall through to the server's `user_message`, which is the designed behavior — nothing mismapped.
- **Picker defaulting is defensive in the right place.** The server's `default` is `names[0]` regardless of configuredness (webapp.py:857, despite its own comment — see watch item); the UI independently filters to configured connectors and falls back to the first usable one (`SendPanel.tsx:36-38`), so a bad default cannot select an unsendable connector.
- **Poll math is as advertised.** `pollStatus(chosen, 120)` at 5s → 121 fetches ≈ 10 min cap, stops when the state settles; cleared on unmount via the `useEffect(() => stopPoll)` cleanup for the common (no-fetch-in-flight) case.
- **Runtime verified.** `node node_modules\vitest\vitest.mjs run src/components/SendPanel.test.tsx src/api.test.ts` → **2 files, 60/60 passed** (run by this auditor, 2026-06-10).

## Watch items
1. **Server `/api/connectors` default contradicts its own comment** (pre-existing, NOT this diff): webapp.py:855-857 says "default = the first configured connector" but returns `names[0]` unconditionally — an unconfigured first entry becomes `default`. The UI defends against it; fix server-side when `/api/connectors` is next touched.
2. **One missed status poll permanently ends the live follow** (`SendPanel.tsx:66-68`): deliberate and commented, but a single transient blip during a 10-minute follow freezes the label at the last known state. Consider one retry before giving up when revisiting FINDING-001.
3. **MCP/CLI send paths** share `_handle_send`'s "POST = confirm" contract; when Stage 10's Bambu-native connector lands, re-verify the confirm story holds for non-browser clients too.

## Escalation recommendation
**No escalation.** Zero Blockers/Criticals; both Majors are local, one-sitting fixes (a generation ref + three doc lines). This is the audit-lite profile — fix to 0/0/0/0/0 per house standard and proceed within Stage 10. The audit-team pass belongs at the stage gate.
