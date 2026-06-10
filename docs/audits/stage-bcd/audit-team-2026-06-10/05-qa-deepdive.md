# Runtime QA Deep-Dive — KimCad (Stage B/C/D scope)

**Audit date:** 2026-06-10
**Role:** QA Engineer
**Scope audited:** Stage B/C/D runtime behavior at commit `5a07381` — the keyring trust chain under adversity, settings-API concurrency, API reset vs. the vault, the `--allow-remote` ACCEPT path, the bench model-down exit (QA-A-001), and the OpenSCAD secret-scrub in a real render. Deliberately NOT redone (walkthrough already verified live): the happy-path keyring chain against the real Windows Credential Manager, the `--allow-remote` refusal, and the served-bundle copy checks — see `docs/audits/walkthrough-stage-bcd-2026-06-10/WALKTHROUGH-REPORT.md`.
**Environment:** Windows 11 Pro, Python 3.13.13 (project `.venv`), `kimcad web --demo` on loopback ports 8712–8715. **Every server ran with its home isolated** (`USERPROFILE`/`HOME` → a scratch dir under `%TEMP%\kimcad-qa-bcd`) **and its keyring isolated** (`PYTHON_KEYRING_BACKEND` → a QA file-backed backend, or `keyring.backends.fail.Keyring` for the broken-vault rig). The real `~/.kimcad` and the real Credential Manager were touched read-only, ever (baseline: no `KimCad` vault entry before the audit; none after).
**Auditor posture:** Adversarial

---

## TL;DR

The Stage C trust boundary holds up under deliberate abuse. A key whose literal value is the `@keyring` sentinel round-trips correctly; a 1000-char key and a unicode/quotes/emoji key round-trip byte-exact; 50 parallel `POST /api/settings` writes never tore the sentinel or leaked a raw key into the file; an API reset wipes the vault entry; the `--allow-remote` accept path serves and prints the no-auth warning; `kimcad bench` against a dead-port backend exits 2 with one friendly model-down line naming the configured model; and a real demo design + slider re-render works with a planted `OPENROUTER_API_KEY` in the server env — which the shared scrub provably strips from child environments and which never appears in any API response. Two Minor robustness findings (an optimistic pre-save `key_storage` disclosure when the keyring backend is broken, and a BOM-intolerant settings reader that also blocks the plaintext migration) and one Nit. No Blocker/Critical/Major.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 1 |

## What's working

