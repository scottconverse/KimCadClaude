# Engineering Deep-Dive — KimCad (Stage B/C/D stage gate)

**Audit date:** 2026-06-10
**Role:** Principal Engineer
**Scope audited:** `git diff 3bb1226..5a07381` (Stage B quality-gate tests, Stage C trust boundary, Stage D UX/version-story) — `settings_store.py`, `subprocess_env.py`, `openscad_runner.py`, `cadquery_runner.py`/`cadquery_worker.py`, `cli.py` (`--allow-remote`), `webapp.py` (key_storage plumbing), `pyproject.toml`/`requirements.lock`, CI workflow, and the Stage-D React changes (`App.tsx`, `Landing`, `ChatPanel`, `RightPanel`, `ExportPanel`, `PhotoOnramp`, `FirstRunWizard`, `SettingsPanel`, `api.ts`) plus the new tests (`conftest.py`, `test_settings_store.py`, `test_trust_boundary.py`, `App.test.tsx`).
**Auditor posture:** Balanced (per-stage audit-lites closed 0/0/0/0/0; the live walkthrough verified the keyring chain against the real vault).

---

## TL;DR

This is a disciplined, well-narrated diff: the keyring sentinel contract is honest (disclosed file fallback rather than fake safety), the `--allow-remote` gate fails safe on every malformed-host input I could construct, the secret scrub was correctly unified into one module with an identity test pinning the two runners together, and the test additions (hermetic fake vault, planted-secret env assertions, photo-local-routing pin) defend the claims rather than merely restating them. One Major survives the audit-lites: the init-time legacy migration in `SettingsStore.__init__` reads the settings file **before** taking `_WRITE_LOCK` and then writes that pre-lock snapshot back under the lock — a lost-update race that is amplified because the LLM provider constructs a fresh `SettingsStore` on every design call. Everything else found is Minor/Nit hygiene: a partial-failure contract gap in `update()`, a BOM + hand-edit smell in `requirements.lock`, scrub-segment gaps (`AUTH`/`PASSPHRASE`), and a landing-draft staleness papercut in the Stage-D React work.

## Severity roll-up (engineering)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 1 |
| Minor | 4 |
| Nit | 4 |

## What's working

