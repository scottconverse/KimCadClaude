# Documentation Deep-Dive — Stage 10 gate (audit-team 2026-06-10)

**Role:** Technical Writer (AUDIT-ONLY — no doc-rewrites produced)
**Scope:** the Stage 10 diff's documentation surface (`253b08c..d9495a8`): README's Bambu setup
note + connector table + CLI `--send` bullet + reason-vocabulary table; `docs/troubleshooting.md`'s
two new entries; ARCHITECTURE.md's new module rows + web-layer narrative; `config/default.yaml`'s
bambu template comments; `pyproject.toml`'s `[bambu]` extra; `frontend/README.md`; the
wizard/Settings/SendPanel user-facing copy read as documentation; `docs/README.md` index currency;
plus a repo-wide hunt for claims contradicted by Stage 10 behavior.
**Method:** every doc claim paired with the code that proves or disproves it (file:line cited).
Cross-checked against the four slice audit-lites (`docs/audits/stage-10/audit-lite-slice-10.*.md`)
and the live walkthrough (`docs/audits/walkthrough-stage-10-2026-06-10/WALKTHROUGH-REPORT.md`) so
already-fixed findings are not re-reported. Product tree untouched; `git status --short` shows only
the untracked audit output directories.

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---------|----------|-------|-------|-----|
| 0 | 0 | 3 | 3 | 2 |

---

## Findings

### DOC-1001 — Major — Accuracy / Onboarding — App copy sends users to **Settings** to set up a printer connection, but Settings has no connection surface at all

**Evidence:**
- `frontend/src/components/SendPanel.tsx:124` — disabled picker option: `(not set up yet — see Settings)`
- `SendPanel.tsx:141` — "Connect a real printer in Settings to print directly."
- `SendPanel.tsx:148` — "None of these printer connections is set up yet — finish setup in Settings."
- `SendPanel.tsx:107-108` — `reasonHint`: `auth: 'Check the connection's key or access code in Settings.'`, `config: 'Finish setting this connection up in Settings.'`
- `frontend/src/components/FirstRunWizard.tsx:531` — "Set up sending jobs from KimCad in Settings, when you're ready." and `:599` — recap "Set up later in Settings"
- **The contradiction:** `SettingsPanel.tsx` contains no printer-*connection* section — its only printer content is the "Printer & material" *defaults* card (`SettingsPanel.tsx:164-176`, which printer profile to validate against). Connector setup actually happens in `config/default.yaml` (`connectors:` section) plus an environment variable — exactly as README:265-274 and `docs/troubleshooting.md:86-94` teach, and as the credential posture *requires*: "A connection's credential is always read from an **environment variable** … never stored in config and never logged" (README:276-277; enforced at `src/kimcad/connectors.py:150-157`). The `auth` hint's "check the connection's key … in Settings" is therefore not just a dead-end but a direct contradiction of the documented secret-handling model — there is no key in Settings and never can be under the current posture.

**Why this matters:** The first-time user with a Bambu printer follows the in-app pointer — picker says "see Settings" — opens Settings, and finds nothing about connections. The actual fix (edit `config/default.yaml`, set the env var) is documented only in README/troubleshooting, which the pointer never names. Compounding it: inside the SPA the *per-piece* diagnosis ("no printer address (IP) configured", "needs the optional bambulabs-api package", "needs its LAN access code" — `connectors.py:131-157`) is effectively unreachable. `GET /api/connectors` returns only `name`/`simulated`/`configured` (`webapp.py:852-859`); the detailed note travels on `/api/connector-status/<name>` (`webapp.py:1341`), which the UI requests only for the *default* connector (`ConnectorStatus.tsx` — and the default is `mock`) or after a successful real send (`SendPanel.tsx:97`). A disabled option can never be sent, so the user can never surface the reason in-app. The walkthrough logged the generic label as an observation for the UX lane (`WALKTHROUGH-REPORT.md:78-84`); the docs-side consequence is that `docs/troubleshooting.md:93-94`'s claim "stays listed as 'not set up yet' **and tells you which piece is missing**" is true only at the CLI / raw-API level, not in the app the sentence is describing.

