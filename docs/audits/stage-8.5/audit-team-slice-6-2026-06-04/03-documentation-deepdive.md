# Stage 8.5 Slice 6 — Technical Writer deep-dive (AUDIT-ONLY)

**Role:** Senior Technical Writer · **Posture:** balanced · **Mode:** audit-only (flag, don't rewrite)
**Scope:** the Slice 6 Settings screen + experimental offer copy, and the repo docs that should reflect Slice 6.
**Diff under audit:** `git diff 16f9290..HEAD -- ":(exclude)docs/audits" ":(exclude)src/kimcad/web/assets"`
**Date:** 2026-06-04 · **Repo:** `C:\Users\scott\dev\kimcad`

## Verdict at a glance

**0 Blocker · 0 Critical · 0 Major · 2 Minor · 2 Nit.**

No in-app copy or doc violates a trust rule. No doc falsely claims Slice 6 / Stage 8.5 is done, merged, or
tagged. The trust-rule fidelity of the Settings + experimental copy is strong, and every load-bearing
honesty claim I spot-checked against the backend (masked key, "off your machine," "locked sandbox," "never
skips the printability check," "your choice via OpenRouter") describes real, verified behavior. The findings
below are small currency / precision items, not corrections of false claims.

---

## Trust-rule fidelity check (the load-bearing pass) — PASS

Each settled trust rule (from `docs/design/stage-8.5-slice-5-onramps.md` §"Trust rules" and
`docs/design/KimCad-Unified-Product-Spec-v3.0.md` §7.3) checked against the built in-app copy:

| # | Trust rule | In-app copy | Verdict |
|---|-----------|-------------|---------|
| (a) | gemma4:e4b is THE model; no Chinese model offered; no model menu | `SettingsPanel.tsx:222-268` AI-model card is a **health readout** (`modelTone`/`modelLabel`), not a picker. Code comment line 26-28 + line 222-223 state the rule explicitly. Default label hard-codes `gemma4:e4b` (line 246). No `<select>` of models anywhere. | **PASS** |
| (b) | Cloud opt-in OFF by default + "sends your prompt off your machine" at point of use | Switch defaults from `settings.cloud_enabled` which the store seeds false; the badge reads "Optional" when off (line 276-278). The privacy callout `SettingsPanel.tsx:293-296` reads **"This sends your prompt off your machine. Off by default…"** — at the point of use, in the cloud card. | **PASS** |
| (c) | API key = a normal Settings field, masked on return; copy must not imply env-only | `SettingsPanel.tsx:300-350` is a normal text field (paste → Save → masked redisplay with Replace). Backend `_mask_key` (`webapp.py:359-364`) returns `••••••••••••••••` + last 5; the full key is never echoed. No copy anywhere says "set an environment variable." | **PASS** |
| (d) | Experimental generator labeled untrusted/OFF + "runs in a locked sandbox" + "never skips the printability check" | `SettingsPanel.tsx:381` badge "Experimental · Untrusted"; line 392-395 "Off by default. Runs in a locked sandbox; never skips the printability check; results can be rough." Inline offer `ChatPanel.tsx:193-196` "Experimental · may not be perfect. It runs in a locked sandbox and still has to pass the printability check." | **PASS — and honest (verified below)** |
| (e) | NO hardwired cloud vendor — the user picks the model (spec §7.3) | Cloud copy `SettingsPanel.tsx:289-292` "send a design prompt to a cloud model — **your choice, via OpenRouter**." A **model field** the user fills (line 352-372) with a "Browse models on OpenRouter →" link; no pre-selected/recommended model. Matches spec §7.3 verbatim intent. | **PASS** |

**No copy contradicts a trust rule.** This is the headline result of the audit.

---

## Honesty check — claims verified against the backend

Every "does it describe REAL behavior?" claim I could trace to code is honest:

- **"Off by default — KimCad stays on your computer until you choose this"** (`SettingsPanel.tsx:294-296`).
  Verified: `_SettingsAwareProvider._active()` (`webapp.py:329-350`) returns the **local** provider unless
  `cloud_enabled` AND a key AND a model are all present; it degrades to local on any gap or cloud-build
  failure. The resting truth really is local.
- **"Runs in a locked sandbox; never skips the printability check"** (`SettingsPanel.tsx:394-395`,
  `ChatPanel.tsx:194-196`). Verified: the experimental codegen path runs through `render_scad`
  (`pipeline.py:302`, the `openscad_runner` sandbox that raises `BlockedCodeError` on forbidden code) and
  `run_gate` is called **unconditionally** (`pipeline.py:756, 805`) on every path including the experimental
  one. The experimental generator uses the identical gate as every other build — the claim is true.
- **"This sends your prompt off your machine"** (`SettingsPanel.tsx:293-296`). True — when cloud is active
  the prompt is sent to OpenRouter (`webapp.py:340-347`).
- **Masked key affordance** — the input shows `settings.cloud_key_masked` read-only with a Replace button
  (`SettingsPanel.tsx:302-318`). The masked form is `••••••••••••••••` + last 5 (`_mask_key`); the API never
  returns the full key (`settings_response`, `webapp.py:367-377`). Honest.
- **Tools "Installed / Not found"** (`SettingsPanel.tsx:407-421`) ← `/api/health` (`webapp.py:879-897`)
  which reports `cfg.binary_path(name).exists()`. It is a real on-disk presence check, not aspirational.
- **Reset confirm** — `resetAll` (`SettingsPanel.tsx:120-134`) genuinely clears printer/material/cloud/key/
  model/experimental and resets units to mm via the same `/api/settings` write. The two-step confirm
  (`SettingsPanel.tsx:435-448`) is real. Honest.
- **Experimental inline offer button** ("Try the experimental generator", `ChatPanel.tsx:197-199`) is
  genuinely wired: `App.tsx handleTryExperimental` (`App.tsx:238-247`) re-runs the last attempt with
  `experimental:true`. Not a dead button — the "may not be perfect" offer does exactly what it says.

**No aspirational or dishonest claim found in the Slice 6 copy.**

---

## Doc-consistency check — PASS (no false "done/merged/tagged")

- **Tags stop at `stage-7`.** `git tag` → `stage-0 … stage-7`. No `stage-8` / `stage-8.5` tag exists. **PASS.**
- **CHANGELOG.md** — the only `[Unreleased]` section. It states Stage 8.5 is "**IN PROGRESS on branch
  `stage-8.5-usability` — not yet merged or tagged**" (CHANGELOG.md:14) and describes **only Slice 1** as
  implemented-and-pending. It makes **no** "done/merged/tagged" claim about Stage 8.5. **PASS.**
- **README.md** (lines 16-20, 45-53) — "Stage 8.5 (Usability) is in progress on branch
  `stage-8.5-usability` — not yet merged or tagged"; documents only Slice 1. The cloud reference (lines
  61-64) is about the `config/local.yaml` opt-in (still accurate for the CLI/config path) and does **not**
  overclaim the in-app cloud screen. **PASS.**
- **ROADMAP.md** (lines 56-62, 212-214) — "Stage 8.5… IN PROGRESS on branch… nothing in it is merged or
  tagged yet." **PASS.**
- **HANDOFF.md** — "Stage 8.5 (Usability) IN PROGRESS on `stage-8.5-usability`"; no false done claim. (Its
  currency is stale — see DOC-002.)
- **`docs/design/stage-8.5-slice-5-onramps.md`** — the "Settled decisions" #1 now reads "**the user picks
  the model via OpenRouter; KimCad does NOT hardwire a vendor**," explicitly correcting the earlier "KimCad
  picks one" draft and citing spec §7.3 + the v3.0 change table. **This matches the built behavior** (a
  user-filled model field, neutral/empty by default; `custom_openrouter` ships `model_name: ""`,
  `config/default.yaml:73`). **PASS — corrected as required.**