- **The keyring contract is honest, tested, and degrades with disclosure.** The sentinel design (`@keyring` in the file, real secret in WinVault) keeps every existing consumer unchanged via transparent resolution in `all()` (`src/kimcad/settings_store.py:132-149`), and the file fallback is *disclosed* (`key_storage()` → SettingsPanel/FirstRunWizard copy) instead of silently pretending safety. The six new store tests cover round-trip, migration, broken-backend fallback, clear/reset vault deletion, and the dangling-sentinel case.
- **Test hermeticity vs the real vault.** The autouse `_fake_keyring` fixture (`tests/conftest.py`) guarantees no pytest run touches the developer's real Credential Manager — this was the single easiest thing to get wrong and it was caught at design time.
- **`_is_loopback_host` fails safe in every direction.** `localhost` literal, `ipaddress.ip_address(...).is_loopback`, and `ValueError → False` means whitespace (`" 127.0.0.1"`), empty string (`""`, which `HTTPServer` would otherwise bind to all interfaces!), bracketed IPv6 (`[::1]`), shorthand (`127.1`), and case variants (`LOCALHOST` — gated, since the comparison is case-sensitive) all land on the *requires-flag* side. IPv6 `::1` and `0:0:0:0:0:0:0:1` parse loopback; `::ffff:127.0.0.1` and `::` are gated. I found **no bypass** other than the documented direct `serve()` import (`webapp.py:2056`), which is a developer surface, not a user one. The gate is also exercised through real `cli.main()` in `test_trust_boundary.py`, not just the helper.
- **One scrub, two runners, pinned by identity.** `kimcad/subprocess_env.py` is the single source of truth; `test_scrub_is_shared_single_source` asserts `cadquery_runner._is_secret_env is subprocess_env.is_secret_env`, so the pre-Stage-C drift (OpenSCAD inheriting everything) cannot silently recur. The OpenSCAD `_run` re-applies the `OPENSCADPATH` overlay *after* scrubbing, and `OPENSCADPATH`/`PATH` survive the segment matcher (verified: neither name contains a secret segment; the planted-secret test asserts the overlay survives).
- **Secret never transits an API response or log.** I traced every `saved_settings()`/`store.all()` consumer in `webapp.py`: `web_options` uses only printer/material keys; `settings_response` masks (`_mask_key`, last 5); `/api/health` reads the key only for a boolean; the provider passes it into the OpenAI client config. No caller serializes the resolved dict wholesale.
- **WinVault limits are a non-issue by construction.** OpenRouter keys (~70 chars) are far below the generic-credential blob limit (2560 bytes), and an oversized/refused `set_password` raises → caught → disclosed file fallback. The failure mode is degraded honesty, not data loss.
- **The Python-3.13 story is reconciled where it matters.** `requires-python = ">=3.13"` matches the venv (3.13.13), CI (`py -3.13` pin in `.github/workflows`), and the lockfile; README Requirements + platform table updated; historical docs (CHANGELOG, ROADMAP/HANDOFF completed-stage records) deliberately keep as-of-then statements — a defensible records policy. The `py -3.12/-3.11` worker probes are *not* dead-wrong: `cadquery_worker.py` is stdlib+cadquery only and never imports `kimcad`, so a 3.11/3.12 worker remains genuinely valid.
- **Stage-D UX changes are test-backed.** UX-001 (cancel-preserves-prompt), UX-005 (confirm-respects-no, no-nag-when-saved), and the UX-008 jargon removal each landed with a pinning test, including updating the old `Gate: Passed` assertion to pin the *absence* of the jargon.

## What couldn't be assessed

- **Scope-list drift:** the audit brief named `benchmark.py` (model-down re-raise), `pipeline.py` (`ToolMissingError` at slice), `webapp.py` slice binary-order / photo/sketch model-down, and `ModelHealthPill.tsx` as part of this diff — **none of those files changed in `3bb1226..5a07381`** (they were Stage-A-or-earlier work, already inside the `3bb1226` baseline). They were not re-audited here.
- **Screen-reader runtime behavior** of the UX-007 `aria-hidden` thinking-row change was not verified against a live NVDA/VoiceOver session (the code comment itself defers fuller live-region scoping to a measured SR session; the Viewport `role=status` overlay is claimed to carry the announcement). Static review only.
- **CI execution** was not re-run by this audit; the workflow file and the stage-D audit-lite's reported 907 pytest / 300 vitest counts were taken as given.

---

## Findings

> **Finding ID prefix:** `ENG-`

### [ENG-101] — Major — Correctness — Init-time keyring migration reads the file outside `_WRITE_LOCK`, then writes the stale snapshot back under it (lost-update race, amplified by per-call store construction)

**Evidence**
`src/kimcad/settings_store.py:93-111`:

```python
def __init__(self, path: Path):
    self._path = path
    try:
        raw = self._read_raw()                      # <-- read OUTSIDE the lock
        secret = raw.get(_SECRET_KEY)
        if isinstance(secret, str) and secret and secret != _KEYRING_SENTINEL:
            kr = _keyring()
            if kr is not None:
                kr.set_password(_KEYRING_SERVICE, _SECRET_KEY, secret)
                with _WRITE_LOCK:
                    raw[_SECRET_KEY] = _KEYRING_SENTINEL
                    ...
                    _atomic_write_json(self._path, raw)   # <-- writes the PRE-LOCK snapshot
```

