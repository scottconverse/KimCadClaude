import { afterEach, describe, expect, it, vi } from 'vitest'
import { designIdFromMeshUrl, getOptions, postDesign, postSlice } from './api'

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

describe('designIdFromMeshUrl', () => {
  it('extracts the trailing id, or null when there is no usable id', () => {
    expect(designIdFromMeshUrl('/api/mesh/7')).toBe(7)
    expect(designIdFromMeshUrl('/api/mesh/42')).toBe(42)
    expect(designIdFromMeshUrl(undefined)).toBeNull()
    expect(designIdFromMeshUrl('/api/mesh/not-a-number')).toBeNull()
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
