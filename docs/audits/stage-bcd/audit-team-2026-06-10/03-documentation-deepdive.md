# Documentation Deep-Dive — KimCad (Stage B/C/D stage gate)

**Audit date:** 2026-06-10
**Role:** Technical Writer
**Scope audited:** The Stage B/C/D doc surface at commit `5a07381`: the two NEW user guides (`docs/guide-photo-onramp.md`, `docs/guide-settings-and-cloud.md`) with every claim verified against the shipped code; the Python-3.13 version-story rewrite (README Requirements + platform table + CadQuery section, `config/default.yaml` comment, `docs/cadquery-backend.md`, `pyproject.toml` comment, `docs/getting-started-windows.md`); the README layout table + key-storage sentence; `docs/README.md` index additions; the DOC-007/008 path fixes; the ARCHITECTURE.md five-jobs + `errors.py` rows; and whether `docs/troubleshooting.md` needs a keyring entry.
**Writer mode:** audit-only
**Auditor posture:** Adversarial (claims verified against source, tests, and the live frontend code; the app was not run — read-only audit)

---

## TL;DR

The two new guides are excellent, honest, plain-language documentation — and almost every privacy/security claim in them is backed by real code and a pinned test. The photo guide's "never your photo" promise is true at three layers (a dedicated local-provider wiring in `webapp.py`, the ENG-008 trust-boundary tests, and a non-persisting handler). The version-story rewrite is genuinely consistent across README, config, pyproject, cadquery-backend.md, and getting-started — **except ARCHITECTURE.md's own module map, which still says "KimCad runs on 3.14" twice**, the one current-facing surface the sweep missed. The other Major is a guide instruction that doesn't exist in the UI: "Clearing the key field deletes the stored key" — there is no clear-the-field path in the Settings panel, so a user trying to revoke a billable credential follows a dead instruction. No Blockers, no Criticals; the doc surface is in strong shape for a stage gate.

## Severity roll-up (documentation)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 2 |
| Minor | 3 |
| Nit | 1 |

## What's working

