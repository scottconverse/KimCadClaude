# Audit Lite — Stage A Slice 1: typed first-run errors + fail-fast (d917a98)
**Date:** 2026-06-10
**Scope:** Commit `d917a98` — `errors.py`, runner/slicer guards, provider timeout split + reachability probe, CLI error mapping + phase progress, webapp typed responses + 500 genericization, 13 new tests.
**Reviewer:** Claude (audit-lite) — adversarial self-review against six named risk vectors.

## TL;DR
Ship after one follow-up fix. Five of the six risk vectors verified clean; the sixth check surfaced that the QA-008 "no class-name leaks in 500s" fix is **incomplete** — the send and re-render handlers still emit `{type(e).__name__}: {e}` to the browser. One Minor, one Nit; both fixed in the re-audit pass before push.

## Severity rollup
- Blocker: 0 · Critical: 0 · Major: 0 · **Minor: 1** · **Nit: 1**

## Findings

### LITE-A1-001 — Minor: QA-008 fix incomplete — send + re-render 500s still leak the exception class name
**Dimension:** Correctness / Security (low-grade info leak)
**Evidence:** `webapp.py:1364` (`_handle_send` catch-all: `self._json(500, {"error": f"{type(e).__name__}: {e}"})` — with a comment citing an older audit decision that class+message is "the deliberate, tested contract") and `webapp.py:1930` (`_handle_render` catch-all, same shape). The design and slice handlers were converted to generic-message + server-side log in this slice; these two siblings were missed, so the leak contract is now inconsistent across the four POST handlers.
**Why it matters:** Same QA-008 rationale — internal class names + OS error strings are non-actionable for the user and a low-grade leak; and an inconsistent contract invites the next regression.
**Fix path:** Convert both to the new pattern (log via `self.log_error`, return the generic line); update the older send-handler test that pinned class+message; supersede the stale "deliberate contract" comment.

### LITE-A1-002 — Nit: CLI NotFoundError match is name-only — a non-openai `NotFoundError` would get model-pull advice
**Dimension:** Correctness
**Evidence:** `cli.py:512` `if type(e).__name__ == "NotFoundError":` — any library's `NotFoundError` reaching `main()` would print "pull the model first," which could mis-advise. Exit code (2) would still be right; only the advice text is at risk. No such class currently flows through the design path, so theoretical today.
**Fix path:** Also require `type(e).__module__.startswith("openai")` before giving model-specific advice.

## Adversarial checks that came back clean
1. **TCP probe vs slow-accept servers:** a listening-but-slow server passes the TCP probe (kernel accepts) even when the HTTP layer times out → full retry budget preserved; only a genuinely-refused/never-up port fails fast. `socket.create_connection` walks getaddrinfo, so IPv4/IPv6 dual-stack localhost is handled. Probe overhead on the fail-fast path ≤2 s.
2. **KeyboardInterrupt/SystemExit:** `except Exception` cannot catch them (BaseException-derived) — Ctrl-C and argparse exits pass through untouched.
3. **`log_error` availability:** a `BaseHTTPRequestHandler` method — both new call sites valid.
4. **FallbackProvider interaction:** with an alt configured, primary already ran `max_attempts=1`, so the fail-fast probe changes nothing in the handoff: primary raises (≤2 s slower worst-case), `_call` catches `APIConnectionError` and tries alt exactly as before. Verified at `llm_provider.py:404–449`.
5. **Hermeticity of the probe in tests:** all retry tests pin `_server_reachable`; the probe-behavior test uses its own ephemeral listener — no dependency on a live Ollama.

## What's working
- The sanitize-before-guard ordering decision (blocked code reports as blocked even with no tool installed) is the right contract and now has a dedicated regression test pinning it.
- CLI/web parity by construction: both surfaces consume `pipeline._is_model_unreachable` + `MODEL_UNAVAILABLE_MESSAGE`, so the two can't drift.
- 13 new tests all assert user-visible behavior (exit codes, stderr content, JSON shapes), not internals.

## Escalation recommendation
No escalation — both findings are local and fixed in the immediate re-audit pass below.

## Re-audit addendum (same date)
LITE-A1-001 and LITE-A1-002 fixed: send + re-render 500s genericized with server-side logging (older pinned test updated; stale contract comment superseded), and the CLI NotFoundError match now requires the `openai` module prefix. Suites re-run green. **0/0/0/0/0.**
