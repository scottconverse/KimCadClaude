# Runtime QA Deep-Dive — KimCad Stage 8.5 Slice 1 ("My Designs" persistence + library)

**Audit date:** 2026-06-03
**Role:** QA Engineer
**Scope audited:** The running demo web app + its JSON API — the new Stage 8.5 persistence surface (`/api/designs*`: list, save, reopen, thumb, export, import, rename, delete, duplicate) plus the SPA flows that drive them (auto-save, My Designs gallery, reopen, reload-restore, sort, import). HTTP layer (raw `requests` + raw socket) and browser layer (Claude_Preview DOM/network/console).
**Environment:** Demo server `python -m kimcad.cli web --demo` (LLM-free `DemoProvider`), Python 3.14.3 stdlib `ThreadingHTTPServer`, Windows 11 (10.0.26200), repo `C:\Users\scott\dev\kimcad` @ `657bc3b` (branch `stage-8.5-usability`). API probed on `127.0.0.1:8766`; browser preview on `127.0.0.1:8765` (Chromium via Claude_Preview). Shared on-disk store `C:\Users\scott\.kimcad\designs`.
**Auditor posture:** Balanced (runtime/QA lens)

---

## TL;DR

The slice behaves as claimed across the board for a single user: the full library round-trip — create → auto-save → list (newest-first) → reopen (part + sliders fully restored) → export (valid `.kimcad` zip) → delete → import → reopen the import — works end to end with correct status codes, content types, and headers, and **a page reload restores the open design rather than blanking the workspace** (the headline Stage 8.5 promise). The console is **completely clean** (zero errors/warnings across the whole session), path-traversal and zip-slip are fully defended (every adversarial id/archive is a clean 4xx with nothing written outside the design dir), and oversized uploads / zip bombs / malformed JSON are all rejected cleanly with the server staying up. The one serious runtime issue is a **Windows-specific concurrency bug**: the "atomic" `os.replace` in `_atomic_write_json` collides with concurrent readers (the gallery's own `GET /api/designs`, which opens every `meta.json`), and on Windows `os.replace` raises `PermissionError [WinError 5]` when the target file is open. Measured: **13 of 30 saves (43%) returned HTTP 500** under the realistic auto-save-while-gallery-is-open scenario, and `rename` silently fails (`ok:false`) on the same race. The data never corrupts (the final state is always consistent), but a user's save/rename intermittently fails on the platform the developer ships and tests on. No security/privacy Blockers.

## Severity roll-up (QA)

| Severity | Count |
|---|---|
| Blocker | 0 |
| Critical | 1 |
| Major | 1 |
| Minor | 3 |
| Nit | 1 |

## What's working

- **Reload restores the open design (the core Stage 8.5 promise).** Built "a unique qa test widget" in the browser, full page `location.reload()` at `#/design/<id>`; after re-mount the part rendered, the conversation history returned, and all 4 sliders restored to their values (80/60/40/2). Not a blank workspace. Network log shows the SPA fetches `GET /api/designs/<id>` on load to rehydrate.
- **Full delete → import → reopen round-trip is clean.** Deleted the original; `GET /api/designs/<id>` and `.../export` of the deleted id both returned **404** (no stale-state served). Imported the exported `.kimcad`; it came back as a **fresh id** coexisting with the pre-existing designs, and reopen restored `object_type=box`, `target_bbox=[80,60,40]`, parameters, and a `200 model/stl` mesh.
- **Path traversal + zip-slip fully defended.** `..%2f..%2fetc%2fpasswd`, dotted ids, slash ids on reopen/thumb/export → clean 404; on rename/delete/duplicate → `{"ok": false}` (the `_safe_id` guard rejects before any filesystem touch). A crafted import zip carrying `../evil.txt` + `../../evil2.txt` imported successfully **with the evil members ignored** — confirmed no `evil.txt`/`evil2.txt` landed in `~`, `~/.kimcad`, or `~/.kimcad/designs` (import reads only the three known files by exact name).
- **Robust input handling / never-raises.** Empty import body → 400; non-zip garbage → 400; zip missing `mesh.stl` or `meta.json` → 400; `meta.json` that's a list / invalid JSON → 400; a 200 MiB-inflated **zip bomb** (204 KB compressed) → 400 (the bounded `_read_zip_member` read caught it); bad JSON / list / null body on save & rename → 400 `invalid request body`; non-existent `design_id` on save → 404; reopen of a non-existent valid id → 404. **The server kept serving after every single probe.**
- **Oversized uploads bounded.** A small-chunk upload declaring 33 MiB returns a clean wire-level `413 Content Too Large` with body `{"error":"File too large."}`; the 2 MiB JSON body on `/api/design` returns `413` likewise. Verified by raw socket.
- **Export/thumb headers are correct.** Export: `200`, `Content-Type: application/zip`, `Content-Disposition: attachment; filename="kimcad-design-<id>.kimcad"`, `PK` magic bytes. Thumb: `200`, `image/png`, real PNG magic (`89 50 4E 47`). Verified at both the curl and browser-fetch layers.
- **Routing + gallery are genuinely wired.** Topbar "My Designs" → `#/designs` gallery (Import / New design / Sort-by control with Newest/Oldest/Name options, per-card Rename/Duplicate/Export/Delete). Clicking a card opens `#/design/<id>`; **browser Back returns to the gallery**. The native `<select>` sort actually re-orders (default Newest-first → switched to Name A–Z and the list re-sorted alphabetically).
- **Auto-save de-dups in the happy path.** A fresh build produced exactly **one** library entry (not a duplicate); the SPA adopts the server-minted id into the route (`#/design/<minted-id>`) and a real viewport-canvas PNG thumbnail is captured and persisted.
- **Mobile (375×812) layout is clean.** No horizontal overflow (`scrollWidth == 375`), 16 cards rendered, heading + sort present.
- **Console is silent.** Zero `console.error`/`warn` across create, save, reopen, reload, slider re-render, gallery, sort, and back-navigation.

## What couldn't be assessed

- **Real-LLM path.** Tested in `--demo` (LLM-free `DemoProvider`) per the run instructions, so the design payloads are the fixed demo plan. Persistence is provider-agnostic (it stores whatever payload the pipeline returns), so this doesn't affect the persistence findings — but I did not exercise save/reopen of a *template-backed* real-LLM part with live-restored template sliders end to end (the demo part is a box; its sliders re-render via `POST /api/render`, which I did confirm works).
- **JPEG screenshots.** Per the run note, I relied on **DOM + computed-state + network + console inspection** via `preview_eval`/`preview_network`/`preview_console_logs` rather than rendered JPEGs (the JPEG tool was not exercised, to avoid the known timeout). Layout/overflow was measured numerically (`getBoundingClientRect`, `scrollWidth`) rather than eyeballed — stated plainly here.
- **Multi-tab conflicting edits.** I exercised concurrency at the HTTP layer (threaded clients) but not two literal browser tabs editing the same saved id simultaneously. The HTTP-layer result (QA-001) is the more severe and more general form of that scenario.
- **Disk-full / permission-denied store.** Did not simulate a read-only `~/.kimcad`. The code degrades best-effort (store builds lazily, returns `None` → 503), but I didn't force the failure.

---

## Product shape

KimCad's Stage 8.5 Slice 1 is a local, single-user web app (a React/Vite SPA served by a dependency-free stdlib `ThreadingHTTPServer`) that adds a persistent "My Designs" library on top of the previously in-memory design loop. Because it both **exposes a JSON API** and **is a SPA**, I tested both layers: API contract/status/headers/adversarial-input at the wire, and the real user flows (auto-save, gallery, reopen, reload-restore, sort, import, back-nav) in a browser. The product is explicitly local-single-user-on-localhost, so per the altitude note I did **not** flag absence of auth/CSRF/rate-limiting or real-hardware printing. I focused on the failure classes that bite a real local user: 500s/traceback leaks on bad input, path escapes, lost-work-on-refresh, duplicate saves, stale state, and console/UI health.

## Flows exercised

| Flow | Result | Findings |
|---|---|---|
| Create design (`POST /api/design`) → render | Pass | — |
| Auto-save on build → appears in library | Pass | — |
| Gallery list (`GET /api/designs`), newest-first | Pass | — |
| Reopen saved design → payload + sliders restored | Pass | — |
| Export `.kimcad` (zip + headers + PK magic) | Pass | — |
| Import `.kimcad` → fresh coexisting id | Pass | — |
| Delete → reopen/export of deleted id is 404 | Pass | — |
| **Reload page → open design restored (not blank)** | **Pass** | — |
| Live slider edit → `POST /api/render` → re-render + auto-save | Pass | — |
| Sort control (Newest / Oldest / Name A–Z) re-orders | Pass | — |
| Reopen from card → Back returns to gallery | Pass | — |
| Rename / Duplicate / Delete per-card actions | Pass (single-user) | QA-001 (rename under concurrent reads) |
| Concurrent save while gallery polls (auto-save realistic) | **Fail (43% HTTP 500)** | QA-001 |
| Mobile 375px gallery layout | Pass | QA-005 (tap-target height) |

## Adversarial scenarios exercised

| Scenario | Outcome | Findings |
|---|---|---|
| Path traversal id on reopen/thumb/export (`..%2f..%2fetc%2fpasswd`, `%2e%2e%2f`, `..`, `...`, `a/b`, `a%2fb`) | Clean 404, no file leak, server up | — (credit) |
| Traversal id on rename/delete/duplicate | `{"ok": false}` (200), no fs touch | QA-003 (200-on-bad-id is off-convention) |
| Import: empty body / garbage / missing mesh / missing meta / list-meta / bad-JSON-meta | Clean 400 each, server up | — (credit) |
| Import: zip with `../evil.txt` + `../../evil2.txt` members | Imported, evil members ignored, **nothing escaped** | — (credit) |
| Import: 200 MiB-inflated zip bomb (204 KB compressed) | 400 (bounded read), server up | — (credit) |
| Oversized import (33 MiB) / oversized JSON body (2 MiB) | Wire-level 413 + JSON body, server up | QA-004 (client-side RST on full-body upload) |
| Save: bad JSON / list / null / missing id / non-numeric id / ghost id | 400 or 404, server up | — (credit) |
| Reopen non-existent valid id | 404, server up | — (credit) |
| Missing Content-Length on POST | Treated as 0-len body → clean 400, server up | — (credit) |
| Unknown methods (DELETE/PUT/PATCH on `/api/designs`) | stdlib 501/405, empty body, server up | QA-006 (Nit) |
| **5 concurrent saves w/o saved_id** | 5 distinct library entries (expected; see QA-002) | QA-002 |
| **8–30 concurrent update-in-place saves (same saved_id)** | mix of 200 + **500**; final state consistent | **QA-001** |
| **30 saves while 4 list + 4 export readers run** | **13/30 = 43% HTTP 500** | **QA-001** |
| 30 renames while 6 list readers run | 28 ok + **2 silent `ok:false`** | QA-001 |

---

## Findings

> **Finding ID prefix:** `QA-`
> **Categories:** Flow / API / Security / Performance / Browser / Mobile / Console / Protocol / Install / Auth / Concurrency

### [QA-001] — Critical — Concurrency / Data integrity — `os.replace` in `_atomic_write_json` raises `PermissionError [WinError 5]` against concurrent readers on Windows, so a save returns HTTP 500 (≈43% under realistic auto-save-while-gallery-open load); rename/duplicate silently fail

**Evidence**

Environment: Windows 11 (10.0.26200), Python 3.14.3, demo server on `127.0.0.1:8766`, threaded `requests` clients.

The intended invariant (stated in `design_store.py` and confirmed by the Engineering deep-dive ENG-001/ENG-004) is that `_atomic_write_json` (`design_store.py:293-298`) writes a temp file then `os.replace(tmp, path)`, so "a concurrent reader never sees a half-write." That holds on POSIX. On **Windows**, `os.replace` fails with `PermissionError [WinError 5] Access is denied` when the destination file is currently **open** by another handle — and `DesignStore.get()` (`design_store.py:95-121`, called unlocked from the handler and from `_prune()` → `list()`) opens `meta.json` for read. The `save()` body wraps everything in `except Exception: return False` (`design_store.py:184-185`), and the handler maps `False` → `self._json(500, {"error": "Couldn't save the design."})` (`webapp.py:918-919`).

Reproductions (all on this machine, this session):

1. **In-process, no readers:** 40 concurrent `store.save(...)` on one id → 40/40 `True`. (Lock serializes store writes; no failure when nothing reads concurrently.)
2. **In-process, 8 concurrent `store.get()` readers + 50 savers:** **0/50 saves succeeded** (`{False: 50}`). Every save's `os.replace` collided with an open `meta.json` handle.
3. **Direct `os.replace` vs `open` contention** on the same path (30 writers + 30 openers): **24× `PermissionError [WinError 5] Access is denied`** captured.
4. **Over HTTP, server-level, the realistic scenario** — 30 update-in-place saves (same `saved_id`) fired while **4 threads poll `GET /api/designs` + 4 threads `GET .../export`** (i.e. the gallery is open / refreshing while auto-save runs): **`{200: 17, 500: 13}` — 43% returned HTTP 500** `{"error":"Couldn't save the design."}`. The final library state was correct (1 entry, reopens 200, no corruption).
5. **`rename` over HTTP** (30 renames while 6 list readers run): **`{(200,True): 28, (200,False): 2}`** — 2 renames **silently failed** (`ok:false`, no 500), because `rename`/`duplicate` also call `_atomic_write_json`.

Why this is the realistic path, not a synthetic stress: the SPA's network log shows that **building, reopening, or slider-editing a design each fire `POST /api/designs/save`** (observed: `.../save` after `POST /api/design`, after reopen, and after `POST /api/render`), and the gallery / a thumbnail render concurrently does `GET /api/designs` (which calls `get()` on **every** design dir) plus `GET .../thumb`. Auto-save firing while the user has My Designs open (or while a thumb loads) is exactly conditions 4/5.

**Why this matters**

A user's "save" (often automatic, so they don't even know it fired) intermittently fails with a 500 on the platform the developer builds and ships on (Windows). The current SPA shows this as a save error or a no-op; under the "auto-save while gallery open" pattern it's not an edge case — it's ~2-in-5. The data never corrupts (the atomic design holds when the replace *succeeds*; a failed replace just leaves the prior `meta.json`), so this is "lost *edit*, not corrupted *library*" — which is why it's Critical, not Blocker. But it directly undermines the slice's headline value ("your work is saved").

