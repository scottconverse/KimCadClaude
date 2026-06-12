// Typed client for KimCad's local JSON API (served by src/kimcad/webapp.py).

export interface PlanPayload {
  object_type: string
  summary: string
  target_bbox_mm: number[] | null
}

export interface ReportDim {
  axis: string
  target: number
  actual: number
  ok: boolean
}

// One readiness risk shown on the Smart Mesh card — a short title + a plain detail + a tone
// ('warn' | 'fail') that drives the amber/red treatment. Mirrors smart_mesh.Risk.
// Slice 8: a risk located by PrintProof3D also carries its geometry (so the viewport can show it
// ON the model) plus an issueId/region (click-to-focus). Gate-derived risks omit these.
export interface ReadinessRisk {
  title: string
  detail: string
  tone: string
  issueId?: string
  region?: string
  geometry?: import('./viewport/KCViewport').HLGeometry
}

// The Smart Mesh readiness verdict (Stage 7): a 0-100 score, a plain verdict, a confidence, the
// risks, concrete recommendations, an optional history comparison, and what backed the assessment
// (the gate alone, or the PrintProof3D engine). Mirrors smart_mesh.MeshReadiness; `null` when the
// pipeline didn't attach one (older results / non-completed paths).
export interface ReadinessPayload {
  score: number
  verdict: string
  tone: string
  confidence: string
  risks: ReadinessRisk[]
  recommendations: string[]
  comparison: string | null
  attribution: string
}

export interface ReportPayload {
  gate_status: string
  headline: string
  // Which geometry backend built the part: 'openscad' (default) or 'cadquery' (Stage 8 parallel
  // backend). A CadQuery part also exposes an editable STEP export via `step_url`.
  backend?: string
  dims: ReportDim[]
  findings: Array<{ level: string; code: string; message: string }>
  watertight?: boolean
  volume_mm3?: number
  orientation?: string
  readiness?: ReadinessPayload | null
}

// One typed, range-bounded parameter — a single live slider. Mirrors the backend's
// TemplateMatch.parameters() snapshot (src/kimcad/templates.py): the spec plus its CURRENT
// value. `integer` means the slider only ever sends whole numbers.
export interface ParamSpec {
  name: string
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  integer: boolean
  // X/Y/Z for a dimensional parameter (ties the slider to the viewport's W/D/H pills); absent
  // for non-dimensional params like wall thickness.
  axis?: string
}

export interface DesignResponse {
  status: string
  prompt?: string
  clarification?: string
  plan?: PlanPayload
  report?: ReportPayload
  error?: string
  has_mesh: boolean
  mesh_url?: string
  // The editable-CAD (.STEP) download. KC-2 (#8): template-built parts get this from their
  // TRUSTED CadQuery twin (built lazily on first download) whenever a CadQuery engine is
  // present; absent for LLM-OpenSCAD parts (OpenSCAD can't emit a BREP/STEP).
  step_url?: string
  // KC-11 (#15): a template part that COULD export .STEP but has no CadQuery engine installed —
  // the UI points at Settings (the guided install card) instead of dangling a dead promise.
  step_offer?: string
  // Template-backed (deterministic) designs carry their family name + the live-slider params.
  // LLM-backed parts have neither — there are no parametric sliders to drive.
  template?: string
  parameters?: ParamSpec[]
  // Stage 8.5: set when this response is a REOPENED saved design — the store id it came from, so
  // the UI knows it's already in the library (and which entry it is).
  saved_id?: string
}

// Stage 8.5 — a saved design as it appears in the "My Designs" library index.
export interface SavedDesignSummary {
  id: string
  name: string
  created_at: string
  object_type: string
  gate_status: string
  readiness_score: number | null
  has_thumb: boolean
  thumb_url: string | null
}

export interface PrinterOption {
  key: string
  name: string
  // Build envelope [x, y, z] in mm (null when not configured) — drives the Topbar printer chip.
  build_volume?: [number, number, number] | null
  sliceable: boolean
  materials: string[]
  generic_materials: string[]
}

