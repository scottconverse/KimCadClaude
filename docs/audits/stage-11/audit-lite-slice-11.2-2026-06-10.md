# Audit-lite — Stage 11 Slice 11.2: the in-app Connections card

- **Date:** 2026-06-10
- **Auditor:** Claude (independent single-pass, audit-lite discipline)
- **Scope:** Uncommitted working tree on top of the Slice 11.1 commit (`7eb18cb`).
  Files: `src/kimcad/connectors.py`, `src/kimcad/settings_store.py`, `src/kimcad/webapp.py`
  (GET/POST `/api/connections`), `frontend/src/components/ConnectionsCard.tsx` (+ test),
  `api.ts`, `SendPanel.tsx`, `SettingsPanel.tsx`, `FirstRunWizard.tsx`, `styles.css`,
  `tests/test_connections_api.py`. Build output (`src/kimcad/web/assets/*`) excluded.

## Verification (run, not assumed)

| Check | Result |
|---|---|
| `pytest tests/test_connections_api.py tests/test_connectors.py tests/test_webapp.py -q` | **161 passed** (61.8s) |
| `ruff check src tests` | **All checks passed** |
| `vitest run ConnectionsCard.test.tsx SendPanel.test.tsx SettingsPanel.test.tsx` (node22) | **3 files, 45 passed** (2.6s) |
| Overlay-read micro-benchmark (per `SettingsStore(path).all()` call, post-migration) | **0.07 ms** plain; **9.3 ms** when an OpenRouter key sentinel is present (per-call Windows Credential Manager hit) |

## Security review (the directed hunt)

All four directed probes came back clean:

1. **Whitelist integrity — HOLDS at all three layers.** The POST handler rejects any
   field outside `USER_CONNECTOR_FIELDS` with a typed 400 (`webapp.py:1252-1257`,
   tested); `apply_saved_connector_overrides` iterates only the whitelist at read time
   (`connectors.py:80-89`, tested with a tampered blob carrying `api_key_env`/`type`);
   `dataclasses.replace` therefore only ever receives `base_url`/`serial`/`use_ams`,
   all real `ConnectorConfig` fields (`config.py:91-101`). `name` is never writable —
   it's the lookup key, validated against `cfg.connectors()`.
2. **Settings-file tampering — degrades safely.** Nested dicts/non-strings fail the
   `isinstance` checks and are ignored; a non-dict `connectors` blob or broken JSON
   reads as "no overlay" (`_saved_connector_overrides` swallows everything; tested with
   `{not json`). No type confusion reaches the GET handler. Residual: unbounded string
   length at read time — see N-1.
3. **`env_set` oracle — none.** It is `bool(api_key_env and os.environ.get(...))`
   (`webapp.py:1221`); the value is never serialized, length never observable, and the
   empty-string-var case matches `build_connector`'s own falsy check. The test asserts
   the secret's value appears nowhere in the GET body.
4. **Remote `base_url` — by design and contained.** It's the printer's address; the
   Bambu host parse (`connectors.py:207`) just strips scheme/path/port. The
   vision/model-pull loopback guard (`webapp.py:1310`, `is_loopback_url`) guards the
   **LLM** `base_url` from the `llm:` config section — a different object entirely;
   the connector overlay cannot reach it. Confirmed unaffected.

Cross-caller propagation **verified**: `/api/connectors` (the send picker) →
`connector_is_configured` → `build_connector` → overlay applied (`webapp.py:883`,
`connectors.py:121-123`); same for CLI/MCP (any `build_connector` caller). The
cross-caller test (`test_connections_api.py:112-135`) proves it on a fresh `Config`.

