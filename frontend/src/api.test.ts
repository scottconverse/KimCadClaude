import { afterEach, describe, expect, it, vi } from 'vitest'
import { designIdFromMeshUrl, getOptions, postDesign, postRender, postSlice } from './api'

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
