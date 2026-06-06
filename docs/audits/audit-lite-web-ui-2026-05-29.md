# Audit Lite — Phase-2 first slice (local web UI)
**Date:** 2026-05-29
**Scope:** New web layer — `src/kimcad/webapp.py`, `src/kimcad/web/index.html`, the `web` subcommand in `src/kimcad/cli.py`, and `tests/test_webapp.py`.
**Reviewer:** Claude (audit-lite)

## TL;DR
Ship-with-fixes. The slice is sound: a dependency-free web layer over the existing pipeline, with the prompt→result logic factored as a pure, unit-tested function and the backend verified end-to-end against real geometry (correct status, honest gate, exact 80/60/40 dims, served STL). Two Major gaps to close before it's "done": the new user-facing surface is undocumented, and the HTTP plumbing itself isn't in the automated suite. No security or correctness blockers.

## Severity rollup
- Blocker: 0
- Critical: 0
- Major: 2
- Minor: 2
- Nit: 1

## Findings

### FINDING-001 Major: New web UI is undocumented
**Dimension:** Docs
**Evidence:** `README.md` documents only the `design` and `bench` CLI verbs; the `web` subcommand and the whole browser surface added in `cli.py` / `webapp.py` are absent.
**Why it matters:** Doc-drift guardrail — an observable new feature with no docs means a user can't discover or run it, and a reviewer can't tell intended behavior from a bug.
**Fix path:** Add a "Web UI (Phase 2)" section to README: what `kimcad web` does, `--demo`, the localhost default, and the explicit-confirm/no-G-code-yet scope.

### FINDING-002 Major: HTTP layer not covered by the test suite
**Dimension:** Tests
**Evidence:** `tests/test_webapp.py` covers `design_response` thoroughly and asserts `make_handler` *builds*, but no test exercises `do_GET` / `do_POST` routing, `/api/mesh/<id>` serving, or the 400/404 paths over a real request. The HTTP behavior was verified manually (urllib) but that check isn't in the suite.
**Why it matters:** The routing, JSON serialization, and mesh-serving are the parts a refactor could silently break, and a manual check doesn't regression-protect them.
**Fix path:** Add a test that starts `ThreadingHTTPServer` on an ephemeral port with a fake-provider pipeline and asserts `GET /`, `POST /api/design`, `GET /api/mesh/<id>`, and a 404.

### FINDING-003 Minor: Clarification answer field has no label
**Dimension:** UX (accessibility)
**Evidence:** `index.html` — `#prompt` has `<label for="prompt">`, but `#answer` (the clarifying-question reply) has only a placeholder.
**Why it matters:** Placeholder-only inputs are an accessibility regression (screen readers, disappearing prompt text).
**Fix path:** Add a real `<label for="answer">`.

### FINDING-004 Minor: `--host` allows unauthenticated exposure
**Dimension:** Security
**Evidence:** `webapp.serve` defaults to `127.0.0.1` (good), but the `web` subcommand exposes `--host`; `--host 0.0.0.0` would serve the pipeline to the network with no auth.
**Why it matters:** A footgun if copied into a non-local context. Low risk given the localhost default and single-user local-first design.
**Fix path:** Document the localhost default and the "don't bind publicly without a proxy/auth" caveat in the README web section. (Keep the default; the flexibility is intentional for LAN dev.)

### FINDING-005 Nit: 500 handler echoes the exception string
**Dimension:** Correctness/Security
**Evidence:** `webapp.py` `do_POST` returns `f"{type(e).__name__}: {e}"` to the browser on unexpected error.
**Why it matters:** Mild info-exposure pattern in general — but this is a localhost, single-user dev tool with no server-side log (the handler silences `log_message`), so surfacing the error to the developer is *more* useful than hiding it.
**Fix path:** Keep as-is by design for the dev tool; revisit if/when the app is ever exposed beyond localhost. Recorded, not changed.

## What's working
- **Clean separation for testability:** `design_response` is a pure `PipelineResult → dict` mapping, so the full response shape is unit-tested with a fake provider and stub renderer — no LLM, binary, or socket (`tests/test_webapp.py`).
- **XSS-safe rendering:** the frontend uses `textContent` for plan/summary/headline/clarification and an `escapeHtml` helper for findings messages; no untrusted string hits `innerHTML` raw.
- **Honest scope on safety:** slicing/G-code is deliberately not triggered; the UI states G-code needs explicit confirmation (matches the spec's safety rule) and marks it next-slice rather than faking it.
- **Graceful 3D degradation:** if three.js fails to load, `viewerFallback` shows a message and the report UI is unaffected — the preview can't break the page.
- **Reuses tested wiring:** `build_web_pipeline` mirrors the CLI's pipeline construction rather than duplicating it; no path traversal in mesh serving (id→registry lookup, int-parsed).

## Watch items
- **three.js is loaded from a CDN** — works online, but breaks the 3D preview offline, which cuts against the local-first posture. Vendor it locally in a later slice (logged as a follow-up task).
- **In-memory mesh registry grows unbounded** over a long session. Fine for a local single-user tool; cap it if sessions get long.
- **Live 3D preview unverified at runtime** — backend + contract are verified; the WebGL render path was reviewed statically and has a fallback, but no browser screenshot was captured (preview tooling is rooted in a different workspace).

## Escalation recommendation
No escalation needed. Zero blockers/criticals, findings are local to the slice. audit-team is the right tool for the full Phase-2 chunk (end of phase), not this first slice.
