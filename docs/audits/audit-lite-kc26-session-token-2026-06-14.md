# Audit Lite — #31 / KC-26 session-token guard
**Date:** 2026-06-14
**Scope:** The session-token guard on state-changing requests — `webapp.py` (token param, do_POST 403 guard, shell-injection, `serve()` token), `shell.py` (desktop server), `frontend/index.html` + `api.ts` (read + send), the rebuilt SPA, and the new tests + docs.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ships. One Critical was found **and fixed within this pass** (the desktop WebView2 shell — the primary distribution — was starting the server *without* the token, so the guard was silently off in the packaged app). With that remediated and pinned by a test, the guard is sound: per-boot random token, constant-time compare, GET-exempt, off-by-default only for the test/embedding path, no method bypass.

## Severity rollup (after remediation)
- Blocker: 0
- Critical: 0
- Major: 0
- Minor: 0
- Nit: 0

## Findings

### FINDING-001 Critical (REMEDIATED): desktop shell ran with the guard off
**Dimension:** Correctness / Security
**Evidence:** `src/kimcad/shell.py:93` called `make_handler(pipeline, web_root, config=config)` with no `session_token`. The `kimcad web` path (`webapp.serve()`) generated + passed a token, but the WebView2 desktop shell (the main distribution) did not — so every state-changing request in the packaged app ran ungated.
**Why it matters:** The feature's whole point (defense-in-depth for the shipped app) was absent exactly where users run it.
**Fix path (done):** `shell.py` now generates `secrets.token_urlsafe(32)` and passes it to `make_handler`; the shell navigates to `http://127.0.0.1:{port}/` so the server injects it into the served shell and the SPA returns it. Pinned by `tests/test_shell.py::test_shell_server_enforces_the_session_token_guard` (tokenless POST → 403; injected token present; token → not 403).
**Blast radius:** Adjacent — the only two production server-start sites are `serve()` (already correct) and `shell.py` (now fixed); no other `make_handler` caller in src. Shared state: none. User-facing: none visible (the SPA already sends the token). Tests updated: added the shell guard test; existing shell tests unaffected.

## What's working
- **Constant-time compare** via `hmac.compare_digest`; a missing header coerces to `""` and fails closed (`webapp.py` do_POST guard).
- **Honest off-by-default**: the guard only engages when a token is configured; tests/embedding default to empty (no churn to the ~135 existing POST tests, verified green), and the guard is exercised by dedicated tests with a token set — not bypassed-and-untested.
- **GET-exempt is correct** — the guard is in `do_POST` only; GET/HEAD change no state. No `do_PUT`/`do_DELETE` exist, and the design delete is a guarded `POST .../delete`, so there's no method bypass.
- **Build reproducibility preserved**: the committed shell carries only the `__KIMCAD_SESSION_TOKEN__` placeholder; the token is substituted at serve time (`_serve_index_shell`), so a fresh build still byte-matches.
- **Tests**: backend guard + injection + default-open (`test_webapp.py`), 3 frontend header cases (`api.session-token.test.ts`), and the shell end-to-end guard test — all green.
- **Docs**: `docs/api.md` + `CHANGELOG.md` document the token AND why full CSRF is deliberately out of scope (single-user loopback, no cookie session to forge).

## Watch items
- The placeholder `__KIMCAD_SESSION_TOKEN__` is treated as "no token" by `api.ts` (covers the vite dev server, where the backend isn't gating) — correct, but worth keeping in mind if the dev server is ever pointed at a real backend.

## Escalation recommendation
No escalation needed — one Critical, local in scope, fixed and tested. (A full `audit-team` follows per the stage cadence regardless.)
