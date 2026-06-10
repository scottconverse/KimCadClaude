import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  deleteDesign,
  designIdFromMeshUrl,
  duplicateDesign,
  exportDesignUrl,
  getConnectors,
  getConnectorStatus,
  getDesignProgress,
  getDesigns,
  getHealth,
  getModelStatus,
  getOptions,
  getSettings,
  importDesign,
  isAbortError,
  postDesign,
  postRender,
  postSettings,
  postSlice,
  renameDesign,
  reopenDesign,
  saveDesign,
  sendDesign,
  uploadPhoto,
  uploadSketch,
} from './api'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockFetch(impl: () => Promise<unknown>) {
  const fn = vi.fn(impl)
  vi.stubGlobal('fetch', fn)
  return fn
}

describe('postDesign', () => {
  it('returns the parsed body on a 200', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ status: 'completed', has_mesh: false }),
    }))
    const result = await postDesign('a box')
    expect(result.status).toBe('completed')
    expect(result.has_mesh).toBe(false)
  })

  it('throws the backend error message on a non-2xx', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: 'Please describe the part you want.' }),
    }))
    await expect(postDesign('')).rejects.toThrow('Please describe the part you want.')
  })

  it('throws a readable error when the body is not JSON', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json')
      },
    }))
    await expect(postDesign('x')).rejects.toThrow(/unreadable/i)
  })

  // Slice 6 MS-4: the consumer opts OUT of the experimental generator by default.
  it('sends experimental:false by default (no history)', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'completed' }) }))
    await postDesign('a box')
    const body = JSON.parse(((f.mock.calls[0] as unknown[])[1] as RequestInit).body as string)
    expect(body).toEqual({ prompt: 'a box', experimental: false })
  })

  it('sends experimental:true + threads history when opted in', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'completed' }) }))
    await postDesign('taller', [{ role: 'user', content: 'a box' }], true)
    const body = JSON.parse(((f.mock.calls[0] as unknown[])[1] as RequestInit).body as string)
    expect(body.experimental).toBe(true)
    expect(body.history).toEqual([{ role: 'user', content: 'a box' }])
  })

  // The user must be able to cancel a long local-model run — postDesign forwards an AbortSignal.
  it('passes the AbortSignal to fetch so a design can be cancelled', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'completed' }) }))
    const ctrl = new AbortController()
    await postDesign('a box', undefined, false, ctrl.signal)
    const init = (f.mock.calls[0] as unknown[])[1] as RequestInit
    expect(init.signal).toBe(ctrl.signal)
  })

  // MS-3: a job id lets the UI poll the run's live phase; it's only sent when provided.
  it('includes the job_id in the body when one is provided', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'completed' }) }))
    await postDesign('a box', undefined, false, undefined, 'job-123')
    const body = JSON.parse(((f.mock.calls[0] as unknown[])[1] as RequestInit).body as string)
    expect(body.job_id).toBe('job-123')
  })
})

describe('getDesignProgress (MS-3)', () => {
  it('returns the phase from a 200 body', async () => {
    mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ phase: 'rendering' }) }))
    expect(await getDesignProgress('job-1')).toEqual({ phase: 'rendering' })
  })

  it('resolves to a null phase on a non-ok response (never throws — polling is best-effort)', async () => {
    mockFetch(async () => ({ ok: false, status: 404, json: async () => ({}) }))
    expect(await getDesignProgress('job-1')).toEqual({ phase: null })
  })

  it('resolves to a null phase when fetch itself rejects', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))
    expect(await getDesignProgress('job-1')).toEqual({ phase: null })
  })
})