export interface MaterialOption {
  key: string
  name: string
}

export interface OptionsResponse {
  printers: PrinterOption[]
  materials: MaterialOption[]
  default_printer: string | null
  default_material: string | null
}

// Structured slice estimate (parsed by the slicer from the G-code header). Any field can be
// null when the printer's profile didn't emit that line. Lets the UI lay out a labeled
// breakout — print time, layers, filament length + weight — instead of one text blob.
export interface EstimateDetail {
  time: string | null
  layers: number | null
  filament_mm: number | null
  filament_cm3: number | null
  filament_g: number | null
  // True when the weight was estimated by KimCad from volume × nominal density (because the
  // slicer profile reported no grams), rather than computed by the slicer itself.
  filament_g_estimated?: boolean
}

export interface SliceResponse {
  sliced: boolean
  reason?: string
  note?: string
  printer?: string
  material?: string
  gcode_lines?: number | null
  estimate?: string
  estimate_detail?: EstimateDetail | null
  profiles?: { machine: string; process: string; filament: string }
  gcode_url?: string
  gcode_filename?: string
}

export interface ConnectorStatusResponse {
  name: string
  ready: boolean
  online?: boolean
  state?: string
  detail?: string
  reason?: string
  simulated: boolean
  note?: string
}

export interface ConnectorsResponse {
  // `simulated` = a no-hardware loopback; `configured` = set up enough to actually send (QA-002) —
  // e.g. an OctoPrint template with no API key is `simulated:false, configured:false`.
  connectors: Array<{ name: string; simulated: boolean; configured: boolean }>
  default: string | null
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    throw new Error(`KimCad returned an unreadable response (HTTP ${res.status}).`)
  }
}

function throwIfNotOk(res: Response, data: unknown): void {
  if (!res.ok) {
    const msg = (data as { error?: string } | null)?.error
    throw new Error(msg || `Request failed (HTTP ${res.status}).`)
  }
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as T
}

async function postJson<T>(url: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as T
}

/** One turn of the design conversation, as sent back to the model on a follow-up. */
export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

/** A turn as rendered in the conversation thread — a ChatTurn plus an optional error tone for a
 * failed reply (the failure reads as a failure, not a neutral message). */
export interface Message extends ChatTurn {
  tone?: 'error'
}

/** One saved version of a design — the full conversation thread and the result at that point.
 * Stage 8.5 Slice 2: each successful refinement push a new version, so the user can step back. */
export interface DesignVersion {
  index: number            // 1-based display label ("v1", "v2", …)
  messages: Message[]      // the conversation thread up to and including this version's reply
  result: DesignResponse   // the design result (mesh_url still valid if server hasn't evicted)
  label: string            // the user prompt that created this version (for the tooltip)
}

/** A special message type rendered as a version comparison card in the thread.
 * Injected when the user clicks Compare in the VersionRail. */
export interface CompareMessage {
  type: 'compare'
  a: DesignVersion
  b: DesignVersion
}

/** Submit a prompt. On a follow-up/refine turn, pass the prior `history` so the model refines the
 * current part in context (Stage 8.5 Slice 2); omit it for a brand-new design.
 *
 * Slice 6 MS-4: `experimental` opts into the raw-codegen generator. The consumer default is
 * `false` — so a request with no deterministic template OFFERS the generator (status
 * `needs_experimental`) instead of auto-running it; the offer's "try it" button re-sends `true`.
 * (The server force-enables it when the user turned the experimental toggle on in Settings.) */