- **Sentinel collision survives** — saved the literal string `@keyring` as the API key via `POST /api/settings`: `saved=true`, file holds the sentinel, the isolated vault holds the literal value, and a follow-up GET resolves it (`has_cloud_key=true`, fully-masked). No corruption, no false "no key" state.
- **Hostile key values round-trip** — a 1000-char key (vault length 1000, byte-exact round-trip, masked tail `KTAIL`) and `sk-or-"мир"-🔑-o'quote-終わり` (exact round-trip incl. emoji + both quote styles; raw value absent from the JSON file).
- **Concurrency holds** — 25 rounds of two truly-parallel `POST /api/settings` (competing key writes + a printer/cloud_enabled change riding along): 50/50 HTTP 200, the file held exactly `"openrouter_api_key": "@keyring"` after (never a raw key, never a torn write), the vault held one whole final-round value (`CONCUR-KEY-B-24`), and the follow-up GET was coherent. The store's `_WRITE_LOCK` + atomic `os.replace` discipline works on the threaded server.
- **API reset wipes the vault** — `POST /api/settings {"reset":true}` → `saved=true`, `has_cloud_key=false`, `settings.json` is `{}`, **and the vault entry is gone** (isolated vault file empty).
- **Legacy plaintext migration, live** — pre-seeded a scratch home's `settings.json` with a plaintext key; on server start the key moved into the (isolated) vault, the file was rewritten with the sentinel, and `cloud_enabled` survived. First GET: `has_cloud_key=true`, `key_storage=keyring`.
- **Broken-vault file fallback discloses honestly at save time** — with `keyring.backends.fail.Keyring` forced, a key save returns `saved=true, key_storage="file"`, the key lands in the JSON file, and the raw key is absent from the response. (Pre-save disclosure is the Minor QA-D-001 below.)
- **`--allow-remote` ACCEPT path** — `kimcad web --demo --host 0.0.0.0 --allow-remote --port 8713` binds and serves (`/api/health` 200 via loopback) and prints exactly the promised stderr warning: `WARNING: serving on 0.0.0.0 with NO authentication - anyone on this network can use this KimCad, including sending prints.` Server killed immediately after the probe.
- **Bench model-down (QA-A-001 fix), live** — added a temporary `qa_deadport` backend (`http://127.0.0.1:1/v1`) to the gitignored `config/local.yaml` (restored byte-identical afterward, hash-verified) and ran `kimcad bench --backend qa_deadport --prompts <one-case file>`: **exit 2**, one friendly "couldn't reach your local AI" message, recovery advice naming the *configured* model (`ollama pull qa-no-such-model` — UX-A-003 honored), no per-case `APIConnectionError` spam, no traceback, fail-fast (seconds).
- **OpenSCAD scrub doesn't break rendering** — server started with `OPENROUTER_API_KEY=QA-FAKE-PLANTED-SECRET-0xDEADBEEF` planted: demo design (`POST /api/design`, a 40×30×20 box) returned a mesh (`GET /api/mesh/1` → 200, 1284 bytes) and a slider re-render (`POST /api/render/1 {"values":{"width":55}}`) returned fresh geometry — both paths run the real bundled OpenSCAD child under `scrubbed_env()`. Direct check: with the key planted, `scrubbed_env()` omits `OPENROUTER_API_KEY` and keeps `PATH`. The planted secret appears nowhere in either API response.
- **Masking discipline under all of the above** — every response carried only `cloud_key_masked` (last-5 or full-dots for short keys); grep for each raw test key across captured responses: absent.

## What couldn't be assessed

- **Real-WinVault behavior under the adversarial inputs.** The standing constraint for this audit is read-only against the real Credential Manager, so the adversity battery ran against an isolated file-backed keyring backend (full `set/get/delete` chain through the real `keyring` API). The real-vault happy chain was already live-verified by the walkthrough. One real-backend property this leaves untested live: WinVault's credential-blob cap (2560 bytes; passwords stored UTF-16, so ≈1280 chars). Static read: an over-limit `set_password` raises, `SettingsStore.update()` catches it, falls back to file storage, and `key_storage()` discloses `"file"` — the designed degradation, but not exercised against the real backend.
- **External reachability of the 0.0.0.0 bind.** Verified the bind + warning + loopback service; did not probe from another machine on the LAN (no second host in the rig; Windows Firewall policy would dominate the result anyway).

---

## Product shape

A local-first CLI + loopback web app (threaded `http.server` serving a Vite SPA and a JSON API) that turns plain-English prompts into printable 3D models via OpenSCAD/CadQuery, with an opt-in cloud LLM whose key is the only durable secret. QA therefore focused on the API contract around that secret (at rest, in transit, under concurrency, on reset), the explicit network-exposure gate, the CLI's failure UX, and the secret hygiene of the geometry subprocesses.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Save → read → clear key via `/api/settings` (isolated keyring) | Pass | — |
| Legacy plaintext `settings.json` → startup migration | Pass | QA-D-002 (BOM edge found en route) |
| Broken vault → save key → file fallback + disclosure | Pass at save time | QA-D-001 (pre-save) |
| Settings reset (`reset:true`) → vault entry removal | Pass | — |
| `kimcad web --host 0.0.0.0 --allow-remote` (accept path) | Pass | — |
| `kimcad bench` with unreachable backend (dead port) | Pass (exit 2, friendly) | — |
| Demo design → mesh → slider re-render with planted secret | Pass | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Key value literally `"@keyring"` (sentinel collision) | Round-trips correctly; no corruption | — (Nit QA-D-003 on the hand-edit variant) |
| 1000-char key | Byte-exact round-trip; sentinel in file | — |
| Unicode + single/double quotes + emoji key | Byte-exact round-trip | — |
| 50 parallel POSTs (competing key writes + mixed fields) | 50× 200; sentinel intact; one whole winner; coherent GET | — |
| Broken keyring backend (`fail.Keyring`) before any save | GET claims `key_storage:"keyring"` | QA-D-001 |
| Hand-written settings.json with UTF-8 BOM | All settings silently ignored; migration skipped | QA-D-002 |
| Planted `OPENROUTER_API_KEY` in server env during real renders | Render + re-render work; secret in no response; scrub strips it from child env | — |

