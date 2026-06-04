import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  designIdFromMeshUrl,
  exportDesignUrl,
  getOptions,
  importDesign,
  postDesign,
  postRender,
  postSettings,
  postSlice,
  uploadPhoto,
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
})