The Engineering deep-dive (ENG-001) explicitly noted it did **not** build a multi-threaded harness ("a stress test would confirm the window's width") and assumed `os.replace` protects readers. This finding is the runtime confirmation — and it surfaces a platform behavior the static read missed: on Windows the replace doesn't *block* the reader, it *fails the writer*.

**Blast radius**
- Adjacent code: every `_atomic_write_json` caller — `save` (`design_store.py:181`), `rename` (`:195`), `duplicate` (`:226`), `import_bytes` (`:274`). All share this root. The unlocked `get()` reads are in the handler (`webapp.py` `_handle_design_reopen`, `_handle_designs_list` → `store.list()` → `get()` per dir) and inside `save`/`import`'s own `_prune()` → `list()`.
- Shared state: `~/.kimcad/designs/<id>/meta.json` + the `_WRITE_LOCK` (which serializes *writers* but not the *unlocked readers* that hold the open handle the replace collides with).
- User-facing: auto-save and rename are the affected flows; failure shows as a save error / unchanged name. No visible change when it succeeds.
- Migration: none — behavioral fix only.
- Tests to update: add a Windows-aware concurrent save-vs-list test (the team has a threading harness in `test_concurrent_rerenders_are_serialized` to copy). The current suite is green because it doesn't run save and read on the same file concurrently on Windows.
- Related findings: ENG-001 (cross-lock mesh copy — same "concurrency under the auto-save" theme), ENG-003/ENG-004 (non-atomic export / write-ordering — same atomicity root), QA-002 (the no-`saved_id` race that produces duplicates rides the same auto-save timing).

