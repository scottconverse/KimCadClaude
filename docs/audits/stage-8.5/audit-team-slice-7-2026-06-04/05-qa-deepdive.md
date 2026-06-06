# 05 — QA Engineer Deep-Dive — Stage 8.5 Slice 7 ("describe with a photo" on-ramp)

**Role:** Senior QA Engineer (runtime behavior across layers — HTTP API + running app)
**Date:** 2026-06-04
**Posture:** Balanced
**Repo:** `C:\Users\scott\dev\kimcad` @ `39b9b09` (Stage 8.5 Slice 7 MS-2), branch `stage-8.5-usability`, tree clean
**Target under test:** model-free demo server **RUNNING** at `http://127.0.0.1:8767` (DemoProvider — canned seed; `object_type "box"` → snap_box)
**Method:** live HTTP exercise of `/api/photo-seed` and the surrounding app via Python `urllib` and a raw socket (for the size-guard timing proof), plus on-disk persistence probes with a marker payload.

---

## Verdict

**0 Blocker / 0 Critical / 0 Major / 0 Minor / 0 Nit from the QA (runtime) lane.**

The Slice 7 runtime surface is clean and matches its claimed behavior exactly. Every guard fires at the right boundary, every error is friendly JSON, there are **zero 500s** on any input I threw at it, the size cap is enforced **before** the body is read (the load-bearing DoS guard), the server **survives** an oversized abort, and the photo **never touches disk** and **never echoes back** in the response. The happy path returns a real, non-empty canned seed and feeds the same text→DesignPlan path that produces a completed, gate-passing demo design.

This lane recommends Slice 7 PASS on runtime grounds. (UI/UX polish nits — object-URL leak, AT announcement, workspace-replace cue — are owned by the UI/UX and Engineering lanes per the committed MS-2 audit-lite; they are not runtime defects and I do not re-flag them here.)

---

## Environment

- **Server:** `BaseHTTP/0.6 Python/3.14.3`, HTTP/1.0 responses, listening on `127.0.0.1:8767` (DemoProvider, model-free).
- **Clients:** Python 3 `urllib.request` and a raw `socket` (to send a lying `Content-Length` and to observe connection close), `curl` for status/size.
- **OS:** Windows 11.
- **Source under test:** `src/kimcad/webapp.py` — `_handle_photo_seed` (line 1147) and `_read_raw_body` (line 1424); cap `MAX_PHOTO_BYTES = 12 * 1_048_576` (line 50).

---

## What I ran vs. what I couldn't

**Ran (live, against 8767):**
- Happy path POST (1×1 PNG) → 200 + canned seed.
- Empty body (`Content-Length: 0`) → 400.
- Oversized via **lying** `Content-Length` (13 MiB declared, 16 bytes sent) → 413 in 0.001 s; proves cap-before-read.
- Connection-close-after-413 observation (raw socket).
- Oversized via **real** 13 MiB body → server aborts the connection after sending 413 (does not sink 13 MiB).
- Boundary: exactly 12 MiB (allowed past guard) vs 12 MiB + 1 (413).
- Malformed `Content-Length: abc` and **missing** `Content-Length` → 400.
- Server-survives-abort check (health after the 13 MiB abort).
- App sanity: `GET /` (SPA), `GET /api/health`, `POST /api/design {"prompt":"a box","experimental":false}` → completed design, then `GET /api/mesh/1`.
- Trust invariants: marker-payload photo POST + on-disk grep of `~/.kimcad`, temp dirs, repo, and every `~/.kimcad/designs/<id>/` dir; `git status` before/after.

**Couldn't / deliberately skipped:**
- **Rendered JPEG screenshot** — skipped per audit instruction (the JPEG tool is unreliable in this environment). DOM-level live evidence is covered by the committed MS-2 audit-lite (`docs/audits/stage-8.5/audit-lite-slice-7-ms2-photo-ui-2026-06-04.md`): affordance → reading → editable confirm → "Use this" starts a real demo design; 44px targets and 0 horizontal overflow at 375px; never auto-submits. I corroborate that with the live `/api/design` completion below. **The absent JPEG is not a finding and the slice is not failed for it.**
- **Forcing a real vision failure (→422)** on the DemoProvider — not easily reachable (the canned provider always returns a seed). The vision-failure→422 path is covered by the test suite and by source inspection (`_handle_photo_seed` lines 1159–1167: any `describe_photo` exception OR empty seed → 422 `{"error": "Couldn't read that photo…"}`, never a 500). I confirmed the *shape* of the friendly-JSON error path on every client-error branch I could reach (400/413).
- **Real vision-model accuracy** and **real-hardware print** — explicitly out of scope.