- **The photo guide's central promise is true, three layers deep.** `guide-photo-onramp.md` says "Your photo never leaves your computer… even if you've turned on cloud acceleration." Verified: `webapp.py:456-463` — `_SettingsAwareProvider.describe_photo` builds a *dedicated* `LLMProvider(self._config.llm_backend("local"))` and never consults `_active()` (the cloud-routing seam); the docstring states the trust rule explicitly. Pinned by **two** tests: `tests/test_trust_boundary.py:85` (`test_describe_photo_routes_local_even_with_cloud_enabled`, the ENG-008 pin) and `tests/test_webapp.py:2891` (asserts the cloud-capable `_active()` raises if consulted). The sketch path mirrors it (`webapp.py:465-471`).
- **"The photo isn't saved anywhere" is accurate.** `webapp.py:1409-1439` (`_handle_photo_seed`): the image is read from the request body, passed to the local vision call, and never written to disk; the docstring says "nothing is persisted," and the UI closes the loop with the UX-010 discard line (`PhotoOnramp.tsx:212`). The empty-read advice ("outdated Ollama") matches the dedicated troubleshooting entry (`troubleshooting.md:38-44`).
- **The settings guide's key-storage story matches the code exactly.** "In Windows Credential Manager… not in a plain file" → `settings_store.py:49-57, 184-193` (keyring write, sentinel in JSON). "If that store isn't available, KimCad falls back to its settings file and *tells you so* right under the key field" → `key_storage()` (`settings_store.py:121-130`) reported through `settings_response` (`webapp.py:500-501`) and disclosed verbatim under the key input (`SettingsPanel.tsx:357-364`, with the honest "Anyone who can read your files could read it" wording in file mode). "Shown only masked" → `_mask_key` (`webapp.py:474-483`), masked redisplay at `SettingsPanel.tsx:313`.
- **"Reset all settings… deletes the saved cloud key (including from the credential store)" is true.** `SettingsStore.clear()` calls `_delete_secret()` before writing `{}` (`settings_store.py:154-165`); the web reset path routes through it (`webapp.py:1235-1240`).
- **"Nothing is sent until you've turned the toggle on, saved a key, *and* chosen a cloud model" is exactly the gate in code.** `_SettingsAwareProvider._active()` (`webapp.py:417-424`) requires `cloud_enabled` truthy + a non-empty string key + a non-empty string model, else local.
- **"KimCad doesn't meter or cap it" is honest disclosure of a real limitation.** Verified by absence: nothing in `_SettingsAwareProvider` or the settings layer counts requests or spend. Stating the *absence* of a safety feature plainly is the right call for a billable key.
- **The version story is consistent on (almost) every current-facing surface.** README Requirements ("**Python 3.13** — the supported line," `README.md:69`), platform table (3.13 × 3, `README.md:355`), CadQuery section reframed as "a security-isolation choice, not a version constraint" (`README.md:160-165`), `pyproject.toml` (`requires-python = ">=3.13"` + a dated decision comment), `config/default.yaml:18-23` (same reframe + `.venv-cq313`-first discovery, which matches `cadquery_runner.py:293-314` including the launcher order), `docs/cadquery-backend.md:24-26` ("no longer a version workaround"), and `docs/getting-started-windows.md` Step 1 says **3.13**. Historical records (CHANGELOG stage entries, dated audits, ROADMAP/HANDOFF completed-stage narrative) correctly keep their as-of-then statements. The one miss is DOC-D-002 below.
- **DOC-007/008 path fixes both resolve.** `docs/README.md:24` now points at `design/stage-8.5-slice-5-onramps.md` (exists); `frontend/README.md` now points at "the repo-root `ARCHITECTURE.md`" (exists). Verified on disk.
- **The docs index earns its keep.** `docs/README.md:12-13` adds both new guides with honest one-line descriptions ("…and its local-only promise"; "…exactly what the cloud opt-in sends and where the key is stored") — a returning user scanning the index finds the privacy answers without opening anything.
- **The ARCHITECTURE five-jobs and errors.py rows match `src`.** `llm_provider.py`'s `Provider` protocol carries exactly five methods (`generate_design_plan`, `generate_openscad`, `generate_cadquery`, `describe_photo`, `describe_sketch` — `llm_provider.py:71-115`), matching the updated row. The `errors.py` row matches `src/kimcad/errors.py` (`ToolMissingError(RuntimeError)`, raised pre-spawn, carries the exact `fetch_tools.py` recovery command).
- **Voice.** Both guides keep the established "promise first, mechanics second" register of `getting-started-windows.md` — short, concrete, no jargon, and they say what the feature is *bad* at ("Not good: precise measurement"). This is the honesty standard the rest of the doc set should hold.

## What couldn't be assessed

- **Live keyring behavior** — whether Windows Credential Manager can ever *prompt* the user (it shouldn't via `keyring`'s Windows backend, which uses the credential vault API silently) was not exercised; this is a read-only audit and the app was not run. The fallback-and-disclose code path was verified statically and is covered by the Stage C tests.
- **The upstream Ollama vision-blank bug** — the guide and troubleshooting attribute an empty photo read to "an outdated Ollama." The KimCad-side handling is verified; the upstream claim is taken on the Stage C evidence trail, not re-reproduced.
- **Rendered SPA copy** — frontend strings were verified in source (`SettingsPanel.tsx`, `PhotoOnramp.tsx`, `FirstRunWizard.tsx`), not in a running browser.

---

## Doc asset inventory (scoped surfaces only)

| Asset | Exists? | Status | Finding(s) |
|---|---|---|---|
| `docs/guide-photo-onramp.md` (NEW) | Yes | Strong — every claim verified | — |
| `docs/guide-settings-and-cloud.md` (NEW) | Yes | Strong, one inaccurate instruction | DOC-D-001 |
| README (Requirements / platform table / CadQuery / layout / key sentence) | Yes | Strong, consistent | — |
| `pyproject.toml` version comment | Yes | Strong | — |
| `config/default.yaml` interpreter comment | Yes | Strong, matches discovery code | — |
| `docs/cadquery-backend.md` | Yes | Strong, fully reframed | — |
| `docs/getting-started-windows.md` | Yes | Says 3.13 throughout | — |
| ARCHITECTURE.md (five-jobs + errors rows) | Yes | Rows accurate; adjacent rows stale | DOC-D-002, DOC-D-004 |
| `docs/README.md` index | Yes | Strong | — |
| `frontend/README.md` (DOC-008 fix) | Yes | Resolves | — |
| `docs/troubleshooting.md` | Yes | Good; one missing entry | DOC-D-003 |

