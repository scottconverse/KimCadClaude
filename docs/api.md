# KimCad HTTP API reference

The local web UI is a thin SPA over this JSON API, served by `kimcad web` on
`http://127.0.0.1:8765` (loopback-only by default; see the security note at the end). Every
endpoint below is the real contract the shipped SPA uses — there is no hidden surface.

Conventions:

- All bodies are JSON (`Content-Type: application/json`) unless noted (the two image
  endpoints take raw bytes; the artifact endpoints return binary downloads).
- Errors are typed statuses with a human-readable `{"error": "..."}` body — a recoverable
  condition (model down, tool missing, stale design) is **never a 500**.
- `<rid>` is the integer design id the server assigns per design (returned inside
  `mesh_url`). State is per-server-run: ids reset on restart (saved designs persist —
  see *My Designs*).

---

## Design

### POST `/api/design`

Turn a plain-English prompt into a designed, validated part.

Request:

```json
{
  "prompt": "a wall hook, 60 mm tall, holds a coat",
  "history": [{"role": "user", "content": "..."}],
  "experimental": false,
  "job_id": "optional-progress-token"
}
```

`history` (optional) carries the refine conversation. `experimental: true` permits the
LLM-OpenSCAD generator for this request when no template fits (otherwise the server OFFERS
it instead of running it).

Response (`200`, abridged to the load-bearing fields):

```json
{
  "status": "completed",
  "has_mesh": true,
  "mesh_url": "/api/mesh/3",
  "step_url": "/api/step/3",
  "template": "wall_hook",
  "params": [{"name": "plate_w", "label": "Plate width", "value": 25.0,
              "min": 12.0, "max": 120.0, "step": 1.0, "unit": "mm",
              "integer": false, "axis": "X"}],
  "plan": {"object_type": "wall_hook", "summary": "...", "target_bbox_mm": [25, 39, 60]},
  "report": {"gate_status": "pass", "headline": "...", "backend": "openscad",
             "dims": [], "findings": [], "readiness": {}}
}
```

`status` values: `completed`, `gate_failed`, `render_failed`, `plan_failed`,
`clarification_needed` (+ `clarification` text), `model_unavailable` (the local AI isn't
running — recoverable), `needs_experimental` (no template fits; the experimental generator
is offered, not run).

STEP export fields: `step_url` is present for a template part when the optional CadQuery
engine is installed (the file builds lazily on first download). `step_offer: "settings"`
appears instead when the part *could* export STEP but no engine is installed.

### GET `/api/design/progress/<job_id>`

Coarse phase of an in-flight design run (`planning` → `generating` → `rendering` →
`validating`); `{"phase": null}` once it resolves. Poll-friendly.

### POST `/api/render/<rid>`

Live-slider re-render of a template part at new parameter values — deterministic, no model
call.

Request: `{"values": {"plate_w": 30, "plate_h": 80, "arm_proj": 40}}`

Response: the same shape as `/api/design`, plus `adjusted_params` listing any value the
engine clamped (`{"name", "requested", "applied"}`), and a cache-busted
`mesh_url (...?v=N)`. Re-rendering invalidates the design's cached slice, G-code, and STEP
(the old shape can never be downloaded or sent).

---

## Artifacts

### GET `/api/mesh/<rid>` · GET `/api/gcode/<id>` · GET `/api/step/<rid>`

Binary downloads: the rendered mesh (`.stl`), the sliced print file (`.gcode.3mf`), and the
editable CAD (`.step`). The STEP for a template part builds **lazily on the first request**
(a few seconds) from the family's trusted CadQuery twin, then caches; `404` when the id is
unknown, the part has no STEP source, or no CadQuery engine is present.

---

## Slice & print

### POST `/api/slice/<rid>`

Slice a gate-passing part for a printer + material. The POST is the explicit confirmation.

Request: `{"printer": "bambu_p2s", "material": "pla"}`

> **In development (dormant today).** The `filament_slot_0`..`filament_slot_{N-1}` fields below
> are **reserved for the in-development multi-material / multi-toolhead path**. No shipped printer
> currently reports `toolhead_count > 1` (every printer is single-head — see `/api/options`), so
> these fields are **ignored today** and KimCad slices every part single-material from `material`.
> The contract is documented here so it's stable when multi-material ships.

For a (future) **multi-toolhead** printer (`toolhead_count > 1` — see `/api/options`), the client
would supply one material per extruder as `filament_slot_0`..`filament_slot_{N-1}` instead of a
single `material`:

```json
{"printer": "<multi_toolhead_printer>", "filament_slot_0": "pla", "filament_slot_1": "petg"}
```

Any omitted slot falls back to the `material` field. A multi-toolhead printer would always slice
per-slot; single-toolhead printers (i.e. every shipped printer today) ignore the
`filament_slot_*` fields and use `material`.