export async function postDesign(
  prompt: string,
  history?: ChatTurn[],
  experimental = false,
  signal?: AbortSignal,
  jobId?: string,
): Promise<DesignResponse> {
  const body: Record<string, unknown> = { prompt, experimental }
  if (history?.length) body.history = history
  // MS-3: an optional client-generated job id lets the UI poll GET /api/design/progress/<id> for
  // the live phase while this (multi-minute) request is in flight. Absent → no progress tracking.
  if (jobId) body.job_id = jobId
  // Own fetch (not postJson) so the caller can pass an AbortSignal — a design can run the local
  // model for minutes, so the user must be able to cancel and escape the "Designing…" screen.
  const res = await fetch('/api/design', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as DesignResponse
}

/** MS-3: poll the live phase of an in-flight design. Best-effort — any error (the run just
 *  finished, a transient blip) resolves to `{ phase: null }` so the poller never throws. */
export async function getDesignProgress(jobId: string): Promise<{ phase: string | null }> {
  try {
    const res = await fetch(`/api/design/progress/${encodeURIComponent(jobId)}`)
    if (!res.ok) return { phase: null }
    const data = await res.json()
    return { phase: typeof data?.phase === 'string' ? data.phase : null }
  } catch {
    return { phase: null }
  }
}

/** True for the error thrown when a fetch is aborted (the user hit Cancel) — distinct from a real
 *  failure, so the UI can return quietly to the prompt instead of showing an error. */
export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException ? err.name === 'AbortError' : (err as { name?: string })?.name === 'AbortError'
}

/** Deterministically re-render a template-backed design at new slider values — no model call.
 * Returns the same payload shape as `postDesign`, with a versioned `mesh_url` (cache-busted) and
 * the server's clamped/validated `parameters` (the source of truth the sliders re-sync to). */
export function postRender(
  designId: number,
  values: Record<string, number>,
): Promise<DesignResponse> {
  return postJson<DesignResponse>(`/api/render/${designId}`, { values })
}

export function getOptions(): Promise<OptionsResponse> {
  return getJson<OptionsResponse>('/api/options')
}

// Stage 8.5 Slice 6 — the in-app Settings screen. The settings GET returns the same printer/material
// choices + effective defaults as /api/options, plus the cloud opt-in state; a POST persists a change
// and echoes back the new settings with a `saved` flag (false if the local store couldn't persist).
// MS-3: the OpenRouter key is only ever returned MASKED (`cloud_key_masked`, last 5) — never in full.
export interface SettingsResponse extends OptionsResponse {
  saved?: boolean
  cloud_enabled?: boolean
  cloud_model?: string
  has_cloud_key?: boolean
  cloud_key_masked?: string | null
  /** ENG-001: where the key lives at rest — "keyring" (OS credential store) or "file"
   * (the disclosed JSON fallback). Absent on older servers. */
  key_storage?: 'keyring' | 'file'
  experimental_enabled?: boolean
}

export function getSettings(): Promise<SettingsResponse> {
  return getJson<SettingsResponse>('/api/settings')
}

// Stage 8.5 Slice 6 MS-2 — the AI model's health for the Settings screen. For the local (Ollama)
// backend, `running` is whether Ollama answered and `model_present` whether the active model is
// pulled, so the UI can show Running / Start Ollama / Get the model. A cloud backend reports
// running:true (it's configured; reachability isn't probed in-band).
export interface ModelStatus {
  model: string
  backend: 'local' | 'cloud'
  running: boolean
  model_present: boolean
  // UX-902 (stage-9 gate): the photo/sketch on-ramps run on a SECOND local model. Optional —
  // a cloud chat backend can't probe the local vision model in-band, so absence means
  // "unknown, don't warn", never "missing".
  vision_model?: string
  vision_present?: boolean
}

export function getModelStatus(): Promise<ModelStatus> {
  return getJson<ModelStatus>('/api/model-status')
}

// Stage 10 Slice 10.4 — in-app model downloads. POST starts pulling whatever of KimCad's
// two models is missing (the list is fixed SERVER-side — no model is ever named from the
// client); idempotent while a pull runs. `not_local` / `ollama_down` are typed statuses.
export interface ModelPullState {
  status: 'queued' | 'pulling' | 'done' | 'error'
  completed: number
  total: number
  error: string
}
export interface ModelPullSnapshot {
  status?: 'ok' | 'ollama_down' | 'not_local'
  error?: string
  running?: boolean
  models?: Record<string, ModelPullState>
}