---

## Persona walk-through

**First-time user** — reads `guide-photo-onramp.md` and succeeds: the promise is up front, the steps match the real UI ("Describe with a photo" is the actual button text, `PhotoOnramp.tsx:152`, on the landing page next to the text box, `Landing.tsx:83`), and the failure path ("returns nothing") routes to a matching troubleshooting entry. No gaps.

**Returning user** — wants one answer fast ("what does cloud send?" / "where's my key?"). `docs/README.md`'s index lines name exactly those questions; the settings guide answers them in a four-bullet block. The one place this persona is failed: they follow "Clearing the key field deletes the stored key" and can't (DOC-D-001).

**New team member** — reads ARCHITECTURE.md to orient and gets told twice that KimCad runs on Python 3.14 (DOC-D-002), then reads README/pyproject saying 3.13. Version-number drift in the orientation doc is precisely the trust-eroding inconsistency this commit set out to eliminate.

---

## Findings

### [DOC-D-001] — Major — Accuracy — The settings guide documents a key-deletion gesture that doesn't exist in the UI

**Evidence**
`docs/guide-settings-and-cloud.md:36-37`: *"Clearing the key field deletes the stored key."*
The Settings panel offers no such path. With a key saved, the field is **read-only masked** with a **Replace** button (`SettingsPanel.tsx:308-324`); in replace/entry mode, the Save button is `disabled={!keyDraft.trim()}` and `saveKey()` early-returns on an empty draft (`SettingsPanel.tsx:106-112, 341`). The only UI route that deletes the key is **Reset all settings**. (The backend *does* support deletion — `update({openrouter_api_key: None})` → `_delete_secret()`, `settings_store.py:180-183` — the UI just never sends it.)

**Why this matters**
The returning user this sentence serves is doing something security- and billing-sensitive: revoking a paid credential. They clear the field, find no way to save the cleared state, and are left unsure whether their billable key is still stored (it is). An inaccurate instruction on a credential-handling flow is exactly the "docs lie" failure class — held to Major rather than Blocker only because the correct path ("Reset all settings removes it") is documented in the adjacent paragraph and the misleading instruction can't *expose* the key.

**Blast radius**
- Adjacent code: if fixed doc-side, only the guide changes. If fixed UI-side (the better product outcome — add a "Remove key" affordance wired to `openrouter_api_key: null`), `SettingsPanel.tsx` and its tests change; the backend path already exists and is tested.
- Other docs: no other doc repeats the claim (README and the wizard describe storage, not deletion). `FirstRunWizard.tsx:318-320` shows storage disclosure only — consistent.
- User-facing: the key-revocation flow for every cloud opt-in user.
- Tests to update: none if doc-fixed; `SettingsPanel` tests if UI-fixed.
- Related findings: none in this lane — this is a doc/UI contract decision for the dev (fix the sentence, or ship the affordance the sentence describes).

**Fix path**
Either (a) rewrite the bullet: *"To remove the key, use 'Reset all settings' (below) — it deletes the key from the credential store"* — or (b) add a Remove-key button to the masked-key row and keep the sentence (recommend (b) as the product-quality outcome; (a) is the honest minimum for this gate).

---

### [DOC-D-002] — Major — Accuracy — ARCHITECTURE.md's module map still says "KimCad runs on 3.14," contradicting the Stage-D version story on a current-facing surface

**Evidence**
- `ARCHITECTURE.md:79` (`cadquery_runner.py` row): *"The **in-process (3.14)** side of the CadQuery parallel backend."*
- `ARCHITECTURE.md:80` (`cadquery_worker.py` row): *"run by a ≤3.13 interpreter (**CadQuery's OCCT has no 3.14 wheels; KimCad runs on 3.14**)."*

Both contradict `pyproject.toml` (`requires-python = ">=3.13"`), README ("Python 3.13 — the supported line"), `config/default.yaml:18-20`, `docs/cadquery-backend.md:24-26`, and the worker's own current docstring (`cadquery_worker.py:3`: "KimCad targets Python 3.13 and CadQuery runs on 3.13 too — the out-of-process split is a [security choice]"). The Stage-D commit updated line 77 of this same table (five jobs) but not the two rows below it; the stage-D audit-lite's claim that "every *current-facing* surface now says 3.13" (`docs/audits/audit-lite-stage-d-2026-06-10.md:16`) is therefore not quite true.