describe('isAbortError', () => {
  it('recognizes an aborted-fetch error and nothing else', () => {
    expect(isAbortError(Object.assign(new Error('x'), { name: 'AbortError' }))).toBe(true)
    // The real browser path: fetch rejects with a DOMException named 'AbortError'.
    expect(isAbortError(new DOMException('aborted', 'AbortError'))).toBe(true)
    expect(isAbortError(new DOMException('boom', 'NetworkError'))).toBe(false)
    expect(isAbortError(new Error('a real failure'))).toBe(false)
    expect(isAbortError(null)).toBe(false)
  })
})

describe('postSettings', () => {
  it('posts a reset flag to clear everything to defaults', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ saved: true }) }))
    await postSettings({ reset: true })
    const body = JSON.parse(((f.mock.calls[0] as unknown[])[1] as RequestInit).body as string)
    expect(body).toEqual({ reset: true })
  })
})

describe('uploadPhoto (Slice 7)', () => {
  it('POSTs the photo to /api/photo-seed and returns the seed', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'a rough box' }) }))
    const file = new File([new Uint8Array([1, 2, 3])], 'p.png', { type: 'image/png' })
    const r = await uploadPhoto(file)
    expect(r.seed).toBe('a rough box')
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/photo-seed')
    expect((call[1] as RequestInit).method).toBe('POST')
  })

  it('rejects an oversized photo up front (no request)', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'x' }) }))
    const big = { size: 13 * 1024 * 1024, type: 'image/png' } as File
    await expect(uploadPhoto(big)).rejects.toThrow(/too large/i)
    expect(f.mock.calls.length).toBe(0)
  })

  // The user must be able to cancel a slow local-vision read — uploadPhoto forwards an AbortSignal.
  it('forwards an AbortSignal to fetch so a slow read can be cancelled', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'x' }) }))
    const ctrl = new AbortController()
    const file = new File([new Uint8Array([1, 2, 3])], 'p.png', { type: 'image/png' })
    await uploadPhoto(file, ctrl.signal)
    const init = (f.mock.calls[0] as unknown[])[1] as RequestInit
    expect(init.signal).toBe(ctrl.signal)
  })

  // TEST-702: the server's friendly 422/413 message must reach the UI (the error-recovery copy is
  // the user's only feedback on a vision failure). Exercises the real throwIfNotOk/readJson seam.
  it('throws the backend error message on a non-2xx (422 vision failure)', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ error: 'Couldn’t read that photo — try a clearer shot, or cancel and describe the part in words.' }),
    }))
    const file = new File([new Uint8Array([1, 2, 3])], 'p.png', { type: 'image/png' })
    await expect(uploadPhoto(file)).rejects.toThrow(/couldn.t read that photo/i)
  })

  it('throws a readable error when the photo response body is not JSON', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json')
      },
    }))
    const file = new File([new Uint8Array([1, 2, 3])], 'p.png', { type: 'image/png' })
    await expect(uploadPhoto(file)).rejects.toThrow(/unreadable/i)
  })
})

// TEST-001 (stage-9 gate): uploadSketch is a separate transport function — its endpoint, size
// cap, abort plumbing, and error mapping were untested (the component tests mock it away).
describe('uploadSketch (Stage 9)', () => {
  const file = () => new File([new Uint8Array([1, 2, 3])], 's.png', { type: 'image/png' })

  it('POSTs the sketch to /api/sketch-seed and returns the seed', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'a 40mm bracket' }) }))
    const r = await uploadSketch(file())
    expect(r.seed).toBe('a 40mm bracket')
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/sketch-seed')
    expect((call[1] as RequestInit).method).toBe('POST')
  })

  it('rejects an oversized sketch up front (no request)', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'x' }) }))
    const big = { size: 13 * 1024 * 1024, type: 'image/png' } as File
    await expect(uploadSketch(big)).rejects.toThrow(/too large/i)
    expect(f.mock.calls.length).toBe(0)
  })

  it('forwards an AbortSignal to fetch so a slow read can be cancelled', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ seed: 'x' }) }))
    const ctrl = new AbortController()
    await uploadSketch(file(), ctrl.signal)
    const init = (f.mock.calls[0] as unknown[])[1] as RequestInit
    expect(init.signal).toBe(ctrl.signal)
  })

  it('throws the backend error message on a non-2xx (422 vision failure)', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 422,
      json: async () => ({ error: 'Couldn’t read that sketch — try a clearer image with written dimensions.' }),
    }))
    await expect(uploadSketch(file())).rejects.toThrow(/couldn.t read that sketch/i)
  })

  it('maps a model_unavailable status to its friendly message (the sketch was fine)', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ status: 'model_unavailable', error: 'KimCad couldn’t reach your local AI.' }),
    }))
    await expect(uploadSketch(file())).rejects.toThrow(/reach your local AI/i)
  })
})