---

## Findings

### [QA-D-001] — Minor — Security/Flow — Pre-save `key_storage` disclosure says "keyring" even when the keyring backend is broken

**Evidence**
1. Start the server with a present-but-broken backend: `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring`, home isolated, `kimcad web --demo --port 8714`.
2. `GET /api/settings` (no key saved yet) → `key_storage: "keyring"`.
3. `POST /api/settings {"openrouter_api_key":"FILE-FALLBACK-KEY-12345"}` → `saved:true, key_storage:"file"`, key stored raw in `settings.json`.

Observed: before the first save, the Settings screen's disclosure claims the OS credential store; the actual save lands in the file. Expected: the no-key branch reports where a key would *actually* go. Root cause: `SettingsStore.key_storage()` (src/kimcad/settings_store.py:121-130) and `_keyring()` treat "the module imports" as "the backend works"; `fail.Keyring` (and some misconfigured backends) import fine and fail only on use.

**Why this matters**
A user on a machine with a broken/locked credential store reads "your key will be stored in the Windows credential store" while typing a billable secret that will land in a plaintext JSON file. The post-save disclosure corrects itself — so the window is the pre-save view only — but Stage C's whole point was honest disclosure.

**Blast radius**
- Adjacent code: `_keyring()` is also the health probe for `update()` and `all()` (src/kimcad/settings_store.py:60-68); a probe-on-use fix there is shared. `webapp.settings_response()` just passes the value through — no change needed.
- User-facing: the SettingsPanel credential-store note flips from optimistic to accurate on broken-vault machines; no change on healthy ones.
- Tests to update: settings-store unit tests that monkeypatch the keyring module; add a fail-backend case for the no-key branch. Dovetails with the walkthrough's note that the SettingsPanel disclosure note has no dedicated vitest for both `key_storage` values.
- Related findings: none in this report; cross-reference the walkthrough's deliberately-skipped live broken-vault check (now done here).

**Fix path**
In `key_storage()`'s no-key branch (and optionally in `_keyring()`), verify the backend is usable — e.g. `keyring.get_keyring()` is not a `fail.Keyring` instance, or wrap a cheap `get_password(_KEYRING_SERVICE, "__probe__")` in try/except and report `"file"` on failure.

### [QA-D-002] — Minor — Flow — A UTF-8-BOM `settings.json` is silently ignored, which also blocks the plaintext-key migration

**Evidence**
1. Write `~/.kimcad/settings.json` containing `{"openrouter_api_key": "LEGACY-PLAINTEXT-KEY-99", "cloud_enabled": true}` **with a UTF-8 BOM** (e.g. PowerShell 5.1 `Out-File -Encoding utf8`, or legacy Notepad "UTF-8 with BOM") into a fresh isolated home.
2. Start `kimcad web --demo`; `GET /api/settings`.

Observed: `has_cloud_key:false`, `cloud_enabled:false` — every saved setting ignored — and the one-time plaintext→keyring migration never runs, so the billable key stays in plaintext on disk while the UI reports no key at all. Re-running the identical scenario with a BOM-less file migrates correctly (key into vault, sentinel written, `cloud_enabled` preserved). Root cause: `_read_raw()` (src/kimcad/settings_store.py:113-119) does `json.loads(read_text(encoding="utf-8"))`; `json.loads` rejects a leading U+FEFF, the broad except returns `{}`.