Response: `{"sliced": true, "gcode_url": "/api/gcode/3", "estimate": "...", "machine": "...",
"process": "...", "filament": "..."}` — or `{"sliced": false, "reason":
"no_profile" | "failed" | "stale", "note": "..."}`. A gate-**failed** part is refused
server-side regardless of what the client claims. Slices are cached per
(design, printer, material) and invalidated by any re-render.

### POST `/api/send/<rid>`

Send an already-sliced part to a configured printer connection. The POST is the explicit
per-send confirmation; a gate-failed or never-sliced part is refused. Responds with the
connector's typed result (including `simulated: true` for the built-in mock — a simulated
send is never narrated as a real print).

### POST `/api/print-outcome/<rid>`

Record the optional real-world result after a **real** hardware send. The server rejects
non-skip outcomes until that design id has successfully gone through `/api/send/<rid>` with
a non-simulated connector in the current server process. The web UI offers
`clean`, `issues`, `failed`, or `skip`; `skip` records nothing. Non-skip answers append a
coarse local-only Smart Mesh history row (`print_outcome`) so KimCad can learn from actual
prints without storing prompt text or geometry.

Request: `{"outcome": "clean" | "issues" | "failed" | "skip"}`

Response: `{"recorded": true, "outcome": "issues"}` (or `recorded:false` for skip).
If the part was not just sent to real hardware, the endpoint returns `409` with
`{"error": "Record an outcome after a real printer send."}`.

### GET `/api/connectors` · GET `/api/connector-status/<name>` · GET/POST `/api/connections`

`connectors` lists configured connections (`name`, `simulated`, `configured`).
`connector-status` is the live readiness of one printer (`ready` / `busy` / `offline` /
`needs_setup` — statuses, never 5xx). When the connector reports them, the status payload MAY
also carry `nozzle_temp_c` (float, °C) and `toolhead_temps` (an array of floats, T0..T(N-1))
— both are present only when the connector actually reports a temperature. A
single-toolhead connector that reports a hotend temperature surfaces it as `nozzle_temp_c`.
Because every shipped printer is single-head today (`toolhead_count` is always 1),
`nozzle_temp_c` is the field you'll see in practice. `toolhead_temps` is **reserved for the
in-development multi-material path**: when it appears it lists only the extruders currently
reporting a numeric temperature, so it can be **shorter than the printer's `toolhead_count`**
(see `/api/options`) if a head is disconnected.