describe('postDesign template payload', () => {
  it('parses template family + parameters when present', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'completed',
        has_mesh: true,
        mesh_url: '/api/mesh/3',
        template: 'snap_box',
        parameters: [
          { name: 'width', label: 'Width', value: 80, min: 20, max: 200, step: 1, unit: 'mm', integer: false },
        ],
      }),
    }))
    const result = await postDesign('a snap box')
    expect(result.template).toBe('snap_box')
    expect(result.parameters?.[0].name).toBe('width')
    expect(result.parameters?.[0].value).toBe(80)
  })
})

describe('postRender', () => {
  it('POSTs the values to /api/render/<id> and returns the re-rendered payload', async () => {
    const fetchMock = mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        status: 'completed',
        has_mesh: true,
        mesh_url: '/api/mesh/3?v=2',
        template: 'snap_box',
        parameters: [
          { name: 'width', label: 'Width', value: 120, min: 20, max: 200, step: 1, unit: 'mm', integer: false },
        ],
      }),
    }))
    const result = await postRender(3, { width: 120 })
    expect(result.mesh_url).toBe('/api/mesh/3?v=2')
    expect(result.parameters?.[0].value).toBe(120)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/render/3',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ values: { width: 120 } }),
      }),
    )
  })

  it('throws the backend error message on a non-2xx', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ error: 'This design has no adjustable parameters.' }),
    }))
    await expect(postRender(9, { width: 1 })).rejects.toThrow(/no adjustable parameters/i)
  })
})

describe('designIdFromMeshUrl', () => {
  it('extracts the trailing id, or null when there is no usable id', () => {
    expect(designIdFromMeshUrl('/api/mesh/7')).toBe(7)
    expect(designIdFromMeshUrl('/api/mesh/42')).toBe(42)
    expect(designIdFromMeshUrl(undefined)).toBeNull()
    expect(designIdFromMeshUrl('/api/mesh/not-a-number')).toBeNull()
  })

  it('strips a cache-busting version query from a re-rendered mesh URL', () => {
    expect(designIdFromMeshUrl('/api/mesh/7?v=2')).toBe(7)
    expect(designIdFromMeshUrl('/api/mesh/42?v=137')).toBe(42)
  })
})