**Why this matters**
The store is documented as degrade-don't-break, and it does degrade — but this particular degradation hides a real secret on disk (the migration that exists to fix exactly this file never fires) and silently discards the user's saved choices. Windows hand-edits with BOM-writing editors are the realistic trigger. Same pattern likely affects the history/design stores' JSON reads.

**Blast radius**
- Adjacent code: any `read_text(encoding="utf-8") + json.loads` reader of user-editable files — check `history.py`, `design_store.py` (meta.json), which share the best-effort pattern.
- User-facing: hand-edited settings silently revert to defaults today; after the fix they load.
- Migration: none — `utf-8-sig` reads both BOM'd and clean files; the writer is unchanged.
- Tests to update: none break; add a BOM round-trip case to the settings-store suite.
- Related findings: QA-D-001 (same file/keyring seam).

**Fix path**
Read with `encoding="utf-8-sig"` in `_read_raw()` (one-line), and consider the same for the sibling stores.

### [QA-D-003] — Nit — Flow — A hand-placed literal `@keyring` value with no vault entry reads as "no key" while `key_storage` reports "keyring"

Static observation (code-read; the API-save path was live-verified safe above): if a user hand-edits `settings.json` to `"openrouter_api_key": "@keyring"` without a vault entry, `all()` pops the key (correct: there is no key) but `key_storage()` reports `"keyring"`. Benign — flagging once for completeness; no blast radius warranted.

---

## Security / privacy snapshot

- No raw key in any API response across every scenario (grep for each planted/saved test value: absent everywhere; masking is last-5, full-dots for short keys).
- Planted `OPENROUTER_API_KEY` provably stripped from geometry-child environments (`scrubbed_env()` direct check) without breaking the real OpenSCAD render/re-render.
- The unauthenticated-exposure gate behaves on both sides: refusal (walkthrough) and explicit accept + loud stderr warning (this audit).
- QA-D-001/002 are the only secret-adjacent soft spots found; both Minor, both edge-conditioned.

## Console and log observations

Server stderr stayed empty across all rigs except the intended `--allow-remote` warning (the handler intentionally quiets request logging via `log_message`). No tracebacks, no 5xx observed in any scenario; the lone 500-path (re-render failure) was never triggered.

## Patterns and systemic observations

- The "best-effort, never raise" store discipline is consistently real under abuse — its one cost is QA-D-002's silent-`{}` failure mode: *unreadable* and *absent* are indistinguishable.
- `_keyring()`'s import-equals-healthy assumption is the single root of both the pre-save disclosure gap and the (correctly handled) save-time fallback; one probe-on-use fix covers it.
- Test-harness note for reproducers: PowerShell 5.1 `New-Object` argument-mode parsing and `Out-File -Encoding utf8` BOMs both produced false failures before being identified as harness artifacts; the repro steps above use the corrected forms.

## Appendix: environments and artifacts

- Rig: Windows 11 Pro; project `.venv` Python 3.13.13; servers on 127.0.0.1:8712 (main, planted secret), :8713 (`0.0.0.0 --allow-remote`), :8714 (fail.Keyring), :8715 (migration); demo provider throughout (real OpenSCAD binary, no LLM).
- Isolation: per-rig scratch `USERPROFILE`/`HOME` under `%TEMP%\kimcad-qa-bcd\home*`; keyring via `PYTHON_KEYRING_BACKEND` → a QA JSON-file backend (full keyring API) or `keyring.backends.fail.Keyring`.
- Tools: `Invoke-RestMethod` / `System.Net.Http.HttpClient` (true parallel POSTs), curl, direct file/vault inspection between every step.
- `config/local.yaml` was temporarily extended with the `qa_deadport` backend for the bench check and restored byte-identical (SHA-256 match verified).
- Cleanup verified at audit end: all four servers down (port probes + process list), `%TEMP%\kimcad-qa-bcd` deleted, real Credential Manager has **no** `KimCad` entry (read-only check; matches the pre-audit baseline), real `~/.kimcad` unchanged (two pre-existing designs, no newer files), `git status` shows only the audit report directories.