---

## Test log (evidence)

### 1. Happy path — POST a small PNG → 200 + real seed ✅

**Command:**
```python
png = bytes.fromhex('89504e47...')  # 1x1 transparent PNG (67 bytes)
req = urllib.request.Request('http://127.0.0.1:8767/api/photo-seed', data=png, method='POST')
req.add_header('Content-Type','image/png')
urllib.request.urlopen(req)
```
**Observed:**
```
STATUS 200
CTYPE  application/json
CLEN   175
BODY   {"seed": "A small rectangular box, roughly 80 mm wide, 60 mm deep, and 40 mm
        tall — these sizes are rough guesses from the photo (a photo has no scale),
        so adjust them."}
```
Real, non-empty text (175 bytes), correctly framed as a **rough** estimate with the scale caveat baked into the seed. Matches `{"seed": "...rough..."}`. ✅

### 2. Oversized — cap checked BEFORE read ✅ (the load-bearing guard)

**2a — lying Content-Length (declared 13 MiB, 16 bytes actually sent), raw socket:**
```
ELAPSED   0.001s   (server did NOT read 13 MiB before answering)
STATUS    HTTP/1.0 413 Content Too Large
BODY      {"error": "File too large."}
```
The 0.001 s round-trip with only 16 bytes on the wire is direct proof that `_read_raw_body` rejects on the **declared** `Content-Length` header before `self.rfile.read(declared)`. A hostile client cannot make the server allocate/read 13 MiB. ✅

**2b — connection closes after 413 (not left streaming):**
```
CONNECTION CLOSED by server after 413 (recv returned empty)  -> not left streaming
status: HTTP/1.0 413 Content Too Large
```
`_read_raw_body` sets `self.close_connection = True` before the 413, so the server tears the socket down rather than waiting (keep-alive) for a body it already refused. Confirmed at the wire. ✅

**2c — real 13 MiB body:**
```
client raised ConnectionAbortedError [WinError 10053]
```
Expected and correct: the server emitted the 413 and closed the connection mid-upload, so the client's `sendall` of 13 MiB was aborted. The server **did not sink** the full payload. ✅

### 3. Empty upload → 400 "Empty upload." ✅
```
STATUS 400  CTYPE application/json  BODY {"error": "Empty upload."}
```

### 4. Boundary checks ✅
```
declared == 12 MiB  exactly      -> guard PASSES (no 413; server proceeds to read)   ✅ correct (cap is `>`, not `>=`)
declared == 12 MiB + 1 byte      -> HTTP/1.0 413  {"error": "File too large."}        ✅
```

### 5. Malformed / missing Content-Length ✅
```
Content-Length: abc   -> declared=-1 -> HTTP/1.0 400  {"error": "Empty upload."}
(no Content-Length)   -> declared= 0 -> HTTP/1.0 400  {"error": "Empty upload."}
```
A garbage length is treated as a clean client error, not an `int()` crash on the request thread. ✅

### 6. NEVER-500 ✅
Across **every** input above — happy, empty, oversized (lying + real), boundary ±1, malformed header, missing header — the status codes observed were **200 / 400 / 413 only**. No 5xx on any path. Every error body is friendly JSON `{"error": "..."}` with `Content-Type: application/json`. ✅

### 7. Server survives the oversized abort ✅
Immediately after the 13 MiB `ConnectionAbortedError`:
```
GET /api/health -> HTTP 200   {"version":"0.1.0","openscad":true,"orcaslicer":true}
```
The connection-reset on one request did not wedge or crash the server. ✅

### 8. App sanity — the rest of the app still works ✅
```
GET  /                 -> HTTP 200  text/html  (real SPA shell: <!doctype html>, #root,
                                                /assets/kimcad.js module + /assets/index.css)
GET  /api/health       -> HTTP 200  {"version":"0.1.0","openscad":true,"orcaslicer":true}
POST /api/design       -> HTTP 200  completed demo design:
       {"prompt":"a box", "mesh_url":"/api/mesh/1", "has_mesh":true,
        "report":{"gate_status":"pass", dims/volume_mm3/watertight/readiness/...}, "status":..., "plan":..., "template":...}
GET  /api/mesh/1       -> HTTP 200  model/stl  1284 bytes  (real mesh, not a dangling URL)
```
This is the **same** text→DesignPlan path the photo seed feeds: a seed becomes the prompt, the prompt produces a gate-passing, rendered, downloadable part. The on-ramp lands the user somewhere real. ✅