describe('importDesign / exportDesignUrl (Stage 8.5)', () => {
  it('returns the new id on a 200', async () => {
    const fetchMock = mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ id: 'imp9' }),
    }))
    const file = new File([new Uint8Array([0x50, 0x4b])], 'd.kimcad', { type: 'application/zip' })
    const r = await importDesign(file)
    expect(r.id).toBe('imp9')
    expect(fetchMock).toHaveBeenCalledWith('/api/designs/import', expect.objectContaining({ method: 'POST' }))
  })

  it('throws the backend error message on a non-2xx', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 400,
      json: async () => ({ error: "That file isn't a valid KimCad design export." }),
    }))
    const file = new File([new Uint8Array([1, 2])], 'd.kimcad')
    await expect(importDesign(file)).rejects.toThrow(/valid KimCad design export/i)
  })

  it('throws a readable error when the import body is not JSON', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json')
      },
    }))
    const file = new File([new Uint8Array([0x50, 0x4b])], 'd.kimcad')
    await expect(importDesign(file)).rejects.toThrow(/unreadable/i)
  })

  it('rejects an over-cap file up front with a friendly message and never fetches (QA-004)', async () => {
    const fetchMock = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ id: 'x' }) }))
    const big = { size: 33 * 1024 * 1024 } as File // only .size is read before the cap check
    await expect(importDesign(big)).rejects.toThrow(/too large/i)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('surfaces a friendly message when the upload connection fails (QA-004)', async () => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    })
    vi.stubGlobal('fetch', fetchMock)
    const file = new File([new Uint8Array([0x50, 0x4b])], 'd.kimcad')
    await expect(importDesign(file)).rejects.toThrow(/too large|unreadable/i)
  })

  it('url-encodes the id in the export URL', () => {
    expect(exportDesignUrl('a/b')).toBe('/api/designs/a%2Fb/export')
    expect(exportDesignUrl('abc123')).toBe('/api/designs/abc123/export')
  })
})

describe('getOptions / postSlice', () => {
  it('getOptions parses the printer/material options', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        printers: [{ key: 'p2s', name: 'P2S', sliceable: true, materials: ['pla'], generic_materials: [] }],
        materials: [{ key: 'pla', name: 'PLA' }],
        default_printer: 'p2s',
        default_material: 'pla',
      }),
    }))
    const options = await getOptions()
    expect(options.printers[0].sliceable).toBe(true)
    expect(options.default_printer).toBe('p2s')
  })

  it('postSlice POSTs to /api/slice/<id> and returns the slice result', async () => {
    const fetchMock = mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ sliced: true, gcode_url: '/api/gcode/7', estimate: '~1h' }),
    }))
    const result = await postSlice(7, 'p2s', 'pla')
    expect(result.sliced).toBe(true)
    expect(result.gcode_url).toBe('/api/gcode/7')
    expect(fetchMock).toHaveBeenCalledWith('/api/slice/7', expect.objectContaining({ method: 'POST' }))
  })

  it('postSlice forwards an AbortSignal so a slow slice can be cancelled', async () => {
    const fetchMock = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ sliced: true }) }))
    const ctrl = new AbortController()
    await postSlice(7, 'p2s', 'pla', ctrl.signal)
    expect((fetchMock.mock.calls[0] as unknown[])[1]).toMatchObject({ signal: ctrl.signal })
  })
})