export async function startModelPull(): Promise<ModelPullSnapshot> {
  const res = await fetch('/api/model-pull', { method: 'POST' })
  const data = await readJson(res)
  if (!res.ok && (data as ModelPullSnapshot).status !== 'not_local') throwIfNotOk(res, data)
  return data as ModelPullSnapshot
}

export function getModelPullProgress(): Promise<ModelPullSnapshot> {
  return getJson<ModelPullSnapshot>('/api/model-pull/progress')
}

// Stage 8.5 Slice 6 MS-5 — tool + app health for the Settings screen: whether the bundled OpenSCAD
// and OrcaSlicer binaries are present, plus the app version.
export interface HealthStatus {
  version: string
  openscad: boolean
  orcaslicer: boolean
  // KC-2 (#8): whether the optional CAD export engine (CadQuery) is installed — drives the
  // Settings card's status line. Optional so an older server payload still type-checks.
  cadquery?: boolean
}

// UI-v2 slice 3 (#23): the library browser's data — the shipped template families.
export interface TemplateFamilyInfo {
  name: string
  summary: string
  examples: string[]
  // The article-correct prompt the modal submits ("a tube", "an open box") — it routes
  // through the NORMAL design flow; the library has no separate seeding machinery.
  seed: string
  param_count: number
}

export function getTemplates(): Promise<{ families: TemplateFamilyInfo[] }> {
  return getJson<{ families: TemplateFamilyInfo[] }>('/api/templates')
}

export function getHealth(recheck = false): Promise<HealthStatus> {
  // KC-2 (#8): recheck drops the server's cached CadQuery probe first — the Settings card's
  // explicit "check again" after the user installs the engine mid-session.
  return getJson<HealthStatus>(recheck ? '/api/health?recheck=1' : '/api/health')
}

// Stage 8.5 Slice 7 — the photo on-ramp. A photo is read by the LOCAL vision model into a ROUGH
// text seed (a description + estimated proportions) that the user confirms/edits, then submits as a
// normal design prompt. The photo never auto-sends off the machine.
export interface PhotoSeedResponse {
  seed: string
}

/** The server's photo cap (mirrors webapp `MAX_PHOTO_BYTES`). Checked client-side so an oversized
 * photo gets a precise message instead of a connection reset. */
export const MAX_PHOTO_BYTES = 12 * 1024 * 1024

export async function uploadPhoto(file: File, signal?: AbortSignal): Promise<PhotoSeedResponse> {
  if (file.size > MAX_PHOTO_BYTES) {
    throw new Error('That photo is too large to read (max 12 MB).')
  }
  let res: Response
  try {
    res = await fetch('/api/photo-seed', {
      method: 'POST',
      headers: { 'Content-Type': file.type || 'image/jpeg' },
      body: file,
      signal,
    })
  } catch (err) {
    if (isAbortError(err)) throw err // a cancel is a cancel — let the caller treat it as one
    throw new Error('Couldn’t read that photo — it may be too large or unreadable.')
  }
  const data = await readJson(res)
  throwIfNotOk(res, data)
  // QA-A-003: a down model server is reported as a typed status (the photo was fine) —
  // surface the friendly start-Ollama message in the on-ramp's error card.
  if ((data as { status?: string }).status === 'model_unavailable') {
    throw new Error((data as { error?: string }).error || 'Your local AI isn’t running yet.')
  }
  return data as PhotoSeedResponse
}

/** Stage 9: the sketch on-ramp — a dimensioned sketch read by the LOCAL vision model into an
 * editable text seed (shape + the labeled dimensions). Same trust rules as the photo path:
 * read locally, never auto-sent, nothing persisted. */
