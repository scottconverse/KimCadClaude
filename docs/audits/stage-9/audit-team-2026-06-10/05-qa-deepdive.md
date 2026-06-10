# Runtime QA Deep-Dive — KimCad Stage 9 (image & sketch on-ramp + DesignRegistry seam)

**Audit date:** 2026-06-10
**Role:** QA Engineer
**Scope audited:** Stage 9 runtime behavior ONLY, at commit `e8339d9` — adversarial sketch-seed inputs (real model), demo canned-seed consistency, concurrency on the new `DesignRegistry` seam, vision read under a cancelled request, eviction under load. The real-model sketch/photo journeys, `kimcad models`, and the stale-guard journey were already proven in `docs/audits/walkthrough-stage-9-2026-06-10/WALKTHROUGH-REPORT.md` and were NOT redone.
**Environment:** Windows 11 Pro, venv Python 3.13.13, Ollama with `qwen2.5vl:3b` + `gemma4:e4b` installed. Real-mode server on `:8718`, demo server on `:8719`, a third demo server on `:8720` with `webapp.MAX_REGISTRY` runtime-patched to 5 (in-process patch via `python -c`; source untouched) for the eviction boundary. Every server ran with `USERPROFILE`/`HOME` pointed at a dedicated temp dir and its cwd inside that dir, so `~/.kimcad` and `output/web` never touched the real profile or the repo. All servers killed and all temp dirs removed at the end (verified: ports closed, dirs gone, real `~/.kimcad` mtime predates the session).
**Auditor posture:** Adversarial

---

## TL;DR

Stage 9's runtime holds up under deliberate abuse. The sketch-seed endpoint turned every adversarial body into the correct clean 4xx (400 empty / 413 oversized / 422 unreadable — twice), with zero 500s; the demo canned path is deterministic and instant; ten parallel designs and ten parallel re-renders on one rid through the new `DesignRegistry` produced unique rids, coherent state, and hash-verified last-wins geometry; and the eviction protocol is exact at the boundary (evicted → 404 + dir removed, live → 200 + dir present). The two findings are both Minor and share one root: a client-cancelled vision read — a first-class UI flow, since the on-ramp's Cancel button aborts the fetch — dumps a full socketserver traceback into the server terminal and leaves the abandoned model read running, which slows the user's own retry. The server stayed healthy throughout; no security or data issues surfaced.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 0 |
| Major | 0 |
| Minor | 2 |
| Nit | 0 |

## What's working

- **The 12 MiB upload cap is real and pre-read** — a 13 MB body got `413 {"error": "File too large."}` in **1.6 ms** (rejected off the Content-Length header, never buffered), per `_read_raw_body`'s declared-length guard.
- **No adversarial input produced a 500 or a handler traceback** — 0-byte → `400 Empty upload.` (1.5 ms); text bytes labeled `image/png` → `422 Couldn't read that sketch…` (7.4 s, real model round-trip); truncated PNG (first third of a valid file) → same 422 (2.5 s). The `cant_read` message correctly blames neither the server nor a healthy model.
- **Demo canned sketch-seed is consistent and instant** — two POSTs returned the byte-identical rectangular-bracket seed in **2.2 ms / 1.8 ms**.
- **The DesignRegistry seam is coherent under parallel load** — 10 simultaneous `POST /api/design` completed in **0.62 s wall**, all 200, all 10 rids unique (`new_rid` under the lock holds), and all 10 `GET /api/mesh/<rid>` returned 200 with full mesh bytes.
- **Last-wins on concurrent re-renders, proven by hash** — 10 parallel `POST /api/render/13` with distinct widths: all 200, version-suffixed `mesh_url`s `?v=1..10` with no gap or duplicate, **1.71 s wall** (serialized by `render_lock`, individual 0.31–1.70 s). The final `GET /api/mesh/13` byte-hash equals a fresh deterministic render at the last-completed width (`338a73bf…` both) — the registered mesh is exactly the last writer's.
- **Server survives a mid-vision client abort** — after killing the connection 2 s into a real sketch read, `GET /api/health` answered 200 in **1.7 ms** and the next full sketch-seed completed 200. Per-request thread isolation (ThreadingHTTPServer) contains the damage. (But see QA-901/902.)
- **Eviction protocol is exact at the boundary** — with the cap patched to 5 and 7 designs driven: rids 1–2 → `GET /api/mesh` **404** and `output/web/1`,`/2` **removed from disk**; rids 3–7 → **200** and dirs present. `evict_locked` + `enforce_caps_locked` do what the Stage 9 extraction promises, including the on-disk half.
- **Under the shipped cap nothing is evicted prematurely** — 21 designs on the demo server (cap 50): rids 1, 2, 3, 13 and the newest all 200; all 21 `output/web/<rid>` dirs present.
- **Home isolation honored** — both servers wrote designs/settings only under the temp `USERPROFILE`; the real `~/.kimcad` mtime (04:22, pre-session) confirms zero leakage.