**No doc falsely claims this work is done, merged, or tagged.**

### Stage-close watch item (NOT a drift finding)

The CHANGELOG `[Unreleased]` and the README/user-manual do **not** yet describe the Settings screen
(Slices 2-6). Per the Slice 1-5 cadence this entry is **intentionally batched to stage close**, so this is
**not** a drift finding now. It is flagged here only as a **stage-close checklist item**: when Stage 8.5
merges, the CHANGELOG `### Added` block and the user docs must gain the Settings screen (model status, cloud
opt-in, experimental toggle, tools/about/reset). Carry to the next-sprint watchlist, not this-sprint punch.

---

## Findings

### DOC-001 (Minor · Accuracy) — README "What it does" diagram omits the template→experimental offer / cloud branch

**Evidence:** `README.md:24-28` shows the single deterministic pipeline
`prompt → design plan → OpenSCAD → render → … → slice`. Slice 6 adds two now-visible branches a reader of
the product would encounter: (1) a no-template request that **offers** the experimental generator
(`needs_experimental`, `pipeline.py:373-381`) rather than always running codegen, and (2) an opt-in cloud
model substituting for the local one (`_SettingsAwareProvider`). Neither is in the README's mental model.

**Why it matters:** the first-time-user persona reading the README forms a model of "what happens when I
type a prompt." After Slice 6 the real flow has an explicit fork (template hit → instant; miss → offer
experimental) that the diagram doesn't show. Not wrong — incomplete.

**Severity rationale:** Minor — the README is accurate for the template/LLM core; this is an additive gap on
a branch that isn't merged. Folds naturally into the stage-close README pass; no action needed mid-slice.

**Blast radius:**
- Adjacent docs: `ARCHITECTURE.md` pipeline section (if it diagrams the same flow) and
  `docs/stage-8.5-usability-plan.md` Slice 6 description already cover the fork; the README is the only
  user-facing doc that lags.
- Migration: none. Tests to update: none.
- Related findings: ties to the stage-close watch item above (Settings/cloud/experimental doc batch).

**Fix path (defer to stage close):** when documenting Stage 8.5, add a one-line note under the diagram —
"a request with no matching template offers an experimental direct generator; an optional cloud model can
stand in for the local one when you opt in" — rather than complicating the ASCII diagram itself.

---