**Fix path**
Make the meta write resilient to a concurrent open on Windows. Options, cheapest first: (a) **retry `os.replace` on `PermissionError`** with a tiny bounded backoff (3–5 tries, ~5–20 ms) — the reader's handle is open only for the brief `read_text`, so a couple of retries closes the window; (b) hold `get()` reads under a shared/`_WRITE_LOCK` (or a read lock) so a write never overlaps an open handle — heavier, serializes the gallery; (c) read `meta.json` via a copy / `O_TEMPORARY`-style short-lived handle. Recommend (a): smallest change, matches the "best-effort, never raise" intent, and turns the 500/`ok:false` into a near-always-success. Either way, **stop mapping a best-effort `save()==False` to a hard 500** — a transient persistence miss should not be a 5xx; consider a 503 "couldn't save, retry" or a 200 with `saved:false` the SPA can re-try, so the UX matches the "best-effort" contract.

---

### [QA-002] — Major — Concurrency / Data integrity — auto-save without a `saved_id` mints a new library entry per call, so a fast build→edit (before the first save's id round-trips) creates duplicate gallery entries

**Evidence**

`POST /api/designs/save` mints a fresh id whenever the request omits `saved_id` (or passes one the store doesn't have): `store_id = requested if existing is not None else uuid.uuid4().hex` (`webapp.py:890-892`). The SPA's auto-save body (captured live) is `{"design_id": <rid>, "name": "", "thumbnail": "data:image/png;..."}` — **no `saved_id`** on the first save. The SPA then adopts the minted id from the response into the route and threads it on subsequent saves (confirmed: a single fresh build produced exactly **1** entry, and the URL became `#/design/<minted-id>`).

But the de-dup depends entirely on the **first save's response arriving before the next save fires**. I directly reproduced the duplicate: **5 concurrent saves of the same live rid without `saved_id` → 5 distinct ids → 5 library entries named "ConcSave"** (`distinct ids: 5 | library entries named ConcSave: 5`). And the library I inherited at session start already contained **two** identical "a small box" entries (same prompt, ids `38a7557d…` and `32da8553…`, ~55 s apart) — the real-world fingerprint of this race from a prior session: an edit auto-saved before the create's `saved_id` came back.

**Why this matters**

A user who builds a part and immediately tweaks a slider (or builds two parts quickly) can silently end up with duplicate gallery entries that then diverge or clutter the library. It's a data-tidiness/correctness issue, not corruption — hence Major. It's the same auto-save-timing root as QA-001.

**Blast radius**
- Adjacent code: `_handle_design_save` (`webapp.py:865-921`) `saved_id` logic; the SPA's save-debounce / id-adoption logic (`kimcad.js`, minified — the client-side guard is where the real fix lives).
- Shared state: the live `rid` ↔ `saved_id` mapping the SPA holds; the `design_snapshot`/`registry` keyed by rid.
- User-facing: My Designs gallery shows duplicates.
- Migration: none; existing duplicates are harmless rows.
- Tests to update: add a test that two saves of the same rid without `saved_id` arriving close together resolve to one entry (requires a server-side or client-side dedup key — e.g. dedup on `(rid)` within a short window, or have the server return a stable id for a given rid until it changes).
- Related findings: QA-001 (same auto-save timing), ENG-001.

**Fix path**
Give the server a stable per-`rid` save identity so a second save for the same live `rid` updates the first entry even without a client-supplied `saved_id`: e.g. keep a `rid → saved_id` map server-side (minted on first save, reused until the rid is evicted) so concurrent or rapid saves of one rid converge to one library entry. Belt-and-suspenders on the client: debounce auto-save and don't fire a second save until the first resolves with its id.

---

### [QA-003] — Minor — API — mutate verbs (rename/delete/duplicate) return HTTP 200 with `{"ok": false}` for an invalid/unsafe/absent id instead of a 4xx

**Evidence**

`POST /api/designs/..%2f..%2fetc/rename` → `200 {"ok": false}`; `.../delete` → `200 {"ok": false}`; `.../duplicate` → `200 {"ok": false, "id": null}`. Same for a well-formed-but-absent id (delete of a non-existent id returns `200 {"ok": true}` — `shutil.rmtree(..., ignore_errors=True)` reports success even when nothing was deleted). The traversal cases are correctly *rejected* (no fs touch) — the issue is only the **status code**: a client can't distinguish "did nothing because the id was bad/absent" from "succeeded" without parsing `ok`, and delete-of-absent reports `ok:true`.

**Why this matters**

An integrator (or the SPA's own error handling) that keys off HTTP status will treat a failed rename/duplicate as success. Low exposure (the SPA reads `ok`), so Minor — but it's an API-contract inconsistency: reopen/thumb/export return a proper 404 for the same bad ids, while the mutate verbs return 200.

**Blast radius**
- Adjacent code: `_handle_design_mutate` (`webapp.py:974-995`); `delete`/`rename`/`duplicate` in `design_store.py`.
- User-facing: none today (SPA reads `ok`); affects future API consumers / MCP.
- Tests to update: add status-code assertions for bad-id mutate (none currently pin this).

**Fix path**
Return `404` when `_safe_id` rejects the id or the design doesn't exist (have `delete`/`rename`/`duplicate` distinguish "not found" from "done"), and reserve `200 {"ok": true}` for an actual mutation. Keep the `ok` field for backward compat.

---

### [QA-004] — Minor — API / Protocol — an oversized upload that streams the full body gets a TCP reset (client sees a connection error), not the friendly 413 JSON

**Evidence**

The 413 is correct on the wire: `_read_json_body`/`_read_raw_body` reject an oversized `Content-Length` up front and set `self.close_connection = True` **without draining the body** (`webapp.py:634-640`, `1028-1031`). A client that has already finished (or barely started) writing reads a clean `413 Content Too Large` + `{"error":"File too large."}` (verified by raw socket). But a client that is *still streaming* the large body when the server closes gets a TCP RST mid-write: `requests` raised `ConnectionError('Connection aborted', ConnectionAbortedError(10053, ...))` when POSTing a real 33 MiB body — it never read the 413. A browser `fetch`/XHR uploading a too-large `.kimcad` will likely surface a generic "network error," not the intended "File too large."

**Why this matters**

The defensive choice (don't drain a hostile upload) is correct for robustness, but the UX of the legitimate "I tried to import a too-big file" path may be a confusing network error instead of the friendly message. Minor — the server stays safe and up; only the error *presentation* to a streaming client suffers.

**Blast radius**
- Adjacent code: the size-guard `close_connection` branch in both body readers.
- User-facing: the import-too-large error path in the SPA.
- Tests to update: the existing `test_oversize_content_length_rejected_with_413` exercises the small-chunk path; add a note (or a comment) that a full-body upload sees an RST.

**Fix path**
Document the behavior, and on the client surface a friendly "that file is too large (max 32 MB)" when an import POST fails with a network/connection error so the user gets the right message regardless of whether the 413 was readable. (No server change strictly required.)

---

### [QA-005] — Minor — Mobile — per-card action buttons are ~25 px tall, below the ~44 px touch-target guideline

**Evidence**

At 375×812 (mobile preset), the per-card Rename/Duplicate/Export/Delete buttons measure ~25 px tall (`{Rename: w55×h25, Duplicate: w63×h25, Delete: w47×h25}` via `getBoundingClientRect`). The layout doesn't overflow and the buttons are present and (in DOM terms) clickable — but 25 px is under the iOS 44 px / Material 48 dp minimum, so a thumb tap on a dense gallery card can miss or hit the wrong action (Delete sits next to Duplicate).

**Why this matters**

Mobile mis-taps on a row that includes **Delete** risk an accidental destructive action. Low severity because there's no confirm-dialog finding here to compound it and the primary flows are reachable; flagged as a runtime mobile usability issue (overlaps the UI/UX lane).

**Blast radius**
- Adjacent code: the gallery card action styling (SPA CSS).
- User-facing: mobile gallery interactions.
- Related findings: see the UI/UX deep-dive for touch-target / destructive-action-confirm coverage.

**Fix path**
Increase the action control hit area to ≥44 px on touch viewports (padding or a larger tap target), and consider a confirm on Delete.

---

### [QA-006] — Nit — API — unimplemented methods return the stdlib default `501`/`405` with an empty body, not the app's JSON error shape

**Evidence**

`DELETE`/`PUT`/`PATCH /api/designs` return a stdlib status (501/405) with an **empty body**, rather than the app's consistent `{"error": "..."}` JSON. Harmless — the server stays up and no real client sends these — but it's the one response shape that breaks the otherwise-uniform JSON-error contract.

**Fix path**
Optionally add `do_PUT`/`do_DELETE`/`do_PATCH` that return `405 {"error":"Method not allowed."}` for parity. Not worth blocking on.

---

## Performance snapshot

| Metric | Observed | Benchmark | Verdict |
|---|---|---|---|
| API: `POST /api/design` (demo, no LLM) | sub-second (returns full payload + mesh registered) | n/a (local) | pass |
| API: `POST /api/designs/save` | sub-second | n/a | pass |
| API: `GET /api/designs` (16 designs, reads each meta) | sub-second | n/a | pass |
| Static asset caching | ETag + `no-cache` revalidation; repeat loads `304 Not Modified` | revalidate-on-rebuild | pass |
| Live slider re-render | `POST /api/render` + cache-busted mesh GET, sub-second | "under a second" (claimed) | pass |
| Mobile layout (375px) | no horizontal overflow | no overflow | pass |

Performance was not the focus (local single-user), and nothing stood out as slow. The cache story (content-hash ETag + `no-cache`) is correct: I observed `200` on first load and `304` on revalidation for the fonts.

## Security / privacy snapshot

- **Path traversal (IDOR-style escape): defended.** Every `..`/encoded-separator/slash id on every endpoint is rejected before touching the filesystem; nothing resolves outside `~/.kimcad/designs`. `_safe_id` (`design_store.py:287-290`) is the single guard and it holds at the HTTP layer.
- **Zip-slip: defended.** Import reads only the three known files by exact name and never uses the archive's own paths; a `../evil.txt`/`../../evil2.txt` member was ignored and nothing escaped (verified on disk).
- **Zip bomb / memory exhaustion: defended.** `_read_zip_member` bounds the inflated read at 64 MiB; a 200 MiB-inflated bomb was rejected as a clean 400.
- **Oversized upload: bounded.** 32 MiB import cap / 1 MiB JSON cap enforced up front (413), body not drained.
- **No traceback leaks.** Across ~80 adversarial requests, not one response leaked a Python stack; the only 5xx observed was the deliberate `{"error":"Couldn't save the design."}` (QA-001) and the `{"error": "ClassName: msg"}` last-resort on `/api/design` (class+message only, no stack — by design).
- Per the altitude note (local single-user on localhost), **not flagged:** absence of auth/CSRF/rate-limiting and no real-hardware print.

## Console and log observations

Browser console was **completely clean** for the entire session — `preview_console_logs` returned "No console logs" at every checkpoint (after create, save, reopen, full reload, slider re-render, gallery render, sort, and back-navigation). No errors, no warnings, no React key warnings, no deprecation notices, no failed-network noise. Network panel showed all SPA traffic at 200/304; the only non-2xx responses in the whole run were the *intended* adversarial 400/404/413 and the QA-001 500s.

## Patterns and systemic observations

- **One root cause spans QA-001, QA-002, ENG-001, ENG-003/004:** the auto-save fires frequently and concurrently with reads, and the persistence layer's atomicity story — solid on POSIX, statically "looks safe" — has a Windows hole (`os.replace` vs open handles) and timing-dependent dedup. This is the highest-leverage fix area in the slice: a retry-on-`PermissionError` in `_atomic_write_json` plus a server-side per-rid save identity closes the two QA findings and hardens the ENG atomicity findings in the same neighborhood.
- **Defensive input handling is genuinely excellent** everywhere *except* the concurrency path. The `_safe_id` guard, the bounded zip reads, the by-exact-name import extraction, the 413 caps, and the "never raise / best-effort" store are all well-built and verified under adversarial input. The gap is specifically *concurrent writers vs readers on Windows*, not input validation.
- **The SPA is real, not cosmetic.** Routing, sort, reopen, reload-restore, slider re-render, and per-card actions are all genuinely wired to the backend (confirmed by the network log), and the console is silent. This is a working slice with one serious platform-specific reliability bug.

## Appendix: environments and artifacts

- **Servers:** `python -m kimcad.cli web --demo` on `127.0.0.1:8766` (HTTP probes) and `127.0.0.1:8765` (browser preview). Both stopped at end of session (verified DOWN).
- **OS / runtime:** Windows 11 10.0.26200; Python 3.14.3; stdlib `ThreadingHTTPServer`; `requests 2.34.2` (HTTP harness) + raw `socket` (wire-level 413 / no-Content-Length probes).
- **Browser:** Chromium via Claude_Preview (`serverId` reused/recreated against `kimcad-demo`). Inspection via `preview_eval` (DOM/computed-state/fetch instrumentation), `preview_network`, `preview_console_logs`, `preview_resize` (mobile 375 + desktop). **No JPEG screenshots** — DOM/network/console only, by design (timeout avoidance), stated in "What couldn't be assessed."
- **Data hygiene:** all 14 QA-created designs deleted after testing; the 2 pre-existing designs (`box` `59a3fec5…`, `box (copy)` `fe589c3c…`) preserved; verified no orphan `*.tmp` files in `~/.kimcad/designs`; `.claude/launch.json` restored to its committed state (not in git status). Both demo servers stopped.
- **Cross-references:** ENG-001/ENG-003/ENG-004 (Engineering deep-dive) share the atomicity/concurrency root with QA-001/QA-002; UI/UX deep-dive owns the mobile touch-target / destructive-confirm lane referenced in QA-005.
