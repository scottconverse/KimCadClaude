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

export interface ReportPayload {
  gate_status: string
  headline: string
  dims: ReportDim[]
  findings: Array<{ level: string; code: string; message: string }>
  watertight?: boolean
  volume_mm3?: number
  orientation?: string
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

export function postDesign(prompt: string): Promise<DesignResponse> {
  return postJson<DesignResponse>('/api/design', { prompt })
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
