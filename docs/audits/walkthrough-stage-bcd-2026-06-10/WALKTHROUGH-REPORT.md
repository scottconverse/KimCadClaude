# Stage B/C/D Walkthrough — gate depth · trust boundary · UX polish (commit 5a07381)
**Date:** 2026-06-10 · **Mode:** audit · **App:** a real-mode server on :8711 with its home isolated to a scratch profile (the developer's real `~/.kimcad` untouched), plus terminal probes. All artifacts cleaned up (server stopped, scratch home deleted, **zero residue in the real Credential Manager** — verified).

## Verdict
The three stages' promises hold on the running product. The headline — the **keyring trust chain ran end-to-end against the real Windows Credential Manager**: a key saved through the real settings API landed in the vault (verified by direct vault read), the settings file held only the `@keyring` sentinel, the API disclosed `key_storage:"keyring"`, the response carried only the masked form (raw key grepped against the full response: absent), and clearing the key **removed the vault entry**. `--allow-remote` refusal verified live (exit 2, the full no-auth warning). All eight Stage-D copy surfaces ship in the served bundles, including the *absence* of the "Gate:" jargon.

## What was exercised

| Check | Result |
|---|---|
| Save key via real `/api/settings` (isolated home) | `saved=true`, `key_storage=keyring`, masked `…99812`, raw key **not** in response |
| At rest: `settings.json` | `"openrouter_api_key": "@keyring"` — sentinel only |
| At rest: real Windows Credential Manager | vault value == the saved key (direct `keyring.get_password` read) |
| Clear key via API | `has_cloud_key=false` AND the vault entry **gone** |
| `--allow-remote` gate (terminal, `--host 0.0.0.0`) | exit 2, refusal + no-auth warning, names the flag |
| Served-bundle copy (8 checks) | credential-store note ✓ · file-fallback note ✓ · Enter hint ✓ · proceed bridge ✓ · slice caution ✓ · connective line ✓ · photo-not-saved ✓ · "Gate:" jargon **gone** ✓ |
| Stage B suites executing | printability seam + trust-boundary + settings-store: 32 passed (the real-OpenSCAD pipeline test among them) |
| Cleanup | server stopped, scratch home removed, vault clean (verified) |

## Limitations (honest)
- **Warn-gate proceed bridge** and **landing-draft survival** were verified by their pinned unit tests + the served-bundle copy, not re-driven in a live browser this pass: the demo provider doesn't produce a warn-gate part on demand, and a real-mode cancel-mid-design costs a multi-minute model run for a micro-interaction the vitest already pins (abort → landing re-seeded + note). Both should get a glance in the Stage-11 beta-gate's full browser pass.
- The **file-fallback disclosure** (broken-vault path) was verified by unit test + bundle copy; deliberately not simulated against the real OS vault.

## Findings
**None new.** One observation for the audit-team roles: the SettingsPanel disclosure note has no dedicated vitest (the copy ships and the `key_storage` field is typed, but no test renders the note for both values) — flagged for the gate's Test role rather than fixed mid-walkthrough.

## Wiring classification
All Stage B/C/D features: **implemented and working** (two micro-interactions verified-by-unit as noted). No cosmetic surfaces, no dead controls, no console errors observed on the probed routes.