**Why this matters**
ARCHITECTURE.md is the orientation doc for the new team member — the persona least equipped to know which of two contradictory version statements is current. Worse, line 80 re-asserts the *obsolete rationale* ("no 3.14 wheels") that this very commit deliberately replaced with the security-isolation rationale everywhere else, so the architecture doc now argues against the README about *why* the process boundary exists.

**Blast radius**
- Other docs that repeat the error: `HANDOFF.md:5` — the **RESUME box** (self-declared "SINGLE SOURCE OF TRUTH") also carries "(CadQuery has no 3.14 wheels)" inside its what's-done summary (see DOC-D-005). Genuinely historical surfaces (CHANGELOG:57-58, ROADMAP:242, dated audit reports, `docs/benchmarks/stage-5-template-families.md`) correctly keep as-of-then wording and should NOT be edited.
- User-facing: none at runtime; this is contributor-facing trust.
- Tests to update: none.
- Related findings: DOC-D-005 (same root: the "current-facing" sweep boundary was drawn one doc too tight); DOC-D-004 (same table row block).

**Fix path**
Two-line edit: row 79 "in-process (3.14) side" → "in-process (app-side)"; row 80 parenthetical → "(generated CadQuery is untrusted, so it runs at arm's length in its own 3.13 venv — a security boundary, not a version constraint; see `docs/cadquery-backend.md`)."

---

### [DOC-D-003] — Minor — Completeness — No troubleshooting entry for the credential-store file fallback

**Evidence**
`docs/troubleshooting.md` has no entry covering the keyring path. The scoped question — "what if Credential Manager prompts/fails?" — resolves as: the `keyring` Windows backend never prompts; any import/backend failure silently falls back to the settings file with UI disclosure (`settings_store.py:60-68, 184-193`; `SettingsPanel.tsx:357-364`). So nothing *breaks* — but a user who sees "Your key is kept in a settings file on this computer (the secure credential store isn't available here). Anyone who can read your files could read it" gets a warning with no doc explaining what happened, whether they should care, or how to get back onto the secure path. `guide-settings-and-cloud.md` discloses the fallback but also stops short of "what to do about it."

**Why this matters**
Troubleshooting.md promises "symptom → cause → fix for every known setup/runtime snag" — this is a known, deliberately-shipped degraded mode with a user-visible symptom string, and it's the only disclosed symptom in the product with no entry. The affected user is rare (broken/locked-down credential vault) but is by definition security-conscious at that moment.

