// Typed client for KimCad's local JSON API (served by src/kimcad/webapp.py).
//
// Slice 3 wires only the design call (enough to load a real mesh into the viewport). The
// richer parts of the response (plan / printability report / clarification / the four
// PipelineStatus values) are rendered in Slice 4; the types are declared here so that wiring
// is a fill-in, not a reshape.

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

export interface DesignResponse {
  status: string
  prompt?: string
  clarification?: string
  plan?: PlanPayload
  report?: ReportPayload
  error?: string
  has_mesh: boolean
  mesh_url?: string
}

export async function postDesign(prompt: string): Promise<DesignResponse> {
  const res = await fetch('/api/design', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })
  let data: unknown
  try {
    data = await res.json()
  } catch {
    throw new Error(`KimCad returned an unreadable response (HTTP ${res.status}).`)
  }
  if (!res.ok) {
    const msg = (data as { error?: string } | null)?.error
    throw new Error(msg || `Request failed (HTTP ${res.status}).`)
  }
  return data as DesignResponse
}