**Blast radius:**
- Adjacent copy: six call-outs across two components (lines above) repeat the pointer; the wizard's two were pre-existing (Stage 8.5 MS-4) but the dead-end only became load-bearing when Stage 10 shipped browser send.
- Docs that stay correct: README:265-274 and troubleshooting:86-94 teach the real path — the fix is to make the app copy agree with them (point at the README/config file, or build the Settings surface the copy imagines — a product decision).
- Related findings: DOC-1004 (config comment overstating the picker), DOC-1008 (the troubleshooting heading's surface); walkthrough observation §"Observation (not a finding)".
- Tests to update: `SendPanel.test.tsx` pins the option label text (slice 10.2 tests) — copy changes will touch those assertions.

**Fix path:** Recommend either (a) reword the six strings to name the real venue — e.g. "not set up yet — see the README's *Send to a printer* setup (config/default.yaml + an environment variable)" — and change the `auth` hint to name the env var rather than Settings; or (b) if a Settings connections panel is planned for Stage 11's installer story, ship the copy change now and the panel later. Surfacing `/api/connector-status`'s `note` on the disabled options (title/tooltip or a line under the picker) would also make troubleshooting's "tells you which piece is missing" true in-app.

---

### DOC-1002 — Major — Completeness / Architecture — ARCHITECTURE.md is declared "the authoritative endpoint list" but omits Stage 10's two new endpoints

**Evidence:** `frontend/README.md:23-25` — "the repo-root `ARCHITECTURE.md` is the authoritative endpoint list (it now spans **Stage 5–8.5 additions** …)". ARCHITECTURE.md's web-layer narrative has per-stage endpoint paragraphs ("Stage 8.5 additions" :170-178, "Stage 9 additions" :180-188) and the Stage-10-updated send paragraph (:162-165), but `POST /api/model-pull` and `GET /api/model-pull/progress` — both new in this diff, live at `webapp.py:1059` and `webapp.py:835` and called by the wizard (`frontend/src/api.ts` `startModelPull`/`getModelPullProgress`) — appear **nowhere** in ARCHITECTURE.md (grep: zero hits for `model-pull`). The new `model_pull.py` *module* row (:110) describes the job object but never names the routes. frontend/README's "spans Stage 5–8.5 additions" is also now two stages stale on its own terms (the file's *other* sentence was updated for Stage 10 send in this same diff — the seam was touched and the stale half left).

**Why this matters:** The new-team-member persona is told exactly one place is authoritative for the SPA↔server contract; that place is now missing the two endpoints the first-run wizard depends on. The repo's own discipline (every prior stage got its endpoint paragraph) makes the omission read as "these routes don't exist" rather than "docs lag."

**Blast radius:**
- ARCHITECTURE.md web-layer section (:150-188) — needs a Stage 10 sentence/paragraph: the two model-pull routes (loopback-only, fixed list, demo-mode 400 `not_local`) and that SendPanel consumes `/api/connectors` + `/api/connector-status` + `/api/send`.
- `frontend/README.md:23` — "Stage 5–8.5" phrasing.
- Related findings: none — the module-table row itself is accurate (verified against `model_pull.py`: loopback-only `is_loopback_url` :46-55, disk pre-check :113-132, idempotent start :104-106, fixed server-side list `webapp.py:1134`).

**Fix path:** Add a "Stage 10 additions" paragraph alongside the Stage 8.5/9 ones naming both routes and their guards; update frontend/README's span phrasing to "Stage 5–10".

---

### DOC-1003 — Major — Accuracy / Release notes — The standing promise "a true G-code toolpath/layer viewer is scheduled for Stage 10's direct-print UI" dangles: Stage 10 is complete and shipped no viewer

**Evidence:** `CHANGELOG.md:132` — "(A true G-code toolpath/layer viewer is scheduled for Stage 10's direct-print UI.)" Same promise at `HANDOFF.md:43-44` ("A true G-code layer viewer is deliberately deferred to Stage 10's direct-print UI") and `docs/stage-8.5-usability-plan.md:128` ("that's a large feature belonging to **Stage 10's direct-print UI**"). Against reality: ROADMAP's Stage 10 scope (`ROADMAP.md:293-302`) never lists a viewer (direct-print UI, Bambu connector, first-run wizard only), and none of the four Stage 10 slices built one (10.1 registry flatten, 10.2 SendPanel, 10.3 bambu connector, 10.4 model pulls — per the slice audit-lites and the diff itself). The deferral chain from Stage 8.5 was never re-homed when Stage 10's actual scope was planned.

**Why this matters:** A returning user who read the Stage 8.5 release notes was told the layer viewer arrives with Stage 10. When the `stage-10` tag lands, CHANGELOG:132 becomes retroactively false — the classic trust-burning moment the repo's honesty discipline exists to prevent. This is the one *new* item the tag-time package must absorb beyond the routine status moves (see the tag-time section below).

**Blast radius:**
- `CHANGELOG.md:132` is the live release-notes surface; the new Stage 10 entry should state explicitly where the viewer went (re-scheduled to Stage 11? post-beta? dropped with rationale?) — silence would leave the promise dangling forever.
- `HANDOFF.md:43-44` sits inside the fenced HISTORICAL narrative (disclaimer at HANDOFF.md:11-14), and `stage-8.5-usability-plan.md` is indexed as historical in `docs/README.md:20-26` — lower priority, but HANDOFF is "a living handoff doc" by the repo's own prior ruling (slice-10.1 audit DOC-003), so a one-line past-tense note there is cheap insurance.
- ROADMAP needs the viewer placed *somewhere* (or an explicit drop) so the promise has a current home.
- Related findings: tag-time package (below).

**Fix path:** In the tag-time CHANGELOG Stage 10 entry, one sentence: "the G-code layer viewer once pencilled for this stage moved to <X> / was descoped because <Y>." Mirror in ROADMAP (add to a stage or a descope note) and optionally annotate HANDOFF:43.

---

### DOC-1004 — Minor — Accuracy — `config/default.yaml`'s bambu comment overstates what the send picker shows: "lists them disabled **with the reason**"

**Evidence:** `config/default.yaml:120-121` — "These ship visible-but-unconfigured: the app's send picker lists them disabled **with the reason** until you fill them in." The picker actually renders the one generic suffix `(not set up yet — see Settings)` for every unconfigured connector (`SendPanel.tsx:124`); the *reason* (missing IP vs serial vs access code vs package — four distinct messages, `connectors.py:131-157`) is carried only by `/api/connector-status/<name>` and the CLI, which the picker never consults. Confirmed live by the walkthrough (journey 1: all three unconfigured entries showed the identical generic label; report :22-27, :80-84).

**Why this matters:** Config comments are first-class user docs in this repo (the template the user must edit). A user reading the comment expects the app to tell them *what's* missing; it doesn't — they get a generic label and a dead "see Settings" pointer (DOC-1001).

**Blast radius:** one comment line; README:267 ("reports 'not set up' with that exact hint") shares the optimistic framing but is defensible at the API/CLI level where the hint genuinely appears. Related: DOC-1001, DOC-1008.

**Fix path:** Either soften the comment ("lists them disabled until you fill them in; the CLI / connection status name the exact missing piece") or fix the UI to show the reason and keep the comment — whichever way DOC-1001 resolves.

---

### DOC-1005 — Minor — Completeness — The "run `ollama pull`"-as-the-only-path copy was not swept after the in-app download shipped

**Evidence (surfaces still single-path):**
- `README.md:126-135` — Setup: "Finally, pull the local model … `ollama pull gemma4:e4b` / `ollama pull qwen2.5vl:3b`" with no mention that the first-run wizard now downloads both in-app (Stage 10.4's flagship feature is absent from the README entirely — grep: no "wizard"/"Download now" hit).
- `docs/getting-started-windows.md:40-46` — the **non-developer** walkthrough (the in-app download's exact audience) still requires the terminal pulls in Step 2 with no "or let KimCad's setup wizard download them" note.
- `frontend/src/components/ModelHealthPill.tsx:34` — "The model isn't pulled yet — run "ollama pull X" first." and `:36` (vision) — manual command only.
- `frontend/src/components/SettingsPanel.tsx:300-305` — design-model-missing action: "Pull `{model}` in Ollama, then check again" — manual only (while the *vision* row four lines up, `:276-278`, correctly offers "or use the setup wizard's download").

**Counter-evidence that the sweep was partial, not absent:** `docs/troubleshooting.md:70-71`, `docs/guide-settings-and-cloud.md:22-23`, and the wizard recap (`FirstRunWizard.tsx:577`) were all correctly updated to name both paths in this diff.

**Why this matters:** Nothing here is false — the manual pulls still work and are stated as the alternative in the updated docs — but the front door and the non-dev guide route every new user through terminal work the product now does itself, and the in-product copy is inconsistent row-to-row inside the same Settings card. The systemic pattern (five surfaces, same root) is what lifts this above Nit.

**Blast radius:** README Setup §, getting-started Step 2, two component copy strings; `ModelHealthPill.test.tsx:52` and `FirstRunWizard.test.tsx:166` assert the current strings. Related: DOC-1002 (the same feature also missing from ARCHITECTURE's endpoint list).

**Fix path:** One sentence in README Setup and getting-started Step 2 ("or skip this — KimCad's first-run wizard offers to download both models with progress"); align the pill/Settings strings with the vision row's "(or use the setup wizard's download)" pattern.

---

### DOC-1006 — Minor — Accuracy / Packaging — The `[bambu]` extra exists but no user doc mentions it, and the taught command bypasses its version floor

**Evidence:** `pyproject.toml:38-40` defines `bambu = ["bambulabs-api>=2.6"]` (with an accurate comment). Every user-facing surface — README:266-267, `docs/troubleshooting.md:88-89`, `BAMBU_INSTALL_HINT` (`bambu_connector.py:66-69`) — teaches bare `pip install bambulabs-api` instead. The slice-10.3 audit verified the connector's API binding **against 2.6.6 specifically** (method signatures, `GcodeState` members, `plate_1` path); the `>=2.6` floor encodes that verification, and the bare command is the only place the floor doesn't travel.

**Why this matters:** In practice `pip install bambulabs-api` resolves to a current version and works; but a constrained/cached environment can satisfy the bare name with an older release the connector was never verified against, and the user followed the docs exactly. Also simple discoverability: the repo already teaches the extras pattern (`pip install -e ".[dev]"`, getting-started:72), so the `[bambu]` extra is invisible, undocumented surface.

**Blast radius:** three doc strings + the in-code hint (the hint is pinned by tests in `tests/test_bambu_connector.py` / `test_connectors` — check before rewording). No migration.

**Fix path:** Recommend teaching `pip install "bambulabs-api>=2.6"` (works for non-source installs too, keeps the floor) or adding "(or `pip install -e ".[bambu]"` from a source checkout)" to the README note; at minimum mention the extra once in the Bambu setup note.

---

### DOC-1007 — Nit — Completeness — `docs/README.md` index omits `docs/cadquery-backend.md`

**Evidence:** `docs/README.md` (the "map of what's current vs. historical") lists every other current doc but not `cadquery-backend.md`, which exists in `docs/` and is current (Stage 8 feature, still shipped). Pre-existing — not introduced by Stage 10 — flagged once for the index-currency check this audit was asked to run; the index needed no Stage 10 additions otherwise (troubleshooting/guides were extended in place, correctly).

**Fix path:** One bullet under "Current".

---

### DOC-1008 — Nit — Accuracy — The troubleshooting heading quotes a message form ("needs …") that only the CLI/developer surface emits; the web-facing note says "need …"

**Evidence:** `docs/troubleshooting.md:86` heading: `A Bambu printer connection says "needs the optional bambulabs-api package"`. Exact-string check: the CLI prints the developer detail — `Not sent to bambu_p2s: connector 'bambu_p2s' (bambu) needs the optional bambulabs-api package` (`cli.py:237-238` printing `str(e)` of `connectors.py:133`) — exact match ✓. The *user-facing* `note` on `/api/connector-status` is `BAMBU_INSTALL_HINT`: "Bambu connections **need** the optional bambulabs-api package — in a terminal, run: pip install bambulabs-api — then try again" (`bambu_connector.py:66-69`) — "need", not "needs", and (per DOC-1001) that note is effectively unreachable inside the SPA anyway. This repo maintains exact-string discipline between troubleshooting headings and implemented messages; this one matches only the CLI surface.

**Fix path:** Quote the substring both surfaces share — e.g. `says it "needs the optional bambulabs-api package"` → `mentions "the optional bambulabs-api package"` — or note "(CLI wording; the in-app status says 'Bambu connections need…')".

---

## Tag-time package — exact lines the stage-10 tag must touch (KNOWN-AND-EXPECTED; flagged, not deep-dived)

Verified still internally consistent *as a pre-tag tree* with one caveat: README now simultaneously says "Next up: a direct-print UI (Stage 10)" (status ¶) **and** documents browser send / the bambu connector as shipped "(Stage 10)" body features (README:263-274, 291-296) — the repo's body-per-slice / status-at-tag convention explains it, but the tag should land promptly; until then a first-time reader sees the front door contradict itself. The full move list:

| File | Lines | What moves |
|---|---|---|
| `CHANGELOG.md` | new entry at top | The owed Stage 10 entry (slices 10.1–10.4, audit trail refs) — **must also resolve the layer-viewer promise at :132 (DOC-1003)** |
| `README.md` | 16-33 (esp. 31-32) | Status ¶: Stage 9 → Stage 10 done/tagged; "Next up" → Stage 11. (README:249-253 "No real hardware is driven yet (that's the final beta at Kim's)" stays true post-Stage-10 — verified consistent with the Bambu mock-only parenthetical.) |
| `ROADMAP.md` | 69 | "**Next = Stage 10 (direct-print UI + Bambu-native).**" → Stage 10 done, next = Stage 11 |
| `ROADMAP.md` | 71-72 | "Still ahead before beta: direct-print UI + Bambu-native (Stage 10), and …" — drop the Stage 10 half |
| `ROADMAP.md` | 127 | The "Still a gap … a **Bambu-native** connector (Stage 10 …)" blockquote — close the gap note |
| `ROADMAP.md` | 293-302 | Stage 10 section needs its **EXIT MET (date)** line (pattern: Stage 9's at :286-291), including the "remaining cloud paths as feasible" disposition (LAN-only shipped) and where the layer viewer went (DOC-1003) |
| `HANDOFF.md` | 1 | Title line (currently "Stage 9 … DONE … Stages 0–9 tagged") |
| `HANDOFF.md` | 4-6 | RESUME box: "What's done" + "Active task: … **Next = Stage 10**" → Stage 10 done, next = Stage 11 |
| `HANDOFF.md` | 43-44, 61 | Optional one-liners in the fenced historical narrative: the layer-viewer deferral (DOC-1003) and "NO model-pull … (those are Stage 11)" — both now superseded; the :11-14 disclaimer technically covers them |
| `docs/audits/RUN-LEDGER-2026-06-05.md` | Phase C table | Stage 10 row → done (the ledger is the tracker the RESUME box delegates to) |

---

## What's working

- **The Bambu setup note (README:265-274) is the best connector doc in the file** — protocol named (MQTT-over-TLS + FTPS), the optional dependency with its exact install command, the on-printer menu paths for both codes (verified word-for-word against `connectors.py:147-156`'s messages: *Settings → Device*, *Settings → WLAN → Access Code*), the secret-in-env-var rule (code: `connectors.py:150`, never stored/logged ✓), the template posture (config ships `bambu_p2s`/`bambu_a1` with empty `base_url:`/`serial:` ✓ `config/default.yaml:122-133`, pinned by `test_default_yaml_ships_bambu_visible_but_unconfigured`), and the confirm + gate rules (enforced at `bambu_connector.py:208` via `ensure_sendable`).
- **The reason-vocabulary table was maintained, not just appended.** The `busy` row's new clause — "and `bambu` refuses to send over a running job" — is exactly what the code does (`bambu_connector.py:224-232`: pre-upload state check, `reason="busy"`, soft typed outcome), and the existing PrusaLink/OctoPrint/Moonraker clauses were preserved correctly.
- **The slice-10.3 audit's doc findings all landed.** CLI `--send` help now names the bambu templates with the third "visible-but-unconfigured" category (`cli.py:81-85`), the README CLI bullet includes `--send bambu_p2s` / `--send bambu_a1` (README:284-285), and the busy row is fixed — nothing from DOC-001 (10.3) survives.
- **Troubleshooting's exact-string discipline held on the model-download entry.** "Not enough disk space" ✓ (`model_pull.py:127`), "about 13 GB together" ✓ (`model_pull.py:63` + wizard button "Download now (~13 GB)" `FirstRunWizard.tsx:366`), "Your local AI (Ollama) isn't running" ✓ (`webapp.py:1171`), **try again** ✓ (`FirstRunWizard.tsx:375,396`), "downloads only KimCad's own two models; you never need to pick one" ✓ (list fixed server-side, `webapp.py:1134`; POST reads no body — walkthrough verified live), "Ollama resumes a partial download" ✓ (blob-level resume, verified in the 10.4 audit-lite).
- **`docs/guide-settings-and-cloud.md`'s update is accurate to the letter** — "Settings shows its own row for it (downloaded / not downloaded)" matches `SettingsPanel.tsx:269-291` exactly, including the "Download now" and "check again" affordance names.
- **ARCHITECTURE's two new module rows are honest and code-true.** `bambu_connector.py` row: env-var-only access code ✓, short-lived sessions/camera-never-started ✓ (`bambu_connector.py:92-96`), graceful absence ✓, busy-refusal ✓, fake-transport-only testing stated plainly ✓. `model_pull.py` row: loopback-only ✓ (`is_loopback_url`, now `ipaddress`-exact after the 10.4 audit), disk pre-check ✓, idempotent start ✓, per-model friendly failures ✓.
- **The audit-lite → fix loop is visible in the shipped code.** Every doc-adjacent finding from the four slice audits was verified fixed in this tree: the FTP "226" upload proof (`bambu_connector.py:241-250`), the plate-count guard with its Bambu-Studio fallback message (:213-220), the `(or use the setup wizard's download)` vision-row copy, the recap's "downloading now" branch (`FirstRunWizard.tsx:571-578`), HANDOFF's `reg.gate_status` correction (HANDOFF.md:381), and the no-op-start state clearing (`model_pull.py:107-111`).
- **`docs/README.md`'s current/historical split continues to do its job** — the superseded Stage 8.5 plan is correctly quarantined with an explicit "gemma vision lines were superseded" warning, and the two updated guides live on the "Current" list.

## Honesty / marketing audit

**Verdict: clean.** The load-bearing parenthetical — README:273-274 "*(Validated against a mock transport; first real-hardware run is the Stage 11 beta at Kim's.)*" — is consistent at every surface where the Bambu send is described: the send-section preamble's stage-wide disclaimer ("**No real hardware is driven yet** … *software-complete and mock-tested*, not hardware-verified", README:250-253), ARCHITECTURE's module row ("Wholly tested against an injected fake transport; first hardware run is the Stage 11 beta"), the module docstring (`bambu_connector.py:18-19`), and the pyproject comment. No surface narrates a real Bambu print as proven. The simulated-send story is equally honest end-to-end: picker label, button ("Send test job"), dialog ("No real printer will run"), and success copy ("No hardware ran") — all walkthrough-verified live. The size claims (~13/~10/~3 GB) round *up* from the real 9.6 + 3.2 GB. The one overclaim found anywhere is internal-facing, not marketing: the config comment of DOC-1004 ("with the reason"). The closest thing to a marketing risk is **under**-claiming: the README never mentions the in-app model download at all (DOC-1005).

## Summary for the orchestrator

- **Rollup:** 0 Blocker / 0 Critical / 3 Major / 3 Minor / 2 Nit (8 findings)
- **Top 3:** DOC-1001 (the "see Settings" dead-end + the auth hint contradicting the env-var credential posture), DOC-1003 (the dangling layer-viewer promise the tag-time CHANGELOG entry must resolve), DOC-1002 (the declared-authoritative ARCHITECTURE endpoint list missing both `/api/model-pull` routes).
- **Tag-time package:** routine status moves verified and enumerated above, **plus two non-routine items found:** the CHANGELOG:132 layer-viewer promise (DOC-1003) and the RUN-LEDGER Phase C row.
- **Drafts produced:** none (AUDIT-ONLY mode).
- **Blockers:** none — no doc instructs something that fails, and the honesty posture on the untested-hardware path is consistent everywhere it's stated.