export async function uploadSketch(file: File, signal?: AbortSignal): Promise<PhotoSeedResponse> {
  if (file.size > MAX_PHOTO_BYTES) {
    throw new Error('That sketch is too large to read (max 12 MB).')
  }
  let res: Response
  try {
    res = await fetch('/api/sketch-seed', {
      method: 'POST',
      headers: { 'Content-Type': file.type || 'image/jpeg' },
      body: file,
      signal,
    })
  } catch (err) {
    if (isAbortError(err)) throw err
    throw new Error('Couldn’t read that sketch — it may be too large or unreadable.')
  }
  const data = await readJson(res)
  throwIfNotOk(res, data)
  if ((data as { status?: string }).status === 'model_unavailable') {
    throw new Error((data as { error?: string }).error || 'Your local AI isn’t running yet.')
  }
  return data as PhotoSeedResponse
}

/** Persist a settings change. Pass only the fields you're changing; `null` (or a blank string for
 * the cloud fields) clears that value. The OpenRouter key is sent here to save it but is never
 * returned in full — only the masked form comes back. */
export function postSettings(updates: {
  default_printer?: string | null
  default_material?: string | null
  cloud_enabled?: boolean
  cloud_model?: string | null
  openrouter_api_key?: string | null
  experimental_enabled?: boolean
  reset?: boolean
}): Promise<SettingsResponse> {
  return postJson<SettingsResponse>('/api/settings', updates)
}

export function getConnectors(): Promise<ConnectorsResponse> {
  return getJson<ConnectorsResponse>('/api/connectors')
}

// Stage 10 — direct print from the app. POSTs the chosen connector to the EXISTING send
// endpoint. The POST itself IS the user's confirmation (the server treats it as confirmed and
// re-checks the gate verdict server-side), so this function must only ever be called from an
// explicit confirm action — KimCad never auto-starts a print. A not-sent outcome is SOFT
// (HTTP 200, `sent:false` + typed `reason` + user-facing `note`) — the download always
// remains the fallback.
export interface SendResponse {
  sent: boolean
  connector?: string
  // mirrors the status contract: a loopback/no-hardware connection is labeled simulated, so a
  // mock send is never narrated as a real print (UX-001).
  simulated: boolean
  job_id?: string
  state?: string
  printer_state?: string
  printer_detail?: string
  reason?: string
  note?: string
}

export async function sendDesign(designId: number, connector: string): Promise<SendResponse> {
  const res = await fetch(`/api/send/${designId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ connector }),
  })
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as SendResponse
}

export type PrintOutcome = 'clean' | 'issues' | 'failed' | 'skip'

export async function recordPrintOutcome(
  designId: number,
  outcome: PrintOutcome,
): Promise<{ recorded: boolean; outcome: PrintOutcome }> {
  const res = await fetch(`/api/print-outcome/${designId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ outcome }),
  })
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as { recorded: boolean; outcome: PrintOutcome }
}

export function getConnectorStatus(name: string): Promise<ConnectorStatusResponse> {
  return getJson<ConnectorStatusResponse>(`/api/connector-status/${encodeURIComponent(name)}`)
}

// Stage 11 Slice 11.2 — the in-app Connections card. The secret (access code / API key)
// never crosses this surface in either direction: `api_key_env` is the env VAR'S NAME and
// `env_set` whether it's set. Saving accepts only the non-secret fields.
export interface ConnectionInfo {
  name: string
  type: string
  simulated: boolean
  configured: boolean
  note: string
  base_url: string
  serial: string
  use_ams: boolean
  api_key_env: string
  env_set: boolean
}

export function getConnections(): Promise<{ connections: ConnectionInfo[] }> {
  return getJson<{ connections: ConnectionInfo[] }>('/api/connections')
}

export async function saveConnection(
  name: string,
  updates: { base_url?: string; serial?: string; use_ams?: boolean },
): Promise<{ saved: boolean }> {
  const res = await fetch('/api/connections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, ...updates }),
  })
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as { saved: boolean }
}