// TEST-403: the settings/status GETs and the "My Designs" CRUD wrappers were the seam most exposed
// to a silent contract drift (URL typo, missing id-encoding, swallowed backend error). Thin tests
// pin each one's URL/method/body, the encodeURIComponent on every id, and error propagation.
describe('settings + status GET wrappers (TEST-403)', () => {
  it.each([
    ['getSettings', getSettings, '/api/settings'],
    ['getModelStatus', getModelStatus, '/api/model-status'],
    ['getHealth', getHealth, '/api/health'],
    ['getConnectors', getConnectors, '/api/connectors'],
    ['getDesigns', getDesigns, '/api/designs'],
  ] as const)('%s GETs %s and returns the parsed body', async (_name, fn, url) => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) }))
    await fn()
    // A bare fetch(url) (GET) — no method/second arg, or an explicit GET.
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe(url)
    const init = call[1] as RequestInit | undefined
    expect(init?.method ?? 'GET').toBe('GET')
  })

  it('getConnectors returns the configured/simulated flags (QA-002 contract)', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        connectors: [{ name: 'octoprint', simulated: false, configured: false }],
        default: 'mock',
      }),
    }))
    const r = await getConnectors()
    expect(r.connectors[0]).toMatchObject({ simulated: false, configured: false })
  })

  // Stage 10: the direct-print send. The endpoint, body shape, and soft-outcome passthrough.
  it('sendDesign POSTs the connector choice to /api/send/<id> and returns the outcome', async () => {
    const f = mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ sent: true, connector: 'mock', simulated: true, job_id: 'j1', state: 'queued' }),
    }))
    const r = await sendDesign(4, 'mock')
    expect(r.sent).toBe(true)
    expect(r.simulated).toBe(true)
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/send/4')
    const init = call[1] as RequestInit
    expect(init.method).toBe('POST')
    expect(JSON.parse(String(init.body))).toEqual({ connector: 'mock' })
  })

  it('sendDesign passes a soft not-sent outcome through (no throw on sent:false)', async () => {
    mockFetch(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ sent: false, simulated: false, reason: 'offline', note: 'No answer.' }),
    }))
    const r = await sendDesign(4, 'octoprint')
    expect(r.sent).toBe(false)
    expect(r.reason).toBe('offline')
  })

  it('sendDesign throws the backend error message on a non-2xx', async () => {
    mockFetch(async () => ({
      ok: false,
      status: 404,
      json: async () => ({ error: 'Slice the part first, then send it to a printer.' }),
    }))
    await expect(sendDesign(99, 'mock')).rejects.toThrow(/slice the part first/i)
  })

  it('getConnectorStatus url-encodes the connector name', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ name: 'a b', ready: false }) }))
    await getConnectorStatus('a b')
    expect((f.mock.calls[0] as unknown[])[0]).toBe('/api/connector-status/a%20b')
  })

  it('propagates the backend error message on a non-2xx GET', async () => {
    mockFetch(async () => ({ ok: false, status: 503, json: async () => ({ error: 'Saved designs aren’t available right now.' }) }))
    await expect(getDesigns()).rejects.toThrow(/aren.t available/i)
  })
})

describe('My Designs CRUD wrappers (TEST-403)', () => {
  it('saveDesign POSTs the id/name/thumbnail/saved_id to /api/designs/save', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ id: 's1', name: 'Box' }) }))
    const r = await saveDesign(7, 'Box', 'data:image/png;base64,AA==', 's1')
    expect(r.id).toBe('s1')
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/designs/save')
    expect((call[1] as RequestInit).method).toBe('POST')
    const body = JSON.parse((call[1] as RequestInit).body as string)
    expect(body).toEqual({ design_id: 7, name: 'Box', thumbnail: 'data:image/png;base64,AA==', saved_id: 's1' })
  })

  it('reopenDesign GETs /api/designs/<id> with the id url-encoded', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ status: 'completed', has_mesh: true }) }))
    await reopenDesign('a/b')
    expect((f.mock.calls[0] as unknown[])[0]).toBe('/api/designs/a%2Fb')
  })

  it('renameDesign POSTs the new name to /api/designs/<id>/rename (id encoded)', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) }))
    await renameDesign('a b', 'New name')
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/designs/a%20b/rename')
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({ name: 'New name' })
  })

  it('deleteDesign POSTs to /api/designs/<id>/delete (id encoded)', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ ok: true }) }))
    await deleteDesign('a/b')
    const call = f.mock.calls[0] as unknown[]
    expect(call[0]).toBe('/api/designs/a%2Fb/delete')
    expect((call[1] as RequestInit).method).toBe('POST')
  })

  it('duplicateDesign POSTs to /api/designs/<id>/duplicate and returns the new id', async () => {
    const f = mockFetch(async () => ({ ok: true, status: 200, json: async () => ({ ok: true, id: 'dup1' }) }))
    const r = await duplicateDesign('abc')
    expect(r.id).toBe('dup1')
    expect((f.mock.calls[0] as unknown[])[0]).toBe('/api/designs/abc/duplicate')
  })

  it('propagates the backend error message on a failed save', async () => {
    mockFetch(async () => ({ ok: false, status: 404, json: async () => ({ error: 'That design is no longer available to save.' }) }))
    await expect(saveDesign(9, '', null)).rejects.toThrow(/no longer available/i)
  })
})
