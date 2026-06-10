# Stage A Walkthrough — first-run hardening (commit 5aad7f3)
**Date:** 2026-06-10 · **Mode:** audit (runtime exploration + terminal probes) · **App:** demo server on :8701 + a real-mode server on :8703 · **Crucially:** the down-states were exercised against a **genuinely stopped Ollama**, not mocks, then recovery was verified after restart.

## Verdict
Stage A's promises hold at runtime. The worst pre-Stage-A experience (4 silent minutes → Python traceback) is now a **21-second, two-line, actionable failure** on the CLI and an **18.5-second typed `model_unavailable`** on the web — measured live. The wizard tells the truth in both directions, the landing pill appears/disappears with the real server state, and the demo design→gate→slice→download chain is fully wired (real OrcaSlicer slice, fetchable G-code). Two findings: one Major (the port-in-use guard never fires python-vs-python on Windows) and one Minor (SDK-internal retries stack under ours).

## What was exercised (evidence inline in session; key numbers recorded here)

| Surface | Check | Result |
|---|---|---|
| Wizard, healthy | 5 steps walked; step-1 health = "Ready"; recap "You're all set" + badge + 3 honest rows | PASS |
| Wizard, Ollama **stopped** | step-1 "Ollama isn't running" + finish-anyway line; recap demotes to **"Almost ready"**, no badge, Model row carries "not reachable yet — start Ollama, then check again", Start designing stays available | PASS (screenshot: mobile 375px — renders correctly) |
| Landing pill, Ollama stopped | `role=status` pill: "Your local AI isn't running yet — start Ollama to design. Check again" | PASS |
| Landing pill, Ollama restored | reload → pill silent | PASS |
| Skip link (UX-004) | present, first focusable, `href` resolves to the active `<main>` | PASS |
| CLI model-down (real) | `kimcad design` → **exit 2 in 21.2 s**, live phase line, friendly 2-line guidance incl. `ollama pull gemma4:e4b`, **no traceback** (was ~234 s + traceback) | PASS |
| Web model-down (real mode, :8703) | POST /api/design → **200 `model_unavailable` in 18.5 s** with the friendly message | PASS |
| Port-in-use (QA-006) | second `kimcad web` on :8701 → **no error, silent double-bind** | **FAIL → WALK-A-001** |
| Demo core flow | design completed → mesh 200 → gate pass → real slice (~50 m 21 s, 200 layers est.) → gcode 200 | PASS |
| Console hygiene | zero warnings/errors across all states | PASS |
| Docs cross-check | getting-started/troubleshooting quote the real port (8765 default), real button names, and the exact Slice-A1 error strings observed live | PASS |

## Findings

### WALK-A-001 — Major — The port-in-use guard never fires for python-vs-python on Windows
**Expected:** a second `kimcad web` on an occupied port prints "Port 8701 is already in use… pass `--port`" and exits 2 (Slice A1's QA-006 fix).
**Actual:** the second instance bound **silently** — `ThreadingHTTPServer` (via Python's `socketserver`) sets `allow_reuse_address`, which on Windows maps to `SO_REUSEADDR` and permits a second bind to share/steal the port. No error, no message; two servers fight over connections. The Slice A1 unit test passes only because its blocker socket sets `SO_EXCLUSIVEADDRUSE`, which forces the bind error the guard handles.
**Likely cause:** missing `allow_reuse_address = False` (Windows) on the server class.
**Fix:** subclass `ThreadingHTTPServer` with `allow_reuse_address = False` on win32 so the second bind raises deterministically and the existing friendly message fires. Add a python-vs-python regression test (start a real `serve()` thread, then a second on the same port).

### WALK-A-002 — Minor — OpenAI SDK internal retries stack under KimCad's retry loop
**Expected:** never-up fail-fast ≈ connect-timeout + probe ≈ ~7 s.
**Actual:** 21.2 s (CLI) / 18.5 s (web) — the OpenAI client defaults to `max_retries=2`, so each of *our* attempts is internally 3 connect cycles. Stacked with our 6-attempt loop, a listening-but-failing server pays up to 18 connect cycles.
**Fix:** pass `max_retries=0` in `_build_client` — KimCad's loop owns retry policy. Expect fail-fast to land ≈7 s.

## Test-coverage recommendations
- A python-vs-python double-bind regression test (WALK-A-001's fix).
- An assertion that the built client carries `max_retries=0` (WALK-A-002).

## Wiring/docs/design classification
All Stage A features: **implemented and working** (with WALK-A-001's guard "implemented but unreachable on Windows" until fixed). No cosmetic/stub surfaces found; no console errors; docs match observed behavior claim-for-claim.