export function postSlice(
  designId: number,
  printer: string,
  material: string,
  signal?: AbortSignal,
): Promise<SliceResponse> {
  return postJson<SliceResponse>(`/api/slice/${designId}`, { printer, material }, signal)
}

/** The design id is the trailing path segment of mesh_url (`/api/mesh/<id>`); slicing + g-code
 * download + re-render all key off the same id. A re-render returns a cache-busted, versioned
 * URL (`/api/mesh/<id>?v=2`), so strip any query string before reading the id. Returns null when
 * there's no mesh (nothing to slice). */
export function designIdFromMeshUrl(meshUrl: string | undefined): number | null {
  if (!meshUrl) return null
  const path = meshUrl.split('?')[0]
  const seg = path.split('/').pop()
  const id = seg ? Number.parseInt(seg, 10) : Number.NaN
  return Number.isNaN(id) ? null : id
}

// --- Stage 8.5: saved designs ("My Designs") -------------------------------------------------

/** The library index, newest first. */
export function getDesigns(): Promise<{ designs: SavedDesignSummary[] }> {
  return getJson<{ designs: SavedDesignSummary[] }>('/api/designs')
}

/** Save the current design to the library. `designId` is the live mesh id; the server already
 * holds the mesh + a snapshot, so the client sends only a name and an optional PNG data-URL
 * thumbnail captured from the viewport. */
export function saveDesign(
  designId: number,
  name: string,
  thumbnail: string | null,
  savedId?: string,
): Promise<{ id: string; name: string }> {
  return postJson('/api/designs/save', {
    design_id: designId,
    name,
    thumbnail,
    saved_id: savedId,
  })
}

/** Reopen a saved design — returns a fresh, fully-functional `DesignResponse` (new mesh url, and
 * for a template part the live sliders are restored). */
export function reopenDesign(id: string): Promise<DesignResponse> {
  return getJson<DesignResponse>(`/api/designs/${encodeURIComponent(id)}`)
}

export function renameDesign(id: string, name: string): Promise<{ ok: boolean }> {
  return postJson(`/api/designs/${encodeURIComponent(id)}/rename`, { name })
}

export function deleteDesign(id: string): Promise<{ ok: boolean }> {
  return postJson(`/api/designs/${encodeURIComponent(id)}/delete`, {})
}

export function duplicateDesign(id: string): Promise<{ ok: boolean; id: string | null }> {
  return postJson(`/api/designs/${encodeURIComponent(id)}/duplicate`, {})
}

/** The download URL for a design export (a `.kimcad` zip) — used as an `<a download>` href. */
export function exportDesignUrl(id: string): string {
  return `/api/designs/${encodeURIComponent(id)}/export`
}

/** The server's import body cap (mirrors webapp `MAX_IMPORT_BYTES`). Checked client-side so an
 * oversized file gets a precise message instead of a connection reset (QA-004). */
export const MAX_IMPORT_BYTES = 32 * 1024 * 1024

/** Import a `.kimcad` export file (the raw zip is the POST body); returns the new design's id. */
export async function importDesign(file: File, signal?: AbortSignal): Promise<{ id: string }> {
  // QA-004: reject an over-cap file up front with a friendly message — otherwise the server closes
  // the oversized upload mid-stream and the browser surfaces an opaque "network error".
  if (file.size > MAX_IMPORT_BYTES) {
    throw new Error('That file is too large to import (max 32 MB).')
  }
  let res: Response
  try {
    res = await fetch('/api/designs/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/zip' },
      body: file,
      signal,
    })
  } catch (err) {
    if (isAbortError(err)) throw err // a cancel is a cancel, not an import failure
    // A connection error mid-upload (e.g. the server closed an oversized stream) lands here.
    throw new Error('Couldn’t import that file — it may be too large (max 32 MB) or unreadable.')
  }
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as { id: string }
}