---

## Trust invariants (probed at runtime)

### TI-1 — The photo never persists ✅
I POSTed a photo whose body carried a distinctive marker (`KQA_MARKER_LEAK_TEST_`) and then searched disk:
```
~/.kimcad/                     -> marker NOT found
%TEMP% / %LOCALAPPDATA%\Temp   -> marker NOT found
repo tree                      -> marker NOT found
every ~/.kimcad/designs/<id>/  -> marker NOT found
git status (before & after)    -> unchanged (only the new audit dir)
```
The photo handler (`_handle_photo_seed`) calls only `pipeline.provider.describe_photo(image, ...)` and returns text; it never touches `get_designs_store()` or `web_root`. The saved designs present in `~/.kimcad/designs/` are prior `/api/design` "save" outputs (`mesh.stl` + `meta.json` + `thumb.png`), **not** photos — confirmed by inspecting the two newest dirs. A photo POST writes **nothing** to disk. ✅

### TI-2 — The response never echoes the raw image ✅
Both the 1×1-PNG happy path and the marker-payload POST returned **only** `{"seed": "...text..."}`. The marker bytes appear nowhere in any response body. The handler returns a text seed exclusively. ✅

### TI-3 — Never a 500 ✅
See §6. No 5xx on any input. The handler wraps the vision call in `try/except` → 422 (source-verified), and the size guard yields 400/413, so the only ways out are 200 / 400 / 413 / 422. ✅

---

## What's working (credit)

- **The size guard is correct and DoS-safe.** Rejection happens on the declared `Content-Length` in ~1 ms before any body read, the connection is closed (not left half-streaming), and the boundary math is exact (`> cap`, so 12 MiB passes, 12 MiB+1 fails). This is the single most important wire-level property of the slice and it is right.
- **Every error is a friendly, consistent JSON shape** (`{"error": "..."}`, `application/json`), with copy a real user can act on ("Empty upload.", "File too large.", and — source-verified — the gentle "Couldn't read that photo — try a clearer shot, or describe the part in words." on a vision miss).
- **Zero 500s** across happy, empty, oversized (lying + real), ±1 boundary, malformed header, and missing header.
- **The server is resilient** — an oversized connection abort doesn't wedge it; health is 200 immediately after.
- **The happy path delivers a real, honestly-framed seed** that explicitly tells the user the sizes are rough guesses (scale disclaimer baked into the seed text itself).
- **Trust invariants hold at runtime:** photo never written to disk, never echoed, never a server error.
- **The on-ramp lands somewhere real:** the seed feeds the same `/api/design` path that produced a completed, `gate_status:"pass"`, rendered (1284-byte STL), downloadable demo part.
- **DOM/UX live evidence corroborated** by the committed MS-2 audit-lite (affordance → reading → editable confirm → "Use this" starts a real demo design; 44px targets, 0 overflow at 375px; never auto-submits).

---

## Findings

None in the QA (runtime) lane. No Blocker / Critical / Major / Minor / Nit.

The three Minor items in the committed MS-2 audit-lite (object-URL leak on unmount; confirm-card not announced to AT / focus not moved; workspace "Use this" silently replaces the current session) are **UI/UX-client** concerns, not runtime-API defects, and are owned by the UI/UX and Engineering lanes. I confirmed they have **no** runtime-API impact: the server side is clean. I do not duplicate them here.

---

## Blast radius (lane-level)

Not applicable — no findings. For situational awareness on the *fix-free* surface I exercised: `_read_raw_body` (the size guard) is shared by `/api/photo-seed` and the design-import path (`MAX_IMPORT_BYTES`, webapp.py line 1415), so the guard's correctness benefits both; any future change to that helper should re-run both the photo and the import oversized/empty cases. The photo handler shares the `provider.describe_photo` contract with the real (non-demo) vision provider — the 422-on-failure behavior I verified by source should be re-confirmed live once a real vision model is in the loop.