Bonus checks: `BambuConnector.__init__` is field-assignment only (no network on the
GET handler's per-row `build_connector`); `/api/connections`' 405 `Allow` header is the
correct `GET, HEAD, POST` (via the default branch of `_method_not_allowed`); the
`setx`-then-restart guidance is technically honest (`setx` never affects the current
process; the card says "then restart KimCad" in the unset branch, `ConnectionsCard.tsx:127-130`).
Reset-all (`store.clear()`) **does** wipe the connectors blob — behavior correct; copy
disclosure is N-3. A11y on the new controls is solid: every input labeled via
`htmlFor`/`id`, the AMS toggle is a real `<button role="switch" aria-checked>` (fully
keyboardable), the save note is `role="status"`.

## Findings

Severity scale: Blocker / Critical / Major / Minor / Nit.

### Minor

- **M-1 — Minor — "Printer address (IP)" label + bare-IP placeholder breaks the HTTP-family connectors** — `frontend/src/components/ConnectionsCard.tsx:82-89`
  The one shared field is labeled "(IP)" with placeholder `e.g. 192.168.0.60` for
  **every** type, but octoprint/moonraker/prusalink pass `base_url` straight to urllib
  (`octoprint_connector.py:75`) and need a scheme (`http://octopi.local:5000`). A user
  following the placeholder on the OctoPrint row saves a scheme-less address that
  passes `build_connector`'s "non-empty" check (row reads **Ready**) and then fails at
  send/status time as a confusing "couldn't check"/offline. Bambu (the strip-the-scheme
  parse) is fine. Fix: per-type label/placeholder, or normalize (prepend `http://`)
  for the HTTP connectors at save or build time.
- **M-2 — Minor — connectors-blob read-modify-write races outside the store lock** — `src/kimcad/webapp.py:1262-1267`
  The POST handler reads the blob via `saved_settings()`, merges in-process, then calls
  `store.update(...)`. `_WRITE_LOCK` serializes the top-level write, but the blob merge
  happens outside it — two concurrent saves to different connections can lose one
  (the exact race class ENG-101 fixed inside the store, reintroduced one level up).
  Single local user clicking Save makes it unlikely; still, a `SettingsStore` merge
  callback or handler-level lock closes it cheaply.
- **M-3 — Minor — every `build_connector` call resolves the OpenRouter secret from the OS keyring** — `src/kimcad/connectors.py:99`
  `_saved_connector_overrides` uses `SettingsStore(...).all()`, which transparently
  resolves the `@keyring` sentinel. Measured: 0.07 ms per call with no cloud key, but
  **9.3 ms** once a key is saved — paid per connector on `/api/connectors`,
  per `connector-status` poll, and per send, and it materializes a billable secret in a
  code path that only needs the `connectors` key. Read the raw blob (a non-resolving
  accessor) instead. Functionally correct today; perf + least-privilege.

### Nit

- **N-1 — Nit — read-time whitelist accepts unbounded strings from a tampered file** — `src/kimcad/connectors.py:87-88`
  The 200-char cap is POST-only; a hand-edited settings file can plant a multi-MB
  `base_url` that flows into GET responses and error strings. The attacker is the local
  user (already owns the process), so defense-in-depth only: mirror the length cap at
  read time.
- **N-2 — Nit — the card vanishes silently when its GET fails, while SendPanel points at it** — `frontend/src/components/ConnectionsCard.tsx:36`
  On a `/api/connections` failure the card renders `null`; the send-flow copy still
  says "Settings → Printer connections". A one-line "couldn't load — reopen Settings"
  row would keep the venue honest in the failure mode.
- **N-3 — Nit — reset-all copy doesn't disclose that printer addresses/serials are wiped** — `frontend/src/components/SettingsPanel.tsx:532`
  `store.clear()` correctly drops the connectors blob, but "Reset all settings to
  defaults" predates connections being settings; a user may not expect their printer
  setup to be included. Mention it in the confirm.
- **N-4 — Nit — the card POSTs `use_ams` for non-Bambu rows** — `frontend/src/components/ConnectionsCard.tsx:43-46`
  `updates` always carries `use_ams`, so saving the OctoPrint row persists a
  meaningless `use_ams: true` into its blob (server accepts: the whitelist is not
  per-type). Harmless — the overlay sets a field octoprint never reads — but the test
  name promises "exactly the editable fields" and the AMS toggle isn't editable there.
- **N-5 — Nit — test gaps** — `tests/test_connections_api.py`, `frontend/src/components/SettingsPanel.test.tsx:47-50`
  (a) No route-level test that **`/api/connectors`** (the send picker) reflects a saved
  overlay — the logic is covered via `connector_is_configured`, the HTTP contract isn't.
  (b) No 405/Allow contract test for `/api/connections` — its correct `Allow: GET, HEAD,
  POST` currently comes from `_method_not_allowed`'s *default* branch (`webapp.py:793-794`);
  a future tightening of the path lists would regress it silently.
  (c) `ConnectionsCard` is never exercised through the SettingsPanel mount —
  `getConnections` is mocked to `[]` there, so the integration seam renders nothing.

## Severity rollup

| Blocker | Critical | Major | Minor | Nit |
|---|---|---|---|---|
| 0 | 0 | 0 | **3** | **5** |

## Escalation verdict

**No escalation — audit-lite suffices.** The slice's security posture is genuinely
sound: the three-layer whitelist holds under directed attack, the secret never crosses
the new surface in either direction, the env-set boolean leaks nothing, and the
loopback guards are untouched. All 161 backend + 45 frontend tests pass; ruff is clean.
The three Minors are real but small (one misleading field label that can strand HTTP-
connector users, one low-likelihood lost-update race, one measured 9.3 ms-per-call
keyring tax once a cloud key exists) — fix-forward items for the dev, none gating.
Per the standing 0/0/0/0/0 rule, all eight findings (M-1..M-3, N-1..N-5) should be
remediated before the Stage 11 gate.