## What couldn't be assessed

- **Real-mode `/api/design` concurrency** — out of scope (LLM-bound, minutes per design); concurrency was exercised on the demo provider, which is the same handler/registry code path with a fast provider.
- **Whether the abort is seen by Ollama** — the provider call ran to completion after the client vanished (see QA-902); whether Ollama *could* be told to stop (request cancellation on its API) wasn't probed.
- Browser-level behavior of the on-ramps — already proven live in the walkthrough; not redone per scope.

---

## Product shape

A local, single-user web server (`kimcad web`) exposing a JSON API + SPA over a text/photo/sketch → DesignPlan → mesh → slice → send pipeline. Stage 9 added the sketch on-ramp (`POST /api/sketch-seed`, vision-read by local Ollama) and extracted all per-design server state into `DesignRegistry` (`src/kimcad/design_registry.py`). QA therefore focused on the API surface under adversarial input, concurrency on the new seam, and the lifecycle (eviction) behavior — the layers the walkthrough's happy-path journeys didn't stress.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Sketch-seed, real model, valid PNG (post-abort retry) | Pass — 200 with a seed | QA-902 (latency) |
| Demo canned sketch-seed ×2 | Pass — identical seed, ~2 ms | — |
| 10 parallel designs → 10 mesh fetches (demo) | Pass — all 200, rids unique | — |
| 10 parallel re-renders on one rid (demo) | Pass — all 200, last-wins hash-verified | — |
| 8 sequential designs under cap → oldest rids/dirs persist | Pass | — |
| 7 designs past a patched cap of 5 → boundary check | Pass — 404+dir-gone vs 200+dir-present, exact | — |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| `POST /api/sketch-seed`, 0-byte body | 400 "Empty upload.", 1.5 ms | — |
| Text bytes with `Content-Type: image/png` | 422 cant-read, 7.4 s, no 500/traceback | — |
| 13 MB body (over the 12 MiB cap) | 413 "File too large.", 1.6 ms, never read | — |
| Truncated PNG (valid header, body cut at 1/3) | 422 cant-read, 2.5 s | — |
| Connection aborted 2 s into a real vision read | Server healthy (health 200 in 1.7 ms; next read 200) — but a full traceback in server output and the abandoned read kept running | QA-901, QA-902 |

---

## Findings

> **Finding ID prefix:** `QA-` (9xx series to stay clear of prior stages' QA ids)

### [QA-901] — Minor — Console — A user's Cancel during a vision read prints a full traceback in the `kimcad web` terminal

**Evidence**
1. Start a real-mode server: `kimcad web --port 8718` (isolated `USERPROFILE`).
2. `curl --max-time 2 -X POST -H "Content-Type: image/png" --data-binary @full.png http://127.0.0.1:8718/api/sketch-seed` — curl aborts at 2 s while the local vision model is still reading.
3. When the read finishes (seconds later), the handler's `self._json(200, …)` write hits the dead socket and socketserver prints ~30 lines to the server terminal: `Exception occurred during processing of request from ('127.0.0.1', 58955)` … `webapp.py line 1444 _handle_sketch_seed` … `ConnectionAbortedError: [WinError 10053]`.
4. This is not an exotic client: the on-ramp UI's Cancel button exists *specifically* for slow reads ("the read can take ~15-20s on CPU — they must be able to back out", `frontend/src/components/PhotoOnramp.tsx:72-74`) and `cancelRead()` calls `AbortController.abort()`, which closes the fetch — so **every UI cancel (and every tab close) mid-read reproduces this**. Unmount aborts too (`PhotoOnramp.tsx:107`).

Observed: 30-line internal traceback in the terminal on a designed-for user action. Expected: at most one quiet log line ("client disconnected before the response"), consistent with the project's own terminal-message discipline (QA-008 / QA-A-004 keep that channel curated because it's where users are sent for "the detail").

**Why this matters**
The terminal is the product's official detail channel for non-technical beta users ("The terminal running `kimcad web` has the detail"). A scary traceback on a normal Cancel erodes exactly the trust that discipline was built to protect, and repeated cancels bury any *real* error in noise. Functionally harmless — the thread dies cleanly and the server keeps serving.