`connections` GET lists each connection's effective
non-secret fields (+ which env var holds its secret and whether it's set); POST saves the
overlay for one named connection (`{"name": "...", "base_url": "...", "serial": "...",
"use_ams": true}`) — secrets never pass through this surface in either direction.

**Connector `type` vocabulary** (the `type` field on a configured connection):
`mock` (`loopback`), `octoprint`, `moonraker`, `prusalink`, `duet`, `marlin`, and `bambu`.
A `snapmaker` type also exists in code (Klipper/Moonraker-based; it extends `moonraker` and
inherits the full send/job/pause/resume/cancel path) but it is **reserved for the
in-development multi-material U1** and is not a shipped, user-facing connector today.

---

## Image on-ramps

### POST `/api/photo-seed` · POST `/api/sketch-seed`

Body: the raw image bytes (not JSON). The LOCAL vision model reads the photo (or
dimensioned sketch) into an editable text seed for the normal design flow — the image
never leaves the machine and is not persisted. Response: `{"seed": "..."}`; an unreadable
image or vision failure is a clean `422` with a typed hint (e.g. the vision model isn't
pulled yet), never a 500.

---

## My Designs (saved designs)

### GET `/api/designs` · POST `/api/designs/save` · GET `/api/designs/<id>` · POST `/api/designs/<id>/{rename,delete,duplicate}` · POST `/api/designs/import`

The persistent store (`~/.kimcad/designs/`). `save` takes `{"design_id": <rid>, "name":
"...", "thumb": "<dataURL>", "saved_id": "optional — overwrite an existing save"}` and
returns the stable `saved_id`. `GET /api/designs/<id>` returns the saved snapshot (the SPA
reopens it through the normal design flow, re-validating against the current printer);
`/thumb` serves the thumbnail. `import` accepts a previously exported design file. Mutating a
saved design is a **POST** sub-route — `POST /api/designs/<id>/rename`, `/delete`, `/duplicate`
(there is no `DELETE` verb; the SPA's `deleteDesign` calls `POST .../delete`).

---

## Settings & status

### GET/POST `/api/settings`

GET returns the Settings payload: printer/material choices + effective defaults, cloud
opt-in state (`cloud_enabled`, `cloud_model`, `has_cloud_key`, `cloud_key_masked` — the
key is returned **only masked**, never in full), `experimental_enabled`, and
`key_storage` (`"keyring"` = the OS credential store; `"file"` = the disclosed fallback).
POST merges any of those fields (validated; unknown values are a `400`, a typo'd field is
an error, `{"reset": true}` clears everything) and returns the new state with a `saved`
flag that is honest about whether the write stuck. The OpenRouter key is stored in the OS
credential store at rest.

### GET `/api/options`

The printer + material catalog the UI offers (each printer with its build volume,
`sliceable` flag, and `toolhead_count`) plus the effective defaults. `toolhead_count` is an
integer — **1 for a single-toolhead printer; N for a multi-toolhead printer**. The field is
**reserved for the in-development multi-material path**: every shipped printer is single-head
today, so `toolhead_count` is **always 1** right now and the SPA renders a single material
picker. When multi-material ships, a printer reporting `toolhead_count > 1` will drive one
material dropdown per extruder and the `filament_slot_*` slice request (see `POST /api/slice`).

### GET `/api/templates`

The part-library catalog the browser modal renders, derived live from the template registry
(the single source — the catalog grows here automatically as families are added). Returns
`{"families": [...]}`, each family:

```json
{
  "name": "tube",
  "summary": "A ring / cylindrical spacer or standoff.",
  "examples": ["tube", "ring", "spacer", "standoff"],
  "seed": "a tube",
  "param_count": 3,
  "tier": "benchmarked"
}
```

`seed` is the article-correct prompt the modal submits through the normal design flow (the
library has no separate seeding path). `tier` is the honesty label: `benchmarked`
(what-you-set-is-what-you-get) or `baseline` (real, gate-verified geometry with a fitness
caveat to verify before real use). The tier is display-only — every family is verified
against its analytic bounding box by a real render regardless of label.

### GET `/api/model-status`

The AI layer's health: `backend` (`local`/`cloud`), `model`, `running`, `model_present`,
and the vision model's presence (`vision_model`, `vision_present`). Never echoes the cloud
key.

### POST `/api/model-pull` · GET `/api/model-pull/progress`

Start (or report) the in-app download of KimCad's own models into a LOCAL loopback Ollama —
the pull list is fixed server-side, never caller-supplied. Idempotent; progress reports
per-model `{status, completed, total}`.

### GET `/api/health` (· `/api/health?recheck=1`)

Tool + app health: `{"version": "...", "openscad": true, "orcaslicer": true,
"cadquery": false}`. With `recheck=1` the server drops its cached CadQuery probe and
discovers fresh (the Settings card's *check again* after the one-time engine install).

---

## Security model (summary)

The server binds **loopback-only** by default and refuses a non-loopback host without an
explicit `--allow-remote` acknowledgment (it then prints a no-auth warning). Secrets
(cloud key, printer access codes) never appear in any response, log, or error; the design
pipeline's generated code runs through static sanitizers and arm's-length worker
processes. Full detail: [`SECURITY.md`](../SECURITY.md) and
[`cadquery-backend.md`](cadquery-backend.md).

**Session token on state-changing requests (KC-26).** The server issues a fresh random token
each boot, injects it into the page shell (`<meta name="kimcad-session-token">`), and the SPA
returns it as the `X-KimCad-Session` header on every POST. A state-changing request without the
matching token (constant-time compared) is refused `403`. This blocks a drive-by **cross-origin**
POST from a malicious web page, in that order of weight: it cannot *read* this same-origin token
(so it can't supply a valid header at all); a request that simply omits the header is refused
outright (empty ≠ token); and trying to *fake* the header forces a CORS preflight the server
doesn't satisfy. A few **side-effecting GETs** that can't carry the token because they're
navigations/reads — the lazy STEP build (`/api/step/<id>`) and the health re-probe
(`/api/health?recheck=1`) — instead refuse a cross-origin request via the browser's
`Sec-Fetch-Site` header. Ordinary GETs are never gated.

This is deliberate defense-in-depth, **not** full CSRF protection, and **not authentication**:
KimCad is a single-user loopback app with no cookie-based session to forge, so a constant per-boot
bearer the attacker can't read is the proportionate measure (per-request form nonces and
`SameSite` cookies would add machinery without a matching threat). Note it does **not** authenticate
a *remote* client on `--allow-remote`: any client that can load the page over HTTP reads the token
from the shell, so `--allow-remote` remains unauthenticated (the CLI warns of this) — the token only
stops a blind cross-origin POST. Because the token rotates per boot, a tab left open across a server
restart will `403`; the SPA detects this (`reason:"session"`) and shows a one-click **Reload**
banner — reloading re-fetches the freshly injected token.