**Blast radius** (optional for Minor, noted for the writer): one new troubleshooting entry quoting the real UI string, explaining the cause (the OS credential store wasn't usable), the risk (plain-file key), and the fix (restore Credential Manager service / re-save the key — the one-time migration at `settings_store.py:95-111` will move a file-stored key into the vault automatically on the next start once keyring works, which is a genuinely nice fact to document). Cross-link from `guide-settings-and-cloud.md`'s fallback parenthetical.

---

### [DOC-D-004] — Minor — Accuracy (status clarity) — The five-jobs row documents `describe_sketch` as "Stage 9" while every status surface says Stage 9 hasn't started

**Evidence**
`ARCHITECTURE.md:77`: *"`describe_sketch` (Stage 9 - the local-vision sketch read)"* — written in the present tense of the module map. The method genuinely exists and is wired (`llm_provider.py:115, 408, 510`; `webapp.py:465-471, 1441+`), so the row is *accurate against src* (the scoped question — verified). But README's status block says "Next up: an image/sketch on-ramp (Stage 9)" and HANDOFF says "next = Stage 9," so a reader cannot tell whether the sketch on-ramp is a shipped feature or not. ARCHITECTURE's web-layer section also lists `/api/photo-seed` but not the sketch endpoint, leaving the five-jobs row as the lone mention.

**Why this matters**
A new team member doing Stage 9 next session needs to know the provider seam (and apparently the endpoint) already exists. One clarifying word — e.g. "(Stage 9 seam, landed early — the on-ramp UI is the remaining Stage 9 work)" — prevents both a "wait, is Stage 9 done?" misread and accidental re-implementation.

---

### [DOC-D-005] — Minor — Accuracy — HANDOFF's RESUME box (self-declared source of truth) still gives the obsolete wheel-availability rationale

**Evidence**
`HANDOFF.md:5`: *"arm's-length 3.13 worker (CadQuery has no 3.14 wheels)"* — inside the "▶ RESUME HERE … SINGLE SOURCE OF TRUTH" box, not the historical narrative below it. The stage-D audit-lite explicitly exempted "ROADMAP/HANDOFF completed-stage records," which is the right policy for the body — but the RESUME box is the one part of HANDOFF that is by its own declaration *current-facing*.

**Why this matters**
The next-session agent/developer is told to treat this box as truth and will re-absorb the obsolete rationale the Stage-D rewrite retired. Smallest possible fix: a parenthetical "(historical rationale — see README/cadquery-backend.md: the boundary is now a security choice; both run 3.13)". Shares a root with DOC-D-002.

---

### [DOC-D-006] — Nit — Hygiene — Dash inconsistency introduced in the edited five-jobs row

**Evidence**
`ARCHITECTURE.md:77`: the new clause uses a hyphen — *"`describe_sketch` (Stage 9 - the local-vision sketch read)"* — while every sibling clause in the same sentence uses an em dash ("Stage 8 — …", "Stage 8.5 — …"). One character; flagging once.

---

## Drafts produced

Writer mode is audit-only; no drafts produced in this pass.

## Marketing / honesty audit

The guides are notably honest where it costs them: "The sizes are estimates," "Not good: precise measurement," "at a privacy cost you should make knowingly," "KimCad doesn't meter or cap it," and the file-fallback disclosure's "Anyone who can read your files could read it." No overclaim found in the scoped surfaces. The "no metering" sentence is the standout — a doc voluntarily disclosing the *absence* of a guardrail on the user's money is the trust-earning move; keep it.

## Patterns and systemic observations

- **Claim→code fidelity is now the house style and it shows.** Every load-bearing sentence in the two new guides traces to a specific code path and, for the trust-critical ones, a pinned test. This is the strongest doc/code alignment seen in this project's audit history; the guides can be cited in support conversations without caveats.
- **The version sweep's "current-facing" boundary was drawn correctly in principle and missed twice in practice** (ARCHITECTURE module map; HANDOFF resume box). Both misses are the same failure shape: long table-row/box prose where a stale clause hides inside an otherwise-edited region. A one-time `grep -n "3\.14"` over README/ARCHITECTURE/HANDOFF-resume-box/config/pyproject/docs-current after any version-story edit would have caught both.
- **Doc-vs-UI contract drift (DOC-D-001) is the residual risk class** now that doc-vs-backend claims are test-pinned. The photo guide's UI claims happen to match because the frontend strings were checked; nothing structurally prevents a guide sentence and a TSX affordance from drifting. Worth one line in the audit cadence: when a guide documents a *gesture*, verify the gesture, not just the backend it would call.

## Appendix: docs reviewed

- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\guide-photo-onramp.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\guide-settings-and-cloud.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\README.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\ARCHITECTURE.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\README.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\cadquery-backend.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\troubleshooting.md` (full)
- `C:\Users\scott\Desktop\Code\kimcadclaude\docs\getting-started-windows.md` (version-relevant sections via search)
- `C:\Users\scott\Desktop\Code\kimcadclaude\config\default.yaml`, `pyproject.toml`, `frontend\README.md`, `HANDOFF.md` (resume box), `CHANGELOG.md` / `ROADMAP.md` (version mentions), `docs\audits\audit-lite-stage-d-2026-06-10.md`
- Code verified against: `src\kimcad\settings_store.py`, `src\kimcad\webapp.py` (provider routing, photo/sketch handlers, settings/reset endpoints, `_mask_key`), `src\kimcad\llm_provider.py` (Provider protocol), `src\kimcad\errors.py`, `src\kimcad\cadquery_runner.py` (discovery order), `frontend\src\components\SettingsPanel.tsx`, `PhotoOnramp.tsx`, `Landing.tsx`, `FirstRunWizard.tsx`, `frontend\src\api.ts`; tests `tests\test_trust_boundary.py`, `tests\test_webapp.py` (photo trust-rule tests)
