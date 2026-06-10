# Audit Lite — Stage C: trust boundary (ENG-001/002/003/008, DOC-005/010)
**Date:** 2026-06-10
**Scope:** Keyring-at-rest for the OpenRouter key (sentinel file contract, one-time plaintext migration, disclosed file fallback, UI disclosure in Settings + wizard, API `key_storage`); `--allow-remote` gate for non-loopback binds; shared `subprocess_env` secret scrub now covering the OpenSCAD child; the photo-local-routing pin; two new user guides; README layout + key-storage copy.
**Reviewer:** Claude (audit-lite) — adversarial self-review.

## TL;DR
Ship. The three trust-posture findings from the original audit are closed *and defended*: the billable key now lives in Windows Credential Manager (verified by a live round-trip on this box, `WinVaultKeyring`), a non-loopback bind is an explicit, warned act, and the OpenSCAD child runs with the same secret-scrubbed environment as the CadQuery worker from one shared module. The suite is hermetic against the real credential store (a conftest autouse fake), and the two legacy tests that asserted plaintext-at-rest were updated to assert the *opposite* — the secret must NOT be in the file.

## Severity rollup
Blocker 0 · Critical 0 · Major 0 · Minor 0 · Nit 0 — **0/0/0/0/0**

## Adversarial checks performed
- **Test hermeticity vs the real vault:** without the autouse fake, the existing webapp cloud-key tests would have written to the developer's real Credential Manager. Caught at design time; `_fake_keyring` (conftest, autouse) guarantees no test touches the OS store. The one intentional live probe ran outside pytest and cleaned up after itself.
- **Sentinel edge cases:** sentinel-with-missing-vault-entry reads as "no key" (never the literal `@keyring` as a key); a broken backend on read degrades to absent; a broken backend on write falls back to the file AND `key_storage()` reports `"file"` so the UI discloses it — tested in all three directions.
- **Migration safety:** init-time migration is best-effort under the write lock; a migration failure leaves the legacy file functional and disclosed. Reset/clear deletes the vault entry too (tested).
- **ENG-002 bypass surfaces:** `serve()` is also importable directly — the gate lives in the CLI by design (the CLI is the user surface; a programmatic caller is a developer who read the docstring). `--host ::1`/`127.0.0.2` correctly need no flag; `myhost.local`/`0.0.0.0`/`::` are gated (parametrized tests).
- **ENG-003 look-alikes:** `TOKENIZER_PATH` survives the scrub in the planted-secret test; the shared-module identity test pins that the two runners can't drift (`_is_secret_env is subprocess_env.is_secret_env`).
- **ENG-008:** the local-only photo promise is now a test, not a wiring convention — cloud fully enabled + configured, `describe_photo` still routes local.
- **Guides' claims verified:** "never your photo", "key in Credential Manager", "reset deletes it", "no metering" — each matches the code shipped in this same commit.

## Tests
18 new/updated (6 keyring store + 2 webapp contract updates + 12 trust-boundary [gate/scrub/photo]); ruff clean; webapp+settings+trust+cadquery suites 189 passed; typecheck + vitest 297 + byte-exact build.

## Escalation recommendation
No escalation.