The amplifier: `_SettingsAwareProvider._settings()` constructs a **fresh `SettingsStore` on every LLM call** (`src/kimcad/webapp.py:409-413`), so this migration path is not "once at startup" — it re-runs at the start of every design request. Whenever the file holds a plaintext key (file-fallback mode — e.g. the vault was unusable at save time but `import keyring` now succeeds), a Settings POST (`update()` on the handler's cached store) that lands between the `__init__` read and its lock acquisition is silently overwritten by the stale snapshot: a just-changed printer default reverts, or a just-*cleared* key is resurrected into the file. The Stage-C audit-lite's "migration is best-effort **under the write lock**" claim is imprecise — only the write is.

**Why this matters**
A lost settings update under normal concurrent use (user saves settings while a design call is in flight) — and in the worst variant, a credential the user explicitly deleted reappears on disk. Conditions are narrow (file-fallback state + concurrent write + millisecond window) but the trigger is ordinary app usage, and this is the project's one security-sensitive store.

**Blast radius**
- Adjacent code: `_SettingsAwareProvider._settings()` (`webapp.py:409-413`) — per-call construction is the amplifier; consider reusing one store instance there regardless of the race fix. The handler-side cached store (`settings_box`, `webapp.py:788`) is unaffected once constructed.
- Shared state: `~/.kimcad/settings.json` + the `KimCad/openrouter_api_key` vault entry; `_WRITE_LOCK` (process-local — fine, the exclusive bind guarantees one process).
- User-facing: Settings saves that intermittently "don't take"; a cleared cloud key reappearing.
- Migration: none — fix is internal re-ordering.
- Tests to update: add a test that interleaves `__init__` migration with an `update()` (monkeypatched `_read_raw` ordering or a hook between read and lock); existing migration tests stay green.
- Related findings: ENG-102 (same method family, same partial-failure theme).

**Fix path**
Move the *entire* read-check-write sequence inside `_WRITE_LOCK`: acquire the lock first, `_read_raw()` inside it, re-check the plaintext predicate, then `set_password` + rewrite. (`set_password` under the lock is acceptable — it's a fast local vault call, and update()/clear() already make vault calls under the same lock.) Independently, have `_SettingsAwareProvider` keep one `SettingsStore` instance instead of constructing per call.

---

### [ENG-102] — Minor — Correctness — `update()` can report failure while the vault already holds the new secret (the "prior settings stand" contract breaks)

**Evidence**
`src/kimcad/settings_store.py:184-200`: for the secret key, `kr.set_password(...)` runs first; if the subsequent `_atomic_write_json` raises (e.g. `PermissionError` after all retries), `update()` returns `False` with the docstring promise "the save is a no-op, the prior settings stand." But the vault entry was already overwritten — and since the file still carries the sentinel, `all()` now resolves to the **new** key despite the reported failure. The reverse ordering issue also exists on clear: `_delete_secret()` runs before the file write that removes the sentinel.

**Why this matters**
A failed save that half-applies is a contract lie, and here the half that applies is the credential. The UI would show "couldn't save" while the new key is silently live (or a "failed" clear has actually revoked the key). Exposure is low — the file write is atomic-with-retries and rarely fails — hence Minor.

**Blast radius**
- Adjacent code: `clear()` (`settings_store.py:154-165`) shares the vault-then-file ordering.
- User-facing: SettingsPanel "saved: false" toast paired with changed effective behavior on the next design call.
- Tests to update: one test forcing `_atomic_write_json` to raise after a successful `set_password`, asserting either full rollback or a documented exception to the contract.
- Related findings: ENG-101 (same method family).

**Fix path**
Either write the file first and only then touch the vault (file failure → nothing changed; vault failure after a sentinel write → restore the prior file state), or capture the prior vault value and restore it on file-write failure. The simplest correct order: stage the file write to a temp name, do the vault op, then `os.replace`.

---

### [ENG-103] — Minor — Hygiene — `requirements.lock` gained a UTF-8 BOM and hand-reordered lines (hand-edited, not regenerated)

**Evidence**
`requirements.lock` byte 0: `EF BB BF` (verified: `head -c 6 | xxd` → `efbb bf61 6e6e`). The diff also shows non-alphabetical churn unrelated to the keyring addition (`pydantic`/`pydantic_core` swapped, `typing-inspection` moved below `typing_extensions`) — the signature of a PowerShell `Out-File`-style hand edit rather than a `pip freeze`/`pip-compile` regeneration.

**Why this matters**
pip itself tolerates the BOM, and CI's `pip install -r` + `pip-audit -r` evidently pass — but the first line `﻿annotated-types==0.7.0` is now a landmine for any other consumer (naive lockfile parsers, some SCA scanners, diff tooling), and a hand-edited lockfile invites drift between the lock and the actually-resolved environment (the keyring transitive set — `jaraco.*`, `more-itertools`, `pywin32-ctypes` — was added by hand and could miss a pin next time).

**Blast radius**
- Adjacent code: `.github/workflows` CI provisioning step and `scripts/ci.sh` both consume this file; the pre-push gate re-installs from it.
- Migration: none — regenerate in place.
- Tests to update: none; optionally a one-line CI guard (`head -c3` ≠ BOM).
- Related findings: none.

**Fix path**
Regenerate the lock from the venv (`python -m pip freeze --exclude-editable > requirements.lock` with UTF-8-no-BOM encoding, or adopt `pip-compile`), and add a trivial no-BOM/sorted check to `scripts/ci.sh` so a hand edit can't land again.

---

### [ENG-104] — Minor — Security — The secret-scrub segment list misses common credential namings: `AUTH`, `PASSPHRASE` (e.g. `npm_config__auth`, `*_AUTH_TOKEN` cousins like `*_AUTH`, SSH/GPG passphrases)

**Evidence**
`src/kimcad/subprocess_env.py:20-23`: `_SECRET_ENV_SEGMENTS = {KEY, APIKEY, TOKEN, SECRET, PASSWORD, PASSWD, CREDENTIAL, CREDENTIALS, PRIVATEKEY}`. Names like `NPM_CONFIG__AUTH` (base64 registry credentials, common on Windows dev boxes), `ARTIFACTORY_AUTH`, `SSH_PASSPHRASE`, or password-bearing URL vars (`DATABASE_URL`, `*_DSN`) pass the scrub into the OpenSCAD/CadQuery children.

**Why this matters**
The scrub is defense-in-depth behind two sanitizer layers, so this is not a reachable exfiltration path on its own — but the module's stated purpose is bounding blast radius *if a sanitizer is bypassed*, and these are exactly the vars an attacker would harvest. The whole-segment design (REAUDIT-N1) already protects against false positives (`AUTHOR` would not match a segment-`AUTH` rule since segments split on non-alphanumerics only — note `AUTHOR` is a single segment `AUTHOR`, not `AUTH`), so the additions are cheap and safe.

**Blast radius**
- Adjacent code: both runners via the shared module — one edit covers both (that's the point of ENG-003/stage-C).
- User-facing: none (geometry children need none of these).
- Tests to update: extend the precision tests in `test_trust_boundary.py`/cadquery scrub tests with `NPM_CONFIG__AUTH` (stripped) and `AUTHOR_NAME` / `OAUTH_CALLBACK_PATH`-style survivors as decided.
- Related findings: none.

**Fix path**
Add `AUTH` and `PASSPHRASE` to `_SECRET_ENV_SEGMENTS` (verify `OAUTH` segment behavior intentionally — `OAUTH` is its own segment and would survive unless also listed). URL-embedded passwords (`DATABASE_URL`) are a judgment call; at minimum document them as out of scope of a name-based scrub.

---

### [ENG-105] — Minor — Correctness (UX/state) — `landingDraft` is cleared only on a successful design, so a cancelled prompt re-seeds the Landing indefinitely — including via the explicit "New design" action — and can silently revert newer unsubmitted edits

**Evidence**
`frontend/src/App.tsx:115` (state), `:399` (set on every submit), `:364-365` (cleared **only** in the success path of `runDesign`), `:502-516` (`handleNewDesign` does **not** clear it), `:612` (`<Landing initialValue={landingDraft} />`); `Landing.tsx:34` seeds `useState(initialValue)` on mount. Two concrete staleness paths:
1. Cancel first design → draft retained (intended). Later: open a saved design from My Designs, work on it, press `n` / click **New design** → the Landing re-seeds the hours-old cancelled prompt with "Picked up where you left off." — on an action whose meaning is "start fresh."
2. Cancel → Landing seeded → user *edits* the text (local `Landing` state only) → visits Settings → returns: `Landing` remounts from the stale `landingDraft`, silently discarding the newer edits.

**Why this matters**
UX-001's intent ("a cancel shouldn't erase the user's words") is right, but without an expiry/clear path the preserved draft outlives its welcome and contradicts the "New design" affordance. The audit-lite's check ("a SECOND visit to the landing after success shows a clean box") only covered the success path.

**Blast radius**
- Adjacent code: `handleNewDesign` (`App.tsx:502`), the `n` shortcut routing through `shortcutsRef`, `Landing`'s mount-only seeding.
- User-facing: Landing, New-design flow, the "Picked up where you left off." note.
- Tests to update: add a case — cancel, then `New design` from a restored workspace → expect an empty box; the existing UX-001 test stays green.
- Related findings: ENG-108 (same handler).

**Fix path**
Clear the draft in `handleNewDesign` (an explicit "start over" is the user discarding it — the confirm dialog already guards the genuinely-unsaved case), and optionally lift the draft text up (controlled `value`/`onChange` or an `onDraftChange` callback) so in-Landing edits survive route hops instead of reverting.

---

### [ENG-106] — Nit — Correctness — Sentinel collision: a literal saved value of `"@keyring"` in file-fallback mode is later misread as the sentinel (key silently vanishes; `key_storage()` reports "keyring")

**Evidence**
`settings_store.py:56,125,137`: with no usable keyring, `update({"openrouter_api_key": "@keyring"})` writes the literal to the file; every subsequent `all()` treats it as the sentinel, finds no vault entry, and pops the key; `key_storage()` answers `"keyring"`. No real OpenRouter key takes this form — purely theoretical, plus reachable by a user hand-editing settings.json. Flagging for the record; namespacing the sentinel (e.g. a JSON-unlikely structure or `{"$kimcad": "keyring"}`) would eliminate the class if the store ever holds more secrets.

---

### [ENG-107] — Nit — Hygiene — Stale "cadquery ships no 3.14 wheels" rationale survives at `cadquery_runner.py:274-275` after the Stage-D version-story sweep

**Evidence**
The module docstring, worker docstring, README, `config/default.yaml`, and `docs/cadquery-backend.md` were all reframed to "security isolation, not a version constraint," but the probe comment (`# ... which implies a compatible Python, since cadquery ships no 3.14 wheels`) still tells the old story. Factually true today, but it's the exact framing Stage D set out to retire. One-line comment edit.

---

### [ENG-108] — Nit — UX/Architecture — `window.confirm` in `handleNewDesign` is a blocking native dialog in an app that otherwise ships accessible custom modals

**Evidence**
`App.tsx:510` (`window.confirm('Start over? ...')`); the wizard and shortcuts help are custom, focus-trapped, styled dialogs. The `n` shortcut path works (keydown is user activation; `preventDefault` fires before the dialog; WebView2 — the Stage-11 shell — renders default JS dialogs), and while the dialog is open the global key handlers and the Escape-cancel listener are suspended, which is acceptable since the design keeps running server-side. Consistency-only observation; fine to keep until Stage 11's shell work, where it's worth a one-line re-verify in the embedded WebView.

---

### [ENG-109] — Nit — Data provenance — `key_storage()`'s "where a NEW key would go" answer probes only importability, not backend usability

**Evidence**
`settings_store.py:121-130` + `_keyring()` (`:60-68`): with no key saved, `key_storage()` returns `"keyring"` whenever `import keyring` succeeds — but a save can still fall back to the file if the backend refuses at `set_password` time (the `fail=True` path the tests model). The wizard/Settings pre-save copy ("the key is kept in this computer's secure credential store") can therefore over-promise on import-OK/backend-broken machines. It self-corrects immediately after the save (the post-save payload re-reads the real file state), so exposure is one sentence for one moment. A stricter probe (`keyring.get_keyring()` not being the fail/null backend) would close it.

---

## Patterns and systemic observations

1. **Lock-scope discipline is the one crack in an otherwise careful store.** `update()`/`clear()` got the read-modify-write right under `_WRITE_LOCK`; the new `__init__` migration didn't (ENG-101), and the vault-vs-file ordering inside the lock leaves a partial-failure seam (ENG-102). Both are the same lesson: treat *vault + file* as one transaction — pick an order that makes the file write the commit point.
2. **The disclosure-over-pretense posture is the diff's best architectural property.** `key_storage()` → API → two UI surfaces, `--allow-remote`'s blunt warning, the photo-onramp privacy line — each chooses honest degradation over implied safety. ENG-106/109 are just the last few percent of that same honesty.
3. **Per-call object construction as a hidden concurrency multiplier.** `_SettingsAwareProvider` rebuilding the store each call was harmless when `__init__` was trivial; Stage C gave `__init__` side effects and quietly turned a startup-only code path into a per-request one. Worth a project convention: constructors with I/O side effects must be singletons or idempotent-under-concurrency.
4. **The audit-lite chain works but trusts its own phrasing.** Stage C's lite said "migration ... under the write lock" — the write is, the read isn't. Adversarial self-review caught the big things (hermeticity, sentinel edges, bypass surfaces); the residue is exactly the kind of word-level claim a second reader catches.

## Dependency snapshot

| Dependency | Version | Concern |
|---|---|---|
| keyring | 25.7.0 | Current major; Windows backend via pywin32-ctypes. No known CVEs; CI pip-audit gates the lockfile. Sound choice. |
| jaraco.classes/context/functools, more-itertools, pywin32-ctypes | (lock pins) | keyring transitives, added by hand (see ENG-103) — pins present, no concerns beyond regeneration hygiene. |
| (everything else) | unchanged | Out of this diff's scope; pip-audit `--strict` runs in CI on every push. |

## Appendix: artifacts reviewed

- `git diff 3bb1226..5a07381` (full), commit messages for `60a4181` (B), `3feaff5` (C), `5a07381` (D)
- `src/kimcad/settings_store.py` (full, post-diff), `subprocess_env.py`, `openscad_runner.py:243-260`, `cadquery_runner.py:265-330`, `cadquery_worker.py` (diff), `cli.py:85-455`, `webapp.py:380-520, 760-800, 1140-1300, 2056-2076`
- `frontend/src/App.tsx:95-240, 350-620`, `Landing.tsx`, `ChatPanel.tsx`, `RightPanel.tsx`, `ExportPanel.tsx`, `PhotoOnramp.tsx`, `FirstRunWizard.tsx`, `SettingsPanel.tsx`, `api.ts` (diffs)
- `tests/conftest.py`, `tests/test_settings_store.py`, `tests/test_trust_boundary.py`, `frontend/src/App.test.tsx`, `RightPanel.test.tsx` (diffs)
- `pyproject.toml`, `requirements.lock` (incl. raw bytes), `config/default.yaml`, `.github/workflows/ci.yml`, `README.md`, `docs/cadquery-backend.md`, `docs/guide-settings-and-cloud.md`, `docs/guide-photo-onramp.md`, ROADMAP/HANDOFF Python-version mentions, `docs/audits/audit-lite-stage-{b,c,d}-2026-06-10.md`
