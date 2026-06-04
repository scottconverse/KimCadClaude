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
export interface ReadinessRisk {
  title: string
  detail: string
  tone: string
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

export interface SliceResponse {
  sliced: boolean
  reason?: string
  note?: string
  printer?: string
  material?: string
  gcode_lines?: number | null
  estimate?: string
  profiles?: { machine: string; process: string; filament: string }
  gcode_url?: string
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
  connectors: Array<{ name: string; simulated: boolean }>
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

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
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
 * current part in context (Stage 8.5 Slice 2); omit it for a brand-new design. */
export function postDesign(prompt: string, history?: ChatTurn[]): Promise<DesignResponse> {
  return postJson<DesignResponse>('/api/design', history?.length ? { prompt, history } : { prompt })
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

export function getConnectors(): Promise<ConnectorsResponse> {
  return getJson<ConnectorsResponse>('/api/connectors')
}

export function getConnectorStatus(name: string): Promise<ConnectorStatusResponse> {
  return getJson<ConnectorStatusResponse>(`/api/connector-status/${encodeURIComponent(name)}`)
}

export function postSlice(
  designId: number,
  printer: string,
  material: string,
): Promise<SliceResponse> {
  return postJson<SliceResponse>(`/api/slice/${designId}`, { printer, material })
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
export async function importDesign(file: File): Promise<{ id: string }> {
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
    })
  } catch {
    // A connection error mid-upload (e.g. the server closed an oversized stream) lands here.
    throw new Error('Couldn’t import that file — it may be too large (max 32 MB) or unreadable.')
  }
  const data = await readJson(res)
  throwIfNotOk(res, data)
  return data as { id: string }
}