### DOC-002 (Minor · Accuracy) — HANDOFF.md "RESUME HERE = Stage 8.5, Slice 1" is stale; branch is at Slice 6

**Evidence:** `HANDOFF.md:1` is dated **2026-06-03** and line 18 reads "**RESUME HERE = Stage 8.5,
Slice 1.**" The branch has since shipped MS-1…MS-5 of Slice 6 (commits `2a6579b … 44c248c`); Slices 2-6 are
implemented. The handoff's "resume" pointer is five slices behind the actual branch state.

**Why it matters:** the new-team-member / returning-author persona uses HANDOFF.md as the single source of
"where am I." A resume pointer at Slice 1 when the work is at Slice 6 is exactly the "one truth per doc"
hazard the handoff itself calls load-bearing (`HANDOFF.md:375-377`). It is not a *false* claim (it doesn't
say Slice 6 is done) — it's a **stale currency** problem: a resumer could redo or misread state.

**Severity rationale:** Minor, not Major — it doesn't assert anything false about gate/merge/tag status, and
the CHANGELOG/ROADMAP correctly carry the branch's in-progress framing. But it's a real "stale pointer"
miss against the project's own standing rule.

**Blast radius:**
- Shared assumption: HANDOFF.md is the declared source of truth (`HANDOFF.md:103-104, 378`); a stale resume
  line there propagates to any session that bootstraps from it.
- Migration: none. Tests: none.
- Related findings: none; isolated to the handoff's currency.

**Fix path:** at the next handoff refresh, advance the "RESUME HERE" pointer to the current slice and note
Slices 2-6 as implemented-pending-gate. (Audit-only — flagged, not rewritten.)

---

### DOC-003 (Nit · Tone/Accuracy) — Cloud model field has no inline note that local is the fallback if the slug is wrong/unreachable

**Evidence:** `SettingsPanel.tsx:352-372` — the Model field placeholder is
"a model slug from openrouter.ai/models" with a "Browse models" link. The backend behavior is honest and
safe (a bad/empty model → `_active()` returns local, `webapp.py:335-336`; a cloud build failure → local,
line 348-349), but the **copy doesn't tell the user** that a typo'd or unreachable slug silently falls back
to local rather than erroring.

**Why it matters:** very mild expectation gap — a user who fat-fingers a slug gets local results with no
explanation of why "cloud" didn't seem to engage. The behavior is the *right* (fail-safe) one; only the
disclosure is thin. Not a dishonest claim — an absent helpful one.

**Severity rationale:** Nit — power-user opt-in surface, fail-safe behavior, no trust-rule or correctness
impact. Mentioned once.

**Fix path (optional):** a one-line helper under the field — "If a model can't be reached, KimCad quietly
falls back to your local model." Entirely optional polish.

---

### DOC-004 (Nit · Accuracy) — About card license string is correct but unverified against repo LICENSE in this slice

**Evidence:** `SettingsPanel.tsx:430` renders "open-source (Apache-2.0)". The spec and prior docs confirm
Apache-2.0 (e.g. CHANGELOG/spec references). This is consistent — flagging only that the license name is now
**also surfaced in-app**, so if the repo license ever changed, this string is a new place that must stay in
sync. No discrepancy today.

**Severity rationale:** Nit — informational; the string is correct. Logged so the team knows the in-app
About is now a second source of the license fact to keep consistent.

**Fix path:** none needed now; note for future license-change checklists.

---

## What's working (credit where due)

- **Trust-rule copy is exemplary.** The Settings copy doesn't just avoid violating the rules — it states
  them plainly to the user in their own language: "your choice, via OpenRouter" (no hardwired vendor),
  "This sends your prompt off your machine" (cloud honesty at point of use), "Experimental · Untrusted" +
  "never skips the printability check." This is honest marketing copy done right.
- **The code comments encode the trust rules as load-bearing invariants** (`SettingsPanel.tsx:26-28,
  222-223, 270-272`; `settings_store.py:39-46`; `webapp.py:305-314`), so the *why* travels with the code —
  a future editor is told, in situ, not to add a model menu or hardwire a vendor. Excellent doc-in-code.
- **Honesty about save failure is built into the contract**, not just the copy: the server returns
  `saved:false` and the UI shows "Couldn't save — your choice didn't stick" (`SettingsPanel.tsx:148-152`,
  `webapp.py:996`). The product never claims "Saved" when it didn't persist.
- **The Slice 5 design doc's "settled decisions" correction is exactly right** — it not only flips "KimCad
  picks" → "user picks," it cites the spec section and change-table that mandate it, and confirms the
  `custom_openrouter` backend already ships `model_name: ""`. That is how a settled-decision record should
  read: decision + authority + built-state confirmation.
- **No doc anywhere overstates status.** CHANGELOG, README, ROADMAP, HANDOFF, and the usability plan all
  consistently frame Stage 8.5 as in-progress-on-branch, not-merged, not-tagged. The "one truth per doc"
  discipline (a prior pain point) is holding across the doc set.
- **The api.ts type comments are honest about masking** (`api.ts:241, 282-284`): "the OpenRouter key is only
  ever returned MASKED… never in full" — the client-side contract documentation matches the server.