**Blast radius**
- Adjacent code: every response-writing path shares `_send` (`webapp.py:809`) — a client that disconnects mid-download of a large mesh/G-code (`_serve_mesh`, `_send_download`) will print the same dump. The fix belongs at one seam: override `handle_error` on the handler (or wrap `_send`'s `wfile.write`) to swallow `ConnectionAbortedError`/`ConnectionResetError`/`BrokenPipeError` with a one-line log.
- User-facing: terminal output only; no API/UX change.
- Tests to update: none known; a new unit test can simulate a closed `wfile`.
- Related findings: QA-902 (same trigger, different symptom).

**Fix path**
Recommend overriding `handle_error` in the `Handler` class (or `_ExclusiveBindServer`) to log one line for client-disconnect exception types and defer to the default for everything else. ~10 lines + a test.

### [QA-902] — Minor — Performance — An aborted vision read keeps the model busy, so the user's own retry queues behind it

**Evidence**
1. Same setup as QA-901; abort a sketch read at 2 s.
2. Immediately POST the same sketch again.
3. Observed: the retry took **25.6 s** end-to-end versus a **7.4 s** baseline for the identical image on the same server minutes earlier (walkthrough baseline: 9 s) — the abandoned read ran to completion inside Ollama and the GPU/CPU only then served the retry.

**Why this matters**
Cancel-then-retry is the natural gesture the Cancel button invites ("that's taking too long → cancel → try a clearer photo"). On the CPU-class machines the UI comment plans for (15–20 s reads), the retry can wait roughly double, which reads as "cancelling made it slower." No correctness impact: the late result is written to a dead socket and discarded; nothing is persisted.

**Blast radius**
- Adjacent code: `_handle_photo_seed` has the identical structure (`webapp.py:1372`), and `/api/design` in real mode shares the can't-cancel-the-provider property (longer-running, but its UI cancel has the same server-side semantics).
- Shared state: the per-request thread stays alive for the duration; ThreadingHTTPServer is unbounded, so stacked cancels grow threads (bounded in practice by model serialization).
- User-facing: retry latency after a cancel; nothing else.
- Migration: none.
- Related findings: QA-901 (same root: client cancellation isn't propagated server-side).

**Fix path**
Cheap first step: document/accept (single-user local server; the queue is the user's own). Real fix: pass a cancellation signal into the provider's vision call (Ollama's HTTP API drops generation when its client connection closes, so closing the provider-side request on client abort would free the model). Worth a Stage-10 note rather than a rushed change.

---

## Performance snapshot

| Metric | Observed | Verdict |
|---|---|---|
| 413 / 400 guard rejections (sketch-seed) | 1.5–1.6 ms | pass — pre-read, no buffering |
| Real vision 422 on garbage / truncated image | 7.4 s / 2.5 s | pass — model round-trip, in family with the 9 s happy-path baseline |
| Real vision 200 (queued behind an abandoned read) | 25.6 s | QA-902 |
| Demo canned sketch-seed | ~2 ms | pass |
| 10 parallel `POST /api/design` (demo), wall | 0.62 s | pass |
| 10 parallel `POST /api/render` on one rid, wall | 1.71 s (0.31–1.70 s each, serialized) | pass |
| `GET /api/mesh/<rid>` | 3–5 ms (one 515 ms outlier under the parallel burst) | pass |
| 8 sequential demo designs | 1.38 s | pass |
| `GET /api/health` | ~2 ms (incl. immediately after an abort) | pass |

## Security / privacy snapshot

Nothing new surfaced. The oversized-body guard rejects without reading (no memory amplification); error bodies leak no internals (the 422/400/413 strings are user-vocabulary); the cancelled-request traceback goes to the local terminal only, never the wire; isolated-home runs confirm the on-ramps persist nothing.

## Console and log observations

Across ~60 requests on three servers: exactly **one** traceback in server output (QA-901's `ConnectionAbortedError`), zero handler-level tracebacks for any adversarial body, zero unexplained log lines. Demo servers' logs were empty (stdout buffering of the banner under redirection — cosmetic, not assessed further).

## Patterns and systemic observations

- The `_read_raw_body`/`_read_json_body` guard pattern is consistent and correct across both upload endpoints — the 4xx vocabulary (400 empty / 413 oversized / 422 unreadable / 200-with-status for a down model) held everywhere it was poked.
- The DesignRegistry extraction did not regress any concurrency behavior reachable in demo mode: rid uniqueness, registry coherence, last-wins, lockstep eviction including disk — all observed live, matching the five protocol unit tests' claims.
- Both findings share one root (client abort isn't a modeled event server-side) — one seam, one coordinated fix.

## Appendix: environments and artifacts

- Windows 11 Pro (10.0.26200); repo venv Python 3.13.13; commit `e8339d9` (clean tree apart from untracked audit dirs).
- Ollama serving `qwen2.5vl:3b` (vision) locally; real OpenSCAD/OrcaSlicer present (`/api/health` true/true) but slicing out of scope.
- Servers: `:8718` real, `:8719` demo, `:8720` demo with `MAX_REGISTRY=5` patched in-process. Each with `USERPROFILE`/`HOME`/cwd in a dedicated `%TEMP%\kimcad-qa-*` dir.
- Tools: curl 8.x, Python `urllib` + `ThreadPoolExecutor` (10 workers), SHA-256 mesh comparison.
- Payloads: 0-byte file; 70-byte text file; 13,631,488-byte zero file; 793-byte Pillow PNG; its first 264 bytes as the truncated PNG.
- Teardown verified: all three PIDs stopped, ports 8718–8720 closed, all four `kimcad-qa-*` temp dirs removed, real `~/.kimcad` untouched (mtime 04:22, pre-session).
